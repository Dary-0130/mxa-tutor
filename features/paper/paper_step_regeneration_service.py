"""Regenerate paper build steps and M script from the current working plan."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Literal

from loguru import logger
from pydantic import ValidationError

from core.domain.exceptions import (
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    PaperNotFoundError,
    PaperPlanGenerationError,
    PaperReparseInProgressError,
    StoreError,
)
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import ModelBuildStep, ModelGenerationPlan, PaperPlanRecord
from core.interfaces.paper_cache import PaperBundleStore, PaperPlanCache
from features.paper.build_guidance_lifecycle import (
    guidance_status_requires_regeneration,
    mark_guidance_stale_for_step_regeneration,
)
from features.paper.build_steps_dependency_audit import build_steps_dependency_audit_enabled
from features.paper.paper_plan_helpers import (
    BuildStepsDtoValidationError,
    BuildStepsEvidenceError,
    BuildStepsJsonParseError,
    BuildStepsRedLineError,
    BuildStepsSemanticValidationError,
    BuildStepsStructuredError,
    PlanAssembler,
    UserEvidenceRef,
    resolved_prompt_ids,
    resolved_user_evidence_refs,
    validate_build_step_evidence_for_spec,
)
from features.paper.paper_plan_integrity import validate_plan_does_not_resolve_conflicts
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_reparse_service import PaperReparseLockRegistry
from features.paper.paper_schemas import ModelGenerationPlanModel, ParameterMappingModel

RegenerationResultKind = Literal[
    "regenerated_with_steps",
    "regenerated_with_steps_mscript_fail_closed",
    "regenerated_fail_closed",
    "nothing_to_regenerate",
    "lock_conflict",
    "store_failed",
]


class PaperStepRegenerationError(Exception):
    """Route-local regeneration failure with a stable public error code."""

    def __init__(self, error_code: str, status_code: int) -> None:
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(error_code)


class PaperStepRegenerationService:
    """Regenerate the local plan artifacts that corrections intentionally suppress."""

    def __init__(
        self,
        *,
        bundle_store: PaperBundleStore,
        plan_cache: PaperPlanCache,
        plan_service: PaperPlanService,
        lock_registry: PaperReparseLockRegistry,
        plan_assembler: PlanAssembler | None = None,
        retry_attempts: int = 4,
        retry_backoff_base_seconds: float = 0.2,
    ) -> None:
        self._bundle_store = bundle_store
        self._plan_cache = plan_cache
        self._plan_service = plan_service
        self._lock_registry = lock_registry
        self._plan_assembler = plan_assembler or PlanAssembler()
        self._retry_attempts = retry_attempts
        self._retry_backoff_base_seconds = retry_backoff_base_seconds

    async def regenerate_steps(self, paper_id: str) -> ModelGenerationPlan:
        """Regenerate build steps and M script while preserving the overlay plan."""

        try:
            async with await self._lock_registry.acquire(paper_id):
                record = await self._bundle_store.get_plan_record(paper_id)
                if record is None:
                    raise PaperNotFoundError("paper_not_found") from None
                corrections = await self._bundle_store.list_parameter_corrections(paper_id)
                if not _has_regeneration_work(record, corrections):
                    _log_regeneration_telemetry("nothing_to_regenerate")
                    raise PaperStepRegenerationError("regenerate_nothing_to_do", 400) from None

                allowed_refs = resolved_user_evidence_refs(record, corrections)
                allowed_prompts = resolved_prompt_ids(record)
                build_steps, build_retries = await self._regenerate_build_steps_with_retry(
                    record,
                    allowed_user_evidence_refs=allowed_refs,
                    allowed_user_prompt_ids=allowed_prompts,
                )
                mscript, mscript_retries = await self._regenerate_mscript_with_retry(record)

                updated_plan = _replace_regenerated_artifacts(
                    record,
                    build_steps=build_steps,
                    mscript=mscript,
                )
                updated_plan = await self._regenerate_build_guidance(record, updated_plan)
                result_kind = _result_kind(
                    build_steps_generated=build_steps is not None,
                    mscript_generated=mscript is not None,
                )

                try:
                    self._validate_regenerated_plan_before_write(
                        updated_plan,
                        record,
                        corrections,
                        allowed_user_evidence_refs=allowed_refs,
                        allowed_user_prompt_ids=allowed_prompts,
                    )
                except (
                    BuildStepsStructuredError,
                    PaperPlanGenerationError,
                    ValidationError,
                    ValueError,
                ):
                    _log_regeneration_telemetry(
                        "regenerated_fail_closed",
                        build_steps_retry_count=build_retries,
                        mscript_retry_count=mscript_retries,
                    )
                    return record.plan

                updated_record = replace(record, plan=updated_plan)
                try:
                    await self._plan_cache.set(paper_id, updated_record)
                except StoreError as exc:
                    logger.error(
                        "paper_step_regeneration_store_failed exception={}",
                        type(exc).__name__,
                    )
                    _log_regeneration_telemetry("store_failed")
                    raise PaperStepRegenerationError("regenerate_store_failed", 500) from None

                _log_regeneration_telemetry(
                    result_kind,
                    build_steps_retry_count=build_retries,
                    mscript_retry_count=mscript_retries,
                )
                return updated_plan
        except PaperReparseInProgressError:
            _log_regeneration_telemetry("lock_conflict")
            raise

    async def _regenerate_build_steps_with_retry(
        self,
        record: PaperPlanRecord,
        *,
        allowed_user_evidence_refs: set[UserEvidenceRef],
        allowed_user_prompt_ids: frozenset[str],
    ) -> tuple[list[ModelBuildStep] | None, int]:
        retry_count = 0
        for attempt in range(self._retry_attempts):
            try:
                drafts = await self._plan_service._llm_build_steps_for_regeneration(
                    record.plan.block_recommendations,
                    record.plan.parameter_mapping,
                    record.spec,
                    record.plan.evidence,
                    allowed_user_evidence_refs,
                    allowed_user_prompt_ids,
                )
                steps = self._plan_assembler.validate_and_derive_build_steps(
                    drafts,
                    record.plan.parameter_mapping,
                    record.plan.block_recommendations,
                )
                self._log_build_steps_dependency_audit(
                    terminal_reason_code="structured_success",
                    attempt_index=attempt + 1,
                )
                return steps, retry_count
            except _BUILD_STEP_TRANSIENT_ERRORS as exc:
                self._log_build_steps_dependency_audit(
                    terminal_reason_code=_build_step_exception_reason_code(exc),
                    attempt_index=attempt + 1,
                )
                if attempt == self._retry_attempts - 1:
                    return None, retry_count
                retry_count += 1
                await self._backoff(attempt)
            except _BUILD_STEP_REDLINE_ERRORS as exc:
                self._log_build_steps_dependency_audit(
                    terminal_reason_code=_build_step_exception_reason_code(exc),
                    attempt_index=attempt + 1,
                )
                return None, retry_count
            except (LLMError, PaperPlanGenerationError) as exc:
                self._log_build_steps_dependency_audit(
                    terminal_reason_code=_build_step_exception_reason_code(exc),
                    attempt_index=attempt + 1,
                )
                return None, retry_count
        return None, retry_count

    def _log_build_steps_dependency_audit(
        self,
        *,
        terminal_reason_code: str,
        attempt_index: int,
    ) -> None:
        if not build_steps_dependency_audit_enabled():
            return
        audit = self._plan_service.build_steps_dependency_audit()
        logger.info(
            "paper_step_regeneration_build_steps_dependency_audit event_code={} "
            "attempt_index={} terminal_reason_code={} dependency_audit={}",
            "paper_step_regeneration_build_steps_dependency_audit",
            attempt_index,
            terminal_reason_code,
            json.dumps(audit.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    async def _regenerate_mscript_with_retry(
        self,
        record: PaperPlanRecord,
    ) -> tuple[str | None, int]:
        retry_count = 0
        for attempt in range(self._retry_attempts):
            try:
                return (
                    await self._plan_service._llm_mscript_draft_from_mapping(
                        record.plan.parameter_mapping,
                        record.spec,
                    ),
                    retry_count,
                )
            except _MSCRIPT_TRANSIENT_ERRORS as exc:
                if _is_mscript_redline(exc):
                    return None, retry_count
                if attempt == self._retry_attempts - 1:
                    return None, retry_count
                retry_count += 1
                await self._backoff(attempt)
            except LLMError:
                return None, retry_count
        return None, retry_count

    async def _backoff(self, attempt: int) -> None:
        if self._retry_backoff_base_seconds <= 0:
            return
        await asyncio.sleep(self._retry_backoff_base_seconds * (2**attempt))

    async def _regenerate_build_guidance(
        self,
        record: PaperPlanRecord,
        updated_plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        stale_plan = mark_guidance_stale_for_step_regeneration(updated_plan)
        generator = getattr(self._plan_service, "generate_build_guidance_for_plan", None)
        if generator is None:
            return stale_plan
        return await generator(record.spec, stale_plan)

    def _validate_regenerated_plan_before_write(
        self,
        updated_plan: ModelGenerationPlan,
        original_record: PaperPlanRecord,
        corrections: list[PaperParameterCorrection],
        *,
        allowed_user_evidence_refs: set[UserEvidenceRef],
        allowed_user_prompt_ids: frozenset[str],
    ) -> None:
        if updated_plan.build_steps is not None:
            _validate_build_step_evidence(
                updated_plan.build_steps,
                original_record,
                allowed_user_evidence_refs=allowed_user_evidence_refs,
                allowed_user_prompt_ids=allowed_user_prompt_ids,
            )
        validate_plan_does_not_resolve_conflicts(
            updated_plan,
            original_record.spec.parameter_conflicts,
        )
        if _parameter_mapping_bytes(updated_plan) != _parameter_mapping_bytes(original_record.plan):
            raise ValueError("parameter_mapping_changed")
        if _plan_evidence_bytes(updated_plan) != _plan_evidence_bytes(original_record.plan):
            raise ValueError("plan_evidence_changed")
        updated_record = replace(original_record, plan=updated_plan)
        if resolved_user_evidence_refs(updated_record, corrections) != resolved_user_evidence_refs(
            original_record,
            corrections,
        ):
            raise ValueError("resolved_user_evidence_changed")
        ModelGenerationPlanModel.from_domain(updated_plan).to_domain()


_BUILD_STEP_TRANSIENT_ERRORS = (
    BuildStepsJsonParseError,
    BuildStepsDtoValidationError,
    BuildStepsSemanticValidationError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
_BUILD_STEP_REDLINE_ERRORS = (BuildStepsRedLineError, BuildStepsEvidenceError)
_MSCRIPT_TRANSIENT_ERRORS = (
    PaperPlanGenerationError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)


def _has_regeneration_work(
    record: PaperPlanRecord,
    corrections: list[PaperParameterCorrection],
) -> bool:
    return bool(
        corrections
        or record.plan.build_steps is None
        or record.plan.m_script_skeleton is None
        or guidance_status_requires_regeneration(record.plan.guidance_status)
    )


def _replace_regenerated_artifacts(
    record: PaperPlanRecord,
    *,
    build_steps: list[ModelBuildStep] | None,
    mscript: str | None,
) -> ModelGenerationPlan:
    effective_build_steps = build_steps if build_steps is not None else record.plan.build_steps
    effective_mscript = mscript if mscript is not None else record.plan.m_script_skeleton
    subsystem_breakdown = (
        [step.display_text for step in build_steps]
        if build_steps is not None
        else record.plan.subsystem_breakdown
    )
    return replace(
        record.plan,
        build_steps=effective_build_steps,
        m_script_skeleton=effective_mscript,
        subsystem_breakdown=subsystem_breakdown,
    )


def _result_kind(
    *,
    build_steps_generated: bool,
    mscript_generated: bool,
) -> RegenerationResultKind:
    if not build_steps_generated:
        return "regenerated_fail_closed"
    if not mscript_generated:
        return "regenerated_with_steps_mscript_fail_closed"
    return "regenerated_with_steps"


def _validate_build_step_evidence(
    build_steps: list[ModelBuildStep],
    record: PaperPlanRecord,
    *,
    allowed_user_evidence_refs: set[UserEvidenceRef],
    allowed_user_prompt_ids: frozenset[str],
) -> None:
    for step in build_steps:
        validate_build_step_evidence_for_spec(
            step.evidence,
            record.spec,
            allowed_user_prompt_ids=allowed_user_prompt_ids,
            allowed_user_evidence_refs=allowed_user_evidence_refs,
        )
        validate_build_step_evidence_for_spec(
            [
                block_ref.paper_reference
                for block_ref in step.block_refs
                if block_ref.paper_reference is not None
            ],
            record.spec,
            allowed_user_prompt_ids=allowed_user_prompt_ids,
            allowed_user_evidence_refs=allowed_user_evidence_refs,
        )
        for configuration_hint in step.configuration_hints:
            validate_build_step_evidence_for_spec(
                configuration_hint.evidence,
                record.spec,
                allowed_user_prompt_ids=allowed_user_prompt_ids,
                allowed_user_evidence_refs=allowed_user_evidence_refs,
            )


def _is_mscript_redline(exc: Exception) -> bool:
    return any(
        arg == "role=mscript_drafter_from_mapping: parameter_conflict_mscript" for arg in exc.args
    )


def _parameter_mapping_bytes(plan: ModelGenerationPlan) -> bytes:
    payload = [
        ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
        for mapping in plan.parameter_mapping
    ]
    return _stable_json_bytes(payload)


def _plan_evidence_bytes(plan: ModelGenerationPlan) -> bytes:
    payload = ModelGenerationPlanModel.from_domain(plan).model_dump(mode="json")["evidence"]
    return _stable_json_bytes(payload)


def _stable_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _log_regeneration_telemetry(
    result_kind: RegenerationResultKind,
    *,
    build_steps_retry_count: int = 0,
    mscript_retry_count: int = 0,
) -> None:
    success_count = 1 if result_kind.startswith("regenerated_with_steps") else 0
    logger.info(
        "paper_step_regeneration event_code={} result_kind={} "
        "regenerate_attempt_count={} regenerate_success_count={} "
        "build_steps_retry_count={} mscript_retry_count={}",
        "paper_step_regeneration",
        result_kind,
        1,
        success_count,
        build_steps_retry_count,
        mscript_retry_count,
    )


def _build_step_exception_reason_code(exc: BaseException) -> str:
    if isinstance(exc, BuildStepsStructuredError):
        return exc.reason_code
    if isinstance(exc, PaperPlanGenerationError) and exc.reason_code is not None:
        return exc.reason_code
    return type(exc).__name__
