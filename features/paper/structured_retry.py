"""Private structured-output retry helpers for paper LLM leaves."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

from core.interfaces.llm_provider import LLMMessage

logger = logging.getLogger(__name__)

StructuredComponent = Literal["spec", "plan"]

REASON_CALL_CAP_EXCEEDED = "structured_retry_call_cap_exceeded"
REASON_WALL_CLOCK_CAP_EXCEEDED = "structured_retry_wall_clock_cap_exceeded"

_CURRENT_RETRY_CONTEXT: ContextVar[StructuredRetryContext | None] = ContextVar(
    "paper_structured_retry_context",
    default=None,
)
_CURRENT_FINISH_REASON: ContextVar[str | None] = ContextVar(
    "paper_structured_finish_reason",
    default=None,
)


class StructuredRetryLimitExceeded(Exception):
    """Raised internally when an in-job structured retry cap is exceeded."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class StructuredRetryHint:
    """Sanitized failure hint safe to feed back to the model."""

    reason_code: str
    loc: tuple[str, ...] | None = None

    def to_message(self) -> LLMMessage:
        loc = ".".join(self.loc or ("root",))
        reason = _generalized_reason(self.reason_code)
        return LLMMessage(
            role="user",
            content=(
                "上一轮结构化输出未通过校验。请重新输出完整 JSON,不要输出 diff。"
                f"问题路径:{loc};原因类别:{reason}。"
            ),
        )


@dataclass
class StructuredRetryContext:
    """In-memory per-job caps and retry telemetry state."""

    warning_call_count: int = 10
    hard_call_count: int = 12
    wall_clock_seconds: float = 600.0
    started_monotonic: float = field(default_factory=time.monotonic)
    call_count: int = 0
    high_call_count_reported: bool = False
    retry_hints: dict[str, StructuredRetryHint] = field(default_factory=dict)
    rescued_leaves: set[str] = field(default_factory=set)
    failure_counts: dict[tuple[str, str, str], int] = field(default_factory=dict)

    def check_wall_clock(self) -> None:
        if time.monotonic() - self.started_monotonic > self.wall_clock_seconds:
            logger.warning(
                "paper_structured_retry_wall_clock_cap_exceeded reason_code=%s",
                REASON_WALL_CLOCK_CAP_EXCEEDED,
            )
            raise StructuredRetryLimitExceeded(REASON_WALL_CLOCK_CAP_EXCEEDED)

    def before_llm_call(self, *, component: StructuredComponent, leaf: str) -> None:
        self.check_wall_clock()
        if self.call_count + 1 > self.hard_call_count:
            logger.warning(
                "paper_structured_retry_call_cap_exceeded component=%s leaf=%s "
                "reason_code=%s call_count=%s hard_call_count=%s",
                component,
                leaf,
                REASON_CALL_CAP_EXCEEDED,
                self.call_count,
                self.hard_call_count,
            )
            raise StructuredRetryLimitExceeded(REASON_CALL_CAP_EXCEEDED)
        self.call_count += 1
        if not self.high_call_count_reported and self.call_count >= self.warning_call_count:
            self.high_call_count_reported = True
            logger.warning(
                "paper_structured_retry_high_call_count component=%s leaf=%s "
                "call_count=%s warning_call_count=%s",
                component,
                leaf,
                self.call_count,
                self.warning_call_count,
            )

    def hint_for_leaf(self, leaf: str) -> StructuredRetryHint | None:
        return self.retry_hints.get(leaf)

    def set_retry_hint(
        self,
        *,
        leaf: str,
        reason_code: str | None,
        loc: tuple[str, ...] | None,
    ) -> None:
        self.retry_hints[leaf] = StructuredRetryHint(
            reason_code=reason_code or "structured_output_invalid",
            loc=loc,
        )

    def mark_rescued(self, leaf: str) -> None:
        self.rescued_leaves.add(leaf)

    def record_failure(
        self,
        *,
        leaf: str,
        reason_code: str | None,
        locator_namespace: str | None,
        loc: tuple[str, ...] | None,
    ) -> int:
        key = (
            leaf,
            reason_code or "unknown",
            locator_namespace or ".".join(loc or ("root",)),
        )
        next_count = self.failure_counts.get(key, 0) + 1
        self.failure_counts[key] = next_count
        return next_count


class StructuredRetryContextToken:
    """Context manager token wrapper for resetting the retry context."""

    def __init__(self, context: StructuredRetryContext | None) -> None:
        self._token = _CURRENT_RETRY_CONTEXT.set(context)

    def reset(self) -> None:
        _CURRENT_RETRY_CONTEXT.reset(self._token)


def bind_retry_context(context: StructuredRetryContext | None) -> StructuredRetryContextToken:
    return StructuredRetryContextToken(context)


def current_retry_context() -> StructuredRetryContext | None:
    return _CURRENT_RETRY_CONTEXT.get()


def before_llm_call(*, component: StructuredComponent, leaf: str) -> None:
    context = current_retry_context()
    if context is not None:
        context.before_llm_call(component=component, leaf=leaf)


def append_retry_hint(messages: list[LLMMessage], leaf: str) -> list[LLMMessage]:
    context = current_retry_context()
    hint = context.hint_for_leaf(leaf) if context is not None else None
    if hint is None:
        return messages
    return [*messages, hint.to_message()]


def set_current_finish_reason(finish_reason: str | None) -> None:
    _CURRENT_FINISH_REASON.set(finish_reason)


def current_finish_reason() -> str | None:
    return _CURRENT_FINISH_REASON.get()


def _generalized_reason(reason_code: str) -> str:
    if reason_code == "invalid_json":
        return "invalid_json"
    if reason_code == "schema_validation":
        return "schema_shape_invalid"
    if "cardinality" in reason_code or "duplicate" in reason_code:
        return "schema_cardinality_invalid"
    if "evidence" in reason_code or "locator" in reason_code or "whitelist" in reason_code:
        return "schema_reference_invalid"
    return "semantic_validation_invalid"
