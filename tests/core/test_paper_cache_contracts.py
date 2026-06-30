from dataclasses import FrozenInstanceError, fields

import pytest

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperDocument, PaperSpec, ParameterEntry
from core.interfaces.paper_cache import PaperBundleStore, PaperPlanCache, PaperSpecCache


def test_missing_parameter_binding_is_core_frozen_dataclass() -> None:
    binding = MissingParameterBinding(
        prompt_id="MISS-1",
        paper_param_name="H",
        model_param_name="Machine.H",
    )

    assert [field.name for field in fields(MissingParameterBinding)] == [
        "prompt_id",
        "paper_param_name",
        "model_param_name",
    ]
    with pytest.raises(FrozenInstanceError):
        binding.prompt_id = "MISS-2"  # type: ignore[misc]


def test_paper_plan_record_fields_use_core_types() -> None:
    record = _record()

    assert [field.name for field in fields(PaperPlanRecord)] == [
        "paper_id",
        "spec",
        "plan",
        "missing_prompts",
        "missing_bindings",
    ]
    assert all(
        "features." not in getattr(field.type, "__module__", "")
        for field in fields(PaperPlanRecord)
    )
    with pytest.raises(FrozenInstanceError):
        record.paper_id = "other"  # type: ignore[misc]


def test_paper_cache_interfaces_have_expected_abstract_methods() -> None:
    assert PaperBundleStore.__abstractmethods__ == {
        "save_ready_bundle",
        "get_spec",
        "get_plan_record",
        "delete_bundle",
    }
    assert PaperSpecCache.__abstractmethods__ == {"get", "put", "invalidate"}
    assert PaperPlanCache.__abstractmethods__ == {"get", "set", "delete"}


def test_bundle_store_is_not_a_spec_or_plan_cache() -> None:
    assert not issubclass(PaperBundleStore, PaperSpecCache)
    assert not issubclass(PaperBundleStore, PaperPlanCache)


def _record() -> PaperPlanRecord:
    evidence = PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id="S1",
        equation_id=None,
        figure_id=None,
        excerpt="The report states H.",
        missing_param_prompt_id=None,
    )
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=PaperSpec(
            paper_title="Short-circuit report",
            paper_type="report",
            domain="motor_control",
            documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
            primary_document_id=None,
            abstract="A report.",
            equations=[
                EquationEntry(
                    equation_id="EQ-1",
                    latex_or_text="H = ?",
                    paper_section_id="S1",
                )
            ],
            parameter_table=[
                ParameterEntry(
                    name="Inertia",
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
                    purpose="Represent the generator.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Machine.H",
                    value="null",
                    unit="s",
                    source=EvidenceSource.DOCUMENT_EXTRACTED,
                )
            ],
            subsystem_breakdown=["A", "B", "C"],
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
                model_param_name="Machine.H",
            )
        ],
    )
