from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from features.matlab_bridge.bridge_run_state_schemas import (
    ENVELOPE_BUCKET_COUNT,
    RUN_STATE_UNIFORM_REL_TOL,
    BridgeRunStateEnvelopeSeriesModel,
    BridgeRunStateIdentitySeriesModel,
    BridgeRunStateMetricModel,
    BridgeRunStateReceiptModel,
    BridgeRunStateRequest,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


def _metric(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "wall_clock_elapsed",
        "value": 1.25,
        "unit_status": "known",
        "unit": "s",
    }
    payload.update(overrides)
    return payload


def _identity_series(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "representation": "identity_uniform_v1",
        "series_id": "simout",
        "label": "simout",
        "time_unit": "s",
        "value_unit_status": "unknown",
        "sample_order": "chronological",
        "source_point_count": 4,
        "t_start": 0.0,
        "t_step": 0.1,
        "y": [0.0, 1.0, 0.0, -1.0],
    }
    payload.update(overrides)
    return payload


def _envelope_series(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "representation": "min_max_envelope_uniform_v1",
        "series_id": "simout",
        "label": "simout",
        "time_unit": "s",
        "value_unit_status": "known",
        "value_unit": "V",
        "sample_order": "chronological",
        "source_point_count": 193,
        "t_start": 0.0,
        "bucket_width": 0.01,
        "y_min": [0.0] * ENVELOPE_BUCKET_COUNT,
        "y_max": [1.0] * ENVELOPE_BUCKET_COUNT,
    }
    payload.update(overrides)
    return payload


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b4",
        "request_id": REQUEST_ID,
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_sequence": 7,
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "run_state_sharing_consent_confirmed": True,
        "consent_notice_version": "run_state_persistence_v1",
        "run_status": "completed",
        "convergence_status": "not_applicable",
        "stop_reason": "ReachedStopTime",
        "solver": "ode45",
        "metrics_status": "available",
        "metrics": [_metric()],
        "series_status": "available",
        "series": [_identity_series()],
    }
    payload.update(overrides)
    return payload


def test_valid_request_converts_to_deeply_immutable_domain() -> None:
    request = BridgeRunStateRequest.model_validate(_valid_payload())

    domain = request.to_domain()

    assert domain.protocol_version == "0.3-b4"
    assert domain.request_id == UUID(REQUEST_ID)
    assert domain.session_id == UUID(SESSION_ID)
    assert domain.run_id == UUID(RUN_ID)
    assert domain.metrics[0].name == "wall_clock_elapsed"
    assert domain.series[0].series_id == "simout"
    assert isinstance(domain.metrics, tuple)
    assert isinstance(domain.series, tuple)
    assert isinstance(domain.series[0].y, tuple)


def test_request_from_domain_and_receipt_round_trip() -> None:
    request = BridgeRunStateRequest.model_validate(_valid_payload())
    domain = request.to_domain()

    rebuilt = BridgeRunStateRequest.from_domain(domain)
    receipt = BridgeRunStateReceiptModel.model_validate(
        {
            "protocol_version": "0.3-b4",
            "status": "persisted",
            "mode": "durable_persisted",
            "durable": True,
            "request_id": REQUEST_ID,
            "run_id": RUN_ID,
            "run_sequence": 7,
        }
    )

    assert rebuilt.model_dump(mode="json") == request.model_dump(mode="json")
    assert BridgeRunStateReceiptModel.from_domain(receipt.to_domain()).model_dump(mode="json") == {
        "protocol_version": "0.3-b4",
        "status": "persisted",
        "mode": "durable_persisted",
        "durable": True,
        "request_id": REQUEST_ID,
        "run_id": RUN_ID,
        "run_sequence": 7,
    }


@pytest.mark.parametrize(
    "override",
    [
        {"protocol_version": "0.3-b2"},
        {"protocol_version": "0.3-b3"},
        {"run_sequence": -1},
        {"run_sequence": 1_000_001},
        {"run_sequence": True},
        {"run_sequence": "7"},
        {"run_state_sharing_consent_confirmed": False},
        {"run_state_sharing_consent_confirmed": 1},
        {"consent_notice_version": "run_state_ephemeral_v1"},
        {"run_status": "failed"},
        {"convergence_status": "done"},
        {"matlab_release": "R2026c"},
        {"client_version": "bad version!"},
    ],
)
def test_top_level_boundaries_are_rejected(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(_valid_payload(**override))


@pytest.mark.parametrize(
    "value",
    [True, "1.0", None, float("nan"), float("inf"), -float("inf")],
)
def test_numeric_values_reject_bool_string_null_and_non_finite(value: object) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(_valid_payload(metrics=[_metric(value=value)]))


def test_json_integer_metric_value_is_accepted_as_float() -> None:
    request = BridgeRunStateRequest.model_validate(_valid_payload(metrics=[_metric(value=1)]))

    assert request.metrics[0].value == 1.0


@pytest.mark.parametrize(
    "payload",
    [
        _valid_payload(run_status="stopped", convergence_status="converged"),
        _valid_payload(metrics_status="available", metrics=[]),
        _valid_payload(metrics_status="unknown", metrics=[_metric()]),
        _valid_payload(series_status="available", series=[]),
        _valid_payload(series_status="not_applicable", series=[_identity_series()]),
        _valid_payload(metrics=[_metric(name="dup"), _metric(name="dup")]),
        _valid_payload(
            series=[_identity_series(series_id="dup"), _identity_series(series_id="dup")]
        ),
    ],
)
def test_cross_field_validators_are_bidirectional(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(payload)


@pytest.mark.parametrize(
    "metric",
    [
        {key: value for key, value in _metric(unit_status="known").items() if key != "unit"},
        _metric(unit_status="unknown", unit="s"),
        _metric(unit_status="not_applicable", unit=None),
    ],
)
def test_metric_unit_exists_if_and_only_if_known(metric: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateMetricModel.model_validate(metric)


@pytest.mark.parametrize(
    "series",
    [
        _identity_series(value_unit_status="known"),
        _identity_series(value_unit_status="unknown", value_unit="V"),
        _identity_series(value_unit_status="not_applicable", value_unit=None),
    ],
)
def test_series_value_unit_exists_if_and_only_if_known(series: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateIdentitySeriesModel.model_validate(series)


@pytest.mark.parametrize(
    "payload",
    [
        _valid_payload(metrics=[_metric(name="x" * 33)]),
        _valid_payload(metrics=[_metric(name="测" * 33)]),
        _valid_payload(metrics=[_metric(unit="x" * 17)]),
        _valid_payload(stop_reason="测" * 161),
        _valid_payload(stop_reason="测" * 161),
        _valid_payload(solver="测" * 33),
        _valid_payload(series=[_identity_series(label="测" * 33)]),
        _valid_payload(series=[_identity_series(series_id="bad/id")]),
        _valid_payload(series=[_identity_series(label="bad\x00label")]),
        _valid_payload(series=[_identity_series(label="bad\u202elabel")]),
    ],
)
def test_string_limits_and_unsafe_unicode_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [
        "file_path",
        "source_code",
        "slx_path",
        "workspace",
        "model_content",
        "mat_path",
        "csv_path",
        "raw_mat",
        "raw_csv",
        "base64",
        "blob",
        "compressed",
        "archive",
    ],
)
def test_sensitive_extra_fields_are_rejected_at_any_depth(field: str) -> None:
    payload = _valid_payload(series=[{**_identity_series(), field: "SECRET"}])

    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(payload)


def test_metrics_and_series_count_limits_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(
            _valid_payload(metrics=[_metric(name=f"m{i}") for i in range(17)])
        )
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(
            _valid_payload(series=[_identity_series(series_id=f"s{i}") for i in range(5)])
        )


@pytest.mark.parametrize(
    "series",
    [
        _identity_series(source_point_count=1, y=[1.0]),
        _identity_series(source_point_count=3, y=[1.0, 2.0]),
        _identity_series(t_step=0.0),
        _identity_series(y=[0.0, True, 1.0, 2.0]),
        _envelope_series(y_min=[0.0] * 95),
        _envelope_series(y_max=[1.0] * 95),
        _envelope_series(y_min=[2.0] * ENVELOPE_BUCKET_COUNT, y_max=[1.0] * ENVELOPE_BUCKET_COUNT),
        _envelope_series(source_point_count=192),
        _envelope_series(bucket_width=0.0),
    ],
)
def test_series_representation_boundaries(series: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateRequest.model_validate(_valid_payload(series=[series]))


def test_envelope_series_accepts_exactly_96_buckets() -> None:
    request = BridgeRunStateRequest.model_validate(_valid_payload(series=[_envelope_series()]))

    series = request.series[0]
    assert isinstance(series, BridgeRunStateEnvelopeSeriesModel)
    assert len(series.y_min) == ENVELOPE_BUCKET_COUNT
    assert len(series.y_max) == ENVELOPE_BUCKET_COUNT


def test_rel_tol_constant_is_frozen_for_matlab_golden_tests() -> None:
    assert RUN_STATE_UNIFORM_REL_TOL == 1e-6


def test_matlab_to_python_golden_payload_validates() -> None:
    payload = json.loads(
        Path("tests/fixtures/matlab_bridge/run_state_golden_payload.json").read_text(
            encoding="utf-8"
        )
    )

    request = BridgeRunStateRequest.model_validate(payload)

    assert request.run_sequence == 7
    assert request.series[0].representation == "identity_uniform_v1"
