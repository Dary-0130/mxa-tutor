"""上传端点响应 schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.domain.project_status import ProjectStatusErrorCode


class UploadResponse(BaseModel):
    """POST /upload 响应体。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    status: Literal["parsing"]


class ProjectStatusResponse(BaseModel):
    """GET /projects/{project_id}/status 响应体(5 字段)。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    status: Literal["parsing", "ready", "failed"]
    created_at: datetime
    error_code: ProjectStatusErrorCode | None = None
