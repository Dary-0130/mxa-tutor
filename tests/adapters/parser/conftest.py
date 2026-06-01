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
