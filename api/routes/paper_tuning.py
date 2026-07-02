"""Paper tuning suggestion endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.dependencies import get_paper_bundle_store, get_paper_tuning_service
from core.domain.exceptions import PaperNotFoundError
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_plan_integrity import validate_record_parameter_conflict_integrity
from features.paper.paper_schemas import TuningSuggestionModel
from features.paper.paper_tuning_service import TuningSuggestionService

router = APIRouter(tags=["paper"])


class TuningSuggestRequest(BaseModel):
    """POST /api/v1/papers/{paper_id}/tuning-suggest request body."""

    model_config = ConfigDict(extra="forbid")

    user_scenario: str = Field(min_length=1, max_length=500)

    @field_validator("user_scenario")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_scenario must contain non-whitespace characters")
        return value


class TuningSuggestResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/tuning-suggest response model."""

    paper_id: str
    suggestion: TuningSuggestionModel
    model_config = ConfigDict(extra="forbid")


@router.post(
    "/api/v1/papers/{paper_id}/tuning-suggest",
    response_model=TuningSuggestResponse,
)
async def suggest_tuning(
    paper_id: str,
    request: TuningSuggestRequest,
    store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    service: Annotated[TuningSuggestionService, Depends(get_paper_tuning_service)],
) -> TuningSuggestResponse:
    """Generate a non-persisted tuning suggestion for a ready paper plan."""
    record = await store.get_plan_record(paper_id)
    if record is None:
        raise PaperNotFoundError("paper_not_found") from None
    validate_record_parameter_conflict_integrity(record)
    corrections = await store.list_parameter_corrections(paper_id)
    suggestion = await service.suggest(
        record,
        request.user_scenario,
        corrections=corrections,
    )
    return TuningSuggestResponse(
        paper_id=paper_id,
        suggestion=TuningSuggestionModel.from_domain(suggestion),
    )
