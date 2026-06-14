from __future__ import annotations

from datetime import datetime

import pytest
from loguru import logger

from app.config import AppSettings
from core.domain.file_paths import contains_server_path_hint, is_public_file_path
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from features.chunking import _project_chunker


def test_is_public_file_path_shape_only() -> None:
    true_paths = [
        "main.m",
        "src/main.m",
        "data/uploads/input.mat",
        "temp/model_init.m",
        "__project_overview__",
    ]
    false_paths = [
        "",
        "/tmp/main.m",
        r"\tmp\main.m",
        r"C:\tmp\main.m",
        r"C:tmp\main.m",
        "src/../main.m",
    ]
    assert all(is_public_file_path(path) for path in true_paths)
    assert not any(is_public_file_path(path) for path in false_paths)


def test_contains_server_path_hint_uses_combined_markers() -> None:
    leaked = [
        r"D:\mxa-workspace\uploads\p1\main.m",
        r"C:\Users\asus\AppData\Local\Temp\pytest-of-asus\main.m",
        "/tmp/pytest-of-asus/project/main.m",
    ]
    clean = ["data/uploads/input.mat", "temp/model_init.m", "upload_signal.m"]
    assert all(contains_server_path_hint(path) for path in leaked)
    assert not any(contains_server_path_hint(path) for path in clean)


@pytest.mark.parametrize(
    ("raw_path", "project_files", "expected"),
    [
        ("src/main.m", [FileInfo("src/main.m", ".m", 10)], "src/main.m"),
        (
            r"D:\mxa-workspace\uploads\p1\src\main.m",
            [FileInfo("src/main.m", ".m", 10)],
            "src/main.m",
        ),
        (
            "/srv/mxa-workspace/uploads/p1/models/top.slx",
            [FileInfo("models/top.slx", ".slx", 10)],
            "models/top.slx",
        ),
        (r"D:\mxa-workspace\uploads\p1\missing.m", [FileInfo("src/main.m", ".m", 10)], None),
        (
            r"D:\mxa-workspace\uploads\p1\src\main.m",
            [FileInfo("src/main.m", ".m", 10), FileInfo("src/main.m", ".m", 12)],
            None,
        ),
    ],
)
def test_compute_public_file_path(
    raw_path: str, project_files: list[FileInfo], expected: str | None
) -> None:
    public_path = _project_chunker._compute_public_file_path(raw_path, iter(project_files))

    assert public_path == expected
    if public_path is not None:
        assert "\\" not in public_path
        assert is_public_file_path(public_path)


def test_unresolved_public_path_skips_chunk_and_logs_four_fields(
    chunk_settings: AppSettings,
) -> None:
    project = Project(
        id="p-no-match",
        name="bad.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("main.m", ".m", 10)],
        slx_models=[],
        m_files=[
            MFile(r"D:\mxa-workspace\uploads\p-no-match\missing.m", "script", [], [], [], "x = 1;")
        ],
        mat_files=[],
        created_at=datetime(2026, 6, 14, 0, 0, 0),
        file_dependencies={},
    )
    records = []
    sink_id = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        drafts = _project_chunker._build_m_file_drafts(project, chunk_settings)
    finally:
        logger.remove(sink_id)

    assert drafts == []
    matching = [
        record for record in records if record["message"] == "chunk_skipped_public_path_unresolved"
    ]
    assert len(matching) == 1
    assert matching[0]["extra"] == {
        "project_id": "p-no-match",
        "source_type": "m_file",
        "match_count": 0,
        "reason": "no_match",
    }
