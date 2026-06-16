# TASK-501:paper-to-model 资料入口骨架 + PaperSpec 抽取(v0.3.2 — 终版 + Stage 2 微补丁)

## 状态

✅ v0.3.1(2026-06-16,**终版**):
- **R1 三审 conditional pass**(0 P0 + 5 P1 + 2 P2),架构师全采纳,**0 challenge**
- **R2-C3 R1 自己裁定成立**(架构师反 challenge R1 二审 P0-1 修订方向成立;v0.3 统一 `dict` 而非 `list` 是正确方向)
- **PM 已拍板**:C1 = 拆分 / C2 = `pypdf + python-docx` / R2-C3 = 接受架构师反 challenge
- **R1 三审明示不需要四审**(除非 v0.3.1 改动 06 § 12 字段 / API 路由范围 / cache 语义 / sandbox 机制 — v0.3.1 7 项小修均不动这些)
- **下一步**:PM 合并任务卡 → Codex Stage 0
- **v0.3.2 微补丁**(2026-06-16,Stage 2 sample roundtrip 实测驱动):06 § 12.5 字段约束放宽(`library_choice` 1-100 → 1-300 字;`ParameterMapping.unit: str` → `str | None`);走 v0.3.1 § 输出 段预留的"若 06 § 12 字段在本卡实施期发现需要微调"通道;PM 拍板不走 R1 四审(修订性质 = 约束放宽,非语义变更)

## R2 公开 challenge 清单(决策 12 v0.4 R2 工艺,留档)

| # | 项 | 裁决 | 结果 |
|---|---|---|---|
| C1 | TASK-501 拆分粒度 | PM 拍板拆分(R1 一审 / 二审 / 三审 三轮同意)| ✅ 拆分 |
| C2 | PDF / docx 解析依赖选型 | PM 拍板 `pypdf + python-docx`(R1 一审 / 二审 / 三审 三轮同意,反对 `unstructured`;具体版本 Codex 查 PyPI 稳定版 + PM PR review)| ✅ pypdf + python-docx |
| R2-C3 | R1 二审 P0-1 修订方向反(架构师反 challenge:实际样本包 JSON 顶层是 dict 而非 list)| **R1 三审自己裁定成立**:"二审 P0-1 抓'描述和测试不一致'是对的,但我当时给的'统一成顶层 list'修订方向是错的。v0.3 以样本实测为准,统一为顶层 `dict` 含 `missing_prompts` key,是正确方向。" | ✅ 统一 dict |

---

## 上下文

### TASK-501 在 paper-to-model 主线位置

paper-to-model 开门 chore(TASK-500 v0.2.1)已合并,五项前置硬门槛全 ✅;主线正式解封(详 `docs/decisions/20260615-22-direction-pivot-paper-to-model.md` § 10.4)。本任 TASK-501 是 paper-to-model 主线**首个实现 task**,承接资料入口骨架。

数据流(02 § 资料入口数据流):

```
用户上传论文 / 报告(PDF·docx)        ← TASK-501 范围起点
   ↓
文档安全沙箱(格式嗅探 / 超时 / 不执行 / 不联网)    ← TASK-501
   ↓
PaperParser(PDF/docx → 结构化文本流)             ← TASK-501
   ↓
PaperSpec(标题/摘要/公式/参数表/图占位/伪代码)      ← TASK-501 终点(单 LLM 抽取)
   ↓
PaperPlanService                                  ← TASK-502 范围(本卡不做,详 D12)
   ↓
ModelGenerationPlan + TuningSuggestion            ← TASK-502 / 503
   ↓
用户据路线图在 MATLAB 中搭建 / 调参
```

### 拆分判断(D2 — 架构师拍板,R1 同意;待 PM 最终拍板)

TASK-500 v0.2.1 § 接口契约要点 + 第 45 任接手简报 § 3 列 10 大新增项。架构师评估单 PR 一锅炖体量 5000-6000 LOC / 30+ 文件,跨 7 层;TASK-203 单服务 1880 LOC R1 抓 12 项,本任不拆估 R1 ≥ 30 项;K_30 跨段同步漂移风险高(决策 22 § 9 警示)。

**拆分方案**(D2 决策):按 02 § 资料入口数据流自然边界切三任:

| Task | 范围 | 数据流位置 | 验收锚点 |
|---|---|---|---|
| **TASK-501**(本卡)| 资料入口骨架 + PaperSpec 抽取 | 上传 → 沙箱 → parser → PaperSpec | `material_to_plan/case_01` input → actual PaperSpec ≈ golden(Layer 2 A1 / A2 / E1)|
| TASK-502 | PaperPlanService + 9 组件 prompt 子角色 + MissingDetector + UserSupplyMerger | PaperSpec → ModelGenerationPlan + MissingParameterPrompt → 用户补充 → updated plan | 两 case 跑通 + 整体门槛 5(`scoring_template.md` § 6 = 两 case 各 ✅ / 🟡 + 0 E1 / E2 一票否决)|
| TASK-503 | TuningSuggestion service + 前端 UX 闭环 + 持久化 cache + `GET /api/v1/papers/{paper_id}/spec` | + TuningSuggestion endpoint + 持久化 cache | 端到端用户旅程跑通 |

**TASK-501 终点 = "上传一份 docx,经 PaperSpec 抽取,返回结构化论文规格"**;不含 plan 生成、不含调参建议、不含缺失参数交互闭环(MissingParameterPrompt 的 schema + serialize 含,但用户补充流程留 502)、**不含 GET 路由**(P0-3 决议:GET + 持久化 cache 留 TASK-503,详 D12)。

### Base commit + 范围边界

- **Base commit**:main HEAD = TASK-500 main merge 之后(PM 派单时提供具体 hash;Codex Stage 0 验证 main 含 TASK-500 ✅ 与五项门槛字面)
- **范围**:本卡仅落地 paper feature 骨架 + parser 层 + PaperSpec 抽取服务 + `POST /api/v1/upload-document` 路由;**不落地** PaperPlanService / MissingDetector / UserSupplyMerger / TuningSuggestion / 9-component 完整体 / evaluator 完整跑分 / `GET /api/v1/papers/{paper_id}/spec`

### mxa-tutor 快速 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制 / 信号处理 / 新能源)的 MATLAB / Simulink AI 助教 Web 应用。v3.0 起从"MCS 工程导览 + 问答"扩展为**二合一产品**:

- MCS 工程入口(既有):上传 .zip 工程包 → 工程导览 + 问答
- paper-to-model 资料入口(新主线):上传论文 / 报告 PDF/docx → 复现路线图 + 模型搭建副驾 + 参数对应说明(R1 降级三层承诺,详决策 22 § 1.1)

四层分层:`api/` 路由 / `features/` 业务 / `core/` 接口 + domain + prompt yaml / `adapters/` 实现。

paper-to-model **不**改造既有 MCS feature(决策 22 § 5.2 红线 + 决策 21 boundary);**新建** `features/paper/` 与 `core/domain/paper_*.py` 对等实现。

### 审批级别:架构升级类(R1 + R6 + PM 三道)

| 维度 | 评分 |
|---|---|
| 决策密度 | **高**:本卡 D1-D12 |
| 下游扩散面 | TASK-502 / 503 / 评测体系 / 前端文案 |
| 用户可见性 | paper-to-model 主线**首个**用户面端点 |
| 新依赖 | 首次引入 PDF / docx 解析库(走 04 § 6 PR review)|
| 跨 feature 边界 | 首次落实决策 21 boundary 到 paper feature 实施层 |

走决策 12 v0.4 双 AI 互审协议:**R1**(GPT 决策质量审)+ **R6**(Codex 完工实测层)+ **PM 兜底**。

---

## 输入(前置依赖)

### 必须已完成 task / 入仓

- ✅ TASK-500 v0.2.1(开门 chore 五项门槛 — 06 § 12 / 04 § 8.6 / 对外口径 / 评测样本包齐全)
- ✅ 决策 22 v1.3.1(方向 pivot,paper-to-model 主线锁定)
- ✅ 宪法 v3.1 + roadmap v2.1(paper-to-model 阶段 Week 5-9)
- ✅ 决策 23(v0.2/v0.3 能力路线 + 客户端 + 技术栈,**TASK-501 不接 MATLAB Engine 留 v0.3**)
- ✅ 决策 24(用户分层 L1-L4 + to B 切入,**TASK-501 不动 B 端**)
- ✅ 02 v3.0 delta(资料入口数据流 + PaperGraph 占位 + features/paper 边界)

### 上游关键契约(R1 stand-alone 看 + Codex 通过 `view` 实地核查)

**06 § 12 paper-to-model 输出契约(`docs/06_OUTPUT_CONTRACTS.md`)**

字段表与不变量字面以 06 § 12.1 - 12.8 为真值源,本卡接口契约段 § 7 不重抄字段表(避免 K_30 跨段同步漂移),仅给 Python 实现层的对应映射 + 校验时机。

- § 12.1 资料入口领域枚举:`control_system` / `signal_processing` / `power_electronics` / `communication` / `motor_control` / `new_energy`(6 类,**拒绝 general**)
- § 12.2 `EvidenceSource` enum:`document_extracted` / `user_supplied`
- § 12.3 `PaperEvidenceEntry`:6 字段 + 两套不变量(本卡 § 7 Pydantic 层强制校验)
- § 12.4 `PaperSpec`:9 字段(`paper_title` / `paper_type` / `domain` / `abstract` / `equations` / `parameter_table` / `figure_locations` / `pseudocode_blocks` / `evidence`)
- § 12.5 `ModelGenerationPlan`:8 字段(**TASK-501 范围内仅 schema 落地;serialize-only,不在本卡 service 生成**);**v0.3.2 微补丁**:`library_choice` 约束 1-300 字 + `ParameterMapping.unit: str | None`(由 Stage 2 sample roundtrip 实测驱动)
- § 12.6 `TuningSuggestion`:7 字段(**TASK-501 范围内仅 schema 落地;serialize-only**)
- § 12.7 `MissingParameterPrompt`:7 字段(**TASK-501 范围内仅 schema 落地;serialize-only**)
- § 12.8 反模式:4 例(本卡 freeze test + Pydantic validator 必须拦反模式 1 / 2 / 3 / 4,详 § 7.6)

**5 个顶层契约 schema**:`PaperEvidenceEntry` / `PaperSpec` / `ModelGenerationPlan` / `TuningSuggestion` / `MissingParameterPrompt`(R1 P0-2 修订:`EvidenceSource` 是 enum,**不是 wrapper**;子项 schema 是 nested submodel,详 § 7.5)

**6 个子项 schema**(06 § 12 子项草稿):`EquationEntry` / `ParameterEntry` / `FigureRef` / `BlockRecommendation` / `ParameterMapping` / `ParameterDirection`

**04 § 8.6 文档上传安全(`docs/04_ENGINEERING_STANDARDS.md`)**

7 子项 a-g 字面(R1 P0-4 修订:(c) sandbox + (g) raw 文档持久化与脱敏的硬约束必须落到本卡实现 + 测试):

- (a) 上传入口策略:**新增 `POST /api/v1/upload-document`**,与 MCS `/upload` 不交集
- (b) magic byte sniffing:PDF 头 `%PDF-` / docx 头 `PK\x03\x04` + 包内 `[Content_Types].xml`
- (c) parser sandbox:**子进程隔离 + 30s timeout / 512MB mem + 子进程只接受临时路径不持有可写项目目录 + 解析失败不泄漏 stack / 绝对路径**(详 § 7.9)
- (d) 解析依赖审批:走 04 § 6 PR review(本卡 D7)
- (e) 恶意 fixtures:6 类(加密 PDF / 嵌入 JS PDF / 巨型 PDF / 含宏 docx / zip bomb docx / 损坏 docx)
- (f) 外链 / 嵌入对象 / 宏 / OCR 策略:不执行 / 不联网 / 不解析远程图像 / OCR 留 v0.2
- (g) raw 文档持久化与脱敏:**raw 不持久化 + 24h TTL + 日志只记 request ID + 文件大小 + hash + 扩展名 + 拒绝原因,不记原始文件名 / 文档正文 / 图片内容**(详 R6.1 grep,§ 验收)

**12 个样本包文件**(`eval/cases/paper_to_model/`)— TASK-501 验收 ground truth

```
eval/cases/paper_to_model/
├── README.md
├── verification_method.md
├── scoring_template.md
├── material_to_plan/case_01_motor_short_circuit/
│   ├── case_README.md
│   ├── input/source_doc_stripped.md
│   └── golden/expected_paper_spec.json     ← TASK-501 主验收锚点(单对象)
│   └── golden/expected_model_generation_plan.json (TASK-502 用,本卡 freeze test 仅做结构 round-trip)
└── missing_param/case_01_missing_image_param/
    ├── case_README.md
    ├── input/source_doc_stripped.md
    ├── input/expected_missing_prompts.json   ← dict { "missing_prompts": list[MissingParameterPrompt] }(R1 二审 P0-1 架构师反向采纳:实际顶层是 dict)
    ├── user_input/user_supplied_params.json
    └── golden/expected_updated_plan.json    (TASK-502 用,本卡仅结构 round-trip)
```

**4 个 sample JSON artifacts**(R1 P1-6 修订,精确描述):
1. `golden/expected_paper_spec.json` — 单对象 `PaperSpec`
2. `golden/expected_model_generation_plan.json` — 单对象 `ModelGenerationPlan`
3. `input/expected_missing_prompts.json` — **顶层 `dict` 含 `missing_prompts` key,值为 `list[MissingParameterPrompt]`(6 项数组)**;注意在 `input/` 不在 `golden/`(R1 二审 P0-1 架构师反向采纳)
4. `golden/expected_updated_plan.json` — 单对象 `ModelGenerationPlan`(用户补充后)

**任意 sample 文件需调整 = 不在 TASK-501 范围内顺手改**(决策 22 § 5.2 + 第 45 任接手简报 § 不要做的事:"不改样本包 12 文件任何字面,若发现 golden 内容需调整 → 走 task-500 v0.2.2 微补丁")。

### 本卡合并守门红线 6 项(R1 P0-5 修订 — 来源多源合并,非决策 22 § 5.2 字面)

红线 6 项 = 决策 22 § 5.2 + 决策 21 + TASK-500 v0.2.1 合并:

| # | 红线文件 / 目录 | 来源 |
|---|---|---|
| 1 | `core/domain/project_overview.py` | 决策 22 § 5.2 字面 |
| 2 | `features/overview/overview_schemas.py` | 决策 22 § 5.2 字面 |
| 3 | `core/prompts/project_overview.yaml` | 决策 22 § 5.2 字面 |
| 4 | `features/overview/` 整目录 | 决策 21 boundary(paper feature 不 import overview 私有结构,引申到整目录禁动)+ 决策 22 § 5.2 "不改既有 MCS feature 的 schema / contract"|
| 5 | `features/explanation/` 整目录 | 决策 21 boundary(三层并存不互相消费私有结构)|
| 6 | `features/explanation/_evidence_builder.py` | TASK-500 v0.2.1 + 决策 21(EvidencePack 不改既有结构,paper feature 新建独立 PaperEvidenceEntry)|

**Stage 0 核查**:Codex 需 grep 三处源文件追溯红线来源(不再要求"全是决策 22 § 5.2 字面")。

### 决策 11 / 决策 21 红线(本卡必守)

- **async 内同步重活必须 `asyncio.to_thread` 桥接**(决策 11 决策 1)
- **业务异常分支禁用 `logger.exception`**,改 `logger.error(..., type(exc).__name__)` + `from None`(决策 11 决策 2)
- **paper feature 不 import overview / explanation 私有结构**(决策 21 boundary)

---

## 输出(交付物)

### 新增生产文件清单(20-22 个;测试 / fixtures 另计)— R1 P2-6 修订

| 路径 | 行数(估)| 用途 |
|---|---:|---|
| `core/domain/paper_evidence.py` | ~80 | `EvidenceSource` enum + `PaperEvidenceEntry` dataclass(纯 contract,无逻辑)|
| `core/domain/paper_spec.py` | ~120 | `PaperSpec` + `EquationEntry` + `ParameterEntry` + `FigureRef`(全纯 dataclass)|
| `core/domain/paper_plan.py` | ~80 | `ModelGenerationPlan` + `BlockRecommendation` + `ParameterMapping`(serialize-only,TASK-502 消费)|
| `core/domain/paper_tuning.py` | ~60 | `TuningSuggestion` + `ParameterDirection`(serialize-only,TASK-503 消费)|
| `core/domain/paper_missing.py` | ~40 | `MissingParameterPrompt`(serialize-only,TASK-502 消费)|
| `core/interfaces/document_parser.py` | ~80 | `DocumentParser` ABC + `ParsedDocument` 数据结构(含 `locator_index`,R1 P1-3 + P1-11 修订:`DocumentParserRouter` 接口同文件)|
| `adapters/parser/pdf_parser.py` | ~120 | `PdfParser(DocumentParser)`:pypdf 实现 + magic byte |
| `adapters/parser/docx_parser.py` | ~120 | `DocxParser(DocumentParser)`:python-docx 实现 + magic + `[Content_Types].xml` 包内校验 |
| `adapters/parser/_sandbox.py` | ~180 | parser 子进程沙箱(timeout / mem limit / 子进程权限隔离 / 错误脱敏,R1 P0-4 + P1-10 修订)|
| `features/paper/__init__.py` | ~10 | re-export `PaperSpecService` + `InMemoryPaperSpecCache`(R1 三审 P2-1 修订:`DocumentParserRouter` 是 `core.interfaces` 层对象,不从 `features/paper` re-export,避免分层误读)|
| `features/paper/paper_schemas.py` | ~280 | **5 个顶层 Pydantic model wrapper + 6 个 nested submodel + EvidenceSource enum 直接复用**(R1 二审 P2-2 修订:Pydantic 直接复用 `core.domain.paper_evidence.EvidenceSource`,不重定义镜像)+ 双源不变量 `model_validator(mode='after')` + `.to_domain()` / `.from_domain()` 桥接(决策 18 模式,R1 一审 P0-2)|
| `features/paper/_paper_spec_cache.py` | ~100 | `PaperSpecCache` ABC + `InMemoryPaperSpecCache`(asyncio.Lock 保护;feature-private,对齐 TASK-203 OverviewCache 模式;自审补强)|
| `features/paper/_paper_spec_extractor.py` | ~80 | LLM prompt 构造 + 输出解析(纯函数辅助层)|
| `features/paper/paper_spec_service.py` | ~280 | `PaperSpecService`:`async def extract(file_path: Path, paper_id: str) -> PaperSpec`,五步校验 + cache + asyncio.to_thread(R1 P2-5 修订:签名统一)|
| `core/prompts/paper_spec_extract.yaml` | ~160 | prompt v0.1(system 含 9 字段输出约定 + 双源契约 + 反幻觉指令 + locator 白名单注入,R1 P1-3 修订)|
| `api/routes/paper_upload.py` | ~80 | **`POST /api/v1/upload-document`**(R1 P0-3 修订:删 `GET /api/v1/papers/{paper_id}/spec`)+ `UploadDocumentResponse` Pydantic model(自审补强)|
| `schemas/paper_spec.schema.json` | ~150 | JSON Schema 导出(对应 PaperSpec Pydantic wrapper)|
| `schemas/paper_evidence.schema.json` | ~60 | 对应 PaperEvidenceEntry |
| `schemas/paper_plan.schema.json` | ~120 | 对应 ModelGenerationPlan(本卡 serialize-only,TASK-502 用)|
| `schemas/paper_tuning.schema.json` | ~80 | 对应 TuningSuggestion(本卡 serialize-only)|
| `schemas/paper_missing.schema.json` | ~50 | 对应 MissingParameterPrompt(本卡 serialize-only)|
| `scripts/export_paper_schemas.py` | ~60 | `python -m scripts.export_paper_schemas` 导出 5 个 .schema.json |

**总计**:21 个生产文件。

**测试新增**(约 1:1 比例,估 ~1600 LOC):

| 路径 | 用途 |
|---|---|
| `tests/core/domain/test_paper_evidence.py` | 双源不变量 / 反模式 2 拦截 |
| `tests/core/domain/test_paper_spec.py` | PaperSpec / 子项 round-trip + 9 字段约束 |
| `tests/features/paper/test_paper_schemas_freeze.py` | **freeze test**:5 顶层 + 6 nested + 反模式 1/2/3/4 全覆盖(详 § 7.6)|
| `tests/features/paper/test_paper_schemas_sample_roundtrip.py` | **4 个 sample JSON × Pydantic 反序列化 × `.to_domain()` × `.from_domain()` × 字面对比**(详 § 7.7)|
| `tests/features/paper/test_paper_spec_cache.py` | InMemoryPaperSpecCache(get/put + lock 并发)|
| `tests/features/paper/test_paper_spec_service.py` | 五步校验 / LLM 异常翻译 / cache 命中 / asyncio.to_thread 桥接 / figure 反幻觉 / locator 白名单 + **本卡阶段 source 校验 2 项**(R1 二审 P1-2):`test_paper_spec_service_rejects_user_supplied_parameter_in_task501` / `test_paper_spec_service_rejects_user_supplied_evidence_in_task501` + **raw_text 长度 fail-fast 1 项**(R1 二审 P1-8):`test_service_rejects_document_text_over_v0_1_limit` |
| `tests/adapters/parser/test_pdf_parser.py` | magic byte / 超长 / 加密 / 损坏 / 短文本兜底(详 § 风险 4)|
| `tests/adapters/parser/test_docx_parser.py` | magic byte / 含宏 / zip bomb 风格 |
| `tests/adapters/parser/test_sandbox.py` | timeout / mem limit / 子进程崩溃隔离 / 绝对路径脱敏 / 原始文件名脱敏(R1 一审 P0-4)+ **4 项可实现不变量**(R1 二审 P1-4 替换过度承诺):`test_sandbox_child_receives_only_temp_path_and_config` / `test_sandbox_child_cwd_is_isolated_temp_dir` / `test_sandbox_child_env_does_not_include_project_root` / `test_sandbox_error_if_parser_attempts_path_outside_temp_dir` |
| `tests/api/test_paper_upload.py` | 路由端到端(mock LLM)+ 输入白名单 + 错误中文化 + 错误码 machine code(R1 P2-7)+ **临时文件清理 4 项**(R1 二审 P0-2):`test_upload_document_removes_temp_file_on_success` / `test_upload_document_removes_temp_file_on_parse_error` / `test_upload_document_removes_temp_file_on_llm_error` / `test_upload_document_temp_path_does_not_include_original_filename` + **magic byte seek(0) 1 项**(R1 三审 P1-2):`test_upload_document_preserves_magic_prefix_after_sniffing` |

**恶意 fixtures**(TASK-500 留占位,本卡补实际 fixtures,对齐 04 § 8.6 (e),R1 P1-13 修订)— 仅 6 类硬要求;不加 PDF/A(非恶意);xfa_form / encrypted.docx 作为**非阻塞扩展样本**由 Codex 实施期决定是否加,**不作硬要求**:

| 路径 |
|---|
| `tests/fixtures/malicious_documents/encrypted.pdf` |
| `tests/fixtures/malicious_documents/embed_js.pdf` |
| `tests/fixtures/malicious_documents/huge.pdf`(占位 stub,真实生成留 conftest 动态构造)|
| `tests/fixtures/malicious_documents/macro.docx` |
| `tests/fixtures/malicious_documents/zip_bomb.docx`(占位 stub,动态构造)|
| `tests/fixtures/malicious_documents/corrupted.docx` |
| `tests/fixtures/malicious_documents/README.md`(TASK-500 已建,本卡更新)|

### 修改文件清单(5-7 个)

| 路径 | 修改性质 |
|---|---|
| `core/domain/exceptions.py` | +2 leaf:`DocumentParseError(MxaError)` / `PaperSpecGenerationError(MxaError)` |
| `api/main.py` | lifespan 加 `paper_spec_cache` + `text_provider` 复用(若已是 lifespan 单例,沿用;否则按 TASK-203 D16 模式新装)+ 注册 `paper_router` |
| `api/dependencies.py` | 追加 ~3 dependency(`get_paper_spec_service` / `get_paper_spec_cache` / `get_document_parser_router`)|
| `api/middleware/error_handler.py` | 末尾追加 2 handler(`DocumentParseError` → 400 / `PaperSpecGenerationError` → 502)|
| `requirements.txt` | +`pypdf==<version>` + `python-docx==<version>`(具体版本 Codex 实施期查 PyPI 最新稳定 + PM PR review 拍板)|
| `docs/03_TASK_INDEX.md` | TASK-501 行 🔲→🔍(等待验收;Codex 不直接写 ✅,沿用 K_36)|
| `docs/06_OUTPUT_CONTRACTS.md` § 7 修订流程 | 若 06 § 12 字段在本卡实施期发现需要微调,走 § 7 D5 流程同步同源 5 处;若不需调整,本文件不动 |

### 新增依赖

- `pypdf==<Codex Stage 1 查 PyPI 稳定版 + PM PR review 拍板版本>`(D7)
- `python-docx==<同上>`(D7)

**禁止**:Codex 本地 `pip install` 后不写进 `requirements.txt`(04 § 6)。

---

## 范围(必须做)

1. 从 main HEAD `<PM 派单 commit hash>` 切分支 `task/TASK-501-paper-to-model-foundation`
2. **Stage 0 实测**:验证 12 sample files 全在 main + JSON 合法 + 双源不变量过(详 § 给 Codex 的提示)
3. **实地核查上游契约**:`view` 06 § 12 / 04 § 8.6 / 02 § 资料入口数据流 / 决策 22 § 5.2 / 决策 21 / 决策 11 / 决策 18;**关键契约引用对照 main HEAD 节号 + 行号实地核查**(R1 P2-2 修订:不再夸大全文标行号);任一字面与本卡 § 7 接口契约不一致 → 停手报 PM
4. 按 § 实施步骤(5 阶段)实施全部新增 / 修改文件
5. `make check` + `python -m ruff format --check .` + `pip check` + 所有新增测试全过
6. **决策 11 grep 验收**(R1 二审 P1-6 加 exclude):
   - `grep -rnE 'logger\.exception' core/ adapters/ features/paper/ api/ --include='*.py' --exclude-dir=".venv" --exclude-dir=".git"` 仅在 MCS 既有处命中,**paper / parser / api/routes/paper_upload 路径任一处命中即 Fail**
   - `grep -rn 'asyncio.to_thread' features/paper/paper_spec_service.py api/routes/paper_upload.py --exclude-dir=".venv" --exclude-dir=".git"` 命中(service **≥ 3 处**:router.route + sandbox parser + LLM,R1 二审 P1-3;route ≥ 3 处:文件保存 + SHA-256 + cleanup,R1 一审 P1-5 + R1 二审 P0-2)
7. **决策 21 boundary grep 验收**(R1 二审 P1-5 + P1-6 修订 — regex 扩展 + exclude):
   - `grep -rnE '(^|[[:space:]])(from|import)[[:space:]]+features\.(overview|explanation)|features\.(overview|explanation)\.' features/paper/ adapters/parser/ core/domain/paper_*.py --exclude-dir=".venv" --exclude-dir=".git"` 应空(覆盖 `from features.overview ...` / `import features.overview...` / `features.overview.foo` 直接引用)
   - `grep -rnE "EvidencePack|ExplanationPack|_evidence_builder|overview_schemas|ProjectOverview" features/paper/ adapters/parser/ core/domain/paper_*.py --exclude-dir=".venv" --exclude-dir=".git"` 应空
8. **本卡合并守门红线 6 项实测**(逐个跑;命令输出贴 PR 完工 report,沿用 TASK-500 v0.2.1 R6.1 模式):
   - `git diff --name-only origin/main -- core/domain/project_overview.py` 应空
   - `git diff --name-only origin/main -- features/overview/overview_schemas.py` 应空
   - `git diff --name-only origin/main -- core/prompts/project_overview.yaml` 应空
   - `git diff --name-only origin/main -- features/overview/` 应空
   - `git diff --name-only origin/main -- features/explanation/` 应空
   - `git diff --name-only origin/main -- features/explanation/_evidence_builder.py` 应空(冗余但保留 — 显式列出)
9. **样本包未改实测**:`git diff --name-only origin/main -- eval/cases/paper_to_model/` 应空(任一字面改动 = K_36 反例,走 task-500 v0.2.2 微补丁,不在本卡)
10. **freeze test + sample roundtrip 实测**:`pytest tests/features/paper/test_paper_schemas_freeze.py tests/features/paper/test_paper_schemas_sample_roundtrip.py -v` 全过
11. **隐私 grep**(R1 一审 P1-7 + R1 二审 P1-6 加 exclude):
    - `grep -rnE "logger\.(debug|info|warning|error).*file\.filename|logger\.(debug|info|warning|error).*raw_text|logger\.(debug|info|warning|error).*response\.(text|content)|str\(exc\)|repr\(exc\)" features/paper/ adapters/parser/ api/routes/paper_upload.py --exclude-dir=".venv" --exclude-dir=".git"` 应空,或逐项说明是安全元数据
12. **临时文件清理实测**(R1 二审 P0-2 新增,R1 三审 P1-5 命令规范化):API 测试结束后跑
    ```bash
    find "$PAPER_TMP_ROOT" -maxdepth 2 \
      \( -path "$PAPER_TMP_ROOT/.venv" -o -path "$PAPER_TMP_ROOT/.git" \) -prune -o \
      -type f -print
    ```
    应为空(或只剩 TTL 管理元数据;**不得剩 raw PDF/docx**);若有残留 = R6.1 Fail
13. **真启动验收**(R1 二审 P1-7 修订:输入源歧义消解):
    - **使用剥离版 docx**:由 `material_to_plan/case_01_motor_short_circuit/input/source_doc_stripped.md` 生成 docx,或 PM 明确提供"剥离版 docx"
    - uvicorn 单 worker + `curl -X POST /api/v1/upload-document -F file=@<剥离版.docx>` 全过(需 PM 配 `.env` `DEEPSEEK_API_KEY`)
    - **只有剥离版适用 A2 工程决定字段禁出项**(`5MW` / `平衡节点` / `0.2s 故障` / `ode15s` / `1s`);若 PM 提供原始 PoC docx 而非剥离版,只验 schema / 类型 / 双源 / locator,**不验 A2 禁出项**
14. 改 03 索引(字节级 Python,LF/CRLF 双试,沿用 TASK-310 chore 模式)
15. 完工三件套(决策 08)+ 提 PR(Codex 给 PM 标题 + 正文,PM 走 GitHub 网页创建)

---

## 不做(明确排除)

### 范围红线(本卡 = 资料入口骨架 + PaperSpec)

- ❌ **PaperPlanService**(PaperSpec → ModelGenerationPlan)— 留 TASK-502(详 D12)
- ❌ **9-component prompt 子角色完整实现**(LibrarySelector / BlockRecommender / ParameterMapper / SubsystemPlanner / MScriptDrafter)— 留 TASK-502(本卡 PaperSpec 抽取 prompt 仅有 **Extractor 角色**;EvidenceTagger 不算独立组件,只是 evidence 字段约束,R1 P2-3 修订)
- ❌ **MissingDetector**(识别图占位 → 生成 MissingParameterPrompt 列表)— 留 TASK-502
- ❌ **UserSupplyMerger**(用户补充 + 双源标记 + 更新 plan)— 留 TASK-502
- ❌ **TuningSuggestion service** — 留 TASK-503
- ❌ **evaluator 完整跑分**(对照 12 sample files 给整体门槛 5 评分)— 留 TASK-502;本卡仅做"sample roundtrip"结构层校验 + 单 case PaperSpec 人工评测(§ 7.7)
- ❌ **`GET /api/v1/papers/{paper_id}/spec` 路由** — 留 TASK-503(R1 P0-3 修订;本卡 InMemory cache 模式下 GET 命中率为 0,GET + 持久化 cache 一并归 TASK-503)
- ❌ **前端 UX 闭环**(MissingParameterPrompt UI / 用户补充表单)— 留 TASK-503
- ❌ **多文档融合 / 图片 OCR / 控制 + 信号处理子类样本** — v0.2 范围(决策 23 § 2.1)

### 红线(本卡合并守门 + 决策 21 + 决策 11,Codex 必守)

- ❌ 不修改本卡合并守门红线 6 项(§ 输入 红线表)
- ❌ `features/paper/` 不 import `features/overview/` / `features/explanation/` 私有结构(决策 21)
- ❌ `core/domain/paper_*.py` 不 import 任何 `features/` 路径(单向分层)
- ❌ 不修改样本包 12 文件任何字面
- ❌ 不接 MATLAB Engine(留 v0.3,决策 23 § 2.2)
- ❌ 不接 CAJ 知网格式
- ❌ 不接 paper-to-model 6 类之外的工科领域
- ❌ 不承诺"自动生成 .slx" / "一键生成" / "完整仿真模型" / "成品生成"等表述(决策 22 § 1.1)
- ❌ 不引入除 pypdf / python-docx 外的新 pip 依赖(若 Codex 实施期发现需要其他依赖 → 停手报 PM,走 04 § 6 PR review)

---

## 实施步骤(5 阶段)

**Commit 拆分原则**:Conventional Commits;subject **单行无 body**(反例 17);按文件改动自然拆分。

### 阶段 1 — 基础设施 + domain 层(2-3 commit)

- 新增 5 个 domain dataclass 文件(`paper_evidence.py` / `paper_spec.py` / `paper_plan.py` / `paper_tuning.py` / `paper_missing.py`,共 5 顶层 + 6 子项 dataclass + EvidenceSource enum)
- 新增 `core/interfaces/document_parser.py`:`DocumentParser` ABC + `ParsedDocument` 结构 + `DocumentParserRouter` 接口(R1 P1-11 修订)
- 新增 2 leaf 异常(`DocumentParseError` / `PaperSpecGenerationError`)
- domain 层单测(各文件配套)
- **不动** API / service / parser

### 阶段 2 — Pydantic wrapper + freeze test + JSON schema(2 commit)

- 新增 `features/paper/paper_schemas.py`(**5 个顶层 wrapper + 6 个 nested submodel** + 双源不变量 model_validator + `.to_domain()` / `.from_domain()`,R1 P0-2 修订)
- 新增 `tests/features/paper/test_paper_schemas_freeze.py`(覆盖反模式 **1/2/3/4 全部**,R1 P2-1 修订)
- 新增 `tests/features/paper/test_paper_schemas_sample_roundtrip.py`(4 个 sample JSON;`expected_missing_prompts.json` 按 dict-with-`missing_prompts`-list 校验,其他单对象,R1 二审 P0-1 架构师反向采纳)
- 新增 `scripts/export_paper_schemas.py` + 跑一遍导出 5 个 `schemas/paper_*.schema.json`

### 阶段 3 — Parser 适配层 + 沙箱(2-3 commit)

- 新增 `adapters/parser/pdf_parser.py`(pypdf 实现 + magic byte)
- 新增 `adapters/parser/docx_parser.py`(python-docx 实现 + magic + 包内 `[Content_Types].xml`)
- 新增 `adapters/parser/_sandbox.py`(子进程隔离 + RLIMIT_AS / RLIMIT_CPU + SIGALRM + **子进程权限隔离 + 错误脱敏**,R1 P0-4 + P1-10 修订)
- 实际 fixtures 落 `tests/fixtures/malicious_documents/`(覆盖 04 § 8.6 (e) 6 类)
- parser + sandbox 单测(R1 三审 P1-6 修订:替换 v0.2 过度承诺旧表述 "子进程不持可写 project 目录",改为 v0.3 已采纳的 4 项可实现不变量):
  - `test_parse_error_sanitizes_absolute_path`
  - `test_parse_error_sanitizes_original_filename`
  - `test_sandbox_child_receives_only_temp_path_and_config`
  - `test_sandbox_child_cwd_is_isolated_temp_dir`
  - `test_sandbox_child_env_does_not_include_project_root`
  - `test_sandbox_error_if_parser_attempts_path_outside_temp_dir`
- requirements.txt 加 pypdf + python-docx(版本号 PR review)

### 阶段 4 — PaperSpecService + Prompt + 校验五步(2-3 commit)

- 新增 `features/paper/_paper_spec_cache.py`(`InMemoryPaperSpecCache` 含 `asyncio.Lock` 保护,对齐 TASK-203 OverviewCache 模式;通过 `__init__.py` re-export,自审补强)
- 新增 `core/prompts/paper_spec_extract.yaml`(v0.1 prompt 模板;含 locator 白名单注入,R1 P1-3 修订)
- 新增 `features/paper/_paper_spec_extractor.py`(prompt 构造 + 输出解析辅助)
- 新增 `features/paper/paper_spec_service.py`(`PaperSpecService` 类,五步校验 + cache + asyncio.to_thread)
- service 单测(mock LLM + cache hit/miss + 五步校验各异常分支 + figure 反幻觉 + locator 白名单)

### 阶段 5 — API 端到端 + 收尾(2-3 commit)

- 新增 `api/routes/paper_upload.py`(`POST /api/v1/upload-document` + `UploadDocumentResponse` Pydantic model 定义,自审补强;**不**含 GET,R1 P0-3)
- `api/main.py` lifespan 加 `paper_spec_cache` 装配 + 注册 router
- `api/dependencies.py` 追加 3 dependency
- `api/middleware/error_handler.py` 末尾追加 2 handler(machine code 标准化,R1 P2-7)
- 端到端 API 测试(mock LLM + 真 parser)
- 03 索引字节级修订:TASK-501 行 🔲 → 🔍(等待验收;沿用 K_36)
- 完工三件套(决策 08)+ R6.1 实测命令输出贴 PR + 提 PR

---

## 接口契约

### 7.1 domain 层文件拆分粒度(D3)

按 06 § 12 节结构对齐(5 文件,11 dataclass + 1 enum):

| 06 节 | core/domain 文件 | 含 entity |
|---|---|---|
| § 12.2 + 12.3 | `paper_evidence.py` | `EvidenceSource` enum + `PaperEvidenceEntry` |
| § 12.4 | `paper_spec.py` | `PaperSpec` + `EquationEntry` + `ParameterEntry` + `FigureRef` |
| § 12.5 | `paper_plan.py` | `ModelGenerationPlan` + `BlockRecommendation` + `ParameterMapping` |
| § 12.6 | `paper_tuning.py` | `TuningSuggestion` + `ParameterDirection` |
| § 12.7 | `paper_missing.py` | `MissingParameterPrompt` |

所有 domain 文件:**纯 Python `@dataclass(frozen=True)` + `Literal` + `Enum`**,**无任何业务逻辑 / 方法**(决策 18 + 决策 21 boundary)。

### 7.2 EvidenceSource enum + PaperEvidenceEntry domain dataclass

**字面对齐 06 § 12.2 + § 12.3**(本卡不重抄字段表,真值源在 06)。

`PaperEvidenceEntry` dataclass(6 字段):

```python
# core/domain/paper_evidence.py

from dataclasses import dataclass
from enum import Enum

class EvidenceSource(str, Enum):
    DOCUMENT_EXTRACTED = "document_extracted"
    USER_SUPPLIED = "user_supplied"

@dataclass(frozen=True)
class PaperEvidenceEntry:
    source: EvidenceSource
    paper_section_id: str | None
    equation_id: str | None
    figure_id: str | None
    excerpt: str | None
    missing_param_prompt_id: str | None
```

**两套不变量**(06 § 12.3 字面;校验位置 = Pydantic wrapper `model_validator(mode='after')`):

- `source = document_extracted`:`paper_section_id` / `equation_id` / `figure_id` 至少一个非 None + `excerpt` 1-300 字非空 + `missing_param_prompt_id` 必为 None
- `source = user_supplied`:三个 paper locator 全为 None + `excerpt` 必为 None + `missing_param_prompt_id` 必填

### 7.3 PaperSpec / 子项 domain dataclass

**字面对齐 06 § 12.4 + 子项表**。

`PaperSpec`(9 字段)+ 子项 `EquationEntry`(3 字段)/ `ParameterEntry`(5 字段,含 `source: EvidenceSource`)/ `FigureRef`(3 字段)。

**关键 invariant**(Pydantic 层强校):

- `domain` 必须 ∈ 6 类 `project_type`,**拒绝 `general`**(06 § 12.1)
- `paper_type` ∈ `Literal["paper", "report", "thesis"]`
- `evidence` 至少 1 个 `PaperEvidenceEntry`
- 所有 `ParameterEntry.source` 必须 ∈ `EvidenceSource` enum
- `figure_locations` 可空数组(剥离版资料无图时 `[]`,详样本包 case_README § 6 反幻觉红线第 1 条)

**TASK-501 范围内 PaperSpec evidence 全为 `document_extracted`**:本卡 PaperSpec 抽取阶段无用户补充流程(自审补强;`user_supplied` evidence 留 TASK-502 UserSupplyMerger 引入)。

### 7.4 ModelGenerationPlan / TuningSuggestion / MissingParameterPrompt — serialize-only

**字面对齐 06 § 12.5 / § 12.6 / § 12.7**。

**TASK-501 范围**:

- 落地 domain dataclass(`paper_plan.py` / `paper_tuning.py` / `paper_missing.py`)
- 落地 Pydantic wrapper(`features/paper/paper_schemas.py` 内,顶层 3 wrapper + nested submodel)
- 落地 freeze test(对齐 06 字段表)
- 落地 sample roundtrip 测试(4 个 sample JSON × Pydantic 反序列化 + round-trip)
- 落地 JSON schema 导出

**不落地**(留 TASK-502 / 503):这 3 类的**生成 service** / API 路由消费 / 实际 prompt yaml(本卡 prompt 仅含 PaperSpec 抽取)。

### 7.5 Pydantic wrapper 设计(`features/paper/paper_schemas.py`)— R1 P0-2 修订

**对齐决策 18 序列化边界**(A 类保留 Pydantic / B 类 core dataclass / C 类 bridge):

- **A 类**(API 边界):`api/routes/paper_upload.py` `response_model` 用 `UploadDocumentResponse`(含 `PaperSpecModel`)
- **B 类**(内部):`features/paper/paper_spec_service.py` 内部 service 返回 core dataclass `PaperSpec`
- **C 类**(bridge):`paper_schemas.py` 提供 `.to_domain()` / `.from_domain()`;service 内部用 core,API 层 `.from_domain()` 转回 Pydantic

**5 个顶层 Pydantic model wrapper**:

| Wrapper | 对应顶层 domain | 校验逻辑(`model_validator(mode='after')`)|
|---|---|---|
| `PaperEvidenceEntryModel` | `PaperEvidenceEntry` | **两套不变量**(§ 7.2),反模式 2 / 3 拦截 |
| `PaperSpecModel` | `PaperSpec` | `domain ≠ general`(Pydantic Literal 已硬拦,wrapper 层为序列化边界标准约束;不在 service 层重复)+ `evidence ≥ 1` + 子项校验 |
| `ModelGenerationPlanModel` | `ModelGenerationPlan` | `subsystem_breakdown` 3-10 步 + `evidence ≥ 1` |
| `TuningSuggestionModel` | `TuningSuggestion` | `parameter_directions ≥ 1` + `confidence ∈ Literal[3]` + `disclaimer` 必填 |
| `MissingParameterPromptModel` | `MissingParameterPrompt` | `paper_reference.source == document_extracted` + `source == user_supplied` 恒定 |

**6 个 nested submodel**(对应 6 个子项 dataclass):

- `EquationEntryModel` / `ParameterEntryModel` / `FigureRefModel` / `BlockRecommendationModel` / `ParameterMappingModel` / `ParameterDirectionModel`

**EvidenceSource enum 直接复用**(R1 二审 P2-2 修订):Pydantic wrapper 直接复用 `core.domain.paper_evidence.EvidenceSource`,**不重定义镜像 enum**(对齐决策 18:domain enum 是 contract,wrapper 序列化时 Pydantic 自然支持 Python enum)

所有 wrapper:`model_config = ConfigDict(extra="forbid")`(反模式 4 拦截)。

**`.to_domain()` / `.from_domain()` 桥接对齐决策 18 模式**:

```python
class PaperSpecModel(BaseModel):
    # ... fields mirror dataclass ...
    model_config = ConfigDict(extra="forbid")

    def to_domain(self) -> PaperSpec:
        return PaperSpec(
            paper_title=self.paper_title,
            # ... explicit field mapping ...
        )

    @classmethod
    def from_domain(cls, spec: PaperSpec) -> "PaperSpecModel":
        return cls(
            paper_title=spec.paper_title,
            # ...
        )
```

### 7.6 freeze test 设计 — R1 P2-1 修订

**对齐 06 § 7 D1-B 三层同源(决策 13 + TASK-310 PR #1 模式)**。

`tests/features/paper/test_paper_schemas_freeze.py` 守门(反模式 1/2/3/4 全覆盖):

| Test 项 | 校验 |
|---|---|
| `test_paper_spec_fields_frozen` | `PaperSpec` dataclass `__annotations__` keys 字面 ∈ 06 § 12.4 字段表(9 个),无新增无遗漏 |
| `test_paper_evidence_fields_frozen` | `PaperEvidenceEntry` 6 字段 ∈ 06 § 12.3 |
| `test_model_generation_plan_fields_frozen` | `ModelGenerationPlan` 8 字段 ∈ 06 § 12.5 |
| `test_tuning_suggestion_fields_frozen` | `TuningSuggestion` 7 字段 ∈ 06 § 12.6 |
| `test_missing_parameter_prompt_fields_frozen` | `MissingParameterPrompt` 7 字段 ∈ 06 § 12.7 |
| `test_pydantic_dataclass_field_consistency` | 各 Pydantic wrapper 字段名 / 顺序 / 类型 = domain dataclass(决策 18 round-trip)|
| `test_anti_pattern_1_domain_general_rejected` | 反模式 1:`domain = "general"` → ValidationError |
| `test_anti_pattern_2_user_supplied_disguise_rejected` | 反模式 2:`user_supplied` + 三 locator 非 None / excerpt 非 None / missing_param_prompt_id None 任一 → ValidationError |
| `test_anti_pattern_3_document_extracted_no_locator_rejected` | 反模式 3 子句 1(R1 二审 P2-3 拆):`document_extracted` + 三 locator 全 None → ValidationError(对齐 06 § 12.8 反模式 3 字面 payload)|
| `test_anti_pattern_3_document_extracted_no_excerpt_rejected` | 反模式 3 子句 2(R1 二审 P2-3 拆):`document_extracted` + locator ≥ 1 + excerpt = None → ValidationError(06 § 12.8 反模式 3 语义"没有 locator **或** 摘录"两子句)|
| `test_anti_pattern_4_evidencepack_shape_rejected` | 反模式 4(R1 二审 P1-1 改名 + 字面 payload):`{"evidence_pack_kind": "parameter_context", "paper_section_id": "sec-2"}` → ValidationError(对齐 06 § 12.8 反模式 4 字面;直接验"EvidencePack 子集消费"被拦)|
| `test_extra_forbid_generic_unknown_field` | (R1 二审 P1-1 另起名)generic extra 字段 → ValidationError(`extra=forbid` 通用语义,与反模式 4 区分)|

**真值源**:本测试断言列出的字段 list 必须与 06 § 12 字段表**逐字符对齐**;06 改字段 = 测试 Fail + 走 § 7 D5 修订流程同步(决策 13)。

### 7.7 sample roundtrip 测试 — R1 P1-6 修订

`tests/features/paper/test_paper_schemas_sample_roundtrip.py`:

**4 个 sample JSON artifacts**(校验类型区分):

| Sample JSON 路径 | 校验类型 | 校验 Pydantic |
|---|---|---|
| `material_to_plan/case_01_motor_short_circuit/golden/expected_paper_spec.json` | 单对象 | `PaperSpecModel.model_validate_json(...)` |
| `material_to_plan/case_01_motor_short_circuit/golden/expected_model_generation_plan.json` | 单对象 | `ModelGenerationPlanModel.model_validate_json(...)` |
| `missing_param/case_01_missing_image_param/input/expected_missing_prompts.json` | **顶层 dict 含 `missing_prompts: list[MissingParameterPrompt]`**(注意在 `input/` 不在 `golden/`;R1 二审 P0-1 架构师反向采纳:samples JSON 实际是 dict wrapper 不是 list)| `json_data = json.loads(...); assert isinstance(json_data, dict); [MissingParameterPromptModel.model_validate(item) for item in json_data["missing_prompts"]]` |
| `missing_param/case_01_missing_image_param/golden/expected_updated_plan.json` | 单对象 | `ModelGenerationPlanModel.model_validate_json(...)` |

对每个 JSON:

1. Pydantic 反序列化成功(structural)
2. `.to_domain()` 成功(domain conversion)
3. `.from_domain(<domain>)` 成功(re-encode)
4. re-encoded JSON 与原 JSON 字段集等价(允许字段顺序差异,但字段集 + 值必相等)
5. 所有 evidence 数组中每个 `PaperEvidenceEntry` 满足双源不变量(`verification_method.md` § 3 字面)

**这是 TASK-501 最关键验收锚点**:**4 个 sample JSON × Pydantic 全过 = schema 与样本包对齐;任一 Fail = schema 错或样本包错(后者走 task-500 v0.2.2,前者本卡修)**。

### 7.8 DocumentParser ABC + DocumentParserRouter(`core/interfaces/document_parser.py`)— R1 P1-3 + P1-11 修订

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass(frozen=True)
class FigurePlaceholder:
    """Parser 注入的图占位(R1 P1-2 修订:figure_id 需可校验)"""
    figure_id: str                     # e.g. "FIG-01"
    caption: str                       # parser 抽到的 caption(可能空)
    paper_section_id: str | None       # 占位所在节(若 parser 能识别)

@dataclass(frozen=True)
class ParsedLocatorIndex:
    """Parser 注入的 locator 白名单 — LLM 输出必须落在这个集合内(R1 P1-3 修订)"""
    section_ids: list[str]             # 章节 ID,e.g. ["S1", "S2", ...]
    equation_ids: list[str]            # 公式 ID,e.g. ["EQ-01"]
    figure_ids: list[str]              # 图占位 ID,e.g. ["FIG-01", "FIG-02"]

@dataclass(frozen=True)
class ParsedDocument:
    """Parser 抽取的结构化结果(LLM 输入前)"""
    raw_text: str                          # 文档全文本(段落以 \n\n 分隔)
    page_count: int | None                 # PDF 页数;docx 为 None
    figure_placeholders: list[FigurePlaceholder]  # 图占位(R1 P1-2:从 list[str] 升级)
    table_placeholders: list[str]          # 表占位(docx 0 表 / PDF 表抽取留 v0.2)
    locator_index: ParsedLocatorIndex      # 章节 / 公式 / 图 ID 白名单(R1 P1-3)
    file_hash: str                         # SHA-256(文件内容)
    extracted_at: datetime                 # 抽取时间

class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        ...

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """magic byte 校验 + 扩展名匹配"""
        ...

class DocumentParserRouter:
    """根据 magic byte + 扩展名分发到具体 parser;不匹配 → DocumentParseError(R1 P1-11)"""

    def __init__(self, parsers: list[DocumentParser]) -> None:
        # parsers 列表由 api/dependencies.py 装配传入;
        # Router 自身只依赖 DocumentParser ABC,不 import PdfParser / DocxParser
        self._parsers = parsers

    def route(self, file_path: Path) -> DocumentParser:
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        raise DocumentParseError("不支持的文档格式")
```

**层级约束**(R1 P1-11):

- `DocumentParserRouter` 落 `core/interfaces/document_parser.py`,与 ABC 同文件;**仅依赖 `DocumentParser` ABC**,不 import 任何具体实现
- `PdfParser` / `DocxParser` 在 `adapters/parser/` 实现,只在 `api/dependencies.py` 装配时实例化注入
- `features/paper/paper_spec_service.py` 通过 `DocumentParserRouter` 间接消费 parser,不直接 import `adapters.parser.*`

### 7.9 Parser sandbox(`adapters/parser/_sandbox.py`)— R1 P0-4 + P1-10 修订

**对齐 04 § 8.6 (c) + (g) 字面**:

- 子进程隔离(`multiprocessing.Process` + `Queue` 传结果)
- 默认 timeout 30s(可配置)
- 默认 mem 512MB(`resource.setrlimit(RLIMIT_AS, ...)`,Linux)
- 子进程崩溃不影响主进程(`process.exitcode != 0` → `DocumentParseError`)

**子进程权限隔离**(R1 P0-4 修订,新增):

- 子进程只接收 sandbox 临时文件路径 + parser 配置;**不得**持有 project root / upload root 的可写句柄
- 子进程 cwd 设为隔离临时目录
- 解析前清理敏感 env(`os.environ` 子集白名单)
- 不联网(无显式禁止 socket 调用,但 parser 库本身不应发起网络请求,测试覆盖)

**错误脱敏**(R1 P0-4 修订,新增):

- 父进程捕获子进程异常时,**只映射为 `DocumentParseError(error_code)`**,不得把 traceback / absolute path / 原始文件名 / 原异常 `str(exc)` 透传到 API 或日志
- 错误 message 仅含中文化 + machine code,不含路径

**接口**:

```python
def run_in_sandbox(
    parser: DocumentParser,
    file_path: Path,
    timeout_seconds: float = 30.0,
    mem_limit_bytes: int = 512 * 1024 * 1024,
) -> ParsedDocument
```

**异常**:超时 / OOM / 崩溃 / 权限违反 → 抛 `DocumentParseError`(400,中文化"文档解析失败,请检查文件是否损坏或超过 512MB")。

**跨平台 trade-off**(R1 P1-10 修订,明确环境策略):

| 环境 | 内存上限策略 | 上线决议 |
|---|---|---|
| Linux(生产 / CI)| `RLIMIT_AS` 硬限制(对齐 04 § 8.6 (c) 字面)| 生产 / CI 安全验收以此为门槛 |
| Windows / macOS(本地开发)| **不引 `psutil`**(R1 二审 P0-3 修订);`multiprocessing.Process` + 30s timeout + 子进程 cwd 隔离 + 错误脱敏仍生效(无 mem 强制上限,依赖 OS OOM-killer 兜底)| 仅本地开发 unit test 用;**不视为满足生产上传安全**;PR 风险段必须标明"非 Linux 不提供 mem 强制上限"|
| Windows 生产 | **不支持**(若 PM 要求 Windows 生产支持,v0.1 fail-closed:非 Linux 启动真实解析时 → `DocumentParseError("unsupported_parser_sandbox_platform")`)| 留 PM 决策点 — v0.1 默认不支持 Windows 生产 |

**决策依据**(R1 二审 P0-3 修订):`psutil` 不在 stdlib;若引入会与"除 pypdf / python-docx 外不引依赖"红线冲突。本卡 v0.1 不为本地开发引入额外依赖;multiprocessing + timeout 已提供 timeout / 进程崩溃隔离 / cwd 隔离 / env 清理 / 错误脱敏五项保护,仅缺 mem 强制上限,可接受作为本地 unit test 边界。

**测试要求**(R1 一审 P0-4 修订 + R1 二审 P1-4 改正为可实现不变量):

- `test_parse_error_sanitizes_absolute_path`:故意触发 parser 异常,断言抛出的 `DocumentParseError.message` 不含本机绝对路径(grep `/home` / `/Users` / `C:\\`)
- `test_parse_error_sanitizes_original_filename`:断言抛出的 error message 不含原始上传文件名
- **新增 4 项可实现不变量测试**(R1 二审 P1-4 修订,替换 v0.2 过度承诺的 `test_child_process_cannot_write_project_dir`):
  - `test_sandbox_child_receives_only_temp_path_and_config`:子进程参数序列化后只包含临时路径 + parser 配置,无 project root path
  - `test_sandbox_child_cwd_is_isolated_temp_dir`:子进程内 `os.getcwd()` 返回隔离临时目录,非 project root
  - `test_sandbox_child_env_does_not_include_project_root`:子进程 `os.environ` 不含 project root 路径相关 env(如 `MXA_PROJECT_ROOT`)
  - `test_sandbox_error_if_parser_attempts_path_outside_temp_dir`:parser 实现内若尝试访问临时目录外路径 → 抛 `DocumentParseError`

**注**(R1 二审 P1-4):`multiprocessing` 子进程默认与父进程同 OS 用户;**仅靠 cwd 隔离 + env 清理 + 只传临时路径,不能从 OS 权限上阻止"如果代码拿到了 project root path 就写入"**。要实现 OS 级硬隔离需要 chroot / namespace / 容器,本卡不引入。本卡 v0.1 通过"不传 project root path 给子进程 + parser 调用层抽象"实现软隔离;若 PM 后续要求 OS 级硬隔离,留 Phase 2 评估。

### 7.10 PaperSpecService 设计(类比 TASK-203 ProjectOverviewService)— R1 P0-1 修订

**构造签名**:

```python
class PaperSpecService:
    def __init__(
        self,
        cache: PaperSpecCache,
        text_provider: TextProvider,
        document_parser_router: DocumentParserRouter,
        timeout: float = DEFAULT_PAPER_SPEC_TIMEOUT_SECONDS,  # 60.0
        max_tokens: int = DEFAULT_PAPER_SPEC_MAX_TOKENS,       # 4000
    ) -> None
```

**主入口**(R1 P2-5 修订:签名统一):

```python
async def extract(self, file_path: Path, paper_id: str) -> PaperSpec
```

**行为**:

1. `cached = await cache.get(paper_id)`;hit 直返(本卡 InMemory cache 同进程内同 paper_id 二次调用极少触发;cache 主要作为 TASK-502 接力面,详 D12)
2. `parser = await asyncio.to_thread(document_parser_router.route, file_path)` 选 parser **(R1 二审 P1-3 修订:`supports(file_path)` 含 docx ZipFile 同步 IO,async service 内必须 `to_thread` 桥接)**
3. `parsed = await asyncio.to_thread(run_in_sandbox, parser, file_path)` **(决策 11 决策 1)** — parser 在子进程沙箱内跑
4. **raw_text 长度 fail-fast**(R1 二审 P1-8 修订,新增):若 `len(parsed.raw_text) > MAX_PAPER_RAW_TEXT_CHARS`(默认 80_000 字符,可配置)→ 抛 `DocumentParseError("document_too_long_for_v0_1")`。**v0.1 不做静默截断**,避免 evidence locator 与文本不一致。Streaming PaperSpec 抽取留 Phase 2(详 § 后续 task 接力点)。
5. `messages = build_messages(parsed)` — 纯函数构造 prompt(注入 `parsed.locator_index` 白名单,R1 P1-3)
6. `response = await asyncio.to_thread(text_provider.chat, messages, json_mode=True, ...)` **(决策 11 决策 1)**
7. `_parse_and_validate(response, parsed)` 五步校验(下)
8. `await cache.put(paper_id, paper_spec)` + return

**校验五步**(`_parse_and_validate`,对齐 TASK-203 v0.3 模式,R1 P0-1 + P1-2 + P1-3 修订):

| Step | 校验 | 失败处理 |
|---|---|---|
| 1 | `json.loads(response.text)` — **R1 P0-1 修订:`LLMResponse.text` 字段,非 `.content`**;对齐 `docs/02_ARCHITECTURE_OVERVIEW.md` § 4.3 字面 | `PaperSpecGenerationError`(502)|
| 2 | `PaperSpecModel.model_validate(...)`(9 字段 + Literal[6] domain + 子项 + double-source invariants + `extra=forbid` + 反模式 1/2/3/4)| `PaperSpecGenerationError` |
| 3 | **`figure_locations` 反幻觉**(R1 P1-2 修订,改两段):<br>(a) 若 `parsed.figure_placeholders == []`,则 `spec.figure_locations == []`;<br>(b) 若 `parsed.figure_placeholders` 非空,则 `spec.figure_locations[*].figure_id` 必须 ∈ `{p.figure_id for p in parsed.figure_placeholders}` | `PaperSpecGenerationError` |
| 4 | **locator 白名单**(R1 P1-3 修订,新增):所有 `PaperEvidenceEntry.paper_section_id` ∈ `parsed.locator_index.section_ids`(若非 None);`equation_id` ∈ `equation_ids`;`figure_id` ∈ `figure_ids`(Step 3 已部分覆盖);所有 `EquationEntry.equation_id` 必须唯一且 ∈ `equation_ids` | `PaperSpecGenerationError` |
| 5 | **双源不变量冗余防御 + 本卡阶段语义校验**(R1 二审 P1-2 修订):<br>(a) `spec.parameter_table[*].source` 必须全部为 `document_extracted`(本卡 PaperSpec 抽取阶段无用户补充流程,Pydantic 层只保证 enum 合法,不保证本卡阶段语义合法);<br>(b) `spec.evidence[*].source` 必须全部为 `document_extracted`(同上);<br>(c) 每个 entry 跑 `verification_method.md` § 3 第一套不变量(Pydantic Step 2 已拦,此为冗余防御);<br>`user_supplied` 路径留 TASK-502 UserSupplyMerger | `PaperSpecGenerationError` |

**异常分支统一**:`logger.error(..., type(exc).__name__) + from None`(决策 11 决策 2);**禁** `logger.exception` / `str(exc)` / `repr(exc)` / `response.text` / `raw_text` 落日志(R1 P1-7 修订)。

`LLMError` 子类 5 类(`LLMAuthError` / `LLMQuotaError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError`)直接向上抛,由 ERROR_MAP 翻译(TASK-203 v0.3 已落 8 handler;本卡 v0.1 不重复)。

### 7.11 Prompt 模板(`core/prompts/paper_spec_extract.yaml`)— R1 P1-2 + P1-3 修订

字段约定:`version: "v0.1"` / `description` / `system` / `user`。

`user` 段含 `{raw_text}`(parser 抽到的全文本)/ `{figure_placeholders}`(图占位列表:`figure_id + caption + section_id`)/ `{table_placeholders}`(表占位)/ **`{section_ids}` / `{equation_ids}` / `{figure_ids}`**(R1 P1-3:locator 白名单)。

**system 必须明示**(关键 invariant,对齐样本包反幻觉红线):

1. 9 字段 JSON schema 字段约定(对齐 06 § 12.4)
2. `domain` 只能从 6 个 `project_type` 选一个;`general` **禁止使用**(必须在 6 类中选一)
3. `paper_type` ∈ `Literal["paper", "report", "thesis"]`
4. **反幻觉硬约束**:
   - `parameter_table` 只列资料原文显式给出的参数,**不编造**
   - `equations` 字面引用资料公式,**不改写**
   - `figure_locations`:**只有当 `{figure_placeholders}` 非空时**才输出对应条目;`{figure_placeholders}` 为空 → `figure_locations: []`(R1 P1-2)
   - **不编造资料未给的工程决定字段**(R1 三审 P2-2 修订:加条件,不一刀切禁词):
     - **剥离版资料未明示给出**`5MW 负荷 / 平衡节点 / 0.2s 故障 / ode15s / 1s` 时,**严禁输出**这些字段(否则即幻觉)
     - **若原文明确出现这些值**,只能作为 `document_extracted` 参数(进 `parameter_table[*]`)或 evidence(进 `evidence[*].excerpt`)抽取;**不得**扩展成 ModelGenerationPlan 的工程搭建决定(`subsystem_breakdown / library_choice / parameter_mapping`)— 这些是 TASK-502 范围
5. **locator 白名单约束**(R1 P1-3,新增):
   - **`paper_section_id` 只能从 `{section_ids}` 列表中选**;不得自造 `S6 / S7`
   - **`equation_id` 只能从 `{equation_ids}` 列表中选**;不得自造 `EQ-99`
   - **`figure_id` 只能从 `{figure_ids}` 列表中选**;不得自造 `FIG-99`
   - 如果资料文本提到"如图 1 所示"但 `{figure_ids}` 中无对应 ID,**只能进 evidence.excerpt,不能进 `figure_locations`**
6. **双源契约**:
   - `parameter_table` 各项 `source` 全为 `document_extracted`(本卡 PaperSpec 抽取阶段无用户补充)
   - `evidence` 数组所有项 `source` 全为 `document_extracted`,严格遵守 06 § 12.3 第一套不变量(三 locator ≥ 1 + excerpt 1-300 字非空 + missing_param_prompt_id = None)
7. **`abstract`** 1-1000 字,基于资料"任务陈述 / 摘要 / 物理含义"段综合(不简单 copy 第一段)
8. **`pseudocode_blocks`** 0-N 项,基于资料公式 + 计算方法描述综合(每项 ≤ 500 字)
9. 教学口吻(05 § 8)

版本号(05 § 9.2):本卡起 v0.1;后续 prompt 修改必须升版本 + 跑评测 + PR review。

### 7.12 API 路由(`api/routes/paper_upload.py`)— R1 P0-3 + P1-5 + P2-7 修订

```python
class UploadDocumentResponse(BaseModel):
    """POST /api/v1/upload-document 响应 model(自审补强:本卡定义)"""
    paper_id: str
    spec: PaperSpecModel
    model_config = ConfigDict(extra="forbid")


@router.post("/api/v1/upload-document", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    service: PaperSpecService = Depends(get_paper_spec_service),
) -> UploadDocumentResponse:
    """
    上传论文 / 报告 PDF·docx → 抽取 PaperSpec → 返回 paper_id + spec

    Raw 文档不持久化(04 § 8.6 (g) 字面 + R1 二审 P0-2 修订):
    成功 / 失败 / 异常路径均必须在 finally 内清理沙箱临时目录,
    不依赖 24h TTL(24h TTL 是异常兜底,不是正常路径的清理机制)。
    """
    sandbox_dir = await asyncio.to_thread(_create_sandbox_dir_sync)
    try:
        # 1. magic byte + 扩展名 + 大小校验(同步小读 < 8KB,UploadFile.read async,不必 to_thread)
        #    **R1 三审 P1-2 修订:read header 后必须 seek(0),否则保存的临时文件会丢前缀**
        header = await file.read(8192)
        _validate_magic_and_extension(header, file.filename)
        await file.seek(0)
        # 2. 保存到沙箱临时目录(同步重活,**asyncio.to_thread**,R1 一审 P1-5)
        saved_path = await asyncio.to_thread(_save_upload_sync, file, sandbox_dir)
        # 3. SHA-256 计算(同步重活,**asyncio.to_thread**)
        file_hash = await asyncio.to_thread(_compute_sha256_sync, saved_path)
        # 4. **安全 metadata 日志**(R1 三审 P1-1 修订:对齐 04 § 8.6 (g) 允许 hash / 文件大小 / 扩展名 / 拒绝原因,**不得**记 file.filename / 正文 / 图片)
        logger.info(
            "paper_document_upload_accepted: request_id=%s file_size=%d file_hash=%s extension=%s",
            request_id, file_size, file_hash, safe_extension,
        )
        # 5. 生成 paper_id(UUID4,D10)
        paper_id = str(uuid.uuid4())
        # 6. 调 service.extract(saved_path, paper_id) → PaperSpec
        spec = await service.extract(saved_path, paper_id)
        # 7. 返回 UploadDocumentResponse
        return UploadDocumentResponse(
            paper_id=paper_id,
            spec=PaperSpecModel.from_domain(spec),
        )
    finally:
        # R1 二审 P0-2 修订:raw 不持久化的实现契约 —— 不管成功/失败/异常都必须清理
        await asyncio.to_thread(_cleanup_sandbox_dir_sync, sandbox_dir)


# 注意:本卡不提供 GET /api/v1/papers/{paper_id}/spec(R1 一审 P0-3 修订;GET + 持久化 cache 留 TASK-503)
```

**`file_hash` 用途**(R1 三审 P1-1 修订):

- ✅ **安全 metadata 日志**:`logger.info(..., file_hash=%s, ...)` 用于审计 / 去重统计(对齐 04 § 8.6 (g) 允许字段)
- ✅ **ParsedDocument 校验**:parser 内已保存 `ParsedDocument.file_hash`(详 § 7.8)用于内部一致性
- ❌ **不进 response**(避免泄漏给前端)
- ❌ **不混作 `paper_id`**(D10 已定 UUID4)
- ❌ **不与 file.filename 一起记日志**(file.filename 永不落日志,对齐 04 § 8.6 (g))

**Magic byte 读取后 `seek(0)` 约束**(R1 三审 P1-2 修订,新增):

- header 读 8KB 后,**必须 `await file.seek(0)`** 再调 `_save_upload_sync`
- 否则保存的临时文件会丢前缀(`%PDF-` / `PK\x03\x04`),parser magic byte / docx zip 校验失败
- 新增测试:`test_upload_document_preserves_magic_prefix_after_sniffing`(用最小 docx/pdf fixture,断言保存后文件开头仍是 `%PDF-` 或 `PK\x03\x04`)

**Raw 文档不持久化契约**(R1 二审 P0-2 修订,实现层不变量):

- **成功路径**:return 前 finally 清理沙箱目录
- **失败路径**(parser / LLM / Pydantic 异常):异常抛出前 finally 清理
- **24h TTL 兜底**:仅用于 finally 失败的极端情况(进程崩溃 / cleanup 自身异常),正常路径不依赖
- **PaperSpec / cache 可留**(它们已经是结构化数据,无 raw 文档残留);**raw PDF / docx 不得在成功 / 失败 / 异常路径后残留**

**响应**(machine code 标准化,R1 P2-7 修订):

- 200:`UploadDocumentResponse { paper_id: str, spec: PaperSpecModel }`
- 400:`{"error": "document_parse_failed", "message": "<中文>"}` — `DocumentParseError`(magic byte 不符 / 损坏 / 加密 / 超大 / 解析超时 / 沙箱权限违反)
- 502:`{"error": "paper_spec_generation_failed", "message": "<中文>"}` — `PaperSpecGenerationError`(LLM JSON / Pydantic / 反幻觉拦截 / locator 白名单拦截)
- 503 / 504 / 429:`LLMAuthError` / `LLMQuotaError` / `LLMRateLimitError` / `LLMTimeoutError`(TASK-203 v0.3 已落 8 handler)

**响应 shape**:`{"error": "<machine_code>", "message": "<中文>"}`(对齐 02 § 9 + TASK-203 D11)。

**异步桥接 grep 要求**(R6.1,R1 二审 P0-2 + P1-3 修订):

- **`service` ≥ 3 处** `asyncio.to_thread`:router.route + sandbox parser + LLM(R1 二审 P1-3)
- **`route` ≥ 3 处** `asyncio.to_thread`:文件保存 `_save_upload_sync` + SHA-256 `_compute_sha256_sync` + cleanup `_cleanup_sandbox_dir_sync`(R1 一审 P1-5 + R1 二审 P0-2)

---

## 验收标准

> **PM 验收边界注**(K_36 沿用 TASK-500 v0.2.1 模式):本节验收勾选 = Codex PR 提交 + R6.1 实测达标的标准;PR 通过 PM 合并前 03 索引 TASK-501 标 🔍(等待验收),合并后由 PM 改 ✅。Codex 不许直接在 03 索引写 ✅。

### 验收清单

- [ ] **域层落地**:`core/domain/paper_*.py` 5 文件(11 dataclass + 1 enum)+ 各对应单测全过(§ 7.1 - 7.4)
- [ ] **Pydantic wrapper 落地**:`features/paper/paper_schemas.py` **5 顶层 wrapper + 6 nested submodel + EvidenceSource enum 直接复用 core.domain**(R1 二审 P2-2)+ `.to_domain()` / `.from_domain()` + 双源不变量 `model_validator`(§ 7.5,R1 一审 P0-2)
- [ ] **freeze test 落地**:`tests/features/paper/test_paper_schemas_freeze.py` **反模式 1/2/3/4 全覆盖** + 6 字段冻结测试 + Pydantic-dataclass 一致性(§ 7.6,R1 P2-1)
- [ ] **样本包 roundtrip 落地**:`tests/features/paper/test_paper_schemas_sample_roundtrip.py` 对 **4 个 sample JSON × Pydantic 全过**(`expected_missing_prompts.json` 按 dict-with-`missing_prompts`-list 校验,其他单对象)+ 双源不变量逐项校验全过(§ 7.7,R1 二审 P0-1 架构师反向采纳)
- [ ] **JSON schema 导出**:5 个 `schemas/paper_*.schema.json` 落仓 + `python -m scripts.export_paper_schemas` 可重跑
- [ ] **Parser 适配层 + 沙箱**:`adapters/parser/pdf_parser.py` + `docx_parser.py` + `_sandbox.py`(含**子进程权限隔离 + 错误脱敏**)+ 各单测(含 3 项 R1 P0-4 新增测试)+ 6 类恶意 fixtures 全拦
- [ ] **PaperSpecService 落地**:`features/paper/paper_spec_service.py` 五步校验(R1 P0-1 修订:`response.text` 非 `.content`)+ cache(`asyncio.Lock`) + asyncio.to_thread + locator 白名单(R1 P1-3)+ figure 反幻觉两段(R1 P1-2)+ 各单测全过
- [ ] **Prompt 落地**:`core/prompts/paper_spec_extract.yaml` v0.1 含 9 项 system invariant(§ 7.11,R1 P1-3 新增 locator 白名单约束)
- [ ] **API 路由落地**:`POST /api/v1/upload-document` + `UploadDocumentResponse` Pydantic model 定义 + 端到端测试全过(**不**含 GET,R1 P0-3)+ 错误码 machine code 标准化(R1 P2-7)
- [ ] **依赖注入装配**:`api/main.py` + `api/dependencies.py` + `api/middleware/error_handler.py` 增量改动通过;`DocumentParserRouter` 在 `api/dependencies.py` 装配,parser 实例注入(R1 P1-11)
- [ ] **新依赖落 requirements.txt**:`pypdf==<version>` + `python-docx==<version>` + PM PR review 通过
- [ ] **真启动验收**(R1 二审 P1-7 修订):uvicorn 单 worker + 上传**剥离版 docx**(由 `material_to_plan/case_01_motor_short_circuit/input/source_doc_stripped.md` 生成 docx,或 PM 明确提供"剥离版 docx")→ 返回 PaperSpec JSON,人工对照 `golden/expected_paper_spec.json` 字段集等价(允许 LLM 输出值偏差,但字段集 + 类型 + 双源标注 + locator 白名单正确;**A2 工程决定字段禁出项仅适用于剥离版**;若 PM 提供原始 PoC docx 含 `5MW / 平衡 / ode15s` 等,只验 schema / 类型 / 双源 / locator 层)
- [ ] **`docs/03_TASK_INDEX.md` 同步**:TASK-501 行 🔲→🔍(等待验收);**PM 合并后** PM 改 TASK-501 ✅
- [ ] **R6.1 完工实测清单**(R1 二审 P2-1 改名;沿用 TASK-500 v0.2.1 模式 + R1 一审 P1-5 / P1-7 + R1 二审 P0-2 / P1-3 / P1-5 / P1-6 扩展):
  - **范围实测**:`git diff --name-only origin/main` 改动文件清单在 § 输出 清单内(超范围 = R6.1 Fail)
  - **决策 11 grep**(§ 范围 #6,R1 二审 P0-2 + P1-3 + P1-6):`logger.exception` 在 paper / parser / api/routes/paper_upload 路径 0 命中;`asyncio.to_thread` 在 `paper_spec_service.py` **≥ 3 处**(router.route + sandbox parser + LLM)+ `api/routes/paper_upload.py` **≥ 3 处**(文件保存 + SHA-256 + cleanup)
  - **决策 21 boundary grep**(§ 范围 #7,R1 二审 P1-5 扩展 + P1-6 加 exclude):2 处 regex grep 全空(覆盖 `from features.overview/explanation` + `import features.overview/explanation` + `features.overview/explanation.` 直接引用 + `EvidencePack / ExplanationPack / _evidence_builder / overview_schemas / ProjectOverview` 名称引用)
  - **本卡合并守门红线 6 项未动**(§ 范围 #8,逐个跑 6 个文件):`git diff --name-only origin/main -- <redline_path>` 应为空;命令输出贴 PR 完工 report
  - **样本包未改**(§ 范围 #9):`git diff --name-only origin/main -- eval/cases/paper_to_model/` 应空
  - **freeze + sample roundtrip 实测**(§ 范围 #10):pytest 输出贴 PR
  - **隐私 grep**(§ 范围 #11,R1 一审 P1-7 + R1 二审 P1-6 加 exclude):`grep -rnE "logger\.(debug|info|warning|error).*file\.filename|logger\.(debug|info|warning|error).*raw_text|logger\.(debug|info|warning|error).*response\.(text|content)|str\(exc\)|repr\(exc\)" features/paper/ adapters/parser/ api/routes/paper_upload.py --exclude-dir=".venv" --exclude-dir=".git"` 应空,或逐项说明是安全元数据
  - **临时文件清理实测**(§ 范围 #12,R1 二审 P0-2 新增,R1 三审 P1-5 命令规范化):
    ```bash
    find "$PAPER_TMP_ROOT" -maxdepth 2 \
      \( -path "$PAPER_TMP_ROOT/.venv" -o -path "$PAPER_TMP_ROOT/.git" \) -prune -o \
      -type f -print
    ```
    API 测试结束后输出应为空,或只剩 TTL 元数据;**不得剩 raw PDF/docx**;若有残留 = R6.1 Fail
  - **对外口径继承 TASK-500 验收**:`git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器" features/paper/ adapters/parser/ api/routes/paper_upload.py core/prompts/paper_spec_extract.yaml` 应空

### 评测验收线(对齐样本包 `scoring_template.md`)

**TASK-501 完工 ≠ 评测完工**(评测整体门槛 5 留 TASK-502 跑全两 case)。本卡评测验收线 = **结构层 + 单 case PaperSpec 层**:

| 评测维度 | TASK-501 验收要求 |
|---|---|
| 结构层(freeze test + sample roundtrip)| **必过**:4 个 sample JSON × Pydantic 全过 + 双源不变量逐项校验全过 |
| Layer 2 A1 抽取字段完整(`material_to_plan/case_01`)| **目标**:人工对照 actual_paper_spec vs golden,12 项电机参数 + EQ-01 + 摘要 + S2/S3/S4/S5 evidence 命中率 ≥ 70%(Partial / Pass)|
| Layer 2 A2 无幻觉(同上)| **必过**:不输出 `figure_locations` 具体条目(剥离版无图)+ 不输出工程决定字段(5MW / 平衡 / 0.2s / ode15s / 1s)+ 不编造资料外参数 + locator ID 全在 parser 白名单内(R1 P1-3)|
| Layer 2 E1 双源不变量(同上)| **必过**(一票否决):所有 evidence 满足 verification_method § 3 两套不变量;评测人工 spot-check 通过 |
| Layer 1 O1 Plan 可执行性 | **N/A**(本卡不产 plan,留 TASK-502)|
| Layer 1 O2 用户补充更新 | **N/A**(本卡不做用户补充,留 TASK-502)|

**单 case 验收**(本卡口径):结构层全过 + A2 + E1 必过 + A1 至少 Partial = 本卡 PaperSpec 抽取层验收通过。

**整体门槛 5**(`scoring_template.md` § 6.1):**留 TASK-502** 跑完两 case 后判断。

---

## 红线(本卡)

- ❌ 不动本卡合并守门红线 6 项(§ 输入 红线表)
- ❌ 不动 `eval/cases/paper_to_model/` 12 文件任何字面
- ❌ `features/paper/` 不 import `features/overview/` / `features/explanation/` 私有结构
- ❌ `core/domain/paper_*.py` 不 import 任何 `features/` 路径
- ❌ async 内同步重活不通过 `asyncio.to_thread` 桥接(决策 11)— 包括文件保存 + SHA-256 计算 + parser 调用 + LLM 调用
- ❌ 业务异常分支用 `logger.exception`(决策 11)
- ❌ 日志记录原始文件名 / 文档正文 / 图片内容 / `str(exc)` / `repr(exc)` / `response.text`(04 § 8.6 (g) + R1 P1-7)
- ❌ 不引入除 pypdf / python-docx 外的新 pip 依赖
- ❌ 对外口径不用"自动生成 .slx" / "一键生成" / "完整仿真模型" / "成品生成"等表述
- ⚠️ 若 Codex 实施期发现 task 描述与宪法 v3.1 / 02 v3.0 delta / 06 § 12 / 04 § 8.6 既有内容冲突 → 停手报 PM(沿用宪法 § 15)

---

## 风险清单

### 风险 1:freeze test 与 06 § 12 字段表跨段不同步(K_30 高发区)

**影响**:freeze test 通过但 06 字段表已变 / 反之 → schema 漂移。

**规避**:`test_paper_*_fields_frozen` 的字段 list 注释链接 06 § 12 节号 + Codex 实施期 grep `^| ` 06 § 12 字段表字面;05 § 9.2 字段表改动需 D5 修订同步。

### 风险 2:Pydantic `model_validator(mode='after')` 不拦双源不变量某 corner case

**影响**:E1 一票否决守不住,污染下游(TASK-502)。

**规避**:6 case 全跑:
- `document_extracted` + 三 locator 全 None / `document_extracted` + excerpt 空 / `document_extracted` + missing_param_prompt_id 非 None
- `user_supplied` + 三 locator 任一非 None / `user_supplied` + excerpt 非 None / `user_supplied` + missing_param_prompt_id None

### 风险 3:PDF / docx 解析依赖跨平台兼容性(Windows vs Linux)

**影响**:`RLIMIT_AS` Linux only;Windows 上沙箱无内存上限。

**规避**(R1 P1-10):**生产 / CI 安全验收以 Linux RLIMIT_AS 为硬门槛**;Windows / macOS 软监控仅限本地开发;若 PM 要求 Windows 生产支持,v0.1 fail-closed(留 PM 决策点)。

### 风险 4:`pypdf` 对加密 / 损坏 PDF 解析行为不一致

**影响**:有些恶意 PDF 不抛异常但返回空字符串 → service 误判"资料无内容"。

**规避**:`pdf_parser.parse(...)` 后置检查 `parsed.raw_text` 长度 ≥ 100 字符(配置默认 100,可调);<100 字符且无明显异常 → `DocumentParseError("文档内容过短或解析失败")`。

### 风险 5:LLM 抽取 `parameter_table` 时把 docx 任务陈述段的"PN=200MW"参数漏抽

**影响**:A1 字段完整率 < 70% → 案例不通过。

**规避**:prompt 内明示"逐项扫描所有显式给出参数"+ 系统提示 12 项电机参数典型字段名(xd / xq / ...)作为 hint;若 LLM 仍漏抽 ≥ 30%,留 TASK-502 R 轮 prompt iteration。

### 风险 6:LLM 幻觉 `figure_locations` 条目(剥离版无图,LLM 编造)

**影响**:A2 无幻觉 Fail。

**规避**:Step 3 两段校验(§ 7.10):(a) parser 无图 → spec 必空;(b) parser 有图 → spec figure_id 必属于 parser placeholder 集(R1 P1-2)。Prompt system 内强调"figure_placeholders 为空时严禁输出 figure_locations 条目"。

### 风险 7:Pydantic wrapper 与 domain dataclass 字段顺序漂移(决策 18 round-trip 风险)

**影响**:`.from_domain(.to_domain(x)) ≠ x` → API 边界不可逆。

**规避**:`test_pydantic_dataclass_field_consistency` 对 5 顶层 wrapper + 6 nested submodel 跑 round-trip 守门;字段顺序差异 → test Fail。

### 风险 8:LLM 输出 `domain = "general"` 绕过 6 类约束

**影响**:决策 22 § 1.5 + 06 § 12.1 资料入口 6 类硬约束失守。

**规避**:Pydantic Step 2 `Literal[6]` 已硬拦;prompt system 明示"严禁输出 general"。Codex 实施期写测试 case:模拟 LLM 输出 `"general"` → ValidationError + ERROR_MAP 翻译 502。

### 风险 9:LLM 编造 paper_section_id / equation_id 绕过双源不变量(R1 P1-3 新增)

**影响**:LLM 输出 `S6 / S7 / EQ-99` 满足"locator ≥ 1 + excerpt 非空"形式约束,但证据不可追溯;E1 形式通过实质失守。

**规避**:Step 4 locator 白名单校验(`PaperEvidenceEntry.paper_section_id` ∈ `parsed.locator_index.section_ids`);prompt system 注入 `{section_ids}` / `{equation_ids}` / `{figure_ids}` 白名单,LLM 严格按集合输出。

### 风险 10:Parser sandbox 子进程未正确传递 ParsedDocument(序列化失败)

**影响**:子进程跑完但主进程拿不到结果。

**规避**:`ParsedDocument` + `FigurePlaceholder` + `ParsedLocatorIndex` 全 `@dataclass(frozen=True)` 纯数据,全 picklable;`multiprocessing.Queue` 传递;Codex 实施期单测覆盖 large file(50MB PDF)子进程返回。

### 风险 11:cache 在本卡 InMemory 模式下命中率低(R1 P1-4 + 自审)

**影响**:同一 paper_id 由 UUID4 新生成,二次上传 cache 命中率为 0;cache 在本卡范围内是"为 TASK-502 / 503 接力面而预留",不是性能优化。

**规避**:D12 显式说明 cache 语义("ready-only,只 put 不 expire,不做并发去重;持久化 + GET 路由留 TASK-503");不引入决策 19 四态 cache record(本卡 POST 同步抽取无 lazy generation 需求)。

### 风险 12:并发请求竞态(R1 P1-4 + 自审补充)

**影响**:同一进程多并发 `POST /api/v1/upload-document` 请求同时跑,可能压垮 LLM 配额或文件系统。

**规避**:本卡 v0.1 不做并发去重(paper_id 由 UUID4 生成,key 永不冲突);`InMemoryPaperSpecCache` 用 `asyncio.Lock` 保护 dict 操作;LLM rate limit 由 `LLMRateLimitError` → 429 兜底;具体并发上限 Codex 实施期评估(必要时加 `Semaphore`)。

### 风险 13(隐私):prompt 含资料原文落 DeepSeek 服务器

**影响**:学生上传的论文 / 报告内容落 LLM 服务商。

**规避**:01 § 9 用户协议明示;**PM 在 paper-to-model v0.1 上线前确认 DeepSeek opt-out 训练**(架构师追踪事项)— 沿用 TASK-203 风险 11 处理路径。

### 风险 14(隐私):日志可能落原始文件名 / 文档正文 / response.text(R1 P1-7 修订)

**影响**:违反 04 § 8.6 (g)。

**规避**:R6.1 隐私 grep 强校;`logger.error(..., type(exc).__name__)` 模式 + `from None` 抹 chain;`response.text` 严禁落日志;原始 `file.filename` 在 magic byte 后直接舍弃,只用沙箱临时路径。

### 风险 15(K_28a 自防):本卡引用 06 / 04 / 02 / 决策 22 字面较多

**影响**:K_28a 凭印象写错节号 / 字段名 → 跨段不同步。

**规避**:本卡 v0.2 起稿期已 grep 06 / 04 / 02 / 决策 22 / 决策 21 / 决策 11 / 决策 18 / 12 sample files 字面 + R1 已抓 P0-1 / P0-2 / P0-5 / P2-5 等 K_28a / K_30 实例并全部采纳修订;Codex Stage 0 必须再 grep 兜底;任一不一致 → 停手报 PM。

### 风险 16:TASK-502 接力时发现 PaperSpec 契约不够用(R1 自审补强)

**影响**:本卡 PaperSpec 字段定型后,TASK-502 PaperPlanService 实施期发现需要 PaperSpec 加字段(如"工程上下文 hint" / "domain confidence score"),牵动本卡 freeze + sample + JSON schema 全部回改。

**规避**:本卡 schema 标"v0.1 草稿,字段未冻结";改动走 06 § 7 D5 流程;TASK-502 实施期如发现需要,优先通过 prompt 而非 schema 扩展;真要改 schema 则走 D5 同步同源 5 处。

---

## 决策日志(D1-D12)

每个 D 含 **理由** + **替代方案 / 反对意见** + **为何不选**。

### D1 — 审批级别:架构升级类(R1 + R6 + PM 三道)

**理由**:首个 paper feature 实施 task + 新依赖 + 跨多文件 + 用户面端点;沿用宪法 § 5 二审节点 #1 + 决策 12 v0.4。

**替代方案**:Codex 一审通过即合并(类比 TASK-310 chore PR)。**为何不选**:本卡是 paper-to-model 主线首个真实现 task,决策密度 + 下游扩散面远超 chore;TASK-203 v0.3 已实证"首个 LLM 端点必走二审"。

### D2 — TASK-501 拆分:本卡仅"资料入口骨架 + PaperSpec 抽取";PaperPlanService 留 TASK-502;TuningSuggestion + UX + GET + 持久化 cache 留 TASK-503

**理由**(详上下文段):

1. 单 PR 体量 5000-6000 LOC + 30+ 文件不可控(TASK-203 单 PR ~1880 LOC R1 抓 12 项;本卡若不拆估 ≥ 30 项)
2. schema 与 service 耦合 → 一锅炖期间 schema 反复改 + service 跟改 = K_30 跨段同步漂移风险(决策 22 § 9 警示;R1 抓 14+ K_30 实例已证明这是高发区)
3. 按 02 § 资料入口数据流自然边界切三任,各 1500-2000 LOC + 各有清晰评测验收线

**替代方案 A**:单 TASK-501 一锅炖。

- **A 的实质优势**(R1 P1-1):更早获得端到端反馈,更早暴露 PaperSpec 是否足够支撑 plan 生成,减少 serialize-only schema 的临时成本,也能更早跑完整两 case
- **为何不选**:本卡用 sample roundtrip + material_to_plan 单 case PaperSpec 人工评测抵消端到端反馈缺失;R 轮风险 + LOC 估超 04 § 4.2 / 决策 12 v0.4 隐性单 task 上限

**替代方案 B**:横向切按层(domain / parser / service / api 各一任)。**为何不选**:不沿 02 § 资料入口数据流,跨任依赖反复,且最后一任才能跑端到端;PM challenge 时不易理解切分理由。

**替代方案 C**:垂直切按 case(case_01 一任 / case_02 一任)。**为何不选**:每任都需要全 9 组件浅触一遍,不减少 review 表面。

**Challenge 待 PM 拍板**:C1(详 § 状态)。

### D3 — domain 文件按 06 § 12 节结构拆 5 文件

**理由**:每文件 ≤ 150 行(对齐 04 § 4 文件 ≤ 300 行),节点边界与契约对齐,易于 TASK-502 / 503 复用消费。

**替代方案 A**:单 `paper.py` 集中。**为何不选**:可能 ≥ 300 行超限。

**替代方案 B**:11 文件按 entity 拆。**为何不选**:过度碎片化,跨文件互引麻烦。

### D4 — domain 层纯 dataclass + Literal + Enum,无业务逻辑

**理由**:对齐决策 18(core dataclass = 内部表示)+ 决策 21 boundary(paper feature 不 import overview / explanation 私有结构 = core/ 层是单向 contract);双源不变量等校验逻辑全在 Pydantic wrapper 层(serialize 边界)。

**替代方案 A**:domain 层加 `__post_init__` 校验。**为何不选**:校验逻辑在两处(domain + wrapper)→ 跨层漂移风险;决策 18 已明示 wrapper 是序列化边界。

**替代方案 B**:domain 层不冻结(`@dataclass` 默认可变)。**为何不选**:domain 是 contract,应不可变;TASK-203 / 310 已沿用 `frozen=True`。

### D5 — 5 顶层 Pydantic wrapper + 6 nested submodel + EvidenceSource enum 直接复用 + `.to_domain()` / `.from_domain()` 桥接(R1 一审 P0-2 + R1 二审 P2-2 修订)

**理由**:API 边界需要 Pydantic 自动 OpenAPI / response_model;内部 service 用 core dataclass(类型安全 + 不可变);C 类 bridge 模式 TASK-310 PR #1 已实证可行。06 § 12 顶层契约 schema 5 个(PaperEvidenceEntry / PaperSpec / ModelGenerationPlan / TuningSuggestion / MissingParameterPrompt),`EvidenceSource` 是 enum 不是 wrapper,子项 6 个走 nested submodel(R1 P0-2)。

**替代方案 A**:API 边界也用 dataclass(`fastapi.encoders.jsonable_encoder`)。**为何不选**:OpenAPI 自动生成丢失 + response_model 校验丢失。

**替代方案 B**:全 Pydantic,不下沉 core dataclass。**为何不选**:`features/paper/` 与 `core/domain/` 边界丢失;决策 18 已锁 core 是契约层。

### D6 — 双源不变量校验位置:Pydantic `model_validator(mode='after')`,domain 层不带逻辑

**理由**:wrapper 是序列化边界(决策 18),双源不变量是 schema 层硬约束(06 § 12.3),自然落在 wrapper;domain 纯 dataclass 不引入校验依赖(对齐 D4)。

**替代方案 A**:校验逻辑落 service 层(`PaperSpecService._parse_and_validate`)。**为何不选**:service 层校验 = 运行时校验,但 schema 是契约层;Pydantic wrapper 不拦 = schema 失守,反模式 2 / 3 / 4 可绕过。

**替代方案 B**:双层校验(wrapper + service)。**为何不选**:本卡 § 7.10 已设 service Step 5 冗余防御(仅 `document_extracted`,本卡范围内);两层同时拦不冲突,Pydantic 是第一道,service 是兜底(对齐 TASK-203 模式)。

### D7 — PDF / docx 解析依赖选型:`pypdf` + `python-docx`(纯 Python,无系统依赖)— R1 P1-9 修订

**理由**:

- `pypdf`:纯 Python 实现,无 native binding;主流维护活跃,社区文档全;v0.1 范围 text + 图占位即可,不需要 pdfplumber 的表抽能力
- `python-docx`:**成熟社区库**(R1 P1-9 修订:不再称"微软官方"),适合 v0.1 paragraph / inline image relationship / table placeholder 的轻量解析
- **不接 OCR**(决策 22 § 4.8 + 04 § 8.6 (f) 字面留 v0.2)
- **不接 pdfplumber / pdfminer.six / camelot / tabula / unstructured**(v0.1 无表抽取需求 / 引入 Java / Tesseract / OpenCV 系统依赖会破坏纯 Python 部署)

**替代方案 A**:`pdfplumber`(表抽强)。**为何不选**:v0.1 无表抽需求;依赖更重(pdfminer.six + Pillow)。

**替代方案 B**:`unstructured`(多格式统一)。**为何不选**:依赖巨大(transformers / detectron2 等)+ License 风险;违反 01 § 7 "不引入的依赖"原则;R1 P1-9 明确不建议。

**Challenge 待 PM 拍板**:C2(详 § 状态);具体版本号由 Codex 实施期查 PyPI 最新稳定 + PM PR review 拍板。

### D8 — Parser sandbox 用 multiprocessing + Linux 硬限制为生产门槛(R1 P0-4 + P1-10 修订)

**理由**:04 § 8.6 (c) 字面"子进程隔离 + 30s + 512MB";`multiprocessing.Process` + `Queue` 是 stdlib 标准做法;`resource.setrlimit(RLIMIT_AS / RLIMIT_CPU)` Linux only,**Windows / macOS 不引 `psutil`**(R1 二审 P0-3 修订:`psutil` 非 stdlib 与"除 pypdf / python-docx 外不引依赖"红线冲突),本地开发仅 multiprocessing + timeout 弱隔离(无 mem 强制上限,OS OOM-killer 兜底) — **生产 / CI 安全验收以 Linux 为硬门槛**,Windows / macOS 仅本地 unit test。

**替代方案 A**:`subprocess` + 解析器命令行入口。**为何不选**:pypdf / python-docx 无 CLI,需要写 wrapper 脚本;多一层 marshalling 开销。

**替代方案 B**:不沙箱,只设 timeout(`asyncio.wait_for`)。**为何不选**:04 § 8.6 (c) 字面违反;parser 崩溃可能拖垮主进程 event loop。

**替代方案 C**:接受 Windows 生产软监控。**为何不选**:R1 P1-10 明示"软监控不视为满足生产上传安全";不能让生产安全语义降级。Windows 生产支持 = PM 决策点(默认 v0.1 不支持)。

### D9 — 上传路由 path:`POST /api/v1/upload-document`(对齐 04 § 8.6 (a) 字面)

**理由**:04 § 8.6 (a) 字面;与 MCS `/upload` 不交集;前端可清晰区分"工程入口 / 资料入口"二选一。

**替代方案 A**:复用 `/upload`,内部按 MIME 分发。**为何不选**:04 § 8.6 (a) 已字面拍板"新增独立路由",违反 = 反向改写工程规范。

**替代方案 B**:`/api/v1/papers/upload`。**为何不选**:04 § 8.6 (a) 字面 `POST /api/v1/upload-document`,凭印象改 = K_28a。

### D10 — paper_id 生成:UUID4(R1 P1-8 修订:补 ULID / file_hash 替代方案)

**理由**:与 project_id 不冲突;无外部依赖;同一文件二次上传 = 新 paper_id,user 视角是"两次独立上传"(对齐 RESTful 资源新建语义)。

**替代方案 A**:递增 ID。**为何不选**:需要数据库支持,本卡 InMemory cache 无 DB,递增不可重启幂等。

**替代方案 B**:文件 SHA-256 hash。**为何不选**:同一文件两次上传会冲突;`paper_id` 不应等于"文件指纹"(后者归 `ParsedDocument.file_hash`)。

**替代方案 C**:ULID。**为何不选**(R1 P1-8 新增):需要新增依赖或自实现;时间有序性对本卡 InMemory cache 无价值,还可能暴露上传时间排序信息。

**替代方案 D**:UUID4 + file_hash 去重索引。**为何不选**(R1 P1-8 新增):本卡无持久化 DB,不做二次上传去重;`file_hash` 已在 `ParsedDocument` 中记录,不能混作 `paper_id`。

### D11 — TASK-501 verification line = 结构层 + 单 case PaperSpec 层,**整体门槛 5 留 TASK-502**

**理由**(详 § 验收标准):

- TASK-501 不产 plan / 不做用户补充 → Layer 1 O1 / O2 不可评(N/A)
- 评测整体门槛 5(`scoring_template.md` § 6.1)要求两 case 各 ✅ / 🟡 + 0 E1 / E2 一票否决 → 必须 PaperPlanService + UserSupplyMerger 落地后才能跑完整两 case
- 本卡评测验收线 = 结构层 + 单 case PaperSpec 层(Layer 2 A1 / A2 / E1)

**替代方案 A**:本卡也跑两 case 完整评测。**为何不选**:本卡无 plan / 无用户补充流程,跑不通整体门槛 5。

**替代方案 B**:本卡不做任何 case 评测。**为何不选**:PaperSpec 抽取层无评测 = R6 守不住 LLM 抽取质量;sample roundtrip 是结构层(过 schema 即过),但 Layer 2 A1 / A2 / E1 是质量层,本卡必须覆盖。

### D12 — PaperPlanService 不在 TASK-501 落地 + cache 语义 + GET 删(R1 P0-3 + P1-4 + P1-14 修订,新增)

**理由 1 — PaperPlanService 不落地**:

- TASK-501 验收线是 PaperSpec(单 LLM 抽取)
- Plan 生成需要 9-component prompt 子角色、MissingDetector、UserSupplyMerger,跨多文件 + 多 LLM call,留 TASK-502
- 范围已经清楚(§ 不做),但"首个真实现 task"会诱导 Codex 顺手写 plan 生成;显式 D12 减少 R6 超范围风险

**替代方案 A**:在 501 写 stub PaperPlanService。**为何不选**:stub 会诱导 API / 测试消费未验证 contract。

**替代方案 B**:501 写最小 plan prompt(单 prompt 同时输出 PaperSpec + ModelGenerationPlan)。**为何不选**:越过 D2 切分,导致 review 面积回到一锅炖;两层契约耦合在一个 prompt 会让 R1 抓 30+ 项。

**理由 2 — cache 语义 ready-only + GET 删**:

- TASK-501 采用 ready-only cache:POST 同步完成后才 put;不缓存 `failed_retryable` / `failed_permanent`(不引入决策 19 四态 cache record)
- 本卡 `GET /api/v1/papers/{paper_id}/spec` **删除**(R1 P0-3):InMemory cache 模式下 GET 命中率为 0;GET + 持久化 cache 留 TASK-503 一并实现
- cache 在本卡范围内保留,主要作为 TASK-502 接力面(PaperPlanService 同进程消费 PaperSpec 时可直接读 cache,无需重抽)
- 同一 paper_id 并发请求:UUID4 新生成不冲突;不做并发去重;GET miss 不触发生成

**替代方案 A**:删 cache + 删 GET。**为何不选**:cache 是 TASK-502 接力面,删了 TASK-502 还得重做(违反"复用"原则);保留 cache + 删 GET 是平衡。

**替代方案 B**:保 GET + 引入决策 19 四态。**为何不选**:本卡 POST 同步抽取无 lazy generation 需求;四态 cache 是 over-engineering;留 TASK-503 持久化时再评估。

---

## Checklist(精简)

**实施前**:

- [ ] 已读 06 § 12 / 04 § 8.6 / 02 § 资料入口数据流 / 决策 22 § 5.2 / 决策 21 / 决策 11 / 决策 18 / TASK-203 § 7 服务模式 / TASK-500 v0.2.1 § 接口契约要点
- [ ] 实地核查 12 个样本包文件 + JSON 合法 + 双源不变量过(Stage 0 #3)
- [ ] 实地核查 main HEAD = TASK-500 main merge 之后(Stage 0 #1)
- [ ] 实地核查 `LLMResponse.text` 字段名(02 § 4.3,R1 P0-1)
- [ ] 实地核查本卡合并守门红线 6 项的三源追溯(决策 22 § 5.2 / 决策 21 / TASK-500 v0.2.1)
- [ ] 理解决策 11 双不变量(asyncio.to_thread + 禁 logger.exception)+ R1 P1-5 扩展(文件保存 + SHA-256 也桥接)
- [ ] 理解决策 21 boundary(paper feature 不 import overview / explanation)
- [ ] 理解 D2 拆分(TASK-501 = 骨架 + Spec;TASK-502 = Plan;TASK-503 = Tuning + UX + GET + 持久化 cache)
- [ ] 理解 D5 桥接(5 顶层 + 6 nested + EvidenceSource enum,R1 P0-2)
- [ ] 理解校验五步(§ 7.10 Step 1-5,R1 P0-1 / P1-2 / P1-3)
- [ ] 理解 locator 白名单注入(§ 7.8 ParsedLocatorIndex + § 7.11 prompt,R1 P1-3)

**完工前**:

- [ ] § 验收清单全过
- [ ] § R6.1 完工实测命令全过 + 输出贴 PR(含 R1 P1-7 隐私 grep 扩展)
- [ ] commit subject 单行无 body(反例 17)
- [ ] 完工三件套(决策 08)
- [ ] 03 索引字节级修订
- [ ] PR(Codex 给 PM 标题 + 正文,PM 走 GitHub 网页创建)

---

## 后续 task 接力点

### 直接阻塞(等本卡合并)

- **TASK-502:PaperPlanService 主线**
  - 范围:PaperSpec → ModelGenerationPlan + MissingDetector + UserSupplyMerger
  - 复用本卡:5 domain dataclass + 5 顶层 Pydantic wrapper + 5 JSON schema + DocumentParser / DocumentParserRouter ABC + PaperSpecService 调用结果 + `InMemoryPaperSpecCache`(同进程内复用 PaperSpec)
  - 新增 prompt yaml:`paper_plan_generate.yaml`(9-component prompt 子角色:LibrarySelector / BlockRecommender / ParameterMapper / SubsystemPlanner / MScriptDrafter / MissingDetector / UserSupplyMerger / EvidenceTagger;Extractor 本卡已含)
  - **接力不变量**(R1 P1-12):TASK-502 不依赖 501 输出 `PaperGraph`,只消费 `PaperSpec`;但 **501 必须保证 `PaperSpec.evidence` locator 可追溯到 `ParsedDocument.locator_index`**(R1 P1-3 强制),否则 502 不得把该 evidence 用作 plan 证据
  - 验收:**整体门槛 5**(两 case 各 ✅ / 🟡 + 0 E1 / E2 一票否决,`scoring_template.md` § 6.1)
  - 估时:2-3 周

- **TASK-503:TuningSuggestion + UX 闭环 + GET 路由 + 持久化 cache**
  - 范围:TuningSuggestion service(06 § 12.6)+ 前端 MissingParameterPrompt UI + 用户补充表单 + `GET /api/v1/papers/{paper_id}/spec` 路由 + `SqlitePaperSpecCache(PaperSpecCache)` 持久化(对齐 TASK-204 模式)
  - 复用本卡:`TuningSuggestionModel` Pydantic wrapper(本卡已 serialize-only 落地)+ `PaperSpecCache` ABC(本卡定义,TASK-503 实现 SQLite 版)
  - 验收:端到端用户旅程跑通 + 真实场景调通率 ≥ 50%(决策 23 § 2.1 v0.2 锚点拉前)
  - 估时:2-3 周

### 可复用 / 未来解锁

- **`SqlitePaperSpecCache(PaperSpecCache)` 替换 InMemory**:对齐 TASK-204 模式,留 TASK-503
- **PaperGraph schema 字段**(02 § 4.2 v3.0 delta 占位):本卡不落地,留 schema 演进 task
- **OCR**(决策 22 § 4.8 + 04 § 8.6 (f)):v0.2 评估

### Phase 2 候选(挂账)

- LLM streaming PaperSpec 抽取(超长 PDF)
- Parser 缓存(同一文件二次上传)
- Multi-document fusion(决策 23 § 2.1 v0.2)
- 控制 / 信号处理类样本 ≥ 1 case 各(roadmap v2.1 § 4.2)
- Windows 生产支持(D8 决策点;v0.1 默认不支持,需 PM 拍板)
- 扩展恶意 fixtures(xfa_form.pdf / encrypted.docx 等;Codex 实施期可决定加,非阻塞)

---

## 工艺(决策 12 v0.4)

- **本任审批级别**:**架构升级类**(首个 paper feature 实施 + 新依赖 + 跨多文件)— R1 + R6 + PM 三道
- **R1**:GPT 审决策质量(挑契约一致性 / 红线落实 / 拆分合理性 / 跨段同步漏)— **v0.1 R1 已完成,5 P0 + 14 P1 + 7 P2 全采纳;0 challenge;v0.2 为采纳后修订版**
- **R6**:Codex 完工后实测层(grep 决策 11 双不变量 + 决策 21 boundary + 本卡合并守门红线 6 项 + 样本包未改 + 对外口径 + 隐私 grep)
- **PM 兜底**:PM 直接 review task 文档 + R1 反馈 + R6 报告
- **K_28a 自防**(决策 22 § 9 警示 + R1 已抓 P0-1 / P0-5 / P1-9 等实例):
  - 关键契约引用优先标注节号;Stage 0 要求 Codex 对 main HEAD 实地核查对应行号(R1 P2-2 修订)
  - 字段表不重抄,引导查 06 § 12(避免跨段同步漂移)
  - Codex Stage 0 必查:对照本卡 § 7 接口契约 vs main HEAD 06 § 12 / 04 § 8.6 字面,任一不一致停手报 PM
- **K_30 自防**:本卡 v0.x → v0.x.x 修订必做全文跨段一致性扫描 — v0.2 修订时已 grep 数字字面(5 顶层 wrapper / 6 nested submodel / 5 阶段 / 5 文件 / 6 类 domain / 7 子项 04 § 8.6 / 9 system invariant prompt / 4 sample JSON / 12 sample files / 5 D / 12 D / 16 risk / 11 dataclass + 1 enum)全文一致
- **K_36 自防**:Codex 不直接在 03 索引写 ✅ / 解封;PM 合并后由 PM 改 ✅(对齐 TASK-500 v0.2.1 PM 验收边界)

### 反例账目(v0.1 起稿期 + R1 一审 + R1 二审 + R1 三审)

按决策 22 § 9 趋势记账:

**R1 一审阶段(v0.1 → v0.2)**:

- **K_28a +2**(R1 一审):
  - P0-1:`response.content` vs `LLMResponse.text` 凭印象(架构师未 grep 02 § 4.3)
  - P1-9:`python-docx` 称"微软官方"措辞过度
  - v0.1 起稿期自抓 +1:`ModelGenerationPlan 9 字段` → 8 字段(自审 freeze test 时抓到)
- **K_30 +17**(R1 一审 P0-2 / P0-3 / P0-5 / P1-2 / P1-3 / P1-4 / P1-5 / P1-6 / P1-7 / P1-8 / P1-10 / P1-11 / P1-12 / P2-1 / P2-3 / P2-5 / P2-6 / P2-7):5/6 wrapper / GET service contract / 红线来源 / figure 反幻觉单边 / locator 白名单 / cache 态 / asyncio.to_thread 覆盖窄 / 4 golden 表述 / 隐私 grep 缺 / paper_id 替代不足 / Windows 软监控 / Router 层 / 502 接力 / 反模式 1 覆盖口径 / 9-component / 签名两处 / 文件数 / 错误码

**R1 二审阶段(v0.2 → v0.3)**:

- **架构师 K_28a +0**(本轮架构师未犯凭印象新错;v0.2 修订时已 grep 字面)
- **K_30 +12**(R1 二审 P0-2 / P0-3 / P1-1 / P1-3 / P1-4 / P1-5 / P1-6 / P1-7 / P1-8 / P2-1 / P2-2 / P2-3):raw 文档清理 / psutil 冲突 / 反模式 4 测试名义 / router IO 同步 / sandbox 过度承诺 / decision 21 grep 偏窄 / venv 排除 / 真启动输入源 / raw_text 长度 / 七件套 / EvidenceSource 镜像措辞 / 反模式 3 拆分 — 全部 R1 抓的真问题(K_30 跨段同步未完成漂移)
- **R1 自身 K_28a +1**(本轮 R1 也凭印象错):R1 一审 P1-6 + 二审 P0-1 同方向错(主张 `expected_missing_prompts.json` 顶层 list,但实际是 dict);架构师反 challenge 实证驳回
- **架构师抓 R1 反例 +1**(本轮首次 R2 challenge):反 challenge R1 P0-1 修订方向反

**R1 三审阶段(v0.3 → v0.3.1 终版)**:

- **架构师 K_28a +0**(本轮规规矩矩 grep / view)
- **K_30 +7**(R1 三审 P1-1 / P1-2 / P1-3 / P1-4 / P1-5 / P1-6 / P2-1 / P2-2 共 8 项中 K_30 类):file_hash 用途未明 / seek(0) 缺 / ls 不准确 / evidence 数组校验过泛 / find 命令不稳 / 阶段 3 旧表述残留 / Router 分层归属混 / prompt 禁出过严 — 全部小修(K_30 密度持续下降:R1 一审 17 / 二审 12 / 三审 7,**收敛趋势明显**)
- **R1 自身 K_28a +0**(本轮 R1 抓的全是真问题;R2-C3 R1 自己确认)
- **架构师抓 R1 反例 +0**(本轮 0 challenge,R1 三审 0 P0)

**TASK-501 Stage 2 实施期(v0.3.1 → v0.3.2 微补丁)**:
- 架构师 K_28a +0 / K_30 +2(06 § 12.5 起稿期 library_choice 1-100 字过紧 + ParameterMapping.unit 子项未明示)
- 架构师抓 R1 反例 +0(R1 三轮均未抓此 K_30,凭任务卡描述判;非反 challenge 范畴,属于 R1 brief 工艺漏)
- Codex Stage 2 抓 PM/架构师反例 +1(sample roundtrip 实测抓出 06 字面 vs 样本包冲突,工艺规则有效)
- **R6 Stage 2 工艺胜利**:决策 12 v0.4 R6 完工实测层在 Stage 2 实施期生效(继 Stage 0 入口生效后第二次),实证"R6 不只是完工后实测,在每阶段实施期都该实测"

**累计本任(v0.1 → v0.3.2)**:架构师 K_28a +3 / K_30 +38 / 架构师抓 R1 反例 +1 / R1 自身 K_28a +1 / Codex 抓 PM+架构师反例 +1(Stage 0 入口 base hash + Stage 2 实施期 sample × schema 冲突)

- **K_31 +0**:本卡无降级压力,沿用决策 22 § 10.4 五项门槛全 ✅ 前提
- **K_34 +0**:本卡引用字面 = 直接查源文件而非凭语义记忆(架构师 v0.2 起规规矩矩 grep,但 R1 二审仍出 K_28a)
- **K_36 +0**:本卡 PM 验收边界 + 红线文件未动 + 样本包未改 三处沿用 TASK-500 v0.2.1 字面

**反思**(决策 12 v0.4 § 4.1 #6 + R2 反 challenge 工艺验证 + R3 收敛验证):

1. **第 45 任 K_28a +3 ≤ 41 任 +7**;K_30 +36 是本任最高发,paper-to-model 跨契约同步漏密集触发(05 / 06 / 04 / 02 / 决策 22 / 决策 21 / decision-11 / decision-18 / sample pack 跨九处),触发决策 22 § 9 "若 paper-to-model 主线首 task 仍密集触发 K_28a / K_30,触发深挖根因 task" 路径
2. **R1 三轮收敛趋势**:R1 一审抓 26 项 + 二审抓 14 项 + 三审抓 7 项 = 47 项,无一漏到 Codex Stage 0;**收敛趋势明显**(K_30 密度逐轮下降),实证三审工艺对架构升级类 task 必要
3. **R1 工艺规则有效但有边界**:**R1 自身依赖任务卡描述,不查源文件**,导致 R1 一审 P1-6 + 二审 P0-1 连环 K_28a;架构师 R2 反 challenge 工艺(决策 12 v0.4 R2 公开 challenge 清单)在本轮首次抓出 R1 反例,**R1 三审自己确认 R2-C3 成立**,实证 R2 工艺对"挡 R1 错误向下传播"有效
4. **R1 三审作为收尾审**:R1 三审明示"不需要四审"(除非 v0.3.1 改动 06 § 12 字段 / API 路由范围 / cache 语义 / sandbox 机制 — v0.3.1 7 项小修均不动这些),实证三轮 R1 是架构升级类 task 的稳态轮次上限
5. **v0.5 协议候选**:
   - **第 7 项**(R1 一审挂账):架构升级类 task 起稿前必须列出所有跨段同步源 + grep 字面一致性
   - **第 8 项**(R1 二审挂账):**R1 brief 必须明示要 R1 view 关键样本 / 源文件实际内容,不许仅靠任务卡描述判断**(连环 K_28a 工艺补丁)
   - **第 9 项**(R1 三审验证):R 轮被审方采纳率应 ≥ 80% 但不应 = 100%(若 = 100% 表明被审方丧失 challenge 能力或 R 轮抓错被默认采纳,工艺反向退化);本任三轮采纳率:一审 100% / 二审 92.9% / 三审 100%,均在健康区间(二审反 challenge 是工艺正常)
   - **第 10 项**(R1 三审验证,本轮新):架构升级类 task R 轮上限 = 3 轮(若三轮后仍有 P0 阻塞,触发"换审方 / 拆任 / 深挖根因 task"路径,不再继续 R 轮)

---

## 给 Codex 的提示

按宪法 § 5 沟通模板。**Stage 0 必查**:

1. **Base commit 校验**:PM 派单时提供 base commit hash;Codex 验证 main 含 TASK-500 ✅ + 五项前置门槛全部入仓(grep 03 索引 + 06 § 12 + 04 § 8.6 + eval/cases/paper_to_model/ 12 文件 + 对外口径 grep)。若 base commit 漂移或 TASK-500 状态不符 → 停手报 PM

2. `git status` 工作树洁;有 untracked 报 PM 后再开工

3. **样本包到位实测**(沿用 TASK-500 v0.2.1 Stage 0 #3 模式;R1 三审 P1-3 + P1-4 修订):
   - **12 文件 manifest 实测**(R1 三审 P1-3:改 `find -type f`,不再用 `ls` 根目录):
     ```bash
     find eval/cases/paper_to_model -type f \
       ! -path '*/.venv/*' ! -path '*/.git/*' \
       | sort
     ```
     输出必须精确匹配以下 12 个路径:
     - `eval/cases/paper_to_model/README.md`
     - `eval/cases/paper_to_model/verification_method.md`
     - `eval/cases/paper_to_model/scoring_template.md`
     - `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/case_README.md`
     - `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/input/source_doc_stripped.md`
     - `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/golden/expected_paper_spec.json`
     - `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/golden/expected_model_generation_plan.json`
     - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/case_README.md`
     - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/source_doc_stripped.md`
     - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/expected_missing_prompts.json`
     - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/user_input/user_supplied_params.json`
     - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/golden/expected_updated_plan.json`
   - **JSON 合法实测**:`find eval/cases/paper_to_model/ -name '*.json' -exec python -m json.tool {} \; > /dev/null` 全过
   - **按 artifact 类型分校验 evidence 双源不变量**(R1 三审 P1-4 修订:不同 sample JSON 顶层结构不同,不许统一按"顶层 evidence 数组"校验):
     - `expected_paper_spec.json`:校验 `PaperSpec.evidence[*]` 满足 `verification_method.md` § 3 字面
     - `expected_model_generation_plan.json`:若 06 § 12.5 字段含 `evidence`,校验 `ModelGenerationPlan.evidence[*]` 同样规则
     - `expected_missing_prompts.json`:**读取 `json_data["missing_prompts"][*]`**(顶层 dict,R1 二审 P0-1 架构师反向采纳),逐项校验 `MissingParameterPrompt.paper_reference`(`PaperEvidenceEntry` 结构,对齐 06 § 12.7)
     - `expected_updated_plan.json`:同 `expected_model_generation_plan.json`
   - **不得**假设 4 个 sample JSON 都有顶层 `evidence` 数组
   - 任一 Fail → 停手报 PM(走 task-500 v0.2.2 微补丁,不在本卡;不许 Codex 自改样本包)
   - **特别注意**:`expected_missing_prompts.json` 在 `input/` 下不在 `golden/` 下,且**顶层是 `dict` 含 `missing_prompts: list`**,不是单对象(R1 二审 P0-1 架构师反向采纳;R1 三审裁定该方向成立)

4. **字面对齐实测**(K_28a / K_30 自防):
   - **`LLMResponse` 字段**:`docs/02_ARCHITECTURE_OVERVIEW.md` § 4.3 字面 `text / prompt_tokens / completion_tokens / model / latency_ms`;本卡 § 7.10 Step 1 用 `response.text`,**不**用 `.content`(R1 P0-1)
   - **06 § 12 字段表**:本卡 § 7.1 / 7.2 / 7.3 / 7.4 / 7.5 / 7.6 引用的字段名 / 数量必须与 main HEAD 06 § 12.1 - 12.8 一致
   - **04 § 8.6 字面**:本卡 § 7.8 / 7.9 / 7.12 引用的 7 子项 a-g 必须与 main HEAD 04 § 8.6 (a) - (g) 一致
   - **本卡合并守门红线 6 项**:Codex 必须 grep 三源追溯(决策 22 § 5.2 / 决策 21 / TASK-500 v0.2.1)— 不再要求"全是决策 22 § 5.2 字面"(R1 P0-5)
   - **12 sample files 字面**:本卡 § 7.7 引用的 4 个 sample JSON 路径必须与 main HEAD eval/cases/paper_to_model/ 字面一致
   - 任一不一致 → 停手报 PM,不许 Codex 自决修

5. **5 阶段改动顺序**(§ 实施步骤):阶段 1 → 2 → 3 → 4 → 5;每阶段完工 → `git diff --name-only origin/main` 自审范围 → 下一阶段

6. **新依赖审批**(D7):Codex **不**自决 pypdf / python-docx 版本号;实施期查 PyPI 最新稳定 → PM PR review 拍板 → 写 requirements.txt

7. **跨平台沙箱注意**(D8 + R1 一审 P1-10 + R1 二审 P0-3 修订):
   - Linux 生产环境用 `resource.setrlimit(RLIMIT_AS / RLIMIT_CPU)` 硬限
   - **Windows / macOS 本地开发不引 `psutil`**(R1 二审 P0-3:与"除 pypdf / python-docx 外不引依赖"红线冲突);用 multiprocessing + 30s timeout + cwd 隔离 + 错误脱敏弱隔离,无 mem 强制上限,OS OOM-killer 兜底
   - **Windows 生产支持不在 v0.1 范围**:非 Linux 启用真实解析时 fail-closed,抛 `DocumentParseError("unsupported_parser_sandbox_platform")`;Codex 实施期若 PM 需要 Windows 生产 → 停手报 PM

8. **样本包 JSON 顶层结构 view**(R1 二审 P0-1 架构师反向采纳):
   - `python3 -c "import json; d=json.load(open('eval/cases/paper_to_model/missing_param/case_01_missing_image_param/input/expected_missing_prompts.json')); print(type(d).__name__, list(d.keys()) if isinstance(d, dict) else len(d))"` → 必为 `dict ['missing_prompts']`
   - 若顶层非 dict 或不含 `missing_prompts` key → 停手报 PM(走 task-500 v0.2.2 微补丁,不在本卡;不许 Codex 自改样本包)
   - 其他 3 个 sample JSON 顶层必为 dict 单对象

9. 全部完工 → **R6.1 完工实测清单**(R1 二审 P2-1 改名;沿用 TASK-500 v0.2.1 R6.1 模式 + R1 一审 P1-5 / P1-7 / R1 二审 P0-2 / P1-3 / P1-5 / P1-6 扩展):
   - **范围实测**:`git diff --name-only origin/main` 输出在 § 输出 文件清单内
   - **决策 11 grep**:`logger.exception` 在 paper / parser / api/routes/paper_upload 路径 0 命中;`asyncio.to_thread` 在 `paper_spec_service.py` **≥ 3 处**(R1 二审 P1-3:parser router.route + sandbox parser + LLM)+ `api/routes/paper_upload.py` ≥ 3 处(文件保存 + SHA-256 + cleanup)
   - **决策 21 boundary grep**(R1 二审 P1-5 扩展,排除 .venv / .git):`grep -rnE '(^|[[:space:]])(from|import)[[:space:]]+features\.(overview|explanation)|features\.(overview|explanation)\.' features/paper/ adapters/parser/ core/domain/paper_*.py --exclude-dir=".venv" --exclude-dir=".git"` 应空 + `grep -rnE "EvidencePack|ExplanationPack|_evidence_builder|overview_schemas|ProjectOverview" features/paper/ core/domain/paper_*.py adapters/parser/ --exclude-dir=".venv" --exclude-dir=".git"` 应空
   - **本卡合并守门红线 6 项未动**(逐个跑 6 个文件)
   - **样本包未改**:`git diff --name-only origin/main -- eval/cases/paper_to_model/` 应空
   - **临时文件清理实测**(R1 二审 P0-2 新增):`find /tmp/mxa_paper_sandbox -type f -maxdepth 2 -path './.venv' -prune -o -path './.git' -prune -o -print` API 测试结束后应为空(或只剩 TTL 管理文件;不得剩 raw PDF/docx)
   - **隐私 grep**(R1 一审 P1-7 + R1 二审 P1-6 加 .venv/.git 排除):`grep -rnE "logger\.(debug|info|warning|error).*file\.filename|logger\.(debug|info|warning|error).*raw_text|logger\.(debug|info|warning|error).*response\.(text|content)|str\(exc\)|repr\(exc\)" features/paper/ adapters/parser/ api/routes/paper_upload.py --exclude-dir=".venv" --exclude-dir=".git"` 应空,或逐项说明是安全元数据
   - **对外口径**:`git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器" features/paper/ adapters/parser/ api/routes/paper_upload.py core/prompts/paper_spec_extract.yaml` 应空
   - **freeze test + sample roundtrip 实测**:pytest 命令 + 输出贴 PR

10. PR 完工 report 必须按 R6.1 实证,不许凭主观范围声明(决策 12 v0.4 R6.1)

11. 若实施期发现 task 描述与宪法 v3.1 / 02 v3.0 delta / 06 § 12 / 04 § 8.6 / 决策 22 / 决策 21 / 决策 11 / 决策 18 任一冲突 → 停手报 PM(宪法 § 15)

---

**版本**:v0.3.2(2026-06-16,**终版 + Stage 2 微补丁**;R1 三审 conditional pass 0 P0 + 5 P1 + 2 P2 全采纳 + 0 challenge;Stage 2 sample roundtrip 实测驱动 06 § 12.5 约束微调;PM 已拍 C1 / C2 / R2-C3;架构师第 45 任修订)

**日期**:2026-06-16

**作者**:Claude(架构师,第四十五任)

**关联宪法版本**:v3.1

**关联决策**:
- `docs/decisions/20260615-22-direction-pivot-paper-to-model.md` § 10.4 + § 5.2(主线启动 + 红线)
- `docs/decisions/20260616-23-product-architecture-v02-v03-client-techstack.md`(v0.2 / v0.3 路线锚定,TASK-501 不接 Engine)
- `docs/decisions/20260616-24-business-path-and-cross-industry-expansion.md`(用户分层 L1-L4,TASK-501 不动 B 端)
- `decision-21-evidencepack-consumption-boundary.md`(paper feature 不 import overview / explanation 私有)
- `decision-18-projectoverview-api-serialization-boundary.md`(domain / Pydantic wrapper / bridge 桥接模式)
- `20260604-11-async-blocking-and-logger-exception-bans.md`(决策 11 async + logger 双不变量)
- `decision-13-schema-sync-checklist.md`(schema 同步流程)

**关联工艺**:决策 12 v0.4(R1 + R6 + PM)

**关联 task**:
- 前置:TASK-500 v0.2.1(开门 chore 五项门槛)
- 后续:TASK-502(PaperPlanService)+ TASK-503(TuningSuggestion + UX + GET + 持久化 cache)

**入仓**:任务文档单独 PR(沿用既有 task chore PR 模式;无同名旧任务卡,**create_file 模式**,K_28b 子类化反思已明示)

**修订历史**:

- v0.1(2026-06-16):架构师起稿,2 个 challenge 点待 PM 拍板(C1 拆分 / C2 解析依赖)。**起稿期自抓 K_28a +1**:`ModelGenerationPlan 9 字段` → 8 字段
- v0.2(2026-06-16):**GPT R1 conditional pass**(5 P0 + 14 P1 + 7 P2);架构师全部采纳 + 自审补强 5 项,**0 challenge,抓出 GPT 反例 0**(R1 抓得到位):
  - **R1 P0 5 条全采纳**(K_28a / K_30):
    - P0-1(K_28a):`response.content` → `response.text`(对齐 02 § 4.3 LLMResponse 字段)
    - P0-2(K_30):`6 Pydantic wrapper` → `5 顶层 wrapper + 6 nested submodel + EvidenceSource enum 镜像`(对齐 06 § 12)
    - P0-3(K_30):删 `GET /api/v1/papers/{paper_id}/spec`(留 TASK-503;cache 保留作 TASK-502 接力面)
    - P0-4(K_30):§ 7.9 parser sandbox 补子进程权限隔离 + 错误脱敏(对齐 04 § 8.6 (c) + (g))
    - P0-5(K_28a):红线"决策 22 § 5.2 字面 6 项" → "本卡合并守门红线 6 项,三源 = 决策 22 § 5.2 + 决策 21 + TASK-500"
  - **R1 P1 14 条全采纳 / 部分采纳**:
    - P1-1:D2 补"替代方案 A 实质优势"
    - P1-2:figure 反幻觉 Step 4 改两段(无图必空 + 有图属白名单)
    - P1-3:locator 白名单(`paper_section_id` / `equation_id` / `figure_id` ∈ parser 注入集合)
    - P1-4 + 自审:cache ready-only + GET 删 + cache 作 TASK-502 接力面
    - P1-5:asyncio.to_thread 扩展到文件保存 + SHA-256
    - P1-6:4 sample JSON 表述精确化(`expected_missing_prompts.json` 在 input/ 下 + 是 list)
    - P1-7:R6.1 加隐私 grep
    - P1-8:D10 补 ULID / file_hash 替代方案
    - P1-9:python-docx "微软官方" → "成熟社区库"
    - P1-10:Windows 软监控写成环境策略(生产以 Linux 为门槛)
    - P1-11:`DocumentParserRouter` 放 `core/interfaces/` 明确所属层
    - P1-12:502 接力增加 locator 不变量
    - P1-13:6 类恶意 fixtures 硬要求,扩展样本(xfa_form / encrypted.docx)非阻塞
    - P1-14:新增 D12(PaperPlanService 不落地 + cache 语义)
  - **R1 P2 7 条全采纳**:
    - P2-1:反模式 1 覆盖文字统一
    - P2-2:行号 vs 节号措辞精确化
    - P2-3:9-component 数量口径(501 仅 Extractor)
    - P2-4:GET 范围段同步(被 P0-3 吸收)
    - P2-5:`extract` 签名统一为 `(file_path, paper_id)`
    - P2-6:17-20 文件 → 20-22 文件
    - P2-7:错误码 machine code 标准化
  - **架构师自审补强 5 项**(R1 未抓):
    - `UploadDocumentResponse` Pydantic model 定义(§ 7.12)
    - Step 5 evidence 校验明示本卡范围仅 `document_extracted`
    - Step 3 简化(Pydantic Literal 已硬拦 domain,不在 service 层重复)
    - `DocumentParserRouter` 接口 + 层级约束(§ 7.8)
    - `InMemoryPaperSpecCache` 加 `asyncio.Lock` 保护
  - **本任反例账目**(决策 22 § 9 趋势记账):K_28a +2 / K_30 +17 / 其他 +0;K_30 是本任最高发,paper-to-model 跨契约同步漏与 41 任同源;v0.2 修订后已收敛;**v0.5 协议候选第 7 项挂账**(架构升级类 task 起稿前必须列出所有跨段同步源 + grep 字面一致性)
  - **K_28a 自防生效**(本轮 +2,vs v0.1 起稿期 +1):R1 P0-1 引用 LLMResponse 字段时架构师未 grep 02 § 4.3 → R1 抓出 → v0.2 已 grep 字面修订;实证 R1 工艺规则有效(无一漏到 Codex)但起稿源头仍不充分(架构师 v0.1 凭印象密度比 41 任低,但仍高于 R1 抓 0 的稳态)
- v0.3(2026-06-16):**GPT R1 二审 conditional pass**(3 P0 + 8 P1 + 3 P2 = 14 项);**架构师采纳 13 + 反向采纳 1**(R1 抓真问题但修订方向反 1 项):
  - **R1 二审 P0 3 条**:
    - P0-1(K_30 / R1 凭印象):`expected_missing_prompts.json` 顶层 shape 矛盾 — **架构师反 challenge,反向采纳**:R1 主张统一 list,但样本包实际顶层是 `dict { "missing_prompts": list[MissingParameterPrompt] }`;架构师实证驳回 R1 修订方向(`python3 json.load(...).keys() = ['missing_prompts']`),v0.3 统一 dict,§ 7.7 原测试代码保留
    - P0-2(K_30)全采纳:raw 文档 try/finally 清理 — § 7.12 加完整 try/finally 伪代码 + 4 项测试 + R6.1 find 实测
    - P0-3(K_30)全采纳:psutil 依赖冲突 — 删 psutil(D8 / Stage 0 / 表格 4 处);Windows / macOS 本地开发改用 multiprocessing + timeout 弱隔离,无 mem 上限,OS OOM-killer 兜底
  - **R1 二审 P1 8 条全采纳**:
    - P1-1:反模式 4 测试改名(`test_anti_pattern_4_evidencepack_shape_rejected`)+ 06 § 12.8 字面 payload + generic extra 另起名 `test_extra_forbid_generic_unknown_field`
    - P1-2:Step 5 加 `parameter_table.source` + `evidence.source` 校验 + 2 测试
    - P1-3:`router.route(file_path)` 在 service 内 `to_thread`(docx ZipFile 同步 IO);R6.1 service ≥ 3 处
    - P1-4:`test_child_process_cannot_write_project_dir` 改 4 项可实现不变量(multiprocessing 不提供 OS 级权限隔离;v0.2 自审补强过度承诺)
    - P1-5:决策 21 grep regex 扩展(覆盖 `from / import / .` 三形式)
    - P1-6:所有 `grep -rn` / `find` 加 `--exclude-dir=".venv" --exclude-dir=".git"`(决策 `20260601-05` 字面)
    - P1-7:真启动验收明示用剥离版 docx,A2 禁出项仅适用剥离版
    - P1-8:加 `MAX_PAPER_RAW_TEXT_CHARS = 80_000` fail-fast(超 80K 字符 → `DocumentParseError("document_too_long_for_v0_1")`)+ 1 测试
  - **R1 二审 P2 3 条全采纳**:
    - P2-1:"七件套"→"完工实测清单"(避免数字漂移 K_30)
    - P2-2:EvidenceSource enum **直接复用** core.domain(去"镜像"字眼,4 处统一)
    - P2-3:反模式 3 拆两测试(`no_locator` + `no_excerpt` 子句,覆盖 06 § 12.8 反模式 3 "没有 locator **或** 摘录"完整语义)
  - **架构师反 challenge R1 1 项(R2 公开 challenge 清单 R2-C3)**:R1 二审 P0-1 修订方向反 — R1 主张 list 但实际样本包顶层是 dict;架构师实证驳回方向,反向采纳(统一 dict 而非 list)
  - **本任反例账目**(决策 22 § 9 趋势记账,R2 轮):
    - K_28a +1(R1 二审 P0-1 R1 凭印象,样本包实际是 dict 不是 list;架构师反向采纳后已收敛)
    - K_30 +多(R1 二审 P0-2 / P0-3 / P1-1 / P1-3 / P1-4 / P1-5 / P1-6 / P1-7 / P1-8 / P2-1 / P2-2 / P2-3 ≈ 12 项 K_30 实例)
    - **R1 K_28a +1**(R1 自己):一审 P1-6 凭印象统一为 list,二审 P0-1 又凭印象同方向错;架构师两轮均未 verify(连环 K_28a)
    - **架构师抓 R1 反例 +1**(本轮首次 R2 challenge):反 challenge R1 P0-1 实证驳回方向
  - **K_28a 自防生效 + 反向**(本轮 +1 抓 R1 反例):R1 工艺规则有效但 R1 自身依赖任务卡描述,不查源文件;v0.5 协议候选第 8 项挂账:**R1 brief 必须明示要 R1 view 关键样本 / 源文件实际内容,不许仅靠任务卡描述判断**(连环 K_28a 工艺补丁)
- v0.3.1(2026-06-16,**终版**):**GPT R1 三审 conditional pass**(0 P0 + 5 P1 + 2 P2 = 7 项);架构师全采纳,**0 challenge**;**R1 三审明示不需要四审**(除非 v0.3.1 改动 06 § 12 字段 / API 路由范围 / cache 语义 / sandbox 机制 — v0.3.1 7 项小修均不动这些);**R2-C3 R1 自己裁定成立**(架构师反 challenge R1 二审 P0-1 修订方向):
  - **R1 三审 P0**:**0 项**(C1 / C2 / D12 / GET 删 / response.text / locator 白名单 / ready-only cache / R6.1 grep 全部继续通过)
  - **R1 三审 P1 5 条全采纳**:
    - P1-1:§ 7.12 `file_hash` 明示用途(安全 metadata 日志 + ParsedDocument 校验,不进 response,不与 file.filename 一起记日志)
    - P1-2:§ 7.12 magic byte 读 8KB 后必须 `await file.seek(0)`(否则保存的临时文件丢前缀,parser magic byte / docx zip 校验失败)+ 1 测试 `test_upload_document_preserves_magic_prefix_after_sniffing`
    - P1-3:Stage 0 #3 改 `find -type f` manifest 式 12 文件路径精确匹配(`ls` 根目录有嵌套 case 目录,不能正确显示 12 文件)
    - P1-4:Stage 0 #3 双源校验按 4 个 artifact 类型分校验(`expected_missing_prompts.json` 读 `json_data["missing_prompts"][*].paper_reference`;不许统一按"顶层 evidence 数组"校验)
    - P1-5:R6.1 临时文件清理 `find` 命令规范化(`-maxdepth` 位置 + prune 分组 + `$PAPER_TMP_ROOT` 路径前缀)
    - P1-6:阶段 3 残留"子进程不持可写 project 目录"旧表述替换为 v0.3 已采纳的 4 项可实现不变量(multiprocessing 不提供 OS 级权限隔离,过度承诺已收敛)
  - **R1 三审 P2 2 条全采纳**:
    - P2-1:`features/paper/__init__.py` 只 re-export `PaperSpecService + InMemoryPaperSpecCache`;`DocumentParserRouter` 从 `core.interfaces.document_parser` import,不从 paper feature re-export(分层归属修复)
    - P2-2:Prompt invariant `5MW / ode15s / 1s` 禁出加条件(剥离版禁出;原文显式给出时只能进 `document_extracted` 不能扩展成 ModelGenerationPlan 工程决定)
  - **本任反例账目**(决策 22 § 9 趋势记账,R3 轮):
    - 架构师 K_28a +0(本轮规规矩矩 grep / view)
    - K_30 +7(R1 三审全部 P1 / P2,但密度持续下降:R1 一审 17 / R1 二审 12 / R1 三审 7 — 收敛趋势)
    - R1 自身 K_28a +0(本轮 R1 抓的全是真问题)
    - **架构师抓 R1 反例 +0**(本轮 R1 三审 0 challenge,因为 R1 自己也确认 R2-C3 成立)
- v0.3.2(2026-06-16,Stage 2 微补丁):**架构师自决修 + PM 拍板,不走 R1 四审**(对齐 v0.3.1 § 输出 段预留通道);Codex Stage 2 sample roundtrip 实测抓出 06 § 12.5 与样本包冲突:
  - `library_choice` 长度 1-100 字过紧 → 改 1-300 字(样本包实测 180-185 字符,LLM 真实输出大概率库名 + 选型理由二合一)
  - `ParameterMapping.unit` 子项约束未明示 → 改 `str | None`(配置参数如变压器接线 `Yn / d11` 无物理单位)
  - 同源 5 处同步:06 § 12.5 / `paper_plan.py` dataclass / `paper_schemas.py` Pydantic wrapper / freeze test 断言 / `schemas/paper_plan.schema.json` 重生成
  - **K_30 反例账目 +2**:06 起稿期 library_choice 约束过紧 + ParameterMapping.unit 未明示;架构师起稿期未跑 sample roundtrip dry run
  - **v0.5 协议候选第 12 项挂账**:契约 schema 字段约束必须由样本数据实测驱动,起稿期 + 修订期都跑 sample roundtrip dry run
  - **v0.5 协议候选第 8 项落地补丁**(R1 二审挂账的具体应用场景):R1 brief 须含 "对每个 sample × 06 字段约束跑 sanity check"实测命令(本次 R1 三轮均凭 v0.3.x 任务卡描述判,没跑样本 × schema sanity check;若跑过会在 R1 一审就抓出此 K_30 反例)

**累计本任(v0.1 → v0.3.2)**:
- 架构师 K_28a +3(v0.1 自抓 1 / R1 一审 2 / R1 二审 0 / R1 三审 0)
- K_30 +38(R1 一审 17 / 二审 12 / 三审 7 / Stage 2 实施期 2)
- 架构师抓 R1 反例 +1(R2-C3,首次)
- R1 自身 K_28a +1(一/二审 P0-1 连环,三审自己确认错)
- Codex 抓 PM+架构师反例 +1(Stage 2 sample × schema 冲突)
- R 轮采纳率:一审 100% / 二审 92.9% / 三审 100%(三轮均在健康区间;二审有反 challenge 是工艺正常)
- **v0.5 协议候选 3 项挂账**(详 § 工艺):第 7 / 8 / 9 项

**R1 三审已确认消化的修订**:
- `expected_missing_prompts.json` 顶层 dict + Stage 0 实地验证 ✅
- raw 文档 try/finally 清理 + 24h TTL 兜底 ✅
- psutil 删除 + Linux RLIMIT 生产门槛 ✅
- response.text + router/sandbox/LLM 三处 to_thread + raw_text 80K fail-fast ✅
- 反模式 1/2/3/4 freeze test + EvidencePack shape 与 generic extra 拆开 ✅
- R6.1 实测清单(boundary grep + 隐私 grep + 样本包未改 + 临时文件清理 + 对外口径 grep)✅
