"""SQLite 持久化 ProjectStore 实现(TASK-204)。"""

from datetime import datetime, timedelta
import json

import aiosqlite
from loguru import logger

from adapters.storage._connection import open_connection
from adapters.storage._project_json import _project_from_json, _project_to_json
from core.domain.exceptions import ProjectNotFoundError, StoreError
from core.domain.project import Project
from core.domain.project_status import ProjectStatusErrorCode
from core.interfaces.project_store import ProjectStatusView, ProjectStore


class SqliteProjectStore(ProjectStore):
    """SQLite 持久化 ProjectStore(7 方法接口 0 改动,TASK-204)。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """MCS 阶段连接按需打开 + 即关,本方法 no-op。"""

    async def create_pending(self, project_id: str, name: str) -> None:
        now = datetime.utcnow().isoformat()
        async with open_connection(self._db_path) as conn:
            try:
                await conn.execute(
                    "INSERT INTO project_status_record("
                    "project_id, name, status, created_at, updated_at"
                    ") VALUES (?,?,?,?,?)",
                    (project_id, name, "parsing", now, now),
                )
                await conn.commit()
            except aiosqlite.IntegrityError:
                await conn.rollback()
                raise ValueError("project_id already exists") from None
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteProjectStore.create_pending failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def mark_ready(self, project_id: str, project: Project) -> None:
        try:
            project_json = _project_to_json(project)
        except (TypeError, ValueError) as exc:
            logger.error(
                "SqliteProjectStore.mark_ready serialize failed: project_id={} exception={}",
                project_id,
                type(exc).__name__,
            )
            raise StoreError("project_serialize_failed") from None

        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "UPDATE project_status_record "
                    "SET status='ready', project=?, updated_at=? "
                    "WHERE project_id=? AND status='parsing'",
                    (project_json, datetime.utcnow().isoformat(), project_id),
                )
                if cur.rowcount == 0:
                    await conn.rollback()
                    raise ValueError("cannot mark_ready")
                await conn.commit()
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteProjectStore.mark_ready failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def mark_failed(self, project_id: str, error_code: ProjectStatusErrorCode) -> None:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "UPDATE project_status_record "
                    "SET status='failed', error_code=?, updated_at=? "
                    "WHERE project_id=? AND status='parsing'",
                    (error_code, datetime.utcnow().isoformat(), project_id),
                )
                if cur.rowcount == 0:
                    await conn.rollback()
                    raise ValueError("cannot mark_failed")
                await conn.commit()
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteProjectStore.mark_failed failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def get_status_view(self, project_id: str) -> ProjectStatusView:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT project_id, name, status, created_at, error_code "
                    "FROM project_status_record WHERE project_id=?",
                    (project_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteProjectStore.get_status_view failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

        if row is None:
            raise ProjectNotFoundError(f"project not found: {project_id}")
        return ProjectStatusView(
            project_id=row["project_id"],
            name=row["name"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            error_code=row["error_code"],
        )

    async def get_project(self, project_id: str) -> Project:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT project FROM project_status_record "
                    "WHERE project_id=? AND status='ready'",
                    (project_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteProjectStore.get_project failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

        if row is None:
            raise ProjectNotFoundError(f"project not ready or not found: {project_id}")
        try:
            return _project_from_json(row["project"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.error(
                "SqliteProjectStore.get_project deserialize failed: project_id={} exception={}",
                project_id,
                type(exc).__name__,
            )
            raise StoreError("project_deserialize_failed") from None

    async def list_expired(self, ttl_hours: int) -> list[str]:
        cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat()
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT project_id FROM project_status_record "
                    "WHERE created_at < ? ORDER BY created_at ASC",
                    (cutoff,),
                )
                rows = await cur.fetchall()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteProjectStore.list_expired failed: exception={}",
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return [row["project_id"] for row in rows]

    async def delete(self, project_id: str) -> None:
        async with open_connection(self._db_path) as conn:
            try:
                await conn.execute(
                    "DELETE FROM project_status_record WHERE project_id=?",
                    (project_id,),
                )
                await conn.commit()
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteProjectStore.delete failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
