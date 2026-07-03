"""DAG orchestration for paper-to-model plan generation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from typing import Annotated, Any, Literal, NoReturn

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_conflicts import (
    mscript_assigns_conflict_value,
    validate_parameter_conflicts_materialized,
    without_conflicted_parameter_entries,
)
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import PaperSpec
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_builder import (
    build_messages_for_build_steps,
    build_messages_for_missing_detect,
    build_messages_for_mscript_draft,
    build_messages_for_mscript_draft_from_mapping,
    build_messages_for_plan_compose,
    build_messages_for_regenerate_build_steps,
    build_messages_for_subsystem_plan,
)
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    BuildStepsDtoValidationError,
    BuildStepsJsonParseError,
    BuildStepsStructuredError,
    EvidenceTagger,
    MissingBindingModel,
    ModelBuildStepDraft,
    PlanAssembler,
    UserEvidenceRef,
    apply_plan_evidence_reference_bridge,
    build_plan_evidence_source_refs,
    validate_build_step_evidence_for_spec,
)
from features.paper.paper_plan_integrity import validate_plan_does_not_resolve_conflicts
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    ConfigurationHintModel,
    ConnectionHintModel,
    PaperEvidenceEntryModel,
    ParameterMappingModel,
    ParameterMappingRefModel,
    StepBlockRefModel,
)

logger = logging.getLogger(__name__)

DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS = 120.0
DEFAULT_PAPER_PLAN_MAX_TOKENS = 8000  # R6 真启动调参,对齐 DeepSeek V3 8192 上限
BUILD_STEP_ROLE_NAME = "build_step_planner"
BUILD_STEP_REGENERATION_ROLE_NAME = "build_step_regenerator"
BUILD_STEP_ROLE_NAMES = frozenset({BUILD_STEP_ROLE_NAME, BUILD_STEP_REGENERATION_ROLE_NAME})


class PaperPlanService:
    """Generate ModelGenerationPlan with a four-call parallel LLM DAG plus fallback."""

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
        try:
            validate_parameter_conflicts_materialized(spec)
        except ValueError:
            raise PaperPlanGenerationError("parameter_conflicts_mismatch") from None

        plan_composer_output, mscript = await asyncio.gather(
            self._llm_plan_compose(spec, plan_id, paper_spec_id),
            self._llm_mscript_draft(spec),
        )
        sentinel_mappings = self._sentinel_mappings(plan_composer_output.parameter_mapping)
        missing_result, build_steps_result = await asyncio.gather(
            self._llm_missing_detect(spec, paper_id, sentinel_mappings),
            self._llm_build_steps(
                plan_composer_output.block_recommendations,
                plan_composer_output.parameter_mapping,
                spec,
            ),
            return_exceptions=True,
        )
        if isinstance(missing_result, BaseException):
            raise missing_result
        missing_prompts = missing_result

        build_steps: list[ModelBuildStep] | None
        try:
            if isinstance(build_steps_result, BuildStepsStructuredError):
                raise build_steps_result
            if isinstance(build_steps_result, BaseException):
                raise build_steps_result
            build_steps = self._plan_assembler.validate_and_derive_build_steps(
                build_steps_result,
                plan_composer_output.parameter_mapping,
                plan_composer_output.block_recommendations,
            )
            self._validate_build_step_evidence(build_steps, spec)
            subsystem_steps = [step.display_text for step in build_steps]
        except BuildStepsStructuredError as exc:
            self._log_build_steps_fallback(exc)
            build_steps = None
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
            build_steps=build_steps,
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
        validate_plan_does_not_resolve_conflicts(assembled_plan, spec.parameter_conflicts)
        return assembled_plan, missing_prompts, missing_bindings

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        """Call the sync TextProvider behind the single thread bridge."""
        last_json_error: json.JSONDecodeError | None = None
        payload: Any = None
        for attempt in range(1, 3):
            response = await asyncio.to_thread(
                self._text_provider.chat,
                messages,
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
            response_text = vars(response)["text"]
            try:
                payload = json.loads(response_text)
                break
            except json.JSONDecodeError as exc:
                last_json_error = exc
                logger.error(
                    "paper_plan_json_decode_failed role=%s attempt=%s exc_type=%s",
                    role_name,
                    attempt,
                    type(exc).__name__,
                )
        else:
            assert last_json_error is not None
            logger.error(
                "paper_plan_json_decode_exhausted role=%s exc_type=%s",
                role_name,
                type(last_json_error).__name__,
            )
            if role_name in BUILD_STEP_ROLE_NAMES:
                raise BuildStepsJsonParseError("json_parse_failed") from None
            raise PaperPlanGenerationError(f"role={role_name}: invalid_json") from None

        if not isinstance(payload, dict):
            if role_name in BUILD_STEP_ROLE_NAMES:
                raise BuildStepsDtoValidationError("json_top_level_must_be_object")
            self._raise_generation_error(role_name, "json_top_level_must_be_object")
        return payload

    async def _llm_missing_detect(
        self,
        spec: PaperSpec,
        paper_id: str,
        sentinel_mappings: list[ParameterMapping],
    ) -> list[MissingParameterPrompt]:
        role_name = "missing_detector"
        messages = build_messages_for_missing_detect(spec, sentinel_mappings)
        data = await self._call_llm_json(messages, role_name)
        source_refs = build_plan_evidence_source_refs(spec)
        data = apply_plan_evidence_reference_bridge(data, source_refs)
        prompts_payload = self._require_list_field(data, "missing_prompts", role_name)
        try:
            drafts = [_MissingPromptDraftModel.model_validate(item) for item in prompts_payload]
        except ValidationError as exc:
            self._raise_validation_error(role_name, exc)

        self._validate_missing_detector_cardinality(drafts, sentinel_mappings, role_name)
        prompts: list[MissingParameterPrompt] = []
        for index, draft in enumerate(drafts, start=1):
            prompts.append(
                MissingParameterPrompt(
                    prompt_id=f"MISS-{index:03d}",
                    parameter_name=draft.parameter_name,
                    paper_reference=draft.paper_reference.to_domain(),
                    suggested_unit=draft.suggested_unit,
                    user_supplied_value=None,
                    user_supplied_unit=None,
                    source=EvidenceSource.USER_SUPPLIED,
                )
            )

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
        source_refs = build_plan_evidence_source_refs(spec)
        data = apply_plan_evidence_reference_bridge(data, source_refs)
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
        plan = model.to_domain()
        self._validate_plan_composer_mappings(plan.parameter_mapping, role_name)
        try:
            validate_plan_does_not_resolve_conflicts(plan, spec.parameter_conflicts)
        except PaperPlanGenerationError:
            self._raise_generation_error(role_name, "parameter_conflict_mapping")
        return plan

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

    async def _llm_build_steps(
        self,
        block_recommendations: list[BlockRecommendation],
        parameter_mapping: list[ParameterMapping],
        spec: PaperSpec,
    ) -> list[ModelBuildStepDraft]:
        data = await self._call_llm_json(
            build_messages_for_build_steps(
                block_recommendations,
                parameter_mapping,
                spec.evidence,
                build_plan_evidence_source_refs(spec),
            ),
            BUILD_STEP_ROLE_NAME,
        )
        source_refs = build_plan_evidence_source_refs(spec)
        data = apply_plan_evidence_reference_bridge(data, source_refs)
        if data.get("build_steps") == []:
            raise BuildStepsDtoValidationError("empty_steps")
        try:
            model = _BuildStepsOutputModel.model_validate(data)
        except ValidationError as exc:
            logger.error(
                "paper_plan_build_steps_dto_failed role=%s exc_type=%s",
                BUILD_STEP_ROLE_NAME,
                type(exc).__name__,
            )
            raise BuildStepsDtoValidationError("dto_invalid") from None
        return model.to_drafts()

    async def _llm_build_steps_for_regeneration(
        self,
        block_recommendations: list[BlockRecommendation],
        parameter_mapping: list[ParameterMapping],
        spec: PaperSpec,
        record_plan_evidence: list[PaperEvidenceEntry],
        allowed_user_evidence_refs: set[UserEvidenceRef],
        allowed_user_prompt_ids: frozenset[str],
    ) -> list[ModelBuildStepDraft]:
        data = await self._call_llm_json(
            build_messages_for_regenerate_build_steps(
                block_recommendations,
                parameter_mapping,
                spec.evidence,
                record_plan_evidence,
                build_plan_evidence_source_refs(spec),
                allowed_user_evidence_refs=allowed_user_evidence_refs,
                allowed_user_prompt_ids=allowed_user_prompt_ids,
            ),
            BUILD_STEP_REGENERATION_ROLE_NAME,
        )
        source_refs = build_plan_evidence_source_refs(spec)
        data = apply_plan_evidence_reference_bridge(data, source_refs)
        if data.get("build_steps") == []:
            raise BuildStepsDtoValidationError("empty_steps")
        try:
            model = _BuildStepsOutputModel.model_validate(data)
        except ValidationError as exc:
            logger.error(
                "paper_plan_build_steps_dto_failed role=%s exc_type=%s",
                BUILD_STEP_REGENERATION_ROLE_NAME,
                type(exc).__name__,
            )
            raise BuildStepsDtoValidationError("dto_invalid") from None
        return model.to_drafts()

    async def _llm_mscript_draft(self, spec: PaperSpec) -> str | None:
        role_name = "mscript_drafter"
        sanitized_spec = without_conflicted_parameter_entries(spec)
        data = await self._call_llm_json(
            build_messages_for_mscript_draft(
                spec.equations,
                sanitized_spec.parameter_table,
                spec.parameter_conflicts,
            ),
            role_name,
        )
        if "m_script_skeleton" not in data:
            self._raise_generation_error(role_name, "m_script_skeleton_missing")
        mscript = data["m_script_skeleton"]
        if mscript is not None and not isinstance(mscript, str):
            self._raise_generation_error(role_name, "m_script_skeleton_invalid")
        if mscript is not None and mscript_assigns_conflict_value(
            mscript, spec.parameter_conflicts
        ):
            self._raise_generation_error(role_name, "parameter_conflict_mscript")
        return mscript

    async def _llm_mscript_draft_from_mapping(
        self,
        parameter_mapping: list[ParameterMapping],
        spec: PaperSpec,
    ) -> str | None:
        role_name = "mscript_drafter_from_mapping"
        data = await self._call_llm_json(
            build_messages_for_mscript_draft_from_mapping(
                spec.equations,
                parameter_mapping,
                spec.parameter_conflicts,
            ),
            role_name,
        )
        if "m_script_skeleton" not in data:
            self._raise_generation_error(role_name, "m_script_skeleton_missing")
        mscript = data["m_script_skeleton"]
        if mscript is not None and not isinstance(mscript, str):
            self._raise_generation_error(role_name, "m_script_skeleton_invalid")
        if mscript is not None and mscript_assigns_conflict_value(
            mscript, spec.parameter_conflicts
        ):
            self._raise_generation_error(role_name, "parameter_conflict_mscript")
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

    def _sentinel_mappings(self, mappings: list[ParameterMapping]) -> list[ParameterMapping]:
        return [mapping for mapping in mappings if mapping.value == MISSING_VALUE_SENTINEL]

    def _validate_plan_composer_mappings(
        self,
        mappings: list[ParameterMapping],
        role_name: str,
    ) -> None:
        name_counts = Counter(mapping.paper_param_name for mapping in mappings)
        if any(count != 1 for count in name_counts.values()):
            self._raise_generation_error(role_name, "paper_param_name_duplicate")
        for mapping in self._sentinel_mappings(mappings):
            if mapping.source is not EvidenceSource.DOCUMENT_EXTRACTED:
                self._raise_generation_error(role_name, "sentinel_source_must_be_document")

    def _validate_missing_detector_cardinality(
        self,
        drafts: list[_MissingPromptDraftModel],
        sentinel_mappings: list[ParameterMapping],
        role_name: str,
    ) -> None:
        sentinel_names = [mapping.paper_param_name for mapping in sentinel_mappings]
        draft_names = [draft.parameter_name for draft in drafts]
        if any(count != 1 for count in Counter(sentinel_names).values()):
            self._raise_generation_error(role_name, "sentinel_parameter_duplicate")
        if any(count != 1 for count in Counter(draft_names).values()):
            self._raise_generation_error(role_name, "missing_prompt_duplicate")
        if len(drafts) != len(sentinel_mappings):
            self._raise_generation_error(role_name, "missing_prompt_cardinality_mismatch")
        for draft_name, sentinel_name in zip(draft_names, sentinel_names, strict=True):
            if draft_name != sentinel_name:
                self._raise_generation_error(role_name, "missing_prompt_parameter_mismatch")

    def _validate_build_step_evidence(
        self,
        build_steps: list[ModelBuildStep],
        spec: PaperSpec,
    ) -> None:
        for step in build_steps:
            validate_build_step_evidence_for_spec(
                step.evidence,
                spec,
                allowed_user_prompt_ids=frozenset(),
            )
            validate_build_step_evidence_for_spec(
                [
                    block_ref.paper_reference
                    for block_ref in step.block_refs
                    if block_ref.paper_reference is not None
                ],
                spec,
                allowed_user_prompt_ids=frozenset(),
            )
            for configuration_hint in step.configuration_hints:
                validate_build_step_evidence_for_spec(
                    configuration_hint.evidence,
                    spec,
                    allowed_user_prompt_ids=frozenset(),
                )

    def _log_build_steps_fallback(self, exc: BuildStepsStructuredError) -> None:
        logger.warning(
            "paper_plan_build_steps_fallback reason_code=%s exc_type=%s",
            exc.reason_code,
            type(exc).__name__,
        )


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


class _MissingPromptDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter_name: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel
    suggested_unit: str | None = Field(default=None, min_length=1)
    source: Literal["user_supplied"] = "user_supplied"


class _ModelBuildStepDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    block_refs: list[StepBlockRefModel]
    parameter_refs: list[ParameterMappingRefModel]
    connection_hints: list[ConnectionHintModel]
    configuration_hints: list[ConfigurationHintModel]
    depends_on: list[str]
    evidence: list[PaperEvidenceEntryModel]

    def to_draft(self) -> ModelBuildStepDraft:
        return ModelBuildStepDraft(
            step_id=self.step_id,
            title=self.title,
            intent=self.intent,
            block_refs=[entry.to_domain() for entry in self.block_refs],
            parameter_refs=[entry.to_domain() for entry in self.parameter_refs],
            connection_hints=[entry.to_domain() for entry in self.connection_hints],
            configuration_hints=[entry.to_domain() for entry in self.configuration_hints],
            depends_on=list(self.depends_on),
            evidence=[entry.to_domain() for entry in self.evidence],
        )


class _BuildStepsOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_steps: list[_ModelBuildStepDraftModel] = Field(min_length=3, max_length=10)

    def to_drafts(self) -> list[ModelBuildStepDraft]:
        return [step.to_draft() for step in self.build_steps]
