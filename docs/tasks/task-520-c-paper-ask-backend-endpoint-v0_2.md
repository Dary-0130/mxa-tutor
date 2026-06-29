# TASK-520-C:Paper 追问 · 后端问答端点 `POST /papers/{id}/ask`(落地 520-A 契约)

**版本**:v0.2(并 R1 + R6 双审 P0 + P1 + 择优 P2;两审均判**无需升 R2、无新产品/契约决定**,定稿候选 → PM 知会一处体验含义后派单)
**所属线**:paper-to-model · 追问子线(decision 22:追问 / 多文件 = 520+;字母子卡折进整数 520)
**前置**:520-A 契约 ✅ 合并(#140)/ 520-B1 可见锚点 ✅ 合并(#141)/ 520-B2 跳转·高亮 ✅ 合并(#142)。本卡**以 520-A v0.2 为最终契约真值**,任何字段 / 枚举 / 不变量冲突一律以 520-A 为准。
**现状基线**:R6 实测 origin/main HEAD `e9ca8c1`(2026-06-29 本轮 fetch);**派单实现阶段 Codex Stage 0 复核最新 HEAD,用 live 值**。

---

## 本版改动(v0.1 → v0.2,并审而来)

**[P0]**（R6 实测 + R1 独立同点 — 高信号:excerpt 来源）
1. **§3/§4 excerpt 来源写死(来源不伪造收紧)**:实测 `ParameterMapping` 无 per-row `paper_reference`/excerpt;`document_extracted ⇒ excerpt 1..300` 的 excerpt **只能取自真实文档摘录结构**（`spec.abstract` / `spec.equations[].latex_or_text` / `spec.evidence[].excerpt` 等本就带 excerpt 的结构）,**禁止**用任何 **plan 生成文本**（`subsystem_breakdown` / `build_steps` / `block_recommendations` / tuning 文本）或 mapping 的生成 `value` 充当 excerpt。无法可靠取得合法 excerpt 的证据 → **不作 document_extracted citation / 不入 source_table**;若因此无任何合法 citation → `insufficient_evidence` fallback。`user_supplied` 不受影响（excerpt=None）。**per-row document evidence 关联增强 = 后续解析升级卡（待办），不在本卡。**（R6 P0 / R1 P1-2 / R1 P1-7）

**[P1]**（R6 实测）
2. **LLM 错误码改为沿用现状**（§7）:实测 DeepSeek adapter 抛 `LLMTimeoutError/LLMRateLimitError/LLMQuotaError/LLMServerError/LLMAuthError`,现有全局 handler 冻结 **timeout 504 / rate 429 / quota 503 / server 502 / auth 503**。删 v0.1 凭印象的「quota/unavailable→429/503」,**PaperAsk 沿用现状映射,不做局部改**（局部改=动对外错误码,非本卡）。（R6 P1-a）
3. **missing_prompts 用 remaining set**（§4）:实测 `UserSupplyService` 更新 plan row 时**保留** `record.missing_prompts`;当前仍待填集合须用 `resolved_prompt_ids(record)` 过滤（现有 `/plan` 即如此）。`MissingPromptParameterTarget.prompt_id` 成员校验 + source_table 收录**只对 remaining set**,不对 raw `record.missing_prompts`。（R6 P1-b）
4. **build_steps=None 降级面**（§4）:实测 `build_steps` 可为 None,前端 `BuildSteps` 改用 `plan.block_recommendations` 渲染。paper-build-steps section 的可跳 / 可引以**当前实际渲染内容**为准（build_steps 非空用之,否则 block_recommendations）;但二者皆生成文本,**不作 document excerpt 来源**（受 P0 规则约束）。（R6 P1-c）

**[P1]**（R1 实测）
5. **只校验 prompt_source_table,不用 full**（§4/§5）:区分 `full_source_table`（从 spec/plan/missing 构出的全量）与 `prompt_source_table`（截断后实际送 LLM 的）。**LLM citation_ids 只能在 `prompt_source_table` 解析**;存在于 full 但未发送的 id → 按 unknown → `invalid_or_missing_citations` fallback。补单测。（R1 P1-1）
6. **out_of_scope 可达 + LLM malformed 裁决**（§5）:LLM **内部响应 schema**（后端↔LLM 私有,非对外 DTO）加 `answer_kind: Literal["answer","out_of_scope"]`;`out_of_scope` → 200 fallback `out_of_scope`。**LLM 输出层不合规**（JSON parse 失败 / 字段缺失 / confidence 非枚举 / citation_ids 类型错 / 引非 `S?` / 含 DOM id 字面）→ **200 fallback `invalid_or_missing_citations`**（不崩 5xx）。区分:**调用层故障**（timeout/quota/server/auth）→ 5xx(§7);**输出层不合规** → 200 fallback。（R1 P1-3）
7. **raw anchor 检测 scope 写死**（§5）:LLM 输出中**任意 citation id 非 `S?` 格式**,或 **answer / citation payload 含 `paper-eq-` / `paper-param-map-` / `paper-param-missing-` 等 DOM id 字面**,或**出现 `anchor`/`dom_id`/`locator` 等越权字段** → 整体 fallback `invalid_or_missing_citations`。补单测,与 §8「后端 grep 不生成 DOM id」互补。（R1 P1-4）
8. **store「spec 在 / plan 缺」裁决**（§7）:实测 `get_plan_record()` 无 plan row → `None` → route 转 `PaperNotFoundError` → 404。ask 需要 plan,**沿用现状 404**（含 spec-only 未生成 plan 的情况）;**不新增错误码**。前端文案可区分「资料在但还没生成方案」,后端沿用现有 404。（R1 P1-5）
9. **Pydantic target union 嵌套约束**（§1/§10）:四种 target 中两个 parameter 变体共享 `kind="parameter"`,**不得**用单层 `Field(discriminator="kind")` 直接包四类;须**嵌套 union**（顶层按 `kind`;parameter 分支内再按 `origin`）或显式 wrapper/validator,由 freeze + roundtrip 锁住四种 target JSON。（R1 P1-6）

**[P2]**（择优并入,低成本高价值）
10. **citation_ids 去重保序**（§5）:LLM 输出 `["S1","S1","S2"]` → citations `S1,S2`,保留首次出现序。补单测。（R1 P2-1）
11. **whitespace-only question → 422**（§3）:wrapper validator,`question.strip()` 空 → 422;但**保留用户原文,不自动 trim 进 LLM**。（R1 P2-2）
12. **wrapper 默认值写清**（§10）:`session_id: str|None=None` / `is_fallback: bool=False` / `fallback_reason: ...|None=None`,避免 Codex 让 `session_id` 成必填致合法请求 422。（R1 P2-3）
13. **fallback 的 follow_up 口径**（§5）:fallback 时 `follow_up_suggestions` 允许空;若非空,不得暗示「资料里有但没找到」。（R1 P2-4）
14. **schema 接 Makefile 作 hygiene 附带单列**（§6/§10）:把「现有 5 个 paper schema 接进 drift 闸」作为同卡 schema-hygiene 附带,完工报告 / PR 描述单列,降 review 噪音（非改现有 paper schema 语义）。（R1 P2-5 / R6 同意）

> 两审一致:**无 P0 推翻契约,无需 PM 重新拍契约,不升 R2**。上述全为实现规格消歧 / 工程门收紧。唯一需给 PM 的是 P0 收紧带来的**体验含义**（哪些出处可点),作知会非拍板（见卡末「PM 接触」）。

---

## 这张卡是什么 / 不是什么

- **是**:后端落地 520-A 定死的 PaperAsk 契约。新增 `POST /api/v1/papers/{paper_id}/ask`:接 PaperAsk 请求 → 现读现构 `source_table`（从 spec / plan / missing_prompts）→ 调 LLM（DeepSeek）带 source_id 引用约束 → 校验 LLM 输出的 source_id 并展开为带 `PaperCitationTarget` 的 citations → 按 520-A §5 裁决失败语义 → 返回 `PaperAskResponse`。含 §6 schema 同步面（decision 13 全清单 + 接 Makefile drift 闸）。
- **不是**:不做前端问答 UI / citation wiring（520-D）;不做 AnchorRegistry / scroll-highlight（B2 已落,不动）;不做 hardening / 截图矩阵（520-E）;不建向量库 / 不存对话历史 / 不复用 MCS ChatService 实现 / 不复用 SourceRefDTO;不碰追问外的 PaperSpec / Plan 生成链 / 现有渲染产物。

**核心风险（为什么这张最重）**:这是 520-A 三层真值源的后端落点。一旦 source_table 构造、citation 校验、失败裁决任一处走样,B 版「精确跳转」要么变跳空死链、要么把用户补充 / AI 生成文本伪装成文档证据、要么绕开「非降级必须带出处」。本卡所有红线均来自 520-A,不得在实现层被绕过。

---

## 状态

🔲 v0.2 定稿候选 → PM 知会一处体验含义（非拍）→ 预放 `docs/tasks/` → 派 Codex 实现。

## 上下文 / 已锁口径（520-A 已拍,本卡不重开）

- **v0 stateless**:不建向量库、不存对话历史、现读现构上下文;DTO 留挂存储位（`session_id` 仅回显）;UI 不暗示多轮记忆（520-D 事）。
- **三层真值源（命脉）**:① citation 真值源在后端 `source_table`,LLM 只引后端编的 `source_id`、不准自造 anchor / locator / DOM id;② anchor（DOM）真值源在前端 AnchorRegistry（B2 已落）,**后端只给语义 target、不碰 DOM**;③ 可点击是能力非承诺,两阶段两处理（后端校语义 target、前端校 DOM）。
- **参数值红线**:回答不替用户编论文没给的值;论文有出处的值可显;调参只给方向。
- **来源不伪造**:`document_extracted` 必有 locator + excerpt;`user_supplied` 必无 paper locator、`excerpt is None`;citation 不得把用户补充**或 AI 生成文本**伪装成文档证据。
- **injection 防御照 MCS 语义、不复用 MCS / paper 现有 prompt builder 实现**:上下文是数据不是指令 + 截断;用户补充 / 问题文本同按 data 处理。
- **feature 边界（decision 21）**:PaperAsk 放 `features/paper/`,跨层只走 `core/` 公开契约,**不 import** overview / explanation / chat 私有;`ConfidenceValue` 复用 `core/domain/paper_tuning.py`,**不得 import chat 私有 `Confidence`**。
- **§6 已拍**:把 paper schemas 接进 `Makefile export-schema/verify-schema` drift 闸（强制项,无开放分支）。
- **LLM provider = DeepSeek**（已锁）,复用现有 paper LLM 调用通道,不新造。

## 不在本卡（明确排除）

- ❌ 前端问答 UI / citation badge wiring / `onClick→scrollToCitationTarget` 接线（520-D）。
- ❌ AnchorRegistry / scroll / highlight（B2 已落,不动）。
- ❌ 图索引 / figure 可跳 target（走「丙」;figure 出处按 §5.4 只落 answer 正文不可点）。
- ❌ 对话历史持久化 / 多轮记忆 / 据 `session_id` 读历史。
- ❌ 复用 / 修改 MCS ChatService、SourceRefDTO、chat 私有 `Confidence`。
- ❌ 改动 spec / plan / missing_prompts 生成链或其 domain;**不在本卡补 per-row document evidence 关联**（后续解析升级卡）。
- ❌ hardening / 截图矩阵（520-E）。

---

## §1 落位与文件清单

**新增**
- `core/domain/paper_ask.py` —— frozen dataclass:`PaperAskRequest` / `PaperAskResponse` / `PaperAskCitation` + target union（`SectionTarget` / `EquationTarget` / `PlanMappingParameterTarget` / `MissingPromptParameterTarget` + `PaperCitationTarget` = 四者 union）+ `PaperAskFallbackReason` Literal。`ConfidenceValue` 从 `core/domain/paper_tuning.py` import 复用;`source_kind` 用 `core/domain/paper_evidence.py` 的 `EvidenceSource`（`str, Enum`,值 `document_extracted` / `user_supplied`）。
- `features/paper/paper_ask_schemas.py` —— Pydantic wrapper:仿现有 `paper_schemas.py` 的 `_StrictBaseModel`（`extra="forbid"` + `from_attributes=True` + `from_domain`/`to_domain`）。**target 用嵌套 discriminated union**:顶层按 `kind` 判别 section/equation/parameter;`kind="parameter"` 分支内再按 `origin` 判别 plan_mapping/missing_prompt（**不得单层 `Field(discriminator="kind")` 包四类**,见 §10）。底部给 `Schema` alias（`PaperAskRequestSchema` / `PaperAskResponseSchema`）。
- `features/paper/paper_ask_service.py` —— 端点核心服务（仿 `paper_tuning_service.py`）:构 source_table → 调 LLM → 校验展开 → 失败裁决。source_table 构造可抽 `_paper_ask_source_table.py`（实施定）。
- `api/routes/paper_ask.py` —— `POST /api/v1/papers/{paper_id}/ask`,仿 `api/routes/paper_tuning.py`（POST + `Depends(get_paper_bundle_store)` + service;R6 确认:POST action 已与 GET 查询分文件,独立 route 比并进 paper_query.py 更贴现状）。在 app 注册路由。
- LLM prompt 模板:走现有 `_prompt_loader.load_prompt_template(...)` 模式新增 PaperAsk prompt yaml（`core/prompts/*.yaml`,`version/description/system/user`）;内容为 data-not-instruction + source_table 引用约束 + 要求 LLM 输出含 `answer_kind`（见 §5）。
- `schemas/paper_ask_request.schema.json` + `schemas/paper_ask_response.schema.json`（export 脚本生成,**人手不写**）。
- 测试:`test_paper_schemas_freeze.py` / `test_paper_schemas_sample_roundtrip.py` 追加 PaperAsk 项（§6）;route serialization 测试（§8）;service 单测（校验 + 失败裁决覆盖 + §8 新增项）。

**改动（additive,不动既有语义）**
- `scripts/export_paper_schemas.py`:`OUTPUTS` 加 paper_ask 两个文件（§6.1）。
- `Makefile`:`export-schema` 加 `python -m scripts.export_paper_schemas`;`verify-schema` 追加 paper diff 清单（§6.2,含修复现有 5 个未接的缺口,作 hygiene 附带）。
- `docs/06_OUTPUT_CONTRACTS.md`:加 PaperAsk 小节（§6.5）。
- `web/src/lib/paperTypes.ts`（手维护）:加 PaperAsk 请求 / 响应 / citation 类型,`citation.target` **引用 B2 已落的 `PaperCitationTarget` union,不重定义**（§6.7）。

**不得新增第二 anchor 真值源**:后端永不生成 / 拼接 DOM id;只给语义 target。

---

## §2 端点流程（实现规格）

`POST /api/v1/papers/{paper_id}/ask`,body = `PaperAskRequest`:

1. **取数据**:`PaperBundleStore.get_plan_record(paper_id)` 一次拿 `spec + plan + missing_prompts (+ missing_bindings)`（R6 实测可落）。
   - 无 plan record（含 spec-only 未生成 plan）→ `raise PaperNotFoundError("paper_not_found")` → 404（§7）。
   - plan 在但 join 不到 spec（bundle incomplete）→ `raise StoreError("paper_bundle_incomplete")` → 500 `store_error`（**不伪装 404**）。
2. **构 full_source_table**（§4）:遍历 spec / plan / **remaining** missing_prompts,把**可合法成为 citation 的证据单元**编号为 `S1..Sn`,每条 = `{source_id, label, excerpt|None, source_kind, target}`。
3. **截断 → prompt_source_table**（§4）:按上限截断后送 LLM 的子集;`source_id` 编号在 **prompt_source_table 内一致**。
4. **调 LLM**（§4/§5）:把 prompt_source_table（带 `S?`）+ 用户问题作为 **data**(非指令)送 LLM,要求输出 `answer_kind` + `answer` + `citation_ids`(只引 `S?`) + `confidence` + `follow_up_suggestions`,**禁止自造 anchor / DOM id / locator / 越权字段 / 论文外的值**。
5. **校验 + 展开**（§5）:
   - `answer_kind=="out_of_scope"` → 200 fallback `out_of_scope`。
   - LLM 输出层不合规（malformed JSON / 字段缺失 / confidence 非枚举 / citation_ids 类型错 / raw anchor，见 §5）→ 200 fallback `invalid_or_missing_citations`。
   - 引的每个 id 必须在 **prompt_source_table**;否则（含 id 在 full 但未发送）→ fallback `invalid_or_missing_citations`。
   - 空 citations → 同上 fallback。
   - 每个 id 对应 target 的语义必须仍在 spec/plan（equation_id ∈ spec.equations；plan_mapping `row_index < len(plan.parameter_mapping)`；missing_prompt `prompt_id` ∈ **remaining set**；section ∈ 五区块）;否则 → fallback `citation_target_unresolved`。
   - citation_ids **去重保序**（首次出现序）。
   - figure-only / 不可引用证据不进 citations;若因此无任何合法 citation → fallback `insufficient_evidence`。
6. **裁决 + 组装**（§3 不变量）:成功 → `is_fallback=False` + `len(citations)>=1` + `fallback_reason=None`;fallback → `is_fallback=True` + `confidence="low"` + `citations=[]` + `fallback_reason!=None`。`session_id = request.session_id or 新生成`;`message_id` 新生成。
7. **返回** `PaperAskResponse`（wrapper 校验 `extra=forbid` + 字段约束 + response 不变量）。

---

## §3 复用 520-A DTO 契约（逐字以 520-A §2/§3 为准;此处复述供实施）

**对外 DTO**（`paper_ask.py` frozen dataclass + `paper_ask_schemas.py` wrapper 约束）:

```python
@dataclass(frozen=True)
class PaperAskRequest:
    question: str                 # wrapper: min_length=1, max_length=1000; strip 后空 → 422(不改原文进 LLM)
    session_id: str | None = None # 仅回显;stateless,不据此读历史

@dataclass(frozen=True)
class PaperAskResponse:
    session_id: str               # = request.session_id or 新生成
    message_id: str
    answer: str                   # wrapper: min_length=1, max_length=3000
    confidence: ConfidenceValue   # 复用 core Literal["high","medium","low"]
    citations: list[PaperAskCitation]
    follow_up_suggestions: list[str]   # wrapper: max_length=3; item 1..100
    is_fallback: bool = False
    fallback_reason: PaperAskFallbackReason | None = None

@dataclass(frozen=True)
class PaperAskCitation:
    source_id: str                # 单次响应内临时 ID(前端不得跨请求缓存做跳转)
    label: str
    excerpt: str | None           # document_extracted ⇒ 1..300; user_supplied ⇒ None
    source_kind: EvidenceSource   # document_extracted / user_supplied(不得伪装)
    target: PaperCitationTarget
```

**response 级不变量（wrapper + 服务端双重保证,写死）**:

```python
if is_fallback:
    assert confidence == "low" and citations == [] and fallback_reason is not None
else:
    assert len(citations) >= 1 and fallback_reason is None   # 非降级必须 ≥1 合法 citation
```

**`source_kind × excerpt` 交叉校验**:`document_extracted ⇒ excerpt 1..300`;`user_supplied ⇒ excerpt is None`。

**PaperCitationTarget 四种类**（精确以 520-A §3 / B2 已落 paperTypes.ts 为准）:`SectionTarget`(`result_section ∈ 五区块,不含 paper-equations`)| `EquationTarget`(`equation_id`)| `PlanMappingParameterTarget`(`origin="plan_mapping"`,`row_index>=0`,paper/model 名仅 label)| `MissingPromptParameterTarget`(`origin="missing_prompt"`,`prompt_id`,name 仅 label)。**不含** figure / spec_parameter / build_step / subsystem 细粒度跳。参数唯一键 = `origin + row_index` 或 `origin + prompt_id`;**名字 / symbol 只作 label / 诊断,绝不作匹配键**。**user_supplied 参数（已进 plan.parameter_mapping）→ PlanMappingParameterTarget（带 row_index）+ source_kind=user_supplied + excerpt=None。**

**`fallback_reason` 枚举**:`Literal["insufficient_evidence","invalid_or_missing_citations","citation_target_unresolved","out_of_scope"]`。**所有 wrapper 子模型 `extra="forbid"`**。

---

## §4 source_table 构造 + excerpt 来源 + LLM 约束 + 截断（C 自建,不复用 _prompt_builder）

**实测现状（R6,HEAD `e9ca8c1`）**:`_prompt_builder.py` 直塞 `raw_text` + 全量 JSON;**C 不复用**,自建截断版。

**source_table = 「可合法成为 citation 的证据单元」集合,每条编 `S?`、带 target**。来源映射:
- `spec.abstract` → `SectionTarget("paper-summary")`,**document_extracted**,excerpt=摘要原文截断(1..300)。
- `spec.equations[i]` → `EquationTarget(equation_id)`,**document_extracted**,excerpt=`latex_or_text` 截断。
- `spec.evidence[]`（document 侧,本就带 excerpt + locator）→ 映射到其支撑的合法 target（参数行 / equation / section,以现有 evidence 结构可可靠建立的为准,R6 核 `PaperEvidenceEntry` 字段）,**document_extracted**,excerpt=该 evidence excerpt。
- `plan.parameter_mapping[row_index]`：
  - `source == USER_SUPPLIED` 行 → `PlanMappingParameterTarget(row_index, paper_param_name, model_param_name)`,**user_supplied**,excerpt=None。
  - `source == DOCUMENT_EXTRACTED` 行 → 仅当能**可靠取得该行的 document excerpt**（经 §下「excerpt 来源红线」）才作 `PlanMappingParameterTarget` + document_extracted citation;**取不到则不作行级 document citation**（不入 source_table 作该 citation）。
- **remaining** `missing_prompts`（`resolved_prompt_ids(record)` 过滤后仍待填的）→ `MissingPromptParameterTarget(prompt_id, parameter_name)`,**user_supplied**,excerpt=None。
- paper-subsystems / paper-build-steps / paper-tuning section:其**可跳锚**以当前实际渲染内容为准（build_steps 非空用之,否则 `block_recommendations`;与前端 BuildSteps 降级同源）;但这些是**生成文本**,**不作 document excerpt 来源**——SectionTarget citation 仅在能追溯到底层真实 document evidence excerpt 时成立(见红线)。

**★ excerpt 来源红线（P0,来源不伪造）**:
- `document_extracted` 的 excerpt **只能**取自真实文档摘录结构（`spec.abstract` / `spec.equations[].latex_or_text` / `spec.evidence[].excerpt`）。
- **禁止**用任何 **plan 生成文本**（`subsystem_breakdown` / `build_steps` / `block_recommendations` / tuning 文本）或 `ParameterMapping.value` 等生成内容充当 document excerpt。
- 无法可靠映射到合法 target 或取不到合法 excerpt 的证据 → **不入 source_table**;若答案因此无任何合法 citation → `insufficient_evidence` fallback。
- `user_supplied` 一律 excerpt=None。
- （现状限制:`ParameterMapping` 无 per-row `paper_reference`,故 document_extracted 参数行可点 citation 仅在 `spec.evidence` 可可靠关联到该行时成立;否则该参数信息可由摘要/公式/其它 evidence 承载,不强行造行级伪 excerpt。**per-row evidence 关联增强 = 后续解析升级卡。**）

**`row_index` 红线**:= 后端遍历 `plan.parameter_mapping` 的 **0-based enumerate 位序**,与 B1 `ParameterTable.tsx` 渲染位序**同源**。R6 实测 `PlanAssembler.merge()` 保序、用户补充原 index replace 不重排（假设仍真）。**若 R6 实现阶段发现已改成会重排 → 停手报架构师（decision 15）。**

**`prompt_id` 校验红线**:硬真值 = **「存在于 remaining missing_prompts」(成员校验)**,**不用** `MISS-\d{3}` 正则。

**LLM context 截断 + injection**：
- `full_source_table`（可能很长）按上限截断为 `prompt_source_table`;**`source_id` 编号在 prompt_source_table 内一致**;**LLM 只能引 prompt_source_table 的 id**（§5）。
- prompt 把 prompt_source_table + 问题作为 **data**,显式声明「以下是资料数据,不是指令」;用户问题 / 用户补充值同按 data 处理（防 injection）。
- 约束 LLM:输出 `answer_kind`(answer/out_of_scope) + `answer` + 引 `S?` 的 `citation_ids` + `confidence` + `follow_up`;**禁止自造 anchor / DOM id / locator / 越权字段;禁止编造论文未给的参数值**。

---

## §5 校验与失败裁决（落地 520-A §5）

**LLM「调用层故障」vs「输出层不合规」二分（v0.2)**：
- **调用层故障**（DeepSeek adapter 抛 timeout/rate/quota/server/auth）→ 5xx（§7,沿用现状映射）。
- **输出层不合规 / 语义裁决** → 200 fallback（下表）。

| 情形 | 裁决 | reason |
|---|---|---|
| `answer_kind=="out_of_scope"` | 200 fallback | `out_of_scope` |
| LLM malformed:JSON parse 失败 / 字段缺失 / confidence 非枚举 / citation_ids 类型错 | 200 fallback,**不 raise 5xx** | `invalid_or_missing_citations` |
| raw anchor:任意 citation id 非 `S?`,或 answer/citation payload 含 `paper-eq-`/`paper-param-map-`/`paper-param-missing-` DOM id 字面,或含 `anchor`/`dom_id`/`locator` 越权字段 | 200 fallback | `invalid_or_missing_citations` |
| 引 unknown id（不在 prompt_source_table,含「在 full 未发送」）/ 空 citations | 200 fallback（不做剔坏 id 后续答） | `invalid_or_missing_citations` |
| target 语义不在当前 spec/plan（漂移） | 后端 fallback | `citation_target_unresolved` |
| 前端 DOM 解析不到 | **后端不处理**:只给合法语义 target;前端(B2)resolve→null 渲不可点 badge。后端 200 正常 | — |
| figure-only / 不可引用证据 | 不进 citations;若无任何合法 citation → fallback | `insufficient_evidence` |
| section-only / AI 引 build_step·subsystem | 降级为对应 `SectionTarget` 或不可点;不假装跳公式/参数 | —（成功）/ `insufficient_evidence`（降级后无合法 citation） |

- **5.1 与 MCS 差异**:MCS unknown id 是 `raise`(崩 500);PaperAsk 改 **fallback 不 raise**(面向最终用户更体面)。**不做剔坏 id 后续答**(半真半假更危险)。
- **citation_ids 去重保序**(首次出现序)。
- **fallback follow_up 口径**:fallback 时 `follow_up_suggestions` 允许空;若非空,不得暗示「资料里有但没找到」。
- fallback 文案口径:平实说「这份资料里没看到相关依据 / 当前解析结果里没找到能支撑的出处」,**不编、不暗示有但没找到**。

---

## §6 schema 同步面（decision 13 全清单 + 接 Makefile;C 最重合规面）

**先存缺口（本卡顺带修复,作 schema-hygiene 附带,PR / 完工报告单列以降噪）**:实测 `Makefile` `export-schema` 只跑 overview + bridge,`verify-schema` 只 diff overview + bridge —— **现有 5 个 `paper_*.schema.json` 从未接进 drift 闸**。C 接 paper_ask 时**一并把现有 5 个接进去**(工程门,走双审,不请示 PM;非改现有 schema 语义)。R6 内存字节比对:现有 5 个均 MATCH,接入无意外 drift。

1. **`scripts/export_paper_schemas.py` `OUTPUTS`** 加 `paper_ask_request.schema.json`→`PaperAskRequestSchema` + `paper_ask_response.schema.json`→`PaperAskResponseSchema`(现有 5 个保留;文件名独立不撞)。
2. **`Makefile`**:`export-schema` 追加 `python -m scripts.export_paper_schemas`(一次导出全部 7 个 paper schema);`verify-schema` 追加 **全部 7 个** paper schema 的 `git diff --exit-code`(现有 5 + 新 2)。**强制,无开放分支。**
3. **`test_paper_schemas_freeze.py`**:TOP_LEVEL/NESTED 列表加 PaperAskRequest/Response + citation + **四种 target variants** freeze;`extra=forbid`;`fallback_reason` / target `kind` / `origin` 的 Literal 集合 + `answer_kind` 不进对外 schema 的确认。
4. **`test_paper_schemas_sample_roundtrip.py`**:加 PaperAsk 样例 roundtrip,**至少覆盖** 正常多 citation / user_supplied citation / fallback response（各 reason 至少一条）/ request。**样例文字不得含模型参数值 / 倍率**。
5. **`docs/06_OUTPUT_CONTRACTS.md`**:加 PaperAsk 小节(citation target 四种类 / 失败语义 / 三层真值源铁律 / response 不变量 / excerpt 来源红线);仿现有 PaperSpec/Plan 小节格式。
6. **守门**:`git diff --exit-code schemas/*.schema.json`。**完工报告贴**:`export_paper_schemas.py` diff + `Makefile` diff + `paper_ask*.schema.json` diff + `make export-schema` 输出 + `make verify-schema` 输出 + `git diff --exit-code` 结果（现有 5 个接入作 hygiene 段单列）。
7. **TS 类型**(`paperTypes.ts`):加 PaperAsk 请求 / 响应 / citation;`citation.target` **引用 B2 已落 union,不重定义**;`pnpm typecheck` 守门。

---

## §7 错误码 / 日志隐私

**错误码矩阵（v0.2 对齐现状全局 handler;R6 实测）**:

| 场景 | 后端 |
|---|---|
| paper_id 不存在 / spec-only 无 plan record | 404 `paper_not_found`(前端文案可区分「资料在但未生成方案」,后端沿用) |
| bundle incomplete（plan 在 spec 缺） | 500 `store_error`（**不伪装 404**） |
| question 空 / 超长 / strip 后空 | 422 |
| LLM timeout | 504 |
| LLM rate limit | 429 |
| LLM quota | 503 |
| LLM server error | 502 |
| LLM auth error | 503 |
| LLM 输出层不合规 / out_of_scope / 无相关证据 / target 漂移 | 200 fallback（§5） |

（**不新增错误码 / 不做 PaperAsk 局部 LLM 映射**;以现有 `error_handler.py` + DeepSeek adapter 错误类型为准。）

**日志隐私（decision 11）**:只落 `paper_id` / error type / `fallback_reason` / citation count / unresolved（被剔）count / `answer_kind`;**不落** LLM raw output / document excerpt / 用户问题全文 / 源码 / token / claim / LLM 正文。**禁 `logger.exception`**;异步阻塞按 decision 11（`to_thread` 按需,沿用现有 paper 调用模式）。

---

## §8 验收标准（可跑命令 + 贴证）

- [ ] `make check` 全管道绿。
- [ ] **schema 同步面**:`make export-schema` + `make verify-schema` 绿（含新接 paper export + 全部 7 个 paper diff）;`git diff --exit-code schemas/*.schema.json` 零 diff;贴 §6.6 全部 diff + 命令输出（现有 5 个接入单列 hygiene 段）。
- [ ] `pytest tests/features/paper/test_paper_schemas_freeze.py tests/features/paper/test_paper_schemas_sample_roundtrip.py` 绿（含 PaperAsk freeze + 四种 target + 样例 roundtrip）。
- [ ] **API route serialization 测试**:request 422（空 / 超长 / strip 后空 question）/ extra forbid（请求或响应塞非契约字段被拒）/ 正常多 citation 响应 / fallback 响应（各 reason 至少一条,含 out_of_scope）。
- [ ] **service 单测**（覆盖 §5 每条 + v0.2 新增）:
  - 5.1 unknown id fallback-not-raise;**`S99` 在 full、被截断排除、LLM 引 `S99` → fallback**（prompt_source_table 校验,P1-1）。
  - LLM malformed（JSON parse 失败 / confidence 非枚举 / citation_ids 类型错）→ 200 fallback,不 5xx（P1-3）。
  - `answer_kind="out_of_scope"` → 200 fallback `out_of_scope`（P1-3）。
  - raw anchor（citation id 非 `S?` / payload 含 DOM id 字面 / 越权字段）→ fallback（P1-4）。
  - 5.2 target 漂移 → `citation_target_unresolved`;5.4 figure-only → `insufficient_evidence`;5.5 section 降级。
  - **excerpt 来源**:document_extracted citation 的 excerpt 来自真实文档摘录;plan 生成文本（subsystem/build_steps/block_recommendations/tuning）/ mapping value **不得**充当 excerpt;无合法 excerpt 的 document 证据不进 source_table（P0）。
  - **missing remaining**:已补参数（进 plan）不再作 MissingPromptParameterTarget;仅 remaining set 作之（P1-b）。
  - **user_supplied 参数** → PlanMappingParameterTarget + source_kind=user_supplied + excerpt=None。
  - response 不变量两分支;**citation_ids 去重保序**（P2-1）;fallback follow_up 口径（P2-4）。
- [ ] **`pnpm typecheck` 绿**:paperTypes.ts PaperAsk 类型镜像;`citation.target` 引用 B2 union 不重定义。
- [ ] **三层真值源核**:后端 grep 确认无 `paper-param-map` / `paper-eq-` / `paper-param-missing` 等 DOM id 字面;后端只给语义 target。
- [ ] **隐私核**:日志不含 excerpt / 问题全文 / LLM 正文（decision 11）。
- [ ] **feature 边界核**:`features/paper/paper_ask_*` 不 import overview/explanation/chat 私有;`ConfidenceValue`/`EvidenceSource` 来自 core。

---

## §9 风险与注意点

- **三层真值源是命脉**:后端给 anchor / DOM id、或前端被迫信任 target 一定有 DOM,都出死链。
- **excerpt 来源（P0)**:document_extracted excerpt 只来自真实文档摘录;**AI 生成文本绝不充当 document excerpt**;现状 document_extracted 参数行可点 citation 受限于 spec.evidence 可关联性（per-row evidence 增强是后续卡）。
- **LLM 调用层 vs 输出层二分**:故障 5xx,输出不合规 200 fallback;别把 malformed 输出崩成 5xx,也别把网络故障当 fallback。
- **`row_index` 稳定性**:依赖 `PlanAssembler.merge()` 不重排（R6 实测仍真);实现阶段复核,否则停手报架构师。
- **`prompt_id` remaining set**:用 `resolved_prompt_ids(record)` 过滤,非 raw `record.missing_prompts`。
- **`build_steps=None` 降级**:section 可跳锚以实际渲染（build_steps 或 block_recommendations）为准;二者皆生成文本,不作 excerpt 来源。
- **prompt_source_table 校验**:只校截断后实际发送的表,防 full/截断混用误判。
- **Pydantic nested union**:parameter 两变体共享 kind,须嵌套 union / 显式 validator,freeze + roundtrip 锁四种 target JSON。
- **user_supplied 不伪装 document**:进 plan 的用户补充给 PlanMappingParameterTarget 但 source_kind=user_supplied + excerpt=None;交叉校验兜住。
- **injection / 截断不复用现有 builder**:自建 source_table context 截断 + data-not-instruction;必须有上限。
- **LLM 错误映射**:沿用现状 handler + DeepSeek adapter 错误类型,不造新错误类、不局部改对外码。
- **stateless 不可被误导**:`session_id` 仅回显;后端不据此读历史。

---

## §10 给 Codex 的提示

- 实现阶段 Stage 0 复核最新 origin/main HEAD,从 live 切新分支。
- domain：core dataclass + features/paper wrapper,**不** import overview/explanation/chat 私有;`ConfidenceValue` 复用 `core/domain/paper_tuning.py`,`EvidenceSource` 复用 `core/domain/paper_evidence.py`。
- **wrapper 默认值**:`session_id: str|None=None` / `is_fallback: bool=False` / `fallback_reason: ...|None=None`（别让 session_id 成必填致合法请求 422）。
- **Pydantic target union**:不得单层 `Field(discriminator="kind")` 包四类;parameter 两变体用嵌套 union（顶层 kind,parameter 内层 origin）或显式 wrapper/validator;freeze + roundtrip 锁四种 target JSON。`answer_kind` 是 **LLM 内部响应 schema**,不进对外 PaperAskResponse / 不进导出 schema。
- schema 同步严格按 §6（含强制接 Makefile + 顺带修复现有 5 个,作 hygiene 段单列）;显式补 `make export-schema` + `make verify-schema` + `git diff --exit-code` + `pnpm typecheck`。
- LLM 调用复用现有 paper 通道（DI 拿 `TextProvider`,底层 `DeepSeekTextProvider`,`to_thread + chat(json_mode=True, timeout, max_tokens)`）+ `_prompt_loader.load_prompt_template` 模式;prompt 内容新写（data-not-instruction + prompt_source_table 引用约束）,**不复用 `_prompt_builder` 的 raw/full JSON 直塞**。
- 可复用件（R6 列）:`PaperBundleStore`、`TextProvider`、`_prompt_loader`、`EvidenceSource`、`ConfidenceValue`、`resolved_prompt_ids`、`MISSING_VALUE_SENTINEL`、`EvidenceTagger` 双源校验思路。**不 import `features.chat.*` / `SourceRefDTO`**;ChatService 的 source_id→source_table→citation_ids 只借口径不复用实现。
- route 仿 `api/routes/paper_tuning.py`（POST + store + service）;错误映射用现有 `error_handler.py`（PaperNotFoundError/StoreError 已有;LLM 错误类型沿现状）。
- 行尾 / 异步 / 日志照 decision 20 / 11;改已存在文本文件保留原始字节（decision 08:`read_bytes`/`write_bytes`,禁 `read_text`/`write_text`/`sed -i`)。本机无 `grep`,用 `git grep` / `rg` / `Select-String`。
- 派单前 PM 预放本卡到 `docs/tasks/`,列进 Stage 0 baseline 白名单 + 允许 diff 清单。
- 完工三件套（decision 08）+ 代码 PR 与索引收尾 PR 分开走（decision 07）;子卡完工 520 仍 🔍、整数不 +1。
