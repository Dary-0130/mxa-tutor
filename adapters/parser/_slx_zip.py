import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from core.domain.exceptions import SlxParseError


def open_slx_zip(slx_file_path: str) -> ZipFile:
    """打开 .slx ZIP 容器。"""
    path = Path(slx_file_path)
    if not path.exists():
        raise SlxParseError(f"找不到 .slx 文件:{slx_file_path}")
    if not path.is_file():
        raise SlxParseError(f"找不到 .slx 文件:{slx_file_path}")

    try:
        return ZipFile(path)
    except BadZipFile as exc:
        raise SlxParseError(f".slx 文件损坏:不是有效的 ZIP 容器({slx_file_path})") from exc


def require_xml(slx_zip: ZipFile, inner_path: str) -> ET.Element:
    """读取必需 XML,缺失或损坏时抛中文 SlxParseError。"""
    if inner_path not in slx_zip.namelist():
        raise SlxParseError(
            ".slx 内部结构异常:未找到 simulink/blockdiagram.xml,可能不是有效的 Simulink 模型"
        )
    return read_xml(slx_zip, inner_path)


def read_xml(slx_zip: ZipFile, inner_path: str) -> ET.Element:
    """读取 XML part 并返回根节点。"""
    try:
        with slx_zip.open(inner_path) as stream:
            return ET.parse(stream).getroot()
    except ET.ParseError as exc:
        raise SlxParseError(f"Simulink 模型 XML 损坏,无法解析:{exc}") from exc
    except KeyError as exc:
        raise SlxParseError(f".slx 内部结构异常:未找到 {inner_path}") from exc


def read_optional_xml(
    slx_zip: ZipFile,
    inner_path: str,
    warnings: list[str],
    warning_text: str | None = None,
) -> ET.Element | None:
    """读取可选 XML,失败时记录 warning 并返回 None。"""
    if inner_path not in slx_zip.namelist():
        if warning_text:
            warnings.append(warning_text)
        return None
    try:
        return read_xml(slx_zip, inner_path)
    except SlxParseError as exc:
        warnings.append(f"可选 XML 解析失败,已跳过:{inner_path}, 原因={exc}")
        return None
