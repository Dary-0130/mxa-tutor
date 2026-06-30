from dataclasses import fields

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterEntry,
)
from core.domain.paper_tuning import ParameterDirection, TuningSuggestion


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The document describes a short-circuit simulation.",
        missing_param_prompt_id=None,
    )


def test_paper_spec_fields_match_contract_order() -> None:
    assert [field.name for field in fields(PaperSpec)] == [
        "paper_title",
        "paper_type",
        "domain",
        "documents",
        "primary_document_id",
        "abstract",
        "equations",
        "parameter_table",
        "figure_locations",
        "pseudocode_blocks",
        "evidence",
    ]


def test_paper_spec_required_fields() -> None:
    evidence = _document_evidence()
    equation = EquationEntry(
        equation_id="EQ-1",
        latex_or_text="i = C e^{-t}",
        paper_section_id="S2",
        document_id="DOC-001",
    )
    parameter = ParameterEntry(
        name="Rated voltage",
        symbol="UN",
        value="13.8",
        unit="kV",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
    )
    figure = FigureRef(
        figure_id="FIG-1", caption="Model diagram", paper_section_id="S3", document_id="DOC-001"
    )
    spec = PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A report about short-circuit simulation.",
        equations=[equation],
        parameter_table=[parameter],
        figure_locations=[figure],
        pseudocode_blocks=["Compute current over sampled time."],
        evidence=[evidence],
    )

    assert spec.paper_type == "report"
    assert spec.domain == "motor_control"
    assert spec.equations == [equation]
    assert spec.parameter_table == [parameter]
    assert spec.figure_locations == [figure]
    assert spec.evidence == [evidence]


def test_serialize_only_domain_contracts_required_fields() -> None:
    evidence = _document_evidence()
    block = BlockRecommendation(
        block_type="Three-Phase Fault",
        purpose="Apply a short-circuit fault",
        paper_reference=evidence,
    )
    mapping = ParameterMapping(
        paper_param_name="UN",
        model_param_name="Nominal voltage",
        value="13.8",
        unit="kV",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )
    plan = ModelGenerationPlan(
        plan_id="plan-1",
        paper_spec_id="spec-1",
        library_choice="SimPowerSystems",
        block_recommendations=[block],
        parameter_mapping=[mapping],
        subsystem_breakdown=["Source", "Machine", "Fault"],
        m_script_skeleton=None,
        evidence=[evidence],
    )
    direction = ParameterDirection(
        param_name="Fault resistance",
        direction="increase",
        physical_meaning="Reduces short-circuit current.",
    )
    suggestion = TuningSuggestion(
        suggestion_id="tun-1",
        user_scenario="Short-circuit current is too high.",
        parameter_directions=[direction],
        expected_effect="Peak current decreases.",
        confidence="medium",
        evidence=[evidence],
        disclaimer="建议需用户在 MATLAB 中验证",
    )
    prompt = MissingParameterPrompt(
        prompt_id="MISS-1",
        parameter_name="Inertia constant",
        paper_reference=evidence,
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
    )

    assert plan.block_recommendations == [block]
    assert suggestion.parameter_directions == [direction]
    assert prompt.source is EvidenceSource.USER_SUPPLIED
