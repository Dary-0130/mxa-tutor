import zipfile
from pathlib import Path

import pytest

from adapters.parser.slx_parser import SlxParserImpl
from core.domain.exceptions import SlxParseError


def test_missing_file_raises_chinese_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.slx"

    with pytest.raises(SlxParseError, match="找不到 .slx 文件"):
        SlxParserImpl().parse(str(missing))


def test_non_zip_raises_chinese_error(tmp_path: Path) -> None:
    slx_path = tmp_path / "plain.slx"
    slx_path.write_bytes(b"not a zip")

    with pytest.raises(SlxParseError, match="不是有效的 ZIP 容器"):
        SlxParserImpl().parse(str(slx_path))


def test_missing_blockdiagram_raises_chinese_error(tmp_path: Path) -> None:
    slx_path = tmp_path / "missing_blockdiagram.slx"
    with zipfile.ZipFile(slx_path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")

    with pytest.raises(SlxParseError, match="未找到 simulink/blockdiagram.xml"):
        SlxParserImpl().parse(str(slx_path))


def test_broken_blockdiagram_xml_raises_chinese_error(tmp_path: Path) -> None:
    slx_path = tmp_path / "broken_xml.slx"
    with zipfile.ZipFile(slx_path, "w") as zf:
        zf.writestr("simulink/blockdiagram.xml", "<ModelInformation>")

    with pytest.raises(SlxParseError, match="XML 损坏"):
        SlxParserImpl().parse(str(slx_path))
