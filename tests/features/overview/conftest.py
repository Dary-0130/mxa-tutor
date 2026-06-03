"""Fixtures for ProjectGraph builder tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


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
