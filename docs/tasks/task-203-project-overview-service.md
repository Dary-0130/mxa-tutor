# TASK-203: ProjectOverviewService(项目导览生成,基于 ProjectGraph)

## 状态

🔍 R2 conditional pass(20260604),v0.3 进 Codex 待最终核查

---

## 二审反馈摘要 + 处理(R2,20260604)

R2 给出 4 必改 + 4 可选(其中 2 接受 / 2 拒绝)。架构师采纳 6/8。

### R2 必改 4 条(全采纳)

| # | 问题 | v0.3 修订位置 |
|---:|---|---|
| 1 | 300 行命令 `wc -l` 多文件输出 `total` 行误报 | § 8 验收 2:加 `xargs -r -n1 wc -l` 逐文件 |
| 2 | `key_blocks` 仅校 `block_name` 漏重复 block 名 | § 7.3 `BlockEntry.location` 格式定型;§ 7.5 校验 Step 4 升级为四元组 `(model_path, name, type, parent)` + `parse_location` 辅助;§ 7.8 加重复 block 名测试 |
| 3 | `evidence.block_id` / `line_range` 静态校验缺失 | § 7.5 加 Step 5(block_id 存在性 + line_range 合法性);§ 7.8 加测试 |
| 4 | `main_simulink_models.file_path` 应 ∈ `project.slx_models` 而非任意 project file | § 7.5 Step 3 拆分(通用 file_path + simulink 专属);§ 7.8 加三 case 测试(无 slx / 错填 .m / 正确 .slx) |

### R2 可选 4 条(2 接受 / 2 拒绝)

| # | 项 | 决定 | 修订位置 |
|---:|---|:---:|---|
| 5 | `key_files` min_length 从 3 放宽到 1 | ❌ 拒绝 | 05 § 2.A 明示 3-8,放宽 = 偏离 schema 真值源;若小工程 prompt 凑数,优化 prompt(留 TASK-305)而非松 schema |
| 6 | `ProjectTypeResolver` feature-private 化 | ❌ 拒绝 | R2 同意维持现状不阻断;返回纯字符串不形成反向类型依赖,与 `OverviewCache` 关键差异(详见 § 末 R2 衍生观察点) |
| 7 | cache 通过 `features/overview/__init__.py` re-export,消除"私有模块被外部 import" | ✅ 接受 | § 7.2 加 re-export 说明;§ 7.7 lifespan / conftest import 改为 `from features.overview import ...`;§ 修改清单加 `__init__.py` |
| 8 | `text_provider` 在 lifespan 单例装配,避免 cache hit 路径浪费 | ✅ 接受 | § 7.7 lifespan 加 `app.state.text_provider`;`get_text_provider` 改 `request.app.state.text_provider`(D16 新增) |

### 与 R1 累积的反馈台账(R1 12 + 6 + R2 4 + 2 = 24 条)

R1 闭环已二审确认:`key_blocks` 防幻觉方向 / `unresolved_symbols` 截断 / `OverviewCache` feature-private / `project_type Literal[7]` / 三类 FileEntry / `Protocol` 化 / ERROR_MAP 502 / DI 无 `# noqa` / 测试覆盖映射。R2 4 必改是"在 R1 方向上的粒度升级",非架构推翻。

---

## 上下文

### mxa-tutor 项目快速建立 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。**"不是从零学 MATLAB,而是把你手上的工程讲明白"**。学生上传 .zip 工程包(.m / .slx / .mat),后端做 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。

四层分层:`api/` 路由 / `features/` 业务 / `core/` 接口 + domain + prompt yaml / `adapters/` 实现。

当前 Week 2(13/32 Task 完成)。Week 1 8/8 ✅(`.mat` 文件**清单占位,MatMetadata dataclass 已建,未深度解析**);Week 2 2/7(TASK-201 + TASK-202 已合并 main)。

数据流(02 § 2):

```
[Parser]  SlxModel / MFile / MatMetadata / FileInfo / file_dependencies
   ↓  无 LLM,纯结构化(TASK-107)
[ProjectGraph]  nodes / edges / entry_points / execution_flow / unresolved_symbols
   ↓  调 LLM 基于 ProjectGraph 生成
[ProjectOverview / TeachingUnit / Chat]  教学化输出,带 SourceRef 证据
```

**架构核心原则**(01 § 4 / 02 § 2):**不让 LLM 猜工程,让解析器还原工程,再让 LLM 讲工程**。

### 本 Task 在数据流的位置

项目**首个 LLM 输出**端点。`GET /projects/{project_id}/overview`:ProjectStore → ProjectGraphBuilder → prompt → DeepSeek `chat(json_mode=True)` → 解析 + Pydantic + citation 静态校验 → `ProjectOverview` JSON。下游 5 个 Task 阻塞:TASK-205 / 206 / 207 / 307 / 402。

### 审批级别:走 GPT 二审(反例 18 自检)

| 维度 | 评分 |
|---|---|
| 决策密度 | **高**:D1-D16 |
| 下游扩散面 | 5 个 Task |
| 用户可见性 | 首个 LLM 输出端点 |
| 异步 / LLM 首次定型 | 首次 LLM 异步桥接 + 12 字段 JSON schema 首次落 Pydantic |
| 隐私 / 安全 | LLM 输入含 ProjectGraph + block 名清单,落 DeepSeek 服务器 |

R1 通过,R2 conditional pass,v0.3 待最终核查。

### 范围边界(硬约束)

- **不修改**:`AppSettings`(配置零增量)/ `Project` dataclass / `ProjectType` enum / `ProjectStore` 接口 / TASK-201 已注册 8 handler / TASK-202 `CleanupWorker` 签名 / Week 1 + TASK-107 产物
- **临时前移**:ERROR_MAP 加 8 handler,TASK-206 接管(D3)
- **唯一新增异常**:`OverviewGenerationError(MxaError)`(D11)
- **跳过 TeachingUnit 中间层**:签名预留 `teaching_units` 参数(D6)
- **`OverviewCache` feature-private**:R1 R-5 + PM 拍板方案 A
- **`text_provider` lifespan 单例**:R2 R-8 + 新增 D16

---

## 输入(前置依赖)

### 必须已完成 Task

✅ TASK-001 / 002 / 101 / 106(commit `b1eb647`)/ 107(commit `e7d2e22`)/ 108 / 201(commit `fa7a4b0`)/ 202(commit `431a2bf`)/ chore PR(commit `7137af6`,决策 11)。

### 上游关键契约(给 GPT 二审 stand-alone 看,Codex 通过 `view` 实地核查)

**`Project` dataclass(`core/domain/project.py`,9 字段冻结)**

```python
@dataclass
class Project:
    id: str
    name: str
    project_type: ProjectType                  # 本 Task 全部 GENERAL(D4)
    files: list[FileInfo]
    slx_models: list[SlxModel]
    m_files: list[MFile]
    mat_files: list[MatMetadata]               # 本 Task 仍为 []
    created_at: datetime
    file_dependencies: dict[str, list[str]]
```

**`ProjectType` enum(TASK-101 锁,7 个值)**

```python
class ProjectType(Enum):
    CONTROL_SYSTEM = "control_system"
    SIGNAL_PROCESSING = "signal_processing"
    POWER_ELECTRONICS = "power_electronics"
    COMMUNICATION = "communication"
    MOTOR_CONTROL = "motor_control"
    NEW_ENERGY = "new_energy"
    GENERAL = "general"
```

本 Task `Project.project_type` 全部填 `GENERAL`(TASK-202 D7);LLM 输出的 `project_type` 通过 Pydantic `Literal[7 个 value]` 严格约束(R1 R-6)。

**`SlxModel.blocks` 元素结构(`core/domain/slx_model.py`,TASK-102 锁)**

```python
@dataclass
class SlxBlock:
    block_id: str
    name: str
    block_type: str
    parameters: dict[str, str]                  # 本 Task 不消费
    position: tuple[int, int, int, int]         # 本 Task 不消费
    parent_subsystem: str | None
    is_masked: bool = False                     # 本 Task 不消费
    is_library_link: bool = False               # 本 Task 不消费
    is_model_reference: bool = False            # 本 Task 不消费
```

本 Task prompt 列出每 slx 前 50 个 block 的 `name / block_type / block_id / parent_subsystem`(R1 R-1);service 校验 **四元组** `(model_path, name, type, parent)` ∈ project block 集(R2 R-2 升级)。

**`ProjectGraph` dataclass(`core/domain/project_graph.py`)**

```python
@dataclass
class ProjectGraph:
    project_id: str
    nodes: list[ProjectNode]
    edges: list[ProjectEdge]
    entry_points: list[str]
    execution_flow: list[str]
    data_flow: list[str]
    control_flow: list[str]
    unresolved_symbols: list[str]               # "category:name" 格式
```

`unresolved_symbols` 4 类:`unresolved:foo` / `ambiguous:foo` / `circular:A<->B` / `partial_parse:bar.slx`。本 Task prompt 截断到前 50 项(R1 R-2)。

**`TextProvider.chat` 接口(`core/interfaces/llm_provider.py`,同步)**

```python
def chat(
    messages: list[LLMMessage],
    json_mode: bool = False,
    timeout: float = 30.0,
    max_tokens: int | None = None,
) -> LLMResponse
```

异常 5 类:`LLMAuthError` / `LLMQuotaError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError`,均 `LLMError` 子类。

**`ProjectStore.get_project`(async,TASK-202 锁)**

```python
async def get_project(self, project_id: str) -> Project:
    """取已 ready 的 Project。未 ready / 未存在抛 ProjectNotFoundError。"""
```

**`ProjectGraphBuilder.build`(同步,TASK-107)**

```python
ProjectGraphBuilder().build(project: Project) -> ProjectGraph
```

通过 `features.overview` package re-export;本 Task 同 package 用完整路径 `from features.overview.project_graph_builder import ProjectGraphBuilder`。

**ERROR_MAP 现状(TASK-201 锁 8 handler)**

```
Leaf: ZipBomb→400 / ZipSlip→400 / FileTypeNotAllowed→400 / ProjectNotFound→404 / ProjectTooLarge→413
Base fallback: UploadError→400 / ProjectError→400
Final: MxaError→500
```

响应 shape `{"error", "message"}` 本 Task 不改。

**lifespan + dependencies 现状(TASK-202 锁)**

- `app.state.project_store = InMemoryProjectStore()`(本 Task 加 `overview_cache` + `text_provider`,R2 R-8)
- `get_settings()` / `get_project_store()` / `get_upload_service()` 三个 dependency(本 Task 末尾追加 4 个)

---

## 输出(交付物)

### 新增文件清单(15 个)

| 路径 | 行数 | 用途 |
|---|---|---|
| `core/prompts/project_overview.yaml` | ~130 | prompt 模板 v0.1,含 block_summaries / unresolved 占位 |
| `core/interfaces/project_type_resolver.py` | ~30 | `ProjectTypeResolver` ABC(D4) |
| `adapters/classifier/__init__.py` | ~3 | 空包 |
| `adapters/classifier/general_project_type_resolver.py` | ~30 | v0.1 占位 |
| `features/overview/_overview_cache.py` | ~100 | `OverviewCache` ABC + `InMemoryOverviewCache`,feature-private |
| `features/overview/_prompt_loader.py` | ~70 | yaml 加载器 |
| `features/overview/overview_schemas.py` | ~190 | Pydantic 12 字段 + 三类 FileEntry + Literal + **`BlockEntry.location` 格式约束**(R2 R-2) |
| `features/overview/_prompt_builder.py` | ~130 | `build_messages` + block_summaries + unresolved 截断 |
| `features/overview/overview_service.py` | ~280 | `ProjectOverviewService`,to_thread + **校验五步**(R2 R-2/R-3/R-4) + `parse_location` 辅助 |
| `api/routes/overview.py` | ~50 | GET /projects/{project_id}/overview |
| `tests/features/overview/test_overview_cache.py` | ~130 | |
| `tests/features/overview/test_prompt_loader.py` | ~60 | |
| `tests/features/overview/test_overview_schemas.py` | ~200 | 三类 FileEntry + Literal + **`BlockEntry.location` 格式**(R2 R-2) |
| `tests/features/overview/test_overview_service.py` | ~290 | **+ 4 个 R2 测试**:重复 block 名 / block_id 不存在 / line_range 非法 / main_simulink_models 三 case |
| `tests/api/test_overview.py` | ~180 | API 端到端 |

总新增 ~1880 行(含测试)。所有文件 ≤ 300 行(04 § 4)。

### 修改文件清单(8 个,R2 R-7 加 `__init__.py`)

| 路径 | 修改性质 |
|---|---|
| `core/domain/exceptions.py` | +1 leaf `OverviewGenerationError(MxaError)` |
| `features/overview/__init__.py` | **R2 R-7**:加 `from ._overview_cache import OverviewCache, InMemoryOverviewCache` re-export |
| `api/main.py` | lifespan 加 `overview_cache` + **`text_provider`**(R2 R-8)装配 + 注册 router |
| `api/dependencies.py` | 追加 4 dependency(**无 `# noqa`**);**`get_text_provider` 改 `request.app.state.text_provider`**(R2 R-8) |
| `api/middleware/error_handler.py` | 末尾追加 8 handler |
| `requirements.txt` | +`pyyaml==6.0.2` |
| `tests/api/conftest.py` | autouse fixture 加 `overview_cache` + `text_provider` 清理(import 改 `from features.overview import InMemoryOverviewCache`,R2 R-7) |
| `docs/03_TASK_INDEX.md` | TASK-203 行 🔲→🔍 + 任务名"基于 TeachingUnit"→"基于 ProjectGraph,TeachingUnit 接口预留" + 进度条 |

### 新增依赖

`pyyaml==6.0.2`(D7)

---

## 范围(必须做)

1. 从 main HEAD `7137af6` 切分支 `task/TASK-203-project-overview-service`
2. 实地核查上游契约(`cat` 关键文件,与 § 2 内联对照),任一不符停手抛冲突(纪律 1)
3. 按 § 5 实施步骤实施全部新增 / 修改文件
4. `make check` + `python -m ruff format --check .` + `pip check` 全过
5. **决策 11 grep 验收**:
   - `grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ --include='*.py' --exclude-dir=.venv --exclude-dir=.git` 空
   - `grep -rn 'asyncio.to_thread' features/overview/overview_service.py` 命中 2 处
6. **R1 R-5 / R2 R-7 cache 验收**:`grep -rn 'from adapters.storage' features/overview/` 空 + `grep -rn 'overview_cache' adapters/` 空 + `grep -rn 'from features.overview._overview_cache' api/ tests/api/` 空(改从 package re-export)
7. **真启动验收**:uvicorn 单 worker + curl 全过(需 PM 配 `.env` `DEEPSEEK_API_KEY`)
8. 改 03 索引(字节级 Python,LF/CRLF 双试)
9. 完工三件套(决策 08)+ 提 PR(Codex 给 PM 标题 + 正文,PM 走 GitHub 网页创建)

---

## 不做(明确排除)

- ❌ 完整 CitationEnforcer(本 Task 仅 Pydantic + file_path + block 四元组 + block_id + line_range 静态校验;运行时降级 / 跨工程引用归 TASK-307)
- ❌ TeachingUnit 构建(签名预留)
- ❌ `project_type` 启发式分类(全 GENERAL,LLM 在 Literal[7] 选)
- ❌ 新增 LLMError / ParseError / ProjectError 子类(只 1 个 `OverviewGenerationError`)
- ❌ 新增 AppSettings 字段
- ❌ 改 ProjectStore / Project / ProjectType / CleanupWorker / TASK-201 8 handler / TASK-202 lifespan **既有装配**(本 Task 仅追加新装配)
- ❌ 抽 `OverviewCache` 到 `core/interfaces/`(R1 R-5)
- ❌ `features/overview/` 内 import `adapters/`(严格分层)
- ❌ route 内 `try/except` 业务异常
- ❌ service / cache 内 `logger.exception`(决策 11)
- ❌ service 内直接 `await` 同步 `provider.chat`(决策 11,必须 to_thread)
- ❌ 日志记录文件名片段 / prompt 原文 / response.text / `str(exc)`
- ❌ 多 worker / cache 显式 TTL / cache 与 CleanupWorker 联动(D15)
- ❌ 流式 LLM / prompt A/B 测试(Phase 2)
- ❌ **`key_files` 放宽到 1**(R2 R-5 拒绝,坚守 05 § 2.A 3-8)

---

## 实施步骤(5 阶段)

**阶段 1 — 基础设施**(1 commit):pyyaml + `OverviewGenerationError` + prompt yaml 建。

**阶段 2 — Cache + Resolver**(1-2 commit):建 `_overview_cache.py`(合并 ABC + InMemory)+ **`features/overview/__init__.py` re-export**(R2 R-7)+ `project_type_resolver.py` + `adapters/classifier/` + 单测。

**阶段 3 — Service 核心**(2-3 commit):依次建 `_prompt_loader.py` / `overview_schemas.py`(含 `BlockEntry.location` 格式约束)/ `_prompt_builder.py` / `overview_service.py`(校验五步 + parse_location),每个建后跑单测。

**阶段 4 — API 端到端装配**(2-3 commit):`api/routes/overview.py` + `api/dependencies.py` 追加 4 dep(text_provider 从 app.state 取)+ `api/main.py` lifespan 加 `overview_cache` + `text_provider` 装配 + `error_handler.py` 8 handler + `conftest.py` autouse + `tests/api/test_overview.py`。

**阶段 5 — 收尾**(1 commit):03 索引字节级修订 + 三件套 + 提 PR。

**Commit 拆分原则**:Conventional Commits;subject **单行无 body**(反例 17);按文件改动自然拆分。

---

## 接口契约

### 7.1 prompt 模板(`core/prompts/project_overview.yaml`)

字段约定:`version: "v0.1"` / `description` / `system` / `user`。`user` 段含 `{file_list}` / `{entry_points}` / `{execution_flow}` / `{unresolved_count}` / `{unresolved_symbols}`(截断 50)/ `{slx_summaries}` / `{block_summaries}`(每 slx 前 50 个 block 的 `name/type/id/parent`)/ `{m_function_summaries}` 占位。

**system 必须明示**(关键 invariant):
1. 12 字段 JSON schema 字段约定(对齐 § 7.3)
2. `project_type` 只能从 7 个 value 选一个
3. 三类 FileEntry 各自必含 `role` / `summary` / `why_key`
4. `file_path` 引用 ∈「文件清单」+ `block_name` 引用 ∈「Simulink Block 清单」
5. **`main_simulink_models.file_path` 必须是 .slx 文件**(R2 R-4 收紧,实现层 service 双校 + prompt 内提示)
6. **`BlockEntry.location` 必须填 `{file_path} / {parent_subsystem 或 <root>}` 格式**(R2 R-2)
7. 引用 unresolved 必须在 `likely_confusing_points` 明示"未能确定 X"(05 § 6 E 类)
8. 教学口吻(05 § 8)

版本号(05 § 9.2):本 Task 起 v0.1;后续 prompt 修改必须升版本 + 跑评测 + PR review。

### 7.2 `features/overview/_overview_cache.py`(feature-private)

接口:

```python
class OverviewCache(ABC):
    async def get(self, project_id: str) -> ProjectOverview | None
    async def put(self, project_id: str, overview: ProjectOverview) -> None
    async def invalidate(self, project_id: str) -> None
```

`InMemoryOverviewCache` 实现要点:单 `dict + asyncio.Lock`;`get` 不持锁(GIL 保证原子);`put` / `invalidate` 持锁;不维护独立 TTL(D15)。**硬约束**单 worker(TASK-202 D5)。

**R2 R-7 re-export**:`features/overview/__init__.py` 加 `from ._overview_cache import OverviewCache, InMemoryOverviewCache`,消除"私有模块被外部 import"代码味;包外 import 用 `from features.overview import InMemoryOverviewCache`,包内仍可用完整路径。

### 7.3 `features/overview/overview_schemas.py` — Pydantic 12 字段

`ProjectOverview` 字段表(对齐 docs/05 § 2.A):

| 字段 | 类型 | 约束 |
|---|---|---|
| `project_title` | `str` | 1-30 字 |
| `project_type` | `Literal[7]` | 7 value 之一(R1 R-6) |
| `one_sentence_summary` | `str` | 1-80 字 |
| `main_entry_files` | `list[EntryFileEntry]` | 1-3 个,含 `role` |
| `main_simulink_models` | `list[SimulinkModelEntry]` | 0-5 个(可空),含 `summary`,**service 校 file_path ∈ .slx 模型集**(R2 R-4) |
| `main_execution_flow` | `list[str]` | 3-7 个 |
| `key_files` | `list[KeyFileEntry]` | 3-8 个,含 `why_key` |
| `key_blocks` | `list[BlockEntry]` | 0-10 个(可空),**service 校四元组**(R2 R-2) |
| `knowledge_points` | `list[str]` | 3-6 个 |
| `beginner_reading_order` | `list[str]` | 3-6 个 |
| `likely_confusing_points` | `list[str]` | 2-5 个 |
| `evidence` | `list[SourceRefEntry]` | ≥ 3 个(05 § 7.1);**service 校 block_id 存在性 + line_range 合法**(R2 R-3) |

三类 FileEntry 拆分(R1 R-7):

- `EntryFileEntry` = `{file_path, role}` (role ≤ 100 字)
- `SimulinkModelEntry` = `{file_path, summary}` (summary ≤ 200 字)
- `KeyFileEntry` = `{file_path, why_key}` (why_key ≤ 200 字)

`BlockEntry` = `{block_name, block_type, location, why_key}`,**`location` 必须是 `"{model_path} / {parent_or_<root>}"` 格式**(R2 R-2,service 用 `parse_location` 解析后校四元组;Pydantic 层不强制 regex 以保留 LLM 偶发空白 / 大小写 / 多余空格的容错,而是在 service 层强校)。

`SourceRefEntry` = `{file_path, line_range?, block_id?}`;**`line_range = tuple[int, int]`**,service 校 `1 ≤ start ≤ end`(R2 R-3);**`block_id`** 若非 None 由 service 校 ∈ project block_id 集(R2 R-3)。

所有模型 `extra="forbid"`。

### 7.4 `features/overview/_prompt_builder.py` — `build_messages` 接口

```python
def build_messages(
    project: Project,
    graph: ProjectGraph,
    project_type_hint: str,
    teaching_units: list[TeachingUnit] | None = None,  # D6 预留,v0.1 不消费
) -> list[LLMMessage]
```

关键 invariant:
- 纯函数(无 self / 无 IO)
- 模块级常量 `MAX_UNRESOLVED_SYMBOLS_IN_PROMPT: Final[int] = 50` + `MAX_BLOCKS_PER_MODEL_IN_PROMPT: Final[int] = 50`
- unresolved 超 50 加"还有 N 项未列出"
- 每 slx 超 50 个 block 加"还有 N 个 block 未列出"
- 删 `from collections.abc import Iterable` 未用 import(R1 R-8)

### 7.5 `features/overview/overview_service.py` — `ProjectOverviewService`

构造签名:

```python
def __init__(
    self,
    store: ProjectStore,
    cache: OverviewCache,
    project_type_resolver: ProjectTypeResolver,
    text_provider: TextProvider,
    graph_builder_factory: Callable[[], ProjectGraphBuilderLike] | None = None,
    timeout: float = DEFAULT_OVERVIEW_TIMEOUT_SECONDS,   # 60.0(D9)
    max_tokens: int = DEFAULT_OVERVIEW_MAX_TOKENS,        # 4000(D9)
) -> None
```

`ProjectGraphBuilderLike` 是 `Protocol` 含单方法 `build(project) -> ProjectGraph`,默认 `ProjectGraphBuilder`(R1 R-9)。

主入口 `async def get_or_generate(project_id) -> ProjectOverview` 行为:

1. `project = await store.get_project(project_id)` 兜底 404 + cache liveness(D12)
2. `cached = await cache.get(project_id)`;hit 直返
3. `graph = await asyncio.to_thread(self._build_graph_sync, project)`(决策 11 决策 1)
4. `messages = build_messages(project, graph, resolver.resolve(project))`
5. `response = await asyncio.to_thread(text_provider.chat, messages, json_mode=True, ...)`
6. `_parse_and_validate(response, project)` **校验五步**(下)
7. `await cache.put(project_id, overview)` + return

**校验五步**(`_parse_and_validate`,R2 R-2/R-3/R-4 收紧):

| Step | 校验 | 失败处理 |
|---|---|---|
| 1 | `json.loads` | `OverviewGenerationError` |
| 2 | `ProjectOverview.model_validate`(12 字段 + Literal + 三类 FileEntry 必填 + extra=forbid) | `OverviewGenerationError` |
| 3a | **通用 file_path** ∈ `{fi.relative_path for fi in project.files}`,校 evidence + 三类 FileEntry 共 4 处 | `OverviewGenerationError` |
| 3b | **simulink 专属**:`main_simulink_models.file_path` ∈ `{m.file_path for m in project.slx_models}`(R2 R-4) | `OverviewGenerationError` |
| 4 | **`key_blocks` 四元组**:`(model_path, block_name, block_type, parent)` ∈ `{(m.file_path, b.name, b.block_type, b.parent_subsystem or "<root>") for m in project.slx_models for b in m.blocks}`(R2 R-2,`parse_location` 辅助方法解析 `BlockEntry.location`) | `OverviewGenerationError` |
| 5 | **`evidence` 深度**:`block_id` 非 None → ∈ `{b.block_id for m in project.slx_models for b in m.blocks}`;`line_range = (start, end)` 非 None → `1 ≤ start ≤ end`(R2 R-3) | `OverviewGenerationError` |

`parse_location` 辅助方法(私有同步):入参 `BlockEntry.location` 字符串,split on ` / `(两侧 trim),返回 `(model_path, parent)` tuple;格式不合(无 ` / ` / 多于 1 个 / 空段)抛 `OverviewGenerationError`(归到 Step 4 失败,文案"AI 输出 block location 格式错误,请刷新重试")。

异常分支统一 `logger.error(..., type(exc).__name__)` metadata-only + `from None` 抹 chain(决策 11 决策 2);**禁** `logger.exception` / `str(exc)` / `response.text`。LLMError 直接向上抛(MxaError 子类,ERROR_MAP 翻译);JSON / Pydantic / file_path / block 四元组 / block_id / line_range 失败均翻译为 `OverviewGenerationError`。

### 7.6 ERROR_MAP 临时前移 8 handler(`api/middleware/error_handler.py`)

| 异常 | HTTP | machine code | 文案 |
|---|---:|---|---|
| `LLMAuthError` | 503 | `llm_auth` | 服务暂时不可用,请稍后重试 |
| `LLMQuotaError` | 503 | `llm_quota` | 服务繁忙,请稍后 |
| `LLMRateLimitError` | 429 | `llm_rate_limit` | 请求太频繁,稍等一下 |
| `LLMTimeoutError` | 504 | `llm_timeout` | 网络较慢,正在重试... |
| `LLMServerError` | 502 | `llm_server` | AI 服务暂不稳定,请刷新重试 |
| `SlxParseError` | 400 | `slx_parse` | Simulink 模型解析失败,可能版本过老或损坏 |
| `MParseError` | 400 | `m_parse` | .m 文件解析失败,请检查文件编码 |
| `OverviewGenerationError` | **502** | `overview_generation` | 导览生成失败,请刷新重试 |

响应 shape `{"error", "message"}` 不变。TASK-206 接管保留这 8 个 + 追加(D3)。

### 7.7 DI + lifespan 装配(R2 R-7 + R-8 修订)

**`api/main.py::lifespan`** 在 `app.state.project_store = ...` 后加:

```python
overview_cache = InMemoryOverviewCache()        # from features.overview (R2 R-7 re-export)
app.state.overview_cache = overview_cache

text_provider = DeepSeekTextProvider(           # R2 R-8 lifespan 单例,避免 cache hit 路径浪费
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)
app.state.text_provider = text_provider
```

`create_app()` 内注册 `overview_router`。

**`api/dependencies.py`** 顶部追加 import + 末尾追加 4 dependency:

- `get_text_provider(request: Request) -> TextProvider`:**`return request.app.state.text_provider`**(R2 R-8,不再每次构造)
- `get_overview_cache(request: Request) -> OverviewCache`:`return request.app.state.overview_cache`
- `get_project_type_resolver() -> ProjectTypeResolver`:`return GeneralProjectTypeResolver()`(D4)
- `get_overview_service(...)`:`ProjectOverviewService(store, cache, resolver, text_provider)` 装配

**无 `# noqa`**(R1 R-3);`InMemoryOverviewCache` import 不出现在本文件(只在 lifespan)。

**`tests/api/conftest.py`** autouse fixture 加 `app.state.overview_cache = InMemoryOverviewCache()` + `app.state.text_provider = <fake>` 重置;import 改 `from features.overview import InMemoryOverviewCache`(R2 R-7)。

### 7.8 测试覆盖边界(不写完整用例名清单)

5 个测试模块覆盖以下边界:

- **`test_overview_cache.py`**:get / put / invalidate 三方法 + 并发 + 不同 project_id 不冲突 + get 不持锁
- **`test_prompt_loader.py`**:加载 / lru_cache 命中不读盘 / 路径 `/` `\\` `..` 抛错 / frozen dataclass 不可改
- **`test_overview_schemas.py`**:12 字段必填 / 三类 FileEntry 各自必填 / `Literal[7]` 严格 / 长度边界 / extra=forbid / `BlockEntry.location` Pydantic 层接受任意非空字符串(R2 R-2 格式校验在 service 层而非 Pydantic 层)
- **`test_overview_service.py`** — 含以下 R2 必加边界:
  - cache hit / miss / 5 个 LLMError 透传 / JSON 解析失败 / Pydantic 失败
  - file_path 通用校验失败(evidence + 三类 FileEntry 共 4 处)
  - **重复 block 名 case**(R2 R-2):工程含 `model_a.slx::SpeedLoop::Gain` + `model_b.slx::CurrentLoop::Gain`,LLM 输出 `location="model_b.slx / SpeedLoop"` → 失败
  - **`BlockEntry.location` 格式非法**(R2 R-2):缺 ` / ` / 多 ` / ` / 空段 → 失败
  - **`evidence.block_id` 不存在**(R2 R-3) / **`line_range` 非法**(start < 1 / end < start) → 失败
  - **`main_simulink_models` 三 case**(R2 R-4):无 slx 工程接受空列表 / `.m` 错填 → 失败 / 真实 `.slx` → 通过
  - **unresolved 截断到 50**(R1 R-2)+ `asyncio.to_thread` 两次调用断言 + logger 不用 exception
- **`test_overview.py`**(API 端到端):200 happy / 404 / 503 / 504 / 429 / 502 / 响应 shape 锁 / cache hit 2 次同结果

LLM 全 mock;整套测试 < 30 秒(04 § 5)。

---

## 验收标准(精简核心)

1. `make check` 全过 + `python -m ruff format --check .` + `pip check`
2. **R2 R-1 修订**:文件大小逐文件 wc,避免 `total` 误报:
   ```bash
   git diff --name-only main...HEAD -- '*.py' \
     | xargs -r -n1 wc -l \
     | awk '$1 > 300 {print; bad=1} END {exit bad}'
   ```
3. **决策 11**:`grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ --include='*.py' --exclude-dir=.venv --exclude-dir=.git` 空 + `grep -rn 'asyncio.to_thread' features/overview/overview_service.py` 命中 2 处
4. **隐私硬约束**:`grep -rn 'str(exc)\|repr(exc)\|{exc}' core/ adapters/ features/ api/ app/ --include='*.py' --exclude-dir=.venv --exclude-dir=.git` 空
5. **route 不 try/except 业务异常**:`grep -rnE 'except .*?(Mxa|LLM|Parse|Project|Upload|Zip|FileType|OverviewGeneration)' api/routes/ --include='*.py'` 空
6. **R1 R-5 / R2 R-7 cache 验收**:
   - `grep -rn 'from adapters.storage' features/overview/` 空
   - `grep -rn 'overview_cache' adapters/` 空
   - `grep -rn 'from features.overview._overview_cache' api/ tests/api/` 空(外部 import 改走 package re-export)
7. **真启动**:uvicorn 单 worker → curl POST /upload + poll status → curl GET /overview 200 含 12 字段 / 第二次 < 200ms cache hit / 不存在 project 404 / 模拟 bad API key 503
8. **日志**:`logs/app_*.log` 含 `Overview LLM call: ... prompt_version=v0.1` + `Overview cache hit: ...`;不含 traceback / 文件名片段 / prompt 原文
9. **03 索引**:字节级 Python 改 TASK-203 状态 🔲→🔍 + 任务名 + 进度条;LF/CRLF 双试

---

## 风险与注意点

### 风险 1:LLM 输出非 JSON / schema 不合

DeepSeek 可能返回 markdown 包裹的 JSON / 字段缺失 / extra 字段。规避:prompt 明示"纯 JSON" + `json_mode=True` + Pydantic `extra="forbid"` + `Literal[7]` + 三类 FileEntry 强制必填;失败 → `OverviewGenerationError` → 502。

### 风险 2:LLM 编造 file_path / block / evidence(R2 R-2/R-3/R-4 闭环)

LLM 看不到 ProjectGraph 全部细节,可能根据 file_list 自由发挥编造。规避(五层防御,service `_parse_and_validate`):

- file_path ∈ 文件清单(三类 FileEntry + evidence)
- `main_simulink_models.file_path` ∈ .slx 模型集(R2 R-4)
- `key_blocks` 四元组 `(model_path, name, type, parent)` ∈ project block 集(R2 R-2,防重复名)
- `evidence.block_id` ∈ project block_id 集(R2 R-3)
- `evidence.line_range` 合法 `1 ≤ start ≤ end`(R2 R-3)

任一不过 → `OverviewGenerationError` → 502。

### 风险 3:LLM 调用超时

工程超大,timeout=60s 可能不够。规避:timeout 走构造参数;`LLMTimeoutError` → 504;TASK-106 已 3 次重试 + 指数退避;Phase 2 streaming。

### 风险 4:event loop 阻塞(决策 11 决策 1,前任 TASK-202 P0-2)

`async def get_or_generate` 内直接同步调 `provider.chat` 阻塞 event loop。规避:用 `await asyncio.to_thread(...)` 桥接;§ 验收 grep 锁 2 处;测试 mock 断言。

### 风险 5:`logger.exception` 误用(决策 11 决策 2,前任 TASK-202 P0-3)

可能含文件名 / prompt 片段。规避:service 五步 `except` 全部 `logger.error(..., type(exc).__name__) + from None`;grep 兜底。

### 风险 6:Pydantic ValidationError 落响应体

漏在 service 层捕获 → FastAPI 默认 422 + `errors()` 字段清单,可能含 LLM response.text。规避:service `_parse_and_validate` Step 2 显式 `except ValidationError`;测试锁定。

### 风险 7:prompt 占位符与 `.format` kwargs 漂移

`build_messages` 调 `template.user.format(...)` 占位符 / kwargs 漂移抛 KeyError。规避:`grep -o '{[a-z_]*}' core/prompts/project_overview.yaml` 列占位符,与 `_prompt_builder.py` kwargs 字面对照;不一致停手。

### 风险 8:单 worker 限制(TASK-202 D5)

多 worker 启动 → cache 不跨进程。规避:真启动验收命令显式 `--port 8000`(默认 1);TASK-204 SQLite 跨进程一致。

### 风险 9:Overview JSON 超 4000 max_tokens

工程极大时 LLM output truncated。规避:prompt 字段长度约束 + 真启动评测统计 truncation 率;Phase 2 streaming。

### 风险 10:cache stale 与 cleanup 不同步(D15)

CleanupWorker 删过期 project 但 `overview_cache` 仍持 stale。规避:D12 store.get_project 兜底;接受 stale 浪费(MCS 几 MB 上限);`invalidate` 接口预留 Phase 2。

### 风险 11(隐私):prompt 含文件路径落 DeepSeek 服务器

学生上传文件路径可能含敏感命名。规避:01 § 9 用户协议明示;**PM 在 MCS 上线前确认 DeepSeek opt-out 训练**(架构师追踪事项)。

### 风险 12(R2 新增):`BlockEntry.location` 格式 LLM 偶发偏差

LLM 可能填 `"model.slx/SpeedLoop"`(缺空格)或 `"model.slx → SpeedLoop"`(错分隔符)。规避:prompt system 明示 `{model_path} / {parent_or_<root>}` 格式带空格;`parse_location` 对两侧 `strip()` 容错单边空格,但严格要求 ` / ` 分隔符;不合 → `OverviewGenerationError`;评测时统计格式失败率,> 10% 触发 prompt 强化(留 TASK-305)。

---

## 决策日志(D1-D16,二审核心)

每个 D 含 **理由** + **替代方案 / 反对意见** + **为何不选**(R1 反馈采纳)。D1-D15 维持 v0.2,**新增 D16(R2 R-8)**。

### D1 — 审批级别:走 GPT 二审

**理由**:LLM 异步首次定型 + 12 字段 JSON schema 首次 + 5 下游 Task 抄此模式;反例 18 自检 5 维度全高。

**替代方案**:Codex 一审通过即合并(类比 task-108)。**为何不选**:task-108 是单点决策,本 Task 决策密度 + 下游扩散面远超(反例 18 同源教训)。

### D2 — CitationEnforcer 归属:本 Task 仅静态校验,完整归 TASK-307

**理由**:本 Task 已做五层静态防御(file_path 双套 + block 四元组 + block_id + line_range,R2 R-2/R-3/R-4 升级);运行时降级配套 RAG 数据流。

**替代方案**:本 Task 直接做 EvidenceMissingError 降级 + 跨工程引用幻觉。**为何不选**:运行时降级需 RAG 召回(本 Task 无 RAG);提前实施 = 写废代码,TASK-307 RAG 落地必然重写。

### D3 — LLM ERROR_MAP 临时前移 8 handler 到本 Task

**理由**:TASK-206 在本 Task 之后但本 Task LLM 重度;不前移 → LLM 失败全 500,违反 02 § 9。

**替代方案**:等 TASK-206。**为何不选**:本 Task 真启动验收必须有中文 + HTTP code 就位;前移代价仅 ~50 行 handler;TASK-206 接管保留 8 个不返工。

### D4 — `project_type` 全 GENERAL + ProjectTypeResolver 接口 + Literal[7] schema

**理由**:TASK-202 D7 已锁 `Project.project_type = GENERAL`;LLM 输出由 `Literal[7]` 严格约束(R1 R-6);Resolver 接口预留,Phase 2 替换 `HeuristicProjectTypeResolver` 仅改 DI。

**替代方案**:
- A. 不抽 resolver,service hardcode `"general"`。**为何不选**:Phase 2 替换面更大。
- B. `project_type` 任意 str。**为何不选**:R1 R-6 — Pydantic 不拦"unknown_xxx",与 05 § 2.A enum 不对齐。

### D5 — `OverviewCache` feature-private(R1 R-5 + PM 拍板 + R2 R-7 re-export)

**理由**:cache 只服务本 Task LLM 路径;存 `ProjectOverview` feature schema;不抽 core 避反向类型依赖;R2 R-7 通过 `__init__.py` re-export 消除"私有模块外部 import"代码味。

**替代方案**:
- A. core/interfaces + adapters/storage(v0.1)。**为何不选**:core 反向 import feature schema → 单向分层契约破坏。
- B. 接口存 `dict[str, Any]` 避类型依赖。**为何不选**:service `.model_dump` / `.model_validate` 开销 + 类型 hint 失效。
- C. 文件改名 `overview_cache.py`(R2 R-7 替代方案)。**为何不选**:命名风格不同于 `_prompt_loader.py` / `_prompt_builder.py`;re-export 保持私有命名一致性。

### D6 — 跳过 TeachingUnit 中间层 + 接口预留 `teaching_units` 参数

**理由**:02 § 2 数据流是理想,MCS 可阶段性偏离;TeachingUnit 主要价值在 RAG(TASK-205);PM Q4 拍板"实用主义"。

**替代方案**:
- A. 严格按 02 § 2 先 TeachingUnitBuilder。**为何不选**:范围膨胀 ~500 行;PM Q4 拒绝。
- B. 不预留参数。**为何不选**:Phase 2 改 signature 触发调用方迁移;预留代价为零。

### D7 — `pyyaml==6.0.2` 依赖

**理由**:05 § 9.1 明示 yaml 格式;`safe_load` 防 RCE。

**替代方案**:TOML / Python module。**为何不选**:TOML 多行 syntax 弱;module 丢"version/description"结构化字段。

### D8 — 三态 `created_at` 语义分离

**理由**:`ProjectStatusRecord.created_at` / `Project.created_at` / `ProjectOverview.generated_at` 三态独立,但 v0.1 **不加** `generated_at` 字段(05 § 2.A 不含);Phase 2 视 UX 加。

**替代方案**:v0.1 加。**为何不选**:05 § 2.A 12 字段是真值源,扩字段必须升 schema 版本 + 评测。

### D9 — LLM `timeout=60s` / `max_tokens=4000` 模块级常量,不入 AppSettings

**理由**:配置零增量;LLM 参数不是运维配置;调整走代码 PR + 评测。

**替代方案**:加入 AppSettings 走 `.env`。**为何不选**:每加 1 个 LLM 参数 = AppSettings 膨胀;Final 常量 + 构造参数足够。

### D10 — Prompt 模板版本号 v0.1

**理由**:05 § 9.2 强制升版本 + 跑评测;`PromptTemplate.version` + service log `prompt_version`。

**替代方案**:无版本号,git hash 锁。**为何不选**:版本号是评测语义 anchor,git hash 是物理 anchor;05 § 9.2 已强制字段。

### D11 — 新增异常类 `OverviewGenerationError(MxaError)` — 严禁新增异常原则的唯一偏离

**理由**:LLM 输出 schema/citation 校验失败不属于 LLMError / ParseError / ProjectError / EvidenceMissingError;新加 1 leaf 代价 +1 行 + 1 handler。

**替代方案**:
- A. 借用 ParseError。**为何不选**:语义错位,Codex 后续混淆。
- B. 抽 `LLMOutputError` 中间层。**为何不选**:本 Task 仅 1 leaf 需求,overengineer;Phase 2 ChatGenerationError 出现再讨论。
- C. 直接抛 MxaError final fallback。**为何不选**:500 internal_error 模糊,前端无法显示"刷新重试"按钮(应 502)。

### D12 — service 路径 `store.get_project` 先于 `cache.get`

**理由**:store.get_project 兜底 404 + 自然实现 cache liveness;stale entry 永远不到客户端(被 404 拦截);代价仅 hit 时多 1 次 store 调用。

**替代方案**:cache.get-first(性能略优)。**为何不选**:stale entry 返回 200 + JSON,实际 project 不存在,调试痛。

### D13 — `unresolved_symbols` prompt 截断 + LLM 容错指令

**理由**:工程破碎 200+ unresolved 浪费 tokens;`MAX_UNRESOLVED_SYMBOLS_IN_PROMPT = 50`(R1 R-2);prompt 内告诉 LLM 引用 unresolved 必须在 `likely_confusing_points` 明示"未能确定 X"(05 § 6 E 类)。

**替代方案**:不截断。**为何不选**:R1 R-2 — 200+ 行 unresolved 主导 user prompt,LLM 输出质量降。

### D14 — Pydantic FileEntry 拆三类(R1 R-7)

**理由**:v0.1 合并设计 → R1 R-7 抓 → v0.2 拆;每类 file_path + 1 必填字段;20 行级别。

**替代方案**:
- A. v0.1 合并(三字段 Optional)。**为何不选**:R1 R-7 — 缺 role/summary/why_key 也能过校验。
- B. 单 FileEntry + `model_validator` root validator 按位置强制。**为何不选**:校验逻辑零散在 ProjectOverview 主类。

### D15 — Overview cache 与 CleanupWorker 不耦合(D15)

**理由**:TASK-202 锁的 `CleanupWorker.__init__` 不接 cache,扩参数 = 改 TASK-202 不在范围;MCS 内存浪费 < 1 MB 可接受;D12 兜底 stale 不到客户端。

**替代方案**:
- A. CleanupWorker 加 cache 参数。**为何不选**:破坏"不动 TASK-202 文件" invariant。
- B. cache 自带 TTL + 后台 worker。**为何不选**:新 worker = 范围膨胀。

### D16(新增,R2 R-8)— `text_provider` 在 lifespan 单例装配

**理由**:`DeepSeekTextProvider` 构造含 OpenAI client init(连接池 / 超时配置);每次请求构造 = cache hit 路径浪费 + LLM 调用路径无收益(client 内部本来就连接池复用);lifespan 单例放 `app.state.text_provider`,DI 改为从 state 取(对齐 `project_store` / `overview_cache` 模式)。

**替代方案**:
- A. 每次请求构造(v0.2 设计)。**为何不选**:R2 R-8 — cache hit 路径浪费,即使 client 轻量也是无用功;一致性 vs `project_store` lifespan 模式差。
- B. `@lru_cache(maxsize=1)` on `get_text_provider`(类似 `get_settings`)。**为何不选**:lru_cache 与 Request 上下文耦合不直观;lifespan + app.state 更清晰,且单测可 override `app.state.text_provider`。
- C. 接受性能损失不改。**为何不选**:R2 明确给改进路径,代价仅 ~5 行(lifespan 加 1 装配 + DI 改 1 行);改了对齐项目模式。

---

## Checklist(精简)

**实施前**:已读 5 核心文档 + 决策 06/09/11 + 反例 1-19;实地核查上游 6 接口 + ProjectType enum + SlxBlock 字段;理解决策 11 双不变量;理解 cache feature-private + project_type Literal + FileEntry 拆三类 + **校验五步**(R2 R-2/R-3/R-4)+ **text_provider lifespan 单例**(R2 R-8)。

**完工前**:§ 8 验收 1-9 全过;commit subject 单行无 body(反例 17);完工三件套(决策 08);03 索引字节级修订;PR(Codex 给 PM 标题 + 正文)。

---

## 后续 Task 接力点

### 直接阻塞(等本 Task 合并)

- **TASK-205**:抄本 Task prompt loader + LLM 桥接 + Pydantic schema 模式
- **TASK-206**:接管前移 8 handler,追加 Quota + Evidence + 404/422 中文化 + E2E
- **TASK-207**:基于本 Task 实战 + 评测 freeze schema 字段
- **TASK-307**:完整 CitationEnforcer(D2 解锁)
- **TASK-402**:消费 12 字段 JSON 渲染 UI

### 可复用 / 未来解锁

- **TASK-204**:`SqliteOverviewCache(OverviewCache)` 替换 InMemory(D5);CleanupWorker invalidate 联动(D15)
- **TASK-305**:回填 TeachingUnit 中间层(D6);prompt yaml 升 v0.2 + 跑评测

### Phase 2 候选

LLM streaming / 多 worker + Sqlite 跨进程 / prompt A/B 路由 / ProjectGraphCache / `generated_at` UX 字段(D8)。

---

## R2 衍生观察点(冲突表,二审已采用本预留)

### 观察点 1:`ProjectTypeResolver` 接口可能过早抽象(R2 已挑战并维持原案)

**R2 实际反馈**:R2 确认"不阻断";`resolve(project) -> str` 返回纯字符串,**不依赖** `ProjectOverview` / 其他 feature schema,**不形成 core → feature 反向类型依赖**(与 OverviewCache 关键差异)。

**保留理由**:作为 injected policy object,Phase 2 / TASK-305 替换 `HeuristicProjectTypeResolver` 时只改 DI 装配 1 处。

**强 challenge 下的退路**:若后续 review 强烈反对,可转 feature-private(`features/overview/_project_type_resolver.py`),DI 路径不变。本 Task v0.3 不实施。

---

**版本**:v0.3(R2 conditional pass 后修订;待 Codex 最终核查)
**日期**:2026-06-04
**作者**:Claude(架构师,第十一任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260601-04` / `20260601-06` / `20260603-09` / `20260604-11`
**审批**:R1 通过 + R2 conditional pass(20260604);v0.3 后直接交 Codex
