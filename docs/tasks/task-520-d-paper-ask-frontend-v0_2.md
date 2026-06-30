# TASK-520-D: Paper 追问 · 前端就地问答 UI + citation 接 B2 跳转(v0.2)

## 本版改动(v0.1 → v0.2;均来自双审 R1(GPT)+ R6(Codex),无新产品决定)
- [R6] 类型名修正:web 里置信度类型叫 `Confidence`(值 "high"|"medium"|"low"),不是 core 名 `ConfidenceValue`;`PaperAskCitation.excerpt` 是 `string | null` **必填可空**,非 optional。接口契约段已改。
- [R1-P1-5 + R6-3] 出处徽标改用新建轻量 `CitationChip`:现有 SourceBadge props 只有 `{ kind }`、文案硬编码、不收 onClick/label/excerpt/target,无法直接承载 citation。CitationChip 复用 `.paper-source-badge` 样式;source_kind 映射 `document_extracted→document_extracted`、`user_supplied→user_supplied_resolved`;DOM 解析不到只改外壳为弱化不可点,**不得**把合法 citation 渲成 `missing_unresolved`。
- [R1-P1-4 + R6-4] 固定面板布局定向 + 硬不变量:**不走顶部常驻**(打穿现状 scroll-margin)。桌面右侧 reserved dock + sticky;移动 / 窄屏底部 fixed compact + 页面 padding-bottom。**硬不变量:citation 跳转后目标完整 / 主要可见、不得被面板遮挡;桌面 + 移动都截图验证。**
- [R1-P1-1] 降级答截图矩阵补到 **4 个 fallback_reason 全覆盖**;明确 `citation_target_unresolved` 是**后端 200 fallback**,与前端 DOM 解析不到的不可点 chip 是两回事。
- [R1-P1-2] 调用层错误措辞改准:是「调用层 HTTP 错误 / 非 200」= 429 / 502 / 503 / 504(429 不是 5xx),429 也归可重试报错。
- [R1-P1-3] 加载态防并发 / 防 stale:请求中禁提交;若允许编辑输入,用 requestId / AbortController 防旧请求覆盖新答;retry 只重试最后一次已提交问题。
- [R1 §5] stateless 收紧:`session_id` 不进 localStorage / URL / history store;组件内若存仅作当前挂载周期相关性,不作会话记忆展示。
- [R1 §4] 降级答 4 句文案定稿(见下「降级答文案」)。
- [R6-5] 真 DOM 还有可选 `paper-equations` 区块,**它不是 SectionTarget**;面板挂点不得给会进 SectionNav / resolver 的 section id。
- [R6] 新增 `smoke:task520d`(同 520b1/b2 静态 smoke 风格)。
- 基线 HEAD 更新为 live `8467ea9`(418bb02→8467ea9 仅新增 520-C 卡归档,消费件未动,D-prep 事实仍成立)。

## 状态
🔲 未开始(v0.2 已并双审 P1,待派 Codex 实现)

## 上下文
追问子线第四张落地卡。520-A 契约 / B1 锚点 / B2 跳转高亮 resolver / C 后端 ask 端点均已合并 origin/main(live `8467ea9`)。D 把这套拼成用户能用的界面:PaperResultPage 上放常驻问答面板 → 调 `postPaperAsk` → 渲染回答 + 置信度 + 建议追问 → 回答下挂可点出处 chip,点击接 B2 `scrollToCitationTarget`(滚 + 高亮)→ 解析不到 DOM 渲不可点 → 加载 / 降级 / 报错 / 输入校验各态体面。**纯前端,只消费 C 接口 + B2 resolver,不碰后端 / schema / 契约 / 已合并产物。** v0 无状态。

**(产品决定,PM 已拍)** 问答面板放用户容易触达、不随页面滚动被滚走;点击出处跳转时,正文在面板下方滚动 + 高亮,面板与回答保持可见。**(落地)** 经 R6 真 DOM 核,顶部常驻会遮跳转落点 → 桌面右侧常驻 dock、移动底部常驻 compact(同样不滚走、不挡跳转)。

## 输入(前置依赖)
- 已完成:TASK-520-A / B1 / B2 / C,均合并 origin/main(live `8467ea9`)。
- 必读:01 / 02 / 04 / 05;520-A 契约定稿;本卡接口契约段。
- 可消费件(R6 @ `8467ea9` 实证,以实现为准):
  - `web/src/lib/paperApi.ts`:`postPaperAsk(paperId, request)`(POST `/api/v1/papers/{paper_id}/ask`)。
  - `web/src/lib/paperTypes.ts`:`PaperAskRequest` / `PaperAskResponse` / `PaperAskCitation` / `PaperCitationTarget`;`EvidenceSource = "document_extracted" | "user_supplied"`;置信度类型 `Confidence`("high"|"medium"|"low")。
  - `web/src/routes/paper/anchorRegistry.ts`:`resolveCitationTargetElement(target): HTMLElement | null`、`scrollToCitationTarget(target)`(解析不到 return null;否则滚最近 `.paper-equation-item` / `.paper-param-row` / `.paper-section` + 瞬时高亮)。
  - `web/src/routes/paper/SourceBadge.tsx`:props 仅 `{ kind: SourceBadgeKind }`,kind = document_extracted | user_supplied_resolved | missing_unresolved,文案硬编码;**不可直接承载 citation**。
  - `web/src/components/ui/GlassCard.tsx`(children + className)、`web/src/routes/paper/TuningPanel.tsx`(textarea + paper-primary-button,仿密度)。
  - `web/src/styles/paper.css`:paper-copy / secondary / readable-card / primary-button / source-badge / anchor-highlight / scroll-margin-top;scroll-margin-top 现值——桌面 `.paper-section`/equation/param 36px;移动(≤980px)equation/param 112px、`.paper-section` 仍 36px。
  - `web/src/routes/PaperResultPage.tsx`:SectionNav + .paper-shell + PaperHeader + 正文区块(含可选 paper-equations,**非 SectionTarget**)。
  - TASK-403 chat 页降级语义:FallbackBanner + 「依据」区 + CitationCard(借语义,实现可不同)。

## 输出(交付物)
- 新增前端组件:`PaperAskPanel`(就地提问 + 回答 + 出处 + 各态)+ 轻量 `CitationChip`,挂进 PaperResultPage。组件拆分 / 状态管理 / hook 由实现定。
- 复用 GlassCard / `.paper-source-badge` 样式 / paper.css token / B2 resolver / `postPaperAsk`;**不新造 token**。
- 新增 `smoke:task520d`(同 520b1/b2 静态 smoke 风格)。
- 截图(图片附件传进对话)覆盖验收每个关键态——合并门。
- 无新后端依赖 / 配置 / schema 改动。

## 范围(必须做)
- [ ] PaperHeader 后包一层 body / grid:左侧现有 target 区块,右侧(桌面)/ 底部(移动)放非-citation-target 的 `PaperAskPanel`;面板**不加**会进 SectionNav / resolver 的 section id。面板常驻、不随滚动滚走。
- [ ] 桌面右侧 reserved dock + sticky;移动 / 窄屏底部 fixed compact + 页面 padding-bottom。**不走顶部常驻**(打穿现状 scroll-margin)。**硬不变量:citation 跳转后目标完整 / 主要可见、不被面板遮挡;桌面 + 移动都验。**
- [ ] 输入仿 TuningPanel(textarea + paper-primary-button);空 → 提交不可用 + 行内提示;超 1000 字 → 拦下 + 提示(客户端先校验再调 `postPaperAsk`;`question` 是 string,TS 不表达 1..1000,前端自校)。
- [ ] 调 `postPaperAsk(paperId, { question, session_id })`;无状态:不存历史、不显示线程、不暗示记忆。**`session_id` 不进 localStorage / URL / history store**;组件内若存仅作当前挂载周期相关性。
- [ ] 加载态:请求中禁提交;若允许编辑输入,用 requestId / AbortController 防 stale 覆盖;retry 只重试最后一次已提交问题。
- [ ] 渲 answer + confidence(Confidence,复用现有置信度呈现语义)+ follow_up_suggestions(≤3,作可点 chip 填输入框,**不自动发送、不串历史**)。
- [ ] 每条 citation 渲 `CitationChip`:展示 label + excerpt(有则展示);**点击 → `scrollToCitationTarget(citation.target)`**;source_kind 映射 document_extracted→document_extracted、user_supplied→user_supplied_resolved。
- [ ] 可点 / 不可点走 B2:`resolveCitationTargetElement(citation.target)` 返回 null → CitationChip 渲弱化不可点外壳(非死链 / 不 fuzzy / 不 fallback,响应 200 正常);**不得**渲成 `missing_unresolved`。跳转**只**靠 target、**不缓存 source_id 跨请求**;**不自己 getElementById / scrollIntoView / location 兜底**。
- [ ] 降级答(`is_fallback === true`)→ 「证据不足」类样式(借 TASK-403 语义);按 4 个 fallback_reason 给定稿文案(见下)。
- [ ] 调用层 HTTP 错误 / 非 200(429 / 502 / 503 / 504)→ 可重试报错态(不伪造回答);与「200 fallback → 降级答」在 UI 上区分清楚。
- [ ] 砼核皮(#2c2c2c / 信号橙 #e85d3a / IBM Plex + 思源黑 / border-radius:0 / 半透玻璃);**不新造 token**;前端控制台干净;`pnpm typecheck` / lint / build 全绿;`smoke:task520d` 绿。

## 降级答文案(定稿,平实口吻,不命令用户)
- `insufficient_evidence`:当前资料里没有足够可核验的依据支撑这个回答,所以没有生成带出处的结论。
- `invalid_or_missing_citations`:这次回答生成的出处没有通过校验,因此没有作为正式回答展示。
- `citation_target_unresolved`:这次回答引用的依据没有稳定对应到当前结果页中的公式、参数或区块,因此没有作为正式回答展示。
- `out_of_scope`:这个问题超出了当前论文复现结果能可靠回答的范围。
- 末尾弱提示(非命令):可以试着围绕论文的公式、参数、建模步骤或调参建议来提问。

## 不做(明确排除)
- ❌ 多轮 / 历史 / 会话线程;UI 不暗示记忆。
- ❌ figure 出处可点(figure 引用只落 answer 正文、不可点)。
- ❌ 论文参数值逐行可点出处(现状无 per-row evidence;经 SectionTarget 或不可点)。
- ❌ 死链 / fuzzy / 近似匹配 / 前端兜底跳转;不自己 getElementById / scrollIntoView / location。
- ❌ 缓存 source_id 跨请求;拿 source_id 当跳转依据。
- ❌ 把合法 citation 渲成 `missing_unresolved`。
- ❌ 顶部常驻面板(本卡走右侧 dock / 底部)。
- ❌ 碰后端 / 改契约 / 改 schema / 改已合并产物(B1 / B2 / C / paperTypes PaperAsk 类型 / SourceBadge);要改 = PM 拍 + 审。
- ❌ 新造设计 token;引入新测试框架;follow-up chip 自动发送 / 串历史。

## 接口契约(只消费,不得重定义 / 改签名)
- `postPaperAsk(paperId: string, request: PaperAskRequest): Promise<PaperAskResponse>`(POST `/api/v1/papers/{paper_id}/ask`)。
- `PaperAskRequest { question: string(后端锁 1..1000,前端自校); session_id?: string | null }`。
- `PaperAskResponse { session_id; message_id; answer: string(后端锁 1..3000); confidence: Confidence("high"|"medium"|"low"); citations: PaperAskCitation[]; follow_up_suggestions: string[](≤3); is_fallback: boolean; fallback_reason: ("insufficient_evidence"|"invalid_or_missing_citations"|"citation_target_unresolved"|"out_of_scope") | null }`。
  - 不变量:`is_fallback` ⟺ confidence=="low" + citations==[] + fallback_reason!=null;非 fallback ⟺ citations≥1 且 fallback_reason==null。
- `PaperAskCitation { source_id: "^S[1-9][0-9]*$"(响应内临时,不得跨请求缓存); label; excerpt: string | null(document_extracted 有 1..300;user_supplied 为 null;**必填可空,非 optional**); source_kind: EvidenceSource("document_extracted"|"user_supplied"); target: PaperCitationTarget }`。
- `PaperCitationTarget` = SectionTarget(result_section ∈ 五区块,不含 paper-equations)| EquationTarget | PlanMappingParameterTarget | MissingPromptParameterTarget。
- `resolveCitationTargetElement(target): HTMLElement | null`;`scrollToCitationTarget(target)`(解析不到 return null;否则滚最近 `.paper-equation-item`/`.paper-param-row`/`.paper-section` + 瞬时高亮)。
- SourceBadge props = `{ kind: SourceBadgeKind }`(不收 onClick/label/excerpt/target)——citation 不用它,用 CitationChip。

## 验收标准(截图覆盖每个关键态 = 合并门;图片附件传进对话)
- [ ] 初始态:面板常驻、易触达、输入为空(桌面右 dock + 移动底部各一张)。
- [ ] 加载态。
- [ ] 回答 + 可点出处:chip 解析到 DOM;点一枚后正文滚动 + 目标高亮、面板与回答仍可见(含点击后高亮)。
- [ ] 回答含不可点出处:target 合法但当前页无 DOM(resolve→null)→ 弱化不可点 chip,响应 200。
- [ ] 降级答:`is_fallback`、无 citation、「证据不足」样式——**4 个 fallback_reason 文案全覆盖**(insufficient_evidence / invalid_or_missing_citations / citation_target_unresolved / out_of_scope);其中 citation_target_unresolved 须呈现为**后端 200 降级答**,不要与前端不可点 chip 混。
- [ ] 调用层报错:模拟 429 / 502 / 503 / 504 → 可重试报错态、无伪造答。
- [ ] 输入校验:空(提交不可用)+ 超 1000 字(拦下 + 提示)。
- [ ] 无状态:连问两次,UI 无历史线程、不暗示记忆。
- [ ] 固定 + 不遮挡:滚动页面面板不滚走;点出处后正文滚动 + 高亮、**跳转落点不被面板遮**(桌面 + 移动各验)。
- [ ] `pnpm typecheck` / lint / build 全绿;前端控制台干净;`smoke:task520d` 绿。
- [ ] 纯前端、零后端 / schema 改动(`git diff` 不含后端 / schema / 契约文件;若意外触及 paper schema → decision 13 全清单,本卡按不触及验收)。

## 风险与注意点
1. **固定面板 vs scroll-margin(已落定向,实现守不变量)**:不走顶部(打穿现状 scroll-margin:桌面 section/equation/param 36px;移动 equation/param 112px、section 仍 36px)。桌面右 dock / 移动底部不吃顶部 scroll-margin、无需协调。守硬不变量:跳转落点不被面板遮。
2. **CitationChip(已落)**:复用 `.paper-source-badge` 样式;source_kind 二值映射;不可点只改外壳。
3. **section 级高亮泛区**:B2 closest 对 section 目标会泛整块橙;真点击联调留意是否收成只高亮标题;若改属前端视觉微调、不动 B2。
4. **paper-equations 区块**:存在但**不是 SectionTarget**;面板挂点别给 section id;equation 出处走 EquationTarget(`.paper-equation-item`)不走 section。
5. **stateless 不暗示记忆**:session_id 不落本地;follow-up chip 填输入框不自动发;连问不显示线程。
6. **体验事实(已锁)**:摘要 / 公式 / 用户补充参数有可点出处;AI 生成文字本身 + 论文参数值逐行(无 per-row evidence)暂无可点出处。失败态截图覆盖「答有内容但出处不可点 / 降级答无 citation」。

## 估时
0.5–1 天(纯前端;接口 / resolver 就绪;主在状态机 + 右 dock / 底部布局 + 不遮挡验证 + CitationChip + smoke + 截图矩阵)。

## 给 Codex 的提示
- Stage 0 取 live origin/main HEAD(预期 `8467ea9`,以 fetch 后 live 为准),确认 A/B1/B2/C 在 + 消费件签名 / 类未变。
- 先解头号风险:桌面右 dock / 移动底部,真机滚动 + 真点一枚 citation 验跳转落点不被遮。
- 可点判定只用 `resolveCitationTargetElement`,跳转只用 `scrollToCitationTarget(target)`;**不自己 getElementById / scrollIntoView / location**。
- 调用层非 200(429/502/503/504)→ 可重试报错;200 fallback(读 is_fallback / fallback_reason)→ 降级答。
- 降级答用本卡定稿文案;CitationChip 复用 `.paper-source-badge` 样式、二值 source_kind 映射、不可点只改外壳。
- smoke:task520d 同 520b1/b2 风格:守 postPaperAsk / resolveCitationTargetElement / scrollToCitationTarget 消费、禁本地 getElementById/scrollIntoView/location 兜底、守 1000 校验 / fallback 文案 / CitationChip 不误用 SourceBadge / 挂点。
- 完工三件套(decision 08;改文本文件保留原始字节 / 行尾)+ 截图作图片附件传进对话覆盖每个关键态。
- 本机无 grep,用 git grep / rg / Select-String。
