"""SQLite substrate for MATLAB bridge run-state persistence."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import aiosqlite
from loguru import logger

from adapters.storage._connection import open_connection
from core.domain.bridge_run_state import (
    BridgeRunStateRequest,
    canonical_run_state_session_id,
)
from core.domain.bridge_run_state_machine import (
    IncomingRunStateSnapshot,
    PersistedRunStateRun,
    RunStateDecision,
    RunStateSessionStatus,
    decide_run_state_persistence,
    fingerprint_run_state_request,
)
from core.domain.exceptions import StoreError
from core.interfaces.coaching_cross_round_reader import CoachingCrossRoundReader
from core.interfaces.coaching_run_state_reader import (
    CoachingRunStateMetric,
    CoachingRunStateReader,
    CoachingRunStateReaderUnavailableError,
    CoachingRunStateReadRejectedError,
    CoachingRunStateScope,
    CoachingRunStateSeries,
    CoachingRunStateSnapshot,
)

RunStateSessionRejectReason = Literal[
    "invalid_scope",
    "project_missing",
    "project_expired",
    "session_missing",
    "session_terminal",
    "scope_mismatch",
    "process_generation_mismatch",
]


class BridgeRunStateSessionRejectedError(Exception):
    """A correctly-scoped run-state session is not writable/readable."""

    def __init__(self, reason: RunStateSessionRejectReason) -> None:
        self.reason = reason
        super().__init__(reason)


class BridgeRunStateStoreUnavailableError(StoreError):
    """Run-state store cannot provide an authoritative answer."""


@dataclass(frozen=True, slots=True)
class BridgeRunStateScope:
    user_id: str
    project_id: str
    session_id: str
    process_generation: str


@dataclass(frozen=True, slots=True)
class BridgeRunStateSessionRecord:
    session_id: str
    project_id: str
    user_id: str
    process_generation: str
    status: RunStateSessionStatus
    current_run_id: str | None
    established_at: datetime
    updated_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class BridgeRunStateCurrentRecord:
    run_id: str
    run_sequence: int
    request_id: str
    run_status: str
    convergence_status: str
    snapshot_json: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class BridgeRunStatePersistResult:
    decision: RunStateDecision
    run_id: str
    current_run_id: str | None


class SqliteBridgeRunStateStore(CoachingRunStateReader, CoachingCrossRoundReader):
    """Persist run-state sessions and immutable run snapshots in SQLite."""

    def __init__(
        self,
        db_path: str,
        *,
        upload_ttl_hours: int = 24,
        sweep_interval_seconds: int = 3600,
        sweep_safety_margin_seconds: int = 60,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._db_path = db_path
        self._upload_ttl_hours = upload_ttl_hours
        self._sweep_interval_seconds = sweep_interval_seconds
        self._sweep_safety_margin_seconds = sweep_safety_margin_seconds
        self._clock = clock or _utcnow_naive

    async def establish_session(self, scope: BridgeRunStateScope) -> BridgeRunStateSessionRecord:
        """Create or refresh an active run-state session before token issuance."""

        normalized = _normalize_scope(scope)
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                project = await self._load_project(conn, normalized.project_id)
                if project is None:
                    raise BridgeRunStateSessionRejectedError("project_missing")
                if _is_project_expired(project.created_at, self._upload_ttl_hours, now):
                    await self._mark_project_sessions_gone(conn, normalized.project_id, now)
                    raise BridgeRunStateSessionRejectedError("project_expired")

                existing = await self._select_session(conn, normalized.session_id)
                if existing is None:
                    await conn.execute(
                        """
                        INSERT INTO bridge_run_state_session(
                            session_id,
                            project_id,
                            user_id,
                            process_generation,
                            status,
                            current_run_id,
                            established_at,
                            updated_at,
                            ended_at
                        ) VALUES (?, ?, ?, ?, 'active', NULL, ?, ?, NULL)
                        """,
                        (
                            normalized.session_id,
                            normalized.project_id,
                            normalized.user_id,
                            normalized.process_generation,
                            now.isoformat(),
                            now.isoformat(),
                        ),
                    )
                else:
                    _reject_scope_mismatch(existing, normalized)
                    if existing.status != "active":
                        raise BridgeRunStateSessionRejectedError("session_terminal")
                    await conn.execute(
                        """
                        UPDATE bridge_run_state_session
                        SET updated_at=?
                        WHERE session_id=? AND status='active'
                        """,
                        (now.isoformat(), normalized.session_id),
                    )

                session = await self._select_session(conn, normalized.session_id)
                if session is None:
                    raise BridgeRunStateStoreUnavailableError("session_establish_failed")
                await conn.commit()
                logger.info(
                    "Bridge run-state session establish: event_code={} status={}",
                    "bridge_run_state_establish",
                    "ok",
                )
                return session
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                logger.info(
                    "Bridge run-state session establish: event_code={} status={}",
                    "bridge_run_state_establish",
                    "rejected",
                )
                raise
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state session establish failed: event_code={} status={} exception={}",
                    "bridge_run_state_establish",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def get_session(self, session_id: str) -> BridgeRunStateSessionRecord | None:
        normalized_session_id = _canonical_session_id(session_id)
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._select_session(conn, normalized_session_id)
                await conn.commit()
                return session
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state get failed: event_code={} status={} exception={}",
                    "bridge_run_state_get",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def list_sessions(
        self, project_id: str | None = None
    ) -> list[BridgeRunStateSessionRecord]:
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                if project_id is None:
                    cur = await conn.execute(
                        """
                        SELECT *
                        FROM bridge_run_state_session
                        ORDER BY established_at ASC
                        """
                    )
                else:
                    cur = await conn.execute(
                        """
                        SELECT *
                        FROM bridge_run_state_session
                        WHERE project_id=?
                        ORDER BY established_at ASC
                        """,
                        (project_id,),
                    )
                rows = await cur.fetchall()
                await conn.commit()
                return [_session_from_row(row) for row in rows]
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state list failed: event_code={} status={} exception={}",
                    "bridge_run_state_list",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def current(self, scope: BridgeRunStateScope) -> BridgeRunStateCurrentRecord | None:
        normalized = _normalize_scope(scope)
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._require_active_session(conn, normalized, now)
                if session.current_run_id is None:
                    await conn.commit()
                    return None
                row = await self._select_run_by_run_id(
                    conn,
                    session.session_id,
                    session.current_run_id,
                )
                if row is None:
                    raise BridgeRunStateStoreUnavailableError("current_run_missing")
                await conn.commit()
                return _current_from_row(row)
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                raise
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state current failed: event_code={} status={} exception={}",
                    "bridge_run_state_current",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def read_run_state_for_coaching(
        self,
        scope: CoachingRunStateScope,
        run_id: UUID,
    ) -> CoachingRunStateSnapshot:
        try:
            normalized = _normalize_scope(_scope_from_coaching_scope(scope))
        except BridgeRunStateSessionRejectedError as exc:
            raise _coaching_rejection(exc.reason) from None
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._require_active_session(conn, normalized, now)
                row = await self._select_run_by_run_id(conn, session.session_id, str(run_id))
                if row is None:
                    await conn.rollback()
                    raise CoachingRunStateReadRejectedError("run_missing")
                snapshot = _coaching_snapshot_from_row(row)
                await conn.commit()
                return snapshot
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                raise _coaching_rejection(exc.reason) from None
            except CoachingRunStateReadRejectedError:
                raise
            except (aiosqlite.Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state coaching read failed: event_code={} status={} exception={}",
                    "bridge_run_state_coaching_read",
                    "store_error",
                    type(exc).__name__,
                )
                raise CoachingRunStateReaderUnavailableError("coaching_read_failed") from None

    async def read_run_state_window_for_coaching(
        self,
        scope: CoachingRunStateScope,
        run_id: UUID,
        previous_run_count: int,
    ) -> tuple[CoachingRunStateSnapshot, ...]:
        try:
            normalized = _normalize_scope(_scope_from_coaching_scope(scope))
        except BridgeRunStateSessionRejectedError as exc:
            raise _coaching_rejection(exc.reason) from None
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._require_active_session(conn, normalized, now)
                target = await self._select_run_by_run_id(conn, session.session_id, str(run_id))
                if target is None:
                    await conn.rollback()
                    raise CoachingRunStateReadRejectedError("run_missing")
                limit = previous_run_count + 1
                cur = await conn.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT *
                        FROM bridge_run_state_run
                        WHERE session_id=? AND run_sequence<=?
                        ORDER BY run_sequence DESC
                        LIMIT ?
                    )
                    ORDER BY run_sequence ASC
                    """,
                    (session.session_id, int(target["run_sequence"]), limit),
                )
                rows = await cur.fetchall()
                snapshots = tuple(_coaching_snapshot_from_row(row) for row in rows)
                if not snapshots or snapshots[-1].run_id != run_id:
                    raise ValueError("target_missing_from_window")
                await conn.commit()
                return snapshots
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                raise _coaching_rejection(exc.reason) from None
            except CoachingRunStateReadRejectedError:
                raise
            except (aiosqlite.Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state coaching window read failed: event_code={} status={} exception={}",
                    "bridge_run_state_coaching_read",
                    "store_error",
                    type(exc).__name__,
                )
                raise CoachingRunStateReaderUnavailableError(
                    "coaching_window_read_failed"
                ) from None

    async def assert_coaching_session_active(self, scope: CoachingRunStateScope) -> None:
        try:
            normalized = _normalize_scope(_scope_from_coaching_scope(scope))
        except BridgeRunStateSessionRejectedError as exc:
            raise _coaching_rejection(exc.reason) from None
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                await self._require_active_session(conn, normalized, now)
                await conn.commit()
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                raise _coaching_rejection(exc.reason) from None
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state coaching fence failed: event_code={} status={} exception={}",
                    "bridge_run_state_coaching_fence",
                    "store_error",
                    type(exc).__name__,
                )
                raise CoachingRunStateReaderUnavailableError("coaching_fence_failed") from None

    async def persist_run(
        self,
        request: BridgeRunStateRequest,
        scope: BridgeRunStateScope,
    ) -> BridgeRunStatePersistResult:
        """Persist one redacted immutable snapshot and atomically move current if needed."""

        normalized = _normalize_scope(scope)
        request_session_id = _canonical_session_id(str(request.session_id))
        if request_session_id != normalized.session_id:
            raise BridgeRunStateSessionRejectedError("scope_mismatch")

        now = _ensure_naive_utc(self._clock())
        snapshot = fingerprint_run_state_request(request)
        incoming = IncomingRunStateSnapshot(
            run_id=str(request.run_id),
            run_sequence=request.run_sequence,
            fingerprint=snapshot.fingerprint,
            fingerprint_version=snapshot.fingerprint_version,
            canonical_bytes=snapshot.canonical_bytes,
        )
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._require_active_session(conn, normalized, now)
                reused_request = await self._select_run_by_request_id(
                    conn,
                    session.session_id,
                    str(request.request_id),
                )
                if reused_request is not None and reused_request["run_id"] != incoming.run_id:
                    await conn.rollback()
                    return BridgeRunStatePersistResult(
                        decision=RunStateDecision(kind="conflict", reason="request_id_reuse"),
                        run_id=incoming.run_id,
                        current_run_id=session.current_run_id,
                    )

                existing_by_run_id = await self._load_persisted_run(
                    conn,
                    session.session_id,
                    run_id=incoming.run_id,
                )
                existing_by_sequence = await self._load_persisted_run(
                    conn,
                    session.session_id,
                    run_sequence=incoming.run_sequence,
                )
                current_run = None
                if session.current_run_id is not None:
                    current_run = await self._load_persisted_run(
                        conn,
                        session.session_id,
                        run_id=session.current_run_id,
                    )
                decision = decide_run_state_persistence(
                    session_status=session.status,
                    incoming=incoming,
                    existing_run_by_run_id=existing_by_run_id,
                    existing_run_by_sequence=existing_by_sequence,
                    current_run=current_run,
                )
                if decision.kind in {"conflict", "idempotent"}:
                    await conn.commit()
                    current_run_id = session.current_run_id
                    return BridgeRunStatePersistResult(decision, incoming.run_id, current_run_id)
                if decision.kind == "rejected":
                    raise BridgeRunStateSessionRejectedError("session_terminal")

                await conn.execute(
                    """
                    INSERT INTO bridge_run_state_run(
                        session_id,
                        run_id,
                        run_sequence,
                        request_id,
                        fingerprint,
                        fingerprint_version,
                        canonical_bytes,
                        run_status,
                        convergence_status,
                        snapshot_json,
                        received_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        incoming.run_id,
                        incoming.run_sequence,
                        str(request.request_id),
                        incoming.fingerprint,
                        incoming.fingerprint_version,
                        incoming.canonical_bytes,
                        request.run_status,
                        request.convergence_status,
                        incoming.canonical_bytes.decode("utf-8"),
                        now.isoformat(),
                    ),
                )
                current_run_id = session.current_run_id
                if decision.kind == "current":
                    await conn.execute(
                        """
                        UPDATE bridge_run_state_session
                        SET current_run_id=?, updated_at=?
                        WHERE session_id=? AND status='active'
                        """,
                        (incoming.run_id, now.isoformat(), session.session_id),
                    )
                    current_run_id = incoming.run_id
                await conn.commit()
                logger.info(
                    "Bridge run-state persist: event_code={} status={}",
                    "bridge_run_state_persist",
                    decision.kind,
                )
                return BridgeRunStatePersistResult(decision, incoming.run_id, current_run_id)
            except BridgeRunStateSessionRejectedError as exc:
                await _commit_expiry_or_rollback(conn, exc)
                raise
            except aiosqlite.IntegrityError:
                await conn.rollback()
                logger.info(
                    "Bridge run-state persist: event_code={} status={}",
                    "bridge_run_state_persist",
                    "conflict",
                )
                return BridgeRunStatePersistResult(
                    decision=RunStateDecision(kind="conflict", reason="run_sequence_conflict"),
                    run_id=incoming.run_id,
                    current_run_id=None,
                )
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state persist failed: event_code={} status={} exception={}",
                    "bridge_run_state_persist",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def end_session(self, scope: BridgeRunStateScope) -> BridgeRunStateSessionRecord:
        normalized = _normalize_scope(scope)
        now = _ensure_naive_utc(self._clock())
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                session = await self._select_session(conn, normalized.session_id)
                if session is None:
                    raise BridgeRunStateSessionRejectedError("session_missing")
                _reject_scope_mismatch(session, normalized)
                if session.status == "active":
                    await conn.execute(
                        """
                        UPDATE bridge_run_state_session
                        SET status='ended', current_run_id=NULL, updated_at=?, ended_at=?
                        WHERE session_id=? AND status='active'
                        """,
                        (now.isoformat(), now.isoformat(), session.session_id),
                    )
                    await conn.execute(
                        "DELETE FROM bridge_run_state_run WHERE session_id=?",
                        (session.session_id,),
                    )
                ended = await self._select_session(conn, normalized.session_id)
                if ended is None:
                    raise BridgeRunStateStoreUnavailableError("session_end_failed")
                await conn.commit()
                logger.info(
                    "Bridge run-state session end: event_code={} status={}",
                    "bridge_run_state_end",
                    ended.status,
                )
                return ended
            except BridgeRunStateSessionRejectedError:
                await conn.rollback()
                raise
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state session end failed: event_code={} status={} exception={}",
                    "bridge_run_state_end",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def delete_session(self, session_id: str) -> None:
        normalized_session_id = _canonical_session_id(session_id)
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                await conn.execute(
                    "DELETE FROM bridge_run_state_session WHERE session_id=?",
                    (normalized_session_id,),
                )
                await conn.commit()
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state delete failed: event_code={} status={} exception={}",
                    "bridge_run_state_delete",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def sweep_expired_run_state(self) -> int:
        """Clear snapshots early enough to keep run-state physical retention under TTL."""

        now = _ensure_naive_utc(self._clock())
        cutoff = (
            now
            - timedelta(hours=self._upload_ttl_hours)
            + timedelta(seconds=self._sweep_interval_seconds + self._sweep_safety_margin_seconds)
        )
        async with open_connection(self._db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                cur = await conn.execute(
                    """
                    SELECT DISTINCT s.session_id
                    FROM bridge_run_state_session AS s
                    JOIN project_status_record AS p ON p.project_id = s.project_id
                    WHERE s.status = 'active' AND p.created_at <= ?
                    """,
                    (cutoff.isoformat(),),
                )
                session_ids = [row["session_id"] for row in await cur.fetchall()]
                for session_id in session_ids:
                    await self._mark_session_gone(conn, session_id, now)
                await conn.commit()
                logger.info(
                    "Bridge run-state sweep: event_code={} status={} sessions_count={}",
                    "bridge_run_state_sweep",
                    "ok",
                    len(session_ids),
                )
                return len(session_ids)
            except aiosqlite.Error as exc:
                await conn.rollback()
                logger.error(
                    "Bridge run-state sweep failed: event_code={} status={} exception={}",
                    "bridge_run_state_sweep",
                    "store_error",
                    type(exc).__name__,
                )
                raise BridgeRunStateStoreUnavailableError("sqlite_operation_failed") from None

    async def _require_active_session(
        self,
        conn: aiosqlite.Connection,
        scope: BridgeRunStateScope,
        now: datetime,
    ) -> BridgeRunStateSessionRecord:
        project = await self._load_project(conn, scope.project_id)
        if project is None:
            raise BridgeRunStateSessionRejectedError("project_missing")
        if _is_project_expired(project.created_at, self._upload_ttl_hours, now):
            await self._mark_project_sessions_gone(conn, scope.project_id, now)
            raise BridgeRunStateSessionRejectedError("project_expired")

        session = await self._select_session(conn, scope.session_id)
        if session is None:
            raise BridgeRunStateSessionRejectedError("session_missing")
        _reject_scope_mismatch(session, scope)
        if session.status != "active":
            raise BridgeRunStateSessionRejectedError("session_terminal")
        return session

    async def _mark_project_sessions_gone(
        self,
        conn: aiosqlite.Connection,
        project_id: str,
        now: datetime,
    ) -> None:
        cur = await conn.execute(
            """
            SELECT session_id
            FROM bridge_run_state_session
            WHERE project_id=? AND status='active'
            """,
            (project_id,),
        )
        for row in await cur.fetchall():
            await self._mark_session_gone(conn, row["session_id"], now)

    async def _mark_session_gone(
        self,
        conn: aiosqlite.Connection,
        session_id: str,
        now: datetime,
    ) -> None:
        await conn.execute(
            """
            UPDATE bridge_run_state_session
            SET status='gone', current_run_id=NULL, updated_at=?, ended_at=?
            WHERE session_id=? AND status='active'
            """,
            (now.isoformat(), now.isoformat(), session_id),
        )
        await conn.execute(
            "DELETE FROM bridge_run_state_run WHERE session_id=?",
            (session_id,),
        )

    async def _load_project(
        self,
        conn: aiosqlite.Connection,
        project_id: str,
    ) -> _ProjectLifecycle | None:
        cur = await conn.execute(
            "SELECT project_id, created_at FROM project_status_record WHERE project_id=?",
            (project_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return _ProjectLifecycle(
            project_id=row["project_id"],
            created_at=_parse_datetime(row["created_at"]),
        )

    async def _select_session(
        self,
        conn: aiosqlite.Connection,
        session_id: str,
    ) -> BridgeRunStateSessionRecord | None:
        cur = await conn.execute(
            "SELECT * FROM bridge_run_state_session WHERE session_id=?",
            (session_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return _session_from_row(row)

    async def _select_run_by_run_id(
        self,
        conn: aiosqlite.Connection,
        session_id: str,
        run_id: str,
    ) -> aiosqlite.Row | None:
        cur = await conn.execute(
            """
            SELECT *
            FROM bridge_run_state_run
            WHERE session_id=? AND run_id=?
            """,
            (session_id, run_id),
        )
        return await cur.fetchone()

    async def _select_run_by_request_id(
        self,
        conn: aiosqlite.Connection,
        session_id: str,
        request_id: str,
    ) -> aiosqlite.Row | None:
        cur = await conn.execute(
            """
            SELECT *
            FROM bridge_run_state_run
            WHERE session_id=? AND request_id=?
            """,
            (session_id, request_id),
        )
        return await cur.fetchone()

    async def _load_persisted_run(
        self,
        conn: aiosqlite.Connection,
        session_id: str,
        *,
        run_id: str | None = None,
        run_sequence: int | None = None,
    ) -> PersistedRunStateRun | None:
        if run_id is not None:
            row = await self._select_run_by_run_id(conn, session_id, run_id)
        elif run_sequence is not None:
            cur = await conn.execute(
                """
                SELECT *
                FROM bridge_run_state_run
                WHERE session_id=? AND run_sequence=?
                """,
                (session_id, run_sequence),
            )
            row = await cur.fetchone()
        else:
            raise ValueError("run_id or run_sequence is required")
        if row is None:
            return None
        return PersistedRunStateRun(
            run_id=row["run_id"],
            run_sequence=int(row["run_sequence"]),
            fingerprint=row["fingerprint"],
            fingerprint_version=int(row["fingerprint_version"]),
            canonical_bytes=bytes(row["canonical_bytes"]),
        )


@dataclass(frozen=True, slots=True)
class _ProjectLifecycle:
    project_id: str
    created_at: datetime


def _session_from_row(row: aiosqlite.Row) -> BridgeRunStateSessionRecord:
    ended_raw = row["ended_at"]
    return BridgeRunStateSessionRecord(
        session_id=row["session_id"],
        project_id=row["project_id"],
        user_id=row["user_id"],
        process_generation=row["process_generation"],
        status=row["status"],
        current_run_id=row["current_run_id"],
        established_at=_parse_datetime(row["established_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        ended_at=_parse_datetime(ended_raw) if ended_raw is not None else None,
    )


def _current_from_row(row: aiosqlite.Row) -> BridgeRunStateCurrentRecord:
    return BridgeRunStateCurrentRecord(
        run_id=row["run_id"],
        run_sequence=int(row["run_sequence"]),
        request_id=row["request_id"],
        run_status=row["run_status"],
        convergence_status=row["convergence_status"],
        snapshot_json=row["snapshot_json"],
        received_at=_parse_datetime(row["received_at"]),
    )


def _coaching_snapshot_from_row(row: aiosqlite.Row) -> CoachingRunStateSnapshot:
    payload = json.loads(row["snapshot_json"])
    if not isinstance(payload, dict):
        raise ValueError("snapshot_json_not_mapping")
    return CoachingRunStateSnapshot(
        run_id=UUID(str(row["run_id"])),
        request_id=UUID(str(row["request_id"])),
        run_sequence=int(row["run_sequence"]),
        matlab_release=_require_payload_string(payload, "matlab_release"),
        client_version=_require_payload_string(payload, "client_version"),
        run_status=_require_payload_string(payload, "run_status"),
        convergence_status=_require_payload_string(payload, "convergence_status"),
        stop_reason=_optional_payload_string(payload, "stop_reason"),
        solver=_optional_payload_string(payload, "solver"),
        metrics_status=_require_payload_string(payload, "metrics_status"),
        metrics=tuple(
            _coaching_metric_from_payload(item) for item in _payload_list(payload, "metrics")
        ),
        series_status=_require_payload_string(payload, "series_status"),
        series=tuple(
            _coaching_series_from_payload(item) for item in _payload_list(payload, "series")
        ),
        received_at=_parse_datetime(row["received_at"]),
    )


def _coaching_metric_from_payload(value: object) -> CoachingRunStateMetric:
    if not isinstance(value, dict):
        raise ValueError("metric_not_mapping")
    unit = _optional_payload_string(value, "unit")
    return CoachingRunStateMetric(
        name=_require_payload_string(value, "name"),
        value=_require_payload_float(value, "value"),
        unit_status=_require_payload_string(value, "unit_status"),
        unit=unit,
    )


def _coaching_series_from_payload(value: object) -> CoachingRunStateSeries:
    if not isinstance(value, dict):
        raise ValueError("series_not_mapping")
    representation = _require_payload_string(value, "representation")
    sample_min: float | None = None
    sample_max: float | None = None
    if representation == "identity_uniform_v1":
        y_values = [_payload_float_item(item) for item in _payload_list(value, "y")]
        if y_values:
            sample_min = min(y_values)
            sample_max = max(y_values)
    elif representation == "min_max_envelope_uniform_v1":
        lows = [_payload_float_item(item) for item in _payload_list(value, "y_min")]
        highs = [_payload_float_item(item) for item in _payload_list(value, "y_max")]
        if lows:
            sample_min = min(lows)
        if highs:
            sample_max = max(highs)
    return CoachingRunStateSeries(
        series_id=_require_payload_string(value, "series_id"),
        label=_require_payload_string(value, "label"),
        representation=representation,
        time_unit=_require_payload_string(value, "time_unit"),
        value_unit_status=_require_payload_string(value, "value_unit_status"),
        source_point_count=_require_payload_int(value, "source_point_count"),
        t_start=_require_payload_float(value, "t_start"),
        sample_min=sample_min,
        sample_max=sample_max,
        value_unit=_optional_payload_string(value, "value_unit"),
    )


def _payload_list(payload: dict[object, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key}_not_list")
    return value


def _require_payload_string(payload: dict[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key}_not_string")
    return value


def _optional_payload_string(payload: dict[object, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key}_not_optional_string")
    return value


def _payload_float_item(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("number_not_numeric")
    return float(value)


def _require_payload_float(payload: dict[object, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key}_not_number")
    return float(value)


def _require_payload_int(payload: dict[object, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key}_not_int")
    return value


def _scope_from_coaching_scope(scope: CoachingRunStateScope) -> BridgeRunStateScope:
    return BridgeRunStateScope(
        user_id=scope.user_id,
        project_id=scope.project_id,
        session_id=scope.session_id,
        process_generation=scope.process_generation,
    )


def _coaching_rejection(reason: RunStateSessionRejectReason) -> CoachingRunStateReadRejectedError:
    return CoachingRunStateReadRejectedError(reason)


def _normalize_scope(scope: BridgeRunStateScope) -> BridgeRunStateScope:
    try:
        session_id = _canonical_session_id(scope.session_id)
    except ValueError:
        raise BridgeRunStateSessionRejectedError("invalid_scope") from None
    if (
        not scope.user_id
        or not scope.project_id
        or not scope.process_generation
        or scope.user_id != scope.user_id.strip()
        or scope.project_id != scope.project_id.strip()
        or scope.process_generation != scope.process_generation.strip()
    ):
        raise BridgeRunStateSessionRejectedError("invalid_scope")
    return BridgeRunStateScope(
        user_id=scope.user_id,
        project_id=scope.project_id,
        session_id=session_id,
        process_generation=scope.process_generation,
    )


def _canonical_session_id(session_id: str) -> str:
    return canonical_run_state_session_id(session_id)


def _reject_scope_mismatch(
    session: BridgeRunStateSessionRecord,
    scope: BridgeRunStateScope,
) -> None:
    if session.project_id != scope.project_id or session.user_id != scope.user_id:
        raise BridgeRunStateSessionRejectedError("scope_mismatch")
    if session.process_generation != scope.process_generation:
        raise BridgeRunStateSessionRejectedError("process_generation_mismatch")


async def _commit_expiry_or_rollback(
    conn: aiosqlite.Connection,
    exc: BridgeRunStateSessionRejectedError,
) -> None:
    if exc.reason == "project_expired":
        await conn.commit()
        return
    await conn.rollback()


def _is_project_expired(created_at: datetime, ttl_hours: int, now: datetime) -> bool:
    return created_at + timedelta(hours=ttl_hours) <= now


def _parse_datetime(value: str) -> datetime:
    return _ensure_naive_utc(datetime.fromisoformat(value))


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ensure_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
