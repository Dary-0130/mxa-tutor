# TASK-505 v0.2:首页双线入口(标签切换 — 资料复现入口露出)

## 状态

🔍 v0.2 起稿 · **GPT R1 + Codex R6 双审已过(条件通过,均"修完可派 Codex、不必升 R2、不拆卡")**,本版并入双审采纳意见,待 PM 拍板派 Codex 实现 — 2026-06-27,架构师,接 origin/main `526ce09`(R6 已 `rev-parse` 实证 = `526ce09acb…`;Stage 0 以最新为准)

---

## v0.2 双审采纳变更(对照 v0.1;两审来源标注)

> 双审均确认:**方向通过、不改后端、不拆卡**;以下为派单前回填项。R1 = GPT(决策/契约/可读性),R6 = Codex(仓库实证)。

| # | 来源 | 级别 | 变更 |
|---|---|---|---|
| 1 | R1 P0-1 | P0 | **索引流程消歧**:本 PR **不碰** `docs/03_TASK_INDEX.md`(列为 **must-clean / 不得改**);**TASK-505 暂不在索引中 = Stage 0 预期,Codex 不得为此停手**;索引收尾(加 TASK-505 行 + 进度条 + ✅)= 合并后**单独 docs-only PR**(决策 07「✅ 在合并后新开小 PR 改索引」+ 504/519 先例「代码 PR 与索引收尾 PR 分开走」)。**未采纳 R1 方案 A**(把索引并入代码 PR);R1 无 repo、依决策 07 字面,未含本项目「分开走」现行约定,架构师据 07 + 先例裁为分开。 |
| 2 | R1 P1-1 | P1 | **busy 硬不变量**:`busy===true` 时标签**不可激活**,组件强制 `activeTab="engineering"`、**不渲染资料复现面板**;方向键/Enter/Space/点击均不能切到资料复现。**不改上传逻辑,仅封死 UI 状态机。** |
| 3 | R1 P1-2 + R6 P2-3 | P1 | **完整 tab a11y**:`<button type="button" role="tab">` + 稳定 `id`;内容区 `role="tabpanel"` + `aria-labelledby` 指回对应 tab;active tab `tabIndex=0` / inactive `tabIndex=-1`;busy 时资料复现 tab `aria-disabled="true"`(若用原生 `disabled`,禁用期键盘亦不可切);方向键只在两 tab 间移动/激活、**不滚页**。另:外层 `<section aria-label="上传 MATLAB 工程">` 的 **aria-label 改中性「首页入口」**(aria 属性、**非可见文案**;因该区现含两入口)。 |
| 4 | R1 P1-3 | P1 | **锁资料复现引导句(verbatim)**:见 § 固定文案。覆盖「独立入口 + 不碰 zip 流程 + 不暗示自动生成模型」(合宪法口径),不许 Codex 自由发挥。 |
| 5 | R1 P1-4 | P1 | **行数核查**:Stage 0 加 `(Get-Content web/src/routes/UploadPage.tsx).Count`;验收加 `UploadPage`(+ `EntryTabs` 若存在)行数核;`UploadPage` 近 300 行(04)则**先抽 `EntryTabs`,不先塞后返工**。 |
| 6 | R1 P1-5 | P1 | **未改文件核验改 `git diff --exit-code` 命令组**(替换「block-hash」),逐个红线文件出命令(见 § 验收);对齐决策 12 R6.1(完工 report 按 `git diff --stat origin/main` 实证列改动)。 |
| 7 | R6 P1-1 + R1 P2-2 | P1 | **`smoke:task505` 落地为 package script**:新增 `web/scripts/task505-smoke.mjs`(仿 `task504-smoke.mjs`)+ `web/package.json` 加 `smoke:task505`;故 **允许 diff / 输出 / commit / Stage 0 白名单显式含 `web/package.json`**(否则与「diff 仅含 UploadPage/EntryTabs/upload.css/卡」冲突,R6 实证 `package.json` 现仅 `dev/build/lint/typecheck/preview/smoke:task402/smoke:task504`)。 |
| 8 | R6 P1-2 | P1 | **本卡预放时点**:R6 实证 `docs/tasks/task-505-*.md` 当前 **untracked 都不存在**(因仍在评审)。改为「实施时 PM 预放本卡 **v0.2(定稿)** 到 `docs/tasks/`;若未预放,Codex 在本 PR 内新增该卡」;Stage 0 白名单含该卡(untracked = 预期 / 或 Codex 新增)。 |
| 9 | R1 P2-1 | P2 | **CSS 类名前缀化**(降全局污染):`.upload-entry-tabs` / `.upload-entry-tab` / `.upload-entry-tab--active` / `.upload-entry-panel` / `.upload-paper-entry`。 |
| 10 | R1 P2-3 | P2 | **`EntryTabs` 纯 UI contract**(若抽组件):`type EntryTabKey = "engineering" \| "paper"; interface EntryTabsProps { activeTab: EntryTabKey; disabled: boolean; onChange:(t:EntryTabKey)=>void }`。**不持有 reducer/poll/navigate**。 |
| 11 | R6 P2-1 | P2 | **§B 修正**:删去「`.upload-copy` 作可复用 styled class」之说(R6 实证无独立 `.upload-copy {}`,仅 `upload.css` 的 `.upload-copy h1` 媒体规则);其余 `.brutal-panel`/`.section-kicker`/`.text-command`/`.upload-content`/`.upload-dropzone`/`.upload-status-card` 均真实存在。 |
| 12 | R6 P2-2 | P2 | **focus 样式落实**:加 `.upload-entry-tab:focus-visible`(signal focus ring),**不靠浏览器默认**(仓库无全局 tab/button focus class)。 |

---

## 上下文(为什么做)

- TASK-504(paper 前端)已合并 main,但 `/paper` 仅作为独立路由存在,**首页(`/` = `UploadPage`)无任何入口可点进资料复现这条线**;TASK-504 当时明确「不做首页并列入口」,本任补此产品断点。
- 首页已有工程线与资料线的入口语义,但**唯一可交互元素是 `.zip` 工程上传框** → 资料这条「说了但点不进去」。本 PR 同步按 PM 拍板做双审后视觉清理:左栏删 `.upload-hero-note` 免责段 + 标语改「工程导览 / 资料复现」。
- 本任 = 在首页上传区**上方**加「工程导览 | 资料复现」两标签:默认停**工程导览**(现有 .zip 上传行为一字不变);点**资料复现** → 跳 `/paper` 的入口面板。**只动首页这一层,不碰 /paper、不碰 .zip 流程、不碰后端、不碰索引。**
- PM 已拍:走**标签切换方案**;沿用现有砼核风;文案正式工程口径。

---

## 输入(前置依赖)

- **已完成**:TASK-402(首页/上传页 + `UploadDropzone` + 设计系统,✅ 在 main)、TASK-504(`/paper` 上传页 + 结果页 + `PaperDropzone`,✅ 在 main)。
- **必读**:02 资料入口数据流(了解)、04 工程规范(单文件 ≤ 300 行、中文化);决策 06 / 07 / 08 / 09 / 12 / 15 / 20 / 22。
- **现有前端**:`web/`(React + TS + Tailwind v4 经 `@tailwindcss/vite` + `@import "tailwindcss"`,无 config;react-router-dom;pnpm)。

---

## 输出(交付物)

- **修改**:`web/src/routes/UploadPage.tsx`(加标签控件 + 资料复现入口面板;现有 `.zip` dropzone/status 包到「工程导览」标签下,逻辑字节不变;外层 section aria-label 改中性)。
- **新增**:`web/scripts/task505-smoke.mjs`(冒烟,仿 `task504-smoke.mjs`)。
- **新增(若需)**:`web/src/routes/upload/EntryTabs.tsx`(纯 UI 标签控件,可选 — `UploadPage` 近 300 行则抽,按 § 变更 #10 contract)。
- **小增量改**:`web/src/styles/upload.css`(标签布局类 + `:focus-visible`,用现有 token)、`web/package.json`(加 `smoke:task505` script,向后兼容)。
- **卡入仓**:`docs/tasks/task-505-home-entry-tabs-v0_2.md`(本 PR)。
- **不新增后端代码、不改后端契约/schema/DB;不加新路由;不碰 `docs/03_TASK_INDEX.md`**(索引收尾单独 PR)。

---

## 上游契约(stand-alone 给 R1 — 自包含,实测自 origin/main `526ce09`)

### A. 首页现状(本任在此之上加标签,既有行为不改;R6 已逐条 RAW 核)

- **路由(`App.tsx`)**:`index → <UploadPage/>`;`paper → <PaperUploadPage/>`;`paper/:paperId → <PaperResultPage/>`;`view/:projectId → OverviewPage`;`view/:projectId/chat → ChatPage`。`Layout` 仅 `<Outlet/>`。
- **`UploadPage`(`/`)结构**:`.upload-content` 两列网格 = 左栏 `.upload-copy`(`<h1>` MXA TUTOR + tagline + `.upload-hero-note` 资料入口口径三段)+ 右栏 460px(上传区,外层 `<section aria-label="上传 MATLAB 工程">`)。背景 = `UploadScene`(**非** `PanoramaScene`)。
- **右栏上传区现状**:`useReducer` 管 `idle/dragging/uploading/parsing/failed`;`busy = uploading||parsing` 时渲染 `UploadStatusCard`,否则 `UploadDropzone`(accept `.zip`);`useParseStatusPolling(projectId, status==="parsing", cbs)` 轮询,parse 成功 `navigate("/view/${projectId}")`,失败置 `failed`。拖拽/进度/取消/`validateZip` 一整套既有逻辑。
- **`/paper` 入口现状**:`PaperUploadPage` 独立页(自挂 `PanoramaScene` + `PaperDropzone`),**首页无任何链接指向它**。

### B. 现有设计系统(复用,不另起;实测自 `web/`,含 R6 P2-1 修正)

- **token(`index.css`)**:`--color-concrete:#2c2c2c` / `--color-ite:#e8e4de` / `--color-rebar:#8b8680` / `--color-formwork:#3a3a3a` / `--color-signal:#e85d3a` / `--color-signal-dim:#c44d2e` / …;字体 `--font-display`(IBM Plex Sans + Noto Sans SC)/ `--font-mono`(IBM Plex Mono)。全局 `*{border-radius:0!important}`。
- **可复用 class(真实存在)**:`.brutal-panel`(2px rebar 边 + formwork 底)、`.section-kicker`(signal/mono/大写)、`.text-command`(下划线命令式按钮,signal 下划线)、`.upload-content`、`.upload-dropzone`/`.upload-dropzone__mark`、`.upload-status-card`。主按钮风格 = signal 实心 + 近黑字 + mono(参 TASK-504 卡 §B)。
- **注意(R6 P2-1)**:`.upload-copy` **无独立样式规则**(仅 `.upload-copy h1` 媒体查询),勿当通用可复用 class;它只是左栏容器。
- **注意(R6 P2-2)**:仓库**无全局 tab/button focus class**,新标签须自带 `.upload-entry-tab:focus-visible`,勿靠浏览器默认。
- `index.css` 已 `@import "./upload.css"` → 首页布局类全局可用。

---

## 范围(必须做)

1. 在右栏上传区**上方**加标签控件,两标签:`工程导览` / `资料复现`。**默认 active = `工程导览`**。
2. **工程导览** active:渲染现有上传区(`busy ? UploadStatusCard : UploadDropzone`),`useReducer` / `useParseStatusPolling` / 拖拽 / 进度 / 取消 / `validateZip` / 跳 `/view` **逻辑一字不改**,仅把这块包进该标签的 `tabpanel` 容器。
3. **资料复现** active:渲染 `tabpanel` 面板 = § 固定文案的引导句 + 主按钮「进入资料复现 →」,点击 `navigate("/paper")`。
4. **busy 硬不变量(变更 #2)**:`busy===true` 时 —— 资料复现 tab 禁用(`aria-disabled="true"`,键盘/点击均不可激活)、`activeTab` 强制保持 `engineering`、**不渲染资料复现面板**;工程导览 tab 保持 active(其下显示上传状态)。busy 只能从工程导览发起,故 busy 时必在该标签,parse 成功跳 `/view` 不会甩到资料 tab。
5. **完整 tab a11y(变更 #3)**:`<button type="button" role="tab">` + 稳定 `id`;`tabpanel` + `aria-labelledby`;active `tabIndex=0` / inactive `tabIndex=-1`;方向键(←/→)只在两 tab 间移动+激活、不滚页;Enter/Space 激活;焦点可见(`.upload-entry-tab:focus-visible`,signal ring)。外层 section aria-label 改中性「首页入口」。
6. **标签样式(变更 #9/#12)**:新增 `.upload-entry-tabs` / `.upload-entry-tab` / `.upload-entry-tab--active` / `.upload-entry-panel` / `.upload-paper-entry` + `.upload-entry-tab:focus-visible` 于 `upload.css`,**仅用现有 token**(active 用 signal 标识、mono 标签、硬直角);不新造颜色/字体。
7. 左栏:删 `.upload-hero-note` 免责段 + 标语改「工程导览 / 资料复现」(PM 拍,双审后视觉清理);现有 dropzone 文案(`拖拽工程压缩包` / `或点击选择 .zip 文件`)**不改**。
8. **冒烟(变更 #7)**:`web/scripts/task505-smoke.mjs` + `package.json` `smoke:task505`,最低覆盖见 § 验收冒烟项。

---

## 不做(红线 — 合并前逐条核 RAW)

- **不碰 `docs/03_TASK_INDEX.md`**(变更 #1):本 PR must-clean,索引收尾走合并后单独 docs-only PR;TASK-505 暂不在索引中为预期(Stage 0 勿停)。
- **不碰已合并的 `/paper`**:`PaperUploadPage` / `PaperDropzone` / `PaperResultPage` 字节不变;资料复现标签只 `navigate("/paper")`,**不在首页内联论文上传**。
- **不碰 `.zip` 上传流程**:`UploadDropzone` / `UploadStatusCard` / `useParseStatusPolling` / reducer 逻辑 / 跳 `/view` 字节不变,仅包一层 tabpanel(合并前 `git diff --exit-code` 逐文件核,见 § 验收)。
- **不碰后端 / schema / 契约**(`git diff --stat` 证 `api/` `core/` `features/` `adapters/` `schemas/` 全空)。
- **不加新路由**;标签是页内 `useState`,不进 URL。
- **不重写范围外现有文案**(本 PR 仅做 PM 拍板的左栏清理:删 `.upload-hero-note` 免责段 + 标语改「工程导览 / 资料复现」;dropzone 标签 verbatim;section aria-label 是 a11y 属性非可见文案,允许改中性)。
- **不另起样式语言**:复用现有 class + token,新增只是标签布局类;不新造颜色/字体 token。
- **不引测试框架**:冒烟扫描 + `lint`/`typecheck`/`build` + PM 实测(`smoke:task505` 是 node 脚本,非框架)。
- 文案**正式工程口径**,无 AI 腔、不口语化、不暗示「自动生成模型 / 打开即跑」。
- **不顺手加范围外功能**(不内联论文上传、不加第三标签、不把首页背景换 `PanoramaScene`、不加复制/导出等)。

---

## 固定文案(逐字一致;新元素与本次左栏清理锁死,范围外现有文案不改)

| 位置 | 文案 |
|---|---|
| 标签 1 / 标签 2 | `工程导览` / `资料复现` |
| 资料复现面板·引导句 | `上传论文 / 报告后，系统将生成复现路线图、参数对应说明与调参方向。该入口独立于工程 .zip 解析流程。` |
| 资料复现面板·主按钮 | `进入资料复现 →` |
| 工程导览·dropzone(现有,**不改**) | `拖拽工程压缩包` / `或点击选择 .zip 文件` |
| 左栏标语(本次改) | `工程导览 / 资料复现` |
| 左栏 `.upload-hero-note` | 删除,不留空壳 |

---

## 验收标准(命令以 Stage 0 `package.json` 实测为准;PowerShell 5.1)

- [ ] 落地 `/` → 上传区上方见两标签 `工程导览` / `资料复现`,**默认 active = `工程导览`**。
- [ ] **工程导览**标签下:`.zip` 上传**端到端无回归**(选/拖 `.zip` → 上传 → 解析 → 跳 `/view`),取消/进度/失败态如旧;TASK-402 冒烟仍绿。
- [ ] **资料复现**标签下:点「进入资料复现 →」→ 落到 `/paper`(`PaperUploadPage`)。
- [ ] **busy 不变量**:模拟 uploading/parsing → 资料复现 tab `aria-disabled`、键盘/点击不可切、面板不渲染、`activeTab` 仍 engineering。
- [ ] **完整 a11y**:`role=tablist/tab/tabpanel`、`aria-labelledby`、`aria-selected`、roving `tabIndex`(0/-1)、←/→ 仅切两 tab 不滚页、Enter/Space 激活、`:focus-visible` 可见;section aria-label = 「首页入口」。
- [ ] **未改文件字节核(变更 #6)**——逐条 exit code 0:
  ```powershell
  git diff --exit-code origin/main -- web/src/routes/upload/UploadDropzone.tsx
  git diff --exit-code origin/main -- web/src/routes/upload/UploadStatusCard.tsx
  git diff --exit-code origin/main -- web/src/routes/upload/useParseStatusPolling.ts
  git diff --exit-code origin/main -- web/src/routes/PaperUploadPage.tsx
  git diff --exit-code origin/main -- web/src/routes/PaperResultPage.tsx
  git diff --exit-code origin/main -- web/src/routes/paper/PaperDropzone.tsx
  git diff --exit-code origin/main -- web/src/components/scene/PanoramaScene.tsx
  git diff --exit-code origin/main -- web/src/routes/OverviewPage.tsx
  git diff --exit-code origin/main -- web/src/routes/ChatPage.tsx
  ```
- [ ] **范围/无后端/不碰索引**:`git diff --stat origin/main` 仅含 `UploadPage.tsx`(+ 可选 `EntryTabs.tsx`)+ `upload.css` + `web/scripts/task505-smoke.mjs` + `web/package.json` + 本卡;**不含** `api/`/`core/`/`features/`/`adapters/`/`schemas/` 与 `docs/03_TASK_INDEX.md`。
- [ ] **行数(变更 #5)**:`(Get-Content web/src/routes/UploadPage.tsx).Count` ≤ 300;若存在 `EntryTabs.tsx` 一并量,均 ≤ 300。
- [ ] **设计**:仅现有 token(grep 无新造颜色),全硬直角,复用 class;active 标签 signal 标识克制。
- [ ] **文案**:§ 固定文案逐字一致;左栏按 PM 拍板清理;范围外现有文案 verbatim。
- [ ] **冒烟 `smoke:task505` 绿**,最低覆盖:① `/` 默认 active 工程导览;② 存在资料复现 tab;③ 激活资料复现后出现「进入资料复现 →」且指向 `/paper`;④ dropzone 文案「拖拽工程压缩包」「或点击选择 .zip 文件」仍存在;⑤ busy 态用静态 grep 兜底(渲染分支含 `aria-disabled` / activeTab 守卫)。
- [ ] `pnpm lint` / `pnpm typecheck` / `pnpm build` 全绿。
- [ ] **PM 实测**:`/` → 切标签 → zip 上传仍通 → 资料复现 → 跳 `/paper`,视觉达标(截图**作为图片附件传入对话**)。

---

## Stage 0(Codex 实施前实地核查,PowerShell 5.1 兼容,勿用 `&&`)

```
git fetch origin
git rev-parse origin/main
```

预期 HEAD ≈ `526ce09` 或更新(**勿硬编旧值**)。逐项报 PASS/FAIL + 异常;任一与 §上游契约不符 → **停手报 PM**(决策 09/15:先诊断卡错还是 main 错,不盲改不盲过):

1. `git show origin/main:web/src/App.tsx` 路由与 §A 一致(`index → UploadPage`、`paper → PaperUploadPage` 存在)。
2. `git show origin/main:web/src/routes/UploadPage.tsx` 结构与 §A 一致(两列、`useReducer`、`UploadDropzone`/`UploadStatusCard`、`useParseStatusPolling`、跳 `/view`、外层 section aria-label `上传 MATLAB 工程`)。
3. `PaperUploadPage` / `PaperDropzone` / `PaperResultPage` 存在(资料复现入口跳转目标)。
4. `index.css` token + 全局 `border-radius:0` + `@import "./upload.css"` 在;§B 可复用 class 存在;确认**无独立 `.upload-copy {}`**、**无全局 tab/button focus class**(据此自带 `:focus-visible`)。
5. **`cat web/package.json`**:确认**无测试框架**、贴真实 scripts(`dev`/`build`/`lint`/`typecheck`/`preview`/`smoke:task402`/`smoke:task504`),据此回填验收命令 + 仿写 `task505-smoke.mjs`;确认加 `smoke:task505` 的最小改法(向后兼容)。
6. `(Get-Content web/src/routes/UploadPage.tsx).Count` 现值(判断是否需先抽 `EntryTabs`)。
7. **索引(变更 #1)**:`git show origin/main:docs/03_TASK_INDEX.md` —— 确认 **TASK-505 暂不在索引中 = 预期,不停手、不在本 PR 改索引**;`docs/03_TASK_INDEX.md` 列为 must-clean。
8. baseline 白名单(变更 #7/#8):PM 预放本卡 `docs/tasks/task-505-home-entry-tabs-v0_2.md`(git untracked = 预期 / 或 Codex 新增)+ `web/package.json` 列入允许 diff,勿停手。

---

## 完工三件套(决策 08)

- **PR 标题**:`TASK-505: 首页双线入口(资料复现入口露出)`
- **PR 正文**:对照 § 验收逐条勾选 + 首页两标签 + zip 上传不回归 + 跳 `/paper` 截图(PM 实测,**作为图片附件传入对话**)+ 明示无后端改动 + 不碰索引(`git diff --stat origin/main` 实证,决策 12 R6.1)。
- **commit 分段(建议 2–4)**:
  1. `feat(home): two-line entry tabs on upload page (工程导览 | 资料复现)`(含 busy 不变量 + a11y;若抽则带 `EntryTabs.tsx`)
  2. `style(home): entry tab styles + focus-visible (reuse concrete tokens)`
  3. `test(home): task505 smoke + package script`
  4. `docs(tasks): add task-505 card`
- **索引收尾**:**本 PR 不含**;合并后由架构师/PM 另起 docs-only PR 加 TASK-505 行 ✅ + 进度条(决策 07,代码 PR 与索引收尾分开)。

---

## 风险与注意点

- **包裹现有 `.zip` 流程最易引回归**:reducer / poll / navigate / `validateZip` 必须原样,仅多一层 tabpanel 条件渲染;合并前用 § 验收的 `git diff --exit-code` 逐红线文件核(exit 0)。
- `busy` 中切标签 / parse 成功跳 `/view` 的交互冲突,用「busy 硬不变量」消解(变更 #2)。
- 控制台不泄露异常细节 / 源码 / 敏感串(决策 11 精神);前端保持控制台干净。
- 单文件 ≤ 300 行(04):`UploadPage` 近限则抽 `EntryTabs`(按变更 #10 纯 UI contract),不先塞后返工。

## 估时

小改,**1 个工作日内**(标签控件 + 包裹现有上传 + 资料入口面板 + a11y + 样式 + 冒烟)。

## 给 Codex 的提示

- 先 Stage 0,后动手;沿用 `web/` 约定。
- 包裹现有上传区时**逻辑零改动**,只做条件渲染;别重构 reducer / poll。
- `EntryTabs`(若抽)= 纯 UI,按 § 变更 #10 contract,不持有上传逻辑。
- 复用现有 class + token;标签新类只加布局 + `:focus-visible`,不造颜色/字体。
- 资料复现标签 = `navigate("/paper")`,**不内联论文上传**。
- § 固定文案 verbatim(含锁定引导句);左栏按 PM 拍板清理;范围外现有文案不改。
- 测试命令以 `package.json` 实测为准,不引入新框架;`smoke:task505` 仿 `task504-smoke.mjs`。
- **不碰 `docs/03_TASK_INDEX.md`**;TASK-505 暂不在索引中是预期。

---

## 关联文档 / 决策

- **宪法/规范**:02 资料入口数据流、04 § 单文件上限 + 中文化错误;宪法「工程入口/资料入口二选一、不暗示自动生成模型」口径(资料复现引导句据此锁)。
- **决策**:06 / 07(索引:当前行 + 进度条算 Codex 必选,但 ✅ 与新行的收尾走合并后单独 PR;本卡据此 + 504/519 先例不碰索引)/ 08 / 09 + 15(实地核查、不符停手)/ 12 R6.1(完工按 `git diff --stat` 实证)/ 20(行尾保留)/ 22(编号 5xx = paper-to-model;本卡 505 = 让 paper 线在首页露出,虽改共享首页,归 paper-to-model 表面化)。
- **评审**:GPT R1(1 P0 + 5 P1 + 3 P2,条件通过)+ Codex R6(0 P0 + 2 P1 + 3 P2,实施可行)。
- **上游 Task**:TASK-402(首页/上传页)、TASK-504(`/paper`)。

## 自动升 R2 条件(Codex 实施期任一触发 → 停手报 PM,Claude 重起 R2)

1. Stage 0 发现 `UploadPage` / `App.tsx` 现状与 §A 不符(已被重构等)= 设计变更。
2. 需**改后端**(任何 `api/`/`core/`/`features/`/`adapters/`/`schemas/`)才能交付。
3. 需改 `/paper` 或 `.zip` 流程**行为**(非纯包裹)才能交付。
4. 范围蔓延(新路由 / 新契约 / 首页内联论文上传 / 第三标签 / 改背景场景 / 复制导出等)。
5. 需新造颜色 / 字体 token(应复用)。
6. 需引入测试框架才能满足验收(应改用冒烟 + lint/build + 实测)。

---

**版本**:v0.2(2026-06-27,并入 R1 + R6 双审采纳意见)
**作者**:Claude(架构师)
**前置基准**:origin/main `526ce09`(Stage 0 以 `git rev-parse origin/main` 最新为准,漂移停手报 PM)
**审批历史**:
- v0.1 起稿(2026-06-27)— 待双审
- v0.2(2026-06-27)— 并入 **GPT R1**(1 P0 + 5 P1 + 3 P2,"修完可派、不升 R2、不拆卡")+ **Codex R6**(0 上游 P0,2 P1 + 3 P2,"实施可行、不被迫改后端/既有逻辑")采纳意见;两审均条件通过;待 PM 拍板派 Codex 实现(Codex Stage 0 复核契约为实现门第一步)
