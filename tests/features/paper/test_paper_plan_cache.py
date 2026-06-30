from dataclasses import FrozenInstanceError, fields

import pytest

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry
from features.paper.paper_plan_cache import InMemoryPaperPlanCache, PaperPlanRecord
from features.paper.paper_plan_helpers import MissingBindingModel


def test_paper_plan_record_fields_are_frozen() -> None:
    record = _record()

    assert [field.name for field in fields(PaperPlanRecord)] == [
        "paper_id",
        "spec",
        "plan",
        "missing_prompts",
        "missing_bindings",
    ]
    with pytest.raises(FrozenInstanceError):
        record.paper_id = "other"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_in_memory_paper_plan_cache_get_set_delete() -> None:
    cache = InMemoryPaperPlanCache()
    record = _record()

    assert await cache.get("paper-1") is None

    await cache.set("paper-1", record)
    assert await cache.get("paper-1") is record

    await cache.delete("paper-1")
    assert await cache.get("paper-1") is None


def _record() -> PaperPlanRecord:
    evidence = _evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
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
            MissingBindingModel(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


def _evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
