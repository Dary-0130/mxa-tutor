from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import eval.run_paper_pdf_smoke as subject
from app.config import AppSettings


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
        guidance_reached=False,
        guidance_status="未触达",
        dto_invalid_errors=[{"loc": "build_steps.0.block_refs.0", "type": "missing"}],
        hybrid_candidate=paper.hybrid_candidate,
        hybrid_guardrail_conclusion="根本没跑到护栏",
        hybrid_no_document_basis_misfire=None,
    )
