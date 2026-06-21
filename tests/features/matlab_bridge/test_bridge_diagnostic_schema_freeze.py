from dataclasses import fields
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from core.domain.bridge_diagnostic import BridgeDiagnostic, BridgeDiagnosticReceipt
from features.matlab_bridge.bridge_diagnostic_schemas import (
    BridgeDiagnosticReceiptModel,
    BridgeDiagnosticRequest,
    BridgeErrorResponse,
)
from features.matlab_bridge.diagnostic_service import DiagnosticService


def test_top_level_model_names_are_frozen() -> None:
    assert [
        BridgeDiagnosticRequest.__name__,
        BridgeDiagnosticReceiptModel.__name__,
        BridgeErrorResponse.__name__,
    ] == [
        "BridgeDiagnosticRequest",
        "BridgeDiagnosticReceiptModel",
        "BridgeErrorResponse",
    ]


def test_extra_forbid_at_all_levels() -> None:
    for model in (BridgeDiagnosticRequest, BridgeDiagnosticReceiptModel, BridgeErrorResponse):
        assert model.model_config.get("extra") == "forbid"


def test_request_and_receipt_field_order_matches_domain() -> None:
    assert tuple(BridgeDiagnosticRequest.model_fields) == tuple(
        field.name for field in fields(BridgeDiagnostic)
    )
    assert tuple(BridgeDiagnosticReceiptModel.model_fields) == tuple(
        field.name for field in fields(BridgeDiagnosticReceipt)
    )


def test_error_response_field_order_is_frozen() -> None:
    assert tuple(BridgeErrorResponse.model_fields) == ("error", "message")


def test_literals_are_frozen() -> None:
    assert get_args(BridgeDiagnosticRequest.model_fields["protocol_version"].annotation) == (
        "0.3-a",
    )
    assert get_args(BridgeDiagnosticRequest.model_fields["diagnostic_kind"].annotation) == (
        "manual_error",
    )
    assert get_args(BridgeDiagnosticReceiptModel.model_fields["status"].annotation) == ("received",)
    assert get_args(BridgeDiagnosticReceiptModel.model_fields["mode"].annotation) == (
        "connectivity_stub",
    )


def test_request_to_domain_and_receipt_from_domain_round_trip() -> None:
    request = BridgeDiagnosticRequest.model_validate(
        {
            "protocol_version": "0.3-a",
            "request_id": "2690af3d-9cfe-4442-900e-c86af37a6244",
            "diagnostic_kind": "manual_error",
            "matlab_release": "R2026a",
            "client_version": "0.1.0",
            "error_text": "manual error",
            "consent_confirmed": True,
        }
    )

    domain_request = request.to_domain()
    domain_receipt = DiagnosticService().consume(domain_request)
    receipt = BridgeDiagnosticReceiptModel.from_domain(domain_receipt)

    assert domain_request == BridgeDiagnostic(
        protocol_version="0.3-a",
        request_id=request.request_id,
        diagnostic_kind="manual_error",
        matlab_release="R2026a",
        client_version="0.1.0",
        error_text="manual error",
        consent_confirmed=True,
    )
    assert receipt.model_dump(mode="json") == {
        "request_id": "2690af3d-9cfe-4442-900e-c86af37a6244",
        "status": "received",
        "mode": "connectivity_stub",
        "message": "连接成功。本版本仅验证诊断信息传输,不提供报错解释。",
    }


def test_domain_contract_does_not_import_pydantic() -> None:
    source = Path("core/domain/bridge_diagnostic.py").read_text(encoding="utf-8")

    assert "pydantic" not in source.lower()


def test_schema_aliases_are_base_models() -> None:
    assert issubclass(BridgeDiagnosticRequest, BaseModel)
    assert issubclass(BridgeDiagnosticReceiptModel, BaseModel)
    assert issubclass(BridgeErrorResponse, BaseModel)
