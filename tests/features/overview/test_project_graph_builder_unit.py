import pytest

from core.domain.exceptions import ProjectError
from core.domain.project_graph import EdgeType, NodeType
from features.overview import ProjectGraphBuilder
from features.overview._node_id import (
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_function_id,
)


def test_project_graph_builder_builds_expected_graph(
    make_project,
    make_m_file,
    make_m_function,
    make_slx_model,
    make_slx_block,
    make_slx_line,
    make_mat_metadata,
) -> None:
    project = make_project(
        id="proj-42",
        name="Demo",
        m_files=[
            make_m_file(
                "run_demo.m",
                file_role="script",
                functions=[make_m_function("run_demo")],
            ),
            make_m_file("helper.m", functions=[make_m_function("helper")]),
        ],
        slx_models=[
            make_slx_model(
                "model.slx",
                blocks=[make_slx_block("1"), make_slx_block("2")],
                lines=[make_slx_line("1", to_block="2")],
            )
        ],
        mat_files=[make_mat_metadata("data/params.mat")],
        file_dependencies={"run_demo.m": ["helper.m", "model.slx", "data/params.mat"]},
    )

    graph = ProjectGraphBuilder().build(project)
    node_ids = {node.id for node in graph.nodes}
    edge_keys = {(edge.from_node, edge.to_node, edge.type) for edge in graph.edges}

    assert graph.project_id == "proj-42"
    assert make_file_m_id("run_demo.m") in node_ids
    assert make_function_id("run_demo.m", "run_demo") in node_ids
    assert make_block_id("model.slx", "1") in node_ids
    assert make_file_mat_id("data/params.mat") in node_ids
    assert {node.type for node in graph.nodes} >= {
        NodeType.FILE_M,
        NodeType.FUNCTION,
        NodeType.FILE_SLX,
        NodeType.BLOCK,
        NodeType.FILE_MAT,
    }
    assert (
        make_file_m_id("run_demo.m"),
        make_file_m_id("helper.m"),
        EdgeType.CALLS,
    ) in edge_keys
    assert (
        make_file_m_id("run_demo.m"),
        make_file_mat_id("data/params.mat"),
        EdgeType.LOADS_DATA,
    ) in edge_keys
    assert make_file_m_id("run_demo.m") in graph.entry_points
    assert graph.execution_flow
    assert graph.unresolved_symbols == []


def test_project_graph_builder_leaves_data_and_control_flow_empty(
    make_project, make_m_file
) -> None:
    project = make_project(m_files=[make_m_file("main.m", file_role="script")])

    graph = ProjectGraphBuilder().build(project)

    assert graph.data_flow == []
    assert graph.control_flow == []


def test_project_graph_builder_empty_project_raises_project_error(make_project) -> None:
    project = make_project(m_files=[], slx_models=[], mat_files=[])

    with pytest.raises(ProjectError, match="empty project"):
        ProjectGraphBuilder().build(project)


def test_project_graph_builder_expand_subsystems_false_skips_nested_blocks(
    make_project,
    make_slx_model,
    make_slx_block,
) -> None:
    project = make_project(
        slx_models=[
            make_slx_model(
                "model.slx",
                blocks=[
                    make_slx_block("1", name="Top"),
                    make_slx_block("2", name="Nested", parent_subsystem="Sub"),
                ],
            )
        ]
    )

    graph = ProjectGraphBuilder(expand_subsystems=False).build(project)

    assert make_block_id("model.slx", "1") in {node.id for node in graph.nodes}
    assert make_block_id("model.slx", "2") not in {node.id for node in graph.nodes}


def test_project_graph_builder_rejects_invalid_parameter_policy() -> None:
    with pytest.raises(ValueError):
        ProjectGraphBuilder(include_block_parameters="bad")  # type: ignore[arg-type]
