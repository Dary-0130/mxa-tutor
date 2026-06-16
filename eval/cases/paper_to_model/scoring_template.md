# 评分模板 · scoring_template.md(v0.1 — 三层诊断栈)

> **本文档定义 paper-to-model 评测的"评什么 / 怎么打分 / 怎么倒推"**,与 `verification_method.md`(怎么验收)配套。
>
> **设计哲学对齐业界 2026 标准**:Confident AI 三层评测栈(`outcome → trajectory → component`)+ Watershed 多步骤 LLM 系统评测框架。**先看 outcome(用户能不能用)→ 不通过时看 component(哪个组件错)**,不一上来就细标准淹没测评人。

---

## 1. 评分总览

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1 ─ Outcome(必填,1 分钟主体)                     │
│   O1 / O2 两个标准,Pass / Partial / Fail               │
│                                                         │
│   ↓ 若 Layer 1 全 Pass → 本 case 验收通过,不用看下层  │
│   ↓ 若 Layer 1 任一非 Pass → 启动 Layer 2              │
├─────────────────────────────────────────────────────────┤
│ Layer 2 ─ Component 诊断(条件启动)                    │
│   5 大类 10 标准(A 抽取 / B 缺失识别 / C 工程方案 /    │
│   D 代码骨架 / E 证据契约)                              │
│   每个 ❌ 加 [Origin / Inherited] 标签 → 解决上游污染   │
├─────────────────────────────────────────────────────────┤
│ Layer 3 ─ Trajectory(留 TASK-501 后做,本任不做)       │
│   trace 中间步骤 / service 内部状态 / retry 次数        │
└─────────────────────────────────────────────────────────┘
```

**分层启动**:Outcome 全 Pass = 系统这个 case 跑通,本 case 验收完毕。Outcome 任一非 Pass = 启动 Component 诊断,定位是哪个组件出问题。

**绝大多数情况下,测评人只需要花 1 分钟填 Layer 1。只有出问题时才往下看 Layer 2(再加 2-3 分钟)。**

---

## 2. 三档评分约定

每个标准用 **Pass / Partial / Fail** 三档,**不用 0-5 分**(对齐业界 atomic rubric 原则,但保留"程度"信号):

| 档位 | 含义 | 示例 |
|---|---|---|
| ✅ **Pass** | 完全符合期望,无明显问题 | 12 项参数全抽到 |
| 🟡 **Partial** | 大致符合但有偏差,不影响主功能 | 12 项参数抽到 10 个,漏 2 个非关键参数 |
| ❌ **Fail** | 关键缺失或严重错误,影响主功能 | 12 项参数只抽到 5 个;或抽出来的全错 |

**为什么三档而不是 Pass/Fail 二档**:我们的标准没法完全 atomic(如"参数表抽对了吗"必有"对了 8/12"的情况),纯二档会丢"程度"信号。三档仍能 1 分钟扫完,但保留诊断信号。

---

## 3. Layer 1 — Outcome(必填)

> **评什么**:用户视角的端到端可用性。**不评 schema 细节,只评"能不能用 / 好不好用"**。

### O1 — Plan 可执行性

**问题**:这份 ModelGenerationPlan 给一个会用 Simulink 的工程师,他能否照着搭出**可工作的模型**?

| 档位 | 判定指引 |
|---|---|
| ✅ Pass | 工程师能直接照 plan 搭出来,核心 block 齐 + 参数对应清楚 + 步骤合理 |
| 🟡 Partial | 工程师需要小补充 / 小修改才能搭出来(如某 block 漏配置 / 某步骤跳跃),但主体可用 |
| ❌ Fail | 工程师无法照 plan 搭出可用模型(库选错 / 关键 block 缺 / 步骤错乱) |

**仅本 case 适用**:material_to_plan/case_01 + missing_param/case_01 都评 O1。

### O2 — 用户补充后 Plan 正确更新

**问题**:用户为 MissingParameterPrompt 补充参数后,**plan 是否正确反映这些补充值**?用户补充的参数有没有正确标 `source: user_supplied`(不伪装成文档证据)?

| 档位 | 判定指引 |
|---|---|
| ✅ Pass | 用户补充的 6 个值全部正确写入 plan + 全部正确标 user_supplied |
| 🟡 Partial | 大多数补充值正确写入,1-2 处遗漏或标错来源,但主功能可用 |
| ❌ Fail | 用户补充未生效,或多处标错来源(把 user_supplied 伪装成 document_extracted) |

**仅 missing_param case 适用**。material_to_plan case 跳过 O2。

### Layer 1 评分卡(模板)

```
Case: ________________________
测评人: ________ 测评日期: ________
LLM 模型 / 版本(actual 来源): DeepSeek-V3 _________  ← v0.1 产品实际跑的是 DeepSeek

| 标准 | 判定 | 备注 |
|------|------|------|
| O1 Plan 可执行性 | ☐ Pass / ☐ Partial / ☐ Fail | |
| O2 用户补充更新(仅 missing_param) | ☐ Pass / ☐ Partial / ☐ Fail / ☐ N/A | |

判定: ☐ 本 case 验收通过(Layer 1 全 Pass)
      ☐ 启动 Layer 2 诊断(Layer 1 任一非 Pass)
```

---

## 4. Layer 2 — Component 诊断(条件启动)

> **启动条件**:Layer 1 任一标准 = Partial / Fail。
>
> **评什么**:定位是 paper-to-model pipeline 中哪个组件出问题 → 知道改哪个组件的 prompt / 逻辑。

### 4.1 系统组件清单(诊断目标)

paper-to-model pipeline 由 9 个组件串联(具体落地路径留 TASK-501,本表是诊断指引):

| # | 组件名 | 输入 → 输出 | 各学科变体差异 |
|---|---|---|---|
| 1 | **Extractor** 文档抽取 | docx 文本 → PaperSpec(参数表 / 公式 / 摘要 / 图占位) | 几乎无差异 |
| 2 | **MissingDetector** 缺失识别 | PaperSpec + 图占位 → MissingParameterPrompt | 各学科图里典型藏什么参数不同 |
| 3 | **LibrarySelector** 库选型 | domain → library_choice | **变体差异最大**(motor_control→SimPowerSystems / signal→DSP / 通信→Communications Toolbox) |
| 4 | **BlockRecommender** Block 推荐 | PaperSpec + 库 → block_recommendations | **变体差异大**(每学科 block 知识库不同) |
| 5 | **ParameterMapper** 参数映射 | 论文参数名 → 模型参数槽位名 | 中等差异(各学科命名约定不同) |
| 6 | **SubsystemPlanner** 拆分步骤 | block 列表 → 有序搭建步骤 | 小差异 |
| 7 | **MScriptDrafter** 代码骨架 | 公式 → MATLAB 代码 | 中等差异 |
| 8 | **EvidenceTagger** 证据 + 双源 | 横跨所有输出 → 每个 claim 配 evidence + source | **无学科差异**(产品架构层硬约束) |
| 9 | **UserSupplyMerger** 用户补充合并 | MissingPrompt + 用户填值 → updated plan | 无学科差异 |

**关键洞察**:**各学科共用同一组组件,只是组件内部变体不同**。用户反馈"motor_control case 不好用" → 不是要为 motor_control 重做整套评测,是要定位哪个组件的 motor_control 变体出问题。

### 4.2 组件依赖图(上游污染追溯)

```
Extractor (A) ─────────────────────┐
   │                                │
   ↓                                ↓
MissingDetector (B)           MScriptDrafter (D)
   │                                
   ↓                                
LibrarySelector / BlockRecommender / ParameterMapper / SubsystemPlanner (C)
   
EvidenceTagger (E1) ─── 横跨所有 ─── 拦在每个输出的 evidence 字段
UserSupplyMerger (E2) ─── 依赖 B + 用户输入
```

**追溯规则**:若 A ❌,大概率 B / C / D 也 ❌(上游污染);若 A ✅ 但 B ❌,则 B 是 [Origin]。

### 4.3 5 大类 10 标准

每个 ❌ / Partial 后必须标 **[Origin]**(本组件独立出错)或 **[Inherited]**(上游污染导致)。

#### A. 抽取(Extractor)

| 标准 | 判定指引 | Fail → 优化方向 |
|---|---|---|
| **A1** PaperSpec 字段抽取完整 | Pass = 所有论文显式给出的参数 / 公式 / 摘要全命中;Partial = 命中 ≥70%;Fail = 命中 <70% | Extractor prompt 加强字段识别(具体改哪段 prompt 由 TASK-501 落地后定位) |
| **A2** 无幻觉(没编造论文里没有的内容) | Pass = 零幻觉;Partial = 1 处可疑(如改写了原文表述);Fail = ≥2 处明显幻觉(编造参数 / 公式 / 引用) | Extractor prompt 加 "STRICT NO HALLUCINATION" 指令 + 后置 hallucination check |

#### B. 缺失识别(MissingDetector)

| 标准 | 判定指引 | Fail → 优化方向 |
|---|---|---|
| **B1** 该识别的缺失参数都识别到(recall) | Pass = recall ≥80%(对照 golden missing_prompts);Partial = 50-80%;Fail = <50% | MissingDetector prompt 加 "scan all figure placeholders" + 学科特定参数清单 |
| **B2** 不乱报缺(文档已给的不当缺失)(precision) | Pass = 100% precision;Partial = 1 处误报;Fail = ≥2 处误报 | MissingDetector 加"先查 parameter_table"前置过滤 |

#### C. 工程方案(LibrarySelector + BlockRecommender + ParameterMapper)

| 标准 | 判定指引 | Fail → 优化方向 |
|---|---|---|
| **C1** 库选对了(LibrarySelector) | Pass = 选 golden 库或合理别名(如 SimPowerSystems / powerlib / Simscape Electrical Specialized Power Systems);Partial = 选了相关库但非最佳;Fail = 选错(如 motor_control 选 "基础 Simulink") | LibrarySelector 的 domain → 库映射字典(留 TASK-501) |
| **C2** 关键 block 推对(BlockRecommender) | Pass = 覆盖 golden block ≥80%;Partial = 50-80%;Fail = <50% | BlockRecommender 的学科 block 知识库(留 TASK-501) |
| **C3** 论文参数 → 模型参数槽位映射对(ParameterMapper) | Pass = ≥90% 参数映射对;Partial = 70-90%;Fail = <70% | ParameterMapper 的参数名字典(各学科) |

#### D. 代码骨架(MScriptDrafter)

| 标准 | 判定指引 | Fail → 优化方向 |
|---|---|---|
| **D1** .m 骨架语法正确(若非空) | Pass = 解析器(TASK-103)通过无 error;Partial = ≤2 个 warning;Fail = syntax error;**N/A** = m_script_skeleton 为空(尽力交付层不交付) | MScriptDrafter prompt + 加 MATLAB 解析器回读守门 |

#### E. 证据契约(EvidenceTagger + UserSupplyMerger,**两条均一票否决**)

| 标准 | 判定指引 | Fail → 优化方向 |
|---|---|---|
| **E1** 所有 evidence 满足双源不变量 — **一票否决** | Pass = 全过(verification_method § 3 两套不变量);Fail = 任一不满足。**无 Partial 档**(契约层非黑即白) | EvidenceTagger schema validation(Pydantic validator,留 TASK-501) |
| **E2** 用户补充正确标 user_supplied — **一票否决** | Pass = 所有用户补充参数 source = user_supplied;Fail = 任一伪装成 document_extracted。**无 Partial 档** | UserSupplyMerger 的 source 标注规则 |

**E1 / E2 任一 Fail = 整 case Fail**,无论 Outcome / 其他组件如何,**这是产品架构层硬约束**(双源契约错乱会污染下游所有依赖参数源头追溯的能力)。

### 4.4 Layer 2 评分卡(模板)

```
Case: ________________________  ← 启动 Layer 2 的原因(O1 / O2 哪个非 Pass): ________________________

| # | 大类 | 标准 | 判定 | [Origin/Inherited] | 备注 |
|---|------|------|------|----|------|
| A1 | 抽取 | PaperSpec 字段完整 | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| A2 | 抽取 | 无幻觉 | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| B1 | 缺失识别 | 缺失参数 recall | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| B2 | 缺失识别 | 缺失参数 precision | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| C1 | 工程方案 | 库选对 | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| C2 | 工程方案 | 关键 block 推对 | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| C3 | 工程方案 | 参数映射对 | ☐ Pass / ☐ Partial / ☐ Fail | ☐ Origin / ☐ Inherited | |
| D1 | 代码骨架 | .m 语法 | ☐ Pass / ☐ Partial / ☐ Fail / ☐ N/A | ☐ Origin / ☐ Inherited / ☐ N/A | |
| E1 | 证据契约 | 双源不变量 | ☐ Pass / ☐ Fail(一票否决) | — | |
| E2 | 证据契约 | user_supplied 标对 | ☐ Pass / ☐ Fail(一票否决) | — | |
```

---

## 5. 倒推流程(协作模式)

**关键原则**:**LLM 是双角色 — DeepSeek 是被测 actor 不参与评测分析;Claude / GPT 是 reviewer 与人共同分析评分卡**。

### 5.1 v0.1(当前 — 人 + Claude/GPT 协作)

```
Step 1. 测评人填评分卡
        ├─ Layer 1 必填(1-2 分钟)
        └─ 若 Layer 1 任一非 Pass → Layer 2 填(再加 2-3 分钟)

Step 2. 倒推根因(人 + Claude/GPT 共同分析)
        ├─ 优先看 Layer 2 [Origin] ❌(本组件独立出错)
        ├─ [Inherited] ❌ 暂不直接改 → 上游修好后大概率自然修复
        ├─ 若有 E1 / E2 一票否决 → 立即定位到 EvidenceTagger / UserSupplyMerger,与其他组件解耦改
        └─ 输出"待优化组件清单"(组件名 + 失败模式 + 优化方向)

Step 3. PM / 架构师 + Claude / GPT 共同决定:
        ├─ 改哪个组件的 prompt 或逻辑(参考 § 4.3 表的"Fail → 优化方向"列)
        ├─ 拆 task(若涉及多组件改 → 拆给 TASK-501 后续 PR)
        └─ 重跑 case 验证修复(回到 Step 1)

Step 4. DeepSeek 角色:被测系统的 LLM 供应商,生产 actual outputs;**不参与评测分析**
```

**为什么 DeepSeek 不参与分析**:DeepSeek 是项目宪法 v3.1 / 决策 22 选定的生产环境 LLM 供应商,本质是被测系统的 actor。让被测 LLM 评测自己的输出会引入 self-preference bias(LLM-as-judge 已知失败模式)。Claude / GPT 作为外部 reviewer 客观性更强。

### 5.2 v0.2+(自动化路径)

```
v0.2(短期):
- Layer 1 Outcome:LLM-as-judge(Claude / GPT 看 actual + golden 自动打 Pass / Partial / Fail)
- Layer 2 Component:仍主要人工 + Claude/GPT 协作(待 LLM judge 在 Layer 1 校准后再扩到 Layer 2)
- 倒推:LLM 看评分结构化反馈,生成"prompt 优化建议",但不自动改 prompt

v0.3+(中期):
- Layer 1 + Layer 2 全自动 LLM-as-judge
- 倒推:Claude / GPT 看评分反馈直接 propose prompt diff,人审后应用
- 完全自动改 prompt(不经过人审)留更远

约束:无论自动化推进到哪一步,DeepSeek 始终是被测 actor,不参与评测分析
```

---

## 6. 单 case 验收口径(各 case 通过线)

不再用"X/30 分"或"80% 通过线"这种数字口径。**新口径是分层的**:

| 情况 | 单 case 验收判定 |
|---|---|
| Layer 1 全 Pass | ✅ 验收通过 |
| Layer 1 任一 Partial,Layer 2 启动后 E1 / E2 均 Pass,其他大类多数 Pass / Partial | 🟡 条件通过(建议改 [Origin] ❌ 组件后重跑) |
| Layer 1 任一 Fail | ❌ 不通过,启动 Layer 2 定位组件 |
| E1 / E2 任一 Fail(任何 Layer) | ❌ 一票否决,不通过(无论 Outcome 如何) |

### 6.1 跨 case 汇总

| Case | Layer 1 O1 | Layer 1 O2 | E1 / E2 一票否决? | 单 case 验收 |
|---|---|---|---|---|
| material_to_plan/case_01 | | (N/A) | | |
| missing_param/case_01 | | | | |

**整体门槛 5 通过标准**:两个 case 各自达到 ✅ 或 🟡 + 两个 case 均无 E1 / E2 一票否决。

---

## 7. 业界标准对齐(脚注)

本评分模板设计参考:

- **Confident AI(2026)**:三层评测栈 `outcome → trajectory → component`,"Use these levels as a diagnostic stack: outcome first, then path, then failing component"
- **Watershed(2025)**:property evals + correctness evals 双类;"先做 task-level eval 找失败,再做 component eval 找根因"
- **Hebbia(2026)**:Pass/Fail atomic rubric 原则(本任放宽为三档,保留"程度"信号)
- **RAFFLES(2025)**:多组件 pipeline 故障归因,引出 [Origin / Inherited] 标签机制
- **错误归因谬误**:气候话语 AFA 论文证明上游 gold feature 喂下游性能能 +12.7 点 → 上游污染严重影响下游评分,必须做追溯

---

**版本**:v0.1(2026-06-16,TASK-500 v0.2.1 交付;三层诊断栈版,替代 v0.1 之前的 6 维 0-5 分版本)
**作者**:架构师(接手第 44 任)
**对齐**:roadmap v2.1 § 8.1 v0.1 评测重点(原 6 维已重组为 Layer 2 的 A-E 5 大类)
