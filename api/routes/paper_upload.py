"""Paper document upload endpoint."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_paper_bundle_store,
    get_paper_plan_service,
    get_paper_reparse_lock_registry,
    get_paper_reparse_store,
    get_paper_spec_service,
    get_paper_upload_job_store,
    get_settings,
)
from app.config import AppSettings
from core.domain.exceptions import (
    DocumentParseError,
    LLMAuthError,
    LLMError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    PaperNotFoundError,
    PaperPlanGenerationError,
    PaperReparseInProgressError,
    PaperSpecGenerationError,
    StoreError,
)
from core.domain.paper_plan import PaperPlanRecord
from core.domain.paper_reparse_source import PaperReparseSource
from core.domain.paper_spec import PaperSpec
from core.domain.paper_upload_job import PaperUploadJobRecord, PaperUploadStage
from core.interfaces.paper_cache import PaperBundleStore
from core.interfaces.paper_reparse_store import PaperReparseStore
from core.interfaces.paper_upload_job_store import PaperUploadJobStore
from features.paper.paper_document_identity import sanitize_paper_display_filename
from features.paper.paper_fusion import (
    SuccessfulPaperSpec,
    document_id_for_upload_index,
    fuse_successful_specs,
)
from features.paper.paper_plan_helpers import resolved_prompt_ids
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_reparse_service import PaperReparseLockRegistry
from features.paper.paper_reparse_source import (
    SuccessfulParsedDocument,
    build_reparse_source,
)
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)
from features.paper.paper_spec_service import PaperSpecService
from features.paper.paper_upload_job_schemas import (
    PaperStatusResponse,
    RerunPlanRequest,
    RerunPlanResponse,
    UploadAsyncResponse,
)
from features.paper.structured_retry import StructuredRetryContext

PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"
SAVE_CHUNK_SIZE = 1024 * 1024
MAX_PAPER_UPLOAD_FILES = 5
PAPER_STAGING_DIRNAME = "paper_staging"

router = APIRouter(tags=["paper"])


class UploadDocumentStatusModel(BaseModel):
    """Per-uploaded-document processing status."""

    document_id: str
    filename: str
    status: Literal["succeeded", "failed"]
    error_code: str | None = None
    model_config = ConfigDict(extra="forbid")


class UploadDocumentResponse(BaseModel):
    """POST /api/v1/upload-document response model."""

    paper_id: str
    spec: PaperSpecModel
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    document_statuses: list[UploadDocumentStatusModel]
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class _PlanGenerationResult:
    record: PaperPlanRecord


@dataclass(frozen=True)
class _UploadFailure:
    status_code: int
    error_code: str
    message: str
    paper_id: str
    job_id: str


@dataclass(frozen=True)
class _StagedUploadDocument:
    upload_index: int
    document_id: str
    display_filename: str
    saved_path: Path


@dataclass(frozen=True)
class _PreparedUpload:
    staged_documents: list[_StagedUploadDocument]
    document_statuses: list[UploadDocumentStatusModel]
    first_error: Exception | None


@router.post("/api/v1/upload-document", response_model=UploadDocumentResponse)
async def upload_document(
    file: Annotated[list[UploadFile], File(...)],
    service: Annotated[PaperSpecService, Depends(get_paper_spec_service)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    reparse_store: Annotated[PaperReparseStore, Depends(get_paper_reparse_store)],
    job_store: Annotated[PaperUploadJobStore, Depends(get_paper_upload_job_store)],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
    settings: Annotated[AppSettings, Depends(get_settings)],
    primary_index: Annotated[int | None, Form()] = None,
) -> UploadDocumentResponse | JSONResponse:
    """Upload a PDF/docx paper and return generated PaperSpec + baseline plan."""
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024
    files = list(file)
    _validate_file_count(files)
    _validate_primary_index(primary_index, len(files))
    paper_id = str(uuid.uuid4())
    job_id = f"PUJ-{uuid.uuid4()}"
    staging_dir = _paper_staging_job_dir(settings.upload_dir, job_id)
    failure: _UploadFailure | None = None
    staging_handed_to_orchestrator = False
    try:
        await job_store.create_upload_job(
            job_id=job_id,
            paper_id=paper_id,
            execution_mode="sync",
            document_ids=[document_id_for_upload_index(index) for index in range(len(files))],
            expires_at=datetime.utcnow() + timedelta(hours=settings.upload_ttl_hours),
        )
        prepared = await _prepare_upload_staging(
            files=files,
            paper_id=paper_id,
            staging_dir=staging_dir,
            max_upload_bytes=max_upload_bytes,
            primary_index=primary_index,
            job_store=job_store,
        )
        if not prepared.staged_documents:
            failure = await _mark_upload_failed_no_usable_spec(
                job_store,
                paper_id,
                job_id,
                prepared.first_error or DocumentParseError("document_parse_failed"),
                failed_stage="extracting_spec",
            )
            return _upload_failure_response(failure)

        staging_handed_to_orchestrator = True
        result = await _run_upload_job(
            staged_documents=prepared.staged_documents,
            initial_document_statuses=prepared.document_statuses,
            first_error=prepared.first_error,
            paper_id=paper_id,
            job_id=job_id,
            staging_dir=staging_dir,
            primary_index=primary_index,
            service=service,
            plan_service=plan_service,
            bundle_store=bundle_store,
            reparse_store=reparse_store,
            job_store=job_store,
            lock_registry=lock_registry,
            retry_context=_structured_retry_context(settings),
        )
        if isinstance(result, _UploadFailure):
            failure = result
            return _upload_failure_response(result)
        return result
    finally:
        if failure is not None:
            logger.info(
                "paper_upload_failed: paper_id={} job_id={} error_code={} failed_stage={}",
                failure.paper_id,
                failure.job_id,
                failure.error_code,
                "recorded",
            )
        if not staging_handed_to_orchestrator:
            await _cleanup_staging_dir(staging_dir, reason="request_bail")


@router.post(
    "/api/v1/upload-async",
    response_model=UploadAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document_async(
    background_tasks: BackgroundTasks,
    file: Annotated[list[UploadFile], File(...)],
    service: Annotated[PaperSpecService, Depends(get_paper_spec_service)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    reparse_store: Annotated[PaperReparseStore, Depends(get_paper_reparse_store)],
    job_store: Annotated[PaperUploadJobStore, Depends(get_paper_upload_job_store)],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
    settings: Annotated[AppSettings, Depends(get_settings)],
    primary_index: Annotated[int | None, Form()] = None,
) -> UploadAsyncResponse:
    """Accept a paper upload and process it after the response."""
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024
    files = list(file)
    _validate_file_count(files)
    _validate_primary_index(primary_index, len(files))
    paper_id = str(uuid.uuid4())
    job_id = f"PUJ-{uuid.uuid4()}"
    staging_dir = _paper_staging_job_dir(settings.upload_dir, job_id)
    failure: _UploadFailure | None = None
    staging_handed_to_orchestrator = False
    try:
        await job_store.create_upload_job(
            job_id=job_id,
            paper_id=paper_id,
            execution_mode="async",
            document_ids=[document_id_for_upload_index(index) for index in range(len(files))],
            expires_at=datetime.utcnow() + timedelta(hours=settings.upload_ttl_hours),
        )
        prepared = await _prepare_upload_staging(
            files=files,
            paper_id=paper_id,
            staging_dir=staging_dir,
            max_upload_bytes=max_upload_bytes,
            primary_index=primary_index,
            job_store=job_store,
        )
        if not prepared.staged_documents:
            failure = await _mark_upload_failed_no_usable_spec(
                job_store,
                paper_id,
                job_id,
                prepared.first_error or DocumentParseError("document_parse_failed"),
                failed_stage="extracting_spec",
            )
            return UploadAsyncResponse(paper_id=paper_id, job_id=job_id)

        staging_handed_to_orchestrator = True
        background_tasks.add_task(
            _run_upload_job_background,
            staged_documents=prepared.staged_documents,
            initial_document_statuses=prepared.document_statuses,
            first_error=prepared.first_error,
            paper_id=paper_id,
            job_id=job_id,
            staging_dir=staging_dir,
            primary_index=primary_index,
            service=service,
            plan_service=plan_service,
            bundle_store=bundle_store,
            reparse_store=reparse_store,
            job_store=job_store,
            lock_registry=lock_registry,
            retry_context=_structured_retry_context(settings),
        )
        return UploadAsyncResponse(paper_id=paper_id, job_id=job_id)
    finally:
        if failure is not None:
            logger.info(
                "paper_upload_failed: paper_id={} job_id={} error_code={} failed_stage={}",
                failure.paper_id,
                failure.job_id,
                failure.error_code,
                "recorded",
            )
        if not staging_handed_to_orchestrator:
            await _cleanup_staging_dir(staging_dir, reason="request_bail")


async def _prepare_upload_staging(
    *,
    files: list[UploadFile],
    paper_id: str,
    staging_dir: Path,
    max_upload_bytes: int,
    primary_index: int | None,
    job_store: PaperUploadJobStore,
) -> _PreparedUpload:
    staged_documents: list[_StagedUploadDocument] = []
    document_statuses: list[UploadDocumentStatusModel] = []
    first_error: Exception | None = None
    await job_store.update_upload_job_state(
        paper_id,
        job_state="running",
        stage="uploading",
        retryable=False,
    )
    for upload_index, upload_file in enumerate(files):
        document_id = document_id_for_upload_index(upload_index)
        display_filename = sanitize_paper_display_filename(upload_file.filename)
        try:
            await job_store.update_upload_job_state(
                paper_id,
                job_state="running",
                stage="parsing",
                retryable=False,
            )
            await job_store.update_upload_document_state(
                paper_id,
                document_id,
                status="parsing",
            )
            _validate_declared_size(upload_file.size, max_upload_bytes)
            header = await upload_file.read(8192)
            extension = _validate_magic_and_extension(header, upload_file.filename)
            await upload_file.seek(0)
            saved_path = await asyncio.to_thread(
                _save_upload_sync,
                upload_file,
                staging_dir,
                extension,
                max_upload_bytes,
                document_id,
            )
        except DocumentParseError as exc:
            first_error = first_error or exc
            document_statuses.append(
                UploadDocumentStatusModel(
                    document_id=document_id,
                    filename=display_filename,
                    status="failed",
                    error_code=_per_document_error_code(exc),
                )
            )
            await job_store.update_upload_document_state(
                paper_id,
                document_id,
                status="failed",
                error_code=_per_document_error_code(exc),
            )
            if primary_index == upload_index:
                return _PreparedUpload(
                    staged_documents=staged_documents,
                    document_statuses=document_statuses,
                    first_error=exc,
                )
            continue

        staged_documents.append(
            _StagedUploadDocument(
                upload_index=upload_index,
                document_id=document_id,
                display_filename=display_filename,
                saved_path=saved_path,
            )
        )

    return _PreparedUpload(
        staged_documents=staged_documents,
        document_statuses=document_statuses,
        first_error=first_error,
    )


async def _run_upload_job(
    *,
    staged_documents: list[_StagedUploadDocument],
    initial_document_statuses: list[UploadDocumentStatusModel],
    first_error: Exception | None,
    paper_id: str,
    job_id: str,
    staging_dir: Path,
    primary_index: int | None,
    service: PaperSpecService,
    plan_service: PaperPlanService,
    bundle_store: PaperBundleStore,
    reparse_store: PaperReparseStore,
    job_store: PaperUploadJobStore,
    lock_registry: PaperReparseLockRegistry,
    retry_context: StructuredRetryContext | None = None,
) -> UploadDocumentResponse | _UploadFailure:
    successes: list[SuccessfulPaperSpec] = []
    source_documents: list[SuccessfulParsedDocument] = []
    document_statuses = list(initial_document_statuses)
    try:
        for staged_document in staged_documents:
            upload_index = staged_document.upload_index
            document_id = staged_document.document_id
            display_filename = staged_document.display_filename
            saved_path = staged_document.saved_path
            try:
                await asyncio.to_thread(_compute_sha256_sync, saved_path)
                logger.info("paper_document_upload_accepted: document_id={}", document_id)
                parsed = await service.parse_uncached(saved_path)
                await job_store.update_upload_document_state(
                    paper_id,
                    document_id,
                    status="parsed",
                )
                await job_store.update_upload_job_state(
                    paper_id,
                    job_state="running",
                    stage="extracting_spec",
                    retryable=False,
                )
                await job_store.update_upload_document_state(
                    paper_id,
                    document_id,
                    status="extracting",
                )
                spec = await service.extract_parsed_uncached(
                    parsed,
                    paper_id,
                    display_filename=display_filename,
                    document_id=document_id,
                    retry_context=retry_context,
                )
            except (DocumentParseError, PaperSpecGenerationError) as exc:
                first_error = first_error or exc
                document_statuses.append(
                    UploadDocumentStatusModel(
                        document_id=document_id,
                        filename=display_filename,
                        status="failed",
                        error_code=_per_document_error_code(exc),
                    )
                )
                await job_store.update_upload_document_state(
                    paper_id,
                    document_id,
                    status="failed",
                    error_code=_per_document_error_code(exc),
                )
                if primary_index == upload_index:
                    return await _mark_upload_failed_no_usable_spec(
                        job_store,
                        paper_id,
                        job_id,
                        exc,
                        failed_stage="extracting_spec",
                    )
                continue

            successes.append(
                SuccessfulPaperSpec(
                    upload_index=upload_index,
                    document_id=document_id,
                    filename=display_filename,
                    spec=spec,
                )
            )
            source_documents.append(
                SuccessfulParsedDocument(
                    upload_index=upload_index,
                    document_id=document_id,
                    filename=display_filename,
                    parsed=parsed,
                )
            )
            await job_store.update_upload_document_state(
                paper_id,
                document_id,
                status="succeeded",
            )
            document_statuses.append(
                UploadDocumentStatusModel(
                    document_id=document_id,
                    filename=display_filename,
                    status="succeeded",
                    error_code=None,
                )
            )
    finally:
        await _cleanup_staging_dir(staging_dir, reason="orchestrator_documents_done")

    if not successes:
        return await _mark_upload_failed_no_usable_spec(
            job_store,
            paper_id,
            job_id,
            first_error or DocumentParseError("document_parse_failed"),
            failed_stage="extracting_spec",
        )

    try:
        await job_store.update_upload_job_state(
            paper_id,
            job_state="running",
            stage="fusing",
            retryable=False,
        )
        spec = fuse_successful_specs(successes, primary_index)
    except DocumentParseError as exc:
        return await _mark_upload_failed_no_usable_spec(
            job_store,
            paper_id,
            job_id,
            exc,
            failed_stage="fusing",
        )

    try:
        await job_store.update_upload_job_state(
            paper_id,
            job_state="running",
            stage="persisting_spec",
            retryable=False,
        )
        await bundle_store.put_spec(paper_id, spec)
        await job_store.update_upload_job_state(
            paper_id,
            job_state="spec_ready",
            stage="persisting_spec",
            retryable=True,
        )
    except StoreError as exc:
        return await _mark_upload_failed_no_usable_spec(
            job_store,
            paper_id,
            job_id,
            exc,
            failed_stage="persisting_spec",
            force_error_code="store_error",
            status_code=500,
        )

    source = build_reparse_source(paper_id, source_documents, primary_index)
    plan_result = await _run_initial_plan_generation(
        paper_id=paper_id,
        job_id=job_id,
        spec=spec,
        plan_service=plan_service,
        bundle_store=bundle_store,
        reparse_store=reparse_store,
        job_store=job_store,
        lock_registry=lock_registry,
        source=source,
        retry_context=retry_context,
    )
    if isinstance(plan_result, _UploadFailure):
        return plan_result
    record = plan_result.record
    return UploadDocumentResponse(
        paper_id=paper_id,
        spec=PaperSpecModel.from_domain(record.spec),
        plan=ModelGenerationPlanModel.from_domain(record.plan),
        missing_prompts=[
            MissingParameterPromptModel.from_domain(prompt) for prompt in record.missing_prompts
        ],
        document_statuses=document_statuses,
    )


async def _run_upload_job_background(
    *,
    staged_documents: list[_StagedUploadDocument],
    initial_document_statuses: list[UploadDocumentStatusModel],
    first_error: Exception | None,
    paper_id: str,
    job_id: str,
    staging_dir: Path,
    primary_index: int | None,
    service: PaperSpecService,
    plan_service: PaperPlanService,
    bundle_store: PaperBundleStore,
    reparse_store: PaperReparseStore,
    job_store: PaperUploadJobStore,
    lock_registry: PaperReparseLockRegistry,
    retry_context: StructuredRetryContext | None = None,
) -> None:
    try:
        result = await _run_upload_job(
            staged_documents=staged_documents,
            initial_document_statuses=initial_document_statuses,
            first_error=first_error,
            paper_id=paper_id,
            job_id=job_id,
            staging_dir=staging_dir,
            primary_index=primary_index,
            service=service,
            plan_service=plan_service,
            bundle_store=bundle_store,
            reparse_store=reparse_store,
            job_store=job_store,
            lock_registry=lock_registry,
            retry_context=retry_context,
        )
        if isinstance(result, _UploadFailure):
            logger.info(
                "paper_upload_failed: paper_id={} job_id={} error_code={} failed_stage={}",
                result.paper_id,
                result.job_id,
                result.error_code,
                "recorded",
            )
    except Exception as exc:
        logger.error(
            "paper_upload_background_failed: paper_id={} job_id={} exception={}",
            paper_id,
            job_id,
            type(exc).__name__,
        )
        await _mark_unhandled_background_failure(job_store, paper_id, job_id)


async def sweep_stale_paper_upload_jobs(
    *,
    upload_dir: str | Path,
    bundle_store: PaperBundleStore,
    job_store: PaperUploadJobStore,
) -> int:
    """Classify non-durable paper upload jobs left by a prior process."""
    try:
        stale_jobs = await job_store.list_stale_upload_jobs()
    except Exception as exc:
        logger.error("paper_upload_startup_sweep_list_failed: exception={}", type(exc).__name__)
        return 0

    swept = 0
    for record in stale_jobs:
        try:
            await _sweep_one_stale_upload_job(
                upload_dir=upload_dir,
                bundle_store=bundle_store,
                job_store=job_store,
                record=record,
            )
            swept += 1
        except Exception as exc:
            logger.error(
                "paper_upload_startup_sweep_job_failed: paper_id={} job_id={} exception={}",
                record.paper_id,
                record.job_id,
                type(exc).__name__,
            )
    if swept:
        logger.info("paper_upload_startup_sweep_completed: count={}", swept)
    return swept


async def _sweep_one_stale_upload_job(
    *,
    upload_dir: str | Path,
    bundle_store: PaperBundleStore,
    job_store: PaperUploadJobStore,
    record: PaperUploadJobRecord,
) -> None:
    plan_record: PaperPlanRecord | None
    try:
        plan_record = await bundle_store.get_plan_record(record.paper_id)
    except StoreError as exc:
        logger.error(
            "paper_upload_startup_sweep_plan_read_failed: paper_id={} job_id={} exception={}",
            record.paper_id,
            record.job_id,
            type(exc).__name__,
        )
        plan_record = None

    if plan_record is not None:
        await job_store.mark_upload_job_terminal(
            record.paper_id,
            job_state="ready",
            stage="done",
            failed_stage=None,
            error_code=None,
            retryable=False,
            finished_at=datetime.utcnow(),
        )
        await _cleanup_staging_dir(
            _paper_staging_job_dir(upload_dir, record.job_id),
            reason="startup_ready_repair",
        )
        return

    spec = await bundle_store.get_spec(record.paper_id)
    if spec is not None:
        await job_store.mark_upload_job_terminal(
            record.paper_id,
            job_state="abandoned_plan_retryable",
            stage=None,
            failed_stage=record.stage,
            error_code="upload_job_abandoned",
            retryable=True,
            finished_at=datetime.utcnow(),
        )
        await _cleanup_staging_dir(
            _paper_staging_job_dir(upload_dir, record.job_id),
            reason="startup_abandoned_plan_retryable",
        )
        return

    await job_store.mark_upload_job_terminal(
        record.paper_id,
        job_state="abandoned_reupload_required",
        stage=None,
        failed_stage=record.stage,
        error_code="upload_job_abandoned",
        retryable=False,
        finished_at=datetime.utcnow(),
    )
    await _cleanup_staging_dir(
        _paper_staging_job_dir(upload_dir, record.job_id),
        reason="startup_abandoned_reupload_required",
    )


@router.get(
    "/api/v1/papers/{paper_id}/status",
    response_model=PaperStatusResponse,
)
async def get_paper_status(
    paper_id: str,
    job_store: Annotated[PaperUploadJobStore, Depends(get_paper_upload_job_store)],
) -> PaperStatusResponse | JSONResponse:
    """Return persisted upload/rerun state for a paper."""
    record = await job_store.get_upload_job(paper_id)
    if record is None:
        raise PaperNotFoundError("paper_not_found") from None
    if _is_expired(record.expires_at):
        return _paper_error_response(
            status_code=410,
            error_code="paper_expired",
            message="这份资料已过期,请重新上传",
            paper_id=paper_id,
            job_id=record.job_id,
        )
    return PaperStatusResponse.from_domain(record)


@router.post(
    "/api/v1/papers/{paper_id}/rerun-plan",
    response_model=RerunPlanResponse,
)
async def rerun_paper_plan(
    paper_id: str,
    request: Annotated[RerunPlanRequest, Body(default_factory=RerunPlanRequest)],
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    job_store: Annotated[PaperUploadJobStore, Depends(get_paper_upload_job_store)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> RerunPlanResponse | JSONResponse:
    """Regenerate a plan from a persisted spec-only or retryable-failed state."""
    _ = request
    record = await job_store.get_upload_job(paper_id)
    if record is None:
        raise PaperNotFoundError("paper_not_found") from None
    if _is_expired(record.expires_at):
        return _paper_error_response(
            status_code=410,
            error_code="paper_expired",
            message="这份资料已过期,请重新上传",
            paper_id=paper_id,
            job_id=record.job_id,
        )

    try:
        async with await lock_registry.acquire(paper_id):
            started = await job_store.try_start_rerun_plan(paper_id)
            if started is None:
                current = await job_store.get_upload_job(paper_id)
                return _paper_error_response(
                    status_code=409,
                    error_code="rerun_plan_unavailable",
                    message="当前状态不能重跑建模计划",
                    paper_id=paper_id,
                    job_id=current.job_id if current is not None else record.job_id,
                )
            spec = await bundle_store.get_spec(paper_id)
            if spec is None:
                await job_store.update_upload_job_state(
                    paper_id,
                    job_state="failed_no_usable_spec",
                    stage="generating_plan",
                    failed_stage="generating_plan",
                    error_code="paper_not_found",
                    retryable=False,
                    finished_at=datetime.utcnow(),
                )
                raise PaperNotFoundError("paper_not_found") from None
            result = await _run_plan_generation(
                paper_id=paper_id,
                job_id=started.job_id,
                spec=spec,
                plan_service=plan_service,
                bundle_store=bundle_store,
                reparse_store=None,
                job_store=job_store,
                source=None,
                retry_context=_structured_retry_context(settings),
            )
    except PaperReparseInProgressError:
        return _paper_error_response(
            status_code=409,
            error_code="rerun_plan_in_progress",
            message="这份结果正在更新,请稍后重试",
            paper_id=paper_id,
            job_id=record.job_id,
        )

    if isinstance(result, _UploadFailure):
        return _upload_failure_response(result)

    resolved_ids = resolved_prompt_ids(result.record)
    remaining_prompts = [
        prompt for prompt in result.record.missing_prompts if prompt.prompt_id not in resolved_ids
    ]
    return RerunPlanResponse(
        paper_id=paper_id,
        job_id=record.job_id,
        job_state="ready",
        plan=ModelGenerationPlanModel.from_domain(result.record.plan),
        missing_prompts=[
            MissingParameterPromptModel.from_domain(prompt)
            for prompt in result.record.missing_prompts
        ],
        remaining_missing_prompts=[
            MissingParameterPromptModel.from_domain(prompt) for prompt in remaining_prompts
        ],
    )


async def _run_initial_plan_generation(
    *,
    paper_id: str,
    job_id: str,
    spec: PaperSpec,
    plan_service: PaperPlanService,
    bundle_store: PaperBundleStore,
    reparse_store: PaperReparseStore | None,
    job_store: PaperUploadJobStore,
    lock_registry: PaperReparseLockRegistry,
    source: PaperReparseSource | None,
    retry_context: StructuredRetryContext | None = None,
) -> _PlanGenerationResult | _UploadFailure:
    try:
        async with await lock_registry.acquire(paper_id):
            started = await job_store.try_start_initial_plan(paper_id)
            if started is None:
                current = await job_store.get_upload_job(paper_id)
                return _UploadFailure(
                    status_code=409,
                    error_code="plan_generation_unavailable",
                    message="当前状态不能生成建模计划",
                    paper_id=paper_id,
                    job_id=current.job_id if current is not None else job_id,
                )
            return await _run_plan_generation(
                paper_id=paper_id,
                job_id=started.job_id,
                spec=spec,
                plan_service=plan_service,
                bundle_store=bundle_store,
                reparse_store=reparse_store,
                job_store=job_store,
                source=source,
                retry_context=retry_context,
            )
    except PaperReparseInProgressError:
        await job_store.update_upload_job_state(
            paper_id,
            job_state="plan_failed_retryable",
            stage="generating_plan",
            failed_stage="generating_plan",
            error_code="plan_generation_in_progress",
            retryable=True,
            finished_at=datetime.utcnow(),
        )
        return _UploadFailure(
            status_code=409,
            error_code="plan_generation_in_progress",
            message="这份结果正在更新,请稍后重试",
            paper_id=paper_id,
            job_id=job_id,
        )


async def _run_plan_generation(
    *,
    paper_id: str,
    job_id: str,
    spec: PaperSpec,
    plan_service: PaperPlanService,
    bundle_store: PaperBundleStore,
    reparse_store: PaperReparseStore | None,
    job_store: PaperUploadJobStore,
    source: PaperReparseSource | None,
    retry_context: StructuredRetryContext | None = None,
) -> _PlanGenerationResult | _UploadFailure:
    try:
        plan, missing_prompts, missing_bindings = await plan_service.generate(
            spec,
            paper_id,
            retry_context=retry_context,
        )
    except Exception as exc:
        failure = await _mark_plan_failed(
            job_store,
            paper_id,
            job_id,
            exc,
            failed_stage="generating_plan",
        )
        _log_structured_retry_job_summary(
            paper_id=paper_id,
            terminal_state="plan_failed_retryable",
            retry_context=retry_context,
        )
        return failure

    record = PaperPlanRecord(
        paper_id=paper_id,
        spec=spec,
        plan=plan,
        missing_prompts=missing_prompts,
        missing_bindings=missing_bindings,
    )
    try:
        await job_store.update_upload_job_state(
            paper_id,
            job_state="plan_generating",
            stage="persisting_plan",
            retryable=False,
        )
        if source is None:
            await bundle_store.set_plan(paper_id, record)
        else:
            if reparse_store is None:
                raise StoreError("paper_reparse_store_missing")
            await reparse_store.save_ready_bundle_with_source(record, source)
        await job_store.update_upload_job_state(
            paper_id,
            job_state="ready",
            stage="done",
            retryable=False,
            finished_at=datetime.utcnow(),
        )
        _log_structured_retry_job_summary(
            paper_id=paper_id,
            terminal_state="ready",
            retry_context=retry_context,
        )
        return _PlanGenerationResult(record=record)
    except Exception as exc:
        failure = await _mark_plan_failed(
            job_store,
            paper_id,
            job_id,
            exc,
            failed_stage="persisting_plan",
            force_retryable=True,
            force_error_code="store_error" if isinstance(exc, StoreError) else None,
            status_code=500 if isinstance(exc, StoreError) else None,
        )
        _log_structured_retry_job_summary(
            paper_id=paper_id,
            terminal_state="plan_failed_retryable",
            retry_context=retry_context,
        )
        return failure


async def _mark_unhandled_background_failure(
    job_store: PaperUploadJobStore,
    paper_id: str,
    job_id: str,
) -> None:
    try:
        record = await job_store.get_upload_job(paper_id)
        if record is None:
            return
        if record.job_state in {"queued", "running"}:
            spec_failed_stage = _spec_failure_stage(record.stage)
            await job_store.update_upload_job_state(
                paper_id,
                job_state="failed_no_usable_spec",
                stage=spec_failed_stage,
                failed_stage=spec_failed_stage,
                error_code="internal_error",
                retryable=False,
                finished_at=datetime.utcnow(),
            )
            return
        if record.job_state in {"spec_ready", "plan_generating"}:
            plan_failed_stage = _plan_failure_stage(record.stage)
            await job_store.update_upload_job_state(
                paper_id,
                job_state="plan_failed_retryable",
                stage=plan_failed_stage,
                failed_stage=plan_failed_stage,
                error_code="internal_error",
                retryable=True,
                finished_at=datetime.utcnow(),
            )
    except Exception as exc:
        logger.error(
            "paper_upload_background_mark_failed: paper_id={} job_id={} exception={}",
            paper_id,
            job_id,
            type(exc).__name__,
        )


def _spec_failure_stage(
    stage: PaperUploadStage,
) -> Literal[
    "parsing",
    "extracting_spec",
    "fusing",
    "persisting_spec",
]:
    if stage == "parsing":
        return "parsing"
    if stage == "fusing":
        return "fusing"
    if stage == "persisting_spec":
        return "persisting_spec"
    if stage == "extracting_spec":
        return stage
    return "extracting_spec"


def _plan_failure_stage(stage: PaperUploadStage) -> Literal["generating_plan", "persisting_plan"]:
    if stage == "persisting_plan":
        return "persisting_plan"
    return "generating_plan"


def _structured_retry_context(settings: AppSettings) -> StructuredRetryContext:
    return StructuredRetryContext(
        warning_call_count=settings.paper_structured_retry_warning_call_count,
        hard_call_count=settings.paper_structured_retry_hard_call_count,
        wall_clock_seconds=settings.paper_structured_retry_wall_clock_seconds,
    )


def _log_structured_retry_job_summary(
    *,
    paper_id: str,
    terminal_state: str,
    retry_context: StructuredRetryContext | None,
) -> None:
    if retry_context is None:
        return
    logger.info(
        "paper_structured_retry_job_summary: paper_id={} terminal_state={} "
        "call_count={} rescued_leaf_count={}",
        paper_id,
        terminal_state,
        retry_context.call_count,
        len(retry_context.rescued_leaves),
    )


async def _mark_upload_failed_no_usable_spec(
    job_store: PaperUploadJobStore,
    paper_id: str,
    job_id: str,
    exc: Exception,
    *,
    failed_stage: Literal[
        "parsing",
        "extracting_spec",
        "fusing",
        "persisting_spec",
    ],
    force_error_code: str | None = None,
    status_code: int | None = None,
) -> _UploadFailure:
    status, error_code, message = _error_contract_for_exception(exc)
    await job_store.update_upload_job_state(
        paper_id,
        job_state="failed_no_usable_spec",
        stage=failed_stage,
        failed_stage=failed_stage,
        error_code=force_error_code or error_code,
        retryable=False,
        finished_at=datetime.utcnow(),
    )
    return _UploadFailure(
        status_code=status_code or status,
        error_code=force_error_code or error_code,
        message=message,
        paper_id=paper_id,
        job_id=job_id,
    )


async def _mark_plan_failed(
    job_store: PaperUploadJobStore,
    paper_id: str,
    job_id: str,
    exc: Exception,
    *,
    failed_stage: Literal["generating_plan", "persisting_plan"],
    force_retryable: bool | None = None,
    force_error_code: str | None = None,
    status_code: int | None = None,
) -> _UploadFailure:
    status, error_code, message = _error_contract_for_exception(exc)
    retryable = force_retryable if force_retryable is not None else _is_retryable_plan_error(exc)
    job_state: Literal["plan_failed_retryable", "plan_failed_permanent"] = (
        "plan_failed_retryable" if retryable else "plan_failed_permanent"
    )
    await job_store.update_upload_job_state(
        paper_id,
        job_state=job_state,
        stage=failed_stage,
        failed_stage=failed_stage,
        error_code=force_error_code or error_code,
        retryable=retryable,
        finished_at=datetime.utcnow(),
    )
    return _UploadFailure(
        status_code=status_code or status,
        error_code=force_error_code or error_code,
        message=message,
        paper_id=paper_id,
        job_id=job_id,
    )


def _is_retryable_plan_error(exc: Exception) -> bool:
    if isinstance(exc, LLMAuthError):
        return False
    if isinstance(exc, StoreError):
        return True
    if isinstance(
        exc,
        PaperPlanGenerationError
        | LLMQuotaError
        | LLMRateLimitError
        | LLMServerError
        | LLMTimeoutError
        | LLMError,
    ):
        return True
    return True


def _error_contract_for_exception(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, DocumentParseError):
        return 400, "document_parse_failed", "文档解析失败,请检查文件是否损坏或超过 512MB"
    if isinstance(exc, PaperSpecGenerationError):
        return 502, "paper_spec_generation_failed", "资料理解失败,请刷新重试"
    if isinstance(exc, PaperPlanGenerationError):
        return 502, "paper_plan_generation_failed", "建模计划生成失败,请刷新重试"
    if isinstance(exc, LLMAuthError):
        return 503, "llm_auth", "服务暂时不可用,请稍后重试"
    if isinstance(exc, LLMQuotaError):
        return 503, "llm_quota", "服务繁忙,请稍后"
    if isinstance(exc, LLMRateLimitError):
        return 429, "llm_rate_limit", "请求太频繁,稍等一下"
    if isinstance(exc, LLMTimeoutError):
        return 504, "llm_timeout", "网络较慢,正在重试..."
    if isinstance(exc, LLMServerError):
        return 502, "llm_server", "AI 服务暂不稳定,请刷新重试"
    if isinstance(exc, StoreError):
        return 500, "store_error", "系统暂时不可用,请稍后重试"
    return 500, "internal_error", "出了点问题,我们已经记录,稍后再试"


def _upload_failure_response(failure: _UploadFailure) -> JSONResponse:
    return _paper_error_response(
        status_code=failure.status_code,
        error_code=failure.error_code,
        message=failure.message,
        paper_id=failure.paper_id,
        job_id=failure.job_id,
    )


def _paper_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    paper_id: str,
    job_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_code,
            "message": message,
            "paper_id": paper_id,
            "job_id": job_id,
        },
    )


def _is_expired(expires_at: datetime) -> bool:
    return expires_at <= datetime.utcnow()


def _validate_declared_size(size: int | None, max_upload_bytes: int) -> None:
    if size is not None and size > max_upload_bytes:
        raise DocumentParseError("document_too_large") from None


def _validate_file_count(files: list[UploadFile]) -> None:
    if not files:
        raise DocumentParseError("document_required") from None
    if len(files) > MAX_PAPER_UPLOAD_FILES:
        raise DocumentParseError("too_many_documents") from None


def _validate_primary_index(primary_index: int | None, file_count: int) -> None:
    if primary_index is None:
        return
    if primary_index < 0 or primary_index >= file_count:
        raise DocumentParseError("primary_index_invalid") from None


def _validate_magic_and_extension(header: bytes, filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension == ".pdf" and header.startswith(PDF_MAGIC):
        return ".pdf"
    if extension == ".docx" and header.startswith(DOCX_MAGIC):
        return ".docx"
    raise DocumentParseError("unsupported_document_format") from None


def _paper_staging_root(upload_dir: str | Path) -> Path:
    return (Path(upload_dir) / PAPER_STAGING_DIRNAME).resolve()


def _paper_staging_job_dir(upload_dir: str | Path, job_id: str) -> Path:
    root = _paper_staging_root(upload_dir)
    staging_dir = (root / job_id).resolve()
    if staging_dir.parent != root:
        raise ValueError("invalid_paper_staging_job_dir")
    return staging_dir


def _save_upload_sync(
    file: UploadFile,
    staging_dir: Path,
    extension: str,
    max_upload_bytes: int,
    document_id: str,
) -> Path:
    _assert_paper_staging_job_dir(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    saved_path = staging_dir / f"{document_id.lower()}{extension}"
    total = 0
    with saved_path.open("wb") as target:
        while True:
            chunk = file.file.read(SAVE_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_upload_bytes:
                raise DocumentParseError("document_too_large") from None
            target.write(chunk)
    return saved_path


def _compute_sha256_sync(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(SAVE_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _cleanup_staging_dir(staging_dir: Path, *, reason: str) -> None:
    try:
        await asyncio.to_thread(_cleanup_staging_dir_sync, staging_dir)
    except Exception as exc:
        logger.error(
            "paper_staging_cleanup_failed: reason={} exception={}",
            reason,
            type(exc).__name__,
        )


def _cleanup_staging_dir_sync(staging_dir: Path) -> None:
    resolved = _assert_paper_staging_job_dir(staging_dir)
    if not resolved.exists():
        return
    if not resolved.is_dir():
        raise ValueError("invalid_paper_staging_job_dir")
    shutil.rmtree(resolved, ignore_errors=False)


def _assert_paper_staging_job_dir(staging_dir: Path) -> Path:
    resolved = staging_dir.resolve()
    if resolved.parent.name != PAPER_STAGING_DIRNAME or not resolved.name:
        raise ValueError("invalid_paper_staging_job_dir")
    return resolved


def _per_document_error_code(exc: Exception) -> str:
    if isinstance(exc, DocumentParseError):
        return "document_parse_failed"
    if isinstance(exc, PaperSpecGenerationError):
        return "paper_spec_generation_failed"
    return "document_processing_failed"
