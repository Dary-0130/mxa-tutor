"""Hybrid retriever with vector main path and keyword fallback."""

from __future__ import annotations

from typing import Literal

from loguru import logger

from core.domain.exceptions import EmbeddingError, VectorStoreError
from core.domain.project import Project
from core.interfaces.vector_store import VectorStore
from features.chat._retriever import RetrievalHit, Retriever

FallbackReason = Literal[
    "chunk_count_below_threshold",
    "get_chunk_count_failed",
    "vector_search_failed",
    "vector_empty_hits",
]


class HybridRetriever(Retriever):
    """Use vector retrieval when chunks are ready, otherwise fall back to keyword."""

    def __init__(
        self,
        vector: Retriever,
        keyword: Retriever,
        vector_store: VectorStore,
        min_chunk_count: int = 1,
    ) -> None:
        self._vector = vector
        self._keyword = keyword
        self._vector_store = vector_store
        self._min_chunk_count = min_chunk_count

    async def search(
        self,
        project: Project,
        query: str,
        top_k: int = 8,
    ) -> list[RetrievalHit]:
        """Search with vector retrieval and fall back to keyword on retriever failures."""
        try:
            chunk_count = await self._vector_store.get_chunk_count(project.id)
        except VectorStoreError as exc:
            return await self._fallback(
                project,
                query,
                top_k,
                fallback_reason="get_chunk_count_failed",
                exc_class=type(exc).__name__,
            )

        if chunk_count < self._min_chunk_count:
            return await self._fallback(
                project,
                query,
                top_k,
                fallback_reason="chunk_count_below_threshold",
                chunk_count=chunk_count,
            )

        try:
            hits = await self._vector.search(project, query, top_k)
        except (VectorStoreError, EmbeddingError) as exc:
            return await self._fallback(
                project,
                query,
                top_k,
                fallback_reason="vector_search_failed",
                chunk_count=chunk_count,
                exc_class=type(exc).__name__,
            )

        if not hits:
            return await self._fallback(
                project,
                query,
                top_k,
                fallback_reason="vector_empty_hits",
                chunk_count=chunk_count,
            )

        return hits

    async def _fallback(
        self,
        project: Project,
        query: str,
        top_k: int,
        *,
        fallback_reason: FallbackReason,
        chunk_count: int | None = None,
        exc_class: str | None = None,
    ) -> list[RetrievalHit]:
        logger.info(
            "HybridRetriever.fallback: project_id={} fallback_reason={} chunk_count={} "
            "exc_class={}",
            project.id,
            fallback_reason,
            chunk_count,
            exc_class,
        )
        return await self._keyword.search(project, query, top_k)
