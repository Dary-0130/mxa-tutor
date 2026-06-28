from dataclasses import fields
from typing import Any, get_args

import pytest
from pydantic import BaseModel, ValidationError

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
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
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from core.domain.paper_tuning import ParameterDirection, TuningSuggestion
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    ConfigurationHintModel,
    ConnectionHintModel,
    EquationEntryModel,
    FigureRefModel,
    MissingParameterPromptModel,
    ModelBuildStepModel,
    ModelGenerationPlanModel,
    PaperEvidenceEntryModel,
    PaperSpecModel,
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
)

NESTED_MODELS = (
    EquationEntryModel,
    ParameterEntryModel,
    FigureRefModel,
    BlockRecommendationModel,
    ParameterMappingModel,
    StepBlockRefModel,
    ParameterMappingRefModel,
    ConnectionHintModel,
    ConfigurationHintModel,
    ModelBuildStepModel,
    ParameterDirectionModel,
)


def _document_evidence_payload() -> dict[str, object]:
    return {
        "source": "document_extracted",
        "paper_section_id": "S1",
        "equation_id": None,
        "figure_id": None,
        "excerpt": "The document states the simulation target.",
        "missing_param_prompt_id": None,
    }


def _user_evidence_payload() -> dict[str, object]:
    return {
        "source": "user_supplied",
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": "MISS-1",
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
    ]


def test_nested_model_count_and_names_are_frozen() -> None:
    assert [model.__name__ for model in NESTED_MODELS] == [
        "EquationEntryModel",
        "ParameterEntryModel",
        "FigureRefModel",
        "BlockRecommendationModel",
        "ParameterMappingModel",
        "StepBlockRefModel",
        "ParameterMappingRefModel",
        "ConnectionHintModel",
        "ConfigurationHintModel",
        "ModelBuildStepModel",
        "ParameterDirectionModel",
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


def test_nested_field_order_matches_domain() -> None:
    assert tuple(EquationEntryModel.model_fields) == tuple(
        fields(EquationEntry)[i].name for i in range(3)
    )
    assert tuple(ParameterEntryModel.model_fields) == tuple(
        field.name for field in fields(ParameterEntry)
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


def test_model_generation_plan_micro_patch_constraints_are_frozen() -> None:
    assert _constraint_value(ModelGenerationPlanModel, "library_choice", "min_length") == 1
    assert _constraint_value(ModelGenerationPlanModel, "library_choice", "max_length") == 300
    assert ParameterMappingModel.model_fields["unit"].annotation == str | None
    assert fields(ParameterMapping)[3].type == str | None
    assert ModelGenerationPlanModel.model_fields["build_steps"].annotation == (
        list[ModelBuildStepModel] | None
    )
    assert fields(ModelGenerationPlan)[8].type == list[ModelBuildStep] | None


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


def test_domain_literal_rejects_general() -> None:
    annotation = PaperSpecModel.model_fields["domain"].annotation
    assert "general" not in get_args(annotation)
    payload = {
        "paper_title": "Report",
        "paper_type": "report",
        "domain": "general",
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


def test_user_supplied_evidence_invariants() -> None:
    model = PaperEvidenceEntryModel.model_validate(_user_evidence_payload())
    assert model.source is EvidenceSource.USER_SUPPLIED


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
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The document states the simulation target.",
        missing_param_prompt_id=None,
    )
