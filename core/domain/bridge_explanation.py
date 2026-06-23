"""Pure domain contracts for MATLAB bridge error explanation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class BridgeExplanationRequest:
    protocol_version: Literal["0.3-b1"]
    request_id: UUID
    diagnostic_kind: Literal["manual_error", "auto_captured_error"]
    matlab_release: str
    client_version: str
    error_text: str
    llm_processing_consent_confirmed: bool


@dataclass(frozen=True)
class LikelyCause:
    cause: str
    is_inference: Literal[True]
    confidence: Literal["low", "medium"]
    supporting_signals: list[str]


@dataclass(frozen=True)
class NextStep:
    action: str


@dataclass(frozen=True)
class BridgeExplanationResult:
    protocol_version: Literal["0.3-b1"]
    request_id: UUID
    status: Literal["completed"]
    mode: Literal["llm_error_explanation"]
    meaning: str
    likely_causes: list[LikelyCause]
    next_steps: list[NextStep]
    caveats: list[str]
