from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


def test_slx_block_required_fields_and_defaults() -> None:
    block = SlxBlock(
        block_id="b1",
        name="Gain",
        block_type="Gain",
        parameters={"Gain": "2"},
        position=(0, 0, 20, 20),
        parent_subsystem=None,
    )

    assert block.block_id == "b1"
    assert block.parameters == {"Gain": "2"}
    assert block.position == (0, 0, 20, 20)
    assert block.parent_subsystem is None
    assert block.is_masked is False
    assert block.is_library_link is False
    assert block.is_model_reference is False


def test_slx_line_required_fields() -> None:
    line = SlxLine(from_block="b1", from_port=1, to_block="b2", to_port=1)

    assert line.from_block == "b1"
    assert line.from_port == 1
    assert line.to_block == "b2"
    assert line.to_port == 1


def test_slx_model_required_fields() -> None:
    block = SlxBlock(
        block_id="b1",
        name="Gain",
        block_type="Gain",
        parameters={},
        position=(0, 0, 20, 20),
        parent_subsystem="Control",
    )
    line = SlxLine(from_block="b1", from_port=1, to_block="b2", to_port=1)
    model = SlxModel(
        file_path="model.slx",
        name="model",
        blocks=[block],
        lines=[line],
        subsystems={"Control": ["b1"]},
        solver_config={"Solver": "ode45"},
        parse_warnings=["ignored unsupported element"],
    )

    assert model.file_path == "model.slx"
    assert model.blocks == [block]
    assert model.lines == [line]
    assert model.subsystems == {"Control": ["b1"]}
    assert model.solver_config == {"Solver": "ode45"}
    assert model.parse_warnings == ["ignored unsupported element"]
