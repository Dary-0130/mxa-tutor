"""进程内 dict + asyncio.Lock 测试 fake;生产使用 SqliteProjectStore。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from core.domain.exceptions import ProjectNotFoundError
from core.domain.project import Project
from core.domain.project_status import ProjectStatusErrorCode, ProjectStatusRecord
from core.interfaces.project_store import ProjectStatusView, ProjectStore


class InMemoryProjectStore(ProjectStore):
    """进程内 dict 实现(7 方法),仅用于测试 fake。"""

    def __init__(self) -> None:
        self._records: dict[str, ProjectStatusRecord] = {}
        self._lock = asyncio.Lock()

    async def create_pending(self, project_id: str, name: str) -> None:
        async with self._lock:
            if project_id in self._records:
                raise ValueError(f"project_id already exists: {project_id}")
            now = datetime.utcnow()
            self._records[project_id] = ProjectStatusRecord(
                project_id=project_id,
                name=name,
                status="parsing",
                created_at=now,
                updated_at=now,
            )

    async def mark_ready(self, project_id: str, project: Project) -> None:
        async with self._lock:
            record = self._records.get(project_id)
            if record is None:
                raise ValueError(f"project_id not found: {project_id}")
            if record.status != "parsing":
                raise ValueError(f"cannot mark_ready: status is {record.status}")
            record.status = "ready"
            record.project = project
            record.updated_at = datetime.utcnow()

    async def mark_failed(self, project_id: str, error_code: ProjectStatusErrorCode) -> None:
        async with self._lock:
            record = self._records.get(project_id)
            if record is None:
                raise ValueError(f"project_id not found: {project_id}")
            if record.status == "ready":
                raise ValueError("cannot mark_failed: already ready")
            record.status = "failed"
            record.error_code = error_code
            record.updated_at = datetime.utcnow()

    async def get_status_view(self, project_id: str) -> ProjectStatusView:
        record = self._records.get(project_id)
        if record is None:
            raise ProjectNotFoundError(f"project not found: {project_id}")
        return ProjectStatusView(
            project_id=record.project_id,
            name=record.name,
            status=record.status,
            created_at=record.created_at,
            error_code=record.error_code,
        )

    async def get_project(self, project_id: str) -> Project:
        record = self._records.get(project_id)
        if record is None or record.status != "ready" or record.project is None:
            raise ProjectNotFoundError(f"project not ready or not found: {project_id}")
        return record.project

    async def list_expired(self, ttl_hours: int) -> list[str]:
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        return [
            project_id for project_id, record in self._records.items() if record.created_at < cutoff
        ]

    async def delete(self, project_id: str) -> None:
        async with self._lock:
            self._records.pop(project_id, None)
