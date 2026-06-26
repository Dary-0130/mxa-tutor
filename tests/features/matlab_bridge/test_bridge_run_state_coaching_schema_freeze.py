from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingAltDirection,
    BridgeRunStateCoachingEvidenceItem,
    BridgeRunStateCoachingLLMError,
    BridgeRunStateCoachingPrimaryDirection,
    BridgeRunStateCoachingRequest,
    BridgeRunStateCoachingResult,
    BridgeRunStateCoachingSignalReading,
)
from features.matlab_bridge.bridge_run_state_coaching_schemas import (
    AltDirectionModel,
    BridgeRunStateCoachingResultModel,
    CoachingLLMError,
    EvidenceItemModel,
    PrimaryDirectionModel,
    SignalReadingModel,
)
from features.matlab_bridge.bridge_run_state_coaching_schemas import (
    BridgeRunStateCoachingRequest as BridgeRunStateCoachingRequestModel,
)
from scripts.export_bridge_schemas import OUTPUTS


def test_top_level_model_names_are_frozen() -> None:
    assert [
        BridgeRunStateCoachingRequestModel.__name__,
        BridgeRunStateCoachingResultModel.__name__,
        CoachingLLMError.__name__,
        EvidenceItemModel.__name__,
        SignalReadingModel.__name__,
        PrimaryDirectionModel.__name__,
        AltDirectionModel.__name__,
    ] == [
        "BridgeRunStateCoachingRequest",
        "BridgeRunStateCoachingResultModel",
        "CoachingLLMError",
        "EvidenceItemModel",
        "SignalReadingModel",
        "PrimaryDirectionModel",
        "AltDirectionModel",
    ]


def test_extra_forbid_at_all_levels() -> None:
    for model in (
        BridgeRunStateCoachingRequestModel,
        BridgeRunStateCoachingResultModel,
        CoachingLLMError,
        EvidenceItemModel,
        SignalReadingModel,
        PrimaryDirectionModel,
        AltDirectionModel,
    ):
        assert model.model_config.get("extra") == "forbid"


def test_public_field_order_matches_domain() -> None:
    assert tuple(BridgeRunStateCoachingRequestModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingRequest)
    )
    assert tuple(BridgeRunStateCoachingResultModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingResult)
    )
    assert tuple(EvidenceItemModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingEvidenceItem)
    )
    assert tuple(SignalReadingModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingSignalReading)
    )
    assert tuple(PrimaryDirectionModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingPrimaryDirection)
    )
    assert tuple(AltDirectionModel.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingAltDirection)
    )
    assert tuple(CoachingLLMError.model_fields) == tuple(
        field.name for field in fields(BridgeRunStateCoachingLLMError)
    )


def test_literals_are_frozen() -> None:
    assert get_args(
        BridgeRunStateCoachingRequestModel.model_fields["protocol_version"].annotation
    ) == ("0.3-c1",)
    assert get_args(
        BridgeRunStateCoachingRequestModel.model_fields[
            "coaching_consent_notice_version"
        ].annotation
    ) == ("run_state_coaching_v1",)
    assert get_args(BridgeRunStateCoachingResultModel.model_fields["mode"].annotation) == (
        "run_state_coaching",
    )
    assert get_args(CoachingLLMError.model_fields["error"].annotation) == (
        "bridge_run_state_coaching_unavailable",
        "bridge_run_state_coaching_timeout",
        "bridge_run_state_coaching_failed",
        "bridge_run_state_coaching_busy",
    )


def test_schema_aliases_are_base_models() -> None:
    assert issubclass(BridgeRunStateCoachingRequestModel, BaseModel)
    assert issubclass(BridgeRunStateCoachingResultModel, BaseModel)
    assert issubclass(CoachingLLMError, BaseModel)


def test_domain_contract_does_not_import_pydantic_or_private_draft() -> None:
    source = Path("core/domain/bridge_run_state_coaching.py").read_text(encoding="utf-8")

    assert "pydantic" not in source.lower()
    assert "CoachingDraft" not in source
    assert "_run_state_coaching_draft" not in source


def test_export_bridge_schemas_now_exports_eighteen_bridge_schemas() -> None:
    bridge_paths = [path for path in OUTPUTS if path.name.startswith("bridge_")]

    assert len(bridge_paths) == 18
    assert Path("schemas/bridge_run_state_coaching_request.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_coaching_result.schema.json") in bridge_paths
    assert Path("schemas/bridge_run_state_coaching_error.schema.json") in bridge_paths
    assert not any("draft" in path.name for path in bridge_paths)


def test_exported_coaching_schemas_do_not_drift() -> None:
    coaching_paths = {
        Path("schemas/bridge_run_state_coaching_request.schema.json"),
        Path("schemas/bridge_run_state_coaching_result.schema.json"),
        Path("schemas/bridge_run_state_coaching_error.schema.json"),
    }
    for path, model in OUTPUTS.items():
        if path not in coaching_paths:
            continue
        actual = json.loads(path.read_text(encoding="utf-8"))
        assert actual == model.model_json_schema()
