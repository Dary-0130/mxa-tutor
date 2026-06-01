import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from adapters.parser._slx_config import parse_solver_config
from adapters.parser._slx_subsystem import walk_systems
from adapters.parser._slx_xml import first_system, get_model_name, get_root_system_ref
from adapters.parser._slx_zip import open_slx_zip, read_optional_xml, require_xml
from core.domain.exceptions import SlxParseError
from core.domain.slx_model import SlxModel
from core.interfaces.parser import SlxParser


class SlxParserImpl(SlxParser):
    """.slx XML 解析器具体实现(P0/P1 分级)。"""

    def parse(self, slx_file_path: str) -> SlxModel:
        """解析单个 .slx 文件。"""
        path = Path(slx_file_path)
        warnings: list[str] = []
        with open_slx_zip(slx_file_path) as slx_zip:
            blockdiagram_root = require_xml(slx_zip, "simulink/blockdiagram.xml")
            root_system = _load_root_system(slx_zip, blockdiagram_root, warnings)
            blocks, lines, subsystems = walk_systems(slx_zip, root_system, warnings)
            config_root = read_optional_xml(
                slx_zip,
                "simulink/configSet0.xml",
                warnings,
                warning_text="solver 配置解析失败,已跳过:未找到 simulink/configSet0.xml",
            )
            solver_config = parse_solver_config(config_root, warnings)
            name = _resolve_model_name(slx_zip, blockdiagram_root, path, warnings)

        return SlxModel(
            file_path=str(path),
            name=name,
            blocks=blocks,
            lines=lines,
            subsystems=subsystems,
            solver_config=solver_config,
            parse_warnings=warnings,
        )


def _load_root_system(
    slx_zip: ZipFile,
    blockdiagram_root: ET.Element,
    warnings: list[str],
) -> ET.Element:
    root_ref = get_root_system_ref(blockdiagram_root)
    if root_ref:
        root_system = read_optional_xml(
            slx_zip,
            f"simulink/systems/{root_ref}.xml",
            warnings,
            warning_text=f"子系统 XML 文件缺失,已跳过:{root_ref}",
        )
        if root_system is not None:
            return root_system
    inline_system = first_system(blockdiagram_root)
    if inline_system is not None:
        return inline_system
    raise SlxParseError(".slx 内部结构异常:未找到顶层 System,可能不是有效的 Simulink 模型")


def _resolve_model_name(
    slx_zip: ZipFile,
    blockdiagram_root: ET.Element,
    path: Path,
    warnings: list[str],
) -> str:
    name = get_model_name(blockdiagram_root)
    if name:
        return name
    core_properties = read_optional_xml(
        slx_zip,
        "metadata/coreProperties.xml",
        warnings,
        warning_text="未找到 metadata/coreProperties.xml,model 名从文件名提取",
    )
    if core_properties is not None:
        title = _find_text_by_local_name(core_properties, "title")
        if title:
            return title
    return path.stem


def _find_text_by_local_name(elem: ET.Element, local_name: str) -> str | None:
    for child in elem.iter():
        tag = child.tag.split("}", 1)[-1]
        if tag == local_name and child.text:
            return child.text.strip()
    return None
