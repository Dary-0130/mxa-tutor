from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from api.dependencies import get_paper_plan_cache, get_settings
from api.main import create_app
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterEntry,
)
from features.paper.paper_plan_cache import InMemoryPaperPlanCache, PaperPlanRecord
from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL, MissingBindingModel


def test_post_user_supply_happy_path_returns_200_with_updated_plan() -> None:
    cache = InMemoryPaperPlanCache()
    asyncio.run(cache.set("paper-1", _record()))
    app = _create_app(cache)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/user-supply",
            json=_payload(),
        )

    body = response.json()
    assert response.status_code == 200
    assert body["paper_id"] == "paper-1"
    assert body["updated_plan"]["parameter_mapping"][0]["value"] == "3.5"
    assert body["updated_plan"]["parameter_mapping"][0]["source"] == "user_supplied"
    assert body["updated_plan"]["evidence"][-1]["missing_param_prompt_id"] == "MISS-1"


def test_post_user_supply_paper_not_found_returns_400() -> None:
    app = _create_app(InMemoryPaperPlanCache())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/missing/user-supply",
            json=_payload(),
        )

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_post_user_supply_already_filled_returns_400() -> None:
    cache = InMemoryPaperPlanCache()
    asyncio.run(cache.set("paper-1", _record(mapping_value="4.0")))
    app = _create_app(cache)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/user-supply",
            json=_payload(),
        )

    assert response.status_code == 400
    assert response.json()["error"] == "paper_user_supply_invalid"


def test_response_field_name_is_updated_plan_not_plan() -> None:
    cache = InMemoryPaperPlanCache()
    asyncio.run(cache.set("paper-1", _record()))
    app = _create_app(cache)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/papers/paper-1/user-supply",
            json=_payload(),
        )

    body = response.json()
    assert "updated_plan" in body
    assert "plan" not in body


def _create_app(cache: InMemoryPaperPlanCache) -> Any:
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_paper_plan_cache] = lambda: cache
    return app


def _payload(
    *,
    prompt_id: str = "MISS-1",
    parameter_name: str = "H",
) -> dict[str, object]:
    return {
        "user_supplied_responses": [
            {
                "prompt_id": prompt_id,
                "parameter_name": parameter_name,
                "user_supplied_value": "3.5",
                "user_supplied_unit": "s",
                "user_supplied_note": "Read from figure.",
            }
        ]
    }


def _record(*, mapping_value: str = MISSING_VALUE_SENTINEL) -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
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
                    value=mapping_value,
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
                paper_reference=_document_evidence(figure_id="FIG-01"),
                suggested_unit="s",
                user_supplied_value=None,
                user_supplied_unit=None,
            )
        ],
        missing_bindings=[
            MissingBindingModel(
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
