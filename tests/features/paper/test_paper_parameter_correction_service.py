from __future__ import annotations

from dataclasses import replace

import pytest

from core.domain.exceptions import PaperParameterCorrectionError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import (
    BlockRecommendation,
    BuildGuidance,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceTarget,
    ModelBuildStep,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import PaperDocument, PaperSpec, ParameterEntry
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_parameter_correction_schemas import CorrectionTargetRequest
from features.paper.paper_parameter_correction_service import ParameterCorrectionService


@pytest.mark.asyncio
async def test_apply_first_correction_updates_plan_and_inserts_overlay() -> None:
    store = _FakeBundleStore(_record(m_script_skeleton="old script"))
    result = await ParameterCorrectionService(store).apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value=" 4.0 ",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )

    mapping = result.record.plan.parameter_mapping[0]
    assert mapping.value == "4.0"
    assert mapping.unit == "s"
    assert mapping.source is EvidenceSource.USER_SUPPLIED
    assert result.record.plan.m_script_skeleton is None
    assert result.record.plan.build_steps is None
    assert store.apply_calls == [False]
    assert store.insert_calls == 0
    assert len(store.corrections) == 1
    correction = store.corrections[0]
    assert correction.original_value == "3.5"
    assert correction.original_unit == "s"
    assert correction.original_source is EvidenceSource.DOCUMENT_EXTRACTED
    assert correction.original_document_id == "DOC-001"
    assert correction.corrected_value == "4.0"
    assert correction.corrected_unit == "s"
    assert correction.created_at.endswith("Z")
    assert result.view.document_label == "paper.pdf"
    assert result.view.can_undo is True
    assert result.record.plan.evidence[-1].user_action is UserEvidenceAction.CORRECT_EXTRACTED
    assert result.record.plan.evidence[-1].parameter_correction_id == correction.correction_id


@pytest.mark.asyncio
async def test_apply_correction_marks_guidance_stale_and_preserves_snapshot() -> None:
    record = _record(m_script_skeleton="old script", build_steps=[])
    old_guidance = _build_guidance()
    store = _FakeBundleStore(
        replace(
            record,
            plan=replace(
                record.plan,
                build_guidance=old_guidance,
                guidance_status="generated",
            ),
        )
    )

    result = await ParameterCorrectionService(store).apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )

    assert result.record.plan.build_steps is None
    assert result.record.plan.m_script_skeleton is None
    assert result.record.plan.guidance_status == "stale_pending_regeneration"
    assert result.record.plan.build_guidance == old_guidance


@pytest.mark.asyncio
async def test_recorrect_updates_corrected_value_without_changing_original() -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)
    first = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit="ms",
        corrected_unit_supplied=True,
    )

    second = await service.apply(
        "paper-1",
        target=_target(expected_value="4.0", expected_unit="ms"),
        corrected_value="4.2",
        corrected_unit=None,
        corrected_unit_supplied=True,
    )

    assert len(store.corrections) == 1
    assert store.apply_calls == [False, True]
    assert second.correction.correction_id == first.correction.correction_id
    assert second.correction.original_value == "3.5"
    assert second.correction.original_unit == "s"
    assert second.correction.corrected_value == "4.2"
    assert second.correction.corrected_unit is None


@pytest.mark.asyncio
async def test_fill_missing_mapping_is_not_correctable() -> None:
    store = _FakeBundleStore(_record_with_filled_missing())

    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await ParameterCorrectionService(store).apply(
            "paper-1",
            target=_target(expected_value="3.5", expected_unit="s"),
            corrected_value="4.0",
            corrected_unit=None,
            corrected_unit_supplied=False,
        )

    assert exc_info.value.error_code == "correction_target_not_correctable"
    assert store.apply_calls == []


@pytest.mark.asyncio
async def test_undo_restores_original_and_deletes_evidence_and_overlay() -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)
    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )

    updated = await service.undo("paper-1", applied.correction.correction_id)

    mapping = updated.plan.parameter_mapping[0]
    assert mapping.value == "3.5"
    assert mapping.unit == "s"
    assert mapping.source is EvidenceSource.DOCUMENT_EXTRACTED
    assert updated.plan.build_steps is None
    assert store.corrections == []
    assert not any(
        entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED for entry in updated.plan.evidence
    )
    assert store.undo_calls == [applied.correction.correction_id]


@pytest.mark.asyncio
async def test_undo_correction_marks_guidance_stale_and_preserves_snapshot() -> None:
    old_guidance = _build_guidance()
    store = _FakeBundleStore(
        replace(
            _record(),
            plan=replace(
                _record().plan,
                build_guidance=old_guidance,
                guidance_status="generated",
            ),
        )
    )
    service = ParameterCorrectionService(store)
    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )

    undone = await service.undo("paper-1", applied.correction.correction_id)

    assert undone.plan.build_steps is None
    assert undone.plan.m_script_skeleton is None
    assert undone.plan.guidance_status == "stale_pending_regeneration"
    assert undone.plan.build_guidance == old_guidance


@pytest.mark.asyncio
async def test_apply_then_undo_keeps_build_steps_and_script_suppressed() -> None:
    store = _FakeBundleStore(
        _record(
            m_script_skeleton="old script",
            build_steps=[
                ModelBuildStep(
                    step_id="STEP-1",
                    title="Structured build step",
                    intent="Use the original extracted parameter.",
                    block_refs=[],
                    parameter_refs=[],
                    connection_hints=[],
                    configuration_hints=[],
                    depends_on=[],
                    evidence=[_document_evidence()],
                    display_text="Old structured step",
                )
            ],
        )
    )
    service = ParameterCorrectionService(store)

    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )
    undone = await service.undo("paper-1", applied.correction.correction_id)

    assert applied.record.plan.build_steps is None
    assert applied.record.plan.m_script_skeleton is None
    assert undone.plan.build_steps is None
    assert undone.plan.m_script_skeleton is None


@pytest.mark.asyncio
async def test_undo_after_regenerate_clears_steps_script_and_correction_refs() -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)

    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )
    correction = applied.correction
    correction_evidence = next(
        entry
        for entry in applied.record.plan.evidence
        if entry.parameter_correction_id == correction.correction_id
    )
    regenerated_plan = replace(
        applied.record.plan,
        build_steps=[
            ModelBuildStep(
                step_id="STEP-1",
                title="Regenerated structured step",
                intent="Use the corrected parameter source.",
                block_refs=[],
                parameter_refs=[],
                connection_hints=[],
                configuration_hints=[],
                depends_on=[],
                evidence=[correction_evidence],
                display_text="Regenerated structured step",
            )
        ],
        m_script_skeleton="clear; clc;",
    )
    store.record = replace(applied.record, plan=regenerated_plan)

    undone = await service.undo("paper-1", correction.correction_id)

    assert undone.plan.build_steps is None
    assert undone.plan.m_script_skeleton is None
    assert store.corrections == []
    assert store.undo_calls == [correction.correction_id]
    assert not any(
        entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED for entry in undone.plan.evidence
    )
    assert not any(
        entry.parameter_correction_id == correction.correction_id for entry in undone.plan.evidence
    )


@pytest.mark.asyncio
async def test_undo_other_paper_correction_raises_not_found_without_writing() -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)
    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )

    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await service.undo("paper-2", applied.correction.correction_id)

    assert exc_info.value.error_code == "correction_not_found"
    assert store.undo_calls == []
    assert store.record is not None
    assert store.record.plan.parameter_mapping[0].value == "4.0"


@pytest.mark.asyncio
async def test_undo_stale_target_raises_without_rewriting_mapping() -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)
    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )
    stale_mapping = replace(
        applied.record.plan.parameter_mapping[0],
        paper_param_name="H_changed",
        value="9.9",
    )
    store.record = replace(
        applied.record,
        plan=replace(applied.record.plan, parameter_mapping=[stale_mapping]),
    )

    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await service.undo("paper-1", applied.correction.correction_id)

    assert exc_info.value.error_code == "correction_target_stale"
    assert store.undo_calls == []
    assert store.record.plan.parameter_mapping[0].paper_param_name == "H_changed"
    assert store.record.plan.parameter_mapping[0].value == "9.9"


@pytest.mark.asyncio
@pytest.mark.parametrize("correction_evidence_count", [0, 2])
async def test_undo_requires_exactly_one_correction_evidence(
    correction_evidence_count: int,
) -> None:
    store = _FakeBundleStore(_record())
    service = ParameterCorrectionService(store)
    applied = await service.apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )
    correction_evidence = [
        entry
        for entry in applied.record.plan.evidence
        if entry.parameter_correction_id == applied.correction.correction_id
    ][0]
    evidence = [
        entry
        for entry in applied.record.plan.evidence
        if entry.parameter_correction_id != applied.correction.correction_id
    ]
    evidence.extend([correction_evidence] * correction_evidence_count)
    store.record = replace(applied.record, plan=replace(applied.record.plan, evidence=evidence))

    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await service.undo("paper-1", applied.correction.correction_id)

    assert exc_info.value.error_code == "correction_store_failed"
    assert store.undo_calls == []
    assert store.record.plan.parameter_mapping[0].value == "4.0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected_value", "paper_param_name", "error_code"),
    [
        ("9.9", "H", "correction_target_stale"),
        ("3.5", "missing", "correction_target_not_extracted"),
    ],
)
async def test_apply_target_errors(
    expected_value: str,
    paper_param_name: str,
    error_code: str,
) -> None:
    store = _FakeBundleStore(_record())

    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await ParameterCorrectionService(store).apply(
            "paper-1",
            target=CorrectionTargetRequest(
                paper_param_name=paper_param_name,
                model_param_name="Synchronous Machine.H",
                plan_mapping_index=0,
                expected_value=expected_value,
                expected_unit="s",
            ),
            corrected_value="4.0",
            corrected_unit=None,
            corrected_unit_supplied=False,
        )

    assert exc_info.value.error_code == error_code


@pytest.mark.asyncio
async def test_unit_three_state() -> None:
    keep_store = _FakeBundleStore(_record())
    keep = await ParameterCorrectionService(keep_store).apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=False,
    )
    assert keep.record.plan.parameter_mapping[0].unit == "s"

    clear_store = _FakeBundleStore(_record())
    clear = await ParameterCorrectionService(clear_store).apply(
        "paper-1",
        target=_target(expected_value="3.5", expected_unit="s"),
        corrected_value="4.0",
        corrected_unit=None,
        corrected_unit_supplied=True,
    )
    assert clear.record.plan.parameter_mapping[0].unit is None

    invalid_store = _FakeBundleStore(_record())
    with pytest.raises(PaperParameterCorrectionError) as exc_info:
        await ParameterCorrectionService(invalid_store).apply(
            "paper-1",
            target=_target(expected_value="3.5", expected_unit="s"),
            corrected_value="4.0",
            corrected_unit=" ",
            corrected_unit_supplied=True,
        )
    assert exc_info.value.error_code == "correction_unit_invalid"


class _FakeBundleStore(PaperBundleStore):
    def __init__(self, record: PaperPlanRecord | None) -> None:
        self.record = record
        self.corrections: list[PaperParameterCorrection] = []
        self.apply_calls: list[bool] = []
        self.undo_calls: list[str] = []
        self.insert_calls = 0

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        self.record = record

    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        _ = paper_id
        return self.record.spec if self.record is not None else None

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        _ = paper_id
        return self.record

    async def put_spec(self, paper_id: str, spec: PaperSpec) -> None:
        _ = paper_id, spec

    async def set_plan(self, paper_id: str, record: PaperPlanRecord) -> None:
        _ = paper_id
        self.record = record

    async def delete_bundle(self, paper_id: str) -> None:
        _ = paper_id
        self.record = None
        self.corrections = []

    async def apply_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction: PaperParameterCorrection,
        *,
        is_recorrect: bool,
    ) -> None:
        _ = paper_id
        self.apply_calls.append(is_recorrect)
        self.record = updated_record
        if is_recorrect:
            self.corrections = [
                correction if item.correction_id == correction.correction_id else item
                for item in self.corrections
            ]
        else:
            self.corrections.append(correction)

    async def undo_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction_id: str,
    ) -> None:
        _ = paper_id
        self.undo_calls.append(correction_id)
        self.record = updated_record
        self.corrections = [
            correction
            for correction in self.corrections
            if correction.correction_id != correction_id
        ]

    async def insert_parameter_correction(self, correction: PaperParameterCorrection) -> None:
        self.insert_calls += 1
        self.corrections.append(correction)

    async def update_parameter_correction_value(
        self,
        paper_id: str,
        correction_id: str,
        corrected_value: str,
        corrected_unit: str | None,
        updated_at: str,
    ) -> None:
        _ = paper_id
        self.corrections = [
            (
                PaperParameterCorrection(
                    correction_id=correction.correction_id,
                    paper_id=correction.paper_id,
                    param_key=correction.param_key,
                    plan_target=correction.plan_target,
                    original_value=correction.original_value,
                    original_unit=correction.original_unit,
                    original_source=correction.original_source,
                    original_document_id=correction.original_document_id,
                    corrected_value=corrected_value,
                    corrected_unit=corrected_unit,
                    created_at=correction.created_at,
                    updated_at=updated_at,
                )
                if correction.correction_id == correction_id
                else correction
            )
            for correction in self.corrections
        ]

    async def get_parameter_correction(
        self,
        paper_id: str,
        correction_id: str,
    ) -> PaperParameterCorrection | None:
        return next(
            (
                correction
                for correction in self.corrections
                if correction.paper_id == paper_id and correction.correction_id == correction_id
            ),
            None,
        )

    async def list_parameter_corrections(
        self,
        paper_id: str,
    ) -> list[PaperParameterCorrection]:
        return [correction for correction in self.corrections if correction.paper_id == paper_id]

    async def delete_parameter_correction(self, paper_id: str, correction_id: str) -> None:
        self.corrections = [
            correction
            for correction in self.corrections
            if not (correction.paper_id == paper_id and correction.correction_id == correction_id)
        ]


def _target(*, expected_value: str, expected_unit: str | None) -> CorrectionTargetRequest:
    return CorrectionTargetRequest(
        paper_param_name="H",
        model_param_name="Synchronous Machine.H",
        plan_mapping_index=0,
        expected_value=expected_value,
        expected_unit=expected_unit,
    )


def _record(
    *,
    m_script_skeleton: str | None = None,
    build_steps: list[ModelBuildStep] | None = None,
) -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[
                BlockRecommendation(
                    block_type="Synchronous Machine",
                    purpose="Model the generator.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=m_script_skeleton,
            evidence=[evidence],
            build_steps=build_steps,
        ),
        missing_prompts=[],
        missing_bindings=[],
    )


def _record_with_filled_missing() -> PaperPlanRecord:
    record = _record()
    return PaperPlanRecord(
        paper_id=record.paper_id,
        spec=record.spec,
        plan=ModelGenerationPlan(
            plan_id=record.plan.plan_id,
            paper_spec_id=record.plan.paper_spec_id,
            library_choice=record.plan.library_choice,
            block_recommendations=record.plan.block_recommendations,
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.USER_SUPPLIED,
                )
            ],
            subsystem_breakdown=record.plan.subsystem_breakdown,
            m_script_skeleton=None,
            evidence=[record.plan.evidence[0], _fill_missing_evidence()],
        ),
        missing_prompts=[
            MissingParameterPrompt(
                prompt_id="MISS-1",
                parameter_name="H",
                paper_reference=_document_evidence(),
                suggested_unit="s",
                user_supplied_value=None,
                user_supplied_unit=None,
            )
        ],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


def _build_guidance() -> BuildGuidance:
    return BuildGuidance(
        version="v2",
        assessment=GuidanceAssessment(
            content_status="outline_only",
            environment_status="not_checked",
            overall_status="outline_only",
            blocking_gap_ids=[],
        ),
        details=[
            GuidanceDetail(
                detail_id="GD-001",
                step_id="STEP-001",
                detail_kind="parameter_value",
                basis="document_extracted",
                actionability="actionable",
                display_text="Use the documented machine inertia.",
                evidence=[_document_evidence()],
                convention_code=None,
                confirmation_reason_code=None,
                target=GuidanceTarget(
                    target_kind="parameter",
                    model_param="Synchronous Machine.H",
                    paper_param="H",
                ),
                obligation_kind="determine_parameter_value",
                resolution={
                    "kind": "fixed",
                    "fixed_kind": "numeric",
                    "value": 3.5,
                    "unit": "s",
                },
                execution_closure="closed",
                input_fact_refs=[],
                punt_reason_code=None,
            )
        ],
        gaps=[],
    )


def _spec() -> PaperSpec:
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A synchronous machine short-circuit report.",
        equations=[],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id="DOC-001",
            )
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[_document_evidence()],
    )


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )


def _fill_missing_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id="MISS-1",
        user_action=UserEvidenceAction.FILL_MISSING,
    )
