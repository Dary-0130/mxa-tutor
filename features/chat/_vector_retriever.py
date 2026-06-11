"""Dense vector retriever using EmbeddingProvider and VectorStore."""

from __future__ import annotations

import asyncio

from loguru import logger

from core.domain.exceptions import EmbeddingError
from core.domain.project import Project
from core.domain.source_ref import SourceRef
from core.interfaces.embedder import EmbeddingProvider
from core.interfaces.vector_store import QueryHit, VectorStore
from features.chat._retriever import RetrievalHit, Retriever, SourceType

_SOURCE_TYPE_MAP: dict[str, SourceType] = {
    "c_file": "function",
    "h_file": "function",
    "m_file": "file",
    "m_function": "function",
    "mat_variable": "param",
    "project_overview": "overview",
    "slx_block": "block",
    "slx_subsystem": "subsystem",
}

_SNIPPET_MAX_CHARS = 300
_MIN_SCORE_LO = -1.0
_MIN_SCORE_HI = 1.0
_TOP_K_LO = 1
_TOP_K_HI = 50


class VectorRetriever(Retriever):
    """Retrieve project context by embedding the query and searching chunks."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        min_score: float = 0.3,
    ) -> None:
        if min_score < _MIN_SCORE_LO or min_score > _MIN_SCORE_HI:
            raise ValueError("min_score out of range")
        self._embedder = embedder
        self._vector_store = vector_store
        self._min_score = min_score

    async def search(
        self,
        project: Project,
        query: str,
        top_k: int = 8,
    ) -> list[RetrievalHit]:
        """Search vector chunks and convert them to ChatService retrieval hits."""
        if top_k < _TOP_K_LO or top_k > _TOP_K_HI:
            raise ValueError("top_k out of range")

        try:
            embeddings = await asyncio.to_thread(self._embedder.embed, [query])
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"embed_failed:{type(exc).__name__}") from exc

        if not embeddings or len(embeddings[0]) != self._embedder.dimension():
            raise EmbeddingError("embed_returned_invalid_shape")

        query_hits = await self._vector_store.query(
            query_embedding=embeddings[0],
            project_id=project.id,
            top_k=top_k,
            min_score=self._min_score,
        )

        seen_chunk_ids: set[str] = set()
        deduped: list[QueryHit] = []
        for query_hit in query_hits:
            if query_hit.chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(query_hit.chunk.chunk_id)
            deduped.append(query_hit)

        hits = [self._to_retrieval_hit(query_hit) for query_hit in deduped]
        logger.debug(
            "VectorRetriever.search: project_id={} hit_count={} top_k={}",
            project.id,
            len(hits),
            top_k,
        )
        return hits

    @staticmethod
    def _to_retrieval_hit(query_hit: QueryHit) -> RetrievalHit:
        chunk = query_hit.chunk
        mapped_type = _SOURCE_TYPE_MAP.get(chunk.source_type)
        if mapped_type is None:
            raise ValueError(f"unknown_source_type:{chunk.source_type}")

        source_ref = SourceRef(
            file_path=chunk.file_path,
            line_range=chunk.line_range,
            block_id=chunk.block_id,
            block_name=chunk.block_name,
            parent_subsystem=chunk.parent_subsystem,
            parameter_name=chunk.symbol_name if mapped_type == "param" else None,
        )

        snippet = chunk.source_text
        if len(snippet) > _SNIPPET_MAX_CHARS:
            snippet = snippet[: _SNIPPET_MAX_CHARS - 1] + "…"

        return RetrievalHit(
            source_ref=source_ref,
            score=query_hit.score,
            snippet=snippet,
            source_type=mapped_type,
            block_type=chunk.block_type if mapped_type == "block" else None,
        )
