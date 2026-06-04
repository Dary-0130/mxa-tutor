from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.storage.in_memory_project_store import InMemoryProjectStore
from api.dependencies import get_settings
from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    MParseError,
    SlxParseError,
)
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxModel
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability
from features.overview import InMemoryOverviewCache
from tests.features.overview.conftest import make_overview_payload


class _Provider:
    def __init__(self, payload: dict[str, Any] | str | None = None, exc: Exception | None = None):
        self.payload = payload or make_overview_payload()
        self.exc = exc
        self.calls = 0

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        import json

        _ = messages, json_mode, timeout, max_tokens
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return LLMResponse(
            text=text, prompt_tokens=1, completion_tokens=1, model="fake", latency_ms=1
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


def _create_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    from api.main import create_app

    return create_app()


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[
            FileInfo("main.m", ".m", 100),
            FileInfo("helper.m", ".m", 100),
            FileInfo("model.slx", ".slx", 100),
        ],
        slx_models=[
            SlxModel(
                file_path="model.slx",
                name="model",
                blocks=[
                    SlxBlock(
                        block_id="b1",
                        name="Gain",
                        block_type="Gain",
                        parameters={},
                        position=(0, 0, 10, 10),
                        parent_subsystem=None,
                    )
                ],
                lines=[],
                subsystems={},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[
            MFile("main.m", "script", [], [], [], ""),
            MFile("helper.m", "function", [], [], [], ""),
        ],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


def _ready_store(project: Project | None = None) -> InMemoryProjectStore:
    store = InMemoryProjectStore()
    if project is not None:
        asyncio.run(store.create_pending(project.id, project.name))
        asyncio.run(store.mark_ready(project.id, project))
    return store


@contextmanager
def _client(
    app: FastAPI,
    store: InMemoryProjectStore,
    provider: _Provider,
) -> Iterator[TestClient]:
    with TestClient(app) as client:
        app.state.project_store = store
        app.state.overview_cache = InMemoryOverviewCache()
        app.state.text_provider = provider
        yield client


def test_get_overview_returns_200_with_12_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)
    provider = _Provider()

    with _client(app, _ready_store(_project()), provider) as client:
        response = client.get("/projects/p1/overview")

    assert response.status_code == 200
    assert set(response.json()) == set(make_overview_payload())
    assert provider.calls == 1


def test_get_overview_cache_hit_reuses_first_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)
    provider = _Provider()

    with _client(app, _ready_store(_project()), provider) as client:
        first = client.get("/projects/p1/overview")
        second = client.get("/projects/p1/overview")

    assert first.status_code == 200
    assert second.json() == first.json()
    assert provider.calls == 1


def test_get_overview_missing_project_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with _client(app, _ready_store(), _Provider()) as client:
        response = client.get("/projects/missing/overview")

    assert response.status_code == 404
    assert response.json()["error"] == "project_not_found"


@pytest.mark.parametrize(
    ("exc", "status_code", "machine_code"),
    [
        (LLMAuthError("x"), 503, "llm_auth"),
        (LLMQuotaError("x"), 503, "llm_quota"),
        (LLMRateLimitError("x"), 429, "llm_rate_limit"),
        (LLMTimeoutError("x"), 504, "llm_timeout"),
        (LLMServerError("x"), 502, "llm_server"),
    ],
)
def test_get_overview_llm_errors_return_locked_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    status_code: int,
    machine_code: str,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with _client(app, _ready_store(_project()), _Provider(exc=exc)) as client:
        response = client.get("/projects/p1/overview")

    assert response.status_code == status_code
    assert set(response.json()) == {"error", "message"}
    assert response.json()["error"] == machine_code


def test_get_overview_generation_error_returns_502(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with _client(app, _ready_store(_project()), _Provider(payload="not json")) as client:
        response = client.get("/projects/p1/overview")

    assert response.status_code == 502
    assert response.json() == {"error": "overview_generation", "message": "导览生成失败,请刷新重试"}


@pytest.mark.parametrize(
    ("exc_type", "machine_code"),
    [(SlxParseError, "slx_parse"), (MParseError, "m_parse")],
)
def test_parse_error_handlers_return_locked_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exc_type: type[Exception],
    machine_code: str,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    async def trigger() -> None:
        raise exc_type("secret")

    app.add_api_route("/_parse_error", trigger, methods=["GET"])
    with TestClient(app) as client:
        response = client.get("/_parse_error")

    assert response.status_code == 400
    assert response.json()["error"] == machine_code
