from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite
import pytest

from adapters.storage._connection import open_connection
from adapters.storage._vector_codec import decode_vector, encode_vector
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from core.domain.exceptions import ProjectNotFoundError, VectorStoreError
from core.interfaces.vector_store import ChunkRecord, VectorStore


def _chunk(
    chunk_id: str = "c1",
    project_id: str = "p1",
    embedding: list[float] | None = None,
    model_name: str = "model-a",
    line_range: tuple[int, int] | None = (1, 3),
    created_at: datetime | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        project_id=project_id,
        source_type="m_function",
        file_path="src/controller.m",
        symbol_name="controller",
        line_range=line_range,
        block_id=None,
        block_name=None,
        block_type=None,
        parent_subsystem=None,
        source_text=f"chunk {chunk_id}",
        embedding=embedding or [1.0, 0.0],
        model_name=model_name,
        created_at=created_at,
    )


async def _create_project(store: SqliteProjectStore, project_id: str = "p1") -> None:
    await store.create_pending(project_id, "demo.zip")


async def _insert_raw_chunk(
    db_path: str,
    *,
    chunk_id: str,
    project_id: str = "p1",
    line_start: int | None = 1,
    line_end: int | None = 3,
    created_at: str = "2026-06-06T12:00:00",
    embedding: list[float] | None = None,
    embedding_dim: int | None = None,
) -> None:
    vector = embedding or [1.0, 0.0]
    async with open_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO chunks("
            "chunk_id, project_id, source_type, file_path, symbol_name, "
            "line_start, line_end, block_id, block_name, block_type, "
            "parent_subsystem, source_text, embedding, embedding_dim, model_name, created_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                chunk_id,
                project_id,
                "m_function",
                "src/controller.m",
                "controller",
                line_start,
                line_end,
                None,
                None,
                None,
                None,
                "raw chunk",
                encode_vector(vector),
                embedding_dim or len(vector),
                "model-a",
                created_at,
            ),
        )
        await conn.commit()


def test_vector_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        VectorStore()


async def test_add_query_round_trip_returns_full_chunk(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    created_at = datetime(2026, 6, 6, 12, 0, 0)
    chunk = _chunk(created_at=created_at)

    await store.add_chunks([chunk])
    hits = await store.query([1.0, 0.0], "p1", top_k=1, min_score=-1.0)

    assert await store.get_chunk_count("p1") == 1
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].chunk == chunk


async def test_delete_and_fk_cascade_paths(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store, "p1")
    await _create_project(project_store, "p2")
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks([_chunk("c1", "p1"), _chunk("c2", "p1"), _chunk("c3", "p2")])

    assert await store.delete_by_project_id("p1") == 2
    assert await store.get_chunk_count("p1") == 0

    await store.add_chunks([_chunk("c4", "p2")])
    await project_store.delete("p2")
    assert await store.get_chunk_count("p2") == 0


async def test_true_cosine_top_k_min_score_and_zero_query(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks(
        [
            _chunk("dot-would-win", embedding=[10.0, 0.0]),
            _chunk("cosine-wins", embedding=[2.0, 2.0]),
            _chunk("negative", embedding=[-1.0, 0.0]),
            _chunk("zero", embedding=[0.0, 0.0]),
        ]
    )

    hits = await store.query([1.0, 1.0], "p1", top_k=2, min_score=-1.0)
    filtered = await store.query([1.0, 1.0], "p1", top_k=4, min_score=0.8)
    zero_hits = await store.query([0.0, 0.0], "p1", top_k=4, min_score=-1.0)

    assert [hit.chunk.chunk_id for hit in hits] == ["cosine-wins", "dot-would-win"]
    assert [hit.chunk.chunk_id for hit in filtered] == ["cosine-wins"]
    assert {hit.score for hit in zero_hits} == {0.0}


async def test_blob_codec_and_query_dimension_checks(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    assert encode_vector([1.0]) == b"\x00\x00\x80?"
    assert decode_vector(encode_vector([1.0, 2.0]), 2) == [1.0, 2.0]
    with pytest.raises(VectorStoreError, match="blob_length_mismatch"):
        decode_vector(b"abc", 1)
    with pytest.raises(VectorStoreError, match="blob_length_mismatch"):
        decode_vector(encode_vector([1.0]), 2)

    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks([_chunk()])
    with pytest.raises(VectorStoreError, match="query_dim_mismatch"):
        await store.query([1.0, 0.0, 0.0], "p1", min_score=-1.0)


async def test_line_range_nullable_rules(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks([_chunk("none-range", line_range=None)])

    hits = await store.query([1.0, 0.0], "p1", min_score=-1.0)
    assert hits[0].chunk.line_range is None

    await _insert_raw_chunk(
        initialized_db_path,
        chunk_id="bad-range",
        line_start=None,
        line_end=7,
    )
    with pytest.raises(VectorStoreError, match="invalid_line_range"):
        await store.query([1.0, 0.0], "p1", min_score=-1.0)


async def test_created_at_rules(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    before = datetime.utcnow()
    explicit = datetime(2026, 6, 6, 12, 30, 0)
    await store.add_chunks(
        [_chunk("auto-time", created_at=None), _chunk("explicit", created_at=explicit)]
    )

    hits = await store.query([1.0, 0.0], "p1", top_k=2, min_score=-1.0)
    by_id = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    assert before <= by_id["auto-time"].created_at <= datetime.utcnow()
    assert by_id["explicit"].created_at == explicit

    await _insert_raw_chunk(initialized_db_path, chunk_id="bad-time", created_at="not-a-date")
    with pytest.raises(VectorStoreError, match="invalid_created_at"):
        await store.query([1.0, 0.0], "p1", min_score=-1.0)


async def test_query_empty_data_semantics_and_write_path_project_check(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)

    assert await store.query([1.0, 2.0, 3.0], "p1") == []
    assert await store.query([1.0, 2.0, 3.0], "missing") == []
    with pytest.raises(ProjectNotFoundError):
        await store.add_chunks([_chunk(project_id="missing")])


async def test_mixed_dimension_and_model_rules(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks([_chunk("first", embedding=[1.0, 0.0], model_name="model-a")])

    with pytest.raises(ValueError, match="mixed_embedding_dim"):
        await store.add_chunks(
            [_chunk("mixed-a", embedding=[1.0, 0.0]), _chunk("mixed-b", embedding=[1.0])]
        )
    with pytest.raises(VectorStoreError, match="embedding_dim_mismatch"):
        await store.add_chunks([_chunk("wrong-dim", embedding=[1.0, 0.0, 0.0])])

    await store.add_chunks([_chunk("same-dim-other-model", embedding=[0.0, 1.0], model_name="b")])
    assert await store.get_chunk_count("p1") == 2


async def test_add_chunks_duplicate_and_operational_error(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)
    await store.add_chunks([_chunk("dupe")])
    with pytest.raises(ValueError, match="chunk_id already exists"):
        await store.add_chunks([_chunk("dupe")])

    class BrokenConnection:
        async def execute(self, *_args: object) -> None:
            raise aiosqlite.OperationalError("boom")

        async def rollback(self) -> None:
            pass

    @asynccontextmanager
    async def broken_open_connection(_db_path: str) -> AsyncIterator[BrokenConnection]:
        yield BrokenConnection()

    monkeypatch.setattr(
        "adapters.storage.sqlite_vector_store.open_connection",
        broken_open_connection,
    )
    with pytest.raises(VectorStoreError, match="sqlite_operation_failed"):
        await store.add_chunks([_chunk("op-error")])


async def test_query_runtime_bounds(
    initialized_db_path: str,
    project_store: SqliteProjectStore,
) -> None:
    await _create_project(project_store)
    store = SqliteVectorStore(initialized_db_path)

    for top_k in (0, 51):
        with pytest.raises(ValueError, match="invalid top_k"):
            await store.query([1.0], "p1", top_k=top_k)
    for min_score in (-1.1, 1.1):
        with pytest.raises(ValueError, match="invalid min_score"):
            await store.query([1.0], "p1", min_score=min_score)
