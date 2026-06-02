import re

from core.domain.m_file import MFunction

LineMap = dict[int, tuple[int, int]]


def classify_file_role(preprocessed_code: str) -> str:
    """分类 .m 文件角色为 script / function / class。"""
    for line in preprocessed_code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^function\b", stripped):
            return "function"
        if re.match(r"^classdef\b", stripped):
            return "class"
        return "script"
    return "script"


def extract_functions(
    preprocessed_code: str,
    line_map: LineMap,
    original_lines: list[str],
) -> list[MFunction]:
    """提取 top-level function 列表。"""
    lines = preprocessed_code.splitlines()
    top_level_starts = _find_top_level_function_lines(lines)
    functions: list[MFunction] = []
    for pos, line_idx in enumerate(top_level_starts):
        parsed = parse_function_signature(lines[line_idx - 1])
        if parsed is None:
            continue
        next_start = top_level_starts[pos + 1] if pos + 1 < len(top_level_starts) else None
        end_line = _find_function_end(lines, line_idx, next_start)
        start_original = line_map[line_idx][0]
        end_original = line_map[end_line][1]
        name, inputs, outputs = parsed
        functions.append(
            MFunction(
                name=name,
                inputs=inputs,
                outputs=outputs,
                line_range=(start_original, end_original),
                docstring=_extract_docstring(original_lines, line_map[line_idx][1]),
            )
        )
    return functions


def parse_function_signature(line: str) -> tuple[str, list[str], list[str]] | None:
    """解析 MATLAB function 签名。"""
    match = _FUNCTION_SIG_RE.match(line)
    if match is None:
        return None
    name = match.group("name")
    inputs = _split_names(match.group("inputs") or "")
    if match.group("outs_bracket"):
        outputs = _split_names(match.group("outs_bracket").strip()[1:-1])
    elif match.group("out_single"):
        outputs = [match.group("out_single")]
    else:
        outputs = []
    return name, inputs, outputs


def _find_top_level_function_lines(lines: list[str]) -> list[int]:
    stack: list[str] = []
    starts: list[int] = []
    for idx, line in enumerate(lines, 1):
        if _is_function_line(line):
            if not stack or (stack == ["function"] and _leading_spaces(line) == 0):
                if stack == ["function"]:
                    stack.clear()
                starts.append(idx)
            stack.append("function")
            continue
        for event in _line_events(line):
            if event == "end":
                if stack:
                    stack.pop()
            else:
                stack.append(event)
    return starts


def _find_function_end(lines: list[str], start_line: int, next_start: int | None) -> int:
    stack = ["function"]
    limit = next_start or (len(lines) + 1)
    for idx in range(start_line + 1, limit):
        line = lines[idx - 1]
        if _is_function_line(line):
            stack.append("function")
            continue
        for event in _line_events(line):
            if event == "end":
                if stack:
                    stack.pop()
                if not stack:
                    return idx
            else:
                stack.append(event)
    return (next_start - 1) if next_start is not None else len(lines)


def _extract_docstring(original_lines: list[str], signature_end_original_line: int) -> str | None:
    idx = signature_end_original_line
    while idx < len(original_lines) and not original_lines[idx].strip():
        idx += 1
    if idx < len(original_lines) and re.match(r"^\s*arguments\b", original_lines[idx]):
        idx = _skip_arguments_block(original_lines, idx)
    while idx < len(original_lines) and not original_lines[idx].strip():
        idx += 1

    doc_lines: list[str] = []
    while idx < len(original_lines):
        stripped = original_lines[idx].strip()
        if (
            stripped.startswith("%")
            and not stripped.startswith("%{")
            and not stripped.startswith("%%")
        ):
            doc_lines.append(stripped.lstrip("%").strip())
            idx += 1
            continue
        break
    return "\n".join(doc_lines) if doc_lines else None


def _skip_arguments_block(original_lines: list[str], start_idx: int) -> int:
    idx = start_idx + 1
    while idx < len(original_lines):
        if re.match(r"^\s*end\s*$", original_lines[idx]):
            return idx + 1
        idx += 1
    return idx


def _line_events(line: str) -> list[str]:
    events: list[str] = []
    depth = 0
    idx = 0
    while idx < len(line):
        char = line[idx]
        if char in "([{":
            depth += 1
            idx += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
            idx += 1
        elif (char.isalpha() or char == "_") and depth == 0:
            token, idx = _consume_identifier(line, idx)
            if token in _BLOCK_STARTS:
                events.append(token)
            elif token == "end" and _looks_like_block_end(line, idx - len(token), idx):
                events.append("end")
        else:
            idx += 1
    return events


def _looks_like_block_end(line: str, start: int, end: int) -> bool:
    before = line[:start].rstrip()
    after = line[end:].lstrip()
    if before.endswith(":"):
        return False
    return not after or after[0] in ";,%"


def _is_function_line(line: str) -> bool:
    return re.match(r"^\s*function\b", line) is not None


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip())


def _consume_identifier(line: str, start: int) -> tuple[str, int]:
    idx = start
    while idx < len(line) and (line[idx].isalnum() or line[idx] == "_"):
        idx += 1
    return line[start:idx], idx


def _split_names(raw: str) -> list[str]:
    normalized = raw.replace(",", " ")
    return [part.strip() for part in normalized.split() if part.strip()]


_BLOCK_STARTS = {
    "if",
    "for",
    "while",
    "switch",
    "try",
    "arguments",
    "classdef",
    "properties",
    "methods",
    "events",
    "enumeration",
}

_FUNCTION_SIG_RE = re.compile(
    r"^\s*function\s+"
    r"(?:(?P<outs_bracket>\[[^\]]*\])\s*=\s*|(?P<out_single>\w+)\s*=\s*)?"
    r"(?P<name>\w+)"
    r"(?:\s*\((?P<inputs>[^)]*)\))?"
    r"\s*$"
)
