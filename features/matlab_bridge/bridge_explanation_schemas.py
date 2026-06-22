"""Pydantic schemas for MATLAB bridge error explanation."""

from __future__ import annotations

import string
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from core.domain.bridge_explanation import (
    BridgeExplanationRequest as BridgeExplanationRequestDomain,
)
from core.domain.bridge_explanation import (
    BridgeExplanationResult as BridgeExplanationResultDomain,
)
from core.domain.bridge_explanation import (
    LikelyCause as LikelyCauseDomain,
)
from core.domain.bridge_explanation import (
    NextStep as NextStepDomain,
)
from features.matlab_bridge.bridge_diagnostic_schemas import SENSITIVE_EXTRA_FIELDS

BridgeExplanationProtocolVersion = Literal["0.3-b1"]
BridgeExplanationDiagnosticKind = Literal["manual_error"]
BridgeExplanationStatus = Literal["completed"]
BridgeExplanationMode = Literal["llm_error_explanation"]
BridgeExplanationErrorCode = Literal[
    "bridge_explanation_failed",
    "bridge_explanation_unavailable",
    "bridge_explanation_timeout",
]
BridgeExplanationConfidence = Literal["low", "medium"]

MAX_SUPPORTING_SIGNALS = 6

_Text1To400 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
_SignalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=200)]


class _BridgeExplanationBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class BridgeExplanationRequest(_BridgeExplanationBaseModel):
    protocol_version: BridgeExplanationProtocolVersion
    request_id: UUID4
    diagnostic_kind: BridgeExplanationDiagnosticKind
    matlab_release: str = Field(pattern=r"^R20[0-9]{2}[ab]$")
    client_version: str = Field(pattern=r"^[A-Za-z0-9.\-]{1,32}$")
    error_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
    ]
    llm_processing_consent_confirmed: StrictBool

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_extra_fields(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            forbidden = SENSITIVE_EXTRA_FIELDS.intersection(data)
            if forbidden:
                names = ", ".join(sorted(forbidden))
                raise ValueError(f"sensitive fields are not accepted: {names}")
        return data

    @field_validator("error_text")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("error_text must not contain NUL")
        return value

    @field_validator("llm_processing_consent_confirmed")
    @classmethod
    def require_confirmed_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("llm_processing_consent_confirmed must be true")
        return value

    def to_domain(self) -> BridgeExplanationRequestDomain:
        return BridgeExplanationRequestDomain(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            diagnostic_kind=self.diagnostic_kind,
            matlab_release=self.matlab_release,
            client_version=self.client_version,
            error_text=self.error_text,
            llm_processing_consent_confirmed=self.llm_processing_consent_confirmed,
        )


class LikelyCauseModel(_BridgeExplanationBaseModel):
    cause: _Text1To400
    is_inference: Literal[True]
    confidence: BridgeExplanationConfidence
    supporting_signals: list[_SignalText] = Field(
        min_length=1,
        max_length=MAX_SUPPORTING_SIGNALS,
    )

    @field_validator("supporting_signals")
    @classmethod
    def reject_unhelpful_signals(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for signal in value:
            normalized = " ".join(signal.split())
            if normalized in seen:
                raise ValueError("supporting_signals must not contain duplicates")
            seen.add(normalized)
            stripped = normalized.strip()
            if stripped in {"[REDACTED_PATH]", "[REDACTED_SECRET]", "[REDACTED_SOURCE]"}:
                raise ValueError("supporting_signals must not be only redaction placeholders")
            if all(
                char in string.punctuation + "，。；：、（）【】[](){}<>《》“”‘’"
                for char in stripped
            ):
                raise ValueError("supporting_signals must include meaningful text")
        return value

    def to_domain(self) -> LikelyCauseDomain:
        return LikelyCauseDomain(
            cause=self.cause,
            is_inference=self.is_inference,
            confidence=self.confidence,
            supporting_signals=list(self.supporting_signals),
        )


class NextStepModel(_BridgeExplanationBaseModel):
    action: _Text1To400

    def to_domain(self) -> NextStepDomain:
        return NextStepDomain(action=self.action)


class BridgeExplanationResultModel(_BridgeExplanationBaseModel):
    protocol_version: BridgeExplanationProtocolVersion
    request_id: UUID4
    status: BridgeExplanationStatus
    mode: BridgeExplanationMode
    meaning: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1500),
    ]
    likely_causes: list[LikelyCauseModel] = Field(min_length=1, max_length=4)
    next_steps: list[NextStepModel] = Field(min_length=1, max_length=5)
    caveats: list[_Text1To400] = Field(min_length=1, max_length=3)

    @classmethod
    def from_domain(cls, result: BridgeExplanationResultDomain) -> Self:
        return cls.model_validate(result)

    def to_domain(self) -> BridgeExplanationResultDomain:
        return BridgeExplanationResultDomain(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            status=self.status,
            mode=self.mode,
            meaning=self.meaning,
            likely_causes=[cause.to_domain() for cause in self.likely_causes],
            next_steps=[step.to_domain() for step in self.next_steps],
            caveats=list(self.caveats),
        )


class BridgeExplanationErrorResponse(_BridgeExplanationBaseModel):
    error: BridgeExplanationErrorCode
    message: str
