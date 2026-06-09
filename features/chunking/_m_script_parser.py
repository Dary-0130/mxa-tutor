"""Split MATLAB script .m raw code into sections for chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_SECTION_MARKER_PATTERN: Final = re.compile(r"^[ \t]*%%[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_DOUBLE_BLANK_PATTERN: Final = re.compile(r"\n[ \t]*\n[ \t]*\n+")
_BLOCK_HEADER_PATTERN: Final = re.compile(r"^% Block:\s*(.+)$", re.MULTILINE)
_SECTION_NUMBER_PATTERN: Final = re.compile(r"\b(Section\s+\d+)\b")


@dataclass(frozen=True)
class MScriptSection:
    """A logical section of a script-style .m file."""

    index: int
    title: str
    code: str


def split_m_script(raw_code: str, max_sections: int) -> list[MScriptSection]:
    """Split raw .m script code into logical sections."""
    if max_sections < 1:
        raise ValueError("max_sections_must_be_positive")
    if not raw_code or not raw_code.strip():
        return []
    raw_code = raw_code.replace("\r\n", "\n").replace("\r", "\n")

    if _SECTION_MARKER_PATTERN.search(raw_code):
        sections = _split_by_markers(raw_code)
    else:
        sections = _split_by_blank_lines(raw_code)

    sections = [
        split_section
        for title, code in sections
        if code.strip()
        for split_section in _split_block_params(title, code)
    ]
    if not sections:
        return []

    if len(sections) > max_sections:
        head = sections[: max_sections - 1]
        tail_codes = [code for _, code in sections[max_sections - 1 :]]
        head.append(("(其余合并)", "\n\n".join(tail_codes)))
        sections = head

    return [
        MScriptSection(index=i + 1, title=title, code=code.strip())
        for i, (title, code) in enumerate(sections)
    ]


def _split_by_markers(raw_code: str) -> list[tuple[str, str]]:
    """Split by %% markers; each section starts at a marker line."""
    result: list[tuple[str, str]] = []
    matches = list(_SECTION_MARKER_PATTERN.finditer(raw_code))
    if not matches:
        return [("", raw_code)]

    first_start = matches[0].start()
    if raw_code[:first_start].strip():
        result.append(("", raw_code[:first_start]))

    for index, marker in enumerate(matches):
        title = marker.group(1).strip()
        body_start = marker.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_code)
        result.append((title, raw_code[body_start:body_end]))

    return result


def _split_by_blank_lines(raw_code: str) -> list[tuple[str, str]]:
    """Split by double blank lines; no titles."""
    return [("", part) for part in _DOUBLE_BLANK_PATTERN.split(raw_code)]


def _split_block_params(section_title: str, section_text: str) -> list[tuple[str, str]]:
    """Split a block-parameter section into one subsection per block."""
    matches = list(_BLOCK_HEADER_PATTERN.finditer(section_text))
    if len(matches) <= 1:
        return [(section_title, section_text)]

    title_prefix = _block_section_title(section_title)
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        block_name = match.group(1).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
        result.append((f"{title_prefix} :: {block_name}", section_text[start:end].strip()))
    return result


def _block_section_title(section_title: str) -> str:
    match = _SECTION_NUMBER_PATTERN.search(section_title)
    return match.group(1) if match else section_title
