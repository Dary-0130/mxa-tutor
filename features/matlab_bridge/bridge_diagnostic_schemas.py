"""Pydantic schemas for the MATLAB diagnostic bridge contract."""

from __future__ import annotations

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

from core.domain.bridge_diagnostic import BridgeDiagnostic, BridgeDiagnosticReceipt

BridgeProtocolVersion = Literal["0.3-a"]
BridgeDiagnosticKind = Literal["manual_error"]
BridgeReceiptStatus = Literal["received"]
BridgeReceiptMode = Literal["connectivity_stub"]
BridgeErrorCode = Literal[
    "matlab_bridge_forbidden",
    "bridge_payload_too_large",
    "bridge_unsupported_media_type",
]

SENSITIVE_EXTRA_FIELDS = frozenset(
    {
        "file_path",
        "source_code",
        "slx_path",
        "workspace",
        "stack",
        "project_files",
        "model_content",
        "files",
    }
)


class _BridgeBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class BridgeDiagnosticRequest(_BridgeBaseModel):
    protocol_version: BridgeProtocolVersion
    request_id: UUID4
    diagnostic_kind: BridgeDiagnosticKind
    matlab_release: str = Field(pattern=r"^R20[0-9]{2}[ab]$")
    client_version: str = Field(pattern=r"^[A-Za-z0-9.\-]{1,32}$")
    error_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
    ]
    consent_confirmed: StrictBool

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

    @field_validator("consent_confirmed")
    @classmethod
    def require_confirmed_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("consent_confirmed must be true")
        return value

    def to_domain(self) -> BridgeDiagnostic:
        return BridgeDiagnostic(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            diagnostic_kind=self.diagnostic_kind,
            matlab_release=self.matlab_release,
            client_version=self.client_version,
            error_text=self.error_text,
            consent_confirmed=self.consent_confirmed,
        )


class BridgeDiagnosticReceiptModel(_BridgeBaseModel):
    request_id: UUID4
    status: BridgeReceiptStatus
    mode: BridgeReceiptMode
    message: str

    @classmethod
    def from_domain(cls, receipt: BridgeDiagnosticReceipt) -> Self:
        return cls.model_validate(receipt)


class BridgeErrorResponse(_BridgeBaseModel):
    error: BridgeErrorCode
    message: str
