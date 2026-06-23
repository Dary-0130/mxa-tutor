# TASK-514:MATLAB bridge 自动采集报错 → 解释(v0.3-b / b2-1 块 B)

## 状态
🔲 **v0.5(R6 spike 通过,可派单)**(2026-06-23)。三审 ACK 后,**R6 spike(R2026a / Windows)= 通过**:`try/catch` 捕获的 `MException` 可稳定取白名单字段、**不需另一套 Engine API、不拓宽服务端 provider**(确认本卡架构站位)。本版把 spike 实测的**白名单字段 + 上限**锁进 §自动采集安全不变量 (1)。**三道实现门全齐 → 可派 Codex 建。**
**实现门(三道,全齐)**:① 契约决策 A — **PM 已拍**;② R1 审 — **三审 ACK 通过**;③ **decision 13 全清单** — 实现期 Codex 照做(清单见本卡)。R6 spike 已通过、字段已锁。

---

## 编号与拆分
- 提议 **TASK-514**(派单前 `git show origin/main:docs/03_TASK_INDEX.md | grep -n "TASK-51[45]"` 复核 514 空)。
- v0.3-b 拆分 `T0 → b1 ∥ b2-0 → b2-1 → b3`:本卡 = **b2-1 块 B(采集 → 解释)**,接在 **块 A(TASK-513,Engine 接入运行时,已合并)** 之后另起;**b3(闭环陪调)= TASK-515,另卡**。
- **定义来源**:权威拆分文件 `v0_3b-split-final-skeleton.md` 经 Codex 实测**不在 `origin/main`**(decision 15 已报);本卡据 **roadmap §5 + b1/bridge 现有契约取证(`origin/main` ac747d8)+ TASK-513 卡尾块 B 预告** 设计。

---

## 背景与定位
- **块 B 只做一件事**:把 b1(TASK-511,`POST /api/v1/bridge/explanation`)的输入来源,从"用户**手动粘贴**的报错"换成"程序**自动采集**的报错",再走**同一条 LLM 解释管线**回传显示。
- **契约决策 A(PM 2026-06-23 拍)**:自动采集来的报错,**扩现有契约**(在现有报错类型上加一个值)接入,**不新建一条解释管线**。理由(PM 认同):自动采集和手动粘贴本质同物——都是一条 MATLAB 报错、要中文讲明白,区别只在"怎么拿到的";加个来源标签即可,复用已验证的护栏最稳。
- **块 B 明确不做**:不碰收敛 / 波形 / CSV/MAT(那是 b3,TASK-515);不改 b1 现有 `explain()` 逻辑 / 签名;不动 `/diagnostic` 连接 stub 与 v0.3-a freeze;**不拓宽服务端 Engine、不跑用户模型**(见 §架构站位)。
- **单拆理由**:把"自动采集 + 受控敏感通道"这块风险独立验,不和 b3 的 run-state / 迭代循环混。
- **块 B 验收门 = 机制 + 确定性护栏**(沿用 b1 哲学):保证"自动采集 → 解释 → 显示的机制对" + "auto_captured 与 manual 走同一脱敏 / 输出隐私 / fail-closed 护栏" + "强制用户确认采集快照"。**解释在事实上对 / 有用的质量评估,仍随 b1 推迟到挂起 seam**(不变量 14;seam 通过前不上 production)。

---

## 架构站位(关键设计决定,请 R1 重点审)
> 取证暴露一个工程坎:**`MatlabEngineProvider` 对服务层只暴露 `health_probe() -> None`**;`run_simulation()` 在 concrete `MatlabEngineSession` 上有,但 `app.state` 公开的是窄 provider,服务层经 provider 调不到 `run_simulation()`。Codex 据此提示"块 B 若要抓诊断 / 跑仿真,按当前 main 不能直接经 provider 调到"。**本卡的设计回应:块 B 根本不经服务端 Engine 采集,所以这不是阻塞。**

- **采集发生在客户端**:Add-on 是跑在用户本机 MATLAB **进程内**的程序,经 MATLAB 自身的报错机制(`MException` / `lasterr` 等)在**进程内**采集报错——**不调用任何 MATLAB Engine API,与服务端 TASK-512/513 的 Python MATLAB Engine 无关**(R1 P1 术语订正)。采集后客户端先 **白名单 + 脱敏 + 有界截断**,**强制用户确认最终待发快照**后,经 HTTPS 发到 `/explanation`,字段标 `diagnostic_kind="auto_captured_error"`。
- **服务端不跑用户模型**:沿用 roadmap §5.2「用户自托管」+ §10.3 数据边界「不上传完整工程」。服务端只收到**有界、脱敏后的报错文本**,职责与 b1 同(收诊断 → LLM 解释),不持有用户 `.slx`、不运行它。
- **服务端 Engine(TASK-512/513)= dev/test 设施,非块 B 采集路径**:它受 `matlab_engine_enabled` + `APP_ENV ∈ {development,test}` 守门(production 永远关),用于开发 / 测试期在本机端到端验桥,**不是生产采集机制**。**块 B 不拓宽 `MatlabEngineProvider`、不经服务端 `run_simulation()` 跑用户模型。R6 前置(R1 P1):若 R6 spike 发现 R2026a 的可行采集形态确实需要另一套 Engine API,停手重新划范围,不在本卡内顺手拓宽服务端 provider。**
- **请 R1 裁的点**:① 上述「采集在客户端、服务端 Engine 非采集路径」是否符合 roadmap §5.2 + 数据边界的既定方向(我据 roadmap 判定为既定,非新决定);② 据此块 B 不动服务端 Engine 接口面,是否正确——以免块 B 误吞服务端仿真范围。

---

## 实测地基(`origin/main` ac747d8,Codex 取证;R1 无 repo,以下为自包含事实,实施前 Codex 复核)

### A. b1 解释请求契约 `core/domain/bridge_explanation.py`(待扩点)
```python
@dataclass(frozen=True)
class BridgeExplanationRequest:
    protocol_version: Literal["0.3-b1"]
    request_id: UUID
    diagnostic_kind: Literal["manual_error"]      # ← 决策 A 在此扩值
    matlab_release: str
    client_version: str
    error_text: str
    llm_processing_consent_confirmed: bool
```
Pydantic(`features/matlab_bridge/bridge_explanation_schemas.py`):`BridgeExplanationDiagnosticKind = Literal["manual_error"]`(待扩);`error_text` strip 后 1–4096、拒 NUL;`llm_processing_consent_confirmed` 须 `True`;`reject_sensitive_extra_fields`(交 `SENSITIVE_EXTRA_FIELDS`)。结果模型 `BridgeExplanationResult`(`status="completed"` / `mode="llm_error_explanation"` / `meaning` 1–1500 / `likely_causes` 1–4 / `next_steps` 1–5 / `caveats` 1–3 各 1–400 / `LikelyCause.supporting_signals` 1–6 各 8–200)。

### B. 服务端脱敏 + 输出隐私(`features/matlab_bridge/bridge_explanation_service.py`)
`explain()` 调 provider 前先 `redact_bridge_error_text(error_text)`(路径 → `[REDACTED_PATH]`、密钥 → `[REDACTED_SECRET]`、源码 → `[REDACTED_SOURCE]`);出口 `_validate_output_privacy` 命中 `contains_private_text` 即 `privacy_scan_failed` fail-closed,不替换后返回。

### C. route(`api/routes/matlab_bridge.py`)
`MatlabBridgeRoute` 固定顺序:loopback(403)→ `Content-Type: application/json`(415)→ `body_with_limit`(413)→ replay → handler。`MAX_BRIDGE_BODY_BYTES = 32 * 1024`(**route 入站上限**)。两端点同挂此 route:`/api/v1/bridge/diagnostic`(连通 stub)、`/api/v1/bridge/explanation`(b1,`Depends(get_matlab_bridge_explanation_service)`)。

### D. 敏感字段拒绝(`features/matlab_bridge/bridge_diagnostic_schemas.py`)
`SENSITIVE_EXTRA_FIELDS = {file_path, source_code, slx_path, workspace, stack, project_files, model_content, files}`。

### E. Engine 接口面(`core/interfaces/matlab_engine_provider.py`)
`MatlabEngineProvider(ABC)` **仅** `health_probe() -> None`;concrete `MatlabEngineSession` 另有 `run_simulation(fixture_path, *, timeout_s, cancel_event)` 等,但**不经 provider 暴露给服务层**。→ 见 §架构站位:块 B 不用它。

### F. decision 13 同步面
导出脚本 `scripts/export_bridge_schemas.py` 一次导出 6 个 schema(含 `bridge_explanation_request/result/error`);freeze/drift:`tests/features/matlab_bridge/test_bridge_explanation_schema_freeze.py`(含 `test_exported_bridge_schemas_do_not_drift`)、`test_bridge_explanation_schemas.py`;`Makefile` `verify-schema` 已把 bridge schema 纳入 drift 闸;契约文档 `docs/06_OUTPUT_CONTRACTS.md` §14.1。

---

## Stage 0 — 取证 / 基线检查(强制,decision 15)
```bash
git fetch origin
git status --short                                            # 须空(可白名单本卡 §文件清单未跟踪路径);否则停手报 PM
git rev-parse origin/main
git merge-base --is-ancestor <填真实 TASK-513 merge commit> origin/main   # 须为真
git show origin/main:docs/03_TASK_INDEX.md | grep -n "TASK-51[45]"        # 确认 514 空
git switch -c task/TASK-514-auto-capture-explanation origin/main
```
**若 main 实际与本卡 §实测地基不符 → 停手报 PM(decision 15)。**

---

## 设计点裁决(草案,交 R1 收口)

| 设计点 | 提议 |
|---|---|
| **DP-1 契约(决策 A)** | 把 `BridgeExplanationRequest.diagnostic_kind` 由 `Literal["manual_error"]` 扩为 `Literal["manual_error","auto_captured_error"]`(**值名提议**,R1/Codex 可定);`BridgeExplanationDiagnosticKind` 同步。**`/diagnostic` 连接 stub 的 `BridgeDiagnostic` 不动**(连通专用、不解释、v0.3-a 冻结)。**不新增端点**,沿用 `/explanation`。触发 decision 13 **仅限 explanation 契约**。`docs/06` 须注明 `diagnostic_kind` 在当前契约表示**输入来源**(R1 P2 命名债说明)。 |
| **DP-2 受控敏感诊断通道** | auto_captured 走**与 manual 相同或更严**的护栏,四条不变量:(a) **强制用户确认采集快照后才发**(`llm_processing_consent_confirmed` 仍须 `True`,且确认的是用户**看过的那份采集快照**);(b) **客户端在显示给用户前先做明显脱敏**(路径 / 密钥 / 源码),服务端 `redact_bridge_error_text` **二次脱敏不变**;(c) 复用 `SENSITIVE_EXTRA_FIELDS` 拒额外敏感字段;(d) 输出隐私扫描 fail-closed 不变。**自动采集比手动粘贴风险高**(程序抓更易裹进路径 / 源码 / 工作区),故 (a)(b) 是硬约束,**不得因"自动"省掉人确认**。 |
| **DP-3 体积** | `error_text` 仍 **≤4096**(沿用 b1);自动采集超长 → **客户端有界截断 / 摘要**后再发(保头部 + 关键行)。**不动 32KB 入站上限**。注意:32KB 是 route 入站、4096 是字段约束,**别混**;收敛 / 波形这类更大的结构化数据是 **b3**,不在块 B。 |
| **DP-4 客户端采集机制(`.m`)** | Add-on 在用户本机 MATLAB **进程内**采集——**仅从 `try/catch` 捕获的 `MException` 对象**提取**白名单字段**(见 §自动采集安全不变量 (1));**不用 `lasterr` / `lasterror` / `MException.last`**(R6 spike 实测:R2026a 受控探针里它们返回空 identifier/message/stack)。**不调任何 Engine API**。**R6 spike 已确认**:此形态不需另一套 Engine API,**不在本卡拓宽服务端 provider**。**会动客户端 `.m`**(513「不动 `.m`」是 513 范围;块 B 是新增,允许动 Add-on `.m`)。 |
| **DP-5 解释随来源** | 解释**核心逻辑不变**;`caveats` 文案按来源区分(manual:「仅基于你粘贴的报错文本」;auto_captured:「基于自动采集的报错文本」);prompt 可告知来源但**grounding 规则不变**(`is_inference` 恒 true、`confidence ∈ {low,medium}`、违禁断言集零命中等沿用 b1)。 |

---

## 协议流程(R1 P0-1,本版锁定)
b1 manual 流是**两段**:客户端先 `POST /diagnostic`(连通回执 ACK,校验 `request_id/status/mode`)→ 再 `POST /explanation`(同 `request_id`)。块 B auto 流**锁为方案 A:直发 `/explanation`,不走 `/diagnostic` ACK**。
- 理由:auto 采集时连接已活(Add-on 正从在跑的会话抓到报错);`/explanation` 调用本身会暴露连接错误,无需额外连通往返。
- **`/diagnostic` 连接 stub 保持 manual 专用、v0.3-a 字节冻结**;auto 文本**不得**伪装成 `diagnostic_kind="manual_error"` 发给 `/diagnostic`。故 **decision 13 范围仍仅限 explanation 契约**(不扩 diagnostic 契约)。
- manual 两段流**原样保留**;auto 单段流与 manual 两段流**分别做 E2E**(G-B5)。

---

## 自动采集安全不变量(R1/R6 一审 P0/P1,本版锁定)
**(1) 白名单采集(R1 P0-2;字段经 R6 spike 实测锁定)** —— 自动采集**采用白名单,不是先抓完整诊断再寄希望于正则脱敏**;采集源**仅为 `try/catch` 捕获的 `MException` 对象**(R6 spike:`lasterr` / `lasterror` / `MException.last` 在 R2026a 受控探针里返回空,不可作主源)。**锁定白名单字段 + 上限**:

| 字段 | 来源 | 上限 |
|---|---|---|
| identifier | `ME.identifier` | 128 chars |
| message | `ME.message` | 2048 chars(**非可信文本**,见下) |
| causes | `ME.cause`(最多 **3 层**) | 每层 identifier 128 / message 768 / stack 元数据 |
| stack | `ME.stack`(最多 **8 帧**) | 每帧仅 `name` 160 chars + `line`(整数) |

**明确禁止采集**:`ME.stack.file`(含本地绝对路径)、`getReport(...)` 完整文本、workspace 变量 / 值、命令历史、当前目录 / 用户名 / 主机名、源码正文 / 上下文、模型参数 / block 内容、完整 extended stack/report。
**`message` 是非可信文本(R6 负例实测)**:若用户代码自己把敏感值拼进 `error(...)` message,`ME.message` 会原样带出——故 `message` 仍须走**客户端脱敏 + 截断 + 用户确认 + 服务端二次脱敏**全链,白名单**不替代**脱敏。脱敏(客户端 + 服务端)是**第二道防线**;`stack.name` / `line` 仍可能含项目语义,须**限长 + 脱敏 + 用户可见确认**(R6 二审 P2)。

**(2) 不可变快照顺序(R1 P0-3 / R6)** —— 固定顺序,中途不得重采 / 重摘 / 再拼:
```
采集一次 → 白名单提取 → 客户端脱敏 → 有界截断/摘要 → 冻结快照 → 向用户显示这份快照 → 用户确认 → 发送完全相同的字节
```
用户确认的快照**必须 = 最终将发送的脱敏 + 截断后 payload**,不是另一个"预览版本"。验收须断言:取消确认 = **零网络请求**;发送 payload 与确认窗口快照**逐字节一致**;确认后 MATLAB 状态变化**不改变**待发内容。

**(3) fail-closed 触发面扩展(R1/R6)** —— 客户端采集失败 / 白名单提取或脱敏失败 / 预览不可生成 / 用户未确认,**一律 fail-closed 不发**。

**(4) 块 B 日志限制(R1/R6 P1)** —— 客户端**和**服务端日志均**不记**原始报错 / 路径 / 源码 / stack / workspace / 未脱敏文本;只允许长度、类别、哈希 / 请求 id 这类最小诊断信息。**哈希只能基于脱敏后的冻结快照或用不可逆 / 内容不可还原形式**,不得把原始报错变成可关联指纹(R6 二审 P2)。

**(5) 整体截断 + 标记(R1 P1;R6 spike)** —— 渲染进现有 `error_text` 前,**脱敏后总长仍硬限 4096 chars**;超限必须加**明确截断标记**(如 `[TRUNCATED_AUTO_CAPTURE]`),**不得静默截断**。

**(6) 来源标签不抬高可信度(R1/R6 P2)** —— `auto_captured_error` **只作来源标签**,不得让模型当成"更真实 / 更完整"的证明;解释仍"不确定就说不确定";来源分支**只改 `caveats` 文案**,**不得降低** `is_inference` / 置信度 / 输出隐私 validator。

---

## decision 13 同步清单(契约改 = 必逐项确认 + 贴 diff,缺一项 = 未完工)
```text
□ core/domain/bridge_explanation.py            — BridgeExplanationRequest.diagnostic_kind 扩值
□ features/matlab_bridge/bridge_explanation_schemas.py — BridgeExplanationDiagnosticKind 扩值
□ schemas/bridge_explanation_request.schema.json — 跑 `python -m scripts.export_bridge_schemas` 重生成
□ tests/features/matlab_bridge/test_bridge_explanation_schema_freeze.py — 期望值更新
□ tests/features/matlab_bridge/test_bridge_explanation_schemas.py — 新枚举值边界测试
□ docs/06_OUTPUT_CONTRACTS.md §14.1 — diagnostic_kind 行 + 来源语义
□ scripts/export_bridge_schemas.py 重跑(脚本本身不改)+ test_exported_bridge_schemas_do_not_drift 绿
□ Makefile verify-schema — 已含 bridge schema,无需改(确认仍绿)
□ 契约测试:`/explanation` 接受两值(manual_error / auto_captured_error)、拒未知 diagnostic_kind;domain↔Pydantic round-trip 两值均成立(R1 P1)
□ 不变项测试:error_text 仍 1–4096 + 拒 NUL、llm_processing_consent_confirmed=true 仍必需(扩值不破这些;R6 P1)
□ `/diagnostic` 仍拒 auto_captured_error(与 §协议流程 方案 A 一致;R1 P1)
□ **schema 口径(R6 二审 P1)**:`export_bridge_schemas.py` 重导 6 个 schema,但本次**仅 `bridge_explanation_request.schema.json` 应有 diff**;`bridge_explanation_result/error.schema.json` 及其余 4 个**确认无漂移**(别误解成"只管 request 文件")
```
不涉 `project_type` Literal,故**不触** `core/prompts/*.yaml` 的 project_type 段 / `docs/05`。DP-5 的 caveat/prompt 文案改属**内容改、非 schema 约束改**,不入本清单,但仍要测(G-B7)。

---

## 验收门(机制 + 确定性护栏;质量评估留 seam)
- [ ] **G-B1 契约 freeze + 新枚举**:explanation 三 schema freeze 扩值后重生成仍绿;`auto_captured_error` 走通、`manual_error` 不回归;decision 13 清单各文件 diff 齐。 [CI]
- [ ] **G-B2 客户端自动采集**:Add-on 能从本地 MATLAB 报错自动采集(spike 实证 R2026a);采集后**强制用户确认快照才发**(无确认不发);客户端预脱敏(路径 / 密钥 / 源码 sentinel)。 [本机]
- [ ] **G-B3 服务端护栏不回归**:auto_captured 与 manual 走同一 `redact_bridge_error_text` + 输出隐私扫描 fail-closed;provider 输入 + HTTP 输出泄漏测试(Windows drive / UNC / POSIX / `file://` / 源码 sentinel)全绿;**测试语料补嵌入式敏感内容**(workspace 值 / 连接串 / 用户目录 / 源码行 / 函数参数值),不只路径(R1/R6 P1)。 [单测]
- [ ] **G-B4 有界**:auto_captured 路径 `error_text ≤4096` 成立、超长客户端截断 / 摘要;32KB 入站不变。 [单测 + 本机]
- [ ] **G-B5 端到端**:Add-on 自动采集 → `/explanation`(`diagnostic_kind=auto_captured_error`)→ 解释结果显示;**旧 manual E2E 保留**;服务端 deadline / timeout 映射沿用 b1(502/503/504)。 [本机 e2e]
- [ ] **G-B6 CI 卫生**:`ruff` / `ruff format --check` / `mypy core/ adapters/ features/ api/` / 全 `pytest`(fake provider,CI 不真打 LLM)/ `check_repo_hygiene.sh` 全绿;**b1 / b2-0 / b2-1 块 A 无回归**。 [CI + 本机]
- [ ] **G-B7 来源区分**:`caveats` / prompt 按来源区分(auto_captured 文案「基于自动采集的报错文本」),grounding 规则不变;加确定语气对抗样例沿用 b1。 [单测]
- [ ] **G-B8 不可变快照(R1 P0-3)**:取消确认 = **零网络请求**;发送 payload = 确认窗口快照**逐字节一致**;确认后 MATLAB 状态变化不改变待发内容。 [本机]
- [ ] **G-B9 白名单 + fail-closed(R1 P0-2;R6 spike 字段)**:采集只含白名单字段(identifier / message / causes≤3 / stack≤8 仅 `name`+`line`),**禁 `ME.stack.file` / `getReport` 全文 / workspace / 源码**;单测对含 workspace 值 / 连接串 / 用户目录 / 源码行 / 函数参数值的样例证**不进 payload**;**负例:用户把敏感值拼进 `error()` message → message 仍经脱敏 + 用户确认**;采集 / 脱敏 / 预览失败或未确认 → **不发**。 [单测 + 本机]
- [ ] **G-B10 日志限制(R1/R6 P1)**:客户端 + 服务端日志均不含原始快照 / 路径 / 源码 / stack / workspace;只元数据(长度 / 类别 / 哈希 / 请求 id)。 [单测]

---

## 不做(明确排除)
- ❌ 收敛 / 波形 / CSV/MAT(b3,TASK-515)。
- ❌ 改 b1 现有 `explain()` 核心逻辑 / 签名(可加来源分支,但不破现有 `manual_error` 行为)。
- ❌ 动 `/diagnostic` 连接 stub 契约与 v0.3-a freeze(字节不动)。
- ❌ 拓宽 `MatlabEngineProvider` / 经服务端 `run_simulation()` 跑用户模型。
- ❌ 上传完整工程(数据边界)。
- ❌ 跨 MATLAB 版本(R2026a)。
- ❌ 动 route 固定顺序与 `MAX_BRIDGE_BODY_BYTES`。
- ❌ seam 前上 production / 作能力宣传(不变量 14)。

---

## 实施约束(全程)
- **decision 11**:同步实现 + async 侧**一处** `to_thread`;**禁 `logger.exception`**(用 `logger.error` + 结构化字段);日志 / 异常 / 对外结果不含 `error_text` 正文 / 绝对路径 / 源码。
- **decision 13**:契约改列清单贴 diff(见上)。
- **decision 15**:main 实际与本卡不符 → 停手报 PM。
- **decision 21**:块 B 在 `features/matlab_bridge/` 内,**不 import `features/explanation/` 私有结构**(bridge 解释是其自有 service,与 MCS explanation 分开);跨 feature 共享只在 `core/` 公开 contract。
- **seam 前不上 production**(不变量 14);确定性护栏只**降低已枚举危险失败概率**,非完整保证。
- **不重开已锁**:v0.3-a freeze、b1 收窄、b2-0 A–D + G0–G10、b2-1 块 A 终审——审过的不翻案。
- **行尾 / 字节级**:照 `20260602-08`(行尾决策是它,非 decision 18)。
- **git**:从最新 `origin/main` 切 `task/TASK-514-auto-capture-explanation`;`git diff --stat origin/main` 与 §文件清单一致;完工 03 索引 🔲→🔍,PM 合并后 → ✅。

---

## 文件清单(草案,Codex 以 Stage 0 复核)
**生产(契约)**:`core/domain/bridge_explanation.py`(改:扩值)、`features/matlab_bridge/bridge_explanation_schemas.py`(改:扩值)、`schemas/bridge_explanation_request.schema.json`(重生成)、`docs/06_OUTPUT_CONTRACTS.md`(改 §14.1)。
**生产(服务/prompt)**:`features/matlab_bridge/bridge_explanation_service.py`(改:来源分支 + caveat 文案,**不破现有逻辑**)、bridge 解释 prompt yaml(改:来源提示,版本化)。
**客户端**:`clients/matlab_bridge/app/+mxa/+bridge/`(改:自动采集 + 采集快照确认 + 客户端预脱敏 + payload 标 `auto_captured_error`)。
**测试**:`test_bridge_explanation_schema_freeze.py` / `test_bridge_explanation_schemas.py`(改:新枚举 + drift)、bridge 解释服务测试(改 / 增:来源分支 + 护栏不回归 + 输出泄漏)、客户端采集单测 + 本机 e2e。
**任务卡 / 索引**:本卡(`create_file`);完工更新 `docs/03_TASK_INDEX.md`(🔲→🔍)。

---

## 关联决策
decision 11(to_thread + 禁 logger.exception)/ decision 12 v0.4(双审)/ **decision 13(本卡触发)** / decision 15 / **decision 21**(EvidencePack/feature boundary)/ **`20260602-08`(保行尾;非 decision 18)** / **不变量 14**(seam 前不上 production)/ **TASK-511 b1**(沿用其契约 / 护栏 / timeout)/ **TASK-513 b2-1 块 A**(不动其实现;服务端 Engine 为 dev/test)。

---

## 审查与派发
- **三审 ACK + R6 spike 通过(2026-06-23)**:spike 实测 `try/catch` 捕获 `MException` 可稳定取白名单字段、不需另一套 Engine API、不拓宽服务端 provider;字段 + 上限已锁进 §安全不变量 (1)。**审查 + 摸底全部完成。**
- **下一步:派 Codex 建**(三道门全齐)。派单注意:① Stage 0 `git status` **白名单已预放的 `docs/tasks/task-514-*.md` / `task-515-*.md`**(PM 预放,非脏状态),其它脏状态照旧停手报 PM;② 本卡已由 PM 预放 `docs/tasks/`,Codex **不再 `create_file` 本卡**;③ 完工补 `docs/03_TASK_INDEX.md` 的 **TASK-514 行** + 🔲→🔍;④ **decision 13 全清单逐项贴 diff**(缺一项 = 未完工)。
- **实现门**:契约决策 A(**PM 已拍**)+ R1 审(**三审 ACK**)+ R6 spike(**通过**)+ **decision 13 全清单**(实现期);完工 PM 看 diff + 验收门勾选 → 合并。
- **brief**:本卡 §实测地基 = 自包含事实(实测自 `origin/main` ac747d8);R1 无 repo、无记忆,以本卡为准。
