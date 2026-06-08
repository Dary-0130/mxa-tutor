from __future__ import annotations

import pytest

from features.explanation._claim_validator import (
    ClaimEvidenceValidator,
    PackAcceptanceError,
)
from features.explanation._explanation_service import (
    ExplanationClaim,
    ExplanationPack,
    ExplanationSection,
)
from features.explanation._markdown_renderer import MarkdownRenderer, normalize_evidence_id


def test_markdown_renderer_adds_citations_and_inference_markers() -> None:
    pack = _pack(
        [
            _claim("C001", "project_purpose", ["E001"], text="工程含有核心模块。"),
            _claim(
                "C002",
                "uncertainty_boundary",
                [],
                text="参数物理含义需要工程文档确认。",
                is_inference=True,
            ),
            _claim("C003", "connection_logic", ["E004"], text="导览暗示存在连接主线。"),
            _claim("C004", "connection_logic", ["E003"], text="信号从上游连到下游。"),
        ]
    )
    result = ClaimEvidenceValidator().validate(pack, _evidence_pack())

    markdown = MarkdownRenderer().render(result, _evidence_pack())

    assert "# 测试讲解" in markdown
    assert "工程含有核心模块。 [E001]" in markdown
    assert "参数物理含义需要工程文档确认。 (推断,无直接证据)" in markdown
    assert "导览暗示存在连接主线。 (推断,基于项目导览描述) [E004]" in markdown
    assert "Validator 守门提示" in markdown


def test_markdown_renderer_refuses_pack_acceptance_failure() -> None:
    pack = _pack(
        [
            _claim("C001", "connection_logic", ["E001"]),
            _claim("C002", "connection_logic", ["E001"]),
        ]
    )
    result = ClaimEvidenceValidator().validate(pack, _evidence_pack())

    with pytest.raises(PackAcceptanceError):
        MarkdownRenderer().render(result, _evidence_pack())


def test_normalize_evidence_id_is_deterministic() -> None:
    assert normalize_evidence_id("e1") == "E001"
    assert normalize_evidence_id("001") == "E001"
    assert normalize_evidence_id("E120") == "E120"
    with pytest.raises(ValueError):
        normalize_evidence_id("block-1")


def _claim(
    claim_id: str,
    claim_type: str,
    evidence_ids: list[str],
    *,
    text: str = "claim",
    is_inference: bool = False,
) -> ExplanationClaim:
    return ExplanationClaim(
        claim_id=claim_id,
        section=claim_type,
        claim_type=claim_type,  # type: ignore[arg-type]
        text=text,
        evidence_ids=evidence_ids,
        is_inference=is_inference,
        confidence="low" if is_inference else "medium",
    )


def _pack(claims: list[ExplanationClaim]) -> ExplanationPack:
    return ExplanationPack(
        project_id="p1",
        title="测试讲解",
        sections=[
            ExplanationSection("project_purpose", "工程在做什么", "body", ["C001", "C002"]),
            ExplanationSection("connection_logic", "信号连接逻辑", "body", ["C003"]),
            ExplanationSection("uncertainty_boundary", "不确定边界", "body", ["C002"]),
        ],
        claims=claims,
    )


def _evidence_pack() -> dict[str, object]:
    return {
        "evidence": [
            {"evidence_id": "E001", "kind": "slx_block"},
            {"evidence_id": "E002", "kind": "parameter"},
            {"evidence_id": "E003", "kind": "slx_line"},
            {"evidence_id": "E004", "kind": "project_overview_field"},
        ]
    }
