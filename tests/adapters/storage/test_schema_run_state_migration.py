from __future__ import annotations

import pytest

from adapters.storage import schema
from adapters.storage._connection import open_connection
from core.domain.exceptions import StoreError


async def test_new_database_latest_schema_includes_run_state_tables_and_constraints(
    db_path: str,
) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        tables = await _tables(conn)
        version = await _schema_version(conn)
        unique_sets = await _run_unique_column_sets(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert {"bridge_run_state_session", "bridge_run_state_run"}.issubset(tables)
    assert {"session_id", "run_id"} in unique_sets
    assert {"session_id", "run_sequence"} in unique_sets
    assert {"session_id", "request_id"} in unique_sets


async def test_migrates_v4_to_v5_and_preserves_existing_data(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await _create_v4_database(conn)
        await _insert_project_chat_and_paper(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        tables = await _tables(conn)
        project = await (
            await conn.execute("SELECT project_id FROM project_status_record WHERE project_id='p1'")
        ).fetchone()
        chat = await (
            await conn.execute("SELECT session_id FROM chat_session WHERE session_id='c1'")
        ).fetchone()
        paper = await (
            await conn.execute("SELECT paper_id FROM paper_spec_cache WHERE paper_id='paper1'")
        ).fetchone()

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert {"bridge_run_state_session", "bridge_run_state_run"}.issubset(tables)
    assert project["project_id"] == "p1"
    assert chat["session_id"] == "c1"
    assert paper["paper_id"] == "paper1"


async def test_latest_schema_reentry_is_idempotent(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        assert await _schema_version(conn) == schema.CURRENT_SCHEMA_VERSION


async def test_run_state_future_schema_version_fails_closed(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        await conn.execute(
            "UPDATE schema_version SET version=? WHERE id=1",
            (schema.CURRENT_SCHEMA_VERSION + 1,),
        )
        await conn.commit()

    async with open_connection(db_path) as conn:
        with pytest.raises(StoreError, match="unsupported_schema_version"):
            await schema.init_schema(conn)


async def test_fault_during_v5_migration_rolls_back(
    db_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_migration(conn) -> None:  # type: ignore[no-untyped-def]
        await conn.execute(schema._RUN_STATE_STATEMENTS[0])
        raise RuntimeError("v5 migration exploded")

    async with open_connection(db_path) as conn:
        await _create_v4_database(conn)
        await _insert_project_chat_and_paper(conn)

    monkeypatch.setitem(schema._MIGRATIONS, 4, broken_migration)

    async with open_connection(db_path) as conn:
        with pytest.raises(RuntimeError, match="v5 migration exploded"):
            await schema.init_schema(conn)

    async with open_connection(db_path) as conn:
        assert await _schema_version(conn) == 4
        assert "bridge_run_state_session" not in await _tables(conn)


async def test_run_state_tables_cascade_when_project_is_deleted(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        await _insert_project(conn)
        await conn.execute(
            """
            INSERT INTO bridge_run_state_session(
                session_id,
                project_id,
                user_id,
                process_generation,
                status,
                current_run_id,
                established_at,
                updated_at,
                ended_at
            ) VALUES (
                '11111111-1111-4111-8111-111111111111',
                'p1',
                'user-alpha',
                'generation-1',
                'active',
                NULL,
                '2026-06-01T00:00:00',
                '2026-06-01T00:00:00',
                NULL
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO bridge_run_state_run(
                session_id,
                run_id,
                run_sequence,
                request_id,
                fingerprint,
                fingerprint_version,
                canonical_bytes,
                run_status,
                convergence_status,
                snapshot_json,
                received_at
            ) VALUES (
                '11111111-1111-4111-8111-111111111111',
                '22222222-2222-4222-8222-222222222222',
                1,
                '33333333-3333-4333-8333-333333333333',
                'sha256:test',
                1,
                X'7B7D',
                'completed',
                'not_applicable',
                '{}',
                '2026-06-01T00:00:00'
            )
            """
        )
        await conn.execute("DELETE FROM project_status_record WHERE project_id='p1'")
        await conn.commit()

        session_count = await _count(conn, "bridge_run_state_session")
        run_count = await _count(conn, "bridge_run_state_run")

    assert session_count == 0
    assert run_count == 0


async def _create_v4_database(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.executescript(schema._SCHEMA_VERSION_DDL)
    await conn.executescript(schema._BASE_DDL)
    await conn.executescript(schema._CHUNKS_DDL)
    await conn.executescript(schema._TEACHING_UNITS_DDL)
    await conn.executescript(schema._PAPER_CACHE_DDL)
    await conn.execute(
        "INSERT INTO schema_version(id, version, applied_at) VALUES (1, 4, '2026-06-01')"
    )
    await conn.commit()


async def _insert_project_chat_and_paper(conn) -> None:  # type: ignore[no-untyped-def]
    await _insert_project(conn)
    await conn.execute(
        """
        INSERT INTO chat_session(session_id, project_id, created_at, updated_at, title)
        VALUES ('c1', 'p1', '2026-06-01T00:00:00', '2026-06-01T00:00:00', NULL)
        """
    )
    await conn.execute(
        """
        INSERT INTO paper_spec_cache(paper_id, paper_spec_json, created_at, updated_at)
        VALUES ('paper1', '{}', '2026-06-01T00:00:00', '2026-06-01T00:00:00')
        """
    )
    await conn.commit()


async def _insert_project(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.execute(
        """
        INSERT INTO project_status_record(
            project_id, name, status, created_at, updated_at
        ) VALUES ('p1', 'demo.zip', 'parsing', '2026-06-01T00:00:00', '2026-06-01T00:00:00')
        """
    )


async def _run_unique_column_sets(conn) -> list[set[str]]:  # type: ignore[no-untyped-def]
    indexes = await (await conn.execute("PRAGMA index_list(bridge_run_state_run)")).fetchall()
    unique_sets: list[set[str]] = []
    for index in indexes:
        if not index["unique"]:
            continue
        columns = await (await conn.execute(f"PRAGMA index_info({index['name']})")).fetchall()
        unique_sets.append({column["name"] for column in columns})
    return unique_sets


async def _schema_version(conn) -> int:  # type: ignore[no-untyped-def]
    row = await (await conn.execute("SELECT version FROM schema_version WHERE id=1")).fetchone()
    return int(row["version"])


async def _tables(conn) -> set[str]:  # type: ignore[no-untyped-def]
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row["name"] for row in await cur.fetchall()}


async def _count(conn, table: str) -> int:  # type: ignore[no-untyped-def]
    row = await (await conn.execute(f"SELECT COUNT(*) AS count FROM {table}")).fetchone()
    return int(row["count"])
