"""项目状态存储抽象接口。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from core.domain.project import Project
from core.domain.project_status import ProjectStatus, ProjectStatusErrorCode


@dataclass
class ProjectStatusView:
    """GET /status 端点专用视图。"""

    project_id: str
    name: str
    status: ProjectStatus
    created_at: datetime
    error_code: ProjectStatusErrorCode | None


class ProjectStore(ABC):
    """工程状态存储(7 方法)。"""

    @abstractmethod
    async def create_pending(self, project_id: str, name: str) -> None:
        """创建 status=parsing 记录。已存在则抛 ValueError。"""
        ...

    @abstractmethod
    async def mark_ready(self, project_id: str, project: Project) -> None:
        """转 status=ready,落 Project。"""
        ...

    @abstractmethod
    async def mark_failed(self, project_id: str, error_code: ProjectStatusErrorCode) -> None:
        """转 status=failed,记 error_code。"""
        ...

    @abstractmethod
    async def get_status_view(self, project_id: str) -> ProjectStatusView:
        """GET /status 端点用。未存在抛 ProjectNotFoundError。"""
        ...

    @abstractmethod
    async def get_project(self, project_id: str) -> Project:
        """取已 ready 的 Project。未 ready / 未存在抛 ProjectNotFoundError。"""
        ...

    @abstractmethod
    async def list_expired(self, ttl_hours: int) -> list[str]:
        """返回 created_at 早于 ttl_hours 的 project_id 列表。"""
        ...

    @abstractmethod
    async def delete(self, project_id: str) -> None:
        """删除记录。未存在静默 no-op。"""
        ...
