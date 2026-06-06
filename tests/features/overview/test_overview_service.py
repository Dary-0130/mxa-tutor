from __future__ import annotations

import copy
from typing import Any

import pytest

from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    OverviewGenerationError,
)
from features.overview import InMemoryOverviewCache
from features.overview import overview_service as service_module
from features.overview._prompt_builder import build_messages
from features.overview.overview_schemas import ProjectOverview
from features.overview.overview_service import ProjectOverviewService
from tests.features.overview.conftest import (
    OverviewBuilderFake,
    OverviewProviderFake,
    OverviewResolverFake,
    make_overview_evidence,
    make_overview_file_entries,
    make_overview_graph,
    make_overview_payload,
    make_overview_response,
)


class OverviewStoreFake:
    def __init__(self, project: Any) -> None:
        self.project = project

    async def get_project(self, project_id: str) -> Any:
        return self.project


class NoopChunkingService:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[tuple[ProjectOverview, str]] = []

    async def build_embed_store_overview_chunk(
        self,
        overview: ProjectOverview,
        project_id: str,
    ) -> int:
        self.calls.append((overview, project_id))
        if self.exc is not None:
            raise self.exc
        return 0


def _service(project: Any, response: Any) -> ProjectOverviewService:
    builder = OverviewBuilderFake(make_overview_graph())
    return ProjectOverviewService(
        OverviewStoreFake(project),
        InMemoryOverviewCache(),
        OverviewResolverFake(),
        OverviewProviderFake(response=response),
        chunking_service=NoopChunkingService(),
        graph_builder_factory=lambda: builder,
    )


def _parse(project: Any, payload: dict[str, Any] | str) -> ProjectOverview:
    return _service(
        project,
        make_overview_response(make_overview_payload()),
    )._parse_and_validate(make_overview_response(payload), project)


@pytest.fixture
def project(make_project, make_file_info, make_slx_model, make_slx_block, make_m_file):
    return make_project(
        files=[
            make_file_info("main.m"),
            make_file_info("helper.m"),
            make_file_info("model.slx", ".slx"),
        ],
        slx_models=[make_slx_model("model.slx", blocks=[make_slx_block("b1", name="Gain")])],
        m_files=[make_m_file("main.m"), make_m_file("helper.m")],
    )


@pytest.mark.asyncio
async def test_get_or_generate_miss_uses_to_thread_twice(
    monkeypatch: pytest.MonkeyPatch,
    project: Any,
) -> None:
    calls: list[str] = []

    async def _to_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(service_module.asyncio, "to_thread", _to_thread)
    provider = OverviewProviderFake(response=make_overview_response(make_overview_payload()))
    builder = OverviewBuilderFake(make_overview_graph())
    service = ProjectOverviewService(
        OverviewStoreFake(project),
        InMemoryOverviewCache(),
        OverviewResolverFake(),
        provider,
        chunking_service=NoopChunkingService(),
        graph_builder_factory=lambda: builder,
    )

    overview = await service.get_or_generate("p1")

    assert overview.project_title == "Buck 控制"
    assert calls == ["_build_graph_sync", "chat"]
    assert provider.kwargs["json_mode"] is True
    assert provider.kwargs["timeout"] == 60.0
    assert provider.kwargs["max_tokens"] == 4000


@pytest.mark.asyncio
async def test_get_or_generate_cache_hit_skips_graph_and_llm(project: Any) -> None:
    overview = ProjectOverview.model_validate(make_overview_payload())
    cache = InMemoryOverviewCache()
    await cache.put("p1", overview)
    provider = OverviewProviderFake(response=make_overview_response(make_overview_payload()))
    builder = OverviewBuilderFake(make_overview_graph())
    service = ProjectOverviewService(
        OverviewStoreFake(project),
        cache,
        OverviewResolverFake(),
        provider,
        chunking_service=NoopChunkingService(),
        graph_builder_factory=lambda: builder,
    )

    assert await service.get_or_generate("p1") is overview
    assert provider.calls == 0
    assert builder.calls == 0


@pytest.mark.parametrize(
    "error_type",
    [LLMAuthError, LLMQuotaError, LLMRateLimitError, LLMServerError, LLMTimeoutError],
)
@pytest.mark.asyncio
async def test_get_or_generate_passes_llm_errors_through(
    error_type: type[Exception], project: Any
) -> None:
    provider = OverviewProviderFake(exc=error_type("x"))
    service = ProjectOverviewService(
        OverviewStoreFake(project),
        InMemoryOverviewCache(),
        OverviewResolverFake(),
        provider,
        chunking_service=NoopChunkingService(),
        graph_builder_factory=lambda: OverviewBuilderFake(make_overview_graph()),
    )

    with pytest.raises(error_type):
        await service.get_or_generate("p1")


@pytest.mark.parametrize("text", ["not json", '{"project_title": "only one"}'])
def test_parse_and_validate_translates_json_and_schema_failures(project: Any, text: str) -> None:
    service = _service(project, make_overview_response(make_overview_payload()))

    with pytest.raises(OverviewGenerationError):
        service._parse_and_validate(make_overview_response(text), project)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["main_entry_files"][0].update(file_path="missing.m"),
        lambda p: p["main_simulink_models"][0].update(file_path="missing.slx"),
        lambda p: p["key_files"][0].update(file_path="missing.m"),
        lambda p: p["evidence"][0].update(file_path="missing.m"),
    ],
)
def test_parse_and_validate_rejects_unknown_file_paths(project: Any, mutate: Any) -> None:
    payload = copy.deepcopy(make_overview_payload())
    mutate(payload)

    with pytest.raises(OverviewGenerationError):
        _parse(project, payload)


def test_parse_and_validate_rejects_duplicate_block_name_wrong_location(
    make_project,
    make_file_info,
    make_slx_model,
    make_slx_block,
) -> None:
    block_a = make_slx_block("a1", name="Gain", parent_subsystem="SpeedLoop")
    block_b = make_slx_block("b1", name="Gain", parent_subsystem="CurrentLoop")
    project = make_project(
        files=[make_file_info("model_a.slx", ".slx"), make_file_info("model_b.slx", ".slx")],
        slx_models=[
            make_slx_model("model_a.slx", blocks=[block_a]),
            make_slx_model("model_b.slx", blocks=[block_b]),
        ],
    )
    payload = make_overview_payload()
    payload["main_entry_files"] = [{"file_path": "model_a.slx", "role": "入口"}]
    payload["main_simulink_models"] = [{"file_path": "model_a.slx", "summary": "模型"}]
    payload["key_files"] = make_overview_file_entries("model_a.slx", "model_b.slx", "model_a.slx")
    payload["key_blocks"] = [
        {
            "block_name": "Gain",
            "block_type": "Gain",
            "location": "model_b.slx / SpeedLoop",
            "why_key": "错配",
        }
    ]
    payload["evidence"] = make_overview_evidence("model_a.slx", "model_b.slx", "model_a.slx", "a1")
    payload["evidence"][1]["block_id"] = "b1"

    with pytest.raises(OverviewGenerationError):
        _parse(project, payload)


@pytest.mark.parametrize("location", ["model.slx/<root>", "model.slx / <root> / Gain", " / <root>"])
def test_parse_and_validate_rejects_bad_block_location(project: Any, location: str) -> None:
    payload = make_overview_payload()
    payload["key_blocks"][0]["location"] = location

    with pytest.raises(OverviewGenerationError):
        _parse(project, payload)


@pytest.mark.parametrize(
    "evidence",
    [
        {"file_path": "model.slx", "block_id": "missing"},
        {"file_path": "main.m", "line_range": [0, 5]},
        {"file_path": "main.m", "line_range": [5, 4]},
    ],
)
def test_parse_and_validate_rejects_bad_evidence(project: Any, evidence: dict[str, Any]) -> None:
    payload = make_overview_payload()
    payload["evidence"][0] = evidence

    with pytest.raises(OverviewGenerationError):
        _parse(project, payload)


def test_parse_and_validate_allows_no_slx_project_with_empty_models(
    make_project,
    make_file_info,
    make_m_file,
) -> None:
    project = make_project(
        files=[make_file_info("main.m"), make_file_info("helper.m"), make_file_info("params.m")],
        m_files=[make_m_file("main.m"), make_m_file("helper.m"), make_m_file("params.m")],
    )
    payload = make_overview_payload()
    payload["main_simulink_models"] = []
    payload["key_blocks"] = []
    payload["key_files"] = make_overview_file_entries("main.m", "helper.m", "params.m")
    payload["evidence"] = make_overview_evidence("main.m", "helper.m", "params.m", "unused")
    payload["evidence"][2].pop("block_id")
    payload["evidence"][2]["line_range"] = [1, 2]

    overview = _parse(project, payload)

    assert overview.main_simulink_models == []


def test_parse_and_validate_rejects_m_file_as_simulink_model(project: Any) -> None:
    payload = make_overview_payload()
    payload["main_simulink_models"][0]["file_path"] = "main.m"

    with pytest.raises(OverviewGenerationError):
        _parse(project, payload)


def test_prompt_builder_truncates_unresolved_symbols(project: Any) -> None:
    graph = make_overview_graph([f"unresolved:s{i}" for i in range(55)])

    content = build_messages(project, graph, "general")[1].content

    assert "unresolved:s49" in content
    assert "unresolved:s50" not in content
    assert "还有 5 项未列出" in content
