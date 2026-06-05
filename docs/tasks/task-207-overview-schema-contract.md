# TASK-207: ProjectOverview Schema 契约文档化 + freeze 守门(Week 2 收尾)

## 状态

🔲 v0.2(R1 conditional pass / 3 P0 + 5 P1 + 3 P2 全采纳 / 不升 R2 / 可进 Codex)

---

## 审批记录

| 轮次 | 时间 | 结论 | 关键修订点 |
|:---:|:---|:---|:---|
| R1 | 2026-06-05 | **条件通过,不升 R2 / 直接进 Codex** | 3 P0 + 5 P1 + 3 P2 全采纳,转 v0.2 |

### R1 3 P0 必改(全采纳)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P0-1 | §6.4 freeze test 维度表写有 `test_top_level_field_types_frozen` 但 §7.3 伪代码漏掉;子 schema `EXPECTED_SUB_SCHEMAS` 写了 `expected_type` 但未用,`list[X]→set[X]` / `tuple[int,int] | None → tuple[int,int]` 漂移漏过 | §7.3 加 `EXPECTED_TOP_LEVEL_TYPES` + `test_top_level_field_types_frozen`;子 schema 测试 `assert field_info.annotation == expected_type` |
| P0-2 | 伪代码 ruff lint 风险:`_StrictBaseModel` import 未使用 / `metadata = {...}` 赋值未使用 / `expected_type` 解包未使用 | §7.3 删无用 import + 删 metadata 字典 + 按 P0-1 使用 expected_type |
| P0-3 | §6.4 / §11.2 写"11 passed"与参数化后实际 25+ items 不一致 | §6.4 测试数量段改述;§11.2 #2 期望改"约 25 个 test items passed,以 pytest 实际收集数为准" |

### R1 5 P1 必改(全采纳)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P1-1 | `scripts/export_overview_schema.py` 用 `write_text` 跨平台行尾漂移(决策 08 同源教训) | §7.2 改 `out_path.write_bytes(...)` 强制 LF |
| P1-2 | 文档承诺 `python scripts/export_overview_schema.py` 直跑,但 sys.path 不含项目根可能 `ModuleNotFoundError: No module named 'features'` | §6.2 + §7.2 删"直跑"承诺;只保留 `python -m scripts.export_overview_schema` |
| P1-3 | `test_schema_exported_json_parseable` 用 `cwd=project root` 写真实仓库 `schemas/*.json`,违反 D4 "测试不应有副作用" | §7.3 改 `cwd=tmp_path` + `env["PYTHONPATH"]=project_root`;读 `tmp_path / "schemas" / ...` |
| P1-4 | D5 四同源对 `project_type` 不够;R6 自己承认 `project_type` 分布 4 处(`overview_schemas.py` + `project_overview.yaml` + 05 + 06),D5 只列 4 处通用同源,漏 prompt yaml + 05 | §决策 D5 升级两层规则(通用 4 处 + project_type 加 prompt yaml + 05 共 6 处)+ PR review checklist 强制确认"prompt yaml / service 五步校验是否同步" |
| P1-5 | §11.2 验收只跑 `python -m scripts.export_overview_schema`,没跑 `make verify-schema`(D4 加的 target 未在验收里实地用) | §11.2 #14 改 `make verify-schema`,期望 exit 0;明示 drift 时 regenerate + commit |

### R1 3 P2 建议(全采纳)

| # | 建议 | v0.2 修订位置 |
|:-:|---|---|
| P2-1 | 顶部"17/32 / Week 2 6/7"事实状态 与 03 索引"16/32 / 5/7"补账文案易混淆 | §上下文加澄清句"这里 17/32 / 6/7 是事实状态;03 索引仍停在 TASK-206 🔍 / 16/32,本 Task 搭车做索引补账" |
| P2-2 | `docs/06` `project_type` 字段表不要继承 05 表格"见 core/domain/project.py";`ProjectTypeValue` 是 schema 输出层 Literal,独立于 domain enum | §7.1 docs/06 骨架 §2/§3 明示"contract 源是 `features/overview/overview_schemas.py::ProjectTypeValue`,不是 `core/domain/project.py::ProjectType`" |
| P2-3 | 反例 25 入仓决策 09 是治理日志追加,不是 schema 契约本身;D1-D6 摘要里看不到,易被 Codex / PM 误读为普通实现 | §决策 D7 新增"PM 授权治理 chore — 反例 25 入仓决策 09";摘要表加一行 |

### 升级触发条件提醒(R1 重申)

宪法 § 5 二审触发类(上传安全 / 计费 / 数据隐私)本 Task 全不涉及。**若实施期出现"改 schema 字段 / 推翻 D2 introspection 策略 / 推翻 D5 流程 / 引入新依赖 / 改 service 行为"等任一**,**必须自动升 R2**。

---

## 审批级别说明(反例 18 自检)

| 维度 | 评分 | 理由 |
|---|---|---|
| 决策密度 | **低**:D1-D6 | freeze test 维度 / 文档命名 / script 位置 / schema 演进流程 / 重复 BaseModel / pydantic 版本风险 |
| 下游扩散面 | **0 阻塞 / 3 下游消费者** | TASK-402(渲染 12 字段 UI)/ 评测脚本(05 § 10)/ Phase 2 第三方(若有)— 都只消费已 freeze 的契约 |
| 用户可见性 | **无**:零代码改动,零 API 变更,零行为变化 | 文档 + script + 测试 |
| 异步 / LLM 首次定型 | **无**:不引入新 async 模式,不调 LLM,不动 service | |
| 隐私 / 安全 | **无**:零新增数据流,零新增日志 | |

→ **一审 1 轮**(沿用 TASK-107 / 206 模式)。R1 出现"重大异议"(改 schema 字段 / 推翻范围 / 引入新依赖)自动升 R2。

---

## 上下文

### mxa-tutor 项目快速建立 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。**"不是从零学 MATLAB,而是把你手上的工程讲明白"**。学生上传 .zip 工程包(.m / .slx / .mat),后端做 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。

当前 Week 2(17/32 Task 完成,TASK-206 已 merge 进 main commit `746a76d`)。Week 2 进度 6/7 ✅,**本 Task 是 Week 2 最后一棒(第 7/7)**。

**注**(R1 P2-1):此处的"17/32 / Week 2 6/7"是事实状态(基于 main 实际 merge 历史)。`docs/03_TASK_INDEX.md` 当前仍停留在"TASK-206 🔍 / 16/32 / Week 2 5/7"补账中间态(详见 § Stage 0 #13),本 Task 搭车 chore 做索引补账(详见 § 7.5 + § 输出"修改文件清单")。

数据流(02 § 2):

```
[Parser]  SlxModel / MFile / MatMetadata / FileInfo / file_dependencies
   ↓  无 LLM,纯结构化(TASK-107)
[ProjectGraph]  nodes / edges / entry_points / execution_flow / unresolved_symbols
   ↓  调 LLM 基于 ProjectGraph 生成
[ProjectOverview / TeachingUnit / Chat]  教学化输出,带 SourceRef 证据
```

### 本 Task 在数据流的位置

**本 Task 不动数据流**。`ProjectOverview` schema 在 TASK-203(commit `871c8e2`)实施时已经完整落地于 `features/overview/overview_schemas.py`(64 行,12 字段 + 5 子 schema 全 freeze,字段约束 100% 对齐 `docs/05_EXPLANATION_STYLE_GUIDE.md` § 2.A)。TASK-203 还跑通 GPT 二审(R1 + R2)+ 8 P0 + 7 P1 反馈采纳,**schema 实战级稳定**。

本 Task **不是**创建 schema,而是把 TASK-203 实战 freeze 的 schema **提升到"项目契约级"**:

1. **`docs/06_OUTPUT_CONTRACTS.md`**:项目第六个顶层契约文档,给 TASK-402(前端) / 评测 / Phase 2 第三方消费者一个稳定 reference。05 是教学口吻规范(给 prompt + LLM),06 是输出契约(给 schema 消费者)。
2. **`scripts/export_overview_schema.py` + `schemas/project_overview.schema.json`**:Pydantic `model_json_schema()` 导出 + JSON 文件入仓,前端 / TypeScript 生成 / 第三方消费有锚。
3. **`tests/features/overview/test_schema_freeze.py`**:introspection-based freeze test,钉死 12 顶层字段 + 5 子 schema 字段名 + 约束 + Literal[7],防意外漂移。

**目的**:把"schema 偶然在 TASK-203 落地"提升为"schema 是项目级契约,后续 PR 改动必须走契约修订 review"。

### 审批级别:走 GPT 一审 1 轮(反例 18 自检)

5 维度全低(详见上表)。**0 业务代码改动**:不动 `overview_schemas.py` / 不动 `overview_service.py` / 不动 `api/routes/overview.py` / 不动 prompt yaml / 不动 service 校验五步 / 不动 ERROR_MAP / 不动配置。**纯文档化 + 守门测试 + 导出脚本**。

### 范围边界(硬约束)

**本 Task 不修改**:

- `features/overview/overview_schemas.py` — **零字段改动**(64 行不动)
- `features/overview/overview_service.py` — **零接口改动**(164 行不动)
- `api/routes/overview.py` — 端点契约 freeze,不动
- `core/prompts/project_overview.yaml` — prompt v0.1 不动(若评测需升版本归 TASK-305)
- `core/domain/exceptions.py` — 0 新增异常
- `core/domain/project.py` — 7 种 `ProjectType` enum 不动(`ProjectTypeValue` Literal 是 schema 输出层,**独立于** domain enum,不耦合)
- `app/config.py::AppSettings` — 配置零增量
- `requirements.txt` / `requirements-dev.txt` — 0 新增依赖
- TASK-201 / 202 / 203 / 204 / 205 / 206 任何文件 — 除 03 索引搭车 chore 外不动

**本 Task 明确不做**:

- ❌ 抽出 `_StrictBaseModel` 到共享基类(`features/overview/` + `features/chat/` 各一份,已知小重复,范围外,Phase 2 收口)
- ❌ 设计 B / C / D / E 类 schema(05 § 3-6,B 类是 markdown 输出无 JSON schema / D-E 类已在 `features/chat/chat_schemas.py` 落地;统一化推到 TASK-208 / Week 3)
- ❌ JSON 文本 diff 守门(版本敏感,脆弱;走 introspection 替代,见 D2)
- ❌ 把 `pydantic` 显式加进 requirements.txt(transitive 风险已知,Phase 2 chore 单独修)
- ❌ 改 prompt yaml v0.1 → v0.2(若评测要求升 prompt 归 TASK-305)
- ❌ 改 service 校验五步(D2 校验 + R2 R-2/R-3/R-4 升级,稳定)
- ❌ 加 `evidence_evaluator` / `citation_recall_metric` / 跨工程引用幻觉检测 — TASK-307 接管
- ❌ docstring linter / mypy plugin 守门 — Phase 2(超出本 Task 范围)

### 下游消费者

- **TASK-402**(上传页 + 工程导览页):消费 12 字段渲染 UI,按 `docs/06_OUTPUT_CONTRACTS.md` § 2 字段表 dispatch 卡片;`schemas/project_overview.schema.json` 可用 TypeScript codegen 生成 DTO
- **评测脚本**(`eval/run_eval.py`,05 § 10):按本 Task 契约文档的"评测维度"段对照打分
- **Phase 2 第三方**(若有,如答辩助手 / 课程导览导出):JSON Schema 是稳定锚
- **TASK-305**(教学 Prompt 优化):若评测显示 schema 字段约束需调整,通过本 Task "schema 修订流程"(D5)走 PR review;**不**绕过

### 关键宪法 / 决策引用

- **05 § 2.A**:A 类项目总览 schema 真值源(本 Task 把它提升为契约级)
- **05 § 8**:教学口吻硬约束,本 Task 契约文档复述并示反例
- **05 § 9.2**:prompt 版本号 + 评测 + PR review 流程(本 Task 不动 prompt,但"schema 修订流程" D5 模仿此模式)
- **04 § 4**:单 .py 文件 ≤ 300 行(本 Task 新建文件全 ≤ 300)
- **04 § 6**:依赖白名单(本 Task 0 新增)
- **04 § 11**:Review 检查清单(本 Task PR review 适用)
- **决策 06**:Codex 可读仓库文件 — 本文档引用其他文档路径不内联全文
- **决策 07**:03 索引更新由 Codex 必选并发 — 搭车 chore 推 TASK-206 ✅ + TASK-207 🔍(D5 例外条款)
- **决策 08**:PM 验 git 三件套 + 字节级 Python 改 docs — 03 索引 4 行 + 决策 09 反例 25 追加都走字节级
- **决策 09**:架构师必须实地核查 — 本 Task 已实地核查 8 段(2 轮 onboard + pydantic 版本 1 段)
- **决策 11**:async + logger 双不变量 — 本 Task 不引入新 async,不动日志,但 § 验收 grep 守门仍跑
- **反例 24**:docstring 漂移(本 Task **不**触发,但 freeze test 是同源防御)
- **反例 25**(候选 → 本 Task 入仓):架构师写 grep 跨平台兼容(POSIX 字符类强制)

---

## 输入(前置依赖)

### 必须已完成 Task

✅ TASK-001 / 002 / 101 / 104 / 106(commit `b1eb647`)/ 107(commit `e7d2e22`)/ 108 / 201(commit `fa7a4b0`)/ 202(commit `431a2bf`)/ 203(commit `871c8e2`)/ 204(commit `5fba99b`)/ 205(commit `dd7a1da`)/ 206(commit `746a76d`,main HEAD)。

### 上游关键契约(stand-alone 内联给 GPT R1 + Codex 通过 view 实地核查)

**`features/overview/overview_schemas.py` 真实形态**(64 行,2026-06-04 21:51 落地,本 Task **不动**):

```python
"""Pydantic schemas for generated project overview JSON."""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


ProjectTypeValue = Literal[
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
]


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntryFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=100)


class SimulinkModelEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=200)


class KeyFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)


class BlockEntry(_StrictBaseModel):
    block_name: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)


class SourceRefEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    line_range: tuple[int, int] | None = None
    block_id: str | None = None


class ProjectOverview(_StrictBaseModel):
    project_title: str = Field(min_length=1, max_length=30)
    project_type: ProjectTypeValue
    one_sentence_summary: str = Field(min_length=1, max_length=80)
    main_entry_files: list[EntryFileEntry] = Field(min_length=1, max_length=3)
    main_simulink_models: list[SimulinkModelEntry] = Field(max_length=5)
    main_execution_flow: list[str] = Field(min_length=3, max_length=7)
    key_files: list[KeyFileEntry] = Field(min_length=3, max_length=8)
    key_blocks: list[BlockEntry] = Field(max_length=10)
    knowledge_points: list[str] = Field(min_length=3, max_length=6)
    beginner_reading_order: list[str] = Field(min_length=3, max_length=6)
    likely_confusing_points: list[str] = Field(min_length=2, max_length=5)
    evidence: list[SourceRefEntry] = Field(min_length=3)
```

**关键不变量**(本 Task 契约文档 + freeze test 钉死):

1. **7 个 project_type 字面**:`control_system / signal_processing / power_electronics / communication / motor_control / new_energy / general`(三处一致:`overview_schemas.py:9-17` + `core/prompts/project_overview.yaml:11-12` + `docs/05_EXPLANATION_STYLE_GUIDE.md:62`)
2. **12 顶层字段**:见上表
3. **5 子 schema**:`EntryFileEntry` / `SimulinkModelEntry` / `KeyFileEntry` / `BlockEntry` / `SourceRefEntry`
4. **`extra="forbid"`**:`_StrictBaseModel` 基类强制,防 LLM 输出冗余字段
5. **service 校验五步**(TASK-203 D2,实地稳定):file_path / simulink file_path / block 四元组 / block_id 存在性 / line_range 合法性

**`docs/05_EXPLANATION_STYLE_GUIDE.md` § 2.A 字段约束表**(本 Task 契约文档 § 2 字段表直接对齐):

| 字段 | 必填 | 类型 | 长度 |
|---|---|---|---|
| project_title | ✅ | string | ≤ 30 字 |
| project_type | ✅ | enum | 见 core/domain/project.py |
| one_sentence_summary | ✅ | string | ≤ 80 字,一句话 |
| main_entry_files | ✅ | array | 1-3 个 |
| main_simulink_models | ✅ | array | 1-5 个,可空 |
| main_execution_flow | ✅ | array | 3-7 步 |
| key_files | ✅ | array | 3-8 个 |
| key_blocks | ✅ | array | 0-10 个,无 Simulink 时可空 |
| knowledge_points | ✅ | array | 3-6 个 |
| beginner_reading_order | ✅ | array | 3-6 步 |
| likely_confusing_points | ✅ | array | 2-5 个 |
| evidence | ✅ | array | ≥ 3 个 SourceRef |

**注**:05 § 2.A 写"main_simulink_models 1-5 个,可空"语义=数组 0-5(`Field(max_length=5)` 无 min_length);"key_blocks 0-10 个"同理。本 Task 契约文档明示语义一致。

**`core/prompts/project_overview.yaml` 真实形态**(57 行,`version: "v0.1"`,本 Task **不动**):

```yaml
version: "v0.1"
description: "Generate a beginner-friendly project overview from ProjectGraph."

system: |
  You generate a single valid JSON object for MATLAB/Simulink project overview.
  Return only JSON, with exactly these 12 fields:
  project_title, project_type, one_sentence_summary, main_entry_files,
  main_simulink_models, main_execution_flow, key_files, key_blocks,
  knowledge_points, beginner_reading_order, likely_confusing_points, evidence.

  project_type must be exactly one of:
  control_system, signal_processing, power_electronics, communication,
  motor_control, new_energy, general.

  main_entry_files entries must contain file_path and role.
  main_simulink_models entries must contain file_path and summary.
  key_files entries must contain file_path and why_key.

  Every file_path must come from the file list. Every block_name must come from
  the Simulink Block list. main_simulink_models.file_path must be a .slx file.
  BlockEntry.location must use this exact shape:
  "{file_path} / {parent_subsystem or <root>}".

  If you mention unresolved symbols, likely_confusing_points must explicitly say
  "未能确定 X" for the relevant item.

  Use a teaching tone for Chinese engineering students: concrete, gentle, and
  focused on how to read the project.
```

### 实地核查的隐私 / 工程约束

- 现有 `overview_service._parse_and_validate` 已遵守决策 11(`logger.error("..., type(exc).__name__")` metadata-only)
- `_validate_*` 五步全在 `overview_service.py:117-164`(已 TASK-203 D2 实战稳定)
- 本 Task 不引入任何 logging / async / IO 新模式

### 必读文档

- `docs/01_PROJECT_CONSTITUTION.md` § 4 壁垒 1-3(教学理解中间层 + 中文教学语境 + 证据强制)
- `docs/02_ARCHITECTURE_OVERVIEW.md` § 2 数据流 / § 3 目录(05 在 docs/ 顶层 + 06 拟新建)
- `docs/04_ENGINEERING_STANDARDS.md` § 4 文件大小 / § 6 依赖 / § 11 review checklist
- `docs/05_EXPLANATION_STYLE_GUIDE.md` § 0 总原则 / § 2.A schema / § 7 证据强制 / § 8 教学口吻 / § 9 prompt yaml / § 10 评测对齐
- `docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / `20260604-11`
- `docs/tasks/task-203-project-overview-service.md`(schema 实战落地 Task,D1-D16 决策链)
- `docs/tasks/task-206-error-handling-and-i18n.md`(最近邻一审 1 轮模板,搭车 chore + docstring 同步模式)
- `features/overview/overview_schemas.py`(实地 view 64 行字段)
- `features/overview/overview_service.py`(实地 view 164 行 service + 校验五步)
- `core/prompts/project_overview.yaml`(实地 view v0.1 prompt)

---

## Stage 0 实地核查清单(Codex 实施必跑,任一不符停手抛冲突)

> 决策 09 纪律 1 + 反例 24 + 25 教训。**架构师本地实测每条 grep 命令的输出再写**(反例 25:跨平台 grep 兼容性 / 反例 24:代码真实形态 vs 概念名假设)。
>
> **所有 grep 用 POSIX 字符类 `[[:upper:]]` / `[[:space:]]` / `[[:alpha:]]`,禁用 `\s` / `\d` / `\w` / `\b`**(反例 25 KPI)。

```bash
# 1. main HEAD + 工作树清洁
git rev-parse main
# 期望:746a76d... 或更新(若期间有 chore 合并)

git status
# 期望:clean

git log --oneline main | head -3
# 期望:746a76d TASK-206 在顶 / 与本 Task 文档时间线一致

# 2. overview_schemas.py 字段实地核查(本 Task 不动)
wc -l features/overview/overview_schemas.py
# 期望:64

grep -nE "^class [[:upper:]][[:alpha:]]+" features/overview/overview_schemas.py
# 期望:6 行(_StrictBaseModel / EntryFileEntry / SimulinkModelEntry / KeyFileEntry / BlockEntry / SourceRefEntry / ProjectOverview — 注 _StrictBaseModel 因下划线开头不匹配大写,命中 6 行而非 7)
# 实际期望明细:
#   24:class EntryFileEntry(_StrictBaseModel):
#   29:class SimulinkModelEntry(_StrictBaseModel):
#   34:class KeyFileEntry(_StrictBaseModel):
#   39:class BlockEntry(_StrictBaseModel):
#   46:class SourceRefEntry(_StrictBaseModel):
#   52:class ProjectOverview(_StrictBaseModel):

grep -cE "^[[:space:]]+[[:lower:]_]+:[[:space:]]" features/overview/overview_schemas.py
# 期望:正整数(字段定义行数,粗略锚定 schema 未漂移)

# 3. project_overview.yaml 7 类型字面 + version
grep -nE "version:|control_system|motor_control|new_energy" core/prompts/project_overview.yaml
# 期望:version: "v0.1" + 7 类型字面行命中

# 4. 05 § 2.A schema 字段表行号
grep -nE "project_title|one_sentence_summary|knowledge_points|likely_confusing_points" docs/05_EXPLANATION_STYLE_GUIDE.md | head -10
# 期望:多行命中,JSON 示例 + 字段约束表两段都有

# 5. service 校验五步 + parse_location 在位(本 Task 不动)
grep -nE "_validate_file_paths|_validate_block_entries|_validate_evidence|parse_location" features/overview/overview_service.py
# 期望:命中 4 个函数定义 + 至少 4 处调用

# 6. 路由端点契约(本 Task 不动)
grep -nE "/projects/\{project_id\}/overview|response_model=ProjectOverview" api/routes/overview.py
# 期望:1 行 GET 端点 + response_model 命中

# 7. 反例 25 NOT 在位(本 Task 入仓)
grep -cE "反例 ?25|POSIX 字符类|新增反例 25" docs/decisions/20260603-09-architect-must-verify-not-assume.md
# 期望:0(本 Task 完工后此 grep 应改命中,见 § 11.2 #11)

# 8. docs/06_OUTPUT_CONTRACTS.md NOT 在位(本 Task 创建)
ls docs/06_OUTPUT_CONTRACTS.md 2>/dev/null
# 期望:文件不存在

ls docs/ | grep -E "^06"
# 期望:空

# 9. scripts/export_overview_schema.py NOT 在位(本 Task 创建)
ls scripts/export_overview_schema.py 2>/dev/null
# 期望:文件不存在

# 10. schemas/ 目录 NOT 在位(本 Task 创建)
ls -d schemas 2>/dev/null
# 期望:目录不存在

# 11. tests/features/overview/test_schema_freeze.py NOT 在位(本 Task 创建)
ls tests/features/overview/test_schema_freeze.py 2>/dev/null
# 期望:文件不存在

# 12. 决策 11 兜底全空(继续保持)
grep -rn "logger\.exception" core/ adapters/ features/ api/ app/ scripts/ --include="*.py" --exclude-dir=.venv --exclude-dir=.git
# 期望:空

grep -rnE "str\(exc\)|repr\(exc\)|\{exc\}" core/ adapters/ features/ api/ app/ scripts/ --include="*.py" --exclude-dir=.venv --exclude-dir=.git
# 期望:空(注:repr(exc) 在 scripts/check_repo_hygiene.py 等可能合法,空 = 业务代码无 — 若命中需 view 上下文判断)

# 13. 03 索引行号(搭车 chore 前 view)
grep -nE "TASK-205|TASK-206|TASK-207|Week 2|总计" docs/03_TASK_INDEX.md | head -10
# 期望:
#   119: TASK-205 ... ✅ ...
#   120: TASK-206 ... 🔍 ...     ← 待推 ✅
#   121: TASK-207 ... 🔲 ...     ← 待推 🔍
#   338: Week 2 [✅✅✅✅✅🔍⬜] 5/7  ← 待推 6/7
#   342: 总计: 16/32             ← 待推 17/32
```

**任一不符停手抛冲突给 PM**(决策 08 第 2 条 + 决策 09 纪律 1)。

---

## 输出(交付物)

### 新增文件清单(4 个)

| 路径 | 行数 | 用途 |
|---|---:|---|
| `docs/06_OUTPUT_CONTRACTS.md` | ~250 | A 类项目总览契约文档(项目第六个顶层契约 doc) |
| `scripts/export_overview_schema.py` | ~70 | `model_json_schema()` 导出 + JSON 文件入仓 |
| `schemas/project_overview.schema.json` | (生成产物) | Pydantic 导出 JSON,前端 / 第三方消费 reference |
| `tests/features/overview/test_schema_freeze.py` | ~150 | introspection-based freeze test(版本无关) |

总新增 ~470 行 Python + Markdown + JSON。所有 .py 文件 ≤ 300 行(04 § 4)。

### 修改文件清单(2 chore + 1 决策追加)

| 路径 | 修改 |
|---|---|
| `docs/03_TASK_INDEX.md` | **搭车 chore**(字节级 Python,决策 08 第 2 条 + 决策 07):TASK-206 🔍→✅(**PM 本次显式授权的历史状态补账,沿用 TASK-206 D5 同款一次性授权,不作为后续先例**)+ TASK-207 🔲→🔍 + Week 2 进度条 5/7→6/7 + 总计 16/32→17/32 |
| `docs/decisions/20260603-09-architect-must-verify-not-assume.md` | **搭车 chore**(字节级 Python,沿用反例 21-24 末尾追加同款 patch 模式):末尾追加反例 25(架构师写 grep 跨平台兼容性,POSIX 字符类强制,KPI 升级) |
| `Makefile` | **可选搭车**(若 D4 选 A):新增 `export-schema` + `verify-schema` 两个 target;若 D4 选 B 则不动 Makefile |

**注**:Makefile 改动看 D4 决策。本 v0.1 倾向 **D4 选 A**(加 target),但 R1 可挑战。

### 新增依赖

**0 个**。pydantic 已是 transitive 依赖(2.12.4),`model_json_schema()` 标准库内置。

### 文件不动确认清单(范围边界守门)

完工时 `git diff --name-only origin/main..HEAD` 应**只**含上表 4 新建 + 2 chore + 可选 1 Makefile,**不**含:

- `features/overview/*.py`(所有现有文件)
- `features/chat/*.py`
- `core/**`
- `adapters/**`
- `app/**`
- `api/**`(routes / middleware / dependencies / main / schemas)
- `requirements*.txt`
- `pyproject.toml` / `.github/workflows/ci.yml`

---

## API Schema 与路由契约

**本 Task 不动 API**。`GET /projects/{project_id}/overview` 已在 TASK-203(commit `871c8e2`)落地,response_model = `ProjectOverview`(已 freeze)。

本 Task 把已落地的 schema **文档化**为契约,**导出**为 JSON,**守门**防漂移。

---

## 接口契约

### 6.1 `docs/06_OUTPUT_CONTRACTS.md` 文档结构

10 个段,~250 行 Markdown(详细 § 7.1)。**总原则**:契约文档是"消费者 reference",不是教学规范(05)的复制;不重复 05 § 8 教学口吻全文,引用即可。

### 6.2 `scripts/export_overview_schema.py` 接口

```python
"""Export ProjectOverview Pydantic schema to schemas/project_overview.schema.json.

Run as a module from project root:
    python -m scripts.export_overview_schema

Output:
    schemas/project_overview.schema.json (overwrite if exists)

Exit code:
    0 = success
    non-zero = output dir not writable / JSON serialization failed

This script is idempotent: running it multiple times produces the same JSON
(modulo pydantic version diff). It does NOT validate against an existing
baseline — see tests/features/overview/test_schema_freeze.py for drift
detection.

Note: direct invocation as `python scripts/export_overview_schema.py` is
NOT supported, because sys.path[0] would be scripts/ and the
`from features.overview...` import would fail. Always use `python -m`.
"""

import json
import sys
from pathlib import Path

from features.overview.overview_schemas import ProjectOverview


def main() -> int:
    schema = ProjectOverview.model_json_schema()
    out_path = Path("schemas") / "project_overview.schema.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # R1 P1-1: write_bytes to lock LF line ending cross-platform (决策 08 同源)
    out_path.write_bytes(
        (json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(f"Exported schema to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**关键不变量**(R1 P1-1 + P1-2 修):

- 入口仅 `python -m scripts.export_overview_schema`(项目根跑,sys.path[0] 是项目根,可 import features.*)
- **不**支持 `python scripts/export_overview_schema.py` 直跑(sys.path 不含项目根,`ModuleNotFoundError`;若误跑直接报错失败,不静默生成错误 JSON)
- 输出路径**字面常量** `schemas/project_overview.schema.json`(本 Task 文档 freeze 路径)
- `mkdir(parents=True, exist_ok=True)` 保证幂等
- `ensure_ascii=False` 保留中文(字段 description 若含中文则可读)
- `indent=2 + 末尾 newline + write_bytes` 强制 LF 跨平台稳定(决策 08 教训:Windows / Git Bash / CI 一致 LF)
- 出错抛异常自然冒泡,Python exit code 非零;**不**捕异常翻译中文(scripts/ 工具脚本,非用户面)

### 6.3 `schemas/project_overview.schema.json` 文件

由 § 6.2 script 生成,**进 git**。

**入仓理由**:

1. 前端 / TypeScript codegen 需要稳定的本地 reference(否则 CI 临时生成,前端开发本地拉 main 看不到)
2. 第三方消费者 / 文档站可以直接 link 到 GitHub raw URL
3. PR diff 可见 schema 实际变化(`model_json_schema()` 输出在 pydantic 主版本内稳定)

**不做文本 diff 守门**(D2):pydantic 2.12 → 2.13 升级可能因 `title` / `$defs` / `examples` 字段处理差异导致 JSON 文本变化,但**语义不变量**(12 字段名 + 类型 + 约束 + Literal[7])稳定。文本 diff 会脆,语义 introspection 不会脆。

**升级流程**:

1. 升 pydantic 主版本 → 跑 `python -m scripts.export_overview_schema` regenerate JSON
2. git diff 看 JSON 文本变化,人工确认是"pydantic 格式细节"还是"schema 语义变化"
3. 若仅格式细节,作为 chore commit 入 PR
4. 若涉及语义变化,触发 D5 schema 修订流程

### 6.4 `tests/features/overview/test_schema_freeze.py` 测试维度

introspection-based,~180 行。**测试函数数 11 个**(test function 级),**pytest 收集 item 数 ~30 个**(因 parametrize 展开:顶层 11 case + 子 schema 5 case + extra forbid 6 case + 顶层类型 11 case + 其他单测 4 个 = 37 上限,实际以 pytest 收集为准)(R1 P0-3 修)。完整伪代码见 § 7.3。**核心维度**:

| 测试 | 维度 | 防漂移目标 |
|---|---|---|
| `test_top_level_field_names_frozen` | 12 字段名清单 | 防字段加 / 删 / 改名 |
| `test_top_level_field_types_frozen`(R1 P0-1)| 12 字段 annotation 精确比对 | 防 `list[X]` 变 `set[X]` / `list[str]` 变 `list[bytes]` |
| `test_top_level_field_constraints_frozen` | min/max_length 数值 | 防约束放宽 / 收紧 |
| `test_project_type_literal_frozen` | 7 类型字面有序 | 防加 / 删 / 改类型 |
| `test_sub_schema_fields_frozen`(R1 P0-1 升级)| 5 子 schema 字段名 + **annotation** + 约束 | 防 `tuple[int,int] \| None` 变 `tuple[int,int]` / 子字段漂移 |
| `test_extra_forbid_at_all_levels` | 6 个 schema 类 `extra="forbid"` | 防意外放宽 |
| `test_schema_exported_json_parseable`(R1 P1-3 修)| 在 `tmp_path` 内跑 export script + JSON 合法 | 防 export script 失效 + 测试不污染仓库 |

**主动演进流程**(D5):若有 PR 要改 schema(加字段 / 改约束),作者必须:

1. 改 `overview_schemas.py`
2. 改 `tests/features/overview/test_schema_freeze.py` 对应测试断言(让 freeze test 重新 pass)
3. 改 `docs/06_OUTPUT_CONTRACTS.md` § 2 字段表
4. 跑 `python -m scripts.export_overview_schema` 重生成 JSON
5. **同时** 4 处 PR diff 才能合并(三同源 + JSON 同步)
6. PR review checklist 加一行确认("schema 修订 4 同源")

→ freeze test **不阻止**演进,但**强制**走显式同步流程,防 schema 偷偷漂移。

---

## 实施细节

### 7.1 `docs/06_OUTPUT_CONTRACTS.md` 详细骨架(~250 行)

```markdown
# 教学输出契约 · OUTPUT CONTRACTS

> 本文是 mxa-tutor 教学输出的**契约级 reference**,给前端、评测、第三方消费者使用。
> 与 `05_EXPLANATION_STYLE_GUIDE.md` 的关系:05 是**给 LLM 的教学口吻规范**(prompt + 输出格式期望),06 是**给 schema 消费者的稳定 reference**(字段名 + 类型 + 约束 + 语义)。
> 与本文冲突的实现 / PR,**一律打回返工**。
> **版本:v0.1(本 Task 起 freeze)**

## 0. 范围

本文覆盖 A 类(项目总览,JSON schema)。

不覆盖:
- B 类 Simulink Block 讲解(markdown 输出,无 JSON schema,见 05 § 3)
- C 类 MATLAB .m 文件讲解(同上,见 05 § 4)
- D 类 问答 QA(见 features/chat/chat_schemas.py,TASK-205 已落地 DTO)
- E 类 不确定回答(同 D 类,is_fallback / fallback_reason 字段)

B-E 类 schema 统一化推到 TASK-208 / Week 3。

## 1. 契约级别

A 类 ProjectOverview schema 处于**契约级**:

- ✅ 实现源:`features/overview/overview_schemas.py`
- ✅ JSON 导出:`schemas/project_overview.schema.json`
- ✅ Freeze 测试:`tests/features/overview/test_schema_freeze.py`
- ✅ Prompt 对齐:`core/prompts/project_overview.yaml`
- ✅ Service 校验:`features/overview/overview_service.py` 五步校验

任一修改必须按 D5 两层同源(通用 4 处 + project_type 6 处)(详见 § 7 schema 修订流程)。

## 2. 字段表(12 顶层 + 5 子 schema)

### 2.1 顶层字段

| 字段 | 类型 | 约束 | 语义 | 教学要求 |
|---|---|---|---|---|
| project_title | string | 1-30 字 | 工程标题 | 学生看到的卡片标题 |
| project_type | enum(7) | 见 § 3 | 工程分类 | 影响 UI 模板 + 知识点关联;契约源 `features/overview/overview_schemas.py::ProjectTypeValue`,**不是** `core/domain/project.py::ProjectType`(05 § 2.A 表写"见 core/domain/project.py"是历史描述,本契约文档以 schema Literal 为真值源,R1 P2-2)|
| one_sentence_summary | string | 1-80 字 | 一句话讲清楚做什么 | 像老师介绍课题,不是百科定义 |
| main_entry_files | array[EntryFileEntry] | 1-3 个 | 主入口脚本 | 学生第一个该看的文件 |
| main_simulink_models | array[SimulinkModelEntry] | 0-5 个 | 顶层 Simulink 模型 | 可空(纯 .m 工程) |
| main_execution_flow | array[string] | 3-7 步 | 工程执行流 | 自然语言句子,不是函数名清单 |
| key_files | array[KeyFileEntry] | 3-8 个 | 关键文件 | 不是所有文件,只是"学生该看的" |
| key_blocks | array[BlockEntry] | 0-10 个 | 关键 Simulink block | 可空 |
| knowledge_points | array[string] | 3-6 个 | 关联课程知识点 | 对齐中文教材术语 |
| beginner_reading_order | array[string] | 3-6 步 | 阅读顺序建议 | 必须给具体动作,不能写"先理解基础概念" |
| likely_confusing_points | array[string] | 2-5 个 | 学生看了工程会问的问题 | 不是教科书难点 |
| evidence | array[SourceRefEntry] | ≥ 3 个 | 证据引用 | 壁垒 3,无证据不许硬答 |

### 2.2 EntryFileEntry / SimulinkModelEntry / KeyFileEntry

[字段表 + 长度 + 示例]

### 2.3 BlockEntry

[4 字段 + location 格式硬约束 "{file_path} / {parent or <root>}"]

### 2.4 SourceRefEntry

[3 字段 + line_range tuple[int, int] + block_id 可选]

## 3. project_type 7 枚举值

> **契约源**(R1 P2-2):`features/overview/overview_schemas.py::ProjectTypeValue`(`Literal[7]` 字面)。**不是** `core/domain/project.py::ProjectType`(domain enum 服务 ProjectClassifier / 内部业务,与 schema 输出 Literal 是两个独立词表,不耦合)。
>
> 新增 / 修改 / 删除 project_type 走 D5 第二层同源(6 处:overview_schemas.py + freeze test + docs/06 + schemas/*.json + project_overview.yaml + 05 § 2.A)。

[7 类型字面 + 中文描述 + 何时选哪个]

## 4. service 五步校验(实施层防御)

[file_path / simulink file_path / block 四元组 / block_id / line_range 五步语义]

## 5. 教学口吻硬要求(对齐 05 § 8)

[简版引用 05 § 8,不重复全文]

## 6. 反模式 + 示例

[6 个常见反模式 + 反例 JSON 片段]

## 7. Schema 修订流程

[D5 两层同源(R1 P1-4):通用 4 处 overview_schemas.py + freeze test + docs/06 + schemas/*.json;project_type 修订加 prompt yaml + 05 共 6 处;PR review checklist 强制三问]

## 8. 评测维度(对齐 05 § 10)

[字段填充率 / 教学口吻评分 / 证据引用覆盖率 / 中文术语对齐]

## 9. 与 05 / Prompt yaml / Service 的对应关系

[D5 两层同源 + 边界:05 给 LLM,06 给消费者,prompt 实现层,service 校验层;通用 4 处 + project_type 6 处]

## 10. 版本

v0.1 — 2026-06-05 起 freeze,与 TASK-203 commit `871c8e2` 实现一致。
```

**`docs/06_OUTPUT_CONTRACTS.md` 不重复内容**(决策 06,引用即可):
- 不复述 05 § 8 教学口吻全文(只给"对齐 05 § 8"引用)
- 不内联 `overview_schemas.py` Python 代码(只给字段表,代码是实现源)
- 不内联 `project_overview.yaml` 全文(只给"对齐 v0.1"引用)
- 不内联 service 校验 Python 代码(只给五步语义清单)

### 7.2 `scripts/export_overview_schema.py` 完整代码

见 § 6.2 已贴。**关键 invariant**:

- 70 行内,标准库 `json` + `pathlib` + `sys`,**不**引入新依赖
- 输出**字面常量路径** `schemas/project_overview.schema.json`(测试断言此路径)
- 出错自然冒泡,**禁** `try/except` 翻中文(非用户面)
- `if __name__ == "__main__"` 兜底支持 `python scripts/export_overview_schema.py` 直跑(虽然推荐 `python -m`)

### 7.3 `tests/features/overview/test_schema_freeze.py` 完整伪代码(~190 行)

```python
"""TASK-207 schema freeze tests: introspection-based, version-agnostic."""

from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from features.overview.overview_schemas import (
    BlockEntry,
    EntryFileEntry,
    KeyFileEntry,
    ProjectOverview,
    SimulinkModelEntry,
    SourceRefEntry,
)


# ============================================================
# Top-level ProjectOverview frozen contract
# ============================================================

EXPECTED_TOP_LEVEL_FIELDS = {
    "project_title",
    "project_type",
    "one_sentence_summary",
    "main_entry_files",
    "main_simulink_models",
    "main_execution_flow",
    "key_files",
    "key_blocks",
    "knowledge_points",
    "beginner_reading_order",
    "likely_confusing_points",
    "evidence",
}


def test_top_level_field_names_frozen() -> None:
    """12 fields by name. Adding / renaming / removing requires explicit schema bump."""
    actual = set(ProjectOverview.model_fields.keys())
    assert actual == EXPECTED_TOP_LEVEL_FIELDS, (
        f"ProjectOverview top-level fields drifted. "
        f"Missing: {EXPECTED_TOP_LEVEL_FIELDS - actual}. "
        f"Unexpected: {actual - EXPECTED_TOP_LEVEL_FIELDS}. "
        f"If intended, update docs/06_OUTPUT_CONTRACTS.md and "
        f"schemas/project_overview.schema.json together (D5 two-tier rule (general 4 + project_type 6))."
    )


# R1 P0-1: lock annotation to catch `list[X] -> set[X]` etc.
# project_type is excluded here (it's a Literal[7], locked by test_project_type_literal_frozen).
EXPECTED_TOP_LEVEL_TYPES = {
    "project_title": str,
    "one_sentence_summary": str,
    "main_entry_files": list[EntryFileEntry],
    "main_simulink_models": list[SimulinkModelEntry],
    "main_execution_flow": list[str],
    "key_files": list[KeyFileEntry],
    "key_blocks": list[BlockEntry],
    "knowledge_points": list[str],
    "beginner_reading_order": list[str],
    "likely_confusing_points": list[str],
    "evidence": list[SourceRefEntry],
}


@pytest.mark.parametrize("field_name,expected_type", EXPECTED_TOP_LEVEL_TYPES.items())
def test_top_level_field_types_frozen(field_name: str, expected_type: type) -> None:
    """12 field annotations. Changing list[X] -> set[X] / list[str] -> list[bytes] caught here."""
    actual = ProjectOverview.model_fields[field_name].annotation
    assert actual == expected_type, (
        f"{field_name} annotation drifted. "
        f"Expected {expected_type!r}, got {actual!r}. "
        f"If intended, update docs/06_OUTPUT_CONTRACTS.md and "
        f"schemas/project_overview.schema.json together (D5 two-tier rule (general 4 + project_type 6))."
    )


EXPECTED_CONSTRAINTS = {
    "project_title": {"min_length": 1, "max_length": 30},
    "one_sentence_summary": {"min_length": 1, "max_length": 80},
    "main_entry_files": {"min_length": 1, "max_length": 3},
    "main_simulink_models": {"max_length": 5},
    "main_execution_flow": {"min_length": 3, "max_length": 7},
    "key_files": {"min_length": 3, "max_length": 8},
    "key_blocks": {"max_length": 10},
    "knowledge_points": {"min_length": 3, "max_length": 6},
    "beginner_reading_order": {"min_length": 3, "max_length": 6},
    "likely_confusing_points": {"min_length": 2, "max_length": 5},
    "evidence": {"min_length": 3},
}


@pytest.mark.parametrize("field_name,expected", EXPECTED_CONSTRAINTS.items())
def test_top_level_field_constraints_frozen(
    field_name: str, expected: dict[str, int]
) -> None:
    """Field min/max_length constraints. Loosening / tightening requires schema bump."""
    field_info = ProjectOverview.model_fields[field_name]
    # Pydantic stores list length constraints differently from string length;
    # both expose .min_length / .max_length attributes on different metadata classes.
    for constraint_name, expected_val in expected.items():
        actual = None
        for m in field_info.metadata:
            if hasattr(m, constraint_name):
                actual = getattr(m, constraint_name)
                break
        assert actual == expected_val, (
            f"{field_name}.{constraint_name}: expected {expected_val}, got {actual}"
        )


# ============================================================
# ProjectTypeValue Literal[7] frozen
# ============================================================

EXPECTED_PROJECT_TYPES = (
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
)


def test_project_type_literal_frozen() -> None:
    """7 project types, ordered. Adding / removing requires bumping prompt yaml + docs."""
    field_info = ProjectOverview.model_fields["project_type"]
    # Pydantic Literal arg extraction via typing.get_args
    from typing import get_args
    actual = get_args(field_info.annotation)
    assert actual == EXPECTED_PROJECT_TYPES, (
        f"project_type Literal drifted. "
        f"Expected (ordered): {EXPECTED_PROJECT_TYPES}. "
        f"Actual: {actual}. "
        f"If intended, update core/prompts/project_overview.yaml + "
        f"docs/06_OUTPUT_CONTRACTS.md § 3 together."
    )


# ============================================================
# Sub-schemas frozen
# ============================================================

EXPECTED_SUB_SCHEMAS = {
    EntryFileEntry: {
        "file_path": (str, {"min_length": 1}),
        "role": (str, {"min_length": 1, "max_length": 100}),
    },
    SimulinkModelEntry: {
        "file_path": (str, {"min_length": 1}),
        "summary": (str, {"min_length": 1, "max_length": 200}),
    },
    KeyFileEntry: {
        "file_path": (str, {"min_length": 1}),
        "why_key": (str, {"min_length": 1, "max_length": 200}),
    },
    BlockEntry: {
        "block_name": (str, {"min_length": 1}),
        "block_type": (str, {"min_length": 1}),
        "location": (str, {"min_length": 1}),
        "why_key": (str, {"min_length": 1, "max_length": 200}),
    },
    SourceRefEntry: {
        # R1 P0-1: lock Optional types so `tuple[int,int] | None -> tuple[int,int]` is caught.
        "file_path": (str, {"min_length": 1}),
        "line_range": (tuple[int, int] | None, {}),
        "block_id": (str | None, {}),
    },
}


@pytest.mark.parametrize(
    "schema_cls,expected_fields",
    EXPECTED_SUB_SCHEMAS.items(),
    ids=lambda x: getattr(x, "__name__", str(x)),
)
def test_sub_schema_fields_frozen(schema_cls, expected_fields) -> None:
    """Sub-schema fields frozen by name + annotation + constraints (R1 P0-1)."""
    actual_fields = set(schema_cls.model_fields.keys())
    expected_field_names = set(expected_fields.keys())
    assert actual_fields == expected_field_names, (
        f"{schema_cls.__name__} fields drifted. "
        f"Expected: {expected_field_names}. Actual: {actual_fields}."
    )
    # Annotation + constraint detail per field (R1 P0-1: annotation now actually asserted)
    for field_name, (expected_type, expected_constraints) in expected_fields.items():
        field_info = schema_cls.model_fields[field_name]
        # Annotation check (catches Optional drift like `tuple[int,int] | None` -> `tuple[int,int]`)
        assert field_info.annotation == expected_type, (
            f"{schema_cls.__name__}.{field_name} annotation drifted. "
            f"Expected {expected_type!r}, got {field_info.annotation!r}."
        )
        # Constraint check
        for constraint_name, expected_val in expected_constraints.items():
            actual = None
            for m in field_info.metadata:
                if hasattr(m, constraint_name):
                    actual = getattr(m, constraint_name)
                    break
            assert actual == expected_val, (
                f"{schema_cls.__name__}.{field_name}.{constraint_name}: "
                f"expected {expected_val}, got {actual}"
            )


# ============================================================
# extra="forbid" at all schema levels
# ============================================================

@pytest.mark.parametrize(
    "schema_cls",
    [
        ProjectOverview,
        EntryFileEntry,
        SimulinkModelEntry,
        KeyFileEntry,
        BlockEntry,
        SourceRefEntry,
    ],
    ids=lambda x: x.__name__,
)
def test_extra_forbid_at_all_levels(schema_cls) -> None:
    """extra='forbid' inherited from _StrictBaseModel at every level."""
    assert schema_cls.model_config.get("extra") == "forbid", (
        f"{schema_cls.__name__} lost extra='forbid'. "
        f"_StrictBaseModel inheritance broken?"
    )


# ============================================================
# Export script integrity
# ============================================================

def test_schema_exported_json_parseable(tmp_path: Path) -> None:
    """scripts/export_overview_schema runs and produces valid JSON.

    R1 P1-3: run in tmp_path with PYTHONPATH=project_root so pytest does NOT
    overwrite the committed schemas/project_overview.schema.json. Drift between
    committed JSON and current schema is caught by `make verify-schema`
    (see Makefile), not by this test.
    """
    project_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    result = subprocess.run(
        [sys.executable, "-m", "scripts.export_overview_schema"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, (
        f"export script failed: stderr={result.stderr}"
    )
    schema_path = tmp_path / "schemas" / "project_overview.schema.json"
    assert schema_path.exists(), f"expected output not found: {schema_path}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # Sanity: top-level JSON Schema structure
    assert "properties" in schema or "$ref" in schema, (
        "exported JSON missing top-level structure"
    )
```

**关键设计**(R1 重点 review 点):

1. **不 diff JSON 文本**:`test_schema_exported_json_parseable` 只 assert script 跑通 + JSON 合法,**不**断言 JSON 内容 byte-for-byte 一致(pydantic 升级会脆)
2. **introspection 直接读 `model_fields`**:绕开 JSON 输出格式细节,版本无关
3. **`metadata` 遍历 + `hasattr` 兼容**:pydantic 2.x metadata 用 annotated-types 包装,不同 patch 版本 metadata class 名可能微变,用 `hasattr(m, constraint_name)` 跨版本安全
4. **annotation 精确比对**(R1 P0-1):`field_info.annotation == expected_type` 锁 `list[X]` / `tuple[int, int] | None` / `str | None` 等类型,防止"放宽类型限制"漂移
5. **错误信息明示修复路径**:每条 assert 失败信息提醒 D5 两层同源(通用 4 处 + project_type 6 处),降低后续 PR 作者心智负担
6. **`subprocess` 在 `tmp_path` + `PYTHONPATH=project_root`**(R1 P1-3):测试不污染工作区 `schemas/project_overview.schema.json`,仓库 JSON 与代码漂移由 `make verify-schema` 守门(§ 7.4 + § 11.2 #14)
7. **drift detection 分两层**:freeze test 守门"schema 语义不变量"(introspection,版本无关);`make verify-schema` 守门"committed JSON 与当前 schema 同步"(命令行 git diff,触发条件就是 pydantic 升级 / 字段改动 / 约束改动)

### 7.4 Makefile 新增 target(D4 选 A)

```makefile
# 在现有 target 后追加
export-schema:
	python -m scripts.export_overview_schema

verify-schema: export-schema
	@git diff --exit-code schemas/project_overview.schema.json \
		|| (echo "schemas/project_overview.schema.json drifted. Regenerate with 'make export-schema' and commit." && exit 1)
```

`make check` **不**默认包含 `verify-schema`(避免在 pydantic 升级时阻塞所有 CI),由开发者主动跑 / Phase 2 集成 CI。

**D4 选 B 替代方案**:不动 Makefile,export script 在文档里有用法说明即可。本 Task v0.1 倾向 A(low cost,明确入口)。

### 7.5 03 索引 4 行字节级修订(搭车 chore)

沿用 task-206 同款模式。字节级 Python(决策 08 + 反例 23 教训):

```python
import pathlib
p = pathlib.Path("docs/03_TASK_INDEX.md")
data = p.read_bytes()

# 行 120: TASK-206 🔍 → ✅
old1 = "| TASK-206 | 错误处理 + 中文化 | 🔍 | Codex | 201-205 |".encode("utf-8")
new1 = "| TASK-206 | 错误处理 + 中文化 | ✅ | Codex | 201-205 |".encode("utf-8")
assert old1 in data, "TASK-206 line not found"

# 行 121: TASK-207 🔲 → 🔍
old2 = "| TASK-207 | **ProjectOverview Schema + 教学输出契约** ⭐ | 🔲 | Codex | 203 |".encode("utf-8")
new2 = "| TASK-207 | **ProjectOverview Schema + 教学输出契约** ⭐ | 🔍 | Codex | 203 |".encode("utf-8")
assert old2 in data, "TASK-207 line not found"

# 行 338: Week 2 进度条 5/7 → 6/7
old3 = "Week 2:  [✅✅✅✅✅🔍⬜]         5/7  (含 TASK-207)".encode("utf-8")
new3 = "Week 2:  [✅✅✅✅✅✅🔍]         6/7  (含 TASK-207)".encode("utf-8")
assert old3 in data, "Week 2 progress line not found"

# 行 342: 总计 16/32 → 17/32
old4 = "总计: 16/32".encode("utf-8")
new4 = "总计: 17/32".encode("utf-8")
assert old4 in data, "Total count line not found"

data = data.replace(old1, new1).replace(old2, new2).replace(old3, new3).replace(old4, new4)
p.write_bytes(data)
print("03 index updated: TASK-206 -> ✅, TASK-207 -> 🔍, Week 2 6/7, total 17/32")
```

**关键不变量**(决策 08 + 反例 24 教训):

- 全 `read_bytes` / `write_bytes`,**禁** `read_text` / `write_text` / `sed -i`
- 4 处 assert 兜底,任一不命中停手抛冲突(行号漂移可能)
- emoji UTF-8 字面**精确字节对**(决策 09 反例 24 教训:emoji 字面 / Markdown 表格分隔符 / 空格数严格一致)
- `Week 2: ` 后**两个空格**(实地核查段 2 输出确认)
- `5/7  (含...)` 后**两个空格**

### 7.6 决策 09 末尾追加反例 25(搭车 chore)

字节级 Python,沿用反例 21-24 同款追加模式:

```python
import pathlib
p = pathlib.Path("docs/decisions/20260603-09-architect-must-verify-not-assume.md")
data = p.read_bytes()

# 追加在文件末尾(实地核查 tail 末行是反例 24 共同特征 + 下一任 KPI 强化句)
append = """

反例 25(2026-06-05 / 第十四任 / TASK-206 review 阶段兜底命令):
架构师在写给 PM 跑的 grep 兜底命令时,没本地实测 `^\\s+\\(\\s*[A-Z]\\w+Error,` 这种 ERE 正则在 Windows Git Bash GNU grep 下是否解析 `\\s`,结果 PM 跑出 0 命中,差点被误读为"tuple entry 不存在"。
实际原因:`\\s` 在 Git Bash GNU grep ERE 下可能不解析为 [[:space:]] 字符类(POSIX BRE/ERE 标准不要求支持)。
教训接续反例 14(bash 中文括号坑)/ 反例 24(grep POSIX vs Perl):任何给 PM 的 grep 命令,架构师必须用 `[[:space:]]` / `[ ]` / `' '` 等 POSIX 兼容字符类,禁用 `\\s` / `\\d` / `\\w`(`\\w` 在 GNU ERE 支持但 BSD 不支持,跨平台风险)。
幸好本次有 2 条兜底命令冗余(`_make_handler\\(|_make_project_too_large_handler\\(`)+ sed 视觉确认,review 决策正确。但单条 grep 失败 = 应触发架构师重测,而不是直接接受 0 命中。

第十五任 KPI 升级(本决策末尾追加):
- 任何写给 PM 的 grep / sed / awk 命令,架构师本地实测一次确认输出形态再下笔(反例 24 / 25 同源)
- 跨平台 grep 用 POSIX 字符类 `[[:space:]]` / `[[:upper:]]` / `[[:alpha:]]`,禁用 `\\s` / `\\d` / `\\w` / `\\b` 等 Perl 风格
- 任何 grep 输出 0 时,架构师默认假设"我的 grep 写错"而不是"代码不存在",再用 2-3 种不同 grep / sed 兜底交叉确认
"""

# 防重复入仓(若 PM 误跑两次)
assert "反例 25" not in data.decode("utf-8"), "reflex 25 already in file"
data = data + append.encode("utf-8")
p.write_bytes(data)
print("Decision 09 updated: 反例 25 + 第十五任 KPI appended")
```

**注**:转义符号 `\\s` 是 Python 字符串内对反斜杠转义,写入文件后是字面 `\s`(展示给读者的反例);中文段落不转义。

### 7.7 PR 元信息

- PR 标题:`TASK-207: ProjectOverview Schema 契约文档化 + freeze 守门(Week 2 收尾)`
- 分支名:`task/TASK-207-overview-schema-contract`
- PR 描述按 04 § 3 模板 + 逐条勾选 § 11.2 验收 + R1 反馈采纳清单(若有)

---

## 决策日志(D1-D6)

### D1 — 审批级别:走 GPT 一审 1 轮

**理由**:
- 反例 18 自检 5 维度全低(决策密度 / 下游扩散面 / 用户可见性 / 异步首次 / 隐私安全)
- 0 业务代码改动(零字段改 / 零接口改 / 零行为改)
- 沿用 TASK-107 / 206 一审 1 轮模式,task-203 / 205 同源 schema 已二审实战

**替代方案**:
- A. 走 GPT 二审(类比 task-203 / 205)。**为何不选**:task-203 / 205 是 schema 首次落地 + 业务行为定型,本 Task 是文档化已稳定的 schema,复杂度不可类比;反例 18 教训反方向应用。
- B. 不走审(类比 task-108)。**为何不选**:本 Task 创建项目第六个顶层契约文档(docs/06)+ schema 修订流程 D5 + freeze test 维度选择;非单点决策,需要 R1 挑战 D2 / D5 设计。

### D2 — Freeze test 走 introspection,不做 JSON 文本 diff

**理由**:
- pydantic 2.x patch 版本间 `model_json_schema()` 输出在 `title` / `$defs` 排序 / `examples` 字段处理上偶有差异
- 项目 pydantic 2.12.4 → 未来 2.13.x 升级时,文本 diff 会因格式细节误报
- 语义不变量(字段名 + 类型 + 约束 + Literal[7] + extra="forbid")在 pydantic 主版本内稳定,introspection 直接读 `model_fields` 跨版本安全
- 失败信息可明示修复路径(D5 两层同源),降低 PR 作者心智负担

**替代方案**:
- A. JSON 文本 diff(`git diff schemas/*.json`)。**为何不选**:pydantic 升级时脆,且文本 diff 失败信息不直观("JSON 文本变了"对调试无用)。
- B. JSON 内容 dict 比对(`json.loads + assert ==`)。**为何不选**:仍受 pydantic 输出格式影响(`additionalProperties` 是否存在 / `$defs` 命名),不如 introspection 稳。
- C. 不做 freeze test,仅靠人工 review。**为何不选**:schema 漂移是反例 24 同源问题(docstring 漂移),自动守门成本 ~150 行测试,收益远超。

### D3 — `docs/06_OUTPUT_CONTRACTS.md` 命名

**理由**:
- 顶层 `docs/` 现有 01-05,06 是自然延续
- 05 是"教学口吻规范"(给 LLM + prompt),06 是"输出契约"(给 schema 消费者),职责分层清晰
- 顶层 docs/ 而非 `docs/tasks/` 或 `docs/specs/`,因契约文档**永久生效**,不是 Task 级临时文档

**替代方案**:
- A. `docs/tasks/task-207-*.md` 内含契约文档。**为何不选**:Task 文档是过程记录,完工后不再更新;契约文档需要长期更新(每次 schema 修订)。
- B. `docs/05_EXPLANATION_STYLE_GUIDE.md` § 2.A 段扩展。**为何不选**:05 关注教学口吻 + prompt 期望,06 关注消费者契约,职责混淆。
- C. `features/overview/CONTRACT.md` feature-local 文档。**为何不选**:契约是项目级跨 Task 消费,不是 feature-private;TASK-402 前端 / 评测 / 第三方都需 link 到稳定 URL。

### D4 — `scripts/export_overview_schema.py` 在 scripts/ + Makefile 加 2 target

**理由**:
- scripts/ 已有 `check_repo_hygiene.py` 工具脚本先例
- 工具脚本不属于业务代码(`features/` / `core/` / `adapters/` / `api/`),不污染业务分层
- Makefile 加 `export-schema` + `verify-schema` 提供明确入口,但**不**进 `make check`(避免 pydantic 升级时全 CI 阻塞)
- `verify-schema` 独立 target 让开发者在 schema 修订时主动跑,作为本地 self-check

**替代方案**:
- A(本 Task 选):scripts/ + Makefile 加 target(low cost,明确入口)
- B. scripts/ 但不动 Makefile。**为何不选**:文档使用说明虽然给了,但缺明确 entry point,后续开发者会找不到;成本仅 ~4 行 Makefile。
- C. 在 `tests/` 内嵌 export 逻辑(测试同时生成 JSON)。**为何不选**:测试不应有副作用(写入工作目录文件),违反测试隔离原则。
- D. 用 pytest fixture 临时生成 JSON 比对。**为何不选**:无法持久化 JSON 入仓供前端 / 第三方消费。

### D5 — Schema 修订两层同源流程(R1 P1-4 升级)

**理由**:
- 防 schema 偷偷漂移(反例 24 同源教训:docstring 漂移因缺自动守门)
- 强制 PR 作者显式同步多处,降低"只改实现忘记改文档 / prompt"风险
- freeze test **不阻止**演进,仅**强制**显式同步;PR review checklist 加一行确认即可
- 类比 05 § 9.2 prompt 修订流程(版本号 + 评测 + PR review),本 Task 引入 schema 修订对应版本
- **R1 P1-4**:R6 自己承认 `project_type` 实际在 4 处定义(`overview_schemas.py` + `project_overview.yaml` + 05 + 06),原 D5 四同源对 `project_type` 不够;改两层规则覆盖

**两层同源规则**:

```text
第一层 — 通用 schema 修订必改 4 处:
  1. features/overview/overview_schemas.py            (实现源)
  2. tests/features/overview/test_schema_freeze.py    (守门测试)
  3. docs/06_OUTPUT_CONTRACTS.md                       (契约文档)
  4. schemas/project_overview.schema.json              (导出 JSON,跑 make export-schema 重生)

第二层 — 若修订涉及 project_type Literal[7],还必须同步 2 处:
  5. core/prompts/project_overview.yaml                (LLM 提示词)
  6. docs/05_EXPLANATION_STYLE_GUIDE.md § 2.A / 示例处 (教学规范)

第三层 — 任何 schema 修订 PR 必须在 review checklist 显式回答:
  - prompt yaml 是否需要同步:是 / 否 + 理由
  - overview_service 五步校验是否需要同步:是 / 否 + 理由
  - 评测脚本(eval/run_eval.py)字段表是否需要同步:是 / 否 + 理由
```

**实施层支持**:

- `freeze test` 失败信息明示"按 D5 两层规则同步"
- `make verify-schema` 守门 #4 JSON 同步
- PR review checklist(04 § 11 + docs/06 § 7)模板加上述 3 问

**替代方案**:
- A. 不强制同步,仅文档"建议同步"。**为何不选**:依赖人工 review,反例 24 教训说明这不可靠。
- B. 自动同步(改 .py → CI 自动 regen JSON + docs)。**为何不选**:CI 自动改 docs 会绕开 review,且 .md 文档需要人工写语义描述无法自动生成。
- C. 拆 schema 实现 + freeze test 到独立 PR / 不同 PR review。**为何不选**:PR 频繁拆解增加协作成本,本流程仅要求"同 PR 内同源",已是最低成本。
- D. 维持 v0.1 四同源(R1 P1-4 前的形态)。**为何不选**:R6 自承认 `project_type` 在 4 处定义,四同源对 `project_type` 漏检 prompt yaml + 05,违反"PR 同源"语义。

### D6 — `_StrictBaseModel` 重复不在本 Task 收口

**理由**:
- `features/overview/overview_schemas.py:20` + `features/chat/chat_schemas.py:22` 各一份独立定义
- 抽出到 `core/shared/` 或 `features/_common/` 需要新建模块 + 改 import,涉及 features/chat/ 范围,**违反**本 Task 范围边界(features/chat/ 不在范围内)
- Phase 2 / Week 3 cleanup 任务可统一收口,不阻塞本 Task

**替代方案**:
- A. 本 Task 抽 `core/shared/strict_base_model.py`。**为何不选**:违反"零业务代码改动" + features/chat/ 范围外。
- B. 在 features/overview/ 内 re-export 给 chat。**为何不选**:违反依赖单向(features/overview/ 不能给 features/chat/ 提供基类)。
- C. Phase 2 单独 chore PR 收口。**为何选**:✅ 推到 Phase 2 候选,本 Task 不阻塞。

### D7(新增,R1 P2-3)— PM 授权治理 chore:反例 25 入仓决策 09

**理由**:
- 第十四任 TASK-206 review 阶段产出反例 25 候选(架构师写 grep 跨平台兼容性,POSIX 字符类强制 + 第十五任 KPI 升级)
- 仅活在第十四 → 第十五任交接文案,**未入仓**;若第十六任接棒只看 `docs/decisions/`,会丢这条教训(交接文案 session-local,会随会话结束消失)
- 本 Task 是 Week 2 最后一棒,搭车字节级 Python 追加到决策 09 末尾,沿用反例 21-24 同款 patch 模式
- **PM 显式授权**:本会话开场即拍板"搭车修",非 Codex 自决
- **不是 schema 契约本身,是治理日志追加**(R1 P2-3 抓住):D1-D6 全部围绕 schema 契约,D7 独立标记治理 chore,Codex / PM review 时能区分

**授权边界明示**(沿用 TASK-206 D5 边界文案):

- ✅ 允许:**本次** 反例 25 入仓决策 09 由 Codex 搭车实施(PM 本次显式授权)
- ❌ 禁止:**后续** Codex 自行追加任何反例 / 教训到决策 09(默认仍是架构师在 R1 review 阶段沉淀,搭车 chore 需 PM 显式授权)
- ❌ 禁止:把本 Task D7 作为"先例"引用,要求后续 Task 自动放宽决策 09 追加规则

**§ 7.6 实施细节** 提供完整字节级 Python patch(`read_bytes` + `assert "反例 25" not in data` 防重复入仓 + `write_bytes` LF 兼容)。

**替代方案**:
- A. 单开 chore PR 入仓反例 25。**为何不选**:Week 2 最后一棒搭车成本接近 0,单 PR 多一次 review + merge 循环不值得。
- B. 推到 TASK-301 / Phase 2 入仓。**为何不选**:KPI 是给"下一任架构师"的,越晚入仓越多任失败风险;搭车 chore 抓住"还在本会话语境"window。
- C. 在 v0.2 文档里只写"PM 授权"但不进决策日志。**为何不选**:R1 P2-3 抓住"决策日志缺漏",决策日志是 PR review 信号源。

---

## 验收清单

### 11.1 测试要求

`tests/features/overview/test_schema_freeze.py` 必须覆盖(详见 § 7.3):

- ✅ 12 顶层字段名清单(set 比对)
- ✅ 11 顶层字段约束(parametrize × min/max_length)
- ✅ ProjectTypeValue 7 类型字面有序(tuple 比对)
- ✅ 5 子 schema 字段名 + 类型 + 约束(parametrize)
- ✅ 6 个 schema 类 `extra="forbid"`(parametrize)
- ✅ `scripts/export_overview_schema.py` 跑通 + JSON 合法

测试**禁止**:
- ❌ 网络调用 / LLM 调用 / 真实 DeepSeek API
- ❌ 写入工作目录除 `schemas/project_overview.schema.json` 外其他文件
- ❌ 依赖项目 fixture(本 Task 测试 stand-alone,只 import schema + script)

### 11.2 完工自检清单(15 条 grep,Codex 跑后输出明示给 PM)

**所有 grep 用 POSIX 字符类**(反例 25 KPI)。

```bash
# 1. Stage 0 实地核查 13 条 grep 全通过(本 Task § Stage 0)
# PR 描述明示每条 grep 实际输出与期望一致

# 2. 单元测试全绿
pytest tests/features/overview/test_schema_freeze.py -v
# 期望:约 30 个 test items passed,以 pytest 实际收集数为准(R1 P0-3)
# 11 个 test function,因 parametrize 展开 sub_schemas / extra_forbid / top_level_constraints /
# top_level_types 各自展开多个 item;具体数量取决于 EXPECTED_* 字典 entry 数

# 3. 既有测试无回归
pytest tests/ -v
# 期望:全绿

# 4. lint + type-check + format
make lint && make type-check && python -m ruff format --check .

# 5. 每文件 ≤ 300 行
git diff --name-only origin/main..HEAD -- '*.py' \
  | xargs -r -n1 wc -l \
  | awk '$1 > 300 {print; bad=1} END {exit bad+0}'

# 6. requirements.txt 0 新增
git diff origin/main..HEAD -- requirements.txt requirements-dev.txt
# 期望:无输出

# 7. 决策 11 兜底 2 条 grep 应空
grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ scripts/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
grep -rnE 'str\(exc\)|repr\(exc\)' core/ adapters/ features/ api/ app/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
# 期望:两条均空(scripts/ 内若命中,view 上下文判断)

# 8. overview_schemas.py 0 修改(范围边界硬约束)
git diff origin/main..HEAD -- features/overview/overview_schemas.py
# 期望:无输出

# 9. overview_service.py 0 修改(范围边界硬约束)
git diff origin/main..HEAD -- features/overview/overview_service.py
# 期望:无输出

# 10. project_overview.yaml 0 修改(范围边界硬约束)
git diff origin/main..HEAD -- core/prompts/project_overview.yaml
# 期望:无输出

# 11. 反例 25 已入仓决策 09(本 Task 搭车 chore)
grep -nE "反例 ?25|新增反例 25|POSIX 字符类" docs/decisions/20260603-09-architect-must-verify-not-assume.md
# 期望:命中(本 Task 完工后,与 § Stage 0 #7 相反)

grep -nE "第十五任 KPI" docs/decisions/20260603-09-architect-must-verify-not-assume.md
# 期望:命中

# 12. docs/06 已创建
ls docs/06_OUTPUT_CONTRACTS.md
wc -l docs/06_OUTPUT_CONTRACTS.md
# 期望:文件存在,行数 ~200-300

# 13. schemas/ 目录 + JSON 文件已创建
ls schemas/project_overview.schema.json
wc -l schemas/project_overview.schema.json
# 期望:文件存在,行数 ~50-200(取决于 pydantic 2.12.4 输出格式)

# 14. export script + verify-schema 一键(R1 P1-5)
make verify-schema
# 期望:exit 0
# 若 `schemas/project_overview.schema.json` 漂移(pydantic 升级 / schema 改动 / 误手改 JSON),
# Makefile 内 git diff --exit-code 会非零,按错误提示跑 `make export-schema` regenerate 并 commit。
# 等价手工命令(若不想依赖 Makefile):
#   python -m scripts.export_overview_schema
#   git diff --exit-code schemas/project_overview.schema.json

# 15. 03 索引 4 处修订正确(字节级 Python 保留 LF 行尾)
grep -nE "TASK-206|TASK-207|Week 2|总计" docs/03_TASK_INDEX.md | head -10
# 期望:
#   119: TASK-205 ... ✅ ...(沿用)
#   120: TASK-206 ... ✅ ...(本 Task 推 ✅)
#   121: TASK-207 ... 🔍 ...(本 Task 推 🔍)
#   338: Week 2 [✅✅✅✅✅✅🔍] 6/7  ← 本 Task 推 6/7
#   342: 总计: 17/32             ← 本 Task 推 17/32
```

### 11.3 PM 验收 Step B(决策 08 第 2 条)

- [ ] `git status` clean + `git log --oneline main..HEAD` commit 拆分合理
- [ ] `make check` 全绿
- [ ] 11.2 第 7 / 8 / 9 / 10 / 11 / 12 / 13 / 14 / 15 条 grep / 命令实际跑,输出与期望一致
- [ ] 4 新建文件 wc -l 在合理范围(.py ≤ 300)
- [ ] PR 描述明示 R1 反馈采纳清单(若有)
- [ ] 搭车 chore 字节级 Python git diff 仅修改预期行(决策 08 字节级保留 CRLF/LF)

### 11.4 PR 元信息

- PR 标题:`TASK-207: ProjectOverview Schema 契约文档化 + freeze 守门(Week 2 收尾)`
- 分支名:`task/TASK-207-overview-schema-contract`
- PR 描述按 04 § 3 模板 + 逐条勾选 11.2 验收 + R1 反馈采纳清单(若有)

---

## 风险与决策日志

### 12.1 风险与注意点(8 条)

**R1 pydantic 升级时 freeze test 误报**

pydantic 2.12 → 2.13 / 3.x 升级可能引入新 `Field` metadata class 名,`hasattr(m, 'min_length')` 兼容策略大概率仍能跑(annotated-types 库提供的 metadata 接口稳定),但极端情况下可能需要更新 freeze test。规避:测试失败信息已明示"introspection 写法,pydantic 升级需主动 review";若发生,改 freeze test 内 `metadata` 遍历逻辑,**不**改 schema。

**R2 schemas/ JSON 因 pydantic 升级被规范化 diff**

升 pydantic 时 `model_json_schema()` 输出微变,`schemas/project_overview.schema.json` 会有 diff。规避:升级时主动跑 `make export-schema` regenerate + 人工 review JSON diff 是否含语义变化(若不含,作为 chore commit;若含,触发 D5 schema 修订流程)。

**R3 反例 25 字节级追加在 emoji / 中文 / `\s` 字面遇坑**

反例 25 文本含 `\s` / `\d` / `\w` 字面 + emoji 0 + 中文段落。Python 字符串内 `\\s` 转义,写入字节后变 `\s`(预期);若遇 Windows codepage / Git Bash 编码问题,可能字面错位。规避:字节级 Python 读 / 写,**禁** `sed -i`;PM 验收时 `git diff` 看反例 25 段是否字符正确(尤其 `\s` / `\d` 字面)。

**R4 freeze test parameterize 在 pydantic 2.12.x 内部 metadata 差异**

pydantic 2.12.4 `Field(min_length=1, max_length=100)` 的 metadata 用 `annotated_types.MinLen` + `annotated_types.MaxLen` 包装(主流形态)。`hasattr(m, "min_length") / hasattr(m, "max_length")` 在 annotated-types 0.6+ 稳定支持。规避:测试代码用 `hasattr` 而非 isinstance,跨次要版本安全。

**R5 service 校验五步在 schema 更宽时漏检**

本 Task 不动 service 校验五步,但若未来 freeze test 放宽某字段约束(如 evidence 从 ≥3 改 ≥1),service 校验五步未同步可能放行非法输入。规避:D5 两层同源流程文档明示此风险,PR review checklist 强制确认 service 五步是否需同步(D5 第三层 checklist 第 2 问)。

**R6 7 项目类型在 6 处定义,新增类型走 D5 第二层同源**(R1 P1-4 升级)

`overview_schemas.py:9-17` + `project_overview.yaml:11-12` + `docs/05_EXPLANATION_STYLE_GUIDE.md:62`(JSON 示例) + `docs/06_OUTPUT_CONTRACTS.md § 3`(本 Task 新增)+ `schemas/project_overview.schema.json`(本 Task 新增,Pydantic 导出) + `tests/features/overview/test_schema_freeze.py::EXPECTED_PROJECT_TYPES`(本 Task 新增,freeze 守门)— 实际 **6 处定义**。规避:D5 第二层规则明示"`project_type` 修订必须 6 同源"+ freeze test `test_project_type_literal_frozen` 守门 schema 层 + checklist 三问 PR review 兜底;具体流程见 D5。

**R7 docs/06 文档与 05 内容重叠风险**

05 § 2.A 已有字段约束表,06 § 2 字段表内容相似。规避:06 § 2 字段表加"教学要求"列(05 没有的语义维度),与 05 区分;06 § 5 教学口吻明示"引用 05 § 8,不重复全文";Phase 2 若发现重叠过多,可考虑把 05 § 2.A 拆到 06。

**R8 反例 25 入仓后第十五任 KPI 在交接文案 vs 决策 09 双源**

第十四任交接文案有"第十五任 KPI 升级"段,本 Task 入仓决策 09 末尾时同源追加。规避:Codex 实施时,本 Task § 7.6 字节级 Python 已明示 KPI 段以"第十五任 KPI 升级"为开头,与交接文案语义一致;若未来第十六任接棒,decision 09 末尾 KPI 才是 source of truth(交接文案是 session-local 记忆,会随会话结束消失)。

### 12.2 决策日志摘要(D1-D7,详见前文 § 决策日志)

| D | 决策 | 一句话 |
|:--:|---|---|
| D1 | 一审 1 轮 | 反例 18 自检 5 维度全低,沿用 task-107 / 206 模式 |
| D2 | introspection freeze | pydantic 版本无关,文本 diff 脆,语义不变量稳 |
| D3 | docs/06_OUTPUT_CONTRACTS.md 命名 | 顶层 docs/,与 05 职责分层(给 LLM vs 给消费者) |
| D4 | scripts/ + Makefile target | low cost 明确入口,不进 make check 避免阻塞 |
| D5 | schema 修订两层同源(R1 P1-4 升级) | 通用 4 处 + project_type 6 处 + checklist 三问 |
| D6 | _StrictBaseModel 重复不收口 | 范围外,Phase 2 chore |
| D7 | PM 授权治理 chore(R1 P2-3 新增) | 反例 25 字节级 patch 入仓决策 09,搭车 + 一次性授权 |

### 12.3 后续 Task 接力点

- **TASK-402 / 403**(前端 UI):消费 `docs/06_OUTPUT_CONTRACTS.md` § 2 字段表 dispatch 卡片;TypeScript 可从 `schemas/project_overview.schema.json` 自动 codegen DTO
- **TASK-305**(教学 Prompt 优化):若评测显示字段约束需调整(如 key_files min 从 3 放宽),走 D5 两层同源流程
- **TASK-307**(完整 CitationEnforcer):本 Task `evidence` 字段静态校验保留,跨工程引用幻觉检测 + 召回率评测由 TASK-307 接管
- **Phase 2**:
  - B / C / D / E 类 schema 统一化(TASK-208 候选,或 Week 3 配合 prompt 优化)
  - `_StrictBaseModel` 收口到共享基类(独立 chore PR)
  - `pydantic` 显式加进 requirements.txt 锁版本(独立 chore PR)
  - JSON Schema 升级到 JSON Schema 2020-12(若 pydantic 输出迁移)

### 12.4 Phase 2 候选

- B / C / D / E 类 schema 统一化 + freeze test
- TypeScript codegen 自动化(`scripts/generate_frontend_types.py`)
- 评测脚本 `eval/run_eval.py` 集成 schema 守门
- docstring linter / mypy plugin 守门(超出本 Task 范围)
- `verify-schema` 集成到 CI(若 pydantic 升级节奏稳定)
- 多 schema 版本(v0.1 / v0.2 共存,前端按 Accept-Version header dispatch)

---

## Checklist(精简)

**实施前**:已读 5 核心文档 + 决策 04/05/06/07/08/09/11 + 反例 1-25(反例 25 本 Task D7 入仓);实地核查 `overview_schemas.py` 64 行 + `overview_service.py` 164 行 + `project_overview.yaml` 57 行 + `05 § 2.A` 字段表 + 03 索引 line 119-121 / 338 / 342 + pydantic 2.12.4;理解 D2 introspection freeze + D5 两层同源(通用 4 处 + project_type 6 处 + checklist 三问)+ D7 反例 25 治理 chore + 反例 25 入仓追加。

**完工前**:§ 11.2 验收 1-15 全过;commit subject 单行无 body(反例 17);完工三件套(决策 08);03 索引字节级修订(4 行)+ 决策 09 反例 25 追加;PR(Codex 给 PM 标题 + 正文)。

---

**版本**:v0.2(R1 conditional pass / 3 P0 + 5 P1 + 3 P2 全采纳 / 不升 R2 / 直接进 Codex)
**日期**:2026-06-05
**作者**:Claude(架构师,第十五任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / `20260604-11`
**关联反例**:反例 25(本 Task D7 治理 chore 入仓决策 09)+ 反例 24(docstring 漂移,本 Task freeze test 是同源防御机制)
**审批历史**:R1 conditional pass(20260605,3 P0 + 5 P1 + 3 P2 全采纳)→ 直接进 Codex
**审批**:**一审 1 轮**(若实施期出现"改 schema 字段 / 推翻 D2 introspection 策略 / 推翻 D5 两层流程 / 引入新依赖 / 改 service 行为"等任一,**必须自动升 R2**)
**前置 commit**:main HEAD `746a76d`(TASK-206 merge)
