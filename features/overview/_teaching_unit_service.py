"""TeachingUnit orchestration service."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Protocol

from core.domain.exceptions import (
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    TeachingUnitGenerationError,
    TeachingUnitInProgressError,
    TeachingUnitTargetNotFoundError,
)
from core.domain.project import Project
from core.domain.project_graph import NodeType, ProjectGraph, ProjectNode
from core.domain.teaching_unit import (
    TeachingLevel,
    TeachingTarget,
    TeachingUnit,
    TeachingUnitRef,
)
from core.interfaces.project_store import ProjectStore
from core.interfaces.teaching_unit_store import (
    CacheKey,
    TeachingUnitCacheRecord,
    TeachingUnitStore,
)
from features.overview.project_graph_builder import ProjectGraphBuilder

from ._teaching_level_policy import TeachingLevelPolicy, TeachingUnitRequest
from ._teaching_unit_builder import BUILDER_VERSION, TeachingUnitBuildRequest

PROMPT_VERSION = "v0.1.0"
SOURCE_VERSION = "v1"
TTL_SECONDS = 24 * 3600
MAX_RETRIES = 3
WAIT_TIMEOUT_SECONDS = 8.0
POLL_INTERVAL_SECONDS = 0.05


class ProjectGraphBuilderLike(Protocol):
    def build(self, project: Project) -> ProjectGraph:
        """Build a ProjectGraph from ``project``."""
        ...


class TeachingUnitBuilderLike(Protocol):
    async def build(
        self,
        request: TeachingUnitBuildRequest,
        graph: ProjectGraph,
    ) -> TeachingUnit:
        """Build a TeachingUnit for a graph target."""
        ...


class TeachingUnitService:
    """Generate and cache TeachingUnit values lazily."""

    def __init__(
        self,
        project_store: ProjectStore,
        teaching_unit_store: TeachingUnitStore,
        builder: TeachingUnitBuilderLike,
        level_policy: TeachingLevelPolicy,
        model_name: str,
        graph_builder_factory: Callable[[], ProjectGraphBuilderLike] | None = None,
        ttl_seconds: int = TTL_SECONDS,
        wait_timeout_seconds: float = WAIT_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._project_store = project_store
        self._store = teaching_unit_store
        self._builder = builder
        self._level_policy = level_policy
        self._model_name = model_name
        self._graph_builder_factory = graph_builder_factory or ProjectGraphBuilder
        self._ttl_seconds = ttl_seconds
        self._wait_timeout_seconds = wait_timeout_seconds
        self._clock = clock
        self._inflight: dict[CacheKey, asyncio.Lock] = {}

    async def get_or_generate(self, request: TeachingUnitRequest) -> TeachingUnit:
        """Return a ready TeachingUnit or generate one lazily."""
        resolved_level = self._level_policy.resolve(request)
        cache_key = self._build_cache_key(request, resolved_level)
        project = await self._project_store.get_project(request.project_id)

        record = await self._store.get_record_by_key(cache_key)
        if record is not None:
            ready = self._check_record_state(record)
            if ready is not None:
                return ready

        lock = self._inflight.setdefault(cache_key, asyncio.Lock())
        try:
            async with lock:
                record = await self._store.get_record_by_key(cache_key)
                if record is not None:
                    ready = self._check_record_state(record)
                    if ready is not None:
                        return ready

                now = int(self._clock())
                expires_at = now + self._ttl_seconds
                won = await self._store.begin_generating(cache_key, now, expires_at)
                if not won:
                    return await self._wait_for_ready(cache_key)

                try:
                    graph = await asyncio.to_thread(self._build_graph_sync, project)
                    target_node = _find_target_node(
                        graph,
                        request.target_type,
                        request.target_id,
                    )
                    prerequisites = await self._prerequisite_candidates(request.project_id)
                    unit = await self._builder.build(
                        TeachingUnitBuildRequest(
                            project_id=request.project_id,
                            target_node=target_node,
                            level=resolved_level,
                            prerequisite_candidates=prerequisites,
                        ),
                        graph,
                    )
                    await self._store.mark_ready(cache_key, unit)
                    return unit
                except TeachingUnitTargetNotFoundError:
                    await self._store.mark_failed(
                        cache_key,
                        "TeachingUnitTargetNotFoundError",
                        retryable=False,
                    )
                    raise
                except Exception as exc:
                    retryable = _is_retryable(exc)
                    await self._store.mark_failed(cache_key, type(exc).__name__, retryable)
                    raise TeachingUnitGenerationError("teaching_unit_generation_failed") from None
        finally:
            self._inflight.pop(cache_key, None)

    def _build_cache_key(
        self,
        request: TeachingUnitRequest,
        resolved_level: TeachingLevel,
    ) -> CacheKey:
        return (
            request.project_id,
            request.target_type,
            request.target_id,
            resolved_level,
            BUILDER_VERSION,
            PROMPT_VERSION,
            self._model_name,
            SOURCE_VERSION,
        )

    def _check_record_state(self, record: TeachingUnitCacheRecord) -> TeachingUnit | None:
        now = int(self._clock())
        if record.expires_at < now:
            return None
        if record.state == "ready" and record.unit is not None:
            return record.unit
        if record.state == "failed_permanent":
            raise TeachingUnitGenerationError("teaching_unit_failed_permanent")
        if record.state == "failed_retryable" and record.retry_count >= MAX_RETRIES:
            raise TeachingUnitGenerationError("teaching_unit_retry_exhausted")
        return None

    async def _wait_for_ready(self, cache_key: CacheKey) -> TeachingUnit:
        deadline = self._clock() + self._wait_timeout_seconds
        while self._clock() < deadline:
            record = await self._store.get_record_by_key(cache_key)
            if record is not None:
                ready = self._check_record_state(record)
                if ready is not None:
                    return ready
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        raise TeachingUnitInProgressError("generating_in_progress")

    def _build_graph_sync(self, project: Project) -> ProjectGraph:
        return self._graph_builder_factory().build(project)

    async def _prerequisite_candidates(self, project_id: str) -> list[TeachingUnitRef]:
        units = await self._store.list_ready_by_project(project_id)
        return [TeachingUnitRef(project_id=project_id, teaching_unit_id=unit.id) for unit in units]


def _find_target_node(
    graph: ProjectGraph,
    target_type: TeachingTarget,
    target_id: str,
) -> ProjectNode:
    for node in graph.nodes:
        if node.id == target_id and _target_matches(node.type, target_type):
            return node
    raise TeachingUnitTargetNotFoundError("teaching_unit_target_not_found")


def _target_matches(node_type: NodeType, target_type: TeachingTarget) -> bool:
    mapping: dict[NodeType, TeachingTarget] = {
        NodeType.FILE_M: "file",
        NodeType.FILE_MAT: "file",
        NodeType.FILE_SLX: "model",
        NodeType.FUNCTION: "function",
        NodeType.BLOCK: "block",
        NodeType.SUBSYSTEM: "subsystem",
    }
    return mapping.get(node_type) == target_type


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, LLMRateLimitError | LLMServerError | LLMTimeoutError)
