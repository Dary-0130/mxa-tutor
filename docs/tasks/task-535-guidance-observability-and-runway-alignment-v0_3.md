# TASK-535:建模指导层失败可观测量具 + 评测跑道口径对齐(v0.3)

> **性质**:量具卡 / 诊断卡。**只修测量通道,不修任何失败。**
> **v0.3 变更**:折入 **R1 设计审(条件通过,5 P0 / 6 P1 / 4 P2,采纳 13 条)** + **Codex Stage-0 只读核查(8 项 live 坐实,打回 R1 两条)** + 架构师新增的**折算选靶规则**。
> **前置**:main 含 TASK-534 + 依赖审计量具 + 依赖措辞 v0.3(均已合入)
> **后继**:对齐后 48 轮观测跑 → 据数选靶 → 修复卡。**本卡不预设打哪层。**
>
> ★ **编号说明(必读,防撞号)**:TASK-535 为**暂定**,尚未核实。派单第一步:`git fetch` 后查 `docs/tasks/`,确认 535 未被占用(上一会话的依赖量具卡 / 措辞卡可能已占号,交接材料未记编号)。被占用则**顺延至下一个空号**,改文件名与卡内编号,回执告知。**不得复用已占用编号。**

## 状态

🔲 v0.3 待实现(R1 条件通过 + Codex Stage-0 完成;**实施前须过 §10 三项 confirm-and-stop**)

---

## 1. 上下文:为什么必须先修尺子,不能先开枪

上一会话据「48 轮新指令臂」的失败分布定下一枪目标:**生成指导 11/20、写步骤剩余 8/20、出计划 1/20** → 结论「打生成指导层」。

**这个结论的证据基础已经塌了。四条,全部已坐实:**

### 1.1 ★ 评测跑道与生产不同构(双重证据)

- **代码**:生产经 `PaperPlanService` 把 plan 的 `max_tokens=8000` 传给 guidance;评测子类 `RecordingBuildGuidanceGenerator(text_provider)` **不继承 plan service 的参数**,落回默认 **`max_tokens=6000`、`timeout=90`**。
- **产物**:历史评测产物里 guidance 调用**白纸黑字写着 `max_tokens=6000`**。

★ **不同构不是一个孤例:一次核查就照出两项(token 上限 + 超时)。** 这正是本卡要在 provider 边界做逐项比对、而不是只看一个字段的原因。

### 1.2 ★ 预算天花板已被同批数据印证

TASK-534 as-built 记录:**build_steps 的 output_tokens P95 = 7058、max = 7999(8000 上限),已经贴着天花板。**
指导层的输出规模不会比它小多少,而评测跑道给指导层的是 **6000**。
**那 5 次「写爆」,极可能大半是预算掐出来的,不是模型写不好。**

### 1.3 ★「写爆」是我们起的名字,代码从未验证过

代码里只有 `llm_unparseable`。**「被截断写不完」与「provider 报正常停止但解析失败」落到同一个码。** 能区分二者的 `finish_reason` 在 provider 元数据里有,但没串到指导层失败对象。

### 1.4 ★ 指标同词异义,已在仓库里发生

TASK-534 as-built 同时记了**两个数**:

| | 改前 | 改后 |
|---|---|---|
| build_steps 结构化成功 | 10/24 = 41.7% | 10/24 = **41.7%** |
| 严格成品(build_steps 成功且 guidance generated) | 10/24 = 41.7% | 9/24 = **37.5%** |

**决策 27 引的是宽的那个,并称之为「成品率」。同一个词,仓库里两个数。**
且同批数据里 **guidance 有 14/24 轮根本没触达** —— **指导层的失败率一直是在一个从未被报出来的小机会基数上算的。**

按**决策 15**(先诊断后修):**本卡只装量具、只摆正尺子,不修任何失败。**

---

## 2. Codex Stage-0 实测(2026-07-12,只读;本卡全部设计建立在这 8 条上)

| # | 结论 |
|---|---|
| **S0-1** | **grounding 白名单未命中 = detail 级降级路径,不是必然终态失败。** 条件:`document_extracted` draft 的 handle 解不出,或 high-risk token 不在 truth index 里。降级后:正文**不保留模型原话,换成后端模板**;`basis=user_confirmation_required`;`confirmation_reason_code=document_evidence_unverified`;`evidence=[]`。★ 528-C **放行**这条降级 detail;**只有当所有 `document_extracted` detail 全丢光**,整份才标 `generation_failed`(不是 `no_document_basis`)。 |
| **S0-2** | `build_steps_unavailable` 时 **guidance 根本没调模型**(`plan.build_steps is None` 直接返回 `generation_failed`)。★ 而 `evidence_card_unavailable` **不是**「没调模型」——它在 evidence pool 构造后、**LLM attempts 之后**由 terminal reason 判出。 |
| **S0-3** | eval summary 现在是**混合记账**:`guidance_reached` 按 `plan.build_steps` 是否存在算,`guidance_failure_reason` 按报错方报的 reason 算。**可以不改生产判定**,新增落 `first_blocking_stage` / `terminal_observed_stage` / `guidance_invoked`;★ **`guidance_invoked` 可直接从 `RecordingTextProvider.calls` 里有没有 `build_guidance_generator` 这个 role 的调用算出来。** |
| **S0-4** | ★ **`critical_steps_fully_covered` 代码里根本没有这个字段**(R1 说 528-B 已有,**错**)。可得的是:`critical_step_count`(从 `_critical_steps(build_steps)`)、`blocking_gap_count`(从 `build_guidance.assessment.blocking_gap_ids`)。`all_document_details_lost` 只在 validator telemetry 里有机器码,summary 没留住 → 需加**评测落档 plumbing,不需改生产判定**。最终 detail 总数 / document detail 数 / 未核实 detail 数:**`build_guidance` 存在时可算;为 null 时算不出来**。guidance 每轮 provider 调用次数可从 `RecordingTextProvider.calls` 按 role 计数。 |
| **S0-5** | resolver 事件码:**不改判定与控制流**,可以给「handle 未命中」和「grounding 白名单未命中」打**可区分事件码**。★ 但「**handle 歧义**」**结构上不可能发生**(handle 是后端生成的 `GEV-###`,`by_handle` 是 dict,当前没有真实歧义分支)。**不造这个字段。** |
| **S0-6** | provider 边界:**DeepSeek adapter 不再 clamp 显式 `max_tokens`**(测试覆盖 16000 直传)。`temperature` / `top_p` / `seed` **当前不发送**。`response_format` 由 `json_mode=True` 在 adapter 内转成 `{"type":"json_object"}`。 |
| **S0-7** | `system_fingerprint`:**每次 call 都能进** `LLMResponse.system_fingerprint`;评测 wrapper 每次 call 都记录;summary **已有**每行去重集合 + 次数,以及整批 run 去重集合 + 次数。供应商不返回则记 note。 |
| **S0-8** | 墙钟:历史默认 8×1 为 **24.72 / 28.90 / 29.28 分钟**;最新 `paired-build-steps-full` 24 行 = 102.17 分钟(折算 8×1 约 34.1 分钟)。**8 篇 × 6 轮串行:2.5–3.4 小时。** smoke 外层现串行,内部每篇已有若干 LLM leaf 并发。★ `GUIDANCE_WALL_CLOCK_SECONDS=180` 是**每次 guidance 的本地 cap**;并发不会变成全局 cap,但 **provider 排队 / 限流导致的真实耗时会计进各自的 180 秒窗口**。 |

★ **S0-8 的直接后果:本次观测跑固定串行。** 并发会把排队时间计进 guidance 自己的时间预算,可能把本来能成的轮变成超时失败 —— **等于用并发把数据弄脏**。串行只要 2.5–3.4 小时,不值得冒这个险。

---

## 3. 是 / 不是

**是**(共用同一条测量通道,分开改会两次动同一批文件、两批数不可比,故同卡):

- **S1** 跑道对齐(**在 provider 边界逐项比对**)+ 有效配置落档
- **S2** 写爆归因(`llm_unparseable` 按 `finish_reason` 拆开,**机器码不夹带结论**)
- **S3** 层归因摆正(`first_blocking_stage` / `terminal_observed_stage` / `guidance_invoked`)+ 细失败码抬到汇总层
- **S4** **机会数 + 分母 + 三层未核实计数**(反假通过的主口)
- **S5** 批次有效性门 + 指标分档冻结
- **S6** attempt 级完整记录 + 终止器归因 + 版本标识

**不是**:

- ❌ **不改生产的判定与控制流**(边界见 §4)
- ❌ 不改任何 prompt / 重试逻辑 / 阈值常量的**取值**
- ❌ **不把「抬 token 上限」当修复**:评测 6000 → 与生产同源,是**摆正尺子**;**生产的 8000 一个字不动**。这两件事必须在 PR 正文里分清楚。
- ❌ **不给 guidance 接 526-B 的 `structured_retry`**(决策 27 修法顺序:**契约 → 稳定 ID → few-shot → retry,不得倒**)
- ❌ **不建 guidance 层配对分叉**(挂点已找到,等数回来定打哪层再建)
- ❌ **不造 `handle_ambiguous` 事件码**(S0-5:结构上不可能发生。**造一个永远为 0 的字段是噪音,会让人误以为量到了什么。**)
- ❌ **不用 `critical_steps_fully_covered`**(S0-4:代码里没有。「完全可执行」改用 `blocking_gap_count == 0` 定义)
- ❌ 不动对外 schema / API / 持久化 / TS / 前端(若发现必须动 → **停手回报**)
- ❌ 不落模型原文(决策 11)
- ❌ 不碰 `03_TASK_INDEX.md`(决策 07;索引单独 closeout PR)

---

## 4. ★ 红线边界澄清(v0.1 此处自相矛盾,本版修正)

v0.1 写的「不改生产行为」是**模糊的** —— S2 要把 `finish_reason` 串到失败对象,本就得动生产代码。明确:

- **允许**:在生产代码路径上加**只读遥测**(新增内部字段、事件码、日志),**且必须有测试证明判定与控制流零变更**
- **禁止**:改判定、改控制流、改 prompt、改重试、改任何阈值 / 常量的**取值**、改对外契约

**只读遥测的判据**:把新增遥测全部摘掉后,程序在**每一个既有测试**上的行为**逐字节相同**。

---

## 5. 范围

### S1 跑道对齐 —— 在 provider 边界比,不比构造对象

★ **这是 R1 的 P0-2,本卡最重要的一条防假通过。**
只比「构造对象上写着 8000」是**能被骗过去的**:对象写 8000,下游 wrapper 又改回 6000,diff 依然漂亮。

**做法**:用**同一个** recording fake provider,分别走**生产**与**评测**两条构造路径,抓它**实际收到的 request envelope**,逐项比对:

```
model
max_tokens
timeout                      ★ 第二个洞,别只盯 token
response_format / json_mode
temperature / top_p / seed   (S0-6:当前不发送 → 断言两边都不发送)
```

外加**生成器层**的实际生效值:

```
GUIDANCE_FULL_ATTEMPTS
GUIDANCE_HARD_CALL_CAP
GUIDANCE_WALL_CLOCK_SECONDS
guidance prompt / template 版本
```

**主断言(必须这么写)**:

```
production_provider_calls[guidance][0].max_tokens
    == evaluation_provider_calls[guidance][0].max_tokens
production_provider_calls[guidance][0].timeout
    == evaluation_provider_calls[guidance][0].timeout
... (上表逐项)
```

**次断言**:生产侧 guidance 的 `max_tokens` 仍来自 plan 的配置值(现为 8000),**未被本卡改动**。

★ **禁止**「两套 fake 各自自证自己」——**必须捕获真实调用参数**,一个 fake、两条路径。
★ **禁止**靠改 `DEFAULT_GUIDANCE_MAX_TOKENS` 常量值来「对齐」——那是改药,不是摆尺子。**评测侧不得自带任何一套默认值**;有效配置必须与生产**同源**(手抄的数值下次还会漂,这个洞会再开一次)。

**有效配置落档**(每次运行写进 summary,可 diff):上表全部 + `git_revision` + `guidance_prompt_template_sha256` + `summary_schema_version`。

> ★ 隐私注(决策 11):此处 hash 的是**仓库内我们自己的静态模板**,不是论文、用户输入或模型输出。与历史上被驳回的「内容 hash」(再识别指纹)**不是一回事**。

### S2 写爆归因 —— 机器码只表达观测事实

把该次 LLM 调用的 `finish_reason` 挂到 guidance 内部失败对象。★ **照 526-A / 526-B §4.7 的既有做法,别另起一套。** 内部字段,不进对外契约;`finish_reason` 是枚举,脱敏安全。

**机器码(三选一,不许并桶,不许夹带解释)**:

```
llm_unparseable_finish_length
llm_unparseable_finish_stop
llm_unparseable_finish_unknown
```

★ **不许叫「完整但畸形」。** `stop` 只证明 provider 报了正常停止,**不证明**语义完整、不证明没被 stop token 提前截断。**给码起名时夹带结论,等于替数据下判断。**

**按 attempt 落档,不只终态**(`GUIDANCE_FULL_ATTEMPTS=2` / `GUIDANCE_HARD_CALL_CAP=3`;只落终态会把首次失败吃掉)。

每次 attempt 同时落:`completion_tokens` / `prompt_tokens` / 当次 `max_tokens` / `completion_tokens ÷ max_tokens`。

★ **异常项单列**:若 `finish_reason == length` 但 `completion_tokens` **没有贴近**当次 `max_tokens` → 落 `provider_telemetry_anomaly`,**不得自动归为预算 / prompt 设计问题**。

### S3 层归因摆正 + 细码抬到汇总层

**★ `guidance_invoked` 是本卡最硬的读数:调没调模型是事实,不是判断。**
定义(S0-3):`RecordingTextProvider.calls` 里有没有 `build_guidance_generator` 这个 role 的调用。

**层归因矩阵(预登记,不得事后改)**:

```
plan 未产出可消费结果
    → first_blocking_stage = "plan"

plan 可用,但 plan.build_steps 未形成合法结构化结果
    → first_blocking_stage = "build_steps"
    ★ 此时 guidance 会报 generation_failed / build_steps_unavailable,
      但 guidance_invoked = false → 这一轮不得记到 guidance 账上(S0-2)

build_steps 合法 且 guidance_invoked = true,随后 guidance 自身失败
    → first_blocking_stage = "guidance"
```

**总账不变量**:

```
plan_owned + build_steps_owned + guidance_owned + unattributed == total_failed_rounds
unattributed == 0        ← 违反即批次作废
```

**两本账,不得混用**:`first_blocking_stage` **用于选靶**;`terminal_observed_stage` **用于诊断**。

**summary 每轮必须带精确码(不许并桶)**:

- `guidance_status`(5 选 1)
- `guidance_failure_reason`(**nullable** —— ★ v0.1 写「每轮 7 选 1」是**错的**,成功轮没有失败原因)
- `guidance_retry_count`
- 528-C validator `machine_codes`(**去重列表、精确码**;现汇总层只留了泛化的 `guidance_validator_generated_output_changed` → 抬上来)
- `guidance_generator_exception`:须带**受控枚举**的异常类别机器码(**不落 message / traceback / 原始异常类名**——类名会随第三方库升级漂移):

```
provider_timeout / provider_rate_limit / provider_server_error /
parse_error / validation_error / storage_error / unexpected_internal_error
```

**resolver 事件码(S0-5,不改判定与控制流)**:

```
handle_no_match
grounding_whitelist_no_match
```

★ 这两条是 **attempt / detail 级事件**,**不是终态失败码**。终态失败码只描述终态失败。**两条正交轴,不许合并**(R1 P0-5;若合并,成功轮会被错记成失败,或被迫改生产判定行为)。

### S4 ★ 机会数 + 分母 + 三层未核实计数(反假通过的主口)

**这是 R1 的 P0-4,也是本卡最容易被刷的地方。**
只落坏事件计数、不落机会数与分母,模型只要**少写 document detail**,或上游多失败让 guidance 根本没机会跑,**坏事件自然归零、数字漂亮、产品更空。**

**机会数**:

```
guidance_invoked                 (布尔,S0-3)
guidance_provider_call_count     (按 role 计数,S0-4)
```

**产出分母**:

```
critical_step_count              (从 _critical_steps(build_steps),S0-4)
blocking_gap_count               (从 build_guidance.assessment.blocking_gap_ids,S0-4)
final_detail_total_count
final_document_detail_count
final_unverified_detail_count
```

★★ **`build_guidance` 为 null 时,后三个字段必须落 `null`,严禁落 `0`。**
落 0 会让「**根本没生成**」和「**生成了、一条未核实都没有**」在汇总里长得**一模一样** —— 那正是 P0-4 的假通过口。
**同理:所有坏事件计数在 guidance 未触达 / 未生成时,一律 null,不许 0。**
汇总时,任何比率的分母**必须是非 null 的有效轮**,且**必须显式报出 null 轮数**。

**三层未核实计数(不许用一层顶替另一层)**:

```
generator_downgraded_unverified_count      生成阶段被降级的条数
validator_dropped_unverified_count         被 528-C 丢弃的条数
final_surviving_unverified_count           最终留在成品里的条数
```

★ 否则某条先被降级、后被 validator 丢弃,最后只看到 0 —— **生成行为与最终产品行为又混在一起。**
★ 若某一层现在拿不到 → **停手回报**(§10),**不许用另一层的数顶替**。

**「有多空」的三个读数(全报,不许只挑一个)**:

```
final_unverified_detail_count                                (绝对条数)
final_unverified_detail_count ÷ final_document_detail_count  (占比;可被 filler 稀释,故不单用)
blocking_gap_count                                           (阻塞缺口)
```

### S5 批次有效性门 + 指标分档冻结

#### 5.1 ★ 指标分档冻结(P0-1;本卡内**禁止**再出现无修饰的「成品率」)

```
plan_ready                = plan 产出可消费结果
build_steps_structured    = plan.build_steps 非空且结构化合法
guidance_delivered        = guidance_status == "generated"
                            AND build_guidance is not null
                            AND 528-C 校验完成
guidance_evidence_clean   = guidance_delivered
                            AND final_surviving_unverified_count == 0
guidance_fully_actionable = guidance_evidence_clean
                            AND blocking_gap_count == 0
```

★ **三档必须分别报,不得再压回一个数。**

★ **命门不变量**(S0-1:全丢光 ⟹ `generation_failed`):

```
guidance_delivered == true  ⟹  all_document_details_lost == false
两者同时为真 → 量具或生产逻辑有 bug → 批次作废
```

#### 5.2 批次有效性门(三道,分别管三种结论)

**门 A — 层选靶有效性**:

```
planned_round_count == 48
terminal_round_record_count == 48
missing_round_count == 0
每轮恰好一个 terminal outcome
每个失败轮恰好一个 first_blocking_stage
attempt_record_count == actual_provider_call_count（按 role 分）
attempt_index 连续、从 1 起
unattributed_failures == 0
```

**门 B — 截断归因有效性**:

```
terminal_llm_unparseable_rounds >= 5
known_finish_reason_coverage >= 90%
```

★ 不满足 → **诚实报 unknown,但不得执行 §8 的「length ≥ 60%」规则**。

**门 C — 跨批合并有效性**(两批 3 轮合并时):

```
fingerprint 去重集合 size == 1        (>1 → 不得合并选靶)
fingerprint 全缺                       → 不得宣称「同模型」,只能报 unverifiable
有效配置 / 并发策略 / 请求顺序策略 三者相同
```

#### 5.3 status × reason 合法组合表

**实施时须从代码逐一坐实**五个 `guidance_status` × 七个 `guidance_failure_reason` 的**合法组合**,写成表,并加断言:

```
guidance_status == "generated"  ⟹  guidance_failure_reason is null
guidance_status == "generation_failed"  ⟹  guidance_failure_reason is not null
（其余组合逐项写死）
非法组合出现 → 批次作废
```

### S6 attempt 级完整记录 + 终止器归因

每条 attempt 记录须带:

```
attempt_index / parse_outcome / finish_reason /
completion_tokens / prompt_tokens / max_tokens /
resolver_event_codes[] / validator_machine_codes[] /
detail_downgraded_count / detail_dropped_count / generated_output_changed /
DraftAttemptStats 四项:
    raw_document_claim_count / raw_supporting_ref_count /
    resolver_error_count / parse_error_count
elapsed_ms
termination_guard:
    none / provider_timeout / guidance_wall_clock /
    hard_call_cap / provider_rate_limit
```

★ **`retry_cap_exhausted` 只是终止器,不是根因。** 有了 `termination_guard` + `elapsed_ms`,才分得清「模型连错三次」与「第一次很慢、撞 wall clock 后没机会再跑」。

---

## 6. 脱敏(决策 11,承 526-B §4.8,本卡不放宽)

- 落档**只许**:机器码枚举 / 计数 / 布尔 / 粗长度桶 / token 数字 / 模型指纹 / 仓库内静态模板 hash / git revision
- **绝不落**:模型写的任何字符串、LLM raw response、partial JSON、异常 message、原始异常类名、字段值、Pydantic input·ctx、文件名、本机路径
- **禁** `str(exc)` / `repr(exc)` / `exc_info` / traceback / `logger.exception`
- Codex 已核:**指导层当前无模型原文落盘点**(`response.text` 只解析,不写库 / 不写文件)。**本卡不得开这个口子。**

---

## 7. 验收(全确定性;不涉任何效果断言,不触发配对跑)

1. **★ provider 边界同源自证**:一个 recording fake provider、两条构造路径(生产 / 评测),抓**实际收到的 request**,§5-S1 表**逐项相等** —— 贴输出。**禁两套 fake 各自自证。**
2. **生产零变更**:确定性测试 + diff 证明生产侧 guidance 有效 `max_tokens` 仍为 plan 的 8000、`timeout` / attempts / cap / wall clock 取值未变
3. **只读遥测自证**:摘掉全部新增遥测后,既有测试行为**逐字节相同**(§4)
4. **对外零 diff**:schema export 零 diff + 前端 typecheck 过(决策 13)
5. **★ `llm_unparseable` 可分 —— 命门测试反向证明**:fake provider 构造三例(`length` / `stop` / `finish_reason` 缺失),各落**互不相等**的机器码
6. **`provider_telemetry_anomaly` 有测试**:构造 `length` 但 completion_tokens 远低于 max_tokens 的 case,断言落异常项、**不落预算问题**
7. **两条正交轴不混**:构造 handle 未命中 / grounding 白名单未命中 两例,断言**各落 resolver 事件码**,且 **grounding 那例仍是 `guidance_status == generated`**(S0-1:它是降级不是失败)
8. **★ null ≠ 0**:构造 `build_guidance is null` 的轮,断言 `final_*_count` 三项**全为 null,不是 0**
9. **三层未核实计数各有测试**:生成阶段降级 / validator 丢弃 / 最终存活,三个数在同一 case 里**可以互不相等**
10. **命门不变量**:`guidance_delivered ⟹ NOT all_document_details_lost` —— 有测试
11. **组合表断言**:非法 status × reason 组合触发批次作废 —— 有测试
12. **按 attempt 落档**:构造「首次失败 + 重试成功」,断言落档里有**两条 attempt 记录**(不是一条终态)
13. **`termination_guard` 可分**:构造 wall-clock 超时 / hard cap 耗尽两例,断言落**不同**枚举值
14. **脱敏零命中**:扫落档产物(summary.json / csv / 日志),无模型字符串 / 无 message / 无 traceback / 无原始异常类名 / 无本机路径 / 无 raw response
15. `make check` **全绿(全管道,禁拆 CI step 列)**

---

## 8. ★ 预登记:选靶规则(先于看数说死,合并后不得改)

★ 本节是**决策 28** 的第一次落地。**规则先说死,再看数;事后调阈值找补 = 本批数据作废。**

**观测跑**(合并后动作,**不属本卡验收**):对齐后的跑道跑 **8 篇 × 6 轮 = 48 轮**,**固定串行**(S0-8),纯采数,不动任何生产逻辑。预计 **2.5–3.4 小时**。若单次跑不了 6 轮,同日连跑两批 3 轮,**须过门 C 才可合并**。

### 8.1 执行顺序(逐门推进,任一门不过即停在该门)

**第 1 门 — 批次有效性**(§5.2 门 A)。不过 → 数据作废,不得下任何结论。

**第 2 门 — 先报三档产品结果**(不选靶,先看清水位):

```
交付率       = guidance_delivered / 48
证据干净率   = guidance_evidence_clean / 48
完全可执行率 = guidance_fully_actionable / 48
```

同时报:机会数(`guidance_invoked` 轮数)、各分母的 null 轮数、`final_unverified_detail_count` 的 P50 / P95。

**第 3 门 — 静默降级门**:

```
若 (guidance_delivered 中 final_surviving_unverified_count > 0 的轮数) ÷ guidance_delivered >= 25%
    → 判「交付率这个指标本身要打折」,先修口径,本轮不选靶
```

★ **注意口径,别说重了**:降级后的正文**是后端模板、不是模型原话**(S0-1)——**这是诚实降级,不是拿假证据冒充论文依据。**
★ **但也别说轻了**:一份指导可以**有一半条目是「请你自己确认」,照样算交付**(只有全丢光才拦)。**它不是虚的,是空的** —— 该讲的没讲,活推回给学生。**能不能见人,看的是「证据干净率」,不是「交付率」。**

**第 4 门 — 截断机制门**(须先过门 B):

```
若 length 轮 ÷ 全部终态 llm_unparseable 轮 >= 60%   （unknown 留在分母,不得剔除）
    → 标 mechanism = budget_or_output_shape_pressure
```

★ **但这些轮次仍然计入 guidance 的层归因账,不得剔除。**
**两本账**:`stage_owner = guidance` + `mechanism = finish_length`。
★ v0.1 曾写「从指导层账里剔出去」——**那是错的**:为了不让指导层刷分,反而会把它的真实损失藏掉(R1 P1-2)。

### 8.2 ★ 第 5 门 — 层选靶:按**期望交付增益**折算,不用原始失败计数

**问题**:原来那条「哪层失败轮数最多就打哪层」**系统性偏袒上游**。修好上游那些轮次,它们还得**活着穿过下游**才算交付。上游的收益必须打折,下游不用打。

**折算(全部从本批数据自算,不引入外部先验)**:

```
downstream_survival(guidance)    = 1.0
downstream_survival(build_steps) = guidance_delivered / guidance_invoked
downstream_survival(plan)        = (build_steps_structured / plan_ready)
                                   × (guidance_delivered / guidance_invoked)

expected_gain(L) = failures_owned_by(L) × downstream_survival(L)
```

**选靶门(两道,须同时满足)**:

```
1) 第一名的 expected_gain 比第二名多 > 4 轮
2) leave-one-paper-out:去掉任意一篇论文的 6 轮后重算,第一名仍须第一
```

**任一不满足 → 判「分不出来」,不许硬选。**
**★ 出路是改用与层无关的判据,不是加样本。**

优先:直接修同时影响多层的机制(例如「改错重交」——出计划那道有,写步骤与生成指导都没有)。
其次:按修起来便宜排序,先做代价小、回退干净的那张。

**★ 不得把「加论文」或「加轮数」当出路:**

加轮数无用:48 轮 = 8 篇 × 6 轮,不是 48 个独立样本。一篇论文稳定死在某层,跑 12 轮就贡献 12 轮 —— 加轮数动不了 leave-one-paper-out。
加论文是另一件事:样本覆盖面属冷启动准入(决策 24:≥20 真实样本),不是选靶前提。现有 8 篇尚未跑好,此时加论文只会让失败模式更散、更难归因。论文扩容归「开测前」那一包,与本枪脱钩。

**★ leave-one-paper-out 这道门保留不变。** 它的作用是:当第一名由单篇撑起来时,禁止架构师硬选靶 —— 那时候诚实的动作是承认分不出来、换判据,不是去买样本。

**每批必报**:各层失败涉及多少篇论文 / 每篇论文各层失败次数 / 第一名是否由单篇贡献。

> ★ **诚实备注**:用作废的旧数把这条折算规则演算过一遍,它会让**指导层的领先扩大**而不是缩小。也就是说,**这不是一条为了迁就架构师预设结论而定的规则** —— 它恰好切在相反方向。规则照定,靶子仍由新数说了算。

### 8.3 作废

**旧 48 轮分布整批作废**,不得与本批混用、不得作对比基线(决策 28)。
★ 旧分布是按混合记账口径统计的(S0-3),其中有多少上游轮次被记进了指导层账 —— **不可考,也不必回头考据。**

---

## 9. 继承红线(不回退,不顺手动)

- **决策 07**(索引单独 closeout PR)/ **决策 08**(改文本文件保原始字节:定点替换 + `git diff --unified=0` 自查)/ **决策 11**(脱敏)/ **决策 13**(改对外 schema 须列全同步)/ **决策 15**(先诊断后修)/ **决策 25**(硬契约始终由确定性规则验证,不靠模型判卷)/ **决策 27**(全部六条 + 修法顺序)/ **决策 28**(效果判据)
- **526-A as-built**(`reason_code` 内部 + `finish_reason` 透传 + 对外零变化)不回退;**本卡复用其口径,别另起一套**
- **528-A/B/C as-built** 不回退;**528-C 语义闸不放宽**
- **反编造防线(506 + 528 + 529)不得放宽**
- **依赖措辞 v0.3 生产路径**(渲染哈希 `053561af…` / `f5b564fc…`)**不得改字**
- **同场配对评测台**(`--paired-build-steps` / `--paired-build-steps-full`)是资产,**不许拆**
- **禁两套 pipeline**

---

## 10. ★ 实施前置(三项 confirm-and-stop;基线 = 当前 `origin/main`)

**核完这三项无阻即实现;不符 → 停手报架构师(决策 15),别硬上。**

1. **七个 `GuidanceFailureReason` 逐一标明「判定发生在调模型之前还是之后」**,产出 §5.3 的**合法 status × reason 组合表**。
   *(Stage-0 已给两个:`build_steps_unavailable` = 之前;`evidence_card_unavailable` = 之后。其余五个须逐一坐实 —— **凡「调模型之前」判出的,一律不记 guidance 账。**)*
2. **三层未核实计数**(生成阶段降级 / validator 丢弃 / 最终存活)是否**都拿得到**。
   **拿不到 → 停手回报,不许用一层顶替另一层。**
3. **生产侧 guidance 的 `timeout` 实际值**。
   *(Stage-0 只报了评测侧落回 90,**未报生产侧**。这是 §5-S1 主断言的一个比对项,不能凭空写。)*

**其余停手条件**:

- **编号**:第一步 `git fetch` + 查 `docs/tasks/`,核 TASK-535 未被占用;占用则顺延、回报
- 若**对齐口径必须改生产的判定或控制流** → **停手回报**
- 若**必须动对外 schema / API / TS / 持久化** → **停手回报**
- 若**跑道不支持配置轮数** → **停手回报**(不自行改跑道结构)
- ★ **卡面与实测不符 → 以实测为准,回报,不迁就卡面**

---

## 11. 派单说明

- feature branch 从 `origin/main`(`git fetch` 后切)
- **卡随代码 PR**;**不碰 `03_TASK_INDEX.md`**(决策 07;合并后提醒 PM 走索引 closeout PR)
- 无对外契约变化 → **无** export-schema / freeze / TS diff(若确需碰对外 → **停手回报**)
- `make check` 全管道跑绿 + 显式列 schema export、前端 typecheck 两条(不在 `make check` 里)
- **脱敏亲核**(贴本体,不凭勾选)
- PR 全走 PM 网页侧:Codex 只 push 分支 + 给标题 / 正文 / compare 链接,**不自建、不登录、不合并**
- PR 正文必须把「**摆正尺子**」(评测 6000 → 与生产同源)和「**改药**」(改生产取值,本卡零)**分开写清楚**

---

## 12. 估时

预估 **6–9 小时**(测量通道 + 测试;不含观测跑机器时间 2.5–3.4 小时)

---

**版本**:v0.3
**作者**:Claude(架构师)
**依据**:Codex R6 只读核查 ×2(2026-07-12)+ R1 设计审(条件通过,采纳 13 / 打回 2)
**审批**:R1 条件通过 → PM 拍 → 派 Codex(须先过 §10 三项 confirm-and-stop)

---

## 附:R1 十五条处置台账

| R1 | 处置 |
|---|---|
| P0-1 「成品率」同词异义 | **采纳** —— 已从 534 as-built 原件坐实(41.7% / 37.5% 两个数) |
| P0-2 provider 边界抓实际调用 | **采纳** —— 本卡最重要一条;顺带照出第二个洞(timeout 90) |
| P0-3 量具完整性门;failure_reason 须 nullable | **采纳** —— v0.1 写「每轮 7 选 1」是错的 |
| P0-4 机会数与分母 | **采纳** —— 534 的 14/24 未触达已证明不是理论问题 |
| P0-5 grounding 拆两条正交轴 | **采纳** —— Codex S0-1 坐实是降级路径 |
| P1-1 first_blocking_stage | **采纳** —— Codex S0-3 给出硬读数 `guidance_invoked` |
| P1-2 60% 规则口径;length 不得剔除 | **采纳** —— v0.1 那条规则是错的 |
| P1-3 leave-one-paper-out | **采纳** —— 并补:真瓶颈是论文数,加轮数无用 |
| P1-4 `stop` 不叫「完整但畸形」 | **采纳** —— 机器码不许夹带结论 |
| P1-5 25% 作报警线 | **采纳** —— 并按 S0-1 修正口径:诚实降级,但「空」不是「没事」 |
| P1-6 指纹每次调用落;并发须冻结 | **采纳** —— S0-7 显示大半已有;本次固定串行 |
| P2-1 attempt 带完整结果 | **采纳** |
| P2-2 termination_guard | **采纳** |
| P2-3 异常类别受控枚举 | **采纳** |
| P2-4 git revision + 模板 hash | **采纳** —— 隐私边界已核:hash 的是仓库内静态模板,非用户/模型内容 |
| ~~R1 称 528-B 已有 `critical_steps_fully_covered`~~ | ❌ **Codex 打回:代码里没有。** 改用 `blocking_gap_count == 0` |
| ~~R1 要求 `handle_ambiguous` 事件码~~ | ❌ **Codex 打回:结构上不可能发生。不造永远为 0 的字段。** |
