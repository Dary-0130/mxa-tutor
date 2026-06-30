"""Paper document upload endpoint."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from loguru import logger
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_paper_bundle_store,
    get_paper_plan_service,
    get_paper_spec_service,
    get_settings,
)
from app.config import AppSettings
from core.domain.exceptions import DocumentParseError, PaperSpecGenerationError
from core.domain.paper_document_identity import validate_paper_spec_document_identity
from core.domain.paper_spec import PaperSpec
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_document_identity import sanitize_paper_display_filename
from features.paper.paper_plan_cache import PaperPlanRecord
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)
from features.paper.paper_spec_service import PaperSpecService

PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"
SAVE_CHUNK_SIZE = 1024 * 1024
MAX_PAPER_UPLOAD_FILES = 5

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
class _SuccessfulUpload:
    upload_index: int
    document_id: str
    filename: str
    spec: PaperSpec


@router.post("/api/v1/upload-document", response_model=UploadDocumentResponse)
async def upload_document(
    file: Annotated[list[UploadFile], File(...)],
    service: Annotated[PaperSpecService, Depends(get_paper_spec_service)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    primary_index: Annotated[int | None, Form()] = None,
) -> UploadDocumentResponse:
    """Upload a PDF/docx paper and return generated PaperSpec + baseline plan."""
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024
    files = list(file)
    _validate_file_count(files)
    _validate_primary_index(primary_index, len(files))
    sandbox_dir = await asyncio.to_thread(_create_sandbox_dir_sync)
    paper_id = str(uuid.uuid4())
    successes: list[_SuccessfulUpload] = []
    document_statuses: list[UploadDocumentStatusModel] = []
    first_error: Exception | None = None
    try:
        for upload_index, upload_file in enumerate(files):
            document_id = _document_id_for_upload_index(upload_index)
            display_filename = sanitize_paper_display_filename(upload_file.filename)
            try:
                _validate_declared_size(upload_file.size, max_upload_bytes)
                header = await upload_file.read(8192)
                extension = _validate_magic_and_extension(header, upload_file.filename)
                await upload_file.seek(0)
                saved_path = await asyncio.to_thread(
                    _save_upload_sync,
                    upload_file,
                    sandbox_dir,
                    extension,
                    max_upload_bytes,
                    document_id,
                )
                file_hash = await asyncio.to_thread(_compute_sha256_sync, saved_path)
                file_size = saved_path.stat().st_size
                logger.info(
                    "paper_document_upload_accepted: document_id={} file_size={} "
                    "file_hash={} extension={}",
                    document_id,
                    file_size,
                    file_hash,
                    extension,
                )
                spec = await service.extract_uncached(
                    saved_path,
                    paper_id,
                    display_filename=display_filename,
                    document_id=document_id,
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
                if primary_index == upload_index:
                    raise
                continue

            successes.append(
                _SuccessfulUpload(
                    upload_index=upload_index,
                    document_id=document_id,
                    filename=display_filename,
                    spec=spec,
                )
            )
            document_statuses.append(
                UploadDocumentStatusModel(
                    document_id=document_id,
                    filename=display_filename,
                    status="succeeded",
                    error_code=None,
                )
            )

        if not successes:
            if first_error is not None:
                raise first_error
            raise DocumentParseError("document_parse_failed") from None

        spec = _fuse_successful_specs(successes, primary_index)
        plan, missing_prompts, missing_bindings = await plan_service.generate(spec, paper_id)
        record = PaperPlanRecord(
            paper_id=paper_id,
            spec=spec,
            plan=plan,
            missing_prompts=missing_prompts,
            missing_bindings=missing_bindings,
        )
        await bundle_store.save_ready_bundle(record)
        return UploadDocumentResponse(
            paper_id=paper_id,
            spec=PaperSpecModel.from_domain(spec),
            plan=ModelGenerationPlanModel.from_domain(plan),
            missing_prompts=[
                MissingParameterPromptModel.from_domain(prompt) for prompt in missing_prompts
            ],
            document_statuses=document_statuses,
        )
    finally:
        await asyncio.to_thread(_cleanup_sandbox_dir_sync, sandbox_dir)


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


def _create_sandbox_dir_sync() -> Path:
    return Path(tempfile.mkdtemp(prefix="mxa_paper_sandbox_")).resolve()


def _save_upload_sync(
    file: UploadFile,
    sandbox_dir: Path,
    extension: str,
    max_upload_bytes: int,
    document_id: str,
) -> Path:
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    saved_path = sandbox_dir / f"{document_id.lower()}{extension}"
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


def _cleanup_sandbox_dir_sync(sandbox_dir: Path) -> None:
    shutil.rmtree(sandbox_dir, ignore_errors=True)


def _document_id_for_upload_index(index: int) -> str:
    return f"DOC-{index + 1:03d}"


def _per_document_error_code(exc: Exception) -> str:
    if isinstance(exc, DocumentParseError):
        return "document_parse_failed"
    if isinstance(exc, PaperSpecGenerationError):
        return "paper_spec_generation_failed"
    return "document_processing_failed"


def _fuse_successful_specs(
    successes: list[_SuccessfulUpload],
    primary_index: int | None,
) -> PaperSpec:
    representative = _representative_success(successes, primary_index)
    primary_document_id = representative.document_id if primary_index is not None else None
    spec = PaperSpec(
        paper_title=representative.spec.paper_title,
        paper_type=representative.spec.paper_type,
        domain=representative.spec.domain,
        documents=[
            document
            for success in successes
            for document in success.spec.documents
            if document.document_id == success.document_id
        ],
        primary_document_id=primary_document_id,
        abstract=representative.spec.abstract,
        equations=[equation for success in successes for equation in success.spec.equations],
        parameter_table=[
            parameter for success in successes for parameter in success.spec.parameter_table
        ],
        figure_locations=[
            figure for success in successes for figure in success.spec.figure_locations
        ],
        pseudocode_blocks=[
            block for success in successes for block in success.spec.pseudocode_blocks
        ],
        evidence=[entry for success in successes for entry in success.spec.evidence],
    )
    validate_paper_spec_document_identity(spec)
    return spec


def _representative_success(
    successes: list[_SuccessfulUpload],
    primary_index: int | None,
) -> _SuccessfulUpload:
    if primary_index is None:
        return successes[0]
    for success in successes:
        if success.upload_index == primary_index:
            return success
    raise DocumentParseError("primary_document_failed") from None
