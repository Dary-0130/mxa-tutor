"""TuningSuggestion use case for persisted paper plan records."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, NoReturn

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.domain.exceptions import PaperPlanGenerationError, PaperTuningError
from core.domain.paper_plan import PaperPlanRecord, ParameterMapping
from core.domain.paper_tuning import ConfidenceValue, TuningSuggestion
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_builder import build_messages_for_tuning_suggest
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
)
from features.paper.paper_schemas import (
    PaperEvidenceEntryModel,
    ParameterDirectionModel,
    TuningSuggestionModel,
)

TUNING_DISCLAIMER = "建议需用户在 MATLAB 中验证"
DEFAULT_TUNING_TIMEOUT_SECONDS = 60.0
DEFAULT_TUNING_MAX_TOKENS = 2000


class TuningSuggestionService:
    """Generate one non-persisted tuning suggestion from a ready paper plan."""

    def __init__(
        self,
        text_provider: TextProvider,
        evidence_tagger: EvidenceTagger | None = None,
        timeout: float = DEFAULT_TUNING_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_TUNING_MAX_TOKENS,
    ) -> None:
        self._text_provider = text_provider
        self._evidence_tagger = evidence_tagger or EvidenceTagger()
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def suggest(self, record: PaperPlanRecord, user_scenario: str) -> TuningSuggestion:
        """Return a validated tuning suggestion for ``user_scenario``."""
        data = await self._call_llm_json(
            build_messages_for_tuning_suggest(record, user_scenario),
        )
        try:
            output = _TuningSuggestionOutputModel.model_validate(data)
        except ValidationError as exc:
            self._raise_tuning_error("llm_output_validation_failed", exc)

        suggestion = TuningSuggestion(
            suggestion_id=f"TUNE-{record.paper_id}-{uuid.uuid4()}",
            user_scenario=user_scenario,
            parameter_directions=[
                parameter_direction.to_domain()
                for parameter_direction in output.parameter_directions
            ],
            expected_effect=output.expected_effect,
            confidence=output.confidence,
            evidence=[entry.to_domain() for entry in output.evidence],
            disclaimer=TUNING_DISCLAIMER,
        )

        self._validate_parameter_directions(suggestion, record)
        try:
            self._evidence_tagger.validate_for_record(suggestion.evidence, record)
        except PaperPlanGenerationError as exc:
            self._raise_tuning_error("evidence_invalid", exc)

        try:
            return TuningSuggestionModel.from_domain(suggestion).to_domain()
        except ValidationError as exc:
            self._raise_tuning_error("public_contract_validation_failed", exc)

    async def _call_llm_json(self, messages: list[LLMMessage]) -> dict[str, Any]:
        """Call the sync TextProvider behind the single thread bridge."""
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        try:
            payload = json.loads(vars(response)["text"])
        except json.JSONDecodeError as exc:
            self._raise_tuning_error("invalid_json", exc)

        if not isinstance(payload, dict):
            logger.error("paper_tuning_generation_failed reason={}", "json_top_level_not_object")
            raise PaperTuningError("json_top_level_not_object") from None
        return payload

    def _validate_parameter_directions(
        self,
        suggestion: TuningSuggestion,
        record: PaperPlanRecord,
    ) -> None:
        mappings_by_name: dict[str, ParameterMapping] = {
            mapping.paper_param_name: mapping for mapping in record.plan.parameter_mapping
        }
        for direction in suggestion.parameter_directions:
            mapping = mappings_by_name.get(direction.param_name)
            if mapping is None:
                logger.error("paper_tuning_generation_failed reason={}", "param_name_unknown")
                raise PaperTuningError("param_name_unknown") from None
            if mapping.value == MISSING_VALUE_SENTINEL:
                logger.error("paper_tuning_generation_failed reason={}", "param_name_unresolved")
                raise PaperTuningError("param_name_unresolved") from None

    def _raise_tuning_error(self, reason: str, exc: Exception) -> NoReturn:
        logger.error(
            "paper_tuning_generation_failed reason={} exception={}",
            reason,
            type(exc).__name__,
        )
        raise PaperTuningError(reason) from None


class _TuningSuggestionOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter_directions: list[ParameterDirectionModel] = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    confidence: ConfidenceValue
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)
