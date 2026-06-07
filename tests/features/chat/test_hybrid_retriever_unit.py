from __future__ import annotations

from datetime import datetime
from typing import get_type_hints

import pytest

from core.domain.exceptions import EmbeddingError, VectorStoreError
from core.domain.project import Project, ProjectType
from core.domain.source_ref import SourceRef
from core.interfaces.vector_store import ChunkRecord
from features.chat._hybrid_retriever import HybridRetriever
from features.chat._retriever import RetrievalHit, Retriever


class FakeRetriever(Retriever):
    def __init__(
        self,
        hits: list[RetrievalHit] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.exc = exc
        self.calls: list[tuple[str, int]] = []

    async def search(
        self,
        project: Project,
        query: str,
        top_k: int = 8,
    ) -> list[RetrievalHit]:
        self.calls.append((query, top_k))
        if self.exc is not None:
            raise self.exc
        return self.hits


class FakeVectorStore:
    def __init__(self, count: int = 1, exc: Exception | None = None) -> None:
        self.count = count
        self.exc = exc
        self.calls: list[str] = []

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        raise NotImplementedError

    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list:
        raise NotImplementedError

    async def delete_by_project_id(self, project_id: str) -> int:
        raise NotImplementedError

    async def get_chunk_count(self, project_id: str) -> int:
        self.calls.append(project_id)
        if self.exc is not None:
            raise self.exc
        return self.count

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


def _hit(source_type: str = "file") -> RetrievalHit:
    return RetrievalHit(
        source_ref=SourceRef(file_path="model.slx"),
        score=1.0,
        snippet="model",
        source_type=source_type,
    )


def _capture_fallback_logs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, ...]]:
    logs: list[tuple[object, ...]] = []

    def fake_info(message: str, *args: object) -> None:
        logs.append((message, *args))

    monkeypatch.setattr("features.chat._hybrid_retriever.logger.info", fake_info)
    return logs


@pytest.mark.asyncio
async def test_fallback_when_chunk_count_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = _capture_fallback_logs(monkeypatch)
    vector = FakeRetriever([_hit("overview")])
    keyword = FakeRetriever([_hit("file")])

    results = await HybridRetriever(
        vector, keyword, FakeVectorStore(count=0), min_chunk_count=1
    ).search(_project(), "速度", top_k=4)

    assert results == [_hit("file")]
    assert vector.calls == []
    assert keyword.calls == [("速度", 4)]
    assert logs[0][2] == "chunk_count_below_threshold"


@pytest.mark.asyncio
async def test_fallback_when_get_chunk_count_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = _capture_fallback_logs(monkeypatch)
    keyword = FakeRetriever([_hit("file")])

    results = await HybridRetriever(
        FakeRetriever([_hit("overview")]),
        keyword,
        FakeVectorStore(exc=VectorStoreError("sqlite_operation_failed")),
    ).search(_project(), "速度")

    assert results == [_hit("file")]
    assert keyword.calls == [("速度", 8)]
    assert logs[0][2] == "get_chunk_count_failed"
    assert logs[0][4] == "VectorStoreError"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [VectorStoreError("sqlite_operation_failed"), EmbeddingError("embedding_failed")],
)
async def test_fallback_when_vector_search_failed(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    logs = _capture_fallback_logs(monkeypatch)
    keyword = FakeRetriever([_hit("file")])

    results = await HybridRetriever(
        FakeRetriever(exc=exc),
        keyword,
        FakeVectorStore(count=2),
    ).search(_project(), "速度", top_k=3)

    assert results == [_hit("file")]
    assert keyword.calls == [("速度", 3)]
    assert logs[0][2] == "vector_search_failed"
    assert logs[0][4] == type(exc).__name__


@pytest.mark.asyncio
async def test_fallback_when_vector_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = _capture_fallback_logs(monkeypatch)
    keyword = FakeRetriever([_hit("file")])

    results = await HybridRetriever(
        FakeRetriever([]),
        keyword,
        FakeVectorStore(count=2),
    ).search(_project(), "速度")

    assert results == [_hit("file")]
    assert keyword.calls == [("速度", 8)]
    assert logs[0][2] == "vector_empty_hits"


@pytest.mark.asyncio
async def test_normal_path_returns_vector_hits_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = _capture_fallback_logs(monkeypatch)
    vector = FakeRetriever([_hit("overview")])
    keyword = FakeRetriever([_hit("file")])

    results = await HybridRetriever(vector, keyword, FakeVectorStore(count=2)).search(
        _project(), "速度", top_k=5
    )

    assert results == [_hit("overview")]
    assert vector.calls == [("速度", 5)]
    assert keyword.calls == []
    assert logs == []


@pytest.mark.asyncio
async def test_value_error_is_not_caught() -> None:
    retriever = HybridRetriever(
        FakeRetriever(exc=ValueError("top_k out of range")),
        FakeRetriever([_hit("file")]),
        FakeVectorStore(count=2),
    )

    with pytest.raises(ValueError, match="top_k out of range"):
        await retriever.search(_project(), "速度")


@pytest.mark.asyncio
async def test_init_accepts_retriever_abc_types() -> None:
    type_hints = get_type_hints(HybridRetriever.__init__)

    assert type_hints["vector"] is Retriever
    assert type_hints["keyword"] is Retriever

    retriever = HybridRetriever(
        vector=FakeRetriever([_hit("overview")]),
        keyword=FakeRetriever([_hit("file")]),
        vector_store=FakeVectorStore(count=1),
    )

    assert await retriever.search(_project(), "速度") == [_hit("overview")]
