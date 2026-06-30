# Case 01 — 电机短路类资料 → 模型搭建路线图

> **评测维**:material_to_plan
> **case_id**:`case_01_motor_short_circuit`
> **domain**:`motor_control`
> **样本来源**:决策 22 § 4.2 PoC 实测干净样本《同步发电机突然三相短路报告.docx》(21 段 / 0 表格 / 6 图片)

---

## 1. case 目的

测试 paper-to-model v0.1 副驾**稳交付层**能力(决策 22 § 1.1):

> 给定一份电机短路类学生实验报告(单主资料,docx 学生报告类),系统能否:
>
> 1. 抽取出 12 项电机参数 + 物理方程 + 物理含义讲解(PaperSpec 层)
> 2. 推断出 SimPowerSystems 库选型 + 关键 block 清单 + 参数对应表 + 子系统拆分建议(ModelGenerationPlan 层)
> 3. 给出 `.m` 数值计算骨架(尽力交付层)

**不测**:`.slx` 自动生成 / 仿真运行结果 / 收敛验证(对齐决策 22 § 1.1 不承诺层)。

---

## 2. 输入

`input/source_doc_stripped.md` — 同步发电机突然三相短路报告的**剥离版**:

- ✅ **保留**:任务陈述 / 12 项电机参数 / 数值计算公式 EQ-01 / 物理含义讲解 / Simulink 仿真任务陈述(只到"建立 Simulink 模型"为止)
- ❌ **剥离的内容**:
  - 工程决定段:`5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s / 1s 仿真时长`
  - 模型参数图片占位(标准同步发电机 / 变压器 / 初始化工具截图)
  - 结果段:`a 相 0.21s 短路冲击电流 9.103 (.slx) / 9.164 (.m) / 误差归因`

**剥离目的**:测系统能否独立从 12 项参数 + 公式推断这些工程决定;若 input 含工程决定段,LLM 直接"抄"就行,无法验证副驾稳交付层的真实能力。

**完整 docx 原文件**:由 PM 在本地维护,**不入仓**(本目录 input/ 不放 docx 原文件,仅放剥离版 .md);详顶层 `README.md` § 5 输入资料来源约定。

---

## 3. 期望输出(golden)

### 3.1 `golden/expected_paper_spec.json`

含 10 个字段:
- `paper_title`:论文标题(从剥离版第一段抽取)
- `paper_type`:`"report"`(学生实验报告)
- `domain`:`"motor_control"`(资料入口 6 类之一)
- `abstract`:对剥离版的摘要(系统应识别工况 / 方法 / 任务,1-1000 字)
- `documents` / `primary_document_id`:单文件身份为 `DOC-001`,主文献为空
- `equations`:1 个 EquationEntry(EQ-01 字面 = 论文公式)
- `parameter_table`:15 个 ParameterEntry,逐项对应论文第 2 段给出的 12 个电机参数 + PN/UN/fN(论文显式标的"额定"三项),全 `source: document_extracted` 且 `document_id: DOC-001`
- `figure_locations`:**空数组**(剥离版剥离了所有图片占位,系统不应"幻觉"出 figure)
- `pseudocode_blocks`:1 项,基于 EQ-01 的伪代码描述
- `evidence`:4 个 PaperEvidenceEntry,全 document_extracted,引用 S2 / S3 / S4 / S5 段,`document_id` 均为 `DOC-001`

**评分关注点**:Layer 2 的 **A1 字段完整 + A2 无幻觉(特别不能编造剥离版没有的内容,如不能输出 figure_locations 具体条目)+ E1 双源不变量**

### 3.2 `golden/expected_model_generation_plan.json`

仍含 9 个顶层字段;其中嵌套的 `PaperEvidenceEntry` 为 7 字段(含 `document_id`):
- `plan_id` / `paper_spec_id`:关联 ID
- `library_choice`:`SimPowerSystems`(决策 22 § 4.4 PoC 实测结论)
- `block_recommendations`:8 个核心 block(powergui / Synchronous Machine pu Standard / Three-Phase Fault / Three-Phase V-I Measurement / Three-Phase Series RLC Load / Three-Phase Transformer / Scope / Mux),每个含 block_type / purpose / paper_reference
- `parameter_mapping`:20 个映射条目(15 个直接对应 + 5 个工程推断:5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s / 1s)
- `subsystem_breakdown`:8 步搭建流程
- `m_script_skeleton`:基于 EQ-01 的 .m 代码骨架(约 30 行)
- `evidence`:3 个 PaperEvidenceEntry,全 document_extracted,引用核心论文段落,`document_id` 均为 `DOC-001`
- `build_steps`:golden sample 仍为 `null`;live run 自 TASK-507-B 起可生成非空结构化步骤,build_steps 指标留 TASK-509 接入

---

## 4. 评分关注维度(三层诊断栈口径)

详评分模板 `scoring_template.md`,本 case 关注点:

### Layer 1 — Outcome(必填)

| 标准 | 本 case 关注 |
|---|---|
| **O1 Plan 可执行性** | 主评维度。会用 Simulink 的工程师拿到 plan 能否搭出可用电机短路模型?SimPowerSystems 库 + 核心 block 齐 + 12 项电机参数对应清楚 + 8 步搭建流程可循 |
| O2 用户补充更新 | **N/A**(本 case 无用户补充流程) |

**Layer 1 全 Pass = 本 case 验收通过,不用看 Layer 2**。

### Layer 2 — Component 诊断(条件启动,Layer 1 非 Pass 时)

本 case 主要诊断目标:

| 组件 | 标准 | 本 case 关注 |
|---|---|---|
| A 抽取 | A1 字段完整 | 12 项电机参数 + EQ-01 公式 + 摘要全命中 |
| A 抽取 | A2 无幻觉 | **不输出 figure_locations 具体条目**(剥离版没图,输出即幻觉) |
| C 工程方案 | C1 库选对 | 应选 SimPowerSystems / Simscape Electrical / powerlib(同义,任一通过) |
| C 工程方案 | C2 关键 block 推对 | Synchronous Machine + Three-Phase Fault + powergui 至少齐 |
| C 工程方案 | C3 参数映射对 | 12 项电机 pu 参数 → Synchronous Machine block 槽位映射(语义对即可,具体槽位名可有版本差异) |
| D 代码骨架 | D1 .m 语法 | 字段非空时,覆盖 EQ-01 各分量 + subplot 绘图;空 = N/A |
| E 证据契约 | **E1 双源不变量(一票否决)** | 所有 evidence 满足两套不变量;**本 case 应全 document_extracted**(无用户补充) |

---

## 5. 测评步骤

详 `verification_method.md` § 1.1(人工对照骨架)。本 case 测评步骤摘要:

1. 读 `input/source_doc_stripped.md`
2. 读 `golden/expected_paper_spec.json` 和 `golden/expected_model_generation_plan.json`
3. 若有 actual 输出(PM / 测评人调用 LLM 跑出的 PaperSpec + ModelGenerationPlan JSON):按 `scoring_template.md` 三层栈口径,先填 Layer 1(O1 必填,O2 N/A),非 Pass 时启动 Layer 2
4. 若无 actual:仅做 golden 结构自检 + 双源不变量校验(verification_method § 3)+ JSON schema 合法性检查

---

## 6. 反 hallucination 红线

测评时特别注意(对应 Layer 2 的 **A2 无幻觉** 标准):

- ❌ actual 不应输出 `figure_locations` 数组的具体条目(剥离版没图)— 输出即 A2 Fail
- ❌ actual 的 `parameter_table` 不应出现剥离版中没有的参数(如"故障持续时间"等)— A2 Fail
- ❌ actual 的工程决定字段(5MW / 平衡节点 / ode15s / 1s)在剥离版中不存在,系统应作为**工程推断**给出,evidence 弱指向 S5 "建立 Simulink 模型"段;若 actual 把这些标 `document_extracted` 且引用一个论文里不存在的 excerpt(假造原文) → A2 严重 Fail,**同时触发 E1 一票否决**(假造的 excerpt 字面 = 双源不变量违反)
- ⚠️ actual 的 `library_choice = "SimPowerSystems"` 是 PoC 实测结论,但 LLM 推断时若给出"基础 Simulink"或"powerlib" 也算合理(SimPowerSystems = powerlib 旧称),C1 给 Partial / Pass;若给出 "Simscape Electrical Specialized Power Systems"(SimPowerSystems 新名)也算对,C1 Pass

---

**版本**:v0.1(2026-06-16,TASK-500 v0.2.1 交付)
