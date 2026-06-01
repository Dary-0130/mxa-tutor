import pytest

from core.interfaces.llm_provider import (
    LLMMessage,
    LLMResponse,
    ModelCapability,
    TextProvider,
)


def test_model_capability_required_fields_and_defaults() -> None:
    capability = ModelCapability(model_name="stub")

    assert capability.model_name == "stub"
    assert capability.supports_streaming is False
    assert capability.supports_json is False
    assert capability.supports_tool_call is False
    assert capability.supports_long_context is False
    assert capability.max_context_tokens == 8192
    assert capability.max_output_tokens == 4096
    assert capability.cost_input_per_million is None
    assert capability.cost_output_per_million is None


def test_llm_message_required_fields() -> None:
    message = LLMMessage(role="user", content="hi")

    assert message.role == "user"
    assert message.content == "hi"


def test_llm_response_required_fields() -> None:
    response = LLMResponse(
        text="ok",
        prompt_tokens=1,
        completion_tokens=2,
        model="stub",
        latency_ms=3,
    )

    assert response.text == "ok"
    assert response.prompt_tokens == 1
    assert response.completion_tokens == 2
    assert response.model == "stub"
    assert response.latency_ms == 3


def test_text_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        TextProvider()


class _StubTextProvider(TextProvider):
    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            text=messages[0].content,
            prompt_tokens=0,
            completion_tokens=0,
            model="stub",
            latency_ms=0,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="stub")


def test_text_provider_stub_works() -> None:
    provider = _StubTextProvider()

    response = provider.chat([LLMMessage(role="user", content="ok")])

    assert response.text == "ok"
    assert provider.capability().model_name == "stub"
