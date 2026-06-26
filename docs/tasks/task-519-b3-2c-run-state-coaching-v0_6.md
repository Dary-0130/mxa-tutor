# TASK-519:run-state 闭环陪调编排 + 解释(v0.3-b / b3-2c)

## 状态
✅ **v0.6 定稿,过审**(R6 ACK + 供 verbatim 码;R1 lease ABA + verbatim 码 round-4 闭合,429 码 = R1 条件 ACK「清除全文不带前缀的旧缩写后即 ACK」,本版已清除并经全文负向先行正则检查验空)。**待派 519-A**。
**实测地基自包含,实测自 `origin/main f5b6b93`(R6 四轮复核,无 decision 15)。** docs-only 收尾 PR `ba46ce7` 仅改 `03_TASK_INDEX.md` 叙述段,不动代码基线。
**审结进度**:P0 9→4→2→0(v0.5 后)。machine-code 已逐字填全(R6 Stage-0 供码,无遗留占位)。
**门已满足**:518-A/B + 收尾在 main。c = `a→b→c` 最后一张。

---

## v0.5 收口(round-4,锁)
1. **429 码单一字面(resolve R1 orig P0-7)**:全文统一 **`bridge_run_state_coaching_busy`**,**删除所有不带 `bridge_run_state_` 前缀的旧缩写写法**(原散见 A-12 / 围栏 / 验收 / 对照表)。`CoachingLLMError.error` = 闭合 Literal `{bridge_run_state_coaching_unavailable, bridge_run_state_coaching_timeout, bridge_run_state_coaching_failed, bridge_run_state_coaching_busy}`。
2. **verbatim 复用码填全(R6 Stage-0 供,无占位)**:auth(`BridgeRunStateAuthErrorResponse`):`401=bridge_auth_invalid_token` / `403=bridge_auth_forbidden`(reason `scope_mismatch`) / `503=bridge_auth_unavailable`;write(`BridgeRunStateWriteErrorResponse`):`410=bridge_run_state_session_unavailable` / `500=bridge_run_state_internal_error` / `503=bridge_run_state_store_unavailable`(`409=bridge_run_state_conflict` 现有写路径码,coaching 不用)。coaching **逐字沿用、不新增不改**。
3. **attempt-bound 槽释放(resolve R1 new P1-1 lease ABA)**:每次占槽绑**不可复用 `attempt_id`(lease generation)**;TTL 强制释放与 done-callback 均 **compare-and-release**(仅当槽仍属本 attempt 才释放,陈旧 callback **no-op**)→ 旧调用 TTL 后才 settle 不会误释放新 attempt 的槽,杜绝 B/C 并发;**强制释放后的孤儿调用设全局上限,超限请求亦 429 `bridge_run_state_coaching_busy`**(防连续挂死累积)。

---

## 编号与拆分
- **TASK-519** 父卡,b3-2c。交付目标 = 完整闭环陪调(单轮深度 + 跨轮连续),非缩水 MVP(PM 锁)。
- **519-A 单轮闭环**:解释同意门(bool+notice)+ `run_state:explain` scope + 独立 `/run-state/coaching` 端点 + 拒 `previous_run_count!=0` + LLM(私有 draft)+ 两阶段迟到围栏(attempt-bound 槽)+ 整形冻结 `0.3-c1` 契约 + 单轮 `CoachingRunStateReader` + 不落盘。端到端「一轮 run → 一份好解释」。
- **519-B 跨轮层**:引入 `CoachingCrossRoundReader`(DI)+ 即时构造目标轮 + 最多 4 前序(锚目标 run)+ 跨轮同意/确认 + 连续指导(可观测变化、不归因)+ 填 `cross_round_trend` + 回显 `context_run_ids` + 解除 `previous_run_count!=0` 拒绝,**不改 schema**。
- **b3-3 = c 后另起**;decision 25 双轴。

---

## 实测地基(实测自 `origin/main f5b6b93`,R6 四轮复核;R1 无 repo,以本卡为准)
- **回执 b4-only durable**:`0.3-b4`/`persisted`/`durable_persisted`/`durable=True`(`core/domain/bridge_run_state.py:65`)。
- **错误模型分层 + verbatim 码(R6,`api/routes/matlab_bridge.py`)**:`401=bridge_auth_invalid_token`(`:248`)/ `403=bridge_auth_forbidden`+`scope_mismatch`(`:160`)/ auth `503=bridge_auth_unavailable`(`:244`);`410=bridge_run_state_session_unavailable`(`:163`)/ `500=bridge_run_state_internal_error`(`:170/510`)/ store `503=bridge_run_state_store_unavailable`(`:177`)/ `409=bridge_run_state_conflict`(`:500`,coaching 不用);Literal 在 `bridge_run_state_schemas.py:58`。
- **LLM 先例(06 §14 b1,`bridge_explanation_service.py:127/190/280`)**:`TextProvider.chat(json_mode=True)` + `wait_for/to_thread`;JSON/Pydantic 校验 + 输出隐私 fail-closed;双同意;LLM 错误 503/504/502;DeepSeek provider 接受 `timeout` 传 SDK(`adapters/llm/deepseek.py:89/107`)。
- **capability 现状(R6)**:只 `run_state:write`(`core/domain/bridge_auth.py:8`);issuer allowlist 默认只 write(`bridge_auth_service.py:85`);测试拒 `run_state:read`;**revoke 要求 write**(`matlab_bridge_auth.py:112`);verifier 单 required capability 精确成员(`:188`)。
- **store 现状(R6)**:public `current(scope)` 只读 current(`sqlite_..._store.py:244/248`);裸 canonical bytes `:675`;`_require_active_session` `:526`;`_mark_session_gone` `:570`。
- **DB schema(R6)**:`CURRENT_SCHEMA_VERSION=5`(`schema.py:13`),registry 4→5(`:288`),无 Alembic。**本卡不落盘 → 不动。**
- **同意现状(R6)**:run-state 同意为 bool + notice 双字段(`bridge_run_state_schemas.py:335`)。
- **全局 `BridgeErrorResponse`** 仅三传输码(`bridge_diagnostic_schemas.py:25`)→ **429 不可入全局,须用 `CoachingLLMError`**。
- **24h / 全局 CleanupWorker 零改 / 红线 NO_DIFF**:同前(`git diff` 空)。
- **docs/05** v2.1 六类无 run-state 类;**prompts** 无 coaching;**MATLAB 客户端** `submitRunState` 只显示「运行状态已保存」(`MatlabBridgeApp.m:339`)。
- **可解释数据(06 §15.1)**:run_status/convergence_status/stop_reason(脱敏非可信)/solver/metrics(≤16)/series(≤4);跨轮=518 run 行(run_sequence)。

---

## 已锁(不重开)
24h、跟工程清、删即清、绝不长期备份、口径「最长不超过 24h,可能更早删除」;516 标识;517(能力≠同意 + write 不蕴含 read/explain + a/b/c);518 v0.3(b4 + 终态 410 + 24h 硬 + 持久化同意 per-run_id);副驾不报死值;两拍;不变量 14;行尾 `20260602-08`。

---

## 范围(必须做)

### 519-A 单轮闭环
- [ ] **A-1 解释同意门(bool+notice,独立+绑定)**:强制 `run_state_coaching_consent_confirmed=true` + `coaching_consent_notice_version=="run_state_coaching_v1"`;三门(write 能力/持久化同意/coaching 同意)分立。绑定语义见 §同意绑定。客户端 coaching 确认流程 + 冻结对象 `{notice_version, session_id, run_id, previous_run_count}` + 变更重确认。
- [ ] **A-2 精确 `run_state:explain` + IDOR**:Store 查询以完整 scope(user/project/session)+ run_id 为键,禁全局 by-run_id;能力矩阵测试。
- [ ] **A-3 capability/revoke 契约扩展(decision 13)**:枚举加 `run_state:explain`;issuer 可授;revoke 接受任一 run-state capability;dev-auth/schemas/tests 同步。
- [ ] **A-4 独立端点 + 拒跨轮**:`POST /api/v1/bridge/run-state/coaching` additively 挂 route-wrapper + verify explain scope;**`previous_run_count!=0 → 422 coaching_cross_round_not_enabled`**;不碰现有分支。
- [ ] **A-5 LLM + 私有 draft + 注入边界**:私有 `CoachingDraft`(`features/matlab_bridge/_run_state_coaching_draft.py`)+ 新 `run_state_coaching.yaml`;经 core `TextProvider`;送 provider 前二次脱敏;非可信字段入 typed data block(仅观测、非指令)+ 规范化 + validator 拒指令复制。
- [ ] **A-6 两阶段迟到围栏 + finalize + transport timeout + attempt-bound 槽**:见 §迟到围栏协议。
- [ ] **A-7 整形冻结 `0.3-c1`**:Request/Result/CoachingLLMError 的 domain(公开)+ Pydantic + JSON(15→18)+ 导出 + verify-schema 计数一次定 + freeze/drift + round-trip + 边界 + core 不 import Pydantic;**`CoachingDraft` feature-private 不导出、不进 core**。
- [ ] **A-8 闭集 evidence + reading↔direction(主+备)+ E 类判别**:服务端生成闭集 evidence(`evidence_id ^e[0-9]{1,3}$` 唯一);LLM 返 reading(`reading_id ^r[0-9]{1,3}$` 唯一)+ 主/备方向(`rationale_reading_id` 均必填、指 reading);校引用合法;`insufficient_evidence` → directions 空 + uncertainties≥1 + fallback_reason + confidence=low。
- [ ] **A-9 契约层禁死值**:`PrimaryDirection`/`AltDirection` 结构化(action+band)+ 全建议性文本 fail-closed 后置校验(命中具体数值/绝对目标 → 502)。
- [ ] **A-10 服务端定 summary + 注入 caveats + 全字符串扫描**:`run_summary` 服务端依 run_status/convergence **确定生成(LLM 不产)**;caveats Python 注入;隐私+承诺扫描覆盖所有字符串,命中 fail-closed 502。
- [ ] **A-11 单轮 reader ABC(decision 21)**:`core/interfaces` `CoachingRunStateReader`(**仅** scope+run_id 读 + 活跃围栏复检),返脱敏有界(非裸 bytes),adapter public 方法在 `BEGIN IMMEDIATE` 内;service 只依赖 ABC,不 import adapter/518 私有/explanation 私有。**window 读不在本 ABC**。
- [ ] **A-12 不落盘 + metadata + 幂等 + in-flight(attempt-bound)**:不落任何 LLM prompt/response/解释/context;metadata-only = 仅不可回连单会话聚合指标、不记标识、无留存;不提供结果幂等、迟到零副作用;每 session in-flight=1、超限 429 `bridge_run_state_coaching_busy`;**槽绑不可复用 `attempt_id`,TTL 与 done-callback 均 compare-and-release(陈旧 callback no-op),孤儿调用全局上限(超限亦 429)**。
- [ ] **A-13 上限钉死(硬值)**:数组/字符串上限 + `max_tokens=1024` + provider input ≤24KB + 响应 ≤32KB + `evidence_id ^e[0-9]{1,3}$` / `signal_ref ≤64` + `context_run_ids 1..5`,全为冻结值;边界测试。
- [ ] **A-14 日志(decision 11)**;**A-15 红线无回归 + 不上 production**;**A-16 OpenAPI 新 path 测试**:同前。
- [ ] **A-17 provider 留存分支(锁定=披露)**:coaching 同意 notice 带第三方留存披露(见 §同意 notice 冻结);若日后实证 DeepSeek 无留存再软化。

### 519-B 跨轮层
- [ ] **B-1 引入 `CoachingCrossRoundReader`(DI)+ 锚目标 run + 上界**:`previous_run_count∈0..4`;锚 `target run_id` → 只取 `run_sequence≤target_sequence`,目标 + 最多 `previous_run_count` 前序、升序;调用中 future run 不改冻结 context。
- [ ] **B-2 可观测变化连续指导(不归因)**;**B-3 跨轮 scope/consent**(窗变重确认);**B-4 回显 `context_run_ids`**;**B-5 不落盘 + 不复活 + 解除 `previous_run_count!=0` 拒绝**。

---

## 同意绑定(锁)
- **形态**:`run_state_coaching_consent_confirmed`(StrictBool)+ `coaching_consent_notice_version`(`Literal["run_state_coaching_v1"]`)双字段。
- **per-request 绑定**:确认 scope = `{notice_version, session_id, run_id, previous_run_count}`,均在请求内 → 用户确认的就是本请求的轮 + 前序数;任一变 → 重确认 → 新请求 consent 重置。`notice_version != 当前` → 422。
- **跨轮 context_run_ids**:服务端派生,不进预确认冻结;result `context_run_ids` 回显披露。
- **诚实边界**:服务端无法密码学区分真人确认 vs 本机硬编码 `true`(客户端侧同意固有限制,与 518 同源)。契约保护 = required-true + notice 匹配 + per-request 轮/前序数绑定。不过度声称。

## 同意 notice 冻结(`run_state_coaching_v1`,锁)
客户端 coaching 确认框固定文案覆盖:**数据类别**(脱敏降采样 run-state 摘要,不含原始 MAT/CSV)/ **用途**(送 LLM 生成陪调 + 跨轮指导)/ **第三方 + 留存(披露)**(由第三方 LLM 服务 **DeepSeek** 生成;其服务端留存**不由本机 24h 控制**;本机不持久化任何解释/上下文)/ **范围**(目标 run + 最多 `previous_run_count` 前序;实际所用轮在结果回显)。

---

## 迟到围栏协议(锁)
1. **阶段一(串行化读,复用 518 `BEGIN IMMEDIATE` + `_require_active_session`)**:校验完整 scope + project 未过期 + session active + 目标 run 存在(519-B 含前序锚);载入不可变脱敏有界 context + fence 标记。**519-A:`previous_run_count!=0 → 422` 在此前**。释放。
2. **发送前轻量活跃复检**:送 provider 前再核 session active;终态 → 410,不外发 context。
3. **阶段二**:构 prompt(非可信入 typed data block)→ 调 LLM,**双超时**:`asyncio.wait_for` deadline(504)**+ 传输层硬超时**(bound 线程;实现用 provider task + `shield`/done-callback 管槽,**不照抄** `wait_for(to_thread(...))`)。
4. **阶段三 finalize(统一顺序)**:先捕获 provider 结果/失败 → 最终串行化活跃复检 → **session 终态一律 410(不论成败)** / active 才暴露 `200`·`502`·`503`·`504`。不落盘 → 成功判据 = 此复检通过。
5. **超时**:走 finalize(终态 410 / 否则 504)。
6. **迟到结果 + attempt-bound 槽**:丢弃;in-flight 槽持到 provider attempt settle、且**最长 TTL 强制释放**;**槽绑不可复用 `attempt_id`,TTL/done-callback 均 compare-and-release——仅当槽仍属本 attempt 才释放,陈旧 callback no-op(旧调用 TTL 后才 settle 不误释放新 attempt 槽,杜绝 lease ABA / B-C 并发)**;**强制释放后孤儿调用全局上限**;over-limit → 429 `bridge_run_state_coaching_busy`;provider worker 禁写库/回调。
7. **测试**:`504 后 fake provider 释放零写入`;两种 end/finalize 顺序双连接 barrier;in-flight 超限 429;发送前复检 410;transport 超时;**lease ABA(旧调用 TTL 后 settle 不误释放新 attempt 槽,compare-and-release)+ 孤儿超全局上限 → 429**。

---

## 接口契约(`0.3-c1`,整形一次冻结于 519-A)

### Request `BridgeRunStateCoachingRequest`(`POST /api/v1/bridge/run-state/coaching`)
| 字段 | 类型 | 约束 |
|---|---|---|
| `protocol_version` | `Literal["0.3-c1"]` | 必填 |
| `request_id` | UUID | 每尝试一个 |
| `session_id` | UUID | scope 输入 |
| `run_id` | UUID | 目标轮 |
| `run_state_coaching_consent_confirmed` | StrictBool | 必须 true |
| `coaching_consent_notice_version` | `Literal["run_state_coaching_v1"]` | 必填,须 == 当前 |
| `previous_run_count` | StrictInt `0..4` | 目标轮之前历史轮数;总 context=1+此值≤5;0=仅本轮;**519-A:!=0 → 422 `coaching_cross_round_not_enabled`** |

`extra="forbid"`;敏感字段硬拒绝。

### 私有 `CoachingDraft`(`features/matlab_bridge/_run_state_coaching_draft.py`,**非 bridge schema、不进 core、不导出**)
LLM **只**输出:`outcome` / `signal_readings[]`(`reading_id` + `reading` + `is_inference=true` + `confidence` + `evidence_ids[]`)/ `primary_directions[]` / `cross_round_trend?` / `uncertainties[]` / `fallback_reason?`。服务端校验(schema + reading_id 唯一 + evidence_id∈闭集 + 主/备 rationale_reading_id∈reading_ids + 禁数值后置校验 + 隐私扫描)后组装公开 Result。

### Result `BridgeRunStateCoachingResult`(公开,客户端渲染)
| 字段 | 类型 | 约束 |
|---|---|---|
| `protocol_version` | `Literal["0.3-c1"]` | 固定 |
| `request_id` / `run_id` | echo | |
| `context_run_ids` | array[UUID] | **1..5**;519-A=`[run_id]` |
| `status` / `mode` | `Literal["completed"]` / `Literal["run_state_coaching"]` | 固定 |
| `outcome` | `Literal["coached","insufficient_evidence"]` | 判别键 |
| `run_summary` | string ≤200 | **服务端确定生成(LLM 不产)** |
| `signal_readings` | array[`SignalReading`] | coached 1-8;insufficient 可空 |
| `primary_directions` | array[`PrimaryDirection`] | coached 1-2;**insufficient 必须空** |
| `cross_round_trend` | string ≤300 / null | 519-B 填;519-A null |
| `uncertainties` | array[string ≤200] | ≤6;insufficient ≥1 |
| `fallback_reason` | `Literal["no_metrics_or_series","run_status_unknown","insufficient_signal","conflicting_signals"]` / null | insufficient 必填 |
| `overall_confidence` | `Literal["low","medium"]` | insufficient 恒 low |
| `evidence` | array[`EvidenceItem`] | 1-16(闭集,服务端展开) |
| `caveats` | array[string ≤400] | 1-3,Python 注入(仅基于脱敏降采样快照、未运行仿真/未验证修复) |

- `SignalReading`:`reading_id`(`^r[0-9]{1,3}$`,LLM 给、服务端校唯一)+ `reading`(≤300)+ `is_inference=Literal[true]` + `confidence∈{low,medium}` + `evidence_ids`(1-6,∈ `evidence.evidence_id`)。
- `PrimaryDirection`:`action∈{increase,decrease,hold,compare}` + `magnitude_band∈{slight,moderate,large}` + `rationale_reading_id`(**必填**,== 一条 reading_id)+ `alternatives`(array[`AltDirection`],0-2)。无 target/absolute value。
- `AltDirection`:`action` + `magnitude_band` + `rationale_reading_id`(**必填**,∈ reading_ids)。
- `EvidenceItem`:`evidence_id`(`^e[0-9]{1,3}$`,result 内全局唯一)+ `text`(脱敏 run-state 精确子串/span,≤200)+ `signal_ref`(≤64,指 metric/series/convergence)。

### 具体值(全冻结硬值)
数组:signal_readings 1-8 / primary_directions 1-2 / alternatives 0-2 / uncertainties 0-6 / caveats 1-3 / evidence 1-16 / evidence_ids/reading 1-6 / context_run_ids 1-5。字符串:run_summary≤200 / reading≤300 / cross_round_trend≤300 / uncertainty≤200 / caveat≤400 / evidence.text≤200 / signal_ref≤64。LLM:`max_tokens=1024`、provider input ≤24KB、最终响应 ≤32KB(均硬值)。

### 错误矩阵(逐码 + verbatim machine-code,无占位)
| 触发 | HTTP | 模型 | `error` 字面 |
|---|---|---|---|
| loopback 403 / 413 / 415 | 403/413/415 | `BridgeErrorResponse` | `matlab_bridge_forbidden` / `bridge_payload_too_large` / `bridge_unsupported_media_type` |
| consent 缺失·false / notice 不匹配 / 字段越界 | 422 | 全局 validation | `validation_error` |
| **519-A `previous_run_count!=0`** | 422 | 全局 validation | `coaching_cross_round_not_enabled` |
| 401 | 401 | `BridgeRunStateAuthErrorResponse` | `bridge_auth_invalid_token` |
| auth 403 | 403 | `BridgeRunStateAuthErrorResponse` | `bridge_auth_forbidden`(reason `scope_mismatch`) |
| auth 503 | 503 | `BridgeRunStateAuthErrorResponse` | `bridge_auth_unavailable` |
| session/run 不可达(含围栏命中) | 410 | `BridgeRunStateWriteErrorResponse` | `bridge_run_state_session_unavailable` |
| 内部不变量 | 500 | `BridgeRunStateWriteErrorResponse` | `bridge_run_state_internal_error` |
| store 不可用 | 503 | `BridgeRunStateWriteErrorResponse` | `bridge_run_state_store_unavailable` |
| provider 不可用 / 超时 / 输出失败 | 503/504/502 | `CoachingLLMError {error,message}` | `bridge_run_state_coaching_unavailable` / `bridge_run_state_coaching_timeout` / `bridge_run_state_coaching_failed` |
| in-flight 超限 / 孤儿超上限 | 429 | `CoachingLLMError` | `bridge_run_state_coaching_busy` |
| OpenAPI `503` | — | `oneOf(Auth, Write, CoachingLLMError)` | |

`CoachingLLMError.error` = 闭合 Literal `{bridge_run_state_coaching_unavailable, bridge_run_state_coaching_timeout, bridge_run_state_coaching_failed, bridge_run_state_coaching_busy}`。**429 不入全局 `BridgeErrorResponse`**;复用 auth/write 码逐字沿用不新增不改;`409`(`bridge_run_state_conflict`)不在本端点;`504` 仅 provider/deadline 超时,围栏命中只 410。

---

## 不做(明确排除)
b3-3;跨天/延长留存;**任何 LLM prompt/response/解释/context 落盘**;改 `/diagnostic`·`/explanation`;改 `/run-state` b4/字节/守序/auth 门/410/24h;回退 517/518 护栏;生产 session 管理;跨 MATLAB 版本;seam 前上 production;报死值;接收原始 MAT/CSV;引 ProjectGraph;归因用户调参;519-A 启用跨轮读取;429 入全局 `BridgeErrorResponse`;把不带 `bridge_run_state_` 前缀的旧缩写当 machine-code。

---

## 验收标准
- [ ] 端到端(519-A):一轮 run → `coached`,主+备 direction→reading→evidence 链可验证、evidence_id 唯一;无死值。
- [ ] `insufficient_evidence`:run_status=unknown 无 metrics/series → directions 空 + uncertainties≥1 + fallback_reason + confidence=low。
- [ ] consent:缺/false 或 notice 不匹配 → 422;`previous_run_count` 单一语义贯穿请求/B-1/notice;write token/持久化同意不能替代;能力矩阵。
- [ ] **519-A 拒跨轮**:`previous_run_count!=0 → 422`;A 的 reader 无 window 方法。
- [ ] machine-code:CoachingLLMError 闭合 4 码、**429=`bridge_run_state_coaching_busy`(全文单一字面、不在全局)**;复用 auth/write 码 verbatim(401/403/503/410/500/503 如 §错误矩阵);OpenAPI 503 oneOf 三模型。
- [ ] revoke:explain-only token 可撤。
- [ ] 迟到围栏:超时 504;调用中终态 410;发送前复检 410;`504 后零写入`;barrier;in-flight 429;transport 超时;**lease ABA compare-and-release(旧调用 TTL 后 settle 不误释新槽)+ 孤儿超上限 429**。
- [ ] 私有 draft:`CoachingDraft` 不在 core/domain、不导出;LLM 不产 summary/caveats/IDs;全字符串扫描。
- [ ] 不落盘:无 LLM/解释/context 入库;DB 仍 5;metadata 仅聚合无标识。
- [ ] provider 分支:披露 notice 已冻结(`run_state_coaching_v1` 含第三方留存披露)。
- [ ] 跨轮(519-B):锚目标 run、future 不改 context、回显、不归因、解除 422 门。
- [ ] decision 13 全清单 diff;decision 21 无私有 import + 经 ABC;decision 11;红线;不上 production;可走 decision 25 双轴。

---

## 变更对照 round-4(给局部确认)

### R1(GPT)
| 项 | v0.5 收口 |
|---|---|
| orig P0-7(部分)429 两套字面 | 收口 1 + 全文:统一 `bridge_run_state_coaching_busy`,删所有不带前缀的旧缩写;A-12 / §迟到围栏 6·7 / §验收 / §不做 / 本表均已改 |
| new P1-1 槽释放 lease ABA | 收口 3 + A-12 + §迟到围栏 6·7:`attempt_id` + compare-and-release(陈旧 callback no-op)+ 孤儿全局上限 429 |
| (R1 建议)verbatim 复用码须实际入卡 | 收口 2 + §错误矩阵:R6 供码已逐字填全(401=bridge_auth_invalid_token / 403=bridge_auth_forbidden / 503=bridge_auth_unavailable / 410=bridge_run_state_session_unavailable / 500=bridge_run_state_internal_error / store 503=bridge_run_state_store_unavailable),无占位 |

### R6(Codex)
全部 ACK,无遗留;供码已并入 §错误矩阵 + §实测地基。

---

## 实施约束(全程)
两 PR(519-A→519-B);decision 11;**decision 12 v0.4 定向复审**;decision 13 全清单(新契约 + capability/revoke 枚举 + 05/06 + prompt);decision 15;decision 21(ABC + 无私有 import + Draft 私有);不变量 14;行尾 `20260602-08`;git/索引 decision 07;任务卡预放 `docs/tasks/` 列 Stage 0 白名单。

---

## 文件清单(草案,Codex Stage-0 复核;**不含新 DB 表/迁移**)
**519-A**:
- `core/domain/bridge_run_state_coaching.py`(**仅公开** Request/Result/Evidence/Reading/Direction/CoachingLLMError;**不含 Draft**;不 import Pydantic/HTTP/store/explanation 私有)
- `features/matlab_bridge/_run_state_coaching_draft.py`(私有 `CoachingDraft`,不导出)
- `core/interfaces/coaching_run_state_reader.py`(`CoachingRunStateReader`,**仅单轮 read + fence**)
- `features/matlab_bridge/bridge_run_state_coaching_service.py`(读单轮 ABC + 三门 + 拒 `previous_run_count!=0` + 私有 draft + 二次脱敏 + 注入边界 + 两阶段围栏 + finalize + transport 超时 + **attempt-bound 槽(compare-and-release + 孤儿上限)** + 闭集 evidence + reading/direction 校验 + 后置校验 + 服务端 summary/Python caveats)
- `bridge_run_state_coaching_schemas.py`(Pydantic + JSON:Request/Result/CoachingLLMError;Draft 私有不导出)
- `schemas/bridge_run_state_coaching_request|result|error.schema.json`(**15→18**);`scripts/export_bridge_schemas.py`(计数一次定)
- `core/prompts/run_state_coaching.yaml`
- `adapters/storage/sqlite_bridge_run_state_store.py`(**实现单轮 `CoachingRunStateReader`**:scope+run_id 读 + 围栏复检,`BEGIN IMMEDIATE`,返脱敏有界;**不加表、不实现 window 读**)
- `api/routes/matlab_bridge.py`(挂端点 + verify explain scope + 拒 `previous_run_count!=0`)+ OpenAPI installer 新 path + 测试
- **capability/revoke**:`core/domain/bridge_auth.py` + `bridge_auth_schemas.py` + `bridge_auth_service.py` + `api/routes/matlab_bridge_auth.py`(revoke 不卡 write)+ tests
- `docs/05` 新增陪调类;`docs/06` §16
- 客户端 coaching post/render/consent(bool+notice)/scope token + `run_state_coaching_v1` 冻结文案(含第三方披露)+ 冻结确认对象
- 测试:freeze/边界/三门矩阵/IDOR/拒跨轮(+reader 无 window)/迟到围栏(barrier+发送前复检+429+transport+**lease ABA**)/不落盘/注入/后置校验禁死值/E 类判别/私有 draft 组装(不在 core)/evidence 链(主+备+唯一)/OpenAPI/红线/decision 21

**519-B**:`core/interfaces/coaching_cross_round_reader.py`(新 window ABC)+ adapter 实现 + service 接 DI;即时构造目标轮+前序、填 `cross_round_trend` 不归因、回显 `context_run_ids`、解除 `previous_run_count!=0` 拒绝;跨轮 scope/consent + 窗重确认;并发/终态/future-run-不改 context 测试。**不改 schema。**

**任务卡/索引**:本卡;完工 `docs/03_TASK_INDEX.md` 新增 TASK-519 行(🔲→🔍)。

---

## 关联决策
07 / 11 / **12 v0.4(定向复审)** / **13(新契约 + capability/revoke 枚举 + 05/06 + prompt)** / 15 / 19(参照)/ **21(ABC + 无私有 import + Draft 私有)** / **25(双轴,b3-3)** / `20260602-08` / 不变量 14 / 515 v0.4 / 516 v0.4 / **517** / **518 v0.3** / **05 v2.1** / **06(§14 b1 双同意 + LLM 503/504/502 先例;§15 数据形态)**。

---

## 审查与派发
- 当前 = **v0.6 定稿,过审**:R6 ACK + 供 verbatim 码;R1 round-4 三点(429 单一字面 / lease ABA / verbatim 码)闭合(429 为条件 ACK,本版已清除全文不带前缀旧缩写并正则验空)。无遗留阻断。
- **实现门**:**v0.6 = 定稿**,派 **519-A** → 合并后派 **519-B** → b3-3。
- **高风险(LLM + 隐私 + 新契约)**:每段完工 PM 看 diff + 验收勾选;**架构师合并前亲自取证 12 项 + LLM 围栏项**(迟到结果不写终态 / 三门 + consent notice / 不落盘真零内容 + metadata 无标识 / 私有 draft 不在 core 且 LLM 不控 summary·caveats·IDs / 解释私有不泄 core / 不报死值 + 后置校验 / capability scope + revoke / provider 披露 notice 冻结 / transport 超时 + attempt-bound 槽),逐条要 RAW。
- **brief**:§实测地基自包含(实测 `origin/main f5b6b93`)。
