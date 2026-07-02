"""Internal store interface for paper reparse source packages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from core.domain.paper_plan import PaperPlanRecord
from core.domain.paper_reparse_source import PaperReparseSource


class PaperReparseStore(ABC):
    """Persistent operations that must handle spec, plan, and source atomically."""

    @abstractmethod
    async def save_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        """Atomically store a ready paper bundle and its temporary source."""
        ...

    @abstractmethod
    async def replace_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        """Atomically replace a ready bundle while preserving source expiry."""
        ...

    @abstractmethod
    async def get_reparse_source(self, paper_id: str) -> PaperReparseSource | None:
        """Return the temporary source package when present and unexpired."""
        ...

    @abstractmethod
    async def delete_expired_paper_bundles(
        self,
        *,
        now: datetime | None = None,
        ttl_hours: int = 24,
    ) -> int:
        """Delete expired paper spec, plan, and source rows in one transaction."""
        ...
