from pathlib import Path

import pytest

from adapters.parser._zip_policy import ALLOW_EXTS, DENY_EXTS, SKIP_EXTS, classify_extension
from adapters.parser.file_classifier import classify_files
from core.domain.exceptions import FileTypeNotAllowedError


def test_classify_extension_policy_sets() -> None:
    assert classify_extension(".m") == "allow"
    assert classify_extension(".slx") == "allow"
    assert classify_extension(".png") == "allow"
    assert classify_extension(".exe") == "deny"
    assert classify_extension(".mexw64") == "skip"
    assert classify_extension(".pdf") == "skip"
    assert classify_extension(".gif") == "allow"
    assert classify_extension(".docx") == "other"
    assert classify_extension("") == "other"
    assert classify_extension("m") == "other"
    assert classify_extension(".M") == "other"
    assert ".html" not in ALLOW_EXTS
    assert ".slxc" not in ALLOW_EXTS
    assert ".py" in DENY_EXTS
    assert ".mexw64" in SKIP_EXTS
    assert ".pdf" in SKIP_EXTS


def test_classify_files_returns_file_info_without_reading_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.m").write_text("disp('ok')", encoding="utf-8")
    (root / "image.gif").write_bytes(b"GIF89a")
    (root / "notes.bak").write_bytes(b"opaque")

    files = classify_files(root, root)

    by_path = {item.relative_path: item for item in files}
    assert by_path["model.m"].file_type == ".m"
    assert by_path["image.gif"].file_type == ".gif"
    assert by_path["notes.bak"].file_type == "other"
    assert by_path["model.m"].description is None


def test_classify_files_rejects_deny_extension(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "evil.exe").write_bytes(b"MZ")

    with pytest.raises(FileTypeNotAllowedError, match="包含不支持的文件类型: .exe"):
        classify_files(root, root)


def test_classify_files_skips_skip_extension(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.m").write_text("disp('ok')", encoding="utf-8")
    (root / "paper.pdf").write_bytes(b"%PDF-1.7")
    (root / "native.mexw64").write_bytes(b"MZ")

    files = classify_files(root, root)

    assert [item.relative_path for item in files] == ["model.m"]
