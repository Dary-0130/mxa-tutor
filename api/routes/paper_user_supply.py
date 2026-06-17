"""Paper plan user-supplied parameter endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_paper_user_supply_service
from features.paper.paper_schemas import ModelGenerationPlanModel
from features.paper.paper_user_input_schemas import UserSuppliedResponseBatch
from features.paper.paper_user_supply_service import UserSupplyService

router = APIRouter(tags=["paper"])


class UpdatedPlanResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/user-supply response model."""

    paper_id: str
    updated_plan: ModelGenerationPlanModel
    model_config = ConfigDict(extra="forbid")


@router.post(
    "/api/v1/papers/{paper_id}/user-supply",
    response_model=UpdatedPlanResponse,
)
async def submit_user_supply(
    paper_id: str,
    batch: UserSuppliedResponseBatch,
    service: Annotated[UserSupplyService, Depends(get_paper_user_supply_service)],
) -> UpdatedPlanResponse:
    """Merge user-supplied missing parameters from the server-side paper plan cache."""
    updated_plan = await service.merge(paper_id, batch.user_supplied_responses)
    return UpdatedPlanResponse(
        paper_id=paper_id,
        updated_plan=ModelGenerationPlanModel.from_domain(updated_plan),
    )
