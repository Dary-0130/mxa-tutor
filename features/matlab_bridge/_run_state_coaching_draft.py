"""Feature-private LLM draft schema for run-state coaching."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

DraftOutcome = Literal["coached", "insufficient_evidence"]
DraftConfidence = Literal["low", "medium"]
DraftAction = Literal["increase", "decrease", "hold", "compare"]
DraftMagnitudeBand = Literal["slight", "moderate", "large"]
DraftFallbackReason = Literal[
    "no_metrics_or_series",
    "run_status_unknown",
    "insufficient_signal",
    "conflicting_signals",
]

_ReadingId = Annotated[str, StringConstraints(pattern=r"^r[0-9]{1,3}$")]
_EvidenceId = Annotated[str, StringConstraints(pattern=r"^e[0-9]{1,3}$")]
_ReadingText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]
_TrendText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
_UncertaintyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class _DraftBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftSignalReading(_DraftBaseModel):
    reading_id: _ReadingId
    reading: _ReadingText
    is_inference: Literal[True]
    confidence: DraftConfidence
    evidence_ids: Annotated[tuple[_EvidenceId, ...], Field(min_length=1, max_length=6)]


class DraftAltDirection(_DraftBaseModel):
    action: DraftAction
    magnitude_band: DraftMagnitudeBand
    rationale_reading_id: _ReadingId


class DraftPrimaryDirection(_DraftBaseModel):
    action: DraftAction
    magnitude_band: DraftMagnitudeBand
    rationale_reading_id: _ReadingId
    alternatives: Annotated[tuple[DraftAltDirection, ...], Field(max_length=2)] = ()


class CoachingDraft(_DraftBaseModel):
    outcome: DraftOutcome
    signal_readings: Annotated[tuple[DraftSignalReading, ...], Field(max_length=8)] = ()
    primary_directions: Annotated[tuple[DraftPrimaryDirection, ...], Field(max_length=2)] = ()
    cross_round_trend: _TrendText | None = None
    uncertainties: Annotated[tuple[_UncertaintyText, ...], Field(max_length=6)] = ()
    fallback_reason: DraftFallbackReason | None = None

    @model_validator(mode="after")
    def validate_draft_shape(self) -> Self:
        evidence_seen: set[str] = set()
        for reading in self.signal_readings:
            if reading.reading_id in evidence_seen:
                raise ValueError("reading_id must be unique")
            evidence_seen.add(reading.reading_id)

        reading_ids = {reading.reading_id for reading in self.signal_readings}
        for direction in self.primary_directions:
            if direction.rationale_reading_id not in reading_ids:
                raise ValueError("direction rationale_reading_id must reference a reading")
            for alternative in direction.alternatives:
                if alternative.rationale_reading_id not in reading_ids:
                    raise ValueError("alternative rationale_reading_id must reference a reading")

        if self.outcome == "coached":
            if not self.signal_readings or not self.primary_directions:
                raise ValueError("coached outcome requires readings and directions")
            if self.fallback_reason is not None:
                raise ValueError("coached outcome must not include fallback_reason")
            return self

        if self.primary_directions:
            raise ValueError("insufficient_evidence must not include directions")
        if not self.uncertainties:
            raise ValueError("insufficient_evidence requires uncertainty")
        if self.fallback_reason is None:
            raise ValueError("insufficient_evidence requires fallback_reason")
        return self
