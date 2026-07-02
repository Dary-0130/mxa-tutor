"""Pydantic schemas for paper parameter correction overlays."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_parameter_correction import (
    PaperParameterCorrection,
    PlanCorrectionTarget,
)


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class CorrectionTargetRequest(_StrictBaseModel):
    paper_param_name: str = Field(min_length=1)
    model_param_name: str = Field(min_length=1)
    plan_mapping_index: int = Field(ge=0)
    expected_value: str = Field(min_length=1)
    expected_unit: str | None


class ParameterCorrectionRequest(_StrictBaseModel):
    target: CorrectionTargetRequest
    corrected_value: str = Field(min_length=1)
    corrected_unit: str | None = None

    @field_validator("corrected_value")
    @classmethod
    def corrected_value_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("corrected_value must contain non-whitespace characters")
        return value


class PlanCorrectionTargetModel(_StrictBaseModel):
    paper_param_name: str
    model_param_name: str
    plan_mapping_index: int

    @classmethod
    def from_domain(cls, target: PlanCorrectionTarget) -> Self:
        return cls.model_validate(target)


class ParameterCorrectionOriginalModel(_StrictBaseModel):
    value: str
    unit: str | None
    source: Literal["document_extracted"]
    document_id: str | None
    document_label: str | None


class ParameterCorrectionCorrectedModel(_StrictBaseModel):
    value: str
    unit: str | None


class ParameterCorrectionModel(_StrictBaseModel):
    correction_id: str
    param_key: str
    target: PlanCorrectionTargetModel
    original: ParameterCorrectionOriginalModel
    corrected: ParameterCorrectionCorrectedModel
    created_at: str
    updated_at: str
    can_undo: bool
    can_undo_reason: Literal["active", "target_stale", "missing_mapping"]

    @classmethod
    def from_domain(
        cls,
        correction: PaperParameterCorrection,
        *,
        document_label: str | None,
        can_undo: bool,
        can_undo_reason: Literal["active", "target_stale", "missing_mapping"],
    ) -> Self:
        return cls(
            correction_id=correction.correction_id,
            param_key=correction.param_key,
            target=PlanCorrectionTargetModel.from_domain(correction.plan_target),
            original=ParameterCorrectionOriginalModel(
                value=correction.original_value,
                unit=correction.original_unit,
                source=EvidenceSource.DOCUMENT_EXTRACTED.value,
                document_id=correction.original_document_id,
                document_label=document_label,
            ),
            corrected=ParameterCorrectionCorrectedModel(
                value=correction.corrected_value,
                unit=correction.corrected_unit,
            ),
            created_at=correction.created_at,
            updated_at=correction.updated_at,
            can_undo=can_undo,
            can_undo_reason=can_undo_reason,
        )


class ParameterCorrectionsResponse(_StrictBaseModel):
    paper_id: str
    corrections: list[ParameterCorrectionModel]


PaperParameterCorrectionsSchema = ParameterCorrectionsResponse
