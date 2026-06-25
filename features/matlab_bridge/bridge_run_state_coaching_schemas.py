"""Pydantic schemas for MATLAB bridge run-state coaching."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingAltDirection as AltDirectionDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingEvidenceItem as EvidenceItemDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingLLMError as CoachingLLMErrorDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingPrimaryDirection as PrimaryDirectionDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingRequest as CoachingRequestDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingResult as CoachingResultDomain,
)
from core.domain.bridge_run_state_coaching import (
    BridgeRunStateCoachingSignalReading as SignalReadingDomain,
)
from features.matlab_bridge.bridge_run_state_schemas import _RUN_STATE_SENSITIVE_EXTRA_FIELDS

BridgeRunStateCoachingProtocolVersion = Literal["0.3-c1"]
BridgeRunStateCoachingNoticeVersion = Literal["run_state_coaching_v1"]
BridgeRunStateCoachingStatus = Literal["completed"]
BridgeRunStateCoachingMode = Literal["run_state_coaching"]
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
CoachingLLMErrorCode = Literal[
    "bridge_run_state_coaching_unavailable",
    "bridge_run_state_coaching_timeout",
    "bridge_run_state_coaching_failed",
    "bridge_run_state_coaching_busy",
]

MAX_CONTEXT_RUN_IDS = 5
MAX_SIGNAL_READINGS = 8
MAX_PRIMARY_DIRECTIONS = 2
MAX_ALTERNATIVES = 2
MAX_UNCERTAINTIES = 6
MAX_CAVEATS = 3
MAX_EVIDENCE_ITEMS = 16
MAX_READING_EVIDENCE_IDS = 6

_RunSummaryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
_ReadingText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]
_TrendText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
_UncertaintyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
_CaveatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
_EvidenceText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
_SignalRefText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
_EvidenceIdText = Annotated[str, StringConstraints(pattern=r"^e[0-9]{1,3}$")]
_ReadingIdText = Annotated[str, StringConstraints(pattern=r"^r[0-9]{1,3}$")]

_BIDI_CONTROL_CODEPOINTS = frozenset(
    {
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class _BridgeRunStateCoachingBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_extra_fields(cls, data: Any) -> Any:
        _reject_sensitive_keys(data)
        return data

    @field_validator("*")
    @classmethod
    def normalize_and_reject_unsafe_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_string(value)
        return value


class BridgeRunStateCoachingRequest(_BridgeRunStateCoachingBaseModel):
    protocol_version: BridgeRunStateCoachingProtocolVersion
    request_id: UUID
    session_id: UUID
    run_id: UUID
    run_state_coaching_consent_confirmed: StrictBool
    coaching_consent_notice_version: BridgeRunStateCoachingNoticeVersion
    previous_run_count: Annotated[StrictInt, Field(ge=0, le=4)]

    @field_validator("run_state_coaching_consent_confirmed")
    @classmethod
    def require_confirmed_coaching_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("run_state_coaching_consent_confirmed must be true")
        return value

    def to_domain(self) -> CoachingRequestDomain:
        return CoachingRequestDomain(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            session_id=self.session_id,
            run_id=self.run_id,
            run_state_coaching_consent_confirmed=self.run_state_coaching_consent_confirmed,
            coaching_consent_notice_version=self.coaching_consent_notice_version,
            previous_run_count=self.previous_run_count,
        )


class EvidenceItemModel(_BridgeRunStateCoachingBaseModel):
    evidence_id: _EvidenceIdText
    text: _EvidenceText
    signal_ref: _SignalRefText

    @classmethod
    def from_domain(cls, item: EvidenceItemDomain) -> Self:
        return cls.model_validate(item)

    def to_domain(self) -> EvidenceItemDomain:
        return EvidenceItemDomain(
            evidence_id=self.evidence_id,
            text=self.text,
            signal_ref=self.signal_ref,
        )


class SignalReadingModel(_BridgeRunStateCoachingBaseModel):
    reading_id: _ReadingIdText
    reading: _ReadingText
    is_inference: Literal[True]
    confidence: BridgeRunStateCoachingConfidence
    evidence_ids: Annotated[
        tuple[_EvidenceIdText, ...],
        Field(min_length=1, max_length=MAX_READING_EVIDENCE_IDS),
    ]

    @classmethod
    def from_domain(cls, reading: SignalReadingDomain) -> Self:
        return cls.model_validate(reading)

    def to_domain(self) -> SignalReadingDomain:
        return SignalReadingDomain(
            reading_id=self.reading_id,
            reading=self.reading,
            is_inference=self.is_inference,
            confidence=self.confidence,
            evidence_ids=tuple(self.evidence_ids),
        )


class AltDirectionModel(_BridgeRunStateCoachingBaseModel):
    action: BridgeRunStateCoachingAction
    magnitude_band: BridgeRunStateCoachingMagnitudeBand
    rationale_reading_id: _ReadingIdText

    @classmethod
    def from_domain(cls, direction: AltDirectionDomain) -> Self:
        return cls.model_validate(direction)

    def to_domain(self) -> AltDirectionDomain:
        return AltDirectionDomain(
            action=self.action,
            magnitude_band=self.magnitude_band,
            rationale_reading_id=self.rationale_reading_id,
        )


class PrimaryDirectionModel(_BridgeRunStateCoachingBaseModel):
    action: BridgeRunStateCoachingAction
    magnitude_band: BridgeRunStateCoachingMagnitudeBand
    rationale_reading_id: _ReadingIdText
    alternatives: Annotated[
        tuple[AltDirectionModel, ...],
        Field(min_length=0, max_length=MAX_ALTERNATIVES),
    ] = ()

    @classmethod
    def from_domain(cls, direction: PrimaryDirectionDomain) -> Self:
        return cls.model_validate(direction)

    def to_domain(self) -> PrimaryDirectionDomain:
        return PrimaryDirectionDomain(
            action=self.action,
            magnitude_band=self.magnitude_band,
            rationale_reading_id=self.rationale_reading_id,
            alternatives=tuple(direction.to_domain() for direction in self.alternatives),
        )


class BridgeRunStateCoachingResultModel(_BridgeRunStateCoachingBaseModel):
    protocol_version: BridgeRunStateCoachingProtocolVersion
    request_id: UUID
    run_id: UUID
    context_run_ids: Annotated[
        tuple[UUID, ...],
        Field(min_length=1, max_length=MAX_CONTEXT_RUN_IDS),
    ]
    status: BridgeRunStateCoachingStatus
    mode: BridgeRunStateCoachingMode
    outcome: BridgeRunStateCoachingOutcome
    run_summary: _RunSummaryText
    signal_readings: Annotated[
        tuple[SignalReadingModel, ...],
        Field(min_length=0, max_length=MAX_SIGNAL_READINGS),
    ]
    primary_directions: Annotated[
        tuple[PrimaryDirectionModel, ...],
        Field(min_length=0, max_length=MAX_PRIMARY_DIRECTIONS),
    ]
    cross_round_trend: _TrendText | None = None
    uncertainties: Annotated[
        tuple[_UncertaintyText, ...],
        Field(min_length=0, max_length=MAX_UNCERTAINTIES),
    ]
    fallback_reason: BridgeRunStateCoachingFallbackReason | None = None
    overall_confidence: BridgeRunStateCoachingConfidence
    evidence: Annotated[
        tuple[EvidenceItemModel, ...],
        Field(min_length=1, max_length=MAX_EVIDENCE_ITEMS),
    ]
    caveats: Annotated[
        tuple[_CaveatText, ...],
        Field(min_length=1, max_length=MAX_CAVEATS),
    ]

    @model_validator(mode="after")
    def validate_coaching_graph(self) -> Self:
        evidence_ids = [item.evidence_id for item in self.evidence]
        _validate_unique(evidence_ids, "evidence_id")
        evidence_set = set(evidence_ids)

        reading_ids = [reading.reading_id for reading in self.signal_readings]
        _validate_unique(reading_ids, "reading_id")
        reading_set = set(reading_ids)
        for reading in self.signal_readings:
            _validate_unique(reading.evidence_ids, "reading evidence_id")
            missing = [item for item in reading.evidence_ids if item not in evidence_set]
            if missing:
                raise ValueError("reading evidence_ids must reference evidence")

        for direction in self.primary_directions:
            if direction.rationale_reading_id not in reading_set:
                raise ValueError("direction rationale_reading_id must reference a reading")
            for alternative in direction.alternatives:
                if alternative.rationale_reading_id not in reading_set:
                    raise ValueError("alternative rationale_reading_id must reference a reading")

        if self.outcome == "coached":
            if not self.signal_readings:
                raise ValueError("coached outcome requires signal_readings")
            if not self.primary_directions:
                raise ValueError("coached outcome requires primary_directions")
            if self.fallback_reason is not None:
                raise ValueError("coached outcome must not include fallback_reason")
        else:
            if self.primary_directions:
                raise ValueError("insufficient_evidence must not include directions")
            if not self.uncertainties:
                raise ValueError("insufficient_evidence requires uncertainty")
            if self.fallback_reason is None:
                raise ValueError("insufficient_evidence requires fallback_reason")
            if self.overall_confidence != "low":
                raise ValueError("insufficient_evidence requires low confidence")
        return self

    @classmethod
    def from_domain(cls, result: CoachingResultDomain) -> Self:
        return cls.model_validate(result)

    def to_domain(self) -> CoachingResultDomain:
        return CoachingResultDomain(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            run_id=self.run_id,
            context_run_ids=tuple(self.context_run_ids),
            status=self.status,
            mode=self.mode,
            outcome=self.outcome,
            run_summary=self.run_summary,
            signal_readings=tuple(reading.to_domain() for reading in self.signal_readings),
            primary_directions=tuple(
                direction.to_domain() for direction in self.primary_directions
            ),
            cross_round_trend=self.cross_round_trend,
            uncertainties=tuple(self.uncertainties),
            fallback_reason=self.fallback_reason,
            overall_confidence=self.overall_confidence,
            evidence=tuple(item.to_domain() for item in self.evidence),
            caveats=tuple(self.caveats),
        )


class CoachingLLMError(_BridgeRunStateCoachingBaseModel):
    error: CoachingLLMErrorCode
    message: str

    @classmethod
    def from_domain(cls, error: CoachingLLMErrorDomain) -> Self:
        return cls.model_validate(error)

    def to_domain(self) -> CoachingLLMErrorDomain:
        return CoachingLLMErrorDomain(error=self.error, message=self.message)


def _validate_unique(values: Iterable[str], field_name: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{field_name} must be unique")
        seen.add(value)


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key.casefold() in _RUN_STATE_SENSITIVE_EXTRA_FIELDS:
                raise ValueError(f"sensitive fields are not accepted: {key}")
            _reject_sensitive_keys(nested)
    elif isinstance(value, list | tuple):
        for nested in value:
            _reject_sensitive_keys(nested)


def _normalize_string(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    for char in normalized:
        if char in _BIDI_CONTROL_CODEPOINTS:
            raise ValueError("string fields must not contain bidi control characters")
        if unicodedata.category(char) == "Cc":
            raise ValueError("string fields must not contain control characters")
    return normalized
