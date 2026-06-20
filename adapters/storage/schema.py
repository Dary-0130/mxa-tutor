"""SQLite schema definition and ordered migrations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

import aiosqlite
from loguru import logger

from core.domain.exceptions import StoreError

CURRENT_SCHEMA_VERSION = 4

_SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
"""

_BASE_DDL = """
CREATE TABLE IF NOT EXISTS project_status_record (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('parsing','ready','failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    project TEXT,
    error_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_project_created_at
    ON project_status_record(created_at);

CREATE TABLE IF NOT EXISTS chat_session (
    session_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    title TEXT,
    FOREIGN KEY (project_id)
        REFERENCES project_status_record(project_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_session_project
    ON chat_session(project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_message (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (session_id)
        REFERENCES chat_session(session_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_message_session
    ON chat_message(session_id, created_at ASC);
"""

_CHUNKS_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id          TEXT PRIMARY KEY,
        project_id        TEXT NOT NULL,
        source_type       TEXT NOT NULL,
        file_path         TEXT NOT NULL,
        symbol_name       TEXT,
        line_start        INTEGER,
        line_end          INTEGER,
        block_id          TEXT,
        block_name        TEXT,
        block_type        TEXT,
        parent_subsystem  TEXT,
        source_text       TEXT NOT NULL,
        embedding         BLOB NOT NULL,
        embedding_dim     INTEGER NOT NULL,
        model_name        TEXT NOT NULL,
        created_at        TEXT NOT NULL,
        FOREIGN KEY (project_id)
            REFERENCES project_status_record(project_id)
            ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id)",
)

_TEACHING_UNITS_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS teaching_units (
        teaching_unit_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        level TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        source_refs_json TEXT NOT NULL,
        prerequisites_json TEXT NOT NULL,
        builder_version TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        model_name TEXT NOT NULL,
        source_version TEXT NOT NULL,
        state TEXT NOT NULL CHECK (
            state IN ('generating', 'ready', 'failed_retryable', 'failed_permanent')
        ),
        error_code TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        UNIQUE (
            project_id,
            target_type,
            target_id,
            level,
            builder_version,
            prompt_version,
            model_name,
            source_version
        ),
        FOREIGN KEY (project_id)
            REFERENCES project_status_record(project_id)
            ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_teaching_units_project ON teaching_units(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_teaching_units_expires ON teaching_units(expires_at)",
)

_PAPER_CACHE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS paper_spec_cache (
        paper_id        TEXT PRIMARY KEY,
        paper_spec_json TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_plan_cache (
        paper_id              TEXT PRIMARY KEY,
        plan_json             TEXT NOT NULL,
        missing_prompts_json  TEXT NOT NULL,
        missing_bindings_json TEXT NOT NULL,
        created_at            TEXT NOT NULL,
        updated_at            TEXT NOT NULL
    )
    """,
)

_CHUNKS_DDL = ";\n".join(_CHUNKS_STATEMENTS) + ";"
_TEACHING_UNITS_DDL = ";\n".join(_TEACHING_UNITS_STATEMENTS) + ";"
_PAPER_CACHE_DDL = ";\n".join(_PAPER_CACHE_STATEMENTS) + ";"

_DDL = "\n".join(
    (
        _SCHEMA_VERSION_DDL,
        _BASE_DDL,
        _CHUNKS_DDL,
        _TEACHING_UNITS_DDL,
        _PAPER_CACHE_DDL,
    )
)

Migration = Callable[[aiosqlite.Connection], Awaitable[None]]


async def _execute_all(conn: aiosqlite.Connection, statements: tuple[str, ...]) -> None:
    for statement in statements:
        await conn.execute(statement)


async def _migrate_v1_to_v2(conn: aiosqlite.Connection) -> None:
    """Add chunks table."""

    await _execute_all(conn, _CHUNKS_STATEMENTS)


async def _migrate_v2_to_v3(conn: aiosqlite.Connection) -> None:
    """Add teaching_units table."""

    await _execute_all(conn, _TEACHING_UNITS_STATEMENTS)


async def _migrate_v3_to_v4(conn: aiosqlite.Connection) -> None:
    """Add persistent paper spec and plan tables."""

    await _execute_all(conn, _PAPER_CACHE_STATEMENTS)


_MIGRATIONS: dict[int, Migration] = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
}


async def init_schema(conn: aiosqlite.Connection) -> None:
    """Create a new latest schema or migrate an existing database in order."""

    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    schema_table = await cur.fetchone()
    if schema_table is None:
        await conn.executescript(_DDL)
        await conn.execute(
            "INSERT INTO schema_version(id, version, applied_at) VALUES (1, ?, ?)",
            (CURRENT_SCHEMA_VERSION, datetime.utcnow().isoformat()),
        )
        await conn.commit()
        return

    cur = await conn.execute("SELECT version FROM schema_version WHERE id=1")
    row = await cur.fetchone()
    if row is None:
        raise StoreError("schema_version_missing")

    version = int(row["version"])
    if version > CURRENT_SCHEMA_VERSION:
        raise StoreError("unsupported_schema_version")
    if version == CURRENT_SCHEMA_VERSION:
        await conn.commit()
        return
    if version < 1:
        raise StoreError("schema_migration_required")

    await conn.execute("BEGIN")
    try:
        for from_version in range(version, CURRENT_SCHEMA_VERSION):
            migration = _MIGRATIONS.get(from_version)
            if migration is None:
                raise StoreError("schema_migration_required")
            await migration(conn)

        await conn.execute(
            "UPDATE schema_version SET version=?, applied_at=? WHERE id=1",
            (CURRENT_SCHEMA_VERSION, datetime.utcnow().isoformat()),
        )
        await conn.commit()
    except Exception:
        try:
            await conn.rollback()
        except Exception as rollback_exc:
            logger.error(
                "schema migration rollback failed: exception={}",
                type(rollback_exc).__name__,
            )
        raise
