import asyncio
import io
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from adapters.storage.in_memory_project_store import InMemoryProjectStore
from api.dependencies import get_project_store, get_settings
from api.schemas.upload import ProjectStatusResponse, UploadResponse
from core.domain.project import Project, ProjectType


def _create_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from api.main import create_app

    return create_app()


def _zip_bytes(entries: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def _post_zip(client: TestClient, zip_bytes: bytes, filename: str = "demo.zip"):
    return client.post(
        "/upload",
        files={"file": (filename, zip_bytes, "application/zip")},
    )


def _project(project_id: str) -> Project:
    return Project(
        id=project_id,
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


def test_post_upload_returns_202_with_project_id_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = _post_zip(client, _zip_bytes({"main.m": "disp('ok');"}))

    body = response.json()
    assert response.status_code == 202
    assert uuid.UUID(body["project_id"]).version == 4
    assert body["status"] == "parsing"


def test_post_upload_declared_size_too_large_returns_413_without_reading_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch, MAX_UPLOAD_SIZE_MB="1")

    with TestClient(app) as client:
        response = _post_zip(client, b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["error"] == "project_too_large"


def test_post_upload_actual_size_too_large_returns_413(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch, MAX_UPLOAD_SIZE_MB="1")

    with TestClient(app) as client:
        response = _post_zip(client, b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["error"] == "project_too_large"


def test_post_upload_uuid_format_is_uuid4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = _post_zip(client, _zip_bytes({"main.m": "disp('ok');"}))

    assert uuid.UUID(response.json()["project_id"]).version == 4


def test_get_status_returns_parsing_initially_with_pending_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryProjectStore()
    project_id = str(uuid.uuid4())
    asyncio.run(store.create_pending(project_id, "demo.zip"))
    app = _create_app(tmp_path, monkeypatch)
    app.dependency_overrides[get_project_store] = lambda: store

    with TestClient(app) as client:
        response = client.get(f"/projects/{project_id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "parsing"


def test_get_status_returns_ready_after_background_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        upload_response = _post_zip(client, _zip_bytes({"main.m": "disp('ok');"}))
        project_id = upload_response.json()["project_id"]
        status_response = client.get(f"/projects/{project_id}/status")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"


def test_get_status_returns_failed_with_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryProjectStore()
    project_id = str(uuid.uuid4())
    asyncio.run(store.create_pending(project_id, "demo.zip"))
    asyncio.run(store.mark_failed(project_id, "parse_error"))
    app = _create_app(tmp_path, monkeypatch)
    app.dependency_overrides[get_project_store] = lambda: store

    with TestClient(app) as client:
        response = client.get(f"/projects/{project_id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "parse_error"


def test_get_status_missing_returns_404_with_locked_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.get(f"/projects/{uuid.uuid4()}/status")

    assert response.status_code == 404
    assert response.json() == {
        "error": "project_not_found",
        "message": "没有找到这个工程,可能已过期或已被删除,请重新上传",
    }


def test_get_status_response_includes_created_at_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        upload_response = _post_zip(client, _zip_bytes({"main.m": "disp('ok');"}))
        project_id = upload_response.json()["project_id"]
        status_response = client.get(f"/projects/{project_id}/status")

    body = status_response.json()
    assert set(body) == {"project_id", "name", "status", "created_at", "error_code"}
    assert body["created_at"]


def test_upload_response_extra_forbid_enforced() -> None:
    with pytest.raises(ValidationError):
        UploadResponse(project_id="p1", status="parsing", extra="x")


def test_status_response_extra_forbid_enforced() -> None:
    with pytest.raises(ValidationError):
        ProjectStatusResponse(
            project_id="p1",
            name="demo.zip",
            status="ready",
            created_at=datetime.utcnow(),
            extra="x",
        )


def test_status_response_error_code_within_known_literals() -> None:
    response = ProjectStatusResponse(
        project_id="p1",
        name="demo.zip",
        status="failed",
        created_at=datetime.utcnow(),
        error_code="parse_error",
    )
    assert response.error_code == "parse_error"


def test_testclient_waits_for_background_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        upload_response = _post_zip(client, _zip_bytes({"main.m": "disp('ok');"}))
        project_id = upload_response.json()["project_id"]
        response = client.get(f"/projects/{project_id}/status")

    assert response.json()["status"] == "ready"


@pytest.mark.parametrize(
    ("zip_bytes", "error_code"),
    [
        (_zip_bytes({"model.m": b"0" * (2 * 1024 * 1024)}), "zip_bomb"),
        (_zip_bytes({"../escape.m": "disp('escape');"}), "zip_slip"),
        (_zip_bytes({"native/evil.exe": b"MZ"}), "file_type_not_allowed"),
        (_zip_bytes({"huge.m": b"0" * (21 * 1024 * 1024)}), "project_too_large"),
        (
            _zip_bytes({f"src/file_{index:03d}.m": "disp('ok');" for index in range(201)}),
            "project_too_large",
        ),
    ],
    ids=[
        "zip_bomb",
        "zip_slip",
        "bad_extension",
        "oversized_inner_file",
        "too_many_files",
    ],
)
def test_a_async_adversarial_inputs_mark_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    zip_bytes: bytes,
    error_code: str,
) -> None:
    app = _create_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        upload_response = _post_zip(client, zip_bytes)
        project_id = upload_response.json()["project_id"]
        status_response = client.get(f"/projects/{project_id}/status")

    assert upload_response.status_code == 202
    assert upload_response.json()["status"] == "parsing"
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"
    assert status_response.json()["error_code"] == error_code


def test_b_outer_body_too_large_returns_413_with_locked_shape_synchronously(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch, MAX_UPLOAD_SIZE_MB="1")

    with TestClient(app) as client:
        response = _post_zip(client, b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert set(response.json()) == {"error", "message"}
    assert response.json()["error"] == "project_too_large"


def test_response_shape_lock_error_and_message_only_for_413(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _create_app(tmp_path, monkeypatch, MAX_UPLOAD_SIZE_MB="1")

    with TestClient(app) as client:
        response = _post_zip(client, b"x" * (1024 * 1024 + 1))

    assert set(response.json()) == {"error", "message"}
