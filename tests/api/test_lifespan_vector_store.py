from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from api.dependencies import get_settings
from core.domain.exceptions import EmbeddingModelLoadError

SENSITIVE_PATH = "C:/Users/student/private/model.bin"


def test_lifespan_embedding_load_failure_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    def broken_embedder(*_args: object, **_kwargs: object) -> object:
        raise OSError(SENSITIVE_PATH)

    monkeypatch.setenv("DB_PATH", str(tmp_path / "mxa.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    monkeypatch.setattr(api_main, "SentenceTransformerEmbedder", broken_embedder)
    buf = io.StringIO()
    sink_id = logger.add(buf, level="ERROR")

    try:
        with pytest.raises(EmbeddingModelLoadError) as exc_info, TestClient(api_main.create_app()):
            pass
    finally:
        logger.remove(sink_id)

    exc = exc_info.value
    assert str(exc) == "model_load_failed"
    assert repr(exc) == "EmbeddingModelLoadError('model_load_failed')"
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert SENSITIVE_PATH not in str(exc)
    assert SENSITIVE_PATH not in repr(exc)
    assert SENSITIVE_PATH not in buf.getvalue()
    assert "OSError" in buf.getvalue()
