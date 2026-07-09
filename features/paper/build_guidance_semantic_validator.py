"""Pure semantic validation for assembled paper build guidance."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceGap,
    ModelBuildStep,
    ModelGenerationPlan,
)
from core.domain.paper_spec import PaperSpec
from features.paper.build_guidance_rules import (
    CONFIRMATION_REASON_TEMPLATES,
    CONVENTION_TEMPLATES,
    ControlledGuidanceTargets,
    GroundingTruthIndex,
    confirmation_display_text,
    convention_display_text,
    gap_rule_signatures,
    high_risk_claim_tokens,
    high_risk_text_tokens,
    unsafe_confirmation_display_text,
    unsafe_freeform_text,
)
from features.paper.paper_plan_helpers import EvidenceTagger

ItemActionKind = Literal["keep", "drop", "downgrade", "normalize"]
ItemActionType = Literal["detail", "gap", "assessment", "guidance", "plan", "raw_guidance"]
WholeAction = Literal[
    "keep",
    "mark_generation_failed",
    "mark_stale_empty",
    "corrupt_unreadable",
]
ValidationMode = Literal["current_generated", "stale_snapshot"]

_EMPTY_STATUSES = frozenset({"not_generated", "generation_failed", "no_document_basis"})
_VALID_GUIDANCE_STATUSES = frozenset(
    {
        "not_generated",
        "generated",
        "stale_pending_regeneration",
        "generation_failed",
        "no_document_basis",
    }
)
_VALID_DETAIL_KINDS = frozenset(
    {
        "block_selection",
        "subsystem_internal_structure",
        "connection",
        "parameter_value",
        "configuration",
        "verification",
        "gap_notice",
    }
)
_VALID_DETAIL_BASES = frozenset(
    {
        "document_extracted",
        "engineering_convention",
        "user_confirmation_required",
    }
)
_VALID_ACTIONABILITY = frozenset(
    {
        "actionable",
        "notice_only",
        "blocked_pending_confirmation",
    }
)
_VALID_GAP_KINDS = frozenset(
    {
        "missing_support_component",
        "missing_parameter_value",
        "toolbox_unverified",
        "library_variant_unresolved",
        "missing_connection_detail",
        "missing_configuration_detail",
        "insufficient_document_evidence",
    }
)
_VALID_GAP_SCOPES = frozenset({"plan", "step", "subsystem"})
_VALID_GAP_BASES = frozenset({"engineering_convention", "user_confirmation_required"})
_VALID_GAP_SEVERITIES = frozenset({"blocking", "warning"})
_VALID_CONTENT_STATUS = frozenset(
    {
        "reproducible_candidate",
        "outline_with_gaps",
        "outline_only",
    }
)
_VALID_ENVIRONMENT_STATUS = frozenset(
    {
        "not_checked",
        "compatible",
        "missing_toolbox",
        "incompatible",
    }
)
_VALID_OVERALL_STATUS = frozenset(
    {
        "reproducible_ready",
        "reproducible_candidate_env_unchecked",
        "outline_with_gaps",
        "outline_only",
    }
)


@dataclass(frozen=True)
class ItemAction:
    """Machine-coded action taken for one guidance item."""

    item_type: ItemActionType
    item_id: str | None
    action: ItemActionKind
    machine_code: str


@dataclass(frozen=True)
class GuidanceSemanticValidationResult:
    """Result of validating one assembled ModelGenerationPlan guidance payload."""

    plan: ModelGenerationPlan
    changed: bool
    item_actions: list[ItemAction]
    whole_action: WholeAction
    machine_codes: list[str]


@dataclass(frozen=True)
class RawGuidanceScrubResult:
    """Pre-typed raw plan payload scrub for legacy or damaged nested guidance."""

    payload: Any
    changed: bool
    machine_codes: list[str]


@dataclass(frozen=True)
class GuidanceValidationTelemetry:
    """Machine-code-only counters for guidance validation callers to log."""

    detail_downgraded_count: int
    detail_dropped_count: int
    gap_dropped_count: int
    all_document_details_lost: int
    template_version_mismatch: int
    display_text_grounding_failed: int
    stale_snapshot_step_ref_ignored: int
    generated_output_changed: int


def guidance_validation_telemetry(
    result: GuidanceSemanticValidationResult,
) -> GuidanceValidationTelemetry:
    """Return machine-code-only counters for validator telemetry."""

    codes = set(result.machine_codes)
    return GuidanceValidationTelemetry(
        detail_downgraded_count=sum(
            1
            for action in result.item_actions
            if action.item_type == "detail" and action.action == "downgrade"
        ),
        detail_dropped_count=sum(
            1
            for action in result.item_actions
            if action.item_type == "detail" and action.action == "drop"
        ),
        gap_dropped_count=sum(
            1
            for action in result.item_actions
            if action.item_type == "gap" and action.action == "drop"
        ),
        all_document_details_lost=int("guidance_validator_all_document_details_lost" in codes),
        template_version_mismatch=int("guidance_validator_version_invalid" in codes),
        display_text_grounding_failed=int(
            "guidance_validator_display_text_grounding_failed" in codes
        ),
        stale_snapshot_step_ref_ignored=int(
            "guidance_validator_stale_snapshot_step_ref_ignored" in codes
        ),
        generated_output_changed=int("guidance_validator_generated_output_changed" in codes),
    )


def scrub_build_guidance_payload(payload: Any) -> RawGuidanceScrubResult:
    """Scrub schema-invalid nested guidance before dataclass validation.

    The scrub is intentionally narrow: it only makes old/damaged nested guidance readable
    enough for the semantic validator to isolate bad units after typing.
    """

    if not isinstance(payload, dict):
        return RawGuidanceScrubResult(payload=payload, changed=False, machine_codes=[])

    migrated = copy.deepcopy(payload)
    machine_codes: list[str] = []
    changed = False

    guidance = migrated.get("build_guidance")
    if "guidance_status" not in migrated:
        migrated["guidance_status"] = "generated" if isinstance(guidance, dict) else "not_generated"
        machine_codes.append("guidance_validator_legacy_status_inferred")
        changed = True

    guidance_status = migrated.get("guidance_status")
    if guidance_status not in _VALID_GUIDANCE_STATUSES:
        migrated["guidance_status"] = "generation_failed"
        migrated["build_guidance"] = None
        machine_codes.append("guidance_validator_raw_status_invalid")
        return RawGuidanceScrubResult(payload=migrated, changed=True, machine_codes=machine_codes)

    if guidance is None:
        return RawGuidanceScrubResult(
            payload=migrated,
            changed=changed,
            machine_codes=_unique_codes(machine_codes),
        )
    if not isinstance(guidance, dict):
        migrated["build_guidance"] = None
        if migrated["guidance_status"] == "generated":
            migrated["guidance_status"] = "generation_failed"
        machine_codes.append("guidance_validator_raw_guidance_unreadable")
        return RawGuidanceScrubResult(payload=migrated, changed=True, machine_codes=machine_codes)

    scrubbed_guidance, guidance_changed, guidance_codes = _scrub_guidance_dict(guidance)
    migrated["build_guidance"] = scrubbed_guidance
    return RawGuidanceScrubResult(
        payload=migrated,
        changed=changed or guidance_changed,
        machine_codes=_unique_codes([*machine_codes, *guidance_codes]),
    )


def validate_build_guidance_semantics(
    spec: PaperSpec,
    plan: ModelGenerationPlan,
    *,
    evidence_tagger: EvidenceTagger | None = None,
) -> GuidanceSemanticValidationResult:
    """Validate and gently sanitize one assembled BuildGuidance payload."""

    item_actions: list[ItemAction] = []
    machine_codes: list[str] = []
    tagger = evidence_tagger or EvidenceTagger()

    def record(
        item_type: ItemActionType,
        item_id: str | None,
        action: ItemActionKind,
        code: str,
    ) -> None:
        item_actions.append(ItemAction(item_type, item_id, action, code))
        machine_codes.append(code)

    if plan.guidance_status not in _VALID_GUIDANCE_STATUSES:
        next_plan = replace(plan, build_guidance=None, guidance_status="generation_failed")
        record("plan", None, "normalize", "guidance_validator_lifecycle_status_invalid")
        return _result(plan, next_plan, item_actions, "mark_generation_failed", machine_codes)

    if plan.guidance_status in _EMPTY_STATUSES:
        if plan.build_guidance is None:
            return GuidanceSemanticValidationResult(
                plan=plan,
                changed=False,
                item_actions=[],
                whole_action="keep",
                machine_codes=[],
            )
        next_plan = replace(plan, build_guidance=None)
        record("plan", None, "normalize", "guidance_validator_terminal_guidance_cleared")
        return _result(plan, next_plan, item_actions, "keep", machine_codes)

    if plan.build_guidance is None:
        if plan.guidance_status == "stale_pending_regeneration":
            return GuidanceSemanticValidationResult(
                plan=plan,
                changed=False,
                item_actions=[],
                whole_action="keep",
                machine_codes=[],
            )
        next_plan = replace(plan, build_guidance=None, guidance_status="generation_failed")
        record("guidance", None, "drop", "guidance_validator_generated_guidance_missing")
        return _result(plan, next_plan, item_actions, "mark_generation_failed", machine_codes)

    if plan.build_guidance.version != "v1":
        whole_action: WholeAction = (
            "mark_stale_empty"
            if plan.guidance_status == "stale_pending_regeneration"
            else "mark_generation_failed"
        )
        status = (
            "stale_pending_regeneration"
            if plan.guidance_status == "stale_pending_regeneration"
            else "generation_failed"
        )
        next_plan = replace(plan, build_guidance=None, guidance_status=status)
        record("guidance", None, "drop", "guidance_validator_version_invalid")
        return _result(plan, next_plan, item_actions, whole_action, machine_codes)

    if plan.guidance_status == "generated" and plan.build_steps is None:
        next_plan = replace(plan, build_guidance=None, guidance_status="generation_failed")
        record("plan", None, "normalize", "guidance_validator_current_steps_missing")
        return _result(plan, next_plan, item_actions, "mark_generation_failed", machine_codes)

    mode: ValidationMode = (
        "stale_snapshot"
        if plan.guidance_status == "stale_pending_regeneration"
        else "current_generated"
    )
    build_steps = plan.build_steps or []
    step_by_id = {step.step_id: step for step in build_steps}
    targets = ControlledGuidanceTargets(build_steps)

    details = _validated_details(
        spec=spec,
        details=plan.build_guidance.details,
        mode=mode,
        step_by_id=step_by_id,
        targets=targets,
        tagger=tagger,
        record=record,
    )
    gaps = _validated_gaps(
        gaps=plan.build_guidance.gaps,
        mode=mode,
        step_by_id=step_by_id,
        record=record,
    )
    assessment = _validated_assessment(
        plan.build_guidance.assessment,
        gaps,
        record=record,
    )
    sanitized_guidance = replace(
        plan.build_guidance,
        assessment=assessment,
        details=details,
        gaps=gaps,
    )

    if not any(detail.basis == "document_extracted" for detail in details):
        if mode == "stale_snapshot":
            next_plan = replace(
                plan,
                build_guidance=None,
                guidance_status="stale_pending_regeneration",
            )
            record("guidance", None, "drop", "guidance_validator_stale_snapshot_empty")
            return _result(plan, next_plan, item_actions, "mark_stale_empty", machine_codes)
        next_plan = replace(plan, build_guidance=None, guidance_status="generation_failed")
        record("guidance", None, "drop", "guidance_validator_all_document_details_lost")
        return _result(plan, next_plan, item_actions, "mark_generation_failed", machine_codes)

    next_plan = replace(plan, build_guidance=sanitized_guidance)
    return _result(plan, next_plan, item_actions, "keep", machine_codes)


def _validated_details(
    *,
    spec: PaperSpec,
    details: list[GuidanceDetail],
    mode: ValidationMode,
    step_by_id: dict[str, ModelBuildStep],
    targets: ControlledGuidanceTargets,
    tagger: EvidenceTagger,
    record: Any,
) -> list[GuidanceDetail]:
    seen_ids: set[str] = set()
    result: list[GuidanceDetail] = []
    for detail in details:
        if detail.detail_id in seen_ids:
            record("detail", detail.detail_id, "drop", "guidance_validator_detail_id_duplicate")
            continue
        seen_ids.add(detail.detail_id)

        step = step_by_id.get(detail.step_id)
        if mode == "current_generated" and step is None:
            record("detail", detail.detail_id, "drop", "guidance_validator_detail_step_missing")
            continue
        if mode == "stale_snapshot" and step is None and step_by_id:
            record(
                "detail",
                detail.detail_id,
                "keep",
                "guidance_validator_stale_snapshot_step_ref_ignored",
            )

        if detail.basis == "document_extracted":
            validated = _validated_document_detail(
                spec=spec,
                detail=detail,
                step=step,
                mode=mode,
                targets=targets,
                tagger=tagger,
                record=record,
            )
            result.append(validated)
            continue
        if detail.basis == "engineering_convention":
            convention_detail = _validated_convention_detail(
                detail=detail,
                targets=targets,
                record=record,
            )
            if convention_detail is not None:
                result.append(convention_detail)
            continue
        if detail.basis == "user_confirmation_required":
            confirmation_detail = _validated_confirmation_detail(
                detail=detail,
                targets=targets,
                record=record,
            )
            if confirmation_detail is not None:
                result.append(confirmation_detail)
            continue
        record("detail", detail.detail_id, "drop", "guidance_validator_detail_basis_invalid")
    return result


def _validated_document_detail(
    *,
    spec: PaperSpec,
    detail: GuidanceDetail,
    step: ModelBuildStep | None,
    mode: ValidationMode,
    targets: ControlledGuidanceTargets,
    tagger: EvidenceTagger,
    record: Any,
) -> GuidanceDetail:
    invalid_codes: list[str] = []
    if detail.actionability != "actionable":
        invalid_codes.append("guidance_validator_document_actionability_invalid")
    if detail.convention_code is not None or detail.confirmation_reason_code is not None:
        invalid_codes.append("guidance_validator_document_code_fields_invalid")
    if not detail.evidence:
        invalid_codes.append("guidance_validator_document_evidence_missing")
    if detail.evidence and not _inline_document_evidence_looks_valid(detail.evidence):
        invalid_codes.append("guidance_validator_document_evidence_invalid")
    if mode == "current_generated" and detail.evidence:
        try:
            tagger.validate_for_spec(detail.evidence, spec)
        except Exception:
            invalid_codes.append("guidance_validator_document_evidence_locator_invalid")
    if detail.evidence:
        tokens = (
            high_risk_claim_tokens(detail.display_text, step)
            if step is not None
            else high_risk_text_tokens(detail.display_text)
        )
        truth_index = GroundingTruthIndex.from_inline_evidence(
            detail.evidence,
            spec=spec if mode == "current_generated" else None,
        )
        if not truth_index.contains_all(tokens):
            invalid_codes.append("guidance_validator_display_text_grounding_failed")

    if invalid_codes:
        downgraded = _downgraded_document_detail(detail, targets)
        record("detail", detail.detail_id, "downgrade", invalid_codes[0])
        return downgraded
    return detail


def _validated_convention_detail(
    *,
    detail: GuidanceDetail,
    targets: ControlledGuidanceTargets,
    record: Any,
) -> GuidanceDetail | None:
    code = detail.convention_code
    if detail.evidence:
        record("detail", detail.detail_id, "drop", "guidance_validator_convention_evidence")
        return None
    if detail.confirmation_reason_code is not None:
        record("detail", detail.detail_id, "drop", "guidance_validator_convention_reason")
        return None
    if code not in CONVENTION_TEMPLATES:
        record("detail", detail.detail_id, "drop", "guidance_validator_convention_code_invalid")
        return None
    detail_kind, actionability = CONVENTION_TEMPLATES[code]
    if detail.detail_kind != detail_kind or detail.actionability != actionability:
        record("detail", detail.detail_id, "drop", "guidance_validator_convention_mapping")
        return None
    if unsafe_freeform_text(detail.display_text):
        normalized = replace(
            detail,
            display_text=convention_display_text(code, targets.label(detail.step_id, None)),
        )
        record("detail", detail.detail_id, "normalize", "guidance_validator_convention_unsafe")
        return normalized
    return detail


def _validated_confirmation_detail(
    *,
    detail: GuidanceDetail,
    targets: ControlledGuidanceTargets,
    record: Any,
) -> GuidanceDetail | None:
    reason_code = detail.confirmation_reason_code
    if detail.evidence:
        record("detail", detail.detail_id, "drop", "guidance_validator_confirmation_evidence")
        return None
    if detail.convention_code is not None:
        record("detail", detail.detail_id, "drop", "guidance_validator_confirmation_convention")
        return None
    if reason_code not in CONFIRMATION_REASON_TEMPLATES:
        record("detail", detail.detail_id, "drop", "guidance_validator_confirmation_reason")
        return None
    if detail.actionability != "blocked_pending_confirmation":
        record(
            "detail",
            detail.detail_id,
            "drop",
            "guidance_validator_confirmation_actionability",
        )
        return None
    if unsafe_confirmation_display_text(detail.display_text, reason_code):
        normalized = replace(
            detail,
            display_text=confirmation_display_text(
                reason_code,
                targets.label(detail.step_id, None),
                None,
            ),
        )
        record("detail", detail.detail_id, "normalize", "guidance_validator_confirmation_unsafe")
        return normalized
    return detail


def _validated_gaps(
    *,
    gaps: list[GuidanceGap],
    mode: ValidationMode,
    step_by_id: dict[str, ModelBuildStep],
    record: Any,
) -> list[GuidanceGap]:
    seen_ids: set[str] = set()
    signatures = gap_rule_signatures()
    result: list[GuidanceGap] = []
    for gap in gaps:
        if gap.gap_id in seen_ids:
            record("gap", gap.gap_id, "drop", "guidance_validator_gap_id_duplicate")
            continue
        seen_ids.add(gap.gap_id)
        if gap.scope == "plan" and gap.step_id is not None:
            record("gap", gap.gap_id, "drop", "guidance_validator_gap_plan_step")
            continue
        if gap.scope in {"step", "subsystem"} and gap.step_id is None:
            record("gap", gap.gap_id, "drop", "guidance_validator_gap_scoped_step_missing")
            continue
        if (
            mode == "current_generated"
            and gap.step_id is not None
            and gap.step_id not in step_by_id
        ):
            record("gap", gap.gap_id, "drop", "guidance_validator_gap_step_missing")
            continue
        if (
            mode == "stale_snapshot"
            and gap.step_id is not None
            and step_by_id
            and gap.step_id not in step_by_id
        ):
            record(
                "gap",
                gap.gap_id,
                "keep",
                "guidance_validator_stale_snapshot_step_ref_ignored",
            )
        if (gap.gap_kind, gap.basis, gap.severity) not in signatures:
            record("gap", gap.gap_id, "drop", "guidance_validator_gap_rule_invalid")
            continue
        result.append(gap)
    return result


def _validated_assessment(
    assessment: GuidanceAssessment,
    gaps: list[GuidanceGap],
    *,
    record: Any,
) -> GuidanceAssessment:
    blocking_gap_ids = [gap.gap_id for gap in gaps if gap.severity == "blocking"]
    content_status = assessment.content_status
    overall_status = assessment.overall_status
    if blocking_gap_ids:
        content_status = "outline_with_gaps"
        overall_status = "outline_with_gaps"
    elif content_status == "outline_with_gaps":
        content_status = "outline_only"
        if overall_status == "outline_with_gaps":
            overall_status = "outline_only"
    if overall_status == "reproducible_ready":
        overall_status = (
            "reproducible_candidate_env_unchecked"
            if content_status == "reproducible_candidate"
            else content_status
        )
    normalized = replace(
        assessment,
        content_status=cast(Any, content_status),
        overall_status=cast(Any, overall_status),
        blocking_gap_ids=blocking_gap_ids,
    )
    if normalized != assessment:
        record("assessment", None, "normalize", "guidance_validator_assessment_recomputed")
    return normalized


def _inline_document_evidence_looks_valid(evidence: list[PaperEvidenceEntry]) -> bool:
    for entry in evidence:
        if entry.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            return False
        if entry.document_id is None:
            return False
        if not any((entry.paper_section_id, entry.equation_id, entry.figure_id)):
            return False
        if not entry.excerpt:
            return False
        if entry.missing_param_prompt_id is not None or entry.user_action is not None:
            return False
        if entry.parameter_correction_id is not None or entry.correction_param_key is not None:
            return False
    return True


def _downgraded_document_detail(
    detail: GuidanceDetail,
    targets: ControlledGuidanceTargets,
) -> GuidanceDetail:
    reason_code = "document_evidence_unverified"
    return replace(
        detail,
        basis="user_confirmation_required",
        actionability="blocked_pending_confirmation",
        display_text=confirmation_display_text(
            reason_code,
            targets.label(detail.step_id, None),
            None,
        ),
        evidence=[],
        convention_code=None,
        confirmation_reason_code=reason_code,
    )


def _scrub_guidance_dict(guidance: dict[str, Any]) -> tuple[dict[str, Any], bool, list[str]]:
    scrubbed = dict(guidance)
    changed = False
    machine_codes: list[str] = []
    if scrubbed.get("version") != "v1":
        scrubbed["version"] = "v1"
        changed = True
        machine_codes.append("guidance_validator_raw_version_defaulted")

    raw_details = scrubbed.get("details")
    if not isinstance(raw_details, list):
        raw_details = []
        changed = True
        machine_codes.append("guidance_validator_raw_details_invalid")
    details: list[dict[str, Any]] = []
    for index, item in enumerate(raw_details, start=1):
        detail = _scrub_detail_dict(item, index)
        if detail is None:
            changed = True
            machine_codes.append("guidance_validator_raw_detail_dropped")
            continue
        details.append(detail)
        if detail is not item:
            changed = True
    scrubbed["details"] = details

    raw_gaps = scrubbed.get("gaps")
    if not isinstance(raw_gaps, list):
        raw_gaps = []
        changed = True
        machine_codes.append("guidance_validator_raw_gaps_invalid")
    gaps: list[dict[str, Any]] = []
    for index, item in enumerate(raw_gaps, start=1):
        gap = _scrub_gap_dict(item, index)
        if gap is None:
            changed = True
            machine_codes.append("guidance_validator_raw_gap_dropped")
            continue
        gaps.append(gap)
        if gap is not item:
            changed = True
    scrubbed["gaps"] = gaps

    assessment = _scrub_assessment_dict(scrubbed.get("assessment"), gaps)
    if assessment != scrubbed.get("assessment"):
        changed = True
        machine_codes.append("guidance_validator_raw_assessment_defaulted")
    scrubbed["assessment"] = assessment
    return scrubbed, changed, _unique_codes(machine_codes)


def _scrub_detail_dict(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    detail = dict(item)
    if detail.get("detail_kind") not in _VALID_DETAIL_KINDS:
        return None
    if detail.get("basis") not in _VALID_DETAIL_BASES:
        return None
    if detail.get("actionability") not in _VALID_ACTIONABILITY:
        return None
    if not _nonempty_string(detail.get("step_id")):
        return None
    if not _nonempty_string(detail.get("display_text")):
        return None
    if not _nonempty_string(detail.get("detail_id")):
        detail["detail_id"] = f"GD-{index:03d}"
    if not isinstance(detail.get("evidence"), list):
        detail["evidence"] = []
    detail.setdefault("convention_code", None)
    detail.setdefault("confirmation_reason_code", None)
    return detail


def _scrub_gap_dict(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    gap = dict(item)
    if gap.get("gap_kind") not in _VALID_GAP_KINDS:
        return None
    if gap.get("scope") not in _VALID_GAP_SCOPES:
        return None
    if gap.get("basis") not in _VALID_GAP_BASES:
        return None
    if gap.get("severity") not in _VALID_GAP_SEVERITIES:
        return None
    if not _nonempty_string(gap.get("display_text")):
        return None
    if not _nonempty_string(gap.get("gap_id")):
        gap["gap_id"] = f"GAP-{index:03d}"
    if "step_id" not in gap:
        gap["step_id"] = None
    return gap


def _scrub_assessment_dict(item: Any, gaps: list[dict[str, Any]]) -> dict[str, Any]:
    assessment = dict(item) if isinstance(item, dict) else {}
    blocking_gap_ids = [
        str(gap.get("gap_id"))
        for gap in gaps
        if gap.get("severity") == "blocking" and _nonempty_string(gap.get("gap_id"))
    ]
    if assessment.get("content_status") not in _VALID_CONTENT_STATUS:
        assessment["content_status"] = "outline_with_gaps" if blocking_gap_ids else "outline_only"
    if assessment.get("environment_status") not in _VALID_ENVIRONMENT_STATUS:
        assessment["environment_status"] = "not_checked"
    if assessment.get("overall_status") not in _VALID_OVERALL_STATUS:
        assessment["overall_status"] = assessment["content_status"]
    if not isinstance(assessment.get("blocking_gap_ids"), list):
        assessment["blocking_gap_ids"] = blocking_gap_ids
    return assessment


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _result(
    original_plan: ModelGenerationPlan,
    next_plan: ModelGenerationPlan,
    item_actions: list[ItemAction],
    whole_action: WholeAction,
    machine_codes: list[str],
) -> GuidanceSemanticValidationResult:
    return GuidanceSemanticValidationResult(
        plan=next_plan,
        changed=next_plan != original_plan,
        item_actions=item_actions,
        whole_action=whole_action,
        machine_codes=_unique_codes(machine_codes),
    )


def _unique_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result
