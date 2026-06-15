from __future__ import annotations

import json
from typing import Any, cast

from adapters.storage._connection import open_connection
from adapters.storage.schema import CURRENT_SCHEMA_VERSION, init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_teaching_unit_store import SqliteTeachingUnitStore
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit, TeachingUnitRef
from core.interfaces.teaching_unit_store import CacheKey, TeachingUnitStore


def _cache_key(
    project_id: str = "p1",
    target_id: str = "model.slx#b1",
    source_version: str = "source-v1",
) -> CacheKey:
    return (
        project_id,
        "block",
        target_id,
        "normal",
        "builder-v1",
        "prompt-v1",
        "deepseek-chat",
        source_version,
    )


def _unit(unit_id: str = "unit-1") -> TeachingUnit:
    kwargs: dict[str, Any] = {
        "id": unit_id,
        "title": "Gain 模块讲解",
        "target": "block",
        "target_id": "model.slx#b1",
        "level": "normal",
        "summary": "说明 Gain 如何影响闭环控制量。",
        "prerequisites": [
            TeachingUnitRef(project_id="p1", teaching_unit_id="project-overview")
        ],
        "explanation_steps": ["先定位输入信号", "再说明增益参数", "最后观察输出"],
        "knowledge_points": ["闭环控制", "比例增益"],
        "source_refs": [
            SourceRef(
                file_path="model.slx",
                block_id="b1",
                block_name="Gain",
                parent_subsystem="<root>",
            )
        ],
        "confusion_points": ["Gain 参数需要结合初始化脚本理解"],
    }
    return TeachingUnit(**cast(Any, kwargs))


async def _create_project(project_store: SqliteProjectStore, project_id: str = "p1") -> None:
    await project_store.create_pending(project_id, "demo.zip")


async def test_store_abc_has_six_abstract_methods() -> None:
    assert TeachingUnitStore.__abstractmethods__ == {
        "begin_generating",
        "delete_by_project",
        "get_record_by_key",
        "list_ready_by_project",
        "mark_failed",
        "mark_ready",
    }


async def test_begin_generating_creates_stateful_record(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()

    assert await store.begin_generating(key, now=100, expires_at=200) is True
    assert await store.begin_generating(key, now=101, expires_at=201) is False
    record = await store.get_record_by_key(key)

    assert record is not None
    assert record.cache_key == key
    assert record.state == "generating"
    assert record.unit is None
    assert record.error_code is None
    assert record.retry_count == 0
    assert record.expires_at == 200


async def test_mark_ready_round_trips_and_lists_ready_units(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()
    unit = _unit()

    assert await store.begin_generating(key, now=100, expires_at=200)
    await store.mark_ready(key, unit)

    record = await store.get_record_by_key(key)
    assert record is not None
    assert record.state == "ready"
    assert record.unit == unit
    assert await store.list_ready_by_project("p1") == [unit]


async def test_mark_failed_increments_retry_count_and_allows_retry(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()

    assert await store.begin_generating(key, now=100, expires_at=200)
    await store.mark_failed(key, "LLMTimeoutError", retryable=True)
    failed = await store.get_record_by_key(key)
    assert failed is not None
    assert failed.state == "failed_retryable"
    assert failed.error_code == "LLMTimeoutError"
    assert failed.retry_count == 1

    assert await store.begin_generating(key, now=110, expires_at=210)
    await store.mark_failed(key, "LLMServerError", retryable=True)
    failed_again = await store.get_record_by_key(key)
    assert failed_again is not None
    assert failed_again.retry_count == 2


async def test_failed_permanent_cannot_be_reclaimed(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()

    assert await store.begin_generating(key, now=100, expires_at=200)
    await store.mark_failed(key, "ValidationError", retryable=False)

    assert await store.begin_generating(key, now=110, expires_at=210) is False
    record = await store.get_record_by_key(key)
    assert record is not None
    assert record.state == "failed_permanent"
    assert record.retry_count == 1


async def test_cache_key_uses_all_eight_tuple_members(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key_v1 = _cache_key(source_version="source-v1")
    key_v2 = _cache_key(source_version="source-v2")

    assert await store.begin_generating(key_v1, now=100, expires_at=200)
    assert await store.begin_generating(key_v2, now=100, expires_at=200)

    assert (await store.get_record_by_key(key_v1)) is not None
    assert (await store.get_record_by_key(key_v2)) is not None


async def test_delete_project_cascades_teaching_units(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()
    assert await store.begin_generating(key, now=100, expires_at=200)
    await store.mark_ready(key, _unit())

    await project_store.delete("p1")

    assert await store.get_record_by_key(key) is None
    assert await store.list_ready_by_project("p1") == []


async def test_delete_by_project_returns_deleted_count(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()
    assert await store.begin_generating(key, now=100, expires_at=200)

    assert await store.delete_by_project("p1") == 1
    assert await store.delete_by_project("p1") == 0


async def test_payload_json_does_not_store_source_payloads(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await _create_project(project_store)
    store = SqliteTeachingUnitStore(initialized_db_path)
    key = _cache_key()
    assert await store.begin_generating(key, now=100, expires_at=200)
    await store.mark_ready(key, _unit())

    async with open_connection(initialized_db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT payload_json, source_refs_json FROM teaching_units WHERE project_id='p1'"
            )
        ).fetchone()

    assert row is not None
    payload = json.loads(row["payload_json"])
    assert set(payload) == {
        "confusion_points",
        "explanation_steps",
        "id",
        "knowledge_points",
        "summary",
        "title",
    }
    assert "raw_code" not in row["payload_json"]
    assert "source_text" not in row["payload_json"]
    assert json.loads(row["source_refs_json"]) == [
        {
            "block_id": "b1",
            "block_name": "Gain",
            "file_path": "model.slx",
            "line_range": None,
            "parameter_name": None,
            "parent_subsystem": "<root>",
        }
    ]


async def test_schema_migrates_v2_to_v3_and_preserves_existing_data(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        await conn.execute("DROP TABLE teaching_units")
        await conn.execute("UPDATE schema_version SET version=2")
        await conn.execute(
            "INSERT INTO project_status_record("
            "project_id, name, status, created_at, updated_at"
            ") VALUES ('p1', 'demo.zip', 'parsing', '2026-06-06T12:00:00', "
            "'2026-06-06T12:00:00')"
        )
        await conn.execute(
            "INSERT INTO chat_session(session_id, project_id, created_at, updated_at) "
            "VALUES ('s1', 'p1', '2026-06-06T12:00:00', '2026-06-06T12:00:00')"
        )
        await conn.execute(
            "INSERT INTO chat_message(message_id, session_id, role, content, created_at) "
            "VALUES ('m1', 's1', 'user', 'hello', '2026-06-06T12:00:01')"
        )
        await conn.execute(
            "INSERT INTO chunks("
            "chunk_id, project_id, source_type, file_path, source_text, embedding, "
            "embedding_dim, model_name, created_at"
            ") VALUES ('c1', 'p1', 'project_overview', 'overview.md', 'overview', "
            "?, 1, 'embedder', '2026-06-06T12:00:00')",
            (b"\x00\x00\x00\x00",),
        )
        await conn.commit()

    async with open_connection(db_path) as conn:
        await init_schema(conn)
        version = await (await conn.execute("SELECT version FROM schema_version")).fetchone()
        tables = await (
            await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        project_count = await (
            await conn.execute("SELECT COUNT(*) AS count FROM project_status_record")
        ).fetchone()
        session_count = await (
            await conn.execute("SELECT COUNT(*) AS count FROM chat_session")
        ).fetchone()
        message_count = await (
            await conn.execute("SELECT COUNT(*) AS count FROM chat_message")
        ).fetchone()
        chunk_count = await (
            await conn.execute("SELECT COUNT(*) AS count FROM chunks")
        ).fetchone()

    assert version is not None
    assert project_count is not None
    assert session_count is not None
    assert message_count is not None
    assert chunk_count is not None
    assert version["version"] == CURRENT_SCHEMA_VERSION
    assert "teaching_units" in {row["name"] for row in tables}
    assert project_count["count"] == 1
    assert session_count["count"] == 1
    assert message_count["count"] == 1
    assert chunk_count["count"] == 1
