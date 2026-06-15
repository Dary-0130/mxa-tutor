"""SQLite schema 定义 + idempotent 建表(TASK-204)。"""

from datetime import datetime

import aiosqlite

from core.domain.exceptions import StoreError

CURRENT_SCHEMA_VERSION = 3

_CHUNKS_DDL = """
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
);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
"""

_TEACHING_UNITS_DDL = """
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
);
CREATE INDEX IF NOT EXISTS idx_teaching_units_project ON teaching_units(project_id);
CREATE INDEX IF NOT EXISTS idx_teaching_units_expires ON teaching_units(expires_at);
"""

_DDL = f"""
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

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
{_CHUNKS_DDL}
{_TEACHING_UNITS_DDL}
"""


async def _migrate_v1_to_v2(conn: aiosqlite.Connection) -> None:
    """Add chunks table and bump schema_version from v1 to v2."""

    await conn.executescript(_CHUNKS_DDL)
    await conn.execute(
        "UPDATE schema_version SET version=?, applied_at=? WHERE id=1",
        (2, datetime.utcnow().isoformat()),
    )


async def _migrate_v2_to_v3(conn: aiosqlite.Connection) -> None:
    """Add teaching_units table and bump schema_version from v2 to v3."""

    await conn.executescript(_TEACHING_UNITS_DDL)
    await conn.execute(
        "UPDATE schema_version SET version=?, applied_at=? WHERE id=1",
        (3, datetime.utcnow().isoformat()),
    )


async def init_schema(conn: aiosqlite.Connection) -> None:
    """Idempotently create tables and verify schema_version."""

    await conn.executescript(_DDL)
    await conn.execute(
        "INSERT OR IGNORE INTO schema_version(id, version, applied_at) VALUES (1, ?, ?)",
        (CURRENT_SCHEMA_VERSION, datetime.utcnow().isoformat()),
    )

    cur = await conn.execute("SELECT version FROM schema_version WHERE id=1")
    row = await cur.fetchone()
    if row is None:
        raise StoreError("schema_version_missing")

    version = int(row["version"])
    if version > CURRENT_SCHEMA_VERSION:
        raise StoreError("unsupported_schema_version")
    if version == 1:
        await _migrate_v1_to_v2(conn)
        version = 2
    if version == 2:
        await _migrate_v2_to_v3(conn)
        version = 3
    if version < CURRENT_SCHEMA_VERSION:
        raise StoreError("schema_migration_required")

    await conn.commit()
