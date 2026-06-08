"""Claim-to-evidence validation for simulation explanation packs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Literal

from ._evidence_pack import EvidenceKind
from ._explanation_service import ClaimType, ExplanationClaim, ExplanationPack

TOPOLOGY_KINDS = {"slx_line", "signal_path", "goto_from_tag", "bus_signal"}
RUNTIME_ASSERTION_WORDS = tuple("运行结果 波形 稳定性已验证 仿真已证明 仿真证明 已验证稳定".split())
STRONG_INFERENCE_WORDS = ("必然", "一定", "证明", "最优")


class ClaimValidationFatalError(Exception):
    """Raised for duplicate claims or fabricated evidence IDs."""


class PackAcceptanceError(Exception):
    """Raised when a pack fails aggregate acceptance gates."""


@dataclass(frozen=True)
class ClaimValidationEvent:
    """Per-claim validation event."""

    claim_id: str
    original_claim_type: ClaimType
    final_claim_type: ClaimType
    action: Literal["accepted", "rejected", "downgraded"]
    downgrade_reason: str | None
    evidence_kind_set: list[str]
    rule_id: int | None = None
    recoverable: bool = False


_Decision = tuple[ExplanationClaim | None, ClaimValidationEvent]


@dataclass(frozen=True)
class ClaimValidationReport:
    """Aggregate validation report."""

    total_claims_count: int
    accepted_claims_count: int
    rejected_claims_count: int
    downgrade_count: int
    recoverable_failure_count: int
    rejected_claim_ids: list[str]
    connection_claims_original_count: int
    connection_downgrade_count: int
    connection_downgrade_rate: float
    parameter_claims_original_count: int
    parameter_downgrade_count: int
    parameter_downgrade_rate: float
    modification_claims_original_count: int
    modification_downgrade_count: int
    modification_downgrade_rate: float
    overview_only_downgrade_count: int
    acceptance_pass: bool
    acceptance_reasons: list[str]
    events: list[ClaimValidationEvent]


@dataclass(frozen=True)
class ValidationResult:
    """Validated pack plus rejected claims and aggregate report."""

    validated_pack: ExplanationPack
    rejected_claims: list[ExplanationClaim]
    events: list[ClaimValidationEvent]
    report: ClaimValidationReport


class ClaimEvidenceValidator:
    """Validate ExplanationClaim objects against an EvidencePack."""

    def validate(
        self,
        pack: ExplanationPack,
        evidence_pack: dict[str, Any],
        *,
        retry_exhausted: bool = False,
    ) -> ValidationResult:
        """Validate claims and return a downgraded/rejected result."""
        evidence_kinds = _evidence_kind_map(evidence_pack)
        _raise_on_duplicate_claim_ids(pack.claims)

        accepted: list[ExplanationClaim] = []
        rejected: list[ExplanationClaim] = []
        events: list[ClaimValidationEvent] = []

        for claim in pack.claims:
            unknown_ids = [item for item in claim.evidence_ids if item not in evidence_kinds]
            if unknown_ids:
                raise ClaimValidationFatalError(
                    f"claim {claim.claim_id} cites unknown evidence_ids: {unknown_ids}"
                )

            kind_set = sorted({evidence_kinds[item] for item in claim.evidence_ids})
            decision_claim, event = self._validate_claim(claim, set(kind_set), retry_exhausted)
            events.append(event)
            if decision_claim is None:
                rejected.append(claim)
            else:
                accepted.append(decision_claim)

        valid_ids = {claim.claim_id for claim in accepted}
        validated_pack = replace(
            pack,
            sections=[
                replace(
                    section, claim_ids=[item for item in section.claim_ids if item in valid_ids]
                )
                for section in pack.sections
            ],
            claims=accepted,
        )
        report = _build_report(events, rejected)
        return ValidationResult(validated_pack, rejected, events, report)

    def _validate_claim(
        self,
        claim: ExplanationClaim,
        kind_set: set[str],
        retry_exhausted: bool,
    ) -> _Decision:
        if not claim.evidence_ids and not claim.is_inference:
            return _reject(claim, kind_set, 3, recoverable=True)
        if claim.is_inference and claim.confidence == "high":
            return _reject(claim, kind_set, 5, recoverable=True)
        if claim.is_inference and _contains_any(claim.text, STRONG_INFERENCE_WORDS):
            return _reject(claim, kind_set, 9, recoverable=True)
        if _contains_any(claim.text, RUNTIME_ASSERTION_WORDS):
            return _reject(claim, kind_set, 10, recoverable=True)

        if claim.claim_type == "parameter_reason" and not {"parameter", "slx_block"} <= kind_set:
            if retry_exhausted:
                return _downgrade(claim, kind_set, 7, "rule_7_parameter_missing_block_evidence")
            return _reject(claim, kind_set, 7, recoverable=True)

        if _is_overview_only_downgrade(claim, kind_set):
            return _downgrade(claim, kind_set, 11, "rule_11_overview_only_evidence")
        if claim.claim_type == "connection_logic" and not (kind_set & TOPOLOGY_KINDS):
            return _downgrade(claim, kind_set, 6, "rule_6_connection_no_topology_evidence")
        if claim.claim_type == "modification_advice" and not (
            {"parameter", "measurement"} <= kind_set or {"parameter", "scope"} <= kind_set
        ):
            return _downgrade(claim, kind_set, 8, "rule_8_modification_missing_observation")

        return _accept(claim, kind_set)


def _accept(claim: ExplanationClaim, kind_set: set[str]) -> _Decision:
    return claim, _event(claim, claim.claim_type, "accepted", kind_set)


def _reject(
    claim: ExplanationClaim,
    kind_set: set[str],
    rule_id: int,
    *,
    recoverable: bool,
) -> _Decision:
    return (
        None,
        _event(
            claim, claim.claim_type, "rejected", kind_set, rule_id=rule_id, recoverable=recoverable
        ),
    )


def _downgrade(
    claim: ExplanationClaim,
    kind_set: set[str],
    rule_id: int,
    reason: str,
) -> _Decision:
    final = replace(
        claim,
        claim_type="uncertainty_boundary",
        is_inference=True,
        confidence="low" if claim.confidence == "high" else claim.confidence,
    )
    return final, _event(claim, final.claim_type, "downgraded", kind_set, reason, rule_id)


def _event(
    claim: ExplanationClaim,
    final_type: ClaimType,
    action: Literal["accepted", "rejected", "downgraded"],
    kind_set: set[str],
    reason: str | None = None,
    rule_id: int | None = None,
    recoverable: bool = False,
) -> ClaimValidationEvent:
    return ClaimValidationEvent(
        claim_id=claim.claim_id,
        original_claim_type=claim.claim_type,
        final_claim_type=final_type,
        action=action,
        downgrade_reason=reason,
        evidence_kind_set=sorted(kind_set),
        rule_id=rule_id,
        recoverable=recoverable,
    )


def _build_report(
    events: list[ClaimValidationEvent],
    rejected: list[ExplanationClaim],
) -> ClaimValidationReport:
    total = len(events)
    downgrade_count = sum(1 for event in events if event.action == "downgraded")
    rejected_count = len(rejected)
    original_counts = Counter(event.original_claim_type for event in events)
    downgrade_counts = Counter(
        event.original_claim_type for event in events if event.action == "downgraded"
    )
    rejected_ratio = rejected_count / total if total else 1.0
    connection_rate = _rate(
        downgrade_counts["connection_logic"], original_counts["connection_logic"]
    )
    reasons: list[str] = []
    if total == 0:
        reasons.append("no_claims")
    if rejected_ratio > 0.30:
        reasons.append("rejected_claims_rate_gt_30_percent")
    if connection_rate > 0.50:
        reasons.append("connection_downgrade_rate_gt_50_percent")

    return ClaimValidationReport(
        total_claims_count=total,
        accepted_claims_count=total - rejected_count,
        rejected_claims_count=rejected_count,
        downgrade_count=downgrade_count,
        recoverable_failure_count=sum(1 for event in events if event.recoverable),
        rejected_claim_ids=[claim.claim_id for claim in rejected],
        connection_claims_original_count=original_counts["connection_logic"],
        connection_downgrade_count=downgrade_counts["connection_logic"],
        connection_downgrade_rate=connection_rate,
        parameter_claims_original_count=original_counts["parameter_reason"],
        parameter_downgrade_count=downgrade_counts["parameter_reason"],
        parameter_downgrade_rate=_rate(
            downgrade_counts["parameter_reason"],
            original_counts["parameter_reason"],
        ),
        modification_claims_original_count=original_counts["modification_advice"],
        modification_downgrade_count=downgrade_counts["modification_advice"],
        modification_downgrade_rate=_rate(
            downgrade_counts["modification_advice"],
            original_counts["modification_advice"],
        ),
        overview_only_downgrade_count=sum(
            1 for event in events if event.downgrade_reason == "rule_11_overview_only_evidence"
        ),
        acceptance_pass=not reasons,
        acceptance_reasons=reasons,
        events=events,
    )


def _evidence_kind_map(evidence_pack: dict[str, Any]) -> dict[str, EvidenceKind]:
    evidence = evidence_pack.get("evidence", [])
    if not isinstance(evidence, list):
        raise ClaimValidationFatalError("EvidencePack.evidence must be a list")
    result: dict[str, EvidenceKind] = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise ClaimValidationFatalError("EvidencePack.evidence item must be an object")
        evidence_id = item.get("evidence_id")
        kind = item.get("kind")
        if isinstance(evidence_id, str) and isinstance(kind, str):
            result[evidence_id] = kind
    return result


def _raise_on_duplicate_claim_ids(claims: list[ExplanationClaim]) -> None:
    counts = Counter(claim.claim_id for claim in claims)
    duplicates = sorted(claim_id for claim_id, count in counts.items() if count > 1)
    if duplicates:
        raise ClaimValidationFatalError(f"duplicate claim_id values: {duplicates}")


def _is_overview_only_downgrade(claim: ExplanationClaim, kind_set: set[str]) -> bool:
    return (
        claim.claim_type in {"parameter_reason", "connection_logic", "modification_advice"}
        and kind_set == {"project_overview_field"}
        and len(claim.evidence_ids) == 1
    )


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
