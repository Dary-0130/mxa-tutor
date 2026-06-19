"""Evaluator-only Markdown parser for paper-to-model fixtures."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import (
    DocumentParser,
    FigurePlaceholder,
    ParsedDocument,
    ParsedLocatorIndex,
    compute_file_hash,
)

_FIG_PATTERN = re.compile(r"\[FIG-(\d{2})(?::([^\]]+))?\]")
_SECTION_PATTERN = re.compile(r"^##\s+(\d+)\.\s+.*$", re.MULTILINE)
_FORMULA_SECTION_PATTERN = re.compile(
    r"^##\s+3\.\s+.*?(?=^##\s+\d+\.\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_CODE_BLOCK_PATTERN = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)


class EvalMarkdownParser(DocumentParser):
    """Parse the checked-in evaluator Markdown fixtures."""

    SUPPORTED_EXTENSIONS: tuple[str, ...] = (".md",)

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def parse(
        self,
        file_path: Path,
        timeout_seconds: float = 30.0,
    ) -> ParsedDocument:
        if not self.supports(file_path):
            raise DocumentParseError("unsupported_document_format")
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError(f"markdown_read_failed:{type(exc).__name__}") from None

        figures, figure_ids = self._extract_figures(raw_text)
        return ParsedDocument(
            raw_text=raw_text,
            page_count=None,
            figure_placeholders=figures,
            table_placeholders=[],
            locator_index=ParsedLocatorIndex(
                section_ids=self._extract_sections(raw_text),
                equation_ids=self._extract_equations(raw_text),
                figure_ids=figure_ids,
            ),
            file_hash=compute_file_hash(file_path),
            extracted_at=datetime.now(UTC),
        )

    @staticmethod
    def _extract_figures(
        raw_text: str,
    ) -> tuple[list[FigurePlaceholder], list[str]]:
        placeholders: list[FigurePlaceholder] = []
        ids: list[str] = []
        seen: set[str] = set()
        for match in _FIG_PATTERN.finditer(raw_text):
            figure_id = f"FIG-{match.group(1)}"
            if figure_id in seen:
                continue
            seen.add(figure_id)
            ids.append(figure_id)
            placeholders.append(
                FigurePlaceholder(
                    figure_id=figure_id,
                    caption=(match.group(2) or "").strip(),
                    paper_section_id=None,
                )
            )
        return placeholders, ids

    @staticmethod
    def _extract_sections(raw_text: str) -> list[str]:
        return list(
            dict.fromkeys(
                f"S{int(match.group(1))}" for match in _SECTION_PATTERN.finditer(raw_text)
            )
        )

    @staticmethod
    def _extract_equations(raw_text: str) -> list[str]:
        formula_section = _FORMULA_SECTION_PATTERN.search(raw_text)
        if formula_section is None:
            return []
        return [
            f"EQ-{index:02d}"
            for index, _ in enumerate(
                _CODE_BLOCK_PATTERN.finditer(formula_section.group(0)),
                start=1,
            )
        ]
