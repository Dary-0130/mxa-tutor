"""PaperSpec extraction service."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from adapters.parser._sandbox import run_in_sandbox
from core.domain.exceptions import DocumentParseError, PaperSpecGenerationError
from core.domain.paper_document_identity import DEFAULT_DOCUMENT_ID
from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_parameter_conflicts import with_parameter_conflicts
from core.domain.paper_spec import PaperSpec
from core.interfaces.document_parser import DocumentParserRouter, ParsedDocument
from core.interfaces.llm_provider import LLMResponse, TextProvider
from features.paper.paper_schemas import PaperSpecModel
from features.paper.structured_retry import (
    REASON_CALL_CAP_EXCEEDED,
    REASON_WALL_CLOCK_CAP_EXCEEDED,
    StructuredRetryContext,
    StructuredRetryLimitExceeded,
    append_retry_hint,
    before_llm_call,
    bind_retry_context,
    current_retry_context,
    set_current_finish_reason,
)

from ._paper_spec_cache import PaperSpecCache
from ._prompt_builder import build_messages
from ._prompt_loader import load_prompt_template
from .paper_document_identity import (
    enrich_single_document_spec_payload,
    sanitize_paper_display_filename,
)

DEFAULT_PAPER_SPEC_TIMEOUT_SECONDS = 60.0
# R6 后置调参,对齐 PaperPlanService 已升 8000 + DeepSeek V3 8192 上限
DEFAULT_PAPER_SPEC_MAX_TOKENS = 16000
MAX_PAPER_RAW_TEXT_CHARS = 150_000
_GENERATION_ERROR_MESSAGE = "PaperSpec 生成失败,请刷新重试"
SPEC_LEAF_NAME = "paper_spec"
SPEC_STRUCTURED_RETRY_EXTRA_ATTEMPTS = 1
EQUATION_REASON_CODES = frozenset({"equation_locator_invalid", "equation_id_outside_whitelist"})
CONTRACT_MISMATCH_REPEAT_COUNT = 3


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
        document_id: str = DEFAULT_DOCUMENT_ID,
    ) -> PaperSpec:
        """Extract a PaperSpec without reading or writing the cache."""
        parsed = await self.parse_uncached(file_path)
        return await self.extract_parsed_uncached(
            parsed,
            paper_id,
            display_filename=sanitize_paper_display_filename(display_filename or file_path.name),
            document_id=document_id,
        )

    async def parse_uncached(self, file_path: Path) -> ParsedDocument:
        """Parse a document file without reading or writing the cache."""
        parser = await asyncio.to_thread(self._document_parser_router.route, file_path)
        return await asyncio.to_thread(run_in_sandbox, parser, file_path)

    async def extract_parsed_uncached(
        self,
        parsed: ParsedDocument,
        paper_id: str,
        display_filename: str | None = None,
        document_id: str = DEFAULT_DOCUMENT_ID,
        retry_context: StructuredRetryContext | None = None,
    ) -> PaperSpec:
        """Extract a PaperSpec from an existing parser output package."""
        token = bind_retry_context(retry_context)
        try:
            return await self._extract_parsed_uncached_with_retries(
                parsed,
                paper_id,
                display_filename=display_filename,
                document_id=document_id,
            )
        finally:
            token.reset()

    async def _extract_parsed_uncached_with_retries(
        self,
        parsed: ParsedDocument,
        paper_id: str,
        display_filename: str | None = None,
        document_id: str = DEFAULT_DOCUMENT_ID,
    ) -> PaperSpec:
        if len(parsed.raw_text) > self._max_raw_text_chars:
            raise DocumentParseError("document_too_long_for_v0_1") from None

        messages = build_messages(parsed)
        template = load_prompt_template()
        logger.info("PaperSpec LLM call: paper_id={} prompt_version={}", paper_id, template.version)
        remaining_structured_retries = SPEC_STRUCTURED_RETRY_EXTRA_ATTEMPTS
        retried = False
        while True:
            try:
                before_llm_call(component="spec", leaf=SPEC_LEAF_NAME)
            except StructuredRetryLimitExceeded as exc:
                raise PaperSpecGenerationError(
                    _GENERATION_ERROR_MESSAGE,
                    reason_code=exc.reason_code,
                    leaf=SPEC_LEAF_NAME,
                ) from None
            response = await asyncio.to_thread(
                self._text_provider.chat,
                append_retry_hint(messages, SPEC_LEAF_NAME),
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
            set_current_finish_reason(response.finish_reason)
            try:
                current_context = current_retry_context()
                if current_context is not None:
                    current_context.check_wall_clock()
            except StructuredRetryLimitExceeded as exc:
                raise PaperSpecGenerationError(
                    _GENERATION_ERROR_MESSAGE,
                    reason_code=exc.reason_code,
                    finish_reason=response.finish_reason,
                    leaf=SPEC_LEAF_NAME,
                ) from None
            try:
                spec = self._parse_and_validate(
                    response,
                    parsed,
                    display_filename=display_filename,
                    document_id=document_id,
                )
            except PaperSpecGenerationError as exc:
                exc = _with_spec_error_metadata(exc)
                if self._should_retry_spec(exc, remaining_structured_retries):
                    remaining_structured_retries -= 1
                    retried = True
                    self._record_spec_retry(exc, remaining_structured_retries)
                    continue
                self._record_spec_exhausted(exc)
                raise exc
            if retried:
                context = current_retry_context()
                if context is not None:
                    context.mark_rescued(SPEC_LEAF_NAME)
                logger.info(
                    "paper_structured_retry_rescued component={} leaf={}", "spec", SPEC_LEAF_NAME
                )
            return spec

    def _parse_and_validate(
        self,
        response: LLMResponse,
        parsed: ParsedDocument,
        *,
        display_filename: str | None = None,
        document_id: str = DEFAULT_DOCUMENT_ID,
    ) -> PaperSpec:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            logger.error(
                "PaperSpec JSON parse failed: reason_code={} error_type={} finish_reason={}",
                "invalid_json",
                type(exc).__name__,
                response.finish_reason,
            )
            raise PaperSpecGenerationError(
                _GENERATION_ERROR_MESSAGE,
                reason_code="invalid_json",
                finish_reason=response.finish_reason,
                leaf=SPEC_LEAF_NAME,
            ) from None

        if not isinstance(payload, dict):
            logger.error(
                "PaperSpec schema validation failed: reason_code={} error_type={} "
                "finish_reason={}",
                "schema_validation",
                "payload_not_mapping",
                response.finish_reason,
            )
            raise PaperSpecGenerationError(
                _GENERATION_ERROR_MESSAGE,
                reason_code="schema_validation",
                finish_reason=response.finish_reason,
                leaf=SPEC_LEAF_NAME,
                loc=("root",),
            ) from None

        payload = enrich_single_document_spec_payload(
            payload,
            display_filename=display_filename,
            document_id=document_id,
        )
        try:
            spec = PaperSpecModel.model_validate(payload).to_domain()
        except ValidationError as exc:
            logger.error(
                "PaperSpec schema validation failed: reason_code={} error_type={} "
                "finish_reason={}",
                "schema_validation",
                type(exc).__name__,
                response.finish_reason,
            )
            raise PaperSpecGenerationError(
                _GENERATION_ERROR_MESSAGE,
                reason_code="schema_validation",
                finish_reason=response.finish_reason,
                leaf=SPEC_LEAF_NAME,
                loc=_validation_loc(exc),
            ) from None

        try:
            _validate_figure_references(spec, parsed)
            _validate_locator_whitelist(spec, parsed)
            _validate_task501_sources(spec)
        except PaperSpecGenerationError as exc:
            reason_code = exc.reason_code or "post_validation"
            logger.error(
                "PaperSpec post validation failed: reason_code={} error_type={} "
                "finish_reason={}",
                reason_code,
                "post_validation",
                response.finish_reason,
            )
            raise PaperSpecGenerationError(
                _GENERATION_ERROR_MESSAGE,
                reason_code=reason_code,
                finish_reason=response.finish_reason,
                leaf=SPEC_LEAF_NAME,
                locator_namespace=exc.locator_namespace,
                loc=exc.loc,
            ) from None

        return with_parameter_conflicts(spec)

    def _should_retry_spec(
        self,
        exc: PaperSpecGenerationError,
        remaining_structured_retries: int,
    ) -> bool:
        context = current_retry_context()
        repeat_count = (
            context.record_failure(
                leaf=SPEC_LEAF_NAME,
                reason_code=exc.reason_code,
                locator_namespace=exc.locator_namespace,
                loc=exc.loc,
            )
            if context is not None
            else 1
        )
        if exc.finish_reason == "length":
            self._log_spec_retry_decision("non_retryable", exc, remaining_structured_retries)
            return False
        if exc.reason_code in {REASON_CALL_CAP_EXCEEDED, REASON_WALL_CLOCK_CAP_EXCEEDED}:
            self._log_spec_retry_decision("non_retryable", exc, remaining_structured_retries)
            return False
        if repeat_count >= CONTRACT_MISMATCH_REPEAT_COUNT:
            event = (
                "equation_locator_invalid_repeated"
                if exc.reason_code in EQUATION_REASON_CODES
                else "schema_contract_mismatch_suspected"
            )
            logger.warning(
                "paper_structured_retry_early_stop component={} leaf={} event={} "
                "reason_code={} repeat_count={}",
                "spec",
                SPEC_LEAF_NAME,
                event,
                exc.reason_code,
                repeat_count,
            )
            return False
        return remaining_structured_retries > 0

    def _record_spec_retry(
        self,
        exc: PaperSpecGenerationError,
        remaining_structured_retries: int,
    ) -> None:
        context = current_retry_context()
        if context is not None:
            context.set_retry_hint(
                leaf=SPEC_LEAF_NAME,
                reason_code=exc.reason_code,
                loc=exc.loc,
            )
        self._log_spec_retry_decision("attempt", exc, remaining_structured_retries)

    def _record_spec_exhausted(self, exc: PaperSpecGenerationError) -> None:
        self._log_spec_retry_decision("exhausted", exc, 0)
        if exc.reason_code in EQUATION_REASON_CODES:
            logger.warning(
                "paper_structured_retry_equation_exhausted component={} leaf={} reason_code={}",
                "spec",
                SPEC_LEAF_NAME,
                exc.reason_code,
            )

    def _log_spec_retry_decision(
        self,
        event: str,
        exc: PaperSpecGenerationError,
        remaining_structured_retries: int,
    ) -> None:
        logger.info(
            "paper_structured_retry_decision component={} leaf={} event={} reason_code={} "
            "finish_reason={} remaining={} schema_subtype={}",
            "spec",
            SPEC_LEAF_NAME,
            event,
            exc.reason_code,
            exc.finish_reason,
            remaining_structured_retries,
            _schema_subtype(exc.reason_code, exc.loc),
        )


def _validate_figure_references(spec: PaperSpec, parsed: ParsedDocument) -> None:
    allowed_figures = {figure.figure_id for figure in parsed.figure_placeholders}
    if not allowed_figures and spec.figure_locations:
        raise PaperSpecGenerationError("figure_hallucination", reason_code="figure_hallucination")
    if any(figure.figure_id not in allowed_figures for figure in spec.figure_locations):
        raise PaperSpecGenerationError("figure_hallucination", reason_code="figure_hallucination")


def _validate_locator_whitelist(spec: PaperSpec, parsed: ParsedDocument) -> None:
    section_ids = set(parsed.locator_index.section_ids)
    equation_ids = set(parsed.locator_index.equation_ids)
    figure_ids = set(parsed.locator_index.figure_ids)
    equation_seen: set[str] = set()

    for evidence in spec.evidence:
        if not _locator_allowed(evidence.paper_section_id, section_ids):
            raise PaperSpecGenerationError(
                "paper_section_locator_invalid",
                reason_code="paper_section_locator_invalid",
                locator_namespace="paper_section_id",
            )
        if not _locator_allowed(evidence.equation_id, equation_ids):
            raise PaperSpecGenerationError(
                "equation_locator_invalid",
                reason_code="equation_locator_invalid",
                locator_namespace="equation_id",
            )
        if not _locator_allowed(evidence.figure_id, figure_ids):
            raise PaperSpecGenerationError(
                "figure_locator_invalid",
                reason_code="figure_locator_invalid",
                locator_namespace="figure_id",
            )

    for equation in spec.equations:
        if equation.equation_id in equation_seen or equation.equation_id not in equation_ids:
            raise PaperSpecGenerationError(
                "equation_locator_invalid",
                reason_code="equation_locator_invalid",
                locator_namespace="equation_id",
            )
        equation_seen.add(equation.equation_id)
        if equation.paper_section_id not in section_ids:
            raise PaperSpecGenerationError(
                "paper_section_locator_invalid",
                reason_code="paper_section_locator_invalid",
                locator_namespace="paper_section_id",
            )

    for figure in spec.figure_locations:
        if figure.figure_id not in figure_ids or figure.paper_section_id not in section_ids:
            raise PaperSpecGenerationError(
                "figure_locator_invalid",
                reason_code="figure_locator_invalid",
                locator_namespace="figure_id",
            )


def _validate_task501_sources(spec: PaperSpec) -> None:
    if any(
        parameter.source is not EvidenceSource.DOCUMENT_EXTRACTED
        for parameter in spec.parameter_table
    ):
        raise PaperSpecGenerationError(
            "parameter_source_invalid", reason_code="parameter_source_invalid"
        )
    if any(evidence.source is not EvidenceSource.DOCUMENT_EXTRACTED for evidence in spec.evidence):
        raise PaperSpecGenerationError(
            "evidence_source_invalid", reason_code="evidence_source_invalid"
        )


def _locator_allowed(value: str | None, allowed: set[str]) -> bool:
    return value is None or value in allowed


def _with_spec_error_metadata(exc: PaperSpecGenerationError) -> PaperSpecGenerationError:
    if exc.leaf is None:
        exc.leaf = SPEC_LEAF_NAME
    if exc.locator_namespace is None:
        exc.locator_namespace = _locator_namespace_for_reason(exc.reason_code)
    return exc


def _validation_loc(exc: ValidationError) -> tuple[str, ...] | None:
    errors = exc.errors(include_url=False, include_context=False, include_input=False)
    if not errors:
        return None
    loc = errors[0].get("loc")
    if not isinstance(loc, tuple):
        return None
    return tuple(str(part) for part in loc)


def _locator_namespace_for_reason(reason_code: str | None) -> str | None:
    if reason_code in {"equation_locator_invalid", "equation_id_outside_whitelist"}:
        return "equation_id"
    if reason_code in {"paper_section_locator_invalid", "paper_section_id_outside_whitelist"}:
        return "paper_section_id"
    if reason_code in {"figure_locator_invalid", "figure_id_outside_whitelist"}:
        return "figure_id"
    return None


def _schema_subtype(reason_code: str | None, loc: tuple[str, ...] | None) -> str | None:
    if reason_code != "schema_validation":
        return None
    loc_parts = set(loc or ())
    if loc_parts & {"evidence", "paper_reference", "source_ref"}:
        return "schema_evidence_invalid"
    if loc_parts & {"equations", "figure_locations", "parameter_table"}:
        return "schema_cardinality_invalid"
    return "schema_shape_invalid"
