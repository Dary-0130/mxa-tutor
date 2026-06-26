"""Pydantic schemas for hidden MATLAB bridge dev/test auth control plane."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

BridgeDevAuthCapability = Literal["run_state:write", "run_state:explain"]
BridgeDevAuthStatus = Literal["issued", "revoked"]
BridgeDevAuthTokenType = Literal["Bearer"]

_BridgeAuthIdentifier = Annotated[str, StringConstraints(min_length=1, max_length=128)]
_BridgeAuthBearer = Annotated[str, StringConstraints(min_length=1, max_length=8192)]


class _BridgeAuthBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BridgeDevAuthTokenRequest(_BridgeAuthBaseModel):
    user_id: _BridgeAuthIdentifier
    project_id: _BridgeAuthIdentifier
    session_id: _BridgeAuthIdentifier
    capabilities: tuple[BridgeDevAuthCapability, ...] = ("run_state:write",)


class BridgeDevAuthTokenResponse(_BridgeAuthBaseModel):
    status: BridgeDevAuthStatus
    access_token: _BridgeAuthBearer
    token_type: BridgeDevAuthTokenType
    expires_at: datetime
    expires_in_seconds: Annotated[int, Field(ge=1, le=3600)]


class BridgeDevAuthRevokeRequest(_BridgeAuthBaseModel):
    access_token: _BridgeAuthBearer


class BridgeDevAuthRevokeResponse(_BridgeAuthBaseModel):
    status: BridgeDevAuthStatus


class BridgeDevAuthErrorResponse(_BridgeAuthBaseModel):
    error: Literal[
        "bridge_auth_forbidden",
        "bridge_auth_invalid_token",
        "bridge_auth_unavailable",
    ]
    message: str
