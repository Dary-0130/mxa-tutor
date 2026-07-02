"""Paper reparse endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_paper_reparse_service
from features.paper.paper_reparse_service import PaperReparseService
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)

router = APIRouter(tags=["paper"])


class PaperReparseResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/reparse response model."""

    paper_id: str
    spec: PaperSpecModel
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    remaining_missing_prompts: list[MissingParameterPromptModel]
    model_config = ConfigDict(extra="forbid")


@router.post("/api/v1/papers/{paper_id}/reparse", response_model=PaperReparseResponse)
async def reparse_paper(
    paper_id: str,
    service: Annotated[PaperReparseService, Depends(get_paper_reparse_service)],
) -> PaperReparseResponse:
    """Reparse a ready paper bundle from temporary stored text source."""

    record = await service.reparse(paper_id)
    missing_prompts = [
        MissingParameterPromptModel.from_domain(prompt) for prompt in record.missing_prompts
    ]
    return PaperReparseResponse(
        paper_id=paper_id,
        spec=PaperSpecModel.from_domain(record.spec),
        plan=ModelGenerationPlanModel.from_domain(record.plan),
        missing_prompts=missing_prompts,
        remaining_missing_prompts=missing_prompts,
    )
