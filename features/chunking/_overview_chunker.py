"""Build the project_overview chunk draft."""

from __future__ import annotations

from core.domain.project_overview import ProjectOverview

from ._chunk_draft import ChunkDraft
from ._chunk_id import make_overview_chunk_id
from ._source_text_templates import build_project_overview_source_text, truncate_source_text


def build_draft(
    overview: ProjectOverview,
    project_id: str,
    max_chars: int = 1024,
) -> ChunkDraft:
    raw = build_project_overview_source_text(overview)
    return ChunkDraft(
        chunk_id=make_overview_chunk_id(project_id),
        project_id=project_id,
        source_type="project_overview",
        file_path="__project_overview__",
        symbol_name=overview.project_title,
        line_range=None,
        block_id=None,
        block_name=None,
        block_type=None,
        parent_subsystem=None,
        source_text=truncate_source_text(raw, max_chars),
    )
