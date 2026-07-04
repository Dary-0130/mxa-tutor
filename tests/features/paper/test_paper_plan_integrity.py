import pytest

from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_plan import (
    ConfigurationHint,
    ModelBuildStep,
    ModelGenerationPlan,
)
from core.domain.paper_spec import (
    ParameterConflict,
    ParameterConflictObservation,
    ParameterConflictValueOption,
)
from features.paper.paper_plan_integrity import validate_plan_does_not_resolve_conflicts


def test_conflict_guard_still_scans_display_text_for_cross_field_values() -> None:
    plan = ModelGenerationPlan(
        plan_id="PLAN-PAPER-001",
        paper_spec_id="PAPER-001",
        library_choice="Simscape Electrical",
        block_recommendations=[],
        parameter_mapping=[],
        subsystem_breakdown=[],
        m_script_skeleton=None,
        evidence=[],
        build_steps=[
            ModelBuildStep(
                step_id="STEP-001",
                title="Configure solver",
                intent="Keep unresolved conflict pending confirmation.",
                block_refs=[],
                parameter_refs=[],
                connection_hints=[],
                configuration_hints=[
                    ConfigurationHint(
                        target="0",
                        setting_name="05",
                        instruction="Keep the value pending confirmation.",
                        evidence=[],
                    )
                ],
                depends_on=[],
                evidence=[],
                display_text="STEP-001 Configure solver | Configure: 0.05",
            )
        ],
    )
    conflicts = [
        ParameterConflict(
            parameter_name="Resistance",
            parameter_symbol="Rs",
            value_options=[
                ParameterConflictValueOption(
                    value="0.05",
                    unit="Ω",
                    observations=[
                        ParameterConflictObservation(
                            document_id="DOC-001",
                            locator=None,
                            excerpt=None,
                        )
                    ],
                )
            ],
        )
    ]

    with pytest.raises(PaperPlanGenerationError, match="parameter_conflict_build_step_text_stale"):
        validate_plan_does_not_resolve_conflicts(plan, conflicts)
