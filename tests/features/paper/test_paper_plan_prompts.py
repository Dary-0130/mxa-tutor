from __future__ import annotations

from pathlib import Path

import pytest

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import BlockRecommendation
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from core.interfaces.document_parser import FigurePlaceholder
from features.paper._prompt_builder import (
    _shared_paper_plan_constraints,
    build_messages_for_missing_detect,
    build_messages_for_mscript_draft,
    build_messages_for_plan_compose,
    build_messages_for_subsystem_plan,
)
from features.paper._prompt_loader import load_prompt_template

PAPER_PLAN_PROMPTS = [
    "paper_plan_missing_detector.yaml",
    "paper_plan_composer.yaml",
    "paper_plan_subsystem.yaml",
    "paper_plan_mscript.yaml",
]


@pytest.fixture(autouse=True)
def _clear_prompt_cache() -> None:
    load_prompt_template.cache_clear()


def test_load_paper_plan_missing_detector_yaml() -> None:
    template = load_prompt_template("paper_plan_missing_detector.yaml")

    assert template.version == "v0.1"
    assert "MissingDetector" in template.system
    assert "{paper_spec_json}" in template.user


def test_load_paper_plan_composer_yaml() -> None:
    template = load_prompt_template("paper_plan_composer.yaml")

    assert template.version == "v0.1"
    assert "PlanComposer" in template.system
    assert "{plan_id}" in template.user


def test_load_paper_plan_subsystem_yaml() -> None:
    template = load_prompt_template("paper_plan_subsystem.yaml")

    assert template.version == "v0.1"
    assert "SubsystemPlanner" in template.system
    assert "{block_recommendations_json}" in template.user


def test_load_paper_plan_mscript_yaml() -> None:
    template = load_prompt_template("paper_plan_mscript.yaml")

    assert template.version == "v0.1"
    assert "MScriptDrafter" in template.system
    assert "{equations_json}" in template.user


def test_shared_snippet_contains_evidence_double_source_contract() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "evidence 双源契约" in snippet
    assert 'source = "document_extracted"' in snippet
    assert 'source = "user_supplied"' in snippet


def test_shared_snippet_contains_locator_whitelist() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "locator 白名单" in snippet
    assert "PaperSpec.evidence[*].paper_section_id" in snippet
    assert "PaperSpec.equations[*].equation_id" in snippet
    assert "PaperSpec.figure_locations[*].figure_id" in snippet


def test_shared_snippet_contains_field_name_hard_constraints() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "字段名硬约束" in snippet
    assert (
        "ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source"
        in snippet
    )
    assert "BlockRecommendation 3 字段:block_type / purpose / paper_reference" in snippet


def test_shared_snippet_contains_forbidden_field_names() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "禁止字段名:locator / locators / paper_locator" in snippet
    assert "param_name / parameter_name / param_symbol / param_value / param_unit" in snippet


def test_shared_snippet_contains_sentinel_literal() -> None:
    snippet = _shared_paper_plan_constraints()

    assert 'value 字面填 "null"' in snippet
    assert "MISSING_VALUE_SENTINEL" in snippet


def test_shared_snippet_contains_plan_id_injection_rule() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "plan_id / paper_spec_id 不要自生成,由系统注入,逐字照抄" in snippet


def test_4_role_systems_all_inject_shared_snippet() -> None:
    systems = [
        build_messages_for_missing_detect(_spec(), [_figure_placeholder()])[0].content,
        build_messages_for_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")[0].content,
        build_messages_for_subsystem_plan([_block_recommendation()], [_document_evidence()])[
            0
        ].content,
        build_messages_for_mscript_draft(_spec().equations, _spec().parameter_table)[0].content,
    ]

    for system in systems:
        assert "evidence 双源契约" in system
        assert "locator 白名单" in system
        assert (
            "ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source"
            in system
        )
        assert "plan_id / paper_spec_id 不要自生成,由系统注入,逐字照抄" in system


def test_build_messages_for_plan_compose_substitutes_plan_id() -> None:
    messages = build_messages_for_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")

    assert "PLAN-PAPER-001" in messages[1].content
    assert "PAPER-001" in messages[1].content
    assert "逐字照抄" in messages[0].content


def test_missing_detector_system_specifies_prompt_fields() -> None:
    system = load_prompt_template("paper_plan_missing_detector.yaml").system

    assert "MissingParameterPrompt 7 字段硬约束" in system
    for field_name in (
        "prompt_id",
        "parameter_name",
        "paper_reference",
        "suggested_unit",
        "user_supplied_value",
        "user_supplied_unit",
        "source",
    ):
        assert field_name in system


def test_composer_system_specifies_subsystem_breakdown_empty_and_mscript_null() -> None:
    system = load_prompt_template("paper_plan_composer.yaml").system

    assert "subsystem_breakdown 留空数组 []" in system
    assert "m_script_skeleton 留 null" in system
    assert '"subsystem_breakdown": []' in system
    assert '"m_script_skeleton": null' in system


def test_subsystem_planner_system_specifies_3_to_10_steps() -> None:
    system = load_prompt_template("paper_plan_subsystem.yaml").system

    assert "3-10 步" in system
    assert "步骤少于 3 步或多于 10 步" in system


def test_mscript_drafter_system_allows_null_output() -> None:
    system = load_prompt_template("paper_plan_mscript.yaml").system

    assert '"m_script_skeleton": "..." | null' in system
    assert "返回 null(R1 P2-2 显式允许)" in system


def test_no_paper_plan_yaml_uses_self_generate_id_literal() -> None:
    for filename in PAPER_PLAN_PROMPTS:
        text = Path("core/prompts", filename).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "自生成" in line:
                assert any(marker in line for marker in ("不要自生成", "不得自生成", "禁止自生成"))


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
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
            )
        ],
        figure_locations=[
            FigureRef(figure_id="FIG-01", caption="Machine parameters", paper_section_id="S1")
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Synchronous Machine",
        purpose="Model the generator.",
        paper_reference=_document_evidence(),
    )


def _figure_placeholder() -> FigurePlaceholder:
    return FigurePlaceholder(
        figure_id="FIG-01",
        caption="Machine parameters",
        paper_section_id="S1",
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
