"""TTL 临时目录清理 worker。"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from loguru import logger

from core.domain.paper_reparse_source import PAPER_REPARSE_TTL_HOURS
from core.interfaces.paper_reparse_store import PaperReparseStore
from core.interfaces.paper_upload_job_store import PaperUploadJobStore
from core.interfaces.project_store import ProjectStore

PAPER_STAGING_DIRNAME = "paper_staging"
PAPER_STAGING_CLEANUP_STATES = {
    "ready",
    "plan_failed_retryable",
    "plan_failed_permanent",
    "failed_no_usable_spec",
    "abandoned_plan_retryable",
    "abandoned_reupload_required",
}


class CleanupWorker:
    """常驻 asyncio.Task,定时清理过期项目。"""

    def __init__(
        self,
        store: ProjectStore,
        upload_dir: Path,
        ttl_hours: int,
        interval_minutes: int = 60,
        paper_store: PaperReparseStore | None = None,
        paper_job_store: PaperUploadJobStore | None = None,
    ) -> None:
        self._store = store
        self._upload_dir = upload_dir
        self._ttl_hours = ttl_hours
        self._interval_seconds = interval_minutes * 60
        self._paper_store = paper_store
        self._paper_job_store = paper_job_store

    async def run_once(self) -> int:
        """单次扫描 + 清理,返回删除的 bundle 数量。"""
        try:
            expired = await self._store.list_expired(self._ttl_hours)
        except Exception as exc:
            logger.error("Cleanup list_expired failed: exception={}", type(exc).__name__)
            return 0

        deleted = 0
        for project_id in expired:
            if project_id == PAPER_STAGING_DIRNAME:
                continue
            project_dir = self._upload_dir / project_id
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
            try:
                await self._store.delete(project_id)
                deleted += 1
            except Exception as exc:
                logger.error(
                    "Cleanup store delete failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )

        if deleted > 0:
            logger.info("Cleanup deleted {} expired projects", deleted)
        return (
            deleted
            + await self._delete_expired_paper_bundles()
            + await self._delete_stale_paper_staging()
        )

    async def _delete_expired_paper_bundles(self) -> int:
        if self._paper_store is None:
            return 0
        try:
            deleted = await self._paper_store.delete_expired_paper_bundles(
                ttl_hours=PAPER_REPARSE_TTL_HOURS,
            )
        except Exception as exc:
            logger.error("Cleanup paper sweep failed: exception={}", type(exc).__name__)
            return 0
        if deleted > 0:
            logger.info("Cleanup deleted {} expired paper bundles", deleted)
        return deleted

    async def _delete_stale_paper_staging(self) -> int:
        if self._paper_job_store is None:
            return 0
        staging_root = self._upload_dir / PAPER_STAGING_DIRNAME
        if not staging_root.exists() or not staging_root.is_dir():
            return 0

        deleted = 0
        for staging_dir in staging_root.iterdir():
            if not staging_dir.is_dir():
                continue
            try:
                record = await self._paper_job_store.get_upload_job_by_job_id(staging_dir.name)
            except Exception as exc:
                logger.error(
                    "Cleanup paper staging lookup failed: exception={}", type(exc).__name__
                )
                continue
            if record is not None and record.job_state not in PAPER_STAGING_CLEANUP_STATES:
                continue
            try:
                shutil.rmtree(staging_dir, ignore_errors=False)
                deleted += 1
            except Exception as exc:
                logger.error(
                    "Cleanup paper staging delete failed: exception={}", type(exc).__name__
                )

        if deleted > 0:
            logger.info("Cleanup deleted {} paper staging directories", deleted)
        return deleted

    async def run_forever(self) -> None:
        """常驻循环,由 lifespan 负责 cancel + await。"""
        logger.info(
            "CleanupWorker started: ttl_hours={} interval_seconds={}",
            self._ttl_hours,
            self._interval_seconds,
        )
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.info("CleanupWorker cancelled")
            raise
