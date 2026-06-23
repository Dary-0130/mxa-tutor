from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from features.matlab_bridge.bridge_explanation_schemas import (
    BridgeExplanationErrorResponse,
    BridgeExplanationRequest,
    BridgeExplanationResultModel,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SIGNAL = "Undefined function or variable Kp_ctrl"


def _valid_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b1",
        "request_id": REQUEST_ID,
        "diagnostic_kind": "manual_error",
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "error_text": f"Error using sim. {SIGNAL}.",
        "llm_processing_consent_confirmed": True,
    }
    payload.update(overrides)
    return payload


def _valid_result(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b1",
        "request_id": REQUEST_ID,
        "status": "completed",
        "mode": "llm_error_explanation",
        "meaning": "这段报错表示 MATLAB 没找到 Kp_ctrl 这个名称。",
        "likely_causes": [
            {
                "cause": "Kp_ctrl 可能尚未定义或未进入当前 workspace。",
                "is_inference": True,
                "confidence": "medium",
                "supporting_signals": [SIGNAL],
            }
        ],
        "next_steps": [{"action": "先运行 which 或检查初始化脚本是否定义 Kp_ctrl。"}],
        "caveats": ["这里只基于粘贴的报错文本,没有运行仿真。"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("diagnostic_kind", ["manual_error", "auto_captured_error"])
def test_request_strips_error_text_and_converts_to_domain(diagnostic_kind: str) -> None:
    request = BridgeExplanationRequest.model_validate(
        _valid_request(diagnostic_kind=diagnostic_kind, error_text="  manual error  ")
    )

    domain = request.to_domain()

    assert domain.protocol_version == "0.3-b1"
    assert domain.request_id == UUID(REQUEST_ID)
    assert domain.diagnostic_kind == diagnostic_kind
    assert domain.matlab_release == "R2026a"
    assert domain.client_version == "0.1.0"
    assert domain.error_text == "manual error"
    assert domain.llm_processing_consent_confirmed is True


def test_request_rejects_unknown_diagnostic_kind() -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationRequest.model_validate(_valid_request(diagnostic_kind="diagnostic_stub"))


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_llm_processing_consent_must_be_strict_true(value: object) -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationRequest.model_validate(
            _valid_request(llm_processing_consent_confirmed=value)
        )


@pytest.mark.parametrize("value", ["", "   ", "bad\x00text", "x" * 4097])
def test_error_text_boundaries(value: str) -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationRequest.model_validate(_valid_request(error_text=value))


@pytest.mark.parametrize("value", ["R2026", "2026a", "R1999a", "R2026c"])
def test_matlab_release_pattern(value: str) -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationRequest.model_validate(_valid_request(matlab_release=value))


@pytest.mark.parametrize(
    "field",
    [
        "file_path",
        "source_code",
        "slx_path",
        "workspace",
        "stack",
        "project_files",
        "model_content",
        "files",
    ],
)
def test_sensitive_extra_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationRequest.model_validate(_valid_request(**{field: "SECRET"}))


def test_result_round_trip_to_domain_and_back() -> None:
    result = BridgeExplanationResultModel.model_validate(_valid_result())
    domain = result.to_domain()

    assert (
        BridgeExplanationResultModel.from_domain(domain).model_dump(mode="json") == _valid_result()
    )


@pytest.mark.parametrize(
    "override",
    [
        {"protocol_version": "0.3-a"},
        {"status": "received"},
        {"mode": "connectivity_stub"},
        {"meaning": ""},
        {"likely_causes": []},
        {"next_steps": []},
        {"caveats": []},
    ],
)
def test_result_static_boundaries(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeExplanationResultModel.model_validate(_valid_result(**override))


def test_likely_cause_rejects_high_confidence_and_false_inference() -> None:
    result = _valid_result()
    cause = dict(result["likely_causes"][0])  # type: ignore[index]
    cause["confidence"] = "high"
    cause["is_inference"] = False
    result["likely_causes"] = [cause]

    with pytest.raises(ValidationError):
        BridgeExplanationResultModel.model_validate(result)


@pytest.mark.parametrize("signals", [["[REDACTED_PATH]"], ["----------"], [SIGNAL, SIGNAL]])
def test_supporting_signals_reject_placeholder_punctuation_and_duplicates(
    signals: list[str],
) -> None:
    result = _valid_result()
    cause = dict(result["likely_causes"][0])  # type: ignore[index]
    cause["supporting_signals"] = signals
    result["likely_causes"] = [cause]

    with pytest.raises(ValidationError):
        BridgeExplanationResultModel.model_validate(result)


def test_explanation_error_response_shape_is_independent_from_diagnostic_error() -> None:
    response = BridgeExplanationErrorResponse.model_validate(
        {"error": "bridge_explanation_timeout", "message": "报错解释超时,请稍后重试"}
    )

    assert tuple(BridgeExplanationErrorResponse.model_fields) == ("error", "message")
    assert response.model_dump() == {
        "error": "bridge_explanation_timeout",
        "message": "报错解释超时,请稍后重试",
    }
