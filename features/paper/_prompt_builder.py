"""Build paper-to-model prompt messages from parsed documents and PaperSpec data."""

from __future__ import annotations

import json

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_parameter_conflicts import (
    conflict_prompt_summary,
    label_hits_parameter_conflict,
    parameter_entry_hits_conflict,
    without_conflicted_parameter_entries,
)
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import BlockRecommendation, PaperPlanRecord, ParameterMapping
from core.domain.paper_spec import EquationEntry, PaperSpec, ParameterConflict, ParameterEntry
from core.interfaces.document_parser import FigurePlaceholder, ParsedDocument
from core.interfaces.llm_provider import LLMMessage
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    PlanEvidenceSourceRef,
    UserEvidenceRef,
    build_plan_evidence_source_refs,
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
    return _role_messages(template.system, user)


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
    allowed_user_evidence = [
        entry
        for entry in plan_evidence
        if entry.source is EvidenceSource.USER_SUPPLIED
        and _user_evidence_entry_is_resolved(entry, allowed_user_evidence_refs)
    ]
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
                [
                    PaperEvidenceEntryModel.from_domain(entry).model_dump(mode="json")
                    for entry in allowed_user_evidence
                ]
            ),
            "resolved_prompt_ids_json": _json_dumps(sorted(allowed_user_prompt_ids)),
            "plan_evidence_sources_json": _plan_evidence_sources_json(source_refs),
        },
    )
    return _role_messages(template.system, user, shared_constraints=_regeneration_constraints())


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


def _regeneration_constraints() -> str:
    return """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【重生成阶段 evidence 双源契约】(每个 PaperEvidenceEntry 必守):
- document_id 是后端注入的契约字段,LLM 不输出、不自创
- source = "document_extracted":必须填写私有 source_ref(来自 plan_evidence_sources_json);三 locator 填 null;excerpt 由后端按 source_ref 回填;missing_param_prompt_id = null;document_id 由后端按 source_ref 注入
- source = "user_supplied":只能逐字复用 allowed_user_evidence_json 中的一条;三 locator 全 null;excerpt = null;document_id = null
- user_action = "fill_missing" 时,missing_param_prompt_id 必须在 resolved_prompt_ids_json 中;parameter_correction_id / correction_param_key = null
- user_action = "correct_extracted" 时,parameter_correction_id / correction_param_key 必须逐字来自 allowed_user_evidence_json;missing_param_prompt_id = null

【私有引用桥】:
- document_extracted evidence 只能引用 plan_evidence_sources_json 里的 source_ref,形如 REF-001;严禁自创 source_ref
- 不输出 document_id;不直接输出 paper_section_id / equation_id / figure_id 的真实 ID;后端会按 source_ref 解析、stamp document_id、回填 canonical locator、并 strip source_ref
- user_supplied evidence 不填 source_ref,不得伪造 allowed_user_evidence_json 之外的用户证据

【字段名硬约束】(逐字匹配,禁止自创字段名):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时优先填 null
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- 禁止字段名嵌套对象:locator 必须把 paper_section_id / equation_id / figure_id 平铺,不嵌套

【重生成阶段参数来源】:
- parameter_mapping_json 是当前建模工作值,可能包含用户已补充或已纠错的 user_supplied 值
- user_supplied 工作值可以作为合法参数来源进入步骤引用,但不得写成论文原文证据
- 不得把 user_supplied evidence 标成 document_extracted;不得伪造论文 locator / excerpt

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段只在 SimPowerSystems 工程惯例下推断;若已有,直接复用,不重新编
- 缺参时只保留 value 字面 "null";不编值
- plan_id / paper_spec_id 不要自生成"""


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
                "document_id": entry.document_id,
                "locator_kind": entry.locator_kind,
                "locator_id": entry.locator_id,
                "filename": entry.filename,
                "excerpt": entry.excerpt,
            }
            for entry in source_refs
        ]
    )


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
