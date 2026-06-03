"""ProjectGraph node builders."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from core.domain.m_file import MFile
from core.domain.mat_metadata import MatMetadata
from core.domain.project_graph import NodeType, ProjectNode
from core.domain.slx_model import SlxBlock, SlxModel
from core.domain.source_ref import SourceRef

from ._node_id import (
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_file_slx_id,
    make_function_id,
    make_subsystem_id,
)
from ._pg_diagnostics import _BuildDiagnostics

ParameterPolicy = Literal["all", "key", "none"]

__all__ = [
    "build_block_and_subsystem_nodes",
    "build_file_m_nodes",
    "build_file_mat_nodes",
    "build_file_slx_nodes",
    "build_function_nodes",
]


def build_file_m_nodes(m_files: list[MFile]) -> list[ProjectNode]:
    """Build FILE_M nodes from parsed MATLAB files."""
    nodes: list[ProjectNode] = []
    for m_file in sorted(m_files, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(m_file.file_path)
        nodes.append(
            ProjectNode(
                id=make_file_m_id(relpath),
                type=NodeType.FILE_M,
                label=PurePosixPath(relpath).name,
                source_ref=SourceRef(file_path=relpath),
                metadata={
                    "file:role": m_file.file_role,
                    "file:imports": ",".join(m_file.imports),
                    "file:uses_toolbox": ",".join(m_file.uses_toolbox),
                },
            )
        )
    return nodes


def build_function_nodes(m_files: list[MFile]) -> list[ProjectNode]:
    """Build FUNCTION nodes from MFile.functions."""
    nodes: list[ProjectNode] = []
    for m_file in sorted(m_files, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(m_file.file_path)
        for function in sorted(m_file.functions, key=lambda item: item.name):
            start, end = function.line_range
            nodes.append(
                ProjectNode(
                    id=make_function_id(relpath, function.name),
                    type=NodeType.FUNCTION,
                    label=function.name,
                    source_ref=SourceRef(file_path=relpath, line_range=function.line_range),
                    metadata={
                        "fn:inputs": ",".join(function.inputs),
                        "fn:outputs": ",".join(function.outputs),
                        "fn:line_range": f"{start}-{end}",
                        "fn:docstring": function.docstring or "",
                    },
                )
            )
    return nodes


def build_file_slx_nodes(slx_models: list[SlxModel], diag: _BuildDiagnostics) -> list[ProjectNode]:
    """Build FILE_SLX nodes from parsed Simulink models."""
    nodes: list[ProjectNode] = []
    for model in sorted(slx_models, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(model.file_path)
        metadata = {"slx:model_name": model.name}
        metadata.update(
            {f"slx:solver_{key}": str(value) for key, value in sorted(model.solver_config.items())}
        )
        if model.parse_warnings:
            metadata["partial_parse"] = "true"
            diag.add("partial_parse", relpath)
        nodes.append(
            ProjectNode(
                id=make_file_slx_id(relpath),
                type=NodeType.FILE_SLX,
                label=model.name,
                source_ref=SourceRef(file_path=relpath),
                metadata=metadata,
            )
        )
    return nodes


def build_block_and_subsystem_nodes(
    slx_models: list[SlxModel],
    diag: _BuildDiagnostics,
    expand_subsystems: bool = True,
    include_block_parameters: ParameterPolicy = "all",
) -> list[ProjectNode]:
    """Build BLOCK and SUBSYSTEM nodes from SlxModel.blocks."""
    nodes: list[ProjectNode] = []
    for model in sorted(slx_models, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(model.file_path)
        existing_subsystems: set[str] = set()
        for block in sorted(model.blocks, key=lambda item: (item.name, item.block_id)):
            if not expand_subsystems and block.parent_subsystem:
                continue
            if block.block_type == "SubSystem":
                existing_subsystems.add(block.name)
                nodes.append(_make_subsystem_node(relpath, block, include_block_parameters))
                continue
            nodes.append(_make_block_node(relpath, block, include_block_parameters))

        for subsystem_name in sorted(model.subsystems):
            if subsystem_name in existing_subsystems:
                continue
            diag.add("partial_parse", relpath)
            nodes.append(_make_synthetic_subsystem_node(relpath, subsystem_name))
    return sorted(nodes, key=lambda node: node.id)


def build_file_mat_nodes(mat_files: list[MatMetadata]) -> list[ProjectNode]:
    """Build FILE_MAT nodes from .mat metadata."""
    nodes: list[ProjectNode] = []
    for mat_file in sorted(mat_files, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(mat_file.file_path)
        nodes.append(
            ProjectNode(
                id=make_file_mat_id(relpath),
                type=NodeType.FILE_MAT,
                label=PurePosixPath(relpath).name,
                source_ref=SourceRef(file_path=relpath),
                metadata={
                    "mat:file_size_bytes": str(mat_file.file_size_bytes),
                    "mat:variable_count": str(len(mat_file.variables)),
                },
            )
        )
    return nodes


def _make_block_node(relpath: str, block: SlxBlock, policy: ParameterPolicy) -> ProjectNode:
    return ProjectNode(
        id=make_block_id(relpath, block.block_id),
        type=NodeType.BLOCK,
        label=block.name,
        source_ref=_block_source_ref(relpath, block),
        metadata=_block_metadata(block, policy),
    )


def _make_subsystem_node(relpath: str, block: SlxBlock, policy: ParameterPolicy) -> ProjectNode:
    return ProjectNode(
        id=make_subsystem_id(relpath, block.name),
        type=NodeType.SUBSYSTEM,
        label=block.name,
        source_ref=_block_source_ref(relpath, block),
        metadata=_block_metadata(block, policy),
    )


def _make_synthetic_subsystem_node(relpath: str, name: str) -> ProjectNode:
    return ProjectNode(
        id=make_subsystem_id(relpath, name),
        type=NodeType.SUBSYSTEM,
        label=name,
        source_ref=SourceRef(file_path=relpath, block_name=name),
        metadata={"synthetic": "true"},
    )


def _block_source_ref(relpath: str, block: SlxBlock) -> SourceRef:
    return SourceRef(
        file_path=relpath,
        block_id=block.block_id,
        block_name=block.name,
        parent_subsystem=block.parent_subsystem,
    )


def _block_metadata(block: SlxBlock, policy: ParameterPolicy) -> dict[str, str]:
    metadata = {
        "block:type": block.block_type,
        "block:position": ",".join(str(part) for part in block.position),
        "block:is_masked": _bool_str(block.is_masked),
        "block:is_library_link": _bool_str(block.is_library_link),
        "block:is_model_reference": _bool_str(block.is_model_reference),
        "block:parent_subsystem": block.parent_subsystem or "",
    }
    if policy in {"all", "key"}:
        for key, value in sorted(block.parameters.items()):
            metadata[f"param:{key}"] = str(value)
    return metadata


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _normalize_relpath(path: str) -> str:
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    return normalized.lstrip("./").rstrip("/")
