# TASK-502:PaperPlanService + MissingDetector + UserSupplyMerger(v0.1.3 — Codex 二次摸底反馈集成)

## 状态

🔲 v0.1.3(2026-06-17,Codex 二次摸底反馈微补丁,**派 Codex 终版**):
- **起稿基础**:TASK-501 PR #97 + chore PR #98 squash merged into main;main 必须包含 `a3fbeb491d9543aabfd4a90a02002e7d006fe08a`(Stage 0 用 `git merge-base --is-ancestor` 校验,允许 main 合法前进;R1 P2-3)
- **GPT R0 摸底**(2026-06-17):0 反方向 + 5 新选项 + 7 跨决策点冲突 — 全盘采纳;v0.1 集成
- **GPT R1 一审**(2026-06-17):3 P0 + 5 P1 + 5 P2 — 全盘采纳(0 反 challenge);v0.1.1 集成
- **GPT R1 二审**(2026-06-17):2 P0 + 3 P1 + 3 P2 — 全盘采纳(0 反 challenge);v0.1.2 集成
- **Codex 二次摸底**(2026-06-17,4 段 A/B/C/D 全过):
  - A 段:9 项 Stage 0 实测全过(base hash ✅ + uvicorn ✅ + single-worker 对齐既有 api/README.md 惯例)
  - B 段:6/6 任务卡理解自检全对(DAG / schema 边界 / 5 字段 record / != 判定 / 502 vs 400 / leaf 分流)
  - C 段:估时 25-34h / 10-15 commits 合理;阶段 2 / 3 / 4 高风险标记对
  - D 段反馈 6 项:5 项工艺承诺 ✅ / **1 项 K_30(D2)→ v0.1.3 微补丁**
- **v0.1.3 微补丁**:风险 10 段旧文案("reason.startswith / reason in" 字符串前缀分流)与 R1 二审 P1-3 leaf 分流冲突 → 改为"双 leaf 直接分流,不用 reason 字符串前缀";架构师 K_30 +1 记账
- **下一步**:**PM 拍板 v0.1.3 → 决定入仓路径(chore PR vs 本地)→ 派 Codex Stage 0 进阶段 1**

---

## R2 公开 challenge 清单(决策 12 v0.4)

| # | 项 | 裁决 | 结果 |
|---|---|---|---|
| (暂空) | GPT R0 摸底 0 反方向 challenge | — | — |

后续 R1 / R2 若有公开 challenge,本表追加。

---

## 上下文

### TASK-502 在 paper-to-model 主线位置

paper-to-model 主线第二个实现 task,承接 TASK-501 资料入口骨架 + PaperSpec 抽取(PR #97 squash merged into main)。

数据流(02 § 资料入口数据流):

```
用户上传论文 / 报告(PDF·docx)        ← TASK-501 范围起点
   ↓
文档安全沙箱(spawn / 30s / 512MB)   ← TASK-501 已落 sandbox(本任不动,D8a 红线)
   ↓
PaperParser(PDF/docx → 结构化文本流)  ← TASK-501 已落 parser/router(本任不动)
   ↓
PaperSpec(标题/摘要/公式/参数表/图占位/伪代码)  ← TASK-501 终点
   ↓
PaperPlanService(DAG: MissingDetector ∥ PlanComposer ∥ MScriptDrafter
                ; SubsystemPlanner ; Python PlanAssembler + EvidenceTagger) ← TASK-502 主范围
   ↓
ModelGenerationPlan + list[MissingParameterPrompt]  ← POST /api/v1/upload-document 扩展响应
   ↓
用户补充(UserSupplyService,纯 Python)  ← POST /api/v1/papers/{id}/user-supply
   ↓
updated ModelGenerationPlan + 双源完整 evidence
   ↓
TuningSuggestion + UX 闭环 + 持久化 cache + GET 端点  ← TASK-503 范围
```

### Base commit + 范围边界

- **Base**:main 必须包含 `a3fbeb491d9543aabfd4a90a02002e7d006fe08a`(TASK-501 PR #97 + chore PR #98 squash merged after;Codex Stage 0 用 `git merge-base --is-ancestor a3fbeb491d9543aabfd4a90a02002e7d006fe08a origin/main` 校验,允许 main 合法前进;R1 P2-3)
- **范围**:本卡仅落地 PaperPlanService + 4 prompt yaml + MissingDetector + UserSupplyMerger + EvidenceTagger Python helper + evaluator;**不落地** TuningSuggestion service / 前端 UX / GET 路由 / 持久化 cache(留 TASK-503)

### TASK-501 接力点字面修订(GPT R0 K_30-1 抓出,本任纠正)

**TASK-501 任务卡 § 后续 task 接力点 原字面**(`docs/tasks/task-501-paper-to-model-foundation.md`):

> 新增 prompt yaml:`paper_plan_generate.yaml`(9-component prompt 子角色:LibrarySelector / BlockRecommender / ParameterMapper / SubsystemPlanner / MScriptDrafter / MissingDetector / UserSupplyMerger / EvidenceTagger;Extractor 本卡已含)

**TASK-502 v0.1 修订口径**(GPT R0 跨决策点冲突 #1):

"9-component" 是 `scoring_template.md` § 4.1 评测组件清单(归因诊断单位),**不是 prompt yaml 数量**。TASK-502 实际拆分:

| # | 评测组件(scoring_template § 4.1) | TASK-502 实施落点 |
|---|---|---|
| 1 | Extractor 文档抽取 | TASK-501 已落地(`paper_spec_extract.yaml` + PaperSpecService) |
| 2 | MissingDetector 缺失识别 | **新 prompt yaml**(`paper_plan_missing_detector.yaml`)+ LLM call 1 |
| 3 | LibrarySelector 库选型 | **PlanComposer 内合并(role tag)** |
| 4 | BlockRecommender Block 推荐 | **PlanComposer 内合并(role tag)** |
| 5 | ParameterMapper 参数映射 | **PlanComposer 内合并(role tag)** |
| 6 | SubsystemPlanner 拆分步骤 | **新 prompt yaml**(`paper_plan_subsystem.yaml`)+ LLM call 3(依赖 PlanComposer 输出) |
| 7 | MScriptDrafter 代码骨架 | **新 prompt yaml**(`paper_plan_mscript.yaml`)+ LLM call 4(并发跑) |
| 8 | EvidenceTagger 证据 + 双源 | **纯 Python helper module**(`features/paper/paper_plan_helpers.py::EvidenceTagger`)被各 service 调用;对齐 TASK-501 R1 P2-3 字面"EvidenceTagger 不算独立组件,只是 evidence 字段约束" |
| 9 | UserSupplyMerger 用户补充合并 | **纯 Python service**(`features/paper/paper_user_supply_service.py`),无 LLM |

**实际落地汇总** = **4 新 prompt yaml**(MissingDetector / PlanComposer / SubsystemPlanner / MScriptDrafter)+ **2 Python module / service**(EvidenceTagger helper / UserSupplyService) — 与 TASK-501 接力点字面"单 yaml"假设不同;本任卡正式纠正。

### 决策摘要(D1-D8,GPT R0 修订集成)

| # | 决策 | GPT R0 修订 | 实施关键点 |
|---|---|---|---|
| **D1** | 4 LLM call + 2 Python module + 私有 MissingBindingModel(方案 B′)| **DAG 编排,非串行** + R1 P0-1 binding 拆分 + R1 P0-2 paper_id 注入 + R1 P1-1 validate_for_spec | Step 0: Python 注入 `plan_id = f"PLAN-{paper_id}"`、`paper_spec_id = paper_id`(R1 P0-2);Step 1: `asyncio.gather(missing_detect, plan_compose, mscript_draft)`(3 个 LLM call 并发);Step 2: SubsystemPlanner LLM call(依赖 plan.block_recommendations);Step 3: Python PlanAssembler 合并 + 生成私有 `list[MissingBindingModel]`(**不写入 ModelGenerationPlan**,因 ParameterMapping 5 字段公开 contract 锁定;R1 P0-1);Step 4: `EvidenceTagger.validate_for_spec(evidence, spec)` 双源 + locator 白名单 fail-fast(R1 P1-1);Step 5: 返回 `(plan, missing_prompts, missing_bindings)` |
| **D2** | 单端点 baseline + 增量更新 + 缺参 sentinel + InMemoryPaperPlanCache | API 字面纠正 + sentinel 常量 + cache 落地(R1 P0-3 / P1-4)| POST `/api/v1/upload-document` 扩响应为 `{paper_id, spec, plan, missing_prompts}` + **服务端存 `InMemoryPaperPlanCache`(内存,无持久化,留 TASK-503 SQLite;R1 P0-3)**;新增 POST `/api/v1/papers/{paper_id}/user-supply`,**入参只接 `{user_supplied_responses}`,不再前端传 plan/missing**;PlanComposer 缺参用 `value=MISSING_VALUE_SENTINEL`(常量 = "null" 字符串;R1 P1-4);PlanAssembler 用私有 binding 把 missing 绑定到 plan.parameter_mapping(不写入 plan) |
| **D3** | LLM-as-classifier + 后置 Python 校验 | source / locator 硬约束 | MissingDetector LLM 输出后必校:`paper_reference.source == "document_extracted"` + locator 在 PaperSpec 白名单内 + `source == "user_supplied"` 恒定;任一不满足直接抛 `PaperPlanGenerationError` |
| **D4** | features/paper 私有 schema + 严格 + 边界转 | 不进 06 § 12.9 | `features/paper/paper_user_input_schemas.py::UserSuppliedResponseModel`(extra=forbid + `user_supplied_note: str \| None = None`);Merger 边界转 `PaperEvidenceEntry(source="user_supplied")` |
| **D5** | schema 双字面 + prompt 优先 null + evaluator 等价 | A′ 三段 | schema 接受 `null` 和 `"—"`(em-dash)两者;prompt 教 LLM **优先输出 null**(工程推断 / 无物理单位);evaluator `is_unitless(unit)` equivalence class;v0.2 sample 扩充时统一字面(挂账 v0.5 协议) |
| **D6** | 半自动 + 归因诚实 | 自动 / 人工边界 + 归因粒度 | **自动**:结构层 + Layer 2 数值维度(A1 / B1 / B2 / C2 / C3 / D1 / E1 / E2);**人工**:Layer 1 O1/O2 + A2 / C1 / [Origin/Inherited] 标签;**归因粒度 = role tag + 字段级 fail reason(中等)**,不宣传"组件级独立自动归因" |
| **D7** | R6.1 显式 mypy 双兜底 | — | R6.1 命令清单显式 `mypy core/ adapters/ features/paper/ api/` + § 给 Codex 的提示 同步显式 |
| **D8a** | sandbox 红线 + 停手机制 | 明确字面 | § 不做 红线:不修改 `adapters/parser/_sandbox.py` / spawn / `pdf_parser.py` / `docx_parser.py`;若发现 PaperSpec locator 缺陷,停手回报 TASK-501,不在 502 顺手修 parser / spec service |
| **D8b** | 共享 prompt contract snippet(A-lean)| 注入,非复制 + **P2-4 完全不动 TASK-501 yaml** | `features/paper/_prompt_builder.py` 抽出共享 snippet 函数(evidence 双源 + locator 白名单 + 字段名清单 + 禁止别名 + literal 示例);4 个新 prompt yaml 引用共享 snippet,**只写本角色特有字段 + 反例**(避免 K_30 漂移面);**shared snippet 只服务 TASK-502 4 个新 prompt,不抽 TASK-501 `paper_spec_extract.yaml`**(R1 P2-4:TASK-501 真启动两轮才稳定,本任 refactor 也禁) |

### mxa-tutor 快速 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制 / 信号处理 / 新能源)的 MATLAB / Simulink AI 助教 Web 应用。v3.0 起从"MCS 工程导览 + 问答"扩展为**二合一产品**:

- MCS 工程入口(既有):上传 .zip 工程包 → 工程导览 + 问答
- paper-to-model 资料入口(新主线,TASK-501 起):上传论文 / 报告 PDF/docx → 抽取 PaperSpec → **TASK-502 生成 ModelGenerationPlan + 缺参提示 + 用户补充更新** → TASK-503 调参建议 + UX 闭环

副驾边界(决策 22 § 1.1 / 宪法 v3.1 § 3):稳交付(论文理解 + 路线图 + 参数对应)+ 尽力交付(.m 骨架)+ 不承诺(.slx 成品 / 运行 / 收敛)。

---

## 输入(前置依赖)

### 必读文档

- `docs/01_PROJECT_CONSTITUTION.md` v3.1(§ 3 paper-to-model v0.1 承诺 / § 16 项目当前状态)
- `docs/02_ARCHITECTURE_OVERVIEW.md` v3.0 delta(§ 资料入口数据流 / § 4.2 v3.0 占位 / § 4.x feature 边界)
- `docs/04_ENGINEERING_STANDARDS.md`(§ 6 依赖 / § 8.6 文档安全 / § 1.4 git log 工作流)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(§ 8 教学口吻 / § 9.2 prompt 版本)
- `docs/06_OUTPUT_CONTRACTS.md` § 12(paper-to-model 输出契约,含 § 12.5 ModelGenerationPlan v0.3.2 微补丁 + § 12.7 MissingParameterPrompt)
- `docs/decisions/20260615-22-direction-pivot-paper-to-model.md`(决策 22)
- `docs/decisions/decision-12-dual-ai-review-protocol-v0_4.md`(双 AI 协议)
- `docs/decisions/decision-15-diagnose-before-fix.md`
- `docs/decisions/decision-18-projectoverview-api-serialization-boundary.md`(D 类 ABC + bridge 桥接模式)
- `docs/decisions/decision-21-evidencepack-consumption-boundary.md`(paper feature 不 import overview / explanation)
- `docs/tasks/task-501-paper-to-model-foundation.md`(§ 接力点字面已被 TASK-502 v0.1 § 上下文修订;§ 7 服务模式可参考)
- `eval/cases/paper_to_model/scoring_template.md`(三层诊断栈 + 5 大类 10 标准 + 整体门槛 5)
- `eval/cases/paper_to_model/verification_method.md`(双源不变量 § 3 + 自动 evaluator 路径 § 1.2)
- `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/`(主验收 case)
- `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/`(双源 + 用户补充验收 case)

### TASK-501 落地代码骨架(本任只读消费,**不动**)

- 5 顶层 domain dataclass:`PaperSpec` / `PaperEvidenceEntry` / `ModelGenerationPlan` / `TuningSuggestion` / `MissingParameterPrompt`(`core/domain/paper_*.py`)
- 6 nested submodel:`EquationEntry` / `ParameterEntry` / `FigureRef` / `BlockRecommendation` / `ParameterMapping` / `ParameterDirection`
- `EvidenceSource` enum(`core/domain/paper_evidence.py:7`)
- 5 顶层 Pydantic wrapper + 6 nested(`features/paper/paper_schemas.py`,`_StrictBaseModel` base + extra=forbid)
- `DocumentParser` ABC + `DocumentParserRouter` + `ParsedDocument` + `ParsedLocatorIndex` + `FigurePlaceholder`(`core/interfaces/document_parser.py`)
- `PaperSpecService` + `InMemoryPaperSpecCache` + `PaperSpecCache` ABC(`features/paper/paper_spec_service.py`,本任**只读 PaperSpec 结果**)
- `TextProvider` ABC + `DeepSeekTextProvider`(`core/interfaces/llm_provider.py` + `adapters/llm/deepseek.py`,4 LLM call 全走 `chat(messages, json_mode=True)`)
- `features/paper/_prompt_loader.py`(参数化 `filename`,本任扩 4 新 yaml)+ `_prompt_builder.py`(本任 refactor 加 shared snippet 注入,D8b)
- `core/prompts/paper_spec_extract.yaml` v0.3(共享 snippet 起稿基准;若 D8b refactor 提取 shared 部分,**只 refactor 不改 LLM 行为**,D8a 兜底)
- `api/dependencies.py` 装配模式(参考 `get_paper_spec_service` 装配 `PaperPlanService` + `UserSupplyService`)
- `core/domain/exceptions.py`:`DocumentParseError` / `PaperSpecGenerationError` 2 leaf

### 本卡新增 leaf 异常

- `PaperPlanGenerationError(MxaError)`(`core/domain/exceptions.py` 新增)

### 本卡合并守门红线(继承 TASK-501,扩 sandbox/parser/spec service)

| # | 红线文件 / 目录 | 来源 |
|---|---|---|
| 1 | `core/domain/project_overview.py` | 决策 22 § 5.2 |
| 2 | `features/overview/overview_schemas.py` | 决策 22 § 5.2 |
| 3 | `core/prompts/project_overview.yaml` | 决策 22 § 5.2 |
| 4 | `features/overview/` 整目录 | 决策 21 |
| 5 | `features/explanation/` 整目录 | 决策 21 |
| 6 | `features/explanation/_evidence_builder.py` | TASK-500 v0.2.1 |
| 7 | **`adapters/parser/_sandbox.py`** | **D8a + GPT R0 红线** |
| 8 | **`adapters/parser/pdf_parser.py`** | D8a 扩展 |
| 9 | **`adapters/parser/docx_parser.py`** | D8a 扩展 |
| 10 | **`core/interfaces/document_parser.py`** | TASK-501 落地不动 |
| 11 | **`features/paper/paper_spec_service.py`** | 只消费 PaperSpec,不改 service |
| 12 | **`features/paper/paper_schemas.py`** | 不动 contract 字段 |
| 13 | **`core/prompts/paper_spec_extract.yaml`** | **D8a + R1 P2-4 强化:LLM 行为 + 文件本身都不动(refactor 也禁;若未来需统一 prompt builder,单独 chore)** |
| 14 | **`eval/cases/paper_to_model/` 12 文件**(D5 双字面接受,不动 sample)| 决策 22 § 5.2 |
| 15 | **`docs/06_OUTPUT_CONTRACTS.md` § 12.4 / 12.6 / 12.7 字段表** | 本任不改公开 contract;只在 § 12.5 加 ParameterMapping.unit 字面口径注(D5) |

---

## 输出(交付物)

### 新增生产文件清单

```text
core/
├── domain/
│   └── exceptions.py                              # 修订:新增 PaperPlanGenerationError + PaperUserSupplyError 双 leaf(R1 二审 P1-3)
└── prompts/
    ├── paper_plan_missing_detector.yaml           # 新建:MissingDetector prompt v0.1
    ├── paper_plan_composer.yaml                   # 新建:PlanComposer prompt v0.1(融合 Library + Block + ParameterMapper)
    ├── paper_plan_subsystem.yaml                  # 新建:SubsystemPlanner prompt v0.1
    └── paper_plan_mscript.yaml                    # 新建:MScriptDrafter prompt v0.1

features/paper/
├── __init__.py                                    # 修订:re-export PaperPlanService / UserSupplyService / InMemoryPaperPlanCache
├── _prompt_builder.py                             # 修订:加 shared snippet 注入函数 + 4 build_messages_*(R1 P2-4:不动 paper_spec_extract.yaml)
├── paper_plan_service.py                          # 新建:PaperPlanService DAG 编排(4 LLM call + Python assembler;R1 P0-2 paper_id 注入)
├── paper_plan_helpers.py                          # 新建:EvidenceTagger + PlanAssembler + MissingBindingModel + MISSING_VALUE_SENTINEL 常量
├── paper_plan_cache.py                            # 新建(R1 P0-3):PaperPlanCache ABC + InMemoryPaperPlanCache(沿用 TASK-204 模式)
├── paper_user_supply_service.py                   # 新建:UserSupplyService 纯 Python service(D4 + R1 P1-5 归属校验)
└── paper_user_input_schemas.py                    # 新建:UserSuppliedResponseModel + UserSuppliedResponseBatch(R1 P2-1 Field min_length=1)

api/
├── dependencies.py                                # 修订:装配 PaperPlanService + UserSupplyService + InMemoryPaperPlanCache
├── middleware/
│   └── error_handler.py                           # 修订(R1 P1-2):PaperPlanGenerationError → 502;user-supply 业务校验 → 400
└── routes/
    ├── paper_upload.py                            # 修订:UploadDocumentResponse 扩 plan + missing_prompts;调 plan_service.generate(spec, paper_id) 后写 cache
    └── paper_user_supply.py                       # 新建:POST /papers/{paper_id}/user-supply,**入参只接 {user_supplied_responses}**(R1 P0-3)

eval/
├── run_paper_eval.py                              # 新建:paper-to-model evaluator(D6 半自动)
├── _paper_eval_metrics.py                         # 新建:Layer 2 自动维度 metric helper
└── _paper_eval_csv.py                             # 新建:Layer 1 + 人工维度 CSV writer
```

### 测试文件清单

```text
tests/features/paper/
├── test_paper_plan_service.py                     # 新建:DAG 编排 + 4 LLM call mock + Python merge + paper_id 注入(R1 P0-2)
├── test_paper_plan_helpers.py                     # 新建:EvidenceTagger.validate_for_spec 单测(双源 + locator 白名单 fail-fast + 6 反例)+ PlanAssembler 单测 + MissingBindingModel
├── test_paper_plan_cache.py                       # 新建(R1 P0-3):InMemoryPaperPlanCache get/set/delete + 5 字段 record(paper_id + spec/plan/missing/bindings;R1 二审 P2-2 字面统一)
├── test_paper_user_supply_service.py              # 新建:UserSupplyMerger 单测(D4 边界转换 + 双源 + R1 P1-5 4 条归属校验)
├── test_paper_user_input_schemas.py               # 新建:UserSuppliedResponseModel + UserSuppliedResponseBatch freeze(extra=forbid + min_length=1;R1 P2-1)
└── test_paper_plan_prompts.py                     # 新建:4 新 prompt yaml load + shared snippet 注入验证

tests/api/
├── test_paper_user_supply.py                      # 新建:POST /user-supply 端点 + 4 种错误场景(R1 P1-2)
└── test_paper_plan_error_handler.py               # 新建(R1 P1-2):PaperPlanGenerationError → 502 + user-supply 业务 400 + evidence invariant 400/502

tests/eval/
└── test_paper_eval_metrics.py                     # 新建:Layer 2 自动维度 metric 校验
```

### 修订文件清单

- `docs/03_TASK_INDEX.md`:TASK-502 🔲 → 🔍(等待验收;PM 合并后改 ✅)
- `docs/06_OUTPUT_CONTRACTS.md` § 12.5:加 `ParameterMapping.unit` 字面口径注(D5 双字面);**字段集合 / 类型 / 约束不动**;**PR description 必须明确"只补充 unit 解释性字面,无字段集 / 类型 / 约束改动"**(R1 P2-5);R6.1 跑 `test_paper_schemas_freeze.py` + `test_paper_schemas_sample_roundtrip.py` 验证 schema 同源
- ~~`core/prompts/paper_spec_extract.yaml`~~ — **R1 P2-4 移除**:本任不动 TASK-501 prompt,shared snippet 只服务 4 个新 prompt;若未来需统一 prompt builder,单独 chore

### 完工三件套(决策 08)

- Commit:Conventional Commits;subject 单行无 body(反例 17)
- PR:Codex 给标题 + 正文草稿,PM 走 GitHub 网页 squash merge
- 03 索引同步:字节级 Python(LF/CRLF 双试,沿用 TASK-310 chore 模式)

---

## 范围(必须做,5 阶段)

**Commit 拆分原则**:Conventional Commits;subject 单行无 body(反例 17);按文件改动自然拆分。

### 阶段 1 — 基础设施 + EvidenceTagger Python helper + Cache(2-3 commit)

- 新增 `PaperPlanGenerationError(MxaError)` + **`PaperUserSupplyError(MxaError)`** leaf(`core/domain/exceptions.py`;R1 二审 P1-3:对齐 TASK-501 leaf-per-category 模式,LLM 侧 / 用户输入侧严格分流)
- 新增 `features/paper/paper_plan_helpers.py`:
  - **常量 `MISSING_VALUE_SENTINEL = "null"`(R1 P1-4)**:缺参 sentinel,所有三处(PlanComposer prompt 校验 / evaluator 命中判定 / UserSupplyService 覆盖校验)显式引用此常量
  - **`MissingBindingModel`(R1 P0-1 新增)**:TASK-502 私有 dataclass / Pydantic BaseModel,字段 `prompt_id / paper_param_name / model_param_name`;**不进 `ModelGenerationPlan`,不进 06 § 12.x 公开 contract**;由 PlanAssembler 生成,由 InMemoryPaperPlanCache 存储,由 UserSupplyService 消费
  - `EvidenceTagger`(纯 Python,R1 P1-1 修订签名):
    - **`validate_for_spec(evidence: list[PaperEvidenceEntry], spec: PaperSpec) -> None`**(签名变更):跑 verification_method § 3 两套不变量 + **locator 白名单校验**(`paper_section_id` ∈ `spec.evidence[*].paper_section_id` / `equation_id` ∈ `spec.equations[*].equation_id` / `figure_id` ∈ `spec.figure_locations[*].figure_id`);任一不满足抛 `PaperPlanGenerationError`
    - 覆盖所有证据位置(R1 P1-1):`ModelGenerationPlan.evidence` / `BlockRecommendation.paper_reference` / `MissingParameterPrompt.paper_reference`
    - `tag_user_supplied(response, missing_prompt) -> PaperEvidenceEntry`:边界转换(D4)
    - **不凭空生成 locator / 不改 source**(GPT R0 跨决策点冲突 #6 字面)
  - `PlanAssembler`(纯 Python,DAG 收尾合并 helper):
    - `merge(plan_composer_output, subsystem_steps, mscript, missing_prompts, paper_id) -> tuple[ModelGenerationPlan, list[MissingBindingModel]]`(R1 P0-1 + P0-2:返回值加 binding 列表;接收 paper_id 用于注入 plan_id / paper_spec_id)
    - **缺参 binding(R1 P0-1):遍历 missing_prompts → 生成 `MissingBindingModel` 列表**,**不写入 plan.parameter_mapping**(因 ParameterMapping 5 字段公开 contract 锁定)
- 新增 `features/paper/paper_plan_cache.py`(R1 P0-3):
  - `PaperPlanCache` ABC:`get(paper_id) -> PaperPlanRecord | None` / `set(paper_id, record) -> None` / `delete(paper_id) -> None`
  - `PaperPlanRecord` dataclass:`paper_id / spec / plan / missing_prompts / missing_bindings`(5 字段 record;R1 二审 P2-2 字面统一)
  - `InMemoryPaperPlanCache(PaperPlanCache)`:内存 dict 实现(沿用 `InMemoryPaperSpecCache` 模式);**不持久化,不引入 SQLite,留 TASK-503**
- 新增 `features/paper/paper_user_input_schemas.py`:
  - `UserSuppliedResponseModel`(D4 私有 schema,extra=forbid,5 字段:prompt_id / parameter_name / user_supplied_value / user_supplied_unit / user_supplied_note)
  - `UserSuppliedResponseBatch`(顶层 dict 校验,字段 `user_supplied_responses: list[UserSuppliedResponseModel] = Field(min_length=1)`;R1 P2-1 显式 validator)
- 单元测试:test_paper_plan_helpers.py + test_paper_plan_cache.py + test_paper_user_input_schemas.py
- **不动** API / PaperPlanService / 4 prompt yaml

### 阶段 2 — UserSupplyService(无 LLM,先落地)(2-3 commit)

- 新增 `features/paper/paper_user_supply_service.py`:
  - `class UserSupplyService`,构造签名 `__init__(cache: PaperPlanCache, evidence_tagger: EvidenceTagger | None = None)`(R1 P0-3:必须注入 cache)
  - 主入口(签名 R1 P0-3 重写,**不再前端传 plan/missing**):
    ```python
    async def merge(
        self,
        paper_id: str,
        responses: list[UserSuppliedResponseModel],
    ) -> ModelGenerationPlan:
        """从 cache 取 (spec, plan, missing_prompts, missing_bindings),
        服务端做归属校验(R1 P1-5),边界转换 + 双源 fail-fast,写回 cache。"""
    ```
  - **R1 P1-5 4 条归属校验**(任一失败 → `PaperPlanGenerationError`,API 翻译 400):
    1. `cache.get(paper_id)` 不存在 → 400 `paper_not_found`
    2. 任一 `response.prompt_id` 不在 `record.missing_prompts` 中 → 400 `prompt_id_not_found`
    3. 同一个 `prompt_id` 在本批 responses 中出现 ≥ 2 次 → 400 `prompt_id_duplicated`
    4. `response.parameter_name != missing_prompt.parameter_name` → 400 `parameter_name_mismatch`
    5. `missing_prompt` 对应的 binding 已被填过(plan.parameter_mapping 对应项 `value != MISSING_VALUE_SENTINEL`)→ 400 `prompt_already_filled`(覆盖留 TASK-503)
  - 行为(校验通过后):
    1. 对每个 response,通过 `evidence_tagger.tag_user_supplied(...)` 生成 `PaperEvidenceEntry(source="user_supplied")`
    2. 通过 `missing_bindings` 找到 plan.parameter_mapping 对应项(prompt_id → paper_param_name / model_param_name 映射),填入 `value` / `unit` / 改 `source="user_supplied"`
    3. append 新 evidence 到 `plan.evidence`(双源完整)
    4. `evidence_tagger.validate_for_spec(updated_plan.evidence, record.spec)` 跑双源 + locator 白名单 fail-fast
    5. `cache.set(paper_id, updated_record)` 写回(plan 已更新;missing_bindings 保留;missing_prompts 不变以供 evaluator 比对)
    6. 返回 `updated_plan`
- 新增 `api/routes/paper_user_supply.py`:
  - POST `/api/v1/papers/{paper_id}/user-supply`,**入参只接 `UserSuppliedResponseBatch`**(R1 P0-3),返回 `UpdatedPlanResponse`(含 **`updated_plan: ModelGenerationPlanModel`**;R1 二审 P2-1 字段名统一)
- 新增 `api/middleware/error_handler.py` 修订(R1 P1-2 + R1 二审 P1-3 leaf 分流):
  - `PaperPlanGenerationError` → 502 `{"error":"paper_plan_generation_failed","message":<中文>}`(LLM 生成侧;PlanComposer / SubsystemPlanner / MScriptDrafter / MissingDetector / PlanAssembler binding cardinality)
  - **`PaperUserSupplyError` → 400 `{"error":"paper_user_supply_invalid","message":<中文>}`**(用户输入侧;UserSupplyService 4 条归属校验 + atomic merge 校验)
  - **R1 二审 P1-3:不再用 reason 字符串前缀分流**,error_handler 按 leaf class 直接映射,Codex 实现边界更硬
- 新增 `api/dependencies.py` 装配:`get_paper_user_supply_service` + `get_paper_plan_cache`(InMemoryPaperPlanCache 单例)
- 单元 + API 测试:test_paper_user_supply_service.py + test_paper_user_supply.py + test_paper_plan_error_handler.py

### 阶段 3 — 4 prompt yaml + shared snippet 注入(2-3 commit)

- 修订 `features/paper/_prompt_builder.py`:
  - 新增 `_shared_paper_plan_constraints()` 函数:返回共享 system snippet(evidence 双源 / locator 白名单 / 字段名清单 / 禁止别名 / literal 示例 / unit 双字面 `null` 优先)
  - 新增 4 个 `build_messages_for_<role>(...)` 函数:每个注入 shared snippet + role 特有 placeholder
- 起稿 4 prompt yaml v0.1(只写 role 特有字段约束 + 反例,共享部分由 prompt_builder 注入,**不重复**):
  - `paper_plan_missing_detector.yaml`:输入 PaperSpec + figure_placeholders,输出 `list[MissingParameterPrompt]` JSON dict(顶层 `missing_prompts` key);role 特有约束 = 6 字段 MissingParameterPrompt + `source: "user_supplied"` 恒定;**LLM-as-classifier**(D3)
  - `paper_plan_composer.yaml`:输入 PaperSpec,输出 `ModelGenerationPlan` 主体(**plan_id / paper_spec_id 由 Python 注入(R1 P0-2),LLM 逐字照抄,不得自生成** + library_choice 1-300 字 + block_recommendations + parameter_mapping + evidence);**subsystem_breakdown 和 m_script_skeleton 留空**(后续 LLM call 填);**缺参 `value=MISSING_VALUE_SENTINEL`**(R1 P1-4 常量,GPT R0 跨决策点冲突 #3)
  - `paper_plan_subsystem.yaml`:输入 PlanComposer 输出 block_recommendations + PaperSpec.evidence,输出 `subsystem_breakdown` 3-10 步字符串数组
  - `paper_plan_mscript.yaml`:输入 PaperSpec.equations + parameter_table,输出 `m_script_skeleton` 字符串
- 单元测试 test_paper_plan_prompts.py:
  - 4 prompt yaml load 成功
  - shared snippet 注入后,4 个 system 段都含「evidence 双源契约」「locator 白名单」「禁止字段名」字面
  - prompt_builder 占位符替换(`{raw_text}` / `{figure_placeholders}` / `{paper_spec_json}` 等)正确

### 阶段 4 — PaperPlanService DAG 编排(2-3 commit)

- 新增 `features/paper/paper_plan_service.py`:`class PaperPlanService`
  - 构造签名:
    ```python
    def __init__(
        self,
        text_provider: TextProvider,
        evidence_tagger: EvidenceTagger | None = None,
        plan_assembler: PlanAssembler | None = None,
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,  # 120.0
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,       # 8000
    ) -> None
    ```
  - 主入口(R1 P0-2 加 paper_id 参数;R1 P0-1 返回值加 bindings):
    ```python
    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,  # R1 P0-2:Python 注入,不让 LLM 编 ID
    ) -> tuple[
        ModelGenerationPlan,
        list[MissingParameterPrompt],
        list[MissingBindingModel],   # R1 P0-1:私有 binding 不进 plan
    ]
    ```
  - DAG 编排(GPT R0 D1-B′ + R1 修订):
    ```
    Step 0: plan_id = f"PLAN-{paper_id}";paper_spec_id = paper_id(R1 P0-2 Python 注入)
    Step 1: asyncio.gather(
        missing_task = self._llm_missing_detect(spec),           # LLM call 1
        plan_task    = self._llm_plan_compose(spec, plan_id, paper_spec_id),  # LLM call 2
        mscript_task = self._llm_mscript_draft(spec),            # LLM call 4(并发)
    )
    Step 2: subsystem = await self._llm_subsystem_plan(           # LLM call 3
        plan.block_recommendations,
        spec.evidence,
    )
    Step 3: assembled_plan, missing_bindings = plan_assembler.merge(
        plan_composer_output=plan,
        subsystem_steps=subsystem,
        mscript=mscript,
        missing_prompts=missing_prompts,
        paper_id=paper_id,         # 注入 plan_id / paper_spec_id 覆盖 LLM 输出
    )
    Step 4: evidence_tagger.validate_for_spec(assembled_plan.evidence, spec)  # R1 P1-1 双源 + locator 白名单 fail-fast
            evidence_tagger.validate_for_spec([bp.paper_reference for bp in assembled_plan.block_recommendations], spec)
            evidence_tagger.validate_for_spec([mp.paper_reference for mp in missing_prompts], spec)
    Step 5: 返回 (assembled_plan, missing_prompts, missing_bindings)
    ```
  - 4 个 `_llm_<role>` helper 共用一个 `_call_llm_json(messages, role_name) -> dict`(R1 P1-3:语义验收抽 helper):
    1. `messages = build_messages_for_<role>(...)`(纯函数,prompt_builder 注入 shared snippet)
    2. **`response = await asyncio.to_thread(text_provider.chat, messages, json_mode=True, ...)`**(决策 11 决策 1;只在 `_call_llm_json` 内部出现 1 处)
    3. `data = json.loads(response.text)`(对齐 TASK-501 R1 P0-1)
    4. 返回 dict 给上层 role helper 做 Pydantic + role 特有校验
  - role 特有 Python 校验(MissingDetector:locator 白名单 + source==user_supplied + paper_reference.source==document_extracted;PlanComposer:plan_id / paper_spec_id 覆盖 LLM 输出 + 缺参 `value == MISSING_VALUE_SENTINEL` 合规;SubsystemPlanner:3-10 步;MScriptDrafter:str | None)
  - 任一不满足抛 `PaperPlanGenerationError(role_name)`
- 异常分支:`logger.error(..., type(exc).__name__) + from None`(决策 11 决策 2);禁 `logger.exception` / `str(exc)` / `repr(exc)` / `response.text` / `raw_text` 落日志
- 单元测试 test_paper_plan_service.py:
  - DAG 编排:mock 4 LLM call 返回固定 JSON,**验证 4 个 _llm_<role> 都调用同一个 `_call_llm_json`,且 `_call_llm_json` 通过 `asyncio.to_thread` 桥接**(R1 P1-3 语义验收)
  - paper_id 注入:LLM 输出 plan_id="PLAN-XXX" 时,assembler 用 `f"PLAN-{paper_id}"` 覆盖
  - 缺参 binding:PlanComposer 输出 `value=MISSING_VALUE_SENTINEL`,MissingDetector 输出对应 prompt_id,PlanAssembler 后返回 `list[MissingBindingModel]`(**plan.parameter_mapping 不含 missing_param_prompt_id**)
  - EvidenceTagger fail-fast:mock LLM 输出违反双源 / 违反 locator 白名单 → 抛 `PaperPlanGenerationError`
  - LLMError 5 子类直接向上抛(由 ERROR_MAP 翻译;沿用 TASK-203 v0.3 已落 handler)

### 阶段 5 — API 扩展 + evaluator + 03 索引(2-3 commit)

- 修订 `api/routes/paper_upload.py`:
  - 修订 `UploadDocumentResponse`:扩为 `{paper_id: str, spec: PaperSpecModel, plan: ModelGenerationPlanModel, missing_prompts: list[MissingParameterPromptModel]}`(**`missing_bindings` 不进 API 响应**,只在服务端 cache 持有;R1 P0-1 + P0-3)
  - 修订 `upload_document` route 流程:
    1. sandbox 处理 → ParsedDocument(沿用 TASK-501,不动)
    2. `spec = await spec_service.extract(saved_path, paper_id)`(沿用 TASK-501,不动)
    3. `plan, missing_prompts, missing_bindings = await plan_service.generate(spec, paper_id)`(R1 P0-2:注入 paper_id)
    4. **`plan_cache.set(paper_id, PaperPlanRecord(paper_id, spec, plan, missing_prompts, missing_bindings))`**(R1 P0-3:服务端写 cache)
    5. 返回 `UploadDocumentResponse(paper_id, spec, plan, missing_prompts)`
  - **不动** sandbox / SHA-256 / cleanup 逻辑(D8a 红线)
- 修订 `api/dependencies.py`:`get_paper_plan_service` + `get_paper_plan_cache`(InMemoryPaperPlanCache 单例,跨请求复用)
- 新增 `eval/run_paper_eval.py`:paper-to-model evaluator
  - 跑 material_to_plan + missing_param 两 case
  - 自动:结构层 schema validation + 双源不变量 + Layer 2 数值维度(A1 字段命中率 / B1 recall / B2 precision / C2 block 命中 / C3 参数映射命中 / **D1 m_script_skeleton shape 校验(R1 P2-2 降级:只评 shape,不评 MATLAB 语法可运行)** / E1 / E2)
  - **R1 P1-4 sentinel:`value == MISSING_VALUE_SENTINEL` 不算参数命中**(C3 计算时排除 sentinel 项)
  - 半自动 / 人工:输出 Layer 1 O1/O2 + A2 / C1 / [Origin/Inherited] 空槽 CSV,留人工填
  - R6.1 重跑获真实数字,以 TASK-502.1 完工 CSV 为准;不预设任一 case ✅/🟡
- 新增 `eval/_paper_eval_metrics.py`:
  - `compute_a1_field_coverage(actual_spec, golden_spec) -> float`
  - `compute_b1_b2(actual_prompts, golden_prompts) -> (recall, precision)`
  - `compute_c2_block_coverage(actual_plan, golden_plan) -> float`
  - `compute_c3_param_mapping_coverage(actual_plan, golden_plan) -> float`(**排除 sentinel 项**,R1 P1-4)
  - `compute_d1_mscript_shape(m_script: str | None) -> dict`(R1 P2-2:含参数区 / 方程区 / 绘图区占位 boolean 三元组;`m_script_skeleton is None` → Pass with `null` shape)
  - `is_unitless(unit: str | None) -> bool`(D5 equivalence class:`return unit is None or unit == "—"`)
  - `MISSING_VALUE_SENTINEL`(从 `features/paper/paper_plan_helpers.py` import,R1 P1-4 同源)
- 新增 `eval/_paper_eval_csv.py`:CSV writer + Layer 1 人工填卡模板
- 改 03 索引:TASK-502 🔲 → 🔍(字节级 LF/CRLF 双试,沿用 TASK-310 chore 模式)
- 完工三件套(决策 08)+ 提 PR(Codex 给 PM 标题 + 正文,PM 走 GitHub 网页创建)

---

## 不做(明确排除)

### 范围红线(本卡 = PaperPlanService + MissingDetector + UserSupplyMerger + 评测脚本)

- ❌ **TuningSuggestion service**(06 § 12.6)— 留 TASK-503
- ❌ **前端 UX 闭环**(MissingParameterPrompt UI / 用户补充表单 / plan 渲染)— 留 TASK-503
- ❌ **GET /api/v1/papers/{paper_id}/spec / GET /papers/{paper_id}/plan** — 留 TASK-503
- ❌ **持久化 cache**(`SqlitePaperSpecCache` / `SqlitePaperPlanCache`,对齐 TASK-204 模式)— 留 TASK-503
- ❌ **多文档融合 / 图片 OCR / 控制 + 信号处理子类样本** — v0.2 范围(决策 23 § 2.1)
- ❌ **LLM-as-judge 自动评测**(scoring_template § 5.2 v0.2 起)— 留 TASK-502 后续 prompt 演进 task 或 TASK-503
- ❌ **TuningSuggestion sample × schema sanity check** — 留 TASK-503(本任不消费 TuningSuggestion)

### 红线(D8a sandbox + 决策 21 / 决策 11,Codex 必守)

- ❌ 不动本卡合并守门红线 15 项(§ 输入 红线表)
- ❌ **不修改 `adapters/parser/_sandbox.py` / spawn 机制 / `pdf_parser.py` / `docx_parser.py`**(D8a + GPT R0 红线明文)
- ❌ **不修改 `features/paper/paper_spec_service.py` / `paper_schemas.py`**(只读消费,不改 contract)
- ❌ **不修改 `core/prompts/paper_spec_extract.yaml`(R1 P2-4 强化:连 refactor 抽取共享段都禁;TASK-501 真启动两轮才稳定,本任不动;若未来需统一 prompt builder,单独 chore)**
- ❌ `features/paper/` 不 import `features/overview/` / `features/explanation/` 私有结构(决策 21)
- ❌ `core/domain/paper_*.py` 不 import 任何 `features/` 路径
- ❌ 不修改样本包 12 文件任何字面(GPT R0 D5 接受双字面,**不改 sample**)
- ❌ 不引入除 TASK-501 已有依赖(pypdf / python-docx)外的新 pip 依赖
- ❌ 对外口径不用"自动生成 .slx / 一键生成 / 完整仿真模型 / 成品生成"等表述(决策 22 § 1.1)
- ❌ **若发现 PaperSpec locator 缺陷,停手回报 TASK-501 缺陷,不在 502 顺手修 parser / sandbox / paper_spec_service**(D8a + 决策 15 字面)

---

## 接口契约

### 7.1 PaperPlanService 构造签名 + 主入口(R1 P0-2 + P0-1 修订)

```python
# features/paper/paper_plan_service.py

DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS = 120.0
DEFAULT_PAPER_PLAN_MAX_TOKENS = 8000  # R6 真启动调参,对齐 DeepSeek V3 8192 上限


class PaperPlanService:
    """
    DAG 编排:
        Step 0: Python 注入 plan_id = f"PLAN-{paper_id}";paper_spec_id = paper_id(R1 P0-2)
        Step 1: asyncio.gather(MissingDetector ∥ PlanComposer ∥ MScriptDrafter)
        Step 2: SubsystemPlanner(依赖 PlanComposer.block_recommendations)
        Step 3: PlanAssembler(Python)合并 + 生成私有 MissingBindingModel 列表(R1 P0-1:不进 plan)
        Step 4: EvidenceTagger.validate_for_spec(evidence, spec)双源 + locator 白名单 fail-fast(R1 P1-1)
        Step 5: 返回 (plan, missing_prompts, missing_bindings)
    """

    def __init__(
        self,
        text_provider: TextProvider,
        evidence_tagger: EvidenceTagger | None = None,
        plan_assembler: PlanAssembler | None = None,
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,
    ) -> None: ...

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,  # R1 P0-2:Python 注入 plan_id / paper_spec_id,不让 LLM 编 ID
    ) -> tuple[
        ModelGenerationPlan,
        list[MissingParameterPrompt],
        list[MissingBindingModel],   # R1 P0-1:私有 binding 不进 plan / 不进 06
    ]: ...

    async def _call_llm_json(
        self,
        messages: list[dict],
        role_name: str,
    ) -> dict:
        """R1 P1-3:4 个 role helper 共用此入口;只在此处出现 1 处 asyncio.to_thread。
        语义验收(单测断言),非 grep 命中数验收。"""
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        return json.loads(response.text)
```

### 7.2 UserSupplyService 构造签名 + 主入口(R1 P0-3 + P1-5 + R1 二审 P1-2 atomic + P1-3 leaf 拆分)

```python
# features/paper/paper_user_supply_service.py

class UserSupplyService:
    """
    R1 P0-3:必须注入 PaperPlanCache;不再前端传 plan/missing。
    R1 P1-5:服务端校验 4 条归属规则(prompt_id 不存在/重复/parameter_name 不一致/已填)。
    R1 二审 P1-2:atomic merge(深拷贝),失败不污染 cache。
    R1 二审 P1-3:用户输入侧错误抛 PaperUserSupplyError(leaf),不抛 PaperPlanGenerationError;
                  error_handler 按 leaf 分流(无需 reason 字符串猜)。
    D4 边界转换:每个 UserSuppliedResponseModel → PaperEvidenceEntry(source="user_supplied")
    """

    def __init__(
        self,
        cache: PaperPlanCache,                          # R1 P0-3:必须注入
        evidence_tagger: EvidenceTagger | None = None,
    ) -> None: ...

    async def merge(
        self,
        paper_id: str,                                  # 路由路径参数
        responses: list[UserSuppliedResponseModel],     # 入参 batch
    ) -> ModelGenerationPlan:
        """流程(R1 二审 P1-2:atomic 语义 + P1-3 leaf 分流):
        1. record = cache.get(paper_id)  # None → PaperUserSupplyError(reason="paper_not_found")
        2. **R1 二审 P1-2:深拷贝 plan 副本**(plan_copy = record.plan.model_copy(deep=True));
           **以下所有修改在 plan_copy 上,record 内对象不可见**
        3. R1 P1-5 校验 4 条(任一失败抛 **PaperUserSupplyError**;**校验阶段不修改 plan_copy**):
           - response.prompt_id ∈ record.missing_prompts → PaperUserSupplyError(reason="prompt_id_not_found")
           - 同 prompt_id 重复 → PaperUserSupplyError(reason="prompt_id_duplicated")
           - response.parameter_name == missing_prompt.parameter_name → PaperUserSupplyError(reason="parameter_name_mismatch")
           - **plan_copy.parameter_mapping 对应项 value != MISSING_VALUE_SENTINEL → PaperUserSupplyError(reason="prompt_already_filled")**
             (R1 二审 P0-2:sentinel = 未填,非 sentinel = 已填,**正向逻辑**;覆盖留 TASK-503)
        4. 校验通过后,在 plan_copy 上修改:
           - 通过 missing_bindings 找到 plan_copy.parameter_mapping 对应项,填 value/unit/改 source="user_supplied"
           - append PaperEvidenceEntry(source="user_supplied") 到 plan_copy.evidence
        5. evidence_tagger.validate_for_spec(plan_copy.evidence, record.spec)  # 双源 + locator 白名单
           (用户侧 invariant 失败 → PaperUserSupplyError(reason="user_supplied_evidence_invalid");
            **若 EvidenceTagger 区分不清,统一按调用上下文判定:UserSupplyService 调用就是用户侧;
            PaperPlanService.generate 调用就是 LLM 侧 → PaperPlanGenerationError**)
        6. **R1 二审 P1-2:atomic write**:cache.set(paper_id, updated_record);
           **仅当 3 + 4 + 5 全过才写回;任一失败 cache 原 record 不变**
        7. 返回 plan_copy(updated_plan)
        """
        ...
```

```python
# core/domain/exceptions.py(修订,R1 二审 P1-3 新增 leaf)

class PaperPlanGenerationError(MxaError):
    """LLM 生成侧错误(MissingDetector / PlanComposer / SubsystemPlanner / MScriptDrafter /
    PlanAssembler binding cardinality / EvidenceTagger LLM 侧 invariant)。
    error_handler:→ 502 paper_plan_generation_failed
    R1 二审 P1-3:与 PaperUserSupplyError 严格区分,不再用 reason 字符串前缀分流。"""


class PaperUserSupplyError(MxaError):
    """用户输入侧错误(UserSupplyService 4 条归属校验失败 + atomic merge 校验失败)。
    error_handler:→ 400 paper_user_supply_invalid
    R1 二审 P1-3 新增 leaf(对齐 TASK-501 DocumentParseError / PaperSpecGenerationError leaf-per-category 模式)。"""
```

### 7.3 Python Helper:EvidenceTagger + PlanAssembler + MissingBindingModel + Cache(R1 P0-1 / P0-3 / P1-1 / P1-4 集成)

```python
# features/paper/paper_plan_helpers.py

# R1 P1-4:缺参 sentinel 常量,所有三处显式引用
MISSING_VALUE_SENTINEL: str = "null"


@dataclass(frozen=True)
class MissingBindingModel:
    """R1 P0-1:TASK-502 私有 binding,不进 ModelGenerationPlan,不进 06。
    由 PlanAssembler 生成,由 InMemoryPaperPlanCache 存储,由 UserSupplyService 消费。
    """
    prompt_id: str           # MissingParameterPrompt.prompt_id
    paper_param_name: str    # ParameterMapping.paper_param_name(锚点)
    model_param_name: str    # ParameterMapping.model_param_name(便于审计)


class EvidenceTagger:
    """纯 Python 双源 + locator 白名单 fail-fast helper(R1 P1-1 修订)。
    GPT R0 跨决策点冲突 #6 字面:不凭空生成 locator;不改 source。"""

    def validate_for_spec(
        self,
        evidence: list[PaperEvidenceEntry],
        spec: PaperSpec,                              # R1 P1-1:必须传 spec 做 locator 白名单校验
    ) -> None:
        """覆盖三处调用点(R1 P1-1):
        - plan.evidence
        - [bp.paper_reference for bp in plan.block_recommendations]
        - [mp.paper_reference for mp in missing_prompts]

        校验:
        - verification_method.md § 3 两套双源不变量(形状层)
        - locator 白名单:paper_section_id ∈ spec.evidence[*].paper_section_id
                          equation_id ∈ spec.equations[*].equation_id
                          figure_id ∈ spec.figure_locations[*].figure_id
        任一不满足 → 抛 PaperPlanGenerationError(reason)。
        """

    def tag_user_supplied(
        self,
        response: "UserSuppliedResponseModel",
        missing_prompt: MissingParameterPrompt,
    ) -> PaperEvidenceEntry:
        """边界转换:UserSuppliedResponseModel → PaperEvidenceEntry(source='user_supplied')
        严格按双源不变量第二套:三 locator 全 None + excerpt = None + missing_param_prompt_id 必填。"""


class PlanAssembler:
    """DAG 收尾合并 helper(纯 Python)。
    R1 P0-1:返回值加 list[MissingBindingModel],不写入 plan。
    R1 P0-2:接收 paper_id,Python 注入 plan_id / paper_spec_id 覆盖 LLM 输出。
    R1 二审 P1-1:binding cardinality fail-fast(0 / 多命中都抛 PaperPlanGenerationError)。"""

    @staticmethod
    def merge(
        plan_composer_output: ModelGenerationPlan,    # subsystem_breakdown / m_script_skeleton 留空
        subsystem_steps: list[str],
        mscript: str | None,
        missing_prompts: list[MissingParameterPrompt],
        paper_id: str,                                # R1 P0-2:用于注入 ID
    ) -> tuple[ModelGenerationPlan, list[MissingBindingModel]]:
        """合并 + 生成 binding(R1 P0-1):
        - plan_id = f"PLAN-{paper_id}";paper_spec_id = paper_id(覆盖 LLM 输出)
        - subsystem_breakdown / m_script_skeleton 填充
        - 遍历 missing_prompts → 在 plan.parameter_mapping 中找 value == MISSING_VALUE_SENTINEL
          且 paper_param_name 匹配的项 → 生成 MissingBindingModel 加入列表

        **R1 二审 P1-1 binding cardinality fail-fast**:
        对每个 MissingParameterPrompt,必须恰好生成 1 个 MissingBindingModel:
        - 0 命中 → PaperPlanGenerationError(reason="missing_binding_not_found", origin="llm_generation")
                  (502:plan 与 missing 在并发生成阶段错配,完整性问题不能留到 UserSupplyService)
        - 多命中 → PaperPlanGenerationError(reason="missing_binding_ambiguous", origin="llm_generation")
                  (502:同名 paper_param_name 出现 ≥ 2 sentinel mapping,无法唯一定位)

        - 不写入 plan.parameter_mapping 任何新字段(ParameterMapping 5 字段公开 contract)
        """
```

```python
# features/paper/paper_plan_cache.py(R1 P0-3 新增)

@dataclass(frozen=True)
class PaperPlanRecord:
    """InMemoryPaperPlanCache 存储单元。"""
    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingBindingModel]


class PaperPlanCache(ABC):
    """对齐 PaperSpecCache 模式(TASK-501 已落)。"""

    @abstractmethod
    async def get(self, paper_id: str) -> PaperPlanRecord | None: ...

    @abstractmethod
    async def set(self, paper_id: str, record: PaperPlanRecord) -> None: ...

    @abstractmethod
    async def delete(self, paper_id: str) -> None: ...


class InMemoryPaperPlanCache(PaperPlanCache):
    """内存 dict 实现。
    不持久化,留 TASK-503 SqlitePaperPlanCache。"""
    # 实现略
```

### 7.4 UserSuppliedResponseModel(D4 features 私有 schema)

```python
# features/paper/paper_user_input_schemas.py

class UserSuppliedResponseModel(BaseModel):
    """v0.1 features 私有 schema(D4 + GPT R0 #4);
    TASK-503 决定是否提升为 06 § 12.9 公开 contract。"""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str                                # 关联 MissingParameterPrompt.prompt_id
    parameter_name: str                           # 待补充参数名(冗余,便于审计)
    user_supplied_value: str                      # 用户补充值(string,避免 numeric 精度问题)
    user_supplied_unit: str | None = None         # 用户补充单位(可空,接线方式等无单位场景)
    user_supplied_note: str | None = None         # 解释性 metadata(非必填,sample 字段)


class UserSuppliedResponseBatch(BaseModel):
    """POST /api/v1/papers/{paper_id}/user-supply 入参顶层 dict 校验。"""

    model_config = ConfigDict(extra="forbid")

    user_supplied_responses: list[UserSuppliedResponseModel] = Field(min_length=1)
    # R1 P2-1:显式 Field validator;freeze test 覆盖空数组 → ValidationError
```

### 7.5 共享 prompt contract snippet(D8b A-lean,注入而非复制)

由 `features/paper/_prompt_builder.py::_shared_paper_plan_constraints()` 返回的 system 段共享部分(伪 YAML 字面,实际由 Python 函数拼接到每个 prompt 的 system 段):

```text
你是中国电气 / 自动化 / 控制专业的 MATLAB/Simulink 助教。
只返回有效 JSON 对象;不要 markdown,不要解释文字。

【evidence 双源契约】(每个 PaperEvidenceEntry 必守):
- 字段(6 个,逐字匹配):source / paper_section_id / equation_id / figure_id / excerpt / missing_param_prompt_id
- source = "document_extracted":三 locator 至少一个非 null;excerpt 1-300 字非空;missing_param_prompt_id = null
- source = "user_supplied":三 locator 全 null;excerpt = null;missing_param_prompt_id 必填(关联 MissingParameterPrompt.prompt_id)

【locator 白名单】(只能从 PaperSpec 给出的 ID 集中选,严禁自创):
- paper_section_id 只能来自 PaperSpec.evidence[*].paper_section_id
- equation_id 只能来自 PaperSpec.equations[*].equation_id
- figure_id 只能来自 PaperSpec.figure_locations[*].figure_id

【字段名硬约束】(逐字匹配,禁止自创字段名,沿用 TASK-501 v0.3):
- BlockRecommendation 3 字段:block_type / purpose / paper_reference
- ParameterMapping 5 字段:paper_param_name / model_param_name / value / unit / source
- ParameterMapping.unit 工程推断 / 无物理单位时 **优先填 null**(更稳);接受 "—"(em-dash)字面但不推荐
- 禁止字段名:locator / locators / paper_locator / param_name / parameter_name / param_symbol / param_value / param_unit
- 禁止字段名嵌套对象:locator 必须把 paper_section_id / equation_id / figure_id 平铺,不嵌套

【字面示例】:
- ParameterMapping 物理单位项:
  {"paper_param_name":"PN","model_param_name":"Synchronous Machine.Pn (VA)","value":"200e6","unit":"VA","source":"document_extracted"}
- ParameterMapping 标幺值项:
  {"paper_param_name":"xd","model_param_name":"Synchronous Machine.Xd (pu)","value":"1.0","unit":"pu","source":"document_extracted"}
- ParameterMapping 工程推断无单位项(优先 null):
  {"paper_param_name":"求解器","model_param_name":"Simulation > Solver","value":"ode15s","unit":null,"source":"document_extracted"}
- ParameterMapping 用户补充项:
  {"paper_param_name":"(用户补充) H","model_param_name":"Synchronous Machine.H (s)","value":"3.5","unit":"s","source":"user_supplied"}
- PaperEvidenceEntry user_supplied:
  {"source":"user_supplied","paper_section_id":null,"equation_id":null,"figure_id":null,"excerpt":null,"missing_param_prompt_id":"MISS-001"}

【双源契约红线】:
- 不得伪造 evidence(凭空生成 locator / excerpt)
- 不得把 user_supplied 标成 document_extracted(反例 2,06 § 12.8)
- 不得让 document_extracted 缺 locator + excerpt(反例 3)
- 不得把 PaperEvidenceEntry 当作 explanation EvidencePack 子集消费(反例 4)

【反幻觉】:
- 不输出 PaperSpec / 资料没给的参数 / 公式 / 图占位
- 工程推断字段(平衡节点 / 求解器名 / 仿真时长 / 故障时刻等)只在 SimPowerSystems 工程惯例下推断;
  若 PaperSpec 已含,直接复用,不重新编
- **缺参时:value 字面填 "null"(字符串,sentinel,R1 P1-4 由系统常量 MISSING_VALUE_SENTINEL 定义);**不编值**;**
  **不在 ParameterMapping 上加 missing_param_prompt_id 字段(R1 P0-1:ParameterMapping 5 字段公开 contract,binding 由 PlanAssembler 后置生成 MissingBindingModel,不进 plan)**
- **plan_id / paper_spec_id 不要自生成,由系统注入,逐字照抄(R1 P0-2)**
```

### 7.6 MissingDetector prompt v0.1 角色特有字段

(system 段共享部分见 § 7.5,以下只列 role 特有约束)

```text
【你的角色】:MissingDetector — 识别资料中提及但 PaperSpec 未抽到具体值或单位的参数,生成补充提示列表。

【输入 placeholder】:
- {paper_spec_json}:完整 PaperSpec JSON
- {figure_placeholders}:figure_id + caption + section_id 列表

【输出 schema】(顶层 JSON dict):
{
  "missing_prompts": [
    {
      "prompt_id": "MISS-XXX",
      "parameter_name": "...",
      "paper_reference": <PaperEvidenceEntry,source=document_extracted,必引用 figure_id 之一>,
      "suggested_unit": "..." | null,
      "user_supplied_value": null,
      "user_supplied_unit": null,
      "source": "user_supplied"
    }
  ]
}

【MissingParameterPrompt 7 字段硬约束】(对齐 06 § 12.7):
- prompt_id / parameter_name / paper_reference(必填,PaperEvidenceEntry)/ suggested_unit(str | null)/
  user_supplied_value(回填前必 null)/ user_supplied_unit(回填前必 null)/ source(恒定 "user_supplied")

【识别规则】(LLM-as-classifier,D3):
- 优先识别 figure_placeholders 中含"参数 / 模型 / 初始化 / 变压器 / 电机"等关键词的 caption,推断图中可能含未抽参数
- 不重复识别 PaperSpec.parameter_table 中已抽出的参数(D3 B2 precision)
- 每个 prompt 的 paper_reference.figure_id 必须来自 figure_placeholders 给出的 ID 集

【角色特有反例】:
- ❌ paper_reference.source = "user_supplied"(必须 "document_extracted")
- ❌ paper_reference.figure_id 不在 figure_placeholders 白名单内
- ❌ source = "document_extracted"(必须恒定 "user_supplied")
- ❌ user_supplied_value / user_supplied_unit 非 null(回填前必 null)
```

### 7.7 PlanComposer prompt v0.1 角色特有字段

```text
【你的角色】:PlanComposer — 融合 LibrarySelector + BlockRecommender + ParameterMapper,
基于 PaperSpec 生成 ModelGenerationPlan 主体(library_choice / block_recommendations / parameter_mapping / evidence);
subsystem_breakdown 留空数组 [];m_script_skeleton 留 null(后续 LLM call 填)。

【输入 placeholder】:
- {paper_spec_json}:完整 PaperSpec JSON
- {plan_id}:系统注入的 plan ID(R1 P0-2,如 "PLAN-PAPER-001"),**逐字照抄,不要自生成**
- {paper_spec_id}:系统注入的 paper_spec_id(R1 P0-2,如 "PAPER-001"),**逐字照抄,不要自生成**

【输出 schema】(顶层 JSON dict,字段对齐 06 § 12.5 ModelGenerationPlan):
{
  "plan_id": "{plan_id}",                    # R1 P0-2:逐字照抄系统注入值
  "paper_spec_id": "{paper_spec_id}",        # R1 P0-2:逐字照抄系统注入值
  "library_choice": "...(1-300 字,含库名 + 选型理由)",
  "block_recommendations": [{block_type, purpose, paper_reference}, ...],
  "parameter_mapping": [{paper_param_name, model_param_name, value, unit, source}, ...],
  "subsystem_breakdown": [],     # 留空,SubsystemPlanner 后续填
  "m_script_skeleton": null,     # 留 null,MScriptDrafter 后续填
  "evidence": [PaperEvidenceEntry, ...]  # 至少 1 项,全 document_extracted
}

【缺参语义】(GPT R0 跨决策点冲突 #3 + R1 P1-4 sentinel):
- 若某参数槽位在 PaperSpec.parameter_table 中没有具体值(如 H 惯性时间常数 / 变压器变比 / α0 初相角),
  parameter_mapping 项的 **value 字面填 "null"(字符串 sentinel,R1 P1-4)**,
  unit 按推断,source = "document_extracted"
- **不要在 ParameterMapping 上加 missing_param_prompt_id 字段(R1 P0-1)**;binding 由系统后置生成
- 不要编造具体数值

【角色特有反例】:
- ❌ subsystem_breakdown 非空数组(必须 [])
- ❌ m_script_skeleton 非 null(必须 null)
- ❌ value 字段含编造的具体数值(必须填 "null" 字符串 sentinel 占位)
- ❌ plan_id / paper_spec_id 不等于系统注入值(必须逐字照抄)
- ❌ parameter_mapping 项含 missing_param_prompt_id 字段(违反 ParameterMapping 5 字段 schema)
```

v0.2 R6 真启动微补丁(2026-06-18):paper_reference 嵌套 dict 6 字段硬约束 + 字面正反例(LLM 易把字段输出为字符串描述,v0.2 显式约束;对齐 TASK-501 v0.3 真启动 prompt 微补丁套路)。

### 7.8 SubsystemPlanner prompt v0.1 角色特有字段

```text
【你的角色】:SubsystemPlanner — 基于 PlanComposer 输出的 block_recommendations + PaperSpec.evidence,
生成有序搭建步骤(3-10 步)。

【输入 placeholder】:
- {block_recommendations_json}:PlanComposer 输出的 block_recommendations 数组
- {paper_evidence_json}:PaperSpec.evidence 数组

【输出 schema】(顶层 JSON dict):
{
  "subsystem_breakdown": ["第 1 步:...", "第 2 步:...", ..., "第 N 步:..."]  # 3-10 步,每步字符串
}

【角色特有反例】:
- ❌ 步骤少于 3 步或多于 10 步
- ❌ 步骤引用 block_recommendations 之外的 block 名
- ❌ 步骤含具体参数数值(参数留 parameter_mapping,subsystem_breakdown 只讲拓扑结构)
```

### 7.9 MScriptDrafter prompt v0.1 角色特有字段(R1 P2-2 降级)

```text
【你的角色】:MScriptDrafter — 基于 PaperSpec.equations + parameter_table,生成 .m 数值计算骨架。
**R1 P2-2:.m 骨架是宪法 v3.1 § 3 尽力交付,不是稳交付;**
**TASK-502 验收只评 shape(参数区 / 方程区 / 绘图区占位三元组),不评 MATLAB 语法可运行。**

【输入 placeholder】:
- {equations_json}:PaperSpec.equations 数组
- {parameter_table_json}:PaperSpec.parameter_table 数组

【输出 schema】(顶层 JSON dict):
{
  "m_script_skeleton": "..."  # str,完整 .m 代码;若资料无显式公式或参数,**返回 null(R1 P2-2 显式允许)**
}

【角色特有约束】(若非 null):
- 包含 clear; clc; 头部
- 参数从 parameter_table 读出(注释标 paper_section_id 来源)
- 公式按 equations[*].latex_or_text 直接转 .m 语法
- 含 figure + subplot + title 绘图段(若公式可绘制)
- 注释为中文(对齐 05 § 8 教学口吻)

【角色特有反例】:
- ❌ 编造资料外的参数 / 公式
- ❌ 用英文注释(必须中文)
- ❌ m_script_skeleton 非空但 PaperSpec.equations 为空(应返回 null)
```

### 7.10 API 路由(D2 单端点 + 增量端点;R1 P0-3 cache 落地)

```python
# api/routes/paper_upload.py(修订)

class UploadDocumentResponse(BaseModel):
    """D2 修订:扩字段为 baseline plan + missing prompts。
    R1 P0-1 + P0-3:missing_bindings 不进 API 响应,只在服务端 cache 持有。"""
    paper_id: str
    spec: PaperSpecModel
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    model_config = ConfigDict(extra="forbid")


@router.post("/api/v1/upload-document", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    spec_service: PaperSpecService = Depends(get_paper_spec_service),
    plan_service: PaperPlanService = Depends(get_paper_plan_service),
    plan_cache: PaperPlanCache = Depends(get_paper_plan_cache),      # R1 P0-3
) -> UploadDocumentResponse:
    """流程:
    1. sandbox 沙箱处理(沿用 TASK-501,不动)
    2. spec = await spec_service.extract(saved_path, paper_id)(沿用 TASK-501,不动)
    3. plan, missing_prompts, missing_bindings = await plan_service.generate(spec, paper_id)  # R1 P0-2 注入 paper_id
    4. await plan_cache.set(paper_id, PaperPlanRecord(...))  # R1 P0-3 服务端写 cache
    5. 返回 UploadDocumentResponse(paper_id, spec, plan, missing_prompts)  # bindings 不出 API
    """


# api/routes/paper_user_supply.py(新建,R1 P0-3 入参重写)

class UpdatedPlanResponse(BaseModel):
    """POST /papers/{paper_id}/user-supply 响应。"""
    paper_id: str
    updated_plan: ModelGenerationPlanModel
    model_config = ConfigDict(extra="forbid")


@router.post(
    "/api/v1/papers/{paper_id}/user-supply",
    response_model=UpdatedPlanResponse,
)
async def submit_user_supply(
    paper_id: str,
    batch: UserSuppliedResponseBatch,                                # R1 P0-3:入参只接 batch
    service: UserSupplyService = Depends(get_paper_user_supply_service),
) -> UpdatedPlanResponse:
    """R1 P0-3:不再前端传 existing_plan / missing_prompts;
    服务端从 PaperPlanCache 取 record(spec / plan / missing_prompts / missing_bindings);
    R1 P1-5 4 条归属校验由 service 层做。"""
    updated_plan = await service.merge(paper_id, batch.user_supplied_responses)
    return UpdatedPlanResponse(paper_id=paper_id, updated_plan=updated_plan)


# api/middleware/error_handler.py(修订,R1 P1-2 + R1 二审 P1-3 leaf 分流)

# ERROR_MAP 加入(对齐 TASK-501 leaf-per-category 模式;不用 reason 字符串前缀分流):
# PaperPlanGenerationError → 502 {"error":"paper_plan_generation_failed","message":<中文>}
# PaperUserSupplyError    → 400 {"error":"paper_user_supply_invalid","message":<中文>}
#
# R1 二审 P1-3:LLM 侧 / 用户输入侧严格分流,无需 service 在 raise 时设置 reason / context;
# Codex 实现边界更硬,error_handler 按 leaf class 直接映射。
```

---

## 验收标准

### 评测验收线(对齐 scoring_template.md 三层栈)

**TASK-502 的完整整体门槛 5 仍按 `scoring_template.md` § 6.1 判定;R6 后置修复已重跑真实 evaluator,数字以 TASK-502.1 完工 CSV 为准,不预设 ✅/🟡。**

| 评测维度 | TASK-502 验收要求 |
|---|---|
| 结构层(Pydantic schema + 双源不变量自动校验)| **必过**(任一不过 = R6.1 Fail) |
| Layer 2 自动维度(A1 / B1 / B2 / C2 / C3 / D1 / E1 / E2)| 以 TASK-502.1 完工 CSV 真实数字为准;`blocked_known_defect` 时不可评维度写 `N/A`,不得判 ✅/🟡 |
| Layer 2 半自动 / 人工(A2 / C1 / [Origin/Inherited] 标签)| 人工填卡;不阻塞自动跑(D6 归因诚实) |
| Layer 1 Outcome(O1 / O2)| 人工填卡:material_to_plan O1 + missing_param O1+O2 |
| **整体门槛 5** | 只有两 case 均 `succeeded` 且各自 ✅ 或 🟡 + 0 E1 / E2 一票否决才通过;`blocked_known_defect` = 产品门槛 Fail |

### R6.1 完工实测命令(D7 显式 mypy + 决策 11 grep + 决策 21 boundary + 红线 15 项)

```bash
# 1. CI 全管道(D7 双兜底)
ruff check core/ adapters/ features/paper/ api/ tests/
ruff format --check core/ adapters/ features/paper/ api/ tests/
mypy core/ adapters/ features/paper/ api/                                   # D7 显式
pytest tests/features/paper/ tests/api/test_paper_user_supply.py tests/api/test_paper_upload.py tests/api/test_paper_plan_error_handler.py tests/eval/ -v
# R1 二审 P2-3:显式包含 test_paper_upload.py(本卡修改 upload route 返回 + 写 cache)
make check                                                                  # 等价 + hygiene

# 1.5. R1 二审 P0-1 反向 grep:Codex 易照旧字面让 LLM 自生成 ID
grep -rn "自生成" core/prompts/paper_plan_*.yaml features/paper/_prompt_builder.py 2>/dev/null
# 期望:0 命中,或仅在"禁止自生成"反例字面中出现(grep -v "禁止自生成\|不得自生成\|不要自生成")

# 2. 决策 11 双不变量 grep + R1 P1-3 语义验收
grep -rn 'logger\.exception' features/paper/ api/routes/paper_user_supply.py --exclude-dir=.venv --exclude-dir=.git
# 期望:0 命中

grep -rn 'asyncio.to_thread' features/paper/paper_plan_service.py --exclude-dir=.venv --exclude-dir=.git
# 期望:≥ 1 命中,且只出现在 _call_llm_json / _call_text_provider_json 内部(R1 P1-3 改语义验收;不卡命中数 ≥ 4)
# 配套单测断言:test_paper_plan_service.py::test_all_role_helpers_use_call_llm_json + test_call_llm_json_bridges_via_asyncio_to_thread

# 3. 决策 21 boundary grep
grep -rnE '(^|[[:space:]])(from|import)[[:space:]]+features\.(overview|explanation)|features\.(overview|explanation)\.' features/paper/ --exclude-dir=.venv --exclude-dir=.git
# 期望:0 命中

grep -rnE "EvidencePack|ExplanationPack|_evidence_builder|overview_schemas|ProjectOverview" features/paper/ --exclude-dir=.venv --exclude-dir=.git
# 期望:0 命中

# 4. 本卡红线 15 项实测(逐文件;R1 P2-4 加 paper_spec_extract.yaml 完全不动)
for f in \
  core/domain/project_overview.py \
  features/overview \
  features/explanation \
  adapters/parser/_sandbox.py \
  adapters/parser/pdf_parser.py \
  adapters/parser/docx_parser.py \
  core/interfaces/document_parser.py \
  features/paper/paper_spec_service.py \
  features/paper/paper_schemas.py \
  core/prompts/paper_spec_extract.yaml; do
  echo "=== $f ==="
  git diff --name-only origin/main -- "$f"
done
# 期望:全空(R1 P2-4:paper_spec_extract.yaml 不动)

# 5. 样本包未改(D5 接受双字面,不动 sample)
git diff --name-only origin/main -- eval/cases/paper_to_model/
# 期望:0

# 6. R1 P2-5:06 § 12.5 schema 同源校验
git diff -- docs/06_OUTPUT_CONTRACTS.md
# 期望:只 § 12.5 unit 字段附近加注释行;字段集合 / 类型 / 约束不变
pytest tests/features/paper/test_paper_schemas_freeze.py -v
# 期望:全过(无新增 / 删除字段;extra=forbid 保持)
pytest tests/features/paper/test_paper_schemas_sample_roundtrip.py -v
# 期望:全过(5 sample JSON 仍能 roundtrip)

# 7. 隐私 grep(沿用 TASK-501)
grep -rnE "logger\.(debug|info|warning|error).*file\.filename|str\(exc\)|repr\(exc\)|response\.text|response\.content" features/paper/ api/routes/paper_user_supply.py --exclude-dir=.venv --exclude-dir=.git
# 期望:空,或逐项说明是安全元数据

# 8. 对外口径(沿用 TASK-501 / TASK-500)
git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器" features/paper/ core/prompts/paper_plan_*.yaml
# 期望:0 命中

# 9. R1 P1-2 + 二审 P1-1 / P1-2 / P1-3:API error handler 场景测试
pytest tests/api/test_paper_plan_error_handler.py -v
# 期望(按 leaf 分流):
#   PaperPlanGenerationError → 502:
#     - test_paper_plan_generation_error_returns_502
#     - test_evidence_invariant_fail_llm_side_returns_502
#     - test_plan_assembler_missing_binding_not_found_returns_502(二审 P1-1)
#     - test_plan_assembler_missing_binding_ambiguous_returns_502(二审 P1-1)
#   PaperUserSupplyError → 400:
#     - test_user_supply_paper_not_found_returns_400
#     - test_user_supply_prompt_not_found_returns_400
#     - test_user_supply_prompt_duplicated_returns_400
#     - test_user_supply_parameter_name_mismatch_returns_400
#     - test_user_supply_already_filled_returns_400(二审 P0-2:value != sentinel 判定)
#     - test_user_supply_allows_sentinel_mapping_to_be_filled_once(二审 P0-2 反向)
#   Atomic merge(二审 P1-2):
#     - test_user_supply_failed_batch_does_not_mutate_cached_plan(深拷贝 + atomic)

# 10. 真启动验收(PM 配 .env DEEPSEEK_API_KEY)
# - R6.1 数字已由 R6 后置修复重新验证;两 case 真跑数字以 TASK-502.1 完工 CSV 为准
# - material_to_plan/case_01 剥离版 docx:期望 plan 含 SimPowerSystems + 8 block + 20 parameter_mapping + 8 subsystem 步;missing_prompts 为 0(剥离版无图);plan_id="PLAN-PAPER-<uuid>";paper_spec_id="PAPER-<uuid>"
# - missing_param/case_01:期望 missing_prompts 6 项(MISS-001..006);用户补充后 plan 更新含 6 个 user_supplied 项;`/user-supply` 入参不传 plan/missing,只传 batch
# - 双源 + locator 白名单人工验证(R1 P1-1)

# 11. evaluator 跑两 case
python eval/run_paper_eval.py --case material_to_plan/case_01_motor_short_circuit --output-dir /d/tmp/task-502-1-r6
python eval/run_paper_eval.py --case missing_param/case_01_missing_image_param --output-dir /d/tmp/task-502-1-r6
# 期望:R6 后置修复 CSV 给出真实 succeeded / blocked_known_defect;blocked 不得 conditional pass
```

---

## 风险清单

### 风险 1(D2 时延):DAG 端到端时延

**影响**:用户上传后等待时间过长 → UX 差。

**规避**:
- D1-B′ DAG 编排端到端 = `max(MissingDetector, PlanComposer→SubsystemPlanner, MScriptDrafter)` ≈ `max(30s, 30+30s=60s, 30s)` = **~60-80s**(若 LLM 响应正常)
- HTTP timeout 设 180s
- 若超 60s:前端显示"生成中..."loading 状态(TASK-503 前端范围)
- v0.3+ 评估 202 Accepted + polling(留 TASK-503)

### 风险 2(D5 双字面):LLM 输出 unit 字面漂移

**影响**:同情况有时输出 null 有时 `"—"`,evaluator equivalence class 不匹配 → A2 Fail 误判。

**规避**:
- prompt 教 LLM "工程推断 / 无物理单位时优先 null"(§ 7.5 shared snippet 字面)
- evaluator `is_unitless(unit)` equivalence class:`return unit is None or unit == "—"`(`_paper_eval_metrics.py`)
- v0.2 sample 扩充时统一字面(挂账 v0.5 协议)

### 风险 3(缺参语义):PlanComposer 编造缺失参数值

**影响**:PlanComposer 输出的 parameter_mapping 含 LLM 编造的 H/F/变压器参数,但 MissingDetector 同时识别它们为缺失 → 矛盾(GPT R0 跨决策点冲突 #3)。

**规避**:
- PlanComposer prompt 显式教 "参数值不在 PaperSpec.parameter_table 中时,填 `value='null'`(字符串),不要编值"(§ 7.7 角色特有反例)
- PlanAssembler (Python) 阶段 binding:遍历 missing_prompts → 给 plan.parameter_mapping 对应 `value='null'` 项标 `missing_param_prompt_id=<MISS-XX>`
- 测试用例覆盖:test_paper_plan_helpers.py 含 PlanAssembler.merge happy path + 边界 case(无 missing / 全 missing)

### 风险 4(EvidenceTagger fail-fast 误判)

**影响**:LLM 输出 evidence 偶有不满足双源不变量 → 整 case 抛 `PaperPlanGenerationError`,降级"unable to generate plan"。

**规避**:
- prompt 教 LLM 严格双源契约(§ 7.5 shared snippet 双源契约红线)
- 单测覆盖 6 种 evidence 反例(对齐 TASK-501 `test_evidence_invariant_violations_rejected` 模式)
- 若 LLM 输出确实偏差大,留 R6 真启动后 prompt 微补丁(沿用 TASK-501 v0.3.3 / v0.3.4 路径,K_30 反例归档)

### 风险 5(共享 snippet 漂移):shared snippet 与 4 prompt yaml 字面不同步(D8b)

**影响**:shared snippet 修订时漏同步 prompt yaml(K_30 风险)。

**规避**:
- shared snippet 由 `_prompt_builder.py::_shared_paper_plan_constraints()` 函数注入,**不在 yaml 中复制**(D8b A-lean)
- prompt yaml 的 system 段只写 role 特有字段,共享部分由代码注入
- test_paper_plan_prompts.py 含 "shared snippet 注入后 4 个 system 段都含 X / Y / Z 字面" 断言

### 风险 6(GPT R0 K_30-1):TASK-501 接力描述漂移

**影响**:TASK-501 任务卡 § 后续 task 接力点字面写"9-component 单 yaml",与 TASK-502 D1-B′ 4 yaml 拆分冲突。

**规避**:
- TASK-502 v0.1 § 上下文 已显式纠正字面("9 component 是评测组件清单,非 prompt yaml 数量")
- v0.5 协议候选第 19 项挂账:任务卡 § 后续 task 接力点字面措辞规则(K_30 子规则)

### 风险 7(DeepSeek API rate limit):4 并发 LLM call 触发 rate limit

**影响**:DeepSeek API 单账号并发限制可能阻塞 asyncio.gather。

**规避**:
- TASK-501 真启动已验证 1 LLM call(PaperSpecService)在 DeepSeek-V3 单账号下可跑
- 本卡 3 并发(MissingDetector + PlanComposer + MScriptDrafter)+ 1 后续(SubsystemPlanner)= 单 case 最多 4 个 LLM call
- 若触发 rate limit,沿用 TASK-203 v0.3 已落 LLMRateLimitError handler(由 `_deepseek_errors.translate_openai_error` 翻译)
- 真启动监测 rate limit error;若 ≥ 2 次/分钟,加 client-side throttle(留 R6 后补丁)

### 风险 8(LLM 输出 JSON parse 失败)

**影响**:DeepSeek-V3 输出非纯 JSON(含 markdown 包裹 / 解释文字)→ `json.loads` 失败 → `PaperPlanGenerationError`。

**规避**:
- prompt 段共享 snippet 明示 "只返回有效 JSON 对象;不要 markdown,不要解释文字"(§ 7.5)
- 沿用 TASK-501 v0.3.3 / v0.3.4 真启动 prompt 微补丁经验
- `json_mode=True` 调用 DeepSeek `response_format={"type": "json_object"}`
- 若真启动出现 JSON parse 失败,走 decision-15 diagnose-before-fix(停手报 PM,不自决修)

### 风险 9(R1 P0-3:InMemoryPaperPlanCache 跨请求一致性)

**影响**:`/upload-document` 写 cache,`/user-supply` 读 cache;若 uvicorn 多 worker(N>1),cache 在多个进程内不共享,会出现"刚上传成功的 paper_id 在 user-supply 端 paper_not_found"。

**规避**:
- v0.1 范围:**单 worker 部署**(对齐 TASK-501 真启动模式;`uvicorn --workers 1`)
- 任务卡 § 给 Codex 提示 + R6.1 真启动验收命令 显式标注 "单 worker"
- TASK-503 替换为 `SqlitePaperPlanCache` 后,多 worker 可启用
- 若 v0.1 真启动出现 paper_not_found 但 paper 实际上传过 → 立即排查是否多 worker

### 风险 10(R1 P1-2 + R1 二审 P1-3 leaf 分流后,**风险已大幅降低,留作历史**)

**影响**:R1 一审 P1-2 起稿时,`PaperPlanGenerationError` 同时承载 LLM 侧(502)+ 用户输入侧(400),依赖 service raise 时设置 `reason / context` 字段分流;若漏设会回退到统一 500。

**v0.1.2 R1 二审 P1-3 修订后**:新增 `PaperUserSupplyError(MxaError)` leaf,error_handler 按 leaf class 直接映射,**无需 service 在 raise 时设置 reason 字符串前缀**,Codex 实现边界更硬;本风险已大幅降低,留作历史 + Codex 二次摸底反馈记账(D2 K_30,架构师 v0.1.2 漏改本段旧文案,v0.1.3 微补丁修复)。

**规避**(v0.1.3 终态):
- UserSupplyService 4 条归属校验 + atomic merge 校验失败 → 抛 `PaperUserSupplyError(reason=...)`,error_handler 直接按 leaf class 翻译 400
- PaperPlanService DAG / PlanAssembler binding cardinality / EvidenceTagger LLM 侧 invariant → 抛 `PaperPlanGenerationError(reason=...)`,error_handler 直接按 leaf class 翻译 502
- **不用 reason.startswith / reason in 字符串前缀分流**(R1 二审 P1-3 字面)
- 完整 7 种错误场景测试覆盖(§ R6.1 第 9 项,按 leaf 分组)

---

## Checklist(精简)

**实施前**:

- [ ] 已读宪法 v3.1 / 02 v3.0 / 04 / 05 § 8 § 9.2 / 06 § 12 / 决策 22 / 决策 21 / 决策 11 / 决策 18 / 决策 15
- [ ] 已读 TASK-501 § 接力点(v0.1 已字面修订 9-component 字面) + § 7 服务模式
- [ ] 已读 scoring_template + verification_method + 2 case_README
- [ ] 实地 grep `core/domain/exceptions.py` 含 `DocumentParseError` + `PaperSpecGenerationError`(本卡新增 `PaperPlanGenerationError`)
- [ ] 实地 grep `features/paper/paper_schemas.py` 含 5 顶层 + 6 nested Pydantic wrapper
- [ ] 实地 grep `core/prompts/paper_spec_extract.yaml` version 字段 = `"v0.3"`
- [ ] 实地核查 base:`git merge-base --is-ancestor a3fbeb491d9543aabfd4a90a02002e7d006fe08a origin/main`(0 退出 = main 已含 TASK-501 + chore 基线;R1 P2-3 修订)
- [ ] 实地核查 12 个样本包文件齐全 + JSON 合法(参考 TASK-500 v0.2.1 § Stage 0 #3)
- [ ] 理解 D1 DAG 编排(MissingDetector ∥ PlanComposer ∥ MScriptDrafter ; SubsystemPlanner ; PlanAssembler)
- [ ] 理解 EvidenceTagger fail-fast 角色(GPT R0 #6:不凭空生成 / 不改 source)
- [ ] 理解 D4 私有 schema 边界转换
- [ ] 理解 D5 双字面(schema 接受双 / prompt 优先 null / evaluator 等价)
- [ ] 理解 D8b shared snippet 注入而非复制
- [ ] 理解 D8a sandbox / paper_spec / parser 红线(若发现 PaperSpec 缺陷停手报 PM)
- [ ] **R1 P0-1 理解:`ParameterMapping` 5 字段公开 contract 锁定;binding 用私有 `MissingBindingModel` 落地,不进 plan / 不进 06**
- [ ] **R1 P0-2 理解:`PaperPlanService.generate(spec, paper_id)`;Python 注入 `plan_id = f"PLAN-{paper_id}"`;LLM 逐字照抄,不自生成 ID**
- [ ] **R1 P0-3 理解:`InMemoryPaperPlanCache`(内存,留 TASK-503 SQLite);`/user-supply` 入参只接 `{user_supplied_responses}`**
- [ ] **R1 P1-1 理解:`EvidenceTagger.validate_for_spec(evidence, spec)` 覆盖 plan.evidence + BlockRecommendation.paper_reference + MissingParameterPrompt.paper_reference**
- [ ] **R1 P1-4 理解:`MISSING_VALUE_SENTINEL = "null"` 常量,三处显式(prompt 校验 / evaluator 命中 / UserSupply 覆盖)**
- [ ] **R1 P1-5 理解:UserSupplyService 4 条归属校验(prompt_id 不存在 / 重复 / parameter_name 不一致 / 已填)**
- [ ] **R1 P2-2 理解:MScriptDrafter 验收降级(可 null;只评 shape;不评 MATLAB 语法可运行)**

**完工前**:

- [ ] § 验收清单全过
- [ ] § R6.1 完工实测命令全过 + 输出贴 PR(D7 含 mypy + 决策 11 grep + 决策 21 boundary + 红线 15 项 + 样本未改 + 隐私 grep + 对外口径 grep)
- [ ] 真启动两 case 真实数字以 TASK-502.1 CSV 为准(material_to_plan + missing_param;PM 配 `.env` DEEPSEEK_API_KEY)
- [ ] evaluator 仅在两 case 均 `succeeded` 且各自 ✅ 或 🟡 + 0 E1 / E2 一票否决时通过;`blocked_known_defect` 不得 conditional pass
- [ ] commit subject 单行无 body(反例 17)
- [ ] 完工三件套(决策 08)
- [ ] 03 索引字节级修订(TASK-502 🔲 → 🔍,LF/CRLF 双试)
- [ ] PR(Codex 给 PM 标题 + 正文,PM 走 GitHub 网页创建 + squash merge)

---

## 后续 task 接力点

### 直接阻塞(等本卡合并)

- **TASK-503:TuningSuggestion service + UX 闭环 + GET 路由 + 持久化 cache**
  - 范围:TuningSuggestion service(06 § 12.6;本任 v0.1 不消费 TuningSuggestion,本任卡 § 上下文也未跑 § 12.6 sample × schema sanity check — 留 TASK-503 起稿期补)+ 前端 MissingParameterPrompt UI + 用户补充表单 + GET /api/v1/papers/{paper_id}/plan + SqlitePaperPlanCache 持久化(对齐 TASK-204 模式)
  - 复用本卡:
    - `UserSuppliedResponseModel` 评估是否提升 06 § 12.9 公开 contract(D4 D-D 演进路径,GPT R0)
    - PaperPlanService 接口
    - EvidenceTagger + PlanAssembler helper
    - evaluator 框架 + LLM-as-judge 自动化(scoring_template § 5.2 v0.2)
  - 估时:2-3 周

### 可复用 / 未来解锁

- `SqlitePaperPlanCache(PaperPlanCache)`:对齐 TASK-204 模式,留 TASK-503
- Layer 1 LLM-as-judge 自动化:留 v0.2(scoring_template.md § 5.2 演进路径)
- 多文档融合 / 图片 OCR / 控制 + 信号处理样本扩充:留 v0.2(决策 23 § 2.1)
- ParameterMapping.unit 字面统一(`"—"` → `null`):留 v0.2 sample 扩充期,走 task-500 v0.2.2 微补丁

---

## 给 Codex 的提示

### 工艺约束

- **K_28a 兜底**(决策 09 + 反例 6):任务卡任何精确字面(commit hash / 文件路径 / class 名 / 字段名)起稿前必先 `grep` / `view` 实测;**不凭印象写**
- **决策 15 diagnose before fix**:遇 ValidationError / 测试 fail / CI fail / `git mv` fail / push 401 **停手报 PM 给 traceback**,不凭印象自决修(沿用 TASK-501 工艺,Codex K_15 反例 6 次生效)
- **决策 11 双不变量**:
  - async 内同步重活必须 `asyncio.to_thread` 桥接(本卡 4 LLM call + 校验 helper)
  - 业务异常分支禁 `logger.exception`,改 `logger.error(..., type(exc).__name__) + from None`
- **决策 21 boundary**:`features/paper/` 不 import `features/overview/` / `features/explanation/` 私有结构;`core/domain/paper_*.py` 不 import 任何 `features/`

### D 红线兜底

- **D7 mypy 双兜底**:R6.1 完工显式跑 `mypy core/ adapters/ features/paper/ api/` + 贴 0 error 输出(v0.5 协议第 17 项落地)
- **D8a sandbox 红线**:**不动** `adapters/parser/_sandbox.py` / spawn / `pdf_parser.py` / `docx_parser.py` / `paper_spec_service.py` / `paper_schemas.py`;若发现 PaperSpec locator 缺陷,**停手回报 TASK-501 缺陷**,不在 502 顺手修 parser
- **D8b shared snippet**:不复制粘贴 system 段;走 `_prompt_builder.py::_shared_paper_plan_constraints()` 函数注入;若 TASK-501 `paper_spec_extract.yaml` v0.3 需要 refactor 抽出共享段,**只 refactor 不改 LLM 行为**(LLM 行为是 D8a 兜底红线)
- **缺参语义**(GPT R0 跨决策点冲突 #3):PlanComposer prompt 教 LLM `value="null"` 字面占位,**不编值**;PlanAssembler 后置 binding `missing_param_prompt_id`

### 范围警惕

- 任何动到 15 项红线 / 样本包字面 / 06 § 12.4 / 12.6 / 12.7 字段表 = **立即停手报 PM**(沿用 TASK-501 chore PR / #98 模式)
- 真启动 + Layer 1 + Layer 2 评测:默认 Codex 做,PM 提供 `.env` DEEPSEEK_API_KEY + 剥离版资料即可(v0.5 协议第 13 项落地)

### Stage 0 必跑(本卡)

1. **`git fetch origin && git merge-base --is-ancestor a3fbeb491d9543aabfd4a90a02002e7d006fe08a origin/main`**(R1 P2-3:非 0 退出 = main 未含 TASK-501 + chore 基线,停手报 PM;允许 main 合法前进 — 即任务卡 chore / 索引 chore 已合并;**不再要求 main HEAD 等于固定 hash**)
2. `find eval/cases/paper_to_model -type f` 列 12 文件齐全(对齐 TASK-500 v0.2.1 Stage 0 模式)
3. `cat core/prompts/paper_spec_extract.yaml | head -5` 见 `version: "v0.3"`
4. `grep -c "class PaperSpecService" features/paper/paper_spec_service.py` = 1
5. `grep -c "class PaperPlanGenerationError" core/domain/exceptions.py` = 0(本卡新增,Stage 0 应不存在)
6. **`grep -c "class InMemoryPaperPlanCache" features/paper/paper_plan_cache.py 2>/dev/null` 或文件不存在**(R1 P0-3:本卡新增)
7. **`grep -c "MissingBindingModel" features/paper/paper_plan_helpers.py 2>/dev/null` 或文件不存在**(R1 P0-1:本卡新增)
8. **`grep -c "validate_for_spec" features/paper/paper_plan_helpers.py 2>/dev/null` 或文件不存在**(R1 P1-1:本卡 EvidenceTagger 签名为 validate_for_spec,非 validate)
9. **真启动 single-worker 启动**:`uvicorn api.main:app --workers 1 --port 8000`(R1 风险 9:InMemoryPaperPlanCache 单进程一致性)

### Commit + PR

- commit subject 单行无 body(反例 17)
- PR:Codex 给标题 + 正文草稿,PM 走 GitHub 网页创建 + squash merge(对齐 TASK-501 PR #97 / chore PR #98 模式)
- 走 feature branch `feat/TASK-502-paper-plan`(不许 main 直推,对齐 04 § 1.4 反例 6)

---

## 反例账目(本任 v0.1.2 终版累积,GPT R0 摸底 + GPT R1 一审 + GPT R1 二审集成)

**v0.1 起稿期**(R0 集成版):

- 架构师 K_28a +0(全程 view / grep / Codex 摸底报告实测,无凭印象)
- **K_30 +1**(GPT R0 抓出,关键):TASK-501 § 后续 task 接力点字面"9-component 单 yaml"假设,与 TASK-502 D1-B′ 4 yaml 拆分冲突;本任 § 上下文 显式纠正字面
- GPT R0 反方向反例 +0 / 架构师反 challenge GPT +0

**v0.1 → v0.1.1 修订期**(R1 一审集成):

- **K_30 +10**:P0-1 ParameterMapping 撞 schema / P0-3 API 边界 / P1-1 EvidenceTagger 漏 spec / P1-2 漏 handler / P1-4 漏 sentinel 常量 / P1-5 归属校验漏 / P2-1 validator 用注释 / P2-2 验收范围偏重 / P2-4 paper_spec_extract.yaml refactor 允许 / P2-5 06 注释漏 schema 同源
- **K_28a +3**:P0-2 LLM 自生 ID 凭印象 / P1-3 grep ≥ 4 凭印象 / P2-3 hash 写死凭印象
- GPT R1 一审反方向 +0 / 架构师反 challenge GPT +0

**v0.1.1 → v0.1.2 修订期**(R1 二审集成,**关键反思**):

- **K_30 +7**(架构师 v0.1.1 修订时未做反向 grep,导致 7 项内部字面互撞 / 字面残留 / 逻辑反 / 接口设计漏):
  - **P0-1**:阶段 3 文字"plan_id / paper_spec_id 自生成"残留(与 § 7.7 PlanComposer prompt 字面 + 主接口签名互撞)— 经典 v0.5 #20 内部字面互撞反例
  - **P0-2**:§ 7.2 接口契约"已填"判定 `== sentinel` 写反(与 § 阶段 2 文字 `!= sentinel` 互撞)— 经典内部字面互撞
  - **P1-1**:PlanAssembler binding cardinality fail-fast 漏(0 / 多命中未写)
  - **P1-2**:UserSupplyService atomic merge 漏(深拷贝未规定,失败可能污染 cache)
  - **P1-3**:`PaperPlanGenerationError` 同时承载 502/400 偏脆(reason 字符串前缀分流 Codex 实现易错)
  - **P2-1**:`UpdatedPlanResponse.plan` vs `updated_plan` 字段名残留(§ 7.10 已对,阶段 2 文字未同步)
  - **P2-2**:`PaperPlanRecord` "4 字段 record" 不准(实际 5 字段)
- **K_28a +0**(本次无凭印象错误;7 项全是字面 / 接口 / 逻辑反)
- GPT R1 二审反方向 +0 / 架构师反 challenge GPT +0
- **v0.5 协议候选 #20 关键反思**(挂账升级):v0.1.1 起稿期我已写下"起稿前自检内部字面是否互撞"候选规则,但实际 v0.1.1 修订时只做正向 grep(新字面落地),**没做反向 grep**(旧字面残留)→ GPT R1 二审 P0-1 / P0-2 / P2-1 都是反向 grep 能抓出的 K_30。**v0.5 协议候选 #20 子规则补**:任务卡 R 轮修订完成 self-check 必须正向 + 反向双 grep — 正向 grep 验证新字面命中,反向 grep 验证旧字面 0 残留(对齐 v0.1 → v0.1.1 我做的 6 项反向 grep,但漏了字面 logic 反 + 字段名不一致 + 数字不准三类)

**v0.1.2 → v0.1.3 修订期**(Codex 二次摸底反馈集成):

- **K_30 +1**(架构师反向 grep 漏覆盖周边字面):
  - **D2(Codex 抓出)**:v0.1.2 R1 二审 P1-3 修订时,只改了 § 输出 / § 7.10 / § 阶段 2 / § R6.1 测试命名,**漏改 § 风险 10 旧文案**"reason.startswith / reason in 字符串前缀分流" — 与 leaf 分流口径冲突;v0.1.3 微补丁修复(风险 10 改为"双 leaf 直接分流,留作历史")
- **K_28a +0**(本次无凭印象错误)
- **Codex 反方向 challenge +0**(D 段全是建设性反馈;5 项工艺承诺接受 + 1 项 K_30 抓出)
- **架构师反 challenge Codex +0**(全盘接受 D 段反馈)
- **Codex 工艺优秀加分**:Stage 0 第 1 项 "git fetch" 与"不动任何文件"指令冲突时,选保守路径 + 停手报 PM(决策 15 实践);A2 grep 漏命中时主动扩展只读搜索找到既有 api/README.md single-worker 惯例 — 工艺超出派活指令最低要求
- **v0.5 协议候选 #20 子规则增强**(关键升级):R 轮修订反向 grep 必须覆盖**所有该 R 轮修订点的旧字面**,不只是 P0 主修订点,还包括 P1/P2 周边连带字面 / 风险段次级字面 / Checklist 字面 / Codex 提示字面(v0.1.2 self-check 漏 § 风险 10 反例兜底)

**累计本任 v0.1.3 终版**:
- 架构师 K_28a +3 / **K_30 +19**(R0 +1 + R1 一审 +10 + R1 二审 +7 + Codex 二次摸底 +1)
- GPT R0 / R1 一审 / R1 二审 反方向 challenge +0 / Codex 反方向 challenge +0 / 架构师反 challenge +0
- 决策 22 § 9 趋势记账:
  - TASK-501 R1 一审 17 P0/P1 → R1 二审 12 → R1 三审 7 → R2 1 → Stage 2 实施期 2 → 真启动 2
  - **TASK-502 R0 摸底 7 跨冲突 → R1 一审 13 → R1 二审 8 → Codex 二次摸底 1**,**4 轮收敛**,无需升 R2(GPT 明确);Codex 直接进阶段 1
  - 趋势对比 TASK-501 仍向好(K_30 总累积 19 vs TASK-501 类似阶段 ~30,反例密度下降)
- 双 AI 互审 + Codex 实测 + PM 救场工艺协议沿用决策 12 v0.4
- v0.5 协议候选累积至第 21 项(#20 子规则升级 + #21 派活前自检指令字面是否内部一致),挂账待 v0.5 协议升级 task 一次性升级

---

**版本**:v0.1.3(2026-06-17,GPT R0 摸底 + GPT R1 一审 + GPT R1 二审 + Codex 二次摸底反馈集成版,**派 Codex 终版**)
**作者**:Claude(架构师,第 46 任)
**关联宪法版本**:v3.1
**前置 commit**:main 必须包含 `a3fbeb491d9543aabfd4a90a02002e7d006fe08a`(TASK-501 PR #97 + chore PR #98 squash merged after;Stage 0 用 `git merge-base --is-ancestor` 校验)
**审批历史**:
- v0.1 起稿(2026-06-17)— GPT R0 摸底全集成;K_28a +0 / K_30 +1
- v0.1.1 修订(2026-06-17)— GPT R1 一审 3 P0 + 5 P1 + 5 P2 全集成;K_28a +3 / K_30 +10
- v0.1.2 修订(2026-06-17)— GPT R1 二审 2 P0 + 3 P1 + 3 P2 全集成;K_28a +0 / K_30 +7
- **v0.1.3 微补丁(2026-06-17)— Codex 二次摸底反馈 D2 K_30 修复(风险 10 leaf 分流口径);K_28a +0 / K_30 +1**
**审批级别**:GPT R0 + R1 一审 + R1 二审 + **Codex 二次摸底 4 轮全通过**(B 段 6/6 任务卡理解自检 + A 段 9 项 Stage 0 实测) → PM 拍板入仓路径 → 派 Codex Stage 0 进阶段 1
**关联协议**:决策 12 v0.4(沿用);v0.5 协议候选累积至第 21 项(挂账)
**入库时改名**:本任卡入 `docs/tasks/task-502-paper-plan.md`(去掉版本号后缀,对齐 TASK-501 chore PR 模式)

---

🚀 **TASK-502 v0.1.3 完工(派 Codex 终版,4 轮 R 收敛),等 PM 拍板入仓路径 + 派 Codex 阶段 1。**

## 阶段 6 — R6 后置 defect 修复(evaluator true run)

### § 6.1 主裁决 A + 条件穿透裁决 D

- **主裁决 A(evaluator 自比)**:原 evaluator 将 golden JSON 当 actual,无法证明真实能力。R6 后置修复后,actual 只来自 `PaperSpecService` / `PaperPlanService` / `UserSupplyService` 返回值;golden 只从 fixture JSON 读取;CSV 与 4 个 actual JSON 独立落盘。
- **条件穿透裁决 D(blocked 诚实口径)**:known defect 仅 `missing_binding_not_found` 可记录为 `blocked_known_defect`;`missing_binding_ambiguous` 与其他 `PaperPlanGenerationError` 必须 re-raise。blocked case 的 B1/B2/C2/C3/D1/E1/E2 写 `N/A`,TASK-502 产品整体门槛 Fail,不得 conditional pass。

### § 6.2 设计字面 — v0.1.4 § IV D1-D11

| # | 决策 | 字面 |
|---|---|---|
| D1 | actual 真跑 | actual 只来自 service return;golden 只来自 fixture JSON;任一 `golden_* or actual_*` 禁止 |
| D2 | parser | sync ABC;7 字段;精确支持 material `S1-S5/EQ-01` 与 missing `S1-S5/EQ-01/FIG-01..05`;`datetime.UTC` 别名 |
| D3 | provider | `DeepSeekTextProvider(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)` |
| D4 | known failure | known set 仅 `missing_binding_not_found`;其他 `PaperPlanGenerationError` re-raise |
| D5 | blocked 诚实口径 | service 异常不返回 prompts;blocked 的 B1/B2/C2/C3/D1/E1/E2 均按不可评写 `N/A`;整体门槛 Fail |
| D6 | 入仓工艺 | v0.1.4 D6 原为 chore/task 合一;本次按 PM 工艺修订覆盖:不创建 v0.1.4 任务卡,decision-22 不动,只更新索引子行 + TASK-502 主卡 |
| D7 | serialization | 直接使用三类已实证 schema wrapper;wrapper 失败向上抛;禁宽 catch / fallback / `str(value)` |
| D8 | E1/E2 | E1 自动反映生产 invariant + wrapper validation;E2 比较完整 prompt/response 集合与全部 user-supplied mapping,不是一项即可 Pass |
| D9 | outputs | 每 case 输出 4 个 actual JSON + 1 个 CSV;blocked 时 4 JSON 用 `null` 表示不可得;人工 A2/C1/O1/O2 有真实审阅对象 |
| D10 | git workflow | Stage 0 / R6 同时支持 Git Bash 与 PowerShell;同步 main 后必须创建 `task/TASK-502-1-evaluator-true-run` feature branch;禁在 main 修改 |
| D11 | task vs product gate | TASK-502.1 可在诚实记录 blocked 后完成;TASK-502 整体门槛不得因此 conditional pass |

### § 6.3 反向 grep 守门

1. 历史 phantom / 错 factory / `.code`:`actual_spec = golden_spec|golden_prompts = actual_prompts|build_paper_(spec|plan)_service|compute_layer2_metrics|\.code`
2. actual/golden self fallback:`actual_[a-z_]+ *= *golden_|golden_[a-z_]+ +or +actual_`
3. 错 LocatorIndex:`(?<!Parsed)LocatorIndex`
4. 错 import:`from adapters\.text_provider|from core\.config`
5. 已删除猜测/fallback/waiver:`_SCHEMA_WRAPPERS_AVAILABLE|except Exception: *$|return str\(value\)|scoped waiver|golden_spec or actual_spec|user_input\.get\(`
6. ruff UP017 反向:`datetime\.now\(timezone\.utc\)`

### § 6.4 工艺反例账目(5 条关键实例)

1. **K_30**(R1 一审抓):evaluator `actual_spec = golden_spec or {}` self-比较 fallback
2. **K_28a**(R1 二审抓):import 路径凭印象错(`adapters.text_provider` / `core.config` → 真实 `adapters.llm` / `app.config`)
3. **K_30**(R1 三审 GPT/Codex 共抓):任务卡新增合法 helper 与反向 grep 守门词同名自撞(`_compute_layer2_metrics` → 改名 `_compute_case_layer_metrics`)
4. **K_30**(R1 三审 Codex 抓):main 已有 `UserSuppliedResponseBatch` Pydantic batch wrapper,任务卡骨架仍逐项 `.get(..., [])` → 改 `batch.model_validate`
5. **K_30**(R1 三审 Codex P0 抓,本任末轮):任务卡 parser 用 `datetime.now(timezone.utc)`,触发 ruff UP017 必失败 → 改 `from datetime import UTC, datetime` + `datetime.now(UTC)`

### § 6.5 R6 真启动结果

外置产物目录:`D:\tmp\task-502-1-r6`(不入 repo)。每 case 1 个 CSV + 4 个 actual JSON。

| case | execution_status | failure | 真实自动结果 |
|---|---|---|---|
| `material_to_plan/case_01_motor_short_circuit` | `blocked_known_defect` | `missing_binding_not_found` | A1=`1.0000`;B1/B2/C2/C3/D1/E1/E2=`N/A`;产品整体门槛 Fail |
| `missing_param/case_01_missing_image_param` | `blocked_known_defect` | `missing_binding_not_found` | A1/B1/B2/C2/C3/D1/E1/E2=`N/A`;产品整体门槛 Fail |
