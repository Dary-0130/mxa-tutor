# TASK-538 v0.2: 内容层放行 · 三类分支逐条处置 + 五阶段收口(build_steps / guidance 不再整份判废)

## 状态
🔲 未开始(v0.2;R1 设计审 + R6 可落核/坐实已收,改动已并入;待 R2 GPT 二审 → 实施 Stage 0 分支处置表架构师签字 → 实施)

## 版本说明(v0.1 → v0.2 改了什么)
双审核心结论:v0.1 的"内容 vs 防崩"二分**不成立**——会泄露私有引用、把未核内容显示成"已验证论文来源"、并在读回/前端重新崩。R6 拿 `origin/main@232bcc1` 实码逐条证过。v0.2 按双审重写:

- 二分 → **三类**(内容 / 结构完整性 / 安全隐私),**逐分支**分类,不按文件名 / validator 名一刀切。
- 清空点从"一处"→ R6 实证的**五阶段**(生成 / 草稿 DTO / 写前 / SQLite 读回 / API 完整性);且 guidance 是 validator **改写返回**、不是抛错。
- "原样透传"拆成**三层**(原始 completion 仅 eval / 模型语义字段保留 / 后端所有权字段仍盖章),消除与"私有引用不外泄 + schema 零 diff"的矛盾。
- 补:确定性降级矩阵、guidance 状态矩阵、隐私安全日志 schema、诚实横幅、badge 盖章、537-A 恢复入口、部署兼容矩阵、验收分母指标。

## 上下文
产品当前按自己口径 0 输出:LLM 已生成完整 build_steps(参数、步骤、连线齐全),但后端一串判定判它"无支撑",把 build_steps 判废清成 null;前端一看没 build_steps 掉进推荐块 fallback,显示成半成品。诊断实证:头号缺口 `missing_parameter_value` 896 条阻塞里 488 条(54%)参数表里明明有值;"generated=成功"只表示结构合法 JSON,三个自承认口径重算 229 轮 = 0/229;墙拦不住真编造(0.0006 死区带 `document_extracted` 过),却把正常参数弹走。

PM 决策(决策 29):产品对 LLM 输出只做格式层(防前端崩),内容判定放行、当参考,编造靠内测反馈收。验收基准:让输出至少能显出来(≈ 跟 GPT 直出打平);真正优于 GPT(参数落到出处且落对)归下一张参数卡。旧口径全作废。

## 现状(R6 已对 `origin/main@232bcc1` 坐实,本轮未改代码)

**后端整份清 build_steps 的点:**
- `paper_plan_service.py:252` — `PlanAssembler.validate_and_derive_build_steps` + `_validate_build_step_evidence`;任何 `BuildStepsStructuredError` → `_log_build_steps_fallback` → `build_steps=None` → 退 `subsystem_steps`。
- `paper_plan_service.py:573 / :1125 / :1272` — 草稿 DTO / `source_ref` 解析 / final evidence → `BuildStepsDtoValidationError`;子码 `source_ref_missing` / `source_ref_no_match` / `source_ref_ambiguous` / `source_ref_leaked` / `final_evidence_invalid` → 整份清。
- `paper_plan_helpers.py:511` — `BuildStepsSemanticValidationError`;子码 `coverage_missing` / `parameter_ref_no_match` / `br_no_match` / `depends_on_cycle` / `connection_ref_not_visible` → 整份清。
- `paper_plan_helpers.py:709` — redline `parameter_value_leak` / `tuning_value_leak` → `BuildStepsRedLineError` → 整份清。
- `paper_plan_helpers.py:967` — evidence 白名单 / locator / source invariant → `BuildStepsEvidenceError` → 整份清。
- `paper_plan_integrity.py:17` — 读回/API 完整性拒绝;`parameter_conflict_build_step_text_stale` → `PaperPlanGenerationError`,可让带 build_steps 的 plan 过不了下游。

**guidance 清空的点(注意:多为 validator 改写返回,不是抛错):**
- `build_guidance_generator.py:280` — `plan.build_steps is None` → `build_guidance=None` / `generation_failed` / reason `build_steps_unavailable`。
- `build_guidance_generator.py:482` — 多轮仍未成功 → `build_guidance=None`;reason `evidence_resolution_failed` / `evidence_card_unavailable` / `no_document_basis` / `llm_unparseable_*`。
- `build_guidance_semantic_validator.py:269` — **返回改写后 plan**(非抛错)可把 guidance 清 null;子码 `guidance_validator_terminal_guidance_cleared` / `_current_steps_missing` / `_all_document_details_lost` / `_legacy_v1_stale`。
- `build_guidance_lifecycle.py:19` / `paper_schemas.py:655` / `sqlite_paper_cache.py:731` — 生命周期/schema/读回仍会把 terminal 状态 guidance 清掉,或拒绝 `generated` 但无 document-basis evidence 的 guidance。

**前端连带:**
- `PaperResultPage.tsx:82` — build_steps 非数组/空 → 推荐块 fallback。
- `BuildSteps.tsx:102` — 非空 build_steps 渲结构化,但内部直接用 `block_refs.length` / `parameter_refs.length` / `connection_hints.length` / `configuration_hints.length` / `depends_on.length` → **放行半结构数据会崩(真白屏点)**。
- `ParameterTable.tsx:134 / :170` — `remainingMissingPrompts.length` / `.flatMap` 无兜底。
- `usePaperResult.ts:79` — 透传 `remaining_missing_prompts`,缺字段无默认 `[]`。
- `SourceBadge.tsx` — 不是最大风险;build_steps evidence 只映射 doc/user 类型,guidance unverified badge 前端基本没渲染。

**537-A(已坐实:未合入 origin/main):**
- `PaperResultPage.tsx:86` — 重生成入口只看 `!structuredSteps || m_script_skeleton == null`。
- `paper_step_regeneration_service.py:325` 含 `guidance_status_requires_regeneration`,但 `build_guidance_lifecycle.py:108` 只对 `stale_pending_regeneration` 为真 → `generation_failed` / `no_document_basis` **不会自动亮入口**。

## 核心原则:三类分支,逐条处置(v0.2 的脊梁)
**不按文件名 / validator 名整体归类。** 同一函数里,内容分支放行、结构分支局部防御、安全分支照旧拒绝。三类:

- **A · 内容规则**(证据够不够、对不对、参数有无论文支持)→ **保留内容 + 记日志**,不再改变产物生死。
- **B · 结构/引用完整性**(重复 ID、`depends_on` 自环、连线指向不存在的 block、字段类型错、私有引用无法解析)→ **保留父级产物,局部去掉/降级坏字段**,不把坏关系塞给前端;不整份清。
- **C · 安全/隐私/所有权**(私有 `source_ref` 外泄、路径/秘密泄漏、危险 HTML、把 `user_supplied` 伪装成 `document_extracted`)→ **照旧确定性剥离/拒绝该字段**,**不放行**。

## "原样透传"的准确定义(三层,消矛盾)
"LLM 给什么留什么" ≠ 把草稿裸透。分三层:
1. **原始 completion**:仅 eval-only 字节级保存(生产不落,守 535 S7)。
2. **模型负责的语义字段**(标题 / 意图 / 步骤正文 / 连线说明 / 涉及块名等):尽量保留。
3. **后端负责的字段**(出处 / ID / 定位 / source 类型 / 版本):后端按不透明引用号唯一解析后重建,**绝不照抄模型给的值**(决策 27 不动)。

`source_ref` 未命中时(R6 指认这是二分最不干净的点——既是内容判定、又是"草稿私有引用 → 公共 `PaperEvidenceEntry`"的结构转换):**保留步骤/detail 主体,evidence 降级或置空,不给伪造"已验证论文"badge**,记日志(子码 + 原始引用摘要,摘要限日志允许字段)。

## 范围(必须做)

### 一、后端:五阶段一起改,三类分支逐条处置
- **实施 Stage 0(第一步,不改代码)**:基于 R6 坐实,产出**分支级处置表**(格式见附录),**架构师签字才动代码**。
- **五阶段全覆盖**:生成期 / 草稿 DTO + source_ref + final evidence / 语义校验 / redline / evidence 白名单 / 写前 + 读回 + API 完整性 / guidance 生成 / guidance 语义 validator 改写返回 / lifecycle + schema + readback(位置见"现状")。
- guidance validator 是**改写返回、不是抛错**:实施要改 validator 的**清空返回逻辑**,不只是 catch。
- `paper_plan_integrity.py` 的 conflict stale 拒绝:Stage 0 明确归类——继续作一致性保护,还是也改日志放行(架构师定,别默认)。
- ★ **只改生成期 = 假放行**:读回 / lifecycle / schema / API 序列化会再清。五阶段不同步改则不算完成。

### 二、格式层:确定性降级矩阵(不是一个大 catch 返空)
- 根 JSON 合法、列表个别 item 校验失败:**逐 item 校验**,留合法 item;坏 evidence 只去 evidence、坏 connection 只去 connection,**留所在步骤**。
- 根 JSON 合法、item 带禁止的后端字段:记 `draft_schema_invalid`(或更细子码),剥离禁止字段后保留可合法重建的模型语义;**不静默**。
- 根 JSON 截断 / 语法坏、结构化重试仍不可解析:**不用正则 / 宽松 parser 猜字段边界**,落现有 fallback;若已有上一份合法产物,**保留旧产物**,不用坏结果覆盖。
- provider 鉴权失败 / 配置错 / 存储事务失败 / 进程取消:**不是"坏 JSON"**,不许被宽 `except Exception` 伪装成内容 fallback;`CancelledError` 等**必须传播**。
- ★ 没这张矩阵,Codex 很可能用一个大 catch"返空不 500",表面过 500 验收,实际用户仍看不到东西。

### 三、guidance 状态矩阵(不新增枚举)
- `generated`:格式合法、有可展示 guidance;**内容警报不再改变此状态**。
- `generation_failed`:provider / 格式层最终无法形成可渲染 guidance。
- `no_document_basis`:新流程不再产生(R6 提醒:它只在零 raw document claims 且 evidence pool 空/未链接时出现,别只搜这一个词——要覆盖 generator terminal reason + validator lifecycle 全链路);旧数据只兼容读取,**不再触发清空**。
- `stale_pending_regeneration`:沿用既有失效语义,**不被本卡改写**。
- **覆盖全回路**:生成 → 持久化 → GET 读回 → 页面刷新,不只测 service 返回值(否则生成当场非空,写前/读回 validator 又清掉)。

### 四、前端同步(真白屏点)
- `PaperResultPage.tsx:82` 顶层数组判断保留。
- **`BuildSteps.tsx:102` 内部数组**(`block_refs` / `parameter_refs` / `connection_hints` / `configuration_hints` / `depends_on` 的 `.length`)必须 normalize 兜底 —— **这是真白屏点,不是 SourceBadge**。
- `ParameterTable.tsx:134 / :170`(`remainingMissingPrompts.length` / `.flatMap`)兜底。
- `usePaperResult.ts:79`(`remaining_missing_prompts` 无默认 `[]`)补默认。
- 非空 build_steps 渲结构化步骤卡,真无法形成结构化步骤才落推荐块 fallback。

### 五、三个 UI(诚实,不把关)
- **恢复入口**:guidance 失败(含 `generation_failed`,及 build_steps + m_script 都在但 guidance 失败)→ **让重生成按钮亮**。现状只在 stale 亮;要把 `generation_failed` 纳入"可重生成"谓词(前端按钮 `PaperResultPage.tsx:86` + 后端 regeneration-required `build_guidance_lifecycle.py:108`)。★ R6 坐实:这个洞不会因放行自动消解,必须手动补。
- **诚实横幅**:结果页常驻一条 **「这是 AI 生成的搭建建议,仅供参考」**(PM 定,就这一句)。**告知,不把关**——不挡不删不筛任何内容。
- **badge 盖章**:`SourceBadge` **只在后端确实解析并盖章出处时**显"论文来源/已定位";引用未命中 → 不显 badge 或显"出处待核",**绝不显绿色/确定性论文 badge**。删除 v0.1"标签留删随意"。★ 538 只做"章真才盖";把"核实"本身做对(参数拼接 bug)是下一张卡,故真机打印会见到不少"出处待核"——**那是诚实**。

### 六、日志(正式交付 + 隐私安全)
结构化事件,冻结字段:
```
correlation_id / paper_id_pseudonym
artifact_kind        build_steps | guidance
role / attempt / stage
rule_code / existing_subcode
item_path            如 steps[2].connection_hints[1]
data_kind            parameter | block | connection | evidence | configuration
claimed_source_kind
action               passed_through | field_degraded | item_degraded | fallback
opportunity_count / hit_count
final_artifact_present
model_version / prompt_version
```
- **禁止字段**:参数值 / 单位值 / 论文 excerpt / 文件名 / 绝对路径 / LLM 正文 / 异常 message / traceback(守宪法 § 9 不记用户内容)。
- 同 `correlation_id` 从"规则命中"追到"最终是否显示";批量聚合/去重,避免一篇论文数百条无用日志。
- 每个旧阻断子码:确定性测试(命中 → 产物非空 → 日志子码准 → 隐私哨兵未出现)。

### 七、评测侧落原文(扩 535 S7,不另造第二条管道)
每次调用并排保存:原始 completion / 私有 draft 解析结果 / 最终 API-持久化结果 / 期间 transform + 子码 / `finish_reason` + token + model + prompt version。边界:公开评测论文、本地 `eval/out/`、gitignored;**生产 DI 不装配 recorder**;唯一哨兵测试证明生产日志 / DB / API 均无 raw completion。★ R6 坐实:现状 `eval/run_paper_pdf_smoke.py` 记的是加工后 payload(不是 raw `response.text`)——**是扩,不是复用现成**;先核现有 recorder 记录哪些 role/attempt/正文再扩,别造两套命名/脱敏规则。

### 八、部署兼容 + 缓存(P1,别漏)
- **兼容矩阵**:新前+旧后(显旧 fallback)/ 旧前+新后(新后端不发让旧组件崩的组合)/ 新+新(缺字段、空数组、`null`、未知状态均有界)。
- **顺序**:先部署向后兼容的前端空值防御,再部署后端放行;或 feature flag 切换。同 PR ≠ 运行时原子切换。
- **历史缓存**:已写成 `build_steps=null` 的旧记录定策略(重生成 / 版本失效 / 用户手动重跑),否则只救新请求、老页面仍"没变化"。`sqlite_paper_cache.py` 写入 / 读回迁移 / 完整性 / 旧 null / 生成版本键一并核。

### 九、提示词
- 一个字不动(PM 指令)。

## 不做(明确排除)
- ❌ 不修参数拼接 bug（`missing_parameter_value` 54% 误判)—— 单列下一张卡。
- ❌ 不改提示词。
- ❌ 不碰模型生成 / `.slx` 生成 / 通电 MATLAB —— 宪法划死。
- ❌ **不裸透草稿**:安全字段(C 类)照旧剥离;结构坏字段(B 类)局部降级;后端所有权字段仍盖章。
- ❌ 不硬 500、不白屏、不静默丢、不用宽 catch 吞非 JSON 错误。
- ❌ 本卡不等于上线;不宣称已优于 GPT(只求打平)。

## 与决策 27 / 29 收口
- **决策 27**:责任划线 / 草稿私有 `extra="forbid"` / 后端不读模型出处值 —— **全保留**。禁静默丢原则保留,后果从"判废清空"改"记日志 + 局部降级"。
- **决策 29 同步升 v0.2**:边界从"两分"精确为"三类"(内容放行 + 日志 / 结构局部防御 / 安全隐私照旧 enforce)。**安全隐私、结构完整性不属"内容判定",不在放行范围。** 决策 29 v0.2 与本卡一起落。

## 验收标准
- `make check` 全绿。
- **确定性测试(逐类)**:
  - 内容规则命中 → build_steps / guidance **非空** + 日志有子码。
  - 结构坏字段 → 父级产物留、坏字段局部去、前端不崩。
  - 安全字段(`source_ref` 泄漏 / `user_supplied` 伪装 doc)→ **仍被剥离/拒绝,不外泄**。
  - 坏 JSON → 不 500、落 fallback、日志有子码;provider 鉴权 / 取消错 → **传播**,不被当内容 fallback。
  - **五阶段全回路**:生成当场非空的产物,写前 / SQLite 读回 / API 序列化后**仍非空**(不只测 service 返回)。
  - 前端:step 内部数组缺失/空 → 不崩;非空 build_steps 正常渲。
  - badge:后端未盖章 → 不显绿章(显"出处待核"或不显)。
  - 恢复入口:guidance `generation_failed` → 按钮亮。
  - **隐私哨兵**:生产日志 / DB / API 无参数值 / excerpt / 路径 / LLM 正文 / raw completion。
- **公共 schema export**:JSON schema **字节零 diff**;但行为契约("`generated` 须有 document evidence" / "terminal 须 guidance null")**有意变更,单独在契约文档标注**(别把"schema 零 diff"和"行为契约改了"混一起)。
- **验收分母指标**(N≥3 = 同论文、同模型、同配置至少三轮配对,报分布,不报单跑百分比):
  - `visible_build_steps_rate` = 前端实渲非空步骤卡轮数 / build_steps 生成机会数
  - `visible_guidance_rate` = 前端实渲 guidance 轮数 / guidance 调用机会数
  - `root_json_failure_rate` = 重试后根 JSON 仍不可解析次数 / provider 调用机会数
  - `item_degradation_rate` = 被局部降级 item 数 / 总 item 数
  - `content_rule_hit_rate` = 各子码命中数 / 对应规则机会数
  - `raw_to_product_retention` = 原始 completion 中模型语义 item 最终仍可见的比例
- **真机重跑 2410**:LLM 原文 vs 产品判定并排打印给 PM;给 `root_json_failure_rate` 一个数。
- **GPT 对照打印(四个分母读数)**:参数出处覆盖率 / 已盖章中定位正确率 / 无依据却标 `document_extracted` 比例 / `user_supplied` 误标 doc 比例。**本卡只求打平,不宣称已优于 GPT**。
- PM 确认"出东西了、是 LLM 原文、假章没了"—— 本卡才算 done。

## 风险与注意点
- ★ **最大风险(两审独立同指)**:把私有 `source_ref` / 引用完整性 / 状态不变量 / 安全红线误归"内容层"一起放行 —— 结果不再清 null,却把未核来源包装成已验证证据,或在持久化/前端边界重新崩。**三类分类 + 分支处置表就是防这个。**
- ★ **假放行**:只改生成期,读回 / lifecycle / schema 再清 → 五阶段必须同步。
- ★ **放行救什么不救什么**:LLM 抽错/编的(0.0006)原样出现,靠内测收,**不是 bug、不是回归**。
- ★ **部署非原子**:同 PR ≠ 运行时原子切换;按兼容矩阵 + 顺序 / flag。
- ★ **老缓存不自动复活**:定重生成/失效策略,否则老页面不变。
- Codex 上下文:Stage 0 处置表 + 后端五阶段 + 前端 + 日志 + eval 若一会话吃不下,可拆块,但**后端五阶段必须一致、前后端不留白屏窗口**。

## 估时
Stage 0 分支处置表(小,先做,架构师签字)→ 实施(后端五阶段 + 前端 + 日志 + eval + 部署/缓存)待处置表定后再估。

## 给 Codex 的提示
- **Stage 0 只出处置表、不改码**;逐分支标 `content` / `structure` / `security`,**禁一刀切 bypass 整个函数**。
- **判断分类**:内容(证据够不够/对不对)→ 放行 + 日志;结构(引用完整性)→ 局部降级留父级;安全(泄漏/伪装)→ 照旧剥离。分不清的**列出来问**。
- **只改生成期 catch = 假放行**;读回 / lifecycle / schema / API 序列化必须同步。
- guidance validator 是**改写返回不是抛错**,改返回逻辑不是改 catch。
- 日志 / 横幅 / badge 是正经交付:日志带隐私哨兵;badge 无真盖章不显绿;横幅就一句「这是 AI 生成的搭建建议,仅供参考」。

## 附录:实施 Stage 0 分支级处置表(R6 格式,架构师签字后进实施)
每条分支一行:
```
path::function::branch
当前输入产物
规则名 + 现有子码
分类(content / structure / security)
当前后果
清空了哪个字段/对象
是否已持久化
前端连带
新后果
保留/剥离的最小粒度
日志子码与允许字段
确定性测试名
```
**最低覆盖集合**:`source_ref` 未命中 / evidence 白名单 / parameter + redline / 冲突守门 / `depends_on` + block 引用完整性 / guidance 语义 validator / `document_evidence_unverified` / requirement + gap reducer / 写前 integrity / SQLite 读回 / 前端 fallback / guidance 恢复入口 / eval recorder。
