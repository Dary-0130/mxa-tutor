from __future__ import annotations

import threading
from datetime import datetime

import pytest

from core.domain.exceptions import EmbeddingError, VectorStoreError
from core.domain.project import Project, ProjectType
from core.interfaces.vector_store import ChunkRecord, QueryHit
from features.chat._vector_retriever import VectorRetriever

_PROJECT_OVERVIEW_SOURCE_TYPE = "project_" + "overview"


class FakeEmbedder:
    def __init__(
        self,
        vector: list[float] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.vector = vector or [1.0, 0.0]
        self.exc = exc
        self.thread_names: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.thread_names.append(threading.current_thread().name)
        if self.exc is not None:
            raise self.exc
        assert texts == ["速度控制器"]
        return [self.vector]

    def dimension(self) -> int:
        return len(self.vector)


class FakeVectorStore:
    def __init__(
        self,
        hits: list[QueryHit] | None = None,
        query_exc: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.query_exc = query_exc
        self.calls: list[tuple[list[float], str, int, float]] = []

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        raise NotImplementedError

    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        self.calls.append((query_embedding, project_id, top_k, min_score))
        if self.query_exc is not None:
            raise self.query_exc
        return self.hits

    async def delete_by_project_id(self, project_id: str) -> int:
        raise NotImplementedError

    async def get_chunk_count(self, project_id: str) -> int:
        return len(self.hits)

    async def aclose(self) -> None:
        return None


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


def _chunk(
    source_type: str,
    chunk_id: str | None = None,
    *,
    file_path: str = "model.slx",
    symbol_name: str | None = None,
    block_type: str | None = None,
    source_text: str = "chunk text",
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id or source_type,
        project_id="p1",
        source_type=source_type,
        file_path=file_path,
        symbol_name=symbol_name,
        line_range=(2, 4),
        block_id="b1" if source_type in {"slx_block", "slx_subsystem"} else None,
        block_name="SpeedController" if source_type in {"slx_block", "slx_subsystem"} else None,
        block_type=block_type,
        parent_subsystem="SpeedLoop" if source_type in {"slx_block", "slx_subsystem"} else None,
        source_text=source_text,
        embedding=[1.0, 0.0],
        model_name="fake",
    )


async def _search(hits: list[QueryHit]) -> list:
    return await VectorRetriever(FakeEmbedder(), FakeVectorStore(hits)).search(
        _project(), "速度控制器"
    )


@pytest.mark.asyncio
async def test_maps_chunk_source_types_to_retrieval_source_types() -> None:
    source_types = {
        "m_file": "file",
        "m_function": "function",
        "slx_block": "block",
        "slx_subsystem": "subsystem",
        "mat_variable": "param",
        _PROJECT_OVERVIEW_SOURCE_TYPE: "overview",
    }
    hits = [QueryHit(_chunk(source_type), 0.9) for source_type in source_types]

    results = await _search(hits)

    assert [result.source_type for result in results] == list(source_types.values())


@pytest.mark.asyncio
async def test_unknown_source_type_raises_value_error() -> None:
    hits = [QueryHit(_chunk("teaching_unit"), 0.9)]

    with pytest.raises(ValueError, match="unknown_source_type:teaching_unit"):
        await _search(hits)


@pytest.mark.asyncio
async def test_embed_runs_in_worker_thread() -> None:
    embedder = FakeEmbedder()
    store = FakeVectorStore([])
    main_thread = threading.current_thread().name

    await VectorRetriever(embedder, store).search(_project(), "速度控制器")

    assert embedder.thread_names
    assert embedder.thread_names[0] != main_thread


@pytest.mark.asyncio
async def test_empty_query_hits_returns_empty_list() -> None:
    results = await _search([])

    assert results == []


@pytest.mark.asyncio
async def test_dedupes_by_chunk_id_only() -> None:
    hits = [
        QueryHit(_chunk("m_file", chunk_id="same", file_path="a.m"), 0.9),
        QueryHit(_chunk("m_file", chunk_id="same", file_path="b.m"), 0.8),
    ]

    results = await _search(hits)

    assert len(results) == 1
    assert results[0].source_ref.file_path == "a.m"


@pytest.mark.asyncio
async def test_parameter_validation_rejects_invalid_values() -> None:
    retriever = VectorRetriever(FakeEmbedder(), FakeVectorStore([]))

    with pytest.raises(ValueError, match="top_k out of range"):
        await retriever.search(_project(), "速度控制器", top_k=0)
    with pytest.raises(ValueError, match="top_k out of range"):
        await retriever.search(_project(), "速度控制器", top_k=51)
    with pytest.raises(ValueError, match="min_score out of range"):
        VectorRetriever(FakeEmbedder(), FakeVectorStore([]), min_score=2.0)
    with pytest.raises(ValueError, match="min_score out of range"):
        VectorRetriever(FakeEmbedder(), FakeVectorStore([]), min_score=-1.5)


@pytest.mark.asyncio
async def test_embedding_error_and_vector_store_error_are_not_swallowed() -> None:
    embedding_error = EmbeddingError("embedding_failed")
    with pytest.raises(EmbeddingError) as embed_info:
        await VectorRetriever(FakeEmbedder(exc=embedding_error), FakeVectorStore([])).search(
            _project(), "速度控制器"
        )
    assert embed_info.value is embedding_error

    vector_store_error = VectorStoreError("sqlite_operation_failed")
    with pytest.raises(VectorStoreError) as store_info:
        await VectorRetriever(FakeEmbedder(), FakeVectorStore(query_exc=vector_store_error)).search(
            _project(), "速度控制器"
        )
    assert store_info.value is vector_store_error


@pytest.mark.asyncio
async def test_wraps_raw_embed_exception_as_embedding_error() -> None:
    raw_error = RuntimeError("model loaded fail")

    with pytest.raises(EmbeddingError) as exc_info:
        await VectorRetriever(FakeEmbedder(exc=raw_error), FakeVectorStore([])).search(
            _project(), "速度控制器"
        )

    assert str(exc_info.value) == "embed_failed:RuntimeError"
    assert exc_info.value.__cause__ is raw_error


@pytest.mark.asyncio
async def test_snippet_is_truncated_with_ellipsis() -> None:
    results = await _search([QueryHit(_chunk("m_file", source_text="x" * 500), 0.9)])

    assert len(results[0].snippet) == 300
    assert results[0].snippet.endswith("…")


@pytest.mark.asyncio
async def test_block_type_only_passes_for_block_hits() -> None:
    results = await _search(
        [
            QueryHit(_chunk("slx_block", block_type="Gain"), 0.9),
            QueryHit(_chunk("slx_subsystem", block_type="SubSystem"), 0.8),
        ]
    )

    assert results[0].source_type == "block"
    assert results[0].block_type == "Gain"
    assert results[1].source_type == "subsystem"
    assert results[1].block_type is None


@pytest.mark.asyncio
async def test_mat_variable_symbol_name_maps_to_parameter_name() -> None:
    results = await _search([QueryHit(_chunk("mat_variable", symbol_name="omega_ref"), 0.9)])

    assert results[0].source_type == "param"
    assert results[0].source_ref.parameter_name == "omega_ref"


@pytest.mark.asyncio
async def test_controlled_non_block_source_types_are_preserved() -> None:
    results = await _search(
        [
            QueryHit(_chunk("slx_subsystem", block_type="SubSystem"), 0.9),
            QueryHit(
                _chunk(
                    _PROJECT_OVERVIEW_SOURCE_TYPE,
                    file_path="__project_overview__",
                    symbol_name="MyProject",
                ),
                0.8,
            ),
        ]
    )

    assert {result.source_type for result in results} == {"subsystem", "overview"}


@pytest.mark.asyncio
async def test_project_overview_sentinel_is_passed_through() -> None:
    results = await _search(
        [
            QueryHit(
                _chunk(
                    _PROJECT_OVERVIEW_SOURCE_TYPE,
                    file_path="__project_overview__",
                    symbol_name="MyProject",
                ),
                0.9,
            )
        ]
    )

    assert results[0].source_ref.file_path == "__project_overview__"
    assert results[0].source_type == "overview"
