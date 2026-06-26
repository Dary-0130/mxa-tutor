from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from core.domain.bridge_run_state import (
    BridgeRunStateEnvelopeSeries,
    BridgeRunStateIdentitySeries,
    BridgeRunStateMetric,
    BridgeRunStateReceipt,
    BridgeRunStateRequest,
)
from core.domain.bridge_run_state import (
    BridgeRunStateWriteErrorResponse as BridgeRunStateWriteErrorResponseDomain,
)
from features.matlab_bridge.bridge_run_state_schemas import (
    BridgeRunStateAuthErrorResponse,
    BridgeRunStateEnvelopeSeriesModel,
    BridgeRunStateIdentitySeriesModel,
    BridgeRunStateMetricModel,
    BridgeRunStateReceiptModel,
)
from features.matlab_bridge.bridge_run_state_schemas import (
    BridgeRunStateRequest as BridgeRunStateRequestModel,
)
from features.matlab_bridge.bridge_run_state_schemas import (
    BridgeRunStateWriteErrorResponse as BridgeRunStateWriteErrorResponseModel,
)
from scripts.export_bridge_schemas import OUTPUTS


def test_top_level_model_names_are_frozen() -> None:
    assert [
        BridgeRunStateRequestModel.__name__,
        BridgeRunStateReceiptModel.__name__,
        BridgeRunStateMetricModel.__name__,
        BridgeRunStateIdentitySeriesModel.__name__,
        BridgeRunStateEnvelopeSeriesModel.__name__,
        BridgeRunStateWriteErrorResponseModel.__name__,
    ] == [
        "BridgeRunStateRequest",
        "BridgeRunStateReceiptModel",
        "BridgeRunStateMetricModel",
        "BridgeRunStateIdentitySeriesModel",
        "BridgeRunStateEnvelopeSeriesModel",
        "BridgeRunStateWriteErrorResponse",
    ]


def test_extra_forbid_at_all_levels() -> None:
    for model in (
        BridgeRunStateRequestModel,
        BridgeRunStateReceiptModel,
        BridgeRunStateMetricModel,
        BridgeRunStateIdentitySeriesModel,
        BridgeRunStateEnvelopeSeriesModel,
        BridgeRunStateWriteErrorResponseModel,
    ):
        assert model.model_config.get("extra") == "forbid"


def test_request_receipt_and_nested_field_order_matches_domain() -> None:
    assert tuple(BridgeRunStateRequestModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateRequest)
    )
    assert tuple(BridgeRunStateReceiptModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateReceipt)
    )
    assert tuple(BridgeRunStateMetricModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateMetric)
    )
    assert tuple(BridgeRunStateIdentitySeriesModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateIdentitySeries)
    )
    assert tuple(BridgeRunStateEnvelopeSeriesModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateEnvelopeSeries)
    )


def test_literals_are_frozen() -> None:
    assert get_args(BridgeRunStateRequestModel.model_fields["protocol_version"].annotation) == (
        "0.3-b4",
    )
    assert get_args(BridgeRunStateRequestModel.model_fields["run_status"].annotation) == (
        "completed",
        "stopped",
        "execution_error",
        "unknown",
    )
    assert get_args(BridgeRunStateReceiptModel.model_fields["status"].annotation) == ("persisted",)
    assert get_args(BridgeRunStateReceiptModel.model_fields["mode"].annotation) == (
        "durable_persisted",
    )
    assert get_args(
        BridgeRunStateIdentitySeriesModel.model_fields["representation"].annotation
    ) == ("identity_uniform_v1",)
    assert get_args(
        BridgeRunStateEnvelopeSeriesModel.model_fields["representation"].annotation
    ) == ("min_max_envelope_uniform_v1",)


def test_schema_aliases_are_base_models() -> None:
    assert issubclass(BridgeRunStateRequestModel, BaseModel)
    assert issubclass(BridgeRunStateReceiptModel, BaseModel)
    assert issubclass(BridgeRunStateMetricModel, BaseModel)
    assert issubclass(BridgeRunStateIdentitySeriesModel, BaseModel)
    assert issubclass(BridgeRunStateEnvelopeSeriesModel, BaseModel)


def test_domain_contract_does_not_import_pydantic() -> None:
    source = Path("core/domain/bridge_run_state.py").read_text(encoding="utf-8")

    assert "pydantic" not in source.lower()


def test_export_bridge_schemas_now_exports_eighteen_bridge_schemas() -> None:
    bridge_paths = [path for path in OUTPUTS if path.name.startswith("bridge_")]

    assert len(bridge_paths) == 18
    assert Path("schemas/bridge_run_state_request.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_receipt.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_auth_error_response.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_write_error.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_coaching_request.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_coaching_result.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_coaching_error.schema.json") in bridge_paths


def test_exported_run_state_schemas_do_not_drift() -> None:
    run_state_paths = {
        Path("schemas/bridge_run_state_request.schema.json"),
        Path("schemas/bridge_run_state_receipt.schema.json"),
        Path("schemas/bridge_run_state_auth_error_response.schema.json"),
        Path("schemas/bridge_run_state_write_error.schema.json"),
    }
    for path, model in OUTPUTS.items():
        if path not in run_state_paths:
            continue
        actual = json.loads(path.read_text(encoding="utf-8"))
        assert actual == model.model_json_schema()


def test_run_state_auth_error_model_is_isolated_from_transport_error_model() -> None:
    assert set(BridgeRunStateAuthErrorResponse.model_fields) == {"error", "message"}
    assert BridgeRunStateAuthErrorResponse.__name__ == "BridgeRunStateAuthErrorResponse"


def test_run_state_write_error_model_is_isolated_from_auth_error_model() -> None:
    assert tuple(BridgeRunStateWriteErrorResponseModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateWriteErrorResponseDomain)
    )
    assert BridgeRunStateWriteErrorResponseModel.__name__ == "BridgeRunStateWriteErrorResponse"
