from core.domain.project_graph import EdgeType, ProjectEdge
from features.overview._node_id import (
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_file_slx_id,
    make_function_id,
    make_subsystem_id,
)
from features.overview._pg_diagnostics import _BuildDiagnostics
from features.overview._pg_edges import (
    build_belongs_to_edges,
    build_calls_edges,
    build_loads_data_edges,
    build_signal_flows_edges,
)
from features.overview._pg_nodes import (
    build_block_and_subsystem_nodes,
    build_file_m_nodes,
    build_file_mat_nodes,
    build_file_slx_nodes,
    build_function_nodes,
)


def _node_index(nodes):
    return {node.id: node for node in nodes}


def test_calls_edges_file_level_m_to_m_and_m_to_slx(
    make_m_file,
    make_slx_model,
) -> None:
    diag = _BuildDiagnostics()
    m_files = [make_m_file("run.m"), make_m_file("helper.m")]
    slx_models = [make_slx_model("model.slx")]
    nodes = build_file_m_nodes(m_files) + build_file_slx_nodes(slx_models, diag)

    edges = build_calls_edges(
        {"run.m": ["helper.m", "model.slx"]},
        _node_index(nodes),
        diag,
    )

    assert edges == [
        ProjectEdge(make_file_m_id("run.m"), make_file_m_id("helper.m"), EdgeType.CALLS),
        ProjectEdge(make_file_m_id("run.m"), make_file_slx_id("model.slx"), EdgeType.CALLS),
    ]


def test_loads_data_edges_direction_loader_to_mat(make_m_file, make_mat_metadata) -> None:
    diag = _BuildDiagnostics()
    nodes = build_file_m_nodes([make_m_file("load_params.m")])
    nodes += build_file_mat_nodes([make_mat_metadata("data/params.mat")])

    edges = build_loads_data_edges(
        {"load_params.m": ["data/params.mat"]},
        _node_index(nodes),
        diag,
    )

    assert edges == [
        ProjectEdge(
            make_file_m_id("load_params.m"),
            make_file_mat_id("data/params.mat"),
            EdgeType.LOADS_DATA,
        )
    ]


def test_signal_flows_edges_direction_source_to_target(
    make_slx_model,
    make_slx_block,
    make_slx_line,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "model.slx",
        blocks=[make_slx_block("1", name="Source"), make_slx_block("2", name="Gain")],
        lines=[make_slx_line("1", to_block="2")],
    )
    nodes = build_block_and_subsystem_nodes([model], diag)

    edges = build_signal_flows_edges([model], _node_index(nodes), diag)

    assert edges == [
        ProjectEdge(
            make_block_id("model.slx", "1"),
            make_block_id("model.slx", "2"),
            EdgeType.SIGNAL_FLOWS,
        )
    ]


def test_signal_flows_resolves_subsystem_block_id_to_subsystem_node(
    make_slx_model,
    make_slx_block,
    make_slx_line,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "model.slx",
        blocks=[
            make_slx_block("1", name="Controller", block_type="SubSystem"),
            make_slx_block("2", name="Gain"),
        ],
        lines=[make_slx_line("1", to_block="2")],
    )
    nodes = build_block_and_subsystem_nodes([model], diag)

    edges = build_signal_flows_edges([model], _node_index(nodes), diag)

    assert edges == [
        ProjectEdge(
            make_subsystem_id("model.slx", "Controller"),
            make_block_id("model.slx", "2"),
            EdgeType.SIGNAL_FLOWS,
        )
    ]


def test_belongs_to_edges_for_functions_blocks_subsystems_and_files(
    make_m_file,
    make_m_function,
    make_slx_model,
    make_slx_block,
) -> None:
    diag = _BuildDiagnostics()
    m_file = make_m_file("main.m", functions=[make_m_function("main")])
    model = make_slx_model(
        "model.slx",
        blocks=[
            make_slx_block("1", name="Controller", block_type="SubSystem"),
            make_slx_block("2", name="Gain", parent_subsystem="Controller"),
        ],
        subsystems={"Controller": ["2"]},
    )
    nodes = (
        build_file_m_nodes([m_file])
        + build_function_nodes([m_file])
        + build_file_slx_nodes([model], diag)
        + build_block_and_subsystem_nodes([model], diag)
    )

    edges = build_belongs_to_edges([model], [m_file], _node_index(nodes), diag)

    assert (
        ProjectEdge(
            make_function_id("main.m", "main"),
            make_file_m_id("main.m"),
            EdgeType.BELONGS_TO,
        )
        in edges
    )
    assert (
        ProjectEdge(
            make_block_id("model.slx", "2"),
            make_subsystem_id("model.slx", "Controller"),
            EdgeType.BELONGS_TO,
        )
        in edges
    )
    assert (
        ProjectEdge(
            make_subsystem_id("model.slx", "Controller"),
            make_file_slx_id("model.slx"),
            EdgeType.BELONGS_TO,
        )
        in edges
    )


def test_synthetic_subsystem_belongs_to_file(
    make_slx_model,
    make_slx_block,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "model.slx",
        blocks=[make_slx_block("2", name="Gain")],
        subsystems={"Synthetic": ["2"]},
    )
    nodes = build_file_slx_nodes([model], diag) + build_block_and_subsystem_nodes([model], diag)

    edges = build_belongs_to_edges([model], [], _node_index(nodes), diag)

    assert (
        ProjectEdge(
            make_subsystem_id("model.slx", "Synthetic"),
            make_file_slx_id("model.slx"),
            EdgeType.BELONGS_TO,
        )
        in edges
    )


def test_dangling_slx_line_is_skipped_and_recorded(
    make_slx_model,
    make_slx_block,
    make_slx_line,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "model.slx",
        blocks=[make_slx_block("1", name="Source")],
        lines=[make_slx_line("1", to_block="missing")],
    )
    nodes = build_block_and_subsystem_nodes([model], diag)

    assert build_signal_flows_edges([model], _node_index(nodes), diag) == []
    assert "unresolved:line<1→missing>" in diag.collect()


def test_dangling_parent_subsystem_is_skipped_and_recorded(
    make_slx_model,
    make_slx_block,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "model.slx",
        blocks=[make_slx_block("2", name="Gain", parent_subsystem="Missing")],
        subsystems={},
    )
    nodes = build_file_slx_nodes([model], diag) + build_block_and_subsystem_nodes([model], diag)

    edges = build_belongs_to_edges([model], [], _node_index(nodes), diag)

    assert (
        ProjectEdge(
            make_block_id("model.slx", "2"),
            make_file_slx_id("model.slx"),
            EdgeType.BELONGS_TO,
        )
        not in edges
    )
    assert "unresolved:subsystem<Missing>" in diag.collect()


def test_edges_are_deduplicated_and_sorted(make_m_file) -> None:
    diag = _BuildDiagnostics()
    nodes = build_file_m_nodes([make_m_file("a.m"), make_m_file("b.m"), make_m_file("c.m")])

    edges = build_calls_edges(
        {"c.m": ["b.m", "a.m", "b.m"]},
        _node_index(nodes),
        diag,
    )

    assert edges == [
        ProjectEdge(make_file_m_id("c.m"), make_file_m_id("a.m"), EdgeType.CALLS),
        ProjectEdge(make_file_m_id("c.m"), make_file_m_id("b.m"), EdgeType.CALLS),
    ]
