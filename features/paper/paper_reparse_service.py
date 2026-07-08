"""Reparse an existing paper bundle from stored temporary text source."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.domain.exceptions import (
    DocumentParseError,
    PaperNotFoundError,
    PaperPlanGenerationError,
    PaperReparseFailedError,
    PaperReparseInProgressError,
    PaperReparseSourceUnavailableError,
    PaperReparseStoreError,
    PaperSpecGenerationError,
    StoreError,
)
from core.domain.paper_plan import PaperPlanRecord
from core.domain.paper_reparse_source import PaperReparseSource
from core.interfaces.paper_cache import PaperBundleStore
from core.interfaces.paper_reparse_store import PaperReparseStore
from features.paper.build_guidance_lifecycle import mark_guidance_not_generated
from features.paper.paper_fusion import SuccessfulPaperSpec, fuse_successful_specs
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_reparse_source import parsed_document_from_source
from features.paper.paper_spec_service import PaperSpecService


class PaperReparseLockRegistry:
    """Single-process per-paper lock registry for reparse requests."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, paper_id: str) -> _PaperReparseLockToken:
        """Acquire the paper lock or fail fast when another reparse is active."""

        async with self._guard:
            lock = self._locks.setdefault(paper_id, asyncio.Lock())
            if lock.locked():
                raise PaperReparseInProgressError("reparse_in_progress") from None
            await lock.acquire()
        return _PaperReparseLockToken(self, paper_id, lock)

    async def _release(self, paper_id: str, lock: asyncio.Lock) -> None:
        async with self._guard:
            lock.release()
            if not lock.locked():
                self._locks.pop(paper_id, None)


@dataclass(frozen=True)
class _PaperReparseLockToken:
    registry: PaperReparseLockRegistry
    paper_id: str
    lock: asyncio.Lock

    async def __aenter__(self) -> _PaperReparseLockToken:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.registry._release(self.paper_id, self.lock)


class PaperReparseService:
    """Prepare a new paper bundle from stored source, then commit atomically."""

    def __init__(
        self,
        bundle_store: PaperBundleStore,
        reparse_store: PaperReparseStore,
        spec_service: PaperSpecService,
        plan_service: PaperPlanService,
        lock_registry: PaperReparseLockRegistry,
    ) -> None:
        self._bundle_store = bundle_store
        self._reparse_store = reparse_store
        self._spec_service = spec_service
        self._plan_service = plan_service
        self._lock_registry = lock_registry

    async def reparse(self, paper_id: str) -> PaperPlanRecord:
        """Reparse a ready paper bundle without reading original files."""

        if await self._bundle_store.get_plan_record(paper_id) is None:
            raise PaperNotFoundError("paper_not_found") from None
        source = await self._reparse_store.get_reparse_source(paper_id)
        if source is None:
            raise PaperReparseSourceUnavailableError("reparse_source_unavailable") from None

        async with await self._lock_registry.acquire(paper_id):
            try:
                return await self._prepare_and_commit(paper_id, source)
            except StoreError:
                raise PaperReparseStoreError("paper_reparse_store_failed") from None
            except (
                DocumentParseError,
                PaperSpecGenerationError,
                PaperPlanGenerationError,
                ValueError,
            ):
                raise PaperReparseFailedError("paper_reparse_failed") from None

    async def _prepare_and_commit(
        self,
        paper_id: str,
        source: PaperReparseSource,
    ) -> PaperPlanRecord:
        successes: list[SuccessfulPaperSpec] = []
        for document_source in source.documents:
            parsed = parsed_document_from_source(document_source)
            spec = await self._spec_service.extract_parsed_uncached(
                parsed,
                paper_id,
                display_filename=document_source.filename,
                document_id=document_source.document_id,
            )
            successes.append(
                SuccessfulPaperSpec(
                    upload_index=document_source.upload_index,
                    document_id=document_source.document_id,
                    filename=document_source.filename,
                    spec=spec,
                )
            )

        spec = fuse_successful_specs(successes, source.primary_index)
        plan, missing_prompts, missing_bindings = await self._plan_service.generate(
            spec,
            paper_id,
        )
        plan = mark_guidance_not_generated(plan)
        record = PaperPlanRecord(
            paper_id=paper_id,
            spec=spec,
            plan=plan,
            missing_prompts=missing_prompts,
            missing_bindings=missing_bindings,
        )
        await self._reparse_store.replace_ready_bundle_with_source(record, source)
        return record
