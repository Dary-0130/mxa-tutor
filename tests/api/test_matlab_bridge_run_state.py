from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from loguru import logger

from api.dependencies import (
    get_matlab_bridge_auth_service,
    get_matlab_bridge_run_state_service,
    get_matlab_bridge_run_state_store,
    get_settings,
)
from api.routes.matlab_bridge import MAX_BRIDGE_BODY_BYTES, bridge_run_state
from features.matlab_bridge.bridge_auth_service import (
    BridgeAuthService,
    BridgeAuthServiceConfig,
    InMemoryBridgeRevocationStore,
)

RUN_STATE_PATH = "/api/v1/bridge/run-state"
REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"
SECRET = "SECRET_BRIDGE_SENTINEL"
TEST_BRIDGE_SIGNING_KEY = "test-bridge-signing-key-32-bytes-ok"
BOOTSTRAP_USER_ID = "user-alpha"
BOOTSTRAP_PROJECT_ID = "project-alpha"


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b3",
        "request_id": REQUEST_ID,
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_sequence": 7,
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "run_state_sharing_consent_confirmed": True,
        "run_status": "completed",
        "convergence_status": "not_applicable",
        "stop_reason": "ReachedStopTime",
        "solver": "ode45",
        "metrics_status": "available",
        "metrics": [
            {
                "name": "wall_clock_elapsed",
                "value": 1.25,
                "unit_status": "known",
                "unit": "s",
            }
        ],
        "series_status": "available",
        "series": [
            {
                "representation": "identity_uniform_v1",
                "series_id": "simout",
                "label": "simout",
                "time_unit": "s",
                "value_unit_status": "unknown",
                "sample_order": "chronological",
                "source_point_count": 4,
                "t_start": 0.0,
                "t_step": 0.1,
                "y": [0.0, 1.0, 0.0, -1.0],
            }
        ],
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
    if enabled:
        monkeypatch.setenv("MATLAB_BRIDGE_AUTH_SIGNING_KEY", TEST_BRIDGE_SIGNING_KEY)
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    get_settings.cache_clear()
    get_matlab_bridge_auth_service.cache_clear()


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


def _auth_headers(session_id: str = SESSION_ID) -> dict[str, str]:
    token = (
        get_matlab_bridge_auth_service()
        .issue_token(
            user_id=BOOTSTRAP_USER_ID,
            project_id=BOOTSTRAP_PROJECT_ID,
            session_id=session_id,
        )
        .access_token
    )
    return {"Authorization": f"Bearer {token}"}


def _decode_token(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    header_b64, payload_b64, _signature = token.split(".")
    return _b64_json_decode(header_b64), _b64_json_decode(payload_b64)


def _sign_token(header: dict[str, Any], payload: dict[str, Any]) -> str:
    signing_input = ".".join((_b64_json(header), _b64_json(payload)))
    signature = _b64_bytes(
        hmac.new(
            TEST_BRIDGE_SIGNING_KEY.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{signing_input}.{signature}"


def _mutated_token(payload_updates: dict[str, object]) -> str:
    token = (
        get_matlab_bridge_auth_service()
        .issue_token(
            user_id=BOOTSTRAP_USER_ID,
            project_id=BOOTSTRAP_PROJECT_ID,
            session_id=SESSION_ID,
        )
        .access_token
    )
    header, payload = _decode_token(token)
    payload.update(payload_updates)
    return _sign_token(header, payload)


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_json_decode(value: str) -> dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    data = json.loads(decoded)
    assert isinstance(data, dict)
    return data


def test_run_state_path_not_registered_when_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=False, app_env="test")

    response = _request(app, "POST", RUN_STATE_PATH, json=_valid_payload())

    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "请求的资源不存在"}


def test_run_state_handler_uses_request_state_instead_of_body_parameter() -> None:
    signature = inspect.signature(bridge_run_state)

    assert "request" in signature.parameters
    assert "request_body" not in signature.parameters


def test_valid_run_state_request_returns_minimal_ephemeral_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(stop_reason=SECRET),
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "validated",
        "mode": "ephemeral_validation",
        "durable": False,
        "request_id": REQUEST_ID,
        "run_id": RUN_ID,
        "run_sequence": 7,
    }
    assert SECRET not in response.text


def test_run_state_route_does_not_resolve_persistence_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    async def fail_if_store_is_resolved() -> None:
        raise AssertionError("run-state must remain b3 ephemeral")

    app.dependency_overrides[get_matlab_bridge_run_state_store] = fail_if_store_is_resolved

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(),
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["durable"] is False


def test_run_state_missing_authorization_fails_with_bearer_challenge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", RUN_STATE_PATH, json=_valid_payload())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": "bridge_auth_invalid_token",
        "message": "bridge auth request denied",
    }
    assert SECRET not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": ""},
        {"Authorization": "Basic abc"},
        {"Authorization": "bearer abc"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer abc def"},
        {"Authorization": "Bearer abc, Bearer def"},
        {"Authorization": f"Bearer {'a' * (8192 + 1)}"},
        [("Authorization", "Bearer abc"), ("Authorization", "Bearer def")],
    ],
)
def test_run_state_rejects_invalid_authorization_header_shapes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    headers: Any,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", RUN_STATE_PATH, json=_valid_payload(), headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": "bridge_auth_invalid_token",
        "message": "bridge auth request denied",
    }


@pytest.mark.parametrize(
    "payload_updates",
    [
        {"iss": "other-issuer"},
        {"aud": "other-audience"},
        {"exp": 1},
        {"nbf": 4102444800},
    ],
)
def test_run_state_maps_invalid_token_claims_to_401(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload_updates: dict[str, object],
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    token = _mutated_token(payload_updates)

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(stop_reason=SECRET),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": "bridge_auth_invalid_token",
        "message": "bridge auth request denied",
    }
    assert SECRET not in response.text


def test_run_state_maps_bad_signature_and_revocation_to_401(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    service = get_matlab_bridge_auth_service()
    revoked = service.issue_token(
        user_id=BOOTSTRAP_USER_ID,
        project_id=BOOTSTRAP_PROJECT_ID,
        session_id=SESSION_ID,
    ).access_token
    service.revoke_token(revoked)
    tampered = revoked[:-1] + ("x" if revoked[-1] != "x" else "y")

    for token in (tampered, revoked):
        response = _request(
            app,
            "POST",
            RUN_STATE_PATH,
            json=_valid_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"] == "bridge_auth_invalid_token"


def test_run_state_maps_capability_denial_to_403(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    token = _mutated_token({"capabilities": ["run_state:read"]})

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(stop_reason=SECRET),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "bridge_auth_forbidden",
        "message": "bridge auth request denied",
    }
    assert SECRET not in response.text


def test_run_state_session_scope_mismatch_fails_before_service_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    dependency_calls = 0

    def service_factory() -> object:
        nonlocal dependency_calls
        dependency_calls += 1
        raise AssertionError("service dependency must not be resolved")

    app.dependency_overrides[get_matlab_bridge_run_state_service] = service_factory

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(stop_reason=SECRET),
        headers=_auth_headers(session_id="33333333-3333-4333-8333-333333333333"),
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "bridge_auth_forbidden",
        "message": "bridge auth request denied",
    }
    assert dependency_calls == 0
    assert SECRET not in response.text


def test_run_state_revocation_store_unavailable_fails_closed_with_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    store = InMemoryBridgeRevocationStore()
    service = BridgeAuthService(
        BridgeAuthServiceConfig(
            signing_key=TEST_BRIDGE_SIGNING_KEY,
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
        user_id=BOOTSTRAP_USER_ID,
        project_id=BOOTSTRAP_PROJECT_ID,
        session_id=SESSION_ID,
    ).access_token
    store.set_available(False)

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        json=_valid_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "bridge_auth_unavailable",
        "message": "bridge auth request denied",
    }


@pytest.mark.parametrize("host", ["8.8.8.8", "not-an-ip"])
def test_run_state_uses_same_loopback_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host: str,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", RUN_STATE_PATH, host=host, json=_valid_payload())

    assert response.status_code == 403
    assert response.json() == {
        "error": "matlab_bridge_forbidden",
        "message": "仅允许本机 MATLAB Add-on 访问",
    }


def test_run_state_content_type_guard_returns_415_before_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        content=f"not-json {SECRET}",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 415
    assert response.json() == {
        "error": "bridge_unsupported_media_type",
        "message": "仅支持 application/json",
    }
    assert SECRET not in response.text


def test_run_state_content_type_allows_json_with_charset_and_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        content=json.dumps(_valid_payload(), separators=(",", ":")),
        headers={**_auth_headers(), "content-type": "Application/JSON; charset=utf-8"},
    )

    assert response.status_code == 200


def test_run_state_malformed_json_returns_422_before_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        content=f'{{"stop_reason":"{SECRET}"',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "请求参数有问题,请检查后重试",
    }
    assert SECRET not in response.text


def test_run_state_body_limiter_counts_32768_and_32769_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    base = json.dumps(_valid_payload(), separators=(",", ":")).encode()
    assert len(base) < MAX_BRIDGE_BODY_BYTES
    exactly_limit = base + (b" " * (MAX_BRIDGE_BODY_BYTES - len(base)))
    over_limit = exactly_limit + b" "

    ok = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        content=exactly_limit,
        headers={**_auth_headers(), "content-type": "application/json", "content-length": "1"},
    )
    too_large = _request(
        app,
        "POST",
        RUN_STATE_PATH,
        content=over_limit,
        headers={"content-type": "application/json", "content-length": "1"},
    )

    assert ok.status_code == 200
    assert too_large.status_code == 413
    assert too_large.json() == {
        "error": "bridge_payload_too_large",
        "message": "诊断内容过大",
    }


@pytest.mark.parametrize(
    "payload",
    [
        _valid_payload(run_state_sharing_consent_confirmed=False),
        _valid_payload(run_sequence=True),
        _valid_payload(metrics=[{"name": "bad", "value": True, "unit_status": "unknown"}]),
        _valid_payload(metrics_status="unknown"),
        _valid_payload(series_status="unknown"),
        _valid_payload(source_code=SECRET),
        _valid_payload(series=[{**_valid_payload()["series"][0], "raw_mat": SECRET}]),  # type: ignore[index]
    ],
)
def test_run_state_pydantic_failures_keep_global_422_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

    response = _request(app, "POST", RUN_STATE_PATH, json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "请求参数有问题,请检查后重试",
    }
    assert SECRET not in response.text


def test_run_state_422_response_and_logs_do_not_echo_payload_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = _valid_payload(
        run_sequence=True,
        stop_reason=f"C:/Users/alice/private/{SECRET}/model.m",
        solver=f"solver-{SECRET}",
        metrics=[
            {
                "name": f"metric-{SECRET}",
                "value": 12345.678,
                "unit_status": "known",
                "unit": f"C:/Users/alice/private/{SECRET}/unit.txt",
            }
        ],
        series=[
            {
                **_valid_payload()["series"][0],  # type: ignore[index]
                "series_id": f"series-{SECRET}",
                "label": f"C:/Users/alice/private/{SECRET}/series.m",
                "y": [0.0, 98765.4321, -42.0, 1.0],
            }
        ],
    )
    log_lines: list[str] = []
    sink_id = logger.add(lambda message: log_lines.append(str(message)), format="{message}")
    try:
        app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")

        response = _request(app, "POST", RUN_STATE_PATH, json=payload)
    finally:
        logger.remove(sink_id)

    log_text = "\n".join(log_lines)
    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "请求参数有问题,请检查后重试",
    }
    assert "RequestValidationError" in log_text
    assert RUN_STATE_PATH in log_text
    for leaked in (
        SECRET,
        "C:/Users/alice/private",
        "metric-",
        "series-",
        "98765.4321",
    ):
        assert leaked not in response.text
        assert leaked not in log_text


def test_run_state_openapi_declares_feature_on_and_off_behavior(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    enabled_app = _create_app(monkeypatch, tmp_path, enabled=True, app_env="test")
    enabled_schema = _request(enabled_app, "GET", "/openapi.json").json()
    run_state_operation = enabled_schema["paths"][RUN_STATE_PATH]["post"]
    responses = run_state_operation["responses"]

    assert {"200", "401", "403", "413", "415", "422", "503"}.issubset(responses)
    assert responses["401"]["headers"]["WWW-Authenticate"]["schema"] == {"type": "string"}
    assert run_state_operation["security"] == [{"BridgeRunStateBearerAuth": []}]
    assert run_state_operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BridgeRunStateRequest"
    }
    assert enabled_schema["components"]["securitySchemes"]["BridgeRunStateBearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    assert "BridgeRunStateAuthErrorResponse" in enabled_schema["components"]["schemas"]
    assert "BridgeRunStateReceiptModel" in enabled_schema["components"]["schemas"]
    for path in ("/api/v1/bridge/diagnostic", "/api/v1/bridge/explanation"):
        operation = enabled_schema["paths"][path]["post"]
        assert "security" not in operation
        assert "401" not in operation["responses"]

    disabled_app = _create_app(monkeypatch, tmp_path, enabled=False, app_env="test")
    disabled_schema = _request(disabled_app, "GET", "/openapi.json").json()

    assert RUN_STATE_PATH not in disabled_schema["paths"]
    assert "BridgeRunStateBearerAuth" not in disabled_schema["components"].get(
        "securitySchemes", {}
    )
