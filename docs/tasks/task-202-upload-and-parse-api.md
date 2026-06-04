# TASK-202: 上传 + 解析 API(异步,含沙箱)

## 状态

🔲 未开始

---

## 上下文

这是 Week 2 的第二个 Task,**项目第一个有用户可见 HTTP 业务端点的 Task**,把"上传 .zip → 沙箱解压 → 文件分类 → .m/.slx 解析 → 文件依赖分析 → 工程落地"全链路打通,通过 FastAPI BackgroundTasks 异步执行。

为什么必须做:

- 03 § Week 2 第二行明文要求,所有后续 Task(TASK-203 导览 / TASK-204 SQLite 替换 store / TASK-205 粗 RAG / TASK-206 错误处理扩展 / TASK-207 ProjectOverview Schema)全部阻塞在本 Task 产出的 `project_id` 与 ProjectStore 接口上
- 本 Task 是项目首次定型**异步 + 长任务 + 攻击面**复合形态。错误一次,后续 5 个 Task 抄错;正确一次,后续 5 个 Task 抄对
- 04 § 临时目录策略要求"每次上传一个 UUID 临时目录,异常也要清理,TTL 24 小时定时任务清理"——本 Task 落实

### 审批级别:走 GPT 二审(已完成)

**反例 18 自检**(决策 09 第 18 条警钟):

| 评估维度 | 本 Task 评分 |
|---|---|
| 决策密度 | **高**:本 Task 共 **D1-D16** 共 16 个决策点(详见 § 10) |
| 下游扩散面 | **5 个 Task** 直接消费:TASK-203 / 204 / 205 / 206 / 207 全部依赖 `ProjectStore` 接口 + `project_id` 语义 + `ProjectStatus` 三态 |
| 用户/安全可见性 | **首个用户面端点**,攻击面 Task(multipart / zip / 临时文件),错误直接暴露给前端 |
| 异步首次定型 | **首次**项目级 BackgroundTasks + `asyncio.to_thread` 复合用例,行为蓝本被 TASK-203 / 205 抄走 |

**结论:走 GPT 二审**(已完成,二审 10 条全部吸收;本文档为 v0.2 终稿)。

### 主要责任

- **HTTP 层**:`POST /upload`(multipart/form-data,HTTP 202 Accepted)+ `GET /projects/{project_id}/status`(轮询查询)
- **同步路径**:declared size 第一道防线(不读 body) → read bytes → actual size 第二道兜底 → 生成 `project_id` + store 落 parsing 记录(`create_upload_record`,内含 UUID 冲突 3 次重试) → 注册 BackgroundTask → **立即返回 202**
- **异步路径**(BackgroundTask 内):创建项目目录 → `asyncio.to_thread` 桥接同步重活(extract → classify → parse → dep_analyze → 构造 Project) → store mark_ready;**任何业务异常** → store mark_failed(error_code)+ metadata 日志
- **CleanupWorker**(lifespan 内常驻 asyncio.Task):定时扫描 `upload_dir`,删除超 `upload_ttl_hours` 的项目目录 + 同步删 store entry
- **InMemoryProjectStore**:TASK-204 SQLite store 前的临时桥接,**仅本进程可见**

### 范围边界(硬约束,必读)

**本 Task 不修改**(零增量原则):
- `app/config.py::AppSettings` — 配置零增量,清理 TTL 复用已有 `upload_ttl_hours`,扫描周期 `interval_minutes` 走 `CleanupWorker(interval_minutes=60)` 构造默认值
- `core/domain/project.py::Project` dataclass — v0.1 9 字段冻结(跨 Task 共享契约),`status` 不进 Project,而是放独立 `ProjectStatusRecord`
- `core/domain/exceptions.py` — 不新增异常类,严格用 TASK-101 / 104 已建的 8 个异常 leaf
- `adapters/parser/mat_reader.py` — **不存在不要顺手建**(D7,详见 § 10);本 Task `Project.mat_files=[]` 占位

**本 Task 临时前移**(TASK-204 边界,详见 § 10 D4):
- `core/interfaces/project_store.py::ProjectStore` 接口(7 方法)
- `adapters/storage/in_memory_project_store.py::InMemoryProjectStore` 实现
- TASK-204 后续接管:补 `SqliteProjectStore`(同接口)+ 数据迁移工具 + `ChatStore`

**本 Task 单 worker 硬约束**(详见 § 10 D5):
- `InMemoryProjectStore` 是进程内 dict + asyncio.Lock,**不跨进程**
- CleanupWorker 是 lifespan 内常驻 asyncio.Task,多 worker 下每个 worker 都会启动
- uvicorn 启动命令 **禁用 `--workers > 1`**;真启动验收只跑单 worker
- TASK-204 持久化后即可放开多 worker 限制

**本 Task 刻意收窄 04 § 8.4 失败隔离原则**(详见 § 10 D14):
- 任何 `ParseError`(单个 .m / .slx 解析失败)→ 整个 project 标记 failed
- 不实现 partial project / `ready_with_warnings` 第四态
- 解锁路径:TASK-203 导览生成时,基于 `unresolved_symbols`(TASK-107 ProjectGraph 已建)做容错展示

### 下游消费者

- **TASK-203**(导览生成):从 `ProjectStore` 取 `Project` 调 LLM 生成导览
- **TASK-204**(SQLite 存储层):**替换** `InMemoryProjectStore`,共享 `ProjectStore` 接口
- **TASK-205**(粗 RAG 问答):同 203,基于 `Project` 做关键词检索 + LLM
- **TASK-206**(错误处理扩展):在 TASK-201 ERROR_MAP 末尾追加 9 项 handler(LLMError 5 + ParseError 2 + Quota + Evidence)
- **TASK-207**(ProjectOverview Schema):基于 `Project` 做 schema 定型

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001 / 002(项目骨架 + CI,已合并)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并):**直接契约依赖**,本 Task 消费 `Project` / `FileInfo` / `ProjectType` / `MxaError` / `UploadError` / `ProjectError` / `ParseError` 子类树
- ✅ TASK-102(.slx 解析器,已合并 commit `2317bb6`):本 Task 调 `SlxParserImpl().parse(path)` → `SlxModel`
- ✅ TASK-103(.m 解析器,已合并 commit `0714ff7`):本 Task 调 `MParserImpl().parse(path)` → `MFile`
- ✅ TASK-104(zip 沙箱 + 文件分类,已合并 commit `d6b05fb`):**核心依赖**,本 Task 消费 `safe_extract` + `classify_files`
- ✅ TASK-105(文件依赖分析,已合并 commit `f63e999`):本 Task 调 `analyze_dependencies(file_infos, m_files, project_root)`
- ✅ TASK-106(DeepSeek TextProvider,已合并 commit `b1eb647`):本 Task **不直接使用**(无 LLM 调用),但 lifespan 需理解 `DEEPSEEK_API_KEY` 环境变量已被 AppSettings 加载
- ✅ TASK-107(ProjectGraph 构建器,已合并 commit `e7d2e22`):**本 Task 不消费**(导览归 TASK-203),仅保留 `Project` 构造接口
- ✅ TASK-108(AppSettings,已合并 commit `4ca7a10`):**直接依赖**,本 Task 消费 9 个字段
- ✅ TASK-201(FastAPI 框架 + ERROR_MAP,已合并 commit `fa7a4b0`):**直接依赖**,本 Task 消费 8-handler ERROR_MAP + `api.dependencies.get_settings` + `api.main.lifespan` + `api/schemas/` + `api/routes/` 子模块组织 + `tests/api/conftest.py` autouse fixture

### 必须存在的文件 / 状态(已经过 Codex dump 实地核查)

**`adapters/parser/zip_extractor.safe_extract` 实际签名锁**:
```python
def safe_extract(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> Path:
    """安全解压 zip 到 dest_dir,失败时抛 UploadError / ProjectError 子类。"""
```
- 参数 1:`zip_bytes: bytes`(**强制内存载入**;改流式需跨 Task 修改契约,违反宪法 § 5)
- 参数 2:`dest_dir: Path`(**必须已存在 + 在 `upload_dir` 子树内**,本 Task 上传服务负责 mkdir)
- 参数 3:`config: AppSettings`(全配置注入)
- 返回:`Path`(resolved 解压根目录)
- 异常:`ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError` / `ProjectTooLargeError`(**TASK-201 ERROR_MAP 全部命中**)

**`adapters/parser/file_classifier.classify_files` 实际签名锁**:
```python
def classify_files(extracted_root: Path, project_root: Path) -> list[FileInfo]:
```
- 两个 Path 参数,本 Task 都传 `safe_extract` 返回的 resolved 目录
- 返回 `list[FileInfo]`,按 `relative_path` 排序
- 异常:`ZipSlipError` / `FileTypeNotAllowedError`

**`adapters/parser/dependency_analyzer.analyze_dependencies` 实际签名锁**:
```python
def analyze_dependencies(
    file_infos: Iterable[FileInfo],
    m_files: Iterable[MFile],
    project_root: str | None = None,
) -> dict[str, list[str]]:
```
- 返回 POSIX relpath → 排序去重的目标 relpath 列表
- 不抛业务异常(纯结构化转换)

**`core/interfaces/parser.py` ABC 锁**:
```python
class SlxParser(ABC):
    def parse(self, slx_file_path: str) -> SlxModel: ...
class MParser(ABC):
    def parse(self, m_file_path: str) -> MFile: ...
```
- 实现类抛 `SlxParseError` / `MParseError`(均为 `ParseError` 子类,本 Task D14 → 任何 ParseError 转 project failed)

**`core/domain/exceptions.py` 异常树锁**(本 Task 仅使用,不新增):
- `MxaError` → `UploadError` → {`ZipBombError`, `ZipSlipError`, `FileTypeNotAllowedError`}
- `MxaError` → `ProjectError` → {`ProjectNotFoundError`, `ProjectTooLargeError`}
- `MxaError` → `ParseError` → {`SlxParseError`, `MParseError`}

**`Project` dataclass 字段锁**(9 字段,v0.1 冻结):
```python
@dataclass
class Project:
    id: str
    name: str
    project_type: ProjectType        # Enum, 本 Task 全部填 ProjectType.GENERAL
    files: list[FileInfo]
    slx_models: list[SlxModel]
    m_files: list[MFile]
    mat_files: list[MatMetadata]     # 本 Task 全部填 []
    created_at: datetime             # 解析完成时间(见 D16 语义)
    file_dependencies: dict[str, list[str]]
```

**`AppSettings` 已有字段**(实地 dump,本 Task 仅消费):
- `upload_dir: str = "./data/uploads"`
- `upload_ttl_hours: int = 24`(**清理 TTL 复用此字段**,D8)
- `max_upload_size_mb: int = 50`
- `max_files_per_project: int = 200`
- `max_single_file_mb: int = 20`
- `max_total_uncompressed_mb: int = 200`
- `max_entries_per_project: int = 200`
- `max_extraction_seconds: int = 30`
- `max_compression_ratio: int = 100`

**`api/dependencies.py::get_settings()` 已建**(TASK-201):本 Task 在同文件追加 `get_project_store()` / `get_upload_service()`,不动 `get_settings()` 本身。

**`api/middleware/error_handler.py` 8-handler ERROR_MAP 已建**(TASK-201):
- `ZipBombError` → 400 / `zip_bomb`
- `ZipSlipError` → 400 / `zip_slip`
- `FileTypeNotAllowedError` → 400 / `file_type_not_allowed`
- `ProjectNotFoundError` → 404 / `project_not_found`
- `ProjectTooLargeError` → 413 / `project_too_large`(动态文案读 settings)
- `UploadError` / `ProjectError` / `MxaError`(3 个 fallback)

**`tests/api/conftest.py` autouse fixture 已建**(TASK-201):
- 自动 `monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")`
- 自动 `get_settings.cache_clear()` + `app.dependency_overrides.clear()`
- 本 Task 测试**不**手动 setenv / clear cache,直接复用

**`adapters/storage/__init__.py` + README placeholder 已存在**(TASK-001):本 Task 直接加文件,零冲突。

**`features/ingest/__init__.py` + README placeholder 已存在**(TASK-001):同上。

**`mat_reader.py` 不存在**(实地 dump 确认)。**本 Task 不开 MatReader**(D7)。

---

## 输出(交付物)

### 新增文件清单(14 个)

| 文件路径 | 估算行数 | 用途 |
|---|---|---|
| `core/domain/project_status.py` | ~60 | `ProjectStatus` Literal + `ProjectStatusErrorCode` Literal + `ProjectStatusRecord` dataclass |
| `core/interfaces/project_store.py` | ~90 | `ProjectStore` ABC(**7 方法**)+ `ProjectStatusView` |
| `adapters/storage/in_memory_project_store.py` | ~160 | 进程内 dict + asyncio.Lock 实现 |
| `features/ingest/upload_service.py` | ~230 | 同步 size 校验 + `create_upload_record` + async process(含 `asyncio.to_thread`) |
| `features/ingest/cleanup_worker.py` | ~130 | 常驻 asyncio.Task,扫描 + 删除 |
| `api/routes/upload.py` | ~140 | `POST /upload` + `GET /projects/{id}/status` |
| `api/schemas/upload.py` | ~90 | `UploadResponse` / `ProjectStatusResponse`(5 字段) |
| `tests/adapters/storage/__init__.py` | 0 | 空 |
| `tests/adapters/storage/test_in_memory_project_store.py` | ~190 | InMemoryStore 单测(覆盖 **7 方法**) |
| `tests/features/__init__.py` | 0 | 空 |
| `tests/features/ingest/__init__.py` | 0 | 空 |
| `tests/features/ingest/test_upload_service.py` | ~250 | UploadService 单测(含 to_thread / size 顺序 / sanitize) |
| `tests/features/ingest/test_cleanup_worker.py` | ~160 | CleanupWorker 单测 |
| `tests/api/test_upload.py` | ~270 | API 端到端 + 5+1 类对抗(A 组 5 异步 + B 组 1 同步) |

**总新增**:~1770 行(含测试)。所有文件 ≤ 300 行(04 § 4)。

### 修改文件清单(7 个)

| 文件路径 | 修改性质 | 估算 diff 行数 |
|---|---|---|
| `api/main.py` | lifespan 扩展 `AsyncExitStack` + store 装配 + cleanup task 启停 | ~50 |
| `api/dependencies.py` | 追加 `get_project_store()` + `get_upload_service()`(顶部完整 import,无 `# noqa`) | ~65 |
| `requirements.txt` | 追加 `python-multipart==0.0.17` | +1 |
| `api/README.md` | 新增 upload/status route + 单 worker 限制段 + 测试 vs 生产语义段 | ~35 |
| `features/ingest/README.md` | UploadService 职责描述 + asyncio.to_thread 桥接说明 | ~30 |
| `adapters/storage/README.md` | InMemoryProjectStore 临时实现 + 7 方法接口说明 | ~25 |
| `docs/03_TASK_INDEX.md` | TASK-202 状态行 + Week 2 进度条 | 字节级修改 |

### 不修改的文件(零增量原则,守住边界)

- `app/config.py`(配置零增量,D8)
- `core/domain/project.py`(v0.1 9 字段冻结)
- `core/domain/exceptions.py`(异常树锁)
- `core/domain/m_file.py` / `mat_metadata.py` / `slx_model.py` / `source_ref.py`(数据类锁)
- `core/interfaces/llm_provider.py` / `parser.py` / `embedder.py`(契约锁)
- `adapters/parser/*`(TASK-102 / 103 / 104 / 105 产物全部 read-only)
- `adapters/llm/*`(TASK-106 产物 read-only)
- `api/middleware/error_handler.py`(TASK-201 ERROR_MAP 锁;新 handler 归 TASK-206)
- `api/routes/health.py` / `api/schemas/health.py`(TASK-201 产物)
- `tests/api/conftest.py`(TASK-201 autouse fixture 直接复用)
- `pyproject.toml`(本 Task 不动 mypy / ruff / pytest 配置)
- `.github/workflows/ci.yml` / `Makefile`(本 Task 不动 CI 命令)
- `docs/01_PROJECT_CONSTITUTION.md` / `02_ARCHITECTURE_OVERVIEW.md` / `04_ENGINEERING_STANDARDS.md` / `05_EXPLANATION_STYLE_GUIDE.md`(决策 07 边界)

---

## 实施步骤(顺序,Commit 拆分建议)

### 步骤序列(30 步)

1. 建分支 `task-202-upload-parse-api`,从 main HEAD 切出
2. 追加 `python-multipart==0.0.17` 到 `requirements.txt`
3. 本地 `pip install -r requirements-dev.txt` 验证新依赖能装
4. 建 `core/domain/project_status.py`(对照 § 7.1)
5. 建 `core/interfaces/project_store.py`(对照 § 7.2,**7 方法**)
6. 建 `adapters/storage/in_memory_project_store.py`(对照 § 7.3)
7. 建 `tests/adapters/storage/__init__.py` 空文件
8. 建 `tests/adapters/storage/test_in_memory_project_store.py`(对照 § 7.10.1,**7 方法全覆盖**)
9. `pytest tests/adapters/storage/ -v` 单跑通过
10. 建 `features/ingest/upload_service.py`(对照 § 7.4,含 `asyncio.to_thread` + `_sanitize_filename`)
11. 建 `tests/features/__init__.py` 空
12. 建 `tests/features/ingest/__init__.py` 空
13. 建 `tests/features/ingest/test_upload_service.py`(对照 § 7.10.2)
14. `pytest tests/features/ingest/test_upload_service.py -v` 通过
15. 建 `features/ingest/cleanup_worker.py`(对照 § 7.5,metadata-only 日志)
16. 建 `tests/features/ingest/test_cleanup_worker.py`(对照 § 7.10.3)
17. `pytest tests/features/ingest/test_cleanup_worker.py -v` 通过
18. 建 `api/schemas/upload.py`(对照 § 7.7,**5 字段** + `ProjectStatusErrorCode`)
19. 建 `api/routes/upload.py`(对照 § 7.6,size 顺序 + sanitize + 真 DI)
20. 在 `api/dependencies.py` 追加 `get_project_store()` + `get_upload_service()`(对照 § 7.8,**完整 import 顶部**,无 `# noqa`)
21. 改 `api/main.py` 扩展 lifespan(对照 § 7.9)
22. 在 `api/main.py::create_app` 注册 `upload_router`
23. 建 `tests/api/test_upload.py`(对照 § 7.10.4 + § 7.11 A 组 + B 组)
24. `pytest tests/api/test_upload.py -v` 通过
25. `pytest -v --tb=short` 整套测试通过(已有 TASK-201 + Week 1 全部测试)
26. `make check` 通过(lint / format / mypy / test / hygiene 五件套)
27. `python -m ruff format --check .` 手动加跑(反例 11 教训:CI 锁版本可能与本地漂移)
28. `pip check` 验证依赖兼容
29. uvicorn 真启动 + curl 5+1 类场景验收(详见 § 8 验收 21-23)
30. 改 `docs/03_TASK_INDEX.md`(字节级 Python,**先 grep 实际字面**,反例 9)+ commit 拆分 + push + 三件套 + 提 PR

### Commit 拆分(Conventional Commits)

```
chore(deps): add python-multipart to runtime requirements for multipart upload
feat(domain): add ProjectStatus and ProjectStatusErrorCode literals plus record
feat(interfaces): add ProjectStore ABC with 7 lifecycle methods
feat(storage): add InMemoryProjectStore with asyncio Lock for single-worker MCS
feat(ingest): add UploadService with split size checks and to-thread parse bridge
feat(ingest): add CleanupWorker with TTL scan reusing upload_ttl_hours
feat(api): add UploadResponse and ProjectStatusResponse schemas with extra-forbid
feat(api): add POST /upload and GET /projects/id/status routes with strict ordering
feat(api): wire ProjectStore and UploadService through app state dependencies
feat(api): extend lifespan with AsyncExitStack for store and cleanup task
docs(api): document upload endpoints single-worker limit and testclient semantics
docs(ingest): document UploadService responsibility and to-thread bridge
docs(storage): document InMemoryProjectStore as TASK-204 temporary bridge
test(storage): add InMemoryProjectStore unit tests covering 7 methods
test(ingest): add UploadService unit tests with injected fakes
test(ingest): add CleanupWorker unit tests with monkeypatched time
test(api): add upload route tests covering five async plus one sync adversarial
docs: mark TASK-202 as in-review in task index
```

Commit subject **单行,无 body**(反例 17 教训;PM 偏好硬约束)。

---

## 不做(明确排除)

- ❌ **任何 LLM 调用**:本 Task 仅做上传 + 解析 + 落库,LLM 归 TASK-203 / 205
- ❌ **SQLite / 持久化 store**:`InMemoryProjectStore` 进程内 dict only;TASK-204 接管
- ❌ **ChatStore / 对话历史**:归 TASK-204
- ❌ **`.mat` 文件深度解析**:不开 `MatReader`(D7);本 Task `Project.mat_files=[]`
- ❌ **多 worker 支持**:单 worker only(D5)
- ❌ **流式上传**:`safe_extract(zip_bytes: bytes)` 强制内存载入;Phase 2
- ❌ **断点续传 / 分片上传**:Phase 2
- ❌ **并发上传限流**:MCS 无用户系统;Phase 2
- ❌ **`project_type` 自动分类**:`ProjectType.GENERAL` 占位
- ❌ **导览生成 / TeachingUnit 构建**:归 TASK-203
- ❌ **partial project / `ready_with_warnings` 第四态**(D14):本 Task `ProjectStatus` 三态;任何 parse error → 整个 project failed
- ❌ **修改 `app/config.py::AppSettings`**:配置零增量(D8)
- ❌ **修改 `core/domain/project.py::Project` dataclass**:v0.1 9 字段冻结(D1)
- ❌ **新增 `MxaError` / `UploadError` / `ProjectError` 子类**:严格用已建 8 leaf
- ❌ **在 `api/middleware/error_handler.py` 追加 handler**:归 TASK-206
- ❌ **新增 zip 安全矩阵测试**:TASK-104 已有完整低层矩阵
- ❌ **在 `features/ingest/upload_service.py` 内 import `adapters/`**:严格 02 § 7 分层(D12)
- ❌ **在 `api/routes/upload.py` 内 `try/except` 业务异常**:同步路径直接抛,统一走 TASK-201 ERROR_MAP
- ❌ **在 `UploadService.process` / `CleanupWorker` 内用 `logger.exception`**:`logger.exception` 等同于落 `str(exc)` + traceback,违反隐私硬约束;统一用 `logger.error(..., type(exc).__name__)` metadata-only
- ❌ **在 `UploadService.process` 内直接 await 同步重活**(D13):全部通过 `asyncio.to_thread(_run_parse_sync, ...)` 桥接,避免阻塞 event loop
- ❌ **在 lifespan 内做重活**:仅装配 store + 启动 cleanup task
- ❌ **日志记录上传内容 / 用户文件名片段 / 异常字符串**:文件内容 / 原始文件名 / API key / `str(exc)` / 用户问题原文 一律禁止
- ❌ **在 route 内 `Depends(lambda: None)` 占位**:全部用真 dependency

---

## 接口契约

### 7.1 `core/domain/project_status.py`

```python
"""上传流程的运行态状态记录。

本模块与 ``core/domain/project.py::Project`` 并列存在,而非把 ``status``
塞进 Project dataclass:Project v0.1 字段冻结(跨 Task 共享契约),且
``status`` 是 *上传流程* 的运行态,不是 *工程* 的属性。Project 实例只在
``status == "ready"`` 时存在(失败的项目没有 Project)。

``ready`` 仅表示 "上传 + 解压 + 解析 + 落库完成",**不**表示导览生成完成
(那是 TASK-203 范畴)/ TeachingUnit 构建完成(同上)/ 向量化完成
(TASK-301)。

时间字段语义(D16):
- ``ProjectStatusRecord.created_at`` = 上传接收时间(POST /upload 落 store 那一刻)
- ``Project.created_at``           = 解析完成时间(BackgroundTask 内构造
  Project 那一刻);早于 ``ProjectStatusRecord.updated_at`` 但晚于
  ``ProjectStatusRecord.created_at``
- 前端展示"上传时间"应读 ``ProjectStatusRecord.created_at``(GET /status
  暴露),不读 ``Project.created_at``

错误码语义(D8 + D14 配套):
- ``ProjectStatusErrorCode`` 是 *status polling 的错误码集合*,与 HTTP
  ERROR_MAP machine code **部分重叠但不完全等同**
- 其中 ``parse_error`` 在 TASK-201 ERROR_MAP 内**无**对应 HTTP handler,
  仅用于 GET /status 的 polling 展示(D14:本 Task 任何 parse error →
  project failed → status polling 显示 ``parse_error``)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.domain.project import Project

ProjectStatus = Literal["parsing", "ready", "failed"]

# status polling 用错误码集合;与 HTTP ERROR_MAP machine code 部分重叠
ProjectStatusErrorCode = Literal[
    "zip_bomb",
    "zip_slip",
    "file_type_not_allowed",
    "project_too_large",
    "upload_error",      # UploadError fallback(未细分 leaf 时)
    "project_error",     # ProjectError fallback(未细分 leaf 时)
    "parse_error",       # 任何 ParseError 子类(本 Task D14)
    "internal_error",    # 未预期异常
]


@dataclass
class ProjectStatusRecord:
    """单次上传请求在 ProjectStore 中的完整记录。

    内部字段(``project`` / ``error_code``)的暴露由 ProjectStore 接口控制:
    GET /status 端点仅暴露 ``ProjectStatusView`` 的 5 字段
    (``project_id`` / ``name`` / ``status`` / ``created_at`` / ``error_code``),
    **不**暴露 ``project`` 内部结构。
    """
    project_id: str
    name: str                          # 经 _sanitize_filename 清洗(D15)
    status: ProjectStatus
    created_at: datetime               # 上传接收时间(D16)
    updated_at: datetime               # 状态最近变更时间
    # parsing 状态时为 None;ready 后填充
    project: Project | None = None
    # failed 状态时填错误码;不存原始异常字符串 / 文件名片段(隐私,风险 11)
    error_code: ProjectStatusErrorCode | None = None
```

### 7.2 `core/interfaces/project_store.py`

```python
"""项目状态存储抽象接口(本 Task InMemory,TASK-204 替换为 SQLite)。

设计原则:
1. 异步接口(``async def``)— 未来 SQLite 实现可能用 aiosqlite,接口
   提前定型;InMemory 实现内部用 asyncio.Lock
2. 细粒度方法(7 个)— 接口不暴露完整 ``ProjectStatusRecord``;GET /status
   端点专用 ``get_status_view`` 仅返回 5 字段,防止泄露 Project 内部
3. 异常对齐 ERROR_MAP — ``get_project`` 在 not-ready 时抛
   ``ProjectNotFoundError``(已在 TASK-201 ERROR_MAP)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from core.domain.project import Project
from core.domain.project_status import ProjectStatus, ProjectStatusErrorCode


@dataclass
class ProjectStatusView:
    """GET /status 端点专用视图(5 字段,不含 Project 内部)。"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: datetime
    error_code: ProjectStatusErrorCode | None


class ProjectStore(ABC):
    """工程状态存储(7 方法)。"""

    @abstractmethod
    async def create_pending(self, project_id: str, name: str) -> None:
        """创建 status=parsing 记录。已存在则抛 ValueError(由调用方处理)。"""
        ...

    @abstractmethod
    async def mark_ready(self, project_id: str, project: Project) -> None:
        """转 status=ready,落 Project。未存在 / 已 failed 则抛 ValueError。"""
        ...

    @abstractmethod
    async def mark_failed(
        self, project_id: str, error_code: ProjectStatusErrorCode
    ) -> None:
        """转 status=failed,记 error_code。未存在 / 已 ready 则抛 ValueError。"""
        ...

    @abstractmethod
    async def get_status_view(self, project_id: str) -> ProjectStatusView:
        """GET /status 端点用。未存在抛 ProjectNotFoundError。"""
        ...

    @abstractmethod
    async def get_project(self, project_id: str) -> Project:
        """取已 ready 的 Project。未 ready / 未存在抛 ProjectNotFoundError。"""
        ...

    @abstractmethod
    async def list_expired(self, ttl_hours: int) -> list[str]:
        """返回 ``created_at`` 早于 ttl_hours 的 project_id 列表(任意状态)。"""
        ...

    @abstractmethod
    async def delete(self, project_id: str) -> None:
        """删除记录。未存在静默 no-op(幂等)。"""
        ...
```

### 7.3 `adapters/storage/in_memory_project_store.py`

```python
"""进程内 dict + asyncio.Lock 实现,TASK-204 SQLite 接管前的临时桥接。

**硬约束**:仅支持单进程单 worker。uvicorn ``--workers > 1`` 下,POST
/upload 与 GET /status 可能落到不同 worker,造成 404 假象。本 Task
真启动验收只跑单 worker;TASK-204 持久化后可放开。

实现要点:
1. 单一 dict ``_records: dict[str, ProjectStatusRecord]`` 存全状态
2. 单一 ``asyncio.Lock`` 串行化所有写操作 — MCS 上传频率低(预期 < 1/s),
   全局锁不构成瓶颈;细粒度 per-id 锁 Phase 2 再优化
3. ``get_*`` 方法不持锁读 dict(Python GIL 保证 dict 单操作原子;读旧值
   不构成正确性问题,客户端 polling 自然收敛)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from core.domain.exceptions import ProjectNotFoundError
from core.domain.project import Project
from core.domain.project_status import (
    ProjectStatusErrorCode,
    ProjectStatusRecord,
)
from core.interfaces.project_store import ProjectStatusView, ProjectStore


class InMemoryProjectStore(ProjectStore):
    """进程内 dict 实现(7 方法)。"""

    def __init__(self) -> None:
        self._records: dict[str, ProjectStatusRecord] = {}
        self._lock = asyncio.Lock()

    async def create_pending(self, project_id: str, name: str) -> None:
        async with self._lock:
            if project_id in self._records:
                raise ValueError(f"project_id already exists: {project_id}")
            now = datetime.utcnow()
            self._records[project_id] = ProjectStatusRecord(
                project_id=project_id,
                name=name,
                status="parsing",
                created_at=now,
                updated_at=now,
            )

    async def mark_ready(self, project_id: str, project: Project) -> None:
        async with self._lock:
            record = self._records.get(project_id)
            if record is None:
                raise ValueError(f"project_id not found: {project_id}")
            if record.status != "parsing":
                raise ValueError(
                    f"cannot mark_ready: status is {record.status}"
                )
            record.status = "ready"
            record.project = project
            record.updated_at = datetime.utcnow()

    async def mark_failed(
        self, project_id: str, error_code: ProjectStatusErrorCode
    ) -> None:
        async with self._lock:
            record = self._records.get(project_id)
            if record is None:
                raise ValueError(f"project_id not found: {project_id}")
            if record.status == "ready":
                raise ValueError("cannot mark_failed: already ready")
            record.status = "failed"
            record.error_code = error_code
            record.updated_at = datetime.utcnow()

    async def get_status_view(self, project_id: str) -> ProjectStatusView:
        record = self._records.get(project_id)
        if record is None:
            raise ProjectNotFoundError(f"project not found: {project_id}")
        return ProjectStatusView(
            project_id=record.project_id,
            name=record.name,
            status=record.status,
            created_at=record.created_at,
            error_code=record.error_code,
        )

    async def get_project(self, project_id: str) -> Project:
        record = self._records.get(project_id)
        if record is None or record.status != "ready" or record.project is None:
            raise ProjectNotFoundError(
                f"project not ready or not found: {project_id}"
            )
        return record.project

    async def list_expired(self, ttl_hours: int) -> list[str]:
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        return [
            pid for pid, record in self._records.items()
            if record.created_at < cutoff
        ]

    async def delete(self, project_id: str) -> None:
        async with self._lock:
            self._records.pop(project_id, None)
```

### 7.4 `features/ingest/upload_service.py`

```python
"""上传 + 解析编排服务。

**严格分层(02 § 7)**:本模块不 import ``adapters/`` 任何子模块。所有
adapter 函数 / 类通过构造函数注入,类型用 Callable 别名或 ABC 表达。
``api/dependencies.py`` 负责把 TASK-102/103/104/105 的具体实现装配进来。

**关键边界**:
1. ``check_declared_size`` / ``check_actual_size`` 是 *同步方法*,
   异常向上抛 → route → ERROR_MAP(同步路径)
2. ``create_upload_record`` 同步预校验通过后调用,内部 UUID 冲突 3 次重试,
   失败抛 ``ProjectError``(已在 ERROR_MAP)
3. ``process`` 是 *async 方法*,被 ``BackgroundTasks.add_task`` 调度;
   **必须** try/except 翻译异常(异步路径独立于 route handler)
4. 同步重活(``extract`` / ``classify`` / ``parse`` / ``dep_analyze``)
   通过 ``asyncio.to_thread`` 桥接,**不**直接 await(D13,避免阻塞 event loop)
5. 日志 metadata-only,**禁** ``logger.exception``(风险 11)
"""
from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

from loguru import logger

from core.domain.exceptions import (
    FileTypeNotAllowedError,
    MxaError,
    ParseError,
    ProjectError,
    ProjectTooLargeError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_status import ProjectStatusErrorCode
from core.interfaces.parser import MParser, SlxParser
from core.interfaces.project_store import ProjectStore

# 已被装配层 curry 过 AppSettings 的 extractor;feature 不知道 settings 存在
ExtractFn: TypeAlias = Callable[[bytes, Path], Path]
ClassifyFn: TypeAlias = Callable[[Path, Path], list[FileInfo]]
DependencyAnalyzeFn: TypeAlias = Callable[
    [list[FileInfo], list[MFile], str | None], dict[str, list[str]]
]


# 业务异常 → ProjectStatusErrorCode 映射
# 本 Task 唯一的异常翻译点;仅用于 BackgroundTask 内 mark_failed
_LEAF_CODE_MAP: dict[type[Exception], ProjectStatusErrorCode] = {
    ZipBombError: "zip_bomb",
    ZipSlipError: "zip_slip",
    FileTypeNotAllowedError: "file_type_not_allowed",
    ProjectTooLargeError: "project_too_large",
}


def _classify_error(exc: Exception) -> ProjectStatusErrorCode:
    """把业务异常翻译为 ProjectStatusErrorCode。"""
    for exc_type, code in _LEAF_CODE_MAP.items():
        if isinstance(exc, exc_type):
            return code
    if isinstance(exc, UploadError):
        return "upload_error"
    if isinstance(exc, ProjectError):
        return "project_error"
    if isinstance(exc, ParseError):
        return "parse_error"  # D14: 任何 ParseError → project failed
    return "internal_error"


# 控制字符正则(NUL / 换行 / TAB 等),用于 filename 清洗
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_filename(raw: str | None) -> str:
    """清洗 multipart filename(D15)。

    1. 取最后一级路径片段(防 ``../`` / Windows 反斜杠)
    2. 去控制字符(NUL / 换行 / TAB)
    3. 截断 100 字符
    4. 空 fallback ``uploaded.zip``
    """
    if not raw:
        return "uploaded.zip"
    # 取最后一级 path 片段(Path 自动处理 / 和 \\)
    name = Path(raw.replace("\\", "/")).name
    # 去控制字符
    name = _CONTROL_CHARS_RE.sub("", name)
    # 截断 100 字符
    name = name[:100].strip()
    return name or "uploaded.zip"


class UploadService:
    """编排上传同步预校验 + 异步解析。"""

    def __init__(
        self,
        store: ProjectStore,
        upload_dir: Path,
        max_upload_bytes: int,
        extractor: ExtractFn,
        classifier: ClassifyFn,
        slx_parser: SlxParser,
        m_parser: MParser,
        dependency_analyzer: DependencyAnalyzeFn,
    ) -> None:
        self._store = store
        self._upload_dir = upload_dir
        self._max_upload_bytes = max_upload_bytes
        self._extractor = extractor
        self._classifier = classifier
        self._slx_parser = slx_parser
        self._m_parser = m_parser
        self._dependency_analyzer = dependency_analyzer

    # ---------- 同步预校验(P0-1:declared 先,read body 后,actual 兜底)----------

    def check_declared_size(self, declared_size: int | None) -> None:
        """第一道防线:HTTP 表头 Content-Length 校验,**不读 body 即拒**。

        ``declared_size`` 来自 ``starlette.UploadFile.size``;在 chunked
        transfer 等情况下可能为 ``None``,此时跳过(由第二道兜底)。
        """
        if declared_size is not None and declared_size > self._max_upload_bytes:
            raise ProjectTooLargeError("上传压缩包过大,请检查后重新上传")

    def check_actual_size(self, actual_size: int) -> None:
        """第二道兜底:read body 后实际字节数校验,覆盖 declared=None。"""
        if actual_size > self._max_upload_bytes:
            raise ProjectTooLargeError("上传压缩包过大,请检查后重新上传")

    # ---------- 创建上传记录(P0-7:UUID 冲突 3 次重试)----------

    async def create_upload_record(self, name: str) -> str:
        """生成 UUID + store 落 parsing 记录,3 次重试 UUID 冲突。

        返回 ``project_id``。冲突 3 次后抛 ``ProjectError``(已在 ERROR_MAP)。
        route 层**不**处理 ValueError(那是 store 的内部信号)。
        """
        last_error: ValueError | None = None
        for _ in range(3):
            project_id = str(uuid.uuid4())
            try:
                await self._store.create_pending(project_id, name)
                return project_id
            except ValueError as exc:
                last_error = exc
                continue
        # 三次 UUID4 冲突 ≈ 2^(-122 × 3) 概率,实际不可能;留兜底
        raise ProjectError("无法创建上传记录,请重试") from last_error

    # ---------- 异步解析(P0-2:asyncio.to_thread 桥接;P0-3:metadata 日志)----------

    async def process(
        self, project_id: str, zip_bytes: bytes, name: str
    ) -> None:
        """异步:解压 + 解析 + 落库,**所有**业务异常翻译为 mark_failed。

        这是本 feature 模块**唯一**允许 ``except`` 业务异常的方法。
        理由:FastAPI ``BackgroundTasks`` 吞掉未处理异常,若不在这里
        翻译,project 永远卡在 status=parsing,GET /status 永远轮询
        不到失败结果。

        同步重活通过 ``asyncio.to_thread`` 桥接(D13),避免阻塞 event loop。
        日志统一 metadata-only(类名 / project_id / error_code),**禁**
        ``logger.exception``(风险 11)。
        """
        project_dir = self._upload_dir / project_id
        try:
            # mkdir 是 async 友好的轻操作,不需要 to_thread
            project_dir.mkdir(parents=True, exist_ok=False)

            # 同步重活全部丢线程池
            project = await asyncio.to_thread(
                self._run_parse_sync,
                project_id,
                zip_bytes,
                name,
                project_dir,
            )

            await self._store.mark_ready(project_id, project)
            logger.info(
                "Upload processed: project_id={} files={} slx={} m={}",
                project_id,
                len(project.files),
                len(project.slx_models),
                len(project.m_files),
            )

        except MxaError as exc:
            error_code = _classify_error(exc)
            # **不**记录 str(exc) / 文件名片段 / 文件内容(风险 11)
            logger.error(
                "Upload processing failed: project_id={} exception={} error_code={}",
                project_id,
                type(exc).__name__,
                error_code,
            )
            await self._store.mark_failed(project_id, error_code)
            self._cleanup_project_dir(project_dir)

        except Exception as exc:
            # 未预期异常 — 仅记类名,**禁** logger.exception(风险 11)
            logger.error(
                "Upload processing crashed: project_id={} exception={}",
                project_id,
                type(exc).__name__,
            )
            await self._store.mark_failed(project_id, "internal_error")
            self._cleanup_project_dir(project_dir)

    def _run_parse_sync(
        self,
        project_id: str,
        zip_bytes: bytes,
        name: str,
        project_dir: Path,
    ) -> Project:
        """同步重活集合;通过 ``asyncio.to_thread`` 在线程池执行(D13)。

        本方法**只调同步函数**,不 await 任何 async 调用(那会触发跨线程
        event loop 错误)。所有异常向上抛,由 ``process`` 顶层捕获翻译。
        """
        # 1. 沙箱解压
        extracted_root = self._extractor(zip_bytes, project_dir)

        # 2. 文件分类
        file_infos = self._classifier(extracted_root, extracted_root)

        # 3. 逐 .slx 解析(D14:任何 SlxParseError 抛出 → process 顶层翻译 parse_error)
        slx_models = []
        for fi in file_infos:
            if fi.file_type == ".slx":
                abs_path = str(extracted_root / fi.relative_path)
                slx_models.append(self._slx_parser.parse(abs_path))

        # 4. 逐 .m 解析(D14:任何 MParseError 同上)
        m_files = []
        for fi in file_infos:
            if fi.file_type == ".m":
                abs_path = str(extracted_root / fi.relative_path)
                m_files.append(self._m_parser.parse(abs_path))

        # 5. 依赖分析
        deps = self._dependency_analyzer(
            file_infos, m_files, str(extracted_root)
        )

        # 6. 构造 Project(本 Task 全部填 GENERAL + mat_files=[])
        return Project(
            id=project_id,
            name=name,
            project_type=ProjectType.GENERAL,
            files=file_infos,
            slx_models=slx_models,
            m_files=m_files,
            mat_files=[],  # D7: 不开 MatReader
            created_at=datetime.utcnow(),  # D16: 解析完成时间
            file_dependencies=deps,
        )

    @staticmethod
    def _cleanup_project_dir(project_dir: Path) -> None:
        """删项目目录,失败静默(cleanup worker 兜底)。"""
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
```

**关键点回顾**:
- `check_declared_size` 先调,**不读 body**(P0-1 第一道防线)
- `check_actual_size` 在 `await file.read()` 之后调(第二道兜底)
- `create_upload_record` 内部 UUID 冲突 3 次重试,失败抛 `ProjectError` → route 不暴露 `ValueError`(P0-7)
- `process` 内同步重活全部走 `asyncio.to_thread(_run_parse_sync, ...)`(D13 / P0-2)
- 所有异常分支 `logger.error(..., type(exc).__name__)`,**禁** `logger.exception`(P0-3)
- D14:任何 `ParseError`(`SlxParseError` / `MParseError`)→ `MxaError` catch-all → `_classify_error` → `parse_error` → `mark_failed`

### 7.5 `features/ingest/cleanup_worker.py`

```python
"""TTL 24h 临时目录清理 worker。

设计:
1. lifespan 启动时创建 asyncio.Task 跑 ``run_forever()``
2. lifespan shutdown 时 ``cancel()`` + ``await`` 等待结束(吞 CancelledError)
3. 扫描周期 ``interval_minutes`` 走构造默认值 60,**不入 AppSettings**(D8)
4. TTL 复用 ``settings.upload_ttl_hours``,**不**新增 ``cleanup_ttl_hours``
5. 删除顺序:先删磁盘(``shutil.rmtree(..., ignore_errors=True)``)→ 后删
   store entry。磁盘失败不阻塞 store 删除(cleanup 是兜底,不是事务)
6. 日志统一 metadata-only,**禁** ``logger.exception``(风险 11)
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from loguru import logger

from core.interfaces.project_store import ProjectStore


class CleanupWorker:
    """常驻 asyncio.Task,定时清理过期项目。"""

    def __init__(
        self,
        store: ProjectStore,
        upload_dir: Path,
        ttl_hours: int,
        interval_minutes: int = 60,
    ) -> None:
        self._store = store
        self._upload_dir = upload_dir
        self._ttl_hours = ttl_hours
        self._interval_seconds = interval_minutes * 60

    async def run_once(self) -> int:
        """单次扫描 + 清理,返回删除的 project_id 数量。"""
        try:
            expired = await self._store.list_expired(self._ttl_hours)
        except Exception as exc:
            # metadata-only,禁 logger.exception(风险 11)
            logger.error("Cleanup list_expired failed: exception={}", type(exc).__name__)
            return 0

        deleted = 0
        for pid in expired:
            project_dir = self._upload_dir / pid
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
            try:
                await self._store.delete(pid)
                deleted += 1
            except Exception as exc:
                logger.error(
                    "Cleanup store delete failed: project_id={} exception={}",
                    pid,
                    type(exc).__name__,
                )

        if deleted > 0:
            logger.info("Cleanup deleted {} expired projects", deleted)
        return deleted

    async def run_forever(self) -> None:
        """常驻循环,被 lifespan 的 AsyncExitStack 管控。"""
        logger.info(
            "CleanupWorker started: ttl_hours={} interval_seconds={}",
            self._ttl_hours,
            self._interval_seconds,
        )
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.info("CleanupWorker cancelled")
            raise
```

### 7.6 `api/routes/upload.py`

```python
"""上传 + 状态查询 HTTP 端点。

**关键边界**:
1. 同步路径(``POST /upload`` 入口部分)**不** try/except 业务异常 —
   异常向上抛由 TASK-201 ERROR_MAP 翻译,确保响应体 shape
   ``{"error", "message"}`` 一致
2. 异步路径(BackgroundTask 内的 ``service.process``)**必须** try/except
   翻译为 ``mark_failed``,详见 § 7.4 注释
3. 不依赖 BackgroundTasks 同步行为来设计接口语义 — 生产 uvicorn 是真
   异步,客户端必须 polling;TestClient 的同步等待仅用于测试确定性
   (D3)
4. size 校验顺序(P0-1):``check_declared_size`` → ``await file.read()``
   → ``check_actual_size``;**禁止颠倒**,否则不读 body 即拒的安全收益消失
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from loguru import logger

from api.dependencies import get_project_store, get_upload_service
from api.schemas.upload import ProjectStatusResponse, UploadResponse
from core.interfaces.project_store import ProjectStore
from features.ingest.upload_service import UploadService, _sanitize_filename

router = APIRouter(tags=["upload"])


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResponse,
)
async def upload(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> UploadResponse:
    """异步上传 + 解析入口(HTTP 202)。

    同步部分:
    1. ``check_declared_size``:HTTP 表头 size,**不读 body 即拒**(防 DoS)
    2. ``await file.read()``:载入 zip bytes 到内存
    3. ``check_actual_size``:实际字节数兜底(覆盖 declared=None)
    4. ``create_upload_record``:生成 UUID + store 落 parsing
    5. 注册 BackgroundTask
    6. 返回 202

    异步部分:见 § 7.4 ``UploadService.process``。
    """
    # 第一道:declared check,不读 body
    service.check_declared_size(file.size)

    # 读 bytes
    zip_bytes = await file.read()

    # 第二道:actual check,兜底 declared=None
    service.check_actual_size(len(zip_bytes))

    # 清洗 filename(D15:控制字符 / 路径片段 / 长度)
    name = _sanitize_filename(file.filename)

    # 生成 project_id + store 落 parsing(内部 UUID 冲突 3 次重试)
    project_id = await service.create_upload_record(name)
    logger.info(
        "Upload accepted: project_id={} size_bytes={}",
        project_id,
        len(zip_bytes),
    )

    # BackgroundTask:返回 response 后才跑;process 内部翻译异常
    background_tasks.add_task(service.process, project_id, zip_bytes, name)

    return UploadResponse(project_id=project_id, status="parsing")


@router.get(
    "/projects/{project_id}/status",
    response_model=ProjectStatusResponse,
)
async def get_status(
    project_id: str,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> ProjectStatusResponse:
    """轮询状态查询。

    未存在的 project_id → 抛 ``ProjectNotFoundError`` → 404 经 ERROR_MAP。
    """
    view = await store.get_status_view(project_id)
    return ProjectStatusResponse(
        project_id=view.project_id,
        name=view.name,
        status=view.status,
        created_at=view.created_at,
        error_code=view.error_code,
    )
```

**关于 route 不 try/except**(对齐 TASK-201 风险 11):
- `service.check_declared_size` 抛 `ProjectTooLargeError` → ERROR_MAP 413
- `service.check_actual_size` 同上
- `service.create_upload_record` 内部翻 `ValueError` → `ProjectError` → ERROR_MAP 400
- `await file.read()` IO 错误 → starlette 默认 500 → MxaError fallback
- `store.get_status_view` 抛 `ProjectNotFoundError` → ERROR_MAP 404

### 7.7 `api/schemas/upload.py`

```python
"""上传端点的请求 / 响应 schema。

锁定 ``extra="forbid"``:任何额外字段触发 ``ValidationError``,
防止未来不小心放进未声明字段(例如调试信息泄漏)。
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.domain.project_status import ProjectStatusErrorCode


class UploadResponse(BaseModel):
    """``POST /upload`` 响应体(202 Accepted)。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    # 上传成功后必为 parsing,不可能直接 ready/failed
    status: Literal["parsing"]


class ProjectStatusResponse(BaseModel):
    """``GET /projects/{project_id}/status`` 响应体(5 字段)。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    status: Literal["parsing", "ready", "failed"]
    created_at: datetime  # 上传接收时间(D16)
    # 仅 status=failed 时非空;ProjectStatusErrorCode 8 种码之一
    error_code: ProjectStatusErrorCode | None = None
```

### 7.8 `api/dependencies.py` 追加(完整 import 顶部,copy-safe)

在 `api/dependencies.py` **顶部**追加 import,**末尾**追加函数。完整新文件(本 Task 修改后)样貌:

```python
"""FastAPI 依赖注入容器。

(原 TASK-201 docstring 保留,本 Task 追加 ProjectStore + UploadService 装配)
"""

from functools import lru_cache, partial
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Request

from adapters.parser.dependency_analyzer import analyze_dependencies
from adapters.parser.file_classifier import classify_files
from adapters.parser.m_parser import MParserImpl
from adapters.parser.slx_parser import SlxParserImpl
from adapters.parser.zip_extractor import safe_extract
from adapters.storage.in_memory_project_store import InMemoryProjectStore  # noqa: F401  # 由 lifespan 装配
from app.config import AppSettings
from core.interfaces.project_store import ProjectStore
from features.ingest.upload_service import ExtractFn, UploadService


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """加载并返回单例 ``AppSettings``。"""
    settings_values: dict[str, Any] = {}
    return AppSettings(**settings_values)


# ============== 以下为 TASK-202 追加 ==============


def get_project_store(request: Request) -> ProjectStore:
    """从 ``app.state.project_store`` 取(由 lifespan 装配)。

    用 ``app.state`` 而不是 ``lru_cache``:测试反复 ``create_app()`` 时
    cache 会持旧 store 引用,污染下一个测试;``app.state`` 与 app 实例
    同生命周期,自然清理。
    """
    return request.app.state.project_store


def get_upload_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> UploadService:
    """每次请求构造新 UploadService(store 是单例,service 无状态)。"""
    upload_dir = Path(settings.upload_dir)
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024

    # 把 AppSettings curry 进 safe_extract,feature 层不知道 settings 存在
    extractor: ExtractFn = partial(safe_extract, config=settings)

    return UploadService(
        store=store,
        upload_dir=upload_dir,
        max_upload_bytes=max_upload_bytes,
        extractor=extractor,
        classifier=classify_files,
        slx_parser=SlxParserImpl(),
        m_parser=MParserImpl(),
        dependency_analyzer=analyze_dependencies,
    )
```

**关于 InMemoryProjectStore 的 `# noqa: F401`**:仅为模块加载副作用 + 类型可见性;实际实例化由 lifespan(§ 7.9)做。`# noqa` 唯一允许此处使用。

**关于 partial 签名兼容**:`safe_extract(zip_bytes, dest_dir, config)` 三位参数;`partial(safe_extract, config=settings)` 绑定关键字 `config` 后剩 `(zip_bytes, dest_dir)` 两位位置参数,符合 `ExtractFn = Callable[[bytes, Path], Path]` 签名。

### 7.9 `api/main.py` lifespan 扩展

```python
"""FastAPI app 工厂与模块级入口。

(原 TASK-201 docstring 保留)

TASK-202 新增:
- lifespan 内 AsyncExitStack 装配 InMemoryProjectStore + CleanupWorker
- shutdown 时 cancel + await cleanup task,吞 CancelledError
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from adapters.storage.in_memory_project_store import InMemoryProjectStore
from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from api.routes.health import router as health_router
from api.routes.upload import router as upload_router
from features.ingest.cleanup_worker import CleanupWorker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifecycle。

    使用 AsyncExitStack 确保 startup 中任一步骤失败时,已启动资源被清理
    (TASK-201 风险 9 guardrail)。
    """
    settings = get_settings()
    logger.info(
        "Application startup: db_path={}, upload_dir={}, ttl_hours={}",
        settings.db_path,
        settings.upload_dir,
        settings.upload_ttl_hours,
    )

    # 确保 upload_dir 存在
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncExitStack() as stack:
        # 资源 A:InMemoryProjectStore(本 Task 单 worker 限制,D5)
        store = InMemoryProjectStore()
        app.state.project_store = store

        # 资源 B:CleanupWorker(常驻 task,interval 走构造默认 60,D8)
        worker = CleanupWorker(
            store=store,
            upload_dir=upload_dir,
            ttl_hours=settings.upload_ttl_hours,
        )
        cleanup_task = asyncio.create_task(worker.run_forever())

        async def _shutdown_cleanup() -> None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("CleanupWorker shutdown complete")

        stack.push_async_callback(_shutdown_cleanup)

        yield

    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """构造 FastAPI app 实例。"""
    settings = get_settings()
    app = FastAPI(
        title="mxa-tutor",
        version="0.0.1",
        description="工科仿真 AI 助教 — MATLAB/Simulink 工程导览与智能问答",
        lifespan=lifespan,
    )
    register_error_handlers(app, settings)
    app.include_router(health_router)
    app.include_router(upload_router)
    return app


app = create_app()
```

**关键点**:
- `AsyncExitStack` 保证若 `CleanupWorker.create_task` 后 lifespan 中段失败(本 Task 没有"中段",但为未来 Task 留接口),`_shutdown_cleanup` 仍会跑
- `app.state.project_store` 是 `get_project_store` dependency 的取数源
- `interval_minutes` **不**从 settings 读,走构造默认 60(D8)

### 7.10 测试布局

**4 个测试模块**,对应 4 个生产模块。

#### § 7.10.1 `tests/adapters/storage/test_in_memory_project_store.py`

覆盖 **7 个 ProjectStore 方法** + 异常分支。用例(~14 个):

```
test_create_pending_creates_record_with_now_timestamps
test_create_pending_duplicate_raises_value_error
test_mark_ready_transitions_status_and_attaches_project
test_mark_ready_on_missing_raises_value_error
test_mark_ready_on_already_failed_raises_value_error
test_mark_failed_records_error_code_using_literal_type
test_mark_failed_on_already_ready_raises_value_error
test_get_status_view_returns_five_fields_excluding_project
test_get_status_view_missing_raises_project_not_found_error
test_get_project_returns_only_when_ready
test_get_project_when_failed_raises_project_not_found_error
test_list_expired_filters_by_created_at_boundary
test_delete_is_idempotent_on_missing
test_concurrent_create_does_not_deadlock  # asyncio.gather 同时 create 多个
```

#### § 7.10.2 `tests/features/ingest/test_upload_service.py`

注入 fake extractor / classifier / parsers / store,断言编排逻辑。**不**调真实 `safe_extract`。用例(~24 个):

```
# size 双道(P0-1)
test_check_declared_size_pass_within_limit
test_check_declared_size_raises_before_read_body
test_check_declared_size_handles_none
test_check_actual_size_raises_when_exceeds
test_check_actual_size_pass_within_limit

# create_upload_record(P0-7)
test_create_upload_record_generates_uuid_and_creates_pending
test_create_upload_record_retries_on_value_error_collision
test_create_upload_record_raises_project_error_after_three_collisions

# _sanitize_filename(D15)
test_sanitize_filename_strips_path_traversal
test_sanitize_filename_strips_control_chars
test_sanitize_filename_truncates_long
test_sanitize_filename_empty_falls_back_to_uploaded_zip
test_sanitize_filename_handles_none

# process(D13 / D14)
test_process_happy_path_marks_ready_with_project
test_process_uses_to_thread_for_sync_parsers  # mock asyncio.to_thread, assert called
test_process_zip_bomb_marks_failed_with_zip_bomb_code
test_process_zip_slip_marks_failed_with_zip_slip_code
test_process_file_type_not_allowed_marks_failed
test_process_project_too_large_marks_failed
test_process_slx_parse_error_marks_failed_parse_error  # D14
test_process_m_parse_error_marks_failed_parse_error    # D14
test_process_unexpected_exception_marks_failed_internal_error
test_process_logger_never_uses_exception_method  # P0-3
test_process_cleans_up_project_dir_on_failure
test_process_constructs_project_with_correct_fields  # mat_files=[], project_type=GENERAL
```

**Fake 模式**:`FakeExtractor` / `FakeClassifier` / `FakeSlxParser` / `FakeMParser` / `FakeDependencyAnalyzer` 通过参数化抛指定异常。`test_process_uses_to_thread_for_sync_parsers` 用 `mocker.patch("features.ingest.upload_service.asyncio.to_thread")` 拦截并断言。

`test_process_logger_never_uses_exception_method` 用 grep 源码兜底:

```python
def test_process_logger_never_uses_exception_method():
    src = (Path(__file__).parent.parent.parent.parent / "features/ingest/upload_service.py").read_text()
    assert "logger.exception" not in src
```

#### § 7.10.3 `tests/features/ingest/test_cleanup_worker.py`

monkeypatch `asyncio.sleep` + 时间。用例(~9 个):

```
test_run_once_deletes_expired_projects
test_run_once_returns_zero_when_none_expired
test_run_once_handles_store_list_expired_failure_with_metadata_log
test_run_once_handles_store_delete_failure_on_one_pid_continues_others
test_run_once_removes_disk_dir_first_then_store
test_run_once_skips_disk_when_dir_not_exist
test_run_once_logger_never_uses_exception_method  # P0-3
test_run_forever_cancellation_propagates_cleanly
test_run_forever_interval_respected  # patch sleep, assert call count
```

#### § 7.10.4 `tests/api/test_upload.py`

复用 TASK-201 autouse fixture。本 Task 在测试文件内用 `app.dependency_overrides` 注入受控 fake。用例(~18 个):

```
# happy + size 同步
test_post_upload_returns_202_with_project_id_parsing
test_post_upload_declared_size_too_large_returns_413_without_reading_body
test_post_upload_actual_size_too_large_returns_413
test_post_upload_uuid_format_is_uuid4

# 受控 fake service 锁定 parsing 状态(补强 3)
test_get_status_returns_parsing_initially_with_controlled_fake_event
test_get_status_returns_ready_after_background_completes
test_get_status_returns_failed_with_error_code
test_get_status_missing_returns_404_with_locked_shape

# 5 字段 + extra-forbid + Literal 锁(P0-4 / P0-8)
test_get_status_response_includes_created_at_field
test_upload_response_extra_forbid_enforced
test_status_response_extra_forbid_enforced
test_status_response_error_code_within_known_literals

# TestClient 行为锁定(D3)
test_testclient_waits_for_background_task

# 5 类异步对抗(A 组)
test_a_zip_bomb_async_marks_failed_with_zip_bomb_code
test_a_zip_slip_async_marks_failed_with_zip_slip_code
test_a_bad_extension_async_marks_failed_with_file_type_not_allowed
test_a_oversized_inner_file_async_marks_failed_with_project_too_large
test_a_too_many_files_async_marks_failed_with_project_too_large

# 1 类同步对抗(B 组,P0-9)
test_b_outer_body_too_large_returns_413_with_locked_shape_synchronously

# 响应 shape 锁
test_response_shape_lock_error_and_message_only_for_413
```

**关于受控 fake service**(补强 3):

```python
class FakeUploadService:
    """fake service: process 一直 await asyncio.Event,直到测试主动 set。"""
    def __init__(self):
        self._event = asyncio.Event()
        self.store = ...
    def check_declared_size(self, size): pass
    def check_actual_size(self, size): pass
    async def create_upload_record(self, name):
        pid = str(uuid.uuid4())
        await self.store.create_pending(pid, name)
        return pid
    async def process(self, project_id, zip_bytes, name):
        await self._event.wait()  # 锁定 parsing 状态

# 测试主体
fake = FakeUploadService()
app.dependency_overrides[get_upload_service] = lambda: fake

with TestClient(app) as client:
    response = client.post("/upload", files={...})
    pid = response.json()["project_id"]
    # event 未 set,background task 卡在 await;GET /status 看到 parsing
    status_response = client.get(f"/projects/{pid}/status")
    assert status_response.json()["status"] == "parsing"
    # 主动 set + with 块退出时 TestClient 自动 await background 完成
    fake._event.set()
```

#### § 7.11 集成场景 — A 组(5 异步) + B 组(1 同步)(P0-9)

`test_upload.py` 中使用**真实** `safe_extract`(不 mock),验证 API → service → adapter → store → handler → response shape 全链路。

**A 组 — 5 类异步 adapter 对抗**(POST 202 + 后台 mark_failed):

| 对抗类型 | fixture | POST 结果 | GET /status 结果 |
|---|---|---|---|
| zip bomb | TASK-104 `bomb.zip` 等价(高压缩比小内容) | 202 + parsing | failed + `zip_bomb` |
| zip slip | TASK-104 `slip.zip` 等价(含 `../`) | 202 + parsing | failed + `zip_slip` |
| bad extension | 含 `.exe` 的合法 zip | 202 + parsing | failed + `file_type_not_allowed` |
| oversized inner file | zip 内单文件 > 20MB,外层 zip body < 50MB | 202 + parsing | failed + `project_too_large` |
| too many files | zip 内 > 200 文件,外层 zip body < 50MB | 202 + parsing | failed + `project_too_large` |

**B 组 — 1 类同步 body size 对抗**(POST 413,同步路径):

| 对抗类型 | fixture | POST 结果 | GET /status |
|---|---|---|---|
| outer body too large | 外层 zip body > `max_upload_size_mb` (50MB) | **413** + `project_too_large` | N/A(无 store 记录) |

**关键区分**:
- A 组 "oversized inner file":zip 内单文件超 20MB,外层 zip body 仍在 50MB 内,**通过同步 size 校验**,进 BackgroundTask 后由 `safe_extract` 的 `max_single_file_mb` 抛
- B 组 "outer body too large":外层 zip body 直接超 50MB,**在同步 `check_actual_size` / `check_declared_size` 即拒**,不进 BackgroundTask
- 两种都是 `project_too_large`,但触发点完全不同;测试名前缀 `test_a_*` / `test_b_*` 显式区分

**fixture 复用 vs 新建**:
- bomb / slip / bad extension:复用 TASK-104 已有 fixture(若存在;Codex 实地 ls `tests/fixtures/`)
- oversized inner file / too many files / outer body too large:测试内动态生成(`zipfile.ZipFile` 写入 200+ 空文件 / 单 21MB 文件 / 51MB 字节流);**不**入仓 fixture(避免大文件污染 git)

---

## 验收标准

> 命令在仓库根目录(`F:\mxa-tutor`)执行,且已 `source .venv/Scripts/activate`。

### 1. 新增文件全部就位

```bash
ls core/domain/project_status.py core/interfaces/project_store.py adapters/storage/in_memory_project_store.py features/ingest/upload_service.py features/ingest/cleanup_worker.py api/routes/upload.py api/schemas/upload.py
```

### 2. 测试目录骨架就位

```bash
ls tests/adapters/storage/__init__.py tests/adapters/storage/test_in_memory_project_store.py tests/features/__init__.py tests/features/ingest/__init__.py tests/features/ingest/test_upload_service.py tests/features/ingest/test_cleanup_worker.py tests/api/test_upload.py
```

### 3. requirements.txt 已加 python-multipart

```bash
grep -n "^python-multipart==" requirements.txt
```

期望:`python-multipart==0.0.17` 一行。

### 4. AppSettings 字段数未变(零增量验证,D2 / D8)

```bash
grep -cE "^\s+[a-z_]+:\s" app/config.py
```

期望:与 TASK-201 合并后实际行数相同(实施前先记基线,实施后应一致)。

### 5. Project dataclass 未被改

```bash
grep -A 12 "^class Project:" core/domain/project.py
```

期望:9 字段,与 dump 完全一致。

### 6. error_handler.py 未被改

```bash
git diff main -- api/middleware/error_handler.py
```

期望:空 diff(本 Task 不加 handler)。

### 7. mat_reader.py 仍不存在

```bash
ls adapters/parser/mat_reader.py 2>&1
```

期望:`No such file or directory`(D7 守住)。

### 8. UploadService 不 import adapters/

```bash
grep -nE "^from adapters\." features/ingest/upload_service.py
```

期望:**空输出**(严格分层,02 § 7;D12)。

### 9. CleanupWorker 不 import AppSettings

```bash
grep -nE "^from app\." features/ingest/cleanup_worker.py
```

期望:**空输出**(feature 层零 app 依赖)。

### 10. route 不 try/except 业务异常

```bash
grep -nE "except\s+(Upload|Project|Mxa|Zip|File|Parse)" api/routes/upload.py
```

期望:**空输出**(异常向上抛走 ERROR_MAP)。

### 11. `logger.exception` 全工程禁用(P0-3 / 风险 11)

```bash
grep -nE "logger\.exception" features/ingest/upload_service.py features/ingest/cleanup_worker.py api/routes/upload.py
```

期望:**空输出**。

### 12. ProjectStore 接口确为 7 方法(P0-5)

```bash
grep -cE "^\s+@abstractmethod" core/interfaces/project_store.py
```

期望:`7`。

### 13. ProjectStatusResponse 含 created_at 字段(P0-4)

```bash
grep -n "created_at" api/schemas/upload.py
```

期望:看到 `created_at: datetime` 行。

### 14. size 校验顺序正确(P0-1):declared check 必须在 await read 之前

```bash
python -c "
src = open('api/routes/upload.py').read()
i_decl = src.find('check_declared_size')
i_read = src.find('await file.read')
i_actual = src.find('check_actual_size')
assert 0 < i_decl < i_read < i_actual, f'order wrong: {i_decl} {i_read} {i_actual}'
print('size order OK')
"
```

期望:`size order OK`。

### 15. asyncio.to_thread 在 process 内被调用(P0-2 / D13)

```bash
grep -n "asyncio.to_thread" features/ingest/upload_service.py
```

期望:至少 1 行命中(在 `process` 方法内桥接 `_run_parse_sync`)。

### 16. 单测全绿

```bash
pytest tests/adapters/storage/ tests/features/ tests/api/test_upload.py -v
```

期望:约 65 用例全绿(14 store + 24 service + 9 cleanup + 18 api)。

### 17. 整套测试全绿

```bash
pytest -v --tb=short
```

期望:含 TASK-201 / Week 1 全部已有用例 + 本 Task 新增 → 全绿。

### 18. 全检通过

```bash
make check
```

期望:lint / format / mypy / test / hygiene 五件套全绿。

### 19. 本地 ruff format 加跑(反例 11)

```bash
python -m ruff format --check .
```

期望:无变更(防 CI 版本漂移)。

### 20. pip check 验证依赖兼容

```bash
pip check
```

期望:`No broken requirements found.`

### 21. uvicorn 真启动(单 worker,D5)+ /health

```bash
uvicorn api.main:app --port 8000
```

另一个终端:
```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

期望:`{"status": "ok", "version": "0.0.1", "app_name": "mxa-tutor"}`。
**注**:`--workers > 1` 会破坏 InMemoryProjectStore 假设,不可用(D5 / 风险 1 / 14)。

### 22. uvicorn + curl 上传 happy path

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST http://127.0.0.1:8000/upload -F "file=@tests/fixtures/slx_samples/<选一个合法 demo>.zip"
```

期望:HTTP 202,响应体 `{"project_id": "<uuid>", "status": "parsing"}`。

```bash
curl -s http://127.0.0.1:8000/projects/<上一步的 uuid>/status | python -m json.tool
```

期望:**首次 polling 可能看到 `parsing`**(若解析未完成);稍后 polling 看到 `ready`,响应体含 `created_at` 字段(**5 字段**)。

### 23. uvicorn + curl — A 组 5 类异步对抗 + B 组 1 类同步对抗(P0-9)

**A 组**(全部 POST 202,GET 后看 failed):

| fixture | POST | GET /status |
|---|---|---|
| `bomb.zip` 等价 | 202 + parsing | failed + `zip_bomb` |
| `slip.zip` 等价 | 202 + parsing | failed + `zip_slip` |
| 含 `.exe` 的合法 zip | 202 + parsing | failed + `file_type_not_allowed` |
| inner 单文件 > 20MB,outer < 50MB | 202 + parsing | failed + `project_too_large` |
| inner 200+ 文件,outer < 50MB | 202 + parsing | failed + `project_too_large` |

**B 组**(POST 直接 413):

| fixture | POST | GET /status |
|---|---|---|
| outer body > 50MB | **413** + body `{"error": "project_too_large", "message": "..."}` | N/A |

### 24. 03 索引同步

```bash
grep -nE "^\| TASK-202 " docs/03_TASK_INDEX.md
```

期望:状态由 `🔲` 改为 `🔍`(review)或 `✅`(已合并)。

### 25. Git 三件套(完工报告)

```bash
git status
git log --oneline main..HEAD
git push origin task-202-upload-parse-api
```

完工报告必须包含三件套**完整 stdout**(决策 08)。

---

## 风险与注意点

### 风险 1:单 worker / InMemoryProjectStore 不支持多进程(D5 硬约束)

**症状**:`uvicorn --workers 4` 启动,POST /upload 落 worker A,GET /status 落 worker B → 404。

**规避**:
- `api/README.md` 明示单 worker 限制
- 本 Task 真启动验收**禁** `--workers > 1`
- TASK-204 接管持久化后再放开,通过 docs 决策日志记录解除时机

### 风险 2:TestClient 同步 background task 行为 ≠ 生产 uvicorn(D3)

**症状**:测试用 `TestClient` 立即看到 `status=ready`,开发者误以为生产也这样,前端没写 polling。

**规避**:
- `test_upload.py` 加 `test_testclient_waits_for_background_task` 显式锁定测试环境行为
- 真启动验收(§ 8 验收 22)明示**首次 polling 可能看到 parsing**
- 用受控 fake service + `asyncio.Event` 锁定 `test_get_status_returns_parsing_initially`(补强 3)
- `api/README.md` 单独段"测试 vs 生产语义"

### 风险 3:route 层误捕获业务异常,绕过 TASK-201 handler

**症状**:`POST /upload` 内写 `try: ... except ZipBombError: raise HTTPException(400, "...")`,响应体 shape 变成 `{"detail": "..."}` 不再是 `{"error", "message"}`。

**规避**:
- § 7.6 route 代码骨架**不含** try/except 业务异常
- § 8 验收 10 grep `except (Upload|Project|Mxa|Zip|File|Parse)` 应空
- code review 重点检查项

### 风险 4:`cleanup_ttl_hours` 与 `upload_ttl_hours` 双来源冲突(D8)

**症状**:开发者顺手加 `cleanup_ttl_hours: int = 24` 到 AppSettings,与已有 `upload_ttl_hours=24` 重复;后续修改一个忘了另一个 → 24h vs 72h 不一致。

**规避**:
- 本 Task **禁** AppSettings 字段增量(§ 6 不做)
- § 8 验收 4 字段计数防护
- TASK-108 文档 + 本 Task 文档双向引用同名约束

### 风险 5:ProjectStore 范围前移与 TASK-204 边界混淆(D4)

**症状**:Codex 在本 Task 顺手实现 SQLite store / ChatStore / migration 脚本。

**规避**:
- § 1 上下文明示前移
- § 6 不做"❌ SQLite / 持久化 store"硬列
- code review 检查 `adapters/storage/` 内仅有 `in_memory_project_store.py`

### 风险 6:project_id 语义混用(D6)

**症状**:开发者看 `Project.id` 是 `str`,误以为可以放 hash;后续 TASK-203 / 205 接力,有的地方期望 UUID 有的期望 hash,语义错乱。

**规避**:
- § 7.4 `create_upload_record` 内 `str(uuid.uuid4())`
- § 7.10.2 单测 `test_create_upload_record_generates_uuid_and_creates_pending` 断言 UUID4 格式
- § 7.10.4 `test_post_upload_uuid_format_is_uuid4` 端到端断言
- D6 决策日志写硬"重复上传同一 zip → 不复用 project_id"

### 风险 7:`.mat` parser 不存在 Codex 顺手实现(D7)

**症状**:Codex 看到 `Project.mat_files: list[MatMetadata]` 必填,自动写 `MatReader` → 拖范围 + 引入 scipy.io 依赖。

**规避**:
- § 6 不做"❌ .mat 文件深度解析"
- § 7.4 `_run_parse_sync` 内 `mat_files=[]` 硬填
- § 8 验收 7 `ls adapters/parser/mat_reader.py` 应不存在
- D7 决策日志:"`Project.mat_files` 字段是 v0.1 占位"

### 风险 8:`safe_extract` 失败后 dest_dir 未清理

**症状**:Codex 创建 `project_dir.mkdir()` 后调 `safe_extract`,失败抛异常,半解压目录残留。

**规避**:
- § 7.4 `UploadService.process` 异常分支调 `_cleanup_project_dir`
- § 7.10.2 `test_process_cleans_up_project_dir_on_failure` 单测断言
- CleanupWorker 兜底:即便 process 清理失败,24h 后扫到

### 风险 9:BackgroundTask 抛异常但项目没标记 failed

**症状**:`process` 内出现未捕获异常(如 `os.makedirs` 权限错误),FastAPI 默默吞掉,GET /status 永远 `parsing`。

**规避**:
- § 7.4 `process` 顶层 `except Exception` 兜底 + `mark_failed("internal_error")`
- § 7.10.2 `test_process_unexpected_exception_marks_failed_internal_error` 注入 RuntimeError 验证

### 风险 10:cleanup 删除正在解析的目录

**症状**:用户刚上传(`created_at` 刚刚),cleanup 不会扫到;但若 ttl_hours 配置错(如 0.001),会扫到正在解析的目录。

**规避**:
- TTL 来自 `upload_ttl_hours` 默认 24(D8),配置错风险低
- `CleanupWorker.run_once` 内**先**删磁盘**再**删 store(已设计)
- Phase 2 可加"status==parsing 时跳过删除"逻辑

### 风险 11(强化):日志记录原始文件名 / 路径 / 异常字符串 / 上传内容(隐私硬约束)

**症状 A**:Codex 写 `logger.error("upload failed: {}", exc)` 把 `str(exc)` 落日志,而异常 message 可能含 `info.filename` / 文件内容片段。

**症状 B**:Codex 用 `logger.exception(...)`,自动落 traceback,实际等同于落 `str(exc)`。

**规避**:
- § 7.4 `process` 异常分支**仅** `logger.error("...exception={}", type(exc).__name__)`
- § 7.5 `CleanupWorker` 同上,**禁** `logger.exception`
- § 8 验收 11 grep `logger\.exception` 全工程空
- § 7.10.2 `test_process_logger_never_uses_exception_method` 用 grep 源码兜底
- § 7.10.3 `test_run_once_logger_never_uses_exception_method` 同上

### 风险 12:app dependency override / `get_settings.cache_clear()` 测试泄漏

**症状**:本 Task 测试加 `app.dependency_overrides[get_upload_service] = ...` 后忘 clear。

**规避**:
- 复用 TASK-201 已建 `tests/api/conftest.py` autouse fixture(自动 clear)
- 测试代码**不**手动 clear
- conftest fixture 内 leak warning 已落 stderr

### 风险 13:cleanup task shutdown 未 cancel/await(TASK-201 风险 9 同类)

**症状**:lifespan yield 后未 cancel cleanup task,uvicorn 退出时 asyncio 报 `Task was destroyed but it is pending`。

**规避**:
- § 7.9 lifespan 用 `AsyncExitStack.push_async_callback(_shutdown_cleanup)`
- `_shutdown_cleanup` 内 `cancel() + await + except CancelledError`
- 单测在 § 7.10.3 `test_run_forever_cancellation_propagates_cleanly` 验证

### 风险 14:uvicorn 真启动验收误用多 worker(对应风险 1 验收侧)

**症状**:文档没强调 `--workers 1`,Codex 在 § 8 验收 21-23 复制 uvicorn 命令时漏掉 / 加 `--workers 4`。

**规避**:
- § 8 验收 21 命令明示不加 `--workers`(默认就是 1)
- 风险 1 + 风险 14 双重提醒

### 风险 15:重复实现 TASK-104 zip 安全矩阵

**症状**:Codex 在 `test_upload.py` 重复实现 zip slip / bomb 构造逻辑。

**规避**:
- § 6 不做"❌ 新增 zip 安全矩阵测试"
- § 7.11 表格列明"复用 TASK-104 已有 fixture"
- 本 Task 集成测试**只**断言端到端链路

### 风险 16:文件超过 300 行未拆分(04 § 4)

**症状**:`tests/api/test_upload.py` 估算 270 行接近上限。

**规避**:
- 实施时若接近 280 行,优先精简
- 真超 290 行,按"happy path + size + adversarial" 拆为 `test_upload_happy.py` / `test_upload_adversarial.py`
- 不强拆,弹性边界(04 § 4 是软约束)

### 风险 17(新增,P0-2):async background task 内不得直接执行同步重活

**症状**:Codex 看 `safe_extract` / `classify_files` / parsers 都是同步函数,在 `async def process` 内直接调用,event loop 被阻塞 — 整个 uvicorn 在解析期间(几秒到几十秒)无法处理任何其他请求,包括 GET /status 轮询。

**根因**:Starlette 仅对**同步** endpoint / background task 自动放线程池;async 函数内的阻塞代码会在 event loop 上执行。

**规避**:
- § 7.4 `process` 调 `await asyncio.to_thread(self._run_parse_sync, ...)`
- `_run_parse_sync` 是同步方法,内含全部 extract / classify / parse / dep_analyze
- § 8 验收 15 grep `asyncio.to_thread` 应命中
- § 7.10.2 `test_process_uses_to_thread_for_sync_parsers` mock `asyncio.to_thread` 断言被调用
- D13 决策日志写硬

### 风险 18(新增,补强 1):用户 filename 未清洗污染 store / 前端

**症状**:Codex 在 route 直接 `name = file.filename or "uploaded.zip"`,multipart filename 可能含路径片段 / 控制字符 / 超长字符串,落入 store → GET /status 返回 → 污染前端展示 / 日志 / DB(TASK-204 持久化后)。

**规避**:
- § 7.4 `_sanitize_filename(raw)` 函数清洗:`Path(...).name` 取末段 + 去控制字符 + 截断 100
- § 7.6 route 调用 `name = _sanitize_filename(file.filename)`
- § 7.10.2 共 5 个 sanitize 单测
- D15 决策日志

### 风险 19(新增,D14 配套):任何 ParseError → project failed,刻意偏离 04 § 8.4 失败隔离

**症状**:Codex 看 04 § 8.4 "单个文件解析失败不能让整个工程失败,失败隔离",在 `process` 内对 `SlxParseError` / `MParseError` 单独 try/except + skip,继续构造 Project → 与本 Task 设计冲突(`Project` 无 `parse_warnings` 字段)。

**规避**:
- § 1 上下文明示"刻意收窄 04 § 8.4"
- § 6 不做"❌ partial project / `ready_with_warnings` 第四态(D14)"
- § 7.4 `_run_parse_sync` 内 parse loop **不** try/except,异常自然抛出
- § 7.10.2 两个 parse error 单测锁定行为
- D14 决策日志写硬"本 Task 阶段性例外;失败隔离 + warnings 展示归 TASK-203"

---

## 决策日志

本 Task 在写作 + GPT 一审 + GPT 二审过程产生的 **16 个决策点**。

### D1 — `ProjectStatus = Literal["parsing", "ready", "failed"]`(不用 Enum)

**理由**:
- 这是上传流程的**运行态状态**,不是工程类型分类(`ProjectType` 是分类用 Enum 合适)
- `Literal` 只用于 API schema / store record 的有限状态值
- 暂不抽业务 Enum,避免 3 个短生命周期状态增加 `.value` / 序列化心智负担
- `ready` 明确仅表示"上传 + 解析 + 落库完成",**不**表示导览 / TeachingUnit 完成
- `failed` 明确仅暴露 ERROR_MAP machine code,不暴露原始异常 / 文件名片段 / 文件内容

### D2 — 配置零增量,清理 TTL 复用 `upload_ttl_hours`

**理由**:
- `app/config.py::AppSettings` 已有 `upload_ttl_hours: int = 24`(实地 dump 确认)
- 新增 `cleanup_ttl_hours` 会造成双来源冲突(风险 4)
- 扫描周期 `interval_minutes` 走 `CleanupWorker(interval_minutes=60)` 构造默认值,**不入** AppSettings
- 本 Task **不修改** `app/config.py`(§ 8 验收 4 零增量验证)

### D3 — TestClient 同步行为 = 测试确定性,不代表生产语义

**理由**:
- Starlette `TestClient` 在 `with` 块内等待 BackgroundTask 完成(GitHub Kludex/starlette#533 锁定行为)
- FastAPI 文档明示生产语义"先响应,后任务"
- 测试用 TestClient 同步行为获得确定性(无需 sleep / poll)
- 真启动验收允许首次 polling 看到 `parsing`,体现生产语义
- `test_testclient_waits_for_background_task` + `test_get_status_returns_parsing_initially_with_controlled_fake_event`(用 `asyncio.Event` 控制)双向锁定

### D4 — `ProjectStore` 临时前移到 TASK-202,InMemory only

**理由**:
- 03 索引明示 store 归 TASK-204,但 TASK-202 `GET /status` 需要 store 接口
- TASK-204 持久化前,InMemory 进程内 dict 是合理桥接
- 接口 `ProjectStore` 定型(7 方法),TASK-204 直接替换实现(零接口改动)
- 本 Task **不**实现 SQLite / ChatStore / migration
- TASK-204 接管后,本 Task `InMemoryProjectStore` 仍保留供测试夹具用

### D5 — 单 worker 是本 Task 硬契约

**理由**:
- `InMemoryProjectStore` 进程内 dict,不跨 worker
- CleanupWorker 每个 worker 各自启动(重复扫描浪费 / 删除竞态)
- MCS 阶段单 worker 足够(预期上传频率 < 1/s)
- TASK-204 持久化后视 PM 决定放开
- `api/README.md` + § 1 上下文 + § 8 验收 21 三处明示

### D6 — `project_id = str(uuid.uuid4())`,不用 hash / 短码

**理由**:
- UUID4:零碰撞 / 零状态 / 零依赖
- 短码:URL 短但需 collision check + retry,并发复杂
- hash 去重:语义争议 + 失败状态混乱;留 Phase 2
- 重复上传同一 zip:**不**复用 project_id,每次生成新 uuid
- UUID4 冲突 3 次重试由 `create_upload_record` 兜底(几乎不可能触发)

### D7 — `.mat` 缺口处理:`mat_files=[]` 占位,**不**开 MatReader

**理由**:
- 实地 dump 确认 `adapters/parser/mat_reader.py` 不存在
- 02 § 2 数据流写了 `.mat → MatReader.parse() → MatMetadata`,但 Task 链未到
- 本 Task 范围严格收窄,scipy.io 依赖 + MatReader 实现归未来独立 Task
- `Project.mat_files: list[MatMetadata]` 字段是 v0.1 占位,接受空 list
- `.mat` 文件仍出现在 `Project.files`(FileInfo 元信息),仅不深度解析

### D8 — cleanup TTL 复用 `upload_ttl_hours`(与 D2 互锁)

**理由**:见 D2。本条强调"TTL 字段名"语义统一(都叫 `upload_ttl_hours`,不区分 cleanup / upload TTL)。

### D9 — 同步路径 size 双道防线 + 严格顺序(P0-1)

**理由**:
- starlette `UploadFile.size` 在 Content-Length 表头存在时填充,chunked 时 None
- 第一道:`check_declared_size(file.size)`,**不读 body 即拒**(防 DoS)
- 第二道:`check_actual_size(len(zip_bytes))`,read 后兜底,覆盖 size=None
- 严格顺序:declared check → await read → actual check;**禁止颠倒**
- 两道都抛 `ProjectTooLargeError` → 413
- § 8 验收 14 用 Python 脚本断言文件内三个字面量的位置顺序

### D10 — POST /upload **不**预校验 `.zip` 后缀

**理由**:
- 任何"格式不对"统一由 `safe_extract` 抛 `ZipBombError("zip 格式非法,无法读取压缩包")`
- 客户端 polling 时看 `failed + error_code=zip_bomb`
- 优点:不扩 ERROR_MAP / route 同步路径简洁
- 缺点:用户上传 `.docx` 要等几秒 polling 才知失败
- MCS UX 可接受,Phase 2 视用户反馈加 `InvalidUploadFileError` leaf

### D11 — 删磁盘先 + 删 store 后(cleanup 顺序)

**理由**:
- 失败磁盘删 → store 仍有 entry → 下次 cleanup 再扫(自愈)
- 成功磁盘删 → store 仍存 → GET /status 返回 ready 但取 project 时文件失踪;**但** cleanup 后 store delete 立即跟上,窗口期极短
- `shutil.rmtree(..., ignore_errors=True)` 避免单文件 perm denied 阻塞整批
- 反过来"先删 store 后删磁盘":store 删了但磁盘失败 → 孤儿目录无追踪

### D12 — UploadService 严格不 import adapters/(GPT 一审强调)

**理由**:
- 02 § 7 分层:features 只依赖 core 接口,不直接 import adapters
- 构造函数注入 `extractor / classifier / slx_parser / m_parser / dependency_analyzer`
- `extractor` 用 `partial(safe_extract, config=settings)` 在 DI 层 curry,feature 不知道 AppSettings
- `slx_parser / m_parser` 走 `core/interfaces/parser.py::SlxParser / MParser` ABC
- `classifier / dependency_analyzer` 用 Callable 类型别名(纯函数无状态,无需 ABC)
- 零临时例外
- § 8 验收 8 grep 应空输出

### D13 — async process 用 `asyncio.to_thread` 桥接同步重活(GPT 二审 P0-2)

**理由**:
- `process` 是 async 方法(被 `BackgroundTasks.add_task` 调度,FastAPI 自动 await)
- `safe_extract` / `classify_files` / `SlxParserImpl.parse` / `MParserImpl.parse` / `analyze_dependencies` 全部同步函数
- Starlette 仅对 *同步* endpoint / background task 自动放线程池;async 函数内同步代码阻塞 event loop
- 解决:`await asyncio.to_thread(self._run_parse_sync, ...)` 把同步重活丢线程池
- `_run_parse_sync` 是同步方法,**不调任何 async**(避免跨线程 event loop 错误)
- async 层只做 mkdir + store 更新 + 异常翻译 + cleanup
- 风险 17 详述;§ 7.10.2 `test_process_uses_to_thread_for_sync_parsers` mock 锁定

### D14 — 任何 ParseError → project failed,刻意偏离 04 § 8.4 失败隔离(PM 拍板 A)

**理由**:
- TASK-202 是首个用户端 API,`ProjectStatus` 三态简单清晰
- `Project` v0.1 9 字段冻结,无 `parse_warnings` 字段承接失败信息
- 实现 partial project 需引入 `ready_with_warnings` 第四态 + 字段扩展,复杂度高
- 失败隔离 + warnings 展示路径已有:TASK-107 ProjectGraph 已建 `unresolved_symbols`,TASK-203 导览生成时基于此做容错展示
- 本 Task 接受"任何 .m / .slx 解析失败 → 整个 project failed"的简化语义
- Codex 实施时**禁**在 `_run_parse_sync` 的 parse loop 内 try/except 跳过失败文件
- 风险 19 详述;§ 7.10.2 两个 parse error 单测锁定

### D15 — filename 清洗(GPT 二审补强 1)

**理由**:
- multipart filename 来自用户,不可信
- 风险:路径片段(`../`)/ 控制字符 / 超长字符串污染 store / 前端 / 日志
- `_sanitize_filename(raw)` 私有函数:`Path(raw.replace("\\", "/")).name` → 控制字符 strip → 截断 100 字符 → fallback `"uploaded.zip"`
- route 调 `_sanitize_filename(file.filename)` 后再传 service
- § 7.10.2 共 5 个 sanitize 单测
- 风险 18 详述

### D16 — `ProjectStatusRecord.created_at` 与 `Project.created_at` 语义分离(GPT 二审补强 2)

**理由**:
- `ProjectStatusRecord.created_at` = 上传接收时间(POST /upload 落 store 那一刻)
- `Project.created_at` = 解析完成时间(BackgroundTask 内构造 Project 那一刻)
- 两者必然不同(差几秒到几十秒,取决于解析耗时)
- 前端展示"上传时间"应读 `ProjectStatusRecord.created_at`(GET /status 暴露)
- 本 Task **不**合并字段(避免改 Project dataclass,违反 D1)
- TASK-204 持久化后可视需求统一;MCS 阶段语义清晰更重要
- § 7.1 docstring + § 7.7 schema 双向注释

---

## Checklist

实施前自查:

- [ ] 已读 18 个项目文档 + task-201 v2 + 决策 01-10 + 反例 1-18
- [ ] 已实地核查 dump 上游产物(safe_extract / analyze_dependencies / classify_files 签名 / AppSettings 字段 / Project dataclass / exceptions 树 / tests/api/conftest.py)
- [ ] 已确认 `adapters/parser/mat_reader.py` **不**存在,本 Task **不**实现(D7)
- [ ] 已确认 `app/config.py` 字段计数,本 Task 实施后**不**变(D2 / D8 / 风险 4 / § 8 验收 4)
- [ ] 已确认 `core/domain/project.py::Project` 9 字段,本 Task **不**改(D1 / § 8 验收 5)
- [ ] 已确认 `api/middleware/error_handler.py` 8-handler,本 Task **不**加(§ 8 验收 6)
- [ ] 已确认单 worker 限制(D5 / 风险 1 / 风险 14 / § 8 验收 21)
- [ ] 已理解 TestClient 同步 vs 生产异步语义差异(D3 / 风险 2)
- [ ] 已理解 route 不 try/except + BackgroundTask 必 try/except 两个边界(风险 3 / § 7.4 / § 7.6)
- [ ] 已理解 size 严格顺序:declared check → await read → actual check(D9 / P0-1 / § 8 验收 14)
- [ ] 已理解 `asyncio.to_thread` 桥接同步重活,**不**在 async 内直接 await 同步函数(D13 / P0-2 / 风险 17 / § 8 验收 15)
- [ ] 已理解 D14:任何 `ParseError` → project failed,**不**做单文件失败隔离(风险 19)
- [ ] 已理解日志隐私硬约束(metadata only / 不 str(exc) / 不文件名 / **禁** `logger.exception` / 风险 11 / § 8 验收 11)
- [ ] 已理解 filename 清洗(D15 / 风险 18)
- [ ] 已理解 `Project.created_at` vs `ProjectStatusRecord.created_at` 语义分离(D16)

完工前自查:

- [ ] § 8 验收 1-25 全过
- [ ] Commit subject 单行无 body(反例 17)
- [ ] 全部文件 ≤ 300 行(04 § 4)
- [ ] 完工报告含 git 三件套(决策 08:`git status` / `git log --oneline main..HEAD` / `git push` 完整 stdout)
- [ ] 提 PR(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)
- [ ] `python -m ruff format --check .` 加跑(反例 11)
- [ ] `pip check` 验证依赖兼容
- [ ] 03 索引状态行 + Week 2 进度条字节级 Python 修改(决策 08 + 反例 9;**先 grep 实际字面再构造 bytes**)

---

## 后续 Task 接力点

- **TASK-203(导览生成)**:消费 `get_project_store()` dependency,从 store 取 `Project` 调 LLM;基于 `unresolved_symbols`(TASK-107 已建)做容错展示(D14 解锁点)
- **TASK-204(SQLite store)**:实现 `SqliteProjectStore(ProjectStore)`,替换 `app.state.project_store`;补 `ChatStore`;放开多 worker 限制(D5 解锁)
- **TASK-205(粗 RAG 问答)**:消费 store 取 Project + 关键词检索 + LLM
- **TASK-206(错误处理扩展)**:在 `api/middleware/error_handler.py` 追加 LLMError / ParseError / Quota / Evidence 9 handler,**不**改本 Task 锁定的 upload / status response shape
- **TASK-207(ProjectOverview Schema)**:基于 `Project` 做 schema 定型
- **TASK-301(嵌入适配器)**:与 store 无关
- **Phase 2 候选**:
  - `MatReader`(D7 解锁)
  - 流式上传 + `safe_extract` 改流式签名(D9 取代,需宪法修订)
  - 用户 + 限流(替代单 worker 限制)
  - `InvalidUploadFileError` leaf(D10 解锁,POST 同步预校验后缀)
  - 细粒度 per-id store lock(D4 取代全局锁)
