"""DeepSeek TextProvider implementation for the OpenAI-compatible API."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from openai import OpenAI

from core.domain.exceptions import LLMError, LLMRateLimitError, LLMServerError, LLMTimeoutError
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider

from ._deepseek_errors import translate_openai_error

__all__ = ["DeepSeekTextProvider"]


DEFAULT_MODEL_NAME = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_CONTEXT_TOKENS = 1_000_000
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFFS = (0.5, 1.0, 2.0)


CAPABILITY: dict[str, ModelCapability] = {
    "deepseek-v4-flash": ModelCapability(
        model_name="deepseek-v4-flash",
        supports_streaming=False,
        supports_json=True,
        supports_tool_call=False,
        supports_long_context=False,
        max_context_tokens=DEFAULT_CONTEXT_TOKENS,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        cost_input_per_million=0.14,
        cost_output_per_million=0.28,
    ),
    "deepseek-v4-pro": ModelCapability(
        model_name="deepseek-v4-pro",
        supports_streaming=False,
        supports_json=True,
        supports_tool_call=False,
        supports_long_context=True,
        max_context_tokens=DEFAULT_CONTEXT_TOKENS,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        cost_input_per_million=0.435,
        cost_output_per_million=0.87,
    ),
}


class DeepSeekTextProvider(TextProvider):
    """Synchronous DeepSeek adapter backed by the OpenAI-compatible SDK.

    The adapter receives all runtime values through its constructor. It does not
    import or read ``app.config.AppSettings``.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL_NAME,
        retry_count: int = DEFAULT_RETRY_COUNT,
    ) -> None:
        """Initialize a provider instance.

        Args:
            api_key: DeepSeek API key supplied by the application layer.
            base_url: DeepSeek OpenAI-compatible base URL.
            model: DeepSeek model name.
            retry_count: Number of retries after the initial attempt.

        Raises:
            ValueError: If ``model`` is unknown or ``retry_count`` is negative.
        """
        if model not in CAPABILITY:
            supported = ", ".join(sorted(CAPABILITY))
            raise ValueError(f"unsupported model: {model!r}. Supported: {supported}")
        if retry_count < 0:
            raise ValueError(f"retry_count must be >= 0, got {retry_count}")

        self._model = model
        self._retry_count = retry_count
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Call DeepSeek and return a structured text response.

        Args:
            messages: Chat messages to send to the model.
            json_mode: Whether to request JSON object output.
            timeout: Per-request timeout in seconds.
            max_tokens: Output token limit. Defaults to the provider limit.

        Returns:
            The normalized LLM response.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "timeout": timeout,
            "max_tokens": max_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return self._call_with_retry(kwargs)

    def capability(self) -> ModelCapability:
        """Return the model capability declaration for this provider."""
        return CAPABILITY[self._model]

    def _call_with_retry(self, kwargs: dict[str, Any]) -> LLMResponse:
        """Run the SDK call with retry for retryable LLM errors."""
        attempts = self._retry_count + 1
        last_exc: LLMError | None = None

        for attempt in range(attempts):
            try:
                start = time.monotonic()
                completion = self._client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)
                response = _to_llm_response(completion, latency_ms)
                logger.info(
                    "LLM call: tokens_in={} tokens_out={} latency_ms={} "
                    "finish_reason={} system_fingerprint={}",
                    response.prompt_tokens,
                    response.completion_tokens,
                    response.latency_ms,
                    response.finish_reason,
                    response.system_fingerprint,
                )
                return response
            except Exception as exc:
                translated = translate_openai_error(exc)
                last_exc = translated
                if not _is_retriable(translated) or attempt == attempts - 1:
                    raise translated from exc

                backoff = DEFAULT_RETRY_BACKOFFS[min(attempt, len(DEFAULT_RETRY_BACKOFFS) - 1)]
                logger.warning(
                    "LLM call failed (attempt {}/{}), retrying in {}s: exception_code={}",
                    attempt + 1,
                    attempts,
                    backoff,
                    _llm_error_code(translated),
                )
                time.sleep(backoff)

        assert last_exc is not None
        raise last_exc


def _is_retriable(error: LLMError) -> bool:
    """Return whether a translated LLM error should be retried."""
    return isinstance(error, LLMRateLimitError | LLMServerError | LLMTimeoutError)


def _llm_error_code(error: LLMError) -> str:
    if isinstance(error, LLMRateLimitError):
        return "llm_rate_limited"
    if isinstance(error, LLMTimeoutError):
        return "llm_timeout"
    if isinstance(error, LLMServerError):
        return "llm_server_error"
    return "llm_error"


def _to_llm_response(completion: Any, latency_ms: int) -> LLMResponse:
    """Convert an OpenAI-compatible chat completion into ``LLMResponse``."""
    usage = getattr(completion, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    choice = completion.choices[0]
    text = choice.message.content or ""
    finish_reason = getattr(choice, "finish_reason", None)
    return LLMResponse(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=completion.model,
        latency_ms=latency_ms,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        system_fingerprint=_metadata_str(completion, "system_fingerprint"),
    )


def _metadata_str(completion: Any, field_name: str) -> str | None:
    value = getattr(completion, field_name, None)
    return value if isinstance(value, str) and value else None
