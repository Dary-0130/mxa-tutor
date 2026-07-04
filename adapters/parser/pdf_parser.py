"""PDF parser adapter backed by pypdf."""

from __future__ import annotations

import importlib
import re
import unicodedata
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
FALLBACK_MIN_CHARS = 100
FALLBACK_MAX_PYPDF_CJK_RATIO = 0.01
FALLBACK_CORRUPTION_RATIO = 0.005
FALLBACK_MIN_RECOVERY_CJK = 50
_ALLOWED_CONTROL_WHITESPACE = "\t\n\r\f\v"
_PDFPLUMBER_FALLBACK_FAILED = "pdfplumber_fallback_failed"
_EQUATION_RE = re.compile(r"(^|\s)[A-Za-z][A-Za-z0-9_]*(\s*=|\s*\()")

PdfFallbackDiagnostics = dict[str, bool | int | float | str | None]
PdfTextExtraction = tuple[str, list[str]]


class PdfParser(DocumentParser):
    """Extract text and locator hints from a PDF without executing embedded content."""

    def __init__(
        self,
        max_file_bytes: int = DEFAULT_MAX_PDF_BYTES,
        min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    ) -> None:
        self._max_file_bytes = max_file_bytes
        self._min_text_chars = min_text_chars
        self._last_fallback_diagnostics: PdfFallbackDiagnostics = {}

    @property
    def last_fallback_diagnostics(self) -> PdfFallbackDiagnostics:
        return dict(self._last_fallback_diagnostics)

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf" and _read_prefix(file_path, 5) == PDF_MAGIC

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = timeout_seconds
        self._last_fallback_diagnostics = {}
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
        raw_text, section_ids, self._last_fallback_diagnostics = _maybe_apply_pdfplumber_fallback(
            file_path,
            raw_text,
            section_ids,
        )
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


def _maybe_apply_pdfplumber_fallback(
    file_path: Path,
    pypdf_text: str,
    pypdf_section_ids: list[str],
) -> tuple[str, list[str], PdfFallbackDiagnostics]:
    diagnostics = _initial_fallback_diagnostics(pypdf_text)
    if not _pypdf_text_looks_corrupted(pypdf_text):
        return pypdf_text, pypdf_section_ids, diagnostics

    diagnostics["fallback_attempted"] = True
    try:
        plumber_extraction = _extract_with_pdfplumber(file_path)
    except Exception:
        diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
        return pypdf_text, pypdf_section_ids, diagnostics

    if plumber_extraction is None:
        diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
        return pypdf_text, pypdf_section_ids, diagnostics

    plumber_text, plumber_section_ids = plumber_extraction
    diagnostics["plumber_cjk_count"] = _cjk_count(plumber_text)
    diagnostics["plumber_corruption_ratio"] = _corruption_ratio(plumber_text)
    if _pdfplumber_is_meaningful_recovery(pypdf_text, plumber_text):
        diagnostics["fallback_adopted"] = True
        return plumber_text, plumber_section_ids, diagnostics

    diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
    return pypdf_text, pypdf_section_ids, diagnostics


def _initial_fallback_diagnostics(pypdf_text: str) -> PdfFallbackDiagnostics:
    return {
        "pypdf_chars": len(pypdf_text),
        "pypdf_cjk_count": _cjk_count(pypdf_text),
        "pypdf_corruption_ratio": _corruption_ratio(pypdf_text),
        "fallback_attempted": False,
        "fallback_adopted": False,
        "plumber_cjk_count": 0,
        "plumber_corruption_ratio": 0.0,
        "fallback_failure_code": None,
    }


def _extract_with_pdfplumber(file_path: Path) -> PdfTextExtraction | None:
    pdfplumber = importlib.import_module("pdfplumber")
    pdfplumber_open = pdfplumber.open
    page_texts: list[str] = []
    section_ids: list[str] = []

    with pdfplumber_open(str(file_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            section_id = f"S{index}"
            section_ids.append(section_id)
            text = (page.extract_text() or "").strip()
            if text:
                page_texts.append(f"[{section_id}]\n{text}")

    return "\n\n".join(page_texts).strip(), section_ids


def _pypdf_text_looks_corrupted(text: str) -> bool:
    nonws = _non_whitespace_count(text)
    cjk_ratio = _cjk_count(text) / max(1, nonws)
    return (
        len(text.strip()) >= FALLBACK_MIN_CHARS
        and cjk_ratio <= FALLBACK_MAX_PYPDF_CJK_RATIO
        and _corruption_ratio(text) >= FALLBACK_CORRUPTION_RATIO
    )


def _pdfplumber_is_meaningful_recovery(pypdf_text: str, plumber_text: str) -> bool:
    return (
        len(plumber_text.strip()) >= FALLBACK_MIN_CHARS
        and _cjk_count(plumber_text) >= FALLBACK_MIN_RECOVERY_CJK
        and _cjk_count(plumber_text) > _cjk_count(pypdf_text)
        and _corruption_ratio(plumber_text) < _corruption_ratio(pypdf_text)
    )


def _corruption_ratio(text: str) -> float:
    corrupt = sum(1 for ch in text if _is_corrupt_pdf_text_marker(ch))
    return corrupt / max(1, _non_whitespace_count(text))


def _non_whitespace_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _is_corrupt_pdf_text_marker(ch: str) -> bool:
    return (
        unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROL_WHITESPACE
    ) or ch == "\ufffd"


def _cjk_count(text: str) -> int:
    return sum(1 for ch in text if _is_cjk(ch))


def _is_cjk(ch: str) -> bool:
    codepoint = ord(ch)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2EBEF
        or 0x30000 <= codepoint <= 0x323AF
    )


def _extract_equation_ids(raw_text: str) -> list[str]:
    return [f"EQ-{index:02d}" for index, line in enumerate(_equation_lines(raw_text), start=1)]


def _equation_lines(raw_text: str) -> list[str]:
    return [line for line in raw_text.splitlines() if _EQUATION_RE.search(line)]
