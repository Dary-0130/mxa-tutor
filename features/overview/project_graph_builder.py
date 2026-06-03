"""ProjectGraph builder for the overview feature.

The builder converts a parsed Project into a ProjectGraph through pure
structured transformations. It does not call LLMs, rescan raw MATLAB code, or
execute user-provided code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from core.domain.exceptions import ProjectError
from core.domain.project import Project
from core.domain.project_graph import ProjectEdge, ProjectGraph, ProjectNode

from ._pg_diagnostics import _BuildDiagnostics
from ._pg_edges import (
    build_belongs_to_edges,
    build_calls_edges,
    build_loads_data_edges,
    build_signal_flows_edges,
)
from ._pg_nodes import (
    build_block_and_subsystem_nodes,
    build_file_m_nodes,
    build_file_mat_nodes,
    build_file_slx_nodes,
    build_function_nodes,
)
from ._pg_topology import infer_entry_points, topological_sort

__all__ = ["ProjectGraphBuilder"]


class ProjectGraphBuilder:
    """Build ProjectGraph from Project using structural parser outputs only.

    Args:
        expand_subsystems: Whether to include blocks nested under subsystems.
        include_block_parameters: Controls block parameter metadata.
        entry_point_heuristics: Reserved for Phase 2 custom heuristics.
    """

    def __init__(
        self,
        expand_subsystems: bool = True,
        include_block_parameters: Literal["all", "key", "none"] = "all",
        entry_point_heuristics: list[Callable[[Project], set[str]]] | None = None,
    ) -> None:
        if include_block_parameters not in ("all", "key", "none"):
            raise ValueError(
                f"include_block_parameters must be one of "
                f"('all', 'key', 'none'), got {include_block_parameters!r}"
            )
        self._expand_subsystems = expand_subsystems
        self._include_block_parameters = include_block_parameters
        self._entry_point_heuristics = entry_point_heuristics

    def build(self, project: Project) -> ProjectGraph:
        """Build and return a ProjectGraph for ``project``.

        Raises:
            ProjectError: If the project has no parseable .m, .slx, or .mat files.
        """
        if not project.m_files and not project.slx_models and not project.mat_files:
            raise ProjectError(f"empty project: project_id={project.id!r} has no parseable files")

        diag = _BuildDiagnostics()
        nodes = self._build_nodes(project, diag)
        edges = self._build_edges(project, nodes, diag)
        entry_points = infer_entry_points(project, nodes, edges)
        execution_flow = topological_sort(nodes, edges, entry_points, diag)

        return ProjectGraph(
            project_id=project.id,
            nodes=nodes,
            edges=edges,
            entry_points=entry_points,
            execution_flow=execution_flow,
            data_flow=[],
            control_flow=[],
            unresolved_symbols=diag.collect(),
        )

    def _build_nodes(self, project: Project, diag: _BuildDiagnostics) -> list[ProjectNode]:
        """Build all ProjectGraph nodes in deterministic type order."""
        nodes: list[ProjectNode] = []
        nodes.extend(build_file_m_nodes(project.m_files))
        nodes.extend(build_function_nodes(project.m_files))
        nodes.extend(build_file_slx_nodes(project.slx_models, diag))
        nodes.extend(
            build_block_and_subsystem_nodes(
                project.slx_models,
                diag,
                expand_subsystems=self._expand_subsystems,
                include_block_parameters=self._include_block_parameters,
            )
        )
        nodes.extend(build_file_mat_nodes(project.mat_files))
        return nodes

    def _build_edges(
        self,
        project: Project,
        nodes: list[ProjectNode],
        diag: _BuildDiagnostics,
    ) -> list[ProjectEdge]:
        """Build all ProjectGraph edges and deduplicate them."""
        node_index: dict[str, ProjectNode] = {node.id: node for node in nodes}
        edges: list[ProjectEdge] = []
        edges.extend(build_calls_edges(project.file_dependencies, node_index, diag))
        edges.extend(build_loads_data_edges(project.file_dependencies, node_index, diag))
        edges.extend(build_signal_flows_edges(project.slx_models, node_index, diag))
        edges.extend(build_belongs_to_edges(project.slx_models, project.m_files, node_index, diag))
        return _dedup_and_sort_edges(edges)


def _dedup_and_sort_edges(edges: list[ProjectEdge]) -> list[ProjectEdge]:
    seen: set[tuple[str, str, str]] = set()
    result: list[ProjectEdge] = []
    for edge in sorted(edges, key=lambda item: (item.from_node, item.to_node, item.type.value)):
        key = (edge.from_node, edge.to_node, edge.type.value)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result
