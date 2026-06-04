# 20260604-11:async 内同步重活必须 asyncio.to_thread 桥接 + 业务异常日志禁用 logger.exception

## 状态

✅ 决议(冻结,v2.1 兼容)。本决策与 01 § 7 异步原则 / 01 § 9 数据隐私 / 02 § 12 日志隐私 / 04 § 9 日志规范 / 04 § 10 异常处理协同。

---

## 触发原因

TASK-202(上传 + 解析 API,首个用户面端点 + 首个 async + 长任务复合形态)走 GPT 二审 round 1,二审给出 10 条建议,其中两条 P0 均触及**框架默认行为的隐性假设**:

### P0-2:async 函数内同步代码阻塞 event loop

第十任架构师在写 task-202 v0.1 初稿时,凭印象认为 FastAPI / Starlette 在 `async def` BackgroundTask 内会**自动把阻塞同步代码放到线程池**,因此在 `UploadService.process` 内直接 await 同步重活(`safe_extract` / `classify_files` / parsers / `analyze_dependencies`)。

GPT 二审实地查 Starlette 源 + FastAPI 文档发现:Starlette 仅对**同步** endpoint / background task **自动放线程池**(`run_in_threadpool`);而 `async def` 函数内的阻塞同步代码会在 event loop 上**直接执行**,导致:

- 整个 uvicorn 在解析期间(几秒到几十秒)**无法处理任何其他请求**,包括 GET /status 轮询
- 单 worker 模式下(TASK-202 D5 硬约束),意味着用户上传一个稍大工程,全站几十秒无响应

正确做法:**`await asyncio.to_thread(self._run_parse_sync, ...)` 桥接**,把同步重活丢进线程池,event loop 继续处理其他请求。

### P0-3:`logger.exception` 自动落 traceback 违反隐私硬约束

第十任在 task-202 v0.1 异常分支用 `logger.exception(...)`,凭印象认为这是 loguru 标准异常日志方式。

GPT 二审实地查 loguru 文档发现:`logger.exception(...)` 等价于 `logger.error(..., exception=True)`,**自动捕获并落 traceback**;traceback 内含完整 `repr(exc)` ≈ `str(exc)`。而本项目内业务异常 message **可能含**:

- 用户上传文件名片段(`info.filename`)
- 文件内容片段(parse error 时的 token 上下文)
- 临时路径片段(可能含 UUID / 项目名)

这违反 01 § 9 + 02 § 12 + 04 § 9 三处隐私硬约束("不记录用户上传的工程内容""不记录原文")。

正确做法:**业务异常分支统一 `logger.error("...exception={}", type(exc).__name__)`**,只落类名 / project_id / error_code 等元数据,不落 `str(exc)` / `repr(exc)` / traceback。

### 共同特征

- 两条 P0 均"凭框架默认行为印象"做错误假设
- 两条 P0 错一次,后续 4-5 个 Task(TASK-203 LLM 异步调用 / TASK-205 RAG 异步检索 / TASK-304 向量 RAG / 任何 BackgroundTask 用例)同款抄错
- 两条 P0 都在第十任**未实地查框架源 / 文档前**做了"看似合理"的写法
- GPT 二审实地核查框架源 / 文档才抓住

固化为长期决策,避免后续架构师在"async 框架行为"或"日志便利方法"维度凭印象写。

---

## 决策

### 决策 1 — async 函数内同步重活必须通过 `asyncio.to_thread` 桥接

**适用范围**:任何 `async def` 函数(API endpoint / BackgroundTask / lifespan / asyncio.Task / service.process / etc.),内部需调用同步阻塞函数(parsers / 文件 IO / `time.sleep` / 同步 LLM / 同步 DB / 同步加密 / 同步 zip / etc.),**必须**:

```python
result = await asyncio.to_thread(sync_function, arg1, arg2, ...)
```

**禁止**:

- ❌ 在 `async def` 内直接 `sync_function(...)` 调用(阻塞 event loop)
- ❌ 用 `loop.run_in_executor()` 替代(可读性差;`asyncio.to_thread` 是 Python 3.9+ 推荐写法)
- ❌ 在 `_run_*_sync` 类同步辅助方法内 `await` 任何 async 调用(跨线程 event loop 错误)

**例外**:

- 同步 endpoint / 同步 background task(FastAPI / Starlette 自动放线程池,无需 to_thread)
- pytest 同步测试函数(无 event loop)
- 同步 service 方法被同步调用方调用(无 event loop)

**实施模式**(TASK-202 D13 已定型,本决策固化为全项目标准):

```python
class SomeService:
    async def process(self, ...) -> None:  # async,被 event loop 调度
        try:
            project_dir.mkdir(parents=True, exist_ok=False)  # 轻 IO,不需 to_thread

            result = await asyncio.to_thread(
                self._run_sync_heavy_work,  # 同步重活
                arg1, arg2, ...,
            )

            await self._store.mark_ready(...)  # async,自然 await
        except Exception as exc:
            # 异常翻译(见决策 2)
            ...

    def _run_sync_heavy_work(self, ...) -> Result:  # 纯同步,丢线程池
        # 在这里做所有同步重活,不调任何 async
        ...
```

**检查方法**:

- 实施时:`grep -rn 'async def' features/ api/ --include='*.py' --exclude-dir=.venv` 看每个 async 函数内是否有可疑同步调用
- review 时:`grep -rn 'asyncio.to_thread' features/ api/ --include='*.py' --exclude-dir=.venv` 看消费是否正确;同时看 `_run_*_sync` 命名的同步辅助方法是否纯同步

### 决策 2 — 业务异常分支日志统一 metadata-only,禁用 `logger.exception`

**适用范围**:任何业务代码(`features/` / `api/` / `adapters/` / `app/` / `core/`)的异常分支,**禁用** `logger.exception(...)`。

**统一写法**(TASK-202 D14 + 风险 11 已定型,本决策固化为全项目标准):

```python
try:
    ...
except SomeBusinessError as exc:
    logger.error(
        "Context: project_id={} exception={} error_code={}",
        project_id,
        type(exc).__name__,    # 类名,不是 str(exc)
        error_code,             # 业务侧分类(已脱敏)
    )
    ...
except Exception as exc:
    logger.error(
        "Unexpected error: project_id={} exception={}",
        project_id,
        type(exc).__name__,    # 同上
    )
    ...
```

**禁止**:

- ❌ `logger.exception(...)`(自动落 traceback)
- ❌ `logger.error(f"...: {exc}")`(`__str__` 触发 message)
- ❌ `logger.error(f"...: {repr(exc)}")`(同上)
- ❌ `logger.error("...", exc_info=True)`(等价 logger.exception)
- ❌ 任何含 `args` / `message` / 异常自身的 f-string

**例外**:

- 测试代码(`tests/`)可以使用 `logger.exception(...)`(无生产隐私风险);但生产代码无例外
- `pytest.raises` 上下文里的断言 message 不在禁列(那是测试断言,不是生产日志)

**检查方法**:

- 实施时:`grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ --include='*.py' --exclude-dir=.venv --exclude-dir=.git` 应**空**
- review 时:同上 + 检查 f-string 异常字段

---

## 工程影响

**对架构师**:写涉及 async / 日志的 Task 文档时,在"接口契约" / "风险与注意" / "决策日志"段明示引用本决策。Task 文档**不重复全文,引用即可**(决策 06)。

**对 Codex**:

- 看到 `async def` 函数内有同步函数调用,**必须**用 `asyncio.to_thread` 桥接,或停手抛冲突
- 看到 Task 文档 / review 命令含 `logger.exception`,**必须**停手抛冲突

**对 PM**:Step B review 命令清单(决策 08 第 2 条)新增两条 grep 兜底:

```bash
# 决策 11 验收
grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
# 应空输出。非空 = 决策 11 违反 = 打回返工

grep -rn 'async def' features/ api/ --include='*.py' --exclude-dir=.venv | head -30
# 看 async 函数内是否有可疑同步重活,review 重点
```

**对 GPT 二审**:本决策定型后,二审材料不再需要重复审 P0-2 / P0-3 类反馈;聚焦其他维度(prompt / schema / 业务边界)。

---

## 与其他决策的关系

- **决策 04**(理解不抽顶层 feature):无关
- **决策 05**(静态扫描排除 .venv / .git):本决策的 grep 检查命令引用决策 05 规范模板
- **决策 06**(Codex 可读仓库文件):Task 文档引用本决策路径即可,无需内联全文
- **决策 07**(03 索引更新边界):无关
- **决策 08**(PM 验 git + 字节级):Step B review 命令清单新增 2 条 grep 兜底(上文)
- **决策 09**(架构师必须实地核查):**本决策是决策 09 在"框架默认行为"维度的延伸**。决策 09 反例 19 已记录第十任凭框架印象写 v0.1 的踩坑;本决策固化两条具体不变量
- **决策 10**(TASK-107 一审 1 轮临时降级):无关
- **宪法 § 7 异步与并发 / 01 § 9 数据隐私 / 02 § 12 监控与日志 / 04 § 9 日志规范**:本决策**不修改宪法**,仅在工程层面具象化"不记录用户上传内容"硬约束

---

## 终止条件

满足以下任一,可考虑废除本决策或降级为"建议":

1. Python / FastAPI / Starlette / loguru 演进出新的明确语义,使本决策的两条不变量自然内化(例如 FastAPI 在 async endpoint 内自动检测阻塞代码并 warn)
2. 项目改为 sync API + 单进程多 worker 模式(MCS 阶段不打算)
3. 项目改用其他日志库(如 structlog)且新库语义不存在 `logger.exception` 类陷阱

任一未满足时,本决策强制生效。

---

## 一句话总结

**`async def` 函数内同步重活必须通过 `asyncio.to_thread` 桥接;业务异常分支日志统一 `logger.error(..., type(exc).__name__)` metadata-only,禁用 `logger.exception` — 两条都是凭框架默认行为印象会写错的不变量,GPT 二审 P0 才抓住,本决策固化为长期约束**。

---

**版本**:v1.0
**日期**:2026-06-04
**作者**:Claude(架构师,第十一任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260603-09-architect-must-verify-not-assume.md`(架构师纪律,反例 19 同步记录;本决策是决策 09 在"框架默认行为"维度的延伸)
**触发 Task**:TASK-202(上传 + 解析 API,首个用户面端点 + 首个 async + 长任务复合形态,GPT 二审 round 1 P0-2 + P0-3)
