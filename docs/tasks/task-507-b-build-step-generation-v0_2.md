# TASK-507-B:结构化建模步骤 · 生成 + 校验 + 降级 + 红线机检(让后端真生成 build_steps)

**版本**:v0.2(R1 + R6 双审「条件通过、不升 R2、不拆卡」→ 并意见定稿候选;PM「已定/不同意再说」口径过后派单 Codex 实现门,Stage 0 兜底)
**所属线**:paper-to-model(decision 22 5xx;指导深度子线 506 RFC ✅ → 507-A 契约 ✅ →【507-B 生成】→ 508 前端 → 509 真实语料评测)
**前置**:506 v0.3 定稿(绑定规格)+ 507-A(契约 substrate 已合 main,`build_steps` 端到端恒 None)
**现状基线**:Codex 取证 origin/main HEAD `d324591`(507-A 契约 + 索引收尾均在;paper 生成链如下「现状」节,逐字实测属实)+ R6 复审实测;**派单后 Codex Stage 0 复核最新 HEAD**

---

## 本版改动(v0.1 → v0.2,并审而来)
**P0(必改,两审独立同挑)**
- **[P0-1]** `_llm_build_steps` **不直接用** 507-A 的 `ModelBuildStepModel` 解析 LLM 原始输出(该 DTO 与 domain 的 `display_text` 均**必填**,而本卡要求 LLM **不输出** display_text)。改用**私有 draft DTO**(`_BuildStepsOutputModel` / `_ModelBuildStepDraftModel`,无 display_text,`extra="forbid"`,`build_steps` 长度 3–10),解析后由 assembler 派生 display_text 再构造 507-A 正式 domain/DTO。`build_steps == []` 在 `_llm_build_steps` **入口即判结构化失败**(不只靠覆盖度兜)。
- **[P0-2]** 新增**结构化失败异常族** `BuildStepsStructuredError`(+ 子类),钉死错误分层;service **单点 catch** 它走 legacy,真异常一律上抛;`_call_llm_json` 在 build_steps role 下的 JSON 失败归结构化失败,provider/IO/auth/quota/rate/server/timeout/serialization/fixture/Cancelled/**legacy fallback 自身失败**一律上抛(case_failed);并发 gather 不取消/不丢 `_llm_missing_detect` 结果。
- **[P0-3]** 生成期 build_steps 证据**禁止伪造 `user_supplied`**:`validate_for_spec` 对 user_supplied 只查形状(有 prompt_id),**不等于**关联 resolved prompt;初始生成阶段无 resolved record,故新增私有 helper `validate_build_step_evidence_for_spec(evidence, spec, allowed_user_prompt_ids=frozenset())`,**初始生成传空集 → user_supplied 一律 fail(降级)**;对 step.evidence / 非空 `block_refs[*].paper_reference` / `configuration_hints[*].evidence` 都走它。

**P1(应改)**
- **[P1-1]** `block_ref_id` **全局唯一**(校验);`connection_hints` ref 须在「本 step ∪ 依赖闭包可见」中**恰好命中 1 个**(原「步内唯一」不足以消歧跨依赖引用)。
- **[P1-2]** BR-xxx 匹配定成**确定性算法**:BR key 按 PlanComposer 数组序生成;匹配主键 = `normalized(block_type, purpose)` exact;该 pair 在 recommendations 重复 → 结构化失败;**locator 不入匹配键**(`StepBlockRef.paper_reference` 可空,入键过脆;paper_reference 另走证据校验)。`normalized` = trim + 折叠内部空白 + casefold。
- **[P1-3]** 红线 `configuration_hints` 例外**加 allowlist + 反查**:例外仅当 `target ∈ {solver,powergui,simulation}` **且** `setting_name` 不命中任何 `parameter_mapping` 参数名;否则按普通步骤文字红线检。规则 ① 扩成「也查 `value` 规范化数字/单位 token 在文字中**裸出现**」(allowlist 配置值除外),堵「0.05 ohm 不带参数名」绕过。
- **[P1-4]** #10 拆两可测点:① `subsystem_breakdown` **字节级**等于 `[display_text]`;② display_text 派生**白名单模板**(只允许 step_id/title/intent/block_type/purpose/param 名/signal_meaning/config target+setting_name;**禁 dereference** `parameter_mapping.value/unit`、禁引入 evidence excerpt)。
- **[P1-5]** #11 覆盖度定义 **dedupe(同 BR key)** + 空 recommendations **vacuous pass**;「无 optional 标记 → 全推荐必覆盖会抬高降级率」写进风险。
- **[P1-6]** 降级护栏:① **reason-coded metadata-only 降级日志**(reason_code 枚举,不记正文/token/原始输出,照 decision 11);② service 级**防全量退化 gate**(fake provider 跑完整 generate,断言 build_steps 非空 + subsystem_breakdown 派生 + **legacy 没被调**)。
- **[P1-7]** 私有 DTO **放 `paper_plan_service.py`、不进 schema export**(R6 实测 exporter 是 alias-based,只导出 `OUTPUTS` 指定 alias,私有 model 不入即零 diff)。
- **[P1-8]** eval harness **R6 实测 = live true run(DeepSeekTextProvider)+ 规则指标**(c2 block_type 覆盖 / c3 非 sentinel 参数名覆盖 / mscript shape,**不看 build_steps**):本卡**保持 golden `build_steps=null`、不改 golden、不改 sample roundtrip 测试、不改 verdict 规则**(全留 509);`structured_status` 由 `plan.build_steps is None` 可 derive(509 接);只更新 eval case README 注解避免误导。

**文档修正**
- 校验职责切分:assembler 做结构/红线/派生(规则 1–7、9–11),service 做证据(规则 8)+ 接结构化失败族;assembler 保持 **pure**(不注入 spec/validator)。
- 结构化 role_name = `build_step_planner`;legacy 保留 `subsystem_planner`。
- 「`validate_for_spec` 关联真 prompt」过度表述 → 改为实际/新 helper(见 P0-3)。
- **行尾/字节级保留 = decision 08**(原 v0.1 跟交接包误写 20;经读真文件核实,decision 08 即「保留原始字节」,decision 20 与本卡无关)。异步 + 日志禁令 = decision 11。

---

## 现状(Codex 实测 origin/main d324591 + R6 复审,本卡设计依据;R1 当真)

1. **SubsystemPlanner**:`core/prompts/paper_plan_subsystem.yaml` v0.1 输出 `{"subsystem_breakdown": ["第1步:…", …]}`(纯文字 list、3–10 步、反例已含「步骤不准写参数数值」)。`_llm_subsystem_plan(...) -> list[str]`:`_call_llm_json`(最多 2 次 JSON parse 重试)→ 校验「是 list / 长度 3–10 / 每项非空 str」,语义不符直接 `raise PaperPlanGenerationError`。
2. **生成 DAG**(`PaperPlanService.generate`):`gather(_llm_plan_compose, _llm_mscript_draft)` → 取 sentinel_mappings → `gather(_llm_missing_detect, _llm_subsystem_plan)` → `PlanAssembler.merge(...)` → **3 处** `evidence_tagger.validate_for_spec`(`plan.evidence`、`block_recommendations[*].paper_reference`、`missing_prompts[*].paper_reference`)→ 返回。`_llm_plan_compose` 强制 `subsystem_breakdown == []`;`_PlanComposerOutputModel` 无 `build_steps`,`to_domain` 走 domain 默认 None。
3. **PlanAssembler.merge**(`features/paper/paper_plan_helpers.py`):只做 `replace(...)` 改 plan_id/paper_spec_id/subsystem_breakdown/m_script_skeleton + 生成 missing bindings;**现无步骤语义校验 / block ref 校验 / display_text 派生**(仅 `missing_binding_not_found` / `_ambiguous`)。
4. **结构字段**:`ParameterMapping(paper_param_name, model_param_name, value: str, unit: str|None, source)`;`MISSING_VALUE_SENTINEL = "null"`。`BlockRecommendation(block_type, purpose, paper_reference: PaperEvidenceEntry)` —— **无 id/ref key**。两者**现无复合键唯一校验**。
5. **EvidenceTagger**(同文件):`validate_for_spec` 查 `_validate_source_invariants`(DOCUMENT_EXTRACTED 须 locator + excerpt≤300 + 无 prompt_id;USER_SUPPLIED 须无 locator + 无 excerpt + 有 prompt_id)+ locator 白名单;`validate_for_record` 才额外查 user_supplied 关联 **resolved** prompt。**现未送检** `build_steps`/step block paper_reference/config evidence。
6. **legacy 降级源完好**:`_llm_subsystem_plan → list[str] → merge subsystem_breakdown`,不依赖 build_steps,507-A 后可独立产出。
7. **507-A 契约**:`ModelBuildStepModel` 等 5 个 strict DTO(`_StrictBaseModel`,`extra="forbid"`)+ `build_steps: …|None = Field(default=None, min_length=1)` 已在 main;`ModelBuildStepModel.display_text: str = Field(min_length=1)`、domain `ModelBuildStep.display_text: str` **均必填**(→ 见 P0-1 私有 draft DTO)。
8. **边界**:`TuningSuggestion`(`core/domain/paper_tuning.py`)只给方向枚举无数值;`_call_llm_json` JSON/DTO/语义失败都走 `PaperPlanGenerationError`、评测器 `isinstance(PaperPlanGenerationError|PaperUserSupplyError)` → `case_failed`(→ 见 P0-2);评测器 = `eval/run_paper_eval.py`(live DeepSeek + execution_status)+ `eval/_paper_eval_rules.py`(verdict;c2/c3/mscript shape,不看 build_steps)+ `eval/_paper_eval_csv.py`(双轴不变量);`export_paper_schemas.py` 的 `OUTPUTS` 仅 alias 导出(→ P1-7)。

---

## 本卡做什么(一句话)
让一个新角色 `build_step_planner` 真生成**结构化 build_steps**,经**私有 draft DTO** 解析、由 PlanAssembler 跑 **11 条校验(fail-closed)** + 派生 `display_text`(白名单模板)与 `subsystem_breakdown`,由 service 把新增 step 证据**送 generate-time 双源校验(拒伪造 user_supplied)**,并加**红线机检**;结构化任一环失败 → **专用异常族被 service 单点接住** → `build_steps=None` + 走 legacy 文本路径得 `subsystem_breakdown`;真 IO 异常才 `case_failed`。**不改对外序列化契约(复用 507-A),不做前端(508),不动评测 verdict/golden(509)。**

## 输入(前置依赖)
- 506 v0.3 绑定规格;507-A 契约(frozen 在 main)。
- 锁:红线 option A(论文带出处的值照常给、只拦瞎编/替填);`TuningSuggestion` 只给方向;不替用户填缺失值;双源证据不互伪(decision 21);改对外契约走 decision 13 全清单 + PM + R1。
- 必读:01 / 02 / 04 / 05 / 06 §12.5 / decision 08 / 11 / 13 / 21 / 22 / 25。

## 范围(必须做)

### 1. 结构化 `build_step_planner`(新增,不删 legacy)
- 新增**结构化 prompt** `core/prompts/paper_plan_build_steps.yaml`:输出 `{"build_steps": [ {step_id, title, intent, block_refs[…], parameter_refs[…], connection_hints[…], configuration_hints[…], depends_on[…], evidence[…]} ]}`;**不输出 `display_text`**(assembler 派生)。prompt 显式约束:① 步骤文字**不得含参数具体值/倍率/「推荐设为 N」**(红线);② `block_refs` **逐字复用**给定 block_recommendation 的 `block_type` + `purpose`(供 assembler normalized 匹配,见 §3 #5);③ 3–10 步、子系统/功能块级粒度;④ `depends_on` 只引前序 step_id;⑤ `block_ref_id` **全局唯一**、`connection_hints` 据其引用;⑥ evidence 只用 `document_extracted`(初始生成无 user_supplied,见 §3 #8)。
- 保留旧 `paper_plan_subsystem.yaml`(v0.1)与 `_llm_subsystem_plan(...) -> list[str]` **原样不动**,作为降级 fallback 源。
- 新增 `_llm_build_steps(...)`:`_call_llm_json`(role=`build_step_planner`)→ 用**私有 `_BuildStepsOutputModel`**(含 `_ModelBuildStepDraftModel`,无 display_text,`extra="forbid"`,`build_steps` `min_length=3, max_length=10`)解析 → `build_steps==[]` 或解析失败 = **结构化失败**(`BuildStepsStructuredError` 子类)。私有 DTO **放 `paper_plan_service.py`**(不进 schema export)。

### 2. 装配 + 派生(PlanAssembler,保持 pure)
- 新增 `validate_and_derive_build_steps(draft_steps, parameter_mapping, block_recommendations) -> list[ModelBuildStep]`(**不接 spec/validator**;证据校验在 service):跑 §3 **规则 1–7、9–11** → 全过则为每 step 按**白名单模板派生 `display_text`** → 构造正式 `ModelBuildStep`。任一失败抛对应 `BuildStepsStructuredError` 子类。
- 调用方(service)成功后:`build_steps` = 该返回;`subsystem_breakdown = [s.display_text for s in build_steps]`。
- **BR-xxx 引用键**:assembler 按 `block_recommendations` 数组序生成 `BR-001…`(确定性);匹配键 `normalized(block_type, purpose)`;**仅内部用,不进对外契约**。
- `display_text` **必须** assembler 派生;**严禁** LLM 直接给 display_text 或从其文字回灌结构(防三源漂移,506 §199)。

### 3. 11 条校验(fail-closed;1–7、9–11 在 assembler,8 在 service;语义照 506 §5)
1. `step_id` 唯一 + 格式稳定(如 `STEP-001`)。
2. `depends_on` **只引数组前序 step_id**(天然无环);乱序先拓扑排序再输出,排序后仍违反 = fail。
3. `parameter_mapping` 复合键 `(paper_param_name, model_param_name)` 唯一;每个 `parameter_refs` **恰好命中 1 项**(0 或 >1 = fail)。
4. `block_ref_id` **全局唯一**;`connection_hints.from_block_ref/to_block_ref` 在「本 step ∪ 依赖闭包可见 block_ref_id」中**恰好命中 1 个**(0 或 >1 = fail)。
5. 每个 `block_refs` 项**恰好命中 1 个 block_recommendation**(按 `normalized(block_type, purpose)` exact);recommendations 中该 pair 重复 → 结构化失败;**locator 不入匹配键**(paper_reference 另走 #8 证据校验)。
6. **每步至少 1 个可操作结构字段非空**(`block_refs`/`connection_hints`/`parameter_refs`/`configuration_hints` 之一);**`intent` 不算**。
7. **红线机检**(见 §5):受检步骤文字字段不得泄漏参数值/倍率。
8. **证据双源（service 执行）**:每 step 的 `evidence`、每非空 `block_refs[*].paper_reference`、每 `configuration_hints[*].evidence` 经新 helper `validate_build_step_evidence_for_spec(..., allowed_user_prompt_ids=frozenset())`:document_extracted locator ∈ PaperSpec;**user_supplied 一律 fail（初始生成无 resolved record）**。失败 = 结构化失败(降级,不 case_failed)。
9. `library_path` 非空仅作 hint(不校验可执行性);为空合法(508 显示「库路径待确认」)。
10. **派生一致 + 模板安全(两点)**:① `subsystem_breakdown` **字节级**等于 `[s.display_text]`;② `display_text` 只用白名单字段(step_id/title/intent/block_type/purpose/param 名/signal_meaning/config target+setting_name),**不 dereference** `parameter_mapping.value/unit`、不含 evidence excerpt。
11. **覆盖度**:`coverage_set` = dedupe(同 BR key) 后的 recommendation 集;非空时每项须被某 step `block_refs` 覆盖,否则 fail;recommendations 为空 → **vacuous pass**(但仍需 3–10 步 + 每步可操作字段)。

### 4. 错误分层 + 降级两态(fail-closed,对齐 decision 25)
**异常族**(钉死分层):
- 新增 `BuildStepsStructuredError`(+ 子类 `…JsonParse` / `…DtoValidation` / `…SemanticValidation` / `…RedLine` / `…Evidence`),**独立于 `PaperPlanGenerationError`**(理由:逃逸 = 布线 bug,应炸响,**不被评测器静默记 case_failed**;实现时 R6 核评测器若有 catch-all 须保证不静默吞它)。
- `_llm_build_steps` 把**本角色的** JSON/DTO 失败包成结构化失败子类;assembler 的 11 条(1–7、9–11)失败抛 Semantic/RedLine 子类;service 的证据(8)失败抛 Evidence 子类。
- service **只 catch `BuildStepsStructuredError`** 走 legacy fallback;**不得 catch** `PaperPlanGenerationError` / `Exception` / `ValueError` 宽类型;provider/IO/auth/quota/rate/server/timeout/serialization/fixture/Cancelled/**legacy fallback 自身失败**一律上抛(case_failed)。

**两态**:
- **正常**:结构化解析 + 11 条全过 → `build_steps` 非空 + `subsystem_breakdown` 派生自 display_text(**不调 legacy**)。
- **降级**:任一结构化失败 → `build_steps=None` → service 调 legacy `_llm_subsystem_plan` 得 `subsystem_breakdown`;**不从失败输出硬挤**。
- **fail-closed**:任一 step 失败 → **整个 build_steps 丢 None**,**绝不返回半截 list 或 `[]`**。
- **decision 25**:结构化失败→降级 = `execution_status=succeeded`(产出了 plan)+ verdict 由 **509** 据 build_steps 缺失判;**本卡不改 verdict 规则**。旧前端不读 build_steps,行为不变。

### 5. 红线机检(保守版,506 红线节)
- 受检步骤文字字段:`title` / `intent` / `block_refs[*].purpose` / `connection_hints[*].signal_meaning` / `configuration_hints[*].instruction` / `display_text`。
- 规则:① 对 `parameter_mapping` 中 `value != "null"` 的项,若「参数名 + 值」邻近出现,**或** `value` 的规范化数字/单位 token **裸出现**在受检文字 → fail;② 禁「增大/减小 N% / N 倍 / 最优 / 推荐设为 N」类倍率/调参表述。
- **例外**:`configuration_hints` 仅当 `target ∈ {solver,powergui,simulation}` **且** `setting_name` 不命中 `parameter_mapping` 任何参数名时,不受 ①② 约束(其 allowlist 配置值/单位不触发裸值检);否则按普通步骤文字检。**均不得伪造来源**。
- **display_text 白名单模板**(§3 #10②)使其**结构上**无法吐参数值/单位 —— 红线在派生侧即闭合。
- 机检失败 = 结构化失败 → 降级。

### 6. service 编排接线
- `generate` 第二阶段:`gather(_llm_missing_detect, _llm_build_steps_try)`,用 **return_exceptions=True 或拆 await**,**build_steps 结构化失败不取消/不丢失 missing_detect 结果**;`_llm_missing_detect` 的 provider/IO/DTO 失败沿用既有 case_failed。
- 成功路径:assembler 派生 → 在 try 块内对 build_steps 证据跑 `validate_build_step_evidence_for_spec`(证据失败转 Evidence 子类)→ 设 build_steps + 派生 subsystem_breakdown,**不调 legacy**。
- 降级路径:catch `BuildStepsStructuredError` → 记 reason-coded 降级日志(§本节下)→ 调 legacy `_llm_subsystem_plan` 补 subsystem_breakdown(build_steps=None)。**legacy 自身失败上抛**,不二次降级。
- 现有 3 处 `validate_for_spec`(plan.evidence / block_recommendations / missing_prompts)保留;新增 step 证据走新 helper。
- 顺手:`PaperPlanService` docstring「three-role」改为与实际 4 calls 一致(506 §207)。
- **降级护栏**:① 每次降级记 **reason-coded metadata-only 日志**(`reason_code ∈ {json_parse_failed, dto_invalid, br_no_match, br_ambiguous, redline, evidence_invalid, coverage_missing, empty_steps, …}`,**不记** LLM 正文/token/原始输出/参数值/路径/源码/claim,照 decision 11);② 见 §7 防全量退化 gate。

### 7. 测试(沿用现有 mock 框架;role 分键)
- `test_paper_plan_service.py`:① 结构化成功(`build_step_planner` payload → build_steps 非空 + subsystem_breakdown == 派生 + **断言 legacy `subsystem_planner` 未被调**)= **防全量退化 gate**;② 降级(结构化 payload 非法 → build_steps=None + subsystem_breakdown 来自 legacy payload);③ 红线泄漏 → 降级;④ 证据不合格(含**伪造 user_supplied**)→ 降级;⑤ provider/IO 真异常 → case_failed(**不降级**);⑥ **降级后 legacy 真异常继续上抛**(不被误降级成空 plan)。
- `test_paper_plan_helpers.py`:11 条逐条(命中/不命中、复合键唯一、无环、`block_ref_id` 全局唯一 + 可见闭包恰好一命中【含「两依赖 step 都声明 B1 → 引用 B1 必 fail」】、BR 重复 pair fail、覆盖度 dedupe/空 vacuous、fail-closed 整体置 None);display_text 白名单派生【Rs=0.05Ω + parameter_ref 指过去 → display_text 只出 Rs/名,**不出 0.05/Ω**】;BR key 确定性;normalized 折叠/trim/casefold。
- `test_paper_plan_prompts.py`:新 `paper_plan_build_steps.yaml` 版本/placeholder/输出 schema 约束/红线 + document-only-evidence 约束注入断言。
- mock:`PayloadPaperPlanService` 按 role_name 喂 payload;结构 role=`build_step_planner`、legacy=`subsystem_planner` **分键**,降级 case 两 payload 都给。

### 8. fixtures / golden / eval(R6 已实测定:不改)
- harness = **live true run(DeepSeekTextProvider)+ 规则指标(c2/c3/mscript shape,不看 build_steps)**:**保持两 golden `build_steps=null`**;**不改 golden、不改 `test_paper_schemas_sample_roundtrip.py`(它断言 golden build_steps is None)、不改 `_paper_eval_rules.py` verdict**——全留 509。
- `structured_status` 由 `plan.build_steps is None` 可 derive(509 接入指标)。
- 仅更新 eval case README 注解:从「507-A 阶段固定 null」改为「golden sample 仍为 null;live 可非空(507-B 起);build_steps 指标 509 接入」,免误导。

### 9. decision 13 同步面(本卡预期:对外契约零变更)
- 复用 507-A 契约、**不加对外字段** → `schemas/paper_plan.schema.json` **零 diff**、`web/src/lib/paperTypes.ts` **不改**。验收跑 `python -m scripts.export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json`(**期望无变更 = 守门;有 diff = 误改契约,停手报架构师**)+ `cd web && pnpm typecheck`。
- **会碰**:`core/prompts/paper_plan_build_steps.yaml`、`features/paper/_prompt_builder.py`、`features/paper/paper_plan_service.py`(含私有 draft DTO + 异常族 + 编排)、`features/paper/paper_plan_helpers.py`(assembler 派生/校验 + 证据 helper)、上述 3 个测试。
- **可能碰需谨慎**:`features/paper/paper_schemas.py`(**仅在必要时**放私有 parse model,但 §1 已定放 service;若放此须确认不进 `OUTPUTS`、不改 exported `ModelGenerationPlanModel/ModelBuildStepModel`)、eval case README(见 §8)。
- **不碰**:`schemas/paper_plan.schema.json`、`paperTypes.ts`、`scripts/export_paper_schemas.py`、`eval/_paper_eval_rules.py`、`test_paper_schemas_sample_roundtrip.py`。

## 不做(明确排除)
- ❌ 不改对外契约/枚举/`schema.json`/`paperTypes.ts`(复用 507-A;若发现非改不可 = 边界划错,**停手报架构师**)。
- ❌ 不做前端渲染/视觉(508)。
- ❌ 不实现评测器 build_steps verdict 规则、不改 `_paper_eval_rules.py`、不改 golden、不改 roundtrip 测试(509)。
- ❌ 不动 `TuningSuggestion`、不给它开数值口子、不绕过其方向-only 锁。
- ❌ 不删/不改 legacy `paper_plan_subsystem.yaml` 与 `_llm_subsystem_plan`(留作 fallback)。
- ❌ **user-supply 流程对 build_steps 的整合出本卡范围**(本卡只覆盖初始 `generate`;user_supplied 证据于初始生成一律拒)。
- ❌ 不碰追问/多文件/`PaperSpec`/`PaperEvidenceEntry` provenance。
- ❌ 不给 `ParameterMapping`/`BlockRecommendation` 加对外正式 ID(BR-xxx 仅 assembler 内部)。
- ❌ 不产出 `build_steps=[]`(非法);不返回半截 list。

## 验收标准
- [ ] 结构化成功 = 防全量退化 gate:合法 payload → build_steps 非空、11 条全过、`subsystem_breakdown` 字节级等于 `[display_text]`、display_text 不含参数值/单位、**legacy 未被调**。
- [ ] 降级:结构化 payload 非法 / 红线泄漏 / 证据不合格(含伪造 user_supplied)→ build_steps=None + subsystem_breakdown 来自 legacy;**绝不出 `[]` 或半截 list**。
- [ ] 错误分层:provider/IO 真异常 → case_failed(不降级);结构化失败 → 降级(execution succeeded);**降级后 legacy 真异常上抛**;并发不丢 missing_detect。
- [ ] 11 条逐条有单测(含 block_ref_id 全局唯一/可见闭包、BR 重复 fail、覆盖度 dedupe/空 vacuous、fail-closed 整体置 None、display_text 白名单)。
- [ ] 红线机检:带出处的值仍只在 `parameter_mapping`(不入步骤文字);瞎编数/裸值单位/倍率被拦;config 例外加 allowlist + 反查后无后门。
- [ ] **对外契约零变更守门**:`export_paper_schemas` + `git diff --exit-code schemas/paper_plan.schema.json` **无变更** + `pnpm typecheck` 绿。
- [ ] `make check` 全管道绿 + 上述显式 schema/前端验收。
- [ ] golden/roundtrip/verdict 未被改;eval 两 case 不回归。
- [ ] 降级日志为 reason-coded metadata-only(无正文/token/值/路径/源码)。
- [ ] decision 13 同步面 diff 全贴完工报告;`TuningSuggestion` 未被改/绕。
- [ ] 完工三件套(decision 08:含 git status/log/push 三命令输出;改已有文件用字节级/编辑器保留原始字节)。

## 风险与注意点
- **错误分层(最大)**:结构化失败族独立于 `PaperPlanGenerationError`、service 单点 catch;`_call_llm_json` 在 build_steps role 的 JSON 失败归结构化失败,但 provider/网络/认证/限流失败**不得**被 `_llm_build_steps` 包成结构化错误(否则真故障被误记 succeeded)。
- **BR-xxx 内容匹配脆弱**:LLM 改写 `purpose` → 不命中 → fail-closed → 降级。可接受(降级安全);prompt 强约束逐字复用;真实命中率/降级率留 509 调。
- **覆盖度抬高降级率**:契约无 optional/替代 block 标记,**全推荐必覆盖** → 推荐里有「可选/替代」block 时会整体降级。本卡接受(fail-closed 安全),509 据真实语料看降级率,必要时再议 optional 标记(新卡)。
- **红线裸值检的误报→降级**:文字里出现与某参数值巧合相同的数字会触发降级(如「3 phases」撞某值)。降级安全,509 调;config allowlist 缓解 build 设置类数字。
- **display_text 单一真值源**:白名单模板派生,严禁 LLM 给/回灌(三源漂移)。
- **证据失败按「降级」非「报错」**:legacy 路径证据已被现有 3 处 validate 兜;不为 build_steps 伪造证据(decision 21)。
- **行尾/异步/日志**:decision 08(改已有文件保留原始字节/编辑器/字节级)/ 11(降级走 `to_thread` 按需;禁 `logger.exception`;日志不漏值/路径/源码/token/claim/LLM 正文)。
- **feature boundary**:paper 独立,不 import overview/explanation 私有(decision 21)。

## Stage 0(派单后实现门第一步)
Codex 先 `git fetch` 取**最新** origin/main HEAD(**别用 d324591 旧值**),核:
1. 「现状」节 1–8 与最新 main 一致(尤其 `ModelBuildStepModel`/domain `display_text` 必填、`_call_llm_json` 异常走 `PaperPlanGenerationError`→评测器 case_failed、exporter alias-based、harness live run + 不看 build_steps、golden 仍 null)。
2. `scripts/export_paper_schemas.py` 预期**不需改**(契约零变更);确认私有 draft DTO 放 `paper_plan_service.py` 不进 `OUTPUTS`。
3. 评测器是否有 catch-all 会静默吞结构化失败族;有则结构化失败逃逸路径需单独保证可见(P0-2)。
4. 约束:除生成/校验/降级/新 yaml/`_prompt_builder.py`/测试 + (可选)eval README 外,**不改**对外契约 schema / `paperTypes.ts` / verdict / golden / roundtrip(若需动 = 边界错,停手报架构师)。
5. `git status`:**除预放任务卡(`task-507-b`)+ 本机 `*-dev.log` 外干净**。
任一不符/边界不对 → 停手报架构师(decision 15)。

## 估时 / 给 Codex 的提示
- 肉在「结构化 prompt + 私有 draft DTO + 异常族 + 11 条校验 + 降级编排 + 红线机检 + 证据 helper + 测试」;**对外契约不动**(复用 507-A)。
- 你那边没 `grep`:定位用 `git grep` / `rg` / `Select-String`。
- paper schema / 前端那几条验收**不在 `make check` 里,显式跑**。
- 改已有文件**保留原始字节**(decision 08:编辑器或 `read_bytes`+`write_bytes`,禁 `read_text`/`write_text`/`sed -i`);完工给 git status/log/push 三命令输出。
- 别越界到 508(前端)/ 509(评测 verdict/golden/roundtrip)。

## TASK-507 拆分位置
507-A(契约 substrate,已合)+ **507-B(本卡:生成 + 校验 + 降级 + 红线机检)**;沿用 substrate/wiring 两段法(517-A/B、518-A/B)。
