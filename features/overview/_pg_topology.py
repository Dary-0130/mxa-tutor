"""Entry-point inference and execution-flow topology helpers."""

from __future__ import annotations

from pathlib import PurePosixPath

from core.domain.project import Project
from core.domain.project_graph import EdgeType, ProjectEdge, ProjectNode

from ._node_id import make_file_m_id, make_file_slx_id
from ._pg_diagnostics import _BuildDiagnostics

__all__ = ["infer_entry_points", "topological_sort"]


def infer_entry_points(
    project: Project,
    nodes: list[ProjectNode],
    edges: list[ProjectEdge],
) -> list[str]:
    """Infer project entry-point node IDs using H2 -> H1 -> H3 -> H4."""
    del edges
    node_ids = {node.id for node in nodes}
    result: list[str] = []
    seen: set[str] = set()

    for node_id in _h2_filename_matches(project):
        _append_existing(node_id, node_ids, result, seen)
    for node_id in _h1_script_files(project):
        _append_existing(node_id, node_ids, result, seen)
    for node_id in _h3_dependency_roots(project):
        _append_existing(node_id, node_ids, result, seen)
    for node_id in _h4_slx_files(project):
        _append_existing(node_id, node_ids, result, seen)

    return result


def topological_sort(
    nodes: list[ProjectNode],
    edges: list[ProjectEdge],
    entry_points: list[str],
    diag: _BuildDiagnostics,
) -> list[str]:
    """Return DFS reverse postorder using only CALLS and LOADS_DATA edges."""
    relevant_edges = [edge for edge in edges if edge.type in {EdgeType.CALLS, EdgeType.LOADS_DATA}]
    adj: dict[str, list[str]] = {}
    for edge in relevant_edges:
        adj.setdefault(edge.from_node, []).append(edge.to_node)
    for key, values in adj.items():
        adj[key] = sorted(set(values))

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {node.id: white for node in nodes}
    post_order: list[str] = []

    def dfs(node_id: str) -> None:
        color[node_id] = gray
        for target_id in adj.get(node_id, []):
            if target_id not in color:
                diag.add("unresolved", f"edge_target:{target_id}")
                continue
            if color[target_id] == white:
                dfs(target_id)
            elif color[target_id] == gray:
                diag.add("circular", f"{node_id}<->{target_id}")
        color[node_id] = black
        post_order.append(node_id)

    for entry_point in entry_points:
        if entry_point in color and color[entry_point] == white:
            dfs(entry_point)

    for node in sorted(nodes, key=lambda item: item.id):
        if color[node.id] == white:
            dfs(node.id)

    return list(reversed(post_order))


def _h2_filename_matches(project: Project) -> list[str]:
    project_name_lower = project.name.lower()
    result: list[str] = []
    for m_file in sorted(project.m_files, key=lambda item: _normalize_relpath(item.file_path)):
        relpath = _normalize_relpath(m_file.file_path)
        basename = PurePosixPath(relpath).name
        basename_lower = basename.lower()
        if (
            basename_lower == "main.m"
            or basename_lower.startswith("run_")
            or basename_lower.startswith("start_")
            or basename_lower == f"{project_name_lower}.m"
        ):
            result.append(make_file_m_id(relpath))
    return result


def _h1_script_files(project: Project) -> list[str]:
    return [
        make_file_m_id(_normalize_relpath(m_file.file_path))
        for m_file in sorted(project.m_files, key=lambda item: _normalize_relpath(item.file_path))
        if m_file.file_role == "script"
    ]


def _h3_dependency_roots(project: Project) -> list[str]:
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for source, targets in project.file_dependencies.items():
        source_relpath = _normalize_relpath(source)
        out_degree[source_relpath] = len(targets)
        for target in targets:
            target_relpath = _normalize_relpath(target)
            in_degree[target_relpath] = in_degree.get(target_relpath, 0) + 1

    result: list[str] = []
    for source in sorted(out_degree):
        if in_degree.get(source, 0) != 0 or out_degree[source] < 1:
            continue
        node_id = _file_node_id(source)
        if node_id is not None:
            result.append(node_id)
    return result


def _h4_slx_files(project: Project) -> list[str]:
    return [
        make_file_slx_id(_normalize_relpath(model.file_path))
        for model in sorted(project.slx_models, key=lambda item: _normalize_relpath(item.file_path))
    ]


def _append_existing(
    node_id: str,
    node_ids: set[str],
    result: list[str],
    seen: set[str],
) -> None:
    if node_id in node_ids and node_id not in seen:
        result.append(node_id)
        seen.add(node_id)


def _file_node_id(relpath: str) -> str | None:
    ext = PurePosixPath(relpath).suffix.lower()
    if ext == ".m":
        return make_file_m_id(relpath)
    if ext == ".slx":
        return make_file_slx_id(relpath)
    return None


def _normalize_relpath(path: str) -> str:
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    return normalized.lstrip("./").rstrip("/")
