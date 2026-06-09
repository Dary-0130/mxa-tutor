"""Build 5 类 project chunks from parsed project data."""

from __future__ import annotations

from pathlib import PurePosixPath

from loguru import logger

from app.config import AppSettings
from core.domain.project import FileInfo, Project
from core.domain.project_graph import ProjectGraph

from ._chunk_draft import ChunkDraft
from ._chunk_id import make_chunk_id
from ._source_text_templates import (
    build_m_file_source_text,
    build_m_function_source_text,
    build_m_script_section_source_text,
    build_mat_variable_source_text,
    build_slx_block_source_text,
    build_slx_subsystem_source_text,
    truncate_source_text,
)


def build_drafts(project: Project, graph: ProjectGraph, settings: AppSettings) -> list[ChunkDraft]:
    """Project path emits 5 类 project chunks; overview uses its own entry."""
    _ = graph
    drafts: list[ChunkDraft] = []
    drafts.extend(_build_m_file_drafts(project, settings))
    drafts.extend(_build_m_function_drafts(project, settings))
    drafts.extend(_build_m_script_drafts(project, settings))
    drafts.extend(_build_slx_block_drafts(project, settings))
    drafts.extend(_build_slx_subsystem_drafts(project, settings))
    drafts.extend(_build_mat_variable_drafts(project, settings))
    return drafts


def _build_m_file_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    from ._m_script_parser import split_m_script

    files_by_path = {_normalize_path(info.relative_path): info for info in project.files}
    drafts: list[ChunkDraft] = []
    for m_file in project.m_files:
        file_info = _find_file_info(files_by_path, m_file.file_path)
        if file_info is None:
            logger.warning(
                "m_file_chunk_skipped: project_id={} reason=missing_file_info", project.id
            )
            continue
        section_count = 0
        if not m_file.functions and m_file.raw_code:
            sections = split_m_script(m_file.raw_code, settings.chunking_max_chunks_per_m_script)
            section_count = len(sections)
        raw = build_m_file_source_text(
            file_info,
            m_file,
            description_max=settings.chunking_description_max_chars,
            section_count=section_count,
        )
        drafts.append(
            ChunkDraft(
                chunk_id=make_chunk_id(project.id, "m_file", m_file.file_path),
                project_id=project.id,
                source_type="m_file",
                file_path=m_file.file_path,
                symbol_name=None,
                line_range=None,
                block_id=None,
                block_name=None,
                block_type=None,
                parent_subsystem=None,
                source_text=_finalize_source_text(raw, settings),
            )
        )
    return drafts


def _build_m_script_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    from ._m_script_parser import split_m_script

    files_by_path = {_normalize_path(info.relative_path): info for info in project.files}
    drafts: list[ChunkDraft] = []
    for m_file in project.m_files:
        if m_file.functions or not m_file.raw_code:
            continue

        file_info = _find_file_info(files_by_path, m_file.file_path)
        if file_info is None:
            continue

        sections = split_m_script(m_file.raw_code, settings.chunking_max_chunks_per_m_script)
        total = len(sections)
        if total == 0:
            continue

        for section in sections:
            raw = build_m_script_section_source_text(
                file_info=file_info,
                m_file=m_file,
                section_index=section.index,
                section_total=total,
                section_title=section.title,
                section_code=section.code,
                code_max=settings.chunking_max_source_text_chars,
            )
            drafts.append(
                ChunkDraft(
                    chunk_id=make_chunk_id(
                        project.id, "m_file", m_file.file_path, f"section_{section.index}"
                    ),
                    project_id=project.id,
                    source_type="m_file",
                    file_path=m_file.file_path,
                    symbol_name=section.title if section.title else f"section_{section.index}",
                    line_range=None,
                    block_id=None,
                    block_name=None,
                    block_type=None,
                    parent_subsystem=None,
                    source_text=_finalize_source_text(raw, settings),
                )
            )
    return drafts


def _build_m_function_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for m_file in project.m_files:
        for func in m_file.functions:
            raw = build_m_function_source_text(
                m_file,
                func,
                docstring_max=settings.chunking_docstring_max_chars,
            )
            drafts.append(
                ChunkDraft(
                    chunk_id=make_chunk_id(project.id, "m_function", m_file.file_path, func.name),
                    project_id=project.id,
                    source_type="m_function",
                    file_path=m_file.file_path,
                    symbol_name=func.name,
                    line_range=func.line_range,
                    block_id=None,
                    block_name=None,
                    block_type=None,
                    parent_subsystem=None,
                    source_text=_finalize_source_text(raw, settings),
                )
            )
    return drafts


def _build_slx_block_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for model in project.slx_models:
        for block in model.blocks:
            raw = build_slx_block_source_text(
                model,
                block,
                param_value_max=settings.chunking_param_value_max_chars,
                max_params=settings.chunking_max_params_per_block,
            )
            drafts.append(
                ChunkDraft(
                    chunk_id=make_chunk_id(
                        project.id, "slx_block", model.file_path, block.block_id
                    ),
                    project_id=project.id,
                    source_type="slx_block",
                    file_path=model.file_path,
                    symbol_name=block.name,
                    line_range=None,
                    block_id=block.block_id,
                    block_name=block.name,
                    block_type=block.block_type,
                    parent_subsystem=block.parent_subsystem,
                    source_text=_finalize_source_text(raw, settings),
                )
            )
    return drafts


def _build_slx_subsystem_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for model in project.slx_models:
        block_id_to_name = {block.block_id: block.name for block in model.blocks}
        for subsystem_name, child_block_ids in model.subsystems.items():
            raw = build_slx_subsystem_source_text(
                model,
                subsystem_name,
                child_block_ids,
                block_id_to_name,
                settings.chunking_max_subsystem_child_block_names,
            )
            drafts.append(
                ChunkDraft(
                    chunk_id=make_chunk_id(
                        project.id, "slx_subsystem", model.file_path, subsystem_name
                    ),
                    project_id=project.id,
                    source_type="slx_subsystem",
                    file_path=model.file_path,
                    symbol_name=subsystem_name,
                    line_range=None,
                    block_id=None,
                    block_name=subsystem_name,
                    block_type="Subsystem",
                    parent_subsystem=None,
                    source_text=_finalize_source_text(raw, settings),
                )
            )
    return drafts


def _build_mat_variable_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for mat in project.mat_files:
        for var in mat.variables:
            raw = build_mat_variable_source_text(mat, var)
            drafts.append(
                ChunkDraft(
                    chunk_id=make_chunk_id(project.id, "mat_variable", mat.file_path, var.name),
                    project_id=project.id,
                    source_type="mat_variable",
                    file_path=mat.file_path,
                    symbol_name=var.name,
                    line_range=None,
                    block_id=None,
                    block_name=None,
                    block_type=None,
                    parent_subsystem=None,
                    source_text=_finalize_source_text(raw, settings),
                )
            )
    return drafts


def _finalize_source_text(raw: str, settings: AppSettings) -> str:
    return truncate_source_text(raw, settings.chunking_max_source_text_chars)


def _find_file_info(files_by_path: dict[str, FileInfo], file_path: str) -> FileInfo | None:
    normalized = _normalize_path(file_path)
    if normalized in files_by_path:
        return files_by_path[normalized]
    matches = [info for path, info in files_by_path.items() if normalized.endswith(f"/{path}")]
    return matches[0] if len(matches) == 1 else None


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path.replace("\\", "/"))).lstrip("./").rstrip("/")
