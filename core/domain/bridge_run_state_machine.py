"""Pure run-state persistence decisions and snapshot fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from core.domain.bridge_run_state import (
    BridgeRunStateEnvelopeSeries,
    BridgeRunStateIdentitySeries,
    BridgeRunStateRequest,
    BridgeRunStateSeries,
)

RunStateSessionStatus = Literal["active", "ended", "gone"]
RunStateDecisionKind = Literal["idempotent", "current", "historical", "conflict", "rejected"]
RunStateConflictReason = Literal[
    "run_id_snapshot_conflict",
    "run_sequence_conflict",
    "current_sequence_invariant_failed",
    "request_id_reuse",
]
RunStateRejectedReason = Literal["session_not_active"]

FINGERPRINT_VERSION = 1


@dataclass(frozen=True, slots=True)
class RunStateSnapshotFingerprint:
    """Canonical bytes and hash for one already-redacted run-state snapshot."""

    fingerprint: str
    fingerprint_version: int
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class IncomingRunStateSnapshot:
    run_id: str
    run_sequence: int
    fingerprint: str
    fingerprint_version: int
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class PersistedRunStateRun:
    run_id: str
    run_sequence: int
    fingerprint: str
    fingerprint_version: int
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class RunStateDecision:
    kind: RunStateDecisionKind
    reason: RunStateConflictReason | RunStateRejectedReason | None = None
    replay_run: PersistedRunStateRun | None = None


def fingerprint_run_state_request(request: BridgeRunStateRequest) -> RunStateSnapshotFingerprint:
    """Return a deterministic fingerprint over the redacted persistent semantics.

    ``request_id`` is deliberately excluded because it identifies an HTTP attempt,
    not the immutable logical run snapshot.
    """

    canonical_bytes = canonicalize_run_state_request(request)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    snapshot_type = RunStateSnapshotFingerprint
    return snapshot_type(
        fingerprint=f"sha256:{digest}",
        fingerprint_version=FINGERPRINT_VERSION,
        canonical_bytes=canonical_bytes,
    )


def canonicalize_run_state_request(request: BridgeRunStateRequest) -> bytes:
    """Serialize the persistent semantic snapshot with stable field ordering."""

    payload = {
        "protocol_version": request.protocol_version,
        "session_id": str(request.session_id),
        "run_id": str(request.run_id),
        "run_sequence": request.run_sequence,
        "matlab_release": request.matlab_release,
        "client_version": request.client_version,
        "run_state_sharing_consent_confirmed": request.run_state_sharing_consent_confirmed,
        "run_status": request.run_status,
        "convergence_status": request.convergence_status,
        "stop_reason": request.stop_reason,
        "solver": request.solver,
        "metrics_status": request.metrics_status,
        "metrics": [
            {
                "name": metric.name,
                "value": metric.value,
                "unit_status": metric.unit_status,
                "unit": metric.unit,
            }
            for metric in request.metrics
        ],
        "series_status": request.series_status,
        "series": [_series_payload(series) for series in request.series],
    }
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def decide_run_state_persistence(
    *,
    session_status: RunStateSessionStatus | None,
    incoming: IncomingRunStateSnapshot,
    existing_run_by_run_id: PersistedRunStateRun | None,
    existing_run_by_sequence: PersistedRunStateRun | None,
    current_run: PersistedRunStateRun | None,
) -> RunStateDecision:
    """Classify one incoming snapshot using only transaction-supplied facts."""

    if session_status != "active":
        return RunStateDecision(kind="rejected", reason="session_not_active")

    if existing_run_by_run_id is not None:
        if _same_snapshot(existing_run_by_run_id, incoming):
            return RunStateDecision(kind="idempotent", replay_run=existing_run_by_run_id)
        return RunStateDecision(kind="conflict", reason="run_id_snapshot_conflict")

    if existing_run_by_sequence is not None:
        if existing_run_by_sequence.run_id == incoming.run_id and _same_snapshot(
            existing_run_by_sequence, incoming
        ):
            return RunStateDecision(kind="idempotent", replay_run=existing_run_by_sequence)
        return RunStateDecision(kind="conflict", reason="run_sequence_conflict")

    if current_run is None:
        return RunStateDecision(kind="current")
    if incoming.run_sequence > current_run.run_sequence:
        return RunStateDecision(kind="current")
    if incoming.run_sequence < current_run.run_sequence:
        return RunStateDecision(kind="historical")
    return RunStateDecision(kind="conflict", reason="current_sequence_invariant_failed")


def _same_snapshot(
    existing: PersistedRunStateRun,
    incoming: IncomingRunStateSnapshot,
) -> bool:
    return (
        existing.fingerprint_version == incoming.fingerprint_version
        and existing.fingerprint == incoming.fingerprint
        and existing.canonical_bytes == incoming.canonical_bytes
    )


def _series_payload(series: BridgeRunStateSeries) -> dict[str, object]:
    common: dict[str, object] = {
        "representation": series.representation,
        "series_id": series.series_id,
        "label": series.label,
        "time_unit": series.time_unit,
        "value_unit_status": series.value_unit_status,
        "sample_order": series.sample_order,
        "source_point_count": series.source_point_count,
        "t_start": series.t_start,
        "value_unit": series.value_unit,
    }
    if isinstance(series, BridgeRunStateIdentitySeries):
        return {
            **common,
            "t_step": series.t_step,
            "y": list(series.y),
        }
    if isinstance(series, BridgeRunStateEnvelopeSeries):
        return {
            **common,
            "bucket_width": series.bucket_width,
            "y_min": list(series.y_min),
            "y_max": list(series.y_max),
        }
    raise TypeError("unsupported run-state series")
