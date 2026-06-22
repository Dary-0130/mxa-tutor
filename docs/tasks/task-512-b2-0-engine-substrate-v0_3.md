# TASK-512:MATLAB Engine substrate gate(v0.3-b / b2-0)

## 状态

🔲 v0.3 三修(2026-06-21,**待 R1 定向三审 + R6 轻核**)。据 `origin/main`(#109 `6bc9c76`)逐字取证设计;v0.3 = 吸收 R1 二审 3 P0(Simulink 前置 / 取消 API 调用契约 / 超时回收状态机)+ 两边 P1/P2。A–D 设计点二审仍全 PASS,任务范围/拆分位置不动。

---

## 背景与定位

- 本卡是 **v0.3-b 拆分定稿**(`T0 → b1 ∥ b2-0 → b2-1 → b3`)里的 **b2-0**,**与 b1(TASK-511)并行**,互不依赖。
- **b2-0 只做一件事:把 MATLAB Engine API 装进 `.venv` 并证明 runtime substrate 成立**——能起、能跑最小代表性模型、异常能传播、能超时/取消、能干净关、连续两轮不残留僵尸、Engine 不可用不拖垮其他 Web 功能和 CI。
- **b2-0 是整个 v0.3-b 的关键前置**:它最早证伪/证实"MATLAB Engine 真能在**服务将使用的 Python runtime(同一 `.venv` / 解释器)**里跑模型"这个最大未知。**b2-0 不通,b2-1 免谈。**(b2-0 尚不能证 uvicorn worker 下的阻塞行为 / request 取消 / lifespan 复用 / 并发 / 关闭时 Engine 回收——那些归 b2-1,R1 P1-1。)
- **b2-0 明确不做**(见 §范围-不做):不把 Engine 接进 bridge route/service/lifespan、不做自动采集、不动 diagnostic 契约、不动客户端——那些是 b2-1 / b1 的面。

---

## 实测地基(来自 `origin/main` A-G + 本轮 b2-0 取证;实施前 Codex 复核)

1. **本机环境可行性高**:`.venv` = 64-bit Python 3.11.15;MATLAB R2026a Update 2;Engine `setup.py` 支持 Python 3.9–3.13;smoke 已通过(`start_matlab()` ~11.5s、`sqrt(4.0)=2.0`、`quit()` 成功)。**注:该 smoke 用临时 `sys.path` 仅为验证可行性;b2-0 正式装配禁止靠 `sys.path`/`PYTHONPATH` 注入(见 §做什么-4 / G0)。**
2. **Engine API 可精确 PyPI pin,但不得进默认 requirements**(R1 P0-1 据 MathWorks 官方文档 + R2026a `setup.py`,**更正 v0.1 误称"不可 PyPI pin"**):R2026a 对应 `matlabengine==26.1.12`(支持 Py3.9–3.13);它**依赖本机 MATLAB**、安装器会查找匹配的 MATLAB,故 CI(`ubuntu-latest`,无 MATLAB)装不了。装配走单独的 `requirements-matlab-r2026a.txt`(不被 dev 引用)。**版本号实测注意**(R6 核验):本机 `F:\Matlab\extern\engines\python\setup.py` 写的是 `version="26.1"`、PyPI 是 `26.1.12`——**两边都不能拿来当死值,最终以装后 `importlib.metadata.version("matlabengine")` 为准**(同"凭来源推断 ≠ 实测"教训),Codex 实测填实际值。
3. **CI(`​.github/workflows/ci.yml`)**:`ubuntu-latest` + Python 3.11;`pip install -r requirements-dev.txt`;`ruff check .` → `ruff format --check .` → `mypy core/ adapters/ features/ api/` → **`pytest -v --tb=short`(不带 `-m` 过滤,跑全部 marker)** → `bash scripts/check_repo_hygiene.sh`。
4. **pytest marker 约定**(`pyproject.toml`):`integration`(调外部服务或加载真实模型)、`slow`(故意慢)。**marker 不被 CI 排除**,故仅靠 marker 挡不住 Engine 测试在 CI 上跑。
5. **mypy 约定**(`pyproject.toml`):`python_version=3.11`、`warn_unused_ignores=true`、`disallow_untyped_defs=false`;已有 `[[tool.mypy.overrides]] module="sentence_transformers.*" ignore_missing_imports=true` 的先例。
6. **依赖 pin 模型**:`requirements.txt` 顶注"Runtime dependencies will be added per-task",全 `==` 精确 pin(numpy 例外区间)。`requirements-dev.txt` = `-r requirements.txt` + 测试/lint 工具。
7. **lazy-import 先例**:`api/main.py` 的 `SentenceTransformerEmbedder(...)` 工厂在函数体内 `from adapters.embedding...` 延迟导入,使"导入 app 保持轻量、缺失重依赖不炸 collection";`adapters/embedding/sentence_transformer.py` 文档明确"synchronous; application code should bridge it with `asyncio.to_thread`"。
8. **decision 11 异步桥接 = 全仓约定**:重活同步实现 + 调用侧 `await asyncio.to_thread(...)`;paper 服务有 `test_only_one_asyncio_to_thread_in_service()` 断言"每服务恰一处 to_thread"的纪律测试。
9. **bridge 现状**:`features/matlab_bridge/diagnostic_service.py` 的 `DiagnosticService.consume()` 是**同步** stub,返回固定 `connectivity_stub` 回执;`api/main.py` 中 `_validate_matlab_bridge_settings()` 在 `matlab_bridge_enabled` 且 `app_environment ∉ {development,test}` 时 `RuntimeError` 失败关闭,`create_app()` 据 `matlab_bridge_enabled` 条件挂 `matlab_bridge_router`。
10. **config 现状**(`app/config.py`):`AppSettings(BaseSettings)`;已有 `app_environment: Literal["production","development","test"] = Field(default="production", validation_alias="APP_ENV")` 与 `matlab_bridge_enabled: bool = False`;字段小写 ↔ 环境变量大写;`extra="ignore"`。

---

## 范围

### 做什么(b2-0 交付物)

1. **Engine substrate 适配器**(落点 `adapters/matlab_engine/`,见 §设计点裁决-A):一个**同步**的 MATLAB Engine 会话封装,**两个明确入口 + 所有权/状态模型**(R1 P0-3/P0-5):
   - `start_owned(...)`:适配器**拥有**该 MATLAB 生命周期;
   - `connect_shared(name: str)`:连接**显式命名**的共享会话(**不**用无参 `connect_matlab()`——它无共享会话时会新起一个、有多个时连最早的,非确定性 connect-only);
   - 内部至少记 `ownership = owned | attached`、`state = new | ready | busy | broken | closed`;
   - **跑真实 `sim`,fixture 必须确定性**(R1 P0-4 / R6 P0-3 + R1 P1-1):代表性门必须在 MATLAB 内真正调 `sim`(**`sim` 属 Simulink,故依赖不止 MATLAB,见 §依赖 + G0b**)——Python 可 `feval` 调 fixture helper,但 helper 内部须**创建/加载 trivial Simulink 模型 + 跑 `sim` + 返回确定性 struct**;`feval` 返回结构化输出**只作安装 smoke,不得替代代表性门**。fixture 钉死:**固定步长离散 solver + 固定 sample time + 固定 StopTime + 固定输出记录方式 + 唯一模型名 + 临时目录 + `onCleanup`/`finally` 关模型删临时文件**(禁默认 variable-step solver,否则 `sample_count` 跨运行不稳),示例返回 `{stop_time: 1.0, sample_count: 11, final_value: 2.0}`;
   - **可超时调用的对外契约现在锁死(R1 P0-2)**——光写底层 future 算法、不给调用者取消入口 = G7 可被"只在测试里操作 fake future"假通过。锁一个最小 concrete 方法(**非 b2-1 的 core Protocol,B 裁决不变**):
     ```python
     def run_simulation(self, fixture_path: Path, *, timeout_s: float,
                        cancel_event: threading.Event | None = None) -> MatlabSimulationResult: ...
     ```
     内部**短周期轮询**:提交 `background=True` future → 每轮 `result(poll_interval)` 并查 deadline / `cancel_event` → `cancel_event` 触发抛 `MatlabEngineCancelledError`、deadline 触发抛 `MatlabEngineTimeoutError`。这样 b2-1 仍是**一个** `await asyncio.to_thread(session.run_simulation, ..., cancel_event=...)` 接入,不必开第二个 to_thread 去调 cancel。**禁**只靠 `asyncio.wait_for(asyncio.to_thread(...))`——它只停等待协程、不终止 MATLAB 执行;
   - **超时后回收状态机(R1 P0-3,`cancel()==False` 不能无条件强关)**:
     ```
     result(timeout) →
       future.done()==True  → 消费 result/exception,session 可保 ready
       future.done()==False → future.cancel()
           True  → 在有界 cleanup_grace_s 内确认 cancelled/done + 轻量 health probe → 成功则 ready,否则 broken
           False → session = broken,按 ownership 隔离
     ```
     任何"等待进入 cancelled/done"必须有第二个**有界 `cleanup_grace_s`**,不无限等。fallback 按所有权分:`owned` 限时 graceful quit 后仍不退才按已记录 PID 终止该进程;`attached` **只断当前 Engine 连接、永不杀用户原有 MATLAB**,本 wrapper 标 broken/closed。PID 用**公开 `matlabProcessID`**(不用未公开的 `feature('getpid')`);
   - **MATLAB 异常 → 本仓 typed error**(粒度见下表,**不再写"卡内细化"**);
   - **干净关闭**:`owned` 的 `close()` 停该 MATLAB 进程;`attached` 的 `close()` 只断连接、**不杀用户 MATLAB**;`close()` 幂等;关后再调抛 typed session error;
   - **`matlab.engine` 延迟导入**(函数体内 import,照 §地基-7)——模块导入本身**不得**因 matlabengine 缺失而 `ImportError`,只有真起会话才报 typed unavailable。

2. **Engine 错误 domain**(照 `core/domain/exceptions.py` 的 `EmbeddingModelLoadError` 模式;**语义粒度现在冻结,类名可微调**,R1 P0-2):

   | 情况 | 本仓异常 |
   |------|----------|
   | `import matlab.engine` 不存在 | `MatlabEngineUnavailableError` |
   | start 失败 | `MatlabEngineStartupError` |
   | connect 失败 | `MatlabEngineConnectionError` |
   | Simulink 未安装 / 许可不可 checkout | `MatlabEngineCapabilityError` |
   | MATLAB 函数/模型执行失败 | `MatlabEngineExecutionError` |
   | 结果等待超时 | `MatlabEngineTimeoutError` |
   | 主动取消 / 调用被中断 | `MatlabEngineCancelledError` |
   | Engine 已退出 / 拒绝调用 | `MatlabEngineSessionError` |
   | 并发调用同一 session(见 §实施约束) | `MatlabEngineBusyError` |

   typed error 带稳定 `reason_code`,**不塞 `str(exc)` 原始 MATLAB 文本**(防本地路径/模型名/脚本片段泄漏),重抛用 `from None`(R1 P1-4)。

3. **测试分两层**(R1 P0-5 / R6 P0-1 ——这是 v0.1 最大盲点:纯 importorskip 会让核心逻辑在 CI 零覆盖):
   - **CI 必跑单元测试** `tests/adapters/matlab_engine/test_runtime_unit.py`:用 **fake engine / fake FutureResult**,测 模块导入不触发 `matlab.engine`、import 缺失 → unavailable、异常翻译、超时后调 cancel、cancel=False → session broken、owned/attached close 分支、close 幂等、原始异常不泄漏。**不**用 importorskip、**不**标 integration。
   - **本机真实集成测试** `tests/adapters/matlab_engine/test_runtime_integration.py`:**显式 env 门 `MXA_RUN_MATLAB_ENGINE=1`**(统一 R1 的 `RUN_MATLAB_ENGINE_INTEGRATION` 与 R6 的 `MXA_REQUIRE_MATLAB_ENGINE` 为一个变量)。**守卫写成伪代码,不用 `importorskip`**(R6 P1 + R1 P1-3——`importorskip` + opt-in 极易被实现成"env 已设仍无条件 skip 掩盖缺包"):
     ```python
     RUN_ENGINE = os.getenv("MXA_RUN_MATLAB_ENGINE") == "1"
     if not RUN_ENGINE:
         pytest.skip("Set MXA_RUN_MATLAB_ENGINE=1 to run.", allow_module_level=True)
     import matlab.engine   # opt-in 后缺包必须 collection fail,不许 skip
     ```
     标 `integration` + `slow`。**双语义**:未设 env → 跳过(防某台偶然装了 matlabengine 的 CI runner 自动起 MATLAB);设了 env → matlabengine 不可用必须 fail。
   - **shared 会话集成测试必须自建自清**(R6 P1 + R1 P1-2):测 `connect_shared` 不得连 PM 当前已开的任意 MATLAB——须 fixture **自己起一个 owned 会话 + 生成合法唯一共享名 + `shareEngine`**,再断原连接、测 `connect_shared(name)` + attached close 后重连,**`finally` 中必须终止这个测试自建的 owner 会话**;否则 G9 证完"attached 不杀用户 MATLAB"后,测试自己反而留了个 MATLAB 残留。

4. **依赖装配**:matlabengine 写进**单独的 `requirements-matlab-r2026a.txt`**(内容 `matlabengine==26.1.12`,实际版本号 Codex 实测确认);**该文件不被 `requirements-dev.txt` 引用**,故 CI 不装;`README` / 本地安装说明写明 `.venv` 装法 + 禁 `sys.path` 注入。**不动 `.env.example`**(C 裁决:b2-0 不接 app,见 §设计点裁决-C)。

5. **mypy override**:`pyproject.toml` 加 `[[tool.mypy.overrides]] module = ["matlab", "matlab.*"] ignore_missing_imports = true`(R1 P1-5,连根包一并覆盖,防将来用 `matlab.double` 等根包符号再现缺口)。**禁行内 `# type: ignore`**(`warn_unused_ignores=true` 会让它在装了 matlab 的机器上变 unused → 重蹈上任覆辙)。

6. **`make test-engine`(交付物,非可选)**(R1 P1-6):内部设 `MXA_RUN_MATLAB_ENGINE=1` 并只跑 Engine integration 文件,供 MATLAB 在场的机器(PM/Codex)跑;R6 报告须贴命令 + 完整结果,不许只写"本机通过"。

### 不做(明确划给后续阶段,本卡不碰)

- **不把 Engine 接进 bridge route / `diagnostic_service` / lifespan**(= b2-1)。b2-0 的适配器是**独立可测的 substrate**,不进运行时服务路径。
- **不做自动采集 / 收敛解释 / 结果解释**(b2-1 / b3)。
- **不动 diagnostic 契约**(`core/domain/bridge_diagnostic.py`、`bridge_diagnostic_schemas.py`、`schemas/bridge_diagnostic_*.json`)、**不动客户端 `.m`**、**不动 route 固定顺序**(loopback/415/413/replay)。
- **不决定 Engine 进程生命周期放哪**(per-request? pooled? lifespan-managed?)——那是 b2-1;但 b2-0 的"**同步 API + 不 per-request 启动**"约束(§实施约束)为 b2-1 留好接法。

---

## 设计点裁决(R1 + R6 一致,已拍定)

- **A. substrate 落点 = `adapters/matlab_engine/`。** 两审一致:MATLAB Engine 是外部 runtime/SDK 集成,归 adapter 层(与 `adapters/llm`、`adapters/embedding` 同构),**不进 `features/matlab_bridge/`**。
- **B. core Protocol 留 b2-1。** b2-0 先落 concrete adapter + typed result/error;此时不知 b2-1 消费的是 run / session / collector / execution handle,过早建 Protocol 易冻错形状。**约束:b2-1 接 service 前必须补最小 `core/interfaces` 契约,届时 `features/matlab_bridge` 不得直接 import 具体 adapter。**
- **C. `matlab_engine_enabled` flag 留 b2-1。** b2-0 不接 app runtime,现在加只会造伪装配面;**相应地 b2-0 不动 `.env.example`**(仓里虽有该文件,本卡范围不含它)。
- **D. CI 隔离 = 第三方案(非原二选一)。** CI 命令不改;真实集成测试用 `env opt-in(MXA_RUN_MATLAB_ENGINE=1)+ importorskip`;核心逻辑另有 CI 必跑 fake 单测(见 §做什么-3)。**不**全局加 `-m "not integration"`(会改全仓 marker 语义)。

---

## 验收门(= b2-0 独立合并门;能力门 G0–G10,取消 v0.1 "7 条/9 条"计数漂移)

> "本机" = MATLAB 在场的机器(PM/Codex),经 `MXA_RUN_MATLAB_ENGINE=1` 强制跑(不许 skip);"CI" = `ubuntu-latest` 无 matlabengine。

| 门 | 验收内容 | CI / 本机 |
|----|----------|-----------|
| G0 | 精确包版本安装,证明来自仓库 `.venv`、**无 `sys.path`/`PYTHONPATH` 注入**;记 `importlib.metadata.version("matlabengine")` + `importlib.metadata.distribution("matlabengine").locate_file("")`(证 distribution location、非注入,R6 P2)+ `matlab.__file__` + MATLAB release/update | 本机 |
| G0b | **Simulink 安装 + 许可能力**(R1 P0-1):`ver("simulink")` 能发现 + `license("test","Simulink")` 可用;缺失 → `MatlabEngineCapabilityError`(不误记为执行错误);最终仍以真实 trivial `sim` 成功为决定性证据 | 本机 |
| G1 | adapter 与 `api.main` 在**无 matlabengine** 环境可导入(延迟导入护 collection) | CI |
| G2 | `start_owned` 正常启动成功 + startup failure 翻译正确 + 记 startup latency(**生产级 startup timeout / reaper / watchdog 留 b2-1**,R1 P0-3:`start_matlab` 的 startup 取消语义与普通函数 `cancel()` 不同,不在 b2-0 硬塞) | 本机 |
| G3 | `connect_shared` 按显式 name 连接**测试自建**的共享会话(`finally` 终止该自建会话) | 本机 |
| G4 | 固定步长真实 `sim` trivial 模型,返回确定性 struct(断言 `stop_time` / `sample_count` / `final_value` 固定值) | 本机 |
| G5 | MATLAB 执行错误 → typed error,原始异常不泄漏 | CI(fake)+ 本机 |
| G6 | 长调用超时经**对外 adapter API**(`run_simulation(timeout_s=...)`)触发 + **有界回收**(`done()` 判定 → cancel → `cleanup_grace_s` + health probe → ready/broken) | CI(fake)+ 本机 |
| G7 | 显式 cancellation 经**对外 adapter API**(`cancel_event`)触发,返 typed cancelled | CI(fake)+ 本机 |
| G8 | owned / attached 的 `close()` 所有权正确(owned 杀进程、attached 不杀用户 MATLAB)、`close()` 幂等 | CI(fake)+ 本机 |
| G9 | 连续两轮 `start → sim → close` 无新增残留 MATLAB 进程,**按公开 `matlabProcessID` 验**(owned PID 轮询消失;attached 关后按名能重连证用户会话仍在) | 本机 |
| G10 | `ruff check` / `ruff format --check` / `mypy core/ adapters/ features/ api/`(经 matlab override)/ 全 `pytest -v`(Engine 集成 skip、fake 单测跑)/ `check_repo_hygiene.sh` 全绿 | CI + 本机 |

**R6 报告须粘贴显式证据表**(R1 P1-6):`sys.executable` / Python version / `matlabengine` version / `matlab.__file__` + distribution location / MATLAB release+update / Simulink version+license probe / startup latency / 超时时 `cancel()` 返回值 / 取消后 session health probe / owned·attached PID 与关闭结果 / unit+integration+全 pytest 汇总 / `git diff --stat origin/main`。不许只写"本机通过"。

**本卡只做确定性 substrate 测试,不引入 b3 的 case evaluator / 产品质量判分**(那是 b3,见定稿 §5)。

---

## 依赖

- **本机必须装并可许可使用 MATLAB R2026a + Simulink R2026a**(R1 P0-1:G4 要真实 `sim`,而 `sim` 属 Simulink;**仅 MATLAB Engine 可用不足以过 b2-0**)。PM/Codex 机已有 MATLAB R2026a(`.mltbx` 装卸早跑通过);Simulink 安装 + 许可由 G0b 探针确认。
- **不依赖 b1(TASK-511)**——两者并行。
- 不依赖 diagnostic 契约/客户端任何改动。

---

## 实施约束(全程)

- **同步实现 + 调用侧 to_thread**:substrate 适配器**同步**(照 sentence_transformer 先例),文档注明"callers bridge with `asyncio.to_thread`";b2-0 本身不接服务,但适配器形态须让 b2-1 能照 decision 11"每服务恰一处 to_thread"接入。
- **超时/取消走 Engine future,非 Python 线程层**:见 §做什么-1(`background=True` → `result(timeout)` → `cancel()`);同步 `eng.sim()` 塞进 `to_thread` 时,Python 侧超时**不等于** MATLAB 侧取消、会留长跑 Engine,故取消必须在 Engine 层做。
- **单会话并发模型**(R1 P1-2 + R1 P1-4):一个 session 实例同一时刻只允许一个 in-flight MATLAB 调用——**检测到已有 in-flight 即立即抛 `MatlabEngineBusyError`**;**不在 adapter 内做隐式锁等待/排队**(排队属队列策略,会隐藏等待时间/超时起点/取消对象/会话饥饿,留 b2-1 的 pool/lifespan 层定)。不得对线程安全作隐含假设;共享 MATLAB 同一时刻也不得被重复连接多次。
- **context manager 不掩盖原异常**(R1 P1-3):块内已抛执行异常、随后 close 又失败时,`__exit__` **不得**用关闭异常替换原始执行异常;关闭失败只记脱敏元数据 + 标 session broken;仅块内无异常时才允许抛 typed close error。
- **不 per-request 启动 Engine**(§地基-9 + 定稿 §2-8):适配器 API 须支持 b2-1 做会话复用/池化,而非每请求 `start_matlab`。
- **延迟导入**:`matlab.engine` 只在函数体内 import,模块顶层不 import(护 collection)。
- **mypy**:用 `["matlab","matlab.*"]` override,**禁行内 `# type: ignore`**(warn_unused_ignores 陷阱)。
- **typed error 不暴露原文,但不等于销毁证据**(R1 P1-5):**b2-0** —— `__str__`/`repr`/`reason_code`/日志均不含原始 MATLAB 文本、不对外暴露 SDK 异常,重抛用 `from None`(与全仓 metadata-only 日志一致);**但 b2-0 不得在 adapter 边界把原始诊断信息不可逆丢弃**——b2-1 最终要解释真实 MATLAB 报错,届时可另建受控、敏感、不可日志化的 diagnostic payload(经脱敏/用户确认后进解释链)。b2-0 只保证"不暴露/不日志化",不保证"永久销毁"。
- **matlabengine 不进默认 requirements**:仅 `requirements-matlab-r2026a.txt` + 文档化环境装配。
- **git 纪律**:实施时从 **`main`(#109)切新分支**(如 `task/TASK-512-engine-substrate`),**不在当前 `chore/task-510-index-accept` 上动**;禁直接改 main;完工 03 索引 🔲→🔍,PM 合并后→✅;R6.1 `git diff --stat origin/main` 与文件清单一致。
- **行尾 / 字节级**:按 **`20260602-08-pm-verify-git-and-preserve-line-endings.md`**(R1 P0-6 更正 v0.1 误引的 decision 18)保 CRLF/LF 一致,防整文件被行尾重写。
- **logger**:按 decision 11 禁 `logger.exception`(用 `logger.error` + 结构化字段,照现有 `diagnostic_service.py` / `chat_service.py` 风格)。

---

## 挂起 seam(留 b2-1,本卡不锁)

- Engine 进程生命周期落点(per-request 禁;pooled vs lifespan-managed 由 b2-1 定)。
- Engine 采集数据如何接进 b1 解释层 + 是否扩 diagnostic 契约 vs 新建 kind(b2-1,走 decision 13)。
- 采集数据体积 vs 32KB 上限(b2-1/b3,走独立结果通道或有界摘要,见定稿 §2-6)。

---

## 关联决策

decision 23 §2.2(v0.3-b 验收门,经定稿 §5 delta 校准)/ **decision 11**(异步桥接 + logger 禁令)/ decision 13(schema-sync,本卡不触发但 b2-1 会)/ **`20260602-08`(PM 核 git + 保行尾;R1 P0-6 更正 v0.1 误引的 decision 18 —— decision 18 实为 ProjectOverview API serialization boundary,与行尾无关)** / decision 12 v0.4(双 AI 互审)/ **v0.3-b 拆分定稿**(`/mnt/user-data/outputs/v0_3b-split-final-skeleton.md`,§2 不变量 / §4 b2-0 定义)。

---

## 修订历史

- **v0.1 草案(2026-06-21)**:据 `origin/main` #109 b2-0 取证起草;含 4 个待锁设计点(A substrate 落点 / B core 接口时机 / C config flag 时机 / D CI 跳过机制)交 R1/R6。
- **v0.2 二修(2026-06-21)**:吸收 **R1 一审 6 P0**(P0-1 PyPI pin 事实更正 / P0-2 超时取消锁 Engine future + 异常表冻结 / P0-3 `start_owned`·`connect_shared` 所有权语义 / P0-4 代表性门锁真实 `sim` / P0-5 测试分两层 + CI fake 单测 / P0-6 行尾决策引用号更正)+ **R6 一审 3 P0**(本地强制跑不许 skip / 超时取消走 future / 代表性门锁 `sim`,与 R1 重合)+ **拍死 A–D 设计点** + 并入 **R1 P1**(单会话并发 / context manager 不掩盖原异常 / `reason_code` 不泄漏原文 / mypy 连根包 / `make test-engine` 升交付物 / R6 证据清单 / 验收门重排 G0–G10 消计数漂移 / "服务进程路径"表述收窄)。
- **v0.3 三修(2026-06-21)**:吸收 **R1 二审 3 P0**(P0-1 依赖补 Simulink + 新增 G0b 能力门 + `MatlabEngineCapabilityError` / P0-2 取消的对外调用契约 `run_simulation(..., cancel_event)` 短周期轮询、堵"fake future 假通过 G7" / P0-3 超时回收状态机 `done()` 先判 + 有界 `cleanup_grace_s` + owned/attached fallback + `matlabProcessID`、并把生产级 startup timeout 从 G2 移至 b2-1)+ **两边 P1/P2**(R6 P1 + R1 P1-3 集成守卫写伪代码、env 已设不许 importorskip 掩盖 / R6 P1 + R1 P1-2 shared 会话自建自清 / R6 P2 G0 加 distribution location / R1 P1-1 确定性 fixture 钉死 / R1 P1-4 并发立即 BusyError 不排队 / R1 P1-5 隐私"不暴露≠不可逆销毁"保 b2-1 证据 / R1 P1-6 R6 证据表)+ **版本号实测注意**(本机 setup.py `26.1` vs PyPI `26.1.12` → 以装后 metadata 为准)。**A–D 二审仍全 PASS;待 R1 定向三审(只看 Simulink 前置 / 取消 API / 回收状态机,不全文重审)+ R6 轻核。**
