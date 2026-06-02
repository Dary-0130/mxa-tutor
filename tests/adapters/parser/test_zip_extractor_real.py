from pathlib import Path

import pytest

from adapters.parser.file_classifier import classify_files
from adapters.parser.zip_extractor import safe_extract
from app.config import AppSettings

SLX_SAMPLES_DIR = Path(__file__).parents[2] / "fixtures" / "slx_samples"


def _settings(upload_dir: Path) -> AppSettings:
    return AppSettings(deepseek_api_key="test", upload_dir=str(upload_dir))


@pytest.mark.parametrize("zip_path", sorted(SLX_SAMPLES_DIR.glob("*.zip")))
def test_real_slx_sample_zip_passes_sandbox(tmp_path: Path, zip_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    dest = upload_root / zip_path.stem
    dest.mkdir(parents=True)

    extracted = safe_extract(zip_path.read_bytes(), dest, _settings(upload_root))
    files = classify_files(extracted, extracted)

    file_types = {item.file_type for item in files}
    assert ".m" in file_types
    assert ".slx" in file_types

    if zip_path.name.startswith("01_") or zip_path.name.startswith("03_"):
        assert ".png" in file_types
    if zip_path.name.startswith("02_"):
        assert ".ssc" in file_types
        assert ".svg" in file_types
