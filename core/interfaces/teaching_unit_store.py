"""TeachingUnit cache store abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from core.domain.teaching_unit import TeachingUnit

CacheKey = tuple[str, str, str, str, str, str, str, str]
CacheState = Literal["generating", "ready", "failed_retryable", "failed_permanent"]


@dataclass(frozen=True)
class TeachingUnitCacheRecord:
    """Stateful cache record consumed by TeachingUnitService."""

    cache_key: CacheKey
    state: CacheState
    unit: TeachingUnit | None
    error_code: str | None
    retry_count: int
    expires_at: int


class TeachingUnitStore(ABC):
    """TeachingUnit persistence and state-machine contract."""

    @abstractmethod
    async def get_record_by_key(self, cache_key: CacheKey) -> TeachingUnitCacheRecord | None:
        """Return the full record for ``cache_key`` when present."""
        ...

    @abstractmethod
    async def begin_generating(self, cache_key: CacheKey, now: int, expires_at: int) -> bool:
        """Claim generation for ``cache_key`` when possible."""
        ...

    @abstractmethod
    async def mark_ready(self, cache_key: CacheKey, unit: TeachingUnit) -> None:
        """Transition a generating record to ready and persist ``unit``."""
        ...

    @abstractmethod
    async def mark_failed(self, cache_key: CacheKey, error_code: str, retryable: bool) -> None:
        """Transition a generating record to failed and increment retry_count."""
        ...

    @abstractmethod
    async def list_ready_by_project(self, project_id: str) -> list[TeachingUnit]:
        """List ready TeachingUnits for one project."""
        ...

    @abstractmethod
    async def delete_by_project(self, project_id: str) -> int:
        """Delete TeachingUnits for one project and return the deleted row count."""
        ...
