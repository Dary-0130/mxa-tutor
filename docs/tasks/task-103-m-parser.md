# TASK-103: .m 文件解析器

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第三个 Task,与 TASK-102(.slx 解析器)并列——一个负责把 `.slx` ZIP+XML 容器还原成 `SlxModel`,另一个负责把 `.m` 纯文本文件还原成 `MFile`。两者合起来构成 MCS 阶段"工程结构静态解析"能力的左右两条腿。

TASK-101 已建好 `MFile` / `MFunction` / `MParser` 抽象接口 / `MParseError` 异常的"骨架"(纯数据结构,无实现)。本 Task 负责"补肉":**实现 `MParser` 接口的具体类,把单个 `.m` 文件解析成填好的 `MFile` dataclass**。

与 `.slx` 不同,`.m` 是纯文本(不需要 ZIP/XML 处理),但 MATLAB 语法有几个**独特坑**:

- 单行注释 `%`(但 `%` 在字符串里不算注释)
- 块注释 `%{ ... %}`(必须独占行,否则降级为单行注释)
- 续行 `...`(但 `...` 在字符串里不算续行)
- 单引号字符串 `'...'` 与转置运算符 `'` 共用一个字符,**靠上下文区分**
- 双引号字符串 `"..."`(R2017a 引入,语法独立)
- `end` 关键字一字多用(块结束 / 数组索引 `A(end)` / `arguments` 块结束)
- `function` 签名 5 种形式 + 可选 `arguments` 验证块
- `classdef` 顶层标记 + 内部 `properties` / `methods` / `events` / `enumeration` 块

`docs/02_ARCHITECTURE_OVERVIEW.md` 第 6 节技术决策 4 明确授权:".m 文件先用正则 + 简单 AST,完整 MATLAB AST 太复杂,MCS 阶段不需要"。本 Task 据此实施——**只做够用即可**,不追求 LSP 级别精确。

本 Task 是 TASK-105(文件依赖关系分析)的关键料源——`MFile.functions` 列出每个 .m 文件定义的 top-level 函数,跨文件调用关系才能基于这些函数名构图。也是 TASK-107(ProjectGraph + TeachingUnit 构建器)的料源——`ProjectGraph` 的 `FILE_M` / `FUNCTION` 节点和 `CALLS` 边,全部来自本 Task 输出的 `MFile`。

上下游依赖:

- **上游**:TASK-101(契约源)/ TASK-003(测试集 4 个 MATLAB 工程含 11 个 .m 文件)
- **下游**:
  - TASK-105 文件依赖分析消费 `MFile.functions` + `MFile.imports`
  - TASK-107 ProjectGraph 构建器消费 `MFile.file_role` + `MFile.functions`

**本 Task 不在 `docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"的核心 Task 清单里**(清单是 101/102/104/107/205/304),且 PM 决定 TASK-102 后的核心 Task 也不二审(GPT 对 R2026a 等新版本细节不准)。Task 文档完稿后**直接交给 Codex 实施**。

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并 commit `01413a7`)
- ✅ TASK-002(开发环境 + CI,已合并 commit `64d337d`)
- ✅ TASK-003(4 个真实 MATLAB demo 测试集,已合并 commit `6bbea80`,位于 `tests/fixtures/slx_samples/`)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并 commit `bf50aba`):**直接契约依赖**,本 Task 实现 `core/interfaces/parser.py::MParser` 并返回 `core/domain/m_file.py::MFile`
- ✅ TASK-102(.slx XML 解析器,已合并 commit `2317bb6`):间接依赖,本 Task 在 `tests/adapters/parser/conftest.py` 里**扩展**(不覆盖)TASK-102 已建的 fixture
- ✅ 小文档清洁 PR(已合并 commit `cfe73b4`):03 索引基线已对齐,本 Task 推 TASK-103 状态时基于干净基线

### 必须存在的文件 / 状态

- `main` 分支处于 commit `cfe73b4` 或之后
- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/domain/m_file.py` — `MFunction` / `MFile` dataclass
  - `core/domain/exceptions.py` — `MParseError` 异常类
  - `core/interfaces/parser.py` — `MParser` 抽象接口
- 以下 TASK-102 产出文件**已存在**,本 Task 不动:
  - `adapters/parser/slx_parser.py` 等 5 个 `.slx` 解析模块
  - `tests/adapters/parser/conftest.py`(本 Task 在此基础上**追加**新的 fixture,不重写)
  - `adapters/parser/__init__.py`(本 Task 在此追加导出 `MParserImpl`)
- `tests/fixtures/slx_samples/` 含 4 个 zip,合计 **11 个 `.m` 文件**(详见"接口契约"小节"11 个 .m 文件预期分类矩阵")
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 3 节 v0.1 不承诺清单 / 第 7 节技术架构原则与禁止依赖 / 第 8 节"禁止执行用户上传代码"**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 4.1 节 `MFile` / `MFunction` 契约 / 第 6 节技术决策 4 "正则 + 简单 AST"授权**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 8.1 节"绝对不执行用户上传代码" / 第 8.4 节失败隔离 / 第 10 节异常处理**)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**讲解输出,但 `MFile` 是后续讲解的数据源,需理解下游使用场景)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`(教学理解中间层归属)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描规范)
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读仓库文件,Task 文档可使用路径引用)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(`docs/` 改动语义)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**Codex 完工报告必须含 git 三件套**;**改已有文件必须用编辑器或 Python 字节级操作**,禁用 `read_text` / `write_text` / `sed -i`)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源,本 Task 严格依赖其定义的 `MFile` / `MFunction` 字段)
- `docs/tasks/task-102-slx-xml-parser.md`(参考实施风格,本 Task 在 `adapters/parser/` / `tests/adapters/parser/` 目录复用 TASK-102 已建的目录结构与 conftest 模式)
- `tests/fixtures/slx_samples/README.md`(测试集清单)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

`adapters/parser/` 下:

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `m_parser.py` | **主入口**,定义 `MParserImpl(MParser)`,实现 `parse(m_file_path: str) -> MFile` | 100-150 |
| `_m_lex.py` | 词法预处理(块注释剥离 / 单行注释剥离 / 续行折叠 / 字符串占位符化) | 150-250 |
| `_m_structure.py` | `file_role` 分类(script / function / class)+ top-level function 提取(name / inputs / outputs / line_range / docstring) | 200-300 |
| `_m_dependencies.py` | imports 提取(`import pkg.Class`)+ uses_toolbox 启发式识别(白名单匹配) | 100-150 |

下划线前缀模块为 `m_parser.py` 的内部协作模块,**不暴露**到 `adapters/parser/__init__.py`(只新增导出 `MParserImpl`)。

`tests/adapters/parser/` 下(目录由 TASK-102 已建,本 Task 仅新增以下 3 个测试文件 + 扩展 conftest.py):

| 文件 | 职责 |
|------|------|
| `test_m_parser_unit.py` | 用**内嵌**小型 .m 字符串测试每个解析单元(注释剥离 / 字符串识别 / function 块提取 / file_role 分类),目标:运行 < 2 秒 |
| `test_m_parser_real.py` | **真实工程验收**,跑在 4 个工程合计 11 个 `.m` 文件上(详见"接口契约"小节"11 个 .m 文件预期分类矩阵") |
| `test_m_parser_errors.py` | 错误处理(文件不存在 / 二进制文件 / 编码异常 / 单 function 解析失败但整体继续) |

### 修改文件

- **`adapters/parser/__init__.py`** — TASK-102 已建,本 Task **追加**一行 `from adapters.parser.m_parser import MParserImpl`,并把 `__all__` 扩展为 `['SlxParserImpl', 'MParserImpl']`
- **`adapters/parser/README.md`** — TASK-102 已建,本 Task **追加**一段说明新增的 4 个 `_m_*` 模块各自的一句话职责,以及 `MParserImpl` 的对外用法 1-2 行示例
- **`tests/adapters/parser/conftest.py`** — TASK-102 已建 `extracted_slx_projects` fixture,本 Task **追加**一个 `extracted_m_files` fixture(返回 `dict[project_name, list[Path]]`,key 是工程名,value 是该工程内 .m 文件路径列表),复用 TASK-102 已经解压好的 `tmp_path_factory` 临时目录
- **`docs/03_TASK_INDEX.md`** — 把 TASK-103 行状态从 🔲 改为 🔍,Week 1 进度条 `[✅✅⬜⬜⬜⬜⬜]` → `[✅✅🔍⬜⬜⬜⬜]`(3/7 数字不变,Codex 推 🔍 后)。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1

### 不动文件

- `core/domain/*.py` 和 `core/interfaces/*.py`(TASK-101 已建,**契约不许动**;如发现需要调整,**停手问 PM**,走宪法修订流程,不能在本 Task 顺带改)
- `adapters/parser/slx_parser.py` / `_slx_*.py`(TASK-102 已建,**与本 Task 解耦**,不允许修改)
- `requirements.txt` / `requirements-dev.txt`(本 Task **不引入任何新依赖**)
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml` / `scripts/check_repo_hygiene.sh`(TASK-002 已配,本 Task 不调)
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(详见决策 07)
- `tests/fixtures/slx_samples/*.zip` 和 `tests/fixtures/slx_samples/README.md`(TASK-003 已建,**只读**)
- `tests/adapters/parser/test_slx_parser_*.py`(TASK-102 已建,**与本 Task 解耦**,不允许修改)
- `core/prompts/` / `eval/` / `app/` / `api/` / `features/` / `web/` 下任何文件
- 其他 Task 的代码与测试

### 新增依赖

**无**。本 Task 全部使用 Python 标准库:`re` / `pathlib` / `dataclasses`。

### 新增配置项

**无**。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-103-m-parser`
- [ ] **依赖结构理解**:实施前**第一件事**,unzip 4 个测试 zip 后 `cat` 11 个 `.m` 文件的前 30 行(详见"给 Codex 的提示"第 1 条),手动确认本文档"接口契约"小节"11 个 .m 文件预期分类矩阵"的预期值与实际文件第一非注释行一致——**若实际不符,停手抛冲突给 PM 裁决**,不要默默改实现绕过预期
- [ ] **核心实现**(`adapters/parser/m_parser.py` 主入口 + 3 个内部模块):
  - [ ] `MParserImpl(MParser).parse(m_file_path: str) -> MFile` 接受单个 `.m` 文件路径,返回填好的 `MFile`
  - [ ] 失败时抛 `MParseError`,错误消息**中文**(详见"接口契约"小节"错误消息中文化清单")
  - [ ] `MFile.file_path` 填充原始路径
  - [ ] `MFile.raw_code` 用 **bytes-first 策略** 读取(详见"接口契约"小节"2.1 文件读取策略",GPT 二审采纳):`Path.read_bytes()` → 二进制检测 → `utf-8-sig` → `utf-8` → `gbk` → `errors='replace'` 兜底,**优先保住中文注释**。读 `.m` 文件本身**不**违反决策 08——决策 08 禁的是改**已有仓库内部**的文本文件;读用户上传 / 测试集的工程文件是正常 IO
  - [ ] `MFile.file_role` 填充 `"script"` / `"function"` / `"class"`(分类规则详见"接口契约"小节)
  - [ ] `MFile.functions` 填充 top-level function 列表(每个 `MFunction` 含 `name` / `inputs` / `outputs` / `line_range` / `docstring`)。**若 `MFile.file_role == "class"`,`functions` 必须为空列表 `[]`**——MCS 阶段不展开 classdef 内部 methods,详见接口契约 8 节 "classdef 守卫"(GPT round-2 采纳)
  - [ ] `MFile.imports` 填充 `import` 语句的目标列表(如 `["matlab.io.*", "containers.Map"]`)
  - [ ] `MFile.uses_toolbox` 填充启发式识别的 toolbox 列表(基于本文档"接口契约"小节定义的白名单 dict)
- [ ] **词法预处理**(`_m_lex.py`):
  - [ ] 块注释 `%{ ... %}` 识别与剥离(必须独占行才识别为块注释)
  - [ ] 单行注释 `%` 识别与剥离(注意:字符串内的 `%` 不算注释)
  - [ ] 续行 `...` 识别与折叠(注意:字符串内的 `...` 不算续行)
  - [ ] 字符串占位符化(将 `'...'` 和 `"..."` 替换为占位符,避免后续 `function` / `end` 等关键字识别被字符串字面值干扰)
  - [ ] **接受边界 case 偶尔误判**:`'` 转置 vs 字符串的极端歧义,接受偶尔误判(影响极小,不阻塞 file_role 分类与 function 提取)
- [ ] **结构提取**(`_m_structure.py`):
  - [ ] `file_role` 分类:看预处理后的代码,第一个非空白非注释行——以 `function` 关键字开头 → `"function"`;以 `classdef` 关键字开头 → `"class"`;否则 → `"script"`
  - [ ] top-level function 提取:用正则匹配 `^\s*function\s+...` 开头的行,解析签名 5 种形式(详见"接口契约"小节"function 签名 5 种形式"),记录 `line_range`(`function` 行号到对应 `end` 行号,**仅 top-level**,不递归 nested function)
  - [ ] docstring 提取:function 行下方第一段连续的 `%` 注释(MATLAB 习惯)
  - [ ] `arguments` 块识别(R2019b+):若 function 内部首段为 `arguments ... end`,在 docstring 提取时跳过这一段
- [ ] **依赖识别**(`_m_dependencies.py`):
  - [ ] `imports` 提取:正则匹配 `^\s*import\s+([\w.]+(?:\.\*)?)\s*;?` 全部命中目标
  - [ ] `uses_toolbox` 启发式:维护一个 `{toolbox_name: set[function_name]}` 白名单 dict(详见"接口契约"小节"toolbox 白名单"),扫预处理后的代码,出现命中函数名 → 加 toolbox(去重)
- [ ] **失败隔离**(`docs/04_ENGINEERING_STANDARDS.md` 第 8.4 节):
  - [ ] 单个 function 块签名解析失败 → **注意:`MFile` dataclass 没有 `parse_warnings` 字段**(`SlxModel` 有,但 `MFile` 没有,TASK-101 契约如此),所以单 function 解析失败时,**该 function 直接跳过不加入 `functions` 列表**,**不**抛异常,继续处理其他 function(下游 TASK-105/107 通过 `ProjectGraph.unresolved_symbols` 承接缺料,详见风险 10)
  - [ ] 文件不存在 → 抛 `MParseError`
  - [ ] 文件存在但是二进制(如 `.mexw64` 错误改后缀) → 抛 `MParseError`,消息含"不是有效的文本文件"
  - [ ] 文件存在且带 UTF-8 BOM → `utf-8-sig` 自动剥离 BOM,继续解析,`file_role` 分类不受影响
  - [ ] 文件存在但是 GBK 编码(含中文注释) → bytes-first 策略命中 GBK 解码,**`raw_code` 正确保留中文**,**不**降级到 `\ufffd` 替换字符
  - [ ] 文件存在但编码连 GBK 也失败 → 用 `errors='replace'` 兜底,继续解析(`raw_code` 保留替换字符);**不**抛异常
- [ ] **单元测试**(`tests/adapters/parser/test_m_parser_unit.py`):用内嵌字符串覆盖以下场景(详见"验收标准"小节)
- [ ] **真实工程测试**(`tests/adapters/parser/test_m_parser_real.py`):**11 个 `.m` 文件全部 parse 成功**,且分类与提取断言全部通过(详见"验收标准"小节"11 个 .m 文件真实工程断言矩阵")
- [ ] **错误处理测试**(`tests/adapters/parser/test_m_parser_errors.py`)
- [ ] **`tests/adapters/parser/conftest.py` 扩展**:新增 `extracted_m_files` fixture(详见"接口契约"小节"conftest 扩展骨架")
- [ ] **`adapters/parser/__init__.py` 扩展**:追加 `MParserImpl` 到 `__all__`
- [ ] **`adapters/parser/README.md` 更新**:追加 4 个新模块的一句话职责 + `MParserImpl` 用法示例
- [ ] **本地全检通过**:`make check` 全绿(lint / type-check / pytest / hygiene)
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-103 状态从 🔲 改为 🔍,Week 1 进度条第 3 位 ⬜ 改为 🔍
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见"风险与注意点"风险 1
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-103 as in-review in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status`(working tree clean)/ `git log --oneline main..HEAD`(完整 commit 列表)/ `git push`(推送成功输出)
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

### v0.1 P2 范围明确不做(`docs/01_PROJECT_CONSTITUTION.md` 第 3 节)

- ❌ **完整 MATLAB AST**:不实现表达式级解析(算术/比较/赋值/索引等),仅做"行级 + function 块级"识别。架构总览第 6 节决策 4 明确授权"正则 + 简单 AST"
- ❌ **nested function 内部结构**:仅识别 top-level function(即 `function` 关键字在文件顶层,在所有 `function/if/for/while/switch/try/classdef` 等块的**外部**),不递归 nested function
- ❌ **anonymous function `@(x) x.^2`**:不提取到 `MFile.functions` 列表,留在 `raw_code` 中
- ❌ **classdef 内部 methods 块详细结构**:遇到 `classdef`,只标记 `file_role == "class"`,**不**展开 `properties` / `methods` / `events` / `enumeration` 块的内部结构(因此 classdef 文件的 `MFile.functions` 列表为空,不把 methods 当 functions)
- ❌ **`arguments` 块内部约束语义**:R2019b 引入的参数验证块,本 Task 仅识别其存在(用于跳过 docstring 误识别),**不**解析 `arguments` 内部的类型约束、size 约束、默认值
- ❌ **运行 / 执行用户工程**(`docs/04_ENGINEERING_STANDARDS.md` 第 8.1 节硬约束):本 Task 严格静态解析,**不**调 `subprocess` / `exec` / `eval` / MATLAB 等任何代码执行路径
- ❌ **跨 .m 文件分析**:本 Task 一次只处理**单个** `.m`;跨文件依赖(谁调用谁)是 TASK-105 的事
- ❌ **`.mlx` Live Script 文件**:本 Task 仅处理 `.m` 纯文本;`.mlx` 是 OOXML 容器(类似 `.slx`),Phase 2 范围
- ❌ **`.p` 编译文件 / `.mex*` 二进制**:不解析(本来也无法解析),遇到当 binary 处理,抛 `MParseError`

### 工程范围排除

- ❌ **不实现 `core/interfaces/parser.py::SlxParser`**(那是 TASK-102 的范围,已合并)
- ❌ **不写 `adapters/parser/mat_reader.py` / `prj_parser.py` / `zip_extractor.py`**(分别是暂未列 / TASK-104 / TASK-104)
- ❌ **不引入第三方依赖**(包括但不限于 `mat2py` / `oct2py` / `matlab_parser` 等;`re` 标准库够用)
- ❌ **不写 ProjectGraph 构建逻辑**(那是 TASK-107)
- ❌ **不写 LLM 调用**(本 Task 是纯结构化解析,无任何 LLM 介入)
- ❌ **不写性能基准测试**(只跑功能正确性测试)
- ❌ **不修改 `core/domain/m_file.py` 字段定义**(TASK-101 契约;尤其注意 `MFile` **没有** `parse_warnings` 字段,与 `SlxModel` 不同,**不允许擅自添加**——单 function 失败时跳过即可)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md`)
- ❌ **不修改 TASK-102 已建文件**(`adapters/parser/slx_parser.py` / `_slx_*.py` / `tests/adapters/parser/test_slx_parser_*.py` 不许动;`__init__.py` / `README.md` / `conftest.py` 是**追加**不是覆盖)

---

## 接口契约

### 1. `MParser` 接口与 `MFile` / `MFunction` 契约(TASK-101 已建,不重新内联)

本 Task 必须实现 `core/interfaces/parser.py::MParser` 抽象接口,签名:

```python
class MParser(ABC):
    @abstractmethod
    def parse(self, m_file_path: str) -> MFile: ...
```

返回 `core/domain/m_file.py::MFile`,字段定义如下(**完整契约请从 `core/domain/m_file.py` 直接读**,**不许修改字段名 / 类型 / 默认值**):

- `MFile`:`file_path: str` / `file_role: str` / `functions: list[MFunction]` / `imports: list[str]` / `uses_toolbox: list[str]` / `raw_code: str`
- `MFunction`:`name: str` / `inputs: list[str]` / `outputs: list[str]` / `line_range: tuple[int, int]` / `docstring: str | None`

异常用 `core/domain/exceptions.py::MParseError`(继承 `ParseError` 继承 `MxaError`)。

**关键细节**:`MFile` 与 `SlxModel` 不同——**`MFile` 没有 `parse_warnings` 字段**。所以解析过程中遇到的可恢复异常(单 function 签名解析失败、未知 toolbox 函数名等),处理方式是:

- 单 function 签名失败 → **跳过该 function 不加入 `functions` 列表**,**不**抛异常,**不**通过任何字段对外报告
- 未知 toolbox → 不加入 `uses_toolbox`,这是正常行为(白名单覆盖不全是已知缺陷)
- 编码异常 → `errors='replace'` 容错,`raw_code` 保留替换字符,**不**抛异常
- 整文件解析失败(不存在 / 二进制) → 抛 `MParseError`

如果你在实施时**强烈感觉**需要给 `MFile` 加 `parse_warnings` 字段以汇报恢复性问题,**停手问 PM**,不要在本 Task 顺带改 TASK-101 契约。

### 2. 实现类签名

`adapters/parser/m_parser.py`:

```python
from pathlib import Path

from core.domain.exceptions import MParseError
from core.domain.m_file import MFile, MFunction
from core.interfaces.parser import MParser


class MParserImpl(MParser):
    """.m 文件解析器具体实现(正则 + 简单 AST,不追求完整 AST)。

    输入单个 .m 文件路径,读取纯文本并基于行级 + function 块级识别,
    返回填好的 MFile dataclass。

    实现策略(架构总览第 6 节决策 4 授权):
        1. 词法预处理(_m_lex):剥离块注释 / 单行注释 / 续行,字符串占位符化
        2. 结构提取(_m_structure):file_role 分类 + top-level function 提取
        3. 依赖识别(_m_dependencies):imports 列表 + uses_toolbox 启发式

    范围(本 Task 不承诺):
        - 不解析 nested function 内部
        - 不解析 anonymous function
        - 不展开 classdef 内部 methods / properties
        - 不解析 arguments 块内部类型约束
        详见 Task 文档"不做"小节
    """

    def parse(self, m_file_path: str) -> MFile:
        """解析单个 .m 文件。

        Args:
            m_file_path: .m 文件绝对或相对路径。

        Returns:
            填好的 MFile。

        Raises:
            MParseError: 文件不存在 / 不是有效文本文件(二进制) / 整文件无法识别。
        """
        ...
```

Codex 在内部模块(`_m_lex.py` / `_m_structure.py` / `_m_dependencies.py`)的函数签名自由设计,但**对外只暴露 `MParserImpl`**(`adapters/parser/__init__.py` 追加 `from adapters.parser.m_parser import MParserImpl`,扩展 `__all__` 为 `['SlxParserImpl', 'MParserImpl']`,**不**导出下划线模块)。

### 2.1 文件读取策略(bytes-first,GPT 二审采纳)

目标用户是中文学生,`.m` 文件里的中文注释 / docstring 是后续教学讲解的关键材料。直接 `read_text(encoding='utf-8', errors='replace')` 在 GBK 编码的 `.m` 文件上会把所有中文变成 `\ufffd` 替换字符——**这是产品级损失**,必须避免。

正确策略:

```python
from pathlib import Path

from core.domain.exceptions import MParseError


def read_m_file(m_file_path: str) -> str:
    """bytes-first 读取 .m 文件,优先保住中文注释。"""
    p = Path(m_file_path)
    if not p.exists():
        raise MParseError(f"找不到 .m 文件:{m_file_path}")
    if p.is_dir():
        raise MParseError(f"路径不是文件:{m_file_path}")

    raw_bytes = p.read_bytes()

    # 1. 二进制检测:前 8KB 含 NULL 字节 = 二进制
    if b'\x00' in raw_bytes[:8192]:
        raise MParseError(f".m 文件解析失败:不是有效的文本文件({m_file_path})")

    # 2. 按优先级尝试解码
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    # 3. 全部失败,用 errors='replace' 兜底(保留可解码部分)
    return raw_bytes.decode('utf-8', errors='replace')
```

要点:

- **`utf-8-sig` 优先**:自动剥离 UTF-8 BOM(Windows 编辑器生成的文件常带 BOM,直接 `utf-8` 解会让第一个 token 前带 `\ufeff`,影响 `file_role` 关键字识别)
- **`utf-8` 第二**:处理标准 UTF-8 文件(MATLAB R2014b+ 默认)
- **`gbk` 第三**:中文 Windows 老工程常见编码(MATLAB R2014b 之前的中文环境默认 GBK)
- **`errors='replace'` 兜底**:确保任何输入都能返回字符串,不抛 `UnicodeDecodeError`

`MFile.raw_code` 必须填这个函数的返回值(**未经预处理**的原始字符串),用户后续可能要看到原代码做对照,不能给它"剥过注释的"版本。

### 3. MATLAB 语法关键规则(7 个坑点,Codex 实施时严格遵守)

#### 预处理 5 步顺序(GPT 二审采纳,必读)

**这是整个解析流程的"成功钥匙"**——必须按顺序执行,颠倒任一步都会让后续识别被字符串内字符 / 注释里的关键字干扰。

| 步骤 | 操作 | 模块 | 行号是否变化 | 原因 |
|---|---|---|---|---|
| 1 | 块注释剥离 | `_m_lex` | 不变(替换为空行) | `%{` / `%}` 独占行特殊规则,可以**最先做**,块注释里的 `'` / `"` / `%` / `end` 都应当作文本忽略 |
| 2 | **字符串占位符化** | `_m_lex` | 不变 | 后续 `%` / `...` / `end` / 括号识别**必须**先去掉字符串内字符的干扰 |
| 3 | 单行注释剥离 | `_m_lex` | 不变 | 此时字符串已被占位符替代,行尾 `%` 一定是注释 |
| 4 | 续行折叠 | `_m_lex` | **变化**(`...\n` 替换为空格,多行合一行) | 字符串已占位,`...` 一定是续行;**必须更新 line_map** |
| 5 | 结构识别 | `_m_structure` | (在 folded code 上分析) | 此时代码已"纯净",正则和 `end` 嵌套深度计数都可靠 |

**关键约束**(GPT 二审 round-2 升级:line_map 是 tuple 形态):`_m_lex` 模块的预处理函数必须**同时返回 `line_map`**,类型是 `dict[int, tuple[int, int]]`(`processed_line → (original_start_line, original_end_line)`,1-based)。步骤 1 把块注释行替换为空行而**不是删除行**,就是为了保住行号;步骤 4 续行折叠会让一个 processed line 覆盖多个原始行,**必须用 tuple 表达这种 "1 → N" 的覆盖关系**——单一 int 映射会丢失续行 function 签名的起始行号信息(详见接口契约 5.1 节"line_map 必须是 tuple,不是单一 int")。

`_m_structure::extract_functions` 接受 `(folded_code, line_map, original_lines)`:在 folded 上识别 function 起止 → 通过 line_map 翻译回原始行号填 `MFunction.line_range` → **从 `original_lines` 提取 docstring**(不能从 folded,因为 % 已剥光)。详见接口契约第 5 节"function 块提取规则"。

#### 坑 1:单行注释 `%`

规则:从 `%` 字符到行尾,视为注释。

**陷阱**:`%` 在字符串字面值内不是注释起始。

```matlab
% this is a comment
x = 'hello %world';     % 行尾这个 % 才是注释,'hello %world' 里的 % 是字符串字符
y = "name = %s";        % R2017a 双引号字符串里的 % 也不是注释
```

实现建议:**先字符串占位符化(坑 4 + 坑 5),再用正则删行尾 `%.*$`**。两步顺序不能颠倒,否则字符串内的 `%` 会被误识别。

#### 坑 2:块注释 `%{ ... %}`

规则:**必须独占行**,即 `%{` 行只能有前导空白,行尾不能有其他内容;`%}` 同理。

```matlab
%{
This is a block comment.
Multiple lines OK.
%}

x = 1;                    %{ this is NOT a block comment (not standalone) %}
                          % 上面这行实际是: 赋值语句 + 单行注释(从第一个 % 到行尾)
```

实现建议:逐行扫,匹配 `^\s*%\{\s*$` 进入"块注释模式",匹配 `^\s*%\}\s*$` 退出。块注释模式内的行直接删除(或替换为空行,保持行号不变,这样后续 `line_range` 字段才能对齐原始文件行号)。

#### 坑 3:续行 `...`

规则:`...` 后跟换行,表示下一行是当前表达式的延续。`...` 后允许跟注释(`%`)再换行。

```matlab
result = a + b + ...
         c + d + ...      % comment after ...
         e;
```

**陷阱**:字符串内的 `...` 不是续行。

```matlab
msg = 'Loading...';        % 这里的 ... 是字符串字符,不是续行
fprintf('Step 1...\n');    % 同上
```

实现建议:字符串占位符化之后,用 `re.sub(r'\.\.\.\s*(%[^\n]*)?\n', ' ', code)` 折叠续行。

#### 坑 4:`'...'` 字符串 vs `'` 转置运算符

规则(MATLAB 官方文档):`'` 的语义取决于**前一个 token**:

- 前一个 token 是**标识符 / 数字 / 闭括号 `)` `]` `}` / `end` 关键字 / `'` 本身(转置后再转置)** → 当前 `'` 是**转置运算符**
- 否则(行首 / `(` `[` `{` / 运算符 / 逗号 / 分号 / 等号 / 关键字开头) → 当前 `'` 是**字符串起始**

```matlab
A = B';                    % B' 转置 — B 是标识符
C = A(end)';               % A(end)' 转置 — end 是关键字,) 是闭括号
D = 'hello';               % 'hello' 字符串 — = 是赋值符号
E = [1 2 3]';              % [1 2 3]' 转置 — ] 是闭括号
F = (a + b)';              % (a+b)' 转置 — ) 是闭括号
G = {'abc', 'def'};        % 'abc' / 'def' 字符串 — { 是开括号,, 是逗号
H = 'it''s';               % 字符串 "it's" — '' 是转义的单引号
```

**陷阱**:`'` 内部转义用 `''`(两个连续单引号),不是 `\'`。

实现建议:**用状态机**,维护"上一个非空白 token 类型"。简单实现:
- 扫每一行,字符级状态机
- 状态 = `(in_single_string, in_double_string, last_token_type)`
- `last_token_type` ∈ {`identifier`, `number`, `close_bracket`, `end_keyword`, `transpose`, `operator`, `start_of_line`}
- 遇到 `'`:
  - 若在字符串内 → 字符串结束(或转义 `''` 继续)
  - 若 last_token_type ∈ {identifier / number / close_bracket / end_keyword / transpose} → 转置,跳过
  - 否则 → 字符串开始,标记 in_single_string=True

**本 Task 允许偶尔误判**:边界 case(如 `f().'` 共轭转置后又跟其他)即使误判,影响仅限于 toolbox 函数名扫描的极少数情况,**不影响** `file_role` 分类和 `function` 块识别(因为 `function` / `classdef` / `end` 关键字行通常不出现 `'`)。

#### 坑 5:`"..."` 双引号字符串(R2017a+)

规则:`"` 内部 `""` 转义双引号,语法简单,不与其他字符冲突。

```matlab
str1 = "hello, world";
str2 = "she said ""hi""";       % 等价于 'she said "hi"'(MATLAB string class)
```

实现建议:状态机与单引号字符串平行处理,简单。

#### 坑 6:`end` 关键字一字多用

`end` 在以下语境下是**块结束关键字**(必须当作语法结构):

- `function ... end`(可选 in script,但 nested function / class methods 内必须;**本 Task 兼容两种**:看到 `function` 行后,若下一行匹配 `^\s*end\s*$` 在嵌套深度回到 0 时,视为函数结束)
- `if/for/while/switch/try ... end`
- `arguments ... end`(R2019b+)
- `classdef ... end` / `properties ... end` / `methods ... end` / `events ... end` / `enumeration ... end`

`end` 在以下语境下是**表达式**(数组索引,**不是关键字**):

- `A(end)` / `A(1:end)` / `A(end, :)`
- `B{end}.field` / `s.field(end)`

**区分启发**(本 Task 用):

> 维护括号嵌套深度计数器 `depth = ( count + [ count + { count`。
> - 遇到 `(`/`[`/`{` → depth++
> - 遇到 `)`/`]`/`}` → depth--
> - 遇到 `end` 标识符:
>   - 若 `depth > 0` → 是数组索引,**不是块结束**
>   - 若 `depth == 0` → 是块结束关键字
>
> 配合"语句块开始标记"栈(`function` / `if` / `for` / `while` / `switch` / `try` / `arguments` / `classdef` / `properties` / `methods` / `events` / `enumeration`),每遇到一个 depth==0 的 `end` 弹栈一次。

**陷阱**:必须**先字符串占位符化**,否则字符串里的 `end` / 括号会被误算。

#### 坑 7:`function` 签名 5 种形式

```matlab
function out = name(in1, in2)         % 形式 1:1 out,N in
function [out1, out2] = name(in)      % 形式 2:多 out,N in
function name(in1, in2)               % 形式 3:0 out,N in
function name                         % 形式 4:0 out,0 in(无括号)
function out = name                   % 形式 5:1 out,0 in(无括号)
```

**陷阱**:形式 4 / 5 没有 `()`,纯靠 `function name` 后跟换行(允许 `%` 注释和空白)识别。

正则示意(允许续行 `...` 已被预处理折叠):

```python
FUNCTION_SIG_RE = re.compile(
    r'^\s*function\s+'
    r'(?:'
        r'(?P<outs_bracket>\[[^\]]*\])\s*=\s*'    # 形式 2: [out1, out2] =
        r'|'
        r'(?P<out_single>\w+)\s*=\s*'              # 形式 1 / 5: out =
    r')?'
    r'(?P<name>\w+)'                                # 函数名
    r'(?:\s*\((?P<inputs>[^)]*)\))?'                # 可选输入参数 ( ... )
    r'\s*(?:%.*)?$',                                # 可选行尾注释
    re.MULTILINE,
)
```

输入参数列表:按逗号分割 + strip 每个名字(可能有 `~` 占位符,表示忽略,本 Task 保留 `~` 字符串)。
输出参数列表:形式 1 → 单个名字;形式 2 → 去掉方括号后按逗号分割 + strip;形式 3 / 4 → 空列表;形式 5 → 单个名字。

#### 坑 8:`arguments` 验证块(R2019b+,docstring 提取的干扰因素)

```matlab
function y = myFunc(x, opts)
    arguments
        x (1,1) double {mustBePositive}
        opts.Method (1,1) string = "default"
    end
    % This is the docstring, but the arguments block above can confuse extraction.
    y = x^2;
end
```

实现建议:docstring 提取时,**跳过** function 行后紧跟的 `arguments ... end` 块(如果有),从 `arguments` 块结束的下一行开始找连续 `%` 注释作为 docstring。

### 4. `file_role` 分类规则(精确定义)

```python
def classify_file_role(preprocessed_code: str) -> str:
    """分类 .m 文件角色为 script / function / class。

    扫描预处理后的代码(已剥离注释、续行、字符串占位符化),
    找第一个非空白行,看其第一个 token:

    - 'function' 关键字 → 'function'
    - 'classdef' 关键字 → 'class'
    - 其他(任何表达式 / 赋值 / 控制流 / 函数调用)→ 'script'

    Returns:
        "script" | "function" | "class"
    """
```

边界 case:

- 文件全空 → `"script"`(空 script,合法)
- 文件只有注释 → `"script"`(纯注释脚本,合法)
- 文件以续行表达式开头 → `"script"`(任何表达式 = script)
- 文件以 `function name` 开头但后面跟 `end`(单 function 文件)→ `"function"`
- 文件以 `function name` 开头但后面又有 top-level 语句(MATLAB R2016b+ 允许 script 文件含 local function,但 local function 不能在 script 顶部)→ **应该判 `"function"`**,因为第一个 token 是 `function`

### 5. function 块提取规则(GPT 二审采纳:line_map 行号回填 + docstring 来源)

```python
def extract_functions(
    preprocessed_code: str,
    line_map: dict[int, tuple[int, int]],  # processed_line -> (original_start, original_end),1-based
    original_lines: list[str],              # 原始 .m 文件按行切分(1-based 索引,index 0 留空或填 "")
) -> list[MFunction]:
    """提取 top-level function 列表。

    1. 扫描预处理代码,找所有 `^\\s*function` 行
    2. 对每个 function,提取签名(用 FUNCTION_SIG_RE)
    3. 从 function 行向下追踪 `end` 配对(用坑 6 的嵌套深度启发),
       找到对应的块结束行
    4. **仅保留 top-level function**(不在另一个 function 内部)
    5. 提取 docstring:**从 `original_lines` 中提取**(GPT round-2 采纳)——
       function 起始行的原始行号 + 1 开始,跳过 arguments 块(若存在),
       找第一段连续 `%` 注释。**绝对禁止**从已剥离单行注释的 preprocessed code
       提取 docstring,否则所有 docstring 都会是 `None`(因为 % 行已经被剥光了)
    6. **`line_range` 必须用原始文件行号**:processed_line_index 通过
       `line_map` 翻译回 (original_start, original_end) 填入 `MFunction.line_range`,
       **绝对禁止**直接使用 folded code 的行号

    Returns:
        list[MFunction]
    """
```

**关键纪律**(GPT 二审 round-2 采纳:line_map 形态升级 + docstring 来源):

#### 5.1 line_map 必须是 tuple,不是单一 int

`_m_lex` 模块的预处理流程(详见接口契约 3 节"5 步顺序")步骤 4 续行折叠会把**多行 `...` 表达式合成一行**。这意味着**一个 processed line 可能源自原始代码的多行**,单一 `dict[int, int]` 不够用,**必须**是 `dict[int, tuple[int, int]]`(processed line → 原始起始行 + 原始结束行)。

举例:

```
原始 .m 文件(1-based):
  10: function [a, b] = longFunc(x, ...
  11:                            y, ...
  12:                            z)
  13:    % docstring
  14:    a = x + y + z;
  15:    b = x * y;
  16: end

folded code(行号被压缩):
  1:  function [a, b] = longFunc(x, y, z)   ← 源自原始 10-12 行
  2:     % docstring                        ← 源自原始 13 行
  3:     a = x + y + z;                     ← 源自原始 14 行
  4:     b = x * y;                         ← 源自原始 15 行
  5:  end                                   ← 源自原始 16 行

line_map(1-based,tuple 形态):
  {1: (10, 12), 2: (13, 13), 3: (14, 14), 4: (15, 15), 5: (16, 16)}

function 起始 processed_line=1,line_map[1] = (10, 12),取 [0]=10 作为起始
function 结束 processed_line=5,line_map[5] = (16, 16),取 [1]=16 作为结束
MFunction.line_range == (10, 16)  ← 正确!
```

如果用旧的 `dict[int, int]` 单一映射,这条 function 会被错误填成 `line_range = (10, 16)` 或 `(12, 16)` 之类——**起始行号丢失了原始 `function` 关键字所在的真正第一行**。

#### 5.2 docstring 必须从 original_lines 提取(GPT round-2 提醒的真实陷阱)

预处理 5 步顺序的步骤 3 会**剥掉所有单行 `%` 注释**。如果你在 folded code 上找 docstring,会发现 function 行下面**所有 `%` 注释都没了**——所有 docstring 都会是 `None`。

正确做法:

```python
def _extract_docstring(
    original_lines: list[str],
    function_start_original_line: int,
) -> str | None:
    """从原始文件行中提取 docstring。

    Args:
        original_lines: 原始 .m 按行切分,1-based(index 0 为占位)
        function_start_original_line: function 关键字所在原始行号(1-based)

    Returns:
        docstring 字符串(多行连续 % 注释拼接,去掉 % 和前导空白),或 None
    """
    # 从 function 行 + 1 开始往下扫
    i = function_start_original_line + 1
    # 跳过 arguments 块(如果存在)
    if i < len(original_lines) and original_lines[i].strip().startswith('arguments'):
        # 找到对应 end,跳过整个 arguments 块
        ...
    # 跳过空行
    while i < len(original_lines) and original_lines[i].strip() == '':
        i += 1
    # 收集连续 % 注释
    doc_lines = []
    while i < len(original_lines):
        line = original_lines[i].strip()
        if line.startswith('%') and not line.startswith('%{') and not line.startswith('%%'):
            doc_lines.append(line.lstrip('%').strip())
            i += 1
        else:
            break
    return '\n'.join(doc_lines) if doc_lines else None
```

#### 5.3 单元测试硬要求

单元测试至少覆盖以下两个 case:

- **case A**:含 `...` 续行的多行 function 签名,验证 `line_range[0]` 等于原始 `function` 关键字所在行号,`line_range[1]` 等于原始 `end` 所在行号
- **case B**:function 行下方有 docstring 注释,验证 `docstring` 字段非 None 且内容为原始注释文本(去掉 `%` 前缀)。如果 Codex 把 docstring 从 preprocessed code 提取,这个 case 会失败

#### 5.4 `_m_lex` 模块输出契约

```python
def preprocess(raw_code: str) -> tuple[str, dict[int, tuple[int, int]]]:
    """返回 (folded_code, line_map)。

    line_map[i] = (orig_start, orig_end),都是 1-based 行号:
      - i 是 folded_code 中的行号
      - orig_start / orig_end 是原始 raw_code 中,该 processed 行所覆盖的起始 / 结束行
      - 单行情况下 orig_start == orig_end
      - 续行折叠后 orig_start < orig_end
    """
```

边界 case:

- function 没有显式 `end`(MATLAB script 模式):该 function 范围从 `function` 行到**下一个 top-level `function` 行的前一行**,或文件末尾
- nested function:**不**加入结果列表
- 多个 top-level function(MATLAB 允许多个 local function 跟在主 function 后):**全部**加入列表,顺序按出现顺序

### 6. `imports` 识别规则

```python
IMPORT_RE = re.compile(r'^\s*import\s+([\w.]+(?:\.\*)?)\s*;?\s*(?:%.*)?$', re.MULTILINE)

def extract_imports(preprocessed_code: str) -> list[str]:
    """提取 import 语句目标列表。

    MATLAB `import` 语法:
        import pkg.ClassName
        import pkg.subpkg.*
        import containers.Map

    Returns:
        list[str],去重后保持出现顺序。
    """
```

注意:MATLAB `import` 只在当前 function 作用域有效(不像 Python 全局),但本 Task **不区分作用域**,所有 `import` 语句的目标合并去重返回。

### 7. `uses_toolbox` 启发式识别规则(白名单,GPT 二审采纳:精度增强)

维护一个白名单 dict,扫预处理后的代码。**只放高置信函数**(toolbox 专属、base MATLAB 不带),避免基础函数误归类:

```python
TOOLBOX_FUNCTIONS: dict[str, set[str]] = {
    # 注:每个 toolbox 只放"高置信"函数,base MATLAB 自带的(fft / ifft / filter / xcorr 等)
    # 不算作 toolbox 强证据。GPT 二审实战指出 fft 在 base MATLAB 就有,
    # 把它归 Signal Processing 会让任何用 fft 的脚本被误判。

    "Control System Toolbox": {
        "tf", "zpk", "ss", "feedback", "series", "parallel",
        "bode", "nyquist", "rlocus", "lsim",
        "pid", "pidtune", "margin", "stepinfo", "pole", "zero",
        # 注:"step" / "impulse" 在 base MATLAB 也可用(timeseries 对象),
        # 这里只列 Control System Toolbox 强证据函数。
    },
    "Signal Processing Toolbox": {
        # 删除 fft / ifft / filter(base MATLAB 函数)
        "designfilt", "butter", "cheby1", "cheby2", "ellip",
        "freqz", "spectrogram", "pwelch", "xcorr",
        "resample", "decimate", "upfirdn",
    },
    "Communications Toolbox": {
        # GPT 二审建议补:通信专业必需
        "qammod", "qamdemod", "pskmod", "pskdemod",
        "awgn", "berawgn", "rcosdesign", "scatterplot",
        # 包名形态(detect_toolboxes 同时支持函数调用形态和 pkg.Class 形态)
        "comm.AWGNChannel", "comm.PSKModulator", "comm.QAMDemodulator",
    },
    "Optimization Toolbox": {
        # GPT 二审建议补:控制 / 参数辨识 / 论文仿真常见
        "optimoptions", "fmincon", "fminunc",
        "lsqnonlin", "lsqlin", "quadprog", "linprog", "fsolve",
    },
    "System Identification Toolbox": {
        # GPT 二审建议补:控制方向常见
        "iddata", "tfest", "ssest", "arx", "n4sid",
    },
    "Simulink": {
        "sim", "set_param", "get_param", "find_system", "add_block",
        "open_system", "close_system", "save_system", "new_system",
    },
    "DSP System Toolbox": {
        # 全部包名形态,本身已含点号,无误报风险
        "dsp.LMSFilter", "dsp.FIRFilter", "dsp.SpectrumAnalyzer",
        "dsp.AudioFileReader", "dsp.AudioFileWriter", "dsp.SineWave",
    },
    "Simscape Electrical": {
        "ee.getModelVariants", "ee.getNetlistVariants",
    },
    "Motor Control Blockset": {
        "mcb_getTrajectory", "mcb_calculateRsLq",
        "mcb.internal",
    },
    "Fixed-Point Designer": {
        # GPT 二审建议补:嵌入式 / 电机控制 / DSP demo 常见(C2000 工程必有)
        # 注:fi 字符太短易误报,只匹配"函数调用形态" fi(...)
        "fi", "fimath", "numerictype",
    },
    "Embedded Coder": {
        "rtwbuild", "slbuild", "codegen",
        "rtw.connectivity",
    },
}


def detect_toolboxes(preprocessed_code: str) -> list[str]:
    """启发式检测代码使用的 toolbox(GPT 二审采纳:精度增强)。

    匹配策略分两种(避免裸词匹配导致变量名误报):

    1. **函数名形态**(不含点号,如 `tf` / `fi`):
       必须紧跟左括号 `(` 才算命中——`tf(s)` 命中,`tf = 0.01` 不命中。
       正则:`\\b<name>\\s*\\(`

    2. **包名 / 类名形态**(含点号,如 `dsp.LMSFilter` / `mcb.internal`):
       点号本身已避免与普通变量名混淆,用裸词匹配即可。
       正则:`\\b<name>\\b`

    Returns:
        list[str],按 TOOLBOX_FUNCTIONS dict 中的 key 顺序,去重。
    """
    result: list[str] = []
    for toolbox_name, func_names in TOOLBOX_FUNCTIONS.items():
        for func in func_names:
            if '.' in func:
                # 包名形态:裸词匹配
                pattern = r'\b' + re.escape(func) + r'\b'
            else:
                # 函数名形态:必须跟左括号
                pattern = r'\b' + re.escape(func) + r'\s*\('
            if re.search(pattern, preprocessed_code):
                result.append(toolbox_name)
                break  # 同 toolbox 命中一次即可,扫下一个 toolbox
    return result
```

**已知缺陷**:白名单覆盖不全,真实 MATLAB 工程可能用很多 toolbox 函数本白名单未列(如 Image Processing / Symbolic Math 等)。**本 Task 接受这个缺陷**,验收只检查"命中的 toolbox 必须正确",不要求"必须命中所有应该命中的 toolbox"。Phase 2 可扩展白名单。

### 7.1 classdef 守卫(GPT round-2 采纳:测试集 0 classdef,必须靠实现守住)

测试集 4 个工程 0 个 classdef 文件,所以**真实工程测试无法守住 classdef 处理正确性**——必须靠实现层 short-circuit + 单元测试守住。

**实施纪律**:`MParserImpl.parse()` 中,**必须在调用 `extract_functions()` 之前先检查 `file_role`**:

```python
def parse(self, m_file_path: str) -> MFile:
    # ... 前面词法预处理略 ...
    role = classify_file_role(folded)
    if role == "class":
        # classdef short-circuit:不展开 methods,functions 直接置空
        funcs: list[MFunction] = []
    else:
        funcs = extract_functions(folded, line_map=line_map, original_lines=original_lines)
    # ... 后面组装 MFile 略 ...
```

**为什么需要这个守卫**:如果 `extract_functions()` 无脑扫所有 `^\s*function` 行,classdef 内 methods 块里的 `function y = run(obj, x)` 会被当成 top-level function 提取出来,然后 `MFile.functions` 里就出现了一个不该有的 `MFunction(name="run", ...)`,污染下游 ProjectGraph 构建。

实施有两种选择(详见 GPT round-2 反馈):

- **选项 A(推荐,MCS 阶段更简单)**:在 `m_parser.py` 主入口做 short-circuit,如上代码所示
- **选项 B**:在 `_m_structure.extract_functions()` 内部维护 classdef 嵌套栈,深度 > 0 时跳过 function。**实现复杂,本 Task 不必这么做**

验收第 7 项单元测试已加 classdef 守卫断言(`file_role == "class"` 且 `functions == []`),即使 methods 块内有 function 也不允许提取。

### 8. 11 个 .m 文件预期分类矩阵(本 Task **核心验收依据**)

**注意**:以下预期基于"文件名 + 大小"的启发式预估,Codex 实施前**第一件事**应 cat 实际文件前 30 行验证。**若实际不符,停手抛冲突给 PM**,不要默默调整断言。

#### 工程 1(`01_pmsm_foc_c2000.zip`,5 个 .m,合计 ~20KB)

| 文件相对路径 | 预期 file_role | 预期 top-level functions 数 | 备注 |
|---|---|---|---|
| `FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample.m` | `script` | 0 | Live Script 导出格式,与工程同名 |
| `mcb_c2000_pmsm_offset_data.m` | `script` | 0 | `_data` 后缀,参数初始化 |
| `mcb_pmsm_foc_f280049C_data.m` | `script` | 0 | F280049C 芯片参数 |
| `mcb_pmsm_foc_f28335_data.m` | `script` | 0 | F28335 芯片参数 |
| `mcb_pmsm_foc_qep_f28035_data.m` | `script` | 0 | F28035+QEP 芯片参数 |

工程 1 小计:5 script + 0 function + 0 class。

#### 工程 2(`02_buck_voltage_control.zip`,4 个 .m,合计 ~4KB)

| 文件相对路径 | 预期 file_role | 预期 top-level functions 数 | 备注 |
|---|---|---|---|
| `BuckVoltageControlData.m` | `script` | 0 | `Data` 后缀,参数 |
| `BuckVoltageControlExample.m` | `script` | 0 | `Example` 后缀,Live Script 导出 |
| `BuckVoltageControlPlotVoltage.m` | `script` | 0 | 懒加载脚本:`if ~exist('simlog_...', 'var') → sim(...) → 画图`(v1.3 修订:实际不是 function,是脚本) |
| `simlogNeedsUpdate.m` | `function` | 1(名为 `simlogNeedsUpdate`,返回 bool) | 小辅助函数,486B |

工程 2 小计:3 script + 1 function + 0 class。

#### 工程 3(`03_pid_antiwindup.zip`,1 个 .m,~14KB)

| 文件相对路径 | 预期 file_role | 预期 top-level functions 数 | 备注 |
|---|---|---|---|
| `AntiWindupControlUsingAPIDControllerExample.m` | `script` | 0 | Example,Live Script 导出 |

工程 3 小计:1 script + 0 function + 0 class。

#### 工程 4(`04_lms_noise_cancel.zip`,1 个 .m,~3.5KB)

| 文件相对路径 | 预期 file_role | 预期 top-level functions 数 | 备注 |
|---|---|---|---|
| `AcousticNoiseCancellationLMSExample.m` | `script` | 0 | Example,Live Script 导出 |

工程 4 小计:1 script + 0 function + 0 class。

#### 总计

**11 个 .m 文件:10 script + 1 function + 0 class**。

分类正确率验收门槛:**11 / 11 全部正确**(架构总览第 6 节决策 4 授权"够用即可"不等于"接受 20% 错误",`docs/03_TASK_INDEX.md` Week 1 验收的"80% 正确"是面向旧版 10 个测试工程的宽松基线,本 Task 测试集仅 11 个文件且预期清晰,应**做到 100%**)。

如果 Codex cat 实际文件后发现某个文件实际不符预期(比如某个 `_data.m` 其实开头是 `function`),**停手抛冲突**,**不要**改测试断言绕过——这是规模太小不允许误差的清单。

#### v1.3 修订特别提醒:function 真实工程覆盖单薄

v1.3 修订后,11 个 .m 文件里**只有 `simlogNeedsUpdate.m` 一个是 function**。这意味着 `file_role == "function"` 分类逻辑和 top-level function 提取逻辑,**真实工程测试只能覆盖到这一个文件**(简单返回 bool 的 helper 函数)。

为了不让 function 分类逻辑"靠 1 个真实文件守住",**单元测试(验收第 7 项)必须强化 function 覆盖**:

- 至少覆盖 function 签名 5 种形式(已在原计划单元测试要求里,不变)
- 至少覆盖一个含 `arguments` 块的 function(R2019b+ 语法)
- 至少覆盖一个含多行续行 `...` 签名的 function(测 `line_range` 经 line_map 回填正确)
- 至少覆盖一个含 docstring 的 function(测 docstring 从 `original_lines` 提取,不是 preprocessed)
- 至少覆盖一个含 nested function 的文件(测 nested 不被加入 functions list)
- 至少覆盖一个含多个 local function 的文件(测都加入 list,不只第一个)

这些单元测试是 function 分类逻辑的**主要质量保证**,真实工程的 `simlogNeedsUpdate.m` 只是"端到端 sanity check"。

### 9. `conftest.py` 扩展骨架

`tests/adapters/parser/conftest.py` 中,**保留** TASK-102 已建的 `extracted_slx_projects` fixture 不动,**追加**:

```python
@pytest.fixture(scope='session')
def extracted_m_files(extracted_slx_projects: dict[str, list[Path]]) -> dict[str, list[Path]]:
    """复用 TASK-102 已解压的临时目录,扫描每个工程的 .m 文件,返回 dict[project_name, list[Path]].

    fixture 依赖 extracted_slx_projects(TASK-102 已建),确保 zip 只解压一次。
    """
    result: dict[str, list[Path]] = {}
    for project_name, slx_files in extracted_slx_projects.items():
        if not slx_files:
            result[project_name] = []
            continue
        # 工程根目录 = slx_files[0] 的祖先目录(在 conftest 解压结构中是 tmp/<project_stem>/<project_inner_folder>/)
        project_root = slx_files[0].parent
        # 实际 m 文件可能在子目录,用 rglob 兜底
        # 但 TASK-102 conftest 把整个 zip 解压在 tmp/<project_stem>/ 下,
        # m 文件路径形如 tmp/<project_stem>/<inner_folder>/*.m
        # 为稳健起见,从 tmp/<project_stem>/ 整个 rglob
        zip_extract_root = project_root.parent if project_root.parent != project_root else project_root
        m_files = sorted(zip_extract_root.rglob('*.m'))
        result[project_name] = m_files
    return result
```

**实施提示**:Codex 实施时**应先打印**(`print` + 测试时 `pytest -s`)看 `extracted_slx_projects` 返回的字典结构和实际路径,再决定 rglob 的根目录。TASK-102 conftest 用的是 `tmp_path_factory.mktemp('slx_samples_extracted')` 作为根,然后 `zip_path.stem` 作为子目录名,所以工程 1 的 m 文件路径形如:

```
<tmp>/slx_samples_extracted/01_pmsm_foc_c2000/FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample/mcb_*_data.m
```

`rglob('*.m')` 从 `<tmp>/slx_samples_extracted/01_pmsm_foc_c2000/` 出发能扫到所有 .m,这是正确做法。

### 10. 错误消息中文化清单

`MParseError` 抛出时**消息必须为中文**(对齐 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 9 节"MParseError → .m 文件解析失败,请检查文件编码"),建议消息模板:

| 触发场景 | 错误消息 |
|---------|---------|
| 文件不存在 | `f"找不到 .m 文件:{m_file_path}"` |
| 路径是目录而非文件 | `f"路径不是文件:{m_file_path}"` |
| 文件是二进制(NULL 字节占比 > 1%) | `f".m 文件解析失败:不是有效的文本文件({m_file_path})"` |
| 文件读取 IO 错误 | `f".m 文件读取失败:{m_file_path}({io_error})"` |
| 整文件结构无法识别 | (本 Task **不**主动抛这种;空文件 / 纯注释文件归为 script,合法) |

`MFile` 没有 `parse_warnings` 字段(参见接口契约第 1 段),所以单 function 签名失败等**可恢复**问题,处理方式是**跳过 + 不报告**,**不**抛 `MParseError`。

---

## 验收标准

> **所有命令在 Git Bash + 已激活的 `.venv` 内,在仓库根目录(`F:\mxa-tutor`)执行。**
> Codex 在 PR 描述里逐条勾选并贴每条命令的输出。
> 静态扫描类命令一律按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。

### 1. 文件全部创建

```bash
ls adapters/parser/m_parser.py adapters/parser/_m_lex.py \
   adapters/parser/_m_structure.py adapters/parser/_m_dependencies.py \
   tests/adapters/parser/test_m_parser_unit.py \
   tests/adapters/parser/test_m_parser_real.py \
   tests/adapters/parser/test_m_parser_errors.py
```

7 个文件全部存在,无 `No such file` 报错。

### 2. 不应被创建的文件确实没创建

```bash
ls adapters/parser/mat_reader.py adapters/parser/prj_parser.py \
   adapters/parser/zip_extractor.py 2>&1
```

期望:全部 `No such file or directory`(那些是后续 Task 的事)。

### 3. 没有引入新依赖

```bash
git fetch origin main
git diff origin/main..HEAD --name-only -- requirements.txt requirements-dev.txt pyproject.toml
```

期望:**无输出**(本 Task 完全不动这三个文件)。

### 4. `adapters/parser/` 内部不 import 任何第三方库

```bash
grep -rn "^import\|^from" adapters/parser/_m_lex.py adapters/parser/_m_structure.py \
  adapters/parser/_m_dependencies.py adapters/parser/m_parser.py \
  --exclude-dir=".venv" --exclude-dir=".git" \
  | grep -vE "(^[^:]+:[0-9]+:)(import|from) (core\.|adapters\.parser\.|abc|dataclasses|datetime|enum|typing|pathlib|io|re|os|sys)"
```

期望:**无输出**(允许的 import:`core.*` / `adapters.parser.*` 内部模块、Python 标准库 `abc` / `dataclasses` / `datetime` / `enum` / `typing` / `pathlib` / `io` / `re` / `os` / `sys`)。

### 5. core/ 完全没动

```bash
git diff origin/main..HEAD --name-only -- core/
```

期望:**无输出**(本 Task 不动 core/)。

### 6. TASK-102 已建的 .slx 解析文件完全没动

```bash
git diff origin/main..HEAD --name-only -- \
  adapters/parser/slx_parser.py \
  adapters/parser/_slx_zip.py \
  adapters/parser/_slx_xml.py \
  adapters/parser/_slx_subsystem.py \
  adapters/parser/_slx_config.py \
  tests/adapters/parser/test_slx_parser_unit.py \
  tests/adapters/parser/test_slx_parser_real_p0.py \
  tests/adapters/parser/test_slx_parser_real_p1.py \
  tests/adapters/parser/test_slx_parser_errors.py
```

期望:**无输出**(本 Task 不动 TASK-102 已建文件,仅扩展 `__init__.py` / `README.md` / `conftest.py` 这三个文件)。

### 7. 单元测试全绿

```bash
pytest tests/adapters/parser/test_m_parser_unit.py tests/adapters/parser/test_m_parser_errors.py -v
```

期望:所有 `test_*` 通过,运行 < 3 秒。

单元测试至少覆盖以下场景(每个一条以上测试用例):

**词法预处理**:

- [ ] 块注释 `%{ %}` 独占行识别(剥离后不影响后续解析)
- [ ] 块注释 `%{ %}` 非独占行不识别为块注释(降级为单行注释)
- [ ] 单行注释 `%` 剥离(字符串内 `%` 不剥离)
- [ ] 续行 `...` 折叠(字符串内 `...` 不折叠)
- [ ] 单引号字符串 `'...'` 识别
- [ ] 单引号转义 `''` 识别
- [ ] 双引号字符串 `"..."` 识别
- [ ] `'` 转置 vs 字符串区分(至少 3 个 case:`A'` 转置、`'hello'` 字符串、`[A B]'` 转置)
- [ ] `end` 块结束 vs 数组索引区分(至少 2 个 case:`A(end)` 索引、`if x; ...; end` 块结束)

**`line_map` 形态(GPT round-2 采纳)**:

- [ ] `line_map` 类型是 `dict[int, tuple[int, int]]`,不是 `dict[int, int]`(可写一个直接断言 `line_map` 返回值类型的测试)
- [ ] **续行折叠后 line_map 正确**:输入一个含 `function y = f(x, ...\n            z)\n y=x+z;\n end` 的 .m,验证 folded line 1 的 `line_map[1] == (1, 2)`(覆盖原始 1-2 行),`line_map` 后续行依次推

**结构提取**:

- [ ] `function` 签名 5 种形式(每种至少一个 case)
- [ ] `arguments` 块识别(在 docstring 提取时被跳过)
- [ ] `file_role` 分类 3 种:script / function / class(每种至少一个 case)
- [ ] top-level function 提取(单 function 文件 / 多 local function 文件)
- [ ] nested function 不提取(只识别 top-level)
- [ ] anonymous function 不提取(`f = @(x) x.^2;` 不进 functions list)
- [ ] **续行 function 签名的 `line_range` 正确**(GPT round-2 采纳):输入 `function y = f(x, ...\n            z)\n y=x+z;\n end`(原始 4 行),验证 `MFunction.line_range == (1, 4)`,即起始等于原始 `function` 行号,结束等于原始 `end` 行号;**不是** folded 后的 (1, 3)
- [ ] **docstring 提取从原始行**(GPT round-2 采纳):输入 `function y = f(x)\n  % This is the doc\n  y = x+1;\n end`,验证 `MFunction.docstring` 非 None 且内容含 "This is the doc"。如果 Codex 从 preprocessed code 提取(% 行已被剥光),这个 case 会失败
- [ ] 单 function 签名解析失败时跳过(不影响其他 function,且**不**在 `MFile` 任何字段汇报)

**classdef 守卫(GPT round-2 采纳:测试集 0 classdef,必须靠 unit test 守住)**:

- [ ] classdef 文件:`file_role == "class"` 且 `functions == []`,**即使** methods 块内有 `function` 行也**不**提取。输入示例:
  ```matlab
  classdef MyClass
      methods
          function y = run(obj, x)
              y = x + 1;
          end
      end
  end
  ```
  断言 `mfile.file_role == "class"` 且 `mfile.functions == []`(空列表,**不是** `[MFunction(name="run", ...)]`)
- [ ] classdef 文件含多个 method 块(`methods (Static)` / `methods (Access = private)` 等),验证 `functions == []`

**imports / toolbox 启发式**:

- [ ] `import pkg.Class` 识别
- [ ] `import pkg.*` 识别

**toolbox 高置信命中样例(GPT round-2 采纳,每个 toolbox 至少 1 例)**:

- [ ] Control System:`sys = tf([1], [1 2 1]);` → `uses_toolbox` 含 `"Control System Toolbox"`
- [ ] Signal Processing:`[pxx, f] = pwelch(x);` → `uses_toolbox` 含 `"Signal Processing Toolbox"`
- [ ] Simulink:`sim("modelName");` → `uses_toolbox` 含 `"Simulink"`
- [ ] DSP System:`lms = dsp.LMSFilter(...);` → `uses_toolbox` 含 `"DSP System Toolbox"`
- [ ] Communications:`y = qammod(data, 16);` → `uses_toolbox` 含 `"Communications Toolbox"`
- [ ] Optimization:`opts = optimoptions("fmincon");` → `uses_toolbox` 含 `"Optimization Toolbox"`
- [ ] System Identification:`data = iddata(y, u, Ts);` → `uses_toolbox` 含 `"System Identification Toolbox"`
- [ ] Fixed-Point Designer:`x = fi(0.5, 1, 16, 12);` → `uses_toolbox` 含 `"Fixed-Point Designer"`

**toolbox 误报排除样例(GPT round-2 采纳,关键)**:

- [ ] `tf = 0.01;` → `uses_toolbox` **不**含 Control System Toolbox(变量名 `tf` 不是函数调用)
- [ ] `filter = 3;` → `uses_toolbox` **不**含 Signal Processing(`filter` 此处是变量名;但注意:`filter` 已经从白名单删除,所以这条本来就不该命中)
- [ ] `my_tf_value = 1;` → `uses_toolbox` **不**含 Control System(子串包含但不是 token 边界)
- [ ] `fi = 5;` → `uses_toolbox` **不**含 Fixed-Point Designer(变量名 `fi`,不是 `fi(...)` 调用)

### 8. 11 个 .m 真实工程测试矩阵(**全部 PASSED**)

```bash
pytest tests/adapters/parser/test_m_parser_real.py -v
```

**所有测试 PASSED**,具体断言对齐"接口契约"小节第 8 段"11 个 .m 文件预期分类矩阵":

#### 工程 1(`01_pmsm_foc_c2000.zip`,5 个 .m)

- [ ] `FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `mcb_c2000_pmsm_offset_data.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `mcb_pmsm_foc_f280049C_data.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `mcb_pmsm_foc_f28335_data.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `mcb_pmsm_foc_qep_f28035_data.m`:`file_role == "script"`, `len(functions) == 0`

#### 工程 2(`02_buck_voltage_control.zip`,4 个 .m)

- [ ] `BuckVoltageControlData.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `BuckVoltageControlExample.m`:`file_role == "script"`, `len(functions) == 0`
- [ ] `BuckVoltageControlPlotVoltage.m`:`file_role == "script"`, `len(functions) == 0`(v1.3 修订:Codex 实施前 dump 抓到,该文件实际是懒加载脚本而非 function)
- [ ] `simlogNeedsUpdate.m`:`file_role == "function"`, `len(functions) >= 1`, 第一个 function 的 `name == "simlogNeedsUpdate"`

#### 工程 3(`03_pid_antiwindup.zip`,1 个 .m)

- [ ] `AntiWindupControlUsingAPIDControllerExample.m`:`file_role == "script"`, `len(functions) == 0`

#### 工程 4(`04_lms_noise_cancel.zip`,1 个 .m)

- [ ] `AcousticNoiseCancellationLMSExample.m`:`file_role == "script"`, `len(functions) == 0`

#### 通用断言(所有 11 个 .m 文件)

- [ ] 每个 .m parse 成功(不抛 `MParseError`)
- [ ] 每个 `MFile.file_path` 非空且对得上输入路径
- [ ] 每个 `MFile.raw_code` 非空(`len(raw_code) > 0`,因为 11 个 .m 都不是空文件)
- [ ] 每个 `MFile.imports` 是 `list[str]`(可空)
- [ ] 每个 `MFile.uses_toolbox` 是 `list[str]`(可空,**类型正确即可,不要求命中**)
- [ ] **不**要求"11 个 .m 中至少 1 个文件命中至少 1 个 toolbox"——白名单变保守后,实际可能因白名单覆盖不全而完全不命中,这是 toolbox 启发式的已知缺陷,**不**反映 parser 错误。Toolbox 命中精度由单元测试(验收第 7 项的高置信样例 + 误报样例)覆盖,**不在真实工程测试中硬断言命中**(GPT round-2 采纳)

**真实工程验收 = 11 / 11 文件全部通过。任一文件未通过,本 Task 打回返工。**

### 9. 错误处理测试全绿

```bash
pytest tests/adapters/parser/test_m_parser_errors.py -v
```

期望:全部通过,包括以下场景:

- [ ] 输入文件不存在 → `MParseError`,消息含 `"找不到 .m 文件"`
- [ ] 输入路径是目录 → `MParseError`,消息含 `"路径不是文件"`
- [ ] 输入文件是二进制(构造一个含大量 NULL 字节的 .m)→ `MParseError`,消息含 `"不是有效的文本文件"`
- [ ] 输入文件是 GBK 编码且含中文注释(GPT 二审采纳)→ **不**抛异常,bytes-first 策略命中 GBK 解码,`raw_code` **正确保留中文**(断言:`"参数" in mfile.raw_code` 或类似),不是 `\ufffd` 替换字符
- [ ] 输入文件是 UTF-8 with BOM(`\xef\xbb\xbf` 开头)(GPT 二审采纳)→ `utf-8-sig` 自动剥离 BOM,`file_role` 分类正确(`function name` 文件的 `file_role` 应为 `"function"`,不能因为 BOM 让第一个 token 识别失败)
- [ ] 输入文件编码异常(连 GBK 都失败的怪异编码)→ 用 `errors='replace'` 容错,`MFile.raw_code` 保留替换字符,**不**抛异常
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
wc -l adapters/parser/_m_*.py adapters/parser/m_parser.py \
  tests/adapters/parser/test_m_parser_*.py | sort -n | tail -10
```

期望:最长的文件 ≤ 300 行(`_m_structure.py` 可能最长,预计 ~250 行)。**若某文件超 300 行,Codex 必须拆分**。

### 12. `adapters/parser/__init__.py` 已扩展

```bash
cat adapters/parser/__init__.py
```

期望:含以下两行(顺序不限,但都要有):

```python
from adapters.parser.slx_parser import SlxParserImpl   # TASK-102 已建
from adapters.parser.m_parser import MParserImpl       # 本 Task 新增
```

并 `__all__ = ['SlxParserImpl', 'MParserImpl']`(或等价写法,允许后续 Task 继续追加)。

### 13. `adapters/parser/README.md` 已更新

```bash
cat adapters/parser/README.md
```

期望:在 TASK-102 段落基础上**追加**一段说明本 Task 新增的 4 个 `_m_*` 模块及其一句话职责,以及 `MParserImpl` 的对外用法 1-2 行示例。

### 14. `tests/adapters/parser/conftest.py` 已扩展

```bash
grep -n "extracted_m_files" tests/adapters/parser/conftest.py
```

期望:看到 `extracted_m_files` fixture 已定义(详见"接口契约"小节"conftest 扩展骨架")。

并 TASK-102 已建的 `extracted_slx_projects` fixture **完全未改动**:

```bash
git diff origin/main..HEAD -- tests/adapters/parser/conftest.py | grep -E "^-" | grep -v "^---"
```

期望:**无输出**或仅极少行(理论上 conftest.py 只追加不删除,所以 `-` 行应该为 0;若有少量 `-` 行说明 Codex 调整了 fixture 签名,在 PR 描述里说明)。

### 15. `docs/03_TASK_INDEX.md` 状态已更新

```bash
grep -n "TASK-103" docs/03_TASK_INDEX.md
grep -n "Week 1:" docs/03_TASK_INDEX.md
```

期望:

- 看到 TASK-103 行状态为 🔍
- Week 1 进度条显示 `[✅✅🔍⬜⬜⬜⬜]`(本 Task 推到 🔍 后,3/7 数字不变)

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md`,本 Task 只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件。**改文件方式必须按决策 08 用字节级 Python 操作或编辑器手改,禁用 `read_text` / `write_text` / `sed -i`**。

### 16. 一键全检

```bash
make check
```

应输出 `All checks passed!`。

### 17. git 三件套(决策 08 硬要求)

Codex 在完工报告里**必须**附带以下三条命令的完整输出:

```bash
git status                              # 期望: working tree clean
git log --oneline main..HEAD            # 期望: 本 Task 的全部 commit 列表,非空
git push                                # 期望: 分支已推送到 origin/task/TASK-103-m-parser
```

不附 = 没完工,PM 退回让 Codex 补。

### 18. PR 元信息

- PR 标题:`TASK-103: .m 文件解析器`
- 分支名:`task/TASK-103-m-parser`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-17 项**并简述每项做了什么

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

# 改动 1:TASK-103 状态 🔲 → 🔍
old = '| TASK-103 | .m 文件解析器 | 🔲 | Codex | 101 |'.encode('utf-8')
new = '| TASK-103 | .m 文件解析器 | 🔍 | Codex | 101 |'.encode('utf-8')
assert old in data, 'TASK-103 row not found'
data = data.replace(old, new, 1)
assert new in data

# 改动 2:Week 1 进度条第 3 位 ⬜ → 🔍
# 注意:进度条字面值在小文档清洁 PR(commit cfe73b4)合并后,已经是
# [✅✅⬜⬜⬜⬜⬜],本 Task 推 🔍 后变成 [✅✅🔍⬜⬜⬜⬜]
old = '[✅✅⬜⬜⬜⬜⬜]'.encode('utf-8')
new = '[✅✅🔍⬜⬜⬜⬜]'.encode('utf-8')
assert old in data, 'Week 1 progress bar not in expected baseline state'
data = data.replace(old, new, 1)
assert new in data

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

确认 diff 只显示 2-3 行级别改动(1 个状态符 + 1 个 emoji),**不应**出现整文件红绿。若 diff 显示几百行变化,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 手改**。

### 风险 2:Codex 漏 git 操作(决策 08 重灾区)

TASK-101 实施时 Codex 写完代码、跑完 `make check`,**完全跳过 `git add` / `git commit` / `git push`**,PM 准备建 PR 时 `git status` 才发现 22 个文件 Untracked。**多花 30 分钟补救**。

本 Task 涉及 7 个新文件 + 4 个修改文件(`__init__.py` / `README.md` / `conftest.py` / `03_TASK_INDEX.md`),**Codex 必须在完工报告里附带 git 三件套输出**(`git status` working tree clean / `git log --oneline main..HEAD` 完整 commit 列表 / `git push` 推送成功)。不附 = 没完工。

### 风险 3:`'` 字符串 vs 转置歧义,字符串状态机优先级

`.m` 解析最常见的边界 case 来源。如果状态机没处理好,`'` 在不同位置可能被误判:

- `A = B';` 中的 `'` 是转置(B 是标识符)
- `A = 'B';` 中的 `'` 是字符串起始(`=` 是 op)
- `[1 2]'` 中的 `'` 是转置(`]` 是闭括号)
- `f('a')` 中的 `'` 是字符串(`(` 是开括号)

**本 Task 实施时的纪律**:

- **必须先字符串占位符化**(把所有 `'...'` 和 `"..."` 替换为 `__STR_N__` 占位符,N 是序号),**再**做 `function` / `end` / `classdef` 识别
- 占位符化时维护"上一个非空白 token"启发(详见接口契约坑 4)
- 接受边界 case 偶尔误判,**不影响**最终 `file_role` 分类和 top-level function 识别即可
- 单元测试至少覆盖坑 4 列出的 3 个 case,真实工程测试覆盖剩余边界

### 风险 4:`end` 一字多用,嵌套深度计数器陷阱

`end` 在以下场景必须正确区分:

- `A(end)` 索引(在 `()` 内,depth > 0)
- `function ... end` 块结束(depth == 0)
- `arguments x (1, end-1) double; end`(变态 case:`(1, end-1)` 里 end 是索引,行末 end 是块结束)

**本 Task 实施时的纪律**:

- 嵌套深度计数器必须正确处理 `(` `[` `{` 三种括号(都计入 depth)
- **必须先字符串占位符化**(否则字符串里的括号会被误算)
- 状态栈必须正确处理所有块开始标记:`function` / `if` / `for` / `while` / `switch` / `try` / `arguments` / `classdef` / `properties` / `methods` / `events` / `enumeration`
- 单元测试至少覆盖坑 6 列出的 2 个 case

### 风险 5:nested function 不递归,但要正确识别

MATLAB R2016b+ 允许 script 含 local function,且 function 内部允许 nested function。本 Task **只识别 top-level function**(不在另一个 function 内部),nested function 必须被识别但**不**加入 `MFile.functions`。

```matlab
function outer()
    function inner()       % nested,本 Task 不加入 functions list
        x = 1;
    end
    y = 2;
end

function localFunc()       % local function,本 Task 加入(在 outer 之后,top-level)
    z = 3;
end
```

**实施提示**:用栈追踪当前 function 嵌套深度,深度 == 0 时识别的 function 才加入 `MFile.functions`。

### 风险 6:docstring 提取被 `arguments` 块干扰(R2019b+)

```matlab
function y = f(x)
    arguments
        x (1,1) double
    end
    % This is the real docstring
    y = x * 2;
end
```

如果不跳过 `arguments` 块,docstring 提取会读到 `x (1,1) double` 那行(它在预处理后是表达式,不是 `%` 注释),所以 docstring 为 `None`(因为 function 行下方第一行不是 `%` 注释)。

**实施纪律**:docstring 提取时,**先**判断 function 体首段是否是 `arguments ... end` 块,如果是,跳过该块,从其后的第一行开始找连续 `%` 注释。

### 风险 7:`uses_toolbox` 白名单覆盖不全,接受为已知缺陷

白名单 dict(详见接口契约第 7 段)只覆盖常见 toolbox 的常见函数。真实 MATLAB 工程可能用:

- 不在白名单的 toolbox(如 Mapping Toolbox / Image Processing Toolbox / Symbolic Math)
- 已知 toolbox 的不常见函数

**本 Task 接受这个缺陷**(GPT round-2 采纳):**不**把"真实 11 个 .m 至少 1 个命中"作为硬验收门槛——白名单保守可能导致实际不命中,但这**不**反映 parser 错误。Toolbox 检测精度由单元测试(验收第 7 项)用高置信样例和误报样例守住,真实工程测试只验证 `uses_toolbox` 是 `list[str]` 类型正确、无异常。

Phase 2 可以扩展白名单,或改用更精确的方法(扫 MATLAB 标准 doc 自动生成全量映射),**不在本 Task 范围**。

### 风险 8:Codex 误改 TASK-102 已建文件

本 Task 与 TASK-102 共享 `adapters/parser/` 和 `tests/adapters/parser/` 目录。Codex 可能"顺手优化" TASK-102 已建的某个 `_slx_*.py`,这是**严重违反"单一 Task 单一职责"**(宪法第 5 节)。

**实施纪律**:

- 本 Task 仅新增 `_m_*.py` 4 个文件 + 3 个 test_m_*.py 文件
- 本 Task 仅扩展(追加,不覆盖)`__init__.py` / `README.md` / `conftest.py` 3 个文件
- TASK-102 已建的 `slx_parser.py` / `_slx_*.py` / `test_slx_parser_*.py` **不允许动**
- 验收步骤 6 会检查这一条,Codex 应自查

### 风险 9:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。本 Task 验收清单已按规则给出命令,直接用。

### 风险 10:`MFile` 没有 `parse_warnings` 字段(与 `SlxModel` 不同)

容易被误以为 `MFile` 和 `SlxModel` 字段对称——但 TASK-101 契约里 **`MFile` 没有 `parse_warnings`**(查看 `core/domain/m_file.py` 验证)。所以解析中的可恢复异常,处理方式是:

- 单 function 签名失败 → 跳过该 function,**不**通过任何字段对外报告
- 编码异常 → bytes-first 策略 + `errors='replace'` 兜底,**不**抛异常
- 不要为了"对称美"而在本 Task 加 `parse_warnings` 字段——那是改契约,违反"单一 Task 单一职责"。如果**强烈认为**需要这个字段,**停手问 PM**,走宪法修订流程

**关于下游缺料的担忧(GPT 二审采纳)**:你可能会担心"跳过 function 不报告,下游 TASK-105 / TASK-107 缺料怎么办"。**不用担心**——架构总览第 2 节明确,`ProjectGraph` dataclass 有 `unresolved_symbols: list[str]` 字段(TASK-101 已建,见 `core/domain/project_graph.py`),专门收纳"扫到了但解析不到定义"的符号。TASK-105 做调用关系分析时,从 `MFile.raw_code` 扫到但 `MFile.functions` 里没有的函数调用,就归入 `unresolved_symbols`。也就是说,**架构层面已经有正确位置承接这类缺料,本 Task 不需要在 `MFile` 上加任何 warning 字段**。

**04 工程规范的 `parse_warnings` 是通用失败隔离原则,本 Task 局部例外**(GPT round-2 强调):

`docs/04_ENGINEERING_STANDARDS.md` 第 8.4 节"失败隔离"提到 `parse_warnings` / `unresolved_symbols` 作为**通用失败隔离原则**(适用于多个 parser)。但对 `MFile` 而言,**本 Task 以 TASK-101 契约为准**——`MFile` 没有 `parse_warnings` 字段,所以可恢复问题**不在 parser 输出中报告**。这是契约差异导致的**局部例外**,不是设计缺陷。后续未解析符号由 `ProjectGraph.unresolved_symbols` 在 TASK-107 层承接,各得其所。

**Codex 实施时若觉得"为了符合 04 第 8.4 节要给 MFile 补 parse_warnings"**——错了。04 是通用原则,TASK-101 是具体契约,**契约 > 通用原则**(冲突时以宪法/契约为准,详见 `docs/01_PROJECT_CONSTITUTION.md` 第 15 节)。停手问 PM 而不是默默改契约。

### 风险 11:测试 .m 文件路径解析

`tests/adapters/parser/conftest.py` 的 `extracted_m_files` fixture 依赖 TASK-102 已建的 `extracted_slx_projects`。但 .m 文件路径结构和 .slx 不同(.m 是 zip 直接解压在工程根目录,.slx 也在同一根目录),所以 fixture 用 `rglob('*.m')` 从 `<tmp>/slx_samples_extracted/<project_stem>/` 整个目录树扫描即可。

**实施提示**:Codex 实施时**先打印** `extracted_slx_projects` 的实际返回结构,再写 `extracted_m_files`,避免路径假设错误。

### 风险 12:Live Script 导出 .m 文件的注释格式

工程 1 / 3 / 4 的主入口 .m 文件(`*Example.m`)很可能是 MATLAB Live Editor 导出的脚本格式。这种文件:

- 顶部通常有大段 `%` 注释作为文档(Live Script 的 markdown 段)
- 可能含 `%%` 段分隔符(MATLAB script section break)
- 整体仍是 script(没有顶层 `function`),`file_role == "script"` 是正确分类

`%%` 是 MATLAB 的 section break,**本 Task 不需要特殊处理**——它在词法上就是"两个 `%` 后跟换行/注释",按普通单行注释处理即可,不影响 `file_role` 分类。

### 风险 13:工程 1 第一个文件名超长

`FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample.m`,文件名 67 字符,加上路径接近 130 字符。Windows 默认路径长度限制 260 字符,理论上够用,但**conftest 在 `tmp_path_factory` 临时目录解压时,完整路径可能接近极限**。

**应对**:TASK-102 已经成功跑过这个测试集,所以路径长度问题不会发生(已有实证)。本 Task 复用 TASK-102 的解压逻辑,沿用即可。

### 风险 14:编码读取策略错误会让中文注释全丢(GPT 二审采纳)

如果直接用 `Path.read_text(encoding='utf-8', errors='replace')` 读 `.m` 文件,**GBK 编码的 `.m`(MATLAB R2014b 之前的中文 Windows 默认 + 部分老工程导出文件)中所有中文注释会变成 `\ufffd` 替换字符**。

这是**产品级损失**——我们的目标用户是中文学生,后续教学讲解的核心材料之一就是 docstring 和注释里的中文(`% 速度环 PID 控制器初始化`、`% 电机参数:Rs=2.8Ω, J=0.001kg·m²` 这类)。中文丢了 → docstring 提取丢内容 → TeachingUnit 缺料 → LLM 讲解被迫从代码字面凭空生成,产品质量直接掉一档。

**应对**:接口契约 2.1 节定义了 bytes-first 策略——先 `read_bytes()`,做二进制检测,再按 `utf-8-sig` → `utf-8` → `gbk` → `errors='replace'` 优先级尝试解码。这套策略覆盖 99% 的真实输入:

- `utf-8-sig`:Windows 编辑器生成的 BOM 文件
- `utf-8`:标准 UTF-8(MATLAB R2014b+ 现代版本默认)
- `gbk`:中文 Windows 老工程
- `errors='replace'`:其他怪异编码兜底

验收标准第 9 项已经把"GBK 中文注释保留"和"UTF-8 BOM 自动剥离"作为硬测试加进去,Codex 必须通过。

---

## 估时

预估 **8-12 小时**:

- 阅读 11 个 .m 实际内容 + 设计模块拆分:0.5-1 小时
- `_m_lex.py` 词法预处理 + 单元测试:2-3 小时(`'` 转置 vs 字符串状态机是最重的)
- `_m_structure.py` file_role + function 提取 + 单元测试:2-3 小时(`end` 嵌套深度计数器)
- `_m_dependencies.py` imports + toolbox 白名单 + 单元测试:1 小时
- 11 个真实 .m 联调(必然有边界 case 需要兼容):1-2 小时
- 错误处理 + 错误消息中文化 + 测试:0.5 小时
- README / `__init__.py` / conftest 扩展 / commit 拆分 / PR 描述 / 三件套确认:0.5-1 小时

比 TASK-101(4-6 小时)长,比 TASK-102(10-15 小时)短。.m 解析比 .slx 简单(没有 ZIP/XML 处理),但 MATLAB 语法的状态机更"刁钻"。

---

## 给 Codex 的提示

### 1. 先看 11 个 .m 实际内容,再动手写代码

切分支后**第一件事**:解压 4 个 zip 后 cat 每个 .m 的前 30 行(只看,不修改测试集):

```bash
mkdir -p /tmp/m_probe
cd /tmp/m_probe
for z in /your/repo/tests/fixtures/slx_samples/0*.zip; do
  unzip -o "$z" "*.m" -d "$(basename $z .zip)"
done

for f in $(find . -name '*.m' | sort); do
  echo ""
  echo "============== $f =============="
  head -30 "$f"
done | less
```

确认本 Task 文档"接口契约"小节第 8 段"11 个 .m 文件预期分类矩阵"的预期与你实际看到的一致(看每个 .m 的第一个非注释行是 `function` / `classdef` 还是其他)。

**如果有任何文件实际不符预期(比如某个 `_data.m` 实际是 function 文件 / 某个 Example 实际含 local function)→ 停手问 PM**,不要默默改测试断言绕过。架构师写这份预期是基于文件名 + 大小的启发,**不是看了实际内容**,所以预期可能有误差,纪律保证你和我都能 catch 到。

### 2. 推荐实现顺序

1. **`_m_lex.py`** 词法预处理:`strip_block_comments(code)` / `strip_line_comments_outside_strings(code)` / `fold_continuations(code)` / `placeholder_strings(code) -> tuple[code_with_placeholders, dict[placeholder, original]]`。每个函数独立单元测试。
2. **`_m_structure.py`** 结构提取:`classify_file_role(preprocessed)` / `extract_functions(preprocessed, original_lines)` / `extract_function_signature(line)` / `extract_docstring(function_body_lines)`。逐个测试。
3. **`_m_dependencies.py`** 依赖识别:`extract_imports(preprocessed)` / `detect_toolboxes(preprocessed)`。简单,最后写。
4. **`m_parser.py`** 主入口:`MParserImpl.parse()` 串起整个流程。
5. **`tests/adapters/parser/conftest.py`** 扩展 `extracted_m_files` fixture(此时 TASK-102 conftest 应已能跑,你可以打印实际路径再写 fixture)。
6. **`tests/adapters/parser/test_m_parser_*.py`** 三个测试文件。

### 3. 先用工程 4 LMS 单文件把流程调通

工程 4 最简单(只有 1 个 .m,3.5KB,Live Script 导出),用它把 `MParserImpl.parse()` 调通:

```bash
pytest tests/adapters/parser/test_m_parser_real.py::test_lms_main -v
```

绿了再扩展到工程 3(1 个 .m)→ 工程 2(4 个,含 1 个真 function `simlogNeedsUpdate.m`)→ 工程 1(5 个 _data.m + 1 个主)。

### 4. Commit 拆分建议(Conventional Commits)

```
feat(parser): add .m lex preprocessor (comments, continuations, strings)
test(parser): add .m lex unit tests
feat(parser): add .m file_role classifier and function extractor
test(parser): add .m structure unit tests
feat(parser): add .m imports and toolbox detection
test(parser): add .m dependencies unit tests
feat(parser): add MParserImpl main entry
test(parser): add MParserImpl integration tests on 11 real .m files
test(parser): add .m parser error handling tests
test(parser): extend conftest with extracted_m_files fixture
chore(parser): export MParserImpl from adapters/parser/__init__.py
docs(parser): update adapters/parser/README with .m parser usage
docs: mark TASK-103 as in-review in task index
```

不要单个超大 commit 提交全部代码——每个 commit 单一职责,review 更轻松。

### 5. 文件拆分纪律

`docs/04_ENGINEERING_STANDARDS.md` 第 4 节"每文件 ≤ 300 行"是硬规定。若 `_m_structure.py` 写到 280 行还没收尾,**主动**拆出 `_m_structure_functions.py` / `_m_structure_role.py`,**不要**写到 320 行才发现违规。

### 6. 错误消息严格中文

`MParseError("file not found")` ❌ — 英文不行。
`MParseError("找不到 .m 文件:...")` ✅。

详见"接口契约"小节"错误消息中文化清单"。

### 7. 内部模块的 import

```python
# adapters/parser/m_parser.py
from adapters.parser._m_lex import strip_comments, fold_continuations, placeholder_strings
from adapters.parser._m_structure import classify_file_role, extract_functions
from adapters.parser._m_dependencies import extract_imports, detect_toolboxes
```

用绝对路径 import,**不**用相对 import(`from ._m_lex import ...`)。

### 8. 整体解析流程伪代码(GPT 二审采纳:bytes-first + 5 步预处理 + line_map)

整个解析流程的关键不变量:

- **第 1 步**:`.m` 文件用 **bytes-first** 策略读取,优先保住中文注释(GBK 兼容)
- **第 2-6 步**:按"接口契约 → 2.1 / 3. 预处理 5 步顺序"严格执行,不许颠倒
- **整个过程维护 `line_map`**:`processed_line -> (original_start_line, original_end_line)`(GPT round-2 采纳:tuple 形态而非单 int),用于回填 `MFunction.line_range`

```python
def parse(self, m_file_path: str) -> MFile:
    # 1. 读文件(bytes-first,详见接口契约 2.1)
    raw = read_m_file(m_file_path)   # utf-8-sig → utf-8 → gbk → replace
    original_lines = raw.splitlines()   # 用于 docstring 提取(不能从 preprocessed code 提取)

    # 2. 块注释剥离(保留行号:把 %{...%} 行替换为空行,不删行)
    after_block, line_map_1 = strip_block_comments_keep_lines(raw)

    # 3. 字符串占位符化(关键!后续步骤依赖)
    placeheld, str_map = placeholder_strings(after_block)

    # 4. 单行注释剥离(此时字符串已占位,% 一定是注释)
    after_line = strip_line_comments(placeheld)

    # 5. 续行折叠(此时字符串已占位,... 一定是续行)
    #    折叠会改变行数,line_map_2 记录 folded -> (orig_start, orig_end) 的 tuple 映射
    folded, line_map_2 = fold_continuations_with_map(after_line, line_map_1)

    # 6. 在 folded 上做结构分析
    role = classify_file_role(folded)

    # 6.1 classdef short-circuit(GPT round-2 采纳)
    #     测试集 0 classdef,Codex 必须在这里短路,否则 methods 块内 function 会被误提
    if role == "class":
        funcs: list[MFunction] = []
    else:
        # docstring 必须从 original_lines 提取(不是从 folded!),否则所有 docstring 都会是 None
        funcs = extract_functions(
            preprocessed_code=folded,
            line_map=line_map_2,
            original_lines=original_lines,
        )

    imports = extract_imports(folded)
    toolboxes = detect_toolboxes(folded)

    # 7. 组装 MFile,raw_code 用原始 raw(未预处理),保留所有内容
    return MFile(
        file_path=m_file_path,
        file_role=role,
        functions=funcs,
        imports=imports,
        uses_toolbox=toolboxes,
        raw_code=raw,
    )
```

**关键约束**(GPT round-2 强化):

- `MFile.raw_code` 必须是**未预处理**的原始字符串(用户可能要看到原代码做对照,不能给它"剥过注释的"版本)
- `MFunction.line_range` **绝对禁止**用 folded code 的行号——必须经 `line_map` 回填:起始用 `line_map[folded_func_line][0]`,结束用 `line_map[folded_end_line][1]`
- `MFunction.docstring` **绝对禁止**从 preprocessed code 提取——必须从 `original_lines` 提取。原因:预处理步骤 4 把所有 `%` 行剥光了,从 folded 找永远找不到 docstring,所有 docstring 会是 `None`
- 步骤 2 块注释剥离时,**把整行替换为空行(`\n`)而不是删除行**,这样行号不变,line_map 处理简化
- **classdef short-circuit**:`role == "class"` 时 `funcs = []`,不走 `extract_functions`,否则 methods 块内 `function` 会被误提

### 9. line_range / docstring 来源纪律(GPT 二审 round-2 强化)

这是最容易出 bug 的地方,Codex 写 `_m_lex` / `_m_structure` 模块时,**两条铁律**:

**(a) `line_map` 必须是 `dict[int, tuple[int, int]]`**(processed line → 原始起始行 + 结束行)

预处理 5 步顺序里:

- 步骤 1(块注释剥离):把 `%{ ... %}` 块内每行替换为空字符串(保留换行符),行号不变 → line_map 单行情况 `(i, i)`
- 步骤 2 / 3(字符串占位、单行注释剥离):**逐字符替换,不改变行数** → line_map 不变
- 步骤 4(续行折叠):`...\n` 替换为空格 → **行数减少**,**多行原始 → 单行 processed**,line_map 必须用 tuple 表达"这一行覆盖原始 (start, end)"

**(b) `MFunction.docstring` **必须**从 `original_lines` 提取,不是 folded code**

预处理步骤 3 会**剥光所有 `%` 行**。如果你在 folded code 上找 docstring,会发现 function 行下面没有任何 `%` 注释——所有 docstring 都会是 `None`。

正确做法:`extract_functions()` 在 folded 上识别出 function 起始/结束行,**通过 `line_map` 翻译回原始行号**,然后**从 `original_lines`** 找 function 起始行 + 1 之后的连续 `%` 注释作为 docstring。

`_m_structure.py::extract_functions` 签名:

```python
def extract_functions(
    preprocessed_code: str,                       # folded code
    line_map: dict[int, tuple[int, int]],         # processed -> (orig_start, orig_end)
    original_lines: list[str],                    # 原始 .m 按行切分
) -> list[MFunction]:
    ...
```

单元测试覆盖(详见验收第 7 项,GPT round-2 强制):

- 含 `...` 续行的多行 function 签名 → `line_range[0]` 等于原始 `function` 行,`line_range[1]` 等于原始 `end` 行
- function 行下方有 `%` docstring 注释 → `MFunction.docstring` 非 None,内容含原文。**如果 Codex 从 preprocessed code 提取,这个 case 必失败**——这就是测试用来守住实施纪律的

### 10. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见"风险与注意点"风险 1 的脚本骨架。改完后 `git diff docs/03_TASK_INDEX.md` 确认只显示 2-3 行级别改动。**若 diff 显示几百行变化,立即 `git checkout --` 撤销,换方式 A 用编辑器手改**。

### 11. 完工报告必须含 git 三件套(决策 08)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 三条命令的完整输出**(决策 08 第 1 条)
- 验收清单(本 Task 文档"验收标准"1-18 项)逐条勾选 + 说明
- PR 标题:`TASK-103: .m 文件解析器`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 12. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:

- PR 标题:`TASK-103: .m 文件解析器`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

PM 在 GitHub 网页手动创建 PR。CI 自动触发,绿了之后 PM 把 Codex 产出 + CI 结果交给架构师 review。

### 13. 遇冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / TASK-101 契约 / TASK-102 已建文件的任何冲突,**停手问 PM**,不要默默偏离。

常见可能冲突场景:

- 发现 `MFile` 字段需要新增 / 修改(尤其想加 `parse_warnings`)→ **不要改 TASK-101 已建的 dataclass**,问 PM 是否走宪法修订流程
- 发现 11 个 .m 中某个文件实际内容与本 Task 文档"预期分类矩阵"不符 → **不要硬扛**,告诉 PM 实际是什么,等架构师调整文档
- 发现需要修改 TASK-102 已建文件(除允许扩展的 `__init__.py` / `README.md` / `conftest.py` 之外)→ **不要动**,问 PM
- 发现需要引入第三方依赖(`matlab_parser` / `oct2py` / 任何)→ **停手**,本 Task 明确"无新依赖"

---

**版本**:Task 文档 v1.3
**作者**:Claude(架构师,第五任)
**日期**:2026-06-02
**修订记录**:
- v1.0(2026-06-02 初版):11 章结构,1296 行
- v1.1(2026-06-02 GPT 二审采纳 4 项):
  - 新增"接口契约 → 2.1 文件读取策略"(bytes-first + UTF-8 BOM + GBK 中文注释保留)
  - 新增"接口契约 → 3. MATLAB 语法关键规则"内的"#### 预处理 5 步顺序"子节(明示 5 步顺序 + line_map 维护要求)
  - 修订"接口契约 → 5. function 块提取规则":签名改 `(preprocessed_code, line_map)`,强调 `MFunction.line_range` 必须经 line_map 回填原始行号,**绝对禁止**用 folded code 行号
  - 修订"接口契约 → 7. uses_toolbox 启发式":(1)删除 `fft / ifft / filter / xcorr` 等 base MATLAB 基础函数误归类 Signal Processing;(2)匹配策略改为函数调用形态 `\\b<name>\\s*\\(` + 包名形态 `\\b<pkg.Class>\\b`,避免变量名误报;(3)补 4 个 toolbox:Communications / Optimization / System Identification / Fixed-Point Designer
  - 新增"风险与注意点 → 风险 14:编码读取策略错误会让中文注释全丢"
  - 风险 10 末尾补 GPT 建议:不用担心下游缺料,`ProjectGraph.unresolved_symbols` 字段已经在架构层面承接
  - 验收标准第 9 项错误处理测试补两条:UTF-8 BOM 自动剥离 / GBK 文件中文注释保留
  - 给 Codex 提示第 8 条"整体解析流程伪代码"重写:bytes-first + 5 步预处理 + line_map 回填
  - 给 Codex 提示新增第 9 条"line_range 行号映射纪律"
- v1.2(2026-06-02 GPT 二审 round-2 采纳 5 项):
  - **line_map 形态升级**:`dict[int, int]` → `dict[int, tuple[int, int]]`(processed → 原始起始/结束行 tuple)。续行折叠后一个 processed line 可覆盖多个原始行,单一 int 映射会丢失续行 function 签名的起始行号(GPT round-2 收口 1)
  - **docstring 来源约束**:docstring 必须从 `original_lines` 提取,**不**能从 preprocessed code 提取——预处理步骤 3 会剥光所有 `%` 行。`extract_functions` 签名加 `original_lines` 参数(GPT round-2 收口 1 延伸)
  - **GBK 测试断言改硬**:验收第 9 项 GBK 用例从"`errors='replace'` 容错"改为"bytes-first 命中 GBK 解码,`raw_code` **正确保留中文**,不是 `\ufffd` 替换字符";风险 7 同步删旧口径(GPT round-2 收口 2)
  - **风险 10 改硬**:明确 04 第 8.4 节 `parse_warnings` 是通用原则,本 Task 因 TASK-101 契约不同而**局部例外**;契约 > 通用原则(GPT round-2 收口 3)
  - **toolbox 真实工程验收去硬门槛**:删除验收第 8 项"11 个 .m 至少 1 个命中至少 1 个 toolbox"硬断言,改为类型正确即可。Toolbox 命中精度移到单元测试守(8 个高置信样例 + 4 个误报排除样例)(GPT round-2 收口 4)
  - **classdef 守卫**:测试集 0 classdef,真实工程拦不住。新增"接口契约 7.1 classdef 守卫"小节 + 主入口伪代码 short-circuit + 验收第 7 项单元测试守住(`file_role == "class"` 时 `functions == []`,即使 methods 块内有 `function` 行也不提取)(GPT round-2 收口 5)
- v1.3(2026-06-02 实施前 cat 验证抓到矩阵预估误差,修订 1 项):
  - **`BuckVoltageControlPlotVoltage.m` 实际是 script 不是 function**:Codex 实施前按 task-103 文档"给 Codex 提示第 1 条"cat 11 个 .m 实际内容,发现该文件第一非注释行是 `if ~exist('simlog_BuckVoltageControl', 'var')...`(MATLAB 常见的"懒加载脚本"模式:数据不存在时先跑仿真再画图),不是 `function ...` 开头。架构师 v1.0 基于"`Plot*` 后缀通常是工具函数"的文件名启发预估错误。
  - 修订内容:接口契约 8 段工程 2 表格 + 小计(2 script + 2 function → 3 script + 1 function)+ 总计(9 script + 2 function → 10 script + 1 function);验收第 8 项工程 2 该文件断言反转(`file_role == "function"` → `"script"`);"给 Codex 的提示"第 3 条"工程 2 含 2 个真 function"改为"1 个"
  - **副作用提醒**:11 个 .m 里只剩 `simlogNeedsUpdate.m` 一个 function,function 分类逻辑的真实工程覆盖单薄。**接口契约 8 段新增 "v1.3 修订特别提醒" 子节**,要求单元测试(验收第 7 项)强化 function 分类覆盖(5 种签名形式 / arguments 块 / 多行续行签名 / docstring / nested / 多 local function),保证 function 分类质量不靠 1 个真实文件守住。
  - **纪律实证**:Codex"看见冲突就停手"纪律在 task-103 首次触发——这是 task-102 实战培养的协作模式延续,完美兑现。架构师预估有误差,Codex 停手抛冲突,PM 转给架构师裁决,15 分钟内回到正轨。无此纪律的 cost 是:Codex 默默改测试断言"绕过",在后续 review 时被发现,需要返工。

**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md` / `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md`
**关联 Task**:依赖 TASK-101(契约) / TASK-003(测试集) / TASK-102(同目录文件,不动);下游 TASK-105 / TASK-107
