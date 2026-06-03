import pytest

from core.domain.project_graph import NodeType
from features.overview._node_id import (
    ParsedNodeId,
    make_block_id,
    make_file_m_id,
    make_file_mat_id,
    make_file_slx_id,
    make_function_id,
    make_subsystem_id,
    parse_node_id,
)


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        (
            make_file_m_id("src/main.m"),
            ParsedNodeId(NodeType.FILE_M, "src/main.m"),
        ),
        (
            make_function_id("src/utils/helper.m", "compute"),
            ParsedNodeId(NodeType.FUNCTION, "src/utils/helper.m", "fn", "compute"),
        ),
        (
            make_file_slx_id("models/main.slx"),
            ParsedNodeId(NodeType.FILE_SLX, "models/main.slx"),
        ),
        (
            make_block_id("models/main.slx", "GUID-abc_123"),
            ParsedNodeId(NodeType.BLOCK, "models/main.slx", "block", "GUID-abc_123"),
        ),
        (
            make_subsystem_id("models/main.slx", "Controller"),
            ParsedNodeId(NodeType.SUBSYSTEM, "models/main.slx", "sub", "Controller"),
        ),
        (
            make_file_mat_id("data/params.mat"),
            ParsedNodeId(NodeType.FILE_MAT, "data/params.mat"),
        ),
    ],
)
def test_node_id_round_trip_all_node_types(node_id: str, expected: ParsedNodeId) -> None:
    assert parse_node_id(node_id) == expected


def test_node_id_round_trip_keeps_chinese_and_spaces() -> None:
    node_id = make_function_id("src/数据 处理/main file.m", "计算函数")

    parsed = parse_node_id(node_id)

    assert parsed.node_type == NodeType.FUNCTION
    assert parsed.relpath == "src/数据 处理/main file.m"
    assert parsed.inner_value == "计算函数"


def test_node_id_round_trip_keeps_special_characters() -> None:
    relpath = "src/my-file_v2.1(test)/Foo.m"
    node_id = make_block_id(relpath, "Gain-1_(A)")

    parsed = parse_node_id(node_id)

    assert parsed.relpath == relpath
    assert parsed.inner_value == "Gain-1_(A)"


def test_same_path_with_different_block_ids_stays_distinct() -> None:
    first = make_block_id("model/main.slx", "1")
    second = make_block_id("model/main.slx", "2")

    assert first != second
    assert parse_node_id(first).inner_value == "1"
    assert parse_node_id(second).inner_value == "2"


def test_node_id_preserves_case() -> None:
    upper = make_file_m_id("src/Foo.m")
    lower = make_file_m_id("src/foo.m")

    assert upper != lower
    assert parse_node_id(upper).relpath == "src/Foo.m"
    assert parse_node_id(lower).relpath == "src/foo.m"


@pytest.mark.parametrize("bad_node_id", ["missing-prefix", "x:foo", "m:foo.m::fn:"])
def test_parse_node_id_rejects_invalid_shapes(bad_node_id: str) -> None:
    with pytest.raises(ValueError):
        parse_node_id(bad_node_id)
