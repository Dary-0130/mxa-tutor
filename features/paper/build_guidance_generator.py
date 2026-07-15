"""Fail-closed generation for model build guidance."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.domain.exceptions import (
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    PaperPlanGenerationError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    BuildGuidance,
    ConnectionHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceGap,
    GuidanceResolution,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    StepBlockRef,
)
from core.domain.paper_spec import PaperSpec, ParameterEntry
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_builder import build_messages_for_build_guidance
from features.paper.build_guidance_observability import (
    GuidanceAttemptTelemetry,
    GuidanceFailureReasonCode,
    GuidanceGenerationTelemetry,
    GuidanceParseOutcome,
    GuidanceTerminationGuard,
    completion_ratio,
    guidance_exception_code,
    has_provider_telemetry_anomaly,
    llm_unparseable_reason,
    termination_guard_for_exception,
    termination_guard_for_retry_reason,
)
from features.paper.build_guidance_requirements import (
    GuidanceRequirement,
    actionability_for_closure,
    claim_mentions_other_requirement,
    closure_from_resolution,
    critical_steps,
    detail_kind_for_target,
    enumerate_guidance_requirements,
    guidance_requirements_prompt_payload,
    reduce_guidance_requirements,
    render_detail_display_text,
    required_object_coverage,
)
from features.paper.build_guidance_rules import (
    CONFIRMATION_REASON_TEMPLATES,
    CONVENTION_TEMPLATES,
    DISPLAY_BLOCK_TERMS,
    REAL_BLOCK_ALLOW_TERMS,
    ControlledGuidanceTargets,
    DetailBasis,
    DetailKind,
    GroundingTruthIndex,
    GuidanceEvidenceCard,
    GuidanceEvidencePool,
    convention_display_text,
    high_risk_claim_tokens,
)
from features.paper.build_guidance_rules import (
    canonicalize as _canonicalize,
)
from features.paper.build_guidance_rules import (
    clean_display_text as _clean_display_text,
)
from features.paper.build_guidance_rules import (
    evidence_key as _evidence_key,
)
from features.paper.build_guidance_rules import (
    unsafe_freeform_text as _unsafe_freeform_text,
)
from features.paper.build_guidance_semantic_validator import (
    GuidanceSemanticValidationResult,
    guidance_validation_telemetry,
    validate_build_guidance_semantics,
)
from features.paper.guidance_resolution_schemas import (
    GuidanceResolutionModel,
    resolution_to_domain,
)
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
    PlanEvidenceSourceRef,
    build_plan_evidence_source_refs,
)

GUIDANCE_ROLE_NAME = "build_guidance_generator"
DEFAULT_GUIDANCE_TIMEOUT_SECONDS = 90.0
DEFAULT_GUIDANCE_MAX_TOKENS = 6000
GUIDANCE_FULL_ATTEMPTS = 2
GUIDANCE_HARD_CALL_CAP = 3
GUIDANCE_WALL_CLOCK_SECONDS = 180.0

GuidanceFailureReason = GuidanceFailureReasonCode
_LEGACY_GUIDANCE_FAILURE_REASON = Literal[
    "zero_document_claims_empty_evidence_pool",
    "zero_document_claims_unlinked_evidence_pool",
    "llm_unparseable",
    "evidence_resolution_failed",
    "retry_cap_exhausted",
    "build_steps_unavailable",
    "evidence_card_unavailable",
]


@dataclass(frozen=True)
class DraftAttemptStats:
    """Raw draft counters captured before fail-closed downgrades."""

    raw_document_claim_count: int
    raw_supporting_ref_count: int
    resolver_error_count: int
    parse_error_count: int = 0


@dataclass(frozen=True)
class GuidanceDraftResult:
    """Parsed and grounded guidance draft result."""

    details: list[GuidanceDetail]
    stats: DraftAttemptStats
    dropped_count: int
    downgraded_unverified_count: int
    resolver_event_codes: list[str]


@dataclass(frozen=True)
class GuidanceLLMCallResult:
    """Parsed guidance payload plus sanitized response metadata."""

    payload: dict[str, Any]
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    max_tokens: int
    elapsed_ms: int


class GuidanceLLMCallError(Exception):
    """Internal non-leaking wrapper for one failed guidance provider attempt."""

    def __init__(
        self,
        *,
        parse_outcome: GuidanceParseOutcome,
        finish_reason: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        max_tokens: int | None,
        elapsed_ms: int,
        generator_exception: str,
        termination_guard: GuidanceTerminationGuard,
    ) -> None:
        self.parse_outcome = parse_outcome
        self.finish_reason = finish_reason
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.max_tokens = max_tokens
        self.elapsed_ms = elapsed_ms
        self.generator_exception = cast(Any, generator_exception)
        self.termination_guard = termination_guard
        super().__init__()


class GuidanceProviderConfigurationError(Exception):
    """Provider configuration failures that must propagate out of content fallback."""


@dataclass(frozen=True)
class GuidanceDocumentResolution:
    """Telemetry-only result of resolving one document-sourced draft detail."""

    detail: GuidanceDetail | None
    resolver_error_count: int
    resolver_event_codes: list[str]
    downgraded_unverified_count: int


@dataclass
class GuidanceRetryContext:
    """Independent retry caps for guidance generation."""

    hard_call_count: int = GUIDANCE_HARD_CALL_CAP
    wall_clock_seconds: float = GUIDANCE_WALL_CLOCK_SECONDS
    started_monotonic: float = 0.0
    call_count: int = 0

    def __post_init__(self) -> None:
        if self.started_monotonic == 0.0:
            self.started_monotonic = time.monotonic()

    def before_call(self) -> None:
        if time.monotonic() - self.started_monotonic > self.wall_clock_seconds:
            raise GuidanceRetryExceeded("guidance_wall_clock_cap_exceeded")
        if self.call_count + 1 > self.hard_call_count:
            raise GuidanceRetryExceeded("guidance_call_cap_exceeded")
        self.call_count += 1


class GuidanceRetryExceeded(Exception):
    """Raised when the independent guidance retry caps are exhausted."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__()


class GuidanceDetailDraftModel(BaseModel):
    """Private per-detail draft DTO."""

    model_config = ConfigDict(extra="forbid")

    requirement_ref: str | None = Field(default=None, min_length=1)
    step_id: str | None = Field(default=None, min_length=1)
    detail_kind: DetailKind | None = None
    basis: DetailBasis
    claim_text: str = Field(min_length=1)
    supporting_evidence_refs: list[str] = Field(default_factory=list)
    convention_code: str | None = Field(default=None, min_length=1)
    target: str | None = Field(default=None, min_length=1)
    confirmation_reason_code: str | None = Field(default=None, min_length=1)
    direction_hint: str | None = Field(default=None, min_length=1)
    resolution: GuidanceResolutionModel | None = None
    input_fact_refs: list[str] = Field(default_factory=list)
    punt_reason_code: str | None = Field(default=None, min_length=1)


class GuidanceGapDraftModel(BaseModel):
    """Private gap draft DTO; severity is ignored and synthesized deterministically."""

    model_config = ConfigDict(extra="forbid")

    gap_kind: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    step_id: str | None = Field(default=None, min_length=1)
    gap_reason_code: str = Field(min_length=1)


class BuildGuidanceGenerator:
    """Generate build guidance while failing closed on every unsafe unit."""

    def __init__(
        self,
        text_provider: TextProvider,
        *,
        timeout: float = DEFAULT_GUIDANCE_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_GUIDANCE_MAX_TOKENS,
        evidence_tagger: EvidenceTagger | None = None,
        retry_context_factory: Callable[[], GuidanceRetryContext] | None = None,
    ) -> None:
        self._text_provider = text_provider
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._evidence_tagger = evidence_tagger or EvidenceTagger()
        self._retry_context_factory = retry_context_factory or GuidanceRetryContext
        self._last_telemetry = GuidanceGenerationTelemetry(
            attempts=[],
            terminal_status=None,
            terminal_reason=None,
            terminal_termination_guard="none",
        )

    @property
    def last_telemetry(self) -> GuidanceGenerationTelemetry:
        """Return telemetry from the latest generate call."""

        return self._last_telemetry

    async def generate(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        """Return the plan with generated guidance or an honest terminal status."""

        attempt_records: list[GuidanceAttemptTelemetry] = []
        terminal_guard: GuidanceTerminationGuard = "none"
        if plan.build_steps is None:
            self._log_terminal(
                "generation_failed",
                "build_steps_unavailable",
                retry_count=0,
            )
            self._last_telemetry = GuidanceGenerationTelemetry(
                attempts=[],
                terminal_status="generation_failed",
                terminal_reason="build_steps_unavailable",
                terminal_termination_guard="none",
            )
            return replace(plan, build_guidance=None, guidance_status="generation_failed")

        pool = build_guidance_evidence_pool(spec, plan, self._evidence_tagger)
        truth_index = GroundingTruthIndex.from_spec_plan(spec, plan, pool)
        targets = ControlledGuidanceTargets(plan.build_steps)
        requirements = enumerate_guidance_requirements(plan.paper_spec_id, plan.build_steps)
        attempts: list[DraftAttemptStats] = []
        retry_context = self._retry_context_factory()

        for attempt_index in range(GUIDANCE_FULL_ATTEMPTS):
            try:
                call_result = await self._call_llm_json(
                    build_messages_for_build_guidance(
                        plan,
                        pool.cards,
                        guidance_requirements_prompt_payload(requirements),
                    ),
                    retry_context,
                )
            except GuidanceRetryExceeded as exc:
                terminal_guard = termination_guard_for_retry_reason(exc.reason_code)
                break
            except GuidanceLLMCallError as exc:
                stats = DraftAttemptStats(
                    raw_document_claim_count=0,
                    raw_supporting_ref_count=0,
                    resolver_error_count=0,
                    parse_error_count=1,
                )
                attempts.append(stats)
                terminal_guard = exc.termination_guard
                attempt_records.append(
                    GuidanceAttemptTelemetry(
                        attempt_index=attempt_index + 1,
                        parse_outcome=exc.parse_outcome,
                        finish_reason=exc.finish_reason,
                        completion_tokens=exc.completion_tokens,
                        prompt_tokens=exc.prompt_tokens,
                        max_tokens=exc.max_tokens,
                        completion_ratio=completion_ratio(
                            exc.completion_tokens,
                            exc.max_tokens,
                        ),
                        provider_telemetry_anomaly=has_provider_telemetry_anomaly(
                            finish_reason=exc.finish_reason,
                            completion_tokens=exc.completion_tokens,
                            max_tokens=exc.max_tokens,
                        ),
                        resolver_event_codes=[],
                        validator_machine_codes=[],
                        detail_downgraded_count=None,
                        detail_dropped_count=None,
                        validator_dropped_unverified_count=None,
                        generated_output_changed=None,
                        raw_document_claim_count=0,
                        raw_supporting_ref_count=0,
                        resolver_error_count=0,
                        parse_error_count=1,
                        elapsed_ms=exc.elapsed_ms,
                        termination_guard=exc.termination_guard,
                        generator_exception=exc.generator_exception,
                    )
                )
                continue

            result = parse_and_ground_guidance_draft(
                call_result.payload,
                pool=pool,
                truth_index=truth_index,
                targets=targets,
                build_steps=plan.build_steps,
                requirements=requirements,
            )
            attempts.append(result.stats)
            attempt_record = GuidanceAttemptTelemetry(
                attempt_index=attempt_index + 1,
                parse_outcome="parsed",
                finish_reason=call_result.finish_reason,
                completion_tokens=call_result.completion_tokens,
                prompt_tokens=call_result.prompt_tokens,
                max_tokens=call_result.max_tokens,
                completion_ratio=completion_ratio(
                    call_result.completion_tokens,
                    call_result.max_tokens,
                ),
                provider_telemetry_anomaly=has_provider_telemetry_anomaly(
                    finish_reason=call_result.finish_reason,
                    completion_tokens=call_result.completion_tokens,
                    max_tokens=call_result.max_tokens,
                ),
                resolver_event_codes=result.resolver_event_codes,
                validator_machine_codes=[],
                detail_downgraded_count=result.downgraded_unverified_count,
                detail_dropped_count=result.dropped_count,
                validator_dropped_unverified_count=0,
                generated_output_changed=False,
                raw_document_claim_count=result.stats.raw_document_claim_count,
                raw_supporting_ref_count=result.stats.raw_supporting_ref_count,
                resolver_error_count=result.stats.resolver_error_count,
                parse_error_count=result.stats.parse_error_count,
                elapsed_ms=call_result.elapsed_ms,
                termination_guard="none",
            )
            if not result.details:
                attempt_records.append(attempt_record)
                continue

            reduction = reduce_guidance_requirements(
                requirements=requirements, details=result.details
            )
            guidance = BuildGuidance(
                version="v2",
                assessment=reduction.assessment,
                details=_dedupe_details(result.details),
                gaps=reduction.gaps,
            )
            self._log_success(
                guidance,
                retry_count=attempt_index,
                critical_step_count=len(_critical_steps(plan.build_steps)),
            )
            candidate = replace(
                plan,
                build_guidance=guidance,
                guidance_status="generated",
            )
            validation = validate_build_guidance_semantics(
                spec,
                candidate,
                evidence_tagger=self._evidence_tagger,
            )
            if validation.changed:
                telemetry = guidance_validation_telemetry(validation)
                machine_codes = [
                    *validation.machine_codes,
                    "guidance_validator_generated_output_changed",
                ]
                logger.error(
                    "paper_build_guidance_validator event_code={} machine_codes={} "
                    "guidance_validator_detail_downgraded_count={} "
                    "guidance_validator_detail_dropped_count={} "
                    "guidance_validator_gap_dropped_count={} "
                    "guidance_validator_all_document_details_lost={} "
                    "guidance_validator_template_version_mismatch={} "
                    "guidance_validator_display_text_grounding_failed={} "
                    "guidance_validator_stale_snapshot_step_ref_ignored={} "
                    "guidance_validator_generated_output_changed={}",
                    "guidance_validator_generated_output_changed",
                    machine_codes,
                    telemetry.detail_downgraded_count,
                    telemetry.detail_dropped_count,
                    telemetry.gap_dropped_count,
                    telemetry.all_document_details_lost,
                    telemetry.template_version_mismatch,
                    telemetry.display_text_grounding_failed,
                    telemetry.stale_snapshot_step_ref_ignored,
                    1,
                )
                attempt_record = replace(
                    attempt_record,
                    validator_machine_codes=machine_codes,
                    detail_dropped_count=telemetry.detail_dropped_count,
                    validator_dropped_unverified_count=(
                        _validator_dropped_unverified_count(candidate, validation)
                    ),
                    generated_output_changed=True,
                )
            attempt_records.append(attempt_record)
            self._last_telemetry = GuidanceGenerationTelemetry(
                attempts=attempt_records,
                terminal_status=validation.plan.guidance_status,
                terminal_reason=None
                if validation.plan.guidance_status == "generated"
                else "guidance_validator_generated_output_changed",
                terminal_termination_guard="none",
            )
            return validation.plan

        status, reason = _terminal_status_and_reason(
            attempts,
            pool=pool,
            call_count=retry_context.call_count,
            attempt_records=attempt_records,
        )
        self._log_terminal(status, reason, retry_count=max(0, len(attempts) - 1))
        self._last_telemetry = GuidanceGenerationTelemetry(
            attempts=attempt_records,
            terminal_status=status,
            terminal_reason=reason,
            terminal_termination_guard=terminal_guard,
        )
        return replace(plan, build_guidance=None, guidance_status=status)

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        retry_context: GuidanceRetryContext,
    ) -> GuidanceLLMCallResult:
        retry_context.before_call()
        start = time.monotonic()
        try:
            response = await asyncio.to_thread(
                self._text_provider.chat,
                messages,
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
        except (LLMAuthError, LLMQuotaError):
            raise
        except (ValueError, RuntimeError) as exc:
            raise GuidanceProviderConfigurationError(guidance_exception_code(exc)) from exc
        except (LLMTimeoutError, LLMRateLimitError, LLMServerError) as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            raise GuidanceLLMCallError(
                parse_outcome="provider_exception",
                finish_reason=None,
                prompt_tokens=None,
                completion_tokens=None,
                max_tokens=self._max_tokens,
                elapsed_ms=elapsed_ms,
                generator_exception=guidance_exception_code(exc),
                termination_guard=termination_guard_for_exception(exc),
            ) from None
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(
                "paper_build_guidance_json_decode_failed reason_code={}",
                "llm_unparseable",
            )
            raise GuidanceLLMCallError(
                parse_outcome="json_error",
                finish_reason=response.finish_reason,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                max_tokens=self._max_tokens,
                elapsed_ms=elapsed_ms,
                generator_exception="parse_error",
                termination_guard="none",
            ) from None
        if not isinstance(payload, dict):
            raise GuidanceLLMCallError(
                parse_outcome="non_object_json",
                finish_reason=response.finish_reason,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                max_tokens=self._max_tokens,
                elapsed_ms=elapsed_ms,
                generator_exception="parse_error",
                termination_guard="none",
            ) from None
        return GuidanceLLMCallResult(
            payload=payload,
            finish_reason=response.finish_reason,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            max_tokens=self._max_tokens,
            elapsed_ms=elapsed_ms,
        )

    def _log_success(
        self,
        guidance: BuildGuidance,
        *,
        retry_count: int,
        critical_step_count: int,
    ) -> None:
        details_by_basis = Counter(detail.basis for detail in guidance.details)
        gaps_by_kind = Counter(gap.gap_kind for gap in guidance.gaps)
        logger.info(
            "paper_build_guidance event_code={} guidance_status={} "
            "details_by_basis={} critical_step_count={} "
            "synthesized_gap_count={} gaps_by_kind={} blocking_gap_count={} "
            "assessment_content_status={} assessment_environment_status={} "
            "assessment_overall_status={} guidance_retry_count={}",
            "paper_build_guidance",
            "generated",
            dict(details_by_basis),
            critical_step_count,
            len(guidance.gaps),
            dict(gaps_by_kind),
            len(guidance.assessment.blocking_gap_ids),
            guidance.assessment.content_status,
            guidance.assessment.environment_status,
            guidance.assessment.overall_status,
            retry_count,
        )

    def _log_terminal(
        self,
        status: Literal["generation_failed", "no_document_basis"],
        reason: GuidanceFailureReason | str,
        *,
        retry_count: int,
    ) -> None:
        logger.info(
            "paper_build_guidance event_code={} guidance_status={} "
            "guidance_failure_reason={} guidance_retry_count={}",
            "paper_build_guidance",
            status,
            reason,
            retry_count,
        )


def build_guidance_evidence_pool(
    spec: PaperSpec,
    plan: ModelGenerationPlan,
    evidence_tagger: EvidenceTagger | None = None,
) -> GuidanceEvidencePool:
    """Build guidance-only evidence cards without exposing locator fields."""

    tagger = evidence_tagger or EvidenceTagger()
    entries: list[tuple[PaperEvidenceEntry, bool, str]] = []
    construction_error_count = 0
    parameter_mapping_evidence: dict[tuple[str, str], PaperEvidenceEntry] = {}

    for source_ref in build_plan_evidence_source_refs(spec):
        entries.append((_entry_from_source_ref(source_ref), False, source_ref.excerpt))

    def add_validated(entry: PaperEvidenceEntry | None, *, linked: bool) -> None:
        nonlocal construction_error_count
        if entry is None or entry.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            return
        try:
            tagger.validate_for_spec([entry], spec)
        except PaperPlanGenerationError:
            construction_error_count += 1
            return
        entries.append((entry, linked, entry.excerpt or ""))

    for entry in plan.evidence:
        add_validated(entry, linked=False)
    for block in plan.block_recommendations:
        add_validated(block.paper_reference, linked=False)
    if plan.build_steps is not None:
        for step in plan.build_steps:
            for entry in step.evidence:
                add_validated(entry, linked=True)
            for block_ref in step.block_refs:
                add_validated(block_ref.paper_reference, linked=True)
            for hint in step.configuration_hints:
                for entry in hint.evidence:
                    add_validated(entry, linked=True)

    for mapping in plan.parameter_mapping:
        mapping_entry = _resolved_parameter_mapping_evidence(mapping, spec, tagger)
        if mapping_entry is not None:
            parameter_mapping_evidence[(mapping.paper_param_name, mapping.model_param_name)] = (
                mapping_entry
            )
            entries.append((mapping_entry, True, mapping_entry.excerpt or ""))

    seen: set[tuple[object, ...]] = set()
    cards: list[GuidanceEvidenceCard] = []
    for entry, linked, summary in entries:
        key = _evidence_key(entry)
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            GuidanceEvidenceCard(
                handle=f"GEV-{len(cards) + 1:03d}",
                summary=_summary_text(summary),
                evidence=entry,
                linked_to_build_steps=linked,
            )
        )
    return GuidanceEvidencePool(
        cards=cards,
        by_handle={card.handle: card for card in cards},
        has_build_step_linked_evidence=any(card.linked_to_build_steps for card in cards),
        construction_error_count=construction_error_count,
        parameter_mapping_evidence=parameter_mapping_evidence,
    )


def parse_and_ground_guidance_draft(
    payload: dict[str, Any],
    *,
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
    targets: ControlledGuidanceTargets,
    build_steps: list[ModelBuildStep],
    requirements: list[GuidanceRequirement],
) -> GuidanceDraftResult:
    """Parse valid units, capture raw counters, and fail closed per detail."""

    raw_items = payload.get("details")
    if not isinstance(raw_items, list):
        return GuidanceDraftResult(
            details=[],
            stats=DraftAttemptStats(0, 0, 0, parse_error_count=1),
            dropped_count=0,
            downgraded_unverified_count=0,
            resolver_event_codes=[],
        )
    raw_counters = _raw_counters(raw_items)
    details: list[GuidanceDetail] = []
    dropped_count = 0
    downgraded_unverified_count = 0
    resolver_error_count = raw_counters.resolver_error_count
    resolver_event_codes: list[str] = []
    step_by_id = {step.step_id: step for step in build_steps}
    requirement_by_ref = {requirement.requirement_ref: requirement for requirement in requirements}
    accepted_detail_id_by_requirement_ref: dict[str, str] = {}

    for raw_item in raw_items:
        try:
            draft = GuidanceDetailDraftModel.model_validate(raw_item)
        except ValidationError:
            dropped_count += 1
            code = _draft_validation_resolution_code(raw_item)
            if code is not None:
                resolver_error_count += 1
                resolver_event_codes.append(code)
            continue
        if draft.requirement_ref is None:
            dropped_count += 1
            resolver_error_count += 1
            resolver_event_codes.append("requirement_ref_missing")
            continue
        requirement = requirement_by_ref.get(draft.requirement_ref)
        if requirement is None:
            dropped_count += 1
            resolver_error_count += 1
            resolver_event_codes.append("requirement_ref_unknown")
            continue
        if draft.step_id is not None and draft.step_id != requirement.step_id:
            dropped_count += 1
            resolver_error_count += 1
            resolver_event_codes.append("requirement_mismatch")
            continue
        if not targets.step_exists(requirement.step_id):
            dropped_count += 1
            continue
        if claim_mentions_other_requirement(draft.claim_text, requirement, requirements):
            dropped_count += 1
            resolver_error_count += 1
            resolver_event_codes.append("requirement_mismatch")
            continue
        draft.input_fact_refs = [
            accepted_detail_id_by_requirement_ref.get(ref, ref) for ref in draft.input_fact_refs
        ]
        step = step_by_id[requirement.step_id]
        if draft.basis == "document_extracted":
            resolution = _document_detail_from_draft(
                draft,
                requirement=requirement,
                pool=pool,
                truth_index=truth_index,
                targets=targets,
                step=step,
                ordinal=len(details) + 1,
            )
            resolver_error_count += resolution.resolver_error_count
            resolver_event_codes.extend(resolution.resolver_event_codes)
            downgraded_unverified_count += resolution.downgraded_unverified_count
            if resolution.detail is not None:
                details.append(resolution.detail)
                accepted_detail_id_by_requirement_ref[requirement.requirement_ref] = (
                    resolution.detail.detail_id
                )
            continue
        if draft.basis == "document_derived":
            detail, code = _derived_detail_from_draft(
                draft,
                requirement=requirement,
                pool=pool,
                truth_index=truth_index,
                step=step,
                ordinal=len(details) + 1,
            )
            if detail is not None:
                details.append(detail)
                accepted_detail_id_by_requirement_ref[requirement.requirement_ref] = (
                    detail.detail_id
                )
            else:
                dropped_count += 1
                resolver_error_count += 1
                if code is not None:
                    resolver_event_codes.append(code)
            continue
        if draft.basis == "engineering_choice" and draft.convention_code is not None:
            detail = _convention_detail_from_draft(
                draft,
                requirement=requirement,
                targets=targets,
                step=step,
                ordinal=len(details) + 1,
            )
            if detail is not None:
                details.append(detail)
                accepted_detail_id_by_requirement_ref[requirement.requirement_ref] = (
                    detail.detail_id
                )
            else:
                dropped_count += 1
            continue
        detail, code = _non_document_detail_from_draft(
            draft,
            requirement=requirement,
            step=step,
            ordinal=len(details) + 1,
        )
        if detail is not None:
            details.append(detail)
            accepted_detail_id_by_requirement_ref[requirement.requirement_ref] = detail.detail_id
        else:
            dropped_count += 1
            resolver_error_count += 1
            if code is not None:
                resolver_event_codes.append(code)

    return GuidanceDraftResult(
        details=details,
        stats=DraftAttemptStats(
            raw_document_claim_count=raw_counters.raw_document_claim_count,
            raw_supporting_ref_count=raw_counters.raw_supporting_ref_count,
            resolver_error_count=resolver_error_count,
            parse_error_count=0,
        ),
        dropped_count=dropped_count,
        downgraded_unverified_count=downgraded_unverified_count,
        resolver_event_codes=_unique_codes(resolver_event_codes),
    )


def synthesize_guidance_gaps(
    *,
    build_steps: list[ModelBuildStep],
    details: list[GuidanceDetail],
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
) -> list[GuidanceGap]:
    """Synthesize v2 gaps by reducing object-level requirement closure."""

    _ = pool, truth_index
    requirements = enumerate_guidance_requirements("legacy", build_steps)
    return reduce_guidance_requirements(requirements=requirements, details=details).gaps


def _draft_validation_resolution_code(raw_item: Any) -> str | None:
    if not isinstance(raw_item, dict):
        return None
    resolution = raw_item.get("resolution")
    if resolution is None:
        return None
    if not isinstance(resolution, dict):
        return "resolution_kind_invalid"
    kind = resolution.get("kind")
    if kind == "fixed":
        return _draft_fixed_resolution_code(resolution)
    if kind == "enum_selection":
        return None if _nonempty_string(resolution.get("selected")) else "resolution_missing"
    if kind == "range":
        return None
    if kind == "derivation":
        return None if isinstance(resolution.get("inputs"), list) else "derivation_input_unresolved"
    if kind == "conditional":
        return (
            None if isinstance(resolution.get("branches"), list) else "conditional_non_exhaustive"
        )
    if kind == "guided_user_decision":
        return (
            None
            if _nonempty_string(resolution.get("decision_item"))
            and _nonempty_string(resolution.get("criteria"))
            and isinstance(resolution.get("options"), list)
            else "decision_procedure_incomplete"
        )
    if kind == "environment_probe":
        return (
            None
            if _nonempty_string(resolution.get("probe_item"))
            and _nonempty_string(resolution.get("procedure"))
            and isinstance(resolution.get("result_actions"), list)
            else "probe_incomplete"
        )
    return "resolution_kind_invalid"


def _draft_fixed_resolution_code(resolution: dict[str, Any]) -> str | None:
    fixed_kind = resolution.get("fixed_kind")
    if fixed_kind == "numeric":
        if not _strict_number(resolution.get("value")) or not _nonempty_string(
            resolution.get("unit")
        ):
            return "resolution_missing"
        return None
    if fixed_kind == "block_ref":
        return None if _nonempty_string(resolution.get("selected_id")) else "resolution_missing"
    if fixed_kind in {"configuration_option", "connection_mode"}:
        token = resolution.get("value_token")
        if not isinstance(token, str) or not re.fullmatch(r"^[A-Za-z0-9]{1,40}$", token):
            return "value_token_invalid"
        return None if _nonempty_string(resolution.get("display_label")) else "resolution_missing"
    return "resolution_kind_invalid"


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _strict_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def compute_guidance_assessment(
    *,
    build_steps: list[ModelBuildStep],
    details: list[GuidanceDetail],
    gaps: list[GuidanceGap],
    pool: GuidanceEvidencePool,
) -> GuidanceAssessment:
    """Compute internal guidance assessment from reducer-owned gaps."""

    _ = details, pool
    critical_steps_list = _critical_steps(build_steps)
    blocking_gap_ids = [gap.gap_id for gap in gaps if gap.severity == "blocking"]
    if blocking_gap_ids:
        content_status = "outline_with_gaps"
    elif critical_steps_list:
        content_status = "reproducible_candidate"
    else:
        content_status = "outline_only"
    overall_status = (
        "reproducible_candidate_env_unchecked"
        if content_status == "reproducible_candidate"
        else content_status
    )
    return GuidanceAssessment(
        content_status=cast(Any, content_status),
        environment_status="not_checked",
        overall_status=cast(Any, overall_status),
        blocking_gap_ids=blocking_gap_ids,
        pending_user_choice_count=sum(
            1 for detail in details if detail.execution_closure == "guided_choice"
        ),
        pending_environment_probe_count=sum(
            1 for detail in details if detail.execution_closure == "guided_probe"
        ),
        open_requirement_count=len(blocking_gap_ids),
    )


def _document_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    requirement: GuidanceRequirement,
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
    targets: ControlledGuidanceTargets,
    step: ModelBuildStep,
    ordinal: int,
) -> GuidanceDocumentResolution:
    resolved: list[PaperEvidenceEntry] = []
    resolver_errors = 0
    resolver_event_codes: list[str] = []
    for handle in draft.supporting_evidence_refs:
        card = pool.by_handle.get(handle)
        if card is None:
            resolver_errors += 1
            resolver_event_codes.append("handle_no_match")
            continue
        resolved.append(card.evidence)
    resolved = _dedupe_evidence(resolved)
    high_risk_tokens = high_risk_claim_tokens(draft.claim_text, step)
    resolution = _domain_resolution(draft)
    closure, code = closure_from_resolution(
        basis=draft.basis,
        target=requirement.target,
        resolution=resolution,
        input_fact_refs=draft.input_fact_refs,
        punt_reason_code=draft.punt_reason_code,
        step=step,
    )
    if closure is None:
        return GuidanceDocumentResolution(
            detail=None,
            resolver_error_count=resolver_errors + 1,
            resolver_event_codes=_unique_codes(
                [*resolver_event_codes, code or "resolution_missing"]
            ),
            downgraded_unverified_count=0,
        )
    if not resolved or not truth_index.contains_all(high_risk_tokens):
        if resolved:
            resolver_event_codes.append("grounding_whitelist_no_match")
        return GuidanceDocumentResolution(
            detail=_claim_unverified_detail(
                requirement=requirement,
                ordinal=ordinal,
            ),
            resolver_error_count=resolver_errors + (0 if resolved else 1),
            resolver_event_codes=_unique_codes(resolver_event_codes),
            downgraded_unverified_count=1,
        )
    return GuidanceDocumentResolution(
        detail=GuidanceDetail(
            detail_id=f"GD-{ordinal:03d}",
            step_id=requirement.step_id,
            detail_kind=cast(Any, detail_kind_for_target(requirement.target.target_kind)),
            basis="document_extracted",
            actionability=actionability_for_closure(closure),
            display_text=render_detail_display_text(
                basis="document_extracted",
                target=requirement.target,
                resolution=resolution,
            ),
            evidence=resolved,
            convention_code=None,
            confirmation_reason_code=None,
            target=requirement.target,
            obligation_kind=requirement.obligation_kind,
            resolution=resolution,
            execution_closure=closure,
            input_fact_refs=list(draft.input_fact_refs),
            punt_reason_code=None,
        ),
        resolver_error_count=resolver_errors,
        resolver_event_codes=_unique_codes(resolver_event_codes),
        downgraded_unverified_count=0,
    )


def _derived_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    requirement: GuidanceRequirement,
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
    step: ModelBuildStep,
    ordinal: int,
) -> tuple[GuidanceDetail | None, str | None]:
    if not draft.input_fact_refs:
        return None, "derivation_input_unresolved"
    resolved: list[PaperEvidenceEntry] = []
    for handle in draft.supporting_evidence_refs:
        card = pool.by_handle.get(handle)
        if card is None:
            return None, "input_fact_ref_unknown"
        resolved.append(card.evidence)
    resolved = _dedupe_evidence(resolved)
    high_risk_tokens = high_risk_claim_tokens(draft.claim_text, step)
    if not resolved or not truth_index.contains_all(high_risk_tokens):
        return (
            _claim_unverified_detail(requirement=requirement, ordinal=ordinal),
            "grounding_whitelist_no_match" if resolved else "input_fact_ref_unknown",
        )
    resolution = _domain_resolution(draft)
    closure, code = closure_from_resolution(
        basis=draft.basis,
        target=requirement.target,
        resolution=resolution,
        input_fact_refs=draft.input_fact_refs,
        punt_reason_code=draft.punt_reason_code,
        step=step,
    )
    if closure is None:
        return None, code
    return (
        GuidanceDetail(
            detail_id=f"GD-{ordinal:03d}",
            step_id=requirement.step_id,
            detail_kind=cast(Any, detail_kind_for_target(requirement.target.target_kind)),
            basis="document_derived",
            actionability=actionability_for_closure(closure),
            display_text=render_detail_display_text(
                basis="document_derived",
                target=requirement.target,
                resolution=resolution,
            ),
            evidence=resolved,
            convention_code=None,
            confirmation_reason_code=None,
            target=requirement.target,
            obligation_kind=requirement.obligation_kind,
            resolution=resolution,
            execution_closure=closure,
            input_fact_refs=list(draft.input_fact_refs),
            punt_reason_code=None,
        ),
        None,
    )


def _convention_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    requirement: GuidanceRequirement,
    targets: ControlledGuidanceTargets,
    step: ModelBuildStep,
    ordinal: int,
) -> GuidanceDetail | None:
    code = draft.convention_code
    if code not in CONVENTION_TEMPLATES:
        return None
    detail_kind, _actionability = CONVENTION_TEMPLATES[code]
    if _unsafe_freeform_text(draft.target):
        return None
    resolution = _domain_resolution(draft)
    closure, machine_code = closure_from_resolution(
        basis="engineering_choice",
        target=requirement.target,
        resolution=resolution,
        input_fact_refs=draft.input_fact_refs,
        punt_reason_code=draft.punt_reason_code,
        step=step,
    )
    if closure is None:
        _ = machine_code
        return None
    target = targets.label(requirement.step_id, draft.target)
    return GuidanceDetail(
        detail_id=f"GD-{ordinal:03d}",
        step_id=requirement.step_id,
        detail_kind=detail_kind,
        basis="engineering_choice",
        actionability=actionability_for_closure(closure),
        display_text=(
            convention_display_text(code, target)
            if resolution is None
            else render_detail_display_text(
                basis="engineering_choice",
                target=requirement.target,
                resolution=resolution,
            )
        ),
        evidence=[],
        convention_code=code,
        confirmation_reason_code=None,
        target=requirement.target,
        obligation_kind=requirement.obligation_kind,
        resolution=resolution,
        execution_closure=closure,
        input_fact_refs=list(draft.input_fact_refs),
        punt_reason_code=None,
    )


def _non_document_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    requirement: GuidanceRequirement,
    step: ModelBuildStep,
    ordinal: int,
) -> tuple[GuidanceDetail | None, str | None]:
    if draft.supporting_evidence_refs:
        return None, "non_document_evidence_present"
    resolution = _domain_resolution(draft)
    closure, code = closure_from_resolution(
        basis=draft.basis,
        target=requirement.target,
        resolution=resolution,
        input_fact_refs=draft.input_fact_refs,
        punt_reason_code=draft.punt_reason_code,
        step=step,
    )
    if closure is None:
        return None, code
    return (
        GuidanceDetail(
            detail_id=f"GD-{ordinal:03d}",
            step_id=requirement.step_id,
            detail_kind=cast(Any, detail_kind_for_target(requirement.target.target_kind)),
            basis=draft.basis,
            actionability=actionability_for_closure(closure),
            display_text=render_detail_display_text(
                basis=draft.basis,
                target=requirement.target,
                resolution=resolution,
                punt_reason_code=draft.punt_reason_code,
            ),
            evidence=[],
            convention_code=None,
            confirmation_reason_code=(
                draft.confirmation_reason_code
                if draft.confirmation_reason_code in CONFIRMATION_REASON_TEMPLATES
                else None
            ),
            target=requirement.target,
            obligation_kind=requirement.obligation_kind,
            resolution=resolution,
            execution_closure=closure,
            input_fact_refs=list(draft.input_fact_refs),
            punt_reason_code=draft.punt_reason_code,
        ),
        None,
    )


def _domain_resolution(draft: GuidanceDetailDraftModel) -> GuidanceResolution | None:
    return resolution_to_domain(draft.resolution)


def _claim_unverified_detail(
    *,
    requirement: GuidanceRequirement,
    ordinal: int,
) -> GuidanceDetail:
    return GuidanceDetail(
        detail_id=f"GD-{ordinal:03d}",
        step_id=requirement.step_id,
        detail_kind=cast(Any, detail_kind_for_target(requirement.target.target_kind)),
        basis="document_claim_unverified",
        actionability="blocked_pending_confirmation",
        display_text=render_detail_display_text(
            basis="document_claim_unverified",
            target=requirement.target,
            resolution=None,
        ),
        evidence=[],
        convention_code=None,
        confirmation_reason_code="document_evidence_unverified",
        target=requirement.target,
        obligation_kind=requirement.obligation_kind,
        resolution=None,
        execution_closure="open",
        input_fact_refs=[],
        punt_reason_code=None,
    )


def _raw_counters(raw_items: list[Any]) -> DraftAttemptStats:
    document_claim_count = 0
    ref_count = 0
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if item.get("basis") in {"document_extracted", "document_derived"}:
            document_claim_count += 1
        refs = item.get("supporting_evidence_refs")
        if isinstance(refs, list):
            ref_count += sum(1 for ref in refs if isinstance(ref, str))
    return DraftAttemptStats(
        raw_document_claim_count=document_claim_count,
        raw_supporting_ref_count=ref_count,
        resolver_error_count=0,
    )


def _critical_steps(build_steps: list[ModelBuildStep]) -> list[ModelBuildStep]:
    return critical_steps(build_steps)


def _is_critical_step(step: ModelBuildStep) -> bool:
    return step in critical_steps([step])


def _block_ref_is_real(block_ref: StepBlockRef) -> bool:
    text = " ".join(
        part for part in (block_ref.block_type, block_ref.purpose, block_ref.library_path) if part
    ).casefold()
    if any(term in text for term in REAL_BLOCK_ALLOW_TERMS):
        return True
    return not any(term in text for term in DISPLAY_BLOCK_TERMS)


def _connection_is_display_only(step: ModelBuildStep, hint: ConnectionHint) -> bool:
    refs = {block_ref.block_ref_id: block_ref for block_ref in step.block_refs}
    blocks = [refs.get(hint.from_block_ref), refs.get(hint.to_block_ref)]
    present = [block for block in blocks if block is not None]
    return bool(present) and all(not _block_ref_is_real(block) for block in present)


def _required_object_coverage(
    step: ModelBuildStep,
    covered_params: set[tuple[str, str]],
) -> list[tuple[str, str, bool]]:
    return required_object_coverage(step, covered_params)


def _unique_codes(codes: list[str]) -> list[str]:
    return sorted(set(codes))


def _validator_dropped_unverified_count(
    candidate: ModelGenerationPlan,
    validation: GuidanceSemanticValidationResult,
) -> int:
    if candidate.build_guidance is None:
        return 0
    details_by_id = {detail.detail_id: detail for detail in candidate.build_guidance.details}
    count = 0
    for action in validation.item_actions:
        if action.item_type != "detail" or action.action != "drop":
            continue
        detail = details_by_id.get(action.item_id or "")
        if (
            detail is not None
            and detail.basis == "user_confirmation_required"
            and detail.confirmation_reason_code == "document_evidence_unverified"
        ):
            count += 1
    return count


def _terminal_status_and_reason(
    attempts: list[DraftAttemptStats],
    *,
    pool: GuidanceEvidencePool,
    call_count: int,
    attempt_records: list[GuidanceAttemptTelemetry],
) -> tuple[Literal["generation_failed", "no_document_basis"], GuidanceFailureReason]:
    if not attempts:
        return "generation_failed", "retry_cap_exhausted"
    if any(stats.parse_error_count for stats in attempts):
        finish_reason = _last_parse_error_finish_reason(attempt_records)
        return "generation_failed", llm_unparseable_reason(finish_reason)
    if any(stats.raw_document_claim_count > 0 for stats in attempts):
        return "generation_failed", "evidence_resolution_failed"
    if any(stats.resolver_error_count > 0 for stats in attempts):
        return "generation_failed", "evidence_resolution_failed"
    if pool.construction_error_count > 0:
        return "generation_failed", "evidence_card_unavailable"
    if len(attempts) >= GUIDANCE_FULL_ATTEMPTS and all(
        stats.raw_document_claim_count == 0 for stats in attempts
    ):
        if not pool.cards:
            return "generation_failed", "zero_document_claims_empty_evidence_pool"
        if not pool.has_build_step_linked_evidence:
            return "generation_failed", "zero_document_claims_unlinked_evidence_pool"
    if call_count >= GUIDANCE_HARD_CALL_CAP:
        return "generation_failed", "retry_cap_exhausted"
    return "generation_failed", "evidence_resolution_failed"


def _last_parse_error_finish_reason(
    attempt_records: list[GuidanceAttemptTelemetry],
) -> str | None:
    for attempt in reversed(attempt_records):
        if attempt.parse_error_count > 0:
            return attempt.finish_reason
    return None


def _entry_from_source_ref(source_ref: PlanEvidenceSourceRef) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=source_ref.document_id,
        paper_section_id=source_ref.locator_id
        if source_ref.locator_kind == "paper_section_id"
        else None,
        equation_id=source_ref.locator_id if source_ref.locator_kind == "equation_id" else None,
        figure_id=source_ref.locator_id if source_ref.locator_kind == "figure_id" else None,
        excerpt=source_ref.excerpt,
        missing_param_prompt_id=None,
    )


def _resolved_parameter_mapping_evidence(
    mapping: ParameterMapping,
    spec: PaperSpec,
    tagger: EvidenceTagger,
) -> PaperEvidenceEntry | None:
    if mapping.source is not EvidenceSource.DOCUMENT_EXTRACTED:
        return None
    if mapping.value == MISSING_VALUE_SENTINEL:
        return None
    parameters = [
        parameter
        for parameter in spec.parameter_table
        if _parameter_matches_mapping(parameter, mapping)
    ]
    for parameter in parameters:
        for entry in spec.evidence:
            if entry.document_id != parameter.document_id:
                continue
            if not _evidence_mentions_parameter(entry, parameter, mapping):
                continue
            try:
                tagger.validate_for_spec([entry], spec)
            except PaperPlanGenerationError:
                continue
            return entry
    return None


def _parameter_matches_mapping(parameter: ParameterEntry, mapping: ParameterMapping) -> bool:
    if parameter.source is not EvidenceSource.DOCUMENT_EXTRACTED:
        return False
    names = {_canonicalize(parameter.name), _canonicalize(parameter.symbol)}
    if _canonicalize(mapping.paper_param_name) not in names:
        return False
    if _canonicalize(parameter.value) != _canonicalize(mapping.value):
        return False
    return _canonicalize(parameter.unit) == _canonicalize(mapping.unit or "")


def _evidence_mentions_parameter(
    entry: PaperEvidenceEntry,
    parameter: ParameterEntry,
    mapping: ParameterMapping,
) -> bool:
    text = _canonicalize(entry.excerpt or "")
    if not text:
        return False
    needles = [
        parameter.name,
        parameter.symbol,
        parameter.value,
        parameter.unit,
        mapping.paper_param_name,
    ]
    return any(_canonicalize(needle) and _canonicalize(needle) in text for needle in needles)


def _dedupe_details(details: list[GuidanceDetail]) -> list[GuidanceDetail]:
    return [replace(detail, detail_id=f"GD-{index:03d}") for index, detail in enumerate(details, 1)]


def _dedupe_evidence(entries: list[PaperEvidenceEntry]) -> list[PaperEvidenceEntry]:
    seen: set[tuple[object, ...]] = set()
    result: list[PaperEvidenceEntry] = []
    for entry in entries:
        key = _evidence_key(entry)
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def _summary_text(value: str | None) -> str:
    cleaned = _clean_display_text(value or "")
    return cleaned[:240] if cleaned else "Document evidence excerpt available."
