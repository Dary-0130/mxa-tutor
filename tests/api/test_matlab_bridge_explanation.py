from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from api.dependencies import get_matlab_bridge_explanation_service, get_settings
from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.matlab_bridge.bridge_explanation_service import BridgeExplanationService

EXPLANATION_PATH = "/api/v1/bridge/explanation"
REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SIGNAL = "Undefined function or variable Kp_ctrl"
SECRET = "SECRET_BRIDGE_SENTINEL"


class FakeExplanationProvider(TextProvider):
    def __init__(
        self,
        *,
        text: str | None = None,
        exc: Exception | None = None,
        sleep_s: float = 0.0,
    ) -> None:
        self.text = text if text is not None else json.dumps(_valid_result(), ensure_ascii=False)
        self.exc = exc
        self.sleep_s = sleep_s
        self.calls = 0
        self.messages: list[LLMMessage] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = json_mode, timeout, max_tokens
        self.calls += 1
        self.messages = messages
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if self.exc is not None:
            raise self.exc
        return LLMResponse(
            text=self.text,
            prompt_tokens=1,
            completion_tokens=1,
            model="fake",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


def _valid_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b1",
        "request_id": REQUEST_ID,
        "diagnostic_kind": "manual_error",
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "error_text": f"Error using sim. {SIGNAL}.",
        "llm_processing_consent_confirmed": True,
    }
    payload.update(overrides)
    return payload


def _valid_result(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b1",
        "request_id": REQUEST_ID,
        "status": "completed",
        "mode": "llm_error_explanation",
        "meaning": "这段报错表示 MATLAB 没找到 Kp_ctrl 这个名称。",
        "likely_causes": [
            {
                "cause": "Kp_ctrl 可能尚未定义或未进入当前 workspace。",
                "is_inference": True,
                "confidence": "medium",
                "supporting_signals": [SIGNAL],
            }
        ],
        "next_steps": [{"action": "先运行 `which` 查看名称解析,再检查初始化脚本。"}],
        "caveats": ["这里只基于粘贴的报错文本,没有运行仿真。"],
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


def _create_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    provider: FakeExplanationProvider | None,
    enabled: bool = True,
):
    _configure_bridge_env(monkeypatch, tmp_path, enabled=enabled, app_env="test")
    from api.main import create_app

    app = create_app()
    if provider is not None:
        app.state.text_provider = provider
    return app


async def _request_async(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    transport = httpx.ASGITransport(app=app, client=(host, 49152))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _request(app, method: str, path: str, host: str = "127.0.0.1", **kwargs: Any):
    return asyncio.run(_request_async(app, method, path, host=host, **kwargs))


def test_explanation_path_not_registered_when_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, provider=None, enabled=False)

    response = _request(app, "POST", EXPLANATION_PATH, json=_valid_request())

    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "请求的资源不存在"}


def test_valid_explanation_request_uses_fake_provider_and_redacts_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FakeExplanationProvider()
    app = _create_app(monkeypatch, tmp_path, provider=provider)

    response = _request(
        app,
        "POST",
        EXPLANATION_PATH,
        json=_valid_request(
            error_text=(
                f"Error using sim. {SIGNAL}. "
                "C:\\Users\\alice\\secret\\model.m api_key=SECRET123456789"
            )
        ),
    )

    provider_input = "\n".join(message.content for message in provider.messages)
    assert response.status_code == 200
    assert response.json()["mode"] == "llm_error_explanation"
    assert provider.calls == 1
    assert "C:\\Users\\alice" not in provider_input
    assert "SECRET123456789" not in provider_input


def test_auto_captured_explanation_request_is_accepted_without_diagnostic_ack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FakeExplanationProvider(
        text=json.dumps(
            _valid_result(caveats=["这里只基于自动采集的报错文本,没有运行仿真。"]),
            ensure_ascii=False,
        )
    )
    app = _create_app(monkeypatch, tmp_path, provider=provider)

    response = _request(
        app,
        "POST",
        EXPLANATION_PATH,
        json=_valid_request(
            diagnostic_kind="auto_captured_error",
            error_text=(
                "identifier: Simulink:Config\n"
                "message:\n"
                f"{SIGNAL} C:\\Users\\alice\\secret\\model.m"
            ),
        ),
    )

    provider_input = "\n".join(message.content for message in provider.messages)
    assert response.status_code == 200
    assert provider.calls == 1
    assert "diagnostic_kind: auto_captured_error" in provider_input
    assert "C:\\Users\\alice" not in provider_input


@pytest.mark.parametrize("host", ["8.8.8.8", "not-an-ip"])
def test_explanation_uses_same_loopback_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host: str,
) -> None:
    app = _create_app(monkeypatch, tmp_path, provider=FakeExplanationProvider())

    response = _request(app, "POST", EXPLANATION_PATH, host=host, json=_valid_request())

    assert response.status_code == 403
    assert response.json() == {
        "error": "matlab_bridge_forbidden",
        "message": "仅允许本机 MATLAB Add-on 访问",
    }


@pytest.mark.parametrize(
    ("exc", "status_code", "machine_code"),
    [
        (LLMAuthError("auth"), 503, "bridge_explanation_unavailable"),
        (LLMQuotaError("quota"), 503, "bridge_explanation_unavailable"),
        (LLMRateLimitError("rate"), 503, "bridge_explanation_unavailable"),
        (LLMServerError("server"), 503, "bridge_explanation_unavailable"),
        (RuntimeError("provider unavailable"), 502, "bridge_explanation_failed"),
        (LLMTimeoutError("timeout"), 504, "bridge_explanation_timeout"),
    ],
)
def test_provider_error_status_code_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    exc: Exception,
    status_code: int,
    machine_code: str,
) -> None:
    provider = FakeExplanationProvider(exc=exc)
    app = _create_app(monkeypatch, tmp_path, provider=provider)

    response = _request(
        app,
        "POST",
        EXPLANATION_PATH,
        json=_valid_request(error_text=f"{SECRET} {SIGNAL}"),
    )

    assert provider.calls == 1
    assert response.status_code == status_code
    assert response.json()["error"] == machine_code
    assert SECRET not in response.text


@pytest.mark.parametrize(
    ("text", "status_code", "machine_code"),
    [
        ("{not-json", 502, "bridge_explanation_failed"),
        (
            json.dumps(_valid_result(caveats=[]), ensure_ascii=False),
            502,
            "bridge_explanation_failed",
        ),
        (
            json.dumps(
                _valid_result(next_steps=[{"action": "不要泄漏 C:\\Users\\alice\\secret.m"}]),
                ensure_ascii=False,
            ),
            502,
            "bridge_explanation_failed",
        ),
    ],
)
def test_bad_json_validator_and_privacy_status_code_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    text: str,
    status_code: int,
    machine_code: str,
) -> None:
    provider = FakeExplanationProvider(text=text)
    app = _create_app(monkeypatch, tmp_path, provider=provider)

    response = _request(app, "POST", EXPLANATION_PATH, json=_valid_request())

    assert provider.calls == 1
    assert response.status_code == status_code
    assert response.json()["error"] == machine_code


def test_missing_shared_provider_maps_to_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, provider=None)

    response = _request(app, "POST", EXPLANATION_PATH, json=_valid_request())

    assert response.status_code == 503
    assert response.json()["error"] == "bridge_explanation_unavailable"


def test_deadline_timeout_maps_to_504(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FakeExplanationProvider(sleep_s=0.05)
    app = _create_app(monkeypatch, tmp_path, provider=provider)
    app.dependency_overrides[get_matlab_bridge_explanation_service] = lambda: (
        BridgeExplanationService(provider, provider_timeout_s=0.01, server_deadline_s=0.01)
    )

    response = _request(app, "POST", EXPLANATION_PATH, json=_valid_request())

    assert provider.calls == 1
    assert response.status_code == 504
    assert response.json()["error"] == "bridge_explanation_timeout"


def test_explanation_pydantic_failures_keep_global_422_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, provider=FakeExplanationProvider())

    for payload in (
        _valid_request(source_code=SECRET),
        _valid_request(diagnostic_kind="diagnostic_stub"),
    ):
        response = _request(app, "POST", EXPLANATION_PATH, json=payload)

        assert response.status_code == 422
        assert response.json() == {
            "error": "validation_error",
            "message": "请求参数有问题,请检查后重试",
        }
        assert SECRET not in response.text


def test_openapi_declares_explanation_error_responses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = _create_app(monkeypatch, tmp_path, provider=FakeExplanationProvider())

    schema = _request(app, "GET", "/openapi.json").json()
    responses = schema["paths"][EXPLANATION_PATH]["post"]["responses"]

    assert {"200", "403", "413", "415", "422", "502", "503", "504"}.issubset(responses)
    assert "BridgeExplanationResultModel" in schema["components"]["schemas"]
    assert "BridgeExplanationErrorResponse" in schema["components"]["schemas"]
