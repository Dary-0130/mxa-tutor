from __future__ import annotations

from datetime import datetime

from app.config import AppSettings
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxModel
from features.chunking import _project_chunker
from features.chunking._source_text_templates import build_slx_block_source_text


def _settings(monkeypatch) -> AppSettings:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    return AppSettings()


def _block(
    block_id: str,
    name: str,
    block_type: str,
    parameters: dict[str, str],
    parent_subsystem: str | None = None,
) -> SlxBlock:
    return SlxBlock(
        block_id=block_id,
        name=name,
        block_type=block_type,
        parameters=parameters,
        position=(0, 0, 20, 20),
        parent_subsystem=parent_subsystem,
    )


def _model(file_path: str, blocks: list[SlxBlock]) -> SlxModel:
    return SlxModel(
        file_path=file_path,
        name=file_path.removesuffix(".slx"),
        blocks=blocks,
        lines=[],
        subsystems={},
        solver_config={},
        parse_warnings=[],
    )


def _project(
    *,
    slx_models: list[SlxModel] | None = None,
    m_files: list[MFile] | None = None,
    files: list[FileInfo] | None = None,
) -> Project:
    return Project(
        id="chunk-quality",
        name="quality.zip",
        project_type=ProjectType.POWER_ELECTRONICS,
        files=files or [FileInfo("model.slx", ".slx", 10), FileInfo("main.m", ".m", 10)],
        slx_models=slx_models or [],
        m_files=m_files or [],
        mat_files=[],
        created_at=datetime(2026, 6, 9, 0, 0, 0),
        file_dependencies={},
    )


def _slx_drafts(project: Project, settings: AppSettings):
    return _project_chunker._build_slx_block_drafts(project, settings)


def _m_file_drafts(project: Project, settings: AppSettings):
    return [
        draft
        for draft in _project_chunker.build_drafts(project, graph=None, settings=settings)
        if draft.source_type == "m_file"
    ]


def test_dab_control_like_noise_blocks_are_filtered_and_duplicates_merge(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    blocks = [
        *[
            _block(
                f"mosfet-{index}",
                f"Mosfet{index}",
                "Mosfet",
                {"Ron": "0.01", "Position": "[0,0,20,20]", "SourceType": "Mosfet"},
            )
            for index in range(1, 9)
        ],
        *[
            _block(
                f"from-{index}",
                f"From{index}",
                "From",
                {"GotoTag": "PWM1", "Position": "[0,0,20,20]"},
            )
            for index in range(1, 11)
        ],
        *[
            _block(
                f"scope-{index}",
                f"Scope{index}",
                "Scope",
                {"Position": "[0,0,20,20]"},
            )
            for index in range(1, 6)
        ],
        _block("goto-1", "Goto", "Goto", {"GotoTag": "PWM1"}),
        _block("clock-1", "Clock", "Clock", {"DisplayTime": "on"}),
        _block("dc-1", "DC Voltage Source", "DC Voltage Source", {"Amplitude": "U1"}),
        _block("vref-1", "Vref", "Constant", {"Value": "80"}),
        _block("sfcn-1", "S-Function", "S-Function", {"FunctionName": "DAB_Sfcn"}),
        _block("rlc-1", "Series RLC Branch1", "Series RLC Branch", {"Resistance": "1"}),
        _block("rlc-2", "Series RLC Branch2", "Series RLC Branch", {"Resistance": "2"}),
        _block("rlc-3", "Series RLC Branch3", "Series RLC Branch", {"Resistance": "3"}),
    ]

    drafts = _slx_drafts(_project(slx_models=[_model("DAB_Control.slx", blocks)]), settings)
    by_name = {draft.symbol_name: draft for draft in drafts}

    assert len(drafts) <= 10
    assert sum(1 for draft in drafts if "Mosfet" in (draft.symbol_name or "")) == 1
    assert sum(1 for draft in drafts if (draft.symbol_name or "").startswith("From")) == 0
    assert sum(1 for draft in drafts if (draft.symbol_name or "").startswith("Goto")) == 0
    assert sum(1 for draft in drafts if (draft.symbol_name or "").startswith("Scope")) == 0
    assert sum(1 for draft in drafts if draft.symbol_name == "Clock") == 0
    assert "DC Voltage Source" in by_name
    assert "Vref" in by_name
    assert "S-Function" in by_name
    assert (
        sum(1 for draft in drafts if (draft.symbol_name or "").startswith("Series RLC Branch")) == 3
    )


def test_source_text_only_contains_meaningful_params(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        slx_models=[
            _model(
                "model.slx",
                [
                    _block(
                        "constant-1",
                        "Vref",
                        "Constant",
                        {
                            "Position": "[0,0,20,20]",
                            "SourceType": "Constant",
                            "Value": "80",
                        },
                    )
                ],
            )
        ]
    )

    drafts = _slx_drafts(project, settings)

    assert len(drafts) == 1
    assert "Value=80" in drafts[0].source_text
    assert "Position" not in drafts[0].source_text
    assert "SourceType" not in drafts[0].source_text


def test_slx_block_source_text_marks_unresolved_and_inlines_workspace_literals() -> None:
    text = build_slx_block_source_text(
        model=_model(
            "model.slx",
            [
                _block(
                    "source-1",
                    "Source",
                    "Sine Wave",
                    {"Amplitude": "U1", "SampleTime": "Ts_sys"},
                )
            ],
        ),
        block=_block(
            "source-1",
            "Source",
            "Sine Wave",
            {"Amplitude": "U1", "SampleTime": "Ts_sys"},
        ),
        param_value_max=80,
        max_params=12,
        workspace_literals={"Ts_sys": "1e-6"},
    )

    assert "Amplitude=U1[未在 workspace 定义]" in text
    assert "SampleTime=Ts_sys(=1e-6)" in text


def test_slx_block_source_text_no_workspace_fallback_compatible() -> None:
    text = build_slx_block_source_text(
        model=_model("model.slx", []),
        block=_block("source-1", "Source", "Sine Wave", {"Amplitude": "U1"}),
        param_value_max=80,
        max_params=12,
    )

    assert "Amplitude=U1" in text
    assert "[未在 workspace 定义]" not in text
    assert "(=" not in text


def test_slx_block_drafts_pass_workspace_literals(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        slx_models=[
            _model(
                "model.slx",
                [
                    _block(
                        "source-1",
                        "Source",
                        "Sine Wave",
                        {"Amplitude": "U1", "SampleTime": "Ts_sys"},
                    )
                ],
            )
        ],
        m_files=[MFile("main.m", "script", [], [], [], "Ts_sys = 1e-6;")],
    )

    drafts = _slx_drafts(project, settings)

    assert len(drafts) == 1
    assert "Amplitude=U1[未在 workspace 定义]" in drafts[0].source_text
    assert "SampleTime=Ts_sys(=1e-6)" in drafts[0].source_text


def test_merge_guard_group_size_less_than_three_does_not_merge(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        slx_models=[
            _model(
                "model.slx",
                [
                    _block("c1", "Constant1", "Constant", {"Value": "0"}),
                    _block("c2", "Constant2", "Constant", {"Value": "0"}),
                ],
            )
        ]
    )

    drafts = _slx_drafts(project, settings)

    assert [draft.symbol_name for draft in drafts] == ["Constant1", "Constant2"]


def test_merge_guard_model_file_path_isolated(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    first_model_blocks = [
        _block(f"a-c{index}", f"Capacitor{index}", "Capacitor", {"Capacitance": "1e-6"})
        for index in range(1, 4)
    ]
    second_model_blocks = [
        _block(f"b-c{index}", f"Capacitor{index}", "Capacitor", {"Capacitance": "1e-6"})
        for index in range(1, 4)
    ]
    project = _project(
        files=[FileInfo("a.slx", ".slx", 10), FileInfo("b.slx", ".slx", 10)],
        slx_models=[
            _model("a.slx", first_model_blocks),
            _model("b.slx", second_model_blocks),
        ],
    )

    drafts = _slx_drafts(project, settings)

    assert len(drafts) == 2
    assert {draft.file_path for draft in drafts} == {"a.slx", "b.slx"}


def test_merge_guard_different_family_names_do_not_merge(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        slx_models=[
            _model(
                "model.slx",
                [
                    _block("s1", "Mosfet1", "Power Switch", {"Ron": "0.01"}),
                    _block("s2", "IGBT1", "Power Switch", {"Ron": "0.01"}),
                    _block("s3", "Mosfet2", "Power Switch", {"Ron": "0.01"}),
                ],
            )
        ]
    )

    drafts = _slx_drafts(project, settings)

    assert [draft.symbol_name for draft in drafts] == ["Mosfet1", "IGBT1", "Mosfet2"]


def test_section_4_block_parameters_do_not_emit_m_file_chunks(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        m_files=[MFile("main.m", "script", [], [], [], _script_with_block_parameters())],
        files=[FileInfo("main.m", ".m", 10)],
    )

    drafts = _m_file_drafts(project, settings)
    symbol_names = [draft.symbol_name or "" for draft in drafts]

    assert not any("Block Parameters" in name for name in symbol_names)
    assert not any(name.startswith("Section 4 ::") for name in symbol_names)


def test_non_section_4_m_file_sections_are_kept(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    project = _project(
        m_files=[MFile("main.m", "script", [], [], [], _script_with_block_parameters())],
        files=[FileInfo("main.m", ".m", 10)],
    )

    drafts = _m_file_drafts(project, settings)
    symbol_names = {draft.symbol_name for draft in drafts}

    assert None in symbol_names
    assert "Section 2: InitFcn" in symbol_names
    assert "Section 3: Model Parameters" in symbol_names
    assert "Section 5: Connections" in symbol_names


def test_meaningful_params_filters_simulink_metadata() -> None:
    assert _project_chunker._meaningful_params(
        {"Position": "[0,0,20,20]", "Value": "80", "SourceType": "Constant"}
    ) == {"Value": "80"}
    assert _project_chunker._meaningful_params({"GotoTag": "PWM1", "IconDisplay": "Tag"}) == {}
    assert _project_chunker._meaningful_params({"Amplitude": "U1", "BlockRotation": "270"}) == {
        "Amplitude": "U1"
    }


def _script_with_block_parameters() -> str:
    return """
%% Section 1: Model Info
model = 'DAB_Control';
%% Section 2: InitFcn
Kp = 1;
%% Section 3: Model Parameters
Ts = 1e-6;
%% Section 4: Block Parameters
% Block: Vref
set_param('DAB_Control/Vref','Value','80');
% Block: Mosfet1
set_param('DAB_Control/Mosfet1','Ron','0.01');
%% Section 5: Connections
line_count = 4;
"""
