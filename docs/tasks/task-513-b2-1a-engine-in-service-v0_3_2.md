# TASK-513:MATLAB Engine 接入服务运行时(v0.3-b / b2-1 块 A:机制层)

## 状态
🔲 未开始 · **v0.3.2(ACK 终态)**。GPT 终审「有条件通过」的 2 个 P0 + 3 项 P1 裁决已写入;Codex 终审 ACK。**无下一轮审查** —— 派单前仅需填入真实 TASK-512 merge commit(Stage 0),即可派 Codex。

> **审查到此收口**:R1 一/二/三审 + 终审、Codex 同步审,全部「方向通过、定点修、未返工重写」。终审两 P0(启动全链同 deadline + `wait_for(to_thread)` 改 retained-task)+ 三 P1(owned 固定走 `from_connected_owned` factory / 唯一名 hex / `{"development","test"}` 字面)已落。PM 授权 `runtime.py` 加该 factory(纯新增)。

---

## 编号与拆分(待对 live 索引核)
- 提议 **TASK-513**(派单前 `git show origin/main:docs/03_TASK_INDEX.md | grep "TASK-51[123]"` 复核 513 空)。
- **b2-1 拆 A / B**:本卡 = **块 A(运行时机制层)**;**块 B(采集→解释)** 另起,必经 PM 拍 + R1 审 + decision 13(卡尾预告)。
- **定义来源声明**:b2-1 权威定义(`v0_3b-split-final-skeleton.md` §4)架构师未能读取;范围据交接 §5-3 + TASK-512 seam + 全文取证 + 本机 spike 重建,靠窄三审校正。

---

## 基线与前置(R1 P0-1 一审 / 二审 P1-5)
- 块 A **不依赖 b1**(511 仍 🔍,b1 代码在 main 但本卡不用)。
- 唯一前置:**TASK-512 merge commit 是 `origin/main` 祖先**(Stage 0 验,**派单时填真实 commit,不留 `<占位>`**)。
- **从派单时最新 `origin/main` 开分支**,禁旧死 hash。

---

## 背景与定位
- v0.3-b:`T0 → b1 ∥ b2-0 → b2-1 → b3`;b2-0 substrate 已合并但不接服务运行时。块 A:让 Engine 以受控生命周期活在服务进程内、经窄抽象取用、flag + APP_ENV 守门,闭合 R1 P1-1 悬念(不 per-request / lifespan 复用 / 关闭回收 / 启动有界)。
- **能力边界(精确口径,R1 二审 P2)**:
  - 本卡做到 **「单进程 · 单 worker · development/test 包络内」的完整生命周期机制**(有界启动 + 启动卡死回收 + 关闭回收)。**P0-6 的 startup reaper 债在本卡清。**
  - **平台约束(spike 实证,诚实标注)**:启动所有权/回收的落地形态依赖 `matlab.exe -wait` + Windows `taskkill /T` + 自起 `shareEngine`,**当前为 Windows-only、仅在本机(PM/Codex 机)实测**;跨平台/CI 不覆盖(本就 flag + APP_ENV 挡 + CI 无 MATLAB)。非通用跨平台生命周期。
  - **feature 仍不上 production**:`matlab_engine_enabled` 限 `APP_ENV ∈ {development,test}`(DP-A3);**bridge 能力 production 解封仍由 seam 把关(不变量 14)**。**「生命周期机制完整」≠「bridge 功能可上线」**,卡内不得宣称后者。

---

## 实测地基(`origin/main` cfe7276 + 本机 spike;Codex 实施前复核)
1. **`lifespan` 现范式**(`api/main.py`):`async with AsyncExitStack() as stack`;**已有 `await asyncio.to_thread(_build_embedder, ...)`** 先例;`stack.push_async_callback(...)` 注册 `aclose`;失败抛 typed。Engine 照此接。
2. **DI 范式**(`api/dependencies.py`):经 `request.app.state.X` + `getattr(..., None)` 兜底;**`get_matlab_bridge_explanation_service` 在 None 时抛 `BridgeExplanationUnavailableError`(不返 None)= 活样板**。无 module-global。
3. **ABC 范式**(`core/interfaces/llm_provider.py`):`ABC + @abstractmethod` + docstring;接口类名以 `Provider/Service/...` 结尾(宪法)。
4. **adapter**(`adapters/matlab_engine/runtime.py`):`MatlabEngineSession` 同步;`start_owned`、`connect_shared(name)`、`run_simulation`、**`health_probe() -> bool`**、`close()` 幂等、公开 `matlab_process_id`、模块级 `_terminate_process(pid, timeout_s)`;`matlab.engine` 延迟导入。
5. **异常**(`core/domain/exceptions.py`):`MatlabEngineError` + 9 子类 = 10 个;**无 disabled leaf**。
6. **config**(`app/config.py`):`app_environment`(alias `APP_ENV`)、`matlab_bridge_enabled=False`;**无 `matlab_engine_enabled`**。
7. **app 接线**:`_validate_matlab_bridge_settings()`(`matlab_bridge_enabled and APP_ENV ∉ {dev,test}` → `RuntimeError`)。
8. **`.env.example`** 末尾有 `APP_ENV=production` + `MATLAB_BRIDGE_ENABLED=false`;**`test_config.py` 的 `ENV_KEYS` 漏列 `APP_ENV`/`MATLAB_BRIDGE_ENABLED`**(既有缺口,本卡加新 env 时一并补)。
9. **依赖**:`requirements-matlab-r2026a.txt = matlabengine==26.1.12`。
10. **本机 spike 实证(路 A 落地形态;P0-1 据此)**:
    - 官方 `start_matlab(background=True)` 的 `FutureResult` 公开属性仅 `cancel/cancelled/done/result`,**`result()` 成功前无任何公开途径取 PID**(实证,非文档)。
    - **可行形态**:`Popen([matlab.exe, "-wait", "-nodesktop", "-nosplash", "-logfile", <owned log>, "-r", "matlab.engine.shareEngine('<unique>')"])`,**启动瞬间即持有 `proc.pid`(不依赖连接成功)**;轮询 `find_matlab()` 见唯一名后连接(**正式实现连接用有界 `connect_matlab(name, background=True)` + `result(timeout)`,见 §核心机制**)。
    - **`-wait` 是命门**:裸启动 `Popen` PID 很快不可查;`-wait` 下 `proc.pid` 全程稳定、可作进程树根。
    - **未连接也能回收**:连接一直失败时,`taskkill /PID <proc.pid> /T /F` 杀树 + 验 PID 消失,闭合「启动卡死」回收。
    - **隔离实证**:自起树与用户 MATLAB 树 **PID 交集为空**,杀自起树用户那个存活。**只杀自己保存的 PID 树、禁按进程名全杀。**
    - **坑**:`eng.quit()` 返 OK 后进程树仍存活约 8s → shutdown 必须「优雅 quit + 等有限时间 + 仍在则杀树」。

---

## Stage 0 — 取证/基线检查(强制,R1 P0-1 + 二审 P1-5 + decision 15)
```bash
git fetch origin
git status --short                                            # 必须为空,否则停手报 PM
git rev-parse origin/main
git merge-base --is-ancestor <填真实 TASK-512 merge commit> origin/main   # 必须为真
git show origin/main:docs/03_TASK_INDEX.md | grep -n "TASK-51[123]"        # 确认 513 空
git switch -c task/TASK-513-engine-in-service origin/main
```

---

## 设计点裁决(R1 一审已拍 + 二审收口;本卡遵此,不翻案)
| 设计点 | 裁决 |
|--------|------|
| **A/B 拆分** | 通过 |
| **DP-A1 ABC** | **最小 use-port**;**改名 `MatlabEngineProvider`**(宪法:`Provider` 结尾;R1 二审 P1-5)仅 `health_probe() -> None`;**不迁 `MatlabSimulationResult`**;**不暴露 acquire/release/close**(所有权归 composition root + concrete adapter)。 |
| **DP-A2 生命周期** | lifespan eager-start、**单会话 = 每应用进程一个**(非全局)、不建池、不 lazy first-use;所有阻塞调用走 `to_thread`;`AsyncExitStack` 回收。 |
| **DP-A3 flag 护栏** | `matlab_engine_enabled ⇒ matlab_bridge_enabled` 且仅 `APP_ENV ∈ {dev,test}`,否则启动前 fail-closed。 |
| **P0-6 = ①(PM 拍)+ 路 A(PM 拍)** | 纳入有界启动 + 启动卡死按**自建 PID 树**回收(见下 §核心机制),reaper 债本卡清(Windows/dev-test 包络内)。 |

---

## 核心机制(P0-1:自建启动所有权 + 有界连接 + handle 跨 lifespan 保留;据 spike 实证 + 三审收口)
> 三审 P0-1 两个阻断:① 同步 `connect_matlab(name)` 自身可能无界卡死 → 整个 timeout/回收分支执行不到;② `start_owned_bounded` 只返回 session → 启动树根 `proc.pid` 丢失,shutdown 无主可回收,且 `connect_matlab` 出来的 session 默认是 **ATTACHED**(TASK-512 冻结:attached 的 `close()` 只断连、永不杀进程),与本卡「杀自存 PID 树」shutdown 语义相反。本版全部收口。

**落点 + 所有权接缝(GPT 终审固定,取消二选一)**:`adapters/matlab_engine/` 内**新增** `owned_startup.py`,与 `runtime.py` 解耦。owned session **固定经 `runtime.py` 新增的最小 factory** 构造:
```python
MatlabEngineSession.from_connected_owned(engine, *, matlab_process_id=matlab_pid)
```
**理由(终审)**:`MatlabEngineSession` 已持 ownership/state/close 真值,在 `owned_startup.py` 外部另造 owned 会形成第二套状态真值;且 TASK-512 冻结了 owned/attached 不同关闭行为。该 factory **纯新增、不改现有 `start_owned`/`connect_shared`/`close`/`run_simulation` 逻辑与签名**——PM 已授权。**仅 composition root 受 flag 保护地函数内延迟 import 它。**

**返回组合对象(三审 P0-1②,写死)**:`start_owned_bounded(...)` **不返回光秃 session**,返回:
```python
@dataclass(slots=True)
class OwnedMatlabEngineRuntime:
    session: MatlabEngineSession        # ownership=owned（见上 factory 接缝）
    provider: MatlabEngineProvider      # 窄接口，进 app.state
    startup_proc: subprocess.Popen      # spike 的 -wait 启动树根，持有 proc.pid
    share_name: str
    def terminate_tree(self) -> bool: ...  # taskkill /PID startup_proc.pid /T /F + 验消失
```
此对象由 lifespan 的 exit-stack callback **持有到 shutdown**;`app.state` 仍只暴露 `runtime.provider`。

**启动状态机(确定,不留自然语言;**全链共用一个总 deadline**,`OwnedMatlabEngineRuntime` 全程持 `proc.pid`)**:
```
deadline = time.monotonic() + startup_timeout_s        # 总 deadline,贯穿等共享名→连接→取 PID
connect_future = None                                  # 预置,防失败分支访问未建变量
0. platform guard:  if sys.platform != "win32": raise MatlabEngineUnavailableError(reason_code="owned_startup_unsupported_platform")
1. sdk first:        _load_matlab_engine_module() 成功后【才】允许 Popen（否则先起 MATLAB 再发现 SDK 缺失 = 制造残留）
2. launch:           proc = Popen([matlab.exe, -wait, -nodesktop, -nosplash, -logfile <owned-temp>, -r shareEngine('<unique>')])
                     立即保存 proc + proc.pid（= 启动树根，不依赖连接成功）
3. bounded connect:  在 deadline 内轮询 find_matlab() 见 <unique>
                     → connect_future = connect_matlab(<unique>, background=True)
                     → engine = connect_future.result(timeout = deadline - now)   # 有界
4. bounded pid attestation【必须同受 deadline 约束】:
                     → pid_future = engine.feval("matlabProcessID", nargout=1, background=True)
                     → matlab_pid = int(pid_future.result(timeout = deadline - now))   # PID 探针卡住也有界
                     → 验证 matlab_pid 属于 proc.pid 进程树；通过才进 ready
                     （删除 v0.3 的「可选 feature('getpid')」；matlabProcessID 是公开接口）
5. construct owned:  matlab_pid 验证通过 → MatlabEngineSession.from_connected_owned(engine, matlab_process_id=matlab_pid)
                     （固定走该 factory,禁复用 connect_shared 的 attached;见 §所有权接缝）
                     → 组装 OwnedMatlabEngineRuntime 返回；状态 ready
任一阶段耗尽 deadline（等共享名 / 连接 / 取 PID 任一）→ 统一 owned-tree cleanup,reason_code = startup_timeout_reaped:
                     → if connect_future is not None: connect_future.cancel()   # best-effort,仅 future 已建时;返回值【不能】替代 PID 树回收证明
                     → terminate_tree()：taskkill /PID proc.pid /T /F（只杀自存 PID 树，禁按名全杀）
                     → bounded cleanup_grace 内【独立】验证 proc.pid 树消失
                     → 抛 MatlabEngineTimeoutError("startup_timeout_reaped")
仅「成功取得 PID 但归属不符」: 同样 cleanup,但抛 MatlabEngineStartupError("startup_pid_attestation_failed")
连接失败（非超时）: 同样 cleanup,抛 MatlabEngineStartupError("startup_connect_failed")
reaper 失败（杀后 PID 仍在）: 状态 broken,记脱敏 metadata,抛 MatlabEngineStartupError("startup_reaper_failed")
```
- **唯一名(终审固定)**:`share_name = f"task513_{uuid.uuid4().hex}"`(**用 hex、不带连字符** —— MATLAB 共享名须合法变量名)。注意 MathWorks:**若该 shared 名已存在,新会话会退回默认 shared name** → 故必须靠步骤 4 的 PID 归属验证确认连到的是自己起的那个,而非撞名连错。
- **隔离铁律**:回收**只针对自存 `proc.pid` 树**;**禁止**「比较启动前后 MATLAB 进程列表后盲杀」(机器上可能有用户 MATLAB)。
- **平台**:`-wait` + `taskkill /T` 为 Windows 形态(spike 实证);非 Windows 由步骤 0 代码级 fail-closed(不只文档说明,见 §约束 + G-A14)。
- **owned logfile**:`-logfile` 落**受控临时目录**、文件名不含用户输入、shutdown 后默认删;含本机路径/license/startup 信息,**禁贴内容**,R6 调试若保留只在证据表记路径元数据。

---

## 薄封装(P0-2:`bool → None/typed`,两审强制,无「或」)
现有 `MatlabEngineSession.health_probe() -> bool` 与 ABC `-> None` 不兼容,且 `False` 易被忽略当成功 → **必须薄封装,禁让 session 直接继承 ABC**:
```python
# core/interfaces/matlab_engine_provider.py
from abc import ABC, abstractmethod

class MatlabEngineProvider(ABC):
    """Service-facing health check on the app-managed MATLAB Engine session.

    Session ownership (start / close / PID / lifecycle) is NOT exposed here;
    it stays in the composition root and concrete adapter. Blocking calls MUST
    be bridged with asyncio.to_thread by the caller.
    """
    @abstractmethod
    def health_probe(self) -> None:
        """Raise a typed MATLAB Engine error when the session is unhealthy."""
        ...
```
```python
# adapters/matlab_engine/ (薄封装,新增)
class SessionBackedMatlabEngineProvider(MatlabEngineProvider):
    def __init__(self, session: MatlabEngineSession) -> None:
        self._session = session
    def health_probe(self) -> None:
        if not self._session.health_probe():
            raise MatlabEngineSessionError("health_probe_failed")
```
- composition root 保留 concrete `MatlabEngineSession`(用于 close / PID / 所有权);**`app.state` 只暴露窄化的 `MatlabEngineProvider`**。
- **P0-2 核销单测(三审指定 3 条)**:底层 `True` → provider 返回 `None`;底层 `False` → 抛 `MatlabEngineSessionError`、reason_code 固定;底层**已抛 typed Engine error** → 原样传播、不二次包装。

---

## 异常四态(R1 二审 P1-2;消除 disabled/unavailable/startup/session 混淆)
- **新增 `MatlabEngineDisabledError`**(`core/domain/exceptions.py`,**纳入文件清单 + 测试**),区分:
  | 情况 | 异常 |
  |------|------|
  | flag false / 未装配 | `MatlabEngineDisabledError("matlab_engine_disabled")` |
  | flag true、SDK 缺失 | `MatlabEngineUnavailableError`(现有) |
  | 非 Windows 进启动路径 | `MatlabEngineUnavailableError(reason_code="owned_startup_unsupported_platform")`(三审 P1-3,代码级 fail-closed) |
  | flag true、启动失败/超时 | 启动超时 → `MatlabEngineTimeoutError`;非超时启动失败 → `MatlabEngineStartupError`(R1 二审 P1-1 要求二者分明) |
  | flag true、会话失效 | `MatlabEngineSessionError`(现有) |

---

## 有界启动 API / 预算 / reason-code(三审 P1-1/P1-2;**冻结,不留实现自决/不留「Codex 实测填」**)
- 签名(final,落 `owned_startup.py`):
  ```python
  def start_owned_bounded(
      *,
      startup_timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S,
      cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
      poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
  ) -> OwnedMatlabEngineRuntime: ...
  ```
- **时间常量冻结**(模块常量;据 spike 连接 ~11.7s 留足余量;R1 ACK 可微调但本卡给定值,不交 Codex):
  ```
  DEFAULT_STARTUP_TIMEOUT_S = 90.0     # 覆盖冷启动 + 连接,远超 spike ~11.7s
  DEFAULT_CLEANUP_GRACE_S   = 10.0     # taskkill 后验进程消失的有界窗口
  DEFAULT_POLL_INTERVAL_S   = 0.5      # find_matlab / 验证轮询间隔
  HEALTH_PROBE_TIMEOUT_S    = 15.0     # lifespan 启动后 health_probe 的有界超时
  ```
  全部 `> 0` 校验。
- **reason-code 矩阵冻结**(稳定串,不含原始 MATLAB 文本;异常构造**按仓库现有 constructor 真实签名书写,不假设位置参数即 reason_code** —— Codex 实施时照 `core/domain/exceptions.py` 现有 `MatlabEngine*Error(...)` 调用形态对齐):
  | 状态 | 异常 | reason_code |
  |------|------|-------------|
  | 启动超时、已回收成功 | `MatlabEngineTimeoutError` | `startup_timeout_reaped` |
  | 回收失败(杀后 PID 仍在) | `MatlabEngineStartupError` | `startup_reaper_failed` |
  | 连接失败(非超时) | `MatlabEngineStartupError` | `startup_connect_failed` |
  | PID 归属验证失败 | `MatlabEngineStartupError` | `startup_pid_attestation_failed` |
  | health probe False | `MatlabEngineSessionError` | `health_probe_failed` |
  | health probe 卡死、已回收 | `MatlabEngineTimeoutError` | `health_probe_timeout_reaped` |
  | health probe 卡死、回收失败 | `MatlabEngineStartupError` | `health_probe_reaper_failed` |
  | 非 Windows | `MatlabEngineUnavailableError` | `owned_startup_unsupported_platform` |
  | SDK 缺失 | `MatlabEngineUnavailableError` | (沿用现有 unavailable reason_code) |
  | flag 关/未装配 | `MatlabEngineDisabledError` | `matlab_engine_disabled` |

---

## 范围(必须做 —— 块 A,v0.3.2)
- [ ] **新 ABC** `core/interfaces/matlab_engine_provider.py`(`create_file`)+ **更新 `core/interfaces/README.md`**(R1 二审 P1-5)。
- [ ] **薄封装 + 自建启动所有权**(`adapters/matlab_engine/owned_startup.py`,**新增**):`SessionBackedMatlabEngineProvider` + `start_owned_bounded(...) -> OwnedMatlabEngineRuntime`(有界连接 + PID 探针同 deadline + 组合对象 + SDK-first + Windows guard,见 §核心机制)。owned 构造**固定经 `runtime.py` 新增的 `from_connected_owned(...)` factory**(纯新增,PM 授权)。
- [ ] **异常**:新增 `MatlabEngineDisabledError`(`core/domain/exceptions.py`)。
- [ ] **flag**(`app/config.py`):`matlab_engine_enabled: bool = Field(default=False, validation_alias="MATLAB_ENGINE_ENABLED")` + 校验 `engine ⇒ bridge` 且 `APP_ENV` 仅 **`{"development", "test"}`**(实现口径用真实字面,非缩写「dev/test」)。
- [ ] **`.env.example`** 增 `MATLAB_ENGINE_ENABLED=false`;**`test_config.py` `ENV_KEYS`** 补 `MATLAB_ENGINE_ENABLED`(+ 补漏的 `APP_ENV`/`MATLAB_BRIDGE_ENABLED`)+ 默认/override/清理。
- [ ] **lifespan 接 Engine + 有界 health probe**(`api/main.py`,composition root;**GPT 终审 P0-2:`wait_for(to_thread(...))` 不是真有界 Engine 调用,改 retained-task + 超时杀树 + 消费迟到**):flag 开 + APP_ENV 合规 → `AsyncExitStack` 内:
  ```
  runtime = await asyncio.to_thread(start_owned_bounded, ...)
  stack.push_async_callback(_close_owned_runtime, app, runtime)   # 成功立即注册回收
  probe_task = asyncio.create_task(asyncio.to_thread(runtime.provider.health_probe))
  done, _ = await asyncio.wait({probe_task}, timeout=HEALTH_PROBE_TIMEOUT_S)
  if not done:                                    # probe 卡死:杀 owned 树 + 消费迟到 + typed
      reaped = await asyncio.to_thread(runtime.terminate_tree)
      probe_task.add_done_callback(_consume_task_result)
      raise (MatlabEngineTimeoutError("health_probe_timeout_reaped") if reaped
             else MatlabEngineStartupError("health_probe_reaper_failed")) from None
  probe_task.result()                             # 正常:取结果（异常会在此抛出，被上面注册的回收兜）
  app.state.matlab_engine_provider = runtime.provider   # 组合对象留 callback,app.state 只暴露窄接口
  ```
  **仅此处受 flag 保护函数内延迟 import 具体 adapter**。
- [ ] **shutdown 清理 + state 清空**(P1-3 + **终审:close 本身也会卡,不只 busy**):`_close_owned_runtime` 同样用 **retained-task 模式** —— `quit`/`close` 起 task + 有界等待;grace 内未完成**或** busy(`MatlabEngineBusyError`)→ `runtime.terminate_tree()` 杀 `proc.pid` 树(spike 坑:quit 后约 8s 仍活)→ 验 PID 消失 → **消费迟到 task 结果**(避免未观察异常);**`finally` 删/置空 `app.state.matlab_engine_provider`**;关闭失败只记脱敏 metadata、不传播出 exit stack、不记 `str(exc)`。
- [ ] **DI**(`api/dependencies.py`):`get_matlab_engine_provider(request) -> MatlabEngineProvider`,flag 关/未装配抛 `MatlabEngineDisabledError`(照样板,不返 None)。
- [ ] **测试**(见验收 + 文件清单)。

## 不做(明确排除)
- ❌ 块 B 任何部分;不接采集、不跑用户模型、不搬运真实报错文本。
- ❌ 不碰 b1 已验收产物及其护栏。
- ❌ **不改对外 Pydantic/JSON/API 契约**(新 ABC/新异常是内部契约,可加);**不触 decision 13**。
- ❌ 不动 `matlab_bridge_router` 顺序与 `MAX_BRIDGE_BODY_BYTES`。
- ❌ 不改 `runtime.py` 现有 `start_owned`/`connect_shared`/`close`/`run_simulation` 逻辑与签名(仅**可能新增**一个 `from_connected_owned` factory)。
- ❌ **不得复用 `connect_shared()` 得到的 attached session 当 owned**(attached 的 close 不杀进程,与本卡 shutdown 语义相反);owned 构造必须经明确接缝。
- ❌ 不建池、不 lazy first-use;**不支持多 worker / `--reload`**。
- ❌ **不按进程名全杀 MATLAB**(只杀自存 PID 树);不动客户端 `.m`。

---

## 配置真值表(R1 一审 P1-6 + **二审 P0-1 修正**:拆「App 启动」与「Engine 启动」两列)
> 二审指出:`engine=false` 时,**App 能否启动仍受现有 `_validate_matlab_bridge_settings()` 约束**(`bridge=true` 且 production 时 App 本就 fail-closed),不能笼统写「通过」。

| engine | bridge | APP_ENV | App 启动 | Engine 会话 |
|--------|--------|---------|----------|-------------|
| false | false | 任意 | 启动 | 不启动、不 import adapter |
| false | true | dev/test | 启动 | 不启动、不 import adapter |
| false | true | production/缺省 | **fail-closed**(现有 bridge 校验) | — |
| true | false | 任意 | **fail-closed**(engine⇒bridge) | — |
| true | true | production/缺省 | **fail-closed** | — |
| true | true | dev/test | 启动 | 进入有界启动 |
| true | true | dev/test、SDK 缺失 | `create_app` 成功 / lifespan startup **fails typed unavailable** | typed unavailable（无残留进程） |

---

## 验收门
- [ ] **G-A1**:flag 关 app 可导入/启动、不起会话、**不 import 具体 adapter**(测在**新 subprocess** 跑,不靠可能被污染的 `sys.modules`,二审 P1-5);CI 无 matlabengine 导入不炸。 [CI]
- [ ] **G-A2**:flag 开 + APP_ENV 合规,lifespan 有界起会话、shutdown 回收;两轮起停按 `proc.pid` 树验无残留。 [本机]
- [ ] **G-A3**:配置真值表逐行成立(含两列 App/Engine 拆分)。 [CI/fake + 本机]
- [ ] **G-A4**:allowlist import/AST 扫描 —— `core/`/`features/`/route/普通 consumer 无 `import adapters.matlab_engine`;仅 composition-root allowlist 允许(非全仓零匹配)。 [CI]
- [ ] **G-A5**:本机经 ABC 取 `MatlabEngineProvider` 并 `health_probe()` 成功(启动探针只用 health_probe;且**有界**,二审 P1-4)。 [本机]
- [ ] **G-A6**:event loop 不被阻塞(**startup / health probe / close** 均经 to_thread,二审 P2)、同会话跨调用复用、无 per-request startup;不数源码 to_thread 个数。 [CI + 本机]
- [ ] **G-A7 ①+路A(R1 硬证)**:本机制造启动卡死(未 share/连接失败)→ 有界启动超时触发 + **按自存 `proc.pid` 树回收 + 独立验证 PID 真消失**(不靠 `cancel()` 返回值);**同时证不误伤另开的用户 MATLAB**(隔离,spike 第 4 项);连接成功路径**用公开 `matlabProcessID` 验连到的 MATLAB 属 `proc.pid` 树**才进 ready。 [本机]
- [ ] **G-A8 startup 中途失败回收**(P0-5):failure-injection —— 成功后续资源失败→`close` 恰一次;health_probe 失败→`close` 恰一次;原始异常不被 close 异常覆盖;close 失败只记 metadata。 [CI/fake]
- [ ] **G-A9 关闭(retained-task)**:shutdown `close` 用保留任务模式 —— grace 内未完成**或** busy → `terminate_tree` 回收、验 PID 消失、迟到 task 结果被消费、不打断 exit stack(**不只对 busy 兜底,普通 close 卡死也走同路**)。 [CI/fake + 本机]
- [ ] **G-A16 有界 Engine 调用(GPT 终审 P0-2)**:fake 模拟 **health probe 卡死** → 杀 owned 树 + typed(`health_probe_timeout_reaped`);**close 卡死** → 杀树回收;**probe 与 close 不并发操作同一 Engine**;**迟到异常已被消费**(无 "Task exception was never retrieved")。 [CI/fake]
- [ ] **G-A10 app.state 清理/隔离**(P1-3):正常退出后 state 不暴露 provider;health probe 失败后 state 不存在;后续资源失败后 state 不存在;同 app 连续两次 lifespan 不复用已关闭实例。 [CI/fake]
- [ ] **G-A11 异常四态 + reason-code**:按冻结矩阵逐条(disabled/unavailable/timeout/startup·各 reason_code 稳定、无原始文本)。 [CI/fake]
- [ ] **G-A12 接口测试**:ABC 不可直接实例化、stub 可实例化;**薄封装 3 条**(True→None / False→typed+固定 reason_code / 已 typed→原样传播)。 [CI]
- [ ] **G-A14 非 Windows fail-closed**(三审 P1-3):非 Windows 下进启动路径**代码级**抛 `owned_startup_unsupported_platform`,**不执行 `Popen`/`taskkill`**(CI 单测证)。 [CI]
- [ ] **G-A15 有界连接**(三审 P0-1①):`connect_matlab(name, background=True)` + `result(timeout=remaining)`;**模拟连接卡死**证超时仍走 owned cleanup(不卡死)。 [CI/fake + 本机]
- [ ] **G-A13**:`ruff` / `ruff format --check` / `mypy core/ adapters/ features/ api/` / 全 `pytest -v`(Engine 集成 skip、fake 跑)/ `check_repo_hygiene.sh` 全绿;**R6 证 b2-0 原 G0–G10 无回归**。 [CI + 本机]
- **R6 证据表**:`sys.executable` / matlabengine version / lifespan 起停时序 / 有界启动超时触发 + 超时后 `proc.pid` 树回收 + 独立 PID 消失核验 / 隔离(用户 MATLAB 存活) / 两轮无残留 / **各 `to_thread` 调用线程 ID + 同会话跨线程稳定**(二审 P1 / 一审 P1-5;线程亲和问题→升 R2 改专用单线程执行器,不临场改架构)/ b2-0 G0–G10 复跑 / `git diff --stat origin/main` 与文件清单一致。日志只含 startup latency/ownership/state/exception type;禁 startup options、异常正文、原始 MATLAB 诊断文本。

---

## 文件清单(R1 一审 P1-6 + 二审 P1-5;Codex 以 Stage 0 复核)
**生产**:
- `core/interfaces/matlab_engine_provider.py`(新增,`create_file`)
- `core/interfaces/README.md`(修改:登记新接口)
- `adapters/matlab_engine/owned_startup.py`(新增,`create_file`:`OwnedMatlabEngineRuntime` + `start_owned_bounded`(有界连接/组合对象/Windows guard/SDK-first) + `SessionBackedMatlabEngineProvider` + 时间常量;可拆多文件)
- `adapters/matlab_engine/__init__.py`(**修改**:导出薄封装/启动入口)
- `adapters/matlab_engine/runtime.py`(**修改 = 仅新增一个 `from_connected_owned(engine, *, matlab_process_id=...)` factory**,纯新增、不改现有 `start_owned`/`connect_shared`/`close`/`run_simulation` 逻辑与签名;PM 授权,GPT 终审固定)
- `core/domain/exceptions.py`(修改:新增 `MatlabEngineDisabledError`)
- `app/config.py`(修改:flag + 校验)
- `api/main.py`(修改:lifespan 接 Engine + 延迟 import 例外)
- `api/dependencies.py`(修改:`get_matlab_engine_provider`)
- `.env.example`(修改:增 `MATLAB_ENGINE_ENABLED=false`)

**测试**:
- `tests/api/test_lifespan_matlab_engine.py`(新增,`create_file`):G-A1/A2/A3/A6/A8/A9/A10/**A16(probe 卡死/close 卡死/无并发/迟到异常消费)** fake
- `tests/architecture/test_no_concrete_adapter_import.py`(新增或扩,`create_file`):G-A4 allowlist
- `tests/core/interfaces/test_matlab_engine_provider.py`(新增,`create_file`):G-A12 ABC 实例化 + 薄封装 bool→typed
- `tests/core/domain/test_matlab_engine_exceptions.py`(新增或扩):G-A11 四态
- `tests/adapters/matlab_engine/test_owned_startup_unit.py`(新增,`create_file`):fake 启动超时+回收状态机 + **G-A14 非 Windows guard(monkeypatch `sys.platform`,证不调 Popen/taskkill)** + **G-A15 有界连接超时(fake 连接卡死)**
- `tests/adapters/matlab_engine/test_owned_startup_integration.py`(新增,`create_file`):G-A7 真机超时+PID 树回收+隔离+`matlabProcessID` 归属验证(`MXA_RUN_MATLAB_ENGINE=1`)
- `tests/app/test_config.py`(修改):`ENV_KEYS` 补项 + 真值表
- `tests/adapters/matlab_engine/test_runtime_unit.py`(**修改**):补 `from_connected_owned` factory 的最小单测(构造出 `ownership=owned` + 记录 PID);现有 b2-0 测试不改
- `tests/adapters/matlab_engine/test_runtime_integration.py`:不改

**任务卡/索引**:`docs/tasks/task-513-b2-1a-engine-in-service-v0_3_2.md`(本卡,`create_file`);完工更新 `docs/03_TASK_INDEX.md`(🔲→🔍)。

---

## 实施约束(全程)
- **decision 11**:同步实现 + async 侧 to_thread;**任一 async 上下文不得直接调同步阻塞 Engine 方法**(startup / health probe / close 全经 to_thread,且 health probe / 启动有界);**禁 `logger.exception`**(用 `logger.error` + 结构化字段)。
- **单会话 = 每应用进程一个**;**R6 固定 `--workers 1 --no-reload`**,多 worker/reload 不支持。
- **装配 import 真正延迟**:concrete adapter import 在「配置校验通过 + engine flag 真」之后;flag 关测「adapter 未被导入」(新 subprocess 跑)。
- **DI 用 `app.state`,禁 module-global**;flag 关抛 `MatlabEngineDisabledError`,不得 `None`→`AttributeError`。
- **SDK 先于 Popen**(Codex P1):状态机第一步 `_load_matlab_engine_module()` 成功**才**允许 `Popen`(否则先起 MATLAB 再发现 SDK 缺失 = 制造残留)。
- **非 Windows 代码级 fail-closed**(三审 P1-3):`Popen` 前 `if sys.platform != "win32": raise MatlabEngineUnavailableError(reason_code="owned_startup_unsupported_platform")`(不靠 flag/APP_ENV 兜)。
- **owned logfile 生命周期**:`-logfile` 落受控临时目录、名不含用户输入、shutdown 后默认删;**禁贴内容**(含本机路径/license/startup),R6 保留只记路径元数据。
- **隔离铁律**:回收只杀自存 `proc.pid` 树,**禁按进程名全杀**(spike 隔离实证)。
- **行尾/字节级**:照 `20260602-08-...`(行尾决策是它,非 decision 18)。
- **延迟导入**:`matlab.engine` 维持函数体导入;ABC/服务层顶层不 import 具体 adapter。
- **mypy**:沿用 `["matlab","matlab.*"]` override,禁行内 `# type: ignore`。
- **matlabengine 不进默认 requirements**。
- **git**:从最新 `origin/main` 开 `task/TASK-513-engine-in-service`;`git diff --stat origin/main` 与清单一致;完工 🔲→🔍,PM 合并后→✅。
- **隐私**:沿用 b2-0「不暴露/不日志化原始 MATLAB 文本」。

---

## 关联决策
decision 11 / decision 13(本卡不触发,块 B 会)/ decision 15 / decision 12 v0.4(双审 + R5.1 清单)/ **`20260602-08`(保行尾;非 decision 18)** / **TASK-512**(b2-0:§B 补最小接口 + §挂起 seam + G0–G10 不可回归)/ **不变量 14**。

---

## 审查与派发
- **审查收口**:R1 终审 = 有条件通过(本版已补两 P0 + 三 P1),Codex 终审 = ACK。**不再进行下一轮审查**(R1 终审明示)。
- **派单唯一前置**:Stage 0 填入真实 TASK-512 merge commit + `git status --short` 为空 + ancestor 检查通过 → 即可派 Codex。
- R6 真机重点(派单后):G-A7/A15/A16(启动·连接·probe·close 卡死均有界回收 + 隔离不误伤用户 MATLAB)、G-A13 b2-0 G0–G10 无回归、跨 `to_thread` 线程稳定。**派单后由 PM 走 R6 + 看 diff 合并;合并前的审已到 ACK。**
- **Codex 实施提醒(终审)**:`_close_owned_runtime` 不得相信 `session.close()` 返回成功就代表 `-wait` 进程树消失 —— 按「优雅 quit + 有界等 + 仍在则 `terminate_tree()`」走。

## 块 B 预告(不在本卡)
块 B 前提:① 最好取得 skeleton §4;② PM 拍「扩 `diagnostic_kind`/`error_text` 契约 vs 新建 explanation kind」;③ 设计「受控敏感诊断通道」如何在保持 b1 grounding/fail-closed 下容纳自动采集;④ 采集产出体积约束。**块 B 动 b1 已验收护栏 + 契约级 → 必经 PM 拍 + R1 审 + decision 13。**
