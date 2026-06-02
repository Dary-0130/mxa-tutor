import io
import stat
import zipfile
from pathlib import Path

import pytest

from adapters.parser._zip_paths import _is_windows_unsafe_name
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


def _dest(tmp_path: Path) -> tuple[Path, AppSettings]:
    upload_root = tmp_path / "uploads"
    dest = upload_root / "project"
    dest.mkdir(parents=True)
    return dest, _settings(upload_root)


def _zip_bytes(entries: dict[str, bytes | str], compression: int = zipfile.ZIP_STORED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data, compress_type=compression)
    return buf.getvalue()


def _zip_with_info(info: zipfile.ZipInfo, data: bytes | str = b"x") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(info, data)
    return buf.getvalue()


def _mark_first_entry_encrypted(data: bytes) -> bytes:
    patched = bytearray(data)
    local = patched.find(b"PK\x03\x04")
    central = patched.find(b"PK\x01\x02")
    assert local >= 0
    assert central >= 0
    patched[local + 6] |= 0x01
    patched[central + 8] |= 0x01
    return bytes(patched)


def test_valid_zip_extracts_at_upload_limit(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    result = safe_extract(_zip_bytes({"model.m": "disp('ok');"}), dest, config)
    assert result == dest.resolve()
    assert (dest / "model.m").read_text(encoding="utf-8") == "disp('ok');"


def test_oversized_upload_bytes_rejected(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    config.max_upload_size_mb = 1
    with pytest.raises(ProjectTooLargeError, match="上传压缩包过大"):
        safe_extract(b"x" * (1024 * 1024 + 1), dest, config)


def test_dest_dir_contract_rejects_invalid_targets(tmp_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    config = _settings(upload_root)

    with pytest.raises(ZipSlipError, match="解压目标目录不存在或不是目录"):
        safe_extract(_zip_bytes({"model.m": "x"}), upload_root / "missing", config)

    file_dest = upload_root / "file"
    file_dest.write_text("x", encoding="utf-8")
    with pytest.raises(ZipSlipError, match="解压目标目录不存在或不是目录"):
        safe_extract(_zip_bytes({"model.m": "x"}), file_dest, config)

    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ZipSlipError, match="解压目标目录不在 upload_dir 子树内"):
        safe_extract(_zip_bytes({"model.m": "x"}), outside, config)


def test_bad_zip_and_empty_zip_rejected(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    with pytest.raises(ZipBombError, match="zip 格式非法"):
        safe_extract(b"not a zip", dest, config)

    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w"):
        pass
    with pytest.raises(ZipBombError, match="zip 格式非法"):
        safe_extract(empty.getvalue(), dest, config)


def test_entry_count_limits_reject_too_many_entries_and_files(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    config.max_entries_per_project = 2
    with pytest.raises(ProjectTooLargeError, match="工程文件数过多"):
        safe_extract(_zip_bytes({"a.m": "x", "b.m": "x", "c.m": "x"}), dest, config)

    dest2, config2 = _dest(tmp_path / "second")
    config2.max_files_per_project = 1
    with pytest.raises(ProjectTooLargeError, match="工程文件数过多"):
        safe_extract(_zip_bytes({"a.m": "x", "b.m": "x"}), dest2, config2)


def test_entry_flags_reject_bad_method_symlink_and_encrypted_bit(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    with pytest.raises(ZipBombError, match="压缩包含加密文件"):
        safe_extract(_mark_first_entry_encrypted(_zip_bytes({"secret.m": "x"})), dest, config)

    with pytest.raises(ZipBombError, match="压缩方法不支持"):
        safe_extract(_zip_bytes({"bad.m": "x"}, compression=zipfile.ZIP_BZIP2), dest, config)

    link = zipfile.ZipInfo("linkdir")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ZipSlipError, match="zip 内含符号链接或非普通文件"):
        safe_extract(_zip_with_info(link, "/tmp/outside"), dest, config)


@pytest.mark.parametrize(
    "name",
    ["../x.m", "/abs/x.m", "C:\\x.m", "file.txt:ads", "CON.txt", "evil.exe."],
)
def test_path_gate_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    dest, config = _dest(tmp_path)
    with pytest.raises(ZipSlipError):
        safe_extract(_zip_bytes({name: "x"}), dest, config)


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
    ],
)
def test_windows_unsafe_name_variants(name: str) -> None:
    unsafe, reason = _is_windows_unsafe_name(name)
    assert unsafe is True
    assert reason


@pytest.mark.parametrize("name", ["model.slx", "dir/file.m", "COM10.txt", "normal.name.txt"])
def test_windows_safe_name_variants(name: str) -> None:
    assert _is_windows_unsafe_name(name) == (False, "")


@pytest.mark.parametrize(
    "entries",
    [
        [("a.m", "1"), ("a.m", "2")],
        [("unicode/e\u0301.m", "1"), ("unicode/é.m", "2")],
        [("case/A.m", "1"), ("case/a.m", "2")],
    ],
)
def test_collision_gate_rejects_duplicates(tmp_path: Path, entries: list[tuple[str, str]]) -> None:
    dest, config = _dest(tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)
    with pytest.raises(ZipSlipError, match="zip 内存在重复路径或路径碰撞"):
        safe_extract(buf.getvalue(), dest, config)


def test_size_ratio_and_extension_gate(tmp_path: Path) -> None:
    dest, config = _dest(tmp_path)
    config.max_single_file_mb = 1
    with pytest.raises(ProjectTooLargeError, match="单个文件解压后过大"):
        safe_extract(_zip_bytes({"big.m": b"x" * (1024 * 1024 + 1)}), dest, config)

    dest2, config2 = _dest(tmp_path / "ratio")
    with pytest.raises(ZipBombError, match="压缩比异常"):
        safe_extract(
            _zip_bytes({"model.m": b"0" * (2 * 1024 * 1024)}, zipfile.ZIP_DEFLATED),
            dest2,
            config2,
        )

    dest3, config3 = _dest(tmp_path / "deny")
    with pytest.raises(FileTypeNotAllowedError, match="包含不支持的文件类型: .exe"):
        safe_extract(_zip_bytes({"evil.exe": b"MZ"}), dest3, config3)

    dest4, config4 = _dest(tmp_path / "other")
    safe_extract(_zip_bytes({"backup.bak": b"opaque"}), dest4, config4)
    assert (dest4 / "backup.bak").exists()
