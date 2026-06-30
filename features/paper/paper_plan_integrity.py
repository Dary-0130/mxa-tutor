"""Integrity guards for plans interacting with parameter conflicts."""

from __future__ import annotations

from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_parameter_conflicts import (
    label_hits_parameter_conflict,
    mscript_assigns_conflict_value,
    text_contains_conflict_value,
    validate_parameter_conflicts_materialized,
)
from core.domain.paper_plan import ModelGenerationPlan, PaperPlanRecord
from core.domain.paper_spec import ParameterConflict
from core.domain.paper_tuning import TuningSuggestion


def validate_record_parameter_conflict_integrity(record: PaperPlanRecord) -> None:
    """Reject stale ready bundles that silently resolved parameter conflicts."""

    try:
        validate_parameter_conflicts_materialized(record.spec)
    except ValueError:
        raise PaperPlanGenerationError("parameter_conflicts_mismatch") from None
    validate_plan_does_not_resolve_conflicts(record.plan, record.spec.parameter_conflicts)


def validate_plan_does_not_resolve_conflicts(
    plan: ModelGenerationPlan,
    conflicts: list[ParameterConflict],
) -> None:
    """Reject plan artifacts that turn a conflict into a concrete value."""

    if not conflicts:
        return
    for mapping in plan.parameter_mapping:
        if label_hits_parameter_conflict(mapping.paper_param_name, conflicts):
            raise PaperPlanGenerationError("parameter_conflict_mapping_stale")

    if plan.m_script_skeleton and mscript_assigns_conflict_value(
        plan.m_script_skeleton,
        conflicts,
    ):
        raise PaperPlanGenerationError("parameter_conflict_mscript_stale")

    if plan.build_steps is None:
        return
    for step in plan.build_steps:
        if text_contains_conflict_value(
            step.display_text,
            conflicts,
            allow_confirmation_placeholder=True,
        ):
            raise PaperPlanGenerationError("parameter_conflict_build_step_text_stale")
        for ref in step.parameter_refs:
            if label_hits_parameter_conflict(ref.paper_param_name, conflicts):
                raise PaperPlanGenerationError("parameter_conflict_build_step_ref_stale")
        for hint in step.configuration_hints:
            if text_contains_conflict_value(
                hint.instruction,
                conflicts,
                allow_confirmation_placeholder=True,
            ):
                raise PaperPlanGenerationError("parameter_conflict_configuration_hint_stale")


def validate_tuning_does_not_resolve_conflicts(
    suggestion: TuningSuggestion,
    conflicts: list[ParameterConflict],
) -> None:
    """Reject tuning output that treats conflicted parameters as resolved."""

    if not conflicts:
        return
    for direction in suggestion.parameter_directions:
        if label_hits_parameter_conflict(direction.param_name, conflicts):
            raise PaperPlanGenerationError("parameter_conflict_tuning_ref_stale")
        if text_contains_conflict_value(
            direction.physical_meaning,
            conflicts,
            allow_confirmation_placeholder=True,
        ):
            raise PaperPlanGenerationError("parameter_conflict_tuning_text_stale")
