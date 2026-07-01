"""Paper bundle query endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_paper_bundle_store
from core.domain.exceptions import PaperNotFoundError
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_plan_helpers import resolved_prompt_ids
from features.paper.paper_plan_integrity import validate_record_parameter_conflict_integrity
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)

router = APIRouter(tags=["paper"])


class PaperSpecResponse(BaseModel):
    """GET /api/v1/papers/{paper_id}/spec response model."""

    paper_id: str
    spec: PaperSpecModel
    model_config = ConfigDict(extra="forbid")


class PaperPlanResponse(BaseModel):
    """GET /api/v1/papers/{paper_id}/plan response model."""

    paper_id: str
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    remaining_missing_prompts: list[MissingParameterPromptModel]
    model_config = ConfigDict(extra="forbid")


@router.get("/api/v1/papers/{paper_id}/spec", response_model=PaperSpecResponse)
async def get_paper_spec(
    paper_id: str,
    store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
) -> PaperSpecResponse:
    """Return the persisted PaperSpec for a paper bundle."""
    spec = await store.get_spec(paper_id)
    if spec is None:
        raise PaperNotFoundError("paper_not_found") from None
    return PaperSpecResponse(paper_id=paper_id, spec=PaperSpecModel.from_domain(spec))


@router.get("/api/v1/papers/{paper_id}/plan", response_model=PaperPlanResponse)
async def get_paper_plan(
    paper_id: str,
    store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
) -> PaperPlanResponse:
    """Return the persisted plan and remaining missing prompts for a paper bundle."""
    record = await store.get_plan_record(paper_id)
    if record is None:
        raise PaperNotFoundError("paper_not_found") from None
    validate_record_parameter_conflict_integrity(record)

    resolved_ids = resolved_prompt_ids(record)
    remaining_prompts = [
        prompt for prompt in record.missing_prompts if prompt.prompt_id not in resolved_ids
    ]
    return PaperPlanResponse(
        paper_id=paper_id,
        plan=ModelGenerationPlanModel.from_domain(record.plan),
        missing_prompts=[
            MissingParameterPromptModel.from_domain(prompt) for prompt in record.missing_prompts
        ],
        remaining_missing_prompts=[
            MissingParameterPromptModel.from_domain(prompt) for prompt in remaining_prompts
        ],
    )
