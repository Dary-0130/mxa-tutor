# TASK-508 v0.2:结构化建模步骤 · 前端渲染（把后端已生成的 build_steps 渲成「照着一步步搭」的清单）

**版本**：v0.2（R1 + R6 双审「方向通过、修完可派、不必升 R2、不必拆卡」→ 并意见定稿候选；PM「已定/不同意再说」口径后派单 Codex 实现门，Stage 0 兜底）
**所属线**：paper-to-model（decision 22 5xx；指导深度子线 506 RFC ✅ → 507-A 契约 ✅ → 507-B 生成 ✅ →【508 前端 ← 本卡】→ 509 真实语料评测）
**前置**：507-B 已合 main（`build_steps` 后端真生成、fail-closed 降级整体置 None）；504 paper 阅读工作台已合 main
**现状基线**：本会话 Codex 取证 + R6 复审 origin/main HEAD `6312053`（前端现状如「现状」节，逐字实测 + 截图 + R6 跑过 typecheck/lint/build/schema 零 diff/冒烟属实）；**派单后 Codex Stage 0 复核最新 HEAD**

---

## 本版改动（v0.1 → v0.2，双审并入）

**P0（必改，R1 挑出；R6 同点 `source` 映射为 P2）**
- **[P0-1]** `PaperEvidenceEntry.source`（`document_extracted | user_supplied`）≠ `SourceBadgeKind`（`document_extracted | user_supplied_resolved | missing_unresolved`），**禁止把 `evidence.source` 原样透传给 `SourceBadge`**。新增显式映射 helper（见 §2）；BuildSteps 内**不得用 `missing_unresolved`**；无 evidence / 未知 source = 不打 badge；只 `document_extracted` 且 `formatEvidence` 非空才显出处，`user_supplied`（理论上初始生成不会出现）只显「用户补充」badge、**不伪造** 章节/式/图出处。
- **[P0-2]** 红线口径从「前端不新增任何数字」（与步号/`step_id`/`block_ref_id`/`library_path`/端口/出处编号自相矛盾、不可机检）**改精确为**「禁止前端新增**参数值/单位/调参倍率/推荐设值**」。允许显示：步骤序号、`step_id`、`block_ref_id`、`depends_on` 派生步号、后端已给字符串（`title`/`intent`/`purpose`/`signal_meaning`/`instruction`/`library_path`/端口/`block_type`）、`formatEvidence` 的章节/式/图编号、参数名内自带下标。验收 grep 改为「BuildSteps 不读/不渲 `plan.parameter_mapping[*].value/unit` + 不硬编码『推荐设为 N / 增大 N% / N 倍 / 最优』类文案」。

**P1（应改，R1）**
- **[P1-1]** 静默降级扩到 **DOM/ARIA/title/badge/样式** 层：不得出现 `fallback`/`legacy`/`degraded`/`overview` 等可见文本、`aria-label`、`title`、badge、状态条或差异化样式类；内部 helper/分支命名可叫 fallback，但**不得渲到 DOM**。`build_steps` 判断写死 `const structuredSteps = Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;`。
- **[P1-2]** 结构化态验收**不得向生产页面加 mock 分支 / dev flag / query 参数 / 硬编码样例**；冒烟用独立脚本/fixture（仿 task504-smoke）或 grep/检视 + 507-B 真实输出截图/PM 实测，不为 508 新建测试框架。
- **[P1-3]** 单步加**分组 + 空组跳过 + 防糊墙**规则（见 §2）：每字段组仅非空才渲、不渲空标题；组顺序固定；短 label，正文仍 `.paper-copy`/`.paper-secondary`、mono 只给 token；长 `library_path`/`block_ref_id`/端口 `overflow-wrap:anywhere` 换行、**不横向滚**；badge + 出处放 meta 行。**不做折叠**（出范围）。
- **[P1-4]** 接线/依赖**纯显示增强**（见 §2）：建当前 plan 内 `block_ref_id → block_type/purpose` 与 `step_id → 序号` 的 best-effort map；接线显示 `B1（Synchronous Machine）→ B2（三相测量）`、依赖显示「依赖步骤 N」；无法唯一解析则回显原始 `B1`/`step_id` 或跳过，**不报错、不打 badge、不 console**。
- **[P1-5]** `parameter_refs` 锚跳边界钉死（见 §3）：默认**只显名 + 「见参数对照表」**（R6 实测 `ParameterTable` 行**现无可锚 id**）；锚跳为可选增强,仅在能给 `ParameterTable` 加**向后兼容** `id`/`scroll-margin`、不改其列/排序/取值/badge 行为时才做；锚 id 由 `paper_param_name + model_param_name` 稳定编码,**不把 value/unit 放进 href/title/aria-label/tooltip**;点击只滚到行,不 inline 展开参数值。
- **[P1-6]** `formatEvidence` 空结果规则：只有 `source === "document_extracted"` 且 `formatEvidence` 返回非空才显出处文本（与 P0-1 一起修）。

**P2（R1 + R6）**
- **[P2-1]** overview/detail 共存说明足够,**不改 SubsystemMap**。**本卡不加任何「非降级说明短句」**——任何只在结构化成功时出现的文案,其有无本身即泄漏「降级/没降级」,与 PM 拍的静默冲突,故不加。
- **[P2-2]** 固定文案补**字段组名**：涉及块 / 关联参数 / 接线提示 / 配置提示 / 步骤证据（见 § 固定文案）。
- **[P2-3]** 无障碍补最小语义（见 § 验收）：step title 用合理 heading 或 `aria-labelledby`；字段组用 section/list 语义；badge 与出处读屏相邻；无 evidence 不渲空 badge 容器。
- **[R6]** `formatEvidence` 现为 `BuildSteps`/`ParameterTable` 内部同形 helper（非共享导出）；BuildSteps 内**复用/就地整理**即可,**不为它扩大重构**。

---

## 本卡做什么（一句话）

后端 507-B 已把结构化 `build_steps` 真生成（`ModelGenerationPlan.build_steps: ModelBuildStep[] | null`，TS 类型 507-A 已在 `paperTypes.ts`）。现有「建模步骤」节（`BuildSteps.tsx`）只平铺渲 `library_choice + block_recommendations`、未读 `build_steps`。本卡把它升级成「照着一步步搭」的结构化步骤清单。**纯前端、只消费现有后端数据；不改后端 / 契约 / schema / paperTypes 类型 / 任何 Python；不重构其它 section；不做追问；复用锁死的砼核皮与现成组件。**

## PM 已拍的产品决定（baked in，2026-06-28）
1. **降级 UX = 静默**：`plan.build_steps == null` 时前端不给任何降级提示/信号，「建模步骤」节静默回退到当前行为（`推荐库 + block_recommendations` 平铺卡）。
2. **不做追问**：508 不实现、布局也不为它预留位置。
3. **视觉皮锁死**：砼核风（`#2c2c2c` / 信号橙 `#e85d3a` / IBM Plex + 思源黑 / `border-radius:0` / 半透玻璃 / `PanoramaScene`）；复用现成组件；不新造颜色/字体/token。

---

## 现状（Codex 实测 + R6 复审 origin/main `6312053`，本卡设计依据；R1 当真）

1. **类型已就位（507-A）**：`web/src/lib/paperTypes.ts`：`ModelGenerationPlan.build_steps: ModelBuildStep[] | null`；五个 step 类型在；`StepBlockRef.library_path: string|null`、`paper_reference: PaperEvidenceEntry|null`；`ParameterMappingRef` 只有 `paper_param_name/model_param_name`。**无 `step_kind`**（`git grep` NO_MATCH）→ 本卡不按 kind 分组。508 不改类型。
2. **建模步骤节**：`web/src/routes/paper/BuildSteps.tsx` 只渲 `plan.library_choice` + `plan.block_recommendations.map(...)`（块 = `block_type` mono + `purpose` + `formatEvidence(paper_reference)`），用 `<ol class="paper-step-list">` + `GlassCard.paper-readable-card.paper-step-card` + `.paper-step-index`。未读 `plan.build_steps`。
3. **结果页**：`web/src/routes/PaperResultPage.tsx` 顺序 = summary → subsystems（`SubsystemMap items={plan.subsystem_breakdown}`）→ `paper-build-steps`（`<BuildSteps plan={data.plan}/>`）→ parameters（`ParameterTable`）→ tuning（`TuningPanel`）。`SectionNav` 五锚点：论文摘要/子系统划分/建模步骤/参数对照/调参建议。
4. **复用件**：`SourceBadge({ kind })` + `SourceBadgeKind` 三态；`getParamSourceKind(row)` 在 `ParameterTable`；`formatEvidence(entry)` 为 `BuildSteps`/`ParameterTable` 内部同形 helper；`GlassCard({ children, className })`、`PanoramaScene({ panoramaX })`。
5. **样式入口**：`web/src/styles/index.css`（`styles/` 下，非 `web/src/index.css`）：token + 全局 `border-radius:0 !important` + `@import "./paper.css"`；`paper.css` 有 `.paper-copy`/`.paper-secondary`/`.paper-token`/`.paper-readable-card`/`.paper-step-list`/`.paper-step-card`/`.paper-step-index`/`.paper-source-badge`。
6. **参数表无锚**：`ParameterTable` 行为 `<div className="paper-param-row" role="row" key={row.key}>`，**无可锚 DOM id** → 锚跳默认不做（见 §3）。
7. **构建/守门**：`web/package.json` scripts `dev/build/lint/typecheck/preview/smoke:task402/504/505`，无测试框架；`task504-smoke.mjs` 为 `readFileSync` + 正则源码守卫，508 可仿写。R6 实跑 `export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` + `pnpm typecheck/lint/build` + `pnpm smoke:task504` 全绿、无 tracked diff。

---

## 数据形状（507-A/B 已落地，R6 实测属实）
- `ModelGenerationPlan.build_steps: ModelBuildStep[] | null`（正常非空、降级 null；`[]` 不会出现——后端 fail-closed 整体置 None）。
- `ModelBuildStep` = `step_id` / `title` / `intent` / `block_refs[]` / `parameter_refs[]` / `connection_hints[]` / `configuration_hints[]` / `depends_on[]` / `evidence[]` / `display_text`。
- `StepBlockRef` = `block_ref_id` / `block_type` / `library_path: string|null` / `purpose` / `paper_reference: PaperEvidenceEntry|null`。
- `ParameterMappingRef` = `paper_param_name` / `model_param_name`（复合键指向 `parameter_mapping` 行，**不带值**）。
- `ConnectionHint` = `from_block_ref` / `from_port: string|null` / `to_block_ref` / `to_port: string|null` / `signal_meaning: string|null`。
- `ConfigurationHint` = `target` / `setting_name: string|null` / `instruction` / `evidence: PaperEvidenceEntry[]`。
- **关键**：步骤所有文字字段后端 507-B 已过红线、不含参数值；参数值只在 `parameter_mapping`（参数对照表已渲）。

---

## 范围（必须做）

### 1. 升级 `BuildSteps.tsx`：结构化清单 + 静默降级回退
- `const structuredSteps = Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;`
- `structuredSteps` 非空 → 渲结构化清单（§2）。
- `structuredSteps == null`（含降级与防御性空）→ **静默**回退当前行为（`推荐库: library_choice` + `block_recommendations` 平铺卡）。**静默 = rendered DOM 不得出现 `fallback`/`legacy`/`degraded`/`overview` 等可见文本、`aria-label`、`title`、badge、状态条、差异化样式类**；内部分支/helper 命名可用 fallback，但不渲到 DOM。
- **不动**「子系统划分」（`SubsystemMap`，仍渲 `subsystem_breakdown`）/ 参数对照 / 调参 / `SectionNav`；「建模步骤」节 id 仍 `paper-build-steps`。
- **overview→detail（不改 SubsystemMap）**：正常路径 `subsystem_breakdown = 各步 display_text`，子系统划分 = 概览（目录），建模步骤 = 同批步结构化详情（照做）；本卡只升级后者，不合并、不删、不加任何区分两态的说明文案（见本版 P2-1）。

### 2. 单步渲染形状（砼核皮内，复用件，硬直角，纵向）
每步 = 一张 `GlassCard.paper-readable-card`（沿用 `.paper-step-card` 风格）：
- **步号 + 标题**：步号 mono（`.paper-step-index`，序号由 `build_steps` 数组顺序派生）；`title`（`.paper-copy`，合理 heading / `aria-labelledby`）。
- **意图**：`intent`（`.paper-secondary`）。
- **字段组（每组仅数组非空才渲，不渲空标题；组顺序固定如下；每组短 label，正文 `.paper-copy`/`.paper-secondary`，mono 只给 token；长 token `overflow-wrap:anywhere`；badge + 出处放 meta 行）**：
  1. **涉及块**（`block_refs[]`，每块一小块）：`block_type`（mono）+ `purpose`（正文）+ 库路径（`library_path` 有则 mono；空显「库路径待确认」**无 badge**，506 §4）+ `paper_reference` 非空 → badge（经 §映射）+ 出处。
  2. **关联参数**（`parameter_refs[]`）：`paper_param_name`（→ `model_param_name`）mono，**只显名、不显值/单位**，附「见参数对照表」。
  3. **接线提示**（`connection_hints[]`）：`from_block_ref → to_block_ref`，best-effort 附块名（`B1（Synchronous Machine）→ B2（三相测量）`，解析不唯一则回显原始 ref）；端口 `from_port`/`to_port` 有则附（mono，搭建提示非可执行端口）；`signal_meaning` 有则正文。
  4. **配置提示**（`configuration_hints[]`）：`target`（mono）+ `setting_name` 有则 mono + `instruction`（正文）+ `evidence[]` 非空 → badge（经 §映射）+ 出处。
  5. **依赖**（`depends_on[]`）：经 `step_id → 序号` map 显「依赖步骤 N」，找不到回显原始 `step_id` 或跳过；不做连线。
  6. **步骤证据**（`step.evidence[]`）：每条经 § 映射渲 badge + 出处（document_extracted）；无则不渲（不留空 badge 容器）。
- **来源 → badge 映射（P0-1 / P1-6，必须显式 helper，禁 raw 透传）**：
  ```ts
  function sourceToBadgeKind(source: PaperEvidenceEntry["source"]): SourceBadgeKind | null {
    if (source === "document_extracted") return "document_extracted";
    if (source === "user_supplied") return "user_supplied_resolved";
    return null; // 不打 badge
  }
  ```
  规则：BuildSteps 内**不得用** `missing_unresolved`；`document_extracted` 才调 `formatEvidence`、且仅返回非空才显出处；`user_supplied`（理论上初始生成不出现）只显「用户补充」badge、**不伪造出处**；映射返回 `null` / 无 evidence → 不打 badge。
- 列表 `<ol>`（沿用 `.paper-step-list`，纵向，硬直角）。

### 3. 复用 / 不新造
- 复用：`GlassCard`、`.paper-readable-card`/`.paper-step-card`/`.paper-step-index`/`.paper-copy`/`.paper-secondary`/`.paper-token`、`SourceBadge` + `SourceBadgeKind`、`formatEvidence`（BuildSteps 内就地复用/整理，**不扩大重构**）。
- `paper.css` 加 `.paper-build-step-*` 排版类（块小卡/参数行/接线行/配置行/meta 行），**只用 § 现状真 token、不新造颜色/字体**。
- **`parameter_refs` 锚跳**：默认**只显名 + 「见参数对照表」**（`ParameterTable` 行现无可锚 id）。锚跳为**可选增强**，仅当能给 `ParameterTable` 加向后兼容 `id`/`scroll-margin`、不改其列/排序/取值/badge 行为时才做；锚 id 由 `paper_param_name + model_param_name` 稳定编码，**不把 value/unit 放进 href/title/aria-label/tooltip**；点击只滚到行、不 inline 展开值。

### 4. 红线（前端侧；后端 507-B 已守，前端不得破）
- **不新增参数值/单位/倍率/推荐设值**：步骤区只显参数**名**（`parameter_refs`）；**不读/不渲** `plan.parameter_mapping[*].value/unit`；不硬编码「推荐设为 N / 增大 N% / N 倍 / 最优」类文案。允许显示：步号 / `step_id` / `block_ref_id` / 依赖号 / 后端原字符串 / `formatEvidence` 编号 / 参数名下标。
- **badge 不伪造**（decision 21）：badge 只挂真 `evidence`/`paper_reference`，经 § 映射；`library_path` 空 → 「库路径待确认」无 badge；不臆造第三态。
- **控制台干净**（decision 11）：不 `console.*`、不抛泄露细节的新异常。
- **feature boundary**（decision 21）：纯消费层，不臆测后端语义。

---

## 不做（明确排除）
- ❌ 不改后端 / API 契约 / `schema.json` / `paperTypes.ts` 类型 / DB / 任何 Python（只消费 `build_steps`；需后端补字段 = 边界划错，**停手报架构师**）。
- ❌ 不做追问；不为追问预留布局。
- ❌ 不给降级加任何提示/信号（含任何区分两态的说明文案）。
- ❌ 不重构其它 section；不改 `SubsystemMap`/`TuningPanel`/`SectionNav` 行为；不改五锚点。
- ❌ 不为结构化态向生产页面加 mock / dev flag / query 参数 / 硬编码样例。
- ❌ 不改现有 MCS 页 / `UploadDropzone` / `PanoramaScene` 签名 / 首页。
- ❌ 不新造颜色/字体/token；不横向滚；不折叠；不做复制/导出。
- ❌ 不引入前端测试框架。
- ❌ 多文件 / `PaperSpec` provenance 不碰。

---

## 验收标准（命令以 Stage 0 `package.json` 实测为准）
- [ ] **结构化态**：渲含完整字段的步骤清单——标题/意图/涉及块(含库路径或「库路径待确认」)/关联参数(只名不值)/接线(best-effort 块名)/配置/依赖/步骤证据 badge；字段组空则跳过、不渲空标题；长 token 换行不横向滚；badge + 出处在 meta 行。
- [ ] **静默降级**：`plan.build_steps = null` → 回退 `推荐库 + block_recommendations`，rendered DOM **无 `fallback`/`legacy`/`degraded`/`overview` 文本、aria-label、title、badge、状态条、差异化样式**；子系统划分照常渲。
- [ ] **来源映射**：grep/检视——BuildSteps **不把 `evidence.source` 原样传 `SourceBadge`**、不用 `missing_unresolved`；`document_extracted` 才显出处；无 evidence/未知 source 不打 badge、不留空容器。
- [ ] **红线（精确口径）**：grep——BuildSteps 不读/不渲 `parameter_mapping[*].value/unit`；无「推荐设为 N / 增大 N% / N 倍 / 最优」硬编码文案；步骤区参数只显名。
- [ ] **badge 不伪造**：`library_path:null` → 「库路径待确认」无 badge；`paper_reference:null`/无 evidence 不打 badge；无第三态臆造。
- [ ] **不污染生产**：grep/检视——生产页面无 mock 分支 / dev flag / query 参数 / 硬编码样例。
- [ ] **设计**：仅 § 现状真 token，全硬直角，复用 `GlassCard`/`SourceBadge`/`formatEvidence`/`.paper-readable-card`；纵向；grep 步骤主正文类不得用 `--color-rebar`（仅 meta/label 可用，504 § C）。
- [ ] **复用边界**：`SubsystemMap`/`TuningPanel`/`SectionNav`/现有 MCS 页字节未改（或 `ParameterTable` 仅加向后兼容锚 `id`/`scroll-margin`、行为不变）；`App.tsx`/路由/`paperTypes.ts` 不改。
- [ ] **无后端改动 + 契约零变更守门**：`git diff --stat origin/main` 仅含 § 范围前端文件 + 本卡；不含 `api/`/`core/`/`features/`/`adapters/`/`schemas/`；`python -m scripts.export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` **无变更**；`cd web && pnpm typecheck`（+ `pnpm lint` + `pnpm build`）全绿。
- [ ] **固定文案**逐字一致（见 § 固定文案，含字段组名）。
- [ ] **无障碍**：step title 合理 heading/`aria-labelledby`；字段组 section/list 语义；badge 与出处读屏相邻；无空 badge 容器。
- [ ] **冒烟**（仿 `task504-smoke`，源码/静态守卫）：至少覆盖「静默降级无 fallback 信号」「步骤区不读 `parameter_mapping.value/unit`」「`library_path` 空显待确认无 badge」；不可机检退化为 grep/检视 + **Codex 截图（图片附件）/PM 实测**。

---

## 固定文案（verbatim，正式工程/学术口径）
- 库路径未知：**库路径待确认**
- 参数引用后缀：**见参数对照表**
- 依赖前缀：**依赖步骤 {step_no}**
- 字段组名：**涉及块 / 关联参数 / 接线提示 / 配置提示 / 步骤证据**
- 出处：沿用 504 `formatEvidence`（按存在字段拼 章节/式/图）
- 无建模步骤（结构化空且 `block_recommendations` 也空）：沿用现有「暂无可展示的建模步骤。」

---

## Stage 0（派单后实现门第一步；Codex 实测，复制即跑，PowerShell 5.1 兼容，勿用 `&&`）
```
git fetch origin
git rev-parse origin/main
```
**用 `git fetch` 后的 live 返回值为基线，别照搬卡里/转述里写死的任何 SHA。** 逐项 PASS/FAIL，任一与 § 现状不符 → **停手报架构师**（decision 09/15：先诊断卡错 / main 错 / 同步漏做）：
1. `paperTypes.ts`：`build_steps: ModelBuildStep[] | null` + 五个 step 类型 + 无 `step_kind`。
2. `BuildSteps.tsx`：现仍只渲 `library_choice + block_recommendations`、未读 `plan.build_steps`。
3. `PaperResultPage.tsx`：section 顺序 + `paper-build-steps` + `<BuildSteps plan=.../>`；`SectionNav` 五锚点。
4. `SourceBadge`/`SourceBadgeKind`/`formatEvidence`/`GlassCard` 签名；`styles/index.css` token + `border-radius:0` + `@import "./paper.css"`；`paper.css` 那几个类。
5. `ParameterTable` 行无可锚 id（→ 默认只显名）。
6. `cat web/package.json`：真实 scripts + 无测试框架；`task504-smoke.mjs` 机制可仿。
7. `export_paper_schemas` 预期零 diff；`git status`：除预放本卡 `docs/tasks/task-508-build-steps-frontend-v0_2.md` + 本机 `*-dev.log` 外干净。

本机没 `grep`：用 `git grep`/`rg`/`Select-String`。**任一需改后端/契约才能交付 = 边界错，停手报架构师（升 R2）。**

---

## 完工三件套（decision 08）
- **PR 标题**：`TASK-508: 结构化建模步骤前端渲染`
- **PR 正文**：对照 § 验收逐条勾 + **结构化态 + 降级静默态截图（图片附件）** + `git diff --stat` 证无后端改动 + `export_paper_schemas` 零 diff + `pnpm typecheck/lint/build` 绿。
- 改已有文件**保留原始字节**（decision 08：编辑器或 `read_bytes`/`write_bytes`，禁 `read_text`/`write_text`/`sed -i`）；给 git status/log/push 三命令输出。
- **commit 分段（建议）**：① `feat(paper): render structured build_steps in BuildSteps (silent legacy fallback)` ② `style(paper): build-step card / blocks / params / hints (reuse tokens)` ③（可选）`feat(paper): param-ref anchor to parameter table` ④ `docs(tasks): add task-508 card`（+ 若有冒烟更新）。

---

## 风险与注意点
- **静默是 DOM 级**（P1-1）：肉眼不明显的 `aria-label`/`title`/`data-state`/差异化类也算降级信号，一律不渲到 DOM。
- **来源映射**（P0-1）：`evidence.source` 不是 `SourceBadgeKind`，必须经 helper；raw 透传/错映 `missing_unresolved` 都违红线。
- **红线精确口径**（P0-2）：禁的是参数值/单位/倍率，不是「一切数字」；验收用「不读 `parameter_mapping.value/unit` + 无推荐数值文案」，别用字面「无数字」。
- **降级回退即今天 UI**：`null` 回退 `block_recommendations`，与今天一致；`[]` 不会出现（后端 fail-closed），防御性按「空也回退」。
- **锚跳别撑范围**（P1-5）：`ParameterTable` 现无锚；默认只显名，锚跳做不了不算缺陷。
- **不污染生产**（P1-2）：截图/冒烟不得在生产路由塞 mock/flag。
- **契约零变更**：纯前端；零 diff 守门 + `pnpm typecheck`；需改后端 = 边界错，停手报架构师。
- decision 08 / 11 / 21 / 13（前端无契约改 → 零 diff 守门）。

---

## 自动升 R2 条件（实施期任一触发 → 停手报架构师，重起 R2）
1. Stage 0 现状与 § 不符（`BuildSteps` 已改 / `paperTypes` 无 `build_steps` / 类型不符）。
2. 渲染任一在范围功能**需改后端**。
3. 需改已合并产物超出 § 范围增量（必须改 `SubsystemMap`/`TuningPanel`/`SectionNav` 行为、或 `ParameterTable` 无法仅加向后兼容锚）。
4. 范围蔓延出 § 清单（追问 / 降级提示 / 横向滚 / 折叠 / 复制导出 / 新 section / 新端点）。
5. token 缺口需新造颜色/字体。
6. 需引入测试框架。

---

## TASK-508 在指导深度线的位置
506 RFC ✅ → 507-A 契约 ✅ → 507-B 生成 ✅ → **508 前端（本卡）** → 509 真实语料评测（量降级率 / 步骤可搭性，decision 25 双轴）。追问 / 多文件后续（520+）。

## 关联文档 / 决策
- **形状** 506 v0.3 §4；**契约** 507-A；**生成** 507-B；**现有前端** 504 v0.2（复用件 / 三态 badge / 可读性 § C）。
- **决策**：06 / 07 / 08 / 09 + 15 / 11 / 12 v0.4 / 13（前端无契约改 → 零 diff 守门）/ 21（feature boundary / badge 不伪造）/ 22（5xx）/ 25（评测双轴，509 用）。
- **审批历史**：v0.1 起稿（2026-06-28）→ v0.2 并入 R1（GPT，2 P0 + 6 P1 + 3 P2，「修完可派、不升 R2、不拆卡」）+ R6（Codex，现状全 PASS、纯前端可落地、契约零 diff 实跑、参数表无锚 / source 映射 / formatEvidence 复用提示）。
