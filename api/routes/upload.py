"""上传 + 状态查询 HTTP 端点。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from loguru import logger

from api.dependencies import get_project_store, get_upload_service
from api.schemas.upload import ProjectStatusResponse, UploadResponse
from core.interfaces.project_store import ProjectStore
from features.ingest.upload_service import UploadService, _sanitize_filename

router = APIRouter(tags=["upload"])


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResponse,
)
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> UploadResponse:
    """异步上传 + 解析入口(HTTP 202)。"""
    service.check_declared_size(file.size)
    zip_bytes = await file.read()
    service.check_actual_size(len(zip_bytes))

    name = _sanitize_filename(file.filename)
    project_id = await service.create_upload_record(name)
    logger.info(
        "Upload accepted: project_id={} size_bytes={}",
        project_id,
        len(zip_bytes),
    )
    background_tasks.add_task(service.process, project_id, zip_bytes, name)

    return UploadResponse(project_id=project_id, status="parsing")


@router.get(
    "/projects/{project_id}/status",
    response_model=ProjectStatusResponse,
)
async def get_status(
    project_id: str,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> ProjectStatusResponse:
    """轮询状态查询。"""
    view = await store.get_status_view(project_id)
    return ProjectStatusResponse(
        project_id=view.project_id,
        name=view.name,
        status=view.status,
        created_at=view.created_at,
        error_code=view.error_code,
    )
