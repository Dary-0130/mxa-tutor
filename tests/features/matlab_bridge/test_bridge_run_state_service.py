from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.domain.bridge_auth import (
    RUN_STATE_WRITE_CAPABILITY,
    BridgeAuthClaims,
    BridgeAuthContext,
)
from core.domain.bridge_run_state_machine import RunStateDecision
from core.domain.exceptions import BridgeRunStateValidationError
from features.matlab_bridge.bridge_run_state_schemas import BridgeRunStateRequest
from features.matlab_bridge.bridge_run_state_service import (
    BridgeRunStateService,
    contains_run_state_private_text,
    redact_run_state_request,
    redact_run_state_text,
)

REQUEST_ID = "2690af3d-9cfe-4442-900e-c86af37a6244"
SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


def _auth_context() -> BridgeAuthContext:
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    return BridgeAuthContext(
        claims=BridgeAuthClaims(
            issuer="mxa-tutor-dev",
            audience="mxa-matlab-bridge",
            subject="user-alpha",
            user_id="user-alpha",
            project_id="project-alpha",
            session_id=SESSION_ID,
            capabilities=frozenset({RUN_STATE_WRITE_CAPABILITY}),
            token_id="token-alpha",
            issued_at=now,
            not_before=now,
            expires_at=now + timedelta(minutes=5),
            process_generation="generation-1",
        )
    )


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
        "metrics": [
            {
                "name": "wall_clock_elapsed",
                "value": 1.25,
                "unit_status": "known",
                "unit": "s",
            }
        ],
        "series_status": "available",
        "series": [
            {
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
        ],
    }
    payload.update(overrides)
    return payload


class FakePersistStore:
    def __init__(self, decision: RunStateDecision | None = None) -> None:
        self.decision = decision or RunStateDecision(kind="current")
        self.requests = []
        self.scopes = []

    async def persist_run(self, request, scope):  # noqa: ANN001, ANN201
        self.requests.append(request)
        self.scopes.append(scope)
        return SimpleNamespace(decision=self.decision)


def test_service_returns_durable_receipt_after_persistence() -> None:
    request = BridgeRunStateRequest.model_validate(_valid_payload()).to_domain()
    store = FakePersistStore()

    receipt = asyncio.run(
        BridgeRunStateService().consume(
            request,
            _auth_context(),
            store=store,
            scope=object(),
        )
    )

    assert receipt.protocol_version == "0.3-b4"
    assert receipt.status == "persisted"
    assert receipt.mode == "durable_persisted"
    assert receipt.durable is True
    assert receipt.request_id == request.request_id
    assert receipt.run_id == request.run_id
    assert receipt.run_sequence == 7
    assert store.requests[0].stop_reason == request.stop_reason


def test_server_side_redaction_covers_all_string_fields() -> None:
    request = BridgeRunStateRequest.model_validate(
        _valid_payload(
            stop_reason="Stopped at C:\\Users\\alice\\secret\\model.m",
            solver="token=SECRET12",
            metrics=[
                {
                    "name": "token=SECRET12",
                    "value": 1.0,
                    "unit_status": "known",
                    "unit": "C:\\u\\a.txt",
                }
            ],
            series=[
                {
                    "representation": "identity_uniform_v1",
                    "series_id": "simout",
                    "label": "C:\\Users\\a\\m.slx",
                    "time_unit": "s",
                    "value_unit_status": "known",
                    "sample_order": "chronological",
                    "source_point_count": 2,
                    "t_start": 0.0,
                    "t_step": 0.1,
                    "y": [0.0, 1.0],
                    "value_unit": "token=SECRET12",
                }
            ],
        )
    ).to_domain()

    redacted = redact_run_state_request(request)
    redacted_text = "\n".join(
        [
            redacted.stop_reason or "",
            redacted.solver or "",
            redacted.metrics[0].name,
            redacted.metrics[0].unit or "",
            redacted.series[0].label,
            redacted.series[0].value_unit or "",
        ]
    )

    assert "C:\\Users\\alice" not in redacted_text
    assert "SECRET12" not in redacted_text
    assert "C:\\Users\\a" not in redacted_text
    assert contains_run_state_private_text(redacted_text) is False


def test_privacy_fail_closed_if_redaction_misses_private_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import features.matlab_bridge.bridge_run_state_service as service_module

    request = BridgeRunStateRequest.model_validate(_valid_payload()).to_domain()
    monkeypatch.setattr(service_module, "redact_run_state_text", lambda text: text)
    request = BridgeRunStateRequest.model_validate(
        _valid_payload(stop_reason="C:\\Users\\alice\\secret\\model.m")
    ).to_domain()

    with pytest.raises(BridgeRunStateValidationError):
        asyncio.run(
            BridgeRunStateService().consume(
                request,
                _auth_context(),
                store=FakePersistStore(),
                scope=object(),
            )
        )


def test_redact_run_state_text_redacts_model_metadata() -> None:
    text = "UserID=alice MachineName=workstation ModelFilePath=C:\\Users\\alice\\model.slx"

    redacted = redact_run_state_text(text)

    assert "alice" not in redacted
    assert "workstation" not in redacted
    assert "C:\\Users\\alice" not in redacted


def test_service_source_uses_metadata_only_logging() -> None:
    source = Path("features/matlab_bridge/bridge_run_state_service.py").read_text(encoding="utf-8")
    logger_lines = [line for line in source.splitlines() if "logger." in line]

    assert "logger.exception" not in source
    assert "SqliteBridgeRunStateStore" not in source
    for leaked in (
        "stop_reason",
        "metric.value",
        "series.y",
        "run_id",
        "request_id",
        "session_id",
        "token",
        "claim",
        "fingerprint",
        "source_code",
        "label",
        "mat_path",
        "csv_path",
    ):
        assert not any(leaked in line for line in logger_lines)
