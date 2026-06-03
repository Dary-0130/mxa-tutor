"""ProjectGraph edge builders."""

from __future__ import annotations

from pathlib import PurePosixPath

from core.domain.m_file import MFile
from core.domain.project_graph import EdgeType, ProjectEdge, ProjectNode
from core.domain.slx_model import SlxBlock, SlxModel

from ._node_id import (
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_file_slx_id,
    make_function_id,
    make_subsystem_id,
)
from ._pg_diagnostics import _BuildDiagnostics

__all__ = [
    "build_belongs_to_edges",
    "build_calls_edges",
    "build_loads_data_edges",
    "build_signal_flows_edges",
]


def build_calls_edges(
    file_dependencies: dict[str, list[str]],
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> list[ProjectEdge]:
    """Build CALLS edges from file-level dependencies."""
    edges: list[ProjectEdge] = []
    for source_relpath, target_relpaths in sorted(file_dependencies.items()):
        source_id = _file_node_id(source_relpath)
        if source_id is None or source_id not in node_index:
            diag.add("unresolved", f"file_dep_source:{_normalize_relpath(source_relpath)}")
            continue
        for target_relpath in sorted(target_relpaths):
            target_ext = PurePosixPath(_normalize_relpath(target_relpath)).suffix.lower()
            if target_ext not in {".m", ".slx"}:
                if target_ext != ".mat":
                    diag.add("unresolved", f"file_dep_target:{_normalize_relpath(target_relpath)}")
                continue
            target_id = _file_node_id(target_relpath)
            if target_id is None or target_id not in node_index:
                diag.add("unresolved", f"file_dep_target:{_normalize_relpath(target_relpath)}")
                continue
            edges.append(ProjectEdge(from_node=source_id, to_node=target_id, type=EdgeType.CALLS))
    return _dedup_and_sort_edges(edges)


def build_loads_data_edges(
    file_dependencies: dict[str, list[str]],
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> list[ProjectEdge]:
    """Build LOADS_DATA edges from .m file dependencies to .mat files."""
    edges: list[ProjectEdge] = []
    for source_relpath, target_relpaths in sorted(file_dependencies.items()):
        source_id = _file_node_id(source_relpath)
        if source_id is None or source_id not in node_index:
            continue
        for target_relpath in sorted(target_relpaths):
            target = _normalize_relpath(target_relpath)
            if PurePosixPath(target).suffix.lower() != ".mat":
                continue
            target_id = make_file_mat_id(target)
            if target_id not in node_index:
                diag.add("unresolved", f"file_dep_target:{target}")
                continue
            edges.append(ProjectEdge(source_id, target_id, EdgeType.LOADS_DATA))
    return _dedup_and_sort_edges(edges)


def build_signal_flows_edges(
    slx_models: list[SlxModel],
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> list[ProjectEdge]:
    """Build SIGNAL_FLOWS edges from SlxModel.lines."""
    edges: list[ProjectEdge] = []
    block_ref_map = _build_block_ref_map(slx_models, node_index)
    for model in sorted(slx_models, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(model.file_path)
        for line in model.lines:
            from_id = block_ref_map.get((relpath, line.from_block))
            to_id = block_ref_map.get((relpath, line.to_block))
            if from_id is None or to_id is None:
                diag.add("unresolved", f"line<{line.from_block}→{line.to_block}>")
                continue
            edges.append(ProjectEdge(from_id, to_id, EdgeType.SIGNAL_FLOWS))
    return _dedup_and_sort_edges(edges)


def build_belongs_to_edges(
    slx_models: list[SlxModel],
    m_files: list[MFile],
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> list[ProjectEdge]:
    """Build BELONGS_TO edges for functions, blocks, subsystems, and files."""
    edges: list[ProjectEdge] = []
    edges.extend(_build_function_belongs_to_edges(m_files, node_index))
    edges.extend(_build_slx_belongs_to_edges(slx_models, node_index, diag))
    return _dedup_and_sort_edges(edges)


def _build_function_belongs_to_edges(
    m_files: list[MFile],
    node_index: dict[str, ProjectNode],
) -> list[ProjectEdge]:
    edges: list[ProjectEdge] = []
    for m_file in sorted(m_files, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(m_file.file_path)
        file_id = make_file_m_id(relpath)
        if file_id not in node_index:
            continue
        for function in sorted(m_file.functions, key=lambda item: item.name):
            function_id = make_function_id(relpath, function.name)
            if function_id in node_index:
                edges.append(ProjectEdge(function_id, file_id, EdgeType.BELONGS_TO))
    return edges


def _build_slx_belongs_to_edges(
    slx_models: list[SlxModel],
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> list[ProjectEdge]:
    edges: list[ProjectEdge] = []
    block_ref_map = _build_block_ref_map(slx_models, node_index)
    for model in sorted(slx_models, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(model.file_path)
        file_id = make_file_slx_id(relpath)
        if file_id not in node_index:
            continue
        subsystem_block_names = {
            block.name for block in model.blocks if block.block_type == "SubSystem"
        }
        for block in sorted(model.blocks, key=lambda item: (item.name, item.block_id)):
            child_id = _block_node_id(relpath, block)
            if child_id not in node_index:
                continue
            parent_id = _block_parent_id(relpath, block, file_id, node_index, diag)
            if parent_id is not None:
                edges.append(ProjectEdge(child_id, parent_id, EdgeType.BELONGS_TO))

        for subsystem_name, child_refs in sorted(model.subsystems.items()):
            parent_id = make_subsystem_id(relpath, subsystem_name)
            if parent_id not in node_index:
                diag.add("unresolved", f"subsystem<{subsystem_name}>")
                continue
            if subsystem_name not in subsystem_block_names:
                edges.append(ProjectEdge(parent_id, file_id, EdgeType.BELONGS_TO))
            for child_ref in sorted(child_refs):
                mapped_child_id = block_ref_map.get((relpath, child_ref))
                if mapped_child_id is not None and mapped_child_id in node_index:
                    edges.append(ProjectEdge(mapped_child_id, parent_id, EdgeType.BELONGS_TO))
    return edges


def _block_parent_id(
    relpath: str,
    block: SlxBlock,
    file_id: str,
    node_index: dict[str, ProjectNode],
    diag: _BuildDiagnostics,
) -> str | None:
    if block.parent_subsystem is None:
        return file_id
    parent_id = make_subsystem_id(relpath, block.parent_subsystem)
    if parent_id not in node_index:
        diag.add("unresolved", f"subsystem<{block.parent_subsystem}>")
        return None
    return parent_id


def _build_block_ref_map(
    slx_models: list[SlxModel],
    node_index: dict[str, ProjectNode],
) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for model in slx_models:
        relpath = _normalize_relpath(model.file_path)
        for block in model.blocks:
            node_id = _block_node_id(relpath, block)
            if node_id not in node_index:
                continue
            result[(relpath, block.block_id)] = node_id
            result.setdefault((relpath, block.name), node_id)
    return result


def _block_node_id(relpath: str, block: SlxBlock) -> str:
    if block.block_type == "SubSystem":
        return make_subsystem_id(relpath, block.name)
    return make_block_id(relpath, block.block_id)


def _file_node_id(relpath: str) -> str | None:
    normalized = _normalize_relpath(relpath)
    ext = PurePosixPath(normalized).suffix.lower()
    if ext == ".m":
        return make_file_m_id(normalized)
    if ext == ".slx":
        return make_file_slx_id(normalized)
    if ext == ".mat":
        return make_file_mat_id(normalized)
    return None


def _dedup_and_sort_edges(edges: list[ProjectEdge]) -> list[ProjectEdge]:
    seen: set[tuple[str, str, str]] = set()
    result: list[ProjectEdge] = []
    for edge in sorted(edges, key=lambda item: (item.from_node, item.to_node, item.type.value)):
        key = (edge.from_node, edge.to_node, edge.type.value)
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def _normalize_relpath(path: str) -> str:
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    return normalized.lstrip("./").rstrip("/")
