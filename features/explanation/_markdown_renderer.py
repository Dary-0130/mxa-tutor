"""Markdown rendering for validated simulation explanation packs."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ._claim_validator import PackAcceptanceError, ValidationResult
from ._explanation_service import SECTION_HEADINGS, ExplanationClaim

TYPE_TO_SECTION = {
    "project_purpose": "project_purpose",
    "reading_order": "reading_order",
    "connection_logic": "connection_logic",
    "parameter_reason": "parameter_reason",
    "modification_advice": "modification_advice",
    "observation_point": "observation_point",
    "simulink_caveat": "uncertainty_boundary",
    "uncertainty_boundary": "uncertainty_boundary",
}


class MarkdownRenderer:
    """Render a ValidationResult into human-readable markdown."""

    def render(self, result: ValidationResult, evidence_pack: dict[str, Any]) -> str:
        """Render validated claims with inline evidence IDs and inference markers."""
        if not result.report.acceptance_pass:
            raise PackAcceptanceError(";".join(result.report.acceptance_reasons))

        evidence_by_id = _evidence_by_id(evidence_pack)
        event_by_claim = {event.claim_id: event for event in result.events}
        claims_by_section = _claims_by_section(result.validated_pack.claims)
        lines = [
            f"# {result.validated_pack.title}",
            "",
            "本讲解只基于静态解析到的工程结构、参数和连接关系,没有运行仿真。",
            "带有 `(推断)` 或 `(推断,无直接证据)` 的内容需要你运行仿真或查工程文档确认。",
            "",
        ]
        if result.report.downgrade_count or result.report.rejected_claims_count:
            lines.extend(
                [
                    "Validator 守门提示:",
                    f"- 已降级 claim 数: {result.report.downgrade_count}",
                    f"- 已拒绝 claim 数: {result.report.rejected_claims_count}",
                    "",
                ]
            )

        for index, (section_id, heading) in enumerate(SECTION_HEADINGS, start=1):
            lines.extend([f"## {index}. {heading}", ""])
            claims = claims_by_section.get(section_id, [])
            if not claims:
                lines.extend(["当前证据不足,本节不做强断言。", ""])
                continue
            for claim in claims:
                event = event_by_claim.get(claim.claim_id)
                marker = _marker(claim, event.downgrade_reason if event else None)
                citation = _citation_text(claim.evidence_ids, evidence_by_id)
                lines.append(f"- {claim.text}{marker}{citation}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def normalize_evidence_id(value: str) -> str:
    """Normalize evidence IDs like ``e1`` or ``001`` into ``E001``."""
    text = str(value).strip()
    match = re.fullmatch(r"[Ee]?0*(\d{1,6})", text)
    if not match:
        raise ValueError(f"invalid evidence id: {value!r}")
    return f"E{int(match.group(1)):03d}"


def _claims_by_section(claims: list[ExplanationClaim]) -> dict[str, list[ExplanationClaim]]:
    result: dict[str, list[ExplanationClaim]] = defaultdict(list)
    valid_sections = {section_id for section_id, _ in SECTION_HEADINGS}
    for claim in claims:
        section = (
            claim.section if claim.section in valid_sections else TYPE_TO_SECTION[claim.claim_type]
        )
        result[section].append(claim)
    return result


def _marker(claim: ExplanationClaim, downgrade_reason: str | None) -> str:
    markers: list[str] = []
    if claim.is_inference and not claim.evidence_ids:
        markers.append("推断,无直接证据")
    elif claim.is_inference:
        markers.append("推断")
    if downgrade_reason == "rule_11_overview_only_evidence":
        markers.append("基于项目导览描述")
    elif downgrade_reason:
        markers.append("已降级为不确定边界")
    return f" ({','.join(markers)})" if markers else ""


def _citation_text(evidence_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    if not evidence_ids:
        return ""
    normalized = [normalize_evidence_id(item) for item in evidence_ids]
    normalized.sort()
    known = [item for item in normalized if item in evidence_by_id]
    if not known:
        return ""
    return f" [{', '.join(known)}]"


def _evidence_by_id(evidence_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = evidence_pack.get("evidence", [])
    if not isinstance(evidence, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str):
            result[normalize_evidence_id(evidence_id)] = item
    return result
