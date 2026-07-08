from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.routes.paper_upload as paper_upload_module
from api.dependencies import (
    get_paper_bundle_store,
    get_paper_plan_service,
    get_paper_reparse_store,
    get_paper_spec_service,
    get_paper_upload_job_store,
    get_settings,
)
from api.main import create_app
from core.domain.exceptions import (
    DocumentParseError,
    PaperPlanGenerationError,
    PaperSpecGenerationError,
    StoreError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_reparse_source import PaperReparseSource
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry
from core.domain.paper_upload_job import (
    PaperUploadDocumentState,
    PaperUploadExecutionMode,
    PaperUploadJobDocument,
    PaperUploadJobRecord,
    PaperUploadJobState,
    PaperUploadStage,
    next_action_for_job,
)
from core.interfaces.document_parser import ParsedDocument, ParsedLocatorIndex
from core.interfaces.paper_cache import PaperBundleStore
from core.interfaces.paper_reparse_store import PaperReparseStore
from core.interfaces.paper_upload_job_store import PaperUploadJobStore
from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL, MissingBindingModel
from features.paper.structured_retry import (
    REASON_WALL_CLOCK_CAP_EXCEEDED,
    StructuredRetryContext,
)


class FakePaperSpecService:
    def __init__(
        self,
        error: Exception | None = None,
        errors_by_document_id: dict[str, Exception] | None = None,
    ) -> None:
        self.error = error
        self.errors_by_document_id = errors_by_document_id or {}
        self.paths: list[Path] = []
        self.bytes_seen: list[bytes] = []
        self.display_filenames: list[str | None] = []
        self.document_ids: list[str] = []

    async def extract(self, file_path: Path, paper_id: str) -> PaperSpec:
        return await self.extract_uncached(file_path, paper_id, display_filename=file_path.name)

    async def parse_uncached(self, file_path: Path) -> ParsedDocument:
        self.paths.append(file_path)
        self.bytes_seen.append(file_path.read_bytes())
        return _parsed_document(file_path)

    async def extract_parsed_uncached(
        self,
        parsed: ParsedDocument,
        paper_id: str,
        display_filename: str | None = None,
        document_id: str = "DOC-001",
        retry_context: object | None = None,
    ) -> PaperSpec:
        _ = parsed, retry_context
        uuid.UUID(paper_id)
        self.display_filenames.append(display_filename)
        self.document_ids.append(document_id)
        error = self.errors_by_document_id.get(document_id) or self.error
        if error is not None:
            raise error
        return _paper_spec(display_filename or "paper.pdf", document_id=document_id)

    async def extract_uncached(
        self,
        file_path: Path,
        paper_id: str,
        display_filename: str | None = None,
        document_id: str = "DOC-001",
    ) -> PaperSpec:
        parsed = await self.parse_uncached(file_path)
        return await self.extract_parsed_uncached(
            parsed,
            paper_id,
            display_filename=display_filename,
            document_id=document_id,
        )


class FakePaperPlanService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[PaperSpec, str]] = []

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
        retry_context: object | None = None,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        _ = retry_context
        uuid.UUID(paper_id)
        self.calls.append((spec, paper_id))
        if self.error is not None:
            raise self.error
        return _plan(paper_id), [_missing_prompt()], [_missing_binding()]


class FakePaperBundleStore(PaperBundleStore, PaperReparseStore, PaperUploadJobStore):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.records: dict[str, PaperPlanRecord] = {}
        self.specs: dict[str, PaperSpec] = {}
        self.sources: dict[str, PaperReparseSource] = {}
        self.deleted_ids: list[str] = []
        self.jobs: dict[str, PaperUploadJobRecord] = {}

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        if self.error is not None:
            raise self.error
        self.records[record.paper_id] = record
        self.specs[record.paper_id] = record.spec

    async def save_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        if self.error is not None:
            raise self.error
        self.records[record.paper_id] = record
        self.specs[record.paper_id] = record.spec
        self.sources[record.paper_id] = source

    async def replace_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        await self.save_ready_bundle_with_source(record, source)

    async def get_reparse_source(self, paper_id: str) -> PaperReparseSource | None:
        return self.sources.get(paper_id)

    async def delete_expired_paper_bundles(
        self,
        *,
        now: datetime | None = None,
        ttl_hours: int = 24,
    ) -> int:
        _ = now, ttl_hours
        return 0

    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        record = self.records.get(paper_id)
        return record.spec if record is not None else self.specs.get(paper_id)

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        return self.records.get(paper_id)

    async def put_spec(self, paper_id: str, spec: PaperSpec) -> None:
        if self.error is not None:
            raise self.error
        if paper_id in self.records:
            raise StoreError("paper_spec_overwrite_for_existing_plan")
        self.specs[paper_id] = spec

    async def set_plan(self, paper_id: str, record: PaperPlanRecord) -> None:
        if self.error is not None:
            raise self.error
        if paper_id not in self.specs:
            raise StoreError("paper_spec_missing_for_plan")
        self.records[paper_id] = record

    async def delete_bundle(self, paper_id: str) -> None:
        self.deleted_ids.append(paper_id)
        self.records.pop(paper_id, None)
        self.specs.pop(paper_id, None)
        self.sources.pop(paper_id, None)
        self.jobs.pop(paper_id, None)

    async def apply_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction: PaperParameterCorrection,
        *,
        is_recorrect: bool,
    ) -> None:
        _ = correction, is_recorrect
        self.records[paper_id] = updated_record

    async def undo_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction_id: str,
    ) -> None:
        _ = correction_id
        self.records[paper_id] = updated_record

    async def insert_parameter_correction(self, correction: PaperParameterCorrection) -> None:
        _ = correction

    async def update_parameter_correction_value(
        self,
        paper_id: str,
        correction_id: str,
        corrected_value: str,
        corrected_unit: str | None,
        updated_at: str,
    ) -> None:
        _ = paper_id, correction_id, corrected_value, corrected_unit, updated_at

    async def get_parameter_correction(
        self,
        paper_id: str,
        correction_id: str,
    ) -> PaperParameterCorrection | None:
        _ = paper_id, correction_id
        return None

    async def list_parameter_corrections(
        self,
        paper_id: str,
    ) -> list[PaperParameterCorrection]:
        _ = paper_id
        return []

    async def delete_parameter_correction(self, paper_id: str, correction_id: str) -> None:
        _ = paper_id, correction_id

    async def create_upload_job(
        self,
        *,
        job_id: str,
        paper_id: str,
        execution_mode: PaperUploadExecutionMode,
        document_ids: list[str],
        expires_at: datetime,
    ) -> PaperUploadJobRecord:
        now = datetime.utcnow()
        record = PaperUploadJobRecord(
            job_id=job_id,
            paper_id=paper_id,
            execution_mode=execution_mode,
            job_state="queued",
            stage="uploading",
            failed_stage=None,
            last_error_code=None,
            retryable=False,
            attempt_count=1,
            state_version=0,
            created_at=now,
            started_at=None,
            finished_at=None,
            expires_at=expires_at,
            documents=[
                PaperUploadJobDocument(
                    document_id=document_id,
                    upload_index=index,
                    status="pending",
                    error_code=None,
                    updated_at=now,
                )
                for index, document_id in enumerate(document_ids)
            ],
        )
        self.jobs[paper_id] = record
        return record

    async def get_upload_job(self, paper_id: str) -> PaperUploadJobRecord | None:
        return self.jobs.get(paper_id)

    async def get_upload_job_by_job_id(self, job_id: str) -> PaperUploadJobRecord | None:
        for record in self.jobs.values():
            if record.job_id == job_id:
                return record
        return None

    async def list_stale_upload_jobs(self) -> list[PaperUploadJobRecord]:
        return [
            record
            for record in self.jobs.values()
            if record.job_state in {"queued", "running", "plan_generating"}
        ]

    async def mark_upload_job_terminal(
        self,
        paper_id: str,
        *,
        job_state: PaperUploadJobState,
        stage: PaperUploadStage | None = None,
        failed_stage: PaperUploadStage | None = None,
        error_code: str | None = None,
        retryable: bool,
        finished_at: datetime | None = None,
    ) -> PaperUploadJobRecord:
        record = self.jobs[paper_id]
        updated = replace(
            record,
            job_state=job_state,
            stage=stage or record.stage,
            failed_stage=failed_stage,
            last_error_code=error_code,
            retryable=retryable,
            state_version=record.state_version + 1,
            started_at=record.started_at or datetime.utcnow(),
            finished_at=finished_at or datetime.utcnow(),
        )
        self.jobs[paper_id] = updated
        return updated

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
        record = self.jobs[paper_id]
        updated = PaperUploadJobRecord(
            job_id=record.job_id,
            paper_id=record.paper_id,
            execution_mode=record.execution_mode,
            job_state=job_state,
            stage=stage,
            failed_stage=failed_stage,
            last_error_code=error_code,
            retryable=retryable,
            attempt_count=record.attempt_count,
            state_version=record.state_version + 1,
            created_at=record.created_at,
            started_at=record.started_at or datetime.utcnow(),
            finished_at=finished_at,
            expires_at=record.expires_at,
            documents=record.documents,
        )
        self.jobs[paper_id] = updated
        return updated

    async def update_upload_document_state(
        self,
        paper_id: str,
        document_id: str,
        *,
        status: PaperUploadDocumentState,
        error_code: str | None = None,
    ) -> None:
        record = self.jobs[paper_id]
        documents = [
            PaperUploadJobDocument(
                document_id=document.document_id,
                upload_index=document.upload_index,
                status=status if document.document_id == document_id else document.status,
                error_code=error_code
                if document.document_id == document_id
                else document.error_code,
                updated_at=datetime.utcnow(),
            )
            for document in record.documents
        ]
        self.jobs[paper_id] = PaperUploadJobRecord(
            job_id=record.job_id,
            paper_id=record.paper_id,
            execution_mode=record.execution_mode,
            job_state=record.job_state,
            stage=record.stage,
            failed_stage=record.failed_stage,
            last_error_code=record.last_error_code,
            retryable=record.retryable,
            attempt_count=record.attempt_count,
            state_version=record.state_version,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            expires_at=record.expires_at,
            documents=documents,
        )

    async def try_start_rerun_plan(self, paper_id: str) -> PaperUploadJobRecord | None:
        record = self.jobs.get(paper_id)
        if record is None or record.job_state not in {
            "spec_ready",
            "plan_failed_retryable",
            "abandoned_plan_retryable",
        }:
            return None
        updated = PaperUploadJobRecord(
            job_id=record.job_id,
            paper_id=record.paper_id,
            execution_mode="rerun_plan",
            job_state="plan_generating",
            stage="generating_plan",
            failed_stage=None,
            last_error_code=None,
            retryable=False,
            attempt_count=record.attempt_count + 1,
            state_version=record.state_version + 1,
            created_at=record.created_at,
            started_at=datetime.utcnow(),
            finished_at=None,
            expires_at=record.expires_at,
            documents=record.documents,
        )
        self.jobs[paper_id] = updated
        return updated

    async def try_start_initial_plan(self, paper_id: str) -> PaperUploadJobRecord | None:
        record = self.jobs.get(paper_id)
        if record is None or record.job_state != "spec_ready":
            return None
        updated = replace(
            record,
            job_state="plan_generating",
            stage="generating_plan",
            failed_stage=None,
            last_error_code=None,
            retryable=False,
            state_version=record.state_version + 1,
            started_at=record.started_at or datetime.utcnow(),
            finished_at=None,
        )
        self.jobs[paper_id] = updated
        return updated


def test_upload_document_returns_200_with_paper_id_and_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"PK\x03\x04docx", "paper.docx")

    body = response.json()
    assert response.status_code == 200
    assert uuid.UUID(body["paper_id"]).version == 4
    assert body["spec"]["paper_title"] == "电机短路实验报告"
    assert body["spec"]["documents"][0]["filename"] == "paper.docx"
    assert service.display_filenames == ["paper.docx"]


def test_upload_response_contains_plan_and_missing_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch, FakePaperSpecService())

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    body = response.json()
    assert response.status_code == 200
    assert body["plan"]["plan_id"] == f"PLAN-{body['paper_id']}"
    assert body["plan"]["build_steps"] is None
    assert body["plan"]["build_guidance"] is None
    assert body["plan"]["guidance_status"] == "not_generated"
    assert body["missing_prompts"][0]["prompt_id"] == "MISS-1"
    assert "missing_bindings" not in body


def test_upload_writes_record_to_paper_bundle_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    paper_id = response.json()["paper_id"]
    record = bundle_store.records[paper_id]
    assert record.paper_id == paper_id
    assert record.plan.plan_id == f"PLAN-{paper_id}"
    assert record.missing_bindings == [_missing_binding()]
    source = bundle_store.sources[paper_id]
    assert [document.document_id for document in source.documents] == ["DOC-001"]
    assert source.documents[0].raw_text.startswith("%PDF-")
    assert source.documents[0].filename == "paper.pdf"
    assert not hasattr(source.documents[0], "file_path")


def test_upload_multiple_documents_fuses_one_spec_with_primary_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    plan_service = FakePaperPlanService()
    app = _create_app(tmp_path, monkeypatch, service, plan_service=plan_service)

    with TestClient(app) as client:
        response = _post_documents(
            client,
            [
                (b"%PDF-1.7\nmain", "main.pdf"),
                (b"%PDF-1.7\naux", "aux.pdf"),
            ],
            primary_index=1,
        )

    body = response.json()
    assert response.status_code == 200
    assert service.document_ids == ["DOC-001", "DOC-002"]
    assert body["spec"]["primary_document_id"] == "DOC-002"
    assert [document["document_id"] for document in body["spec"]["documents"]] == [
        "DOC-001",
        "DOC-002",
    ]
    assert [entry["document_id"] for entry in body["spec"]["equations"]] == [
        "DOC-001",
        "DOC-002",
    ]
    assert [status["status"] for status in body["document_statuses"]] == [
        "succeeded",
        "succeeded",
    ]
    assert plan_service.calls[0][0].primary_document_id == "DOC-002"


def test_upload_auxiliary_failure_keeps_doc_gap_and_reports_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService(
        errors_by_document_id={"DOC-002": DocumentParseError("parse_failed")}
    )
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_documents(
            client,
            [
                (b"%PDF-1.7\none", "one.pdf"),
                (b"%PDF-1.7\ntwo", "two.pdf"),
                (b"%PDF-1.7\nthree", "three.pdf"),
            ],
        )

    body = response.json()
    assert response.status_code == 200
    assert [document["document_id"] for document in body["spec"]["documents"]] == [
        "DOC-001",
        "DOC-003",
    ]
    assert body["spec"]["primary_document_id"] is None
    assert [(item["document_id"], item["status"]) for item in body["document_statuses"]] == [
        ("DOC-001", "succeeded"),
        ("DOC-002", "failed"),
        ("DOC-003", "succeeded"),
    ]
    assert body["document_statuses"][1]["error_code"] == "document_parse_failed"


def test_upload_auxiliary_failure_does_not_store_failed_document_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService(
        errors_by_document_id={"DOC-002": PaperSpecGenerationError("bad_json")}
    )
    bundle_store = FakePaperBundleStore()
    app = _create_app(tmp_path, monkeypatch, service, bundle_store=bundle_store)

    with TestClient(app) as client:
        response = _post_documents(
            client,
            [
                (b"%PDF-1.7\none", "one.pdf"),
                (b"%PDF-1.7\ntwo", "two.pdf"),
                (b"%PDF-1.7\nthree", "three.pdf"),
            ],
        )

    paper_id = response.json()["paper_id"]
    assert response.status_code == 200
    assert [document.document_id for document in bundle_store.sources[paper_id].documents] == [
        "DOC-001",
        "DOC-003",
    ]


def test_upload_primary_document_failure_fails_whole_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService(
        errors_by_document_id={"DOC-002": DocumentParseError("parse_failed")}
    )
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_documents(
            client,
            [
                (b"%PDF-1.7\none", "one.pdf"),
                (b"%PDF-1.7\ntwo", "two.pdf"),
            ],
            primary_index=1,
        )

    assert response.status_code == 400
    assert response.json()["error"] == "document_parse_failed"


def test_upload_rejects_primary_index_out_of_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch, FakePaperSpecService())

    with TestClient(app) as client:
        response = _post_documents(
            client,
            [(b"%PDF-1.7\none", "one.pdf")],
            primary_index=1,
        )

    assert response.status_code == 400
    assert response.json()["error"] == "document_parse_failed"


def test_upload_store_failure_does_not_run_application_compensation_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore(StoreError("sqlite_operation_failed"))
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 500
    assert response.json()["error"] == "store_error"
    assert bundle_store.records == {}
    assert bundle_store.deleted_ids == []


def test_upload_plan_failure_keeps_spec_and_status_allows_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        plan_service=FakePaperPlanService(PaperPlanGenerationError("bad_plan")),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        upload_response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")
        paper_id = upload_response.json()["paper_id"]
        status_response = client.get(f"/api/v1/papers/{paper_id}/status")

    assert upload_response.status_code == 502
    assert upload_response.json()["error"] == "paper_plan_generation_failed"
    assert "reason_code" not in upload_response.json()
    assert "paper_id" in upload_response.json()
    assert paper_id in bundle_store.specs
    assert paper_id not in bundle_store.records
    status_body = status_response.json()
    assert status_response.status_code == 200
    assert status_body["job_state"] == "plan_failed_retryable"
    assert status_body["failed_stage"] == "generating_plan"
    assert "reason_code" not in status_body
    assert status_body["error_code"] == "paper_plan_generation_failed"
    assert status_body["next_action"] == "rerun_plan"
    assert status_body["documents"] == [
        {"document_id": "DOC-001", "status": "succeeded", "error_code": None}
    ]


def test_rerun_plan_recovers_from_spec_only_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        plan_service=FakePaperPlanService(PaperPlanGenerationError("bad_plan")),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        upload_response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")
        paper_id = upload_response.json()["paper_id"]
        app.dependency_overrides[get_paper_plan_service] = lambda: FakePaperPlanService()
        rerun_response = client.post(f"/api/v1/papers/{paper_id}/rerun-plan", json={})
        status_response = client.get(f"/api/v1/papers/{paper_id}/status")

    assert rerun_response.status_code == 200
    assert rerun_response.json()["paper_id"] == paper_id
    assert rerun_response.json()["job_state"] == "ready"
    assert bundle_store.records[paper_id].plan.plan_id == f"PLAN-{paper_id}"
    assert status_response.json()["job_state"] == "ready"
    assert status_response.json()["next_action"] == "open_result"
    assert bundle_store.jobs[paper_id].attempt_count == 2


def test_upload_async_returns_202_and_background_reaches_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        response = _post_document_async(client, b"%PDF-1.7\n", "paper.pdf")
        body = response.json()
        status_response = client.get(f"/api/v1/papers/{body['paper_id']}/status")

    assert response.status_code == 202
    assert uuid.UUID(body["paper_id"]).version == 4
    assert body["job_id"].startswith("PUJ-")
    status_body = status_response.json()
    assert status_body["execution_mode"] == "async"
    assert status_body["job_state"] == "ready"
    assert status_body["stage"] == "done"
    assert status_body["next_action"] == "open_result"
    assert status_body["job_id"] == body["job_id"]


def test_startup_sweep_repairs_plan_persisted_ready_mark_crash(
    tmp_path: Path,
) -> None:
    bundle_store = FakePaperBundleStore()
    upload_dir = tmp_path / "uploads"
    paper_id = "paper-ready-crash"
    job_id = "PUJ-ready-crash"
    bundle_store.records[paper_id] = PaperPlanRecord(
        paper_id=paper_id,
        spec=_paper_spec("paper.pdf"),
        plan=_plan(paper_id),
        missing_prompts=[_missing_prompt()],
        missing_bindings=[_missing_binding()],
    )
    bundle_store.specs[paper_id] = bundle_store.records[paper_id].spec
    bundle_store.jobs[paper_id] = _job_record(
        paper_id=paper_id,
        job_id=job_id,
        job_state="plan_generating",
        stage="persisting_plan",
    )
    staging_dir = upload_dir / "paper_staging" / job_id
    staging_dir.mkdir(parents=True)
    (staging_dir / "doc.pdf").write_bytes(b"%PDF-1.7\n")

    swept = asyncio.run(
        paper_upload_module.sweep_stale_paper_upload_jobs(
            upload_dir=upload_dir,
            bundle_store=bundle_store,
            job_store=bundle_store,
        )
    )

    record = bundle_store.jobs[paper_id]
    assert swept == 1
    assert record.job_state == "ready"
    assert record.stage == "done"
    assert record.finished_at is not None
    assert not staging_dir.exists()


def test_startup_sweep_spec_only_abandoned_can_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    upload_dir = tmp_path / "uploads"
    paper_id = str(uuid.uuid4())
    job_id = "PUJ-spec-only"
    bundle_store.specs[paper_id] = _paper_spec("paper.pdf")
    bundle_store.jobs[paper_id] = _job_record(
        paper_id=paper_id,
        job_id=job_id,
        job_state="plan_generating",
        stage="generating_plan",
    )
    staging_dir = upload_dir / "paper_staging" / job_id
    staging_dir.mkdir(parents=True)
    (staging_dir / "doc.pdf").write_bytes(b"%PDF-1.7\n")

    asyncio.run(
        paper_upload_module.sweep_stale_paper_upload_jobs(
            upload_dir=upload_dir,
            bundle_store=bundle_store,
            job_store=bundle_store,
        )
    )

    swept_record = bundle_store.jobs[paper_id]
    assert swept_record.job_state == "abandoned_plan_retryable"
    assert swept_record.stage == "generating_plan"
    assert next_action_for_job(swept_record) == "rerun_plan"
    assert not staging_dir.exists()

    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )
    with TestClient(app) as client:
        status_before = client.get(f"/api/v1/papers/{paper_id}/status")
        rerun_response = client.post(f"/api/v1/papers/{paper_id}/rerun-plan", json={})
        status_after = client.get(f"/api/v1/papers/{paper_id}/status")

    assert status_before.json()["next_action"] == "rerun_plan"
    assert rerun_response.status_code == 200
    assert status_after.json()["job_state"] == "ready"
    assert bundle_store.jobs[paper_id].attempt_count == 2


def test_startup_sweep_queued_without_spec_requires_reupload_and_cleans_staging(
    tmp_path: Path,
) -> None:
    bundle_store = FakePaperBundleStore()
    upload_dir = tmp_path / "uploads"
    paper_id = "paper-queued-crash"
    job_id = "PUJ-queued-crash"
    bundle_store.jobs[paper_id] = _job_record(
        paper_id=paper_id,
        job_id=job_id,
        job_state="queued",
        stage="uploading",
    )
    staging_dir = upload_dir / "paper_staging" / job_id
    staging_dir.mkdir(parents=True)
    (staging_dir / "doc.pdf").write_bytes(b"%PDF-1.7\n")

    asyncio.run(
        paper_upload_module.sweep_stale_paper_upload_jobs(
            upload_dir=upload_dir,
            bundle_store=bundle_store,
            job_store=bundle_store,
        )
    )

    record = bundle_store.jobs[paper_id]
    assert record.job_state == "abandoned_reupload_required"
    assert record.stage == "uploading"
    assert record.retryable is False
    assert next_action_for_job(record) == "reupload"
    assert not staging_dir.exists()


def test_initial_plan_generation_uses_same_lock_as_rerun(
    tmp_path: Path,
) -> None:
    bundle_store = FakePaperBundleStore()
    plan_service = FakePaperPlanService()
    paper_id = "paper-lock-busy"
    job_id = "PUJ-lock-busy"
    spec = _paper_spec("paper.pdf")
    bundle_store.specs[paper_id] = spec
    bundle_store.jobs[paper_id] = _job_record(
        paper_id=paper_id,
        job_id=job_id,
        job_state="spec_ready",
        stage="persisting_spec",
        retryable=True,
    )

    async def run_busy_lock_case():
        registry = paper_upload_module.PaperReparseLockRegistry()
        token = await registry.acquire(paper_id)
        try:
            return await paper_upload_module._run_initial_plan_generation(
                paper_id=paper_id,
                job_id=job_id,
                spec=spec,
                plan_service=plan_service,
                bundle_store=bundle_store,
                reparse_store=bundle_store,
                job_store=bundle_store,
                lock_registry=registry,
                source=None,
            )
        finally:
            await token.__aexit__(None, None, None)

    result = asyncio.run(run_busy_lock_case())

    assert isinstance(result, paper_upload_module._UploadFailure)
    assert result.error_code == "plan_generation_in_progress"
    assert plan_service.calls == []
    assert bundle_store.jobs[paper_id].job_state == "plan_failed_retryable"


def test_plan_wall_clock_cap_marks_retryable_releases_lock_and_keeps_no_partial_bundle(
    tmp_path: Path,
) -> None:
    bundle_store = FakePaperBundleStore()
    paper_id = str(uuid.uuid4())
    job_id = "PUJ-wall-clock"
    spec = _paper_spec("paper.pdf")
    bundle_store.specs[paper_id] = spec
    bundle_store.jobs[paper_id] = _job_record(
        paper_id=paper_id,
        job_id=job_id,
        job_state="spec_ready",
        stage="persisting_spec",
        retryable=True,
    )
    plan_service = FakePaperPlanService(
        PaperPlanGenerationError(
            "cap",
            reason_code=REASON_WALL_CLOCK_CAP_EXCEEDED,
            leaf="plan_composer",
        )
    )
    registry = paper_upload_module.PaperReparseLockRegistry()

    async def run_case():
        result = await paper_upload_module._run_initial_plan_generation(
            paper_id=paper_id,
            job_id=job_id,
            spec=spec,
            plan_service=plan_service,
            bundle_store=bundle_store,
            reparse_store=bundle_store,
            job_store=bundle_store,
            lock_registry=registry,
            source=None,
            retry_context=StructuredRetryContext(wall_clock_seconds=0.01),
        )
        async with await registry.acquire(paper_id):
            return result

    result = asyncio.run(run_case())

    assert isinstance(result, paper_upload_module._UploadFailure)
    assert result.error_code == "paper_plan_generation_failed"
    assert bundle_store.jobs[paper_id].job_state == "plan_failed_retryable"
    assert bundle_store.jobs[paper_id].failed_stage == "generating_plan"
    assert paper_id not in bundle_store.records


def test_rerun_plan_rejects_ready_state_with_cas_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        upload_response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")
        paper_id = upload_response.json()["paper_id"]
        rerun_response = client.post(f"/api/v1/papers/{paper_id}/rerun-plan", json={})

    assert upload_response.status_code == 200
    assert rerun_response.status_code == 409
    assert rerun_response.json()["error"] == "rerun_plan_unavailable"


def test_status_expired_returns_410_without_content_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_store = FakePaperBundleStore()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        bundle_store=bundle_store,
    )

    with TestClient(app) as client:
        upload_response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")
        paper_id = upload_response.json()["paper_id"]
        bundle_store.jobs[paper_id] = replace(
            bundle_store.jobs[paper_id],
            expires_at=datetime(2026, 1, 1, 0, 0, 0),
        )
        status_response = client.get(f"/api/v1/papers/{paper_id}/status")

    assert status_response.status_code == 410
    assert status_response.json() == {
        "error": "paper_expired",
        "message": "这份资料已过期,请重新上传",
        "paper_id": paper_id,
        "job_id": bundle_store.jobs[paper_id].job_id,
    }


def test_upload_calls_plan_service_with_injected_paper_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_service = FakePaperPlanService()
    app = _create_app(
        tmp_path,
        monkeypatch,
        FakePaperSpecService(),
        plan_service=plan_service,
    )

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    paper_id = response.json()["paper_id"]
    assert plan_service.calls
    assert plan_service.calls[0][1] == paper_id


def test_upload_document_rejects_magic_extension_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch, FakePaperSpecService())

    with TestClient(app) as client:
        response = _post_document(client, b"PK\x03\x04docx", "paper.pdf")

    assert response.status_code == 400
    assert response.json()["error"] == "document_parse_failed"


def test_upload_document_removes_temp_file_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 200
    assert service.paths
    assert not service.paths[0].parent.exists()


def test_upload_document_removes_temp_file_on_parse_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService(error=DocumentParseError("parse_failed"))
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 400
    assert service.paths
    assert not service.paths[0].parent.exists()


def test_upload_document_removes_temp_file_on_llm_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService(error=PaperSpecGenerationError("bad_json"))
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 502
    assert service.paths
    assert not service.paths[0].parent.exists()


def test_upload_document_temp_path_does_not_include_original_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "secret_user_filename.pdf")

    assert response.status_code == 200
    assert "secret_user_filename" not in str(service.paths[0])
    assert service.paths[0].parent.name.startswith("PUJ-")
    assert service.paths[0].parent.parent.name == "paper_staging"


def test_upload_document_preserves_magic_prefix_after_sniffing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\nbody", "paper.pdf")

    assert response.status_code == 200
    assert service.bytes_seen[0].startswith(b"%PDF-")


def test_upload_removes_staging_before_plan_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()

    class StagingAwarePlanService(FakePaperPlanService):
        async def generate(
            self,
            spec: PaperSpec,
            paper_id: str,
            retry_context: object | None = None,
        ):
            _ = retry_context
            assert service.paths
            assert not service.paths[0].parent.exists()
            return await super().generate(spec, paper_id)

    app = _create_app(
        tmp_path,
        monkeypatch,
        service,
        plan_service=StagingAwarePlanService(),
    )

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 200


def test_upload_request_bail_removes_created_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_app(tmp_path, monkeypatch, FakePaperSpecService())

    def fail_after_creating_staging(
        _file: object,
        staging_dir: Path,
        _extension: str,
        _max_upload_bytes: int,
        _document_id: str,
    ) -> Path:
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "leftover.tmp").write_text("temporary", encoding="utf-8")
        raise DocumentParseError("document_too_large") from None

    monkeypatch.setattr(paper_upload_module, "_save_upload_sync", fail_after_creating_staging)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    staging_root = tmp_path / "uploads" / "paper_staging"
    assert response.status_code == 400
    assert response.json()["error"] == "document_parse_failed"
    assert not any(staging_root.iterdir())


def test_upload_staging_cleanup_failure_does_not_mask_ready_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)
    logged_errors: list[tuple[str, tuple[object, ...]]] = []

    def fail_cleanup(_staging_dir: Path) -> None:
        raise RuntimeError("secret path should not appear") from None

    def capture_error(message: str, *args: object, **_kwargs: object) -> None:
        logged_errors.append((message, args))

    monkeypatch.setattr(paper_upload_module, "_cleanup_staging_dir_sync", fail_cleanup)
    mocker.patch.object(paper_upload_module.logger, "error", side_effect=capture_error)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 200
    assert response.json()["plan"]["plan_id"] == f"PLAN-{response.json()['paper_id']}"
    assert logged_errors == [
        (
            "paper_staging_cleanup_failed: reason={} exception={}",
            ("orchestrator_documents_done", "RuntimeError"),
        )
    ]


def test_upload_document_uses_to_thread_for_save_hash_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePaperSpecService()
    app = _create_app(tmp_path, monkeypatch, service)
    calls: list[str] = []

    async def fake_to_thread(function: object, *args: object, **kwargs: object) -> object:
        calls.append(getattr(function, "__name__", function.__class__.__name__))
        return function(*args, **kwargs)  # type: ignore[misc]

    monkeypatch.setattr(paper_upload_module.asyncio, "to_thread", fake_to_thread)

    with TestClient(app) as client:
        response = _post_document(client, b"%PDF-1.7\n", "paper.pdf")

    assert response.status_code == 200
    assert "_save_upload_sync" in calls
    assert "_compute_sha256_sync" in calls
    assert "_cleanup_staging_dir_sync" in calls


def _create_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    service: FakePaperSpecService,
    *,
    plan_service: FakePaperPlanService | None = None,
    bundle_store: FakePaperBundleStore | None = None,
) -> Any:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_paper_spec_service] = lambda: service
    app.dependency_overrides[get_paper_plan_service] = (
        lambda: plan_service or FakePaperPlanService()
    )
    app.dependency_overrides[get_paper_bundle_store] = (
        lambda: bundle_store or FakePaperBundleStore()
    )
    app.dependency_overrides[get_paper_reparse_store] = (
        lambda: bundle_store or FakePaperBundleStore()
    )
    app.dependency_overrides[get_paper_upload_job_store] = (
        lambda: bundle_store or FakePaperBundleStore()
    )
    return app


@asynccontextmanager
async def _noop_lifespan(_app: Any):
    yield


def _post_document(client: TestClient, content: bytes, filename: str):
    return client.post(
        "/api/v1/upload-document",
        files={"file": (filename, content, "application/octet-stream")},
    )


def _post_document_async(client: TestClient, content: bytes, filename: str):
    return client.post(
        "/api/v1/upload-async",
        files={"file": (filename, content, "application/octet-stream")},
    )


def _post_documents(
    client: TestClient,
    documents: list[tuple[bytes, str]],
    *,
    primary_index: int | None = None,
):
    data = {}
    if primary_index is not None:
        data["primary_index"] = str(primary_index)
    return client.post(
        "/api/v1/upload-document",
        data=data,
        files=[
            ("file", (filename, content, "application/octet-stream"))
            for content, filename in documents
        ],
    )


def _job_record(
    *,
    paper_id: str,
    job_id: str,
    job_state: PaperUploadJobState,
    stage: PaperUploadStage,
    execution_mode: PaperUploadExecutionMode = "async",
    failed_stage: PaperUploadStage | None = None,
    error_code: str | None = None,
    retryable: bool = False,
) -> PaperUploadJobRecord:
    now = datetime.utcnow()
    return PaperUploadJobRecord(
        job_id=job_id,
        paper_id=paper_id,
        execution_mode=execution_mode,
        job_state=job_state,
        stage=stage,
        failed_stage=failed_stage,
        last_error_code=error_code,
        retryable=retryable,
        attempt_count=1,
        state_version=0,
        created_at=now,
        started_at=now if job_state != "queued" else None,
        finished_at=None,
        expires_at=now.replace(year=now.year + 1),
        documents=[
            PaperUploadJobDocument(
                document_id="DOC-001",
                upload_index=0,
                status="pending",
                error_code=None,
                updated_at=now,
            )
        ],
    )


def _paper_spec(filename: str = "paper.pdf", *, document_id: str = "DOC-001") -> PaperSpec:
    evidence = PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=document_id,
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="报告给出了惯性常数和短路公式。",
        missing_param_prompt_id=None,
    )
    return PaperSpec(
        paper_title="电机短路实验报告",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id=document_id, filename=filename)],
        primary_document_id=None,
        abstract="报告描述同步电机短路实验参数。",
        equations=[EquationEntry("EQ-01", "H = 3.5", "S1", document_id)],
        parameter_table=[
            ParameterEntry(
                name="惯性常数",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id=document_id,
            )
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _parsed_document(file_path: Path) -> ParsedDocument:
    return ParsedDocument(
        raw_text=file_path.read_text(encoding="utf-8", errors="ignore"),
        page_count=1,
        figure_placeholders=[],
        table_placeholders=[],
        locator_index=ParsedLocatorIndex(
            section_ids=["S1"],
            equation_ids=["EQ-01"],
            figure_ids=[],
        ),
        file_hash="hash",
        extracted_at=datetime.utcnow(),
    )


def _plan(paper_id: str) -> ModelGenerationPlan:
    evidence = _document_evidence()
    return ModelGenerationPlan(
        plan_id=f"PLAN-{paper_id}",
        paper_spec_id=paper_id,
        library_choice="SimPowerSystems",
        block_recommendations=[
            BlockRecommendation(
                block_type="Synchronous Machine",
                purpose="Model the generator.",
                paper_reference=evidence,
            )
        ],
        parameter_mapping=[
            ParameterMapping(
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
                value=MISSING_VALUE_SENTINEL,
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=[evidence],
    )


def _missing_prompt() -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id="MISS-1",
        parameter_name="H",
        paper_reference=_document_evidence(),
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
    )


def _missing_binding() -> MissingBindingModel:
    return MissingBindingModel(
        prompt_id="MISS-1",
        paper_param_name="H",
        model_param_name="Synchronous Machine.H",
    )


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="报告给出了惯性常数和短路公式。",
        missing_param_prompt_id=None,
    )
