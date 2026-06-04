"""Build overview prompt messages from Project and ProjectGraph."""

from __future__ import annotations

from typing import Final

from core.domain.project import Project
from core.domain.project_graph import ProjectGraph
from core.domain.teaching_unit import TeachingUnit
from core.interfaces.llm_provider import LLMMessage

from ._prompt_loader import load_prompt_template

MAX_UNRESOLVED_SYMBOLS_IN_PROMPT: Final[int] = 50
MAX_BLOCKS_PER_MODEL_IN_PROMPT: Final[int] = 50


def build_messages(
    project: Project,
    graph: ProjectGraph,
    project_type_hint: str,
    teaching_units: list[TeachingUnit] | None = None,
) -> list[LLMMessage]:
    """Build system/user messages for overview generation."""
    _ = teaching_units
    template = load_prompt_template()
    user = template.user.format(
        project_name=project.name,
        project_type_hint=project_type_hint,
        file_list=_format_file_list(project),
        entry_points=_format_strings(graph.entry_points),
        execution_flow=_format_strings(graph.execution_flow),
        unresolved_count=len(graph.unresolved_symbols),
        unresolved_symbols=_format_unresolved(graph.unresolved_symbols),
        slx_summaries=_format_slx_summaries(project),
        block_summaries=_format_block_summaries(project),
        m_function_summaries=_format_m_function_summaries(project),
    )
    return [
        LLMMessage(role="system", content=template.system),
        LLMMessage(role="user", content=user),
    ]


def _format_file_list(project: Project) -> str:
    if not project.files:
        return "(none)"
    lines = []
    for file_info in project.files:
        desc = f" - {file_info.description}" if file_info.description else ""
        lines.append(
            f"- {file_info.relative_path} ({file_info.file_type}, "
            f"{file_info.size_bytes} bytes){desc}"
        )
    return "\n".join(lines)


def _format_strings(values: list[str]) -> str:
    if not values:
        return "(none)"
    return "\n".join(f"- {value}" for value in values)


def _format_unresolved(values: list[str]) -> str:
    if not values:
        return "(none)"
    visible = values[:MAX_UNRESOLVED_SYMBOLS_IN_PROMPT]
    lines = [f"- {value}" for value in visible]
    omitted = len(values) - len(visible)
    if omitted > 0:
        lines.append(f"- 还有 {omitted} 项未列出")
    return "\n".join(lines)


def _format_slx_summaries(project: Project) -> str:
    if not project.slx_models:
        return "(none)"
    lines = []
    for model in project.slx_models:
        lines.append(
            f"- {model.file_path}: name={model.name}, blocks={len(model.blocks)}, "
            f"lines={len(model.lines)}, subsystems={len(model.subsystems)}"
        )
    return "\n".join(lines)


def _format_block_summaries(project: Project) -> str:
    if not project.slx_models:
        return "(none)"
    sections = []
    for model in project.slx_models:
        lines = [f"{model.file_path}:"]
        visible = model.blocks[:MAX_BLOCKS_PER_MODEL_IN_PROMPT]
        for block in visible:
            parent = block.parent_subsystem or "<root>"
            lines.append(
                f"- name={block.name}; type={block.block_type}; "
                f"id={block.block_id}; parent={parent}"
            )
        omitted = len(model.blocks) - len(visible)
        if omitted > 0:
            lines.append(f"- 还有 {omitted} 个 block 未列出")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _format_m_function_summaries(project: Project) -> str:
    if not project.m_files:
        return "(none)"
    lines = []
    for m_file in project.m_files:
        if not m_file.functions:
            lines.append(f"- {m_file.file_path}: role={m_file.file_role}, functions=(none)")
            continue
        for func in m_file.functions:
            doc = f", doc={func.docstring}" if func.docstring else ""
            lines.append(
                f"- {m_file.file_path}::{func.name} lines={func.line_range}, "
                f"inputs={func.inputs}, outputs={func.outputs}{doc}"
            )
    return "\n".join(lines)
