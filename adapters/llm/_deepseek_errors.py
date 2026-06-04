"""OpenAI-compatible SDK exceptions to project LLM errors."""

from core.domain.exceptions import (
    LLMAuthError,
    LLMError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)


def translate_openai_error(exc: Exception) -> LLMError:
    """Translate SDK or transport exceptions into project business errors.

    Args:
        exc: Exception raised by the OpenAI-compatible SDK or underlying transport.

    Returns:
        A project-level ``LLMError`` subclass. The caller should raise it with
        ``from exc`` to preserve the original cause.
    """
    status_code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None),
        "status_code",
        None,
    )

    if status_code is not None:
        if status_code in (401, 403):
            return LLMAuthError("DeepSeek auth failed")
        if status_code == 402:
            return LLMQuotaError("DeepSeek quota / balance")
        if status_code == 429:
            return LLMRateLimitError("DeepSeek rate limit")
        if 500 <= status_code < 600:
            return LLMServerError(f"DeepSeek server error status={status_code}")
        return LLMServerError(f"DeepSeek unexpected status status={status_code}")

    exc_class_name = type(exc).__name__
    if exc_class_name in {"APITimeoutError", "TimeoutException", "ReadTimeout"}:
        return LLMTimeoutError("DeepSeek timeout")
    if exc_class_name in {"APIConnectionError", "ConnectError"}:
        return LLMServerError("DeepSeek connection failed")

    msg = exc_class_name.lower()
    if "timeout" in msg or "timed out" in msg:
        return LLMTimeoutError("DeepSeek timeout")
    if "rate limit" in msg or "too many requests" in msg:
        return LLMRateLimitError("DeepSeek rate limit")
    if "quota" in msg or "balance" in msg or "insufficient" in msg:
        return LLMQuotaError("DeepSeek quota / balance")

    return LLMServerError(f"DeepSeek unknown error type={exc_class_name}")
