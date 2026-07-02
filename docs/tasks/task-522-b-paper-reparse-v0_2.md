# TASK-522-B:Paper 重新解析(不重传、原地重跑) · v0.2

> **子线**:TASK-522 解析可信 / 纠错四条(①诚实提示=522-A[对内暂缓] / **②重新解析=522-B[本卡]** / ③用户纠错=522-C[排后] / ④局部重跑=522-D[最后])。①②③④ ↔ A/B/C/D,PM 锁优先级 ①→②→③→④。
> **状态**:v0.2 · **R1(GPT)方案审 + R6(Codex)可落核均已过、P0 已收敛** · **待 Codex Stage 0 确认基线 → 实现**
> **性质**:后端契约卡(加路由 + 加内部存储表 + 补论文数据 TTL 清理 + 动隐私存留)+ 少量前端。走合并前亲核真 diff + decision 13 清单 + 对外零 schema drift;前端走静态 smoke + 走查 + 截图(前端无测试框架)。
> **基线**:R6 @ live `origin/main` `e10cc0a` 实证(见 §3);Codex 起手 Stage 0 复核 live HEAD,以实现为准。

---

## 1. 这张卡是什么 / 不是什么

**是**:给「已解析过的一篇论文」加「**不重传、原地重跑整条解析链**」:用户在结果页点「重新解析」→ 后端用**已存的纯文本解析包**重新抽取 → 全新 spec + plan → **prepare-then-commit 原子替换**旧结果。为此在服务端**临时存论文抽取的纯文本解析包**(原始 PDF/DOCX 仍上传即删)。

**动机**:内测摸「哪些论文会解崩」,解崩多在解析链发挥不稳(AI 这次读岔 / 漏了文字里明明有的东西),「原地重掷一次」是救火按钮。

**不是**:①不重存原始文件(只存纯文本解析包);②不是「只重生成 plan」——**必须从解析包重新抽 spec**(否则救不了参数抽错 / 整篇读岔);③不做③用户纠错 / ④局部重跑;④不长期保存(24h 固定清、真相源=用户本地,方向决策 26 甲);⑤不救「图 / 表第一次就没读进来的信息」(解析器没抓图、重跑补不回,那是解析器升级独立线);⑥不改已合并产物行为(521-A/B1/B2/C/D、追问、MCS、其它后端;改=PM 拍+审)。

---

## 2. 产品决定(PM 已拍 + R1/R6 收敛,本卡不重开)
- 「重新解析」= 不重传、原地整份重跑;临时存纯文本解析包、原始文件仍即删。
- **三道闸**:①**prepare-then-commit 原子替换**(不叠加、失败保旧,见 §4.1);②纯文本随结果清 + **补论文数据 TTL 清理**(见 §4.4);③**24h 固定过期、重跑不续命**(见 §4.5)。
- 隐私:存纯文本解析包非原文件;24h 固定清;绝不跨用户 / 训练;纯文本 / filename / error 不落日志·控制台。
- 对齐方向决策 26 甲:纯文本仅服务端临时存(24h、绑结果),真相源=用户本地课题包(未来工作台,本卡不做、只留可打包+键稳定的口子)。

---

## 3. 现状基线(R6 @ live `e10cc0a` 实证;★ 三个 R6 收敛点已并入设计)
- **抽取 / 解析强耦合在 `extract_uncached` 一处**:`route(file) → run_in_sandbox(parser,file) → 得 parsed(ParsedDocument) → len(raw_text) 闸 → build_messages(parsed) → LLM → _parse_and_validate(response, parsed, ...)`。★ **`raw_text` 不止 prompt 用,还在 `extract_uncached` 做长度闸;确未落库**。
- **★ 仅存 raw_text 不足以严格复现同型抽取**(R6):`build_messages(parsed)` 与 validator 还用 `parsed.figure_placeholders / table_placeholders / locator_index(section_ids/equation_ids/figure_ids)`;`ParsedDocument = {raw_text, page_count, figure_placeholders, table_placeholders, locator_index, file_hash, extracted_at}`;**docx 的 figures/tables 不在 raw_text 里,不能靠 raw_text 重建**。故须存**纯文本解析包**(见 §4.2)。
- **上传编排**:`for upload_index, file: document_id=_document_id_for_upload_index(upload_index); extract_uncached(...)`;失败篇进 `document_statuses(failed + error_code)` + `if primary_index==upload_index: raise`(主篇失败整体失败)+ `continue`(辅篇失败留 DOC gap);`if not successes: raise`;`spec=_fuse_successful_specs(successes, primary_index)` → `plan_service.generate` → `save_ready_bundle`。
- **`_fuse_successful_specs`**:取 representative(有主取主、无主取首个成功)填顶层单值字段;跨成功篇拼 documents/equations/parameter_table/figure_locations/pseudocode/evidence;`with_parameter_conflicts` + `validate_paper_spec_document_identity`。
- **存储**:`paper_spec_cache(paper_id PK, paper_spec_json, created_at, updated_at)` / `paper_plan_cache(paper_id PK, plan_json, missing_prompts_json, missing_bindings_json, created_at, updated_at)`,**无 raw_text 字段**。`save_ready_bundle` 现状 = 先序列化 → 单连接 `BEGIN → UPSERT spec → UPSERT plan → commit`,失败 rollback 不覆盖主异常(已有测试断言双表 rollback)。
- **★ 24h 清不覆盖 paper 表**(R6):`CleanupWorker` 只扫 / 删 `project_status_record`;paper 表无 FK、无自身 sweep。**本卡须补论文数据 TTL 清理**(§4.4)。
- **无 consent 门**(R6):paper 上传链无 consent 字段(对照 bridge 的 `llm_processing_consent_confirmed` schema validator)。
- **并发**:`PRAGMA WAL + busy_timeout=5000`,但 paper store 无应用层锁;写事务是 `BEGIN`(非 `BEGIN IMMEDIATE`);同 paper_id 并发 = last-write-wins,与 user-supply `set_plan` 并发也可能互覆盖。
- **对外 schema**:raw_text 不触碰 `PaperSpec`/`ModelGenerationPlan`/`PaperAskCitation`/`UploadDocumentResponse`,预期零 drift 成立。
- **前端**:`PaperHeader` 有「重新上传」(`<Link to="/paper">`);错误态「重试」=`usePaperResult.retry`=`Promise.all([getPaperSpec, getPaperPlan])` 只重 GET;**web 无 test runner**(vitest/jest/playwright/testing-library/cypress 无命中),只有 build/lint/typecheck + task smoke。

---

## 4. 范围(必须做)

### 4.1 ★ prepare-then-commit 原子替换(P0-1,取代「就地覆盖」)
执行顺序**写死为硬契约**:
```
1. 读旧 bundle + reparse source record + 当前 revision/updated_at。
2. 获取 per-paper reparse lock(§4.6)。
3. 内存中逐篇用 stored source 重抽 spec(§4.3)。
4. 融合成新 spec(复现同一融合,§4.3)。
5. PaperPlanService.generate() 生成新 plan + missing_prompts + bindings。
6. 过公开 wrapper / domain helper / evidence / provenance 校验。
7. 单事务 replace:spec row + plan row + missing/bindings JSON + source metadata(同一 BEGIN 内)。
8. commit 后才向前端返回新 spec + plan。
9. 任一步失败 → 返回错误,旧 bundle 原封不动。
```
- **不得**先删旧记录 / 先写半成品 / 用应用层补偿删除模拟事务。commit 前 GET **永远读旧 bundle**。
- source metadata 更新纳入同一事务,或至少保证「替换 spec/plan 的事务不受 source 更新失败影响」。

### 4.2 ★ 临时存纯文本解析包(P0-2,非裸 raw_text)· 独立内部表
- 新建**内部表** `paper_reparse_source_cache(paper_id PK, source_json TEXT NOT NULL, created_at, expires_at)`(**不塞进 `paper_spec_json` / 对外 DTO**;GET spec/plan 不读、不返、不日志 raw_text;cleanup 级联清晰;未来本地导出按 paper_id 打包)。
  - **R6 若判定扩 `paper_spec_cache` 加 nullable 列更稳**,须同样保证 GET spec 不读 / 不返 / 不日志 raw_text——**默认走独立表**(隔离最干净)。
- `source_json` 结构(per-doc 纯文本解析包):
  ```
  PaperReparseSource{ paper_id, expires_at,
    documents[]{ document_id, upload_index, filename(清洗显示名), raw_text,
                 figure_placeholders, table_placeholders, locator_index,
                 (page_count/file_hash/extracted_at 若复建 ParsedDocument 需要) },
    primary_index(原值,区分 null 无主 vs 显式主),
    source_schema_version }
  ```
- **禁存**:原始 PDF/DOCX bytes / file_path / 沙箱路径 / 未清洗 filename。
- 部分成功 banner 现状不持久化(刷新即无)——**本卡不承诺持久化 statuses**;若将来要在 reparse 后展示 banner 再单议(不在本卡范围)。

### 4.3 ★ 重新解析路由 + 重抽 seam + 融合复现 + 失败篇边界
- **路由** `POST /api/v1/papers/{paper_id}/reparse`:空 body、不收文件;读回 source → 走 §4.1 流程。
- **★ 重抽 seam**(R6):提一个新 service 公开入口(如 `extract_parsed_uncached(...)`),**输入重建的 ParsedDocument(从 stored source)、跳过文件解析、复用 `len(raw_text)` 闸 + build_messages + LLM + _parse_and_validate**;reparse route 无 file_path,**不得从 route 调私有方法**。
- **★ 重抽=重抽 spec 非 plan-only**(P0):新 plan 基于**新 spec** 生成,不复用旧 spec。
- **★ 融合复现**:按 stored `upload_index/document_id/primary_index` 复现同一 `_fuse_successful_specs` 融合(同 DOC 映射、同 primary、维持 gap 与成功顺序);LLM 不产 document_id(后端注入 / 引用桥解析,沿 521 红线);plan provenance 引用桥无法干净落地 → fail-fast、不兜底 DOC-001/primary/None。
- **★ 失败篇不复活**(P0-3):reparse **只重跑已进入 `PaperSpec.documents` 的成功篇**(有 stored source);**原上传失败篇无 source record、不参与、也不偷偷留其 raw_text**(避免扩大隐私存留面);用户要重试失败篇**只能走「重新上传」**。两类失败(解析阶段失败=无 raw_text;raw_text 曾抽出但 spec 失败=未进 bundle 者不留 source)均不 reparse。主篇当初失败=整体失败、无可 reparse bundle。

### 4.4 ★ 闸②:纯文本随结果清 + 补论文数据 TTL 清理(P0,修现状缺口)
- **补论文 bundle TTL 清理**:现有 `CleanupWorker` 不覆盖 paper 表 → 本卡加论文 sweep(扩 CleanupWorker 或新 worker,R6 定):按 `paper_spec_cache.created_at` 找过期 paper_id,**事务内先删 `paper_plan_cache` → 再删 `paper_spec_cache` → 删 `paper_reparse_source_cache`**,无孤儿。
- 手动 `delete_bundle(paper_id)` 同样级联删 source。
- 若 source 挂独立表,随同一清理级联;GET spec/plan 永不加载 source。

### 4.5 ★ 闸③:24h 固定过期、重跑不续命(P0-4,防滑动续命)
- `expires_at = initial_ready_bundle_created_at + 24h`;**reparse 不延长 expires_at**(否则反复点重跑=无限续命=不再「有界」)。
- cleanup 以 `expires_at`(或等价固定 created_at + TTL)为准,删 spec + plan + source 三者。
- **不设比结果更短的独立窗口**(R1 建议):短窗口会造「结果在但不能重抽」的降级态,迫使前后端新增降级文案 + 不稳定行为。**source 与结果同生共死、共同受固定 24h 约束**——满足三道闸(不叠加 / 结果清它清 / 生命周期有界),且无降级态。

### 4.6 ★ 并发语义:per-paper reparse 锁(P0-5,不用隐式 last-write-wins)
- 同 paper_id 同刻只允许一个 reparse;已在重跑 → 第二请求返回 `409/423 reparse_in_progress`、**不启动第二组 LLM 调用**。
- GET spec/plan 在重跑期间返回旧 ready bundle;commit 后返回新 bundle。
- 单进程 per-paper lock;若已有 revision/updated_at 可加 compare-and-swap 防两 worker 互覆盖。多 worker 若暂不支持跨进程锁,R6 标明现状(至少单进程锁)。

### 4.7 前端:重新解析入口 + 确认弹窗 + 状态
- 结果页 header action 区加**「重新解析」入口**,与「重新上传」**并列且语义分开**:重新解析=不选文件、用 stored source 原地重跑;重新上传=回 `/paper` 从头选文件。**错误态「重试」保持现语义(只重 GET),不与 reparse 混。**
- **★ 确认弹窗文案**(P0-6,须写明覆盖已补参数):
  > 重新解析会用同一份论文文字重新抽取并**替换当前结果**;**已补充的缺失参数、当前 plan 和调参结果会被替换**。它只重跑已读入的论文文字;若缺的信息在图片 / 表格里,或某篇上传时就失败,重新解析补不回,需要重新上传或等解析升级。
- **重跑中**:按钮 disabled、二次点击不重复提交;取消(若做)仅前端 `AbortController` 取消请求、不假装取消后端。
- **成功换新**:替换 spec/plan/missing_prompts;页面内旧 ask/tuning 临时结果清空或标「旧解析结果下的回答」。
- **失败保旧**:失败 → 保留旧 spec/plan 不炸、顶部可关错误、可重试。
- **source unavailable(410)**:按钮旁提示「这份结果没有可重跑的临时文字,请重新上传」。

### 4.8 朝工作台预留(方向决策 26 甲,几乎零成本)
- source + spec + plan 结构上是同一 paper_id 下**可整体导出的单元**(未来本地课题包素材);paper_id 保持稳定长期键;纯文本仍「仅服务端临时、24h 清」,**不做服务端长存 / 跨设备**;本卡只保证「可打包 + 键稳定」,不实现导出。

---

## 5. 不做(红线 — 合并前逐条核 RAW)
- 不存原始文件 / 原始 bytes / 沙箱路径;原始 PDF/DOCX 仍上传即删(sandbox `finally rmtree` 仍执行,reparse 不依赖原文件)。
- 不长期保存纯文本(24h 固定清);不做服务端长存 / 跨设备。
- 不改已合并产物行为:`extract_uncached` 现有从文件抽取路径、521-B1 融合对现有上传产出、追问 B1/B2/C/D、B2 参数冲突、MCS、`upload-document` 现有对外行为——reparse 是**新增外层路径**,不改现有产出字节 / 行为。
- 不改对外 paper 输出契约 schema;若触碰任何导出 schema → 停手报架构师(预期零 drift)。
- 不做③④;不把「重新解析」伪装成「重试原始上传包」。

---

## 6. 隐私(锁死)
纯文本解析包仅服务端临时存(24h 固定清、重跑不续命);prepare-then-commit 不叠加;原始文件仍即删;绝不跨用户 / 训练;**纯文本 / filename / LLM raw response / error 正文不落日志 · 控制台 · HTTP error body**(decision 11);A 用户不能 reparse B 用户 paper_id(现无用户身份则至少不新增跨用户可枚举能力);与方向决策 26 甲铁律一致(服务器不长存,真相源=用户本地)。

---

## 7. decision 13 同步清单(R6 起手核实际触碰面 + 贴 diff)
```text
□ 新表 paper_reparse_source_cache 建表 + freeze/迁移测试(或 R6 选加列方案则 ALTER TABLE + 旧行 null 语义)
□ 读回兼容:老 paper 记录(无 source)读回不炸、reparse 返 410;新记录 round-trip 不变;老 spec/plan blob 迁移不受影响
□ 新路由 reparse:请求(空 body)/ 响应(新 spec+plan+missing_prompts 或错误码)+ 契约测试(见 §10)
□ 清理:补论文 bundle TTL sweep(§4.4)+ TTL 测试(过期删 spec+plan+source 无孤儿)
□ 对外 paper 输出 schema 零 drift:make export-schema && make verify-schema 对外零 diff(raw_text 内部、不进对外 DTO/JSON schema/TS 类型)
□ consent:paper 上传链无 consent 门 → reparse 不新建独立 consent 机制;但确认弹窗写明「用临时保存的论文文字重跑」(§4.7)
□ decision 11:reparse LLM 调用走 to_thread(复用现有异步桥、不绕)、禁 logger.exception/str(exc)/repr(exc)/exc_info=True;raw_text/filename/LLM 正文不落日志·console·error body
□ make check 后端全绿 + pnpm typecheck/lint/build + smoke(含 task522b smoke)
```

---

## 8. 关键设计点已定(供实现,不再重开)
1. 重抽=重抽 spec 非 plan-only,经新公开 seam `extract_parsed_uncached` 复用抽取+校验、以 stored source 为输入。
2. 存纯文本解析包(per-doc raw_text + figure/table placeholders + locator_index + upload_index/document_id + primary_index + schema_version),非裸 raw_text,独立表隔离。
3. prepare-then-commit 原子替换,失败保旧,单事务 replace。
4. 失败篇不复活、不留 source,重试失败篇走重新上传。
5. 24h 固定过期、重跑不续命;补论文 TTL 清理(修现状缺口)。
6. per-paper reparse 锁,409/423 拒并发。

---

## 9. Stage 0 gate(Codex 实现前核 live,不符停手报架构师、禁兜底硬上)
基线用 `origin/main`(git fetch 后最新真值)。核:①live HEAD(仍 `e10cc0a` 或已移动但 521-A/B1/B2/C/D 全在、§3 假设仍成立);②§3 六个现状点仍符(抽取/解析耦合形状、纯文本解析包所需字段、24h 清未覆盖 paper 表、无 consent 门、并发无锁、对外零 drift)。逐条报核对结果,基线通过才动手。任一不符 → 停手报架构师先诊断。

---

## 10. 验收标准(命令以 Stage 0 实测为准;收敛 R1 26 条断言的关键项)
**后端契约 / 状态**
- [ ] 原子替换:fake provider 让第 2 篇 LLM 抽取失败 → reparse 后 GET spec/plan 返回旧 bundle 字节级不变、row updated_at 不变。
- [ ] 成功替换:upload 生成 A、reparse 生成 B → 成功后 GET 返回 B;paper_id 不变;row 数不增(闸①不叠加)。
- [ ] commit fault:replace 事务第 2 写入点注入 SQLite fault → rollback,旧 spec/plan/source 全保留,无 plan-only/spec-only 异常态。
- [ ] GET 交错:reparse 生成中 GET 返回旧 bundle;commit 后返回新。
- [ ] 并发:同 paper_id 两 reparse 并发 → 第二返回 409/423、不启动第二组 LLM。
- [ ] source unavailable:老记录无 source → POST reparse 返回 410、不调 LLM。
- [ ] fixed TTL:reparse 不延长 expires_at;时间推进过 expires_at 后 source/spec/plan 均被清或逻辑失效。
- [ ] cleanup cascade:手动 delete_bundle 或 TTL 清后 source 表无孤儿。

**重抽 / 融合**
- [ ] 重抽 spec 非 plan-only:fake provider 让 reparse spec 参数值变 → 新 plan 基于新 spec。
- [ ] validator seam:reparse 与 upload 同一抽取+校验路径,无「无 locator 校验」shortcut。
- [ ] LLM 不产 document_id;plan provenance 引用桥仍生效、无法解析 fail-fast 不兜底。
- [ ] multi-doc partial:原传 3 篇第 2 失败 → bundle 只 DOC-001+DOC-003;reparse 只重跑这两、不尝试 DOC-002、保持 gap。
- [ ] primary preservation:原 primary=DOC-003 → reparse 后仍 DOC-003;无主仍 None、不折叠首篇。

**前端**
- [ ] 确认弹窗文案含「当前结果+已补参数+plan+调参被替换」「图/表未读入信息不因重跑补回」「上传即失败的篇需重新上传」。
- [ ] loading + 禁二次提交;失败保旧结果 + 可关错误 + 可重试;成功换新;410 提示「无可重跑文字、请重新上传」。
- [ ] 无前端测试框架:pnpm typecheck/lint/build + 静态守卫 smoke + 走查 + 关键态截图(桌面+移动:结果页含重新解析入口 / 确认弹窗 / 重跑中 / 重跑成功换新 / 重跑失败保旧 / 410 source 不可用)。

**隐私 / 日志**
- [ ] grep 守门:生产代码无 `logger.exception`/`str(exc)`/`repr(exc)`/`exc_info=True`;raw_text/filename/LLM raw response 不进日志·console·error body(逐项确认字段名命中不在这些位置)。
- [ ] raw source 最小性:source 表不含 file_path/原始 bytes/沙箱路径;只纯文本解析包。
- [ ] 同 paper reparse 100 次,source 行数不增;原文件即删回归(sandbox rmtree 仍执行、reparse 不依赖原文件)。

**收尾**
- [ ] make check / pnpm typecheck·lint·build / smoke 绿;`git diff --name-only origin/main` 落点符合(后端 store+route+service+cleanup + 少量前端 + 任务卡,无对外契约 schema drift);任务卡随代码同 PR 入仓,索引收尾单独 PR。

---

## 修订历史
- **v0.1(2026-07-02)**:据 R6 @ `e10cc0a` 取证起草;PM 拍产品决定;多篇融合复现 + 解耦 + 闸③取舍列为待审点。
- **v0.2(2026-07-02)**:收敛 R1 6 P0(prepare-then-commit 原子替换 / 纯文本解析包非裸 raw_text / 失败篇不复活不留 source / 24h 固定不续命 / per-paper 锁拒并发 / 确认弹窗写明覆盖已补参数)+ R6 三收敛点(raw_text 兼做长度闸且未落库 / build_messages+validator 需 figure·table·locator 故存解析包 / 24h 清未覆盖 paper 表故补论文 TTL 清理)+ 独立内部表 `paper_reparse_source_cache` + 错误码分类 + decision 13 清单 + 26 条验收关键项;**待 Codex Stage 0 确认基线 → 实现**(卡随代码同 PR、索引收尾单独 PR)。
