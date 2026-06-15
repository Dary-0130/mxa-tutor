"""Project overview HTTP endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_overview_service
from features.overview.overview_schemas import ProjectOverviewModel
from features.overview.overview_service import ProjectOverviewService

router = APIRouter(tags=["overview"])


@router.get("/projects/{project_id}/overview", response_model=ProjectOverviewModel)
async def get_project_overview(
    project_id: str,
    service: Annotated[ProjectOverviewService, Depends(get_overview_service)],
) -> ProjectOverviewModel:
    """Return generated project overview."""
    overview = await service.get_or_generate(project_id)
    return ProjectOverviewModel.from_domain(overview)
