from core.domain.project_graph import EdgeType, NodeType, ProjectEdge, ProjectNode
from core.domain.source_ref import SourceRef
from features.overview._node_id import make_file_m_id, make_file_slx_id
from features.overview._pg_diagnostics import _BuildDiagnostics
from features.overview._pg_topology import infer_entry_points, topological_sort


def _node(node_id: str, node_type: NodeType = NodeType.FILE_M) -> ProjectNode:
    return ProjectNode(
        id=node_id,
        type=node_type,
        label=node_id,
        source_ref=SourceRef(file_path=node_id),
        metadata={},
    )


def test_entry_points_filename_matches_take_priority(
    make_project,
    make_m_file,
    make_slx_model,
) -> None:
    project = make_project(
        name="Demo",
        m_files=[
            make_m_file("zzz_script.m", file_role="script"),
            make_m_file("main.m", file_role="function"),
            make_m_file("run_init.m", file_role="function"),
            make_m_file("Demo.m", file_role="function"),
        ],
        slx_models=[make_slx_model("model.slx")],
        file_dependencies={"zzz_script.m": ["model.slx"]},
    )
    nodes = [
        _node(make_file_m_id("Demo.m")),
        _node(make_file_m_id("main.m")),
        _node(make_file_m_id("run_init.m")),
        _node(make_file_m_id("zzz_script.m")),
        _node(make_file_slx_id("model.slx"), NodeType.FILE_SLX),
    ]

    entry_points = infer_entry_points(project, nodes, [])

    assert entry_points[:3] == [
        make_file_m_id("Demo.m"),
        make_file_m_id("main.m"),
        make_file_m_id("run_init.m"),
    ]
    assert make_file_m_id("zzz_script.m") in entry_points[3:]


def test_entry_points_accumulate_deduped_by_heuristic_order(make_project, make_m_file) -> None:
    project = make_project(
        m_files=[make_m_file("run_main.m", file_role="script")],
        file_dependencies={"run_main.m": ["helper.m"]},
    )
    nodes = [_node(make_file_m_id("run_main.m")), _node(make_file_m_id("helper.m"))]

    entry_points = infer_entry_points(project, nodes, [])

    assert entry_points == [make_file_m_id("run_main.m")]


def test_entry_points_dependency_root_and_slx_fallback(
    make_project,
    make_m_file,
    make_slx_model,
) -> None:
    project = make_project(
        m_files=[make_m_file("driver.m", file_role="function"), make_m_file("helper.m")],
        slx_models=[make_slx_model("plant.slx")],
        file_dependencies={"driver.m": ["helper.m"]},
    )
    nodes = [
        _node(make_file_m_id("driver.m")),
        _node(make_file_m_id("helper.m")),
        _node(make_file_slx_id("plant.slx"), NodeType.FILE_SLX),
    ]

    assert infer_entry_points(project, nodes, []) == [
        make_file_m_id("driver.m"),
        make_file_slx_id("plant.slx"),
    ]


def test_execution_flow_ignores_signal_flow_cycles() -> None:
    diag = _BuildDiagnostics()
    nodes = [_node("block:a", NodeType.BLOCK), _node("block:b", NodeType.BLOCK)]
    edges = [
        ProjectEdge("block:a", "block:b", EdgeType.SIGNAL_FLOWS),
        ProjectEdge("block:b", "block:a", EdgeType.SIGNAL_FLOWS),
    ]

    flow = topological_sort(nodes, edges, [], diag)

    assert set(flow) == {"block:a", "block:b"}
    assert not any(item.startswith("circular:") for item in diag.collect())


def test_dfs_reverse_postorder_keeps_caller_before_callee() -> None:
    diag = _BuildDiagnostics()
    nodes = [_node(make_file_m_id(name)) for name in ["a.m", "b.m", "c.m"]]
    edges = [
        ProjectEdge(make_file_m_id("a.m"), make_file_m_id("b.m"), EdgeType.CALLS),
        ProjectEdge(make_file_m_id("b.m"), make_file_m_id("c.m"), EdgeType.CALLS),
    ]

    flow = topological_sort(nodes, edges, [make_file_m_id("a.m")], diag)

    assert flow == [make_file_m_id("a.m"), make_file_m_id("b.m"), make_file_m_id("c.m")]


def test_cycle_back_edge_is_recorded_and_skipped() -> None:
    diag = _BuildDiagnostics()
    a = make_file_m_id("a.m")
    b = make_file_m_id("b.m")
    nodes = [_node(a), _node(b)]
    edges = [ProjectEdge(a, b, EdgeType.CALLS), ProjectEdge(b, a, EdgeType.CALLS)]

    flow = topological_sort(nodes, edges, [a], diag)

    assert flow == [a, b]
    assert diag.collect() == [f"circular:{b}<->{a}"]


def test_unvisited_nodes_are_included_with_deterministic_order() -> None:
    diag = _BuildDiagnostics()
    a = make_file_m_id("a.m")
    b = make_file_m_id("b.m")
    c = make_file_m_id("c.m")
    nodes = [_node(a), _node(b), _node(c)]
    edges = [ProjectEdge(a, b, EdgeType.CALLS)]

    flow = topological_sort(nodes, edges, [a], diag)

    assert flow == [c, a, b]


def test_topological_sort_handles_more_than_50_nodes() -> None:
    diag = _BuildDiagnostics()
    ids = [make_file_m_id(f"node_{index:02d}.m") for index in range(60)]
    nodes = [_node(node_id) for node_id in ids]
    edges = [
        ProjectEdge(ids[index], ids[index + 1], EdgeType.CALLS) for index in range(len(ids) - 1)
    ]

    flow = topological_sort(nodes, edges, [ids[0]], diag)

    assert flow == ids
    assert diag.collect() == []
