"""Paper plan user-supplied parameter endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_paper_reparse_lock_registry, get_paper_user_supply_service
from core.domain.exceptions import PaperReparseInProgressError, PaperUserSupplyInProgressError
from features.paper.paper_reparse_service import PaperReparseLockRegistry
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
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
) -> UpdatedPlanResponse:
    """Merge user-supplied missing parameters from the server-side paper plan cache."""
    try:
        async with await lock_registry.acquire(paper_id):
            updated_plan = await service.merge(paper_id, batch.user_supplied_responses)
    except PaperReparseInProgressError:
        raise PaperUserSupplyInProgressError("paper_user_supply_in_progress") from None
    return UpdatedPlanResponse(
        paper_id=paper_id,
        updated_plan=ModelGenerationPlanModel.from_domain(updated_plan),
    )
