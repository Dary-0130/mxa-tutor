"""Pydantic schemas for PaperAsk request and response contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from core.domain.paper_ask import (
    EquationTarget,
    MissingPromptParameterTarget,
    PaperAskCitation,
    PaperAskFallbackReason,
    PaperAskRequest,
    PaperAskResponse,
    PaperResultSection,
    PlanMappingParameterTarget,
    SectionTarget,
)
from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_tuning import ConfidenceValue


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    @classmethod
    def from_domain(cls, entry: object) -> Self:
        return cls.model_validate(entry)


class SectionTargetModel(_StrictBaseModel):
    kind: Literal["section"]
    result_section: PaperResultSection

    def to_domain(self) -> SectionTarget:
        return SectionTarget(kind=self.kind, result_section=self.result_section)


class EquationTargetModel(_StrictBaseModel):
    kind: Literal["equation"]
    equation_id: str = Field(min_length=1)

    def to_domain(self) -> EquationTarget:
        return EquationTarget(kind=self.kind, equation_id=self.equation_id)


class PlanMappingParameterTargetModel(_StrictBaseModel):
    kind: Literal["parameter"]
    origin: Literal["plan_mapping"]
    row_index: int = Field(ge=0)
    paper_param_name: str = Field(min_length=1)
    model_param_name: str = Field(min_length=1)

    def to_domain(self) -> PlanMappingParameterTarget:
        return PlanMappingParameterTarget(
            kind=self.kind,
            origin=self.origin,
            row_index=self.row_index,
            paper_param_name=self.paper_param_name,
            model_param_name=self.model_param_name,
        )


class MissingPromptParameterTargetModel(_StrictBaseModel):
    kind: Literal["parameter"]
    origin: Literal["missing_prompt"]
    prompt_id: str = Field(min_length=1)
    parameter_name: str = Field(min_length=1)

    def to_domain(self) -> MissingPromptParameterTarget:
        return MissingPromptParameterTarget(
            kind=self.kind,
            origin=self.origin,
            prompt_id=self.prompt_id,
            parameter_name=self.parameter_name,
        )


ParameterTargetModel = Annotated[
    PlanMappingParameterTargetModel | MissingPromptParameterTargetModel,
    Field(discriminator="origin"),
]
PaperCitationTargetModel = Annotated[
    SectionTargetModel | EquationTargetModel | ParameterTargetModel,
    Field(union_mode="left_to_right"),
]


class PaperAskRequestModel(_StrictBaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, min_length=1)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must contain non-whitespace characters")
        return value

    def to_domain(self) -> PaperAskRequest:
        return PaperAskRequest(question=self.question, session_id=self.session_id)


class PaperAskCitationModel(_StrictBaseModel):
    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    label: str = Field(min_length=1, max_length=200)
    excerpt: str | None = Field(default=None, min_length=1, max_length=300)
    source_kind: EvidenceSource
    target: PaperCitationTargetModel

    @model_validator(mode="after")
    def validate_source_excerpt_invariant(self) -> Self:
        if self.source_kind is EvidenceSource.DOCUMENT_EXTRACTED:
            if self.excerpt is None:
                raise ValueError("document_extracted citation requires excerpt")
            return self
        if self.excerpt is not None:
            raise ValueError("user_supplied citation cannot have excerpt")
        return self

    def to_domain(self) -> PaperAskCitation:
        return PaperAskCitation(
            source_id=self.source_id,
            label=self.label,
            excerpt=self.excerpt,
            source_kind=self.source_kind,
            target=self.target.to_domain(),
        )


FollowUpSuggestion = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class PaperAskResponseModel(_StrictBaseModel):
    session_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=3000)
    confidence: ConfidenceValue
    citations: list[PaperAskCitationModel]
    follow_up_suggestions: list[FollowUpSuggestion] = Field(max_length=3)
    is_fallback: bool = False
    fallback_reason: PaperAskFallbackReason | None = None

    @model_validator(mode="after")
    def validate_response_invariant(self) -> Self:
        if self.is_fallback:
            if self.confidence != "low":
                raise ValueError("fallback response confidence must be low")
            if self.citations:
                raise ValueError("fallback response cannot include citations")
            if self.fallback_reason is None:
                raise ValueError("fallback response requires fallback_reason")
            return self
        if not self.citations:
            raise ValueError("non-fallback response requires at least one citation")
        if self.fallback_reason is not None:
            raise ValueError("non-fallback response cannot include fallback_reason")
        return self

    def to_domain(self) -> PaperAskResponse:
        return PaperAskResponse(
            session_id=self.session_id,
            message_id=self.message_id,
            answer=self.answer,
            confidence=self.confidence,
            citations=[entry.to_domain() for entry in self.citations],
            follow_up_suggestions=list(self.follow_up_suggestions),
            is_fallback=self.is_fallback,
            fallback_reason=self.fallback_reason,
        )


PaperAskRequestSchema = PaperAskRequestModel
PaperAskResponseSchema = PaperAskResponseModel
