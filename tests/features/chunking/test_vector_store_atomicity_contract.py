from __future__ import annotations

from datetime import datetime

import aiosqlite
import pytest

from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from core.domain.exceptions import VectorStoreError
from core.domain.project import Project, ProjectType
from core.interfaces.vector_store import ChunkRecord


def _project(project_id: str) -> Project:
    return Project(
        id=project_id,
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime(2026, 6, 6, 0, 0, 0),
        file_dependencies={},
    )


def _chunk(chunk_id: str, project_id: str = "p1") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        project_id=project_id,
        source_type="m_file",
        file_path="main.m",
        symbol_name=None,
        line_range=None,
        block_id=None,
        block_name=None,
        block_type=None,
        parent_subsystem=None,
        source_text=f"chunk {chunk_id}",
        embedding=[1.0, 0.0, 0.0],
        model_name="fake-model",
        created_at=datetime(2026, 6, 6, 0, 0, 0),
    )


async def _ready_db(db_path: str, project_id: str = "p1") -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    project_store = SqliteProjectStore(db_path)
    await project_store.create_pending(project_id, "demo.zip")
    await project_store.mark_ready(project_id, _project(project_id))
    await project_store.aclose()


async def test_add_chunks_operational_error_rolls_back_batch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = str(tmp_path / "chunks.db")
    await _ready_db(db_path)
    vector_store = SqliteVectorStore(db_path)
    original = aiosqlite.core.Connection.executemany

    async def fail_after_insert(self, sql, parameters):
        result = await original(self, sql, parameters)
        if "INSERT INTO chunks(" in sql:
            raise aiosqlite.OperationalError("boom")
        return result

    monkeypatch.setattr(aiosqlite.core.Connection, "executemany", fail_after_insert)

    with pytest.raises(VectorStoreError) as exc_info:
        await vector_store.add_chunks([_chunk("c1"), _chunk("c2")])

    assert exc_info.value.args == ("sqlite_operation_failed",)
    assert await vector_store.get_chunk_count("p1") == 0

    monkeypatch.setattr(aiosqlite.core.Connection, "executemany", original)
    await vector_store.add_chunks([_chunk("c1"), _chunk("c2")])
    assert await vector_store.get_chunk_count("p1") == 2


async def test_add_chunks_duplicate_rolls_back_new_rows(tmp_path) -> None:
    db_path = str(tmp_path / "chunks.db")
    await _ready_db(db_path)
    vector_store = SqliteVectorStore(db_path)

    await vector_store.add_chunks([_chunk("existing")])
    with pytest.raises(ValueError) as exc_info:
        await vector_store.add_chunks([_chunk("new"), _chunk("existing")])

    assert exc_info.value.args == ("chunk_id already exists",)
    assert await vector_store.get_chunk_count("p1") == 1
