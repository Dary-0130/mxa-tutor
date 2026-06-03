"""Real DeepSeek API integration tests.

Run manually with:
    DEEPSEEK_API_KEY=sk-xxx pytest -m integration tests/adapters/llm/ -v
"""

from __future__ import annotations

import json
import os

import pytest

from adapters.llm import DeepSeekTextProvider
from core.interfaces.llm_provider import LLMMessage

pytestmark = pytest.mark.integration


@pytest.fixture
def real_provider() -> DeepSeekTextProvider:
    """Create a real provider or skip when no API key is configured."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")
    return DeepSeekTextProvider(api_key=api_key)


def test_real_chat_returns_nonempty_text(real_provider: DeepSeekTextProvider) -> None:
    """Real API call returns non-empty text and token usage."""
    response = real_provider.chat(
        messages=[LLMMessage(role="user", content="请用一句话介绍 PID 控制器")],
        timeout=30.0,
    )

    assert response.text.strip() != ""
    assert response.completion_tokens > 0
    assert response.prompt_tokens > 0
    assert response.latency_ms >= 0


def test_real_json_mode_returns_valid_json(real_provider: DeepSeekTextProvider) -> None:
    """Real JSON mode response can be parsed as JSON."""
    response = real_provider.chat(
        messages=[
            LLMMessage(
                role="user",
                content='输出 JSON: {"answer": "PID is a controller"}, only JSON',
            ),
        ],
        json_mode=True,
        timeout=30.0,
    )

    parsed = json.loads(response.text)
    assert isinstance(parsed, dict)
