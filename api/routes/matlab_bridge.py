"""MATLAB Add-on diagnostic bridge route."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import ip_address
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from loguru import logger
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive

from adapters.storage.sqlite_bridge_run_state_store import (
    BridgeRunStateScope,
    BridgeRunStateSessionRejectedError,
    BridgeRunStateStoreUnavailableError,
    SqliteBridgeRunStateStore,
)
from api.dependencies import (
    get_matlab_bridge_auth_service,
    get_matlab_bridge_diagnostic_service,
    get_matlab_bridge_explanation_service,
    get_matlab_bridge_run_state_coaching_service,
    get_matlab_bridge_run_state_service,
    get_matlab_bridge_run_state_store,
)
from core.domain.bridge_auth import (
    RUN_STATE_EXPLAIN_CAPABILITY,
    RUN_STATE_WRITE_CAPABILITY,
    BridgeAuthContext,
)
from core.domain.bridge_run_state import canonical_run_state_session_id
from core.domain.exceptions import BridgeRunStateValidationError
from core.interfaces.coaching_run_state_reader import (
    CoachingRunStateReaderUnavailableError,
    CoachingRunStateReadRejectedError,
)
from features.matlab_bridge.bridge_auth_service import (
    BridgeAuthForbiddenError,
    BridgeAuthRevocationStoreUnavailableError,
    BridgeAuthService,
    BridgeAuthTokenError,
)
from features.matlab_bridge.bridge_diagnostic_schemas import (
    BridgeDiagnosticReceiptModel,
    BridgeDiagnosticRequest,
    BridgeErrorResponse,
)
from features.matlab_bridge.bridge_explanation_schemas import (
    BridgeExplanationErrorResponse,
    BridgeExplanationRequest,
    BridgeExplanationResultModel,
)
from features.matlab_bridge.bridge_explanation_service import (
    BridgeExplanationService,
    bridge_explanation_error_payloads,
)
from features.matlab_bridge.bridge_run_state_coaching_schemas import (
    BridgeRunStateCoachingRequest,
    BridgeRunStateCoachingResultModel,
    CoachingLLMError,
)
from features.matlab_bridge.bridge_run_state_coaching_service import (
    BridgeRunStateCoachingBusyError,
    BridgeRunStateCoachingFailedError,
    BridgeRunStateCoachingService,
    BridgeRunStateCoachingTimeoutError,
    BridgeRunStateCoachingUnavailableError,
    coaching_error_payloads,
)
from features.matlab_bridge.bridge_run_state_schemas import (
    BridgeRunStateAuthErrorResponse,
    BridgeRunStateReceiptModel,
    BridgeRunStateRequest,
    BridgeRunStateWriteErrorResponse,
)
from features.matlab_bridge.bridge_run_state_service import (
    BridgeRunStateConflictError,
    BridgeRunStateInternalError,
    BridgeRunStateService,
)

MAX_BRIDGE_BODY_BYTES = 32 * 1024
MAX_BRIDGE_BEARER_BYTES = 8192
BRIDGE_RUN_STATE_PATH = "/api/v1/bridge/run-state"
BRIDGE_RUN_STATE_COACHING_PATH = "/api/v1/bridge/run-state/coaching"
BRIDGE_RUN_STATE_SECURITY_SCHEME = "BridgeRunStateBearerAuth"
_BRIDGE_AUTH_DENIED_MESSAGE = "bridge auth request denied"


class BridgePayloadTooLargeError(Exception):
    """Raised once the actual request body exceeds the bridge limit."""


class MatlabBridgeRequest(Request):
    """Bridge-scoped request helpers used before FastAPI JSON/Pydantic parsing."""

    _bridge_body: bytes

    def is_loopback_client(self) -> bool:
        if self.client is None or self.client.host is None:
            return False
        try:
            return ip_address(self.client.host).is_loopback
        except ValueError:
            return False

    def media_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    async def body_with_limit(self, max_bytes: int) -> bytes:
        if hasattr(self, "_bridge_body"):
            return self._bridge_body

        chunks: list[bytes] = []
        total = 0
        async for chunk in self.stream():
            total += len(chunk)
            if total > max_bytes:
                raise BridgePayloadTooLargeError
            chunks.append(chunk)
        self._bridge_body = b"".join(chunks)
        return self._bridge_body


def _bridge_error(status_code: int, error: str, message: str) -> JSONResponse:
    payload = BridgeErrorResponse.model_validate({"error": error, "message": message})
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _bridge_validation_error(request: Request) -> JSONResponse:
    logger.error(
        "API error: exception={} status={} path={} method={}",
        "RequestValidationError",
        422,
        request.url.path,
        request.method,
    )
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": "请求参数有问题,请检查后重试"},
    )


def _bridge_auth_error(status_code: int, error: str, status: str) -> JSONResponse:
    logger.info(
        "Bridge run-state auth rejected: event_code={} status={}",
        "bridge_run_state_auth",
        status,
    )
    payload = BridgeRunStateAuthErrorResponse.model_validate(
        {"error": error, "message": _BRIDGE_AUTH_DENIED_MESSAGE}
    )
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content=payload.model_dump(), headers=headers)


def _bridge_coaching_error(status_code: int, error: str, message: str) -> JSONResponse:
    logger.info(
        "Bridge run-state coaching rejected: event_code={} status={}",
        "bridge_run_state_coaching",
        error,
    )
    payload = CoachingLLMError.model_validate({"error": error, "message": message})
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _bridge_run_state_write_error(status_code: int, error: str, status: str) -> JSONResponse:
    logger.info(
        "Bridge run-state write rejected: event_code={} status={}",
        "bridge_run_state_write",
        status,
    )
    payload = BridgeRunStateWriteErrorResponse.model_validate(
        {"error": error, "message": "bridge run-state write failed"}
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _run_state_scope(auth_context: BridgeAuthContext) -> BridgeRunStateScope:
    return BridgeRunStateScope(
        user_id=auth_context.user_id,
        project_id=auth_context.project_id,
        session_id=auth_context.session_id,
        process_generation=auth_context.claims.process_generation,
    )


def _map_session_rejection(exc: BridgeRunStateSessionRejectedError) -> JSONResponse:
    if exc.reason in {"invalid_scope", "scope_mismatch"}:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")
    return _bridge_run_state_write_error(
        410,
        "bridge_run_state_session_unavailable",
        "session_unavailable",
    )


def _map_coaching_read_rejection(exc: CoachingRunStateReadRejectedError) -> JSONResponse:
    if exc.reason in {"invalid_scope", "scope_mismatch"}:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")
    return _bridge_run_state_write_error(
        410,
        "bridge_run_state_session_unavailable",
        "session_unavailable",
    )


def _map_store_unavailable(exc: BridgeRunStateStoreUnavailableError) -> JSONResponse:
    if str(exc) in {"current_run_missing"}:
        return _bridge_run_state_write_error(
            500,
            "bridge_run_state_internal_error",
            "invariant_failed",
        )
    return _bridge_run_state_write_error(
        503,
        "bridge_run_state_store_unavailable",
        "store_unavailable",
    )


def _replay_receive(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _extract_bearer_token(request: Request) -> str:
    values = [
        value
        for name, value in request.scope.get("headers", [])
        if name.lower() == b"authorization"
    ]
    if len(values) != 1:
        raise BridgeAuthTokenError("invalid_authorization")
    try:
        header_value = values[0].decode("ascii")
    except UnicodeDecodeError:
        raise BridgeAuthTokenError("invalid_authorization") from None
    if "," in header_value:
        raise BridgeAuthTokenError("invalid_authorization")
    parts = header_value.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
        raise BridgeAuthTokenError("invalid_authorization")
    token = parts[1]
    try:
        token_size = len(token.encode("ascii"))
    except UnicodeEncodeError:
        raise BridgeAuthTokenError("invalid_authorization") from None
    if token_size > MAX_BRIDGE_BEARER_BYTES:
        raise BridgeAuthTokenError("invalid_authorization")
    return token


def _get_auth_service(request: Request) -> BridgeAuthService:
    overrides = getattr(request.app, "dependency_overrides", {})
    override = overrides.get(get_matlab_bridge_auth_service)
    if override is not None:
        return cast(BridgeAuthService, override())
    return get_matlab_bridge_auth_service()


def _verify_run_state_request(request: Request, body: bytes) -> JSONResponse | None:
    try:
        run_state_request = BridgeRunStateRequest.model_validate_json(body)
    except ValidationError:
        return _bridge_validation_error(request)

    try:
        token = _extract_bearer_token(request)
        auth_context = _get_auth_service(request).verify_token(
            token,
            required_capability=RUN_STATE_WRITE_CAPABILITY,
        )
    except BridgeAuthRevocationStoreUnavailableError:
        return _bridge_auth_error(503, "bridge_auth_unavailable", "unavailable")
    except BridgeAuthForbiddenError:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "forbidden")
    except BridgeAuthTokenError:
        return _bridge_auth_error(401, "bridge_auth_invalid_token", "denied")

    try:
        body_session_id = canonical_run_state_session_id(run_state_request.session_id)
        token_session_id = canonical_run_state_session_id(auth_context.session_id)
    except ValueError:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")
    if body_session_id != token_session_id:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")

    request.state.bridge_run_state_request = run_state_request
    request.state.bridge_auth_context = auth_context
    return None


def _verify_run_state_coaching_request(request: Request, body: bytes) -> JSONResponse | None:
    try:
        coaching_request = BridgeRunStateCoachingRequest.model_validate_json(body)
    except ValidationError:
        return _bridge_validation_error(request)

    try:
        token = _extract_bearer_token(request)
        auth_context = _get_auth_service(request).verify_token(
            token,
            required_capability=RUN_STATE_EXPLAIN_CAPABILITY,
        )
    except BridgeAuthRevocationStoreUnavailableError:
        return _bridge_auth_error(503, "bridge_auth_unavailable", "unavailable")
    except BridgeAuthForbiddenError:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "forbidden")
    except BridgeAuthTokenError:
        return _bridge_auth_error(401, "bridge_auth_invalid_token", "denied")

    try:
        body_session_id = canonical_run_state_session_id(coaching_request.session_id)
        token_session_id = canonical_run_state_session_id(auth_context.session_id)
    except ValueError:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")
    if body_session_id != token_session_id:
        return _bridge_auth_error(403, "bridge_auth_forbidden", "scope_mismatch")

    request.state.bridge_run_state_coaching_request = coaching_request
    request.state.bridge_auth_context = auth_context
    return None


class MatlabBridgeRoute(APIRoute):
    """Apply bridge-only guards before FastAPI reads JSON or validates Pydantic."""

    def get_route_handler(self) -> Callable[[Request], Any]:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            bridge_request = MatlabBridgeRequest(request.scope, request.receive)
            if not bridge_request.is_loopback_client():
                return _bridge_error(
                    403,
                    "matlab_bridge_forbidden",
                    "仅允许本机 MATLAB Add-on 访问",
                )
            if bridge_request.media_type() != "application/json":
                return _bridge_error(
                    415,
                    "bridge_unsupported_media_type",
                    "仅支持 application/json",
                )
            try:
                body = await bridge_request.body_with_limit(MAX_BRIDGE_BODY_BYTES)
            except BridgePayloadTooLargeError:
                return _bridge_error(
                    413,
                    "bridge_payload_too_large",
                    "诊断内容过大",
                )
            replay_request = MatlabBridgeRequest(request.scope, _replay_receive(body))
            if replay_request.scope.get("path") == BRIDGE_RUN_STATE_PATH:
                auth_response = _verify_run_state_request(replay_request, body)
                if auth_response is not None:
                    return auth_response
            if replay_request.scope.get("path") == BRIDGE_RUN_STATE_COACHING_PATH:
                auth_response = _verify_run_state_coaching_request(replay_request, body)
                if auth_response is not None:
                    return auth_response
            return await original_handler(replay_request)

        return handler


def install_matlab_bridge_openapi(app: FastAPI) -> None:
    """Add route-wrapper auth OpenAPI metadata that has no FastAPI dependency hook."""
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return cast(dict[str, Any], app.openapi_schema)
        schema = cast(dict[str, Any], original_openapi())
        components = schema.setdefault("components", {})
        component_schemas = components.setdefault("schemas", {})
        component_schemas.setdefault(
            "BridgeRunStateRequest",
            BridgeRunStateRequest.model_json_schema(ref_template="#/components/schemas/{model}"),
        )
        component_schemas.setdefault(
            "BridgeRunStateCoachingRequest",
            BridgeRunStateCoachingRequest.model_json_schema(
                ref_template="#/components/schemas/{model}"
            ),
        )
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes[BRIDGE_RUN_STATE_SECURITY_SCHEME] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


router = APIRouter(tags=["matlab-bridge"], route_class=MatlabBridgeRoute)


@router.post(
    "/api/v1/bridge/diagnostic",
    response_model=BridgeDiagnosticReceiptModel,
    responses={
        403: {"model": BridgeErrorResponse},
        413: {"model": BridgeErrorResponse},
        415: {"model": BridgeErrorResponse},
        422: {
            "description": "Global validation error shape",
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "请求参数有问题,请检查后重试",
                    }
                }
            },
        },
    },
)
async def bridge_diagnostic(
    request_body: BridgeDiagnosticRequest,
) -> BridgeDiagnosticReceiptModel:
    """Receive one user-confirmed manual_error diagnostic and return a fixed stub."""
    service = get_matlab_bridge_diagnostic_service()
    receipt = service.consume(request_body.to_domain())
    return BridgeDiagnosticReceiptModel.from_domain(receipt)


@router.post(
    "/api/v1/bridge/explanation",
    response_model=BridgeExplanationResultModel,
    responses={
        403: {"model": BridgeErrorResponse},
        413: {"model": BridgeErrorResponse},
        415: {"model": BridgeErrorResponse},
        422: {
            "description": "Global validation error shape",
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "请求参数有问题,请检查后重试",
                    }
                }
            },
        },
        502: {
            "model": BridgeExplanationErrorResponse,
            "content": {
                "application/json": {"example": bridge_explanation_error_payloads()[502]},
            },
        },
        503: {
            "model": BridgeExplanationErrorResponse,
            "content": {
                "application/json": {"example": bridge_explanation_error_payloads()[503]},
            },
        },
        504: {
            "model": BridgeExplanationErrorResponse,
            "content": {
                "application/json": {"example": bridge_explanation_error_payloads()[504]},
            },
        },
    },
)
async def bridge_explanation(
    request_body: BridgeExplanationRequest,
    service: Annotated[
        BridgeExplanationService,
        Depends(get_matlab_bridge_explanation_service),
    ],
) -> BridgeExplanationResultModel:
    """Explain one user-confirmed MATLAB bridge error diagnostic."""
    result = await service.explain(request_body.to_domain())
    return BridgeExplanationResultModel.from_domain(result)


@router.post(
    BRIDGE_RUN_STATE_PATH,
    response_model=BridgeRunStateReceiptModel,
    responses={
        401: {
            "model": BridgeRunStateAuthErrorResponse,
            "headers": {
                "WWW-Authenticate": {
                    "description": "Bearer challenge",
                    "schema": {"type": "string"},
                }
            },
        },
        403: {
            "description": "Loopback guard or run-state auth scope denied",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/BridgeErrorResponse"},
                            {"$ref": "#/components/schemas/" "BridgeRunStateAuthErrorResponse"},
                        ]
                    }
                }
            },
        },
        413: {"model": BridgeErrorResponse},
        415: {"model": BridgeErrorResponse},
        422: {
            "description": "Global validation error shape",
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "请求参数有问题,请检查后重试",
                    }
                }
            },
        },
        409: {"model": BridgeRunStateWriteErrorResponse},
        410: {"model": BridgeRunStateWriteErrorResponse},
        500: {"model": BridgeRunStateWriteErrorResponse},
        503: {
            "description": "Auth revocation store or durable run-state write unavailable",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/BridgeRunStateAuthErrorResponse"},
                            {"$ref": "#/components/schemas/BridgeRunStateWriteErrorResponse"},
                        ]
                    }
                }
            },
        },
    },
    openapi_extra={
        "security": [{BRIDGE_RUN_STATE_SECURITY_SCHEME: []}],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/BridgeRunStateRequest"}
                }
            },
        },
    },
)
async def bridge_run_state(
    request: Request,
    service: Annotated[
        BridgeRunStateService,
        Depends(get_matlab_bridge_run_state_service),
    ],
    store: Annotated[
        SqliteBridgeRunStateStore,
        Depends(get_matlab_bridge_run_state_store),
    ],
) -> BridgeRunStateReceiptModel | JSONResponse:
    """Persist one user-confirmed run-state snapshot."""
    request_body = cast(BridgeRunStateRequest, request.state.bridge_run_state_request)
    auth_context = cast(BridgeAuthContext, request.state.bridge_auth_context)
    scope = _run_state_scope(auth_context)
    try:
        receipt = await service.consume(
            request_body.to_domain(),
            auth_context,
            store=store,
            scope=scope,
        )
    except BridgeRunStateConflictError:
        return _bridge_run_state_write_error(
            409,
            "bridge_run_state_conflict",
            "conflict",
        )
    except BridgeRunStateSessionRejectedError as exc:
        return _map_session_rejection(exc)
    except BridgeRunStateStoreUnavailableError as exc:
        return _map_store_unavailable(exc)
    except BridgeRunStateValidationError:
        return _bridge_run_state_write_error(
            500,
            "bridge_run_state_internal_error",
            "invariant_failed",
        )
    except BridgeRunStateInternalError:
        return _bridge_run_state_write_error(
            500,
            "bridge_run_state_internal_error",
            "invariant_failed",
        )
    return BridgeRunStateReceiptModel.from_domain(receipt)


@router.post(
    BRIDGE_RUN_STATE_COACHING_PATH,
    response_model=BridgeRunStateCoachingResultModel,
    responses={
        401: {
            "model": BridgeRunStateAuthErrorResponse,
            "headers": {
                "WWW-Authenticate": {
                    "description": "Bearer challenge",
                    "schema": {"type": "string"},
                }
            },
        },
        403: {
            "description": "Loopback guard or run-state auth scope denied",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/BridgeErrorResponse"},
                            {"$ref": "#/components/schemas/" "BridgeRunStateAuthErrorResponse"},
                        ]
                    }
                }
            },
        },
        410: {"model": BridgeRunStateWriteErrorResponse},
        413: {"model": BridgeErrorResponse},
        415: {"model": BridgeErrorResponse},
        422: {
            "description": "Global validation error shape",
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "请求参数有问题,请检查后重试",
                    }
                }
            },
        },
        429: {
            "model": CoachingLLMError,
            "content": {"application/json": {"example": coaching_error_payloads()[429]}},
        },
        500: {"model": BridgeRunStateWriteErrorResponse},
        502: {
            "model": CoachingLLMError,
            "content": {"application/json": {"example": coaching_error_payloads()[502]}},
        },
        503: {
            "description": "Auth, store, or coaching provider unavailable",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/BridgeRunStateAuthErrorResponse"},
                            {"$ref": "#/components/schemas/BridgeRunStateWriteErrorResponse"},
                            {"$ref": "#/components/schemas/CoachingLLMError"},
                        ]
                    }
                }
            },
        },
        504: {
            "model": CoachingLLMError,
            "content": {"application/json": {"example": coaching_error_payloads()[504]}},
        },
    },
    openapi_extra={
        "security": [{BRIDGE_RUN_STATE_SECURITY_SCHEME: []}],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/BridgeRunStateCoachingRequest"}
                }
            },
        },
    },
)
async def bridge_run_state_coaching(
    request: Request,
    service: Annotated[
        BridgeRunStateCoachingService,
        Depends(get_matlab_bridge_run_state_coaching_service),
    ],
    store: Annotated[
        SqliteBridgeRunStateStore,
        Depends(get_matlab_bridge_run_state_store),
    ],
) -> BridgeRunStateCoachingResultModel | JSONResponse:
    """Generate one coaching explanation from persisted run-state context."""
    request_body = cast(
        BridgeRunStateCoachingRequest,
        request.state.bridge_run_state_coaching_request,
    )
    auth_context = cast(BridgeAuthContext, request.state.bridge_auth_context)
    try:
        result = await service.coach(
            request_body.to_domain(),
            auth_context,
            reader=store,
        )
    except CoachingRunStateReadRejectedError as exc:
        return _map_coaching_read_rejection(exc)
    except CoachingRunStateReaderUnavailableError:
        return _bridge_run_state_write_error(
            503,
            "bridge_run_state_store_unavailable",
            "store_unavailable",
        )
    except BridgeRunStateCoachingBusyError:
        payload = coaching_error_payloads()[429]
        return _bridge_coaching_error(429, payload["error"], payload["message"])
    except BridgeRunStateCoachingUnavailableError:
        payload = coaching_error_payloads()[503]
        return _bridge_coaching_error(503, payload["error"], payload["message"])
    except BridgeRunStateCoachingTimeoutError:
        payload = coaching_error_payloads()[504]
        return _bridge_coaching_error(504, payload["error"], payload["message"])
    except BridgeRunStateCoachingFailedError:
        payload = coaching_error_payloads()[502]
        return _bridge_coaching_error(502, payload["error"], payload["message"])
    return BridgeRunStateCoachingResultModel.from_domain(result)
