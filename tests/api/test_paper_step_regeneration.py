from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_paper_step_regeneration_service, get_settings
from api.main import create_app
from core.domain.exceptions import PaperNotFoundError, PaperReparseInProgressError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry
from features.paper.paper_step_regeneration_service import PaperStepRegenerationError


@pytest.mark.parametrize("json_body", [None, {}])
def test_regenerate_steps_accepts_empty_body_and_returns_updated_plan(
    json_body: dict[str, object] | None,
) -> None:
    service = _FakeRegenerationService(plan=_record().plan)
    app = _create_app(service)

    with TestClient(app) as client:
        if json_body is None:
            response = client.post("/api/v1/papers/paper-1/regenerate-steps")
        else:
            response = client.post(
                "/api/v1/papers/paper-1/regenerate-steps",
                json=json_body,
            )

    body = response.json()
    assert response.status_code == 200
    assert service.paper_ids == ["paper-1"]
    assert body["paper_id"] == "paper-1"
    assert body["updated_plan"]["plan_id"] == "PLAN-paper-1"
    assert "plan" not in body


def test_regenerate_steps_rejects_extra_body_fields() -> None:
    app = _create_app(_FakeRegenerationService(plan=_record().plan))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/regenerate-steps",
            json={"parameter_mapping": []},
        )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PaperReparseInProgressError("reparse_in_progress"), 409, "regenerate_lock_conflict"),
        (
            PaperStepRegenerationError("regenerate_nothing_to_do", 400),
            400,
            "regenerate_nothing_to_do",
        ),
        (
            PaperStepRegenerationError("regenerate_store_failed", 500),
            500,
            "regenerate_store_failed",
        ),
        (PaperNotFoundError("paper_not_found"), 404, "paper_not_found"),
    ],
)
def test_regenerate_steps_error_codes(error: Exception, status: int, code: str) -> None:
    app = _create_app(_FakeRegenerationService(error=error))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/paper-1/regenerate-steps", json={})

    assert response.status_code == status
    assert response.json()["error"] == code


def _create_app(service: _FakeRegenerationService) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_step_regeneration_service] = lambda: service
    return app


class _FakeRegenerationService:
    def __init__(
        self,
        *,
        plan: ModelGenerationPlan | None = None,
        error: Exception | None = None,
    ) -> None:
        self.plan = plan
        self.error = error
        self.paper_ids: list[str] = []

    async def regenerate_steps(self, paper_id: str) -> ModelGenerationPlan:
        self.paper_ids.append(paper_id)
        if self.error is not None:
            raise self.error
        assert self.plan is not None
        return self.plan


def _record() -> PaperPlanRecord:
    evidence = PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
    spec = PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A synchronous machine short-circuit report.",
        equations=[EquationEntry("EQ-01", "H = 3.5", "S1", "DOC-001")],
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
    )
    plan = ModelGenerationPlan(
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
        m_script_skeleton=None,
        evidence=[evidence],
    )
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=spec,
        plan=plan,
        missing_prompts=[],
        missing_bindings=[],
    )
