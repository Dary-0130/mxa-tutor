# TASK-500:paper-to-model 开门 chore(5 项前置硬门槛一锅炖)

## 状态

🔲 v0.2.1(R1 复审 conditional pass:0 P0 + 3 P1 + 3 P2 全采纳;待 PM 拍板 → Codex Stage 0 → R6.1)

---

## 上下文

- 决策 22 § 10.4 锁定 paper-to-model 主线 5 项前置硬门槛,任一未完成 = TASK-501 派单封禁
- PM 拍板:不拆 chore,5 项一锅炖(2026-06-15)
- 编号 **TASK-500**:卡在 MCS 缓冲段(311-499)末与 paper-to-model 主线起点(501)之间,沿用 TASK 前缀不引入新概念
- **本 chore 产出 = 文档与规范层(契约 + 安全规范 + 对外口径 + 评测样本包),不写功能代码**(避免开门 chore 膨胀成实现 task,GPT 联审 P2 防卡死)
- 功能代码留 TASK-501 系列

---

## 5 项门槛拆解

### 门槛 1 — 06 契约新增三套 schema(PaperSpec / ModelGenerationPlan / TuningSuggestion)

- **改文件**:`docs/06_OUTPUT_CONTRACTS.md`
- **改动**:
  - **末尾新增 `## 12. paper-to-model 输出契约`**(06 现有最末为 `## 11. 版本`,本 chore 新增 § 12)
  - 三套主 schema(PaperSpec / ModelGenerationPlan / TuningSuggestion)字段表 + 反模式示例(参照现有 § 2 / § 6 风格)
  - 每个 schema 标 "v0.1 草稿,字段未冻结,TASK-501 落地时按 § 7 D1-B 三层同源流程演进"
- **字段策略(关键)**:**最小可用 + 占位**;不一次性冻结全部最终字段;允许 TASK-501 实施期按 D5 流程演进
- **同步**:§ 7 修订流程章节追加 paper-to-model 同源路径:`core/domain/paper_*.py` domain dataclass/contract + `features/paper/paper_schemas.py` Pydantic wrapper + `tests/features/paper/test_paper_schema_freeze.py` + 06 + `schemas/paper_*.schema.json`(均为占位路径,TASK-501 实际新建)
- **不动**:既有 ProjectOverview 12 字段 / 7 枚举 / SourceRefEntry / ChunkRecord 任何字面(决策 22 § 5.2 红线)

> **决策 22 § 10.4 字面对齐注**:决策 22 第 1 项字面是"06 新增 paper-to-model **三套契约**"(PaperSpec / ModelGenerationPlan / TuningSuggestion);MissingParameterPrompt + EvidencePack 双源在第 2 项(门槛 2)。本 chore 三套与双源同在 06 § 12 章节落地,但任务拆解口径按决策 22 字面分项,避免跨段同步漂移。

### 门槛 2 — MissingParameterPrompt + EvidenceSource + PaperEvidenceEntry 双源契约

- **改文件**:`docs/06_OUTPUT_CONTRACTS.md`(并入门槛 1 的 § 12 同一章节)
- **改动**:
  - 新增公共 `EvidenceSource` enum:`Literal["document_extracted", "user_supplied"]`
  - paper-to-model 新增 `PaperEvidenceEntry` schema(**不复用** explanation 的 EvidencePack 名字,避免歧义),含 `source: EvidenceSource` + paper 类证据字段(`paper_section_id` / `equation_id` / `figure_id`);约束详 § 接口契约要点
  - 新增 `MissingParameterPrompt` schema(字段表详 § 接口契约要点),其 `source` 字段恒为 `user_supplied`,体现双源契约
- **红线**:**不改** `features/explanation/_evidence_builder.py` 现有 EvidencePack 任何字段(决策 22 § 5.2;决策 21 boundary)
- **架构师拍板理由**:既有 EvidencePack 包含 14 类 EvidenceKind + 3 类 typed payload(`EndpointRef` / `SignalPathPayload` / `ParameterContextPayload`),全是 .slx 工程语境;论文证据语境不同(段落 / 公式 / 图表),独立新建比扩既有合理
- **PM 已拍板**:走方案 B(独立新建)。2026-06-15 PM 确认
- **消费者注意**(06 § 12 必须明示):`PaperEvidenceEntry` 是 paper-to-model 独立证据条目,**与既有 `features/explanation/_evidence_builder.py::EvidencePack` 无包含 / 继承 / 引用关系**;避免下游消费者误以为是子集
- **Python 实现落地路径占位**:`core/domain/paper_evidence.py` domain dataclass/contract(含 `EvidenceSource` enum + `PaperEvidenceEntry`)+ `features/paper/paper_schemas.py` Pydantic wrapper;命名可由 TASK-501 微调;**本 chore 不落地 Python 实现**,仅在 06 写契约字面 + 在 § 7 修订流程占位路径

### 门槛 3 — 04 文档上传安全(PDF / docx,7 子项)

- **改文件**:`docs/04_ENGINEERING_STANDARDS.md`
- **改动**:**新增 `### 8.6 文档上传安全(PDF / docx)`**(04 现有 § 8.5 是测试要求 malicious_zips,本 chore 不动 § 8.5,在其后新增 § 8.6),7 子项:
  - **(a) 上传入口策略**:**PM 已拍板**新增独立路由 `POST /api/v1/upload-document`(2026-06-15)。理由:zip 工程沙箱白名单(.m / .slx / .mat / .prj 等)和文档白名单(.pdf / .docx)不交集,共用会让 sandbox 分支逻辑膨胀;独立路由方便前端区分"工程入口 / 资料入口"二选一(决策 22 § 2.1 E2)。本 chore 在 04 § 8.6 写明路由路径 + 边界,不实现路由(留 TASK-501)
  - **(b) magic byte sniffing**:PDF 头 `%PDF-`(0x25 50 44 46 2D);docx 是 zip 容器,头 `PK\x03\x04` + 内容校验 `[Content_Types].xml`;扩展名匹配 + 内容头双重校验,任一不符拒绝
  - **(c) parser sandbox**:解析超时(默认 30s 可配置)+ 内存上限(默认 512MB 可配置)+ 子进程隔离(解析进程崩溃不影响主进程);对齐既有 § 8.2 zip 沙箱风格
  - **(d) 解析依赖审批**:新增 PDF / docx 解析库必须走 `requirements.txt` PR review(沿用 `docs/04_ENGINEERING_STANDARDS.md` § 6 依赖管理规范:requirements.txt / requirements-dev.txt + 禁止 Codex 自己 pip install);本 chore 不引入任何解析库,具体库选型由 TASK-501 评审
  - **(e) 恶意 fixtures 占位**:`tests/fixtures/malicious_documents/` 目录骨架(实际 fixtures 由 TASK-501 收集)+ README 写明覆盖类型:加密 PDF / 嵌入 JS 的 PDF / 巨型 PDF / 含宏的 docx / zip bomb 风格 docx / 损坏 docx
  - **(f) 外链 / 嵌入对象 / 宏 / OCR 策略**:解析器**不执行任何嵌入对象**(JS / 宏 / OLE)+ **不联网**(禁止解析 URL 引用的远程资源)+ **不解析远程图像**;OCR 在 v0.2 评估,v0.1 不接(决策 22 § 4.8 第 ii 选项延期)
  - **(g) raw 文档持久化与脱敏策略**:对齐 01 § 9 + 04 § 8.3 既有策略:**raw 原文不持久化**;允许持久化结构化抽取结果 `PaperSpec`,但须受长度上限 / 字段级脱敏 / `source: document_extracted` 来源标注 / 临时目录 24h TTL 删除策略约束
- **不动**:§ 8.1-8.5 既有 zip 沙箱与测试要求章节字面(§ 8.5 是 zip malicious 测试要求,与 § 8.6 PDF/docx 文档安全独立并列)

### 门槛 4 — v0.1 对外口径(前端 / 销售 / API / README)

- **改文件**:Codex 全仓扫描确定,候选清单:
  - `README.md`(项目根)
  - `web/` 前端上传页文案 / 提示文案
  - 任何对外文案(销售物料若在仓)
  - **不动 `docs/api/**`**(沿用决策 `20260601-07-task-index-update-not-docs-change.md` 第 32 行字面,`docs/api/` 为自动生成目录禁止手改;API 口径同步留 TASK-501 在实际 route docstring + handler 里落,本 chore 不做)
- **口径锁定**(决策 22 § 1.1 硬约束):
  - ✅ **必须用三件套**:"复现路线图" / "模型搭建副驾" / "参数对应说明"
  - ❌ **禁用词集**:"自动生成 Simulink 模型" / "paper-to-model 一键生成" / "自动生成 .slx" / "AI 生成完整仿真模型" / "成品生成" / "模型成品生成器" 等任何暗示"成品自动生成"的表述
  - ✅ **必须明示 R1 降级三层承诺**(决策 22 § 1.1):稳交付(论文摘要 + 公式 / 参数抽取 + 物理含义 + 模型搭建路线图)/ 尽力交付(`.m` 脚本骨架)/ **不承诺**(打开即跑的完整 `.slx` 成品)
  - ✅ **必须明示资料入口领域**:6 类 `project_type`(`control_system` / `signal_processing` / `power_electronics` / `communication` / `motor_control` / `new_energy`);**`general` 资料入口拒绝**,提示用户选具体类型(决策 22 § 1.5)
  - ✅ **必须明示**:图片中参数需用户补充(MissingParameterPrompt 流程)/ 不承诺运行结果正确 / 不承诺最优调参
- **Codex 完工 R6.1 grep**(覆盖完整禁用词集 + 必用词三件套):
  - 禁用词扫描:`git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器"` 应无命中(除本 task 文档自身的反例引用 + 决策 22 / 宪法历史引用,Codex 报 PM 由 PM 判定)
  - 必用词扫描:`git grep -nE "复现路线图|模型搭建副驾|参数对应说明"` 应在 README + 前端文案至少各命中一次
- **不动**:MCS 工程入口对外口径(MCS 不废弃,沿用既有"工程导览 + 问答"文案)

### 门槛 5 — 评测准入(最小可执行评测样本包)

> **决策 22 § 10.4 字面对齐注**:第 5 项硬门槛字面 = "至少 1 个'资料 → 路线图'样本完整跑通 + 至少 1 个'缺图片参数 → 用户补充 → 输出更新'样本跑通"。"跑通"的实际执行需 TASK-501 PaperPlanService 落地,但**样本数据 + golden expected 输出 + 评分方式必须在 TASK-500 阶段交付完整可执行**,避免本 chore 把硬门槛降级为"TODO 骨架"反向改写决策 22(R1 P0-1 K_31 抓出原 v0.1 漂移)。

- **新建文件**(全部为可执行样本数据,不写功能代码):
  - `eval/cases/paper_to_model/README.md`(评测范围 / 样本组织约定 / 评分流程 / 手工 vs TASK-501 自动跑差异说明)
  - `eval/cases/paper_to_model/material_to_plan/case_01_motor_short_circuit/`:
    - `input/`:1 份电机短路类输入资料(沿用决策 22 § 4 PoC 已实测的 docx 学生实验报告样本;**PM 在 R1 复审通过后提供具体文件**,Codex 落仓)
    - `golden/expected_paper_spec.json`(手工编写,符合 06 § 12 PaperSpec 草稿 schema)
    - `golden/expected_model_generation_plan.json`(手工编写,符合 06 § 12 ModelGenerationPlan 草稿 schema;含 SimPowerSystems 库选型 + 5MW / 平衡节点 / 0.2s 故障 / ode15s / 1s 等 PoC 实测配方)
    - `case_README.md`(说明 case 输入 / 期望输出 / 评分维度)
  - `eval/cases/paper_to_model/missing_param/case_01_missing_image_param/`:
    - `input/`:1 份资料(图片中含关键参数但未被文本抽取)+ `expected_missing_prompts.json`(手工编写的 MissingParameterPrompt 列表)
    - `user_input/user_supplied_params.json`(手工编写的用户补充参数,标注 `source: user_supplied`)
    - `golden/expected_updated_plan.json`(用户补充后期望的 ModelGenerationPlan,带双源标记)
    - `case_README.md`
  - `eval/cases/paper_to_model/scoring_template.md`(评分模板,Markdown;评分维度对齐 roadmap v2 § 8.1:资料解析准确率 / 路线图可用性 / 证据双源区分 / 缺失参数识别 / .m 骨架语法 / 幻觉率)
  - `eval/cases/paper_to_model/verification_method.md`(验收方式说明:本 chore 阶段 = 人工对照 golden vs case_README;TASK-501 PaperPlanService 落地后 = 自动对比 actual vs golden,evaluator 脚本由 TASK-501 实施)
- **架构师 / PM 协作分工**:
  - 架构师产出 golden JSON / 评分模板 / verification_method 骨架(基于 06 § 12 草稿 schema + 决策 22 § 4 PoC 实测结论)
  - PM 提供 1 份真实电机短路类 docx 输入资料(沿用 PoC 样本即可)
  - **missing_param case 可复用同一 PoC docx**(决策 22 § 4 PoC 实测同步发电机报告 docx 有 6 张图片且参数值常在图片里,天然满足 missing_param case 的"图片中含关键参数但未被文本抽取"要求);若该 docx 不满足,PM 需额外提供第二份资料
  - Codex 落仓目录结构 + golden / template 文件;**Codex 不自创 golden 内容**(架构师产出,Codex 仅按字节落仓)
- **样本包交接硬规则**(P1-1 K_36 修订,Codex Stage 0 必查):
  - **Codex 开工前必须收到 PM/架构师提供的样本包**:1 份电机短路 docx + 架构师产出的所有 golden JSON(`expected_paper_spec.json` / `expected_model_generation_plan.json` / `expected_missing_prompts.json` / `user_supplied_params.json` / `expected_updated_plan.json`)+ scoring_template.md + verification_method.md
  - **交接路径**:PM 在派单时通过对话上传样本包文件,或 PM 指定 `handoff/TASK-500/eval_cases/` 本地工作区路径
  - **未提供 → Codex 停手报 PM**,不许 Codex 自创 golden 内容或自填占位
  - **Codex 仅按字节落仓**:把样本包文件按目录结构落到 `eval/cases/paper_to_model/...`,不许改 golden JSON 内容(包括 reformat / 字段重排)
- **不写**:PaperPlanService / evaluator 脚本 / actual 输出(留 TASK-501)

---

## 不做(明确排除)

- ❌ 不落地 `core/domain/paper_*.py` domain dataclass/contract(留 TASK-501)
- ❌ 不落地 `features/paper/*_schemas.py` Pydantic wrapper(留 TASK-501)
- ❌ **不新增 `PaperGraph` schema**(02 v3.0 delta 已列 PaperGraph 占位签名,但本 chore 范围限定为决策 22 § 10.4 五项门槛;PaperGraph schema 字段由后续 schema 演进 task 落地。06 § 12 章节仅保留对 02 PaperGraph 占位的引用说明,不写字段表)
- ❌ 不写 `features/paper/` 任何代码(留 TASK-501)
- ❌ 不写 PDF / docx 解析器(留 TASK-501)
- ❌ 不引入任何新 pip 依赖(PDF / docx 解析库由 TASK-501 评审引入)
- ❌ 不写 PaperPlanService / evaluator 脚本(留 TASK-501;门槛 5 只交付样本数据)
- ❌ 不动 `features/overview/` / `features/explanation/` 任何文件(决策 22 § 5.2 红线)
- ❌ 不动 `core/domain/project_overview.py` / `features/overview/overview_schemas.py` / `core/prompts/project_overview.yaml`(决策 22 § 5.2 红线)
- ❌ 不动既有 04 § 8.1-8.5 字面(zip 沙箱 + zip 测试要求)

---

## 接口契约要点(三套主 schema + EvidenceSource + PaperEvidenceEntry + MissingParameterPrompt 最小字段建议,给 Codex 写 06 § 12 时参考)

> 字段为草稿建议,允许 Codex 实施期微调字段名 / 类型。**字段数超出建议范围**(明显增减)**需在 PR 说明中说明理由并 challenge PM**,但不作为硬失败条件;避免一次性把所有 v0.1 想到的字段都塞进契约,但也不把"草稿未冻结"伪装成隐性冻结(R1 P2-1 反例 K_28b 反思)。真实演进留 TASK-501 走 § 7 D5 流程。

**PaperSpec**(论文 / 报告结构化规格,7-9 字段)
- `paper_title: str`(1-200 字)
- `paper_type: Literal["paper", "report", "thesis"]`
- `domain: Literal[6]`(沿用 6 类 project_type,不含 general;`general` 直接拒绝并提示用户选具体类型)
- `abstract: str`(摘要,1-1000 字)
- `equations: list[EquationEntry]`(0-N,字段:`equation_id` / `latex_or_text` / `paper_section_id`)
- `parameter_table: list[ParameterEntry]`(0-N,字段:`name` / `symbol` / `value` / `unit` / `source: EvidenceSource`)
- `figure_locations: list[FigureRef]`(0-N,字段:`figure_id` / `caption` / `paper_section_id`)
- `pseudocode_blocks: list[str]`(0-N)
- `evidence: list[PaperEvidenceEntry]`(至少 1 个)

**ModelGenerationPlan**(模型搭建路线图,6-8 字段)
- `plan_id: str`
- `paper_spec_id: str`(关联 PaperSpec)
- `library_choice: str`(库选型,如 `"SimPowerSystems"` / `"基础 Simulink"`,1-100 字)
- `block_recommendations: list[BlockRecommendation]`(字段:`block_type` / `purpose` / `paper_reference`)
- `parameter_mapping: list[ParameterMapping]`(字段:`paper_param_name` / `model_param_name` / `value` / `unit` / `source: EvidenceSource`)
- `subsystem_breakdown: list[str]`(子系统拆分建议,3-10 步)
- `m_script_skeleton: str | None`(尽力交付的 `.m` 骨架,可空)
- `evidence: list[PaperEvidenceEntry]`

**TuningSuggestion**(调参建议,5-7 字段)
- `suggestion_id: str`
- `user_scenario: str`(用户描述场景,1-500 字)
- `parameter_directions: list[ParameterDirection]`(字段:`param_name` / `direction: Literal["increase", "decrease", "tune_within_range"]` / `physical_meaning`)
- `expected_effect: str`(预期效果讲解,1-500 字)
- `confidence: Literal["high", "medium", "low"]`
- `evidence: list[PaperEvidenceEntry]`
- `disclaimer: str`(固定提示语,如"建议非保证,需用户在 MATLAB 中验证")

**MissingParameterPrompt**(缺失参数补充提示,5-7 字段)
- `prompt_id: str`
- `parameter_name: str`(论文中提及但未抽到的参数名)
- `paper_reference: PaperEvidenceEntry`(指向论文中出现该参数线索的位置)
- `suggested_unit: str | None`(从上下文推断的单位建议)
- `user_supplied_value: str | None`(用户补充后填入)
- `user_supplied_unit: str | None`
- `source: Literal["user_supplied"]`(恒为 user_supplied,体现双源)

**PaperEvidenceEntry**(论文证据条目,5-6 字段)
- `source: EvidenceSource`(`document_extracted` / `user_supplied` 二选一)
- `paper_section_id: str | None`
- `equation_id: str | None`
- `figure_id: str | None`
- `excerpt: str | None`(原文摘录,document_extracted 时 1-300 字非空;user_supplied 时必为 None)
- `missing_param_prompt_id: str | None`(user_supplied 时必填,关联 `MissingParameterPrompt.prompt_id`;document_extracted 时为 None)

**两套不变量**(06 § 12 必须明示;**禁止跨段冲突**,R1 P1-3 / P1-4 反例 K_30 反思):
- `source = document_extracted`:`paper_section_id` / `equation_id` / `figure_id` **至少一个非 None** + `excerpt` **非 None 非空**(1-300 字)+ `missing_param_prompt_id` 必为 None
- `source = user_supplied`:三个 paper locator **全部为 None** + `excerpt` **必为 None** + `missing_param_prompt_id` **必填关联用户补充流程**(不得伪装成文档证据)

---

## 验收标准

> **PM 验收边界注**(R1 P1-5 反例 K_36):本节验收勾选 = Codex PR 提交 + R6.1 实测达标的标准;PR 通过 PM 合并前 03 索引 TASK-500 标 🔍(等待验收),合并后由 PM 改 ✅ 并解封 TASK-501。Codex 不许直接在 03 索引写 ✅ / 解封字面。

- [ ] 06 末尾新增 `## 12. paper-to-model 输出契约`,含三套主 schema(PaperSpec / ModelGenerationPlan / TuningSuggestion)+ EvidenceSource enum + PaperEvidenceEntry(含两套不变量明示)+ MissingParameterPrompt + 反模式示例(至少 3 个);**所有 schema 标"v0.1 草稿,字段未冻结"**;**保留对 02 v3.0 delta PaperGraph 占位的引用说明**(不写字段表)
- [ ] 06 § 7 修订流程章节追加 paper-to-model 同源路径(占位:`core/domain/paper_*.py` domain dataclass + `features/paper/paper_schemas.py` Pydantic wrapper + freeze test + 06 + schema.json)
- [ ] 04 新增 `### 8.6 文档上传安全(PDF / docx)`,7 子项(a-g)全覆盖;§ 8.5 字面不动
- [ ] 对外口径 R6.1 双向 grep:
  - 禁用词:`git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器"` 应仅在 task-500 文档自身 + 决策 22 / 宪法历史引用处命中;命中其他文件 → 报 PM 由 PM 判定
  - 必用词三件套:`git grep -nE "复现路线图|模型搭建副驾|参数对应说明"` 应在 README + 前端文案至少各命中一次
- [ ] README + API + 前端至少有一处明示 R1 降级三层承诺(稳交付 / 尽力交付 / 不承诺)+ 资料入口 6 类 `project_type` + `general` 拒绝口径
- [ ] `eval/cases/paper_to_model/` 含可执行样本包:README + scoring_template.md + verification_method.md + 1 个 material_to_plan case(含 input 资料 + golden expected PaperSpec + golden expected ModelGenerationPlan)+ 1 个 missing_param case(含 input 资料 + expected_missing_prompts.json + user_supplied_params.json + golden expected updated plan)
- [ ] `tests/fixtures/malicious_documents/` 目录占位 + README(实际 fixtures 留 TASK-501)
- [ ] `docs/03_TASK_INDEX.md` 同步:Week 5+ 段 TASK-500 行新增,标 🔍(等待验收),备注"5 项门槛交付已提交待验收";TASK-501 备注"封禁至 TASK-500 合并 ✅"。**PM 合并后** PM 改 TASK-500 ✅ + 解封 TASK-501
- [ ] R6.1 完工实测命令:
  - **范围实测**:`git diff --name-only origin/main` 改动文件清单仅在以下范围内:
    - `docs/06_OUTPUT_CONTRACTS.md`(改)
    - `docs/04_ENGINEERING_STANDARDS.md`(改)
    - `docs/03_TASK_INDEX.md`(改)
    - `README.md`(改,口径同步)
    - `web/**` 前端文案(改,口径同步;具体文件 Codex 扫描确定)
    - `eval/cases/paper_to_model/**`(新建)
    - `tests/fixtures/malicious_documents/**`(新建占位)
    - 任何范围外文件改动 → Codex 停手报 PM
  - **红线文件未动实测**(对每个红线文件分别跑):`git diff --name-only origin/main -- <redline_path>` 应为空输出;R6.1 报告必须贴这些命令的实际输出
  - 红线文件清单:
    - `features/overview/` 全目录
    - `features/explanation/` 全目录
    - `core/domain/project_overview.py`
    - `features/overview/overview_schemas.py`
    - `core/prompts/project_overview.yaml`
    - `features/explanation/_evidence_builder.py`

---

## 红线(决策 22 § 5.2 + § 5.1,Codex 必守)

- ❌ **不修改** `features/overview/` / `features/explanation/` 任何文件
- ❌ **不修改** `core/domain/project_overview.py` / `features/overview/overview_schemas.py` / `core/prompts/project_overview.yaml`
- ❌ **不修改** `features/explanation/_evidence_builder.py` 既有 EvidencePack
- ❌ **不引入新 pip 依赖**(PDF / docx 解析库待 TASK-501 评审,本 chore 只写规范不引依赖)
- ❌ **paper feature 不 import overview / explanation 私有结构**(决策 21 boundary;本 chore 不写代码,仅在 06 / 04 规范层落实)
- ⚠️ 若 Codex 实施期发现 task 描述与宪法 / 02 / 06 / 04 既有内容冲突 → 停手报 PM(沿用宪法 § 15)

---

## 估时

Codex 实施:1-2 天(纯文档改动 + 目录骨架,不写功能代码)

R 轮:R1(GPT 审决策质量)+ R6(Codex 完工实测自审)+ PM 兜底,1 天

总计:**2-3 天完工**

---

## 工艺(决策 12 v0.4)

- **本任审批级别**:**架构升级类**(契约 + 工程规范 + 对外口径多文件同步,沿用宪法 § 5 二审节点 #1)— R1 + R6 + PM 三道
- **R1**:GPT 审决策质量(挑契约一致性 / 红线落实 / 跨段同步漏)
- **R6**:Codex 完工后实测层(grep 红线文件未动 / git diff --stat 范围 / "自动生成" 全仓扫描)
- **PM 兜底**:PM 直接 review task 文档 + R1 反馈 + R6 报告
- **K_28a 自防**:架构师起稿前已 grep 06 / 04 / 02 / 03 索引现有字面 + EvidencePack / SourceType 既有定义(本 task 文档每条改动都标注现有文件 + 章节锚点)

---

## 给 Codex 的提示

按宪法 § 5 沟通模板。Stage 0 必查:

1. **Base commit 校验**(P1-3 K_30/K_34 修订):PM 派单时提供 base commit hash;Codex 验证 main 含决策 22 v3.0 pivot squash commit + TASK-500 v0.2.1 任务卡(若 v0.2.1 已先期入仓)。若 base commit 漂移或 TASK-500 版本不符 → 停手报 PM
2. `git status` 工作树洁;有 untracked 报 PM 后再开工
3. **样本包到位实测**(P1-1 K_36 修订):验证 PM/架构师提供的电机短路 docx + 全部 golden JSON + scoring_template.md + verification_method.md 已到位(交接路径由 PM 派单时指定);未到位 → 停手报 PM,不许自创 golden 内容
4. grep 验证 task 文档引用的 06 / 04 / 02 / 03 索引现有章节号**当前字面**与 task 描述一致(若 PM merge 期间有变更,以 main HEAD 为准,task 描述按 PM 指令修订)
5. 5 项门槛改动顺序自由,建议:门槛 1 + 2(06 § 12 一锅炖)→ 门槛 3(04 § 8.6)→ 门槛 4(对外口径全仓 grep;**不动 `docs/api/**` 决策 07 红线**)→ 门槛 5(eval 可执行样本包按字节落仓)→ 03 索引同步(标 🔍 等待验收)
6. 每个门槛完工 → `git diff --name-only origin/main` 自审范围 → 下一门槛
7. 全部完工 → R6.1 完工实测三件套:
   - **范围实测**:`git diff --name-only origin/main` 输出在验收标准的范围清单内
   - **禁用词扫描**:`git grep -nE "自动生成|一键生成|生成.*\.slx|完整仿真模型|成品生成|模型成品生成器"` 检查命中合理性
   - **必用词扫描**:`git grep -nE "复现路线图|模型搭建副驾|参数对应说明"` 应在 README + 前端文案至少各命中一次
   - **红线文件未动实测**(逐个跑):`git diff --name-only origin/main -- <redline_path>` 应为空;命令输出贴入 PR 完工 report
8. PR 完工 report 必须按 R6.1 实证,不许凭主观范围声明(决策 12 v0.4 R6.1)

---

**版本**:v0.2.1(R1 复审 conditional pass + 3 P1 + 3 P2 全采纳,2026-06-15)
**作者**:Claude(架构师,接手第 43 任)
**关联决策**:`docs/decisions/20260615-22-direction-pivot-paper-to-model.md` § 10.4
**关联宪法**:v3.0
**关联工艺**:决策 12 v0.4(R1 + R6 + PM)
**入仓**:任务文档单独 PR(沿用既有 chore PR 模式)或合并入决策 22 配套(由 PM 决定);代码改动随后 PR

**修订历史**:
- v0.1(2026-06-15):架构师起稿,2 个 challenge 点待 PM 拍板(EvidencePack 路径 / 上传入口策略)
- v0.1.1(2026-06-15):PM 拍板两项 challenge 全部 = 架构师默认推荐(独立 PaperEvidenceEntry / 独立路由 `/upload-document`);架构师起稿后自审补 2 个漏点:
  - 门槛 2 补 `EvidenceSource` enum + `PaperEvidenceEntry` Python 实现落地路径占位(`core/domain/paper_evidence.py`,TASK-501 落地)
  - 门槛 2 补"PaperEvidenceEntry 与既有 EvidencePack 无包含关系"消费者注意,避免 06 章节被消费者误读为子集
- v0.2(2026-06-15):**GPT R1 第一轮 reject**(3 P0 + 8 P1 + 4 P2);架构师全部采纳,无 challenge,无独立反 challenge;按决策 12 v0.4 R2 公开 challenge 清单工艺累积本任反例:
  - **采纳 15 条 / Challenge 0 条 / 抓出 GPT 反例 0**(本轮 R1 GPT 抓得到位,架构师无可反驳)
  - **R1 P0 三条修订**(决策 22 字面对齐 + 章节号实测):
    - P0-1(K_31 / K_30):门槛 5 从"骨架占位"改为"最小可执行样本包"(交付样本数据 + golden expected + 评分模板,不写功能代码);避免本 chore 局部口径反向改写决策 22 § 10.4 字面
    - P0-2(K_28a):06 现有 § 11 是"版本"章节,04 现有 § 8.5 是"测试要求"章节;凭印象写错章节号 → 改 06 末尾新增 `## 12. paper-to-model 输出契约` + 04 新增 `### 8.6 文档上传安全(PDF / docx)`,全文同步
    - P0-3(K_30):决策 22 § 10.4 字面是"三套契约 + 第 2 项双源",原 v0.1.1 合并成"4 套主 schema"漂移 → 门槛 1 改"三套主 schema",门槛 2 改"MissingParameterPrompt + EvidenceSource + PaperEvidenceEntry 双源契约"
  - **R1 P1 八条修订**:
    - P1-1(K_30):对外口径 grep 命令窄于禁用词集 → 扩展为正则覆盖完整禁用词集 + 必用词三件套双向 grep
    - P1-2(K_28a):依赖审批章节凭印象引用 04 § 13 → 改 § 6 依赖管理
    - P1-3 / P1-4(K_30):PaperEvidenceEntry 字段表跨段冲突 → 改字段类型 + 写两套不变量(document_extracted / user_supplied)
    - P1-5(K_36):03 索引验收混 Codex 阶段与 PM 阶段 → 改 Codex 阶段标 🔍 + 备注待验收;PM 合并后改 ✅ 与解封
    - P1-6(K_36 / K_28a):红线文件未动校验命令 `git log -1` 不成立 → 改 `git diff --name-only origin/main -- <path>` 必须空输出
    - P1-7(K_30):Gate 4 未纳入 R1 降级三层 + general 拒绝 → 门槛 4 + 验收新增三层承诺 + 6 类枚举 + general 拒绝口径明示
    - P1-8(K_30):PaperGraph 未在范围边界明示 → "不做"段加"不新增 PaperGraph schema",06 § 12 仅保留 02 占位引用
  - **R1 P2 四条修订**:
    - P2-1(K_28b):字段数 ±1 隐性冻结 → 改软约束,字段数超出需 PR 说明 + challenge PM,不作硬失败
    - P2-2(K_34):raw 文档"仅存元数据"措辞不精确 → 改"raw 原文不持久化;允许持久化 PaperSpec,但须受长度 / 脱敏 / 来源标注 / TTL 删除策略约束"
    - P2-3(K_34):core/domain Pydantic 措辞混层 → 改"core/domain dataclass/contract + features/paper Pydantic wrapper"分层精确
    - P2-4(K_30):顶部 v0.1 / 底部 v0.1.1 不一致 → 统一 v0.2
  - **本任反例趋势**(本轮 R1 抓出,沿用决策 22 § 9 趋势记账):
    - K_28a 高发(本轮 +3:章节号 § 11 / § 8.5 / § 13 全是凭印象;沿用 41 任 K_28a 高发区警示)
    - K_30 最高发(本轮 +8:跨段同步漏密集 — 三套 vs 四套 / 章节号 / 必填约束 / excerpt 类型 / grep 窄字 / 03 状态语义 / PaperGraph 漏列 / 顶部底部版本号)
    - K_31 +1(门槛 5 局部口径反向改写决策 22 § 10.4)
    - K_34 +2(PaperSpec 称元数据 / core/domain Pydantic 措辞混层)
    - K_36 +2(红线 git log 不成立 / 03 索引越过 PM 验收边界)
    - K_28b +1(字段数 ±1 隐性冻结)
  - **架构师 K_28a 反思**(决策 12 v0.4 § 7.1.3 KPI 12):本任 v0.1 起稿期已 grep EvidencePack / SourceType / 02 占位签名,但**漏 grep 06 / 04 全章节列表**(只 grep § 8 上传安全字段,没 grep 06 § 11 / 04 § 8.5 是否被占用),K_28a 三条全是同源(章节号凭印象),提示自审 grep 范围应覆盖目标文件**完整章节目录**,不只字段层面;v0.5 协议候选第 6 项再添实证(自身前序版本 + 目标文件章节目录均需 grep)
- v0.2.1(2026-06-15):**GPT R1 复审 conditional pass**(0 P0 + 3 P1 + 3 P2);架构师全部采纳,无 challenge;按 R2 公开 challenge 清单工艺累积:
  - **采纳 6 条 / Challenge 0 条 / 抓出 GPT 反例 0 条**
  - **R1 复审 P1 三条**:
    - P1-1(K_36):门槛 5 样本包交接未封装成 Codex 可执行规则 → Stage 0 加"样本包到位实测"硬规则 + 门槛 5 加"交接路径 + 未到位停手 + 仅按字节落仓"
    - P1-2(K_30 / K_36):门槛 4 候选清单含 `docs/api/*` 但 R6.1 白名单未含 + 决策 07 把 `docs/api/` 列自动生成禁止改 → 移除候选清单 + 改"不动 `docs/api/**`",API 口径同步留 TASK-501
    - P1-3(K_30 / K_34):Stage 0 锁死 main = 决策 22 commit,与 task 单独入仓时序冲突 → 改为"PM 派单时提供 base commit;Codex 验证 main 含决策 22 + TASK-500 v0.2.1"
  - **R1 复审 P2 三条**:
    - P2-1(K_30):PaperEvidenceEntry 标题 "4-5 字段" vs 实列 6 字段 → 改 "5-6 字段"
    - P2-2(K_30):上下文 "评测骨架" vs Gate 5 "最小可执行样本包" → 改 "评测样本包",仅 verification_method + scoring_template 称骨架
    - P2-3(K_30 / K_36):missing_param case 复用 PoC docx 未明示 → 加"missing_param case 可复用同一 PoC docx,决策 22 § 4 PoC 已实测同步发电机 docx 含 6 张图片参数;若不满足 PM 提供第二份"
  - **K_28a 自防生效**(本轮 +0,vs v0.2 +3):GPT P1-2 引用决策 07 时架构师先 grep `/mnt/project/20260601-07-task-index-update-not-docs-change.md` 第 32 行字面确认 `docs/api/` 在禁止列表,再据此改 task;实证 K_28a 防御范式(不凭 GPT 引用 / 不凭印象,grep 字面再下笔)
  - **本任反例趋势 v0.2.1 末态**(沿用决策 22 § 9 趋势记账,不再逐位累加):K_30 / K_28a 仍是高发区(累积);K_36 +2(样本包交接 + docs/api 边界)是新触发点,提示文档与决策跨段一致性仍需 grep 兜底
