"""Validation and durable wiring service for MATLAB bridge run-state snapshots."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Protocol

from loguru import logger

from adapters.storage.sqlite_bridge_run_state_store import BridgeRunStateScope
from core.domain.bridge_auth import BridgeAuthContext
from core.domain.bridge_run_state import (
    BridgeRunStateEnvelopeSeries,
    BridgeRunStateIdentitySeries,
    BridgeRunStateMetric,
    BridgeRunStateReceipt,
    BridgeRunStateRequest,
    BridgeRunStateSeries,
)
from core.domain.exceptions import BridgeRunStateValidationError

_PATH_PATTERNS = (
    re.compile(r"file://[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9._$-]+\\[^\s'\"<>]+"),
    re.compile(r"[A-Za-z]:[\\/][^\s'\"<>]+"),
    re.compile(r"/(?:Users|home|tmp|var|opt|mnt|Volumes)/[^\s'\"<>]+"),
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[^\s'\"<>]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
)
_SOURCE_PATTERNS = (
    re.compile(r"```[\s\S]*?```"),
    re.compile(r"(?im)^\s*(?:function|classdef|#include)\b.*$"),
)
_MODEL_METADATA_PATTERNS = (
    re.compile(r"(?i)\b(?:UserID|MachineName|ModelFilePath)\s*[:=]\s*[^\s,'\"<>]+"),
)


class RunStatePersistenceStore(Protocol):
    async def persist_run(
        self,
        request: BridgeRunStateRequest,
        scope: BridgeRunStateScope,
    ) -> Any:
        """Persist one redacted run-state snapshot in an authoritative transaction."""


class BridgeRunStateConflictError(Exception):
    """The incoming immutable snapshot conflicts with persisted run-state."""

    def __init__(self, reason: str | None) -> None:
        self.reason = reason
        super().__init__(reason or "conflict")


class BridgeRunStateInternalError(Exception):
    """The store returned a persistence state that should be unreachable."""


class BridgeRunStateService:
    """Validate, redact, and persist one run-state payload."""

    async def consume(
        self,
        request: BridgeRunStateRequest,
        auth_context: BridgeAuthContext,
        *,
        store: RunStatePersistenceStore,
        scope: BridgeRunStateScope,
    ) -> BridgeRunStateReceipt:
        _ = auth_context
        redacted_request = redact_run_state_request(request)
        if contains_run_state_private_text("\n".join(_iter_request_strings(redacted_request))):
            logger.error(
                "Bridge run-state privacy validation failed: event_code={} status={}",
                "bridge_run_state_privacy",
                "rejected",
            )
            raise BridgeRunStateValidationError("run_state_privacy_validation_failed") from None

        result = await store.persist_run(redacted_request, scope)
        decision = result.decision
        if decision.kind == "conflict":
            logger.info(
                "Bridge run-state persist rejected: event_code={} status={}",
                "bridge_run_state_write",
                "conflict",
            )
            raise BridgeRunStateConflictError(decision.reason)
        if decision.kind == "rejected":
            logger.error(
                "Bridge run-state persist invariant failed: event_code={} status={}",
                "bridge_run_state_write",
                "rejected_decision",
            )
            raise BridgeRunStateInternalError("rejected_decision") from None
        if decision.kind not in {"current", "historical", "idempotent"}:
            logger.error(
                "Bridge run-state persist invariant failed: event_code={} status={}",
                "bridge_run_state_write",
                "unknown_decision",
            )
            raise BridgeRunStateInternalError("unknown_decision") from None

        logger.info(
            "Bridge run-state persisted: event_code={} status={}",
            "bridge_run_state_write",
            decision.kind,
        )
        return BridgeRunStateReceipt(
            protocol_version="0.3-b4",
            status="persisted",
            mode="durable_persisted",
            durable=True,
            request_id=request.request_id,
            run_id=request.run_id,
            run_sequence=request.run_sequence,
        )


def redact_run_state_request(request: BridgeRunStateRequest) -> BridgeRunStateRequest:
    """Return a copy with every string field server-side redacted."""

    return replace(
        request,
        matlab_release=redact_run_state_text(request.matlab_release),
        client_version=redact_run_state_text(request.client_version),
        stop_reason=_redact_optional(request.stop_reason),
        solver=_redact_optional(request.solver),
        metrics=tuple(_redact_metric(metric) for metric in request.metrics),
        series=tuple(_redact_series(series) for series in request.series),
    )


def redact_run_state_text(text: str) -> str:
    """Best-effort server-side redaction for run-state string fields."""

    redacted = text
    for pattern in _PATH_PATTERNS:
        redacted = pattern.sub("[REDACTED_PATH]", redacted)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    for pattern in _SOURCE_PATTERNS:
        redacted = pattern.sub("[REDACTED_SOURCE]", redacted)
    for pattern in _MODEL_METADATA_PATTERNS:
        redacted = pattern.sub("[REDACTED_METADATA]", redacted)
    return redacted


def contains_run_state_private_text(text: str) -> bool:
    """Return True when text still contains material that must not be retained."""

    return any(
        pattern.search(text)
        for pattern in (
            *_PATH_PATTERNS,
            *_SECRET_PATTERNS,
            *_SOURCE_PATTERNS,
            *_MODEL_METADATA_PATTERNS,
        )
    )


def _redact_metric(metric: BridgeRunStateMetric) -> BridgeRunStateMetric:
    return replace(
        metric,
        name=redact_run_state_text(metric.name),
        unit=_redact_optional(metric.unit),
    )


def _redact_series(series: BridgeRunStateSeries) -> BridgeRunStateSeries:
    if isinstance(series, BridgeRunStateIdentitySeries):
        return replace(
            series,
            series_id=redact_run_state_text(series.series_id),
            label=redact_run_state_text(series.label),
            value_unit=_redact_optional(series.value_unit),
        )
    if isinstance(series, BridgeRunStateEnvelopeSeries):
        return replace(
            series,
            series_id=redact_run_state_text(series.series_id),
            label=redact_run_state_text(series.label),
            value_unit=_redact_optional(series.value_unit),
        )
    return series


def _redact_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return redact_run_state_text(value)


def _iter_request_strings(request: BridgeRunStateRequest) -> list[str]:
    values = [
        request.matlab_release,
        request.client_version,
        request.consent_notice_version,
        request.run_status,
        request.convergence_status,
        request.metrics_status,
        request.series_status,
    ]
    if request.stop_reason is not None:
        values.append(request.stop_reason)
    if request.solver is not None:
        values.append(request.solver)
    for metric in request.metrics:
        values.extend([metric.name, metric.unit_status])
        if metric.unit is not None:
            values.append(metric.unit)
    for series in request.series:
        values.extend(
            [
                series.representation,
                series.series_id,
                series.label,
                series.time_unit,
                series.value_unit_status,
                series.sample_order,
            ]
        )
        if series.value_unit is not None:
            values.append(series.value_unit)
    return values
