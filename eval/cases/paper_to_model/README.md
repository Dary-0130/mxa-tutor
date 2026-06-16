# paper-to-model 评测样本包(v0.1)

> **本目录是决策 22 § 10.4 第 5 项前置硬门槛("评测准入")的最小可执行样本包**,由 TASK-500 v0.2.1 交付。
>
> **关联**:决策 22(方向 pivot)/ 宪法 v3.1 / roadmap v2.1 § 8.1(评测体系)/ 06 § 12 paper-to-model 输出契约(草稿,字段未冻结,TASK-501 落地后按 D5 流程演进)。

---

## 1. 评测范围

paper-to-model v0.1 副驾分三层承诺(决策 22 § 1.1),本评测样本包对应:

- **稳交付层**(必须做到):资料 → PaperSpec → ModelGenerationPlan;**`material_to_plan`** 子目录测之
- **MissingParameterPrompt 双源契约**:缺失参数识别 + 用户补充 → 更新 plan;**`missing_param`** 子目录测之
- **尽力交付层**(`.m` 骨架)/ **不承诺层**(`.slx` 成品):**本样本包不做硬性评测**,在 ModelGenerationPlan 的 `m_script_skeleton` 字段为可空设计,有则纳入 Layer 2 的 D1 标准评分

**资料入口领域范围**(决策 22 § 1.5):资料 `domain` 字段字面映射 6 类 project_type — `control_system` / `signal_processing` / `power_electronics` / `communication` / `motor_control` / `new_energy`;`general` 在资料入口拒绝。本样本包覆盖 `motor_control`(电机短路类),其他子类样本留 v0.2 扩。

---

## 2. 目录组织约定

```
eval/cases/paper_to_model/
├── README.md                     # 本文件
├── verification_method.md        # 验收方式说明(人工 vs TASK-501 自动)
├── scoring_template.md           # 三层诊断栈评分模板(Outcome → Component)
│
├── material_to_plan/             # "资料 → 模型搭建路线图"评测维
│   └── case_01_motor_short_circuit/
│       ├── case_README.md        # 本 case 说明 + 评分关注维度
│       ├── input/
│       │   └── source_doc_stripped.md   # 剥离版输入资料(剥离工程决定 + 结果段)
│       └── golden/
│           ├── expected_paper_spec.json
│           └── expected_model_generation_plan.json
│
└── missing_param/                # "缺图片参数 → 用户补充 → 输出更新"评测维
    └── case_01_missing_image_param/
        ├── case_README.md
        ├── input/
        │   ├── source_doc_stripped.md         # 同源 docx 剥离版
        │   └── expected_missing_prompts.json  # 系统应识别出的缺失参数
        ├── user_input/
        │   └── user_supplied_params.json      # 用户补充参数(标 user_supplied)
        └── golden/
            └── expected_updated_plan.json     # 用户补充后期望的更新 plan
```

**case 命名约定**:`case_NN_<short_slug>`(NN = 两位数字,从 01 起;slug = 英文小写下划线分隔关键词)。v0.1 范围每个评测维只配 1 case;v0.2 起扩样本时按 02 / 03 ... 顺延。

**Case 与 task-500 v0.2.1 目录对齐**:本目录结构严格对齐 task-500 v0.2.1 验收清单(material_to_plan + missing_param 二维 × 1 case 各),Codex 落仓时按字节复制,不许重命名 / 重排。

---

## 3. 评分流程(三层诊断栈)

**设计哲学**(对齐业界 2026 标准 — Confident AI / Watershed):**先看 outcome(用户能不能用)→ 不通过时看 component(哪个组件错)**,不一上来淹没测评人。详细评分模板见 `scoring_template.md`。

### 3.1 本 chore 阶段(TASK-500,人 + Claude/GPT 协作)

```
Step 1. 读 input/source_doc_stripped.md 理解输入

Step 2. (可选)PM 调通用 LLM(产品中实际跑 DeepSeek-V3,baseline 可用 Claude / GPT)
        生成 actual outputs(actual_paper_spec.json 等)

Step 3. 测评人填评分卡:
        ├─ Layer 1 Outcome(必填,2 标准,1 分钟):
        │   O1 Plan 可执行性 / O2 用户补充更新
        ├─ 若 Layer 1 全 Pass → 本 case 验收通过,不用看 Layer 2
        └─ 若 Layer 1 任一非 Pass → 启动 Layer 2(5 大类 10 标准),
                                    每个 ❌ 加 [Origin / Inherited] 标签

Step 4. 倒推根因(人 + Claude / GPT 共同分析评分卡)
        ├─ 优先看 [Origin] ❌(本组件独立出错)
        ├─ [Inherited] ❌ 暂不直接改 → 上游修好后大概率自然修复
        ├─ E1 / E2 一票否决 → 立即定位证据契约层
        └─ 输出"待优化组件清单"(组件 + 失败模式 + 优化方向)

Step 5. DeepSeek 角色:被测系统的 LLM 供应商(actual 生产者);
        不参与评测分析(避免 self-preference bias)
```

**为什么 DeepSeek 不参与分析**:DeepSeek 是项目宪法 v3.1 / 决策 22 选定的生产环境 LLM 供应商,本质是被测系统的 actor。让被测 LLM 评测自己的输出会引入 self-preference bias(LLM-as-judge 已知失败模式)。Claude / GPT 作为外部 reviewer 客观性更强。

### 3.2 TASK-501 PaperPlanService 落地后(自动评测演进)

| 阶段 | Layer 1 Outcome | Layer 2 Component | 倒推优化 |
|---|---|---|---|
| **v0.1**(当前) | 人 + Claude/GPT 协作 | 人 + Claude/GPT 协作 | 人决定改哪 |
| **v0.2** | LLM-as-judge(Claude / GPT 自动) | 人 + Claude/GPT 协作 | LLM 生成 prompt 优化建议,人审 |
| **v0.3+** | LLM-as-judge | LLM-as-judge | Claude / GPT propose prompt diff,人审应用 |
| **更远** | 全自动 | 全自动 | 自动改 prompt(无需人审) |

约束:**无论自动化推进到哪一步,DeepSeek 始终是被测 actor,不参与评测分析**。

### 3.3 单 case 验收口径(新口径)

**不用"X/30 分"或"80% 通过线"这种数字口径**。详 `scoring_template.md` § 6,简要:

| 情况 | 单 case 判定 |
|---|---|
| Layer 1 全 Pass | ✅ 验收通过 |
| Layer 1 任一 Partial,Layer 2 启动后 E1 / E2 均 Pass | 🟡 条件通过(建议改 [Origin] ❌ 组件后重跑) |
| Layer 1 任一 Fail | ❌ 不通过,启动 Layer 2 定位 |
| E1 / E2 任一 Fail | ❌ 一票否决(无论 Outcome 如何) |

**整体门槛 5 通过标准**:两个 case 各自达到 ✅ 或 🟡 + 两个 case 均无 E1 / E2 一票否决。

---

## 4. 样本演进路径

- **v0.1**(当前):2 个评测维 × 1 case 各;`motor_control` 子类
- **v0.2**(后续):扩样本至 `control_system` / `signal_processing` / `power_electronics` 各 ≥1 case;加多文档融合 case;加 OCR 图片参数抽取 case
- **新增 case** 必须同时提供 case_README + input + golden;**不许**只加 input 而不提供 golden(避免评测集腐烂)

---

## 5. 输入资料来源约定(产品架构约束)

**输入 docx / PDF 不入 mxa-tutor repo**:paper-to-model 产品形态中,输入资料是用户在使用产品时从本地文件系统(D 盘 / 桌面等)选择上传的,**资料本身不进 repo**(类比 MCS 工程入口的 zip — zip 不入仓,只在请求生命周期内沙箱解析)。

因此本评测样本包遵守以下约定:

- 每个 case 的 `input/source_doc_stripped.md` 是**自包含的评测输入**(剥离 / 模拟 v0.1 系统从用户 docx 抽到的文本流),测评人**不需要 docx 原文件**即可独立跑完评测
- **完整 docx 原文件**:由 PM 在本地维护(参见决策 22 § 4 PoC 实测样本《同步发电机突然三相短路报告.docx》),**不入仓**;架构师产 golden 时引用本地 docx 内容,但只把剥离版 .md + golden JSON 落仓
- TASK-501 PaperPlanService 端到端自动评测:由 PM 在本地把 docx 路径作为参数传入 eval 脚本;eval 脚本不假设 docx 在仓内

**对 task-500 v0.2.1 验收清单"PM 提供 docx,Codex 落仓"字面的解释口径**:落仓的是**架构师基于 docx 构造的剥离版 .md + golden JSON 套件**,不是 docx 文件本身;docx 仅作为架构师产 golden 时的 ground truth 参考。

---

## 6. 红线(对齐决策 22 § 5.2 + § 1.1)

- ❌ golden JSON 字段名 / 类型 / Literal 取值必须严格对齐 `docs/06_OUTPUT_CONTRACTS.md` § 12;**字段漂移 = 评测集失效**
- ❌ EvidencePack 双源约束(`document_extracted` / `user_supplied`)在 golden 中必须遵守 task-500 v0.2.1 § 接口契约要点的"两套不变量",**禁止跨 source 字段冲突**
- ❌ 不在 README / 文案中使用"自动生成 Simulink 模型 / 一键生成 / 完整仿真模型 / 模型成品"等表述;本样本包对外口径统一为"复现路线图 / 模型搭建副驾 / 参数对应说明"
- ❌ 不承诺 `.slx` 成品 / 不承诺运行结果 / 不承诺收敛(对齐决策 22 § 1.1)

---

**版本**:v0.1(2026-06-16,TASK-500 v0.2.1 交付)
**作者**:架构师(接手第 44 任)
**关联 task**:TASK-500 v0.2.1
