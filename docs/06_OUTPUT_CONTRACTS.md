# 教学输出契约 · OUTPUT CONTRACTS

> 本文是 mxa-tutor 教学输出的**契约级 reference**,给前端、评测、第三方消费者使用。
> `05_EXPLANATION_STYLE_GUIDE.md` 是给 LLM 的教学口吻规范;本文是给 schema 消费者的稳定契约。
> 与本文冲突的实现 / PR,一律打回返工。
> **版本:v0.1(本 Task 起 freeze)**

---

## 0. 范围

本文覆盖 A 类输出:项目总览(Project Overview),即上传解析完成后首屏展示的结构化 JSON。
本文另在 § 8 补充检索层 `ChunkRecord` 契约说明,用于前端 / 评测 / RAG 消费者理解
chunk 元数据字段和 `source_type` 词表。

本文不覆盖:

- B 类 Simulink Block / Subsystem 讲解:markdown 输出,见 05 § 3
- C 类 MATLAB `.m` 文件讲解:markdown 输出,见 05 § 4
- D 类 工程问答 QA:见 `features/chat/chat_schemas.py`
- E 类 不确定 / 证据不足回答:同 D 类中的 `is_fallback` / `fallback_reason`

B-E 类 schema 统一化推到 TASK-208 / Week 3。本文只冻结 A 类 `ProjectOverview`。

---

## 1. 契约级别

A 类 `ProjectOverview` schema 处于**契约级**。它不是一次 prompt 输出样例,而是后续前端、评测和第三方消费的稳定接口。

契约锚点:

- Domain 契约源:`core/domain/project_overview.py`
- Pydantic wrapper / JSON Schema 源:`features/overview/overview_schemas.py`
- JSON 导出:`schemas/project_overview.schema.json`
- Freeze 测试:`tests/features/overview/test_schema_freeze.py`
- Prompt 对齐:`core/prompts/project_overview.yaml`
- Service 校验:`features/overview/overview_service.py` 五步校验

任一 schema 修改必须按 § 7 的 D1-B 三层同源流程走。Freeze 测试失败不是“测试太严”,而是提醒 PR 作者同步契约、wrapper、测试、导出 JSON 和下游说明。

---

## 2. 字段表(12 顶层 + 5 子 schema)

### 2.1 顶层字段

| 字段 | 类型 | 约束 | 语义 | 教学要求 |
|---|---|---|---|---|
| `project_title` | string | 1-30 字 | 工程标题 | 学生首屏看到的卡片标题,短而具体 |
| `project_type` | enum(7) | 见 § 3 | 工程分类 | 影响 UI 模板和知识点关联;契约源是 `core/domain/project_overview.py::ProjectTypeValue`,不是 `core/domain/project.py::ProjectType` |
| `one_sentence_summary` | string | 1-80 字 | 一句话讲清楚工程做什么 | 像老师介绍课题,不是百科定义 |
| `main_entry_files` | array[`EntryFileEntry`] | 1-3 个 | 主入口脚本 / 首读文件 | 学生第一步该打开的文件 |
| `main_simulink_models` | array[`SimulinkModelEntry`] | 0-5 个 | 顶层 Simulink 模型 | 纯 `.m` 工程可为空数组 |
| `main_execution_flow` | array[string] | 3-10 步 | 工程执行流 | 自然语言步骤,不是函数名清单 |
| `key_files` | array[`KeyFileEntry`] | 1-8 个 | 关键文件 | 只列“学生该看”的文件,不是全量文件树 |
| `key_blocks` | array[`BlockEntry`] | 0-10 个 | 关键 Simulink block | 无 Simulink 或无关键 block 时可为空 |
| `knowledge_points` | array[string] | 3-6 个 | 关联课程知识点 | 对齐中文工科课程术语 |
| `beginner_reading_order` | array[string] | 3-6 步 | 新手阅读顺序 | 必须给具体动作,不能写“先理解基础概念” |
| `likely_confusing_points` | array[string] | 2-5 个 | 学生容易卡住的问题 | 必须是看工程会问的问题,不是教科书难点 |
| `evidence` | array[`SourceRefEntry`] | 至少 1 个 | 证据引用 | 壁垒 3:无证据不许硬答 |

### 2.2 EntryFileEntry / SimulinkModelEntry / KeyFileEntry

`EntryFileEntry` 描述入口文件:

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| `file_path` | string | min_length=1 | `"run_simulation.m"` | 必须来自解析出的工程文件列表 |
| `role` | string | 1-100 字 | `"主入口脚本,设置参数并启动仿真"` | 说明这个入口在工程里负责什么 |

`SimulinkModelEntry` 描述顶层模型:

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| `file_path` | string | min_length=1 | `"pmsm_foc.slx"` | 必须是解析出的 `.slx` 模型文件 |
| `summary` | string | 1-200 字 | `"顶层模型,含速度环、电流环和 PMSM 本体"` | 用工程语境概括模型结构 |

`KeyFileEntry` 描述关键文件:

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| `file_path` | string | min_length=1 | `"init_params.m"` | 必须来自解析出的工程文件列表 |
| `why_key` | string | 1-200 字 | `"所有可调参数集中在这里"` | 解释为什么学生需要优先看它 |

### 2.3 BlockEntry

`BlockEntry` 只用于 Simulink 工程里的关键 block。纯 MATLAB `.m` 工程可以让顶层 `key_blocks` 为空数组。

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| `block_name` | string | min_length=1 | `"SpeedController"` | 必须来自解析出的 Simulink Block 列表 |
| `block_type` | string | min_length=1 | `"PID Controller"` | 必须与解析出的 block 类型一致 |
| `location` | string | min_length=1 | `"pmsm_foc.slx / SpeedLoop"` | 必须使用 `{file_path} / {parent_subsystem or <root>}` |
| `why_key` | string | 1-200 字 | `"速度环核心,影响整个系统响应"` | 说明为什么这个 block 影响理解工程 |

`location` 的分隔符是字面 `" / "`。顶层 block 使用 `<root>`,如 `pmsm_foc.slx / <root>`。

### 2.4 SourceRefEntry

`SourceRefEntry` 是所有讲解的证据锚。`file_path` 必填,`line_range` 和 `block_id` 至少应按实际证据择一填写;schema 允许两者都为空,但 service 会校验已填写的引用是否合法。

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| `file_path` | string | min_length=1 | `"init_params.m"` | 必须来自解析出的工程文件列表 |
| `line_range` | tuple[int, int] \| null | start >= 1, end >= start | `[1, 30]` | 用于 `.m` / 文本文件行号证据 |
| `block_id` | string \| null | 若填写必须存在 | `"SpeedLoop/PID"` | 用于 Simulink block 证据 |

示例:`{"file_path": "init_params.m", "line_range": [1, 30], "block_id": null}`。

---

## 3. project_type 7 枚举值

**契约源**:`core/domain/project_overview.py::ProjectTypeValue` 的 `Literal[7]` 字面。它不是 `core/domain/project.py::ProjectType`;后者服务内部分类逻辑,本文只冻结输出层词表。

新增、删除或改名任何 `project_type` 时,必须走 § 7 第二层 6 同源流程。

| 字面值 | 中文描述 | 何时选择 |
|---|---|---|
| `control_system` | 控制系统 | PID、状态空间、闭环响应、鲁棒控制、Simulink 控制框图是主线 |
| `signal_processing` | 信号处理 | 滤波、频谱、FFT、采样、去噪、特征提取是主线 |
| `power_electronics` | 电力电子 | 整流、逆变、DC-DC、PWM、开关器件、变换器拓扑是主线 |
| `communication` | 通信系统 | 调制解调、信道、编码、同步、误码率仿真是主线 |
| `motor_control` | 电机控制 | PMSM、BLDC、FOC、dq 变换、速度环 / 电流环是主线 |
| `new_energy` | 新能源 | 光伏、风电、储能、并网、MPPT、微电网是主线 |
| `general` | 通用工程 | 无法稳定归入以上 6 类,或工程主题明显混合且没有单一主线 |

选择优先级:先看工程主入口和核心模型的目标,再看关键 block / 文件。不要因为出现一个 PID block 就直接选 `control_system`;如果工程主线是 PMSM FOC,应选 `motor_control`。

---

## 4. Service 五步校验(实施层防御)

`ProjectOverview` 先由 Pydantic schema 校验字段和长度,再由 `features/overview/overview_service.py` 做工程语义校验:

1. `main_entry_files.file_path`、`key_files.file_path`、`evidence.file_path` 必须来自工程文件列表。
2. `main_simulink_models.file_path` 必须来自解析出的 `.slx` 模型文件列表。
3. `BlockEntry.location` 必须能按字面 `" / "` 拆成 `(model_path, parent)`。
4. 每个 `BlockEntry` 必须匹配已解析 block 四元组:`model_path + block_name + block_type + parent_subsystem`。
5. `evidence.block_id` 若填写,必须存在;`evidence.line_range` 若填写,必须满足 `start >= 1` 且 `end >= start`。

这五步不会替代 schema freeze。它们是运行时防御,用于拦截 LLM 编造文件、block 或非法证据。

---

## 5. 教学口吻硬要求(对齐 05 § 8)

本文不重复 05 § 8 全文。消费者只需要知道:所有字段展示给学生时,都必须保持“具体、温和、基于工程证据”的中文教学口吻。

写法要求:

- 讲“这个工程里它做什么”,不要讲百科定义。
- 讲“下一步该看哪里 / 怎么读”,不要只给抽象建议。
- 术语使用中文工科课堂常见说法,必要时保留英文缩写,如“矢量控制 / FOC”。
- 有证据时给判断;证据不足时明确说“未能确定 X”,不要用模糊语气假装知道。
- `likely_confusing_points` 写学生看工程会问的问题,不是课程目录。

---

## 6. 反模式 + 示例

以下 JSON 片段均为反例,不能作为合法输出。

反模式 1:额外字段。`extra="forbid"` 会拒绝:

```json
{"project_title": "PMSM 仿真", "project_type": "motor_control", "confidence": 0.92}
```

反模式 2:`project_type` 使用非 Literal 字面:

```json
{"project_type": "electrical_control"}
```

反模式 3:阅读顺序是空话,没有具体文件或动作:

```json
{"beginner_reading_order": ["1. 先理解基础概念", "2. 再阅读核心代码", "3. 最后进行调试"]}
```

反模式 4:证据不是工程内文件:

```json
{"evidence": [{"file_path": "textbook.pdf", "line_range": [10, 20], "block_id": null}]}
```

反模式 5:`main_simulink_models` 引用非 `.slx` 文件:

```json
{"main_simulink_models": [{"file_path": "plot_results.m", "summary": "画仿真曲线"}]}
```

反模式 6:`BlockEntry.location` 形状错误或 block 编造:

```json
{"key_blocks": [{"block_name": "MagicController", "block_type": "PID Controller", "location": "pmsm_foc.slx > SpeedLoop", "why_key": "核心控制器"}]}
```

---

## 7. Schema 修订流程

Schema 可以演进,但不能偷偷漂移。任何修订 PR 必须按 D1-B 三层同源处理。

第一层:通用 schema 修订必改 5 处:

1. `core/domain/project_overview.py`
2. `features/overview/overview_schemas.py`
3. `tests/features/overview/test_schema_freeze.py`
4. `docs/06_OUTPUT_CONTRACTS.md`
5. `schemas/project_overview.schema.json`(跑 `make export-schema` 重生)

第二层:若涉及 `project_type Literal[7]`,还必须同步 2 处:

6. `core/prompts/project_overview.yaml`
7. `docs/05_EXPLANATION_STYLE_GUIDE.md` § 2.A / 示例处

第三层:任何 schema 修订 PR 必须在 review checklist 显式回答:

- prompt yaml 是否需要同步:是 / 否 + 理由
- overview_service 五步校验是否需要同步:是 / 否 + 理由
- 评测脚本 `eval/run_eval.py` 字段表是否需要同步:是 / 否 + 理由

paper-to-model 输出契约新增或修订时,沿用 D1-B 三层同源流程,但真值源路径独立于
`ProjectOverview`:

1. `core/domain/paper_*.py` domain dataclass / contract
2. `features/paper/paper_schemas.py` Pydantic wrapper
3. `tests/features/paper/test_paper_schema_freeze.py`
4. `docs/06_OUTPUT_CONTRACTS.md` § 12
5. `schemas/paper_*.schema.json`

以上路径是 TASK-501 落地占位名,实际文件名可在实施 PR 中微调;但任一字段、Literal 或
证据不变量变更,必须在同一 PR 内同步 domain / wrapper / freeze test / JSON schema / 本文。

推荐本地命令:

```bash
pytest tests/features/overview/test_schema_freeze.py -v
make verify-schema
```

---

## 8. ChunkRecord Schema(RAG 检索层)

`ChunkRecord` 是进入向量库和 RAG 检索链路的 chunk 元数据契约。本文描述其消费语义;
实现真值源仍是 `core/interfaces/vector_store.py:25-41::ChunkRecord` 和
`core/interfaces/vector_store.py:10-20::SourceType`。

### 8.1 字段表(14 字段)

| 字段 | 类型 | 可空 | 语义 |
|---|---|---|---|
| `chunk_id` | string | 否 | chunk 全局稳定 ID,由 `make_chunk_id` / `make_overview_chunk_id` 生成 |
| `project_id` | string | 否 | 所属上传工程 ID |
| `source_type` | `SourceType` | 否 | chunk 来源类型,见 § 8.2 |
| `file_path` | string | 否 | 工程内相对路径;项目总览使用 `__project_overview__` |
| `symbol_name` | string | 是 | 函数名、脚本段名、变量名、子系统名或 C/H section 标题 |
| `line_range` | tuple[int, int] | 是 | 源码行号范围;适用于 `.m` / `.c` / `.h` 等文本来源 |
| `block_id` | string | 是 | Simulink block ID;仅 block chunk 必填 |
| `block_name` | string | 是 | Simulink block / subsystem 展示名 |
| `block_type` | string | 是 | Simulink block 类型;非 block 来源为空 |
| `parent_subsystem` | string | 是 | 所属父子系统;顶层或非 Simulink 来源为空 |
| `source_text` | string | 否 | 用于 embedding 和 LLM 上下文的隐私加工文本,不是原始文件全文 |
| `embedding` | list[float] | 否 | 预计算向量 |
| `model_name` | string | 否 | embedding 模型名 |
| `created_at` | datetime | 是 | chunk 入库时间;未持久化前可为空 |

### 8.2 SourceType 9 枚举值

| 字面值 | 语义 | 当前用途 |
|---|---|---|
| `c_file` | C 源码 section chunk | `.c` 顶层结构切段,映射到 chat 层 `function` |
| `h_file` | C header section chunk | `.h` 头文件切段,映射到 chat 层 `function` |
| `m_file` | MATLAB 文件 / 脚本段 chunk | `.m` 文件概览和脚本 section |
| `m_function` | MATLAB 函数 chunk | `.m` 文件中的函数定义 |
| `mat_variable` | MAT 变量 chunk | `.mat` 变量元数据 |
| `project_overview` | 项目总览 chunk | overview service 单独产出 |
| `slx_block` | Simulink block chunk | 有工程语义的 block 参数和标记 |
| `slx_subsystem` | Simulink subsystem chunk | 子系统及其子 block 摘要 |
| `teaching_unit` | 教学单元 chunk | reserved,当前不由项目 chunker 产出 |

`RESERVED_SOURCE_TYPES` 当前仅包含 `teaching_unit`。`c_file` / `h_file` 已是正式生效类型,
不属于 reserved。

### 8.3 隐私与证据边界

- `source_text` 是加工后的教学 / 检索文本,不得持久化大段原始源码。
- `.c` / `.h` chunk 的证据摘录最多保留 10 行连续原始代码。
- 日志只允许记录路径、行号、函数名、扩展名和原因,不得记录源码内容。
- Chat 层 `RetrievalHit.source_type` 不扩展 `c_file` / `h_file`;VectorRetriever 将二者映射为
  `function`,保持下游问答 schema 稳定。

---

## 9. 评测维度(对齐 05 § 10)

评测脚本消费 `ProjectOverview` 时,至少应看这些维度:

- 字段填充率:12 个顶层字段是否齐全,数组数量是否落在约束范围内。
- 教学口吻评分:是否像老师讲工程,而不是百科式定义。
- 证据引用覆盖率:`evidence` 是否覆盖标题、入口、关键文件、关键 block 等核心判断。
- 证据合法性:引用文件、block_id、line_range 是否能被 service 校验通过。
- 中文术语对齐:是否使用“速度环 / 电流环 / dq 坐标系”等学生熟悉的术语。
- 新手可执行性:`beginner_reading_order` 是否给出具体文件和动作。
- 不确定性处理:遇到 unresolved symbol 或证据不足时,是否明确写“未能确定 X”。

---

## 10. 与 05 / Prompt yaml / Service 的对应关系

| 层 | 文件 | 职责 | 与本文关系 |
|---|---|---|---|
| 教学规范 | `docs/05_EXPLANATION_STYLE_GUIDE.md` | 规定 LLM 该怎么讲 | 本文引用 05,不复制全文 |
| Prompt | `core/prompts/project_overview.yaml` | 约束 LLM 输出 12 字段和 7 类型 | `project_type` 修订必须同步 |
| Domain 契约 | `core/domain/project_overview.py` | 字段名、顺序、类型和 project_type Literal 真值源 | 本文的跨 feature 契约源 |
| Schema wrapper | `features/overview/overview_schemas.py` | Pydantic 字段约束、API response_model、JSON Schema 导出源 | 包装 domain 契约并提供 `.to_domain()` / `.from_domain()` |
| Service 校验 | `features/overview/overview_service.py` | 拦截编造文件、block、证据 | 本文 § 4 描述其语义 |
| Freeze 测试 | `tests/features/overview/test_schema_freeze.py` | 锁字段名、类型、约束、Literal、extra | 防止无意漂移 |
| JSON 导出 | `schemas/project_overview.schema.json` | 前端 / 第三方消费 reference | 由脚本生成后入仓 |

边界:05 给 LLM 和评测看,06 给消费者和 review 看,prompt 是实现层输入,service 是运行时防御。四者职责不同,但 schema 修订时必须同源。

---

## 11. 版本

v0.1 - 2026-06-05 起 freeze,与 TASK-203 commit `871c8e2` 的 `ProjectOverview` 实现一致。

本版本冻结:

- 12 个顶层字段
- 5 个子 schema
- `ProjectTypeValue Literal[7]`
- 顶层和子字段的 min_length / max_length
- 所有 schema 层级的 `extra="forbid"`

下一次修改以上任一项,必须按 § 7 修订流程走同 PR 同源。

---

## 12. paper-to-model 输出契约

本节覆盖 C 类资料复现副驾输出:从论文 / 报告 / 文献中抽取结构化规格,给出模型搭建路线图,
并在参数缺失时提示用户补充。它是 v0.1 草稿契约,字段未冻结;TASK-501 落地时必须按
§ 7 的 D1-B 三层同源流程演进。

本节不覆盖 `ProjectOverview`,也不改造既有 MCS 工程导览契约。`PaperGraph` 已在
`02_ARCHITECTURE_OVERVIEW.md` § 4.2 v3.0 delta 中作为独立结构占位;本节仅引用该占位,
不写 `PaperGraph` 字段表。

### 12.1 资料入口领域枚举

资料入口的 `domain` 只接受既有 `project_type` 中的 6 个具体工程领域,不接受 `general`。

| 字面值 | 语义 |
|---|---|
| `control_system` | 控制系统资料 |
| `signal_processing` | 信号处理资料 |
| `power_electronics` | 电力电子资料 |
| `communication` | 通信系统资料 |
| `motor_control` | 电机控制资料 |
| `new_energy` | 新能源资料 |

`general` 只作为 MCS 工程入口的兜底分类存在。资料入口若无法归入以上 6 类,应拒绝并提示用户选择具体领域。

### 12.2 EvidenceSource enum

`EvidenceSource` 是 paper-to-model 参数和证据的双源标记。

| 字面值 | 语义 | 使用场景 |
|---|---|---|
| `document_extracted` | 来自上传资料的文本 / 公式 / 图表位置 | PaperSpec 中抽到的参数、公式、段落证据 |
| `user_supplied` | 用户在缺失参数流程中补充 | MissingParameterPrompt 回填后的参数 |

任何参数来源都必须保留该标记。用户补充值不得伪装成文档证据。

### 12.3 PaperEvidenceEntry schema

`PaperEvidenceEntry` 是 paper-to-model 独立证据条目,与
`features/explanation/_evidence_builder.py::EvidencePack` 无包含、继承或引用关系。后者服务
.slx 工程解释语境;本条目服务论文 / 报告的段落、公式和图表语境。

**状态**:v0.1 草稿,字段未冻结。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `source` | `EvidenceSource` | 必填 | 证据来源 |
| `paper_section_id` | string \| null | 见不变量 | 文档段落 / 小节 ID |
| `equation_id` | string \| null | 见不变量 | 公式 ID |
| `figure_id` | string \| null | 见不变量 | 图表 ID |
| `excerpt` | string \| null | 见不变量 | 文档原文摘录 |
| `missing_param_prompt_id` | string \| null | 见不变量 | 用户补充流程关联 ID |

两套不变量:

- `source = document_extracted`: `paper_section_id` / `equation_id` / `figure_id` 至少一个非
  null;`excerpt` 必须是 1-300 字非空字符串;`missing_param_prompt_id` 必须为 null。
- `source = user_supplied`: `paper_section_id` / `equation_id` / `figure_id` 全部为 null;
  `excerpt` 必须为 null;`missing_param_prompt_id` 必填,并关联到
  `MissingParameterPrompt.prompt_id`。

Python 实现占位路径:`core/domain/paper_evidence.py` domain dataclass / contract,以及
`features/paper/paper_schemas.py` Pydantic wrapper。TASK-500 不落地 Python 实现。

### 12.4 PaperSpec schema

`PaperSpec` 描述论文 / 报告的结构化规格。

**状态**:v0.1 草稿,字段未冻结。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `paper_title` | string | 1-200 字 | 资料标题 |
| `paper_type` | `Literal["paper", "report", "thesis"]` | 必填 | 资料类型 |
| `domain` | 资料入口领域枚举 | 不含 `general` | 工程领域 |
| `abstract` | string | 1-1000 字 | 摘要或任务陈述 |
| `equations` | array[`EquationEntry`] | 0-N | 公式列表 |
| `parameter_table` | array[`ParameterEntry`] | 0-N | 参数表 |
| `figure_locations` | array[`FigureRef`] | 0-N | 图表位置 |
| `pseudocode_blocks` | array[string] | 0-N | 伪代码 / 算法段 |
| `evidence` | array[`PaperEvidenceEntry`] | 至少 1 个 | 结构化抽取证据 |

子项草稿:

| 子项 | 字段 |
|---|---|
| `EquationEntry` | `equation_id` / `latex_or_text` / `paper_section_id` |
| `ParameterEntry` | `name` / `symbol` / `value` / `unit` / `source` |
| `FigureRef` | `figure_id` / `caption` / `paper_section_id` |

### 12.5 ModelGenerationPlan schema

`ModelGenerationPlan` 描述模型搭建路线图,给会用 MATLAB / Simulink 的用户按步骤复现。

**状态**:v0.1 草稿,字段未冻结。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `plan_id` | string | 必填 | 路线图 ID |
| `paper_spec_id` | string | 必填 | 关联 `PaperSpec` |
| `library_choice` | string | 1-300 字 | 库选型建议 + 选型理由(如 `SimPowerSystems(电机短路类工程标准库;论文 d/q 轴电抗 / 时间常数 / 阻尼参数与 SimPowerSystems 的 Synchronous Machine pu Standard block 参数槽位直接对应)`) |
| `block_recommendations` | array[`BlockRecommendation`] | 0-N | block 建议 |
| `parameter_mapping` | array[`ParameterMapping`] | 0-N | 论文参数到模型参数的对应说明 |
| `subsystem_breakdown` | array[string] | 3-10 步 | 子系统拆分建议 |
| `m_script_skeleton` | string \| null | 可空 | 尽力交付的 `.m` 骨架 |
| `evidence` | array[`PaperEvidenceEntry`] | 至少 1 个 | 路线图证据 |

子项草稿:

| 子项 | 字段 |
|---|---|
| `BlockRecommendation` | `block_type` / `purpose` / `paper_reference` |
| `ParameterMapping` | `paper_param_name` / `model_param_name` / `value` / `unit` / `source` |

**子项约束补充**(v0.3.2 微补丁,基于样本包实测驱动):

- `ParameterMapping.unit` 允许为 `null`:配置参数如接线方式 `Yn / d11` / 模式选择 / 布尔配置等无物理单位的情况(实测样本包 `expected_updated_plan.json` 第 19 项变压器接线为此场景)
- `ParameterMapping.value` 类型为 `string`(允许带单位文字描述,不强制 numeric)
- `EquationEntry.equation_text` / `PaperEvidenceEntry.excerpt` 等已含字面约束的字段保持不变

**修订历史**:v0.1(2026-06-15 起稿期)→ v0.3.2(2026-06-16 微补丁;TASK-501 Stage 2 sample roundtrip 实测驱动)

### 12.6 TuningSuggestion schema

`TuningSuggestion` 描述面向用户场景的调参方向。它给方向和物理影响,不承诺运行结果或最优调参。

**状态**:v0.1 草稿,字段未冻结。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `suggestion_id` | string | 必填 | 建议 ID |
| `user_scenario` | string | 1-500 字 | 用户描述的调参场景 |
| `parameter_directions` | array[`ParameterDirection`] | 1-N | 参数方向列表 |
| `expected_effect` | string | 1-500 字 | 预期物理影响讲解 |
| `confidence` | `Literal["high", "medium", "low"]` | 必填 | 建议置信度 |
| `evidence` | array[`PaperEvidenceEntry`] | 至少 1 个 | 建议依据 |
| `disclaimer` | string | 必填 | 固定提示:建议需用户在 MATLAB 中验证 |

子项草稿:

| 子项 | 字段 |
|---|---|
| `ParameterDirection` | `param_name` / `direction` / `physical_meaning` |

`direction` 取值:`increase` / `decrease` / `tune_within_range`。

### 12.7 MissingParameterPrompt schema

`MissingParameterPrompt` 描述资料中出现线索但 v0.1 无法抽到值或单位的参数补充项。

**状态**:v0.1 草稿,字段未冻结。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `prompt_id` | string | 必填 | 缺失参数提示 ID |
| `parameter_name` | string | 必填 | 待补充参数名 |
| `paper_reference` | `PaperEvidenceEntry` | 必填 | 文档中出现该线索的位置 |
| `suggested_unit` | string \| null | 可空 | 从上下文推断的单位建议 |
| `user_supplied_value` | string \| null | 回填前为空 | 用户补充值 |
| `user_supplied_unit` | string \| null | 回填前为空 | 用户补充单位 |
| `source` | `Literal["user_supplied"]` | 恒定值 | 体现双源契约 |

`paper_reference.source` 必须是 `document_extracted`,用于指出缺失线索来自哪里;用户回填后的参数证据
另以 `source = user_supplied` 的 `PaperEvidenceEntry` 表示。

### 12.8 反模式

反模式 1:资料入口使用 `general`:

```json
{"domain": "general", "paper_title": "某仿真实验报告"}
```

反模式 2:用户补充证据伪装成文档证据:

```json
{
  "source": "document_extracted",
  "paper_section_id": "sec-5",
  "equation_id": null,
  "figure_id": null,
  "excerpt": "用户补充 H = 3.5 s",
  "missing_param_prompt_id": "mp-001"
}
```

反模式 3:文档证据没有 locator 或摘录:

```json
{
  "source": "document_extracted",
  "paper_section_id": null,
  "equation_id": null,
  "figure_id": null,
  "excerpt": null,
  "missing_param_prompt_id": null
}
```

反模式 4:把 `PaperEvidenceEntry` 当作 explanation 的 `EvidencePack` 子集消费:

```json
{"evidence_pack_kind": "parameter_context", "paper_section_id": "sec-2"}
```

## 13. MATLAB Bridge Diagnostic 契约(TASK-510)

`BridgeDiagnostic` 只证明 MATLAB Add-on 到后端的诊断传输桥可达。它不接 MATLAB Engine、不调用 LLM、不生成报错解释、不回传建议、不持久化用户正文。

**状态**:v0.3-a 冻结。

| 同步项 | 路径 |
|---|---|
| Domain | `core/domain/bridge_diagnostic.py` |
| Pydantic wrapper | `features/matlab_bridge/bridge_diagnostic_schemas.py` |
| JSON Schema | `schemas/bridge_diagnostic_request.schema.json` / `schemas/bridge_diagnostic_receipt.schema.json` / `schemas/bridge_error_response.schema.json` |
| 导出脚本 | `scripts/export_bridge_schemas.py` |
| Freeze 测试 | `tests/features/matlab_bridge/test_bridge_diagnostic_schema_freeze.py` |
| 边界测试 | `tests/features/matlab_bridge/test_bridge_diagnostic_schemas.py` |

### 13.1 BridgeDiagnosticRequest

请求端点:`POST /api/v1/bridge/diagnostic`,`Content-Type: application/json`。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `protocol_version` | `Literal["0.3-a"]` | 必填 | v0.3-a 传输桥协议 |
| `request_id` | UUID4 | 必填 | 客户端生成的请求 ID |
| `diagnostic_kind` | `Literal["manual_error"]` | 必填 | 用户手动粘贴错误文本 |
| `matlab_release` | string | `^R20[0-9]{2}[ab]$` | MATLAB release,本卡实测 R2026a |
| `client_version` | string | `^[A-Za-z0-9.\-]{1,32}$` | Add-on 版本,本卡为 `0.1.0` |
| `error_text` | string | strip 后 1-4096 Unicode 字符,拒 NUL | 用户确认后的脱敏文本 |
| `consent_confirmed` | StrictBool | 必须为 `true` | 用户已确认发送同一脱敏快照 |

`extra="forbid"`。显式拒绝字段:`file_path` / `source_code` / `slx_path` / `workspace` / `stack` / `project_files` / `model_content` / `files`。

### 13.2 BridgeDiagnosticReceipt

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `request_id` | UUID4 | 与请求相同 | 回执关联 ID |
| `status` | `Literal["received"]` | 固定 | 后端已收到 |
| `mode` | `Literal["connectivity_stub"]` | 固定 | 连接回执 stub |
| `message` | string | 固定文案 | `连接成功。本版本仅验证诊断信息传输,不提供报错解释。` |

### 13.3 BridgeErrorResponse

Bridge guard 错误响应只含 `{error,message}`:

| 状态码 | `error` | `message` |
|---|---|---|
| 403 | `matlab_bridge_forbidden` | `仅允许本机 MATLAB Add-on 访问` |
| 413 | `bridge_payload_too_large` | `诊断内容过大` |
| 415 | `bridge_unsupported_media_type` | `仅支持 application/json` |

422 沿用全局 `{error,message}`: `validation_error` / `请求参数有问题,请检查后重试`。404 沿用全局 404;feature flag 关闭时整个 bridge path 不注册。

### 13.4 前置 guard 顺序

Bridge route 使用 path-scoped custom `APIRoute` / `Request`,顺序固定为:feature flag 注册路由 → loopback → Content-Type → 实际 body 字节数 `>32768` → JSON → Pydantic → service。不得用普通 dependency 替代前三个请求边界。
