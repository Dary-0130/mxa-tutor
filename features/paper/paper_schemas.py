"""Pydantic schemas for paper-to-model contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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
    PaperDomain,
    PaperSpec,
    PaperType,
    ParameterEntry,
)
from core.domain.paper_tuning import (
    ConfidenceValue,
    ParameterDirection,
    ParameterDirectionValue,
    TuningSuggestion,
)


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    @classmethod
    def from_domain(cls, entry: object) -> Self:
        return cls.model_validate(entry)


class PaperEvidenceEntryModel(_StrictBaseModel):
    source: EvidenceSource
    paper_section_id: str | None = Field(default=None, min_length=1)
    equation_id: str | None = Field(default=None, min_length=1)
    figure_id: str | None = Field(default=None, min_length=1)
    excerpt: str | None = Field(default=None, min_length=1, max_length=300)
    missing_param_prompt_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_source_invariants(self) -> Self:
        locators = (self.paper_section_id, self.equation_id, self.figure_id)
        if self.source is EvidenceSource.DOCUMENT_EXTRACTED:
            if not any(locator is not None for locator in locators):
                raise ValueError("document_extracted evidence requires at least one locator")
            if self.excerpt is None:
                raise ValueError("document_extracted evidence requires excerpt")
            if self.missing_param_prompt_id is not None:
                raise ValueError("document_extracted evidence cannot link missing prompt")
            return self

        if any(locator is not None for locator in locators):
            raise ValueError("user_supplied evidence cannot have paper locators")
        if self.excerpt is not None:
            raise ValueError("user_supplied evidence cannot have excerpt")
        if self.missing_param_prompt_id is None:
            raise ValueError("user_supplied evidence requires missing prompt id")
        return self

    def to_domain(self) -> PaperEvidenceEntry:
        return PaperEvidenceEntry(
            source=self.source,
            paper_section_id=self.paper_section_id,
            equation_id=self.equation_id,
            figure_id=self.figure_id,
            excerpt=self.excerpt,
            missing_param_prompt_id=self.missing_param_prompt_id,
        )


class EquationEntryModel(_StrictBaseModel):
    equation_id: str = Field(min_length=1)
    latex_or_text: str = Field(min_length=1)
    paper_section_id: str = Field(min_length=1)

    def to_domain(self) -> EquationEntry:
        return EquationEntry(
            equation_id=self.equation_id,
            latex_or_text=self.latex_or_text,
            paper_section_id=self.paper_section_id,
        )


class ParameterEntryModel(_StrictBaseModel):
    name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: EvidenceSource

    def to_domain(self) -> ParameterEntry:
        return ParameterEntry(
            name=self.name,
            symbol=self.symbol,
            value=self.value,
            unit=self.unit,
            source=self.source,
        )


class FigureRefModel(_StrictBaseModel):
    figure_id: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    paper_section_id: str = Field(min_length=1)

    def to_domain(self) -> FigureRef:
        return FigureRef(
            figure_id=self.figure_id,
            caption=self.caption,
            paper_section_id=self.paper_section_id,
        )


class BlockRecommendationModel(_StrictBaseModel):
    block_type: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel

    def to_domain(self) -> BlockRecommendation:
        return BlockRecommendation(
            block_type=self.block_type,
            purpose=self.purpose,
            paper_reference=self.paper_reference.to_domain(),
        )


class ParameterMappingModel(_StrictBaseModel):
    paper_param_name: str = Field(min_length=1)
    model_param_name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str | None = Field(default=None, min_length=1)
    source: EvidenceSource

    def to_domain(self) -> ParameterMapping:
        return ParameterMapping(
            paper_param_name=self.paper_param_name,
            model_param_name=self.model_param_name,
            value=self.value,
            unit=self.unit,
            source=self.source,
        )


class ParameterDirectionModel(_StrictBaseModel):
    param_name: str = Field(min_length=1)
    direction: ParameterDirectionValue
    physical_meaning: str = Field(min_length=1)

    def to_domain(self) -> ParameterDirection:
        return ParameterDirection(
            param_name=self.param_name,
            direction=self.direction,
            physical_meaning=self.physical_meaning,
        )


class PaperSpecModel(_StrictBaseModel):
    paper_title: str = Field(min_length=1, max_length=200)
    paper_type: PaperType
    domain: PaperDomain
    abstract: str = Field(min_length=1, max_length=1000)
    equations: list[EquationEntryModel] = Field(default_factory=list)
    parameter_table: list[ParameterEntryModel] = Field(default_factory=list)
    figure_locations: list[FigureRefModel] = Field(default_factory=list)
    pseudocode_blocks: list[str] = Field(default_factory=list)
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)

    def to_domain(self) -> PaperSpec:
        return PaperSpec(
            paper_title=self.paper_title,
            paper_type=self.paper_type,
            domain=self.domain,
            abstract=self.abstract,
            equations=[entry.to_domain() for entry in self.equations],
            parameter_table=[entry.to_domain() for entry in self.parameter_table],
            figure_locations=[entry.to_domain() for entry in self.figure_locations],
            pseudocode_blocks=self.pseudocode_blocks,
            evidence=[entry.to_domain() for entry in self.evidence],
        )


class ModelGenerationPlanModel(_StrictBaseModel):
    plan_id: str = Field(min_length=1)
    paper_spec_id: str = Field(min_length=1)
    library_choice: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    block_recommendations: list[BlockRecommendationModel] = Field(default_factory=list)
    parameter_mapping: list[ParameterMappingModel] = Field(default_factory=list)
    subsystem_breakdown: list[str] = Field(min_length=3, max_length=10)
    m_script_skeleton: str | None = None
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)

    def to_domain(self) -> ModelGenerationPlan:
        return ModelGenerationPlan(
            plan_id=self.plan_id,
            paper_spec_id=self.paper_spec_id,
            library_choice=self.library_choice,
            block_recommendations=[entry.to_domain() for entry in self.block_recommendations],
            parameter_mapping=[entry.to_domain() for entry in self.parameter_mapping],
            subsystem_breakdown=self.subsystem_breakdown,
            m_script_skeleton=self.m_script_skeleton,
            evidence=[entry.to_domain() for entry in self.evidence],
        )


class TuningSuggestionModel(_StrictBaseModel):
    suggestion_id: str = Field(min_length=1)
    user_scenario: str = Field(min_length=1, max_length=500)
    parameter_directions: list[ParameterDirectionModel] = Field(min_length=1)
    expected_effect: str = Field(min_length=1, max_length=500)
    confidence: ConfidenceValue
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)
    disclaimer: str = Field(min_length=1)

    def to_domain(self) -> TuningSuggestion:
        return TuningSuggestion(
            suggestion_id=self.suggestion_id,
            user_scenario=self.user_scenario,
            parameter_directions=[entry.to_domain() for entry in self.parameter_directions],
            expected_effect=self.expected_effect,
            confidence=self.confidence,
            evidence=[entry.to_domain() for entry in self.evidence],
            disclaimer=self.disclaimer,
        )


class MissingParameterPromptModel(_StrictBaseModel):
    prompt_id: str = Field(min_length=1)
    parameter_name: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel
    suggested_unit: str | None = Field(default=None, min_length=1)
    user_supplied_value: str | None = Field(default=None, min_length=1)
    user_supplied_unit: str | None = Field(default=None, min_length=1)
    source: Literal["user_supplied"] = "user_supplied"

    @model_validator(mode="after")
    def validate_paper_reference_source(self) -> Self:
        if self.paper_reference.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            raise ValueError("paper_reference must be document_extracted")
        return self

    def to_domain(self) -> MissingParameterPrompt:
        return MissingParameterPrompt(
            prompt_id=self.prompt_id,
            parameter_name=self.parameter_name,
            paper_reference=self.paper_reference.to_domain(),
            suggested_unit=self.suggested_unit,
            user_supplied_value=self.user_supplied_value,
            user_supplied_unit=self.user_supplied_unit,
            source=EvidenceSource(self.source),
        )


PaperEvidenceEntrySchema = PaperEvidenceEntryModel
PaperSpecSchema = PaperSpecModel
ModelGenerationPlanSchema = ModelGenerationPlanModel
TuningSuggestionSchema = TuningSuggestionModel
MissingParameterPromptSchema = MissingParameterPromptModel
