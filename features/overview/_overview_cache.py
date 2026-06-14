"""Feature-private cache for generated project overviews."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.domain.project_overview import ProjectOverview


class OverviewCache(ABC):
    """Async cache boundary for ProjectOverview values."""

    @abstractmethod
    async def get(self, project_id: str) -> ProjectOverview | None:
        """Return cached overview for ``project_id`` when present."""
        ...

    @abstractmethod
    async def put(self, project_id: str, overview: ProjectOverview) -> None:
        """Store ``overview`` for ``project_id``."""
        ...

    @abstractmethod
    async def invalidate(self, project_id: str) -> None:
        """Remove cached overview for ``project_id`` if present."""
        ...


class InMemoryOverviewCache(OverviewCache):
    """Single-process cache used before a persistent cache lands."""

    def __init__(self) -> None:
        self._items: dict[str, ProjectOverview] = {}
        self._lock = asyncio.Lock()

    async def get(self, project_id: str) -> ProjectOverview | None:
        return self._items.get(project_id)

    async def put(self, project_id: str, overview: ProjectOverview) -> None:
        async with self._lock:
            self._items[project_id] = overview

    async def invalidate(self, project_id: str) -> None:
        async with self._lock:
            self._items.pop(project_id, None)
