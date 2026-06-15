from __future__ import annotations

import os
from dataclasses import fields
from datetime import datetime

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from core.domain.project import FileInfo, Project
from core.domain.project_graph import ProjectGraph
from core.interfaces.embedder import EmbeddingProvider
from core.interfaces.vector_store import ChunkRecord, QueryHit, VectorStore
from features.chunking import _project_chunker
from features.chunking._chunk_draft import ChunkDraft
from features.chunking._chunk_id import make_chunk_id, make_overview_chunk_id
from features.chunking._errors import ChunkingError
from features.chunking.chunking_service import ChunkingService
from tests.features.overview.conftest import make_domain_project_overview

RUN_INTEGRATION = os.getenv("RUN_EMBEDDING_INTEGRATION") == "1"


class FakeEmbedder(EmbeddingProvider):
    def __init__(self, dimension: int = 3, mismatch: bool = False) -> None:
        self._dimension = dimension
        self._mismatch = mismatch
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        count = max(len(texts) - 1, 0) if self._mismatch else len(texts)
        return [[1.0, 0.0, 0.0] for _ in range(count)]

    def dimension(self) -> int:
        return self._dimension


class FakeVectorStore(VectorStore):
    def __init__(self) -> None:
        self.chunks: list[ChunkRecord] = []
        self.delete_calls: list[str] = []

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        existing = {chunk.chunk_id for chunk in self.chunks}
        if any(chunk.chunk_id in existing for chunk in chunks):
            raise ValueError("chunk_id already exists")
        self.chunks.extend(chunks)

    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        _ = query_embedding, project_id, top_k, min_score
        return []

    async def delete_by_project_id(self, project_id: str) -> int:
        self.delete_calls.append(project_id)
        return 0

    async def get_chunk_count(self, project_id: str) -> int:
        return sum(1 for chunk in self.chunks if chunk.project_id == project_id)

    async def aclose(self) -> None:
        return None


class FakeGraphProvider:
    def __init__(self) -> None:
        self.calls = 0

    def build(self, project: Project) -> ProjectGraph:
        self.calls += 1
        return ProjectGraph(
            project_id=project.id,
            nodes=[],
            edges=[],
            entry_points=[],
            execution_flow=[],
            data_flow=[],
            control_flow=[],
            unresolved_symbols=[],
        )


class FixedClock:
    def utcnow(self) -> datetime:
        return datetime(2026, 6, 6, 12, 0, 0)


@pytest.fixture(scope="session")
def real_embedder() -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder()


def _service(
    chunk_settings,
    *,
    embedder: FakeEmbedder | None = None,
    vector_store: FakeVectorStore | None = None,
    graph_provider: FakeGraphProvider | None = None,
) -> ChunkingService:
    return ChunkingService(
        embedder=embedder or FakeEmbedder(),
        vector_store=vector_store or FakeVectorStore(),
        graph_provider=graph_provider or FakeGraphProvider(),
        settings=chunk_settings,
        clock=FixedClock(),
    )


def _attach_c_h_sources(project: Project, chunk_settings, tmp_path):
    upload_root = tmp_path / "uploads"
    project_root = upload_root / project.id
    (project_root / "src").mkdir(parents=True)
    (project_root / "include").mkdir(parents=True)
    (project_root / "src" / "controller.c").write_text(
        "static void controller(void) {\n    Phase = 90;\n}\n",
        encoding="utf-8",
    )
    (project_root / "include" / "controller.h").write_text(
        "typedef struct { float Kp; } PID;\nvoid pid_calc(PID *v);\n",
        encoding="utf-8",
    )
    project.files.extend(
        [
            FileInfo("src/controller.c", ".c", 42),
            FileInfo("include/controller.h", ".h", 58),
        ]
    )
    return chunk_settings.model_copy(update={"upload_dir": str(upload_root)})


def test_chunk_draft_has_storage_free_shape() -> None:
    assert {field.name for field in fields(ChunkDraft)} == {
        "chunk_id",
        "project_id",
        "source_type",
        "file_path",
        "symbol_name",
        "line_range",
        "block_id",
        "block_name",
        "block_type",
        "parent_subsystem",
        "source_text",
    }


def test_chunk_id_namespace_hash_and_empty_identifier() -> None:
    first = make_chunk_id("p1", "m_file", "a b.m")
    second = make_chunk_id("p1", "m_file", "a_b.m")

    assert first != second
    assert len(first.rsplit("::", 1)[1]) == 12
    assert make_overview_chunk_id("p1") == "p1::project_overview"
    with pytest.raises(ValueError, match="empty_chunk_identifier"):
        make_chunk_id("p1", "m_file")


def test_project_drafts_emit_seven_project_classes_and_flags(
    rich_project,
    chunk_settings,
    tmp_path,
) -> None:
    settings = _attach_c_h_sources(rich_project, chunk_settings, tmp_path)
    drafts = _project_chunker.build_drafts(
        rich_project,
        FakeGraphProvider().build(rich_project),
        settings,
    )
    by_type = {
        source_type: [draft for draft in drafts if draft.source_type == source_type]
        for source_type in {draft.source_type for draft in drafts}
    }

    assert set(by_type) == {
        "c_file",
        "h_file",
        "m_file",
        "m_function",
        "slx_block",
        "slx_subsystem",
        "mat_variable",
    }
    assert all(draft.source_type != "teaching_unit" for draft in drafts)
    assert by_type["m_file"][0].symbol_name is None
    assert len(by_type["c_file"]) == 1
    assert len(by_type["h_file"]) == 1
    assert len(by_type["slx_block"]) == 3
    assert any(",标记 library_link" in draft.source_text for draft in by_type["slx_block"])
    assert any(",标记 model_reference" in draft.source_text for draft in by_type["slx_block"])


async def test_service_materializes_and_stores_project_chunks(
    rich_project,
    chunk_settings,
    tmp_path,
) -> None:
    settings = _attach_c_h_sources(rich_project, chunk_settings, tmp_path)
    vector_store = FakeVectorStore()
    count = await _service(settings, vector_store=vector_store).build_embed_store_project_chunks(
        rich_project
    )

    assert count == 9
    assert await vector_store.get_chunk_count("p1") == 9
    assert vector_store.delete_calls == []
    assert {chunk.source_type for chunk in vector_store.chunks} == {
        "c_file",
        "h_file",
        "m_file",
        "m_function",
        "slx_block",
        "slx_subsystem",
        "mat_variable",
    }
    assert all(chunk.model_name == settings.embedding_model_name for chunk in vector_store.chunks)
    assert all(chunk.created_at is not None for chunk in vector_store.chunks)


async def test_project_duplicate_is_noop_without_delete(
    rich_project,
    chunk_settings,
    tmp_path,
) -> None:
    settings = _attach_c_h_sources(rich_project, chunk_settings, tmp_path)
    vector_store = FakeVectorStore()
    service = _service(settings, vector_store=vector_store)

    assert await service.build_embed_store_project_chunks(rich_project) == 9
    assert await service.build_embed_store_project_chunks(rich_project) == 0
    assert await vector_store.get_chunk_count("p1") == 9
    assert vector_store.delete_calls == []


async def test_empty_project_does_not_embed(empty_project, chunk_settings) -> None:
    embedder = FakeEmbedder()
    graph_provider = FakeGraphProvider()

    count = await _service(
        chunk_settings,
        embedder=embedder,
        graph_provider=graph_provider,
    ).build_embed_store_project_chunks(empty_project)

    assert count == 0
    assert embedder.calls == []
    assert graph_provider.calls == 0


async def test_embedding_count_mismatch_raises(rich_project, chunk_settings) -> None:
    service = _service(chunk_settings, embedder=FakeEmbedder(mismatch=True))

    with pytest.raises(ChunkingError, match="embedding_count_mismatch"):
        await service.build_embed_store_project_chunks(rich_project)


async def test_overview_chunk_is_independent_and_duplicate_noop(chunk_settings) -> None:
    vector_store = FakeVectorStore()
    service = _service(chunk_settings, vector_store=vector_store)
    overview = make_domain_project_overview()

    assert await service.build_embed_store_overview_chunk(overview, "p1") == 1
    assert await service.build_embed_store_overview_chunk(overview, "p1") == 0
    assert await vector_store.get_chunk_count("p1") == 1
    assert vector_store.chunks[0].source_type == "project_overview"


def test_source_text_total_truncates(rich_project, chunk_settings) -> None:
    settings = chunk_settings.model_copy(update={"chunking_max_source_text_chars": 64})
    rich_project.files[0].description = "很长" * 200

    drafts = _project_chunker.build_drafts(
        rich_project, FakeGraphProvider().build(rich_project), settings
    )

    assert max(len(draft.source_text) for draft in drafts) <= 64
    assert any(draft.source_text.endswith("[…]") for draft in drafts)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="Set RUN_EMBEDDING_INTEGRATION=1 to run real embedding model tests.",
)
async def test_real_embedder_project_chunking_smoke(
    rich_project,
    chunk_settings,
    real_embedder: SentenceTransformerEmbedder,
) -> None:
    vector_store = FakeVectorStore()
    count = await _service(
        chunk_settings,
        embedder=real_embedder,
        vector_store=vector_store,
    ).build_embed_store_project_chunks(rich_project)

    assert count == 7
    assert all(len(chunk.embedding) == 512 for chunk in vector_store.chunks)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="Set RUN_EMBEDDING_INTEGRATION=1 to run real embedding model tests.",
)
async def test_real_embedder_overview_chunking_smoke(
    chunk_settings,
    real_embedder: SentenceTransformerEmbedder,
) -> None:
    vector_store = FakeVectorStore()
    overview = make_domain_project_overview()

    count = await _service(
        chunk_settings,
        embedder=real_embedder,
        vector_store=vector_store,
    ).build_embed_store_overview_chunk(overview, "p1")

    assert count == 1
    assert len(vector_store.chunks[0].embedding) == 512
