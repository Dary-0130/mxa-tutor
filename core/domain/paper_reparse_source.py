"""Internal temporary source package for paper reparse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

PAPER_REPARSE_SOURCE_SCHEMA_VERSION = 1
PAPER_REPARSE_TTL_HOURS = 24


@dataclass(frozen=True)
class PaperReparseFigurePlaceholder:
    """Stored image placeholder needed to rebuild parser output."""

    figure_id: str
    caption: str
    paper_section_id: str | None


@dataclass(frozen=True)
class PaperReparseLocatorIndex:
    """Stored locator allowlist needed by PaperSpec validation."""

    section_ids: list[str]
    equation_ids: list[str]
    figure_ids: list[str]


@dataclass(frozen=True)
class PaperReparseDocumentSource:
    """Per-document text parser package for reparse."""

    document_id: str
    upload_index: int
    filename: str
    raw_text: str
    page_count: int | None
    figure_placeholders: list[PaperReparseFigurePlaceholder]
    table_placeholders: list[str]
    locator_index: PaperReparseLocatorIndex
    file_hash: str
    extracted_at: datetime


@dataclass(frozen=True)
class PaperReparseSource:
    """Temporary text-only source package tied to one paper bundle."""

    paper_id: str
    expires_at: datetime
    documents: list[PaperReparseDocumentSource]
    primary_index: int | None
    source_schema_version: int = PAPER_REPARSE_SOURCE_SCHEMA_VERSION
