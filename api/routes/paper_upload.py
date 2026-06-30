"""Paper document upload endpoint."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from loguru import logger
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_paper_bundle_store,
    get_paper_plan_service,
    get_paper_spec_service,
    get_settings,
)
from app.config import AppSettings
from core.domain.exceptions import DocumentParseError
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

router = APIRouter(tags=["paper"])


class UploadDocumentResponse(BaseModel):
    """POST /api/v1/upload-document response model."""

    paper_id: str
    spec: PaperSpecModel
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    model_config = ConfigDict(extra="forbid")


@router.post("/api/v1/upload-document", response_model=UploadDocumentResponse)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    service: Annotated[PaperSpecService, Depends(get_paper_spec_service)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> UploadDocumentResponse:
    """Upload a PDF/docx paper and return generated PaperSpec + baseline plan."""
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024
    _validate_declared_size(file.size, max_upload_bytes)
    sandbox_dir = await asyncio.to_thread(_create_sandbox_dir_sync)
    try:
        header = await file.read(8192)
        extension = _validate_magic_and_extension(header, file.filename)
        display_filename = sanitize_paper_display_filename(file.filename)
        await file.seek(0)
        saved_path = await asyncio.to_thread(
            _save_upload_sync,
            file,
            sandbox_dir,
            extension,
            max_upload_bytes,
        )
        file_hash = await asyncio.to_thread(_compute_sha256_sync, saved_path)
        file_size = saved_path.stat().st_size
        logger.info(
            "paper_document_upload_accepted: file_size={} file_hash={} extension={}",
            file_size,
            file_hash,
            extension,
        )
        paper_id = str(uuid.uuid4())
        spec = await service.extract_uncached(
            saved_path,
            paper_id,
            display_filename=display_filename,
        )
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
        )
    finally:
        await asyncio.to_thread(_cleanup_sandbox_dir_sync, sandbox_dir)


def _validate_declared_size(size: int | None, max_upload_bytes: int) -> None:
    if size is not None and size > max_upload_bytes:
        raise DocumentParseError("document_too_large") from None


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
) -> Path:
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    saved_path = sandbox_dir / f"upload{extension}"
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
