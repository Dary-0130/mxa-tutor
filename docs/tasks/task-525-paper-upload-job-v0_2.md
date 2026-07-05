# TASK-525:论文多文档上传作业化 · 后端可靠性与可恢复中间态(v0.2)

> **编号暂拟 525**(paper-to-model 线,决策 22 分段 501-999;索引副本占用到 524)。**Stage 0 必须 git fetch 后核 525 未被占**,被占则顺延。
> **本卡 = 「卡一」的后端部分**。卡一(多文档上传三类真机问题:①LLM 输出不稳 ②失败体验差 ③耗时长)经 R6 三轮取证 + R1 两轮设计审收敛为「上传作业化 + 可恢复中间态」架构卡;R1 建议切三段(1A 后端状态基座 / 1B 后台执行+恢复 / 1C 前端)。**PM 已拍:前端(1C)整卡搁置,本卡只做后端**,内部切 525-A / 525-B 两段 PR(见 §6)。LLM 稳定性(问题①)= 独立卡二(TASK-526 待起),不在本卡。

> **525-A 派单收窄(2026-07-05 开工授权)**:Stage 0 live 复核确认当前上传入口每次生成全新 `paper_id = str(uuid.uuid4())`,同一篇重传天然不会撞旧 ready。故 525-A **不做同一篇身份 / C 覆盖 / prepare-then-commit 重传替换**;这组能力整体顺延 TASK-527。525-A 范围收敛为:状态基座 + fused spec 提前落盘 + rerun-plan + GET status + TTL/schema/隐私红线。

## 状态
🔲 **v0.2**(架构师定稿,并 R1 第二轮设计审[条件通过·补 8 P0/5 P1]+ PM 两决定)。待 **R6 派单前 Stage 0 可落核**(落点已三轮,派单那刻复核 + C 方案落地核)→ 派 Codex。
> 起稿实证基础(Codex R6 三轮 live 取证,末轮 @ origin/main `7be9af2`;Stage 0 用 live 值复核,允许 main 合法前进)。

## v0.1 → v0.2 变更摘要
- **PM 决定①(重复上传走 C)**:同一篇重传撞旧 ready plan → 走 **prepare-then-commit 覆盖**(新 plan 跑成功再单事务替换旧 ready、失败保旧、本阶段只留最新版)。这解 R1 揪出的最大 P0(§9 P0-2)。**引入「同一篇 paper 身份」概念,为 527 历史版本铺地基。**
- **PM 决定②(历史版本 defer)**:历史多版本 + 存储上限 → **TASK-527(后继)**,不在本卡;本卡只立「同一篇身份」+ C 覆盖(只留最新版)。
- **并 R1 第二轮意见**:①同步失败必返 `paper_id`(否则 rerun 够不着,P0-1);②stage 补 `persisting_spec/persisting_plan`(崩点准,P0-4);③僵尸任务分流 `abandoned_plan_retryable` / `abandoned_reupload_required`(P0-3);④status 加 `next_action`(P1-1);⑤`plan_failed_permanent` 极窄化、默认 retryable(§5);⑥同步/异步共用同一 orchestrator、不复制两套 pipeline(§6 调整二收紧);⑦既有入口 spec-only **smoke 体检**(不崩/不写坏/不泄漏即 defer 话术,否则本卡修,P0-5);⑧`expired` 派生化返 410、不长期留 metadata(P0-7);⑨契约同步只补本卡新增 DTO、不清理旧 DTO(§7);⑩锁与 CAS 顺序全项目统一(P0-6)。

---

## 1. 上下文

### 在 paper-to-model 主线的位置
核心流程:上传 PDF → 解析 → LLM 抽取 `PaperSpec`(结构化论文规格)→ LLM 生成 `ModelGenerationPlan`(建模计划:`parameter_mapping` / `build_steps` / `m_script_skeleton`)→ 前端展示。多文档:逐篇抽 `PaperSpec`,后端 `fuse_successful_specs` 拼成 fused spec,再喂 plan 生成。

### 触发(PM 真机跑两个 PDF 合并上传,坐实三类)
- **① LLM 输出不稳/随机失败**(第一次失败、同样两篇第二次成功):`PaperSpec schema validation failed` / `paper_plan_json_decode_failed` → `paper_plan_generation_failed` 502。**→ 归卡二(TASK-526),不在本卡。**
- **② 失败体验差**:系统内部已知「两篇都抽取成功、是 plan 崩了」,但 502 只回 `{error,message}`;更糟——plan 崩时**整份丢弃**,成功解析的 spec **一点没落 DB**,用户啥都看不到、还得从头重传两篇。
- **③ 耗时长**:两篇同步一条请求跑完,用户干等 5 分多钟。

### 本卡要解决的(PM 锁定的后端四件)
1. **上传可改后台跑**,不让用户同步干等(异步执行能力;完整「不干等」体验依赖前端轮询,前端搁置,故本卡只建后端异步能力)。
2. **每步记进度、崩了记崩在哪步**(做法二:后端在崩点记真实 `failed_stage`,供前端如实显示崩点)。留 `GET status` 供查。
3. **成功的部分(fused spec)先落盘、不丢**(spec 提前持久化;plan 崩了 spec 还在)。
4. **能基于已存 spec 只重跑崩掉的 plan 那步**(rerun-plan,不重传、不重解析、不重抽 spec)。

### 与已有恢复机制的同构
「保住成果、只重跑坏的那步」= 与已合并 **TASK-522-D1**(不重解析、就地重生成 build_steps)同一恢复思路。差别:D1 是 plan 已存、只补 build_steps;本卡是 plan 完全缺失、从 spec 重跑整个 plan DAG。粒度更大,同一条路(overlay 不可变、失败保旧、单事务写回)。

---

## 2. 是 / 不是

**是**(后端):持久化 upload job 状态机 + per-doc 状态 + 崩点记录;fused spec 提前落盘(半成品合法化);**同一篇身份 + 重传 C 覆盖**(prepare-then-commit、失败保旧、只留最新版);`GET status`;`POST rerun-plan`(基于已存 spec 重跑 plan);异步上传执行能力 + 僵尸任务分流恢复;文件生命周期收口;TTL/cleanup 覆盖新表;对外契约 schema-sync 同步(仅本卡新增 DTO)。

**不是 / defer**:
- ❌ **前端任何改动**(进度条、重试按钮、失败话术、错误映射表)→ **后续前端批次(原 1C)**,PM 已拍搁置。
- ❌ **LLM 结构化稳定性**(PaperSpec/plan 加重试、schema 放宽、失败分类 telemetry)→ **卡二 TASK-526**。
- ❌ **历史多版本 + 存储上限**(同一篇留多次上传、超限淘汰、用户翻版本)→ **TASK-527(后继)**。本卡只立「同一篇身份」+ C 覆盖(只留最新版),为 527 铺地基。
- ❌ **spec-only 半成品下其它既有读回入口的错误契约统一**(`GET /plan`、tuning、ask、user-supply、reparse、regenerate 现碰 spec-only 谎报 404/400 的**话术**)→ **defer 前端批次**。PM 裁定用户不可见、前端不翻译即无害。**但 defer 仅限话术,不含功能崩溃,见 §8 红线 + §9 P0-5。**
- ❌ **不重传、重抽 PaperSpec**(要临存 raw text,522-B prepare-then-commit 纪律)→ 不在本卡;rerun-plan 只从**已存 spec** 走。
- ❌ 消解冲突(522-D2)、`parameter_conflicts` 重算 → 更后。
- ❌ 进度百分比(无阶段耗时 telemetry)→ 只做阶段状态(R1 P1-1)。
- ❌ durable 消息队列 / 外部 worker → 本卡用 FastAPI 后台 + DB 状态 + 僵尸恢复兜(真队列是更后演进)。

**★ defer 的唯一例外(本卡必须做)**:本卡新建的 **rerun-plan 入口必须正确处理 spec-only**;既有入口 spec-only 的**功能正确性**(不崩/不写坏/不泄漏)也须本卡 smoke 保证(§9 P0-5),只有**话术**才 defer。

---

## 3. 产品决定(PM 已拍,不重开)
- **后端优先、前端全搁置**:后端做完再敲前端。
- **核心价值 = 保住成果 + 能接着做**:成功解析的 spec 先存不丢;能基于它只重跑崩掉那步(不重传)。
- **崩点要准(做法二)**:后端在崩点记真实阶段(含 DB 持久化阶段),前端将来据此如实显示崩点。
- **重复上传走 C**:认同一篇、prepare-then-commit 覆盖、失败保旧、本阶段只留最新版。
- **历史版本 + 存储上限 = 单独 TASK-527**,本卡只立身份 + C 覆盖。
- **既有入口 spec-only 错误契约统一(话术)= defer 前端批次**;功能崩溃不 defer。

---

## 4. 状态机设计(R1 两轮意见并入)

### job 生命周期(粗粒度)
```
queued
  → running
    → spec_ready              # fused spec 已落盘、plan 未生成
      → plan_generating
        → ready               # spec + plan 都在,完整成品
        → plan_failed_retryable    # plan 崩、可重试(rerun-plan);默认归此
        → plan_failed_permanent    # plan 崩、确定性硬失败、不可重试(极窄,见 §5)
    → failed_no_usable_spec   # 无任一篇成功抽取,无可用 spec
  → abandoned_plan_retryable  # 僵尸:崩点在 spec 已存之后(可 rerun-plan 恢复)
  → abandoned_reupload_required  # 僵尸:崩点在 spec 存之前(无 spec、须重传)
```
> **`expired` 不入持久 job_state**(R1 P0-7):TTL 后删全部 job/per-doc/spec/plan/source;status 查已过期 → 派生返 **410 `paper_expired`**,不长期留 metadata(守隐私口径)。

### stage(细粒度,给「进度 + 崩点」;补 DB 持久化阶段,R1 P0-4)
```
uploading → parsing → extracting_spec → fusing → persisting_spec → generating_plan → persisting_plan → done
```
崩点 = `failed_stage` 落在崩的 stage(做法二)。**`persisting_spec`/`persisting_plan` 必列**——否则「后端记真实 failed_stage」被 DB 写失败打穿(spec 抽成了但存崩了 ≠ LLM 失败)。

### per-doc 状态
```
每篇: upload_index / document_id / status(pending|parsing|parsed|extracting|succeeded|failed)/ error_code
```
> per-doc 建议**独立表**(R1 P1-3:JSON blob 逐步更新易并发覆盖);若为 MCS 收窄用 JSON 内嵌,须加 optimistic version。Stage 0 定。

### bundle 层不变量(R1 定,与 Codex 坐实现状一致)
```
spec-only : paper_spec_cache 有 row、paper_plan_cache 无 row → 合法,可 GET spec、可 rerun-plan
ready     : spec row + plan row 都在                        → 合法,可 GET spec / GET plan
plan-only : spec 无、plan 有                                → 非法,StoreError(不伪装 404)
```
> Codex 坐实此三态存储层现状已如此;本卡把「spec-only 合法半成品」产品化为 job 状态,不改三态存储语义。

---

## 5. `plan_failed_retryable` vs `plan_failed_permanent` 边界(R1 定:默认 retryable、permanent 极窄)

**默认归 retryable**(同一 spec 重跑有合理成功概率;正是本卡 rerun-plan 要救的、与问题①「第一次崩第二次成」吻合):
- LLM JSON decode / schema validation / semantic validation 失败(输出随机性)
- PlanComposer / MissingDetector / BuildSteps / MScript 任一 role 输出不稳
- LLM timeout / server error / rate limit
- plan assembly 失败但输入 spec 合法
- `persisting_plan` 瞬时 DB 错误(spec 已存)

**仅这些归 permanent / non-retryable**(重跑同一 spec 无意义、不该让用户反复点):
- spec 不存在 / 已过期
- unsupported domain / input contract 不满足
- prompt 超硬上限且重跑不会变短
- deterministic spec invariant 失败
- auth/config 缺失(如 DeepSeek key 无效)
- 明确安全/隐私/policy guard 阻断
- DB schema 版本不兼容 / migration 失败

> **不因「schema validation failed」就 permanent**(R1 P1-5):它多半是 LLM 随机不合约,正是 rerun 要救的。初期宁可 retryable 多、permanent 少。

---

## 6. 范围(必须做)· 切两段 PR

> R1 认同切段 + rerun 放段一。段一 = 独立可验收的「保成果 + 能重跑 + 记状态」止血闭环;段二 = 纯异步执行 + 僵尸恢复。

### 段一(525-A · 状态基座 + spec 提前落盘 + rerun-plan + 同一篇身份/C 覆盖 · 止血闭环,先起)
- [ ] **schema 迁移**:新增 `paper_upload_job` 表(+ per-doc status 表,R1 P1-3 建议独立表)+ 字段 `execution_mode(sync|async|rerun_plan)` / `created_at` / `started_at` / `finished_at` / `attempt_count` / `last_error_code` / `state_version`(R1:审计 + CAS 需版本号)。走现有迁移体系加 `v7_to_v8`,bump `CURRENT_SCHEMA_VERSION`(Codex 坐实现为 7;Stage 0 核 live)。
- [ ] **状态机落地**:§4 job_state / stage(含 persisting_*) / per-doc / bundle 不变量 / §5 retryable-permanent 边界。
- [ ] **同一篇身份 + 重传 C 覆盖(★ 解 R1 最大 P0)**:Stage 0 先定 `paper_id` 是否每次上传唯一(见 §10)。按 C:同一篇已有 ready plan 时重传 → **prepare-then-commit**——新 plan 跑成功后**单事务替换**旧 ready、**失败保旧 ready、不产生 spec-only、不先删旧**;本阶段只留最新版(历史版本 = 527)。**禁 `delete_plan → put_spec → generate` 序列**(旧 ready 在新成功前被破坏,违反失败保旧)。
- [ ] **同步 upload 内部改造走同一 orchestrator**(R1 调整二收紧,禁两套 pipeline):抽出 `create_upload_job` / `run_upload_job(job_id, execution_mode)` / `run_plan_generation(job|paper, source=initial|rerun)`;同步端点 = create job → `await run_upload_job(sync)` → terminal ready 返旧 200 body / terminal failed 返旧错误 envelope **+ additive `paper_id`(P0-1,失败也必返,否则 rerun 够不着)**。**对外仍同步 200 + spec+plan(成功),前端不崩。**
  - Codex 坐实:提前落盘点可干净插在 `fuse_successful_specs(...)` 之后、`generate(...)` 之前。
  - Codex 坐实:只写 spec 现成路径 = `put_spec()`(有 `paper_spec_overwrite_for_existing_plan` 守门);不在 route 依赖的 `PaperReparseStore` 接口 → 需把「只写 spec」纳入 route store 接口。
- [ ] **`GET status`**:返回 §5 契约草案字段(含 `next_action`)。
- [ ] **`POST rerun-plan`**:读已存 spec(`spec_ready`/`plan_failed_retryable`)→ 重跑 plan DAG(复用 `run_plan_generation(source=rerun)`)→ 成功单事务 `set_plan` 写 ready / 失败保 spec-only。**只重跑 plan、不重抽 spec、不复活失败篇、不碰原文件**;TTL 不续命。
  - Codex 坐实:`set_plan` 要求 spec 先存(`paper_spec_missing_for_plan`),spec-only 满足。
- [ ] **锁 + CAS 顺序全项目统一**(R1 P0-6):定死一个顺序(lock-first 或 CAS-first 二选一),rerun-plan / reparse / user-supply / correction / regenerate 任一写 plan 者一致遵守,复用 D1/C2 `PaperReparseLockRegistry` additive;**DB 原子状态转移(CAS)** `WHERE state IN ('spec_ready','plan_failed_retryable') → 'plan_generating'` 只一方成功;单进程锁不够(worker 前提)。
- [ ] **TTL / cleanup 覆盖新表**:`delete_bundle` / TTL sweep / `replace_ready_bundle_with_source` 三处级联加 job 表 + per-doc 表(Codex 坐实现清 plan/spec/reparse_source/parameter_correction 四表,同事务加新表);**TTL 从首次持久化算,rerun 不续命**;`expired` 派生返 410、不留持久 metadata。
- [ ] **对外契约同步(仅本卡新增 DTO)**:`PaperStatusResponse` / `PaperJobDocumentStatus` / `RerunPlanRequest` / `RerunPlanResponse` /(同步失败 additive envelope 若增字段)进 export/verify-schema/freeze/06/TS。**补基建缺口**:route DTO 未纳入 schema 导出 → 扩 `export_paper_schemas.py`(或新 `export_paper_route_schemas.py`)只纳本卡 DTO,freeze 锁字段名/枚举/`extra=forbid`,06 增 status/rerun 小节,TS mirror 只维护本卡新类型。**不顺手纳入既有 `UploadDocumentResponse`/GET spec·plan 等旧 DTO**(R1:防膨胀成「paper route schema 大清理」)。
- [ ] **段一后端真测试**:spec 提前落盘 / plan 崩后 spec 保住 / rerun 基于已存 spec 成功 / rerun 并发原子(CAS)/ 崩点记录(含 persisting_*)/ TTL/cleanup 覆盖 / **重传撞旧 ready 走 C prepare-then-commit + 失败保旧** / **spec-only 下既有入口 smoke(§9 P0-5)** / 隐私红线。

### 段二(525-B · 异步执行 + 僵尸恢复)
- [ ] **异步上传入口**:`202 + job_id/paper_id` 立即返回;后台执行走**同一 orchestrator** `run_upload_job(async)`(不复制 pipeline);参照工程 zip 样板(`BackgroundTasks + GET status + Store`,Codex 坐实),状态机 paper 版更细。
- [ ] **文件生命周期收口**(R1 P0-3):上传文件先安全落 staging → 返 202 → 后台读 → **抽完 spec 即删**(rerun 从 spec 走、不需原文件,不长期留、守隐私);不依赖 `UploadFile` 句柄;route `finally` 不删后台要读的文件。
- [ ] **僵尸任务分流恢复**(R1 P0-2/P0-3):`BackgroundTasks` 非 durable,进程重启遗留 `running` → stale 处理。**分流**:崩点在 spec 已存之后 → `abandoned_plan_retryable`(可 rerun-plan);崩点在 spec 存之前 → `abandoned_reupload_required`(无 spec、`retryable=false`、`next_action=reupload`)。启动时扫描标记;**不让状态永卡 running**;**不给点不通的重试**。
- [ ] **rerun-plan 是否 job 化**(R1 P1-4,Stage 0/PM 定):段一 rerun-plan 若同步等待 plan DAG,前端将来点「重试生成计划」仍会等;若 PM 要 retry 也不干等,段二把 rerun-plan 也纳入 job 化。默认段二不做,记后继。
- [ ] 段二真测试:异步入口 / 后台编排逐步状态 / 僵尸分流恢复 / 文件生命周期 / 并发。

---

## 7. 不做(§2 已列;补充)
- ❌ 改 `PaperSpec.parameter_table`(overlay 不可变红线,继承 C1/C2/D1)。
- ❌ 改已合并 522-B reparse / 522-C 纠错 / D1 regenerate 行为本体(本卡只在清理级联加表 + 复用锁 registry additive + 统一锁/CAS 顺序)。
- ❌ 顺手纳入既有旧 route DTO 到 schema 导出(只补本卡新增 DTO)。
- ❌ 历史多版本 / 存储上限(527)。

---

## 8. 关键红线(继承 + 本卡新增)
- **overlay 三层不可变**(继承):`spec.parameter_table` 不可变;rerun 只改 plan、不动 spec/correction。
- **失败保旧、单事务写回**(对齐 522-B / D1):rerun 失败保 spec-only;**C 覆盖失败保旧 ready、不产生 spec-only、不先删旧**;成功单事务写。
- **rerun / C 覆盖不续命**:TTL 从首次持久化算,rerun/retry/覆盖不延长(R1 P0-5)。
- **失败篇不复活**(R1 P0-9):rerun 只基于已持久化 fused spec,原上传失败篇不偷偷重新参与。
- **日志/隐私脱敏**(decision 11,硬红线):禁 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info`;**参数值/单位/原文/filename/异常 message/堆栈不进日志、错误响应体、telemetry、status DTO**;SQL 错误只 log `type(exc).__name__`;崩点/status 只记**阶段名/error_code 分类**。
- **decision 08**:改文本文件保原始字节。
- **★ 错误契约统一 defer 的边界**(本卡红线,R1 收紧):既有读回入口(GET /plan / tuning / ask / user-supply / reparse / regenerate)spec-only 的**话术**本卡不改(defer);但**功能崩溃不 defer**——spec-only 下这些入口须**干净拒绝**(4xx/409),**不得 500 / 不得误写 plan-side / 不得生成 plan-only / 不得删 spec / 不得空 build_steps 覆盖 / 不得空 plan 硬答 / 不得泄漏日志**;本卡新建 rerun-plan 入口必须正确处理 spec-only。后续会话/前端批次改话术时,须知本卡已产品化 spec-only 半成品,别当「不存在」。

---

## 9. 风险与注意点(R1 两轮 P0/P1 并入)

**P0**
1. **sync plan 失败后无 ID → rerun 闭环不可用**(R1 P0-1,段一硬约束):同步失败响应/header 必返 `paper_id`(或 job_id/status_url 至少一项),additive 前端可暂忽略但契约必须在。否则段一只是「DB 止血」、非可用闭环。
2. **★ existing ready bundle 与提前 `put_spec()` 冲突**(R1 判定本卡最大 P0):同一篇重传、DB 已有 spec+plan 时,提前 `put_spec()` 撞 `paper_spec_overwrite_for_existing_plan`。**PM 定走 C**:唯一 attempt/或 revision/或 prepare-then-commit 覆盖(新成功再单事务换、失败保旧);**禁先 delete_plan**。**Stage 0 必先答 `paper_id` 是否每次唯一 + 已 ready 再上传如何处理,不可实现时硬上。**
3. **`abandoned` 误标**(R1 P0-3):stale running 仅 spec 已存(或 staging 可安全恢复)才 retryable,否则 `abandoned_reupload_required`;否则前端将来给用户点不通的「重试」。
4. **缺 `persisting_spec/persisting_plan` 崩点**(R1 P0-4):本卡核心新增 DB 写点,无持久化 stage 则崩点不准,打穿「记真实 failed_stage」的产品决定。
5. **spec-only 下既有入口须 smoke**(R1 P0-5):defer 话术可、defer 500/误写/误删/泄漏不可。GET /plan、tuning、ask、user-supply、reparse、regenerate 逐个 spec-only smoke——不 500 / 不写 DB / 不删 spec / 不产 plan-only / 不泄漏 / 返 4xx-409 可接受(话术 defer)。
6. **rerun-plan 与 522-C/D1/reparse 并发互斥**(R1 P0-6):同一 paper_id 上任一写 plan 操作(rerun/reparse/user-supply/correction/regenerate)共享锁 + 共享 DB revision + **统一 lock/CAS 顺序**;不能只给 rerun 自己加锁。
7. **TTL cleanup 与 `expired` 矛盾**(R1 P0-7):cleanup 删 job/per-doc 行则 `expired` 不能是持久 job_state → 改 status 派生返 410;留 tombstone 需 PM 明确允许超 24h 留非内容 metadata(当前口径不取)。
8. **status 端点枚举/泄漏**(R1 P0-8):无用户体系则 paper_id/job_id 须不可猜 + TTL 短;status 不回 filename/原文/参数值/异常 message(已在红线)。

**P1**
1. status 加 `next_action`(R1 P1-1):wait / rerun_plan / reupload / open_result / none / contact_support,比单 boolean 稳。
2. job 表加 `attempt_count`/`state_version`(R1 P1-2):rerun 多次后审计 + CAS 需版本号。
3. per-doc 独立表优于 JSON blob(R1 P1-3);JSON 则加 optimistic version。
4. rerun-plan 是否同步须提前定(R1 P1-4):段一 rerun 大概率同步等待,前端将来点「重试」仍等;PM 要 retry 不干等则段二 job 化 rerun。
5. `plan_failed_permanent` 初期少用(R1 P1-5):分类不准夺走可恢复机会,permanent 只给确定性硬失败。
6. 进度不做百分比、只阶段状态(R1 上轮 P1-1);「真实文件名更稳」未证实、不作设计依据(Codex + R1)。

---

## 10. Stage 0 可落性 gate(Codex 派单前核 live,不符停手报架构师,禁兜底硬上)
1. `git fetch origin && git rev-parse origin/main` 报 HEAD;**核 525 号未被占**(查索引 + 决策 22 分段)。
2. 确认本卡随代码入 `docs/tasks/`(PM 预放,untracked=预期)。
3. **复核 Codex 三轮取证 as-built 仍成立**(贴 RAW 定性):spec/plan 分表 + spec-only 三态语义;上传入口同步现状 + save 在 plan 后 + 提前落盘点可插;`put_spec`/`set_plan` 守门;schema 版本 + 迁移体系 + 清理级联四表;工程 zip 异步样板 + 无僵尸恢复;worker 前提。
4. **★ C 方案落地核(R1 最大 P0,必先答)**:
   - **`paper_id` 是否每次上传唯一?** 贴生成方式本体。
   - 若不唯一(可复用):已有 ready bundle 再上传如何处理?选 A(每次新 paper_id)/ B(新 revision/bundle_id 不覆盖)/ C(prepare-then-commit 覆盖、失败保旧)——**本卡 PM 定 C**,核 prepare-then-commit 在现有 store 能否原子落地(新 plan 成功再单事务替换旧 ready、失败保旧、不先删)。不可原子实现 → 停手报架构师。
5. **本卡高风险落点 gate**(核准才动):
   - 同步 upload 内部改造走**同一 orchestrator**(create_upload_job / run_upload_job / run_plan_generation)、对外 200 不变可行(不破坏现有前端/测试)。
   - 提前 `put_spec` + `paper_spec_overwrite_for_existing_plan` 守门 + C 覆盖交互不撞。
   - DB 原子状态转移(CAS)+ 统一 lock/CAS 顺序可实现 rerun/后台执行/既有写 plan 操作互斥。
   - 文件 staging → 202 → 后台读 → 抽完删,不依赖句柄、不长期留。
   - status/rerun DTO 纳入 schema 导出/freeze/TS 落点(补 route DTO 未覆盖基建缺口,只纳本卡 DTO)。
   - **spec-only 下既有入口 smoke 预核**:哪些干净拒绝、哪些会 500/误写(后者本卡必修,前者 defer 话术)。
6. 任一不符 → 停手诊断(decision 15)。

---

## 11. 给 Codex 的提示(派单实现阶段)
- 走 feature branch(git fetch 后从 origin/main 切,不许 main 直推)。
- **段一(525-A)先起、可独立验收**(止血闭环:保成果 + 能重跑 + 记状态 + 同一篇身份/C 覆盖);段二(525-B)后起(异步 + 僵尸分流恢复)。**两段各独立 PR**,不一个 PR 全塞。
- **卡随代码同 PR**;**索引收尾单独 PR**;本代码 PR 不碰 `03_TASK_INDEX.md`(decision 07)。
- PR 全走 PM 网页侧:Codex 给标题 + 正文草稿 + `pull/new` 链接,PM 建 PR + squash merge(不自建 PR、不用登录)。
- `make check` 全管道,禁拆 CI step 列;显式加 `make export-schema && make verify-schema` + freeze + `pnpm typecheck`(status/rerun DTO 映射 TS)。
- **同步/异步共用同一 orchestrator**(禁复制两套 pipeline);同步失败也必返 `paper_id`。
- **spec 提前落盘**:fuse 成功即 `put_spec`,plan 崩 spec 已在;对外同步 200 不变。
- **重传走 C**:prepare-then-commit 覆盖旧 ready、失败保旧、不先删、只留最新版;禁 `delete_plan → put_spec → generate`。
- **rerun 只重跑 plan**:不重抽 spec、不复活失败篇、不碰原文件;失败保 spec-only、成功单事务 `set_plan`;TTL 不续命。
- **崩点含 persisting_spec/persisting_plan**;status 带 `next_action`;僵尸分流 `abandoned_plan_retryable` / `abandoned_reupload_required`。
- **僵尸恢复 + 文件生命周期 + DB 原子转移 + 统一 lock/CAS 顺序**:段二/并发核心 P0,贴本体核。
- **spec-only 既有入口 smoke**:不崩/不写坏/不泄漏即 defer 话术;真崩了本卡修。
- **隐私红线亲核**(贴本体不凭勾选):参数值/单位/原文/filename/异常 message/堆栈绝不落日志/console/error body/telemetry/status DTO;崩点只记阶段名/error_code 分类。
- 本机无 `grep`,用 `git grep`/`rg`/`Select-String`;行尾/字节(08);异步/日志(11)。
- 合并前架构师亲核后端真 diff + 对外零 drift(新增 DTO 除外,须证纳入 schema-sync);RAW 取证/diff 贴对话、去行号、不收本机路径。

---

## 关键契约草案(R1 建议版,Stage 0 定死)
```
job_state:
  queued / running / spec_ready / plan_generating / ready
  plan_failed_retryable / plan_failed_permanent / failed_no_usable_spec
  abandoned_plan_retryable / abandoned_reupload_required
  (expired 派生返 410,不持久化)

stage:
  uploading / parsing / extracting_spec / fusing
  persisting_spec / generating_plan / persisting_plan / done

status response:
  paper_id / job_id / execution_mode / job_state / stage / failed_stage
  error_code / retryable / next_action / expires_at / documents[]

next_action:
  wait / rerun_plan / reupload / open_result / none / contact_support
```

---

**版本**:v0.2(架构师定稿,并 R1 第二轮设计审[条件通过·8 P0/5 P1]+ PM 两决定)
**作者**:Claude(架构师)
**审批级别**:R1 两轮设计审(方向 + 具体卡)条件通过 + PM 拍(后端优先/四件/重传 C/历史版本 defer 527)→ 待 R6 派单前 Stage 0 可落核(含 C 方案落地核)→ 派 Codex
**前置**:main 含 D1(#166)/ 522-C1(#162)/ C2(#164)/ 521-B2(#154)/ 524(#173)(Codex 坐实均在;Stage 0 用 `git merge-base --is-ancestor` 复核,允许 main 合法前进)
**后继**:卡二 TASK-526(LLM 结构化稳定性 · 问题①)/ **TASK-527(历史多版本 + 存储上限)** / 本卡前端批次(原 1C:进度条 + 重试按钮 + 失败呈现 + 错误契约话术统一)/ TASK-522-D2(消解冲突)
