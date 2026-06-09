"""Build 5 类 project chunks from parsed project data."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Final, NamedTuple

from loguru import logger

from app.config import AppSettings
from core.domain.project import FileInfo, Project
from core.domain.project_graph import ProjectGraph
from core.domain.slx_model import SlxBlock, SlxModel

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

METADATA_PARAM_KEYS: Final[frozenset[str]] = frozenset(
    {
        "SourceBlock",
        "SourceType",
        "Position",
        "ZOrder",
        "BlockMirror",
        "BlockRotation",
        "NameLocation",
        "ContentPreviewEnabled",
        "IconDisplay",
        "DisplayOption",
        "GotoTag",
        "RTWMemSecDataConstants",
        "RTWMemSecDataInternal",
        "RTWMemSecDataParameters",
        "RTWMemSecFuncExecute",
        "LibraryVersion",
        "LibrarySourceBlock",
        "LConnTagsString",
        "RConnTagsString",
    }
)

DROP_BLOCK_TYPES: Final[frozenset[str]] = frozenset(
    {
        "scope",
        "clock",
        "from",
        "goto",
        "mux",
        "demux",
        "display",
    }
)

_GroupKey = tuple[str, str, str, tuple[tuple[str, str], ...]]


class _SlxBlockCandidate(NamedTuple):
    model: SlxModel
    block: SlxBlock
    meaningful: dict[str, str]
    group_key: _GroupKey


def _meaningful_params(params: dict[str, str]) -> dict[str, str]:
    """过滤掉 Simulink 元数据参数,只保留有工程价值的参数。"""
    return {
        key: str(value).strip()
        for key, value in params.items()
        if key not in METADATA_PARAM_KEYS and str(value).strip()
    }


def _has_engineering_value(params: dict[str, str]) -> bool:
    """参数值里有没有工程信息(数值/变量引用),还是全是元数据。"""
    return bool(_meaningful_params(params))


def _has_block_engineering_value(block: SlxBlock, meaningful: dict[str, str]) -> bool:
    return (
        bool(meaningful)
        or block.is_library_link
        or block.is_model_reference
        or getattr(block, "is_masked", False)
    )


def _normalize_block_type(block_type: str) -> str:
    """统一 block_type 到小写无多余空格。"""
    return " ".join(block_type.strip().lower().split())


def _should_drop_block(block_type: str) -> bool:
    return _normalize_block_type(block_type) in DROP_BLOCK_TYPES


def _normalized_param_items(
    params: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value).strip()) for key, value in params.items()))


def _group_key(
    file_path: str,
    parent_subsystem: str | None,
    block_type: str,
    meaningful: dict[str, str],
) -> _GroupKey:
    return (
        file_path,
        parent_subsystem or "",
        _normalize_block_type(block_type),
        _normalized_param_items(meaningful),
    )


def _copy_family_name(name: str) -> str:
    """Mosfet7 -> mosfet, Series RLC Branch1 -> series rlc branch"""
    return re.sub(r"\d+$", "", name).strip().lower()


def _should_merge_group(blocks: list[SlxBlock]) -> bool:
    """只在 ≥3 个同 family name 时合并,防误合并。"""
    if len(blocks) < 3:
        return False
    families = {_copy_family_name(block.name) for block in blocks}
    return len(families) == 1


def _group_duplicate_blocks(
    candidates: list[_SlxBlockCandidate],
) -> list[list[_SlxBlockCandidate]]:
    groups: defaultdict[_GroupKey, list[_SlxBlockCandidate]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.group_key].append(candidate)
    return list(groups.values())


def _is_block_parameters_section(section_title: str) -> bool:
    """识别 .m 导出脚本的 Block Parameters 段。"""
    lower = section_title.lower()
    return "block parameters" in lower or lower.startswith("section 4")


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
            if _is_block_parameters_section(section.title):
                continue
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
    candidates: list[_SlxBlockCandidate] = []
    for model in project.slx_models:
        for block in model.blocks:
            if _should_drop_block(block.block_type):
                continue

            meaningful = _meaningful_params(block.parameters)
            if not _has_block_engineering_value(block, meaningful):
                continue

            candidates.append(
                _SlxBlockCandidate(
                    model=model,
                    block=block,
                    meaningful=meaningful,
                    group_key=_group_key(
                        model.file_path,
                        block.parent_subsystem,
                        block.block_type,
                        meaningful,
                    ),
                )
            )

    drafts: list[ChunkDraft] = []
    for group in _group_duplicate_blocks(candidates):
        blocks = [candidate.block for candidate in group]
        if group[0].meaningful and _should_merge_group(blocks):
            drafts.append(_build_merged_slx_block_draft(project, settings, group))
            continue

        for candidate in group:
            drafts.append(_build_slx_block_draft(project, settings, candidate))
    return drafts


def _build_slx_block_draft(
    project: Project,
    settings: AppSettings,
    candidate: _SlxBlockCandidate,
) -> ChunkDraft:
    raw = build_slx_block_source_text(
        candidate.model,
        candidate.block,
        param_value_max=settings.chunking_param_value_max_chars,
        max_params=settings.chunking_max_params_per_block,
        params_override=candidate.meaningful,
    )
    return ChunkDraft(
        chunk_id=make_chunk_id(
            project.id, "slx_block", candidate.model.file_path, candidate.block.block_id
        ),
        project_id=project.id,
        source_type="slx_block",
        file_path=candidate.model.file_path,
        symbol_name=candidate.block.name,
        line_range=None,
        block_id=candidate.block.block_id,
        block_name=candidate.block.name,
        block_type=candidate.block.block_type,
        parent_subsystem=candidate.block.parent_subsystem,
        source_text=_finalize_source_text(raw, settings),
    )


def _build_merged_slx_block_draft(
    project: Project,
    settings: AppSettings,
    group: list[_SlxBlockCandidate],
) -> ChunkDraft:
    representative = group[0]
    names = [candidate.block.name for candidate in group]
    raw = build_slx_block_source_text(
        representative.model,
        representative.block,
        param_value_max=settings.chunking_param_value_max_chars,
        max_params=settings.chunking_max_params_per_block,
        params_override=representative.meaningful,
    )
    raw = (
        f"{raw},合并同参数重复 block 总数 {len(group)},"
        f"代表 block {representative.block.name},实例 {','.join(names)}"
    )
    return ChunkDraft(
        chunk_id=make_chunk_id(
            project.id,
            "slx_block",
            representative.model.file_path,
            representative.block.block_id,
        ),
        project_id=project.id,
        source_type="slx_block",
        file_path=representative.model.file_path,
        symbol_name=representative.block.name,
        line_range=None,
        block_id=representative.block.block_id,
        block_name=representative.block.name,
        block_type=representative.block.block_type,
        parent_subsystem=representative.block.parent_subsystem,
        source_text=_finalize_source_text(raw, settings),
    )


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
