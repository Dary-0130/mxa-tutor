"""Pure domain contracts for MATLAB bridge run-state coaching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

BridgeRunStateCoachingProtocolVersion = Literal["0.3-c1"]
BridgeRunStateCoachingConsentNoticeVersion = Literal["run_state_coaching_v1"]
BridgeRunStateCoachingOutcome = Literal["coached", "insufficient_evidence"]
BridgeRunStateCoachingConfidence = Literal["low", "medium"]
BridgeRunStateCoachingAction = Literal["increase", "decrease", "hold", "compare"]
BridgeRunStateCoachingMagnitudeBand = Literal["slight", "moderate", "large"]
BridgeRunStateCoachingFallbackReason = Literal[
    "no_metrics_or_series",
    "run_status_unknown",
    "insufficient_signal",
    "conflicting_signals",
]
BridgeRunStateCoachingErrorCode = Literal[
    "bridge_run_state_coaching_unavailable",
    "bridge_run_state_coaching_timeout",
    "bridge_run_state_coaching_failed",
    "bridge_run_state_coaching_busy",
]


@dataclass(frozen=True)
class BridgeRunStateCoachingRequest:
    protocol_version: BridgeRunStateCoachingProtocolVersion
    request_id: UUID
    session_id: UUID
    run_id: UUID
    run_state_coaching_consent_confirmed: bool
    coaching_consent_notice_version: BridgeRunStateCoachingConsentNoticeVersion
    previous_run_count: int


@dataclass(frozen=True)
class BridgeRunStateCoachingEvidenceItem:
    evidence_id: str
    text: str
    signal_ref: str


@dataclass(frozen=True)
class BridgeRunStateCoachingSignalReading:
    reading_id: str
    reading: str
    is_inference: Literal[True]
    confidence: BridgeRunStateCoachingConfidence
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class BridgeRunStateCoachingAltDirection:
    action: BridgeRunStateCoachingAction
    magnitude_band: BridgeRunStateCoachingMagnitudeBand
    rationale_reading_id: str


@dataclass(frozen=True)
class BridgeRunStateCoachingPrimaryDirection:
    action: BridgeRunStateCoachingAction
    magnitude_band: BridgeRunStateCoachingMagnitudeBand
    rationale_reading_id: str
    alternatives: tuple[BridgeRunStateCoachingAltDirection, ...]


@dataclass(frozen=True)
class BridgeRunStateCoachingResult:
    protocol_version: BridgeRunStateCoachingProtocolVersion
    request_id: UUID
    run_id: UUID
    context_run_ids: tuple[UUID, ...]
    status: Literal["completed"]
    mode: Literal["run_state_coaching"]
    outcome: BridgeRunStateCoachingOutcome
    run_summary: str
    signal_readings: tuple[BridgeRunStateCoachingSignalReading, ...]
    primary_directions: tuple[BridgeRunStateCoachingPrimaryDirection, ...]
    cross_round_trend: str | None
    uncertainties: tuple[str, ...]
    fallback_reason: BridgeRunStateCoachingFallbackReason | None
    overall_confidence: BridgeRunStateCoachingConfidence
    evidence: tuple[BridgeRunStateCoachingEvidenceItem, ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class BridgeRunStateCoachingLLMError:
    error: BridgeRunStateCoachingErrorCode
    message: str
