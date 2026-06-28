from dataclasses import FrozenInstanceError, fields, replace

import pytest

from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ConfigurationHint,
    ConnectionHint,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    BuildStepsEvidenceError,
    BuildStepsRedLineError,
    BuildStepsSemanticValidationError,
    EvidenceTagger,
    MissingBindingModel,
    ModelBuildStepDraft,
    PlanAssembler,
    resolved_prompt_ids,
    validate_build_step_evidence_for_spec,
)


class ResponseStub:
    def __init__(self, prompt_id: str) -> None:
        self.prompt_id = prompt_id


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
    excerpt: str | None = "The report states the machine parameter.",
    missing_param_prompt_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt=excerpt,
        missing_param_prompt_id=missing_param_prompt_id,
    )


def _user_evidence(
    *,
    paper_section_id: str | None = None,
    equation_id: str | None = None,
    figure_id: str | None = None,
    excerpt: str | None = None,
    missing_param_prompt_id: str | None = "MISS-1",
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt=excerpt,
        missing_param_prompt_id=missing_param_prompt_id,
    )


def test_missing_value_sentinel_literal_is_frozen() -> None:
    assert MISSING_VALUE_SENTINEL == "null"
    assert isinstance(MISSING_VALUE_SENTINEL, str)


def test_missing_binding_model_fields_are_frozen() -> None:
    binding = MissingBindingModel(
        prompt_id="MISS-1",
        paper_param_name="H",
        model_param_name="Synchronous Machine.H",
    )

    assert [field.name for field in fields(MissingBindingModel)] == [
        "prompt_id",
        "paper_param_name",
        "model_param_name",
    ]
    with pytest.raises(FrozenInstanceError):
        binding.prompt_id = "MISS-2"  # type: ignore[misc]


def test_evidence_tagger_accepts_document_and_user_supplied_evidence() -> None:
    spec = _spec()
    EvidenceTagger().validate_for_spec(
        [
            _document_evidence(),
            _document_evidence(equation_id="EQ-01"),
            _document_evidence(figure_id="FIG-01"),
            _user_evidence(),
        ],
        spec,
    )


@pytest.mark.parametrize(
    "entry",
    [
        _document_evidence(paper_section_id=None),
        _document_evidence(excerpt=""),
        _document_evidence(missing_param_prompt_id="MISS-1"),
        _document_evidence(paper_section_id="S9"),
        _user_evidence(paper_section_id="S1"),
        _user_evidence(missing_param_prompt_id=None),
    ],
)
def test_evidence_tagger_rejects_double_source_and_locator_violations(
    entry: PaperEvidenceEntry,
) -> None:
    with pytest.raises(PaperPlanGenerationError):
        EvidenceTagger().validate_for_spec([entry], _spec())


def test_tag_user_supplied_creates_user_evidence_entry() -> None:
    prompt = _missing_prompt()

    entry = EvidenceTagger().tag_user_supplied(ResponseStub("MISS-1"), prompt)

    assert entry == PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id="MISS-1",
    )


def test_tag_user_supplied_rejects_mismatched_prompt_id() -> None:
    with pytest.raises(PaperUserSupplyError):
        EvidenceTagger().tag_user_supplied(ResponseStub("MISS-2"), _missing_prompt())


def test_plan_assembler_merge_returns_plan_and_private_bindings() -> None:
    plan = _plan(parameter_mapping=[_mapping("H", MISSING_VALUE_SENTINEL)])

    assembled, bindings = PlanAssembler().merge(
        plan_composer_output=plan,
        subsystem_steps=["Place machine", "Apply fault"],
        mscript="disp('ok')",
        missing_prompts=[_missing_prompt()],
        paper_id="PAPER-1",
    )

    assert assembled.plan_id == "PLAN-PAPER-1"
    assert assembled.paper_spec_id == "PAPER-1"
    assert assembled.subsystem_breakdown == ["Place machine", "Apply fault"]
    assert assembled.m_script_skeleton == "disp('ok')"
    assert bindings == [
        MissingBindingModel(
            prompt_id="MISS-1",
            paper_param_name="H",
            model_param_name="Synchronous Machine.H",
        )
    ]
    assert not hasattr(assembled.parameter_mapping[0], "missing_param_prompt_id")


def test_plan_assembler_rejects_missing_binding_not_found() -> None:
    plan = _plan(parameter_mapping=[_mapping("H", "3.5")])

    with pytest.raises(PaperPlanGenerationError, match="missing_binding_not_found"):
        PlanAssembler().merge(
            plan_composer_output=plan,
            subsystem_steps=[],
            mscript=None,
            missing_prompts=[_missing_prompt()],
            paper_id="PAPER-1",
        )


def test_plan_assembler_rejects_missing_binding_ambiguous() -> None:
    plan = _plan(
        parameter_mapping=[
            _mapping("H", MISSING_VALUE_SENTINEL),
            _mapping("H", MISSING_VALUE_SENTINEL),
        ]
    )

    with pytest.raises(PaperPlanGenerationError, match="missing_binding_ambiguous"):
        PlanAssembler().merge(
            plan_composer_output=plan,
            subsystem_steps=[],
            mscript=None,
            missing_prompts=[_missing_prompt()],
            paper_id="PAPER-1",
        )


def test_resolved_prompt_ids_requires_all_five_conditions() -> None:
    record = _record(
        mapping=_mapping("H", "3.5", source=EvidenceSource.USER_SUPPLIED),
        plan_evidence=[_document_evidence(), _user_evidence(missing_param_prompt_id="MISS-1")],
    )

    assert resolved_prompt_ids(record) == frozenset({"MISS-1"})

    unresolved_value = _record(
        mapping=_mapping("H", MISSING_VALUE_SENTINEL, source=EvidenceSource.USER_SUPPLIED),
        plan_evidence=[_document_evidence(), _user_evidence(missing_param_prompt_id="MISS-1")],
    )
    unresolved_source = _record(
        mapping=_mapping("H", "3.5", source=EvidenceSource.DOCUMENT_EXTRACTED),
        plan_evidence=[_document_evidence(), _user_evidence(missing_param_prompt_id="MISS-1")],
    )
    unresolved_evidence = _record(
        mapping=_mapping("H", "3.5", source=EvidenceSource.USER_SUPPLIED),
        plan_evidence=[_document_evidence()],
    )
    duplicate_binding = _record(
        mapping=_mapping("H", "3.5", source=EvidenceSource.USER_SUPPLIED),
        bindings=[
            MissingBindingModel(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            ),
            MissingBindingModel(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            ),
        ],
        plan_evidence=[_document_evidence(), _user_evidence(missing_param_prompt_id="MISS-1")],
    )

    assert resolved_prompt_ids(unresolved_value) == frozenset()
    assert resolved_prompt_ids(unresolved_source) == frozenset()
    assert resolved_prompt_ids(unresolved_evidence) == frozenset()
    assert resolved_prompt_ids(duplicate_binding) == frozenset()


def test_validate_for_record_accepts_resolved_user_evidence() -> None:
    record = _record(
        mapping=_mapping("H", "3.5", source=EvidenceSource.USER_SUPPLIED),
        plan_evidence=[_document_evidence(), _user_evidence(missing_param_prompt_id="MISS-1")],
    )

    EvidenceTagger().validate_for_record([_user_evidence(missing_param_prompt_id="MISS-1")], record)


def test_validate_for_record_rejects_unresolved_user_evidence() -> None:
    record = _record(
        mapping=_mapping("H", MISSING_VALUE_SENTINEL, source=EvidenceSource.USER_SUPPLIED),
        plan_evidence=[_document_evidence()],
    )

    with pytest.raises(PaperPlanGenerationError, match="user_evidence_unresolved_prompt"):
        EvidenceTagger().validate_for_record(
            [_user_evidence(missing_param_prompt_id="MISS-1")],
            record,
        )


def test_validate_and_derive_build_steps_success_derives_display_text() -> None:
    steps = PlanAssembler().validate_and_derive_build_steps(
        _build_step_drafts(),
        [_mapping("H", MISSING_VALUE_SENTINEL)],
        [_block_recommendation()],
    )

    assert [step.step_id for step in steps] == ["STEP-001", "STEP-002", "STEP-003"]
    assert all(step.display_text for step in steps)
    assert steps[0].display_text.startswith("STEP-001 Place machine block")


def test_build_steps_can_be_topologically_sorted_before_validation() -> None:
    drafts = _build_step_drafts()

    steps = PlanAssembler().validate_and_derive_build_steps(
        [drafts[1], drafts[0], drafts[2]],
        [_mapping("H", MISSING_VALUE_SENTINEL)],
        [_block_recommendation()],
    )

    assert [step.step_id for step in steps] == ["STEP-001", "STEP-002", "STEP-003"]


@pytest.mark.parametrize(
    ("drafts_factory", "reason"),
    [
        (lambda: [], "empty_steps"),
        (
            lambda: [replace(step, step_id="BAD-1") for step in _build_step_drafts()],
            "step_id_invalid",
        ),
        (
            lambda: [replace(step, step_id="STEP-001") for step in _build_step_drafts()],
            "step_id_duplicate",
        ),
        (
            lambda: [
                replace(_build_step_drafts()[0], depends_on=["STEP-003"]),
                *_build_step_drafts()[1:],
            ],
            "depends_on_cycle",
        ),
    ],
)
def test_build_steps_reject_step_id_and_dependency_errors(
    drafts_factory: object,
    reason: str,
) -> None:
    drafts = drafts_factory()
    with pytest.raises(BuildStepsSemanticValidationError, match=reason):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [_block_recommendation()],
        )


def test_parameter_mapping_refs_require_exact_composite_match() -> None:
    drafts = _build_step_drafts()

    with pytest.raises(BuildStepsSemanticValidationError, match="parameter_ref_no_match"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Different.H",
                    value=MISSING_VALUE_SENTINEL,
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            [_block_recommendation()],
        )

    with pytest.raises(BuildStepsSemanticValidationError, match="parameter_mapping_duplicate"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL), _mapping("H", "4.0")],
            [_block_recommendation()],
        )


def test_block_refs_match_recommendations_by_normalized_type_and_purpose() -> None:
    drafts = _build_step_drafts()
    drafts[0] = replace(
        drafts[0],
        block_refs=[
            replace(
                drafts[0].block_refs[0],
                block_type=" synchronous   machine ",
                purpose=" model  THE generator. ",
            )
        ],
    )

    steps = PlanAssembler().validate_and_derive_build_steps(
        drafts,
        [_mapping("H", MISSING_VALUE_SENTINEL)],
        [_block_recommendation()],
    )

    assert steps[0].block_refs[0].block_ref_id == "B1"


def test_block_recommendation_internal_keys_are_deterministic_by_array_order() -> None:
    recommendation_index = PlanAssembler()._build_recommendation_index(
        [
            _block_recommendation(),
            BlockRecommendation("Scope", "Display current.", _document_evidence()),
        ]
    )

    assert list(recommendation_index.values()) == ["BR-001", "BR-002"]


def test_block_refs_reject_no_match_and_duplicate_recommendation_pair() -> None:
    drafts = _build_step_drafts()

    with pytest.raises(BuildStepsSemanticValidationError, match="br_no_match"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [
                BlockRecommendation(
                    block_type="Scope",
                    purpose="Display current.",
                    paper_reference=_document_evidence(),
                )
            ],
        )

    with pytest.raises(BuildStepsSemanticValidationError, match="br_ambiguous"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [_block_recommendation(), _block_recommendation()],
        )


def test_block_ref_id_is_global_and_connection_refs_must_be_visible() -> None:
    drafts = _build_step_drafts()
    drafts[1] = replace(
        drafts[1],
        block_refs=[replace(drafts[0].block_refs[0], block_ref_id="B1")],
        parameter_refs=[],
    )

    with pytest.raises(BuildStepsSemanticValidationError, match="block_ref_id_duplicate"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [_block_recommendation()],
        )

    invisible = _build_step_drafts()
    invisible[2] = replace(
        invisible[2],
        connection_hints=[
            ConnectionHint(
                from_block_ref="B99",
                from_port=None,
                to_block_ref="B1",
                to_port=None,
                signal_meaning="route measured current",
            )
        ],
        configuration_hints=[],
    )
    with pytest.raises(BuildStepsSemanticValidationError, match="connection_ref_not_visible"):
        PlanAssembler().validate_and_derive_build_steps(
            invisible,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [_block_recommendation()],
        )


def test_each_step_must_have_operable_structure_and_cover_recommendations() -> None:
    drafts = _build_step_drafts()
    drafts[2] = replace(
        drafts[2],
        block_refs=[],
        parameter_refs=[],
        connection_hints=[],
        configuration_hints=[],
    )

    with pytest.raises(BuildStepsSemanticValidationError, match="step_not_operable"):
        PlanAssembler().validate_and_derive_build_steps(
            drafts,
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [_block_recommendation()],
        )

    with pytest.raises(BuildStepsSemanticValidationError, match="coverage_missing"):
        PlanAssembler().validate_and_derive_build_steps(
            _build_step_drafts(),
            [_mapping("H", MISSING_VALUE_SENTINEL)],
            [
                _block_recommendation(),
                BlockRecommendation("Scope", "Display current.", _document_evidence()),
            ],
        )


def test_coverage_is_vacuous_when_recommendations_are_empty() -> None:
    drafts = _build_step_drafts()
    drafts[0] = replace(drafts[0], block_refs=[], configuration_hints=[_config_hint()])

    steps = PlanAssembler().validate_and_derive_build_steps(
        drafts,
        [_mapping("H", MISSING_VALUE_SENTINEL)],
        [],
    )

    assert len(steps) == 3


def test_display_text_does_not_dereference_parameter_value_or_unit() -> None:
    steps = PlanAssembler().validate_and_derive_build_steps(
        _build_step_drafts(paper_param_name="Rs", model_param_name="Synchronous Machine.Rs"),
        [
            ParameterMapping(
                paper_param_name="Rs",
                model_param_name="Synchronous Machine.Rs",
                value="0.05",
                unit="Ω",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        [_block_recommendation()],
    )

    display_text = "\n".join(step.display_text for step in steps)
    assert "Rs" in display_text
    assert "0.05" not in display_text
    assert "Ω" not in display_text


def test_redline_rejects_naked_value_and_config_allowlist_has_reverse_check() -> None:
    drafts = _build_step_drafts(paper_param_name="Rs", model_param_name="Synchronous Machine.Rs")
    mapping = ParameterMapping(
        paper_param_name="Rs",
        model_param_name="Synchronous Machine.Rs",
        value="0.05",
        unit="Ω",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )
    leaking = list(drafts)
    leaking[0] = replace(leaking[0], title="Place source with 0.05 Ω")

    with pytest.raises(BuildStepsRedLineError, match="parameter_value_leak"):
        PlanAssembler().validate_and_derive_build_steps(
            leaking,
            [mapping],
            [_block_recommendation()],
        )

    allowed = list(drafts)
    allowed[2] = replace(
        allowed[2],
        configuration_hints=[
            ConfigurationHint(
                target="solver",
                setting_name="Relative tolerance",
                instruction="Set solver tolerance to 0.05 Ω.",
                evidence=[_document_evidence()],
            )
        ],
    )
    PlanAssembler().validate_and_derive_build_steps(allowed, [mapping], [_block_recommendation()])

    reversed_setting = list(drafts)
    reversed_setting[2] = replace(
        reversed_setting[2],
        configuration_hints=[
            ConfigurationHint(
                target="solver",
                setting_name="Synchronous Machine.Rs",
                instruction="Set solver tolerance to 0.05 Ω.",
                evidence=[_document_evidence()],
            )
        ],
    )
    with pytest.raises(BuildStepsRedLineError, match="parameter_value_leak"):
        PlanAssembler().validate_and_derive_build_steps(
            reversed_setting,
            [mapping],
            [_block_recommendation()],
        )


def test_build_step_evidence_helper_rejects_unresolved_user_supplied_evidence() -> None:
    with pytest.raises(BuildStepsEvidenceError, match="user_supplied_evidence_not_allowed"):
        validate_build_step_evidence_for_spec(
            [_user_evidence(missing_param_prompt_id="MISS-1")],
            _spec(),
            allowed_user_prompt_ids=frozenset(),
        )

    validate_build_step_evidence_for_spec(
        [_user_evidence(missing_param_prompt_id="MISS-1")],
        _spec(),
        allowed_user_prompt_ids=frozenset({"MISS-1"}),
    )


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        abstract="A synchronous machine short-circuit report.",
        equations=[
            EquationEntry(
                equation_id="EQ-01",
                latex_or_text="H = 3.5",
                paper_section_id="S1",
            )
        ],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        figure_locations=[
            FigureRef(figure_id="FIG-01", caption="Machine parameters", paper_section_id="S1")
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _build_step_drafts(
    *,
    paper_param_name: str = "H",
    model_param_name: str = "Synchronous Machine.H",
) -> list[ModelBuildStepDraft]:
    return [
        ModelBuildStepDraft(
            step_id="STEP-001",
            title="Place machine block",
            intent="Create the machine subsystem entry point.",
            block_refs=[
                StepBlockRef(
                    block_ref_id="B1",
                    block_type="Synchronous Machine",
                    library_path=None,
                    purpose="Model the generator.",
                    paper_reference=_document_evidence(),
                )
            ],
            parameter_refs=[],
            connection_hints=[],
            configuration_hints=[],
            depends_on=[],
            evidence=[_document_evidence()],
        ),
        ModelBuildStepDraft(
            step_id="STEP-002",
            title="Bind machine parameter",
            intent="Link the paper parameter name to the model slot.",
            block_refs=[],
            parameter_refs=[
                ParameterMappingRef(
                    paper_param_name=paper_param_name,
                    model_param_name=model_param_name,
                )
            ],
            connection_hints=[],
            configuration_hints=[],
            depends_on=["STEP-001"],
            evidence=[_document_evidence()],
        ),
        ModelBuildStepDraft(
            step_id="STEP-003",
            title="Prepare simulation observation",
            intent="Keep the simulation output ready for comparison.",
            block_refs=[],
            parameter_refs=[],
            connection_hints=[],
            configuration_hints=[_config_hint()],
            depends_on=["STEP-001"],
            evidence=[_document_evidence()],
        ),
    ]


def _config_hint() -> ConfigurationHint:
    return ConfigurationHint(
        target="simulation",
        setting_name="Signal logging",
        instruction="Record the generated current signal.",
        evidence=[_document_evidence()],
    )


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Synchronous Machine",
        purpose="Model the generator.",
        paper_reference=_document_evidence(),
    )


def _record(
    *,
    mapping: ParameterMapping,
    plan_evidence: list[PaperEvidenceEntry],
    bindings: list[MissingBindingModel] | None = None,
) -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="PAPER-1",
        spec=_spec(),
        plan=_plan(parameter_mapping=[mapping], plan_evidence=plan_evidence),
        missing_prompts=[_missing_prompt()],
        missing_bindings=bindings
        or [
            MissingBindingModel(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


def _plan(
    parameter_mapping: list[ParameterMapping],
    plan_evidence: list[PaperEvidenceEntry] | None = None,
) -> ModelGenerationPlan:
    block_evidence = _document_evidence()
    return ModelGenerationPlan(
        plan_id="PLAN-BAD",
        paper_spec_id="BAD",
        library_choice="SimPowerSystems",
        block_recommendations=[
            BlockRecommendation(
                block_type="Synchronous Machine",
                purpose="Model the generator.",
                paper_reference=block_evidence,
            )
        ],
        parameter_mapping=parameter_mapping,
        subsystem_breakdown=[],
        m_script_skeleton=None,
        evidence=plan_evidence if plan_evidence is not None else [_document_evidence()],
    )


def _mapping(
    paper_param_name: str,
    value: str,
    *,
    source: EvidenceSource = EvidenceSource.DOCUMENT_EXTRACTED,
) -> ParameterMapping:
    return ParameterMapping(
        paper_param_name=paper_param_name,
        model_param_name=f"Synchronous Machine.{paper_param_name}",
        value=value,
        unit="s",
        source=source,
    )


def _missing_prompt() -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id="MISS-1",
        parameter_name="H",
        paper_reference=_document_evidence(figure_id="FIG-01"),
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
    )
