from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import get_settings
from api.routes.matlab_bridge import (
    MAX_BRIDGE_BODY_BYTES,
    BridgePayloadTooLargeError,
    MatlabBridgeRequest,
)

BRIDGE_PATH = "/api/v1/bridge/diagnostic"
REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SECRET = "SECRET_BRIDGE_SENTINEL"


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-a",
        "request_id": REQUEST_ID,
        "diagnostic_kind": "manual_error",
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "error_text": "Error using foo",
        "consent_confirmed": True,
    }
    payload.update(overrides)
    return payload


def _configure_bridge_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    enabled: bool,
    app_env: str | None = "test",
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "mxa.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true" if enabled else "false")
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    get_settings.cache_clear()


def _create_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: Any):
    _configure_bridge_env(monkeypatch, tmp_path, **env)
    from api.main import create_app

    return create_app()


async def _request_async(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    transport = httpx.ASGITransport(app=app, client=(host, 49152))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _request(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    return asyncio.run(_request_async(app, method, path, host=host, **kwargs))


def test_bridge_path_not_registered_when_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=False, app_env="test")

    response = _request(app, "POST", BRIDGE_PATH, json=_valid_payload())

    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "请求的资源不存在"}


def test_valid_request_returns_fixed_connectivity_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", BRIDGE_PATH, json=_valid_payload(error_text=SECRET))

    assert response.status_code == 200
    assert response.json() == {
        "request_id": REQUEST_ID,
        "status": "received",
        "mode": "connectivity_stub",
        "message": "连接成功。本版本仅验证诊断信息传输,不提供报错解释。",
    }
    assert SECRET not in response.text


@pytest.mark.parametrize("app_env", [None, "production"])
def test_enabled_bridge_fails_closed_outside_dev_and_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str | None,
) -> None:
    with pytest.raises(RuntimeError, match="APP_ENV=development or APP_ENV=test"):
        _create_app(monkeypatch, tmp_path, enabled=True, app_env=app_env)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_enabled_bridge_starts_in_dev_and_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env=app_env)

    assert BRIDGE_PATH in {getattr(route, "path", "") for route in app.routes}


@pytest.mark.parametrize("app_env", [None, "production", "development", "test"])
def test_disabled_bridge_starts_in_any_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str | None,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=False, app_env=app_env)

    assert BRIDGE_PATH not in {getattr(route, "path", "") for route in app.routes}


def test_non_loopback_client_returns_bridge_403(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", BRIDGE_PATH, host="8.8.8.8", json=_valid_payload())

    assert response.status_code == 403
    assert response.json() == {
        "error": "matlab_bridge_forbidden",
        "message": "仅允许本机 MATLAB Add-on 访问",
    }


def test_unparseable_client_host_returns_bridge_403(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", BRIDGE_PATH, host="not-an-ip", json=_valid_payload())

    assert response.status_code == 403
    assert response.json() == {
        "error": "matlab_bridge_forbidden",
        "message": "仅允许本机 MATLAB Add-on 访问",
    }


def test_content_type_guard_returns_415_before_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        BRIDGE_PATH,
        content=f"not-json {SECRET}",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 415
    assert response.json() == {
        "error": "bridge_unsupported_media_type",
        "message": "仅支持 application/json",
    }
    assert SECRET not in response.text


def test_content_type_allows_json_with_charset_and_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        BRIDGE_PATH,
        content=json.dumps(_valid_payload()),
        headers={"content-type": "Application/JSON; charset=utf-8"},
    )

    assert response.status_code == 200


def test_body_limiter_counts_actual_bytes_before_json_and_pydantic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    base = json.dumps(_valid_payload(), separators=(",", ":")).encode()
    assert len(base) < 32768
    exactly_limit = base + (b" " * (32768 - len(base)))
    over_limit = exactly_limit + b" "

    ok = _request(
        app,
        "POST",
        BRIDGE_PATH,
        content=exactly_limit,
        headers={"content-type": "application/json", "content-length": "1"},
    )
    too_large = _request(
        app,
        "POST",
        BRIDGE_PATH,
        content=over_limit,
        headers={"content-type": "application/json", "content-length": "1"},
    )

    assert ok.status_code == 200
    assert too_large.status_code == 413
    assert too_large.json() == {
        "error": "bridge_payload_too_large",
        "message": "诊断内容过大",
    }


def test_chunked_body_over_limit_returns_413(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    body = json.dumps(_valid_payload(), separators=(",", ":")).encode()
    over_limit = body + (b" " * (32769 - len(body)))

    async def chunks() -> AsyncIterator[bytes]:
        yield over_limit[:100]
        yield over_limit[100:]

    response = _request(
        app,
        "POST",
        BRIDGE_PATH,
        content=chunks(),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "bridge_payload_too_large",
        "message": "诊断内容过大",
    }


def test_body_limiter_still_rejects_after_starlette_base_body_cache() -> None:
    app = FastAPI()

    @app.post("/_probe/bridge-body-limit")
    async def probe(request: Request) -> JSONResponse:
        bridge_request = MatlabBridgeRequest(request.scope, request.receive)
        await bridge_request.body()
        try:
            await bridge_request.body_with_limit(MAX_BRIDGE_BODY_BYTES)
        except BridgePayloadTooLargeError:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "bridge_payload_too_large",
                    "message": "诊断内容过大",
                },
            )
        return JSONResponse({"ok": True})

    body = b"x" * (MAX_BRIDGE_BODY_BYTES + 1)

    response = _request(
        app,
        "POST",
        "/_probe/bridge-body-limit",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "bridge_payload_too_large",
        "message": "诊断内容过大",
    }


@pytest.mark.parametrize(
    "payload",
    [
        _valid_payload(consent_confirmed=False),
        _valid_payload(consent_confirmed=1),
        _valid_payload(consent_confirmed="true"),
        _valid_payload(error_text=""),
        _valid_payload(error_text="\x00"),
        _valid_payload(client_version="bad version!"),
        _valid_payload(diagnostic_kind="auto_captured_error"),
        _valid_payload(source_code=SECRET),
    ],
)
def test_pydantic_failures_keep_global_422_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", BRIDGE_PATH, json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "请求参数有问题,请检查后重试",
    }
    assert SECRET not in response.text


def test_openapi_declares_bridge_error_responses_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    schema = _request(app, "GET", "/openapi.json").json()
    responses = schema["paths"][BRIDGE_PATH]["post"]["responses"]

    assert {"200", "403", "413", "415", "422"}.issubset(responses)
    assert "BridgeDiagnosticReceiptModel" in schema["components"]["schemas"]
    assert "BridgeErrorResponse" in schema["components"]["schemas"]


def test_openapi_omits_bridge_path_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=False, app_env="test")

    schema = _request(app, "GET", "/openapi.json").json()

    assert BRIDGE_PATH not in schema["paths"]
