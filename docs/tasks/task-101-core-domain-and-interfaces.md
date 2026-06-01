# TASK-101: core 接口 + domain 数据结构(基础)

## 状态
🔲 未开始

## 上下文

这是 Week 1 的第一个 Task,也是整个项目的地基。

Week 1 后续 6 个 Task(TASK-102 到 TASK-107)**全部依赖**本 Task 产出的数据结构和抽象接口:

- TASK-102 `.slx` 解析器 → 用 `SlxBlock` / `SlxLine` / `SlxModel` / `SlxParser` 接口 / `SlxParseError`
- TASK-103 `.m` 文件解析器 → 用 `MFunction` / `MFile` / `MParser` 接口 / `MParseError`
- TASK-104 工程压缩包安全解压 → 用 `FileInfo` / `UploadError` / `ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError` / `ProjectTooLargeError`
- TASK-105 文件依赖关系分析 → 用 `MFile`
- TASK-106 DeepSeek `TextProvider` 实现 → 用 `TextProvider` / `LLMMessage` / `LLMResponse` / `ModelCapability` / `LLMError` 各子类
- TASK-107 ProjectGraph + TeachingUnit 构建器 → 用 `ProjectGraph` / `ProjectNode` / `ProjectEdge` / `NodeType` / `EdgeType` / `TeachingUnit` / `SourceRef`

**本 Task 只建"形",不写"行为"**。所有具体实现(解析、LLM 调用、构建逻辑)是后续 Task 的事。

## 输入(前置依赖)

- Week 0 已完成(TASK-001 项目骨架 + TASK-002 开发环境/CI),`main` 分支可用
- 仓库目录结构已按 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节建好,`core/domain/` 和 `core/interfaces/` 目录存在
- 必读文档:
  - `docs/01_PROJECT_CONSTITUTION.md`
  - `docs/02_ARCHITECTURE_OVERVIEW.md`(尤其第 4 节"关键接口契约")
  - `docs/04_ENGINEERING_STANDARDS.md`(尤其第 4 节代码风格、第 5 节测试规范)

## 输出(交付物)

### 新增文件

```
core/domain/
  source_ref.py              SourceRef
  project.py                 ProjectType / FileInfo / Project
  slx_model.py               SlxBlock / SlxLine / SlxModel
  m_file.py                  MFunction / MFile
  mat_metadata.py            MatVariable / MatMetadata
  project_graph.py           NodeType / EdgeType / ProjectNode / ProjectEdge / ProjectGraph
  teaching_unit.py           TeachingUnit
  exceptions.py              MxaError 体系

core/interfaces/
  llm_provider.py            ModelCapability / LLMMessage / LLMResponse / TextProvider
  embedder.py                EmbeddingProvider
  parser.py                  SlxParser / MParser

tests/core/
  test_domain_source_ref.py
  test_domain_project.py
  test_domain_slx_model.py
  test_domain_m_file.py
  test_domain_mat_metadata.py
  test_domain_project_graph.py
  test_domain_teaching_unit.py
  test_domain_exceptions.py
  test_interfaces_llm_provider.py
  test_interfaces_embedder.py
  test_interfaces_parser.py
```

### 修改文件

- `core/domain/README.md` — 列出每个 domain 模块的职责(1-2 行/模块)
- `core/interfaces/README.md` — 列出每个 interface 模块的职责(1-2 行/模块)
- `docs/03_TASK_INDEX.md` — 把 TASK-101 状态从 🔲 改为 🔍,并同步底部"当前进度"那个进度条

### 不动文件

- `requirements.txt` / `requirements-dev.txt`(本 Task 不引入任何新依赖,标准库 `dataclasses` / `enum` / `abc` / `datetime` 全部内置)
- `pyproject.toml`
- `Makefile`
- `.github/workflows/ci.yml`
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何核心文档

## 范围(必须做)

- [ ] 创建上述 8 个 `core/domain/*.py` 文件,**严格按下方"接口契约"小节内联的代码实现**
- [ ] 创建上述 3 个 `core/interfaces/*.py` 文件,**严格按下方"接口契约"小节内联的代码实现**
- [ ] 给每个 dataclass / 接口类 / 异常类加 docstring(Google 风格,简短一句话即可)
- [ ] 每个公开符号(class / Enum 成员)都有类型注解(dataclass 字段必备)
- [ ] 编写单元测试,覆盖:
  - 每个 dataclass 能用所有必填字段构造,默认字段值正确
  - 每个 Enum 的全部取值与契约一致
  - 每个异常类的继承关系符合契约(`isinstance` 检查)
  - 每个抽象接口直接实例化会抛 `TypeError`(因为有未实现的 `@abstractmethod`)
  - 每个抽象接口能被一个**最小 Stub 子类**正确实现(签名匹配)
- [ ] 更新 `core/domain/README.md` 和 `core/interfaces/README.md`
- [ ] **最后一步**:本地全检通过(`make check` 全绿)后,把 `docs/03_TASK_INDEX.md` 中 TASK-101 行的状态从 🔲 改为 🔍,同步底部"当前进度"那个进度条,作为本 Task 最后一个 commit(`docs: mark TASK-101 as in-review in task index`)

## 不做(明确排除)

- ❌ **不实现 `core/domain/chat.py`**(`ChatMessage` / `ChatSession`)。这部分与存储层强耦合,放到 TASK-204(SQLite 存储层 Project + Chat)一起做。
- ❌ **不实现 `core/interfaces/project_store.py` 和 `core/interfaces/chat_store.py`**。同样推到 TASK-204。
- ❌ **不实现任何 adapter**(`adapters/llm/` / `adapters/parser/` / `adapters/embedding/` 等保持现状)。
- ❌ **不实现任何 feature service**(`features/ingest/` / `features/overview/` / `features/chat/` 等保持现状)。
- ❌ **不写任何 prompt yaml**(`core/prompts/` 目录保持现状)。
- ❌ **不在 `core/domain/` 或 `core/interfaces/` 中 import 任何业务逻辑模块**(不 import LLM SDK、不 import 文件解析库、不 import requests 等)。
- ❌ **不引入任何第三方依赖**。本 Task 全部基于 Python 标准库。
- ❌ **不修改 `core/prompts/` / `tests/fixtures/` / `eval/` / `scripts/` 下任何文件**。
- ❌ 不写集成测试,只写纯单元测试(测试运行总耗时应 < 1 秒)。

## 接口契约

> **以下所有代码块是本 Task 的硬契约**,**不允许擅自修改字段名、类型、默认值、继承关系、抽象方法签名**。
> 如果你在实现时发现任何字段缺少 / 类型可优化 / 应增加方法,**停手问 PM**,不要默默修改。
> 契约来源:`docs/02_ARCHITECTURE_OVERVIEW.md` 第 4 节(关键接口契约)。

### 通用约束

1. 全部使用 Python 标准库 `dataclasses.dataclass`(不用 pydantic;pydantic 只在 `app/config.py` 用)。
2. dataclass **默认不加 `frozen=True`**,保持可变。
3. 跨模块引用其他 dataclass / Enum 时,**使用真实 import**(如 `from core.domain.slx_model import SlxModel`),**不用字符串前向引用**(02 第 4 节示例代码中用的 `list["SlxModel"]` 是因为所有类型集中在一个代码块展示;真实文件中请用正常 import)。
4. Enum **不加 `str` 基类**,直接 `class XxxType(Enum)`(跟随 02 第 4 节契约)。
5. 所有 `@dataclass` / `class` / Enum 必须有 docstring(一句话即可)。
6. 每文件 ≤ 300 行(本 Task 任何文件都远低于此)。

### 4.1 基础数据结构

`core/domain/source_ref.py`:

```python
from dataclasses import dataclass


@dataclass
class SourceRef:
    """证据引用 —— 所有教学输出和问答都必须基于 SourceRef。"""
    file_path: str
    line_range: tuple[int, int] | None = None   # .m 文件用
    block_id: str | None = None                  # .slx block 用
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None            # 引用具体参数时用
```

`core/domain/project.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.domain.slx_model import SlxModel
from core.domain.m_file import MFile
from core.domain.mat_metadata import MatMetadata


class ProjectType(Enum):
    """项目类型分类,用于路由 prompt 模板和导览生成。"""
    CONTROL_SYSTEM = "control_system"
    SIGNAL_PROCESSING = "signal_processing"
    POWER_ELECTRONICS = "power_electronics"
    COMMUNICATION = "communication"
    MOTOR_CONTROL = "motor_control"
    NEW_ENERGY = "new_energy"
    GENERAL = "general"


@dataclass
class FileInfo:
    """工程中单个文件的元信息。"""
    relative_path: str
    file_type: str               # ".m" / ".slx" / ".mat" / ".prj" / "other"
    size_bytes: int
    description: str | None = None


@dataclass
class Project:
    """单个上传工程的完整结构化表示。"""
    id: str                          # 工程唯一 ID(内容哈希)
    name: str
    project_type: ProjectType
    files: list[FileInfo]
    slx_models: list[SlxModel]
    m_files: list[MFile]
    mat_files: list[MatMetadata]     # 仅元信息,不存原始数据
    created_at: datetime
    file_dependencies: dict[str, list[str]]
```

`core/domain/slx_model.py`:

```python
from dataclasses import dataclass


@dataclass
class SlxBlock:
    """Simulink 模型中的单个 block。"""
    block_id: str
    name: str
    block_type: str              # "Gain" / "Sum" / "Subsystem" / etc.
    parameters: dict[str, str]
    position: tuple[int, int, int, int]
    parent_subsystem: str | None
    is_masked: bool = False
    is_library_link: bool = False
    is_model_reference: bool = False


@dataclass
class SlxLine:
    """Simulink 模型中两个 block 之间的连接线。"""
    from_block: str
    from_port: int
    to_block: str
    to_port: int


@dataclass
class SlxModel:
    """单个 .slx 文件解析后的结构化表示。"""
    file_path: str
    name: str
    blocks: list[SlxBlock]
    lines: list[SlxLine]
    subsystems: dict[str, list[str]]
    solver_config: dict[str, str]
    parse_warnings: list[str]    # 解析警告(无法解析的部分)
```

`core/domain/m_file.py`:

```python
from dataclasses import dataclass


@dataclass
class MFunction:
    """MATLAB 文件中的单个函数定义。"""
    name: str
    inputs: list[str]
    outputs: list[str]
    line_range: tuple[int, int]
    docstring: str | None


@dataclass
class MFile:
    """单个 .m 文件解析后的结构化表示。"""
    file_path: str
    file_role: str               # "script" / "function" / "class"
    functions: list[MFunction]
    imports: list[str]
    uses_toolbox: list[str]
    raw_code: str
```

`core/domain/mat_metadata.py`:

```python
from dataclasses import dataclass


@dataclass
class MatVariable:
    """单个 .mat 变量的元信息(不含原始数据)。"""
    name: str
    var_type: str                # "double" / "char" / "struct" / "timeseries" / etc.
    shape: tuple[int, ...]
    likely_role: str | None      # "param_table" / "input_data" / "sim_result" / "unknown"
    first_field_names: list[str] # 如果是 struct,前几个字段名


@dataclass
class MatMetadata:
    """单个 .mat 文件的元信息汇总,不存原始数据。"""
    file_path: str
    file_size_bytes: int
    variables: list[MatVariable]
```

### 4.2 教学理解中间层数据结构

`core/domain/project_graph.py`:

```python
from dataclasses import dataclass
from enum import Enum

from core.domain.source_ref import SourceRef


class NodeType(Enum):
    """ProjectGraph 中节点的类型。"""
    FILE_M = "file_m"
    FILE_SLX = "file_slx"
    FILE_MAT = "file_mat"
    BLOCK = "block"
    SUBSYSTEM = "subsystem"
    FUNCTION = "function"
    PARAMETER = "parameter"


class EdgeType(Enum):
    """ProjectGraph 中边的类型。"""
    CALLS = "calls"              # .m 文件之间的调用
    SIGNAL_FLOWS = "signal_flows"  # Simulink 信号流
    BELONGS_TO = "belongs_to"    # 父子归属(block 属于 subsystem 等)
    READS_PARAM = "reads_param"  # 读取参数
    LOADS_DATA = "loads_data"    # 加载 .mat 文件


@dataclass
class ProjectNode:
    """ProjectGraph 的一个节点。"""
    id: str
    type: NodeType
    label: str                   # 显示名
    source_ref: SourceRef
    metadata: dict[str, str]     # 任意附加信息


@dataclass
class ProjectEdge:
    """ProjectGraph 的一条边。"""
    from_node: str
    to_node: str
    type: EdgeType


@dataclass
class ProjectGraph:
    """工程的结构化理解图,由 Parser 输出经纯逻辑转换构建,不含 LLM 调用。"""
    project_id: str
    nodes: list[ProjectNode]
    edges: list[ProjectEdge]
    entry_points: list[str]      # 工程的入口节点 IDs(主脚本、顶层模型等)
    execution_flow: list[str]    # 推测的执行顺序
    data_flow: list[str]         # 数据流主线
    control_flow: list[str]      # 控制流主线
    unresolved_symbols: list[str]  # 未能解析的符号
```

`core/domain/teaching_unit.py`:

```python
from dataclasses import dataclass

from core.domain.source_ref import SourceRef


@dataclass
class TeachingUnit:
    """教学讲解单元 —— LLM 基于此生成最终输出(导览 / block 讲解 / .m 讲解 / 问答)。"""
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

### 4.3 LLM 接口

`core/interfaces/llm_provider.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelCapability:
    """模型能力声明,用于路由和成本控制。"""
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
    """LLM 对话中的单条消息。"""
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """LLM 单次响应的结构化结果。"""
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int


class TextProvider(ABC):
    """文本类 LLM 提供方的抽象接口(DeepSeek 等具体实现见 adapters/llm/)。"""

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

`core/interfaces/embedder.py`:

```python
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """嵌入模型的抽象接口(具体实现见 adapters/embedding/)。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入,返回每个文本的向量。"""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度。"""
        ...
```

### 4.5 Parser 接口

`core/interfaces/parser.py`:

```python
from abc import ABC, abstractmethod

from core.domain.slx_model import SlxModel
from core.domain.m_file import MFile


class SlxParser(ABC):
    """.slx 文件解析器的抽象接口(具体实现见 adapters/parser/)。"""

    @abstractmethod
    def parse(self, slx_file_path: str) -> SlxModel: ...


class MParser(ABC):
    """.m 文件解析器的抽象接口(具体实现见 adapters/parser/)。"""

    @abstractmethod
    def parse(self, m_file_path: str) -> MFile: ...
```

### 4.6 业务异常体系

`core/domain/exceptions.py`:

```python
class MxaError(Exception):
    """所有业务异常的基类。"""


class LLMError(MxaError):
    """LLM 调用相关异常的基类。"""


class LLMAuthError(LLMError):
    """LLM API 鉴权失败(API Key 无效 / 过期)。"""


class LLMQuotaError(LLMError):
    """LLM 服务商额度耗尽。"""


class LLMRateLimitError(LLMError):
    """LLM 请求被限流。"""


class LLMServerError(LLMError):
    """LLM 服务端错误(5xx)。"""


class LLMTimeoutError(LLMError):
    """LLM 调用超时。"""


class ParseError(MxaError):
    """文件解析异常的基类。"""


class SlxParseError(ParseError):
    """.slx 文件解析失败。"""


class MParseError(ParseError):
    """.m 文件解析失败。"""


class ProjectError(MxaError):
    """工程相关异常的基类。"""


class ProjectNotFoundError(ProjectError):
    """指定工程不存在。"""


class ProjectTooLargeError(ProjectError):
    """工程超过大小 / 文件数限制。"""


class UploadError(MxaError):
    """上传相关异常的基类。"""


class ZipBombError(UploadError):
    """压缩比异常,疑似 zip bomb。"""


class ZipSlipError(UploadError):
    """压缩包内含非法路径(zip slip 攻击)。"""


class FileTypeNotAllowedError(UploadError):
    """文件扩展名不在白名单。"""


class QuotaExhaustedError(MxaError):
    """用户使用额度耗尽。"""


class EvidenceMissingError(MxaError):
    """LLM 回答缺少证据引用(被 CitationEnforcer 拦截)。"""
```

> **注意**:`docs/04_ENGINEERING_STANDARDS.md` 第 10 节"三层异常体系"中提到了一个略写的 `QuotaError` 作为基类,但 02 第 4.6 节用的是 `QuotaExhaustedError`。**本 Task 以 02 第 4.6 节为准**,实现 `QuotaExhaustedError`(直接继承 `MxaError`,不引入 `QuotaError` 中间基类)。

## 验收标准

> **以下每条都给出 PM 可在 Git Bash 跑出来的命令**。
> 命令在仓库根目录(`F:\mxa-tutor`)下执行,且已 `source .venv/Scripts/activate`(或 Windows 下 `.venv\Scripts\activate.bat`)。

### 1. 文件全部创建

```bash
ls core/domain/source_ref.py core/domain/project.py core/domain/slx_model.py \
   core/domain/m_file.py core/domain/mat_metadata.py core/domain/project_graph.py \
   core/domain/teaching_unit.py core/domain/exceptions.py \
   core/interfaces/llm_provider.py core/interfaces/embedder.py core/interfaces/parser.py
```

11 个文件全部存在(11 行输出,无 "No such file" 报错)。

### 2. 不应被创建的文件确实没创建

```bash
ls core/domain/chat.py core/interfaces/project_store.py core/interfaces/chat_store.py 2>&1
```

期望:全部 "No such file or directory"。

### 3. 没有引入第三方依赖

**最直观的方式**:PM 在 GitHub PR 页面 "Files changed" 标签查看,**不应**出现 `requirements.txt` / `requirements-dev.txt` / `pyproject.toml` 这三个文件。

**本地备选验证**(需要先 `git fetch origin main`):

```bash
git fetch origin main
git diff origin/main..HEAD --name-only -- requirements.txt requirements-dev.txt pyproject.toml
```

期望:无输出(本 Task 完全不动这三个文件)。

### 4. domain 和 interfaces 内部不 import 任何外部库

```bash
grep -rn "^import\|^from" core/domain/ core/interfaces/ \
  --include="*.py" --exclude-dir=".venv" --exclude-dir=".git" \
  | grep -vE "from (core\.|abc|dataclasses|datetime|enum|typing)" \
  | grep -vE "^[^:]+:[0-9]+:import (abc|dataclasses|datetime|enum|typing)"
```

期望:**无输出**(允许的 import:`core.*` 内部模块、标准库 `abc` / `dataclasses` / `datetime` / `enum` / `typing`)。

> `--exclude-dir` 按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 强制要求。虽然此处搜索范围已限定在 `core/` 下不会扫到 `.venv`,但所有静态扫描命令都按规则写,形成肌肉记忆。

### 5. 单元测试全绿

```bash
pytest tests/core/ -v
```

期望:所有 `test_*.py` 通过,**整个 `tests/core/` 测试套件运行 < 5 秒**。

测试用例最低要求(每个测试文件的"必须有"清单):

- `test_domain_source_ref.py`:能用必填字段 `file_path` 构造;选填字段默认为 `None`
- `test_domain_project.py`:能用全部字段构造 `Project`;`ProjectType` 七个取值与契约完全一致;`FileInfo` 默认 `description=None`
- `test_domain_slx_model.py`:`SlxBlock` 三个 `is_*` 默认 `False`;`SlxLine` / `SlxModel` 必填字段构造
- `test_domain_m_file.py`:`MFunction` / `MFile` 必填字段构造
- `test_domain_mat_metadata.py`:`MatVariable` 选填字段默认正确;`MatMetadata` 能构造
- `test_domain_project_graph.py`:`NodeType` 七个取值、`EdgeType` 五个取值与契约一致;能构造完整 `ProjectGraph`
- `test_domain_teaching_unit.py`:能用全部字段构造
- `test_domain_exceptions.py`:每个异常类的 `isinstance` 继承关系正确,例如:
  - `isinstance(ZipBombError("x"), UploadError) is True`
  - `isinstance(ZipBombError("x"), MxaError) is True`
  - `isinstance(LLMAuthError("x"), LLMError) is True`
  - `isinstance(SlxParseError("x"), ParseError) is True`
  - `isinstance(EvidenceMissingError("x"), MxaError) is True`
- `test_interfaces_llm_provider.py`:
  - 直接 `TextProvider()` 抛 `TypeError`(因有未实现的 `@abstractmethod`)
  - 写一个最小 Stub 子类(实现 `chat` 和 `capability`),能正常实例化
  - `ModelCapability` / `LLMMessage` / `LLMResponse` 能用必填字段构造
- `test_interfaces_embedder.py`:直接 `EmbeddingProvider()` 抛 `TypeError`;Stub 子类能实例化
- `test_interfaces_parser.py`:直接 `SlxParser()` / `MParser()` 抛 `TypeError`;Stub 子类能实例化

### 6. lint 和 type-check 全绿

```bash
make lint        # ruff check
make type-check  # mypy core/
```

两者都应 0 error。

### 7. 每文件 ≤ 300 行(04 第 4 节硬规定)

```bash
wc -l core/domain/*.py core/interfaces/*.py | sort -n | tail -5
```

期望:最长的文件远小于 300 行(预计最长 `exceptions.py` 约 80 行)。

### 8. README 已更新

```bash
cat core/domain/README.md
cat core/interfaces/README.md
```

期望:每个文件列出本 Task 新增的模块及其一句话职责描述。

### 9. TASK_INDEX 状态已更新

```bash
grep -n "TASK-101" docs/03_TASK_INDEX.md
```

期望:看到 TASK-101 那一行状态变成 🔍,且底部"当前进度"那个 Week 1 进度条中第一个方块变成 🔍。

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md` 第 1 条,**本 Task 只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件,不动其他任何 docs 核心文档**。

### 10. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 11. PR 元信息

- PR 标题:`TASK-101: core 接口 + domain 数据结构(基础)`
- 分支名:`task/TASK-101-core-domain-and-interfaces`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-10 项**并简述每项做了什么

## 风险与注意点

### 风险 1:Codex 容易把数据结构设计成"含 LLM 调用"

**这是本 Task 最大的雷**。

`ProjectGraph` 和 `TeachingUnit` 是教学理解中间层(`docs/02_ARCHITECTURE_OVERVIEW.md` 第 2 节)的产物,**它们的构建逻辑**(TASK-107)会涉及 LLM 调用,但**本 Task 只建数据结构本身**,不涉及任何构建逻辑、不 import 任何 LLM 模块、不在 dataclass 里写 `__post_init__` 调 LLM。

如果你不确定"这件事算不算业务逻辑",**默认就是算**——本 Task 唯一允许写的代码是:

- `@dataclass` 字段声明
- `class XxxType(Enum)` 成员声明
- `class XxxError(SomeBase): """docstring"""`
- `class XxxProvider(ABC)` + `@abstractmethod` 签名

不写 `__init__` 自定义方法、不写校验逻辑、不写工厂方法、不写转换方法。

### 风险 2:跨模块 import 顺序

`project.py` 引用了 `SlxModel` / `MFile` / `MatMetadata`;`project_graph.py` 引用了 `SourceRef`;`teaching_unit.py` 引用了 `SourceRef`;`parser.py` 引用了 `SlxModel` / `MFile`。

由于这些是单向依赖(`SlxModel` 不反过来引用 `Project`),**直接 import 不会循环**。请用真实 import,不要用字符串前向引用 `list["SlxModel"]`,也不要用 `from __future__ import annotations`(本项目 Python 3.11 内置支持 PEP 604 `|` 联合类型,无需 future import)。

### 风险 3:`docs/04` 和 `docs/02` 异常体系略有出入

`docs/04` 第 10 节"三层异常体系"中写了一个 `QuotaError` 基类,但 `docs/02` 第 4.6 节直接用 `QuotaExhaustedError`(无中间基类)。**本 Task 以 02 为准**(已在上文契约中明示)。如果你认为应该按 04,**停手问 PM**,不要自己拍板。

### 风险 4:Python 版本与类型注解写法

本项目锁 Python 3.11(详见 `pyproject.toml`),**可直接使用** `str | None`、`tuple[int, int]`、`list[X]`、`dict[str, str]` 这些 PEP 604 / PEP 585 写法,**不要用** `Optional[str]` / `Tuple[int, int]` / `List[X]`(老写法)。

### 风险 5:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 排除 `.venv` / `.git`。本 Task 验收清单已经按规则给出命令,直接用。

## 估时

4-6 小时(主要是 11 个测试文件 + 文档,代码本身很简单)。

## 给 Codex 的提示

1. **先建 `source_ref.py`**(无依赖),再建 `slx_model.py` / `m_file.py` / `mat_metadata.py`(无依赖),再建 `project.py`(依赖前三个),再建 `project_graph.py` / `teaching_unit.py`(依赖 `source_ref`),再建 `exceptions.py`(无依赖),最后建 `interfaces/` 三个文件(依赖 domain 数据结构)。按依赖顺序建,避免 import 错乱。

2. **每个文件建完就立刻写对应的测试,跑一遍**`pytest tests/core/test_domain_<name>.py -v`,绿了再写下一个文件。逐文件验证,而不是最后一起跑——避免一次性出十几个错。

3. **测试要简洁**。每个 dataclass 的测试就是 3-5 行:构造一次、断言字段值。不需要参数化测试、不需要 fixture、不需要 mock(本 Task 没有任何外部依赖可以 mock)。`test_domain_exceptions.py` 写得长一点没关系(11 个异常类都要测继承),但每个 `isinstance` 断言也就一行。

4. **测试用例最小骨架示例**(给 `test_domain_source_ref.py`):

   ```python
   from core.domain.source_ref import SourceRef


   def test_source_ref_minimal() -> None:
       ref = SourceRef(file_path="init_params.m")
       assert ref.file_path == "init_params.m"
       assert ref.line_range is None
       assert ref.block_id is None


   def test_source_ref_full() -> None:
       ref = SourceRef(
           file_path="model.slx",
           line_range=(10, 20),
           block_id="SpeedLoop/PID",
           block_name="PID",
           parent_subsystem="SpeedLoop",
           parameter_name="Kp",
       )
       assert ref.parameter_name == "Kp"
   ```

   其他测试照葫芦画瓢。

5. **抽象类测试骨架**(给 `test_interfaces_llm_provider.py`):

   ```python
   import pytest

   from core.interfaces.llm_provider import (
       LLMMessage,
       LLMResponse,
       ModelCapability,
       TextProvider,
   )


   def test_text_provider_is_abstract() -> None:
       with pytest.raises(TypeError):
           TextProvider()  # type: ignore[abstract]


   class _StubProvider(TextProvider):
       def chat(self, messages, json_mode=False, timeout=30.0, max_tokens=None):
           return LLMResponse(text="ok", prompt_tokens=0, completion_tokens=0,
                              model="stub", latency_ms=0)

       def capability(self) -> ModelCapability:
           return ModelCapability(model_name="stub")


   def test_text_provider_stub_works() -> None:
       provider = _StubProvider()
       resp = provider.chat([LLMMessage(role="user", content="hi")])
       assert resp.text == "ok"
       assert provider.capability().model_name == "stub"
   ```

6. **写完后**,在本地依次跑:
   ```bash
   make lint
   make type-check
   make test
   make check
   ```
   全绿后再 push 分支。

7. **commit 拆分建议**(每个 commit 单一职责,不要把测试和实现混在一个 commit):
   - `feat(domain): add SourceRef`
   - `test(domain): add SourceRef unit tests`
   - `feat(domain): add SlxBlock / SlxLine / SlxModel`
   - `test(domain): add slx model unit tests`
   - ……(以此类推)
   - 最后:`docs: mark TASK-101 as in-review in task index`

8. **PR 描述模板**(贴给 PM 时一并给出):

   ```markdown
   ## 关联 Task
   TASK-101

   ## 变更摘要
   建立 core/ 层的全部基础数据结构和抽象接口(11 个文件 + 11 个测试文件 + 2 个 README + 1 个索引状态更新)。
   本 Task 不引入任何业务逻辑、不引入任何第三方依赖、不实现任何 adapter / service。

   ## 主要变更文件
   ...

   ## 验收清单
   [按 Task 文档第 9 节 1-11 项逐条勾选]

   ## 测试结果
   [贴 `make check` 输出]

   ## 风险与注意
   [如果有任何"我做了 Task 文档没明确的细微判断",在这里列出来]
   ```

9. **看见冲突就停手**:本 Task 文档与 docs/01/02/04/05 / decisions 的任何冲突,**停手问 PM**,不要默默偏离。

10. **PR 创建流程**:Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后,**给 PM 两样东西**:
    - PR 标题:`TASK-101: core 接口 + domain 数据结构(基础)`
    - PR 正文(按第 8 条模板)
    
    PM 会在 GitHub 网页手动创建 PR。CI 会自动触发,绿了之后 PM 把 Codex 给的产出 + CI 结果交给架构师 review。
