# TASK-521-D: Paper 多文件 · 前端上传界面(多选 + 主文献勾选 + 文件来源展示 + 部分成功提示)(v0.2)

## 本版改动(v0.1 → v0.2;并 R1=GPT 方案+护栏审「条件通过」+ R6=Codex 真 repo 可落核;无新产品决定;唯一 PM 接触仍 = §7 单篇是否走待传确认态)

**R6 真 repo 纠正的两处事实(架构师采纳 R6 真值,覆盖 v0.1 / R1 假设):**
- ★ 资料上传页实际用 **`PanoramaScene`**,不是首页的 `UploadScene`(v0.1 现状基线写错,已改)。
- ★ **error_code 实际只吐三个码**(见 §3 / §4.4):`document_parse_failed`、`paper_spec_generation_failed`、`document_processing_failed`(兜底,当前路径基本不吐)。R1 拟的通用码草案(unsupported_file_type / invalid_file_signature / …)**作废**——`unsupported_document_format` / `document_too_large` 等在 per-doc status 里**被折叠成 `document_parse_failed`**;主篇失败 / 全失败 / primary_index 越界 / 超 5 篇是**整体请求失败、无 document_statuses**。前端映射按真实三码 + unknown 兜底。

**R6 落点事实(v0.2 据此把范围从「改 PaperDropzone」升为「三处结构改」):**
- 现状 `PaperUploadPage` 状态机只有 `idle/dragging/uploading/failed`、全是单 `file`;`PaperDropzone` 取 `files.item(0)`;需新增「已选未传」队列态 + 队列 / 确认组件,`PaperDropzone` 改成只负责选 / 拖 `File[]`。
- 现状 `apiUploadTask(path, file, onProgress)` 写死单文件 FormData;新增 **`apiUploadFormTask(path, formData, onProgress)`**(不改单文件版,护 MCS 工程 zip 的 `/upload` 调用)。XHR `upload.onprogress` 对多文件成立、但是 **multipart 总上传进度、非逐篇解析进度**。
- 现状上传成功 `navigate(/paper/:id, { state: response })`,但 `usePaperResult` 的 `PaperResultData` 丢掉 `document_statuses`(只留 spec/plan/missingPrompts);直达 / 刷新只 GET `/spec` + `/plan`、拿不到 statuses。→ `PaperResultData` 加 `documentStatuses?`,从 `location.state` 带。
- `PaperHeader` 现展示标题 / 摘要 / tags / 重新上传按钮;来源清单放 tags 后。
- 后端上限 `MAX_PAPER_UPLOAD_FILES = 5`;现有 `validatePaper(file)` 单文件、需升 per-file;`errorMessages.ts` 缺 `paper_spec_generation_failed` / `document_processing_failed` 中文映射、需补。

**R1 补硬(架构师并入):**
- 补 12 个状态(空态 / 混合非法 / 重复文件 / 追加 / 移除主文献不提升首篇 / radio toggle 语义 + 键盘可操作 / 上传中冻结 / 失败回待传 / input value reset / 单篇回归 / **原始多篇但只成功一篇** / 刷新语义)。
- ★ **primary_index 只在 submit 派生**:UI 状态存 `primaryLocalId | null`(不存 index);提交瞬间从 valid snapshot 算 index;`localId` 做 React key(不用 index / filename);invalid 文件不参与 index。
- ★ **原始多篇但只成功一篇**:来源展示判定用 `document_statuses.length` 而非 `spec.documents.length`——原始多篇即使 `spec.documents.length===1` 仍显 compact「已读取 X/N + 失败篇」;仅**原始就是单篇**(两者皆 1)才省略噪音。
- error_code allowlist + unknown fallback 结构(码值用 R6 真三码)。
- 部分成功 banner 以 `document_statuses` 为真值(N=总数、X=失败数),失败篇绝不进 source / plan / prompt;主文献标记只读 `spec.primary_document_id`。
- **测试适配**:R1 期望的组件 / e2e / 单元测试与项目现状「前端无测试框架」冲突 → 降级为「关键纯逻辑(primary_index 重算)抽纯函数 + 静态守卫 smoke + Codex 手动走查 + 九态截图」作为验收证据(见 §8)。

## 状态
🔲 v0.2(已并双审「条件通过」,无升 R2,无新产品决定)→ **派 Codex 实现**;Stage 0 复核 live + §3 现状逐条比对,若发现须改后端 / schema 或须改 C 的 citation 可点链 / B2 冲突链 → 停手报架构师(decision 15)。纯前端卡,**无后端 schema diff、合并走截图视觉过目 + typecheck/lint/build + smoke**(不走后端六组亲核)。

## 1. 这张卡是什么 / 不是什么

**是**:多文件子线**最后一张**、**纯前端**卡。把现有「单篇即时上传」改成:多选上传(PDF/DOCX)+ 上传前指定主文献(可选、toggle 语义)+ 结果页展示「由哪几篇组成」(标主)+ 部分成功提示(哪篇没读成)。后端**零改动**(入参 / 状态 / 来源结构已在 521-A/B1/C 全落,见 §3)。

**不是**(明确排除):
- ❌ 任何后端 / schema / route / PaperAsk / B2 冲突链改动(纯前端;若必须动 → 停手报 PM)。
- ❌ 值冲突展示(B2 已落)/ 交互式裁决 / 上传后改主文献(后端只在上传时收 primary_index)。
- ❌ 改追问链 CitationChip 可点性 / target 跳转 / 高亮(保持 C 行为)、B2 参数冲突区(无采用 / 合并 / 裁决按钮)、MCS 页(工程 zip / 导览 / chat 零 diff)。
- ❌ 碰工程文件 / 表格 / 代码类。
- ❌ **引入前端测试框架**(沿用静态守卫 smoke;R1 的组件 / e2e 期望按 §8 适配)。

## 2. 产品决定

**已锁沿用(PM 已拍,不重开)**:多文件=多篇文档(PDF/DOCX);一主多辅、主文献可选;主文献=主次身份非可信度权重;「每文件后可点框、点=主、不点=无主」;filename 仅展示不落日志、展示纯 filename。
- ★ **主文献交互 = toggle 语义**(非原生 radio):点某篇=主、再点同篇=取消为无主、最多一篇为主;**键盘可操作 + aria 文案**(避免鼠标能取消、键盘不能的状态分裂)。

**本卡待 PM 表态(§7 一句知会,非拍)**:单篇是否也走「待传确认态」,还是保留「选完即传」。v0.2 **倾向单篇也走确认态**(设主标记对单篇隐藏);若 PM 要短路,单篇直传(可切换,不阻塞派单)。

## 3. 现状基线(取证 @ live origin/main `31c23ce`;起草 Codex 须 Stage 0 复核 live HEAD)

**后端(全就绪,零改动)**:
- `POST /api/v1/upload-document`:`file: list[UploadFile]` + `primary_index: int|None`(optional form)。后端按上传序分配 DOC、映射 primary_index → primary_document_id(不给=None);越界 / 非法 4xx;**上限 `MAX_PAPER_UPLOAD_FILES = 5`**。
- 响应 `UploadDocumentResponse`:`{paper_id, spec, plan, missing_prompts, document_statuses}`;`spec.documents:[{document_id, filename}]` + `spec.primary_document_id: str|null`;`document_statuses:[{document_id, filename, status:"succeeded"|"failed", error_code: str|null}]`。
- ★ **per-doc error_code 实际三码**:`document_parse_failed`(折叠了不支持格式 / 超大 / 解析失败等)、`paper_spec_generation_failed`、`document_processing_failed`(兜底、当前基本不吐)。整体失败(主篇 / 全失败 / primary_index 越界 / 超 5 篇)**无 document_statuses**。
- 部分成功语义(后端已实现):指定主篇且主篇失败 → 整体失败;辅篇失败但整体成功 → 用成功篇生成、statuses 报失败篇;未指定主篇且全失败 → 整体失败;未指定主篇且 ≥1 成功 → 继续、primary_document_id=None;primary_index 越界 → 4xx。
- filename 是后端已清洗显示名;error_code 脱敏。

**前端现状**:
- ★ 资料上传页用 **`PanoramaScene`**;`PaperUploadPage` 状态机 `idle/dragging/uploading/failed`、全单 `file`;`PaperDropzone` 取 `files.item(0)`、input 无 multiple。
- `apiUploadTask(path, file, onProgress)` 写死单文件 FormData(`append("file", file)`);MCS 工程 zip 走 `/upload` 也用它。
- 上传成功 `navigate(/paper/:id, { state: response })`;`usePaperResult` 的 `PaperResultData` **只留 spec/plan/missingPrompts、丢 document_statuses**;直达 / 刷新只 GET `/spec` + `/plan`。
- `PaperResultPage` 已把 `spec.documents` 传给 `ParameterConflicts` + `PaperAskPanel`(C 落);`PaperAskPanel` 按 `documents.length>1` 决定篇标(单篇不显)。
- `PaperHeader` 展示标题 / 摘要 / tags / 重新上传按钮、**无 documents 清单**。
- `validatePaper(file)` 单文件(扩展名 + 50MB);`errorMessages.ts` **缺** `paper_spec_generation_failed` / `document_processing_failed` 中文映射。
- TS:`PaperDocument{document_id, filename}`、`UploadDocumentResponse`(含 document_statuses)、`UploadDocumentStatus` 齐。

**视觉皮(沿用)**:#2c2c2c + 信号橙 #e85d3a + IBM Plex / 思源黑 + border-radius:0 + 半透玻璃 + PanoramaScene;结果页左锚点导航 + 顶部 header + 右下追问面板。

## 4. 范围(必须做)

### 4.1 多选 + 待传确认态(新队列组件)
- [ ] `PaperDropzone` 改成只负责选 / 拖入 `File[]`(拖拽 `Array.from(files)`、input 加 `multiple`、**不再** `item(0)`);选完 `<input>` **reset value**(否则删掉再选同名文件不触发 onChange)。
- [ ] 新建**待传队列 / 确认组件** + `PaperUploadPage` reducer 扩「已选未传」态(`selected`:`items` + `primaryLocalId` + progress 0):列出选中文件(纯 filename + 大小)、可移除、可追加、点「开始生成」才上传。
- [ ] **per-file 校验**:`validatePaper` 升级逐篇(扩展名 + 50MB);混合非法拖入 → 合法进列表、非法逐项显原因、**不因有非法把合法全丢**;全非法不能提交。
- [ ] **篇数上限 5**(对齐 `MAX_PAPER_UPLOAD_FILES`):超限明确提示、不构造请求。
- [ ] **重复文件**:完全相同(`name + size + lastModified`)默认拦截 + 提示;同名但 size / lastModified 不同允许加入、UI 显大小区分。**不用 filename 当 key / primary 锚**。
- [ ] **空态**:全部移除后列表回空、主文献清空、开始按钮 disabled、错误降级为「请选择 PDF/DOCX 文件」。
- [ ] **上传中冻结**:点「开始生成」后 items / 移除 / 追加 / 主文献全冻结、按钮 loading、二次点击不重复提交;取消(若做)仅前端 `AbortController` 取消请求,**不假装取消后端任务**。
- [ ] **失败回待传**:主篇失败 / 全失败 / 4xx → 不进结果页、回待传列表、**保留用户选择 + 主文献**、显顶层错误;用户改任何文件后清旧错误。
- [ ] **单篇路径**:按 §7 PM 表态(倾向走确认态、设主隐藏;或短路直传);无论如何单篇回归 `files.length=1`、不传 primary_index、结果页不加来源噪音。

### 4.2 主文献勾选(★ primaryLocalId 模型 + submit 派生)
- [ ] UI 状态存 **`primaryLocalId: string | null`**(每篇 `localId = crypto.randomUUID()`);**不存 primary_index**。`localId` 做 React key(**不用** index / filename)。
- [ ] toggle 语义(§2):点某篇=主、再点取消=无主、最多一篇;键盘可操作 + aria。
- [ ] **移除主文献**:被移除篇是主 → `primaryLocalId=null`;**不自动提升首篇**(违反「无主=平等」;禁 `primary or documents[0]` 折叠)。
- [ ] **★ submit 瞬间派生 primary_index**:从**同一份** `validItems` snapshot 同时生成 `files` 与 `primary_index`:
  ```
  const validItems = items.filter(x => x.validation === "valid");
  const files = validItems.map(x => x.file);
  const primary_index = primaryLocalId == null ? null
      : validItems.findIndex(x => x.localId === primaryLocalId);
  // primary_index === -1(主篇已被移除 / 变非法)→ 前端清 primary、按无主提交
  ```
  invalid / removed 文件**不进** files、**不参与** index;无主 = **不传** primary_index(不传空串 / `-1` / `0`)。

### 4.3 结果页「这份理解由哪几篇来」(★ 判定用 document_statuses)
- [ ] `PaperHeader` tags 后加**只读**来源清单:成功篇读 `spec.documents`(纯 filename)、主文献 badge 只在 `document.document_id === spec.primary_document_id` 时显、`primary_document_id===null` 不显 badge 也不默认首篇为主。
- [ ] **★ 省略噪音条件精确**:仅**原始就是单篇**(`document_statuses.length===1 && spec.documents.length===1`)才省略 / 极简;**原始多篇即使只成功一篇**(`document_statuses.length>1`、`spec.documents.length===1`)仍显 compact「已读取 X/N: xxx.pdf」+ 失败篇(§4.4)。
- [ ] 来源清单**不加**会进 SectionNav / anchor resolver 的 section id;复用 C 数据流、无新请求。

### 4.4 部分成功提示(★ document_statuses 为真值)
- [ ] `PaperResultData` 加 `documentStatuses?: UploadDocumentStatus[]`,`routeData` 从 `location.state.document_statuses` 带入、传 PaperHeader / 顶部提示组件。
- [ ] banner **只在成功响应**里 `document_statuses.some(s=>s.status==="failed")` 时出现;计数以 statuses 为真值:`N = document_statuses.length`、`X = failed 数`;成功来源用 `spec.documents`;**失败篇绝不进 source / plan / prompt / source_table**;主文献标记只读 `spec.primary_document_id`、不读前端历史选择。
  ```
  共 N 篇资料,X 篇未读取成功。系统已基于读取成功的 (N-X) 篇生成结果。
  未读取成功:
  - xxx.pdf:<友好原因>
  ```
- [ ] **★ error_code 映射(R6 真三码 + unknown 兜底)**:
  ```
  document_parse_failed        → 文件内容未能读取(可能格式不支持、体量过大或文件损坏)。
  paper_spec_generation_failed → 文件已读取,但未能从中提取出结构化内容。
  document_processing_failed   → 该文件未能处理成功。
  (unknown / null)             → 该文件未能读取成功。
  ```
  **不显 raw error_code、不 console 打 filename / error_code / 后端 error body / 文件对象**(decision 11);前端可展示后端清洗后 filename(用户识别失败篇需要)。errorMessages.ts 补上述映射。
- [ ] **刷新语义**:部分成功提示 = 上传后即时提示、**不承诺刷新持久化**;刷新 / 直达无 `document_statuses` → **不报错、不显假 banner**。持久化需后端支持(非本纯前端卡)。

### 4.5 API 层
- [ ] 新增 **`apiUploadFormTask(path, formData, onProgress)`**(护现有单文件 `apiUploadTask` / MCS zip `/upload` 不改);`paperApi.uploadDocument` 改接 `File[]` + `primaryIndex?: number`:FormData 逐篇 `append("file", f)`(按 valid snapshot 顺序)+ **按需** `append("primary_index", String(idx))`(无主省略);send 整个 FormData。
- [ ] 进度用 XHR `upload.onprogress`(multipart 总进度,非逐篇解析进度;文案不误导成「逐篇」)。

## 5. 落点小结(实施形状,R6 已勘;Codex Stage 0 复核 live)
- 待传队列 = 新组件;`PaperDropzone` 降为 `File[]` 选择器;reducer 扩 `selected` 态。
- 上传 = 新 `apiUploadFormTask`;不动单文件 `apiUploadTask`。
- statuses = `PaperResultData.documentStatuses?` ← `location.state`;PaperHeader 消费。
- 来源清单 = PaperHeader tags 后。
- error 文案 = errorMessages.ts 补三码。

## 6. 不做 / defer
后端任何改动、schema、B2 冲突链、C citation 可点链、MCS、交互式裁决、上传后改主文献、拖拽排序(本期不做、但 primary_index 重算须为未来排序留正确性)、前端测试框架、刷新持久化 banner。

## 7. PM 接触(一句知会 + 表态空间,非拍)
- **多选流体验 + 单篇分支**(视觉走截图):多选上传在「开始生成」前给用户看待传列表(设主 / 移除);单篇倾向也走这一步(设主隐藏),PM 若要「选完即传」则单篇短路。视觉(队列 / 主文献框 / 来源清单 / 失败提示措辞 / 主文献解释文案)截图过目。
- 其余(primary_index 派生、statuses 落点、进度呈现、校验、上限、error 映射、组件拆分)= 实施形状,双审,不烦 PM。

## 8. 验收标准(并 R1 P0 gate;测试类适配「前端无框架」)

**测试适配说明**:项目**前端无测试框架**,故 R1 的「单元 / 组件 / e2e 测试」适配为 —— 关键纯逻辑(primary_index 重算)**抽纯函数** + 静态守卫 smoke + **Codex 手动走查** + **九态截图**(桌面+移动)作为验收证据;下列 gate 凡涉「测试覆盖」均以「走查 + 截图覆盖该态」满足。

**A 范围 / diff**:① 不改 `api/ core/ features/ adapters/ schemas/ docs/06`(发现须动 → 停手报 PM);② 不改 CitationChip target / 高亮 / 降级(C 行为);③ 不给 B2 冲突区加采用 / 合并 / 裁决;④ MCS 页零 diff;⑤ `git diff --name-only origin/main` 只落 web 前端 + 必要 TS。

**B 待传态**:⑥ 选择 + 拖拽多文件、input 有 multiple、无 `item(0)` 旧路径;⑦ 列表用 `localId` key(非 index / filename);⑧ 空态开始按钮 disabled + 主文献清空;⑨ 混合非法:合法留、非法逐项原因、全非法不可提交;⑩ 上限 ≤5 超限提示、不构造请求;⑪ 重复完全相同拦截、同名不同文件可加入且可区分;⑫ 重选同一文件能触发 change(input reset)。

**C 主文献**:⑬ 状态存 `primaryLocalId`(非 index);⑭ 点设主 / 再点取消、键盘同等可操作;⑮ 移除主文献 → null、不自动提首篇;⑯ 追加 / 移除后 submit 重算 primary_index;⑰ 无主不传 primary_index(非空串 / `-1` / `0`);⑱ 单篇不传 primary_index(向后兼容);⑲ **纯函数 + 走查 / 截图验**:3 个 mock / 手选 File,选第 3 为主、删第 1 → 提交 primary_index = 1。

**D FormData / API**:⑳ FormData 按最终 valid list 顺序 append 多个 `file`;㉑ primary_index 与 append 同一 snapshot;㉒ invalid / removed 不进 FormData;㉓ 提交中禁二次点击、双击一次请求;㉔ 上传中列表 / 主文献 / 追加 / 删除全 locked;㉕ 4xx / 整体失败留上传页错误态、不进结果页;㉖ 不改单文件 `apiUploadTask` / MCS zip。

**E 结果页 source / partial**:㉗ 来源清单只读 `spec.documents` + `spec.primary_document_id`;㉘ 原始单篇(statuses 与 documents 皆 1)不加噪音;㉙ **原始多篇即使 documents 只 1** 仍显 compact 来源 + 读取成功说明;㉚ 主文献 badge 仅 `document_id===primary_document_id` 显、null 不显不默认首篇;㉛ failed 篇不进来源清单;㉜ banner 仅成功响应 `statuses.some(failed)` 时出现;㉝ banner 计数以 statuses 为准(总 / 失败 / 文件名 / 友好原因);㉞ 刷新无 statuses 不报错、不显假 banner。

**F 错误文案 / 隐私**:㉟ error_code 只走 allowlist(真三码)、未知走通用;㊱ 不显 raw error_code;㊲ `console.*` 不输出 filename / error_code / 后端 error body / 文件对象;㊳ lint / grep 确认无 `console.*(file` / `console.*error_code` 泄露;㊴ 失败文案不写「主文献失败但已改用第一篇」类错误暗示。

**G 回归 / 视觉**:㊵ `pnpm typecheck` / lint / build 绿 + 静态守卫 smoke 过;㊶ **九态截图**(桌面+移动)给 PM:空态、待传多篇无主、待传多篇有主、混合非法、上传中、单篇成功、多篇成功带主文献、部分成功(原始多篇只成功一篇)、整体失败错误态;㊷ decision 13 纯前端零后端 schema diff、跳过 schema-sync(PR 说明注明)。

## 9. 风险与注意点
1. **★ primary_index 只在 submit 派生**(P0):存 primaryLocalId、valid snapshot 算 index、localId key、invalid 不参与、无主不传;传错 = 指错主文献。
2. **★ 原始多篇只成功一篇**:判定用 `document_statuses.length`,不用 `spec.documents.length` 反推;否则用户不知系统用哪篇生成。
3. **单篇向后兼容**:多选改造不挂单篇(files 长度 1、不传 primary_index)。
4. **statuses 落点 + 刷新语义**:只在 location.state、刷新丢;不承诺持久化、刷新不报假 banner。
5. **error_code 真三码**(非 R1 草案):allowlist + unknown 兜底;不泄露、不 console(decision 11)。
6. **上传 helper 隔离**:新 `apiUploadFormTask`,不动单文件版护 MCS zip;进度是 multipart 总进度非逐篇。
7. **不碰已合并**:CitationChip 可点链 / B2 冲突区 / MCS 零改。
8. **无前端测试框架**:纯逻辑抽函数 + smoke + 走查 + 截图,不引框架。
9. **主文献误解**:UI 给解释文案(主次 ≠ 更可信)。

## 10. 给 Codex 的提示(派单实现阶段)
- Stage 0 取 live origin/main HEAD、从 live 切新分支;逐条复核 §3 现状(PanoramaScene、PaperUploadPage 状态机、PaperDropzone item(0)、apiUploadTask 单文件、usePaperResult 丢 statuses、navigate state=response、PaperHeader 结构、MAX_PAPER_UPLOAD_FILES=5、validatePaper 单文件、error_code 三码、errorMessages.ts 缺映射),不符停手(decision 15);**若发现须改后端 / schema 或须动 C 可点链 / B2 冲突链 → 停手报架构师**。
- 纯前端:后端零改动、schema 零 diff(decision 13 跳过 schema-sync,PR 说明注明);现有 TS 镜像已足,不改后端契约。
- primary_index 只在 submit 从 valid snapshot 派生(§4.2);存 primaryLocalId、localId key、invalid 不参与、无主不传;移除主文献不提首篇。
- 原始多篇只成功一篇判定用 document_statuses.length(§4.3 / 4.4)。
- 新 `apiUploadFormTask`、不动单文件 `apiUploadTask`(护 MCS zip);FormData 逐篇 append + 按需 primary_index;进度 multipart 总进度、文案不误导。
- statuses 经 `PaperResultData.documentStatuses?` ← location.state;刷新无 statuses 不报假 banner。
- error_code 真三码 allowlist + unknown 兜底;不显 raw、前端 console 干净(decision 11:不打 filename / error_code / error body / 文件对象)。
- validatePaper 升 per-file(扩展名 + 50MB);篇数上限 5;input reset;拖拽 Array.from。
- 单篇按 §7 PM 表态(确认态 or 短路);单篇回归不挂。
- 不碰 CitationChip 可点链 / target、B2 参数冲突区、MCS。
- 无前端测试框架:纯逻辑抽函数 + 静态守卫 smoke + 走查 + 九态截图(桌面+移动)。
- 改文本文件保留原始字节 / 行尾(decision 08);本机无 grep 用 git grep / rg / Select-String。
- 截图作图片附件传对话(桌面+移动九态);本机路径不收。
- 完工三件套;任务卡随代码同 PR add、索引收尾单独 PR(decision 07);子卡完工 521 整数不 +1。

**修订历史**:v0.1(架构师起稿,以取证 live `31c23ce` + 521-A/B1/C as-built + 06 §12 为据)→ **v0.2**(并 R1=GPT「条件通过」12 状态 + primary_index submit 派生 + P0 gate + R6=Codex 真 repo 可落核纠正 PanoramaScene / error_code 三码 + 三处结构落点;无新产品决定;测试类适配「前端无框架」)。
