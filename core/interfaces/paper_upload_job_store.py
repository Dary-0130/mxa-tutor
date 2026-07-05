"""Persistent store interface for paper upload jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from core.domain.paper_upload_job import (
    PaperUploadDocumentState,
    PaperUploadExecutionMode,
    PaperUploadJobRecord,
    PaperUploadJobState,
    PaperUploadStage,
)


class PaperUploadJobStore(ABC):
    """State-machine persistence for paper upload and rerun jobs."""

    @abstractmethod
    async def create_upload_job(
        self,
        *,
        job_id: str,
        paper_id: str,
        execution_mode: PaperUploadExecutionMode,
        document_ids: list[str],
        expires_at: datetime,
    ) -> PaperUploadJobRecord:
        """Create one upload job with pending document rows."""
        ...

    @abstractmethod
    async def get_upload_job(self, paper_id: str) -> PaperUploadJobRecord | None:
        """Return one job and its document statuses."""
        ...

    @abstractmethod
    async def update_upload_job_state(
        self,
        paper_id: str,
        *,
        job_state: PaperUploadJobState,
        stage: PaperUploadStage,
        failed_stage: PaperUploadStage | None = None,
        error_code: str | None = None,
        retryable: bool,
        finished_at: datetime | None = None,
    ) -> PaperUploadJobRecord:
        """Update the current job state and increment its version."""
        ...

    @abstractmethod
    async def update_upload_document_state(
        self,
        paper_id: str,
        document_id: str,
        *,
        status: PaperUploadDocumentState,
        error_code: str | None = None,
    ) -> None:
        """Update one document row."""
        ...

    @abstractmethod
    async def try_start_rerun_plan(self, paper_id: str) -> PaperUploadJobRecord | None:
        """CAS transition spec-ready or retryable plan-failed jobs to plan generation."""
        ...
