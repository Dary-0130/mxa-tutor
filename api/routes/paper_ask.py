"""Paper ask endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_paper_ask_service, get_paper_bundle_store
from core.domain.exceptions import PaperNotFoundError
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_ask_schemas import PaperAskRequestSchema, PaperAskResponseSchema
from features.paper.paper_ask_service import PaperAskService

router = APIRouter(tags=["paper"])


@router.post(
    "/api/v1/papers/{paper_id}/ask",
    response_model=PaperAskResponseSchema,
)
async def ask_paper(
    paper_id: str,
    request: PaperAskRequestSchema,
    store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    service: Annotated[PaperAskService, Depends(get_paper_ask_service)],
) -> PaperAskResponseSchema:
    """Answer one stateless paper follow-up question."""
    record = await store.get_plan_record(paper_id)
    if record is None:
        raise PaperNotFoundError("paper_not_found") from None
    response = await service.ask(record, request.to_domain())
    return PaperAskResponseSchema.from_domain(response)
