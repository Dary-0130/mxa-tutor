import re

LineMap = dict[int, tuple[int, int]]


def strip_block_comments_keep_lines(raw_code: str) -> tuple[str, LineMap]:
    """剥离 MATLAB 独占行块注释,并保留原始行号。"""
    lines = raw_code.splitlines()
    result: list[str] = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if in_block:
            result.append("")
            if stripped == "%}":
                in_block = False
            continue
        if stripped == "%{":
            in_block = True
            result.append("")
            continue
        result.append(line)
    line_map = {idx: (idx, idx) for idx in range(1, len(result) + 1)}
    return "\n".join(result), line_map


def placeholder_strings(code: str) -> tuple[str, dict[str, str]]:
    """把单引号和双引号字符串替换为占位符。"""
    result: list[str] = []
    string_map: dict[str, str] = {}
    idx = 0
    token_type = "start"
    while idx < len(code):
        char = code[idx]
        if char == "\n":
            result.append(char)
            token_type = "start"
            idx += 1
        elif char == "'":
            if token_type in {"identifier", "number", "close_bracket", "end_keyword", "transpose"}:
                result.append(char)
                token_type = "transpose"
                idx += 1
            else:
                literal, idx = _consume_single_quoted(code, idx)
                placeholder = f"__STR_{len(string_map)}__"
                string_map[placeholder] = literal
                result.append(placeholder)
                token_type = "identifier"
        elif char == '"':
            literal, idx = _consume_double_quoted(code, idx)
            placeholder = f"__STR_{len(string_map)}__"
            string_map[placeholder] = literal
            result.append(placeholder)
            token_type = "identifier"
        elif char.isalpha() or char == "_":
            token, idx = _consume_identifier(code, idx)
            result.append(token)
            token_type = "end_keyword" if token == "end" else "identifier"
        elif char.isdigit():
            token, idx = _consume_number(code, idx)
            result.append(token)
            token_type = "number"
        else:
            result.append(char)
            if char in ")]}":
                token_type = "close_bracket"
            elif char in "([{" or not char.isspace():
                token_type = "operator"
            idx += 1
    return "".join(result), string_map


def strip_line_comments(code: str) -> str:
    """剥离单行注释;调用前应先完成字符串占位符化。"""
    return "\n".join(line.split("%", 1)[0].rstrip() for line in code.splitlines())


def fold_continuations_with_map(code: str, line_map: LineMap) -> tuple[str, LineMap]:
    """折叠 MATLAB 续行,返回 folded code 和 tuple 形态行号映射。"""
    folded_lines: list[str] = []
    folded_map: LineMap = {}
    current = ""
    current_start: int | None = None
    current_end: int | None = None

    for processed_idx, line in enumerate(code.splitlines(), 1):
        original_start, original_end = line_map[processed_idx]
        if current_start is None:
            current_start = original_start
        current_end = original_end

        continuation = _CONTINUATION_RE.search(line)
        if continuation:
            current += line[: continuation.start()].rstrip() + " "
            continue

        current += line
        folded_idx = len(folded_lines) + 1
        folded_lines.append(current)
        folded_map[folded_idx] = (current_start, current_end)
        current = ""
        current_start = None
        current_end = None

    if current_start is not None:
        folded_idx = len(folded_lines) + 1
        folded_lines.append(current)
        folded_map[folded_idx] = (current_start, current_end or current_start)

    return "\n".join(folded_lines), folded_map


def preprocess(raw_code: str) -> tuple[str, LineMap]:
    """按固定顺序预处理 .m 代码,返回 folded code 和行号映射。"""
    after_block, line_map = strip_block_comments_keep_lines(raw_code)
    placeheld, _ = placeholder_strings(after_block)
    without_line_comments = strip_line_comments(placeheld)
    return fold_continuations_with_map(without_line_comments, line_map)


def _consume_single_quoted(code: str, start: int) -> tuple[str, int]:
    idx = start + 1
    while idx < len(code):
        if code[idx] == "'":
            if idx + 1 < len(code) and code[idx + 1] == "'":
                idx += 2
                continue
            idx += 1
            return code[start:idx], idx
        idx += 1
    return code[start:], len(code)


def _consume_double_quoted(code: str, start: int) -> tuple[str, int]:
    idx = start + 1
    while idx < len(code):
        if code[idx] == '"':
            if idx + 1 < len(code) and code[idx + 1] == '"':
                idx += 2
                continue
            idx += 1
            return code[start:idx], idx
        idx += 1
    return code[start:], len(code)


def _consume_identifier(code: str, start: int) -> tuple[str, int]:
    idx = start
    while idx < len(code) and (code[idx].isalnum() or code[idx] == "_"):
        idx += 1
    return code[start:idx], idx


def _consume_number(code: str, start: int) -> tuple[str, int]:
    idx = start
    while idx < len(code) and (code[idx].isalnum() or code[idx] in "._"):
        idx += 1
    return code[start:idx], idx


_CONTINUATION_RE = re.compile(r"\.\.\.\s*$")
