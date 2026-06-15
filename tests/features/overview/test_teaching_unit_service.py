from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from adapters.storage._connection import open_connection
from adapters.storage.in_memory_project_store import InMemoryProjectStore
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_teaching_unit_store import SqliteTeachingUnitStore
from core.domain.exceptions import (
    LLMTimeoutError,
    TeachingUnitGenerationError,
    TeachingUnitTargetNotFoundError,
    UnsupportedTeachingLevelError,
)
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_graph import NodeType, ProjectGraph, ProjectNode
from core.domain.slx_model import SlxBlock, SlxModel
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit
from features.overview._teaching_level_policy import TeachingLevelPolicy, TeachingUnitRequest
from features.overview._teaching_unit_builder import TeachingUnitBuildRequest
from features.overview._teaching_unit_service import (
    BUILDER_VERSION,
    PROMPT_VERSION,
    SOURCE_VERSION,
    TeachingUnitService,
)


class GraphBuilderFake:
    def __init__(self, graph: ProjectGraph) -> None:
        self._graph = graph

    def build(self, project: Project) -> ProjectGraph:
        assert project.id == "p1"
        return self._graph


class TeachingUnitBuilderFake:
    def __init__(self, *, delay: float = 0.0, exc: Exception | None = None) -> None:
        self.delay = delay
        self.exc = exc
        self.calls = 0
        self.requests: list[TeachingUnitBuildRequest] = []

    async def build(
        self,
        request: TeachingUnitBuildRequest,
        graph: ProjectGraph,
    ) -> TeachingUnit:
        self.calls += 1
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc is not None:
            raise self.exc
        return TeachingUnit(
            id=f"unit-{request.target_node.id}",
            title="Gain 模块讲解",
            target="block",
            target_id=request.target_node.id,
            level=request.level,
            summary="说明 Gain 模块如何影响输出。",
            prerequisites=request.prerequisite_candidates,
            explanation_steps=["定位输入", "查看参数", "跟踪输出"],
            knowledge_points=["比例增益", "闭环控制"],
            source_refs=[request.target_node.source_ref],
            confusion_points=["不要把 Gain 当作积分器"],
        )


def _node(node_id: str = "slx:model.slx::block:b1") -> ProjectNode:
    return ProjectNode(
        id=node_id,
        type=NodeType.BLOCK,
        label="Gain",
        source_ref=SourceRef(
            file_path="model.slx",
            block_id="b1",
            block_name="Gain",
            parent_subsystem=None,
        ),
        metadata={"block:type": "Gain"},
    )


def _graph(nodes: list[ProjectNode] | None = None) -> ProjectGraph:
    return ProjectGraph(
        project_id="p1",
        nodes=nodes if nodes is not None else [_node()],
        edges=[],
        entry_points=["m:main.m"],
        execution_flow=["m:main.m", "slx:model.slx"],
        data_flow=[],
        control_flow=[],
        unresolved_symbols=[],
    )


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("main.m", ".m", 100), FileInfo("model.slx", ".slx", 100)],
        slx_models=[
            SlxModel(
                file_path="model.slx",
                name="model",
                blocks=[
                    SlxBlock(
                        block_id="b1",
                        name="Gain",
                        block_type="Gain",
                        parameters={},
                        position=(0, 0, 10, 10),
                        parent_subsystem=None,
                    )
                ],
                lines=[],
                subsystems={},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[MFile("main.m", "script", [], [], [], "")],
        mat_files=[],
        created_at=datetime(2026, 6, 15, 12, 0, 0),
        file_dependencies={},
    )


async def _project_store() -> InMemoryProjectStore:
    store = InMemoryProjectStore()
    project = _project()
    await store.create_pending(project.id, project.name)
    await store.mark_ready(project.id, project)
    return store


async def _sqlite_teaching_store(tmp_path: Path) -> SqliteTeachingUnitStore:
    db_path = str(tmp_path / "service.db")
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    sqlite_project_store = SqliteProjectStore(db_path)
    await sqlite_project_store.create_pending("p1", "demo.zip")
    return SqliteTeachingUnitStore(db_path)


def _request(level: str | None = None) -> TeachingUnitRequest:
    return TeachingUnitRequest(
        project_id="p1",
        target_type="block",
        target_id="slx:model.slx::block:b1",
        level=level,  # type: ignore[arg-type]
        trigger="api",
    )


def _service(
    project_store: InMemoryProjectStore,
    teaching_store: SqliteTeachingUnitStore,
    builder: TeachingUnitBuilderFake,
    graph: ProjectGraph | None = None,
) -> TeachingUnitService:
    return TeachingUnitService(
        project_store=project_store,
        teaching_unit_store=teaching_store,
        builder=builder,
        level_policy=TeachingLevelPolicy(),
        model_name="fake-model",
        graph_builder_factory=lambda: GraphBuilderFake(graph or _graph()),
    )


async def test_policy_defaults_to_normal_and_rejects_advanced() -> None:
    policy = TeachingLevelPolicy()

    assert policy.resolve(_request(level=None)) == "normal"
    assert policy.resolve(_request(level="beginner")) == "beginner"
    with pytest.raises(UnsupportedTeachingLevelError):
        policy.resolve(_request(level="advanced"))


async def test_get_or_generate_caches_ready_unit(tmp_path: Path) -> None:
    project_store = await _project_store()
    teaching_store = await _sqlite_teaching_store(tmp_path)
    builder = TeachingUnitBuilderFake()
    service = _service(project_store, teaching_store, builder)

    first = await service.get_or_generate(_request())
    second = await service.get_or_generate(_request())

    assert first == second
    assert builder.calls == 1
    assert builder.requests[0].level == "normal"


async def test_get_or_generate_deduplicates_100_concurrent_requests(tmp_path: Path) -> None:
    project_store = await _project_store()
    teaching_store = await _sqlite_teaching_store(tmp_path)
    builder = TeachingUnitBuilderFake(delay=0.01)
    service = _service(project_store, teaching_store, builder)

    units = await asyncio.gather(*[service.get_or_generate(_request()) for _index in range(100)])

    assert len({unit.id for unit in units}) == 1
    assert builder.calls == 1
    record = await teaching_store.get_record_by_key(
        (
            "p1",
            "block",
            "slx:model.slx::block:b1",
            "normal",
            BUILDER_VERSION,
            PROMPT_VERSION,
            "fake-model",
            SOURCE_VERSION,
        )
    )
    assert record is not None
    assert record.state == "ready"
    assert record.unit == units[0]


async def test_failed_retryable_record_retries_and_increments_count(tmp_path: Path) -> None:
    project_store = await _project_store()
    teaching_store = await _sqlite_teaching_store(tmp_path)
    builder = TeachingUnitBuilderFake(exc=LLMTimeoutError("timeout"))
    service = _service(project_store, teaching_store, builder)

    with pytest.raises(TeachingUnitGenerationError):
        await service.get_or_generate(_request())
    with pytest.raises(TeachingUnitGenerationError):
        await service.get_or_generate(_request())

    record = await teaching_store.get_record_by_key(
        (
            "p1",
            "block",
            "slx:model.slx::block:b1",
            "normal",
            BUILDER_VERSION,
            PROMPT_VERSION,
            "fake-model",
            SOURCE_VERSION,
        )
    )
    assert record is not None
    assert record.state == "failed_retryable"
    assert record.retry_count == 2
    assert builder.calls == 2


async def test_target_not_found_returns_domain_error_and_marks_permanent(
    tmp_path: Path,
) -> None:
    project_store = await _project_store()
    teaching_store = await _sqlite_teaching_store(tmp_path)
    builder = TeachingUnitBuilderFake()
    service = _service(project_store, teaching_store, builder, graph=_graph(nodes=[]))

    with pytest.raises(TeachingUnitTargetNotFoundError):
        await service.get_or_generate(_request())

    record = await teaching_store.get_record_by_key(
        (
            "p1",
            "block",
            "slx:model.slx::block:b1",
            "normal",
            BUILDER_VERSION,
            PROMPT_VERSION,
            "fake-model",
            SOURCE_VERSION,
        )
    )
    assert record is not None
    assert record.state == "failed_permanent"
    assert builder.calls == 0
