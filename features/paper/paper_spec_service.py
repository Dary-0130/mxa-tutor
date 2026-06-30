"""PaperSpec extraction service."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from adapters.parser._sandbox import run_in_sandbox
from core.domain.exceptions import DocumentParseError, PaperSpecGenerationError
from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_spec import PaperSpec
from core.interfaces.document_parser import DocumentParserRouter, ParsedDocument
from core.interfaces.llm_provider import LLMResponse, TextProvider
from features.paper.paper_schemas import PaperSpecModel

from ._paper_spec_cache import PaperSpecCache
from ._prompt_builder import build_messages
from ._prompt_loader import load_prompt_template
from .paper_document_identity import (
    enrich_single_document_spec_payload,
    sanitize_paper_display_filename,
)

DEFAULT_PAPER_SPEC_TIMEOUT_SECONDS = 60.0
# R6 后置调参,对齐 PaperPlanService 已升 8000 + DeepSeek V3 8192 上限
DEFAULT_PAPER_SPEC_MAX_TOKENS = 8000
MAX_PAPER_RAW_TEXT_CHARS = 80_000
_GENERATION_ERROR_MESSAGE = "PaperSpec 生成失败,请刷新重试"


class PaperSpecService:
    """Generate and cache PaperSpec values from uploaded papers."""

    def __init__(
        self,
        cache: PaperSpecCache,
        text_provider: TextProvider,
        document_parser_router: DocumentParserRouter,
        timeout: float = DEFAULT_PAPER_SPEC_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_SPEC_MAX_TOKENS,
        max_raw_text_chars: int = MAX_PAPER_RAW_TEXT_CHARS,
    ) -> None:
        self._cache = cache
        self._text_provider = text_provider
        self._document_parser_router = document_parser_router
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._max_raw_text_chars = max_raw_text_chars

    async def extract(self, file_path: Path, paper_id: str) -> PaperSpec:
        """Return cached PaperSpec or extract one from ``file_path``."""
        cached = await self._cache.get(paper_id)
        if cached is not None:
            logger.info("PaperSpec cache hit: paper_id={}", paper_id)
            return cached

        spec = await self.extract_uncached(
            file_path,
            paper_id,
            display_filename=file_path.name,
        )
        await self._cache.put(paper_id, spec)
        return spec

    async def extract_uncached(
        self,
        file_path: Path,
        paper_id: str,
        display_filename: str | None = None,
    ) -> PaperSpec:
        """Extract a PaperSpec without reading or writing the cache."""
        parser = await asyncio.to_thread(self._document_parser_router.route, file_path)
        parsed = await asyncio.to_thread(run_in_sandbox, parser, file_path)
        if len(parsed.raw_text) > self._max_raw_text_chars:
            raise DocumentParseError("document_too_long_for_v0_1") from None

        messages = build_messages(parsed)
        template = load_prompt_template()
        logger.info("PaperSpec LLM call: paper_id={} prompt_version={}", paper_id, template.version)
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        return self._parse_and_validate(
            response,
            parsed,
            display_filename=sanitize_paper_display_filename(display_filename or file_path.name),
        )

    def _parse_and_validate(
        self,
        response: LLMResponse,
        parsed: ParsedDocument,
        *,
        display_filename: str | None = None,
    ) -> PaperSpec:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            logger.error("PaperSpec JSON parse failed: error_type={}", type(exc).__name__)
            raise PaperSpecGenerationError(_GENERATION_ERROR_MESSAGE) from None

        if not isinstance(payload, dict):
            logger.error("PaperSpec schema validation failed: error_type=payload_not_mapping")
            raise PaperSpecGenerationError(_GENERATION_ERROR_MESSAGE) from None

        payload = enrich_single_document_spec_payload(
            payload,
            display_filename=display_filename,
        )
        try:
            spec = PaperSpecModel.model_validate(payload).to_domain()
        except ValidationError as exc:
            logger.error("PaperSpec schema validation failed: error_type={}", type(exc).__name__)
            raise PaperSpecGenerationError(_GENERATION_ERROR_MESSAGE) from None

        try:
            _validate_figure_references(spec, parsed)
            _validate_locator_whitelist(spec, parsed)
            _validate_task501_sources(spec)
        except PaperSpecGenerationError:
            logger.error("PaperSpec post validation failed: error_type=post_validation")
            raise PaperSpecGenerationError(_GENERATION_ERROR_MESSAGE) from None

        return spec


def _validate_figure_references(spec: PaperSpec, parsed: ParsedDocument) -> None:
    allowed_figures = {figure.figure_id for figure in parsed.figure_placeholders}
    if not allowed_figures and spec.figure_locations:
        raise PaperSpecGenerationError("figure_hallucination")
    if any(figure.figure_id not in allowed_figures for figure in spec.figure_locations):
        raise PaperSpecGenerationError("figure_hallucination")


def _validate_locator_whitelist(spec: PaperSpec, parsed: ParsedDocument) -> None:
    section_ids = set(parsed.locator_index.section_ids)
    equation_ids = set(parsed.locator_index.equation_ids)
    figure_ids = set(parsed.locator_index.figure_ids)
    equation_seen: set[str] = set()

    for evidence in spec.evidence:
        if not _locator_allowed(evidence.paper_section_id, section_ids):
            raise PaperSpecGenerationError("paper_section_locator_invalid")
        if not _locator_allowed(evidence.equation_id, equation_ids):
            raise PaperSpecGenerationError("equation_locator_invalid")
        if not _locator_allowed(evidence.figure_id, figure_ids):
            raise PaperSpecGenerationError("figure_locator_invalid")

    for equation in spec.equations:
        if equation.equation_id in equation_seen or equation.equation_id not in equation_ids:
            raise PaperSpecGenerationError("equation_locator_invalid")
        equation_seen.add(equation.equation_id)
        if equation.paper_section_id not in section_ids:
            raise PaperSpecGenerationError("paper_section_locator_invalid")

    for figure in spec.figure_locations:
        if figure.figure_id not in figure_ids or figure.paper_section_id not in section_ids:
            raise PaperSpecGenerationError("figure_locator_invalid")


def _validate_task501_sources(spec: PaperSpec) -> None:
    if any(
        parameter.source is not EvidenceSource.DOCUMENT_EXTRACTED
        for parameter in spec.parameter_table
    ):
        raise PaperSpecGenerationError("parameter_source_invalid")
    if any(evidence.source is not EvidenceSource.DOCUMENT_EXTRACTED for evidence in spec.evidence):
        raise PaperSpecGenerationError("evidence_source_invalid")


def _locator_allowed(value: str | None, allowed: set[str]) -> bool:
    return value is None or value in allowed
