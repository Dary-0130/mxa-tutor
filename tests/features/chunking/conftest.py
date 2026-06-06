from __future__ import annotations

from datetime import datetime

import pytest

from app.config import AppSettings
from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxModel


@pytest.fixture
def chunk_settings(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    return AppSettings()


@pytest.fixture
def rich_project() -> Project:
    func = MFunction(
        name="controller",
        inputs=["u"],
        outputs=["y"],
        line_range=(10, 20),
        docstring="控制器函数",
    )
    blocks = [
        SlxBlock("b1", "Gain", "Gain", {"K": "1"}, (0, 0, 10, 10), None),
        SlxBlock("b2", "Lib", "Gain", {}, (0, 0, 10, 10), None, is_library_link=True),
        SlxBlock("b3", "Ref", "ModelReference", {}, (0, 0, 10, 10), None, is_model_reference=True),
    ]
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[
            FileInfo("main.m", ".m", 10, description="主入口文件"),
            FileInfo("model.slx", ".slx", 10),
            FileInfo("data.mat", ".mat", 10),
        ],
        slx_models=[
            SlxModel(
                file_path="model.slx",
                name="model",
                blocks=blocks,
                lines=[],
                subsystems={"Loop": ["b1", "b2", "b3"]},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[MFile("main.m", "script", [func], [], [], "secret")],
        mat_files=[
            MatMetadata(
                file_path="data.mat",
                file_size_bytes=10,
                variables=[MatVariable("Kp", "double", (1, 1), "gain", [])],
            )
        ],
        created_at=datetime(2026, 6, 6, 0, 0, 0),
        file_dependencies={},
    )


@pytest.fixture
def empty_project() -> Project:
    return Project(
        id="empty",
        name="empty.zip",
        project_type=ProjectType.GENERAL,
        files=[],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime(2026, 6, 6, 0, 0, 0),
        file_dependencies={},
    )
