# TASK-528-B · 建模指导细化层生成(后处理)· 定稿 · 派 Codex 实现

> **入库路径**:`docs/tasks/task-528-b-v0_6.md`(复数 `tasks`)。
> **状态**:v0.6 经两轮双审(R1 GPT 设计审 + R6 Codex 可落核)+ R6 终轮轻核收敛;本定稿 = v0.6 + 补参触发重算必做项 + Codex 落地提醒并入实现说明。**可派实现。** 全线最要死守"不编造"的一张,亲核从严。
> **不改** 已合的 528-A `build_guidance` 契约形状;仅 additive `guidance_status`(R6 坐实:additive 进 `plan_json`,**不 bump v9**,`CURRENT_SCHEMA_VERSION=8` 不动)。
> **分工**:本卡 = 生成 + 证据/grounding gate + 分级失败 + 后端确定性缺口合成 + `guidance_status` + 派生生命周期 + 生成当场最小防编造阀门。穷尽语义硬门在 528-C;渲染在 528-D;05(用户文案/标签)+ eval 在 528-E。**本卡产物暂不渲染。** 合并顺序:528-C 先于 528-D。

## 实现工作流(先读)
- **Stage-0 先 `git fetch origin` 复核**:确认 528-A 已合(`build_guidance` 恒 None)、507-A/B/508/522-D1/526-B/525/526-B as-built 与本卡一致;不一致**停手报架构师**,别硬改。
- **真机 E2E 从严**(命门卡):从 **repo 目录**起(`.env` 有可用 `DEEPSEEK_API_KEY`、`AppSettings` 自动加载,**无需再要 key**;只看 shell `$env:` 会误判缺 key),存储落**临时库/内存、不污染本地 `data/mxa.db`**,全程**不回显 key**;LLM raw / 失败 partial **不落库**。
- **PR 全走 PM 网页侧**:你只 push 分支 + 给 PR 标题/正文/`pull/new` 链接,**PM 建 PR + squash**;你**不自建 PR、不登录、不合并**。
- **代码 PR 不碰 `03_TASK_INDEX.md`**(决策 07):索引单独 closeout PR,合并后 PM 补;**别动那 361 行旧状态块**。
- **改文本文件保原始字节**(决策 08):禁 `read_text`/`write_text`/`sed -i` 式整写,按行 patch。
- 完工报告须含 §9 全部亲核项;任何与本卡的偏差**先报、待架构师核**,别自行决断。

## 0. 定稿相对复核版 v0.6 的增补
- **【必做·实现坑】补参按钮不得空转**:系统判"要不要重算"现靠"有无 correction 记录(`_has_regeneration_work()`)";而 `paper_user_supply_service`(补缺失参数)**不产生 correction、也不清 build_steps** → 该函数可能返回 false → 补参后 guidance 标过期、用户点"重新生成"却 `regenerate_nothing_to_do` **空转哑火**。**修法**:让 `stale_pending_regeneration` 状态本身能触发重算,**或**给 guidance 单开重生成入口;不得只看 correction 记录。归实现必做,非新产品决策(§7)。
- **Codex 落地提醒并入实现说明**(证据池桥补口、`ParameterMapping` 回溯保守点、纯显示步骤排除按 block 类型、连接对象 key 防撞、lifecycle helper 挂点、重生成入口)——见各节 **[R6 落点]** 标注。
- **【验收死盯】**唯一剩余 `no_document_basis` 误判面:真论文但**抽取根本没提出任何 document claim 且证据池空/不关联**(扫描/图片型 PDF、依据只在表格/公式图/Simulink 截图、低质 PDF 泛化文本、`parameter_mapping` 换算值无合法 evidence)。raw-counter 护栏已把"有主张但解析失败"导向 `generation_failed`,危险面窄但非零 → 实现须拿多篇此类真论文**逐篇亲核**(§8)。

---

## 1. Stage-0 与不升版本
- `guidance_status` additive 进 `plan_json`(默认 `not_generated`)+ 本卡新机制(`GroundingTruthIndex`、缺口合成、`build_guidance_lifecycle`、冻结快照、`guidance_view_state`)全落 `plan_json`/服务层纯函数/写前校验/前端状态解释 → **不新增表/列 → 不 bump v9**。
- **[R6 已坐实] 决策 13 同步面(全集)**:domain dataclass(`ModelGenerationPlan.guidance_status`)· Pydantic(字段/Literal/to·from_domain)· `scripts/export_paper_schemas.py` 重导出 · `schemas/paper_plan.schema.json` **与** `schemas/paper_rerun_plan_response.schema.json`(两个)· `tests/.../test_paper_schemas_freeze.py`(字段序/默认/Literal/roundtrip)· `tests/.../test_paper_schemas_sample_roundtrip.py` · 枚举边界测试 · `docs/06_OUTPUT_CONTRACTS.md` · `web/src/lib/paperTypes.ts` · 两个 golden(`.../material_to_plan/.../expected_model_generation_plan.json` + `.../missing_param/.../expected_updated_plan.json`,补默认 `not_generated`)。测试影响外溢到 API/storage/service/stale 样例,但**契约同步文件不新增**。
- schema 仍允许 `overall_status="reproducible_ready"`;**生成器/评级纯函数须自禁产出**(§4)。
- 落点:`build_steps is not None` 成功后,build_steps try/except **之外**(`assembled_plan` 后、return 前)。

## 2. 落点与输入
- 新建 `features/paper/build_guidance_generator.py`,不扩 `build_step_planner`。
- 输入 = `build_steps` 骨架 + **扩宽证据池**(经私有 handle 暴露)+ `library_choice`(仅助一致性、不作可复现真值)+ `block_recommendations` + `parameter_mapping`。
- **[R6 落点] 证据池桥补口**:现桥 `build_plan_evidence_source_refs()` 只覆盖 `PaperSpec.evidence` + equation/figure;**须补** `ModelGenerationPlan.evidence` + `block_recommendations.paper_reference` + `build_steps[*].evidence` + `build_steps[*].block_refs[*].paper_reference` + `configuration_hints.evidence`。**须另建 guidance 专用取证 renderer**——现有 `_plan_evidence_sources_json()` 会输出 `document_id/locator` 且被 build_steps prompt 使用,**不得全局改坏 build_steps 输入**;guidance 侧只暴露"handle + 摘要"。`parameter_mapping` 无直接 evidence 字段,只能经 `source=document_extracted` + name/value/unit 回溯到合法 `PaperEvidenceEntry`,**回溯不到即不作 document 真值**。统一去重发私有 handle。

## 3. 生成规则

### 3.1 证据 handle gate + grounding gate(白名单化)
- 后端把扩宽证据池做成 evidence cards(摘要 + 私有 handle,**不含 `document_id`/locator**)。复用 `PlanEvidenceSourceRef`/`build_plan_evidence_source_refs()`/`apply_plan_evidence_reference_bridge()`/`EvidenceTagger.validate_for_spec()`。
- LLM 草稿 DTO(私有,逐单元独立):`GuidanceDetailDraft`(step_id·detail_kind·basis·claim_text·supporting_evidence_refs[handle]·convention_code+target·confirmation_reason_code(白名单)+target+direction_hint);`GuidanceGapDraft`(gap_kind·scope·step_id?·gap_reason_code)。
- 后端解析 refs → 唯一出处 → 注入 `PaperEvidenceEntry`;无法解析/不属当前池 → 弃。
- **`GroundingTruthIndex`(白名单,只四类)**:① `PaperSpec` 已过 `EvidenceTagger.validate_for_spec` 的项;② `ParameterMapping` 中 `source=document_extracted` 且回溯到合法 `PaperEvidenceEntry` 的项;③ `BlockRecommendation.paper_reference` 已 resolved;④ `build_steps[*].evidence` 已 resolved。**禁止** `display_text`/`library_choice`/raw `build_steps` 字段/LLM 生成摘要/未 resolved 引用作真值(防"AI 拿自己编的东西自证"闭环污染)。**[R6] 四类 resolved 状态均有现成校验基础**(`EvidenceTagger.validate_for_spec` / `validate_build_step_evidence_for_spec`);`ParameterMapping` 回溯是唯一保守点。
- **grounding gate**:`document_extracted` 的 `claim_text` 中高危 token——数字+单位/参数名值/库路径/block type/端口/连接端点/solver/采样时间/toolbox 变体,**+ 非数值工程决定词**(anti-windup/限幅/离散·连续/微分滤波/缩放/相序/角度来源/PWM/器件类型/控制器变体)——须逐项在 `GroundingTruthIndex` 命中;**命中前做最小 canonicalization**(空格/全半角/常见单位别名/LaTeX 符号/大小写,防 `5 kW` vs `5kW` 等误伤薄论文;**命不中仍降级,不为召回牺牲安全**)。
- **document_extracted 无 ≥1 合法 resolved evidence,或过不了 grounding → 降 `user_confirmation_required`,不复用原 claim_text**,改后端模板"这步需确认 X;论文证据未核实,请查 Y"。与 §6 护栏配合:**"有主张但 resolved/grounding 为零"落 `generation_failed`,不落 `no_document_basis`**。

### 3.2 三档判据
- **document_extracted**:仅论文明确给出;必挂合法 resolved evidence;**过 grounding gate**;值/单位/连接/库路径不得推断补。
- **engineering_convention**:只准 §3.3 白名单;后端模板、LLM 不自由写正文。
- **user_confirmation_required**:依赖版本/工具箱/库块变体/精确参数/采样时间/solver/初值/开关频率/仿真时长/接线细节者;模糊项默认落此。`confirmation_reason_code` 走白名单绑模板;**`direction_hint` 只说"取决于什么/往哪查",禁任何数值+单位/精确库路径/端口/solver/采样时间/toolbox 变体**(除非来自合法 document evidence);禁空占位"待确认"三字。每 reason code 配正反例单测。

### 3.3 convention_code 白名单 v1 + target 受控
detail 级:`pi_controller_standard_structure`/`pid_controller_standard_structure`(只允许误差求和 + P/I(/D) 环节;禁 anti-windup/限幅/离散/微分滤波/变体);`clarke_transform_structure`/`park_transform_structure`(拆开;只允许基础结构;禁缩放/相序/角度来源/库路径/端口;**默认 notice_only 或 blocked_pending_confirmation**,除非 document evidence 给出关键工程决定)。gap 级(无 convention_code):`basic_measurement_gap`/`basic_display_gap` → `missing_support_component`、后端 warning、notice_only。
- **target 受控**:优先受控引用(step_id/block_ref_id/parameter_ref/后端 label);文本须过硬过滤。
- **白名单外不走 convention**;**电源/逆变器/主功率器件/物理 plant 缺失 → confirmation 或不生成,绝不 convention**。扩单门槛:允许/禁止句式 + ≥2 正例 + ≥3 反例(**含 3 类 target 反例**:数值单位 / 库路径端口 / solver·采样时间·toolbox 变体)+ allow/denylist 单测 + 真实论文抽查。

### 3.4 缺失整块 vs 子系统展开
子系统内部标准展开 → `GuidanceDetail`(subsystem_internal_structure,convention,actionable);缺失整块 → 只进 `GuidanceGap`(notice_only),不进正文、不占位、不代填。

## 4. 后端确定性评级(内部)+ 对象粒度缺口合成
**评级不上屏**:`compute_guidance_assessment` 仍算(确定性、保守、**绝不 `reproducible_ready`**),但只作**驱动缺口合成 + telemetry** 两用,**不渲染为用户可见徽标**(`GuidanceAssessment` 仍在契约、不删,528-D 不渲染)。
- **critical_step**:build_steps 中**真放模块/真设参/真连线/真配置**的步(有 block_refs/parameter_refs/connection_hints/configuration_hints),**排除纯显示/测量辅助步**。**[R6] 排除不能只看字段非空**,须按 block type/purpose/library_path allow/denylist 判。
- **对象粒度确定性缺口合成(不信 LLM 报)**:逐 critical step 按**对象 key**核 document 覆盖——`block_ref_id` / `paper_param_name+model_param_name` / `from_block_ref+to_block_ref+signal_meaning` / `configuration target+setting_name`;缺任一对象 → 经 `GapSynthesisRule` 表合成对应 `GuidanceGap`。**[R6] connection key 若 `signal_meaning=None` 或重复连接,须加 ports/序号防 key 碰撞。** 每个 critical step 上 `blocked_pending_confirmation` detail → 同步合成一条 blocking gap,`blocking_gap_ids` 只引这些 gap。
- **`GapSynthesisRule` 固定表**:输入 `missing_object_kind + criticality + step_category + target_kind` → 输出 `gap_kind + basis + severity + template_id`;**severity/basis 一律走此表,LLM 不定**。
```
if blocking_gap 存在:            content_status = outline_with_gaps
elif 每个 critical_step 每一 required 对象 key 都有 document 覆盖 且无 critical user_confirmation_required:
                                 content_status = reproducible_candidate
else:                            content_status = outline_only
environment_status = not_checked;overall_status = candidate?→candidate_env_unchecked : content_status
```
(以上 status 仅内部/telemetry,**不上屏**;上屏的是每步缺件 `GuidanceGap` + 每条 basis 标签。)

## 5. prompt
- 新 `core/prompts/*.yaml` 带 `version`;`_call_llm_json` 已 `json_mode`。结构:evidence cards → LLM 每 detail 先填 refs → 有 refs 且过 grounding 才 document_extracted → 无 refs 只能白名单 convention 或 confirmation → 不确定必 confirmation(白名单 reason code + direction_hint 只说往哪查)。
- 一条 detail 一原子 claim;逐单元列表;不要求 LLM 产评级/severity/缺口/用户文案。
- 反例进 prompt+单测:补充值伪装文档证据;文档证据无 locator/摘录;convention 夹带/ target 注入;claim 越出证据(grounding 反例,含非数值工程决定词)。

## 6. 失败处理:分级救 + 诚实终态 + 护栏 + 上限
输出 = 独立 detail-draft + gap-draft 单元。终态是诚实报错/告知、**不是裸卡**:
1. **单元级宽容解析**(决策 17):截断只丢尾部、保住前面;单个坏结构/非法枚举/未知 step_id → 只丢那条。
2. **单元级 fail-closed**:无合法 evidence / 过不了 grounding → 降该条 confirmation(模板文案、不复用原 claim);convention 硬过滤/非法 code/target 注入 → 丢或降那条。都不整份丢。
3. **部分重跑(带上限)**;4. **整份崩 → 稳定骨架上整份重跑(带上限)**,不立即终态。
5. **诚实终态地板**:
   - 重跑上限耗尽仍不可解析 → `generation_failed`(可重试)。
   - **`no_document_basis` 护栏——只看 raw counters + 池构造状态**:解析 draft 后**立即**记 `raw_document_claim_count`/`raw_supporting_ref_count`/`resolver_error_count`;仅当「两轮 `raw_document_claim_count=0`」+「evidence 池空/无 build_steps 关联」+「`resolver_error_count=0` 且无构造错误」才落 `no_document_basis`;凡"raw 有 document claim 但全 resolver/grounding 失败 / 有 resolver error" → `generation_failed`(记 `evidence_resolution_failed`/`evidence_card_unavailable`)。**严防"先降级、再数零、误判没依据"。**
   - 两者都不回退裸卡、都不误伤 build_steps 骨架;**≥1 document_extracted 一律照常出**。
- **[R6] 上限细则**:参考 `structured_retry.py` 的 call cap/wall-clock/hint 思路,**guidance 独立 retry context/adapter**,不动 526-B 主体、不污染 upload job summary;单元补跑 ≤N / 整份 ≤M / 总 LLM call cap / wall-clock;按 `step_id+detail_kind+basis+target` 去重;超 cap → `generation_failed`,**不持久化 partial guidance**。

## 7. 派生生命周期 + 统一 helper + 五态 + 红线

### 修订不变量(过期态按动作分;`build_guidance_lifecycle.py` 统一强制)
```
generated                  → build_guidance 非空 + len(details)≥1 + ≥1 document_extracted
stale_pending_regeneration → 改参数路径(correction/user_supply)→ 保留旧 build_guidance(冻结快照,只显示自身 display_text)
                             重生成步骤路径(step_regeneration)   → build_guidance=None
generation_failed / no_document_basis / not_generated → build_guidance=None
```
消费者**一律经 `guidance_view_state(plan)`**(current / stale_with_snapshot / stale_empty / failed_retryable / no_basis / not_generated);**禁止 `build_guidance!=null` 直接判显示**。**[R6]** 前端目前几乎不真实消费 `build_guidance`(仅 TS 镜像),收敛阻力低;freeze/TS/route 加 stale 非空样例。

### 冻结快照语义
保留的旧 guidance **只显示自身冻结 `display_text`**,**不从当前 build_steps 派生正文、不把旧 detail 重 join 到当前步骤文案**;旧内容 read-only。**correction 现状清 build_steps 不用动**——冻结快照自带文字、`build_steps=None` 时仍合法可显示、`guidance_view_state` 判 `stale_with_snapshot`(R6 坐实形状已允许 `build_steps=None` 且 `build_guidance` 非空)。

### 派生作废(与之前有没有指导无关;默认不自动重跑,只置过期)—— [R6] 坐实落点
- `paper_parameter_correction_service`(apply/undo,现清 m_script/build_steps、不清 build_guidance)→ 加 `guidance_status="stale_pending_regeneration"`、**保留旧 build_guidance 冻结快照**。
- `paper_user_supply_service`(**现漏清派生物——必补**)→ 置过期、保留旧 build_guidance 冻结快照。
- `paper_step_regeneration_service`(step_id 可能变)→ 置过期、`build_guidance=None`。
- `paper_reparse_service`(整包替换)→ 新 plan `not_generated`。
- **★【必做】"重新生成"触发条件**:重生成入口挂在 `paper_step_regeneration_service._replace_regenerated_artifacts()` 后、写库前(该服务在有 corrections 或 `build_steps is None` 时用纠正后 `parameter_mapping/evidence` 重跑 build steps + guidance)。但 **user_supply 不产生 correction、`_has_regeneration_work()` 可能返回 false → 补参后点按钮会 `regenerate_nothing_to_do` 空转**。**须让 `stale_pending_regeneration` 状态本身触发重算,或单开 guidance regenerate 入口**;改参数场景 = 连 build_steps 带 guidance 一起重算。**增量重跑后置。**

### 五态 UI 语义(供 528-D;本卡定语义、不渲染)
`generated`→显示指导(每条 basis 标签 + 每步缺件);`generation_failed`→可重试;`no_document_basis`→诚实终态;`stale_with_snapshot`→显示旧冻结快照 + "基于旧参数、可重新生成"横幅 + 按钮;`stale_empty`→"步骤已重新生成,请重新生成指导" + 按钮;`not_generated`→隐藏或"尚未生成"。**任何状态绝不露裸步骤卡;绝不显示用户可见总评级徽标。**(用户可见文案/标签全归 05/528-E 定死、LLM 不生成;含过期横幅"检测到参数变更。此指导基于旧参数,重新生成以与当前配置保持一致。"+ 按钮"重新生成指导"。)

### 红线 / 不做
- **fail-closed 独立于 build_steps**:try/except 外独立跑;**绝不抛 `BuildStepsStructuredError`、绝不调 `_log_build_steps_fallback()`、绝不落 partial**;build_steps 逐字节不变。
- **绝不以裸 build_steps 冒充指导产物。**
- 红线复用按 basis 区分:document_extracted 允许带证据的参数值;convention/confirmation 禁值;**不无脑套 build_steps"步骤文本禁值"**。
- 本卡不做:存储/历史版本/用户纠正持久化(后置);增量重跑(后置);不改 build_steps 生成/校验/派生/fail-closed;**不改 correction 清 build_steps 现状**;不改 526-B 主体;不改既有 prompt;不渲染(528-D);穷尽语义硬门(528-C);05 用户文案(528-E);不 bump v9(guidance_status additive 除外)。
- **[R6] `build_guidance_lifecycle` 挂点**:`normalize/validate/mark_stale`,在 plan 写回前 + SQLite `_dump`/`_load_with_nested_evidence_migration`(`adapters/storage/sqlite_paper_cache.py`)+ Pydantic `from_domain/to_domain` 统一调用;旧 blob 缺 `guidance_status` 默认补 `not_generated`。
- 脱敏(决策 11):LLM raw / 失败 partial 不落库;telemetry 机器码(`details_by_basis`/`critical_step_count`/`critical_steps_fully_covered`/`critical_user_confirmation_count`/`synthesized_gap_count`/`gaps_by_kind`/`blocking_gap_count`/`assessment_*`(内部)/`guidance_status`/`guidance_failure_reason`(含 `zero_document_claims_empty_evidence_pool`/`zero_document_claims_unlinked_evidence_pool` 两 no_basis 子码 + `llm_unparseable`/`evidence_resolution_failed`/`retry_cap_exhausted`/`build_steps_unavailable`)/`guidance_retry_count`),**不塞值/单位/原文/路径/claim**。

## 8. 验收(从严——真机 + 亲核)
- **真机 E2E 多篇真论文**(repo 目录起、临时库、key 不回显):
  - 证据 gate + **grounding 白名单**:document_extracted 确有 resolved evidence 且 claim 不越界;夹带假值(含非数值工程决定)被降/弃且降级后**不残留原句**;**grounding 真值只取白名单四类**,不吃 display_text/library_choice/未 resolved 引用(闭环污染验)。
  - **归一化不误伤**:`5 kW`/`5kW`、`0.2 s`/`0.2s`、中文单位、科学计数法合法证据能命中、不被过度降级。
  - **证据解析故障注入**:handle resolver 全/部分失败、handle 不属池、document_id 越界、locator 缺失/非法、池空但 draft 有引用 → **不得落 `no_document_basis`**,应 `generation_failed` 或单条降 confirmation,记内部 reason。
  - **no_basis 只看 raw + 真论文亲核**:raw 有 document claim 但全 resolver/grounding 失败 → generation_failed 或 generated-with-confirmation,绝不 no_document_basis;**★ 死盯:多篇"抽取没提出任何 document claim 且池空/不关联"的真模型论文(扫描/图片型、依据在表格/公式图)逐篇亲核不误落**;非模型论文/纯理论 → no_document_basis 终态。
  - **薄论文照常出**:≥1 document_extracted → 出,**无总评级徽标**;缺件按该步 gap 如实列。
  - **对象粒度缺口/评级(内部)**:两参数覆盖一个 → 补另一个 gap;纯显示/测量步骤按 block 类型排除、不误判为建模缺口;connection key 无碰撞;synthesized gap severity 走固定表、不由 LLM;同输入内部评级一致。
  - **过期按动作(stale 回归,≥3 例)**:① 纯补参 → `stale_with_snapshot`(冻结快照 + 横幅 + 按钮、不自动重跑)、**点"重新生成"确实重算(不 `regenerate_nothing_to_do`)**;② 重生成步骤 → `stale_empty`(提示 + 按钮);③ correction 清了 build_steps → 冻结快照**照常显示**、按"重新生成"连步骤带指导重算贯通。作废与原状态无关(含 no_document_basis 后重解析);`user_supply` 漏口已补。
  - 待确认有方向且无数值;convention 只补结构、Clarke/Park 非 actionable(除非有据);电源/逆变器不走 convention。
  - **消费端 status-aware**:无处用 `build_guidance!=null` 直接判显示;`guidance_view_state` 六态齐。
  - 脱敏:telemetry/落库无敏感值。
- **契约/同步**:`guidance_status` 统一 validator 强制五态不变量;additive、旧 plan 默认 `not_generated`、round-trip;决策 13 全清单(§1)同步且绿;freeze/TS/route 含 stale 非空样例。
- `build_steps` 链**逐字节无 diff**;现有测试套件全绿;新增本层 + 评级/缺口合成纯函数 + `GroundingTruthIndex` + 硬过滤 + 分级失败 + 重跑上限 + `build_guidance_lifecycle` 五态 单测。
- **PR 走 PM 网页侧**;代码 PR 不碰 `03_TASK_INDEX.md`。

## 9. 交接给架构师(完工报告需含,逐项亲核)
- **关键 diff**:证据池扩宽(+桥补口、guidance 专用 renderer 不动 build_steps 输入)· `GroundingTruthIndex` 白名单四类 · 非数值高危词 + 归一化 · no_basis raw-counter 护栏 · 对象粒度缺口 + `GapSynthesisRule` 表 · 评级转内部不上屏 · 过期按动作(冻结快照 / `stale_empty` / **补参触发重算不空转**)· `guidance_view_state` · `build_guidance_lifecycle` 统一 · 四处作废(含 user_supply 补口)· `guidance_status`。
- **真机证据**:grounding 白名单拦假值(含闭环污染)· 归一化不误伤薄论文 · 故障注入不误判 · no_basis 只看 raw + **多篇扫描/图片型真论文逐篇亲核不误落** · 真模型论文不误落 · 薄论文无总评级照常出 · 过期三例(含补参按钮真重算)· 消费端无裸 null 判 · build_steps 无 diff · 脱敏抽查。
- **确认**:build_steps 链 / 526-B 主体 / correction 清步骤现状 / 既有 prompt **无 diff**;`guidance_status` additive **不 bump v9** 结论 + §1 同步面每项 diff。
- 与本卡任何偏差(说明,待架构师核)。
