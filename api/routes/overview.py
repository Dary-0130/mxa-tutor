"""Project overview HTTP endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_overview_service
from features.overview.overview_schemas import ProjectOverview
from features.overview.overview_service import ProjectOverviewService

router = APIRouter(tags=["overview"])


@router.get("/projects/{project_id}/overview", response_model=ProjectOverview)
async def get_project_overview(
    project_id: str,
    service: Annotated[ProjectOverviewService, Depends(get_overview_service)],
) -> ProjectOverview:
    """Return generated project overview."""
    return await service.get_or_generate(project_id)
