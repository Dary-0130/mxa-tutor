from uuid import UUID

import pytest
from pydantic import ValidationError

from features.matlab_bridge.bridge_diagnostic_schemas import (
    BridgeDiagnosticReceiptModel,
    BridgeDiagnosticRequest,
    BridgeErrorResponse,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-a",
        "request_id": REQUEST_ID,
        "diagnostic_kind": "manual_error",
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "error_text": "Error using foo at line 1",
        "consent_confirmed": True,
    }
    payload.update(overrides)
    return payload


def test_valid_request_strips_error_text_and_converts_to_domain() -> None:
    request = BridgeDiagnosticRequest.model_validate(
        _valid_payload(error_text="  Error using foo  ")
    )

    domain = request.to_domain()

    assert domain.protocol_version == "0.3-a"
    assert domain.request_id == UUID(REQUEST_ID)
    assert domain.diagnostic_kind == "manual_error"
    assert domain.matlab_release == "R2026a"
    assert domain.client_version == "0.1.0"
    assert domain.error_text == "Error using foo"
    assert domain.consent_confirmed is True


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_consent_confirmed_must_be_strict_true(value: object) -> None:
    with pytest.raises(ValidationError):
        BridgeDiagnosticRequest.model_validate(_valid_payload(consent_confirmed=value))


def test_missing_consent_confirmed_is_rejected() -> None:
    payload = _valid_payload()
    payload.pop("consent_confirmed")

    with pytest.raises(ValidationError):
        BridgeDiagnosticRequest.model_validate(payload)


@pytest.mark.parametrize("value", ["", "   ", "bad\x00text", "x" * 4097])
def test_error_text_boundaries(value: str) -> None:
    with pytest.raises(ValidationError):
        BridgeDiagnosticRequest.model_validate(_valid_payload(error_text=value))


@pytest.mark.parametrize("value", ["R2026", "2026a", "R1999a", "R2026c"])
def test_matlab_release_pattern(value: str) -> None:
    with pytest.raises(ValidationError):
        BridgeDiagnosticRequest.model_validate(_valid_payload(matlab_release=value))


@pytest.mark.parametrize("value", ["", "bad version!", "x" * 33])
def test_client_version_pattern(value: str) -> None:
    with pytest.raises(ValidationError):
        BridgeDiagnosticRequest.model_validate(_valid_payload(client_version=value))


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
        BridgeDiagnosticRequest.model_validate(_valid_payload(**{field: "SECRET"}))


def test_receipt_model_from_domain_uses_locked_message() -> None:
    domain = BridgeDiagnosticRequest.model_validate(_valid_payload()).to_domain()
    receipt = BridgeDiagnosticReceiptModel.from_domain(
        type(
            "Receipt",
            (),
            {
                "request_id": domain.request_id,
                "status": "received",
                "mode": "connectivity_stub",
                "message": "连接成功。本版本仅验证诊断信息传输,不提供报错解释。",
            },
        )()
    )

    assert receipt.model_dump(mode="json") == {
        "request_id": REQUEST_ID,
        "status": "received",
        "mode": "connectivity_stub",
        "message": "连接成功。本版本仅验证诊断信息传输,不提供报错解释。",
    }


def test_bridge_error_response_shape_is_error_and_message_only() -> None:
    response = BridgeErrorResponse.model_validate(
        {"error": "bridge_payload_too_large", "message": "诊断内容过大"}
    )

    assert tuple(BridgeErrorResponse.model_fields) == ("error", "message")
    assert response.model_dump() == {
        "error": "bridge_payload_too_large",
        "message": "诊断内容过大",
    }
