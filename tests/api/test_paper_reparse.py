from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_paper_reparse_service, get_settings
from api.main import create_app
from core.domain.exceptions import (
    PaperNotFoundError,
    PaperReparseFailedError,
    PaperReparseInProgressError,
    PaperReparseSourceUnavailableError,
    PaperReparseStoreError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PaperNotFoundError("paper_not_found"), 404, "paper_not_found"),
        (
            PaperReparseSourceUnavailableError("reparse_source_unavailable"),
            410,
            "reparse_source_unavailable",
        ),
        (PaperReparseInProgressError("reparse_in_progress"), 409, "reparse_in_progress"),
        (PaperReparseFailedError("paper_reparse_failed"), 502, "paper_reparse_failed"),
        (
            PaperReparseStoreError("paper_reparse_store_failed"),
            500,
            "paper_reparse_store_failed",
        ),
    ],
)
def test_reparse_error_codes(error: Exception, status: int, code: str) -> None:
    app = _create_app(_FakeReparseService(error=error))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/paper-1/reparse")

    assert response.status_code == status
    assert response.json()["error"] == code


def test_reparse_success_returns_spec_plan_and_remaining_prompts() -> None:
    app = _create_app(_FakeReparseService(record=_record()))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/paper-1/reparse")

    body = response.json()
    assert response.status_code == 200
    assert body["paper_id"] == "paper-1"
    assert body["spec"]["paper_title"] == "Short-circuit report"
    assert body["plan"]["plan_id"] == "PLAN-paper-1"
    assert body["missing_prompts"] == []
    assert body["remaining_missing_prompts"] == []


def _create_app(service: _FakeReparseService) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_reparse_service] = lambda: service
    return app


class _FakeReparseService:
    def __init__(
        self,
        *,
        record: PaperPlanRecord | None = None,
        error: Exception | None = None,
    ) -> None:
        self.record = record
        self.error = error

    async def reparse(self, paper_id: str) -> PaperPlanRecord:
        if self.error is not None:
            raise self.error
        assert self.record is not None
        assert paper_id == self.record.paper_id
        return self.record


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
