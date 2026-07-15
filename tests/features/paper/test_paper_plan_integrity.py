from dataclasses import replace

import pytest

from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_parameter_conflicts import with_parameter_conflicts
from core.domain.paper_plan import (
    ConfigurationHint,
    ModelBuildStep,
    ModelGenerationPlan,
    PaperPlanRecord,
)
from core.domain.paper_spec import (
    PaperDocument,
    PaperSpec,
    ParameterConflict,
    ParameterConflictObservation,
    ParameterConflictValueOption,
    ParameterEntry,
)
from features.paper.paper_plan_integrity import (
    validate_plan_does_not_resolve_conflicts,
    validate_record_parameter_conflict_integrity,
)


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


def test_record_integrity_degrades_build_step_text_stale_without_mutating_record() -> None:
    plan = _conflict_plan()
    record = PaperPlanRecord(
        paper_id="paper-1",
        spec=_conflict_spec(),
        plan=plan,
        missing_prompts=[],
        missing_bindings=[],
    )

    degraded = validate_record_parameter_conflict_integrity(record)

    assert record.plan.build_steps is not None
    assert degraded.plan.build_steps is None
    assert degraded.plan.build_guidance is None
    assert degraded.plan.guidance_status == "stale_pending_regeneration"
    assert degraded.plan.library_choice == plan.library_choice


def _conflict_plan() -> ModelGenerationPlan:
    base = ModelGenerationPlan(
        plan_id="PLAN-PAPER-001",
        paper_spec_id="PAPER-001",
        library_choice="Simscape Electrical",
        block_recommendations=[],
        parameter_mapping=[],
        subsystem_breakdown=[],
        m_script_skeleton=None,
        evidence=[],
    )
    return replace(
        base,
        build_steps=[
            ModelBuildStep(
                step_id="STEP-001",
                title="Configure solver",
                intent="Keep unresolved conflict pending confirmation.",
                block_refs=[],
                parameter_refs=[],
                connection_hints=[],
                configuration_hints=[],
                depends_on=[],
                evidence=[],
                display_text="STEP-001 Configure solver | Configure: 0.05",
            )
        ],
    )


def _conflict_spec() -> PaperSpec:
    return with_parameter_conflicts(
        PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            documents=[
                PaperDocument(document_id="DOC-001", filename="paper-a.pdf"),
                PaperDocument(document_id="DOC-002", filename="paper-b.pdf"),
            ],
            primary_document_id=None,
            abstract="A synchronous machine short-circuit report.",
            equations=[],
            parameter_table=[
                ParameterEntry(
                    name="Resistance",
                    symbol="Rs",
                    value="0.05",
                    unit="Ω",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                    document_id="DOC-001",
                ),
                ParameterEntry(
                    name="Resistance",
                    symbol="Rs",
                    value="0.06",
                    unit="Ω",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                    document_id="DOC-002",
                ),
            ],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[],
        )
    )
