from __future__ import annotations

from datetime import datetime

from core.domain.project import FileInfo, Project, ProjectType
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit
from features.chat._prompt_builder import ChatPromptBuilder
from features.chat._retriever import RetrievalHit, SourceEntry


class ReadyTeachingUnitStoreFake:
    def __init__(self, units: list[TeachingUnit]) -> None:
        self.units = units
        self.project_ids: list[str] = []

    async def list_ready_by_project(self, project_id: str) -> list[TeachingUnit]:
        self.project_ids.append(project_id)
        return self.units


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("model.slx", ".slx", 100)],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime(2026, 6, 15, 12, 0, 0),
        file_dependencies={},
    )


def _source_entry(
    block_id: str = "b1",
    block_name: str = "Gain",
) -> SourceEntry:
    ref = SourceRef(
        file_path="model.slx",
        block_id=block_id,
        block_name=block_name,
        parent_subsystem="<root>",
    )
    return SourceEntry(
        source_id="S1",
        hit=RetrievalHit(
            source_ref=ref,
            score=5.0,
            snippet="Block Gain(Gain) 位于 model.slx/<root>,参数 Gain=Kp",
            source_type="block",
            block_type="Gain",
        ),
        source_ref=ref,
        snippet="Block Gain(Gain) 位于 model.slx/<root>,参数 Gain=Kp",
        validation_key=("model.slx", "Gain", "Gain", "<root>"),
    )


def _unit(
    block_id: str = "b1",
    summary: str = "Gain 模块把输入信号乘以 Kp,是控制量形成的一步。",
) -> TeachingUnit:
    return TeachingUnit(
        id="tu-1",
        title="Gain 模块讲解",
        target="block",
        target_id=f"slx:model.slx::block:{block_id}",
        level="normal",
        summary=summary,
        prerequisites=[],
        explanation_steps=["定位输入", "查看 Kp", "跟踪输出"],
        knowledge_points=["比例增益"],
        source_refs=[
            SourceRef(
                file_path="model.slx",
                block_id=block_id,
                block_name="Gain",
                parent_subsystem="<root>",
            )
        ],
        confusion_points=["Gain 不是积分器"],
    )


def _user_message(builder: ChatPromptBuilder, entries: list[SourceEntry]) -> str:
    messages = builder.build_messages(_project(), entries, history=[], question="这个 Kp 是什么?")
    return messages[-1].content


def test_ready_teaching_unit_matching_retrieval_hit_adds_summary_context() -> None:
    store = ReadyTeachingUnitStoreFake([_unit()])
    builder = ChatPromptBuilder(teaching_unit_store=store)

    user = _user_message(builder, [_source_entry()])

    assert store.project_ids == ["p1"]
    assert "[S1] block:" in user
    assert "教学单元补充: Gain 模块把输入信号乘以 Kp" in user


def test_no_ready_teaching_unit_keeps_prompt_unchanged() -> None:
    builder = ChatPromptBuilder(teaching_unit_store=ReadyTeachingUnitStoreFake([]))

    user = _user_message(builder, [_source_entry()])

    assert "教学单元补充" not in user


def test_unmatched_ready_teaching_unit_is_not_added() -> None:
    builder = ChatPromptBuilder(teaching_unit_store=ReadyTeachingUnitStoreFake([_unit("b2")]))

    user = _user_message(builder, [_source_entry()])

    assert "教学单元补充" not in user


def test_prompt_builder_without_teaching_unit_store_does_not_query_context() -> None:
    builder = ChatPromptBuilder()

    user = _user_message(builder, [_source_entry()])

    assert "教学单元补充" not in user
