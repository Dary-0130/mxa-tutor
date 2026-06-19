"""Feature-private cache for generated paper plans."""

from __future__ import annotations

import asyncio

from core.domain.paper_plan import PaperPlanRecord
from core.interfaces.paper_cache import PaperPlanCache


class InMemoryPaperPlanCache(PaperPlanCache):
    """Single-process cache used before persistent paper plan storage lands."""

    def __init__(self) -> None:
        self._items: dict[str, PaperPlanRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, paper_id: str) -> PaperPlanRecord | None:
        return self._items.get(paper_id)

    async def set(self, paper_id: str, record: PaperPlanRecord) -> None:
        async with self._lock:
            self._items[paper_id] = record

    async def delete(self, paper_id: str) -> None:
        async with self._lock:
            self._items.pop(paper_id, None)
