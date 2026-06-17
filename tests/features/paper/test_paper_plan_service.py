from __future__ import annotations

import asyncio
import copy
import inspect
import json
from collections.abc import Callable
from typing import Any

import pytest

import features.paper.paper_plan_service as service_module
from core.domain.exceptions import LLMRateLimitError, PaperPlanGenerationError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
    MissingBindingModel,
)
from features.paper.paper_plan_service import PaperPlanService


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
        payloads: dict[str, dict[str, Any]],
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
        return copy.deepcopy(self.payloads[role_name])


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


@pytest.mark.asyncio
async def test_generate_happy_path_returns_plan_missing_bindings() -> None:
    service = PayloadPaperPlanService(_payloads())

    plan, missing_prompts, missing_bindings = await service.generate(_spec(), "PAPER-001")

    assert service.calls == [
        "missing_detector",
        "plan_composer",
        "mscript_drafter",
        "subsystem_planner",
    ]
    assert plan.plan_id == "PLAN-PAPER-001"
    assert plan.paper_spec_id == "PAPER-001"
    assert plan.subsystem_breakdown == ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]
    assert (
        plan.m_script_skeleton
        == "clear; clc;\n% 参数区\nfigure; subplot(1,1,1); title('短路电流');"
    )
    assert [prompt.prompt_id for prompt in missing_prompts] == ["MISS-1"]
    assert missing_bindings == [
        MissingBindingModel(
            prompt_id="MISS-1",
            paper_param_name="H",
            model_param_name="Synchronous Machine.H",
        )
    ]


@pytest.mark.asyncio
async def test_step1_three_llm_calls_run_concurrently_via_asyncio_gather() -> None:
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

        async def _llm_missing_detect(self, spec: PaperSpec) -> list[MissingParameterPrompt]:
            _ = spec
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

        async def _llm_subsystem_plan(
            self,
            block_recommendations: list[BlockRecommendation],
            evidence: list[PaperEvidenceEntry],
        ) -> list[str]:
            _ = block_recommendations, evidence
            return ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]

    service = ConcurrentService()

    await service.generate(_spec(), "PAPER-001")

    assert service.max_active == 3


@pytest.mark.asyncio
async def test_step2_subsystem_planner_awaits_plan_composer_block_recommendations() -> None:
    class OrderedService(PaperPlanService):
        def __init__(self) -> None:
            super().__init__(NoopTextProvider())
            self.plan_done = False

        async def _llm_missing_detect(self, spec: PaperSpec) -> list[MissingParameterPrompt]:
            _ = spec
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

        async def _llm_subsystem_plan(
            self,
            block_recommendations: list[BlockRecommendation],
            evidence: list[PaperEvidenceEntry],
        ) -> list[str]:
            _ = evidence
            assert self.plan_done
            assert block_recommendations[0].block_type == "Synchronous Machine"
            return ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]

    await OrderedService().generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_all_role_helpers_use_call_llm_json(monkeypatch: pytest.MonkeyPatch) -> None:
    service = PaperPlanService(NoopTextProvider())
    calls: list[str] = []

    async def fake_call(messages: list[LLMMessage], role_name: str) -> dict[str, Any]:
        _ = messages
        calls.append(role_name)
        return copy.deepcopy(_payloads()[role_name])

    monkeypatch.setattr(service, "_call_llm_json", fake_call)

    await service._llm_missing_detect(_spec())
    await service._llm_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")
    await service._llm_subsystem_plan([_block_recommendation()], [_document_evidence()])
    await service._llm_mscript_draft(_spec())

    assert calls == [
        "missing_detector",
        "plan_composer",
        "subsystem_planner",
        "mscript_drafter",
    ]


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
    payloads["plan_composer"]["plan_id"] = "PLAN-XXX"
    payloads["plan_composer"]["paper_spec_id"] = "PAPER-XXX"

    plan, _, _ = await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")

    assert plan.plan_id == "PLAN-PAPER-001"
    assert plan.paper_spec_id == "PAPER-001"


@pytest.mark.asyncio
async def test_missing_detector_rejects_paper_reference_not_document_extracted() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["paper_reference"] = _user_evidence_payload()
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError):
        await service._llm_missing_detect(_spec())


@pytest.mark.asyncio
async def test_missing_detector_rejects_figure_id_not_in_spec_whitelist() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["paper_reference"]["figure_id"] = "FIG-99"
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError):
        await service._llm_missing_detect(_spec())


@pytest.mark.asyncio
async def test_missing_detector_rejects_source_not_user_supplied() -> None:
    payloads = _payloads()
    payloads["missing_detector"]["missing_prompts"][0]["source"] = "document_extracted"
    service = PayloadPaperPlanService(payloads)

    with pytest.raises(PaperPlanGenerationError):
        await service._llm_missing_detect(_spec())


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

    with pytest.raises(PaperPlanGenerationError, match="validation_failed"):
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )


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


@pytest.mark.asyncio
async def test_plan_assembler_missing_binding_not_found_raises_502() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["parameter_mapping"][0]["value"] = "3.5"

    with pytest.raises(PaperPlanGenerationError, match="missing_binding_not_found"):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_plan_assembler_missing_binding_ambiguous_raises_502() -> None:
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

    with pytest.raises(PaperPlanGenerationError, match="missing_binding_ambiguous"):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_evidence_tagger_validates_plan_evidence() -> None:
    tagger = RecordingEvidenceTagger()
    plan, _, _ = await PayloadPaperPlanService(_payloads(), evidence_tagger=tagger).generate(
        _spec(), "PAPER-001"
    )

    assert tagger.calls[1] == plan.evidence


@pytest.mark.asyncio
async def test_evidence_tagger_validates_block_recommendations_paper_reference() -> None:
    tagger = RecordingEvidenceTagger()
    plan, _, _ = await PayloadPaperPlanService(_payloads(), evidence_tagger=tagger).generate(
        _spec(), "PAPER-001"
    )

    assert tagger.calls[2] == [plan.block_recommendations[0].paper_reference]


@pytest.mark.asyncio
async def test_evidence_tagger_validates_missing_prompts_paper_reference() -> None:
    tagger = RecordingEvidenceTagger()
    _, missing_prompts, _ = await PayloadPaperPlanService(
        _payloads(), evidence_tagger=tagger
    ).generate(_spec(), "PAPER-001")

    assert tagger.calls[0] == [missing_prompts[0].paper_reference]
    assert tagger.calls[3] == [missing_prompts[0].paper_reference]


@pytest.mark.asyncio
async def test_evidence_tagger_locator_whitelist_fail_raises_502() -> None:
    payloads = _payloads()
    payloads["plan_composer"]["evidence"][0]["paper_section_id"] = "S9"

    with pytest.raises(PaperPlanGenerationError):
        await PayloadPaperPlanService(payloads).generate(_spec(), "PAPER-001")


@pytest.mark.asyncio
async def test_invalid_json_raises_paper_plan_generation_error() -> None:
    service = PaperPlanService(QueueTextProvider(["not json"]))

    with pytest.raises(PaperPlanGenerationError, match="invalid_json"):
        await service._call_llm_json([LLMMessage("system", "x")], "plan_composer")


@pytest.mark.asyncio
async def test_pydantic_validation_error_raises_paper_plan_generation_error() -> None:
    payloads = _payloads()
    del payloads["plan_composer"]["library_choice"]

    with pytest.raises(PaperPlanGenerationError, match="validation_failed"):
        await PayloadPaperPlanService(payloads)._llm_plan_compose(
            _spec(), "PLAN-PAPER-001", "PAPER-001"
        )


@pytest.mark.asyncio
async def test_llm_provider_error_propagates_without_wrapping() -> None:
    service = PaperPlanService(QueueTextProvider([LLMRateLimitError("rate")]))

    with pytest.raises(LLMRateLimitError):
        await service._call_llm_json([LLMMessage("system", "x")], "plan_composer")


@pytest.mark.asyncio
async def test_logger_uses_error_with_type_name_not_exception(
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
        await PaperPlanService(QueueTextProvider(["not json"]))._call_llm_json(
            [LLMMessage("system", "x")],
            "plan_composer",
        )

    assert error_calls
    assert "JSONDecodeError" in " ".join(repr(arg) for arg in error_calls[0][0])


@pytest.mark.asyncio
async def test_logger_does_not_leak_llm_response_text(monkeypatch: pytest.MonkeyPatch) -> None:
    error_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_error(*args: object, **kwargs: object) -> None:
        error_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "error", fake_error)
    with pytest.raises(PaperPlanGenerationError):
        await PaperPlanService(QueueTextProvider(["SECRET_LLM_RAW_TEXT"]))._call_llm_json(
            [LLMMessage("system", "x")],
            "plan_composer",
        )

    logged_text = " ".join(repr(item) for call in error_calls for item in call[0])
    assert "SECRET_LLM_RAW_TEXT" not in logged_text


def _payloads() -> dict[str, dict[str, Any]]:
    return {
        "missing_detector": {"missing_prompts": [_missing_prompt_payload()]},
        "plan_composer": _plan_payload(),
        "subsystem_planner": {
            "subsystem_breakdown": ["第 1 步:放置电机", "第 2 步:接入故障", "第 3 步:观察电流"]
        },
        "mscript_drafter": {
            "m_script_skeleton": "clear; clc;\n% 参数区\nfigure; subplot(1,1,1); title('短路电流');"
        },
    }


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
        "prompt_id": "MISS-1",
        "parameter_name": "H",
        "paper_reference": _document_evidence_payload(figure_id="FIG-01"),
        "suggested_unit": "s",
        "user_supplied_value": None,
        "user_supplied_unit": None,
        "source": "user_supplied",
    }


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        abstract="A synchronous machine short-circuit report.",
        equations=[
            EquationEntry(
                equation_id="EQ-01",
                latex_or_text="H = 3.5",
                paper_section_id="S1",
            )
        ],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        figure_locations=[
            FigureRef(figure_id="FIG-01", caption="Machine parameters", paper_section_id="S1")
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
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


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
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
    return {
        "source": "document_extracted",
        "paper_section_id": paper_section_id,
        "equation_id": equation_id,
        "figure_id": figure_id,
        "excerpt": "The report states the machine parameter.",
        "missing_param_prompt_id": None,
    }


def _user_evidence_payload() -> dict[str, Any]:
    return {
        "source": "user_supplied",
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": "MISS-1",
    }
