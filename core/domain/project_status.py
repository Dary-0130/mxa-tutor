"""上传流程的运行态状态记录。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.domain.project import Project

ProjectStatus = Literal["parsing", "ready", "failed"]

ProjectStatusErrorCode = Literal[
    "zip_bomb",
    "zip_slip",
    "file_type_not_allowed",
    "project_too_large",
    "upload_error",
    "project_error",
    "parse_error",
    "internal_error",
]


@dataclass
class ProjectStatusRecord:
    """单次上传请求在 ProjectStore 中的完整记录。"""

    project_id: str
    name: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    project: Project | None = None
    error_code: ProjectStatusErrorCode | None = None
