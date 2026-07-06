"""Shared fixtures for DeepSeek LLM adapter tests."""

from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture
def fake_chat_completion() -> Any:
    """Factory for fake OpenAI-compatible chat completion objects."""

    def _make(
        text: str = "ok",
        prompt_tokens: int = 12,
        completion_tokens: int = 5,
        model: str = "deepseek-v4-flash",
        finish_reason: str | None = None,
        include_finish_reason: bool = True,
    ) -> Any:
        choice = SimpleNamespace(
            message=SimpleNamespace(content=text),
        )
        if include_finish_reason:
            choice.finish_reason = finish_reason
        return SimpleNamespace(
            choices=[choice],
            usage=SimpleNamespace(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            model=model,
        )

    return _make


@pytest.fixture
def mock_openai_client(mocker: Any) -> tuple[Any, Any]:
    """Patch the imported ``OpenAI`` symbol and return the fake client/create method."""
    mock_client = mocker.MagicMock()
    mock_create = mock_client.chat.completions.create
    mocker.patch("adapters.llm.deepseek.OpenAI", return_value=mock_client)
    return mock_client, mock_create
