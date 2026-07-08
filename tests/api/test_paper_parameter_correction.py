from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from api.dependencies import (
    get_paper_bundle_store,
    get_paper_reparse_lock_registry,
    get_settings,
)
from api.main import create_app
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import PaperDocument, PaperSpec, ParameterEntry
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_reparse_service import PaperReparseLockRegistry


def test_post_parameter_correction_returns_wrapper_and_get_list() -> None:
    store = _FakeBundleStore(_record())
    app = _create_app(store)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/parameter-correction",
            json={
                "target": {
                    "paper_param_name": "H",
                    "model_param_name": "Synchronous Machine.H",
                    "plan_mapping_index": 0,
                    "expected_value": "3.5",
                    "expected_unit": "s",
                },
                "corrected_value": "4.0",
            },
        )
        list_response = client.get("/api/v1/papers/paper-1/parameter-corrections")

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"paper_id", "updated_plan", "correction"}
    assert body["updated_plan"]["parameter_mapping"][0]["value"] == "4.0"
    assert body["updated_plan"]["parameter_mapping"][0]["source"] == "user_supplied"
    assert body["updated_plan"]["build_steps"] is None
    assert body["updated_plan"]["build_guidance"] is None
    assert body["updated_plan"]["guidance_status"] == "stale_pending_regeneration"
    assert body["correction"]["original"]["value"] == "3.5"
    assert body["correction"]["original"]["document_label"] == "paper.pdf"
    assert list_response.status_code == 200
    assert list_response.json()["corrections"][0]["can_undo"] is True


def test_parameter_correction_extra_field_returns_422() -> None:
    app = _create_app(_FakeBundleStore(_record()))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/parameter-correction",
            json={
                "target": {
                    "paper_param_name": "H",
                    "model_param_name": "Synchronous Machine.H",
                    "plan_mapping_index": 0,
                    "expected_value": "3.5",
                    "expected_unit": "s",
                    "source": "document_extracted",
                },
                "corrected_value": "4.0",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_parameter_correction_lock_conflict_returns_409() -> None:
    registry = PaperReparseLockRegistry()
    token = asyncio.run(registry.acquire("paper-1"))
    app = _create_app(_FakeBundleStore(_record()))
    app.dependency_overrides[get_paper_reparse_lock_registry] = lambda: registry

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/papers/paper-1/parameter-correction",
                json={
                    "target": {
                        "paper_param_name": "H",
                        "model_param_name": "Synchronous Machine.H",
                        "plan_mapping_index": 0,
                        "expected_value": "3.5",
                        "expected_unit": "s",
                    },
                    "corrected_value": "4.0",
                },
            )
    finally:
        asyncio.run(token.__aexit__(None, None, None))

    assert response.status_code == 409
    assert response.json()["error"] == "correction_lock_conflict"


def test_undo_parameter_correction_returns_updated_plan() -> None:
    store = _FakeBundleStore(_record())
    app = _create_app(store)

    with TestClient(app) as client:
        applied = client.post(
            "/api/v1/papers/paper-1/parameter-correction",
            json={
                "target": {
                    "paper_param_name": "H",
                    "model_param_name": "Synchronous Machine.H",
                    "plan_mapping_index": 0,
                    "expected_value": "3.5",
                    "expected_unit": "s",
                },
                "corrected_value": "4.0",
            },
        ).json()
        response = client.post(
            "/api/v1/papers/paper-1/parameter-correction/"
            f"{applied['correction']['correction_id']}/undo"
        )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"paper_id", "updated_plan"}
    assert body["updated_plan"]["parameter_mapping"][0]["value"] == "3.5"
    assert body["updated_plan"]["parameter_mapping"][0]["source"] == "document_extracted"
    assert store.corrections == []


def _create_app(store: _FakeBundleStore) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_bundle_store] = lambda: store
    return app


class _FakeBundleStore(PaperBundleStore):
    def __init__(self, record: PaperPlanRecord | None) -> None:
        self.record = record
        self.corrections: list[PaperParameterCorrection] = []

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        self.record = record

    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        _ = paper_id
        return self.record.spec if self.record is not None else None

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        _ = paper_id
        return self.record

    async def put_spec(self, paper_id: str, spec: PaperSpec) -> None:
        _ = paper_id, spec

    async def set_plan(self, paper_id: str, record: PaperPlanRecord) -> None:
        _ = paper_id
        self.record = record

    async def delete_bundle(self, paper_id: str) -> None:
        _ = paper_id
        self.record = None
        self.corrections = []

    async def apply_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction: PaperParameterCorrection,
        *,
        is_recorrect: bool,
    ) -> None:
        _ = paper_id
        self.record = updated_record
        if is_recorrect:
            self.corrections = [
                correction if item.correction_id == correction.correction_id else item
                for item in self.corrections
            ]
        else:
            self.corrections.append(correction)

    async def undo_parameter_correction_atomically(
        self,
        paper_id: str,
        updated_record: PaperPlanRecord,
        correction_id: str,
    ) -> None:
        _ = paper_id
        self.record = updated_record
        self.corrections = [
            correction
            for correction in self.corrections
            if correction.correction_id != correction_id
        ]

    async def insert_parameter_correction(self, correction: PaperParameterCorrection) -> None:
        self.corrections.append(correction)

    async def update_parameter_correction_value(
        self,
        paper_id: str,
        correction_id: str,
        corrected_value: str,
        corrected_unit: str | None,
        updated_at: str,
    ) -> None:
        _ = paper_id, correction_id, corrected_value, corrected_unit, updated_at

    async def get_parameter_correction(
        self,
        paper_id: str,
        correction_id: str,
    ) -> PaperParameterCorrection | None:
        return next(
            (
                correction
                for correction in self.corrections
                if correction.paper_id == paper_id and correction.correction_id == correction_id
            ),
            None,
        )

    async def list_parameter_corrections(
        self,
        paper_id: str,
    ) -> list[PaperParameterCorrection]:
        return [correction for correction in self.corrections if correction.paper_id == paper_id]

    async def delete_parameter_correction(self, paper_id: str, correction_id: str) -> None:
        self.corrections = [
            correction
            for correction in self.corrections
            if not (correction.paper_id == paper_id and correction.correction_id == correction_id)
        ]


def _record() -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="A synchronous machine short-circuit report.",
            equations=[],
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
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton="old script",
            evidence=[evidence],
        ),
        missing_prompts=[],
        missing_bindings=[],
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
