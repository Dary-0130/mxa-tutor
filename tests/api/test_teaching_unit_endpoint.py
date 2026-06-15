from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.storage._connection import open_connection
from adapters.storage.in_memory_project_store import InMemoryProjectStore
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_teaching_unit_store import SqliteTeachingUnitStore
from api.dependencies import get_settings
from core.domain.exceptions import LLMTimeoutError
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxModel
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.overview._node_id import make_block_id


class TeachingUnitProviderFake(TextProvider):
    def __init__(self, payload: dict[str, object] | str | None = None, exc: Exception | None = None):
        self.payload = payload or _payload()
        self.exc = exc
        self.calls = 0

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = messages, json_mode, timeout, max_tokens
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return LLMResponse(
            text=text,
            prompt_tokens=1,
            completion_tokens=1,
            model="fake",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake-model", supports_json=True)


def _payload() -> dict[str, object]:
    return {
        "title": "Gain 模块讲解",
        "summary": "Gain 模块把输入信号按参数放大,用于形成控制量。",
        "explanation_steps": ["定位输入", "查看 Gain 参数", "跟踪输出"],
        "knowledge_points": ["比例增益", "闭环控制"],
        "confusion_points": ["Gain 不是积分环节"],
    }


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("main.m", ".m", 100), FileInfo("model.slx", ".slx", 100)],
        slx_models=[
            SlxModel(
                file_path="model.slx",
                name="model",
                blocks=[
                    SlxBlock(
                        block_id="b1",
                        name="Gain",
                        block_type="Gain",
                        parameters={"Gain": "Kp"},
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
        m_files=[MFile("main.m", "script", [], [], [], "")],
        mat_files=[],
        created_at=datetime(2026, 6, 15, 12, 0, 0),
        file_dependencies={},
    )


def _target_id() -> str:
    return make_block_id("model.slx", "b1")


def _create_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "lifespan.db"))
    get_settings.cache_clear()
    from api.main import create_app

    return create_app()


async def _install_state(
    app: FastAPI,
    tmp_path: Path,
    provider: TeachingUnitProviderFake,
) -> None:
    project = _project()
    project_store = InMemoryProjectStore()
    await project_store.create_pending(project.id, project.name)
    await project_store.mark_ready(project.id, project)

    db_path = str(tmp_path / "teaching-unit.db")
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    sqlite_project_store = SqliteProjectStore(db_path)
    await sqlite_project_store.create_pending("p1", "demo.zip")

    app.state.project_store = project_store
    app.state.teaching_unit_store = SqliteTeachingUnitStore(db_path)
    app.state.text_provider = provider


def test_generate_teaching_unit_returns_200_with_cached_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)
    provider = TeachingUnitProviderFake()

    with TestClient(app) as client:
        asyncio.run(_install_state(app, tmp_path, provider))
        started = time.perf_counter()
        response = client.post(
            "/projects/p1/teaching-units:generate",
            json={"target_type": "block", "target_id": _target_id()},
        )
        elapsed = time.perf_counter() - started
        second = client.post(
            "/projects/p1/teaching-units:generate",
            json={"target_type": "block", "target_id": _target_id()},
        )

    assert response.status_code == 200
    assert elapsed < 8
    body: dict[str, Any] = response.json()
    assert set(body) == {
        "confusion_points",
        "explanation_steps",
        "id",
        "knowledge_points",
        "level",
        "prerequisites",
        "source_refs",
        "summary",
        "target",
        "target_id",
        "title",
    }
    assert body["target"] == "block"
    assert body["target_id"] == _target_id()
    assert body["level"] == "normal"
    assert "is_fallback" not in body
    assert second.status_code == 200
    assert second.json() == body
    assert provider.calls == 1


def test_generate_teaching_unit_advanced_returns_422(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        asyncio.run(_install_state(app, tmp_path, TeachingUnitProviderFake()))
        response = client.post(
            "/projects/p1/teaching-units:generate",
            json={"target_type": "block", "target_id": _target_id(), "level": "advanced"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_teaching_level"


def test_generate_teaching_unit_llm_timeout_returns_502(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        asyncio.run(
            _install_state(
                app,
                tmp_path,
                TeachingUnitProviderFake(exc=LLMTimeoutError("timeout")),
            )
        )
        response = client.post(
            "/projects/p1/teaching-units:generate",
            json={"target_type": "block", "target_id": _target_id()},
        )

    assert response.status_code == 502
    assert response.json() == {
        "error": "teaching_unit_generation",
        "message": "教学单元生成失败,请刷新重试",
    }


def test_generate_teaching_unit_missing_target_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        asyncio.run(_install_state(app, tmp_path, TeachingUnitProviderFake()))
        response = client.post(
            "/projects/p1/teaching-units:generate",
            json={"target_type": "block", "target_id": "slx:model.slx::block:missing"},
        )

    assert response.status_code == 404
    assert response.json()["error"] == "teaching_unit_target_not_found"
