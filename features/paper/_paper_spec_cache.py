"""Feature-private cache for generated PaperSpec values."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.domain.paper_spec import PaperSpec


class PaperSpecCache(ABC):
    """Async cache boundary for PaperSpec values."""

    @abstractmethod
    async def get(self, paper_id: str) -> PaperSpec | None:
        """Return cached spec for ``paper_id`` when present."""
        ...

    @abstractmethod
    async def put(self, paper_id: str, spec: PaperSpec) -> None:
        """Store ``spec`` for ``paper_id``."""
        ...

    @abstractmethod
    async def invalidate(self, paper_id: str) -> None:
        """Remove cached spec for ``paper_id`` if present."""
        ...


class InMemoryPaperSpecCache(PaperSpecCache):
    """Single-process cache used before persistent paper storage lands."""

    def __init__(self) -> None:
        self._items: dict[str, PaperSpec] = {}
        self._lock = asyncio.Lock()

    async def get(self, paper_id: str) -> PaperSpec | None:
        return self._items.get(paper_id)

    async def put(self, paper_id: str, spec: PaperSpec) -> None:
        async with self._lock:
            self._items[paper_id] = spec

    async def invalidate(self, paper_id: str) -> None:
        async with self._lock:
            self._items.pop(paper_id, None)
