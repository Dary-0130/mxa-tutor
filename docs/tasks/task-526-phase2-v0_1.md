# TASK-526 阶段二:LLM 结构化输出稳定性 · 据诊断修「少崩」

> **编号暂拟 526**(paper-to-model 线 · 卡二 · 决策 22 分段 501-999)。**Stage 0 必须 git fetch 后核 `526` 未被占**,被占则顺延。
> **两阶段卡**:**阶段一 · 诊断取数(已完成,本会话真机 A/B/AB 各 5 轮)**;**阶段二 · 据数据修(本卡)**。本卡承阶段一诊断 + R1 方案设计审(条件通过)。

## 状态
🔲 **v0.1**(架构师起草,并 **R1 方案审[条件通过·6 P0 采纳 + 7 P1 + 边界收口]** + 阶段一真机诊断数据)。待 **Stage 0 派单前可落核** → 派 Codex。

---

## 1. 上下文 / 起因

- 525-B 真机照出:同批两篇 PDF 上,LLM plan 生成随机失败(`paper_plan_generation_failed`),但同批其它 roll 能到 ready = **失败瞬时、roll-dependent**。525-B 只做「崩了不丢 + 能重试」安全网,**没治「为什么崩」**。
- 阶段一真机诊断(A/B/AB 各 5 轮 = 15 upload,真 DeepSeek,脱敏)量清了崩因(§3),**推翻几个直觉**:失败几乎全在 plan 生成(非 spec 抽取)、plan 大头是「格式对但内容不合规」(非 JSON 坏)、现有重试恰好只保 JSON 不保大头崩因、「库路径待确认」是字段空兜底(非诚实占位)。
- 阶段二 = **据数据修「少崩」**,核心 = 给「大头崩因」加有限重试 + 分类护栏。R1 方案审条件通过并收口边界(§2/§4)。
- **产品偏好(PM 拍)**:偏「稳」——宁可后台多试几次、每次上传多等,也尽量别让用户看到崩、少手动重试(与 roll-dependent 吻合:重试大概率能救)。

---

## 2. 是 / 不是(R1 边界收口)

**是**:
- **Plan 结构化输出重试**(§4.1):3 total attempts(initial+2),覆盖 JSON decode / schema validation / **retryable 语义缺陷**;**retry policy 落在 plan 生成层**、每次 attempt 完整走校验、失败产物丢弃。
- **Spec 抽取重试**(§4.2):2 total attempts(initial+1),只兜偶发 JSON/schema 输出缺陷,**不改 spec schema**。
- **Retry 分类器**(§4.3):retryable vs non-retryable reason code;硬预算 / unsupported domain / auth-config / store-invariant 等**快速失败别空转**。
- **硬上限**(§4.4):plan/spec total attempts + per-job LLM-call cap + per-job wall-clock cap,全 config 可调、卡给默认。
- **脱敏 telemetry**(§7/§9):stage/loc/error type/reason code/attempt/prompt length/outcome 分层记。
- **C 的字段级取证**(§6):记「plan 卡在哪条校验」的脱敏字段分布,**本卡零 schema 放宽**。

**不是 / defer**:
- ❌ **schema 放宽本体**(方案 C 的实际放宽)→ **另起后续卡**,须带失败字段分布 + 反例 + 契约同源清单。本卡只取证。
- ❌ **library_path 质量缺口**(D6)→ **只计数**,不改 schema、不把 null 升级为 plan fatal;另起卡治(改 prompt / 显式 `unknown_reason`)。
- ❌ **prompt 瘦身**(D3「越长越易崩」苗头,样本小)→ 记后继,先靠重试兜。
- ❌ **provider 层 retry**(本轮 timeout/server/rate-limit 命中 0)→ 不动;A/B 只处理「provider 已正常返文本、但文本没过结构化契约」。
- ❌ **状态机改动**(锁着)→ 用既有 `plan_failed_retryable` 终态;新 reason code 是机器码值、不强改状态机。
- ❌ 前端(锁着)。

---

## 3. 阶段一诊断数据基线(真机脱敏,自包含供 Stage 0 / 审计;只分类+数字)

**D1 崩点**:spec 抽取 1/20 失败(~5%);plan 生成 4/14 失败(~29%);终态 ready 10/15、plan_failed_retryable 4/15、failed_no_usable_spec 1/15。
**D2 失败类型**:fatal — spec JSON decode 1(`JSONDecodeError`)/ plan schema validation 3(`ValidationError`)/ plan semantic 1(`PaperPlanGenerationError`);nonfatal — plan JSON decode retry 命中 5(现有重试后恢复)/ build_steps schema fallback 3(`BuildStepsDtoValidationError`);timeout/server/rate-limit/provider 异常 0;role 不稳 0(77/77)。→ **plan 4 次 fatal 全 schema/语义、无一 JSON 坏。**
**D3 prompt 规模(字符)**:spec n=20 min14,843/med16,694/max18,546(失败那次=18,546);plan n=57 min5,549/med15,360/max36,058;plan 成功 job 内 mean14,956;**plan 失败 job 内 mean20,412/max36,058**。→ 失败侧更长,苗头未成定论。
**D4 roll**:A ready4/5;B ready3/5(+failed_no_usable_spec1);AB ready3/5。→ **roll-dependent 时崩时好 → 重试大概率能救**(方案核心依据)。
**D5 现状重试基线**:spec `extract_parsed_uncached` **无结构化重试(0)**;plan `_call_llm_json` = `for attempt in range(1,3)` **只重试 JSON decode(schema/语义不重试)**;provider 底层 retry(默认 3)**仅限 rate-limit/server/timeout**(本次 0 命中)。→ **现有重试只保格式、不保大头崩因。**
**D6 library_path**:ready plans 10(build_steps present 7/absent-null 3);present 中 `library_path` 待确认 34 处 = **字段空兜底 34 / LLM 诚实占位 0**。→ 生成质量缺口,非诚实行为。

---

## 4. 修复方案(R1 定稿边界)

### 4.1 Plan 结构化输出重试(P0-1 / P1-1)
- **3 total attempts**(initial + 2 retry),覆盖 JSON decode / schema validation / retryable 语义缺陷(现只重试 JSON、恰缺大头崩因)。
- **★ retry policy 落在 plan structured-output 层(plan_service / wrapper),不塞进 `_call_llm_json` 无类型 catch**——底层 helper 只管一次调用/解析(或重构成「带 validator callback 的结构化调用 helper」),**分类权与 budget 在 plan 层**(它知道当前 schema、语义 validator、stage、reason code)。
- **重试边界 = 一次完整闭环**:LLM 输出 → JSON parse → Pydantic schema validate → 语义校验;**每次 retry 产物重新完整走校验,失败产物直接丢弃,不得拿失败输出拼补最终 plan**。
- **多 leaf call 优先重试失败 leaf**(D3 暗示 plan 非单次调用):plan 内若有多个 LLM 子调用(composer / missing detector / build step planner 等),优先在**失败的 leaf output boundary** 重试;无法归因到单 leaf 再允许一次 whole-plan retry。**避免成本乘法。**

### 4.2 Spec 抽取重试(P1-1)
- **2 total attempts**(initial + 1 retry),只兜偶发 JSON/schema 输出缺陷(D1/D2:spec 失败低、唯一 fatal 是 JSON decode)。**不改 spec schema。**

### 4.3 Retry 分类器(reason code · P0-3)
`ValidationError` 多可 retry,但 **`PaperPlanGenerationError` 必须拆 reason code 分类、禁整体 retry**。三类:
- **可重试(LLM 随机输出缺陷,合 roll-dependent)**:JSON decode 失败;Pydantic 缺字段/类型不符/Literal 不符/extra 字段/数组越界;引用了不存在但本应从 spec/候选表选的 source id / parameter name / block ref;evidence 缺失 / citation target 非法 / locator 不可解析;prompt_id / mapping / build step ref 重复或 cardinality 不一致;`parameter_mapping`↔`build_steps` 内部引用不闭合;可修正的非法枚举 / 空数组 / null 误用。
- **不重试(输入/配置/领域/硬预算,重试同 prompt 没意义 → 快速失败别空转)**:unsupported domain / `general` 入口拒绝;无 usable spec / 文档解析失败 / 加密损坏文档 / 不在支持范围;prompt 超配置硬上限;**output token budget 不足(provider 返 length/truncated 或 completion 打满 max_tokens 致字段缺 → 归 token budget/prompt 设计,非普通随机 schema 失败)**;auth/config 缺失 / key 无效 / 模型不支持 JSON mode;DB/store/schema version/cache incomplete 等基础设施或状态不变量;代码契约错位(domain/wrapper 不同步致任何合法输出都过不了)。
- **重试后仍失败 → 保既有可重试终态(不降标放行)**:见 §4.6。

### 4.4 硬上限(P0-2,防叠乘 / 防拖死)
- **plan total attempts = 3;spec total attempts = 2;per-job extra LLM-call cap;per-job wall-clock cap。全 config 可调,卡给默认值。**
- **★ 必须写清**:这些次数 **含 JSON decode retry(含)**、**含不含 provider retry(不含,provider 层另管)**、**跨 plan 子调用是否共享 budget(是——全 plan 共享额外 retry budget,不让每个 leaf 各叠)**。
- provider 层 rate-limit/timeout/server retry 继续由 provider 处理,**不被 structured-output retry 再包一层重复放大**。
- wall-clock cap 秒数**对齐现有后台 job 超时/SLA**(Stage 0 核;无明确 SLA 则用 config 项、不硬编码)。

### 4.5 error-aware retry prompt(P1-2,不做 patch repair)
- 第二次 prompt 可加**极简失败提示**:「上一轮不符 schema」+ 字段路径(如 `parameter_mapping[*].source` / `build_steps[*].depends_on`)+ 原因类别(如 `invalid_literal` / `unresolved_reference` / `missing_evidence`)。
- **禁把上一轮 JSON 贴回让模型修补、禁只输出 diff**;要求重新输出完整 JSON,再走完整校验。(提示内容受 §7 脱敏约束:只带字段路径 + 泛化原因,不贴上一轮输出。)

### 4.6 retry 耗尽终态(P0-3 / P1-6)
- 输出缺陷类连续耗尽 → **终态仍是既有 `plan_failed_retryable` 语义**(系统已尽力自动 retry,用户/后台 rerun 仍可能救):**不升 permanent、不把最后一次「最接近」的输出降标放行**。
- **区分脱敏机器码**(不暴露异常 message):`plan_output_schema_retry_exhausted` / `plan_output_semantic_retry_exhausted` / `spec_json_retry_exhausted` / `non_retryable_unsupported_domain` / `non_retryable_prompt_budget_exceeded`。(Stage 0 核 `error_code` 是否 enum-frozen:是则新码走 registry + freeze + 契约同源。)

---

## 5. 无副作用边界(P0-6,retry 纯生成侧)
每个 attempt 可产内部 telemetry,但**不得**:写入 ready plan;更新前端可见 plan;把中间失败暴露成 job 终态;写入可被 GET 读到的 partial bundle;复用失败 attempt 的部分字段拼最终结果;因最后一次失败把 schema fallback 当正常 ready。**正确边界**:
```
job 进入 generating_plan → 内部 attempts 循环 → 某次完整校验通过 → 一次性 persist ready bundle / mark ready
或
job 进入 generating_plan → attempts 全失败 → mark plan_failed_retryable(既有失败态)
```
retry 内若触发 build_steps fallback → **标 degraded metric,不吞成「完全成功」**(本卡不修 D6,但不让新 retry 扩大「看似 ready、实际质量空洞」的口子)。

---

## 6. 方案 C = 字段级取证 only(P0-4,本轮零 schema 放宽)
- D2 的 3 次 schema fatal + 3 次 build_steps fallback **可能有某条规则过严把可用 plan 判死**,但**无字段级证据**。此时直接放宽 = 把「少崩」错成「坏数据进 ready」。
- **本轮只做脱敏取证**,记:component/stage、Pydantic `loc` 字段路径、error type、sanitized reason code、prompt length bucket、attempt number、final outcome。**不记原文/prompt/spec/plan/字段值/异常 message/traceback。**
- 攒够样本后 **另起后续卡** 评审某条 schema 是否过严(须带失败字段分布 + 反例 + 契约同源清单:domain/wrapper/freeze/JSON schema/06/prompt/前端类型/evaluator)。**本卡不落任何 schema 放宽。**

---

## 7. 脱敏红线(P0-5,decision 11 深化 · retry 扩大了数据暴露面,列 P0)
- **禁**:`str(exc)` / `repr(exc)` / traceback;Pydantic error 的 `input` / `ctx` 中可能含原值的部分;LLM raw response 落库/落日志;failed attempt 的 partial JSON 进 DB。
- **只允许记**:`loc`、`type`、内部 reason code、attempt number、prompt 字符数、token 数、stage、是否 retry 成功。
- retry prompt 的失败提示**只带字段路径 + 泛化原因**,不把上一轮输出贴回。
- SQL/清理/生成错误只 `type(exc).__name__`;禁 `logger.exception` / `exc_info`。

---

## 8. 继承红线(不回退,不顺手动)
- 状态机(锁,用既有 `plan_failed_retryable` 终态);spec schema 不改;plan schema 本轮不放宽;provider 层 retry 不动;523/524/525-A/525-B as-built 均不回退。
- **契约**:若加新 `error_code` / telemetry 字段 → 走 `export_paper_schemas.py` 白名单 + freeze + 06 + TS mirror(Stage 0 核 error_code 是否 frozen);**不动既有 DTO 语义**。
- **library_path 只计数**,不改 schema、不升 fatal。
- decision 08(字节)/ decision 11(脱敏,§7)。

---

## 9. Telemetry 分层(P1-3 / P1-4 / P1-5,供上线后归因 + 验收)
分开统计:provider retry count;JSON / schema / semantic retry count;final attempt number;final terminal state;extra LLM calls per job;generation wall-clock bucket;prompt chars / estimated tokens bucket;build_steps present / fallback / null 分布;`library_path` null count;LLM 明确无法确定 vs 字段空缺;schema/semantic final failure reason 分布。→ 否则上线后分不清「失败下降是 provider 改善、结构化 retry 生效、还是只是请求变慢」。

---

## 10. Stage-0 可落性 gate(Codex 派单前核 live,不符停手,禁兜底硬上 · decision 15)
1. `git fetch origin && git rev-parse origin/main` 报 HEAD;核 `526` 编号未被占;确认 main 含 525-B。
2. 确认本卡随代码入 `docs/tasks/`(PM 预放 untracked)。
3. **★ retry 落点核**:plan structured-output 层在哪(能放 classifier + shared budget)?`_call_llm_json` 现状(`range(1,3)`,只重试 JSON)?**plan 是否多 leaf call**(D3 暗示是)、能否在**失败 leaf boundary** 重试?spec `extract_parsed_uncached` 落点?贴 RAW 定性。
4. **★ 异常→reason code 映射核**:现 plan/spec 生成实际 raise 哪些异常(`JSONDecodeError` / `ValidationError` / `PaperPlanGenerationError` / `BuildStepsDtoValidationError`),能否干净映射到 §4.3 的 retryable / non-retryable 两类?**`PaperPlanGenerationError` 内部能否拆 reason**(区分随机缺陷 vs 确定性失败 vs token budget)?若拆不出干净分界 → 报架构师。
5. **★ error_code / 契约核**:`error_code` 是 free-form 还是 enum-frozen(§4.6 新 exhausted 码要不要走 registry + freeze)?status DTO 是否需加字段?
6. **★ 硬上限核**:有无 per-job wall-clock SLA / 后台 job 超时可对齐 cap(无则 config 项);确认 provider 层 retry 层次(§4.4 不重复放大)。
7. 任一不符 / 拆不出干净分类 → 停手诊断报架构师。

---

## 11. 真机硬门(P1-7,合并前必过 · 「少崩」+「质量没降」双验)
> 真 `DeepSeekTextProvider` 经 uvicorn HTTP + **那两篇易崩 PDF(样本集)**,从 repo 工作目录起让 `.env` 自动加载(**不回显 key**),临时库不污染本地。**沿用阶段一 A/B/AB 各 5 轮再跑一轮**(样本仍小,验方向 + 有无明显副作用)。
- **少崩**:`ready` 比例较基线(10/15)↑;`plan_failed_retryable` 比例;spec 失败比例;**plan retry rescue rate**(retry 救回多少)。
- **代价可控**:平均 / P95 **额外 LLM 调用数**;per-job wall-clock **不超 cap**。
- **★ 质量没降(核心守门,防「更多 ready 但更差」)**:build_steps present / fallback / null 分布;schema/semantic final failure reason 分布;**是否出现 evidence 空洞 / 非法引用 / 参数映射缺失被放行**(retry 后放进坏数据 = 硬失败,必须无)。
- **脱敏**:失败/取证日志扫 key label / 本机路径 / 原文 / `raw_text` / 字段值 / Pydantic input / 异常 message / traceback,**全无命中**。
- 分类正确性:retryable 类被自动重试、non-retryable 类快速失败不空转(可注入验证边界)。

---

## 12. 给 Codex 的提示(派单实现阶段)
- feature branch 从 `origin/main`(git fetch 后切,不 main 直推)。
- **可一个 PR 做完,或按你建议切**(自然缝:spec retry 较小可单独);**若切,每个 PR 独立真机验(§11 指标)**。核心(classifier + plan retry + caps + telemetry)紧耦合,建议同 PR。
- **卡随代码 PR**;**不碰 `03_TASK_INDEX.md`**(索引单独 PR,decision 07)。
- 新 `error_code` / telemetry 字段 → `make export-schema && make verify-schema` + freeze + `pnpm typecheck`,说明动了啥。
- `make check` 全管道(PATH 前置 `F:\python;F:\python\Scripts` 注脚同前)。
- **脱敏亲核**(贴本体不凭勾选);字节(08)/ 日志(11,§7)。
- 合并前架构师亲核真 diff + **真机验「少崩 + 质量没降」双指标**;RAW 贴对话、去行号、不带本机路径。

---

## 13. 开放点(Stage 0 定)
- retry 层具体落点 + budget 在哪持有(plan_service vs 新 wrapper)。
- `PaperPlanGenerationError` 拆 reason 的具体分界(拆不出干净分界 → 报架构师,可能需先补一轮取证)。
- `error_code` frozen 与否 → 新 exhausted 码走 registry+freeze 还是 free-form。
- per-job wall-clock cap 具体值(对齐现有 SLA 或 config 默认)。
- 多 leaf call 的失败-leaf 重试可行性(若 plan 生成不便按 leaf 归因 → 退 whole-plan retry + budget)。

---

**版本**:v0.1(架构师起草,并 R1 方案设计审[条件通过·6 P0 采纳 + 7 P1 + 边界收口]+ 阶段一真机诊断数据 + PM「稳」偏好)
**作者**:Claude(架构师)
**审批级别**:R1 方案审条件通过 → 待 Stage 0 派单前可落核 → 派 Codex
**前置**:main 含 525-B(异步上传 + 僵尸恢复);阶段一诊断已完成(本会话)
**后继**:schema 放宽本体(方案 C,须带字段证据 + 反例,另起卡)/ library_path 质量缺口(prompt / `unknown_reason`,另起卡)/ prompt 瘦身(D3,若 A/B 后仍长 prompt 集中失败)/ 前端批次(失败呈现 + 重试按钮)
