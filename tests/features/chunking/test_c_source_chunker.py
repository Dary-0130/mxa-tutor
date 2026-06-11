from __future__ import annotations

from core.domain.project import FileInfo
from features.chunking._c_source_splitter import split_c_source
from features.chunking._source_text_templates import build_c_source_text


def test_split_c_source_emits_one_section_per_function() -> None:
    raw = """\
static void f1(void) {
    int x = 1;
}

static int f2(int y) {
    return y + 1;
}
"""

    sections = split_c_source(raw)

    functions = [section for section in sections if section.kind == "function_body"]
    assert [section.title for section in functions] == ["f1", "f2"]
    assert [(section.line_start, section.line_end) for section in functions] == [(1, 3), (5, 7)]


def test_split_c_source_handles_function_brace_on_next_line() -> None:
    raw = """\
static void mdlStart(SimStruct *S)
{
    pid_V.OutMax = 90;
}
"""

    sections = split_c_source(raw)

    assert len(sections) == 1
    assert sections[0].kind == "function_body"
    assert sections[0].title == "mdlStart"
    assert sections[0].line_start == 1
    assert sections[0].line_end == 4


def test_split_c_source_emits_define_block_section() -> None:
    raw = """\
#define A 1
#define B 2

static void f(void) {
}
"""

    sections = split_c_source(raw)

    assert sections[0].kind == "define_block"
    assert sections[0].code == "#define A 1\n#define B 2"


def test_split_c_source_emits_typedef_block_section() -> None:
    raw = """\
typedef struct {
    float Kp;
    float Ki;
} PID;
"""

    sections = split_c_source(raw)

    assert len(sections) == 1
    assert sections[0].kind == "typedef_block"
    assert sections[0].line_start == 1
    assert sections[0].line_end == 4


def test_split_c_source_emits_global_var_block_section() -> None:
    raw = """\
float x;
int y = 2;

static void f(void) {
}
"""

    sections = split_c_source(raw)

    assert sections[0].kind == "global_var_block"
    assert sections[0].code == "float x;\nint y = 2;"


def test_build_c_source_text_excludes_raw_code_over_10_lines() -> None:
    body = "\n".join(f"    value_{index} = {index};" for index in range(20))
    raw = f"static void f(void) {{\n{body}\n}}"
    section = split_c_source(raw)[0]

    source_text = build_c_source_text(FileInfo("src/f.c", ".c", 1), section)
    evidence = source_text.split("证据摘录(最多 10 行):", 1)[1].strip().splitlines()

    assert len(evidence) <= 10
    assert "value_19" not in source_text


def test_c_function_oversize_logged(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_warning(_message: str, file_path: str, func: str, tokens: int) -> None:
        calls.append((file_path, func, tokens))

    monkeypatch.setattr("features.chunking._c_source_splitter.logger.warning", fake_warning)
    raw = "static void heavy(void) {\n" + " ".join(f"token_{i}" for i in range(20)) + "\n}"

    sections = split_c_source(raw, max_tokens=3)

    assert sections[0].title == "heavy"
    assert calls
    assert calls[0][1] == "heavy"
    assert calls[0][2] > 3
