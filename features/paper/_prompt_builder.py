"""Build paper-to-model prompt messages from parsed documents and PaperSpec data."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_parameter_conflicts import (
    conflict_prompt_summary,
    label_hits_parameter_conflict,
    parameter_entry_hits_conflict,
    without_conflicted_parameter_entries,
)
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, PaperSpec, ParameterConflict, ParameterEntry
from core.interfaces.document_parser import FigurePlaceholder, ParsedDocument
from core.interfaces.llm_provider import LLMMessage
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    BuildStepUserEvidenceSourceRef,
    PlanEvidenceSourceRef,
    UserEvidenceRef,
    build_plan_evidence_source_refs,
    build_step_user_evidence_source_refs,
    resolved_prompt_ids,
    resolved_user_evidence_refs,
)
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    EquationEntryModel,
    PaperEvidenceEntryModel,
    PaperSpecModel,
    ParameterConflictModel,
    ParameterEntryModel,
    ParameterMappingModel,
)

from ._prompt_loader import load_prompt_template

_BUILD_STEP_DEPENDENCY_TEMPLATE_LINES = (
    "- depends_on 不得自己依赖自己;只能引用别的步骤",
    "- 系统会自动排序步骤,depends_on 不必为书写顺序兜底",
    "- 没有前提就给空列表 [];尤其第一步通常就该是空依赖",
    "- 接线要连到别的步骤产生的模块,就必须把那个步骤写进依赖(depends_on)",
)
_BUILD_STEP_DEPENDENCY_CONSTRAINTS = """【depends_on 依赖/接线可见性机制】:
- depends_on 不得自己依赖自己;只能引用别的步骤
- 系统会自动排序步骤,depends_on 不必为书写顺序兜底
- 没有前提就给空列表 [];尤其第一步通常就该是空依赖
- 接线要连到别的步骤产生的模块,就必须把那个步骤写进依赖(depends_on)"""


class _GuidanceEvidenceCardLike(Protocol):
    @property
    def handle(self) -> str: ...

    @property
    def summary(self) -> str: ...


def build_messages(parsed: ParsedDocument) -> list[LLMMessage]:
    """Build system/user messages for PaperSpec extraction."""
    template = load_prompt_template()
    user = template.user.format(
        raw_text=parsed.raw_text,
        figure_placeholders=_format_figures(parsed.figure_placeholders),
        table_placeholders=_format_strings(parsed.table_placeholders),
        section_ids=_format_strings(parsed.locator_index.section_ids),
        equation_ids=_format_strings(parsed.locator_index.equation_ids),
        figure_ids=_format_strings(parsed.locator_index.figure_ids),
    )
    return [
        LLMMessage(role="system", content=template.system),
        LLMMessage(role="user", content=user),
    ]


def _shared_paper_plan_constraints() -> str:
    """Return the shared system snippet for the paper plan role prompts."""

    return """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【evidence 双源契约】(每个 PaperEvidenceEntry 必守):
- LLM 输出字段(9 个,逐字匹配):source / paper_section_id / equation_id / figure_id / excerpt / missing_param_prompt_id / user_action / parameter_correction_id / correction_param_key
- document_id 是后端注入的契约字段,LLM 不输出、不自创
- source = "document_extracted":必须填写私有 source_ref(来自 plan_evidence_sources_json);三 locator 填 null;excerpt 由后端按 source_ref 回填;missing_param_prompt_id = null;document_id 由后端按 source_ref 注入
- source = "user_supplied":三 locator 全 null;excerpt = null;user_action = "fill_missing";missing_param_prompt_id 必填(关联 MissingParameterPrompt.prompt_id);parameter_correction_id / correction_param_key = null;document_id 由系统注入 null

【私有引用桥】:
- document_extracted evidence 只能引用 plan_evidence_sources_json 里的 source_ref,形如 REF-001;严禁自创 source_ref
- 不输出 document_id;不直接输出 paper_section_id / equation_id / figure_id 的真实 ID;后端会按 source_ref 解析、stamp document_id、回填 canonical locator、并 strip source_ref
- user_supplied evidence 不填 source_ref

【字段名硬约束】(逐字匹配,禁止自创字段名,沿用 TASK-501 v0.3):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时 **优先填 null**(更稳);接受 "—"(em-dash)字面但不推荐
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- 禁止字段名嵌套对象:locator 必须把 paper_section_id / equation_id / figure_id 平铺,不嵌套

【字面示例】:
- ParameterMapping 物理单位项:
  {"paper_param_name":"PN","model_param_name":"Synchronous Machine.Pn (VA)","value":"200e6","unit":"VA","source":"document_extracted"}
- ParameterMapping 标幺值项:
  {"paper_param_name":"xd","model_param_name":"Synchronous Machine.Xd (pu)","value":"1.0","unit":"pu","source":"document_extracted"}
- ParameterMapping 工程推断无单位项(优先 null):
  {"paper_param_name":"求解器","model_param_name":"Simulation > Solver","value":"ode15s","unit":null,"source":"document_extracted"}
- ParameterMapping 用户补充项:
  {"paper_param_name":"(用户补充) H","model_param_name":"Synchronous Machine.H (s)","value":"3.5","unit":"s","source":"user_supplied"}
- PaperEvidenceEntry user_supplied:
  {"source":"user_supplied","paper_section_id":null,"equation_id":null,"figure_id":null,"excerpt":null,"missing_param_prompt_id":"MISS-001","user_action":"fill_missing","parameter_correction_id":null,"correction_param_key":null}

【双源契约红线】:
- 不得伪造 evidence(凭空生成 locator / excerpt)
- 不得把 user_supplied 标成 document_extracted(反例 2,06 § 12.8)
- 不得让 document_extracted 缺 locator + excerpt(反例 3)
- 不得把 PaperEvidenceEntry 当作其他模块的 evidence 包结构子集消费(反例 4)

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段(平衡节点 / 求解器名 / 仿真时长 / 故障时刻等)只在 SimPowerSystems 工程惯例下推断;
  若 PaperSpec 已含,直接复用,不重新编
- **缺参时:value 字面填 "null"(字符串,sentinel,R1 P1-4 由系统常量 MISSING_VALUE_SENTINEL 定义);**不编值**;**
  **不在 ParameterMapping 上加 missing_param_prompt_id 字段(R1 P0-1:ParameterMapping 5 字段公开 contract,binding 由 PlanAssembler 后置生成 MissingBindingModel,不进 plan)**
- **plan_id / paper_spec_id 不要自生成,由系统注入,逐字照抄(R1 P0-2)**"""


def build_messages_for_missing_detect(
    spec: PaperSpec,
    sentinel_mappings: list[ParameterMapping],
) -> list[LLMMessage]:
    """Build MissingDetector messages."""

    template = load_prompt_template("paper_plan_missing_detector.yaml")
    user = _render_user(
        template.user,
        {
            "paper_spec_json": _paper_spec_json(spec),
            "sentinel_mappings_json": _json_dumps(
                [
                    ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
                    for mapping in sentinel_mappings
                ]
            ),
            "plan_evidence_sources_json": _plan_evidence_sources_json(
                build_plan_evidence_source_refs(spec)
            ),
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_plan_compose(
    spec: PaperSpec,
    plan_id: str,
    paper_spec_id: str,
) -> list[LLMMessage]:
    """Build PlanComposer messages with system-injected IDs."""

    template = load_prompt_template("paper_plan_composer.yaml")
    user = _render_user(
        template.user,
        {
            "paper_spec_json": _paper_spec_json_for_generation(spec),
            "parameter_conflicts_json": _parameter_conflicts_prompt_json(spec.parameter_conflicts),
            "plan_evidence_sources_json": _plan_evidence_sources_json(
                build_plan_evidence_source_refs(spec)
            ),
            "plan_id": plan_id,
            "paper_spec_id": paper_spec_id,
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_subsystem_plan(
    block_recommendations: list[BlockRecommendation],
    evidence: list[PaperEvidenceEntry],
) -> list[LLMMessage]:
    """Build SubsystemPlanner messages."""

    template = load_prompt_template("paper_plan_subsystem.yaml")
    user = _render_user(
        template.user,
        {
            "block_recommendations_json": _json_dumps(
                [
                    BlockRecommendationModel.from_domain(block).model_dump(mode="json")
                    for block in block_recommendations
                ]
            ),
            "paper_evidence_json": _json_dumps(
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in evidence
                ]
            ),
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_build_steps(
    block_recommendations: list[BlockRecommendation],
    parameter_mapping: list[ParameterMapping],
    evidence: list[PaperEvidenceEntry],
    source_refs: list[PlanEvidenceSourceRef],
) -> list[LLMMessage]:
    """Build BuildStepPlanner messages."""

    return _build_messages_for_build_steps(
        block_recommendations,
        parameter_mapping,
        evidence,
        source_refs,
        shared_constraints=_build_steps_constraints(),
    )


def build_messages_for_build_steps_legacy_dependency_eval(
    block_recommendations: list[BlockRecommendation],
    parameter_mapping: list[ParameterMapping],
    evidence: list[PaperEvidenceEntry],
    source_refs: list[PlanEvidenceSourceRef],
) -> list[LLMMessage]:
    """Build the legacy BuildStepPlanner prompt for eval paired control arms only."""

    return _build_messages_for_build_steps(
        block_recommendations,
        parameter_mapping,
        evidence,
        source_refs,
        shared_constraints=_build_steps_constraints_legacy_dependency_eval(),
    )


def _build_messages_for_build_steps(
    block_recommendations: list[BlockRecommendation],
    parameter_mapping: list[ParameterMapping],
    evidence: list[PaperEvidenceEntry],
    source_refs: list[PlanEvidenceSourceRef],
    *,
    shared_constraints: str,
) -> list[LLMMessage]:
    template = load_prompt_template("paper_plan_build_steps.yaml")
    user = _render_user(
        template.user,
        {
            "block_recommendations_json": _json_dumps(
                [
                    BlockRecommendationModel.from_domain(block).model_dump(mode="json")
                    for block in block_recommendations
                ]
            ),
            "parameter_mapping_json": _json_dumps(
                [
                    ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
                    for mapping in parameter_mapping
                ]
            ),
            "paper_evidence_json": _json_dumps(
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in evidence
                ]
            ),
            "plan_evidence_sources_json": _plan_evidence_sources_json(source_refs),
        },
    )
    return _role_messages(
        _build_step_template_system(template.system),
        user,
        shared_constraints=shared_constraints,
    )


def build_messages_for_regenerate_build_steps(
    block_recommendations: list[BlockRecommendation],
    parameter_mapping: list[ParameterMapping],
    document_evidence: list[PaperEvidenceEntry],
    plan_evidence: list[PaperEvidenceEntry],
    source_refs: list[PlanEvidenceSourceRef],
    *,
    allowed_user_evidence_refs: set[UserEvidenceRef],
    allowed_user_prompt_ids: frozenset[str],
) -> list[LLMMessage]:
    """Build regeneration-only BuildStepPlanner messages."""

    template = load_prompt_template("paper_plan_build_steps_regenerate.yaml")
    user_source_refs = build_step_user_evidence_source_refs(
        plan_evidence,
        allowed_user_evidence_refs,
    )
    user = _render_user(
        template.user,
        {
            "block_recommendations_json": _json_dumps(
                [
                    BlockRecommendationModel.from_domain(block).model_dump(mode="json")
                    for block in block_recommendations
                ]
            ),
            "parameter_mapping_json": _json_dumps(
                [
                    ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
                    for mapping in parameter_mapping
                ]
            ),
            "paper_evidence_json": _json_dumps(
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in document_evidence
                ]
            ),
            "allowed_user_evidence_json": _json_dumps(
                [_user_evidence_source_ref_prompt_payload(entry) for entry in user_source_refs]
            ),
            "resolved_prompt_ids_json": _json_dumps(sorted(allowed_user_prompt_ids)),
            "plan_evidence_sources_json": _plan_evidence_sources_json(source_refs),
        },
    )
    return _role_messages(
        _build_step_template_system(template.system),
        user,
        shared_constraints=_regeneration_constraints(),
    )


def build_messages_for_mscript_draft(
    equations: list[EquationEntry],
    parameter_table: list[ParameterEntry],
    parameter_conflicts: list[ParameterConflict] | None = None,
) -> list[LLMMessage]:
    """Build MScriptDrafter messages."""

    template = load_prompt_template("paper_plan_mscript.yaml")
    conflicts = parameter_conflicts or []
    filtered_parameter_table = [
        entry for entry in parameter_table if not parameter_entry_hits_conflict(entry, conflicts)
    ]
    user = _render_user(
        template.user,
        {
            "equations_json": _json_dumps(
                [
                    EquationEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in equations
                ]
            ),
            "parameter_table_json": _json_dumps(
                [
                    ParameterEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in filtered_parameter_table
                ]
            ),
            "parameter_conflicts_json": _parameter_conflicts_prompt_json(conflicts),
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_mscript_draft_from_mapping(
    equations: list[EquationEntry],
    parameter_mapping: list[ParameterMapping],
    parameter_conflicts: list[ParameterConflict] | None = None,
) -> list[LLMMessage]:
    """Build regeneration-only MScriptDrafter messages from effective mappings."""

    template = load_prompt_template("paper_plan_mscript_from_mapping.yaml")
    conflicts = parameter_conflicts or []
    filtered_mapping = [
        mapping for mapping in parameter_mapping if not _mapping_hits_conflict(mapping, conflicts)
    ]
    user = _render_user(
        template.user,
        {
            "equations_json": _json_dumps(
                [
                    EquationEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in equations
                ]
            ),
            "parameter_mapping_json": _json_dumps(
                [
                    ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
                    for mapping in filtered_mapping
                ]
            ),
            "parameter_conflicts_json": _parameter_conflicts_prompt_json(conflicts),
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_tuning_suggest(
    record: PaperPlanRecord,
    user_scenario: str,
    corrections: list[PaperParameterCorrection] | None = None,
) -> list[LLMMessage]:
    """Build TuningSuggestion messages with server-side allowlists."""

    resolved_ids = resolved_prompt_ids(record)
    resolved_user_refs = resolved_user_evidence_refs(record, corrections or [])
    allowed_document_evidence = _dedupe_evidence(
        [
            entry
            for entry in [
                *record.spec.evidence,
                *record.plan.evidence,
                *(block.paper_reference for block in record.plan.block_recommendations),
                *(prompt.paper_reference for prompt in record.missing_prompts),
            ]
            if entry.source is EvidenceSource.DOCUMENT_EXTRACTED
        ]
    )
    allowed_resolved_user_evidence = [
        entry
        for entry in record.plan.evidence
        if entry.source is EvidenceSource.USER_SUPPLIED
        and _user_evidence_entry_is_resolved(entry, resolved_user_refs)
    ]

    template = load_prompt_template("paper_tuning_suggest.yaml")
    user = _render_user(
        template.user,
        {
            "user_scenario": user_scenario,
            "allowed_plan_parameter_names_json": _json_dumps(
                [
                    mapping.paper_param_name
                    for mapping in record.plan.parameter_mapping
                    if mapping.value != MISSING_VALUE_SENTINEL
                ]
            ),
            "allowed_document_evidence_json": _json_dumps(
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in allowed_document_evidence
                ]
            ),
            "allowed_resolved_user_evidence_json": _json_dumps(
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in allowed_resolved_user_evidence
                ]
            ),
            "resolved_prompt_ids_json": _json_dumps(
                [
                    prompt.prompt_id
                    for prompt in record.missing_prompts
                    if prompt.prompt_id in resolved_ids
                ]
            ),
        },
    )
    return _role_messages(template.system, user)


def build_messages_for_build_guidance(
    plan: ModelGenerationPlan,
    evidence_cards: Sequence[_GuidanceEvidenceCardLike],
) -> list[LLMMessage]:
    """Build BuildGuidanceGenerator messages with guidance-only evidence cards."""

    template = load_prompt_template("paper_build_guidance.yaml")
    user = _render_user(
        template.user,
        {
            "library_choice": plan.library_choice,
            "block_recommendations_json": _json_dumps(
                [
                    {
                        "block_type": block.block_type,
                        "purpose": block.purpose,
                    }
                    for block in plan.block_recommendations
                ]
            ),
            "parameter_mapping_json": _json_dumps(
                [
                    ParameterMappingModel.from_domain(mapping).model_dump(mode="json")
                    for mapping in plan.parameter_mapping
                ]
            ),
            "build_steps_skeleton_json": _build_guidance_steps_json(plan),
            "guidance_evidence_cards_json": _guidance_evidence_cards_json(evidence_cards),
        },
    )
    return _role_messages(template.system, user, shared_constraints=_build_guidance_constraints())


def _user_evidence_entry_is_resolved(
    entry: PaperEvidenceEntry,
    resolved_user_refs: set[UserEvidenceRef],
) -> bool:
    if (
        entry.user_action is UserEvidenceAction.FILL_MISSING
        and entry.missing_param_prompt_id is not None
    ):
        return (
            UserEvidenceRef(
                kind=UserEvidenceAction.FILL_MISSING,
                key=entry.missing_param_prompt_id,
            )
            in resolved_user_refs
        )
    if (
        entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED
        and entry.parameter_correction_id is not None
    ):
        return (
            UserEvidenceRef(
                kind=UserEvidenceAction.CORRECT_EXTRACTED,
                key=entry.parameter_correction_id,
            )
            in resolved_user_refs
        )
    return False


def _role_messages(
    system: str,
    user: str,
    *,
    shared_constraints: str | None = None,
) -> list[LLMMessage]:
    return [
        LLMMessage(
            role="system",
            content=f"{system.rstrip()}\n\n{shared_constraints or _shared_paper_plan_constraints()}",
        ),
        LLMMessage(role="user", content=user),
    ]


def _build_step_template_system(system: str) -> str:
    for line in _BUILD_STEP_DEPENDENCY_TEMPLATE_LINES:
        system = system.replace(f"{line}\n", "")
    return system


def _with_build_step_dependency_constraints(base: str) -> str:
    return base.replace(
        "\n\n【字段名硬约束】",
        f"\n\n{_BUILD_STEP_DEPENDENCY_CONSTRAINTS}\n\n【字段名硬约束】",
    )


def _regeneration_constraints() -> str:
    base = """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【重生成阶段私有 draft evidence 契约】:
- build_steps[*].block_refs[*].paper_reference / build_steps[*].configuration_hints[*].evidence[*] / build_steps[*].evidence[*] 只允许输出 {"source_ref":"REF-001"} 或 {"source_ref":"USER-001"} 这种对象
- document_extracted evidence 只能引用 plan_evidence_sources_json 中的 REF-* source_ref
- user_supplied evidence 只能引用 allowed_user_evidence_json 中的 USER-* source_ref
- source_ref 不得自创、不得留空、不得输出 null
- 不输出 source / document_id / paper_section_id / equation_id / figure_id / locator / excerpt / missing_param_prompt_id / user_action / parameter_correction_id / correction_param_key
- 后端会按 source_ref 唯一解析并盖章 source、document_id、canonical locator、excerpt 或 user_supplied provenance;解析失败整份 build_steps fail-closed

【字段名硬约束】(逐字匹配,禁止自创字段名):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时优先填 null
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- 禁止字段名嵌套对象:locator 必须把 paper_section_id / equation_id / figure_id 平铺,不嵌套
- connection_hints.to_block_ref 必须是既有 block_ref_id 字符串,不得输出数字、对象或自创引用

【重生成阶段参数来源】:
- parameter_mapping_json 是当前建模工作值,可能包含用户已补充或已纠错的 user_supplied 值
- user_supplied 工作值可以作为合法参数来源进入步骤引用,但不得写成论文原文证据
- 不得把 user_supplied evidence 标成 document_extracted;不得伪造论文 locator / excerpt

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段只在 SimPowerSystems 工程惯例下推断;若已有,直接复用,不重新编
- 缺参时只保留 value 字面 "null";不编值
- plan_id / paper_spec_id 不要自生成"""
    return _with_build_step_dependency_constraints(base)


def _build_steps_constraints() -> str:
    base = """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【build_steps 私有 draft evidence 契约】:
- build_steps[*].block_refs[*].paper_reference / build_steps[*].configuration_hints[*].evidence[*] / build_steps[*].evidence[*] 只允许输出 {"source_ref":"REF-001"} 这种对象
- source_ref 必须逐字来自 plan_evidence_sources_json;不得自创,不得留空,不得输出 null
- 不输出 source / document_id / paper_section_id / equation_id / figure_id / locator / excerpt / missing_param_prompt_id / user_action / parameter_correction_id / correction_param_key
- 后端会按 source_ref 唯一解析并盖章 source=document_extracted、document_id、canonical locator、excerpt;解析失败整份 build_steps fail-closed
- 初始生成阶段禁止 user_supplied evidence

【字段名硬约束】(逐字匹配,禁止自创字段名):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时优先填 null
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- connection_hints.to_block_ref 必须是既有 block_ref_id 字符串,不得输出数字、对象或自创引用

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段只在 SimPowerSystems 工程惯例下推断;若已有,直接复用,不重新编
- 缺参时只保留 value 字面 "null";不编值
- plan_id / paper_spec_id 不要自生成"""
    return _with_build_step_dependency_constraints(base)


def _build_steps_constraints_legacy_dependency_eval() -> str:
    return """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【build_steps 私有 draft evidence 契约】:
- build_steps[*].block_refs[*].paper_reference / build_steps[*].configuration_hints[*].evidence[*] / build_steps[*].evidence[*] 只允许输出 {"source_ref":"REF-001"} 这种对象
- source_ref 必须逐字来自 plan_evidence_sources_json;不得自创,不得留空,不得输出 null
- 不输出 source / document_id / paper_section_id / equation_id / figure_id / locator / excerpt / missing_param_prompt_id / user_action / parameter_correction_id / correction_param_key
- 后端会按 source_ref 唯一解析并盖章 source=document_extracted、document_id、canonical locator、excerpt;解析失败整份 build_steps fail-closed
- 初始生成阶段禁止 user_supplied evidence

【字段名硬约束】(逐字匹配,禁止自创字段名):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时优先填 null
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- connection_hints.to_block_ref 必须是既有 block_ref_id 字符串,不得输出数字、对象或自创引用

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段只在 SimPowerSystems 工程惯例下推断;若已有,直接复用,不重新编
- 缺参时只保留 value 字面 "null";不编值
- plan_id / paper_spec_id 不要自生成"""


def _build_guidance_constraints() -> str:
    return """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【guidance evidence handle 契约】:
- guidance_evidence_cards_json 只给私有 handle + 摘要;你只能引用 handle,不得输出 document_id / locator / 文件路径
- document_extracted detail 必须至少引用一个 supporting_evidence_refs handle
- 没有 handle 或不确定时,只能输出 user_confirmation_required 或白名单 engineering_convention
- 不得把 library_choice、build_steps_skeleton_json、display_text 或自己的总结当作论文真值

【防编造红线】:
- claim_text 一条只写一个原子主张
- 参数值、单位、block type、库路径、端口、连接端点、solver、采样时间、toolbox 变体,以及 anti-windup/限幅/离散连续/微分滤波/缩放/相序/角度来源/PWM/器件类型/控制器变体等工程决定,只有在 evidence handle 摘要明确支持时才可放入 document_extracted claim
- 不确定、依赖版本/工具箱/精确参数/采样时间/solver/初值/开关频率/仿真时长/接线细节时,输出 user_confirmation_required
- direction_hint 只说往哪查,不得包含数值+单位、精确库路径、端口、solver、采样时间或 toolbox 变体

【engineering_convention 白名单】:
- pi_controller_standard_structure / pid_controller_standard_structure:只允许误差求和 + P/I(/D) 环节;禁止 anti-windup/限幅/离散/微分滤波/变体
- clarke_transform_structure / park_transform_structure:只允许基础结构提示;缩放/相序/角度来源必须确认
- 白名单外不要输出 engineering_convention;电源/逆变器/主功率器件/物理 plant 不走 convention

【输出顶层 JSON】:
{
  "details": [
    {
      "step_id": "STEP-001",
      "detail_kind": "block_selection|subsystem_internal_structure|connection|parameter_value|configuration|verification|gap_notice",
      "basis": "document_extracted|engineering_convention|user_confirmation_required",
      "claim_text": "...",
      "supporting_evidence_refs": ["GEV-001"],
      "convention_code": "..." | null,
      "target": "STEP-001|B1|paper_param::model_param|plan|..." | null,
      "confirmation_reason_code": "missing_parameter_value|library_variant_unresolved|toolbox_unverified|solver_unverified|sample_time_unverified|connection_detail_missing|initial_condition_unverified|switching_frequency_unverified|simulation_time_unverified|configuration_unverified|document_evidence_unverified|engineering_decision_unverified" | null,
      "direction_hint": "..." | null
    }
  ],
  "gaps": []
}

【不要输出】:
- 不要输出 final display_text、detail_id、gap_id、severity、assessment;这些由后端确定性生成
- 不要输出裸 build_steps 文案来冒充指导"""


def _build_guidance_steps_json(plan: ModelGenerationPlan) -> str:
    steps = plan.build_steps or []
    payload = []
    for step in steps:
        payload.append(
            {
                "step_id": step.step_id,
                "title": step.title,
                "intent": step.intent,
                "block_refs": [
                    {
                        "block_ref_id": block.block_ref_id,
                        "block_type": block.block_type,
                        "library_path": block.library_path,
                        "purpose": block.purpose,
                    }
                    for block in step.block_refs
                ],
                "parameter_refs": [
                    {
                        "paper_param_name": ref.paper_param_name,
                        "model_param_name": ref.model_param_name,
                        "target": f"{ref.paper_param_name}::{ref.model_param_name}",
                    }
                    for ref in step.parameter_refs
                ],
                "connection_hints": [
                    {
                        "from_block_ref": hint.from_block_ref,
                        "from_port": hint.from_port,
                        "to_block_ref": hint.to_block_ref,
                        "to_port": hint.to_port,
                        "signal_meaning": hint.signal_meaning,
                    }
                    for hint in step.connection_hints
                ],
                "configuration_hints": [
                    {
                        "target": hint.target,
                        "setting_name": hint.setting_name,
                    }
                    for hint in step.configuration_hints
                ],
                "depends_on": step.depends_on,
            }
        )
    return _json_dumps(payload)


def _guidance_evidence_cards_json(evidence_cards: Sequence[_GuidanceEvidenceCardLike]) -> str:
    payload = []
    for card in evidence_cards:
        payload.append(
            {
                "handle": card.handle,
                "summary": card.summary,
            }
        )
    return _json_dumps(payload)


def _mapping_hits_conflict(
    mapping: ParameterMapping,
    conflicts: list[ParameterConflict],
) -> bool:
    return label_hits_parameter_conflict(
        mapping.paper_param_name,
        conflicts,
    ) or label_hits_parameter_conflict(mapping.model_param_name, conflicts)


def _render_user(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _paper_spec_json(spec: PaperSpec) -> str:
    return _json_dumps(PaperSpecModel.from_domain(spec).model_dump(mode="json"))


def _paper_spec_json_for_generation(spec: PaperSpec) -> str:
    payload = PaperSpecModel.from_domain(without_conflicted_parameter_entries(spec)).model_dump(
        mode="json"
    )
    payload["parameter_conflicts"] = []
    return _json_dumps(payload)


def _parameter_conflicts_prompt_json(conflicts: list[ParameterConflict]) -> str:
    return _json_dumps(conflict_prompt_summary(conflicts))


def _parameter_conflicts_json(conflicts: list[ParameterConflict]) -> str:
    return _json_dumps(
        [
            ParameterConflictModel.from_domain(conflict).model_dump(mode="json")
            for conflict in conflicts
        ]
    )


def _plan_evidence_sources_json(source_refs: list[PlanEvidenceSourceRef]) -> str:
    return _json_dumps(
        [
            {
                "source_ref": entry.source_ref,
                "basis": _plan_evidence_selection_basis(entry),
            }
            for entry in source_refs
        ]
    )


def _plan_evidence_selection_basis(entry: PlanEvidenceSourceRef) -> str:
    kind_label = {
        "paper_section_id": "paper section",
        "equation_id": "equation",
        "figure_id": "figure",
    }[entry.locator_kind]
    return f"{entry.filename} / {kind_label}: {entry.excerpt}"


def _user_evidence_source_ref_prompt_payload(
    entry: BuildStepUserEvidenceSourceRef,
) -> dict[str, str]:
    return {
        "source_ref": entry.source_ref,
        "basis": entry.selection_basis,
    }


def _dedupe_evidence(entries: list[PaperEvidenceEntry]) -> list[PaperEvidenceEntry]:
    seen: set[tuple[object, ...]] = set()
    result: list[PaperEvidenceEntry] = []
    for entry in entries:
        key = (
            entry.source,
            entry.document_id,
            entry.paper_section_id,
            entry.equation_id,
            entry.figure_id,
            entry.excerpt,
            entry.missing_param_prompt_id,
            entry.user_action,
            entry.parameter_correction_id,
            entry.correction_param_key,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _format_figures(figures: list[FigurePlaceholder]) -> str:
    if not figures:
        return "(none)"
    return "\n".join(
        "- id={}; caption={}; section={}".format(
            figure.figure_id,
            figure.caption or "(empty)",
            figure.paper_section_id or "(unknown)",
        )
        for figure in figures
    )


def _format_strings(values: list[str]) -> str:
    if not values:
        return "(none)"
    return "\n".join(f"- {value}" for value in values)
