from dataclasses import fields
from typing import Any, get_args

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from core.domain.paper_ask import (
    EquationTarget,
    MissingPromptParameterTarget,
    PaperAskCitation,
    PaperAskFallbackReason,
    PaperAskRequest,
    PaperAskResponse,
    PlanMappingParameterTarget,
    SectionTarget,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ConfigurationHint,
    ConnectionHint,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterConflict,
    ParameterConflictObservation,
    ParameterConflictValueOption,
    ParameterEntry,
)
from core.domain.paper_tuning import ParameterDirection, TuningSuggestion
from features.paper.paper_ask_schemas import (
    EquationTargetModel,
    MissingPromptParameterTargetModel,
    PaperAskCitationModel,
    PaperAskRequestModel,
    PaperAskResponseModel,
    PaperCitationTargetModel,
    PlanMappingParameterTargetModel,
    SectionTargetModel,
)
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    ConfigurationHintModel,
    ConnectionHintModel,
    EquationEntryModel,
    FigureRefModel,
    MissingParameterPromptModel,
    ModelBuildStepModel,
    ModelGenerationPlanModel,
    PaperDocumentModel,
    PaperEvidenceEntryModel,
    PaperSpecModel,
    ParameterConflictModel,
    ParameterConflictObservationModel,
    ParameterConflictValueOptionModel,
    ParameterDirectionModel,
    ParameterEntryModel,
    ParameterMappingModel,
    ParameterMappingRefModel,
    StepBlockRefModel,
    TuningSuggestionModel,
)

TOP_LEVEL_MODELS = (
    PaperEvidenceEntryModel,
    PaperSpecModel,
    ModelGenerationPlanModel,
    TuningSuggestionModel,
    MissingParameterPromptModel,
    PaperAskRequestModel,
    PaperAskResponseModel,
)

NESTED_MODELS = (
    EquationEntryModel,
    ParameterEntryModel,
    ParameterConflictObservationModel,
    ParameterConflictValueOptionModel,
    ParameterConflictModel,
    PaperDocumentModel,
    FigureRefModel,
    BlockRecommendationModel,
    ParameterMappingModel,
    StepBlockRefModel,
    ParameterMappingRefModel,
    ConnectionHintModel,
    ConfigurationHintModel,
    ModelBuildStepModel,
    ParameterDirectionModel,
    PaperAskCitationModel,
    SectionTargetModel,
    EquationTargetModel,
    PlanMappingParameterTargetModel,
    MissingPromptParameterTargetModel,
)


def _document_evidence_payload() -> dict[str, object]:
    return {
        "source": "document_extracted",
        "document_id": "DOC-001",
        "paper_section_id": "S1",
        "equation_id": None,
        "figure_id": None,
        "excerpt": "The document states the simulation target.",
        "missing_param_prompt_id": None,
    }


def _user_evidence_payload() -> dict[str, object]:
    return {
        "source": "user_supplied",
        "document_id": None,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": "MISS-1",
        "user_action": "fill_missing",
        "parameter_correction_id": None,
        "correction_param_key": None,
    }


def _correction_evidence_payload() -> dict[str, object]:
    return {
        "source": "user_supplied",
        "document_id": None,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": None,
        "user_action": "correct_extracted",
        "parameter_correction_id": "CORR-1",
        "correction_param_key": "H::Synchronous Machine.H",
    }


def _paper_ask_citation_payload(
    *,
    source_kind: str = "document_extracted",
    excerpt: str | None = "The report states the machine component.",
    target: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "source_id": "S1",
        "label": "Paper summary",
        "excerpt": excerpt,
        "source_kind": source_kind,
        "target": target
        or {
            "kind": "section",
            "result_section": "paper-summary",
        },
    }


def _constraint_value(schema_cls: type[BaseModel], field_name: str, constraint_name: str) -> Any:
    field_info = schema_cls.model_fields[field_name]
    for item in field_info.metadata:
        if hasattr(item, constraint_name):
            return getattr(item, constraint_name)
    return None


def test_top_level_model_count_and_names_are_frozen() -> None:
    assert [model.__name__ for model in TOP_LEVEL_MODELS] == [
        "PaperEvidenceEntryModel",
        "PaperSpecModel",
        "ModelGenerationPlanModel",
        "TuningSuggestionModel",
        "MissingParameterPromptModel",
        "PaperAskRequestModel",
        "PaperAskResponseModel",
    ]


def test_nested_model_count_and_names_are_frozen() -> None:
    assert [model.__name__ for model in NESTED_MODELS] == [
        "EquationEntryModel",
        "ParameterEntryModel",
        "ParameterConflictObservationModel",
        "ParameterConflictValueOptionModel",
        "ParameterConflictModel",
        "PaperDocumentModel",
        "FigureRefModel",
        "BlockRecommendationModel",
        "ParameterMappingModel",
        "StepBlockRefModel",
        "ParameterMappingRefModel",
        "ConnectionHintModel",
        "ConfigurationHintModel",
        "ModelBuildStepModel",
        "ParameterDirectionModel",
        "PaperAskCitationModel",
        "SectionTargetModel",
        "EquationTargetModel",
        "PlanMappingParameterTargetModel",
        "MissingPromptParameterTargetModel",
    ]


@pytest.mark.parametrize("model", TOP_LEVEL_MODELS + NESTED_MODELS)
def test_extra_forbid_at_all_levels(model: type[BaseModel]) -> None:
    assert model.model_config.get("extra") == "forbid"


def test_evidence_source_reuses_core_enum() -> None:
    assert PaperEvidenceEntryModel.model_fields["source"].annotation is EvidenceSource


def test_paper_spec_field_order_matches_domain() -> None:
    assert tuple(PaperSpecModel.model_fields) == tuple(field.name for field in fields(PaperSpec))


def test_serialize_only_field_order_matches_domain() -> None:
    assert tuple(ModelGenerationPlanModel.model_fields) == tuple(
        field.name for field in fields(ModelGenerationPlan)
    )
    assert tuple(TuningSuggestionModel.model_fields) == tuple(
        field.name for field in fields(TuningSuggestion)
    )
    assert tuple(MissingParameterPromptModel.model_fields) == tuple(
        field.name for field in fields(MissingParameterPrompt)
    )
    assert tuple(PaperAskRequestModel.model_fields) == tuple(
        field.name for field in fields(PaperAskRequest)
    )
    assert tuple(PaperAskResponseModel.model_fields) == tuple(
        field.name for field in fields(PaperAskResponse)
    )


def test_nested_field_order_matches_domain() -> None:
    assert tuple(EquationEntryModel.model_fields) == tuple(
        field.name for field in fields(EquationEntry)
    )
    assert tuple(ParameterEntryModel.model_fields) == tuple(
        field.name for field in fields(ParameterEntry)
    )
    assert tuple(ParameterConflictObservationModel.model_fields) == tuple(
        field.name for field in fields(ParameterConflictObservation)
    )
    assert tuple(ParameterConflictValueOptionModel.model_fields) == tuple(
        field.name for field in fields(ParameterConflictValueOption)
    )
    assert tuple(ParameterConflictModel.model_fields) == tuple(
        field.name for field in fields(ParameterConflict)
    )
    assert tuple(PaperDocumentModel.model_fields) == tuple(
        field.name for field in fields(PaperDocument)
    )
    assert tuple(FigureRefModel.model_fields) == tuple(field.name for field in fields(FigureRef))
    assert tuple(BlockRecommendationModel.model_fields) == tuple(
        field.name for field in fields(BlockRecommendation)
    )
    assert tuple(ParameterMappingModel.model_fields) == tuple(
        field.name for field in fields(ParameterMapping)
    )
    assert tuple(StepBlockRefModel.model_fields) == tuple(
        field.name for field in fields(StepBlockRef)
    )
    assert tuple(ParameterMappingRefModel.model_fields) == tuple(
        field.name for field in fields(ParameterMappingRef)
    )
    assert tuple(ConnectionHintModel.model_fields) == tuple(
        field.name for field in fields(ConnectionHint)
    )
    assert tuple(ConfigurationHintModel.model_fields) == tuple(
        field.name for field in fields(ConfigurationHint)
    )
    assert tuple(ModelBuildStepModel.model_fields) == tuple(
        field.name for field in fields(ModelBuildStep)
    )
    assert tuple(ParameterDirectionModel.model_fields) == tuple(
        field.name for field in fields(ParameterDirection)
    )
    assert tuple(PaperAskCitationModel.model_fields) == tuple(
        field.name for field in fields(PaperAskCitation)
    )
    assert tuple(SectionTargetModel.model_fields) == tuple(
        field.name for field in fields(SectionTarget)
    )
    assert tuple(EquationTargetModel.model_fields) == tuple(
        field.name for field in fields(EquationTarget)
    )
    assert tuple(PlanMappingParameterTargetModel.model_fields) == tuple(
        field.name for field in fields(PlanMappingParameterTarget)
    )
    assert tuple(MissingPromptParameterTargetModel.model_fields) == tuple(
        field.name for field in fields(MissingPromptParameterTarget)
    )


def test_model_generation_plan_micro_patch_constraints_are_frozen() -> None:
    assert _constraint_value(ModelGenerationPlanModel, "library_choice", "min_length") == 1
    assert _constraint_value(ModelGenerationPlanModel, "library_choice", "max_length") == 300
    assert ParameterMappingModel.model_fields["unit"].annotation == str | None
    assert fields(ParameterMapping)[3].type == str | None
    assert ModelGenerationPlanModel.model_fields["build_steps"].annotation == (
        list[ModelBuildStepModel] | None
    )
    assert fields(ModelGenerationPlan)[8].type == list[ModelBuildStep] | None


def test_document_identity_fields_are_required_but_nullable_where_expected() -> None:
    assert PaperSpecModel.model_fields["documents"].is_required()
    assert PaperSpecModel.model_fields["primary_document_id"].is_required()
    assert PaperSpecModel.model_fields["parameter_conflicts"].default_factory is list
    assert PaperEvidenceEntryModel.model_fields["document_id"].is_required()
    assert ParameterEntryModel.model_fields["document_id"].is_required()
    assert EquationEntryModel.model_fields["document_id"].is_required()
    assert FigureRefModel.model_fields["document_id"].is_required()

    spec_payload = _paper_spec_payload(primary_document_id=None)
    assert PaperSpecModel.model_validate(spec_payload).primary_document_id is None

    with pytest.raises(ValidationError):
        PaperSpecModel.model_validate(_without(spec_payload, "primary_document_id"))
    with pytest.raises(ValidationError):
        PaperSpecModel.model_validate(_without(spec_payload, "documents"))
    with pytest.raises(ValidationError):
        PaperEvidenceEntryModel.model_validate(
            _without(_document_evidence_payload(), "document_id")
        )
    with pytest.raises(ValidationError):
        ParameterEntryModel.model_validate(_without(_document_parameter_payload(), "document_id"))
    with pytest.raises(ValidationError):
        EquationEntryModel.model_validate(_without(_equation_payload(), "document_id"))
    with pytest.raises(ValidationError):
        FigureRefModel.model_validate(_without(_figure_payload(), "document_id"))

    assert PaperEvidenceEntryModel.model_validate(_user_evidence_payload()).document_id is None
    assert ParameterEntryModel.model_validate(_user_parameter_payload()).document_id is None
    assert (
        EquationEntryModel.model_validate(_equation_payload(document_id=None)).document_id is None
    )
    assert FigureRefModel.model_validate(_figure_payload(document_id=None)).document_id is None


def test_paper_spec_document_identity_invariants_are_enforced() -> None:
    assert PaperSpecModel.model_validate(_paper_spec_payload()).to_domain().documents[0].document_id

    invalid_payloads = [
        _paper_spec_payload(documents=[]),
        _paper_spec_payload(
            documents=[
                {"document_id": "DOC-001", "filename": "paper-a.pdf"},
                {"document_id": "DOC-001", "filename": "paper-b.pdf"},
            ]
        ),
        _paper_spec_payload(documents=[{"document_id": "DOC-1", "filename": "paper.pdf"}]),
        _paper_spec_payload(documents=[{"document_id": "DOC-001", "filename": "bad/name.pdf"}]),
        _paper_spec_payload(documents=[{"document_id": "DOC-001", "filename": "bad\nname.pdf"}]),
        _paper_spec_payload(primary_document_id="DOC-999"),
        _paper_spec_payload(evidence=[{**_document_evidence_payload(), "document_id": "DOC-999"}]),
        _paper_spec_payload(
            parameter_table=[{**_document_parameter_payload(), "document_id": "DOC-999"}]
        ),
        _paper_spec_payload(equations=[{**_equation_payload(), "document_id": "DOC-999"}]),
        _paper_spec_payload(figure_locations=[{**_figure_payload(), "document_id": "DOC-999"}]),
        _paper_spec_payload(
            parameter_conflicts=[
                {
                    "parameter_name": "Inertia",
                    "parameter_symbol": "H",
                    "value_options": [
                        {
                            "value": "3.5",
                            "unit": "s",
                            "observations": [
                                {
                                    "document_id": "DOC-999",
                                    "locator": None,
                                    "excerpt": None,
                                }
                            ],
                        },
                        {
                            "value": "4.0",
                            "unit": "s",
                            "observations": [
                                {
                                    "document_id": "DOC-001",
                                    "locator": None,
                                    "excerpt": None,
                                }
                            ],
                        },
                    ],
                }
            ]
        ),
        _paper_spec_payload(
            parameter_table=[{**_user_parameter_payload(), "document_id": "DOC-001"}]
        ),
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            PaperSpecModel.model_validate(payload)


def test_build_steps_none_missing_and_non_empty_roundtrip() -> None:
    legacy_payload = _plan_payload()

    legacy_model = ModelGenerationPlanModel.model_validate(legacy_payload)
    explicit_none_model = ModelGenerationPlanModel.model_validate(
        {**legacy_payload, "build_steps": None}
    )
    with_build_steps_model = ModelGenerationPlanModel.from_domain(_plan_domain(build_steps=True))

    assert legacy_model.build_steps is None
    assert legacy_model.to_domain().build_steps is None
    assert explicit_none_model.to_domain().build_steps is None
    assert with_build_steps_model.to_domain().build_steps == _build_steps()


def test_build_steps_empty_rejected_and_json_schema_has_min_items() -> None:
    with pytest.raises(ValidationError):
        ModelGenerationPlanModel.model_validate({**_plan_payload(), "build_steps": []})

    build_steps_schema = ModelGenerationPlanModel.model_json_schema()["properties"]["build_steps"]
    assert build_steps_schema["anyOf"][0]["minItems"] == 1


def test_paper_ask_defaults_and_literals_are_frozen() -> None:
    assert PaperAskRequestModel.model_fields["session_id"].default is None
    assert PaperAskCitationModel.model_fields["document_id"].default is None
    assert PaperAskCitationModel.model_fields["document_label"].default is None
    assert not PaperAskCitationModel.model_fields["document_id"].is_required()
    assert not PaperAskCitationModel.model_fields["document_label"].is_required()
    assert PaperAskResponseModel.model_fields["is_fallback"].default is False
    assert PaperAskResponseModel.model_fields["fallback_reason"].default is None
    citation_schema = PaperAskCitationModel.model_json_schema()
    assert "document_id" not in citation_schema["required"]
    assert "document_label" not in citation_schema["required"]
    assert get_args(PaperAskFallbackReason) == (
        "insufficient_evidence",
        "invalid_or_missing_citations",
        "citation_target_unresolved",
        "out_of_scope",
    )


def test_paper_ask_target_union_roundtrips_four_variants() -> None:
    adapter = TypeAdapter(PaperCitationTargetModel)
    payloads = [
        {"kind": "section", "result_section": "paper-summary"},
        {"kind": "equation", "equation_id": "EQ-main"},
        {
            "kind": "parameter",
            "origin": "plan_mapping",
            "row_index": 0,
            "paper_param_name": "Inertia",
            "model_param_name": "Machine inertia",
        },
        {
            "kind": "parameter",
            "origin": "missing_prompt",
            "prompt_id": "MISS-H",
            "parameter_name": "Damping",
        },
    ]

    for payload in payloads:
        model = adapter.validate_python(payload)
        assert adapter.dump_python(model, mode="json") == payload


def test_paper_ask_response_invariants_are_enforced() -> None:
    success_payload = {
        "session_id": "session-1",
        "message_id": "message-1",
        "answer": "The source supports this answer.",
        "confidence": "medium",
        "citations": [_paper_ask_citation_payload()],
        "follow_up_suggestions": [],
        "is_fallback": False,
        "fallback_reason": None,
    }
    fallback_payload = {
        **success_payload,
        "citations": [],
        "confidence": "low",
        "is_fallback": True,
        "fallback_reason": "insufficient_evidence",
    }

    assert PaperAskResponseModel.model_validate(success_payload).to_domain().citations
    assert PaperAskResponseModel.model_validate(fallback_payload).to_domain().is_fallback

    with pytest.raises(ValidationError):
        PaperAskResponseModel.model_validate({**success_payload, "citations": []})
    with pytest.raises(ValidationError):
        PaperAskResponseModel.model_validate({**fallback_payload, "confidence": "medium"})


def test_paper_ask_citation_document_fields_are_optional_nullable_and_roundtrip() -> None:
    missing_model = PaperAskCitationModel.model_validate(_paper_ask_citation_payload())
    assert missing_model.document_id is None
    assert missing_model.document_label is None

    null_payload = {
        **_paper_ask_citation_payload(),
        "document_id": None,
        "document_label": None,
    }
    null_model = PaperAskCitationModel.model_validate(null_payload)
    assert null_model.document_id is None
    assert null_model.document_label is None

    valued_payload = {
        **_paper_ask_citation_payload(),
        "document_id": "DOC-002",
        "document_label": "paper-b.pdf",
    }
    valued_model = PaperAskCitationModel.model_validate(valued_payload)

    assert (
        PaperAskCitationModel.from_domain(valued_model.to_domain()).model_dump(mode="json")
        == valued_payload
    )


def test_paper_ask_source_kind_excerpt_invariant_is_enforced() -> None:
    assert PaperAskCitationModel.model_validate(_paper_ask_citation_payload()).excerpt
    assert (
        PaperAskCitationModel.model_validate(
            _paper_ask_citation_payload(source_kind="user_supplied", excerpt=None)
        ).excerpt
        is None
    )

    with pytest.raises(ValidationError):
        PaperAskCitationModel.model_validate(_paper_ask_citation_payload(excerpt=None))
    with pytest.raises(ValidationError):
        PaperAskCitationModel.model_validate(
            _paper_ask_citation_payload(source_kind="user_supplied", excerpt="bad")
        )
    with pytest.raises(ValidationError):
        PaperAskCitationModel.model_validate(
            {
                **_paper_ask_citation_payload(source_kind="user_supplied", excerpt=None),
                "document_id": "DOC-001",
                "document_label": "paper.pdf",
            }
        )


def test_paper_ask_question_blank_rejected_without_trimming_value() -> None:
    model = PaperAskRequestModel.model_validate({"question": "  keep me  "})
    assert model.question == "  keep me  "
    with pytest.raises(ValidationError):
        PaperAskRequestModel.model_validate({"question": "   "})


def test_answer_kind_is_internal_and_not_exported_in_public_response_schema() -> None:
    schema_text = str(PaperAskResponseModel.model_json_schema())
    assert "answer_kind" not in schema_text


def test_new_build_step_submodel_extra_forbid_is_enforced() -> None:
    payload = _build_step_payload()
    payload["extra_field"] = "not allowed"

    with pytest.raises(ValidationError):
        ModelBuildStepModel.model_validate(payload)


def test_parameter_mapping_unit_accepts_null() -> None:
    payload = {
        "paper_param_name": "Transformer connection",
        "model_param_name": "Winding connection",
        "value": "Yn / d11",
        "unit": None,
        "source": "user_supplied",
    }

    model = ParameterMappingModel.model_validate(payload)

    assert model.unit is None
    assert ParameterMappingModel.from_domain(model.to_domain()).model_dump(mode="json") == payload


def test_parameter_conflicts_must_match_parameter_table_materialized_view() -> None:
    parameter_table = [
        {**_document_parameter_payload(), "document_id": "DOC-001", "value": "3.5"},
        {**_document_parameter_payload(), "document_id": "DOC-002", "value": "4.0"},
    ]
    valid_conflict = {
        "parameter_name": "Rated capacity",
        "parameter_symbol": "PN",
        "value_options": [
            {
                "value": "3.5",
                "unit": "MW",
                "observations": [{"document_id": "DOC-001", "locator": None, "excerpt": None}],
            },
            {
                "value": "4.0",
                "unit": "MW",
                "observations": [{"document_id": "DOC-002", "locator": None, "excerpt": None}],
            },
        ],
    }
    payload = _paper_spec_payload(
        documents=[
            {"document_id": "DOC-001", "filename": "paper-a.pdf"},
            {"document_id": "DOC-002", "filename": "paper-b.pdf"},
        ],
        parameter_table=parameter_table,
        parameter_conflicts=[valid_conflict],
    )

    model = PaperSpecModel.model_validate(payload)

    assert model.parameter_conflicts[0].value_options[0].observations[0].locator is None
    with pytest.raises(ValidationError):
        PaperSpecModel.model_validate({**payload, "parameter_conflicts": []})


def test_domain_literal_rejects_general() -> None:
    annotation = PaperSpecModel.model_fields["domain"].annotation
    assert "general" not in get_args(annotation)
    payload = {
        "paper_title": "Report",
        "paper_type": "report",
        "domain": "general",
        "documents": [{"document_id": "DOC-001", "filename": "paper.pdf"}],
        "primary_document_id": None,
        "abstract": "Abstract",
        "equations": [],
        "parameter_table": [],
        "figure_locations": [],
        "pseudocode_blocks": [],
        "evidence": [_document_evidence_payload()],
    }

    with pytest.raises(ValidationError):
        PaperSpecModel.model_validate(payload)


def test_document_extracted_evidence_invariants() -> None:
    model = PaperEvidenceEntryModel.model_validate(_document_evidence_payload())
    assert model.source is EvidenceSource.DOCUMENT_EXTRACTED
    assert model.user_action is None
    assert model.parameter_correction_id is None
    assert model.correction_param_key is None


def test_user_supplied_evidence_invariants() -> None:
    model = PaperEvidenceEntryModel.model_validate(_user_evidence_payload())
    assert model.source is EvidenceSource.USER_SUPPLIED
    assert model.user_action is UserEvidenceAction.FILL_MISSING


def test_correct_extracted_evidence_invariants() -> None:
    model = PaperEvidenceEntryModel.model_validate(_correction_evidence_payload())

    assert model.source is EvidenceSource.USER_SUPPLIED
    assert model.user_action is UserEvidenceAction.CORRECT_EXTRACTED
    assert model.parameter_correction_id == "CORR-1"
    assert model.missing_param_prompt_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {
            "source": "document_extracted",
            "paper_section_id": "S1",
            "excerpt": "user supplied value",
            "missing_param_prompt_id": "MISS-1",
        },
        {
            "source": "document_extracted",
            "excerpt": "has excerpt",
            "missing_param_prompt_id": None,
        },
        {
            "source": "document_extracted",
            "paper_section_id": "S1",
            "excerpt": None,
            "missing_param_prompt_id": None,
        },
        {
            "source": "user_supplied",
            "paper_section_id": "S1",
            "excerpt": None,
            "missing_param_prompt_id": "MISS-1",
        },
        {
            "source": "user_supplied",
            "paper_section_id": None,
            "excerpt": "bad",
            "missing_param_prompt_id": "MISS-1",
        },
        {
            "source": "user_supplied",
            "paper_section_id": None,
            "excerpt": None,
            "missing_param_prompt_id": None,
            "user_action": "fill_missing",
        },
        {
            "source": "user_supplied",
            "document_id": None,
            "paper_section_id": None,
            "equation_id": None,
            "figure_id": None,
            "excerpt": None,
            "missing_param_prompt_id": "MISS-1",
            "user_action": "fill_missing",
            "parameter_correction_id": "CORR-1",
        },
        {
            "source": "user_supplied",
            "document_id": None,
            "paper_section_id": None,
            "equation_id": None,
            "figure_id": None,
            "excerpt": None,
            "missing_param_prompt_id": "MISS-1",
            "user_action": "correct_extracted",
            "parameter_correction_id": "CORR-1",
        },
        {
            "source": "document_extracted",
            "document_id": "DOC-001",
            "paper_section_id": "S1",
            "equation_id": None,
            "figure_id": None,
            "excerpt": "The document states the simulation target.",
            "missing_param_prompt_id": None,
            "user_action": "fill_missing",
        },
    ],
)
def test_evidence_invariant_violations_rejected(payload: dict[str, object]) -> None:
    payload.setdefault("equation_id", None)
    payload.setdefault("figure_id", None)
    with pytest.raises(ValidationError):
        PaperEvidenceEntryModel.model_validate(payload)


def test_anti_pattern_4_evidencepack_shape_rejected() -> None:
    with pytest.raises(ValidationError):
        PaperEvidenceEntryModel.model_validate(
            {"evidence_pack_kind": "parameter_context", "paper_section_id": "sec-2"}
        )


def test_missing_parameter_prompt_requires_document_reference() -> None:
    payload = {
        "prompt_id": "MISS-1",
        "parameter_name": "H",
        "paper_reference": _user_evidence_payload(),
        "suggested_unit": "s",
        "user_supplied_value": None,
        "user_supplied_unit": None,
        "source": "user_supplied",
    }

    with pytest.raises(ValidationError):
        MissingParameterPromptModel.model_validate(payload)


def _paper_spec_payload(
    *,
    documents: list[dict[str, object]] | None = None,
    primary_document_id: str | None = None,
    parameter_table: list[dict[str, object]] | None = None,
    parameter_conflicts: list[dict[str, object]] | None = None,
    equations: list[dict[str, object]] | None = None,
    figure_locations: list[dict[str, object]] | None = None,
    evidence: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "paper_title": "Report",
        "paper_type": "report",
        "domain": "motor_control",
        "documents": documents
        if documents is not None
        else [{"document_id": "DOC-001", "filename": "paper.pdf"}],
        "primary_document_id": primary_document_id,
        "abstract": "Abstract",
        "equations": equations if equations is not None else [_equation_payload()],
        "parameter_table": parameter_table
        if parameter_table is not None
        else [_document_parameter_payload()],
        "figure_locations": figure_locations
        if figure_locations is not None
        else [_figure_payload()],
        "pseudocode_blocks": [],
        "evidence": evidence if evidence is not None else [_document_evidence_payload()],
        "parameter_conflicts": parameter_conflicts if parameter_conflicts is not None else [],
    }


def _document_parameter_payload() -> dict[str, object]:
    return {
        "name": "Rated capacity",
        "symbol": "PN",
        "value": "200",
        "unit": "MW",
        "source": "document_extracted",
        "document_id": "DOC-001",
    }


def _user_parameter_payload() -> dict[str, object]:
    return {
        "name": "Inertia",
        "symbol": "H",
        "value": "3.5",
        "unit": "s",
        "source": "user_supplied",
        "document_id": None,
    }


def _equation_payload(document_id: str | None = "DOC-001") -> dict[str, object]:
    return {
        "equation_id": "EQ-01",
        "latex_or_text": "H = 3.5",
        "paper_section_id": "S1",
        "document_id": document_id,
    }


def _figure_payload(document_id: str | None = "DOC-001") -> dict[str, object]:
    return {
        "figure_id": "FIG-01",
        "caption": "Machine parameters",
        "paper_section_id": "S1",
        "document_id": document_id,
    }


def _without(payload: dict[str, object], field_name: str) -> dict[str, object]:
    result = dict(payload)
    result.pop(field_name)
    return result


def _plan_payload() -> dict[str, object]:
    return {
        "plan_id": "PLAN-1",
        "paper_spec_id": "SPEC-1",
        "library_choice": "SimPowerSystems",
        "block_recommendations": [],
        "parameter_mapping": [],
        "subsystem_breakdown": ["Place machine", "Apply fault", "Observe current"],
        "m_script_skeleton": None,
        "evidence": [_document_evidence_payload()],
    }


def _build_step_payload() -> dict[str, object]:
    return {
        "step_id": "STEP-001",
        "title": "Place the machine block",
        "intent": "Represent the main plant component from the source material.",
        "block_refs": [
            {
                "block_ref_id": "B1",
                "block_type": "Synchronous Machine",
                "library_path": None,
                "purpose": "Represent the generator component.",
                "paper_reference": _document_evidence_payload(),
            }
        ],
        "parameter_refs": [
            {
                "paper_param_name": "Rated capacity",
                "model_param_name": "Synchronous Machine nominal power",
            }
        ],
        "connection_hints": [
            {
                "from_block_ref": "B1",
                "from_port": "measurement",
                "to_block_ref": "B2",
                "to_port": None,
                "signal_meaning": "Machine measurement output",
            }
        ],
        "configuration_hints": [
            {
                "target": "solver",
                "setting_name": None,
                "instruction": "Use the project solver policy selected for this reproduction.",
                "evidence": [],
            }
        ],
        "depends_on": [],
        "evidence": [_document_evidence_payload()],
        "display_text": "Place the machine block and route its measurement output.",
    }


def _plan_domain(*, build_steps: bool) -> ModelGenerationPlan:
    evidence = _document_evidence()
    return ModelGenerationPlan(
        plan_id="PLAN-1",
        paper_spec_id="SPEC-1",
        library_choice="SimPowerSystems",
        block_recommendations=[],
        parameter_mapping=[],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=[evidence],
        build_steps=_build_steps() if build_steps else None,
    )


def _build_steps() -> list[ModelBuildStep]:
    evidence = _document_evidence()
    return [
        ModelBuildStep(
            step_id="STEP-001",
            title="Place the machine block",
            intent="Represent the main plant component from the source material.",
            block_refs=[
                StepBlockRef(
                    block_ref_id="B1",
                    block_type="Synchronous Machine",
                    library_path=None,
                    purpose="Represent the generator component.",
                    paper_reference=evidence,
                )
            ],
            parameter_refs=[
                ParameterMappingRef(
                    paper_param_name="Rated capacity",
                    model_param_name="Synchronous Machine nominal power",
                )
            ],
            connection_hints=[
                ConnectionHint(
                    from_block_ref="B1",
                    from_port="measurement",
                    to_block_ref="B2",
                    to_port=None,
                    signal_meaning="Machine measurement output",
                )
            ],
            configuration_hints=[
                ConfigurationHint(
                    target="solver",
                    setting_name=None,
                    instruction="Use the project solver policy selected for this reproduction.",
                    evidence=[],
                )
            ],
            depends_on=[],
            evidence=[evidence],
            display_text="Place the machine block and route its measurement output.",
        )
    ]


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The document states the simulation target.",
        missing_param_prompt_id=None,
    )
