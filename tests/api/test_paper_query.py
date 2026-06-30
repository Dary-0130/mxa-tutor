from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_paper_cache import SqlitePaperBundleStore, SqlitePaperPlanCacheView
from api.dependencies import (
    get_paper_bundle_store,
    get_paper_plan_cache,
    get_paper_tuning_service,
    get_settings,
)
from api.main import create_app
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterEntry,
)
from core.domain.paper_tuning import ParameterDirection, TuningSuggestion
from features.paper.paper_tuning_service import TUNING_DISCLAIMER


class RecordingTuningService:
    def __init__(self) -> None:
        self.records: list[PaperPlanRecord] = []

    async def suggest(self, record: PaperPlanRecord, user_scenario: str) -> TuningSuggestion:
        self.records.append(record)
        return TuningSuggestion(
            suggestion_id="TUNE-paper-1-test",
            user_scenario=user_scenario,
            parameter_directions=[
                ParameterDirection(
                    param_name="H",
                    direction="increase",
                    physical_meaning="Higher inertia slows current transients.",
                )
            ],
            expected_effect="Short-circuit current changes more slowly.",
            confidence="medium",
            evidence=[_document_evidence()],
            disclaimer=TUNING_DISCLAIMER,
        )


def test_get_paper_spec_returns_persisted_spec(tmp_path: Path) -> None:
    store = _initialized_store(tmp_path)
    record = _record()
    asyncio.run(store.save_ready_bundle(record))
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.get("/api/v1/papers/paper-1/spec")

    body = response.json()
    assert response.status_code == 200
    assert body["paper_id"] == "paper-1"
    assert body["spec"]["paper_title"] == "Short-circuit report"
    assert body["spec"]["evidence"][0]["paper_section_id"] == "S1"


def test_get_paper_spec_missing_returns_404(tmp_path: Path) -> None:
    store = _initialized_store(tmp_path)
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.get("/api/v1/papers/missing/spec")

    assert response.status_code == 404
    assert response.json()["error"] == "paper_not_found"


def test_get_paper_plan_returns_remaining_prompts_from_resolved_helper(
    tmp_path: Path,
) -> None:
    store = _initialized_store(tmp_path)
    record = _record(
        first_value="3.5",
        first_source=EvidenceSource.USER_SUPPLIED,
        plan_evidence=[_document_evidence(), _user_evidence("MISS-1")],
    )
    asyncio.run(store.save_ready_bundle(record))
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.get("/api/v1/papers/paper-1/plan")

    body = response.json()
    assert response.status_code == 200
    assert body["paper_id"] == "paper-1"
    assert [prompt["prompt_id"] for prompt in body["missing_prompts"]] == [
        "MISS-1",
        "MISS-2",
    ]
    assert [prompt["prompt_id"] for prompt in body["remaining_missing_prompts"]] == ["MISS-2"]


def test_get_paper_plan_spec_only_returns_404(tmp_path: Path) -> None:
    store = _initialized_store(tmp_path)
    asyncio.run(store.put_spec("paper-1", _spec()))
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.get("/api/v1/papers/paper-1/plan")

    assert response.status_code == 404
    assert response.json()["error"] == "paper_not_found"


def test_get_paper_plan_plan_only_surfaces_store_error(tmp_path: Path) -> None:
    db_path = tmp_path / "paper.db"
    store = _initialized_store_at(db_path)
    asyncio.run(_insert_plan_only(str(db_path)))
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.get("/api/v1/papers/paper-1/plan")

    assert response.status_code == 500
    assert response.json()["error"] == "store_error"


def test_sqlite_get_plan_record_reads_legacy_plan_without_build_steps(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "paper.db"
    store = _initialized_store_at(db_path)
    asyncio.run(_insert_legacy_ready_bundle(str(db_path)))

    record = asyncio.run(store.get_plan_record("paper-1"))

    assert record is not None
    assert record.plan.build_steps is None


def test_user_supply_updates_sqlite_view_then_get_and_tuning_read_updated_record(
    tmp_path: Path,
) -> None:
    store = _initialized_store(tmp_path)
    asyncio.run(store.save_ready_bundle(_record()))
    tuning_service = RecordingTuningService()
    app = _create_app(store)
    app.dependency_overrides[get_paper_plan_cache] = lambda: SqlitePaperPlanCacheView(store)
    app.dependency_overrides[get_paper_tuning_service] = lambda: tuning_service

    with TestClient(app) as client:
        supply_response = client.post(
            "/api/v1/papers/paper-1/user-supply",
            json={
                "user_supplied_responses": [
                    {
                        "prompt_id": "MISS-1",
                        "parameter_name": "H",
                        "user_supplied_value": "3.5",
                        "user_supplied_unit": "s",
                    }
                ]
            },
        )
        plan_response = client.get("/api/v1/papers/paper-1/plan")
        tuning_response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "Need stronger damping"},
        )

    assert supply_response.status_code == 200
    assert plan_response.status_code == 200
    assert tuning_response.status_code == 200
    assert [
        prompt["prompt_id"] for prompt in plan_response.json()["remaining_missing_prompts"]
    ] == ["MISS-2"]
    assert tuning_service.records
    mapping = tuning_service.records[0].plan.parameter_mapping[0]
    assert mapping.paper_param_name == "H"
    assert mapping.value == "3.5"
    assert mapping.source is EvidenceSource.USER_SUPPLIED


def _create_app(store: SqlitePaperBundleStore) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_bundle_store] = lambda: store
    return app


def _initialized_store(tmp_path: Path) -> SqlitePaperBundleStore:
    db_path = tmp_path / "paper.db"
    return _initialized_store_at(db_path)


def _initialized_store_at(db_path: Path) -> SqlitePaperBundleStore:
    asyncio.run(_init_db(str(db_path)))
    return SqlitePaperBundleStore(str(db_path))


async def _init_db(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await init_schema(conn)


async def _insert_plan_only(db_path: str) -> None:
    async with open_connection(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO paper_plan_cache(
                paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                created_at, updated_at
            ) VALUES ('paper-1', '{}', '[]', '[]', 'now', 'now')
            """
        )
        await conn.commit()


async def _insert_legacy_ready_bundle(db_path: str) -> None:
    record = _record()
    plan_payload = TypeAdapter(ModelGenerationPlan).dump_python(record.plan, mode="json")
    assert isinstance(plan_payload, dict)
    plan_payload.pop("build_steps")
    async with open_connection(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO paper_spec_cache(
                paper_id, paper_spec_json, created_at, updated_at
            ) VALUES (?, ?, 'now', 'now')
            """,
            (
                record.paper_id,
                TypeAdapter(PaperSpec).dump_json(record.spec).decode("utf-8"),
            ),
        )
        await conn.execute(
            """
            INSERT INTO paper_plan_cache(
                paper_id, plan_json, missing_prompts_json, missing_bindings_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'now', 'now')
            """,
            (
                record.paper_id,
                json.dumps(plan_payload),
                TypeAdapter(list[MissingParameterPrompt])
                .dump_json(record.missing_prompts)
                .decode("utf-8"),
                TypeAdapter(list[MissingParameterBinding])
                .dump_json(record.missing_bindings)
                .decode("utf-8"),
            ),
        )
        await conn.commit()


def _record(
    *,
    first_value: str = "null",
    first_source: EvidenceSource = EvidenceSource.DOCUMENT_EXTRACTED,
    plan_evidence: list[PaperEvidenceEntry] | None = None,
) -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=_plan(
            first_value=first_value,
            first_source=first_source,
            plan_evidence=plan_evidence,
        ),
        missing_prompts=[
            _missing_prompt("MISS-1", "H"),
            _missing_prompt("MISS-2", "D"),
        ],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            ),
            MissingParameterBinding(
                prompt_id="MISS-2",
                paper_param_name="D",
                model_param_name="Synchronous Machine.D",
            ),
        ],
    )


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
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
        figure_locations=[
            FigureRef(figure_id="FIG-01", caption="Machine parameters", paper_section_id="S1")
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _plan(
    *,
    first_value: str,
    first_source: EvidenceSource,
    plan_evidence: list[PaperEvidenceEntry] | None,
) -> ModelGenerationPlan:
    evidence = _document_evidence()
    return ModelGenerationPlan(
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
                value=first_value,
                unit="s",
                source=first_source,
            ),
            ParameterMapping(
                paper_param_name="D",
                model_param_name="Synchronous Machine.D",
                value="null",
                unit=None,
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            ),
        ],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=plan_evidence if plan_evidence is not None else [evidence],
    )


def _missing_prompt(prompt_id: str, parameter_name: str) -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id=prompt_id,
        parameter_name=parameter_name,
        paper_reference=_document_evidence(figure_id="FIG-01"),
        suggested_unit="s",
        user_supplied_value=None,
        user_supplied_unit=None,
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )


def _user_evidence(prompt_id: str) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id=prompt_id,
    )
