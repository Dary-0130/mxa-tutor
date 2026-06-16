from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.routes.paper_upload as paper_upload_module
from api.dependencies import get_paper_spec_service, get_settings
from api.main import create_app
from core.domain.exceptions import DocumentParseError, PaperSpecGenerationError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_spec import EquationEntry, PaperSpec, ParameterEntry


class FakePaperSpecService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.paths: list[Path] = []
        self.bytes_seen: list[bytes] = []

    async def extract(self, file_path: Path, paper_id: str) -> PaperSpec:
        uuid.UUID(paper_id)
        self.paths.append(file_path)
        self.bytes_seen.append(file_path.read_bytes())
        if self.error is not None:
            raise self.error
        return _paper_spec()


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
) -> Any:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_spec_service] = lambda: service
    return app


def _post_document(client: TestClient, content: bytes, filename: str):
    return client.post(
        "/api/v1/upload-document",
        files={"file": (filename, content, "application/octet-stream")},
    )


def _paper_spec() -> PaperSpec:
    evidence = PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
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
        abstract="报告描述同步电机短路实验参数。",
        equations=[EquationEntry("EQ-01", "H = 3.5", "S1")],
        parameter_table=[
            ParameterEntry("惯性常数", "H", "3.5", "s", EvidenceSource.DOCUMENT_EXTRACTED)
        ],
        figure_locations=[],
        pseudocode_blocks=[],
        evidence=[evidence],
    )
