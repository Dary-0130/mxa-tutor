import pytest

from adapters.storage import schema
from adapters.storage._connection import open_connection
from core.domain.exceptions import StoreError


async def test_new_database_latest_schema_includes_paper_tables(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        tables = await _tables(conn)
        version = await _schema_version(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert {
        "paper_spec_cache",
        "paper_plan_cache",
        "paper_reparse_source_cache",
        "paper_parameter_correction",
        "teaching_units",
        "chunks",
    }.issubset(tables)


async def test_plan_table_has_no_spec_json_column(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        cur = await conn.execute("PRAGMA table_info(paper_plan_cache)")
        columns = {row["name"] for row in await cur.fetchall()}

    assert "spec_json" not in columns
    assert columns == {
        "paper_id",
        "plan_json",
        "missing_prompts_json",
        "missing_bindings_json",
        "created_at",
        "updated_at",
    }


async def test_migrates_v1_to_latest_and_preserves_project_and_chat(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await _create_v1_database(conn)
        await _insert_project_chat(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        tables = await _tables(conn)
        project = await (
            await conn.execute("SELECT project_id FROM project_status_record WHERE project_id='p1'")
        ).fetchone()
        session = await (
            await conn.execute("SELECT session_id FROM chat_session WHERE session_id='s1'")
        ).fetchone()

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert {
        "chunks",
        "teaching_units",
        "paper_spec_cache",
        "paper_plan_cache",
        "paper_reparse_source_cache",
        "paper_parameter_correction",
    }.issubset(tables)
    assert project["project_id"] == "p1"
    assert session["session_id"] == "s1"


async def test_migrates_v2_to_latest_and_preserves_chunks(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await _create_v2_database(conn)
        await _insert_project_chat(conn)
        await _insert_chunk(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        chunk = await (
            await conn.execute("SELECT chunk_id, source_text FROM chunks WHERE chunk_id='c1'")
        ).fetchone()
        tables = await _tables(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert chunk["chunk_id"] == "c1"
    assert chunk["source_text"] == "source"
    assert {
        "teaching_units",
        "paper_spec_cache",
        "paper_plan_cache",
        "paper_reparse_source_cache",
        "paper_parameter_correction",
    }.issubset(tables)


async def test_migrates_v3_to_latest_and_preserves_teaching_units(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await _create_v3_database(conn)
        await _insert_project_chat(conn)
        await _insert_teaching_unit(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        unit = await (
            await conn.execute(
                "SELECT teaching_unit_id, payload_json FROM teaching_units "
                "WHERE teaching_unit_id='tu1'"
            )
        ).fetchone()
        tables = await _tables(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert unit["teaching_unit_id"] == "tu1"
    assert unit["payload_json"] == "{}"
    assert {
        "paper_spec_cache",
        "paper_plan_cache",
        "paper_reparse_source_cache",
        "paper_parameter_correction",
    }.issubset(tables)


async def test_migrates_v5_to_latest_and_preserves_run_state_tables(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await _create_v5_database(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        tables = await _tables(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert {
        "bridge_run_state_session",
        "bridge_run_state_run",
        "paper_reparse_source_cache",
        "paper_parameter_correction",
    }.issubset(tables)


async def test_migrates_v6_to_latest_and_adds_parameter_correction_table(
    db_path: str,
) -> None:
    async with open_connection(db_path) as conn:
        await _create_v6_database(conn)

    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        version = await _schema_version(conn)
        tables = await _tables(conn)
        indexes = await _indexes(conn)

    assert version == schema.CURRENT_SCHEMA_VERSION
    assert "paper_parameter_correction" in tables
    assert "idx_paper_parameter_correction_paper" in indexes


async def test_target_latest_schema_is_idempotent(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
    async with open_connection(db_path) as conn:
        await schema.init_schema(conn)
        assert await _schema_version(conn) == schema.CURRENT_SCHEMA_VERSION


async def test_future_schema_version_fails_closed(db_path: str) -> None:
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


async def test_fault_during_migration_rolls_back_version_and_new_tables(
    db_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_migration(conn) -> None:  # type: ignore[no-untyped-def]
        await conn.execute(schema._PAPER_CACHE_STATEMENTS[0])
        raise RuntimeError("migration exploded")

    async with open_connection(db_path) as conn:
        await _create_v3_database(conn)
        await _insert_project_chat(conn)

    monkeypatch.setitem(schema._MIGRATIONS, 3, broken_migration)

    async with open_connection(db_path) as conn:
        with pytest.raises(RuntimeError, match="migration exploded"):
            await schema.init_schema(conn)

    async with open_connection(db_path) as conn:
        assert await _schema_version(conn) == 3
        assert "paper_spec_cache" not in await _tables(conn)


async def _create_v1_database(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.executescript(schema._SCHEMA_VERSION_DDL)
    await conn.executescript(schema._BASE_DDL)
    await conn.execute(
        "INSERT INTO schema_version(id, version, applied_at) VALUES (1, 1, '2026-06-01')"
    )
    await conn.commit()


async def _create_v2_database(conn) -> None:  # type: ignore[no-untyped-def]
    await _create_v1_database(conn)
    await conn.executescript(schema._CHUNKS_DDL)
    await conn.execute("UPDATE schema_version SET version=2 WHERE id=1")
    await conn.commit()


async def _create_v3_database(conn) -> None:  # type: ignore[no-untyped-def]
    await _create_v2_database(conn)
    await conn.executescript(schema._TEACHING_UNITS_DDL)
    await conn.execute("UPDATE schema_version SET version=3 WHERE id=1")
    await conn.commit()


async def _create_v5_database(conn) -> None:  # type: ignore[no-untyped-def]
    await _create_v3_database(conn)
    await conn.executescript(schema._PAPER_CACHE_DDL)
    await conn.executescript(schema._RUN_STATE_DDL)
    await conn.execute("UPDATE schema_version SET version=5 WHERE id=1")
    await conn.commit()


async def _create_v6_database(conn) -> None:  # type: ignore[no-untyped-def]
    await _create_v5_database(conn)
    await conn.executescript(schema._PAPER_REPARSE_SOURCE_DDL)
    await conn.execute("UPDATE schema_version SET version=6 WHERE id=1")
    await conn.commit()


async def _insert_project_chat(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.execute(
        """
        INSERT INTO project_status_record(
            project_id, name, status, created_at, updated_at
        ) VALUES ('p1', 'demo.zip', 'parsing', '2026-06-01T00:00:00', '2026-06-01T00:00:00')
        """
    )
    await conn.execute(
        """
        INSERT INTO chat_session(session_id, project_id, created_at, updated_at, title)
        VALUES ('s1', 'p1', '2026-06-01T00:00:00', '2026-06-01T00:00:00', NULL)
        """
    )
    await conn.commit()


async def _insert_chunk(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.execute(
        """
        INSERT INTO chunks(
            chunk_id, project_id, source_type, file_path, source_text,
            embedding, embedding_dim, model_name, created_at
        ) VALUES ('c1', 'p1', 'm_file', 'a.m', 'source', X'00000000', 1, 'model', 'now')
        """
    )
    await conn.commit()


async def _insert_teaching_unit(conn) -> None:  # type: ignore[no-untyped-def]
    await conn.execute(
        """
        INSERT INTO teaching_units(
            teaching_unit_id, project_id, target_type, target_id, level,
            payload_json, source_refs_json, prerequisites_json,
            builder_version, prompt_version, model_name, source_version,
            state, error_code, retry_count, created_at, updated_at, expires_at
        ) VALUES (
            'tu1', 'p1', 'project', 'p1', 'intro',
            '{}', '[]', '[]', 'b1', 'p1', 'm1', 's1',
            'ready', NULL, 0, 1, 1, 2
        )
        """
    )
    await conn.commit()


async def _schema_version(conn) -> int:  # type: ignore[no-untyped-def]
    row = await (await conn.execute("SELECT version FROM schema_version WHERE id=1")).fetchone()
    return int(row["version"])


async def _tables(conn) -> set[str]:  # type: ignore[no-untyped-def]
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row["name"] for row in await cur.fetchall()}


async def _indexes(conn) -> set[str]:  # type: ignore[no-untyped-def]
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {row["name"] for row in await cur.fetchall()}
