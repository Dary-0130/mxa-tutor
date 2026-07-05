"""Pydantic schemas for paper upload status and rerun-plan contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.domain.paper_upload_job import (
    PaperUploadDocumentState,
    PaperUploadExecutionMode,
    PaperUploadJobRecord,
    PaperUploadJobState,
    PaperUploadNextAction,
    PaperUploadStage,
    next_action_for_job,
)
from features.paper.paper_schemas import MissingParameterPromptModel, ModelGenerationPlanModel


class PaperJobDocumentStatus(BaseModel):
    """Per-document status exposed by GET paper status."""

    document_id: str = Field(pattern=r"^DOC-[0-9]{3}$")
    status: PaperUploadDocumentState
    error_code: str | None = None
    model_config = ConfigDict(extra="forbid")


class PaperStatusResponse(BaseModel):
    """GET /api/v1/papers/{paper_id}/status response."""

    paper_id: str
    job_id: str
    execution_mode: PaperUploadExecutionMode
    job_state: PaperUploadJobState
    stage: PaperUploadStage
    failed_stage: PaperUploadStage | None = None
    error_code: str | None = None
    retryable: bool
    next_action: PaperUploadNextAction
    expires_at: datetime
    documents: list[PaperJobDocumentStatus]
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain(cls, record: PaperUploadJobRecord) -> PaperStatusResponse:
        return cls(
            paper_id=record.paper_id,
            job_id=record.job_id,
            execution_mode=record.execution_mode,
            job_state=record.job_state,
            stage=record.stage,
            failed_stage=record.failed_stage,
            error_code=record.last_error_code,
            retryable=record.retryable,
            next_action=next_action_for_job(record),
            expires_at=record.expires_at,
            documents=[
                PaperJobDocumentStatus(
                    document_id=document.document_id,
                    status=document.status,
                    error_code=document.error_code,
                )
                for document in record.documents
            ],
        )


class RerunPlanRequest(BaseModel):
    """POST /api/v1/papers/{paper_id}/rerun-plan request."""

    model_config = ConfigDict(extra="forbid")


class RerunPlanResponse(BaseModel):
    """POST /api/v1/papers/{paper_id}/rerun-plan response."""

    paper_id: str
    job_id: str
    job_state: PaperUploadJobState
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    remaining_missing_prompts: list[MissingParameterPromptModel]
    model_config = ConfigDict(extra="forbid")


PaperStatusResponseSchema = PaperStatusResponse
PaperJobDocumentStatusSchema = PaperJobDocumentStatus
RerunPlanRequestSchema = RerunPlanRequest
RerunPlanResponseSchema = RerunPlanResponse
