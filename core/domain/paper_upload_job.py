"""Domain records for paper upload job state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PaperUploadExecutionMode = Literal["sync", "async", "rerun_plan"]
PaperUploadJobState = Literal[
    "queued",
    "running",
    "spec_ready",
    "plan_generating",
    "ready",
    "plan_failed_retryable",
    "plan_failed_permanent",
    "failed_no_usable_spec",
    "abandoned_plan_retryable",
    "abandoned_reupload_required",
]
PaperUploadStage = Literal[
    "uploading",
    "parsing",
    "extracting_spec",
    "fusing",
    "persisting_spec",
    "generating_plan",
    "persisting_plan",
    "done",
]
PaperUploadDocumentState = Literal[
    "pending",
    "parsing",
    "parsed",
    "extracting",
    "succeeded",
    "failed",
]
PaperUploadNextAction = Literal[
    "wait",
    "rerun_plan",
    "reupload",
    "open_result",
    "none",
    "contact_support",
]


@dataclass(frozen=True)
class PaperUploadJobDocument:
    """Persisted status for one uploaded document in a paper job."""

    document_id: str
    upload_index: int
    status: PaperUploadDocumentState
    error_code: str | None
    updated_at: datetime


@dataclass(frozen=True)
class PaperUploadJobRecord:
    """Persisted paper upload job state."""

    job_id: str
    paper_id: str
    execution_mode: PaperUploadExecutionMode
    job_state: PaperUploadJobState
    stage: PaperUploadStage
    failed_stage: PaperUploadStage | None
    last_error_code: str | None
    retryable: bool
    attempt_count: int
    state_version: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime
    documents: list[PaperUploadJobDocument]


def next_action_for_job(record: PaperUploadJobRecord) -> PaperUploadNextAction:
    """Return the stable UI action for a non-expired job."""

    if record.job_state in {"queued", "running", "plan_generating"}:
        return "wait"
    if record.job_state == "ready":
        return "open_result"
    if record.job_state in {
        "spec_ready",
        "plan_failed_retryable",
        "abandoned_plan_retryable",
    }:
        return "rerun_plan"
    if record.job_state in {
        "failed_no_usable_spec",
        "abandoned_reupload_required",
    }:
        return "reupload"
    if record.job_state == "plan_failed_permanent":
        return "contact_support"
    return "none"
