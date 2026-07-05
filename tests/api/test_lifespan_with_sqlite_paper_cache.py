from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_settings


def test_lifespan_wires_sqlite_paper_bundle_store_and_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main
    from adapters.storage.sqlite_paper_cache import (
        SqlitePaperBundleStore,
        SqlitePaperPlanCacheView,
        SqlitePaperSpecCacheView,
    )

    db_path = tmp_path / "mxa.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()

    app = api_main.create_app()
    with TestClient(app):
        assert isinstance(app.state.paper_bundle_store, SqlitePaperBundleStore)
        assert isinstance(app.state.paper_spec_cache, SqlitePaperSpecCacheView)
        assert isinstance(app.state.paper_plan_cache, SqlitePaperPlanCacheView)
        assert _table_names(db_path) >= {
            "paper_spec_cache",
            "paper_plan_cache",
            "paper_reparse_source_cache",
            "paper_upload_job",
            "paper_upload_job_document",
        }


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}
