# TASK-107: ProjectGraph 构建器

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第七个 Task,**项目第一个 `features/overview/` 模块**,实现 ProjectGraph 构建器 — 把上游 Parser 产物(SlxModel / MFile / FileInfo / file_dependencies)经**纯结构化转换**变成 ProjectGraph 中间层数据。

为什么必须做:

- 02 § 2 数据流明确:**ProjectGraph 只做"结构理解"(无 LLM,基于解析结果)**,是 Parser 输出与 TeachingUnit / LLM 调用之间的关键桥梁
- Week 2 起所有 LLM 任务(TASK-203 导览生成 / TASK-205 粗 RAG / TASK-307 证据引用强制)都阻塞在本 Task 产出的 ProjectGraph 数据上
- TASK-101 已建好 `ProjectGraph` / `ProjectNode` / `ProjectEdge` / `NodeType` / `EdgeType` / `TeachingUnit` / `SourceRef` 等数据结构的"骨架"(纯 dataclass + enum,无构建逻辑)。本 Task 负责"补肉":**实现 `ProjectGraphBuilder` 类,把 `Project` 输入构建出填好的 `ProjectGraph`**

本 Task 同时承担**示范责任**:走通 `features/overview/` 子目录的代码组织、内部辅助模块拆分(node_id helper / 节点构建器 / 边构建器 / 拓扑模块 / 诊断对象)、私有 `_xxx.py` 命名约定,为后续 `features/overview/teaching_unit_builder.py`(Week 2)/ `features/overview/schemas.py` / `features/chat/` / `features/billing/` 立样。

### 范围调整说明(重要)

第七任架构师交接时把 TASK-107 描述为"ProjectGraph + TeachingUnit 基础构建器"。第八任实地核查 03 索引(验收权威)第 99-103 行,发现**只列 ProjectGraph 验收点,完全不列 TeachingUnit**。结合 02 § 2 数据流"TeachingUnit **才用 LLM**(基于 ProjectGraph 生成)"+ 03 索引"**本 Task 不调用 LLM**" — 唯一一致解读是 **本 Task 仅做 ProjectGraph 构建器,TeachingUnit 推到 Week 2 由 LLM Task(TASK-203 或新拆 110)处理**。

PM 已拍板按此调整。本 Task **不产出**:
- `features/overview/teaching_unit_builder.py`
- 任何调用 LLM 的代码
- `ProjectGraph.data_flow` / `ProjectGraph.control_flow` 字段填充(留空 list,Phase 2 填)

### v0.1 后扩展空间(贯穿设计的 cross-cutting 约束)

PM 明确要求本 Task 设计为 mxa-tutor v0.1 之后版本(Phase 2)的更新扩展留空间。10 条原则:

1. ProjectGraph dataclass 字段 v0.1 冻结(多 Task 共享),Builder 独立演进
2. `PARAMETER` 节点类型 enum 已留位,本 Task 不实施,Phase 2 加 builder 方法
3. `READS_PARAM` 边类型 enum 已留位,Phase 2 同上
4. disambiguate 策略可插拔(MCS best-effort → Phase 2 disambiguator 类)
5. entry_points 用 list[启发式] 累加,Phase 2 可从 AppSettings 读权重
6. block 参数全量落 metadata,TU 层过滤(后续可加策略)
7. ProjectGraphBuilder 输出语义足够 → TeachingUnitBuilder(Week 2)消费接口预留
8. execution_flow 算法解耦(DFS / Kahn / Tarjan SCC 可插)
9. data_flow / control_flow 字段保留留空,Phase 2 填无需改 dataclass
10. unresolved_symbols 格式 v0.1 `"category:name"`,Phase 2 可演进 `"category:name:context"`

### 上下游依赖

- **上游**(已合并 main):
  - TASK-101(契约源,**直接依赖**):`ProjectGraph` / `ProjectNode` / `ProjectEdge` / `NodeType` / `EdgeType` / `SourceRef` / `Project` / `FileInfo` 全部 dataclass + enum
  - TASK-102:`SlxModel` / `SlxBlock` / `SlxLine` 已建,本 Task 直接消费
  - TASK-103:`MFile` / `MFunction` 已建,本 Task 直接消费
  - TASK-104:`FileInfo` 已建,本 Task 直接消费 `Project.files`
  - TASK-105:`analyze_dependencies` 已产出,`Project.file_dependencies: dict[str, list[str]]` 是本 Task CALLS / LOADS_DATA 边的料源
- **下游**(Week 2 起):
  - TASK-203(导览生成):调用本 Task 的 `ProjectGraphBuilder.build(project)`,基于产出 ProjectGraph 调 LLM 生成 TeachingUnit + 导览
  - TASK-205(粗 RAG 问答):基于 ProjectGraph 节点 metadata 做关键词召回
  - TASK-307(证据引用强制):基于 SourceRef 链路验证

**本 Task 在 `docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"的核心 Task 清单里**(清单:101/102/104/**107**/205/304)。Task 文档完稿后**经过 GPT 一审 1 轮**(范围缩小后从二审降级为一审,记入决策攒账)。GPT 一审已通过 12 条建议,本文档已采纳全部建议。

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并)
- ✅ TASK-002(开发环境 + CI,已合并)
- ✅ TASK-003(4 个真实 MATLAB demo 测试集,已合并,位于 `tests/fixtures/slx_samples/`)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并 commit `bf50aba`):**直接契约依赖**,本 Task 消费全部 7 个 dataclass + 2 个 enum
- ✅ TASK-102(.slx 解析器,已合并 commit `2317bb6`):本 Task 消费 `Project.slx_models: list[SlxModel]`
- ✅ TASK-103(.m 解析器,已合并 commit `0714ff7`):本 Task 消费 `Project.m_files: list[MFile]`
- ✅ TASK-104(zip 沙箱 + 文件分类,已合并 commit `d6b05fb`):本 Task 消费 `Project.files: list[FileInfo]`
- ✅ TASK-105(文件依赖分析,已合并 commit `f63e999`):本 Task 消费 `Project.file_dependencies: dict[str, list[str]]`
- ✅ TASK-108(`app/config.py + pydantic-settings`,已合并 commit `4ca7a10`):**本 Task 不直接使用**,但理解配置层架构

### 必须存在的文件 / 状态

- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/domain/project.py` — `Project` / `FileInfo` / `ProjectType`
  - `core/domain/project_graph.py` — `ProjectGraph` / `ProjectNode` / `ProjectEdge` / `NodeType` / `EdgeType`
  - `core/domain/source_ref.py` — `SourceRef`
  - `core/domain/slx_model.py` — `SlxModel` / `SlxBlock` / `SlxLine`
  - `core/domain/m_file.py` — `MFile` / `MFunction`
  - `core/domain/mat_metadata.py` — `MatMetadata` / `MatVariable`
  - `core/domain/exceptions.py` — `MxaError` / `ProjectError`(失败时抛 `ProjectError` 子类)
- 以下文件由 TASK-105 建好,本 Task **直接消费产物**(不重新扫 raw_code,不 import 私有函数):
  - `adapters/parser/dependency_analyzer.py::analyze_dependencies` — 已在 ingest 阶段填好 `Project.file_dependencies`,本 Task 直接读字段
- 以下目录现状:
  - `features/`:已存在(TASK-001 建),含子目录占位
  - `features/overview/`:**可能不存在或仅含 `__init__.py + README.md` 占位**,本 Task 新建主体
  - `tests/features/`:**可能不存在**(TASK-001 / 102 / 103 / 104 / 105 只建 `tests/adapters/` 与 `tests/app/`),本 Task 新建 `tests/features/overview/` 目录
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 5 节核心 Task 二审清单 / 第 7 节技术架构原则 / 第 8 节工程规则:不执行用户代码 / 第 9 节数据隐私**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 2 节数据流(三层转换)/ 第 4.2 节教学理解中间层数据结构 / 第 6 节技术决策 7(理解不抽顶层 feature)**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范 / 第 10 节异常处理**)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**教学输出,但 ProjectGraph 是 TeachingUnit 上游,需理解下游使用场景)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`(**特别关键**:本 Task 实现位置依据)
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(本 Task 不重新扫 raw_code,直接消费上游产物)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**Codex 完工报告必须含 git 三件套**;**改 03 索引必须用编辑器或 Python 字节级操作**)
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(架构师纪律,**Codex 实施时遇文档与现状不一致,停手抛冲突**)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源)
- `docs/tasks/task-102-slx-xml-parser.md`(SlxModel 字段语义)
- `docs/tasks/task-103-m-parser.md`(MFile 字段语义)
- `docs/tasks/task-104-zip-extract-and-classify.md`(FileInfo 字段语义)
- `docs/tasks/task-105-file-dependency-analysis.md`(file_dependencies 字段语义)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `features/overview/__init__.py` | 模块入口,导出 `ProjectGraphBuilder` | 5-10 |
| `features/overview/project_graph_builder.py` | **主类**,`ProjectGraphBuilder` + `build()` 串联各步 | 150-220 |
| `features/overview/_node_id.py` | 私有,node_id 生成 / 解析 helper(6 种节点类型) | 80-140 |
| `features/overview/_pg_nodes.py` | 私有,`_build_nodes` 实现(扫 m_files / slx_models / mat_files / 函数 / block / subsystem) | 180-270 |
| `features/overview/_pg_edges.py` | 私有,`_build_edges` 实现(CALLS / SIGNAL_FLOWS / BELONGS_TO / LOADS_DATA 四类边) | 150-220 |
| `features/overview/_pg_topology.py` | 私有,`_infer_entry_points` + `_topological_sort`(DFS reverse postorder + cycle detection) | 120-180 |
| `features/overview/_pg_diagnostics.py` | 私有,`_BuildDiagnostics` 类(内部诊断聚合) | 50-80 |
| `features/overview/README.md` | 模块说明,列出 ProjectGraphBuilder 职责 + 用法示例 | 30-50 |
| `tests/features/__init__.py` | 空文件,模块标记 | — |
| `tests/features/overview/__init__.py` | 空文件,模块标记 | — |
| `tests/features/overview/conftest.py` | fixtures:`make_project` / `make_slx_model` / `make_m_file` / `make_file_info` 等工厂 | 100-150 |
| `tests/features/overview/test_node_id_unit.py` | node_id helper 单元测试(round-trip 6+ case) | 80-120 |
| `tests/features/overview/test_pg_nodes_unit.py` | 节点构建单元测试 | 150-220 |
| `tests/features/overview/test_pg_edges_unit.py` | 边构建单元测试(每种边类型 + 方向) | 180-260 |
| `tests/features/overview/test_pg_topology_unit.py` | 拓扑 + entry_points 单元测试(含环 / 多入口 / 退化) | 120-180 |
| `tests/features/overview/test_project_graph_builder_unit.py` | 主类集成单元测试(端到端 mock Project → ProjectGraph) | 150-220 |
| `tests/features/overview/test_project_graph_builder_real_projects.py` | 用 TASK-003 真实 fixture 跑 4 个 MATLAB 工程,断言关键字段 | 80-140 |

所有 `_xxx.py` 都是 `project_graph_builder.py` 的内部协作模块,**不暴露**到 `features/overview/__init__.py`(只导出 `ProjectGraphBuilder`)。

### 修改文件

- **`docs/03_TASK_INDEX.md`** — 本 Task 推 🔲 → 🔍,Week 1 进度条第 7 位 ⬜ → 🔍。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1。

### 不动文件

- `core/` 下所有文件(**不**修改 task-101 已建的 dataclass / enum 字段定义)
- `adapters/` 下所有文件(**不**修改 task-102 / 103 / 104 / 105 / 106 已建)
- `app/config.py`(本 Task **不**新增 AppSettings 字段;builder 行为由构造参数控制)
- `features/ingest/` / `features/chat/` / `features/billing/`(其他 feature)
- `api/` / `web/`
- `Makefile` / `.github/workflows/ci.yml` / `pyproject.toml` / `scripts/check_repo_hygiene.sh`
- `requirements.txt` / `requirements-dev.txt`(本 Task **0 个**新依赖)
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(决策 07 边界)
- `tests/fixtures/` / `tests/core/` / `tests/adapters/` / `tests/app/`
- 其他 Task 的代码与测试

### 新增依赖

**0 个**。本 Task 只用标准库 + 已 import 的 `core/` 模块。

### 新增配置项

**0 个**。本 Task **不修改 `app/config.py`**。Builder 行为(`expand_subsystems` / `include_block_parameters` / `entry_point_heuristics`)由构造函数参数控制,默认值即 v0.1 行为。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-107-project-graph-builder`
- [ ] **依赖结构理解**:实施前**第一件事**,跑下面命令看现状,确认本 Task 文档"输入"小节描述与实际一致:
  ```bash
  ls -la features/overview/ tests/features/ 2>/dev/null
  cat core/domain/project_graph.py
  cat core/domain/teaching_unit.py
  cat core/domain/source_ref.py
  cat core/domain/project.py
  cat core/domain/slx_model.py
  cat core/domain/m_file.py
  cat core/domain/exceptions.py
  head -50 adapters/parser/dependency_analyzer.py
  ```
  若发现与本文档"输入 / 输出"小节描述显著不符(如 dataclass 字段名 / 类型变了 / features/overview/ 已含同名文件),**停手抛冲突给 PM**,不要默默偏离
- [ ] **建 `features/overview/_node_id.py`**(详见接口契约 § 7.1):
  - [ ] 6 种 `make_*` helper:`make_file_m_id` / `make_function_id` / `make_file_slx_id` / `make_block_id` / `make_subsystem_id` / `make_file_mat_id`
  - [ ] 1 种 `parse_node_id` helper(返回 NodeType + 各组成部分)
  - [ ] 内部分隔符常量(`PREFIX_SEP = ":"` / `INNER_SEP = "::"`)
- [ ] **建 `features/overview/_pg_diagnostics.py`**(详见接口契约 § 7.7):
  - [ ] 私有 dataclass `_BuildDiagnostics`(`unresolved_categories: dict[str, set[str]]`)
  - [ ] `add(category, name)` 方法(去重写入)
  - [ ] `collect() -> list[str]`(按 `"category:name"` 格式排序输出)
- [ ] **建 `features/overview/_pg_nodes.py`**(详见接口契约 § 7.2):
  - [ ] 实现 `build_file_m_nodes(m_files: list[MFile]) -> list[ProjectNode]`
  - [ ] 实现 `build_function_nodes(m_files: list[MFile]) -> list[ProjectNode]`
  - [ ] 实现 `build_file_slx_nodes(slx_models: list[SlxModel]) -> list[ProjectNode]`
  - [ ] 实现 `build_block_and_subsystem_nodes(slx_models, diag) -> list[ProjectNode]`(**关键**:`block_type == "SubSystem"` 不重复建 BLOCK)
  - [ ] 实现 `build_file_mat_nodes(mat_files: list[MatMetadata]) -> list[ProjectNode]`
  - [ ] 内部:metadata key namespacing(`param:*` / `block:*` / `fn:*` / `file:*` 详见 § 7.2)
- [ ] **建 `features/overview/_pg_edges.py`**(详见接口契约 § 7.3):
  - [ ] 实现 `build_calls_edges(file_dependencies, node_index, diag) -> list[ProjectEdge]`(文件级,**v0.1 不做 function symbol 级**)
  - [ ] 实现 `build_loads_data_edges(file_dependencies, node_index, diag) -> list[ProjectEdge]`
  - [ ] 实现 `build_signal_flows_edges(slx_models, node_index, diag) -> list[ProjectEdge]`
  - [ ] 实现 `build_belongs_to_edges(slx_models, m_files, node_index, diag) -> list[ProjectEdge]`
  - [ ] 边方向**硬契约**遵守(详见 § 7.3)
- [ ] **建 `features/overview/_pg_topology.py`**(详见接口契约 § 7.4 / 7.5):
  - [ ] 实现 `infer_entry_points(project, nodes, edges) -> list[str]`(优先级 H2 > H1 > H3 > H4)
  - [ ] 实现 `topological_sort(nodes, edges, entry_points, diag) -> list[str]`(DFS reverse postorder + gray/black cycle detection,**只用 CALLS + LOADS_DATA 边**)
- [ ] **建 `features/overview/project_graph_builder.py`**(详见接口契约 § 7.8 完整骨架):
  - [ ] 类 `ProjectGraphBuilder` + 构造函数 + `build(project) -> ProjectGraph`
  - [ ] 各步串联,内部 `_BuildDiagnostics` 贯穿
- [ ] **建 `features/overview/__init__.py`**:`from .project_graph_builder import ProjectGraphBuilder`
- [ ] **建 `features/overview/README.md`**:`ProjectGraphBuilder` 职责 + 5-10 行用法示例
- [ ] **建 `tests/features/__init__.py`** + `tests/features/overview/__init__.py`(空文件)
- [ ] **建 fixture(`tests/features/overview/conftest.py`)**(详见 § 7.10):
  - [ ] `make_file_info` / `make_m_file` / `make_m_function` / `make_slx_model` / `make_slx_block` / `make_slx_line` / `make_mat_metadata` / `make_project` 工厂
- [ ] **建 node_id 单元测试**(`tests/features/overview/test_node_id_unit.py`):
  - [ ] 6 种节点 make → parse round-trip
  - [ ] 中文文件名 round-trip
  - [ ] 空格文件名 round-trip
  - [ ] 特殊字符(`-` / `_` / `.` / `(` / `)`)round-trip
  - [ ] 重复路径不同 block_id 区分
  - [ ] 大小写保留(`Foo.m` 与 `foo.m` 不冲突)
- [ ] **建节点构建单元测试**(`tests/features/overview/test_pg_nodes_unit.py`):
  - [ ] 单文件单函数:1 FILE_M + 1 FUNCTION
  - [ ] 多文件多函数
  - [ ] block_type == "SubSystem" 不重复建模(只建 SUBSYSTEM,不建 BLOCK)
  - [ ] SlxModel.subsystems 含无匹配 block_id 的 key → synthetic subsystem + metadata["synthetic"]="true"
  - [ ] metadata key namespacing 验证(全部 `str` value)
  - [ ] partial_parse:SlxModel.parse_warnings 非空 → metadata["partial_parse"]="true" + diag 加入
- [ ] **建边构建单元测试**(`tests/features/overview/test_pg_edges_unit.py`):
  - [ ] CALLS:.m → .m 文件级,方向 caller → callee
  - [ ] CALLS:.m → .slx(sim/load_system 语义)
  - [ ] LOADS_DATA:.m → .mat,方向 loader → mat
  - [ ] SIGNAL_FLOWS:block → block,方向 source → target
  - [ ] BELONGS_TO:block → subsystem,方向 child → parent
  - [ ] BELONGS_TO:subsystem → file_slx
  - [ ] BELONGS_TO:function → file_m
  - [ ] dangling SlxLine(from_block/to_block 不在节点表)→ 跳过 + diag 加入 `unresolved:line<from→to>`
  - [ ] dangling parent_subsystem(name 在 SlxModel.subsystems 不存在)→ 跳过 + diag 加入 `unresolved:subsystem<name>`
  - [ ] 边去重排序
- [ ] **建拓扑单元测试**(`tests/features/overview/test_pg_topology_unit.py`):
  - [ ] entry_points 优先级:文件名命中(main.m / run_*.m / start_*.m / project.name 同名)优先
  - [ ] entry_points 累加去重排序
  - [ ] execution_flow 只用 CALLS + LOADS_DATA 边(SIGNAL_FLOWS 闭环不进拓扑)
  - [ ] DFS reverse postorder 顺序正确
  - [ ] 环检测:back edge 跳过 + diag 加入 `circular:A<->B`
  - [ ] 未访问节点按 node_id 排序补跑
- [ ] **建主类集成单元测试**(`tests/features/overview/test_project_graph_builder_unit.py`):
  - [ ] mock Project → ProjectGraph,断言全部字段
  - [ ] `data_flow` / `control_flow` 为空 list(v0.1 不实施)
  - [ ] empty project(无 .m / .slx / .mat)→ 抛 `ProjectError("empty project")`
  - [ ] 构造参数:`expand_subsystems=False` 验证行为(虽然 v0.1 默认 True)
- [ ] **建真实工程单元测试**(`tests/features/overview/test_project_graph_builder_real_projects.py`):
  - [ ] 加载 `tests/fixtures/slx_samples/` 下 4 个工程(PMSM / Buck / SignalProcessing / Communication)
  - [ ] 模拟 ingest pipeline:zip 解压 → 文件分类 → SlxParser.parse → MParser.parse → analyze_dependencies → 构造 Project → ProjectGraphBuilder.build
  - [ ] 断言:nodes / edges 数量 ≥ 阈值,entry_points 非空,execution_flow 非空,无 `circular:*` 即视为通过
  - [ ] 跑通即 ✅,**不**作为节点 / 边数量的精确断言(允许 ±20% 浮动)
- [ ] **本地 `make check` 全绿** — `ruff check` / `ruff format --check` / `mypy core/ adapters/ features/` / `pytest -v --tb=short` / `scripts/check_repo_hygiene.sh` 五件套
- [ ] **本地 `python -m ruff format --check .` 单独跑一次确认**(决策 09 反例 11 教训,用 `python -m ruff` 而不是裸 `ruff`)
- [ ] **改 03 索引**(字节级 Python 操作,详见风险 1):
  - [ ] TASK-107 行 `🔲` → `🔍`
  - [ ] Week 1 进度条第 7 位 `⬜` → `🔍`
- [ ] **commit 拆分**(Conventional Commits,详见"给 Codex 的提示" § 2)
- [ ] **push 分支** + **完工三件套** 给 PM(决策 08)

---

## 范围(不做) / 工程范围排除

- ❌ **不调用 LLM**(03 索引明文 + 02 § 2 数据流原则;本 Task 是纯结构化转换)
- ❌ **不构建 `TeachingUnit`**(03 索引验收点不含 TeachingUnit,推 Week 2 TASK-203 或拆 TASK-110)
- ❌ **不产出 `features/overview/teaching_unit_builder.py`**(同上)
- ❌ **不填充 `ProjectGraph.data_flow` / `control_flow`**(v0.1 留空 list,Phase 2 填,无需改 dataclass)
- ❌ **不建 `PARAMETER` 类型节点**(料源不足:需扫 .m raw_code 找 `params.X` 模式,违反决策 06;v0.1 不实施)
- ❌ **不建 `READS_PARAM` 类型边**(同上)
- ❌ **不重新扫 `.m` raw_code**(直接消费 `Project.file_dependencies`;决策 06 边界)
- ❌ **不 import `adapters/parser/dependency_analyzer.py` 的私有函数**(`_build_function_name_map` / `_strip_comments` / 等,`_` 前缀模块私有边界)
- ❌ **不做 function symbol 级 disambiguate**(v0.1 CALLS 边以文件为单位,FUNCTION 节点只参与 BELONGS_TO;`ambiguous:<name>` 在 v0.1 基本不产 — best-effort 仅在有可靠料源时触发)
- ❌ **不修改 TASK-101 已建的 dataclass / enum 字段定义**(改 `core/domain/` 任何文件,**停手问 PM**)
- ❌ **不新增 `core/interfaces/` ABC**(本 Task 不需要 ABC,因为 `ProjectGraphBuilder` 是具体类,没有"多实现"的可能性 — Phase 2 子类化扩展即可)
- ❌ **不调用任何外部网络**(本 Task 纯本地结构化转换)
- ❌ **不执行 `.m` / `.slx` 代码**(宪法 § 8.1 / 04 § 8.1 硬约束)
- ❌ **不引入第三方依赖**(包括但不限于 `networkx` / `graphlib` 之外的图算法库;`graphlib` 标准库可用但本 Task 不需要,自己写 DFS 即可)
- ❌ **不写 LLM 集成测试**(本 Task 无 LLM 调用)
- ❌ **不修改 `app/config.py`**(本 Task 不新增 AppSettings 字段;builder 参数走构造函数)
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md`)
- ❌ **不创建 `core/prompts/project_graph_build.yaml`**(02 § 4.2 列了此文件,但 v0.1 不调 LLM,prompt 模板归 TASK-203 创建)

---

## 接口契约

本节是 Codex 实施的**直接抄录源**。所有代码骨架经过架构师与 GPT 一审 1 轮确认,Codex 实施时**遵循骨架**,如发现骨架本身有 bug **停手问 PM**。

### 7.1 节点 ID 命名约定(基石决策)

**硬契约**:所有 `ProjectNode.id` 必须由 `_node_id.py` 的 `make_*` helper 生成,**禁止**各模块手写拼接;所有解析必须用 `parse_node_id` helper,**禁止**下游 `id.split("::")`。

ID 语法 6 种:

| 节点类型 | ID 模板 | 示例 |
|---|---|---|
| FILE_M | `m:<relpath>` | `m:src/utils/helper.m` |
| FUNCTION | `m:<relpath>::fn:<name>` | `m:src/utils/helper.m::fn:compute` |
| FILE_SLX | `slx:<relpath>` | `slx:models/main.slx` |
| BLOCK | `slx:<relpath>::block:<block_id>` | `slx:models/main.slx::block:GUID-abc-123` |
| SUBSYSTEM | `slx:<relpath>::sub:<name>` | `slx:models/main.slx::sub:Controller` |
| FILE_MAT | `mat:<relpath>` | `mat:data/params.mat` |

**关键约束**:

1. `<relpath>` 保留**原始**大小写 + 原始 POSIX 风格,**不**做 lowercase / URL-encode
2. 含空格 / 中文 / 特殊字符的文件名**直接保留**:`m:src/数据 处理/main.m::fn:计算` 是合法的
3. 内部 `_node_id.py` 用 `casefold()` 做 lookup map 辅助查找(类比 `dependency_analyzer.py` 的 `index.setdefault(key.lower(), relpath)` 模式),但**输出 ID 不变**
4. 分隔符常量在 `_node_id.py` 内集中定义,不在调用方硬编码:
   - `PREFIX_SEP = ":"`(前缀与 relpath)
   - `INNER_SEP = "::"`(relpath 与子标识)
   - `SUB_SEP = ":"`(子标识前缀与值,如 `fn:compute` 内的 `:`)
5. **如果未来 relpath 内出现 `::` 字面**(MATLAB 中可能么?极罕见但理论可能,例如某些奇怪的目录名),**实际项目中接受退化**(parse 时返回最长前缀匹配 + 警告 diag),不增加 escape 逻辑

**`_node_id.py` 完整代码骨架**:

```python
"""ProjectNode.id 生成与解析(私有 helper)。

所有节点 ID 由本模块的 ``make_*`` 函数生成,**禁止**调用方手写拼接;
所有解析由 ``parse_node_id`` 完成,**禁止**调用方 ``id.split('::')``。

ID 语法见 task-107.md § 7.1。中文 / 空格 / 特殊字符在 relpath 中
直接保留,不做 escape / encode。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.domain.project_graph import NodeType


__all__ = [
    "make_file_m_id",
    "make_function_id",
    "make_file_slx_id",
    "make_block_id",
    "make_subsystem_id",
    "make_file_mat_id",
    "parse_node_id",
    "ParsedNodeId",
]


# ---------- 分隔符常量(集中定义) ----------

PREFIX_SEP = ":"
INNER_SEP = "::"


# ---------- ID 生成 ----------

def make_file_m_id(relpath: str) -> str:
    """`m:<relpath>`"""
    return f"m{PREFIX_SEP}{relpath}"


def make_function_id(relpath: str, function_name: str) -> str:
    """`m:<relpath>::fn:<function_name>`"""
    return f"m{PREFIX_SEP}{relpath}{INNER_SEP}fn{PREFIX_SEP}{function_name}"


def make_file_slx_id(relpath: str) -> str:
    """`slx:<relpath>`"""
    return f"slx{PREFIX_SEP}{relpath}"


def make_block_id(slx_relpath: str, block_id: str) -> str:
    """`slx:<slx_relpath>::block:<block_id>`"""
    return f"slx{PREFIX_SEP}{slx_relpath}{INNER_SEP}block{PREFIX_SEP}{block_id}"


def make_subsystem_id(slx_relpath: str, subsystem_name: str) -> str:
    """`slx:<slx_relpath>::sub:<subsystem_name>`"""
    return f"slx{PREFIX_SEP}{slx_relpath}{INNER_SEP}sub{PREFIX_SEP}{subsystem_name}"


def make_file_mat_id(relpath: str) -> str:
    """`mat:<relpath>`"""
    return f"mat{PREFIX_SEP}{relpath}"


# ---------- ID 解析 ----------

@dataclass(frozen=True)
class ParsedNodeId:
    """parse_node_id 的返回值。"""
    node_type: NodeType
    relpath: str
    inner_kind: Literal["fn", "block", "sub"] | None = None
    inner_value: str | None = None


def parse_node_id(node_id: str) -> ParsedNodeId:
    """解析 node_id 字符串为结构化对象。

    Args:
        node_id: 由 ``make_*`` 函数生成的 ID 字符串。

    Returns:
        ``ParsedNodeId``,含 node_type / relpath / 可选 inner_kind / inner_value。

    Raises:
        ValueError: 如果 node_id 格式不被识别。
    """
    # 1. 拆前缀
    if PREFIX_SEP not in node_id:
        raise ValueError(f"invalid node_id (no prefix sep): {node_id!r}")
    prefix, _, rest = node_id.partition(PREFIX_SEP)

    # 2. 拆内部子标识(用最长前缀匹配,实际项目中 INNER_SEP "::" 出现在 relpath 极罕见)
    if INNER_SEP in rest:
        relpath, _, inner = rest.partition(INNER_SEP)
        if PREFIX_SEP not in inner:
            raise ValueError(f"invalid inner (no sep): {node_id!r}")
        inner_kind, _, inner_value = inner.partition(PREFIX_SEP)
    else:
        relpath = rest
        inner_kind = None
        inner_value = None

    # 3. 映射 (prefix, inner_kind) → NodeType
    mapping: dict[tuple[str, str | None], NodeType] = {
        ("m", None): NodeType.FILE_M,
        ("m", "fn"): NodeType.FUNCTION,
        ("slx", None): NodeType.FILE_SLX,
        ("slx", "block"): NodeType.BLOCK,
        ("slx", "sub"): NodeType.SUBSYSTEM,
        ("mat", None): NodeType.FILE_MAT,
    }
    key = (prefix, inner_kind)
    if key not in mapping:
        raise ValueError(f"unknown node_id pattern: {node_id!r}")
    node_type = mapping[key]

    # 4. validate inner
    if inner_kind in {"fn", "block", "sub"}:
        assert inner_value is not None, "inner_kind requires inner_value"
        if inner_value == "":
            raise ValueError(f"empty inner_value: {node_id!r}")

    return ParsedNodeId(
        node_type=node_type,
        relpath=relpath,
        inner_kind=inner_kind,  # type: ignore[arg-type]
        inner_value=inner_value,
    )
```

### 7.2 节点类型与构建职责

**节点类型 6 种**(本 Task 实施):

| NodeType | 来源 | label | metadata keys |
|---|---|---|---|
| FILE_M | 每个 `MFile` | `MFile.file_path` 的 basename | `file:role` / `file:imports`(逗号 join) / `file:uses_toolbox`(逗号 join) |
| FUNCTION | 每个 `MFunction`(在每个 MFile.functions 内) | `MFunction.name` | `fn:inputs`(逗号 join) / `fn:outputs`(逗号 join) / `fn:line_range`(`"start-end"` 字符串) / `fn:docstring`(`docstring` 或 `""`) |
| FILE_SLX | 每个 `SlxModel` | `SlxModel.name` | `slx:model_name`(== name) / `slx:solver_*`(展开 solver_config) / `partial_parse: "true"`(如果 parse_warnings 非空) |
| BLOCK | 每个 `SlxBlock`(**block_type != "SubSystem"**) | `SlxBlock.name` | `block:type`(== block_type) / `block:position`(`"l,t,r,b"`) / `block:is_masked`(`"true"/"false"`) / `block:is_library_link`(同) / `block:is_model_reference`(同) / `block:parent_subsystem`(name 或 `""`) / `param:<paramN>` for each in `SlxBlock.parameters` |
| SUBSYSTEM | **block_type == "SubSystem"** 的 `SlxBlock` 或 `SlxModel.subsystems` 中无匹配的 key | name | 同 BLOCK keys + `synthetic: "true"` (如果是无匹配 key 的 synthetic subsystem) |
| FILE_MAT | 每个 `MatMetadata` | `MatMetadata.file_path` 的 basename | `mat:file_size_bytes`(str) / `mat:variable_count`(str) |

**Subsystem 不与 Block 重复建模(GPT 一审建议 11)**:

```
SlxModel.blocks 里的 SlxBlock 处理流程:
  for block in slx_model.blocks:
      if block.block_type == "SubSystem":
          → 建 SUBSYSTEM 节点(id = make_subsystem_id(relpath, block.name))
          → metadata 加 block:* 全部字段
          → 不建 BLOCK 节点
      else:
          → 建 BLOCK 节点
```

**Synthetic SUBSYSTEM**(GPT 一审建议 11):

```
扫完 SlxModel.blocks 后,处理 SlxModel.subsystems:
  for sub_name, child_block_names in slx_model.subsystems.items():
      if sub_name 已经作为 SUBSYSTEM 节点存在(来自 block_type=="SubSystem" 的 block):
          → 跳过(已建)
      else:
          → 建 synthetic SUBSYSTEM 节点
          → metadata["synthetic"] = "true"
          → 仍参与 BELONGS_TO 边构建
          → diag.add("partial_parse", relpath)(诊断:有无匹配 block_id 的 subsystem name)
```

**metadata value 强类型**:全部 `str`。boolean → `"true"/"false"`,tuple → `","` join 后 str,int → str,list → `","` join。**单元测试必须断言** `assert all(isinstance(v, str) for v in node.metadata.values())`。

**metadata key namespacing 表**(完整,GPT 一审建议 12):

| 前缀 | 来源 dataclass | 示例 keys |
|---|---|---|
| `file:` | MFile 结构性字段 | `file:role` / `file:imports` / `file:uses_toolbox` |
| `fn:` | MFunction 字段 | `fn:inputs` / `fn:outputs` / `fn:line_range` / `fn:docstring` |
| `slx:` | SlxModel 结构性字段 | `slx:model_name` / `slx:solver_type` / `slx:solver_*`(展开) |
| `block:` | SlxBlock 结构性字段 | `block:type` / `block:position` / `block:is_masked` / `block:is_library_link` / `block:is_model_reference` / `block:parent_subsystem` |
| `param:` | SlxBlock.parameters 内每个 key | `param:Gain` / `param:Numerator` / `param:Denominator` / `param:<任意 parameter name>` |
| `mat:` | MatMetadata 字段 | `mat:file_size_bytes` / `mat:variable_count` |
| (none) | 通用诊断标记 | `partial_parse` / `synthetic` |

注意:**`param:` 与 `block:type` 不会冲突**,因为 SlxBlock.parameters 的 key 是 MATLAB 参数名(`Gain` / `Numerator` 等),不会出现 `type` / `position` 等结构字段同名。

### 7.3 边类型与方向硬契约

**边类型 4 种**(本 Task 实施),**方向硬契约**:

| EdgeType | from_node | to_node | 语义 | 料源 |
|---|---|---|---|---|
| CALLS | caller(`.m` 或 `.slx`) | callee(`.m` 或 `.slx`) | "调用方 → 被调用方" | `Project.file_dependencies`,目标后缀为 `.m` 或 `.slx` |
| LOADS_DATA | loader file(`.m`) | mat file | "加载方 → 数据" | `Project.file_dependencies`,目标后缀为 `.mat` |
| SIGNAL_FLOWS | source block | target block | "信号源 → 信号去" | `SlxModel.lines`,from_block → to_block |
| BELONGS_TO | child(block / sub / fn) | parent(sub / slx / m) | "归属关系" | 4 种:`SlxBlock.parent_subsystem`、`SlxModel.subsystems`、`SlxModel` 的所有顶层 block/sub、每个 `MFile.functions` |

**CALLS 边在 v0.1 文件级**(GPT 一审建议 9):

`Project.file_dependencies` 是 `dict[str, list[str]]`,key/value 都是 `FileInfo.relative_path`,**没有 function symbol 级**。本 Task **不重新扫 raw_code**,所以 CALLS 边只能建在 FILE_M / FILE_SLX 节点之间(以 `analyze_dependencies` 返回的文件级粒度为准)。

边构建逻辑:

```
for source_relpath, target_relpaths in project.file_dependencies.items():
    source_node_id = ... # 根据扩展名映射:.m→file_m_id, .slx→file_slx_id
    for target_relpath in target_relpaths:
        target_ext = PurePosixPath(target_relpath).suffix.lower()
        target_node_id = ... # 根据 ext 映射
        if target 是 .m 或 .slx:
            建 CALLS 边(source → target)
        elif target 是 .mat:
            建 LOADS_DATA 边(source → target)
        else:
            跳过 + diag.add("unresolved", f"file_dep_target:{target_relpath}")
```

**FUNCTION 节点不参与 CALLS 边**:`MFunction` 之间的调用关系在 v0.1 不可靠(料源不全),不建函数级 CALLS。`function → file_m` 走 BELONGS_TO。

**BELONGS_TO 边的所有层级**:

| from(child)| to(parent) | 来源 |
|---|---|---|
| FUNCTION | FILE_M | 每个 MFile.functions 一条 |
| BLOCK | SUBSYSTEM | `SlxBlock.parent_subsystem` 非空时 |
| SUBSYSTEM | SUBSYSTEM | 嵌套 subsystem(若 `SlxBlock.parent_subsystem` 指向另一个 subsystem) |
| BLOCK | FILE_SLX | `SlxBlock.parent_subsystem == None` 时(顶层 block) |
| SUBSYSTEM | FILE_SLX | 顶层 subsystem(其 `SlxBlock.parent_subsystem == None`) |

**SIGNAL_FLOWS 边**(SlxLine 处理):

```
for slx_model in project.slx_models:
    for line in slx_model.lines:
        from_id = make_block_id(relpath, line.from_block)
        to_id = make_block_id(relpath, line.to_block)
        if from_id 或 to_id 不在 node_index:
            diag.add("unresolved", f"line<{line.from_block}→{line.to_block}>")
            continue
        建 SIGNAL_FLOWS 边
```

但需要注意:**from_block / to_block 可能引用 SUBSYSTEM**(信号线连到 subsystem 边界 port)。此时 `line.from_block == subsystem_block_id`,本 Task 已经把 `block_type == "SubSystem"` 建成 SUBSYSTEM 节点(用 `make_subsystem_id(relpath, name)` 而不是 `make_block_id`),所以**需要 fallback 查找**:先尝试 `make_block_id(relpath, line.from_block)`,如不在则尝试 `make_subsystem_id(relpath, <name_from_block_id>)`。具体回查方式:维护内部 `block_id → node_id` 映射表,在节点构建时同时填好。

**边去重排序**(全部边都做):

```
def _dedup_and_sort(edges: list[ProjectEdge]) -> list[ProjectEdge]:
    seen = set()
    result = []
    for e in sorted(edges, key=lambda x: (x.from_node, x.to_node, x.type.value)):
        key = (e.from_node, e.to_node, e.type.value)
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result
```

### 7.4 entry_points 启发式(优先级)

**4 种启发式累加 + 优先级排序**(GPT 一审建议 8):

| 优先级 | ID | 描述 | 命中规则 |
|---|---|---|---|
| 1(最高)| H2 | 文件名强命中 | `MFile.file_path` 的 basename 匹配:`main.m` / `run_*.m` / `start_*.m` / `<project.name>.m`(忽略大小写比较,**但 ID 保留原大小写**) |
| 2 | H1 | script 类型 | `MFile.file_role == "script"` |
| 3 | H3 | 调用图根 | 在 file_dependencies 中:出度 ≥ 1 且入度 == 0(被 task-105 计入 sources 但不在任何 targets 中) |
| 4(最低)| H4 | .slx 文件 | 每个 SlxModel(Simulink 通常顶层模型是入口) |

`infer_entry_points` 算法:

```python
def infer_entry_points(project, nodes, edges) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    # H2 文件名强命中
    project_name_lower = project.name.lower()
    h2_patterns = lambda name: (
        name.lower() == "main.m"
        or name.lower().startswith("run_")
        or name.lower().startswith("start_")
        or name.lower() == f"{project_name_lower}.m"
    )
    for m_file in project.m_files:
        basename = PurePosixPath(m_file.file_path).name
        if h2_patterns(basename):
            node_id = make_file_m_id(_normalize_relpath(m_file.file_path))
            if node_id not in seen:
                result.append(node_id)
                seen.add(node_id)

    # H1 script 类型
    for m_file in project.m_files:
        if m_file.file_role == "script":
            node_id = make_file_m_id(_normalize_relpath(m_file.file_path))
            if node_id not in seen:
                result.append(node_id)
                seen.add(node_id)

    # H3 调用图根(出度 >= 1 入度 == 0)
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for src, tgts in project.file_dependencies.items():
        out_degree[src] = len(tgts)
        for t in tgts:
            in_degree[t] = in_degree.get(t, 0) + 1
    for src in out_degree:
        if in_degree.get(src, 0) == 0 and out_degree[src] >= 1:
            # src 是 relpath,需要根据扩展名生成 node_id
            ext = PurePosixPath(src).suffix.lower()
            if ext == ".m":
                node_id = make_file_m_id(src)
            elif ext == ".slx":
                node_id = make_file_slx_id(src)
            else:
                continue
            if node_id not in seen:
                result.append(node_id)
                seen.add(node_id)

    # H4 所有 .slx
    for slx_model in project.slx_models:
        node_id = make_file_slx_id(_normalize_relpath(slx_model.file_path))
        if node_id not in seen:
            result.append(node_id)
            seen.add(node_id)

    return result
```

注意:**返回值不再二次排序**,优先级体现在 H2→H1→H3→H4 的追加顺序。同一启发式内部可以按 node_id 排序(确保确定性)。

### 7.5 execution_flow 算法

**算法**:DFS reverse postorder + gray/black cycle detection,**只用 CALLS + LOADS_DATA 边**(GPT 一审建议 4 / 5)。

**为什么排除 SIGNAL_FLOWS + BELONGS_TO**:
- SIGNAL_FLOWS:Simulink 闭环反馈(控制系统常见)会让全图有大量"环",不适合做文件级执行流的排序边
- BELONGS_TO:归属关系不是"执行顺序",混进拓扑会让 child 永远在 parent 之后,语义错

```python
def topological_sort(
    nodes: list[ProjectNode],
    edges: list[ProjectEdge],
    entry_points: list[str],
    diag: _BuildDiagnostics,
) -> list[str]:
    """DFS reverse postorder,只用 CALLS + LOADS_DATA 边。"""
    # 1. 过滤参与拓扑的边
    relevant_edges = [
        e for e in edges
        if e.type in (EdgeType.CALLS, EdgeType.LOADS_DATA)
    ]

    # 2. 建邻接表
    adj: dict[str, list[str]] = {}
    for e in relevant_edges:
        adj.setdefault(e.from_node, []).append(e.to_node)
    # 邻接列表去重 + 排序,保证确定性
    for k in adj:
        adj[k] = sorted(set(adj[k]))

    # 3. DFS gray/black 状态
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n.id: WHITE for n in nodes}
    post_order: list[str] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in adj.get(u, []):
            if v not in color:
                # v 是文件级 node_id 但目标节点不存在(罕见,因为节点构建阶段应该覆盖)
                diag.add("unresolved", f"edge_target:{v}")
                continue
            if color[v] == WHITE:
                dfs(v)
            elif color[v] == GRAY:
                # back edge → 环
                diag.add("circular", f"{u}<->{v}")
                # 跳过(不递归),继续
        color[u] = BLACK
        post_order.append(u)

    # 4. 从 entry_points 起跑 DFS
    for ep in entry_points:
        if ep in color and color[ep] == WHITE:
            dfs(ep)

    # 5. 未访问节点按 node_id 排序补跑
    for n in sorted(nodes, key=lambda x: x.id):
        if color[n.id] == WHITE:
            dfs(n.id)

    # 6. reverse postorder = dependency 较少的在前 / 调用者在前
    return list(reversed(post_order))
```

**注**:`post_order` 是 DFS 完成顺序,reverse 后变成"调用者优先"。如果上层语义需要"被调用者优先"(依赖优先序),返回 `post_order` 不 reverse。本 Task 选**调用者优先**(对教学导览更自然,入口文件出现在前)。

**递归深度风险**:Python 默认 recursion limit 1000。大工程理论上不会超(教学工程 < 100 节点)。若需要可改迭代 DFS(用 stack 模拟),但 v0.1 用递归即可,**单元测试覆盖 ≥ 50 节点不挂**。

### 7.6 unresolved_symbols 4 类(精确定义)

**重新定义**(基于 GPT 一审建议 10):

| 类别 | 格式 | 触发条件 | 不触发条件 |
|---|---|---|---|
| `unresolved` | `unresolved:<name>` | 图构建阶段发现 dangling reference:SlxLine 的 from_block/to_block 不在节点表 / SlxBlock.parent_subsystem 在 subsystems 不存在 / file_dependencies 目标无法映射到节点 / etc. | "调用了不存在的函数"— 本 Task 不重新扫 raw_code,不承诺 |
| `ambiguous` | `ambiguous:<name>` | v0.1 best-effort:**在 v0.1 基本不产**(因为本 Task 不做 function symbol 级 disambiguate),仅作为格式预留 | 任何 v0.1 情形 |
| `circular` | `circular:<from><-><to>` | DFS 检测到 back edge | 跨 SIGNAL_FLOWS 的环(SIGNAL_FLOWS 不参与拓扑) |
| `partial_parse` | `partial_parse:<relpath>` | `SlxModel.parse_warnings` 非空 / `SlxModel.subsystems` 含无匹配 block_id 的 key | `MFile` 解析失败(已被 TASK-103 抛 MParseError,不会进 list) |

**输出格式**:`list[str]`,由 `_BuildDiagnostics.collect()` 排序去重产出。

**v0.1 → Phase 2 演进**(扩展原则 10):Phase 2 可演进为 `<category>:<name>:<context>` 三段式,LLM prompt 同时支持 2 段(v0.1)和 3 段(Phase 2)解析。

### 7.7 `_BuildDiagnostics` 内部诊断机制(GPT 一审建议 7)

**问题背景**:`_collect_unresolved(project, nodes, edges)` 事后无法可靠反推所有 unresolved 情形 — 例如"被跳过的 SlxLine""被跳过的 dangling parent_subsystem""检测到的环"都不会留在最终 nodes/edges 列表上。

**解法**:内部诊断对象,各步构建时直接 add,build() 末聚合。

`_pg_diagnostics.py` 完整代码骨架:

```python
"""ProjectGraph 构建过程的内部诊断对象(私有)。

各 `_build_*` / `_topological_sort` 等步骤通过 ``add`` 写入诊断;
``collect`` 在 build() 末尾聚合输出到 ProjectGraph.unresolved_symbols。
"""
from __future__ import annotations

from dataclasses import dataclass, field


__all__ = ["_BuildDiagnostics"]


@dataclass
class _BuildDiagnostics:
    """ProjectGraph 构建过程的诊断聚合(内部用)。"""

    # category → set of name(去重)
    _entries: dict[str, set[str]] = field(default_factory=dict)

    def add(self, category: str, name: str) -> None:
        """记录一条诊断。

        Args:
            category: 类别(``unresolved`` / ``ambiguous`` / ``circular`` / ``partial_parse``)。
            name: 与类别配套的标识(name / file_path / `"A<->B"` / etc.)。
        """
        self._entries.setdefault(category, set()).add(name)

    def collect(self) -> list[str]:
        """聚合输出,格式 ``category:name``,按 category 然后 name 排序。"""
        result: list[str] = []
        for category in sorted(self._entries):
            for name in sorted(self._entries[category]):
                result.append(f"{category}:{name}")
        return result
```

各步如何使用:

- `_build_nodes`:`diag.add("partial_parse", slx_model.file_path)`(如 SlxModel.parse_warnings 非空)
- `_build_edges`:`diag.add("unresolved", f"line<{from_block}→{to_block}>")`(dangling SlxLine)
- `_build_edges`:`diag.add("unresolved", f"subsystem<{name}>")`(dangling parent_subsystem)
- `_build_edges`:`diag.add("unresolved", f"file_dep_target:{target_relpath}")`(无法映射的 file_dependencies 目标)
- `_topological_sort`:`diag.add("circular", f"{u}<->{v}")`(back edge)
- `_topological_sort`:`diag.add("unresolved", f"edge_target:{v}")`(邻接表中目标节点不存在)

### 7.8 `ProjectGraphBuilder` 主类骨架

完整骨架:

```python
"""ProjectGraph 构建器(features/overview)。

从 Project(包含 SlxModel / MFile / MatMetadata / FileInfo / file_dependencies)
经纯结构化转换构建 ProjectGraph。不调用 LLM,不重新扫 raw_code,不执行用户代码。

设计原则:
  - 主类 ProjectGraphBuilder 负责串联,各步实现在内部 `_pg_*` 模块
  - 每步独立可测,Phase 2 可子类化重写单步
  - 内部 _BuildDiagnostics 贯穿,build() 末聚合到 unresolved_symbols
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from core.domain.exceptions import ProjectError
from core.domain.project import Project
from core.domain.project_graph import (
    EdgeType,
    NodeType,
    ProjectEdge,
    ProjectGraph,
    ProjectNode,
)

from ._pg_diagnostics import _BuildDiagnostics
from ._pg_edges import (
    build_belongs_to_edges,
    build_calls_edges,
    build_loads_data_edges,
    build_signal_flows_edges,
)
from ._pg_nodes import (
    build_block_and_subsystem_nodes,
    build_file_m_nodes,
    build_file_mat_nodes,
    build_file_slx_nodes,
    build_function_nodes,
)
from ._pg_topology import infer_entry_points, topological_sort


__all__ = ["ProjectGraphBuilder"]


class ProjectGraphBuilder:
    """从 Project 输入构建 ProjectGraph(纯结构化转换,不调用 LLM)。

    Args:
        expand_subsystems: 是否展开 subsystem 内部 block。默认 True。
        include_block_parameters: block parameters 落 metadata 的策略。
            ``"all"`` 全部落 / ``"key"`` 仅关键参数(v0.1 未实施)/ ``"none"`` 不落。默认 ``"all"``。
        entry_point_heuristics: 自定义入口点启发式列表。None 时用默认 H2→H1→H3→H4。

    Example:
        >>> builder = ProjectGraphBuilder()
        >>> graph = builder.build(project)
        >>> print(len(graph.nodes), len(graph.edges))
    """

    def __init__(
        self,
        expand_subsystems: bool = True,
        include_block_parameters: Literal["all", "key", "none"] = "all",
        entry_point_heuristics: list[Callable[[Project], set[str]]] | None = None,
    ) -> None:
        if include_block_parameters not in ("all", "key", "none"):
            raise ValueError(
                f"include_block_parameters must be one of "
                f"('all', 'key', 'none'), got {include_block_parameters!r}"
            )
        self._expand_subsystems = expand_subsystems
        self._include_block_parameters = include_block_parameters
        self._entry_point_heuristics = entry_point_heuristics  # v0.1 不使用,Phase 2 接

    def build(self, project: Project) -> ProjectGraph:
        """主入口,串联各步并返回 ProjectGraph。

        Args:
            project: 上游 Project 实例,含 slx_models / m_files / mat_files /
                files / file_dependencies 全部填好。

        Returns:
            ``ProjectGraph``,字段全部填充,``data_flow`` / ``control_flow`` 留空 list。

        Raises:
            ProjectError: 工程完全无 .m / .slx / .mat 文件时。
        """
        # 1. critical_failure 检查
        if not project.m_files and not project.slx_models and not project.mat_files:
            raise ProjectError(
                f"empty project: project_id={project.id!r} has no parseable files"
            )

        diag = _BuildDiagnostics()

        # 2. 节点构建
        nodes = self._build_nodes(project, diag)

        # 3. 边构建
        edges = self._build_edges(project, nodes, diag)

        # 4. entry_points 推断
        entry_points = infer_entry_points(project, nodes, edges)

        # 5. execution_flow 拓扑排序(只用 CALLS + LOADS_DATA 边)
        execution_flow = topological_sort(nodes, edges, entry_points, diag)

        # 6. 聚合诊断到 unresolved_symbols
        unresolved = diag.collect()

        return ProjectGraph(
            project_id=project.id,
            nodes=nodes,
            edges=edges,
            entry_points=entry_points,
            execution_flow=execution_flow,
            data_flow=[],     # v0.1 留空,Phase 2 填
            control_flow=[],  # v0.1 留空,Phase 2 填
            unresolved_symbols=unresolved,
        )

    def _build_nodes(
        self, project: Project, diag: _BuildDiagnostics
    ) -> list[ProjectNode]:
        """节点构建,串联各类型节点 builder。"""
        nodes: list[ProjectNode] = []
        nodes.extend(build_file_m_nodes(project.m_files))
        nodes.extend(build_function_nodes(project.m_files))
        nodes.extend(build_file_slx_nodes(project.slx_models, diag))
        nodes.extend(
            build_block_and_subsystem_nodes(
                project.slx_models,
                diag,
                expand_subsystems=self._expand_subsystems,
                include_block_parameters=self._include_block_parameters,
            )
        )
        nodes.extend(build_file_mat_nodes(project.mat_files))
        return nodes

    def _build_edges(
        self,
        project: Project,
        nodes: list[ProjectNode],
        diag: _BuildDiagnostics,
    ) -> list[ProjectEdge]:
        """边构建,串联各类型边 builder + 去重排序。"""
        # 建 node_index:id → ProjectNode(供后续 lookup)
        node_index: dict[str, ProjectNode] = {n.id: n for n in nodes}

        edges: list[ProjectEdge] = []
        edges.extend(build_calls_edges(project.file_dependencies, node_index, diag))
        edges.extend(
            build_loads_data_edges(project.file_dependencies, node_index, diag)
        )
        edges.extend(
            build_signal_flows_edges(project.slx_models, node_index, diag)
        )
        edges.extend(
            build_belongs_to_edges(project.slx_models, project.m_files, node_index, diag)
        )

        # 去重排序
        return _dedup_and_sort_edges(edges)


def _dedup_and_sort_edges(edges: list[ProjectEdge]) -> list[ProjectEdge]:
    """边去重排序(确保确定性 + 幂等)。"""
    seen: set[tuple[str, str, str]] = set()
    result: list[ProjectEdge] = []
    for e in sorted(edges, key=lambda x: (x.from_node, x.to_node, x.type.value)):
        key = (e.from_node, e.to_node, e.type.value)
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result
```

### 7.9 内部模块拆分清单

为满足"每文件 ≤ 300 行"(04 § 4),主类 `project_graph_builder.py` 只做串联,各步实现拆到内部模块:

| 文件 | 主要导出 | 预估行数 |
|---|---|---|
| `project_graph_builder.py` | `ProjectGraphBuilder`(主类)+ `_dedup_and_sort_edges`(模块级 helper) | 150-220 |
| `_node_id.py` | `make_*` × 6 / `parse_node_id` / `ParsedNodeId` | 80-140 |
| `_pg_nodes.py` | `build_file_m_nodes` / `build_function_nodes` / `build_file_slx_nodes` / `build_block_and_subsystem_nodes` / `build_file_mat_nodes` | 180-270 |
| `_pg_edges.py` | `build_calls_edges` / `build_loads_data_edges` / `build_signal_flows_edges` / `build_belongs_to_edges` | 150-220 |
| `_pg_topology.py` | `infer_entry_points` / `topological_sort` | 120-180 |
| `_pg_diagnostics.py` | `_BuildDiagnostics`(私有 dataclass) | 50-80 |

**接口纪律**:

- 各 `_pg_*` 模块的 `build_*` 函数都接受 `diag: _BuildDiagnostics` 作为最后一个参数(可选,某些函数不需要)
- 各 `build_*` 函数返回 `list[ProjectNode]` 或 `list[ProjectEdge]`
- `parse_node_id` 是**公开 API**(`__all__` 列出),其他模块可以 import 使用;`_node_id.py` 内部 helper 不暴露
- `_BuildDiagnostics` 内部使用,不出 `features/overview/` 包

### 7.10 测试 fixture(`tests/features/overview/conftest.py`)

完整骨架:

```python
"""tests/features/overview/conftest.py — fixtures for ProjectGraph builder tests."""
from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


@pytest.fixture
def make_file_info():
    def _make(
        relative_path: str,
        file_type: str = ".m",
        size_bytes: int = 1024,
        description: str | None = None,
    ) -> FileInfo:
        return FileInfo(
            relative_path=relative_path,
            file_type=file_type,
            size_bytes=size_bytes,
            description=description,
        )
    return _make


@pytest.fixture
def make_m_function():
    def _make(
        name: str = "fn",
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        line_range: tuple[int, int] = (1, 10),
        docstring: str | None = None,
    ) -> MFunction:
        return MFunction(
            name=name,
            inputs=inputs or [],
            outputs=outputs or [],
            line_range=line_range,
            docstring=docstring,
        )
    return _make


@pytest.fixture
def make_m_file(make_m_function):
    def _make(
        file_path: str,
        file_role: str = "function",
        functions: list[MFunction] | None = None,
        imports: list[str] | None = None,
        uses_toolbox: list[str] | None = None,
        raw_code: str = "",
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
def make_slx_block():
    def _make(
        block_id: str,
        name: str | None = None,
        block_type: str = "Gain",
        parameters: dict[str, str] | None = None,
        position: tuple[int, int, int, int] = (0, 0, 100, 50),
        parent_subsystem: str | None = None,
        is_masked: bool = False,
        is_library_link: bool = False,
        is_model_reference: bool = False,
    ) -> SlxBlock:
        return SlxBlock(
            block_id=block_id,
            name=name or block_id,
            block_type=block_type,
            parameters=parameters or {},
            position=position,
            parent_subsystem=parent_subsystem,
            is_masked=is_masked,
            is_library_link=is_library_link,
            is_model_reference=is_model_reference,
        )
    return _make


@pytest.fixture
def make_slx_line():
    def _make(
        from_block: str,
        from_port: int = 1,
        to_block: str = "",
        to_port: int = 1,
    ) -> SlxLine:
        return SlxLine(
            from_block=from_block,
            from_port=from_port,
            to_block=to_block,
            to_port=to_port,
        )
    return _make


@pytest.fixture
def make_slx_model():
    def _make(
        file_path: str,
        name: str | None = None,
        blocks: list[SlxBlock] | None = None,
        lines: list[SlxLine] | None = None,
        subsystems: dict[str, list[str]] | None = None,
        solver_config: dict[str, str] | None = None,
        parse_warnings: list[str] | None = None,
    ) -> SlxModel:
        return SlxModel(
            file_path=file_path,
            name=name or file_path.rsplit("/", 1)[-1].replace(".slx", ""),
            blocks=blocks or [],
            lines=lines or [],
            subsystems=subsystems or {},
            solver_config=solver_config or {},
            parse_warnings=parse_warnings or [],
        )
    return _make


@pytest.fixture
def make_mat_metadata():
    def _make(
        file_path: str,
        file_size_bytes: int = 1024,
        variables: list[MatVariable] | None = None,
    ) -> MatMetadata:
        return MatMetadata(
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            variables=variables or [],
        )
    return _make


@pytest.fixture
def make_project():
    def _make(
        id: str = "proj-1",
        name: str = "TestProject",
        project_type: ProjectType = ProjectType.GENERAL,
        files: list[FileInfo] | None = None,
        slx_models: list[SlxModel] | None = None,
        m_files: list[MFile] | None = None,
        mat_files: list[MatMetadata] | None = None,
        file_dependencies: dict[str, list[str]] | None = None,
    ) -> Project:
        return Project(
            id=id,
            name=name,
            project_type=project_type,
            files=files or [],
            slx_models=slx_models or [],
            m_files=m_files or [],
            mat_files=mat_files or [],
            created_at=datetime(2026, 6, 3, 0, 0, 0),
            file_dependencies=file_dependencies or {},
        )
    return _make
```

### 7.11 下游消费契约(给 Week 2 的硬约束)

**TeachingUnitBuilder 与 ProjectGraph 反查规则**(GPT 一审建议 3 — 写入本 Task 文档供未来 Task-203 派活时复用):

```
**下游 TeachingUnitBuilder 的 target_id 必须满足**:
- 从已存在的 ProjectNode.id 列表中选择或注入
- 不允许 LLM 输出未经校验的 target_id
- 校验方式:`assert target_id in {n.id for n in project_graph.nodes}`
- 不通过校验的 target_id → 当作 unresolved 处理(降级 + 日志告警)

理由:
- TeachingUnit.target_id 是教学内容定位锚,LLM 编造会导致 RAG 链路断
- ProjectGraph 节点 ID 由本 Task 的 `_node_id.py` helper 生成,稳定 + 可解析
- LLM 输出 TU 文本字段(summary / explanation_steps / 等)可以自由生成,但 target_id 必须代码注入
```

### 7.12 边方向硬契约表(汇总)

| EdgeType | from_node | to_node | 例子 |
|---|---|---|---|
| CALLS | caller | callee | `m:src/a.m` → `m:lib/helper.m` |
| LOADS_DATA | loader | mat | `m:src/load.m` → `mat:data/params.mat` |
| SIGNAL_FLOWS | source block | target block | `slx:m.slx::block:b1` → `slx:m.slx::block:b2` |
| BELONGS_TO | child | parent | `m:src/a.m::fn:f` → `m:src/a.m` |

---

## 验收标准

完工时 Codex 必须**逐条对照 + 勾选** 并向 PM 报告:

1. [ ] 13 个新增文件全部建好(`features/overview/` 8 个 + `tests/features/overview/` 8 个 + `tests/features/__init__.py` 1 个 = 共 17 个,详见 § 输出)
2. [ ] **`features/overview/__init__.py` 仅导出 `ProjectGraphBuilder`**(不暴露 `_pg_*` / `_node_id` 私有模块)
3. [ ] **每文件 ≤ 300 行**(04 § 4)— 全部新增文件 `wc -l` 输出 ≤ 300
4. [ ] **node_id round-trip 测试 ≥ 6 case**(`test_node_id_unit.py`)
5. [ ] **6 种节点类型全部覆盖**(test_pg_nodes 各类型至少 1 个 case)
6. [ ] **4 种边类型 + 方向**(test_pg_edges 各类型 + 方向校验)
7. [ ] **Subsystem 不与 Block 重复建模 + synthetic subsystem**(test_pg_nodes 含此 case)
8. [ ] **execution_flow 只用 CALLS + LOADS_DATA 边**(test_pg_topology 验证 SIGNAL_FLOWS 闭环不进拓扑)
9. [ ] **环检测 + 跳过 back edge + diag 记录**(test_pg_topology 含此 case)
10. [ ] **dangling SlxLine / parent_subsystem → diag 加入**(test_pg_edges 含此 case)
11. [ ] **metadata value 全 str 强类型**(test_pg_nodes 含 `assert all(isinstance(v, str) for v in node.metadata.values())`)
12. [ ] **`data_flow` / `control_flow` 留空 list**(test_project_graph_builder_unit 显式断言 `graph.data_flow == [] and graph.control_flow == []`)
13. [ ] **empty project 抛 ProjectError**(test_project_graph_builder_unit 含此 case)
14. [ ] **真实工程跑通**(`test_project_graph_builder_real_projects.py` 4 个工程全部 pass,无 `circular:*`)
15. [ ] **本地 `make check` 全绿** — ruff check / ruff format --check / mypy / pytest / hygiene
16. [ ] **本地 `python -m ruff format --check .` 全绿**(决策 09 反例 11 教训)
17. [ ] **mypy 全绿** — `mypy core/ adapters/ features/`(若新增 mypy 警告,**先修代码不抑制**)
18. [ ] **03 索引推 🔲 → 🔍**(字节级 Python,决策 08 / 风险 1)
19. [ ] **commit 拆分合理**(详见"给 Codex 的提示" § 2)
20. [ ] **完工三件套**:文件清单 + `make check` 输出 + `python -m ruff format --check .` 输出 + `git status` / `git log --oneline main..HEAD` / `git push` 输出

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`。使用 Python 字节级操作(read_bytes + bytes.replace + write_bytes)。脚本错误消息必须**纯 ASCII**(Windows Git Bash codepage 中文会乱码)。

进度条字面量**必须实地 grep 后再匹配**(105 / 106 状态可能在你实施时已经 ✅,字面不同;`Week 1: [✅✅✅✅🔍🔍🔲✅]` 第 7 位是 🔲 → 改 🔍)。如果实际字面与预期不符,**停手抛冲突给 PM**。

参考 task-106 v1.1 § 风险 1 的脚本骨架。

### 风险 2:`features/overview/` 已存在的占位文件不要覆盖

实施前 `cat features/overview/__init__.py 2>/dev/null` 看现状。若 TASK-001 已建占位文件且为空,本 Task **覆盖写**(从空到含 `ProjectGraphBuilder` 导出);若已含其他模块 import,**停手问 PM**(决策 09 反例 1 同源 — task-104 当时假设 app/config.py 已建实际未建)。

### 风险 3:`tests/features/` 目录不存在

实施前 `ls tests/features/ 2>/dev/null` 看现状。如不存在,**Codex 主动 `mkdir tests/features/ tests/features/overview/` + 建 `__init__.py`**,不需要问 PM(本 Task 范围明确扩展测试目录)。

但**只建本 Task 需要的目录**(`tests/features/` + `tests/features/overview/`),不预先建 `tests/features/ingest/` / `tests/features/chat/` 等其他 feature 目录。

### 风险 4:递归深度

`_pg_topology.py` 的 DFS 用递归实现。Python 默认 `sys.getrecursionlimit() == 1000`,本 Task 测试集中节点数 < 100,不会触发。但**单元测试必须显式覆盖 ≥ 50 节点的拓扑测试**(确保 DFS 不退化),如有性能问题改迭代 DFS。

### 风险 5:边去重 key 一致性

`_dedup_and_sort_edges` 用 `(from_node, to_node, type.value)` 三元组做 key。如果某种边在不同步骤被重复建(如 SUBSYSTEM 的 BELONGS_TO 在 `build_belongs_to_edges` 走 SlxModel.subsystems 路径 + Subsystem 自身作为 block_type=="SubSystem" 时又走一遍),去重会兜底,但会多耗 CPU。**优先在生成阶段就做内部去重**(`set` 跟踪已建 edge 三元组),再过 `_dedup_and_sort_edges` 兜底。

### 风险 6:`SlxLine.from_block / to_block` 可能引用 Subsystem 而非 Block

详见 § 7.3 SIGNAL_FLOWS 边的说明。**必须维护 `block_id → node_id` 内部映射**(在节点构建时同时填好),边构建时通过映射查找,而不是直接 `make_block_id(relpath, line.from_block)`。如果 line.from_block 对应的 SlxBlock 在节点构建阶段判定为 SUBSYSTEM(因 block_type=="SubSystem"),映射应指向 `make_subsystem_id(relpath, block.name)` 而非 `make_block_id`。

`_pg_edges.build_signal_flows_edges` 调用方需在 `_pg_nodes` 中获取该映射(可作为返回值 / 参数传递)。**推荐**:节点构建函数额外返回 `block_id_to_node_id: dict[str, str]` 映射,边构建函数接收此参数。

### 风险 7:中文 / 空格文件名

`_node_id.py` 不做 escape,直接保留原字符。**单元测试必须覆盖**:`m:src/数据 处理/main.m::fn:计算函数` 的 round-trip。

但如果文件名中**真的包含**`::` 字面(理论可能,实际罕见),`parse_node_id` 会按最长前缀匹配退化(返回错误的 relpath)。**v0.1 接受退化**,不增加 escape 逻辑;`_node_id.py` 内部测试 case 不覆盖此场景(留 Phase 2)。

### 风险 8:不要 import `adapters/parser/dependency_analyzer.py` 私有函数

诱惑:`_build_function_name_map` 在 task-105 里返回 `dict[name, list[relpath]]` 多候选,似乎可以用来做 function 级 disambiguate。**禁止**(模块私有边界,`_` 前缀)。

v0.1 CALLS 边以文件为单位即可,`ambiguous:<name>` 在 v0.1 基本不产。如果有强烈需求,**停手问 PM** 走单独 chore PR 在 task-105 暴露 helper。

### 风险 9:`MFile.file_path` vs `FileInfo.relative_path` 一致性

`MFile.file_path` 可能是 absolute 也可能是 relative,task-105 的 `_mfile_to_relpath` 已有归一化逻辑。本 Task **自己做归一化**(类似 `_normalize_relpath(MFile.file_path)`),**不**调用 task-105 私有 helper。

归一化规则(与 task-105 一致):
- 反斜杠 `\` 转 POSIX `/`
- 若 `project_root` 提供且 path 以 root 开头,relative_to(root)
- 去除前缀 `./`、后缀 `/`

但本 Task **不需要 project_root 参数**(`Project.id` 不是路径根)。所以归一化只做 1 / 3 步,不做 relative_to。这意味着如果 MFile.file_path 是绝对路径,本 Task 会得到全绝对路径作为 relpath — **但实际 ingest 阶段已经把 MFile.file_path 写成 relative_path**(task-104 + 105 的契约保证)。**单元测试用 relative MFile.file_path,真实工程测试不验证绝对路径场景**。

### 风险 10:Python 标准库 `graphlib.TopologicalSorter`

诱惑:Python 3.9+ 标准库 `graphlib` 提供 `TopologicalSorter`,似乎可以替代手写 DFS。**不推荐**,理由:
- `graphlib.TopologicalSorter` 不支持 cycle detection + 跳过 back edge 继续(它会抛 `CycleError`)
- 本 Task 需要环时降级输出 + 记录 diag,标准库不直接支持
- 手写 DFS 30 行可控,且未来 Phase 2 替换为 Kahn / Tarjan 更平滑

**若 Codex 强烈认为该用 `graphlib`,停手问 PM**。

### 风险 11:静态扫描误报

任何 `grep` / `find` 检查必须按决策 05 加 `--exclude-dir=".venv" --exclude-dir=".git"`。**单测目录约定**:测试 import 用 `from features.overview import ProjectGraphBuilder`,**不**用 relative import。

### 风险 12:工具版本对齐(决策 09 反例 11 教训)

本 Task 实施时严格遵守:
1. **完工自检命令必须用 `python -m ruff format --check .`**(不是裸 `ruff`)
2. **完工三件套必须贴 `python -m ruff format --check .` 输出**
3. 怀疑 cache 命中时 `rm -rf .ruff_cache` 再跑
4. 通常 venv 已激活 + `pip install -r requirements-dev.txt` 跑过的环境,`python -m ruff` 和 `ruff` 一致;保守起见统一用前者

漏踩这条 → CI 红 → PM 来一轮 round-trip,延误 15-30 分钟。

### 风险 13:Codex 看见冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / 03 索引 / TASK-001-106 / 108 已合并产物 的任何冲突,**停手问 PM**,不要默默偏离。

常见冲突场景:
- `features/overview/` 已含同名导出(`ProjectGraphBuilder` 已存在)→ **不要**覆盖
- `core/domain/` dataclass 字段与本文档描述不一致(字段名 / 类型 / 默认值变了)→ 告诉 PM
- `Project.file_dependencies` 类型不是 `dict[str, list[str]]` → 告诉 PM
- `tests/fixtures/slx_samples/` 不存在(TASK-003 测试集未合并)→ 告诉 PM
- `MFile.functions[].line_range` 不是 `tuple[int, int]` → 告诉 PM

---

## 估时

预估 **8-12 小时**:

- 阅读本 Task 文档 + 02 § 2 / § 4.2 + 决策 04 + task-101 / 102 / 103 / 104 / 105 关键段:1 小时
- 建 `_node_id.py`(直接抄 § 7.1):0.5 小时
- 建 `_pg_diagnostics.py`(直接抄 § 7.7):0.2 小时
- 建 `_pg_nodes.py`(按 § 7.2 描述实现):1.5 小时
- 建 `_pg_edges.py`(按 § 7.3 描述实现):2 小时
- 建 `_pg_topology.py`(直接抄 § 7.4 / 7.5):1 小时
- 建 `project_graph_builder.py` 主体(直接抄 § 7.8):0.5 小时
- 建 `__init__.py` + `README.md`:0.3 小时
- 建测试 conftest.py(直接抄 § 7.10):0.5 小时
- 写 node_id round-trip 单元测试:0.5 小时
- 写节点构建单元测试:1 小时
- 写边构建单元测试:1.5 小时
- 写拓扑单元测试:1 小时
- 写主类集成单元测试:0.8 小时
- 写真实工程单元测试:0.5 小时
- `make check` 调试 + 修复 + 三件套 + PR 描述:1 小时
- 改 03 索引(字节级)+ commit 拆分 + push:0.3 小时

如果 Codex 实施期间发现本文档与现状冲突 / 设计缺陷,**停手问 PM**,不在估时内。

---

## 给 Codex 的提示

### 1. 推荐实现顺序

1. 切分支 `task/TASK-107-project-graph-builder`
2. `ls features/overview/ tests/features/ 2>/dev/null` + `cat core/domain/project_graph.py` 等核查现状(详见 § 范围"依赖结构理解"清单)
3. 建 `_node_id.py`(直接抄 § 7.1 完整骨架)
4. 建 `_pg_diagnostics.py`(直接抄 § 7.7 完整骨架)
5. 建 `tests/features/__init__.py` + `tests/features/overview/__init__.py` + `tests/features/overview/conftest.py`(直接抄 § 7.10)
6. 建 `test_node_id_unit.py`(round-trip 6+ case)
7. `pytest tests/features/overview/test_node_id_unit.py -v` 跑过
8. 建 `_pg_nodes.py`(实现 5 个 `build_*_nodes` 函数)
9. 建 `test_pg_nodes_unit.py`
10. `pytest tests/features/overview/test_pg_nodes_unit.py -v` 跑过
11. 建 `_pg_edges.py`(实现 4 个 `build_*_edges` 函数)
12. 建 `test_pg_edges_unit.py`
13. `pytest tests/features/overview/test_pg_edges_unit.py -v` 跑过
14. 建 `_pg_topology.py`(实现 `infer_entry_points` + `topological_sort`)
15. 建 `test_pg_topology_unit.py`
16. `pytest tests/features/overview/test_pg_topology_unit.py -v` 跑过
17. 建 `project_graph_builder.py` 主体(直接抄 § 7.8)
18. 建 `__init__.py` + `README.md`
19. 建 `test_project_graph_builder_unit.py`
20. 建 `test_project_graph_builder_real_projects.py`(用 TASK-003 fixture)
21. `pytest tests/features/overview/ -v` 全跑过
22. `make check` 全绿
23. `python -m ruff format --check .` 全绿
24. 改 03 索引(决策 08 字节级)
25. commit 拆分 + push + 三件套 + 提 PR

### 2. Commit 拆分建议(Conventional Commits)

```
feat(overview): add node_id helpers with structured path grammar
feat(overview): add _BuildDiagnostics for internal build context
feat(overview): add ProjectGraph node builders (file_m / function / file_slx / block_subsystem / file_mat)
feat(overview): add ProjectGraph edge builders (calls / loads_data / signal_flows / belongs_to)
feat(overview): add entry_points heuristics + execution_flow topological sort
feat(overview): add ProjectGraphBuilder main class
test(overview): add unit tests + real project integration
docs(overview): add features/overview/README
docs: mark TASK-107 as in-review in task index
```

不要单个超大 commit。

### 3. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见风险 1 的脚本骨架。**进度条字面量必须实地 grep 后再匹配**(105 / 106 状态可能在你实施时已经 ✅,字面不同),否则 assert 失败。

### 4. CI 实际跑的命令(决策 09 反例 8)

CI workflow 跑:`ruff check .` / `ruff format --check .` / `mypy core/ adapters/ features/` / `pytest -v --tb=short` / `scripts/check_repo_hygiene.sh`。

完工前**手动**:
```bash
python -m ruff format --check .
```
挂了就 `python -m ruff format .` 修复并 commit。

### 5. 完工报告必须含 git 三件套(决策 08)+ 工具版本对齐(决策 09 反例 11)

完工时给 PM:
- 修改 / 新增的文件清单
- 本地 `make check` 输出
- **本地 `python -m ruff format --check .` 完整输出**(必须用 `python -m ruff`,**不**用裸 `ruff`)
- **`git status` / `git log --oneline main..HEAD` / `git push` 完整输出**
- 验收清单 1-20 项逐条勾选 + 说明
- PR 标题:`TASK-107: ProjectGraph 构建器`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板;**变更摘要必须明示**"项目第一个 `features/overview/` 模块")

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 6. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:PR 标题 + PR 正文,PM 在 GitHub 网页手动创建 PR。

### 7. 遇冲突就停手

本 Task 文档与已合并产物的任何冲突,**停手问 PM**,不要默默偏离。详见风险 13 的常见冲突场景。

### 8. 决策 09 提醒

虽然决策 09 是**架构师**的纪律(写文档前实地核查,不凭印象),但 Codex 实施时遇到"task 文档与现状不一致"的场景也可以参考其反例集。架构师可能凭印象的维度:**字面量空格 / 字段总数 / CI 行为 / 仓库现状 / 上游 API 暴露面**。抓住就停手抛冲突给 PM。

### 9. 真实工程测试的容错

`test_project_graph_builder_real_projects.py` 跑 4 个工程时,允许:
- 节点数 / 边数浮动 ±20%(因为上游 parser 输出可能微调)
- `unresolved_symbols` 含若干 `partial_parse:*` 条目(部分 .slx 解析告警)
- `unresolved_symbols` **不能含** `circular:*` 条目(教学工程不应有环)

如果某个工程产生 `circular:*`,**停手问 PM** — 可能是上游 parser bug 或本 Task 算法 bug。

### 10. mypy 与 dataclass 字段

`core/domain/` 的 dataclass 已在 TASK-101 定义。本 Task **不修改字段**(改了 mypy 会跨 Task 报错)。如本 Task 实施中发现某个 dataclass 字段名 / 类型与本文档描述不一致,**停手问 PM**(决策 09 反例 1 同源)。

mypy 命令对齐 CI:`mypy core/ adapters/ features/`。

---

**版本**:Task 文档 v1.0
**作者**:Claude(架构师,第八任)
**日期**:2026-06-03
**修订纪录**:
- v1.0(2026-06-03):基于 GPT 一审 12 条采纳建议产出。范围确认仅 ProjectGraph(TeachingUnit 推 Week 2)。节点 ID 命名约定写硬契约 + 私有 helper + round-trip 测试。边方向硬契约。CALLS v0.1 文件级,不做 function 消歧。execution_flow 只用 CALLS + LOADS_DATA,DFS reverse postorder + 环检测。Subsystem 不与 Block 重复建模。metadata key namespacing(`param:` / `block:` / `fn:` / `file:` / `mat:`)。`_BuildDiagnostics` 内部诊断机制。10 条 v0.1 后扩展原则贯穿。
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md`(实现位置)/ `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md` / `20260603-09-*.md`
**关联 Task**:依赖 TASK-101(契约源)/ 102 / 103 / 104 / 105(上游产物);下游 TASK-203 / 205 / 305 / 307
**是否走 GPT 二审**:**一审 1 轮(已通过,12 条建议全采纳)**。本 Task 在宪法 § 5 核心二审清单,但范围从"ProjectGraph + TeachingUnit"缩到"仅 ProjectGraph"后,复杂度降至接近 task-103 / 105 一审级别,PM 拍板降级为一审 1 轮。这条调整记入决策攒账事项第 21 项,待下次决策 chore PR 入仓。
**实地核查日期**:2026-06-03(架构师 Codex 协同核查 main 真实代码 + GPT 一审 1 轮)
