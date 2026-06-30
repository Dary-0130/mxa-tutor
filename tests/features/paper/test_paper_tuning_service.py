from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

import pytest

import features.paper.paper_tuning_service as service_module
from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    PaperTuningError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
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
from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL
from features.paper.paper_tuning_service import TUNING_DISCLAIMER, TuningSuggestionService


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
async def test_suggest_injects_fixed_fields_and_validates_public_wrapper() -> None:
    provider = QueueTextProvider([json.dumps(_llm_payload())])
    service = TuningSuggestionService(provider)

    suggestion = await service.suggest(_record(), "  I want stronger damping  ")

    assert suggestion.suggestion_id.startswith("TUNE-paper-1-")
    assert suggestion.user_scenario == "  I want stronger damping  "
    assert suggestion.disclaimer == TUNING_DISCLAIMER
    assert suggestion.parameter_directions[0].param_name == "H"
    assert provider.calls[0][1] is True
    prompt_text = provider.calls[0][0][1].content
    assert "  I want stronger damping  " in prompt_text
    assert "suggestion_id" not in prompt_text
    assert "disclaimer" not in prompt_text


@pytest.mark.asyncio
async def test_call_llm_json_bridges_via_asyncio_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = QueueTextProvider([json.dumps({"ok": True})])
    service = TuningSuggestionService(provider, timeout=12.0, max_tokens=34)
    calls: list[tuple[Callable[..., object], tuple[object, ...], dict[str, object]]] = []

    async def fake_to_thread(
        function: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr(service_module.asyncio, "to_thread", fake_to_thread)

    assert await service._call_llm_json([LLMMessage("system", "x")]) == {"ok": True}
    assert calls[0][0] == provider.chat
    assert calls[0][2] == {"json_mode": True, "timeout": 12.0, "max_tokens": 34}


def test_only_one_asyncio_to_thread_in_service() -> None:
    source = inspect.getsource(service_module.TuningSuggestionService)

    assert source.count("asyncio.to_thread") == 1
    assert "self._text_provider.chat(" not in source


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
async def test_llm_error_subclasses_propagate_without_wrapping(exc: Exception) -> None:
    service = TuningSuggestionService(QueueTextProvider([exc]))

    with pytest.raises(type(exc)):
        await service.suggest(_record(), "Need damping")


@pytest.mark.asyncio
async def test_llm_extra_fixed_fields_raise_paper_tuning_error() -> None:
    payload = _llm_payload()
    payload["disclaimer"] = TUNING_DISCLAIMER

    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider([json.dumps(payload)])).suggest(
            _record(),
            "Need damping",
        )


@pytest.mark.asyncio
async def test_unresolved_user_evidence_is_rejected() -> None:
    payload = _llm_payload(evidence=[_user_evidence_payload("MISS-1")])

    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider([json.dumps(payload)])).suggest(
            _record(resolved=False),
            "Need damping",
        )


@pytest.mark.asyncio
async def test_resolved_user_evidence_is_accepted() -> None:
    payload = _llm_payload(evidence=[_user_evidence_payload("MISS-1")])

    suggestion = await TuningSuggestionService(QueueTextProvider([json.dumps(payload)])).suggest(
        _record(resolved=True),
        "Need damping",
    )

    assert suggestion.evidence[0].source is EvidenceSource.USER_SUPPLIED
    assert suggestion.evidence[0].missing_param_prompt_id == "MISS-1"


@pytest.mark.asyncio
async def test_parameter_direction_rejects_unresolved_sentinel_mapping() -> None:
    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider([json.dumps(_llm_payload())])).suggest(
            _record(resolved=False),
            "Need damping",
        )


@pytest.mark.asyncio
async def test_parameter_direction_rejects_unknown_param_name() -> None:
    payload = _llm_payload(param_name="X")

    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider([json.dumps(payload)])).suggest(
            _record(),
            "Need damping",
        )


@pytest.mark.asyncio
async def test_public_wrapper_validation_failure_raises_paper_tuning_error() -> None:
    payload = _llm_payload(expected_effect="x" * 501)

    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider([json.dumps(payload)])).suggest(
            _record(),
            "Need damping",
        )


@pytest.mark.asyncio
async def test_invalid_json_raises_paper_tuning_error_without_leaking_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_error(*args: object, **kwargs: object) -> None:
        error_calls.append((args, kwargs))

    monkeypatch.setattr(service_module.logger, "error", fake_error)

    with pytest.raises(PaperTuningError):
        await TuningSuggestionService(QueueTextProvider(["SECRET_LLM_RAW_TEXT"])).suggest(
            _record(),
            "SECRET_USER_SCENARIO",
        )

    logged_text = " ".join(repr(item) for call in error_calls for item in call[0])
    assert "SECRET_LLM_RAW_TEXT" not in logged_text
    assert "SECRET_USER_SCENARIO" not in logged_text


def _llm_payload(
    *,
    param_name: str = "H",
    expected_effect: str = "Higher inertia slows current transients.",
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "parameter_directions": [
            {
                "param_name": param_name,
                "direction": "increase",
                "physical_meaning": "Increasing H makes the rotor speed change more slowly.",
            }
        ],
        "expected_effect": expected_effect,
        "confidence": "medium",
        "evidence": evidence or [_document_evidence_payload()],
    }


def _record(*, resolved: bool = True) -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=_plan(resolved=resolved),
        missing_prompts=[_missing_prompt()],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


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


def _plan(*, resolved: bool) -> ModelGenerationPlan:
    evidence = _document_evidence()
    return ModelGenerationPlan(
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
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
                value="3.5" if resolved else MISSING_VALUE_SENTINEL,
                unit="s",
                source=EvidenceSource.USER_SUPPLIED
                if resolved
                else EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=[evidence, _user_evidence("MISS-1")] if resolved else [evidence],
    )


def _missing_prompt() -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id="MISS-1",
        parameter_name="H",
        paper_reference=_document_evidence(figure_id="FIG-01"),
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
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


def _document_evidence_payload() -> dict[str, Any]:
    return {
        "source": "document_extracted",
        "document_id": "DOC-001",
        "paper_section_id": "S1",
        "equation_id": None,
        "figure_id": None,
        "excerpt": "The report states the machine parameter.",
        "missing_param_prompt_id": None,
    }


def _user_evidence_payload(prompt_id: str) -> dict[str, Any]:
    return {
        "source": "user_supplied",
        "document_id": None,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": prompt_id,
    }
