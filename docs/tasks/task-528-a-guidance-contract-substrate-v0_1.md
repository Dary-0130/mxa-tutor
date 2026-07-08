# TASK-528-A · 建模指导契约 substrate · v0.1

> 承 TASK-528 目标形状 RFC(v0.2,R1+R6 已收口)。**只加对外契约 + schema + 向后兼容 + fixtures;不接生成、不渲染、不做语义校验。端到端恒 `build_guidance = None`(同 507-A substrate 模式)。用户零可见变化。**
> 这是契约变更卡 → 严格走决策 13 schema-sync 全清单。生成在 528-B、语义校验在 528-C、前端在 528-D、05+eval 在 528-E。

## 0. Stage-0(实现前先做)
- `git fetch origin` 取 live HEAD(参考 `ff4de774`,以实际 fetch 为准),确认 507-A/B/508、526-B as-built 与 528 卡一致,不一致停手报架构师。
- 确认 `CURRENT_SCHEMA_VERSION`(现 v8)处理:本卡字段 **additive 进 `plan_json` 且给默认值** → 不新增表/列 → **不 bump v9**;若落地发现需新表/列,停手报架构师(不擅自 bump)。

## 1. 目标
在 `ModelGenerationPlan` 上新增可空 sibling 契约 `build_guidance: BuildGuidance | None`,**默认 None、端到端恒 None**。不改写 `build_steps`。让契约、schema、TS、fixtures、freeze 守门就位,为 528-B 生成打底。**本卡不产生任何 guidance 内容、不改任何运行行为。**

## 2. 契约形状(照 528 v0.2 §4;证据用 `PaperEvidenceEntry`,非 `SourceRef`)

新增 domain + Pydantic:
```
ModelGenerationPlan.build_guidance: BuildGuidance | None = None   # 端到端恒 None(本卡)

BuildGuidance: version:Literal["v1"] · assessment:GuidanceAssessment · details:list[GuidanceDetail] · gaps:list[GuidanceGap]

GuidanceAssessment:
  content_status:     Literal["reproducible_candidate","outline_with_gaps","outline_only"]
  environment_status: Literal["not_checked","compatible","missing_toolbox","incompatible"]
  overall_status:     Literal["reproducible_ready","reproducible_candidate_env_unchecked","outline_with_gaps","outline_only"]
  blocking_gap_ids:   list[str]

GuidanceDetail:
  detail_id:str · step_id:str
  detail_kind:   Literal["block_selection","subsystem_internal_structure","connection","parameter_value","configuration","verification","gap_notice"]
  basis:         Literal["document_extracted","engineering_convention","user_confirmation_required"]
  actionability: Literal["actionable","notice_only","blocked_pending_confirmation"]
  display_text:str
  evidence: list[PaperEvidenceEntry]        # 复用既有 paper 证据结构(保留多文档/公式/图表/参数 locator)
  convention_code: str | None
  confirmation_reason_code: str | None

GuidanceGap:
  gap_id:str
  gap_kind: Literal["missing_support_component","missing_parameter_value","toolbox_unverified","library_variant_unresolved","missing_connection_detail","missing_configuration_detail","insufficient_document_evidence"]
  scope: Literal["plan","step","subsystem"] · step_id:str|None
  basis: Literal["engineering_convention","user_confirmation_required"]
  severity: Literal["blocking","warning"]
  display_text:str
```
- 所有枚举为机器码;**本卡只定契约,不实现"哪些组合合法"的语义校验**(那在 528-C)。schema 层只做类型/枚举/必填的结构约束(如 `version` Literal、字段类型)。
- 证据字段**复用 `PaperEvidenceEntry`**;若需桥接,单独定义映射,**不得**与讲解体系 `SourceRef` 混写(R6 额外障碍)。

## 3. 实现约束
- **可空 sibling,不改写 `build_steps`**:`build_steps` 的生成/校验/`display_text` 派生/fail-closed 降级**一律不动**(507-A/B 不回退)。
- **端到端恒 None**:本卡不接生成器、不填 guidance;所有路径 `build_guidance=None`。现有 plan 行为、`build_steps` 输出、真机结果**逐字节不变**。
- **向后兼容**:既有已持久化 plan(无 `build_guidance`)加载正常(默认 None);round-trip 通过。
- **additive**:字段进 `plan_json`、给默认;不 bump schema version(见 Stage-0)。
- **脱敏(决策 11)**:契约/枚举全机器码;不引入任何塞源文/参数值/异常 message 的字段或路径。

## 4. 决策 13 schema-sync 全清单(完工报告必须逐项贴 diff,缺项 = 未完工)
```text
□ domain dataclass 新增(BuildGuidance/GuidanceAssessment/GuidanceDetail/GuidanceGap)
□ Pydantic schema 同步(ModelGenerationPlanSchema 新增 sibling + 子 schema)
□ scripts/export_paper_schemas.py 导出的 JSON schema(schemas/*.schema.json)
□ test_schema_freeze.py 期望值
□ test_*_schemas.py 边界/枚举测试数据
□ docs/06_OUTPUT_CONTRACTS.md 新增 BuildGuidance 契约描述
□ 前端 TS 类型同步(web 侧 plan 类型)
□ golden / sample fixtures(含 build_guidance=None 的默认态)
```
(本卡不含 `project_type` Literal 改动,故不触 `core/prompts/*.yaml`;05 的新类型在 528-E,不在本卡。)

## 5. 红线 / 明确不做
- 不接生成器、不填任何 guidance 内容(528-B)。
- 不做 basis/gap 语义合法性校验或红线机检(528-C)。
- 不改前端渲染(508 现状不动;评级/缺口渲染在 528-D)。
- 不改 05、不改 eval(528-E)。
- 不动 `build_steps` 生成/校验/降级、不动 526-B 重试路径、不改任何 prompt。
- 不 bump schema version(除非 Stage-0 发现必须,须先报)。

## 6. 验收
- freeze 测试、schema JSON、TS 类型全同步且绿。
- 向后兼容:旧 plan(无 build_guidance)加载 + round-trip 通过;新字段默认 None。
- **端到端 null 透传**:跑现有 paper plan 路径,`build_guidance` 恒 None,`build_steps` 与现有输出**无 diff**。
- 现有测试套件(test_paper_plan_service / test_paper_spec_service 等)全绿。
- 真机 E2E:本卡无新行为,**轻验**——确认 null 透传 + 现有上传/计划结果不回归即可(从 repo 目录起,`.env` 有 key、AppSettings 自动加载,临时库不污染本地 db,key 不回显)。
- **PR 走 PM 网页侧**:Codex push 分支 + 给 PR 标题/正文/`pull/new` 链接,PM 建 PR + squash;Codex 不自建 PR、不登录、不合并。
- **代码 PR 不碰 `03_TASK_INDEX.md`**(决策 07);索引单独 closeout PR;合并后提醒 PM 补索引(528-A 记"完成")。

## 7. 交接给架构师(完工报告需含)
- 决策 13 清单每项 diff。
- 确认端到端 `build_guidance` 恒 None、`build_steps` 输出无 diff 的证据。
- 是否触及 v9 的判断结论。
- 任何契约形状与 528 v0.2 §4 的偏差(如有,说明原因待架构师核)。
