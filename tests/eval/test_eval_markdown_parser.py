from __future__ import annotations

from pathlib import Path

import pytest

from core.domain.exceptions import DocumentParseError
from eval._eval_markdown_parser import EvalMarkdownParser

FIXTURE_ROOT = Path("eval/cases/paper_to_model")


def _parse_text(tmp_path: Path, text: str, suffix: str = ".md"):
    path = tmp_path / f"case{suffix}"
    path.write_text(text, encoding="utf-8")
    return EvalMarkdownParser().parse(path)


def test_supports_only_markdown_files() -> None:
    parser = EvalMarkdownParser()

    assert parser.supports(Path("sample.md"))
    assert parser.supports(Path("sample.MD"))
    assert not parser.supports(Path("sample.txt"))


def test_parse_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "case.txt"
    path.write_text("# nope", encoding="utf-8")

    with pytest.raises(DocumentParseError, match="unsupported_document_format"):
        EvalMarkdownParser().parse(path)


def test_parse_empty_file_has_empty_locator_sets(tmp_path: Path) -> None:
    parsed = _parse_text(tmp_path, "")

    assert parsed.raw_text == ""
    assert parsed.figure_placeholders == []
    assert parsed.locator_index.section_ids == []
    assert parsed.locator_index.equation_ids == []
    assert parsed.locator_index.figure_ids == []


def test_extracts_captioned_and_bare_figures(tmp_path: Path) -> None:
    parsed = _parse_text(
        tmp_path,
        "> **[FIG-01:标准同步发电机模型参数图]**(含 H / F 缺参线索)\n\n" "> **[FIG-02]**\n",
    )

    assert parsed.locator_index.figure_ids == ["FIG-01", "FIG-02"]
    assert [figure.caption for figure in parsed.figure_placeholders] == [
        "标准同步发电机模型参数图（含 H / F 缺参线索）",
        "",
    ]


def test_deduplicates_figures_by_first_occurrence(tmp_path: Path) -> None:
    parsed = _parse_text(
        tmp_path,
        "[FIG-01:first]\n[FIG-02:second]\n[FIG-01:duplicate]\n",
    )

    assert parsed.locator_index.figure_ids == ["FIG-01", "FIG-02"]
    assert [figure.caption for figure in parsed.figure_placeholders] == [
        "first",
        "second",
    ]


def test_extracts_numeric_sections_in_order(tmp_path: Path) -> None:
    parsed = _parse_text(
        tmp_path,
        "## 01. 任务陈述\n\n## 2. 参数\n\n## 2. 重复\n\n## 10. 附录\n",
    )

    assert parsed.locator_index.section_ids == ["S1", "S2", "S10"]


def test_only_formula_section_code_blocks_create_equations(tmp_path: Path) -> None:
    parsed = _parse_text(
        tmp_path,
        "## 2. 参数\n\n```text\nPN = 200\n```\n\n## 4. 物理含义\n\n```matlab\nx = 1\n```\n",
    )

    assert parsed.locator_index.equation_ids == []


def test_formula_section_code_blocks_create_equation_ids(tmp_path: Path) -> None:
    parsed = _parse_text(
        tmp_path,
        "## 3. 数值计算公式\n\n```text\nia = 1\n```\n\n```matlab\nplot(ia)\n```\n",
    )

    assert parsed.locator_index.equation_ids == ["EQ-01", "EQ-02"]


def test_real_material_fixture_exact_locator_sets() -> None:
    parsed = EvalMarkdownParser().parse(
        FIXTURE_ROOT
        / "material_to_plan"
        / "case_01_motor_short_circuit"
        / "input"
        / "source_doc_stripped.md"
    )

    assert parsed.locator_index.section_ids == ["S1", "S2", "S3", "S4", "S5"]
    assert parsed.locator_index.equation_ids == ["EQ-01"]
    assert parsed.locator_index.figure_ids == []
    assert parsed.figure_placeholders == []


def test_real_missing_fixture_exact_locator_sets() -> None:
    parsed = EvalMarkdownParser().parse(
        FIXTURE_ROOT
        / "missing_param"
        / "case_01_missing_image_param"
        / "input"
        / "source_doc_stripped.md"
    )

    assert parsed.locator_index.section_ids == ["S1", "S2", "S3", "S4", "S5"]
    assert parsed.locator_index.equation_ids == ["EQ-01"]
    assert parsed.locator_index.figure_ids == [
        "FIG-01",
        "FIG-02",
        "FIG-03",
        "FIG-04",
        "FIG-05",
    ]
    assert [figure.caption for figure in parsed.figure_placeholders] == [
        "标准同步发电机模型参数图（v0.1 系统无 OCR,图片信息丢失;论文在此提供 SimPowerSystems Synchronous Machine pu Standard 完整参数槽位,可能含本文档第 2 节文字之外的额外参数如 H 惯性时间常数 / F 摩擦因数 等(系统应识别这两项为缺失参数,等待用户补充)。）",
        "变压器参数图（v0.1 系统无 OCR,图片信息丢失;论文在此提供 Three-Phase Transformer 参数 — 包括 **变压器变比(原边/副边电压比)** / **变压器漏阻抗 X_T** / **变压器接线方式(原边 / 副边连接组别)** 三项,文字未给出任何变压器具体数值。系统应识别这三项为缺失参数,等待用户补充。）",
        "电机初始化工具截图（v0.1 系统无 OCR,图片信息丢失;文字仅明示 a 相滞后电压 -4.43°,其他初始化参数 — 如励磁电压 Vf0 / 机械功率初值 Pm0 / α0 初相角 — 在截图中。系统应识别为缺失参数,等待用户补充。）",
        ".m 计算 a 相定子电流分量波形（图片占位,v0.1 系统无 OCR;非参数缺失,仅是结果可视化）",
        "Simulink 三相定子电流波形（图片占位,同上;非参数缺失）",
    ]
