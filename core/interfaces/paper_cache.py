"""Paper-to-model persistent cache and bundle store interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.domain.paper_plan import PaperPlanRecord
from core.domain.paper_spec import PaperSpec


class PaperBundleStore(ABC):
    """Persistent store for complete PaperSpec + PaperPlan bundles."""

    @abstractmethod
    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        """Atomically store a ready paper spec and plan bundle."""
        ...

    @abstractmethod
    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        """Return the persisted PaperSpec for ``paper_id`` when present."""
        ...

    @abstractmethod
    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        """Return the persisted plan record for ``paper_id`` when complete."""
        ...

    @abstractmethod
    async def delete_bundle(self, paper_id: str) -> None:
        """Delete both spec and plan rows for ``paper_id``."""
        ...


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
