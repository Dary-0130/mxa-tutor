from __future__ import annotations

import json
from typing import Any

import pytest

from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.domain.paper_ask import EquationTarget
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper.paper_ask_service import (
    PaperAskService,
    SourceTableEntry,
    build_paper_ask_source_table,
)
from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL


class QueueTextProvider(TextProvider):
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[LLMMessage], bool, float, int | None]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append((messages, json_mode, timeout, max_tokens))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMResponse(
            text=response,
            prompt_tokens=0,
            completion_tokens=0,
            model="fake",
            latency_ms=0,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


@pytest.mark.asyncio
async def test_ask_success_dedupes_citation_ids_and_preserves_first_order() -> None:
    provider = QueueTextProvider([json.dumps(_llm_payload(citation_ids=["S2", "S1", "S2"]))])
    service = PaperAskService(provider)

    response = await service.ask(_record(), _request("  Explain the relation  "))

    assert response.is_fallback is False
    assert [citation.source_id for citation in response.citations] == ["S2", "S1"]
    assert response.session_id == "session-1"
    assert provider.calls[0][1] is True
    prompt_text = provider.calls[0][0][1].content
    assert "  Explain the relation  " in prompt_text


@pytest.mark.asyncio
async def test_unknown_id_in_full_but_not_prompt_source_table_falls_back() -> None:
    record = _many_equation_record(100)
    provider = QueueTextProvider([json.dumps(_llm_payload(citation_ids=["S99"]))])
    service = PaperAskService(provider, source_table_limit=3)

    response = await service.ask(record, _request())

    assert response.is_fallback is True
    assert response.fallback_reason == "invalid_or_missing_citations"
    prompt_text = provider.calls[0][0][1].content
    assert '"source_id": "S3"' in prompt_text
    assert '"source_id": "S99"' not in prompt_text


@pytest.mark.parametrize(
    "case_name",
    [
        "not_json",
        "missing_confidence",
        "bad_confidence",
        "bad_citation_ids_type",
    ],
)
@pytest.mark.asyncio
async def test_malformed_llm_output_falls_back_without_raising(case_name: str) -> None:
    raw_responses = {
        "not_json": "not json",
        "missing_confidence": json.dumps(
            {"answer_kind": "answer", "answer": "ok", "citation_ids": ["S1"]}
        ),
        "bad_confidence": json.dumps(_llm_payload(confidence="certain")),
        "bad_citation_ids_type": json.dumps(_llm_payload(citation_ids="S1")),
    }
    response = await PaperAskService(QueueTextProvider([raw_responses[case_name]])).ask(
        _record(),
        _request(),
    )

    assert response.is_fallback is True
    assert response.fallback_reason == "invalid_or_missing_citations"


@pytest.mark.asyncio
async def test_out_of_scope_falls_back_and_drops_follow_ups() -> None:
    payload = _llm_payload(
        answer_kind="out_of_scope",
        citation_ids=[],
        follow_up_suggestions=["Ask about material that exists in the document"],
    )

    response = await PaperAskService(QueueTextProvider([json.dumps(payload)])).ask(
        _record(),
        _request(),
    )

    assert response.is_fallback is True
    assert response.fallback_reason == "out_of_scope"
    assert response.follow_up_suggestions == []


@pytest.mark.parametrize(
    "case_name",
    [
        "bad_citation_id",
        "forbidden_field",
        "dom_marker_in_answer",
    ],
)
@pytest.mark.asyncio
async def test_raw_anchor_output_falls_back(case_name: str) -> None:
    payloads = {
        "bad_citation_id": _llm_payload(citation_ids=["EQ-01"]),
        "forbidden_field": {**_llm_payload(), "dom_id": "front-end-owned"},
        "dom_marker_in_answer": _llm_payload(answer="-".join(["paper", "eq"]) + "-EQ-01"),
    }
    response = await PaperAskService(QueueTextProvider([json.dumps(payloads[case_name])])).ask(
        _record(),
        _request(),
    )

    assert response.is_fallback is True
    assert response.fallback_reason == "invalid_or_missing_citations"


@pytest.mark.asyncio
async def test_target_drift_falls_back_to_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_entry = SourceTableEntry(
        source_id="S1",
        label="Stale equation",
        excerpt="A stale equation excerpt.",
        source_kind=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        document_label="DOC-001 - paper.pdf",
        target=EquationTarget(kind="equation", equation_id="EQ-stale"),
    )
    monkeypatch.setattr(
        "features.paper.paper_ask_service.build_paper_ask_source_table",
        lambda record: [stale_entry],
    )

    response = await PaperAskService(
        QueueTextProvider([json.dumps(_llm_payload(citation_ids=["S1"]))])
    ).ask(_record(), _request())

    assert response.is_fallback is True
    assert response.fallback_reason == "citation_target_unresolved"


@pytest.mark.asyncio
async def test_figure_only_sources_do_not_call_llm_and_fall_back_insufficient() -> None:
    provider = QueueTextProvider([json.dumps(_llm_payload())])
    response = await PaperAskService(provider).ask(_figure_only_record(), _request())

    assert response.is_fallback is True
    assert response.fallback_reason == "insufficient_evidence"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_section_evidence_degrades_to_section_target() -> None:
    response = await PaperAskService(
        QueueTextProvider([json.dumps(_llm_payload(citation_ids=["S1"]))])
    ).ask(_section_only_record(), _request())

    assert response.is_fallback is False
    target = response.citations[0].target
    assert target.kind == "section"
    assert target.result_section == "paper-subsystems"


def test_source_table_uses_only_real_document_excerpts_not_generated_plan_text() -> None:
    table = build_paper_ask_source_table(
        _record(
            abstract="REAL ABSTRACT EXCERPT",
            equation_text="REAL EQUATION EXCERPT",
            evidence_excerpt="REAL EVIDENCE EXCERPT",
            mapping_value="PLAN GENERATED VALUE",
            subsystem_text="PLAN GENERATED SUBSYSTEM",
        )
    )
    excerpts = [entry.excerpt for entry in table if entry.excerpt is not None]

    assert any("REAL ABSTRACT EXCERPT" in excerpt for excerpt in excerpts)
    assert any("REAL EQUATION EXCERPT" in excerpt for excerpt in excerpts)
    assert any("REAL EVIDENCE EXCERPT" in excerpt for excerpt in excerpts)
    assert all("PLAN GENERATED VALUE" not in excerpt for excerpt in excerpts)
    assert all("PLAN GENERATED SUBSYSTEM" not in excerpt for excerpt in excerpts)


def test_missing_prompts_use_remaining_set_and_user_supplied_maps_to_plan_row() -> None:
    table = build_paper_ask_source_table(_remaining_missing_record())
    missing_targets = [
        entry.target
        for entry in table
        if getattr(entry.target, "kind", None) == "parameter"
        and getattr(entry.target, "origin", None) == "missing_prompt"
    ]
    plan_targets = [
        entry
        for entry in table
        if getattr(entry.target, "kind", None) == "parameter"
        and getattr(entry.target, "origin", None) == "plan_mapping"
    ]

    assert [target.prompt_id for target in missing_targets] == ["MISS-2"]
    assert plan_targets
    assert plan_targets[0].source_kind is EvidenceSource.USER_SUPPLIED
    assert plan_targets[0].excerpt is None
    assert plan_targets[0].target.row_index == 0


@pytest.mark.asyncio
async def test_user_supplied_plan_mapping_can_be_returned_as_citation() -> None:
    response = await PaperAskService(
        QueueTextProvider([json.dumps(_llm_payload(citation_ids=["S1"]))])
    ).ask(_user_mapping_only_record(), _request())

    assert response.is_fallback is False
    citation = response.citations[0]
    assert citation.source_kind is EvidenceSource.USER_SUPPLIED
    assert citation.excerpt is None
    assert citation.target.origin == "plan_mapping"


@pytest.mark.parametrize(
    "exc",
    [
        LLMAuthError("auth"),
        LLMQuotaError("quota"),
        LLMRateLimitError("rate"),
        LLMServerError("server"),
        LLMTimeoutError("timeout"),
    ],
)
@pytest.mark.asyncio
async def test_llm_call_errors_propagate_to_global_handlers(exc: Exception) -> None:
    with pytest.raises(type(exc)):
        await PaperAskService(QueueTextProvider([exc])).ask(_record(), _request())


def _llm_payload(
    *,
    answer_kind: str = "answer",
    answer: str = "The supplied sources support the answer.",
    citation_ids: Any = None,
    confidence: str = "medium",
    follow_up_suggestions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "answer_kind": answer_kind,
        "answer": answer,
        "citation_ids": ["S1"] if citation_ids is None else citation_ids,
        "confidence": confidence,
        "follow_up_suggestions": follow_up_suggestions or [],
    }


def _request(question: str = "What does the source support?"):
    from core.domain.paper_ask import PaperAskRequest

    return PaperAskRequest(question=question, session_id="session-1")


def _record(
    *,
    abstract: str = "A synchronous machine short-circuit report.",
    equation_text: str = "State relation",
    evidence_excerpt: str = "The report states the machine modelling basis.",
    mapping_value: str = "user supplied",
    subsystem_text: str = "Place machine",
) -> PaperPlanRecord:
    evidence = _document_evidence(excerpt=evidence_excerpt)
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract=abstract,
            equations=[
                EquationEntry(
                    equation_id="EQ-01",
                    latex_or_text=equation_text,
                    paper_section_id="S1",
                )
            ],
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[evidence],
        ),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[
                BlockRecommendation(
                    block_type="Synchronous Machine",
                    purpose="Model the generator.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="Inertia",
                    model_param_name="Machine inertia",
                    value=mapping_value,
                    unit="s",
                    source=EvidenceSource.USER_SUPPLIED,
                )
            ],
            subsystem_breakdown=[subsystem_text, "Apply fault", "Observe current"],
            m_script_skeleton=None,
            evidence=[evidence, _user_evidence("MISS-1")],
        ),
        missing_prompts=[_missing_prompt("MISS-1", "Inertia")],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="Inertia",
                model_param_name="Machine inertia",
            )
        ],
    )


def _many_equation_record(count: int) -> PaperPlanRecord:
    record = _record()
    equations = [
        EquationEntry(
            equation_id=f"EQ-{index:03d}", latex_or_text=f"Equation {index}", paper_section_id="S1"
        )
        for index in range(count)
    ]
    return PaperPlanRecord(
        paper_id=record.paper_id,
        spec=PaperSpec(
            paper_title=record.spec.paper_title,
            paper_type=record.spec.paper_type,
            domain=record.spec.domain,
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract=record.spec.abstract,
            equations=equations,
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[],
        ),
        plan=record.plan,
        missing_prompts=record.missing_prompts,
        missing_bindings=record.missing_bindings,
    )


def _figure_only_record() -> PaperPlanRecord:
    evidence = _document_evidence(
        paper_section_id=None,
        figure_id="FIG-1",
        excerpt="Figure-only evidence.",
    )
    return PaperPlanRecord(
        paper_id="paper-figure",
        spec=PaperSpec(
            paper_title="Figure report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="",
            equations=[],
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[evidence],
        ),
        plan=_empty_plan(evidence=[]),
        missing_prompts=[],
        missing_bindings=[],
    )


def _section_only_record() -> PaperPlanRecord:
    evidence = _document_evidence(excerpt="The section describes the plant component.")
    return PaperPlanRecord(
        paper_id="paper-section",
        spec=PaperSpec(
            paper_title="Section report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="",
            equations=[],
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[],
        ),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-section",
            paper_spec_id="paper-section",
            library_choice="SimPowerSystems",
            block_recommendations=[
                BlockRecommendation(
                    block_type="Machine",
                    purpose="Represent the plant.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=[],
            subsystem_breakdown=["Represent plant", "Add input", "Observe output"],
            m_script_skeleton=None,
            evidence=[evidence],
        ),
        missing_prompts=[],
        missing_bindings=[],
    )


def _remaining_missing_record() -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-missing",
        spec=PaperSpec(
            paper_title="Missing report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="",
            equations=[],
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[],
        ),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-missing",
            paper_spec_id="paper-missing",
            library_choice="SimPowerSystems",
            block_recommendations=[],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="Inertia",
                    model_param_name="Machine inertia",
                    value="user supplied",
                    unit="s",
                    source=EvidenceSource.USER_SUPPLIED,
                ),
                ParameterMapping(
                    paper_param_name="Damping",
                    model_param_name="Machine damping",
                    value=MISSING_VALUE_SENTINEL,
                    unit=None,
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                ),
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=None,
            evidence=[_user_evidence("MISS-1")],
        ),
        missing_prompts=[
            _missing_prompt("MISS-1", "Inertia"),
            _missing_prompt("MISS-2", "Damping"),
        ],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="Inertia",
                model_param_name="Machine inertia",
            ),
            MissingParameterBinding(
                prompt_id="MISS-2",
                paper_param_name="Damping",
                model_param_name="Machine damping",
            ),
        ],
    )


def _user_mapping_only_record() -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-user",
        spec=PaperSpec(
            paper_title="User report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="",
            equations=[],
            parameter_table=[],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[],
        ),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-user",
            paper_spec_id="paper-user",
            library_choice="SimPowerSystems",
            block_recommendations=[],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="Inertia",
                    model_param_name="Machine inertia",
                    value="user supplied",
                    unit="s",
                    source=EvidenceSource.USER_SUPPLIED,
                )
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=None,
            evidence=[],
        ),
        missing_prompts=[],
        missing_bindings=[],
    )


def _empty_plan(*, evidence: list[PaperEvidenceEntry]) -> ModelGenerationPlan:
    return ModelGenerationPlan(
        plan_id="PLAN-empty",
        paper_spec_id="paper-empty",
        library_choice="SimPowerSystems",
        block_recommendations=[],
        parameter_mapping=[],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=evidence,
    )


def _missing_prompt(prompt_id: str, parameter_name: str) -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id=prompt_id,
        parameter_name=parameter_name,
        paper_reference=_document_evidence(),
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
    excerpt: str = "The report states the machine modelling basis.",
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt=excerpt,
        missing_param_prompt_id=None,
    )


def _user_evidence(prompt_id: str) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id=prompt_id,
    )
