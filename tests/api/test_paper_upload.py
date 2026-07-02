from __future__ import annotations

import uuid
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
    get_settings,
)
from api.main import create_app
from core.domain.exceptions import DocumentParseError, PaperSpecGenerationError, StoreError
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
from core.interfaces.document_parser import ParsedDocument, ParsedLocatorIndex
from core.interfaces.paper_cache import PaperBundleStore
from core.interfaces.paper_reparse_store import PaperReparseStore
from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL, MissingBindingModel


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
    ) -> PaperSpec:
        _ = parsed
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
    def __init__(self) -> None:
        self.calls: list[tuple[PaperSpec, str]] = []

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        uuid.UUID(paper_id)
        self.calls.append((spec, paper_id))
        return _plan(paper_id), [_missing_prompt()], [_missing_binding()]


class FakePaperBundleStore(PaperBundleStore, PaperReparseStore):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.records: dict[str, PaperPlanRecord] = {}
        self.sources: dict[str, PaperReparseSource] = {}
        self.deleted_ids: list[str] = []

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        if self.error is not None:
            raise self.error
        self.records[record.paper_id] = record

    async def save_ready_bundle_with_source(
        self,
        record: PaperPlanRecord,
        source: PaperReparseSource,
    ) -> None:
        if self.error is not None:
            raise self.error
        self.records[record.paper_id] = record
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
        return record.spec if record is not None else None

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        return self.records.get(paper_id)

    async def delete_bundle(self, paper_id: str) -> None:
        self.deleted_ids.append(paper_id)
        self.records.pop(paper_id, None)
        self.sources.pop(paper_id, None)

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
    assert "_cleanup_sandbox_dir_sync" in calls


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
    return app


def _post_document(client: TestClient, content: bytes, filename: str):
    return client.post(
        "/api/v1/upload-document",
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
