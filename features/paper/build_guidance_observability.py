"""Telemetry-only helpers for paper build guidance measurement."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

from core.domain.exceptions import (
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)

SUMMARY_SCHEMA_VERSION = "paper_pdf_smoke_guidance_observability_v4"
LENGTH_FINISH_COMPLETION_RATIO_FLOOR = 0.9

GuidanceFailureReasonCode = Literal[
    "zero_document_claims_empty_evidence_pool",
    "zero_document_claims_unlinked_evidence_pool",
    "llm_unparseable_finish_length",
    "llm_unparseable_finish_stop",
    "llm_unparseable_finish_unknown",
    "evidence_resolution_failed",
    "retry_cap_exhausted",
    "build_steps_unavailable",
    "evidence_card_unavailable",
    "guidance_generator_exception",
]
GuidanceGeneratorExceptionCode = Literal[
    "provider_timeout",
    "provider_rate_limit",
    "provider_server_error",
    "parse_error",
    "validation_error",
    "storage_error",
    "unexpected_internal_error",
]
GuidanceTerminationGuard = Literal[
    "none",
    "provider_timeout",
    "guidance_wall_clock",
    "hard_call_cap",
    "provider_rate_limit",
]
GuidanceParseOutcome = Literal[
    "parsed",
    "json_error",
    "non_object_json",
    "provider_exception",
]
GuidanceTerminalObservedStage = Literal["plan", "build_steps", "guidance"]
GuidanceFailureOwnerBucket = Literal[
    "plan_owned",
    "build_steps_owned",
    "guidance_owned",
    "guidance_input_defect",
    "unattributed",
]

GUIDANCE_INPUT_DEFECT_REASONS = frozenset(
    {
        "zero_document_claims_empty_evidence_pool",
        "zero_document_claims_unlinked_evidence_pool",
    }
)
_GENERATION_FAILED_REASONS = frozenset(
    {
        "llm_unparseable_finish_length",
        "llm_unparseable_finish_stop",
        "llm_unparseable_finish_unknown",
        "evidence_resolution_failed",
        "retry_cap_exhausted",
        "build_steps_unavailable",
        "evidence_card_unavailable",
        "guidance_generator_exception",
    }
)
_NO_DOCUMENT_BASIS_REASONS = GUIDANCE_INPUT_DEFECT_REASONS


@dataclass(frozen=True)
class GuidanceAttemptTelemetry:
    """Sanitized telemetry for one guidance provider attempt."""

    attempt_index: int
    parse_outcome: GuidanceParseOutcome
    finish_reason: str | None
    completion_tokens: int | None
    prompt_tokens: int | None
    max_tokens: int | None
    completion_ratio: float | None
    provider_telemetry_anomaly: bool
    resolver_event_codes: list[str]
    validator_machine_codes: list[str]
    detail_downgraded_count: int | None
    detail_dropped_count: int | None
    validator_dropped_unverified_count: int | None
    generated_output_changed: bool | None
    raw_document_claim_count: int | None
    raw_supporting_ref_count: int | None
    resolver_error_count: int | None
    parse_error_count: int
    elapsed_ms: int
    termination_guard: GuidanceTerminationGuard
    generator_exception: GuidanceGeneratorExceptionCode | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe dict for eval summary files."""

        return asdict(self)


@dataclass(frozen=True)
class GuidanceGenerationTelemetry:
    """Telemetry collected for one guidance generation call."""

    attempts: list[GuidanceAttemptTelemetry]
    terminal_status: str | None
    terminal_reason: str | None
    terminal_termination_guard: GuidanceTerminationGuard
    generator_exception: GuidanceGeneratorExceptionCode | None = None

    def attempt_dicts(self) -> list[dict[str, object]]:
        """Return attempts as JSON-safe dictionaries."""

        return [attempt.to_dict() for attempt in self.attempts]


def llm_unparseable_reason(finish_reason: str | None) -> GuidanceFailureReasonCode:
    """Map an observed finish_reason to the unparseable machine code."""

    if finish_reason == "length":
        return "llm_unparseable_finish_length"
    if finish_reason == "stop":
        return "llm_unparseable_finish_stop"
    return "llm_unparseable_finish_unknown"


def completion_ratio(completion_tokens: int | None, max_tokens: int | None) -> float | None:
    """Return completion/max_tokens when both values are usable."""

    if completion_tokens is None or max_tokens is None or max_tokens <= 0:
        return None
    return completion_tokens / max_tokens


def has_provider_telemetry_anomaly(
    *,
    finish_reason: str | None,
    completion_tokens: int | None,
    max_tokens: int | None,
) -> bool:
    """Return whether finish_reason=length conflicts with token usage telemetry."""

    if finish_reason != "length":
        return False
    ratio = completion_ratio(completion_tokens, max_tokens)
    return ratio is None or ratio < LENGTH_FINISH_COMPLETION_RATIO_FLOOR


def guidance_exception_code(exc: BaseException) -> GuidanceGeneratorExceptionCode:
    """Map exceptions to the controlled guidance exception taxonomy."""

    if isinstance(exc, LLMTimeoutError):
        return "provider_timeout"
    if isinstance(exc, LLMRateLimitError):
        return "provider_rate_limit"
    if isinstance(exc, LLMServerError):
        return "provider_server_error"
    if isinstance(exc, json.JSONDecodeError | TypeError | ValueError):
        return "parse_error"
    return "unexpected_internal_error"


def termination_guard_for_exception(exc: BaseException) -> GuidanceTerminationGuard:
    """Return the termination guard associated with a provider exception."""

    if isinstance(exc, LLMTimeoutError):
        return "provider_timeout"
    if isinstance(exc, LLMRateLimitError):
        return "provider_rate_limit"
    return "none"


def termination_guard_for_retry_reason(reason_code: str) -> GuidanceTerminationGuard:
    """Return the termination guard associated with a guidance retry stop."""

    if reason_code == "guidance_wall_clock_cap_exceeded":
        return "guidance_wall_clock"
    if reason_code == "guidance_call_cap_exceeded":
        return "hard_call_cap"
    return "none"


def validate_guidance_status_reason(status: str, reason: str | None) -> None:
    """Raise ValueError when guidance status and terminal reason are illegal."""

    if status == "generated" and reason is None:
        return
    if status in {"not_generated", "stale_pending_regeneration"} and reason is None:
        return
    if status == "generation_failed" and reason in _GENERATION_FAILED_REASONS:
        return
    if status == "no_document_basis" and reason in _NO_DOCUMENT_BASIS_REASONS:
        return
    raise ValueError("invalid_guidance_status_reason")


def guidance_failure_owner_bucket(
    *,
    failed: bool,
    plan_ready: bool,
    build_steps_structured: bool,
    guidance_invoked: bool,
    guidance_failure_reason: str | None,
) -> GuidanceFailureOwnerBucket | None:
    """Classify a failed round without relying on misleading reason names."""

    if not failed:
        return None
    if not plan_ready:
        return "plan_owned"
    if not build_steps_structured:
        return "build_steps_owned"
    if guidance_failure_reason in GUIDANCE_INPUT_DEFECT_REASONS:
        return "guidance_input_defect"
    if guidance_failure_reason == "retry_cap_exhausted" and not guidance_invoked:
        return "build_steps_owned"
    if guidance_invoked:
        return "guidance_owned"
    return "build_steps_owned"


def first_blocking_stage_from_owner(
    owner: GuidanceFailureOwnerBucket | None,
) -> str | None:
    """Return the pre-registered first-blocking-stage label for a row."""

    if owner == "plan_owned":
        return "plan"
    if owner == "build_steps_owned":
        return "build_steps"
    if owner == "guidance_owned":
        return "guidance"
    if owner == "guidance_input_defect":
        return "guidance_input_defect"
    if owner == "unattributed":
        return "unattributed"
    return None
