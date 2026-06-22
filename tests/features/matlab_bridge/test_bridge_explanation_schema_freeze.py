from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from core.domain.bridge_explanation import BridgeExplanationRequest, BridgeExplanationResult
from features.matlab_bridge.bridge_explanation_schemas import (
    BridgeExplanationErrorResponse,
    BridgeExplanationResultModel,
    LikelyCauseModel,
    NextStepModel,
)
from features.matlab_bridge.bridge_explanation_schemas import (
    BridgeExplanationRequest as BridgeExplanationRequestModel,
)
from scripts.export_bridge_schemas import OUTPUTS


def test_top_level_model_names_are_frozen() -> None:
    assert [
        BridgeExplanationRequestModel.__name__,
        BridgeExplanationResultModel.__name__,
        BridgeExplanationErrorResponse.__name__,
    ] == [
        "BridgeExplanationRequest",
        "BridgeExplanationResultModel",
        "BridgeExplanationErrorResponse",
    ]


def test_extra_forbid_at_all_levels() -> None:
    for model in (
        BridgeExplanationRequestModel,
        BridgeExplanationResultModel,
        BridgeExplanationErrorResponse,
        LikelyCauseModel,
        NextStepModel,
    ):
        assert model.model_config.get("extra") == "forbid"


def test_request_and_result_field_order_matches_domain() -> None:
    assert tuple(BridgeExplanationRequestModel.model_fields) == tuple(
        field.name for field in fields(BridgeExplanationRequest)
    )
    assert tuple(BridgeExplanationResultModel.model_fields) == tuple(
        field.name for field in fields(BridgeExplanationResult)
    )


def test_nested_and_error_field_order_is_frozen() -> None:
    assert tuple(LikelyCauseModel.model_fields) == (
        "cause",
        "is_inference",
        "confidence",
        "supporting_signals",
    )
    assert tuple(NextStepModel.model_fields) == ("action",)
    assert tuple(BridgeExplanationErrorResponse.model_fields) == ("error", "message")


def test_literals_are_frozen() -> None:
    assert get_args(BridgeExplanationRequestModel.model_fields["protocol_version"].annotation) == (
        "0.3-b1",
    )
    assert get_args(BridgeExplanationRequestModel.model_fields["diagnostic_kind"].annotation) == (
        "manual_error",
    )
    assert get_args(BridgeExplanationResultModel.model_fields["status"].annotation) == (
        "completed",
    )
    assert get_args(BridgeExplanationResultModel.model_fields["mode"].annotation) == (
        "llm_error_explanation",
    )
    assert get_args(LikelyCauseModel.model_fields["confidence"].annotation) == ("low", "medium")
    assert get_args(BridgeExplanationErrorResponse.model_fields["error"].annotation) == (
        "bridge_explanation_failed",
        "bridge_explanation_unavailable",
        "bridge_explanation_timeout",
    )


def test_schema_aliases_are_base_models() -> None:
    assert issubclass(BridgeExplanationRequestModel, BaseModel)
    assert issubclass(BridgeExplanationResultModel, BaseModel)
    assert issubclass(BridgeExplanationErrorResponse, BaseModel)


def test_domain_contract_does_not_import_pydantic() -> None:
    source = Path("core/domain/bridge_explanation.py").read_text(encoding="utf-8")

    assert "pydantic" not in source.lower()


def test_exported_bridge_schemas_do_not_drift() -> None:
    explanation_paths = {
        Path("schemas/bridge_explanation_request.schema.json"),
        Path("schemas/bridge_explanation_result.schema.json"),
        Path("schemas/bridge_explanation_error.schema.json"),
    }
    for path, model in OUTPUTS.items():
        if path not in explanation_paths:
            continue
        actual = json.loads(path.read_text(encoding="utf-8"))
        assert actual == model.model_json_schema()
