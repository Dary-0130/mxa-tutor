from __future__ import annotations

import pytest

from features.chunking._m_script_parser import split_m_script


def test_empty_string_returns_empty_list() -> None:
    assert split_m_script("", max_sections=20) == []


def test_whitespace_returns_empty_list() -> None:
    assert split_m_script(" \n\t  ", max_sections=20) == []


def test_single_line_without_marker_returns_one_section() -> None:
    sections = split_m_script("Kp = 1;", max_sections=20)

    assert len(sections) == 1
    assert sections[0].index == 1
    assert sections[0].title == ""
    assert sections[0].code == "Kp = 1;"


def test_multiline_without_marker_or_blank_line_returns_one_section() -> None:
    raw = "Kp = 1;\nKi = 2;\nout = Kp + Ki;"

    sections = split_m_script(raw, max_sections=20)

    assert len(sections) == 1
    assert sections[0].code == raw


def test_multiline_without_marker_splits_on_blank_lines() -> None:
    raw = "Kp = 1;\n\n\nKi = 2;\n\n\nout = Kp + Ki;"

    sections = split_m_script(raw, max_sections=20)

    assert [section.code for section in sections] == [
        "Kp = 1;",
        "Ki = 2;",
        "out = Kp + Ki;",
    ]


def test_marker_sections_extract_titles() -> None:
    raw = "%% setup\nKp = 1;\n%% run\nout = Kp;"

    sections = split_m_script(raw, max_sections=20)

    assert [(section.title, section.code) for section in sections] == [
        ("setup", "Kp = 1;"),
        ("run", "out = Kp;"),
    ]


def test_marker_without_title_uses_empty_title() -> None:
    sections = split_m_script("%%\nKp = 1;", max_sections=20)

    assert len(sections) == 1
    assert sections[0].title == ""
    assert sections[0].code == "Kp = 1;"


def test_exceeding_max_sections_merges_tail() -> None:
    raw = "%% one\na = 1;\n%% two\nb = 2;\n%% three\nc = 3;"

    sections = split_m_script(raw, max_sections=2)

    assert len(sections) == 2
    assert sections[0].title == "one"
    assert sections[1].title == "(其余合并)"
    assert "b = 2;" in sections[1].code
    assert "c = 3;" in sections[1].code


def test_max_sections_one_merges_all_sections() -> None:
    raw = "%% one\na = 1;\n%% two\nb = 2;"

    sections = split_m_script(raw, max_sections=1)

    assert len(sections) == 1
    assert sections[0].index == 1
    assert sections[0].title == "(其余合并)"
    assert "a = 1;" in sections[0].code
    assert "b = 2;" in sections[0].code


def test_mixed_marker_and_prefix_section_keeps_prefix() -> None:
    raw = "clear;\nclc;\n%% setup\nKp = 1;\n%% run\nout = Kp;"

    sections = split_m_script(raw, max_sections=20)

    assert [(section.title, section.code) for section in sections] == [
        ("", "clear;\nclc;"),
        ("setup", "Kp = 1;"),
        ("run", "out = Kp;"),
    ]


def test_section_with_multiple_block_params_splits_per_block() -> None:
    raw = (
        "%% ========== Section 4: Block Parameters ==========\n"
        "% Total blocks: 2\n\n"
        "% Block: Vref\n"
        "% Type: Constant\n"
        "% Value = 80\n\n"
        "% Block: Linear Transformer\n"
        "% Type: Reference\n"
        "% Winding1 = [1 0.01]\n"
    )

    sections = split_m_script(raw, max_sections=80)

    assert [(section.title, section.code) for section in sections] == [
        (
            "Section 4 :: Vref",
            "% Block: Vref\n% Type: Constant\n% Value = 80",
        ),
        (
            "Section 4 :: Linear Transformer",
            "% Block: Linear Transformer\n% Type: Reference\n% Winding1 = [1 0.01]",
        ),
    ]


def test_section_with_single_block_param_stays_whole() -> None:
    raw = "%% ========== Section 4: Block Parameters ==========\n% Block: Vref\n% Value = 80"

    sections = split_m_script(raw, max_sections=80)

    assert len(sections) == 1
    assert sections[0].title == "========== Section 4: Block Parameters =========="
    assert sections[0].code == "% Block: Vref\n% Value = 80"


def test_section_without_block_param_stays_whole() -> None:
    raw = "%% ========== Section 5: Simulation Configuration ==========\n% StopTime = 2"

    sections = split_m_script(raw, max_sections=80)

    assert len(sections) == 1
    assert sections[0].title == "========== Section 5: Simulation Configuration =========="
    assert sections[0].code == "% StopTime = 2"


def test_single_blank_line_without_marker_does_not_split() -> None:
    raw = "Kp = 1;\n\nKi = 2;"

    sections = split_m_script(raw, max_sections=20)

    assert len(sections) == 1
    assert sections[0].code == raw


def test_invalid_max_sections_raises() -> None:
    with pytest.raises(ValueError, match="max_sections_must_be_positive"):
        split_m_script("Kp = 1;", max_sections=0)
