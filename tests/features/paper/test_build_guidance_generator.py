from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
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
    GuidanceTarget,
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
from features.paper.build_guidance_observability import termination_guard_for_retry_reason
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


class MetadataProvider(TextProvider):
    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "json_mode": json_mode,
                "timeout": timeout,
                "max_tokens": max_tokens,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


def _response(
    text: str,
    *,
    finish_reason: str | None,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> LLMResponse:
    return LLMResponse(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model="fake",
        latency_ms=1,
        finish_reason=finish_reason,
    )


@pytest.mark.asyncio
async def test_document_claim_requires_resolved_handle_and_grounding_normalizes_units() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "requirement_ref": "REQ-002",
                        "step_id": "STEP-001",
                        "detail_kind": "parameter_value",
                        "basis": "document_extracted",
                        "claim_text": "Use the 5 kW load from the paper.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "PL::Load.P",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "fixed", "value": "5", "unit": "kW"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
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
                        "requirement_ref": "REQ-002",
                        "step_id": "STEP-001",
                        "detail_kind": "parameter_value",
                        "basis": "document_extracted",
                        "claim_text": "Use the 5 kW load from the paper.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "PL::Load.P",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "fixed", "value": "5", "unit": "kW"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
                    },
                    {
                        "requirement_ref": "REQ-001",
                        "step_id": "STEP-001",
                        "detail_kind": "block_selection",
                        "basis": "document_extracted",
                        "claim_text": "Enable anti-windup for the controller.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "enum_selection", "selected": "Load"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
                    },
                ],
                "gaps": [],
            }
        ]
    )

    generator = BuildGuidanceGenerator(provider)
    updated = await generator.generate(_spec(), _plan())

    assert updated.guidance_status == "generated"
    assert updated.build_guidance is not None
    unverified = updated.build_guidance.details[1]
    assert unverified.basis == "document_claim_unverified"
    assert unverified.confirmation_reason_code == "document_evidence_unverified"
    assert "anti-windup" not in unverified.display_text.casefold()
    assert (
        "grounding_whitelist_no_match" in generator.last_telemetry.attempts[0].resolver_event_codes
    )


@pytest.mark.asyncio
async def test_raw_document_claim_with_unresolved_handle_never_becomes_no_basis() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "requirement_ref": "REQ-001",
                        "step_id": "STEP-001",
                        "detail_kind": "block_selection",
                        "basis": "document_extracted",
                        "claim_text": "Use the load block.",
                        "supporting_evidence_refs": ["GEV-999"],
                        "convention_code": None,
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "enum_selection", "selected": "Load"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
                    }
                ],
                "gaps": [],
            },
            {"details": [], "gaps": []},
        ]
    )

    generator = BuildGuidanceGenerator(provider)
    updated = await generator.generate(_spec(), _plan_without_linked_evidence())

    assert updated.guidance_status == "generation_failed"
    assert guidance_view_state(updated) == "failed_retryable"
    assert updated.build_guidance is None
    assert "handle_no_match" in generator.last_telemetry.attempts[0].resolver_event_codes


@pytest.mark.asyncio
async def test_raw_document_claim_with_grounding_failure_never_becomes_no_basis() -> None:
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "requirement_ref": "REQ-001",
                        "step_id": "STEP-001",
                        "detail_kind": "block_selection",
                        "basis": "document_extracted",
                        "claim_text": "Enable anti-windup for the controller.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "B1",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "enum_selection", "selected": "Load"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
                    }
                ],
                "gaps": [],
            },
            {"details": [], "gaps": []},
        ]
    )

    generator = BuildGuidanceGenerator(provider)
    updated = await generator.generate(_spec(), _plan())

    assert updated.guidance_status == "generation_failed"
    assert guidance_view_state(updated) == "failed_retryable"
    assert updated.build_guidance is None
    assert (
        "grounding_whitelist_no_match" in generator.last_telemetry.attempts[0].resolver_event_codes
    )


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
@pytest.mark.parametrize(
    ("finish_reason", "expected_reason"),
    [
        ("length", "llm_unparseable_finish_length"),
        ("stop", "llm_unparseable_finish_stop"),
        (None, "llm_unparseable_finish_unknown"),
    ],
)
async def test_llm_unparseable_reason_preserves_finish_reason_machine_code(
    finish_reason: str | None,
    expected_reason: str,
) -> None:
    provider = MetadataProvider(
        [
            _response("not json", finish_reason=finish_reason),
            _response("still not json", finish_reason=finish_reason),
        ]
    )
    generator = BuildGuidanceGenerator(provider)

    updated = await generator.generate(_spec(), _plan())

    assert updated.guidance_status == "generation_failed"
    assert generator.last_telemetry.terminal_reason == expected_reason
    assert {attempt.finish_reason for attempt in generator.last_telemetry.attempts} == {
        finish_reason
    }


@pytest.mark.asyncio
async def test_provider_telemetry_anomaly_marks_length_far_from_token_cap() -> None:
    provider = MetadataProvider(
        [
            _response("not json", finish_reason="length", completion_tokens=5),
            _response("still not json", finish_reason="length", completion_tokens=5),
        ]
    )
    generator = BuildGuidanceGenerator(provider, max_tokens=100)

    updated = await generator.generate(_spec(), _plan())

    assert updated.guidance_status == "generation_failed"
    assert generator.last_telemetry.terminal_reason == "llm_unparseable_finish_length"
    assert generator.last_telemetry.attempts[0].provider_telemetry_anomaly is True
    assert generator.last_telemetry.attempts[0].completion_ratio == 0.05


@pytest.mark.asyncio
async def test_attempt_telemetry_keeps_first_failure_when_retry_succeeds() -> None:
    provider = MetadataProvider(
        [
            _response("not json", finish_reason="stop"),
            _response(json.dumps(_valid_guidance_payload()), finish_reason="stop"),
        ]
    )
    generator = BuildGuidanceGenerator(provider)

    updated = await generator.generate(_spec(), _plan())

    assert updated.guidance_status == "generated"
    assert [attempt.parse_outcome for attempt in generator.last_telemetry.attempts] == [
        "json_error",
        "parsed",
    ]
    assert [attempt.attempt_index for attempt in generator.last_telemetry.attempts] == [1, 2]
    assert generator.last_telemetry.terminal_reason is None


@pytest.mark.asyncio
async def test_production_guidance_generator_does_not_write_guidance_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write_text(self: Path, *args: object, **kwargs: object) -> int:
        _ = self, args, kwargs
        raise AssertionError("production guidance path wrote model body")

    monkeypatch.setattr(Path, "write_text", fail_write_text)
    provider = MetadataProvider(
        [_response(json.dumps(_valid_guidance_payload()), finish_reason="stop")]
    )

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())

    assert updated.guidance_status == "generated"
    assert updated.build_guidance is not None


def test_termination_guard_distinguishes_wall_clock_and_hard_cap() -> None:
    assert (
        termination_guard_for_retry_reason("guidance_wall_clock_cap_exceeded")
        == "guidance_wall_clock"
    )
    assert termination_guard_for_retry_reason("guidance_call_cap_exceeded") == "hard_call_cap"


@pytest.mark.asyncio
async def test_semantic_validator_passes_generated_guidance_without_changes() -> None:
    provider = QueueProvider([_valid_guidance_payload()])

    updated = await BuildGuidanceGenerator(provider).generate(_spec(), _plan())
    validation = validate_build_guidance_semantics(_spec(), updated)

    assert updated.guidance_status == "generated"
    assert validation.plan == updated
    assert validation.changed is False
    assert validation.item_actions == []
    assert validation.machine_codes == []
    assert validation.whole_action == "keep"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        pytest.param(
            lambda plan: _replace_first_detail(plan, evidence=[]),
            "resolution_missing",
            id="document-evidence-required",
        ),
        pytest.param(
            lambda plan: _replace_first_detail(plan, actionability=cast(Any, "notice_only")),
            "guidance_validator_detail_normalized",
            id="actionability-derived",
        ),
        pytest.param(
            lambda plan: _with_extra_detail(
                plan,
                _domain_default_detail(evidence=[_evidence()]),
            ),
            "non_document_document_id_present",
            id="non-document-evidence-forbidden",
        ),
        pytest.param(
            lambda plan: _with_extra_detail(
                plan,
                _punt_detail(resolution={"kind": "fixed", "value": "5", "unit": "kW"}),
            ),
            "punt_from_exception_forbidden",
            id="punt-resolution-forbidden",
        ),
        pytest.param(
            lambda plan: _replace_first_detail(
                plan,
                resolution={"kind": "range", "lower": "1", "upper": "10"},
            ),
            "range_incomplete",
            id="range-start-required",
        ),
        pytest.param(
            lambda plan: _replace_first_detail(
                plan,
                target=None,
            ),
            "requirement_mismatch",
            id="target-required",
        ),
        pytest.param(
            lambda plan: _replace_first_detail(
                plan,
                input_fact_refs=["GD-001"],
            ),
            "input_fact_ref_cycle",
            id="input-ref-self-cycle",
        ),
    ],
)
def test_semantic_validator_mutation_redlines(
    mutate: Callable[[ModelGenerationPlan], ModelGenerationPlan],
    expected_code: str,
) -> None:
    plan = mutate(_generated_plan())

    validation = validate_build_guidance_semantics(_spec(), plan)

    assert validation.changed is True
    assert expected_code in _action_codes(validation.item_actions)


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        pytest.param("document_id", "non_document_document_id_present", id="document-id"),
        pytest.param("locator", "non_document_locator_present", id="locator"),
        pytest.param("excerpt", "non_document_excerpt_present", id="excerpt"),
        pytest.param("source", "non_document_evidence_present", id="source"),
    ],
)
def test_semantic_validator_distinguishes_non_document_evidence_fields(
    case: str,
    expected_code: str,
) -> None:
    evidence_by_case = {
        "document_id": [_evidence()],
        "locator": [replace(_evidence(), document_id=None, excerpt="")],
        "excerpt": [
            replace(
                _evidence(),
                document_id=None,
                paper_section_id=None,
                equation_id=None,
                figure_id=None,
            )
        ],
        "source": [
            replace(
                _evidence(),
                document_id=None,
                paper_section_id=None,
                equation_id=None,
                figure_id=None,
                excerpt="",
            )
        ],
    }
    evidence = evidence_by_case[case]
    plan = _with_extra_detail(_generated_plan(), _domain_default_detail(evidence=evidence))

    validation = validate_build_guidance_semantics(_spec(), plan)

    assert validation.changed is True
    assert expected_code in _action_codes(validation.item_actions)


def test_semantic_validator_rejects_input_fact_ref_cycle_between_details() -> None:
    base_step = _build_step()
    second_block = StepBlockRef(
        block_ref_id="B2",
        block_type="Scope",
        library_path=None,
        purpose="Observe the load signal.",
        paper_reference=None,
    )
    plan = replace(
        _generated_plan(),
        build_steps=[replace(base_step, block_refs=[*base_step.block_refs, second_block])],
    )
    first = _domain_default_detail(
        detail_id="GD-900",
        target=_block_target(),
        input_fact_refs=["GD-901"],
    )
    second = _domain_default_detail(
        detail_id="GD-901",
        target=GuidanceTarget(target_kind="block_choice", block_role_ref="B2"),
        input_fact_refs=["GD-900"],
    )

    validation = validate_build_guidance_semantics(
        _spec(),
        _with_extra_detail(_with_extra_detail(plan, first), second),
    )

    assert validation.changed is True
    assert "input_fact_ref_cycle" in _action_codes(validation.item_actions)


def test_reducer_duplicate_closing_detail_is_ambiguous_fail_closed() -> None:
    plan = _generated_plan()
    assert plan.build_guidance is not None
    duplicate = replace(plan.build_guidance.details[0], detail_id="GD-002")

    validation = validate_build_guidance_semantics(_spec(), _with_extra_detail(plan, duplicate))

    assert "duplicate_closing_detail" in validation.machine_codes
    assert validation.plan.build_guidance is not None
    assert any(
        gap.failure_code == "requirement_ambiguous" for gap in validation.plan.build_guidance.gaps
    )


@pytest.mark.asyncio
async def test_one_detail_covering_multiple_parameter_requirements_does_not_pass() -> None:
    step = replace(
        _build_step(),
        parameter_refs=[
            ParameterMappingRef(paper_param_name="PL", model_param_name="Load.P"),
            ParameterMappingRef(paper_param_name="QL", model_param_name="Load.Q"),
        ],
    )
    provider = QueueProvider(
        [
            {
                "details": [
                    {
                        "requirement_ref": "REQ-002",
                        "step_id": "STEP-001",
                        "detail_kind": "parameter_value",
                        "basis": "document_extracted",
                        "claim_text": "Set PL and QL to 5 kW.",
                        "supporting_evidence_refs": ["GEV-001"],
                        "convention_code": None,
                        "target": "PL::Load.P",
                        "confirmation_reason_code": None,
                        "direction_hint": None,
                        "resolution": {"kind": "fixed", "value": "5", "unit": "kW"},
                        "input_fact_refs": [],
                        "punt_reason_code": None,
                    }
                ],
                "gaps": [],
            },
            {"details": [], "gaps": []},
        ]
    )

    generator = BuildGuidanceGenerator(provider)
    updated = await generator.generate(_spec(), _plan(build_steps=[step]))

    assert updated.guidance_status == "generation_failed"
    assert "requirement_mismatch" in generator.last_telemetry.attempts[0].resolver_event_codes


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


def test_none_block_ref_paper_reference_stays_uncovered_and_out_of_document_pool() -> None:
    step = replace(
        _build_step(evidence=[], include_block_reference=False),
        parameter_refs=[],
    )
    plan = replace(_plan(build_steps=[step]), parameter_mapping=[])
    pool = build_guidance_evidence_pool(_spec(), plan)
    truth = GroundingTruthIndex.from_spec_plan(_spec(), plan, pool)

    gaps = synthesize_guidance_gaps(
        build_steps=plan.build_steps or [],
        details=[],
        pool=pool,
        truth_index=truth,
    )

    assert not any(card.linked_to_build_steps for card in pool.cards)
    assert any(
        gap.gap_kind == "missing_support_component" and gap.step_id == "STEP-001" for gap in gaps
    )


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


def _valid_guidance_payload() -> dict[str, object]:
    return {
        "details": [
            {
                "requirement_ref": "REQ-002",
                "step_id": "STEP-001",
                "detail_kind": "parameter_value",
                "basis": "document_extracted",
                "claim_text": "Use the 5 kW load from the paper.",
                "supporting_evidence_refs": ["GEV-001"],
                "convention_code": None,
                "target": "PL::Load.P",
                "confirmation_reason_code": None,
                "direction_hint": None,
                "resolution": {"kind": "fixed", "value": "5", "unit": "kW"},
                "input_fact_refs": [],
                "punt_reason_code": None,
            }
        ],
        "gaps": [],
    }


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


def _parameter_target() -> GuidanceTarget:
    return GuidanceTarget(
        target_kind="parameter",
        model_param="Load.P",
        paper_param="PL",
    )


def _block_target() -> GuidanceTarget:
    return GuidanceTarget(target_kind="block_choice", block_role_ref="B1")


def _domain_default_detail(
    *,
    evidence: list[PaperEvidenceEntry] | None = None,
    detail_id: str = "GD-900",
    target: GuidanceTarget | None = None,
    input_fact_refs: list[str] | None = None,
) -> GuidanceDetail:
    resolved_target = _block_target() if target is None else target
    return GuidanceDetail(
        detail_id=detail_id,
        step_id="STEP-001",
        detail_kind="block_selection",
        basis="domain_default",
        actionability="actionable",
        display_text="领域默认（非论文）：模块角色 B1；选择 Load。",
        evidence=[] if evidence is None else evidence,
        convention_code=None,
        confirmation_reason_code=None,
        target=resolved_target,
        obligation_kind="select_component",
        resolution={"kind": "enum_selection", "selected": "Load"},
        execution_closure="closed",
        input_fact_refs=[] if input_fact_refs is None else input_fact_refs,
        punt_reason_code=None,
    )


def _punt_detail(
    *,
    evidence: list[PaperEvidenceEntry] | None = None,
    resolution: dict[str, Any] | None = None,
) -> GuidanceDetail:
    return GuidanceDetail(
        detail_id="GD-901",
        step_id="STEP-001",
        detail_kind="block_selection",
        basis="user_confirmation_required",
        actionability="blocked_pending_confirmation",
        display_text="暂无法确定：模块角色 B1；原因：source_does_not_specify。",
        evidence=[] if evidence is None else evidence,
        convention_code=None,
        confirmation_reason_code=None,
        target=_block_target(),
        obligation_kind="select_component",
        resolution=resolution,
        execution_closure="open",
        input_fact_refs=[],
        punt_reason_code="source_does_not_specify",
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
        version="v2",
        assessment=GuidanceAssessment(
            content_status="outline_with_gaps",
            environment_status="not_checked",
            overall_status="outline_with_gaps",
            blocking_gap_ids=["GAP-001"],
            open_requirement_count=1,
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
                target=_parameter_target(),
                obligation_kind="determine_parameter_value",
                resolution={"kind": "fixed", "value": "5", "unit": "kW"},
                execution_closure="closed",
                input_fact_refs=[],
                punt_reason_code=None,
            )
        ],
        gaps=[
            GuidanceGap(
                gap_id="GAP-001",
                gap_kind="missing_support_component",
                scope="step",
                step_id="STEP-001",
                basis="user_confirmation_required",
                severity="blocking",
                display_text="需要选择模块角色 B1 对应的可用模块。",
                target=_block_target(),
                obligation_kind="select_component",
                execution_closure="open",
                failure_code="does_not_close_gap",
            )
        ],
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
