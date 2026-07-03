# TASK-311:文档解析 sandbox 大 payload 死锁修复 + 超时兜底补真 · v0.3

> **归属**:MCS 主线基础设施修复(sandbox 由 TASK-202 引入)。**非** paper-to-model 功能卡,占用 311(311-499 缓冲区首位)。
> **状态**:v0.3 · **R1(GPT)方案审 + R6(Codex)可落核 + Stage 0 基线/Windows 探针均已过** · **环境策略已定(Windows 本地 + Linux 靠 CI)** · **待实现到 staged → 亲核 → push**
> **性质**:后端基础设施修复卡(改 `adapters/parser/_sandbox.py` 进程间传输机制 + 补真超时兜底)。**不改对外 schema、不加路由、不碰任何业务逻辑**。走合并前亲核真 diff + 后端真测试(sandbox 有测试框架);**无前端、无截图**。
> **基线**:R6 @ live `origin/main` `35b89e1` 实证(见 §3);Codex Stage 0 已复核基线全对齐 + Windows 探针全绿(见 §8)。
>
> **★ v0.2 → v0.3 环境策略调整(唯一改动,修法本身不变)**:v0.2 的「双环境本地实测」硬门,Codex 本机 Linux 通路打不通(WSL 虚拟化层缺失 vmcompute/hns 服务、需提权重装、不在本卡范围;Docker/gh 均不可用)。改为务实版:
> - **Windows 本地充分测**(Codex 已在 Stage 0 复跑全绿:死锁复现 8000 字、修法探针 8000/80000/1000000 全 ok、真超时掐掉、crash 快速失败 0.5s、临时目录无残留、并发无串、empty()-竞态 30 次无误判)。
> - **Linux 靠 CI 兜**:R6 确认 `.github/workflows/ci.yml` 在 `ubuntu-latest` 跑全量 `pytest -v`(testpaths=["tests"] 含 sandbox 测试),故新增 9 类测试 **push 后 CI 自动在 Linux 执行**。这是 Linux 侧的真实测,只是从「Codex 命令行跑」换成「CI 跑」(CI 每个 PR 本就跑)。
> - **RLIMIT_CPU vs wall-clock 分类(P0-C)做成 Linux-only 测试**:Windows 无 RLIMIT_CPU、测不了;实现成 pytest skip-on-non-linux,在 CI 的 ubuntu 上验证 CPU-spin→timeout / deadline 前异常退出→failed。
> - **注意**:CI 不是跑 `make check` 整包,而是拆开跑 ruff/format/mypy/pytest/hygiene。故合并前 Codex **本地仍须跑完整 make check 到「All checks passed!」**(CI 拆跑 ≠ make check 全绿,两者都要过)。
>
> **★ v0.1 → v0.2 双审收敛(3 项,仍有效)**:
> - **P0-A(R1 挖出真漏洞,官方文档背书)**:v0.1 用 `process.is_alive()==False and result_queue.empty()` 判「无结果」——`multiprocessing.Queue.empty()` 在多进程语义下**不可靠**(put 后有极短延迟、结果还在管道里时 `empty()` 可能返 True),会把**已成功的解析误判成失败、丢结果**。v0.2 改为「子进程死后做 bounded grace drain(再短取几次)、仍无果才判失败」,**禁止用 empty() 当 correctness 判据**(§4.1 重写)。
> - **P0-B(R1 加固)**:真超时 / 清理进程加 **kill escalation**(`terminate → join → kill → join`,SIGTERM 可能被忽略/延迟,wall-clock 兜底不能只停在「请求退出」);**拿到结果后即便为清理杀子进程,也不得把成功改判成 timeout**(§4.1 + §4.3)。
> - **P0-C(R1+R6)**:Linux `RLIMIT_CPU`(SIGXCPU)与父进程 wall-clock deadline 是**两套超时**,按 `process.exitcode` 分类:deadline 到且 alive→timeout;exitcode==-SIGXCPU→timeout;deadline 前无结果异常退出/OOM/segfault→failed(§4.3)。做成 Linux-only 测试靠 CI 验(见上「v0.2 → v0.3」)。

---

## 1. 这张卡是什么 / 不是什么

**是**:修 `run_in_sandbox` 一个 **join-before-drain 死锁**——当解析结果(`ParsedDocument`,主要是 `raw_text`)超过约 8000 字符时,子进程 `result_queue.put(...)` 后无法退出(大 payload 卡在管道 feeder 缓冲区、父进程还没 drain),父进程 `process.join(timeout)` 先等子进程结束、之后才 `queue.get_nowait()`,父子互等到 30s 超时,报 `document_parse_timeout`。**修法 = 把「取结果」提到「回收进程」之前**(带 deadline 循环取 + 同时监控子进程存活),任意大小结果都能顺畅回传。

**顺带补的一件事(必须一起做)**:那 30s timeout 因为死锁**从未作为真正的解析耗时上限生效过**(一直被死锁吃掉)。死锁修好后,timeout 必须补成**真兜底**:合法但巨慢 / 恶意的文件,解析真超时 → `terminate()` 子进程 + 报 `document_parse_timeout`。

**动机**:用户真实要用的中文论文(内容较多,解析出上万字)撞上 8000 字阈值,**全部卡在解析第一步、进不了系统**。这不是个例——**任何内容较多的 PDF 或 DOCX 都会被卡**(PdfParser 和 DocxParser 走同一 sandbox)。论文进不来,paper-to-model 整条线是空的。这是基础中的基础。

**不是**:
- ①**不改传输机制的选型**为 Pipe / Manager / 临时文件(经 R1/R6 评估,drain-before-join 是最小根治;换机制改动大、测试面大,非本卡)。
- ②**不靠「调大 size 上限」治标**(那只是把 8000 字的坎推到 8 万字,内容更多的论文照样撞新的 pipe/Queue 缓冲坎,本质互等仍在;R6 已实测 80000 字照样死锁)。
- ③**不碰中文 PDF 抽取乱码问题**(第一篇论文 pypdf 抽 CJK 为 0、pdfplumber 正常——根因在 `pdf_parser.py` 的抽取库选择,与本卡的 `_sandbox.py` 传输死锁是两处不同代码;换库牵动英文/正常 PDF 版式、需独立依赖 review + 回归。**单独起卡排后**,见 §7)。
- ④**不削弱任何现有 sandbox 安全语义**(spawn 隔离 / 临时目录复制 / cwd 隔离 / env 白名单 / 路径 inside 校验 / Linux RLIMIT_AS+RLIMIT_CPU / 错误脱敏 / 内存上限;见 §4.2,逐条守死)。
- ⑤**不碰任何业务逻辑 / 对外契约 / 前端**(纯 `_sandbox.py` 内部机制修复 + 验收测试)。

---

## 2. 产品 / 隐私边界(本卡不重开)

- **无产品决定点**:这是纯技术修复,不改任何用户可见行为、不加任何功能。修好之后用户的可见变化只有一个:**内容较多的论文/Word 从「一律超时失败」变成「能正常解析进来」**(这是修 bug 的自然结果,不是新功能)。
- **隐私不变**:sandbox 的错误脱敏(不泄露堆栈 / 本地绝对路径 / 原始 filename)必须**原样保住**;修传输机制不得引入任何新的信息落盘 / 落日志。解析失败仍返回中文可理解错误码,不变。
- 对齐 `04_ENGINEERING_STANDARDS.md` §(c) parser sandbox 的全部要求(见 §4.2 逐条),本卡是**修复使其真正满足**这些要求(尤其「默认解析超时 30s」这条,此前虚设、本卡补真),不是放宽。

---

## 3. 现状基线(R6 @ live `origin/main` `35b89e1` 实证)

### 3.1 死锁本体(`adapters/parser/_sandbox.py`)
当前 `_run_child` 顺序(**病灶**):
```
result_queue = ctx.Queue(maxsize=1)
process = ctx.Process(target=_sandbox_child_main, args=(request, result_queue))
process.start()
process.join(timeout_seconds)          # ← 先等子进程结束
if process.is_alive(): terminate + raise document_parse_timeout
status, payload = result_queue.get_nowait()   # ← 之后才取结果
```
子进程 `_sandbox_child_main`:parse 完 `result_queue.put(("ok", parsed))`,靠 `("error", ...)` 传异常。

**根因**:`multiprocessing.Queue` 的 `put` 把大对象交给后台 feeder 线程写管道;管道缓冲区满时 feeder 阻塞,子进程**主函数返回后也无法真正退出**(要等 feeder flush 完);父进程 `join` 永远等不到子进程结束 → 到 30s → 误判为「解析超时」`terminate`。**父进程从不 drain queue,所以永远撞死锁**。

**R6 实测阈值**(fake parser 不读 PDF、只返回 N 字符):
```
1000/4000/6000/7000 → ok
8000/12000/80000     → document_parse_timeout(稳定复现)
```
证明**与 PDF 内容无关**,纯传输阈值问题。两篇真实论文 raw_text 分别 8767 / 14706 字,均超阈值 → 都超时。直接跑 parser 核心逻辑(不进 sandbox)各约 1.0s 完成,证明**解析本身极快、慢的是回传**。

### 3.2 调用面(R6 实证:全仓库唯一生产调用点)
- 唯一生产调用:`features/paper/paper_spec_service.py` 的 `parse_uncached`:
  ```
  parser = await asyncio.to_thread(router.route, file_path)
  return await asyncio.to_thread(run_in_sandbox, parser, file_path)
  ```
  **经 `asyncio.to_thread` 桥接**(遵守异步阻塞纪律)→ FastAPI 上传路径 `paper_upload.py` 调 `parse_uncached`。
- **PdfParser 和 DocxParser 走同一 sandbox**(`get_document_parser_router() = DocumentParserRouter([PdfParser(), DocxParser()])`)。**故大 DOCX 只要 raw_text 够大,同样潜在死锁**;本卡修一处、两种 parser 同时受益,验收须两类都覆盖(至少构造大 payload parser 覆盖机制层)。

### 3.3 现有安全语义(R6 实证,`04_ENGINEERING_STANDARDS.md` §c + 代码)
必须**逐条保住**:
- **spawn 子进程隔离**:`_SANDBOX_MP_CONTEXT = mp.get_context("spawn")`;解析进程崩溃不拖垮主进程。
- **临时目录复制**:`TemporaryDirectory(prefix="mxa_paper_parse_")`,把源文件复制进 sandbox_dir 再解析,子进程只拿临时路径。
- **cwd 隔离**:`os.chdir(sandbox_dir)`。
- **env 白名单**:`_sanitize_child_env()` 只留 `_ENV_ALLOWLIST`(COMSPEC/PATH/PATHEXT/SYSTEMDRIVE/SYSTEMROOT/TEMP/TMP/TMPDIR/WINDIR)。
- **路径 inside 校验**:`_assert_path_inside(file_path, sandbox_dir)`,越界报 `sandbox_path_violation`。
- **Linux 资源上限**:`_apply_resource_limits` 设 `RLIMIT_AS`(512MB 默认)+ `RLIMIT_CPU`(≈ceil(timeout))。
- **错误脱敏**:子进程任何异常 → 父进程统一 `DocumentParseError("document_parse_failed")`,**不泄露堆栈 / 绝对路径 / 原始 filename**(现有测试 `test_parse_error_sanitizes_absolute_path_and_original_filename` 断言 `C:\`、`/home`、`/Users`、原文件名都不在 message)。
- **PDF/DOCX 自身防护**(在各 parser 内,本卡不碰):`_reject_active_pdf_content`(拒 /JavaScript /JS /OpenAction)、docx 宏/zip-bomb 检查。
- **默认 30s timeout / 512MB mem**:`04_ENGINEERING_STANDARDS.md §c` 明列,「允许通过配置调整」。**此前 timeout 被死锁吃掉、未真正生效;本卡补真**。

### 3.4 现有测试面(R6 实证,`tests/adapters/parser/test_sandbox.py`,8 passed)
已覆盖:临时路径脱敏 / cwd 隔离 / env 清理 / 异常脱敏 / **timeout(SleepingParser sleep timeout+5)** / 子进程 crash(ExitParser)/ outside path / 非 Linux hard-limit fail-closed。
**未覆盖(本卡验收必补)**:**大 payload round-trip**(会产生大 raw_text 的 parser 能在 sandbox 内正常返回、不超时)——正是这个 bug 藏这么久没被测出来的原因。
`test_paper_spec_service.py` 只验 `parse_uncached` 用 `to_thread` + sandbox 被 monkeypatch,**不测真实 round-trip**。

---

## 4. 范围(必须做)

### 4.1 ★ 核心:drain-before-join + bounded grace drain,把「取结果」提到「回收进程」之前(P0-1,含 v0.2 P0-A 修正)

把 `_run_child` 的顺序改为**先取结果、再回收进程**,用 **monotonic deadline 循环 + 子进程存活监控 + 死后 grace drain**。**新顺序写死为硬契约**(v0.2 已把 v0.1 的 `empty()` 误判改掉):

```
result_queue = ctx.Queue(maxsize=1)
process = ctx.Process(target=_sandbox_child_main, args=(request, result_queue))
process.start()

POLL_SECONDS = 0.1
DEAD_PROCESS_DRAIN_GRACE_SECONDS = 0.2   # 0.2~0.5,建议 0.2 起
deadline = time.monotonic() + timeout_seconds
result = None

while result is None:
    remaining = deadline - time.monotonic()
    # 真超时:deadline 到且子进程还活着 → 一定 timeout,不再读 queue
    if remaining <= 0 and process.is_alive():
        _terminate_then_kill(process)
        raise DocumentParseError("document_parse_timeout") from None
    try:
        result = result_queue.get(timeout=max(0.0, min(POLL_SECONDS, remaining)))
        break                                  # ← 唯一结果来源
    except Empty:
        if process.is_alive():
            continue                           # 还活着、没到 deadline → 继续轮询
        # 子进程已退出。★ 不查 result_queue.empty()(多进程下不可靠)。
        # 改 bounded grace drain:再短取几次,给 pipe/feeder 可见性一个小窗口,
        # 避免「刚 put 完就退出、结果还在管道里」被误判成失败而丢结果。
        grace_until = time.monotonic() + DEAD_PROCESS_DRAIN_GRACE_SECONDS
        while time.monotonic() < grace_until:
            try:
                result = result_queue.get(
                    timeout=min(0.05, max(0.0, grace_until - time.monotonic()))
                )
                break
            except Empty:
                pass
        if result is None:
            # grace 仍无结果 → 按 exitcode/deadline 分类(见 §4.3)
            if time.monotonic() >= deadline or _is_cpu_limit_exit(process.exitcode):
                raise DocumentParseError("document_parse_timeout") from None
            raise DocumentParseError("document_parse_failed") from None

# 拿到结果后回收进程(feeder 已被 drain,join 秒回)
process.join(1)
if process.is_alive():
    _terminate_then_kill(process)
# ★ 已拿到 result:即便上面为清理杀了子进程,也按 result 判定,绝不改判成 timeout
<result==("ok", ParsedDocument) → 返回 payload;("error",...)/未知/无结果 → document_parse_failed>
```

`_terminate_then_kill(process)`(P0-B,kill escalation):
```
process.terminate(); process.join(1)
if process.is_alive() and hasattr(process, "kill"):
    process.kill(); process.join(1)
```

**要点(逐条,实现须全落)**:
- **✗ 禁止用 `result_queue.empty()` 作为「无结果」判定**(P0-A 核心)。`multiprocessing.Queue.empty()` 在多进程语义下不可靠(官方文档明确;put 后有极短延迟、结果还在管道里时可能返 True),用它当判据会把**已成功的解析误判成失败、丢掉业务结果**。唯一结果来源是 `result_queue.get(timeout=...)`;子进程死后用 **bounded grace drain**(再短取几次)替代 `empty()`。R6 实测 40 次未观察到该竞态触发,但官方文档警告为真,**不赌概率,按可靠写法落地**。
- **必须先 drain queue 再 join**——这是修复本身。任意大小 payload,子进程 `put` 后 feeder 得以被父进程 `get` 消费、随即能退出,`join` 不再卡。R6 修法探针:8000 / 80000 / 1000000 字符全部正常返回、内容完整无截断(约 0.4s)。
- **deadline 用单调时钟**(`time.monotonic()`);轮询间隔 0.1s(`get(timeout=)` 是阻塞等待、非忙等,CPU 极低);`get` 的 timeout 用 `min(POLL_SECONDS, remaining)`,保证 **timeout 小于轮询间隔时不会固定多等 0.1s**(边界见 §4.4 测试)。
- **crash 快速失败**:子进程秒退无结果 → grace drain(0.2s)后判失败,**远小于 timeout**(R6 探针:`os._exit(7)` + timeout 5s → 0.758s 返回 document_parse_failed)。绝不傻等满 30s。
- **kill escalation(P0-B)**:`terminate` 发 SIGTERM,可能被忽略/延迟;wall-clock 兜底必须能真正终结子进程,故 `terminate → join → kill → join`。
- **拿到结果后不改判(P0-B)**:正常路径先 drain 到结果,之后 `join(1)` 回收;即便为清理 `terminate/kill` 子进程,**已拿到的成功结果不得被改成 timeout / failed**。
- **✗ 超时 / kill 后不再读 queue**(R1):子进程被 terminate/kill 时 queue 可能损坏(官方文档警告),该 queue 一次性、直接丢弃,timeout 路径在 raise 前不 get。

### 4.2 ★ 逐条保住现有安全 / 隔离语义(P0-2,不得退步)
本卡**只改 `_run_child` 内父进程侧的取结果/回收顺序**(以及必要时 `_sandbox_child_main` 的错误传回方式,见 §4.3)。以下**一律不动、且验收须回归**:
- spawn context(`mp.get_context("spawn")`)不变。
- `run_in_sandbox` 的临时目录复制 / sandbox_file 命名 / `shutil.copyfile` 不变。
- `_prepare_child`(cwd 隔离 + env 白名单 + 路径 inside 校验 + Linux 资源上限)**逐字不动**。
- 错误脱敏:父进程对外仍只抛 `DocumentParseError(<固定码>)`,**绝不**把子进程堆栈 / payload / 路径 / filename 带出。现有脱敏测试必须继续绿。
- `require_hard_limits` 非 Linux fail-closed 行为不变。
- **30s 默认 timeout / 512MB mem 不放宽**(只是让 timeout 真正生效)。

### 4.3 ★ 超时兜底补真 + 错误分类 + 错误回传健壮性(P0-3,含 v0.2 P0-C)
- **超时补真**:死锁修好后,`document_parse_timeout` 从「几乎必然误触发」变成「仅当解析真的超过 deadline 才触发」。语义:合法但巨慢(超大合法文件)/ 恶意拖时文件 → deadline 到 → `_terminate_then_kill` 子进程 + 报 `document_parse_timeout`。**这是把一层此前虚设的安全兜底补成真的**。
- **★ timeout vs failed 分类(P0-C,R1+R6)**:Linux `RLIMIT_CPU`(SIGXCPU)与父进程 wall-clock deadline 是**两套超时**,可能任一先触发。子进程死且 grace drain 后仍无结果时,按 `process.exitcode` 分类:
  ```
  父进程 wall-clock deadline 到且 child 仍 alive   → document_parse_timeout(§4.1 已在循环顶部拦)
  child exitcode == -SIGXCPU(CPU 时间上限)         → document_parse_timeout
  child 在 deadline 前无结果异常退出(OOM/SIGKILL/segfault/os._exit) → document_parse_failed
  child put("error", ...)(parse 内部 raise,能执行 handler) → document_parse_failed
  ```
  实现用 `_is_cpu_limit_exit(exitcode)` 判 `exitcode == -signal.SIGXCPU`。**最低要求(即便不做信号细分)**:deadline 到且还活着一定 timeout;deadline 前死且无结果一定 failed;**绝不傻等**。
- **crash 快速失败**:子进程异常退出(无结果)→ grace drain(0.2s)后快速判(§4.1),远小于 deadline。
- **parse 失败仍正确回传**:损坏 PDF / parser 内部 raise → 子进程 `_sandbox_child_main` 捕获后 `put(("error", "document_parse_failed"))` → 父进程 drain 到 error → 报 `document_parse_failed`。error payload 小、drain 顺畅;若子进程在 put error 前就崩了,存活监控 + grace drain 兜住,不变新死锁。
- **★ 结果状态白名单(R1)**:父进程只接受 `("ok", ParsedDocument)` 和 `("error", "document_parse_failed")`。**未知 status / tuple 形状不对 / payload 类型不对 → 一律 `document_parse_failed`,且绝不把 payload 写日志**。
- **可选加固(实现自决,R6 评估)**:`_sandbox_child_main` 里 `put` 之后,可在子进程侧对 result_queue 做 `close()` + `join_thread()`(把「等 feeder flush」变显式,可读性加固);父进程已 drain 时不引入新问题。**✗ 不得用 `cancel_join_thread()` 绕过 flush**(丢数据风险,结果是业务 payload——见 §5)。父进程侧可在所有路径 finally 里 `result_queue.close()`(父进程从不 put、不会引入 feeder 等待);**但不得在 get 前 close**。默认按需,除非 R6 判定某平台确需。

### 4.4 ★ 验收测试(必补,后端有测试框架)
在 `tests/adapters/parser/test_sandbox.py` 补(现有 8 个必须继续全绿)。**核心 5 类**:
1. **大 payload round-trip(命根回归)**:parser 返回大 `raw_text`(**≥80000 字符**;若目标环境 80k 不失败则用 **1000000 字符**贴 Python 官方死锁示例量级),`run_in_sandbox` **正常返回完整 ParsedDocument、不超时、内容完整无截断**。直接钉死 bug 不复发。
2. **真超时仍生效**:保留 / 强化 SleepingParser——真 sleep 超过 deadline 的 parser 仍被 `document_parse_timeout` 掐掉(证明修死锁没把真超时保护弄没)。
3. **crash 快速失败不等满 timeout**:子进程秒退(`os._exit` / crash)且无结果时,`run_in_sandbox` **在远小于 timeout 的时间内**返回 `document_parse_failed`(较大 timeout + 计时断言,证明 §4.1 存活监控 + grace drain 生效、没有「crash 也傻等 30s」)。
4. **大 payload + 脱敏并存**:大 payload 但 parser 内 raise,确认错误仍脱敏、不泄露路径 / filename(现有脱敏断言继续成立)。
5. **DOCX 侧机制覆盖**:构造走 DocxParser 路径产大 raw_text 的用例,或至少机制层用大 payload parser 证明与 parser 类型无关(修的是通用机制、PDF/DOCX 同受益)。

**边界 4 类(R1/R6 补,必做)**:
6. **dead-after-put 可见性回归(P0-A 对应)**:parser 快速返回大 payload,把父进程轮询间隔调成容易错过首轮 get 的值(或 monkeypatch 小 poll),验证**不会因 child 已退出而误判 failed**、结果仍完整取回。不必完全 deterministic,用多轮 / monkeypatch 覆盖。
7. **timeout 后进程确实被清掉 + 临时目录可删**:SleepingParser 超时后断言子进程不残留(通过 active_children / 测试 hook / 临时目录已删除间接断言)。**Windows 上尤其重要**(避免 timeout 后临时目录清理失败)。
8. **并发多次大 payload**:5–10 个并行 `run_in_sandbox` 各返回 80000 字,确认无串扰、无共享 tmp/cwd/env 泄漏、无句柄泄漏(可标 slow,至少一个轻量并发回归)。R6 探针已验 4 workers×8 次×80000 字全 ok。
9. **边界 timeout 小于 poll interval**:如 `timeout=0.05, poll=0.1`,确认用 `min(poll, remaining)`、不会固定多等 0.1s(计时断言)。

**可选(目标环境可用时)**:
- **Linux CPU-spin parser**:Linux 且 hard limit 可用时,CPU 忙循环触发 RLIMIT_CPU(SIGXCPU),期望 `document_parse_timeout`(证明 §4.3 分类)。
- **result tuple 非法 / 未知 status**:固定报 `document_parse_failed`、不泄露 payload(证明 §4.3 白名单)。

### 4.5 验证 checklist(合并前)
- `make check` 后端**完整跑到「All checks passed!」**(含 ruff format + lint + 全部 pytest;只报「X passed」视为没跑全、打回)。
- 新增 5 类测试全绿 + 现有 8 个 sandbox 测试继续全绿。
- **本卡无对外 schema 改动** → decision 13:无 schema diff,`make export-schema && make verify-schema` 预期零 drift(仍跑一遍确认没被意外触碰)。
- **本卡无前端改动** → 无 pnpm、无 smoke、无截图。
- `git diff --check` / `--cached` 过;隐私 grep:新代码无 `logger.exception` / `str(exc)` / `repr(exc)` / `exc_info`、无堆栈 / 路径 / filename 落日志。
- 合并前亲核真 diff:确认改动**只在 `_sandbox.py`**(+ 测试文件),`_prepare_child` / 安全语义逐字未动,传输顺序改对(先 drain 后 join),超时兜底真生效。

---

## 5. 反例 / 红线(不许这样修)

- **✗ 不许靠调大 Queue/pipe 缓冲或 size 上限治标**:根因是传输顺序(join-before-drain),不是缓冲太小。调大只把坎推远,80000 字论文照撞(R6 已实测)。必须改顺序。
- **✗ 不许用 `cancel_join_thread()` 作为主修**:它绕过 feeder flush 等待,有**丢数据风险**——而这里丢的是业务结果 payload(解析出的全文),丢了就是静默数据损坏。绝不用它换「不卡」。
- **✗ 不许改传输选型为 Manager().Queue() / 临时文件传结果**(除非 R1/R6 明确判定 drain-before-join 在某平台不成立):这些改动大、清理/脱敏/失败路径测试面大,超出「最小根治」,非本卡。若 R6 发现 drain-before-join 有平台坑,回来单议、不擅自扩范围。
- **✗ 不许削弱任何 §3.3 / §4.2 安全语义**换取修复:spawn 隔离、临时目录、cwd、env 白名单、路径校验、资源上限、错误脱敏,一条都不能松。
- **✗ 不许让「修死锁」把真超时保护一起弄没**:修完后 SleepingParser 那类真慢/卡死的文件仍必须被 `document_parse_timeout` 掐掉(§4.4 测试 2 钉死)。
- **✗ 不许把 crash 快速失败做成「傻等满 timeout」**:子进程秒退无结果必须秒判失败(§4.4 测试 3 钉死),否则一个崩溃也拖 30s、拉垮上传吞吐。
- **✗ 不许碰 `pdf_parser.py` / `docx_parser.py` 的解析逻辑**(含中文抽取):本卡只动 `_sandbox.py` 传输机制。中文乱码是另一张卡(§7)。

---

## 6. Stage 0 可落性 gate(基线 1-5+7-8 Codex 已核过;实现时以 live 为准复核一遍)

Codex 已从 live `origin/main` `35b89e1` 复核以下(实现开工再 `git fetch` 确认一遍,任一不符 → 停手报架构师,禁兜底硬上):
1. **唯一生产调用点仍是 `parse_uncached` 一处**、且仍经 `asyncio.to_thread` 桥接(确认修法不违反异步阻塞纪律、不需改调用方)。若发现新增了别的 `run_in_sandbox` 直接调用点(尤其未经 to_thread 的),停手报。
2. **`_run_child` / `_sandbox_child_main` 现状与 §3.1 一致**(Queue(maxsize=1) + join-before-get);若已被他人改动,停手报(可能已有人动过这块)。
3. **`_prepare_child` 及所有安全语义与 §3.3 一致**(改动前先确认基线,才能保证「逐字不动」有意义)。
4. **现有 8 个 sandbox 测试在 live 全绿**(改动前基线绿,才能证明改动没弄坏)。
5. **spawn context 下大 payload 死锁在 live 可复现**(用 §3.1 的 fake-parser 探针,确认阈值现象仍在——若已不复现,说明基线变了,停手报)。

**★ 6. 环境策略已定(v0.3;Windows 本地 + Linux 靠 CI)**:Codex Stage 0 已确认本机 Linux 通路打不通(WSL 虚拟化层缺 vmcompute/hns、需提权重装、不在本卡范围;Docker/gh 均不可用),故采用务实策略——**不再要求 Codex 本地跑 Linux**:
   - **Windows 侧**:Codex 已在 Stage 0 复跑全绿(死锁阈值 8000 字、修法探针 8000/80000/1000000 全 ok、真超时掐掉、crash 快速失败 0.5s、临时目录无残留、4×8×80000 并发无串、empty()-竞态 30 次无误判)。实现后本地再跑一遍 make check 全绿。
   - **Linux 侧靠 CI**:R6 确认 `.github/workflows/ci.yml` 在 `ubuntu-latest` 跑全量 `pytest -v`(testpaths=["tests"] 含 sandbox 测试)→ 新增 9 类测试 **push 后 CI 自动在 Linux 执行**,合并前看 **CI 全绿**(这是 Linux 侧真实测,只是 CI 跑而非命令行跑)。
   - **RLIMIT_CPU vs wall-clock 分类(§4.3 P0-C)做成 Linux-only 测试**:pytest skip-on-non-linux,CI ubuntu 上验证 CPU-spin→timeout / deadline 前异常退出→failed。**若 CI 上该测试红,说明 Linux 分类与设计有别 → 报架构师收敛,禁兜底硬改**。

**★ 7. `empty()` 竞态(v0.2 P0-A,已过)**:实现**未用 `result_queue.empty()` 当无结果判据**,用 bounded grace drain;dead-after-put 场景(§4.4 测试 6)Windows 已验 30 次无误判、Linux 靠 CI 该测试兜。

**★ 8. spawn context 未被改成 fork(已核)**:live 仍 `mp.get_context("spawn")`。实现不得改成 fork(fork 改隔离语义、违反 §3.3)。

**Stage 0 结论(Codex 已报)**:1-5 + 7-8 基线全对齐;第 6 项环境策略已定为上述务实版。**可进实现**。

---

## 7. 明确不在本卡、单独排的后继

- **★ [单独起卡] PDF 中文抽取质量 / fallback**(R6 实证:第一篇论文 pypdf 抽 CJK=0、pdfplumber 正常;非通病、是特定字体/CMap 编码的 pypdf 兼容问题)。根因在 `pdf_parser.py` 的抽取库选择,与本卡 `_sandbox.py` 传输死锁**是两处不同代码**。换 / 加 pdfplumber 作 fallback 会:新增依赖、改 PDF 文本抽取行为、影响英文/正常 PDF 的空白与版式输出 → 需**独立依赖 review + 回归**。**本卡先修 sandbox 阻断(让大论文进得来),中文抽取质量单独一张卡排后**。起草前需 Codex 再摸清 fallback 的确切改动面(是整体换 pdfplumber、还是 pypdf 失败时 fallback、判定阈值怎么定)。
- 解析器抓图 / 公式渲染 / 逐行可点出处等解析升级(既有独立线,不在此)。

---

## 8. 双审结论 + Stage 0 结果(R1 GPT + R6 Codex 均已过 → v0.2 收敛;Stage 0 基线/Windows 探针已过 → v0.3 环境策略)

**R1(设计审)= 条件通过**,挖出 1 个真漏洞(P0-A,已修)+ 2 个加固(P0-B/C,已并入)+ 4 个边界测试(已并入 §4.4):
- **P0-A(真漏洞)**:v0.1 用 `result_queue.empty()` 判无结果 → 多进程下不可靠、会把成功误判成失败丢结果。官方文档背书。**已改为 bounded grace drain(§4.1)**。
- **P0-B**:kill escalation(terminate→join→kill→join)+ 拿到结果后不改判。**已并入 §4.1/§4.3**。
- **P0-C**:RLIMIT_CPU vs wall-clock 两套超时按 exitcode 分类。**已并入 §4.3**。
- 确认 drain-before-join 是三约束下最优根治;排除的三候选(调大缓冲 / cancel_join_thread / 换传输选型)理由成立。
- 补 4 边界测试(dead-after-put / terminate 清理 / 并发 / sub-poll timeout)+ 结果白名单。**已并入 §4.4/§4.3**。

**R6(可落核)= live 现状全对齐 + 修法探针全绿 + 环境查清**:
- live `origin/main` `35b89e1` 现状与 §3 完全一致;唯一调用点 + 安全语义 + 现有 8 测试全绿,确认。
- Windows spawn 复现死锁阈值 8000 字(1000/…/7000 ok,8000/12000/80000 timeout);修法探针 8000/80000/1000000 字全 ok(约 0.4s)+ 真超时掐掉 + crash 快速失败 + 临时目录无残留 + 4 并发全 ok。
- **环境查清**:CI=Ubuntu/Linux,开发机=Windows,**生产 OS 仓库内无从确认**(无 Dockerfile/部署配置)。
- 同样指出 `empty()` 不可靠、建议 grace drain(与 R1 一致,无分歧)。

**无剩余分歧待裁**:R1 条件(改 empty())与 R6 建议指向完全一致,已全部并入。

**★ Stage 0 结果(v0.3;Codex 已报)**:
- 基线 §6.1-5 + 7-8 全对齐(唯一调用点、死锁现状、_prepare_child 安全语义、spawn 未改 fork、现有 8 测试全绿)。
- **Linux 本地通路打不通**:WSL 报 HCS_E_SERVICE_NOT_AVAILABLE(vmcompute/hns 服务不存在、虚拟机平台未启用,需提权重装,不在本卡范围);Docker Desktop 起不来;gh 未登录无法触发 CI。
- **CI 兜底成立**:`.github/workflows/ci.yml` 在 ubuntu-latest 跑全量 `pytest -v`(testpaths=["tests"] 含 sandbox 测试)→ 新增测试 push 后 CI 自动在 Linux 跑。CI 拆开跑 ruff/format/mypy/pytest/hygiene(非 make check 整包)。
- **Windows 探针全绿**:死锁 8000 字复现;修法探针 8000/80000/1000000 全 ok、真超时 0.33s 掐掉、crash 0.54s 快速失败、临时目录无残留、4×8×80000 并发无串、empty()-竞态 30 次无误判。
- **→ v0.3 环境策略**:Windows 本地充分测 + Linux 靠 CI 兜 + RLIMIT 分类做成 Linux-only CI 测试(§6.6)。**可进实现**。

---

**本卡版本**:v0.3(2026-07-03,双审 + Stage 0 基线/Windows 探针均已过、环境策略已定;待实现到 staged → 亲核 → push)
**作者**:Claude(架构师)
**归属**:MCS 主线基础设施修复 TASK-311;修 `adapters/parser/_sandbox.py` join-before-drain 死锁(drain-before-join + bounded grace drain,**不用 empty()**)+ 补真 30s 超时兜底 + kill escalation + 两套超时按 exitcode 分类;PdfParser/DocxParser 同受益;中文抽取乱码单独排(§7)。
**v0.1 → v0.2**:P0-A 把 `empty()` 误判改成 grace drain(R1 挖出、官方文档背书);P0-B kill escalation + 成功不改判;P0-C RLIMIT_CPU vs wall-clock 分类。
**v0.2 → v0.3**:环境策略从「双环境本地实测」改为「Windows 本地充分测 + Linux 靠 CI 兜 + RLIMIT 分类做成 Linux-only CI 测试」(Codex 本机 Linux 通路虚拟化层缺失、打不通;CI 在 ubuntu 跑全量 pytest 兜底成立)。修法本身 v0.2→v0.3 零改动。
