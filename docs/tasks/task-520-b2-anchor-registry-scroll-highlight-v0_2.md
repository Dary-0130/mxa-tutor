# TASK-520-B2:Paper 追问 · AnchorRegistry + 跳转/高亮(target→DOM 解析 + scrollIntoView + 瞬时高亮 + unresolved→null)

**版本**:v0.2(R1 + R6 双审通过,均无 P0;并入 5 处实施 / 验收精修 P1 + R6 移动端 scroll-margin;3 个设计决定双审同意 → 定稿可派)
**所属线**:paper-to-model · 追问子线(decision 22)
**前置**:520-A 契约 RFC v0.2 已合并 main(#140);520-B1 可见锚点 substrate 已合并 main(#141,squash → origin/main HEAD)。B2 复用 B1 的 `web/src/routes/paper/paperAnchors.ts`。
**现状基线**:R6 实测 origin/main HEAD = `e861fb4`(B1 squash);**派单后 Codex Stage 0 复核最新 HEAD,用 live 值**。

---

## 本版改动(v0.1 → v0.2,并审而来)

**[P0]**:无(两审皆无 P0)。

**[P1 — 已并入]**:
1. **删 A3「开发态日志诊断一句」歧义(R1 + R6 一致)**:与「前端运行时不新增 `console.*`」打架。改为 `el == null` 早返回 `null`,**不新增任何 runtime console 日志**;B2 的信号就是 resolve→null,诊断 / 计数 / UI 表达留 D(见 §A3 / 验收)。
2. **「五个 section DOM id」→「六个页面区块 DOM id,其中五个是 `SectionTarget`」(R1 + R6 一致)**:`paper-equations` 也是真实 DOM 区块,但不进 520-A `SectionTarget.result_section` 五枚举(见 §现状事实)。
3. **补 `closest()` TS 返回类型收窄(R1 + R6 一致)**:`closest()` 默认 `Element | null`;用 `el.closest<HTMLElement>(...)` 收窄,或把 `scrollToCitationTarget` 返回类型定 `Element | null`(见 §A3)。
4. **smoke null / fuzzy 守门结构化(R1 + R6 一致)**:纯关键词出现 / 不出现守不住;改成结构化断言(只允许 `getElementById(resolveCitationTargetAnchorId(...))`、`if (el === null) return null` 在 `scrollIntoView` 前、禁 `querySelector` 拼名字 / 禁 resolver 后非空断言 `!`)(见 §A5)。
5. **移动端 scroll-margin(R6 真 repo)**:移动导航是 `position:sticky;top:0` 顶部横栏(有 padding、窄屏可能换多行),36px 会被盖住。移动 `@media` 另给清横栏的更大值,Codex 按真实渲染高度取,跨断点最终核定留 D(见 §A4 / §C)。
6. **equation 单一来源守(R6)**:equation 锚走默认内联(决定 ①),smoke 同时守 resolver 字面 + B1 `EquationList` 字面(或继续跑 `smoke:task520b1`)防两处漂移(见 §A5)。

---

## 这张卡是什么 / 不是什么

- **是**:追问功能的前端「跳转机制 substrate」,纯前端。把「拿一个后端给的语义 citation target → 解析成当前页面真实 DOM → 平滑滚过去并瞬时高亮 → 解析不到返回 null」这套机制建出来。复用 B1 已挂好的锚点(`paper-eq-*` / `paper-param-map-*` / `paper-param-missing-*` / 五个 section id)和 `paperAnchors.ts` 的 id 生成 helper。
- **不是**:不接后端 ask 端点 / source_table / citation / LLM(C);不做问答 UI、不把 citation badge 接到点击(D);**不渲染「不可点 badge」**(那是 D 的 wiring,B2 只产出 resolve→null 信号);不引 `location.hash` / `window.location`;不做 fuzzy「猜最近行」;不改 B1 锚点形状 / 不改 B1 组件渲染行为;不补解析器抓图 / figure 锚。

**为什么单独成卡**:520-A 铁律 2「anchor(DOM)真值源在前端 AnchorRegistry」。B1 把目标 DOM 铺好,B2 把「语义 target → 真实 DOM → 滚 + 高亮 + 解析不到返 null」这层机制建出来,作为 D 接 citation 点击时直接调用的地基。B2 与 C(后端 ask)可并行,但「点 citation 真跳」联调在 D。

## 状态

✅ v0.2 双审通过(R1 + R6 均无 P0;3 个设计决定双审同意;5 处实施 / 验收精修 P1 + R6 移动端 scroll-margin 已并)→ 定稿,可派 Codex。纯前端 substrate,不动任何对外契约 / schema / 后端;不改 B1 已合组件行为(只新增 resolver 模块 + 给 `paperTypes.ts` 加 target 类型 + 给 `paper.css` 加高亮 / scroll-margin 规则 + 新 smoke)。

## 上下文 / 已锁口径(沿用,本卡不重开)

- **出处可点击是能力非承诺,两阶段两处理(520-A 铁律 3)**:后端阶段语义不合法 → 整体 fallback(C 的事);**前端阶段 target 合法但当前页面无 DOM → 不可点 badge,不 fallback、绝不死链、绝不 fuzzy 猜最近行**。B2 负责前端阶段「解析」这一半:resolve 不到就返回 `null`;「渲染成不可点 badge」是 D。
- **绝不 `location.hash`**(520-A §4 / B1 已守):不污染 URL;跳转一律 `scrollIntoView`,且只对解析到的真实元素调用。
- **参数类锚 id 唯一走 `paperAnchors.ts` 公共 helper**,B2 复用、不重写算法(520-A §4 / B1 §A3)。
- **砼核风皮**(#2c2c2c / 信号橙 `--color-signal` #e85d3a / `border-radius:0` / 半透玻璃);高亮用现有 token,**不新造 token**。
- **标准**:给朋友用要能见人。但 B2 这版无真实 citation 驱动(citation 由 C/D 提供),**可视验证天然有限**——验证策略见 §A5 + §★ 已双审定 ③。

## 现状事实(R6 实测 origin/main `e861fb4`,全部成立;派单时再核 live)

> 给 R1:你无 repo,以下为实测事实,按此审、勿假设其它。

- **六个页面区块 DOM id**(`PaperResultPage.tsx`):`paper-summary` / `paper-equations`(B1 新增,条件渲染)/ `paper-subsystems` / `paper-build-steps` / `paper-parameters` / `paper-tuning`。其中 **`paper-equations` 是 B1 的公式 UI 区,不属于** 520-A `SectionTarget.result_section` 的**五枚举**(公式定位靠 `EquationTarget`);**`SectionTarget` 只允许那五个**,resolver 不把 `paper-equations` 当 section 目标。
- **公式锚**(`EquationList.tsx`):每条渲染为 `<li id="paper-eq-${equation_id}" className="paper-equation-item">`,锚在 `<li.paper-equation-item>` 上。空 / 纯空白条已在 `PaperResultPage` 过滤(不渲染 → 该锚不存在 → resolve→null,由 D 处理)。**无 equation id 公共 helper**——B1 内联 `paper-eq-${equation.equation_id}`。
- **参数行锚**(`ParameterTable.tsx`,三型行 + 双锚):
  - 纯 mapping 行:`<div className="paper-param-row" id={mappingAnchorId}>`,`mappingAnchorId = makePlanMappingAnchorId(mappingIndex, paper_param_name, model_param_name)`。
  - mapping+prompt 合并行:行 id 仍是 `mappingAnchorId`;`promptAnchorId` 作为**零布局子锚**挂在最后一个 `<span role="cell">` 内:`<span id={promptAnchorId} className="paper-anchor-stub" aria-hidden="true" />`,`promptAnchorId = makeMissingPromptAnchorId(prompt_id)`。
  - missing-only 行:`<div className="paper-param-row" id={promptAnchorId}>`,无 stub。
  - 表头行:`<div className="paper-param-row paper-param-row--head">`,**无 id**(resolver 永不解析到它)。
- **`paperAnchors.ts` helper**:`makePlanMappingAnchorId(rowIndex, paperParamName, modelParamName) → paper-param-map-${rowIndex}-${hash}`(hash = FNV-1a 32-bit code-point → `toString(36)`,输入 `${paperParamName}|${modelParamName}`);`makeMissingPromptAnchorId(promptId) → paper-param-missing-${promptId}`。
- **CSS**(`web/src/styles/paper.css`):`.paper-section{scroll-margin-top:36px;margin-top:84px}`;`.paper-equation-item` 与 `.paper-param-row` **没有** scroll-margin-top;`.paper-anchor-stub{display:block;width:0;height:0;overflow:hidden;line-height:0}`(零尺寸);**无任何现有 highlight 规则**。
- **SectionNav**(`SectionNav.tsx` + CSS):桌面 `position:fixed;top:112px;left:…;width:150px`(**左侧固定栏,不压内容顶部**);`@media(max-width:980px)` 改 `position:sticky;top:0`(**移动端顶部 sticky 横栏**,有 padding、窄屏 nav 项可能换多行,会盖住 top:0 的元素)。
- **TS 类型**:`web/src/lib/paperTypes.ts` 手维护 paper 域类型;当前**无** `PaperCitationTarget` union(520-A §3 的语义 target TS 类型尚未落,§6.7 把它列在 C 的 schema 同步里)。

## 接口 / 契约对齐(520-A v0.2;B2 必守)

- **三层真值源(520-A §1)**:LLM 只给 source_id(不造 anchor);后端给语义 target;**前端 AnchorRegistry(= 本卡)是 DOM 真值源**,负责把语义 target 解析成当前页面 DOM。
- **target 种类与字段(520-A §3,B2 resolver 据此映射)**:
  - `SectionTarget`{`kind:"section"`, `result_section` ∈ 五区块} → DOM id = `result_section` 字面值。
  - `EquationTarget`{`kind:"equation"`, `equation_id`} → DOM id = `paper-eq-${equation_id}`。
  - `PlanMappingParameterTarget`{`kind:"parameter"`, `origin:"plan_mapping"`, `row_index`, `paper_param_name`, `model_param_name`} → DOM id = `makePlanMappingAnchorId(row_index, paper_param_name, model_param_name)`。
  - `MissingPromptParameterTarget`{`kind:"parameter"`, `origin:"missing_prompt"`, `prompt_id`, `parameter_name`} → DOM id = `makeMissingPromptAnchorId(prompt_id)`。
  - **不含** figure / spec_parameter / build_step / subsystem 细粒度跳(520-A §3)。
- **锚 id 形状(520-A §4)**:同上;参数类**必经 `paperAnchors.ts` helper**(不重写 hash)。
- **无锚不跳空 / 失败语义(520-A §4 / §5.3)**:resolver 解析不到 → 返回 `null`;调用方(本卡 scroll 函数)**不得**对 null `scrollIntoView` 或 `location.hash`;**不得** fuzzy 猜最近似行作用户可见跳转(最多由 D 拿到 null 后表达)。「渲染不可点 badge」是 D,不在本卡。
- **参数唯一键 = origin + row_index / prompt_id**(520-A §3):名字 / symbol 只作 label,B2 解析**不**用名字匹配(论文重复参数名 H/K/R/L 按名字会对错)。

---

## §A 范围(必须做)

### A1. 前端语义 target 类型(`web/src/lib/paperTypes.ts`,additive)
- 新增 `PaperCitationTarget` discriminated union TS 类型,**逐字镜像 520-A §3**(`SectionTarget` / `EquationTarget` / `PlanMappingParameterTarget` / `MissingPromptParameterTarget`;字段名 + `kind` / `origin` 判别值照 §3,**Codex 从 live 520-A §3 抄,不自创**)。
- 这一步把 520-A §6.7「target(discriminated union)」TS 义务**落在 B2**;C 起 schema 同步时只加 PaperAsk request/response/citation 类型,其 `citation.target` **引用本卡的 `PaperCitationTarget`**(B2↔C 协调,见 §★ 已双审定 ②)。
- additive:只加导出类型,不动 paperTypes.ts 现有任何类型。

### A2. target→DOM resolver(新模块,如 `web/src/routes/paper/anchorRegistry.ts`)
- `resolveCitationTargetAnchorId(target): string` —— 纯函数,按 §3 映射:`switch (target.kind)` 穷尽,parameter 再 `switch (target.origin)` 穷尽;参数类调 `paperAnchors` helper;equation 内联 `paper-eq-${target.equation_id}`(见 §★ 已双审定 ①);section 返回 `target.result_section`。
- `resolveCitationTargetElement(target): HTMLElement | null` —— **DOM 解析只经** `document.getElementById(resolveCitationTargetAnchorId(target))`;查不到返回 `null`(520-A §5.3)。**不用** `querySelector` / 任何按名字拼的 selector。
- 命名沿用「AnchorRegistry」概念,但实现是**无状态 resolver**(B1 锚点已直接在 DOM,现查 `getElementById` 即可,不需注册表式状态)。

### A3. scroll + 瞬时高亮(同模块)
- `scrollToCitationTarget(target): HTMLElement | null`(或返回 boolean / `Element | null`,见下):
  1. `el = resolveCitationTargetElement(target)`;`el === null` → **早返回 `null`,不滚、不跳、不 hash;本卡不新增任何 runtime `console.*` 日志**(B2 的产品信号就是 resolve→null;诊断 / 计数 / UI 表达留给 D 拿到 null 后做,见 §★ 已双审定 ③ / 验收)。
  2. 求**可见目标**:`const visibleTarget = el.closest<HTMLElement>(".paper-equation-item, .paper-param-row, .paper-section") ?? el;`
     —— `closest()` 默认 TS 推断为 `Element | null`,用泛型 `closest<HTMLElement>` 收窄(或把 `scrollToCitationTarget` 返回类型定为 `Element | null`);调用方只依赖 truthy/null,不依赖 HTMLElement 专属字段,避免临场 cast 自由发挥。
     —— 处理 B1 合并行的**零布局 stub**:missing_prompt 命中合并行时 `el` 是 `<span.paper-anchor-stub>`(零尺寸、aria-hidden,直接高亮看不见),`closest(".paper-param-row")` 取到其所在合并行,滚 + 高亮落在可见行上(见 §C)。对直接命中的 equation li / param-row / section,closest 取到自身,无副作用。
  3. **先清旧高亮**(移除上一个高亮元素的类),再 `visibleTarget.scrollIntoView({ behavior: "smooth", block: "start" })`(block 取值实施定,配 A4 的 scroll-margin)。
  4. 给 `visibleTarget` 加瞬时高亮类(A4),计时移除(或 `animationend` 移除);连续点同一目标要能重触发(移除→强制 reflow→重加,或等价)。
- **绝无** `location.hash` / `window.location`;**绝无** fuzzy / 名字匹配兜底跳转;**绝无**对 `getElementById` / resolve 结果的非空断言 `!`(防绕过 null 早返回)。

### A4. CSS(`web/src/styles/paper.css`,additive)
- 给 `.paper-equation-item` 和 `.paper-param-row` 加 `scroll-margin-top`:
  - **桌面基线 = `.paper-section` 现有 36px**(桌面导航是左侧 fixed 栏,不压内容顶,36px 够)。
  - **移动端必须在现有 `@media (max-width:980px)` 块里另给这两个目标更大的 `scroll-margin-top`**——移动导航是 `position:sticky;top:0` 顶部横栏(有 padding、窄屏可能换多行),36px 会让滚到的元素被横栏盖住。Codex 按移动断点**真实渲染的横栏高度**取值(留足换行余量 + 小 buffer),并在 PR body 报「量到的横栏高度 + 取的 scroll-margin 值」;**最终跨断点视觉核定留 D**(真 citation 点击时跨断点截图)。
- 新增瞬时高亮类(命名照现有风格,如 `.paper-anchor-highlight`):用 `--color-signal`(信号橙)做短促描边 / 背景闪一下后淡出(CSS `@keyframes`);`border-radius:0`(砼核风);**复用现有 token,不新造**。`@media (prefers-reduced-motion: reduce)` 下退化为无动画瞬时着色(可访问性,P2 可裁)。

### A5. smoke(`web/scripts/task520b2-smoke.mjs` + `package.json` `"smoke:task520b2"`)
照 `task508-smoke.mjs` / `task520b1-smoke.mjs` 静态守卫风格(读源码字符串断言);**结构化正向 + 负向**(两审一致:纯关键词出现 / 不出现守不住 null / fuzzy,要更结构化):
- **正向(该有)**:resolver 模块存在且导出 resolve 函数;DOM 解析**只经** `document.getElementById(resolveCitationTargetAnchorId(target))`;四类 target 映射存在(section→`result_section`;equation→出现 `paper-eq-` 字面;plan_mapping / missing_prompt→调 `makePlanMappingAnchorId` / `makeMissingPromptAnchorId` 且 import 自 `paperAnchors`);scroll 函数体里 **`if (el === null) return null`(或 `if (!el …) return`)早返回分支出现在 `scrollIntoView` 之前**;含 `closest(`、「先清旧高亮」逻辑、瞬时高亮类名;`paper.css` 含 `.paper-equation-item` / `.paper-param-row` 的 `scroll-margin-top`(桌面 + 移动 `@media`)与新高亮类。
- **负向(不该有 — 防越界 / 防死链 / 防绕 null)**:resolver 模块**禁** `location.hash` / `window.location`;**禁** `querySelector` / 任何按参数名拼 selector 查 DOM(`paper_param_name` / `model_param_name` **只允许**出现在 `makePlanMappingAnchorId(...)` 调用实参里,**不得**进 selector——故不能粗暴禁这两个词,要专禁「selector 里带名字」);**禁** resolver / `getElementById` 之后对结果的非空断言 `!`(防绕过 null 早返回)。
- **equation 单一来源守(R6)**:因 equation 锚走默认内联(§★ 已双审定 ①),smoke 同时查 resolver 里有 `paper-eq-` 字面 **且** B1 `EquationList.tsx` 仍有 `paper-eq-` 字面(或在 task520b2 套件里继续跑 `smoke:task520b1`),防两处内联漂移。
- 不跑功能 / 不渲染;behavioral 验证留 D(见 §★ 已双审定 ③)。

---

## ★ 已双审定的设计决定(R1 + R6 双审同意)

1. **equation 锚内联,不抽 helper(双审同意)**:resolver **内联** `paper-eq-${equation_id}`(对齐 B1 EquationList 内联;equation 锚是零逻辑常量字面、无 hash、无字段组合漂移;抽 helper 反要动已合 B1 文件、扩大纯 B2 substrate 的 diff 面)。**约束(R6)**:smoke 必须同时守 resolver 的 `paper-eq-` 字面 + B1 `EquationList` 的 `paper-eq-` 字面(或继续跑 `smoke:task520b1`),且默认路径下 `EquationList.tsx` / `paperAnchors.ts` 不出现在 diff(§A5 / §B 已含)。
2. **`PaperCitationTarget` TS 类型落 B2、C 引用(双审同意)**:B2 resolver 当前就需要 target union;作为 TS-only discriminated union 加到 `web/src/lib/paperTypes.ts`,不影响 Pydantic schema / Makefile drift 闸、不绕后端契约。字段名 / 判别值从 live 520-A §3 逐字抄;C 之后只补 PaperAsk request/response/citation 并引用该 target。边界干净:B2 产「前端 target 类型 + resolver substrate」,C 产「后端 ask DTO / source_table / citation 业务语义」,D 才 wiring UI 点击。
3. **验证仅静态 smoke + typecheck/lint/build 为合并门(双审有条件同意)**:B2 无真实 citation 驱动,真实点击→滚→高亮截图推到 D(D 把 citation badge 接到 `scrollToCitationTarget`、DOM unresolved 时渲不可点 badge)。**条件(两审)**:① 不进任何 shipped dev trigger;② 不用 console 诊断替代 null 信号(P1-1 已并);③ smoke 负向结构化守 hash / fuzzy / null 早返回 / 参数 helper 复用 / 非空断言(P1-4 已并)。可选:Codex 本地一次性 throwaway 验证(临时调一下看滚动 + 高亮,**提交前撤掉**,不入库),非合并必需。

---

## 不在本卡(明确排除)

- ❌ 后端 ask 端点 / source_table / citation / LLM(C);问答 UI / 把 citation badge 接到 onClick(D)。
- ❌ 渲染「不可点 badge」/ badge 文案(D;B2 只产 resolve→null 信号)。
- ❌ `location.hash` / `window.location` / fuzzy 猜最近行 / `querySelector` 拼名字。
- ❌ 改 B1 锚 id 形状 / 改 B1 组件渲染行为(EquationList / ParameterTable / SectionNav / PaperResultPage 渲染逻辑不动;B2 只新增 resolver / CSS / 类型 / smoke;equation helper 取默认则连 EquationList 都不碰)。
- ❌ figure 锚 / 图索引 / 补解析器抓图(走「丙」)。
- ❌ 重写 `paperAnchors` hash 算法(参数类必复用)。
- ❌ 任何持久化 / 跨请求缓存 source_id(520-A §2;跳转靠 target,不靠 source_id)。
- ❌ shipped dev trigger / window 暴露 resolver(§★ 已双审定 ③)。

## §B 验收标准

- [ ] resolver 对 520-A §3 四类 target 映射正确(section→`result_section` 字面;equation→`paper-eq-{id}`;plan_mapping→`makePlanMappingAnchorId`;missing_prompt→`makeMissingPromptAnchorId`);union 判别穷尽,`pnpm typecheck` 守得住。
- [ ] resolve 不到 → 返回 `null`,scroll 分支 `if (el === null) return null` 早返回(在 `scrollIntoView` 之前),不滚不 hash;DOM 解析**只经** `getElementById(resolveCitationTargetAnchorId(...))`,**无** `querySelector` / 按名字拼 selector / `location.hash` / `window.location` / fuzzy / resolver 后非空断言 `!`(结构化负向 smoke 守)。
- [ ] 合并行零布局 stub:scroll / 高亮经 `closest<HTMLElement>(...)` 落在可见的 `.paper-param-row`(不直接高亮 stub);直接命中类无副作用;`closest(".paper-param-row")` 不误命中表头 `.paper-param-row--head`(表头无锚、且是兄弟非祖先)。
- [ ] `.paper-equation-item` / `.paper-param-row` 有 `scroll-margin-top`:桌面 36px(同 section),**移动 `@media` 另给清横栏的更大值**(Codex 按真实横栏高度定,PR body 报量到的值);新高亮类用 `--color-signal` + `border-radius:0`、瞬时淡出、复用现有 token、连续触发可重放;旧高亮在新高亮前清理。
- [ ] `smoke:task520b2` 结构化正向 + 负向全绿(含 equation 双字面单一来源守 + null 早返回结构守);`pnpm typecheck` / `lint` / `build` 绿;前端运行时不新增 `console.*`(decision 11;smoke 脚本 console 同现有风格 OK)。
- [ ] **纯前端零对外契约 / schema / 后端改动**。验收贴:
  - `git diff --name-only origin/main -- api core features adapters schemas docs/06_OUTPUT_CONTRACTS.md Makefile` → **期望空**;
  - `git diff --stat origin/main` → 全量改动实证(只应在新 resolver 模块 + `web/src/lib/paperTypes.ts` + `web/src/styles/paper.css` + `web/scripts/...` + `web/package.json`;equation helper 取默认则**不应**出现 `EquationList.tsx` / `paperAnchors.ts`;实际 ≠ 卡范围 → 停手报架构师,decision 12 R6.1)。
- [ ] **验证策略按 §★ 已双审定 ③ 定稿**:这版合并门 = 静态 smoke + typecheck/lint/build;**无 shipped dev 触发器**;behavioral(点击→滚→高亮)可视验证在 D。

## §C 风险与注意点

- **合并行 stub 是零尺寸**(实测 `.paper-anchor-stub` width/height:0、aria-hidden):直接高亮看不见、直接 `scrollIntoView` 也无 scroll-margin 留白 → **必须 `closest` 到可见行**再滚 + 高亮(§A3)。这是 B1 双锚结构的直接后果(契约分类 ≠ DOM 行结构)。
- **`closest` 不误命中表头**:`.paper-param-row--head` 也带 `paper-param-row` 类,但表头**无锚 id**(resolver 不会解析到它)且是数据行的**兄弟非祖先**,故 `closest(".paper-param-row")` 从数据行元素往上只命中自身数据行。R6 已用真 DOM 核(表头 line 152、stub line 195)。
- **scroll-margin 跨断点**:桌面 36px(同 section,左侧 fixed 导航不压内容顶,够);**移动端 `@media(max-width:980px)` 必须另给更大值清 top:0 sticky 横栏**(横栏有 padding、窄屏可能换多行,36px 会被盖住),Codex 按真实渲染横栏高度取值;最终跨断点核定留 D(真点击截图)。
- **resolver 不做名字匹配**(520-A §3):参数靠 origin + row_index / prompt_id。
- **不引 `location.hash`**(520-A 铁律 / B1 已守):URL 不染;只对真实元素 `scrollIntoView`。
- **`paper-equations` 不是 SectionTarget**:它是 B1 公式 UI 区,section 跳的五个目标不含它;公式定位走 `EquationTarget`→`paper-eq-*`。resolver 别把 `paper-equations` 当 section 目标。
- **null 信号不靠 console**(P1-1):`el === null` 早返回即可;**不**加 runtime console 日志(与 decision 11「控制台干净」一致),诊断留 D。
- **字节 / 行尾**:动 `paper.css` / `paperTypes.ts` 等已存在文件保留原始字节(decision 08:补丁式编辑,禁 `read_text` / `write_text` / `sed -i`)。
- **B2 无驱动**:真实 citation 由 C/D 给;B2 这版不可能 end-to-end 点击验证,诚实对 PM 讲清(机制 + 守卫,真跳转效果 D 才显)。

## §D 给 Codex 的提示

- Stage 0 用 **live HEAD**(`git fetch` 后 `git rev-parse origin/main`,用 live 值;卡基线 `e861fb4` 供对照)。先基于 origin/main 起新分支(别用旧 B1 分支)。
- 纯前端;**不碰**后端 / schema / Makefile / docs/06。
- `PaperCitationTarget` 从 **live 520-A §3 逐字抄**(字段名 / 判别值),别凭卡转述;参数类 id 一律走 `paperAnchors` helper,**别重写 hash**;equation 取默认内联(见 §★ 已双审定 ①)。
- scroll / 高亮按 §A3:`if (el === null) return null` 早返回(在 `scrollIntoView` 前);`closest<HTMLElement>(...)` 取可见行处理合并行 stub;**无** `location.hash` / `window.location`;**无** fuzzy / `querySelector` 拼名字;resolver / `getElementById` 后**不**用非空断言 `!`;**不加 runtime console 日志**。
- scroll-margin:桌面 36px;**移动 `@media` 量真实 sticky 横栏高度取更大值**,PR body 报「量到的横栏高度 + 取的 scroll-margin 值」。
- smoke 结构化正向 + 负向(§A5),照 `task520b1-smoke.mjs` 风格;含 equation 双字面单一来源守 + null 早返回结构守。
- 改已存在文件保留原始字节(decision 08);前端运行时控制台干净(decision 11)。
- **索引(decision 07 / 08)**:`TASK-520` 整数行已 🔍。B2 完工后 520 仍未全完(C/D/E 在)→ **仍 🔍、计数不 +1**;索引收尾 = 更新 `TASK-520` 行**备注**(加 520-B2 ✅),保持 🔍;读真索引定收尾范围;代码 PR 与索引收尾 PR 分开走;预放的本卡定稿文件在实现 PR 里连代码入仓(Stage 0 白名单)。

## §E 后续依赖(本卡定稿后)

```
520-B2(本卡,跳转/高亮机制)
   └─► 520-D 前端问答 UI + citation wiring(把 citation badge 接到 onClick→scrollToCitationTarget;DOM 解析不到→渲染不可点 badge;此时才 end-to-end 点击 + 跨断点截图验证 scroll/高亮 + 移动端 scroll-margin 最终核定)
520-C 后端 ask 端点 可与 B2 并行起;C 的 PaperAsk citation TS 类型引用本卡的 PaperCitationTarget。
520-E hardening / 截图矩阵 最后。
```
