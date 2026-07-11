from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import eval.run_paper_pdf_smoke as subject
from app.config import AppSettings
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import BlockRecommendation, ParameterMapping
from core.domain.paper_spec import PaperDocument, PaperSpec
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability


def test_discover_papers_marks_hybrid_candidates(tmp_path: Path) -> None:
    hybrid = tmp_path / "arxiv-2003.10496-transient-safety-filter.pdf"
    ordinary = tmp_path / "arxiv-2605.27553-economic-nmpc.pdf"
    hybrid.write_bytes(b"%PDF-")
    ordinary.write_bytes(b"%PDF-")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    papers = subject.discover_papers(tmp_path)

    assert [paper.path.name for paper in papers] == [hybrid.name, ordinary.name]
    assert papers[0].arxiv_id == "2003.10496"
    assert papers[0].hybrid_candidate is True
    assert papers[1].hybrid_candidate is False


def test_hybrid_guardrail_conclusion_distinguishes_not_reached_and_misfire() -> None:
    assert subject.hybrid_guardrail_conclusion(
        hybrid_candidate=True,
        guidance_reached=False,
        guidance_status="未触达",
    ) == ("根本没跑到护栏", None)
    assert subject.hybrid_guardrail_conclusion(
        hybrid_candidate=True,
        guidance_reached=True,
        guidance_status="generated",
    ) == ("护栏没误触发", False)
    assert subject.hybrid_guardrail_conclusion(
        hybrid_candidate=True,
        guidance_reached=True,
        guidance_status="no_document_basis",
    ) == ("no_document_basis误触发", True)


def test_spec_validation_errors_merge_counts_without_values() -> None:
    existing = [{"loc": "abstract", "type": "string_too_long", "count": 1, "max_length": 1500}]
    incoming = (
        {"loc": "abstract", "type": "string_too_long", "count": 2, "max_length": 1500},
        {"loc": "domain", "type": "literal_error", "count": 1},
    )

    assert subject._merge_spec_validation_errors(existing, incoming) == [
        {"loc": "abstract", "type": "string_too_long", "count": 3, "max_length": 1500},
        {"loc": "domain", "type": "literal_error", "count": 1},
    ]


def test_classify_build_steps_result_preserves_bridge_resolution_subcodes() -> None:
    telemetry = subject.BuildStepsTelemetry(
        fallback_reason_code="source_ref_no_match",
        fallback_exception_type="BuildStepsDtoValidationError",
    )

    assert subject.classify_build_steps_result(None, telemetry) == "source_ref_no_match"


def test_pydantic_loc_sanitizer_replaces_dynamic_keys() -> None:
    assert (
        subject._sanitize_pydantic_loc(("build_steps", 0, "evidence", "paper text leaked"))
        == "build_steps.0.evidence.<dynamic_key>"
    )


def test_write_summary_artifacts_uses_fixed_schema(tmp_path: Path) -> None:
    row = _summary_row(tmp_path)

    subject.write_summary_artifacts(tmp_path, [row])

    json_rows = json.loads((tmp_path / "paper_pdf_smoke.summary.json").read_text("utf-8"))
    assert list(json_rows[0]) == subject.SUMMARY_COLUMNS

    with (tmp_path / "paper_pdf_smoke.summary.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == subject.SUMMARY_COLUMNS
        csv_row = next(reader)
    assert json.loads(csv_row["dto_invalid_errors"]) == row.dto_invalid_errors
    assert json.loads(csv_row["spec_validation_errors"]) == row.spec_validation_errors
    assert json.loads(csv_row["llm_model_identifiers"]) == row.llm_model_identifiers
    assert json.loads(csv_row["llm_model_identifier_counts"]) == row.llm_model_identifier_counts
    assert json.loads(csv_row["llm_system_fingerprints"]) == row.llm_system_fingerprints
    assert json.loads(csv_row["llm_system_fingerprint_counts"]) == row.llm_system_fingerprint_counts
    assert json.loads(csv_row["paired_arm_order"]) == row.paired_arm_order
    assert json.loads(csv_row["paired_build_steps_arms"]) == row.paired_build_steps_arms
    assert json.loads(csv_row["violations_by_code"]) == row.violations_by_code
    assert json.loads(csv_row["violation_edges"]) == row.violation_edges
    assert json.loads(csv_row["same_number_probes"]) == row.same_number_probes


def test_llm_model_summary_marks_missing_version_fingerprint() -> None:
    calls = [
        subject.LLMCallRecord(
            role="paper_spec_extractor",
            arm_label=None,
            finish_reason="stop",
            prompt_tokens=1,
            completion_tokens=2,
            max_tokens=3,
            response_model="deepseek-v4-flash",
            system_fingerprint=None,
        )
    ]

    summary = subject._llm_model_summary(calls, no_calls_note="no calls")

    assert summary["model_identifiers"] == ["deepseek-v4-flash"]
    assert summary["model_identifier_counts"] == {"deepseek-v4-flash": 1}
    assert summary["system_fingerprints"] == []
    assert summary["system_fingerprint_counts"] == {}
    assert summary["version_fingerprint_note"] == "供应商未提供版本标识"


def test_paired_build_steps_first_arm_alternates_by_round_index() -> None:
    assert [subject._paired_build_steps_first_arm(index) for index in (1, 2, 3)] == [
        "off",
        "on",
        "off",
    ]


@pytest.mark.asyncio
async def test_paired_build_steps_runs_two_arms_on_same_upstream() -> None:
    fake_provider = _SequenceProvider(
        [
            _build_steps_payload(depends_on_third_step=["STEP-003"]),
            _build_steps_payload(depends_on_third_step=["STEP-001", "STEP-002"]),
        ]
    )
    provider = subject.RecordingTextProvider(fake_provider)
    telemetry = subject.BuildStepsTelemetry()
    service = subject.RecordingPaperPlanService(
        provider,
        telemetry=telemetry,
        paired_build_steps=True,
        pair_order_start="off",
    )

    drafts = await service._llm_build_steps(
        [_block_recommendation()],
        [_parameter_mapping()],
        _paper_spec(),
    )

    assert [call.arm_label for call in provider.calls] == ["off", "on"]
    assert fake_provider.messages[0][1].content == fake_provider.messages[1][1].content
    assert [step.depends_on for step in drafts] == [[], ["STEP-001"], ["STEP-001", "STEP-002"]]
    assert telemetry.paired_arm_order == ["off", "on"]
    assert telemetry.paired_downstream_arm == "on"
    arms = subject._paired_build_steps_arms_for_summary(telemetry, provider.calls)
    assert [arm["arm_label"] for arm in arms] == ["off", "on"]
    assert arms[0]["dependency_audit"]["violations_by_code"]["self"] == 1
    assert arms[1]["dependency_audit"]["dependency_audit_status"] == "clean"
    assert arms[1]["downstream_used"] is True
    assert arms[1]["response_model"] == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_run_smoke_wires_temp_db_upload_dir_and_mock_runner(tmp_path: Path) -> None:
    paper_dir = tmp_path / "papers"
    paper_dir.mkdir()
    (paper_dir / "arxiv-2410.04316-ufls.pdf").write_bytes(b"%PDF-")
    output_dir = tmp_path / "out"
    calls: list[tuple[str, int]] = []

    def settings_factory(runtime: subject.SmokeRuntime) -> AppSettings:
        return AppSettings(
            deepseek_api_key="test-key",
            upload_dir=str(runtime.upload_dir),
            db_path=str(runtime.db_path),
        )

    async def fake_runner(
        paper: subject.SmokePaper,
        round_index: int,
        runtime: subject.SmokeRuntime,
        settings: AppSettings,
        store: object,
        provider_factory: object,
    ) -> subject.SmokeSummaryRow:
        assert Path(settings.upload_dir) == runtime.upload_dir
        assert Path(settings.db_path) == runtime.db_path
        assert runtime.db_path.is_file()
        assert str(runtime.db_path).startswith(str(output_dir.resolve()))
        calls.append((paper.path.name, round_index))
        return _summary_row(runtime.output_dir, paper=paper, round_index=round_index)

    runtime, rows = await subject.run_smoke(
        paper_dir=paper_dir,
        output_dir=output_dir,
        rounds=2,
        settings_factory=settings_factory,
        round_runner=fake_runner,
    )

    assert runtime.output_dir == output_dir.resolve()
    assert calls == [("arxiv-2410.04316-ufls.pdf", 1), ("arxiv-2410.04316-ufls.pdf", 2)]
    assert len(rows) == 2
    assert (output_dir / "paper_pdf_smoke.summary.json").is_file()
    assert (output_dir / "_runtime" / "paper_pdf_smoke.sqlite").is_file()


def test_ci_guard_requires_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")

    with pytest.raises(SystemExit):
        subject._guard_not_ci(allow_ci=False)

    subject._guard_not_ci(allow_ci=True)


def _summary_row(
    tmp_path: Path,
    *,
    paper: subject.SmokePaper | None = None,
    round_index: int = 1,
) -> subject.SmokeSummaryRow:
    paper = paper or subject.SmokePaper(
        path=tmp_path / "arxiv-2003.10496-test.pdf",
        arxiv_id="2003.10496",
        hybrid_candidate=True,
    )
    return subject.SmokeSummaryRow(
        run_id="run",
        paper_file=paper.path.name,
        arxiv_id=paper.arxiv_id,
        round_index=round_index,
        main_terminal_state="ready",
        paper_id="paper-1",
        job_id="job-1",
        error_code=None,
        failure_stage=None,
        spec_validation_errors=[
            {"loc": "abstract", "type": "string_too_long", "count": 1, "max_length": 1500}
        ],
        build_steps_result_code="dto_invalid",
        build_steps_raw_reason_code="dto_invalid",
        build_steps_finish_reason="length",
        build_steps_prompt_tokens=10,
        build_steps_completion_tokens=20,
        build_steps_total_tokens=30,
        build_steps_max_tokens=8000,
        build_steps_response_model="deepseek-v4-flash",
        build_steps_system_fingerprint="fp-test",
        llm_model_identifiers=["deepseek-v4-flash"],
        llm_model_identifier_counts={"deepseek-v4-flash": 1},
        llm_system_fingerprints=["fp-test"],
        llm_system_fingerprint_counts={"fp-test": 1},
        llm_version_fingerprint_note=None,
        run_llm_model_identifiers=["deepseek-v4-flash"],
        run_llm_model_identifier_counts={"deepseek-v4-flash": 1},
        run_llm_system_fingerprints=["fp-test"],
        run_llm_system_fingerprint_counts={"fp-test": 1},
        run_llm_version_fingerprint_note=None,
        paired_build_steps_enabled=False,
        paired_arm_count=0,
        paired_downstream_arm=None,
        paired_arm_order=[],
        paired_build_steps_arms=[],
        guidance_reached=False,
        guidance_status="未触达",
        dto_invalid_errors=[{"loc": "build_steps.0.block_refs.0", "type": "missing"}],
        dependency_audit_status="violations",
        dependency_audit_unavailable_stage=None,
        total_steps=3,
        total_dep_edges=1,
        dep_edge_density=0.5,
        all_empty_dependency_graph=False,
        nonfirst_steps_with_empty_depends_on=0,
        duplicate_step_id_count=0,
        violations_by_code={"self": 1, "unknown": 0, "cycle": 0, "not_prior": 0},
        violation_edges=[
            {
                "step_index": 2,
                "step_id_conforming": True,
                "dep_conforming": True,
                "dep_match_count": 1,
                "dep_index": 2,
                "violation": "self",
                "dep_length_bucket": None,
                "cycle_length_bucket": None,
            }
        ],
        violation_edges_total_count=1,
        violation_edges_truncated=False,
        same_number_probe_count=1,
        dep_ordinal_equals_source_ref_ordinal_count=1,
        same_number_probes=[
            {
                "step_ordinal": 3,
                "dep_ordinal": 3,
                "chosen_source_ref_ordinal": 3,
                "dep_ordinal_equals_source_ref_ordinal": True,
            }
        ],
        connection_ref_not_visible_count=0,
        evidence_ref_count=4,
        block_candidate_count=2,
        parameter_mapping_count=1,
        prompt_tokens_bucket="4001-8000",
        rendered_prompt_version="v0.2",
        hybrid_candidate=paper.hybrid_candidate,
        hybrid_guardrail_conclusion="根本没跑到护栏",
        hybrid_no_document_basis_misfire=None,
    )


class _SequenceProvider:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = list(payloads)
        self.messages: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = json_mode, timeout, max_tokens
        self.messages.append(messages)
        payload = self.payloads.pop(0)
        return LLMResponse(
            text=json.dumps(payload),
            prompt_tokens=10,
            completion_tokens=20,
            model="deepseek-v4-flash",
            latency_ms=1,
            finish_reason="stop",
            system_fingerprint="fp-test",
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="deepseek-v4-flash", supports_json=True)


def _build_steps_payload(*, depends_on_third_step: list[str]) -> dict[str, object]:
    return {
        "build_steps": [
            _build_step_payload("STEP-001", "B1", []),
            _build_step_payload("STEP-002", "B2", ["STEP-001"]),
            _build_step_payload("STEP-003", "B3", depends_on_third_step),
        ]
    }


def _build_step_payload(
    step_id: str, block_ref_id: str, depends_on: list[str]
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "title": f"Build {block_ref_id}",
        "intent": "Place the reusable model block.",
        "block_refs": [
            {
                "block_ref_id": block_ref_id,
                "block_type": "Gain",
                "library_path": None,
                "purpose": "Scale the input signal",
                "paper_reference": {"source_ref": "REF-001"},
            }
        ],
        "parameter_refs": [{"paper_param_name": "K", "model_param_name": "Gain.K"}],
        "connection_hints": [],
        "configuration_hints": [],
        "depends_on": depends_on,
        "evidence": [{"source_ref": "REF-001"}],
    }


def _paper_spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Gain control",
        paper_type="paper",
        domain="control_system",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id="DOC-001",
        abstract="A small control paper.",
        equations=[],
        parameter_table=[],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The paper uses a gain block.",
        missing_param_prompt_id=None,
    )


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Gain",
        purpose="Scale the input signal",
        paper_reference=_document_evidence(),
    )


def _parameter_mapping() -> ParameterMapping:
    return ParameterMapping(
        paper_param_name="K",
        model_param_name="Gain.K",
        value="null",
        unit=None,
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )
