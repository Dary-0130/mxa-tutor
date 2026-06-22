from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from core.domain.bridge_explanation import BridgeExplanationRequest
from core.domain.exceptions import (
    BridgeExplanationError,
    BridgeExplanationTimeoutError,
    BridgeExplanationUnavailableError,
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.matlab_bridge.bridge_explanation_service import (
    DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS,
    DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS,
    DEFAULT_BRIDGE_SERVER_DEADLINE_SECONDS,
    BridgeExplanationService,
    contains_private_text,
    redact_bridge_error_text,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
RAW_ERROR = (
    "Error using sim. Undefined function or variable Kp_ctrl. "
    "See C:\\Users\\alice\\secret\\model.m"
)
REDACTED_SIGNAL = "Undefined function or variable Kp_ctrl"


class FakeProvider(TextProvider):
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
        self.json_mode: bool | None = None
        self.timeout: float | None = None
        self.max_tokens: int | None = None

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls += 1
        self.messages = messages
        self.json_mode = json_mode
        self.timeout = timeout
        self.max_tokens = max_tokens
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if self.exc is not None:
            raise self.exc
        return LLMResponse(
            text=self.text,
            prompt_tokens=10,
            completion_tokens=20,
            model="fake",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


def _request(error_text: str = RAW_ERROR) -> BridgeExplanationRequest:
    return BridgeExplanationRequest(
        protocol_version="0.3-b1",
        request_id=UUID(REQUEST_ID),
        diagnostic_kind="manual_error",
        matlab_release="R2026a",
        client_version="0.1.0",
        error_text=error_text,
        llm_processing_consent_confirmed=True,
    )


def _valid_result(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
                "supporting_signals": [REDACTED_SIGNAL],
            }
        ],
        "next_steps": [{"action": "先运行 `which` 查看名称解析,再检查初始化脚本。"}],
        "caveats": ["这里只基于粘贴的报错文本,没有运行仿真。"],
    }
    payload.update(overrides)
    return payload


async def test_explain_redacts_before_provider_and_passes_locked_call_options() -> None:
    provider = FakeProvider()
    service = BridgeExplanationService(provider)

    result = await service.explain(
        _request(
            "Error using sim. Undefined function or variable Kp_ctrl. "
            "Path C:\\Users\\alice\\secret\\model.m token=sk-SECRET12345"
        )
    )

    provider_input = "\n".join(message.content for message in provider.messages)
    assert result.status == "completed"
    assert provider.calls == 1
    assert provider.json_mode is True
    assert provider.timeout == DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS
    assert provider.max_tokens == DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS
    assert "C:\\Users\\alice" not in provider_input
    assert "sk-SECRET12345" not in provider_input
    assert "[REDACTED_PATH]" in provider_input
    assert "[REDACTED_SECRET]" in provider_input


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (LLMAuthError("auth"), BridgeExplanationUnavailableError),
        (LLMQuotaError("quota"), BridgeExplanationUnavailableError),
        (LLMRateLimitError("rate"), BridgeExplanationUnavailableError),
        (LLMServerError("server"), BridgeExplanationUnavailableError),
        (LLMTimeoutError("timeout"), BridgeExplanationTimeoutError),
    ],
)
async def test_provider_errors_map_to_bridge_errors(
    exc: Exception,
    expected: type[Exception],
) -> None:
    provider = FakeProvider(exc=exc)
    service = BridgeExplanationService(provider)

    with pytest.raises(expected) as error:
        await service.explain(_request())

    assert provider.calls == 1
    assert error.value.__cause__ is None


async def test_unclassified_provider_error_maps_to_failed_without_raw_text() -> None:
    provider = FakeProvider(exc=RuntimeError("provider secret C:\\Users\\alice\\model.m"))
    service = BridgeExplanationService(provider)

    with pytest.raises(BridgeExplanationError) as error:
        await service.explain(_request())

    assert provider.calls == 1
    assert error.value.__cause__ is None
    assert "secret" not in str(error.value)
    assert "C:\\Users\\alice" not in str(error.value)


async def test_server_deadline_timeout_maps_to_timeout() -> None:
    provider = FakeProvider(sleep_s=0.05)
    service = BridgeExplanationService(provider, provider_timeout_s=0.01, server_deadline_s=0.01)

    with pytest.raises(BridgeExplanationTimeoutError):
        await service.explain(_request())

    assert provider.calls == 1


@pytest.mark.parametrize(
    "text",
    [
        "{not-json",
        "[]",
        json.dumps(_valid_result(request_id="7ce7c327-0c4e-441f-ae0f-850b0f990636")),
        json.dumps(_valid_result(caveats=[]), ensure_ascii=False),
    ],
)
async def test_bad_json_schema_or_request_id_fail_closed(text: str) -> None:
    provider = FakeProvider(text=text)
    service = BridgeExplanationService(provider)

    with pytest.raises(BridgeExplanationError) as error:
        await service.explain(_request())

    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "result",
    [
        _valid_result(
            likely_causes=[
                {
                    "cause": "信号不在输入中。",
                    "is_inference": True,
                    "confidence": "low",
                    "supporting_signals": ["not in input signal"],
                }
            ]
        ),
        _valid_result(next_steps=[{"action": "可以确认根因就是 Kp_ctrl 未定义。"}]),
        _valid_result(next_steps=[{"action": "执行该步骤即可解决。"}]),
        _valid_result(next_steps=[{"action": "检查 `fabricatedFcn` 的路径。"}]),
    ],
)
async def test_grounding_hygiene_failures_return_bridge_error(result: dict[str, Any]) -> None:
    provider = FakeProvider(text=json.dumps(result, ensure_ascii=False))
    service = BridgeExplanationService(provider)

    with pytest.raises(BridgeExplanationError):
        await service.explain(_request())


async def test_builtin_identifier_allowlist_does_not_fail_grounding() -> None:
    result = _valid_result(
        next_steps=[{"action": "可以运行 `which`、`ver` 或 `license` 辅助排查。"}]
    )
    provider = FakeProvider(text=json.dumps(result, ensure_ascii=False))
    service = BridgeExplanationService(provider)

    assert (await service.explain(_request())).status == "completed"


async def test_output_privacy_scan_is_fail_closed_after_grounding() -> None:
    result = _valid_result(next_steps=[{"action": "不要输出 C:\\Users\\alice\\secret\\model.m。"}])
    provider = FakeProvider(text=json.dumps(result, ensure_ascii=False))
    service = BridgeExplanationService(provider)

    with pytest.raises(BridgeExplanationError):
        await service.explain(_request())


def test_redaction_and_privacy_scanner_cover_paths_secrets_and_source() -> None:
    raw = (
        "file:///C:/Users/alice/private/model.m\n"
        "\\\\server\\share\\secret\\file.m\n"
        "/home/alice/project/file.m\n"
        "api_key=SECRET123456789\n"
        "function y = secret(x)"
    )

    redacted = redact_bridge_error_text(raw)

    assert "C:/Users/alice" not in redacted
    assert "\\\\server\\share" not in redacted
    assert "/home/alice" not in redacted
    assert "SECRET123456789" not in redacted
    assert "function y" not in redacted
    assert contains_private_text(raw)
    assert not contains_private_text(redacted)


def test_timeout_budget_is_closed() -> None:
    assert DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS < DEFAULT_BRIDGE_SERVER_DEADLINE_SECONDS < 60
    assert 4 * DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS + 3.5 <= (
        DEFAULT_BRIDGE_SERVER_DEADLINE_SECONDS
    )
    assert DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS == 2048


def test_only_one_asyncio_to_thread_in_service() -> None:
    source = Path("features/matlab_bridge/bridge_explanation_service.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    count = sum(
        1 for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == "to_thread"
    )

    assert count == 1


def test_service_does_not_use_logger_exception() -> None:
    source = Path("features/matlab_bridge/bridge_explanation_service.py").read_text(
        encoding="utf-8"
    )

    assert "logger.exception" not in source
