"""Fixtures for ProjectGraph builder tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_graph import ProjectGraph
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability


@pytest.fixture
def make_file_info():
    def _make(
        relative_path: str,
        file_type: str = ".m",
        size_bytes: int = 1024,
        description: str | None = None,
    ) -> FileInfo:
        return FileInfo(
            relative_path=relative_path,
            file_type=file_type,
            size_bytes=size_bytes,
            description=description,
        )

    return _make


@pytest.fixture
def make_m_function():
    def _make(
        name: str = "fn",
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        line_range: tuple[int, int] = (1, 10),
        docstring: str | None = None,
    ) -> MFunction:
        return MFunction(
            name=name,
            inputs=inputs or [],
            outputs=outputs or [],
            line_range=line_range,
            docstring=docstring,
        )

    return _make


@pytest.fixture
def make_m_file(make_m_function):
    def _make(
        file_path: str,
        file_role: str = "function",
        functions: list[MFunction] | None = None,
        imports: list[str] | None = None,
        uses_toolbox: list[str] | None = None,
        raw_code: str = "",
    ) -> MFile:
        return MFile(
            file_path=file_path,
            file_role=file_role,
            functions=functions or [],
            imports=imports or [],
            uses_toolbox=uses_toolbox or [],
            raw_code=raw_code,
        )

    return _make


@pytest.fixture
def make_slx_block():
    def _make(
        block_id: str,
        name: str | None = None,
        block_type: str = "Gain",
        parameters: dict[str, str] | None = None,
        position: tuple[int, int, int, int] = (0, 0, 100, 50),
        parent_subsystem: str | None = None,
        is_masked: bool = False,
        is_library_link: bool = False,
        is_model_reference: bool = False,
    ) -> SlxBlock:
        return SlxBlock(
            block_id=block_id,
            name=name or block_id,
            block_type=block_type,
            parameters=parameters or {},
            position=position,
            parent_subsystem=parent_subsystem,
            is_masked=is_masked,
            is_library_link=is_library_link,
            is_model_reference=is_model_reference,
        )

    return _make


@pytest.fixture
def make_slx_line():
    def _make(
        from_block: str,
        from_port: int = 1,
        to_block: str = "",
        to_port: int = 1,
    ) -> SlxLine:
        return SlxLine(
            from_block=from_block,
            from_port=from_port,
            to_block=to_block,
            to_port=to_port,
        )

    return _make


@pytest.fixture
def make_slx_model():
    def _make(
        file_path: str,
        name: str | None = None,
        blocks: list[SlxBlock] | None = None,
        lines: list[SlxLine] | None = None,
        subsystems: dict[str, list[str]] | None = None,
        solver_config: dict[str, str] | None = None,
        parse_warnings: list[str] | None = None,
    ) -> SlxModel:
        return SlxModel(
            file_path=file_path,
            name=name or file_path.rsplit("/", 1)[-1].replace(".slx", ""),
            blocks=blocks or [],
            lines=lines or [],
            subsystems=subsystems or {},
            solver_config=solver_config or {},
            parse_warnings=parse_warnings or [],
        )

    return _make


@pytest.fixture
def make_mat_metadata():
    def _make(
        file_path: str,
        file_size_bytes: int = 1024,
        variables: list[MatVariable] | None = None,
    ) -> MatMetadata:
        return MatMetadata(
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            variables=variables or [],
        )

    return _make


@pytest.fixture
def make_project():
    def _make(
        id: str = "proj-1",
        name: str = "TestProject",
        project_type: ProjectType = ProjectType.GENERAL,
        files: list[FileInfo] | None = None,
        slx_models: list[SlxModel] | None = None,
        m_files: list[MFile] | None = None,
        mat_files: list[MatMetadata] | None = None,
        file_dependencies: dict[str, list[str]] | None = None,
    ) -> Project:
        return Project(
            id=id,
            name=name,
            project_type=project_type,
            files=files or [],
            slx_models=slx_models or [],
            m_files=m_files or [],
            mat_files=mat_files or [],
            created_at=datetime(2026, 6, 3, 0, 0, 0),
            file_dependencies=file_dependencies or {},
        )

    return _make


class OverviewResolverFake:
    def resolve(self, project) -> str:
        return "general"


class OverviewProviderFake:
    def __init__(self, response: LLMResponse | None = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls = 0
        self.kwargs = {}

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls += 1
        self.kwargs = {
            "messages": messages,
            "json_mode": json_mode,
            "timeout": timeout,
            "max_tokens": max_tokens,
        }
        if self.exc is not None:
            raise self.exc
        assert self.response is not None
        return self.response

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


class OverviewBuilderFake:
    def __init__(self, graph: ProjectGraph) -> None:
        self.graph = graph
        self.calls = 0

    def build(self, project) -> ProjectGraph:
        self.calls += 1
        return self.graph


def make_overview_graph(unresolved: list[str] | None = None) -> ProjectGraph:
    return ProjectGraph(
        project_id="p1",
        nodes=[],
        edges=[],
        entry_points=["main.m"],
        execution_flow=["main.m", "model.slx", "helper.m"],
        data_flow=[],
        control_flow=[],
        unresolved_symbols=unresolved or [],
    )


def make_overview_file_entries(*paths: str) -> list[dict[str, str]]:
    return [{"file_path": path, "why_key": f"{path} 很关键"} for path in paths]


def make_overview_evidence(
    main: str,
    helper: str,
    model: str,
    block_id: str,
) -> list[dict[str, object]]:
    first = {"file_path": main, "line_range": [1, 5]}
    second = {"file_path": helper, "line_range": [1, 3]}
    third = {"file_path": model, "block_id": block_id}
    return [first, second, third]


def make_overview_payload() -> dict[str, object]:
    return {
        "project_title": "Buck 控制",
        "project_type": "control_system",
        "one_sentence_summary": "这是一个 Buck 电压闭环控制工程。",
        "main_entry_files": [{"file_path": "main.m", "role": "运行入口"}],
        "main_simulink_models": [{"file_path": "model.slx", "summary": "主仿真模型"}],
        "main_execution_flow": ["打开 main.m", "加载参数", "运行 model.slx"],
        "key_files": make_overview_file_entries("main.m", "helper.m", "model.slx"),
        "key_blocks": [
            {
                "block_name": "Gain",
                "block_type": "Gain",
                "location": "model.slx / <root>",
                "why_key": "代表控制增益",
            }
        ],
        "knowledge_points": ["闭环控制", "PWM", "采样"],
        "beginner_reading_order": ["main.m", "helper.m", "model.slx"],
        "likely_confusing_points": ["未能确定 load_x", "Gain 的单位要结合参数看"],
        "evidence": make_overview_evidence("main.m", "helper.m", "model.slx", "b1"),
    }


def make_overview_response(payload) -> LLMResponse:
    import json

    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return LLMResponse(
        text=text, prompt_tokens=10, completion_tokens=20, model="fake", latency_ms=1
    )
