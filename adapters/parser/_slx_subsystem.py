import xml.etree.ElementTree as ET
from zipfile import ZipFile

from adapters.parser._slx_xml import (
    get_inline_system,
    get_subsystem_ref,
    iter_subsystem_blocks,
    parse_blocks,
    parse_lines,
    subsystem_key,
)
from adapters.parser._slx_zip import read_optional_xml
from core.domain.slx_model import SlxBlock, SlxLine


def walk_systems(
    slx_zip: ZipFile,
    root_system: ET.Element,
    warnings: list[str],
) -> tuple[list[SlxBlock], list[SlxLine], dict[str, list[str]]]:
    """从顶层 System 递归遍历子系统。"""
    blocks: list[SlxBlock] = []
    lines: list[SlxLine] = []
    subsystems: dict[str, list[str]] = {}
    visited: set[str] = set()
    _walk_system(
        slx_zip=slx_zip,
        system_elem=root_system,
        parent_subsystem=None,
        warnings=warnings,
        visited=visited,
        blocks=blocks,
        lines=lines,
        subsystems=subsystems,
        current_ref="system_root",
    )
    return blocks, lines, subsystems


def _walk_system(
    slx_zip: ZipFile,
    system_elem: ET.Element,
    parent_subsystem: str | None,
    warnings: list[str],
    visited: set[str],
    blocks: list[SlxBlock],
    lines: list[SlxLine],
    subsystems: dict[str, list[str]],
    current_ref: str,
) -> None:
    if current_ref in visited:
        warnings.append(f"检测到子系统循环引用,已跳过:{current_ref}")
        return
    visited.add(current_ref)

    system_blocks = parse_blocks(system_elem, parent_subsystem, warnings)
    blocks.extend(system_blocks)
    lines.extend(parse_lines(system_elem, warnings))

    for subsystem_block in iter_subsystem_blocks(system_elem):
        key = subsystem_key(subsystem_block)
        ref = get_subsystem_ref(subsystem_block)
        child_system = get_inline_system(subsystem_block)
        child_ref = ref or f"inline:{subsystem_block.get('SID') or key}"
        if ref:
            child_system = read_optional_xml(
                slx_zip,
                f"simulink/systems/{ref}.xml",
                warnings,
                warning_text=f"子系统 XML 文件缺失,已跳过:{ref}",
            )
        if child_system is None:
            continue
        before = len(blocks)
        _walk_system(
            slx_zip=slx_zip,
            system_elem=child_system,
            parent_subsystem=key,
            warnings=warnings,
            visited=visited,
            blocks=blocks,
            lines=lines,
            subsystems=subsystems,
            current_ref=child_ref,
        )
        subsystems[key] = [block.block_id for block in blocks[before:]]
