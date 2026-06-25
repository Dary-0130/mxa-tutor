from __future__ import annotations

from uuid import uuid4

from core.domain.bridge_run_state_machine import (
    IncomingRunStateSnapshot,
    PersistedRunStateRun,
    decide_run_state_persistence,
    fingerprint_run_state_request,
)
from features.matlab_bridge.bridge_run_state_schemas import BridgeRunStateRequest
from features.matlab_bridge.bridge_run_state_service import redact_run_state_request

SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b3",
        "request_id": "2690af3d-9cfe-4442-900e-c86af37a6244",
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_sequence": 7,
        "matlab_release": "R2026a",
        "client_version": "0.1.0",
        "run_state_sharing_consent_confirmed": True,
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
                "source_point_count": 2,
                "t_start": 0.0,
                "t_step": 0.1,
                "y": [0.0, 1.0],
            }
        ],
    }
    payload.update(overrides)
    return payload


def _domain_request(**overrides: object):
    return BridgeRunStateRequest.model_validate(_payload(**overrides)).to_domain()


def _incoming(run_id: str = RUN_ID, sequence: int = 7, content: bytes = b"a"):
    return IncomingRunStateSnapshot(
        run_id=run_id,
        run_sequence=sequence,
        fingerprint=f"sha256:{content.hex()}",
        fingerprint_version=1,
        canonical_bytes=content,
    )


def _persisted(run_id: str = RUN_ID, sequence: int = 7, content: bytes = b"a"):
    return PersistedRunStateRun(
        run_id=run_id,
        run_sequence=sequence,
        fingerprint=f"sha256:{content.hex()}",
        fingerprint_version=1,
        canonical_bytes=content,
    )


def test_state_machine_rejects_missing_or_terminal_session() -> None:
    decision = decide_run_state_persistence(
        session_status="ended",
        incoming=_incoming(),
        existing_run_by_run_id=None,
        existing_run_by_sequence=None,
        current_run=None,
    )

    assert decision.kind == "rejected"
    assert decision.reason == "session_not_active"


def test_state_machine_replays_same_run_id_and_same_snapshot() -> None:
    existing = _persisted()

    decision = decide_run_state_persistence(
        session_status="active",
        incoming=_incoming(),
        existing_run_by_run_id=existing,
        existing_run_by_sequence=existing,
        current_run=existing,
    )

    assert decision.kind == "idempotent"
    assert decision.replay_run == existing


def test_state_machine_conflicts_same_run_id_with_different_snapshot() -> None:
    decision = decide_run_state_persistence(
        session_status="active",
        incoming=_incoming(content=b"new"),
        existing_run_by_run_id=_persisted(content=b"old"),
        existing_run_by_sequence=None,
        current_run=None,
    )

    assert decision.kind == "conflict"
    assert decision.reason == "run_id_snapshot_conflict"


def test_state_machine_conflicts_same_sequence_with_different_run_id() -> None:
    decision = decide_run_state_persistence(
        session_status="active",
        incoming=_incoming(run_id=str(uuid4()), sequence=7),
        existing_run_by_run_id=None,
        existing_run_by_sequence=_persisted(run_id=RUN_ID, sequence=7),
        current_run=_persisted(run_id=RUN_ID, sequence=7),
    )

    assert decision.kind == "conflict"
    assert decision.reason == "run_sequence_conflict"


def test_state_machine_classifies_current_and_historical_runs() -> None:
    current = _persisted(sequence=7)

    newer = decide_run_state_persistence(
        session_status="active",
        incoming=_incoming(run_id=str(uuid4()), sequence=8),
        existing_run_by_run_id=None,
        existing_run_by_sequence=None,
        current_run=current,
    )
    older = decide_run_state_persistence(
        session_status="active",
        incoming=_incoming(run_id=str(uuid4()), sequence=6),
        existing_run_by_run_id=None,
        existing_run_by_sequence=None,
        current_run=current,
    )

    assert newer.kind == "current"
    assert older.kind == "historical"


def test_fingerprint_excludes_request_id_but_covers_persistent_semantics() -> None:
    first = _domain_request()
    retry = _domain_request(request_id=str(uuid4()))
    changed_sequence = _domain_request(run_sequence=8)

    first_fingerprint = fingerprint_run_state_request(first)
    retry_fingerprint = fingerprint_run_state_request(retry)
    changed_fingerprint = fingerprint_run_state_request(changed_sequence)

    assert retry_fingerprint == first_fingerprint
    assert changed_fingerprint.fingerprint != first_fingerprint.fingerprint
    assert changed_fingerprint.canonical_bytes != first_fingerprint.canonical_bytes


def test_fingerprint_uses_redacted_semantics_as_hash_source() -> None:
    first = redact_run_state_request(
        _domain_request(stop_reason="Stopped at C:\\Users\\alice\\secret\\model.m")
    )
    second = redact_run_state_request(
        _domain_request(stop_reason="Stopped at C:\\Users\\bob\\other\\model.m")
    )

    assert fingerprint_run_state_request(first) == fingerprint_run_state_request(second)
