# TASK-520-B1:Paper 追问 · 可见锚点 substrate(公式区 + 参数行锚 + 公共 formatEvidence + smoke)

**版本**:v0.2(已并 R1 + R6 双审 P1;**条件通过 → 定稿**,可派 Codex)
**所属线**:paper-to-model · 追问子线(decision 22)
**前置**:TASK-520-A 契约 RFC v0.2 已合并 main(PR #140 squash → main commit `1c8c4ef`);PM 已拍「公式区做、本版纯文本不引渲染库」
**现状基线**:R6 实测 origin/main HEAD = `1c8c4ef`(520-A squash);**派单后 Codex Stage 0 复核最新 HEAD,用 live 值**

---

## 本版改动(v0.1 → v0.2,并审而来)

**[P0]**:无(两审皆无 P0)。

**[P1 — 已并入]**:
1. **参数行不是互斥两类(R6 实测,结构性修正)**:`mergeRows` 会产出同时含 `mapping` + `prompt` 的合并行(缺参输入渲染在 mapping 行内)。单容器一个 id 无法同时给两个锚 → **改为双锚方案**(见 §A3)。
2. **equation_id 撞锚不改 id 形状(R1 + R6 一致,高信号)**:删除 v0.1「重复 equation_id 用序号兜底」。`equation_id` 唯一性是上游不变量(R6:parser 顺序 `EQ-xx`、`PaperSpecService` 拒重复 / 越界);B1 **不加 index 后缀、不改 `paper-eq-{equation_id}` 形状**;若实测真有重复 / 空 → 停手报架构师(decision 15),不自创 fallback id(见 §A2 / §C)。
3. **锚 id hash 锁成公共纯函数(R1 + R6,P2→P1)**:不留给临场实现。新增 `paperAnchors.ts`,B1 用、**B2 必复用同一算法**(见 §A3)。
4. **公式「照原样」需 `white-space: pre-wrap`(R1)**:`trim()` 只用于过滤空条;渲染用原始 `latex_or_text`(不 trim / normalize / replace);`.paper-equation-body` 必含 `pre-wrap` + 等宽 + `overflow-wrap`(见 §A2)。
5. **smoke 加负向越界守卫 + 重构删副本守卫(R1)**:不只断言「该有什么」,还断言「不该有什么」(见 §A5)。
6. **SectionNav 文案 + 行为澄清(R1)**:允许加 `paper-equations` 项并沿用既有 nav 行为,但不为 citation 新增任何 scroll / resolver / highlight / `location.hash`(见 §A1)。
7. **参数行 id 防 `undefined`(R1)**:`mappingIndex === undefined` 不得生成 `paper-param-map-*`(见 §A3 / §B)。
8. **验收加命令级红线(R1)**:`git diff --name-only` 范围核 + `git diff --stat` 全量实证(见 §B)。

**[★ 需双审确认的点 — 已裁]**:① `paper-equations` **不进** 520-A `SectionTarget` 枚举(R1 + R6 同意,公式定位靠 `EquationTarget`,不动已合契约);② 文案「公式」(两审认可);③ hash 选型升 P1、锁进 `paperAnchors.ts`(见上 P1-3)。

---

## 这张卡是什么 / 不是什么

- **是**:追问功能的前端「可见锚点地基」,纯前端。把「AI 出处要精确跳到的目标」在结果页真实建出来:① 新建公式区(逐条显示 `spec.equations`,每条挂 `paper-eq-*` 锚)② 参数表每行挂可定位锚 ③ 抽公共 `formatEvidence` + 锚 id 公共 helper ④ 基础静态 smoke(正向 + 负向)。
- **不是**:不做 scroll / 跳转 / 高亮(B2);不做 AnchorRegistry / target→DOM 解析(B2);不做后端 ask 端点 / source_table / citation / LLM(C);不做问答 UI / citation wiring(D);**不引数学渲染库**(本版纯文本,PM 拍);不补解析器抓图;不碰已有渲染产物语义(只加,不改 BuildSteps / SubsystemMap / TuningPanel / 既有 SectionNav 五项的行为)。

**为什么单独成卡**:520-A 铁律 2「anchor(DOM)真值源在前端」——后端只给语义 target,前端必须有真实 DOM 可被解析。实测结果页当前公式没渲染、参数行没锚,B 版「精确跳转」无目标可跳。B1 先把目标铺好,B2 才做跳转。

## 状态

✅ v0.2 双审条件通过 → 定稿,可派 Codex。纯前端 substrate,不动任何对外契约 / schema / 后端。

## 上下文 / 已锁口径(PM 已拍,本卡不重开)

- **公式区做,本版纯文本显示**(不引 katex / mathjax)。理由(R6 实测):公式数据是 Unicode 数学 / 纯文本混合、**非严格 LaTeX**,渲染库帮不上、还会在大量条目上报错;print-quality 渲染留待「解析器升级吐标准 LaTeX」后单独立卡。
- **公式数据脏是常态**:可能含残留 TeX 代码、上下标错位、乱码、空 / 占位(实测样本含 `H = ?`)。B1 **不假设干净**:照原样显示(等宽 + `pre-wrap`、不改写);空 / 纯空白条目不渲染、不留空壳;整区无可显示内容时连区块带导航项一起不渲染。锚点照挂——好不好看不影响「点出处可跳」核心。
- **标准**:给朋友用要能见人——失败态都要兜住且体面;合并前截图覆盖关键态(含「公式带残留代码」「公式区为空」)。
- **复用砼核风皮**(#2c2c2c / 信号橙 #e85d3a / IBM Plex + 思源黑 / `border-radius:0` / 半透玻璃);**不新造 token**(token 在 `web/src/styles/index.css` 的 `:root`)。

## 现状事实(R6 实测 origin/main `1c8c4ef`,全部成立;派单时再核 live)

> 给 R1:你无 repo,以下为实测事实,按此审、勿假设其它。

- **PaperResultPage**(`web/src/routes/PaperResultPage.tsx`):五 section,顺序 = 摘要 `paper-summary` / 子系统 `paper-subsystems` / 建模步骤 `paper-build-steps` / 参数 `paper-parameters` / 调参 `paper-tuning`。`SectionNav` 同步五项(静态五项 + observer 映射)。公式区插「摘要后、子系统前」可行。
- **EquationEntry**(`web/src/lib/paperTypes.ts` + `core/domain/paper_spec.py` 同形):`{ equation_id: string; latex_or_text: string; paper_section_id: string }`。
- **公式数据样本**:`"...e^(-2.97t)·cos(ωt+α0)..."` / `"i = C e^{-t}"` / `"H = ?"` / `"H = 3.5"` —— Unicode 数学 + 少量类 TeX 上标,混合、非严格 LaTeX、含空 / 占位。parser 生成顺序 `EQ-xx` id,`PaperSpecService` 拒重复 / 越界 → 真实 API 数据不应有重复 equation_id。
- **渲染库**:`web/package.json` 无 katex / mathjax;React 19 + react-router-dom 7 + Vite + Tailwind 4 + pnpm。**本版不引库**。
- **ParameterTable**(`web/src/routes/paper/ParameterTable.tsx`):`mergeRows` 行**不互斥**——`mappings.map((mapping, index) => ...)` 产出的行恒有 `mapping`、可能附带匹配到的 `prompt`(`{mapping}` 或 `{mapping, prompt}`);未匹配的 prompt 另起 `{prompt}` 行。缺参输入渲染在带 prompt 的行内。mapping 原始 `index` 现仅在 map 闭包内可见、写进 `row.key`;渲染层 `rows.map((row) => ...)` 拿不到原 index。`prompt.prompt_id` 渲染层可直接拿。
- **formatEvidence 两份**:`BuildSteps.tsx` 版无证据返回 `""`;`ParameterTable.tsx` 版无证据返回 `"依据:未标注"`;其余(章节 / 式 / 图)逻辑相同。
- **CSS**:token 在 `web/src/styles/index.css` 的 `:root`;`paper.css` 有 `.paper-section{scroll-margin-top:36px;margin-top:84px}` 与 `.paper-param-row` 的 grid。
- **smoke**:`web/scripts/task508-smoke.mjs` 是「读源码字符串静态断言」守卫;`web/package.json` scripts 有 `smoke:task402/504/505/508`。
- **数据可得**:`usePaperResult`(`web/src/routes/paper/usePaperResult.ts`)→ `data.spec.equations` / `data.plan` / `data.remainingMissingPrompts` 均可直接读。

## 接口 / 契约对齐(520-A v0.2;B1 必须守)

- **三层真值源**:① LLM 只给 `source_id`,不造 anchor;② 后端给**语义 target**;③ **前端 AnchorRegistry 是 DOM 真值源**。**B1 只负责「让 DOM 锚存在」这一步——挂锚,不做解析、不做跳转**(解析 + scroll + highlight 是 B2)。
- **锚 id 形状(520-A §4)**:公式 `paper-eq-{equation_id}`;plan_mapping 行 `paper-param-map-{row_index}-{hash(paper_param_name|model_param_name)}`;missing_prompt `paper-param-missing-{prompt_id}`;section 沿用现有五个;`hash` **仅 DOM-id 字符安全 / 去重,非业务键**。
- **参数定位唯一键** = `origin + row_index`(plan_mapping)/ `prompt_id`(missing);`paper_param_name` / `symbol` **只作 label / 诊断,绝不作匹配键**。
- **`mappingIndex`(前端)== `row_index`(后端)**:两者都按 `plan.parameter_mapping` 原顺序索引(520-A:`PlanAssembler.merge()` 保序)。**B1 据此用 `mappingIndex` 生成 map 锚,B2 用 target `row_index` 经同一 helper 解析,二者必然一致。**(若生成链以后改成会重排 → 本假设失效,停手报架构师,decision 15。)
- **alias = MAY(520-A §4)**:B1 **不得**用 name / symbol fuzzy 或名字相等创建 alias;每个可见行只挂自身 origin 锚。
- **无锚不跳空**:B1 不引入任何 `location.hash` / `scrollIntoView`;本卡只产出 DOM 锚。

---

## §A 范围(必须做)

### A1. 新建公式区 section(`PaperResultPage.tsx`)
- **位置**:插在 `paper-summary` 之后、`paper-subsystems` 之前。
- **形状**:`<section id="paper-equations" className="paper-section" aria-labelledby="paper-equations-title">` + `<h2 id="paper-equations-title">公式</h2>` + `<EquationList items={data.spec.equations} />`。
- **空态(条件渲染)**:`renderableEquations = equations.filter(e => e.latex_or_text.trim() !== "")`;若 `renderableEquations` 为空 → 整个 section **不渲染** + SectionNav **不加该项**(不留空壳)。
- **SectionNav**:加一项(`paper-equations` / 「公式」),顺序对应(摘要后、子系统前),**与公式区同条件出现**。R6 实测 SectionNav 是静态五项 + observer;**允许**通过 prop(如 `includeEquations` / `sections`)加入该项并**沿用既有 SectionNav 行为**(observer 会跳过不存在元素,不牵动既有五项逻辑)。**不得**为 citation / source badge 新增任何 scroll / resolver / highlight / `location.hash`;本卡只新增同类 nav item,不扩展为 B2 精确跳转机制。

### A2. 新建 `EquationList` 组件(`web/src/routes/paper/EquationList.tsx`)
- 渲染 `renderableEquations`(空 / 纯空白条目已在 A1 过滤;组件内不再渲染空壳)。每条:
  - 容器挂锚 `id = paper-eq-${equation_id}`(供 B2;**本卡只挂、不跳**)。**严格此形状,不加 index 后缀。**
  - 显示 `latex_or_text`:**用原始字符串渲染**(不 trim / normalize / replace / 美化)。`trim()` 仅用于 A1 的空判断。
  - 可附小标签显示 `equation_id`(label 用;实施细节)。
- **不用 `dangerouslySetInnerHTML`;不引任何数学渲染库。**
- 新 CSS 类(`paper.css`),命名照 build-step 类风格,如 `.paper-equation-list` / `.paper-equation-item` / `.paper-equation-body` / `.paper-equation-id`。**`.paper-equation-body` 必含 `white-space: pre-wrap` + 等宽字体(`var(--font-mono)`)+ `overflow-wrap:anywhere`**(保「照原样」覆盖残留 TeX / 乱码 / 换行 / 缩进 / `H = ?`)。复用现有 token。

### A3. 参数行加锚 + 锚 id 公共 helper(`ParameterTable.tsx` + 新 `paperAnchors.ts`)

**A3.1 公共 helper(`web/src/routes/paper/paperAnchors.ts`,纯函数)**
```
makePlanMappingAnchorId(rowIndex, paperParamName, modelParamName)
   → `paper-param-map-${rowIndex}-${hash}`
   hash = FNV-1a 32-bit,遍历 code point,输出 .toString(36)
   hash 输入 = `${paperParamName}|${modelParamName}`
makeMissingPromptAnchorId(promptId)
   → `paper-param-missing-${promptId}`
```
- B1 **只用它生成 id**,不做 registry / resolver。**B2 必复用该 helper**(从 `PlanMappingParameterTarget` 的 `row_index` / `paper_param_name` / `model_param_name` 与 `MissingPromptParameterTarget` 的 `prompt_id` 算同一 id),**不重写算法**。
- 算法要求:**稳定、同步、DOM-id-safe、非业务键**(业务真值仍是 `row_index` / `prompt_id`)。

**A3.2 行锚挂载(`ParameterTable.tsx`,按 R6 双锚)**
行不互斥,共三型:① `{mapping}` ② `{mapping, prompt}`(合并行)③ `{prompt}`(missing-only)。
- `ParameterRow` type **增字段 `mappingIndex?: number`**;`mergeRows`:mapping 行(①②)`row.mappingIndex = 原 index`;③ 不设(`undefined`)。
- **① / ②(有 mapping 的行)**:容器 `.paper-param-row` 挂 `id = makePlanMappingAnchorId(mappingIndex, paper_param_name, model_param_name)`。
- **②(合并行,额外)**:在该行已有 cell / 缺参 label 内**放一个零布局子锚**(如 `<span id={makeMissingPromptAnchorId(prompt_id)} className="paper-anchor-stub" />`),使 `paper-param-missing-{prompt_id}` 在合并行也可被定位。
- **③(missing-only 行)**:容器 `.paper-param-row` 挂 `id = makeMissingPromptAnchorId(prompt_id)`。
- **防 `undefined`**:仅 `mappingIndex !== undefined` 才生成 map 锚;若有 mapping 的行缺 `mappingIndex` = 实现错误(smoke / 测试应失败),**不得生成 `paper-param-map-undefined-*`**。
- **只加 `id`(及零布局 stub),不改 grid / 样式**(520-A:加 id 不触发样式;`.paper-anchor-stub` 须零尺寸 / 不占布局)。

### A4. 抽公共 `formatEvidence`(`web/src/lib/paperEvidence.ts`)
- 新建 `paperEvidence.ts`,签名 `formatEvidence(entry, { emptyText = "" } = {})` —— **保留两版差异**:默认 `emptyText = ""`(BuildSteps 用默认);`ParameterTable` 显式传 `"依据:未标注"`。
- `BuildSteps.tsx` 与 `ParameterTable.tsx` 改为 import 公共版,**删除各自局部副本**。
- 行为对齐现状(章节 / 式 / 图 同逻辑)。**纯重构,对用户零可见变化。**

### A5. 基础 smoke(`web/scripts/task520b1-smoke.mjs` + `package.json` scripts `"smoke:task520b1"`)
照 `task508-smoke.mjs` 静态守卫风格(读源码字符串断言),**正向 + 负向 + 重构守门**:

**正向(该有什么)**:
- PaperResultPage 含 `paper-equations` section + `EquationList` 引用。
- EquationList 渲染 `paper-eq-${...}` 锚 id 形状;`.paper-equation-body` 含 `white-space: pre-wrap`。
- ParameterTable 行挂 `paper-param-map-` 与 `paper-param-missing-` 两种锚形状;`ParameterRow` 有 `mappingIndex`;锚 id 经 `paperAnchors` helper 生成(import 自 `paperAnchors`)。
- 公式区新 CSS 类存在。

**负向(不该有什么 — 防越界 B2 / 渲染库)**:
- `PaperResultPage.tsx` / `EquationList.tsx` / `ParameterTable.tsx` **不含** `scrollIntoView`、`location.hash`、`window.location`、`AnchorRegistry`。
- `package.json` **不新增** `katex` / `mathjax` / `react-katex` 等数学渲染依赖。
- 公式组件**不含** `dangerouslySetInnerHTML`。

**重构守门(纯重构、保留差异)**:
- `BuildSteps.tsx` / `ParameterTable.tsx` **不再含** `function formatEvidence` / `const formatEvidence`。
- 两处均从 `web/src/lib/paperEvidence` import。
- `paperEvidence.ts` 默认 `emptyText` 是 `""`;`ParameterTable` 调用显式传 `"依据:未标注"`。

**不跑功能、不渲染**;静态守卫防回退。

## 不在本卡(明确排除)
- ❌ scroll / `scrollIntoView` / `location.hash` / `window.location` / 高亮(B2)。
- ❌ AnchorRegistry / target→DOM resolver(B2)。
- ❌ 后端 ask 端点 / source_table / citation / LLM(C);问答 UI / citation wiring(D)。
- ❌ 数学渲染库 / `dangerouslySetInnerHTML`(本版 PM 拍纯文本)。
- ❌ figure 锚 / 图索引(走「丙」);补解析器抓图。
- ❌ 改 BuildSteps / SubsystemMap / TuningPanel / 既有 SectionNav 五项行为(SectionNav 只**加**一项)。
- ❌ alias / fuzzy 参数匹配(520-A §4)。
- ❌ 改 `paper-eq-*` 锚 id 形状 / 加 index 后缀(equation_id 重复 = 上游错,停手报架构师)。

## §B 验收标准
- [ ] 公式区在摘要后、子系统前渲染;每条挂 `paper-eq-{equation_id}`(无 index 后缀);`latex_or_text` 用原文 + `white-space: pre-wrap` + 等宽显示;空 / 纯空白条不渲染;**`renderableEquations` 空 → 整区 + 导航项都不显示**。
- [ ] 参数表三型行锚正确:① `{mapping}` 容器挂 `paper-param-map-{index}-{hash}`;② `{mapping,prompt}` 容器挂 map 锚 + 行内零布局子锚 `paper-param-missing-{prompt_id}`;③ `{prompt}` 容器挂 `paper-param-missing-{prompt_id}`。`ParameterRow` 带 `mappingIndex`;grid / 样式无变化;**无 `paper-param-map-undefined-*`**。
- [ ] 锚 id 全经 `paperAnchors.ts` 公共 helper 生成(FNV-1a、`row_index`/`prompt_id` 为业务键);B2 可复用同函数得一致 id。
- [ ] `paperEvidence.ts` 公共 `formatEvidence(entry,{emptyText=""})` 被 `BuildSteps` + `ParameterTable` 复用,保留 `emptyText` 差异;两处局部副本删除;用户零可见变化。
- [ ] `smoke:task520b1` 正向 + 负向 + 重构守门全绿。
- [ ] `pnpm typecheck` / `lint` / `build` 绿;前端运行时不新增 `console.*`(decision 11)。
- [ ] **纯前端零对外契约 / schema / 后端改动**。验收贴:
  - `git diff --name-only origin/main -- api core features adapters schemas docs/06_OUTPUT_CONTRACTS.md Makefile` → **期望空**;
  - `git diff --stat origin/main` → 全量改动实证(只应在 `web/src/...` / `web/scripts/...` / `web/package.json`;实际改动 ≠ 卡范围 → 停手报架构师,decision 12 R6.1)。
- [ ] **合并前截图覆盖关键态(图片附件传进对话)**:① 正常公式区(干净符号)② 公式带残留 TeX / 乱码 ③ 公式区为空(整区不显示)④ 参数表(含 `{mapping}` 纯 mapping 行 + `{mapping,prompt}` 合并行 + `{prompt}` missing-only 行三型)⑤ 整页(含新公式区位置 + 导航)。

## §C 风险与注意点
- **公式数据脏是常态**(R6 实测):任何脏值不得让公式区崩 / 白屏;原文 + `pre-wrap` + 等宽兜住。
- **equation_id 唯一性是上游不变量**:B1 **不改 `paper-eq-{equation_id}` 形状、不加 index**。若实测真有重复 / 空 `equation_id` → 停手报架构师(decision 15),不自创 fallback id;最多开发态静态 / 测试守护。
- **参数行不互斥**(R6):合并行(`{mapping,prompt}`)必须双锚,否则真实 unresolved prompt 无可跳锚(smoke 可能误绿)。
- **不引 `location.hash` / `scrollIntoView` / `window.location`**(B2 的事);B1 引入任何跳转行为 = 越界(负向 smoke 守)。
- **SectionNav 只加一项**,沿用既有行为,不为 citation 扩跳转;空公式区时该项也不出现。
- **`mappingIndex == row_index` 依赖保序**:若生成链将来重排 parameter_mapping,本契约失效 → 停手报架构师。
- **字节 / 行尾**:改已存在文件保留原始字节(decision 08:补丁式编辑,禁 `read_text`/`write_text`/`sed -i`)。
- **`latex_or_text` 不参与可信度红线**:B1 只显示,不改写 / 替换 / 补全;脏 / 空照实。

## §D 给 Codex 的提示
- Stage 0 用 **live HEAD**(`git fetch` 后 `git rev-parse origin/main`,用 live 值;卡基线 `1c8c4ef` 供对照)。
- 纯前端;**不碰**后端 / schema / Makefile / docs/06。
- 锚 id 一律走 `paperAnchors.ts` 公共 helper;hash = FNV-1a 32-bit code-point → `toString(36)`,输入 `${paperParamName}|${modelParamName}`;**B2 复用,别让 B2 重写**。
- 参数双锚按 §A3.2(三型行);`formatEvidence` 抽取是纯重构(`emptyText` 差异保留)。
- smoke 正向 + 负向 + 重构守门(§A5),照 `task508-smoke.mjs` 风格。
- **截图作为图片附件传进对话**,覆盖 §B 关键态(尤其脏公式 / 空公式区 / 参数表三型行);绿勾 ≠ 看了视觉。
- 改已存在文件保留原始字节(decision 08);前端运行时控制台干净(decision 11;smoke 脚本 `console.log` 同现有风格 OK)。
- **索引(decision 07 / 08)**:`TASK-520` 整数行已 🔍 在索引。B1 完工后 520 仍未全完 → **仍 🔍、进度计数不 +1**;索引收尾 = 更新 `TASK-520` 行**备注**(加 520-B1 ✅、B2/C/D/E 待起草),保持 🔍。**读真索引定收尾范围**;代码 PR 与索引收尾 PR 分开走;预放的 v0.2 卡文件在该实现 PR 里连代码一并入仓(Stage 0 白名单)。

## §E 后续依赖(本卡定稿后)
```
TASK-520-B1(本卡,可见锚点 substrate)
   └─► 520-B2  AnchorRegistry + scroll/highlight(复用 paperAnchors helper;target→DOM resolver + scrollIntoView + 高亮 + unresolved→null + 不 location.hash)
520-C 后端 ask 端点 可与 B1/B2 并行起;equation/param 可点联调等 B2。
```
