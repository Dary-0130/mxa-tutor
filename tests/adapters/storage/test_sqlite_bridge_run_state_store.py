from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite
import pytest

from adapters.storage._connection import open_connection
from adapters.storage.sqlite_bridge_run_state_store import (
    BridgeRunStateScope,
    BridgeRunStateSessionRejectedError,
    BridgeRunStateStoreUnavailableError,
    SqliteBridgeRunStateStore,
)
from features.matlab_bridge.bridge_run_state_schemas import BridgeRunStateRequest
from features.matlab_bridge.run_state_cleanup_worker import RunStateCleanupWorker

SESSION_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _scope(
    *,
    session_id: str = SESSION_ID,
    project_id: str = "project-alpha",
    generation: str = "generation-1",
) -> BridgeRunStateScope:
    return BridgeRunStateScope(
        user_id="user-alpha",
        project_id=project_id,
        session_id=session_id,
        process_generation=generation,
    )


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "0.3-b3",
        "request_id": str(uuid4()),
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_sequence": 1,
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


def _request(**overrides: object):
    return BridgeRunStateRequest.model_validate(_payload(**overrides)).to_domain()


async def test_establish_session_requires_existing_unexpired_project(
    initialized_db_path: str,
) -> None:
    store = SqliteBridgeRunStateStore(initialized_db_path)

    with pytest.raises(BridgeRunStateSessionRejectedError, match="project_missing"):
        await store.establish_session(_scope())

    await _insert_project(initialized_db_path)

    session = await store.establish_session(_scope())

    assert session.session_id == SESSION_ID
    assert session.status == "active"
    assert session.project_id == "project-alpha"


async def test_establish_is_idempotent_and_does_not_revive_terminal_session(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    clock = MutableClock(datetime(2026, 6, 1, 0, 0, 0))
    store = SqliteBridgeRunStateStore(initialized_db_path, clock=clock)

    first = await store.establish_session(_scope())
    clock.now = datetime(2026, 6, 1, 0, 5, 0)
    refreshed = await store.establish_session(_scope())
    ended = await store.end_session(_scope())

    assert refreshed.session_id == first.session_id
    assert refreshed.updated_at > first.updated_at
    assert ended.status == "ended"
    with pytest.raises(BridgeRunStateSessionRejectedError, match="session_terminal"):
        await store.establish_session(_scope())


async def test_persist_run_uses_run_id_for_idempotency_and_conflict(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())
    first = _request()
    retry = _request(request_id=str(uuid4()))
    changed = _request(request_id=str(uuid4()), stop_reason="DifferentStop")

    accepted = await store.persist_run(first, _scope())
    replayed = await store.persist_run(retry, _scope())
    conflicted = await store.persist_run(changed, _scope())

    assert accepted.decision.kind == "current"
    assert replayed.decision.kind == "idempotent"
    assert conflicted.decision.kind == "conflict"
    assert conflicted.decision.reason == "run_id_snapshot_conflict"
    assert await _run_count(initialized_db_path) == 1


async def test_persist_run_tracks_current_and_historical_without_updating_runs(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())

    current_request = _request(run_sequence=2)
    historical_request = _request(run_id=str(uuid4()), run_sequence=1)

    current_result = await store.persist_run(current_request, _scope())
    historical_result = await store.persist_run(historical_request, _scope())
    current = await store.current(_scope())

    assert current_result.decision.kind == "current"
    assert historical_result.decision.kind == "historical"
    assert current is not None
    assert current.run_id == str(current_request.run_id)
    assert await _run_count(initialized_db_path) == 2
    assert await _source_contains_no_run_update()


async def test_same_sequence_different_run_conflicts_and_request_id_reuse_is_not_idempotent(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())
    request_id = str(uuid4())
    first = _request(request_id=request_id, run_sequence=1)
    same_sequence = _request(run_id=str(uuid4()), run_sequence=1)
    reused_request = _request(request_id=request_id, run_id=str(uuid4()), run_sequence=2)

    await store.persist_run(first, _scope())
    sequence_conflict = await store.persist_run(same_sequence, _scope())
    request_id_conflict = await store.persist_run(reused_request, _scope())

    assert sequence_conflict.decision.kind == "conflict"
    assert sequence_conflict.decision.reason == "run_sequence_conflict"
    assert request_id_conflict.decision.kind == "conflict"
    assert request_id_conflict.decision.reason == "request_id_reuse"
    assert await _run_count(initialized_db_path) == 1


async def test_end_session_clears_snapshots_and_keeps_minimal_terminal_row(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())
    await store.persist_run(_request(), _scope())

    ended = await store.end_session(_scope())
    current = await store.get_session(SESSION_ID)

    assert ended.status == "ended"
    assert ended.current_run_id is None
    assert current is not None
    assert current.status == "ended"
    assert await _run_count(initialized_db_path) == 0
    with pytest.raises(BridgeRunStateSessionRejectedError, match="session_terminal"):
        await store.current(_scope())


async def test_project_expiry_marks_session_gone_and_rejects_read_write(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path, created_at="2026-06-01T00:00:00")
    clock = MutableClock(datetime(2026, 6, 1, 23, 0, 0))
    store = SqliteBridgeRunStateStore(initialized_db_path, clock=clock)
    await store.establish_session(_scope())
    await store.persist_run(_request(), _scope())

    clock.now = datetime(2026, 6, 2, 0, 0, 0)

    with pytest.raises(BridgeRunStateSessionRejectedError, match="project_expired"):
        await store.current(_scope())
    with pytest.raises(BridgeRunStateSessionRejectedError, match="project_expired"):
        await store.persist_run(_request(run_id=str(uuid4()), run_sequence=2), _scope())
    session = await store.get_session(SESSION_ID)

    assert session is not None
    assert session.status == "gone"
    assert await _run_count(initialized_db_path) == 0


async def test_sweep_clears_snapshots_before_ttl_cutoff(initialized_db_path: str) -> None:
    await _insert_project(initialized_db_path, created_at="2026-06-01T00:00:00")
    clock = MutableClock(datetime(2026, 6, 1, 23, 0, 0))
    store = SqliteBridgeRunStateStore(initialized_db_path, clock=clock)
    await store.establish_session(_scope())
    await store.persist_run(_request(), _scope())

    swept = await store.sweep_expired_run_state()
    session = await store.get_session(SESSION_ID)

    assert swept == 1
    assert session is not None
    assert session.status == "gone"
    assert await _run_count(initialized_db_path) == 0


async def test_project_delete_cascades_run_state_tables(initialized_db_path: str) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())
    await store.persist_run(_request(), _scope())

    async with open_connection(initialized_db_path) as conn:
        await conn.execute("DELETE FROM project_status_record WHERE project_id='project-alpha'")
        await conn.commit()

    assert await _session_count(initialized_db_path) == 0
    assert await _run_count(initialized_db_path) == 0


async def test_delete_session_removes_session_and_cascades_runs(initialized_db_path: str) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())
    await store.persist_run(_request(), _scope())

    await store.delete_session(SESSION_ID)

    assert await _session_count(initialized_db_path) == 0
    assert await _run_count(initialized_db_path) == 0


async def test_current_pointer_trigger_rejects_drift(initialized_db_path: str) -> None:
    await _insert_project(initialized_db_path)
    store = SqliteBridgeRunStateStore(initialized_db_path)
    await store.establish_session(_scope())

    async with open_connection(initialized_db_path) as conn:
        with pytest.raises(aiosqlite.IntegrityError, match="bridge_run_state_current_run_missing"):
            await conn.execute(
                """
                UPDATE bridge_run_state_session
                SET current_run_id='22222222-2222-4222-8222-222222222222'
                WHERE session_id=?
                """,
                (SESSION_ID,),
            )


async def test_concurrent_writes_with_two_connections_leave_single_current(
    initialized_db_path: str,
) -> None:
    await _insert_project(initialized_db_path)
    first_store = SqliteBridgeRunStateStore(initialized_db_path)
    second_store = SqliteBridgeRunStateStore(initialized_db_path)
    await first_store.establish_session(_scope())
    first = _request(run_id=str(uuid4()), run_sequence=1)
    second = _request(run_id=str(uuid4()), run_sequence=1)

    first_result, second_result = await asyncio.gather(
        first_store.persist_run(first, _scope()),
        second_store.persist_run(second, _scope()),
    )
    kinds = {first_result.decision.kind, second_result.decision.kind}
    current = await first_store.current(_scope())

    assert kinds == {"current", "conflict"}
    assert current is not None
    assert await _run_count(initialized_db_path) == 1


async def test_run_state_cleanup_worker_fail_closed_on_sweep_failure() -> None:
    class FailingStore:
        async def sweep_expired_run_state(self) -> int:
            raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed")

    worker = RunStateCleanupWorker(FailingStore())

    assert await worker.run_once() == 0


def test_store_source_uses_safe_transaction_and_logging_patterns() -> None:
    source = Path("adapters/storage/sqlite_bridge_run_state_store.py").read_text(encoding="utf-8")
    logger_lines = [line for line in source.splitlines() if "logger." in line]

    assert "BEGIN IMMEDIATE" in source
    assert "UPDATE bridge_run_state_run" not in source
    assert "logger.exception" not in source
    assert not any("fingerprint" in line for line in logger_lines)
    assert not any("snapshot_json" in line for line in logger_lines)


async def _insert_project(
    db_path: str,
    *,
    created_at: str | None = None,
) -> None:
    created_at = created_at or datetime.now(UTC).replace(tzinfo=None).isoformat()
    async with open_connection(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO project_status_record(
                project_id, name, status, created_at, updated_at
            ) VALUES (?, 'demo.zip', 'parsing', ?, ?)
            """,
            ("project-alpha", created_at, created_at),
        )
        await conn.commit()


async def _run_count(db_path: str) -> int:
    async with open_connection(db_path) as conn:
        row = await (
            await conn.execute("SELECT COUNT(*) AS count FROM bridge_run_state_run")
        ).fetchone()
    return int(row["count"])


async def _session_count(db_path: str) -> int:
    async with open_connection(db_path) as conn:
        row = await (
            await conn.execute("SELECT COUNT(*) AS count FROM bridge_run_state_session")
        ).fetchone()
    return int(row["count"])


async def _source_contains_no_run_update() -> bool:
    source = Path("adapters/storage/sqlite_bridge_run_state_store.py").read_text(encoding="utf-8")
    return "UPDATE bridge_run_state_run" not in source
