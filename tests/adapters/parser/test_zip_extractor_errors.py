import io
import zipfile
from pathlib import Path

import pytest

from adapters.parser.zip_extractor import safe_extract
from app.config import AppSettings
from core.domain.exceptions import (
    FileTypeNotAllowedError,
    ProjectTooLargeError,
    ZipBombError,
    ZipSlipError,
)


def _settings(upload_dir: Path, **overrides: int | str) -> AppSettings:
    values: dict[str, int | str] = {"deepseek_api_key": "test", "upload_dir": str(upload_dir)}
    values.update(overrides)
    return AppSettings(**values)


def _dest(tmp_path: Path, name: str) -> tuple[Path, AppSettings]:
    upload_root = tmp_path / "uploads"
    dest = upload_root / name
    dest.mkdir(parents=True)
    return dest, _settings(upload_root)


@pytest.mark.parametrize(
    ("fixture_name", "error_type"),
    [
        ("zip_bomb_ratio", ZipBombError),
        ("zip_slip_paths", ZipSlipError),
        ("symlink_chain", ZipSlipError),
        ("duplicate_collision", ZipSlipError),
        ("forbidden_type", FileTypeNotAllowedError),
        ("encrypted_or_bad_method", ZipBombError),
        ("total_uncompressed_exceeds_cap", ZipBombError),
    ],
)
def test_malicious_fixtures_are_rejected(
    tmp_path: Path,
    malicious_zip_dir: dict[str, Path],
    fixture_name: str,
    error_type: type[Exception],
) -> None:
    dest, config = _dest(tmp_path, fixture_name)
    if fixture_name == "total_uncompressed_exceeds_cap":
        config.max_total_uncompressed_mb = 1

    with pytest.raises(error_type):
        safe_extract(malicious_zip_dir[fixture_name].read_bytes(), dest, config)


@pytest.mark.parametrize(
    "name",
    [
        "C:foo",
        "c:\\foo",
        "\\\\server\\share\\x.m",
        "//server/share/x.m",
        "file.txt:ads",
        "dir/CON.txt",
        "NUL",
        "COM1.log",
        "LPT9",
        "evil.exe.",
        "evil.exe ",
        "dir/.. /x.m",
        "folder/name\tbad.m",
    ],
)
def test_windows_unsafe_zip_paths_rejected(tmp_path: Path, name: str) -> None:
    dest, config = _dest(tmp_path, "unsafe")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, "x")

    with pytest.raises(ZipSlipError):
        safe_extract(buf.getvalue(), dest, config)


def test_extraction_timeout_rejected(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path, "timeout")
    config.max_extraction_seconds = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("model.m", "disp('slow');")

    with pytest.raises(ProjectTooLargeError, match="解压超时"):
        safe_extract(buf.getvalue(), dest, config)
