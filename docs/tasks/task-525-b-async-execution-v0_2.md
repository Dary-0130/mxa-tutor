# TASK-525-B:论文上传作业化 · 段二(异步执行 + 文件生命周期收口 + 僵尸分流恢复)

> **编号暂拟 525-B**(paper-to-model 线,决策 22 分段 501-999)。**Stage 0 必须 git fetch 后核 `525-b` 未被占**,被占则顺延。
> **本卡 = 「卡一」后端的段二**,承 TASK-525(v0.2)。**取代**父卡 task-525-paper-upload-job §6「段二」清单(父卡段二成稿于 R6 摸底前,假设 orchestrator 已可分支,已被证伪)。

## 状态
🔲 **v0.2**(架构师定稿,并 R1 设计审[条件通过·4 P0 采纳 + 1 P0 澄清 + 8 P1]+ R6 两轮 live 摸底实证)。待 **Stage 0 派单前可落核** → 派 Codex。

## v0.1 → v0.2 变更摘要(并 R1)
- **P0-1 采纳**:startup stale set 扩为 `{queued, running, plan_generating}`——补「已建 job、后台未启动前崩溃」的 `queued` 僵尸窗(原只扫 running/plan_generating 会永卡 queued + staging 不清)。见 §5。
- **P0-2 采纳**:僵尸分流改**三段**(先看 plan record 可完整读→修 ready;再 spec 有/plan 无→`abandoned_plan_retryable`;再 spec 无→`abandoned_reupload_required`),防「plan 已落盘、ready 未标记」被误降级、用户已有 plan 却被要求 rerun。见 §5。
- **P0-3 采纳**:rerun CAS 允许源状态**加 `abandoned_plan_retryable`**(否则分流后状态说 `next_action=rerun_plan`、`POST /rerun-plan` 被 CAS 拒 → 恢复点不通)。**additive 扩 525-A `try_start_rerun_plan` 的 WHERE 集,不改其它、不回退**。见 §5 / §7。
- **P0-4 采纳**:后台并发从「同锁+CAS vs job-state gate 二选一」**收口为强制**「同锁 + job-state CAS 序列」(gate 不足以互斥「只拿进程锁、不查 upload job-state CAS」的既有写路径 reparse/user-supply/correction/regenerate)。见 §7。
- **P0-5 处置(非采纳原文,澄清)**:R1 据 R1-brief 内**不全的 schema** 判「无 `failed_stage` 列、须改用 `stage`」。**实为 brief 漏抄字段**——525-A rerun CAS RAW 明写 `failed_stage=NULL`(且有 `last_error_code`/`retryable`/`attempt_count`),故 `failed_stage` 是**既有 v8 列**。**卡保留 `failed_stage`,不改用 stage**(改了反而错)。采纳其**用意**(禁 Codex 擅自加列/写不存在字段):§1 钉死 v8 完整列集,Stage 0 live 复核。见 §1.F1 / §8。
- **P1-1~8 采纳**(各节):staging root 定 `<upload_dir>/paper_staging/<job_id>/`(§4);TTL sweep 状态感知(§4);cleanup 失败不遮蔽主结果(§4);status→next_action 映射表(§6);async 入口优先新端点/显式 opt-in、默认 sync(§6);terminal/abandoned mark 递增 `state_version` + 置 `finished_at`(§5);staging 文件名沿用 `document_id` 派生(现状 `_save_upload_sync` 已如此,保留,§4);B2 真机硬门加两崩窗(§11)。

---

## 1. 上下文 / 起因(R6 两轮 live 取证 @ HEAD `aa21407`;Stage 0 用 live 值复核)

### 525-A 现状(已合并 main)
- HEAD `aa2140775fa0daf337be27fd0e73a406e2b499d2`;`CURRENT_SCHEMA_VERSION = 8`;`paper_upload_job` + `paper_upload_job_document` 表已落;迁移体系 `_migrate_v7_to_v8` 在。
- as-built §4 立命断言在(同步 200 body 不变 / plan 崩 spec 保住 + 失败返 paper_id / rerun 从 spec-only 恢复 / persisting_* 崩点 / lock-first→CAS / spec-only 三态 / expired 派生 410 / 契约只加新 DTO)。

### **F1 — v8 `paper_upload_job` 完整列集(★ P0-5 澄清;Stage 0 逐列复核)**
R1-brief 曾漏列部分字段,此处按 525-A RAW(含 rerun CAS `SET ... failed_stage=NULL, last_error_code=NULL, retryable=0, attempt_count=attempt_count+1`)钉死:
```
paper_upload_job:
  job_id PK, paper_id UNIQUE, execution_mode IN('sync','async','rerun_plan'),
  job_state IN(queued|running|spec_ready|plan_generating|ready|plan_failed_retryable|
    plan_failed_permanent|failed_no_usable_spec|abandoned_plan_retryable|abandoned_reupload_required),
  stage IN(uploading|parsing|extracting_spec|fusing|persisting_spec|generating_plan|persisting_plan|done),
  failed_stage,          # ← 既有列(rerun CAS 写 NULL 证其存在)。崩点记真实阶段
  last_error_code,       # ← 既有列
  retryable,             # ← 既有列
  attempt_count,         # ← 既有列
  state_version, created_at, started_at, finished_at, expires_at
  # 无 updated_at / heartbeat / worker_id / staging_path
paper_upload_job_document:
  job_id, paper_id, document_id, upload_index,
  status IN(pending|parsing|parsed|extracting|succeeded|failed), error_code, updated_at
```
→ **本卡不新增列**(僵尸/staging 用既有列 + spec/plan row 判);Stage 0 若发现必须持久新列 → 停手报架构师。

### 其余摸底事实(自包含;Stage 0 复核)
- **F2 无可分支 orchestrator**:实际 route-local `_run_upload_job(files: list[UploadFile], sandbox_dir, ...)`,依赖请求期句柄,route `finally` 删 sandbox;`create_upload_job` 若在 route `try/finally` 前抛,已建 sandbox 不被该 finally 清(pre-try leak)。
- **F3 句柄切分点干净**:`_save_upload_sync`(落盘、文件名 = `f"{document_id.lower()}{extension}"`)之后下游只需 `saved_path`/`parsed`/字符串 metadata,不再需句柄;解析器 `parse_uncached(saved_path)` 内部 `run_in_sandbox(parser, file_path)` = 路径 + 沙箱子进程。
- **F4 工程 zip 样板 = bytes-in-memory**(`zip_bytes = await file.read()` 交后台),非 staging-path;`CleanupWorker` 只扫工程 `upload_dir/project_id` + DB 过期 bundle,**不扫 `mxa_paper_sandbox_`**。
- **F5 僵尸字段缺口**:`abandoned_*` 已在 enum,但无 startup 扫描/list-stale 接口/写入点;无 heartbeat → 运行期判不了 running 死活;可用 spec-row 判「崩点 spec 前/后」。
- **F6 锁/CAS/rerun**:rerun = lock-first(`PaperReparseLockRegistry.acquire`)→ DB CAS(`WHERE job_state IN('spec_ready','plan_failed_retryable') → 'plan_generating'`);reparse/user-supply/correction/regenerate 共用同一进程锁但只有 rerun 有 job-state CAS;当前 sync 初始 plan gen 不拿锁;`POST /rerun-plan` 现为同步。

---

## 2. 是 / 不是

**是**(后端):把上传管线重塑成**落盘路径驱动的单一 orchestrator**(sync/async 共用,禁两套 pipeline)+ 异步入口(`202 + {job_id, paper_id}`)+ 文件生命周期收口(staging 落盘 keyed by job_id → 后台读 → 抽完 spec 即删 + orphan 清)+ 僵尸分流恢复(startup sweep 三段)+ 后台并发纳统一锁+CAS + additive store 接口 + 真机复验 525-A 立命断言不回归。

**不是 / defer**:前端(锁着)/ LLM 稳定性(卡二 526)/ 历史多版本+存储上限(527)/ rerun-plan job 化(默认不做,记后继)/ durable 队列+外部 worker(更后)/ 多进程·多机器僵尸稳版(单进程假设下不做,PM 要多机器再上 v9 heartbeat)。

---

## 3. 架构师已定(Codex R6 抛回两点 + 卡结构)

### ① 文件送后台 = staging-path(不用 zip 的 bytes-in-memory)
论文解析器路径 + 沙箱子进程(F3),bytes 版仍要落盘 + 大 PDF 驻内存整个作业期。故请求期消费句柄 + 落盘 staging → 之后全读 staging path。staging 从 `mkdtemp`(系统 temp、不可扫)改为**已知可扫 root、keyed by job_id**(§4 定 `<upload_dir>/paper_staging/<job_id>/`)。

### ② 僵尸活性判定 = startup-only + 单进程假设
v8 无 heartbeat(F5)。按已锁定本地优先方向(一台机器一个服务进程):**startup 时凡遗留非终态 job(`queued`/`running`/`plan_generating`)一律视为已死**(进程若重启其 BackgroundTask 已消失;startup hook 只开机跑一次、不误杀开机后新起活任务),再三段分流(§5)。**liveness 不加 v9**,仅 additive store 接口(list-stale + mark)。in-alive-process 无限挂起靠既有 LLM timeout 兜。**单进程钉为本卡显式约束**(本地优先方向的后果,非新赌);日后要多机器/多进程 → 升 v9 heartbeat/worker_id(记后继)。**PM FYI 已发,近期无多机器计划即照此。**

### ③ 卡结构 = 两个 PR(先重塑、后异步)
- **B1 · 底子重塑**:`_run_upload_job` → 落盘路径驱动的**单一** orchestrator;staging 移可扫 root + 生命周期 owner 收口;**对外零变化**(sync 仍 200 + 旧 body)。**合并前真机复验 525-A 五场景立命断言不回归**。
- **B2 · 异步 + 僵尸**:异步入口 + 后台执行 + startup sweep 三段分流 + 后台并发纳锁/CAS。
- **B1 先真机验过才起 B2**,不一锅端。

---

## 4. staging-path 契约(★ 核心新契约)

- **请求期职责边界**(切分点 = F3):请求期只做 magic 校验 + `_save_upload_sync` 落 staging → 得 staging path;其后所有步骤只读 staging path,**不再碰 `UploadFile` 句柄**。
- **staging 位置(P1-1 定死)**:`<upload_dir>/paper_staging/<job_id>/`。`job_id` = 服务端生成、既有 job_id 字符集;**禁用户输入参与路径拼接**。选此因 startup sweep + TTL worker 都能扫到、按 job_id 定位,且贴现有 `CleanupWorker`(围绕 `upload_dir`)扩展。(Stage 0 若发现与 `CleanupWorker` 的 `upload_dir/project_id` 扫描撞车 → 报架构师微调命名空间。)
- **staging 内文件名(P1-7 保留现状)**:沿用 `_save_upload_sync` 现有 `f"{document_id.lower()}{extension}"`——**不用原始 filename**;展示名只作 metadata 进业务对象,不出现在磁盘路径/日志。
- **删除 owner 变更(P0)**:现由 route `finally` 删 → 重塑后由 **orchestrator 在 spec 抽取完成(成功或失败)即删该 job 的 staging**;**route `finally` 不再删后台仍要读的 staging**。请求期在进 orchestrator 前抛错(F2 pre-try leak)须保证已建 staging 被清。**多文档一 job**:一 job 一目录装 N 文件,**全部文件抽完 spec 后整目录删**(不逐文件删,避免中途崩留半份的判定复杂;整目录删对齐 job 粒度)。
- **cleanup 失败处置(P1-3)**:`shutil.rmtree` 可能失败 → **metadata-only log(不记 path/filename/exception message)+ 不覆盖主业务成功/失败(ready 不因清理失败变 500)+ 依赖 TTL sweep 兜底**;真机硬门加 `cleanup_failed` 场景(§11)。
- **orphan / TTL 兜底(P1-2 状态感知)**:startup sweep 清「job 终态/abandoned/不存在」对应 staging;**TTL staging sweep 只清:job 不存在 / job_state 终态或 abandoned / 超安全 TTL 且 startup 已判 stale;不得清当前进程内非终态活跃 job(`queued/running/parsing/extracting_spec` 等)的 staging**。
- **隐私(decision 11)**:staging = 原文件,只活到 spec 抽完、抽完即删、不长期留;staging 路径/filename/原文不进日志/status DTO/telemetry。

---

## 5. 僵尸分流恢复(startup sweep · 三段,P0-1/P0-2 并入)

- **触发**:app startup 扫一遍(落 `CleanupWorker` 还是独立 startup hook,Stage 0 定)。
- **stale set(P0-1)**:`job_state ∈ {queued, running, plan_generating}` → 视为已死(单进程假设,§3②;startup 早于新请求,这些遗留态不可能是活任务)。
- **分流顺序(P0-2 三段,只用既有 spec/plan store,不加列)**:
  1. **plan record 可完整读取** → mark `ready` + stage `done` + 清对应 staging(修复「plan 已落、ready 未标」的完整结果,不误降级)。
  2. **spec row 存在、plan record 不存在** → `abandoned_plan_retryable` + `next_action=rerun_plan`。
  3. **spec row 不存在** → `abandoned_reupload_required` + `next_action=reupload`(`retryable=false`)。
  - **plan record 存在但 bundle 不完整/反序列化失败** → 走脱敏 StoreError/修复分支(对齐 bundle 三态:plan-only 非法),**不伪装 ready、不覆盖 spec-only 可恢复路径**。
- **mark 写法(P0-5 + P1-6)**:mark 时更 `job_state`;**保留现有 `stage` 作为遗弃/失败阶段**(如已是 `generating_plan`/`persisting_plan` 就留该值);**递增 `state_version` + 置 `finished_at`**(进 abandoned/ready/permanent terminal 均置);不新增列。
- **写入接口**:additive `PaperUploadJobStore`(list-stale + mark)。
- **不给点不通的重试**:`abandoned_reupload_required` 的 `next_action=reupload`(非 rerun_plan);`abandoned_plan_retryable` 须与 rerun CAS 联动(§7)。
- **清对应 staging**(若残留)。

---

## 6. 异步入口

- **async 模式**:请求期落 staging + `create_upload_job(execution_mode=async)` → 返 **`202 + {job_id, paper_id}`** → `background_tasks.add_task(run_upload_job, ..., execution_mode=async)` → 后台读 staging path 走**同一 orchestrator**。
  - **落 staging 与 create_upload_job 的先后**须保证:两者中途崩溃都能被 §5 stale set(job 存在→queued 僵尸)或 §4 orphan sweep(job 不存在→清 staging)兜住,无「job 无、staging 有」或「job queued 永卡」漏窗。
- **入口区分(P1-5 定)**:**优先新端点 `POST /upload-async`(或等价新增路由)**;若复用同端点,则 async 必须**显式 opt-in、默认仍 sync 200 旧 body**。**这是后端契约收口,非前端改动**;前端锁着、现有前端仍走 sync。红线 = 不破坏 sync 200 body。
- **GET status 失败态 → next_action 映射(P1-4 补表;用既有 next_action 枚举 `wait/rerun_plan/reupload/open_result/none/contact_support`)**:
  ```
  plan_failed_retryable        retryable=true   next_action=rerun_plan
  plan_failed_permanent        retryable=false  next_action=contact_support
  failed_no_usable_spec        retryable=false  next_action=reupload
  abandoned_plan_retryable     retryable=true   next_action=rerun_plan
  abandoned_reupload_required  retryable=false  next_action=reupload
  崩点 stage=persisting_spec   → 无 spec → next_action=reupload
  崩点 stage=persisting_plan   → spec row 存在 → next_action=rerun_plan
  ```
  防「202 后只能查 status」的 async 失败呈现比 sync 弱。
- **后台失败**:走 as-built retryable/permanent 边界;崩点记 `failed_stage`(含 `persisting_*`)。

---

## 7. 后台并发 / 锁(P0-3 + P0-4 收口)

- **后台初始 plan generation 必须(强制,非二选一)**:
  1. `acquire(paper_id)`(同一 `PaperReparseLockRegistry` 进程锁);
  2. job-state CAS:`spec_ready → plan_generating`;
  3. 生成 plan;
  4. `persisting_plan`;
  5. CAS/mark `ready` 或 `plan_failed_*`;
  6. release lock。
  **不得用「job-state gate 禁入口」替代同锁**(gate 挡不住只拿进程锁、不查 upload job-state CAS 的既有写路径)。这样不回退 525-A「写 plan 统一 lock-first→CAS」。
- **rerun CAS 扩源(P0-3,additive)**:`try_start_rerun_plan` 允许源状态加 `abandoned_plan_retryable`:
  ```sql
  WHERE job_state IN ('spec_ready', 'plan_failed_retryable', 'abandoned_plan_retryable')
  ```
  保持 lock-first → CAS 顺序;测试覆盖 `abandoned_plan_retryable → rerun → plan_generating → ready`。**仅扩 WHERE 集,不动 525-A rerun 其它逻辑。**
- **并发正确性 vs 僵尸**:并发写正确性靠 CAS(跨进程);僵尸 startup sweep 走单进程假设——不矛盾(CAS 保不双跑,单进程保 sweep 不误杀活任务)。两并发 async 上传各拿新 `paper_id`(525-A 每次新 uuid),不撞。

---

## 8. 迁移

- 僵尸分流 + staging 追踪走既有列(§1.F1)+ spec/plan row 判(§5)→ **不需 v9**。Stage 0 确认无需迁移;**若发现分流/staging 追踪必须持久列 → 停手报架构师**(可能 v8→v9,不自补)。

---

## 9. 继承红线(不回退,不顺手动它)

- **525-A as-built §4 全部不回退**:状态机枚举 / `persisting_*` 崩点 / **同步 200 body 不变 + 失败返 `paper_id`** / rerun 只重跑 plan 不碰原文件 / lock-first→CAS 统一顺序 / spec-only 三态 / expired 派生 410 / 契约只加新 DTO。**B1 重塑对外零变化——sync 200 body + spec 提前落盘 + rerun 从 spec-only 恢复 不许破**(§11 真机守门)。**本卡对 525-A 的两处触碰均 additive**:rerun CAS 扩 WHERE 集(§7)、abandoned mark 用既有列——不改既有语义。
- **禁两套 pipeline**:sync/async 共用同一 orchestrator。
- **decision 11(脱敏)**:staging 路径/filename/原文/参数值/单位/异常 message/堆栈**绝不进**日志/console/error body/telemetry/status DTO;SQL 错误只 `type(exc).__name__`;崩点/status 只阶段名/error_code 分类;禁 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info`。
- **decision 08**:改文本文件保原始字节。

---

## 10. Stage-0 可落性 gate(Codex 派单前核 live,不符停手,禁兜底硬上 · decision 15)

1. `git fetch origin && git rev-parse origin/main` 报 HEAD;核 `525-b` 编号未被占;`git merge-base --is-ancestor` 复核 525-A 在 main(允许 main 合法前进)。
2. 确认本卡随代码入 `docs/tasks/`(PM 预放,untracked=预期)。
3. **★ 逐列复核 v8 `paper_upload_job` 列集(§1.F1)**:`failed_stage`/`last_error_code`/`retryable`/`attempt_count` 确为既有列;确认无 `updated_at`/heartbeat/staging_path(P0-5 澄清落实,不新增列)。
4. **复核 F2–F6 摸底 as-built 仍成立**(贴 RAW):句柄切分点、sandbox 生命周期 + pre-try leak、`abandoned_*` 无 scan/接口、rerun 同步 + CAS、迁移体系、worker 前提。
5. **★ B1 staging-path 重塑落地核**:请求期消费句柄→落盘→后续只读 path 可干净切;staging root `<upload_dir>/paper_staging/<job_id>/` 可扫 + keyed by job_id 可实现、不与 `CleanupWorker` 撞;orchestrator 接管删除 + startup/TTL orphan sweep(状态感知)可实现;route `finally` 改造不误删;cleanup 失败不遮蔽主结果可实现。
6. **★ B2 异步落地核**:`BackgroundTasks` 可承 `run_upload_job(async)`(不复制 pipeline);后台 orchestrator 纳入 `acquire + job-state CAS 序列`(§7,强制同锁)可实现;`202+{job_id,paper_id}` 入口不破坏 sync 200;新端点 vs 同端点 opt-in 落点。
7. **★ B2 僵尸三段 sweep 落地核**:startup 扫 `{queued,running,plan_generating}` + 三段分流(plan record 可读→ready / spec 有→abandoned_plan_retryable / spec 无→abandoned_reupload_required)+ mark(保留 stage、递增 state_version、置 finished_at)可实现,**无需持久新列**(需则停手);additive `PaperUploadJobStore`(list-stale + mark)可扩;rerun CAS 扩 `abandoned_plan_retryable` 可 additive 落地。
8. 任一不符 → 停手诊断报架构师。

---

## 11. 真机硬门(523/524→525 一脉,合并前必过 · 依赖真 LLM 输出分布的立命断言只真机能证)

> uvicorn HTTP + 真 `DeepSeekTextProvider`(需 PM 给 `DEEPSEEK_API_KEY`)+ 真 PDF;存储落临时库/内存,**不污染本地 `data/mxa.db`**。

**B1(重塑)合并前**——复验 525-A 五场景立命断言**不回归**:
- 正常同步:upload 200(旧 body 不变)、status ready/done/open_result、spec+plan 落盘。
- plan 崩后 spec 保住:upload 502 带 `paper_id`+`job_id`、status `plan_failed_retryable`/`generating_plan`/retryable/`rerun_plan`、spec 落盘 plan 未落、GET `/spec` 200 / `/plan` 404。
- spec-only rerun 恢复:rerun 成功、`/plan` 200、`attempt_count=2`。
- persisting_spec / persisting_plan 崩点旁证。
- 脱敏复核:失败日志只 `paper_id/job_id/error_code`+阶段+HTTP 码+异常类型分类,无原文/值/filename/message/traceback。
- **新增(P1-3):`cleanup_failed` 场景**——staging 删除失败时 ready 主结果不变 500、日志 metadata-only 无 path/filename。

**B2(异步 + 僵尸)合并前**:
- 异步入口 `202+{job_id,paper_id}` 立即返回;GET status 逐步 `job_state`/`stage`;失败态经 status 如实透出 + `next_action` 按 §6 表给对。
- **进程重启僵尸分流**:遗留(plan 已落、ready 未标)→ 修复 `ready`/`done`,**不误标 abandoned_plan_retryable**(P0-2);遗留 running/plan_generating(spec 已存/plan 无)→ `abandoned_plan_retryable` + `rerun_plan`,且 **rerun 从该态成功恢复到 ready**(P0-3);遗留(spec 未存)→ `abandoned_reupload_required` + `reupload`;**无永卡**。
- **新增(P1-8)两崩窗**:
  - **async job created 后、background start 前崩溃**:`queued` 遗留 → 按 §5 三段分流(此处 spec/plan 均无 → `abandoned_reupload_required`),**无永卡 queued**;staging 被清。
  - **plan persisted 后、ready mark 前崩溃**:startup 修复为 `ready`/`done`,**不误标 abandoned**。
- **staging 生命周期**:抽完 spec 即删;进程中途死残留 staging 被 startup/TTL(状态感知)清;活跃 job staging 不被 TTL 误删;无孤儿。
- **后台并发**:同 `paper_id` 后台 plan-gen 与 rerun/reparse 互斥(同锁 + CAS),无双跑。
- 脱敏复核同上。

---

## 12. 给 Codex 的提示(派单实现阶段)
- feature branch 从 `origin/main`(git fetch 后切,不许 main 直推)。
- **两个 PR:B1(重塑)先起、独立可验收 + 真机复验不回归;B2(异步+僵尸)后起**。各独立 PR。
- **卡随代码同 PR**;**索引收尾单独 PR**;本代码 PR 不碰 `03_TASK_INDEX.md`(decision 07)。
- PR 全走 PM 网页侧:Codex 给标题 + 正文草稿 + `pull/new` 链接,PM 建 PR + squash(不自建 PR、不用登录)。
- `make check` 全管道(注:需临时 PATH 前置 `F:\python;F:\python\Scripts`,否则裸 pytest 走 Anaconda 缺依赖,与 524/525-A 同款环境注脚,非失败);additive DTO/接口变更则显式 `make export-schema && make verify-schema` + freeze + `pnpm typecheck`。
- **禁两套 pipeline**;async 与 sync 共用同一 orchestrator。
- **隐私红线亲核**(贴本体不凭勾选)。
- 本机无 `grep`,用 `git grep`/`rg`/`Select-String`;行尾/字节(08);异步/日志(11)。
- 合并前架构师亲核后端真 diff + 对外零 drift(新增 DTO 除外,须证纳入 schema-sync)+ **真机验立命断言**;RAW 取证/diff 贴对话、去行号、不收本机路径。

---

## 13. 开放点(Stage 0 定,已大幅收窄)
- **startup sweep 落点**:并入 `CleanupWorker` vs 独立 startup hook —— Stage 0 定。
- **落 staging 与 create_upload_job 先后**:两序都要被 §5 stale set / §4 orphan sweep 兜住 —— Stage 0 定具体序 + 核无漏窗。
- **单进程假设**:PM 确认近期无多机器服务计划则照 startup-only;否则升 v9 heartbeat/worker_id(PM FYI 已发)。
> (staging root 位置 / async 入口方式 / 后台并发处理 三项原开放点已由 R1 P1-1/P1-5/P0-4 定死,不再摇摆。)

---

**版本**:v0.2(架构师定稿,并 R1 设计审[条件通过·4 P0 采纳 + P0-5 澄清 + 8 P1]+ R6 两轮 live 摸底实证 + 架构师两项落地裁定[staging-path / startup-only 单进程]+ 两 PR 结构)
**作者**:Claude(架构师)
**审批级别**:R1 设计审条件通过 → 待 Stage 0 派单前可落核 → 派 Codex
**前置**:main 含 525-A(代码 PR #174 / 索引 PR #175,HEAD `aa21407`;Stage 0 用 `git merge-base --is-ancestor` 复核)
**后继**:卡二 TASK-526(LLM 结构化稳定性 · 问题①)/ TASK-527(历史多版本 + 存储上限)/ 本卡前端批次(原 1C)/ rerun-plan job 化 / 多机器僵尸稳版(v9 heartbeat)
