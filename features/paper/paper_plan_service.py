"""DAG orchestration for paper-to-model plan generation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from collections.abc import Awaitable
from dataclasses import replace
from typing import Annotated, Any, Literal, NoReturn, cast

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
    StepBlockRef,
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
from features.paper._prompt_loader import load_prompt_template
from features.paper.build_guidance_generator import BuildGuidanceGenerator
from features.paper.build_guidance_observability import guidance_exception_code
from features.paper.build_steps_dependency_audit import (
    DependencyAudit,
    audit_step_dependencies_from_payload,
    build_steps_dependency_audit_enabled,
    prompt_token_bucket,
)
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    PLAN_EVIDENCE_SOURCE_REF_FIELD,
    BuildStepsDtoValidationError,
    BuildStepsJsonParseError,
    BuildStepsStructuredError,
    BuildStepUserEvidenceSourceRef,
    EvidenceTagger,
    MissingBindingModel,
    ModelBuildStepDraft,
    PlanAssembler,
    PlanEvidenceSourceRef,
    UserEvidenceRef,
    apply_plan_evidence_reference_bridge,
    build_plan_evidence_source_refs,
    build_step_user_evidence_source_refs,
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
)
from features.paper.structured_retry import (
    REASON_CALL_CAP_EXCEEDED,
    REASON_WALL_CLOCK_CAP_EXCEEDED,
    StructuredRetryContext,
    StructuredRetryLimitExceeded,
    append_retry_hint,
    before_llm_call,
    bind_retry_context,
    current_finish_reason,
    current_retry_context,
    set_current_finish_reason,
)

logger = logging.getLogger(__name__)

DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS = 120.0
DEFAULT_PAPER_PLAN_MAX_TOKENS = 8000  # R6 真启动调参,对齐 DeepSeek V3 8192 上限
PLAN_COMPOSER_ROLE_NAME = "plan_composer"
MISSING_DETECTOR_ROLE_NAME = "missing_detector"
BUILD_STEP_ROLE_NAME = "build_step_planner"
BUILD_STEP_REGENERATION_ROLE_NAME = "build_step_regenerator"
SUBSYSTEM_PLANNER_ROLE_NAME = "subsystem_planner"
BUILD_STEP_ROLE_NAMES = frozenset({BUILD_STEP_ROLE_NAME, BUILD_STEP_REGENERATION_ROLE_NAME})
BUILD_STEP_DEGRADATION_ROLE_NAMES = frozenset(
    {BUILD_STEP_ROLE_NAME, BUILD_STEP_REGENERATION_ROLE_NAME, SUBSYSTEM_PLANNER_ROLE_NAME}
)
PLAN_STRUCTURED_RETRY_EXTRA_ATTEMPTS = 2
RETRYABLE_PLAN_LEAF_NAMES = frozenset({PLAN_COMPOSER_ROLE_NAME, MISSING_DETECTOR_ROLE_NAME})
EQUATION_REASON_CODES = frozenset({"equation_locator_invalid", "equation_id_outside_whitelist"})
CONTRACT_MISMATCH_REPEAT_COUNT = 3
_UNSET = object()
_MISSING = object()


class PaperPlanService:
    """Generate ModelGenerationPlan with a four-call parallel LLM DAG plus fallback."""

    def __init__(
        self,
        text_provider: TextProvider,
        evidence_tagger: EvidenceTagger | None = None,
        plan_assembler: PlanAssembler | None = None,
        build_guidance_generator: BuildGuidanceGenerator | None = None,
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,
    ) -> None:
        self._text_provider = text_provider
        self._evidence_tagger = evidence_tagger or EvidenceTagger()
        self._plan_assembler = plan_assembler or PlanAssembler()
        self._build_guidance_generator = build_guidance_generator or BuildGuidanceGenerator(
            text_provider,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._last_llm_prompt_tokens_by_role: dict[str, int] = {}
        self._last_build_steps_dependency_audit: DependencyAudit | None = None

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
        retry_context: StructuredRetryContext | None = None,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        token = bind_retry_context(retry_context)
        try:
            return await self._generate_with_retries(spec, paper_id)
        finally:
            token.reset()

    async def _generate_with_retries(
        self,
        spec: PaperSpec,
        paper_id: str,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        plan_id = f"PLAN-{paper_id}"
        paper_spec_id = paper_id
        try:
            validate_parameter_conflicts_materialized(spec)
        except ValueError:
            raise PaperPlanGenerationError(
                "parameter_conflicts_mismatch",
                reason_code="parameter_conflicts_mismatch",
            ) from None
        self._preflight_spec_equation_namespace(spec)

        remaining_structured_retries = PLAN_STRUCTURED_RETRY_EXTRA_ATTEMPTS
        retried_leaves: set[str] = set()
        plan_composer_output: ModelGenerationPlan | None = None
        mscript: str | None = None
        mscript_ready = False

        while plan_composer_output is None:
            if mscript_ready:
                plan_result = await self._capture_plan_leaf(
                    self._llm_plan_compose(spec, plan_id, paper_spec_id),
                    PLAN_COMPOSER_ROLE_NAME,
                )
                mscript_result: str | BaseException | None = mscript
            else:
                plan_result, mscript_result = await asyncio.gather(
                    self._capture_plan_leaf(
                        self._llm_plan_compose(spec, plan_id, paper_spec_id),
                        PLAN_COMPOSER_ROLE_NAME,
                    ),
                    self._llm_mscript_draft(spec),
                    return_exceptions=True,
                )
                if not isinstance(mscript_result, BaseException):
                    mscript = mscript_result
                    mscript_ready = True

            if isinstance(mscript_result, BaseException):
                raise mscript_result
            if isinstance(plan_result, BaseException):
                if self._should_retry_plan_leaf(
                    plan_result,
                    PLAN_COMPOSER_ROLE_NAME,
                    remaining_structured_retries,
                ):
                    remaining_structured_retries -= 1
                    retried_leaves.add(PLAN_COMPOSER_ROLE_NAME)
                    self._record_plan_retry(
                        plan_result,
                        PLAN_COMPOSER_ROLE_NAME,
                        remaining_structured_retries,
                    )
                    continue
                self._record_plan_exhausted(plan_result, PLAN_COMPOSER_ROLE_NAME)
                raise plan_result
            plan_composer_output = cast(ModelGenerationPlan, plan_result)
            self._record_plan_rescue_if_needed(PLAN_COMPOSER_ROLE_NAME, retried_leaves)

        sentinel_mappings = self._sentinel_mappings(plan_composer_output.parameter_mapping)
        build_steps_result: object = _UNSET
        missing_prompts: list[MissingParameterPrompt] | None = None
        while missing_prompts is None:
            if build_steps_result is _UNSET:
                missing_result, build_steps_result = await asyncio.gather(
                    self._capture_plan_leaf(
                        self._llm_missing_detect(spec, paper_id, sentinel_mappings),
                        MISSING_DETECTOR_ROLE_NAME,
                    ),
                    self._llm_build_steps(
                        plan_composer_output.block_recommendations,
                        plan_composer_output.parameter_mapping,
                        spec,
                    ),
                    return_exceptions=True,
                )
            else:
                missing_result = await self._capture_plan_leaf(
                    self._llm_missing_detect(spec, paper_id, sentinel_mappings),
                    MISSING_DETECTOR_ROLE_NAME,
                )
            if isinstance(missing_result, BaseException):
                if self._should_retry_plan_leaf(
                    missing_result,
                    MISSING_DETECTOR_ROLE_NAME,
                    remaining_structured_retries,
                ):
                    remaining_structured_retries -= 1
                    retried_leaves.add(MISSING_DETECTOR_ROLE_NAME)
                    self._record_plan_retry(
                        missing_result,
                        MISSING_DETECTOR_ROLE_NAME,
                        remaining_structured_retries,
                    )
                    continue
                self._record_plan_exhausted(missing_result, MISSING_DETECTOR_ROLE_NAME)
                raise missing_result
            missing_prompts = cast(list[MissingParameterPrompt], missing_result)
            self._record_plan_rescue_if_needed(MISSING_DETECTOR_ROLE_NAME, retried_leaves)

        build_steps: list[ModelBuildStep] | None
        try:
            if isinstance(build_steps_result, BuildStepsStructuredError):
                raise build_steps_result
            if isinstance(build_steps_result, BaseException):
                raise build_steps_result
            if build_steps_result is _UNSET:
                raise PaperPlanGenerationError(
                    "role=build_step_planner: missing_result",
                    reason_code="build_steps_missing_result",
                    leaf=BUILD_STEP_ROLE_NAME,
                )
            build_steps = self._plan_assembler.validate_and_derive_build_steps(
                cast(list[ModelBuildStepDraft], build_steps_result),
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
        assembled_plan = await self._generate_build_guidance(spec, assembled_plan)

        return assembled_plan, missing_prompts, missing_bindings

    async def _generate_build_guidance(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        try:
            return await self._build_guidance_generator.generate(spec, plan)
        except Exception as exc:
            logger.warning(
                "paper_build_guidance_unhandled_fail_closed reason_code=%s exception_code=%s",
                "guidance_generator_exception",
                guidance_exception_code(exc),
            )
            return replace(plan, build_guidance=None, guidance_status="generation_failed")

    async def generate_build_guidance_for_plan(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        """Regenerate only build guidance for an already assembled plan."""

        return await self._generate_build_guidance(spec, plan)

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        """Call the sync TextProvider behind the single thread bridge."""
        last_json_error: json.JSONDecodeError | None = None
        payload: Any = None
        messages = append_retry_hint(messages, role_name)
        enforce_retry_caps = role_name not in BUILD_STEP_DEGRADATION_ROLE_NAMES
        for attempt in range(1, 3):
            if enforce_retry_caps:
                try:
                    before_llm_call(component="plan", leaf=role_name)
                except StructuredRetryLimitExceeded as exc:
                    raise PaperPlanGenerationError(
                        f"role={role_name}: {exc.reason_code}",
                        reason_code=exc.reason_code,
                        leaf=role_name,
                    ) from None
            response = await asyncio.to_thread(
                self._text_provider.chat,
                messages,
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
            self._last_llm_prompt_tokens_by_role[role_name] = response.prompt_tokens
            set_current_finish_reason(response.finish_reason)
            if enforce_retry_caps:
                try:
                    current_context = current_retry_context()
                    if current_context is not None:
                        current_context.check_wall_clock()
                except StructuredRetryLimitExceeded as exc:
                    raise PaperPlanGenerationError(
                        f"role={role_name}: {exc.reason_code}",
                        reason_code=exc.reason_code,
                        finish_reason=response.finish_reason,
                        leaf=role_name,
                    ) from None
            response_text = vars(response)["text"]
            try:
                payload = json.loads(response_text)
                break
            except json.JSONDecodeError as exc:
                last_json_error = exc
                logger.error(
                    "paper_plan_json_decode_failed role=%s attempt=%s reason_code=%s "
                    "exc_type=%s finish_reason=%s",
                    role_name,
                    attempt,
                    "invalid_json",
                    type(exc).__name__,
                    response.finish_reason,
                )
        else:
            assert last_json_error is not None
            logger.error(
                "paper_plan_json_decode_exhausted role=%s reason_code=%s exc_type=%s",
                role_name,
                "invalid_json",
                type(last_json_error).__name__,
            )
            if role_name in BUILD_STEP_ROLE_NAMES:
                raise BuildStepsJsonParseError("json_parse_failed") from None
            raise PaperPlanGenerationError(
                f"role={role_name}: invalid_json",
                reason_code="invalid_json",
                finish_reason=current_finish_reason(),
                leaf=role_name,
            ) from None

        if not isinstance(payload, dict):
            if role_name in BUILD_STEP_ROLE_NAMES:
                raise BuildStepsDtoValidationError("json_top_level_must_be_object")
            self._raise_generation_error(
                role_name,
                "json_top_level_must_be_object",
                reason_code="schema_validation",
            )
        return payload

    async def _llm_missing_detect(
        self,
        spec: PaperSpec,
        paper_id: str,
        sentinel_mappings: list[ParameterMapping],
    ) -> list[MissingParameterPrompt]:
        role_name = MISSING_DETECTOR_ROLE_NAME
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
        role_name = PLAN_COMPOSER_ROLE_NAME
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
        self._evidence_tagger.validate_for_spec(plan.evidence, spec)
        self._evidence_tagger.validate_for_spec(
            [block.paper_reference for block in plan.block_recommendations],
            spec,
        )
        return plan

    async def _llm_subsystem_plan(
        self,
        block_recommendations: list[BlockRecommendation],
        evidence: list[PaperEvidenceEntry],
    ) -> list[str]:
        role_name = SUBSYSTEM_PLANNER_ROLE_NAME
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
        self._clear_build_steps_dependency_audit()
        source_refs = build_plan_evidence_source_refs(spec)
        prompt_version = load_prompt_template("paper_plan_build_steps.yaml").version
        data = await self._call_llm_json(
            build_messages_for_build_steps(
                block_recommendations,
                parameter_mapping,
                spec.evidence,
                source_refs,
            ),
            BUILD_STEP_ROLE_NAME,
        )
        return self._parse_build_steps_output(
            data,
            document_source_refs=source_refs,
            user_source_refs=[],
            role_name=BUILD_STEP_ROLE_NAME,
            evidence_ref_count=len(source_refs),
            block_candidate_count=len(block_recommendations),
            parameter_mapping_count=len(parameter_mapping),
            rendered_prompt_version=prompt_version,
        )

    async def _llm_build_steps_for_regeneration(
        self,
        block_recommendations: list[BlockRecommendation],
        parameter_mapping: list[ParameterMapping],
        spec: PaperSpec,
        record_plan_evidence: list[PaperEvidenceEntry],
        allowed_user_evidence_refs: set[UserEvidenceRef],
        allowed_user_prompt_ids: frozenset[str],
    ) -> list[ModelBuildStepDraft]:
        self._clear_build_steps_dependency_audit()
        source_refs = build_plan_evidence_source_refs(spec)
        user_source_refs = build_step_user_evidence_source_refs(
            record_plan_evidence,
            allowed_user_evidence_refs,
        )
        prompt_version = load_prompt_template("paper_plan_build_steps_regenerate.yaml").version
        data = await self._call_llm_json(
            build_messages_for_regenerate_build_steps(
                block_recommendations,
                parameter_mapping,
                spec.evidence,
                record_plan_evidence,
                source_refs,
                allowed_user_evidence_refs=allowed_user_evidence_refs,
                allowed_user_prompt_ids=allowed_user_prompt_ids,
            ),
            BUILD_STEP_REGENERATION_ROLE_NAME,
        )
        return self._parse_build_steps_output(
            data,
            document_source_refs=source_refs,
            user_source_refs=user_source_refs,
            role_name=BUILD_STEP_REGENERATION_ROLE_NAME,
            evidence_ref_count=len(source_refs) + len(user_source_refs),
            block_candidate_count=len(block_recommendations),
            parameter_mapping_count=len(parameter_mapping),
            rendered_prompt_version=prompt_version,
        )

    def _parse_build_steps_output(
        self,
        data: dict[str, Any],
        *,
        document_source_refs: list[PlanEvidenceSourceRef],
        user_source_refs: list[BuildStepUserEvidenceSourceRef],
        role_name: str,
        evidence_ref_count: int | None = None,
        block_candidate_count: int | None = None,
        parameter_mapping_count: int | None = None,
        rendered_prompt_version: str | None = None,
    ) -> list[ModelBuildStepDraft]:
        raw_data = data
        self._record_build_steps_dependency_audit(
            raw_data,
            role_name=role_name,
            evidence_ref_count=evidence_ref_count,
            block_candidate_count=block_candidate_count,
            parameter_mapping_count=parameter_mapping_count,
            rendered_prompt_version=rendered_prompt_version,
        )
        data = _resolve_build_steps_draft_evidence_payload(
            data,
            document_source_refs=document_source_refs,
            user_source_refs=user_source_refs,
        )
        _log_omitted_build_step_block_reference_count(raw_data, role_name=role_name)
        if data.get("build_steps") == []:
            raise BuildStepsDtoValidationError("empty_steps")
        try:
            model = _BuildStepsOutputModel.model_validate(data)
        except ValidationError as exc:
            self._record_build_steps_dto_validation_errors(exc, role_name=role_name)
            reason_code = _build_steps_final_validation_reason(exc)
            logger.error(
                "paper_plan_build_steps_dto_failed role=%s reason_code=%s exc_type=%s",
                role_name,
                reason_code,
                type(exc).__name__,
            )
            raise BuildStepsDtoValidationError(reason_code) from None
        return model.to_drafts()

    def _record_build_steps_dto_validation_errors(
        self,
        exc: ValidationError,
        *,
        role_name: str,
    ) -> None:
        _ = exc, role_name

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
        loc = _validation_loc(exc)
        logger.error(
            "paper_plan_validation_failed role=%s reason_code=%s exc_type=%s schema_subtype=%s",
            role_name,
            "schema_validation",
            type(exc).__name__,
            _schema_subtype("schema_validation", loc),
        )
        raise PaperPlanGenerationError(
            f"role={role_name}: validation_failed",
            reason_code="schema_validation",
            finish_reason=current_finish_reason(),
            leaf=role_name,
            loc=loc,
        ) from None

    def _raise_generation_error(
        self,
        role_name: str,
        reason: str,
        *,
        reason_code: str | None = None,
    ) -> NoReturn:
        effective_reason_code = reason_code or reason
        logger.error(
            "paper_plan_generation_failed role=%s reason_code=%s",
            role_name,
            effective_reason_code,
        )
        raise PaperPlanGenerationError(
            f"role={role_name}: {reason}",
            reason_code=effective_reason_code,
            finish_reason=current_finish_reason(),
            leaf=role_name,
            locator_namespace=_locator_namespace_for_reason(effective_reason_code),
        ) from None

    async def _capture_plan_leaf(
        self,
        awaitable: Awaitable[object],
        leaf: str,
    ) -> object | BaseException:
        try:
            return await awaitable
        except PaperPlanGenerationError as exc:
            return _with_plan_error_metadata(exc, leaf=leaf)
        except BaseException as exc:
            return exc

    def _should_retry_plan_leaf(
        self,
        exc: BaseException,
        leaf: str,
        remaining_structured_retries: int,
    ) -> bool:
        if not isinstance(exc, PaperPlanGenerationError):
            return False
        exc = _with_plan_error_metadata(exc, leaf=leaf)
        context = current_retry_context()
        repeat_count = (
            context.record_failure(
                leaf=leaf,
                reason_code=exc.reason_code,
                locator_namespace=exc.locator_namespace,
                loc=exc.loc,
            )
            if context is not None
            else 1
        )
        if leaf not in RETRYABLE_PLAN_LEAF_NAMES:
            return False
        if exc.finish_reason == "length":
            self._log_plan_retry_decision("non_retryable", exc, leaf, remaining_structured_retries)
            return False
        if exc.reason_code in {REASON_CALL_CAP_EXCEEDED, REASON_WALL_CLOCK_CAP_EXCEEDED}:
            self._log_plan_retry_decision("non_retryable", exc, leaf, remaining_structured_retries)
            return False
        if repeat_count >= CONTRACT_MISMATCH_REPEAT_COUNT:
            event = (
                "equation_locator_invalid_repeated"
                if exc.reason_code in EQUATION_REASON_CODES
                else "schema_contract_mismatch_suspected"
            )
            logger.warning(
                "paper_structured_retry_early_stop component=%s leaf=%s event=%s "
                "reason_code=%s repeat_count=%s",
                "plan",
                leaf,
                event,
                exc.reason_code,
                repeat_count,
            )
            return False
        return remaining_structured_retries > 0

    def _record_plan_retry(
        self,
        exc: BaseException,
        leaf: str,
        remaining_structured_retries: int,
    ) -> None:
        if isinstance(exc, PaperPlanGenerationError):
            context = current_retry_context()
            if context is not None:
                context.set_retry_hint(
                    leaf=leaf,
                    reason_code=exc.reason_code,
                    loc=exc.loc,
                )
            self._log_plan_retry_decision("attempt", exc, leaf, remaining_structured_retries)

    def _record_plan_exhausted(self, exc: BaseException, leaf: str) -> None:
        if isinstance(exc, PaperPlanGenerationError):
            self._log_plan_retry_decision("exhausted", exc, leaf, 0)
            if exc.reason_code in EQUATION_REASON_CODES:
                logger.warning(
                    "paper_structured_retry_equation_exhausted component=%s leaf=%s "
                    "reason_code=%s",
                    "plan",
                    leaf,
                    exc.reason_code,
                )

    def _record_plan_rescue_if_needed(self, leaf: str, retried_leaves: set[str]) -> None:
        if leaf not in retried_leaves:
            return
        context = current_retry_context()
        if context is not None:
            context.mark_rescued(leaf)
        logger.info(
            "paper_structured_retry_rescued component=%s leaf=%s",
            "plan",
            leaf,
        )
        if leaf in {PLAN_COMPOSER_ROLE_NAME, MISSING_DETECTOR_ROLE_NAME}:
            logger.info(
                "paper_structured_retry_equation_rescue_checked component=%s leaf=%s",
                "plan",
                leaf,
            )
        retried_leaves.discard(leaf)

    def _log_plan_retry_decision(
        self,
        event: str,
        exc: PaperPlanGenerationError,
        leaf: str,
        remaining_structured_retries: int,
    ) -> None:
        logger.info(
            "paper_structured_retry_decision component=%s leaf=%s event=%s "
            "reason_code=%s finish_reason=%s remaining=%s schema_subtype=%s",
            "plan",
            leaf,
            event,
            exc.reason_code,
            exc.finish_reason,
            remaining_structured_retries,
            _schema_subtype(exc.reason_code, exc.loc),
        )

    def _preflight_spec_equation_namespace(self, spec: PaperSpec) -> None:
        document_ids = [document.document_id for document in spec.documents]
        document_id_set = set(document_ids)
        if len(document_ids) != len(document_id_set):
            _raise_plan_preflight_equation_error()

        equation_keys: list[tuple[str, str]] = []
        for equation in spec.equations:
            if equation.document_id is None or equation.document_id not in document_id_set:
                _raise_plan_preflight_equation_error()
            equation_keys.append((equation.document_id, equation.equation_id))
        if len(equation_keys) != len(set(equation_keys)):
            _raise_plan_preflight_equation_error()

        allowed_equations = set(equation_keys)
        for entry in spec.evidence:
            if entry.equation_id is None:
                continue
            if (
                entry.document_id is None
                or (entry.document_id, entry.equation_id) not in allowed_equations
            ):
                _raise_plan_preflight_equation_error()

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
        audit = self.build_steps_dependency_audit()
        if build_steps_dependency_audit_enabled():
            logger.warning(
                "paper_plan_build_steps_fallback reason_code=%s exc_type=%s " "dependency_audit=%s",
                exc.reason_code,
                type(exc).__name__,
                json.dumps(audit.to_dict(), sort_keys=True, separators=(",", ":")),
            )
            return
        logger.warning(
            "paper_plan_build_steps_fallback reason_code=%s exc_type=%s",
            exc.reason_code,
            type(exc).__name__,
        )

    def build_steps_dependency_audit(self) -> DependencyAudit:
        if self._last_build_steps_dependency_audit is None:
            return DependencyAudit.unavailable("draft_parse")
        return self._last_build_steps_dependency_audit

    def _clear_build_steps_dependency_audit(self) -> None:
        self._last_build_steps_dependency_audit = None

    def _record_build_steps_dependency_audit(
        self,
        raw_data: object,
        *,
        role_name: str,
        evidence_ref_count: int | None,
        block_candidate_count: int | None,
        parameter_mapping_count: int | None,
        rendered_prompt_version: str | None,
    ) -> None:
        if not build_steps_dependency_audit_enabled():
            self._last_build_steps_dependency_audit = None
            return
        prompt_tokens = self._last_llm_prompt_tokens_by_role.get(role_name)
        self._last_build_steps_dependency_audit = audit_step_dependencies_from_payload(
            raw_data
        ).with_context(
            evidence_ref_count=evidence_ref_count,
            block_candidate_count=block_candidate_count,
            parameter_mapping_count=parameter_mapping_count,
            prompt_tokens_bucket=prompt_token_bucket(prompt_tokens),
            rendered_prompt_version=rendered_prompt_version,
        )


def _with_plan_error_metadata(
    exc: PaperPlanGenerationError,
    *,
    leaf: str,
) -> PaperPlanGenerationError:
    if exc.leaf is None:
        exc.leaf = leaf
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
    if loc_parts & {"missing_prompts", "block_recommendations", "parameter_mapping"}:
        return "schema_cardinality_invalid"
    return "schema_shape_invalid"


def _raise_plan_preflight_equation_error() -> NoReturn:
    raise PaperPlanGenerationError(
        "role=plan_preflight: equation_namespace_invalid",
        reason_code="equation_id_outside_whitelist",
        leaf="plan_preflight",
        locator_namespace="equation_id",
    ) from None


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


class _BuildStepDraftEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(min_length=1)


class _StepBlockRefDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_ref_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    library_path: str | None = Field(min_length=1)
    purpose: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel | None = None

    def to_domain(self) -> StepBlockRef:
        return StepBlockRef(
            block_ref_id=self.block_ref_id,
            block_type=self.block_type,
            library_path=self.library_path,
            purpose=self.purpose,
            paper_reference=(
                self.paper_reference.to_domain() if self.paper_reference is not None else None
            ),
        )


class _ModelBuildStepDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    block_refs: list[_StepBlockRefDraftModel]
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


def _resolve_build_steps_draft_evidence_payload(
    data: dict[str, Any],
    *,
    document_source_refs: list[PlanEvidenceSourceRef],
    user_source_refs: list[BuildStepUserEvidenceSourceRef],
) -> dict[str, Any]:
    source_index = _build_step_source_ref_index(
        document_source_refs=document_source_refs,
        user_source_refs=user_source_refs,
    )
    result = dict(data)
    steps = result.get("build_steps")
    if not isinstance(steps, list):
        return result
    result["build_steps"] = [
        _resolve_build_step_draft_evidence(step, source_index) for step in steps
    ]
    return result


def _build_step_source_ref_index(
    *,
    document_source_refs: list[PlanEvidenceSourceRef],
    user_source_refs: list[BuildStepUserEvidenceSourceRef],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for document_entry in document_source_refs:
        index.setdefault(document_entry.source_ref, []).append(
            _document_evidence_payload_from_source_ref(document_entry)
        )
    for user_entry in user_source_refs:
        try:
            payload = PaperEvidenceEntryModel.from_domain(user_entry.evidence).model_dump(
                mode="json"
            )
        except ValidationError:
            raise BuildStepsDtoValidationError("final_evidence_invalid") from None
        index.setdefault(user_entry.source_ref, []).append(payload)
    return index


def _document_evidence_payload_from_source_ref(entry: PlanEvidenceSourceRef) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": EvidenceSource.DOCUMENT_EXTRACTED.value,
        "document_id": entry.document_id,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": entry.excerpt,
        "missing_param_prompt_id": None,
        "user_action": None,
        "parameter_correction_id": None,
        "correction_param_key": None,
    }
    payload[entry.locator_kind] = entry.locator_id
    try:
        return PaperEvidenceEntryModel.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        raise BuildStepsDtoValidationError("final_evidence_invalid") from None


def _resolve_build_step_draft_evidence(
    step: object,
    source_index: dict[str, list[dict[str, Any]]],
) -> object:
    if not isinstance(step, dict):
        return step
    result = dict(step)

    block_refs = result.get("block_refs")
    if isinstance(block_refs, list):
        result["block_refs"] = [
            _resolve_build_step_block_ref_evidence(block_ref, source_index)
            for block_ref in block_refs
        ]

    configuration_hints = result.get("configuration_hints")
    if isinstance(configuration_hints, list):
        result["configuration_hints"] = [
            _resolve_build_step_configuration_hint_evidence(hint, source_index)
            for hint in configuration_hints
        ]

    evidence = result.get("evidence")
    if isinstance(evidence, list):
        result["evidence"] = [
            _resolve_build_step_draft_evidence_entry(entry, source_index) for entry in evidence
        ]
    return result


def _resolve_build_step_block_ref_evidence(
    block_ref: object,
    source_index: dict[str, list[dict[str, Any]]],
) -> object:
    if not isinstance(block_ref, dict):
        return block_ref
    result = dict(block_ref)
    if result.get("paper_reference") is not None:
        result["paper_reference"] = _resolve_build_step_draft_evidence_entry(
            result["paper_reference"],
            source_index,
        )
    return result


def _resolve_build_step_configuration_hint_evidence(
    hint: object,
    source_index: dict[str, list[dict[str, Any]]],
) -> object:
    if not isinstance(hint, dict):
        return hint
    result = dict(hint)
    evidence = result.get("evidence")
    if isinstance(evidence, list):
        result["evidence"] = [
            _resolve_build_step_draft_evidence_entry(entry, source_index) for entry in evidence
        ]
    return result


def _resolve_build_step_draft_evidence_entry(
    payload: object,
    source_index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BuildStepsDtoValidationError("draft_schema_invalid") from None
    source_ref = payload.get(PLAN_EVIDENCE_SOURCE_REF_FIELD, _MISSING)
    if source_ref is _MISSING or source_ref is None:
        raise BuildStepsDtoValidationError("source_ref_missing") from None
    if not isinstance(source_ref, str):
        raise BuildStepsDtoValidationError("source_ref_type_invalid") from None
    if not source_ref.strip():
        raise BuildStepsDtoValidationError("source_ref_missing") from None
    try:
        _BuildStepDraftEvidenceModel.model_validate(payload)
    except ValidationError:
        raise BuildStepsDtoValidationError("draft_schema_invalid") from None

    matches = source_index.get(source_ref, [])
    if not matches:
        raise BuildStepsDtoValidationError("source_ref_no_match") from None
    if len(matches) > 1:
        raise BuildStepsDtoValidationError("source_ref_ambiguous") from None
    return dict(matches[0])


def _build_steps_final_validation_reason(exc: ValidationError) -> str:
    for item in exc.errors(include_url=False, include_context=False, include_input=False):
        loc = item.get("loc")
        if not isinstance(loc, tuple):
            continue
        loc_parts = {str(part) for part in loc}
        if PLAN_EVIDENCE_SOURCE_REF_FIELD in loc_parts:
            return "source_ref_leaked"
        if loc_parts & {"evidence", "paper_reference"}:
            return "final_evidence_invalid"
    return "dto_invalid"


def _log_omitted_build_step_block_reference_count(
    data: object,
    *,
    role_name: str,
) -> None:
    omitted_count = _count_omitted_build_step_block_references(data)
    if omitted_count == 0:
        return
    logger.info(
        "paper_plan_build_steps_draft_default_applied role=%s stage=%s field_path=%s "
        "reason_code=%s count=%s",
        role_name,
        "llm_draft",
        "build_steps.block_refs.paper_reference",
        "omitted_paper_reference",
        omitted_count,
    )


def _count_omitted_build_step_block_references(data: object) -> int:
    if not isinstance(data, dict):
        return 0
    build_steps = data.get("build_steps")
    if not isinstance(build_steps, list):
        return 0
    omitted_count = 0
    for step in build_steps:
        if not isinstance(step, dict):
            continue
        block_refs = step.get("block_refs")
        if not isinstance(block_refs, list):
            continue
        omitted_count += sum(
            1
            for block_ref in block_refs
            if isinstance(block_ref, dict) and "paper_reference" not in block_ref
        )
    return omitted_count
