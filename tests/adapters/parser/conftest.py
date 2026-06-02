import zipfile
from pathlib import Path, PurePosixPath

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.project import FileInfo
from tests.fixtures.malicious_zips.build_fixtures import build_all

SLX_SAMPLES_DIR = Path(__file__).parents[2] / "fixtures" / "slx_samples"


@pytest.fixture(scope="session")
def extracted_slx_projects(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[Path]]:
    """解压 4 个测试 zip 到临时目录。"""
    extract_root = tmp_path_factory.mktemp("slx_samples_extracted")
    result: dict[str, list[Path]] = {}
    for zip_path in sorted(SLX_SAMPLES_DIR.glob("*.zip")):
        project_dest = extract_root / zip_path.stem
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(project_dest)
        result[zip_path.stem] = sorted(project_dest.rglob("*.slx"))
    return result


@pytest.fixture(scope="session")
def extracted_m_files(extracted_slx_projects: dict[str, list[Path]]) -> dict[str, list[Path]]:
    """复用已解压的测试工程,扫描每个工程内的 .m 文件。"""
    result: dict[str, list[Path]] = {}
    for project_name, slx_files in extracted_slx_projects.items():
        if slx_files:
            project_root = _project_extract_root(slx_files[0], project_name)
            result[project_name] = sorted(project_root.rglob("*.m"))
        else:
            result[project_name] = []
    return result


def _project_extract_root(sample_path: Path, project_name: str) -> Path:
    for parent in sample_path.parents:
        if parent.name == project_name:
            return parent
    return sample_path.parent


@pytest.fixture(scope="session")
def malicious_zip_dir(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """生成 TASK-104 的 7 个恶意 zip fixture。"""
    fixture_root = tmp_path_factory.mktemp("malicious_zips")
    build_all(fixture_root)
    return {path.stem: path for path in sorted(fixture_root.glob("*.zip"))}


@pytest.fixture
def make_m_file():
    """Factory for compact ``MFile`` test objects."""

    def _make(
        file_path: str,
        raw_code: str = "",
        functions: list[MFunction] | None = None,
        file_role: str = "script",
        imports: list[str] | None = None,
        uses_toolbox: list[str] | None = None,
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
def make_file_info():
    """Factory for compact ``FileInfo`` test objects."""

    def _make(
        relative_path: str,
        file_type: str | None = None,
        size_bytes: int = 0,
    ) -> FileInfo:
        inferred_type = file_type or PurePosixPath(relative_path).suffix or "other"
        return FileInfo(
            relative_path=relative_path,
            file_type=inferred_type,
            size_bytes=size_bytes,
        )

    return _make
