"""Paper parameter correction endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_paper_parameter_correction_service,
    get_paper_reparse_lock_registry,
)
from core.domain.exceptions import PaperParameterCorrectionError, PaperReparseInProgressError
from features.paper.paper_parameter_correction_schemas import (
    ParameterCorrectionModel,
    ParameterCorrectionRequest,
    ParameterCorrectionsResponse,
)
from features.paper.paper_parameter_correction_service import ParameterCorrectionService
from features.paper.paper_reparse_service import PaperReparseLockRegistry
from features.paper.paper_schemas import ModelGenerationPlanModel

router = APIRouter(tags=["paper"])


class ParameterCorrectionResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/parameter-correction response."""

    paper_id: str
    updated_plan: ModelGenerationPlanModel
    correction: ParameterCorrectionModel
    model_config = ConfigDict(extra="forbid")


class ParameterCorrectionUndoResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/parameter-correction/{id}/undo response."""

    paper_id: str
    updated_plan: ModelGenerationPlanModel
    model_config = ConfigDict(extra="forbid")


@router.post(
    "/api/v1/papers/{paper_id}/parameter-correction",
    response_model=ParameterCorrectionResponse,
)
async def apply_parameter_correction(
    paper_id: str,
    request: ParameterCorrectionRequest,
    service: Annotated[
        ParameterCorrectionService,
        Depends(get_paper_parameter_correction_service),
    ],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
) -> ParameterCorrectionResponse:
    """Apply one user correction to an extracted parameter mapping."""
    try:
        async with await lock_registry.acquire(paper_id):
            result = await service.apply(
                paper_id,
                target=request.target,
                corrected_value=request.corrected_value,
                corrected_unit=request.corrected_unit,
                corrected_unit_supplied="corrected_unit" in request.model_fields_set,
            )
    except PaperReparseInProgressError:
        _log_lock_conflict()
        raise PaperParameterCorrectionError("correction_lock_conflict", 409) from None

    return ParameterCorrectionResponse(
        paper_id=paper_id,
        updated_plan=ModelGenerationPlanModel.from_domain(result.record.plan),
        correction=ParameterCorrectionModel.from_domain(
            result.correction,
            document_label=result.view.document_label,
            can_undo=result.view.can_undo,
            can_undo_reason=result.view.can_undo_reason,
        ),
    )


@router.post(
    "/api/v1/papers/{paper_id}/parameter-correction/{correction_id}/undo",
    response_model=ParameterCorrectionUndoResponse,
)
async def undo_parameter_correction(
    paper_id: str,
    correction_id: str,
    service: Annotated[
        ParameterCorrectionService,
        Depends(get_paper_parameter_correction_service),
    ],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
) -> ParameterCorrectionUndoResponse:
    """Undo one active user correction."""
    try:
        async with await lock_registry.acquire(paper_id):
            record = await service.undo(paper_id, correction_id)
    except PaperReparseInProgressError:
        _log_lock_conflict()
        raise PaperParameterCorrectionError("correction_lock_conflict", 409) from None

    return ParameterCorrectionUndoResponse(
        paper_id=paper_id,
        updated_plan=ModelGenerationPlanModel.from_domain(record.plan),
    )


@router.get(
    "/api/v1/papers/{paper_id}/parameter-corrections",
    response_model=ParameterCorrectionsResponse,
)
async def list_parameter_corrections(
    paper_id: str,
    service: Annotated[
        ParameterCorrectionService,
        Depends(get_paper_parameter_correction_service),
    ],
) -> ParameterCorrectionsResponse:
    """Return active correction overlays for one paper."""
    result = await service.list_corrections(paper_id)
    return ParameterCorrectionsResponse(
        paper_id=result.paper_id,
        corrections=[
            ParameterCorrectionModel.from_domain(
                view.correction,
                document_label=view.document_label,
                can_undo=view.can_undo,
                can_undo_reason=view.can_undo_reason,
            )
            for view in result.views
        ],
    )


def _log_lock_conflict() -> None:
    logger.info(
        "paper_parameter_correction event_code={} target_kind={} "
        "correction_created_count={} undo_count={}",
        "paper_parameter_correction",
        "lock_conflict",
        0,
        0,
    )
