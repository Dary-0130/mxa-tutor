"""Paper step regeneration endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_paper_step_regeneration_service
from api.routes.paper_user_supply import UpdatedPlanResponse
from core.domain.exceptions import PaperReparseInProgressError
from features.paper.paper_schemas import ModelGenerationPlanModel
from features.paper.paper_step_regeneration_service import (
    PaperStepRegenerationError,
    PaperStepRegenerationService,
)

router = APIRouter(tags=["paper"])


class RegenerateStepsRequest(BaseModel):
    """POST /api/v1/papers/{paper_id}/regenerate-steps request."""

    model_config = ConfigDict(extra="forbid")


_ERROR_MESSAGES = {
    "regenerate_lock_conflict": "这份结果正在更新,请稍后重试",
    "regenerate_nothing_to_do": "当前步骤已经是完整的",
    "regenerate_store_failed": "步骤保存失败,旧结果已保留",
}


@router.post(
    "/api/v1/papers/{paper_id}/regenerate-steps",
    response_model=UpdatedPlanResponse,
)
async def regenerate_paper_steps(
    paper_id: str,
    request: Annotated[
        RegenerateStepsRequest,
        Body(default_factory=RegenerateStepsRequest),
    ],
    service: Annotated[
        PaperStepRegenerationService,
        Depends(get_paper_step_regeneration_service),
    ],
) -> UpdatedPlanResponse | JSONResponse:
    """Regenerate suppressed paper build steps from the current plan."""

    _ = request
    try:
        updated_plan = await service.regenerate_steps(paper_id)
    except PaperReparseInProgressError:
        return _error_response("regenerate_lock_conflict", 409)
    except PaperStepRegenerationError as exc:
        return _error_response(exc.error_code, exc.status_code)

    return UpdatedPlanResponse(
        paper_id=paper_id,
        updated_plan=ModelGenerationPlanModel.from_domain(updated_plan),
    )


def _error_response(error_code: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_code,
            "message": _ERROR_MESSAGES.get(error_code, "步骤保存失败,旧结果已保留"),
        },
    )
