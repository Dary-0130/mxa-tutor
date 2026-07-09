# TASK-528-C · 建模指导语义校验闸(穷尽语义硬门)· v0.1

**线**:paper-to-model · **前置**:528-A(契约,已合)、528-B(生成引擎,已合 @ `origin/main` `1518f9a`)· **后继**:528-D(前端)、528-E(05 文案 + eval)
**双审**:R1(GPT 设计审)+ R6(Codex 可落核)已完成,2×P0 + 6×P1 已收敛入本卡(见 §7 审查台账)。
**范围**:完整瘦 C —— ①独立语义校验闸 ②接读回路径(工作台可复用)③红线机检测试。**不 bump `CURRENT_SCHEMA_VERSION=8`;不新增对外契约;不破 feature 边界(决策 21)。**

---

## 1. 目标与非目标

**目标**:造一道独立、权威、穷尽的语义校验闸,**任何一份组装好的 `BuildGuidance` 对象(不管刚生成还是从存储/本地文件读回)在被当作产品消费前都经它**。把散在生成器里的语义规则收成单一权威真值,补上 528-B 未覆盖的三个洞:(A)无独立穷尽校验器 (B)无红线测试套件 (C)读回不走语义校验。

**非目标(明确不做)**:
- 不给用户加任何可见变更(→ 528-D)。
- 不改 build_steps、不降 build_steps 降级率(另一条线)。
- 不造本地课题包存储本身(工作台阶段)—— 但校验闸设计成工作台读回可复用(§5.6)。
- 不评价指导内容质量/有用性(→ 528-E eval);本卡只管"绝不越界",不管"写得多好"。
- 不 bump schema version、不新增公开字段(见 §6 契约红线)。

---

## 2. 核心原则(不得推翻)

### 2.1 逐条隔离,不是整份判死
一条不合法 → **只把那一条降级(→ `user_confirmation_required`)或丢弃**,其余全留;粒度与 528-B 生成当场一致。**整份才降级只限三种诚实情况**(§4.3):对象结构不可读;逐条处理后无合法 `document_extracted` 剩余;lifecycle 不变量无法修复。**绝不因单条坏 detail 判死整份。**

### 2.2 两种"严"分离 —— 内容合法性对齐生成器、结构/读回完整性主动补
- **维度一「内容合法性」:闸与生成器共用同一份权威规则、绝不更严。** 规则**只写一份**,生成器与闸共同调用(不是闸抄一份),防两边尺子飘开、也防闸偷偷收窄。**在此维度把闸顶得比生成器严 = 掏空合法内容 = 本卡首要缺陷。**
- **维度二「结构/引用/读回完整性」:闸主动补,生成器未显式校验。** 生成器顺流程产出天然满足,故补它不误杀合法内容,只逮被改坏/旧版/损坏的读回对象。
- **划分见 §5.1(维度一)/§5.2(维度二),由 R6 拿真代码坐实。**

### 2.3 一致性铁律(焊死"不掏空")
**生成器产出的任何一份对象,过闸后:0 丢弃 + 0 降级 + 0 语义 normalization + assessment/status 不变。** 必过项;CI 红即挡合并(§5.7 测试 T1)。这条把"焊错"的面缩到"生成器现行规矩本身对不对"——闸若与生成器不一致,此测试当场红。

---

## 3. 维度划分权威表(R6 已实证坐实 @ `1518f9a`)

### 3.1 维度一 —— 抽成共享单一真值,闸调用、不许更严
物理落点建议:`features/paper/build_guidance_rules.py`(生成器与闸共用;R6 确认不 import overview/explanation 私有、不破决策 21)。

| 规则 | 生成器现位置 | 闸复用方式 |
| --- | --- | --- |
| convention code 白名单 | `CONVENTION_TEMPLATES` | 直接查集合 |
| confirmation reason 白名单 | `CONFIRMATION_REASON_TEMPLATES` | 直接查集合 |
| 不安全文本过滤(数值+单位/路径/环境词) | `_unsafe_freeform_text` / `_unsafe_direction_hint` 及其 regex 口径 | **同源调用,绝不扩严** |
| high-risk token 抽取 + canonicalization(`5 kW`/`5kW`/LaTeX/单位别名) | `high_risk_claim_tokens` + 归一化 | **同源调用**(仅用于 §5.3 读回事实核对) |
| `GroundingTruthIndex` 四类真值面 | 现有 | 同源(仅 §5.3 场景) |
| basis → actionability 映射 | 后端构造映射 | 查确定表 |
| gap 合成表(kind/basis/severity/scope/template) | `GAP_SYNTHESIS_RULES` / `_gap_from_rule` | **复用同表,不另起更严 gap 表** |

> ★ `GapSynthesisRule` 属维度一(内容合法性),**易被误归成结构校验 —— 不是**。闸校验"gap ∈ 表",不许自造更严 gap 规则。

### 3.2 维度二 —— 闸主动补(生成器未显式校验)
- `guidance_status` ↔ `build_guidance` 五态不变量(lifecycle floor 之上补全)。
- `detail_id` / `gap_id` 唯一性。
- `detail.step_id` 存在于当前 build_steps(**仅 current 模式**,§5.4)。
- `gap.scope` 与 `step_id` 一致性(`plan`⟹`step_id=None`;`step`/`subsystem`⟹`step_id!=None`)。
- evidence locator ∈ 当前 `PaperSpec`(**仅 current 模式**;复用 `EvidenceTagger.validate_for_spec`)。
- `blocking_gap_ids` 与实际 blocking gaps **精确重算一致**(不是子集,§5.5)。
- assessment 由 details/gaps 重算而来;`overall_status="reproducible_ready"` 读回时重算覆盖或拒绝。
- convention/confirmation 的 evidence 必须为空;document_extracted 的 convention_code/confirmation_reason_code 必须为空。
- 旧/损坏读回对象温和净化(§5.6)。

---

## 4. 组合矩阵与整份终态(P0-2 + P1-3)

### 4.1 合法组合矩阵(穷尽,写成测试表非散在 if 里)
| basis | evidence | convention_code | confirmation_reason_code | actionability |
| --- | --- | --- | --- | --- |
| document_extracted | ≥1 且合法内联 evidence | None | None | actionable |
| engineering_convention | `[]` | 白名单 code | None | code 映射值 |
| user_confirmation_required | `[]` | None | 白名单 reason | blocked_pending_confirmation |

### 4.2 非法例(逐条须有红线测试拦下)
`document_extracted + evidence=[]` · `document_extracted + actionability!=actionable` · `engineering_convention + evidence非空` · `engineering_convention + convention_code=None` · `engineering_convention + 白名单外 code` · `user_confirmation_required + evidence非空` · `user_confirmation_required + display_text/hint 含数值或路径` · `GuidanceGap.basis=document_extracted`(类型层已排除,读回旧/坏对象仍测)· `gap.scope=plan + step_id!=None` · `gap.scope in {step,subsystem} + step_id=None` · gap 的 (kind,basis,severity) 不在 `GAP_SYNTHESIS_RULES` 表内。

### 4.3 整份终态处理(P0-2 硬边界)
逐条隔离后:
1. **仍要作为 `generated` 暴露 ⟹ 至少保留 1 条合法 `document_extracted` detail。**
2. 若隔离后无任何合法 `document_extracted`(即使还剩 convention/confirmation)—— **不得作为 `generated` 返回**(守"指导必须有论文依据"根约束)。
3. 此类读回损坏对象标 **`generation_failed`(需重生成)**,**不是 `no_document_basis`**。`no_document_basis` 保留给"生成跑通但确实零 document claim"的诚实终态;读回损坏 = 对象不可信,不是论文无依据。
4. telemetry 须区分 `guidance_validator_all_document_details_lost`,避免误统计成论文无依据。

---

## 5. 校验闸设计

### 5.1 两个模式(P1-1,防冻结快照被误清)
校验闸按 `guidance_status` 分模式:
```
mode = current_generated:
  强校验 step_id ∈ build_steps / evidence locator ∈ PaperSpec / gap / status / assessment 全一致(§3.2 全量)
mode = stale_snapshot:   # guidance_status == stale_pending_regeneration 且保留冻结快照
  不把"旧 step_id 不存在于当前 build_steps"当作单条非法(豁免 step membership)
  不用当前 build_steps 重新合成缺口
  只校验:不出现伪 document truth(§5.3)、不出现 unsafe convention/confirmation、不破坏状态不变量、blocking_gap_ids 等自含部分一致
  UI 只显示 snapshot 自身 display_text + stale banner,不参与可复现评级
```
> R6 实锤:参数纠错 apply/undo 会清 `m_script_skeleton` + `build_steps`、保留旧 `build_guidance` 标 `stale_pending_regeneration`;故 `build_steps=None` 时 current 模式的 step/PaperSpec 强校验**必须豁免**,否则合法快照被整份误杀。

### 5.2 逐条净化流程
每条 detail/gap 独立过维度一 + 维度二检查:合法 → keep;维度一违规(内容对不上规矩)→ 按类型 downgrade/drop;维度二可修(缺默认字段/稳定排序)→ normalize;不可修 → drop。降级产生的替代文案**走后端模板重建**,**禁止复用原 claim_text**(528-B 已规定 grounding 失败不复用原文)。

### 5.3 读回事实核对(P0-1,走"当场现算";补维度二、不碰维度一口径)
读回对象只剩公开 `display_text` + 内联 evidence,无原始 handle/pool/truth-index 上下文,**不能重演 handle-resolved 判定**。改为:
- 对 `document_extracted.display_text`:抽 high-risk token(§3.1 同源 extractor + canonicalization)→ 与内联 evidence 对应的 `GroundingTruthIndex` 命中检查;对不上 → 该条降级为 `user_confirmation_required`。
- 对 convention/confirmation.display_text:优先后端模板重建比对(§5.8);至少跑同源 `_unsafe_*` filter,禁数值/精确路径/solver/采样时间/toolbox 变体从模板后门进入。
> 这补的是"这句话是否被证据支持"(手改防线),**用的是生成期同一套口径,不新立更严标准** —— 属维度二加固,不改维度一。**★ 明令:不对最终 display_text 做通用"禁所有数字"扫描**(模板天然带 step_id/参数名等合法标识,通扫数字是过严高危,§7 高危点 1)。

### 5.4 step 引用校验:仅 current 模式强制(见 §5.1)。stale_snapshot 豁免。

### 5.5 blocking_gap_ids:精确重算,非子集(P1-4)
```
assert assessment.blocking_gap_ids == recompute_blocking_gap_ids(gaps, details, build_steps)  # 顺序稳定、去重稳定
```
子集只防"引用不存在的 gap",防不住"漏报 blocking gap"(会让 UI/评测低估阻塞)。mismatch:读回以重算值覆盖;current generated 模式且重算失败 → 整份 `generation_failed`/`stale`,不继续当 current。

### 5.6 落点:独立无 IO 纯函数(P2-3,工作台复用)
校验闸放 `features/paper/build_guidance_semantic_validator.py`(无 IO 纯函数,靠近 domain),**由 SQLite load、(未来)本地课题包 import、API 写回共同调用**;不绑死在 `SqlitePaperCache` 内。
- **SQLite 挂点(R6 实锤)**:`_load_with_nested_evidence_migration` 里 `TypeAdapter.validate_python` 得到 typed plan 之后、在拿到 spec+plan 的 record 层执行(需 spec 供 §3.2 的 PaperSpec/评估校验)。
- **schema-invalid nested guidance**:现结构会整份 deserialize fail、闸看不到;要温和隔离旧/坏 blob(缺字段、旧枚举)需在 typed 化前加 **raw guidance 预清洗(scrub)**。旧 blob 缺 `guidance_status` 补 `not_generated`;若同时带旧 guidance,按 §4.3 终态处理,不静默清空。

### 5.7 返回结构化结果(P1-6,不只抛异常)
```python
GuidanceSemanticValidationResult:
    plan: ModelGenerationPlan
    changed: bool
    item_actions: list[ItemAction]     # drop | downgrade | keep | normalize (+ 机器码)
    whole_action: Literal["keep","mark_generation_failed","mark_stale_empty","corrupt_unreadable"]
    machine_codes: list[str]           # 决策 11:纯机器码,不带值/单位/原文/路径/claim
```
统一结果对象,防 SQLite load / import / API GET / regenerate 写回各自临场处理、语义再次散落。

### 5.8 模板版本兼容(P1-5,防旧文件被批量误降)
**不做 convention/confirmation display_text 的"必须等于当前模板输出"exact 比对**(文案小改会让旧 SQLite/本地包里合法旧 guidance 读回时批量降级)。改为:`BuildGuidance.version="v1"` 下对旧模板只做 unsafe-token filter,不做 exact string equality;或模板版本变更时把旧 guidance 统一标 `stale_pending_regeneration`。典型"过严掏空"点。

### 5.9 telemetry(P2-1;决策 11:纯机器码,不带内容)
`guidance_validator_detail_downgraded_count` · `_detail_dropped_count` · `_gap_dropped_count` · `_all_document_details_lost` · `_template_version_mismatch` · `_display_text_grounding_failed` · `_stale_snapshot_step_ref_ignored` · `_generated_output_changed`(**必须长期为 0;非 0 即 CI fail**)。真论文批量跑时"过严"会显示成降级飙高、当场可见。

---

## 6. 契约红线(不 bump v9)

- 若仅新增 validator + 共享规则 + 测试 + telemetry 机器码,**不新增公开字段、不改 Literal、不改 Pydantic Field 约束 ⟹ 不 bump `CURRENT_SCHEMA_VERSION=8`、不触发完整 schema-sync**(R6 确认)。
- **本卡走"读回当场现算"(§5.3),不新增持久字段**,故落此路,不动契约。
- 触发决策 13 全清单的红线(本卡不得踩):新增公开字段(如 `semantic_validation_version`/`template_version`/`validation_errors`)、增删改 `guidance_status`/basis/gap_kind/severity 等 Literal、改 Pydantic 约束、改 06 中 BuildGuidance 公开语义、新增 JSON schema 导出字段。若实施中发现非动契约不可,**停下报架构师**,不擅自 bump。
- 脱敏(决策 11)贯穿:validator/telemetry 机器码,日志不含任何值/单位/原文/路径/claim;不复用原 claim_text。
- 改文本文件保原始字节(决策 08);先诊断后修(决策 15)。

---

## 7. 审查台账 + 过严高危点(实施须逐条守)

**P0-1**(§5.3):读回补 display_text 事实核对(同源 grounding,不通用扫数字)。
**P0-2**(§4.3):逐条隔离碰"论文依据全丢"→ 标 `generation_failed`、区分 telemetry、不误落 `no_document_basis`。
**P1-1**(§5.1):current/stale 两模式,冻结快照豁免 step/PaperSpec 强校验。
**P1-2**(§3):维度划分——gap 表/actionability 映射归维度一共享真值,引用完整性/重算/唯一性归维度二。
**P1-3**(§4.1/4.2):组合矩阵穷尽、写成测试表。
**P1-4**(§5.5):blocking_gap_ids 精确重算、非子集。
**P1-5**(§5.8):模板版本兼容,不做 exact 比对。
**P1-6**(§5.7):返回结构化结果对象。
**P2-1**(§5.9)/ **P2-3**(§5.6):telemetry 机器码 + validator 独立纯函数。

**★ 四处明令不许过严(拿真代码坐实的掏空高危点):**
1. **不对最终 display_text 做通用"禁所有数字"扫描**(§5.3)。
2. **stale_snapshot 豁免 `step_id ∈ build_steps`**(§5.1/5.4)。
3. **读回只校验内联 evidence 合法性,不重演 handle/truth-index**(§5.3)。
4. **domain-legal 但 generator-impossible 的旧 gap:丢该 gap/标需重生成,不杀整包**(§5.6)。

---

## 8. 验收(双轴,两轴同为必过)

**拦得住**:§4.2 每条非法组合被红线测试拦下;读回手改(document_extracted.display_text 塞入论文外数字但 evidence 合法)被 §5.3 降级;引用断裂/被手改对象逐条隔离,损坏时整份标需重生成。
**留得住**:§2.3 一致性测试(生成器产出过闸 0 丢/0 降/0 semantic normalization/status 不变)绿;边界(`5 kW`/`5kW` 归一化不误伤薄论文)。
**测试三组(§5.7 落点)**:
- **T1 generator golden pass-through**:真实/fixture 生成的 guidance 过闸,0 changed/0 drop/0 downgrade。
- **T2 mutation redline**:对合法对象逐字段 mutate,§4.2 非法组合全部被拦。
- **T3 stale/readback**:旧 blob、缺字段、stale snapshot、step_id 已变化、本地包 JSON 被手改,各得正确 mode 处理;冻结快照不被误清。
**红线测试挂回来源**:每条红线测试注明其对应生成器哪条行为/哪条共享规则(便于某规矩以后被判定要改时,一眼定位该改的测试、不漏改)。
**落点**:规则/一致性 → `tests/features/paper/test_build_guidance_generator.py`;读回/旧 blob/隔离 → `tests/adapters/storage/test_sqlite_paper_cache.py`;冻结快照 → 复用现有 parameter correction / user supply / step regeneration 测试;schema 不变 → 确认 freeze 不动。全绿 + `make check` 全管道(含 `ruff format --check`、`ruff check`、mypy)方可交。

---

## 9. 继承红线(不回退)
528-A/B、507-A/B、508、522-C1/C2/D1、523、524、525、526 as-built 不回退。禁两套 pipeline。build_steps 链逐字节无 diff。反编造全套(506 + 528 §4.2/4.3 as-built)不松。
