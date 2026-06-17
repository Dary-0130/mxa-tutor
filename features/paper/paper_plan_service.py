"""DAG orchestration for paper-to-model plan generation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any, NoReturn

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import BlockRecommendation, ModelGenerationPlan
from core.domain.paper_spec import PaperSpec
from core.interfaces.document_parser import FigurePlaceholder
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_builder import (
    build_messages_for_missing_detect,
    build_messages_for_mscript_draft,
    build_messages_for_plan_compose,
    build_messages_for_subsystem_plan,
)
from features.paper.paper_plan_helpers import EvidenceTagger, MissingBindingModel, PlanAssembler
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    MissingParameterPromptModel,
    PaperEvidenceEntryModel,
    ParameterMappingModel,
)

logger = logging.getLogger(__name__)

DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS = 120.0
DEFAULT_PAPER_PLAN_MAX_TOKENS = 4000


class PaperPlanService:
    """Generate ModelGenerationPlan with a three-role parallel LLM DAG."""

    def __init__(
        self,
        text_provider: TextProvider,
        evidence_tagger: EvidenceTagger | None = None,
        plan_assembler: PlanAssembler | None = None,
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,
    ) -> None:
        self._text_provider = text_provider
        self._evidence_tagger = evidence_tagger or EvidenceTagger()
        self._plan_assembler = plan_assembler or PlanAssembler()
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        plan_id = f"PLAN-{paper_id}"
        paper_spec_id = paper_id

        missing_prompts, plan_composer_output, mscript = await asyncio.gather(
            self._llm_missing_detect(spec),
            self._llm_plan_compose(spec, plan_id, paper_spec_id),
            self._llm_mscript_draft(spec),
        )
        subsystem_steps = await self._llm_subsystem_plan(
            plan_composer_output.block_recommendations,
            spec.evidence,
        )

        assembled_plan, missing_bindings = self._plan_assembler.merge(
            plan_composer_output=plan_composer_output,
            subsystem_steps=subsystem_steps,
            mscript=mscript,
            missing_prompts=missing_prompts,
            paper_id=paper_id,
        )

        self._evidence_tagger.validate_for_spec(assembled_plan.evidence, spec)
        self._evidence_tagger.validate_for_spec(
            [block.paper_reference for block in assembled_plan.block_recommendations],
            spec,
        )
        self._evidence_tagger.validate_for_spec(
            [prompt.paper_reference for prompt in missing_prompts],
            spec,
        )
        return assembled_plan, missing_prompts, missing_bindings

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        """Call the sync TextProvider behind the single thread bridge."""
        try:
            response = await asyncio.to_thread(
                self._text_provider.chat,
                messages,
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
            response_text = vars(response)["text"]
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "paper_plan_json_decode_failed role=%s exc_type=%s",
                role_name,
                type(exc).__name__,
            )
            raise PaperPlanGenerationError(f"role={role_name}: invalid_json") from None

        if not isinstance(payload, dict):
            self._raise_generation_error(role_name, "json_top_level_must_be_object")
        return payload

    async def _llm_missing_detect(self, spec: PaperSpec) -> list[MissingParameterPrompt]:
        role_name = "missing_detector"
        messages = build_messages_for_missing_detect(
            spec,
            [
                FigurePlaceholder(
                    figure_id=figure.figure_id,
                    caption=figure.caption,
                    paper_section_id=figure.paper_section_id,
                )
                for figure in spec.figure_locations
            ],
        )
        data = await self._call_llm_json(messages, role_name)
        prompts_payload = self._require_list_field(data, "missing_prompts", role_name)
        try:
            prompts = [
                MissingParameterPromptModel.model_validate(item).to_domain()
                for item in prompts_payload
            ]
        except ValidationError as exc:
            self._raise_validation_error(role_name, exc)

        for prompt in prompts:
            if prompt.source is not EvidenceSource.USER_SUPPLIED:
                self._raise_generation_error(role_name, "source_must_be_user_supplied")
            if prompt.paper_reference.source is not EvidenceSource.DOCUMENT_EXTRACTED:
                self._raise_generation_error(
                    role_name,
                    "paper_reference_must_be_document_extracted",
                )
        self._evidence_tagger.validate_for_spec(
            [prompt.paper_reference for prompt in prompts],
            spec,
        )
        return prompts

    async def _llm_plan_compose(
        self,
        spec: PaperSpec,
        plan_id: str,
        paper_spec_id: str,
    ) -> ModelGenerationPlan:
        role_name = "plan_composer"
        data = await self._call_llm_json(
            build_messages_for_plan_compose(spec, plan_id, paper_spec_id),
            role_name,
        )
        if data.get("subsystem_breakdown") != []:
            self._raise_generation_error(role_name, "subsystem_breakdown_must_be_empty")
        if "m_script_skeleton" not in data or data.get("m_script_skeleton") is not None:
            self._raise_generation_error(role_name, "m_script_skeleton_must_be_null")

        data = dict(data)
        if data.get("plan_id") != plan_id or data.get("paper_spec_id") != paper_spec_id:
            logger.warning(
                "paper_plan_ids_overridden role=%s expected_plan_id=%s expected_paper_spec_id=%s",
                role_name,
                plan_id,
                paper_spec_id,
            )
            data["plan_id"] = plan_id
            data["paper_spec_id"] = paper_spec_id

        try:
            model = _PlanComposerOutputModel.model_validate(data)
        except ValidationError as exc:
            self._raise_validation_error(role_name, exc)
        return model.to_domain()

    async def _llm_subsystem_plan(
        self,
        block_recommendations: list[BlockRecommendation],
        evidence: list[PaperEvidenceEntry],
    ) -> list[str]:
        role_name = "subsystem_planner"
        data = await self._call_llm_json(
            build_messages_for_subsystem_plan(block_recommendations, evidence),
            role_name,
        )
        steps = self._require_list_field(data, "subsystem_breakdown", role_name)
        if len(steps) < 3 or len(steps) > 10:
            self._raise_generation_error(role_name, "subsystem_breakdown_length_invalid")
        if not all(isinstance(step, str) and step.strip() for step in steps):
            self._raise_generation_error(role_name, "subsystem_breakdown_item_invalid")
        return steps

    async def _llm_mscript_draft(self, spec: PaperSpec) -> str | None:
        role_name = "mscript_drafter"
        data = await self._call_llm_json(
            build_messages_for_mscript_draft(spec.equations, spec.parameter_table),
            role_name,
        )
        if "m_script_skeleton" not in data:
            self._raise_generation_error(role_name, "m_script_skeleton_missing")
        mscript = data["m_script_skeleton"]
        if mscript is not None and not isinstance(mscript, str):
            self._raise_generation_error(role_name, "m_script_skeleton_invalid")
        return mscript

    def _require_list_field(
        self,
        data: dict[str, Any],
        field_name: str,
        role_name: str,
    ) -> list[Any]:
        value = data.get(field_name)
        if not isinstance(value, list):
            self._raise_generation_error(role_name, f"{field_name}_must_be_array")
        return value

    def _raise_validation_error(self, role_name: str, exc: ValidationError) -> NoReturn:
        logger.error(
            "paper_plan_validation_failed role=%s exc_type=%s",
            role_name,
            type(exc).__name__,
        )
        raise PaperPlanGenerationError(f"role={role_name}: validation_failed") from None

    def _raise_generation_error(self, role_name: str, reason: str) -> NoReturn:
        logger.error("paper_plan_generation_failed role=%s reason=%s", role_name, reason)
        raise PaperPlanGenerationError(f"role={role_name}: {reason}") from None


class _PlanComposerOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    paper_spec_id: str = Field(min_length=1)
    library_choice: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    block_recommendations: list[BlockRecommendationModel] = Field(default_factory=list)
    parameter_mapping: list[ParameterMappingModel] = Field(default_factory=list)
    subsystem_breakdown: list[str] = Field(default_factory=list)
    m_script_skeleton: str | None = None
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)

    def to_domain(self) -> ModelGenerationPlan:
        return ModelGenerationPlan(
            plan_id=self.plan_id,
            paper_spec_id=self.paper_spec_id,
            library_choice=self.library_choice,
            block_recommendations=[
                block_recommendation.to_domain()
                for block_recommendation in self.block_recommendations
            ],
            parameter_mapping=[parameter.to_domain() for parameter in self.parameter_mapping],
            subsystem_breakdown=list(self.subsystem_breakdown),
            m_script_skeleton=self.m_script_skeleton,
            evidence=[entry.to_domain() for entry in self.evidence],
        )
