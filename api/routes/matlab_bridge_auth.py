"""Hidden dev/test control plane for MATLAB bridge auth tokens."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from starlette.responses import JSONResponse

from adapters.storage.sqlite_bridge_run_state_store import (
    BridgeRunStateScope,
    BridgeRunStateSessionRejectedError,
    BridgeRunStateStoreUnavailableError,
    SqliteBridgeRunStateStore,
)
from api.dependencies import (
    get_matlab_bridge_auth_service,
    get_matlab_bridge_run_state_store,
    get_settings,
)
from app.config import AppSettings
from features.matlab_bridge.bridge_auth_schemas import (
    BridgeDevAuthErrorResponse,
    BridgeDevAuthRevokeRequest,
    BridgeDevAuthRevokeResponse,
    BridgeDevAuthTokenRequest,
    BridgeDevAuthTokenResponse,
)
from features.matlab_bridge.bridge_auth_service import (
    BridgeAuthForbiddenError,
    BridgeAuthRevocationStoreUnavailableError,
    BridgeAuthService,
    BridgeAuthTokenError,
)

router = APIRouter(tags=["matlab-bridge-dev-auth"], include_in_schema=False)


def _auth_error(status_code: int, error: str) -> JSONResponse:
    payload = BridgeDevAuthErrorResponse.model_validate(
        {"error": error, "message": "bridge auth request denied"}
    )
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content=payload.model_dump(), headers=headers)


def _bootstrap_allowed(
    settings: AppSettings,
    bootstrap_token: str | None,
) -> bool:
    expected = settings.matlab_bridge_dev_auth_bootstrap_token
    return bool(expected and bootstrap_token and bootstrap_token == expected)


@router.post("/api/v1/bridge/dev-auth/token", response_model=BridgeDevAuthTokenResponse)
async def issue_dev_bridge_token(
    request_body: BridgeDevAuthTokenRequest,
    settings: Annotated[AppSettings, Depends(get_settings)],
    service: Annotated[BridgeAuthService, Depends(get_matlab_bridge_auth_service)],
    run_state_store: Annotated[
        SqliteBridgeRunStateStore,
        Depends(get_matlab_bridge_run_state_store),
    ],
    bootstrap_token: Annotated[str | None, Header(alias="X-MXA-Bridge-Dev-Bootstrap")] = None,
) -> BridgeDevAuthTokenResponse | JSONResponse:
    if not _bootstrap_allowed(settings, bootstrap_token):
        return _auth_error(403, "bridge_auth_forbidden")
    try:
        await run_state_store.establish_session(
            BridgeRunStateScope(
                user_id=request_body.user_id,
                project_id=request_body.project_id,
                session_id=request_body.session_id,
                process_generation=service.process_generation,
            )
        )
        issued = service.issue_token(
            user_id=request_body.user_id,
            project_id=request_body.project_id,
            session_id=request_body.session_id,
            capabilities=request_body.capabilities,
        )
    except BridgeRunStateStoreUnavailableError:
        return _auth_error(503, "bridge_auth_unavailable")
    except BridgeRunStateSessionRejectedError:
        return _auth_error(403, "bridge_auth_forbidden")
    except BridgeAuthForbiddenError:
        return _auth_error(403, "bridge_auth_forbidden")
    except BridgeAuthTokenError:
        return _auth_error(401, "bridge_auth_invalid_token")
    return BridgeDevAuthTokenResponse(
        status="issued",
        access_token=issued.access_token,
        token_type="Bearer",
        expires_at=issued.expires_at,
        expires_in_seconds=issued.expires_in_seconds,
    )


@router.post("/api/v1/bridge/dev-auth/revoke", response_model=BridgeDevAuthRevokeResponse)
async def revoke_dev_bridge_token(
    request_body: BridgeDevAuthRevokeRequest,
    settings: Annotated[AppSettings, Depends(get_settings)],
    service: Annotated[BridgeAuthService, Depends(get_matlab_bridge_auth_service)],
    bootstrap_token: Annotated[str | None, Header(alias="X-MXA-Bridge-Dev-Bootstrap")] = None,
) -> BridgeDevAuthRevokeResponse | JSONResponse:
    if not _bootstrap_allowed(settings, bootstrap_token):
        return _auth_error(403, "bridge_auth_forbidden")
    try:
        service.revoke_token(request_body.access_token)
    except BridgeAuthRevocationStoreUnavailableError:
        return _auth_error(503, "bridge_auth_unavailable")
    except BridgeAuthForbiddenError:
        return _auth_error(403, "bridge_auth_forbidden")
    except BridgeAuthTokenError:
        return _auth_error(401, "bridge_auth_invalid_token")
    return BridgeDevAuthRevokeResponse(status="revoked")
