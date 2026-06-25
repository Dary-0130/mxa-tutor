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

## 14. MATLAB Bridge Error Explanation 契约(TASK-511 b1 / TASK-514 b2-1B)

`BridgeExplanation` 用于一次 LLM 报错解释。`manual_error` 保持 v0.3-a 连接回执之后用同一个 `request_id` 请求解释;`auto_captured_error` 由客户端自动采集、脱敏、截断并经用户确认后直发 `/explanation`,不走 `/diagnostic` ACK。两种来源都不接 MATLAB Engine、不运行仿真、不验证文件或工具箱状态。质量评估和真实 case 覆盖留到后续 seam;本契约只冻结传输、结构、安全护栏和错误映射。

**状态**:v0.3-b1 冻结。

| 同步项 | 路径 |
|---|---|
| Domain | `core/domain/bridge_explanation.py` |
| Pydantic wrapper | `features/matlab_bridge/bridge_explanation_schemas.py` |
| JSON Schema | `schemas/bridge_explanation_request.schema.json` / `schemas/bridge_explanation_result.schema.json` / `schemas/bridge_explanation_error.schema.json` |
| 导出脚本 | `scripts/export_bridge_schemas.py` |
| Freeze 测试 | `tests/features/matlab_bridge/test_bridge_explanation_schema_freeze.py` |
| 边界测试 | `tests/features/matlab_bridge/test_bridge_explanation_schemas.py` |

### 14.1 BridgeExplanationRequest

请求端点:`POST /api/v1/bridge/explanation`,`Content-Type: application/json`。该端点与 diagnostic 挂在同一个 `MatlabBridgeRoute`,共享 loopback / Content-Type / 32KB body guard。

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `protocol_version` | `Literal["0.3-b1"]` | 必填 | 报错解释协议 |
| `request_id` | UUID4 | manual 与 ACK 同一个 ID;auto 为客户端本次解释请求 ID | 请求关联 |
| `diagnostic_kind` | `Literal["manual_error","auto_captured_error"]` | 必填 | 输入来源标签:`manual_error`=用户手动粘贴错误文本;`auto_captured_error`=客户端自动采集的错误文本 |
| `matlab_release` | string | `^R20[0-9]{2}[ab]$` | MATLAB release |
| `client_version` | string | `^[A-Za-z0-9.\-]{1,32}$` | Add-on 版本 |
| `error_text` | string | strip 后 1-4096 Unicode 字符,拒 NUL | 用户确认后的脱敏文本;auto 超限必须带 `[TRUNCATED_AUTO_CAPTURE]` 截断标记;服务端调 provider 前会再次脱敏 |
| `llm_processing_consent_confirmed` | StrictBool | 必须为 `true` | 用户确认允许进行 LLM 解释,且确认的是最终发送的同一脱敏快照 |

`extra="forbid"`。显式拒绝字段与 diagnostic 一致:`file_path` / `source_code` / `slx_path` / `workspace` / `stack` / `project_files` / `model_content` / `files`。`diagnostic_kind` 只表示输入来源,不得提高解释置信度;`/diagnostic` v0.3-a stub 仍只接受 `manual_error`。

### 14.2 BridgeExplanationResult

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `protocol_version` | `Literal["0.3-b1"]` | 固定 | 报错解释协议 |
| `request_id` | UUID4 | 与请求相同 | 解释关联 ID |
| `status` | `Literal["completed"]` | 固定 | 已生成解释 |
| `mode` | `Literal["llm_error_explanation"]` | 固定 | 与 `connectivity_stub` 区分 |
| `meaning` | string | 1-1500 字 | 解释报错含义,不得新增环境事实 |
| `likely_causes` | array[`LikelyCause`] | 1-4 个 | 可能原因 |
| `next_steps` | array[`NextStep`] | 1-5 个 | 非破坏性排查动作 |
| `caveats` | array[string] | 1-3 个,每项 1-400 字 | 风险提示;manual 必须说明仅基于粘贴报错文本,auto 必须说明仅基于自动采集的报错文本 |

`LikelyCause`:

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `cause` | string | 1-400 字 | 可能原因 |
| `is_inference` | `Literal[true]` | 固定 | b1 不输出确定事实判断 |
| `confidence` | `Literal["low","medium"]` | 禁 high | 置信度 |
| `supporting_signals` | array[string] | 1-6 个,每项 8-200 字 | 必须是服务端二次脱敏后送入 provider 的文本精确子串 |

`NextStep` 只有 `action:string(1-400)`。步骤必须是非破坏性排查建议,不得伪装成已经执行。

### 14.3 Explanation 错误响应

Explanation 错误响应独立于旧 `BridgeErrorResponse` 的 Literal,但 shape 仍是 `{error,message}`。

| 触发 | HTTP | `error` |
|---|---:|---|
| provider 鉴权 / quota / rate / server 错误,或共享 provider 不可用 | 503 | `bridge_explanation_unavailable` |
| provider `LLMTimeoutError` 或服务端 `wait_for` deadline | 504 | `bridge_explanation_timeout` |
| 坏 JSON / schema / validator / 输出隐私扫描命中 | 502 | `bridge_explanation_failed` |

所有错误文案为固定中文友好文案,不得包含用户 `error_text` 正文、绝对路径或源码。隐私扫描命中时 fail-closed,不做替换后返回。

## 15. MATLAB Bridge Run-State 契约(TASK-516 b3-1 → TASK-518-B)

`BridgeRunState` 用于一次用户确认后的 MATLAB/Simulink run-state 快照持久化。客户端在用户本机 MATLAB 进程内经固定白名单 adapter 采集 `Simulink.SimulationOutput`,脱敏、降采样、冻结 JSON 并经用户确认后,发送到独立端点 `POST /api/v1/bridge/run-state`。服务端做结构校验、二次脱敏、隐私 fail-closed、权威 session 校验、幂等/冲突/顺序判定和 SQLite 持久化;不调 LLM、不运行用户模型、不接收原始 MAT/CSV。

**状态**:v0.3-b4 + TASK-517-B auth gate + TASK-518-B durable wiring。`/diagnostic`、`/explanation` 的 guard 与语义不变。`/run-state` 顺序固定为:loopback → `Content-Type: application/json` → 实际 body 字节数 `>32768` → replay → JSON/Pydantic(b4-only) → Bearer scoped-token 校验/撤销 → capability/session scope → verified auth context → service → 同一 SQLite `BEGIN IMMEDIATE` 写事务内 session 校验和持久化。`MAX_BRIDGE_BODY_BYTES` 保持 `32 * 1024`;客户端另做 `28 * 1024` UTF-8 字节预检。

| 同步项 | 路径 |
|---|---|
| Domain | `core/domain/bridge_run_state.py` |
| Pydantic wrapper | `features/matlab_bridge/bridge_run_state_schemas.py` |
| JSON Schema | `schemas/bridge_run_state_request.schema.json` / `schemas/bridge_run_state_receipt.schema.json` / `schemas/bridge_run_state_auth_error_response.schema.json` / `schemas/bridge_run_state_write_error.schema.json` |
| 导出脚本 | `scripts/export_bridge_schemas.py` |
| Freeze 测试 | `tests/features/matlab_bridge/test_bridge_run_state_schema_freeze.py` |
| 边界测试 | `tests/features/matlab_bridge/test_bridge_run_state_schemas.py` |

### 15.1 BridgeRunStateRequest

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `protocol_version` | `Literal["0.3-b4"]` | 必填;b3 拒绝 | 独立 run-state 协议 |
| `request_id` | UUID | 每个 HTTP 尝试一个 | 请求关联 |
| `session_id` | UUID | 必填 | 会话 scope 输入,非鉴权证明 |
| `run_id` | UUID | 一个逻辑快照一个;重试沿用 | 快照关联 |
| `run_sequence` | StrictInt | `0..1_000_000`,拒 bool/string | 会话内序号 |
| `matlab_release` | string | `^R20[0-9]{2}[ab]$` | MATLAB release |
| `client_version` | string | `^[A-Za-z0-9.\-]{1,32}$` | Add-on 版本 |
| `run_state_sharing_consent_confirmed` | StrictBool | 必须为 `true` | 用户确认共享并持久化 run-state 快照 |
| `consent_notice_version` | `Literal["run_state_persistence_v1"]` | 必填 | 客户端存储同意文案版本 |
| `run_status` | enum | `completed` / `stopped` / `execution_error` / `unknown` | 运行状态 |
| `convergence_status` | enum | `converged` / `not_converged` 仅允许配 `completed`;另有 `not_applicable` / `unknown` | 收敛状态 |
| `stop_reason` | string/null | ≤160 chars 且 ≤480 UTF-8 bytes,脱敏 | 非可信文本 |
| `solver` | string/null | ≤32 chars 且 ≤96 UTF-8 bytes,脱敏 | 求解器摘要 |
| `metrics_status` / `series_status` | enum | `available` 当且仅当对应容器非空;其它状态当且仅当容器为空 | 容器恒在 |
| `metrics` | array | ≤16,列表内 `name` 去重 | 有界指标 |
| `series` | array | ≤4,列表内 `series_id` 去重 | 有界波形摘要 |

`metrics[]`: `name` ≤32 chars/≤96 bytes;`value` 为有限 JSON number,拒 bool/string/null/NaN/Inf;`unit_status` 为 `known` / `unknown` / `not_applicable`;`unit` 当且仅当 `unit_status="known"` 存在,≤16 chars/≤48 bytes。

`series[]` 只接受两种表示:`identity_uniform_v1` 与 `min_max_envelope_uniform_v1`。公共字段:`series_id` 匹配 `^[A-Za-z0-9._\-]{1,32}$`;`label` ≤32 chars/≤96 bytes;`time_unit` 为 `s` / `ms` / `us` / `unknown`;`value_unit_status` 为 `known` / `unknown` / `not_applicable`;`value_unit` 当且仅当 `value_unit_status="known"` 存在,≤16 chars/≤48 bytes;`sample_order` 固定 `chronological`;`source_point_count` 为 StrictInt。

`identity_uniform_v1`: `2 ≤ source_point_count ≤ 192`;`t_start` 有限;`t_step > 0`;`y` 长度等于 `source_point_count`,每项有限。`min_max_envelope_uniform_v1`: `source_point_count > 192`;固定 96 桶;`bucket_width > 0`;`y_min` / `y_max` 各 96 项且 `y_min[i] ≤ y_max[i]`。

所有层级 `extra="forbid"`。敏感字段硬拒绝覆盖 diagnostic 字段并扩展 `mat_path` / `csv_path` / `raw_mat` / `raw_csv` / `base64` / `blob` / `compressed` / `archive` / `model_content` 等;所有字符串字段 Unicode NFC 规范化,拒 NUL、控制符和双向文本控制符。

### 15.2 Auth、Session 与持久化

`POST /api/v1/bridge/run-state` 必须携带单个 `Authorization: Bearer <access_token>` header。只接受一个 Authorization header、只接受 Bearer scheme、拒绝空值、重复 header、逗号拼接、多凭据、非法结构和超过独立 bearer 字节上限的 token。32KB body limit 不覆盖 header。

token scope 必须包含精确 capability `run_state:write`,并绑定 user/project/session。`body.session_id` 与 token `session_id` 经同一 run-state session 解析器得到 canonical value 后精确比较;鉴权层不得自行 trim、大小写折叠或做宽松等价。比较失败只返回 auth 403,不查 session、不写库、不进入 service。

authorization 不等于 consent:`run_state:write` 只表示 scoped-token 写入门通过,不代表持久化同意、LLM 处理同意、read/explain 能力或最终写事务授权。持久化同意来自每个新 `run_id` 的 `run_state_sharing_consent_confirmed=true` 与当前 `consent_notice_version`。同一冻结快照的 HTTP 重试不重新弹框;410 后必须新建会话/新快照并重新确认。

写事务在同一 SQLite `BEGIN IMMEDIATE` 边界内完成:从 `auth_context` 派生 scope → 校验权威 run-state session 存在、active、未逻辑过期、归属与 process generation 匹配 → 判幂等/冲突/顺序 → 先插入不可变 run 行 → 原子更新 current → commit。run 行永不 UPDATE。缺失、ended、gone、project 逻辑过期或旧 process generation 均为 410;归属/scope 不符为 403。

留存硬上限来自 `project_status_record.created_at + upload_ttl_hours`(默认 24h)。到点后 run-state 逻辑失效,读/写均 410,不依赖物理清理时机。物理清理由 run-state 专用 sweep 受控提前清除快照,文案口径为“最长不超过 24h,可能更早删除”。project 删除、session end/delete、TTL sweep 均清除 run 快照和 current。

### 15.3 客户端冻结、鉴权携带与降采样

客户端顺序固定:白名单读取 run-state → 所有字符串脱敏 → 有界截断/降采样 → 生成 `run_id` → 固定字段顺序构造 → `jsonencode` 一次得到 `frozen_json` / UTF-8 `frozen_bytes` → ≤28KB 预检 → 向用户预览同一份 JSON → 用户确认存储文案 → 运行期 token provider 取 access token → `Authorization` header 发送同一份 `frozen_json`。取消确认、采集失败、脱敏失败、非有限数值、预检超限、取 token 失败均 fail-closed。

确认文案仅 run-state 使用,覆盖数据类别、用途、持久化、最长留存和删除条件;不得套到 `/diagnostic` 或 `/explanation`。access token 只允许在 app 运行期私有内存/局部变量中流转,不得进入 base workspace、preferences、命令历史、日志、`.mltbx` 静态文件或 run-state JSON payload。bootstrap 凭据不得编进 `.mltbx`。`401` 时客户端最多重新向 provider 取一次 token,并重发同一份 `frozen_json` / 同一 `run_id`;409 不盲重试;410 提示新建会话并重新确认。

波形源序列必须为有限实数、严格递增、均匀时间轴。均匀判定常量固定为 `rel_tol = 1e-6`: `max(abs(diff(Time)-median(diff(Time)))) ≤ rel_tol * median(diff(Time))`。单点、非严格递增、非均匀源均不发出。≤192 点完整保留为 identity;>192 点降为 96 桶 min/max envelope,`bucket_width=(Time[end]-Time[0])/96`,MATLAB 1-based 入桶为 `idx=min(96,floor((t-t_start)/bucket_width)+1)`,末桶右闭。

### 15.4 BridgeRunStateReceipt 与错误响应

| 字段 | 类型 | 语义 |
|---|---|---|
| `protocol_version` | `Literal["0.3-b4"]` | 回显协议 |
| `status` | `Literal["persisted"]` | 快照已被 durable 写入或幂等确认已存在 |
| `mode` | `Literal["durable_persisted"]` | 持久化 run-state 写入 |
| `durable` | `Literal[true]` | 已保存 |
| `request_id` / `run_id` / `run_sequence` | echo | 只回显关联 id 与序号 |

200 表示本次请求已通过校验并完成 durable 持久化或幂等确认;`durable=true` 代表快照已保存。回执、错误响应和日志不得回显 run-state 内容、原始序列、路径、源码、token、claim 或客户端/服务端指纹。

auth 错误响应使用独立 `BridgeRunStateAuthErrorResponse`:

| 状态码 | `error` | header | 语义 |
|---|---|---|---|
| 401 | `bridge_auth_invalid_token` | `WWW-Authenticate: Bearer` | 缺失、格式错、签名错、过期、`nbf` 未到、撤销、issuer/audience 错 |
| 403 | `bridge_auth_forbidden` | 无 | token 有效但 capability 不足,body/session scope 不符,或权威 session 归属不符 |
| 503 | `bridge_auth_unavailable` | 无 | 撤销/verifier 基础设施不可用,fail-closed |

写入错误响应使用独立 `BridgeRunStateWriteErrorResponse`,不扩展 diagnostic/auth Literal:

| 状态码 | `error` | 语义 |
|---|---|---|
| 409 | `bridge_run_state_conflict` | 同一 `run_id` 不同规范化快照、同 sequence 不同 run,或 request_id 误复用 |
| 410 | `bridge_run_state_session_unavailable` | session 缺失、ended/gone、project 逻辑过期、旧 process generation 或已删 |
| 503 | `bridge_run_state_store_unavailable` | 存储不可用或 durable 写失败,fail-closed |
| 500 | `bridge_run_state_internal_error` | 反序列化/持久化不变量损坏 |

OpenAPI 只在 `/run-state` operation 挂 `BridgeRunStateBearerAuth` security scheme,并声明 401/403/409/410/413/415/422/500/503;`/diagnostic` 与 `/explanation` 不挂该 security scheme。
