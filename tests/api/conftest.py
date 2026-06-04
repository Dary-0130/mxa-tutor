"""tests/api 共享 fixture。"""

from collections.abc import Iterator

import pytest

from api.dependencies import get_settings
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability
from features.overview import InMemoryOverviewCache


class FakeTextProvider:
    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = messages, json_mode, timeout, max_tokens
        return LLMResponse(
            text="{}", prompt_tokens=0, completion_tokens=0, model="fake", latency_ms=0
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


@pytest.fixture(autouse=True)
def _isolate_test_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """测试前后清理 ``get_settings`` 缓存 + ``dependency_overrides``。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    get_settings.cache_clear()

    from api.main import app

    app.dependency_overrides.clear()
    app.state.overview_cache = InMemoryOverviewCache()
    app.state.text_provider = FakeTextProvider()

    yield

    get_settings.cache_clear()

    leaked = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    if leaked:
        import sys

        print(
            f"WARNING: test leaked dependency_overrides: {list(leaked.keys())}",
            file=sys.stderr,
        )
