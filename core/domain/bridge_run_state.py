"""Pure domain contracts for MATLAB bridge run-state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

RunStatus = Literal["completed", "stopped", "execution_error", "unknown"]
ConvergenceStatus = Literal["converged", "not_converged", "not_applicable", "unknown"]
ContainerStatus = Literal["available", "unavailable", "not_applicable", "unknown"]
UnitStatus = Literal["known", "unknown", "not_applicable"]
TimeUnit = Literal["s", "ms", "us", "unknown"]


def canonical_run_state_session_id(value: UUID | str) -> str:
    """Return the canonical run-state session identifier used for scope checks."""
    if isinstance(value, UUID):
        return str(value)
    return str(UUID(value))


@dataclass(frozen=True)
class BridgeRunStateMetric:
    name: str
    value: float
    unit_status: UnitStatus
    unit: str | None = None


@dataclass(frozen=True)
class BridgeRunStateIdentitySeries:
    representation: Literal["identity_uniform_v1"]
    series_id: str
    label: str
    time_unit: TimeUnit
    value_unit_status: UnitStatus
    sample_order: Literal["chronological"]
    source_point_count: int
    t_start: float
    t_step: float
    y: tuple[float, ...]
    value_unit: str | None = None


@dataclass(frozen=True)
class BridgeRunStateEnvelopeSeries:
    representation: Literal["min_max_envelope_uniform_v1"]
    series_id: str
    label: str
    time_unit: TimeUnit
    value_unit_status: UnitStatus
    sample_order: Literal["chronological"]
    source_point_count: int
    t_start: float
    bucket_width: float
    y_min: tuple[float, ...]
    y_max: tuple[float, ...]
    value_unit: str | None = None


BridgeRunStateSeries = BridgeRunStateIdentitySeries | BridgeRunStateEnvelopeSeries


@dataclass(frozen=True)
class BridgeRunStateRequest:
    protocol_version: Literal["0.3-b3"]
    request_id: UUID
    session_id: UUID
    run_id: UUID
    run_sequence: int
    matlab_release: str
    client_version: str
    run_state_sharing_consent_confirmed: bool
    run_status: RunStatus
    convergence_status: ConvergenceStatus
    stop_reason: str | None
    solver: str | None
    metrics_status: ContainerStatus
    metrics: tuple[BridgeRunStateMetric, ...]
    series_status: ContainerStatus
    series: tuple[BridgeRunStateSeries, ...]


@dataclass(frozen=True)
class BridgeRunStateReceipt:
    status: Literal["validated"]
    mode: Literal["ephemeral_validation"]
    durable: Literal[False]
    request_id: UUID
    run_id: UUID
    run_sequence: int
