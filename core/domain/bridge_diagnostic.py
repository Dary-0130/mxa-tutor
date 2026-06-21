"""Pure domain contracts for the MATLAB diagnostic bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class BridgeDiagnostic:
    protocol_version: Literal["0.3-a"]
    request_id: UUID
    diagnostic_kind: Literal["manual_error"]
    matlab_release: str
    client_version: str
    error_text: str
    consent_confirmed: bool


@dataclass(frozen=True)
class BridgeDiagnosticReceipt:
    request_id: UUID
    status: Literal["received"]
    mode: Literal["connectivity_stub"]
    message: str
