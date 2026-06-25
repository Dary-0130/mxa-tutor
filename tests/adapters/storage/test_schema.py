import pytest

from adapters.storage._connection import open_connection
from adapters.storage.schema import CURRENT_SCHEMA_VERSION, init_schema
from core.domain.exceptions import StoreError


async def test_init_schema_creates_tables_and_version(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row["name"] for row in await cur.fetchall()}
        version_cur = await conn.execute("SELECT id, version FROM schema_version")
        version = await version_cur.fetchone()

    assert {
        "bridge_run_state_run",
        "bridge_run_state_session",
        "chunks",
        "chat_message",
        "chat_session",
        "project_status_record",
        "schema_version",
    }.issubset(tables)
    assert dict(version) == {"id": 1, "version": CURRENT_SCHEMA_VERSION}


async def test_init_schema_is_idempotent(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        cur = await conn.execute("SELECT COUNT(*) AS count FROM schema_version")
        row = await cur.fetchone()

    assert row["count"] == 1


async def test_init_schema_rejects_newer_schema_version(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        await conn.execute("UPDATE schema_version SET version=?", (CURRENT_SCHEMA_VERSION + 1,))
        await conn.commit()

    async with open_connection(db_path) as conn:
        with pytest.raises(StoreError, match="unsupported_schema_version"):
            await init_schema(conn)


async def test_init_schema_migrates_v1_to_v2_and_preserves_data(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        await conn.execute("DROP TABLE chunks")
        await conn.execute(
            "INSERT INTO project_status_record("
            "project_id, name, status, created_at, updated_at"
            ") VALUES ('p1', 'demo.zip', 'parsing', '2026-06-06T12:00:00', "
            "'2026-06-06T12:00:00')"
        )
        await conn.execute("UPDATE schema_version SET version=1")
        await conn.commit()

    async with open_connection(db_path) as conn:
        await init_schema(conn)
        version_row = await (await conn.execute("SELECT version FROM schema_version")).fetchone()
        project_row = await (
            await conn.execute("SELECT project_id FROM project_status_record WHERE project_id='p1'")
        ).fetchone()
        chunks_row = await (
            await conn.execute("SELECT name FROM sqlite_master WHERE name='chunks'")
        ).fetchone()

    assert version_row["version"] == CURRENT_SCHEMA_VERSION
    assert project_row["project_id"] == "p1"
    assert chunks_row["name"] == "chunks"


async def test_init_schema_rejects_unknown_older_schema_version(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)
        await conn.execute("UPDATE schema_version SET version=0")
        await conn.commit()

    async with open_connection(db_path) as conn:
        with pytest.raises(StoreError, match="schema_migration_required"):
            await init_schema(conn)


async def test_open_connection_sets_expected_pragmas(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        foreign_keys = await (await conn.execute("PRAGMA foreign_keys")).fetchone()
        secure_delete = await (await conn.execute("PRAGMA secure_delete")).fetchone()
        busy_timeout = await (await conn.execute("PRAGMA busy_timeout")).fetchone()
        journal_mode = await (await conn.execute("PRAGMA journal_mode")).fetchone()

    assert foreign_keys[0] == 1
    assert secure_delete[0] == 1
    assert busy_timeout[0] == 5000
    assert journal_mode[0].lower() == "wal"
