"""Stateless validation service for MATLAB bridge run-state snapshots."""

from __future__ import annotations

import re
from dataclasses import replace

from loguru import logger

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


class BridgeRunStateService:
    """Validate one run-state payload and return an ephemeral receipt."""

    def consume(self, request: BridgeRunStateRequest) -> BridgeRunStateReceipt:
        redacted_request = redact_run_state_request(request)
        if contains_run_state_private_text("\n".join(_iter_request_strings(redacted_request))):
            logger.error(
                "Bridge run-state privacy validation failed: request_id={} run_sequence={}",
                str(request.request_id),
                request.run_sequence,
            )
            raise BridgeRunStateValidationError("run_state_privacy_validation_failed") from None

        logger.info(
            (
                "Bridge run-state validated: request_id={} run_sequence={} run_status={} "
                "metrics_count={} series_count={}"
            ),
            str(request.request_id),
            request.run_sequence,
            request.run_status,
            len(request.metrics),
            len(request.series),
        )
        return BridgeRunStateReceipt(
            status="validated",
            mode="ephemeral_validation",
            durable=False,
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
