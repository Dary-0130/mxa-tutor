# TASK-521-A: Paper 多文件 · 多文档身份契约 substrate(v0.2)

## 本版改动(v0.1 → v0.2;均来自双审 R1(GPT)+ R6(Codex),无新产品决定)
- [两审同] **跨结构不变量下沉 core 公共 helper**:`document_id ∈ documents` 不能只放 `PaperSpecModel` after-validator——现状 SQLite 读回是 `TypeAdapter(PaperSpec)` 直接对 domain 反序列化、绕过 Pydantic wrapper。新增 core 纯函数 `validate_paper_spec_document_identity(spec)`,让 Pydantic to_domain / SQLite 读回迁移 / 单文件最终组装 / save 前都调用。**不在 domain dataclass 加 `__post_init__`**(R6 实测 `core/domain` 无 post_init 校验先例,保持 domain 纯数据 + 校验在边界的现有惯例)。
- [两审同] **raw LLM 输出 validate 前 enrich**:现状 `_parse_and_validate` 是 `PaperSpecModel.model_validate(json.loads(response.text))` 直接喂——加必填字段后 raw LLM JSON(不带 document_id)会当场 validation fail,after-validator 来不及补。必须在 `json.loads` 后、`model_validate` 前 server-side 注入 documents / primary / nested document_id。**不得**把 raw LLM JSON 直接喂新 required schema;**LLM 不产 document_id**。
- [两审同] **迁移覆盖所有持久化 PaperEvidenceEntry blob、不只 spec**:`plan_json` / `missing_prompts_json` 里嵌套 `PaperEvidenceEntry`(`ModelGenerationPlan.evidence` / `BlockRecommendation.paper_reference` / `MissingParameterPrompt.paper_reference` / build_steps 内 evidence)。只迁 spec 会让 `get_plan_record` 读老 plan blob 时炸。Stage 0 实测确认所有持久化 evidence blob 范围,迁移逐一覆盖。
- [R6 实测] **`extract_uncached` 加 display_filename 参数**:现状它只拿到沙箱 `upload.pdf`、拿不到原始 `file.filename`。要写 `documents[0].filename` 须改签名 `extract_uncached(file_path, paper_id, display_filename: str | None = None)`;`extract()` 默认用 `file_path.name`,upload route 显式传清洗后的 `file.filename`。DOC-001 注入落点在 `_parse_and_validate` 的 `json.loads` 后、`model_validate` 前。
- [R1] **迁移给 user_supplied 缺失 document_id 显式注入 None**:`document_id: str | None` 是新 required 字段,"字段缺失" ≠ "值为 null";老 user_supplied evidence/parameter 缺该字段也会炸。迁移须 `document_extracted 缺→DOC-001`、`user_supplied 缺→None` 两分支都写。
- [R1] **ParameterEntry document_id 措辞:"建议必填"→"必须必填"**:消除 v0.1 卡内自相矛盾。`source==document_extracted` → document_id 必填且 ∈ documents;`source==user_supplied` → 必须 None。与 evidence 同口径硬约束。
- [两审同] **对外 `PaperAskCitation` 本卡不改,defer 521-C**:一改对外 DTO 牵动 `core/domain/paper_ask.py` / `paper_ask_schemas.py` / `paper_ask_response.schema.json` / TS / sample roundtrip。本卡只改**内部** `SourceTableEntry`(+ `_SourceCandidate`)加 document 维度;`to_citation()` 暂不带出 document(写明,避免被误以为静默丢弃);把"扩到 public citation / API / 前端展示"明确列进「不做(留 521-C)」。
- [R6 实测] **source_table abstract/equation candidate 非 evidence 派生,措辞收紧**:`_spec_candidates` 里 abstract candidate 来自 `record.spec.abstract`、equation candidate 来自 `record.spec.equations`,**不是** evidence。v0.1 "只从 evidence 派生"不成立。改为:**单文件 A 阶段**这些 candidate 注入 DOC-001(单篇下恒 DOC-001);多文件阶段的"abstract 综合归属 / equation 反查 document_id"留 521-B/C。
- [R6 实测] **迁移唯一入口 `_load_spec_with_migration`**:`_load` 对 `self._SPEC_ADAPTER` 特判委托它,`get_spec` / `get_plan_record` 两处自动覆盖、不漏;未来续用 `_load(_SPEC_ADAPTER,...)` 也自动迁移。
- [两审同] **Stage 0 构造入口 grep 升为 P1 验收项**:不只 `TypeAdapter(PaperSpec)`,还要 grep direct constructors + fixtures + goldens + eval + persisted plan JSON;否则非上传路径(测试/eval)CI 必炸。Codex 实测清单已附(见「范围 5」)。
- [两审同] **freeze 测试改法精确化**:required+nullable 分开测(字段缺失 fail / 值为 None pass);`documents` 用 `Field(min_length=1)` **不用** default_factory;`primary_document_id` 是 required-but-nullable **不设默认**;`PaperDocumentModel` 进 `NESTED_MODELS`(16→17);迁移测四类 JSON(old spec / old plan / new / bad new)。
- [R1/R6 P2 并入] document_id 加 pattern `^DOC-\d{3}$` + 测重复/非法;filename 加长度上下限 + 去路径分隔符 + 去控制字符 + 截断;防 `primary or documents[0]` 折叠的反模式明文。

## 状态
🔲 未开始(v0.2 已并双审 P1,待派 Codex 实现)

## 上下文
多文件子线第一张落地卡 = **契约 / 结构地基**。目标产品形态(PM 已定):用户一次上传多篇**文档**(PDF / DOCX;一主多辅,主文献可选),AI 综合多篇理解 + 问答时把每条出处标到「来自哪篇文件」。两点产品目标:多篇信息互相**补充** + 综合多篇**辅助推理**。

本卡**只做结构层、不做行为层**:把 `PaperSpec` 及相关结构扩出「多文档身份 + 每条依据/参数的文档归属」维度,同步 Pydantic wrapper / JSON schema(自动重导出)/ freeze 测试 / SQLite 读回兼容 / 前端 TS 类型 / **内部** citation source_table 构造。**本卡不碰**多文件上传入参、解析融合逻辑、前端多选 / 文件来源展示、冲突检测、对外 PaperAskCitation——那些留后续卡(521-B 上传+融合、521-C 问答出处标到篇+对外 citation、521-D 前端)。

合并后系统仍是「**只能传单文件、但结构已支持多文档标记、且单文件路径已真实写入 DOC-001**」的可用中间态。**关键(防死字段):单文件现有链路必须立即写满新字段**(见「范围 4」)。**关键(防 validate 炸):所有产生 / 反序列化 PaperSpec 及嵌套 evidence 的入口都要覆盖**(见「范围 5」)——这是本卡最大实现风险。

**(产品决定,PM 已拍)**
- 多文件 = 多篇**文档**(PDF / DOCX),**不含**工程文件(.zip MATLAB 工程,属 MCS 线)、暂不含表格 / 代码类。
- `primary_document_id`**可空**:指定 = 主线锚点(主次身份,**不参与值裁决**);不指定 = 几篇平等。前端「每文件后一个可点框、点=主、不点=无主」留 521-D。
- 主文献是**主次身份非可信度权重**:不因「是主文献」让 AI 信它更多;值冲突一律如实呈现,绝不静默挑。
- 红线延续:① 参数值只给有出处的、来源不伪造;② AI 综合多篇推出的、无单一出处结论放回答正文讲,**不挂可点击假出处**(只有能定位到具体 document + locator 的证据才做成 citation);③ 值冲突如实标、不静默裁决。

## 输入(前置依赖)
- 已完成:paper-to-model 后端 + 前端 + 追问线(520-A/B1/B2/C/D)全部合并 origin/main。
- 必读:01 / 02 / 04 / 06(§12 paper 契约);本卡契约段。
- 现状基线(R6 @ live origin/main `d44668d` 实证,以实现为准;起草时 Codex 须 Stage 0 复核 live HEAD):
  - `core/domain/paper_spec.py`:`PaperSpec`(frozen)+ `EquationEntry` / `ParameterEntry` / `FigureRef`,**全部字段必填、无默认值、无 `__post_init__` 校验**。
  - `core/domain/paper_evidence.py`:`EvidenceSource`(document_extracted | user_supplied)+ `PaperEvidenceEntry{source, paper_section_id|None, equation_id|None, figure_id|None, excerpt|None, missing_param_prompt_id|None}`。
  - `features/paper/paper_schemas.py`:`PaperSpecModel`(无 after-validator)/ `ParameterEntryModel` / `PaperEvidenceEntryModel`(有双源不变量 after-validator)等 wrapper(`extra="forbid"`,`from_attributes=True`,`to_domain()`);`PaperSpecModel.to_domain()` 是唯一 `PaperSpec(...)` 生产代码。
  - `features/paper/paper_spec_service.py`:`extract_uncached(file_path, paper_id)` → `_parse_and_validate(response, parsed)` = `PaperSpecModel.model_validate(json.loads(response.text)).to_domain()`(**LLM raw JSON 直接喂 validate,无中间 raw schema**)。
  - `schemas/paper_spec.schema.json`(`additionalProperties:false`,required 列 5 项)由 `scripts/export_paper_schemas.py` 从 `PaperSpecSchema` 等 **自动生成**(不手写)。导出 7 个 paper schema:paper_evidence/paper_spec/paper_plan/paper_tuning/paper_missing/paper_ask_request/paper_ask_response。
  - `tests/features/paper/test_paper_schemas_freeze.py`:`TOP_LEVEL_MODELS`(7)+ `NESTED_MODELS`(16)+ 计数命名 + extra=forbid + 字段顺序 + 不变量断言。
  - `adapters/storage/schema.py`:`paper_spec_cache(paper_id PK, paper_spec_json TEXT, ...)` + `paper_plan_cache(paper_id PK, plan_json, missing_prompts_json, missing_bindings_json, ...)`——整份结构序列化成 JSON blob 存列。
  - `adapters/storage/sqlite_paper_cache.py`:`_SPEC_ADAPTER = TypeAdapter(PaperSpec)`;`_load(adapter, payload, code)` = 裸 `adapter.validate_json(payload)`;spec blob 读回点 = `get_spec` + `get_plan_record`(**仅此两处**,R6 实测无其它 service 反序列化 spec blob)。
  - `features/paper/paper_ask_service.py`:`build_paper_ask_source_table(record)` 用 `_SourceCandidate{label, excerpt, source_kind, target}` 拼 `SourceTableEntry`;`_spec_candidates` 的 abstract/equation candidate **非 evidence 派生**。
  - `core/domain/paper_ask.py`:`SourceTableEntry{source_id, label, excerpt|None, source_kind, target}` + `to_citation()→PaperAskCitation` + 四种 target。
  - `web/src/lib/paperTypes.ts`:`PaperSpec` / `PaperEvidenceEntry` / `ParameterEntry` TS 镜像(均无文档身份字段;现有组件只读不构造,加字段不致炸)。
  - `api/routes/paper_upload.py`:`POST /api/v1/upload-document` 单 `UploadFile`;`file.filename` 仅用于 `_validate_magic_and_extension`、可能为 None / 带客户端路径;paper 无现成 filename 清洗函数(`features.ingest.upload_service._sanitize_filename` 是私有、zip 专用,**不跨 feature 复用**)。

## 输出(交付物)
- `core/domain` 新增 `PaperDocument` + `PaperSpec` 加 `documents`/`primary_document_id` + `PaperEvidenceEntry` 加 `document_id` + `ParameterEntry` 加 `document_id`。
- `core` 新增纯函数 `validate_paper_spec_document_identity(spec)`(跨结构不变量,所有入口调用)。
- `features/paper/paper_schemas.py` 新增 `PaperDocumentModel` + wrapper 字段 + `PaperSpecModel` after-validator(交叉校验)。
- `features/paper/paper_spec_service.py` `extract_uncached` 加 `display_filename` 参数 + raw LLM JSON validate 前 enrich DOC-001。
- `scripts/export_paper_schemas.py` 重导出 → 受影响 `schemas/paper_*.schema.json` 更新(过 `make verify-schema` 零 drift)。
- `adapters/storage/sqlite_paper_cache.py` 新增 `_load_spec_with_migration` + `_load` 特判 + plan/missing blob 嵌套 evidence 迁移。
- `tests/features/paper/test_paper_schemas_freeze.py` 同步 + 新增迁移/不变量测试;受影响 core/domain/eval/prompt 测试同步。
- `docs/06_OUTPUT_CONTRACTS.md` §12 同步新字段表 + 不变量 + 反模式 + locator 命名空间前瞻约束。
- `web/src/lib/paperTypes.ts` 同步 `PaperDocument` + 三处字段(**仅类型、不展示**)。
- 内部 `SourceTableEntry` + `_SourceCandidate` 加 document 维度(单文件注 DOC-001);**对外 PaperAskCitation 不改**。
- 单文件上传现有路径立即写满 DOC-001。
- eval/golden 样本同步加 documents/primary/document_id。

## 范围(必须做)

### 1. domain 结构(`core/domain`)
- [ ] 新增 `PaperDocument`(frozen dataclass):`document_id: str`(`^DOC-\d{3}$`,spec 内唯一)+ `filename: str`(已清洗显示名;**仅展示、不参与逻辑、不落日志**)。
- [ ] `PaperSpec` 加 `documents: list[PaperDocument]`(非空)+ `primary_document_id: str | None`(可空)。**字段顺序**:domain dataclass 与 `PaperSpecModel` 同位同序加(满足 freeze 顺序断言),两处一致。
- [ ] `PaperEvidenceEntry` 加 `document_id: str | None`(同位同序加 domain + `PaperEvidenceEntryModel`)。
- [ ] `ParameterEntry` 加 `document_id: str | None`(同位同序加 domain + `ParameterEntryModel`)。理由(R1-B):承载参数值本体,后续冲突检测必须能把每个 value 追到来源篇。
- [ ] domain 保持纯数据,**不加 `__post_init__` 校验**(对齐现有惯例,R6 实测 core/domain 无 post_init 先例);校验走 helper(见 2)。

### 2. 跨结构不变量 — core 公共 helper(**P1 核心**)
- [ ] 新增 core 纯函数 `validate_paper_spec_document_identity(spec: PaperSpec) -> None`,校验:
  - documents 非空;document_id 唯一;document_id 形如 `^DOC-\d{3}$`。
  - primary_document_id 为 None,或必须 ∈ documents 的某 document_id。
  - `source==document_extracted` 的 evidence/parameter:document_id 非 None 且 ∈ documents。
  - `source==user_supplied` 的 evidence/parameter:document_id == None。
- [ ] **所有入口都调用此 helper**,不只 Pydantic:
  - `PaperSpecModel` after-validator:to_domain 后调 helper(或在 model 层等价交叉校验 + helper 兜底)。
  - SQLite 读回迁移:`validate_python` 后调 helper 再返回。
  - 单文件最终组装(`_parse_and_validate` enrich 后 to_domain 后)。
  - save 前(`save_ready_bundle` dump 前可选兜底)。
- [ ] `PaperSpecModel` 新增 after-validator:可访问 self.documents/primary/evidence/parameter_table 做交叉校验(单条 model validator 看不到 documents 全集)。

### 3. 向后兼容(读回层迁移,**不靠 domain 默认值**)— R1-A
- [ ] **新写入路径**:documents / primary 显式必填(primary 可 None 但字段须在);**不靠默认值蒙混**。
- [ ] **迁移唯一入口** `_load_spec_with_migration(payload, error_code)`:`_load` 对 `self._SPEC_ADAPTER` 特判委托;`get_spec` / `get_plan_record` 自动覆盖。**禁裸 `validate_json` 绕过迁移**。
- [ ] **spec blob 迁移**(validate 前补缺字段):
  - 缺 `documents` → `[{"document_id":"DOC-001","filename":"legacy_document"}]`
  - 缺 `primary_document_id` → `None`(老数据无主文献语义;固定 None,测试锁死)
  - evidence 中缺 `document_id`:`source=="document_extracted"`→`"DOC-001"`;`source=="user_supplied"`→`None`(**两分支都写**)
  - parameter_table 中缺 `document_id`:`document_extracted`→`"DOC-001"`;`user_supplied`→`None`
  - 注入后 `validate_python` + helper;**禁** validate 失败后硬构造 domain。
- [ ] **plan / missing blob 嵌套 evidence 迁移**(P1,R6):Stage 0 实测 `plan_json` / `missing_prompts_json` 内持久化的 `PaperEvidenceEntry`(`plan.evidence` / `block_recommendations[].paper_reference` / build_steps 内 evidence / `MissingParameterPrompt.paper_reference`)范围;`get_plan_record` 读回这些 blob 同样按上述规则迁移嵌套 evidence 的 document_id。**不能只迁 spec 让老 plan record 在 get_plan_record 炸。**

### 4. 单文件路径立即写入(**防死字段** — R1-C)
- [ ] `extract_uncached(file_path, paper_id, display_filename: str | None = None)`;`extract()` 默认 `file_path.name`;upload route 传清洗后 `file.filename`。
- [ ] **filename 清洗**(paper 自有,不跨 feature 复用):去路径分隔符 / 控制字符、长度上下限、截断;为 None 时回退 `"legacy_document"` 或合理占位。
- [ ] **raw LLM JSON validate 前 enrich**(`_parse_and_validate` 的 `json.loads` 后、`model_validate` 前):注入 `documents=[{DOC-001, <清洗 filename>}]`、`primary_document_id=None`、所有 `document_extracted` evidence/parameter 的 `document_id="DOC-001"`、`user_supplied` 的 `document_id=None`。**不得**把 raw LLM JSON 直接喂新 required schema;**LLM 不产 document_id**。
- [ ] plan/missing/build/tuning 链路的 LLM 输出 evidence 同样在 validate 前 enrich DOC-001 / None(P1,R6:全局 `PaperEvidenceEntryModel` 要求 document_id 后,这些链路的 raw LLM evidence 也会炸)。
- [ ] 内部 citation `SourceTableEntry` 带 DOC-001 / 对应 label(见 6)。

### 5. 入口覆盖(**P1 验收项,防 validate 炸** — 两审同)
Stage 0 必须 `git grep` 枚举并逐项改造 / 说明不受影响:
- [ ] `PaperSpec(` / `ParameterEntry(` / `PaperEvidenceEntry(` direct constructor(R6 命中:`tests/adapters/storage/test_sqlite_paper_cache.py`、`tests/api/test_paper_{ask,query,tuning,upload,user_supply}.py`、`tests/core/test_paper_cache_contracts.py`、`tests/core/test_paper_spec.py`、`tests/core/test_paper_evidence.py`、`tests/eval/test_run_paper_eval.py`、`tests/features/paper/test_paper_{ask_service,plan_cache,plan_helpers,plan_prompts,plan_service,tuning_service,user_supply_service,spec_service}.py`)——全部补 documents/primary/document_id。
- [ ] `TypeAdapter(PaperSpec)` / `PaperSpecModel.model_validate(` 反序列化点。
- [ ] eval golden / sample JSON(R6 命中:`eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/golden/expected_paper_spec.json`、`.../expected_model_generation_plan.json`、`eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/expected_missing_prompts.json`、`.../golden/expected_updated_plan.json`)——补 documents/primary/document_id。
- [ ] prompt 硬写字段数(R6 命中:`core/prompts/paper_spec_extract.yaml` / `features/paper/_prompt_builder.py` / `tests/features/paper/test_paper_plan_prompts.py` 里硬写「9 字段 / 6 字段 / 5 字段」)——同步字段计数。

### 6. 内部 citation source_table(**对外 PaperAskCitation 不改** — 两审同)
- [ ] `_SourceCandidate` + `SourceTableEntry` 加 `document_id: str | None` + `document_label: str | None`;candidate 统一带到 final entry。
- [ ] evidence-derived candidate:取 `evidence.document_id`;user_supplied candidate(无 evidence):置 None。
- [ ] **abstract / equation candidate 非 evidence 派生**(R6):单文件 A 阶段注入 DOC-001(单篇恒 DOC-001);多文件的 abstract 综合归属 / equation 反查 document_id 留 521-B/C。
- [ ] `to_citation()` 暂不带出 document(对外 PaperAskCitation 本卡不改);**写明 document 维度此刻仅在内部 SourceTableEntry,不静默丢弃、留 521-C 扩到对外**。
- [ ] document_id 后端注入、**LLM 不产**;综合推理无单一出处不做 citation、不伪造 DOC-ALL。

### 7. schema 导出 + drift 闸
- [ ] 改完 Pydantic model 跑 `make export-schema` 重导出;`make verify-schema` 零 diff 通过。
- [ ] required:`documents` 进 required、`primary_document_id` required-but-nullable、`document_id` required-but-nullable(避免"新写入漏字段"守门偏弱)。受影响 schema:paper_spec 必变(+PaperDocumentModel/documents/primary);paper_evidence/paper_plan/paper_missing/paper_tuning 因嵌套 evidence 变;**paper_ask_response 本卡不变**(PaperAskCitation 不改)。

### 8. freeze 测试同步(改 schema 必同步)
- [ ] `PaperDocumentModel` 进 `NESTED_MODELS`(16→17)+ `test_nested_model_count_and_names_are_frozen` 精确列表更新;`TOP_LEVEL_MODELS` 不变(仍 7)。
- [ ] `test_extra_forbid_at_all_levels`:PaperDocumentModel 随 NESTED 自动覆盖。
- [ ] `test_paper_spec_field_order_matches_domain` / `test_nested_field_order_matches_domain`:加字段后顺序对齐;ParameterEntryModel/PaperEvidenceEntryModel 加 document_id + PaperDocumentModel 字段顺序断言。
- [ ] **required vs nullable 分开测**:字段缺失 fail / 值为 None pass(primary 与 document_id)。`documents` 用 `Field(min_length=1)` **不用** default_factory;`primary_document_id` / `document_id` **不设默认值**。
- [ ] 新增针对性测试:
  - 迁移四类 JSON:old spec(缺 documents/primary/evidence·parameter document_id)→ DOC-001/None;old plan(嵌套 evidence 缺 document_id)→ 迁移;new JSON round-trip 不变;bad new(documents missing / primary 不在 documents / document_extracted document_id missing 或 ∉ documents / user_supplied document_id 非 null)→ fail。
  - document_id pattern `^DOC-\d{3}$` 重复 / 非法格式 → fail。
  - 同名参数多来源值不被 dedupe(各保留 document_id)。
- [ ] 受影响 core/domain 测试(`test_paper_evidence.py` / `test_paper_spec.py` 字段顺序 + 构造)、`test_paper_spec_service.py`(LLM payload)同步。

### 9. 前端 TS 镜像(仅类型,不展示)
- [ ] `paperTypes.ts` 加 `PaperDocument` + `PaperSpec` 加 `documents: PaperDocument[]` / `primary_document_id: string | null` + `PaperEvidenceEntry` / `ParameterEntry` 加 `document_id: string | null`(**不设 optional**,镜像后端 required-but-nullable)。
- [ ] `pnpm typecheck` / lint / build 全绿;**不改任何 UI 组件、不展示文件来源**(展示留 521-D)。

### 10. 工程守则
- [ ] decision 08:改文本文件保留原始字节 / 行尾(补丁式 / read_bytes/write_bytes,禁 read_text/write_text/sed -i)。
- [ ] decision 11:不 logger.exception;filename 不落日志;document_id 可入结构、日志按既有口径不漏 excerpt / 源文本。
- [ ] decision 13 schema-sync 全清单(本卡**触及** paper schema → 逐项过:domain / Pydantic model / schema export(7 个)/ freeze test / 06_OUTPUT_CONTRACTS §12 / TS mirror / prompt 字段计数 / eval golden;**对外 paper_ask_response / PaperAskCitation 本卡不动、记 521-C**)。

## 不做(明确排除)
- ❌ **对外 `PaperAskCitation` / `paper_ask_response.schema.json` / ask response TS 加 document 维度**——留 521-C(本卡只改内部 SourceTableEntry)。
- ❌ 多文件上传入参(单→多 UploadFile)、解析器多文件签名、融合逻辑(留 521-B)。
- ❌ 冲突检测 / `ParameterConflict` / conflict_report(只留可检测底座;留 521-B)。
- ❌ 前端多选上传 / 主文献勾选框 / 文件来源展示 UI(留 521-D)。
- ❌ citation 按文件分组展示 / 「来自哪篇」前端呈现(留 521-C/D)。
- ❌ per-document 解析状态 / 部分成功(辅文档失败表达)——记 521-B 风险,不入 PaperSpec。
- ❌ content_hash / 文件去重 / 审计字段(不做成必需字段;后续需要再加)。
- ❌ 把 `source`(document_extracted|user_supplied)改成文件 ID 或叫 `source_file`——`source` 双源语义不动;新字段叫 `document_id`。
- ❌ primary_document_id 参与值裁决 / 冲突自动选主;documents 里加 `role`(避免双真值,只保留 primary 一处真值)。
- ❌ **`primary or documents[0]` 把 None 折叠成"DOC-001 是主文献"**(反模式;None=无主,不得隐式偏向首篇)。
- ❌ 在 domain dataclass 加 `__post_init__` 校验(保持纯数据 + 边界校验惯例;校验走 helper)。
- ❌ 碰工程文件(.zip,MCS 线)、表格 / 代码类解析。
- ❌ 让 LLM 产 document_id;改 LLM 输出契约 / answer_kind / target union。
- ❌ lazy write-back 迁移(读时迁移即可,不写回,降存储副作用)。
- ❌ 改已合并产物行为(B1/B2/C/D 前端、MCS、其它后端);改 = PM 拍 + 审。

## 接口契约(本卡定义的结构增量)

### PaperDocument(新)
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `document_id` | string | 必填,`^DOC-\d{3}$`,spec 内唯一 | 文档内部编号(后端结构事实,非 LLM 输出) |
| `filename` | string | 必填,已清洗显示名(去路径分隔/控制字符、长度限、截断) | 用户可见文件名;仅展示,不参与逻辑,不落日志 |

### PaperSpec 增量
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `documents` | array[`PaperDocument`] | 非空(min_length=1,无默认);document_id 唯一 | 本份结果由哪几篇文档组成 |
| `primary_document_id` | string \| null | required-but-nullable(无默认);非 null 时 ∈ documents | 主文献(主线锚点,**不参与值裁决**);null = 平等/无主 |

### PaperEvidenceEntry 增量
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `document_id` | string \| null | document_extracted 必填且 ∈ documents;user_supplied 必须 None | 该条证据来自哪篇文档 |

### ParameterEntry 增量
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `document_id` | string \| null | document_extracted **必填**且 ∈ documents;user_supplied 必须 None | 该参数值来自哪篇文档(冲突检测地基) |

### SourceTableEntry 增量(内部,本卡;对外 PaperAskCitation 不改)
| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `document_id` | string \| null | document_extracted 派生自 evidence(abstract/equation 单文件注 DOC-001);user_supplied 可空 | 内部 citation 来自哪篇 |
| `document_label` | string \| null | 派生(filename 或 `DOC-00x · 名`) | 展示用文件标签(本卡不经 to_citation 带出对外) |

**不变量汇总**:documents 非空、document_id 唯一且 `^DOC-\d{3}$`;primary ∈ documents ∪ {null};document_extracted 的 evidence/parameter document_id 必填且 ∈ documents;user_supplied 的 == None;单文件写入 / 老 blob 迁移固定 DOC-001(primary 注 None);citation document 维度后端派生、LLM 不产、综合推理无单一出处不做 citation 不伪造 DOC-ALL;不对同参数多来源值静默 dedupe;None 不折叠成 documents[0]。

## 验收标准
- [ ] 单文件上传产出 PaperSpec 含 documents(单条 DOC-001 + 真实清洗文件名)+ primary=None;evidence/parameter(document_extracted)document_id 全 DOC-001、user_supplied 全 None;内部 SourceTableEntry 带 DOC-001;LLM 输出未被要求产 document_id。
- [ ] 老 spec blob(缺新字段)读回迁移得 DOC-001 / primary=None / user_supplied document_id=None,不炸;老 plan blob 嵌套 evidence 同样迁移、`get_plan_record` 不炸;新 blob round-trip 不变。
- [ ] 新写入漏 documents / primary 不在 documents / document_extracted 缺 document_id 或 ∉ documents / user_supplied 带非 null document_id / document_id 非法格式 → 全部 fail。
- [ ] 跨结构 helper 被 Pydantic to_domain + SQLite 读回 + 单文件组装所有路径调用(直接构造 PaperSpec 也被 helper 拦——经任一上述边界)。
- [ ] `make export-schema` 重导出后 `make verify-schema` 零 diff;新字段 required/nullable 符合预期;paper_ask_response 未变。
- [ ] freeze 测试全绿(PaperDocumentModel 计数 16→17/命名/extra=forbid + 字段顺序 + required-vs-nullable + 迁移四类 JSON + pattern + dedupe)。
- [ ] 范围 5 所有入口(direct constructor / eval golden / prompt 字段数)同步,`make check` 后端测试全绿。
- [ ] `pnpm typecheck` / lint / build 全绿(前端仅类型对齐,无 UI 改动)。
- [ ] `docs/06_OUTPUT_CONTRACTS.md` §12 同步新字段表 + 不变量 + 反模式(用户补充带 document_id / 综合推理伪造 DOC-ALL / None 折叠 documents[0])+ locator 命名空间前瞻约束。
- [ ] decision 13 全清单逐项确认(PR 说明列出);对外 PaperAskCitation 明确 defer 521-C。
- [ ] 纯结构/契约层:无新端点、无 UI 展示、无融合行为、无冲突检测、对外 citation 未改。

## 风险与注意点
1. **入口覆盖(最大风险)**:新 required 字段下,任何未 enrich / 未迁移的 PaperSpec / 嵌套 evidence 生产点都会 validate 炸。范围 5 列了 Codex 实测清单;Stage 0 须再核 live 是否有新增入口。
2. **plan/missing blob 嵌套 evidence**:迁移不能只迁 spec_json;plan_json/missing_prompts_json 内嵌 evidence 也要迁,否则 get_plan_record 炸。
3. **raw LLM JSON**:spec + plan/missing/build/tuning 链路的 LLM 输出都不带 document_id,必须 validate 前 enrich。
4. **跨结构 helper 落点**:domain 直接构造(测试/内部)绕过 Pydantic;helper 须在所有边界调用,domain 不加 post_init(对齐惯例)。
5. **filename 传递**:extract_uncached 改签名加 display_filename;paper 自写清洗(不跨 feature 复用 ingest 私有函数)。
6. **primary None 语义**:None=无主,固定迁移注 None;防 `primary or documents[0]` 折叠;测试锁死。
7. **locator 命名空间(前瞻,本卡标不实现)**:多文件后 locator 合法性应 `(document_id, locator_id)` 复合;单文件下不触发(只 DOC-001);**521-B 必须处理、不得继续拖**——06 文档注明,521-B 前置硬门槛(R1-P2)。
8. **source_table abstract/equation 非 evidence**:单文件注 DOC-001;多文件归属/反查留 521-B/C。
9. **eval/prompt 硬数字**:prompt 里"9/6/5 字段"硬写 + golden JSON 加字段会 fail,须同步。

## 估时
1.5–2 天(后端结构 + 跨结构 helper + 读回迁移含嵌套 evidence + raw LLM enrich(spec+plan/missing/tuning)+ extract 签名 + filename 清洗 + freeze 同步 + schema 重导出 + 入口全覆盖 + 内部 source_table + TS 镜像 + eval/prompt 同步;主在入口覆盖 + 嵌套 evidence 迁移 + raw LLM enrich 链路)。

## 给 Codex 的提示
- Stage 0 取 live origin/main HEAD,确认 paper 全链 + 追问线在;`git grep` 三组:① 所有 `PaperSpec(`/`ParameterEntry(`/`PaperEvidenceEntry(`/`TypeAdapter(PaperSpec)`/`PaperSpecModel.model_validate(` 入口;② 所有持久化嵌套 evidence 的 blob(plan_json/missing_prompts_json + plan.evidence/block_recommendations[].paper_reference/build_steps evidence/MissingParameterPrompt.paper_reference);③ eval/golden + prompt 硬字段数。
- 字段顺序:domain 与 Pydantic model 同位同序;PaperDocumentModel 进 NESTED_MODELS(16→17)。
- 跨结构不变量走 core 公共 helper,所有边界(Pydantic to_domain / SQLite 读回 / 单文件组装 / save)调用;domain 不加 post_init。
- 读回迁移唯一入口 `_load_spec_with_migration`,`_load` 特判;spec + 嵌套 evidence(plan/missing blob)都迁;user_supplied 缺 document_id 注 None、document_extracted 注 DOC-001;禁裸 validate 绕过。
- raw LLM JSON(spec + plan/missing/build/tuning)validate 前 server-side enrich DOC-001/None;LLM 不产 document_id;不得直接喂新 required schema。
- extract_uncached 加 display_filename;upload route 传清洗后 file.filename;paper 自写 filename 清洗(去路径分隔/控制字符/截断),不跨 feature 复用。
- 内部 SourceTableEntry/_SourceCandidate 加 document_id/document_label;evidence 派生取 evidence.document_id、user_supplied 置 None、abstract/equation 单文件注 DOC-001;to_citation 不带出对外;对外 PaperAskCitation **本卡不改**、defer 521-C。
- 改 schema 后 make export-schema 重导出 + make verify-schema 零 diff(7 个 paper schema,paper_ask_response 不应变);freeze + eval golden + prompt 字段数同步。
- TS 仅改 paperTypes.ts(三处字段不设 optional);不改 UI 组件。
- 不做融合/冲突检测/多选上传/前端展示/对外 citation(留后续卡);不碰工程文件;locator 复合命名空间留 521-B(06 注明前瞻)。
- 改已存在文本文件保留原始字节/行尾(decision 08);本机无 grep,用 git grep/rg/Select-String。
- 完工三件套 + decision 13 全清单逐项在 PR 说明列出。
