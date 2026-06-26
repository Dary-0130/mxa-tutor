from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from features.matlab_bridge.bridge_run_state_coaching_schemas import (
    BridgeRunStateCoachingRequest,
    BridgeRunStateCoachingResultModel,
    CoachingLLMError,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


def _valid_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-c1",
        "request_id": REQUEST_ID,
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_state_coaching_consent_confirmed": True,
        "coaching_consent_notice_version": "run_state_coaching_v1",
        "previous_run_count": 0,
    }
    payload.update(overrides)
    return payload


def _valid_result(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-c1",
        "request_id": REQUEST_ID,
        "run_id": RUN_ID,
        "context_run_ids": [RUN_ID],
        "status": "completed",
        "mode": "run_state_coaching",
        "outcome": "coached",
        "run_summary": "本轮状态为 completed,收敛状态为 not_applicable。",
        "signal_readings": [
            {
                "reading_id": "r1",
                "reading": "指标有可用变化,可以做温和比较。",
                "is_inference": True,
                "confidence": "medium",
                "evidence_ids": ["e1"],
            }
        ],
        "primary_directions": [
            {
                "action": "compare",
                "magnitude_band": "slight",
                "rationale_reading_id": "r1",
                "alternatives": [
                    {
                        "action": "hold",
                        "magnitude_band": "slight",
                        "rationale_reading_id": "r1",
                    }
                ],
            }
        ],
        "cross_round_trend": None,
        "uncertainties": [],
        "fallback_reason": None,
        "overall_confidence": "medium",
        "evidence": [
            {
                "evidence_id": "e1",
                "text": "metric wall_clock_elapsed=1.25 s",
                "signal_ref": "metric:wall_clock_elapsed",
            }
        ],
        "caveats": ["这里只基于脱敏、降采样的 run-state 摘要。"],
    }
    payload.update(overrides)
    return payload


def test_request_round_trip_and_consent_notice() -> None:
    request = BridgeRunStateCoachingRequest.model_validate(_valid_request())
    domain = request.to_domain()

    assert domain.protocol_version == "0.3-c1"
    assert domain.run_id == UUID(RUN_ID)
    assert domain.run_state_coaching_consent_confirmed is True
    assert domain.coaching_consent_notice_version == "run_state_coaching_v1"


@pytest.mark.parametrize(
    "payload",
    [
        _valid_request(run_state_coaching_consent_confirmed=False),
        _valid_request(coaching_consent_notice_version="run_state_coaching_v0"),
        _valid_request(previous_run_count=True),
        _valid_request(previous_run_count=5),
        _valid_request(raw_mat="SECRET"),
    ],
)
def test_request_rejects_invalid_consent_bounds_and_sensitive_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateCoachingRequest.model_validate(payload)


def test_persistence_consent_cannot_replace_coaching_consent() -> None:
    missing_coaching_consent = _valid_request()
    missing_coaching_consent.pop("run_state_coaching_consent_confirmed")
    missing_coaching_consent["run_state_sharing_consent_confirmed"] = True

    with pytest.raises(ValidationError):
        BridgeRunStateCoachingRequest.model_validate(missing_coaching_consent)

    with pytest.raises(ValidationError):
        BridgeRunStateCoachingRequest.model_validate(
            _valid_request(run_state_sharing_consent_confirmed=True)
        )

    request = BridgeRunStateCoachingRequest.model_validate(
        _valid_request(run_state_coaching_consent_confirmed=True)
    )
    assert request.run_state_coaching_consent_confirmed is True


def test_result_round_trip_validates_evidence_reading_direction_chain() -> None:
    result = BridgeRunStateCoachingResultModel.model_validate(_valid_result())
    domain = result.to_domain()
    round_trip = BridgeRunStateCoachingResultModel.from_domain(domain)

    assert round_trip.model_dump(mode="json") == result.model_dump(mode="json")
    assert result.primary_directions[0].rationale_reading_id == "r1"
    assert result.signal_readings[0].evidence_ids == ("e1",)


@pytest.mark.parametrize(
    "updates",
    [
        {"evidence": [_valid_result()["evidence"][0], _valid_result()["evidence"][0]]},
        {
            "signal_readings": [
                {
                    **_valid_result()["signal_readings"][0],  # type: ignore[index]
                    "evidence_ids": ["e404"],
                }
            ]
        },
        {
            "primary_directions": [
                {
                    **_valid_result()["primary_directions"][0],  # type: ignore[index]
                    "rationale_reading_id": "r404",
                }
            ]
        },
    ],
)
def test_result_rejects_broken_evidence_chain(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BridgeRunStateCoachingResultModel.model_validate(_valid_result(**updates))


def test_insufficient_evidence_requires_empty_directions_uncertainty_reason_and_low_confidence() -> (
    None
):
    result = BridgeRunStateCoachingResultModel.model_validate(
        _valid_result(
            outcome="insufficient_evidence",
            signal_readings=[],
            primary_directions=[],
            uncertainties=["缺少指标和波形摘要。"],
            fallback_reason="no_metrics_or_series",
            overall_confidence="low",
        )
    )

    assert result.primary_directions == ()
    assert result.fallback_reason == "no_metrics_or_series"


def test_coaching_error_response_is_closed_and_independent() -> None:
    ok = CoachingLLMError.model_validate(
        {
            "error": "bridge_run_state_coaching_busy",
            "message": "运行状态陪调正在处理中,请稍后重试",
        }
    )

    assert ok.error == "bridge_run_state_coaching_busy"
    with pytest.raises(ValidationError):
        CoachingLLMError.model_validate({"error": "bridge_run_state_busy", "message": "bad"})
