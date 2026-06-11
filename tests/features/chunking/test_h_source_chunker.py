from __future__ import annotations

from features.chunking._h_source_splitter import split_h_source


def test_split_h_source_short_file_returns_single_section() -> None:
    raw = """\
#ifndef PID_H
#define PID_H
typedef struct { float Kp; } PID;
#endif
"""

    sections = split_h_source(raw)

    assert len(sections) == 1
    assert sections[0].title == "header_file"
    assert sections[0].line_start == 1
    assert sections[0].line_end == 4
    assert sections[0].code == raw


def test_split_h_source_long_file_splits_by_typedef() -> None:
    raw = """\
typedef struct {
    float Kp;
} PID_A;

typedef struct {
    float Ki;
} PID_B;
"""

    sections = split_h_source(raw, max_tokens=4)

    typedefs = [section for section in sections if section.kind == "typedef_block"]
    assert len(typedefs) == 2
    assert [section.title for section in typedefs] == ["typedef struct {", "typedef struct {"]
