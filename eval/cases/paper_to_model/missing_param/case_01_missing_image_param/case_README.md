# Case 01 — 缺图片参数 → 用户补充 → 输出更新

> **评测维**:missing_param
> **case_id**:`case_01_missing_image_param`
> **domain**:`motor_control`
> **样本来源**:决策 22 § 4.2 PoC 实测样本《同步发电机突然三相短路报告.docx》(21 段 / 0 表格 / 6 图片;PoC 实测发现图片含关键参数但未被文本抽取)

---

## 1. case 目的

测试 paper-to-model v0.1 副驾**双源契约能力**(决策 22 § 4.8 + § 10.4 第 2 项门槛):

> 给定一份电机短路类资料,**图片中含关键参数但未被文本抽取**(v0.1 系统无 OCR),系统能否:
>
> 1. **识别缺失**:在 PaperSpec 抽取阶段,识别出"论文提及该参数但文本未给具体值",输出 `MissingParameterPrompt` 候选;判分按 R1a-pre / R1a-post / R2 / R3 / R4 / R5 死规则,不约束固定数量
> 2. **接受用户补充**:用户为每个 prompt 提供具体数值,系统接受 `user_supplied_value` / `user_supplied_unit`
> 3. **更新 plan + 标对双源**:用户补充后,`ModelGenerationPlan` 更新;补充的参数在 `parameter_mapping` 中 `source: user_supplied`,与文档证据 `source: document_extracted` **分开标注**
> 4. **遵守双源不变量**:补充的 evidence 三 locator 全 None + excerpt = None + missing_param_prompt_id 关联到具体 prompt;文档证据 evidence 三 locator ≥ 1 + excerpt 非空 + missing_param_prompt_id = None

**核心红线**:用户补充的参数**不许伪装成 document_extracted**(否则下游消费者无法溯源该参数到底来自论文还是用户,污染参数源头追溯能力)。

---

## 2. 输入

### 2.1 `input/source_doc_stripped.md`

**模拟 v0.1 系统从完整 docx 抽到的文本流**(v0.1 无 OCR,图片信息丢失):

- ✅ **保留**:所有 docx 文本内容(任务陈述 / 12 项参数 / 公式 / 物理含义 / Simulink 任务陈述 / 仿真配置文字段)
- ⚠️ **图片信息丢失**(图片位置以 `[FIG-0X: caption]` 占位提示 + 注释说明,模拟 v0.1 无 OCR 行为):
  - FIG-01:标准同步发电机模型参数(含 H 惯性时间常数 / F 摩擦因数等图片中独有的参数)
  - FIG-02:变压器参数(变比 / 漏阻抗 / 接线全在图)
  - FIG-03:电机初始化工具截图(文字仅给 a 相滞后电压 -4.43°,完整 α0 初相角等在图)
- ❌ **剥离的最终结果段**:`.slx` 9.103 / `.m` 9.164 / 误差归因 — 非 paper-to-plan 输入

### 2.2 `input/expected_missing_prompts.json`

系统**参考样例**中的 `MissingParameterPrompt`(供人工理解 case,不作为 evaluator 判分真值源):

| parameter_name | 缺失原因 | suggested_unit |
|---|---|---|
| 同步发电机惯性时间常数 H | FIG-01 图片中,文字未给 | s |
| 同步发电机摩擦因数 F | FIG-01 图片中 | pu |
| 变压器变比(原边/副边电压比) | FIG-02 图片中,文字未给任何变压器数值 | kV / kV |
| 变压器漏阻抗 X_T | FIG-02 图片中 | pu |
| 变压器接线方式(原边 / 副边连接组别) | FIG-02 图片中 | (无单位) |
| 电机初相角 α0 | FIG-03 初始化截图中(文字仅给 -4.43°) | rad |

**说明**:这些条目是 v0.1 阶段**架构师手工标定**的参考样例;TASK-503 v0.2.4 evaluator 不把该文件当判分真值源,缺失识别按 R1a-pre / R1a-post + R2 真值源 + R3/R4/R5 死规则自动判定,详见 `verification_method.md`。

### 2.3 `user_input/user_supplied_params.json`

用户为参考样例中的缺失参数提供补充值(本 case 模拟一位电气工程师在使用产品时按 prompt 填入的典型值):

| parameter_name | 补充值 | 单位 | 来源说明 |
|---|---|---|---|
| 同步发电机惯性时间常数 H | 3.5 | s | 200MW 汽轮发电机典型值 |
| 同步发电机摩擦因数 F | 0 | pu | SimPowerSystems block 默认 F=0 |
| 变压器变比(原边/副边电压比) | 13.8 / 230 | kV / kV | 电厂出口升压变压器,接 230 kV 输电网 |
| 变压器漏阻抗 X_T | 0.12 | pu | 200MW 等级升压变压器典型漏抗 |
| 变压器接线方式(原边 / 副边连接组别) | Yn / d11 | — | 标准电厂升压变压器接线 |
| 电机初相角 α0 | 1.5708 | rad | π/2,空载短路典型初值 |

---

## 3. 期望输出(golden)

### `golden/expected_updated_plan.json`

含 9 个字段的 `ModelGenerationPlan`(用户补充后的更新版本):

- `plan_id` / `paper_spec_id`:关联 ID
- `library_choice`:`SimPowerSystems`(同 material_to_plan case)
- `block_recommendations`:8 个核心 block(含 **Three-Phase Transformer (Two Windings)**,由用户补充变压器参数后激活)
- `parameter_mapping`:**26 个映射条目** = 15 个论文文字直接给的(`source: document_extracted`)+ 6 个用户补充的(`source: user_supplied`)+ 5 个工程配置(`source: document_extracted`,因 missing_param case 的剥离版保留了"5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s / 1s"文字段)
- `subsystem_breakdown`:9 步搭建流程(比 material_to_plan case 多一步变压器与初始化配置)
- `m_script_skeleton`:基于 EQ-01 + α0 = 1.5708 的 .m 代码骨架
- `evidence`:**9 个 PaperEvidenceEntry** = 3 个 document_extracted(指向论文核心段落:S2 参数 / S3 公式 / S5 仿真配置)+ 6 个 user_supplied(每个关联到参考样例中的用户补充参数;判分真值仍以 R2 truth source + actual 链路为准)

**评分重点**:本 case 测试 R1a-pre/R1a-post 缺失识别死规则 + R2 真值源(冲突 / 幻觉)+ R3 来源真实性一票否决 + R4 一对一基数 + R5 全链 canonical name 一致 + 更新后 plan 可执行性(O1 / O2)

---

## 4. 评分关注维度(三层诊断栈口径)

详评分模板 `scoring_template.md`,本 case 关注点:

### Layer 1 — Outcome(必填)

| 标准 | 本 case 关注 |
|---|---|
| **O1 Plan 可执行性** | 工程师拿到更新后的 plan(含变压器 + 同步机 H/F 等用户补充值)能否搭出可用模型? |
| **O2 用户补充更新**(本 case 核心) | 用户为 6 个 MISS prompt 补充的值是否正确写入 plan?是否全部正确标 `source: user_supplied`? |

**Layer 1 全 Pass = 本 case 验收通过,不用看 Layer 2**。

### Layer 2 — Component 诊断(条件启动,Layer 1 非 Pass 时)

本 case 主要诊断目标:

| 组件 | 标准 | 本 case 关注 |
|---|---|---|
| A 抽取 | A1 / A2 | 论文 12 项参数 + 公式 + 物理含义抽取完整,无幻觉(同 material_to_plan case) |
| **R1a 缺失识别**(本 case 核心) | **R1a-pre / R1a-post** | 图片参数候选与用户补充后链路必须按 evaluator 死规则通过;不约束固定 prompt 数量 |
| **R2 真值源**(本 case 核心) | **R2 conflict / hallucination** | 对照 `r2_truth_source/document_facts.json`,文档已显式给出的参数不应被误识别为缺失或伪造成用户补充 |
| C 工程方案 | C1 / C2 / C3 | 同 material_to_plan case;额外注意 Three-Phase Transformer block 应推出 |
| D 代码骨架 | D1 | 用用户补充的 α0 = 1.5708 而非默认 α0 = 0 |
| **R3 来源真实性**(本 case 核心) | **一票否决** | **本 case 关键测试点**:用户补充参数不许伪装成 document_extracted;文档明示参数不许伪装成 user_supplied |
| **R4/R5 绑定一致**(本 case 核心) | **R4 一对一基数 / R5 canonical name** | user_supplied mapping 与 prompts、updated_plan 全链参数名必须一致 |

---

## 5. 测评步骤

详 `verification_method.md` § 1.1。本 case 特殊步骤:

1. 读 `input/source_doc_stripped.md`
2. 读 `input/expected_missing_prompts.json`(仅参考样例,evaluator 不读)
3. 读 `user_input/user_supplied_params.json`(对照用户应如何补充)
4. 读 `golden/expected_updated_plan.json`(仅参考样例,evaluator 不读)
5. 若有 actual 输出:按 `scoring_template.md` 口径,先填 Layer 1(O1 + O2 都填),再对 missing case 必跑 R1a/R2/R3/R4/R5 五条死规则
6. **R3 来源真实性校验**(本 case 必跑):对 `actual_updated_plan.json` 的所有 evidence 数组逐项跑 verification_method § 3 的两套不变量校验;任一用户补充伪装成 document_extracted 或文档明示值伪装成 user_supplied → **R3 Fail 一票否决**

---

## 6. 反 hallucination 红线

测评时特别注意:
- ❌ **用户补充的参数不许标 `source: document_extracted`**(把 user_supplied 伪装成文档证据是双源契约最严重的违反)
- ❌ **文档明示的参数不许标 `source: user_supplied`**(把已经在文档第 2 段写明的 PN/UN/fN/12 项 pu 参数误判为缺失)
- ❌ actual 不应输出与 `r2_truth_source/document_facts.json` 冲突的"假缺失"(如把"故障持续时间"列为缺失 — 文档第 5 段写明 "0.2s 时发生三相短路",仅是单点时刻;持续时间默认为"故障后到仿真结束"是常识)
- ⚠️ 用户补充的具体数值可能与 golden 不一致(用户可填任意合理值);评分关注**双源标注正确性 + plan 接受用户值的能力**,不关注具体数值是否等于 golden(只要在物理合理范围内)

---

## 7. 输入资料来源约定(产品架构约束)

**输入 docx 不入 mxa-tutor repo**:paper-to-model 产品形态中,输入资料(PDF / docx)是用户在使用产品时从本地文件系统(D 盘 / 桌面等)选择上传的,**资料本身不进 repo**(类比 MCS 工程入口的 zip — zip 不入仓)。

因此:
- 本 case 的 `input/source_doc_stripped.md` 是**自包含的评测输入**(模拟 v0.1 系统从用户 docx 抽到的文本流 + 图片占位),不需要 docx 原文件即可独立完成评测
- **完整 docx 原文件**:由 PM 在本地维护(参见决策 22 § 4 PoC 实测样本《同步发电机突然三相短路报告.docx》),不入仓
- TASK-501 PaperPlanService 落地后的端到端自动评测,可由 PM 在本地把 docx 路径作为参数传入 eval 脚本;eval 脚本不依赖 docx 在仓内

---

**版本**:v0.1(2026-06-16,TASK-500 v0.2.1 交付)
