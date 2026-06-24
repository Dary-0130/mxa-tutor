"""Pydantic schemas for MATLAB bridge run-state snapshots."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from core.domain.bridge_run_state import (
    BridgeRunStateEnvelopeSeries as BridgeRunStateEnvelopeSeriesDomain,
)
from core.domain.bridge_run_state import (
    BridgeRunStateIdentitySeries as BridgeRunStateIdentitySeriesDomain,
)
from core.domain.bridge_run_state import BridgeRunStateMetric as BridgeRunStateMetricDomain
from core.domain.bridge_run_state import BridgeRunStateReceipt as BridgeRunStateReceiptDomain
from core.domain.bridge_run_state import BridgeRunStateRequest as BridgeRunStateRequestDomain
from core.domain.bridge_run_state import BridgeRunStateSeries as BridgeRunStateSeriesDomain
from features.matlab_bridge.bridge_diagnostic_schemas import SENSITIVE_EXTRA_FIELDS

BridgeRunStateProtocolVersion = Literal["0.3-b3"]
BridgeRunStateStatus = Literal["completed", "stopped", "execution_error", "unknown"]
BridgeRunStateConvergenceStatus = Literal[
    "converged",
    "not_converged",
    "not_applicable",
    "unknown",
]
BridgeRunStateContainerStatus = Literal[
    "available",
    "unavailable",
    "not_applicable",
    "unknown",
]
BridgeRunStateUnitStatus = Literal["known", "unknown", "not_applicable"]
BridgeRunStateTimeUnit = Literal["s", "ms", "us", "unknown"]
BridgeRunStateSampleOrder = Literal["chronological"]
BridgeRunStateReceiptStatus = Literal["validated"]
BridgeRunStateReceiptMode = Literal["ephemeral_validation"]

MAX_RUN_SEQUENCE = 1_000_000
MAX_RUN_STATE_METRICS = 16
MAX_RUN_STATE_SERIES = 4
MAX_IDENTITY_POINTS = 192
ENVELOPE_BUCKET_COUNT = 96
RUN_STATE_UNIFORM_REL_TOL = 1e-6

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
_RUN_STATE_SENSITIVE_EXTRA_FIELDS = frozenset(
    {
        *SENSITIVE_EXTRA_FIELDS,
        "archive",
        "base_workspace",
        "base64",
        "blob",
        "compressed",
        "csv_path",
        "dump",
        "file_content",
        "machine_name",
        "mat_path",
        "matlab_path",
        "model_file_path",
        "model_info",
        "raw_csv",
        "raw_mat",
        "raw_workspace",
        "simulink_model",
        "user_id",
        "userid",
        "workspace_dump",
    }
)

_ShortText32 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
_StopReasonText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
_SolverText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
_UnitText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)]
_SeriesIdText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9._\-]{1,32}$"),
]
_FiniteFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]
_PositiveFiniteFloat = Annotated[StrictFloat, Field(gt=0, allow_inf_nan=False)]


class _BridgeRunStateBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_extra_fields(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            _reject_sensitive_keys(data)
        return data

    @field_validator("*")
    @classmethod
    def normalize_and_reject_unsafe_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _normalize_string(value)
        return value


class BridgeRunStateMetricModel(_BridgeRunStateBaseModel):
    name: _ShortText32
    value: _FiniteFloat
    unit_status: BridgeRunStateUnitStatus
    unit: _UnitText | None = None

    @model_validator(mode="before")
    @classmethod
    def require_unit_only_when_known(cls, data: Any) -> Any:
        _validate_optional_unit_field(data, "unit_status", "unit")
        return data

    @field_validator("name")
    @classmethod
    def enforce_name_byte_limit(cls, value: str) -> str:
        return _require_utf8_bytes(value, 96, "name")

    @field_validator("unit")
    @classmethod
    def enforce_unit_byte_limit(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_utf8_bytes(value, 48, "unit")

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        return _require_finite(value, "value")

    def to_domain(self) -> BridgeRunStateMetricDomain:
        return BridgeRunStateMetricDomain(
            name=self.name,
            value=self.value,
            unit_status=self.unit_status,
            unit=self.unit,
        )


class _BridgeRunStateSeriesBaseModel(_BridgeRunStateBaseModel):
    @model_validator(mode="before")
    @classmethod
    def require_value_unit_only_when_known(cls, data: Any) -> Any:
        _validate_optional_unit_field(data, "value_unit_status", "value_unit")
        return data

    @field_validator("series_id", check_fields=False)
    @classmethod
    def enforce_series_id_byte_limit(cls, value: str) -> str:
        return _require_utf8_bytes(value, 96, "series_id")

    @field_validator("label", check_fields=False)
    @classmethod
    def enforce_label_byte_limit(cls, value: str) -> str:
        return _require_utf8_bytes(value, 96, "label")

    @field_validator("value_unit", check_fields=False)
    @classmethod
    def enforce_value_unit_byte_limit(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_utf8_bytes(value, 48, "value_unit")


class BridgeRunStateIdentitySeriesModel(_BridgeRunStateSeriesBaseModel):
    representation: Literal["identity_uniform_v1"]
    series_id: _SeriesIdText
    label: _ShortText32
    time_unit: BridgeRunStateTimeUnit
    value_unit_status: BridgeRunStateUnitStatus
    sample_order: BridgeRunStateSampleOrder
    source_point_count: Annotated[StrictInt, Field(ge=2, le=MAX_IDENTITY_POINTS)]
    t_start: _FiniteFloat
    t_step: _PositiveFiniteFloat
    y: Annotated[tuple[_FiniteFloat, ...], Field(min_length=2, max_length=MAX_IDENTITY_POINTS)]
    value_unit: _UnitText | None = None

    @field_validator("t_start", "t_step")
    @classmethod
    def require_finite_scalar(cls, value: float) -> float:
        return _require_finite(value, "series_scalar")

    @field_validator("y")
    @classmethod
    def require_finite_y(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        return _require_finite_values(value, "y")

    @model_validator(mode="after")
    def validate_identity_lengths(self) -> Self:
        if self.source_point_count != len(self.y):
            raise ValueError("source_point_count must match y length")
        return self

    @classmethod
    def from_domain(cls, series: BridgeRunStateIdentitySeriesDomain) -> Self:
        return cls.model_validate(series)

    def to_domain(self) -> BridgeRunStateIdentitySeriesDomain:
        return BridgeRunStateIdentitySeriesDomain(
            representation=self.representation,
            series_id=self.series_id,
            label=self.label,
            time_unit=self.time_unit,
            value_unit_status=self.value_unit_status,
            sample_order=self.sample_order,
            source_point_count=self.source_point_count,
            t_start=self.t_start,
            t_step=self.t_step,
            y=self.y,
            value_unit=self.value_unit,
        )


class BridgeRunStateEnvelopeSeriesModel(_BridgeRunStateSeriesBaseModel):
    representation: Literal["min_max_envelope_uniform_v1"]
    series_id: _SeriesIdText
    label: _ShortText32
    time_unit: BridgeRunStateTimeUnit
    value_unit_status: BridgeRunStateUnitStatus
    sample_order: BridgeRunStateSampleOrder
    source_point_count: Annotated[StrictInt, Field(gt=MAX_IDENTITY_POINTS)]
    t_start: _FiniteFloat
    bucket_width: _PositiveFiniteFloat
    y_min: Annotated[
        tuple[_FiniteFloat, ...],
        Field(min_length=ENVELOPE_BUCKET_COUNT, max_length=ENVELOPE_BUCKET_COUNT),
    ]
    y_max: Annotated[
        tuple[_FiniteFloat, ...],
        Field(min_length=ENVELOPE_BUCKET_COUNT, max_length=ENVELOPE_BUCKET_COUNT),
    ]
    value_unit: _UnitText | None = None

    @field_validator("t_start", "bucket_width")
    @classmethod
    def require_finite_scalar(cls, value: float) -> float:
        return _require_finite(value, "series_scalar")

    @field_validator("y_min", "y_max")
    @classmethod
    def require_finite_envelope(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        return _require_finite_values(value, "envelope")

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if len(self.y_min) != len(self.y_max):
            raise ValueError("y_min and y_max must have the same length")
        for low, high in zip(self.y_min, self.y_max, strict=True):
            if low > high:
                raise ValueError("y_min must be less than or equal to y_max")
        return self

    @classmethod
    def from_domain(cls, series: BridgeRunStateEnvelopeSeriesDomain) -> Self:
        return cls.model_validate(series)

    def to_domain(self) -> BridgeRunStateEnvelopeSeriesDomain:
        return BridgeRunStateEnvelopeSeriesDomain(
            representation=self.representation,
            series_id=self.series_id,
            label=self.label,
            time_unit=self.time_unit,
            value_unit_status=self.value_unit_status,
            sample_order=self.sample_order,
            source_point_count=self.source_point_count,
            t_start=self.t_start,
            bucket_width=self.bucket_width,
            y_min=self.y_min,
            y_max=self.y_max,
            value_unit=self.value_unit,
        )


BridgeRunStateSeriesModel = Annotated[
    BridgeRunStateIdentitySeriesModel | BridgeRunStateEnvelopeSeriesModel,
    Field(discriminator="representation"),
]


class BridgeRunStateRequest(_BridgeRunStateBaseModel):
    protocol_version: BridgeRunStateProtocolVersion
    request_id: UUID
    session_id: UUID
    run_id: UUID
    run_sequence: Annotated[StrictInt, Field(ge=0, le=MAX_RUN_SEQUENCE)]
    matlab_release: str = Field(pattern=r"^R20[0-9]{2}[ab]$")
    client_version: str = Field(pattern=r"^[A-Za-z0-9.\-]{1,32}$")
    run_state_sharing_consent_confirmed: StrictBool
    run_status: BridgeRunStateStatus
    convergence_status: BridgeRunStateConvergenceStatus
    stop_reason: _StopReasonText | None = None
    solver: _SolverText | None = None
    metrics_status: BridgeRunStateContainerStatus
    metrics: Annotated[
        tuple[BridgeRunStateMetricModel, ...],
        Field(max_length=MAX_RUN_STATE_METRICS),
    ]
    series_status: BridgeRunStateContainerStatus
    series: Annotated[
        tuple[BridgeRunStateSeriesModel, ...],
        Field(max_length=MAX_RUN_STATE_SERIES),
    ]

    @field_validator("stop_reason")
    @classmethod
    def enforce_stop_reason_byte_limit(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_utf8_bytes(value, 480, "stop_reason")

    @field_validator("solver")
    @classmethod
    def enforce_solver_byte_limit(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_utf8_bytes(value, 96, "solver")

    @field_validator("run_state_sharing_consent_confirmed")
    @classmethod
    def require_confirmed_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("run_state_sharing_consent_confirmed must be true")
        return value

    @model_validator(mode="after")
    def validate_cross_fields(self) -> Self:
        if (
            self.convergence_status in {"converged", "not_converged"}
            and self.run_status != "completed"
        ):
            raise ValueError("convergence requires run_status=completed")
        _validate_container_status(self.metrics_status, self.metrics, "metrics")
        _validate_container_status(self.series_status, self.series, "series")
        _validate_unique([metric.name for metric in self.metrics], "metric name")
        _validate_unique([series.series_id for series in self.series], "series_id")
        return self

    @classmethod
    def from_domain(cls, request: BridgeRunStateRequestDomain) -> Self:
        return cls.model_validate(request)

    def to_domain(self) -> BridgeRunStateRequestDomain:
        return BridgeRunStateRequestDomain(
            protocol_version=self.protocol_version,
            request_id=self.request_id,
            session_id=self.session_id,
            run_id=self.run_id,
            run_sequence=self.run_sequence,
            matlab_release=self.matlab_release,
            client_version=self.client_version,
            run_state_sharing_consent_confirmed=self.run_state_sharing_consent_confirmed,
            run_status=self.run_status,
            convergence_status=self.convergence_status,
            stop_reason=self.stop_reason,
            solver=self.solver,
            metrics_status=self.metrics_status,
            metrics=tuple(metric.to_domain() for metric in self.metrics),
            series=tuple(_series_to_domain(series) for series in self.series),
            series_status=self.series_status,
        )


class BridgeRunStateReceiptModel(_BridgeRunStateBaseModel):
    status: BridgeRunStateReceiptStatus
    mode: BridgeRunStateReceiptMode
    durable: Literal[False]
    request_id: UUID
    run_id: UUID
    run_sequence: Annotated[StrictInt, Field(ge=0, le=MAX_RUN_SEQUENCE)]

    @classmethod
    def from_domain(cls, receipt: BridgeRunStateReceiptDomain) -> Self:
        return cls.model_validate(receipt)

    def to_domain(self) -> BridgeRunStateReceiptDomain:
        return BridgeRunStateReceiptDomain(
            status=self.status,
            mode=self.mode,
            durable=self.durable,
            request_id=self.request_id,
            run_id=self.run_id,
            run_sequence=self.run_sequence,
        )


def _series_to_domain(series: BridgeRunStateSeriesModel) -> BridgeRunStateSeriesDomain:
    if isinstance(series, BridgeRunStateIdentitySeriesModel):
        return series.to_domain()
    return series.to_domain()


def _validate_optional_unit_field(data: Any, status_field: str, unit_field: str) -> None:
    if not isinstance(data, Mapping):
        return
    status = data.get(status_field)
    has_unit = unit_field in data
    if status == "known":
        if not has_unit or data.get(unit_field) is None:
            raise ValueError(f"{unit_field} is required when {status_field}=known")
        return
    if has_unit:
        raise ValueError(f"{unit_field} is only accepted when {status_field}=known")


def _validate_container_status(status: str, values: tuple[object, ...], field_name: str) -> None:
    if status == "available":
        if not values:
            raise ValueError(f"{field_name}_status=available requires non-empty {field_name}")
        return
    if values:
        raise ValueError(f"{field_name} must be empty unless {field_name}_status=available")


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


def _require_utf8_bytes(value: str, max_bytes: int, field_name: str) -> str:
    if len(value.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field_name} exceeds UTF-8 byte limit")
    return value


def _require_finite(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


def _require_finite_values(values: tuple[float, ...], field_name: str) -> tuple[float, ...]:
    for value in values:
        _require_finite(value, field_name)
    return values
