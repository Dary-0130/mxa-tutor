from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_graph import ProjectGraph
from core.domain.slx_model import SlxBlock, SlxModel
from features.chat._retriever import KeywordRetriever, _tokenize


class GraphProvider:
    def __init__(self) -> None:
        self.calls = 0

    def build(self, project: Project) -> ProjectGraph:
        self.calls += 1
        return ProjectGraph(
            project_id=project.id,
            nodes=[],
            edges=[],
            entry_points=["main.m"],
            execution_flow=["main.m", "motor_model.slx"],
            data_flow=[],
            control_flow=[],
            unresolved_symbols=["Kp_speed"],
        )


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[
            FileInfo("main.m", ".m", 100, "启动脚本"),
            FileInfo("motor_model.slx", ".slx", 200, "电机控制模型"),
        ],
        slx_models=[
            SlxModel(
                file_path="motor_model.slx",
                name="motor_model",
                blocks=[
                    SlxBlock(
                        block_id="b1",
                        name="SpeedController",
                        block_type="PID Controller",
                        parameters={"Kp": "5.0", "Ki": "0.1"},
                        position=(0, 0, 10, 10),
                        parent_subsystem="SpeedLoop",
                    )
                ],
                lines=[],
                subsystems={},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[
            MFile(
                file_path="main.m",
                file_role="script",
                functions=[
                    MFunction(
                        name="initSpeedController",
                        inputs=[],
                        outputs=["Kp_speed"],
                        line_range=(3, 8),
                        docstring="速度环参数初始化",
                    )
                ],
                imports=[],
                uses_toolbox=[],
                raw_code="",
            )
        ],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


def test_tokenizer_splits_camel_snake_slash_and_alias() -> None:
    tokens = set(_tokenize("速度环 SpeedController speed_controller CurrentLoop/PID Kp"))

    assert {"speed", "speedloop"} & tokens
    assert {"speed", "controller", "current", "loop", "pid", "kp"} <= tokens


@pytest.mark.asyncio
async def test_keyword_retriever_finds_block_and_caps_snippet() -> None:
    provider = GraphProvider()
    retriever = KeywordRetriever(provider)

    hits = await retriever.search(_project(), "速度环 Kp 为什么这么大", top_k=8)

    assert provider.calls == 1
    assert hits
    block_hit = next(hit for hit in hits if hit.source_type == "block")
    assert block_hit.source_ref.block_name == "SpeedController"
    assert block_hit.block_type == "PID Controller"
    assert len(block_hit.snippet) <= 300


@pytest.mark.asyncio
async def test_keyword_retriever_min_score_filters_unrelated_query() -> None:
    hits = await KeywordRetriever(GraphProvider()).search(_project(), "完全无关的问题", top_k=8)

    assert hits == []


@pytest.mark.asyncio
async def test_keyword_retriever_caps_top_k() -> None:
    hits = await KeywordRetriever(GraphProvider()).search(_project(), "main speed Kp", top_k=99)

    assert len(hits) <= 12
