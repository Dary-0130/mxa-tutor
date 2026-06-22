# TASK-511:MATLAB bridge LLM 报错解释(v0.3-b / b1)

## 状态

🔲 v0.5 五修(2026-06-21,**R6 已 PASS;待 R1 确认 ACK 修法**)。据 `origin/main`(#109 `6bc9c76`)取证设计。**R6 v0.4 复审 = PASS 无 P0**(机制落地 / timeout 账闭合 / `webwrite` 已处理 / 收窄是干净减法,明说可派 Codex)。**R1 v0.4 复审 = 仅 1 个新 P0**(P0-1/P0-2 已确认闭合、质量评估移 seam 属正当收窄):**旧 diagnostic ACK 文案"本版本…不提供报错解释"会与实际解释同屏自相矛盾**——v0.5 按 R1 修法**不动服务端契约**(diagnostic endpoint / `consume()` / receipt JSON / 0.3-a freeze + E2E 全不动),改客户端 ACK 渲染为**本地中性 formatter**(读 `status/mode/request_id`,**不显示服务端旧 `message` 字段**)。同收 R1+R6 的 P1/P2:retry 消歧(无第二层重试)、`max_tokens` 锁值、`wait_for` 是 deadline 非线程中断、error 模型不复用旧 `BridgeErrorResponse` Literal、状态码×code 配对矩阵测试、`已挡住`→`降低已枚举危险失败概率`、**seam 通过前 `matlab_bridge_enabled` 不得上 production / 不作能力宣传**、删重复 item 9、timeout 名统一。**一处待你拍**:`case_kind`/`compute_verdict` 是否留 b1(你上轮要留;R1 建议移 seam,因 b1 无 runner/case 消费它)——v0.5 暂按你"留 b1"+ R1 语义澄清,见 §设计点裁决 DP-3。v0.3 已锁契约 / 映射 / timeout **全保留**。**拆分定稿 `v0_3b-split-final-skeleton.md` 经 Codex 实测未入 `origin/main`**,b1 定义据交接包 §4 + decision 23 + A–I 取证重建。

---

## 背景与定位

- 本卡是 **v0.3-b 拆分定稿**(`T0 → b1 ∥ b2-0 → b2-1 → b3`)里的 **b1**,**与 b2-0(TASK-512)并行**,互不依赖——起 b1 不必等 b2-0 完工。
- **b1 只做一件事**:在 **v0.3-a 已合并的传输桥**之上挂 LLM 报错解释——桥现在能传的 `manual_error` diagnostic → **服务端** bridge 专用 prompt + validator 的 LLM 解释 → 经**新增的版本化"解释结果"契约**回传客户端显示。
- **b1 明确不做**(见 §范围-不做):不接 MATLAB Engine、不改采集源(输入仍是用户手动粘贴的 `manual_error`)、不改 route 固定顺序、不动 v0.3-a 连接回执语义、不直接复用 `features/explanation`。
- **单拆理由**:把"LLM 报错解释质量"这块风险独立验,不和 Engine substrate(b2-0)、自动采集 / 收敛 / 波形(b2-1 / b3)混。
- **b1 验收门 = 机制 + 确定性护栏(≠ 质量门、≠ b3 总门)**:b1 只保证"传输→解释→显示的机制对" + "确定性护栏**降低已枚举危险失败的概率**"(全机器可判,§验收门)——护栏挡的是已枚举模式,**同义改写仍可能绕过,故 seam 通过前不上 production**(不变量 14);**"解释在事实上对/有用"的质量评估推迟到挂起 seam `bridge 报错解释·小规模质量测试`**(PM 决策)。**decision 23 §2.2 的 b3 总门不是 b1 门**,本卡不引入那套。

---

## 实测地基(来自 `origin/main` #109 A–H 取证;GPT 无 repo,以下为自包含事实,**实施前 Codex 复核**)

### A. 契约底座 `core/domain/bridge_diagnostic.py`(纯 domain,不 import Pydantic)

```python
@dataclass(frozen=True)
class BridgeDiagnostic:
    protocol_version: Literal["0.3-a"]
    request_id: UUID
    diagnostic_kind: Literal["manual_error"]
    matlab_release: str
    client_version: str
    error_text: str
    consent_confirmed: bool

@dataclass(frozen=True)
class BridgeDiagnosticReceipt:
    request_id: UUID
    status: Literal["received"]
    mode: Literal["connectivity_stub"]
    message: str
```

`schemas/bridge_diagnostic_request.schema.json` 约束(实测):`protocol_version` const `"0.3-a"`、`diagnostic_kind` const `"manual_error"`、`matlab_release` pattern `^R20[0-9]{2}[ab]$`、`client_version` pattern `^[A-Za-z0-9.\-]{1,32}$`、`error_text` minLength 1 / maxLength 4096、`additionalProperties: false`。`bridge_diagnostic_receipt.schema.json`:`status` const `received`、`mode` const `connectivity_stub`。两者均有 freeze test(`tests/features/matlab_bridge/test_bridge_diagnostic_schema_freeze.py`)。

### B. service `features/matlab_bridge/diagnostic_service.py`

`DiagnosticService.consume(diagnostic: BridgeDiagnostic) -> BridgeDiagnosticReceipt` 是**同步** stub:构造固定回执(`status="received"`、`mode="connectivity_stub"`、`message=BRIDGE_RECEIPT_MESSAGE`)、`logger.info` 仅记元数据(request_id / matlab_release / client_version / payload_chars / status / latency_ms,**不记 error_text 正文**)、返回。`BRIDGE_RECEIPT_MESSAGE = "连接成功。本版本仅验证诊断信息传输,不提供报错解释。"`

`bridge_diagnostic_schemas.py`:`_BridgeBaseModel(model_config=ConfigDict(extra="forbid", from_attributes=True))`;`BridgeDiagnosticRequest`(Pydantic 镜像 + `reject_sensitive_extra_fields` / `reject_nul` / `require_confirmed_consent` 三 validator + `to_domain()`);`BridgeDiagnosticReceiptModel`(+ `from_domain()`);`BridgeErrorResponse`(`error: BridgeErrorCode` + `message`)。`SENSITIVE_EXTRA_FIELDS = {file_path, source_code, slx_path, workspace, stack, project_files, model_content, files}`(route 层之外的二道防线)。`BridgeErrorCode = Literal["matlab_bridge_forbidden","bridge_payload_too_large","bridge_unsupported_media_type"]`。

### C. route `api/routes/matlab_bridge.py`

`MatlabBridgeRoute.get_route_handler` 在 FastAPI 读 JSON / Pydantic **之前**的固定顺序:**loopback 检查(403 `matlab_bridge_forbidden`)→ media_type 必须 `application/json`(415)→ `body_with_limit(32KB)`(413)→ replay body → `original_handler`**。`MAX_BRIDGE_BODY_BYTES = 32*1024`。处理器:

```python
@router.post("/api/v1/bridge/diagnostic", response_model=BridgeDiagnosticReceiptModel, responses={403,413,415,422})
async def bridge_diagnostic(request_body: BridgeDiagnosticRequest) -> BridgeDiagnosticReceiptModel:
    service = get_matlab_bridge_diagnostic_service()
    receipt = service.consume(request_body.to_domain())
    return BridgeDiagnosticReceiptModel.from_domain(receipt)
```

依赖工厂 `from api.dependencies import get_matlab_bridge_diagnostic_service`。**处理器是 `async`,b1 可在此 `await`**;Pydantic 校验在处理器入参完成。**route 门控 / 注册见 §I(R6 二审实测)**:`matlab_bridge_enabled` 仅在 `APP_ENV=development|test` 可启,默认不注册 bridge route。

### D. 客户端 `clients/matlab_bridge/app/+mxa/+bridge/`

`MatlabBridgeApp.m`:`ProtocolVersion="0.3-a"`、`ClientVersion="0.1.0"`、`DiagnosticKind="manual_error"`、`TimeoutSeconds=10`。UI 组件:`InputTextArea`(粘贴错误)/ `PreviewTextArea`(脱敏预览)/ `SubmitButton`/ `StatusLabel`/ `ResponseTextArea`(标签"连接回执")。`submitManualError`:`updatePreview`(`redactDiagnosticText` 脱敏)→ `ConfirmFunction`(默认 `uiconfirm`)→ `buildPayload`(protocol/uuid/kind/`matlab_release="R"+version`/client_version/error_text/`consent_confirmed=true`)→ `postDiagnostic`(`webwrite` POST `/api/v1/bridge/diagnostic`,`weboptions MediaType application/json + Timeout`)→ `LastReceipt=receipt`、`ResponseTextArea = formatReceipt(receipt)`。`formatReceipt.m` 读 `message/status/mode/request_id` 拼行显示。`validateBaseUrl.m`:http 仅许 localhost、https 放行、禁 userinfo。tests:`headless_bridge_e2e.m` / `run_headless_e2e.py` / `test_redaction_and_url.m`。

### E. LLM service 范例(b1 服务端解释照此搭)

`adapters/llm/__init__.py` 导出 `DeepSeekTextProvider`;接口 `core.interfaces.llm_provider` 的 `TextProvider`(`chat(messages, *, json_mode, timeout, max_tokens) -> LLMResponse`)。`features/paper/paper_spec_service.py` 金样板:`async extract` → cache → `extract_uncached`:`await asyncio.to_thread(self._text_provider.chat, messages, json_mode=True, timeout=self._timeout, max_tokens=self._max_tokens)` → 同步 `_parse_and_validate`(`json.loads` → `PaperSpecModel.model_validate(payload).to_domain()` → 后置 validators → 失败一律 `logger.error(...)`(**非 `logger.exception`**)+ `raise PaperSpecGenerationError(_GENERATION_ERROR_MESSAGE) from None`)。prompt 经 `load_prompt_template()` 载入、带 `.version`。**纪律测试 `test_only_one_asyncio_to_thread_in_service` 仅存在于 `test_paper_plan_service.py` / `test_paper_tuning_service.py`(paper_spec 有多处 to_thread、不受其约束)**;b1 解释服务只有一处 LLM 调用,照 plan/tuning 的"恰一处 to_thread"模式并配套该纪律测试。

### F. `features/explanation`(**b1 不可直接复用**——以下是根因)

模块是**静态结构讲解**层:`EvidenceBuilder(纯结构化,不调 LLM)→ ExplanationService(LLM)→ ClaimEvidenceValidator(11 规则,Recoverable/Fatal/Pack 三档失败)→ MarkdownRenderer`。grounding = 结构化 `EvidencePack` + `evidence_ids` 引用。`core/prompts/simulation_explanation_pack.yaml`(version v0.2.3)system prompt 原文(节选实测):"static MATLAB/Simulink project explanation. Use only the provided EvidencePack. **Do not claim that a simulation was executed.**" 禁令:不得说波形 stable/validated/verified、不得说 simulation run proves/confirms/demonstrates、不得 invent `simulation_run_result` evidence、不得 cite 不在 EvidencePack 的 evidence_ids;`is_inference=true` 时 confidence 必须 low/medium 不得 high。claim_type 枚举 = `project_purpose|reading_order|connection_logic|parameter_reason|modification_advice|observation_point|simulink_caveat|uncertainty_boundary`。`_claim_validator.py` 有 `RUNTIME_ASSERTION_WORDS=(运行结果/波形/稳定性已验证/仿真已证明/仿真证明/已验证稳定)`、`STRONG_INFERENCE_WORDS=(必然/一定/证明/最优)`。

**为何 b1 不能复用**:b1 解释的是用户那次运行的**真实报错文本**(无 `EvidencePack`、无 `evidence_ids` 可引、来源是用户而非 mxa-tutor 跑出的结构);claim 类型、grounding 机制、validator 集全不同。**共享 DNA 仅三条**:别声称(mxa-tutor)已跑 / 已验证仿真 + 标注推断且推断不得 high 置信 + 教学语气。故 b1 须另起 **bridge/runtime 专用 prompt + validator**(DP-5)。

### G. typed error `core/domain/exceptions.py`

基类 `MxaError`;LLM 系 `LLMError`(`LLMAuthError`/`LLMQuotaError`/`LLMRateLimitError`/`LLMServerError`/`LLMTimeoutError`);生成类统一 `*GenerationError`/`*Error` 模式(`OverviewGenerationError`/`PaperSpecGenerationError`/`PaperPlanGenerationError`/`PaperTuningError`/`ChatGenerationError`)。**目前无任何 bridge 系 typed error** → b1 照此模式新增(DP-5,建议 `BridgeExplanationError(MxaError)`)。

### H. eval + decision 25(b1 质量门判分复用)

`docs/decisions/20260620-25-...`(decision 25):双轴 `ExecutionStatus = Literal["succeeded","case_failed"]`(case 是否跑完 vs 中途真异常)× `Verdict = Literal["pass","partial","fail","not_evaluated"]`(确定性判定);不变量 `case_failed → not_evaluated`、`succeeded → {pass,partial,fail}`;`compute_verdict(*, case_kind, execution_status, rule_results) -> Verdict` 按 `case_kind` 分派(`missing_param` 死规则全 pass→pass / 任一 fail→fail、无 partial;`material_to_plan` 软指标→pass/partial/fail)。**核心 = 判分错(规则失败,execution 仍 succeeded)与真异常(IO/序列化/provider→case_failed+not_evaluated)分离**;**judge / 漏报盲评 v0.1 单 case 不适用、留 v0.2 多 case**。`eval/run_paper_eval.py`:`CASES_ROOT = Path("eval/cases/paper_to_model")`;现有 case kind = `material_to_plan` / `missing_param`(各带 `case_README` + `golden/` + `input/`),另有 `scoring_template.md` / `verification_method.md`。

### I. R6 二审补充实测(同 `origin/main` #109;Codex `git show` 取证,**当 ground truth**)

1. **app 启动即要必填 `deepseek_api_key`**:`api/main.py` 模块底 `app = create_app()`;`create_app()` 立即 `settings = get_settings()`;`AppSettings.deepseek_api_key: str` **必填**;现有测试 `test_lifespan_fails_when_deepseek_api_key_missing` 印证缺 key 即失败。→ **G0 不能写"真无 key 进 route 后友好降级"**(app 创建阶段就炸),改为 fake provider / provider 抛 typed error 时 route 友好返回(状态码按§契约改动映射表:auth/quota→503、timeout→504、坏 JSON/validator→502;§验收门 G0)。
2. **LLM 单次往返实测 7.77s**(`DeepSeekTextProvider.chat(json_mode=True)` 真打一条 MATLAB 报错解释,`deepseek-v4-flash`,`provider_latency_ms=7769`,JSON 可解析)→ **同步单回合可行,但客户端 `TimeoutSeconds=10` 太紧**(顺利小请求已近 10s,真实网络 / 更多输出 / retry 会先超时)。
3. **error handler 落点**:`api/middleware/error_handler.py` 现有 leaf handler 覆盖 `PaperSpecGenerationError` / `PaperPlanGenerationError` / `PaperTuningError` 等;新 `BridgeExplanationError(MxaError)` **若不注册只会走 `MxaError → 500 internal_error`** → 必须显式注册(建议 `502 bridge_explanation_failed`)+ 测不泄漏 `error_text`。
4. **依赖注入用共享 provider**:`api/dependencies.py` 现有 `get_text_provider(request)` 从 `app.state.text_provider` 取**共享** provider(service 可新建、**provider 复用**)→ `get_matlab_bridge_explanation_service` 须 `Depends(get_text_provider)` / 从 `request.app.state` 取,**禁在 dependency 里 `DeepSeekTextProvider(...)` 现起**。
5. **prompt loader 花括号坑**:`load_prompt_template(filename)` 读 `core/prompts/*.yaml` 的 `version/description/system/user`;`build_messages()` 一处用 `template.user.format(...)`、`_render_user()` 是安全字符串替换 → bridge prompt 的 YAML 里若放 JSON 示例 `{meaning,...}`,**不能直接 `.format()`**,要走 `_render_user` 风格替换或转义花括号。
6. **schema 导出 / drift 实情**:实际脚本 `scripts/export_bridge_schemas.py`(**非 tools 路径**);`Makefile export-schema` 只跑 overview;CI = `ruff / mypy / pytest / hygiene`,**不自动导出 / 验 bridge schema drift** → decision 13 清单写准该脚本 + 加 schema drift 测试或 make target。
7. **route 门控**:`matlab_bridge_enabled` 仅 `APP_ENV=development|test` 可启,默认不注册 bridge route;新增测试须显式 `MATLAB_BRIDGE_ENABLED=true`。新 explanation 端点须挂在 `api/routes/matlab_bridge.py` **同一个 `router = APIRouter(..., route_class=MatlabBridgeRoute)`** 下,否则绕过 loopback/415/413/replay 防线。
8. **webwrite 读不到 5xx body(R6 实测)**:R6 在本机 MATLAB 实测——`webwrite` 命中 5xx 直接抛 `MATLAB:webservices:HTTP5xxStatusCodeError`,异常 `message` 只含状态短语、`cause=0`,且服务端**根本没收到请求**(`SERVER_SEEN=[]`,本机代理 / loopback 设置影响)。→ **客户端错误路径不得依赖服务端 JSON body**,须按 `ME.identifier` + 固定 fallback 文案显示"解释失败";"能否读 JSON body"仍留实施期实测(§实施约束)。
9. **retry 总耗时账(R6 实测)**:`adapters/llm/deepseek.py` `DEFAULT_RETRY_COUNT = 3`、backoff `0.5/1.0/2.0`(合 3.5s)→ **最坏墙钟 = 4 × provider_timeout + 3.5s**。**不能用 provider 默认 30s**(最坏 4×30+3.5=123.5s,客户端 60s 必炸)。R6 建议并 v0.3 锁:**bridge 单次 `provider_timeout_s=12`、`server_deadline_s=55`、客户端 `ExplanationTimeoutSeconds=60`**(最坏 4×12+3.5=51.5s < 55 < 60);若实施期单次需 15s 则客户端升 ≥70s。R6 另补一次实测(`prompt_tokens=297`/`completion_tokens=671`/`7.25s`)印证同步可保留,但非上界——G4"稳不住实施前切 C"保留。

---

## 范围

### 做什么(b1 交付物)

1. **bridge 报错解释服务**(落点 `features/matlab_bridge/`,与 `diagnostic_service.py` 同目录):新增 **`BridgeExplanationService`**,**`DiagnosticService.consume()` 字节级不动**(同步 stub、仍是 0.3-a 连接回执);新服务**不调用 `consume()`**。新服务:
   - `__init__(self, text_provider: TextProvider, prompt_template, *, provider_timeout_s=12, server_deadline_s=55, max_tokens=DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS)`(provider **复用** `app.state.text_provider`,见 §I-4,**不在构造里新起 provider**);`DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS=2048`(R6 实测 completion≈671,2048 足够承载最大合法 JSON;PM 可调,§契约改动)——**不留空参**(R1-P1-3);
   - `async def explain(self, request: BridgeExplanationRequest_domain) -> BridgeExplanationResult`:**恰一处** `await asyncio.to_thread(self._text_provider.chat, messages, json_mode=True, timeout=provider_timeout_s, max_tokens=self._max_tokens)`,外裹 `asyncio.wait_for(..., timeout=server_deadline_s)` 作服务端整体 deadline;+ 同步 `_parse_and_validate`;
   - **retry 边界(已锁,R1-P1-2 / R6-P1-1)**:`BridgeExplanationService` **不加业务级 retry / repair / fallback**;共享 `TextProvider` 既有内部 `retry_count=3` 不变、已计入 55s deadline(最坏 `4×12+3.5=51.5s`,§I-9);**禁第二层重试**;配 `provider.chat` **恰一次**调用次数测试。**注意:`wait_for` 是响应 deadline、非线程硬中断**——超时只让本次请求返 504,线程内 sync provider 仍跑到 SDK timeout 自然结束(dev/test 范围可接受);测试用 fake slow provider + patch deadline 验 `wait_for 超时→504`,**不用真 55s sleep**;
   - **错误映射(已锁,R1-P0-2 / R6-P0)**:catch `LLMTimeoutError` / `wait_for` 超时 → `raise BridgeExplanationTimeoutError(...) from None`(→504);catch `LLMAuthError|LLMQuotaError|LLMRateLimitError|LLMServerError` / 共享 provider 不可用 → `BridgeExplanationUnavailableError(...)`(→503);坏 JSON / schema / validator / 隐私扫描命中 → `BridgeExplanationError(...)`(→502)。**一律 `logger.error` + 结构化字段 + `from None`,不重试、不降级**(fail-closed);
   - **服务端二次脱敏**(R1-P0-4):调 provider **前**对 `error_text` 再做一道 redaction(Windows 盘符 / UNC / POSIX / `file://` / 源码 sentinel);`supporting_signals` 后续只能引用**这份脱敏后送入 provider 的文本**的子串(§契约改动);
   - 配套 `test_only_one_asyncio_to_thread_in_service`(AST/inspect 断言本服务恰一处 to_thread)。
2. **bridge 专用 prompt + validator(grounding hygiene + 隐私扫描,R1-P1-3/P1-4)**:新 prompt yaml `core/prompts/bridge_error_explanation.yaml`(version `v0.1`,**事件事实 + 通用知识两层 grounding** + 注入分隔符)+ bridge validator(typed,**fail-closed**)。validator 规则:① 每 cause 的 `supporting_signals` 为**脱敏后送入 provider 文本**的精确子串、**单项 ≥ 最小有效长度、拒纯标点 / 占位符(如 `[REDACTED_PATH]`)/ 重复项**;② `is_inference` 恒 true、confidence ∈ {low,medium}、`caveats` 恒 ≥1;③ **"编造标识"检查只针对事件专属标识,MATLAB 内置命令(`which`/`ver`/`license` 等)走版本化 allowlist 放行**;④ `meaning` 只解释错误含义、**不得新增环境事实**;⑤ **隐私扫描在最后**(parse→schema→grounding→privacy),命中绝对路径 / 长源码 / 密钥 → **直接 fail-closed 返回 502,不做替换**。**YAML 内 JSON 示例花括号走 `_render_user` 风格 / 转义,不直接 `.format()`**(§I-5)。
3. **版本化"解释结果"契约(已锁,protocol `0.3-b1`)**:新 `BridgeExplanationRequest` + `BridgeExplanationResult` + 各自嵌套模型 `LikelyCause` / `NextStep`(字段与边界见 §契约改动)+ `schemas/*.json` + freeze + 边界 + round-trip(decision 13 全清单)。**0.3-a 连接回执契约字节不动、freeze 不碰。**
4. **route 接线(已锁 = B + 两段同步)**:新端点 `POST /api/v1/bridge/explanation` 挂在 `api/routes/matlab_bridge.py` **同一 `router`(`route_class=MatlabBridgeRoute`)**(§I-7;同享 loopback/415/413/replay + body≤32KB + 敏感字段拒);新 handler `await` 解释服务、**不调 `consume()`**;**现 `/api/v1/bridge/diagnostic` handler 字节不动**。
5. **依赖接线**:`api/dependencies.py` 加 `get_matlab_bridge_explanation_service`,**`Depends(get_text_provider)` / 从 `request.app.state` 取共享 provider**(§I-4),禁现起 `DeepSeekTextProvider(...)`。
6. **typed errors + handler 注册(三状态,已锁)**:`core/domain/exceptions.py` 加 `BridgeExplanationError(MxaError)`(→502)、`BridgeExplanationUnavailableError(MxaError)`(→503)、`BridgeExplanationTimeoutError(MxaError)`(→504)三 leaf;`api/middleware/error_handler.py` **各注册显式 handler**(或一个 bridge error 携冻结 reason/status enum——但 handler + OpenAPI/freeze/客户端测试须同表,§契约改动映射表),否则只走 `MxaError → 500`;测 provider fail / invalid JSON / validator fail / 隐私命中 **不泄漏 `error_text`**。
7. **客户端两段流 + ACK 中性显示(R1-P0-1 修法,不动服务端契约)**:客户端拆**两个 protocol 常量** `DiagnosticProtocolVersion="0.3-a"` / `ExplanationProtocolVersion="0.3-b1"` + **两个 payload builder**(R1-P1-2)。`submitManualError`:生成**一次** UUID + **一份冻结**脱敏文本 → POST diagnostic → **校验 ACK 的 `request_id`/`status`/`mode`** 通过后 → 再 POST `/api/v1/bridge/explanation`(**同 `request_id` + 同冻结文本**)→ 校验返回 `request_id` 一致 → 渲染;第二步失败 **ACK 仍保留**。**ACK 区改用本地中性 formatter**(读 `status`/`mode`/`request_id`,如"连接成功,诊断信息已接收。状态:received 模式:connectivity_stub 请求 ID:…"),**b1 客户端不显示服务端旧 `message` 字段**(旧文案"…不提供报错解释"会与实际解释自相矛盾);`BRIDGE_RECEIPT_MESSAGE` / receipt JSON / `/api/v1/bridge/diagnostic` / `consume()` / 0.3-a freeze + E2E **全字节不动**。**错误显示按 `ME.identifier` + 固定 fallback 文案**(§I-8)。独立 **`ExplanationTimeoutSeconds=60`**(不复用 10s);`uiconfirm` 文案明写"脱敏文本将发往服务端、由 LLM 生成解释",explanation 请求带专用 `llm_processing_consent_confirmed=true`。`formatExplanation.m`:原因显示为"可能原因(中/低置信)"、**始终显示 caveat 与推断标记**,**ACK 永久独立、解释失败不覆盖中性 ACK**。`ClientVersion` 0.1.0→0.2.0(pattern 不变、不碰 freeze;同步核 `.mltbx` ToolboxVersion + 装后版本断言)。客户端仍发 `manual_error`。**3 项 ACK 测试**:① diagnostic HTTP 响应仍含旧 `message` 文案(服务端未变);② b1 UI **不出现**"不提供报错解释";③ explanation 失败后中性 ACK 仍在。
8. **b1 = `case_kind="error_explanation"` 确定性判定 + 确定性 validator 单测(质量评估推迟 seam)**:b1 在 `compute_verdict` 注册 `case_kind="error_explanation"`(**无 partial**)+ **确定性判定映射**,并以 **fake provider 单测**喂构造输出验之(护栏 + verdict 逻辑)。**verdict 映射(确定性,b1)**:provider/网络/IO/产物写出异常 → `case_failed + not_evaluated`;模型坏 JSON / schema / validator / 隐私命中 → `succeeded + fail`;确定性护栏全过 → `succeeded + pass`。**语义澄清(R1-P1-1)**:此处 `pass` **仅代表"确定性护栏通过",绝不代表解释正确 / 有用**;改的是 `eval/` 现 evaluator 的 verdict 模块(与 `run_paper_eval` 同框架但**新增 case_kind 分支、不接 paper evaluator**),完工注明实际改的文件。**(待你拍:R1 建议把 `case_kind`/`compute_verdict` 也移 seam——b1 无 runner/case 消费它;若移,b1 直接单测 schema / grounding-hygiene / privacy validator + route 错误映射 + 客户端 E2E 即闭合 G0–G6。见 §设计点裁决 DP-3。)** **整体推迟到挂起 seam `bridge 报错解释·小规模质量测试`**(PM 决策):真打 LLM 的 runner `eval/run_bridge_error_eval.py` + `--manual-scores`、策展 dev / 真实捕获 holdout、人工两维评分(`事实正确` / `可操作性深度`)、`ManualBridgeScore` 契约、覆盖门 N/M——这些在 seam 落地时再走一轮 R1/R6。
9. **decision 13 同步**(§契约改动,含 `scripts/export_bridge_schemas.py` + schema drift 测试)+ **03 索引行** 🔲→🔍。

### 不做(明确划给后续阶段)

- ❌ 不接 MATLAB Engine、不做自动采集(输入仍是 `manual_error`;Engine = b2-0/b2-1)。
- ❌ 不做收敛状态解释 / 波形 / CSV / MAT 结果解释 / "真实场景调通率 ≥ 50%"(= b3 总门)。
- ❌ 不动 v0.3-a 连接回执语义(`connectivity_stub` ACK 不被偷换成解释结果)、不改 `DiagnosticService.consume()` 现行为、不改 route 固定顺序。
- ❌ 不直接复用 `features/explanation`(prompt/validator/EvidencePack/evidence_id 机制均为静态结构讲解设计)。
- ❌ **不做报错解释质量评估**(真打 LLM 的 runner + 策展/真实捕获 case + 人工两维评分 + `ManualBridgeScore` + 覆盖门 N/M)→ 全部推迟到挂起 seam `bridge 报错解释·小规模质量测试`(PM 决策);b1 只做**确定性护栏**(机器可判)+ `case_kind` 确定性判定。decision 25 的 judge / 漏报盲评本就留 v0.2 多 case,不在此。
- ❌ 不 repair / retry / 产降级业务结果(**fail-closed**,R1-P1-3)。
- ❌ 不改 decision 23 §2.2 的 b3 总门:b1 报错**类别**覆盖是 **b1-local 门**、不修改 b3 总门(R1-P1-2 纠 v0.1 把它误当 decision 23 delta);"能力三类"总门重构留挂起 seam。

---

## 设计点裁决(R1 + R6 一审,已锁)

> v0.1 的 6 个待锁点已由两审裁定;以下为已锁结论(替代 v0.1"推荐 + 交审")。

### DP-1 解释结果契约 + 时序 = **B(新端点 + 新版本化契约)+ 两段同步调用**(R1-P0-1 / R6-DP-1)

锁:① 客户端生成**一次** UUID + **一份冻结**脱敏文本;② 先 POST `/api/v1/bridge/diagnostic` 显示既有 ACK;③ ACK 成功后再 POST `/api/v1/bridge/explanation`(**同 `request_id` + 同冻结文本**);④ 第二步失败 **ACK 仍保留**、解释区显示固定失败文案;⑤ 新 explanation handler **不调 `DiagnosticService.consume()`**、现 diagnostic handler **字节不动**;⑥ 客户端校验返回 `request_id` 与本次一致。protocol `0.3-b1`。**新端点必挂同一 `MatlabBridgeRoute` router**(§I-7)。**不选** A(会动 0.3-a freeze)/ C(异步 job;R6 实测 7.77s,同步可行,但须修 DP-1 的 timeout,见 §验收门——若实施期稳不住已锁 timeout 上限,则**实施前**切 C、不许完工后再决)。

### DP-2 case 来源 → **推迟到 seam `bridge 报错解释·小规模质量测试`**(PM 决策)

v0.3 的裁决(dev 可策展 / 手写;holdout 每覆盖类别 ≥1 真实捕获,记 release / 语言 / 来源)**保留为 seam 的设计依据**,但 case 语料属于质量评估,随之推迟,**b1 不建 case 语料**。R1-P1-1 的"holdout 真实捕获下限"在 seam 落地时生效。

### DP-3 判分 = **b1 只做确定性判定(`case_kind` + 护栏);人工语义层 + 阈值推迟 seam**(PM 决策 + R1-DP-3 不引 judge)

锁(b1):复用 decision 25 双轴 + `case_kind="error_explanation"`,**无 partial**,**确定性映射**——provider/IO/序列化异常 → `case_failed + not_evaluated`;模型坏 JSON/schema/validator/隐私命中 → `succeeded + fail`;**确定性护栏全过 → `succeeded + pass`**(b1 不含人工语义硬门)。确定性护栏:`supporting_signals` 子串/最小长度/拒占位重复 / `is_inference` 恒 true·confidence∈{low,medium} / `caveats` 恒 ≥1 / ≥1 next_step / 不编造 error_text 外标识(内置命令 allowlist 除外) / `meaning` 不新增环境事实 / 无违禁断言 / 不泄漏。以 **fake provider 单测**喂构造输出验之。**待 PM 拍(R1-P1-1)**:`case_kind`/`compute_verdict` 分派**留 b1**(你上轮要留)还是**移 seam**(R1 建议——b1 无 runner/case/调用者消费此 verdict,属仍存活的 evaluator 引用)。**v0.5 暂按"留 b1"**,但补两条 R1 要求的澄清:① b1 的 `pass` 仅="确定性护栏过",**非**解释正确/有用;② 完工注明实际改的 evaluator 文件(`eval/` 现 verdict 模块新增分支,**不接 paper evaluator**)。若移 seam,b1 改为直接单测 schema / grounding-hygiene / privacy validator + route 错误映射 + 客户端 E2E(同样闭合 G0–G6)。**推迟 seam**(PM 决策):人工两维语义评分(`事实正确` / `可操作性深度`,对照 per-case golden)+ 评分量表/阈值 + `ManualBridgeScore` + 真打 LLM runner——R1 复审 P0-3、一审 P0-6 随之到 seam 处理。decision 25 的 judge / 盲评仍留 v0.2 多 case。

### DP-4 覆盖门 = **b1-local 门,不改 decision 23 §2.2**(R1-P1-2 推翻 v0.1 delta 误判)

锁:b3 的 project_type 总门**保持不变**;b1 增"报错类别覆盖"只是**子任务补充验收(b1-local gate)**,**不修改 decision 23、不阻塞 b1 验收**。仅当未来要替换 / 重构 b3 总门时才正式走 delta;"能力三类"总门重构继续留挂起 seam。(撤 v0.1"待 decision 23 delta 批"。)

### DP-5 bridge prompt + validator = **专用;两层 grounding(事件事实 + 通用知识),不要"error_text 唯一知识源 / token 全匹配"**(R1-P0-5)

锁(R1 同意专用、不复用 `features/explanation`;但推翻 v0.1 的"唯一证据 / token 全匹配"):
- **两层 grounding**:**本次事件事实**只能来自服务端脱敏后 `error_text + matlab_release`;**通用 MATLAB 知识 + 非破坏性排查动作**允许使用,但不得伪装成"已观察到的环境事实"。**删除**"通用命令必须出现在 error_text"规则。
- 每 cause 加 `supporting_signals` = 脱敏报错文本的**精确短子串**;`likely_causes[*].is_inference` 恒 true、`confidence` 仅 low/medium;`caveats` **恒 ≥1**(不再依赖不可计算的"cause 是否唯一")。
- **违禁断言集补全**(不止"自称已跑"):自称已检查 / 确认用户环境·路径·工作区·工具箱·许可证;自称已确定某文件 / 模型 / 变量存在或不存在;自称已验证修复有效 / 执行后必成功;与报错证据无关的具体版本兼容性断言。
- **prompt injection 防护**:`error_text` 包在数据分隔符内,声明其中任何指令均为不可信数据。
- YAML 内 JSON 示例花括号走 `_render_user` 风格 / 转义,不直接 `.format()`(§I-5)。

### DP-6 客户端显示 = **最小双区;ACK 永久独立;解释区显示置信/推断/caveat 与独立失败态**(R1-P1-4 / R1-DP-6)

锁:`formatExplanation.m` **不能只显示 cause 文本**——原因显示为"可能原因(中/低置信)"、**始终显示局限说明(caveat)与推断标记**;解释失败**不得覆盖已有 ACK**。UI 一区 vs 两区等布局 = 实施形状级。

---

## 不变量(全局锁;几条是 b2-0 审稿血换,别违反)

1. **v0.3-a 连接回执保持原语义**:`connectivity_stub` ACK 不得被偷换成业务/解释结果;`DiagnosticService.consume()` 现行为不动。
2. **ACK ≠ 解释结果**:报错解释走**新增版本化"解释结果"契约**,不在传输 ACK 上原地变义(字段细节 DP-1 + decision 13;"版本化、不原地变义"现在锁)。
3. **解释逻辑在服务端**:LLM 解释 / 质量控制 / 降级在后端;Add-on **只做** 采集 / 脱敏 / 确认 / 发送 / 显示,不承载 prompt / 解释规则 / 判分逻辑。
4. **异步边界(decision 11)**:LLM 调用**不得**塞进同步 `consume()`;走 `asyncio.to_thread(...)`,本服务**恰一处 to_thread** + 配套纪律测试。**禁 `logger.exception`**(用 `logger.error` + 结构化字段,重抛 `from None`、不泄漏原文/SDK 异常)。
5. **`features/explanation` 不可直接复用**(§F):b1 用 bridge/runtime 专用 prompt + validator。
6. **manual_error 是长期 fallback**:b1 阶段输入仍是 `manual_error`(Engine 未接)。
7. **隐私 + LLM 处理同意(沿用 b2-0 口径 + R1-P0-4)**:① 诊断证据经客户端 `redactDiagnosticText` + route 拒 `SENSITIVE_EXTRA_FIELDS` + `error_text` ≤4096 脱敏;② **服务端调 provider 前再做一道 redaction**(Windows 盘符 / UNC / POSIX / `file://` / 源码 sentinel);③ **新增 LLM 处理同意**:`uiconfirm` 文案明写"脱敏文本将发往服务端、由 LLM 生成解释",explanation 请求带专用 `llm_processing_consent_confirmed=true`(0.3-a 的 `consent_confirmed` 是传输同意、语义不同、**不复用**);④ `supporting_signals` **只能是②脱敏后送 provider 文本的、有上限长度的精确子串**(故不回带路径 / 源码);⑤ **输出隐私扫描在最后,命中即 fail-closed 返回 502、不替换**(R1-P1-4);⑥ provider 输入与 HTTP 输出均加泄漏测试。日志 / 异常 / 对外结果均不含 `error_text` 正文 / 绝对路径 / 源码。
8. **route 固定前置 + 两条独立管线**(R1-P1-1):两端点共享 loopback(403)→ application/json(415)→ body≤32KB(413)→ replay → Pydantic 前置;之后**分流**——`diagnostic: … → BridgeDiagnosticRequest → DiagnosticService.consume()`;`explanation: … → BridgeExplanationRequest → BridgeExplanationService.explain()`(handler `async`,**不调 `consume()`**)。客户端时序另定:diagnostic ACK 成功后才发 explanation(不变量 10)。
9. **行尾 / git**:按 `20260602-08-pm-verify-git-and-preserve-line-endings.md`(**非 decision 18**;decision 18 = ProjectOverview API serialization)保 CRLF/LF 一致;实施从 `main` 切新分支 `task/TASK-511-bridge-error-explanation`,禁直接改 main;完工 03 索引 🔲→🔍,PM 合并后→✅;`git diff --stat origin/main` 与文件清单一致。
10. **两段调用 + ACK 永久独立**(R1-P0-1 / DP-1):一次 UUID + 一份冻结脱敏文本;diagnostic POST(ACK)与 explanation POST(同 `request_id`)分两次;explanation handler 不调 `consume()`;**解释失败时 ACK 仍在、不被覆盖**;客户端校验返回 `request_id` 一致。
11. **fail-closed + verdict 分类**(R1-P1-3 / R1-P0-3):服务端任何失败抛 typed bridge error(503/504/502,见不变量 13),**不重试 / 不降级**。eval `error_explanation` **无 partial**:仅 provider/网络/IO/产物写出异常 → `case_failed + not_evaluated`;**模型坏 JSON / schema / validator / 隐私命中 → `succeeded + fail`**(模型质量失败,非基建);全过 → `succeeded + pass`。
12. **prompt 注入防护 + 两层 grounding**(R1-P0-5):`error_text` 包数据分隔符、声明内含指令为不可信数据;事件事实仅来自脱敏 `error_text + matlab_release`,通用 MATLAB 知识 / 内置命令 allowlist 可用但不得伪装成已观察的环境事实。
13. **错误状态映射唯一 + schema 同源**(R1-P0-2 / R6-P0 / R6-P1-2):`timeout/deadline→504` / `auth·quota·rate·server·provider不可用→503` / `坏JSON·schema·validator·隐私→502`;handler + OpenAPI + freeze + 客户端测试同此一张表,**不得同一 timeout 既 502 又 504**;新 error 模型/schema **不复用旧 `BridgeErrorResponse` 的 Literal**(那只有 3 个 guard code),三 explanation code 独立;加**状态码×code 配对矩阵测试**(防 503 携 timeout code 漂移)。
14. **seam 前不上 production**(R1-P1-4):质量 seam 通过前,`matlab_bridge_enabled` **不得扩到 production、不得作为用户可用能力宣传**;确定性护栏只**降低已枚举危险失败概率**(同义改写仍可能绕过),非完整安全保证。
15. **ACK 中性显示不动服务端**(R1-P0-1):客户端 ACK 区用本地中性 formatter(读 `status/mode/request_id`),**不显示服务端旧 `message`**("…不提供报错解释"会与实际解释矛盾);`BRIDGE_RECEIPT_MESSAGE` / receipt JSON / diagnostic endpoint / `consume()` / 0.3-a freeze 全不动。

---

## 契约改动 + decision 13 schema-sync 清单(新 `0.3-b1` 解释契约;**已锁到可实施粒度**,R1-P0-3)

> 字段长度为已锁默认(PM 可微调,decision 13 一行改),**不留给 Codex 发明**。**所有模型(含嵌套)`extra="forbid"`;所有字符串 strip 后须非空、拒 NUL。**

```text
BridgeExplanationRequest          # 客户端 → 新端点;与 diagnostic 同 request_id + 同冻结文本
- protocol_version: Literal["0.3-b1"]
- request_id: UUID4
- diagnostic_kind: Literal["manual_error"]
- matlab_release: 沿用现 pattern ^R20[0-9]{2}[ab]$
- client_version: 沿用现 pattern ^[A-Za-z0-9.\-]{1,32}$
- error_text: str  1..4096
- llm_processing_consent_confirmed: StrictBool(必须 true)

BridgeExplanationResult           # 服务端 → 客户端
- protocol_version: Literal["0.3-b1"]
- request_id: UUID4
- status: Literal["completed"]
- mode: Literal["llm_error_explanation"]      # 与 connectivity_stub 显式区分
- meaning: str  1..1500                        # 仅释义,不新增环境事实
- likely_causes: list[LikelyCause]  1..4
- next_steps:    list[NextStep]     1..5
- caveats:       list[str(1..400)]  1..3       # 恒 ≥1

LikelyCause                       # 嵌套模型(extra=forbid)
- cause: str  1..400
- is_inference: Literal[true]                  # 恒 true
- confidence: Literal["low","medium"]          # 禁 high
- supporting_signals: list[str(8..200)]  1..MAX_SUPPORTING_SIGNALS(=6)
  # 验证基准:服务端二次脱敏后、实际送入 provider 的那份文本的精确子串;
  # 拒纯标点 / 纯占位符(如 [REDACTED_PATH])/ 重复项(R1-P0-1/P1-3)

NextStep                          # 嵌套模型(extra=forbid)
- action: str  1..400                          # 非破坏性排查动作;不得伪装成已执行
```

**错误响应映射表(已锁;脱敏 `{error, message}`,handler + OpenAPI + freeze + 客户端测试同此一表,R1-P0-2 / R6-P0)**:

| 触发 | HTTP / code |
|------|-------------|
| `LLMAuthError`/`LLMQuotaError`/`LLMRateLimitError`/`LLMServerError`、或共享 provider 不可用 | `503 bridge_explanation_unavailable` |
| `LLMTimeoutError`、或服务端 explanation deadline(`wait_for`)超时 | `504 bridge_explanation_timeout` |
| provider 有返回但坏 JSON / schema 不合格 / grounding·业务 validator 失败 / 隐私扫描命中 | `502 bridge_explanation_failed` |

实现可用三 leaf exception 或一个 bridge error 携冻结 reason/status enum;**G0 不再写 `LLMTimeoutError→502`**。**新 error 模型 / `bridge_explanation_error.schema.json` 不复用旧 `BridgeErrorResponse` 的 Literal**(那只含 `matlab_bridge_forbidden`/`bridge_payload_too_large`/`bridge_unsupported_media_type` 三 guard code),三 explanation code 独立定义(R6-P1-2);加**状态码×code 配对矩阵测试**(防 503 携 `bridge_explanation_timeout` 之类交叉漂移,R1-P2-3)。timeout 数值锁:`provider_timeout_s=12 < server_deadline_s=55 < ExplanationTimeoutSeconds=60`(统一用此名,不用泛称 `client_timeout_s`),且 `4×provider_timeout_s+3.5 ≤ server_deadline_s`(retry 账,§I-9),配序关系测试。`max_tokens` 锁 `DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS=2048`(PM 可调)+ 测该上限足以承载最大合法 `BridgeExplanationResult` JSON。

**decision 13 完工清单(贴各文件 diff,缺任一 = 未完工;路径按 §I-6 实测)**:

```text
□ core/domain/bridge_explanation.py               # 新 frozen dataclass(纯 domain,不 import Pydantic)
□ features/matlab_bridge/bridge_explanation_schemas.py  # request/result/error Pydantic + validators + to_domain/from_domain
□ schemas/bridge_explanation_request.schema.json
□ schemas/bridge_explanation_result.schema.json
□ schemas/bridge_explanation_error.schema.json
□ scripts/export_bridge_schemas.py                # 实际脚本路径(非 tools);新增三 schema 导出
□ tests/.../test_bridge_explanation_schema_freeze.py     # freeze 期望
□ tests/.../test_bridge_explanation_schemas.py           # 边界 + round-trip
□ + schema drift 测试或 make target（CI 不自动验 bridge schema，§I-6）
□ docs/06_OUTPUT_CONTRACTS.md                     # 新解释契约 + 错误响应描述
□ docs/05_EXPLANATION_STYLE_GUIDE.md              # bridge 报错解释输出段
□ api/routes/matlab_bridge.py 的 OpenAPI responses 声明（502/503/504）
□ clients/matlab_bridge/ formatExplanation.m + client contract 测试
```

**0.3-a 现契约(`bridge_diagnostic_*`)字节不动、freeze 不碰**(DP-1 选 B 的核心收益)。

---

## 验收门(= b1 机制 + 确定性护栏;**≠ 质量门、≠ b3 总门**)

> 全部**机器可判**。复用 decision 25 双轴 + `case_kind="error_explanation"`(**无 partial**,确定性映射,§设计点裁决 DP-3),以 **fake provider 单测**喂构造输出验护栏与 verdict 逻辑。**报错解释质量评估(真打 LLM + case + 人工两维评分 + 覆盖门 N/M)整体推迟到挂起 seam `bridge 报错解释·小规模质量测试`**(PM 决策);b1 不真打 LLM、不建 case 语料。

| 门 | 内容 | 判分层 |
|----|------|--------|
| G0 | provider 抛 typed error / 返回坏 JSON 时 route **不 crash**,**按映射表翻译**:auth/quota/rate/server→`503`、`LLMTimeoutError`/deadline→`504`、坏 JSON/validator/隐私→`502`,均脱敏友好中文(**不测"真无 key"**——`create_app()` 即要必填 key,§I-1;**G0 不再写 timeout→502**);**状态码×code 配对矩阵测试** + `provider.chat` **恰一次**调用次数测试(无业务级第二层 retry,R1-P1-2) | 确定性(单测 + fake/slow provider) |
| G1 | **一处 `to_thread`** + 纪律测试 `test_only_one_asyncio_to_thread_in_service`(AST/inspect)绿;无 `logger.exception`;重抛 `from None` 不泄漏 `error_text`/SDK 异常 | 确定性(单测 + grep) |
| G2 | 新 `0.3-b1` 三 schema(request/result/error)freeze + 边界 + round-trip 绿;decision 13 清单各文件 diff 齐(含 `scripts/export_bridge_schemas.py` + drift 测试);**0.3-a 契约 freeze 仍绿(字节未动)** | 确定性(CI) |
| G3 | **隐私不泄漏**:服务端二次 redaction + 输出 validator;provider 输入 + HTTP 输出泄漏测试(Windows drive / UNC / POSIX / `file://` / 源码 sentinel)全绿 | 确定性(单测) |
| G4 | **timeout 闭合(数值已锁)**:`provider_timeout_s=12 < server_deadline_s=55 < ExplanationTimeoutSeconds=60`,且 `4×provider_timeout_s+3.5 ≤ server_deadline_s`(retry 账,§I-9);配序关系测试 + fake slow provider 触 `504` 单测 + 客户端超时 e2e。**若实施期单次需 15s 则客户端升 ≥70s;稳不住 → 实施前切 DP-1 C** | 确定性 + 本机 e2e |
| G5 | **grounding hygiene(确定性;只降低已枚举危险概率、非完整保证;语义质量留 seam)**:每 cause `supporting_signals` 为脱敏文本精确子串、单项 ≥ 最小长度、拒纯标点 / 占位符 / 重复、数量 ≤ `MAX_SUPPORTING_SIGNALS`;`is_inference` 恒 true、`confidence`∈{low,medium};`caveats` 恒 ≥1;违禁断言集(自称已跑 / 已检查环境·工具箱·许可证 / 已确定文件存在 / 已验证修复 / 无关版本兼容)零命中;≥1 `next_step`;`meaning` 不新增环境事实;**编造标识检查只针对事件专属标识,内置命令(`which`/`ver`/`license`)走版本化 allowlist**;**加确定性对抗样例**覆盖确定语气同义表达("可以确认 / 根因就是 / 执行该步骤即可解决"等,R1-P1-4) | 确定性(validator + fake provider 单测) |
| G6 | `ruff check` / `ruff format --check` / `mypy core/ adapters/ features/ api/`(matlab 不涉)/ 全 `pytest -v`(报错 case 用 fixture / fake provider、**CI 不真打 LLM**)/ `check_repo_hygiene.sh` 全绿;新端点 route 单测 + 真 FastAPI+fake provider headless E2E,**旧 0.3-a E2E 保留**(R1-P1-5);**3 项 ACK 测试**(diagnostic 响应仍含旧 message / b1 UI 不现"不提供报错解释" / 解释失败后中性 ACK 仍在,R1-P0-1) | CI + 本机 |

`error_explanation` verdict 映射(b1,确定性):provider/网络/IO/产物写出异常→`case_failed + not_evaluated`;**模型坏 JSON / schema / validator / 隐私命中→`succeeded + fail`**(模型质量失败);确定性护栏全过→`succeeded + pass`。**b1 不含人工语义硬门**;真打 LLM 的发布门 + 人工评分 + `ManualBridgeScore` + 覆盖 N/M → seam。

**b1 在 4 维度里只判 3 个结构/安全维**(机器可判):`不过度推断`(G5)/ `可操作性结构`(G5 的 ≥1 next_step)/ `风险提示`(G5 的 caveat 恒 ≥1)。**`事实正确` + `可操作性深度`(语义)留 seam 人工评。** 收敛 / 波形 / CSV/MAT 解释、真实场景调通率 ≥ 50% = b3,不在 b1。

**本版无 PM 待批阻塞数值**:覆盖 N/M、评分量表 + 阈值随质量评估推迟到 seam(届时 PM 定 + R1/R6 审)。b1 派单不依赖这些。

---

## 实施约束(全程)

- **同步核心 + 调用侧 to_thread**:解释服务核心 `_parse_and_validate` 同步;LLM 调用经**一处** `await asyncio.to_thread(provider.chat, ...)`(照 PaperSpecService);`consume()` 字节不动。
- **共享 provider 注入**(§I-4):`get_matlab_bridge_explanation_service` 走 `Depends(get_text_provider)` / `request.app.state.text_provider`,**禁 dependency 内 `DeepSeekTextProvider(...)` 现起 / 禁 per-request 新建 provider**;service 可新建。
- **provider 错误友好,非"真无 key"**(§I-1):`create_app()` 即要必填 `deepseek_api_key`,故韧性测试针对 provider 抛错 / fake provider,不针对真缺 key;真缺 key = 全局配置改,**不在 b1 scope**(若要做须升 PM)。
- **三状态 typed error + handler 注册 + 脱敏日志**:`core/domain/exceptions.py` 加 `BridgeExplanationError`(502)/`BridgeExplanationUnavailableError`(503)/`BridgeExplanationTimeoutError`(504);`api/middleware/error_handler.py` 各注册(或一个 error 携冻结 reason/status enum),否则只走 `MxaError → 500`;失败 `logger.error` + 结构化字段(request_id / matlab_release / error_type)、`raise ... from None`;**禁 `logger.exception`**;日志 / 异常 / 对外结果均不含 `error_text` 正文 / 绝对路径 / 源码。
- **服务端 deadline + 二次脱敏 + fail-closed**:`asyncio.wait_for(to_thread(...), server_deadline_s=55)`;调 provider 前再 redaction;按映射表抛对应 typed error(`provider_timeout_s=12`、客户端 60s,§I-9),**不重试 / 不降级 / 不替换**(隐私命中也 fail-closed 502)。
- **prompt 版本化 + 花括号坑**(§I-5):`bridge_error_explanation.yaml` 带 `version` 经 `load_prompt_template` 载入;YAML 内 JSON 示例花括号走 `_render_user` 风格 / 转义,**不直接 `.format()`**。
- **新端点挂同一 router**(§I-7):`POST /api/v1/bridge/explanation` 用 `api/routes/matlab_bridge.py` 同一 `route_class=MatlabBridgeRoute`(同享 loopback/415/413/replay + 32KB + 敏感字段拒);`matlab_bridge_enabled` 仅 `APP_ENV=development|test`,测试显式 `MATLAB_BRIDGE_ENABLED=true`;**现 diagnostic handler 字节不动**。
- **客户端 ACK 中性 + 错误按 `ME.identifier`**(R1-P0-1 / §I-8):ACK 区本地中性 formatter 读 `status/mode/request_id`,**不显示服务端旧 `message`**(矛盾文案);错误显示按异常 identifier + 固定 fallback、不依赖服务端 body(R6 实测 5xx 读不到 body、`cause=0`);"能否读 JSON body"留实施期实测。客户端拆 `DiagnosticProtocolVersion`/`ExplanationProtocolVersion` 双常量 + 两 payload builder,首段 ACK 校验 `request_id`/`status`/`mode` 后才发第二段。**服务端 receipt / `consume()` / `BRIDGE_RECEIPT_MESSAGE` / 0.3-a freeze 全字节不动**。
- **seam 前不上 production**(R1-P1-4):质量 seam 通过前 `matlab_bridge_enabled` 不扩 production、不作能力宣传;确定性护栏只降低已枚举危险概率。
- **decision 13**:任何 Pydantic 约束改动列同步清单、贴 diff(§契约改动,含 `scripts/export_bridge_schemas.py` + drift 测试)。
- **质量评估推迟 seam**:真打 LLM 的 runner `eval/run_bridge_error_eval.py` + case 语料 + 人工评分 + `ManualBridgeScore` 不在 b1;b1 只在 `compute_verdict` 注册 `case_kind="error_explanation"` 确定性判定 + 确定性 validator,以 fake provider 单测验之(不真打 LLM、不进 CI 之外的网络)。
- **git / 行尾**:`main` 切 `task/TASK-511-bridge-error-explanation`;`20260602-08` 保行尾;`git diff --stat origin/main` 与清单一致;完工 03 🔲→🔍。
- **不重开已锁**:v0.3-a 已收口、v0.3-b 拆分定稿、b1∥b2-0 不依赖、b1 门≠b3 门;遇 main 实际与本卡不符按 **decision 15** 停手报 PM。

---

## 依赖

- ✅ TASK-510(v0.3-a 传输桥,#108 已合并 main)——b1 在其上加解释。
- **不依赖 b2-0(TASK-512)**——两者并行。
- decision 11 / 12 v0.4 / 13 / 15 / 25 已在 main;decision 23 §2.2 为 b3 总门(**b1 报错类别覆盖推迟到 seam、不改它**,R1-P1-2)。

---

## 挂起 seam(留 b2-1 / b3 或后定,本卡不锁)

- **`bridge 报错解释·小规模质量测试`(PM 决策推迟自 b1,优先级最高)**:真打 LLM 的 runner `eval/run_bridge_error_eval.py` + `--manual-scores`;策展 dev set + **holdout 每覆盖类别 ≥1 真实捕获 case**(记 release/语言/来源,DP-2/R1-P1-1);人工两维评分(`事实正确` / `可操作性深度`,对照 per-case golden);冻结 `ManualBridgeScore`(`case_id`/两维分/rubric version/结论);覆盖门 N(报错类别数)/ M(case 总数)/ dev:holdout 比;发布门(全 case 须有 verdict,缺/重/越界→门挂);CI 外真跑、holdout 不用于 prompt 调优。**落地时 PM 定数值 + R1/R6 审**(R1 复审 P0-3 人工分调用契约、一审 P0-6 阈值在此处理)。
- Engine 采集数据如何接进 b1 解释层 + 是否再扩契约(b2-1,走 decision 13)。
- 收敛状态 / 波形 / CSV/MAT 结果解释(b3)+ 真实场景调通率 ≥ 50% 总门(b3,decision 23 §2.2)。
- 采集数据体积 vs 32KB 上限(b2-1/b3,独立结果通道或有界摘要)。
- "能力三类"评测重构在 v0.3-b 总门层正式落定(decision 23/24 验收门,PM+GPT)。

---

## 关联决策

decision 23 §2.2(b3 总门;**b1 报错类别覆盖推迟到 seam、不改 b3 总门**,R1-P1-2 纠 v0.1 delta 误判)/ **decision 11**(asyncio.to_thread + 禁 logger.exception)/ **decision 13**(schema-sync,本卡触发)/ **decision 25**(双轴判分,b1 用**确定性轴** + `case_kind="error_explanation"` 无 partial;人工语义 / judge 留 seam 与 v0.2 多 case)/ decision 12 v0.4(双 AI 互审)/ decision 15(实际与方案不符停手报 PM)/ **`20260602-08`(保行尾 —— 行尾决策是它,不是 decision 18;decision 18 = ProjectOverview API serialization boundary)** / **v0.3-b 拆分定稿**(`v0_3b-split-final-skeleton.md`,§2 不变量 / §4 b1 / §5 评测口径;**经 Codex 实测未入 origin/main**,本卡据其复述 + 取证重建)。

---

## 修订历史

- **v0.1 草案(2026-06-21)**:据 `origin/main` #109 `6bc9c76` 的 A–H 取证(契约底座 / diagnostic_service / route 固定顺序 / 客户端 / paper LLM 范例 / features/explanation 禁令 / exceptions / decision 25 + eval)逐字起草;含 6 待锁设计点(DP-1 解释结果契约 + 时序 / DP-2 case 来源 / DP-3 判分确定性 vs judge / DP-4 覆盖口径 delta / DP-5 bridge prompt+validator / DP-6 客户端显示)交 R1/R6;锁不变量 1–9;`v0_3b-split-final-skeleton.md` 经 Codex 实测确认未入 main,b1 定义据交接包 §4 + decision 23 + 取证重建。
- **v0.2 二修(2026-06-21)**:吸收 **R1 一审 6 P0**(P0-1 DP-1 调用路径自相矛盾→锁 B + 两段同步、同 request_id、ACK 独立 / P0-2 timeout 不闭合 + 错误响应未定义→独立 `ExplanationTimeoutSeconds` + 503/504 / P0-3 契约只"形如"→锁 `BridgeExplanationRequest`/`Result` + 嵌套模型到可实施粒度 / P0-4 consent 与隐私契约缺口→专用 `llm_processing_consent_confirmed` + 服务端二次脱敏 + 输出泄漏测试 / P0-5 grounding 不 sound→两层 grounding + `supporting_signals` + 违禁断言集补全 + 注入分隔、删"token 全匹配" / P0-6 G5/G6 非可执行门→无 partial + 真跑 runner + 人工分进 verdict + 数值 PM 派单前锁)+ **R6 一审 2 P0**(G0 "真无 key 友好降级"按 main 不可达 `create_app()` 必填 key→改 fake provider/provider 错韧性 / 客户端 10s timeout 与同步 LLM 不闭合、实测往返 7.77s→锁 timeout 关系 + 客户端默认 60s)+ **两边 P1/P2**(DP-2 holdout 真实捕获下限 / DP-4 撤 delta 误判改 b1-local 门不改 decision 23 / fail-closed / 共享 provider DI 不 per-request / 502 handler 注册 / prompt 花括号坑 / 导出脚本真实路径 + drift 测试 / 新端点挂同一 `MatlabBridgeRoute` / 客户端显示置信+caveat+独立失败态 / 0.3-a freeze 字节不碰)。**DP-1~DP-6 转"已锁"**;**待 R1 + R6 定向复审**;两处真 PM 级挂起(G6 人工评分阈值 + G7 N/M/比例)。
- **v0.3 三修(2026-06-21)**:吸收 **R1 定向复审 3 P0 + R6 定向复审 1 P0**(两边**收敛于错误状态映射**):① 错误响应锁**唯一映射表**(`auth/quota/rate/server→503` / `timeout/deadline→504` / `坏JSON/validator/隐私→502`)+ 三 leaf typed error,**删 G0 的 `timeout→502`**,handler/OpenAPI/freeze/客户端测试同表(不变量 13);② timeout 数值锁死并算 **retry 总耗时**(R6 实测 `DEFAULT_RETRY_COUNT=3`/backoff 3.5s):`provider_timeout_s=12 < server_deadline_s=55 < 客户端 60`、`4×12+3.5 ≤ 55`,服务端 `asyncio.wait_for` 兜 deadline;③ 契约填**具体字段边界** + `MAX_SUPPORTING_SIGNALS=6` + strip 非空 + 嵌套 `extra=forbid`,`supporting_signals` 锁**为二次脱敏后送 provider 文本的有界子串**(解隐私冲突);④ 人工评分锁**调用契约**(`ManualBridgeScore` + `--manual-scores` 两段命令 + 缺/重/越界→门挂 + 全 case 必有 verdict),并明确**坏 JSON/validator/隐私 = `succeeded+fail`**(非 case_failed);⑤ P1:修不变量 8 的 `consume` 残句为两条独立管线、客户端拆双 protocol 常量 + 两 payload builder + 首段 ACK 校验、grounding 更名 **hygiene** 并加最小 signal 长度 + 内置命令 allowlist + `meaning` 不新增环境事实、隐私**拒不换** fail-closed、webwrite 按 R6 实测改 `ME.identifier` fallback(读不到 5xx body);⑥ P2:修状态门号笔误、`supporting_signals` 上限改名。**待 R1 + R6 定向复审 #2**。
- **v0.4 四修(2026-06-21)**:**PM 授权范围收窄**——把报错解释**质量评估**(真打 LLM runner `eval/run_bridge_error_eval.py` + `--manual-scores` + 策展/真实捕获 case + 人工两维评分 + `ManualBridgeScore` + 覆盖门 N/M)**整体推迟到命名挂起 seam `bridge 报错解释·小规模质量测试`**;b1 收为 **"主线机制 + 确定性护栏"**,验收门全部机器可判(G0 错误映射 / G1 to_thread / G2 契约 freeze / G3 隐私不泄漏 / G4 timeout 闭合 / G5 grounding hygiene / G6 CI+E2E)。理由(PM):人工评分须先有真实输出管线;主线先打通、小规模测试再评质量;bridge 仅 dev/test 环境、无真实用户。**此收窄化掉 R1 两条未闭合 P0**(复审 P0-3 人工分进 verdict 调用契约、一审 P0-6 阈值)→ 到 seam 再处理;v0.3 已锁契约/映射/timeout **全保留**。**待 R1 + R6 范围确认复审**。
- **v0.5 五修(2026-06-21)**:**R6 v0.4 复审 = PASS 无 P0**(可派 Codex)。吸收 **R1 v0.4 复审唯一 P0**:P0-1 旧 ACK 文案("…不提供报错解释")与实际解释同屏矛盾 → 按 R1 修法**不动服务端契约**,客户端 ACK 区改**本地中性 formatter**(读 status/mode/request_id、不显服务端旧 `message`)+ 3 项 ACK 测试(不变量 15)。同收两边 P1/P2:① retry 消歧——`BridgeExplanationService` 无业务级第二层 retry,provider 内置 `retry_count=3` 已计入 55s deadline,`wait_for` 是响应 deadline 非线程硬中断(超时返 504、线程到 SDK timeout 结束),配 `provider.chat` 恰一次调用测试;② `max_tokens` 锁 `DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS=2048` + 承载测试;③ 新 error 模型**不复用旧 `BridgeErrorResponse` Literal**、加状态码×code 配对矩阵测试(R6-P1-2/R1-P2-3);④ G5 措辞"挡住"→"**降低已枚举危险失败概率**" + 加确定语气同义对抗样例,**seam 前 `matlab_bridge_enabled` 不上 production / 不作能力宣传**(不变量 14);⑤ 删重复 item 9、timeout 名统一 `ExplanationTimeoutSeconds`。**一处待 PM 拍**:`case_kind`/`compute_verdict` 留 b1(暂按此 + R1 语义澄清:pass=仅护栏过、注明改 `eval/` 现 verdict 模块非 paper)还是移 seam(R1 建议)。**R6 已 PASS;待 R1 确认 ACK 修法即可派 Codex。**
