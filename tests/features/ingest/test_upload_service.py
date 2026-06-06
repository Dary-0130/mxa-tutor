from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from adapters.storage.in_memory_project_store import InMemoryProjectStore
from core.domain.exceptions import (
    FileTypeNotAllowedError,
    MParseError,
    ProjectError,
    ProjectTooLargeError,
    SlxParseError,
    ZipBombError,
    ZipSlipError,
)
from core.domain.m_file import MFile
from core.domain.project import FileInfo, ProjectType
from core.domain.slx_model import SlxModel
from core.interfaces.parser import MParser, SlxParser
from features.ingest.upload_service import UploadService, _sanitize_filename


class FakeSlxParser(SlxParser):
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    def parse(self, slx_file_path: str) -> SlxModel:
        if self._exc is not None:
            raise self._exc
        return SlxModel(
            file_path=slx_file_path,
            name=Path(slx_file_path).stem,
            blocks=[],
            lines=[],
            subsystems={},
            solver_config={},
            parse_warnings=[],
        )


class FakeMParser(MParser):
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    def parse(self, m_file_path: str) -> MFile:
        if self._exc is not None:
            raise self._exc
        return MFile(
            file_path=m_file_path,
            file_role="script",
            functions=[],
            imports=[],
            uses_toolbox=[],
            raw_code="disp('ok');",
        )


class NoopChunkingService:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls = []

    async def build_embed_store_project_chunks(self, project) -> int:
        self.calls.append(project)
        if self.exc is not None:
            raise self.exc
        return 0


def _service(
    tmp_path: Path,
    *,
    store: InMemoryProjectStore | None = None,
    file_infos: list[FileInfo] | None = None,
    extractor_exc: Exception | None = None,
    classifier_exc: Exception | None = None,
    slx_exc: Exception | None = None,
    m_exc: Exception | None = None,
    chunking_exc: Exception | None = None,
    max_upload_bytes: int = 10,
) -> tuple[UploadService, InMemoryProjectStore]:
    actual_store = store or InMemoryProjectStore()
    infos = file_infos or [
        FileInfo("model.slx", ".slx", 1),
        FileInfo("main.m", ".m", 1),
        FileInfo("data/params.mat", ".mat", 1),
    ]

    def extractor(_zip_bytes: bytes, project_dir: Path) -> Path:
        if extractor_exc is not None:
            raise extractor_exc
        return project_dir

    def classifier(_extracted_root: Path, _project_root: Path) -> list[FileInfo]:
        if classifier_exc is not None:
            raise classifier_exc
        return infos

    def dependency_analyzer(
        _file_infos: list[FileInfo], _m_files: list[MFile], _project_root: str | None
    ) -> dict[str, list[str]]:
        return {"main.m": ["model.slx"]}

    return (
        UploadService(
            store=actual_store,
            upload_dir=tmp_path,
            max_upload_bytes=max_upload_bytes,
            extractor=extractor,
            classifier=classifier,
            slx_parser=FakeSlxParser(slx_exc),
            m_parser=FakeMParser(m_exc),
            dependency_analyzer=dependency_analyzer,
            chunking_service=NoopChunkingService(chunking_exc),
        ),
        actual_store,
    )


async def test_check_declared_size_pass_within_limit(tmp_path: Path) -> None:
    service, _store = _service(tmp_path, max_upload_bytes=3)
    service.check_declared_size(3)


async def test_check_declared_size_raises_before_read_body(tmp_path: Path) -> None:
    service, _store = _service(tmp_path, max_upload_bytes=3)
    with pytest.raises(ProjectTooLargeError):
        service.check_declared_size(4)


async def test_check_declared_size_handles_none(tmp_path: Path) -> None:
    service, _store = _service(tmp_path)
    service.check_declared_size(None)


async def test_check_actual_size_raises_when_exceeds(tmp_path: Path) -> None:
    service, _store = _service(tmp_path, max_upload_bytes=3)
    with pytest.raises(ProjectTooLargeError):
        service.check_actual_size(4)


async def test_check_actual_size_pass_within_limit(tmp_path: Path) -> None:
    service, _store = _service(tmp_path, max_upload_bytes=3)
    service.check_actual_size(3)


async def test_create_upload_record_generates_uuid_and_creates_pending(tmp_path: Path) -> None:
    service, store = _service(tmp_path)

    project_id = await service.create_upload_record("demo.zip")

    assert UUID(project_id).version == 4
    assert (await store.get_status_view(project_id)).status == "parsing"


async def test_create_upload_record_retries_on_value_error_collision(
    tmp_path: Path, mocker
) -> None:
    service, store = _service(tmp_path)
    first = UUID("00000000-0000-4000-8000-000000000001")
    second = UUID("00000000-0000-4000-8000-000000000002")
    await store.create_pending(str(first), "existing.zip")
    mocker.patch("features.ingest.upload_service.uuid.uuid4", side_effect=[first, second])

    project_id = await service.create_upload_record("demo.zip")

    assert project_id == str(second)


async def test_create_upload_record_raises_project_error_after_three_collisions(
    tmp_path: Path, mocker
) -> None:
    service, store = _service(tmp_path)
    ids = [UUID(f"00000000-0000-4000-8000-00000000000{index}") for index in range(1, 4)]
    for project_id in ids:
        await store.create_pending(str(project_id), "existing.zip")
    mocker.patch("features.ingest.upload_service.uuid.uuid4", side_effect=ids)

    with pytest.raises(ProjectError):
        await service.create_upload_record("demo.zip")


def test_sanitize_filename_strips_path_traversal() -> None:
    assert _sanitize_filename(r"..\secret\demo.zip") == "demo.zip"


def test_sanitize_filename_strips_control_chars() -> None:
    assert _sanitize_filename("bad\n\tname.zip") == "badname.zip"


def test_sanitize_filename_truncates_long() -> None:
    assert len(_sanitize_filename("a" * 120 + ".zip")) == 100


def test_sanitize_filename_empty_falls_back_to_uploaded_zip() -> None:
    assert _sanitize_filename("") == "uploaded.zip"


def test_sanitize_filename_handles_none() -> None:
    assert _sanitize_filename(None) == "uploaded.zip"


async def test_process_happy_path_marks_ready_with_project(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    view = await store.get_status_view("p1")
    project = await store.get_project("p1")
    assert view.status == "ready"
    assert project.id == "p1"
    assert len(project.slx_models) == 1
    assert len(project.m_files) == 1


async def test_process_chunking_failure_keeps_ready_status(tmp_path: Path) -> None:
    service, store = _service(tmp_path, chunking_exc=RuntimeError("boom"))
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    view = await store.get_status_view("p1")
    assert view.status == "ready"


async def test_process_uses_to_thread_for_sync_parsers(tmp_path: Path, mocker) -> None:
    calls = []

    async def fake_to_thread(fn, *args):
        calls.append((fn, args))
        return fn(*args)

    mocker.patch("features.ingest.upload_service.asyncio.to_thread", side_effect=fake_to_thread)
    service, store = _service(tmp_path)
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    assert calls
    assert calls[0][0] == service._run_parse_sync


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (ZipBombError("secret"), "zip_bomb"),
        (ZipSlipError("secret"), "zip_slip"),
        (FileTypeNotAllowedError("secret"), "file_type_not_allowed"),
        (ProjectTooLargeError("secret"), "project_too_large"),
    ],
)
async def test_process_upload_errors_mark_failed(tmp_path: Path, exc: Exception, code: str) -> None:
    service, store = _service(tmp_path, extractor_exc=exc)
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    view = await store.get_status_view("p1")
    assert view.status == "failed"
    assert view.error_code == code


async def test_process_slx_parse_error_marks_failed_parse_error(tmp_path: Path) -> None:
    service, store = _service(tmp_path, slx_exc=SlxParseError("secret"))
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    assert (await store.get_status_view("p1")).error_code == "parse_error"


async def test_process_m_parse_error_marks_failed_parse_error(tmp_path: Path) -> None:
    service, store = _service(tmp_path, m_exc=MParseError("secret"))
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    assert (await store.get_status_view("p1")).error_code == "parse_error"


async def test_process_unexpected_exception_marks_failed_internal_error(tmp_path: Path) -> None:
    service, store = _service(tmp_path, extractor_exc=RuntimeError("secret"))
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    assert (await store.get_status_view("p1")).error_code == "internal_error"


def test_process_logger_never_uses_exception_method() -> None:
    src = Path("features/ingest/upload_service.py").read_text(encoding="utf-8")
    assert "logger.exception" not in src


async def test_process_cleans_up_project_dir_on_failure(tmp_path: Path) -> None:
    service, store = _service(tmp_path, extractor_exc=ZipBombError("secret"))
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    assert not (tmp_path / "p1").exists()


async def test_process_constructs_project_with_correct_fields(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    before = datetime.utcnow()
    await store.create_pending("p1", "demo.zip")

    await service.process("p1", b"zip", "demo.zip")

    project = await store.get_project("p1")
    assert project.project_type == ProjectType.GENERAL
    assert project.mat_files == []
    assert project.file_dependencies == {"main.m": ["model.slx"]}
    assert before <= project.created_at <= datetime.utcnow()
