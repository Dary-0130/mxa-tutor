# TASK-504 v0.2:资料入口前端页(论文复现阅读工作台)

## 状态

🔍 v0.2 起稿 · **GPT R1 + Codex R6 双审已过(方向通过,均"修完可派 Codex、不必升 R2")**,本版并入双审采纳意见,待 PM 拍板派 Codex 实现 — 2026-06-27,架构师,接 origin/main `57a672d`(Codex 取证基准,Stage 0 以最新为准)

---

## v0.2 双审采纳变更(对照 v0.1;两审来源标注)

> 双审均确认:**方向通过、不需改后端契约、不需拆卡**;以下为派单前回填项。R1 = GPT(决策/契约/可读性),R6 = Codex(仓库实证)。

| # | 来源 | 级别 | 变更 |
|---|---|---|---|
| 1 | R1 P0-1 | P0 | **参数表不替 `parameter_mapping` 行编逐参数出处**(后端这些参数无逐个 evidence)。只有 `missing_prompts.paper_reference` 与 `block_recommendations.paper_reference` 显示具体出处;`parameter_mapping` 行只标来源 badge;`plan.evidence[]` 作"整体依据"单列,不绑定单参数。 |
| 2 | R1 P0-2 | P0 | **来源 badge 不直接消费后端 `EvidenceSource`**(`MissingParameterPrompt.source` 恒为 `user_supplied`,但未填≠已补)。改为前端三态 `SourceBadgeKind` + 判定规则(见 § 接口契约)。 |
| 3 | R1 P0-3 / R6 P1 | P0 | **补参后流程改为 POST → 用 `updated_plan` 先渲染 → 再 GET `/plan` 刷新 `remaining_missing_prompts`**(user-supply 只返回 `updated_plan`,不含缺参状态)。 |
| 4 | R1 P1-1 | P1 | TS 类型补全 response/request DTO(`UploadDocumentResponse` / `PaperSpecResponse` / `PaperPlanResponse` / `TuningSuggestRequest` / `TuningSuggestResponse` / `UserSuppliedResponse` / `UserSuppliedResponseBatch` / `UpdatedPlanResponse`)。 |
| 5 | R1 P1-2 | P1 | 上传成功 `navigate` 携带同步返回结果(route state),结果页先渲染、再可选 GET 校准,避免二次 loading;直达/刷新仍走 GET。 |
| 6 | R1 P1-3 / P1-4 | P1 | 缺参可编辑列表用 `remaining_missing_prompts`;`parameter_mapping` 与 `missing_prompts` 按 `parameter_name` 合并(优先 `paper_param_name`,次 `model_param_name`,都不匹配则独立追加),不重复渲染。 |
| 7 | R1 P1-5 | P1 | 出处文案不写死"论文第 {N} 节"(`paper_section_id` 不保证是数字);改为按存在字段拼 `章节/式/图`。 |
| 8 | R1 P1-6 | P1 | 调参"禁造数值"用**代码锁 + 冒烟/检视**卡死(方向映射恰好 3 串;后端文本里自带的数字可原样显示,但前端方向标签/说明不得新增任何数字)。 |
| 9 | R1 P1-7 | P1 | 固定文案补 empty/error/success 状态(无子系统/无块/无参数/无待补/补充成功失败/调参空/未生成/失败/直达未找到)。 |
| 10 | R1 P1-8 | P1 | 可读性补 CSS 选择器级验收 + grep:主正文类不得用 `--color-rebar`(仅 meta/label/placeholder 可用)。 |
| 11 | R6 P1 | P1 | **`web/vite.config.ts` 加进范围**:补 `"/api":"http://localhost:8000"` 代理(现 proxy 只覆盖 `/health`/`/upload`/`/projects`,否则 PM 本机 `pnpm dev` 打不到 paper 后端)。 |
| 12 | R6 P1 | P1 | **前端无测试框架**(`package.json` 无 test、无 Vitest/Jest)。取消"按现有框架写测试",改用项目现成模式:`smoke:task504` 冒烟脚本(仿 `scripts/task402-smoke.mjs`)+ `pnpm lint`/`typecheck`/`build` + PM 实测;真实命令以 Stage 0 `package.json` 为准。 |
| 13 | R6 P1 | P1 | **`lib/api.ts` 允许最小增量**:上传 helper 泛型化(`apiUploadTask<T=UploadResponse>`)或新增 `apiUploadForm<T>` + 导出/复用 URL/error 逻辑,使 `paperApi.uploadDocument` 沿用同一 `VITE_API_BASE`/error 约定,不复制粘贴。**向后兼容、不破坏 TASK-402 上传**。 |
| 14 | R6 P2 / R1 | P2 | `PanelFrame` 仅作视觉参考,**不直接复用**(硬编码"导览第 n 屏/共 6 屏"+ `onFocusPanel`);论文 section 新建。 |
| 15 | R6 P2 | P2 | 允许 diff 文件清单**显式含** `docs/tasks/task-504-paper-frontend-v0_2.md`(Codex 在本 PR 连卡入仓),与"仅前端文件"验收口径不打架;Stage 0 baseline 白名单含该卡。 |
| 16 | R1 P2 | P2 | **不做复制/导出**(按钮不出现),避免顺手加范围外功能;调参输入**不 sticky bottom**,初始态用固定文案。 |

> 注:`web/src/styles/index.css` 已 `@import "./upload.css"`(实证),`.upload-dropzone` 类**全局可用**,新 `PaperDropzone` 复用无需额外 import;`paper.css` 加入同一 @import 链。

---

## 上下文(本任为什么做)

- paper-to-model v0.1 后端地基(TASK-500~503)已全部合并 main:文档解析 → `PaperSpec` → `ModelGenerationPlan` → `TuningSuggestion`、持久化、上传与 GET/POST 路由,**同步打通、无断点**(R6 取证自 origin/main `57a672d`)。
- 论文这条**没有任何前端页**,现只能接口调,无法演示 / 给用户上手。
- 本任 = **上传论文(PDF/docx)→ 一页纵向"阅读工作台"**(论文摘要 / 子系统划分 / 建模步骤 / 参数对照 / 调参建议),复用现有设计系统,**只对接已有后端数据、不改后端**。
- 产品定位"副驾不替代":用户开本机 MATLAB、对照本页逐步搭模型——**长时间边读边操作**,**可读性第一**(R1 可读性评审结论并入 § 上游契约 C)。
- 本任属 **paper-to-model v0.2 的前端落地**;PM 已拍定走论文线、沿用现有 app 皮、固定文案改正式口径、后端不动。

---

## 输入(前置依赖)

- **已完成**:TASK-500~503(paper 后端,✅ 在 main)、TASK-401(前端框架)、TASK-402(上传/导览页 + 设计系统 + UploadDropzone)、TASK-403(问答页 + scene 复用)。
- **必读**:01 / 02 / 04 / 05;决策 06 / 07 / 08 / 09 / 11 / 20 / 22。05 不改,仅了解(后端生成口径不动)。
- **现有前端**:`web/`(React + TS + Tailwind v4 经 `@tailwindcss/vite` + `@import "tailwindcss"`,无 config;react-router-dom;pnpm)。

---

## 输出(交付物)

- 新增:上传页 + 结果页、路由、`paperApi`/`paperTypes`、页内 section 组件、`paper.css`、`smoke:task504` 冒烟脚本。
- **不新增后端代码、不改后端契约/schema/DB**。
- 修改(均向后兼容小增量):`App.tsx`(2 路由)、`index.css`(1 行 @import)、`vite.config.ts`(1 行代理)、`lib/api.ts`(上传 helper 泛型化)、`lib/errorMessages.ts`(按需增量)。
- 完整清单见 § 范围。

---

## 上游契约(stand-alone 给 R1 — 自包含,实测自 origin/main `57a672d`)

### A. 后端数据契约(本任只消费,**不改**)

```
POST /api/v1/upload-document            (同步 await,非后台)  出: { paper_id, spec, plan, missing_prompts }
GET  /api/v1/papers/{paper_id}/spec     出: { paper_id, spec }
GET  /api/v1/papers/{paper_id}/plan     出: { paper_id, plan, missing_prompts, remaining_missing_prompts }
POST /api/v1/papers/{paper_id}/tuning-suggest  入:{ user_scenario:str(1..500) }  出:{ paper_id, suggestion }
POST /api/v1/papers/{paper_id}/user-supply     入:UserSuppliedResponseBatch       出:{ paper_id, updated_plan }   ← 仅 updated_plan,不含缺参状态
```

**模型字段(关键;全字段以 Stage 0 实测为准):**

- `PaperSpec`:`paper_title`、`paper_type`、`domain`、`abstract`、`equations[]`、`parameter_table[]`、`figure_locations[]`、`pseudocode_blocks[]`、`evidence[]`
- `ModelGenerationPlan`:`plan_id`、`paper_spec_id`、`library_choice`(单串)、`block_recommendations[]`(`block_type`+`purpose`+`paper_reference`)、`parameter_mapping[]`(`paper_param_name`+`model_param_name`+`value`+`unit?`+`source`,**无逐参数 evidence**)、`subsystem_breakdown`(**list[str] 3~10**)、`m_script_skeleton?`、`evidence[]`
- `MissingParameterPrompt`:`prompt_id`、`parameter_name`、`paper_reference`、`suggested_unit?`、`user_supplied_value?`、`user_supplied_unit?`、`source="user_supplied"`(**恒为此值,不代表已填**)
- `TuningSuggestion`:`suggestion_id`、`user_scenario`、`parameter_directions[]`(`param_name`+`direction`(increase/decrease/tune_within_range)+`physical_meaning`)、`expected_effect`、`confidence`(high/medium/low)、`evidence[]`、`disclaimer`(**无数值/倍率字段**)
- `PaperEvidenceEntry`:`source`、`paper_section_id?`(**字符串,不保证数字**)、`equation_id?`、`figure_id?`、`excerpt?`、`missing_param_prompt_id?`

**数据形状硬约束(决定页面能做什么):**

1. 上传**同步返回**;结果页可直接拿结果,直达/刷新走 GET `/spec`+`/plan`;**不照搬 zip 那条 `/projects/{id}/status` 轮询**。
2. `subsystem_breakdown` 只是字符串串,无与块/参数挂钩 → 只做轻量"子系统划分"总览。
3. `block_recommendations`/`parameter_mapping` 平铺,`library_choice` plan 级单库,无每步检查点/阅读顺序/该步参数绑定 → 建模步骤做"库 + 推荐块 + 用途 + 出处"可扫读卡。
4. `parameter_mapping` **无逐参数 evidence**;只 `missing_prompts`/`block_recommendations` 有 `paper_reference`。**禁止前端为 mapping 行猜/编出处**(R1 P0-1)。
5. 调参**只给方向**(三值枚举 + physical_meaning + expected_effect + confidence + disclaimer),**无数值** → 前端**禁造任何数值/区间**(R1 P1-6)。
6. `user-supply` 只返回 `updated_plan`,**缺参状态须 POST 后再 GET `/plan`** 取(R1 P0-3/R6)。

### B. 现有设计系统(**复用,不另起**;实测自 `web/`)

`index.css` token:

```css
--color-concrete:#2c2c2c;--color-ite:#e8e4de;--color-rebar:#8b8680;--color-formwork:#3a3a3a;
--color-signal:#e85d3a;--color-signal-dim:#c44d2e;--color-moss:#8fa58d;--color-cold:#d5e1db;
--font-display:"IBM Plex Sans","Noto Sans SC",system-ui,sans-serif; --font-mono:"IBM Plex Mono","Noto Sans Mono",monospace;
```

- 全局 `*{border-radius:0!important}` → 全硬直角。`index.css` 已 `@import` `scene.css`/`upload.css`/`overview.css`(故 `.upload-dropzone` 全局可用)。
- 氛围场景 `PanoramaScene`(prop `panoramaX:number`,`={0}` 纯背景)**按页挂**(`Layout.tsx` 仅 `<Outlet/>`);新页像 `OverviewPage` 自挂。
- 复用组件:`GlassCard`(`.info-card`)、`PanelIndicator`、`EmptyStateText`、`FileRow`、`PanoramaScene`。`PanelFrame` **仅视觉参考不直接复用**(硬编码"共 6 屏"+`onFocusPanel`)。
- `UploadDropzone` 硬编码 `.zip` → **不改**,新 `PaperDropzone` 复用 `.upload-dropzone`/`.upload-dropzone__mark` CSS,换 accept(.pdf/.docx)+ 文案。
- 皮 CSS 参考:`.info-card`=`border:1px solid rgba(220,230,220,.14);background:rgba(8,13,13,.34);backdrop-filter:blur(14px)`;主按钮 signal 实心 + 近黑字 + mono。
- 路由(`App.tsx`):`index→UploadPage`/`view/:projectId→OverviewPage`/`view/:projectId/chat→ChatPage`。
- lib:`api.ts`(`apiUploadTask`/`apiGet`,`buildUrl` 私有,`API_BASE` 来自 `VITE_API_BASE`)、`types.ts`、`errorMessages.ts`、`localStore.ts`。
- **dev 代理缺口**:`vite.config.ts` proxy 仅 `/health`/`/upload`/`/projects`,**未覆盖 `/api/v1/*`**(R6 P1)→ 本任补 `"/api"` 代理。

### C. 可读性规格(R1 评审采纳;本页为"阅读工作台")

1. **纵向滚**,不沿用导览页横向滚;品牌一致靠硬直角/信号色 + 左侧 sticky 锚点导航。
2. **正文提亮放大**:主正文/步骤 `--color-ite`、16px、行高 ~1.62;次级 ~14–15px(用 `--color-cold` 或定义可读次色);`--color-rebar` **仅** meta/label/placeholder/弱说明。
3. **字体分工严格**:`--font-mono` 只给短 token(块名/库名/参数名/单位/文件名);中文成句一律 `--font-display` + 大行距。
4. 阅读密集区表面**做实**(更不透,不让纹理透进笔画区);玻璃感留给顶栏/标签/按钮。
5. **信号色克制(~5–8%)**:仅主按钮/当前步号/来源 badge/待补充·warning/hover·focus/少量关键词;不铺正文、不全标题橙、不大面积边框。
6. **来源带文字**(见 § 接口契约固定文案),不只靠颜色/形状。
7. 建模步骤可扫读卡;参数完整表在正文 section,不塞窄侧栏无限滚。

---

## 范围(必须做)

> 新页多文件构建(非小补丁),"30 行阈值"不适用;红线见 § 不做 / § 自动升 R2。可按 commit 分段。每个新文件 ≤ 300 行(04),超了拆组件。

**新增文件(`web/src/`):**

1. `routes/PaperUploadPage.tsx` — 上传页(挂 `PanoramaScene` + `PaperDropzone`;成功后 `navigate("/paper/:paperId", { state:{ spec, plan, missing_prompts } })`,携同步结果避免二次 loading)。
2. `routes/PaperResultPage.tsx` — 纵向阅读工作台外壳(挂 `PanoramaScene` + `SectionNav` + 各 section + loading/error 态)。
3. `routes/paper/PaperDropzone.tsx` — PDF/docx 拖拽框,复用 `.upload-dropzone` CSS;accept=".pdf,.docx",mark "PDF",文案见固定文案表。
4. `routes/paper/PaperHeader.tsx` — 标题区(标题/一句话摘要/领域标签/资料类型/"重新上传";收敛,不做 hero)。
5. `routes/paper/SectionNav.tsx` — 左侧 sticky 锚点(摘要/子系统划分/建模步骤/参数对照/调参建议),当前项 signal 高亮;active 用 `IntersectionObserver`,无 observer 退化为点击态;键盘可达。
6. `routes/paper/SubsystemMap.tsx` — `subsystem_breakdown` 渲染为一排硬直角小块(编号,**不横向滚**,可换行)。
7. `routes/paper/BuildSteps.tsx` — `library_choice` + `block_recommendations`:每块 = 块名(mono)+ 用途(正文)+ `paper_reference` 出处。
8. `routes/paper/ParameterTable.tsx` — 见 § 接口契约的合并 + 来源 + 出处规则:`parameter_mapping` 行**只标来源 badge、不显示逐参数出处**;`missing_prompts` 行显示其 `paper_reference` + **可选填**输入;`plan.evidence[]` 作"整体依据"单列。
9. `routes/paper/SourceBadge.tsx` — 消费前端三态 `SourceBadgeKind`(见 § 接口契约),**均带文字**;`document_extracted`→signal 实心、`user_supplied_resolved`→signal 描边、`missing_unresolved`→虚线框 + warning icon。
10. `routes/paper/TuningPanel.tsx` — 场景输入(非 sticky)+ "生成调参建议" → 渲染 `parameter_directions`(方向枚举映射中文)+ physical_meaning + expected_effect + confidence(中文)+ disclaimer 原文;**前端不加任何数字**。
11. `routes/paper/usePaperResult.ts` — 取数/状态:route state 有完整结果先渲染(可选 GET 校准 `remaining_missing_prompts`);无则按 `paperId` GET `/spec`+`/plan`;loading/error/数据三态。
12. `routes/paper/useUserSupply.ts` — 提交缺参 → POST `/user-supply` → 用 `updated_plan` 先渲染 → **再 GET `/plan` 刷新 `remaining_missing_prompts`**;GET 失败保留 `updated_plan` + 提示"参数已提交,缺参状态刷新失败,可稍后重试";留空不提交、不挡。
13. `lib/paperApi.ts` — `uploadDocument`/`getPaperSpec`/`getPaperPlan`/`postTuningSuggest`/`postUserSupply`,沿用 `lib/api.ts` 的 `VITE_API_BASE`/error 约定(经 #18 的 helper)。
14. `lib/paperTypes.ts` — 与 § 接口契约 TS 类型逐字对齐(含全部 response/request DTO)。
15. `styles/paper.css` — 本页样式(§ B 真 token,不新造颜色;含 § 接口契约的 CSS 选择器级规格)。
16. `scripts/task504-smoke.mjs` — 冒烟脚本(仿 `scripts/task402-smoke.mjs` 机制,Codex 确认机制可行性):至少覆盖"调参 mock 无数字 → 渲染区无数字"、"来源三态文字正确"、"未填 missing prompt 显示待补充"等不变量;不可行的断言退化为 grep/检视 + PM 实测。

**修改文件(向后兼容小增量):**

17. `App.tsx` — 加 `/paper`(上传)+ `/paper/:paperId`(结果)。
18. `lib/api.ts` — 上传 helper 泛型化(`apiUploadTask<T=UploadResponse>`)或新增 `apiUploadForm<T>` + 导出/复用 URL/error,供 `paperApi` 沿用;**不破坏现有工程上传**。
19. `vite.config.ts` — proxy 补 `"/api":"http://localhost:8000"`(dev 转发 paper 后端)。
20. `styles/index.css` — 加 `@import "./paper.css";`。
21. `lib/errorMessages.ts` — 按需**增量**加资料入口中文错误文案(不改现有项)。
22. `package.json` — 加 `"smoke:task504"` script(若需);**不引入测试框架**。

---

## 不做(明确排除)

- ❌ 不改后端 / 任何 API 契约 / schema / DB / 后端 Python(只消费现有数据)。
- ❌ 不做需后端补数据的功能:每步"搭完检查清单"、参数面板跟步骤联动、单参数"看调参影响"(留以后,扩需 PM + R1)。
- ❌ 不做登录 / 付费 / 生成"打开即跑"`.slx` 成品。
- ❌ 不改后端 AI 生成内容口径(05 不动;只改前端固定文案)。
- ❌ 不沿用导览页横向滚;不做复制/导出按钮;调参输入不 sticky bottom。
- ❌ 不改现有 MCS 页(`UploadPage`/`OverviewPage`/`ChatPage`)、不改 `UploadDropzone`、不改 `PanoramaScene` 签名、不直接复用 `PanelFrame`。
- ❌ 不引入前端测试框架(用现成冒烟 + lint/typecheck/build + 实测)。
- ❌ 不做首页并列入口:先单独路由 `/paper`,不碰首页(并列入口待 PM 另拍)。

---

## 接口契约(TS 须与后端逐字对齐;固定文案 verbatim,Codex 不得自由发挥)

### TS 类型(`lib/paperTypes.ts`)

```ts
type EvidenceSource = "document_extracted" | "user_supplied";
type PaperDomain = "control_system"|"signal_processing"|"power_electronics"|"communication"|"motor_control"|"new_energy";
type PaperType = "paper"|"report"|"thesis";
type TuningDirection = "increase"|"decrease"|"tune_within_range";
type Confidence = "high"|"medium"|"low";

interface PaperEvidenceEntry { source:EvidenceSource; paper_section_id?:string|null; equation_id?:string|null; figure_id?:string|null; excerpt?:string|null; missing_param_prompt_id?:string|null; }
interface BlockRecommendation { block_type:string; purpose:string; paper_reference:PaperEvidenceEntry; }
interface ParameterMapping { paper_param_name:string; model_param_name:string; value:string; unit?:string|null; source:EvidenceSource; }
interface ModelGenerationPlan { plan_id:string; paper_spec_id:string; library_choice:string; block_recommendations:BlockRecommendation[]; parameter_mapping:ParameterMapping[]; subsystem_breakdown:string[]; m_script_skeleton?:string|null; evidence:PaperEvidenceEntry[]; }
interface MissingParameterPrompt { prompt_id:string; parameter_name:string; paper_reference:PaperEvidenceEntry; suggested_unit?:string|null; user_supplied_value?:string|null; user_supplied_unit?:string|null; source:"user_supplied"; }
interface PaperSpec { paper_title:string; paper_type:PaperType; domain:PaperDomain; abstract:string; evidence:PaperEvidenceEntry[]; /* equations[]/parameter_table[]/figure_locations[]/pseudocode_blocks[] 以 Stage 0 实测补全 */ }
interface ParameterDirection { param_name:string; direction:TuningDirection; physical_meaning:string; }
interface TuningSuggestion { suggestion_id:string; user_scenario:string; parameter_directions:ParameterDirection[]; expected_effect:string; confidence:Confidence; evidence:PaperEvidenceEntry[]; disclaimer:string; }

interface UploadDocumentResponse { paper_id:string; spec:PaperSpec; plan:ModelGenerationPlan; missing_prompts:MissingParameterPrompt[]; }
interface PaperSpecResponse { paper_id:string; spec:PaperSpec; }
interface PaperPlanResponse { paper_id:string; plan:ModelGenerationPlan; missing_prompts:MissingParameterPrompt[]; remaining_missing_prompts:MissingParameterPrompt[]; }
interface TuningSuggestRequest { user_scenario:string; }
interface TuningSuggestResponse { paper_id:string; suggestion:TuningSuggestion; }
interface UserSuppliedResponse { prompt_id:string; parameter_name:string; user_supplied_value:string; user_supplied_unit?:string|null; user_supplied_note?:string|null; }
interface UserSuppliedResponseBatch { user_supplied_responses:UserSuppliedResponse[]; }
interface UpdatedPlanResponse { paper_id:string; updated_plan:ModelGenerationPlan; }
```

### 来源 badge 三态(R1 P0-2,**前端判定,不直接消费后端枚举**)

```ts
type SourceBadgeKind = "document_extracted" | "user_supplied_resolved" | "missing_unresolved";
// row.kind: "mapping" | "missing"
function getParamSourceKind(row): SourceBadgeKind {
  if (row.kind === "missing" && !row.user_supplied_value) return "missing_unresolved"; // 待补充
  if (row.source === "user_supplied" && row.value)        return "user_supplied_resolved"; // 用户补充
  return "document_extracted"; // 论文提取
}
```

### 参数表合并 + 出处规则(R1 P0-1 / P1-3 / P1-4)

- 合并键优先级:`prompt.parameter_name == mapping.paper_param_name` → 否则 `== mapping.model_param_name` → 都不匹配则 prompt 作独立待补行追加;匹配则同一行显示 mapping 信息 + 待补输入,不重复两行。
- 可编辑待补列表来自 `remaining_missing_prompts`(非 `missing_prompts`)。
- **出处**:`parameter_mapping` 行**不显示逐参数出处**(后端无此数据),只显示来源 badge;`missing` 行可显示其 `paper_reference`;`plan.evidence[]` 单列为"整体依据",不绑定单参数。`block_recommendations` 行显示各自 `paper_reference`。

### 枚举 → 中文映射(API 返英文,UI 一律正式中文)

- domain:控制系统/信号处理/电力电子/通信/电机控制/新能源
- paper_type:论文/报告/学位论文
- direction:increase 增大 / decrease 减小 / tune_within_range 区间内调整(**恰好这 3 串,不得"增大10%–20%""小幅增大"**)
- confidence:高/中/低
- source(经三态):论文提取 / 用户补充 / 待补充

### 固定文案(verbatim,正式工程/学术口径)

| 位置 | 文案 |
|---|---|
| 上传拖拽框标题 / 副标题 / mark | 拖拽论文文件 / 或点击选择 .pdf / .docx 文件 / PDF |
| section 标题 1-5 | 论文摘要 / 子系统划分 / 建模步骤 / 参数对照 / 调参建议 |
| 顶栏按钮 / 调参按钮 | 重新上传 / 生成调参建议 |
| 建模步骤·推荐库前缀 | 推荐库: |
| 出处前缀 | 依据:章节 {paper_section_id} · 式({equation_id}) · 图({figure_id})(按存在字段拼,缺则省该项;**不写"第 N 节"、不从串提取数字**) |
| 来源 badge | 论文提取 / 用户补充 / 待补充 |
| 参数对照·说明 | 各参数已标注来源。缺失参数可选填,留空不影响其余建模步骤。 |
| 缺失参数输入 placeholder | 可填入数值,亦可留空 |
| 调参·方向区说明 | 仅给出调整方向,不提供具体数值。 |
| 调参·预期影响标签 / 置信度标签 | 预期影响 / 置信度: |
| 调参·免责 | 渲染后端 `disclaimer` 原文,不另加前端措辞 |
| 整体依据标签 | 路线图整体依据 |
| loading | 正在解析论文并生成建模路线… |
| 无子系统划分 / 无建模步骤 / 无参数 / 无待补 | 暂无可展示的子系统划分。/ 暂无可展示的建模步骤。/ 暂无可展示的参数对照。/ 暂无待补充参数。 |
| 参数补充成功 / 失败 | 已更新参数补充。/ 参数补充失败,请稍后重试。 |
| 缺参刷新失败 | 参数已提交,缺参状态刷新失败,可稍后重试。 |
| 调参输入为空 / 未生成 / 失败 | 请先描述调参场景。/ 输入调参场景后生成建议。/ 调参建议生成失败,请稍后重试。 |
| 直达未找到 | 论文结果不存在或已过期,请重新上传。 |
| 上传/解析错误 | 走 `errorMessages` 中文映射;兜底"论文解析失败,请检查文件格式或稍后重试。" |

### 可读性 CSS 选择器级(R1 P1-8;真 token,值可按现有 rgba 微调)

```css
.paper-copy{font-family:var(--font-display);font-size:16px;line-height:1.62;color:var(--color-ite);}
.paper-secondary{font-size:14px;line-height:1.55;color:var(--color-cold);}
.paper-token{font-family:var(--font-mono);}
.paper-readable-card{background:rgba(8,13,13,0.72);} /* 比氛围玻璃更实 */
```

---

## 验收标准(给可跑命令;命令以 Stage 0 `package.json` 实测为准)

- [ ] 上传 PDF/docx → 结果页从真实后端响应渲染五个 section。
- [ ] **来源三态**:mock `MissingParameterPrompt{ source:"user_supplied", user_supplied_value:null }` → UI 显示**待补充**,不得显示"用户补充";已填 → "用户补充";`document_extracted` → "论文提取"。
- [ ] **不伪造出处**:`parameter_mapping` 行**无逐参数出处**(grep/检视:mapping 行不渲染 `paper_reference`/evidence);只 `missing`/`block_recommendations` 显示具体依据;`plan.evidence[]` 仅作"整体依据"单列。
- [ ] **缺参可选填 + 重查**:留空不提交不挡;填后 POST `/user-supply` 成功 → **再 GET `/plan`** → 以 `remaining_missing_prompts` 刷新可编辑列表;GET 失败保留 `updated_plan` + 中文提示。
- [ ] **调参禁造数值**:方向映射恰好 3 串(grep);冒烟 A:mock suggestion 全文无数字 → 调参渲染区无 `/[0-9]+|%|倍|±|~|～/`;冒烟/检视 B:`expected_effect` 自带"约 5%"可原样显示,但方向标签/前端说明**不新增数字**。
- [ ] 设计:仅 § B 真 token(无新造颜色),全硬直角,复用 `GlassCard`/`.upload-dropzone` CSS/`PanoramaScene`;**纵向滚**(无横向 snap);可读性符合 § C;grep:主正文类不得用 `--color-rebar`。
- [ ] 复用边界:`UploadDropzone`/`PanoramaScene`/现有 MCS 页字节未改;`App.tsx` 仅加 2 路由;`index.css` 仅加 1 @import;`vite.config.ts` 仅加 1 代理;`lib/api.ts` 改动向后兼容(现有工程上传不回归)。
- [ ] **无后端改动**:`git diff --stat origin/main` 仅含 § 范围列前端文件 + 本卡 `docs/tasks/task-504-paper-frontend-v0_2.md`;不含 `api/`/`core/`/`features/`/`adapters/`/`schemas/`。
- [ ] 固定文案逐字一致;枚举全显示中文。
- [ ] 无障碍:结果页起首 sr-only 摘要;锚点导航键盘可达;aria 标签(沿用现有)。
- [ ] `pnpm lint` / `pnpm typecheck` / `pnpm build` 全绿;`pnpm smoke:task504`(若落地)绿。
- [ ] PM 实测:本机起前端(`pnpm dev` + paper 后端可用,经 `/api` 代理或 `VITE_API_BASE`)走"上传 → 看结果 → 填/留空缺参 → 生成调参建议"全流程,视觉与可读性达标。

---

## Stage 0(Codex 实施前实地核查,复制即运行,PowerShell 5.1 兼容,勿用 `&&`)

```
git fetch origin
git rev-parse origin/main
```

预期 HEAD ≈ `57a672d` 或更新(勿硬编旧值)。逐项报 PASS/FAIL + 异常;任一与 § 上游契约不符 → **停手报 PM**(决策 09/15:先诊断卡错还是 main 错,不盲改不盲过):

1. 五路由 + 模型字段与 § 上游契约 A 一致(`git show` 路由 + `paper_schemas.py`):确认 `upload-document` 同步、`subsystem_breakdown` list[str]、`parameter_mapping` **无逐参数 evidence**、`MissingParameterPrompt.source` 恒 `user_supplied`、`user-supply` 只返回 `updated_plan`、`TuningSuggestion` 无数值字段。
2. `index.css` token 与 § B 一致;全局 `border-radius:0` 在;确认 `index.css` 已 `@import "./upload.css"`(`.upload-dropzone` 全局)。
3. 复用组件存在/签名:`GlassCard`/`PanoramaScene`/`UploadDropzone`/`PanelFrame`;`Layout.tsx` 仅 `<Outlet/>`。
4. **`cat web/package.json`**:确认**无测试框架**、贴真实 scripts(dev/build/lint/typecheck/preview/smoke:task402),据此回填验收命令;确认 `scripts/task402-smoke.mjs` 机制(供 `task504-smoke` 仿写,判 DOM 断言可行性)。
5. `lib/api.ts`:`apiUploadTask`/`apiGet`/`buildUrl`/`API_BASE` 签名与私有性,确认泛型化/新 helper 的最小改法。
6. **`vite.config.ts` proxy 现状**:确认仅 `/health`/`/upload`/`/projects`、未覆盖 `/api`(R6 P1),据此补 `/api` 代理。
7. `lib/errorMessages.ts` 现有 error code/映射现状(供增量补文案)。
8. baseline 白名单:PM 预放的本卡 `docs/tasks/task-504-paper-frontend-v0_2.md`(git untracked = 预期)列入 baseline 勿停手;且列入"允许 diff 文件清单"。

---

## 完工三件套(决策 08)

- **PR 标题**:`TASK-504: 资料入口前端页(论文复现阅读工作台)`
- **PR 正文**:对照 § 验收逐条勾选 + 各 section 截图(PM 实测)+ 明示无后端改动(`git diff --stat` 证)。
- **commit 分段(建议 7–8)**:
  1. `chore(web): add /api dev proxy + generic upload helper`(vite.config + lib/api 增量)
  2. `feat(paper): upload page + PaperDropzone + route + paperApi/types`
  3. `feat(paper): result page shell + section nav + scene background`
  4. `feat(paper): subsystem map + build steps`
  5. `feat(paper): parameter table (merge + provenance three-state, no per-row evidence)`
  6. `feat(paper): tuning panel + optional user-supply (post then refetch)`
  7. `style(paper): readability spec + reuse tokens` + `test(paper): task504 smoke`
  8. `docs(tasks): add task-504 card`

---

## 风险与注意点

- 同步上传可能慢:给清晰 loading 态;"慢"是后端范畴,不在本任(不擅自加轮询/改后端)。
- **双源不可混淆 / 不伪造证据**(产品壁垒/决策 21):严格按三态 + 合并规则;`parameter_mapping` 行不挂逐参数出处;`user_supplied` 未填显示待补充。
- **调参不报死值**:只渲染后端方向 + physical_meaning + effect + disclaimer,前端禁造数字。
- 控制台不泄露异常细节/源码/敏感串(决策 11 精神)。
- 复用 CSS / token,不 fork;`lib/api.ts`/`vite.config.ts` 改动须向后兼容(现有工程上传/代理不回归)。
- 单文件 ≤ 300 行(04),组件拆分满足。

## 估时

前端多文件构建,预估 2–3 个工作日(取数/状态/五 section/样式/冒烟);按 commit 分段。

## 给 Codex 的提示

- 先 Stage 0,后动手;沿用 `web/` 约定(component 目录、全局 CSS 经 `index.css` @import、`lib/api` 约定、Tailwind v4 任意值类 + `backdrop-blur-md`)。
- **复用不重造**;固定文案 verbatim;枚举按映射显示中文;后端生成内容(摘要/用途/physical_meaning/disclaimer)原样渲染不改写。
- 来源用前端三态判定,**不直接渲染后端枚举**;`parameter_mapping` 行不挂出处。
- 补参 POST 后再 GET `/plan` 刷新 `remaining_missing_prompts`。
- 结果页取数:route state 优先,直达/刷新走 GET。
- 测试框架/命令以 `package.json` 实测为准,不引入新框架。

---

## 关联文档 / 决策

- **宪法/规范**:01 § 真实痛点 / 02 资料入口数据流 / 04 § 单文件上限 + 上传白名单 + 中文化错误 / 05(后端口径不动,仅了解)。
- **决策**:06 / 07 / 08 / 09 + 15(实地核查、不符停手)/ 11(异步/日志禁令精神)/ 20(行尾保留)/ 22(编号 5xx = paper-to-model,本卡 504)。
- **评审**:GPT R1(可读性 + P0/P1 并入)、Codex R6(仓库实证 + P1 并入)。
- **上游 Task**:TASK-500~503 / TASK-401/402/403。

## 自动升 R2 条件(Codex 实施期任一触发 → 停手报 PM,Claude 重起 R2)

1. Stage 0 发现后端实际数据与 § 上游契约 A 不符(字段/同步性/枚举/`user-supply` 返回/`parameter_mapping` evidence 等)= 设计变更。
2. 需要**改后端**(任何 `api/`/`core/`/`features/`/`adapters/`/`schemas/`)才能交付任一在范围功能。
3. 需要改已合并产物超出 § 范围列增量(如必须改 `UploadDropzone`/`PanoramaScene` 签名/现有 MCS 页;或 `lib/api.ts`/`vite.config.ts` 无法向后兼容)。
4. 范围蔓延到 § 范围清单外(新端点/新契约/横向滚/付费/.slx/复制导出等)。
5. token 缺口需新造颜色/字体(应复用)。
6. 需要引入测试框架才能满足验收(应改用冒烟 + lint/build + 实测)。

---

**版本**:v0.2(2026-06-27,并入 R1+R6 双审采纳意见)
**作者**:Claude(架构师)
**前置基准**:origin/main `57a672d`(Stage 0 以 `git rev-parse origin/main` 最新为准,漂移停手报 PM)
**审批历史**:
- v0.1 起稿(2026-06-27)— 待双审
- v0.2(2026-06-27)— 并入 **GPT R1**(3 P0 + 9 P1 + 3 P2,均"修完可派、不升 R2")+ **Codex R6**(0 上游 P0,4 P1 + 2 P2,"回填即稳")采纳意见;两审均确认方向通过、不改后端、不拆卡;待 PM 拍板派 Codex 实现(Codex Stage 0 复核契约为实现门第一步)
