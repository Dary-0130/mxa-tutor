# TASK-521-C: Paper 多文件 · 问答出处标到篇(对外)(v0.2 · 双审收口 · 可派单)

## 状态
🔲 **v0.2**（R1 方案审[条件通过·A2/B1/C1] + R6 可落性核[可落·无停手点] → 锁三裁决 + 写硬 6 条 P0 gate + 采纳 R1 精确契约 → **派单/开工**）。
> 动对外契约（`PaperAskCitation` / `paper_ask_response.schema.json` / TS）。**对外 schema 是「有意改」（新增两个 optional nullable document 字段）、非零 diff**：走 decision 13 全清单 + freeze/export 更新到新形状 + **合并前架构师亲核后端真 diff + 对外 schema diff（确认改动仅限新增两个可空字段、无其它对外偏移）**。前端走截图视觉过目（四态）。

---

## ★ 三裁决已锁（R1 裁 + R6 核事实一致）

| 裁决点 | 锁定 | 依据 |
|---|---|---|
| **A** 对外露哪些 document 字段 | **A2：`document_id` + `document_label` 两个扁平字段** | R6：现状 `document_label` 已带 `DOC-00x` 前缀，同名 `model.pdf` 不撞；但 label 是展示名（可重名/清洗/截断），不该当程序 key。`document_id` 作稳定 key（分组/消歧/将来文档锚），LLM 不产、后端注入、链路干净。 |
| **B** 单篇不标篇归属 | **B1：后端始终如实填，前端按 `documents.length > 1` 决定显示** | DTO 表达出处事实、不表达展示策略；`null` 保留给「无文档来源/不适用」（补参/缺参），单篇填 null 会混淆「来自唯一文档但 UI 不显示」与「不来自文档」。R6：渲染点现无 documents，需新接一小段数据流（`PaperResultPage` 已有 `data.spec.documents`）。 |
| **C** 喂 LLM payload 带不带 document | **C1：不带；必须把 LLM payload 与对外 citation 构造解耦** | LLM 只按 `source_id` 选、不需 document；prompt 零变动=不必重跑 ask 行为 eval；避免诱导 LLM 在自由文本 answer 复述篇名。R6：payload 现状 = `from_domain(entry.to_citation())`、确实耦合，可干净解耦。 |

**裁决 D（无争议）**：`user_supplied` / 剩余缺参 citation 的 `document_id`/`document_label` = `null`（内部本就 None）；`source_kind` 前端已用 badge 区分 → 补参 citation **天然不显示篇**。

---

## ★★ 6 条 P0 实现 gate（R1 定，必须在实现/亲核锁死）

1. **C 解耦失败 → document 泄进 LLM payload**（本卡最大风险）：`_source_table_entry_payload()` **不得复用完整 `to_citation()` 结果**；新增独立 payload builder，白名单固定 `source_id/label/excerpt/source_kind/target`；**单测断言 prompt source table 不含 `document_id`/`document_label`/`filename`**。
2. **schema 误把新字段加入 required** → 破坏旧客户端/旧 sample：新字段 optional+nullable，`required` 列表零变化；**freeze 必须测「字段缺失可读」**。
3. **单篇显示篇标 / 多篇不显示篇标**：前端必须拿 `documents.length > 1`，**不得从 citation 局部猜**（即使多文档项目某次回答只引一篇，仍标篇）。
4. **filename/document_label 落日志**：`document_label` 只展示；payload/answer/log/error/console 路径全 grep；不新增 source_table/payload/answer/raw response 日志。
5. **对外 diff 越界**：合并前架构师亲核 `paper_ask_response.schema.json` diff——只新增两个 optional nullable 字段；`target` union / `fallback_reason` enum / `required` / 既有字段约束**零变化**。
6. **`user_supplied` / 剩余缺参被错误标篇**：这些 citation 的 document 必须 `null`；**不得因其 target 可跳到某参数行就补 document**。

---

## 1. 是 / 不是
**是**：把每条 PaperAsk citation 标清「来自你上传的哪一篇文档」——
- 对外 `PaperAskCitation` + `paper_ask_response.schema.json` + `paperTypes.ts` 加 `document_id` + `document_label`（A2）。
- `SourceTableEntry.to_citation()` 透传已有的 `document_id`/`document_label`（现留内部、注释「stay internal until 521-C」→ 本卡放开）。
- **喂 LLM 的 source payload 解耦、不带 document（C1）**。
- 前端 `CitationChip` 展示篇来源，**显示纯文件名（用户上传的名字，不带 `DOC-00x` 内部前缀）**；单篇不显示（B1）；补参不显示（D）；重名文件用 `document_id` 轻量消歧。
- **LLM 不产 document**：source table 每条已由后端绑定 document（B1/B2 注入），LLM 只按 `source_id` 选，`citations = [entry.to_citation() for entry in selected_sources]` 本就从 selected ENTRY 造、非 LLM 输出。

**不是**：
- ❌ 参数值冲突展示（已在 521-B2）；❌ 多选上传 UI / 主文献勾选 / 部分成功提示 → 521-D。
- ❌ 改内部 source_table 收录范围（B1/B2 已定、不变）；C 只把**已有** document 维度对外露出。
- ❌ LLM 产/改 `document_id`；综合多篇无单一出处 → 不挂假 citation、不伪造 `DOC-ALL`。
- ❌ filename 落日志。
- ❌ 改 `target` union / `fallback_reason` enum / `paper_ask_request.schema.json`；动 target resolve / fallback 逻辑；碰 PaperSpec / parameter_conflicts / 冲突展示链 / plan provenance 引用桥。

---

## 2. 产品决定（PM 已拍，不重开）
- 每条出处**标到篇**；**单篇不标、多篇才标**；用户手动补的参数出处**不标篇**。
- （展示形态）问答出处显示**干净文件名**（不带内部编号），重名才加区分 → PM 视觉过目时确认。

---

## 3. 范围（必须做）

### 3.1 对外 DTO 加 document 字段（A2）
- [ ] `core/domain/paper_ask.py`：`PaperAskCitation` **末尾追加**（减 freeze diff 噪音）`document_id: str | None = None`、`document_label: str | None = None`。
- [ ] `features/paper/paper_ask_schemas.py`：`PaperAskCitationModel` 加对应两字段（默认 None）+ `from_domain`/`to_domain`。
- [ ] `schemas/paper_ask_response.schema.json`：加两字段（**optional + nullable、不进 required**）。

### 3.2 透传 + payload 解耦（C1）
- [ ] `SourceTableEntry.to_citation()`：透传 `document_id`/`document_label` 到 `PaperAskCitation`。
- [ ] **新增独立 LLM payload builder**（替代 `_source_table_entry_payload()` 复用 `to_citation()`）：白名单显式 `source_id/label/excerpt/source_kind/target`；**不含 document**。（比 `exclude={...}` 更稳——后续 citation 再加字段不会自动泄进 prompt。）

### 3.3 单篇/多篇 + 展示纯 filename（B1 + D）
- [ ] 后端如实填 document（有 document_id 就填）；补参/缺参 = null。
- [ ] 前端：`showDocumentLabel = documents.length > 1`；display if `showDocumentLabel && citation.document_label`；`source_kind == user_supplied` 或 `document_id == null` **永不显示**。
- [ ] **展示纯文件名**（不带 `DOC-00x` 前缀）：⚠ 现状 `_document_label` = `f"{document_id} - {filename}"`（带前缀）。**Codex Stage 0 核最干净落点**——(a) 对外 `document_label` 取 `document.filename`（纯）；或 (b) 前端用 `document_id` 从 `documents` 查 `document.filename` 展示。任一皆可，标准 = 用户看到纯 filename、重名用 `document_id` 消歧（如 `model.pdf · DOC-002`，平时只显 filename）。**核 `SourceTableEntry.document_label`（带前缀）有无其它内部消费者，改动别波及。**

### 3.4 前端展示
- [ ] `web/src/lib/paperTypes.ts`：`PaperAskCitation` 加 `document_id?: string | null`、`document_label?: string | null`（只读镜像，按 optional 处理）。
- [ ] 数据流：`documents`（或 `documentCount`）从 `PaperResultPage`（有 `data.spec.documents`）→ `PaperAskPanel` → `CitationChip`。
- [ ] `CitationChip.tsx`：新增 `showDocumentLabel` prop（调用方从 `documents.length > 1` 算）；**CitationChip 不自行请求数据、不自行推断文档数**；重名 `document_label` 用 `document_id` 轻量消歧；**复用现有设计系统**（#2c2c2c / 信号橙 #e85d3a / IBM Plex + 思源黑 / border-radius:0）。
- [ ] 不改 citation 可点性 / target 跳转（document 仅附加展示）。
- [ ] 截图（桌面 + 移动、**四态：单篇无篇标 / 多篇有篇标 / 补参无篇标 / 重名 label 消歧**）作图片附件给 PM。

### 3.5 schema / freeze / eval / TS 同步（decision 13；★ 对外 schema 有意改、非零 diff）
- [ ] `paper_ask_response.schema.json` 加两字段；`make export-schema` + `verify-schema` = **更新到新形状后零 drift**（非旧形状零 diff）。R6：`export_paper_schemas.py` 本身大概率不改、只重跑；`Makefile verify-schema` 已覆盖 `paper_ask_response.schema.json`。
- [ ] freeze（`test_paper_schemas_freeze.py`）：`PaperAskCitationModel` 字段顺序 + required-vs-nullable + **三态 round-trip**：字段缺失可读 / 字段为 null 可读 / 字段有值 round-trip。
- [ ] sample roundtrip（`test_paper_schemas_sample_roundtrip.py`）+ eval golden：ask 响应加 document 维度 case——多篇 citation 带篇 / 单篇 null / 补参 null。
- [ ] **越权测试**（R1）：构造 LLM 输出含越权 document 字段或非 `S?` citation id → 仍按既有 malformed/fallback 处理；结构化 document 只从 selected `SourceTableEntry` 来（不加正文级篇名查杀 guard）。
- [ ] `pnpm typecheck` / lint / build 绿；前端控制台干净。

### 3.6 工程守则
- [ ] decision 08 原始字节/行尾；decision 11 **filename/document_label 不落任何日志**、不 `logger.exception`、前端控制台干净；decision 21 跨层经 core 公开契约。
- [ ] `docs/06_OUTPUT_CONTRACTS.md` §12.8（PaperAskCitation 对外形状）加 document 维度 + 「标到篇」语义。
- [ ] **不回退 B1/B2 不变量**：document_id 后端注入·LLM 不产；同名多源不 dedupe；**B2 `parameter_conflicts` 链零 diff**（C 只碰 ask，不动 `PaperSpec.parameter_conflicts`/检测 helper/generate 净化 guard/`ParameterConflicts` UI；R6 已确认 ask 文件无冲突链命中）。

---

## 4. 接口契约（本卡增量 · R1 精确版）

### `PaperAskCitation` 增量
```
document_id?: string | null
document_label?: string | null
```
**语义**：
- `document_extracted` 且来自某篇文档：后端填对应 `document_id` / `document_label`。
- `user_supplied` / 剩余缺参 / 无单一文档来源：`document_id = null`, `document_label = null`。
- 单篇项目后端**仍如实填**；前端按 `documents.length > 1` 控制显示。
- `document_label` **仅展示、不作 key、不落日志**（展示纯 filename）。
- `document_id` 是稳定程序 key，可用于分组 / 消歧 / 未来文档锚点。

### C 实现硬约束
```
_source_table_entry_payload() 不得复用完整 to_citation() 结果。
新增 LLM payload builder，显式白名单 source_id/label/excerpt/source_kind/target。
单测断言 prompt source table 不含 document_id/document_label/filename。
```

### 前端硬约束
```
CitationChip 新增 showDocumentLabel prop；调用方从 PaperSpec.documents.length > 1 计算。
CitationChip 不自行请求数据、不自行推断项目文档数。
展示纯 filename（不带 DOC-00x 前缀）；duplicate document_label 时用 document_id 轻量消歧。
```

### 不变量（对外契约）
- 两字段 optional、不进 required → 向后兼容（旧客户端忽略、旧 blob 缺字段可读）。
- 除新增两字段外，`PaperAskCitation` / `paper_ask_response.schema.json` 其它字段、`target` union、`fallback_reason` enum、`required` 列表**零变化**。
- LLM 不产 document；喂 LLM payload 不含 document。
- 补参/缺参 document = null；综合无单一出处不挂假 citation、不伪造 DOC-ALL。

**B-i blast radius（R6 实测，实现期逐一同步）**：`core/domain/paper_ask.py` · `features/paper/paper_ask_schemas.py` · `schemas/paper_ask_response.schema.json` · `docs/06_OUTPUT_CONTRACTS.md`(§12.8) · `test_paper_schemas_freeze.py` · `test_paper_schemas_sample_roundtrip.py` · ask service tests(`tests/api/test_paper_ask.py`) · `features/paper/paper_ask_service.py`(`to_citation()` 透传 + payload 解耦) · `web/src/lib/paperTypes.ts` · `PaperResultPage.tsx`(传 documents) · `PaperAskPanel.tsx` · `CitationChip.tsx`。（`export_paper_schemas.py` 大概率只重跑不改。）

---

## 5. 验收（可跑命令 + 贴证）
**后端**
- [ ] 多篇上传 → 每条**来自论文**的 citation 带 `document_id` + `document_label`；单篇 → 仍如实填（前端不显示）。
- [ ] 用户补参 / 剩余缺参 citation → document = null。
- [ ] **payload 断言**（P0-1）：`prompt_source_table` 不含 `document_id` / `document_label` / `filename`。
- [ ] **越权**：LLM 输出含越权 document 字段或非 `S?` id → malformed/fallback；结构化 document 只从 selected entry。
- [ ] `make export-schema` + `verify-schema` 零 drift（新形状）；`paper_ask_response.schema.json` 含两字段（optional）、`required` 未变。
- [ ] **freeze 三态**：字段缺失可读 / null 可读 / 有值 round-trip；旧 ask 响应 blob（无 document 字段）读回不炸。
- [ ] `make check` 全绿（含 eval golden 新 case）。
- [ ] **filename/document_label 不落日志**：grep ask payload/answer/log/error 路径无 document_label/filename 输出。

**前端**
- [ ] 多篇 → CitationChip 显示纯文件名；单篇/补参 → 不显示篇；重名 → `document_id` 消歧。
- [ ] citation 可点性 / 跳转不变。
- [ ] 复用设计系统；`pnpm typecheck`/lint/build 绿；控制台干净。
- [ ] 截图四态（桌面+移动）作图片附件给 PM。

**收尾**
- [ ] `docs/06` §12.8 同步；decision 13 全清单逐项在 PR 说明列。

---

## 6. 风险与注意点
**P0（见上「6 条 P0 gate」，此处补语境）**
1. C 解耦失败 document 泄 payload（最大）——独立 builder + 断言锁。
2. schema 误加 required——freeze 测缺字段可读。
3. 单篇/多篇篇标错——前端拿 `documents.length > 1`、不局部猜。
4. filename/document_label 落日志——全路径 grep。
5. 对外 diff 越界——合并前亲核 schema diff。
6. 补参/缺参错误标篇——document 必须 null。

**P1**
1. 重名 `document_label` 前端消歧（`document_id`）。
2. `document_id` 只作程序 key、不作展示主要文案。
3. C 只动 ask，B2 冲突链零 diff（亲核确认）。

---

## 7. PM 接触（已拍 + 一处视觉过目）
- **已拍**：每条标到篇；单篇不标、多篇才标；补参不标篇。
- **唯一剩余 PM 接触 = 视觉过目**：前端篇标做出后，Codex 出截图（桌面+移动、四态），PM 瞄一眼「好不好看 / 纯文件名展示行不行」（视觉级，PM 定）。
- 其余（三裁决字段边界/单篇归属/payload 解耦、schema churn、向后兼容、展示落点）= 实施形状，双审已收口，不烦 PM。

## 8. 给 Codex 的提示（派单实现阶段）
- **Stage 0（实现前，可落性 gate）**：live origin/main HEAD、从 live 切新分支。R1 点名实测两件事 + 展示落点：
  - **① `CitationChip` 渲染链能否拿到 `PaperSpec.documents.length`**；拿不到就加数据流（`PaperResultPage` → `PaperAskPanel` → `CitationChip`），**不改后端单篇 null 策略**。
  - **② `_source_table_entry_payload()` 与 `to_citation()` 的真实复用点怎么拆**；**拆不开就停手报架构师、不能把 document 泄进 prompt 后硬上**。
  - **③ 展示纯 filename 落点**（§3.3）：对外 label 取 `document.filename` vs 前端查 documents；核 `SourceTableEntry.document_label` 带前缀值有无其它内部消费者。
  - 核卡在 `docs/tasks/`、schema/freeze/export 更新点、ask 日志路径（filename 不落）。**高风险落不下来停手报架构师、禁兜底硬上**（沿 B1/B2 gate 做法）。不符即停（decision 15）。
- **后端**：两字段进 domain + model + schema.json（末尾追加、optional）；`to_citation()` 透传；**独立 payload builder（不含 document）+ 断言**；对外向后兼容（required 零变化、target/fallback enum 不动）。
- **前端**：TS 镜像（只读、optional）+ 数据流 + `showDocumentLabel` prop + 纯 filename 展示 + 重名消歧；不改可点性/跳转；复用设计系统；截图四态作图片附件给 PM。
- **红线**：LLM 不产/不改 document；filename/document_label 不落日志；不伪造无出处 citation、不 DOC-ALL；不改 source_table 收录范围；不回退 B1/B2 不变量（含 B2 `parameter_conflicts` 链零 diff）。
- 完工三件套 + decision 13 全清单逐项在 PR 说明列；**任务卡随代码一并 add 进同一代码 PR、索引收尾走单独 PR**（decision 07）；子卡完工 521 整数**不 +1**（维持 20/21、51/54）。
- 本机无 `grep`，用 `git grep`/`rg`/`Select-String`；行尾/字节（08）；异步/日志（11）。
- **合并前架构师亲核后端真 diff + 对外 schema diff（确认仅新增两个可空字段、无其它对外偏移）；前端部分走截图四态视觉过目、不走后端 schema 重关。** 合并前 RAW 要本体不要行号。

**修订历史**：v0.1（draft-ahead 起稿，抛 A/B/C 三裁决点）→ **v0.2**（R1 条件通过[A2/B1/C1] + R6 可落无停手 → 锁三裁决 + 写硬 6 P0 gate + 采纳 R1 精确契约/约束文字 + 展示纯 filename + R6 blast radius → 派单）。
