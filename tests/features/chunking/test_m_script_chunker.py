from __future__ import annotations

from datetime import datetime

from app.config import AppSettings
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from features.chunking._project_chunker import _build_m_file_drafts, _build_m_script_drafts


def _project_with_script(raw_code: str) -> Project:
    return Project(
        id="p-script",
        name="script.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("main.m", ".m", 10, description="入口脚本")],
        slx_models=[],
        m_files=[MFile("main.m", "script", [], [], [], raw_code)],
        mat_files=[],
        created_at=datetime(2026, 6, 6, 0, 0, 0),
        file_dependencies={},
    )


def test_build_m_script_drafts_emits_one_chunk_per_section(
    chunk_settings: AppSettings,
) -> None:
    project = _project_with_script("%% setup\nKp = 1;\n%%\nKi = 2;")

    drafts = _build_m_script_drafts(project, chunk_settings)

    assert len(drafts) == 2
    assert all(draft.source_type == "m_file" for draft in drafts)
    assert all(f"section_{index}" in draft.chunk_id for index, draft in enumerate(drafts, 1))
    assert [draft.symbol_name for draft in drafts] == ["setup", "section_2"]
    assert "第 1 段(共 2 段)标题 setup" in drafts[0].source_text
    assert "第 2 段(共 2 段)" in drafts[1].source_text


def test_m_file_summary_uses_assignment_section_count(
    chunk_settings: AppSettings,
) -> None:
    project = _project_with_script("a = 1;\n\n\nb = 2;")

    drafts = _build_m_file_drafts(project, chunk_settings)

    assert len(drafts) == 1
    assert drafts[0].source_text.startswith("文件 main.m,类型 .m,角色 script,含 2 段赋值。")
