from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from adapters.storage._connection import open_connection
from adapters.storage.sqlite_paper_cache import (
    SqlitePaperBundleStore,
    SqlitePaperPlanCacheView,
    SqlitePaperSpecCacheView,
)
from core.domain.exceptions import StoreError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperSpec, ParameterEntry


async def test_save_ready_bundle_round_trips_across_connections(
    initialized_db_path: str,
) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)

    await store.save_ready_bundle(record)

    fresh_store = SqlitePaperBundleStore(initialized_db_path)
    assert await fresh_store.get_spec("paper-1") == record.spec
    assert await fresh_store.get_plan_record("paper-1") == record


async def test_spec_only_state_is_legal(initialized_db_path: str) -> None:
    store = SqlitePaperBundleStore(initialized_db_path)
    record = _record()

    await store.put_spec(record.paper_id, record.spec)

    assert await store.get_spec(record.paper_id) == record.spec
    assert await store.get_plan_record(record.paper_id) is None


async def test_plan_only_state_raises_store_error(initialized_db_path: str) -> None:
    async with open_connection(initialized_db_path) as conn:
        await conn.execute(
            """
            INSERT INTO paper_plan_cache(
                paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                created_at, updated_at
            ) VALUES ('paper-1', '{}', '[]', '[]', 'now', 'now')
            """
        )
        await conn.commit()

    store = SqlitePaperBundleStore(initialized_db_path)

    with pytest.raises(StoreError, match="paper_bundle_incomplete"):
        await store.get_plan_record("paper-1")


async def test_plan_view_set_requires_existing_spec(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    plan_view = SqlitePaperPlanCacheView(store)

    with pytest.raises(StoreError, match="paper_spec_missing_for_plan"):
        await plan_view.set(record.paper_id, record)


async def test_views_delegate_without_multiple_inheritance(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    spec_view = SqlitePaperSpecCacheView(store)
    plan_view = SqlitePaperPlanCacheView(store)

    await spec_view.put(record.paper_id, record.spec)
    await plan_view.set(record.paper_id, record)

    assert await spec_view.get(record.paper_id) == record.spec
    assert await plan_view.get(record.paper_id) == record
    assert not isinstance(store, SqlitePaperSpecCacheView)
    assert not isinstance(store, SqlitePaperPlanCacheView)


async def test_put_spec_rejects_independent_overwrite_after_plan_exists(
    initialized_db_path: str,
) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle(record)

    with pytest.raises(StoreError, match="paper_spec_overwrite_for_existing_plan"):
        await store.put_spec(record.paper_id, record.spec)


async def test_delete_plan_leaves_spec_only_state(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle(record)

    await store.delete_plan(record.paper_id)

    assert await store.get_spec(record.paper_id) == record.spec
    assert await store.get_plan_record(record.paper_id) is None


async def test_invalidate_spec_deletes_both_rows(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle(record)

    await store.invalidate_spec(record.paper_id)

    assert await store.get_spec(record.paper_id) is None
    assert await store.get_plan_record(record.paper_id) is None


async def test_save_ready_bundle_sqlite_fault_rolls_back_both_tables(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(
        initialized_db_path,
        connection_factory=_faulting_connection_factory(),
    )

    with pytest.raises(StoreError, match="sqlite_operation_failed"):
        await store.save_ready_bundle(_record())

    async with open_connection(initialized_db_path) as conn:
        spec_count = await _count(conn, "paper_spec_cache")
        plan_count = await _count(conn, "paper_plan_cache")

    assert spec_count == 0
    assert plan_count == 0


async def test_rollback_failure_does_not_cover_primary_error(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(
        initialized_db_path,
        connection_factory=_faulting_connection_factory(rollback_fails=True),
    )

    with pytest.raises(StoreError, match="sqlite_operation_failed"):
        await store.save_ready_bundle(_record())


def _faulting_connection_factory(
    *,
    rollback_fails: bool = False,
):
    @asynccontextmanager
    async def factory(db_path: str) -> AsyncIterator[object]:
        async with open_connection(db_path) as conn:
            yield _FaultingConnection(conn, rollback_fails=rollback_fails)

    return factory


class _FaultingConnection:
    def __init__(self, conn: aiosqlite.Connection, *, rollback_fails: bool) -> None:
        self._conn = conn
        self._rollback_fails = rollback_fails

    def __getattr__(self, name: str) -> object:
        return getattr(self._conn, name)

    async def execute(self, sql: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "INSERT INTO paper_plan_cache" in sql:
            raise aiosqlite.OperationalError("injected paper_plan_cache failure")
        return await self._conn.execute(sql, *args, **kwargs)

    async def rollback(self) -> None:
        if self._rollback_fails:
            raise aiosqlite.OperationalError("injected rollback failure")
        await self._conn.rollback()


async def _count(conn: aiosqlite.Connection, table: str) -> int:
    row = await (await conn.execute(f"SELECT COUNT(*) AS count FROM {table}")).fetchone()
    return int(row["count"])


def _record() -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            abstract="A synchronous machine short-circuit report.",
            equations=[
                EquationEntry(
                    equation_id="EQ-01",
                    latex_or_text="H = 3.5",
                    paper_section_id="S1",
                )
            ],
            parameter_table=[
                ParameterEntry(
                    name="Inertia constant",
                    symbol="H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            figure_locations=[],
            pseudocode_blocks=[],
            evidence=[evidence],
        ),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[
                BlockRecommendation(
                    block_type="Synchronous Machine",
                    purpose="Model the generator.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                    value="null",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=None,
            evidence=[evidence],
        ),
        missing_prompts=[
            MissingParameterPrompt(
                prompt_id="MISS-1",
                parameter_name="H",
                paper_reference=evidence,
                suggested_unit="s",
                user_supplied_value=None,
                user_supplied_unit=None,
            )
        ],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
