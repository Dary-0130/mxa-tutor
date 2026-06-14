"""Tests for overview list-length lenient truncation (decision 17)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from core.domain.exceptions import OverviewGenerationError
from core.domain.project_overview import ProjectOverview
from features.overview import InMemoryOverviewCache
from features.overview.overview_service import ProjectOverviewService
from tests.features.overview.conftest import (
    OverviewBuilderFake,
    OverviewProviderFake,
    OverviewResolverFake,
    make_overview_graph,
    make_overview_payload,
    make_overview_response,
)


class _OverviewStoreFake:
    async def get_project(self, project_id: str) -> Any:
        _ = project_id
        raise AssertionError("not used by lenient truncation tests")


class _NoopChunkingService:
    async def build_embed_store_overview_chunk(
        self,
        overview: ProjectOverview,
        project_id: str,
    ) -> int:
        _ = overview, project_id
        return 0


@pytest.fixture
def base_valid_raw() -> dict[str, Any]:
    return copy.deepcopy(make_overview_payload())


@pytest.fixture
def service() -> ProjectOverviewService:
    return ProjectOverviewService(
        store=_OverviewStoreFake(),
        cache=InMemoryOverviewCache(),
        project_type_resolver=OverviewResolverFake(),
        text_provider=OverviewProviderFake(
            response=make_overview_response(make_overview_payload())
        ),
        chunking_service=_NoopChunkingService(),
        graph_builder_factory=lambda: OverviewBuilderFake(make_overview_graph()),
    )


class TestLenientTruncation:
    def test_knowledge_points_oversize_truncated_to_max(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """LLM gives 8 knowledge_points; service keeps the first 6."""
        base_valid_raw["knowledge_points"] = [f"k{i}" for i in range(8)]

        result = service._try_parse_with_list_truncation(base_valid_raw)

        assert len(result.knowledge_points) == 6
        assert result.knowledge_points == [f"k{i}" for i in range(6)]

    def test_multiple_lists_oversize_all_truncated(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """Multiple top-level list overflows are truncated together."""
        base_valid_raw["knowledge_points"] = [f"k{i}" for i in range(8)]
        base_valid_raw["main_execution_flow"] = [f"s{i}" for i in range(12)]

        result = service._try_parse_with_list_truncation(base_valid_raw)

        assert len(result.knowledge_points) == 6
        assert len(result.main_execution_flow) == 10
        assert result.main_execution_flow == [f"s{i}" for i in range(10)]

    def test_list_too_short_not_truncatable(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """A list below min_length is not rescued."""
        base_valid_raw["main_execution_flow"] = ["only_one"]

        with pytest.raises(OverviewGenerationError):
            service._try_parse_with_list_truncation(base_valid_raw)

    def test_string_oversize_not_truncated(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """String max_length errors are not truncated."""
        base_valid_raw["project_title"] = "x" * 100

        with pytest.raises(OverviewGenerationError):
            service._try_parse_with_list_truncation(base_valid_raw)

    def test_item_validation_failure_not_truncated(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """List item validation errors are not a length-only problem."""
        base_valid_raw["main_entry_files"] = [{"file_path": "", "role": ""}]

        with pytest.raises(OverviewGenerationError):
            service._try_parse_with_list_truncation(base_valid_raw)

    def test_mixed_too_long_and_other_error_not_truncated(
        self,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """too_long mixed with another error is rejected conservatively."""
        base_valid_raw["knowledge_points"] = [f"k{i}" for i in range(8)]
        base_valid_raw["project_title"] = "x" * 100

        with pytest.raises(OverviewGenerationError):
            service._try_parse_with_list_truncation(base_valid_raw)

    def test_happy_path_no_truncation_no_logs(
        self,
        monkeypatch: pytest.MonkeyPatch,
        service: ProjectOverviewService,
        base_valid_raw: dict[str, Any],
    ) -> None:
        """Valid payloads return directly without truncation logging."""
        info_calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(
            "features.overview.overview_service.logger.info",
            lambda *args, **kwargs: info_calls.append(args),
        )

        result = service._try_parse_with_list_truncation(base_valid_raw)

        assert result.project_title == base_valid_raw["project_title"]
        assert info_calls == []
