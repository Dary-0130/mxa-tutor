"""Source text templates and truncation helpers."""

from __future__ import annotations

from typing import Final

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo
from core.domain.project_overview import ProjectOverview
from core.domain.slx_model import SlxBlock, SlxModel
from core.domain.teaching_unit import TeachingUnit

from ._c_source_splitter import CSourceSection
from ._h_source_splitter import HSourceSection
from ._workspace_resolver import is_unresolved_var_ref

_TRUNCATE_MARKER: Final[str] = "[…]"
_SOURCE_TEXT_MAX_CHARS_DEFAULT: Final[int] = 1024


def _collapse_whitespace(text: str) -> str:
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in text)
    return " ".join(cleaned.split())


def _truncate_field(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(_TRUNCATE_MARKER):
        return _TRUNCATE_MARKER[:max_chars]
    return text[: max_chars - len(_TRUNCATE_MARKER)] + _TRUNCATE_MARKER


def truncate_source_text(
    text: str,
    max_chars: int = _SOURCE_TEXT_MAX_CHARS_DEFAULT,
) -> str:
    return _truncate_field(_collapse_whitespace(text), max_chars)


def build_m_file_source_text(
    file_info: FileInfo,
    m_file: MFile,
    description_max: int,
    section_count: int = 0,
    public_file_path: str | None = None,
) -> str:
    file_path = public_file_path or file_info.relative_path
    desc = _truncate_field(_collapse_whitespace(file_info.description or ""), description_max)
    if m_file.functions:
        body = f"含 {len(m_file.functions)} 个函数"
    elif section_count > 0:
        body = f"含 {section_count} 段赋值"
    else:
        body = "无函数无赋值"
    return f"文件 {file_path},类型 {file_info.file_type}," f"角色 {m_file.file_role},{body}。{desc}"


def build_m_script_section_source_text(
    file_info: FileInfo,
    m_file: MFile,
    section_index: int,
    section_total: int,
    section_title: str,
    section_code: str,
    code_max: int,
    public_file_path: str | None = None,
) -> str:
    """Build source_text for a single script section chunk."""
    _ = m_file
    file_path = public_file_path or file_info.relative_path
    title_part = f"标题 {section_title}" if section_title else ""
    code = _truncate_field(section_code, code_max)
    return f"脚本 {file_path} 第 {section_index} 段(共 {section_total} 段){title_part}\n" f"{code}"


def build_m_function_source_text(
    m_file: MFile,
    func: MFunction,
    docstring_max: int,
    public_file_path: str | None = None,
) -> str:
    file_path = public_file_path or m_file.file_path
    doc = _truncate_field(_collapse_whitespace(func.docstring or ""), docstring_max)
    return f"函数 {func.name} 位于 {file_path}," f"输入 {func.inputs},输出 {func.outputs}。{doc}"


def build_slx_block_source_text(
    model: SlxModel,
    block: SlxBlock,
    param_value_max: int,
    max_params: int,
    *,
    params_override: dict[str, str] | None = None,
    workspace_literals: dict[str, str] | None = None,
    public_file_path: str | None = None,
) -> str:
    file_path = public_file_path or model.file_path
    parent = block.parent_subsystem or "顶层"
    params = params_override if params_override is not None else block.parameters
    sorted_items = sorted(params.items())[:max_params]
    param_parts: list[str] = []
    for key, value in sorted_items:
        value_text = _collapse_whitespace(str(value))
        value_truncated = _truncate_field(value_text, param_value_max)
        value_stripped = value_text.strip()
        if workspace_literals is not None and is_unresolved_var_ref(
            value_stripped, workspace_literals
        ):
            param_parts.append(f"{key}={value_truncated}[未在 workspace 定义]")
        elif workspace_literals is not None and value_stripped in workspace_literals:
            actual = _truncate_field(workspace_literals[value_stripped], param_value_max)
            param_parts.append(f"{key}={value_truncated}(={actual})")
        else:
            param_parts.append(f"{key}={value_truncated}")
    params_str = ",".join(param_parts)
    flags = []
    if block.is_library_link:
        flags.append("library_link")
    if block.is_model_reference:
        flags.append("model_reference")
    if getattr(block, "is_masked", False):
        flags.append("masked")
    flag_text = f",标记 {'/'.join(flags)}" if flags else ""
    return (
        f"Block {block.name}({block.block_type}) 位于 {file_path}/{parent},"
        f"参数 {params_str}{flag_text}"
    )


def build_slx_subsystem_source_text(
    model: SlxModel,
    subsystem_name: str,
    child_block_ids: list[str],
    block_id_to_name: dict[str, str],
    top_n: int,
    public_file_path: str | None = None,
) -> str:
    file_path = public_file_path or model.file_path
    names = [block_id_to_name[bid] for bid in child_block_ids[:top_n] if bid in block_id_to_name]
    suffix = f"等 {len(child_block_ids)} 个" if len(child_block_ids) > top_n else ""
    return (
        f"子系统 {subsystem_name} 在 {file_path} 内,"
        f"包含 {len(child_block_ids)} 个 block。子 block:{','.join(names)}{suffix}"
    )


def build_mat_variable_source_text(
    mat: MatMetadata,
    var: MatVariable,
    public_file_path: str | None = None,
) -> str:
    file_path = public_file_path or mat.file_path
    role_suffix = f",角色 {var.likely_role}" if var.likely_role else ""
    return f"变量 {var.name} 在 {file_path} 中,类型 {var.var_type},shape {var.shape}{role_suffix}"


def build_c_source_text(
    file_info: FileInfo,
    section: CSourceSection,
    evidence_max_lines: int = 10,
) -> str:
    signature = _section_signature(section)
    evidence = _select_code_evidence(section.code, evidence_max_lines)
    globals_text = _global_declaration_summary(section.code)
    globals_part = f"\n关键全局声明:\n{globals_text}" if globals_text else ""
    return (
        f"C 源码 {file_info.relative_path},kind={section.kind},"
        f"line_range={section.line_start}-{section.line_end},title={section.title}\n"
        f"签名: {signature}{globals_part}\n"
        f"证据摘录(最多 {evidence_max_lines} 行):\n{evidence}"
    )


def build_h_source_text(
    file_info: FileInfo,
    section: HSourceSection,
    evidence_max_lines: int = 10,
) -> str:
    signature = _section_signature(section)
    evidence = _select_code_evidence(section.code, evidence_max_lines)
    return (
        f"头文件 {file_info.relative_path},kind={section.kind},"
        f"line_range={section.line_start}-{section.line_end},title={section.title}\n"
        f"签名: {signature}\n"
        f"证据摘录(最多 {evidence_max_lines} 行):\n{evidence}"
    )


def build_project_overview_source_text(overview: ProjectOverview) -> str:
    return (
        f"项目 {overview.project_title} 类型 {overview.project_type}。"
        f"{overview.one_sentence_summary} "
        f"主流程 {','.join(overview.main_execution_flow)}。"
        f"知识点 {','.join(overview.knowledge_points)}。"
        f"建议阅读顺序 {','.join(overview.beginner_reading_order)}。"
        f"常见困惑 {','.join(overview.likely_confusing_points)}"
    )


def build_teaching_unit_source_text(unit: TeachingUnit) -> str:
    return (
        f"教学单元 {unit.title}({unit.level}):{unit.summary} "
        f"讲解步骤 {','.join(unit.explanation_steps)}"
    )


def _section_signature(section: CSourceSection) -> str:
    for line in section.code.splitlines():
        stripped = line.strip()
        if stripped:
            return _truncate_field(stripped, 180)
    return section.title


def _select_code_evidence(code: str, max_lines: int) -> str:
    if max_lines <= 0:
        return ""
    meaningful = [
        line.rstrip()
        for line in code.splitlines()
        if line.strip() and line.strip() not in {"{", "}"}
    ]
    if not meaningful:
        return ""

    priority_terms = (
        "OutMax",
        "OutMin",
        "Kp",
        "Ki",
        "Phase",
        "Tsw",
        "pid_calc",
        "typedef",
        "#define",
        "static",
    )
    selected: list[str] = []
    for line in meaningful:
        if any(term in line for term in priority_terms):
            selected.append(line)
            if len(selected) >= max_lines:
                return "\n".join(selected)

    for line in meaningful:
        if line not in selected:
            selected.append(line)
            if len(selected) >= max_lines:
                break
    return "\n".join(selected)


def _global_declaration_summary(code: str) -> str:
    lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "#")):
            continue
        if any(stripped.startswith(prefix) for prefix in ("float ", "int ", "real_T ", "double ")):
            lines.append(stripped)
        if len(lines) >= 5:
            break
    return "\n".join(lines)
