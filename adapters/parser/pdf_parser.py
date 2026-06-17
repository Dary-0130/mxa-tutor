"""PDF parser adapter backed by pypdf."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import (
    DocumentParser,
    ParsedDocument,
    ParsedLocatorIndex,
    compute_file_hash,
)

PDF_MAGIC = b"%PDF-"
DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_MIN_TEXT_CHARS = 100
_EQUATION_RE = re.compile(r"(^|\s)[A-Za-z][A-Za-z0-9_]*(\s*=|\s*\()")


class PdfParser(DocumentParser):
    """Extract text and locator hints from a PDF without executing embedded content."""

    def __init__(
        self,
        max_file_bytes: int = DEFAULT_MAX_PDF_BYTES,
        min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    ) -> None:
        self._max_file_bytes = max_file_bytes
        self._min_text_chars = min_text_chars

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf" and _read_prefix(file_path, 5) == PDF_MAGIC

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = timeout_seconds
        if not self.supports(file_path):
            raise DocumentParseError("unsupported_pdf_format") from None
        if file_path.stat().st_size > self._max_file_bytes:
            raise DocumentParseError("pdf_too_large") from None
        _reject_active_pdf_content(file_path)

        try:
            reader = PdfReader(str(file_path), strict=False)
        except (OSError, PdfReadError, ValueError):
            raise DocumentParseError("pdf_parse_failed") from None

        if reader.is_encrypted:
            raise DocumentParseError("encrypted_pdf_not_supported") from None

        page_texts: list[str] = []
        section_ids: list[str] = []
        try:
            for index, page in enumerate(reader.pages, start=1):
                section_id = f"S{index}"
                section_ids.append(section_id)
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(f"[{section_id}]\n{text}")
        except (PdfReadError, ValueError, KeyError):
            raise DocumentParseError("pdf_parse_failed") from None

        raw_text = "\n\n".join(page_texts).strip()
        if len(raw_text) < self._min_text_chars:
            raise DocumentParseError("document_text_too_short") from None

        return ParsedDocument(
            raw_text=raw_text,
            page_count=len(reader.pages),
            figure_placeholders=[],
            table_placeholders=[],
            locator_index=ParsedLocatorIndex(
                section_ids=section_ids,
                equation_ids=_extract_equation_ids(raw_text),
                figure_ids=[],
            ),
            file_hash=compute_file_hash(file_path),
            extracted_at=datetime.now(UTC),
        )


def _read_prefix(file_path: Path, size: int) -> bytes:
    try:
        with file_path.open("rb") as stream:
            return stream.read(size)
    except OSError:
        return b""


def _reject_active_pdf_content(file_path: Path) -> None:
    try:
        data = file_path.read_bytes()
    except OSError:
        raise DocumentParseError("pdf_parse_failed") from None
    if b"/JavaScript" in data or b"/JS" in data or b"/OpenAction" in data:
        raise DocumentParseError("active_pdf_content_not_supported") from None


def _extract_equation_ids(raw_text: str) -> list[str]:
    return [f"EQ-{index:02d}" for index, line in enumerate(_equation_lines(raw_text), start=1)]


def _equation_lines(raw_text: str) -> list[str]:
    return [line for line in raw_text.splitlines() if _EQUATION_RE.search(line)]
