from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from features.matlab_bridge.bridge_auth_schemas import (
    BridgeDevAuthErrorResponse,
    BridgeDevAuthRevokeRequest,
    BridgeDevAuthRevokeResponse,
    BridgeDevAuthTokenRequest,
    BridgeDevAuthTokenResponse,
)
from scripts.export_bridge_schemas import OUTPUTS


def test_dev_auth_schema_model_names_are_frozen() -> None:
    assert [
        BridgeDevAuthTokenRequest.__name__,
        BridgeDevAuthTokenResponse.__name__,
        BridgeDevAuthRevokeRequest.__name__,
        BridgeDevAuthRevokeResponse.__name__,
        BridgeDevAuthErrorResponse.__name__,
    ] == [
        "BridgeDevAuthTokenRequest",
        "BridgeDevAuthTokenResponse",
        "BridgeDevAuthRevokeRequest",
        "BridgeDevAuthRevokeResponse",
        "BridgeDevAuthErrorResponse",
    ]


def test_dev_auth_schema_extra_forbid_at_all_levels() -> None:
    for model in (
        BridgeDevAuthTokenRequest,
        BridgeDevAuthTokenResponse,
        BridgeDevAuthRevokeRequest,
        BridgeDevAuthRevokeResponse,
        BridgeDevAuthErrorResponse,
    ):
        assert model.model_config.get("extra") == "forbid"


def test_dev_auth_token_request_round_trip_and_capability_allowlist() -> None:
    payload = {
        "user_id": "user-alpha",
        "project_id": "project-alpha",
        "session_id": "11111111-1111-4111-8111-111111111111",
        "capabilities": ["run_state:write"],
    }

    request = BridgeDevAuthTokenRequest.model_validate(payload)

    assert request.model_dump(mode="json") == {
        **payload,
        "capabilities": ["run_state:write"],
    }
    explain_request = BridgeDevAuthTokenRequest.model_validate(
        {**payload, "capabilities": ["run_state:explain"]}
    )
    assert explain_request.capabilities == ("run_state:explain",)
    with pytest.raises(ValidationError):
        BridgeDevAuthTokenRequest.model_validate({**payload, "capabilities": ["run_state:read"]})


def test_dev_auth_revoke_request_round_trip() -> None:
    request = BridgeDevAuthRevokeRequest.model_validate({"access_token": "header.payload.sig"})

    assert request.model_dump(mode="json") == {"access_token": "header.payload.sig"}


def test_exported_dev_auth_schemas_do_not_drift() -> None:
    dev_auth_paths = {
        Path("schemas/bridge_dev_auth_token_request.schema.json"),
        Path("schemas/bridge_dev_auth_token_response.schema.json"),
        Path("schemas/bridge_dev_auth_revoke_request.schema.json"),
        Path("schemas/bridge_dev_auth_revoke_response.schema.json"),
        Path("schemas/bridge_dev_auth_error_response.schema.json"),
    }
    for path, model in OUTPUTS.items():
        if path not in dev_auth_paths:
            continue
        actual = json.loads(path.read_text(encoding="utf-8"))
        assert actual == model.model_json_schema()
