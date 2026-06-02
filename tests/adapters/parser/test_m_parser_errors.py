from pathlib import Path

import pytest

from adapters.parser.m_parser import MParserImpl
from core.domain.exceptions import MParseError


def test_missing_file_raises_chinese_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.m"

    with pytest.raises(MParseError, match="找不到 .m 文件"):
        MParserImpl().parse(str(missing))


def test_directory_raises_chinese_error(tmp_path: Path) -> None:
    with pytest.raises(MParseError, match="路径不是文件"):
        MParserImpl().parse(str(tmp_path))


def test_binary_file_raises_chinese_error(tmp_path: Path) -> None:
    path = tmp_path / "binary.m"
    path.write_bytes(b"x = 1;\x00\x00")

    with pytest.raises(MParseError, match="不是有效的文本文件"):
        MParserImpl().parse(str(path))


def test_gbk_file_preserves_chinese_comments(tmp_path: Path) -> None:
    path = tmp_path / "gbk_file.m"
    path.write_bytes("% 参数\nx = 1;\n".encode("gbk"))

    mfile = MParserImpl().parse(str(path))

    assert "参数" in mfile.raw_code
    assert "\ufffd" not in mfile.raw_code


def test_utf8_bom_file_classifies_function_correctly(tmp_path: Path) -> None:
    path = tmp_path / "bom_function.m"
    path.write_bytes(b"\xef\xbb\xbffunction y = f(x)\ny = x;\nend\n")

    mfile = MParserImpl().parse(str(path))

    assert mfile.file_role == "function"
    assert mfile.functions[0].name == "f"


def test_unknown_encoding_uses_replacement_without_raising(tmp_path: Path) -> None:
    path = tmp_path / "odd_encoding.m"
    path.write_bytes(b"\xff\xff\nx = 1;\n")

    mfile = MParserImpl().parse(str(path))

    assert "\ufffd" in mfile.raw_code
    assert mfile.file_role == "script"
