import zipfile
from pathlib import Path

from adapters.parser.slx_parser import SlxParserImpl


def test_parse_minimal_block(tmp_path: Path) -> None:
    slx_path = _make_slx(
        tmp_path,
        {
            "simulink/blockdiagram.xml": _blockdiagram_xml(),
            "simulink/systems/system_root.xml": """
                <System>
                  <Block BlockType="Gain" Name="Kp" SID="3">
                    <P Name="Position">[100, 100, 130, 130]</P>
                    <P Name="Gain">Kp_speed</P>
                  </Block>
                </System>
            """,
        },
    )

    model = SlxParserImpl().parse(str(slx_path))

    assert model.name == "minimal"
    assert len(model.blocks) == 1
    assert model.blocks[0].block_id == "3"
    assert model.blocks[0].block_type == "Gain"
    assert model.blocks[0].parameters["Gain"] == "Kp_speed"
    assert model.blocks[0].position == (100, 100, 130, 130)


def test_parse_line_and_branch_ports(tmp_path: Path) -> None:
    slx_path = _make_slx(
        tmp_path,
        {
            "simulink/blockdiagram.xml": _blockdiagram_xml(),
            "simulink/systems/system_root.xml": """
                <System>
                  <Block BlockType="Inport" Name="In" SID="1">
                    <P Name="Position">[10, 10, 30, 30]</P>
                  </Block>
                  <Block BlockType="Gain" Name="Gain" SID="2">
                    <P Name="Position">[50, 10, 80, 30]</P>
                  </Block>
                  <Block BlockType="Outport" Name="Out" SID="3">
                    <P Name="Position">[100, 10, 130, 30]</P>
                  </Block>
                  <Line>
                    <P Name="Src">1#out:1</P>
                    <Branch><P Name="Dst">2#in:1</P></Branch>
                    <Branch><P Name="Dst">3#in:1</P></Branch>
                  </Line>
                </System>
            """,
        },
    )

    model = SlxParserImpl().parse(str(slx_path))

    assert {
        (line.from_block, line.from_port, line.to_block, line.to_port) for line in model.lines
    } == {
        ("1", 1, "2", 1),
        ("1", 1, "3", 1),
    }


def test_parse_nested_subsystem(tmp_path: Path) -> None:
    slx_path = _make_slx(
        tmp_path,
        {
            "simulink/blockdiagram.xml": _blockdiagram_xml(),
            "simulink/systems/system_root.xml": """
                <System>
                  <Block BlockType="SubSystem" Name="Controller" SID="10">
                    <P Name="Position">[10, 10, 60, 40]</P>
                    <System Ref="system_10"/>
                  </Block>
                </System>
            """,
            "simulink/systems/system_10.xml": """
                <System>
                  <Block BlockType="Sum" Name="Sum" SID="11">
                    <P Name="Position">[20, 20, 40, 40]</P>
                  </Block>
                </System>
            """,
        },
    )

    model = SlxParserImpl().parse(str(slx_path))

    assert model.subsystems["Controller"] == ["11"]
    assert model.blocks[1].parent_subsystem == "Controller"


def test_bad_block_isolated_with_warning(tmp_path: Path) -> None:
    slx_path = _make_slx(
        tmp_path,
        {
            "simulink/blockdiagram.xml": _blockdiagram_xml(),
            "simulink/systems/system_root.xml": """
                <System>
                  <Block BlockType="Gain" Name="Good" SID="2">
                    <P Name="Position">[1, 2, 3, 4]</P>
                  </Block>
                  <Block BlockType="Gain" Name="Bad">
                    <P Name="Position">[1, 2, 3, 4]</P>
                  </Block>
                </System>
            """,
        },
    )

    model = SlxParserImpl().parse(str(slx_path))

    assert [block.name for block in model.blocks] == ["Good"]
    assert any("block 解析失败" in warning for warning in model.parse_warnings)


def test_solver_config_from_config_set(tmp_path: Path) -> None:
    slx_path = _make_slx(
        tmp_path,
        {
            "simulink/blockdiagram.xml": _blockdiagram_xml(),
            "simulink/systems/system_root.xml": "<System/>",
            "simulink/configSet0.xml": """
                <ConfigSet>
                  <Object ClassName="Simulink.SolverCC">
                    <P Name="StartTime">0</P>
                    <P Name="StopTime">10</P>
                    <P Name="SolverName">ode45</P>
                    <P Name="FixedStep">auto</P>
                  </Object>
                </ConfigSet>
            """,
        },
    )

    model = SlxParserImpl().parse(str(slx_path))

    assert model.solver_config == {
        "StartTime": "0",
        "StopTime": "10",
        "Solver": "ode45",
        "FixedStep": "auto",
    }


def _blockdiagram_xml() -> str:
    return """
        <ModelInformation>
          <Model Name="minimal">
            <System Ref="system_root"/>
          </Model>
        </ModelInformation>
    """


def _make_slx(tmp_path: Path, files: dict[str, str]) -> Path:
    slx_path = tmp_path / "model.slx"
    with zipfile.ZipFile(slx_path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        for inner_path, content in files.items():
            zf.writestr(inner_path, content.strip())
    return slx_path
