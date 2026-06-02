import zipfile
from pathlib import Path

import pytest

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
