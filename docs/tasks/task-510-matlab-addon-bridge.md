# TASK-510:MATLAB Add-on 连接桥 spike(v0.3-a)

> 任务卡落仓文件名:`docs/tasks/task-510-matlab-addon-bridge.md`

## 状态

🔲 v0.5 终版(2026-06-21,**两轮 AI 终审一致可派**:Codex R6「通过可派单」;GPT R1「修完 4 P0 即派,无需再全文审」——本版已修完)

- v0.4 → v0.5:吸收第五轮 R1(GPT,4 P0 + 4 P1,均为**局部消歧 / 笔误 / 填空**)。Codex 第五轮直接通过。
- **策略级 + 契约级已全部纸面锁死**。**Stage 0「实测确认」项(非待定留白)**:① `APP_ENV` 与 main `app/config.py` 现有 `SettingsConfigDict` / `env_prefix` / 大小写策略**兼容性**(外部变量名与 `validation_alias` 已锁,不改);② `ToolboxOptions.SupportedPlatforms` 字段在 R2026a 的实测;③ bridge 415 guard 行为。这三项是"用真实环境确认已锁方案能落地",不是"留给 Codex 发明"。
- 编号 TASK-510;命名 `matlab_bridge` / `bridge_diagnostic` / `matlab_bridge_enabled` / `/api/v1/bridge/diagnostic`。

---

## 上下文

### 在 paper-to-model 主线的位置

- paper-to-model v0.1 后端链路已全部入 main、TASK-500~503 ✅。
- TASK-510 = decision 23 的 **v0.3-a「Add-on 连接 spike」**:打通 MATLAB ↔ 后端最小连接;不做 v0.3-b 的自动采集 / 报错解释 / 收敛 / 波形 / **Engine 接入**。
- **v0.3 总体仍以 Engine 闭环为目标;仅 v0.3-a 不接、不验 Engine,Engine 接入归 v0.3-b**(PoC:v0.1 相对通用 ChatGPT +5-10%,engine 闭环 55-65%;**55-65% 不进本卡验收 / 发布**)。

### 不确定性已被本机 probe 大幅消除

probe 已真跑通「打 `.mltbx` → `installToolbox` → 函数内 `webwrite` → 收回包写进隐藏 `uifigure` → `uninstallToolbox` → 无残留」。本卡 = 做实 + 加 bridge 端点 + 安全边界 + schema 治理,**非赌能不能通**。E2E 禁 echo server,打真实 FastAPI app。

### 对外口径硬约束

证明 **传输桥**,未用 / 未验证 Engine API、未运行模型。PR / 对外禁写「Engine 已接通 / 闭环完成」。副驾口径不升。

### Base commit(ancestor 检查)

PM 派单提供前置 chore merge commit `<SYNC_COMMIT>`。Stage 0(先 `git fetch`):`git merge-base --is-ancestor 393e6be origin/main` 与 `... <SYNC_COMMIT> origin/main` 均退 0 → 从最新 `origin/main` 切分支;任一非 0 停手报 PM。

### 本机环境事实

R2026a(`F:\Matlab`,单版本,R2022b 残留)/ `matlab -batch`(启动 10-21s)/ App Designer · `uifigure` 可用 / 代理 `127.0.0.1:7897`(用 `localhost`)/ License = Sponsored。

### 审批级别:架构升级类(已过五轮 R1 + R6,两边可派)

---

## 输入(前置依赖）

- ✅ TASK-500~503 / decision 22;decision 24 / 25 无直接前置。

### 两个 PR 文件归属(严格拆分,互不重叠)

**前置同步 chore PR(实施 PR 前合并;不写生产代码)**:
- `docs/tasks/task-510-matlab-addon-bridge.md`(本卡,以 `create_file` 入仓)
- `docs/decisions/20260616-23-product-architecture-v02-v03-client-techstack.md`(decision 23 § 2.2 v0.3-a 整行)
- roadmap(**Stage 0 grep 确认实际路径**:GPT 称 `docs/roadmap/mxa-tutor-v2-paper-to-model.md`,与项目快照扁平路径不一致,以 main 实测为准)的 § 5 + § 10.3
- `docs/01_PROJECT_CONSTITUTION.md`(宪法 § 3 `.mlx` / Engine 阶段表述)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(加「v0.3-a 传输桥,不含 Engine」数据流)

**TASK-510 实施 PR(不创建 / 不修改本任务卡,不再改上述四份战略文档）**:
- 后端 + MATLAB 生产代码 / tests / `schemas/*.json`(三个)/ schema 导出脚本 / `docs/06_OUTPUT_CONTRACTS.md` / `.env.example` / `docs/03_TASK_INDEX.md`(TASK-510 行)

### 前置 chore 改动 + 验收

四处把 v0.3-a 旧定义(error/status + 建议回传 + ≥2 版本 + 接 Engine + `.mlx`)收窄到(manual_error + 连接回执 + 仅 R2026a + 不接 Engine + 程序化 `.m`),**保留「v0.3 总体仍以 Engine 闭环为目标,Engine 接入归 v0.3-b」**。chore 验收:更新各文档版本号 / 状态头 + 相互引用;`git diff` 无无关行尾变化;**grep 确认旧字面 `.mlx`、v0.3-a 接 Engine、`≥2 版本` / `≥90%` 无指令性残留**。

---

## 输出(交付物 — 决策 13 schema 全清单)

### 后端

- `core/domain/bridge_diagnostic.py`(纯 domain,**不 import Pydantic**)
- `features/matlab_bridge/bridge_diagnostic_schemas.py`(冻结三类:`BridgeDiagnosticRequest` / `BridgeDiagnosticReceiptModel` / `BridgeErrorResponse`)
- `features/matlab_bridge/diagnostic_service.py`
- `api/routes/matlab_bridge.py`(path-scoped custom `APIRoute` / `Request`)
- 三个 JSON Schema:`schemas/bridge_diagnostic_request.schema.json` / `bridge_diagnostic_receipt.schema.json` / `bridge_error_response.schema.json`
- schema 导出 / 重生成脚本
- `tests/features/matlab_bridge/test_bridge_diagnostic_schemas.py`(边界)
- `tests/features/matlab_bridge/test_bridge_diagnostic_schema_freeze.py`(分别 freeze 三模型 + domain↔wrapper round-trip,见 § domain 边界)
- `docs/06_OUTPUT_CONTRACTS.md` 新增 bridge diagnostic 章节
- 增量改 `api/dependencies.py` / `api/main.py` / `app/config.py` / `.env.example`
- `docs/03_TASK_INDEX.md` 新增 TASK-510 行(完工 🔍,PM 合并后 ✅)

### MATLAB 端(落点子树 — R1 P1-1)

```
clients/matlab_bridge/
├── app/     # 打入 .mltbx 的生产代码(含窄注入点 + 真实 uiconfirm/webwrite)
├── build/   # 打包脚本,不打入工具箱
├── tests/   # 单测 + headless E2E,不打入工具箱
└── dist/    # 本地生成物
```

**`.mltbx` 二进制策略(R1 P1-1,方案 A)**:`.mltbx` **不进 git**;R6 报告记录绝对产物路径、文件大小、SHA-256(供 PM 双击补测)。

### domain / wrapper 唯一边界(R1 P1-3)

```
route: BridgeDiagnosticRequest(Pydantic).to_domain()
  → DiagnosticService.consume(BridgeDiagnostic domain)
  → BridgeDiagnosticReceipt(domain)
  → BridgeDiagnosticReceiptModel.from_domain()
```

freeze 测试增:wrapper↔domain 字段名 / 顺序 / 类型对应、`request.to_domain()`、`receipt.from_domain()`、round-trip、core 不 import Pydantic。(防 core contract 变无消费者空壳)

> 决策 13「project_type Literal」项不适用。

---

## 范围(必须做)

### 1. 后端 bridge 端点 `POST /api/v1/bridge/diagnostic`

**matlab_bridge router 固定执行顺序(R1 P0-2;1–4 全在 JSON/Pydantic 前,经 path-scoped custom `APIRoute`/`Request` 实现,普通 dependency 不能作此前置边界)**:

```text
1. feature flag      → 决定路由是否存在(关 → 整个 path 不注册 → 404 沿用全局)
2. loopback 检查     → 非 127.0.0.1/::1 或 client.host 缺失/无法解析 → 403
3. Content-Type 检查 → 非 application/json → 415(按解析后 media type 判断,接受大小写 + charset=utf-8,不对原始 Header 全文精确相等)
4. 实际字节累计      → body > 32 KiB(> 32768 字节)→ 413;≤ 32768 继续
5. JSON 解码
6. Pydantic 校验     → 失败 → 沿用全局 422
7. service           → 固定连接回执 stub
```

- **feature flag `matlab_bridge_enabled`(默认 false)失败关闭**:`app_environment` **默认 `"production"`**,类型 `Literal["production","development","test"]`,**绑定写死 `Field(default="production", validation_alias="APP_ENV")`**(R1 P0-1 / R6 P0-1:外部变量名 `APP_ENV` 与 alias 已锁,Stage 0 只验与 main config 兼容,不改外部名 / 验收字面)。启动不变量:`matlab_bridge_enabled == true and app_environment not in {"development","test"} → 启动失败`(默认 production ⇒ 漏配即失败关闭)。
- 路由元数据(R1 P1-4):`response_model = BridgeDiagnosticReceiptModel`;`responses`:403 / 413 / 415 → `BridgeErrorResponse`,422 → 全局 `{error, message}`。
- 不调 LLM / DB / cache / 不持久化 / 成功与失败路径均不 echo `error_text`;生产 URL 仅 HTTPS,不绕证书校验。

### 2. MATLAB Add-on

- 用户**手动粘贴错误文本**(`manual_error`)→ 客户端绝对路径 best-effort 脱敏 → 显示最终待发文本 → `uiconfirm` 确认 → `webwrite` POST → 收回包写进 `uitextarea`
- **`uiconfirm`**:`DefaultOption=Cancel`、`CancelOption=Cancel`;**确认框脱敏文本冻结为不可变快照,确认后发送同一快照**
- **UI 固定提示**:「请勿粘贴源码、账号、密钥或其他敏感信息」
- **base URL(R1 P0-4)**:UI **不提供 URL 输入框**;生产 app 内部 `BaseUrl` 配置;**默认 `BaseUrl = http://localhost:8000`**(对齐 TASK-503 后端验收惯例);E2E 经非 UI 构造参数 / factory 注入 `http://localhost:<ephemeral-port>`;**http 仅允许 hostname 精确 `localhost`,其他 hostname 必须 https,URL 不含 userinfo**
- 客户端 `weboptions("MediaType","application/json", ...)`(R1 P1-4);网络调用设有限 timeout;**客户端不持久化请求正文;网络错误只显示固定文案,不把 payload / stack 打到 Command Window**
- **`.mltbx` 元数据(R1 P0-4 / P1-4)**:`MinimumMatlabRelease = MaximumMatlabRelease = "R2026a"`;`ToolboxVersion = "0.1.0"`(避免默认 `"1.0"` 与 `client_version` 漂移;安装后断言 `Version=="0.1.0"`);`SupportedPlatforms`:`Win64=true`,`Mac=false`、`Glnxa64=false`、`MatlabOnline=false`(官方已定义字段;R2026a Stage 0 实测确认);固定 UUID 常量 `2690af3d-9cfe-4442-900e-c86af37a6244`;`ToolboxName = "mxa-matlab-bridge"`;(R2017b 仅文档注释,不作兼容声明)

### 3. 安全边界(v0.3-a 子集)

- **诚实表述**:Add-on 不自动读取 / 单独上传源码 · 工程 · 模型;用户确认后的自由文本仍可能含源码 / 秘密(故 UI 提示 + 脱敏 + 后端不留存)。
- 客户端绝对路径 best-effort 脱敏,**至少覆盖 Windows drive / UNC / POSIX / `file://`**(不承诺彻底)+ 用户看最终文本。
- 后端不持久化 / 不缓存 / 成功与失败均不 echo `error_text`;**bridge 业务事件日志**白名单 = `{request_id, matlab_release, client_version, payload_chars, status, latency}`。
- **不修改全局 `RequestValidationError` handler**(现有 `{"error","message"}` 被 paper/MCS 契约测试锁定)。
- schema `extra="forbid"`,显式拒 `file_path` / `source_code` / `slx_path` / `workspace` / `stack` / `project_files` / `model_content` / `files`。

### 4. 打包 seam(注入钩子属生产代码,替身 / 驱动不打包)

- **打入 `.mltbx`**:`app/` 生产代码 + 窄依赖注入点(构造参数 / 内部 factory,用于 confirm 实现与 base URL)+ 真实 `uiconfirm` / `webwrite`
- **禁止打入**:fake confirm、test harness、E2E launcher、构建脚本、测试数据
- 锁具体入口:构造参数 / 内部 factory(**禁自创全局变量测试门**);显式设 `ToolboxFiles` / `AppGalleryFiles` / `ToolboxMatlabPath`(App Gallery 入口须同时在 ToolboxFiles)

### 5. 端到端连通

本机 R2026a 跑通「装 → 脱敏 → 确认 → 发 → 收 → 显示 → 卸载无残留」,打真实 FastAPI app。

---

## 不做（明确排除）

❌ 自动捕获运行期错误 / ❌ 报错解释 · 收敛 · 波形 · **Engine 接入** / ❌ 后端接 LLM / ❌ 跨多版本实测 / ❌ 完整 token · 认证(靠 loopback + 默认关 + 启动不变量) / ❌ 中间件 · Electron / ❌ 状态采集 / ❌ 改 paper · MCS 既有 feature / ❌ 改全局 422 handler / ❌ 复用 paper_upload 上传链路 / ❌ import paper 私有结构。

---

## 接口契约

**请求**(`POST /api/v1/bridge/diagnostic`,`Content-Type: application/json`):
```json
{ "protocol_version": "0.3-a", "request_id": "<UUID4>", "diagnostic_kind": "manual_error",
  "matlab_release": "R2026a", "client_version": "0.1.0",
  "error_text": "<用户确认后的脱敏文本>", "consent_confirmed": true }
```
**成功回执**:
```json
{ "request_id": "<同请求>", "status": "received", "mode": "connectivity_stub",
  "message": "连接成功。本版本仅验证诊断信息传输,不提供报错解释。" }
```
**字段类型(Pydantic)**:`protocol_version` `Literal["0.3-a"]` / `request_id` `UUID4` / `diagnostic_kind` `Literal["manual_error"]` / `matlab_release` `^R20[0-9]{2}[ab]$` / `client_version` `^[A-Za-z0-9.\-]{1,32}$` / `error_text` strip 后非空、拒 NUL、1–4096 Unicode 字符 / `consent_confirmed` `StrictBool` + validator 强制 `True`(测 `1` / `"true"` 均拒)/ `extra="forbid"` 显式拒上列敏感字段。

**错误响应契约(唯一方案;`BridgeErrorResponse` = `{error, message}`,禁 `field/input/body/value/detail`)**:

| 状态码 | 触发 | 响应模型 | `error` | `message` |
|---|---|---|---|---|
| 200 | 成功 | `BridgeDiagnosticReceiptModel`(冻结) | — | 见上 |
| 422 | schema / consent≠true | **沿用全局** `{error,message}`(不纳入 bridge 冻结) | `validation_error` | 全局现有 |
| 413 | body > 32768 字节 | `BridgeErrorResponse`(冻结) | `bridge_payload_too_large` | `诊断内容过大` |
| 415 | Content-Type 非 json | `BridgeErrorResponse`(冻结) | `bridge_unsupported_media_type` | `仅支持 application/json` |
| 403 | 非 loopback / `client.host` 缺失或无法解析 | `BridgeErrorResponse`(冻结) | `matlab_bridge_forbidden` | `仅允许本机 MATLAB Add-on 访问` |
| 404 | feature 未启用(router 未注册) | **沿用全局 404** | — | — |

- **body > 32 KiB(> 32768 字节)按实际字节在 Pydantic 前拒绝并返回 413;≤ 32768 字节继续进入 JSON / Pydantic**(R1 P0-3,修正反向不等号)。成功与失败均不 echo `error_text`;不调 LLM / DB / cache。

---

## 验收标准(三层)

### A. 后端单测

- [ ] 合法请求 → 200 固定 receipt
- [ ] `consent_confirmed`=false / 缺失 / `1` / `"true"` → 422;空 / strip 空 / NUL / 超 4096 字符 `error_text` → 422;`client_version` 违反 pattern → 422;多余敏感字段 → 422(均沿用全局 422 shape)
- [ ] body limiter:无 `Content-Length` / 伪造偏小 CL / chunked / **恰好 32768 通过 / 32769 → 413**(`BridgeErrorResponse`,Pydantic 前)
- [ ] `Content-Type` 非 json(含 `application/json; charset=utf-8` 应通过)→ 415(`BridgeErrorResponse`)
- [ ] 非 loopback / `client.host` 缺失或无法解析 → 403(`BridgeErrorResponse`)
- [ ] 失败路径脱敏:4 sentinel(`error_text` / `source_code` 字段值 / 超长 body / 损坏 JSON)不含于 HTTP response、bridge 业务日志、access/error log、stdout/stderr;**全局 422 shape 未改动(paper/MCS 契约测试仍绿)**
- [ ] 无 LLM / DB / cache 调用(bridge 层)
- [ ] 失败关闭矩阵:`enabled=true + APP_ENV 缺失(默认 production)→ 启动失败`;`enabled=true + production → 启动失败`;`enabled=true + development/test → 成功`;`enabled=false + 任意 → 成功启动但 path 不注册(404)`
- [ ] schema freeze:request / receipt / error_response 三模型 + domain↔wrapper round-trip + core 不 import Pydantic
- [ ] OpenAPI:feature 开时含 403/413/415/422 响应声明;关时整个 path 不存在

### B. R2026a headless E2E（真实 FastAPI app,禁 echo server）

> launcher 启动 `create_app()`,临时 `DB_PATH`/`UPLOAD_DIR`、`MATLAB_BRIDGE_ENABLED=true`、`APP_ENV=test`,monkeypatch embedder 为 `FakeEmbedder`;MATLAB 请求真实 `/api/v1/bridge/diagnostic`。「不调 DB/LLM」指 bridge 层。

- [ ] `packageToolbox` → `.mltbx`(固定 UUID + Min=Max=R2026a + `ToolboxVersion="0.1.0"` + 仅 Win64 + 显式文件清单**排除替身 / launcher / 构建脚本**);重复构建 UUID 不变
- [ ] `installToolbox`(返回含 `Name`/`Version`/`Guid`;**断言 `Version=="0.1.0"`**;不用 `matlab.addons.install`)
- [ ] 隐藏 `uifigure`;`onCleanup` 兜卸载
- [ ] 经生产代码窄注入点(构造参数 / factory)注入「确认」+ 临时 localhost 端口 → 触发一次请求到真实 app → 回包写入 UI 组件 / 状态变量并断言(真 GUI 点击留 PM)
- [ ] 注入「取消」→ 零 HTTP 请求
- [ ] E2E server 处理 `localhost` `::1`;非 loopback 来源被 403 拒
- [ ] 客户端脱敏单测:Windows drive / UNC / POSIX / `file://` / 含源码 sentinel → 脱敏后不含原路径
- [ ] `uninstallToolbox` → `installedToolboxes` 无该 `Guid`、`which('入口函数')` 为空、install folder 不在 MATLAB path(不强制 restoredefaultpath / rehash)
- [ ] 「卸载无残留」= 无 TASK-510 可观测残留

### C. PM 人工补测

- [ ] 真双击 `.mltbx`(≤1 分钟,产物路径见 R6 报告)/ 真 App Gallery 启动 / 真 `uiconfirm` 确认与取消 / 卸载体验

### 不验

❌ 跨版本连通率

---

## 风险与注意点

- identifier 固定 UUID;`installToolbox` 不用 `matlab.addons.install`;`localhost` 可能优先 `::1`;`Content-Length` 不可信(按实际字节);不改全局 422 handler;`MinimumMatlabRelease`=最早兼容版本(只测 R2026a 锁 Min=Max);stub 无阻塞不加 `to_thread`、`logger.exception` 禁(决策 11)。
- **Stage 0 实测确认(非待定)**:`APP_ENV` alias 与 main config 兼容、`SupportedPlatforms` 字段名 R2026a、415 guard 行为。

---

## 估时

预估 **2–3 天**。Stage 0 复核。

---

## 给 Codex 的提示

- **Stage 0**:① `git fetch`;两条 `merge-base --is-ancestor`(`393e6be`、`<SYNC_COMMIT>`)均 0,从最新 origin/main 切分支;② grep 03 索引 + **grep 确认 roadmap / decision 23 实际路径**;③ 对齐 main paper feature 落点 + `app/config.py` pydantic-settings 约定;④ 确认前置 chore 已合并;⑤ 核对决策 13 清单。
- 415 / loopback / body limiter 全走 path-scoped custom `APIRoute`/`Request`(顺序见 § 范围 1),**不用普通 dependency**;失败脱敏走 bridge 专属,不动全局 handler。
- E2E:launcher + `create_app()` + 临时路径 + `FakeEmbedder` + `APP_ENV=test` 打真实 app;经生产代码窄注入点注入 confirm 与端口,**替身 / launcher 不打入 `.mltbx`**。
- 任务卡由前置 chore 以 `create_file` 入仓;**TASK-510 实施 PR 不创建、不修改本任务卡**;分支 `task/TASK-510-matlab-addon-bridge`;禁 main 改;完工 03 索引 🔲 → 🔍;R6.1 `git diff --stat origin/main` 与文件清单一致 + 记录 `.mltbx` 路径/大小/SHA-256。

---

## 关联

decision 23 § 2.2(🔲,前置 chore 同步)/ decision 22 § 1.1 · § 3.3 / **决策 13** / 决策 11 / 决策 21 / 决策 12 v0.4。

---

## 审批历史

- v0.1（brief 过审）→ v0.2（二审 R1 6P0+R6 7）→ v0.3（三审 R1 4P0/7P1+R6 2P0/4P1）→ v0.4（四审 R1 4P0/3P1+R6 2P0/4P1）。
- **v0.5 终版（2026-06-21，五审）**:Codex R6 直接通过可派;GPT R1 4 P0 + 4 P1（均局部消歧 / 笔误 / 填空）:
  - P0-1（`APP_ENV` 一边委托一边写死 → 外部名 + `validation_alias` 锁死,Stage 0 仅验兼容）/ P0-2（415 删 `dependency`,统一 path-scoped custom `APIRoute` + 固定执行顺序）/ P0-3（`≤32KiB` 反向不等号 → `>32768 字节 413`）/ P0-4（`<固定端口>` 占位符 → `BaseUrl=http://localhost:8000` + ephemeral-port + hostname/userinfo 约束）
  - P1:MATLAB 落点 `clients/matlab_bridge/` 子树 + `.mltbx` 不进 git(R6 记录路径/大小/SHA-256)/ 前置 chore 精确路径 + `create_file` 归属消歧 / domain↔wrapper 转换方向 + round-trip freeze / OpenAPI `responses` 声明 + `ToolboxVersion="0.1.0"` + `SupportedPlatforms` 字段写死 + `weboptions` MediaType
- **架构师起草线判断偏差承接(趋势记账,决策 22 § 9)**:
  - 编号 K_28a 连栽 2 次;多轮凭过时/间接证据推 main 现状被实测推翻;v0.1 后倾向直接派被二审 6 P0 否定;三、四审持续抓出我引入的局部契约矛盾 + 凭印象写错的实施细节。
  - **委托边界偏差(本轮 GPT 拉回)**:四审起对策"环境依赖级委托 Stage 0"划得过宽,把官方已明确的 `validation_alias` 机制、`SupportedPlatforms` 字段名也委托了——矫枉过正。**修正后边界**:官方有定论的写死 + Stage 0 实测确认;只委托真正无官方定论、依赖 main 现有约定 / 运行时行为的项。
  - **收敛轨迹**:五轮 P0 性质从「方向 / 策略」→「工艺 / 治理」→「契约矛盾」→「局部消歧 / 笔误」,逐轮触底;Codex 五审通过 + GPT「修完即派无需再审」= 终点信号。
