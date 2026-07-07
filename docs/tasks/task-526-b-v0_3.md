# TASK-526-B:LLM 结构化输出稳定性 · 重试主体(v0.3 · 折入 Stage-0 live 核对)

> 承 TASK-526 阶段二。526 已拆:526-A(观测打底,已合入 main)/ **526-B(本卡)**。
> **v0.3 变更**:折入 Codex Stage-0 五项 live 核对(C1–C5)。关键:**① plan 是 4-leaf 并行 DAG,重试按 leaf**;**② 分类改 nature-based + 收窄到三个关键 leaf**(据实证);**③ finish_reason 需内部串接到失败对象**;**④ 僵尸 sweep 坐实 startup-only(v0.2 的 periodic contingency 解除)**;**⑤ 对外零变化坐实**。
> **本卡直接派实现,但实现须先过 §8 的两个 confirm-and-stop 前置**(并行 DAG per-leaf 重试可行性 + leaf 依赖结构);不符 → 停手报架构师(decision 15)。

## 状态

🔲 **v0.3**(据 526-A as-landed + 第二轮真机分布 + R1 526-B 分类审[条件通过·2 P0 + 5 P1 采纳] + **Stage-0 live 核对 C1–C5**)。待实现(§8 前置先核)。

---

## 1. 上下文 / 起因

- LLM 结构化输出对**同一篇论文**「时崩时好」(roll-dependent):第二轮真机同输入整体成功率 70.8%,单篇 A 8 轮 5 成/3 败——重试大概率能救。
- **现有重试只覆盖 JSON decode**(plan `_call_llm_json` = `range(1,3)`),漏掉大头 schema 失败;spec 无结构化重试;provider 层只管 rate-limit/timeout/server(命中 0)。
- **Stage-0 揭示 plan 内部是 4-leaf 并行 DAG**(§3),重试须按 leaf(§4.1b)。
- **526-A 已落地**:内部 `reason_code` + `LLMResponse.finish_reason`,对外零变化,只产标签不消费。**526-B = 据标签做自动重试主体**,吃 roll-dependent 输出缺陷,对确定性/预算/基础设施失败快速失败,守住质量不因重试下降。
- **产品偏好(PM 拍)**:偏「稳」。

---

## 2. 是 / 不是

**是**:spec + plan 关键 leaf 结构化输出重试(§4);nature-based leaf-scoped 分类器(§4.3);双 cap + 三层次数 + 统一 counter(§4.5);无副作用原子重试 + wall-clock cap 落态(§4.6);finish_reason 内部串接(§4.7);脱敏 telemetry + schema 子类取证(§4.8/§4.9);C 字段级取证(§6,零 schema 放宽)。

**不是 / defer**:
- ❌ **对外契约变化**:526-B 对外零变化(Stage-0 C5 坐实)。重试耗尽落既有 `plan_failed_retryable` / `failed_no_usable_spec` + 既有 `error_code`(`paper_plan_generation_failed` / `paper_spec_generation_failed`);`reason_code` / `finish_reason` / 新 telemetry 码全内部。无 export/freeze/TS diff。
- ❌ **build_steps leaf 重试**:有既有 fallback(§4.3),不动。
- ❌ **mscript_draft leaf 重试**:既有 non-blocking,不动。
- ❌ schema 放宽本体 / library_path 质量缺口(只计数)/ prompt 瘦身 / provider 层 retry / 状态机改动 / 前端 —— 均 defer,同 v0.2。

---

## 3. 真机分布 + Stage-0 结构发现(自包含供审计)

**第二轮真机(A/B/AB 各 8 = 24 轮,132 次 LLM 调用,脱敏)**:
- 终态:总 ready 17/24(70.8%)/ plan_failed_retryable 5/24 / failed_no_usable_spec 2/24。
- 7 次终端失败 reason_code:`schema_validation` 5 / `invalid_json` 1 / `equation_locator_invalid` 1。
- 7 次终端失败 leaf:`extracting_spec`(paper_spec)2 → failed_no_usable_spec;`generating_plan`(**plan_composer 3 / missing_detector 2**)5 → plan_failed_retryable;**`build_step_planner` 0 终端**(fallback 吸收)。
- 非终端:`plan_json_decode_retry:invalid_json` 12;`build_steps_fallback:{dto_invalid 4 / json_parse_failed 3 / parameter_value_leak 2 / connection_ref_not_visible 1}`。
- finish_reason:全部 stop 120/length 12;失败 job 内 stop 23/length 3;7 次终端失败那次调用 stop 6/length 1。
- token/max(8000):7 次终端失败仅 1 次(7999,即那次 length)贴近上限。
- 同输入成功率:A 62.5%/B 87.5%/AB 62.5%/总 70.8%(**单篇同输入方差=分类核心依据**)。
- 数据缝:未做 reason_code×finish_reason 交叉表(那 1 次 length 终端的 reason_code 未知)。

**Stage-0 live 结构发现**:
- **plan = 4-leaf 并行 DAG**:轮1 `gather(plan_compose, mscript_draft)`;轮2 `gather(missing_detect, build_steps, return_exceptions=True)`(轮2 依赖轮1 plan_composer_output,如 sentinel_mappings)。
- **live reason_code 全集远超初列**:spec 端 `invalid_json/schema_validation/equation_locator_invalid/parameter_source_invalid`;plan 端 `schema_validation/invalid_json/paper_param_name_duplicate/missing_prompt_cardinality_mismatch/subsystem_breakdown_length_invalid/equation_id_outside_whitelist/connection_ref_not_visible/parameter_value_leak/dto_invalid` 等。→ 促成 §4.3 改 nature-based。
- **finish_reason 未挂失败对象**(只局部日志)→ §4.7。
- **僵尸 job-state sweep = startup-only**(非 periodic)→ §4.6。
- **对外无新增需求**(§4.3 全落既有终态+既有 error_code)→ 对外零变化成立。
- **无整体 wall-clock SLA**(只 leaf/provider timeout + 24h TTL)→ cap 用新 config。

---

## 4. 526-B 分类与重试(据分布 + Stage-0 定死)

### 4.1 526-A 已落地、本卡依赖的标签(不回退)
- `PaperSpecGenerationError` / `PaperPlanGenerationError` 有内部 `reason_code`;`LLMResponse` 有 `finish_reason: str|None`(DeepSeek 透传)。均内部,不进对外 DTO/status/error。

### 4.1b Plan 是 4-leaf 并行 DAG,重试按 leaf(Stage-0 C1)
- live:plan = 两轮并行 gather(见 §3),轮2 依赖轮1。
- **重试按 leaf,尊重 DAG 依赖**:某关键 leaf 失败 → 用其**已成功依赖的固定输出**重投该 leaf,**保留其它已成功 leaf 产物**(不整盘重来):
  - `plan_compose` 失败(轮2 之前)→ 重投 plan_compose,再跑轮2;
  - `missing_detect` 失败(轮2)→ 重投 missing_detect(轮1 已固定、输入 sentinel_mappings 不变 → 重投输出与保留的 plan_compose 一致);
  - `build_steps` 失败 → **既有 fallback,不重投**。
- **一致性**:每个 leaf 只用其已固定依赖重投 → 无跨 leaf 不一致;质量门(§5.3)兜底。
- ★ **实现前须确认(§8 前置)**:精确 leaf 依赖结构 + 在 `asyncio.gather(..., return_exceptions=True)` 上按 leaf 重投可行性;**不便按 leaf 归因 → 退「whole-plan 重投 + 共享 budget」并报架构师权衡**。

### 4.2 决策规则(在范围内 leaf 失败点评估,持锁、CAS 前)
```
1) 失败是非 LLM 生成缺陷异常(auth/config、DB/store/schema-version/不变量、
   unsupported domain/general 拒绝、解析/加密损坏):
        → 不重试(原样传播 / 落既有终态)。
2) 否则这次失败调用 finish_reason == 'length':
        → 不给外层重投(§4.4;不动现有内层 JSON-decode 重试)。
3) 否则该 leaf 在重试范围内 且 reason_code 属「输出缺陷」 且 剩余 budget>0
   且 未触发早停(equation 复发 / 同 loc 3 次):
        → 重投该 leaf:丢弃失败产物,重新完整走 parse→schema→语义 校验。
4) 否则:
        → 落既有终态(plan_failed_retryable / failed_no_usable_spec)。既有 rerun 不受影响。
```

### 4.3 分类(nature-based · leaf-scoped · R1 Q1「统一 retry」落地)

**A. 重试范围 = 三个关键 leaf(其余保持现状)**
- **纳入**:spec 抽取 + plan 的 **plan_compose** + **missing_detect**(7 次终端失败全出自这三处)。
- **不纳入**:**build_steps**(既有 fallback:dto_invalid/json_parse_failed/parameter_value_leak/connection_ref_not_visible → degraded,plan 仍 ready,0 终端;526-B 不加重试、不动 fallback,**质量门监控其事件率**)/ **mscript_draft**(既有 non-blocking)/ **provider 层**(既有底层 retry,不双包)。

**B. 范围内按性质分类(不逐码枚举)**
- **RETRYABLE = 一切「输出缺陷」reason_code**(模型产出结构化输出畸形,本质 roll-dependent):`invalid_json`、`schema_validation`、及各语义/不变量/引用/基数码(`paper_param_name_duplicate`、`missing_prompt_cardinality_mismatch`、`subsystem_breakdown_length_invalid`、`parameter_source_invalid`、`connection_ref_not_visible`[若现于关键 leaf]、`equation_id_outside_whitelist`、`equation_locator_invalid` 等)。**原则:范围内 leaf 的输出缺陷失败一律可重投(受 cap),不逐码列白名单**(对未来新码亦稳)。
- **NON-RETRYABLE(快速失败,落既有终态)**:`finish_reason=='length'`(§4.4,覆盖 reason_code);上述非 LLM 生成缺陷异常;`failed_no_usable_spec` 作终态(spec 重投耗尽后落点)。
- **SPECIAL(重试但带早停/预检)**:
  - **equation 族**(`equation_locator_invalid` / `equation_id_outside_whitelist`):可重试 + **同 leaf+同 spec+同 namespace 连续复发早停**(telemetry `equation_locator_invalid_repeated`)+ **plan 入口 preflight**(PaperSpec 已在,廉价扫 `(document_id, equation_id)` 重复/命名空间冲突 → 直接 non-retryable、不进 LLM;防多文档身份根因被重试掩盖)。**spec 抽取阶段无 preflight(只能 LLM 后校验)→ 仅复发早停。**
  - **contract-mismatch-suspected**:任一 reason_code **同 `loc` 连续 3 次全败** → 疑契约错位,早停落既有终态(telemetry `schema_contract_mismatch_suspected`)。

### 4.4 `finish_reason == 'length'` 边界(措辞收窄)
- **本卡新增 structured-output retry 路径中**,`finish_reason=='length'` 视为 budget/prompt 设计类,**不消耗外层 retry budget**;补救=prompt 瘦身(parked)。
- **不动现有内层 JSON-decode 重试**(不看 finish_reason,今天就救回一部分截断-JSON 失败)。length→不重试 **只作用于外层新增重试**。
- 不写「length 永远确定性预算溢出」(无 reason_code×finish_reason 交叉表)。

### 4.5 三层次数 + 统一 counter(Stage-0 C1)
- **内层(既有,不变)**:`_call_llm_json` 每次调用最多 2 次 JSON-decode 重投。
- **外层(新,按 leaf)**:关键 leaf 失败(内层 JSON 重投耗尽 raise `invalid_json`,或解析后 schema/语义校验失败)且 retryable 且 budget 剩 → 外层重投该 leaf。**外层 budget:plan 额外 ≤2(跨 plan_compose/missing_detect 共享)、spec 额外 ≤1。**依据:plan 单次成功 ~75–80% → 3 次残余 ~0.8–1.6%;spec ~92–95% → 2 次残余 ~0.25–0.64%。
- **job cap(新)**:全 job 所有内层+外层+各 leaf LLM 调用总数 ≤ **hard 12 / warning 10**(不含 provider 底层 retry;含所有 JSON-decode + schema + semantic);超 warning telemetry `structured_retry_high_call_count`;真机 P95 ≤9 可收紧 hard 到 10。
- ★ **统一 counter 贯穿 `_call_llm_json` + plan/spec wrapper**:Stage-0 确认现无、须加私有 retry context 传入 helper(否则 job cap 含 JSON-decode 失真)。
- **length 与层次**:内层不看 finish_reason(不变);**外层重投前检 finish_reason,==length 不加外层重投**。
- **wall-clock cap = 新 config 项**(Stage-0 确认无既有整体 SLA)。

### 4.6 无副作用原子重试 + wall-clock cap 落态(P0-1;Stage-0 C4 坐实)
- 重试全在 `plan_generating` / `extracting_spec` 窗口内、持锁、CAS 转 `persisting_plan` 前;attempt 间不落半产物;失败产物丢弃。build_steps fallback 触发标 degraded、不吞成成功。
- 状态机不变(v8,无新列);**in-job 重试次数瞬时(内存),不碰持久 `attempt_count`**(rerun 级)。
- **★ Stage-0 坐实:僵尸 job-state sweep = startup-only(非 periodic)**(RAW:`sweep_stale_paper_upload_jobs` 单次调用非循环;stale `WHERE job_state IN (queued,running,plan_generating)`;TTL staging worker 独立且 state-aware,`PAPER_STAGING_CLEANUP_STATES` 排除 active)。→ **runtime 不扫长重试 live job;无需 heartbeat/阈值**(v0.2 「若 periodic 停手」contingency **已解除**)。
- **wall-clock cap 命中落态(活进程内显式收场,不抛出去等 sweep)**:plan 阶段 → `plan_failed_retryable`(telemetry `structured_retry_wall_clock_cap_exceeded`);spec 阶段无 usable spec → `failed_no_usable_spec`,已有 spec 在 plan 阶段 → `plan_failed_retryable`;**必须释放 per-paper lock**(Stage-0 确认锁内落终态后退 context 即释放)。
- 验收加**假慢 LLM 测试**:重试期 live job 不被 sweep 抢占;cap 落既有终态;释放锁;无 partial bundle。

### 4.7 finish_reason 内部串接(§4.4 依赖;Stage-0 C3)
- Stage-0:`LLMResponse.finish_reason`(526-A)现只在 plan/spec 失败**局部可见 + 写日志**,**未挂**到 `PaperSpecGenerationError` / `PaperPlanGenerationError` → 外层 classifier 读不到。
- 526-B 须:leaf 失败 raise 时**把该次 `LLMResponse.finish_reason` 挂到内部失败对象**(内部字段),或让 structured helper 返回/抛带元数据私有结果,供外层 classifier 读(§4.4)。**内部字段,不进对外契约;finish_reason 是枚举,脱敏安全。** 现有内层 JSON-decode 重试不动。

### 4.8 脱敏(decision 11,承 526-A)
- 重试决策**只读** `reason_code`(枚举)+ `finish_reason`(枚举)。**绝不** log/telemeter:message 文本、字段值、Pydantic input/ctx、文件名、LLM raw response、partial JSON。**禁** `str(exc)`/`repr(exc)`/`exc_info`/traceback/`logger.exception`。
- 重试 telemetry(attempt/reason_code/finish_reason/rescue/exhausted/wall-clock/high-call/子类码)**只机器枚举**。error-aware prompt 只带字段路径 + 泛化原因,**禁贴上一轮输出**。

### 4.9 telemetry 分层 + schema 子类(P1-2/P1-5)
- **provider / structured retry 指标分层**:验收报告分开显示 provider retry count、structured(JSON/schema/semantic)retry count、final attempt、terminal state、extra LLM calls/job、wall-clock/prompt/token bucket、build_steps present/fallback/null 分布、`library_path` null count、equation `rescue/repeated/exhausted` 三指标(P1-3)。
- **schema_validation 子类(只 telemetry,不分裂行为)**:`schema_shape_invalid` / `schema_reference_invalid` / `schema_cardinality_invalid` / `schema_evidence_invalid` / `schema_contract_mismatch_suspected`(同 loc 连续 3 次全败)。供后续 schema 放宽卡取证。

### 4.10 error-aware retry prompt(P1-4,不做 patch repair)
- 第二次可加极简失败提示:「上一轮不符 schema」+ 字段路径 + 原因类别;**禁贴回上一轮 JSON、禁只输出 diff**,要求重出完整 JSON 再走完整校验。**应作测试断言**。

---

## 5. 真机硬门(合并前必过 · 「少崩」+「质量没降」双验;A/B/AB 各 8 轮)

### 5.1 少崩(P1-1,可执行数字)
- **ready ≥ 22/24 → 通过**;**= 21/24 → 条件通过**(须解释 residual 且 residual 不得仍大量 `schema_validation`);**≤ 20/24 或 residual 仍大量 `schema_validation` → 不通过**。
- 报 plan/spec 重试 rescue rate;残余失败应是 NON-RETRYABLE 类。

### 5.2 代价可控
- 额外 LLM 调用数(mean/P95)+ per-job wall-clock,**均在双 cap 内**(§4.5)。

### 5.3 ★ 质量没降(P0-2,核心守门,两层;topology-agnostic,检最终装配 plan)
- **第一层(趋势)**:质量信号事件率(`parameter_value_leak` / `connection_ref_not_visible` / `dto_invalid` / evidence 空洞 / dangling equation-locator / build_steps fallback|null|degraded 分布)相对基线**不得上升**。
- **第二层(确定性全检)**:**所有 retry-rescued ready**(telemetry 标「有 leaf 被外层重投」)必须过与首次成功相同的 schema+语义 validator,并额外跑 **rescued-plan invariant suite**:每条 `document_extracted` evidence 有合法 locator/excerpt(非 plan 文本伪装摘录);`user_supplied`↔`document_extracted` 双源不混;`parameter_mapping ↔ build_steps` 引用闭合(无 dangling block/parameter/equation ref);`remaining_missing_prompts` 与 sentinel/binding 一致;equation 族 rescued case 最终 locator 解析到当前 spec 真实 equation/section/figure 命名空间。
- **任一 rescued plan 命中红线 → 合并失败。**(结构 invariant 全检;rescued 数太多时可对「展示质量」抽样人工看,结构必须全检。)

### 5.4 脱敏零命中
- 扫 key label / 本机路径 / 原文 / `raw_text` / 字段值 / Pydantic input / 异常 message / traceback,**全无**。

### 5.5 as-built 非回归
- 525-A/B 立命断言(plan 崩后 spec 保住 + rerun 能救;同步 `/upload-document` 200 body 不变;单一 handle-free pipeline;僵尸三段 startup sweep)**全过**。

---

## 6. 方案 C = 字段级取证 only(承 v0.2,本轮零 schema 放宽)
- 只脱敏取证(component/stage、`loc`、error type、sanitized reason code[含 §4.9 子类]、prompt length bucket、attempt、outcome),**不记原文/字段值/异常 message/traceback**。攒够另起 schema 放宽卡。**本卡不落任何 schema 放宽。**

---

## 7. 继承红线(不回退,不顺手动)
- **526-A as-built**(reason_code 内部 + finish_reason 透传 + 对外零变化)不回退;标签/新 telemetry 码不进对外契约。
- 状态机(锁,既有终态);spec schema 不改;plan schema 不放宽;**build_steps fallback / mscript non-blocking / provider 层 retry 均不动**;523/524/525-A/525-B as-built 不回退。**禁两套 pipeline。**
- **对外零变化**:不动既有 DTO 语义、不加 `error_code` 值/`job_state`/DTO 字段。将来必须加对外字段仅两种场景(LLM 调用计入用户额度 / 前端展示「已自动尝试 N 次」)→ 走 export+freeze+TS;**本卡不加**。
- library_path 只计数;decision 08(字节)/ decision 11(脱敏,§4.8)。

---

## 8. 实现前置(两个 confirm-and-stop)+ 派单说明

**★ 实现须先核这两项,不符停手报架构师(decision 15),别硬上**:
1. **并行 DAG per-leaf 重试可行性**:精确 leaf 依赖结构(谁依赖谁,尤其 missing_detect 是否只依赖轮1 plan_composer_output/sentinel_mappings);能否在 `asyncio.gather(..., return_exceptions=True)` 上按 leaf 重投(重投失败 leaf、保留已成功 leaf)。**不便按 leaf 归因 → 退「whole-plan 重投 + 共享 budget」并报架构师权衡**(仍守 §4.5 budget/cap)。
2. **equation 族 leaf-attribution + preflight**:`equation_locator_invalid` / `equation_id_outside_whitelist` 失败对象能否带/补 leaf+spec+locator namespace 上下文以支持复发早停;plan 入口 `(document_id, equation_id)` 重复/命名空间 preflight 是否廉价可行(不可行则退仅复发早停)。

**核完两项无阻即实现**(其余 Stage-0 已坐实:finish_reason 串接[§4.7 补法清楚]、统一 counter[须加]、wall-clock 落态[§4.6]、对外零变化[§4.3 全落既有终态]、僵尸 startup-only)。

**派单**:
- feature branch 从 `origin/main`(git fetch 后切)。核心(classifier + spec/plan-leaf retry + 双 cap + 统一 counter + finish_reason 串接 + wall-clock 落态 + telemetry)紧耦合,建议同 PR;spec retry 较小若切须各 PR 独立真机验(§5)。
- **卡随代码 PR**;**不碰 `03_TASK_INDEX.md`**(索引单独 closeout PR,decision 07;合并后主动提醒 PM 补索引,记「进行中」)。
- 新 telemetry 码全内部 → **无** export-schema/freeze/TS(若确需碰对外 → 停手报架构师);跑 `make check` 全管道。
- **脱敏亲核**(贴本体不凭勾选);字节(08)/日志(11,§4.8)。
- 合并前架构师亲核真 diff + **真机双验(少崩 + 质量没降)+ 假慢 LLM sweep 抢占测试**(§4.6/§5)。**真机不用 PM 给 key**(`.env` 有、`AppSettings` 从 repo 目录自动加载)——从 repo 目录起 uvicorn/harness,不回显 key,临时库不污染本地。RAW 贴对话、去行号、不带本机路径。

---

**版本**:v0.3(526-A as-landed + 第二轮真机分布 + R1[条件通过·2 P0+5 P1] + Stage-0 C1–C5 live 核对)
**作者**:Claude(架构师)
**审批级别**:R1 526-B 分类审条件通过(2 P0 折入)+ Stage-0 可落核完成(C4/C5 坐实,C1/C2/C3 架构师据 live 重构)→ 待实现(§8 两前置先核)
**前置**:main 含 525-B + 526-A
**后继**:schema 放宽本体 / library_path 质量缺口 / prompt 瘦身 / 前端批次(均另起卡)
