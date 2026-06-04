"""SQLite schema 定义 + idempotent 建表(TASK-204)。"""

from datetime import datetime

import aiosqlite

from core.domain.exceptions import StoreError

CURRENT_SCHEMA_VERSION = 1

_DDL = """
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
"""


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
    if version < CURRENT_SCHEMA_VERSION:
        raise StoreError("schema_migration_required")

    await conn.commit()
