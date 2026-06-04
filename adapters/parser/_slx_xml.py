import re
import xml.etree.ElementTree as ET

from adapters.parser._slx_config import (
    collect_workspace_warnings,
    is_library_link,
    is_masked,
    is_model_reference,
)
from core.domain.slx_model import SlxBlock, SlxLine

POSITION_RE = re.compile(r"-?\d+")
PORT_RE = re.compile(r"^(?P<sid>[^#]+)#(?P<kind>[A-Za-z]+):(?P<port>\d+)$")
BRANCH_DEPTH_LIMIT = 10


def get_p_value(elem: ET.Element, name: str, default: str | None = None) -> str | None:
    """读取子元素 P Name=name 的文本值。"""
    for child in elem:
        if child.tag == "P" and child.get("Name") == name:
            return _clean_text(child.text) if child.text is not None else ""
    return default


def get_model_name(blockdiagram_root: ET.Element) -> str | None:
    """从 blockdiagram.xml 提取模型名称。"""
    model = _first_by_tag(blockdiagram_root, "Model")
    if model is None:
        model = _first_by_tag(blockdiagram_root, "Subsystem")
    if model is None:
        return None
    return model.get("Name") or get_p_value(model, "Name")


def get_root_system_ref(blockdiagram_root: ET.Element) -> str | None:
    """从 blockdiagram.xml 提取顶层 System Ref。"""
    model = _first_by_tag(blockdiagram_root, "Model")
    if model is None:
        model = _first_by_tag(blockdiagram_root, "Subsystem")
    if model is None:
        return None
    for child in model:
        if child.tag == "System":
            return child.get("Ref")
    return None


def first_system(blockdiagram_root: ET.Element) -> ET.Element | None:
    """查找第一个 System 节点。"""
    return _first_by_tag(blockdiagram_root, "System")


def parse_blocks(
    system_elem: ET.Element,
    parent_subsystem: str | None,
    warnings: list[str],
) -> list[SlxBlock]:
    """解析一个 System 里的直接 Block。"""
    blocks: list[SlxBlock] = []
    for block_elem in system_elem.findall("Block"):
        try:
            block = _parse_block(block_elem, parent_subsystem, warnings)
        except Exception as exc:  # noqa: BLE001 - 单 block 必须失败隔离
            sid = block_elem.get("SID") or "<unknown>"
            warnings.append(f"block 解析失败,已跳过:SID={sid}, 原因={type(exc).__name__}")
            continue
        blocks.append(block)
    return blocks


def parse_lines(system_elem: ET.Element, warnings: list[str]) -> list[SlxLine]:
    """解析一个 System 里的直接 Line,展开 Branch 分支。"""
    lines: list[SlxLine] = []
    for line_elem in system_elem.findall("Line"):
        src = get_p_value(line_elem, "Src")
        direct_dst = get_p_value(line_elem, "Dst")
        if src and direct_dst:
            _append_line(lines, src, direct_dst, warnings)
        for branch in line_elem.findall("Branch"):
            _collect_branch_lines(branch, src, lines, warnings, depth=0)
        if not direct_dst and not line_elem.findall("Branch"):
            warnings.append(f"line 端口格式异常,已跳过:src={src}, dst={direct_dst}")
    return lines


def get_subsystem_ref(block_elem: ET.Element) -> str | None:
    """读取 SubSystem block 的 System Ref。"""
    for child in block_elem:
        if child.tag == "System":
            return child.get("Ref")
    return None


def get_inline_system(block_elem: ET.Element) -> ET.Element | None:
    """读取内联 System 结构。"""
    for child in block_elem:
        if child.tag == "System" and child.get("Ref") is None:
            return child
    return None


def subsystem_key(block_elem: ET.Element) -> str:
    """返回 subsystem 字典使用的可读 key。"""
    return _clean_text(block_elem.get("Name")) or block_elem.get("SID") or "<unknown>"


def iter_subsystem_blocks(system_elem: ET.Element) -> list[ET.Element]:
    """返回当前 System 的直接 SubSystem block。"""
    return [
        block
        for block in system_elem.findall("Block")
        if _raw_block_type(block) == "SubSystem" or get_inline_system(block) is not None
    ]


def _parse_block(
    block_elem: ET.Element,
    parent_subsystem: str | None,
    warnings: list[str],
) -> SlxBlock:
    sid = block_elem.get("SID") or ""
    if not sid:
        raise ValueError("缺少 SID")
    raw_type = _raw_block_type(block_elem)
    if not raw_type:
        raw_type = "Unknown"
        warnings.append(f"block 缺少 BlockType 属性,SID={sid},标记为 Unknown")
    parameters = _collect_parameters(block_elem, raw_type)
    block_type = _effective_block_type(raw_type, parameters)
    position = _parse_position(parameters.get("Position"), sid, warnings)
    warnings.extend(collect_workspace_warnings(parameters))

    return SlxBlock(
        block_id=sid,
        name=_clean_text(block_elem.get("Name")) or sid,
        block_type=block_type,
        parameters=parameters,
        position=position,
        parent_subsystem=parent_subsystem,
        is_masked=is_masked(block_elem),
        is_library_link=is_library_link(block_elem),
        is_model_reference=is_model_reference(block_elem, raw_type),
    )


def _collect_parameters(block_elem: ET.Element, raw_type: str) -> dict[str, str]:
    params = {"BlockType": raw_type}
    for child in block_elem:
        if child.tag == "System":
            continue
        if child.tag == "P":
            _store_param(params, child)
            continue
        for param in child.iter("P"):
            _store_param(params, param)
    return params


def _store_param(params: dict[str, str], elem: ET.Element) -> None:
    name = elem.get("Name")
    if not name:
        return
    value = elem.text or ""
    params[name] = value.strip()


def _effective_block_type(raw_type: str, params: dict[str, str]) -> str:
    if raw_type == "Reference" and params.get("SourceType"):
        source_type = _clean_text(params["SourceType"]) or raw_type
        if {"Kp", "Ki"}.issubset(params) and "PI" not in source_type.upper():
            return f"{source_type} PI Controller"
        return source_type
    if raw_type == "SimscapeComponentBlock":
        component = params.get("ComponentPath") or params.get("ComponentName") or "Component"
        return "Simscape." + _clean_text(component)
    return _clean_text(raw_type) or "Unknown"


def _raw_block_type(block_elem: ET.Element) -> str:
    return block_elem.get("BlockType") or get_p_value(block_elem, "BlockType", "") or ""


def _parse_position(
    value: str | None,
    sid: str,
    warnings: list[str],
) -> tuple[int, int, int, int]:
    if not value:
        warnings.append(f"block 位置字段格式异常,使用 (0,0,0,0):SID={sid}")
        return (0, 0, 0, 0)
    nums = [int(num) for num in POSITION_RE.findall(value)]
    if len(nums) >= 4:
        return (nums[0], nums[1], nums[2], nums[3])
    warnings.append(f"block 位置字段格式异常,使用 (0,0,0,0):SID={sid}")
    return (0, 0, 0, 0)


def _collect_branch_lines(
    branch_elem: ET.Element,
    inherited_src: str | None,
    lines: list[SlxLine],
    warnings: list[str],
    depth: int,
) -> None:
    if depth > BRANCH_DEPTH_LIMIT:
        warnings.append("line 分支嵌套过深,已截断")
        return
    src = get_p_value(branch_elem, "Src") or inherited_src
    dst = get_p_value(branch_elem, "Dst")
    if src and dst:
        _append_line(lines, src, dst, warnings)
    for child in branch_elem.findall("Branch"):
        _collect_branch_lines(child, src, lines, warnings, depth + 1)


def _append_line(lines: list[SlxLine], src: str, dst: str, warnings: list[str]) -> None:
    parsed_src = _parse_port_ref(src)
    parsed_dst = _parse_port_ref(dst)
    if parsed_src is None or parsed_dst is None:
        warnings.append(f"line 端口格式异常,已跳过:src={src}, dst={dst}")
        return
    from_block, from_port = parsed_src
    to_block, to_port = parsed_dst
    lines.append(
        SlxLine(
            from_block=from_block,
            from_port=from_port,
            to_block=to_block,
            to_port=to_port,
        )
    )


def _parse_port_ref(value: str) -> tuple[str, int] | None:
    match = PORT_RE.match(value.strip())
    if not match:
        return None
    return (match.group("sid"), int(match.group("port")))


def _first_by_tag(elem: ET.Element, tag: str) -> ET.Element | None:
    if elem.tag == tag:
        return elem
    for child in elem.iter(tag):
        return child
    return None


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())
