"""Chunking service entry points."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Final, Protocol

from loguru import logger

from app.config import AppSettings
from core.domain.project import Project
from core.domain.project_graph import ProjectGraph
from core.interfaces.embedder import EmbeddingProvider
from core.interfaces.vector_store import ChunkRecord, VectorStore
from features.overview.overview_schemas import ProjectOverview

from . import _overview_chunker, _project_chunker
from ._chunk_draft import ChunkDraft
from ._errors import ChunkingError


class ProjectGraphProvider(Protocol):
    def build(self, project: Project) -> ProjectGraph:
        """Build a graph for chunking."""


class Clock(Protocol):
    def utcnow(self) -> datetime:
        """Return current UTC time."""


class _SystemClock:
    def utcnow(self) -> datetime:
        return datetime.utcnow()


class ChunkingService:
    """Project path stores 5 类 project chunks; overview path stores 1 overview chunk."""

    _DUP_CHUNK_ID_ARGS: Final[tuple[str, ...]] = ("chunk_id already exists",)

    def __init__(
        self,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        graph_provider: ProjectGraphProvider,
        settings: AppSettings,
        clock: Clock | None = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._graph_provider = graph_provider
        self._settings = settings
        self._clock = clock or _SystemClock()

    async def _embed_drafts(self, drafts: list[ChunkDraft]) -> list[list[float]]:
        source_texts = [draft.source_text for draft in drafts]
        embeddings = await asyncio.to_thread(self._embedder.embed, source_texts)
        if len(embeddings) != len(drafts):
            raise ChunkingError("embedding_count_mismatch")
        return embeddings

    async def build_embed_store_project_chunks(self, project: Project) -> int:
        if not project.m_files and not project.slx_models and not project.mat_files:
            logger.info("project_chunking_skipped: project_id={} reason=no_chunks", project.id)
            return 0

        graph = await asyncio.to_thread(self._graph_provider.build, project)
        drafts = _project_chunker.build_drafts(project, graph, self._settings)
        if not drafts:
            logger.info("project_chunking_skipped: project_id={} reason=no_chunks", project.id)
            return 0

        embeddings = await self._embed_drafts(drafts)
        chunks = [
            self._materialize(draft, embedding)
            for draft, embedding in zip(drafts, embeddings, strict=True)
        ]
        try:
            await self._vector_store.add_chunks(chunks)
        except ValueError as exc:
            if exc.args == self._DUP_CHUNK_ID_ARGS:
                logger.info(
                    "project_chunks_already_exist: project_id={} drafts_count={}",
                    project.id,
                    len(drafts),
                )
                return 0
            raise

        counts = _count_by_type(drafts)
        logger.info(
            "project_chunks_added: project_id={} m_file={} m_function={} "
            "slx_block={} slx_subsystem={} mat_variable={}",
            project.id,
            counts["m_file"],
            counts["m_function"],
            counts["slx_block"],
            counts["slx_subsystem"],
            counts["mat_variable"],
        )
        return len(chunks)

    async def build_embed_store_overview_chunk(
        self,
        overview: ProjectOverview,
        project_id: str,
    ) -> int:
        draft = _overview_chunker.build_draft(
            overview,
            project_id,
            self._settings.chunking_max_source_text_chars,
        )
        embeddings = await self._embed_drafts([draft])
        chunk = self._materialize(draft, embeddings[0])
        try:
            await self._vector_store.add_chunks([chunk])
        except ValueError as exc:
            if exc.args == self._DUP_CHUNK_ID_ARGS:
                logger.debug("overview_chunk_already_exists: project_id={}", project_id)
                return 0
            raise
        logger.info("overview_chunk_added: project_id={}", project_id)
        return 1

    def _materialize(self, draft: ChunkDraft, embedding: list[float]) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=draft.chunk_id,
            project_id=draft.project_id,
            source_type=draft.source_type,
            file_path=draft.file_path,
            symbol_name=draft.symbol_name,
            line_range=draft.line_range,
            block_id=draft.block_id,
            block_name=draft.block_name,
            block_type=draft.block_type,
            parent_subsystem=draft.parent_subsystem,
            source_text=draft.source_text,
            embedding=embedding,
            model_name=self._settings.embedding_model_name,
            created_at=self._clock.utcnow(),
        )

    async def aclose(self) -> None:
        """No resources are held by this service."""


def _count_by_type(drafts: list[ChunkDraft]) -> dict[str, int]:
    return {
        "m_file": sum(1 for draft in drafts if draft.source_type == "m_file"),
        "m_function": sum(1 for draft in drafts if draft.source_type == "m_function"),
        "slx_block": sum(1 for draft in drafts if draft.source_type == "slx_block"),
        "slx_subsystem": sum(1 for draft in drafts if draft.source_type == "slx_subsystem"),
        "mat_variable": sum(1 for draft in drafts if draft.source_type == "mat_variable"),
    }
