"""SQLite TeachingUnitStore implementation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, cast

import aiosqlite
from loguru import logger

from adapters.storage._connection import open_connection
from core.domain.exceptions import ProjectNotFoundError, StoreError
from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit, TeachingUnitRef
from core.interfaces.teaching_unit_store import (
    CacheKey,
    CacheState,
    TeachingUnitCacheRecord,
    TeachingUnitStore,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class SqliteTeachingUnitStore(TeachingUnitStore):
    """SQLite-backed TeachingUnit cache with stateful records."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """MCS stage opens and closes connections per method."""

    async def get_record_by_key(self, cache_key: CacheKey) -> TeachingUnitCacheRecord | None:
        async with open_connection(self._db_path) as conn:
            try:
                row = await _fetch_by_key(conn, cache_key)
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteTeachingUnitStore.get_record_by_key failed: project_id={} "
                    "exception={}",
                    cache_key[0],
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return _record_from_row(row) if row is not None else None

    async def begin_generating(self, cache_key: CacheKey, now: int, expires_at: int) -> bool:
        unit_id = _unit_id_for_key(cache_key)
        async with open_connection(self._db_path) as conn:
            try:
                await conn.execute("BEGIN IMMEDIATE")
                await _ensure_project_exists(conn, cache_key[0])
                cur = await conn.execute(
                    "INSERT OR IGNORE INTO teaching_units("
                    "teaching_unit_id, project_id, target_type, target_id, level, "
                    "payload_json, source_refs_json, prerequisites_json, builder_version, "
                    "prompt_version, model_name, source_version, state, error_code, "
                    "retry_count, created_at, updated_at, expires_at"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        unit_id,
                        cache_key[0],
                        cache_key[1],
                        cache_key[2],
                        cache_key[3],
                        "{}",
                        "[]",
                        "[]",
                        cache_key[4],
                        cache_key[5],
                        cache_key[6],
                        cache_key[7],
                        "generating",
                        None,
                        0,
                        now,
                        now,
                        expires_at,
                    ),
                )
                if cur.rowcount == 1:
                    await conn.commit()
                    return True

                row = await _fetch_by_key(conn, cache_key)
                if row is None:
                    await conn.rollback()
                    return False

                state = str(row["state"])
                expired = int(row["expires_at"]) < now
                if state == "failed_permanent" or state == "generating":
                    await conn.rollback()
                    return False
                if state != "failed_retryable" and not expired:
                    await conn.rollback()
                    return False

                retry_count = int(row["retry_count"])
                if expired and state == "ready":
                    retry_count = 0
                cur = await conn.execute(
                    "UPDATE teaching_units SET state='generating', error_code=NULL, "
                    "retry_count=?, updated_at=?, expires_at=? "
                    "WHERE project_id=? AND target_type=? AND target_id=? AND level=? "
                    "AND builder_version=? AND prompt_version=? AND model_name=? "
                    "AND source_version=? AND state!='generating' "
                    "AND state!='failed_permanent'",
                    (retry_count, now, expires_at, *cache_key),
                )
                await conn.commit()
            except ProjectNotFoundError:
                await conn.rollback()
                raise
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteTeachingUnitStore.begin_generating failed: project_id={} "
                    "exception={}",
                    cache_key[0],
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return cur.rowcount == 1

    async def mark_ready(self, cache_key: CacheKey, unit: TeachingUnit) -> None:
        payload_json = json.dumps(_payload_from_unit(unit), ensure_ascii=False, sort_keys=True)
        source_refs_json = json.dumps(
            [_dataclass_to_dict(ref) for ref in unit.source_refs],
            ensure_ascii=False,
            sort_keys=True,
        )
        prerequisites_json = json.dumps(
            [_prerequisite_to_json(item) for item in unit.prerequisites],
            ensure_ascii=False,
            sort_keys=True,
        )
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "UPDATE teaching_units SET teaching_unit_id=?, state='ready', "
                    "payload_json=?, source_refs_json=?, prerequisites_json=?, "
                    "error_code=NULL, updated_at=? "
                    "WHERE project_id=? AND target_type=? AND target_id=? AND level=? "
                    "AND builder_version=? AND prompt_version=? AND model_name=? "
                    "AND source_version=? AND state='generating'",
                    (
                        unit.id,
                        payload_json,
                        source_refs_json,
                        prerequisites_json,
                        _now(),
                        *cache_key,
                    ),
                )
                if cur.rowcount == 0:
                    await conn.rollback()
                    raise ValueError("teaching_unit_not_generating")
                await conn.commit()
            except ValueError:
                raise
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteTeachingUnitStore.mark_ready failed: project_id={} exception={}",
                    cache_key[0],
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def mark_failed(self, cache_key: CacheKey, error_code: str, retryable: bool) -> None:
        state = "failed_retryable" if retryable else "failed_permanent"
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "UPDATE teaching_units SET state=?, error_code=?, "
                    "retry_count=retry_count + 1, updated_at=? "
                    "WHERE project_id=? AND target_type=? AND target_id=? AND level=? "
                    "AND builder_version=? AND prompt_version=? AND model_name=? "
                    "AND source_version=? AND state='generating'",
                    (state, error_code, _now(), *cache_key),
                )
                if cur.rowcount == 0:
                    await conn.rollback()
                    raise ValueError("teaching_unit_not_generating")
                await conn.commit()
            except ValueError:
                raise
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteTeachingUnitStore.mark_failed failed: project_id={} exception={}",
                    cache_key[0],
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def list_ready_by_project(self, project_id: str) -> list[TeachingUnit]:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT * FROM teaching_units WHERE project_id=? AND state='ready' "
                    "ORDER BY updated_at ASC, teaching_unit_id ASC",
                    (project_id,),
                )
                rows = await cur.fetchall()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteTeachingUnitStore.list_ready_by_project failed: project_id={} "
                    "exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return [_unit_from_row(row) for row in rows]

    async def delete_by_project(self, project_id: str) -> int:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "DELETE FROM teaching_units WHERE project_id=?",
                    (project_id,),
                )
                await conn.commit()
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteTeachingUnitStore.delete_by_project failed: project_id={} "
                    "exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return int(cur.rowcount or 0)


async def _fetch_by_key(
    conn: aiosqlite.Connection,
    cache_key: CacheKey,
) -> aiosqlite.Row | None:
    cur = await conn.execute(
        "SELECT * FROM teaching_units WHERE project_id=? AND target_type=? "
        "AND target_id=? AND level=? AND builder_version=? AND prompt_version=? "
        "AND model_name=? AND source_version=?",
        cache_key,
    )
    return await cur.fetchone()


async def _ensure_project_exists(conn: aiosqlite.Connection, project_id: str) -> None:
    cur = await conn.execute(
        "SELECT 1 FROM project_status_record WHERE project_id=?",
        (project_id,),
    )
    if await cur.fetchone() is None:
        raise ProjectNotFoundError(f"project not found: {project_id}")


def _record_from_row(row: aiosqlite.Row) -> TeachingUnitCacheRecord:
    state = cast(CacheState, row["state"])
    return TeachingUnitCacheRecord(
        cache_key=_cache_key_from_row(row),
        state=state,
        unit=_unit_from_row(row) if state == "ready" else None,
        error_code=row["error_code"],
        retry_count=int(row["retry_count"]),
        expires_at=int(row["expires_at"]),
    )


def _unit_from_row(row: aiosqlite.Row) -> TeachingUnit:
    payload = _json_object(row["payload_json"])
    prerequisites = [
        _teaching_unit_ref_from_json(item) for item in _json_list(row["prerequisites_json"])
    ]
    source_refs = [_source_ref_from_json(item) for item in _json_list(row["source_refs_json"])]
    kwargs: dict[str, Any] = {
        "id": str(payload.get("id") or row["teaching_unit_id"]),
        "title": str(payload.get("title") or ""),
        "target": row["target_type"],
        "target_id": row["target_id"],
        "level": row["level"],
        "summary": str(payload.get("summary") or ""),
        "prerequisites": prerequisites,
        "explanation_steps": _string_list(payload.get("explanation_steps")),
        "knowledge_points": _string_list(payload.get("knowledge_points")),
        "source_refs": source_refs,
        "confusion_points": _string_list(payload.get("confusion_points")),
    }
    return TeachingUnit(**kwargs)


def _payload_from_unit(unit: TeachingUnit) -> dict[str, Any]:
    return {
        "id": unit.id,
        "title": unit.title,
        "summary": unit.summary,
        "explanation_steps": list(unit.explanation_steps),
        "knowledge_points": list(unit.knowledge_points),
        "confusion_points": list(unit.confusion_points),
    }


def _source_ref_from_json(value: object) -> SourceRef:
    if not isinstance(value, dict):
        raise StoreError("invalid_source_ref_json")
    line_range = value.get("line_range")
    return SourceRef(
        file_path=str(value.get("file_path") or ""),
        line_range=tuple(line_range) if isinstance(line_range, list) else line_range,
        block_id=_optional_str(value.get("block_id")),
        block_name=_optional_str(value.get("block_name")),
        parent_subsystem=_optional_str(value.get("parent_subsystem")),
        parameter_name=_optional_str(value.get("parameter_name")),
    )


def _teaching_unit_ref_from_json(value: object) -> TeachingUnitRef:
    if not isinstance(value, dict):
        raise StoreError("invalid_prerequisite_json")
    return TeachingUnitRef(
        project_id=str(value.get("project_id") or ""),
        teaching_unit_id=str(value.get("teaching_unit_id") or ""),
    )


def _cache_key_from_row(row: aiosqlite.Row) -> CacheKey:
    return (
        row["project_id"],
        row["target_type"],
        row["target_id"],
        row["level"],
        row["builder_version"],
        row["prompt_version"],
        row["model_name"],
        row["source_version"],
    )


def _unit_id_for_key(cache_key: CacheKey) -> str:
    digest = hashlib.sha256("\x1f".join(cache_key).encode("utf-8")).hexdigest()
    return f"tu-{digest[:32]}"


def _dataclass_to_dict(value: object) -> dict[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return cast(dict[str, object], asdict(cast("DataclassInstance", value)))
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    raise StoreError("invalid_dataclass_payload")


def _prerequisite_to_json(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(cast("DataclassInstance", value))
    return value


def _json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise StoreError("invalid_teaching_unit_json") from None
    if not isinstance(value, dict):
        raise StoreError("invalid_teaching_unit_json")
    return value


def _json_list(raw: str) -> list[Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise StoreError("invalid_teaching_unit_json") from None
    if not isinstance(value, list):
        raise StoreError("invalid_teaching_unit_json")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _now() -> int:
    return int(time.time())
