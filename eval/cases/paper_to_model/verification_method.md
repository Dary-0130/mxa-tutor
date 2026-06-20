# 验收方式说明 · verification_method.md

> **本文档定义 paper-to-model 评测样本包的"如何验收"**,与 `scoring_template.md`(评什么/怎么打分)配套。

---

## 1. 两个阶段的验收方式

### 1.1 TASK-500 / TASK-503 当前验收 — case 分流

**目的**:在 TASK-503 v0.2.4 evaluator 接管 missing case 判分后,**明确 golden 数据 / R2 真值源 / 评分约定 / 验收方式的职责边界**,避免门槛 5 降级为"TODO 骨架"或固定样例对拍。

**形式**:**case 分流验收**。具体步骤:

1. **missing_param/case_01**:TASK-503 v0.2.4 evaluator 全自动跑 R1a-pre / R1a-post / R2 / R3 / R4 / R5 五条死规则;`expected_missing_prompts.json` 与 `expected_updated_plan.json` 仅作参考样例,evaluator 不读
2. **material_to_plan/case_01**:保留人工 + 自动混合验收;自动 metrics 覆盖 A1 / C2 / C3 / D1 / E1 / R3,人工 spot-check 覆盖 A2 / C1
3. **读 case_README**:测评人理解本 case 评分关注点(见 case_README § 4)
4. **结构性自检**:对每个 golden JSON 跑 `python -m json.tool` 验证 JSON 合法;对 golden 中的 evidence 字段逐项验证双源不变量(详 § 3)
5. **对外口径自检**:本目录任何 .md / .json 不含"自动生成 .slx / 一键生成 / 完整仿真模型 / 模型成品"等表述

**本阶段验收通过标准**(不依赖 actual):
- [ ] 14 个文件齐全(README / verification_method / scoring_template + 两个 case 文件 + missing r2_truth_source 两文件)
- [ ] 所有 JSON 文件 `python -m json.tool` 通过
- [ ] golden 中每个 `PaperEvidenceEntry` 满足 task-500 v0.2.1 § 接口契约要点的两套不变量
- [ ] golden 字段名 / 类型 / Literal 取值与 06 § 12 字段表对齐(本阶段 06 § 12 也由本 chore 同步入仓)
- [ ] case_README 对每个 case 说明清晰(输入 / 期望输出 / 评分关注维度)
- [ ] 对外口径合规:本目录任何 .md / .json 不含"自动生成 .slx / 一键生成 / 完整仿真模型 / 模型成品"等表述

### 1.2 TASK-503 v0.2.4 evaluator 落地后 — 自动 evaluator

**目的**:实现端到端实跑评测,作为模型 / prompt 改动的回归守门。

**形式**:**`eval/run_paper_eval.py`**(具体脚本路径由 TASK-503 v0.2.4 拍板,本 chore 不写)。具体设计建议(留 TASK-503 参考):

1. **input 喂入**:读 `input/source_doc_stripped.md` → 调 PaperPlanService → 拿到 actual_paper_spec / actual_model_generation_plan / actual_missing_prompts / actual_updated_plan(按 case 类型)
2. **case-specific evaluator**:
   - **schema 校验**:actual JSON 必须通过 Pydantic 校验(`features/paper/paper_schemas.py`)
   - **字段填充率**:actual 必填字段覆盖率 ≥ 90%
   - **missing case**:R1a-pre / R1a-post / R2 / R3 / R4 / R5 五条死规则全自动;R2 对照 `r2_truth_source/document_facts.json`
   - **material case**:actual `parameter_table` / `block_recommendations` / `parameter_mapping` 等 list,与 golden 的 key field(`symbol` / `block_type` / `paper_param_name`)交集 / 召回率
3. **双源不变量校验**:对 actual 的所有 `evidence` 数组中每个 `PaperEvidenceEntry` 自动校验两套不变量(详 § 3)
4. **Outcome vs Component 分层自动化**(对齐 scoring_template.md 三层诊断栈):
   - **Layer 1 Outcome**(O1 / O2):material case 可用 LLM-as-judge;missing case 由五条死规则优先判定
   - **Layer 2 Component**:material case 自动跑 A1 / C2 / C3 / D1 / E1 / R3;missing case 自动跑 R1a / R2 / R3 / R4 / R5;**A2 无幻觉 + Origin/Inherited 标签**仍需人工 spot-check
   - 自动评测 v0.2 起 Layer 1 全自动 + Layer 2 部分自动;v0.3+ 推全自动(详 scoring_template.md § 5.2 演进路径)
5. **CSV 输出**:每 case 一行,字段建议:`case_id / o1 / o2 / a1 / a2 / r1a / r2 / c1 / c2 / c3 / d1 / e1 / r3 / r4 / r5 / origin_inherited_tags / verdict`

**TASK-503 阶段验收通过标准**:
- [ ] `eval/run_paper_eval.py` 存在并可跑
- [ ] 跑通 material_to_plan + missing_param 两个 v0.1 case
- [ ] **Layer 1 Outcome 全 Pass** OR **Layer 2 启动后 E1 / R3/R4/R5 均 Pass**(scoring_template § 6 单 case 验收口径);missing case 另须 R1a/R2/R3/R4/R5 全 Pass
- [ ] CSV 输出格式齐全;人工 spot-check 后无 [Origin] 类组件失败遗漏

---

## 2. golden 的内容来源与权威性

**material_to_plan/case_01 的 golden 直接锚定决策 22 § 4.2 PoC 实测结果**:

- `expected_paper_spec.json` 的 12 个参数:与 `同步发电机突然三相短路报告.docx` 第 2 段 100% 字面对齐(`PN=200MW` 等)
- `expected_model_generation_plan.json` 的 `library_choice = "SimPowerSystems"`:决策 22 § 4.4 发现 1 实测结论
- 工程决定字段:`5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s / 1s 时长` — 决策 22 § 4.2 实测电机短路报告 docx 第 5 段字面
- 衰减时间常数 `2.97 / 0.608 / 6.3`:与 docx 公式 `ia = ... 1.4·e^(-2.97t) ... 2.34·e^(0.608t) ... 0.77·e^(-6.3t) ...` 字面对齐
- 短路冲击电流参考值 `9.103`(`.slx`)/ `9.164`(`.m`):docx 最末段字面(**仅在 case_README 备注引用,不进 golden JSON** — golden 仅评 plan 层不评结果层)

**missing_param/case_01 的 golden 锚点**:决策 22 § 4.2 实测发现 docx 有 6 张图片,关键参数(标准同步发电机模型 / 变压器参数 / 初始化工具截图)在图片里;v0.1 纯文本抽取漏。

**权威性原则**:任一 golden 字段值与 docx 原文 / 决策 22 实测结论冲突 = 反例 K_34(语义记忆错位),需重审 golden,不许"按印象修"。

---

## 3. EvidencePack 双源不变量(task-500 v0.2.1 § 接口契约要点)

**`PaperEvidenceEntry` 字段**(6 字段):
- `source: Literal["document_extracted", "user_supplied"]`
- `paper_section_id: str | None`
- `equation_id: str | None`
- `figure_id: str | None`
- `excerpt: str | None`
- `missing_param_prompt_id: str | None`

**两套不变量**(自动 / 人工验收必跑):

### 3.1 `source = document_extracted`

- ✅ `paper_section_id` / `equation_id` / `figure_id` **至少一个非 None**
- ✅ `excerpt` **非 None 且非空**(1-300 字)
- ✅ `missing_param_prompt_id` **必为 None**

### 3.2 `source = user_supplied`

- ✅ `paper_section_id` / `equation_id` / `figure_id` **全部为 None**
- ✅ `excerpt` **必为 None**
- ✅ `missing_param_prompt_id` **必填**(非 None,关联 `MissingParameterPrompt.prompt_id`)

**校验脚本(留 TASK-501 实现)**:伪代码

```python
# 留 TASK-501 落地,本 chore 仅给约定
def validate_evidence_invariants(entry: dict) -> tuple[bool, str]:
    if entry["source"] == "document_extracted":
        locators_present = any(entry.get(k) is not None for k in ("paper_section_id", "equation_id", "figure_id"))
        if not locators_present:
            return False, "document_extracted 缺三 locator 至少一个"
        if not (entry.get("excerpt") and 1 <= len(entry["excerpt"]) <= 300):
            return False, "document_extracted 的 excerpt 必须 1-300 字非空"
        if entry.get("missing_param_prompt_id") is not None:
            return False, "document_extracted 的 missing_param_prompt_id 必须为 None"
        return True, "OK"
    elif entry["source"] == "user_supplied":
        locators_present = any(entry.get(k) is not None for k in ("paper_section_id", "equation_id", "figure_id"))
        if locators_present:
            return False, "user_supplied 的三个 paper locator 必须全为 None"
        if entry.get("excerpt") is not None:
            return False, "user_supplied 的 excerpt 必须为 None"
        if entry.get("missing_param_prompt_id") is None:
            return False, "user_supplied 的 missing_param_prompt_id 必填"
        return True, "OK"
    else:
        return False, f"未知 source: {entry['source']}"
```

**本 chore 人工验收**:测评人对每个 golden JSON 的 evidence 数组逐项肉眼对照上述两套不变量,任一不通过 → 改 golden,不通过 review。

---

## 4. 字段名 / Literal 取值真值源

**所有 golden JSON 字段名 / Literal 取值的真值源**:`docs/06_OUTPUT_CONTRACTS.md` § 12(本 TASK-500 chore 同步入仓)。

**截至本样本包入仓**,06 § 12 草稿 schema 字段表对齐 task-500 v0.2.1 § 接口契约要点;若 TASK-501 实施期发现字段需调整,走 06 § 7 D5 修订流程同步 golden(避免 golden 与契约漂移)。

**字段命名约定**(继承 06 既有风格):
- snake_case
- ID 字段:`<entity>_id`(`equation_id` / `figure_id` / `prompt_id` 等)
- 列表 / map 容器:复数(`equations` / `parameter_table` / `block_recommendations`)
- 单元 / 数值字段类型:string(避免 LLM JSON 输出 number 时的精度问题;具体类型 v0.1 草稿不冻结)

---

## 5. 测评人资格要求(本 chore 阶段)

**Layer 1 Outcome 评测**(必填 O1 / O2)+ **Layer 2 Component A2 无幻觉判断 + [Origin/Inherited] 标签**对测评人有专业要求:

- 至少有本科电气 / 自动化 / 控制 / 通信 / 信号处理专业背景,或同等领域工作经验(本 case 是 motor_control,要求具备 SimPowerSystems 经验最佳;v0.2 扩到其他学科 case 时同理)
- 能读懂 MATLAB / Simulink 工程
- 了解被测 case 的 domain(electrical / signal_processing / etc)对应的标准 MATLAB 工具箱

不具备上述资质的测评人,只能对**纯结构性 Layer 2 标准**(A1 字段完整 / R1a / R2 / C3 / D1 / E1 / R3/R4/R5)打分;**Layer 1 Outcome + A2 + C1 / C2 + [Origin/Inherited] 标签**留 PM / 架构师 / 电气专家 spot-check。

---

## 6. 版本

**版本**:v0.1(2026-06-16,TASK-500 v0.2.1 交付)
**作者**:架构师(接手第 44 任)
**关联**:scoring_template.md(评什么)+ README.md(目录组织)+ task-500 v0.2.1 § 接口契约要点
