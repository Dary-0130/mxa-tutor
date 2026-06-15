"""TeachingUnit HTTP endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_teaching_unit_service
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingLevel, TeachingTarget, TeachingUnit, TeachingUnitRef
from features.overview._teaching_level_policy import TeachingUnitRequest
from features.overview._teaching_unit_service import TeachingUnitService

router = APIRouter(tags=["teaching-unit"])


class TeachingUnitRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: TeachingTarget
    target_id: str = Field(min_length=1)
    level: TeachingLevel | None = None


class TeachingUnitRefDTO(BaseModel):
    project_id: str
    teaching_unit_id: str

    @classmethod
    def from_domain(cls, ref: TeachingUnitRef) -> TeachingUnitRefDTO:
        return cls(project_id=ref.project_id, teaching_unit_id=ref.teaching_unit_id)


class SourceRefDTO(BaseModel):
    file_path: str
    line_range: tuple[int, int] | None = None
    block_id: str | None = None
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None

    @classmethod
    def from_domain(cls, ref: SourceRef) -> SourceRefDTO:
        return cls(
            file_path=ref.file_path,
            line_range=ref.line_range,
            block_id=ref.block_id,
            block_name=ref.block_name,
            parent_subsystem=ref.parent_subsystem,
            parameter_name=ref.parameter_name,
        )


class TeachingUnitResponse(BaseModel):
    id: str
    title: str
    target: TeachingTarget
    target_id: str
    level: TeachingLevel
    summary: str
    prerequisites: list[TeachingUnitRefDTO]
    explanation_steps: list[str]
    knowledge_points: list[str]
    source_refs: list[SourceRefDTO]
    confusion_points: list[str]

    @classmethod
    def from_domain(cls, unit: TeachingUnit) -> TeachingUnitResponse:
        return cls(
            id=unit.id,
            title=unit.title,
            target=unit.target,
            target_id=unit.target_id,
            level=unit.level,
            summary=unit.summary,
            prerequisites=[TeachingUnitRefDTO.from_domain(ref) for ref in unit.prerequisites],
            explanation_steps=unit.explanation_steps,
            knowledge_points=unit.knowledge_points,
            source_refs=[SourceRefDTO.from_domain(ref) for ref in unit.source_refs],
            confusion_points=unit.confusion_points,
        )


@router.post(
    "/projects/{project_id}/teaching-units:generate",
    response_model=TeachingUnitResponse,
)
async def generate_teaching_unit(
    project_id: str,
    request_body: TeachingUnitRequestBody,
    service: Annotated[TeachingUnitService, Depends(get_teaching_unit_service)],
) -> TeachingUnitResponse:
    """Generate or return a cached TeachingUnit for one project target."""
    unit = await service.get_or_generate(
        TeachingUnitRequest(
            project_id=project_id,
            target_type=request_body.target_type,
            target_id=request_body.target_id,
            level=request_body.level,
            trigger="api",
        )
    )
    return TeachingUnitResponse.from_domain(unit)
