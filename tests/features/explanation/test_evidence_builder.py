from __future__ import annotations

import json
from datetime import datetime

from core.domain.m_file import MFile, MFunction
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_overview import ProjectOverview
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel
from features.explanation import EvidenceBuilder
from features.explanation._score import (
    classify_block_type,
    is_ambiguously_named,
    select_high_value_blocks,
)
from features.overview.project_graph_builder import ProjectGraphBuilder
from tests.features.overview.conftest import make_domain_project_overview


def test_d3_selection_scores_blocks_and_marks_ambiguous_names() -> None:
    model = _model(
        blocks=[
            _block("1", "1", "Constant", {"Value": "Vdc_nom"}),
            _block("2", "wr", "Gain", {"Gain": "Kp"}),
            _block("3", "Bus Selector1", "BusSelector", {"OutputSignals": "wr,iq"}),
            _block("4", "Scope", "Scope"),
            _block("5", "B_grid", "Three-Phase VI Measurement"),
        ],
        lines=[
            SlxLine("1", 1, "2", 1),
            SlxLine("2", 1, "3", 1),
            SlxLine("3", 1, "4", 1),
            SlxLine("2", 1, "5", 1),
        ],
    )
    project = _project(slx_models=[model])
    graph = ProjectGraphBuilder().build(project)

    result = select_high_value_blocks(project, graph, min_blocks=3, max_blocks=10)

    assert 3 <= result.diagnostics.selected_count <= 10
    assert result.diagnostics.raw_layer_counts["L1"] >= 3
    assert result.diagnostics.top_layer_counts["L3"] == 1
    assert classify_block_type("BusSelector") == "routing"
    assert is_ambiguously_named(model.blocks[0]) is True
    assert is_ambiguously_named(model.blocks[1]) is False


def test_evidence_builder_outputs_typed_payloads_and_sequential_ids() -> None:
    model = _model(
        blocks=[
            _block("1", "Vdc", "Constant", {"Value": "Vdc_nom"}),
            _block("2", "Kp", "Gain", {"Gain": "Kp"}),
            _block("3", "Bus Creator1", "BusCreator", {"InputSignals": "Vdc,Kp"}),
            _block("4", "Scope", "Scope"),
            _block("5", "Voltage Measurement", "Voltage Measurement"),
        ],
        lines=[
            SlxLine("1", 1, "2", 1),
            SlxLine("2", 1, "3", 1),
            SlxLine("3", 1, "4", 1),
            SlxLine("1", 1, "5", 1),
        ],
        subsystems={"Data acquisition": ["4", "5"]},
    )
    project = _project(slx_models=[model])
    graph = ProjectGraphBuilder().build(project)

    pack = EvidenceBuilder(max_blocks=10).build(project, graph, _overview())
    data = pack.to_dict()
    evidence = data["evidence"]
    kinds = {item["kind"] for item in evidence}

    assert [item["evidence_id"] for item in evidence] == [
        f"E{index:03d}" for index in range(1, len(evidence) + 1)
    ]
    assert {"project_overview_field", "slx_block", "parameter", "slx_line", "scope"} <= kinds
    assert "bus_signal" in kinds
    assert all(len(item["summary"]) <= 200 for item in evidence)

    parameter = next(item for item in evidence if item["kind"] == "parameter")
    assert parameter["payload"]["block_ref"]["block_name"] in {"Vdc", "Kp", "Bus Creator1"}
    assert parameter["payload"]["role_guess"] in {
        "unknown",
        "operating_point",
        "gain",
        "observation",
    }
    assert set(parameter["source_ref"]) == {
        "file_path",
        "line_range",
        "block_id",
        "block_name",
        "parent_subsystem",
        "parameter_name",
    }


def test_evidence_pack_excludes_raw_code_and_docstrings() -> None:
    secret = "SECRET_RAW_CODE_MARKER"
    m_file = MFile(
        file_path="main.m",
        file_role="entry",
        functions=[
            MFunction(
                name="main",
                inputs=[],
                outputs=[],
                line_range=(1, 3),
                docstring=f"{secret} docstring",
            )
        ],
        imports=[],
        uses_toolbox=[],
        raw_code=f"{secret} raw code",
    )
    project = _project(m_files=[m_file], slx_models=[_model(blocks=[_block("1", "Gain1", "Gain")])])
    graph = ProjectGraphBuilder().build(project)

    data = EvidenceBuilder(max_blocks=5).build(project, graph).to_dict()

    assert secret not in json.dumps(data, ensure_ascii=False)


def _project(
    *,
    slx_models: list[SlxModel] | None = None,
    m_files: list[MFile] | None = None,
) -> Project:
    files = [FileInfo(model.file_path, ".slx", 1000) for model in slx_models or []]
    files.extend(FileInfo(m_file.file_path, ".m", 1000) for m_file in m_files or [])
    return Project(
        id="p1",
        name="TestProject",
        project_type=ProjectType.GENERAL,
        files=files,
        slx_models=slx_models or [],
        m_files=m_files or [],
        mat_files=[],
        created_at=datetime(2026, 6, 8),
        file_dependencies={},
    )


def _model(
    *,
    blocks: list[SlxBlock],
    lines: list[SlxLine] | None = None,
    subsystems: dict[str, list[str]] | None = None,
) -> SlxModel:
    return SlxModel(
        file_path="model.slx",
        name="model",
        blocks=blocks,
        lines=lines or [],
        subsystems=subsystems or {},
        solver_config={"Solver": "FixedStepDiscrete"},
        parse_warnings=["发现可能的 workspace 变量引用:Kp"],
    )


def _block(
    block_id: str,
    name: str,
    block_type: str,
    parameters: dict[str, str] | None = None,
) -> SlxBlock:
    return SlxBlock(
        block_id=block_id,
        name=name,
        block_type=block_type,
        parameters=parameters or {},
        position=(0, 0, 10, 10),
        parent_subsystem=None,
    )


def _overview() -> ProjectOverview:
    return make_domain_project_overview(
        {
            "project_title": "测试工程",
            "project_type": "general",
            "one_sentence_summary": "这是一个静态结构测试工程。",
            "main_entry_files": [{"file_path": "model.slx", "role": "主模型"}],
            "main_simulink_models": [{"file_path": "model.slx", "summary": "主 Simulink 模型"}],
            "main_execution_flow": ["查看模型", "读取参数", "观察 Scope"],
            "key_files": [
                {"file_path": "model.slx", "why_key": "主模型"},
                {"file_path": "main.m", "why_key": "可选入口"},
                {"file_path": "params.m", "why_key": "参数文件"},
            ],
            "key_blocks": [
                {
                    "block_name": "Kp",
                    "block_type": "Gain",
                    "location": "model.slx / <root>",
                    "why_key": "代表控制增益",
                }
            ],
            "knowledge_points": ["静态结构", "参数", "观测点"],
            "beginner_reading_order": ["model.slx", "Kp", "Scope"],
            "likely_confusing_points": ["未能确定 Kp 的物理单位", "Scope 只说明观察位置"],
            "evidence": [
                {"file_path": "model.slx", "block_id": "1"},
                {"file_path": "model.slx", "block_id": "2"},
                {"file_path": "model.slx", "block_id": "4"},
            ],
        }
    )
