"""tests/api 共享 fixture。"""

import os

# 在 import 任何应用模块前先设 env,避免 collection 阶段 `from api.main import app`
# 触发 AppSettings.deepseek_api_key 必填校验崩。用 setdefault,本地 .env 真 key 不被覆盖。
_DID_SET_DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY" not in os.environ
os.environ.setdefault("DEEPSEEK_API_KEY", "fake-for-test")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402

from api.dependencies import get_matlab_bridge_auth_service, get_settings  # noqa: E402
from core.interfaces.embedder import EmbeddingProvider  # noqa: E402
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability  # noqa: E402
from features.overview import InMemoryOverviewCache  # noqa: E402


def pytest_collection_finish() -> None:
    if _DID_SET_DEEPSEEK_API_KEY and os.environ.get("DEEPSEEK_API_KEY") == "fake-for-test":
        os.environ.pop("DEEPSEEK_API_KEY", None)


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


class FakeChatService:
    async def handle_chat(self, project_id: str, question: str, session_id: str | None):
        _ = project_id, question, session_id
        raise RuntimeError("FakeChatService should be overridden by chat route tests")


class FakeEmbedder(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = "fake-model",
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        _ = model_name, device, normalize

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def dimension(self) -> int:
        return 2


@pytest.fixture(autouse=True)
def _isolate_test_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """测试前后清理 ``get_settings`` 缓存 + ``dependency_overrides``。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    get_settings.cache_clear()
    get_matlab_bridge_auth_service.cache_clear()

    import api.main as api_main

    app = api_main.app
    monkeypatch.setattr(api_main, "SentenceTransformerEmbedder", FakeEmbedder)

    app.dependency_overrides.clear()
    app.state.overview_cache = InMemoryOverviewCache()
    app.state.text_provider = FakeTextProvider()
    app.state.chat_service = FakeChatService()

    yield

    get_settings.cache_clear()
    get_matlab_bridge_auth_service.cache_clear()

    leaked = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    if leaked:
        import sys

        print(
            f"WARNING: test leaked dependency_overrides: {list(leaked.keys())}",
            file=sys.stderr,
        )
