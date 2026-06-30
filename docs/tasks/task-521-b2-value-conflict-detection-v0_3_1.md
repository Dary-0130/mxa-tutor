# TASK-521-B2: Paper 多文件 · 值冲突检测 + 冲突展示(前后端一体)(v0.3.1)

## v0.3.1 增补(v0.3 → v0.3.1;并 **R1 定向复审[条件通过·不升 R2]** + **Codex Stage 0[清·无高风险落不下来]**;补 1 P0 + 5 P1 + 解 1 schema 偏差;**可派单/开工**。下方 §1–§8 v0.3 正文仍有效,本块为增补/覆盖。)

**双审结论**:R1 定向复审——A–E+F/G 落实正确、ask 对外零 diff 守住、前端不越界 521-D 守住、不偏向主文献/不伪造 locator/excerpt 守住、service 两层自洽;**派单前补 1 P0**。Codex Stage 0(分支 `codex/521-b2-parameter-conflicts`,切自 live origin/main)——检测挂点 / 防裁决+净化落点(`PaperPlanService.generate()` 共用入口)/ 真源落点(单篇 `_parse_and_validate`、多篇 `_fuse_successful_specs`、迁移 `_load_spec_with_migration`)/ B1 不变量无结构冲突 / ask 不动 / 结果页需新做一小块,**全部成立**。

**★ 新增 P0 — 旧/陈旧 plan 读回隔离(把 D 的不静默裁决从生成期扩到读回期)**:读回 `PaperPlanRecord` 时,若 `spec.parameter_conflicts` 非空——① 校 `plan.parameter_mapping` 不得命中 conflict key;② 校 `m_script_skeleton` 不得含冲突候选值单值赋值;③ 校 build_steps/tuning 依赖不把 abstain 参数当已定值;④ 命中任一 → **禁止静默返回旧 plan**:标记 stale 触发 regenerate / fail-fast 返脱敏错误,**不得当合法 ready bundle**。覆盖 GET /plan、tuning allowlist、前端参数表读回。(防 B1 合并后/B2 前已持久化的「静默裁决过的旧单值 plan」窗口;实现期可顺带确认此类旧 bundle 是否真存在,存在与否本守门都按 P0 落 = 读回期不变量。)

**schema 偏差裁决(Codex Stage 0 报)**:卡原写「symbol 空按空串入 key」,但现状 `ParameterEntryModel.symbol` 是 `min_length=1`。**裁决:不放宽 symbol schema**(放宽属参数表征层改动、超 B2 范围;现状参数恒非空 symbol,key `(name.strip(), symbol.strip())` 直接可用、空分支不触发;helper 仍 strip 作前向兼容)。**此项不动 schema/freeze、不进 decision 13**;**且 §3.2 的 `locator`/`excerpt` 恒 null**(Stage 0 确认 `ParameterEntry` 无 locator/source_ref/excerpt、不可追溯)。

**R1 5 条 P1(并入实现)**:① **builder 绕过路径核**——`git grep` 所有 `build_messages_for_plan_compose`/`build_messages_for_mscript_draft`/`_llm_plan_compose`/`_llm_mscript_draft` 生产调用点,确认无绕过 `PaperPlanService.generate()` 净化入口者;有则改经统一入口或签名强制传 sanitized。② **文本泄漏断言**——冲突候选值不出现在 `configuration_hints.instruction`/`ModelBuildStep.display_text`/tuning `parameter_directions`,除非「需用户确认」占位。③ **helper 层锁 value option 排序**(doc order,不只前端),防 snapshot 漂移。④ **save/load 边界 stored==recompute 运行期 assert/测试**(不只 freeze)。⑤ **前端文案固定**——「这些文档给出的参数值不一致,需要你确认后再用于建模」(PM 视觉过目带看)。

**验收/风险增补**:验收加——旧 plan 命中冲突 key → 不静默返回(stale/regenerate 或 fail-fast);**「全冲突 abstain + 前端冲突区可见」作端到端 case**;`configuration_hints`/`display_text`/`parameter_directions` 文本泄漏三处断言。风险加——**P0:旧/陈旧 plan 读回不隔离 → 绕过 generate-time guard 静默用旧单值**;P1:builder 绕过路径。

---

## 本版改动(v0.2 → v0.3;**并 R6 收尾 4 项确认 + PM 决定 → 前后端一体定稿**;待 R1 定向复审 → 派单)

**PM 决定(拍)**
- ① 冲突**当场给朴素提示**(选 A,不等后续);② **前后端一体、不分包**(PM:「一起做完别分包」)——**冲突展示前端折入本卡**,不再留 521-D;`521-C(ask 出处标到篇·对外)` / `521-D(多选上传+主文献勾选+文件来源展示+部分成功提示)` **其余范围不变、仍分卡**。

**R6=Codex 真 repo 收尾确认(实测 @origin/main 8156846)**
1. **可见表面**:现有结果页**无干净落点**承载冲突标记——参数区只吃 `plan.parameter_mapping` + `remainingMissingPrompts`(`PaperResultPage.tsx` / `ParameterTable.tsx`);塞 `remaining_missing_prompts` 会被当缺参输入框+user-supply 提交流程;塞 `parameter_mapping.value` 污染计划参数真值面 + 被 tuning allowlist 当可用参数收;塞 `build_steps.configuration_hints.instruction` 是步骤内容面、fallback 不稳。→ **冲突展示须新做一小块前端**(已折入本卡 §3.5)。
2. **输入控制**:**可干净落**。两个危险输入都在 prompt builder——PlanComposer `build_messages_for_plan_compose()` 塞完整 `PaperSpecModel`、prompt 要求从 `parameter_table` 识别参数;MScriptDrafter `build_messages_for_mscript_draft()` 塞 `parameter_table_json`、prompt 要求脚本参数从 parameter_table 读。落点 = `PaperPlanService.generate()` 入口先算/校 conflict set,再传两路 builder(过滤后输入 + `parameter_conflicts_json` summary)+ 后置 guard。不破坏现有 schema 假设(`parameter_table`/`parameter_mapping` 可空、`BuildStepPlanner` 的 `parameter_refs` 本就只引已有 mapping)。
3. **ask 暴露面**:**不含原始 `parameter_table`**——PaperAsk prompt 只拿 `source_table_json`;source 只收摘要/公式/spec evidence/plan·block·build-step evidence/用户补参/剩余缺参,`_spec_candidates()` 不遍历 `parameter_table`、`parameter_mapping` 只收 `USER_SUPPLIED` 行。→ **B2 不动 ask、归 521-C**。
4. **service 不变量落点**:**两层**——`PaperSpec.parameter_conflicts` 真源在 **spec 构造/融合**处落(单篇 `PaperSpecService._parse_and_validate()` + 多篇 route helper `_fuse_successful_specs()`);「不静默裁决」硬不变量 + LLM 输入净化在 **`PaperPlanService.generate()` 入口**(upload route / eval / service tests 都进或可直调这里)。检测 helper 放 core。

## 状态
🔲 **v0.3.1**(R1 定向复审过[不升 R2] + Codex Stage 0 清 + 补 1 P0/5 P1 + 解 symbol 偏差)→ **派单/开工**。
> 后端契约部分:实现 Stage 0 可落性 gate(沿 B1 引用桥做法)+ **合并前架构师亲核真 diff + decision 13 全清单 + 对外 `PaperAskCitation` 零 diff 验证**。前端部分:取证现有皮 + 截图(桌面+移动、空态/有冲突态)给 PM 过视觉。

---

## 1. 是 / 不是
**是**:在 B1 底座(同名参数 = `parameter_table` 多条 `ParameterEntry`、各带 document_id、融合纯拼接不去重)上——
- **检测**同名(`(name,symbol)`)跨篇值(`(value,unit)`)不一致;
- 持久化 **`PaperSpec.parameter_conflicts`**(materialized view、单一 helper 生成);
- **保证所有后端生成物不把冲突参数收敛成单值**(plan mapping abstain + PlanComposer/MScriptDrafter 输入控制 + build_steps/tuning 不当已定值);
- **冲突展示前端**(本版折入):结果页新增一小块,读 `parameter_conflicts`,朴素呈现「这两篇在『X』上对不上、你来定」(列出冲突的几个值 + 各自来自哪篇),**不伪造值、无「采用此值」按钮**;复用现有设计系统。

**不是**:
- ❌ 对外 `PaperAskCitation`/`paper_ask_response.schema.json` 加 document/冲突维度 → 521-C。**前端只读 `PaperSpec.parameter_conflicts`(经 GET /spec 已暴露),不碰 ask 对外 DTO。**
- ❌ 多选上传 UI / 主文献勾选 / 文件来源展示 / 部分成功提示 → 521-D。
- ❌ **交互式裁决**(让用户在界面上「选用某值/合并」)→ 留 521-D 若将来要;本卡只「如实摆出来、你来定」,不替用户选、界面也不提供选值动作。
- ❌ 扩 `ParameterMapping`(多值/document_id)、放宽 `paper_param_name` 唯一。
- ❌ 数值容差/单位换算/同义词归并;替用户挑值/偏向主文献/静默去重/静默丢冲突参数。
- ❌ 单篇内部同名矛盾(只管跨篇);LLM 产 document_id/判值对错;改已合并产物行为;工程文件/表格/代码解析。

---

## 2. 产品决定(PM 已拍,不重开)
- 值冲突**如实标、不静默裁决**:不替用户挑值。
- **不偏向主文献**:`primary_document_id` 主次身份非权重;检测/排序/呈现**不得**用它挑值(value option 排序最多按 doc order 稳定)。
- 综合多篇推出、无单一出处 → 不挂假出处、不伪造 `DOC-ALL`。
- 不回退 B1 不变量(locator A1 复合不改写、plan helper per-doc、plan provenance 引用桥无兜底、同名多源不去重、对外 `PaperAskCitation` 零 diff)。
- **(本轮 PM 拍)** 冲突**当场给朴素提示**;**前后端一体、不分包**(冲突展示前端在本卡)。

---

## 3. 范围(必须做)

### 3.1 冲突检测(A + F + G)
- [ ] core helper **`detect_parameter_conflicts(parameter_table) -> list[ParameterConflict]`**(纯函数、确定性、无 LLM):`parameter_key=(name.strip(), symbol.strip())`、`value_signature=(value.strip(), unit.strip())`;**只纳 `source==document_extracted` 且 `document_id != None`**(F);冲突 = 同 key 下 ≥2 不同 document_id 且 ≥2 不同 value_signature;同值多篇 = 一个 value option 的多 observation(不报冲突,但若另有不同值则该值作为一个选项列入)。
- [ ] **不做** 数值容差 / 单位换算 / 同义词归并;`symbol` 空按空串入 key、不强行按 name 合并。
- [ ] `parameter_conflicts` = `parameter_table` 的 materialized view(G):**只经 `detect_parameter_conflicts` / `with_parameter_conflicts(spec)` 生成**,禁手写不一致结构。

### 3.2 结构(B;见 §4 字段表)
- [ ] 顶层 `PaperSpec.parameter_conflicts: list[ParameterConflict]`;非 per-entry、非现场派生。
- [ ] `document_id`+`value`+`unit` 必填;`locator`/`excerpt` **可空、仅当真 repo 能从 `ParameterEntry` 确定性追到原始 evidence 时填、否则不填、禁伪造**(⚠ 可追性实现 Stage 0 确认;不可追则恒 null)。

### 3.3 检测落点 + service 不变量(C + R6 两层)
- [ ] **真源落点**:`parameter_conflicts` 在 **spec 构造/融合**处由 helper 生成并落——单篇经 `PaperSpecService._parse_and_validate()`、多篇经 `_fuse_successful_specs()`(融合后 `parameter_table` 已纯拼接);单篇/无冲突为 `[]`。
- [ ] **防裁决不变量落点**:「不静默裁决」硬不变量 + LLM 输入净化在 **`PaperPlanService.generate()` 入口**(R6:upload route / eval/run_paper_eval.py / service tests 都进或可直调此处);**非 route-only**。
- [ ] 老 blob 读回:缺 `parameter_conflicts` → 用同一 helper **deterministic recompute**(单文件旧数据自然空、多文件旧数据不被静默漏),**不固定补空**;沿 `_load_spec_with_migration` 唯一入口。

### 3.4 下游不静默裁决(★ 头号 P0;扩到所有生成物;R6 确认可落)
冲突 parameter_key **不得被任何后端生成物收敛成单值**:
- [ ] **`plan.parameter_mapping`**:冲突参数 **abstain**;保 plan 契约(不扩 mapping、不放宽 name 唯一)。① plan prompt 列 `parameter_conflicts` + 要求 composer 不为这些 key 产 mapping;② **后置 guard**:任何 mapping 命中 conflict key → plan invalid → retry / fail-fast;③ **不静默 prune** LLM 产的冲突 mapping(掩盖 LLM 已尝试裁决);若 prune 必伴重校、不得让空 evidence/不合法结构通过。
- [ ] **PlanComposer 输入控制**(R6 真正卡点):`PaperPlanService.generate()` 入口算 conflict set → 传 `_llm_plan_compose()`,builder 把喂 composer 的 `paper_spec_json` 改成**过滤后参数输入 + `parameter_conflicts_json` summary**(冲突参数不以「可挑单值」形态出现)。
- [ ] **`MScriptDrafter` 输入控制**(GPT 易漏 P0 + R6 confirm):同入口传 `_llm_mscript_draft()`,builder 把喂 drafter 的 `parameter_table_json` 改成过滤后输入 + summary;m_script skeleton **不得含冲突参数的具体候选值**。
- [ ] **build_steps / configuration_hints / tuning**:不把冲突参数当已定值;`BuildStepPlanner` 不引被 abstain 参数(否则 `parameter_ref_no_match` 降级 legacy——`BuildSteps.tsx` 有 null 回退、不炸)。
- [ ] **空结构守门**(P1):全冲突 abstain → mapping 可空,但 `parameter_conflicts` 必存且可读;非冲突参数仍空 mapping → plan 质量失败、retry;build/script/tuning 依赖被 abstain 参数 → fail-fast 或「需用户确认」占位,**不隐式取值**。**空结构不得作为静默吞冲突的伪成功**。

### 3.5 冲突展示前端(本版折入;R6:无干净现有落点 → 新做一小块)
- [ ] 结果页(`PaperResultPage.tsx`)新增**独立「参数冲突」区**——**独立于参数表(`ParameterTable`)与缺参输入流程**,避免被当「待填值/缺参」处理。读 `PaperSpec.parameter_conflicts`(经 GET /spec 已暴露)。
- [ ] 每条冲突呈现:参数名 + 各 value option(值 / 单位 / **来自哪篇**)+ 朴素语义「这几篇对这个参数给的值不一样,需你确认」。**无「采用此值/合并」按钮**(交互式裁决留 521-D);**不伪造值、不替用户挑、不偏向主文献**(value option 按 doc order 稳定列)。
- [ ] `parameter_conflicts == []` → 不显示该区(或空态、不占视觉)。
- [ ] **复用现有设计系统**(#2c2c2c / 信号橙 #e85d3a / IBM Plex + 思源黑 / border-radius:0 / 半透玻璃);TS `paperTypes.ts` 镜像 `parameter_conflicts`、前端只读不回写。
- [ ] 截图(桌面 + 移动、空态 + 有冲突态)作图片附件给 PM 过视觉。

### 3.6 ask(R6 确认:B2 不动)
- [ ] ask 的 LLM prompt/source table **不含原始 `parameter_table`**(R6 实测),故 ask 不会静默挑冲突参数单值 → **B2 不动 ask;ask 的 document 维度 / 参数出处归 521-C**。对外 `PaperAskCitation` 零 diff。

### 3.7 schema / freeze / eval / prompt / TS 同步(decision 13;R6 blast radius)
- [ ] schema:`paper_spec.schema.json` 加 `parameter_conflicts` + 嵌套结构;`make export-schema`+`verify-schema` 零 diff;**`paper_ask_response.schema.json` 零 diff**。
- [ ] freeze:`ParameterConflict`/value option/observation 字段顺序 + required-vs-nullable + `PaperSpec` 字段顺序 + **「stored conflicts == deterministic recompute」** round-trip + 多篇冲突 round-trip。
- [ ] paper_schemas.py:嵌套 model + `PaperSpecModel` 字段 + `_to_domain_unchecked`/`to_domain`/`from_domain`;paper_spec_service.py/paper_document_identity.py:**raw LLM PaperSpec 不产 conflicts → 后端默认/注入,strict validate 不炸**。
- [ ] paper_document_identity.py:校 conflict observation `document_id ∈ documents` + source 约束(经 core helper)。
- [ ] 迁移:sqlite_paper_cache.py dump/load + `_load_spec_with_migration` deterministic recompute。
- [ ] eval golden:`expected_paper_spec.json`/`expected_multidoc_fused_paper_spec.json` 加 `parameter_conflicts`(单篇/无冲突 `[]`);**新增跨篇同名参数不同值冲突 case** + m_script/plan 防单值裁决断言。
- [ ] prompt:plan composer prompt 列 `parameter_conflicts` + 禁为其产 mapping、参数识别改「过滤后输入」;mscript prompt 同步防单值。
- [ ] TS:`paperTypes.ts` 镜像 `parameter_conflicts`(GET /spec & upload response 暴露 `PaperSpec`)+ 前端冲突区组件;`pnpm typecheck`/lint/build 绿。

### 3.8 工程守则
- [ ] decision 08 原始字节/行尾;decision 11 不 `logger.exception`、filename/原文/参数值原文不落日志、**前端控制台干净**;decision 21 跨层经 core 公开契约、跨结构校验经 core helper。
- [ ] **不回退 B1 不变量**(§2)。

---

## 4. 接口契约(本卡增量)
### `PaperSpec.parameter_conflicts: list[ParameterConflict]`(新顶层;经 GET /spec & upload response 暴露,前端只读)
### `ParameterConflict`
| 字段 | 类型 | 约束 |
|---|---|---|
| `parameter_name` | str | strip 后 |
| `parameter_symbol` | str | strip 后(可空串)|
| `value_options` | list[ParameterConflictValueOption] | ≥2 |
### `ParameterConflictValueOption`
| 字段 | 类型 | 约束 |
|---|---|---|
| `value` | str | 必填 |
| `unit` | str | 必填 |
| `observations` | list[ParameterConflictObservation] | ≥1(同值可多篇)|
### `ParameterConflictObservation`
| 字段 | 类型 | 约束 |
|---|---|---|
| `document_id` | str | 必填、∈ documents |
| `locator` | str \| null | 可空、仅可靠时填、禁伪造 |
| `excerpt` | str \| null | 可空、仅可靠时填、禁伪造 |

> ⚠ `locator`/`excerpt` 可追性 = 实现 Stage 0 确认;不可追则恒 null。字段名/精确形状以实现 Stage 0 实测为准微调。

**B-i blast radius(R6 实测清单,实现期逐一同步)**:core/domain/paper_spec.py · features/paper/paper_schemas.py · core/domain/paper_document_identity.py · api/routes/paper_upload.py(`_fuse_successful_specs`)· features/paper/paper_spec_service.py(`_parse_and_validate`)+ paper_document_identity.py · adapters/storage/sqlite_paper_cache.py(`TypeAdapter(PaperSpec)` dump/load + `_load_spec_with_migration`)· scripts/export_paper_schemas.py · freeze/roundtrip 测 · eval golden · web/src/lib/paperTypes.ts + 结果页冲突区组件 · docs/06。

### 不变量(B1 上新增)
- 冲突只纳 `document_extracted`+`document_id` 非空;`parameter_conflicts` = `parameter_table` 的 deterministic materialized view(单一 helper、stored==recompute)。
- 冲突参数不被任何后端生成物收敛成单值(mapping abstain + PlanComposer/MScriptDrafter 输入控制 + build/tuning 不当已定值);空结构不得静默吞冲突。
- `locator`/`excerpt` 禁伪造;不偏向主文献挑值;**对外 `PaperAskCitation`/`paper_ask_response.schema.json` 零 diff**;不扩 `ParameterMapping`/不放宽 name 唯一。
- 前端冲突区只读 `parameter_conflicts`、**无选值动作**、不伪造值。

---

## 5. 验收(可跑命令 + 贴证)
**后端**
- [ ] 两篇同名 `H` 两值(`3.5/DOC-001`、`4.0/DOC-002`)→ `parameter_conflicts` 一条、value_options 两个、各带 document_id;同名同值多篇 → 不报冲突。
- [ ] 单篇 / 无冲突 → `parameter_conflicts == []`。
- [ ] `(value,unit)` 精确比:`5 s` vs `5 ms` 判冲突;`3.5` vs `3.50` 判冲突(接受假阳)。
- [ ] **stored == deterministic recompute**(freeze/round-trip 守)。
- [ ] **plan abstain**:冲突参数不进 `parameter_mapping`;构造「LLM 仍产冲突 mapping」→ plan invalid → retry/fail-fast;非冲突参数空 mapping → 质量失败。
- [ ] **MScriptDrafter 防单值**:H 两值冲突 → `m_script_skeleton` 不出现 `H = 3.5`/`H = 4.0` 单值赋值。
- [ ] **build_steps/tuning**:不把冲突参数当已定值;abstain 参数不被 build step 引用(或合法降级)。
- [ ] **service 不变量**:经 `PaperPlanService.generate()` 的所有路径(含 eval/服务测试)都跑防裁决,非仅上传 route。
- [ ] 老 blob(缺 `parameter_conflicts`)读回 deterministic recompute、不炸;新多篇 blob round-trip 不变。
- [ ] `make export-schema`+`verify-schema` 零 diff;`paper_spec.schema.json` 含 `parameter_conflicts`;`paper_ask_response.schema.json` 未变。
- [ ] freeze 全绿;`make check` 全绿(含 R6 blast radius 全入口)。

**前端**
- [ ] 两篇冲突 → 结果页冲突区列参数名 + 各值 + 来自哪篇 + 「你来定」;**无「采用」按钮**。
- [ ] 无冲突 → 不显示冲突区/空态、不占视觉。
- [ ] 复用设计系统;`pnpm typecheck`/lint/build 绿;**控制台干净**。
- [ ] 截图(桌面+移动、空态+有冲突态)作图片附件给 PM。

**收尾**
- [ ] `docs/06` 同步;decision 13 全清单逐项在 PR 说明列;对外 citation defer 521-C、交互式裁决 defer 521-D 明示。

---

## 6. 风险与注意点(GPT + R6)
**P0**
1. **只检测不防裁决**(最大):必须扩到所有生成物。
2. **漏 MScriptDrafter**:直吃 `parameter_table`、最易静默写单值;专门测。
3. **PlanComposer/MScriptDrafter 输入未控**(R6 真正卡点):只 abstain mapping 但仍喂原始冲突参数 = 仍会静默挑;输入净化在 `PaperPlanService.generate()` 入口。
4. **locator/excerpt 强制必填但无可靠链路** → 诱导伪造;先保 document_id+value+unit,可追才填。
5. **`parameter_conflicts` 与 `parameter_table` 漂移**:单一 helper + stored==recompute 守。
6. **primary 被隐式当权重**:检测/abstain/value option 排序/前端列序不得用 primary。
7. **对外 DTO 越界**:`paper_ask_response.schema.json` 零 diff;碰 = 进 521-C。
8. **service vs route**(R6):防裁决须落 `PaperPlanService.generate()` 入口、非仅上传 route。
9. **前端冲突区越界成 D**:本卡只「如实摆出+你来定」,**不提供选值/合并动作**(那是 521-D);也不得改坏现有结果页/参数表。

**P1**
1. 假阳噪音(`3.5` vs `3.50`):首版接受;后续真实 eval 再议显示层等价提示(不在本卡引容差/换算)。
2. `symbol` 缺失漏判:首版接受避误并;后续可人工可审 alias map。
3. 单篇内部同名矛盾:本卡只管跨篇,内部另起 task。
4. schema churn:触发 decision 13 全清单。
5. 旧 blob 迁移 deterministic recompute、不补空。
6. fixture 大量炸:所有 `PaperSpec`/`ParameterEntry` constructor、golden、eval case 补新字段 + 冲突样本。

---

## 7. PM 接触(已拍 + 一处视觉过目)
- **已拍(本轮)**:① 冲突当场提示(选 A);② 前后端一体不分包。
- **唯一剩余 PM 接触 = 视觉过目**:前端冲突区做出后,Codex 出截图(桌面+移动、空态+有冲突态),PM 瞄一眼「好不好看」(视觉级,PM 定)。
- 其余(冲突判定口径、结构、abstain 机制、输入控制落点、service 两层、schema churn、前端非交互边界)= 实施形状,走双审,不烦 PM。

## 8. 给 Codex 的提示(派单实现阶段)
- **Stage 0(实现前)**:live origin/main HEAD、从 live 切新分支。逐条核 v0.3 假设仍成立(检测挂点 / `PaperPlanService.generate()` 入口净化点 / 两路 builder 输入构造 / spec 构造+融合落 conflicts 点 / 迁移入口 / `parameter_conflicts` 加进结构是否引发 B1 不变量冲突 / locator·excerpt 可追性);**高风险落不下来停手报架构师、禁兜底硬上**(沿 B1 引用桥做法)。不符即停(decision 15)。
- **后端**:检测 helper 放 core;spec 构造(单篇 `_parse_and_validate`)+ 融合(`_fuse_successful_specs`)落 `parameter_conflicts`;`PaperPlanService.generate()` 入口 = 防裁决硬不变量 + 两路 builder LLM 输入净化(过滤冲突参数 + `parameter_conflicts_json` summary)+ 后置 guard(mapping 无冲突 key / m_script 无冲突候选值);**对外 `PaperAskCitation`/`paper_ask_response.schema.json` 零 diff**;decision 13 全清单。
- **前端**:取证现有结果页皮 + 截图;新增独立「参数冲突」区读 `parameter_conflicts`、**无选值动作**、复用设计系统;截图(桌面+移动、空态+有冲突态)作图片附件给 PM;`pnpm typecheck`/lint/build + 控制台干净。
- 红线:LLM 不产 document_id/不判值对错;locator/excerpt 禁伪造;不偏向主文献;不回退 B1;不扩 `ParameterMapping`/不放宽 name 唯一;前端不做交互式裁决。
- 完工三件套 + decision 13 全清单逐项在 PR 说明列;**任务卡随代码一并 add 进同一代码 PR、索引收尾走单独 PR**(decision 07);子卡完工 521 整数不 +1。
- 本机无 `grep`,用 `git grep`/`rg`/`Select-String`;行尾/字节(08);异步/日志(11)。**合并前架构师亲核后端真 diff + 对外零 diff(后端契约部分);前端部分不走亲核后端 schema 重关、走截图视觉过目。**

**修订历史**:v0.1(draft-ahead 起稿)→ v0.2(并 GPT 方案裁决 A–E+F+G + R6 可落性发现 + 架构师可见性裁决)→ **v0.3**(并 R6 收尾 4 项确认 + PM 拍 A+不分包 → 前后端一体定稿;待 R1 定向复审 → 派单)。
