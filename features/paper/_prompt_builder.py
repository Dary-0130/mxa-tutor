"""Build paper-to-model prompt messages from parsed documents and PaperSpec data."""

from __future__ import annotations

import json

from core.domain.paper_evidence import PaperEvidenceEntry
from core.domain.paper_plan import BlockRecommendation, ParameterMapping
from core.domain.paper_spec import EquationEntry, PaperSpec, ParameterEntry
from core.interfaces.document_parser import FigurePlaceholder, ParsedDocument
from core.interfaces.llm_provider import LLMMessage
from features.paper.paper_schemas import (
    BlockRecommendationModel,
    EquationEntryModel,
    PaperEvidenceEntryModel,
    PaperSpecModel,
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
    """Return the shared system snippet for the four paper plan role prompts."""

    return """你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【evidence 双源契约】(每个 PaperEvidenceEntry 必守):
- 字段(6 个,逐字匹配):source / paper_section_id / equation_id / figure_id / excerpt / missing_param_prompt_id
- source = "document_extracted":三 locator 至少一个非 null;excerpt 1-300 字非空;missing_param_prompt_id = null
- source = "user_supplied":三 locator 全 null;excerpt = null;missing_param_prompt_id 必填(关联 MissingParameterPrompt.prompt_id)

【locator 白名单】(只能从 PaperSpec 给出的 ID 集中选,严禁自创):
- paper_section_id 只能来自 PaperSpec.evidence[*].paper_section_id
- equation_id 只能来自 PaperSpec.equations[*].equation_id
- figure_id 只能来自 PaperSpec.figure_locations[*].figure_id

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
  {"source":"user_supplied","paper_section_id":null,"equation_id":null,"figure_id":null,"excerpt":null,"missing_param_prompt_id":"MISS-001"}

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
            "paper_spec_json": _paper_spec_json(spec),
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


def build_messages_for_mscript_draft(
    equations: list[EquationEntry],
    parameter_table: list[ParameterEntry],
) -> list[LLMMessage]:
    """Build MScriptDrafter messages."""

    template = load_prompt_template("paper_plan_mscript.yaml")
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
                    for entry in parameter_table
                ]
            ),
        },
    )
    return _role_messages(template.system, user)


def _role_messages(system: str, user: str) -> list[LLMMessage]:
    return [
        LLMMessage(
            role="system",
            content=f"{system.rstrip()}\n\n{_shared_paper_plan_constraints()}",
        ),
        LLMMessage(role="user", content=user),
    ]


def _render_user(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _paper_spec_json(spec: PaperSpec) -> str:
    return _json_dumps(PaperSpecModel.from_domain(spec).model_dump(mode="json"))


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
