import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import aiosqlite
import pytest

from adapters.storage._connection import open_connection
from adapters.storage.sqlite_paper_cache import (
    SqlitePaperBundleStore,
    SqlitePaperPlanCacheView,
    SqlitePaperSpecCacheView,
)
from core.domain.exceptions import StoreError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_parameter_correction import (
    PaperParameterCorrection,
    PlanCorrectionTarget,
)
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_reparse_source import (
    PaperReparseDocumentSource,
    PaperReparseLocatorIndex,
    PaperReparseSource,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry


async def test_save_ready_bundle_round_trips_across_connections(
    initialized_db_path: str,
) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)

    await store.save_ready_bundle(record)

    fresh_store = SqlitePaperBundleStore(initialized_db_path)
    assert await fresh_store.get_spec("paper-1") == record.spec
    assert await fresh_store.get_plan_record("paper-1") == record


async def test_save_ready_bundle_with_source_round_trips_minimal_source(
    initialized_db_path: str,
) -> None:
    record = _record()
    source = _source(record.paper_id)
    store = SqlitePaperBundleStore(initialized_db_path)

    await store.save_ready_bundle_with_source(record, source)

    assert await store.get_plan_record(record.paper_id) == record
    assert await store.get_reparse_source(record.paper_id) == source
    async with open_connection(initialized_db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT source_json FROM paper_reparse_source_cache WHERE paper_id=?",
                (record.paper_id,),
            )
        ).fetchone()
    payload = json.loads(row["source_json"])
    document = payload["documents"][0]
    assert document["raw_text"] == "paper text"
    assert document["filename"] == "paper.pdf"
    assert "file_path" not in document
    assert "bytes" not in document


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


async def test_delete_bundle_deletes_reparse_source(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle_with_source(record, _source(record.paper_id))
    await store.insert_parameter_correction(_correction(record.paper_id))

    await store.delete_bundle(record.paper_id)

    assert await store.get_spec(record.paper_id) is None
    assert await store.get_plan_record(record.paper_id) is None
    async with open_connection(initialized_db_path) as conn:
        assert await _count(conn, "paper_reparse_source_cache") == 0
        assert await _count(conn, "paper_parameter_correction") == 0


async def test_invalidate_spec_deletes_both_rows(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle(record)

    await store.invalidate_spec(record.paper_id)

    assert await store.get_spec(record.paper_id) is None
    assert await store.get_plan_record(record.paper_id) is None


async def test_invalidate_spec_deletes_reparse_source(initialized_db_path: str) -> None:
    record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle_with_source(record, _source(record.paper_id))

    await store.invalidate_spec(record.paper_id)

    async with open_connection(initialized_db_path) as conn:
        assert await _count(conn, "paper_reparse_source_cache") == 0


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


async def test_replace_ready_bundle_source_fault_rolls_back_all_tables(
    initialized_db_path: str,
) -> None:
    old_record = _record()
    old_source = _source(old_record.paper_id, text="old text")
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle_with_source(old_record, old_source)
    faulting_store = SqlitePaperBundleStore(
        initialized_db_path,
        connection_factory=_faulting_connection_factory(fail_on_source_update=True),
    )
    new_record = _record(title="New title")

    with pytest.raises(StoreError, match="sqlite_operation_failed"):
        await faulting_store.replace_ready_bundle_with_source(
            new_record,
            _source(old_record.paper_id, text="new text"),
        )

    fresh_store = SqlitePaperBundleStore(initialized_db_path)
    assert await fresh_store.get_plan_record(old_record.paper_id) == old_record
    assert await fresh_store.get_reparse_source(old_record.paper_id) == old_source


async def test_replace_ready_bundle_with_source_clears_parameter_corrections(
    initialized_db_path: str,
) -> None:
    old_record = _record()
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.save_ready_bundle_with_source(old_record, _source(old_record.paper_id))
    await store.insert_parameter_correction(_correction(old_record.paper_id))

    await store.replace_ready_bundle_with_source(
        _record(title="Reparsed report"),
        _source(old_record.paper_id, text="new text"),
    )

    assert await store.list_parameter_corrections(old_record.paper_id) == []


async def test_delete_expired_paper_bundles_cascades_plan_spec_source(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(initialized_db_path)
    record = _record()
    await store.save_ready_bundle_with_source(record, _source(record.paper_id))
    await store.insert_parameter_correction(_correction(record.paper_id))
    expired = datetime(2026, 7, 2, 12, 0, 0)
    async with open_connection(initialized_db_path) as conn:
        await conn.execute(
            "UPDATE paper_spec_cache SET created_at=? WHERE paper_id=?",
            ((expired - timedelta(hours=25)).isoformat(), record.paper_id),
        )
        await conn.commit()

    deleted = await store.delete_expired_paper_bundles(now=expired)

    assert deleted == 1
    async with open_connection(initialized_db_path) as conn:
        assert await _count(conn, "paper_plan_cache") == 0
        assert await _count(conn, "paper_spec_cache") == 0
        assert await _count(conn, "paper_reparse_source_cache") == 0
        assert await _count(conn, "paper_parameter_correction") == 0


async def test_delete_expired_paper_bundles_cleans_orphan_parameter_corrections(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(initialized_db_path)
    await store.insert_parameter_correction(_correction("orphan-paper"))

    deleted = await store.delete_expired_paper_bundles(now=datetime(2026, 7, 2, 12, 0, 0))

    assert deleted == 0
    async with open_connection(initialized_db_path) as conn:
        assert await _count(conn, "paper_parameter_correction") == 0


async def test_parameter_correction_crud_round_trips_and_preserves_original(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(initialized_db_path)
    correction = _correction("paper-1")

    await store.insert_parameter_correction(correction)
    await store.update_parameter_correction_value(
        "paper-1",
        correction.correction_id,
        corrected_value="4.0",
        corrected_unit="s",
        updated_at="2026-07-02T01:00:00",
    )

    fetched = await store.get_parameter_correction("paper-1", correction.correction_id)
    assert fetched == PaperParameterCorrection(
        correction_id=correction.correction_id,
        paper_id=correction.paper_id,
        param_key=correction.param_key,
        plan_target=correction.plan_target,
        original_value=correction.original_value,
        original_unit=correction.original_unit,
        original_source=correction.original_source,
        original_document_id=correction.original_document_id,
        corrected_value="4.0",
        corrected_unit="s",
        created_at=correction.created_at,
        updated_at="2026-07-02T01:00:00",
    )
    assert await store.list_parameter_corrections("paper-1") == [fetched]

    await store.delete_parameter_correction("paper-1", correction.correction_id)

    assert await store.get_parameter_correction("paper-1", correction.correction_id) is None
    assert await store.list_parameter_corrections("paper-1") == []


async def test_legacy_user_supplied_evidence_readback_normalizes_user_action(
    initialized_db_path: str,
) -> None:
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_json(_current_spec_payload()),
        plan_json=_legacy_user_supplied_plan_json(),
        missing_prompts_json=_current_missing_prompts_json(),
    )

    record = await SqlitePaperBundleStore(initialized_db_path).get_plan_record("paper-1")

    assert record is not None
    user_evidence = record.plan.evidence[-1]
    assert user_evidence.source is EvidenceSource.USER_SUPPLIED
    assert user_evidence.missing_param_prompt_id == "MISS-1"
    assert user_evidence.user_action is UserEvidenceAction.FILL_MISSING


async def test_rollback_failure_does_not_cover_primary_error(
    initialized_db_path: str,
) -> None:
    store = SqlitePaperBundleStore(
        initialized_db_path,
        connection_factory=_faulting_connection_factory(rollback_fails=True),
    )

    with pytest.raises(StoreError, match="sqlite_operation_failed"):
        await store.save_ready_bundle(_record())


async def test_legacy_spec_json_migrates_single_document_identity(
    initialized_db_path: str,
) -> None:
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_old_spec_json(),
        plan_json=None,
        missing_prompts_json=None,
    )

    spec = await SqlitePaperBundleStore(initialized_db_path).get_spec("paper-1")

    assert spec is not None
    assert spec.documents == [PaperDocument(document_id="DOC-001", filename="legacy_document")]
    assert spec.primary_document_id is None
    assert spec.evidence[0].document_id == "DOC-001"
    assert spec.parameter_table[0].document_id == "DOC-001"
    assert spec.equations[0].document_id == "DOC-001"


async def test_legacy_521a_spec_migrates_equation_and_figure_document_ids(
    initialized_db_path: str,
) -> None:
    payload = _old_spec_payload()
    payload["documents"] = [{"document_id": "DOC-001", "filename": "paper.pdf"}]
    payload["primary_document_id"] = None
    payload["parameter_table"][0]["document_id"] = "DOC-001"  # type: ignore[index]
    payload["evidence"][0]["document_id"] = "DOC-001"  # type: ignore[index]
    payload["figure_locations"] = [
        {
            "figure_id": "FIG-01",
            "caption": "Machine parameters",
            "paper_section_id": "S1",
        }
    ]
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_json(payload),
        plan_json=None,
        missing_prompts_json=None,
    )

    spec = await SqlitePaperBundleStore(initialized_db_path).get_spec("paper-1")

    assert spec is not None
    assert spec.equations[0].document_id == "DOC-001"
    assert spec.figure_locations[0].document_id == "DOC-001"


async def test_legacy_spec_json_recomputes_missing_parameter_conflicts(
    initialized_db_path: str,
) -> None:
    payload = _conflict_spec_payload()
    payload.pop("parameter_conflicts")
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_json(payload),
        plan_json=None,
        missing_prompts_json=None,
    )

    spec = await SqlitePaperBundleStore(initialized_db_path).get_spec("paper-1")

    assert spec is not None
    assert [
        (option.value, option.unit) for option in spec.parameter_conflicts[0].value_options
    ] == [
        ("3.5", "s"),
        ("4.0", "s"),
    ]


async def test_stored_parameter_conflicts_must_match_recomputed_view(
    initialized_db_path: str,
) -> None:
    payload = _conflict_spec_payload()
    payload["parameter_conflicts"] = []
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_json(payload),
        plan_json=None,
        missing_prompts_json=None,
    )

    with pytest.raises(StoreError, match="paper_spec_deserialize_failed"):
        await SqlitePaperBundleStore(initialized_db_path).get_spec("paper-1")


async def test_legacy_plan_and_missing_json_migrates_nested_evidence(
    initialized_db_path: str,
) -> None:
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_old_spec_json(),
        plan_json=_old_plan_json(),
        missing_prompts_json=_old_missing_prompts_json(),
    )

    record = await SqlitePaperBundleStore(initialized_db_path).get_plan_record("paper-1")

    assert record is not None
    assert record.plan.evidence[0].document_id == "DOC-001"
    assert record.plan.block_recommendations[0].paper_reference.document_id == "DOC-001"
    assert record.plan.build_steps is not None
    assert record.plan.build_steps[0].evidence[0].document_id == "DOC-001"
    assert record.plan.build_steps[0].block_refs[0].paper_reference is not None
    assert record.plan.build_steps[0].block_refs[0].paper_reference.document_id == "DOC-001"
    assert record.plan.build_steps[0].configuration_hints[0].evidence[0].document_id == "DOC-001"
    assert record.missing_prompts[0].paper_reference.document_id == "DOC-001"


async def test_new_bad_spec_json_without_nested_document_id_fails(
    initialized_db_path: str,
) -> None:
    payload = _old_spec_payload()
    payload["documents"] = [{"document_id": "DOC-001", "filename": "paper.pdf"}]
    payload["primary_document_id"] = None
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_json(payload),
        plan_json=None,
        missing_prompts_json=None,
    )

    with pytest.raises(StoreError, match="paper_spec_deserialize_failed"):
        await SqlitePaperBundleStore(initialized_db_path).get_spec("paper-1")


async def test_new_bad_plan_json_without_nested_document_id_fails(
    initialized_db_path: str,
) -> None:
    plan_payload = json.loads(_old_plan_json())
    plan_payload["evidence"][0]["document_id"] = "DOC-001"
    await _insert_bundle(
        initialized_db_path,
        paper_spec_json=_old_spec_json(),
        plan_json=_json(plan_payload),
        missing_prompts_json=_old_missing_prompts_json(),
    )

    with pytest.raises(StoreError, match="paper_plan_deserialize_failed"):
        await SqlitePaperBundleStore(initialized_db_path).get_plan_record("paper-1")


def _faulting_connection_factory(
    *,
    rollback_fails: bool = False,
    fail_on_source_update: bool = False,
):
    @asynccontextmanager
    async def factory(db_path: str) -> AsyncIterator[object]:
        async with open_connection(db_path) as conn:
            yield _FaultingConnection(
                conn,
                rollback_fails=rollback_fails,
                fail_on_source_update=fail_on_source_update,
            )

    return factory


class _FaultingConnection:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        *,
        rollback_fails: bool,
        fail_on_source_update: bool,
    ) -> None:
        self._conn = conn
        self._rollback_fails = rollback_fails
        self._fail_on_source_update = fail_on_source_update

    def __getattr__(self, name: str) -> object:
        return getattr(self._conn, name)

    async def execute(self, sql: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "INSERT INTO paper_plan_cache" in sql:
            raise aiosqlite.OperationalError("injected paper_plan_cache failure")
        if self._fail_on_source_update and "UPDATE paper_reparse_source_cache" in sql:
            raise aiosqlite.OperationalError("injected source failure")
        return await self._conn.execute(sql, *args, **kwargs)

    async def rollback(self) -> None:
        if self._rollback_fails:
            raise aiosqlite.OperationalError("injected rollback failure")
        await self._conn.rollback()


async def _count(conn: aiosqlite.Connection, table: str) -> int:
    row = await (await conn.execute(f"SELECT COUNT(*) AS count FROM {table}")).fetchone()
    return int(row["count"])


async def _insert_bundle(
    db_path: str,
    *,
    paper_spec_json: str,
    plan_json: str | None,
    missing_prompts_json: str | None,
) -> None:
    async with open_connection(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO paper_spec_cache(paper_id, paper_spec_json, created_at, updated_at)
            VALUES (?, ?, 'now', 'now')
            """,
            ("paper-1", paper_spec_json),
        )
        if plan_json is not None and missing_prompts_json is not None:
            await conn.execute(
                """
                INSERT INTO paper_plan_cache(
                    paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, '[]', 'now', 'now')
                """,
                ("paper-1", plan_json, missing_prompts_json),
            )
        await conn.commit()


def _old_spec_json() -> str:
    return _json(_old_spec_payload())


def _old_plan_json() -> str:
    evidence = _old_document_evidence_payload()
    return _json(
        {
            "plan_id": "PLAN-paper-1",
            "paper_spec_id": "paper-1",
            "library_choice": "SimPowerSystems",
            "block_recommendations": [
                {
                    "block_type": "Synchronous Machine",
                    "purpose": "Model the generator.",
                    "paper_reference": evidence,
                }
            ],
            "parameter_mapping": [],
            "subsystem_breakdown": ["Place machine", "Apply fault", "Observe current"],
            "m_script_skeleton": None,
            "evidence": [evidence],
            "build_steps": [
                {
                    "step_id": "STEP-001",
                    "title": "Place machine",
                    "intent": "Create the machine subsystem.",
                    "block_refs": [
                        {
                            "block_ref_id": "B1",
                            "block_type": "Synchronous Machine",
                            "library_path": None,
                            "purpose": "Model the generator.",
                            "paper_reference": evidence,
                        }
                    ],
                    "parameter_refs": [],
                    "connection_hints": [],
                    "configuration_hints": [
                        {
                            "target": "solver",
                            "setting_name": None,
                            "instruction": "Use the configured solver.",
                            "evidence": [evidence],
                        }
                    ],
                    "depends_on": [],
                    "evidence": [evidence],
                    "display_text": "Place machine.",
                }
            ],
        }
    )


def _old_missing_prompts_json() -> str:
    return _json(
        [
            {
                "prompt_id": "MISS-1",
                "parameter_name": "H",
                "paper_reference": _old_document_evidence_payload(),
                "suggested_unit": "s",
                "user_supplied_value": None,
                "user_supplied_unit": None,
                "source": "user_supplied",
            }
        ]
    )


def _current_missing_prompts_json() -> str:
    evidence = {**_old_document_evidence_payload(), "document_id": "DOC-001"}
    return _json(
        [
            {
                "prompt_id": "MISS-1",
                "parameter_name": "H",
                "paper_reference": evidence,
                "suggested_unit": "s",
                "user_supplied_value": None,
                "user_supplied_unit": None,
                "source": "user_supplied",
            }
        ]
    )


def _old_spec_payload() -> dict[str, object]:
    return {
        "paper_title": "Short-circuit report",
        "paper_type": "report",
        "domain": "motor_control",
        "abstract": "A synchronous machine short-circuit report.",
        "equations": [
            {
                "equation_id": "EQ-01",
                "latex_or_text": "H = 3.5",
                "paper_section_id": "S1",
            }
        ],
        "parameter_table": [
            {
                "name": "Inertia constant",
                "symbol": "H",
                "value": "3.5",
                "unit": "s",
                "source": "document_extracted",
            }
        ],
        "figure_locations": [],
        "pseudocode_blocks": [],
        "evidence": [_old_document_evidence_payload()],
    }


def _current_spec_payload() -> dict[str, object]:
    payload = _old_spec_payload()
    payload["documents"] = [{"document_id": "DOC-001", "filename": "paper.pdf"}]
    payload["primary_document_id"] = None
    payload["parameter_table"][0]["document_id"] = "DOC-001"  # type: ignore[index]
    payload["equations"][0]["document_id"] = "DOC-001"  # type: ignore[index]
    payload["evidence"][0]["document_id"] = "DOC-001"  # type: ignore[index]
    payload["parameter_conflicts"] = []
    return payload


def _conflict_spec_payload() -> dict[str, object]:
    evidence = {**_old_document_evidence_payload(), "document_id": "DOC-001"}
    return {
        "paper_title": "Short-circuit report",
        "paper_type": "report",
        "domain": "motor_control",
        "documents": [
            {"document_id": "DOC-001", "filename": "paper-a.pdf"},
            {"document_id": "DOC-002", "filename": "paper-b.pdf"},
        ],
        "primary_document_id": None,
        "abstract": "A synchronous machine short-circuit report.",
        "equations": [],
        "parameter_table": [
            {
                "name": "Inertia constant",
                "symbol": "H",
                "value": "3.5",
                "unit": "s",
                "source": "document_extracted",
                "document_id": "DOC-001",
            },
            {
                "name": "Inertia constant",
                "symbol": "H",
                "value": "4.0",
                "unit": "s",
                "source": "document_extracted",
                "document_id": "DOC-002",
            },
        ],
        "figure_locations": [],
        "pseudocode_blocks": [],
        "evidence": [evidence],
        "parameter_conflicts": [
            {
                "parameter_name": "Inertia constant",
                "parameter_symbol": "H",
                "value_options": [
                    {
                        "value": "3.5",
                        "unit": "s",
                        "observations": [
                            {"document_id": "DOC-001", "locator": None, "excerpt": None}
                        ],
                    },
                    {
                        "value": "4.0",
                        "unit": "s",
                        "observations": [
                            {"document_id": "DOC-002", "locator": None, "excerpt": None}
                        ],
                    },
                ],
            }
        ],
    }


def _old_document_evidence_payload() -> dict[str, object]:
    return {
        "source": "document_extracted",
        "paper_section_id": "S1",
        "equation_id": None,
        "figure_id": None,
        "excerpt": "The report states the machine parameter.",
        "missing_param_prompt_id": None,
    }


def _legacy_user_supplied_plan_json() -> str:
    document_evidence = {**_old_document_evidence_payload(), "document_id": "DOC-001"}
    user_evidence = {
        "source": "user_supplied",
        "document_id": None,
        "paper_section_id": None,
        "equation_id": None,
        "figure_id": None,
        "excerpt": None,
        "missing_param_prompt_id": "MISS-1",
    }
    return _json(
        {
            "plan_id": "PLAN-paper-1",
            "paper_spec_id": "paper-1",
            "library_choice": "SimPowerSystems",
            "block_recommendations": [],
            "parameter_mapping": [
                {
                    "paper_param_name": "H",
                    "model_param_name": "Synchronous Machine.H",
                    "value": "3.5",
                    "unit": "s",
                    "source": "user_supplied",
                }
            ],
            "subsystem_breakdown": ["Place machine", "Apply fault", "Observe current"],
            "m_script_skeleton": None,
            "evidence": [document_evidence, user_evidence],
            "build_steps": None,
        }
    )


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _record(*, title: str = "Short-circuit report") -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
            paper_title=title,
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="A synchronous machine short-circuit report.",
            equations=[
                EquationEntry(
                    equation_id="EQ-01",
                    latex_or_text="H = 3.5",
                    paper_section_id="S1",
                    document_id="DOC-001",
                )
            ],
            parameter_table=[
                ParameterEntry(
                    name="Inertia constant",
                    symbol="H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                    document_id="DOC-001",
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


def _source(paper_id: str, *, text: str = "paper text") -> PaperReparseSource:
    return PaperReparseSource(
        paper_id=paper_id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        documents=[
            PaperReparseDocumentSource(
                document_id="DOC-001",
                upload_index=0,
                filename="paper.pdf",
                raw_text=text,
                page_count=1,
                figure_placeholders=[],
                table_placeholders=[],
                locator_index=PaperReparseLocatorIndex(
                    section_ids=["S1"],
                    equation_ids=["EQ-01"],
                    figure_ids=[],
                ),
                file_hash="hash",
                extracted_at=datetime(2026, 7, 2, 0, 0, 0),
            )
        ],
        primary_index=None,
    )


def _correction(paper_id: str) -> PaperParameterCorrection:
    return PaperParameterCorrection(
        correction_id="CORR-1",
        paper_id=paper_id,
        param_key="H::Synchronous Machine.H",
        plan_target=PlanCorrectionTarget(
            paper_param_name="H",
            model_param_name="Synchronous Machine.H",
            plan_mapping_index=0,
        ),
        original_value="3.5",
        original_unit="s",
        original_source=EvidenceSource.DOCUMENT_EXTRACTED,
        original_document_id="DOC-001",
        corrected_value="3.8",
        corrected_unit="s",
        created_at="2026-07-02T00:00:00",
        updated_at="2026-07-02T00:00:00",
    )


def _document_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
