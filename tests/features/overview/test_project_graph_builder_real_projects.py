from datetime import datetime
from pathlib import Path

import pytest

from adapters.parser import (
    MParserImpl,
    SlxParserImpl,
    analyze_dependencies,
    classify_files,
    safe_extract,
)
from app.config import AppSettings
from core.domain.mat_metadata import MatMetadata
from core.domain.project import FileInfo, Project, ProjectType
from features.overview import ProjectGraphBuilder

SLX_SAMPLES_DIR = Path(__file__).parents[2] / "fixtures" / "slx_samples"
PROJECT_ZIPS = sorted(SLX_SAMPLES_DIR.glob("*.zip"))


def _settings(upload_dir: Path) -> AppSettings:
    return AppSettings(deepseek_api_key="test", upload_dir=str(upload_dir))


@pytest.mark.parametrize("zip_path", PROJECT_ZIPS)
def test_project_graph_builder_runs_on_real_projects(tmp_path: Path, zip_path: Path) -> None:
    assert len(PROJECT_ZIPS) == 4
    project = _parse_project_from_zip(tmp_path, zip_path)

    graph = ProjectGraphBuilder().build(project)

    assert len(graph.nodes) >= len(project.m_files) + len(project.slx_models) + len(
        project.mat_files
    )
    assert len(graph.edges) > 0
    assert graph.entry_points
    assert graph.execution_flow
    assert not any(item.startswith("circular:") for item in graph.unresolved_symbols)


def _parse_project_from_zip(tmp_path: Path, zip_path: Path) -> Project:
    upload_root = tmp_path / "uploads"
    dest = upload_root / zip_path.stem
    dest.mkdir(parents=True)
    extracted = safe_extract(zip_path.read_bytes(), dest, _settings(upload_root))
    file_infos = classify_files(extracted, extracted)

    m_files = _parse_m_files(extracted, file_infos)
    slx_models = _parse_slx_models(extracted, file_infos)
    mat_files = _make_mat_metadata(extracted, file_infos)
    file_dependencies = analyze_dependencies(file_infos, m_files, project_root=str(extracted))

    return Project(
        id=zip_path.stem,
        name=zip_path.stem,
        project_type=ProjectType.GENERAL,
        files=file_infos,
        slx_models=slx_models,
        m_files=m_files,
        mat_files=mat_files,
        created_at=datetime(2026, 6, 3, 0, 0, 0),
        file_dependencies=file_dependencies,
    )


def _parse_m_files(extracted: Path, file_infos: list[FileInfo]):
    parser = MParserImpl()
    result = []
    for file_info in file_infos:
        if file_info.file_type != ".m":
            continue
        parsed = parser.parse(str(extracted / file_info.relative_path))
        parsed.file_path = file_info.relative_path
        result.append(parsed)
    return result


def _parse_slx_models(extracted: Path, file_infos: list[FileInfo]):
    parser = SlxParserImpl()
    result = []
    for file_info in file_infos:
        if file_info.file_type != ".slx":
            continue
        parsed = parser.parse(str(extracted / file_info.relative_path))
        parsed.file_path = file_info.relative_path
        result.append(parsed)
    return result


def _make_mat_metadata(extracted: Path, file_infos: list[FileInfo]) -> list[MatMetadata]:
    return [
        MatMetadata(
            file_path=file_info.relative_path,
            file_size_bytes=(extracted / file_info.relative_path).stat().st_size,
            variables=[],
        )
        for file_info in file_infos
        if file_info.file_type == ".mat"
    ]
