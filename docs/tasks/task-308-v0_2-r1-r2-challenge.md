# TASK-308 v0.2 challenge 清单(R1 轮)

**起稿日期**:2026-06-08
**架构师**:Claude(第二十四任)
**评审对象**:GPT 对 TASK-308 v0.1 的 R1 反馈(6 P0 + 5 P1 + 3 P2 共 14 条)
**工艺依据**:决策 12 双 AI 互审协议 v0.1
**配套文件**:`task-308-v0_2.md`(任务卡正文,不掺 challenge)

---

## § 1 同意清单(Claude 接受 GPT R1 共 9 条)

接受清单(逐条简短理由 + 实际修订位置):

| GPT R1 项 | 接受理由 | v0.2 修订位置 |
|---|---|---|
| **P0-1** prompt yaml 违宪 | 01 § 8 line 311 字面冲突;**Claude 反例 28**:凭印象禁 `core/prompts/` 没意识到本任要新增 | v0.2 § 范围 + 给 Codex 提示;允许新增 `core/prompts/simulation_explanation_pack.yaml` |
| **P0-3** 范围边界 + 03 索引 ✅/🔍 危险措辞 | 跨段同步漏(反例 30 同源);"Week 4 起步 ✅ 或 🔍" 违反决策 07 字面 | v0.2 § 范围 + § 验收 + § 给 Codex 提示;**仅 🔲 → 🔍** 不写 ✅;Codex 第一棒新增 🔲 行(沿用 PM 拍板细节 1 = A) |
| **P0-4** Stage 0 #LLM 时序冲突 | 第一棒不能跑 ExplanationService(它第二棒才实现);**Claude 反例 28**:没核查 #LLM 在哪一棒可执行 | v0.2 § Stage 0:#LLM 改 #LLM_EST(第一棒 token 预算估算);第二棒新增 Preflight #LLM_RUN |
| **P0-5** Validator 失败处理冲突 | 我自己 KPI 6 加硬反伤防御和正文 Codex 提示打架;GPT 拆三类失败清晰 | v0.2 § 接口契约 § Validator 段:三类失败明示(Recoverable LLM / Fatal impl-data / Pack acceptance) |
| **P0-6** payload dict[str, str] | 验收脚本 deterministic 判断需要 typed;**Claude 反例 28**:抄 GPT 二修稿 `dict[str, str]` 时没想验收 | v0.2 § 接口契约 § typed payload:`EndpointRef` + `SignalPathPayload` + `ParameterContextPayload`(详 § 3 互抓 G-1)|
| **P1-1** Stage 0 编号不连续 | 表格 #1-#5 + #OV + #LLM + #ATTR + #11-#14 中间 #6-#10 缺失 | v0.2 § Stage 0 表格:统一 12 项,不再写"20+ 检查点" |
| **P1-2** 自动指标"8 条"vs 表格 11 条 | 反例 30 同源 N+2 | v0.2 § 验收 § 文本验收:统一"自动指标 11 条" |
| **P1-3** features/explanation/ 顶层决策 | 需 D16 显式 + README | v0.2 § 决策摘要 D16 + § 接口契约 § README 模板 |
| **P1-5** 03 索引"Week 4 起步"危险 | 沿用 PM 细节 1 拍板:Codex 自补 🔲 但不擅自重排 Week 4 | v0.2 § 范围:Codex 自补 TASK-308 行到 Week 3 末或 Week 4 起步(按 03 索引现有结构决定);**不重排其他 Week 4 task** |

接受合计 **9 条**(占 14 条 = 64%)。

---

## § 2 分歧清单(Claude 对 GPT R1 challenge 5 条)

逐条:GPT 主张 / Claude 立场 / 决断建议。

### 分歧 1 — P0-2 untracked 产物的处理:**PR 描述 artifact** vs **Codex 报路径**

**GPT 主张**(R1 P0-2):
> "Stage 0 report / evidence_pack.json 作为 PR 描述附件或 PM 本地 artifact,不 commit"

**Claude challenge**:
- "PR 描述附件"是文字粘贴,不是文件;**4 份 .md / .json + evidence_pack.json + Stage 0 report 怎么作 PR 描述附件?** 字面无法落地
- 更落地的做法:**完全不挂 PR;Codex 报路径 + PR 描述贴 Stage 0 报告摘要文字**(简化结构 + 部分关键指标);完整 pack PM 本地查看

**双方都对的部分**:不入仓 + 不形成 commit

**双方分歧**:产物如何展示给 PM
- GPT:"PR 描述附件"(操作不明)
- Claude:"PR 描述贴 Stage 0 摘要 + Codex 报路径,完整 pack PM 本地"

**决断建议**:**采纳 Claude 立场**(更落地)。但若 PM 拍板"PR 描述附件可 attach 二进制",采纳 GPT 立场。**给 PM**:PM 见 § 4 决策点 Q-D1。

### 分歧 2 — P0-5 Validator 规则 6/8 "降级行为"是否需要 acceptance 守门

**GPT 主张**(R1 P0-5 修法):
> "规则 6/8:若 evidence_ids 存在但 kind 不足 → 自动 downgrade_to_uncertainty_boundary"

**Claude 加强**:
- 降级到 uncertainty_boundary **是个隐式损失**(本来要讲"为什么连接"降级成"不确定")
- 应在 PR 描述累计降级次数 + acceptance warning(沿用 GPT 自己 P2-3 思路:不确定 claim > 40% warning 不 fail)
- 若降级数量某工程 > 20% connection claim → acceptance warning(不 fail)
- 若降级数量某工程 > 50% connection claim → acceptance fail(Codex 回炉)

**双方都对的部分**:确定行为 + 不让 Codex 自选

**双方分歧**:**降级量化守门** GPT 没说;Claude 加层 acceptance 阈值

**决断建议**:**采纳 Claude 加强**(降级也要量化守门,否则 Validator 可能掩盖大量低质量 claim)。GPT 若反驳,见 R2 微审。

### 分歧 3 — P0-6 typed payload 类型范围(GPT 2 类 vs Claude 3 类)

**GPT 主张**(R1 P0-6):
> "至少改成 JSON 值类型 + EndpointRef + SignalPathPayload"

**Claude challenge / 互抓反例 28**(详 § 3 G-1):
- GPT 只给 2 类(连接相关:`EndpointRef` / `SignalPathPayload`)
- **GPT 自己漏 ParameterContextPayload** —— 但 acceptance #43"参数 claim 含 block + value + downstream/effect"同样需要 typed
- 不加 ParameterContextPayload → 验收 #43 / #45(修改建议含"改哪里+看哪里")同样 deterministic 判断不了

**双方都对的部分**:`dict[str, str]` 不够

**双方分歧**:typed 范围
- GPT:2 类(连接)
- Claude:3 类(连接 + 参数;详 v0.2 § 接口契约)

**决断建议**:**采纳 Claude 3 类**;这是 GPT 自己的反例 28(详 § 3),不是单纯 Claude 加层。

### 分歧 4 — P1-3 features/explanation/ 归属层级

**GPT 主张**(R1 P1-3):
> "可以成为独立 feature;加 D16 + features/explanation/README.md"

**Claude challenge**:
- 02 架构总览 features/ 层划分(ingest / overview / chat / payment)是按**用户场景**分,不是按**实现技术**分
- `features/explanation/` 是讲解层产物,**更精确归属是 features/overview/explanation/**(因为讲解是导览的深化,不是新用户场景)
- 但讲解层用 EvidenceBuilder(基于 ProjectGraph),功能依赖跨 chunker / overview / parser,**作为新顶层 feature 也有理由**

**双方都对的部分**:需 D16 显式决策 + README

**双方分歧**:顶层 vs overview/ 子模块
- GPT:顶层 `features/explanation/`
- Claude:可考虑 `features/overview/explanation/` 但**最终倾向沿用 GPT 顶层**(理由:跨依赖广 + GPT 自己也说"未来若合并入 overview 由后续重构处理")

**决断建议**:**采纳 GPT 顶层**;但 v0.2 D16 加一句"未来若合并入 overview/ 由后续重构处理"(GPT 自己说的)。**留 PM 拍板**:见 § 4 Q-D2(若 PM 觉得 features/overview/explanation/ 更对就改)。

### 分歧 5 — P2-2 overview_hint 强断言守门位置(Validator vs Renderer)

**GPT 主张**(R1 P2-2):
> "EvidenceKind=project_overview_field 不能单独支撑 parameter_reason / connection_logic / modification_advice 强断言"(Validator 规则 11)

**Claude 加强**:
- GPT 只在 Validator 层守门(拒绝 / 降级)
- Claude 加 Renderer 层守门:**若 claim 只有 1 个 evidence 且 kind=project_overview_field**,Renderer 强制加角标 `(基于项目导览描述)` + 推断标记
- 这样人工抽检时**直接看到**,不会被 Validator 静默拒绝

**双方都对的部分**:不能单独支撑

**双方分歧**:守门层
- GPT:Validator 拒绝 / 降级
- Claude:Validator 降级 + Renderer 显式角标提示

**决断建议**:**采纳 Claude 双层**;Validator 降级 + Renderer 显式提示,人工抽检透明度更高。

---

## § 3 互抓反例 28(Claude 抓 GPT R1 共 2 条 + 反例 30 共 1 条)

### G-1 反例 28:GPT § E1 高价值 block 白名单 5 大类 ~ 80 个 block type 凭印象写

**GPT R1 / 二修稿 § E1**:
- 5 大类 block type 清单(`Constant / Step / Ramp / ... / IGBT / Diode / ...`)
- 领域关键词补充(`PLL / PWM / dq / Park / DFIG / ...`)

**Claude 抓出**:
- GPT 没见过实际 4 工程数据(02_ee_b 多电平 / 01_ee_a DFIG 风电 / 03_ee_c 含 220kV-690V / 04_ee_d)
- 这 ~ 80 个 block type 是 GPT **凭"Simulink 通用工程知识"列**,未实地核查 4 工程的真实 block_type 分布
- 4 工程可能有特殊 block(如 `Three-Phase Source 30°` / `Active & Reactive Power` / `Powergui Discrete` 等)未在白名单
- 反向也可能:白名单某些 block(如 `MOSFET` / `XY Graph`)4 工程根本没用

**证据**(对 GPT 的 challenge):
- GPT R1 P0-4 严格抓 Claude 反例 28(Stage 0 #LLM 时序),但 GPT 自己 § E1 同样凭印象
- GPT R1 14 项里**没有自抓**白名单"凭印象"问题
- 这是 **GPT 自己的反例 28**

**修法**(v0.2 D17 + Stage 0 #4):
- v0.2 § 接口契约 § E1 白名单标"**初始建议清单,以 Codex Stage 0 #4 实测调整为准**"
- Codex Stage 0 #4 实测每路命中率;若白名单某条 4 工程 0 命中 → 报 PM 删
- 若 4 工程出现高频但白名单遗漏 block_type → 报 PM 加
- **不在 v0.2 任务卡里写死白名单为"权威清单"**,沿用反例 28 兜底纪律

### G-2 反例 28:GPT § E2 模糊命名 regex + "无工程语义"判断凭印象

**GPT R1 / 二修稿 § E2**:
- regex `^(constant|gain|sum|add|product|switch|scope|from|goto|mux|demux|...)\d*$`
- "无工程语义"判断"名字长度 ≤ 2 且非常见电气符号"

**Claude 抓出**:
- regex 类型词清单同样凭印象(可能漏 `Subsystem` / `Reference` / `Compare` 等)
- "常见电气符号"GPT 没明示什么是 → Codex 实施时凭印象判断
- 4 工程实测可能出现 `Vab / Iab / dq / abc / Vdc` 等 ≤ 2-3 字符的电气符号 → 但 GPT 的 normalize 规则未明示

**证据**:
- GPT § E4 项目级触发规则有数字(`ambiguous_block_ratio > 30%` 等),但 4 工程实际比例 GPT 未测
- 这些数字若 4 工程实测 < 5%(因为研究生工程命名规范),则规则永远不触发 → 等于无用
- 反之若实测 > 60%,则规则触发太频繁 → 大量"命名质量风险"段 → 文本看起来很空

**修法**(v0.2 D17 + Stage 0 #5):
- v0.2 § 接口契约 § E2 regex 标"草案规则,Codex Stage 0 #5 实测后 PM 拍板调整"
- "常见电气符号"清单明示(`Vab / Vbc / Vca / Iab / Ibc / Ica / Vdq / Idq / Vdc / Idc / Vd / Vq / Id / Iq / wr / wm / ...`)或留 PM 补
- 阈值 `30% / 20% / 5 个 Constant*` 标"建议值,实测调整"

### G-3 反例 30 同源:GPT R1 自身跨段同步漏

**GPT R1**:
- P0-2 指出 Claude v0.1 "6 commits / 拆 5" 跨段不一致
- 但 **GPT R1 P1-2** 自身指出"自动指标 8 条 / 11 条"也是跨段不一致(Claude v0.1 错)

**Claude 抓出**:
- GPT R1 14 项里**没有自抓**"R1 反馈本身是否跨段一致"
- 例如:GPT R1 P0-2 给的修订清单 "commit 18 / commit 19 / commit 20 / commit 21 / commit 22" 5 个 commit,但 P0-2 修法只列了 3 个 PR;**5 commits / 3 PR 比例对吗?** Claude 起 v0.2 时需重新核算
- GPT R1 P1-3 说"加 D16",但 GPT R1 没说本任决策摘要是不是有 D17(本任 R0 / R1 没明示)→ Claude 起 v0.2 时遇到 D17 反例 28 兜底无明文规则

**严重度**:**中**(GPT R1 本身没引入新错位,但跨段同步密度低;Claude 起 v0.2 需要 grep 跨段)

**修法**:Claude v0.2 起稿后跑 KPI 7 全文 grep 同步 commit 编号 / 自动指标条数 / D 决策编号 / 自查 KPI 编号 → 防 v0.2 反例 30 N+3

---

## § 4 给 PM 的实质决策点(R1 轮)

### Q-D1 — untracked 产物展示形态(分歧 1)

✅ **已拍 A**(v0.2 已按 Codex 报路径 + PR 描述贴 Stage 0 摘要 + 完整 pack PM 本地查看 写入)

### Q-D2 — features/explanation/ 顶层 vs overview/ 子模块(分歧 4)

✅ **已拍 A**(v0.2 已按顶层 features/explanation/ + D16 加未来合并预案 写入)

### Q-D3 — 决策 12 入仓时机

✅ **已拍 A**(R2 期间 PM 拍 Q-R2-1 = A 立刻入仓;详 § 6 R2 互抓清单)

---

## § 5 累积统计(本协议数据;R1 + R2 合并;v0.2.1 修订)

| 项目 | R1 数据 | R2 增量 | 累计 |
|---|:-:|:-:|:-:|
| GPT 总抓项数 | 14(6 P0 + 5 P1 + 3 P2) | 7(3 P0 + 3 P1 + F-1) | 21 |
| Claude 同意 | 9 (64%) | 7 (100%) | 16 |
| Claude 分歧 / 加强 | 5 (36%) | 0 | 5 |
| Claude 抓 GPT 反例 28 | 2 (G-1/G-2) | 0 | 2 |
| Claude 抓 GPT 反例 30 | 1 (G-3) | 0 | 1 |
| Claude 自抓协议自反 | 0 | 1(决策 12 P0-3) | 1 |
| GPT 抓 Claude 反例 28 | 3 (P0-1/4/6) | 2(P0-1 数据结构 / P0-2 sim_run kind) | 5 |
| GPT 抓 Claude 反例 30 | 2 (P0-2/P1-2) | 2(F-1 commits / P1-2 跨文件 / P1-1 hand-off) | 4(GPT R2 P1-1 计在内为 5) |
| **反例 28 互抓累积 K_28** | 5 | +2 | **7** |
| **反例 30 互抓累积 K_30** | 3 | +2 | **5** |
| **反例 31 协议自反 K_31** | 0 | +1 | **1** |
| **总互抓累积 K** | 8 | +5 | **K = 13** |

**升仪触发**(决策 12 § 4.1):K ≥ 10 已超 → **决策 12 v0.2 立刻入仓,PM 已拍 Q-R2-1 = A**

---

## § 6 R2 轮互抓清单(v0.2.1 新增)

### GPT R2 抓 Claude(7 项,全部成立)

| R2 项 | 类型 | 摘要 | v0.2.1 修订位置 |
|:-:|---|---|---|
| **P0-1** | 反例 28 | Validator 降级量化未设计数据结构(`original_claim_type / final_claim_type / downgrade_reason` 缺) | v0.2.1 § 3.5 ClaimValidationEvent schema + claim_validation_report.json 字段约束 |
| **P0-2** | 反例 28 | Validator 规则 10 引用未声明的 `simulation_run_result` kind | v0.2.1 规则 10 改述:不引未声明 kind;明示本任不新增 |
| **P0-3** | **反例 31 反面同源** | 决策 12 v0.1 R4 例外段 "必须保留至少 1 个分歧点" 诱导形式化分歧 | **Claude 自抓**;决策 12 v0.2 R4 改 "强制 challenge,不强制 disagreement" |
| **F-1** | 反例 30 | line 67 "5 commits 拆 3 PR" 但实际 3 commits(v0.2 残留) | v0.2.1 line 67:5 commits → 3 commits |
| **P1-1** | 反例 30 | PR hand-off 顺序"PM merge → 等评"与语义应"评 → merge"冲突 | v0.2.1 § Commit 拆分:ready → 评 → merge 顺序明示 |
| **P1-2** | 反例 30 | challenge 文件 § 4 Q-D1/Q-D2 仍标"待 PM 拍板",但 v0.2 已写入 | challenge 文件 § 4 改"已拍 A 写入"(本文件已修) |
| **P1-3** | 表述精简 | D16 应加引决议 04 "不是 understanding 顶层回潮" | v0.2.1 D16 加引(实地核查决议 04 内容,GPT 引用准确) |

### Claude R2 抓 GPT(0 项)

**Claude R2 跑完 grep 实测 + 决议 04 实地 view + 字段设计实用性核查后,未发现 GPT R2 凭印象 / 跨段同步漏**。

诚实记 0 抓,**不为决策 12 协议形式化对称硬凑**(沿用 GPT R2 P0-3 修法精神 "强制 challenge,不强制 disagreement")。

具体核查:
- GPT D2 `ClaimValidationEvent` 字段 `evidence_kind_set` 虽冗余但作审计 log 有用 — 非反例 28
- GPT 引决议 04 → Claude `view /mnt/project/20260601-04-understanding-not-top-level-feature.md` 全文 — 引用准确
- GPT F-1~F-5 5 项放行条件全部有实测依据 — 无凭印象

### Claude 自抓 1 项 ⭐⭐⭐

**决策 12 v0.1 R4 例外段协议自反 bug**(GPT R2 P0-3 抓到的形态,但**根因是 Claude 起协议时撞 KPI 6 加硬反伤的元层级形态**):

- 起决策 12 时,**Claude 想强制双 AI 不能完全自洽**,所以加了"必须保留至少 1 个分歧"硬规则
- 这条本身是**反例 31 反面同源**:为治理而治理加硬,诱导双 AI **凑分歧而非真分歧**
- 等于在写一份反"反例 31"协议时,撞了"反例 31 反面同源"
- **这是 Claude 自起协议的自反 bug**,不是 GPT 抓的 — 但 GPT R2 P0-3 触发了 Claude 自查
- **决策 12 v0.2 修法**:R4 改"强制 challenge,不强制 disagreement";允许 § 2 写"无方向性分歧",但必须说明 grep 哪些区域 + 为什么无分歧 + 是否抓到反例 28/30

---

## § 7 给 PM 的 R2 决策点

### Q-R2-1 — 决策 12 v0.2 入仓时机

✅ **已拍 A**(2026-06-08 PM 字面拍板)— 决策 12 v0.2 立刻入仓(与本任 v0.2.1 PR 并入或独立 PR,PM 拍板;沿用 v0.2.1 § 末尾"完工后 PM 单独动作 #4")

### Q-R2-2(若 PM 需)— 决策 12 v0.2 入仓 PR 形态

- **A.** 与 TASK-308 v0.2.1 同 PR 入仓(共 1 PR,内容多)
- **B.** 决策 12 v0.2 单独 PR(共 2 PR,各自精简)
- **C.** PM 自己 commit 决策 12(沿用 KPI-D PM 主体)

**Claude 建议:B**(单独 PR 工艺级独立性更高;但 PM 拍)

---

**版本**:v0.1(R1)→ v0.2(R1 + R2 合并)
**起稿**:Claude(第二十四任)
**配套**:`task-308-v0_2_1.md`(任务卡正文)+ `decision-12-dual-ai-review-protocol-v0_2.md`(决策 12 草案)
**协议依据**:决策 12 v0.2 § 3.1 R 轮文档拆分 + § 3.2 challenge 清单入仓 + § 4.3 KPI 9 自查清单(R1 + R2 各跑一次)
