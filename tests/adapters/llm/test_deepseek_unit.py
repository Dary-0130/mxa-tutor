"""Unit tests for the DeepSeek TextProvider adapter."""

from __future__ import annotations

from typing import Any

import pytest
from loguru import logger
from openai import APITimeoutError

from adapters.llm.deepseek import DeepSeekTextProvider
from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
)
from core.interfaces.llm_provider import LLMMessage


class _FakeStatusError(Exception):
    """Exception with an OpenAI-like response status code."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


def _provider() -> DeepSeekTextProvider:
    return DeepSeekTextProvider(api_key="fake")


def test_chat_normal_path_returns_llm_response(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Normal SDK response is converted into LLMResponse."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion(
        text="hello",
        prompt_tokens=10,
        completion_tokens=3,
        model="deepseek-v4-flash",
        finish_reason="stop",
    )

    response = _provider().chat([LLMMessage(role="user", content="hi")])

    assert response.text == "hello"
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 3
    assert response.model == "deepseek-v4-flash"
    assert response.latency_ms >= 0
    assert response.finish_reason == "stop"


def test_chat_finish_reason_missing_returns_none(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Missing provider finish_reason stays unknown instead of being guessed."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion(include_finish_reason=False)

    response = _provider().chat([LLMMessage(role="user", content="hi")])

    assert response.finish_reason is None


def test_chat_passes_messages_role_content(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Message role/content values are passed through to the SDK."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion()

    _provider().chat(
        [
            LLMMessage(role="system", content="system text"),
            LLMMessage(role="user", content="user text"),
        ],
    )

    assert mock_create.call_args.kwargs["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "user text"},
    ]


def test_chat_passes_timeout_and_max_tokens(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Timeout and max_tokens parameters are passed through to the SDK."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion()

    _provider().chat([LLMMessage(role="user", content="hi")], timeout=7.5, max_tokens=123)

    assert mock_create.call_args.kwargs["timeout"] == 7.5
    assert mock_create.call_args.kwargs["max_tokens"] == 123


def test_json_mode_sends_response_format(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """JSON mode sends the OpenAI-compatible response_format argument."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion()

    _provider().chat([LLMMessage(role="user", content="json")], json_mode=True)

    assert mock_create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_json_mode_false_omits_response_format(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Non-JSON mode omits the response_format argument."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion()

    _provider().chat([LLMMessage(role="user", content="plain")])

    assert "response_format" not in mock_create.call_args.kwargs


def test_auth_error_translated(mock_openai_client: tuple[Any, Any]) -> None:
    """401/403 status errors become LLMAuthError."""
    _, mock_create = mock_openai_client
    mock_create.side_effect = _FakeStatusError(401)

    with pytest.raises(LLMAuthError):
        _provider().chat([LLMMessage(role="user", content="hi")])


def test_quota_error_translated(mock_openai_client: tuple[Any, Any]) -> None:
    """402 status errors become LLMQuotaError."""
    _, mock_create = mock_openai_client
    mock_create.side_effect = _FakeStatusError(402)

    with pytest.raises(LLMQuotaError):
        _provider().chat([LLMMessage(role="user", content="hi")])


def test_rate_limit_translated_and_retried(
    mocker: Any,
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """429 errors are retried and can eventually succeed."""
    _, mock_create = mock_openai_client
    mocker.patch("adapters.llm.deepseek.time.sleep")
    mock_create.side_effect = [
        _FakeStatusError(429),
        _FakeStatusError(429),
        _FakeStatusError(429),
        fake_chat_completion(text="ok"),
    ]

    response = _provider().chat([LLMMessage(role="user", content="hi")])

    assert response.text == "ok"
    assert mock_create.call_count == 4


def test_rate_limit_exhausted_raises(
    mocker: Any,
    mock_openai_client: tuple[Any, Any],
) -> None:
    """Retry exhaustion re-raises the translated rate limit error."""
    _, mock_create = mock_openai_client
    mocker.patch("adapters.llm.deepseek.time.sleep")
    mock_create.side_effect = [_FakeStatusError(429)] * 4

    with pytest.raises(LLMRateLimitError):
        _provider().chat([LLMMessage(role="user", content="hi")])

    assert mock_create.call_count == 4


def test_server_error_translated_and_retried(
    mocker: Any,
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """5xx errors are retried."""
    _, mock_create = mock_openai_client
    mocker.patch("adapters.llm.deepseek.time.sleep")
    mock_create.side_effect = [
        _FakeStatusError(503),
        _FakeStatusError(503),
        fake_chat_completion(text="ok"),
    ]

    response = _provider().chat([LLMMessage(role="user", content="hi")])

    assert response.text == "ok"
    assert mock_create.call_count == 3


def test_timeout_translated_and_retried(
    mocker: Any,
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """OpenAI timeout errors are translated and retried."""
    _, mock_create = mock_openai_client
    mocker.patch("adapters.llm.deepseek.time.sleep")
    timeout_error = APITimeoutError(request=mocker.MagicMock())
    mock_create.side_effect = [timeout_error, fake_chat_completion(text="ok")]

    response = _provider().chat([LLMMessage(role="user", content="hi")])

    assert response.text == "ok"
    assert mock_create.call_count == 2


def test_unknown_error_translated_to_server_error(
    mock_openai_client: tuple[Any, Any],
) -> None:
    """Unknown exceptions become LLMServerError and preserve the cause."""
    _, mock_create = mock_openai_client
    original = RuntimeError("boom")
    mock_create.side_effect = original

    with pytest.raises(LLMServerError) as exc_info:
        _provider().chat([LLMMessage(role="user", content="hi")])

    assert exc_info.value.__cause__ is original


def test_capability_returns_v4_flash_by_default(mock_openai_client: tuple[Any, Any]) -> None:
    """Default model is DeepSeek V4 Flash."""
    provider = DeepSeekTextProvider(api_key="fake")

    assert provider.capability().model_name == "deepseek-v4-flash"


def test_capability_returns_v4_pro_when_constructed(
    mock_openai_client: tuple[Any, Any],
) -> None:
    """Explicit V4 Pro construction returns its capability."""
    provider = DeepSeekTextProvider(api_key="fake", model="deepseek-v4-pro")

    assert provider.capability().model_name == "deepseek-v4-pro"


def test_capability_unknown_model_raises_value_error(
    mock_openai_client: tuple[Any, Any],
) -> None:
    """Unknown model names fail during construction."""
    with pytest.raises(ValueError):
        DeepSeekTextProvider(api_key="fake", model="invalid")


def test_no_message_content_logged(
    mock_openai_client: tuple[Any, Any],
    fake_chat_completion: Any,
) -> None:
    """Provider logs metadata only, not prompt or response content."""
    _, mock_create = mock_openai_client
    mock_create.return_value = fake_chat_completion(text="secret response")
    logs: list[str] = []
    sink_id = logger.add(logs.append)
    try:
        _provider().chat([LLMMessage(role="user", content="secret prompt")])
    finally:
        logger.remove(sink_id)

    joined = "".join(logs)
    assert "secret prompt" not in joined
    assert "secret response" not in joined
    assert "tokens_in=" in joined
    assert "finish_reason=" in joined
