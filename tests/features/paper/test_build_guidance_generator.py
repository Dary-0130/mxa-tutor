from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

import pytest

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    BlockRecommendation,
    BuildGuidance,
    ConnectionHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceGap,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import PaperDocument, PaperSpec, ParameterEntry
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper.build_guidance_generator import (
    BuildGuidanceGenerator,
    GroundingTruthIndex,
    build_guidance_evidence_pool,
    high_risk_claim_tokens,
    synthesize_guidance_gaps,
)
from features.paper.build_guidance_lifecycle import (
    guidance_view_state,
    normalize_guidance_lifecycle,
)
from features.paper.build_guidance_semantic_validator import (
    validate_build_guidance_semantics,
)


class QueueProvider(TextProvider):
    def __init__(self, responses: list[dict[str, object] | str | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = json_mode, timeout, max_tokens
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        text = response if isinstance(response, str) else json.dumps(response)
        return LLMResponse(
            text=text,
            prompt_tokens=0,
            completion_tokens=0,
            model="fake",
            latency_ms=0,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


@pytest.mark.asyncio
async def test_document_claim_requires_resolved_handle_and_grounding_normalizes_units() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "parameter_value",
                        "basis": "document_extracted",
                        "claim_text": "Use the 5 kW load from the paper.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "PL::Load.P",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    }
                ],
                "gaps": [],
            }
        ]
    )

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())

    assert updated.guidance_status == "generated"
    assert guidance_view_state(updated) == "current"
    assert updated.build_guidance is not None
    assert updated.build_guidance.details[0].basis == "document_extracted"
    assert updated.build_guidance.details[0].evidence == [_evidence()]


@pytest.mark.asyncio
async def test_unsupported_engineering_decision_downgrades_without_reusing_claim_text() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "block_selection",
                        "basis": "document_extracted",
                        "claim_text": "Use the synchronous machine block described by the paper.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    },
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "configuration",
                        "basis": "document_extracted",
                        "claim_text": "Enable anti-windup for the controller.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "STEP-001",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    },
                ],
                "gaps": [],
            }
        ]
    )

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())

    assert updated.guidance_status == "generated"
    assert updated.build_guidance is not None
    confirmation = updated.build_guidance.details[1]
    assert confirmation.basis == "user_confirmation_required"
    assert confirmation.confirmation_reason_code == "document_evidence_unverified"
    assert "anti-windup" not in confirmation.display_text.casefold()


@pytest.mark.asyncio
async def test_raw_document_claim_with_unresolved_handle_never_becomes_no_basis() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "block_selection",
                        "basis": "document_extracted",
                        "claim_text": "Use the load block.",
                        "supporting_evidence_refs": ["GEV-999"],
                        "convention_code": None,
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    }
                ],
                "gaps": [],
            },
            {"details": [], "gaps": []},
        ]
    )

    updated = await BuildGuidanceGenerator(provider).generate(
        _spec(), _plan_without_linked_evidence()
    )

    assert updated.guidance_status == "generation_failed"
    assert guidance_view_state(updated) == "failed_retryable"
    assert updated.build_guidance is None


@pytest.mark.asyncio
async def test_raw_document_claim_with_grounding_failure_never_becomes_no_basis() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "configuration",
                        "basis": "document_extracted",
                        "claim_text": "Enable anti-windup for the controller.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "STEP-001",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    }
                ],
                "gaps": [],
            },
            {"details": [], "gaps": []},
        ]
    )

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())

    assert updated.guidance_status == "generation_failed"
    assert guidance_view_state(updated) == "failed_retryable"
    assert updated.build_guidance is None


@pytest.mark.asyncio
async def test_no_basis_requires_zero_raw_document_claims_and_unlinked_evidence_pool() -> None:
    provider = QueueProvider([{"details": [], "gaps": []}, {"details": [], "gaps": []}])

    updated = await BuildGuidanceGenerator(provider).generate(
        _spec(), _plan_without_linked_evidence()
    )

    assert updated.guidance_status == "no_document_basis"
    assert guidance_view_state(updated) == "no_basis"
    assert updated.build_guidance is None


@pytest.mark.asyncio
async def test_semantic_validator_passes_generated_guidance_without_changes() -> None:
    # T1 source: parse_and_ground_guidance_draft + shared CONVENTION_TEMPLATES /
    # CONFIRMATION_REASON_TEMPLATES / GAP_SYNTHESIS_RULES must round-trip unchanged.
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "parameter_value",
                        "basis": "document_extracted",
                        "claim_text": "Use the 5 kW load from the paper.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "PL::Load.P",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    },
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "subsystem_internal_structure",
                        "basis": "engineering_convention",
                        "claim_text": "Use the standard PI convention.",
                        "supporting_evidence_refs": [],
                        "convention_code": "pi_controller_standard_structure",
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                    },
                    {
                        "step_id": "STEP-001",
                        "detail_kind": "configuration",
                        "basis": "user_confirmation_required",
                        "claim_text": "Confirm configuration.",
                        "supporting_evidence_refs": [],
                        "convention_code": None,
                        "target": "STEP-001",
                        "confirmation_reason_code": "configuration_unverified",
                        "direction_hint": "Check source model setup",
                    },
                ],
                "gaps": [],
            }
        ]
    )

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())
    validation = validate_build_guidance_semantics(_spec(), updated)

    assert updated.guidance_status == "generated"
    assert validation.plan == updated
    assert validation.changed is False
    assert validation.item_actions == []
    assert validation.machine_codes == []
    assert validation.whole_action == "keep"


@pytest.mark.parametrize(
    ("_source_note", "mutate", "expected_code"),
    [
        pytest.param(
            "document_extracted evidence: generator _document_detail_from_draft requires resolved evidence",
            lambda plan: _replace_first_detail(plan, evidence=[]),
            "guidance_validator_document_evidence_missing",
            id="source=_document_detail_from_draft/document-evidence-required",
        ),
        pytest.param(
            "document_extracted actionability: legal matrix requires actionable",
            lambda plan: _replace_first_detail(plan, actionability=cast(Any, "notice_only")),
            "guidance_validator_document_actionability_invalid",
            id="source=legal-matrix/document-actionability",
        ),
        pytest.param(
            "engineering_convention evidence: generator _convention_detail_from_draft emits []",
            lambda plan: _with_extra_detail(
                plan,
                _convention_detail(evidence=[_evidence()]),
            ),
            "guidance_validator_convention_evidence",
            id="source=_convention_detail_from_draft/evidence-empty",
        ),
        pytest.param(
            "engineering_convention code: shared CONVENTION_TEMPLATES whitelist",
            lambda plan: _with_extra_detail(
                plan,
                _convention_detail(convention_code=None),
            ),
            "guidance_validator_convention_code_invalid",
            id="source=CONVENTION_TEMPLATES/code-required",
        ),
        pytest.param(
            "engineering_convention code: shared CONVENTION_TEMPLATES whitelist",
            lambda plan: _with_extra_detail(
                plan,
                _convention_detail(convention_code="unsupported_convention"),
            ),
            "guidance_validator_convention_code_invalid",
            id="source=CONVENTION_TEMPLATES/code-whitelist",
        ),
        pytest.param(
            "user_confirmation evidence: generator _confirmation_detail_from_draft emits []",
            lambda plan: _with_extra_detail(
                plan,
                _confirmation_detail(evidence=[_evidence()]),
            ),
            "guidance_validator_confirmation_evidence",
            id="source=_confirmation_detail_from_draft/evidence-empty",
        ),
        pytest.param(
            "user_confirmation text: shared unsafe filter rejects numeric units/paths",
            lambda plan: _with_extra_detail(
                plan,
                _confirmation_detail(display_text="Confirm 7 kW at simulink/Unsafe/Path."),
            ),
            "guidance_validator_confirmation_unsafe",
            id="source=_unsafe_direction_hint/confirmation-display",
        ),
        pytest.param(
            "GuidanceGap basis: domain literal excludes document_extracted for gaps",
            lambda plan: _with_gap(
                plan,
                _gap(basis=cast(Any, "document_extracted")),
            ),
            "guidance_validator_gap_rule_invalid",
            id="source=GuidanceGap.basis/domain-legal-matrix",
        ),
        pytest.param(
            "GuidanceGap scope: plan gaps cannot carry step_id",
            lambda plan: _with_gap(plan, _gap(scope="plan", step_id="STEP-001")),
            "guidance_validator_gap_plan_step",
            id="source=gap-scope-structure/plan-step-none",
        ),
        pytest.param(
            "GuidanceGap scope: step/subsystem gaps require step_id",
            lambda plan: _with_gap(plan, _gap(scope="step", step_id=None)),
            "guidance_validator_gap_scoped_step_missing",
            id="source=gap-scope-structure/scoped-step-required",
        ),
        pytest.param(
            "GuidanceGap synthesis: shared GAP_SYNTHESIS_RULES table is authoritative",
            lambda plan: _with_gap(
                plan,
                _gap(gap_kind="toolbox_unverified", severity="blocking"),
            ),
            "guidance_validator_gap_rule_invalid",
            id="source=GAP_SYNTHESIS_RULES/signature-whitelist",
        ),
    ],
)
def test_semantic_validator_mutation_redlines(
    _source_note: str,
    mutate: Callable[[ModelGenerationPlan], ModelGenerationPlan],
    expected_code: str,
) -> None:
    # T2 source notes are carried in the parametrized case ids and _source_note values.
    plan = mutate(_generated_plan())

    validation = validate_build_guidance_semantics(_spec(), plan)

    assert validation.changed is True
    assert expected_code in _action_codes(validation.item_actions)


def test_semantic_validator_all_document_details_lost_is_generation_failed() -> None:
    # T2/P0-2 source: document grounding failures downgrade per item; if all document
    # details are lost, readback corruption is generation_failed, not no_document_basis.
    plan = _replace_first_detail(_generated_plan(), evidence=[])

    validation = validate_build_guidance_semantics(_spec(), plan)

    assert validation.plan.guidance_status == "generation_failed"
    assert validation.plan.build_guidance is None
    assert validation.whole_action == "mark_generation_failed"
    assert "guidance_validator_all_document_details_lost" in validation.machine_codes


def test_high_risk_terms_include_non_numeric_engineering_decisions() -> None:
    tokens = high_risk_claim_tokens(
        "Use SVPWM with anti-windup and 5 kW load.",
        _plan().build_steps[0],  # type: ignore[index]
    )

    assert "anti-windup" in tokens
    assert "svpwm" in [token.casefold() for token in tokens]
    assert "5 kW" in tokens


def test_gap_synthesis_excludes_pure_display_steps_and_keeps_connection_keys_distinct() -> None:
    plan = _plan(
        build_steps=[
            _display_step(),
            _connection_step(
                ConnectionHint("B1", None, "B2", None, None),
                ConnectionHint("B1", "out", "B2", "in", None),
            ),
        ]
    )
    pool = build_guidance_evidence_pool(_spec(), plan)
    truth = GroundingTruthIndex.from_spec_plan(_spec(), plan, pool)

    gaps = synthesize_guidance_gaps(
        build_steps=plan.build_steps or [],
        details=[],
        pool=pool,
        truth_index=truth,
    )

    assert all(gap.step_id != "STEP-DISPLAY" for gap in gaps)
    connection_gaps = [gap for gap in gaps if gap.gap_kind == "missing_connection_detail"]
    assert len(connection_gaps) == 2
    assert connection_gaps[0].display_text != connection_gaps[1].display_text


def test_guidance_lifecycle_view_states_and_terminal_clear() -> None:
    guidance = _build_guidance()
    generated = replace(_plan(), build_guidance=guidance, guidance_status="generated")
    stale_snapshot = replace(
        _plan(),
        build_guidance=guidance,
        guidance_status="stale_pending_regeneration",
    )
    stale_empty = replace(
        _plan(), build_guidance=None, guidance_status="stale_pending_regeneration"
    )
    failed = normalize_guidance_lifecycle(
        replace(_plan(), build_guidance=guidance, guidance_status="generation_failed")
    )
    no_basis = normalize_guidance_lifecycle(
        replace(_plan(), build_guidance=guidance, guidance_status="no_document_basis")
    )
    not_generated = normalize_guidance_lifecycle(
        replace(_plan(), build_guidance=guidance, guidance_status="not_generated")
    )

    assert guidance_view_state(generated) == "current"
    assert guidance_view_state(stale_snapshot) == "stale_with_snapshot"
    assert guidance_view_state(stale_empty) == "stale_empty"
    assert guidance_view_state(failed) == "failed_retryable"
    assert failed.build_guidance is None
    assert guidance_view_state(no_basis) == "no_basis"
    assert no_basis.build_guidance is None
    assert guidance_view_state(not_generated) == "not_generated"
    assert not_generated.build_guidance is None


def _generated_plan() -> ModelGenerationPlan:
    return replace(_plan(), build_guidance=_build_guidance(), guidance_status="generated")


def _replace_first_detail(plan: ModelGenerationPlan, **changes: Any) -> ModelGenerationPlan:
    assert plan.build_guidance is not None
    details = list(plan.build_guidance.details)
    details[0] = replace(details[0], **changes)
    return replace(plan, build_guidance=replace(plan.build_guidance, details=details))


def _with_extra_detail(plan: ModelGenerationPlan, detail: GuidanceDetail) -> ModelGenerationPlan:
    assert plan.build_guidance is not None
    return replace(
        plan,
        build_guidance=replace(
            plan.build_guidance,
            details=[*plan.build_guidance.details, detail],
        ),
    )


def _with_gap(plan: ModelGenerationPlan, gap: GuidanceGap) -> ModelGenerationPlan:
    assert plan.build_guidance is not None
    assessment = GuidanceAssessment(
        content_status="outline_with_gaps",
        environment_status="not_checked",
        overall_status="outline_with_gaps",
        blocking_gap_ids=[gap.gap_id] if gap.severity == "blocking" else [],
    )
    return replace(
        plan,
        build_guidance=replace(
            plan.build_guidance,
            assessment=assessment,
            gaps=[gap],
        ),
    )


def _convention_detail(
    *,
    evidence: list[PaperEvidenceEntry] | None = None,
    convention_code: str | None = "pi_controller_standard_structure",
) -> GuidanceDetail:
    return GuidanceDetail(
        detail_id="GD-900",
        step_id="STEP-001",
        detail_kind="subsystem_internal_structure",
        basis="engineering_convention",
        actionability="actionable",
        display_text="Use a standard PI structure for step STEP-001.",
        evidence=[] if evidence is None else evidence,
        convention_code=convention_code,
        confirmation_reason_code=None,
    )


def _confirmation_detail(
    *,
    evidence: list[PaperEvidenceEntry] | None = None,
    display_text: str = "Confirm the configuration detail for step STEP-001.",
) -> GuidanceDetail:
    return GuidanceDetail(
        detail_id="GD-901",
        step_id="STEP-001",
        detail_kind="configuration",
        basis="user_confirmation_required",
        actionability="blocked_pending_confirmation",
        display_text=display_text,
        evidence=[] if evidence is None else evidence,
        convention_code=None,
        confirmation_reason_code="configuration_unverified",
    )


def _gap(
    *,
    gap_kind: str = "insufficient_document_evidence",
    scope: str = "step",
    step_id: str | None = "STEP-001",
    basis: str = "user_confirmation_required",
    severity: str = "blocking",
) -> GuidanceGap:
    return GuidanceGap(
        gap_id="GAP-900",
        gap_kind=cast(Any, gap_kind),
        scope=cast(Any, scope),
        step_id=step_id,
        basis=cast(Any, basis),
        severity=cast(Any, severity),
        display_text="Step STEP-001 has a detail that requires confirmation before reproduction.",
    )


def _action_codes(actions: list[object]) -> set[str]:
    return {cast(Any, action).machine_code for action in actions}


def _spec() -> PaperSpec:
    return PaperSpec(
        paper_title="Load model report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A load model report.",
        equations=[],
        parameter_table=[
            ParameterEntry(
                name="Load power",
                symbol="PL",
                value="5",
                unit="kW",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id="DOC-001",
            )
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[_evidence()],
    )


def _plan(*, build_steps: list[ModelBuildStep] | None = None) -> ModelGenerationPlan:
    evidence = _evidence()
    return ModelGenerationPlan(
        plan_id="PLAN-1",
        paper_spec_id="paper-1",
        library_choice="SimPowerSystems",
        block_recommendations=[
            BlockRecommendation(
                block_type="Three-Phase Series RLC Load",
                purpose="Represent the 5kW load.",
                paper_reference=evidence,
            )
        ],
        parameter_mapping=[
            ParameterMapping(
                paper_param_name="PL",
                model_param_name="Load.P",
                value="5",
                unit="kW",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        subsystem_breakdown=["Place load", "Set parameter", "Observe output"],
        m_script_skeleton=None,
        evidence=[evidence],
        build_steps=build_steps if build_steps is not None else [_build_step()],
    )


def _plan_without_linked_evidence() -> ModelGenerationPlan:
    plan = _plan()
    step = _build_step(evidence=[], include_block_reference=False)
    return ModelGenerationPlan(
        plan_id=plan.plan_id,
        paper_spec_id=plan.paper_spec_id,
        library_choice=plan.library_choice,
        block_recommendations=plan.block_recommendations,
        parameter_mapping=[],
        subsystem_breakdown=plan.subsystem_breakdown,
        m_script_skeleton=None,
        evidence=plan.evidence,
        build_steps=[step],
    )


def _build_step(
    *,
    evidence: list[PaperEvidenceEntry] | None = None,
    block_reference: PaperEvidenceEntry | None = None,
    include_block_reference: bool = True,
) -> ModelBuildStep:
    resolved_block_reference = (
        block_reference
        if block_reference is not None
        else (_evidence() if include_block_reference else None)
    )
    return ModelBuildStep(
        step_id="STEP-001",
        title="Place load",
        intent="Represent the document load.",
        block_refs=[
            StepBlockRef(
                block_ref_id="B1",
                block_type="Three-Phase Series RLC Load",
                library_path=None,
                purpose="Represent the load.",
                paper_reference=resolved_block_reference,
            )
        ],
        parameter_refs=[ParameterMappingRef(paper_param_name="PL", model_param_name="Load.P")],
        connection_hints=[],
        configuration_hints=[],
        depends_on=[],
        evidence=[_evidence()] if evidence is None else evidence,
        display_text="Place the load block.",
    )


def _display_step() -> ModelBuildStep:
    return ModelBuildStep(
        step_id="STEP-DISPLAY",
        title="Display current",
        intent="Display the output signal.",
        block_refs=[
            StepBlockRef(
                block_ref_id="SCOPE",
                block_type="Scope",
                library_path="simulink/Sinks/Scope",
                purpose="Display simulation output.",
                paper_reference=None,
            )
        ],
        parameter_refs=[],
        connection_hints=[],
        configuration_hints=[],
        depends_on=[],
        evidence=[],
        display_text="Display simulation output.",
    )


def _connection_step(*connections: ConnectionHint) -> ModelBuildStep:
    return ModelBuildStep(
        step_id="STEP-CONNECT",
        title="Connect plant",
        intent="Connect two plant blocks.",
        block_refs=[
            StepBlockRef("B1", "Synchronous Machine", None, "Represent plant.", _evidence()),
            StepBlockRef("B2", "Three-Phase Fault", None, "Represent fault.", _evidence()),
        ],
        parameter_refs=[],
        connection_hints=list(connections),
        configuration_hints=[],
        depends_on=[],
        evidence=[_evidence()],
        display_text="Connect plant blocks.",
    )


def _build_guidance() -> BuildGuidance:
    return BuildGuidance(
        version="v1",
        assessment=GuidanceAssessment(
            content_status="outline_only",
            environment_status="not_checked",
            overall_status="outline_only",
            blocking_gap_ids=[],
        ),
        details=[
            GuidanceDetail(
                detail_id="GD-001",
                step_id="STEP-001",
                detail_kind="parameter_value",
                basis="document_extracted",
                actionability="actionable",
                display_text="Use the documented load power.",
                evidence=[_evidence()],
                convention_code=None,
                confirmation_reason_code=None,
            )
        ],
        gaps=[],
    )


def _evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report specifies a 5kW load for the model.",
        missing_param_prompt_id=None,
    )
