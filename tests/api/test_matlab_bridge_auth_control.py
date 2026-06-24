from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from api.dependencies import get_matlab_bridge_auth_service, get_settings
from core.domain.bridge_auth import RUN_STATE_WRITE_CAPABILITY
from features.matlab_bridge.bridge_auth_service import (
    BridgeAuthService,
    BridgeAuthServiceConfig,
    BridgeAuthTokenError,
    InMemoryBridgeRevocationStore,
)

TOKEN_PATH = "/api/v1/bridge/dev-auth/token"
REVOKE_PATH = "/api/v1/bridge/dev-auth/revoke"
BOOTSTRAP = "test-bridge-bootstrap-token-32-bytes"
SIGNING_KEY = "test-bridge-signing-key-32-bytes-ok"


def _configure_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    bridge_enabled: bool = True,
    dev_auth_enabled: bool = True,
    app_env: str = "test",
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "mxa.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("MATLAB_BRIDGE_ENABLED", "true" if bridge_enabled else "false")
    monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.setenv("MATLAB_BRIDGE_DEV_AUTH_ENABLED", "true" if dev_auth_enabled else "false")
    monkeypatch.setenv("MATLAB_BRIDGE_DEV_AUTH_BOOTSTRAP_TOKEN", BOOTSTRAP)
    get_settings.cache_clear()
    get_matlab_bridge_auth_service.cache_clear()


def _create_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: Any):
    _configure_env(monkeypatch, tmp_path, **env)
    from api.main import create_app

    return create_app()


async def _request_async(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    transport = httpx.ASGITransport(app=app, client=(host, 49152))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _request(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    return asyncio.run(_request_async(app, method, path, host=host, **kwargs))


def _token_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": "user-alpha",
        "project_id": "project-alpha",
        "session_id": "11111111-1111-4111-8111-111111111111",
        "capabilities": ["run_state:write"],
    }
    payload.update(overrides)
    return payload


def test_dev_auth_routes_are_hidden_and_default_off(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, bridge_enabled=True, dev_auth_enabled=False)

    response = _request(
        app,
        "POST",
        TOKEN_PATH,
        json=_token_request(),
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )
    schema = _request(app, "GET", "/openapi.json").json()

    assert response.status_code == 404
    assert TOKEN_PATH not in schema["paths"]
    assert REVOKE_PATH not in schema["paths"]


def test_dev_auth_requires_bootstrap_header(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)

    response = _request(app, "POST", TOKEN_PATH, json=_token_request())

    assert response.status_code == 403
    assert response.json() == {
        "error": "bridge_auth_forbidden",
        "message": "bridge auth request denied",
    }
    assert SIGNING_KEY not in response.text


def test_dev_auth_issues_token_with_only_run_state_write_capability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)

    response = _request(
        app,
        "POST",
        TOKEN_PATH,
        json=_token_request(),
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "issued"
    assert body["token_type"] == "Bearer"
    assert body["expires_in_seconds"] == 300
    assert SIGNING_KEY not in response.text

    context = get_matlab_bridge_auth_service().verify_token(
        body["access_token"],
        required_capability=RUN_STATE_WRITE_CAPABILITY,
    )
    assert context.user_id == "user-alpha"
    assert context.project_id == "project-alpha"
    assert context.session_id == "11111111-1111-4111-8111-111111111111"
    assert context.capabilities == frozenset({RUN_STATE_WRITE_CAPABILITY})


def test_dev_auth_rejects_capability_outside_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)

    response = _request(
        app,
        "POST",
        TOKEN_PATH,
        json=_token_request(capabilities=["run_state:read"]),
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "请求参数有问题,请检查后重试",
    }


def test_dev_auth_revoke_invalidates_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)
    token = _request(
        app,
        "POST",
        TOKEN_PATH,
        json=_token_request(),
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    ).json()["access_token"]

    response = _request(
        app,
        "POST",
        REVOKE_PATH,
        json={"access_token": token},
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "revoked"}
    with pytest.raises(BridgeAuthTokenError):
        get_matlab_bridge_auth_service().verify_token(
            token,
            required_capability=RUN_STATE_WRITE_CAPABILITY,
        )


def test_dev_auth_store_unavailable_maps_to_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)
    store = InMemoryBridgeRevocationStore()
    service = BridgeAuthService(
        BridgeAuthServiceConfig(
            signing_key=SIGNING_KEY,
            key_id="mxa-bridge-dev-v1",
            issuer="mxa-tutor-dev",
            audience="mxa-matlab-bridge",
            token_ttl_seconds=300,
            max_token_lifetime_seconds=900,
            clock_skew_seconds=10,
            process_generation="generation-1",
        ),
        revocation_store=store,
    )
    app.dependency_overrides[get_matlab_bridge_auth_service] = lambda: service
    token = service.issue_token(
        user_id="user-alpha",
        project_id="project-alpha",
        session_id="11111111-1111-4111-8111-111111111111",
    ).access_token
    store.set_available(False)

    response = _request(
        app,
        "POST",
        REVOKE_PATH,
        json={"access_token": token},
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "bridge_auth_unavailable",
        "message": "bridge auth request denied",
    }


def test_dev_auth_invalid_token_maps_to_401_with_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path)

    response = _request(
        app,
        "POST",
        REVOKE_PATH,
        json={"access_token": "not.a.jwt"},
        headers={"X-MXA-Bridge-Dev-Bootstrap": BOOTSTRAP},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"] == "bridge_auth_invalid_token"
