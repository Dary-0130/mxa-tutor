from __future__ import annotations

from pathlib import Path

import pytest

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
from features.paper._prompt_builder import (
    _dedupe_evidence,
    _shared_paper_plan_constraints,
    build_messages_for_build_steps,
    build_messages_for_missing_detect,
    build_messages_for_mscript_draft,
    build_messages_for_plan_compose,
    build_messages_for_subsystem_plan,
    build_messages_for_tuning_suggest,
)
from features.paper._prompt_loader import load_prompt_template
from features.paper.paper_plan_helpers import build_plan_evidence_source_refs

PAPER_PLAN_PROMPTS = [
    "paper_plan_missing_detector.yaml",
    "paper_plan_composer.yaml",
    "paper_plan_build_steps.yaml",
    "paper_plan_subsystem.yaml",
    "paper_plan_mscript.yaml",
    "paper_tuning_suggest.yaml",
]


@pytest.fixture(autouse=True)
def _clear_prompt_cache() -> None:
    load_prompt_template.cache_clear()


def test_load_paper_plan_missing_detector_yaml() -> None:
    template = load_prompt_template("paper_plan_missing_detector.yaml")

    assert template.version == "v0.2"
    assert "MissingDetector" in template.system
    assert "{paper_spec_json}" in template.user
    assert "{sentinel_mappings_json}" in template.user


def test_load_paper_plan_composer_yaml() -> None:
    template = load_prompt_template("paper_plan_composer.yaml")

    assert template.version == "v0.3"
    assert "PlanComposer" in template.system
    assert "{plan_id}" in template.user


def test_load_paper_plan_subsystem_yaml() -> None:
    template = load_prompt_template("paper_plan_subsystem.yaml")

    assert template.version == "v0.1"
    assert "SubsystemPlanner" in template.system
    assert "{block_recommendations_json}" in template.user


def test_load_paper_plan_build_steps_yaml() -> None:
    template = load_prompt_template("paper_plan_build_steps.yaml")

    assert template.version == "v0.1"
    assert "BuildStepPlanner" in template.system
    assert "{block_recommendations_json}" in template.user
    assert "{parameter_mapping_json}" in template.user
    assert "禁止输出 display_text" in template.system


def test_load_paper_plan_mscript_yaml() -> None:
    template = load_prompt_template("paper_plan_mscript.yaml")

    assert template.version == "v0.1"
    assert "MScriptDrafter" in template.system
    assert "{equations_json}" in template.user


def test_load_paper_tuning_suggest_yaml() -> None:
    template = load_prompt_template("paper_tuning_suggest.yaml")

    assert template.version == "v0.1"
    assert "TuningSuggestion" in template.system
    assert "{allowed_plan_parameter_names_json}" in template.user
    assert "禁止输出 suggestion_id / user_scenario / disclaimer" in template.system


def test_shared_snippet_contains_evidence_double_source_contract() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "evidence 双源契约" in snippet
    assert "document_id 是后端注入的第 7 个契约字段" in snippet
    assert 'source = "document_extracted"' in snippet
    assert 'source = "user_supplied"' in snippet


def test_shared_snippet_contains_private_source_ref_bridge() -> None:
    snippet = _shared_paper_plan_constraints()

    assert "私有引用桥" in snippet
    assert "source_ref" in snippet
    assert "后端会按 source_ref 解析" in snippet


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


def test_5_role_systems_all_inject_shared_snippet() -> None:
    systems = [
        build_messages_for_missing_detect(_spec(), [_sentinel_mapping()])[0].content,
        build_messages_for_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")[0].content,
        build_messages_for_subsystem_plan([_block_recommendation()], [_document_evidence()])[
            0
        ].content,
        build_messages_for_build_steps(
            [_block_recommendation()],
            [_sentinel_mapping()],
            [_document_evidence()],
            build_plan_evidence_source_refs(_spec()),
        )[0].content,
        build_messages_for_mscript_draft(_spec().equations, _spec().parameter_table)[0].content,
    ]

    for system in systems:
        assert "evidence 双源契约" in system
        assert "私有引用桥" in system
        assert (
            "ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source"
            in system
        )
        assert "plan_id / paper_spec_id 不要自生成,由系统注入,逐字照抄" in system


def test_build_messages_for_tuning_suggest_uses_allowlists_not_fixed_fields() -> None:
    messages = build_messages_for_tuning_suggest(_record_with_resolved_prompt(), "需要提高阻尼")
    user = messages[1].content

    assert "需要提高阻尼" in user
    assert '"H"' in user
    assert '"D"' not in user
    assert '"MISS-1"' in user
    assert '"MISS-2"' not in user
    assert "suggestion_id" not in user
    assert "disclaimer" not in user


def test_evidence_dedupe_preserves_same_locator_from_different_documents() -> None:
    first = _document_evidence()
    second = _document_evidence(document_id="DOC-002")
    duplicate = _document_evidence()

    assert _dedupe_evidence([first, second, duplicate]) == [first, second]


def test_build_messages_for_plan_compose_substitutes_plan_id() -> None:
    messages = build_messages_for_plan_compose(_spec(), "PLAN-PAPER-001", "PAPER-001")

    assert "PLAN-PAPER-001" in messages[1].content
    assert "PAPER-001" in messages[1].content
    assert "逐字照抄" in messages[0].content


def test_missing_detector_system_specifies_prompt_fields() -> None:
    system = load_prompt_template("paper_plan_missing_detector.yaml").system

    assert "draft 字段硬约束" in system
    for field_name in (
        "parameter_name",
        "paper_reference",
        "suggested_unit",
        "source",
    ):
        assert field_name in system
    assert "禁止输出 prompt_id" in system
    assert "Python 按 sentinel 顺序注入" in system


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


def test_build_step_planner_system_specifies_structured_redline_contract() -> None:
    system = load_prompt_template("paper_plan_build_steps.yaml").system

    assert "build_steps 必须 3-10 步" in system
    assert "不得输出空数组 []" in system
    assert "逐字复用 block_recommendations" in system
    assert 'source="document_extracted"' in system
    assert '禁止输出 source="user_supplied"' in system
    assert "不得包含参数具体值" in system
    assert '禁止写"增大 10%"' in system


def test_build_messages_for_build_steps_includes_blocks_params_and_evidence() -> None:
    messages = build_messages_for_build_steps(
        [_block_recommendation()],
        [_sentinel_mapping()],
        [_document_evidence()],
        build_plan_evidence_source_refs(_spec()),
    )
    user = messages[1].content

    assert '"block_type": "Synchronous Machine"' in user
    assert '"paper_param_name": "H 惯性时间常数"' in user
    assert '"paper_section_id": "S1"' in user
    assert '"source_ref": "REF-001"' in user


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


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Synchronous Machine",
        purpose="Model the generator.",
        paper_reference=_document_evidence(),
    )


def _sentinel_mapping() -> ParameterMapping:
    return ParameterMapping(
        paper_param_name="H 惯性时间常数",
        model_param_name="Synchronous Machine.H",
        value="null",
        unit="s",
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )


def _record_with_resolved_prompt() -> PaperPlanRecord:
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[_block_recommendation()],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                    value="3.5",
                    unit="s",
                    source=EvidenceSource.USER_SUPPLIED,
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
            evidence=[_document_evidence(), _user_evidence("MISS-1")],
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
    document_id: str | None = "DOC-001",
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=document_id,
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
