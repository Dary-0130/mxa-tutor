# 架构总览 · ARCHITECTURE OVERVIEW

> **前置阅读**:必须先读 `01_PROJECT_CONSTITUTION.md`
> **目的**:让任何新接手的人 / AI 在 15 分钟内理解整个系统结构
> **版本**:v3.1(delta)

---

## 1. 系统分层全景

```
┌──────────────────────────────────────────────────────────┐
│  Web 前端 web/                                           │
│  上传页 · 工程导览页 · 问答对话 · 支付页 · 用户中心      │
└─────────────────────────┬────────────────────────────────┘
                          │ HTTP/WebSocket
                          ▼
┌──────────────────────────────────────────────────────────┐
│  API 层 api/                                             │
│  FastAPI 路由 · 认证中间件 · 限流 · 文件上传 · 沙箱      │
└─────────────────────────┬────────────────────────────────┘
                          │ 调用 feature service
                          ▼
┌──────────────────────────────────────────────────────────┐
│  功能层 features/                                        │
│  ProjectIngestService    工程解析入库                    │
│  ProjectOverviewService  导览生成(含 Graph + Teaching)│
│  ChatService             智能问答                        │
│  PaymentService          支付与额度                      │
└─────────────────────────┬────────────────────────────────┘
                          │ 依赖 core 抽象接口和领域模型
                          ▼
┌──────────────────────────────────────────────────────────┐
│  核心层 core/                                            │
│  domain/      Project, SlxModel, MFile, ChatMessage      │
│               ProjectGraph, TeachingUnit, SourceRef ⭐  │
│  interfaces/  抽象接口(LLM, Embedder, Parser, Store)    │
│  prompts/     所有 prompt 模板                           │
└─────────────────────────▲────────────────────────────────┘
                          │ 实现 core 接口
                          │
┌─────────────────────────┴────────────────────────────────┐
│  适配器层 adapters/                                      │
│  llm/           DeepSeek V4-Flash / V4-Pro 适配器        │
│  embedding/     sentence-transformers 本地嵌入           │
│  parser/        .slx XML 解析 / .m 解析 / .mat 元信息    │
│  storage/       SQLite 存储 / 文件系统存储 / 沙箱        │
│  payment/       微信支付适配器(Phase 2)                  │
└──────────────────────────────────────────────────────────┘
```

⭐ = v2.1 新增的"教学理解中间层"

---

## 2. 教学理解中间层(架构核心)

### 数据流(v2.1 核心)

```
Parser 输出(SlxModel / MFile / 文件树)
   ↓ (无 LLM,纯结构化转换)
ProjectGraph
   - 节点:文件、subsystem、block、function、参数
   - 边:调用关系、信号流、数据依赖、归属关系
   - 入口点、执行流、数据流、控制流
   - 未解析符号(unresolved symbols)
   ↓ (调 LLM,基于 ProjectGraph 生成)
TeachingUnit
   - 教学讲解单元(可按 block / file / subsystem / project 维度)
   - 每个单元含目标、级别、摘要、前置概念、讲解步骤、相关概念、SourceRef
   ↓ (基于 TeachingUnit + 5 类输出格式)
最终输出(项目导览 / block 讲解 / 文件讲解 / 问答)
```

### 资料入口数据流(v3.0 paper-to-model)

```
用户上传论文 / 报告(PDF·docx)
   ↓
文档安全沙箱(格式嗅探 / 解析器超时 / 不执行外链或宏)
   ↓
PaperParser
   ↓
PaperSpec
   ↓
PaperPlanService
   ↓
ModelGenerationPlan + TuningSuggestion
   ↓
用户据路线图在 MATLAB 中搭建 / 调参
```

资料入口的 EvidencePack 必须区分 `document_extracted` 与 `user_supplied` 两类来源:文档抽取的公式 / 参数 / 段落证据走 `document_extracted`,用户补充的缺失参数走 `user_supplied`,下游回答和调参建议不得把用户补充伪装成文档证据。

### v0.3-a 诊断传输桥数据流(连接 spike,不含 Engine;TASK-510)

```
用户本地 MATLAB(R2026a)+ mxa Add-on(.mltbx)
   ↓ 用户手动粘贴错误文本(manual_error)
客户端绝对路径 best-effort 脱敏 → uiconfirm 确认(快照冻结)
   ↓ HTTPS,POST /api/v1/bridge/diagnostic
mxa-tutor Web 后端(loopback 限定 + feature flag 失败关闭 + 415/413/403 边界)
   ↓ 不调 LLM / DB / cache,不持久化,不 echo error_text
固定连接回执(connectivity stub)→ 客户端 UI
```

**v0.3-a 边界**:仅验证**传输连接桥**,**不接入、不验证 MATLAB Engine**,不运行模型、不解释报错、不回传建议。Engine 接入 + 自动错误/状态采集 + 报错解释/收敛/波形解释 + 建议回传 归 **v0.3-b**(届时数据流补充 Engine 采集段)。

### 关键原则

**不要让 LLM"猜工程",要让解析器"还原工程",再让 LLM"讲工程"**。

具体来说:
1. Parser 只做"还原"(纯解析,无 LLM)
2. ProjectGraph 只做"结构理解"(无 LLM,基于解析结果)
3. TeachingUnit 才用 LLM(基于 ProjectGraph 生成教学化讲解)
4. 用户看到的输出(导览 / 讲解 / 问答)基于 TeachingUnit

### 实现位置

| 层 | 文件 |
|----|------|
| 数据结构 | `core/domain/project_graph.py` / `teaching_unit.py` / `source_ref.py` |
| 构建逻辑 | `features/overview/project_graph_builder.py` / `teaching_unit_builder.py` |
| Prompt 模板 | `core/prompts/project_graph_build.yaml` / `teaching_unit_generate.yaml` |

**注意:**不新增顶层 `features/understanding/`。决策见 `docs/decisions/20260601-04-understanding-not-top-level-feature.md`。

### v3.0 paper feature 边界

paper-to-model 新建 `features/paper/` 与 `core/domain/paper_*.py` 对等实现,复用 MCS 的治理机制和基础设施,不改造既有 `features/overview/` 私有结构。`features/paper/` 与 `features/overview/` 不互相 import 私有结构;跨 feature 共享只能放在 `core/` 公开 contract 层(沿用决策 21 boundary)。

PaperGraph 方向拍板为**新建独立 `PaperGraph`**,不扩展 `ProjectGraph`。理由:`ProjectGraph` 的 `NodeType` / `EdgeType` 已绑定 .m / .slx / .mat 工程结构,并被 overview / chunking / chat / explanation 多处消费;独立 `PaperGraph` 可以复用节点-边-入口-流向的框架,同时避免论文节点污染既有 MCS 契约。

---

## 3. 目录结构(权威版本 v2.1)

```
mxa-tutor/
│
├── docs/                                    # 所有文档
│   ├── 01_PROJECT_CONSTITUTION.md           # 项目宪法
│   ├── 02_ARCHITECTURE_OVERVIEW.md          # 本文件
│   ├── 03_TASK_INDEX.md                     # Task 总览
│   ├── 04_ENGINEERING_STANDARDS.md          # 工程规范细则
│   ├── 05_EXPLANATION_STYLE_GUIDE.md        # 教学输出风格规范 ⭐
│   ├── tasks/                               # 每个 Task 一个文件
│   ├── decisions/                           # 决策日志
│   └── api/                                 # API 文档(自动生成)
│
├── core/                                    # 纯业务,无外部依赖
│   ├── domain/
│   │   ├── project.py                       # Project 数据结构
│   │   ├── slx_model.py                     # Simulink 模型结构
│   │   ├── m_file.py                        # MATLAB 代码文件
│   │   ├── mat_metadata.py                  # .mat 元信息 ⭐
│   │   ├── chat.py                          # ChatMessage / ChatSession
│   │   ├── project_graph.py                 # ProjectGraph + Node + Edge ⭐
│   │   ├── teaching_unit.py                 # TeachingUnit ⭐
│   │   ├── source_ref.py                    # SourceRef(证据引用) ⭐
│   │   └── exceptions.py                    # 业务异常
│   ├── interfaces/
│   │   ├── llm_provider.py                  # TextProvider
│   │   ├── embedder.py                      # EmbeddingProvider
│   │   ├── parser.py                        # SlxParser / MParser
│   │   ├── project_store.py                 # ProjectRepository
│   │   └── chat_store.py                    # ChatRepository
│   └── prompts/
│       ├── project_graph_build.yaml         # ProjectGraph 构建辅助 ⭐
│       ├── teaching_unit_generate.yaml      # TeachingUnit 生成 ⭐
│       ├── project_overview.yaml            # 工程导览生成
│       ├── slx_block_explain.yaml           # Simulink block 讲解
│       ├── m_code_explain.yaml              # MATLAB 代码讲解
│       ├── qa_with_context.yaml             # 带 RAG 的问答(强制证据)
│       └── classify_project.yaml            # 项目类型识别
│
├── adapters/                                # 实现 core 接口
│   ├── llm/
│   │   ├── deepseek.py                      # TextProvider 实现
│   │   └── README.md
│   ├── embedding/
│   │   ├── sentence_transformer.py          # bge-small-zh / m3e-small
│   │   └── README.md
│   ├── parser/
│   │   ├── slx_parser.py                    # .slx XML 解析(核心)
│   │   ├── m_parser.py                      # .m 代码结构提取
│   │   ├── mat_reader.py                    # .mat 仅元信息 ⭐
│   │   ├── prj_parser.py                    # .prj 项目文件解析
│   │   ├── zip_extractor.py                 # 工程压缩包解压(含沙箱) ⭐
│   │   └── README.md
│   ├── storage/
│   │   ├── sqlite_project_store.py
│   │   ├── sqlite_chat_store.py
│   │   ├── file_storage.py                  # 文件系统暂存(含 TTL)
│   │   └── README.md
│   └── payment/                             # Phase 2
│       └── (待 Phase 2)
│
├── features/                                # 业务功能
│   ├── ingest/
│   │   ├── service.py                       # ProjectIngestService
│   │   ├── README.md
│   │   └── eval_cases/
│   ├── overview/
│   │   ├── service.py                       # ProjectOverviewService
│   │   ├── project_graph_builder.py         # ProjectGraph 构建器 ⭐
│   │   ├── teaching_unit_builder.py         # TeachingUnit 构建器 ⭐
│   │   ├── schemas.py                       # Overview 输出 schema ⭐
│   │   ├── citation_collector.py            # 证据收集器 ⭐
│   │   ├── README.md
│   │   └── eval_cases/
│   ├── chat/
│   │   ├── service.py                       # ChatService
│   │   ├── retriever.py                     # RAG 检索
│   │   ├── citation_enforcer.py             # 证据引用强制器 ⭐
│   │   ├── README.md
│   │   └── eval_cases/
│   └── billing/
│       ├── service.py                       # 额度与套餐
│       └── README.md
│
├── api/                                     # FastAPI 后端
│   ├── main.py                              # FastAPI 入口
│   ├── routes/
│   │   ├── upload.py                        # 上传 + 解析(含沙箱)
│   │   ├── overview.py                      # 获取导览
│   │   ├── chat.py                          # 问答
│   │   ├── auth.py                          # 用户认证
│   │   └── payment.py                       # 支付(Phase 2)
│   ├── middleware/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   └── error_handler.py
│   ├── dependencies.py                      # 依赖注入
│   └── README.md
│
├── web/                                     # 前端
│   ├── (Next.js / Vue 3,Task 401 时定型)
│   └── README.md
│
├── app/                                     # 应用装配
│   ├── config.py                            # 配置加载(pydantic)
│   ├── container.py                         # 依赖注入容器
│   └── logger.py                            # loguru 配置
│
├── tests/                                   # 单元测试
│   ├── core/
│   ├── adapters/
│   ├── features/
│   ├── api/
│   ├── fixtures/                            # 测试数据
│   │   ├── slx_samples/                     # 真实 .slx 测试文件
│   │   ├── m_samples/                       # 真实 .m 测试文件
│   │   └── malicious_zips/                  # 恶意 zip 测试(zip bomb 等) ⭐
│   └── conftest.py
│
├── eval/                                    # 评测系统
│   ├── cases/                               # 真实工程评测集
│   ├── run_eval.py                          # 评测脚本
│   └── results/                             # 评测结果归档
│
├── scripts/                                 # 一次性脚本
│   ├── init_db.py                           # 数据库初始化
│   └── dev_setup.py                         # 开发环境一键准备
│
├── .github/
│   └── workflows/
│       └── ci.yml                           # GitHub Actions CI
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── Makefile                                 # 常用命令封装
```

⭐ = v2.1 新增

---

## 4. 关键接口契约

### 4.1 基础数据结构(core/domain)

```python
# core/domain/project.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ProjectType(Enum):
    CONTROL_SYSTEM = "control_system"
    SIGNAL_PROCESSING = "signal_processing"
    POWER_ELECTRONICS = "power_electronics"
    COMMUNICATION = "communication"
    MOTOR_CONTROL = "motor_control"
    NEW_ENERGY = "new_energy"
    GENERAL = "general"


@dataclass
class FileInfo:
    relative_path: str
    file_type: str               # ".m" / ".slx" / ".mat" / ".prj" / "other"
    size_bytes: int
    description: str | None = None


@dataclass
class Project:
    id: str                      # 工程唯一 ID(内容哈希)
    name: str
    project_type: ProjectType
    files: list[FileInfo]
    slx_models: list["SlxModel"]
    m_files: list["MFile"]
    mat_files: list["MatMetadata"]   # 仅元信息,不存原始数据
    created_at: datetime
    file_dependencies: dict[str, list[str]]
```

```python
# core/domain/slx_model.py
@dataclass
class SlxBlock:
    block_id: str
    name: str
    block_type: str              # "Gain" / "Sum" / "Subsystem" / etc.
    parameters: dict[str, str]
    position: tuple[int, int, int, int]
    parent_subsystem: str | None
    is_masked: bool = False      # 是否 masked
    is_library_link: bool = False  # 是否引用 library
    is_model_reference: bool = False  # 是否引用其他模型


@dataclass
class SlxLine:
    from_block: str
    from_port: int
    to_block: str
    to_port: int


@dataclass
class SlxModel:
    file_path: str
    name: str
    blocks: list[SlxBlock]
    lines: list[SlxLine]
    subsystems: dict[str, list[str]]
    solver_config: dict[str, str]
    parse_warnings: list[str]    # 解析警告(无法解析的部分)
```

```python
# core/domain/m_file.py
@dataclass
class MFunction:
    name: str
    inputs: list[str]
    outputs: list[str]
    line_range: tuple[int, int]
    docstring: str | None


@dataclass
class MFile:
    file_path: str
    file_role: str               # "script" / "function" / "class"
    functions: list[MFunction]
    imports: list[str]
    uses_toolbox: list[str]
    raw_code: str
```

```python
# core/domain/mat_metadata.py  ⭐ v2.1 新增
@dataclass
class MatVariable:
    name: str
    var_type: str                # "double" / "char" / "struct" / "timeseries" / etc.
    shape: tuple[int, ...]
    likely_role: str | None      # "param_table" / "input_data" / "sim_result" / "unknown"
    first_field_names: list[str] # 如果是 struct,前几个字段名


@dataclass
class MatMetadata:
    """仅 .mat 元信息,不存原始数据"""
    file_path: str
    file_size_bytes: int
    variables: list[MatVariable]
```

### 4.2 教学理解中间层数据结构 ⭐

```python
# core/domain/source_ref.py
@dataclass
class SourceRef:
    """证据引用 —— 所有教学输出和问答都必须基于 SourceRef"""
    file_path: str
    line_range: tuple[int, int] | None = None   # .m 文件用
    block_id: str | None = None                  # .slx block 用
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None            # 引用具体参数时用
```

```python
# core/domain/project_graph.py
from enum import Enum

class NodeType(Enum):
    FILE_M = "file_m"
    FILE_SLX = "file_slx"
    FILE_MAT = "file_mat"
    BLOCK = "block"
    SUBSYSTEM = "subsystem"
    FUNCTION = "function"
    PARAMETER = "parameter"


class EdgeType(Enum):
    CALLS = "calls"              # .m 文件之间的调用
    SIGNAL_FLOWS = "signal_flows"  # Simulink 信号流
    BELONGS_TO = "belongs_to"    # 父子归属(block 属于 subsystem 等)
    READS_PARAM = "reads_param"  # 读取参数
    LOADS_DATA = "loads_data"    # 加载 .mat 文件


@dataclass
class ProjectNode:
    id: str
    type: NodeType
    label: str                   # 显示名
    source_ref: SourceRef
    metadata: dict[str, str]     # 任意附加信息


@dataclass
class ProjectEdge:
    from_node: str
    to_node: str
    type: EdgeType


@dataclass
class ProjectGraph:
    project_id: str
    nodes: list[ProjectNode]
    edges: list[ProjectEdge]
    entry_points: list[str]      # 工程的入口节点 IDs(主脚本、顶层模型等)
    execution_flow: list[str]    # 推测的执行顺序
    data_flow: list[str]         # 数据流主线
    control_flow: list[str]      # 控制流主线
    unresolved_symbols: list[str]  # 未能解析的符号
```

```python
# core/domain/teaching_unit.py
@dataclass
class TeachingUnit:
    """教学讲解单元 —— LLM 基于此生成最终输出"""
    id: str
    title: str
    target: str                  # "file" / "function" / "block" / "subsystem" / "model" / "project"
    target_id: str               # 对应 ProjectNode.id
    level: str                   # "beginner" / "normal" / "advanced"
    summary: str                 # 一句话总结
    prerequisites: list[str]     # 前置概念(其他 TeachingUnit.id)
    explanation_steps: list[str] # 讲解步骤
    related_concepts: list[str]  # 相关知识点(如"PID 控制器""根轨迹"等)
    source_refs: list[SourceRef]  # 证据,至少 1 个
    confusion_points: list[str]  # 学生容易误解的地方
```

#### v3.0 paper-to-model 占位签名(不冻结字段)

- `PaperSpec`:论文结构化规格,输入 = 解析后的 PDF/docx,输出 = 摘要 / 公式 / 参数表 / 图表位置 / 伪代码的结构化表示;具体字段留 `06_OUTPUT_CONTRACTS.md` 与 TASK-501 落地。
- `PaperGraph`:论文-模型对应图,输入 = `PaperSpec`,输出 = 段落 / 公式 / 参数 / 图表与模型搭建路线之间的引用 / 推导 / 对应关系;本 PR 拍板为独立结构,不扩展 `ProjectGraph`,具体字段留 06 与 TASK-501。
- `ModelGenerationPlan`:模型搭建路线图,输入 = `PaperSpec` / `PaperGraph` / 用户补充参数,输出 = 库选型 / block 建议 / 参数对应 / 子系统拆分 / `.m` 骨架建议;具体字段留 06 与 TASK-501。
- `TuningSuggestion`:调参建议,输入 = 用户场景 / 已知模型路线 / 参数证据,输出 = 调参方向与物理影响讲解;具体字段留 06 与 TASK-501。
- `MissingParameterPrompt`:缺失参数补充提示,输入 = 文档中出现但未抽到数值或单位的参数线索,输出 = 用户待补充项及来源说明;具体字段留 06 与 TASK-501。

### 4.3 LLM 接口(ModelCapability 扩展版) ⭐

```python
# core/interfaces/llm_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ModelCapability:
    """模型能力声明,用于路由和成本控制"""
    model_name: str
    supports_streaming: bool = False
    supports_json: bool = False
    supports_tool_call: bool = False
    supports_long_context: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 4096
    cost_input_per_million: float | None = None    # USD / 1M tokens
    cost_output_per_million: float | None = None   # USD / 1M tokens


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int


class TextProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
    
    @abstractmethod
    def capability(self) -> ModelCapability: ...
```

### 4.4 Embedding 接口

```python
# core/interfaces/embedder.py
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入,返回每个文本的向量"""
        ...
    
    @abstractmethod
    def dimension(self) -> int: ...
```

### 4.5 Parser 接口

```python
# core/interfaces/parser.py
class SlxParser(ABC):
    @abstractmethod
    def parse(self, slx_file_path: str) -> SlxModel: ...

class MParser(ABC):
    @abstractmethod
    def parse(self, m_file_path: str) -> MFile: ...
```

### 4.6 业务异常

```python
# core/domain/exceptions.py
class MxaError(Exception): pass

class LLMError(MxaError): pass
class LLMAuthError(LLMError): pass
class LLMQuotaError(LLMError): pass
class LLMRateLimitError(LLMError): pass
class LLMServerError(LLMError): pass
class LLMTimeoutError(LLMError): pass

class ParseError(MxaError): pass
class SlxParseError(ParseError): pass
class MParseError(ParseError): pass

class ProjectError(MxaError): pass
class ProjectNotFoundError(ProjectError): pass
class ProjectTooLargeError(ProjectError): pass

class UploadError(MxaError): pass
class ZipBombError(UploadError): pass         # ⭐ v2.1 新增
class ZipSlipError(UploadError): pass         # ⭐ v2.1 新增
class FileTypeNotAllowedError(UploadError): pass  # ⭐ v2.1 新增

class QuotaExhaustedError(MxaError): pass

class EvidenceMissingError(MxaError): pass    # ⭐ v2.1 新增(无证据的回答)
```

---

## 5. 数据流示例

### 流 1:工程上传与解析

```
[用户在 Web 上传 .zip]
        ↓
[api/routes/upload] 接收文件 + 沙箱检查(大小、扩展名、压缩比)
        ↓
[ProjectIngestService.ingest(zip_bytes)]:
  ├─ ZipExtractor 安全解压(防 zip bomb / zip slip)到临时目录
  ├─ 遍历文件,按扩展名分类
  ├─ 对每个 .slx → SlxParser.parse() → SlxModel
  ├─ 对每个 .m → MParser.parse() → MFile
  ├─ 对每个 .mat → MatReader.parse() → MatMetadata(仅元信息)
  ├─ 分析文件依赖关系
  ├─ ProjectClassifier 识别项目类型(调 LLM)
  └─ 存入 ProjectRepository(SQLite)
        ↓
返回 project_id 给前端
        ↓
[Background Task] 后台生成导览:
  ├─ ProjectOverviewService.generate(project_id)
  │   ├─ ProjectGraphBuilder 构建 ProjectGraph(纯逻辑)
  │   ├─ TeachingUnitBuilder 调 LLM 生成 TeachingUnits
  │   ├─ OverviewSchemaGenerator 按固定 schema 输出导览
  │   └─ CitationCollector 收集所有 SourceRef
  ├─ 切块 + Embedding,存入向量表
  └─ 标记导览生成完成
```

### 流 2:智能问答(粗 RAG,Week 2 版)

```
[用户在 Web 输入问题]
        ↓
[api/routes/chat] 接收问题 + project_id
        ↓
[ChatService.ask(project_id, question)]:
  ├─ 检查额度(BillingService)
  ├─ Retriever.retrieve_coarse(question, project_id):
  │     └─ 关键词命中:文件名 / block 名 / function 名 / 参数名
  │     └─ 取 top-k 相关 TeachingUnit / chunk
  ├─ 拼装 prompt:系统提示 + 相关 TeachingUnit + 用户问题
  ├─ TextProvider.chat() → LLM 回答(JSON 模式,带 citations)
  ├─ CitationEnforcer 检查 citations 字段
  │     └─ 无 citation → 标记 warning,降级为"不确定"答案
  ├─ ChatRepository.save() 记录对话
  └─ BillingService.deduct() 扣除额度
        ↓
返回 {answer, citations, confidence}
```

### 流 3:智能问答(向量 RAG,Week 3 版)

```
同上,但 retrieve_coarse 换成 retrieve_vector:
  ├─ Embedder.embed(question) → 向量
  ├─ SQLite 向量检索 top-k chunks(带 metadata)
  ├─ 重排序(可选)
  └─ 返回 TeachingUnit + SourceRef
```

---

## 6. 关键技术决策

### 决策 1:用 SQLite + sentence-transformers,不上 Milvus

- **理由**:MCS 阶段单工程规模小,SQLite 完全够用
- **实现**:SQLite 表用 BLOB 存向量,查询时 Python 内存里做余弦相似度
- **何时升级**:单工程 chunk 数 > 5000 或 用户量 > 1000

### 决策 2:Embedding 用本地模型,不调云端

- **模型选**:`BAAI/bge-small-zh-v1.5`(中文,~100MB,效果好,免费)
- **理由**:Embedding 调用量大,云端成本不可控
- **实现**:Python 进程内加载,启动时一次性

### 决策 3:.slx 解析用 Python 标准库,不依赖 MATLAB

- **理由**:.slx = ZIP + XML,纯 Python 可解析
- **风险**:不同 MATLAB 版本格式可能有差异
- **应对**:Task 102 验收按 P0/P1/P2 分级,见 03 Task Index

### 决策 4:.m 文件先用正则 + 简单 AST

- **理由**:完整 MATLAB AST 太复杂,MCS 阶段不需要
- **范围**:能提取函数定义、输入输出、调用关系、注释即可

### 决策 5:.mat 文件第一版只做元信息

- **理由**:.mat 可能很大、可能含敏感数据、塞 LLM 没意义
- **范围**:读取 `scipy.io.loadmat` 或 `h5py` 顶层变量名、类型、shape
- **不做**:完整数据读取、自动画图、自动解释变量物理意义

### 决策 6:支付走"激活码"模式

- **MCS 第一版**:用户付款 → 客服微信收款 → 手动发激活码 → 网页输入激活码解锁
- **升级路径**:Phase 2 接入微信支付自动化

### 决策 7:教学理解中间层不抽出独立 feature

- **决策**:`ProjectGraph` / `TeachingUnit` 数据结构在 `core/domain/`,构建逻辑在 `features/overview/` 内部模块
- **理由**:MCS 阶段不是独立用户用例,减少 Codex 心智负担
- **何时抽出**:满足任一条件
  1. ChatService 频繁主动重建 ProjectGraph
  2. 导出报告、答辩准备、知识点映射多处复用 TeachingUnit
  3. understanding 相关代码超过 500-800 行
  4. 出现跨工程对比 / 工程质量分析等新能力
- **决策记录**:`docs/decisions/20260601-04-understanding-not-top-level-feature.md`

---

## 7. 配置管理

```python
# app/config.py 用 pydantic-settings

from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    # LLM
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    
    # Storage
    db_path: str = "./data/mxa.db"
    upload_dir: str = "./data/uploads"
    upload_ttl_hours: int = 24
    
    # Quota
    free_question_per_project: int = 3
    single_pack_quota: int = 100        # ⭐ v2.1
    monthly_quota: int = 300            # ⭐ v2.1
    
    # File limits  ⭐ v2.1 加强
    max_upload_size_mb: int = 50
    max_files_per_project: int = 200
    max_single_file_mb: int = 20
    max_compression_ratio: int = 100     # 防 zip bomb
    
    class Config:
        env_file = ".env"
```

---

## 8. 异步与并发策略

- **API 接口**:全部 `async def`
- **耗时任务**(LLM 调用、文件解析、Embedding):FastAPI `BackgroundTasks` 或 `asyncio.create_task`
- **数据库**:SQLite + `aiosqlite`(异步驱动)
- **进程内并发**:Uvicorn 单进程多 worker,初期 4 worker

---

## 9. 错误处理与用户提示

| 后端错误 | 用户看到的中文 |
|----------|--------------|
| `LLMAuthError` | "服务暂时不可用,请稍后重试" |
| `LLMQuotaError` | "服务繁忙,请稍后" |
| `LLMRateLimitError` | "请求太频繁,稍等一下" |
| `LLMTimeoutError` | "网络较慢,正在重试..." |
| `LLMServerError` | "AI 服务暂不稳定,请刷新重试" |
| `SlxParseError` | "Simulink 模型解析失败,可能版本过老或损坏" |
| `MParseError` | ".m 文件解析失败,请检查文件编码" |
| `ProjectTooLargeError` | "工程过大,请压缩到 50MB 以内" |
| `ZipBombError` ⭐ | "压缩文件异常,请检查后重新上传" |
| `ZipSlipError` ⭐ | "压缩包内含非法路径,请重新打包后上传" |
| `FileTypeNotAllowedError` ⭐ | "包含不支持的文件类型,只支持 .m / .slx / .mat / .prj / .txt / .md" |
| `QuotaExhaustedError` | "已达到合理使用上限,可联系加量" |
| `EvidenceMissingError` ⭐ | (内部错误,降级为"不确定"答案返回) |
| 未知异常 | "出了点问题,我们已经记录,稍后再试" |

---

## 10. 部署与分发

### MCS 阶段
- **后端**:阿里云 / 腾讯云轻量服务器(99-199 元/年)
- **数据库**:服务器本地 SQLite
- **前端**:Vercel / 腾讯云静态托管 / 直接 Nginx
- **域名**:.com 或 .cn,80-200 元/年
- **HTTPS**:Let's Encrypt 免费

### 后续(MCS 跑通后)
- 后端可能升级到 Docker + 阿里云 ECS
- 数据库可能升级 PostgreSQL
- 加 CDN

---

## 11. 性能预算

| 指标 | 目标 | 硬上限 |
|------|------|-------|
| 工程上传响应 | < 5s | < 30s |
| 完整解析(< 10MB 工程) | < 30s | < 90s |
| 完整解析(10-50MB 工程) | < 90s | < 180s |
| 单次问答响应 | < 8s | < 20s |
| 二次访问同工程 | < 5s | < 15s |
| 并发用户(单服务器) | 50 | 100 |

---

## 12. 监控与日志

### 日志(MCS 阶段)
- **本地文件**:`loguru` 按天滚动
- **内容**:请求路径、状态码、耗时、token 消耗、错误堆栈
- **不记录**:用户上传内容、问题原文、回答原文

### 监控
- MCS 阶段:**无监控**(看日志就够)
- Phase 2:可能加 Sentry + 阿里云监控

---

## 13. CI / CD

### GitHub Actions
- 每个 PR 自动:
  - `pytest`
  - `ruff check`
  - `mypy`
- 失败的 PR 不允许合并

### 部署
- MCS 阶段:**手动 SSH 上服务器 git pull + systemd 重启**
- Phase 2:GitHub Actions 自动部署

---

**版本**:v3.1(delta)
**最后更新**:2026-06-21

## 修订历史

- v3.1(delta)(2026-06-21):前置同步 chore — §2 新增 v0.3-a 诊断传输桥数据流,明确 TASK-510 仅验证传输连接桥、不含 Engine;Engine 接入与自动采集/解释/建议返回归 v0.3-b
