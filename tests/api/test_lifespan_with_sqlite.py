import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_settings
from core.domain.chat import ChatMessage, ChatSession


def test_lifespan_wires_sqlite_stores_and_status_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "mxa.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    from adapters.storage.sqlite_chat_store import SqliteChatStore
    from adapters.storage.sqlite_project_store import SqliteProjectStore
    from api.main import create_app

    app = create_app()
    with TestClient(app) as client:
        assert db_path.exists()
        assert isinstance(app.state.project_store, SqliteProjectStore)
        assert isinstance(app.state.chat_store, SqliteChatStore)
        assert _table_names(db_path) >= {
            "chat_message",
            "chat_session",
            "project_status_record",
            "schema_version",
        }

        asyncio.run(app.state.project_store.create_pending("p1", "demo.zip"))
        session_time = datetime(2026, 6, 4, 12, 0, 0)
        asyncio.run(
            app.state.chat_store.create_session(
                ChatSession(
                    session_id="s1",
                    project_id="p1",
                    created_at=session_time,
                    updated_at=session_time,
                )
            )
        )
        asyncio.run(
            app.state.chat_store.append_message(
                ChatMessage(
                    message_id="m1",
                    session_id="s1",
                    role="user",
                    content="hello",
                    created_at=session_time,
                )
            )
        )

        health = client.get("/health")
        status = client.get("/projects/p1/status")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert status.status_code == 200
    assert status.json()["project_id"] == "p1"
    assert status.json()["status"] == "parsing"


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}
