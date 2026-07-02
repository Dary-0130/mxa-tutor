"""Helpers for temporary paper reparse source packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.domain.paper_reparse_source import (
    PAPER_REPARSE_TTL_HOURS,
    PaperReparseDocumentSource,
    PaperReparseFigurePlaceholder,
    PaperReparseLocatorIndex,
    PaperReparseSource,
)
from core.interfaces.document_parser import (
    FigurePlaceholder,
    ParsedDocument,
    ParsedLocatorIndex,
)


@dataclass(frozen=True)
class SuccessfulParsedDocument:
    """A parser output package for one successfully extracted document."""

    upload_index: int
    document_id: str
    filename: str
    parsed: ParsedDocument


def build_reparse_source(
    paper_id: str,
    documents: list[SuccessfulParsedDocument],
    primary_index: int | None,
    *,
    created_at: datetime | None = None,
) -> PaperReparseSource:
    """Build the text-only temporary reparse package for successful documents."""

    base_time = created_at or datetime.utcnow()
    return PaperReparseSource(
        paper_id=paper_id,
        expires_at=base_time + timedelta(hours=PAPER_REPARSE_TTL_HOURS),
        documents=[_to_document_source(document) for document in documents],
        primary_index=primary_index,
    )


def parsed_document_from_source(source: PaperReparseDocumentSource) -> ParsedDocument:
    """Rebuild parser output from stored text-only source."""

    return ParsedDocument(
        raw_text=source.raw_text,
        page_count=source.page_count,
        figure_placeholders=[
            FigurePlaceholder(
                figure_id=figure.figure_id,
                caption=figure.caption,
                paper_section_id=figure.paper_section_id,
            )
            for figure in source.figure_placeholders
        ],
        table_placeholders=list(source.table_placeholders),
        locator_index=ParsedLocatorIndex(
            section_ids=list(source.locator_index.section_ids),
            equation_ids=list(source.locator_index.equation_ids),
            figure_ids=list(source.locator_index.figure_ids),
        ),
        file_hash=source.file_hash,
        extracted_at=source.extracted_at,
    )


def _to_document_source(document: SuccessfulParsedDocument) -> PaperReparseDocumentSource:
    parsed = document.parsed
    return PaperReparseDocumentSource(
        document_id=document.document_id,
        upload_index=document.upload_index,
        filename=document.filename,
        raw_text=parsed.raw_text,
        page_count=parsed.page_count,
        figure_placeholders=[
            PaperReparseFigurePlaceholder(
                figure_id=figure.figure_id,
                caption=figure.caption,
                paper_section_id=figure.paper_section_id,
            )
            for figure in parsed.figure_placeholders
        ],
        table_placeholders=list(parsed.table_placeholders),
        locator_index=PaperReparseLocatorIndex(
            section_ids=list(parsed.locator_index.section_ids),
            equation_ids=list(parsed.locator_index.equation_ids),
            figure_ids=list(parsed.locator_index.figure_ids),
        ),
        file_hash=parsed.file_hash,
        extracted_at=parsed.extracted_at,
    )
