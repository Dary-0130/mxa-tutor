"""Feature-private cache for generated paper plans."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import ModelGenerationPlan
from core.domain.paper_spec import PaperSpec
from features.paper.paper_plan_helpers import MissingBindingModel


@dataclass(frozen=True)
class PaperPlanRecord:
    """Single-process cache record for paper plan state."""

    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingBindingModel]


class PaperPlanCache(ABC):
    """Async cache boundary for paper plan state."""

    @abstractmethod
    async def get(self, paper_id: str) -> PaperPlanRecord | None:
        """Return cached plan state for ``paper_id`` when present."""
        ...

    @abstractmethod
    async def set(self, paper_id: str, record: PaperPlanRecord) -> None:
        """Store ``record`` for ``paper_id``."""
        ...

    @abstractmethod
    async def delete(self, paper_id: str) -> None:
        """Remove cached plan state for ``paper_id`` if present."""
        ...


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
