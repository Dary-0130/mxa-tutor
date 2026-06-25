"""Reader boundary for MATLAB bridge run-state coaching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

CoachingRunStateRejectReason = Literal[
    "invalid_scope",
    "project_missing",
    "project_expired",
    "session_missing",
    "session_terminal",
    "scope_mismatch",
    "process_generation_mismatch",
    "run_missing",
]


class CoachingRunStateReadRejectedError(Exception):
    """A scoped coaching read is unavailable or not authorized."""

    def __init__(self, reason: CoachingRunStateRejectReason) -> None:
        self.reason = reason
        super().__init__(reason)


class CoachingRunStateReaderUnavailableError(Exception):
    """The coaching reader cannot produce an authoritative answer."""


@dataclass(frozen=True, slots=True)
class CoachingRunStateScope:
    user_id: str
    project_id: str
    session_id: str
    process_generation: str


@dataclass(frozen=True, slots=True)
class CoachingRunStateMetric:
    name: str
    value: float
    unit_status: str
    unit: str | None


@dataclass(frozen=True, slots=True)
class CoachingRunStateSeries:
    series_id: str
    label: str
    representation: str
    time_unit: str
    value_unit_status: str
    source_point_count: int
    t_start: float
    sample_min: float | None
    sample_max: float | None
    value_unit: str | None


@dataclass(frozen=True, slots=True)
class CoachingRunStateSnapshot:
    run_id: UUID
    request_id: UUID
    run_sequence: int
    matlab_release: str
    client_version: str
    run_status: str
    convergence_status: str
    stop_reason: str | None
    solver: str | None
    metrics_status: str
    metrics: tuple[CoachingRunStateMetric, ...]
    series_status: str
    series: tuple[CoachingRunStateSeries, ...]
    received_at: datetime


class CoachingRunStateReader(ABC):
    """Read one scoped run-state snapshot and recheck its active fence."""

    @abstractmethod
    async def read_run_state_for_coaching(
        self,
        scope: CoachingRunStateScope,
        run_id: UUID,
    ) -> CoachingRunStateSnapshot:
        """Read one target run for coaching; never reads a cross-run window."""
        ...

    @abstractmethod
    async def assert_coaching_session_active(self, scope: CoachingRunStateScope) -> None:
        """Recheck that the scoped run-state session remains active."""
        ...
