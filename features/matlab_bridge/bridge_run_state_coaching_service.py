"""LLM-backed MATLAB bridge run-state coaching service."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import ValidationError

from core.domain.bridge_auth import BridgeAuthContext
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingAltDirection,
    BridgeRunStateCoachingConfidence,
    BridgeRunStateCoachingEvidenceItem,
    BridgeRunStateCoachingFallbackReason,
    BridgeRunStateCoachingPrimaryDirection,
    BridgeRunStateCoachingRequest,
    BridgeRunStateCoachingResult,
    BridgeRunStateCoachingSignalReading,
)
from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.interfaces.coaching_run_state_reader import (
    CoachingRunStateReader,
    CoachingRunStateScope,
    CoachingRunStateSnapshot,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, TextProvider
from features.matlab_bridge._run_state_coaching_draft import CoachingDraft
from features.matlab_bridge.bridge_run_state_service import (
    contains_run_state_private_text,
    redact_run_state_text,
)
from features.paper._prompt_loader import PromptTemplate, load_prompt_template

DEFAULT_BRIDGE_COACHING_PROVIDER_TIMEOUT_SECONDS = 12.0
DEFAULT_BRIDGE_COACHING_SERVER_DEADLINE_SECONDS = 55.0
DEFAULT_BRIDGE_COACHING_MAX_TOKENS = 1024
MAX_BRIDGE_COACHING_PROVIDER_INPUT_BYTES = 24 * 1024
MAX_BRIDGE_COACHING_RESPONSE_BYTES = 32 * 1024
DEFAULT_BRIDGE_COACHING_SLOT_TTL_SECONDS = 70.0
DEFAULT_BRIDGE_COACHING_ORPHAN_LIMIT = 8

_COACHING_FAILED_MESSAGE = "运行状态陪调生成失败,请稍后重试"
_COACHING_UNAVAILABLE_MESSAGE = "运行状态陪调服务暂时不可用,请稍后重试"
_COACHING_TIMEOUT_MESSAGE = "运行状态陪调超时,请稍后重试"
_COACHING_BUSY_MESSAGE = "运行状态陪调正在处理中,请稍后重试"

_COMMITMENT_PATTERNS = (
    re.compile(r"(?:已经|已)(?:运行|执行|检查|验证|确认)"),
    re.compile(r"已跑"),
    re.compile(r"仿真.*(?:证明|确认|验证)"),
    re.compile(r"(?:可以确认|确定是|一定是|必然是|保证)"),
    re.compile(r"(?:修复|调整).*即可解决"),
)
_DEAD_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:set|target|tune)\b.{0,24}\b\d+(?:\.\d+)?\b"),
    re.compile(r"(?:设为|调到|调整到|目标|固定为|最终值|具体数值).{0,24}\d+(?:\.\d+)?"),
    re.compile(r"(?:Kp|Ki|Kd|增益|参数).{0,24}(?:=|为|到)\s*\d+(?:\.\d+)?"),
)


class BridgeRunStateCoachingCrossRoundNotEnabledError(Exception):
    """519-A rejects cross-round context requests."""


class BridgeRunStateCoachingUnavailableError(Exception):
    """Provider or shared dependency is unavailable."""


class BridgeRunStateCoachingTimeoutError(Exception):
    """Provider or server deadline timed out."""


class BridgeRunStateCoachingFailedError(Exception):
    """Provider output failed closed validation."""


class BridgeRunStateCoachingBusyError(Exception):
    """A session already has a coaching attempt in flight."""


@dataclass(frozen=True, slots=True)
class _AttemptSlot:
    attempt_id: str
    expires_at: float


class CoachingAttemptSlotManager:
    """Attempt-bound per-session in-flight guard with compare-and-release."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_BRIDGE_COACHING_SLOT_TTL_SECONDS,
        orphan_limit: int = DEFAULT_BRIDGE_COACHING_ORPHAN_LIMIT,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._orphan_limit = orphan_limit
        self._slots: dict[str, _AttemptSlot] = {}
        self._orphan_attempt_ids: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def orphan_count(self) -> int:
        return len(self._orphan_attempt_ids)

    async def acquire(self, session_key: str) -> str | None:
        now = _loop_time()
        async with self._lock:
            slot = self._slots.get(session_key)
            if slot is not None and slot.expires_at <= now:
                if len(self._orphan_attempt_ids) >= self._orphan_limit:
                    return None
                self._orphan_attempt_ids.add(slot.attempt_id)
                del self._slots[session_key]
                slot = None
            if slot is not None:
                return None

            attempt_id = uuid4().hex
            self._slots[session_key] = _AttemptSlot(
                attempt_id=attempt_id,
                expires_at=now + self._ttl_seconds,
            )
            return attempt_id

    async def release(self, session_key: str, attempt_id: str) -> None:
        async with self._lock:
            slot = self._slots.get(session_key)
            if slot is not None and slot.attempt_id == attempt_id:
                del self._slots[session_key]
                return
            self._orphan_attempt_ids.discard(attempt_id)


_DEFAULT_SLOT_MANAGER = CoachingAttemptSlotManager()


class BridgeRunStateCoachingService:
    """Generate one guarded run-state coaching result."""

    def __init__(
        self,
        text_provider: TextProvider,
        prompt_template: PromptTemplate | None = None,
        *,
        provider_timeout_s: float = DEFAULT_BRIDGE_COACHING_PROVIDER_TIMEOUT_SECONDS,
        server_deadline_s: float = DEFAULT_BRIDGE_COACHING_SERVER_DEADLINE_SECONDS,
        max_tokens: int = DEFAULT_BRIDGE_COACHING_MAX_TOKENS,
        slot_manager: CoachingAttemptSlotManager | None = None,
    ) -> None:
        self._text_provider = text_provider
        self._prompt_template = prompt_template or load_prompt_template("run_state_coaching.yaml")
        self._provider_timeout_s = provider_timeout_s
        self._server_deadline_s = server_deadline_s
        self._max_tokens = max_tokens
        self._slot_manager = slot_manager or _DEFAULT_SLOT_MANAGER

    async def coach(
        self,
        request: BridgeRunStateCoachingRequest,
        auth_context: BridgeAuthContext,
        *,
        reader: CoachingRunStateReader,
    ) -> BridgeRunStateCoachingResult:
        if request.previous_run_count != 0:
            raise BridgeRunStateCoachingCrossRoundNotEnabledError

        scope = CoachingRunStateScope(
            user_id=auth_context.user_id,
            project_id=auth_context.project_id,
            session_id=auth_context.session_id,
            process_generation=auth_context.claims.process_generation,
        )
        session_key = scope.session_id
        attempt_id = await self._slot_manager.acquire(session_key)
        if attempt_id is None:
            raise BridgeRunStateCoachingBusyError

        provider_task: asyncio.Task[LLMResponse] | None = None
        release_without_provider = True
        try:
            snapshot = await reader.read_run_state_for_coaching(scope, request.run_id)
            evidence = _build_evidence(snapshot)
            if _is_insufficient_without_provider(snapshot):
                result = _build_insufficient_result(request, snapshot, evidence)
                await reader.assert_coaching_session_active(scope)
                return result

            await reader.assert_coaching_session_active(scope)
            messages = self._build_messages(request, snapshot, evidence)
            _require_provider_input_limit(messages)
            logger.info(
                "Bridge run-state coaching LLM call: event_code={} status={} evidence_count={}",
                "bridge_run_state_coaching",
                "provider_call",
                len(evidence),
            )
            provider_task = asyncio.create_task(
                asyncio.to_thread(
                    self._text_provider.chat,
                    messages,
                    json_mode=True,
                    timeout=self._provider_timeout_s,
                    max_tokens=self._max_tokens,
                )
            )
            provider_task.add_done_callback(
                lambda task: _release_provider_attempt(
                    task,
                    self._slot_manager,
                    session_key,
                    attempt_id,
                )
            )
            release_without_provider = False

            outcome = await self._await_and_shape_provider(
                provider_task,
                request,
                snapshot,
                evidence,
            )
            await reader.assert_coaching_session_active(scope)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        finally:
            if release_without_provider:
                await self._slot_manager.release(session_key, attempt_id)

    def _build_messages(
        self,
        request: BridgeRunStateCoachingRequest,
        snapshot: CoachingRunStateSnapshot,
        evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
    ) -> list[LLMMessage]:
        context_json = json.dumps(
            _context_payload(snapshot, evidence),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        user = _render_user(
            self._prompt_template.user,
            {
                "REQUEST_ID": str(request.request_id),
                "MATLAB_RELEASE": snapshot.matlab_release,
                "ALLOWED_EVIDENCE_IDS": ",".join(item.evidence_id for item in evidence),
                "RUN_STATE_CONTEXT_JSON": context_json,
            },
        )
        return [
            LLMMessage(role="system", content=self._prompt_template.system),
            LLMMessage(role="user", content=user),
        ]

    async def _await_and_shape_provider(
        self,
        provider_task: asyncio.Task[LLMResponse],
        request: BridgeRunStateCoachingRequest,
        snapshot: CoachingRunStateSnapshot,
        evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
    ) -> BridgeRunStateCoachingResult | Exception:
        try:
            response = await asyncio.wait_for(
                asyncio.shield(provider_task),
                timeout=self._server_deadline_s,
            )
            return _parse_and_validate_response(response, request, snapshot, evidence)
        except TimeoutError:
            logger.error(
                "Bridge run-state coaching timeout: event_code={} status={}",
                "bridge_run_state_coaching",
                "server_deadline",
            )
            return BridgeRunStateCoachingTimeoutError(_COACHING_TIMEOUT_MESSAGE)
        except LLMTimeoutError:
            logger.error(
                "Bridge run-state coaching timeout: event_code={} status={}",
                "bridge_run_state_coaching",
                "provider_timeout",
            )
            return BridgeRunStateCoachingTimeoutError(_COACHING_TIMEOUT_MESSAGE)
        except (LLMAuthError, LLMQuotaError, LLMRateLimitError, LLMServerError):
            logger.error(
                "Bridge run-state coaching unavailable: event_code={} status={}",
                "bridge_run_state_coaching",
                "provider_unavailable",
            )
            return BridgeRunStateCoachingUnavailableError(_COACHING_UNAVAILABLE_MESSAGE)
        except BridgeRunStateCoachingFailedError as exc:
            return exc
        except Exception as exc:
            logger.error(
                "Bridge run-state coaching failed: event_code={} status={} exception_type={}",
                "bridge_run_state_coaching",
                "provider_failed",
                type(exc).__name__,
            )
            return BridgeRunStateCoachingFailedError(_COACHING_FAILED_MESSAGE)


def coaching_error_payloads() -> dict[int, dict[str, str]]:
    """Return the frozen status-code to coaching error-code mapping."""

    return {
        429: {
            "error": "bridge_run_state_coaching_busy",
            "message": _COACHING_BUSY_MESSAGE,
        },
        502: {
            "error": "bridge_run_state_coaching_failed",
            "message": _COACHING_FAILED_MESSAGE,
        },
        503: {
            "error": "bridge_run_state_coaching_unavailable",
            "message": _COACHING_UNAVAILABLE_MESSAGE,
        },
        504: {
            "error": "bridge_run_state_coaching_timeout",
            "message": _COACHING_TIMEOUT_MESSAGE,
        },
    }


def _parse_and_validate_response(
    response: LLMResponse,
    request: BridgeRunStateCoachingRequest,
    snapshot: CoachingRunStateSnapshot,
    evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
) -> BridgeRunStateCoachingResult:
    if len(response.text.encode("utf-8")) > MAX_BRIDGE_COACHING_RESPONSE_BYTES:
        raise BridgeRunStateCoachingFailedError(_COACHING_FAILED_MESSAGE)
    try:
        payload = json.loads(response.text)
        draft = CoachingDraft.model_validate(payload)
        result = _assemble_result(request, snapshot, evidence, draft)
        _validate_result_postconditions(result)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.error(
            "Bridge run-state coaching validation failed: event_code={} status={} exception_type={}",
            "bridge_run_state_coaching",
            "validation_failed",
            type(exc).__name__,
        )
        raise BridgeRunStateCoachingFailedError(_COACHING_FAILED_MESSAGE) from None
    logger.info(
        "Bridge run-state coaching completed: event_code={} status={}",
        "bridge_run_state_coaching",
        "completed",
    )
    return result


def _assemble_result(
    request: BridgeRunStateCoachingRequest,
    snapshot: CoachingRunStateSnapshot,
    evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
    draft: CoachingDraft,
) -> BridgeRunStateCoachingResult:
    evidence_ids = {item.evidence_id for item in evidence}
    reading_ids: set[str] = set()
    readings: list[BridgeRunStateCoachingSignalReading] = []
    for reading in draft.signal_readings:
        if reading.reading_id in reading_ids:
            raise ValueError("duplicate_reading_id")
        reading_ids.add(reading.reading_id)
        if any(evidence_id not in evidence_ids for evidence_id in reading.evidence_ids):
            raise ValueError("unknown_evidence_id")
        readings.append(
            BridgeRunStateCoachingSignalReading(
                reading_id=reading.reading_id,
                reading=reading.reading,
                is_inference=True,
                confidence=reading.confidence,
                evidence_ids=tuple(reading.evidence_ids),
            )
        )

    directions: list[BridgeRunStateCoachingPrimaryDirection] = []
    for direction in draft.primary_directions:
        if direction.rationale_reading_id not in reading_ids:
            raise ValueError("unknown_direction_reading")
        alternatives = []
        for alternative in direction.alternatives:
            if alternative.rationale_reading_id not in reading_ids:
                raise ValueError("unknown_alternative_reading")
            alternatives.append(
                BridgeRunStateCoachingAltDirection(
                    action=alternative.action,
                    magnitude_band=alternative.magnitude_band,
                    rationale_reading_id=alternative.rationale_reading_id,
                )
            )
        directions.append(
            BridgeRunStateCoachingPrimaryDirection(
                action=direction.action,
                magnitude_band=direction.magnitude_band,
                rationale_reading_id=direction.rationale_reading_id,
                alternatives=tuple(alternatives),
            )
        )

    if draft.cross_round_trend is not None:
        raise ValueError("cross_round_trend_not_enabled")
    confidence: BridgeRunStateCoachingConfidence = "low"
    if draft.outcome == "coached" and any(reading.confidence == "medium" for reading in readings):
        confidence = "medium"
    return BridgeRunStateCoachingResult(
        protocol_version="0.3-c1",
        request_id=request.request_id,
        run_id=request.run_id,
        context_run_ids=(request.run_id,),
        status="completed",
        mode="run_state_coaching",
        outcome=draft.outcome,
        run_summary=_run_summary(snapshot),
        signal_readings=tuple(readings),
        primary_directions=tuple(directions),
        cross_round_trend=None,
        uncertainties=tuple(draft.uncertainties),
        fallback_reason=draft.fallback_reason,
        overall_confidence=confidence,
        evidence=evidence,
        caveats=_caveats(),
    )


def _build_insufficient_result(
    request: BridgeRunStateCoachingRequest,
    snapshot: CoachingRunStateSnapshot,
    evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
) -> BridgeRunStateCoachingResult:
    reason: BridgeRunStateCoachingFallbackReason = (
        "run_status_unknown" if snapshot.run_status == "unknown" else "no_metrics_or_series"
    )
    return BridgeRunStateCoachingResult(
        protocol_version="0.3-c1",
        request_id=request.request_id,
        run_id=request.run_id,
        context_run_ids=(request.run_id,),
        status="completed",
        mode="run_state_coaching",
        outcome="insufficient_evidence",
        run_summary=_run_summary(snapshot),
        signal_readings=(),
        primary_directions=(),
        cross_round_trend=None,
        uncertainties=("这轮 run-state 缺少足够的指标或波形摘要,不适合给出陪调方向。",),
        fallback_reason=reason,
        overall_confidence="low",
        evidence=evidence,
        caveats=_caveats(),
    )


def _build_evidence(
    snapshot: CoachingRunStateSnapshot,
) -> tuple[BridgeRunStateCoachingEvidenceItem, ...]:
    items: list[BridgeRunStateCoachingEvidenceItem] = []

    def add(signal_ref: str, text: str) -> None:
        if len(items) >= 16:
            return
        evidence_id = f"e{len(items) + 1}"
        items.append(
            BridgeRunStateCoachingEvidenceItem(
                evidence_id=evidence_id,
                text=redact_run_state_text(text)[:200],
                signal_ref=redact_run_state_text(signal_ref)[:64],
            )
        )

    add("run_status", f"run_status={snapshot.run_status}")
    add("convergence_status", f"convergence_status={snapshot.convergence_status}")
    if snapshot.stop_reason:
        add("stop_reason", f"stop_reason={snapshot.stop_reason}")
    if snapshot.solver:
        add("solver", f"solver={snapshot.solver}")
    for metric in snapshot.metrics:
        unit = f" {metric.unit}" if metric.unit else ""
        add(f"metric:{metric.name}", f"metric {metric.name}={metric.value:g}{unit}")
    for series in snapshot.series:
        if series.sample_min is None or series.sample_max is None:
            add(
                f"series:{series.series_id}",
                f"series {series.series_id} points={series.source_point_count}",
            )
        else:
            add(
                f"series:{series.series_id}",
                (
                    f"series {series.series_id} points={series.source_point_count} "
                    f"range=[{series.sample_min:g},{series.sample_max:g}]"
                ),
            )
    return tuple(items)


def _context_payload(
    snapshot: CoachingRunStateSnapshot,
    evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...],
) -> dict[str, Any]:
    return {
        "run_id": str(snapshot.run_id),
        "run_sequence": snapshot.run_sequence,
        "matlab_release": snapshot.matlab_release,
        "client_version": snapshot.client_version,
        "run_status": snapshot.run_status,
        "convergence_status": snapshot.convergence_status,
        "stop_reason": snapshot.stop_reason,
        "solver": snapshot.solver,
        "metrics_status": snapshot.metrics_status,
        "metrics": [
            {
                "name": metric.name,
                "value": metric.value,
                "unit_status": metric.unit_status,
                "unit": metric.unit,
            }
            for metric in snapshot.metrics
        ],
        "series_status": snapshot.series_status,
        "series": [
            {
                "series_id": series.series_id,
                "label": series.label,
                "representation": series.representation,
                "time_unit": series.time_unit,
                "value_unit_status": series.value_unit_status,
                "source_point_count": series.source_point_count,
                "sample_min": series.sample_min,
                "sample_max": series.sample_max,
                "value_unit": series.value_unit,
            }
            for series in snapshot.series
        ],
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "text": item.text,
                "signal_ref": item.signal_ref,
            }
            for item in evidence
        ],
    }


def _validate_result_postconditions(result: BridgeRunStateCoachingResult) -> None:
    for text in _iter_result_strings(result):
        if contains_run_state_private_text(text):
            raise ValueError("privacy_scan_failed")
        for pattern in _COMMITMENT_PATTERNS:
            if pattern.search(text):
                raise ValueError("commitment_scan_failed")
    for text in _iter_provider_controlled_strings(result):
        for pattern in _DEAD_VALUE_PATTERNS:
            if pattern.search(text):
                raise ValueError("dead_value_scan_failed")


def _iter_result_strings(result: BridgeRunStateCoachingResult) -> list[str]:
    values = [result.run_summary, *result.uncertainties, *result.caveats]
    if result.cross_round_trend is not None:
        values.append(result.cross_round_trend)
    for reading in result.signal_readings:
        values.append(reading.reading)
        values.extend(reading.evidence_ids)
    for direction in result.primary_directions:
        values.extend([direction.action, direction.magnitude_band, direction.rationale_reading_id])
        for alternative in direction.alternatives:
            values.extend(
                [
                    alternative.action,
                    alternative.magnitude_band,
                    alternative.rationale_reading_id,
                ]
            )
    for item in result.evidence:
        values.extend([item.evidence_id, item.text, item.signal_ref])
    if result.fallback_reason is not None:
        values.append(result.fallback_reason)
    return values


def _iter_provider_controlled_strings(result: BridgeRunStateCoachingResult) -> list[str]:
    values = [*result.uncertainties]
    if result.cross_round_trend is not None:
        values.append(result.cross_round_trend)
    values.extend(reading.reading for reading in result.signal_readings)
    return values


def _is_insufficient_without_provider(snapshot: CoachingRunStateSnapshot) -> bool:
    return snapshot.run_status == "unknown" or (not snapshot.metrics and not snapshot.series)


def _run_summary(snapshot: CoachingRunStateSnapshot) -> str:
    return (
        f"本轮状态为 {snapshot.run_status},收敛状态为 {snapshot.convergence_status},"
        f"包含 {len(snapshot.metrics)} 个指标和 {len(snapshot.series)} 个波形摘要。"
    )


def _caveats() -> tuple[str, str]:
    return (
        "这里只基于脱敏、降采样的 run-state 摘要,没有运行仿真或读取原始 MAT/CSV。",
        "建议方向需要你在 MATLAB/Simulink 中自行验证,本机不会持久化解释或上下文。",
    )


def _require_provider_input_limit(messages: list[LLMMessage]) -> None:
    size = sum(len(message.content.encode("utf-8")) for message in messages)
    if size > MAX_BRIDGE_COACHING_PROVIDER_INPUT_BYTES:
        raise BridgeRunStateCoachingFailedError(_COACHING_FAILED_MESSAGE)


def _render_user(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"__{key}__", value)
    return rendered


def _release_provider_attempt(
    task: asyncio.Task[LLMResponse],
    slot_manager: CoachingAttemptSlotManager,
    session_key: str,
    attempt_id: str,
) -> None:
    try:
        if not task.cancelled():
            with suppress(Exception):
                task.result()
    finally:
        loop = asyncio.get_running_loop()
        loop.create_task(slot_manager.release(session_key, attempt_id))


def _loop_time() -> float:
    return asyncio.get_running_loop().time()
