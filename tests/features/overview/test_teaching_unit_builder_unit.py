from __future__ import annotations

import json

import pytest

from core.domain.project_graph import NodeType, ProjectGraph, ProjectNode
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnitRef
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.overview._prompt_loader import load_prompt_template
from features.overview._teaching_unit_builder import (
    DEFAULT_TEACHING_UNIT_TIMEOUT_SECONDS,
    MAX_PREREQUISITES,
    TeachingUnitBuilder,
    TeachingUnitBuildRequest,
    _teaching_unit_id,
)


class FakeTextProvider(TextProvider):
    def __init__(self, payload: dict[str, object] | list[object] | str) -> None:
        self._payload = payload
        self.calls = 0
        self.messages: list[LLMMessage] = []
        self.json_mode: bool | None = None
        self.timeout: float | None = None
        self.max_tokens: int | None = None

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls += 1
        self.messages = messages
        self.json_mode = json_mode
        self.timeout = timeout
        self.max_tokens = max_tokens
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return LLMResponse(
            text=text,
            prompt_tokens=10,
            completion_tokens=20,
            model="fake",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake", supports_json=True)


def _node(node_type: NodeType = NodeType.BLOCK) -> ProjectNode:
    return ProjectNode(
        id="model.slx#b1",
        type=node_type,
        label="Gain",
        source_ref=SourceRef(
            file_path="model.slx",
            block_id="b1",
            block_name="Gain",
            parent_subsystem="<root>",
        ),
        metadata={"block_type": "Gain", "parameter": "Kp"},
    )


def _graph() -> ProjectGraph:
    return ProjectGraph(
        project_id="p1",
        nodes=[_node()],
        edges=[],
        entry_points=["main.m"],
        execution_flow=["运行 main.m", "打开 model.slx"],
        data_flow=["Vref -> Gain"],
        control_flow=[],
        unresolved_symbols=[],
    )


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Gain 模块如何读",
        "summary": "Gain 模块把输入信号按 Kp 放大,是闭环控制量形成的一步。",
        "explanation_steps": ["看输入信号", "确认 Gain 参数", "跟踪输出去向"],
        "knowledge_points": ["比例增益", "闭环控制"],
        "confusion_points": ["Gain 不是积分器"],
    }
    payload.update(overrides)
    return payload


async def test_builder_ignores_llm_identity_fields_and_injects_code_fields() -> None:
    fake = FakeTextProvider(
        _payload(
            id="evil",
            target_id="evil-target",
            source_refs=[{"file_path": "evil.m"}],
            prerequisites=["forged"],
            prerequisites_hint=["pre-2", "missing", "pre-1"],
        )
    )
    builder = TeachingUnitBuilder(fake)
    request = TeachingUnitBuildRequest(
        project_id="p1",
        target_node=_node(),
        level="normal",
        prerequisite_candidates=[
            TeachingUnitRef(project_id="p1", teaching_unit_id="pre-1"),
            TeachingUnitRef(project_id="p1", teaching_unit_id="pre-2"),
        ],
    )

    unit = await builder.build(request, _graph())

    assert fake.calls == 1
    assert fake.json_mode is True
    assert fake.timeout == DEFAULT_TEACHING_UNIT_TIMEOUT_SECONDS
    assert unit.id.startswith("tu-")
    assert unit.id != "evil"
    assert unit.target == "block"
    assert unit.target_id == "model.slx#b1"
    assert unit.level == "normal"
    assert unit.source_refs == [request.target_node.source_ref]
    assert unit.prerequisites == [
        TeachingUnitRef(project_id="p1", teaching_unit_id="pre-2"),
        TeachingUnitRef(project_id="p1", teaching_unit_id="pre-1"),
    ]
    assert unit.knowledge_points == ["比例增益", "闭环控制"]


async def test_builder_removes_self_cycle_and_truncates_prerequisites() -> None:
    target = _node()
    current_id = _teaching_unit_id("p1", "block", target.id)
    candidates = [
        TeachingUnitRef(project_id="p1", teaching_unit_id=current_id),
        *[TeachingUnitRef(project_id="p1", teaching_unit_id=f"pre-{index}") for index in range(12)],
    ]
    builder = TeachingUnitBuilder(FakeTextProvider(_payload()))
    request = TeachingUnitBuildRequest(
        project_id="p1",
        target_node=target,
        level="beginner",
        prerequisite_candidates=candidates,
    )

    unit = await builder.build(request, _graph())

    assert current_id not in {item.teaching_unit_id for item in unit.prerequisites}
    assert len(unit.prerequisites) == MAX_PREREQUISITES
    assert unit.prerequisites[0].teaching_unit_id == "pre-0"


async def test_builder_rejects_invalid_payload() -> None:
    builder = TeachingUnitBuilder(FakeTextProvider({"title": "缺字段"}))
    request = TeachingUnitBuildRequest(
        project_id="p1",
        target_node=_node(),
        level="normal",
        prerequisite_candidates=[],
    )

    with pytest.raises(ValueError, match="teaching_unit_field_missing"):
        await builder.build(request, _graph())


async def test_builder_rejects_unsupported_target_type() -> None:
    builder = TeachingUnitBuilder(FakeTextProvider(_payload()))
    request = TeachingUnitBuildRequest(
        project_id="p1",
        target_node=_node(NodeType.PARAMETER),
        level="normal",
        prerequisite_candidates=[],
    )

    with pytest.raises(ValueError, match="unsupported_teaching_unit_target"):
        await builder.build(request, _graph())


def test_teaching_unit_prompt_yaml_loads_and_names_five_json_fields() -> None:
    template = load_prompt_template("teaching_unit.yaml")

    assert template.version == "v0.1.0"
    assert "title" in template.system
    assert "summary" in template.system
    assert "explanation_steps" in template.system
    assert "knowledge_points" in template.system
    assert "confusion_points" in template.system
    assert "不要输出 id / target / target_id / level / source_refs / prerequisites" in (
        template.system
    )
