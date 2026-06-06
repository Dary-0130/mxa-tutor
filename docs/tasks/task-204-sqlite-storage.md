# TASK-204: SQLite 存储层(ProjectStore + ChatStore 持久化)

## 状态

🔲 未开始(v0.2,GPT 一审条件通过 / 不升 round 2 / 应用 9 项反馈 + 4 项文档修订)。

### v0.2 修订摘要(相对 v0.1)

| 来源 | 修订点 | 落点 |
|---|---|---|
| 一审 P0-1 | `Project` JSON 化前显式 redaction `MFile.raw_code=""`,对齐宪法 § 9 line 339"数据库不存储工程原始内容" | D15(新增)+ § 9.3 + 风险 5 + 验收新增 1 |
| 一审 P0-2 | `core/domain/exceptions.py` 从"不动"清单移到"修改"清单(追加 `ChatSessionNotFoundError` + `StoreError`);所有 `StoreError(...)` 调用去掉 `error_code=` 关键字参数 | § 输出 + D12 + D13 |
| 一审 P0-3 | 异常树锁定方案 1:`ChatSessionNotFoundError(ProjectError)` + `StoreError(MxaError)`,不新建 `ChatError` 父类;route 层不许 `try/except` 业务异常,TASK-205 若先于 TASK-206 暴露 chat 端点,应在 TASK-205 追加 ERROR_MAP handler 而非 route 兜底 | D12 + § 9.2 末尾 + 接力点 |
| 一审 P0-4 | `open_connection` 改 `@asynccontextmanager`(原 `async def` 返回 coroutine 不能 `async with` 是硬错);新增 `PRAGMA secure_delete=ON` 加固 24h TTL 删除语义 | § 9.5 + 风险 5 |
| 一审 P0-5 | 所有写操作(`INSERT`/`UPDATE`/`DELETE`/DDL)显式 `await conn.commit()`,事务方法 `BEGIN`/`COMMIT`/`ROLLBACK` 明示 | D8 新增 commit 表 + § 9.3 / 9.4 / 9.6 |
| 一审 P1-1 | store 单元测试 + 集成测试统一 `tmp_path` 文件 DB,**不用** `:memory:`(每次 connect 独立库,与 D8"每方法开+关"天然冲突) | D11 完整重写 |
| 一审 P1-2 | ChatStore 显式 SELECT 预检查 → INSERT(避免靠 SQLite `IntegrityError` message 区分 UNIQUE / FK 语义脆弱) | § 9.4 流程重写 |
| 一审 P1-3 | Project JSON 化:`enum.value` 显式 / `datetime.isoformat()` 显式 / 反序列化 tuple 字段显式还原(`SlxBlock.position` / `MFunction.line_range`);`_project_to_json` / `_project_from_dict` 辅助函数若使 `sqlite_project_store.py` > 300 行,拆 `adapters/storage/_project_json.py` | D14 完整重写 + § 9.3 |
| 一审 P1-4 | `schema_version` 表加 `CURRENT_SCHEMA_VERSION=1` 常量 + 版本校验逻辑:`version > 1` 抛 `StoreError("unsupported_schema_version")`;`version < 1` 抛 `StoreError("schema_migration_required")`(本 Task 不做 migration) | D7 + § 9.6 |
| 一审 P1-5 | 风险 5 改双重删除语义说明:① 逻辑(FK CASCADE 删 chat_session/chat_message)② 物理(`secure_delete=ON` 减少 SQLite freelist 残留) | 风险 5 |
| 文档 Q1 | 全文修正:`chat_message.embedding BLOB` 扩展属 TASK-302 范围(03 索引 Week 3 第 2 行),不是 TASK-304 | 后续 Task 接力点 + D7 |
| 文档 Q2 | `docs/03_TASK_INDEX.md` 状态符号:Week 2 第 4 格写 🔍(等待验收),不是 ✅(已通过) | § 输出 |
| 文档 Q3 | 测试路径对齐 task-202 已建子目录:全部 `tests/adapters/storage/test_*.py`,不平铺 `tests/adapters/test_storage_*.py` | § 输出 + § 验收 |
| 文档 Q4 | Stage 4 lifespan 集成测试缩窄:不打 overview / LLM,只验证 ① db 文件存在 ② `app.state.project_store` / `app.state.chat_store` 装配为 SQLite 实现 ③ schema 表存在 ④ store 直接写读 round-trip ⑤ `/health` + `/projects/{id}/status`(纯存储读路径) | § Stage 4 + § 验收 9 |
| 验收新增 | 6 条新验收命令(raw_code 不持久化 / schema_version=1 / PRAGMA / @asynccontextmanager / import sqlite3 禁 / exceptions.py 只新增 2 类) | § 验收 |

### 审批级别:走 GPT 一审(1 轮,**已完成,条件通过**)

**反例 18 自检**(决策 09 第 18 条):

| 评估维度 | 本 Task 评分 |
|---|---|
| 决策密度 | **中-高**:本 Task 共 **D1-D15** 共 15 个决策点(详见 § 12;v0.2 新增 D15 raw_code redaction) |
| 下游扩散面 | **3 Task**:TASK-205 `ChatStore` 消费者首次定型 + TASK-302 向量字段扩展 schema + TASK-207 schema 边界确认 |
| 用户/安全可见性 | **中**:纯后端持久化层,无新增用户面端点;**但** SQLite 文件落盘是首次磁盘写入,raw_code redaction 是隐私边界关键 |
| 异步首次定型 | **首次** aiosqlite + 持久化 store + 多 worker 解锁(task-202 D5 单 worker 硬约束在本 Task 后放开) |

**结论**:GPT 一审 round 1 已完成,**条件通过 / 不升 round 2**。v0.2 应用所有 P0 / P1 / 文档修订点。

---

## 上下文

### 背景

TASK-202 已建 `InMemoryProjectStore`(`adapters/storage/in_memory_project_store.py`)作为临时桥接,**进程内 dict + asyncio.Lock**,仅支持单 worker。这阻塞了:

1. **多 worker 部署**:uvicorn `--workers > 1` 下,POST /upload 与 GET /status 落不同 worker → 404 假象(task-202 § 范围边界 line 53-57)
2. **进程重启数据丢失**:服务重启后所有 parsing / ready / failed 状态全失,用户已上传工程要重新走一遍
3. **Chat 历史**:TASK-205 粗 RAG 问答需要 chat session 持久化,task-101 / 202 / 203 全程未实现

本 Task 把存储层从内存切到 SQLite,**接口完全不变**(task-203 line 271 已锁 ProjectStore 接口不可改),只换实现。同时**首次定型** `ChatMessage` / `ChatSession` / `ChatStore`,为 TASK-205 / 302 铺路。

### 主要责任

- **ProjectStore SQLite 实现**:`adapters/storage/sqlite_project_store.py::SqliteProjectStore`,实现 task-202 已定型的 7 方法接口 + ProjectStatusView 视图,**接口签名 0 改动**;Project 序列化前 redaction `MFile.raw_code=""`(D15,对齐宪法 § 9)
- **ChatStore 全新建立**:`core/domain/chat.py` 定义 `ChatMessage` / `ChatSession` dataclass;`core/interfaces/chat_store.py` 定义 `ChatStore` ABC;`adapters/storage/sqlite_chat_store.py::SqliteChatStore` 实现
- **Schema + Migration**:`adapters/storage/schema.py` 集中所有 CREATE TABLE SQL + `init_schema(conn)` 函数;lifespan 启动时 idempotent 建表(`CREATE TABLE IF NOT EXISTS` + `schema_version` 表 + 版本校验);无需 alembic
- **lifespan 装配改造**:`api/main.py` lifespan 把 `InMemoryProjectStore()` 替换为 `SqliteProjectStore(db_path)`,新增 `app.state.chat_store = SqliteChatStore(db_path)`
- **InMemoryProjectStore 处理**:**保留为测试 fake**(D6),源文件不删,在 `__init__.py` 不导出,在 README 标注"仅测试用,生产 lifespan 用 SQLite"
- **异常树追加**:`core/domain/exceptions.py` 追加 **2 个**异常类:`ChatSessionNotFoundError(ProjectError)` + `StoreError(MxaError)`(D12,GPT 一审 P0-2 修)
- **多 worker 解锁信号**:本 Task 完成后,uvicorn `--workers > 1` 不再有 store 一致性问题(SQLite 共享磁盘文件);实际放开 worker 启动参数由 TASK-405 部署 Task 决定

### 范围边界(硬约束,必读)

**本 Task 不修改**(零增量原则):

- `core/interfaces/project_store.py::ProjectStore` 接口 — **7 方法签名一字不动**(task-203 line 271 锁)
- `core/domain/project_status.py::ProjectStatusRecord` 字段 — **7 字段冻结**(task-202 D 决策)
- `core/domain/project.py::Project` dataclass — 9 字段冻结(跨 Task 共享契约,task-202 § 范围边界 line 44)
- `app/config.py::AppSettings` — 配置零增量,**已有** `db_path: str = "./data/mxa.db"`(task-108 line 175)
- TASK-201 已注册 8 handler + ERROR_MAP — 不动(新增异常的 ERROR_MAP 注册延后 TASK-206 / TASK-205)
- TASK-202 `CleanupWorker` 签名 + `UploadService.process` — 不动
- TASK-203 `ProjectOverviewService` + lifespan 新增的 4 个 dependency — 不动

**本 Task 修改 1 个 core 异常文件**:

- `core/domain/exceptions.py` — 追加且**仅追加** 2 个异常类:`ChatSessionNotFoundError(ProjectError)` + `StoreError(MxaError)`(GPT 一审 P0-2);既有 11 个异常类不动

**本 Task 不做**(明确推到未来 Task):

- ❌ Vector store / embedding 持久化(**TASK-302** 接管,扩展 `chat_message` 表加 embedding BLOB 字段;v0.1 误写 304 已修)
- ❌ Chat 端点 + ChatService(TASK-205 接管)
- ❌ User / quota 表(MCS 阶段激活码模式不需要;Phase 2 与 TASK-404 接管)
- ❌ Migration 工具完整化(alembic / 版本号管理):MCS 阶段 `CREATE TABLE IF NOT EXISTS` + `schema_version` 单行表已够(D7)
- ❌ Backup / restore 工具(运维侧 cp 即可,MCS 阶段不做)
- ❌ 跨 worker 协调(进程级 read/write 一致性靠 SQLite WAL + busy_timeout)

### 下游消费者

- **TASK-205**(粗 RAG 问答 ⭐):**核心消费者**。`ChatService` 调 `chat_store.create_session` / `append_message` / `get_session` / `list_messages` / `list_recent_sessions` 实现对话历史;若先于 TASK-206 上线,在 TASK-205 自身追加 `ChatSessionNotFoundError → 404` + `StoreError → 500` ERROR_MAP handler(route 层禁止 try/except,GPT 一审 P0-3)
- **TASK-207**(ProjectOverview Schema 边界):本 Task 不动 `Project` dataclass;TASK-207 在 schema 层做 Pydantic 输出收口,不依赖本 Task 字段
- **TASK-302**(SQLite 向量存储 + 检索):扩展 `chat_message` 表加 embedding BLOB 字段 + `ALTER TABLE` + bump schema_version.version 到 2;本 Task 预留 schema_version 校验逻辑配合
- **TASK-404**(激活码):未来新建 `activation_codes` 表,**不动本 Task 已建表**

### 关键宪法引用

- **01 § 9 line 339**(数据隐私硬约束):"数据库**不存储**工程原始内容,**只存元数据**(用户 ID、工程哈希、问答记录、token 消耗)"— 触发 D15 raw_code redaction
- **02 § 8 line 705**(异步):"数据库:SQLite + aiosqlite(异步驱动)"— aiosqlite 选型由宪法锁定,**不改用 sqlite3 + to_thread**(D1)
- **02 § 3 line 153-157**(目录规划):`adapters/storage/sqlite_project_store.py` + `sqlite_chat_store.py` 权威路径
- **02 § 6 决策 1 line 620-624**:SQLite + sentence-transformers,MCS 阶段单工程规模小够用;升级阈值"单工程 chunk 数 > 5000 或 用户量 > 1000"
- **决策 11 决策 1**:async 内同步重活必须 `asyncio.to_thread` 桥接 — **aiosqlite 是原生 async,本 Task 不需要 to_thread**(D1 子注解)
- **决策 11 决策 2**:业务异常分支日志统一 `logger.error(..., type(exc).__name__)`,禁用 `logger.exception` — 本 Task 所有 store 方法 except 分支按此模板(D13)

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001 / 002(项目骨架 + CI,已合并)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并):**直接契约依赖**,本 Task 消费 `Project` / `FileInfo` / `MxaError` / `ProjectError` / `ProjectNotFoundError`;**新增** `ChatMessage` / `ChatSession` / `ChatStore` / `ChatSessionNotFoundError` / `StoreError`(task-101 § 不做 line 95-96 明示推到 204)
- ✅ TASK-104(zip 沙箱,已合并 commit `d6b05fb`):本 Task 不直接依赖,但已有的 `UploadError` 异常树本 Task 不动
- ✅ TASK-108(AppSettings,已合并 commit `4ca7a10`):**直接依赖** `settings.db_path` 字段
- ✅ TASK-201(FastAPI 框架 + ERROR_MAP,已合并 commit `fa7a4b0`):**直接依赖**:本 Task 在 lifespan 改装配,**不动 ERROR_MAP**;新异常的 HTTP 映射延后 TASK-205 / TASK-206
- ✅ TASK-202(上传 + 解析 API,已合并 commit `431a2bf`):**核心依赖**,本 Task 替换其 `InMemoryProjectStore` 装配 + 实现 7 方法接口;沿用其 naive `datetime.utcnow()` 习惯(风险 2)
- ✅ TASK-203(ProjectOverviewService,已合并 commit `871c8e2`):**装配兼容**,本 Task 不动 TASK-203 在 lifespan 追加的 4 dependency;TASK-203 不消费 `MFile.raw_code`(grep 已核查空),D15 redaction 不破坏 TASK-203

### 必须存在的文件 / 状态(实地核查锁定)

实地核查命令(Codex Stage 0 必跑,**任一不符停手抛冲突**,决策 08 第 2 条 / 决策 09 纪律 1):

```bash
# ProjectStore 接口 7 方法在位
grep -n "abstractmethod" core/interfaces/project_store.py
# 期望:7 处 abstractmethod 装饰器,对应 create_pending / mark_ready / mark_failed
#       / get_status_view / get_project / list_expired / delete 7 方法

# ProjectStatusRecord 7 字段在位
grep -E "^[[:space:]]+[a-z_]+:" core/domain/project_status.py | head -10
# 期望:project_id / name / status / created_at / updated_at / project / error_code(7 字段)

# AppSettings.db_path 字段在位
grep -n "db_path" app/config.py
# 期望:db_path: str = "./data/mxa.db" 默认值

# adapters/storage 目录现状
ls -la adapters/storage/
# 期望:in_memory_project_store.py / README.md / __init__.py / __pycache__(可选)

# InMemoryProjectStore 当前装配点
grep -n "InMemoryProjectStore" api/main.py
# 期望:lifespan 内 app.state.project_store = InMemoryProjectStore() 一处

# requirements.txt 当前不含 aiosqlite(本 Task 新增)
grep -n "aiosqlite" requirements.txt
# 期望:空输出(本 Task 新增)

# datetime 用法核查(风险 2):task-202 用 naive datetime.utcnow()
grep -n 'datetime\.\(now\|utcnow\)' adapters/storage/in_memory_project_store.py features/ingest/cleanup_worker.py features/ingest/upload_service.py
# 期望:全部 datetime.utcnow();若出现 datetime.now(tz=...) → 上游已变,停手抛冲突

# CI workflow 装 runtime 依赖(风险 9):若 CI 仍只装 dev 且 dev 不传递 -r requirements.txt,本 Task 加 aiosqlite 会挂
cat .github/workflows/ci.yml | grep -A 2 "pip install"
grep -n "^-r requirements.txt" requirements-dev.txt
# 期望:CI 装 runtime dep(或 dev 传递引用);任一不符停手
```

### 必读文档

- `docs/01_PROJECT_CONSTITUTION.md`(尤其 § 7 异步并发 / **§ 9 数据隐私** / § 12 测试)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(尤其 § 3 目录结构 / § 6 决策 1 / § 7 配置 / § 8 异步 / § 12 日志)
- `docs/04_ENGINEERING_STANDARDS.md`(尤其 § 4 文件 ≤ 300 行 / § 6 依赖管理 / § 9 日志 / § 10 异常处理)
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(实地核查纪律 1 / 4 / 5)
- `docs/decisions/20260604-11-async-blocking-and-logger-exception-bans.md`(本 Task 关键纪律,见 D1 / D13)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(§ 不做 line 95-96 明示本 Task 接管 chat domain + chat store + 异常追加)
- `docs/tasks/task-202-upload-and-parse-api.md`(§ 7.1 / 7.2 / 7.3 接口契约,本 Task 完全照搬 ProjectStore 7 方法签名)
- `docs/tasks/task-103-m-parser.md`(`MFile.raw_code` 字段语义,关系 D15 redaction)

---

## 输出(交付物)

### 新增文件

| 文件 | 预估行数 | 内容 |
|---|---:|---|
| `core/domain/chat.py` | ~60 | `ChatMessage` / `ChatSession` dataclass(D3) |
| `core/interfaces/chat_store.py` | ~85 | `ChatStore` ABC(5 方法,D5) |
| `adapters/storage/schema.py` | ~90 | 集中 CREATE TABLE SQL + 索引 + `CURRENT_SCHEMA_VERSION=1` 常量;`init_schema(conn)` 函数含版本校验(D7) |
| `adapters/storage/_connection.py` | ~70 | aiosqlite 连接管理 `@asynccontextmanager` helper(WAL + busy_timeout + foreign_keys + secure_delete + row_factory,D8) |
| `adapters/storage/_project_json.py` | ~120 | Project ↔ JSON 序列化辅助(`_project_to_json` 含 raw_code redaction;`_project_from_dict` 显式 tuple 还原);若 sqlite_project_store.py 不超 300 行,可内联(D14) |
| `adapters/storage/sqlite_project_store.py` | ~230 | `SqliteProjectStore(ProjectStore)` 7 方法实现(D8 / D12 / D14) |
| `adapters/storage/sqlite_chat_store.py` | ~200 | `SqliteChatStore(ChatStore)` 5 方法实现,SELECT 预检查 + 显式事务(D5 + GPT 一审 P1-2) |
| `tests/core/test_domain_chat.py` | ~50 | ChatMessage / ChatSession 构造测试 |
| `tests/core/test_interfaces_chat_store.py` | ~40 | ChatStore ABC 抽象性测试 + Stub 子类 |
| `tests/core/test_domain_exceptions_v204.py` | ~40 | 新增 2 个异常类的继承关系断言(`isinstance(ChatSessionNotFoundError("x"), ProjectError)` / `isinstance(StoreError("x"), MxaError)`) |
| `tests/adapters/storage/test_schema.py` | ~80 | `init_schema` idempotent + 表存在 + schema_version 版本校验(unsupported / migration_required 抛 StoreError) |
| `tests/adapters/storage/test_sqlite_project_store.py` | ~290 | 7 方法 + 边界 + **raw_code 已 redaction** 断言(D11 tmp_path 文件 DB) |
| `tests/adapters/storage/test_sqlite_chat_store.py` | ~220 | 5 方法 + SELECT 预检查路径 + FK 级联 + 事务回滚 |
| `tests/api/test_lifespan_with_sqlite.py` | ~90 | lifespan 装配 SqliteProjectStore + SqliteChatStore 集成,**不打 overview / LLM**(GPT 一审 Q4) |

### 修改文件

| 文件 | 改动 |
|---|---|
| `core/domain/exceptions.py` | **追加 2 个异常类**(`ChatSessionNotFoundError(ProjectError)` + `StoreError(MxaError)`);**不动**既有 11 个类(GPT 一审 P0-2) |
| `api/main.py` | lifespan 内 `app.state.project_store = SqliteProjectStore(...)` 替换;新增 `app.state.chat_store = SqliteChatStore(...)`;startup 时 `_bootstrap_db(db_path)` 建表;shutdown 时调用各 store `aclose()` |
| `api/dependencies.py` | 新增 `get_chat_store()` 依赖 |
| `requirements.txt` | **追加 1 行** `aiosqlite==0.20.0`(项目第 7 个 runtime 依赖) |
| `adapters/storage/in_memory_project_store.py` | **顶部 docstring 加注** "仅测试 fake,生产用 SqliteProjectStore"(D6) |
| `adapters/storage/__init__.py` | **不导出** `InMemoryProjectStore`;仅导出 `SqliteProjectStore` / `SqliteChatStore`(D6) |
| `adapters/storage/README.md` | 更新职责描述:SQLite 实现 + InMemory 仅测试用 + secure_delete 隐私加固 + FK CASCADE 删除语义 |
| `docs/03_TASK_INDEX.md` | TASK-204 状态 🔲 → **🔍**(等待验收);Week 2 进度条第 4 格 **🔍**(决策 07,Codex 必选并发动作;GPT 一审 Q2 修) |

### 不动文件(明示禁动)

- ❌ `core/interfaces/project_store.py`(接口锁,task-203 line 271)
- ❌ `core/domain/project_status.py`(7 字段冻结)
- ❌ `core/domain/project.py`(9 字段冻结)
- ❌ `app/config.py`(配置零增量,`db_path` 已存在)
- ❌ TASK-201 ERROR_MAP / TASK-202 UploadService / TASK-203 ProjectOverviewService 任何代码
- ❌ `core/prompts/` 任何 yaml
- ❌ `Makefile` / `pyproject.toml` / `.github/workflows/ci.yml`(本 Task 不改 CI / 工具链)
- ❌ `tests/api/conftest.py`(autouse fixture 仍用 InMemory 替换 lifespan store,跑 task-201/202/203 单测;**不动**保证零回归,D6)

> **注**:`core/domain/exceptions.py` 在 v0.1 误列"不动",v0.2 已修正为"修改"(GPT 一审 P0-2)。

---

## 范围(必须做)

- [ ] **Stage 0 实地核查**:跑"必须存在的文件 / 状态"8 条 grep,任一不符停手抛冲突
- [ ] **Stage 1 chat domain + 异常 + ChatStore ABC**:
  - 建 `core/domain/chat.py`:`ChatMessage` + `ChatSession` dataclass(字段见 § 9.1)
  - 改 `core/domain/exceptions.py`:**追加** `ChatSessionNotFoundError(ProjectError)` + `StoreError(MxaError)`(各 3-5 行 docstring,无自定义 `__init__`)
  - 建 `core/interfaces/chat_store.py`:`ChatStore` ABC + 5 abstractmethod(签名见 § 9.2)
  - 建 / 改对应单元测试(domain 字段构造 + 异常继承关系 + ABC 抽象性 + Stub 子类)
- [ ] **Stage 2 schema + connection + SqliteProjectStore**:
  - 建 `adapters/storage/schema.py`:`CURRENT_SCHEMA_VERSION=1`(模块常量)+ `init_schema(conn) -> None` 函数,集中所有 CREATE TABLE SQL + 索引 + 版本校验(§ 9.6)
  - 建 `adapters/storage/_connection.py`:`open_connection(db_path)` **@asynccontextmanager**(PRAGMA WAL / busy_timeout / foreign_keys / secure_delete / synchronous / row_factory,§ 9.5)
  - 建 `adapters/storage/_project_json.py`:`_project_to_json(project)` 含 raw_code redaction + enum.value + datetime.isoformat;`_project_from_dict(d)` 显式 tuple 还原(§ 9.3 + D14)
  - 建 `adapters/storage/sqlite_project_store.py`:实现 7 方法接口(§ 9.3),所有写操作显式 `await conn.commit()`
  - 建测试:7 方法覆盖 + 边界(ProjectNotFoundError / ValueError / list_expired / delete 幂等);**断言 raw_code 已 redaction**(用 sqlite3 读出 JSON 验证)
- [ ] **Stage 3 SqliteChatStore**:
  - 建 `adapters/storage/sqlite_chat_store.py`:实现 5 方法接口(§ 9.4),SELECT 预检查 + 显式事务 BEGIN/COMMIT/ROLLBACK
  - 建测试:5 方法覆盖 + FK 级联(删除 project 同步删 chat)+ 事务回滚(append_message 中途抛错时 message 未 INSERT)
- [ ] **Stage 4 lifespan 装配改造**:
  - 改 `api/main.py` lifespan:替换 `InMemoryProjectStore()` → `SqliteProjectStore(db_path)`;新增 `app.state.chat_store = SqliteChatStore(db_path)`;startup 时 `_bootstrap_db(db_path)`(parent.mkdir + open_connection + init_schema);shutdown 时调各 store `aclose()`
  - 改 `api/dependencies.py`:新增 `get_chat_store()` 依赖
  - 改 `adapters/storage/in_memory_project_store.py` 顶部 docstring + `adapters/storage/__init__.py` 不导出(D6)
  - 改 `adapters/storage/README.md` 更新职责
  - 建集成测试 `tests/api/test_lifespan_with_sqlite.py`:**缩窄范围**(GPT 一审 Q4)— 不打 overview / LLM,只验证 ① db 文件 + schema 表存在 ② `app.state.project_store` 是 `SqliteProjectStore` + `app.state.chat_store` 是 `SqliteChatStore` ③ 直接通过 store 写入 project/status/chat 再读回 ④ TestClient `/health` + `/projects/{id}/status` 跑通(纯存储读路径)
- [ ] **Stage 5 收尾**:
  - 追加 `aiosqlite==0.20.0` 到 `requirements.txt`
  - 更新 `docs/03_TASK_INDEX.md` 状态:🔲 → 🔍(等待验收);Week 2 进度条第 4 格 🔍
  - 本地 `make check` 全绿后 push 分支
- [ ] **每文件 ≤ 300 行**(04 § 4 硬规定;若 `sqlite_project_store.py` 接近 300 行,拆出 `_project_json.py`)
- [ ] **commit 拆分**(参考 task-201 / 202 习惯,每个 commit 单一职责,见 § 8)
- [ ] **PR 描述**(按 04 § 3 模板,逐条勾选 § 10 验收清单)

---

## 不做(明确排除)

- ❌ **不实现 vector store / embedding 持久化** — TASK-302 接管
- ❌ **不实现 chat 端点 + ChatService** — TASK-205 接管(本 Task 只建 ChatStore 接口 + 持久化,不接 HTTP)
- ❌ **不引入 alembic / migration 框架** — MCS 阶段 `CREATE TABLE IF NOT EXISTS` + `schema_version` 单行表 + 版本校验已够(D7)
- ❌ **不引入 SQLAlchemy / ORM** — aiosqlite 原生 SQL 字符串足够,引 ORM 是过度抽象(02 § 6 决策 1 风格)
- ❌ **不改 ProjectStore 接口签名 / Project dataclass / ProjectStatusRecord 字段** — 全部已锁
- ❌ **不删 InMemoryProjectStore 源文件** — 保留为测试 fake(D6)
- ❌ **不在本 Task 落开 / 关闭 worker > 1 的部署** — 本 Task 完成提供"技术可行性",实际 uvicorn 启动参数仍单 worker(避免本 Task 范围外的运维变动)
- ❌ **不写 User / quota / activation_codes 表** — Phase 2 与 TASK-404 接管
- ❌ **不调任何 LLM / 不读 prompt yaml** — 纯持久化层;Stage 4 lifespan 集成测试**不触发 overview / chat**(GPT 一审 Q4)
- ❌ **不持久化 `MFile.raw_code` 工程原始内容** — Project JSON 化前显式 redaction `raw_code=""`(D15,01 § 9 line 339 硬约束)
- ❌ **不在 route 层 try/except 业务异常** — 异常翻译统一走 TASK-201 ERROR_MAP;新异常的 handler 注册延后 TASK-205 / TASK-206(GPT 一审 P0-3)
- ❌ **不修改 `core/prompts/` / `tests/fixtures/` / `eval/` / `scripts/`** — 范围外

---

## 实施步骤(5 Stage,顺序固定)

| Stage | 内容 | 预估 commit |
|---|---|---|
| 0 | 实地核查 8 条 grep,任一不符停手抛冲突 | 无(仅核查) |
| 1 | chat domain + 异常追加 + ChatStore ABC + 测试 | `feat(domain): add ChatMessage / ChatSession`<br>`feat(domain): add ChatSessionNotFoundError + StoreError`<br>`feat(interfaces): add ChatStore ABC`<br>`test(core): add chat domain + chat store + new exception tests` |
| 2 | schema + connection helper + _project_json + SqliteProjectStore + 测试 | `feat(storage): add SQL schema + version check`<br>`feat(storage): add aiosqlite connection context manager`<br>`feat(storage): add Project json (with raw_code redaction)`<br>`feat(storage): add SqliteProjectStore impl`<br>`test(storage): add SqliteProjectStore tests` |
| 3 | SqliteChatStore + 测试 | `feat(storage): add SqliteChatStore impl`<br>`test(storage): add SqliteChatStore tests` |
| 4 | lifespan 装配改造 + 集成测试 + InMemory 测试 fake 标注 | `refactor(api): wire SqliteProjectStore / SqliteChatStore in lifespan`<br>`feat(api): add get_chat_store dependency`<br>`docs(storage): mark InMemoryProjectStore as test fake`<br>`test(api): add lifespan SQLite integration (no LLM)` |
| 5 | 收尾:requirements / 03 索引 | `chore: add aiosqlite==0.20.0 to requirements.txt`<br>`docs: mark TASK-204 as in-review in task index` |

**commit subject 单行无 body**(反例 17 / PM 偏好)。

---

## 接口契约

> **以下代码块是本 Task 的硬契约**,**字段名 / 类型 / 默认值 / 方法签名 / 异常类型 / 上下文管理形态不允许擅自修改**。
> 如实施时发现任何字段缺失 / 类型可优化 / 应增加方法,**停手问 PM**,不要默默偏离。

### 9.1 `core/domain/chat.py` — ChatMessage / ChatSession

```python
"""对话消息与会话 domain 数据结构(TASK-204)。"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


# 角色:user(学生提问)/ assistant(LLM 回答)/ system(系统消息,如错误降级提示)
ChatRole = Literal["user", "assistant", "system"]


@dataclass
class ChatMessage:
    """单条对话消息。所有字段持久化进 chat_message 表。"""
    message_id: str           # UUID4,主键
    session_id: str           # FK → chat_session
    role: ChatRole
    content: str              # 用户提问 / LLM 回答原文
    created_at: datetime      # naive UTC(沿用 task-202 datetime.utcnow() 习惯)
    # citations 列表序列化为 JSON 文本入库;空列表表示无证据(用于"不确定"降级)
    citations_json: str = "[]"


@dataclass
class ChatSession:
    """单次对话会话,绑定 project_id。"""
    session_id: str           # UUID4,主键
    project_id: str           # FK → project_status_record(数据库层 FK,ON DELETE CASCADE)
    created_at: datetime      # naive UTC
    updated_at: datetime      # 最近一条 message 时间,naive UTC
    title: str | None = None  # 用户给会话起的标题(可选,MCS 阶段不暴露 UI)
```

**字段不变量**:

- `ChatMessage.message_id` / `ChatSession.session_id`:UUID4 字符串,生成由调用方(TASK-205 ChatService),**ChatStore 不生成 ID**
- `ChatMessage.citations_json`:**字符串字段**,不是 `list[SourceRef]`(避免 dataclass 跨边界传 list 引用)。序列化 / 反序列化由 ChatService 负责(本 Task 不引入 json 依赖到 domain)
- `ChatSession.title`:MCS 阶段可空,TASK-205 / 402 决定是否暴露
- **不引入** `tokens_in` / `tokens_out` / `latency_ms` / `model` 字段:LLM 元数据由 ChatService 经 logger 落 metadata-only 日志(决策 11 § 决策 2),**不入库**(数据隐私 + schema 收敛)
- **datetime 字段全部 naive**(无 tzinfo,沿用 task-202 习惯,详见风险 2)

### 9.2 `core/interfaces/chat_store.py` — ChatStore ABC

```python
"""对话历史存储抽象接口(TASK-204 SQLite 实现)。

设计原则:
1. 与 ProjectStore 平行(7 方法 / 本接口 5 方法)
2. 全部 async(aiosqlite,02 § 8 锁)
3. session-message 1:N 关系;FK 在 SQLite 层维护(D7 schema)
4. **不暴露原始 connection / cursor**,纯 dataclass in/out
5. 异常显式列在 docstring;调用方(ChatService)负责在 ERROR_MAP 注册 HTTP 映射,
   **route 层禁止 try/except 业务异常**(GPT 一审 P0-3)
"""
from abc import ABC, abstractmethod

from core.domain.chat import ChatMessage, ChatSession


class ChatStore(ABC):
    """对话存储(5 方法)。"""

    @abstractmethod
    async def create_session(self, session: ChatSession) -> None:
        """创建会话。
        - session.project_id 不存在于 project_status_record 表 → ProjectNotFoundError
        - session.session_id 已存在 → ValueError(调用方应生成新 UUID 重试)
        """

    @abstractmethod
    async def append_message(self, message: ChatMessage) -> None:
        """追加消息到会话,同步更新 session.updated_at(单事务)。
        - message.session_id 不存在 → ChatSessionNotFoundError
        - message.message_id 已存在 → ValueError
        """

    @abstractmethod
    async def get_session(self, session_id: str) -> ChatSession:
        """取会话元信息。不存在 → ChatSessionNotFoundError。"""

    @abstractmethod
    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        """按 created_at ASC 列消息。
        - 会话不存在 → ChatSessionNotFoundError
        - limit ≤ 200 / offset ≥ 0 → 超界抛 ValueError
        """

    @abstractmethod
    async def list_recent_sessions(
        self, project_id: str, limit: int = 20
    ) -> list[ChatSession]:
        """按 updated_at DESC 列会话。
        - limit ≤ 100
        - project 不存在返回空列表(不抛异常,允许"无对话"状态)
        """
```

**新增异常(本 Task 在 `core/domain/exceptions.py` 追加)**:

```python
class ChatSessionNotFoundError(ProjectError):
    """指定对话会话不存在。继承 ProjectError(chat 是 project 子资源)。"""


class StoreError(MxaError):
    """持久化存储层异常(SQLite OperationalError / JSON decode / schema 版本不匹配等)。

    构造仅接受单个 message 字符串(无自定义 __init__);
    日志仅记录 type(exc).__name__,不记录 message(决策 11)。
    """
```

**异常树最终形态**(决策 09 纪律 4 数值核查:**总计 13 个异常类**,既有 11 + 新增 2):

```
MxaError
├── ProjectError
│   ├── ProjectNotFoundError       (TASK-101 已建)
│   └── ChatSessionNotFoundError   (TASK-204 新增)
├── UploadError + 4 子类           (TASK-101 已建)
├── ParseError + 2 子类            (TASK-101 已建)
├── LLMError + 5 子类              (TASK-101 已建)
├── QuotaExhaustedError            (TASK-101 已建)
├── EvidenceMissingError           (TASK-101 已建)
└── StoreError                     (TASK-204 新增,平行于 ProjectError 等)
```

**HTTP 映射延后**:

- TASK-201 ERROR_MAP **本 Task 不动**(8 handler 不增不减)
- TASK-205 / TASK-206 决定 `ChatSessionNotFoundError` 与 `StoreError` 的 HTTP 映射:
  - 推荐 `ChatSessionNotFoundError → HTTP 404`(类比 `ProjectNotFoundError`)
  - 推荐 `StoreError → HTTP 500`(基础设施错)
- TASK-205 若先于 TASK-206 暴露 chat 端点,**应在 TASK-205 自身追加这两条 handler 到 ERROR_MAP**,**不在 route 层 try/except 业务异常**(违反 task-202 / 203 已建立的"route 不 try/except,统一 ERROR_MAP"风格,GPT 一审 P0-3 指出)
- 替代方案:把 TASK-206 部分前置,在 TASK-205 启动前完成 ERROR_MAP 扩展(由 PM 在派 TASK-205 时决定)

### 9.3 `adapters/storage/sqlite_project_store.py` — SqliteProjectStore 实现要点

**类签名**:

```python
class SqliteProjectStore(ProjectStore):
    """SQLite 持久化 ProjectStore(7 方法接口 0 改动,TASK-204)。

    构造时不立即建表;由 lifespan 启动时显式调用 _bootstrap_db -> init_schema 完成。
    Project 序列化前 redaction MFile.raw_code,对齐 01 § 9 数据隐私(D15)。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """lifespan shutdown 调用。MCS 阶段连接按需打开 + 即关,本方法 no-op,
        预留 Phase 2 接入连接池时实现。"""
```

**7 方法实现要点表**(签名照搬 `ProjectStore`,**所有写操作显式 `await conn.commit()`**,GPT 一审 P0-5):

| 方法 | SQL 操作 | commit 时机 | 异常映射 |
|---|---|---|---|
| `create_pending` | `INSERT INTO project_status_record(project_id, name, status, created_at, updated_at) VALUES (?,?,?,?,?)`;`status='parsing'`,`project=NULL`,`error_code=NULL` | 单 INSERT 后 `await conn.commit()` | `IntegrityError`(UNIQUE)→ `ValueError`;`OperationalError` → `StoreError("sqlite_operation_failed")` |
| `mark_ready` | 先 `_project_to_json(project)` 生成 JSON 文本(含 raw_code redaction,D15);再 `UPDATE ... SET status='ready', project=?, updated_at=? WHERE project_id=? AND status='parsing'`;`rowcount==0` → `ValueError` | 单 UPDATE 后 `await conn.commit()` | 同上 + JSON serialize 异常 → `StoreError("project_serialize_failed")` |
| `mark_failed` | `UPDATE ... SET status='failed', error_code=?, updated_at=? WHERE project_id=? AND status='parsing'`;`rowcount==0` → `ValueError` | 单 UPDATE 后 `await conn.commit()` | `OperationalError` → `StoreError("sqlite_operation_failed")` |
| `get_status_view` | `SELECT project_id, name, status, created_at, error_code FROM ... WHERE project_id=?` → `ProjectStatusView(5 字段)`;空行 → `ProjectNotFoundError` | 纯读,无 commit | `OperationalError` → `StoreError("sqlite_operation_failed")` |
| `get_project` | `SELECT project FROM ... WHERE project_id=? AND status='ready'`;空行 → `ProjectNotFoundError`;`_project_from_dict(json.loads(...))` 反序列化(D14) | 纯读,无 commit | `JSONDecodeError` → `StoreError("project_deserialize_failed")` + `OperationalError` → `StoreError("sqlite_operation_failed")` |
| `list_expired` | `SELECT project_id FROM ... WHERE created_at < ?`(以 `(datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat()` 为阈值;naive UTC 文本字典序比较等价时序比较) | 纯读,无 commit | 同上 |
| `delete` | `DELETE FROM ... WHERE project_id=?`;FK ON DELETE CASCADE 自动级联删 chat_session / chat_message;`rowcount==0` 静默 no-op(幂等) | 单 DELETE 后 `await conn.commit()` | `OperationalError` → `StoreError("sqlite_operation_failed")` |

**Project ↔ JSON 序列化策略(D14 实现要点,详细决策见 D14 + D15)**:

辅助函数定位:

- 若 `sqlite_project_store.py` 接近 300 行(04 § 4 硬规定),拆 `_project_to_json` / `_project_from_dict` 到独立文件 `adapters/storage/_project_json.py`
- 否则可内联 sqlite_project_store.py 末尾(私有函数,下划线前缀)

**`_project_to_json(project: Project) -> str` 关键逻辑(D14 + D15)**:

```python
def _project_to_json(project: Project) -> str:
    """Project → JSON 文本,含 raw_code redaction。

    隐私约束(D15 + 01 § 9 line 339):
    - 不持久化 MFile.raw_code(工程原始代码)
    - asdict 后显式置 m_files[i].raw_code = ""
    """
    data = asdict(project)
    # Enum / datetime / nested types 显式处理(GPT 一审 P1-3)
    data["project_type"] = project.project_type.value
    data["created_at"] = project.created_at.isoformat()
    # D15 redaction:不持久化 .m 原文
    for m_file in data["m_files"]:
        m_file["raw_code"] = ""
    # MFile.functions[i].line_range 是 tuple,asdict 转 list,JSON 落库后反序列化时还原
    # SlxBlock.position 同理
    return json.dumps(data, ensure_ascii=False)  # 中文 block 名可读
```

**`_project_from_dict(d: dict) -> Project` 关键逻辑(P1-3 反序列化)**:

```python
def _project_from_dict(d: dict) -> Project:
    """JSON dict → Project,显式还原 enum / datetime / tuple 字段。

    asdict 时 tuple 字段转为 list,JSON 不区分 list / tuple;
    反序列化必须显式 tuple(...) 转换,否则 dataclass 字段类型漂移。
    """
    return Project(
        id=d["id"],
        name=d["name"],
        project_type=ProjectType(d["project_type"]),       # 显式 Enum 还原
        files=[FileInfo(**f) for f in d["files"]],
        slx_models=[_slx_model_from_dict(m) for m in d["slx_models"]],
        m_files=[_m_file_from_dict(mf) for mf in d["m_files"]],
        mat_files=[_mat_metadata_from_dict(mt) for mt in d["mat_files"]],
        created_at=datetime.fromisoformat(d["created_at"]),  # 显式 naive datetime
        file_dependencies=d["file_dependencies"],
    )


def _slx_model_from_dict(d: dict) -> SlxModel:
    return SlxModel(
        file_path=d["file_path"],
        name=d["name"],
        blocks=[_slx_block_from_dict(b) for b in d["blocks"]],
        lines=[SlxLine(**ln) for ln in d["lines"]],
        subsystems=d["subsystems"],
        solver_config=d["solver_config"],
        parse_warnings=d["parse_warnings"],
    )


def _slx_block_from_dict(d: dict) -> SlxBlock:
    return SlxBlock(
        block_id=d["block_id"],
        name=d["name"],
        block_type=d["block_type"],
        parameters=d["parameters"],
        position=tuple(d["position"]),  # tuple 还原(P1-3)
        parent_subsystem=d["parent_subsystem"],
        is_masked=d.get("is_masked", False),
        is_library_link=d.get("is_library_link", False),
        is_model_reference=d.get("is_model_reference", False),
    )
```

**剩余辅助**(`_m_file_from_dict` / `_m_function_from_dict` / `_mat_metadata_from_dict` / `_mat_variable_from_dict`)按相同模式逐层构造,**MFunction.line_range** 同样显式 `tuple(d["line_range"])` 还原。

**datetime 编码(D14 子注解 + 风险 2 已实地核查)**:

- **task-202 已合并行为**(line 512 / 532 / 545 / 568 / 849):全部 naive `datetime.utcnow()`
- 本 Task **沿用** naive `datetime.utcnow()`,**不切到** aware `datetime.now(timezone.utc)`
- 入库:`datetime.utcnow().isoformat()` → 文本(无时区后缀,如 `2026-06-04T12:34:56.789012`)
- 出库:`datetime.fromisoformat(text)` → naive datetime
- 字段名 `created_at` / `updated_at` 默认即 UTC(README + docstring 明示);Python 3.12+ `datetime.utcnow()` DeprecationWarning 但仍工作,Phase 2 独立 chore 迁移到 aware datetime

**禁止**:

- ❌ 用 `default=str` 让 `json.dumps` 自动处理 enum(`str(ProjectType.GENERAL)` = `"ProjectType.GENERAL"`,**不是** `"general"`,GPT 一审 P1-3)
- ❌ 用 `default=str` 让 `json.dumps` 自动处理 datetime(隐式格式不可控,显式 `.isoformat()` 更稳)
- ❌ 引入 `dataclasses-json` / `marshmallow` / `pydantic.dataclasses`(domain 层不依赖 pydantic,task-101 § 通用约束第 1 条)
- ❌ JSON 反序列化后直接 `Project(**d)`(嵌套 dataclass 不还原 + tuple 字段会变 list)

### 9.4 `adapters/storage/sqlite_chat_store.py` — SqliteChatStore 实现要点

**类签名**:

```python
class SqliteChatStore(ChatStore):
    """SQLite 持久化 ChatStore(5 方法接口,TASK-204)。

    异常语义稳定靠"SELECT 预检查 → INSERT"模式,不依赖 SQLite IntegrityError
    错误字符串区分 UNIQUE / FK(GPT 一审 P1-2)。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """同 SqliteProjectStore.aclose,MCS no-op。"""
```

**5 方法实现要点(显式预检查 + 显式事务,GPT 一审 P1-2 + P0-5)**:

#### `create_session`(显式预检查避免 IntegrityError message 解析)

流程:

1. `async with open_connection(self._db_path) as conn:`
2. `SELECT 1 FROM project_status_record WHERE project_id=?` — 检查 project 存在
3. 无行 → 抛 `ProjectNotFoundError`(调用方 ChatService 已知此契约)
4. `INSERT INTO chat_session(session_id, project_id, created_at, updated_at, title) VALUES (?,?,?,?,?)`
5. `IntegrityError`(主键 session_id 已存在)→ 抛 `ValueError("session_id already exists")`
6. `await conn.commit()`
7. 其他 `OperationalError` → 抛 `StoreError("sqlite_operation_failed")` from None

#### `append_message`(显式事务 BEGIN / SELECT / INSERT / UPDATE / COMMIT)

流程:

```text
async with open_connection(self._db_path) as conn:
    try:
        await conn.execute("BEGIN")                                 -- 显式事务
        cur = await conn.execute(
            "SELECT 1 FROM chat_session WHERE session_id=?",
            (message.session_id,),
        )
        row = await cur.fetchone()
        if row is None:
            await conn.rollback()
            raise ChatSessionNotFoundError(message.session_id)

        try:
            await conn.execute(
                "INSERT INTO chat_message(message_id, session_id, role, content, "
                "created_at, citations_json) VALUES (?,?,?,?,?,?)",
                (message.message_id, message.session_id, message.role,
                 message.content, message.created_at.isoformat(),
                 message.citations_json),
            )
        except aiosqlite.IntegrityError:
            await conn.rollback()
            raise ValueError("message_id already exists") from None

        await conn.execute(
            "UPDATE chat_session SET updated_at=? WHERE session_id=?",
            (message.created_at.isoformat(), message.session_id),
        )
        await conn.commit()
    except (ChatSessionNotFoundError, ValueError):
        raise
    except aiosqlite.OperationalError as exc:
        await conn.rollback()
        logger.error(
            "SqliteChatStore.append_message failed: session_id={} exception={}",
            message.session_id, type(exc).__name__,
        )
        raise StoreError("sqlite_operation_failed") from None
```

**注**:伪代码示意控制流;实际 Codex 实现按此模式,行长 / 命名按 04 § 4 约定。

#### `get_session`

`SELECT session_id, project_id, created_at, updated_at, title FROM chat_session WHERE session_id=?`;空行 → `ChatSessionNotFoundError`;反序列化 `datetime.fromisoformat`。纯读,无 commit。

#### `list_messages`

1. 先 `SELECT 1 FROM chat_session WHERE session_id=?` 预检查(避免空数组与"session 不存在"歧义)
2. 无行 → `ChatSessionNotFoundError`
3. `limit > 200` 或 `offset < 0` → `ValueError`
4. `SELECT message_id, session_id, role, content, created_at, citations_json FROM chat_message WHERE session_id=? ORDER BY created_at ASC LIMIT ? OFFSET ?`

纯读,无 commit。

#### `list_recent_sessions`

- `limit > 100` → `ValueError`
- `SELECT ... FROM chat_session WHERE project_id=? ORDER BY updated_at DESC LIMIT ?`
- project 不存在 → 返回 `[]`(不抛异常,允许"无对话"状态;**不**做 project 预检查 SELECT,减少一次查询)

纯读,无 commit。

**事务边界总结**(GPT 一审 P0-5):

| 方法 | commit / 事务 |
|---|---|
| `create_session` | 单 INSERT + `commit()` |
| `append_message` | 显式 `BEGIN` / SELECT / INSERT / UPDATE / `commit()`(或 `rollback()`) |
| `get_session` | 纯读 |
| `list_messages` | 纯读 |
| `list_recent_sessions` | 纯读 |

### 9.5 `adapters/storage/_connection.py` — open_connection async context manager

**唯一公开函数(GPT 一审 P0-4 + P1-5 完整重写)**:

```python
"""aiosqlite 连接管理 helper(TASK-204)。

开放 API:
    open_connection(db_path) — @asynccontextmanager,正确支持 `async with` 语法

PRAGMA 顺序在每次连接打开时全部执行(SQLite PRAGMA 是 per-connection 状态)。
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


@asynccontextmanager
async def open_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """打开 aiosqlite 连接,配置 PRAGMA 后 yield,退出时关闭。

    PRAGMA 配置:
        journal_mode=WAL        -- 多 worker 并发读 + 单 worker 写,WAL 是 MCS 持久化基础
        busy_timeout=5000       -- 5 秒等锁,避免短时冲突报错
        foreign_keys=ON         -- 启用 FK 约束(SQLite 默认关闭,FK CASCADE 删除依赖此)
        synchronous=NORMAL      -- WAL 模式下安全 + 性能平衡(FULL 太重,OFF 不安全)
        secure_delete=ON        -- 删除 row 后覆盖 freelist 页面,降低工程内容残留
                                   隐私风险(GPT 一审 P1-5,对齐 01 § 9 + 24h TTL)

    row_factory = aiosqlite.Row(命名访问列,出库 row["field_name"])

    使用模式(强制):
        async with open_connection(db_path) as conn:
            await conn.execute(...)
            await conn.commit()
        # 退出 with 块时自动 close

    禁止:
        - 持久化 conn 在 store 实例 self._conn(状态泄漏 + 关闭歧义)
        - await open_connection(...) 不带 async with(因为是 context manager,
          直接 await 是 TypeError)
    """
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA secure_delete=ON")
        yield conn
    finally:
        await conn.close()
```

**为什么不池化连接(D8)**:见 D8 决策日志。简要:MCS QPS < 1,WAL 模式下 connect ~ ms 级开销可忽略。

**禁止**:

- ❌ `async def open_connection(db_path) -> aiosqlite.Connection`(v0.1 形态,GPT 一审 P0-4 抓出:返回 coroutine 不能 `async with`,硬错)
- ❌ `self._conn = await open_connection(...)` 在 store 实例持久化
- ❌ 在 store 方法内手写 `await aiosqlite.connect(...)` + `await conn.close()`(应统一走 `open_connection`,PRAGMA 才会一致)

### 9.6 `adapters/storage/schema.py` — DDL + 版本校验 init_schema

**模块常量 + 唯一公开函数**:

```python
"""SQLite schema 定义 + idempotent 建表(TASK-204)。

CURRENT_SCHEMA_VERSION 每次 schema 变更时由对应 Task bump:
    1 = TASK-204 初版(3 业务表 + 1 schema_version 表)
    2 = TASK-302 加 chunks 表(向量存储,本 TASK 实施)
    3 = TASK-404 加 activation_codes 表(预留)
"""
CURRENT_SCHEMA_VERSION = 1


_DDL = """
-- 版本元数据(单行表,id 固定 1)
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

-- ProjectStatusRecord 持久化(7 字段对应 task-202 dataclass)
CREATE TABLE IF NOT EXISTS project_status_record (
    project_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,                          -- 已 _sanitize_filename 清洗
    status       TEXT NOT NULL CHECK (status IN ('parsing','ready','failed')),
    created_at   TEXT NOT NULL,                          -- ISO8601 naive UTC
    updated_at   TEXT NOT NULL,
    project      TEXT,                                   -- JSON,ready 状态填,其他 NULL
    error_code   TEXT                                    -- failed 状态填,其他 NULL
);
CREATE INDEX IF NOT EXISTS idx_project_created_at ON project_status_record(created_at);

-- ChatSession(FK → project_status_record,ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS chat_session (
    session_id   TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    title        TEXT,
    FOREIGN KEY (project_id) REFERENCES project_status_record(project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_session_project ON chat_session(project_id, updated_at DESC);

-- ChatMessage(FK → chat_session,ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS chat_message (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    citations_json  TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (session_id) REFERENCES chat_session(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_message(session_id, created_at ASC);
"""


async def init_schema(conn: aiosqlite.Connection) -> None:
    """idempotent 建表 + 版本校验。

    GPT 一审 P1-4:必须处理 schema_version 不匹配场景。

    流程:
        1. 执行 _DDL(全部 CREATE TABLE IF NOT EXISTS + 索引)
        2. INSERT OR IGNORE INTO schema_version VALUES (1, CURRENT_SCHEMA_VERSION, isoformat)
        3. SELECT version FROM schema_version WHERE id=1
        4. version > CURRENT_SCHEMA_VERSION → StoreError("unsupported_schema_version")
           (DB 比代码新,可能是回滚 / 误升级)
        5. version < CURRENT_SCHEMA_VERSION → StoreError("schema_migration_required")
           (本 Task 不做 migration;后续 TASK-302 / 404 各自实现 ALTER + bump)
        6. await conn.commit()
    """
```

**实施要点**:

- `_DDL` 用 `await conn.executescript(_DDL)`(aiosqlite 支持多语句脚本)
- `INSERT OR IGNORE` 保证幂等(首次插入,后续启动跳过)
- 校验逻辑用 `cur = await conn.execute("SELECT version FROM schema_version WHERE id=1"); row = await cur.fetchone()`
- 末尾 `await conn.commit()`(DDL + INSERT 全部入库,GPT 一审 P0-5)
- `applied_at` 用 `datetime.utcnow().isoformat()`,**不用** SQLite `datetime('now')`(统一 Python 层时间生成,避免格式混杂)

**禁止**:

- ❌ 不显式校验版本就 INSERT(v0.1 错;P1-4 修)
- ❌ 用 `datetime('now')` 让 SQLite 生成时间(格式 `YYYY-MM-DD HH:MM:SS` 与 Python isoformat `2026-06-04T12:34:56.789` 不一致)
- ❌ DDL 不 commit(MCS SQLite WAL 下 DDL 也需 commit 才持久化)

### 9.7 lifespan 装配改造(对 `api/main.py`)

**改动锁定**(`api/main.py` lifespan 函数):

```python
# 改动前(task-203 末态):
#     app.state.project_store = InMemoryProjectStore()
#     app.state.upload_service = UploadService(...)
#     app.state.overview_cache = TTLCache(...)
#     app.state.text_provider = DeepSeekTextProvider(...)
#     ...

# 改动后(本 Task):
async with _bootstrap_db(settings.db_path):                          # 启动时 init_schema 一次
    app.state.project_store = SqliteProjectStore(settings.db_path)   # 替换
    app.state.chat_store = SqliteChatStore(settings.db_path)         # 新增
    app.state.upload_service = UploadService(...)                    # 不动
    app.state.overview_cache = TTLCache(...)                         # 不动
    app.state.text_provider = DeepSeekTextProvider(...)              # 不动
    yield
    await app.state.project_store.aclose()                           # 新增
    await app.state.chat_store.aclose()                              # 新增
```

**`_bootstrap_db` helper**(`api/main.py` 内私有 async context manager):

- 入参:`db_path: str`
- 实现:`async with open_connection(db_path) as conn: await init_schema(conn)`;yield 阶段不持有 conn
- 错误:`OSError`(目录不存在 → `open_connection` 已 mkdir 父目录)/ `aiosqlite.OperationalError`(磁盘满 / 权限错)/ `StoreError`(版本不匹配)→ **lifespan 启动失败,uvicorn 退出**。**不掩盖**(基础设施 / schema 错应让用户看到)

**新增 `get_chat_store()` dependency**(`api/dependencies.py`):

```python
def get_chat_store(request: Request) -> ChatStore:
    """从 app.state 取 chat_store(由 lifespan 装配)。"""
    store = getattr(request.app.state, "chat_store", None)
    if store is None:
        raise RuntimeError("ChatStore not initialized; lifespan misconfigured")
    return store
```

**测试 fixture**(`tests/api/conftest.py` 改动 — 实际**不动**,D6):

- 现状(task-202):autouse fixture 替换 `app.state.project_store = InMemoryProjectStore()` 跑测试
- 改动:**不动现有 autouse fixture**(继续用 InMemory 跑 task-201/202/203 单测,**保留 InMemoryProjectStore 为测试 fake**,D6)
- 新增 `tests/api/test_lifespan_with_sqlite.py`:**独立** TestClient + `tmp_path / "test.db"`,**禁用** autouse fixture,跑 lifespan 真起 SQLite,**不打 overview / LLM**(GPT 一审 Q4)

---

## 验收标准

### 1. Stage 0 实地核查 8 条 grep 全通过

PR 描述中**明示**每条 grep 的实际输出,与预期一致。

### 2. 单元测试全绿(子目录路径,GPT 一审 Q3)

```bash
pytest tests/core/test_domain_chat.py \
       tests/core/test_interfaces_chat_store.py \
       tests/core/test_domain_exceptions_v204.py \
       tests/adapters/storage/test_schema.py \
       tests/adapters/storage/test_sqlite_project_store.py \
       tests/adapters/storage/test_sqlite_chat_store.py \
       tests/api/test_lifespan_with_sqlite.py -v
```

预期:全部通过。**所有 store 测试用 `tmp_path / "test.db"` 文件 DB**(D11,GPT 一审 P1-1),不用 `:memory:`。

### 3. 既有测试无回归

```bash
pytest tests/ -v
```

预期:全绿。**重点关注** `tests/api/test_upload_*.py` / `tests/api/test_overview_*.py`(task-202 / 203 测试)继续通过(autouse fixture 仍用 InMemory 替换,不被影响)。

### 4. lint + type-check + format 全绿

```bash
make lint        # ruff check
make type-check  # mypy
make format-check  # ruff format --check
```

三者 0 error。**对齐 ci.yml 实际 `run:` 步骤**(决策 09 纪律 6 / 7)。

### 5. 每文件 ≤ 300 行

```bash
wc -l core/domain/chat.py core/interfaces/chat_store.py \
      adapters/storage/schema.py adapters/storage/_connection.py \
      adapters/storage/_project_json.py \
      adapters/storage/sqlite_project_store.py \
      adapters/storage/sqlite_chat_store.py \
      | sort -n
```

预期:所有文件 < 300。若 `sqlite_project_store.py` 接近上限,JSON 辅助函数已拆到 `_project_json.py`。

### 6. requirements.txt 仅追加 1 行

```bash
git diff origin/main..HEAD -- requirements.txt
```

预期:`+aiosqlite==0.20.0` 单行追加,其他不变。

### 7. 决策 11 兜底两条 grep 应空(决策 11 § 工程影响)

```bash
# 决策 11 决策 2:不准 logger.exception
grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
# 期望:空输出

# 决策 11 决策 1:async def 内可疑同步重活 — 本 Task 用 aiosqlite 原生 async,
# 不应出现 to_thread+sqlite 桥接 或 同步 sqlite3 调用
grep -rn 'asyncio\.to_thread.*sqlite\|^import sqlite3\|^from sqlite3' \
  adapters/storage/ --include='*.py' --exclude-dir=.venv
# 期望:空输出
```

### 8. `make check` 一键全检

```bash
make check
```

应输出 "All checks passed!" 或等价。

### 9. lifespan 启动行为真起验证(单 worker,**不打 LLM**)

```bash
# 启动服务(不依赖 .env,会用 AppSettings 默认 db_path)
uvicorn api.main:app --host 127.0.0.1 --port 8000 &
sleep 2

# 验证 1:db 文件已创建
ls -la ./data/mxa.db
# 期望:文件存在

# 验证 2:表已建(GPT 一审 Q4 — 不打 overview / chat)
sqlite3 ./data/mxa.db ".tables"
# 期望:chat_message  chat_session  project_status_record  schema_version

# 验证 3:schema_version 已写为 1
sqlite3 ./data/mxa.db "SELECT id, version FROM schema_version;"
# 期望:1|1

# 验证 4:健康检查通过
curl -s http://127.0.0.1:8000/health
# 期望:HTTP 200 + 健康状态 JSON

# 关闭服务
kill %1
```

**注**:本步骤是 **PM 本地体验**,**不阻塞** Task 完成(架构师交接备忘录:真启动验收不在硬验收清单)。CI 不跑此步;实施 PR 通过的硬条件是 1-8 + 10-15。

### 10. 隐私 — raw_code 已 redaction(GPT 一审 P0-1 + D15)

```bash
# 真启动 + 上传一个工程后,验证 .m 原文未持久化进 DB
# (此步在验收 9 之后,需要 task-202 上传路径走过一次)
python3 - <<'PY'
import json, sqlite3

db = sqlite3.connect("./data/mxa.db")
rows = db.execute("SELECT project FROM project_status_record WHERE project IS NOT NULL").fetchall()

if not rows:
    print("OK: no ready projects yet (skip)")
else:
    for (project_json,) in rows:
        data = json.loads(project_json)
        for mf in data.get("m_files", []):
            assert mf.get("raw_code", "") == "", \
                f"raw_code MUST be redacted in DB, got: {mf['raw_code'][:50]!r}"
        print(f"OK: project {data.get('id', '?')} has all m_files raw_code redacted")
PY
```

期望:**所有 ready 状态的 project 中,`m_files[*].raw_code` 字段为空字符串**(D15)。

### 11. schema_version 校验(GPT 一审 P1-4)

```bash
# 验证版本号写入正确
sqlite3 ./data/mxa.db "SELECT id, version FROM schema_version;"
# 期望:1|1

# 检查代码常量与 DB 一致
grep -n "CURRENT_SCHEMA_VERSION" adapters/storage/schema.py
# 期望:CURRENT_SCHEMA_VERSION = 1
```

### 12. PRAGMA 配置生效(GPT 一审 P0-4 / P1-5)

```bash
sqlite3 ./data/mxa.db "PRAGMA foreign_keys;"
# 期望:1(已启用 FK,CASCADE 删除依赖此)

sqlite3 ./data/mxa.db "PRAGMA secure_delete;"
# 期望:1(启用 secure_delete,降低 freelist 残留)

sqlite3 ./data/mxa.db "PRAGMA journal_mode;"
# 期望:wal
```

> **注**:`PRAGMA` 是 per-connection 状态,但 `journal_mode` 是持久化的,可在任意连接查询。`foreign_keys` / `secure_delete` 默认每次连接重新设置(在 `open_connection` 内),独立验证靠测试覆盖。

### 13. `open_connection` 必须 @asynccontextmanager(GPT 一审 P0-4)

```bash
# 验证 open_connection 不是裸 async def(否则 async with 用法会 TypeError)
grep -B 1 "async def open_connection" adapters/storage/_connection.py
# 期望:上一行有 @asynccontextmanager 装饰器
```

### 14. exceptions.py 仅追加 2 类(GPT 一审 P0-2)

```bash
git diff origin/main..HEAD -- core/domain/exceptions.py
# 期望:diff 中只新增 2 个 class 定义(ChatSessionNotFoundError + StoreError)
#       既有 11 个异常类不动
```

### 15. 测试路径子目录(GPT 一审 Q3)

```bash
ls tests/adapters/storage/
# 期望:test_in_memory_project_store.py(已有,task-202)
#       + test_schema.py / test_sqlite_project_store.py / test_sqlite_chat_store.py(本 Task 新增)
```

### 16. PR 元信息

- PR 标题:`TASK-204: SQLite 存储层(ProjectStore + ChatStore 持久化)`
- 分支名:`task/TASK-204-sqlite-storage`
- PR 描述按 04 § 3 模板,逐条勾选 1-15 项并简述

---

## 风险与注意点

### 风险 1 — SQLite 文件路径目录不存在

`AppSettings.db_path` 默认 `./data/mxa.db`,**`./data/` 目录可能不存在**(尤其首次启动或 CI 环境)。

**规避**:`open_connection` 内 `Path(db_path).parent.mkdir(parents=True, exist_ok=True)`,与 task-202 `upload_dir` 处理一致(§ 9.5 已实现)。

### 风险 2 — datetime 时区一致性(已实地核查 task-202)

**已知事实**(实地核查 task-202 line 512 / 532 / 545 / 568 / 849):task-202 全程用 **naive** `datetime.utcnow()`(无 tzinfo)。本 Task **沿用** naive datetime,与 task-202 接口语义零差异(详见 § 9.3 末尾 datetime 编码注解)。

**Codex 实施时**:

- 所有新生成的 datetime 字段用 `datetime.utcnow()`,**不要**切到 `datetime.now(timezone.utc)`
- SQLite 入库 `datetime.utcnow().isoformat()` → 文本(无时区后缀);出库 `datetime.fromisoformat(text)` 自动还原 naive datetime
- **不需要**任何 `.replace(tzinfo=None)` 兼容代码

**若 task-202 已迁移到 aware datetime**(本文档作者实地核查时为 naive,但若实施时已变更):停手抛冲突给 PM。

### 风险 3 — Project JSON 序列化精度

`Project.slx_models[i].blocks[j].parameters: dict[str, str]` 中字符串可能含特殊字符(中文 block 名 / 引号 / 换行)。

**约定**:`json.dumps(ensure_ascii=False)`(可读性优先,SQLite TEXT 字段全 UTF-8)。**`json.loads` 不需要额外参数**。

### 风险 4 — schema 升级路径与版本不匹配处理(GPT 一审 P1-4)

本 Task `schema_version` 表是**单行预留**(`id=1` 唯一)+ 显式版本校验逻辑(§ 9.6 init_schema)。

**升级路径**(后续 Task 责任):

- v1 → v2(TASK-302 加 chat_message.embedding BLOB):`ALTER TABLE chat_message ADD COLUMN embedding BLOB`,同步 bump `CURRENT_SCHEMA_VERSION=2`
- v2 → v3(TASK-404 加 activation_codes 表):`CREATE TABLE`,bump 到 3

**版本不匹配场景**:本 Task `init_schema` 已抛 `StoreError`(unsupported / migration_required),lifespan 启动失败,uvicorn 退出。**不掩盖**。

若实施时 Codex 想加 `migrations/` 目录或 alembic 框架,**停手抛冲突**(D7 锁)。

### 风险 5 — FK ON DELETE CASCADE 双重删除语义(GPT 一审 P1-5 重写)

本 Task 启用 FK + ON DELETE CASCADE + `PRAGMA secure_delete=ON`。涉及两层删除语义,**PR 描述 + README 必须明示**:

**1. 逻辑删除语义(FK CASCADE)**:

- `ProjectStore.delete(project_id)` 在 SQLite 实现中触发 FK 级联,**自动删除** chat_session / chat_message
- 这与 InMemory 时代不同(InMemory 没有 FK,删 project 不动 chat)
- 符合**产品语义**:"项目被清理 → 其下所有对话也清理"(对齐 task-202 CleanupWorker + 01 § 9 24h TTL)
- 测试覆盖:`tests/adapters/storage/test_sqlite_project_store.py` 必须断言 `delete(project_id)` 后 `chat_store.list_recent_sessions(project_id)` 返回 `[]`,且对应 message 取不到

**2. 物理删除语义(secure_delete)**:

- `PRAGMA secure_delete=ON`(§ 9.5):SQLite 删除 row 后**覆盖 freelist 页面**,降低数据库文件中残留工程内容片段的隐私风险
- 对齐 01 § 9 line 338 "24 小时后自动删除,不长期保存"
- 性能代价:写操作 ~ 10-30% slowdown,MCS QPS < 1 可忽略

### 风险 6 — aiosqlite 与 pytest-asyncio 配合(D11)

`tests/adapters/storage/test_*.py` 用 `tmp_path / "test.db"` 文件 DB(GPT 一审 P1-1 锁定,**不用** `:memory:`)。

**fixture 结构**(`tests/adapters/storage/conftest.py`):

- `@pytest_asyncio.fixture` 产 store,`tmp_path` per-test 隔离
- 每个测试用例独立 db 文件(pytest tmp_path 自动清理)
- 跨方法共享同一 db 文件(因为 store 方法是"每方法开+关 connection",共享靠文件)

### 风险 7 — InMemoryProjectStore 保留为测试 fake 的语义清晰度(D6)

**规避**:

- 顶部 docstring 三行警示("仅测试用,生产 lifespan 不再装配")
- `adapters/storage/__init__.py` **不导出**(`from adapters.storage import SqliteProjectStore` 是唯一推荐路径)
- `README.md` 显式说明
- `lifespan` 装配代码注释引用 D6

### 风险 8 — 多 worker 解锁信号的实际含义

task-202 D5 单 worker 硬约束在本 Task 完成后"技术可放开",但**本 Task 不实际启动 worker > 1**。实际放开是 TASK-405 部署 Task 的事;本 Task 仅验证 SqliteProjectStore + WAL 模式下并发可行(测试覆盖)。

PR 描述明示:"本 Task 不修改 uvicorn 启动参数,仅提供持久化基础以支持未来 worker > 1。实际放开 by TASK-405"。

### 风险 9 — 决策 09 反例 1 复现(CI 不装 runtime dep)

本 Task 加 `aiosqlite==0.20.0` 到 `requirements.txt`。**风险**:CI workflow 若仍只 `pip install -r requirements-dev.txt` 且 dev 不传递引用 runtime,CI 会 `ModuleNotFoundError`。

**Codex 实施 Stage 0 必跑**(已在 § 输入 Stage 0 清单):

```bash
cat .github/workflows/ci.yml | grep -A 2 "pip install"
grep -n "^-r requirements.txt" requirements-dev.txt
```

任一不符停手抛冲突。反例 1 教训(task-108 已踩,理应已修),但本 Task 加新 runtime dep 仍是关键节点。

### 风险 10 — `MFile.raw_code` redaction 对未来"原代码查看"功能的影响(D15 延伸)

**已知影响**(决策 09 纪律 5 跨文档同步核查):

- task-105 `analyze_dependencies` 在 ingest pipeline 内消费 `raw_code`(内存,在 mark_ready 之前),**不**通过 store 取回 → **不受影响**
- task-107 `ProjectGraphBuilder` 明示"不重新扫 raw_code,直接消费 task-105 产物" → **不受影响**
- task-203 `ProjectOverviewService` grep `raw_code` 空,只用结构化字段(SlxModel.blocks / MFunction.line_range)→ **不受影响**
- task-103 line 334 注释 "用户后续可能要看原代码做对照" → **本 Task 之后,从 24h 临时目录读 OR Phase 2 独立功能;不通过 store**

**未来扩展路径**(不在本 Task 范围):

- 选项 A:Phase 2 单独建"原代码查看"API,从 24h 临时目录 `./data/uploads/{project_id}/` 读
- 选项 B:Phase 2 数据隐私二审,审查"是否允许 raw_code 入 DB"
- 选项 C:redaction 后此功能永久不实现(用户上传 24h 后原代码彻底没了)

本 Task 实施时**不为未来功能预留 raw_code 入库后门**;PR 描述明示 D15 redaction 是隐私硬约束。

---

## 决策日志(D1-D15)

> 每个 D 决策追溯到具体宪法 / 决策 / Task 锚点;GPT 一审反馈在对应 D 下标注 P0 / P1。

### D1 — 异步驱动选 aiosqlite,不用 sqlite3 + asyncio.to_thread

**理由**:02 § 8 line 705 明文锁定 `数据库:SQLite + aiosqlite(异步驱动)`,这是宪法约束。04 § 6 line 266 已列 `aiosqlite==0.20.0` 在 requirements.txt 模板。

**子注解(与决策 11 § 决策 1 关系)**:决策 11 要求 async 内同步重活必须 `asyncio.to_thread` 桥接。**aiosqlite 是原生 async 驱动**,内部已用线程池跑 SQLite C 调用,**不需要再 to_thread**。本 Task 任何 `async def` store 方法直接 `await conn.execute(...)`,符合决策 11 精神。

**禁止**:Codex 实施时若有任何"想用 sqlite3 + to_thread 替代 aiosqlite"的冲动 → **停手抛冲突**。

### D2 — `db_path` 字段已在 AppSettings,不新增配置字段

task-108 line 175 已建 `db_path: str = "./data/mxa.db"`;.env.example / task-201/202 lifespan 已 log。本 Task 复用,**零配置增量**。

**不引入**:`db_pool_size` / `db_wal_checkpoint_interval` / `db_busy_timeout_ms` 等(Phase 2 视压测决定;MCS 阶段全部用代码常量,如 busy_timeout=5000)。

### D3 — ChatMessage / ChatSession 字段最小集

为 TASK-205 提供刚好够用的字段,不预测未来需求。

- `ChatMessage` 6 字段:`message_id` / `session_id` / `role` / `content` / `created_at` / `citations_json`
- `ChatSession` 5 字段:`session_id` / `project_id` / `created_at` / `updated_at` / `title`

**不加**:`tokens_in` / `tokens_out` / `latency_ms` / `model` / `temperature`(LLM 元数据走 logger metadata-only,符合 01 § 9 + 决策 11)。

**citations_json 用字符串**:避免 dataclass 跨边界传 `list[SourceRef]`;ChatService(TASK-205)负责序列化 / 反序列化。

### D4 — 单一 db 文件,Project + Chat 共库

MCS 阶段两表数据量小(< 千条记录),分库无收益;FK 跨库不支持(SQLite 限制)。`db_path = ./data/mxa.db` 单文件,全部表共存。

**未来分库阈值**:Phase 2 若 chat_message > 100k 行影响 project 查询性能,届时分库;MCS 不操心。

### D5 — ChatStore 5 方法接口(不照搬 ProjectStore 7 方法)

Chat 与 Project 生命周期不同:

- ProjectStore 7 方法是 `parsing → ready/failed` 三态生命周期 + TTL 清理
- ChatStore 5 方法是 session 创建 + message 追加 + 双向 list,**无三态**(对话天然 append-only)

**不加**:`mark_session_archived` / `delete_message` / `update_message`(MCS 不需要;聊天历史是不可变记录)。

### D6 — InMemoryProjectStore 保留为测试 fake

**理由**:

1. task-202 已实现 + 已测试,删除牵动 7 方法 unit test
2. 测试用 fake > mock(经典实践);测试速度快(纯内存),无文件 IO
3. 现有 `tests/api/conftest.py` autouse fixture 用 InMemory 替换 lifespan store,**不动 fixture = 零测试回归**

**收紧措施**:顶部 docstring 警示 + `__init__.py` 不导出 + README 明示。

**对立方案(拒)**:删除 InMemory,所有测试改用 SQLite tmp_path 文件。代价:跑 100+ 测试每个开 SQLite 连接 + init_schema,测试时长从 < 1s 涨到 ~ 5-10s,得不偿失。GPT 一审同意保留。

### D7 — Schema migration 用 `CREATE TABLE IF NOT EXISTS` + `schema_version` 单行表 + 版本校验,不引 alembic(GPT 一审 P1-4 增强)

**核心决策**:MCS 阶段单一开发者 + 单一服务器,schema 变更频率极低(本 Task 后预计 TASK-302 / 404 两次);引入 alembic 是过度抽象。

**实施约束(GPT 一审 P1-4 新增)**:

1. 模块常量 `CURRENT_SCHEMA_VERSION = 1`(`adapters/storage/schema.py` 顶层)
2. `init_schema` 末尾 `INSERT OR IGNORE INTO schema_version(id, version, applied_at) VALUES (1, CURRENT_SCHEMA_VERSION, datetime.utcnow().isoformat())`
3. `SELECT version FROM schema_version WHERE id=1`
4. `version > CURRENT_SCHEMA_VERSION` → 抛 `StoreError("unsupported_schema_version")`(DB 比代码新,可能是回滚 / 误升级)
5. `version < CURRENT_SCHEMA_VERSION` → 抛 `StoreError("schema_migration_required")`(本 Task 不做 migration;后续 TASK-302 / 404 各自实现 ALTER + bump)
6. `applied_at` 用 Python `datetime.utcnow().isoformat()`,**不用** SQLite `datetime('now')`(格式统一)

**升级路径**(各 Task 自管):

- v1 → v2(TASK-302 加 chat_message.embedding BLOB):`ALTER TABLE chat_message ADD COLUMN embedding BLOB` + `UPDATE schema_version SET version=2, applied_at=?`
- v2 → v3(TASK-404 加 activation_codes 表):`CREATE TABLE` + bump 到 3

### D8 — 连接管理:不池化 + `@asynccontextmanager` 形态 + 显式 commit(GPT 一审 P0-4 + P0-5 关键修订)

**理由**:MCS QPS < 1,WAL 模式下 connect 开销 < 5ms,Phase 2 视压测决定是否池化。

**关键修订(GPT 一审 P0-4)**:`open_connection` **必须** `@asynccontextmanager`,**禁止** `async def open_connection(db_path) -> aiosqlite.Connection`(返回 coroutine 不能 `async with`,v0.1 形态硬错);详见 § 9.5。

**关键修订(GPT 一审 P0-5)**:**所有写操作必须显式 `await conn.commit()`**(aiosqlite 默认 autocommit=False,不显式 commit 写入丢失)。下表是本 Task 所有需要 commit 的方法:

| 方法 | 操作 | commit 时机 |
|---|---|---|
| `init_schema`(schema.py) | `executescript(_DDL)` + `INSERT OR IGNORE schema_version` | 末尾 `await conn.commit()` |
| `SqliteProjectStore.create_pending` | `INSERT` | 单 INSERT 后 `await conn.commit()` |
| `SqliteProjectStore.mark_ready` | `UPDATE` | 单 UPDATE 后 `await conn.commit()` |
| `SqliteProjectStore.mark_failed` | `UPDATE` | 单 UPDATE 后 `await conn.commit()` |
| `SqliteProjectStore.delete` | `DELETE`(+ FK CASCADE) | 单 DELETE 后 `await conn.commit()` |
| `SqliteChatStore.create_session` | SELECT 预检查 + `INSERT` | 单 INSERT 后 `await conn.commit()` |
| `SqliteChatStore.append_message` | `BEGIN` + SELECT + `INSERT` + `UPDATE` + `COMMIT`(或 `ROLLBACK`) | 显式事务,异常路径必 `rollback` |
| `get_*` / `list_*`(所有读) | `SELECT` | 纯读,**无 commit** |

**禁止**:`self._conn = await open_connection(...)` 持久化在 store 实例(状态泄漏)。**强制**:所有方法 `async with open_connection(self._db_path) as conn: ...`。

### D9 — lifespan startup 显式 `init_schema`,不靠 lazy 建表

lazy 建表(首次 INSERT 触发 CREATE)在多 worker 下有 race condition;显式 startup 单次建表是 MCS / Phase 2 都安全的模式。

**实现位置**:`api/main.py` lifespan 内 `_bootstrap_db(db_path)` async context manager(§ 9.7)。失败抛出后 uvicorn 退出。

### D10 — 多 worker 解锁信号,不实际启动 worker > 1

本 Task 完成后**技术允许** uvicorn `--workers > 1`,但实际启动参数由 TASK-405 部署 Task 决定。本 Task 范围严格限定在持久化层。

**测试覆盖**:`tests/api/test_lifespan_with_sqlite.py` 不测多进程并发(那是 TASK-405 压测范围);只测 lifespan 单进程下 SQLite store 工作正常(GPT 一审 Q4 缩窄)。

### D11 — store 单元测试 + 集成测试统一 `tmp_path` 文件 DB,**不用** `:memory:`(GPT 一审 P1-1 完整重写)

**理由**(收口 v0.1 的犹豫):

- 本 Task D8 强制每方法 `open_connection` + 关闭
- `:memory:` 在 aiosqlite 中**每次 connect 都是独立库**,与 D8 天然冲突 — 测试时 store 方法 A 的写在方法 B 的读取里看不见
- 引入 conn_factory 注入或共享 connection 是给"测试可见性"反向修改生产代码,污染设计
- tmp_path 文件 DB 简单稳定,pytest 自动隔离 + 自动清理

**fixture 模式**(`tests/adapters/storage/conftest.py`):

```python
import pytest_asyncio
from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_project_store import SqliteProjectStore


@pytest_asyncio.fixture
async def project_store(tmp_path):
    db_path = str(tmp_path / "test.db")
    async with open_connection(db_path) as conn:
        await init_schema(conn)
    return SqliteProjectStore(db_path)
```

**SqliteChatStore fixture** 同模式。

**统一禁用 `:memory:`**:验收 § 15 + § Checklist Codex Stage 0 全文 grep `':memory:'` 应空。

### D12 — 新增 2 异常类,锁定方案 1(GPT 一审 P0-2 + P0-3)

**异常树最终形态**(决策 09 纪律 4 数值核查:**13 个**异常类,既有 11 + 新增 2):

```
MxaError
├── ProjectError
│   ├── ProjectNotFoundError       (TASK-101)
│   └── ChatSessionNotFoundError   (本 Task 新增)
├── UploadError + 4 子类           (TASK-101)
├── ParseError + 2 子类            (TASK-101)
├── LLMError + 5 子类              (TASK-101)
├── QuotaExhaustedError            (TASK-101)
├── EvidenceMissingError           (TASK-101)
└── StoreError                     (本 Task 新增,平行)
```

**方案 1 vs 方案 2 取舍**:

- ✅ **方案 1(采纳)**:`ChatSessionNotFoundError(ProjectError)` — chat 是 project 子资源,"某 project 下的 session 不存在"归 `ProjectError` 足够;少一层抽象;TASK-201 ERROR_MAP `ProjectError` fallback 已覆盖,新 leaf 不变成未捕获(GPT 一审 P0-3 推荐)
- ❌ **方案 2(拒)**:新建 `ChatError` 父类 — MCS 无独立 chat 错误体系,新增中间层让 ERROR_MAP / 测试 / 文档多一层无收益

**异常类签名(GPT 一审 P0-2 修)**:

```python
class ChatSessionNotFoundError(ProjectError):
    """指定对话会话不存在。"""


class StoreError(MxaError):
    """持久化存储层异常(SQLite OperationalError / JSON decode / schema 版本不匹配等)。"""
```

**`StoreError` 构造仅接受 message 字符串**:

- ✅ `raise StoreError("sqlite_operation_failed")`
- ❌ `raise StoreError(error_code="sqlite_operation_failed")` — v0.1 错(`StoreError.__init__` 不接受 keyword,task-101 异常树未定义自定义 `__init__`,GPT 一审 P0-2 抓)
- ❌ `raise StoreError("...", details=...)` — 同上

**HTTP 映射延后**:TASK-201 ERROR_MAP 本 Task 不动;TASK-205 / TASK-206 决定 leaf handler(详见 § 9.2 末尾)。

### D13 — async / 日志规范严格遵循决策 11 + commit() 落实(GPT 一审 P0-5)

**本 Task 落实点**:

1. **所有 store 方法 `async def`**,直接 `await conn.execute(...)`(aiosqlite 原生 async,不需要 to_thread)
2. **所有写操作显式 `await conn.commit()`**(D8 表)
3. **业务异常分支 logger metadata-only**(决策 11 § 决策 2):

```python
try:
    async with open_connection(self._db_path) as conn:
        await conn.execute("UPDATE ... SET status='ready' WHERE project_id=?", (project_id,))
        await conn.commit()                                     # D8 显式 commit
except aiosqlite.OperationalError as exc:
    logger.error(
        "SqliteProjectStore.mark_ready failed: project_id={} exception={}",
        project_id,
        type(exc).__name__,                                     # 类名,不是 str(exc)
    )
    raise StoreError("sqlite_operation_failed") from None       # D12:单 message 参数
```

**禁用**:`logger.exception(...)` / `logger.error(f"... {exc}")` / `logger.error("...", exc_info=True)` / 任何含 `args` / `message` / 异常自身的 f-string(决策 11 全部禁项)。

### D14 — Project 序列化用 `dataclasses.asdict` + json,不引 pydantic;**显式处理 raw_code / Enum / datetime / tuple**(GPT 一审 P1-3 完整重写)

**核心原则**:domain 层(task-101 § 通用约束第 1 条)不依赖 pydantic;只 `app/config.py` 用。

**实现要点(GPT 一审 P1-3 修)**:

1. **raw_code redaction**(D15 关联):`asdict` 后**显式**置每个 `m_files[i]["raw_code"] = ""`,**不**入库工程原文
2. **Enum 显式 `.value`**:`data["project_type"] = project.project_type.value`(不能依赖 `json.dumps(default=str)` — `str(ProjectType.GENERAL)` = `"ProjectType.GENERAL"`,**不是** `"general"`,GPT 一审 P1-3 抓)
3. **datetime 显式 `.isoformat()`**:`data["created_at"] = project.created_at.isoformat()`(不依赖 `default=str`,格式不可控)
4. **`json.dumps(ensure_ascii=False)`**:中文 block 名 / 注释入库可读(风险 3)
5. **反序列化 tuple 字段显式还原**:`SlxBlock.position = tuple(d["position"])` / `MFunction.line_range = tuple(d["line_range"])`(JSON 不区分 list / tuple,asdict 出 list,不还原 dataclass 字段类型漂)
6. **反序列化 Enum 显式构造**:`ProjectType(d["project_type"])`(用 `.value` 构造,不能 `ProjectType[d["project_type"]]`)
7. **反序列化 datetime 显式**:`datetime.fromisoformat(d["created_at"])` → naive datetime
8. **嵌套 dataclass 逐层构造**:`_slx_model_from_dict` / `_slx_block_from_dict` / `_m_file_from_dict` / `_m_function_from_dict` / `_mat_metadata_from_dict` / `_mat_variable_from_dict`(详见 § 9.3 代码模板)

**文件拆分**:辅助函数若使 `sqlite_project_store.py` 接近 300 行(04 § 4 硬规定),拆 `adapters/storage/_project_json.py`;否则可内联。GPT 一审 P1-3 注:**不要为压行数硬塞**。

**未来扩展**:Phase 2 若 Project 字段大量增加,考虑 `pydantic.dataclasses` + `.model_dump_json` 替代。MCS 不做。

### D15 — Project 持久化前 redaction `MFile.raw_code`,对齐 01 § 9 数据隐私(GPT 一审 P0-1 新增)

**触发原因**:GPT 一审 P0-1 抓出 v0.1 D14"完整 Project JSON 入库"与宪法 § 9 line 339 硬约束冲突:

> 01 § 9 line 339:"数据库**不存储**工程原始内容,**只存元数据**(用户 ID、工程哈希、问答记录、token 消耗)"

而 task-101 `MFile.raw_code: str`(task-103 line 334 明文 "未经预处理的原始字符串"),是用户上传 `.m` 文件原文。完整 `dataclasses.asdict(project)` 后 `json.dumps` 入库 = **DB 存储工程原始代码**,**直接违反 § 9 硬约束**。

**决策**:采 GPT 一审推荐**方案 A — 序列化前显式 redaction**:

```python
def _project_to_json(project: Project) -> str:
    data = asdict(project)
    # ... enum / datetime 处理 ...
    for m_file in data["m_files"]:
        m_file["raw_code"] = ""                                  # D15
    return json.dumps(data, ensure_ascii=False)
```

**为什么不升二审**:

- GPT 一审给出方案 A 即可在 MCS 阶段保持 § 9 合规,不需要重新设计数据流
- 反序列化后 `Project.m_files[i].raw_code = ""`,**对下游零破坏**(实地核查):
  - task-105 在 ingest pipeline 内消费 raw_code(内存,mark_ready 之前)→ **不**通过 store 取回
  - task-107 明示"不重新扫 raw_code,直接消费 task-105 产物"
  - task-203 grep `raw_code` 空,只用 SlxModel / MFunction 结构化字段
- 若 PM 决定保留 raw_code 入库("未来需要原代码查看功能"),那触发数据隐私 AI 二审(01 § 9 / 04 数据安全章节),不属本 Task

**对未来"原代码查看"功能的影响**:见风险 10。

**测试覆盖**:`tests/adapters/storage/test_sqlite_project_store.py` 必须含一个测试 `test_mark_ready_redacts_raw_code`:构造一个 `Project` 含非空 `raw_code`,mark_ready 后用 sqlite3 直读 JSON,断言 `m_files[*].raw_code == ""`。验收 § 10 是这个测试的 PM 端兜底命令。

**禁止**:

- ❌ 任何"为方便调试,临时关闭 redaction"的开关 / 环境变量(隐私不能用 feature flag 绕)
- ❌ 在 store 出库后"恢复"raw_code(数据已不在,不可恢复;调用方应从 24h 临时目录读)

---

## Checklist(精简)

### Codex 实施前 Stage 0 必跑

- [ ] 跑 § 输入"必须存在的文件 / 状态"8 条 grep,任一不符停手抛冲突
- [ ] 风险 9 CI workflow 核查(`pip install` 是否装 runtime + dev 是否 `-r requirements.txt`)
- [ ] 读完 § 决策日志 D1-D15,理解每个决策的不变量,**特别注意 D14 / D15(raw_code redaction)**
- [ ] 读完决策 09 / 11 全文 + 宪法 § 9(数据隐私)+ task-103 § raw_code 字段语义

### Codex 实施中分 Stage 验证

- [ ] **Stage 1 完成**:`pytest tests/core/test_domain_chat.py tests/core/test_interfaces_chat_store.py tests/core/test_domain_exceptions_v204.py -v` 全绿
- [ ] **Stage 2 完成**:`pytest tests/adapters/storage/test_schema.py tests/adapters/storage/test_sqlite_project_store.py -v` 全绿;**特别确认** `test_mark_ready_redacts_raw_code` 用 sqlite3 直读 JSON 验证 `m_files[*].raw_code == ""`
- [ ] **Stage 3 完成**:`pytest tests/adapters/storage/test_sqlite_chat_store.py -v` 全绿
- [ ] **Stage 4 完成**:`pytest tests/api/test_lifespan_with_sqlite.py -v` 全绿(**不打 LLM**,GPT 一审 Q4);`pytest tests/ -v` 全套全绿(无回归)
- [ ] **Stage 5 完成**:`make check` 全绿 + 03 索引状态更新(🔍 不是 ✅)

### PR 描述必含

- [ ] § 输入"必须存在的文件 / 状态"8 条 grep 实际输出(明示符合)
- [ ] § 验收 1-15 项逐条勾选 + 简述
- [ ] § 验收 9 真启动验证为 PM 本地体验,**不阻塞合并**
- [ ] 列出 D1-D15 决策点的实施确认("按 D1 选 aiosqlite,按 D6 保留 InMemory,按 D8 显式 commit,按 D12 异常方案 1,按 D14 显式 enum/datetime/tuple,按 D15 raw_code redaction,...")
- [ ] 明示新增 2 个异常类(`ChatSessionNotFoundError` + `StoreError`),`ERROR_MAP` 不修改(由 TASK-205 / 206 接管)
- [ ] 明示 D15 raw_code redaction 实施细节 + 测试覆盖
- [ ] 明示 FK CASCADE 是相对 InMemory 的行为变化(风险 5)
- [ ] commit subject 单行无 body(反例 17 / PM 偏好)
- [ ] PR 标题 + 分支名按 § 验收 16

### PM 验收侧 Step B 命令(决策 08 第 2 条 + 决策 09 纪律 7)

- [ ] `git status` clean + `git log --oneline main..HEAD` 看 commit 拆分合理
- [ ] `make check` 本地全绿
- [ ] 决策 11 兜底 2 条 grep(见 § 验收 7)
- [ ] **对齐 CI 实际步骤**(决策 09 纪律 6 / 7):`cat .github/workflows/ci.yml` 看 `run:` 步骤,逐条对齐本地是否覆盖
- [ ] `wc -l` 看 7 个新文件每个 ≤ 300
- [ ] `git diff origin/main..HEAD -- core/domain/exceptions.py` 仅新增 2 类(GPT 一审 P0-2 验收 14)
- [ ] `grep -B 1 "async def open_connection" adapters/storage/_connection.py` 必带 `@asynccontextmanager`(GPT 一审 P0-4 验收 13)
- [ ] `grep -rn 'import sqlite3\|from sqlite3' adapters/storage/` 应空(GPT 一审 P0-4 验收 7)
- [ ] 跑 § 验收 10(raw_code redaction Python 脚本,GPT 一审 P0-1 兜底)

---

## 后续 Task 接力点

### TASK-205(粗 RAG 问答 ⭐)消费本 Task

- 装配:`ChatService(text_provider, project_store, chat_store, ...)`,从 lifespan `app.state.chat_store` 注入
- 流程:`POST /projects/{project_id}/chat` → `chat_store.create_session()`(若新会话)→ `chat_store.append_message(user_msg)` → RAG 检索 → LLM → `chat_store.append_message(assistant_msg, citations_json)` → 返回
- 异常处理(GPT 一审 P0-3 锁定):`ChatSessionNotFoundError → HTTP 404` / `StoreError → HTTP 500`,**在 TASK-205 自身追加 ERROR_MAP handler**,**route 层禁止 try/except**;或 PM 选择把 TASK-206 部分前置(在 TASK-205 启动前完成 ERROR_MAP 扩展)
- **不**消费 `Project.m_files[*].raw_code`(D15 已 redaction 为空字符串);需要原代码做 RAG chunk 时,从 24h 临时目录 `./data/uploads/{project_id}/` 读 OR Phase 2 隐私评审

### TASK-302(SQLite 向量存储 + 检索)扩展本 Task schema(GPT 一审 Q1 修正)

- `ALTER TABLE chat_message ADD COLUMN embedding BLOB`
- 同步 `bump CURRENT_SCHEMA_VERSION = 2` + `UPDATE schema_version SET version=2, applied_at=?`
- **不动** ChatMessage dataclass(embedding 仅落库,Python 侧由 EmbeddingProvider 负责);或扩展为 6 → 7 字段(TASK-302 决定)
- 本 Task `init_schema` 版本校验在 v=2 时会抛 `schema_migration_required`,TASK-302 必须先实现 v1 → v2 migration 脚本

### TASK-304(向量 RAG 整合到 ChatService)消费 TASK-302 的 schema 扩展

- 注:v0.1 误把"扩展 schema"写在 TASK-304,实际是 TASK-302 的工作。TASK-304 是 ChatService 层消费,**不动 schema**(GPT 一审 Q1 修正)

### TASK-404(激活码)新建表

- `CREATE TABLE activation_codes (...)`(独立设计,不依赖 chat / project)
- 升 `CURRENT_SCHEMA_VERSION = 3`

### TASK-405(部署)放开多 worker

- uvicorn `--workers > 1` 启动参数(由 deploy script 或 systemd 服务设置)
- WAL 模式 + busy_timeout 5000ms 已足够处理多 worker 并发(本 Task 已配置)
- 压测目标:50 QPS 上传 + 100 QPS 问答(by TASK-405 决定)

---

**版本**:v0.2(GPT 一审条件通过,应用所有 P0 / P1 / 文档修订)
**日期**:2026-06-04
**作者**:Claude(架构师,第十二任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`(本文档引用其他 Task 文档路径,不内联全文)
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`(03 索引更新由 Codex 必选并发完成)
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(PM 字节级 Python 改文档)
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(架构师纪律,本文档 Stage 0 实地核查 + 风险 10 跨文档同步)
- `docs/decisions/20260604-11-async-blocking-and-logger-exception-bans.md`(决策 11,本文档 D1 / D13 关键引用)
**触发 Task**:本 Task 是 TASK-202 临时 InMemoryProjectStore 的正式接管;同时首次定型 ChatStore 接口,为 TASK-205 粗 RAG 铺路
**GPT 一审反馈处理**:P0-1(D15 + § 9.3 + 风险 5/10 + 验收 10)/ P0-2(§ 输出 + D12 + D13)/ P0-3(§ 9.2 末尾 + 接力点)/ P0-4(§ 9.5 重写)/ P0-5(D8 commit 表 + § 9.3/9.4/9.6)/ P1-1(D11 重写)/ P1-2(§ 9.4 SELECT 预检查 + 事务)/ P1-3(D14 重写)/ P1-4(D7 + § 9.6)/ P1-5(风险 5 + § 9.5 secure_delete)/ Q1(TASK-302 vs 304)/ Q2(03 索引 🔍)/ Q3(测试路径子目录)/ Q4(Stage 4 不打 LLM)/ 验收新增 6 条
