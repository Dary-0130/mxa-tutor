# TASK-105: 文件依赖关系分析

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第五个 Task,把 TASK-103 产出的 `MFile` 列表 + TASK-104 产出的 `FileInfo` 列表组装成**工程级文件依赖图**(文件粒度,粗粒度)。

依赖图回答一个问题:**这个工程里,哪个文件用了哪个文件?** 三类边:

- `.m → .m`:跨文件函数调用(基于 `MFile.functions` 函数名 → 文件名的查表)
- `.m → .mat`:数据加载(扫 `MFile.raw_code` 里的 `load / loadmat / importdata`)
- `.m → .slx`:仿真调用(扫 `MFile.raw_code` 里的 `sim / load_system / set_param`)

下游消费者:

- **TASK-107**(ProjectGraph + TeachingUnit 基础构建器):把本 Task 输出的 `dict[str, list[str]]` 转成 `ProjectGraph.edges`(EdgeType = CALLS / LOADS_DATA);同时基于此推断 `entry_points` / `execution_flow` / `unresolved_symbols`
- **TASK-203**(导览生成):"主入口文件"启发式可能引用本 Task 输出
- **TASK-303**(分块策略):chunk metadata 里"file_path 上下游"基于本 Task 输出

本 Task 是**粗粒度文件级依赖**,不细到函数级 edge,不细到 block 级 signal flow,不做拓扑排序,不做入口推断,不做未解析符号集 —— 这些**全部归 TASK-107**(详见 § 6 不做清单)。

**本 Task 不在 `docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"的核心 Task 清单里**(清单:101/102/104/107/205/304),Task 文档完稿后**直接交给 Codex 实施**,不走 GPT 二审。

上下游依赖:

- **上游**:TASK-101(契约源,`FileInfo` / `MFile` / `MFunction`)/ TASK-103(`MFile` 实际产物)/ TASK-104(`FileInfo` 实际产物)
- **下游**:TASK-107 / TASK-203 / TASK-303(Week 1-3 跨周消费)

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架)
- ✅ TASK-002(开发环境 + CI)
- ✅ TASK-003(4 个真实 MATLAB demo 测试集,位于 `tests/fixtures/slx_samples/`)
- ✅ TASK-101(core 接口 + domain 数据结构):**直接契约依赖**,本 Task 用 `FileInfo` / `MFile` / `MFunction`
- ✅ TASK-102(.slx XML 解析器):**不直接依赖**(`SlxModel` 不进本 Task 输入),仅复用 `tests/adapters/parser/conftest.py` 模式
- ✅ TASK-103(.m 文件解析器):**直接消费依赖**,本 Task 接受 `MFile` 实例作为输入
- ✅ TASK-104(zip 沙箱 + 文件分类):**直接消费依赖**,本 Task 接受 `FileInfo` 实例作为输入
- ✅ TASK-108(app/config.py + pydantic-settings 配置层):**不直接依赖**(本 Task 无配置消费)

### 必须存在的文件 / 状态

- `main` 分支处于 TASK-104 已 ✅ 之后的 HEAD(决策 09 入仓后的 commit 或更新)
- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/domain/project.py` — `FileInfo` dataclass(`relative_path: str` / `file_type: str` / `size_bytes: int` / `description: str | None`)
  - `core/domain/m_file.py` — `MFile` / `MFunction` dataclass
- 以下 TASK-103 / 104 产出文件**已存在**,本 Task **不动**:
  - `adapters/parser/m_parser.py` + 4 个 .m 解析内部模块
  - `adapters/parser/zip_extractor.py` + `file_classifier.py` + 2 个 zip 内部模块
  - `adapters/parser/__init__.py`(本 Task **追加**导出 `analyze_dependencies`)
  - `tests/adapters/parser/conftest.py`(本 Task **追加** fixture,不重写)
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,特别第 3 节 v0.1 不承诺清单 / 第 5 节核心 Task 二审清单 / 第 7 节技术架构原则与禁止依赖)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,特别第 4.1 节 `FileInfo` / `MFile` / `Project.file_dependencies` 契约 / 第 6 节技术决策 4 "正则 + 简单 AST"授权)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 10 节异常处理)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**讲解输出,但 `Project.file_dependencies` 是后续讲解的料源,需理解下游使用场景)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`(教学理解中间层归属)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`(静态扫描规范)
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(Codex 能读仓库文件)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(`docs/` 改动语义)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**Codex 完工报告必须含 git 三件套**;**改已有文件必须用编辑器或 Python 字节级操作**)
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(架构师纪律,Codex 也读过对架构师后续修订建议有帮助)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源)
- `docs/tasks/task-103-m-parser.md`(料源,**特别**注意 `MFile.raw_code` 是**未经预处理**的原始字符串,§ 7.2 第 334 行明文)
- `docs/tasks/task-104-zip-extract-and-classify.md`(料源,`FileInfo.file_type` 是字面扩展名 str,不是 enum)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `adapters/parser/dependency_analyzer.py` | **主入口**,定义 `analyze_dependencies(file_infos, m_files) -> dict[str, list[str]]`,实现三类边的提取 + 文件名归一化 + 自调用过滤 + 去重排序 | 180-260 |
| `adapters/parser/_dep_patterns.py` | 私有,收纳正则模式(单行注释剥离 / `load` / `sim` / `set_param` / `load_system` / `importdata` / 函数调用候选 identifier 提取)+ MATLAB 内置函数白名单 frozenset | 80-130 |

下划线前缀模块为内部协作模块,**不暴露**到 `adapters/parser/__init__.py`(只导出 `analyze_dependencies`)。

`tests/adapters/parser/` 下(目录由 TASK-102 / 103 / 104 已建,本 Task 仅新增以下 2 个测试文件 + 扩展 conftest.py):

| 文件 | 职责 |
|---|---|
| `test_dependency_analyzer_unit.py` | 单元测试,用内存构造的 `MFile` / `FileInfo` 对象覆盖每类边的正反 case + 重名函数 + 自调用过滤 + 注释 / 字符串误报场景 + 文件名归一化 |
| `test_dependency_analyzer_real.py` | 集成测试,基于 `tests/fixtures/slx_samples/` 的 4 个真实工程跑端到端(用 TASK-103 / 104 实际 parser),断言每个工程的预期依赖映射 |

### 修改文件

- **`adapters/parser/__init__.py`** — TASK-102 / 103 / 104 已建,本 Task **追加** `from .dependency_analyzer import analyze_dependencies`,**不动现有导出**
- **`tests/adapters/parser/conftest.py`** — TASK-102 / 103 / 104 已建,本 Task **追加** `make_m_file` / `make_file_info` 两个工厂 fixture(便于单测内存构造),**不动现有 fixture**
- **`adapters/parser/README.md`** — TASK-102 / 103 / 104 已维护,本 Task 在末尾**追加** `dependency_analyzer.py` 的职责描述(2-3 行)
- **`docs/03_TASK_INDEX.md`** — 本 Task 推 🔲 → 🔍,Week 1 进度条第 5 位 ⬜ → 🔍。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1

### 不动文件

- `core/` 下所有文件(本 Task **不**修改 task-101 已建的 `FileInfo` / `MFile` / `MFunction` / `Project` 字段定义)
- `adapters/parser/m_parser.py` / `slx_parser.py` / `file_classifier.py` / `zip_extractor.py` 及其内部模块
- `app/` / `features/` / `api/` / `web/` 下所有文件
- `pyproject.toml` / `Makefile` / `.github/workflows/ci.yml`
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(决策 07 边界)
- `tests/fixtures/` 已建文件
- 其他 Task 的代码与测试

### 新增依赖

**0 个**。本 Task 只用 Python 3.11 标准库(`re` / `pathlib` / `collections.OrderedDict` 等),不引入任何第三方依赖。

### 新增配置项

**0 个**。本 Task **不消费 AppSettings**(纯静态分析,无 IO 限制 / 无阈值 / 无超时)。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-105-file-dependency-analysis`
- [ ] **依赖结构理解**:实施前**第一件事**,`cat adapters/parser/__init__.py tests/adapters/parser/conftest.py adapters/parser/README.md` 看实际内容,确认本 Task 文档"输入"小节描述与实际一致。若 conftest.py 已有的 fixture 名与本 Task 文档"接口契约"§ 7.5 描述的工厂 fixture 名冲突,**停手抛冲突给 PM**
- [ ] **建 `adapters/parser/_dep_patterns.py`**(详见接口契约 § 7.4):
  - [ ] `BUILTIN_FUNCTIONS: frozenset[str]` 内置函数白名单(详见 § 7.4)
  - [ ] `STRIP_LINE_COMMENT: re.Pattern` 单行 `%` 注释剥离(注意避开字符串内的 `%`)
  - [ ] `STRIP_BLOCK_COMMENT: re.Pattern` 块注释 `%{ %}` 剥离(独占行)
  - [ ] `RE_LOAD_CALL: re.Pattern` `load(...)` / `loadmat(...)` / `importdata(...)` 提取目标字符串
  - [ ] `RE_SIM_CALL: re.Pattern` `sim(...)` / `load_system(...)` / `set_param(...)` 提取目标字符串
  - [ ] `RE_IDENTIFIER_CALL: re.Pattern` `identifier\s*\(` 提取候选函数名(用于 .m → .m 候选)
- [ ] **建 `adapters/parser/dependency_analyzer.py`**(详见接口契约 § 7.1):
  - [ ] 实现 `analyze_dependencies(file_infos, m_files, project_root=None) -> dict[str, list[str]]`
  - [ ] 实现 `_build_function_name_map(m_files) -> dict[str, list[str]]`(函数名 → 定义文件列表)
  - [ ] 实现 `_strip_comments(raw_code) -> str`(简化版,单行 `%` + 块 `%{ %}`,不处理字符串)
  - [ ] 实现 `_extract_m_to_m_targets(stripped_code, fn_to_file, self_file) -> set[str]`
  - [ ] 实现 `_extract_data_load_targets(stripped_code, mat_files_index) -> set[str]`
  - [ ] 实现 `_extract_slx_targets(stripped_code, slx_files_index) -> set[str]`
  - [ ] 实现 `_normalize_target(name, candidates_index) -> str | None`(文件名归一化 + 在 file_infos 中查找匹配项)
- [ ] **追加 `analyze_dependencies` 到 `adapters/parser/__init__.py`** 导出列表
- [ ] **追加 fixture 到 `tests/adapters/parser/conftest.py`**:`make_m_file` + `make_file_info`(详见 § 7.5)
- [ ] **建单元测试**(`tests/adapters/parser/test_dependency_analyzer_unit.py`):
  - [ ] `test_m_to_m_basic_call`:A.m 定义 `foo`,B.m 调用 `foo(x)` → B → A
  - [ ] `test_m_to_m_self_call_excluded`:A.m 定义 `foo` + `bar`,A.m 内 `bar` 调用 `foo` → A 不连 A
  - [ ] `test_m_to_m_builtin_excluded`:A.m 调用 `disp(...)` / `length(...)` → A 不连任何文件
  - [ ] `test_m_to_m_duplicate_name`:A.m 和 B.m 都定义 `helper`,C.m 调用 `helper` → C → [A, B](按 relative_path 排序)
  - [ ] `test_m_to_m_unresolved_silent`:A.m 调用工程外不存在的函数 `mystery(x)` → A 输出空(不报错)
  - [ ] `test_m_to_mat_load_basic`:A.m `load('data.mat')` + data.mat 在 file_infos → A → data.mat
  - [ ] `test_m_to_mat_load_no_extension`:A.m `load('data')` + data.mat 在 file_infos → A → data.mat(扩展名自动补)
  - [ ] `test_m_to_mat_loadmat_alias`:A.m `loadmat('data.mat')` → A → data.mat
  - [ ] `test_m_to_mat_importdata`:A.m `importdata('data.mat')` → A → data.mat
  - [ ] `test_m_to_mat_unresolved_silent`:A.m `load('ghost.mat')` + ghost.mat 不在 file_infos → A 不连
  - [ ] `test_m_to_slx_sim`:A.m `sim('model.slx')` + model.slx 在 file_infos → A → model.slx
  - [ ] `test_m_to_slx_sim_no_extension`:A.m `sim('model')` + model.slx 在 file_infos → A → model.slx
  - [ ] `test_m_to_slx_load_system`:A.m `load_system('model')` → A → model.slx
  - [ ] `test_m_to_slx_set_param_with_subpath`:A.m `set_param('model/SpeedLoop/PID', ...)` → A → model.slx(提取顶层模型名)
  - [ ] `test_comment_stripped_avoids_false_positive`:A.m 注释 `% load('xxx.mat')` 中的 `xxx.mat` 存在于 file_infos → A 不连 xxx.mat(被注释剥离)
  - [ ] `test_block_comment_stripped`:A.m `%{ load('xxx.mat') %}` → A 不连(块注释也剥离)
  - [ ] `test_string_literal_may_false_positive`:A.m 在双引号字符串里出现 `"load('xxx.mat')"` → A 连 xxx.mat(接受少量误报,本 Task 不剥离字符串)
  - [ ] `test_target_list_sorted_dedup`:A.m 多次 `load('data.mat')` + 多次 `load('data')` → A → [data.mat](去重)
  - [ ] `test_no_outgoing_omitted`:A.m 无任何调用 → A 不在 dict 的 key 集合中
  - [ ] `test_path_separator_normalized`:A.m `load('subdir/data.mat')` 在 Windows 也能匹配 file_infos 里 `subdir/data.mat`(POSIX 风格 relative_path,详见 § 7.3 文件名归一化)
  - [ ] `test_empty_inputs`:`analyze_dependencies([], [])` 返回 `{}`
- [ ] **建集成测试**(`tests/adapters/parser/test_dependency_analyzer_real.py`):
  - [ ] 用 TASK-103 `MParserImpl` + TASK-104 `classify_files` 跑 4 个真实工程
  - [ ] 每个工程断言预期依赖映射(由 Codex 实施时通过 `cat -n` 工程内文件 / 跑一遍获取后 hard-code 到测试 — 详见 § 7.6 fixture 矩阵指南)
  - [ ] 至少覆盖 1 个工程有 `.m → .m` 边 + 1 个工程有 `.m → .slx` 边
- [ ] **本地全检通过**:`make check` 全绿
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-105 状态从 🔲 改为 🔍
  - Week 1 进度条第 5 位 ⬜ 改为 🔍
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见风险 1
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-105 as in-review in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status` / `git log --oneline main..HEAD` / `git push` 完整输出
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

- ❌ **`.slx → .slx` model reference 边**(宪法 § 3 v0.1 不承诺 / TASK-107 也不做)
- ❌ **`.slx → .m` mask init 边**(宪法 § 3 v0.1 不承诺 / TASK-107 也不做)
- ❌ **MATLAB toolbox 依赖图边**(`MFile.uses_toolbox` 是元信息呈现,不进依赖图)
- ❌ **rich edge list 或新 EdgeType 数据结构**(归 TASK-107 用 `core/domain/project_graph.py` 已建的 `ProjectEdge` + `EdgeType`)
- ❌ **新增 `core/domain/` 数据结构**(本 Task 输出格式严格用 task-101 已建的 `Project.file_dependencies: dict[str, list[str]]` 同形态)
- ❌ **新增 `core/interfaces/` ABC**(本 Task 不需要 ABC,因为没有多实现的可能性 — `analyze_dependencies` 是一个独立函数,不是有多个实现的接口)
- ❌ **拓扑排序 / 入口推断**(归 TASK-107,基于 `ProjectGraph.entry_points` / `execution_flow`)
- ❌ **未解析符号集 `unresolved_symbols`**(归 TASK-107,基于 `ProjectGraph.unresolved_symbols`)
- ❌ **重名函数 disambiguate**(MCS 接受 list 所有候选,disambiguate 留给 TASK-107 或 Phase 2)
- ❌ **LLM 调用**(本 Task 纯静态分析)
- ❌ **`.slx` 内部 block parameters 扫描**(`SlxModel` 不进本 Task 输入)
- ❌ **调用 TASK-103 私有 `_m_lex` 模块**(私有模块,跨边界耦合,本 Task 自己做简化注释剥离)
- ❌ **完美的字符串识别 / 转置 vs 字符串歧义处理**(接受字符串内极端 case 的少量误报,详见风险 3)
- ❌ **修改 TASK-101 已建的 `FileInfo` / `MFile` / `MFunction` 字段定义**(尤其不要试图把 `Project.file_dependencies` 类型从 `dict[str, list[str]]` 改成别的)
- ❌ **执行 `.m` 代码**(宪法 § 8.1 硬约束)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md` 的 TASK-105 状态行 + Week 1 进度条第 5 位)

---

## 接口契约

### 7.1 `adapters/parser/dependency_analyzer.py` 完整函数签名

```python
"""跨文件依赖分析(粗粒度文件级)。

本模块基于 TASK-103 产出的 ``MFile`` 列表 + TASK-104 产出的 ``FileInfo`` 列表,
扫描每个 .m 文件的 ``raw_code``,提取三类跨文件依赖边:

- ``.m → .m``  : 跨文件函数调用
- ``.m → .mat``: 数据加载 (load / loadmat / importdata)
- ``.m → .slx``: 仿真调用 (sim / load_system / set_param)

输出格式严格对齐 ``core/domain/project.py::Project.file_dependencies``
(``dict[str, list[str]]``,key 与 value 都是 ``FileInfo.relative_path``)。

本模块纯静态分析,**不**执行任何 .m 代码,**不**调用 LLM,**不**消费 AppSettings。
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable

from core.domain.m_file import MFile, MFunction
from core.domain.project import FileInfo

from ._dep_patterns import (
    BUILTIN_FUNCTIONS,
    RE_BLOCK_COMMENT,
    RE_LINE_COMMENT,
    RE_LOAD_CALL,
    RE_SIM_CALL,
    RE_IDENTIFIER_CALL,
)


__all__ = ["analyze_dependencies"]


def analyze_dependencies(
    file_infos: Iterable[FileInfo],
    m_files: Iterable[MFile],
    project_root: str | None = None,
) -> dict[str, list[str]]:
    """提取工程内跨文件依赖关系,返回 {source_relpath: sorted_unique_targets}.

    Args:
        file_infos: 工程内所有文件清单(TASK-104 ``classify_files`` 产出)。
        m_files: 工程内所有 .m 文件的解析结果(TASK-103 ``MParserImpl.parse`` 产出)。
            ``MFile.file_path`` 必须能与 ``file_infos`` 中某个 ``FileInfo.relative_path``
            对齐(详见 § 7.3 文件名归一化)。
        project_root: 可选,工程根目录绝对路径。若 ``MFile.file_path`` 是绝对路径,
            用于裁出 relative_path。可为 ``None``,此时假设 ``MFile.file_path``
            已经是 relative_path。

    Returns:
        映射 {source_relpath: [target1_relpath, target2_relpath, ...]}.

        - 边语义:source 用了 target(无方向反转)
        - target 列表去重 + 按字母序排序
        - 无任何 outgoing 依赖的文件不在 key 集合中
        - **不**记录 self-reference(A 文件内函数互相调用不算)
        - 文件名归一化为 POSIX 风格(详见 § 7.3)
    """
    # 实现要点(详见各内部函数):
    #   1. 建立 {function_name: [defining_relpath1, defining_relpath2, ...]} 索引
    #      跨所有 m_files,从 MFile.functions 提取(去重并保留所有候选)
    #   2. 建立 {filename_lower: relpath} 索引(.mat / .slx 文件名 -> relpath)
    #      用于扩展名补全 + 大小写归一化匹配
    #   3. 对每个 MFile:
    #        a. 简化注释剥离(_strip_comments)
    #        b. 提取 .m -> .m 候选(_extract_m_to_m_targets)
    #        c. 提取 .m -> .mat 候选(_extract_data_load_targets)
    #        d. 提取 .m -> .slx 候选(_extract_slx_targets)
    #        e. 合并 + 排除 self-reference + 去重 + 排序
    #   4. 汇总输出
```

### 7.2 私有辅助函数

```python
def _build_function_name_map(
    m_files: Iterable[MFile],
    relpath_normalize: callable,
) -> dict[str, list[str]]:
    """{function_name: [defining_relpath_normalized_1, ...]} 索引。

    - 只收 ``MFile.functions`` 中 top-level functions(MFunction.name)
    - 一个函数名可能出现在多个 .m 文件(重名),value 是排序后的 relpath 列表
    - .m 文件 file_role == 'class' 时,MFile.functions 必然为空(task-103 契约),自然跳过
    - 不收 builtin(后续 _extract_m_to_m_targets 阶段过滤,而不是此处过滤)
    """


def _build_file_index_by_ext(
    file_infos: Iterable[FileInfo],
    target_ext: str,
) -> dict[str, str]:
    """{lowercase_stem_or_filename: relpath} 索引,用于 .mat / .slx 文件名匹配。

    - target_ext 是 ".mat" 或 ".slx"
    - 索引同时收录两种 key:
        - 带扩展名的小写文件名 (e.g. "data.mat")
        - 不带扩展名的小写主名 (e.g. "data")
      这样 ``load('data')`` 和 ``load('data.mat')`` 都能命中
    - 大小写冲突或同名跨目录:取**首个出现**的 relpath,后续覆盖跳过(MCS 接受这点)
    """


def _strip_comments(raw_code: str) -> str:
    """剥离单行 % 注释 + 块注释 %{ %}。

    简化实现:
    - 块注释:%{ 和 %} 必须独占行(忽略前后空白),把这两行之间所有内容替换为空行
    - 单行注释:删除每行从 % 开始到行尾的内容(简单 string.replace 不行,用 regex)
    - **不剥离字符串**:接受字符串内含 `%` 被误判为注释起始的极端 case

    输出与输入行数一致(替换为空行而不是删除行),避免影响调用方对行号的引用(虽然
    本 Task 不引用行号,但保持行号语义稳定是好习惯)。
    """


def _extract_m_to_m_targets(
    stripped_code: str,
    fn_to_file: dict[str, list[str]],
    self_file_relpath: str,
) -> set[str]:
    """从剥注释后的代码提取 .m -> .m 调用目标 relpath 集合.

    - regex ``RE_IDENTIFIER_CALL`` 提取所有 ``identifier\\s*\\(`` 形态的 identifier
    - 过滤 BUILTIN_FUNCTIONS(disp / length / size / fprintf 等基础函数,**不**视为依赖)
    - 在 fn_to_file 查表,命中则加入候选(同名多文件时全部加入)
    - 排除 self_file_relpath(A 文件调用 A 文件内函数不算依赖)
    """


def _extract_data_load_targets(
    stripped_code: str,
    mat_index: dict[str, str],
) -> set[str]:
    """从剥注释后的代码提取 .m -> .mat 加载目标 relpath 集合.

    - regex ``RE_LOAD_CALL`` 匹配 ``load`` / ``loadmat`` / ``importdata`` 调用,
      提取引号包裹的目标字符串
    - 目标字符串在 mat_index 查表(支持带 / 不带 .mat 扩展名)
    - 不命中 → 静默丢弃(MCS 不报 unresolved,留给 TASK-107)
    """


def _extract_slx_targets(
    stripped_code: str,
    slx_index: dict[str, str],
) -> set[str]:
    """从剥注释后的代码提取 .m -> .slx 引用目标 relpath 集合.

    - regex ``RE_SIM_CALL`` 匹配 ``sim`` / ``load_system`` / ``set_param`` / ``open_system``,
      提取引号包裹的目标字符串
    - ``set_param('model/Sub/Block', ...)`` 形态:提取顶层 'model' 部分(用 '/' 切分取首段)
    - 目标字符串在 slx_index 查表(支持带 / 不带 .slx 扩展名)
    - 不命中 → 静默丢弃
    """


def _normalize_relpath(path: str) -> str:
    """归一化为 POSIX 风格 relative_path:
    - 反斜杠 -> 正斜杠
    - 多余的 ``./`` 前缀 / 末尾斜杠去除
    - 大小写**保留**(关键 case:Linux 文件系统大小写敏感,Windows 不敏感)

    匹配时单独做大小写不敏感比较(_build_file_index_by_ext 的 key 已小写)。
    """
```

### 7.3 文件名归一化策略

**问题**:`FileInfo.relative_path` 在 TASK-104 是 POSIX 风格(`zip_extractor` 解压后归一化过);`MFile.file_path` 可能是 POSIX 也可能是 Windows 风格(TASK-103 用 `pathlib.Path` 读文件,在 Windows 上可能产生反斜杠路径)。

**MFile.file_path → relpath 的转换规则**:

```python
def _mfile_to_relpath(mfile_path: str, project_root: str | None) -> str:
    """把 MFile.file_path 转成 POSIX 风格 relative_path."""
    p = PurePosixPath(mfile_path.replace("\\", "/"))
    if project_root:
        root = PurePosixPath(project_root.replace("\\", "/"))
        try:
            p = p.relative_to(root)
        except ValueError:
            pass  # 不在 project_root 下,保留原 path
    # 去掉前导 ./ 和末尾 /
    result = str(p).lstrip("./").rstrip("/")
    return result
```

**load / sim 引用目标的文件名匹配规则**:

1. 引用字符串可能是:
   - 完整文件名:`'data.mat'` / `'model.slx'`
   - 仅主名:`'data'` / `'model'`(MATLAB 自动补扩展名)
   - 含相对路径:`'subdir/data.mat'` / `'./subdir/data'`
   - **不支持**:绝对路径 / `~` 展开(MCS 不做)

2. 匹配优先级(在 `mat_index` / `slx_index` 中查):
   - 先按"原字符串小写"查
   - 不命中再按"原字符串 + 默认扩展名 小写"查
   - 仍不命中 → 丢弃(不连边)

3. **重要 case** — Windows 路径分隔符:`'subdir\\data.mat'` 在 .m 代码里出现时(极少),先把 `\\` 替换为 `/` 再查表。

### 7.4 `adapters/parser/_dep_patterns.py` 正则模式 + 白名单

```python
"""依赖分析用正则模式与白名单(私有,不导出)。"""
import re

# ---------- 注释剥离 ----------

# 块注释 %{ ... %} 独占行
# 编译时用 re.MULTILINE,以行为单位匹配 %{ 与 %} 独占行
RE_BLOCK_COMMENT = re.compile(
    r"^\s*%\{[^\n]*\n.*?^\s*%\}[^\n]*$",
    re.MULTILINE | re.DOTALL,
)

# 单行注释 % 到行尾(简化:不区分字符串内的 %)
RE_LINE_COMMENT = re.compile(r"%[^\n]*")


# ---------- 跨文件调用模式 ----------

# load / loadmat / importdata 调用,捕获引号内目标
# 支持单引号 / 双引号 / 命令式调用 (load data.mat)
RE_LOAD_CALL = re.compile(
    r"\b(?:load|loadmat|importdata)\s*"
    r"(?:"
    r"\(\s*['\"]([^'\"]+)['\"]"      # 函数式: load('data.mat')
    r"|"
    r"\s+([A-Za-z_]\w*(?:\.\w+)?)"   # 命令式: load data.mat
    r")",
)

# sim / load_system / open_system / set_param 调用,捕获引号内目标
# set_param 的 'model/Sub/Block' 形态由 _extract_slx_targets 二次处理
RE_SIM_CALL = re.compile(
    r"\b(?:sim|load_system|open_system|set_param)\s*"
    r"\(\s*['\"]([^'\"]+)['\"]",
)

# identifier ( 形态,提取 identifier(用于 .m -> .m 候选)
# 排除前导 . (字段访问) 和 @ (anonymous function)
RE_IDENTIFIER_CALL = re.compile(
    r"(?<![.\w@])([A-Za-z_]\w*)\s*\(",
)


# ---------- 内置函数白名单 ----------

# MATLAB 基础函数,不视为依赖目标。仅收高频基础函数,**不**追求穷举
# 命中 BUILTIN_FUNCTIONS 的 identifier 自动从 .m -> .m 候选中过滤
BUILTIN_FUNCTIONS: frozenset[str] = frozenset({
    # I/O 与显示
    "disp", "fprintf", "sprintf", "print", "warning", "error", "input", "keyboard",
    # 类型 / 形状
    "size", "length", "numel", "ndims", "isempty", "isnan", "isinf", "isreal",
    "isnumeric", "ischar", "isstring", "iscell", "isstruct", "islogical",
    "class", "isa", "double", "single", "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64", "char", "string", "logical", "cell",
    # 数学基础
    "abs", "sqrt", "exp", "log", "log2", "log10", "sin", "cos", "tan",
    "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "floor", "ceil",
    "round", "fix", "mod", "rem", "sign", "max", "min", "sum", "prod",
    "mean", "median", "std", "var", "cumsum", "cumprod", "diff",
    # 数组构造
    "zeros", "ones", "eye", "rand", "randn", "linspace", "logspace",
    "repmat", "reshape", "transpose", "permute", "squeeze", "kron",
    "horzcat", "vertcat", "cat",
    # 控制流辅助
    "true", "false", "isequal", "isequaln", "any", "all", "find",
    # 字符串处理
    "strcmp", "strcmpi", "strcat", "strsplit", "strrep", "strtrim",
    "regexp", "regexprep", "lower", "upper", "num2str", "str2num", "str2double",
    # 文件 / 路径(注意:load / sim 等在依赖匹配里另外处理,不在此列)
    "exist", "fopen", "fclose", "fread", "fwrite", "fileparts", "fullfile",
    "pwd", "cd", "ls", "dir", "mkdir", "rmdir",
    # 绘图(常见)
    "plot", "subplot", "figure", "hold", "grid", "axis", "xlabel", "ylabel",
    "title", "legend", "colorbar", "colormap", "scatter", "bar", "stem",
    "semilogx", "semilogy", "loglog", "polar", "surf", "mesh", "contour",
    "imagesc", "image", "imshow",
    # 控制系统 toolbox 基础
    "tf", "zpk", "ss", "step", "impulse", "bode", "nyquist", "rlocus", "margin",
    "feedback", "series", "parallel", "minreal", "balreal",
    # 信号处理 toolbox 基础
    "fft", "ifft", "filter", "conv", "xcorr", "freqz",
    # 流程控制 / 元编程
    "feval", "nargin", "nargout", "varargin", "varargout", "isfield", "fieldnames",
    "struct", "cellfun", "arrayfun", "structfun",
    # try / 错误处理
    "lasterr", "lasterror", "MException", "throw", "rethrow",
    # 时间
    "tic", "toc", "clock", "now", "datestr", "datenum",
    # 其他常见
    "pause", "deal", "assert",
})
```

**白名单维护原则**:
- **只收高频基础函数**,避免穷举(MCS 阶段够用)
- **不收** toolbox 高级函数(那些可能就是用户工程的核心,如 `pid()` / `lsim()` / `dsolve()` 等)
- 命中白名单不连边 → **保守过滤**:误判一个用户函数为 builtin = 漏一条边(尚可接受;TASK-107 unresolved_symbols 可能补)
- 漏判一个 builtin 为用户函数 → 在 `fn_to_file` 查表不命中 = 同样不连边(自然过滤)

### 7.5 `tests/adapters/parser/conftest.py` 追加 fixture

```python
# tests/adapters/parser/conftest.py
# 现有 fixture 不动,本 Task 在末尾追加以下两个工厂 fixture:

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.project import FileInfo


@pytest.fixture
def make_m_file():
    """工厂:快速构造 MFile,只填本测试关心的字段。"""
    def _make(
        file_path: str,
        raw_code: str = "",
        functions: list[MFunction] | None = None,
        file_role: str = "script",
        imports: list[str] | None = None,
        uses_toolbox: list[str] | None = None,
    ) -> MFile:
        return MFile(
            file_path=file_path,
            file_role=file_role,
            functions=functions or [],
            imports=imports or [],
            uses_toolbox=uses_toolbox or [],
            raw_code=raw_code,
        )
    return _make


@pytest.fixture
def make_file_info():
    """工厂:快速构造 FileInfo,只填 relative_path + file_type."""
    def _make(
        relative_path: str,
        file_type: str | None = None,
        size_bytes: int = 0,
    ) -> FileInfo:
        if file_type is None:
            # 从扩展名推断
            from pathlib import PurePosixPath
            file_type = PurePosixPath(relative_path).suffix or "other"
        return FileInfo(
            relative_path=relative_path,
            file_type=file_type,
            size_bytes=size_bytes,
        )
    return _make
```

**冲突避免**:如果 conftest.py 已有同名 fixture(`make_m_file` / `make_file_info`),Codex **停手抛冲突给 PM**,不要默默重命名。

### 7.6 集成测试 fixture 矩阵指南(给 Codex)

`tests/adapters/parser/test_dependency_analyzer_real.py` 需要为 4 个真实工程**手工建预期依赖映射**。流程:

1. 在 `tests/fixtures/slx_samples/` 列出 4 个 zip
2. 对每个 zip:
   a. `cat tests/fixtures/slx_samples/README.md`(TASK-003 已建)看工程描述
   b. **临时**在 Python REPL 中跑:
      ```python
      from adapters.parser import safe_extract, classify_files, MParserImpl
      from app.config import AppSettings
      # ... 跑 TASK-104 / 103 pipeline 获取 file_infos + m_files
      # 然后人工 cat 每个 .m 文件,记录其 load / sim / 跨文件调用
      ```
   c. **人工 cat 验证**每个 .m 文件的依赖,**不**信赖 `analyze_dependencies` 的输出
3. 把人工核查的预期映射 hard-code 到 `test_dependency_analyzer_real.py`,如:

```python
EXPECTED_PROJECT_A = {
    "run_simulation.m": sorted(["init_params.m", "pmsm_foc.slx", "plot_results.m"]),
    "plot_results.m": sorted(["results.mat"]),
}
```

4. 测试函数:
```python
def test_project_a_dependencies(tmp_path):
    extracted = safe_extract(...)
    file_infos = classify_files(extracted, ...)
    m_files = [MParserImpl().parse(...) for fi in file_infos if fi.file_type == ".m"]
    result = analyze_dependencies(file_infos, m_files)
    assert result == EXPECTED_PROJECT_A
```

**至少覆盖**:
- 1 个工程有 `.m → .m` 边
- 1 个工程有 `.m → .slx` 边
- 1 个工程有 `.m → .mat` 边(可与上面任意之一重叠)

允许某个工程无任何跨文件依赖(返回 `{}`),只要 4 个工程**合起来**覆盖三类边即可。

### 7.7 性能预算

- 单次 `analyze_dependencies(file_infos, m_files)` 调用,工程含 ≤ 50 个 .m 文件,**应在 100ms 内完成**
- 4 个真实工程的集成测试**总耗时 ≤ 5 秒**(含 TASK-103 / 104 parser 调用)
- 单元测试 `test_dependency_analyzer_unit.py` **总耗时 ≤ 1 秒**

性能保证靠两件事:
1. `_build_function_name_map` / `_build_file_index_by_ext` 各只构造一次,后续查表 O(1)
2. 正则使用预编译模式(`_dep_patterns.py` 模块加载时编译)

---

## 验收标准

> **以下每条都给出 PM 可在 Git Bash 跑出来的命令**。
> 命令在仓库根目录(`F:\mxa-tutor`)下执行,且已 `source .venv/Scripts/activate`。

### 1. 文件全部创建

```bash
ls adapters/parser/dependency_analyzer.py adapters/parser/_dep_patterns.py tests/adapters/parser/test_dependency_analyzer_unit.py tests/adapters/parser/test_dependency_analyzer_real.py
```

### 2. `adapters/parser/__init__.py` 已追加 export

```bash
grep -n "analyze_dependencies" adapters/parser/__init__.py
```

### 3. 不引入新依赖

```bash
git fetch origin main
git diff origin/main..HEAD -- requirements.txt requirements-dev.txt
```

期望:无任何输出(本 Task 0 新增依赖)。

### 4. 不修改 TASK-001-104 / 108 已建文件

```bash
git diff origin/main..HEAD --stat -- \
    core/ \
    adapters/parser/m_parser.py adapters/parser/slx_parser.py \
    adapters/parser/zip_extractor.py adapters/parser/file_classifier.py \
    adapters/parser/_m_lex.py adapters/parser/_m_structure.py \
    adapters/parser/_zip_paths.py adapters/parser/_zip_policy.py \
    adapters/parser/_slx_*.py \
    app/ features/ api/ web/ \
    pyproject.toml Makefile .github/ scripts/ \
    tests/core/ tests/fixtures/ tests/app/
```

期望:无输出(本 Task 严格只动 `adapters/parser/dependency_analyzer.py` + `_dep_patterns.py` + `__init__.py` + `README.md` + `tests/adapters/parser/conftest.py` + 2 个新 test 文件 + `docs/03_TASK_INDEX.md`)。

### 5. 单元测试全绿

```bash
pytest tests/adapters/parser/test_dependency_analyzer_unit.py -v
```

期望:21 个测试通过,运行 ≤ 1 秒。

### 6. 集成测试全绿

```bash
pytest tests/adapters/parser/test_dependency_analyzer_real.py -v
```

期望:4 个测试通过(每个工程一个),运行 ≤ 5 秒。

### 7. lint 和 type-check 全绿

```bash
make lint        # ruff check
make type-check  # mypy core/ adapters/ features/
ruff format --check .   # 决策 09 反例 8 兜底:CI 实际跑此命令
```

期望:全过。

### 8. 每文件 ≤ 300 行

```bash
wc -l adapters/parser/dependency_analyzer.py adapters/parser/_dep_patterns.py
```

期望:`dependency_analyzer.py` ≤ 260 行;`_dep_patterns.py` ≤ 130 行。

### 9. README 已更新

```bash
grep -n "dependency_analyzer" adapters/parser/README.md
```

期望:看到 `dependency_analyzer.py` 的职责说明 2-3 行。

### 10. TASK_INDEX 状态已更新

```bash
grep -n "TASK-105" docs/03_TASK_INDEX.md
```

期望:看到 TASK-105 那一行状态变成 🔍,Week 1 进度条第 5 位变成 🔍。改动用字节级 Python 操作(详见风险 1),`git diff docs/03_TASK_INDEX.md` 应只显示 2 行 +/-。

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md` 第 1 条,本 Task **只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件**,不动其他任何 docs 核心文档或决策日志或 task 文档。

### 11. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 12. PR 元信息

- PR 标题:`TASK-105: 文件依赖关系分析`
- 分支名:`task/TASK-105-file-dependency-analysis`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-11 项**并简述每项做了什么

### 13. 完工报告含 git 三件套(决策 08)

完工时必须给 PM:

- 修改的文件清单
- 本地 `make check` 完整输出
- **`git status`(显示 working tree clean)**
- **`git log --oneline main..HEAD`(显示本 Task 完整 commit 列表)**
- **`git push` 完整输出**
- 验收清单 1-12 项逐条勾选 + 说明
- PR 标题 + PR 正文

**不附三件套 = 没完工**,PM 退回让 Codex 补。

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须按决策 08 字节级操作

`docs/03_TASK_INDEX.md` 实际行尾是 **LF**(架构师实地 `cat -A` 核查过,详见决策 09 反例集第 9 行)。**禁用**:

- ❌ `pathlib.Path.read_text() + write_text()`
- ❌ `open(path, 'w').write(...)`
- ❌ `sed -i`

**只允许**方式 A(编辑器手改)或方式 B(Python 字节级):

```python
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# TASK-105 状态行 🔲 -> 🔍
old_status = '| TASK-105 | 文件依赖关系分析 | 🔲 | Codex | 103 |'.encode('utf-8')
new_status = '| TASK-105 | 文件依赖关系分析 | 🔍 | Codex | 103 |'.encode('utf-8')
assert old_status in data, 'TASK-105 row not found, check spacing'
data = data.replace(old_status, new_status)

# Week 1 进度条第 5 位 ⬜ -> 🔍
# 注意:本 Task 实施时 main 上 TASK-104 已 ✅,基线进度条是 5/8
old_bar = 'Week 1:  [✅✅✅✅⬜⬜⬜✅]           5/8  (含 TASK-107 / TASK-108)'.encode('utf-8')
new_bar = 'Week 1:  [✅✅✅✅🔍⬜⬜✅]           5/8  (含 TASK-107 / TASK-108)'.encode('utf-8')
assert old_bar in data, 'Week 1 progress bar literal not found, check actual bytes via: grep -n "Week 1" docs/03_TASK_INDEX.md'
data = data.replace(old_bar, new_bar)

p.write_bytes(data)
```

**改完立即 `git diff docs/03_TASK_INDEX.md` 验证**。若 diff 显示几百行红绿,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 用编辑器手改**。

### 风险 2:`MFile.raw_code` 是未经预处理的原始字符串

task-103 § 7.2 第 334 行明文产品决策:**`MFile.raw_code` 必须填未经预处理的原始字符串**(用户后续看原代码做对照)。

这意味着 `raw_code` 里:
- 注释 `%` / `%{ %}` **保留**
- 字符串 `'...'` / `"..."` **保留**
- 续行 `...` **保留**

本 Task 必须**自己**做简化注释剥离(`_strip_comments`)。**不要**尝试调用 task-103 的 `_m_lex` 模块 — 那是 task-103 的私有内部模块,跨边界耦合。

### 风险 3:字符串内的误报接受

简化注释剥离**不**处理字符串。极端 case:

```matlab
str = '% load(''data.mat'')';   % 单引号内 % 后面的 load() 字面
sql = "SELECT * FROM load('data.mat')";  % 双引号内的 load 字面
```

这种代码极少出现,即使出现,误报到 `data.mat` 也只是工程内已存在的文件,后果可控(多一条边)。**MCS 接受**,不做完美字符串识别(对齐 task-103 § 8.6 "接受偶尔误判"原则)。

### 风险 4:重名函数 disambiguate 不做

工程内两个 .m 都定义 `helper(x)`,某文件调用 `helper(x)` —— 实际 MATLAB 路径搜索规则决定调用谁,但**本 Task 不做精确 disambiguate**:返回所有候选 .m 文件作为 target。

下游(TASK-107)消费时可能按"同目录优先"或其他启发式做 disambiguate,本 Task **不**预设。

### 风险 5:Builtin 白名单维护

`_dep_patterns.BUILTIN_FUNCTIONS` 集合**有限**(详见 § 7.4)。维护原则:

- 收高频基础函数(disp / size / zeros / 等)
- **不**收用户工程可能也叫这个名字的 toolbox 高级函数(如 `pid` / `lsim` / `dsolve`)
- 漏判一个 builtin → 在 `fn_to_file` 查表自然不命中 → 不连边,**无副作用**
- 误判一个用户函数为 builtin → 漏一条边,**可接受**(下游 TASK-107 unresolved 可能补)

**强烈认为某个函数应该加进白名单,停手问 PM**,不要单方面扩展(避免与 PM 意图漂移)。

### 风险 6:命令式 load 形态边界

MATLAB 的命令式 load:

```matlab
load data.mat        % 命令式,等价于 load('data.mat')
load data            % 命令式,等价于 load('data')
load -ascii data.txt % 带 flag 的命令式
```

本 Task `RE_LOAD_CALL` 的命令式分支只匹配 `load\s+[A-Za-z_]\w*(\.\w+)?`(简单形态),**不**支持 flag。带 flag 形态会被漏判,可接受(用户极少 load .mat 时加 flag)。

### 风险 7:Python 3.11 标准库依赖

本 Task 用 `re` / `pathlib` / `typing` 标准库,**不**用 `functools.cache` / `functools.lru_cache` 等装饰器(避免本模块内的 cache 在测试间泄漏导致状态污染)。如果想加 cache,**停手问 PM**。

### 风险 8:Codex 看见冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / 03 索引 / 已合并 task 文档的任何冲突,**停手问 PM**,不要默默偏离。

常见冲突场景:
- `adapters/parser/__init__.py` 已有 `analyze_dependencies` 同名导出 → **不要**覆盖,告诉 PM
- `tests/adapters/parser/conftest.py` 已有 `make_m_file` / `make_file_info` 同名 fixture → **不要**覆盖,告诉 PM
- 发现 `MFile` / `FileInfo` 字段与文档描述不符 → **不要**改 task-101 契约,告诉 PM
- 03 索引里 TASK-105 行不存在(罕见) → 告诉 PM,不要自己加行

### 风险 9:静态扫描误报

任何 `grep` / `find` 检查必须按 `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md` 加 `--exclude-dir=".venv" --exclude-dir=".git"`。本 Task 验收清单的命令已遵守。

### 风险 10:集成测试预期映射手工建

`test_dependency_analyzer_real.py` 的预期映射必须**人工 cat 验证**(详见 § 7.6),**不**信赖 `analyze_dependencies` 的输出作为 ground truth(那是循环验证 = 无效)。

如果某个工程的人工核查需要 PM 配合(.m 内容看不懂),**停手问 PM**。

---

## 估时

预估 **3-5 小时**:

- 阅读本 Task 文档 + 02 § 4.1 / 04 § 4-5 / task-103 § 7.2 关键段:0.5 小时
- 建 `_dep_patterns.py`(白名单 + 正则):0.5 小时
- 建 `dependency_analyzer.py` 主入口 + 各内部函数:1-1.5 小时
- 写单元测试(21 个 case):1 小时
- 跑 4 个真实工程 + 人工核查预期映射 + 写集成测试:0.5-1 小时
- 改 `__init__.py` / README / 03 索引 + commit 拆分:0.3 小时
- `make check` + push + 三件套 + PR 描述:0.2 小时

---

## 给 Codex 的提示

### 1. 推荐实现顺序

1. 切分支 `task/TASK-105-file-dependency-analysis`
2. `cat adapters/parser/__init__.py tests/adapters/parser/conftest.py adapters/parser/README.md` 看现状,确认与本文档描述一致
3. 建 `_dep_patterns.py`(白名单 + 6 个 regex,直接抄 § 7.4)
4. 建 `dependency_analyzer.py` 主入口 + 7 个内部辅助函数(按 § 7.1 / 7.2 顺序)
5. 追加 `conftest.py` 工厂 fixture(直接抄 § 7.5)
6. 写 `test_dependency_analyzer_unit.py` 21 个 case(逐条对照 § 5 范围清单)
7. `pytest tests/adapters/parser/test_dependency_analyzer_unit.py -v` 跑过
8. 跑 4 个真实工程的预 ingest(临时 Python REPL),人工 cat 每个 .m 文件,记录预期依赖
9. 写 `test_dependency_analyzer_real.py` 4 个集成 case
10. `pytest tests/adapters/parser/test_dependency_analyzer_real.py -v` 跑过
11. 追加 `analyze_dependencies` 导出到 `__init__.py` + 更新 README
12. `make check` + `ruff format --check .` 全检
13. 改 03 索引(决策 08 字节级)
14. commit 拆分 + push + 三件套 + 提 PR

### 2. Commit 拆分建议(Conventional Commits)

```
feat(parser): add dependency analyzer regex patterns and builtin whitelist
feat(parser): add cross-file dependency analyzer (m->m, m->mat, m->slx)
test(parser): add dependency analyzer unit tests (21 cases)
test(parser): add dependency analyzer real-project integration tests
docs(parser): update parser README with dependency_analyzer module
docs: mark TASK-105 as in-review in task index
```

不要单个超大 commit。

### 3. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见风险 1 的脚本骨架。改完后 `git diff docs/03_TASK_INDEX.md` 确认只显示 2 行左右改动。

### 4. CI 实际跑的命令(决策 09 反例 8)

CI workflow (`.github/workflows/ci.yml`) 跑:

- `ruff check .`
- `ruff format --check .`  ← **本地 `make check` 不一定含此步,务必手动跑**
- `mypy core/ adapters/ features/`
- `pytest -v --tb=short`

完工前**手动**:

```bash
ruff format --check .
```

挂了就 `ruff format .` 修复并 commit。

### 5. 完工报告必须含 git 三件套(决策 08)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 三条命令的完整输出**
- 验收清单 1-12 项逐条勾选 + 说明
- PR 标题:`TASK-105: 文件依赖关系分析`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板)

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 6. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:

- PR 标题:`TASK-105: 文件依赖关系分析`
- PR 正文

PM 在 GitHub 网页手动创建 PR。CI 自动触发,绿了之后 PM 把 Codex 产出 + CI 结果交给架构师 review。

### 7. 遇冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / 03 索引 / TASK-001-104 / 108 已建产物 的任何冲突,**停手问 PM**,不要默默偏离。详见风险 8 的常见冲突场景。

### 8. 决策 09 提醒(给 Codex 也读一下)

虽然决策 09 是**架构师**的纪律(写文档前实地核查,不凭印象),但 Codex 实施时遇到"task 文档与现状不一致"的场景也可以参考其反例集(`docs/decisions/20260603-09-architect-must-verify-not-assume.md` 末尾的 9 行反例表),知道架构师可能在哪些维度凭印象出错,**抓住就停手抛冲突给 PM**。

---

**版本**:Task 文档 v1.0
**作者**:Claude(架构师,第七任)
**日期**:2026-06-03
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md` / `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md` / `20260603-09-*.md`
**关联 Task**:依赖 TASK-101 / TASK-103 / TASK-104(上游契约与产物);下游 TASK-107(直接消费者)/ TASK-203 / TASK-303(间接消费者)
**是否走 GPT 二审**:**否**(本 Task 不在宪法 § 5 核心 Task 二审清单)
