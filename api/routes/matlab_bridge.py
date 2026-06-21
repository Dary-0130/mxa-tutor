"""MATLAB Add-on diagnostic bridge route."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import ip_address
from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.dependencies import get_matlab_bridge_diagnostic_service
from features.matlab_bridge.bridge_diagnostic_schemas import (
    BridgeDiagnosticReceiptModel,
    BridgeDiagnosticRequest,
    BridgeErrorResponse,
)

MAX_BRIDGE_BODY_BYTES = 32 * 1024


class BridgePayloadTooLargeError(Exception):
    """Raised once the actual request body exceeds the bridge limit."""


class MatlabBridgeRequest(Request):
    """Bridge-scoped request helpers used before FastAPI JSON/Pydantic parsing."""

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
        if hasattr(self, "_body"):
            return self._body  # type: ignore[attr-defined]

        chunks: list[bytes] = []
        total = 0
        async for chunk in self.stream():
            total += len(chunk)
            if total > max_bytes:
                raise BridgePayloadTooLargeError
            chunks.append(chunk)
        self._body = b"".join(chunks)  # type: ignore[attr-defined]
        return self._body  # type: ignore[attr-defined]


def _bridge_error(status_code: int, error: str, message: str) -> JSONResponse:
    payload = BridgeErrorResponse.model_validate({"error": error, "message": message})
    return JSONResponse(status_code=status_code, content=payload.model_dump())


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
                await bridge_request.body_with_limit(MAX_BRIDGE_BODY_BYTES)
            except BridgePayloadTooLargeError:
                return _bridge_error(
                    413,
                    "bridge_payload_too_large",
                    "诊断内容过大",
                )
            return await original_handler(bridge_request)

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
