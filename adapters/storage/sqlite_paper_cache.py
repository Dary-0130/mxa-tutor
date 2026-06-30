"""SQLite persistent paper bundle store and cache views."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, TypeVar, cast

import aiosqlite
from loguru import logger
from pydantic import TypeAdapter

from adapters.storage._connection import open_connection
from core.domain.exceptions import StoreError
from core.domain.paper_document_identity import (
    DEFAULT_DOCUMENT_ID,
    LEGACY_DOCUMENT_FILENAME,
    validate_paper_spec_document_identity,
)
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_parameter_conflicts import (
    detect_parameter_conflicts,
    validate_parameter_conflicts_materialized,
)
from core.domain.paper_plan import ModelGenerationPlan, PaperPlanRecord
from core.domain.paper_spec import PaperSpec, ParameterConflict, ParameterEntry
from core.interfaces.paper_cache import PaperBundleStore, PaperPlanCache, PaperSpecCache

T = TypeVar("T")
ConnectionFactory = Callable[[str], AbstractAsyncContextManager[aiosqlite.Connection]]


class SqlitePaperBundleStore(PaperBundleStore):
    """SQLite implementation for persisted paper spec and plan bundles."""

    _SPEC_ADAPTER = TypeAdapter(PaperSpec)
    _PLAN_ADAPTER = TypeAdapter(ModelGenerationPlan)
    _PROMPTS_ADAPTER = TypeAdapter(list[MissingParameterPrompt])
    _BINDINGS_ADAPTER = TypeAdapter(list[MissingParameterBinding])

    def __init__(
        self,
        db_path: str,
        connection_factory: ConnectionFactory = open_connection,
    ) -> None:
        self._db_path = db_path
        self._connection_factory = connection_factory

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        spec_json = self._dump(self._SPEC_ADAPTER, record.spec, "paper_spec_serialize_failed")
        plan_json = self._dump(self._PLAN_ADAPTER, record.plan, "paper_plan_serialize_failed")
        prompts_json = self._dump(
            self._PROMPTS_ADAPTER,
            record.missing_prompts,
            "missing_prompts_serialize_failed",
        )
        bindings_json = self._dump(
            self._BINDINGS_ADAPTER,
            record.missing_bindings,
            "missing_bindings_serialize_failed",
        )
        now = datetime.utcnow().isoformat()

        async with self._connect() as conn:
            try:
                await conn.execute("BEGIN")
                await conn.execute(
                    """
                    INSERT INTO paper_spec_cache(
                        paper_id, paper_spec_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(paper_id) DO UPDATE SET
                        paper_spec_json=excluded.paper_spec_json,
                        updated_at=excluded.updated_at
                    """,
                    (record.paper_id, spec_json, now, now),
                )
                await conn.execute(
                    """
                    INSERT INTO paper_plan_cache(
                        paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(paper_id) DO UPDATE SET
                        plan_json=excluded.plan_json,
                        missing_prompts_json=excluded.missing_prompts_json,
                        missing_bindings_json=excluded.missing_bindings_json,
                        updated_at=excluded.updated_at
                    """,
                    (record.paper_id, plan_json, prompts_json, bindings_json, now, now),
                )
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, record.paper_id)
                logger.error(
                    "SqlitePaperBundleStore.save_ready_bundle failed: paper_id={} exception={}",
                    record.paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, record.paper_id)
                raise

    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        async with self._connect() as conn:
            try:
                cur = await conn.execute(
                    "SELECT paper_spec_json FROM paper_spec_cache WHERE paper_id=?",
                    (paper_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.Error as exc:
                logger.error(
                    "SqlitePaperBundleStore.get_spec failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

        if row is None:
            return None
        return self._load(
            self._SPEC_ADAPTER, row["paper_spec_json"], "paper_spec_deserialize_failed"
        )

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        async with self._connect() as conn:
            try:
                plan_cur = await conn.execute(
                    "SELECT 1 FROM paper_plan_cache WHERE paper_id=?",
                    (paper_id,),
                )
                if await plan_cur.fetchone() is None:
                    return None

                cur = await conn.execute(
                    """
                    SELECT s.paper_spec_json,
                           p.plan_json,
                           p.missing_prompts_json,
                           p.missing_bindings_json
                    FROM paper_plan_cache AS p
                    JOIN paper_spec_cache AS s ON s.paper_id = p.paper_id
                    WHERE p.paper_id = ?
                    """,
                    (paper_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.Error as exc:
                logger.error(
                    "SqlitePaperBundleStore.get_plan_record failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

        if row is None:
            raise StoreError("paper_bundle_incomplete")
        return PaperPlanRecord(
            paper_id=paper_id,
            spec=self._load(
                self._SPEC_ADAPTER,
                row["paper_spec_json"],
                "paper_spec_deserialize_failed",
            ),
            plan=self._load(self._PLAN_ADAPTER, row["plan_json"], "paper_plan_deserialize_failed"),
            missing_prompts=self._load(
                self._PROMPTS_ADAPTER,
                row["missing_prompts_json"],
                "missing_prompts_deserialize_failed",
            ),
            missing_bindings=self._load(
                self._BINDINGS_ADAPTER,
                row["missing_bindings_json"],
                "missing_bindings_deserialize_failed",
            ),
        )

    async def delete_bundle(self, paper_id: str) -> None:
        async with self._connect() as conn:
            try:
                await conn.execute("BEGIN")
                await conn.execute("DELETE FROM paper_plan_cache WHERE paper_id=?", (paper_id,))
                await conn.execute("DELETE FROM paper_spec_cache WHERE paper_id=?", (paper_id,))
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, paper_id)
                logger.error(
                    "SqlitePaperBundleStore.delete_bundle failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, paper_id)
                raise

    async def put_spec(self, paper_id: str, spec: PaperSpec) -> None:
        spec_json = self._dump(self._SPEC_ADAPTER, spec, "paper_spec_serialize_failed")
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            try:
                await conn.execute("BEGIN")
                cur = await conn.execute(
                    "SELECT 1 FROM paper_plan_cache WHERE paper_id=?",
                    (paper_id,),
                )
                if await cur.fetchone() is not None:
                    raise StoreError("paper_spec_overwrite_for_existing_plan")
                await conn.execute(
                    """
                    INSERT INTO paper_spec_cache(
                        paper_id, paper_spec_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(paper_id) DO UPDATE SET
                        paper_spec_json=excluded.paper_spec_json,
                        updated_at=excluded.updated_at
                    """,
                    (paper_id, spec_json, now, now),
                )
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, paper_id)
                logger.error(
                    "SqlitePaperBundleStore.put_spec failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, paper_id)
                raise

    async def invalidate_spec(self, paper_id: str) -> None:
        async with self._connect() as conn:
            try:
                await conn.execute("BEGIN")
                await conn.execute("DELETE FROM paper_plan_cache WHERE paper_id=?", (paper_id,))
                await conn.execute("DELETE FROM paper_spec_cache WHERE paper_id=?", (paper_id,))
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, paper_id)
                logger.error(
                    "SqlitePaperBundleStore.invalidate_spec failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, paper_id)
                raise

    async def set_plan(self, paper_id: str, record: PaperPlanRecord) -> None:
        validate_paper_spec_document_identity(record.spec)
        plan_json = self._dump(self._PLAN_ADAPTER, record.plan, "paper_plan_serialize_failed")
        prompts_json = self._dump(
            self._PROMPTS_ADAPTER,
            record.missing_prompts,
            "missing_prompts_serialize_failed",
        )
        bindings_json = self._dump(
            self._BINDINGS_ADAPTER,
            record.missing_bindings,
            "missing_bindings_serialize_failed",
        )
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            try:
                await conn.execute("BEGIN")
                cur = await conn.execute(
                    "SELECT 1 FROM paper_spec_cache WHERE paper_id=?",
                    (paper_id,),
                )
                if await cur.fetchone() is None:
                    raise StoreError("paper_spec_missing_for_plan")
                await conn.execute(
                    """
                    INSERT INTO paper_plan_cache(
                        paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(paper_id) DO UPDATE SET
                        plan_json=excluded.plan_json,
                        missing_prompts_json=excluded.missing_prompts_json,
                        missing_bindings_json=excluded.missing_bindings_json,
                        updated_at=excluded.updated_at
                    """,
                    (paper_id, plan_json, prompts_json, bindings_json, now, now),
                )
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, paper_id)
                logger.error(
                    "SqlitePaperBundleStore.set_plan failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, paper_id)
                raise

    async def delete_plan(self, paper_id: str) -> None:
        async with self._connect() as conn:
            try:
                await conn.execute("DELETE FROM paper_plan_cache WHERE paper_id=?", (paper_id,))
                await conn.commit()
            except aiosqlite.Error as exc:
                await self._rollback_preserving_error(conn, paper_id)
                logger.error(
                    "SqlitePaperBundleStore.delete_plan failed: paper_id={} exception={}",
                    paper_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
            except Exception:
                await self._rollback_preserving_error(conn, paper_id)
                raise

    def _connect(self) -> AbstractAsyncContextManager[aiosqlite.Connection]:
        return self._connection_factory(self._db_path)

    def _dump(self, adapter: TypeAdapter[T], value: T, error_code: str) -> str:
        try:
            if adapter is self._SPEC_ADAPTER:
                spec = cast(PaperSpec, value)
                validate_paper_spec_document_identity(spec)
                validate_parameter_conflicts_materialized(spec)
            return adapter.dump_json(value).decode("utf-8")
        except (TypeError, ValueError) as exc:
            logger.error(
                "SqlitePaperBundleStore serialize failed: error_code={} exception={}",
                error_code,
                type(exc).__name__,
            )
            raise StoreError(error_code) from None

    def _load(self, adapter: TypeAdapter[T], payload: str, error_code: str) -> T:
        if adapter is self._SPEC_ADAPTER:
            return cast(T, self._load_spec_with_migration(payload, error_code))
        if adapter is self._PLAN_ADAPTER or adapter is self._PROMPTS_ADAPTER:
            return self._load_with_nested_evidence_migration(adapter, payload, error_code)
        try:
            return adapter.validate_json(payload)
        except (TypeError, ValueError) as exc:
            logger.error(
                "SqlitePaperBundleStore deserialize failed: error_code={} exception={}",
                error_code,
                type(exc).__name__,
            )
            raise StoreError(error_code) from None

    def _load_spec_with_migration(self, payload: str, error_code: str) -> PaperSpec:
        try:
            raw = json.loads(payload)
            if not isinstance(raw, dict):
                raise TypeError("paper spec payload must be an object")
            migrated = _migrate_spec_payload(raw)
            spec = self._SPEC_ADAPTER.validate_python(migrated)
            validate_paper_spec_document_identity(spec)
            validate_parameter_conflicts_materialized(spec)
            return spec
        except (TypeError, ValueError) as exc:
            logger.error(
                "SqlitePaperBundleStore deserialize failed: error_code={} exception={}",
                error_code,
                type(exc).__name__,
            )
            raise StoreError(error_code) from None

    def _load_with_nested_evidence_migration(
        self,
        adapter: TypeAdapter[T],
        payload: str,
        error_code: str,
    ) -> T:
        try:
            raw = json.loads(payload)
            migrated = _migrate_nested_evidence_payloads(raw)
            return adapter.validate_python(migrated)
        except (TypeError, ValueError) as exc:
            logger.error(
                "SqlitePaperBundleStore deserialize failed: error_code={} exception={}",
                error_code,
                type(exc).__name__,
            )
            raise StoreError(error_code) from None

    async def _rollback_preserving_error(
        self,
        conn: aiosqlite.Connection,
        paper_id: str,
    ) -> None:
        try:
            await conn.rollback()
        except Exception as rollback_exc:
            logger.error(
                "paper bundle rollback failed: paper_id={} exception={}",
                paper_id,
                type(rollback_exc).__name__,
            )


def _migrate_spec_payload(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    legacy_identity = "documents" not in migrated or "primary_document_id" not in migrated
    if "documents" not in migrated:
        migrated["documents"] = [
            {
                "document_id": DEFAULT_DOCUMENT_ID,
                "filename": LEGACY_DOCUMENT_FILENAME,
            }
        ]
    if "primary_document_id" not in migrated:
        migrated["primary_document_id"] = None

    if legacy_identity:
        _add_missing_document_ids_to_spec_evidence(migrated.get("evidence"))
        _add_missing_document_ids_to_parameters(migrated.get("parameter_table"))
    if _is_legacy_single_document_payload(migrated):
        _add_missing_document_ids_to_extracted_items(migrated.get("equations"))
        _add_missing_document_ids_to_extracted_items(migrated.get("figure_locations"))
    _refresh_parameter_conflicts(migrated)
    return migrated


def _refresh_parameter_conflicts(payload: dict[str, Any]) -> None:
    parameters = TypeAdapter(list[ParameterEntry]).validate_python(
        payload.get("parameter_table", [])
    )
    computed = TypeAdapter(list[ParameterConflict]).dump_python(
        detect_parameter_conflicts(parameters),
        mode="json",
    )
    if "parameter_conflicts" not in payload:
        payload["parameter_conflicts"] = computed
        return
    if payload["parameter_conflicts"] != computed:
        raise ValueError("parameter_conflicts_mismatch")


def _migrate_nested_evidence_payloads(payload: Any) -> Any:
    legacy_evidence_payload = not _any_evidence_payload_has_document_id(payload)
    return _visit_evidence_payloads(payload, fill_missing=legacy_evidence_payload)


def _add_missing_document_ids_to_spec_evidence(value: Any) -> None:
    if not isinstance(value, list):
        return
    for entry in value:
        if not isinstance(entry, dict) or "document_id" in entry:
            continue
        document_id = _document_id_for_source(entry.get("source"))
        if document_id is not _MISSING:
            entry["document_id"] = document_id


def _add_missing_document_ids_to_parameters(value: Any) -> None:
    if not isinstance(value, list):
        return
    for entry in value:
        if not isinstance(entry, dict) or "document_id" in entry:
            continue
        document_id = _document_id_for_source(entry.get("source"))
        if document_id is not _MISSING:
            entry["document_id"] = document_id


def _add_missing_document_ids_to_extracted_items(value: Any) -> None:
    if not isinstance(value, list):
        return
    for entry in value:
        if isinstance(entry, dict) and "document_id" not in entry:
            entry["document_id"] = DEFAULT_DOCUMENT_ID


def _is_legacy_single_document_payload(payload: dict[str, Any]) -> bool:
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) != 1:
        return False
    document = documents[0]
    return isinstance(document, dict) and document.get("document_id") == DEFAULT_DOCUMENT_ID


def _visit_evidence_payloads(value: Any, *, fill_missing: bool) -> Any:
    if isinstance(value, list):
        return [_visit_evidence_payloads(item, fill_missing=fill_missing) for item in value]
    if not isinstance(value, dict):
        return value

    result = {
        key: _visit_evidence_payloads(item, fill_missing=fill_missing)
        for key, item in value.items()
    }
    if fill_missing and _looks_like_evidence_payload(result) and "document_id" not in result:
        document_id = _document_id_for_source(result.get("source"))
        if document_id is not _MISSING:
            result["document_id"] = document_id
    return result


def _any_evidence_payload_has_document_id(value: Any) -> bool:
    if isinstance(value, list):
        return any(_any_evidence_payload_has_document_id(item) for item in value)
    if not isinstance(value, dict):
        return False
    if _looks_like_evidence_payload(value) and "document_id" in value:
        return True
    return any(_any_evidence_payload_has_document_id(item) for item in value.values())


_EVIDENCE_KEYS = frozenset(
    {
        "paper_section_id",
        "equation_id",
        "figure_id",
        "excerpt",
        "missing_param_prompt_id",
    }
)
_MISSING = object()


def _looks_like_evidence_payload(value: dict[str, Any]) -> bool:
    return "source" in value and any(key in value for key in _EVIDENCE_KEYS)


def _document_id_for_source(source: object) -> str | None | object:
    if source == "document_extracted":
        return DEFAULT_DOCUMENT_ID
    if source == "user_supplied":
        return None
    return _MISSING


class SqlitePaperSpecCacheView(PaperSpecCache):
    """PaperSpecCache view backed by SqlitePaperBundleStore."""

    def __init__(self, store: SqlitePaperBundleStore) -> None:
        self._store = store

    async def get(self, paper_id: str) -> PaperSpec | None:
        return await self._store.get_spec(paper_id)

    async def put(self, paper_id: str, spec: PaperSpec) -> None:
        await self._store.put_spec(paper_id, spec)

    async def invalidate(self, paper_id: str) -> None:
        await self._store.invalidate_spec(paper_id)


class SqlitePaperPlanCacheView(PaperPlanCache):
    """PaperPlanCache view backed by SqlitePaperBundleStore."""

    def __init__(self, store: SqlitePaperBundleStore) -> None:
        self._store = store

    async def get(self, paper_id: str) -> PaperPlanRecord | None:
        return await self._store.get_plan_record(paper_id)

    async def set(self, paper_id: str, record: PaperPlanRecord) -> None:
        await self._store.set_plan(paper_id, record)

    async def delete(self, paper_id: str) -> None:
        await self._store.delete_plan(paper_id)
