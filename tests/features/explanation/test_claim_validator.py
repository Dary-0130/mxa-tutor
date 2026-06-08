from __future__ import annotations

import pytest

from features.explanation._claim_validator import (
    ClaimEvidenceValidator,
    ClaimValidationFatalError,
)
from features.explanation._explanation_service import (
    ExplanationClaim,
    ExplanationPack,
    ExplanationSection,
)


def test_validator_accepts_rejects_and_downgrades_claims() -> None:
    pack = _pack(
        [
            _claim("C001", "project_purpose", ["E001"]),
            _claim("C002", "connection_logic", ["E001"]),
            _claim("C003", "parameter_reason", ["E002"]),
            _claim("C004", "modification_advice", ["E002", "E001"]),
        ]
    )

    result = ClaimEvidenceValidator().validate(pack, _evidence_pack())

    assert any(event.recoverable for event in result.events if event.action == "rejected")
    assert result.report.rejected_claim_ids == ["C003"]
    assert result.report.downgrade_count == 2
    assert result.report.connection_downgrade_rate == 1.0
    assert {claim.claim_id for claim in result.validated_pack.claims} == {"C001", "C002", "C004"}
    downgraded = {claim.claim_id: claim for claim in result.validated_pack.claims}
    assert downgraded["C002"].claim_type == "uncertainty_boundary"
    assert downgraded["C004"].is_inference is True


def test_validator_downgrades_parameter_rule_after_retry_is_exhausted() -> None:
    pack = _pack([_claim("C001", "parameter_reason", ["E002"])])

    result = ClaimEvidenceValidator().validate(pack, _evidence_pack(), retry_exhausted=True)

    assert not any(event.recoverable for event in result.events if event.action == "rejected")
    assert result.report.rejected_claims_count == 0
    assert result.report.parameter_downgrade_rate == 1.0
    assert result.validated_pack.claims[0].claim_type == "uncertainty_boundary"


def test_validator_rule_11_tracks_overview_only_downgrade() -> None:
    pack = _pack([_claim("C001", "connection_logic", ["E004"])])

    result = ClaimEvidenceValidator().validate(pack, _evidence_pack())

    assert result.report.overview_only_downgrade_count == 1
    assert result.events[0].downgrade_reason == "rule_11_overview_only_evidence"


def test_validator_rejects_fabricated_evidence_id_as_fatal() -> None:
    pack = _pack([_claim("C001", "project_purpose", ["E999"])])

    with pytest.raises(ClaimValidationFatalError):
        ClaimEvidenceValidator().validate(pack, _evidence_pack())


def test_validator_rejects_duplicate_claim_id_as_fatal() -> None:
    pack = _pack(
        [
            _claim("C001", "project_purpose", ["E001"]),
            _claim("C001", "reading_order", ["E001"]),
        ]
    )

    with pytest.raises(ClaimValidationFatalError):
        ClaimEvidenceValidator().validate(pack, _evidence_pack())


def _claim(
    claim_id: str,
    claim_type: str,
    evidence_ids: list[str],
    *,
    text: str = "这是一条静态证据支持的 claim。",
) -> ExplanationClaim:
    return ExplanationClaim(
        claim_id=claim_id,
        section=claim_type,
        claim_type=claim_type,  # type: ignore[arg-type]
        text=text,
        evidence_ids=evidence_ids,
        is_inference=False,
        confidence="medium",
    )


def _pack(claims: list[ExplanationClaim]) -> ExplanationPack:
    return ExplanationPack(
        project_id="p1",
        title="测试讲解",
        sections=[
            ExplanationSection(
                section_id="project_purpose",
                heading="工程在做什么",
                body="body",
                claim_ids=[claim.claim_id for claim in claims],
            )
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
            {"evidence_id": "E005", "kind": "measurement"},
        ]
    }
