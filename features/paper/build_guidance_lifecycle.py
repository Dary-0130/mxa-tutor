"""Lifecycle helpers for paper build guidance state."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from core.domain.paper_plan import BuildGuidance, GuidanceStatus, ModelGenerationPlan

GuidanceViewState = Literal[
    "current",
    "stale_with_snapshot",
    "stale_empty",
    "failed_retryable",
    "no_basis",
    "not_generated",
]

TERMINAL_EMPTY_STATUSES = frozenset({"not_generated", "generation_failed", "no_document_basis"})


def normalize_guidance_lifecycle(plan: ModelGenerationPlan) -> ModelGenerationPlan:
    """Return a plan whose guidance payload matches its lifecycle status."""

    if plan.guidance_status == "generated":
        validate_generated_guidance(plan.build_guidance)
        return plan
    if plan.guidance_status == "stale_pending_regeneration":
        return plan
    if plan.guidance_status in TERMINAL_EMPTY_STATUSES:
        if plan.build_guidance is None:
            return plan
        return replace(plan, build_guidance=None)
    raise ValueError("guidance_status_invalid")


def validate_guidance_lifecycle(plan: ModelGenerationPlan) -> None:
    """Validate the public lifecycle invariants without mutating the plan."""

    if plan.guidance_status == "generated":
        validate_generated_guidance(plan.build_guidance)
        return
    if plan.guidance_status == "stale_pending_regeneration":
        return
    if plan.guidance_status in TERMINAL_EMPTY_STATUSES:
        if plan.build_guidance is not None:
            raise ValueError("guidance_status_requires_empty_guidance")
        return
    raise ValueError("guidance_status_invalid")


def validate_generated_guidance(guidance: BuildGuidance | None) -> None:
    """Validate the generated-state payload floor."""

    if guidance is None:
        raise ValueError("generated_guidance_required")
    if guidance.version != "v2":
        raise ValueError("generated_guidance_version_required")
    if not guidance.details:
        raise ValueError("generated_guidance_details_required")
    if not any(
        detail.basis in {"document_extracted", "document_derived"} and detail.evidence
        for detail in guidance.details
    ):
        raise ValueError("generated_guidance_document_detail_required")


def mark_guidance_stale_for_parameter_change(
    plan: ModelGenerationPlan,
) -> ModelGenerationPlan:
    """Mark parameter-driven derived guidance stale while preserving its snapshot."""

    return replace(plan, guidance_status="stale_pending_regeneration")


def mark_guidance_stale_for_step_regeneration(
    plan: ModelGenerationPlan,
) -> ModelGenerationPlan:
    """Mark step-derived guidance stale and clear the old step-bound payload."""

    return replace(
        plan,
        build_guidance=None,
        guidance_status="stale_pending_regeneration",
    )


def mark_guidance_not_generated(plan: ModelGenerationPlan) -> ModelGenerationPlan:
    """Reset guidance lifecycle for a newly replaced bundle."""

    return replace(plan, build_guidance=None, guidance_status="not_generated")


def guidance_view_state(plan: ModelGenerationPlan) -> GuidanceViewState:
    """Map persisted lifecycle state to the consumer view state."""

    if plan.guidance_status == "generated":
        return "current"
    if plan.guidance_status == "stale_pending_regeneration":
        return "stale_with_snapshot" if plan.build_guidance is not None else "stale_empty"
    if plan.guidance_status == "generation_failed":
        return "failed_retryable"
    if plan.guidance_status == "no_document_basis":
        return "no_basis"
    return "not_generated"


def guidance_status_requires_regeneration(status: GuidanceStatus) -> bool:
    """Return whether a user retry button should have real regeneration work."""

    return status == "stale_pending_regeneration"
