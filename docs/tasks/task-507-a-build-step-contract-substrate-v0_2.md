# TASK-507-A:结构化建模步骤 · 契约 substrate(只加契约 / schema / 向后兼容,不接生成)

**版本**:v0.2(已并入 R1 + R6 双审意见;可派 Codex 实现门,Stage 0 兜底)
**所属线**:paper-to-model(decision 22 5xx)
**前置**:TASK-506 v0.3 定稿(目标形状已定 + PM 拍板)
**现状基线**:R6 实测 origin/main HEAD `0c5818d`(paper 后端自此未变,「近核 0c5818d」仍成立);**派单后 Codex Stage 0 复核最新 HEAD**

---

## 本版改动(v0.1 → v0.2,并审而来)
- **[P0]** `build_steps=[]` 在**契约层**非法(Pydantic `min_length=1` / JSON schema `minItems:1`);domain + DTO 默认 `None`,**禁 `default_factory=list`**。
- **[P1]** 新增 Pydantic 子模型统一 `extra="forbid"`(防塞非契约字段绕红线 / 造第三真值源)。
- **[P1]** 加**非空 `build_steps` 的 synthetic domain↔DTO roundtrip 测试**(否则 5 个新结构的转换没被测到;样例文字**不得含参数值 / 倍率**)。
- **[P1]** 「行为不变」精确化为「**业务生成行为不变;API JSON additive 多出 `build_steps:null`,非字节级不变**」。
- **[P1]** 补**旧 SQLite / PaperBundleStore 读取路径**测试(旧 plan_json 缺字段 → `build_steps is None`),不只测 wrapper。
- **[P1]** 验收硬清单显式加 `python -m scripts.export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` + `cd web && pnpm typecheck`(**R6 实测:`make check` 不覆盖 paper schema export,也不覆盖前端**)。
- **[P1]** `scripts/export_paper_schemas.py` 纳入 Stage 0 核查 + 完工报告(需改则列 diff,不需改则说明)。
- **[P1]** 至少一处 API / wrapper serialization 测试断言 `plan.build_steps is null`。
- **[P1]** 2 个 eval case README(写死「含 9 个字段」)纳入允许 diff(加 build_steps 后变 10 字段)。
- **[P1]** `docs/06 §12.5` 写明:507-A 阶段 `build_steps` 恒 null,507-B 才开始非空生成。
- **[P2]** TS 类型用**非 optional + nullable**:`build_steps: ModelBuildStep[] | null`,同步所有 mock / golden。
- **[P2]** Stage 0 加 grep / diff 约束:除 DTO 转换最小必需外,不改 SubsystemPlanner prompt / PlanAssembler / evaluator / 前端渲染。
- 术语统一:**5 个新增 dataclass**(`ModelBuildStep` + 4 子结构 `StepBlockRef` / `ParameterMappingRef` / `ConnectionHint` / `ConfigurationHint`)+ `ModelGenerationPlan` 追加 `build_steps` 字段。
- R6 实测确认:`paperTypes.ts` 手维护(无 codegen);现有序列化无 `exclude_none`;SQLite 走 `TypeAdapter(ModelGenerationPlan)`;约 14 个测试构造 `ModelGenerationPlan(...)`,双默认 None 可避免大面积改。

---

## 状态
🔍 实施中(双审 ✅ 条件通过;补 P0/P1 后可派)

## 上下文

TASK-506 v0.3 把结构化建模步骤的目标形状定死了。TASK-507 按 R6 建议拆两张:
- **本卡 507-A = 契约 substrate**:只把数据结构 / Pydantic schema / JSON schema / 向后兼容 / fixtures 落地,**不接生成、不做校验、不渲染**。落地后 `build_steps` **端到端恒 `None`**(契约在,无人填充),业务生成行为不变。
- **507-B(下一张)** = 生成(SubsystemPlanner 改出结构化步骤)+ PlanAssembler 11 条校验 + 降级 fallback + `display_text` 派生 + 红线机检。

惯用 substrate / wiring 两段法(参 517-A/B、518-A/B):先冻结契约面、CI 绿、向后兼容,再上行为。

## 输入(前置依赖)
- TASK-506 v0.3(绑定规格:字段集 / 可空性 / 复合键 / 命名 / 红线 / 兼容)。
- R6 实测的 schema-sync 契约侧同步面(见「范围」§9)。
- 锁:**additive 不删旧字段**;改契约走 decision 13 全清单 + PM 拍 + R1 审;feature boundary(decision 21)paper 独立,**不 import** overview / explanation 私有结构。
- 必读:`01` / `02` / `04` / `06` §12.5 / decision 13 / 21 / 22。

## 范围(必须做)
1. **domain**(`core/domain/paper_plan.py`):新增 5 个 dataclass(见「接口契约」);`ModelGenerationPlan` 追加 `build_steps: list[ModelBuildStep] | None`,**domain 默认 `None`**(**禁 `default_factory=list`**)。
2. **Pydantic DTO / wrapper**(`features/paper/paper_schemas.py`):镜像 5 个结构,新增子模型统一 **`extra="forbid"`**;`build_steps` **默认 `None` + `min_length=1`**(`None` 合法、`[]` 非法、非空合法);补 domain ↔ DTO 转换(`from_domain` / `to_domain`)。
3. **JSON schema**:`python -m scripts.export_paper_schemas` 重生成 `schemas/paper_plan.schema.json`,含 5 个结构 + `build_steps`(数组带 `minItems:1`);**`git diff --exit-code` 确认已 commit、无漏**。
4. **freeze / roundtrip 测试**(`tests/features/paper/test_paper_schemas_freeze.py` / `test_paper_schemas_sample_roundtrip.py`):
   - 同步期望值 + 样例,`build_steps=None` 序列化为 `"build_steps": null`(additive、可预测;现无 `exclude_none`,按现行无策略对齐);
   - **加 synthetic 非空 `build_steps` roundtrip 测试**:`ModelBuildStep(step_id="STEP-001", …)` → DTO `from_domain` → `to_domain` → 字段等价(**文字字段不得含模型参数值 / 倍率**;非 eval golden,仅契约转换测试);
   - **加 `build_steps=[]` 被 Pydantic / JSON schema 拒绝**的边界测试;
   - **加旧 JSON 缺 `build_steps` → `None`** 的反序列化测试。
5. **golden / fixtures**:`eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/golden/expected_model_generation_plan.json`、`eval/cases/paper_to_model/missing_param/case_01_missing_image_param/golden/expected_updated_plan.json` 加 `"build_steps": null`。
6. **eval case README 同步**:上述两 case 的 `case_README.md` 把「含 9 个字段」改 10 字段。
7. **旧存储读取路径测试**:旧 `plan_json` 无 `build_steps` 经 `SqlitePaperBundleStore.get_plan_record(...)`(或 `TypeAdapter(ModelGenerationPlan)` adapter 层)→ `record.plan.build_steps is None`,不报错。
8. **API / wrapper serialization 测试**:至少一处断言返回 `plan.build_steps is null`(`UploadDocumentResponse` / `GET /plan` 含 `ModelGenerationPlanModel`;若无稳定 API sample 则用 wrapper serialization 测试替代,**完工报告说明 API 响应是否被覆盖**)。
9. **TS 类型镜像**(`web/src/lib/paperTypes.ts`,手维护):加 5 个结构 + `build_steps: ModelBuildStep[] | null`(**非 optional + nullable**)**类型声明**;**只声明、不渲染、不碰视觉**(渲染是 TASK-508,且 508 先取证现有皮);同步该文件相关 mock。
10. **文档**(`docs/06_OUTPUT_CONTRACTS.md` §12.5):同步 5 个结构 + `build_steps` 描述;**写明 507-A 阶段 `build_steps` 恒 null,507-B 才开始非空生成**。
11. **decision 13 全清单**:完工报告逐项贴上述 diff;缺一项 = 未完工。
12. **索引(decision 07)**:Codex 把 507-A 当前行 + 进度条同步(🔍);✅ 收尾走合并后单独 docs PR。

## 不做(明确排除)
- ❌ 不实现 `build_steps` **生成**(SubsystemPlanner 仍出 `list[str]`;`build_steps` 恒 `None`)——507-B。
- ❌ 不实现 11 条 evaluator 校验、不实现降级、不实现红线机检——507-B。
- ❌ 不碰 `features/paper/paper_plan_service.py` / `paper_plan_helpers.py`(PlanAssembler 语义校验) / `_prompt_builder.py` / `core/prompts/paper_plan_subsystem.yaml` 的**生成逻辑**(仅允许 DTO 转换 / type import / response model 的最小必需改动,且不引入生成)——507-B。
- ❌ 不做前端渲染、不画视觉(TASK-508)。
- ❌ 不碰追问 / 多文件 / `PaperSpec` / `PaperEvidenceEntry`。
- ❌ 不动旧 `subsystem_breakdown`(保留不变)。
- ❌ 不加 `step_kind`(506 记可留 TASK-508 定,避免提前固化枚举)。
- ❌ 不给 `ParameterMapping` / `BlockRecommendation` 加正式 ID;不把 paper schema export 接进 Makefile / CI(R6 实测该缺口存在,但接入是单独 hygiene chore、不在本卡;本卡用手动跑 + `git diff --exit-code` 兜底)。

## 接口契约(照 TASK-506 v0.3 逐字落地;只新增、不改旧字段语义)

**现状**(R6 实测 origin/main 0c5818d):`ModelGenerationPlan` 8 字段,`subsystem_breakdown: list[str]`,`ParameterMapping` 无 ID。

**本卡新增(additive)**:
```python
@dataclass(frozen=True)
class StepBlockRef:
    block_ref_id: str                       # step 内唯一,如 "B1";connection_hints 据此引用
    block_type: str
    library_path: str | None                # 库路径 hint;未知为 None
    purpose: str
    paper_reference: PaperEvidenceEntry | None   # 可空:库选型/工程常识可无论文证据(防伪造)

@dataclass(frozen=True)
class ParameterMappingRef:
    paper_param_name: str                   # 复合键引用 parameter_mapping(本轮不加 mapping_id)
    model_param_name: str

@dataclass(frozen=True)
class ConnectionHint:
    from_block_ref: str                     # 指向本 step 或依赖 step 的 block_ref_id
    from_port: str | None                   # 人类搭建提示,非可执行 Simulink 端口契约
    to_block_ref: str
    to_port: str | None
    signal_meaning: str | None

@dataclass(frozen=True)
class ConfigurationHint:                    # 承载「配置求解器/powergui/仿真时长」类步骤
    target: str                             # e.g. "solver" / "powergui" / "simulation"
    setting_name: str | None
    instruction: str                        # 受红线约束(不写模型参数值)
    evidence: list[PaperEvidenceEntry]

@dataclass(frozen=True)
class ModelBuildStep:
    step_id: str                            # 稳定格式,如 "STEP-001"
    title: str
    intent: str
    block_refs: list[StepBlockRef]
    parameter_refs: list[ParameterMappingRef]
    connection_hints: list[ConnectionHint]
    configuration_hints: list[ConfigurationHint]
    depends_on: list[str]                   # 只引用前序 step_id
    evidence: list[PaperEvidenceEntry]
    display_text: str                       # 507-B 由 assembler 派生;507-A 仅声明字段

# ModelGenerationPlan 追加(旧字段全部保留不动):
#   build_steps: list[ModelBuildStep] | None   # domain+DTO 双默认 None;DTO min_length=1([] 非法);507-A 恒 None
```
**Pydantic 层约束**:5 个新子模型 `extra="forbid"`;`build_steps` 默认 `None` + `min_length=1`(`None` 合法、`[]` 拒绝、非空合法)。

## 验收标准
- [ ] 5 个 dataclass + `build_steps` 落地 domain;`ModelGenerationPlan(...)` 旧构造点不传该字段仍可构造(`build_steps=None`)。
- [ ] domain + Pydantic DTO + JSON schema + TS **四处契约镜像一致**(字段名 / 类型 / 可空性对齐 506 v0.3)。
- [ ] **`build_steps=[]` 被 Pydantic / JSON schema 拒绝**;`None`→`None`;`[valid step]`→roundtrip 通过。
- [ ] 新子模型 `extra="forbid"` 生效(塞非契约字段被拒)。
- [ ] **synthetic 非空 `build_steps` domain↔DTO roundtrip 等价**(样例文字无参数值 / 倍率)。
- [ ] 旧数据 / 旧 SQLite `plan_json` 缺 `build_steps` → 读为 `None`,不报错(走真实 / adapter 读取路径,非仅 wrapper)。
- [ ] grep 确认 **无 `default_factory=list`**、Pydantic 无默认 `[]`。
- [ ] freeze + roundtrip + golden 全绿(已同步 `"build_steps": null`);2 个 case README 字段数 9→10。
- [ ] 至少一处 serialization 测试断言 `plan.build_steps is null`(完工报告说明是否覆盖 API 响应)。
- [ ] **`make check` 全管道绿**,**外加**:`python -m scripts.export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` + `cd web && pnpm typecheck`(碰 TS 故也跑 `pnpm lint`)。
- [ ] `build_steps` **端到端恒 None**(无生成逻辑接入);现有 paper 上传 → spec → plan **业务行为不变**(回归;API JSON additive 多 `build_steps:null` 属预期)。
- [ ] decision 13 同步面 diff 全部贴在完工报告;`scripts/export_paper_schemas.py` 需改则列 diff、不需改则说明。
- [ ] 完工三件套(decision 08)。

## 风险与注意点
- **`[]` 中间态(最大风险)**:本卡只能产生 `build_steps=None`,**不得产生 `[]` 或半截 list**;契约层 `min_length=1` + 禁 `default_factory=list` 钉死(506:None=失败/降级、[]=非法)。
- **序列化全等测试**:`build_steps:null` 必同步进 golden / sample,否则 roundtrip 断(R6 P1)。
- **CI 盲区**:`make check` 不覆盖 paper schema export / 前端(R6 实测)——验收靠显式 export + `git diff --exit-code` + `pnpm typecheck` 兜底。
- **synthetic 样例别带数值**:测试 / docs / schema examples 的 build_steps 文字不得出现「Kp 增大 20%」「H 设为 3.5s」「推荐设为 N」(506 红线)。
- **别越界到 507-B**:只加字段,不接生成 / 不做校验 / 不做降级 / 不做红线机检;若发现「光加字段就得改生成」,说明边界划错——**停手报架构师**(诊断先行 decision 15)。
- **TS 只声明**:不渲染、不碰视觉(504-③)。
- **feature boundary**:paper 独立,不 import overview / explanation 私有(decision 21)。
- **行尾 / 异步 / 日志**:照 decision 20 / 11。

## Stage 0(派单后实现门第一步)
Codex 先 `git fetch` + 取最新 origin/main HEAD(**别用 0c5818d 旧值**),并核:
1. `core/domain/paper_plan.py` 现状与 506 一致(8 字段、`subsystem_breakdown: list[str]`、`ParameterMapping` 无 ID);
2. schema-sync 真实契约侧同步面(范围 §9 列表)对齐仓库;`scripts/export_paper_schemas.py` **是否需改**(若显式枚举导出 model,则加 `ModelBuildStepModel` 等需改)；
3. 现有序列化确无 `exclude_none`、SQLite 确走 `TypeAdapter(ModelGenerationPlan)`;
4. grep / diff 约束:除 DTO 转换最小必需外,**不改** SubsystemPlanner prompt / PlanAssembler / evaluator / 前端渲染;
5. `git status` 干净。
任一不符 → 停手报架构师(decision 15)。

## 估时 / 给 Codex 的提示
- 纯契约 substrate,工作量在「字段镜像四处一致 + golden / README 同步 + 旧读取路径兼容 + 不碰生成」。
- 前端无测试框架:TS 类型声明靠 `tsc` typecheck + lint。
- 约 14 个 `ModelGenerationPlan(...)` 构造点,双默认 None 可不逐个补参;只需新增/调整兼容 + synthetic + 边界测试。
- 派单前预放 `docs/tasks/task-507-a-*.md`,列进 Stage 0 baseline 白名单 + 允许 diff 清单(含 2 个 case README)。
