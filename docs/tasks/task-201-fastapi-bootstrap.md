# TASK-201: FastAPI 框架搭建 + 健康检查 + 最小错误处理闭环

## 状态

🔲 未开始

---

## 上下文

这是 Week 2 的第一个 Task,也是项目第一个真正建立 API 后端的 Task。

`docs/03_TASK_INDEX.md` Week 2 段第一行验收点已写"FastAPI 框架搭建 + 健康检查"。但实际范围比 v1 草稿(单纯"骨架 + 占位 MxaError handler")**扩张到正式承担 API 错误处理的最小闭环**:本 Task 实现 8 个 exception handler(5 个 leaf + 2 个 base fallback + 1 个 final fallback)+ 锁定响应体 shape,TASK-206 接管剩余的 LLMError / ParseError / Quota / Evidence handler 以及 404/422 中文化和 4 个真实工程 E2E 测试。

**审批级别**:本 Task 已走 GPT 一审 1 轮 + 二审 1 轮(归属"API 层首次定型"类,符合宪法 § 5 二审标准:首次定型跨多个下游 Task 会复制的工程模式)。本 Task 是项目第一个由架构师**预先把审批级别评估错(凭"基建 Task 类比 task-108"降级为无审)**的 Task,详见决策 09 反例 18(随本 Task 前置的 chore PR 入仓)。

本 Task 实现三件事:

1. **`api/main.py`** — FastAPI app 工厂 + lifespan 钩子 + 中间件 / 路由挂载点,作为后续 TASK-202 ~ 205 全部 HTTP 端点的基座
2. **`api/routes/health.py`** — `GET /health` 健康检查端点(实为 readiness check:验证 app 配置可加载、路由可用,**不**检查 DeepSeek 网络连通性)
3. **`api/middleware/error_handler.py`** — **最小可用 ERROR_MAP**(8 个 handler),正式承担 TASK-202 上传错误的 HTTP 语义翻译。**响应体 shape `{"error", "message"}` 由本 Task 锁定**,TASK-206 后续只**追加条目**,**不改 shape**

### 与 TASK-206(错误处理 + 中文化)的范围边界

| 范围 | TASK-201(本 Task) | TASK-206 |
|---|---|---|
| FastAPI app + lifespan + 路由挂载 | ✅ 建 | — |
| **响应体 shape `{"error", "message"}`** | ✅ **锁定** | 沿用,不改 |
| `ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError` handler | ✅ 实现(400) | 不动 |
| `ProjectNotFoundError` handler | ✅ 实现(404) | 不动 |
| `ProjectTooLargeError` handler | ✅ 实现(413,**动态读 settings**) | 不动 |
| `UploadError` / `ProjectError` base fallback handler | ✅ 实现(400,防漏注册) | 不动 |
| `MxaError` final fallback handler | ✅ 实现(500) | 不动 |
| `LLMAuthError` / `LLMQuotaError` / `LLMRateLimitError` / `LLMTimeoutError` / `LLMServerError` handler | ❌ 不做 | ✅ 实现 |
| `SlxParseError` / `MParseError` handler | ❌ 不做 | ✅ 实现 |
| `QuotaExhaustedError` handler | ❌ 不做 | ✅ 实现 |
| `EvidenceMissingError` handler | ❌ 不做 | ✅ 实现(降级为"不确定"答案,非 HTTP 错误) |
| 404 / 422 默认文案中文化 | ❌ 不做(沿用 FastAPI 默认英文) | ✅ 实现 |
| 4 个真实工程端到端中文化测试 | ❌ 不做 | ✅ 实现 |
| 健康检查端点 | ✅ 建 | — |
| 后续 route 共用的 DI 容器(`get_settings()`) | ✅ 建 | — |
| `tests/api/conftest.py` autouse 清理 fixture | ✅ 建 | 沿用,可扩展 |

### 范围扩张说明(v1 → v2)

v1 草稿原计划"占位 MxaError handler → 500",TASK-206 再实现完整 ERROR_MAP。GPT 一审 + 二审一致指出:

1. **语义问题**:TASK-202 / 203 / 204 / 205 全部在 TASK-206 之前实施。如 201 只兜底 MxaError → 500,上传安全错误(ZipBomb / ZipSlip / FileTypeNotAllowed)会被翻译为 500,违反 Week 2 验收语义"上传沙箱**能拒绝** zip bomb / zip slip / 非白名单"(拒绝应为 4xx,不是 5xx)
2. **可复制性问题**:若 201 不映射,202 实施时只能在 route 里写临时 `try/except` 拼 4xx 响应,206 接管时全部要重构;同样模式会被 203/205 复制
3. **shape 问题**:占位 handler 只兜 MxaError,响应体 shape 未锁。202 / 203 实施时各自设计 shape,206 接管时改 shape = 破坏性变更

PM 拍板方案 B:TASK-201 正式承担 minimal ERROR_MAP,8 个 handler 覆盖 UploadError + ProjectError 树。**这不是临时多映射几个异常,是 201 正式定型 API 错误处理的最小闭环**。

### 上下游依赖

- **上游**(均已合并):
  - TASK-001(项目骨架):`api/` 4 个占位文件已建
  - TASK-002(开发环境 + CI):`Makefile` / `pyproject.toml` / CI 就位
  - TASK-101(异常体系):`core/domain/exceptions.py` 16 个异常类就位
  - TASK-104(沙箱):`safe_extract` 抛 `ZipBombError` / `ZipSlipError` / `FileTypeNotAllowedError` / `ProjectTooLargeError`
  - TASK-106(DeepSeek TextProvider):`loguru` 已加入 `requirements.txt`
  - TASK-108(配置层):`AppSettings` 16 字段(`max_upload_size_mb=50` / `max_files_per_project=200` 默认值给 `ProjectTooLargeError` 文案动态消费)
  - **chore PR(随本 Task 前置)**:决策 09 反例 18 入仓 + 03 索引 Week 0 进度条修复历史欠账
- **下游**:
  - **TASK-202**:**直接消费**本 Task 5 leaf + 2 base fallback。**禁止**在 route 内 `try/except` 翻译业务异常(详见风险 11)
  - **TASK-203 / 205**:消费 `get_settings()` 与 error_handler 挂载点
  - **TASK-206**:**追加**剩余 9 项 handler,**不改** TASK-201 锁定的响应体 shape
  - **TASK-405**:消费 production `uvicorn api.main:app` 命令

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001 / 002 / 101 / 104 / 106 / 108
- ✅ chore PR(前置):反例 18 入仓 + Week 0 进度条修复

### 实地核查记录(2026-06-04,by 第九任架构师 via Codex dump)

- `requirements.txt` 当前 **4 行**:1 行 comment + `pydantic-settings==2.6.1` / `loguru==0.7.2` / `openai==1.55.3`。本 Task **追加 2 行 runtime**(`fastapi==0.115.4` + `uvicorn[standard]==0.32.0`)
- `requirements-dev.txt` 当前 6 行(`pytest==8.3.3` / `pytest-asyncio==0.24.0` / `ruff==0.7.0` / `mypy==1.13.0` / `pytest-mock==3.14.0` + `-r requirements.txt`)。本 Task **追加 1 行 dev**(`httpx==0.27.2`,详见风险 5)
- `app/config.py` `AppSettings` 含 **16 字段**,`extra="ignore"` 已设
- `core/domain/exceptions.py` 含 16 个异常类。**关键契约**:`ProjectTooLargeError(ProjectError)` 继承自 `ProjectError`,**不是** `UploadError`(TASK-202 实施时需 `except (UploadError, ProjectError)` 联合捕获,但本 Task handler 注册时 leaf 即可覆盖,无需特殊处理)
- `Makefile` 当前 `type-check` = `mypy core/ adapters/ features/`,**本 Task 改为** `mypy core/ adapters/ features/ api/`(详见 mypy 配置变更段)
- `.github/workflows/ci.yml` 当前 `Type check (mypy)` 步骤 `run: mypy core/ adapters/ features/`,**本 Task 同步改**
- `pyproject.toml`:`name = "mxa-tutor"`,`version = "0.0.1"`,`description = "工科仿真 AI 助教 — MATLAB/Simulink 工程导览与智能问答"`(em-dash `—` U+2014,本 Task `api/main.py` FastAPI description **从 pyproject.toml 复制**,不凭键盘输入)
- `pyproject.toml` `[tool.mypy]` `strict = false` / `disallow_untyped_defs = false`;本 Task **可能**追加 `[[tool.mypy.overrides]]` 块(实施时实测决定,见 mypy 配置变更段)
- `tests/api/` 目录已存在(空)。`tests/api/__init__.py` 是否存在 Codex 实施前 `find tests/api -type f` 自核查
- `api/` 4 个占位文件:`__init__.py`(0 字节)/ `README.md`(81 字节)/ `middleware/__init__.py`(0 字节)/ `routes/__init__.py`(0 字节)
- 02 § 9 错误处理表 14 行:本 Task ERROR_MAP 8 行的文案与 02 § 9 对齐(无尾句号风格统一);`FileTypeNotAllowedError` 文案因 02 旧白名单(6 扩展名)与 TASK-104 实际 `ALLOW_EXTS`(更广)漂移而**改写**为概括性描述

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,特别 § 7 / § 8 / § 12)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,特别 § 3 / § 8 / § 9 错误处理表 / § 12 日志隐私)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,特别 § 3 / § 4 / § 6 / § 10 / § 11 / § 12 / § 13)
- `docs/decisions/20260601-05-*.md` / `20260601-07-*.md` / `20260602-08-*.md` / `20260603-09-*.md`(**特别反例 18**)/ `20260604-10-*.md`
- `docs/tasks/task-101-core-domain-and-interfaces.md`(异常类层级权威定义)
- `docs/tasks/task-104-zip-extract-and-classify.md`(`safe_extract` 抛 4 类 leaf 异常)
- `docs/tasks/task-108-bootstrap-app-config-layer.md`(`AppSettings` 16 字段)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件(11 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `api/main.py` | FastAPI app 工厂 + 模块级 `app = create_app()` + lifespan + settings 注入到 `register_error_handlers` | 70–110 |
| `api/dependencies.py` | DI 容器:`get_settings()` with `lru_cache(maxsize=1)` | 30–50 |
| `api/routes/health.py` | `GET /health`,`Annotated[T, Depends]` 写法 | 30–50 |
| `api/schemas/__init__.py` | 空文件 | — |
| `api/schemas/health.py` | `HealthResponse`(3 字段 + `ConfigDict(extra="forbid")`) | 30–40 |
| `api/middleware/error_handler.py` | **8-handler 表驱动 ERROR_MAP**,响应 shape 锁定 + 日志只记元数据 | 100–150 |
| `tests/api/__init__.py` | 空文件(若不存在) | — |
| `tests/api/conftest.py` | **autouse fixture**:测试前后清 `get_settings.cache_clear()` + `app.dependency_overrides.clear()` + leak detection | 30–50 |
| `tests/api/test_app.py` | app 工厂 / lifespan / lru_cache / `/openapi.json`(9 用例) | 100–140 |
| `tests/api/test_health.py` | `/health` 行为 + 404(4 用例) | 60–90 |
| `tests/api/test_error_handler.py` | ERROR_MAP 8 handler + precedence + shape lock + 日志隐私(12 用例) | 200–280 |

### 修改文件(6 个 + 03 索引)

- **`requirements.txt`** — 追加 2 行 runtime,不动现有 4 行
- **`requirements-dev.txt`** — 追加 1 行 dev(`httpx==0.27.2`),不动现有 6 行
- **`Makefile`** — `type-check` target 加入 `api/`
- **`.github/workflows/ci.yml`** — `Type check (mypy)` 步骤同步加入 `api/`
- **`pyproject.toml`** — **可能**追加 `[[tool.mypy.overrides]]` 块(`api.routes.*` 局部松绑),Codex 实测决定;若全量 `mypy api/` 通过则**不**加
- **`api/README.md`** — 覆盖写,5 模块职责 + 启动 + watchfiles polling 提示 + 测试 + 后续扩展点
- **`api/__init__.py`** / `api/middleware/__init__.py` / `api/routes/__init__.py` — 保持空文件
- **`docs/03_TASK_INDEX.md`** — 推 🔲 → 🔍,Week 2 进度条第 1 位 ⬜ → 🔍(字节级 Python + 实施前先 grep,详见风险 1)

### 不动文件

- `app/` / `core/` / `adapters/` / `features/`
- `scripts/` / `.env.example`
- `tests/conftest.py` / `tests/test_smoke.py` / `tests/__init__.py`
- 除 `03_TASK_INDEX.md` 外的所有 `docs/` 文件(决策 07 边界)
- 其他 Task 的代码与测试

### 新增依赖

**Runtime(2)**:`fastapi==0.115.4` + `uvicorn[standard]==0.32.0`

**Dev(1)**:`httpx==0.27.2`(显式 pin,详见风险 5)

### mypy 配置变更

`Makefile` `make type-check` 从 `mypy core/ adapters/ features/` 改为 `mypy core/ adapters/ features/ api/`,**且可能**在 `pyproject.toml` 追加:

```toml
[[tool.mypy.overrides]]
module = "api.routes.*"
ignore_errors = false
disallow_untyped_defs = false
warn_unused_ignores = false
```

实施流程:
1. 先尝试**全量** `make type-check`
2. 若全量通过 → **不**加 override → PR 描述明示"全量纳入"
3. 若 `api.routes.*` 产生 5+ silent error → 加上述 override 块 → PR 描述贴出具体 silent error 类型与数量
4. 若 `api.main` / `api.dependencies` / `api.middleware` / `api.schemas` 任一模块出现 silent error → **停手抛冲突给 PM**(本 Task 这四个模块必须严格通过)

---

## 范围(必须做)

- [ ] **前置确认**:chore PR 已合并到 main(`git log --oneline origin/main | grep "反例 18"` 应能看到 commit)
- [ ] 从 `main` 切分支 `task/TASK-201-fastapi-bootstrap`
- [ ] `source .venv/Scripts/activate`(Windows Git Bash;Linux 用 `source .venv/bin/activate`)
- [ ] **依赖结构理解**:`cat api/__init__.py api/middleware/__init__.py api/routes/__init__.py api/README.md requirements.txt requirements-dev.txt Makefile pyproject.toml .github/workflows/ci.yml` 看实际内容,与本文档"输入"段对照。任一不符停手抛冲突
- [ ] **本地装新依赖**:`pip install fastapi==0.115.4 'uvicorn[standard]==0.32.0' httpx==0.27.2`
- [ ] 追加 2 行到 `requirements.txt`
- [ ] 追加 1 行(`httpx==0.27.2`)到 `requirements-dev.txt`
- [ ] 改 `Makefile` `type-check` target 加入 `api/`
- [ ] 改 `.github/workflows/ci.yml` `Type check (mypy)` 步骤同步
- [ ] 建 `api/schemas/__init__.py` 空文件
- [ ] 建 `api/schemas/health.py`(§ 7.1,**含 `ConfigDict(extra="forbid")`**)
- [ ] 建 `api/dependencies.py`(§ 7.2)
- [ ] 建 `api/middleware/error_handler.py`(§ 7.3,**8 handler 表驱动**,**注释禁 TODO/FIXME/XXX**,**日志禁记 `str(exc)`**)
- [ ] 建 `api/routes/health.py`(§ 7.4,**`Annotated[T, Depends]` 写法**)
- [ ] 建 `api/main.py`(§ 7.5,**FastAPI description 从 pyproject.toml 复制**,**settings 注入到 register_error_handlers**)
- [ ] 覆盖写 `api/README.md`(§ 7.6,**含 watchfiles polling 提示**)
- [ ] 建 `tests/api/__init__.py`(若不存在)
- [ ] 建 `tests/api/conftest.py`(§ 7.7,**autouse fixture**)
- [ ] 建 `tests/api/test_app.py`(§ 7.8,9 用例)
- [ ] 建 `tests/api/test_health.py`(§ 7.9,4 用例)
- [ ] 建 `tests/api/test_error_handler.py`(§ 7.10,12 用例)
- [ ] 试运行 `make type-check`;若 `api.routes.*` 产生 5+ silent error 则加 `[[tool.mypy.overrides]]`,否则不加
- [ ] **本地全检**:`make check` 全绿
- [ ] **本地手动加跑** `python -m ruff format --check .`(决策 09 反例 11)
- [ ] **本地手动加跑** `pip check`(验证依赖兼容)
- [ ] **真启动 uvicorn 验收** /health 与 /openapi.json(详见验收 15)
- [ ] 改 `docs/03_TASK_INDEX.md`:推 🔲 → 🔍,Week 2 进度条第 1 位 ⬜ → 🔍(字节级 Python,**先 grep 实际字面**)
- [ ] 本 Task 最后一个 commit:`docs: mark TASK-201 as in-review in task index`
- [ ] 完工三件套(决策 08)
- [ ] 提 PR

---

## 不做(明确排除)

### 范围明确排除(TASK-206 接管)

- ❌ 不实现 `LLMError` 5 leaf handler
- ❌ 不实现 `ParseError` 2 leaf handler(`SlxParseError` / `MParseError`)
- ❌ 不实现 `QuotaExhaustedError` handler
- ❌ 不实现 `EvidenceMissingError` handler(降级语义,非 HTTP 错误)
- ❌ 不实现 4 个真实工程端到端中文化测试
- ❌ 不实现 404 / 422 默认文案中文化

### 工程范围明确排除

- ❌ 不实现 BackgroundTasks 真实异步任务
- ❌ 不实现请求体 Pydantic 校验
- ❌ 不实现认证 / 限流 / CORS middleware
- ❌ 不实现 OpenAPI 自定义文档(但 § 7.8 测试 `/openapi.json` 端点)
- ❌ 不实现版本号动态读取
- ❌ 不用 `httpx.AsyncClient` 作本 Task 测试客户端主路径(用 `TestClient`;**后续 Task 若测试函数本身需 `async def` 再局部引入 AsyncClient**,**不写永久禁用**)

### 修订上游契约范围排除

- ❌ 不修改 `core/domain/exceptions.py`
- ❌ 不新增 `MxaError` 子类
- ❌ 不在 `api/` 内定义新业务异常

---

## 接口契约

### 7.1 `api/schemas/health.py`

```python
"""健康检查端点的响应 schema。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """``GET /health`` 响应体。

    version 字段需与 ``pyproject.toml`` 的 ``[project].version`` 保持同步。
    本字段升级时需在同一 chore PR 中同时更新两处,**不**走运行时动态读取。

    ``extra="forbid"`` 锁定 schema 契约:任何额外字段都会触发 ``ValidationError``,
    防止未来不小心放进未声明的字段(例如调试信息泄漏)。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    version: str
    app_name: str
```

### 7.2 `api/dependencies.py`

```python
"""FastAPI 依赖注入容器。

所有需要 ``AppSettings`` 的 route handler 通过
``Annotated[AppSettings, Depends(get_settings)]`` 注入(FastAPI 0.115+ 偏好写法),
**不**在模块顶部全局实例化 ``settings = AppSettings()``。

``lru_cache(maxsize=1)`` 保证进程内单例语义。测试通过
``app.dependency_overrides[get_settings] = lambda: AppSettings(...)`` 替换;
``tests/api/conftest.py`` 已建 autouse fixture,每个测试前后自动调用
``get_settings.cache_clear()`` 与 ``app.dependency_overrides.clear()``,
**测试作者不需要手动管理缓存**。

**约束**:``get_settings()`` 只能加载配置,**不能**在内部创建 DeepSeek client、
数据库连接、临时目录清理器等有副作用资源。需要这些资源时,新建独立 dependency
(如 ``get_text_provider()`` / ``get_project_store()``)。
"""

from functools import lru_cache

from app.config import AppSettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """加载并返回单例 ``AppSettings``。"""
    return AppSettings()
```

### 7.3 `api/middleware/error_handler.py`

**目录路径保留**(`middleware/` 子目录),**但 docstring 与注释明确说明**:本模块实现的是 FastAPI **exception handler** 挂载点,**不是** ASGI middleware(`BaseHTTPMiddleware`)。后续 Task 若需要真正的 ASGI middleware(如 request ID 注入、CORS),应另建文件,不要塞到本文件。

```python
"""API 层异常 handler 挂载点(不是 ASGI middleware,命名沿用历史目录结构)。

本模块实现 minimal ERROR_MAP:8 个 handler,覆盖 ``UploadError`` /
``ProjectError`` 异常树 + ``MxaError`` final fallback。

响应体 shape ``{"error": "<machine_code>", "message": "<中文文案>"}`` 由本
Task 锁定。TASK-206 接管后只**追加**剩余 9 项 handler(``LLMError`` 5 子类 +
``ParseError`` 2 + ``Quota`` + ``Evidence``)及 404/422 中文化,**不改 shape**。

设计要点:
1. **handler precedence**:FastAPI 按 exception class MRO 查找最具体 handler。
   5 个 leaf handler 优先匹配,2 个 base fallback 兜底子类漏注册,
   ``MxaError`` final fallback 兜未知业务异常。
2. **日志隐私**(02 § 12):
   只记录异常**类名 / HTTP code / request path / method**,**不**记录
   ``str(exc)``(异常 message 可能含用户文件名 / 路径 / 工程片段)。
3. **``ProjectTooLargeError`` 文案动态化**:从 ``AppSettings`` 读
   ``max_upload_size_mb`` / ``max_files_per_project``,避免文案与配置漂移。
4. **``FileTypeNotAllowedError`` 文案不列扩展名**:02 § 9 旧文案列了 6 个扩展名,
   但 TASK-104 实际 ``ALLOW_EXTS`` 比那广得多(``.mdl`` / ``.mlx`` / ``.fig`` /
   ``.png`` / ``.svg`` / ``.pdf`` / ``.json`` / ``.yaml`` 等)。本 Task 文案使用
   概括性描述。完整白名单展示由 TASK-202 或 TASK-206 按 ``_zip_policy.py``
   统一生成。
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import AppSettings
from core.domain.exceptions import (
    FileTypeNotAllowedError,
    MxaError,
    ProjectError,
    ProjectNotFoundError,
    ProjectTooLargeError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)

# Type alias for FastAPI exception handlers
ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _log_error(request: Request, exc: Exception, status_code: int) -> None:
    """统一日志格式:只记录元数据,不记录异常 message。

    隐私约束(02 § 12 / 04 § 10):异常 ``args`` 可能含用户上传文件名 / 路径 /
    工程片段。本 handler 只记录 ``type(exc).__name__`` + HTTP context。
    完整堆栈调试由 loguru 默认 traceback 处理(开发环境),production 环境
    不输出 traceback(由 loguru sink 配置控制)。
    """
    logger.error(
        "API error: exception={} status={} path={} method={}",
        type(exc).__name__,
        status_code,
        request.url.path,
        request.method,
    )


def _make_handler(
    status_code: int,
    machine_code: str,
    message: str,
) -> ExceptionHandler:
    """工厂函数:为静态文案的异常构造 handler。"""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        _log_error(request, exc, status_code)
        return JSONResponse(
            status_code=status_code,
            content={"error": machine_code, "message": message},
        )

    return handler


def _make_project_too_large_handler(settings: AppSettings) -> ExceptionHandler:
    """``ProjectTooLargeError`` handler:文案动态读 settings。

    ``settings`` 通过 closure 捕获(``create_app()`` 内一次性注入),
    避免在 handler 内部调用 ``get_settings()`` 绕开测试 override。
    """

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        _log_error(request, exc, 413)
        message = (
            f"工程过大或文件太多,请压缩到 {settings.max_upload_size_mb}MB 以内"
            f"并减少到 {settings.max_files_per_project} 个文件以下后重新上传"
        )
        return JSONResponse(
            status_code=413,
            content={"error": "project_too_large", "message": message},
        )

    return handler


def register_error_handlers(app: FastAPI, settings: AppSettings) -> None:
    """注册 8 个 exception handler。

    注册顺序不影响 FastAPI 行为(FastAPI 按 MRO 查找最具体 handler),
    但本模块按"leaf -> base fallback -> final fallback"组织,便于 review。

    TASK-206 接管后,在本函数末尾**追加**剩余 9 项 handler 注册,
    **不改前 8 个**。
    """
    # ---- Leaf handlers (5) ----
    # UploadError tree
    app.add_exception_handler(
        ZipBombError,
        _make_handler(400, "zip_bomb", "压缩文件异常,请检查后重新上传"),
    )
    app.add_exception_handler(
        ZipSlipError,
        _make_handler(400, "zip_slip", "压缩包内含非法路径,请重新打包后上传"),
    )
    app.add_exception_handler(
        FileTypeNotAllowedError,
        _make_handler(
            400,
            "file_type_not_allowed",
            "包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试",
        ),
    )
    # ProjectError tree
    app.add_exception_handler(
        ProjectNotFoundError,
        _make_handler(
            404,
            "project_not_found",
            "没有找到这个工程,可能已过期或已被删除,请重新上传",
        ),
    )
    app.add_exception_handler(
        ProjectTooLargeError,
        _make_project_too_large_handler(settings),
    )

    # ---- Base fallback handlers (2) ----
    # 防 TASK-202/203/204/205 新增 UploadError / ProjectError 子类时
    # 漏注册 leaf handler 而掉到 MxaError 500
    app.add_exception_handler(
        UploadError,
        _make_handler(400, "upload_error", "上传文件有问题,请检查压缩包后重新上传"),
    )
    app.add_exception_handler(
        ProjectError,
        _make_handler(400, "project_error", "工程处理失败,请重新上传后再试"),
    )

    # ---- Final fallback handler (1) ----
    app.add_exception_handler(
        MxaError,
        _make_handler(500, "internal_error", "出了点问题,我们已经记录,稍后再试"),
    )
```

**HTTP code 总览**:

| 异常类 | HTTP code | machine code | 文案 |
|---|---:|---|---|
| `ZipBombError` | 400 | `zip_bomb` | 压缩文件异常,请检查后重新上传 |
| `ZipSlipError` | 400 | `zip_slip` | 压缩包内含非法路径,请重新打包后上传 |
| `FileTypeNotAllowedError` | 400 | `file_type_not_allowed` | 包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试 |
| `ProjectNotFoundError` | 404 | `project_not_found` | 没有找到这个工程,可能已过期或已被删除,请重新上传 |
| `ProjectTooLargeError` | 413 | `project_too_large` | 工程过大或文件太多,请压缩到 `{N}`MB 以内并减少到 `{M}` 个文件以下后重新上传 |
| `UploadError` (base) | 400 | `upload_error` | 上传文件有问题,请检查压缩包后重新上传 |
| `ProjectError` (base) | 400 | `project_error` | 工程处理失败,请重新上传后再试 |
| `MxaError` (final) | 500 | `internal_error` | 出了点问题,我们已经记录,稍后再试 |

### 7.4 `api/routes/health.py`

```python
"""健康检查端点。

实为 readiness check:验证 app 配置可加载、路由可用。**不**检查 DeepSeek 网络
连通性或数据库可达性(避免 ``/health`` 因外部依赖抖动而误报)。深度健康检查
由 TASK-405 部署阶段的独立监控系统覆盖。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_settings
from api.schemas.health import HealthResponse
from app.config import AppSettings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthResponse:
    """返回服务健康状态。

    本端点不真消费 ``settings``,仅示范 ``Annotated[T, Depends]`` DI 模式
    给后续 TASK-202 / 203 / 205 的 route handler 抄。
    """
    return HealthResponse(
        status="ok",
        version="0.0.1",
        app_name="mxa-tutor",
    )
```

### 7.5 `api/main.py`

```python
"""FastAPI app 工厂与模块级入口。

uvicorn 通过 ``uvicorn api.main:app`` 加载模块底部的 ``app`` 实例。

**lifespan 设计原则**(TASK-201 + 后续 Task 共同约束):
1. startup 只做轻量 fail-fast(本 Task:加载 ``AppSettings`` 验证 ``.env``)
2. 重任务用 ``BackgroundTasks`` 或 service 层异步初始化,**不**在 lifespan 内做
3. 未来 lifespan 一旦初始化真实资源(DB pool / 临时目录 / 后台清理 worker),
   必须用 ``AsyncExitStack`` 或显式 try/cleanup 保证"已初始化资源在 startup
   中途失败时也被清理"——**不能假设** ``yield`` 后 shutdown block 必然执行
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifecycle。

    startup:加载 ``AppSettings``(``.env`` 缺 ``DEEPSEEK_API_KEY`` 会立即抛
    ``ValidationError``,production 友好的 fail-fast)。

    shutdown:占位。本 Task 不初始化真实资源,无需清理。
    """
    settings = get_settings()
    logger.info(
        "Application startup: db_path={}, upload_dir={}",
        settings.db_path,
        settings.upload_dir,
    )
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """构造 FastAPI app 实例。

    工厂模式便于测试覆盖(``test_app.py`` 中调用此函数得到独立 app 实例)。

    description 字符串(含 em-dash ``—``)从 ``pyproject.toml`` 的
    ``[project].description`` 复制,保持字面一致。**不要凭键盘输入**
    (反例 11 同源教训:em-dash U+2014 与 ASCII hyphen-minus U+002D 看起来像)。
    """
    settings = get_settings()
    app = FastAPI(
        title="mxa-tutor",
        version="0.0.1",
        description="工科仿真 AI 助教 — MATLAB/Simulink 工程导览与智能问答",
        lifespan=lifespan,
    )
    register_error_handlers(app, settings)
    app.include_router(health_router)
    return app


# uvicorn 入口:``uvicorn api.main:app --reload --port 8000``
app = create_app()
```

### 7.6 `api/README.md` 内容

覆盖写整个文件,内容如下(下面用 4 个反引号包裹整段以避免与内部 3 反引号冲突):

````markdown
# api

FastAPI 后端。所有 HTTP 端点在此层装配,通过 feature service 调用 core / adapter,
不直接调 LLM(详见 `docs/02_ARCHITECTURE_OVERVIEW.md` § 3 目录结构 / § 7 API 分层约束)。

## 模块结构

- `main.py` — FastAPI app 工厂(`create_app()`)+ 模块级 `app` 实例 + lifespan 钩子
- `dependencies.py` — DI 容器,`get_settings()` 返回 `AppSettings` 单例
- `routes/health.py` — `GET /health` 健康检查端点(readiness check,不查外部依赖)
- `schemas/health.py` — `HealthResponse` Pydantic 响应模型(`extra="forbid"` 锁契约)
- `middleware/error_handler.py` — minimal ERROR_MAP(8 handler,响应体 shape `{"error", "message"}`);命名沿用历史目录,**实为 exception handler 挂载点**,不是 ASGI middleware

## 启动

开发模式(自动重载,端口 8000):

```bash
make dev
```

或直接:

```bash
uvicorn api.main:app --reload --port 8000
```

**Windows / OneDrive / 中文路径 / WSL 用户**:`uvicorn[standard]` 的 watchfiles 自动重载在某些环境下不稳定。如发现保存代码后 reload 不触发,临时设环境变量:

```bash
export WATCHFILES_FORCE_POLLING=true
uvicorn api.main:app --reload --port 8000
```

或直接关闭 reload 验证业务功能:

```bash
uvicorn api.main:app --port 8000
```

## 测试

```bash
pytest tests/api/ -v
```

## 后续 Task 扩展点

- TASK-202:在 `routes/upload.py` 实现上传 + 解析 API;**禁止**在 route 内 `try/except` 翻译业务异常(直接抛 `MxaError` 子类,让 ERROR_MAP 处理)
- TASK-203:在 `routes/overview.py` 实现导览端点
- TASK-205:在 `routes/chat.py` 实现问答端点
- TASK-206:在 `middleware/error_handler.py` **追加**剩余 9 项 handler(`LLMError` 5 子类 + `ParseError` 2 + `Quota` + `Evidence`)+ 404/422 中文化,**不改**本 Task 锁定的响应体 shape
````

### 7.7 `tests/api/conftest.py`

```python
"""tests/api 共享 fixture。

autouse 清理 fixture 防止以下污染:
1. ``get_settings()`` lru_cache 跨测试残留(测试 A monkeypatch 环境变量后
   测试 B 仍拿到 A 的 cached 实例)
2. ``app.dependency_overrides`` 跨测试残留
3. teardown 时检测 ``dependency_overrides`` leak,警告但不抛 AssertionError
   (避免翻转已通过测试状态)

测试作者**不需要**手动 ``cache_clear()`` / ``dependency_overrides.clear()``。
"""

from collections.abc import Iterator

import pytest

from api.dependencies import get_settings


@pytest.fixture(autouse=True)
def _isolate_test_state() -> Iterator[None]:
    """测试前后清理 ``get_settings`` 缓存 + ``dependency_overrides``。

    Yields:
        None: fixture 不返回值,仅做 setup / teardown。
    """
    # Setup
    get_settings.cache_clear()

    # Late import to avoid circular import at conftest load time
    from api.main import app

    app.dependency_overrides.clear()

    yield

    # Teardown: 显式清理 + leak detection
    get_settings.cache_clear()

    leaked = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    if leaked:
        import sys

        print(
            f"WARNING: test leaked dependency_overrides: {list(leaked.keys())}",
            file=sys.stderr,
        )
```

### 7.8 `tests/api/test_app.py` 测试矩阵

9 个测试用例(全部 `def test_xxx`,优先 `TestClient`):

| # | 测试名 | 验证 |
|---|---|---|
| 1 | `test_create_app_returns_fastapi_instance` | `create_app()` 返回 `FastAPI` 实例,`app.title == "mxa-tutor"` / `app.version == "0.0.1"` |
| 2 | `test_create_app_description_uses_em_dash` | `create_app().description` 与 `pyproject.toml` `[project].description` 完全相同(含 em-dash `—`);**通过 `tomllib.load` 读 pyproject 拿期望值,不在测试源码硬编码该字符串**(否则键盘输入错也测不出来) |
| 3 | `test_module_level_app_exists` | `from api.main import app` 能 import,`app.title == "mxa-tutor"` |
| 4 | `test_app_has_health_route` | `app.routes` 中存在 `/health` GET 路由 |
| 5 | `test_get_settings_returns_app_settings` | `get_settings()` 返回 `AppSettings` 实例(autouse fixture 已清缓存,monkeypatch 环境变量直接生效) |
| 6 | `test_get_settings_is_lru_cached` | 连续两次 `get_settings()` 返回 `is` 同一对象 |
| 7 | `test_lifespan_startup_runs_without_exception` | `with TestClient(app):` 触发 lifespan,不抛异常即通过 |
| 8 | `test_lifespan_fails_when_deepseek_api_key_missing` | monkeypatch 删 `DEEPSEEK_API_KEY`,`with TestClient(create_app()):` 抛异常;断言异常链中能定位到 `deepseek_api_key`(详见风险 6,允许任何包装类型) |
| 9 | `test_openapi_schema_includes_health` | `client.get("/openapi.json")` 返回 200,JSON 中 `paths["/health"]["get"]` 存在,`components/schemas/HealthResponse` 存在;**锁定 OpenAPI contract**,前端 / SDK / Postman 都依赖此 schema 生成 |

测试 2 详细示例(防键盘输入错):

```python
def test_create_app_description_uses_em_dash():
    import tomllib
    from pathlib import Path
    from api.main import create_app

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    expected = pyproject["project"]["description"]

    app = create_app()
    assert app.description == expected
    # 反证:em-dash 确实在 description 中(防 pyproject 与 main.py 都被改成 hyphen)
    assert "\u2014" in app.description  # em-dash U+2014
```

### 7.9 `tests/api/test_health.py` 测试矩阵

4 个测试用例(简化版,错误处理测试已分到 test_error_handler.py):

| # | 测试名 | 验证 |
|---|---|---|
| 1 | `test_get_health_returns_200_with_exact_body` | `client.get("/health")` 返回 200,body JSON 精确等于 `{"status": "ok", "version": "0.0.1", "app_name": "mxa-tutor"}`(用 `assert body == {...}` 而非 `HealthResponse(**body)`,后者会忽略额外字段) |
| 2 | `test_health_response_rejects_extra_field` | 直接构造 `HealthResponse(status="ok", version="0.0.1", app_name="mxa-tutor", extra="x")` 抛 `ValidationError`(验证 `extra="forbid"` 生效) |
| 3 | `test_health_response_schema_in_openapi` | `paths["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]` 指向 `#/components/schemas/HealthResponse` |
| 4 | `test_404_for_unknown_path` | `client.get("/nonexistent")` 返回 404,body 是 FastAPI 默认 `{"detail": "Not Found"}`(本 Task 不本地化) |

### 7.10 `tests/api/test_error_handler.py` 测试矩阵

12 个测试用例,验证 8 个 handler 行为 + shape lock + 日志隐私 + leaf precedence:

| # | 测试名 | 验证 |
|---|---|---|
| 1 | `test_zip_bomb_returns_400_with_locked_shape` | 注册端点抛 `ZipBombError`,断言 status=400,body 精确等于 `{"error": "zip_bomb", "message": "压缩文件异常,请检查后重新上传"}` |
| 2 | `test_zip_slip_returns_400_with_locked_shape` | 同上,`ZipSlipError`,`error=zip_slip` |
| 3 | `test_file_type_not_allowed_returns_400_with_locked_shape` | 同上,`FileTypeNotAllowedError`,`error=file_type_not_allowed`,文案不含具体扩展名(`assert ".m" not in body["message"]`) |
| 4 | `test_project_not_found_returns_404_with_locked_shape` | 同上,`ProjectNotFoundError`,status=404,`error=project_not_found` |
| 5 | `test_project_too_large_returns_413_with_dynamic_message` | 异常 `ProjectTooLargeError`,status=413,`error=project_too_large`;断言 `message` 中含 `f"{settings.max_upload_size_mb}MB"` 与 `f"{settings.max_files_per_project} 个文件"`(动态读 settings 验证) |
| 6 | `test_upload_error_base_fallback_returns_400` | 抛 `UploadError`(基类直接 raise),status=400,`error=upload_error` |
| 7 | `test_project_error_base_fallback_returns_400` | 抛 `ProjectError`,`error=project_error` |
| 8 | `test_mxa_error_final_fallback_returns_500` | 抛 `MxaError`,status=500,`error=internal_error` |
| 9 | `test_zip_bomb_leaf_takes_precedence_over_upload_base` | **关键测试**:抛 `ZipBombError`,断言 status=400 且 `error=zip_bomb`(精确 leaf 文案),**不**是 `upload_error`(防 leaf 被 base fallback 抢走) |
| 10 | `test_log_does_not_contain_exception_message` | 用 loguru capture 捕获日志,触发 `MxaError("sensitive-content-from-user")` 后,断言日志输出**不**含 `sensitive-content-from-user`(只含异常类名 / status / path / method) |
| 11 | `test_all_handlers_registered_after_create_app` | `create_app().exception_handlers` 含 8 个 key,**断言数量等于 8**,防未来漏注册 |
| 12 | `test_handler_response_does_not_leak_str_exc` | 触发 `ZipBombError("path/to/secret.zip")`,断言 response body `message` 字段不含 `"path/to/secret.zip"` |

测试 9 详细示例:

```python
def test_zip_bomb_leaf_takes_precedence_over_upload_base():
    from fastapi.testclient import TestClient
    from api.main import create_app
    from core.domain.exceptions import ZipBombError

    app = create_app()

    @app.get("/_trigger_zip_bomb")
    async def trigger() -> None:
        raise ZipBombError("test bomb")

    with TestClient(app) as client:
        response = client.get("/_trigger_zip_bomb")
        assert response.status_code == 400
        body = response.json()
        # 精确 leaf 文案
        assert body["error"] == "zip_bomb"
        assert "压缩文件异常" in body["message"]
        # 反证:base fallback 文案不应出现
        assert body["error"] != "upload_error"
        assert "上传文件有问题" not in body["message"]
```

测试 10 loguru capture 示例(Codex 实地调试时按 loguru 实际 API 调整):

```python
def test_log_does_not_contain_exception_message(caplog):
    import io
    from loguru import logger
    from fastapi.testclient import TestClient
    from api.main import create_app
    from core.domain.exceptions import MxaError

    # Redirect loguru output to capture buffer
    buf = io.StringIO()
    sink_id = logger.add(buf, level="ERROR")
    try:
        app = create_app()

        @app.get("/_trigger")
        async def trigger() -> None:
            raise MxaError("sensitive-content-from-user")

        with TestClient(app) as client:
            response = client.get("/_trigger")
            assert response.status_code == 500

        log_output = buf.getvalue()
        # 日志应含元数据
        assert "MxaError" in log_output
        assert "/_trigger" in log_output
        # 日志不应含异常 message
        assert "sensitive-content-from-user" not in log_output
    finally:
        logger.remove(sink_id)
```

---

## 验收标准

> **所有命令在 Git Bash + 已激活 `.venv` 内,在仓库根目录(`F:\mxa-tutor`)执行。**
> Codex 在 PR 描述里逐条勾选并贴每条命令的输出。
> 静态扫描类命令一律按决策 05 加 `--exclude-dir=".venv" --exclude-dir=".git"`。

### 1. 文件全部创建

```bash
ls api/main.py api/dependencies.py \
   api/routes/health.py \
   api/schemas/__init__.py api/schemas/health.py \
   api/middleware/error_handler.py \
   tests/api/conftest.py \
   tests/api/test_app.py tests/api/test_health.py tests/api/test_error_handler.py
```

10 个核心文件全部存在(`tests/api/__init__.py` 视实地是否已存在决定是否新建,单独验证)。

### 2. 不应被创建的文件确实没创建

```bash
ls api/routes/upload.py api/routes/overview.py api/routes/chat.py \
   api/middleware/auth.py api/middleware/rate_limit.py \
   api/middleware/cors.py \
   api/middleware/request_id.py \
   api/schemas/upload.py 2>&1
```

期望:全部 `No such file or directory`。

### 3. `requirements.txt` 已扩展且不破坏现有 4 行

```bash
cat requirements.txt
```

期望输出严格为:

```
# Runtime dependencies will be added per-task
pydantic-settings==2.6.1
loguru==0.7.2
openai==1.55.3
fastapi==0.115.4
uvicorn[standard]==0.32.0
```

### 4. `requirements-dev.txt` 已扩展且不破坏现有 6 行

```bash
cat requirements-dev.txt
```

期望末尾追加 `httpx==0.27.2`,其他 6 行不变。

### 5. `pip check` 验证依赖兼容

```bash
pip check
```

期望:`No broken requirements found.`

### 6. `app/` / `core/` / `adapters/` / `features/` 全部不动

```bash
git fetch origin main
git diff origin/main..HEAD --stat -- app/ core/ adapters/ features/
```

期望:无输出。

### 7. 不修改 `scripts` / `.env.example` / `tests/conftest.py` / `tests/test_smoke.py` / `tests/__init__.py`

```bash
git diff origin/main..HEAD --stat -- \
    scripts/ .env.example \
    tests/conftest.py tests/test_smoke.py tests/__init__.py
```

期望:无输出。

### 8. 单元测试全绿

```bash
pytest tests/api/ -v
```

期望:**25 个测试**(test_app.py 9 + test_health.py 4 + test_error_handler.py 12)全部通过,运行 < 10 秒。

### 9. 整套测试套件全绿

```bash
pytest -v --tb=short
```

期望:所有现有测试(TASK-101–108)+ 本 Task 25 个新测试全部通过。

### 10. lint 和 format check 全绿

```bash
make lint
```

期望:`ruff check .` 与 `ruff format --check .` 都 0 issues。

### 11. type-check 全绿(已纳入 `api/`)

```bash
make type-check
```

期望:`mypy core/ adapters/ features/ api/` 0 errors。**若 `api.routes.*` 产生 5+ silent error**(Codex 实地观察),允许在 `pyproject.toml` 加 `[[tool.mypy.overrides]] module = "api.routes.*"` 局部松绑;但 `api.main` / `api.dependencies` / `api.middleware` / `api.schemas` **必须严格通过**。Codex 在 PR 描述中说明是否启用 override 及理由。

### 12. hygiene check 全绿

```bash
bash scripts/check_repo_hygiene.sh
```

期望:6 项检查全 PASS。

### 13. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 14. 本地手动加跑 `python -m ruff format --check .`(决策 09 反例 11)

```bash
python -m ruff format --check .
```

期望:`X files already formatted`。

### 15. 健康检查端点 + OpenAPI 真启动跑通(inline env,无需 `.env`)

```bash
DEEPSEEK_API_KEY=fake-for-test uvicorn api.main:app --port 8001 &
UVICORN_PID=$!
trap 'kill $UVICORN_PID 2>/dev/null || true' EXIT
sleep 2

curl -sS http://127.0.0.1:8001/health
echo
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/openapi.json

kill $UVICORN_PID
trap - EXIT
```

期望:
- 第一个 curl 输出含 `"status":"ok"` + `"version":"0.0.1"` + `"app_name":"mxa-tutor"`
- 第二个 curl 输出 `200`

inline `DEEPSEEK_API_KEY=fake-for-test` 避免依赖本地 `.env`(其他人复现验收时不踩 `.env` 缺失坑)。

### 16. 每文件 ≤ 300 行(04 § 4)

```bash
wc -l api/main.py api/dependencies.py api/routes/health.py \
      api/schemas/health.py api/middleware/error_handler.py \
      tests/api/conftest.py \
      tests/api/test_app.py tests/api/test_health.py tests/api/test_error_handler.py
```

期望:所有文件 < 300 行(预估最大 `tests/api/test_error_handler.py` 约 280 行)。

### 17. README 已更新

```bash
cat api/README.md
```

期望:5 个模块的一句话职责描述 + 启动命令 + watchfiles polling 提示 + 测试命令 + 后续扩展点。**`docs/02_*` 引用必须是 § 3 目录结构 / § 7 API 分层约束**,**不是** § 7 配置管理(v1 草稿引用错,v2 已修)。

### 18. TASK_INDEX 状态已更新

```bash
grep -n "TASK-201" docs/03_TASK_INDEX.md
grep -n "Week 2:" docs/03_TASK_INDEX.md
```

期望:TASK-201 行状态 🔍,Week 2 进度条第 1 位变 🔍。

按决策 07,本 Task **只动 `docs/03_TASK_INDEX.md` 这一个 docs 文件**。

### 19. PR 元信息

- PR 标题:`TASK-201: FastAPI 框架搭建 + 健康检查 + 最小错误处理闭环`
- 分支名:`task/TASK-201-fastapi-bootstrap`
- PR 描述按 04 § 3 模板,**变更摘要必须明示**:
  1. 项目首次实质性 API 层填充
  2. 第 4 / 5 个 runtime 依赖(`fastapi==0.115.4` + `uvicorn[standard]==0.32.0`)+ 第 1 个显式 pin 的 dev 依赖 `httpx==0.27.2`
  3. **正式定型 ERROR_MAP 响应体 shape `{"error", "message"}`** + 8 个 handler 覆盖 `UploadError` / `ProjectError` 异常树
  4. **首次纳入 `api/` 到 mypy CI**(`api.routes.*` override 状态明示)

### 20. 完工报告含 git 三件套(决策 08)

完工时必须给 PM:

- 修改 / 新增的文件清单
- 本地 `make check` 完整输出
- 本地 `python -m ruff format --check .` 完整输出
- 本地 `pip check` 输出
- `git status` / `git log --oneline main..HEAD` / `git push` 完整输出
- 验收清单 1-19 项逐条勾选 + 说明
- PR 标题 + PR 正文

**不附三件套 = 没完工**。

### 21. ERROR_MAP shape lock 自证

PR 描述中明示:

> 本 PR 锁定 API 错误响应体 shape 为 `{"error": "<machine_code>", "message": "<中文文案>"}`。
> 未来任何 Task 修改此 shape 必须走 dataclass 修订 PR + 架构师 review,**不接受隐式 shape 演化**。
> TASK-206 在本 Task ERROR_MAP table 内**追加**剩余 9 项 handler,**不**改 shape。

### 22. mypy 配置变更明示

PR 描述中说明:
- `Makefile` `type-check` target 改动(`+api/`)
- `.github/workflows/ci.yml` `Type check (mypy)` 步骤改动
- `pyproject.toml` 是否新增 `[[tool.mypy.overrides]] module = "api.routes.*"`(本地实测决定;若加,贴具体 silent error 数量 + 类型作为理由)

### 23. autouse fixture leak detection 自证

PR 描述中确认 `tests/api/conftest.py` autouse fixture 已就位,且本 Task 的 25 个测试**全部不**触发 "WARNING: test leaked dependency_overrides" 警告。

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须保留原始字节,禁文本模式重写

决策 08 的真正规则是**保留文件原始字节**,**不是**"行尾必为 LF"。**禁用**:

- ❌ `pathlib.Path.read_text() + write_text()`(可能改 newline 转换)
- ❌ `open(path, 'w').write(...)`
- ❌ `sed -i`

**只允许** Python 字节级 `read_bytes()` → `bytes.replace()` → `write_bytes()`。

**Codex 实施前必须先**:

```bash
grep -n "TASK-201" docs/03_TASK_INDEX.md
grep -n "Week 2" docs/03_TASK_INDEX.md | cat -A
```

实地核查字面,再构造 old/new bytes。**前置 chore PR 已修复 Week 0 进度条**,但 Week 2 字面**没动**;Codex 实施时按 chore PR 合并后的实际状态再 grep。骨架:

```python
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# TASK-201 status: empty -> in-review
# IMPORTANT: replace with exact byte sequence from grep output
old_status = b'<EXACT TASK-201 row from grep>'
new_status = b'<same row, emoji replaced>'
assert old_status in data, 'TASK-201 row not found - run grep first'
data = data.replace(old_status, new_status)

# Week 2 progress bar slot 1
old_bar = b'<EXACT Week 2 bar from grep>'
new_bar = b'<same bar, slot 1 replaced>'
assert old_bar in data, 'Week 2 bar not found - run grep first'
data = data.replace(old_bar, new_bar)

p.write_bytes(data)
print('OK')
```

**改完立即 `git diff docs/03_TASK_INDEX.md` 验证**。若 diff 显示几百行红绿,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销**,换方式 A 编辑器手改。

字节级脚本错误消息**必须纯 ASCII**(Windows Git Bash codepage 中文乱码挡视线)。

### 风险 2:hygiene 检查 4 禁 TODO / FIXME / XXX

`scripts/check_repo_hygiene.sh` 第 4 项强制 `.py` 文件**不含** `TODO` / `FIXME` / `XXX`。本 Task error_handler 注释**绝对不能用这三个词**:

- ✅ "Placeholder: TASK-206 接管完整映射表"
- ✅ "Reserved for TASK-206 expansion"
- ❌ `# TODO: TASK-206 implement ERROR_MAP`

Codex 实施完成前**手动**跑 `bash scripts/check_repo_hygiene.sh` 确认通过。

### 风险 3:hygiene 检查 5 禁非测试 `.py` 含 `print(`

非 `tests/` 下的 `.py` 文件**不能用 `print()`**:

- `api/main.py` lifespan 启停日志 → 用 `loguru.logger.info(...)`
- `api/middleware/error_handler.py` 异常日志 → 用 `loguru.logger.error(...)`

**conftest.py** 在 `tests/api/` 下,**允许** `print()`(本 Task leak detection 用 `print(..., file=sys.stderr)` 而非 `raise AssertionError`,因为后者会翻转已通过测试的状态)。

### 风险 4:`api/` mypy 纳入策略

本 Task 改 `Makefile` + `.github/workflows/ci.yml` 把 `api/` 加入 type-check target。Codex 实施流程:

1. **先尝试全量** `make type-check`(`mypy core/ adapters/ features/ api/`)
2. 若全量通过 → **不**加任何 override → PR 描述明示"全量纳入,无需 override"
3. 若 `api.routes.*` 产生 5+ silent error → 在 `pyproject.toml` 加:

   ```toml
   [[tool.mypy.overrides]]
   module = "api.routes.*"
   ignore_errors = false
   disallow_untyped_defs = false
   warn_unused_ignores = false
   ```

   再跑 `make type-check`,期望通过。PR 描述贴出具体 silent error 类型 + 数量。
4. 若 `api.main` / `api.dependencies` / `api.middleware` / `api.schemas` 任何模块出现 silent error → **停手抛冲突给 PM**(本 Task 这四个模块必须严格通过)

**`Annotated[T, Depends]`** 写法(本 Task § 7.4)显著降低 mypy 噪音,实施时优先用此写法。

### 风险 5:`httpx` 显式 pin 到 requirements-dev.txt

FastAPI `TestClient` 依赖 httpx(官方文档要求)。当前项目通过 `openai==1.55.3` 间接传递引入 httpx——**但这是"被传递依赖兜住",不是契约**。

- ✅ 本 Task **显式 pin** `httpx==0.27.2` 到 `requirements-dev.txt`
- ✅ 验收 5 跑 `pip check` 验证 fastapi 0.115.4 + uvicorn[standard] 0.32.0 + httpx 0.27.2 + openai 1.55.3 + starlette(传递)无冲突
- ❌ **不**把 httpx pin 到 `requirements.txt`(httpx 仅测试期消费,production 不需要)

### 风险 6:lifespan startup 异常断言不写死单一异常类型

`@asynccontextmanager` 的 `async def lifespan(app):` 在 startup 抛异常时,starlette 在不同版本可能:
- 直接透传原异常(`pydantic.ValidationError`)
- 包装为 `RuntimeError("Application startup failed.")`
- Python 3.11+ 若 lifespan 内用 `asyncio.TaskGroup`,可能包装为 `ExceptionGroup`

本 Task 测试 8(`test_lifespan_fails_when_deepseek_api_key_missing`)**不**写死单一异常类型,断言改为**追溯根因**:

```python
def test_lifespan_fails_when_deepseek_api_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from api.main import create_app
    app = create_app()

    with pytest.raises(Exception) as exc_info:
        with TestClient(app):
            pass

    # 追溯根因:在异常链中能找到 deepseek_api_key 字符串
    exc_chain_str = ""
    e = exc_info.value
    while e is not None:
        exc_chain_str += str(e)
        e = e.__cause__ or e.__context__
    # ExceptionGroup 支持
    if hasattr(exc_info.value, 'exceptions'):
        for sub_exc in exc_info.value.exceptions:  # type: ignore[attr-defined]
            exc_chain_str += str(sub_exc)

    assert "deepseek_api_key" in exc_chain_str.lower(), (
        f"expected deepseek_api_key in exception chain, got: {exc_chain_str}"
    )
```

允许 starlette / TaskGroup / pydantic 任何方式包装,**但必须证明根因是 settings 缺失**。

### 风险 7:autouse fixture 在 conftest.py 的 late import

`tests/api/conftest.py` 内 `from api.main import app` 必须是**函数内 late import**,**不能在模块顶部**:

```python
@pytest.fixture(autouse=True)
def _isolate_test_state():
    get_settings.cache_clear()

    from api.main import app  # late import in function
    app.dependency_overrides.clear()
    ...
```

理由:conftest.py 在测试 collection 时即被加载;若顶部 import `api.main`,会触发 `app = create_app()` 副作用——而此时测试可能想 monkeypatch 环境变量再 import app,顺序错乱会导致测试不稳定。

### 风险 8:测试 3(`FileTypeNotAllowedError` 文案不含扩展名)

`api/middleware/error_handler.py` 中 `FileTypeNotAllowedError` 文案**故意不列具体扩展名**(详见 § 7.3 docstring)。**测试 3 反证**:

```python
assert ".m" not in body["message"]
assert ".slx" not in body["message"]
```

防 Codex"顺手"按 02 § 9 旧文案抄上完整白名单(02 与 TASK-104 实际 `ALLOW_EXTS` 漂移)。

### 风险 9:lifespan 未来资源 guardrail

**本 Task 不测 lifespan shutdown 资源释放顺序**(`/health` lifespan 无真实资源,测了是伪测试)。

**但** TASK-202 / 204 一旦在 lifespan 中初始化真实资源(临时目录清理 worker / SQLite 连接池 / 后台任务),必须**单独测试**:

> "资源 A 初始化成功 → 资源 B 初始化失败时,资源 A 被清理"

推荐用 `AsyncExitStack` 或显式 try/cleanup,**不**依赖 `yield` 后 shutdown block 在 startup 中途失败时被调用(starlette 不保证)。

本 Task 文档**预先**写下此 guardrail,TASK-202 / 204 实施者读 task-201 文档时获得提示。

### 风险 10:`em-dash` 字符从 pyproject.toml 复制

`api/main.py` `FastAPI(description="...")` 字符串含 em-dash `—`(U+2014)。Codex 实施时**不要凭键盘输入**,从 `pyproject.toml` 复制:

```bash
grep -E "^description" pyproject.toml
```

测试 2(`test_create_app_description_uses_em_dash`)通过 `tomllib.load(open("pyproject.toml", "rb"))` 拿 pyproject 实际字符串,断言 `create_app().description == that_string`。**键盘输入错也能被测试抓**。

### 风险 11:Route 不翻译业务异常(cross-Task guardrail)

最容易翻车的 cross-Task 模式不是 `create_app()` 或 `lru_cache`,是 route 内的临时错误翻译。后续 Codex 实施 TASK-202 时很可能写:

```python
# 反模式 - 禁止
@router.post("/upload")
async def upload(...):
    try:
        result = await safe_extract(...)
    except ZipBombError:
        return JSONResponse(status_code=400, content={"error": "..."})
```

这绕开统一 ERROR_MAP,**禁止**。正确模式:

```python
# 正确
@router.post("/upload")
async def upload(...):
    result = await safe_extract(...)  # 让异常抛出,ERROR_MAP 处理
    ...
```

`api/README.md` "后续 Task 扩展点" 段已明示。TASK-202 文档实施时,架构师在 task-202 文档中再次重申。

### 风险 12:Codex 误以为该实现 BackgroundTasks 演示

FastAPI BackgroundTasks 是常见模式,Codex 可能"顺手"在本 Task 演示。**这是范围扩张**。

**对策**:本 Task 健康检查是同步逻辑,`async def` 是为了对齐"API 接口全部 async def"(02 § 8),**不**演示 BackgroundTasks。BackgroundTasks 留给 TASK-202(上传后台清理 / 后台解析)。

### 风险 13:CI 跑的命令对齐(决策 09 反例 8 + 本 Task 改 type-check 命令)

CI workflow(`.github/workflows/ci.yml`)跑:
- `ruff check .`
- `ruff format --check .`
- `mypy core/ adapters/ features/` → **本 Task 改为** `mypy core/ adapters/ features/ api/`
- `pytest -v --tb=short`
- `bash scripts/check_repo_hygiene.sh`

本 Task 同时改 `Makefile` 与 `.github/workflows/ci.yml` 两处 mypy 命令,**两处字面必须完全相同**。完工前手动跑:

```bash
make type-check
grep "mypy" .github/workflows/ci.yml
```

确认两边一致。

仍建议完工前手动加跑:

```bash
python -m ruff format --check .
```

挂了就 `python -m ruff format .` 修复并 commit(本 Task 末尾建议一个独立 commit `style: ruff format` 跑完所有新文件)。

### 风险 14:遇冲突就停手

本 Task 是项目第一个 API Task,前置依赖较多,但已实地核查(2026-06-04 Codex dump)。冲突可能性低但非零:

| 冲突类型 | 应对 |
|---|---|
| chore PR 还没合并(`grep "反例 18"` 看不到) | 停手,等 chore PR 合并 |
| `api/__init__.py` 非空 / 含其他 import | 停手 |
| `requirements.txt` / `requirements-dev.txt` 行数与文档不符 | 停手,贴实际内容给 PM |
| `app/config.py::AppSettings` 字段数 / 名称与文档不符 | 停手 |
| `core/domain/exceptions.py` 类层级与文档不符 | 停手(本 Task 严重依赖 8 个异常类存在) |
| `tests/api/__init__.py` 已存在含 import | 停手,问 PM 是否覆盖 / 合并 |
| 03 索引 Week 2 进度条字面与风险 1 grep 预期不符 | 停手,贴 grep 输出给 PM |
| `Makefile` `make type-check` 已含 `api/`(可能其他 PR 抢先做了) | 停手,问 PM 后续策略 |
| `pyproject.toml` 已含 `[[tool.mypy.overrides]] module = "api.*"` | 停手 |

---

## 给 Codex 的提示

### 1. 推荐实现顺序

1. **前置确认**:`git fetch origin main && git log --oneline origin/main | head -5`,确认 chore PR 已合并(grep "反例 18")
2. 切分支 `task/TASK-201-fastapi-bootstrap`
3. `source .venv/Scripts/activate`(避免 ModuleNotFoundError,反例 12 同源)
4. `cat requirements.txt requirements-dev.txt Makefile pyproject.toml .github/workflows/ci.yml app/config.py api/__init__.py api/README.md api/middleware/__init__.py api/routes/__init__.py` 看现状,确认与本文档"输入"段一致
5. `find tests/api -type f 2>/dev/null` 看 `tests/api/` 当前内容
6. `pip install fastapi==0.115.4 'uvicorn[standard]==0.32.0' httpx==0.27.2` 本地装
7. 追加 2 行到 `requirements.txt`
8. 追加 1 行到 `requirements-dev.txt`
9. 改 `Makefile` `type-check` target
10. 改 `.github/workflows/ci.yml` `Type check (mypy)` 步骤
11. 建 `api/schemas/__init__.py` + `api/schemas/health.py`(抄 § 7.1)
12. 建 `api/dependencies.py`(抄 § 7.2)
13. 建 `api/middleware/error_handler.py`(抄 § 7.3,**注释禁 TODO/FIXME/XXX**,**日志禁 `str(exc)`**)
14. 建 `api/routes/health.py`(抄 § 7.4,**Annotated 写法**)
15. 建 `api/main.py`(抄 § 7.5,**description 从 pyproject 复制 em-dash**)
16. 覆盖写 `api/README.md`(抄 § 7.6)
17. 建 `tests/api/__init__.py`(若不存在)
18. 建 `tests/api/conftest.py`(抄 § 7.7,autouse fixture)
19. 建 `tests/api/test_app.py`(对照 § 7.8 9 用例)
20. 建 `tests/api/test_health.py`(对照 § 7.9 4 用例)
21. 建 `tests/api/test_error_handler.py`(对照 § 7.10 12 用例)
22. **试运行** `make type-check`;若 `api.routes.*` 5+ silent error 则加 `[[tool.mypy.overrides]]` 到 `pyproject.toml`
23. `pytest tests/api/ -v` 跑过 25 个测试
24. `pytest -v --tb=short` 整套测试跑过
25. `make check` 全检通过
26. `python -m ruff format --check .` 手动加跑
27. `pip check` 验证依赖兼容
28. uvicorn 真启动验收 /health + /openapi.json(详见验收 15)
29. 改 03 索引(字节级 Python,**先 grep 实际字面**,风险 1)
30. commit 拆分 + push + 三件套 + 提 PR

### 2. Commit 拆分建议(Conventional Commits)

```
chore(deps): add fastapi and uvicorn[standard] to runtime requirements
chore(deps): pin httpx as explicit dev dependency
chore(ci): include api/ in mypy type-check target
feat(api): add HealthResponse pydantic schema with extra-forbid
feat(api): add DI container with cached get_settings
feat(api): add 8-handler minimal ERROR_MAP with locked response shape
feat(api): add health check route with Annotated DI demo
feat(api): wire FastAPI app factory with lifespan and settings injection
docs(api): update README with module layout and watchfiles polling note
test(api): add autouse cleanup fixture for tests/api
test(api): add app factory tests covering lifespan and openapi schema
test(api): add health endpoint tests with extra-forbid validation
test(api): add error handler tests covering 8 handlers and shape lock
docs: mark TASK-201 as in-review in task index
```

不要单个超大 commit。Commit subject **单行,无 body**(PM 偏好,反例 17 教训)。

若实地决定加 `[[tool.mypy.overrides]]`,再加一个 commit:`chore(ci): override mypy strictness for api.routes.*`。

### 3. 测试客户端选择:`TestClient` 优先

FastAPI 自带 `TestClient`(基于 starlette,同步):

```python
from fastapi.testclient import TestClient
from api.main import app

def test_health():
    with TestClient(app) as client:  # with 触发 lifespan
        response = client.get("/health")
        assert response.status_code == 200
```

**不要**用 `httpx.AsyncClient`(本 Task 测试都能用同步 client 搞定)。

`asyncio_mode = "auto"` 意味着 async 测试函数**不需要**装饰器,但本 Task **测试函数全部 `def test_xxx`,不用 `async def`**,简化心智。

**注**:这条规则仅针对**本 Task**。后续 TASK-202 / 203 / 205 若测试函数本身需要 `async def`(并发上传、async DB、直接 await service),局部引入 `httpx.AsyncClient + ASGITransport`,**不是项目永久禁令**。

### 4. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

字节级 Python(详见风险 1)。**字面量必须实地 grep 后再匹配**(chore PR 已修 Week 0 但 Week 2 字面没动;实施时按 chore PR 合并后实际状态再 grep),否则 assert 失败。

### 5. CI 实际跑的命令(决策 09 反例 8 + 反例 13)

本 Task 改了 `Makefile` 与 `.github/workflows/ci.yml` 两处 mypy 命令。**两处字面必须完全相同**,否则会复制反例 8 模式(本地 `make check` 过 CI 挂)。完工前:

```bash
grep "mypy core/ adapters/ features/" Makefile .github/workflows/ci.yml
```

应在两个文件中找到相同的命令字面(`mypy core/ adapters/ features/ api/`)。

### 6. 完工报告含 git 三件套 + 工具版本对齐 + 依赖兼容验证

完工时给 PM:

- 修改 / 新增的文件清单
- 本地 `make check` 输出
- **本地 `python -m ruff format --check .` 完整输出**(必须 `python -m ruff`)
- **本地 `pip check` 输出**(本 Task 新加,因 httpx + fastapi 依赖兼容性需明确验证)
- **`git status` / `git log --oneline main..HEAD` / `git push` 完整输出**
- 验收清单 1–23 项逐条勾选 + 说明
- PR 标题:`TASK-201: FastAPI 框架搭建 + 健康检查 + 最小错误处理闭环`
- PR 正文(变更摘要明示"项目首次实质性 API 层填充 + 第 4/5 个 runtime 依赖 + ERROR_MAP shape 锁定 + api/ 首次纳入 mypy CI")

**不附三件套 = 没完工**。

### 7. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:PR 标题 + PR 正文,PM 在 GitHub 网页手动创建 PR。

### 8. 遇冲突就停手

详见风险 14。本 Task 是项目第一个 API Task,前置依赖较多,但已实地核查(2026-06-04 Codex dump),冲突可能性低但非零。**最关键**:chore PR 必须先合并,否则 03 索引 / decision 09 状态可能与本文档预期不符。

### 9. 决策 09 反例 18 提醒

本 Task 文档是项目首个**经历过审批级别误判**的 Task(反例 18)。Codex 实施时若发现"task 文档与现状不一致"的场景,参考反例集——尤其反例 11(二审采纳后忘 grep 全文)和反例 18(类比降级审批)的根因。**抓住就停手抛冲突给 PM**。

### 10. mypy 全量纳入 `api/`

本 Task 改 `Makefile` + `.github/workflows/ci.yml` 把 `api/` 纳入 mypy CI。这是首次纳入,Codex 实施时:

- **优先**全量 `mypy core/ adapters/ features/ api/` 通过
- 若 `api.routes.*` 真有 5+ silent error,加 `[[tool.mypy.overrides]]` 局部松绑
- **不**整体豁免 `api/`(v1 草稿原方案,一审 + 二审一致反对)

完工时本地手动跑 `mypy api/` 自检,确认类型注解正确;若 `# type: ignore[xxx]` 多于 3 处,PR 描述如实贴出来让架构师 review 判断。

### 11. `Annotated[T, Depends]` 写法

FastAPI 0.115+ 偏好的写法,显著降低 mypy 噪音:

```python
# 优先(本 Task 用)
async def get_health(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthResponse:
    ...

# 旧写法(v1 草稿原用),仍可工作但 mypy 噪音多
async def get_health(
    settings: AppSettings = Depends(get_settings),
) -> HealthResponse:
    ...
```

本 Task 所有 route handler 用前者写法。后续 TASK-202/203/205 复制此模式。

### 12. autouse fixture late import

`tests/api/conftest.py` 内 `from api.main import app` **必须在函数体内 late import**,**不能在模块顶部**(详见风险 7)。否则 conftest collection 时即触发 `app = create_app()` 副作用,monkeypatch 环境变量的测试会拿到错误的 settings 实例。

---

**版本**:Task 文档 v2.0
**作者**:Claude(架构师,第九任)
**日期**:2026-06-04
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md` / `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md` / `20260603-09-*.md`(**特别反例 18**)/ `20260604-10-*.md`
**关联 Task**:依赖 TASK-001 / 002 / 101 / 104 / 106 / 108(已合并产物);下游 TASK-202 / 203 / 204 / 205 / 206 / 405
**前置 chore PR**:决策 09 反例 18 + 03 索引 Week 0 进度条修复(随本 Task 入仓时序合并)
**是否走 GPT 二审**:**是**(本 Task 经一审 1 轮 + 二审 1 轮,PM 拍板方案 B 后定型)
**是否走 GPT 一审**:**是**(本 Task 是 API 层首次定型,8 决策点 × 5 下游扩散,审批级别评估错过两次后正确定位)
**审批级别教训**:决策 09 反例 18 — 凭"基建 Task 类比 task-108"判断审批级别,把首次定型 API 层模式的 Task 误降为无审;教训:审批级别评估也属于"凭印象 vs 实地核查"范畴,需评估"决策密度 × 下游扩散面 × 用户/安全可见性",不看"基建 / 非核心 / 代码少"等标签
**实地核查日期**:2026-06-04(Codex dump 核查 13 文件 + 2 目录树,决策 09 纪律 1 实操记录)
