"""MATLAB Add-on diagnostic bridge route."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import ip_address
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive

from api.dependencies import (
    get_matlab_bridge_diagnostic_service,
    get_matlab_bridge_explanation_service,
    get_matlab_bridge_run_state_service,
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
from features.matlab_bridge.bridge_run_state_schemas import (
    BridgeRunStateReceiptModel,
    BridgeRunStateRequest,
)
from features.matlab_bridge.bridge_run_state_service import BridgeRunStateService

MAX_BRIDGE_BODY_BYTES = 32 * 1024


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


def _replay_receive(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


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
            return await original_handler(replay_request)

        return handler


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
    "/api/v1/bridge/run-state",
    response_model=BridgeRunStateReceiptModel,
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
async def bridge_run_state(
    request_body: BridgeRunStateRequest,
    service: Annotated[
        BridgeRunStateService,
        Depends(get_matlab_bridge_run_state_service),
    ],
) -> BridgeRunStateReceiptModel:
    """Validate one user-confirmed run-state snapshot without persistence."""
    receipt = service.consume(request_body.to_domain())
    return BridgeRunStateReceiptModel.from_domain(receipt)
