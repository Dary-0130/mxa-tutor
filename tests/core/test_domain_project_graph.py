from core.domain.project_graph import EdgeType, NodeType, ProjectEdge, ProjectGraph, ProjectNode
from core.domain.source_ref import SourceRef


def test_node_type_values_match_contract() -> None:
    assert {item.name: item.value for item in NodeType} == {
        "FILE_M": "file_m",
        "FILE_SLX": "file_slx",
        "FILE_MAT": "file_mat",
        "BLOCK": "block",
        "SUBSYSTEM": "subsystem",
        "FUNCTION": "function",
        "PARAMETER": "parameter",
    }


def test_edge_type_values_match_contract() -> None:
    assert {item.name: item.value for item in EdgeType} == {
        "CALLS": "calls",
        "SIGNAL_FLOWS": "signal_flows",
        "BELONGS_TO": "belongs_to",
        "READS_PARAM": "reads_param",
        "LOADS_DATA": "loads_data",
    }


def test_project_graph_required_fields() -> None:
    source_ref = SourceRef(file_path="model.slx", block_id="b1")
    node = ProjectNode(
        id="node-1",
        type=NodeType.BLOCK,
        label="Gain",
        source_ref=source_ref,
        metadata={"block_type": "Gain"},
    )
    edge = ProjectEdge(from_node="node-1", to_node="node-2", type=EdgeType.SIGNAL_FLOWS)
    graph = ProjectGraph(
        project_id="project-1",
        nodes=[node],
        edges=[edge],
        entry_points=["node-1"],
        execution_flow=["node-1", "node-2"],
        data_flow=["node-1"],
        control_flow=["node-2"],
        unresolved_symbols=["unknown_gain"],
    )

    assert graph.project_id == "project-1"
    assert graph.nodes == [node]
    assert graph.edges == [edge]
    assert graph.entry_points == ["node-1"]
    assert graph.execution_flow == ["node-1", "node-2"]
    assert graph.data_flow == ["node-1"]
    assert graph.control_flow == ["node-2"]
    assert graph.unresolved_symbols == ["unknown_gain"]
