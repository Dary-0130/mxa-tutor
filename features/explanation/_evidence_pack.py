"""EvidencePack schema for simulation explanation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Literal

from core.domain.source_ref import SourceRef

from ._score_types import SelectionDiagnostics

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

EvidenceKind = Literal[
    "project_overview_field",
    "slx_block",
    "slx_line",
    "signal_path",
    "subsystem",
    "parameter",
    "goto_from_tag",
    "bus_signal",
    "measurement",
    "scope",
    "m_file",
    "m_function",
    "mat_variable",
    "simulink_caveat",
]

ParameterRoleGuess = Literal[
    "initial_value",
    "gain",
    "operating_point",
    "grid_equivalent",
    "sample_time",
    "protection",
    "observation",
    "placeholder",
    "unknown",
]


@dataclass(frozen=True)
class EndpointRef:
    block_id: str | None
    block_name: str
    block_type: str | None
    port: str | None = None
    signal_name: str | None = None


@dataclass(frozen=True)
class SignalPathPayload:
    """Payload for signal_path / slx_line / goto_from_tag / bus_signal evidence."""

    source: EndpointRef | None
    via: list[EndpointRef]
    target: EndpointRef | None
    path_length: int
    tags: list[str]


@dataclass(frozen=True)
class ParameterContextPayload:
    """Payload for parameter evidence."""

    parameter_name: str
    value: str
    block_ref: EndpointRef
    role_guess: ParameterRoleGuess
    is_default_value: bool
    downstream_endpoints: list[EndpointRef]
    evidence_for_inference: list[str]
    confidence: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    kind: EvidenceKind
    source_ref: SourceRef
    summary: str
    payload: dict[str, JsonValue]

    def to_dict(self) -> dict[str, JsonValue]:
        return _jsonify(asdict(self))


@dataclass(frozen=True)
class EvidencePack:
    project_id: str
    project_name: str
    schema_version: str
    evidence: list[EvidenceItem]
    selection_diagnostics: SelectionDiagnostics
    builder_notes: list[str]

    def to_dict(self) -> dict[str, JsonValue]:
        return _jsonify(asdict(self))


def _jsonify(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, tuple | list):
        return [_jsonify(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _jsonify(value.model_dump())
    if is_dataclass(value):
        return _jsonify(asdict(value))
    return str(value)
