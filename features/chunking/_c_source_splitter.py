"""Lightweight top-level C source splitting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from loguru import logger

CSectionKind = Literal[
    "header_comment",
    "define_block",
    "typedef_block",
    "global_var_block",
    "function_body",
    "preprocessor_block",
]

_FUNCTION_START_RE = re.compile(
    r"^\s*(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w\s\*]*\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*(?:\{)?\s*$"
)
_TYPEDEF_START_RE = re.compile(r"^\s*typedef\b")
_GLOBAL_VAR_RE = re.compile(
    r"^\s*(?:static\s+)?(?:const\s+)?(?:volatile\s+)?"
    r"(?:real_T|int_T|uint_T|boolean_T|char|short|int|long|float|double|"
    r"size_t|[A-Za-z_]\w*(?:\s*\*)?)\s+"
    r"[A-Za-z_]\w*(?:\s*(?:=|,|;).*)?;\s*(?://.*)?$"
)


@dataclass(frozen=True)
class CSourceSection:
    index: int
    title: str
    kind: CSectionKind
    line_start: int
    line_end: int
    code: str


def split_c_source(raw_code: str, max_tokens: int = 1500) -> list[CSourceSection]:
    """Split C source into top-level sections without parsing function internals."""
    lines = raw_code.splitlines()
    sections: list[CSourceSection] = []
    cursor = 0

    cursor = _maybe_header_comment(lines, cursor, sections)
    while cursor < len(lines):
        if not lines[cursor].strip():
            cursor += 1
            continue

        line = lines[cursor]
        if _is_preprocessor(line):
            cursor = _collect_preprocessor(lines, cursor, sections)
            continue
        if _TYPEDEF_START_RE.match(line):
            cursor = _collect_typedef(lines, cursor, sections)
            continue
        function_match = _FUNCTION_START_RE.match(line)
        if function_match:
            cursor = _collect_function(
                lines, cursor, function_match.group("name"), sections, max_tokens
            )
            continue
        if _GLOBAL_VAR_RE.match(line):
            cursor = _collect_global_vars(lines, cursor, sections)
            continue

        cursor += 1

    return sections


def _maybe_header_comment(
    lines: list[str],
    cursor: int,
    sections: list[CSourceSection],
) -> int:
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    if cursor >= len(lines):
        return cursor

    stripped = lines[cursor].strip()
    if stripped.startswith("/*"):
        end = cursor
        while end < len(lines) and "*/" not in lines[end]:
            end += 1
        end = min(end, len(lines) - 1)
        _append_section(sections, "header_comment", "header_comment", cursor, end, lines)
        return end + 1
    if stripped.startswith("//"):
        end = cursor
        while end + 1 < len(lines) and lines[end + 1].strip().startswith("//"):
            end += 1
        _append_section(sections, "header_comment", "header_comment", cursor, end, lines)
        return end + 1
    return cursor


def _is_preprocessor(line: str) -> bool:
    return line.lstrip().startswith("#")


def _collect_preprocessor(
    lines: list[str],
    cursor: int,
    sections: list[CSourceSection],
) -> int:
    start = cursor
    end = cursor
    while end + 1 < len(lines):
        next_line = lines[end + 1]
        if not next_line.strip():
            break
        if not _is_preprocessor(next_line):
            break
        end += 1

    block = "\n".join(lines[start : end + 1])
    kind: CSectionKind = "define_block" if "#define" in block else "preprocessor_block"
    title = _first_non_empty(lines[start : end + 1])
    _append_section(sections, kind, title, start, end, lines)
    return end + 1


def _collect_typedef(
    lines: list[str],
    cursor: int,
    sections: list[CSourceSection],
) -> int:
    start = cursor
    end = cursor
    depth = 0
    seen_brace = False
    while end < len(lines):
        scrubbed = _strip_string_literals(lines[end])
        depth += scrubbed.count("{")
        if "{" in scrubbed:
            seen_brace = True
        depth -= scrubbed.count("}")
        if ";" in scrubbed and (not seen_brace or depth <= 0):
            break
        end += 1
    end = min(end, len(lines) - 1)
    title = _first_non_empty(lines[start : end + 1])
    _append_section(sections, "typedef_block", title, start, end, lines)
    return end + 1


def _collect_function(
    lines: list[str],
    cursor: int,
    name: str,
    sections: list[CSourceSection],
    max_tokens: int,
) -> int:
    start = cursor
    end = _find_balanced_brace_end(lines, cursor)
    code = "\n".join(lines[start : end + 1])
    token_count = _count_tokens(code)
    if token_count > max_tokens:
        logger.warning(
            "c_function_oversize: file={} func={} tokens={}",
            "<unknown>",
            name,
            token_count,
        )
    _append_section(sections, "function_body", name, start, end, lines)
    return end + 1


def _find_balanced_brace_end(lines: list[str], cursor: int) -> int:
    depth = 0
    seen_open = False
    for index in range(cursor, len(lines)):
        scrubbed = _strip_string_literals(lines[index])
        depth += scrubbed.count("{")
        if "{" in scrubbed:
            seen_open = True
        depth -= scrubbed.count("}")
        if seen_open and depth <= 0:
            return index
    return len(lines) - 1


def _collect_global_vars(
    lines: list[str],
    cursor: int,
    sections: list[CSourceSection],
) -> int:
    start = cursor
    end = cursor
    while end + 1 < len(lines):
        next_line = lines[end + 1]
        if not next_line.strip() or not _GLOBAL_VAR_RE.match(next_line):
            break
        end += 1
    title = _first_non_empty(lines[start : end + 1])
    _append_section(sections, "global_var_block", title, start, end, lines)
    return end + 1


def _append_section(
    sections: list[CSourceSection],
    kind: CSectionKind,
    title: str,
    start: int,
    end: int,
    lines: list[str],
) -> None:
    sections.append(
        CSourceSection(
            index=len(sections) + 1,
            title=title.strip(),
            kind=kind,
            line_start=start + 1,
            line_end=end + 1,
            code="\n".join(lines[start : end + 1]),
        )
    )


def _first_non_empty(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return "section"


def _count_tokens(code: str) -> int:
    return len(re.findall(r"\S+", code))


def _strip_string_literals(line: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', line)
