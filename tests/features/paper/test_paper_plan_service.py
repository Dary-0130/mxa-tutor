from __future__ import annotations

import asyncio
import copy
import inspect
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

import features.paper.paper_plan_service as service_module
from core.domain.exceptions import (
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    PaperPlanGenerationError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_conflicts import with_parameter_conflicts
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterEntry,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    BuildStepsDtoValidationError,
    BuildStepsJsonParseError,
    BuildStepsStructuredError,
    EvidenceTagger,
    MissingBindingModel,
    ModelBuildStepDraft,
    UserEvidenceRef,
)
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_schemas import ModelGenerationPlanModel, StepBlockRefModel
from features.paper.structured_retry import (
    REASON_CALL_CAP_EXCEEDED,
    StructuredRetryContext,
)


class NoopTextProvider(TextProvider):
    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = messages, json_mode, timeout, max_tokens
        return LLMResponse(
            text="{}", prompt_tokens=0, completion_tokens=0, model="fake", latency_ms=0
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


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


class PayloadPaperPlanService(PaperPlanService):
    def __init__(
        self,
        payloads: dict[str, dict[str, Any] | BaseException],
        evidence_tagger: EvidenceTagger | None = None,
    ) -> None:
        super().__init__(NoopTextProvider(), evidence_tagger=evidence_tagger)
        self.payloads = payloads
        self.calls: list[str] = []

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        _ = messages
        self.calls.append(role_name)
        payload = self.payloads[role_name]
        if isinstance(payload, BaseException):
            raise payload
        return copy.deepcopy(payload)


class SequencedPayloadPaperPlanService(PaperPlanService):
    def __init__(
        self,
        payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException],
    ) -> None:
        super().__init__(NoopTextProvider())
        self.payloads = payloads
        self.calls: list[str] = []

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        _ = messages
        self.calls.append(role_name)
        payload = self.payloads[role_name]
        item = payload.pop(0) if isinstance(payload, list) else payload
        if isinstance(item, BaseException):
            raise item
        return copy.deepcopy(item)


class CountingPayloadPaperPlanService(SequencedPayloadPaperPlanService):
    def __init__(
        self,
        payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException],
    ) -> None:
        super().__init__(payloads)
        self.guidance_calls = 0

    async def _generate_build_guidance(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        _ = spec
        self.guidance_calls += 1
        return plan


class RecordingEvidenceTagger(EvidenceTagger):
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[list[PaperEvidenceEntry]] = []

    def validate_for_spec(
        self,
        evidence: list[PaperEvidenceEntry],
        spec: PaperSpec,
    ) -> None:
        _ = spec
        self.calls.append(evidence)
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise PaperPlanGenerationError("forced_evidence_failure")


def test_build_steps_structured_error_is_independent_from_generation_error() -> None:
    assert not issubclass(BuildStepsStructuredError, PaperPlanGenerationError)


@pytest.mark.asyncio
async def test_generate_happy_path_returns_plan_missing_bindings() -> None:
    service = PayloadPaperPlanService(_payloads())

    plan, missing_prompts, missing_bindings = await service.generate(_spec(), "PAPER-001")

    assert service.calls == [
        "plan_composer",
        "mscript_drafter",
        "missing_detector",
        "build_step_planner",
    ]
    assert plan.plan_id == "PLAN-PAPER-001"
    assert plan.paper_spec_id == "PAPER-001"
    assert plan.build_steps is not None
    assert plan.build_guidance is None
    assert len(plan.build_steps) == 3
    assert plan.subsystem_breakdown == [step.display_text for step in plan.build_steps]
    assert (
        plan.m_script_skeleton
        == "clear; clc;\n% 参数区\nfigure; subplot(1,1,1); title('短路电流');"
    )
    assert [prompt.prompt_id for prompt in missing_prompts] == ["MISS-001"]
    assert missing_bindings == [
        MissingBindingModel(
            prompt_id="MISS-001",
            paper_param_name="H",
            model_param_name="Synchronous Machine.H",
        )
    ]


@pytest.mark.asyncio
async def test_build_step_planner_accepts_omitted_block_ref_paper_reference_without_fallback() -> (
    None
):
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][0]["block_refs"][0].pop("paper_reference")
    service = PayloadPaperPlanService(payloads)

    plan, _, _ = await service.generate(_spec(), "PAPER-001")

    assert plan.build_steps is not None
    assert plan.build_steps[0].block_refs[0].paper_reference is None
    assert "subsystem_planner" not in service.calls
    public_payload = ModelGenerationPlanModel.from_domain(plan).model_dump(mode="json")
    block_ref_payload = public_payload["build_steps"][0]["block_refs"][0]
    assert "paper_reference" in block_ref_payload
    assert block_ref_payload["paper_reference"] is None


def test_omitted_and_explicit_null_block_ref_paper_reference_are_equivalent() -> None:
    omitted_payload = _build_steps_payload()
    omitted_payload["build_steps"][0]["block_refs"][0].pop("paper_reference")
    null_payload = _build_steps_payload()
    null_payload["build_steps"][0]["block_refs"][0]["paper_reference"] = None

    omitted_drafts = _drafts_from_build_steps_payload(omitted_payload)
    null_drafts = _drafts_from_build_steps_payload(null_payload)

    assert omitted_drafts == null_drafts


def test_build_step_block_ref_draft_accepts_legal_paper_reference() -> None:
    drafts = _drafts_from_build_steps_payload(_build_steps_payload())

    assert drafts[0].block_refs[0].paper_reference == _document_evidence()


@pytest.mark.parametrize(
    "case_name",
    [
        "invalid_paper_reference_shape",
        "missing_required_field",
        "extra_field",
    ],
)
def test_block_ref_draft_rejects_invalid_payloads_fail_red(case_name: str) -> None:
    payload = _build_steps_payload()
    block_ref = payload["build_steps"][0]["block_refs"][0]
    if case_name == "invalid_paper_reference_shape":
        block_ref["paper_reference"] = _document_evidence_payload()
    elif case_name == "missing_required_field":
        block_ref.pop("block_type")
    elif case_name == "extra_field":
        block_ref["unexpected_field"] = "forbidden"

    with pytest.raises((ValidationError, BuildStepsDtoValidationError)):
        _drafts_from_build_steps_payload(payload)


def test_block_ref_draft_keeps_public_field_set_aligned() -> None:
    draft_fields = service_module._StepBlockRefDraftModel.model_fields
    public_fields = StepBlockRefModel.model_fields

    assert tuple(draft_fields) == tuple(public_fields)
    assert draft_fields["paper_reference"].default is None
    assert public_fields["paper_reference"].is_required()
    for field_name in public_fields:
        if field_name == "paper_reference":
            continue
        assert draft_fields[field_name].annotation == public_fields[field_name].annotation
        assert draft_fields[field_name].is_required() == public_fields[field_name].is_required()


@pytest.mark.asyncio
async def test_omitted_block_ref_paper_reference_logs_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_info(*args: object, **kwargs: object) -> None:
        info_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "info", fake_info)
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][0]["block_refs"][0].pop("paper_reference")

    await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    build_step_info_calls = [
        call
        for call in info_calls
        if call[0][0]
        == "paper_plan_build_steps_draft_default_applied role=%s stage=%s field_path=%s "
        "reason_code=%s count=%s"
    ]
    assert build_step_info_calls == [
        (
            (
                "paper_plan_build_steps_draft_default_applied role=%s stage=%s field_path=%s "
                "reason_code=%s count=%s",
                "build_step_planner",
                "llm_draft",
                "build_steps.block_refs.paper_reference",
                "omitted_paper_reference",
                1,
            ),
            {},
        )
    ]
    logged = repr(info_calls)
    assert "The report states the machine parameter." not in logged
    assert "source_ref" not in logged
    assert "paper_reference" in logged


@pytest.mark.asyncio
async def test_build_step_draft_evidence_resolves_three_entry_points_from_source_ref() -> None:
    service = PayloadPaperPlanService({"build_step_planner": _build_steps_payload()})

    drafts = await service._llm_build_steps(
        [_block_recommendation()],
        [_sentinel_mapping()],
        _spec(),
    )

    assert drafts[0].block_refs[0].paper_reference == _document_evidence()
    assert drafts[0].evidence == [_document_evidence()]
    assert drafts[2].configuration_hints[0].evidence == [_document_evidence()]


@pytest.mark.parametrize(
    ("draft_evidence", "reason_code"),
    [
        ({}, "source_ref_missing"),
        ({"source_ref": None}, "source_ref_missing"),
        ({"source_ref": ""}, "source_ref_missing"),
        ({"source_ref": 1}, "source_ref_type_invalid"),
        ({"source_ref": "REF-999"}, "source_ref_no_match"),
        (
            {"source_ref": "REF-001", "document_id": "DOC-001"},
            "draft_schema_invalid",
        ),
    ],
)
@pytest.mark.asyncio
async def test_build_step_draft_evidence_fail_closed_with_machine_codes(
    draft_evidence: dict[str, Any],
    reason_code: str,
) -> None:
    payload = _build_steps_payload()
    payload["build_steps"][0]["evidence"][0] = draft_evidence
    service = PayloadPaperPlanService({"build_step_planner": payload})

    with pytest.raises(BuildStepsDtoValidationError) as exc_info:
        await service._llm_build_steps(
            [_block_recommendation()],
            [_sentinel_mapping()],
            _spec(),
        )

    assert exc_info.value.reason_code == reason_code


@pytest.mark.asyncio
async def test_build_step_draft_evidence_ambiguous_source_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refs = service_module.build_plan_evidence_source_refs(_spec())
    monkeypatch.setattr(
        service_module,
        "build_plan_evidence_source_refs",
        lambda spec: [refs[0], refs[0]],
    )
    service = PayloadPaperPlanService({"build_step_planner": _build_steps_payload()})

    with pytest.raises(BuildStepsDtoValidationError) as exc_info:
        await service._llm_build_steps(
            [_block_recommendation()],
            [_sentinel_mapping()],
            _spec(),
        )

    assert exc_info.value.reason_code == "source_ref_ambiguous"


@pytest.mark.asyncio
async def test_build_step_bridge_final_evidence_invalid_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service_module,
        "build_plan_evidence_source_refs",
        lambda spec: [
            service_module.PlanEvidenceSourceRef(
                source_ref="REF-001",
                document_id="",
                locator_kind="paper_section_id",
                locator_id="S1",
                filename="paper.pdf",
                excerpt="The report states the machine parameter.",
            )
        ],
    )
    service = PayloadPaperPlanService({"build_step_planner": _build_steps_payload()})

    with pytest.raises(BuildStepsDtoValidationError) as exc_info:
        await service._llm_build_steps(
            [_block_recommendation()],
            [_sentinel_mapping()],
            _spec(),
        )

    assert exc_info.value.reason_code == "final_evidence_invalid"


def test_build_step_public_dto_rejects_source_ref_leak() -> None:
    payload = service_module._resolve_build_steps_draft_evidence_payload(
        _build_steps_payload(),
        document_source_refs=service_module.build_plan_evidence_source_refs(_spec()),
        user_source_refs=[],
    )
    payload["build_steps"][0]["evidence"][0]["source_ref"] = "REF-001"

    with pytest.raises(ValidationError) as exc_info:
        service_module._BuildStepsOutputModel.model_validate(payload)

    assert service_module._build_steps_final_validation_reason(exc_info.value) == (
        "source_ref_leaked"
    )


@pytest.mark.asyncio
async def test_build_step_to_block_ref_non_string_fails_dto_validation() -> None:
    payload = _build_steps_payload()
    payload["build_steps"][2]["connection_hints"] = [
        {
            "from_block_ref": "B1",
            "from_port": None,
            "to_block_ref": 1,
            "to_port": None,
            "signal_meaning": "machine signal",
        }
    ]
    service = PayloadPaperPlanService({"build_step_planner": payload})

    with pytest.raises(BuildStepsDtoValidationError) as exc_info:
        await service._llm_build_steps(
            [_block_recommendation()],
            [_sentinel_mapping()],
            _spec(),
        )

    assert exc_info.value.reason_code == "dto_invalid"


@pytest.mark.asyncio
async def test_regenerate_build_steps_resolves_user_supplied_source_ref() -> None:
    user_evidence = _user_evidence()
    payload = _build_steps_payload()
    payload["build_steps"][1]["evidence"][0] = {"source_ref": "USER-001"}
    payload["build_steps"][2]["configuration_hints"][0]["evidence"][0] = {"source_ref": "USER-001"}
    service = PayloadPaperPlanService({"build_step_regenerator": payload})

    drafts = await service._llm_build_steps_for_regeneration(
        [_block_recommendation()],
        [_sentinel_mapping()],
        _spec(),
        [_document_evidence(), user_evidence],
        {UserEvidenceRef(kind=UserEvidenceAction.FILL_MISSING, key="MISS-1")},
        frozenset({"MISS-1"}),
    )

    assert drafts[1].evidence == [user_evidence]
    assert drafts[2].configuration_hints[0].evidence == [user_evidence]


@pytest.mark.asyncio
async def test_two_llm_calls_run_concurrently_in_each_dag_phase() -> None:
    class ConcurrentService(PaperPlanService):
        def __init__(self) -> None:
            super().__init__(NoopTextProvider())
            self.active = 0
            self.max_active = 0

        async def _parallel(self, result: object) -> object:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return result

        async def _llm_missing_detect(
            self,
            spec: PaperSpec,
            paper_id: str,
            sentinel_mappings: list[ParameterMapping],
        ) -> list[MissingParameterPrompt]:
            _ = spec, paper_id, sentinel_mappings
            return await self._parallel([])  # type: ignore[return-value]

        async def _llm_plan_compose(
            self,
            spec: PaperSpec,
            plan_id: str,
            paper_spec_id: str,
        ) -> ModelGenerationPlan:
            _ = spec, plan_id, paper_spec_id
            return await self._parallel(_plan_domain(missing=False))  # type: ignore[return-value]

        async def _llm_mscript_draft(self, spec: PaperSpec) -> str | None:
            _ = spec
            return await self._parallel(None)  # type: ignore[return-value]

        async def _llm_build_steps(
            self,
            block_recommendations: list[BlockRecommendation],
            parameter_mapping: list[ParameterMapping],
            spec: PaperSpec,
        ) -> list[ModelBuildStepDraft]:
            _ = block_recommendations, parameter_mapping, spec
            return await self._parallel(_build_step_drafts())  # type: ignore[return-value]

    service = ConcurrentService()

    await service.generate(_spec(), "PAPER-001")

    assert service.max_active == 2


@pytest.mark.asyncio
async def test_step2_build_step_planner_awaits_plan_composer_block_recommendations() -> None:
    class OrderedService(PaperPlanService):
        def __init__(self) -> None:
            super().__init__(NoopTextProvider())
            self.plan_done = False

        async def _llm_missing_detect(
            self,
            spec: PaperSpec,
            paper_id: str,
            sentinel_mappings: list[ParameterMapping],
        ) -> list[MissingParameterPrompt]:
            _ = spec, paper_id, sentinel_mappings
            return []

        async def _llm_plan_compose(
            self,
            spec: PaperSpec,
            plan_id: str,
            paper_spec_id: str,
        ) -> ModelGenerationPlan:
            _ = spec, plan_id, paper_spec_id
            await asyncio.sleep(0.01)
            self.plan_done = True
            return _plan_domain(missing=False)

        async def _llm_mscript_draft(self, spec: PaperSpec) -> str | None:
            _ = spec
            return None

        async def _llm_build_steps(
            self,
            block_recommendations: list[BlockRecommendation],
            parameter_mapping: list[ParameterMapping],
            spec: PaperSpec,
        ) -> list[ModelBuildStepDraft]:
            _ = parameter_mapping, spec
            assert self.plan_done
            assert block_recommendations[0].block_type == "Synchronous Machine"
            return _build_step_drafts()

    await OrderedService().generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_plan_composer_structured_retry_reruns_leaf_and_preserves_mscript() -> None:
    payloads: dict[str, list[dict[str, Any] | Exception] | dict[str, Any] | Exception] = _payloads()
    payloads["plan_composer"] = [
        PaperPlanGenerationError(
            "validation_failed",
            reason_code="schema_validation",
            finish_reason="stop",
            leaf="plan_composer",
            loc=("library_choice",),
        ),
        _plan_payload(),
    ]
    service = SequencedPayloadPaperPlanService(payloads)
    context = StructuredRetryContext()

    plan, _, _ = await service.generate(_spec(), "PAPER-001", retry_context=context)

    assert plan.plan_id == "PLAN-PAPER-001"
    assert service.calls == [
        "plan_composer",
        "mscript_drafter",
        "plan_composer",
        "missing_detector",
        "build_step_planner",
    ]
    assert context.rescued_leaves == {"plan_composer"}


@pytest.mark.asyncio
async def test_plan_composer_failure_still_aborts_before_build_steps_and_guidance() -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["plan_composer"] = [
        PaperPlanGenerationError(
            "validation_failed",
            reason_code="schema_validation",
            finish_reason="length",
            leaf="plan_composer",
            loc=("library_choice",),
        )
    ]
    service = CountingPayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service.generate(_spec(), "PAPER-001", retry_context=StructuredRetryContext())

    assert exc_info.value.leaf == "plan_composer"
    assert exc_info.value.reason_code == "schema_validation"
    assert "build_step_planner" not in service.calls
    assert service.guidance_calls == 0


@pytest.mark.asyncio
async def test_plan_composer_failure_remains_primary_when_mscript_also_degrades() -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["plan_composer"] = [
        PaperPlanGenerationError(
            "validation_failed",
            reason_code="schema_validation",
            finish_reason="length",
            leaf="plan_composer",
            loc=("library_choice",),
        )
    ]
    payloads["mscript_drafter"] = [RuntimeError("SECRET_MSCRIPT")]
    service = CountingPayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service.generate(_spec(), "PAPER-001", retry_context=StructuredRetryContext())

    assert exc_info.value.leaf == "plan_composer"
    assert exc_info.value.reason_code == "schema_validation"
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.outcome == "degraded"
    assert outcome.degradation_code == "internal-error"
    assert "build_step_planner" not in service.calls
    assert service.guidance_calls == 0


@pytest.mark.asyncio
async def test_build_steps_failure_remains_primary_after_mscript_degradation() -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = [RuntimeError("SECRET_MSCRIPT")]
    payloads["build_step_planner"] = [
        PaperPlanGenerationError(
            "role=build_step_planner: original_failure",
            reason_code="build_steps_original",
            leaf="build_step_planner",
        )
    ]
    service = CountingPayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service.generate(_spec(), "PAPER-001")

    assert exc_info.value.reason_code == "build_steps_original"
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.degradation_code == "internal-error"
    assert service.guidance_calls == 0


@pytest.mark.asyncio
async def test_missing_detector_structured_retry_preserves_build_steps_result() -> None:
    payloads: dict[str, list[dict[str, Any] | Exception] | dict[str, Any] | Exception] = _payloads()
    payloads["missing_detector"] = [
        PaperPlanGenerationError(
            "validation_failed",
            reason_code="schema_validation",
            finish_reason="stop",
            leaf="missing_detector",
            loc=("missing_prompts",),
        ),
        {"missing_prompts": [_missing_prompt_payload()]},
    ]
    service = SequencedPayloadPaperPlanService(payloads)
    context = StructuredRetryContext()

    plan, missing_prompts, _ = await service.generate(
        _spec(),
        "PAPER-001",
        retry_context=context,
    )

    assert plan.build_steps is not None
    assert [prompt.prompt_id for prompt in missing_prompts] == ["MISS-001"]
    assert service.calls == [
        "plan_composer",
        "mscript_drafter",
        "missing_detector",
        "build_step_planner",
        "missing_detector",
    ]
    assert context.rescued_leaves == {"missing_detector"}


@pytest.mark.asyncio
async def test_length_finish_reason_does_not_use_outer_structured_retry() -> None:
    payloads: dict[str, list[dict[str, Any] | Exception] | dict[str, Any] | Exception] = _payloads()
    payloads["plan_composer"] = [
        PaperPlanGenerationError(
            "validation_failed",
            reason_code="schema_validation",
            finish_reason="length",
            leaf="plan_composer",
            loc=("library_choice",),
        ),
        _plan_payload(),
    ]
    service = SequencedPayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service.generate(_spec(), "PAPER-001", retry_context=StructuredRetryContext())

    assert exc_info.value.finish_reason == "length"
    assert service.calls == ["plan_composer", "mscript_drafter"]


@pytest.mark.asyncio
async def test_all_role_helpers_use_call_llm_json(monkeypatch: pytest.MonkeyPatch) -> None:
    service = PaperPlanService(NoopTextProvider())
    calls: list[str] = []

    async def fake_call(messages: list[LLMMessage], role_name: str) -> dict[str, Any]:
        _ = messages
        calls.append(role_name)
        return copy.deepcopy(_payloads()[role_name])

    monkeypatch.setattr(service, "_call_llm_json", fake_call)

    await service._llm_missing_detect(_spec(), "PAPER-001", [_sentinel_mapping()])
    await service._llm_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")
    await service._llm_subsystem_plan([_block_recommendation()], [_document_evidence()])
    await service._llm_build_steps(
        [_block_recommendation()],
        [_sentinel_mapping()],
        _spec(),
    )
    await service._llm_mscript_draft(_spec())

    assert calls == [
        "missing_detector",
        "plan_composer",
        "subsystem_planner",
        "build_step_planner",
        "mscript_drafter",
    ]


@pytest.mark.asyncio
async def test_regeneration_role_helpers_use_call_llm_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = PaperPlanService(NoopTextProvider())
    calls: list[str] = []

    async def fake_call(messages: list[LLMMessage], role_name: str) -> dict[str, Any]:
        _ = messages
        calls.append(role_name)
        payloads = _payloads()
        if role_name == "build_step_regenerator":
            return copy.deepcopy(payloads["build_step_planner"])
        if role_name == "mscript_drafter_from_mapping":
            return copy.deepcopy(payloads["mscript_drafter"])
        raise AssertionError(f"unexpected role {role_name}")

    monkeypatch.setattr(service, "_call_llm_json", fake_call)

    await service._llm_build_steps_for_regeneration(
        [_block_recommendation()],
        [_sentinel_mapping()],
        _spec(),
        [_document_evidence()],
        set(),
        frozenset(),
    )
    await service._llm_mscript_draft_from_mapping([_sentinel_mapping()], _spec())

    assert calls == ["build_step_regenerator", "mscript_drafter_from_mapping"]


@pytest.mark.asyncio
async def test_call_llm_json_bridges_via_asyncio_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = QueueTextProvider([json.dumps({"ok": True})])
    service = PaperPlanService(provider, timeout=12.0, max_tokens=34)
    calls: list[tuple[Callable[..., object], tuple[object, ...], dict[str, object]]] = []

    async def fake_to_thread(
        function: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr(service_module.asyncio, "to_thread", fake_to_thread)

    data = await service._call_llm_json([LLMMessage("system", "x")], "test_role")

    assert data == {"ok": True}
    assert calls[0][0] == provider.chat
    assert calls[0][2] == {"json_mode": True, "timeout": 12.0, "max_tokens": 34}


def test_only_one_asyncio_to_thread_in_service() -> None:
    source = inspect.getsource(service_module.PaperPlanService)

    assert source.count("asyncio.to_thread") == 1
    assert "self._text_provider.chat(" not in source


@pytest.mark.asyncio
async def test_plan_id_uses_python_injection_format() -> None:
    plan, _, _ = await PayloadPaperPlanService(_payloads()).generate(_spec(), "PAPER-001")

    assert plan.plan_id == "PLAN-PAPER-001"


@pytest.mark.asyncio
async def test_paper_spec_id_equals_paper_id() -> None:
    plan, _, _ = await PayloadPaperPlanService(_payloads()).generate(_spec(), "PAPER-001")

    assert plan.paper_spec_id == "PAPER-001"


@pytest.mark.asyncio
async def test_llm_returned_plan_id_is_overridden_by_python_injection() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["plan_id"] = "PLAN-PLACEHOLDER"
    payloads["plan_composer"]["paper_spec_id"] = "PAPER-PLACEHOLDER"

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.plan_id == "PLAN-PAPER-001"
    assert plan.paper_spec_id == "PAPER-001"


@pytest.mark.asyncio
async def test_plan_composer_strips_private_source_ref_after_stamping_document() -> None:
    plan = await PayloadPaperPlanService(_payloads())._llm_plan_compose(
        _spec(), "PLAN-PAPER-001", "PAPER-001"
    )

    assert plan.evidence[0].document_id == "DOC-001"
    assert plan.evidence[0].paper_section_id == "S1"
    assert not hasattr(plan.evidence[0], "source_ref")


@pytest.mark.asyncio
async def test_missing_detector_rejects_paper_reference_not_document_extracted() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["paper_reference"] = _user_evidence_payload()
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service._llm_missing_detect(_spec(), "PAPER-001", [_sentinel_mapping()])

    assert exc_info.value.reason_code == "paper_reference_must_be_document_extracted"


@pytest.mark.asyncio
async def test_missing_detector_rejects_figure_id_not_in_spec_whitelist() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["paper_reference"]["source_ref"] = "REF-999"
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service._llm_missing_detect(_spec(), "PAPER-001", [_sentinel_mapping()])

    assert exc_info.value.reason_code == "schema_validation"


@pytest.mark.asyncio
async def test_missing_detector_rejects_source_not_user_supplied() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["source"] = "document_extracted"
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service._llm_missing_detect(_spec(), "PAPER-001", [_sentinel_mapping()])

    assert exc_info.value.reason_code == "schema_validation"


@pytest.mark.asyncio
async def test_missing_detector_rejects_llm_prompt_id_output() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["prompt_id"] = "MISS-LLM"

    with pytest.raises(PaperPlanGenerationError, match="validation_failed") as exc_info:
        await PayloadPaperPlanService(payloads)._llm_missing_detect(
            _spec(),
            "PAPER-001",
            [_sentinel_mapping()],
        )

    assert exc_info.value.reason_code == "schema_validation"


@pytest.mark.asyncio
async def test_missing_detector_rejects_parameter_name_mismatch() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["parameter_name"] = "H"
    sentinel = ParameterMapping(
        paper_param_name="H 惯性时间常数",
        model_param_name="Synchronous Machine.H",
        value=MISSING_VALUE_SENTINEL,
        unit="s",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )

    with pytest.raises(
        PaperPlanGenerationError,
        match="missing_prompt_parameter_mismatch",
    ) as exc_info:
        await PayloadPaperPlanService(payloads)._llm_missing_detect(
            _spec(),
            "PAPER-001",
            [sentinel],
        )

    assert exc_info.value.reason_code == "missing_prompt_parameter_mismatch"


@pytest.mark.asyncio
async def test_missing_detector_rejects_cardinality_mismatch() -> None:
    with pytest.raises(
        PaperPlanGenerationError,
        match="missing_prompt_cardinality_mismatch",
    ) as exc_info:
        await PayloadPaperPlanService(_payloads())._llm_missing_detect(_spec(), "PAPER-001", [])

    assert exc_info.value.reason_code == "missing_prompt_cardinality_mismatch"


@pytest.mark.asyncio
async def test_plan_composer_rejects_duplicate_paper_param_name() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"].append(
        {
            "paper_param_name": "H",
            "model_param_name": "Synchronous Machine.H duplicate",
            "value": "3.5",
            "unit": "s",
            "source": "document_extracted",
        }
    )

    with pytest.raises(PaperPlanGenerationError, match="paper_param_name_duplicate") as exc_info:
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )

    assert exc_info.value.reason_code == "paper_param_name_duplicate"


@pytest.mark.asyncio
async def test_plan_composer_rejects_sentinel_user_supplied_source() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"][0]["source"] = "user_supplied"

    with pytest.raises(PaperPlanGenerationError, match="sentinel_source_must_be_document"):
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )


@pytest.mark.asyncio
async def test_plan_composer_rejects_subsystem_breakdown_not_empty() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["subsystem_breakdown"] = ["第 1 步:错误"]

    with pytest.raises(PaperPlanGenerationError, match="subsystem_breakdown_must_be_empty"):
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )


@pytest.mark.asyncio
async def test_plan_composer_rejects_m_script_skeleton_not_none() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["m_script_skeleton"] = "clear; clc;"

    with pytest.raises(PaperPlanGenerationError, match="m_script_skeleton_must_be_null"):
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )


@pytest.mark.asyncio
async def test_plan_composer_value_must_be_string_not_none() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"][0]["value"] = None

    with pytest.raises(PaperPlanGenerationError, match="validation_failed") as exc_info:
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )

    assert exc_info.value.reason_code == "schema_validation"


@pytest.mark.asyncio
async def test_subsystem_planner_rejects_fewer_than_3_steps() -> None:
    payloads = _payloads()
    payloads["subsystem_planner"]["subsystem_breakdown"] = ["第 1 步:放置电机", "第 2 步:接线"]

    with pytest.raises(PaperPlanGenerationError, match="subsystem_breakdown_length_invalid"):
        await PayloadPaperPlanService(payloads)._llm_subsystem_plan(
            [_block_recommendation()], [_document_evidence()]
        )


@pytest.mark.asyncio
async def test_subsystem_planner_rejects_more_than_10_steps() -> None:
    payloads = _payloads()
    payloads["subsystem_planner"]["subsystem_breakdown"] = [
        f"第 {index} 步:搭建" for index in range(1, 12)
    ]

    with pytest.raises(PaperPlanGenerationError, match="subsystem_breakdown_length_invalid"):
        await PayloadPaperPlanService(payloads)._llm_subsystem_plan(
            [_block_recommendation()], [_document_evidence()]
        )


@pytest.mark.asyncio
async def test_mscript_drafter_allows_null_output() -> None:
    payloads = _payloads()
    payloads["mscript_drafter"]["m_script_skeleton"] = None

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.m_script_skeleton is None


@pytest.mark.parametrize(
    ("mscript_results", "expected_value", "expected_outcome", "expected_code"),
    [
        ([{"m_script_skeleton": "clear; clc;"}], "clear; clc;", "generated", None),
        ([{"m_script_skeleton": None}], None, "returned_null", None),
        (
            [LLMTimeoutError("SECRET_TIMEOUT"), LLMTimeoutError("SECRET_TIMEOUT")],
            None,
            "degraded",
            "timeout",
        ),
        (
            [LLMRateLimitError("SECRET_RATE"), LLMServerError("SECRET_SERVER")],
            None,
            "degraded",
            "transient",
        ),
        (
            [
                PaperPlanGenerationError(
                    "SECRET_RAW_JSON",
                    reason_code="invalid_json",
                    finish_reason="length",
                    leaf="mscript_drafter",
                )
            ],
            None,
            "degraded",
            "truncated",
        ),
        ([{"m_script_skeleton": 3.5}], None, "degraded", "schema-invalid"),
        ([RuntimeError("SECRET_RUNTIME")], None, "degraded", "internal-error"),
    ],
)
@pytest.mark.asyncio
async def test_mscript_outcomes_do_not_block_build_steps_or_guidance(
    mscript_results: list[dict[str, Any] | BaseException],
    expected_value: str | None,
    expected_outcome: str,
    expected_code: str | None,
) -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = mscript_results
    service = CountingPayloadPaperPlanService(payloads)

    plan, _, _ = await service.generate(_spec(), "PAPER-001")

    assert plan.m_script_skeleton == expected_value
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.outcome == expected_outcome
    assert outcome.degradation_code == expected_code
    assert service.calls.count("build_step_planner") == 1
    assert service.guidance_calls == 1


@pytest.mark.asyncio
async def test_mscript_unparseable_degrades_separately_from_returned_null() -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = [
        PaperPlanGenerationError(
            "SECRET_RAW_JSON",
            reason_code="invalid_json",
            finish_reason="stop",
            leaf="mscript_drafter",
        )
    ]
    service = CountingPayloadPaperPlanService(payloads)

    plan, _, _ = await service.generate(_spec(), "PAPER-001")

    assert plan.m_script_skeleton is None
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.outcome == "degraded"
    assert outcome.degradation_code == "unparseable"
    assert service.calls.count("build_step_planner") == 1
    assert service.guidance_calls == 1


@pytest.mark.asyncio
async def test_conflicted_parameter_mapping_is_rejected_without_pruning() -> None:
    with pytest.raises(PaperPlanGenerationError, match="parameter_conflict_mapping"):
        await PayloadPaperPlanService(_payloads()).generate(_conflict_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_all_conflicted_parameters_can_abstain_and_fallback_build_steps() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"] = []
    payloads["missing_detector"] = {"missing_prompts": []}

    plan, missing_prompts, missing_bindings = await PayloadPaperPlanService(payloads).generate(
        _conflict_spec(),
        "PAPER-001",
    )

    assert plan.parameter_mapping == []
    assert missing_prompts == []
    assert missing_bindings == []
    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]


@pytest.mark.asyncio
async def test_mscript_drafter_rejects_conflict_candidate_assignment() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"] = []
    payloads["missing_detector"] = {"missing_prompts": []}
    payloads["mscript_drafter"] = {"m_script_skeleton": "clear; clc;\nH = 3.5;"}

    service = CountingPayloadPaperPlanService(payloads)
    plan, _, _ = await service.generate(_conflict_spec(), "PAPER-001")

    assert plan.m_script_skeleton is None
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.outcome == "degraded"
    assert outcome.degradation_code == "conflict-guard"
    assert service.calls.count("build_step_planner") == 1
    assert service.guidance_calls == 1


@pytest.mark.asyncio
async def test_mscript_cancelled_error_propagates() -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = [asyncio.CancelledError()]
    service = CountingPayloadPaperPlanService(payloads)

    with pytest.raises(asyncio.CancelledError):
        await service.generate(_spec(), "PAPER-001")

    assert "build_step_planner" not in service.calls
    assert service.guidance_calls == 0


@pytest.mark.asyncio
async def test_mscript_drafter_from_mapping_rejects_conflict_candidate_assignment() -> None:
    payloads = _payloads()
    payloads["mscript_drafter_from_mapping"] = {"m_script_skeleton": "clear; clc;\nH = 3.5;"}

    with pytest.raises(PaperPlanGenerationError, match="parameter_conflict_mscript"):
        await PayloadPaperPlanService(payloads)._llm_mscript_draft_from_mapping(
            [],
            _conflict_spec(),
        )


@pytest.mark.asyncio
async def test_structured_build_steps_invalid_payload_falls_back_to_legacy() -> None:
    payloads = _payloads()
    payloads["build_step_planner"] = {"build_steps": []}
    service = PayloadPaperPlanService(payloads)

    plan, missing_prompts, _ = await service.generate(_spec(), "PAPER-001")

    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]
    assert [prompt.prompt_id for prompt in missing_prompts] == ["MISS-001"]
    assert service.calls == [
        "plan_composer",
        "mscript_drafter",
        "missing_detector",
        "build_step_planner",
        "subsystem_planner",
    ]


@pytest.mark.asyncio
async def test_redline_value_leak_falls_back_to_legacy() -> None:
    payloads = _payloads()
    payloads["missing_detector"] = {"missing_prompts": []}
    payloads["plan_composer"]["parameter_mapping"] = [
        {
            "paper_param_name": "Rs",
            "model_param_name": "Synchronous Machine.Rs",
            "value": "0.05",
            "unit": "Ω",
            "source": "document_extracted",
        }
    ]
    payloads["build_step_planner"] = _build_steps_payload(
        paper_param_name="Rs",
        model_param_name="Synchronous Machine.Rs",
    )
    payloads["build_step_planner"]["build_steps"][0]["title"] = "Place Rs block with 0.05 Ω"

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]


@pytest.mark.asyncio
async def test_structured_fallback_log_is_reason_coded_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warning_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_warning(*args: object, **kwargs: object) -> None:
        warning_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "warning", fake_warning)
    payloads = _payloads()
    payloads["missing_detector"] = {"missing_prompts": []}
    payloads["plan_composer"]["parameter_mapping"] = [
        {
            "paper_param_name": "Rs",
            "model_param_name": "Synchronous Machine.Rs",
            "value": "0.05",
            "unit": "Ω",
            "source": "document_extracted",
        }
    ]
    payloads["build_step_planner"] = _build_steps_payload(
        paper_param_name="Rs",
        model_param_name="Synchronous Machine.Rs",
    )
    payloads["build_step_planner"]["build_steps"][0]["title"] = "Place Rs block with 0.05 Ω"

    await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    logged = repr(warning_calls)
    assert "paper_plan_build_steps_fallback reason_code=%s" in logged
    assert "parameter_value_leak" in logged
    assert "0.05" not in logged
    assert "Ω" not in logged


@pytest.mark.asyncio
async def test_dependency_audit_shadows_dto_invalid_terminal_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MXA_BUILD_STEPS_DEPENDENCY_AUDIT", "1")
    warning_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_warning(*args: object, **kwargs: object) -> None:
        warning_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "warning", fake_warning)
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][2]["depends_on"] = ["STEP-003"]
    payloads["build_step_planner"]["build_steps"][2]["unexpected"] = "dto failure"
    service = PayloadPaperPlanService(payloads)

    plan, _, _ = await service.generate(_spec(), "PAPER-001")

    audit = service.build_steps_dependency_audit()
    assert plan.build_steps is None
    assert audit.dependency_audit_status == "violations"
    assert audit.violations_by_code["self"] == 1
    logged = repr(warning_calls)
    assert "reason_code=%s" in logged
    assert "dto_invalid" in logged
    assert '"dependency_audit_status":"violations"' in logged


@pytest.mark.asyncio
async def test_dependency_audit_log_does_not_include_nonconforming_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MXA_BUILD_STEPS_DEPENDENCY_AUDIT", "1")
    warning_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_warning(*args: object, **kwargs: object) -> None:
        warning_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "warning", fake_warning)
    leaked_dependency = "STEP-002 求解第3.2节"
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][2]["depends_on"] = [leaked_dependency]

    await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    logged = repr(warning_calls)
    assert "depends_on_unknown" in logged
    assert "dep_length_bucket" in logged
    assert leaked_dependency not in logged
    assert "求解第3.2节" not in logged


@pytest.mark.asyncio
async def test_dependency_audit_toggle_does_not_change_plan_output_or_terminal_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_once(enabled: bool) -> tuple[dict[str, Any], list[str], list[str]]:
        if enabled:
            monkeypatch.setenv("MXA_BUILD_STEPS_DEPENDENCY_AUDIT", "1")
        else:
            monkeypatch.delenv("MXA_BUILD_STEPS_DEPENDENCY_AUDIT", raising=False)
        payloads = _payloads()
        payloads["build_step_planner"]["build_steps"][2]["depends_on"] = ["STEP-003"]
        service = _FallbackRecordingPaperPlanService(payloads)

        plan, missing_prompts, missing_bindings = await service.generate(_spec(), "PAPER-001")

        return (
            ModelGenerationPlanModel.from_domain(plan).model_dump(mode="json"),
            service.fallback_reason_codes,
            [prompt.prompt_id for prompt in missing_prompts]
            + [binding.prompt_id for binding in missing_bindings],
        )

    off_result = await run_once(False)
    on_result = await run_once(True)

    assert off_result == on_result
    assert on_result[1] == ["depends_on_self"]


@pytest.mark.asyncio
async def test_user_supplied_build_step_evidence_falls_back_to_legacy() -> None:
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][0]["evidence"] = [_user_evidence_payload()]

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]


@pytest.mark.asyncio
async def test_user_supplied_block_ref_paper_reference_falls_back_to_legacy() -> None:
    payloads = _payloads()
    payloads["build_step_planner"]["build_steps"][0]["block_refs"][0]["paper_reference"] = (
        _user_evidence_payload()
    )

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]


@pytest.mark.asyncio
async def test_build_step_provider_error_propagates_without_legacy_fallback() -> None:
    payloads = _payloads()
    payloads["build_step_planner"] = LLMRateLimitError("rate")
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(LLMRateLimitError):
        await service.generate(_spec(), "PAPER-001")

    assert "subsystem_planner" not in service.calls


@pytest.mark.asyncio
async def test_legacy_error_after_structured_fallback_propagates() -> None:
    payloads = _payloads()
    payloads["build_step_planner"] = {"build_steps": []}
    payloads["subsystem_planner"] = PaperPlanGenerationError("legacy_failed")

    with pytest.raises(PaperPlanGenerationError, match="legacy_failed"):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_composer_missing_sentinel_fails_in_detector_cardinality() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"][0]["value"] = "3.5"

    with pytest.raises(PaperPlanGenerationError, match="missing_prompt_cardinality_mismatch"):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_duplicate_sentinel_mapping_fails_before_assembly() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"].append(
        {
            "paper_param_name": "H",
            "model_param_name": "Synchronous Machine.H duplicate",
            "value": MISSING_VALUE_SENTINEL,
            "unit": "s",
            "source": "document_extracted",
        }
    )

    with pytest.raises(PaperPlanGenerationError, match="paper_param_name_duplicate"):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_evidence_tagger_validates_plan_evidence() -> None:
    tagger = RecordingEvidenceTagger()
    plan, _, _ = await PayloadPaperPlanService(_payloads(), evidence_tagger=tagger).generate(
        _spec(), "PAPER-001"
    )

    assert tagger.calls[0] == plan.evidence


@pytest.mark.asyncio
async def test_evidence_tagger_validates_block_recommendations_paper_reference() -> None:
    tagger = RecordingEvidenceTagger()
    plan, _, _ = await PayloadPaperPlanService(_payloads(), evidence_tagger=tagger).generate(
        _spec(), "PAPER-001"
    )

    assert tagger.calls[1] == [plan.block_recommendations[0].paper_reference]


@pytest.mark.asyncio
async def test_evidence_tagger_validates_missing_prompts_paper_reference() -> None:
    tagger = RecordingEvidenceTagger()
    _, missing_prompts, _ = await PayloadPaperPlanService(
        _payloads(), evidence_tagger=tagger
    ).generate(_spec(), "PAPER-001")

    assert tagger.calls[2] == [missing_prompts[0].paper_reference]


@pytest.mark.asyncio
async def test_evidence_tagger_locator_whitelist_fail_raises_502() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["evidence"][0]["source_ref"] = "REF-999"

    with pytest.raises(PaperPlanGenerationError):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_invalid_json_raises_paper_plan_generation_error() -> None:
    service = PaperPlanService(QueueTextProvider(["not json", "still not json"]))

    with pytest.raises(PaperPlanGenerationError, match="invalid_json") as exc_info:
        await service._call_llm_json([LLMMessage("system", "x")], "plan_composer")

    assert exc_info.value.reason_code == "invalid_json"


@pytest.mark.asyncio
async def test_build_step_invalid_json_raises_structured_error() -> None:
    service = PaperPlanService(QueueTextProvider(["not json", "still not json"]))

    with pytest.raises(BuildStepsJsonParseError, match="json_parse_failed"):
        await service._call_llm_json([LLMMessage("system", "x")], "build_step_planner")


@pytest.mark.asyncio
async def test_regenerate_build_step_invalid_json_raises_structured_error() -> None:
    service = PaperPlanService(QueueTextProvider(["not json", "still not json"]))

    with pytest.raises(BuildStepsJsonParseError, match="json_parse_failed"):
        await service._call_llm_json([LLMMessage("system", "x")], "build_step_regenerator")


@pytest.mark.asyncio
async def test_invalid_json_retries_once_then_returns_valid_payload() -> None:
    provider = QueueTextProvider(["not json", '{"ok": true}'])
    service = PaperPlanService(provider)

    data = await service._call_llm_json([LLMMessage("system", "x")], "plan_composer")

    assert data == {"ok": True}
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_call_llm_json_counts_decode_retry_against_job_cap() -> None:
    provider = QueueTextProvider(["not json", '{"ok": true}'])
    service = PaperPlanService(provider)
    context = StructuredRetryContext(warning_call_count=1, hard_call_count=1)

    with pytest.raises(PaperPlanGenerationError) as exc_info:
        await service.generate(_spec(), "PAPER-001", retry_context=context)

    assert exc_info.value.reason_code == REASON_CALL_CAP_EXCEEDED
    assert len(provider.calls) == 1
    assert context.call_count == 1


@pytest.mark.asyncio
async def test_build_steps_cap_boundary_still_falls_back_to_legacy() -> None:
    class BuildStepsCapBoundaryService(PaperPlanService):
        async def _llm_plan_compose(
            self,
            spec: PaperSpec,
            plan_id: str,
            paper_spec_id: str,
        ) -> ModelGenerationPlan:
            _ = spec, plan_id, paper_spec_id
            return _plan_domain(missing=False)

        async def _llm_mscript_draft(self, spec: PaperSpec) -> str | None:
            _ = spec
            return None

        async def _llm_missing_detect(
            self,
            spec: PaperSpec,
            paper_id: str,
            sentinel_mappings: list[ParameterMapping],
        ) -> list[MissingParameterPrompt]:
            _ = spec, paper_id, sentinel_mappings
            return []

    provider = QueueTextProvider(
        [
            json.dumps({"build_steps": []}),
            json.dumps(
                {
                    "subsystem_breakdown": [
                        "第 1 步:放置电机",
                        "第 2 步:接入故障",
                        "第 3 步:观察电流",
                    ]
                }
            ),
        ]
    )
    service = BuildStepsCapBoundaryService(provider)
    context = StructuredRetryContext(warning_call_count=1, hard_call_count=1)
    context.call_count = 1

    plan, missing_prompts, _ = await service.generate(
        _spec(),
        "PAPER-001",
        retry_context=context,
    )

    assert plan.build_steps is None
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]
    assert missing_prompts == []
    assert len(provider.calls) == 2
    assert context.call_count == 1


@pytest.mark.asyncio
async def test_pydantic_validation_error_raises_paper_plan_generation_error() -> None:
    payloads = _payloads()
    del payloads["plan_composer"]["library_choice"]

    with pytest.raises(PaperPlanGenerationError, match="validation_failed") as exc_info:
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )

    assert exc_info.value.reason_code == "schema_validation"


@pytest.mark.asyncio
async def test_llm_provider_error_propagates_without_wrapping() -> None:
    service = PaperPlanService(QueueTextProvider([LLMRateLimitError("rate")]))

    with pytest.raises(LLMRateLimitError):
        await service._call_llm_json([LLMMessage("system", "x")], "plan_composer")


@pytest.mark.asyncio
async def test_logger_uses_error_with_reason_code_not_exception_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_error(*args: object, **kwargs: object) -> None:
        error_calls.append((args, kwargs))

    def fake_exception(*args: object, **kwargs: object) -> None:
        _ = args, kwargs
        raise AssertionError("logger.exception must not be used")

    monkeypatch.setattr(service_module.logger, "error", fake_error)
    monkeypatch.setattr(service_module.logger, "exception", fake_exception)

    with pytest.raises(PaperPlanGenerationError):
        await PaperPlanService(QueueTextProvider(["not json", "still not json"]))._call_llm_json(
            [LLMMessage("system", "x")],
            "plan_composer",
        )

    assert error_calls
    logged = " ".join(repr(arg) for arg in error_calls[0][0])
    assert "invalid_json" in logged
    assert "JSONDecodeError" not in logged


@pytest.mark.asyncio
async def test_logger_does_not_leak_llm_response_text(monkeypatch: pytest.MonkeyPatch) -> None:
    error_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_error(*args: object, **kwargs: object) -> None:
        error_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "error", fake_error)
    with pytest.raises(PaperPlanGenerationError):
        await PaperPlanService(
            QueueTextProvider(["SECRET_LLM_RAW_TEXT", "SECRET_LLM_RAW_TEXT"])
        )._call_llm_json([LLMMessage("system", "x")], "plan_composer")

    logged_text = " ".join(repr(item) for call in error_calls for item in call[0])
    assert "SECRET_LLM_RAW_TEXT" not in logged_text


@pytest.mark.asyncio
async def test_mscript_degradation_log_sink_failure_does_not_abort_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = [RuntimeError("SECRET_MSCRIPT_MESSAGE")]
    service = CountingPayloadPaperPlanService(payloads)

    def failing_info(*args: object, **kwargs: object) -> None:
        _ = args, kwargs
        raise RuntimeError("telemetry sink down")

    monkeypatch.setattr(service_module.logger, "info", failing_info)

    plan, _, _ = await service.generate(_spec(), "PAPER-001")

    assert plan.build_steps is not None
    assert plan.m_script_skeleton is None
    outcome = service.last_mscript_draft_outcome()
    assert outcome is not None
    assert outcome.degradation_code == "internal-error"


@pytest.mark.asyncio
async def test_mscript_degradation_logs_do_not_include_exception_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    payloads: dict[str, list[dict[str, Any] | BaseException] | dict[str, Any] | BaseException] = (
        _payloads()
    )
    payloads["mscript_drafter"] = [RuntimeError("SECRET_MSCRIPT_MESSAGE")]
    service = CountingPayloadPaperPlanService(payloads)

    def fake_info(*args: object, **kwargs: object) -> None:
        info_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "info", fake_info)

    await service.generate(_spec(), "PAPER-001")

    logged_text = " ".join(repr(item) for call in info_calls for item in call[0])
    assert "internal-error" in logged_text
    assert "SECRET_MSCRIPT_MESSAGE" not in logged_text


class _FallbackRecordingPaperPlanService(PayloadPaperPlanService):
    def __init__(self, payloads: dict[str, dict[str, Any] | Exception]) -> None:
        super().__init__(payloads)
        self.fallback_reason_codes: list[str] = []

    def _log_build_steps_fallback(self, exc: BuildStepsStructuredError) -> None:
        self.fallback_reason_codes.append(exc.reason_code)
        super()._log_build_steps_fallback(exc)


def _payloads() -> dict[str, dict[str, Any]]:
    return {
        "missing_detector": {"missing_prompts": [_missing_prompt_payload()]},
        "plan_composer": _plan_payload(),
        "build_step_planner": _build_steps_payload(),
        "subsystem_planner": {
            "subsystem_breakdown": ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]
        },
        "mscript_drafter": {
            "m_script_skeleton": "clear; clc;\n% 参数区\nfigure; subplot(1,1,1); title('短路电流');"
        },
    }


def _build_steps_payload(
    *,
    paper_param_name: str = "H",
    model_param_name: str = "Synchronous Machine.H",
) -> dict[str, Any]:
    return {
        "build_steps": [
            {
                "step_id": "STEP-001",
                "title": "Place machine block",
                "intent": "Create the machine subsystem entry point.",
                "block_refs": [
                    {
                        "block_ref_id": "B1",
                        "block_type": "Synchronous Machine",
                        "library_path": None,
                        "purpose": "Model the generator.",
                        "paper_reference": _document_draft_evidence_payload(),
                    }
                ],
                "parameter_refs": [],
                "connection_hints": [],
                "configuration_hints": [],
                "depends_on": [],
                "evidence": [_document_draft_evidence_payload()],
            },
            {
                "step_id": "STEP-002",
                "title": "Bind machine parameter",
                "intent": "Link the paper parameter name to the model slot.",
                "block_refs": [],
                "parameter_refs": [
                    {
                        "paper_param_name": paper_param_name,
                        "model_param_name": model_param_name,
                    }
                ],
                "connection_hints": [],
                "configuration_hints": [],
                "depends_on": ["STEP-001"],
                "evidence": [_document_draft_evidence_payload()],
            },
            {
                "step_id": "STEP-003",
                "title": "Prepare simulation observation",
                "intent": "Keep the simulation output ready for comparison.",
                "block_refs": [],
                "parameter_refs": [],
                "connection_hints": [],
                "configuration_hints": [
                    {
                        "target": "simulation",
                        "setting_name": "Signal logging",
                        "instruction": "Record the generated current signal.",
                        "evidence": [_document_draft_evidence_payload()],
                    }
                ],
                "depends_on": ["STEP-001"],
                "evidence": [_document_draft_evidence_payload()],
            },
        ]
    }


def _build_step_drafts() -> list[ModelBuildStepDraft]:
    return _drafts_from_build_steps_payload(_build_steps_payload())


def _drafts_from_build_steps_payload(payload: dict[str, Any]) -> list[ModelBuildStepDraft]:
    bridged_payload = service_module._resolve_build_steps_draft_evidence_payload(
        payload,
        document_source_refs=service_module.build_plan_evidence_source_refs(_spec()),
        user_source_refs=[],
    )
    return service_module._BuildStepsOutputModel.model_validate(bridged_payload).to_drafts()


def _plan_payload() -> dict[str, Any]:
    return {
        "plan_id": "PLAN-PAPER-001",
        "paper_spec_id": "PAPER-001",
        "library_choice": "SimPowerSystems, because the report describes a synchronous machine.",
        "block_recommendations": [
            {
                "block_type": "Synchronous Machine",
                "purpose": "Model the generator.",
                "paper_reference": _document_evidence_payload(),
            }
        ],
        "parameter_mapping": [
            {
                "paper_param_name": "H",
                "model_param_name": "Synchronous Machine.H",
                "value": MISSING_VALUE_SENTINEL,
                "unit": "s",
                "source": "document_extracted",
            }
        ],
        "subsystem_breakdown": [],
        "m_script_skeleton": None,
        "evidence": [_document_evidence_payload()],
    }


def _missing_prompt_payload() -> dict[str, Any]:
    return {
        "parameter_name": "H",
        "paper_reference": _document_evidence_payload(figure_id="FIG-01"),
        "suggested_unit": "s",
        "source": "user_supplied",
    }


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A synchronous machine short-circuit report.",
        equations=[
            EquationEntry(
                equation_id="EQ-01",
                latex_or_text="H = 3.5",
                paper_section_id="S1",
                document_id="DOC-001",
            )
        ],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id="DOC-001",
            )
        ],
        figure_locations=[
            FigureRef(
                figure_id="FIG-01",
                caption="Machine parameters",
                paper_section_id="S1",
                document_id="DOC-001",
            )
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _conflict_spec() -> PaperSpec:
    evidence = _document_evidence()
    return with_parameter_conflicts(
        PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            documents=[
                PaperDocument(document_id="DOC-001", filename="paper-a.pdf"),
                PaperDocument(document_id="DOC-002", filename="paper-b.pdf"),
            ],
            primary_document_id=None,
            abstract="A synchronous machine short-circuit report.",
            equations=[],
            parameter_table=[
                ParameterEntry(
                    name="Inertia constant",
                    symbol="H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                    document_id="DOC-001",
                ),
                ParameterEntry(
                    name="Inertia constant",
                    symbol="H",
                    value="4.0",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                    document_id="DOC-002",
                ),
            ],
            figure_locations=[
                FigureRef(
                    figure_id="FIG-01",
                    caption="Machine parameters",
                    paper_section_id="S1",
                    document_id="DOC-001",
                )
            ],
            pseudocode_blocks=[],
            evidence=[evidence],
        )
    )


def _plan_domain(*, missing: bool = True) -> ModelGenerationPlan:
    evidence = _document_evidence()
    return ModelGenerationPlan(
        plan_id="PLAN-PAPER-001",
        paper_spec_id="PAPER-001",
        library_choice="SimPowerSystems",
        block_recommendations=[_block_recommendation()],
        parameter_mapping=[
            ParameterMapping(
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
                value=MISSING_VALUE_SENTINEL if missing else "3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        subsystem_breakdown=[],
        m_script_skeleton=None,
        evidence=[evidence],
    )


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Synchronous Machine",
        purpose="Model the generator.",
        paper_reference=_document_evidence(),
    )


def _sentinel_mapping() -> ParameterMapping:
    return ParameterMapping(
        paper_param_name="H",
        model_param_name="Synchronous Machine.H",
        value=MISSING_VALUE_SENTINEL,
        unit="s",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )


def _document_evidence_payload(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> dict[str, Any]:
    source_ref = "REF-001"
    if equation_id is not None:
        source_ref = "REF-002"
    if figure_id is not None:
        source_ref = "REF-003"
    return {
        "source": "document_extracted",
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": "The report states the machine parameter.",
        "missing_param_prompt_id": None,
        "source_ref": source_ref,
    }


def _document_draft_evidence_payload(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> dict[str, Any]:
    source_ref = "REF-001"
    if equation_id is not None:
        source_ref = "REF-002"
    if figure_id is not None:
        source_ref = "REF-003"
    _ = paper_section_id
    return {"source_ref": source_ref}


def _user_evidence_payload() -> dict[str, Any]:
    return {
        "source": "user_supplied",
        "document_id": None,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": "MISS-1",
        "user_action": "fill_missing",
        "parameter_correction_id": None,
        "correction_param_key": None,
    }


def _user_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id="MISS-1",
        user_action=UserEvidenceAction.FILL_MISSING,
    )
