# TASK-518:run-state 持久化 + 跨轮状态机(v0.3-b / b3-2b)

## 状态
🔲 **v0.3 定稿,过审待派 518-A**(2026-06-25)。定向复审:**R1(GPT)无条件 ACK**(5 P0 + 6 P1 全闭合;倾向 b4-only 退役 b3,理由成立);**R6(Codex)有条件 ACK**——`origin/main 664d9ce` 复核无 decision 15;P0/P1 落对;剩两条实施规约(已写进本 v0.3 §24h 硬保证 + §状态机·establishment;架构师定,非 PM 拍):24h 物理删 = **run-state 专用 sweep + 受控提前 cutoff,不动全局 `CleanupWorker`**;establishment = **dev-auth route 级 additive,DB 副作用不进 `BridgeAuthService` / `get_settings()`,establish 失败不返 token**。**§待复审确认 #1(b4-only 退役 b3)已锁**。 

**门已满足**:517-A(#120)+ 517-B(#121)均已合并 main。**仍无 LLM**(LLM 解释 / 读历史 / 建议 = c / TASK-519)。

---

## 编号与拆分
- **TASK-518**(父卡;派单前 Codex grep 复核空号 518/519)。代号 b3-2b。
- 两个独立过审的 PR(照 517 套路,先搭骨架再开写口):
  - **518-A substrate**:权威 session + 不可变 run 快照的**存储 + 状态机 + 受信 establishment + 24h 硬过期机制**(表 / 迁移 / Store / core 纯状态机 + 指纹 / session 终态机 / establish·end·delete 路径),**不开放 `/run-state` 写路径**(consume 仍返回 b3 `durable=false` 临时回执)。
  - **518-B wiring**:把写事务接进 consume——**同一串行化边界**内做权威 session 校验 + 幂等 / 冲突 / 顺序 + current 切换 + 持久化;**协议升 `0.3-b4` + 回执 durable=true 定型**(decision 13 全清单)+ 客户端处理新回执 / 错误码 / **改存储同意文案**。
- **c(TASK-519)须 518-A、518-B 均合并后才派**;顺序 `a→b→c` 不重开。

---

## 背景与定位
- TASK-517 §架构站位锁:「权威 session 校验(归属 / active / 未过期 / 幂等 / 冲突 / 顺序 / current)在 **b 同一原子写事务内**完成。a 只交付 auth context,不查 session 内容、不判 active、不写库、不建 session。」本卡 = 落写事务 + 状态机 + 持久化 + **a 没建的 session establishment**。
- TASK-516 DP-6 锁:b3-1 = 无状态 ingress(不含持久化);**持久化 + 跨轮状态机 = b3-2,一旦写盘须同时落 token scope / TTL / 删除 / 隔离 / 幂等冲突 / 过期拒写**。
- **能力 ≠ 同意 / 沿用 a 授权(517 锁)**:`run_state:write` 只是写授权;持久化同意来自客户端每轮的 `run_state_sharing_consent_confirmed=true`(见 §同意语义)。
- 副驾边界不变:服务端不跑用户模型、不接收 / 反序列化原始 MAT/CSV;只持久化客户端抽稀 + 脱敏 + 每轮确认过的有界快照 + 派生状态。

---

## 实测地基(`origin/main 664d9ce`,Codex R6 两轮实测;R1 无 repo,自包含)
*(Stage-0 须对最新 origin/main 复核;HEAD 可能已前进)*

**`/run-state` 现状(517-B 后)**:route-wrapper(`MatlabBridgeRoute`)级 enforcement——验 `Authorization` → 解析 `BridgeRunStateRequest` → `verify_token(run_state:write)` → `canonical(body.session_id)==canonical(token.session_id)` 否则 403 → 写 `request.state.bridge_run_state_request` + `bridge_auth_context`。handler 从 `request.state` 取已校验对象,调 `service.consume(request_body.to_domain(), auth_context)`。**consume 当前 `_ = auth_context`,redact 后返回 `validated / ephemeral_validation / durable=False`,未查 session、未写库。**

**516 锁定的标识语义(R1 P0-1 依据,Codex 实测 `task-516 v0.4` 确认)**:
- `request_id:UUID` = **每个 HTTP 尝试一个**。
- `run_id:UUID` = **一个逻辑不可变快照一个;重试沿用同一个**(规则 2)。
- `run_sequence:int(0..1_000_000)` = **会话内单调**。
- 客户端 `snapshot_fingerprint` **已删**;幂等 / 冲突真值由 **b3-2 服务端**对「校验 + 规范化 + 二次脱敏后语义快照」计算,日志不记指纹。
- 客户端不可变快照:生成 `run_id` → 固定字段序构造 → frozen_json → frozen_bytes;**预览 = 发送**(逐字节一致);取消 = 零网络;重试沿用同一 frozen_bytes(含同一 `run_id`)。

**请求载荷(均有界)** domain `BridgeRunStateRequest`(`core/domain/bridge_run_state.py`,现为 dataclass+UUID,无 Pydantic/HTTP/store):`protocol_version="0.3-b3"`、`request_id`、`session_id`、`run_id`、`run_sequence`、`matlab_release`、`client_version`、`run_state_sharing_consent_confirmed`(强制 true)、`run_status`、`convergence_status`、`stop_reason?`、`solver?`、`metrics_status`、`metrics`(≤16)、`series_status`、`series`(≤4:identity[2..192]/envelope[96])。上限 16/4/192/96。

**脱敏** `redact_run_state_request`(consume 内对 domain 做):字符串字段命中 path/secret/source/model-metadata → `[REDACTED_*]`;UUID / status / 数值 / source_point_count / t_start / t_step / bucket_width / y / y_min / y_max 不改。

**回执** domain `BridgeRunStateReceipt`:`status:Literal["validated"]` / `mode:Literal["ephemeral_validation"]` / `durable:Literal[False]` / 回显 `request_id`/`run_id`/`run_sequence`(**无 protocol_version 字段**)。

**`chat_session` 表**:`session_id(PK)` / `project_id(NOT NULL, FK→project_status_record ON DELETE CASCADE)` / `created_at` / `updated_at` / `title`。**无 active/expires/generation/owner/capability**。其子表(FK→chat_session ON DELETE CASCADE)= **`chat_message`**(Codex 确认)。

**关键:`token.session_id` 不绑 `chat_session`(Codex P0,实测)**:dev issuer(`api/routes/matlab_bridge_auth.py` 的 `issue_token`)**不查、不创建、不绑定** `chat_session`;`session_id` 仅由 dev-auth 请求体(`BridgeDevAuthTokenRequest`)传入、签进 claim(`bridge_auth_service.py` 只 `_require_identifier`)。→ **518 不得默认 FK `chat_session`**;权威 run-state session 自立(见 §状态机)。

**迁移机制**:无 Alembic;**代码内 registry**(`adapters/storage/schema.py`:`CURRENT_SCHEMA_VERSION=4` + `_MIGRATIONS={1,2,3}`)。

**`BridgeAuthContext`**(`core/domain/bridge_auth.py`,frozen):持 `claims`(`user_id/project_id/session_id/capabilities/token_id/issued_at/not_before/expires_at/process_generation`);仅 verifier factory 产。→ b 从 auth_context 派生 scope,不从 body 取信任。

**留存现状**:`chat_session` 无自有 TTL;project 24h 周期清理(`CleanupWorker`,**interval 60min**),删 project FK cascade 清 chat/chat_message。**注:60min 扫 + 24h TTL → 物理删最坏 ~25h,非硬 ≤24h(R1 P0-4)**。

**串行化先例(Codex 实测)**:`adapters/storage/_connection.py` 开 `PRAGMA journal_mode=WAL` + `busy_timeout=5000` + `foreign_keys=ON`;`sqlite_teaching_unit_store.py` 已有 `BEGIN IMMEDIATE ... commit` 先例 → 单连接单事务可给「单 writer」串行化。

**客户端确认文案现状(Codex 实测)**:`defaultConfirm.m` 弹「发送诊断信息?」选项 `["发送","Cancel"]`,SafetyPrompt = 「请勿粘贴源码、账号、密钥或其他敏感信息」→ **仅「发送」口径,未覆盖「存储」**(518-B 须改)。

**schema 机制**:bridge schema 现 **14**;`export_bridge_schemas.py` + `Makefile verify-schema` 显式列清单;各 schema freeze/drift + round-trip;OpenAPI `/run-state` 挂 `BridgeRunStateBearerAuth`、响应 `{200,401,403,413,415,422,503}`,`/diagnostic`·`/explanation` 无 security。无 `logger.exception`(生产)。

---

## 已锁(不重开;PM / 515 / 516 / 517)
- **留存上限 24h、跟工程清**(PM);**「一删 / 一停立刻清、绝不长期备份」不变**;跨天 / 延长留存属另起范围。**24h 须实现成可证明硬上限**(见 §24h 硬保证)。
- **516 标识语义**:`request_id` 每尝试一个;`run_id` 每快照一个(重试沿用);`run_sequence` 单调;指纹服务端算。
- run/session 8 规则 + 数据边界 5 条 + 留存删除(515 v0.4);独立通道 ≠ 原始上传。
- 517 全部:route-wrapper auth 门 / 守序 / 32KB / handler 从 `request.state` 取 / 两老端点字节+语义不变(**518-B 改 durable→true 是有意契约演进,但不得回退 auth 门 / 守序 / 两老端点**)。

---

## 状态机 + 写事务设计(v0.2;收 R1 五 P0 + Codex P0)

### session 权威来源(解 §待 R1 裁 #2 + R1 P0-5 + Codex P0)
- **独立权威 run-state session**,**不是 chat_session 扩展**(Codex 证 session_id 未绑 chat_session)。`bridge_run_state_session.session_id` **FK→`project_status_record(project_id) ON DELETE CASCADE`**(给 project 删 / 24h 级联),**且自带终态机 + establish/end/delete 路径**——「session 删即清」由该终态路径保证,**不靠 FK→project 单独成立**(R1 P0-5)。
- 若未来要挂 `chat_session`:须新增「签发前 / 首写前 chat_session 存在且归属一致」机制(Codex)——**本卡不做,留 future**。

### session 终态机(R1 P0-2;消除 v0.1「不懒建 vs 首写懒建」矛盾)
```
active  --end-->        ended      (单调,不可回 active)
active  --expiry到-->   gone       (project_expires_at 到点逻辑失效)
ended / gone:          后续写一律 410,不复活
```
- **受信 establishment 挂载方式(R6 钉死)**:**dev-auth route 级 additive orchestration**——`api/routes/matlab_bridge_auth.py` 在签发 token 前,额外注入 run-state Store,受控 establish + 校验 project 存在与未终态;**establish 失败 → 不返回 token**(fail-closed)。**DB 副作用不进 `BridgeAuthService` 或 `get_settings()`**(保 517 auth service 纯净);**不改 token/auth 契约**。**establishment 幂等**(同 session 重签 = 刷新,不改 lifecycle;**对 ended/gone 不复活**)。
- **`/run-state` 写路径绝不懒建 session**:记录缺失 → **410**(R1 P0-2/P0-5)。
- **`ended`**:在同一写事务内清该 session 的 run 快照 + current 指针 + 派生状态;**保留不含快照内容的最小终态 session 行**当 tombstone(直至 project 删 / TTL)——**不另建 tombstone 表**。
- **session 过期 = 权威 session / project 生命周期,不是 token `exp`**(R1 P1-4):**不把 `session.expires_at` 设成 token 的 `exp`**(刷新不得隐式延长 / 截短逻辑 session)。`process_generation` 不匹配 = 「旧代次 session」→ **410**;重启后产品行为:旧代次 session 不可续写,须新建。

### 表(草案,518-A;字段名随 R6)
1. **`bridge_run_state_session`**:`session_id(PK,canonical)` / `project_id(NOT NULL,FK→project_status_record ON DELETE CASCADE)` / `user_id` / `process_generation` / `status`(精确字面 `active|ended|gone`,**无省略号**) / `current_run_id?` / `established_at` / `ended_at?`;过期取 project 生命周期(见 §24h 硬保证),**不存 token exp**。
2. **`bridge_run_state_run`**(不可变):`run_id` / `session_id(FK→session ON DELETE CASCADE)` / `run_sequence` / `request_id`(**仅查误复用,非业务幂等**) / `fingerprint` / `fingerprint_version` / `canonical_bytes`(或其引用) / `run_status` / `convergence_status` / `snapshot_json`(脱敏后) / `received_at`。
   - 约束:**`UNIQUE(session_id, run_id)`**(rule 2 业务幂等键)、**`UNIQUE(session_id, run_sequence)`**(rule 4 单调)、`UNIQUE(session_id, request_id)`(仅发现误复用);**run 行永不 UPDATE**;`current_run_id` 加 FK / 组合约束防漂移(或删冗余 `current_run_sequence`)。
- 级联 / TTL:随 project 删 + 24h(§24h 硬保证);迁移 `_migrate_v4_to_v5` + `CURRENT_SCHEMA_VERSION=5`,**fresh DDL + registry 同补**(Codex P1)。

### 幂等 / 冲突 / 顺序(R1 P0-1,改正 v0.1)
- **业务幂等键 = `(session_id, run_id)`**(**不是 `request_id`**——重试沿用同一 `run_id`,`request_id` 每尝试不同;用 request_id 当键会让超时重试插第二行,违反 rule 2/3)。
- rule 3 改写:**同一 `run_id` + 同规范化持久化快照 = 幂等(返回同一业务结果);同一 `run_id` + 不同规范化快照 = 冲突(409)。**
- `run_sequence == current_run_sequence`:同 `run_id` 同快照 = 幂等;**不同 `run_id` 同 sequence = 409 sequence conflict**。
- rule 4:`run_sequence` 旧于 current → 收为历史、**不作 current**。

### 服务端指纹(R1 #3 确认正确 + 收紧;core 纯)
- 算在**脱敏后语义快照**上(规范化内容,非原始敏感内容)——「两请求仅差被脱敏掉的字符串」落库相同 → 判幂等(也避免敏感内容稳定哈希侧信道)。
- **覆盖全部不可变持久化语义**:`run_sequence`、各 status 字段、脱敏后 `stop_reason/solver`、release/client version、metrics/series 状态及数据;**排除每尝试变化的 `request_id`**。
- **canonical JSON 字节** = 哈希同一份;存 `fingerprint_version`;哈希相等再比 canonical bytes(防算法升级 / 极低概率碰撞误判)。**客户端不算 / 不传**。

### core 纯状态机(decision 21;R1 P2 拆模块 + R1 P1-1 补输入契约)
- 新 **`core/domain/bridge_run_state_machine.py`**(纯状态机判定 + 指纹规范化),与 `bridge_run_state.py`(dataclass)分开。
- 判定纯函数输入 = **(session 终态, `existing_run_by_run_id`, `existing_run_by_sequence`, current 信息)**——由 Store **在事务内**提供;输出 `{幂等重放 | 收为 current | 收为历史 | 冲突 | 拒绝(410)}`。无 IO。

### 写事务(518-B;同一 SQLite 写串行化边界,R1 #4)
- **所有生命周期写(establish/end/delete、project cleanup)与 run 写共用同一写串行化边界**。
- 顺序:`从 auth_context 派生 scope` → `校验 session(active/未过期/归属/代次,缺失或失效=410)` → `判幂等/冲突/sequence` → **`先 INSERT 不可变 run 行`** → `再原子更新 current` → `commit`。
- **并发测试用两个独立 SQLite connection + barrier**,不靠单进程 asyncio lock 自证(R1 #4)。
- 写路径在状态机就位前不开:状态机 / 表 / Store / establishment 在 **518-A 落且 consume 仍 ephemeral**;**518-B 才接进 consume**。

---

## 24h 硬保证(R1 P0-4;不重开 PM 的 24h,补成可证明;R6 钉死机制)
- **权威 `project_expires_at` 计算来源**(R6 实测):`project_status_record.created_at + settings.upload_ttl_hours`(默认 24h);Store 层用**同一来源**算,**不从 token exp / chat_session 推**;与现 `SqliteProjectStore.list_expired()` 一致。
- **逻辑失效(主)**:`project_expires_at` 到点即逻辑失效——任何 run-state 读 / 写在到点后一律 **410**,不依赖物理清理时机(让「24h 后不可访问」为真)。
- **物理删机制**(R6 钉死,**不动全局 `CleanupWorker`**):**run-state 专用 sweep + 受控提前 cutoff**——按 `project_created_at + 24h − sweep_interval − safety_margin` 物理删,确保物理数据最晚 24h 内消失;**不改全局 `CleanupWorker` 节奏 / 不影响 ingest 等其它 feature**。
- **客户端文案口径**(R6):写「**最长不超过 24h,可能更早删除**」,不写死「刚好 24h」——比承诺精确时点更稳。
- **清理失败 fail-closed + 测试 + 监控**;sweep 失败不得让逻辑失效退化为「可读」。
- **此机制闭合前,客户端不得承诺「存储 ≤24h」**(故 §同意语义 文案改与本节绑定)。

---

## run / session 8 规则映射(515 v0.4;v0.2 逐条钉死,验收对应)
1. 真值在客户端;只存脱敏后有界快照 + 派生 → 只落 redact 输出;consent 强制。
2. re-run = 新不可变快照,旧不覆盖 → `UNIQUE(session_id, run_id)` + run 行永不 UPDATE。
3. 同 run_id 同快照 = 幂等;同 run_id 不同快照 = 冲突 → `(session_id,run_id)` 键 + 服务端指纹;冲突 **409**。
4. 乱序旧 run 仅历史 → `run_sequence` 比较;equal-sequence 决策(同 run_id 幂等 / 异 run_id 409)。
5. 串行 + 单 current → 单写串行化事务 + `UNIQUE` 约束;**两连接并发测试**只一个 current。
6. 失效 session 拒写不复活 → 终态机 `active→ended/gone`、`/run-state` 不懒建、缺失 / 失效 = **410**;续调须新 session。
7. 删除 / TTL 全清 → FK cascade(随 project)清两表 + **24h 硬保证**(逻辑+物理)。
8. user/project/session 隔离 → scope 从 auth_context 强制;**保持 403(归属/scope 不符)与 410(session 失效)分界**;派生不进长期 cache/备份/分析日志。

> 闭合判据:以上 + §验收门 B-2 逐条钉死后方称「8 规则 enforcement 周延」(v0.1 不可宣称,R1)。

---

## 同意语义(consent ≠ authorization;R1 #5 + Codex P1)
- 写授权 = 517 scoped token(`run_state:write`);**持久化同意 = 每个逻辑 run 的 `run_state_sharing_consent_confirmed=true`**;两者分离(不沿用 a 授权当同意)。**不新增请求字段作同意**。
- **「每轮」= 每个新逻辑 `run_id` 确认一次**;同一已确认冻结快照的 HTTP 重试**不再弹框**;**410 后新建 session/new run 须重新确认**。
- **确认文案(518-B 必改;Codex 证现状仅「发送」)**:须覆盖**数据类别 / 用途 / 持久化 / 最长留存 / 删除条件**(不止「发送」);**且仅在 §24h 硬保证闭合后才写「最长不超过 24h,可能更早删除」**(口径见 §24h)。**注意 R6**:现 `defaultConfirm.m` 被 `/diagnostic`·`/explanation`·`/run-state` 共用,**存储文案做成 run-state 专用或 context-aware**,**不误套到旧两端点**(旧两端点是 ephemeral validation,无持久化语义,套上「存储 ≤24h」会误导)。
- **锁 consent notice 版本**:新增 `consent_notice_version`(或 `client_version → notice version` 可测试映射)。

---

## 契约变更 + decision 13 同步面(518-B 触发;逐项贴 diff,缺一=未完工)
**变更(R1 P0-3,改正 v0.1)**:**`protocol_version` 升 `0.3-b3 → 0.3-b4`**(请求 + 回执);**b4 回执回显 `protocol_version` + 固定三元组** `status:Literal["persisted"]` / `mode:Literal["durable_persisted"]` / `durable:Literal[True]`(+ 回显 request_id/run_id/run_sequence)——**不把 durable 放宽成 bool**(防 `validated+durable=true` 非法组合);旧 b3 字面**不在同一模型混用**。**run-state 路径 b4-only,退役 b3(已锁,R1 倾向 ACK)**——自控两端 + dev/test、不变量 14、无外部 b3 消费者;保留 b3 只会增静默降级路径 + 双套成功语义。**阶段边界**:518-A 不开写路径期间 `/run-state` 仍 b3 ephemeral 行为(consume 返 `durable=false`);**518-B 接通持久化即切 b4-only**,`/run-state` 拒 b3 请求;不为 b3 留独立模型 / 运行分支。
**状态码定**:`401`(token 无效/过期)、`403`(有效 token 但归属/scope 不符)、`409`(同 run_id/sequence 不同内容)、`410`(session 已结束/逻辑过期/已删/记录不存在,正确 scope 下)、`503`(存储不可用 / durable 写失败)、`500`(反序列化/不变量损坏);**409/410/503 不得回退 `durable=false`**(R1 P1-2)。
**错误模型(R1 P1-3)**:一个 run-state 专用 **`BridgeRunStateWriteErrorResponse`** 覆盖 409/410/503(+500),**不扩 diagnostic guard / auth-error 的 Literal**;状态码 × machine-code 矩阵测试。**bridge schema 14 → 15**(非 16)。
**全清单**:
- domain:`bridge_run_state.py` b4 请求 + 回执字面 + 新错误 domain。
- Pydantic:`bridge_run_state_schemas.py` b4 请求 + 回执 model + 错误 model。
- JSON schema:`bridge_run_state_request.schema.json`(b4)+ `bridge_run_state_receipt.schema.json`(重生)+ 新 `bridge_run_state_write_error.schema.json` → **14→15**。
- 导出脚本 `export_bridge_schemas.py` OUTPUTS + `Makefile verify-schema` git-diff 清单(+ 新)。
- **freeze/drift + round-trip + `test_*_schemas.py` 边界测试**(不止 freeze/drift/round-trip;R1)。
- core 不 import Pydantic(decision 21)。
- **OpenAPI**:`/run-state` 加 409/410/503/500 response(snapshot/freeze);`/diagnostic`·`/explanation` **零漂移**;既有 auth 401/403/503 schema **零漂移断言**;security 仍只挂 `/run-state`。
- **StoreError → handler/route 映射**(503/500)。
- 跨语言 golden:MATLAB 处理 b4 durable=true 回执 + 409 不盲重试 + 410 新建(不复用 run_id)。
- `docs/06` §15:增「持久化 + 留存(24h 硬,逻辑+物理)+ 同意覆盖存储 + b4 回执语义 + 状态机对外行为 + 409/410/503/500」;**改 516 那句「200=校验未保存」为 b4 的「durable=已保存」口径**。
- **不触解释 / LLM → 不动 docs/05 + `core/prompts/*.yaml`**(c)。

---

## §已解(v0.2 双审 + v0.3 实施规约)
1. **b4-only vs 留 b3 ephemeral**:**b4-only,退役 b3**(R1 倾向 ACK,理由:自控两端 + dev/test、不变量 14、无外部 b3 消费者;保留只增降级路径)。阶段边界已写进 §契约变更。
2. **establishment 挂点**(R6 钉死):**dev-auth route 级 additive orchestration**;DB 副作用不进 `BridgeAuthService` / `get_settings()`;establish 失败不返 token。已写进 §session 终态机。
3. **24h 物理删机制**(R6 钉死):**run-state 专用 sweep + 受控提前 cutoff**,不动全局 `CleanupWorker`;权威来源 `project_status_record.created_at + settings.upload_ttl_hours`;文案口径「最长不超过 24h,可能更早删除」。已写进 §24h 硬保证。

---

## v0.2 → v0.3 变更对照(收实施规约;无新设计点)
| v0.2 状态 | 来源 | v0.3 处理 |
|---|---|---|
| 24h 物理删机制留实现选 | R6 P0 / 待确认 #3 | 钉死 = run-state 专用 sweep + 受控提前 cutoff;不动全局 `CleanupWorker`;权威来源 = `project_status_record.created_at + settings.upload_ttl_hours`;文案「最长不超过 24h,可能更早删除」 |
| establishment 挂点写「additively 挂 issuer」 | R6 待确认 #2 | 改 route 级 additive;DB 副作用不进 `BridgeAuthService` / `get_settings()`;establish 失败不返 token(fail-closed) |
| b4-only 待 R1 确认 | R1 待确认 #1 | 锁 b4-only 退役 b3;阶段边界 518-A 仍 b3 ephemeral / 518-B 起 b4-only |
| 确认文案改造范围 | R6 实证 defaultConfirm 三端共用 | 文案做 run-state 专用或 context-aware;不误套 /diagnostic·/explanation |

---

## Stage 0(强制,decision 15;518-A 派单前 Codex 跑)
```bash
git fetch origin && git rev-parse origin/main      # 664d9ce 或后裔;不符停手报 PM
grep -n "TASK-518\|TASK-519" docs/03_TASK_INDEX.md; ls docs/tasks/ | grep -iE '51[89]'  # 确认空号
# 复核(§实测地基对最新 main;本轮新增几条仍属实?):
#  - session_id 仍未绑 chat_session(dev issuer 不查/不建)?chat_message 仍是 chat_session 子表?
#  - 确认文案仍仅「发送」?BEGIN IMMEDIATE + WAL/busy_timeout/FK 先例在?
#  - 517 dev issuer 路径可 additively 挂 establishment?project_expires_at 权威来源在哪?
git switch -c task/TASK-518A-run-state-substrate origin/main
```
**§实测地基不符 → 停手报 PM。**

---

## 验收门(按两 PR 分段;机制 + 确定性护栏,质量留 b3-3)

### 518-A(substrate;**不开放写路径**)
- [ ] **A-1 迁移 + 表**:`_migrate_v4_to_v5` + `CURRENT_SCHEMA_VERSION=5`(fresh DDL + registry 同补);两表 + 全约束建成。[单测]
- [ ] **A-1b 迁移测试(R1 P1-5)**:v4→v5 数据保留 / 新库直建 v5 / v5 重入 / future version fail-closed / 迁移中途 fault rollback / FK cascade 开启验证。[单测]
- [ ] **A-2 core 纯状态机 + 输入契约(R1 P1-1)**:输入 (session 终态, existing_run_by_run_id, existing_run_by_sequence, current)→{幂等/current/历史/冲突/410};纯函数、确定、无 IO;拆 `bridge_run_state_machine.py`。[单测]
- [ ] **A-3 服务端指纹**:脱敏后语义快照、覆盖全不可变语义、排除 request_id、`fingerprint_version` + canonical bytes 比对;客户端不算/不传;确定可复现。[单测]
- [ ] **A-4 Store + 串行化事务**:`BEGIN IMMEDIATE`;`UNIQUE(session_id,run_id)` + `UNIQUE(session_id,run_sequence)` + `UNIQUE(session_id,request_id)`(误复用);run 行永不 UPDATE;先插 run 再更 current;current 指针无漂移。[单测]
- [ ] **A-5 session 终态机 + establishment**:`active→ended/gone` 单调不可回;受信 establish(挂 issuer,幂等,不复活 ended/gone);`/run-state` 不懒建;`ended` 同事务清快照+current+派生 + 留最小终态行;session 过期取 project 生命周期、不取 token exp;代次不匹配=旧代次。[单测]
- [ ] **A-6 24h 硬保证(R1 P0-4)**:`project_expires_at` 到点逻辑失效(读/写 410);物理删 ≤24h 机制;清理失败 fail-closed;不改全局 CleanupWorker 影响其它 feature。[单测]
- [ ] **A-7 级联(rule 7)**:两表随 project 删级联清快照+派生+索引。[单测]
- [ ] **A-8 core 纯净(decision 21)**:core/domain 不 import Pydantic/JOSE/HTTP/store;不 import explanation 私货。[单测]
- [ ] **A-9 日志(decision 11)**:substrate 不记数值/标签/路径/源码/指纹/密钥;仅大小/类型/点数/状态/事件码。[单测]
- [ ] **A-10 写路径未开**:`/run-state` 仍 b3 `durable=false`;consume 行为不变;Store 未接 consume;517/b1/b2/b3-1 无回归。[单测+e2e]
- [ ] **A-11 decision 13(substrate 侧)**:A 不改对外契约(表/迁移内部);CI 绿。[CI]

### 518-B(wiring;两段合并后 c 方可派)
- [ ] **B-1 串行化写事务**:auth_context 派生 scope → 校验 session(缺失/失效=410)→ 幂等/冲突/sequence → 先插 run → 原子更 current → commit;生命周期写共用同一边界;**两连接 barrier 并发测试**只一个 current。[单测+e2e]
- [ ] **B-2 8 规则 enforcement(逐条钉死)**:不可变(run_id 唯一)/ 幂等·冲突(run_id 键,409)/ 顺序·历史(equal-sequence)/ 串行·单 current / 失效拒不复活(410)/ 级联清 + 24h 硬 / 隔离(403 vs 410 分界)。[单测]
- [ ] **B-3 b4 回执契约**:升 0.3-b4;回执回显 protocol_version + 固定三元组 persisted/durable_persisted/durable=true;幂等重放返回同一业务结果;b3 退役(或双版本独立模型,见 §待复审确认)。[单测+契约]
- [ ] **B-4 错误码 + 错误模型**:401/403/409/410/503/500;一个 `BridgeRunStateWriteErrorResponse`(14→15);状态码×machine-code 矩阵;错误隔离不污染 /diagnostic·/explanation;StoreError→503/500 不回退 durable=false。[单测]
- [ ] **B-5 同意(consent≠authorization)**:持久化以 per-run_id 的 `consent=true` 为门;每轮=每新 run_id;HTTP 重试不再弹框;410 后重确认;客户端文案覆盖存储/留存/删除(24h 硬闭合后写「≤24h」);`consent_notice_version`。[单测+本机]
- [ ] **B-6 decision 13 全清单**:b4 请求+回执+错误 schema 的 domain+Pydantic+JSON+导出+verify-schema+freeze/drift+round-trip+边界测试+core 不 import Pydantic+OpenAPI(新码+零漂移)+StoreError 映射+跨语言 golden+docs/06;14→15。[CI+本机]
- [ ] **B-7 红线无回归**:route-wrapper auth 门 / 守序 / 32KB / handler 从 request.state 取(无 request_body)/ 两老端点字节+语义不变 / consent flag 仍强制 / loopback 403 与 auth 403 区分。[单测+e2e]
- [ ] **B-8 MATLAB 客户端**:处理 b4 durable=true;409 不盲重试;410 提示新建(不复用 run_id);token 仍不进 payload;每轮(每 run_id)确认;不传原始文件。[本机+单测]
- [ ] **B-9 日志 + fail-closed(decision 11)**:写/错误路径不记内容;失败不回显 payload;无 `logger.exception`;**按 decision 11 判断阻塞调用、不为数量强凑 to_thread**(aiosqlite await 即可)。[单测]
- [ ] **B-10 CI + 不上 production**:全管道绿;feature 关 path 不存在;b1/b2/b3-1/517 无回归;不变量 14。[CI+本机]

---

## 不做(明确排除)
- ❌ LLM 解释 / 读历史 / 建议 / read·explain(c / TASK-519);本卡纯持久化 + 状态机。
- ❌ 跨天 / 延长留存(24h 已锁)。
- ❌ 把 run-state session 挂 chat_session(需另立绑定机制,future)。
- ❌ 生产 session 管理 / 登录 / SSO(seam);本卡 establishment 走 517 dev/test 路径。
- ❌ 改 `/diagnostic`·/explanation 语义;动守序 / 32KB / `MatlabEngineProvider`;回退 517 auth 门 / `request.state` 形态。
- ❌ 改全局 CleanupWorker 节奏影响其它 feature(24h 物理删用最小扰动机制)。
- ❌ 跨 MATLAB 版本;seam 前上 production / 作能力宣传(不变量 14)。

---

## 实施约束(全程)
- **两 PR 分段**:518-A → 518-B;c 须两段合并后派;各从最新 origin/main 切;`git diff --stat` 与 §文件清单一致。
- **decision 11**:日志/异常/对外不含数值/标签/路径/源码/token/claim/指纹;禁 `logger.exception`;**to_thread 按需(不强凑)**。
- **decision 12 v0.4**:本轮起**定向复审**(贴 §一审变更对照,各核自己上轮 P0/P1)。
- **decision 13 / 15 / 21**:见各段;decision 21 = 状态机/指纹纯 core,Store 在 adapters,不 import explanation 私货。
- **不变量 14**;**行尾 `20260602-08`**;**不重开已锁**(v0.3-a / b1 / b2 / b3-1 / 517-A / 517-B / 515 v0.4 / 516 标识语义 / 两拍决策)。
- **git/索引**:完工 Codex 推 TASK-518 行 🔍,PM merge 后翻 ✅(decision 07)。

---

## 文件清单(草案,Codex Stage-0 复核;按段)
**518-A**:`adapters/storage/schema.py`(`_migrate_v4_to_v5` + `CURRENT_SCHEMA_VERSION=5` + 两表 DDL + 约束);新 `adapters/storage/sqlite_bridge_run_state_store.py`(Store + 串行化事务 + establish/end/delete);新 `core/domain/bridge_run_state_machine.py`(纯状态机 + 指纹);`api/routes/matlab_bridge_auth.py`(**additively** 挂 establishment,不改 token/auth 契约);24h 逻辑失效 + 物理删机制(最小扰动);测试 = 迁移(含 A-1b)/ 状态机 / 指纹 / Store / 终态机+establishment / 24h / 级联 / core 纯净 / 日志 / 写路径未开。
**518-B**:`features/matlab_bridge/bridge_run_state_service.py`(consume 接写事务 + b4 回执);b4 请求 + 回执 + `BridgeRunStateWriteErrorResponse` 的 domain+Pydantic+JSON schema(14→15)+导出+verify-schema+freeze+边界测试;`api/routes/matlab_bridge.py`(错误响应映射 + StoreError,**不动守序/auth 门/两老端点**);OpenAPI 新码+freeze+零漂移;`clients/matlab_bridge/...`(b4 durable / 409 不盲重试 / 410 新建 / **改确认文案覆盖存储** + `consent_notice_version`);`docs/06` §15 增节 + 改 516「200=未保存」口径;e2e + 跨语言 golden。
**任务卡 / 索引**:本卡;完工 `docs/03_TASK_INDEX.md` 新增 TASK-518 行(🔲→🔍)。

---

## 一审变更对照(给定向复审:逐条对应,各核自己项)
| 一审项 | 源 | v0.2 处理 |
|---|---|---|
| 幂等标识用错(request_id) | R1 P0-1 | 业务幂等键改 **`(session_id, run_id)`**;`UNIQUE(session_id,run_id)`+`UNIQUE(session_id,run_sequence)`;request_id 仅查误复用;equal-sequence 同 run_id 幂等 / 异 run_id 409;rule 3 改写为「同 run_id+同规范化快照=幂等」。**已核 516 v0.4 锁定 request_id/run_id 语义。** |
| 缺可达结束态 + 懒建矛盾 | R1 P0-2 | 终态机 `active→ended/gone` 单调不可回;受信 establishment(挂 issuer,幂等,不复活);`/run-state` 不懒建、缺失/失效=410;ended 同事务清 + 留最小终态行(不另建 tombstone 表) |
| 协议/回执不变量未闭合 | R1 P0-3 | **升 `0.3-b4`**;回执回显版本 + 固定三元组 persisted/durable_persisted/durable=true;不放宽 durable=bool;旧字面不混用;b4-only(待确认) |
| 24h 与 hourly cleanup 推导不成立 | R1 P0-4 | §24h 硬保证:project_expires_at 到点逻辑失效(读/写 410)+ 物理 ≤24h(最小扰动)+ fail-closed;闭合前文案不写「≤24h」 |
| session 权威源不能停在二选一 | R1 P0-5 / Codex P0 | 独立权威 run-state session(**非 chat_session 扩展**,Codex 证未绑);FK→project + **自带终态/establish/end/delete**(「删即清」靠终态路径,不靠 FK 单独成立) |
| 状态机输入契约不全 | R1 P1-1 | 纯函数输入加 existing_run_by_run_id / by_sequence / current,Store 事务内提供 |
| 缺存储失败对外契约 | R1 P1-2 | 503(locked/full/unavailable)/ 500(损坏);不回退 durable=false |
| 错误模型 | R1 P1-3 | 一个 `BridgeRunStateWriteErrorResponse` 覆盖 409/410/503(+500);不扩 diagnostic/auth Literal;14→15;状态码×码矩阵 |
| session expiry 语义 | R1 P1-4 | 取权威 session/project 生命周期,不取 token exp;代次不匹配=旧代次→410;重启行为写明 |
| 迁移测试 | R1 P1-5 | A-1b:数据保留/新库直建/重入/future fail-closed/中途 rollback/FK cascade |
| 别硬凑 to_thread | R1 P1-6 / Codex | 按 decision 11 判断阻塞;aiosqlite await 即可,不为数量强凑 |
| 指纹粒度 | R1 #3 | 确认正确(脱敏后);收紧:覆盖全不可变语义、排除 request_id、fingerprint_version + canonical bytes;rule 3 文字同改 |
| 同意条件 | R1 #5 / Codex P1 | 每轮=每新 run_id;重试不弹框;410 重确认;文案覆盖类别/用途/持久化/留存/删除(现状仅「发送」,518-B 改);`consent_notice_version` |
| P2 字面/回执措辞/拆模块 | R1 P2 | status 精确字面+转移表(无省略号);「返回同一业务结果」;拆 `bridge_run_state_machine.py` |
| session_id 未绑 chat_session | Codex P0 | §实测地基记实证;FK→project 不挂 chat_session;挂 chat_session 须另立绑定机制(future) |
| chat_session 子表 = chat_message | Codex | §实测地基记;rule 7 级联现状确认 |
| 客户端文案仅「发送」 | Codex P1 | §同意语义 + B-5:518-B 改文案覆盖存储 ≤24h/删即清 |
| 迁移 / 串行化 / 红线可行性 | Codex | 实证 BEGIN IMMEDIATE + WAL/FK 先例、core 纯、14→15 口径、红线守得住、无新 to_thread——已纳设计 |

---

## 关联决策
decision 07 / 11 / **12 v0.4(双审+定向复审)** / **13(518-B 触发:b4 请求+回执+错误契约)** / 15 / **19(缓存记录状态契约,参照)** / **21(feature boundary)** / 25(评测双轴,b3-3 沿用)/ **`20260602-08`** / **不变量 14** / **TASK-515 v0.4**(8 规则+数据边界+留存) / **TASK-516 v0.4**(标识语义 request_id/run_id/sequence + 指纹归 b3-2 + DP-6) / **TASK-517**(架构站位:a 交付 context、权威 session 校验留 b、能力≠同意)。

---

## 审查与派发
- 当前 = **v0.3 定稿,过审,待派 518-A**:
  - **R1(GPT)**:**无条件 ACK**(2026-06-25 定向复审)——5 P0 + 6 P1 全闭合;倾向 b4-only 退役 b3,理由成立。无剩项。
  - **R6(Codex)**:**有条件 ACK**(同上)——`origin/main 664d9ce` 实测无 decision 15;v0.1 P0/P1 落对;两条实施规约(24h 物理删机制 / establishment 挂载方式)已在本 v0.3 §24h 硬保证 + §session 终态机 钉死。
- **实现门**:派 **518-A** 建;518-A 合并后派 **518-B**(decision 13 同步面实现期逐项);两段合并后方派 **c(TASK-519)**。
- **高风险(持久化 + 隐私)**:每段完工 PM 看 diff + 验收勾选;**架构师合并前亲自取证复核真 diff + 安全门**(只落脱敏有界快照 / 写事务串行化 + fail-closed / 24h 逻辑+物理删干净 / 隔离 / 日志不漏 / 红线无回归 / b4-only 切换干净),不只看绿勾。
- **brief**:§实测地基自包含(实测 `origin/main 664d9ce`,Codex R6 两轮);R1 无 repo,以本卡为准。
