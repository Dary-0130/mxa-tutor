# TASK-102: .slx XML 解析器(P0/P1/P2 分级)

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第二个 Task,也是项目第一个**真实业务逻辑** Task。

TASK-101 已建好 `SlxModel` / `SlxBlock` / `SlxLine` / `SlxParser` 抽象接口 / `SlxParseError` 异常的"骨架"(纯数据结构与抽象接口,无实现)。本 Task 负责"补肉":**实现 `SlxParser` 接口的具体类,把单个 `.slx` 文件解析成填好的 `SlxModel` dataclass**。

这是 `docs/01_PROJECT_CONSTITUTION.md` 第 4 节"壁垒 1:.slx 文件结构化解析 + 教学理解中间层"的技术起点。`.slx` 本质是 ZIP + XML 容器,我们用 Python 标准库读取 XML 还原 Simulink 模型的真实结构——**通用 ChatGPT 只能看模型截图,我们能解析结构**,这是产品在教学场景的核心技术杠杆。

本 Task 是 TASK-107(ProjectGraph + TeachingUnit 构建器)的关键料源——`ProjectGraph` 的 `BLOCK` / `SUBSYSTEM` / `SIGNAL_FLOWS` 节点和边,全部来自本 Task 输出的 `SlxModel`。如果本 Task 解析不准、关键字段缺失,后续整个"教学理解中间层"会缺料,LLM 又退化成"看截图"。

上下游依赖:

- **上游**:TASK-101(契约源)/ TASK-003(测试集 4 个真实 MATLAB 工程)
- **下游**:
  - TASK-104(工程压缩包安全解压)调用本 Task 解析单个 `.slx`
  - TASK-107(ProjectGraph 构建器)消费本 Task 输出的 `SlxModel`

本 Task 是 `docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"清单中明确列出的核心 Task 之一。**Task 文档完稿后建议 PM 找 AI 二审压力测试一次**,二审通过再交给 Codex 实施。

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并 commit `01413a7`)
- ✅ TASK-002(开发环境 + CI,已合并 commit `64d337d`)
- ✅ TASK-003(4 个真实 MATLAB demo 测试集,已合并 commit `6bbea80`,位于 `tests/fixtures/slx_samples/`)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并 commit `bf50aba`):**直接契约依赖**,本 Task 实现 `core/interfaces/parser.py::SlxParser` 并返回 `core/domain/slx_model.py::SlxModel`

### 必须存在的文件 / 状态

- `main` 分支处于 commit `6bbea80`(TASK-003)或之后
- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/domain/slx_model.py` — `SlxBlock` / `SlxLine` / `SlxModel` dataclass
  - `core/domain/exceptions.py` — `SlxParseError` 异常类
  - `core/interfaces/parser.py` — `SlxParser` 抽象接口
- `tests/fixtures/slx_samples/` 含 4 个 zip:
  - `01_pmsm_foc_c2000.zip`(PMSM 矢量控制 + TI C2000,10 个 .slx)
  - `02_buck_voltage_control.zip`(Buck 变换器电压控制,1 个 .slx)
  - `03_pid_antiwindup.zip`(PID 抗积分饱和,3 个 .slx 变体)
  - `04_lms_noise_cancel.zip`(LMS 自适应噪声消除,2 个 .slx)
  - `README.md`(测试集清单和覆盖意图)
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 3 节 v0.1 不承诺清单 / 第 4 节技术壁垒 / 第 7 节技术架构原则与禁止依赖**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 2 节教学理解中间层 / 第 4.1 节 SlxModel 契约 / 第 6 节技术决策 3 "用 Python 标准库,不依赖 MATLAB"**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 8.1 节"绝对不执行用户上传代码" / 第 8.4 节失败隔离 / 第 10 节异常处理**)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**讲解输出,但 `SlxModel` 是后续讲解的数据源,需理解下游使用场景)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描规范)
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读仓库文件,Task 文档可使用路径引用)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(`docs/` 改动语义)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(⭐ Week 1 新增,**Codex 完工报告必须含 git 三件套**;**改已有文件必须用编辑器或 Python 字节级操作**,禁用 `read_text` / `write_text` / `sed -i`)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源,本 Task 严格依赖其定义的 dataclass 字段)
- `tests/fixtures/slx_samples/README.md`(测试集清单,本 Task 验收依据)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

`adapters/parser/` 下:

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `slx_parser.py` | **主入口**,定义 `SlxParserImpl(SlxParser)`,实现 `parse(slx_file_path: str) -> SlxModel` | 100-200 |
| `_slx_zip.py` | `.slx` ZIP 容器读取工具(列文件、读单个 XML),内部模块 | 50-100 |
| `_slx_xml.py` | XML 解析工具(从 XML 抽 blocks / lines / parameters / position) | 200-300 |
| `_slx_subsystem.py` | 子系统层级遍历与 SID 解析 | 100-200 |
| `_slx_config.py` | solver config / mask / library link / model reference 识别(P1 内容) | 100-150 |

下划线前缀模块为 `slx_parser.py` 的内部协作模块,**不暴露**到 `adapters/parser/__init__.py`(只导出 `SlxParserImpl`)。

`tests/adapters/parser/` 下(若 `tests/adapters/` / `tests/adapters/parser/` 不存在则创建):

| 文件 | 职责 |
|------|------|
| `__init__.py` × 2 | 模块标记(空文件) |
| `conftest.py` | 解压 4 个 zip 到 `tmp_path_factory`(session scope),返回 `dict[str, list[Path]]`(工程名 → 该工程内 .slx 路径列表) |
| `test_slx_parser_unit.py` | 用**内嵌**小型 XML 字符串测试解析单元(解析 1 个 block / 1 条 line / 嵌套 1 层 subsystem),目标:运行 < 2 秒 |
| `test_slx_parser_real_p0.py` | **P0 验收**,跑在 4 个真实工程的全部 .slx 上 |
| `test_slx_parser_real_p1.py` | **P1 验收**,跑在 4 个真实工程的全部 .slx 上 |
| `test_slx_parser_errors.py` | 错误处理(ZIP 损坏 / 缺关键 XML / 非 OOXML 容器 / 单 block 解析失败但整体继续) |

### 修改文件

- **`adapters/parser/README.md`** — TASK-001 占位 README,本 Task 更新内容:列出新增的 5 个模块各自的一句话职责。
- **`docs/03_TASK_INDEX.md`** — 改两处(均按决策 08 用字节级 Python 操作,详见"风险与注意点"小节):
  1. 把 TASK-102 行状态从 🔲 改为 🔍,Week 1 进度条 1/7 → 2/7(本 Task 自身的常规收尾)
  2. 把 TASK-003 行状态从 🔲 改为 ✅,Week 0 进度条 1/4 → 2/4(**顺手补救** PR #8 合并时未走 🔲 → 🔍 → ✅ 流程的索引遗留,本 Task 仅限这两处字面替换)

### 不动文件

- `core/domain/*.py` 和 `core/interfaces/*.py`(TASK-101 已建,**契约不许动**;如发现需要调整,**停手问 PM**,走宪法修订流程,不能在本 Task 顺带改)
- `requirements.txt` / `requirements-dev.txt`(本 Task **不引入任何新依赖**)
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml` / `scripts/check_repo_hygiene.sh`(TASK-002 已配,本 Task 不调)
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(详见决策 07)
- `tests/fixtures/slx_samples/*.zip` 和 `tests/fixtures/slx_samples/README.md`(TASK-003 已建,**只读**)
- `core/prompts/` / `eval/` / `app/` / `api/` / `features/` / `web/` 下任何文件
- 其他 Task 的代码与测试

### 新增依赖

**无**。本 Task 全部使用 Python 标准库:`zipfile` / `xml.etree.ElementTree` / `pathlib` / `io` / `re`(若识别 workspace 变量占位符用)。

### 新增配置项

**无**。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-102-slx-xml-parser`
- [ ] **依赖结构理解**:阅读 4 个测试工程的 `.slx` 内部结构(见"接口契约"小节"`.slx` 文件内部 XML 结构指引"),手动 `unzip -l tests/fixtures/slx_samples/04_lms_noise_cancel.zip` 等命令先确认你看到的文件结构与本文档描述一致
- [ ] **P0 实现**(`adapters/parser/slx_parser.py` 主入口 + `_slx_zip.py` + `_slx_xml.py` + `_slx_subsystem.py`):
  - [ ] 接受单个 `.slx` 文件路径,返回 `SlxModel` dataclass
  - [ ] 失败时抛 `SlxParseError`,错误消息**中文**(详见"接口契约"小节"错误消息中文化清单")
  - [ ] `SlxModel.name` 填充(从 `metadata/coreProperties.xml` 或 `simulink/blockdiagram.xml` 根元素提取)
  - [ ] `SlxModel.blocks` 填充:每个 block 含 `block_id` / `name` / `block_type` / `parameters`(原始字典)/ `position` / `parent_subsystem`,其中 `is_masked` / `is_library_link` / `is_model_reference` 在 P0 可全默认 `False`,P1 再补
  - [ ] `SlxModel.lines` 填充:每条 line 含 `from_block` / `from_port` / `to_block` / `to_port`
  - [ ] `SlxModel.subsystems` 填充:`dict[subsystem_name, list[block_id]]`,递归遍历嵌套子系统
  - [ ] `SlxModel.solver_config` P0 阶段允许填空字典 `{}`(P1 再补)
  - [ ] `SlxModel.parse_warnings` 填充:**任何**解析中遇到的可恢复异常(单 block 解析失败、未知 XML 元素、字段缺失等)累积为中文 warning 字符串
- [ ] **P1 实现**(`adapters/parser/_slx_config.py`):
  - [ ] `solver_config` 从 `simulink/configSet0.xml` 提取关键键值(`StartTime` / `StopTime` / `Solver` / `SolverType` / `FixedStep` 等,**有就填,没有就跳**,不要硬要求 5 个键齐全)
  - [ ] `is_masked = True` 识别:block 的 XML 子元素含 `<Mask>` 或 `<MaskType>` 标签
  - [ ] `is_library_link = True` 识别:block 的 XML 属性 / 子元素含 `<P Name="SourceBlock">` 且引用 library 路径
  - [ ] `is_model_reference = True` 识别:`block_type == "ModelReference"` 或 block 含 `<P Name="ModelName">`
  - [ ] workspace 变量引用名称识别:在 `parameters` 字典里,值中出现的 `[A-Za-z_][A-Za-z0-9_]*` 形式标识符(非数字字面量)收集到 warnings 或独立字段(P1 阶段可以放进 `parse_warnings` 中,**不修改 `SlxModel` 字段定义**)
- [ ] **P2 范围明确不做**(详见"不做"小节)
- [ ] **失败隔离**(`docs/04_ENGINEERING_STANDARDS.md` 第 8.4 节):
  - [ ] 单个 block 解析失败 → 加 `parse_warnings`,**继续**处理其他 block
  - [ ] 单个 subsystem XML 文件解析失败 → 加 `parse_warnings`,**继续**处理其他 subsystem
  - [ ] 整个 ZIP 损坏 / 不是 ZIP / 关键文件 `simulink/blockdiagram.xml` 缺失 → 抛 `SlxParseError`(此时无法继续)
- [ ] **单元测试**(`tests/adapters/parser/test_slx_parser_unit.py`):
  - [ ] 用内嵌小型 XML 字符串构造**最小可解析输入**(1 个 block,无 subsystem,无 line),验证 `SlxModel.blocks` 长度 = 1、字段填充正确
  - [ ] 验证 1 条 line 的 from/to/port 正确提取
  - [ ] 验证嵌套 1 层 subsystem 的 `subsystems` 字典结构
  - [ ] 验证单 block 解析失败时不影响其他 block(注入一个故意残缺的 block XML)
  - [ ] 验证 `solver_config` 从合成 `configSet0.xml` 字符串正确提取
- [ ] **P0 真实工程测试**(`tests/adapters/parser/test_slx_parser_real_p0.py`):**4 个工程的全部 .slx 都必须 P0 通过**,具体断言清单见"验收标准"小节"P0 真实工程断言矩阵"
- [ ] **P1 真实工程测试**(`tests/adapters/parser/test_slx_parser_real_p1.py`):**4 个工程中至少 3 个 P1 通过**,具体断言清单见"验收标准"小节"P1 真实工程断言矩阵"
- [ ] **错误处理测试**(`tests/adapters/parser/test_slx_parser_errors.py`):
  - [ ] 输入非 ZIP 文件(如纯文本 .slx)→ 抛 `SlxParseError`
  - [ ] 输入有效 ZIP 但缺 `simulink/blockdiagram.xml` → 抛 `SlxParseError`
  - [ ] 输入有效 ZIP + 有 `blockdiagram.xml` 但 XML 格式损坏 → 抛 `SlxParseError`
  - [ ] 错误消息为中文
- [ ] **`adapters/parser/README.md` 更新**(列出 5 个新模块各自一句话职责)
- [ ] **本地全检通过**:`make check` 全绿(lint / type-check / pytest / hygiene)
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-102 状态从 🔲 改为 🔍,Week 1 进度条相应位置 ⬜ 改为 🔍
  - **顺手**把 TASK-003 状态从 🔲 改为 ✅,Week 0 进度条 1/4 → 2/4
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见"风险与注意点"
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-102 as in-review and TASK-003 as done in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status`(working tree clean)/ `git log --oneline main..HEAD`(完整 commit 列表)/ `git push`(推送成功输出)
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

### v0.1 P2 范围明确不做(`docs/01_PROJECT_CONSTITUTION.md` 第 3 节)

- ❌ **Stateflow 内部语义**:遇到 Stateflow chart,只填 `block_type == "SubSystem"` 或 `"Chart"`,**不**解析状态机内部
- ❌ **masked subsystem 内部语义还原**:只标记 `is_masked = True`,**不**解析 mask 内部参数绑定与执行逻辑
- ❌ **library link 实际展开**:只标记 `is_library_link = True`,**不**加载 `.slx` 库文件还原 library 内部 blocks
- ❌ **model reference 跨模型展开**:只标记 `is_model_reference = True`,**不**加载被引用的 `.slx`
- ❌ **自定义 S-Function 内部行为**:遇到 `S-Function` block 只记录类型和参数,**不**解析 `.c` / `.cpp` / `.mexw64` 等附属文件
- ❌ **`.ssc` Simscape 自定义元件内部解析**:工程 2(Buck)含一个 `.ssc` 文件,本 Task **不**解析其内容,**仅在** `_slx_xml.py` 遇到引用它的 block 时,识别 `block_type == "Simscape.<Name>"` 即可
- ❌ **运行 / 仿真用户工程**(`docs/04_ENGINEERING_STANDARDS.md` 第 8.1 节硬约束):本 Task 严格静态解析,**不**调 `subprocess` / `exec` / `eval` / MATLAB 等任何代码执行路径
- ❌ **`.mat` 文件读取**:即使 `.slx` 引用了 workspace 中由 `.mat` 加载的变量,本 Task **不**读 `.mat` 内容(那是 Phase 2 范围)
- ❌ **`.m` 文件解析**:即使 `.slx` 引用了 `.m` 函数,本 Task **不**解析 `.m`(那是 TASK-103)
- ❌ **跨 .slx 文件分析**:本 Task 一次只处理**单个** `.slx`;工程 1 PMSM 含 10 个 .slx,测试时**逐个调用** `parse()`,**不**做跨文件关联(关联是 TASK-105 / TASK-107 的事)

### 工程范围排除

- ❌ **不实现 `core/interfaces/parser.py::MParser`**(那是 TASK-103)
- ❌ **不写 `adapters/parser/m_parser.py` / `mat_reader.py` / `prj_parser.py` / `zip_extractor.py`**(分别是 TASK-103 / 暂未列 / TASK-104 / TASK-104)
- ❌ **不引入第三方依赖**(包括但不限于 `lxml` / `defusedxml` / `slxutils` 等;`xml.etree.ElementTree` 标准库够用)
- ❌ **不写 ProjectGraph 构建逻辑**(那是 TASK-107)
- ❌ **不写 LLM 调用**(本 Task 是纯结构化解析,无任何 LLM 介入,`docs/02_ARCHITECTURE_OVERVIEW.md` 第 2 节"教学理解中间层"原则)
- ❌ **不写性能基准测试**(只跑功能正确性测试;若单文件解析 > 10 秒,在 `parse_warnings` 记一笔,**不**作为本 Task 验收硬指标)
- ❌ **不修改 `core/domain/slx_model.py` 字段定义**(TASK-101 契约,改了停手问 PM)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md`)

---

## 接口契约

### 1. `SlxParser` 接口与 `SlxModel` 契约(TASK-101 已建,不重新内联)

本 Task 必须实现 `core/interfaces/parser.py::SlxParser` 抽象接口,签名:

```python
class SlxParser(ABC):
    @abstractmethod
    def parse(self, slx_file_path: str) -> SlxModel: ...
```

返回 `core/domain/slx_model.py::SlxModel`,字段定义如下(**完整契约请从 `core/domain/slx_model.py` 直接读**,**不许修改字段名 / 类型 / 默认值**):

- `SlxModel`:`file_path: str` / `name: str` / `blocks: list[SlxBlock]` / `lines: list[SlxLine]` / `subsystems: dict[str, list[str]]` / `solver_config: dict[str, str]` / `parse_warnings: list[str]`
- `SlxBlock`:`block_id: str` / `name: str` / `block_type: str` / `parameters: dict[str, str]` / `position: tuple[int, int, int, int]` / `parent_subsystem: str | None` / `is_masked: bool = False` / `is_library_link: bool = False` / `is_model_reference: bool = False`
- `SlxLine`:`from_block: str` / `from_port: int` / `to_block: str` / `to_port: int`

异常用 `core/domain/exceptions.py::SlxParseError`(继承 `ParseError` 继承 `MxaError`)。

### 2. 实现类签名

`adapters/parser/slx_parser.py`:

```python
from pathlib import Path

from core.domain.exceptions import SlxParseError
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel
from core.interfaces.parser import SlxParser


class SlxParserImpl(SlxParser):
    """.slx XML 解析器具体实现(P0/P1 分级)。

    输入单个 .slx 文件路径,解压 ZIP 容器并解析内部 XML,
    返回填好的 SlxModel dataclass。

    P0 字段(必填,不达标本 Task 不验收):
        name / blocks / lines / subsystems / parse_warnings
    P1 字段(尽量填,4 个测试工程至少 3 个填充正确):
        solver_config, blocks 中的 is_masked / is_library_link / is_model_reference
    P2 范围(本 Task 不承诺):见 Task 文档"不做"小节
    """

    def parse(self, slx_file_path: str) -> SlxModel:
        """解析单个 .slx 文件。

        Args:
            slx_file_path: .slx 文件绝对或相对路径。

        Returns:
            填好的 SlxModel。

        Raises:
            SlxParseError: 文件不存在 / 不是有效 ZIP / 缺关键 XML / XML 损坏。
        """
        ...
```

Codex 在内部模块(`_slx_zip.py` / `_slx_xml.py` / `_slx_subsystem.py` / `_slx_config.py`)的函数签名自由设计,但**对外只暴露 `SlxParserImpl`**(`adapters/parser/__init__.py` 中只 `from adapters.parser.slx_parser import SlxParserImpl`,不导出下划线模块)。

### 3. `.slx` 文件内部 XML 结构指引

`.slx` 是 OOXML 容器(ZIP + 一组 XML)。MATLAB R2014b 起的默认模型格式。**4 个测试工程全部由 MATLAB R2026a 导出**,内部结构遵循 OOXML + Simulink 内部约定。

#### 3.1 典型 ZIP 内文件结构

```
project_name.slx (ZIP 容器)
├── [Content_Types].xml                # OOXML 必备(声明各 part MIME)
├── _rels/.rels                        # OOXML 根关系
├── metadata/
│   ├── coreProperties.xml             # 模型元信息(标题、作者、创建时间)
│   └── thumbnail.png                  # 模型缩略图(本 Task 不读)
└── simulink/
    ├── _rels/                         # 各 XML 的关系文件
    │   ├── blockdiagram.xml.rels
    │   └── ...
    ├── blockdiagram.xml               # ⭐ 主模型结构(顶层 blocks + lines)
    ├── systems/                       # 子系统目录
    │   ├── system_root.xml            # 顶层 system(等价于 blockdiagram.xml,或单独存在)
    │   ├── system_1.xml               # 第 1 个 subsystem 内部
    │   ├── system_2.xml               # 第 2 个 subsystem 内部
    │   └── ...
    ├── configSet0.xml                 # ⭐ 仿真配置(solver / step / tolerance)
    ├── modeling_metadata.xml          # 建模元数据(本 Task 不读)
    └── ...                            # 其他可选 XML
```

**关键文件**:

- **`simulink/blockdiagram.xml`**:本 Task 的**核心输入**,含顶层 model 的全部 blocks 和 lines。
- **`simulink/systems/system_*.xml`**:每个 subsystem 一个 XML,通过 SID(Simulink ID)或文件名关联回 `blockdiagram.xml` 中对应的 SubSystem block。
- **`simulink/configSet0.xml`**:P1 阶段读取 solver 配置。
- **`metadata/coreProperties.xml`**:可选用作 `SlxModel.name` 来源(更可靠的来源是 `blockdiagram.xml` 根元素的 `Name` 属性 / 子元素)。

#### 3.2 `blockdiagram.xml` 节点结构(R2026a)

典型骨架(下面是**示意性**结构,真实文件中可能多一些标签;Codex 应宽容解析,只取关心的字段):

```xml
<?xml version="1.0" encoding="utf-8"?>
<ModelInformation>
  <Model Name="pmsm_foc" ... >
    <P Name="Name">pmsm_foc</P>
    <System>
      <Block BlockType="Sum" Name="Sum1" SID="2">
        <P Name="Position">[100, 100, 130, 130]</P>
        <P Name="Inputs">|++</P>
        <Port Type="input" Number="1" />
        <Port Type="output" Number="1" />
      </Block>
      <Block BlockType="Gain" Name="Kp" SID="3">
        <P Name="Position">[200, 100, 230, 130]</P>
        <P Name="Gain">Kp_speed</P>     <!-- workspace 变量引用 -->
      </Block>
      <Block BlockType="SubSystem" Name="SpeedLoop" SID="10">
        <P Name="Position">[300, 80, 400, 150]</P>
        <System Ref="system_1" />        <!-- 引用 systems/system_1.xml -->
      </Block>
      <Line>
        <P Name="Src">2#out:1</P>         <!-- SID#port_type:port_number -->
        <P Name="Dst">3#in:1</P>
      </Line>
      <Line>
        <P Name="Src">3#out:1</P>
        <Branch>
          <P Name="Dst">10#in:1</P>
        </Branch>
        <Branch>
          <P Name="Dst">5#in:2</P>
        </Branch>
      </Line>
    </System>
  </Model>
</ModelInformation>
```

**注意点**:

- 根元素名可能是 `ModelInformation` / `Model` / 其他,Codex 用 `tree.getroot()` 后递归找含 `<Block>` / `<Line>` 子元素的层级,**不**硬编码根元素名
- `<P Name="...">value</P>` 是 Simulink XML 表达"属性"的标准方式,Codex 应封装一个 `_get_p_value(elem, name)` 辅助函数,失败返回默认值
- `<Block>` 的 `BlockType` 是属性而不是子元素 `<P>`,这是 Simulink 内部约定,但**也可能**部分版本下 `BlockType` 跑到 `<P>` 里,Codex 应两种都试
- `<Port>` 子元素描述端口编号,P0 阶段可以**不**逐个解析端口(因为 Line 的 Src/Dst 已经含 port 信息),仅在端口数与 Line 引用对不上时,作为 warning 提示

#### 3.3 Line 的 `Src` / `Dst` 字符串格式

格式:`<SID>#<port_type>:<port_number>`,例如:

- `2#out:1` 表示 SID=2 的 block 的第 1 个输出端口
- `10#in:1` 表示 SID=10 的 block 的第 1 个输入端口

Codex 应**用 SID 而非 Name 来作为 `SlxLine.from_block` / `to_block`**(SID 全模型唯一,Name 在不同 subsystem 下可能重名)。因此 `SlxLine` 字段实际填的是 SID 字符串。

`SlxBlock.block_id` 也应使用 SID(全模型唯一),`SlxBlock.name` 保留人类可读名(可能重名)。

#### 3.4 子系统层级关系

`<Block BlockType="SubSystem">` 内部含 `<System Ref="system_1" />` 或直接含 `<System>...</System>` 内联子结构。

两种情况都要处理:

- **外联引用**:`<System Ref="system_1" />` 表示子系统内部在 `simulink/systems/system_1.xml`,Codex 应打开该文件继续解析
- **内联结构**:`<System>` 直接含 `<Block>` / `<Line>` 子元素,Codex 递归当前 XML

最终 `SlxModel.subsystems` 填充为 `dict[subsystem_name_or_sid, list[block_sid]]`,key 用 subsystem 的 `Name` 属性更易读,但若 Name 缺失退回到 SID。

#### 3.5 `configSet0.xml` 结构(P1)

骨架:

```xml
<ConfigSet Name="Configuration">
  <Array PropName="Components">
    <Object Class="Simulink.SolverCC">
      <P Name="StartTime">0.0</P>
      <P Name="StopTime">10.0</P>
      <P Name="SolverType">Variable-step</P>
      <P Name="Solver">ode45</P>
      <P Name="FixedStep">auto</P>
    </Object>
    <Object Class="Simulink.DataIOCC">
      ...
    </Object>
  </Array>
</ConfigSet>
```

`SlxModel.solver_config` 填 `dict[str, str]`,Codex 可填 5 个关键键(`StartTime` / `StopTime` / `SolverType` / `Solver` / `FixedStep`),**有就填,没有就跳**,不抛异常。

#### 3.6 `coreProperties.xml`(可选)

```xml
<cp:coreProperties xmlns:cp="...">
  <dc:title>pmsm_foc</dc:title>
  <dc:creator>...</dc:creator>
</cp:coreProperties>
```

带命名空间,Codex 解析时需要用 `{命名空间URL}tag` 形式。**推荐 fallback 策略**:`SlxModel.name` 优先从 `blockdiagram.xml` 的 `<Model Name="...">` 取,取不到再 fallback 到 `coreProperties.xml` 的 `dc:title`,再取不到 fallback 到文件名(去掉 .slx 扩展名)。

### 4. 错误消息中文化清单

`SlxParseError` 抛出时**消息必须为中文**(对齐 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 9 节"SlxParseError → Simulink 模型解析失败,可能版本过老或损坏"),建议消息模板:

| 触发场景 | 错误消息 |
|---------|---------|
| 文件不存在 | `f"找不到 .slx 文件:{slx_file_path}"` |
| 文件不是 ZIP | `f".slx 文件损坏:不是有效的 ZIP 容器({slx_file_path})"` |
| ZIP 内缺关键 XML | `f".slx 内部结构异常:未找到 simulink/blockdiagram.xml,可能不是有效的 Simulink 模型"` |
| XML 解析失败 | `f"Simulink 模型 XML 损坏,无法解析:{xml_inner_error}"` |
| MATLAB 版本不兼容 | (本 Task 不主动检测版本)按上面"XML 解析失败"或"内部结构异常"统一处理 |

`parse_warnings`(可恢复,**不**抛异常)的中文模板:

| 触发场景 | warning 消息 |
|---------|-------------|
| 单 block 解析失败 | `f"block 解析失败,已跳过:SID={sid}, 原因={reason}"` |
| 单 subsystem XML 缺失 | `f"子系统 XML 文件缺失,已跳过:{system_ref}"` |
| Line 端口信息异常 | `f"line 端口格式异常,已跳过:src={src}, dst={dst}"` |
| 未知 BlockType | `f"未识别的 BlockType,按通用处理:{block_type}"` |
| 字段 `BlockType` 缺失 | `f"block 缺少 BlockType 属性,SID={sid},标记为 Unknown"` |
| `coreProperties.xml` 缺失 | `f"未找到 metadata/coreProperties.xml,model 名从 blockdiagram 提取"` |
| solver_config 解析失败 | `f"solver 配置解析失败,已跳过:{reason}"` |

---

## 验收标准

> **所有命令在 Git Bash + 已激活的 `.venv` 内,在仓库根目录(`F:\mxa-tutor`)执行。**
> Codex 在 PR 描述里逐条勾选并贴每条命令的输出。
> 静态扫描类命令一律按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。

### 1. 文件全部创建

```bash
ls adapters/parser/slx_parser.py adapters/parser/_slx_zip.py \
   adapters/parser/_slx_xml.py adapters/parser/_slx_subsystem.py \
   adapters/parser/_slx_config.py \
   tests/adapters/parser/__init__.py tests/adapters/parser/conftest.py \
   tests/adapters/parser/test_slx_parser_unit.py \
   tests/adapters/parser/test_slx_parser_real_p0.py \
   tests/adapters/parser/test_slx_parser_real_p1.py \
   tests/adapters/parser/test_slx_parser_errors.py
```

12 个文件全部存在,无 `No such file` 报错。

### 2. 不应被创建的文件确实没创建

```bash
ls adapters/parser/m_parser.py adapters/parser/mat_reader.py \
   adapters/parser/prj_parser.py adapters/parser/zip_extractor.py 2>&1
```

期望:全部 `No such file or directory`(那些是后续 Task 的事)。

### 3. 没有引入新依赖

```bash
git fetch origin main
git diff origin/main..HEAD --name-only -- requirements.txt requirements-dev.txt pyproject.toml
```

期望:**无输出**(本 Task 完全不动这三个文件)。

### 4. adapters/parser/ 内部不 import 任何第三方库

```bash
grep -rn "^import\|^from" adapters/parser/ \
  --include="*.py" --exclude-dir=".venv" --exclude-dir=".git" \
  | grep -vE "(^[^:]+:[0-9]+:)(import|from) (core\.|adapters\.parser\.|abc|dataclasses|datetime|enum|typing|pathlib|io|zipfile|xml\.etree\.|re|os|sys)"
```

期望:**无输出**(允许的 import:`core.*` / `adapters.parser.*` 内部模块、Python 标准库 `abc` / `dataclasses` / `datetime` / `enum` / `typing` / `pathlib` / `io` / `zipfile` / `xml.etree.*` / `re` / `os` / `sys`)。

### 5. core/ 完全没动

```bash
git diff origin/main..HEAD --name-only -- core/
```

期望:**无输出**(本 Task 不动 core/)。

### 6. 单元测试全绿

```bash
pytest tests/adapters/parser/test_slx_parser_unit.py tests/adapters/parser/test_slx_parser_errors.py -v
```

期望:所有 `test_*` 通过,运行 < 3 秒。

### 7. P0 真实工程断言矩阵(**4 个工程全部通过**)

```bash
pytest tests/adapters/parser/test_slx_parser_real_p0.py -v
```

**所有测试 PASSED**,具体断言清单:

#### 工程 1(`01_pmsm_foc_c2000.zip`,10 个 `.slx`)
- [ ] 10 个 .slx 全部能 parse 成功(不抛 `SlxParseError`)
- [ ] 每个 .slx 的 `SlxModel.name` 非空
- [ ] 每个 .slx 的 `SlxModel.blocks` 长度 ≥ 1
- [ ] 至少 5 个 .slx 的 `SlxModel.subsystems` 含 ≥ 1 个子系统(PMSM 工程子系统密集)
- [ ] 至少 1 个 .slx 能识别出含 `"Inverter"` / `"Motor"` / `"FOC"` 关键字的 block name(任意大小写)

#### 工程 2(`02_buck_voltage_control.zip`,1 个 `.slx`)
- [ ] `BuckVoltageControl.slx`(或类似名)能 parse 成功
- [ ] `SlxModel.blocks` 长度 ≥ 5
- [ ] 至少 1 个 block 的 `block_type` 含 `"PID"` 或 `"PI"` 字样(Buck 通常有 PI 控制器)
- [ ] 至少 1 个 block 的 `block_type` 以 `"Simscape"` / `"SimscapeElectrical"` 开头(电力电子 Simscape 元件),或在 `parse_warnings` 中明确记录"未识别的 Simscape 元件"

#### 工程 3(`03_pid_antiwindup.zip`,3 个 `.slx` 变体)
- [ ] 3 个 .slx 全部能 parse 成功
- [ ] 每个 .slx 都能识别出 `block_type == "PID Controller"` 或类似(`"PIDController"` / `"DiscretePIDController"`)的 block
- [ ] 至少 2 个 .slx 能识别出 `block_type == "Saturation"` 的 block(抗饱和工程的核心)

#### 工程 4(`04_lms_noise_cancel.zip`,2 个 `.slx`)
- [ ] 浮点版 + 定点版 2 个 .slx 全部能 parse 成功
- [ ] 至少 1 个 .slx 能识别出 `block_type` 含 `"LMS"` 字样的 block 或 `block.name` 含 `"LMS"` 的 block
- [ ] 至少 1 个 .slx 能识别出 `block.name` 含 `"Spectrum"` / `"Scope"` 字样的可视化 block

**P0 验收 = 4 / 4 工程全部通过上述所有断言。任一工程未通过,本 Task 打回返工。**

### 8. P1 真实工程断言矩阵(**至少 3 / 4 工程通过**)

```bash
pytest tests/adapters/parser/test_slx_parser_real_p1.py -v
```

**至少 3 个工程 PASSED**(允许 1 个工程的 P1 断言被 `pytest.skip` 或 `xfail`,但必须**在测试中显式标记原因**)。

每个工程的 P1 断言清单:

#### 通用 P1(每个工程)
- [ ] `SlxModel.solver_config` 字典非空,**至少含 `Solver` 或 `SolverType` 键之一**
- [ ] 该工程至少 1 个 .slx 的 `solver_config["StopTime"]` 字段非空字符串(常规仿真模型都设了仿真时长)

#### 工程 1(PMSM)
- [ ] 至少 1 个 .slx 的某 block `is_masked == True`(PMSM FOC 工程子系统多,通常有 mask)
- [ ] 或 至少 1 个 .slx 的某 block `is_library_link == True`(C2000 嵌入式工程常引用 library)

#### 工程 2(Buck)
- [ ] `BuckVoltageControl.slx` 的 `solver_config` 含 `StopTime`(电力电子模型常用变步长 + 显式 StopTime)

#### 工程 3(PID)
- [ ] 3 个 .slx 的 PID Controller block 的 `parameters` 字典里能取到 `P` / `I` / `D` 中至少 1 个键(可能值是字面数字也可能是 workspace 变量名)

#### 工程 4(LMS)
- [ ] 定点版 .slx 的 `parse_warnings` 中**不出现** "崩溃" / "无法解析" 等致命字样(定点 block 不在 P0 必识别清单,但解析过程不能崩)

**P1 验收 = 至少 3 / 4 工程通过。若仅 2 / 4 通过,Codex 应在 PR 描述里说明哪 2 个工程的哪些 P1 断言无法通过、原因是什么(MATLAB 版本差异 / XML 字段格式异常 / 其他)。**

### 9. 错误处理测试全绿

```bash
pytest tests/adapters/parser/test_slx_parser_errors.py -v
```

期望:全部通过,包括以下场景:

- [ ] 输入文件不存在 → `SlxParseError`,消息含 `"找不到 .slx 文件"`
- [ ] 输入文件是纯文本(非 ZIP)→ `SlxParseError`,消息含 `"不是有效的 ZIP 容器"`
- [ ] 输入文件是有效 ZIP 但内部缺 `simulink/blockdiagram.xml` → `SlxParseError`,消息含 `"未找到 simulink/blockdiagram.xml"`
- [ ] 输入文件是有效 ZIP 且有 `blockdiagram.xml` 但 XML 内容损坏 → `SlxParseError`,消息含 `"XML 损坏"` 或类似
- [ ] 错误消息为中文(不是英文堆栈)

### 10. lint / type-check / hygiene 全绿

```bash
make lint
make type-check
make hygiene
```

三个命令都应 0 error。

### 11. 每文件 ≤ 300 行

```bash
wc -l adapters/parser/*.py tests/adapters/parser/*.py | sort -n | tail -10
```

期望:最长的文件 ≤ 300 行(`_slx_xml.py` 可能最长,预计 ~250 行)。**若某文件超 300 行,Codex 必须拆分**(参考"输出"小节的 5 文件结构)。

### 12. `adapters/parser/README.md` 已更新

```bash
cat adapters/parser/README.md
```

期望:列出本 Task 新增的 5 个模块及其一句话职责,以及 `SlxParserImpl` 的对外用法 1-2 行示例。

### 13. `docs/03_TASK_INDEX.md` 状态已更新

```bash
grep -n "TASK-102" docs/03_TASK_INDEX.md
grep -n "TASK-003" docs/03_TASK_INDEX.md
grep -n "Week 0:" docs/03_TASK_INDEX.md
grep -n "Week 1:" docs/03_TASK_INDEX.md
```

期望:

- 看到 TASK-102 行状态为 🔍
- 看到 TASK-003 行状态为 ✅
- Week 0 进度条显示 `2/4`,Week 1 进度条显示 `2/7`(本 Task 推到 🔍 后)

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md`,本 Task 只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件。**改文件方式必须按决策 08 用字节级 Python 操作或编辑器手改,禁用 `read_text` / `write_text` / `sed -i`**。

### 14. 一键全检

```bash
make check
```

应输出 `All checks passed!`。

### 15. git 三件套(决策 08 硬要求)

Codex 在完工报告里**必须**附带以下三条命令的完整输出:

```bash
git status                              # 期望: working tree clean
git log --oneline main..HEAD            # 期望: 本 Task 的全部 commit 列表,非空
git push                                # 期望: 分支已推送到 origin/task/TASK-102-slx-xml-parser
```

不附 = 没完工,PM 退回让 Codex 补。

### 16. PR 元信息

- PR 标题:`TASK-102: .slx XML 解析器(P0/P1/P2 分级)`
- 分支名:`task/TASK-102-slx-xml-parser`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-15 项**并简述每项做了什么

---

## 风险与注意点

### 风险 1:`docs/03_TASK_INDEX.md` 改文件方式(决策 08 重灾区)

TASK-101 收尾时 PM 用 `pathlib.Path.read_text() + write_text()` 改 03 索引,**整个文件 CRLF 行尾被规范化成 LF**,git diff 显示 700+ 行变化,PR 不可 review,后果是 `git reset --soft HEAD~1` + 字节级重做,**多花 20 分钟**。

**本 Task 改 `docs/03_TASK_INDEX.md` 时必须用以下方式之一**(决策 08 第 2 条):

**方式 A:VS Code / Notepad++ 等编辑器手改**(注意编辑器要保留原文件行尾)。

**方式 B:Python 字节级操作**(推荐,可脚本化):

```python
# 在 Codex 切的分支上执行
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# 改动 1:TASK-102 状态 🔲 → 🔍
old = '| TASK-102 | .slx XML 解析器(P0/P1/P2 分级) | 🔲 | Codex | 101 + 测试集 |'.encode('utf-8')
new = '| TASK-102 | .slx XML 解析器(P0/P1/P2 分级) | 🔍 | Codex | 101 + 测试集 |'.encode('utf-8')
assert old in data, 'TASK-102 row not found'
data = data.replace(old, new)

# 改动 2:TASK-003 状态 🔲 → ✅(顺手补救)
old = '| TASK-003 | 收集 10 个真实 Simulink 工程做测试集 | 🔲 | PM | 无 |'.encode('utf-8')
new = '| TASK-003 | 收集 10 个真实 Simulink 工程做测试集 | ✅ | PM | 无 |'.encode('utf-8')
assert old in data, 'TASK-003 row not found'
data = data.replace(old, new)

# 改动 3:Week 0 进度条 1/4 → 2/4
# (具体字面值由 Codex 实际查看当前 03 索引底部进度条后构造,
#  本文档不内联当前进度条的精确字符串,因为 TASK-101 收尾时已经改过一轮,
#  Codex 实际编辑前 git log + grep 一下 "Week 0:" 行的当前状态再构造 old/new)

# 改动 4:Week 1 进度条 1/7 → 2/7
# (同上)

p.write_bytes(data)
print("OK")
```

**禁止**:

- ❌ `path.read_text(encoding='utf-8') + path.write_text(...)`(行尾会被规范化)
- ❌ `open(path, 'w').write(...)`(默认文本模式)
- ❌ `sed -i 's/.../.../g' docs/03_TASK_INDEX.md`(Git Bash 下中文 + emoji 处理不稳定,**实战已踩过坑**)

改完后 Codex 必须跑:

```bash
git diff docs/03_TASK_INDEX.md
```

确认 diff 只显示 4 行左右改动(2 个状态符 + 2 个进度条数字),**不应**出现整文件红绿。若 diff 显示几百行变化,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 手改**。

### 风险 2:Codex 漏 git 操作(决策 08 重灾区)

TASK-101 实施时 Codex 写完代码、跑完 `make check`,**完全跳过 `git add` / `git commit` / `git push`**,PM 准备建 PR 时 `git status` 才发现 22 个文件 Untracked。**多花 30 分钟补救**。

本 Task 涉及 12 个新文件 + 2 个修改文件,**Codex 必须在完工报告里附带 git 三件套输出**(`git status` working tree clean / `git log --oneline main..HEAD` 完整 commit 列表 / `git push` 推送成功)。不附 = 没完工。

### 风险 3:XML 命名空间陷阱

`.slx` 内部 XML(`blockdiagram.xml` / `system_*.xml` / `configSet0.xml`)通常**不带**命名空间,可以直接 `tree.findall('.//Block')`。

但 `metadata/coreProperties.xml` 带 OOXML 标准命名空间:

```xml
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>...</dc:title>
</cp:coreProperties>
```

读取时需要:

```python
ns = {
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    'dc': 'http://purl.org/dc/elements/1.1/',
}
title = root.find('dc:title', ns)
```

或者**更稳妥**:用 `iterparse` 剥掉命名空间前缀后再处理。Codex 选哪种实现均可,但 `coreProperties.xml` 失败时**不要崩**,fallback 到 `blockdiagram.xml` 提取 model 名。

### 风险 4:不同 MATLAB 版本格式差异

4 个测试工程均由 R2026a 导出,但产品上线后用户可能上传 R2018 / R2020 / R2024 等版本的 `.slx`。**本 Task 只承诺 R2026a 兼容**,旧版本属于 P2 范围(`docs/01_PROJECT_CONSTITUTION.md` 第 3 节"v0.1 不承诺")。

实现时遵循"宽容解析"原则:

- 未知元素 / 属性 → 加 `parse_warnings`,继续
- 字段缺失 → 用默认值(空字符串 / 空列表 / `None`),加 warning
- **不**主动检测版本号,**不**抛 "version not supported"
- 遇到完全无法理解的结构 → 抛 `SlxParseError` 兜底

### 风险 5:Line 的 `Branch` 分支结构

R2014b 之后,一条 line 可能有多个分支(一个 src 信号送到多个 dst block):

```xml
<Line>
  <P Name="Src">3#out:1</P>
  <Branch>
    <P Name="Dst">10#in:1</P>
  </Branch>
  <Branch>
    <P Name="Dst">5#in:2</P>
  </Branch>
</Line>
```

Codex 应**展开**为多条 `SlxLine`(每条 src 相同,dst 不同),而不是只取第一个 dst。

边界:嵌套 `<Branch>` 内可能又有 `<Branch>`,Codex 应递归处理,但**深度限制 ≤ 10 层**(防止恶意构造);超深度 → 加 warning + 截断。

### 风险 6:Subsystem 内部递归不要无限循环

理论上 Simulink 模型不允许子系统递归引用自己(即 SubSystem A 内部含 SubSystem A 自身),但**恶意构造的 `.slx`** 可能引入循环。

Codex 解析子系统层级时,**必须**维护一个 `visited: set[str]`(已处理的 system_ref / SID 集合),进入新 subsystem 前检查是否已在 visited 中,**已在 = 跳过 + 加 warning**(`"检测到子系统循环引用,已跳过:{ref}"`)。

### 风险 7:大文件性能

工程 1 PMSM 含 10 个 .slx,总解压后 XML 可能达几 MB。建议:

- 使用 `xml.etree.ElementTree.parse(file_like)` 一次性解析单个 XML,**不**用全文 string 拼接
- 对单个 .slx 解析 > 10 秒 → 加 `parse_warnings`,但**不**作为本 Task 验收硬指标
- **不**引入 `lxml` / `iterparse` 流式解析(标准库 `ElementTree` 够用,引入 lxml 违反"不加依赖"规则)

### 风险 8:测试 fixture 的 zip 解压

`tests/adapters/parser/conftest.py` 必须实现一个 `session` scope 的 fixture,把 4 个 zip 解压到 `tmp_path_factory` 提供的临时目录,**全 session 复用**(避免每个测试都重新解压,session 级别共享解压结果,大幅缩短测试运行时间)。

骨架:

```python
import zipfile
from pathlib import Path

import pytest


SLX_SAMPLES_DIR = Path(__file__).parent.parent.parent / 'fixtures' / 'slx_samples'


@pytest.fixture(scope='session')
def extracted_slx_projects(tmp_path_factory):
    """解压 4 个测试 zip 到临时目录,返回 dict[project_name, list[Path]]."""
    extract_root = tmp_path_factory.mktemp('slx_samples_extracted')
    result: dict[str, list[Path]] = {}
    for zip_path in sorted(SLX_SAMPLES_DIR.glob('*.zip')):
        project_dest = extract_root / zip_path.stem
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(project_dest)
        slx_files = sorted(project_dest.rglob('*.slx'))
        result[zip_path.stem] = slx_files
    return result
```

注意:测试 conftest 本身解压 zip 是 fixture 准备,**与 TASK-104"工程压缩包安全解压"不同**——TASK-104 的安全解压是给生产代码用的(防 zip bomb / zip slip),conftest 这里的解压只是给测试取数据,无需安全检查(测试数据是可信的)。

### 风险 9:命名冲突

`adapters/parser/__init__.py` 在 TASK-001 时建为占位空文件。本 Task 应**在 `__init__.py` 中只导出 `SlxParserImpl`**:

```python
from adapters.parser.slx_parser import SlxParserImpl

__all__ = ['SlxParserImpl']
```

下划线模块(`_slx_zip.py` / `_slx_xml.py` 等)**不**在 `__all__` 中,Python 约定"内部使用"。

### 风险 10:`SlxBlock.position` 字段类型陷阱

契约:`position: tuple[int, int, int, int]`,即 4 个整数。

XML 中 `<P Name="Position">[100, 100, 130, 130]</P>` 是字符串,Codex 需要:

```python
import re
pos_str = '[100, 100, 130, 130]'
nums = [int(x) for x in re.findall(r'-?\d+', pos_str)]
if len(nums) == 4:
    position = tuple(nums)  # type: ignore[assignment]
else:
    position = (0, 0, 0, 0)  # fallback
    warnings.append(f"block 位置字段格式异常,使用 (0,0,0,0):SID={sid}")
```

mypy 在严格模式下会抱怨 `tuple` 长度,但本项目 `pyproject.toml` mypy `strict=false`,直接用 `# type: ignore[assignment]` 或显式 `tuple((nums[0], nums[1], nums[2], nums[3]))`。

### 风险 11:`SlxBlock.parameters` 原始字典

契约:`parameters: dict[str, str]`,**全部用字符串**保存,**不**转换数值。这是有意的——参数原始字符串可能是 workspace 变量名(如 `"Kp_speed"`)、表达式(如 `"2*pi*f"`)、字面量(如 `"5.0"`)。TASK-107 ProjectGraph 构建器需要原始字符串才能识别 workspace 变量引用,**这里转成 float 会丢信息**。

### 风险 12:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。本 Task 验收清单已按规则给出命令,直接用。

### 风险 13:`tests/adapters/__init__.py` 可能不存在

TASK-001 建的目录结构可能没在 `tests/adapters/` 下放 `__init__.py`。本 Task 若 `tests/adapters/__init__.py` 不存在,需新建空文件(否则 pytest 可能找不到 `tests/adapters/parser/` 子包)。

```bash
test -f tests/adapters/__init__.py && echo OK || touch tests/adapters/__init__.py
```

---

## 估时

预估 **10-15 小时**:

- 阅读 4 个 zip 实际 XML 结构 + 设计模块拆分:1-2 小时
- `_slx_zip.py` + `_slx_xml.py` P0 实现 + 单元测试:3-4 小时
- `_slx_subsystem.py` 子系统递归 + 测试:1-2 小时
- 4 个真实工程 P0 联调(必然有版本差异 / 字段格式差异需要兼容):2-3 小时
- `_slx_config.py` P1 实现 + 测试:1-2 小时
- 4 个真实工程 P1 联调:1 小时
- 错误处理 + 错误消息中文化 + 测试:0.5 小时
- README / commit 拆分 / PR 描述 / 三件套确认:0.5-1 小时

比 TASK-101(4-6 小时)显著长,主要是真实 XML 解析的"字段格式碰运气"。Codex 实际可能在 4 个工程联调阶段反复调整宽容解析逻辑。

---

## 给 Codex 的提示

### 1. 先看 4 个 zip 实际结构,再动手写代码

切分支后**第一件事**:解压 4 个 zip 看实际 XML(只看,不修改测试集):

```bash
mkdir -p /tmp/slx_probe
cd /tmp/slx_probe
unzip -l /your/repo/tests/fixtures/slx_samples/04_lms_noise_cancel.zip
# 选最简单的工程 4 LMS,unzip 后看内部 .slx 的目录结构
unzip /your/repo/tests/fixtures/slx_samples/04_lms_noise_cancel.zip
# 找到 .slx 文件后再 unzip 一次(.slx 自身是 ZIP)
unzip /tmp/slx_probe/some_path/foo.slx -d /tmp/slx_probe/foo_slx
ls -R /tmp/slx_probe/foo_slx
cat /tmp/slx_probe/foo_slx/simulink/blockdiagram.xml | head -100
```

确认本 Task 文档"接口契约"小节描述的 XML 结构与你实际看到的一致。**如果有显著差异(节点名 / 嵌套结构 / 属性命名),停手问 PM**,不要默默按你看到的另一套结构实现。

### 2. 推荐实现顺序

1. **`_slx_zip.py`**:`open_slx_zip(path)` 上下文管理器返回 `ZipFile` 对象 / `read_xml(zf, name)` 读单个 XML 返回 `ElementTree`
2. **`_slx_xml.py`**:`parse_blocks(system_elem)` / `parse_lines(system_elem)` / `get_p_value(elem, name, default=None)` 辅助工具
3. **`_slx_subsystem.py`**:`walk_subsystems(zf, root_system_elem)` 递归遍历,维护 `visited` 集合
4. **`slx_parser.py`**:`SlxParserImpl.parse()` 串起整个流程
5. **`_slx_config.py`**:P1 内容,放到 P0 4 工程联调通过后再做

### 3. 先用工程 4 LMS 把 P0 调通

工程 4 最简单(只有 2 个 .slx,信号处理工程结构清晰),用它把 P0 流程跑通:

```bash
pytest tests/adapters/parser/test_slx_parser_real_p0.py::test_lms_floating_point -v
```

绿了再扩展到工程 3(PID,3 个变体)→ 工程 2(Buck,1 个但含 Simscape)→ 工程 1(PMSM,10 个最复杂)。

### 4. Commit 拆分建议(Conventional Commits)

```
feat(parser): add slx zip reader utility
test(parser): add slx zip reader unit tests
feat(parser): add slx xml block and line parser
test(parser): add slx xml parser unit tests
feat(parser): add slx subsystem traversal
test(parser): add slx subsystem unit tests
feat(parser): add slx parser main entry (P0)
test(parser): add slx parser P0 tests on 4 real projects
feat(parser): add solver config / mask / library link recognition (P1)
test(parser): add slx parser P1 tests on 4 real projects
test(parser): add slx parser error handling tests
docs(parser): update adapters/parser/README
docs: mark TASK-102 as in-review and TASK-003 as done in task index
```

不要单个超大 commit 提交全部代码——每个 commit 单一职责,review 更轻松。

### 5. 文件拆分纪律

`docs/04_ENGINEERING_STANDARDS.md` 第 4 节"每文件 ≤ 300 行"是硬规定。若 `_slx_xml.py` 写到 280 行还没收尾,**主动**拆出 `_slx_xml_params.py` / `_slx_xml_ports.py` 等子模块,**不要**写到 320 行才发现违规。

### 6. 错误消息严格中文

`SlxParseError("file not found")` ❌ — 英文不行。
`SlxParseError("找不到 .slx 文件:...")` ✅。

详见"接口契约"小节"错误消息中文化清单"。

### 7. 不要硬编码 R2026a 假设

虽然测试集全是 R2026a 导出,但实现时**不要**写 `if matlab_version == "R2026a"`(本来也没法可靠检测版本)。用"宽容解析",有就用,没有就 fallback / warning。

### 8. 内部模块的 import

```python
# adapters/parser/slx_parser.py
from adapters.parser._slx_zip import open_slx_zip, read_xml
from adapters.parser._slx_xml import parse_blocks, parse_lines
from adapters.parser._slx_subsystem import walk_subsystems
from adapters.parser._slx_config import parse_solver_config, detect_mask, detect_library_link
```

用绝对路径 import,**不**用相对 import(`from .slx_zip import ...`)。

### 9. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见"风险与注意点"风险 1 的脚本骨架。改完后 `git diff docs/03_TASK_INDEX.md` 确认只显示 4 行左右改动。**若 diff 显示几百行变化,立即 `git checkout --` 撤销,换方式 A 用编辑器手改**。

### 10. 完工报告必须含 git 三件套(决策 08)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 三条命令的完整输出**(决策 08 第 1 条)
- 验收清单(本 Task 文档"验收标准"1-16 项)逐条勾选 + 说明
- PR 标题:`TASK-102: .slx XML 解析器(P0/P1/P2 分级)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 11. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:

- PR 标题:`TASK-102: .slx XML 解析器(P0/P1/P2 分级)`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

PM 在 GitHub 网页手动创建 PR。CI 自动触发,绿了之后 PM 把 Codex 产出 + CI 结果交给架构师 review。

### 12. 遇冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / TASK-101 契约 的任何冲突,**停手问 PM**,不要默默偏离。

常见可能冲突场景:

- 发现 `SlxModel` 字段需要新增 / 修改 → **不要改 TASK-101 已建的 dataclass**,问 PM 是否走宪法修订流程
- 发现 `core/domain/exceptions.py` 缺某种异常子类需要新增 → **不要在本 Task 顺带改 core**,问 PM
- 发现 4 个测试工程中某个工程实际格式与本 Task 文档"接口契约"小节描述完全不同 → **不要硬扛**,告诉 PM 你看到的实际结构,等架构师调整

---

**版本**:Task 文档 v1.0
**作者**:Claude(架构师,第四任)
**日期**:2026-06-02
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md`
**关联 Task**:依赖 TASK-101(契约) / TASK-003(测试集);下游 TASK-104 / TASK-107
