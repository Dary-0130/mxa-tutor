from dataclasses import FrozenInstanceError, fields

import pytest

from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
    MissingBindingModel,
    PlanAssembler,
    resolved_prompt_ids,
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
