"""Fail-closed generation for model build guidance."""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    BuildGuidance,
    ConfigurationHint,
    ConnectionHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceGap,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import PaperSpec, ParameterEntry
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_builder import build_messages_for_build_guidance
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

GuidanceFailureReason = Literal[
    "zero_document_claims_empty_evidence_pool",
    "zero_document_claims_unlinked_evidence_pool",
    "llm_unparseable",
    "evidence_resolution_failed",
    "retry_cap_exhausted",
    "build_steps_unavailable",
    "evidence_card_unavailable",
]

DetailKind = Literal[
    "block_selection",
    "subsystem_internal_structure",
    "connection",
    "parameter_value",
    "configuration",
    "verification",
    "gap_notice",
]
DetailBasis = Literal[
    "document_extracted",
    "engineering_convention",
    "user_confirmation_required",
]

CONVENTION_TEMPLATES: dict[str, tuple[DetailKind, Literal["actionable", "notice_only"]]] = {
    "pi_controller_standard_structure": ("subsystem_internal_structure", "actionable"),
    "pid_controller_standard_structure": ("subsystem_internal_structure", "actionable"),
    "clarke_transform_structure": ("subsystem_internal_structure", "notice_only"),
    "park_transform_structure": ("subsystem_internal_structure", "notice_only"),
}

CONFIRMATION_REASON_TEMPLATES: dict[str, str] = {
    "missing_parameter_value": "Confirm the parameter value for {target}; check the source model or paper table.",
    "library_variant_unresolved": "Confirm the Simulink block variant for {target}; check the local library version.",
    "toolbox_unverified": "Confirm toolbox availability for {target}; check the installed MATLAB products.",
    "solver_unverified": "Confirm the solver choice for {target}; check the reproduction environment.",
    "sample_time_unverified": "Confirm sample-time handling for {target}; check the source model setup.",
    "connection_detail_missing": "Confirm the connection detail for {target}; inspect the source diagram or model.",
    "initial_condition_unverified": "Confirm initial-condition handling for {target}; check the source model setup.",
    "switching_frequency_unverified": "Confirm switching-frequency handling for {target}; check the source model setup.",
    "simulation_time_unverified": "Confirm simulation-time handling for {target}; check the source model setup.",
    "configuration_unverified": "Confirm the configuration detail for {target}; check the source model setup.",
    "document_evidence_unverified": "Confirm {target}; the cited paper evidence could not be verified for this detail.",
    "engineering_decision_unverified": "Confirm the engineering decision for {target}; check the source model setup.",
}

GAP_SYNTHESIS_RULES: dict[
    str, tuple[str, Literal["engineering_convention", "user_confirmation_required"], str]
] = {
    "block": ("missing_support_component", "user_confirmation_required", "blocking"),
    "parameter": ("missing_parameter_value", "user_confirmation_required", "blocking"),
    "connection": ("missing_connection_detail", "user_confirmation_required", "blocking"),
    "configuration": ("missing_configuration_detail", "user_confirmation_required", "blocking"),
    "blocked_detail": ("insufficient_document_evidence", "user_confirmation_required", "blocking"),
}

NON_NUMERIC_ENGINEERING_TERMS = frozenset(
    {
        "anti-windup",
        "antiwindup",
        "限幅",
        "saturation",
        "limiter",
        "discrete",
        "continuous",
        "离散",
        "连续",
        "derivative filter",
        "d filter",
        "微分滤波",
        "scaling",
        "缩放",
        "phase sequence",
        "相序",
        "angle source",
        "角度来源",
        "pwm",
        "spwm",
        "svpwm",
        "igbt",
        "mosfet",
        "器件类型",
        "controller variant",
        "控制器变体",
    }
)
TOOL_ENV_TERMS = frozenset(
    {
        "ode15s",
        "ode45",
        "fixed-step",
        "variable-step",
        "powergui",
        "simscape",
        "simpowersystems",
        "specialized power systems",
        "sample time",
        "solver",
        "toolbox",
    }
)
DISPLAY_BLOCK_TERMS = frozenset(
    {
        "scope",
        "display",
        "dashboard",
        "viewer",
        "plot",
        "to workspace",
        "measurement",
        "meter",
        "voltage measurement",
        "current measurement",
        "voltmeter",
        "ammeter",
    }
)
REAL_BLOCK_ALLOW_TERMS = frozenset(
    {
        "machine",
        "motor",
        "generator",
        "converter",
        "inverter",
        "rectifier",
        "controller",
        "transform",
        "filter",
        "plant",
        "power",
        "source",
        "load",
        "pwm",
        "breaker",
        "fault",
    }
)

NUMBER_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9_.+-])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?\s*"
    r"(?:[A-Za-zµμΩ°/%]+|pu|标幺|秒|毫秒|千瓦|兆瓦|伏|安|欧姆|赫兹)"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
PATH_RE = re.compile(r"\b(?:simulink|simscape|powerlib|sps|ee_lib)[A-Za-z0-9_ ./\\-]+", re.I)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class GuidanceEvidenceCard:
    """Private evidence card exposed to the guidance LLM."""

    handle: str
    summary: str
    evidence: PaperEvidenceEntry
    linked_to_build_steps: bool


@dataclass(frozen=True)
class GuidanceEvidencePool:
    """Resolved guidance evidence pool and construction metadata."""

    cards: list[GuidanceEvidenceCard]
    by_handle: dict[str, GuidanceEvidenceCard]
    has_build_step_linked_evidence: bool
    construction_error_count: int
    parameter_mapping_evidence: dict[tuple[str, str], PaperEvidenceEntry]


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


class GuidanceDetailDraftModel(BaseModel):
    """Private per-detail draft DTO."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    detail_kind: DetailKind
    basis: DetailBasis
    claim_text: str = Field(min_length=1)
    supporting_evidence_refs: list[str] = Field(default_factory=list)
    convention_code: str | None = Field(default=None, min_length=1)
    target: str | None = Field(default=None, min_length=1)
    confirmation_reason_code: str | None = Field(default=None, min_length=1)
    direction_hint: str | None = Field(default=None, min_length=1)


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
    ) -> None:
        self._text_provider = text_provider
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._evidence_tagger = evidence_tagger or EvidenceTagger()

    async def generate(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        """Return the plan with generated guidance or an honest terminal status."""

        if plan.build_steps is None:
            self._log_terminal(
                "generation_failed",
                "build_steps_unavailable",
                retry_count=0,
            )
            return replace(plan, build_guidance=None, guidance_status="generation_failed")

        pool = build_guidance_evidence_pool(spec, plan, self._evidence_tagger)
        truth_index = GroundingTruthIndex.from_spec_plan(spec, plan, pool)
        targets = ControlledGuidanceTargets(plan.build_steps)
        attempts: list[DraftAttemptStats] = []
        retry_context = GuidanceRetryContext()

        for attempt_index in range(GUIDANCE_FULL_ATTEMPTS):
            try:
                payload = await self._call_llm_json(
                    build_messages_for_build_guidance(plan, pool.cards),
                    retry_context,
                )
            except GuidanceRetryExceeded:
                break
            except Exception:
                attempts.append(
                    DraftAttemptStats(
                        raw_document_claim_count=0,
                        raw_supporting_ref_count=0,
                        resolver_error_count=0,
                        parse_error_count=1,
                    )
                )
                continue

            result = parse_and_ground_guidance_draft(
                payload,
                pool=pool,
                truth_index=truth_index,
                targets=targets,
                build_steps=plan.build_steps,
            )
            attempts.append(result.stats)
            document_details = [
                detail for detail in result.details if detail.basis == "document_extracted"
            ]
            if not document_details:
                continue

            gaps = synthesize_guidance_gaps(
                build_steps=plan.build_steps,
                details=result.details,
                pool=pool,
                truth_index=truth_index,
            )
            assessment = compute_guidance_assessment(
                build_steps=plan.build_steps,
                details=result.details,
                gaps=gaps,
                pool=pool,
            )
            guidance = BuildGuidance(
                version="v1",
                assessment=assessment,
                details=_dedupe_details(result.details),
                gaps=gaps,
            )
            self._log_success(
                guidance,
                retry_count=attempt_index,
                critical_step_count=len(_critical_steps(plan.build_steps)),
            )
            return replace(
                plan,
                build_guidance=guidance,
                guidance_status="generated",
            )

        status, reason = _terminal_status_and_reason(
            attempts,
            pool=pool,
            call_count=retry_context.call_count,
        )
        self._log_terminal(status, reason, retry_count=max(0, len(attempts) - 1))
        return replace(plan, build_guidance=None, guidance_status=status)

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        retry_context: GuidanceRetryContext,
    ) -> dict[str, Any]:
        retry_context.before_call()
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(
                "paper_build_guidance_json_decode_failed reason_code={}",
                "llm_unparseable",
            )
            raise
        if not isinstance(payload, dict):
            raise TypeError("guidance_json_top_level_must_be_object")
        return payload

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
        except Exception:
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
        entry = _resolved_parameter_mapping_evidence(mapping, spec, tagger)
        if entry is not None:
            parameter_mapping_evidence[(mapping.paper_param_name, mapping.model_param_name)] = entry
            entries.append((entry, True, entry.excerpt or ""))

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


class GroundingTruthIndex:
    """Canonicalized truth surface for high-risk guidance claims."""

    def __init__(self, truth_texts: list[str]) -> None:
        self._truth = [_canonicalize(text) for text in truth_texts if _canonicalize(text)]

    @classmethod
    def from_spec_plan(
        cls,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
        pool: GuidanceEvidencePool,
    ) -> GroundingTruthIndex:
        truth_texts: list[str] = []
        for entry in spec.evidence:
            if entry.source is EvidenceSource.DOCUMENT_EXTRACTED and entry.excerpt:
                truth_texts.append(entry.excerpt)
        for equation in spec.equations:
            truth_texts.append(equation.latex_or_text)
        for figure in spec.figure_locations:
            truth_texts.append(figure.caption)
        for parameter in spec.parameter_table:
            if parameter.source is EvidenceSource.DOCUMENT_EXTRACTED:
                truth_texts.extend(_parameter_truth_texts(parameter))
        for card in pool.cards:
            if card.evidence.excerpt:
                truth_texts.append(card.evidence.excerpt)
        for mapping in plan.parameter_mapping:
            if (mapping.paper_param_name, mapping.model_param_name) in pool.parameter_mapping_evidence:
                truth_texts.extend(_mapping_truth_texts(mapping))
        for block in plan.block_recommendations:
            if _evidence_key(block.paper_reference) in {
                _evidence_key(card.evidence) for card in pool.cards
            }:
                truth_texts.extend([block.block_type, block.purpose])
        return cls(truth_texts)

    def contains(self, token: str) -> bool:
        canonical = _canonicalize(token)
        if not canonical:
            return True
        return any(canonical in truth for truth in self._truth)

    def contains_all(self, tokens: list[str]) -> bool:
        return all(self.contains(token) for token in tokens)


class ControlledGuidanceTargets:
    """Controlled target labels for details and confirmations."""

    def __init__(self, build_steps: list[ModelBuildStep]) -> None:
        self._step_ids = {step.step_id for step in build_steps}
        self._targets: dict[str, str] = {"plan": "the overall model plan"}
        for step in build_steps:
            self._targets[step.step_id] = f"step {step.step_id}"
            for block_ref in step.block_refs:
                self._targets[block_ref.block_ref_id] = f"block {block_ref.block_ref_id}"
            for parameter_ref in step.parameter_refs:
                key = _parameter_ref_key(parameter_ref)
                self._targets[key] = f"parameter mapping {parameter_ref.paper_param_name}"
            for index, hint in enumerate(step.configuration_hints, start=1):
                self._targets[_configuration_key(step.step_id, hint, index)] = (
                    f"configuration for {step.step_id}"
                )

    def step_exists(self, step_id: str) -> bool:
        return step_id in self._step_ids

    def label(self, step_id: str, target: str | None) -> str:
        if target is not None and target in self._targets:
            return self._targets[target]
        if step_id in self._targets:
            return self._targets[step_id]
        return "the referenced step"


def parse_and_ground_guidance_draft(
    payload: dict[str, Any],
    *,
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
    targets: ControlledGuidanceTargets,
    build_steps: list[ModelBuildStep],
) -> GuidanceDraftResult:
    """Parse valid units, capture raw counters, and fail closed per detail."""

    raw_items = payload.get("details")
    if not isinstance(raw_items, list):
        return GuidanceDraftResult(
            details=[],
            stats=DraftAttemptStats(0, 0, 0, parse_error_count=1),
            dropped_count=0,
        )
    raw_counters = _raw_counters(raw_items)
    details: list[GuidanceDetail] = []
    dropped_count = 0
    resolver_error_count = raw_counters.resolver_error_count
    step_by_id = {step.step_id: step for step in build_steps}
    seen_keys: set[tuple[str, str, str, str]] = set()

    for raw_item in raw_items:
        try:
            draft = GuidanceDetailDraftModel.model_validate(raw_item)
        except ValidationError:
            dropped_count += 1
            continue
        if not targets.step_exists(draft.step_id):
            dropped_count += 1
            continue
        step = step_by_id[draft.step_id]
        key = (
            draft.step_id,
            draft.detail_kind,
            draft.basis,
            _canonicalize(draft.target or draft.claim_text),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if draft.basis == "document_extracted":
            detail, resolver_errors = _document_detail_from_draft(
                draft,
                pool=pool,
                truth_index=truth_index,
                targets=targets,
                step=step,
                ordinal=len(details) + 1,
            )
            resolver_error_count += resolver_errors
            if detail is not None:
                details.append(detail)
            continue
        if draft.basis == "engineering_convention":
            detail = _convention_detail_from_draft(
                draft,
                targets=targets,
                ordinal=len(details) + 1,
            )
            if detail is not None:
                details.append(detail)
            else:
                dropped_count += 1
            continue
        detail = _confirmation_detail_from_draft(
            draft,
            targets=targets,
            ordinal=len(details) + 1,
        )
        if detail is not None:
            details.append(detail)
        else:
            dropped_count += 1

    return GuidanceDraftResult(
        details=details,
        stats=DraftAttemptStats(
            raw_document_claim_count=raw_counters.raw_document_claim_count,
            raw_supporting_ref_count=raw_counters.raw_supporting_ref_count,
            resolver_error_count=resolver_error_count,
            parse_error_count=0,
        ),
        dropped_count=dropped_count,
    )


def synthesize_guidance_gaps(
    *,
    build_steps: list[ModelBuildStep],
    details: list[GuidanceDetail],
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
) -> list[GuidanceGap]:
    """Synthesize object-granular gaps from deterministic rules."""

    _ = truth_index
    gaps: list[GuidanceGap] = []
    covered_params = set(pool.parameter_mapping_evidence)
    document_detail_steps = {
        detail.step_id for detail in details if detail.basis == "document_extracted"
    }
    for step in _critical_steps(build_steps):
        for kind, object_key, covered in _required_object_coverage(step, covered_params):
            if covered:
                continue
            gaps.append(
                _gap_from_rule(
                    "GAP",
                    len(gaps) + 1,
                    kind,
                    step.step_id,
                    object_key,
                )
            )
        if step.step_id not in document_detail_steps:
            gaps.append(
                _gap_from_rule(
                    "GAP",
                    len(gaps) + 1,
                    "blocked_detail",
                    step.step_id,
                    step.step_id,
                )
            )
    for detail in details:
        if detail.actionability != "blocked_pending_confirmation":
            continue
        if any(gap.step_id == detail.step_id and gap.gap_kind == "insufficient_document_evidence" for gap in gaps):
            continue
        gaps.append(
            _gap_from_rule(
                "GAP",
                len(gaps) + 1,
                "blocked_detail",
                detail.step_id,
                detail.step_id,
            )
        )
    return gaps


def compute_guidance_assessment(
    *,
    build_steps: list[ModelBuildStep],
    details: list[GuidanceDetail],
    gaps: list[GuidanceGap],
    pool: GuidanceEvidencePool,
) -> GuidanceAssessment:
    """Compute internal guidance assessment without producing ready status."""

    critical_steps = _critical_steps(build_steps)
    blocking_gap_ids = [gap.gap_id for gap in gaps if gap.severity == "blocking"]
    critical_confirmation_count = sum(
        1
        for detail in details
        if detail.actionability == "blocked_pending_confirmation"
        and any(step.step_id == detail.step_id for step in critical_steps)
    )
    if blocking_gap_ids:
        content_status = "outline_with_gaps"
    elif pool.has_build_step_linked_evidence and critical_steps and critical_confirmation_count == 0:
        content_status = "reproducible_candidate"
    else:
        content_status = "outline_only"
    overall_status = (
        "reproducible_candidate_env_unchecked"
        if content_status == "reproducible_candidate"
        else content_status
    )
    return GuidanceAssessment(
        content_status=content_status,
        environment_status="not_checked",
        overall_status=overall_status,
        blocking_gap_ids=blocking_gap_ids,
    )


def _document_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    pool: GuidanceEvidencePool,
    truth_index: GroundingTruthIndex,
    targets: ControlledGuidanceTargets,
    step: ModelBuildStep,
    ordinal: int,
) -> tuple[GuidanceDetail | None, int]:
    resolved: list[PaperEvidenceEntry] = []
    resolver_errors = 0
    for handle in draft.supporting_evidence_refs:
        card = pool.by_handle.get(handle)
        if card is None:
            resolver_errors += 1
            continue
        resolved.append(card.evidence)
    resolved = _dedupe_evidence(resolved)
    high_risk_tokens = high_risk_claim_tokens(draft.claim_text, step)
    if not resolved or not truth_index.contains_all(high_risk_tokens):
        return (
            _confirmation_detail(
                step_id=draft.step_id,
                detail_kind=draft.detail_kind,
                reason_code="document_evidence_unverified",
                target=targets.label(draft.step_id, draft.target),
                ordinal=ordinal,
            ),
            resolver_errors + (0 if resolved else 1),
        )
    return (
        GuidanceDetail(
            detail_id=f"GD-{ordinal:03d}",
            step_id=draft.step_id,
            detail_kind=draft.detail_kind,
            basis="document_extracted",
            actionability="actionable",
            display_text=_clean_display_text(draft.claim_text),
            evidence=resolved,
            convention_code=None,
            confirmation_reason_code=None,
        ),
        resolver_errors,
    )


def _convention_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    targets: ControlledGuidanceTargets,
    ordinal: int,
) -> GuidanceDetail | None:
    code = draft.convention_code
    if code not in CONVENTION_TEMPLATES:
        return None
    detail_kind, actionability = CONVENTION_TEMPLATES[code]
    if _unsafe_freeform_text(draft.target):
        return None
    target = targets.label(draft.step_id, draft.target)
    if code == "pi_controller_standard_structure":
        text = f"Use a standard PI structure for {target}: error summing plus proportional and integral paths."
    elif code == "pid_controller_standard_structure":
        text = f"Use a standard PID structure for {target}: error summing plus proportional, integral, and derivative paths."
    elif code == "clarke_transform_structure":
        text = f"Treat Clarke transform details for {target} as a basic structure notice; confirm scaling and phase convention separately."
    else:
        text = f"Treat Park transform details for {target} as a basic structure notice; confirm angle source and convention separately."
    return GuidanceDetail(
        detail_id=f"GD-{ordinal:03d}",
        step_id=draft.step_id,
        detail_kind=detail_kind,
        basis="engineering_convention",
        actionability=actionability,
        display_text=text,
        evidence=[],
        convention_code=code,
        confirmation_reason_code=None,
    )


def _confirmation_detail_from_draft(
    draft: GuidanceDetailDraftModel,
    *,
    targets: ControlledGuidanceTargets,
    ordinal: int,
) -> GuidanceDetail | None:
    reason_code = draft.confirmation_reason_code
    if reason_code not in CONFIRMATION_REASON_TEMPLATES:
        return None
    direction_hint = (
        None if _unsafe_direction_hint(draft.direction_hint) else draft.direction_hint
    )
    target = targets.label(draft.step_id, draft.target)
    text = CONFIRMATION_REASON_TEMPLATES[reason_code].format(target=target)
    if direction_hint:
        text = f"{text} Check: {_clean_display_text(direction_hint)}."
    return GuidanceDetail(
        detail_id=f"GD-{ordinal:03d}",
        step_id=draft.step_id,
        detail_kind=draft.detail_kind,
        basis="user_confirmation_required",
        actionability="blocked_pending_confirmation",
        display_text=text,
        evidence=[],
        convention_code=None,
        confirmation_reason_code=reason_code,
    )


def _confirmation_detail(
    *,
    step_id: str,
    detail_kind: DetailKind,
    reason_code: str,
    target: str,
    ordinal: int,
) -> GuidanceDetail:
    return GuidanceDetail(
        detail_id=f"GD-{ordinal:03d}",
        step_id=step_id,
        detail_kind=detail_kind,
        basis="user_confirmation_required",
        actionability="blocked_pending_confirmation",
        display_text=CONFIRMATION_REASON_TEMPLATES[reason_code].format(target=target),
        evidence=[],
        convention_code=None,
        confirmation_reason_code=reason_code,
    )


def _raw_counters(raw_items: list[Any]) -> DraftAttemptStats:
    document_claim_count = 0
    ref_count = 0
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if item.get("basis") == "document_extracted":
            document_claim_count += 1
        refs = item.get("supporting_evidence_refs")
        if isinstance(refs, list):
            ref_count += sum(1 for ref in refs if isinstance(ref, str))
    return DraftAttemptStats(
        raw_document_claim_count=document_claim_count,
        raw_supporting_ref_count=ref_count,
        resolver_error_count=0,
    )


def high_risk_claim_tokens(claim_text: str, step: ModelBuildStep) -> list[str]:
    """Extract high-risk tokens that require grounding truth hits."""

    tokens: list[str] = []
    tokens.extend(match.group(0) for match in NUMBER_UNIT_RE.finditer(claim_text))
    tokens.extend(match.group(0) for match in PATH_RE.finditer(claim_text))
    lowered = claim_text.casefold()
    for term in NON_NUMERIC_ENGINEERING_TERMS | TOOL_ENV_TERMS:
        if term.casefold() in lowered:
            tokens.append(term)
    for block_ref in step.block_refs:
        _append_if_present(tokens, claim_text, block_ref.block_type)
        if block_ref.library_path:
            _append_if_present(tokens, claim_text, block_ref.library_path)
    for parameter_ref in step.parameter_refs:
        _append_if_present(tokens, claim_text, parameter_ref.paper_param_name)
        _append_if_present(tokens, claim_text, parameter_ref.model_param_name)
    for connection in step.connection_hints:
        _append_if_present(tokens, claim_text, connection.from_block_ref)
        _append_if_present(tokens, claim_text, connection.to_block_ref)
        if connection.from_port:
            _append_if_present(tokens, claim_text, connection.from_port)
        if connection.to_port:
            _append_if_present(tokens, claim_text, connection.to_port)
        if connection.signal_meaning:
            _append_if_present(tokens, claim_text, connection.signal_meaning)
    return _unique_nonempty(tokens)


def _append_if_present(tokens: list[str], text: str, value: str | None) -> None:
    cleaned = _clean_text(value)
    if cleaned and _canonicalize(cleaned) in _canonicalize(text):
        tokens.append(cleaned)


def _critical_steps(build_steps: list[ModelBuildStep]) -> list[ModelBuildStep]:
    return [step for step in build_steps if _is_critical_step(step)]


def _is_critical_step(step: ModelBuildStep) -> bool:
    if step.parameter_refs or step.configuration_hints:
        return True
    if step.connection_hints and not all(_connection_is_display_only(step, hint) for hint in step.connection_hints):
        return True
    if not step.block_refs:
        return False
    return any(_block_ref_is_real(block_ref) for block_ref in step.block_refs)


def _block_ref_is_real(block_ref: StepBlockRef) -> bool:
    text = " ".join(
        part
        for part in (block_ref.block_type, block_ref.purpose, block_ref.library_path)
        if part
    ).casefold()
    if any(term in text for term in REAL_BLOCK_ALLOW_TERMS):
        return True
    return not any(term in text for term in DISPLAY_BLOCK_TERMS)


def _connection_is_display_only(step: ModelBuildStep, hint: ConnectionHint) -> bool:
    refs = {
        block_ref.block_ref_id: block_ref for block_ref in step.block_refs
    }
    blocks = [refs.get(hint.from_block_ref), refs.get(hint.to_block_ref)]
    present = [block for block in blocks if block is not None]
    return bool(present) and all(not _block_ref_is_real(block) for block in present)


def _required_object_coverage(
    step: ModelBuildStep,
    covered_params: set[tuple[str, str]],
) -> list[tuple[str, str, bool]]:
    result: list[tuple[str, str, bool]] = []
    for block_ref in step.block_refs:
        covered = (
            block_ref.paper_reference is not None
            and block_ref.paper_reference.source is EvidenceSource.DOCUMENT_EXTRACTED
        )
        result.append(("block", block_ref.block_ref_id, covered))
    for parameter_ref in step.parameter_refs:
        key = (parameter_ref.paper_param_name, parameter_ref.model_param_name)
        result.append(("parameter", _parameter_ref_key(parameter_ref), key in covered_params))
    for index, connection in enumerate(step.connection_hints, start=1):
        result.append(("connection", _connection_key(connection, index), False))
    for index, hint in enumerate(step.configuration_hints, start=1):
        covered = any(entry.source is EvidenceSource.DOCUMENT_EXTRACTED for entry in hint.evidence)
        result.append(("configuration", _configuration_key(step.step_id, hint, index), covered))
    return result


def _gap_from_rule(
    prefix: str,
    ordinal: int,
    missing_object_kind: str,
    step_id: str,
    object_key: str,
) -> GuidanceGap:
    gap_kind, basis, severity = GAP_SYNTHESIS_RULES[missing_object_kind]
    return GuidanceGap(
        gap_id=f"{prefix}-{ordinal:03d}",
        gap_kind=cast(Any, gap_kind),
        scope="step",
        step_id=step_id,
        basis=cast(Any, basis),
        severity=cast(Any, severity),
        display_text=_gap_text(gap_kind, step_id, object_key),
    )


def _gap_text(gap_kind: str, step_id: str, object_key: str) -> str:
    if gap_kind == "missing_parameter_value":
        return f"Step {step_id} needs confirmed document support for parameter object {object_key}."
    if gap_kind == "missing_connection_detail":
        return f"Step {step_id} needs confirmed document support for connection object {object_key}."
    if gap_kind == "missing_configuration_detail":
        return f"Step {step_id} needs confirmed document support for configuration object {object_key}."
    if gap_kind == "missing_support_component":
        return f"Step {step_id} needs confirmed document support for block object {object_key}."
    return f"Step {step_id} has a detail that requires confirmation before reproduction."


def _terminal_status_and_reason(
    attempts: list[DraftAttemptStats],
    *,
    pool: GuidanceEvidencePool,
    call_count: int,
) -> tuple[Literal["generation_failed", "no_document_basis"], GuidanceFailureReason]:
    if not attempts:
        return "generation_failed", "retry_cap_exhausted"
    if any(stats.parse_error_count for stats in attempts):
        return "generation_failed", "llm_unparseable"
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
            return "no_document_basis", "zero_document_claims_empty_evidence_pool"
        if not pool.has_build_step_linked_evidence:
            return "no_document_basis", "zero_document_claims_unlinked_evidence_pool"
    if call_count >= GUIDANCE_HARD_CALL_CAP:
        return "generation_failed", "retry_cap_exhausted"
    return "generation_failed", "evidence_resolution_failed"


def _entry_from_source_ref(source_ref: PlanEvidenceSourceRef) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=source_ref.document_id,
        paper_section_id=source_ref.locator_id if source_ref.locator_kind == "paper_section_id" else None,
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
            except Exception:
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


def _parameter_truth_texts(parameter: ParameterEntry) -> list[str]:
    return [
        parameter.name,
        parameter.symbol,
        parameter.value,
        parameter.unit,
        f"{parameter.symbol} {parameter.value} {parameter.unit}",
        f"{parameter.name} {parameter.value} {parameter.unit}",
    ]


def _mapping_truth_texts(mapping: ParameterMapping) -> list[str]:
    unit = mapping.unit or ""
    return [
        mapping.paper_param_name,
        mapping.model_param_name,
        mapping.value,
        unit,
        f"{mapping.paper_param_name} {mapping.value} {unit}",
        f"{mapping.model_param_name} {mapping.value} {unit}",
    ]


def _dedupe_details(details: list[GuidanceDetail]) -> list[GuidanceDetail]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[GuidanceDetail] = []
    for detail in details:
        key = (
            detail.step_id,
            detail.detail_kind,
            detail.basis,
            _canonicalize(detail.display_text),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(replace(detail, detail_id=f"GD-{len(result) + 1:03d}"))
    return result


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


def _evidence_key(entry: PaperEvidenceEntry) -> tuple[object, ...]:
    return (
        entry.source,
        entry.document_id,
        entry.paper_section_id,
        entry.equation_id,
        entry.figure_id,
        entry.excerpt,
        entry.missing_param_prompt_id,
        entry.user_action,
        entry.parameter_correction_id,
        entry.correction_param_key,
    )


def _parameter_ref_key(ref: ParameterMappingRef) -> str:
    return f"{ref.paper_param_name}::{ref.model_param_name}"


def _configuration_key(step_id: str, hint: ConfigurationHint, index: int) -> str:
    return "::".join(
        [
            "config",
            step_id,
            _clean_text(hint.target),
            _clean_text(hint.setting_name) or f"#{index}",
        ]
    )


def _connection_key(connection: ConnectionHint, index: int) -> str:
    parts = [
        connection.from_block_ref,
        connection.from_port or f"from#{index}",
        connection.to_block_ref,
        connection.to_port or f"to#{index}",
        connection.signal_meaning or f"signal#{index}",
    ]
    return "::".join(_clean_text(part) for part in parts)


def _summary_text(value: str | None) -> str:
    cleaned = _clean_display_text(value or "")
    return cleaned[:240] if cleaned else "Document evidence excerpt available."


def _clean_display_text(value: str) -> str:
    cleaned = CONTROL_CHAR_RE.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    if not cleaned:
        return "Confirm this step against the source material."
    return cleaned


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _unsafe_freeform_text(value: str | None) -> bool:
    if not value:
        return False
    return bool(NUMBER_UNIT_RE.search(value) or PATH_RE.search(value))


def _unsafe_direction_hint(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    if NUMBER_UNIT_RE.search(value) or PATH_RE.search(value):
        return True
    return any(term in lowered for term in TOOL_ENV_TERMS)


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        key = _canonicalize(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _canonicalize(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = normalized.replace("μ", "u").replace("µ", "u").replace("ω", "ohm")
    normalized = normalized.replace("\\omega", "ohm").replace("\\times", "x")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("千瓦", "kw").replace("兆瓦", "mw")
    normalized = normalized.replace("秒", "s").replace("毫秒", "ms")
    normalized = normalized.replace("欧姆", "ohm").replace("赫兹", "hz")
    normalized = normalized.replace("伏", "v").replace("安", "a")
    return normalized
