from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from api.dependencies import get_paper_bundle_store, get_paper_tuning_service, get_settings
from api.main import create_app
from core.domain.exceptions import PaperTuningError
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
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_tuning_service import TUNING_DISCLAIMER


class FakeBundleStore(PaperBundleStore):
    def __init__(self, record: PaperPlanRecord | None) -> None:
        self.record = record

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None:
        self.record = record

    async def get_spec(self, paper_id: str) -> PaperSpec | None:
        _ = paper_id
        return self.record.spec if self.record is not None else None

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        _ = paper_id
        return self.record

    async def delete_bundle(self, paper_id: str) -> None:
        _ = paper_id
        self.record = None


class FakeTuningService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[PaperPlanRecord, str]] = []

    async def suggest(self, record: PaperPlanRecord, user_scenario: str) -> TuningSuggestion:
        self.calls.append((record, user_scenario))
        if self.error is not None:
            raise self.error
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


def test_post_tuning_suggest_returns_suggestion_and_preserves_scenario() -> None:
    service = FakeTuningService()
    app = _create_app(FakeBundleStore(_record()), service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "  Need stronger damping  "},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["paper_id"] == "paper-1"
    assert body["suggestion"]["user_scenario"] == "  Need stronger damping  "
    assert body["suggestion"]["disclaimer"] == TUNING_DISCLAIMER
    assert service.calls[0][0].paper_id == "paper-1"


def test_post_tuning_suggest_missing_paper_returns_404() -> None:
    app = _create_app(FakeBundleStore(None), FakeTuningService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/missing/tuning-suggest",
            json={"user_scenario": "Need damping"},
        )

    assert response.status_code == 404
    assert response.json()["error"] == "paper_not_found"


def test_post_tuning_suggest_blank_scenario_returns_422() -> None:
    app = _create_app(FakeBundleStore(_record()), FakeTuningService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "   "},
        )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_post_tuning_suggest_extra_field_returns_422() -> None:
    app = _create_app(FakeBundleStore(_record()), FakeTuningService())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "Need damping", "extra": "nope"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_post_tuning_suggest_paper_tuning_error_returns_502() -> None:
    app = _create_app(FakeBundleStore(_record()), FakeTuningService(PaperTuningError("bad")))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/tuning-suggest",
            json={"user_scenario": "Need damping"},
        )

    assert response.status_code == 502
    assert response.json()["error"] == "paper_tuning_failed"


def _create_app(store: FakeBundleStore, service: FakeTuningService) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_bundle_store] = lambda: store
    app.dependency_overrides[get_paper_tuning_service] = lambda: service
    return app


def _record() -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=_plan(),
        missing_prompts=[_missing_prompt()],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
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


def _plan() -> ModelGenerationPlan:
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
                value="3.5",
                unit="s",
                source=EvidenceSource.USER_SUPPLIED,
            )
        ],
        subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
        m_script_skeleton=None,
        evidence=[evidence, _user_evidence("MISS-1")],
    )


def _missing_prompt() -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id="MISS-1",
        parameter_name="H",
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
