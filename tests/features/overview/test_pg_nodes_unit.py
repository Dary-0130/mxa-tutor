from core.domain.project_graph import NodeType
from features.overview._node_id import (
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_file_slx_id,
    make_function_id,
    make_subsystem_id,
)
from features.overview._pg_diagnostics import _BuildDiagnostics
from features.overview._pg_nodes import (
    build_block_and_subsystem_nodes,
    build_file_m_nodes,
    build_file_mat_nodes,
    build_file_slx_nodes,
    build_function_nodes,
)


def test_single_file_single_function_builds_file_and_function(make_m_file, make_m_function) -> None:
    m_file = make_m_file(
        "src/main.m",
        file_role="script",
        functions=[make_m_function("main", inputs=["u"], outputs=["y"], line_range=(3, 8))],
        imports=["pkg.Class"],
        uses_toolbox=["Control System Toolbox"],
    )

    file_nodes = build_file_m_nodes([m_file])
    function_nodes = build_function_nodes([m_file])

    assert file_nodes[0].id == make_file_m_id("src/main.m")
    assert file_nodes[0].type == NodeType.FILE_M
    assert file_nodes[0].metadata == {
        "file:role": "script",
        "file:imports": "pkg.Class",
        "file:uses_toolbox": "Control System Toolbox",
    }
    assert function_nodes[0].id == make_function_id("src/main.m", "main")
    assert function_nodes[0].metadata["fn:line_range"] == "3-8"


def test_multiple_files_and_functions_are_deterministic(make_m_file, make_m_function) -> None:
    m_files = [
        make_m_file("b.m", functions=[make_m_function("b2"), make_m_function("b1")]),
        make_m_file("a.m", functions=[make_m_function("a")]),
    ]

    file_ids = [node.id for node in build_file_m_nodes(m_files)]
    function_ids = [node.id for node in build_function_nodes(m_files)]

    assert file_ids == [make_file_m_id("a.m"), make_file_m_id("b.m")]
    assert function_ids == [
        make_function_id("a.m", "a"),
        make_function_id("b.m", "b1"),
        make_function_id("b.m", "b2"),
    ]


def test_slx_and_mat_file_nodes(make_slx_model, make_mat_metadata) -> None:
    diag = _BuildDiagnostics()
    slx = make_slx_model(
        "models/main.slx",
        name="main_model",
        solver_config={"StopTime": "10", "Solver": "ode45"},
    )
    mat = make_mat_metadata("data/params.mat", file_size_bytes=42)

    slx_nodes = build_file_slx_nodes([slx], diag)
    mat_nodes = build_file_mat_nodes([mat])

    assert slx_nodes[0].id == make_file_slx_id("models/main.slx")
    assert slx_nodes[0].metadata["slx:model_name"] == "main_model"
    assert slx_nodes[0].metadata["slx:solver_StopTime"] == "10"
    assert mat_nodes[0].id == make_file_mat_id("data/params.mat")
    assert mat_nodes[0].metadata == {
        "mat:file_size_bytes": "42",
        "mat:variable_count": "0",
    }


def test_subsystem_block_is_not_duplicated_as_block(make_slx_model, make_slx_block) -> None:
    diag = _BuildDiagnostics()
    subsystem = make_slx_block("1", name="Controller", block_type="SubSystem")
    gain = make_slx_block("2", name="Gain", block_type="Gain", parent_subsystem="Controller")
    model = make_slx_model("models/main.slx", blocks=[subsystem, gain])

    nodes = build_block_and_subsystem_nodes([model], diag)

    assert make_subsystem_id("models/main.slx", "Controller") in {node.id for node in nodes}
    assert make_block_id("models/main.slx", "1") not in {node.id for node in nodes}
    assert make_block_id("models/main.slx", "2") in {node.id for node in nodes}


def test_synthetic_subsystem_node_is_created_for_unmatched_subsystem(
    make_slx_model,
    make_slx_block,
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "models/main.slx",
        blocks=[make_slx_block("2", name="Gain")],
        subsystems={"MissingSub": ["2"]},
    )

    nodes = build_block_and_subsystem_nodes([model], diag)
    synthetic = next(
        node for node in nodes if node.id == make_subsystem_id("models/main.slx", "MissingSub")
    )

    assert synthetic.type == NodeType.SUBSYSTEM
    assert synthetic.metadata["synthetic"] == "true"
    assert diag.collect() == ["partial_parse:models/main.slx"]


def test_block_metadata_uses_namespaces_and_str_values(make_slx_model, make_slx_block) -> None:
    diag = _BuildDiagnostics()
    block = make_slx_block(
        "10",
        name="Gain",
        block_type="Gain",
        parameters={"Gain": "Kp", "Numerator": "[1 2]"},
        position=(1, 2, 3, 4),
        is_masked=True,
    )
    model = make_slx_model("models/main.slx", blocks=[block])

    node = build_block_and_subsystem_nodes([model], diag)[0]

    assert node.metadata["block:type"] == "Gain"
    assert node.metadata["block:position"] == "1,2,3,4"
    assert node.metadata["block:is_masked"] == "true"
    assert node.metadata["param:Gain"] == "Kp"
    assert all(isinstance(value, str) for value in node.metadata.values())


def test_partial_parse_slx_file_records_metadata_and_diag(make_slx_model) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model("models/warn.slx", parse_warnings=["unknown block"])

    node = build_file_slx_nodes([model], diag)[0]

    assert node.metadata["partial_parse"] == "true"
    assert diag.collect() == ["partial_parse:models/warn.slx"]


def test_expand_subsystems_false_keeps_only_top_level_blocks(
    make_slx_model, make_slx_block
) -> None:
    diag = _BuildDiagnostics()
    model = make_slx_model(
        "models/main.slx",
        blocks=[
            make_slx_block("1", name="TopGain"),
            make_slx_block("2", name="NestedGain", parent_subsystem="Controller"),
        ],
    )

    nodes = build_block_and_subsystem_nodes([model], diag, expand_subsystems=False)

    assert {node.id for node in nodes} == {make_block_id("models/main.slx", "1")}
