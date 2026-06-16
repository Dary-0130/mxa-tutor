"""Document parser contracts for paper-to-model uploads."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.domain.exceptions import DocumentParseError


@dataclass(frozen=True)
class FigurePlaceholder:
    """Image location discovered by a parser before LLM extraction."""

    figure_id: str
    caption: str
    paper_section_id: str | None


@dataclass(frozen=True)
class ParsedLocatorIndex:
    """Locator whitelist that downstream PaperSpec evidence must reference."""

    section_ids: list[str]
    equation_ids: list[str]
    figure_ids: list[str]


@dataclass(frozen=True)
class ParsedDocument:
    """Structured parser output before LLM extraction."""

    raw_text: str
    page_count: int | None
    figure_placeholders: list[FigurePlaceholder]
    table_placeholders: list[str]
    locator_index: ParsedLocatorIndex
    file_hash: str
    extracted_at: datetime


class DocumentParser(ABC):
    """Synchronous parser interface executed behind a sandbox boundary."""

    @abstractmethod
    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        """Parse one PDF/docx file."""
        ...

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Return true when extension and magic/container checks match."""
        ...


class DocumentParserRouter:
    """Route a document path to the first parser that supports it."""

    def __init__(self, parsers: list[DocumentParser]) -> None:
        self._parsers = parsers

    def route(self, file_path: Path) -> DocumentParser:
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        raise DocumentParseError("unsupported_document_format")


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 without logging or exposing the source filename."""
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
