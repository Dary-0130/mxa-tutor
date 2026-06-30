# TASK-521-B1: Paper 多文件 · 多篇上传 + 逐篇解析 + 融合成一份 PaperSpec(v0.3)

## 本版改动(v0.2 → v0.3;并 R1=GPT 定向复审 2×P1 + R6=Codex 真 repo 实测发现 + plan provenance 引用桥设计;**无新产品决定**;唯一 PM 接触仍 = §7 部分成功体验知会)

**R6 实测核心发现 → 触发 plan provenance 引用桥设计(§3.5 重写)**
- Codex 实测确认:现状 plan 链路(`_llm_plan_compose`/`_llm_missing_detect`/`_llm_build_steps`)的嵌套 evidence document_id 由 `enrich_single_document_evidence_payloads` **按 source 盲注 `DOC-001`/None**,**不是从被引 spec 项推导**;且 `PaperEvidenceEntry` 只存平铺 locator、`ModelGenerationPlan` 嵌套 evidence **无「引用了哪条 spec evidence/equation/figure」的外键**;`equation_id`/`figure_id` 加 document_id 后可建映射但**跨篇会撞**、`paper_section_id` 无持久列表无法回查 document。**故 v0.2 的 B-ii「从被引项确定 document_id」按现状不可直接落,必须先补一个确定性引用桥**(见 §3.5)。这道检查在实现前逮住,正是 §3.5 Stage 0 gate 的目的。
- **plan helper 现状是全局 locator 白名单**(`allowed_sections` 取自 `spec.evidence[*].paper_section_id`、`allowed_equations`/`allowed_figures` 取自 spec.equations/figures),**非 per-doc**;多篇下必须改 per-doc((document_id, locator) 复合)。
- 现状 spec **enrich + 迁移只覆盖 parameter/evidence、未覆盖 equations/figures**;`save_ready_bundle`(经 `_dump`)/ `get_spec`·`get_plan_record`(经 `_load_spec_with_migration`)/ `set_plan` 都调 `validate_paper_spec_document_identity`,本卡把 equations/figures 纳入 validator 后这些边界能覆盖,但**迁移函数 + single-doc enrich 必须扩**。
- `paper_ask_service.py` 仍有给 abstract/equation citation 用 `DEFAULT_DOCUMENT_ID` 的单文档假设,多篇下要跟随调整。
- DOC id gap **现状已满足**(validator 只校 pattern + unique、无连续性假设);上传沙箱/清理 try/finally 每请求隔离、可逐篇复用,但**多文件 API/融合编排尚不存在、需新增外层逐篇流程**。

**R1=GPT 定向复审 2×P1(措辞加硬,GPT 判定通过不升 R2)**
- **[P1-1]** plan evidence「丢弃」语义补守门:**丢弃不确定 evidence 后,必须重跑 plan/missing/嵌套 evidence 的 schema 与 provenance 校验;若任何 required evidence 位被清空、或 plan 级 evidence 不满足最小数量(06 §12.5:plan.evidence 至少 1)/ 出处不变量 → 不得保存 ready bundle,应 retry / fail-fast / 返回脱敏错误;禁止以「空 evidence plan」降级通过**。即「丢弃」严格限定为局部 pruning 且剩余结构仍合法。(见 §3.5)
- **[P1-2]** §3.3 读回期校验区分 equation/figure 与 section;验收「跨篇误指」改三段式(抽取期 / 融合期 / 读回期)。(见 §3.3★ + §5)

**v0.2 已并的 R1 方案裁决 A–E(沿用)**:A=A1 复合键(canonical 不改写)/ B=B-ii 去兜底(本版加引用桥落地)/ C=主篇·首个成功篇代表值 / D=部分成功五行表 + DOC gap / E=`primary_index`。

## 状态
🔲 v0.3(已并双审全部意见 + 引用桥设计)→ **派 Codex 实现**;Codex Stage 0 **先确认 §3.5 引用桥在真 plan 代码里搭得起来**(报取证 → 架构师确认 → 再实现;若引用桥按现状无法干净落,**停手报架构师**)。高风险卡(LLM + 新引用契约 + 后端 schema + 多篇编排),**合并前架构师亲核真 diff + decision 13 全清单 + 对外 zero-diff**。

---

## 1. 这张卡是什么 / 不是什么

**是**:把「只能传单篇」的上传→抽取→(同请求)生成 plan→落库管线,改成「能传多篇 → 逐篇独立抽取 → 后端融合成**一份**带 `documents` 的 PaperSpec → plan 从融合 spec 生成、且每条 plan 依据**正确标到来自哪篇**(经 §3.5 引用桥)→ 部分成功如实表达」。补齐 06 §12.4 的 locator 复合命名空间(A1)。

**不是**(明确排除):
- ❌ 值冲突**检测** / `ParameterConflict` / conflict_report —— 留 521-B2(本卡只留底座:同名参数多来源值**不去重**)。
- ❌ 对外 `PaperAskCitation` / `paper_ask_response.schema.json` 加 document 维度 —— 留 521-C(本卡 ask 端内部解析改复合、但**不带出对外 DTO**)。
- ❌ 前端多选上传 / 主文献勾选 / 文件来源展示 —— 留 521-D。
- ❌ 碰工程文件(.zip,MCS 线)、表格 / 代码类解析。
- ❌ 让 LLM 产 document_id / 做跨篇归属 —— document_id 一律后端注入 / 后端从引用桥解析(沿 521-A 红线)。
- ❌ per-doc abstract / metadata 冲突裁决 / 把 plan 链路做超出「证据正确归篇」的更深多篇重构。
- ❌ 改已合并产物行为(追问 B1/B2/C/D 前端、MCS、其它后端);改 = PM 拍 + 审。

---

## 2. 产品决定(PM 已拍,本卡不重开)
- 多文件 = 多篇文档(PDF / DOCX);一主多辅,主文献可选;主文献是**主次身份、非可信度权重**:不因「是主文献」让 AI 信它更多,值冲突如实呈现、绝不静默挑。
- 两点目标:多篇信息互相补充 + 综合多篇辅助推理。
- 红线:① 参数值只给有出处的、来源不伪造;② 综合多篇推出、无单一出处的结论放回答正文讲,**不挂可点击假出处**;③ 同名参数多来源值如实保留、**不静默去重**(冲突检测在 B2)。

---

## 3. 范围(必须做)

### 3.1 上传入参:单 → 多
- [ ] `POST /api/v1/upload-document` 接受**多篇** `UploadFile`;**向后兼容**(单篇 = 长度 1 的列表;现有单篇前端 521-D 前继续可用、不被改挂)。**多文件 API / 融合编排是新增外层流程**(R6 确认现状是单文件 endpoint)。
- [ ] **`primary_index`**(optional form field):不给 = 无主;校验 `0 <= primary_index < len(files)`,越界 / 非法 → 4xx。后端**先按上传序分配 DOC**,再映射 `primary_index → primary_document_id`(对应 DOC)或 None。禁 `primary or documents[0]` 折叠首篇。
- [ ] **DOC id 按上传原始顺序预分配、允许 gap**(R6 确认 validator 现状即允许 gap):第 2 篇失败 → 成功篇 `DOC-001` + `DOC-003`,不重排;`primary_index`/per-doc 状态/日志因此稳定。
- [ ] **篇数 / 体量 / 并发上限**(实施定):单篇格式/魔数/体量校验沿用现状、**逐篇**施加;总篇数硬上限(建议 ≤5);`MAX_PAPER_RAW_TEXT_CHARS`(现状 80_000)**逐篇** fail-fast;多篇抽取串行或 bounded concurrency(**并发上限实现定**);**失败清理逐篇隔离**(沿用现状每请求 try/finally 沙箱清理,逐篇复用,一篇失败不污染其它篇)。

### 3.2 逐篇解析 + 逐篇抽取 → 融合
- [ ] **抽取模型 = 逐篇独立一次 LLM 调用**(R6 确证);多篇 = 各抽各的再后端融合,不拼多篇文本一次喂 LLM。
- [ ] **逐篇 enrich 注入身份**(R6:现状 enrich 是按 source 盲注 `DOC-001`,**必须扩**):扩展 `enrich_single_document_spec_payload` / `enrich_single_document_evidence_payloads` 为「按上传序分配该篇 DOC 号(支持 gap)」;该篇所有 `document_extracted` 证据 / 参数 / **公式 / 图**(见 3.3)的 document_id = **该篇 DOC 号**;`user_supplied` 一律 None。**LLM 不产 document_id**。
- [ ] **融合成一份 PaperSpec**:
  - `documents` = 每篇**成功解析**的 doc 各一条(预分配 DOC 号 + 清洗显示名);**只列成功篇**。
  - `primary_document_id` = `primary_index` 映射 或 None。
  - **单值顶层字段**(`paper_title`/`paper_type`/`domain`/`abstract`):有主取主篇;**无主取首个成功解析篇**(非上传首篇)。`domain` 取单一代表域,**不裁决多篇领域冲突**(v0 代表值,卡内写明)。其余篇 abstract / intro **仅当能形成真实 locator + excerpt** 时作 `document_extracted` evidence、**不为不丢而造**。
  - **列表字段**(`equations`/`parameter_table`/`figure_locations`/`pseudocode_blocks`/`evidence`):跨篇拼接,每条带各自 document_id;**同名参数多来源值不去重**(各保留 document_id;为 B2 留底座)。

### 3.3 locator 复合命名空间(A1;06 §12.4 硬门槛)
- [ ] **结构补全**:给 `EquationEntry` + `FigureRef` 各加 `document_id: str | None`(`document_extracted` 必填且 ∈ documents)。同步:domain(同位同序)+ `EquationEntryModel`/`FigureRefModel` + `PaperSpecModel` after-validator + 跨结构 helper `validate_paper_spec_document_identity`(R6:现只校 evidence/parameter,**扩到 equations/figures**)+ schema 重导出 + freeze + TS。
- [ ] **canonical locator 保持解析器原值、逐篇不改写**(A1):合法性 / 解析按 `(document_id, locator_id)` 复合判;**允许**派生内部唯一 key(`make_locator_key(document_id, locator_id)` / source_table key / 展示 key),**禁回写** canonical 字段。
- [ ] **抽取期校验逐篇**:现状 `_validate_locator_whitelist(spec_片段, parsed_该篇)` 对**该篇** parser 白名单校验(不变);通过后融合层 stamp 该篇 DOC 号。
- [ ] **plan 链路 locator 校验改 per-doc**(R6:现状全局白名单):plan 嵌套 evidence 的 locator 合法性按 `(document_id, locator)` 复合判;`allowed_equations`/`allowed_figures` 从持久化 `equations[]`/`figure_locations[]` 按 document_id 派生 per-doc 集合。
- [ ] **★ section 真值来源 + 读回期校验区分(R1 P1-2;R6 确认)**:
  - `equation_id` / `figure_id` 可从持久化 `equations[]` / `figure_locations[]`(加新 document_id)按 doc 派生 per-doc 集合;**`paper_section_id` 无独立持久列表**(parser `ParsedLocatorIndex.section_ids` 抽取期瞬态、不持久化)。
  - **读回期校验**:equation / figure locator **可**按持久化结构集合复校;**section locator 读回期仅解析已持久化 evidence / source_table candidate 中出现的 `(document_id, paper_section_id)`,不支持对任意 section id 做白名单 membership 复校**;section 的 parser 白名单合法性**只在抽取期**保证。读回期 helper 校验 document_id 一致性(各项 document_id ∈ documents + source 规则)。
  - ⚠ **R6 复核**:若验收确需读回期复校任意 section membership,最小备选 = `PaperDocument` 持久化 per-doc `section_ids`(结构更大,本卡不取,除非 R6 判定必要)。
- [ ] **内部 source_table / ask 端 locator 解析改复合**(R6:现状 `paper_ask_service.py` 有 `DEFAULT_DOCUMENT_ID` 单文档假设,需调整):equation/section candidate 合法性与归属按 `(document_id, locator)` 判;非 evidence 派生的 candidate(abstract/equation)取其所属 document 的 DOC 号。**`to_citation()` 仍不带出对外**(对外复合 locator 留 521-C)。

### 3.4 部分成功(⚠ 产品体验含义 → PM 一句知会,见 §7)
逐篇 parse / extract,收每篇状态(succeeded / failed + 脱敏原因码),按下表:

| 场景 | 结果 |
|---|---|
| 指定主篇,主篇失败 | **整体上传失败** |
| 指定主篇,主篇成功,辅篇部分失败 | 继续,用成功篇融合;响应报告失败辅篇 |
| 未指定主篇,**至少 1 篇成功** | 继续,用成功篇融合;`primary_document_id = None` |
| 未指定主篇,**全部失败** | **整体上传失败** |
| `primary_index` 越界 / 非法 | **4xx 拒绝** |

- **无主语义 = 几篇平等**,不写成「无主时任一篇失败即整体失败」。
- per-doc 状态进 `UploadDocumentResponse`、**不进 PaperSpec**;`documents` 只列成功篇;失败原因脱敏,不落 filename / 原文 / 源码(decision 11)。
- **部分成功下 plan / prompt / source_table 只含成功篇**;失败篇不得出现在其中。

### 3.5 plan 生成 + provenance 引用桥(★ 本版重写;R6 实测驱动 + R1 P1-1)
**目标(B-ii,GPT 裁决)**:plan 从融合 spec 生成;plan 嵌套 evidence 的 document_id **必须从被引 spec 项确定**;不可确定 → 不作 `document_extracted` evidence、fail-fast / 丢弃 / 降级,**禁兜底 primary/None**。
**R6 发现**:现状无可追桥、enrich 盲注 DOC-001 —— 故须补一个**确定性引用桥**:
- [ ] **引用桥(沿用 paper_ask source_table 引用模式,不另造范式)**:给 plan LLM 的上下文渲染**后端编号的 doc 限定标签**(形如 `[S?]` / 复合 key,映射 `(document_id, locator_kind, locator_id, 文件显示名, 摘录)`,如 `DOC-002 / EQ-01 / 文件名 / 摘录`);plan LLM 在其 evidence 里**引用后端给的标签**,**不**直接产 document_id;后端把标签解析回 `(document_id, canonical locator)` 并据此给该条 plan evidence stamp document_id。document_id 来自**后端的标签→doc 映射**(后端拥有),非 LLM 杜撰 —— 不破「LLM 不产 document_id」「locator 只来自解析器白名单」红线。
- [ ] **不可解析即丢弃 + 守门(R1 P1-1)**:LLM 引到无法解析回单一 `(document_id, locator)` 的标签 → 该 evidence **不作 document_extracted、丢弃**。**丢弃后必须重跑 plan / missing / 嵌套 evidence 的 schema + provenance 校验**:若任何 required evidence 位被清空、或 plan 级 evidence 不满足最小数量(06 §12.5 plan.evidence ≥1)/ 出处不变量 → **不得保存 ready bundle**,应 retry / fail-fast / 返回脱敏错误;**禁止「空 evidence plan」降级通过**。
- [ ] ⚠ **Stage 0 必核(派单 gate)**:Codex 先确认本引用桥在真 plan 代码(`paper_plan_service.py` 各 `_llm_*` + `_prompt_builder.py` plan 部分 + plan 校验链)里**搭得起来**(标签注入点 / LLM 引用回收 / 解析回 doc 的落点);报取证 → 架构师确认 → 再实现。**若引用桥按现状无法干净落,停手报架构师,不得用 DOC-001/primary/None 兜底硬上。**

### 3.6 存储 + 老数据读回迁移(R6 确认迁移现状未覆盖 equations/figures)
- [ ] 融合后仍是**一份** PaperSpec blob + 一份 plan blob,存储路径不变;**不加新持久结构**(`ParameterConflict` 留 B2)。
- [ ] **读回迁移扩到 equations/figures**:521-A 的 `_add_missing_document_ids_to_spec_evidence` / `_add_missing_document_ids_to_parameters` 只迁 evidence/parameter;本卡**新增**老 spec blob 里 `equations[]` / `figure_locations[]` 的 document_id 注入(`document_extracted` 注 `DOC-001`),沿 521-A 唯一迁移入口 `_load_spec_with_migration`,**不只补新写路径**。
- [ ] `save_ready_bundle`(`_dump`)/ `get_spec`·`get_plan_record`(`_load_spec_with_migration`)/ `set_plan` 现都调 `validate_paper_spec_document_identity`(R6 确认);本卡 equations/figures 纳入 validator 后这些边界自动覆盖 —— 但**迁移函数 + single-doc enrich 必须同步扩**。

### 3.7 schema / freeze / eval / prompt / TS 同步(decision 13 全清单;R6 已列入口清单)
- [ ] schema 导出:`make export-schema` + `make verify-schema` 零 diff;受影响 `paper_spec.schema.json`(EquationEntry/FigureRef + document_id);**`paper_ask_response.schema.json` 本卡不变**。
- [ ] freeze:EquationEntryModel/FigureRefModel 加 document_id 的字段顺序 + required-vs-nullable(缺失 fail / None pass);多篇融合 round-trip;locator 复合不变量;DOC id gap 测(`DOC-001`+`DOC-003` 通过);NESTED_MODELS 计数不变。**R6 已确认 freeze 现有断言**(`tuple(EquationEntryModel.model_fields) == fields(EquationEntry)` 等)随字段加而需更新。
- [ ] **prompt(R6:多处固化「3 字段」)**:`paper_spec_extract.yaml` 的 equations/figures「3 个字段」硬约束改(document_id 后端注、LLM 不产);`_prompt_builder.py` / plan prompt 的 `DOC-001` 单文档措辞改为 **doc 限定复合标签**(§3.5);⚠ Stage 0 逐项核字段数。
- [ ] **eval golden**:现有单篇 golden 随 equations/figures 加 document_id(扩展后的单篇 enrich 注 `DOC-001`);**新增一例多篇融合 golden**(含跨篇同名 locator,R6 实测期出最小 fixture)。R6 已列受影响 golden/fixture/test 文件清单(见附)。
- [ ] **`UploadDocumentResponse` 新增 per-doc 状态字段**:现状 `{paper_id, spec, plan, missing_prompts}` 且 `extra="forbid"`;新增 per-doc status 是 API shape 变化 → TS / schema / 测试同步;**标注向后兼容风险**。
- [ ] TS:`paperTypes.ts` 的 `EquationEntry`/`FigureRef` 加 `document_id: string | null`(不设 optional);`UploadDocumentResponse` 镜像加 per-doc 状态;`pnpm typecheck`/lint/build 绿;**无 UI 改动**(展示 521-D)。

### 3.8 工程守则
- [ ] decision 08:改文本文件保留原始字节 / 行尾。decision 11:不 `logger.exception`;filename / 原文 / per-doc 失败原文不落日志;异步阻塞 `to_thread` 按需。decision 21:跨层只经 core 公开契约;`features/paper` 不 import overview/explanation/chat 私有;跨结构校验经 core helper。

---

## 4. 接口契约(本卡定义的增量)

### EquationEntry / FigureRef 增量(新)
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `document_id` | string \| null | `document_extracted` 必填且 ∈ documents;(本结构无 user_supplied) | 该公式 / 图来自哪篇 |

### UploadDocumentResponse 增量(⚠ 以 Stage 0 实测现状形状为准扩展)
| 字段 | 类型 | 语义 |
|---|---|---|
| per-doc 状态数组 | array | 每篇 succeeded/failed + 脱敏原因码 + DOC 号(按上传序、允许 gap)+ 清洗显示名 |

### 不变量汇总(在 521-A 基础上新增 / 收紧)
- `EquationEntry`/`FigureRef` document_id:`document_extracted` 必填且 ∈ documents(core helper 校验)。
- locator 保持解析器原值;合法性按 `(document_id, locator_id)` 复合;派生唯一 key 仅内部、不回写 canonical。plan 链路 locator 校验 per-doc。
- DOC id 按上传原序预分配、允许 gap;helper 只保 pattern + 唯一、不要求连续。
- `documents` 只列成功篇;`primary_document_id` 无主为 null、不折叠首篇;主篇文件失败 → 整体失败。
- plan 从融合 spec 生成;plan 嵌套 evidence document_id 经**引用桥**从被引项确定;不可确定即不作 document_extracted、**禁兜底 primary/None**;**丢弃后重校,空 evidence / 缺 required 位 → 不存 bundle、fail-fast**。
- 同名参数多来源值不静默去重(各保留 document_id;冲突检测 B2)。
- 综合推理无单一出处不挂 citation、不伪造 `DOC-ALL`;document_id 后端注入 / 后端从引用桥解析、LLM 不产;filename 仅展示、不落日志。
- 对外 `PaperAskCitation` / `paper_ask_response.schema.json` 本卡零 diff(对外复合 locator 留 521-C)。
- section 白名单瞬态、不持久化;读回期 equation/figure 可结构集合复校、section 仅解析已持久化的 `(document_id, paper_section_id)`、不复校任意 membership(§3.3★)。

---

## 5. 验收标准(可跑命令 + 贴证)
- [ ] 传两篇(各有同名 `S1`/`EQ-01`)→ 一份 PaperSpec:`documents` 两条(`DOC-001`/`DOC-002`)+ 真实清洗文件名;evidence/parameter/equations/figures 各带正确 document_id;canonical locator 保持原值;同篇 locator 解析通过。
- [ ] 传单篇 → 仍得 `DOC-001`;equations/figures 也注 `DOC-001`(扩展后单篇 enrich)。
- [ ] `primary_index` 给 → `primary_document_id` 指对应 DOC;不给 → None;越界/非法 → 4xx;**主篇文件失败 → 整体失败**(不静默改首成功篇)。
- [ ] 部分成功:辅篇失败 → 带成功篇返回、per-doc 状态如实报(DOC 号允许 gap、原因脱敏);无主 + ≥1 成功 → 继续、primary=None;主篇 / 全失败 → 整体失败。
- [ ] DOC id gap:第 2 篇失败 → 成功篇 `DOC-001`+`DOC-003`,helper 不因不连续 fail。
- [ ] **plan provenance(引用桥)**:多篇 plan 从融合 spec 生成、嵌套 evidence document_id 经引用桥从被引项确定且**归对篇**;构造「LLM 引到无法解析的标签」→ 该 evidence 被丢弃 + **重校**;构造「丢弃后 plan evidence 空 / 缺 required 位」→ **不存 bundle、fail-fast / 脱敏错误**,**全程无 DOC-001/primary/None 兜底**;失败篇不出现在 plan/prompt/source_table。
- [ ] 同名参数多来源值**不被去重**(各保留 document_id)。
- [ ] **跨篇误指三段式**:**抽取期**——某篇片段引用本篇 parser 白名单外 section/equation/figure → fail;**融合期**——每片段只 stamp 本篇 DOC、LLM 无跨篇 document_id 入口;**读回期**——helper 拒 document_id 规则违例;**section 不做白名单成员复校**(equation/figure 可按持久结构集合复校)。
- [ ] 老 spec blob(缺 equations/figures document_id)读回迁移注 `DOC-001`、不炸;新多篇 blob round-trip 不变。
- [ ] `make export-schema` + `make verify-schema` 零 diff;`paper_spec.schema.json` 含 EquationEntry/FigureRef document_id;`paper_ask_response.schema.json` 未变。
- [ ] freeze 全绿(含 EquationEntry/FigureRef document_id 顺序 + required-vs-nullable + 多篇 round-trip + locator 复合 + DOC gap)。
- [ ] `make check` 后端全绿(含 R6 列出的全部入口同步:direct constructor / eval golden / prompt 字段数 / UploadDocumentResponse / plan helper per-doc)。
- [ ] `pnpm typecheck`/lint/build 绿(仅类型,无 UI)。
- [ ] `docs/06_OUTPUT_CONTRACTS.md` §12 同步:EquationEntry/FigureRef document_id;locator 复合命名空间「前瞻」→「已落」(A1,原措辞保留);部分成功 + DOC gap;同名多源不去重;plan evidence 引用桥 + 不兜底 + 丢弃后重校;section 读回期校验口径(P1-2);domain 单一代表值不裁决冲突。
- [ ] decision 13 全清单逐项在 PR 说明列出;对外 citation 明确 defer 521-C,冲突检测明确 defer 521-B2。

---

## 6. 风险与注意点
1. **plan provenance + 引用桥是最大 P0**:plan evidence document_id 必经引用桥从被引项确定;不可确定即不作 document_extracted、丢弃 + 重校,**禁兜底 primary/None**;空 evidence/缺 required 位不存 bundle。⚠ 引用桥可落性 Stage 0 必核,无法干净落停手报架构师。
2. **plan helper 改 per-doc**(R6:现状全局白名单);locator 校验按 `(document_id, locator)`。
3. **section 真值来源**(R1 P1-2 + R6):parser section 白名单瞬态;读回期 equation/figure 可结构集合复校、section 不复校任意 membership;R6 复核取舍。
4. **入口覆盖(承 521-A 教训,R6 已列清单)**:EquationEntry/FigureRef 加 required-but-nullable document_id 后,所有 direct constructor / eval golden / fixture / 反序列化点 / 迁移函数 / single-doc enrich 都要补,否则 validate 炸。
5. **单篇向后兼容**:多文件 API 是新增外层流程,不得挂掉现有单篇前端(521-D 前)。
6. **DOC id gap**:按上传序预分配、允许 gap;helper 不要求连续。
7. **多篇成本 / 超时**:总篇数 ≤5、逐篇 raw_text 上限、并发上限实现定、失败清理逐篇隔离。
8. **abstract / metadata 融合**:不拼造融合摘要;余篇摘要仅在有真 locator+excerpt 时进 evidence;`domain` 单一代表值不裁决多篇冲突。
9. **UploadDocumentResponse 兼容**:新 per-doc 字段是 API shape 变化,TS/schema/测试同步 + 向后兼容标注。
10. **paper_ask 单文档假设**(R6):`DEFAULT_DOCUMENT_ID` 给 abstract/equation citation,多篇下随调整(内部维度,不带出对外)。

## 7. PM 接触(知会一处,非拍)
- **部分成功体验**:本卡建议「传多篇时,主文献能读、辅篇有一篇读不了,系统继续用能读的篇生成结果并在响应里告知哪篇失败;主文献失败或全失败才整体失败」。给 PM 一句大白话知会 +「建议按这个来、不满意说」,不要他拍机械实现。
- 其余(拆 B1/B2、locator 机制、plan 引用桥、字段边界、API 形状、存储落点、DOC gap)= 实施形状,走双审,不烦 PM。(`domain` 单一代表值若将来前端要展示「本资料包领域 = X」,那是 521-D 文案问题,届时 PM 看一眼。)

## 8. 给 Codex 的提示(派单实现阶段)
- Stage 0 取 live origin/main HEAD,从 live 切新分支。**首要 gate:确认 §3.5 引用桥在真 plan 代码(`paper_plan_service.py` 各 `_llm_*` + `_prompt_builder.py` plan 部分 + plan 校验链)搭得起来**(标签注入点 / LLM 引用回收 / 解析回 doc 落点);报取证 → 架构师确认 → 再实现;**无法干净落停手报架构师,不得 DOC-001/primary/None 兜底**。其余 Stage 0:`EquationEntry(`/`FigureRef(` 构造点 + locator id 产出点 + upload route/parser/extract/bundle store/迁移函数/single-doc enrich 现状,与本卡假设逐条比对,不符停手(decision 15)。
- document_id 一律后端注入 / 后端从引用桥解析(扩展 `enrich_single_document_*` 为「按上传序分配 DOC 号、支持 gap」+ 覆盖 equations/figures;plan 经引用桥);LLM 不产 document_id、不做跨篇归属。
- canonical locator 不改写;允许派生 `make_locator_key`/source_table key,禁回写 canonical;合法性按 `(document_id, locator)` 复合;plan helper 改 per-doc。
- 跨结构 helper `validate_paper_spec_document_identity` 扩到 equations/figures;所有边界(Pydantic to_domain / SQLite 读回 / 融合组装 / save)调用;helper 只保 pattern + 唯一、**不要求连续**;domain 不加 post_init。
- plan 从融合 spec 生成;喂 plan LLM 渲染 doc 限定复合标签;plan evidence document_id 经引用桥确定,不可确定即丢弃 + 重校,空/缺位不存 bundle、fail-fast。
- 读回迁移扩到老 spec blob 的 equations/figures document_id(沿 `_load_spec_with_migration`)。
- 改 schema 后 `make export-schema` + `make verify-schema` 零 diff(`paper_ask_response` 不应变);freeze + eval golden(含多篇 fixture)+ prompt 字段数 + UploadDocumentResponse 同步。
- 行尾/字节(decision 08)、异步/日志(decision 11,filename 与 per-doc 失败原文不落日志);本机无 grep 用 git grep / rg / Select-String。
- 完工三件套 + decision 13 全清单逐项在 PR 说明列出;**任务卡随代码一并 add 进同一代码 PR、索引收尾走单独 PR**(decision 07);子卡完工 521 整数不 +1。

**修订历史**:v0.1(架构师起稿,以 E 组 live 结构 + 06 §12 + 521-A 卡为据)→ v0.2(并 R1=GPT 方案讨论裁决 A–E + 9 条风险加硬)→ **v0.3**(并 R1 定向复审 2×P1 + R6 真 repo 实测发现 + plan provenance 引用桥设计;无新产品决定;派单 Stage 0 含引用桥可落性 gate)。
