"""Project overview generation service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import PurePath
from typing import Protocol

from loguru import logger
from pydantic import ValidationError

from core.domain.exceptions import OverviewGenerationError
from core.domain.project import Project
from core.domain.project_graph import ProjectGraph
from core.interfaces.llm_provider import LLMResponse, TextProvider
from core.interfaces.project_store import ProjectStore
from core.interfaces.project_type_resolver import ProjectTypeResolver
from features.chunking import ChunkingService

from ._overview_cache import OverviewCache
from ._prompt_builder import build_messages
from ._prompt_loader import load_prompt_template
from .overview_schemas import BlockEntry, ProjectOverview
from .project_graph_builder import ProjectGraphBuilder

DEFAULT_OVERVIEW_TIMEOUT_SECONDS = 60.0
DEFAULT_OVERVIEW_MAX_TOKENS = 4000


class ProjectGraphBuilderLike(Protocol):
    def build(self, project: Project) -> ProjectGraph:
        """Build a ProjectGraph from ``project``."""
        ...


class ProjectOverviewService:
    """Generate and cache ProjectOverview values."""

    def __init__(
        self,
        store: ProjectStore,
        cache: OverviewCache,
        project_type_resolver: ProjectTypeResolver,
        text_provider: TextProvider,
        chunking_service: ChunkingService,
        graph_builder_factory: Callable[[], ProjectGraphBuilderLike] | None = None,
        timeout: float = DEFAULT_OVERVIEW_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_OVERVIEW_MAX_TOKENS,
    ) -> None:
        self._store = store
        self._cache = cache
        self._project_type_resolver = project_type_resolver
        self._text_provider = text_provider
        self._chunking_service = chunking_service
        self._graph_builder_factory = graph_builder_factory or ProjectGraphBuilder
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def get_or_generate(self, project_id: str) -> ProjectOverview:
        """Return cached overview or generate a fresh one."""
        project = await self._store.get_project(project_id)
        cached = await self._cache.get(project_id)
        if cached is not None:
            logger.info("Overview cache hit: project_id={}", project_id)
            try:
                await self._chunking_service.build_embed_store_overview_chunk(cached, project_id)
            except Exception as exc:
                logger.error(
                    "overview_chunking_failed_on_cache_hit: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
            return cached

        graph = await asyncio.to_thread(self._build_graph_sync, project)
        project_type_hint = self._project_type_resolver.resolve(project)
        messages = build_messages(project, graph, project_type_hint)
        template = load_prompt_template()
        logger.info(
            "Overview LLM call: project_id={} prompt_version={}",
            project_id,
            template.version,
        )
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        overview = self._parse_and_validate(response, project)
        await self._cache.put(project_id, overview)
        try:
            await self._chunking_service.build_embed_store_overview_chunk(overview, project_id)
        except Exception as exc:
            logger.error(
                "overview_chunking_failed: project_id={} exception={}",
                project_id,
                type(exc).__name__,
            )
        return overview

    def _build_graph_sync(self, project: Project) -> ProjectGraph:
        builder = self._graph_builder_factory()
        return builder.build(project)

    def _parse_and_validate(self, response: LLMResponse, project: Project) -> ProjectOverview:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            logger.error("Overview JSON parse failed: error_type={}", type(exc).__name__)
            raise OverviewGenerationError("导览生成失败,请刷新重试") from None

        try:
            overview = ProjectOverview.model_validate(payload)
        except ValidationError as exc:
            logger.error("Overview schema validation failed: error_type={}", type(exc).__name__)
            raise OverviewGenerationError("导览生成失败,请刷新重试") from None

        try:
            _validate_file_paths(overview, project)
            _validate_block_entries(overview.key_blocks, project)
            _validate_evidence(overview, project)
        except OverviewGenerationError as exc:
            logger.error("Overview citation validation failed: error_type={}", type(exc).__name__)
            raise OverviewGenerationError("导览生成失败,请刷新重试") from None

        return overview


def parse_location(location: str) -> tuple[str, str]:
    """Parse ``BlockEntry.location`` into ``(model_path, parent)``."""
    parts = location.split(" / ")
    if len(parts) != 2:
        raise OverviewGenerationError("AI 输出 block location 格式错误,请刷新重试")
    model_path = parts[0].strip()
    parent = parts[1].strip()
    if not model_path or not parent:
        raise OverviewGenerationError("AI 输出 block location 格式错误,请刷新重试")
    return model_path, parent


def _validate_file_paths(overview: ProjectOverview, project: Project) -> None:
    project_files = {file_info.relative_path for file_info in project.files}
    slx_files = {
        file_info.relative_path for file_info in project.files if file_info.file_type == ".slx"
    }

    referenced_files: list[str] = []
    referenced_files.extend(item.file_path for item in overview.main_entry_files)
    referenced_files.extend(item.file_path for item in overview.main_simulink_models)
    referenced_files.extend(item.file_path for item in overview.key_files)
    referenced_files.extend(item.file_path for item in overview.evidence)
    if any(file_path not in project_files for file_path in referenced_files):
        raise OverviewGenerationError("AI 输出包含不存在的文件引用,请刷新重试")

    if any(item.file_path not in slx_files for item in overview.main_simulink_models):
        raise OverviewGenerationError("AI 输出包含不存在的 Simulink 模型引用,请刷新重试")


def _validate_block_entries(blocks: list[BlockEntry], project: Project) -> None:
    slx_file_paths = {
        file_info.relative_path for file_info in project.files if file_info.file_type == ".slx"
    }
    rel_by_basename = {
        PurePath(relative_path).name: relative_path for relative_path in slx_file_paths
    }

    known_blocks = set()
    for model in project.slx_models:
        model_basename = PurePath(model.file_path).name
        model_relative_path = rel_by_basename.get(model_basename, model.file_path)
        for slx_block in model.blocks:
            known_blocks.add(
                (
                    model_relative_path,
                    slx_block.name,
                    slx_block.block_type,
                    slx_block.parent_subsystem or "<root>",
                )
            )

    for entry in blocks:
        model_path, parent = parse_location(entry.location)
        key = (model_path, entry.block_name, entry.block_type, parent)
        if key not in known_blocks:
            raise OverviewGenerationError("AI 输出包含不存在的 block 引用,请刷新重试")


def _validate_evidence(overview: ProjectOverview, project: Project) -> None:
    known_block_ids = {block.block_id for model in project.slx_models for block in model.blocks}
    for ref in overview.evidence:
        if ref.block_id is not None and ref.block_id not in known_block_ids:
            raise OverviewGenerationError("AI 输出包含不存在的 block_id 引用,请刷新重试")
        if ref.line_range is None:
            continue
        start, end = ref.line_range
        if start < 1 or end < start:
            raise OverviewGenerationError("AI 输出包含非法行号引用,请刷新重试")
