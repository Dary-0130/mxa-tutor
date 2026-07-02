from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.dependencies import get_paper_ask_service, get_paper_bundle_store, get_settings
from api.main import create_app
from core.domain.paper_ask import (
    EquationTarget,
    PaperAskCitation,
    PaperAskFallbackReason,
    PaperAskRequest,
    PaperAskResponse,
    SectionTarget,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_parameter_correction import PaperParameterCorrection
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
from core.interfaces.paper_cache import PaperBundleStore
from features.paper.paper_ask_schemas import PaperAskResponseSchema


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

    async def insert_parameter_correction(self, correction: PaperParameterCorrection) -> None:
        _ = correction

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
        _ = paper_id, correction_id
        return None

    async def list_parameter_corrections(
        self,
        paper_id: str,
    ) -> list[PaperParameterCorrection]:
        _ = paper_id
        return []

    async def delete_parameter_correction(self, paper_id: str, correction_id: str) -> None:
        _ = paper_id, correction_id


class FakeAskService:
    def __init__(self, response: PaperAskResponse) -> None:
        self.response = response
        self.calls: list[tuple[PaperPlanRecord, PaperAskRequest]] = []

    async def ask(self, record: PaperPlanRecord, request: PaperAskRequest) -> PaperAskResponse:
        self.calls.append((record, request))
        return self.response


def test_post_paper_ask_returns_multi_citation_response_and_preserves_question() -> None:
    service = FakeAskService(_success_response())
    app = _create_app(FakeBundleStore(_record()), service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/ask",
            json={"question": "  How does the model map the paper?  ", "session_id": "s1"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["session_id"] == "s1"
    assert body["is_fallback"] is False
    assert [citation["source_id"] for citation in body["citations"]] == ["S1", "S2"]
    assert [
        (citation["document_id"], citation["document_label"]) for citation in body["citations"]
    ] == [
        ("DOC-001", "paper.pdf"),
        ("DOC-001", "paper.pdf"),
    ]
    assert service.calls[0][0].paper_id == "paper-1"
    assert service.calls[0][1].question == "  How does the model map the paper?  "


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {"question": "valid", "extra": "nope"},
    ],
)
def test_post_paper_ask_request_validation_returns_422(payload: dict[str, object]) -> None:
    app = _create_app(FakeBundleStore(_record()), FakeAskService(_success_response()))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/paper-1/ask", json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_post_paper_ask_missing_paper_returns_404() -> None:
    app = _create_app(FakeBundleStore(None), FakeAskService(_success_response()))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/missing/ask", json={"question": "What now?"})

    assert response.status_code == 404
    assert response.json()["error"] == "paper_not_found"


@pytest.mark.parametrize(
    "reason",
    [
        "insufficient_evidence",
        "invalid_or_missing_citations",
        "citation_target_unresolved",
        "out_of_scope",
    ],
)
def test_post_paper_ask_returns_fallback_response(reason: PaperAskFallbackReason) -> None:
    app = _create_app(FakeBundleStore(_record()), FakeAskService(_fallback_response(reason)))

    with TestClient(app) as client:
        response = client.post("/api/v1/papers/paper-1/ask", json={"question": "What now?"})

    body = response.json()
    assert response.status_code == 200
    assert body["is_fallback"] is True
    assert body["confidence"] == "low"
    assert body["citations"] == []
    assert body["fallback_reason"] == reason


def test_paper_ask_response_schema_rejects_extra_contract_field() -> None:
    payload = PaperAskResponseSchema.from_domain(_success_response()).model_dump(mode="json")
    payload["extra"] = "nope"

    with pytest.raises(ValidationError):
        PaperAskResponseSchema.model_validate(payload)


def _create_app(store: FakeBundleStore, service: FakeAskService) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_bundle_store] = lambda: store
    app.dependency_overrides[get_paper_ask_service] = lambda: service
    return app


def _success_response() -> PaperAskResponse:
    return PaperAskResponse(
        session_id="s1",
        message_id="m1",
        answer="The document summary and equation support this answer.",
        confidence="medium",
        citations=[
            PaperAskCitation(
                source_id="S1",
                label="Paper summary",
                excerpt="The report describes the model structure.",
                source_kind=EvidenceSource.DOCUMENT_EXTRACTED,
                target=SectionTarget(kind="section", result_section="paper-summary"),
                document_id="DOC-001",
                document_label="paper.pdf",
            ),
            PaperAskCitation(
                source_id="S2",
                label="Equation EQ-01",
                excerpt="The equation links the machine state and response.",
                source_kind=EvidenceSource.DOCUMENT_EXTRACTED,
                target=EquationTarget(kind="equation", equation_id="EQ-01"),
                document_id="DOC-001",
                document_label="paper.pdf",
            ),
        ],
        follow_up_suggestions=["Which section should I inspect next?"],
    )


def _fallback_response(reason: PaperAskFallbackReason) -> PaperAskResponse:
    return PaperAskResponse(
        session_id="s1",
        message_id="m-fallback",
        answer="Current parsed sources do not provide a citable answer.",
        confidence="low",
        citations=[],
        follow_up_suggestions=[],
        is_fallback=True,
        fallback_reason=reason,
    )


def _record() -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=_plan(),
        missing_prompts=[_missing_prompt()],
        missing_bindings=[
            MissingParameterBinding(
                prompt_id="MISS-1",
                paper_param_name="Damping",
                model_param_name="Machine damping",
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
                latex_or_text="State relation",
                paper_section_id="S1",
                document_id="DOC-001",
            )
        ],
        parameter_table=[
            ParameterEntry(
                name="Inertia",
                symbol="H",
                value="document value",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id="DOC-001",
            )
        ],
        figure_locations=[
            FigureRef(
                figure_id="FIG-01",
                caption="Machine parameters",
                paper_section_id="S1",
                document_id="DOC-001",
            )
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
                paper_param_name="Inertia",
                model_param_name="Machine inertia",
                value="user supplied",
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
        parameter_name="Damping",
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
        excerpt="The report states the machine modelling basis.",
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
        user_action=UserEvidenceAction.FILL_MISSING,
    )
