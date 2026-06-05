# TASK-206: 错误处理 + 中文化(Week 2 收尾)

## 状态

🔲 v0.2(R1 通过待入 Codex / **R1 conditional pass / 7 反馈全采纳 / 直接进 Codex,不升 R2**)审批级别 **一审 1 轮**(反例 18 自检详见 § 审批级别说明)。

---

## 审批记录

| 轮次 | 时间 | 结论 | 关键修订点 |
|:---:|:---|:---|:---|
| R1 | 2026-06-05 | **条件通过,不升 R2 / 直接进 Codex** | 4 P1 必改 + 3 P2 建议 全部采纳,转 v0.2;若实施期出现"调试期回传 validation errors"诉求自动升 R2 |

### R1 4 P1 必改(全采纳)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P1-1 | 404/422 兜底实际产 4 个 machine_code(not_found / method_not_allowed / http_error / validation_error),原文档只主叙事 2 个,前端会误以为只 freeze `21 + 2` | § 主要责任 #2 闭合 4 个 machine_code;§ 6.2 注释升级明示 3 分支隐私边界;§ 11.1 TestDefaultHandlers 升 4 case 含 405 + 418 generic |
| P1-2 | 422 隐私测试必须用"带敏感输入片段"的 validation error,而不是只测缺字段 | § 11.1 TestDefaultHandlers case 4:POST `{"count": "SECRET_STUDENT_INPUT"}` 到 `count: int` Pydantic endpoint,断言 body + log 均不含 SECRET_STUDENT_INPUT / errors / detail |
| P1-3 | `/_test/raise/{exc_name}` 测试 endpoint 隔离要求从"风险"升为"测试 fixture 硬契约" | § 11.1 测试 endpoint 隔离硬契约段(独立 test_app / 禁止 patch api.main.app / function 级 fixture);§ 11.2 #14 grep `grep -rn "_test/raise" api/` 应空 守门 |
| P1-4 | TASK-205 🔍→✅ 搭车 chore 与决策 07 默认规则不同,需标"PM 授权例外" | § 输出搭车 chore 表 + § 决策日志 D5 新增 + 紧凑表;明示"不作为 Codex 后续可自行写 ✅ 的先例" |

### R1 3 P2 建议(全采纳)

| # | 建议 | v0.2 修订位置 |
|:-:|---|---|
| P2-1 | "下游扩散面 0"易被误读,改"0 阻塞 / 3 下游消费者,仅消费已 freeze 的 machine_code/message" | § 审批级别说明表 |
| P2-2 | HANDLER_CASES 增加 expected_message,20 静态 handler 字面匹配 + ProjectTooLargeError 动态文案 assert template | § 11.1 parameterize 模板升级 + ProjectTooLargeError 单独动态测函数 |
| P2-3 | caplog 收窄为 `mocker.patch("api.middleware.error_handler.logger.error")` 唯一推荐,避免 loguru / pytest caplog 不天然等价踩坑 | § 11.1 TestLogPrivacy 行表述收窄 |

### R1 D1-D4 复核结论

D1 / D2 / D3 / D4 全部 **可接受**,不修订。D5(P1-4)作为新增决策插入 § 决策日志。

### 升级触发条件提醒(R1 重申)

宪法 § 5 把"上传安全、计费、数据隐私相关改动"列为二审触发类。本 Task 的 422 脱敏属于**隐私收敛**而非新隐私数据流,故不升 R2。**若后续实施期采纳**"调试期回传 validation errors / 日志落 errors() / DEBUG_VALIDATION env var Phase 2 提前实施"等任一,**必须自动升 R2**。

---

## 审批级别说明(反例 18 自检)

| 维度 | 评分 |
|---|---|
| 决策密度 | **低**:D1-D4(EvidenceMissingError status_code / tuple 顺序 / 404+422 实现位置 / 不新增异常类)|
| 下游扩散面 | **0 阻塞 / 3 下游消费者**:TASK-402 / 403 / 307 仅消费已 freeze 的 machine_code / message,不复制工程模式 |
| 用户可见性 | **间接**:21 handler + 2 兜底文案最终被 TASK-402 / 403 UI 渲染 |
| 异步 / LLM 首次定型 | **无**:不引入新 async 模式,不调 LLM |
| 隐私 / 安全 | **中**:422 RequestValidationError 必须脱敏 default error details(决策 11 隐私 spirit);EvidenceMissingError handler 边界 |

**评估**:沿用 task-107(决策 10)+ task-103 / task-105 一审通过模式;与 task-205(核心二审)/ task-203(GPT 二审)不同源。

**升级触发条件**(若 R1 给出任一,自动升 R2):
- 改 `core/domain/exceptions.py` 异常树结构(新增 / 删除 / 改父类)
- 引入新依赖
- 推翻 02 § 9 现有中文文案映射表(改 status_code / 改 machine_code / 改 message 范式)
- 推翻 ChatService E 类降级架构(决策 11 隐私 spirit / TASK-205 D13)

---

## 上下文

### mxa-tutor 快速建立 context(给 GPT R1 stand-alone 看)

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。
**"不是从零学 MATLAB,而是把你手上的工程讲明白"**。学生上传 .zip 工程(.m / .slx / .mat),后端 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。MCS 目标:4 周交付可收费产品。

四层分层:`api/` 路由 / `features/` 业务 / `core/` 接口 + domain + prompt yaml / `adapters/` 实现。
**core/ 不允许 import 外部库**;**features/ 只依赖 core 接口,不直接 import adapters**。

**当前 Week 2 已合并** 5/7:TASK-201 / 202 / 203 / 204 / 205。本 Task = Week 2 第 6 个 = **错误处理 + 中文化收尾**。

### 本 Task 在数据流的位置

不在数据流主线上,**横切关注点**。所有 API 端点 raise 业务异常 → FastAPI 按 MRO 查 handler → handler 返回 `{"error": "<machine_code>", "message": "<中文>"}` + HTTP status code。

`api/middleware/error_handler.py` 命名沿用历史目录结构,实际是 **FastAPI exception handler 注册点**(不是 ASGI middleware,文件级 docstring 已说明)。

### 主要责任

1. **追加 2 leaf handler**(完成 02 § 9 映射表):
   - `QuotaExhaustedError → 402, "quota_exhausted", "已达到合理使用上限,可联系加量"`
   - `EvidenceMissingError → 500, "evidence_missing", "出了点问题,我们已经记录,稍后再试"`(last resort,正常路径走 ChatService E 类降级)
2. **404 / 422 兜底 customize**(实际 freeze **4** 个 machine_code,R1 P1-1 闭合契约):
   - `StarletteHTTPException` handler 覆盖 FastAPI 默认 4xx 路径级错误,产 3 个 machine_code:
     - 404 → `{"error": "not_found", "message": "请求的资源不存在"}`
     - 405 → `{"error": "method_not_allowed", "message": "请求方式不正确"}`
     - 其他 HTTPException(罕见,FastAPI 业务代码极少裸抛)→ `{"error": "http_error", "message": "请求处理失败,请稍后重试"}`
   - `RequestValidationError` handler 覆盖 FastAPI 默认 422,产 1 个 machine_code:
     - 422 → `{"error": "validation_error", "message": "请求参数有问题,请检查后重试"}` **不暴露** `errors()` / `detail` 数组(决策 11 隐私 spirit)
3. **docstring 同步**(反例 24 同款修):
   - 文件级 docstring `"minimal ERROR_MAP:8 个 handler"` → 反映真实 21 handler + 2 兜底
   - `register_error_handlers` 函数 docstring `"注册 8 个 exception handler"` → 同步
4. **测试覆盖**:
   - `tests/api/test_error_handlers.py` parameterize 21 handler + 404 / 422 兜底
   - 隐私不泄露断言:异常 message / validation errors 不进响应体

### 范围边界(硬约束)

**本 Task 不修改**(零增量原则):

- `core/domain/exceptions.py` — **0 新增异常类**(反例 24 教训:23 类已稳;EvidenceMissingError / QuotaExhaustedError 早在宪法 v2.1 + TASK-101 入仓时落地)
- 21 个现有 handler 的 `status_code` / `machine_code` / `message`(沿用,02 § 9 + 既有实现是 source of truth)
- `features/chat/` / `features/overview/` / `features/ingest/` / `adapters/*/` — 异常 raise 源头不动
- `ChatService` 内部 E 类降级逻辑(TASK-205 D13 已实现)
- `app/config.py::AppSettings` — 配置零增量
- `error_handlers` tuple 顺序 — **不重组**(FastAPI MRO 不依赖注册顺序;避免范围扩张)
- `api/main.py` lifespan + DI 装配 — 不动
- TASK-201 / 202 / 203 / 204 / 205 任何文件 — 除 docstring 同步外不动

**本 Task 明确不做**:

- ❌ 不新增 `ProjectGenerationError` / `ChatNotFoundError` / 任何中间基类(反例 24 教训)
- ❌ 不抽 ERROR_MAP 配置文件(模块级 tuple 已经够,02 § 9 是文档,代码内 source of truth 是 tuple 内容本身)
- ❌ 不改 ChatService / OverviewService / UploadService 异常 raise 行为
- ❌ 不引入 i18n 框架(中文文案静态字面值即可,Phase 2 多语言再考虑)
- ❌ 不重写 docstring 全文(只同步数字 + handler 清单概要,保留既有设计要点)
- ❌ 不修改 `core/prompts/` / `tests/fixtures/` / `eval/` / `scripts/` — 范围外

### 下游消费者

- **TASK-402**(上传页 + 工程导览页):消费 21 handler + 2 兜底文案,前端按 `error` machine_code dispatch UI 提示
- **TASK-403**(问答对话页):同上,问答路径主要消费 `chat_session_not_found` / `chat_generation` / `llm_*` 5 类 / `evidence_missing`(last resort)/ `quota_exhausted`(付费触发)
- **TASK-307**(完整 CitationEnforcer):本 Task `EvidenceMissingError → 500` 是 last resort,正常路径(TASK-307 后)走 ChatService E 类降级,不到 handler

### 关键宪法 / 决策引用

- **01 § 5 line 198**:核心二审 Task 含 205 / 304,**不含 206** — 本 Task 一审通过
- **01 § 9 line 339**:日志只记录元数据,不记录原文(决策 11 已具象化)
- **01 § 11 line 367**:错误信息必须翻译成中文,不暴露 API 原始错误码 — 本 Task 直接收口
- **02 § 9 line 712-727**:错误处理表(14 个机器码 → 中文映射)真值源
- **04 § 9**:日志规范 — 不记录用户内容
- **04 § 10**:三层异常体系 — adapter / feature / api 各层职责
- **决策 11 决策 2**:`logger.error(..., type(exc).__name__)` metadata-only,禁 `logger.exception` — 本 Task `_log_error` 已遵守
- **TASK-203 D3**:LLM ERROR_MAP 临时前移 8 handler 模式(本 Task 接管,但已经全部入仓在 main,无需再"接管",**仅追加 2 + 兜底 2**)
- **TASK-205 D1 / D8**:Chat 路径前移 3 handler 同款(同上,已经入仓,无需"接管")
- **反例 24**:`api/middleware/error_handler.py` docstring 仍说"8 handler"实际 19 — 本 Task 修订

---

## 输入(前置依赖)

### 必须已完成 Task

✅ TASK-001 / 002 / 101 / 104 / 106(commit `b1eb647`)/ 107(commit `e7d2e22`)/ 108 / 201(commit `fa7a4b0`)/ 202(commit `431a2bf`)/ 203(commit `871c8e2`)/ 204(commit `5fba99b`)/ 205(commit `dd7a1da`,main HEAD)。

### 上游关键契约(stand-alone 内联给 GPT R1 + Codex 通过 view 实地核查)

**`core/domain/exceptions.py` 23 类异常树**(实地核查 main HEAD,本 Task 不动):

```
MxaError(Exception)                                          # 1. base
├── LLMError                                                 # 2. 中间基
│   ├── LLMAuthError                                         # 3. leaf, handler #9 → 503 llm_auth
│   ├── LLMQuotaError                                        # 4. leaf, handler #10 → 503 llm_quota
│   ├── LLMRateLimitError                                    # 5. leaf, handler #11 → 429 llm_rate_limit
│   ├── LLMServerError                                       # 6. leaf, handler #13 → 502 llm_server
│   └── LLMTimeoutError                                      # 7. leaf, handler #12 → 504 llm_timeout
├── ParseError                                               # 8. 中间基
│   ├── SlxParseError                                        # 9. leaf, handler #14 → 400 slx_parse
│   └── MParseError                                          # 10. leaf, handler #15 → 400 m_parse
├── ProjectError                                             # 11. 中间基, handler #7 → 400 project_error (base fallback)
│   ├── ProjectNotFoundError                                 # 12. leaf, handler #4 → 404 project_not_found
│   ├── ProjectTooLargeError                                 # 13. leaf, handler #5 → 413 project_too_large
│   └── ChatSessionNotFoundError                             # 14. 跨树设计! leaf, handler #17 → 404 chat_session_not_found
├── UploadError                                              # 15. 中间基, handler #6 → 400 upload_error (base fallback)
│   ├── ZipBombError                                         # 16. leaf, handler #1 → 400 zip_bomb
│   ├── ZipSlipError                                         # 17. leaf, handler #2 → 400 zip_slip
│   └── FileTypeNotAllowedError                              # 18. leaf, handler #3 → 400 file_type_not_allowed
├── QuotaExhaustedError                                      # 19. leaf, ★本 Task 新增 handler → 402 quota_exhausted
├── EvidenceMissingError                                     # 20. leaf, ★本 Task 新增 handler → 500 evidence_missing (last resort)
├── OverviewGenerationError                                  # 21. leaf, handler #16 → 502 overview_generation
├── StoreError                                               # 22. leaf, handler #18 → 500 store_error
└── ChatGenerationError                                      # 23. leaf, handler #19 → 502 chat_generation
```

**`api/middleware/error_handler.py` 现状(19 handler tuple)**:

实地核查 main HEAD `dd7a1da` 行 152-198 `error_handlers: tuple[ErrorHandlerSpec, ...]`,按注册顺序:

| # | Exception type | status | machine_code | message 中文文案(既有,本 Task 不动)|
|---:|---|---:|---|---|
| 1 | ZipBombError | 400 | zip_bomb | 压缩文件异常,请检查后重新上传 |
| 2 | ZipSlipError | 400 | zip_slip | 压缩包内含非法路径,请重新打包后上传 |
| 3 | FileTypeNotAllowedError | 400 | file_type_not_allowed | 包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试 |
| 4 | ProjectNotFoundError | 404 | project_not_found | 没有找到这个工程,可能已过期或已被删除,请重新上传 |
| 5 | ProjectTooLargeError | 413 | project_too_large | **动态文案**:从 `AppSettings.max_upload_size_mb` + `max_files_per_project` 模板生成 |
| 6 | UploadError (base fallback) | 400 | upload_error | 上传文件有问题,请检查压缩包后重新上传 |
| 7 | ProjectError (base fallback) | 400 | project_error | 工程处理失败,请重新上传后再试 |
| 8 | MxaError (final fallback) | 500 | internal_error | 出了点问题,我们已经记录,稍后再试 |
| 9 | LLMAuthError | 503 | llm_auth | 服务暂时不可用,请稍后重试 |
| 10 | LLMQuotaError | 503 | llm_quota | 服务繁忙,请稍后 |
| 11 | LLMRateLimitError | 429 | llm_rate_limit | 请求太频繁,稍等一下 |
| 12 | LLMTimeoutError | 504 | llm_timeout | 网络较慢,正在重试... |
| 13 | LLMServerError | 502 | llm_server | AI 服务暂不稳定,请刷新重试 |
| 14 | SlxParseError | 400 | slx_parse | Simulink 模型解析失败,可能版本过老或损坏 |
| 15 | MParseError | 400 | m_parse | .m 文件解析失败,请检查文件编码 |
| 16 | OverviewGenerationError | 502 | overview_generation | 导览生成失败,请刷新重试 |
| 17 | ChatSessionNotFoundError | 404 | chat_session_not_found | 对话不存在 |
| 18 | StoreError | 500 | store_error | 系统暂时不可用,请稍后重试 |
| 19 | ChatGenerationError | 502 | chat_generation | 回答生成失败,请刷新重试 |

**本 Task 追加 2 leaf**(注册到 tuple 末尾):

| # | Exception type | status | machine_code | message |
|---:|---|---:|---|---|
| 20 | QuotaExhaustedError | 402 | quota_exhausted | 已达到合理使用上限,可联系加量 |
| 21 | EvidenceMissingError | 500 | evidence_missing | 出了点问题,我们已经记录,稍后再试 |

**本 Task 新增 2 兜底**(不在 tuple 内,通过 `app.add_exception_handler(StarletteHTTPException, ...)` + `app.exception_handler(RequestValidationError, ...)` 注册):

| 触发 | status | machine_code | message |
|---|---:|---|---|
| `starlette.exceptions.HTTPException` 404 路径 | 404 | not_found | 请求的资源不存在 |
| `fastapi.exceptions.RequestValidationError` | 422 | validation_error | 请求参数有问题,请检查后重试 |

**实地核查的隐私约束**:
- 现有 `_log_error` 已遵守决策 11:只记录 `type(exc).__name__` / `status_code` / `request.url.path` / `request.method`,不记 message
- 新增 404 / 422 兜底必须沿用此模式,**禁止** 落 `exc.detail` 或 `exc.errors()` 到日志
- 新增 422 handler 响应体**禁止**回传 `errors()` 数组(可能含用户输入片段:01 § 9 数据隐私)

### 必读文档

- `docs/01_PROJECT_CONSTITUTION.md` § 9 数据隐私 / § 11 用户体验底线
- `docs/02_ARCHITECTURE_OVERVIEW.md` § 9 错误处理表(line 712-727)/ § 12 监控与日志
- `docs/04_ENGINEERING_STANDARDS.md` § 9 日志规范 / § 10 异常处理
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`
- `docs/decisions/20260604-11-async-blocking-and-logger-exception-bans.md` 决策 2
- `api/middleware/error_handler.py`(实地 view 既有 19 handler)
- `core/domain/exceptions.py`(实地 view 23 异常类树)

---

## Stage 0 实地核查清单(Codex 实施必跑,任一不符停手抛冲突)

> 决策 09 纪律 1 + 反例 24 教训(本 Task 触发的 docstring 与代码漂移)。
> **架构师本地实测每条 grep 命令的输出再写**(反例 24 教训:POSIX vs Perl 语法 / GNU vs BSD grep 兼容性 / 代码真实形态 vs 概念名假设)。

```bash
# 1. 23 个异常类全在位(本 Task 0 新增,实地校验"不动 exceptions.py")
grep -cE "^class [A-Z]\w*(Error|Exception)" core/domain/exceptions.py
# 期望:23

# 2. EvidenceMissingError + QuotaExhaustedError 在位但 handler 未注册(本 Task 入口)
grep -nE "^class (EvidenceMissingError|QuotaExhaustedError)" core/domain/exceptions.py
# 期望:2 行命中

grep -n "QuotaExhaustedError\|EvidenceMissingError" api/middleware/error_handler.py
# 期望:空(本 Task 完工后期望 4 行:import 2 + tuple entry 2)

# 3. error_handlers tuple 当前 19 entry(本 Task 完工后 21)
python3 -c "import re, pathlib; data = pathlib.Path('api/middleware/error_handler.py').read_text(); print(len(re.findall(r'\(\s*[A-Z]\w+Error,\s*\n\s*_make_', data)))"
# 期望:19(本 Task 完工后 21)

# 4. docstring 漂移检测(反例 24 同款,本 Task 必修)
grep -nE "minimal ERROR_MAP[^\d]*\b8\b|注册\s*\b8\s*个" api/middleware/error_handler.py
# 期望:命中 2 处(文件级 docstring + register 函数 docstring 均写"8 个"过期)
# 本 Task 完工后:期望 0 命中(docstring 同步为 21 handler + 2 兜底)

# 5. 404 / 422 兜底未注册(本 Task 入口)
grep -rnE "RequestValidationError|StarletteHTTPException|http_exception_handler|validation_exception_handler" api/ --include="*.py"
# 期望:空(本 Task 完工后期望 2-4 处 import + register)

# 6. 决策 11 兜底全空(继续保持)
grep -rn "logger\.exception" core/ adapters/ features/ api/ app/ \
  --include="*.py" --exclude-dir=.venv --exclude-dir=.git
# 期望:空

grep -rnE "str\(exc\)|repr\(exc\)|\{exc\}" core/ adapters/ features/ api/ app/ \
  --include="*.py" --exclude-dir=.venv --exclude-dir=.git
# 期望:空

# 7. ChatService E 类降级未被本 Task 触碰(范围边界硬约束)
git diff --name-only main..HEAD -- features/chat/
# 期望:空(本 Task 不动 features/chat/)

# 8. exceptions.py 未被本 Task 触碰(范围边界硬约束)
git diff --name-only main..HEAD -- core/domain/exceptions.py
# 期望:空

# 9. 03 索引行号未漂移(搭车 chore 字节级前 view)
grep -n "TASK-205\|TASK-206\|Week 2" docs/03_TASK_INDEX.md | head -8
# 期望(若漂移用 grep 重新定位):
#   line ~119: | TASK-205 | ... | 🔍 | Codex | 203, 204 |
#   line ~120: | TASK-206 | 错误处理 + 中文化 | 🔲 | Codex | 201-205 |
#   line ~338: Week 2:  [✅✅✅✅🔍⬜⬜]         4/7  (含 TASK-207)
#   line ~342: 总计: 15/32

# 10. tests/api/ 目录现状(本 Task 新增 test_error_handlers.py)
ls tests/api/ 2>/dev/null
grep -lE "test_error" tests/api/ 2>/dev/null || echo "FILE_NOT_EXISTS_OK_BUILD_NEW"
# 期望:test_error_handlers.py 不存在(本 Task 新建)
```

**任一不符停手抛冲突给 PM**(决策 08 第 2 条 + 决策 09 纪律 1)。

---

## 输出(交付物)

### 新增文件清单(1 个)

| 路径 | 行数 | 用途 |
|---|---:|---|
| `tests/api/test_error_handlers.py` | ~280 | parameterize 21 handler + 404 / 422 兜底 + 隐私不泄露 + 动态文案 + log 不记 message + log 不记 validation errors |

总新增 ~280 行,**单文件 ≤ 300 行**(04 § 4)。

### 修改文件清单(2 + 1 搭车 chore)

| 路径 | 修改 |
|---|---|
| `api/middleware/error_handler.py` | **追加 2 leaf handler**(QuotaExhaustedError / EvidenceMissingError)+ **新增 2 兜底 handler**(404 not_found / 422 validation_error)+ **修订 docstring**(文件级 + register 函数级,反映 21 handler + 2 兜底)+ **追加 import**(QuotaExhaustedError / EvidenceMissingError / StarletteHTTPException / RequestValidationError)。预估 200 → ~270 行(仍 ≤ 300)|
| `tests/api/conftest.py` | **可能不动**(若现有 `client` fixture + `app.state` 重置已够覆盖本 Task 测试,见 § 11.1 测试边界)。若需追加 fixture 用于 404 / 422 路径触发,加 ~10 行 |
| `docs/03_TASK_INDEX.md` | **搭车 chore**(字节级 Python,反例 23 + 决策 08 第 2 条 + 决策 07):TASK-205 🔍→✅(**PM 本次显式授权的历史状态补账,不作为 Codex 后续可自行写 ✅ 的先例**,R1 P1-4)+ TASK-206 🔲→🔍 + Week 2 进度条 4/7→5/7 + 总计 15/32→16/32 |

### 新增依赖

**0 个**。`fastapi.exceptions.RequestValidationError` 与 `starlette.exceptions.HTTPException` 已经在 FastAPI / Starlette 依赖树内(TASK-201 已引入),无新增 pip dependency。

### 拆分预案(类比 TASK-205 D14 模式)

`api/middleware/error_handler.py` 200 → ~270 行,**距离 300 上限有 ~30 行余量**。

判断标准:若 Codex 实施时实际写到 ~290 行附近(例如 docstring 修订更冗长 / 404+422 handler 含更多边界处理)→ **拆 `api/middleware/_default_exception_handlers.py`** 承接 404 / 422 兜底,主文件保留 21 业务 handler。**不预先拆**(避免过度模块化);Codex 实施时决定。

---

## 接口契约

### 6.1 追加 2 leaf handler(写入 `error_handlers` tuple 末尾)

```python
# api/middleware/error_handler.py 末尾(line ~196 之后)tuple 内追加 2 entry:

(
    QuotaExhaustedError,
    _make_handler(402, "quota_exhausted", "已达到合理使用上限,可联系加量"),
),
(
    EvidenceMissingError,
    _make_handler(500, "evidence_missing", "出了点问题,我们已经记录,稍后再试"),
),
```

**注册位置**:tuple 末尾,**不重组** 19 个既有 entry 顺序(决策 D2)。FastAPI 按 MRO 查找,注册顺序不影响行为。

**import 追加**(`from core.domain.exceptions import (...)` 块):

```python
from core.domain.exceptions import (
    ChatGenerationError,
    ChatSessionNotFoundError,
    EvidenceMissingError,      # ★ 本 Task 追加
    FileTypeNotAllowedError,
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    MParseError,
    MxaError,
    OverviewGenerationError,
    ProjectError,
    ProjectNotFoundError,
    ProjectTooLargeError,
    QuotaExhaustedError,        # ★ 本 Task 追加
    SlxParseError,
    StoreError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)
```

### 6.2 404 / 422 兜底 handler

**实现位置**:写在 `register_error_handlers(app, settings)` 函数体 `error_handlers` tuple 注册 for 循环**之后**,作为独立 `app.add_exception_handler(...)` 调用:

```python
# api/middleware/error_handler.py

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


async def _starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException,
) -> JSONResponse:
    """覆盖 Starlette 默认 HTTPException handler:中文化 + 项目 shape。

    注意:本 handler 主要兜底 404 / 405 等 path-level 错误。业务异常通过 MxaError
    子树触发,不到这里。422 由 RequestValidationError 独立 handler 处理。
    """
    _log_error(request, exc, exc.status_code)
    # 不暴露 exc.detail(可能含原始路径片段)
    # 本 handler 产 3 个 machine_code,与主叙事 21+2 之外的兜底契约一并 freeze(R1 P1-1)。
    # 任何 status_code 分支响应体都**不**含 exc.detail(可能含原始路径片段 / 测试期可能含敏感字面)。
    if exc.status_code == 404:
        machine_code = "not_found"
        message = "请求的资源不存在"
    elif exc.status_code == 405:
        machine_code = "method_not_allowed"
        message = "请求方式不正确"
    else:
        # 其他 HTTPException 落入此分支(罕见;FastAPI 业务代码极少裸抛 4xx/5xx HTTPException)。
        # 不暴露 exc.detail,统一 generic 中文文案 + machine_code。
        machine_code = "http_error"
        message = "请求处理失败,请稍后重试"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": machine_code, "message": message},
    )


async def _request_validation_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """覆盖 FastAPI 默认 RequestValidationError handler:中文化 + 隐私脱敏 + 项目 shape。

    关键:**不**回传 exc.errors() 数组(可能含用户输入片段,违反 01 § 9 数据隐私)。
    也**不**记录 exc.errors() 到日志(决策 11 决策 2 隐私 spirit)。
    """
    _log_error(request, exc, 422)
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": "请求参数有问题,请检查后重试"},
    )


# 在 register_error_handlers 函数体 tuple for 循环之后调用:
app.add_exception_handler(StarletteHTTPException, _starlette_http_exception_handler)
app.add_exception_handler(RequestValidationError, _request_validation_handler)
```

**为什么用 `starlette.exceptions.HTTPException` 而不是 `fastapi.HTTPException`**:
- `fastapi.HTTPException` 是 `starlette.exceptions.HTTPException` 的子类(实地 view FastAPI 源 `fastapi/exceptions.py`)
- FastAPI 内部 404 / 405 抛 `starlette.exceptions.HTTPException`,**不**经 fastapi.HTTPException 路径
- 注册 starlette 父类 handler 兼容 FastAPI 子类 + Starlette 直接抛的所有情况
- 这是 FastAPI 官方文档推荐的 customize 默认 handler 写法(`fastapi.tiangolo.com/tutorial/handling-errors/#override-the-httpexception-error-handler`)

### 6.3 docstring 同步(反例 24 同款修)

**文件级 docstring**(line 1-29,需修订):

```python
"""API 层异常 handler 挂载点(不是 ASGI middleware,命名沿用历史目录结构)。

本模块实现完整 ERROR_MAP:21 个业务 handler(覆盖 ``MxaError`` 异常树全部
leaf + 3 个 base/final fallback)+ 2 个 FastAPI 默认 handler 兜底
(``StarletteHTTPException`` for 404/405 / ``RequestValidationError`` for 422)。

响应体 shape ``{"error": "<machine_code>", "message": "<中文文案>"}`` 由
TASK-201 锁定,TASK-203 / 205 / 206 沿用,不改 shape。

设计要点:
1. handler precedence:FastAPI 按 exception class MRO 查找最具体 handler。
   leaf handler 优先匹配,2 个 base fallback 兜底子类漏注册,
   ``MxaError`` final fallback 兜未知业务异常,2 个 FastAPI 默认 handler
   兜 404/405/422 框架级错误。
2. 日志隐私(02 § 12 + 决策 11 决策 2):
   只记录异常类名 / HTTP code / request path / method,不记录异常 message
   / exc.detail / exc.errors()(可能含用户文件名 / 路径 / 工程片段 / 输入片段)。
3. ``ProjectTooLargeError`` 文案动态化:从 ``AppSettings`` 读
   ``max_upload_size_mb`` / ``max_files_per_project``,避免文案与配置漂移。
4. ``FileTypeNotAllowedError`` 文案不列扩展名:02 § 9 旧文案列了 6 个扩展名,
   但 TASK-104 实际 ``ALLOW_EXTS`` 比那广得多。本模块文案使用概括性描述。
5. ``EvidenceMissingError`` handler 是 last resort:正常路径走 ChatService
   E 类降级(TASK-205 D13);本 handler 防止意外穿透到客户端时不暴露 500。
6. ``RequestValidationError`` handler 隐私脱敏:**不**回传 exc.errors() 数组,
   只返回通用中文文案(01 § 9 数据隐私 + 决策 11 隐私 spirit)。
"""
```

**`register_error_handlers` 函数 docstring**(line 134-141,需修订):

```python
def register_error_handlers(app: FastAPI, settings: AppSettings) -> None:
    """注册 21 个业务 exception handler + 2 个 FastAPI 默认 handler 兜底。

    注册顺序不影响 FastAPI 行为(FastAPI 按 MRO 查找最具体 handler),
    但注册表按 "leaf -> base fallback -> final fallback" 组织,便于 review。

    21 业务 handler 覆盖 ``MxaError`` 异常树:
    - Upload 子树 leaf 3(ZipBomb / ZipSlip / FileTypeNotAllowed)+ base fallback 1
    - Project 子树 leaf 3(NotFound / TooLarge / ChatSessionNotFound)+ base fallback 1
    - LLM 子树 leaf 5(Auth / Quota / RateLimit / Server / Timeout)
    - Parse 子树 leaf 2(SlxParse / MParse)
    - 顶层 leaf 5(Quota / Evidence / OverviewGen / Store / ChatGen)
    - final fallback 1(MxaError)

    2 兜底 handler:
    - StarletteHTTPException -> 404 / 405 / 其他 HTTP 错误中文化
    - RequestValidationError -> 422 中文化 + 隐私脱敏(不暴露 errors() 数组)
    """
```

### 6.4 `_log_error` 不动(决策 11 决策 2 已遵守)

实地核查 main HEAD `_log_error` 实现已经只记录 metadata(`type(exc).__name__` / `status_code` / `path` / `method`),**不动**。新增 2 兜底 handler 复用此函数。

---

## 决策日志(D1-D4)

### D1 — EvidenceMissingError handler status_code: 500 last resort

**理由**:
- 02 § 9 line 726 写"EvidenceMissingError:内部错误,降级为'不确定'答案返回"
- 正常路径:ChatService E 类降级(TASK-205 D13)在 service 层捕获 EvidenceMissingError,转换为 D 类 / E 类 ChatAnswer 返回 200 + `is_fallback=true` + `fallback_reason=evidence_missing`
- **本 handler 是 last resort**:防止任何未经 ChatService 捕获的 EvidenceMissingError 穿透到客户端时,不暴露未脱敏 message 或 500 generic
- status_code 500:这是"程序 bug 等级"的兜底,意味着代码 path 漏捕获,等同于 final fallback;前端按 `internal_error` 同款处理

**替代方案**:
- A. status_code 403 / 422:**为何不选**:这两个 code 暗示用户请求有问题,但 EvidenceMissingError 是后端 LLM 输出问题,与用户请求无关。
- B. status_code 502:**为何不选**:502 暗示上游服务问题,但本错误是后端 citation 逻辑问题,语义偏差。
- C. 不注册 handler,让 MxaError final fallback 兜底:**为何不选**:可以,但本 handler 提供更精确的 machine_code(`evidence_missing` vs `internal_error`),帮助前端 / 评测 / debug 区分。代价仅 1 个 tuple entry(4 行)。

### D2 — 不重组 tuple 顺序

**理由**:
- FastAPI 按 exception class MRO 查找,**注册顺序不影响 handler 选择**
- 重组 = 范围扩张 + git diff 噪音,review 时模糊"哪行是新增 vs 哪行只是移位"
- 现有顺序虽然 MxaError final fallback 在 #8 位置(LLM leaf 之前),但 FastAPI MRO 正确处理(LLM leaf 比 MxaError 更具体,优先匹配)

**替代方案**:
- A. 重组到"按子树分组 + final fallback 最后":**为何不选**:范围扩张,git diff 噪音(预估 +50 行 diff,实际仅 2 行新增);review 难辨"重组动了什么";本 Task 0 行为变更原则。
- B. 加注释标记现有顺序的子树边界:**为何不选**:可以,但增加 docstring 维护负担(下次有人改顺序又要同步);本 Task docstring 已经在 register 函数级写了子树分组概要(§ 6.3),够了。

### D3 — 404 / 422 兜底实现位置:`register_error_handlers` 函数体内

**理由**:
- 统一入口:所有 handler 注册在同一函数内,API lifespan / 测试 fixture 一次性 setup
- 复用 `_log_error`:不需要重复实现日志隐私逻辑
- 不引入新文件:200 → ~270 行仍 ≤ 300(04 § 4)

**替代方案**:
- A. 拆 `api/middleware/_default_exception_handlers.py`:**为何不选**(预先拆):200 → 270 行有 30 行余量,Codex 实施时若实际超 300 再拆(拆分预案)。
- B. 用 `@app.exception_handler(...)` 装饰器在 `api/main.py` 直接注册:**为何不选**:打散了 handler 注册位置,与现有"所有 handler 在 error_handler.py"模式不一致,可读性差。
- C. 在 `api/main.py` lifespan 内 `app.add_exception_handler(...)`:**为何不选**:同 B,职责打散。

### D4 — 不新增异常类(反例 24 教训)

**理由**:
- 实地核查 exceptions.py 已有 23 类,QuotaExhaustedError / EvidenceMissingError 早在 TASK-101 / 宪法 v2.1 落地
- 本 Task 仅追加 handler,不新增 exception class
- 反例 24 教训:exceptions.py 异常树**已经稳**(TASK-205 D8 之后增长曲线已饱和),不要为追加 handler 而冗余新加 ErrorClass

**替代方案**:
- A. 新增 `Http404Error(MxaError)` / `ValidationFailedError(MxaError)` 让 404 / 422 兜底走业务异常树:**为何不选**:404 / 422 是框架级错误,不属于业务异常(MxaError 子树是业务异常硬约束,04 § 10);引入这类异常会扭曲业务异常树语义。
- B. 新增 `ChatNotFoundError(MxaError)` 与 `ChatSessionNotFoundError(ProjectError)` 配对:**为何不选**:范围外,且 ChatSessionNotFoundError(ProjectError) 跨树设计已是 TASK-205 D8 拍板,本 Task 不动。

### D5 — TASK-205 🔍→✅ 搭车 chore 是 PM 显式授权例外(R1 P1-4 新增)

**理由**:
- 决策 07 默认规则是 Codex 只把当前 Task 推到 🔍,✅ 由 PM 在合并后改(避免 Codex 自审自批)
- 本 Task 搭车 chore 把 TASK-205 从 🔍 改 ✅,**与默认规则不同**
- 本轮 PM 在开场已明确授权这 4 行 chore(沿用第十二 → 第十三任移交模式)
- R1 P1-4 抓住此分歧并要求文档明示授权边界

**授权边界明示**:
- ✅ 允许:**本次** TASK-205 🔍→✅ 由 Codex 搭车实施(PM 本次显式授权的历史状态补账)
- ❌ 禁止:**后续** Codex 自行把任意 Task 从 🔍 推到 ✅(决策 07 默认规则继续生效)
- ❌ 禁止:把本 Task D5 作为"先例"引用,要求后续 Task 自动放宽决策 07

**替代方案**:
- A. 不搭车,等 PR merge 后 PM 单独跑字节级 Python 改 03 索引:**为何不选**:违反"一刀切 copy-paste 派活脚本"PM 偏好(决策 08 第 4 条精神);4 行字节级 Python 完全可纳入 Codex 派活脚本
- B. PM 在 GitHub 网页改:**为何不选**:违反决策 08 字节级 Python 规则(网页编辑器可能 LF→CRLF 漂移,反例 14 / 决策 08 坑 2 同源)

---

## 测试与验收命令

### 11.1 测试覆盖边界(`tests/api/test_error_handlers.py`)

| 测试类 | 覆盖 |
|---|---|
| `TestBusinessHandlers`(parameterize 19 既有) | 每个 handler 触发 → 断言 status_code + JSON shape `{"error", "message"}` + machine_code 匹配 + message 字面匹配(允许 ProjectTooLargeError 模板化 assert)|
| `TestNewLeafHandlers`(本 Task 新增 2) | QuotaExhaustedError → 402 quota_exhausted + EvidenceMissingError → 500 evidence_missing |
| `TestDefaultHandlers`(本 Task 新增 2 兜底,R1 P1-1 + P1-2 闭合 4 个 machine_code + 隐私脱敏)| 4 case:(1)GET /nonexistent → 404 not_found,响应体不含 detail / errors / 原始路径片段;(2)POST 到 GET-only endpoint → 405 method_not_allowed,响应体不含 detail;(3)测试专用 endpoint 抛 `StarletteHTTPException(status_code=418, detail="SECRET_DETAIL")` → 418 http_error,响应体 + 日志均不含 `SECRET_DETAIL`(R1 P1-1 generic 分支隐私守门);(4)POST `{"count": "SECRET_STUDENT_INPUT"}` 到 `count: int` Pydantic 字段 endpoint → 422 validation_error,响应体 + 日志均不含 `SECRET_STUDENT_INPUT` / `errors` / `detail`(R1 P1-2 真隐私守门,**非** 仅"缺字段"测试)|
| `TestLogPrivacy`(决策 11 决策 2 + 01 § 9,R1 P2-3 收窄)| 触发任意 handler → 断言 logger 调用参数**只含** `type(exc).__name__` / status / path / method,**不含** message / exc.detail / exc.errors() — **统一用** `mocker.patch("api.middleware.error_handler.logger.error")`(loguru 与 pytest `caplog` 默认不天然等价,本 Task 唯一推荐写法,避免测试不稳定)|
| `TestDocstring`(反例 24 同款守门) | 用 `re.search` 断言 `error_handler.py` docstring **不**含"8 个 handler"过期字面,**含**"21" + "2 兜底"新字面 |

**parameterize 模板**(避免 21 个独立测试函数):

```python
import pytest
from core.domain.exceptions import (...)  # 21 类

# R1 P2-2 升级:20 静态 handler 字面匹配 expected_message,ProjectTooLargeError
# 因动态文案(模板含 max_upload_size_mb / max_files_per_project)单独测,见下文。
HANDLER_CASES = [
    # (exception_class, expected_status, expected_machine_code, expected_message)
    (ZipBombError, 400, "zip_bomb", "压缩文件异常,请检查后重新上传"),
    (ZipSlipError, 400, "zip_slip", "压缩包内含非法路径,请重新打包后上传"),
    (FileTypeNotAllowedError, 400, "file_type_not_allowed",
     "包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试"),
    (ProjectNotFoundError, 404, "project_not_found",
     "没有找到这个工程,可能已过期或已被删除,请重新上传"),
    # ProjectTooLargeError 动态文案,单独测,不在此表
    (UploadError, 400, "upload_error", "上传文件有问题,请检查压缩包后重新上传"),
    (ProjectError, 400, "project_error", "工程处理失败,请重新上传后再试"),
    (MxaError, 500, "internal_error", "出了点问题,我们已经记录,稍后再试"),
    (LLMAuthError, 503, "llm_auth", "服务暂时不可用,请稍后重试"),
    (LLMQuotaError, 503, "llm_quota", "服务繁忙,请稍后"),
    (LLMRateLimitError, 429, "llm_rate_limit", "请求太频繁,稍等一下"),
    (LLMTimeoutError, 504, "llm_timeout", "网络较慢,正在重试..."),
    (LLMServerError, 502, "llm_server", "AI 服务暂不稳定,请刷新重试"),
    (SlxParseError, 400, "slx_parse", "Simulink 模型解析失败,可能版本过老或损坏"),
    (MParseError, 400, "m_parse", ".m 文件解析失败,请检查文件编码"),
    (OverviewGenerationError, 502, "overview_generation", "导览生成失败,请刷新重试"),
    (ChatSessionNotFoundError, 404, "chat_session_not_found", "对话不存在"),
    (StoreError, 500, "store_error", "系统暂时不可用,请稍后重试"),
    (ChatGenerationError, 502, "chat_generation", "回答生成失败,请刷新重试"),
    (QuotaExhaustedError, 402, "quota_exhausted",                          # ★ 本 Task
     "已达到合理使用上限,可联系加量"),
    (EvidenceMissingError, 500, "evidence_missing",                        # ★ 本 Task
     "出了点问题,我们已经记录,稍后再试"),
]

@pytest.mark.parametrize("exc_class,status,code,message", HANDLER_CASES)
async def test_handler(test_client, exc_class, status, code, message):
    """20 个静态文案 handler 全字面匹配(R1 P2-2 守住"文案不动")"""
    response = await test_client.get(f"/_test/raise/{exc_class.__name__}")
    assert response.status_code == status
    body = response.json()
    assert body == {"error": code, "message": message}  # exact match,无额外字段


async def test_project_too_large_dynamic_message(test_client, settings):
    """ProjectTooLargeError 动态文案模板 assert(R1 P2-2 例外)"""
    response = await test_client.get("/_test/raise/ProjectTooLargeError")
    assert response.status_code == 413
    body = response.json()
    assert body["error"] == "project_too_large"
    # 模板含 max_upload_size_mb 与 max_files_per_project,字面 contains 检查
    assert str(settings.max_upload_size_mb) in body["message"]
    assert str(settings.max_files_per_project) in body["message"]
    assert "MB 以内" in body["message"]
    assert "个文件以下" in body["message"]
```

**测试 endpoint 隔离硬契约**(R1 P1-3 升级,从"风险"提升为"测试 fixture 硬契约"):

1. **必须**创建独立的 `FastAPI()` test instance(推荐使用 `api.main.create_app()` 工厂模式或新建 `test_app = FastAPI()`),在 fixture 内调用 `register_error_handlers(test_app, settings)` + 挂 `/_test/raise/{exc_name}` debug endpoint
2. **禁止**向真实 `api.main.app` 注册任何 `/_test/*` endpoint;**禁止** `monkeypatch.setattr("api.main.app", ...)` 或类似 patch 真实 app
3. 测试 endpoint dict 覆盖 21 类业务异常 + 测试 endpoint 用于触发 405 / 418 / 422 隐私场景(P1-1 / P1-2)
4. fixture 作用域 `function` 级:每个测试函数独立 test_app,避免 handler 注册副作用跨 case 泄漏
5. **验收 grep 守门**(§ 11.2 #16 新增):`grep -rn "_test/raise" api/ --include='*.py'` 应空,确保 `/_test/*` 仅在 `tests/` 内出现,不污染生产 `api/`

**为何升级**:R1 P1-3 抓出原文将测试隔离写在 § 12.1 R6 "风险"段,但 fixture 错误实现可能在生产 app 暴露 endpoint,这是硬契约不是软风险。

### 11.2 验收命令(沿用 task-205 风格)

```bash
# 1. Stage 0 实地核查 10 条 grep 全通过
# PR 描述明示每条 grep 实际输出与期望一致

# 2. 单元测试全绿
pytest tests/api/test_error_handlers.py -v

# 3. 既有测试无回归
pytest tests/ -v

# 4. lint + type-check + format
make lint && make type-check && python -m ruff format --check .

# 5. 每文件 ≤ 300 行
git diff --name-only main...HEAD -- '*.py' \
  | xargs -r -n1 wc -l \
  | awk '$1 > 300 {print; bad=1} END {exit bad+0}'

# 6. requirements.txt 0 新增
git diff origin/main..HEAD -- requirements.txt
# 期望:无输出

# 7. 决策 11 兜底 2 条 grep 应空
grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
grep -rnE 'str\(exc\)|repr\(exc\)|\{exc\}' core/ adapters/ features/ api/ app/ \
  --include='*.py' --exclude-dir=.venv --exclude-dir=.git
# 期望:两条均空

# 8. error_handlers tuple 19 → 21(本 Task +2 leaf)
python3 -c "import re, pathlib; data = pathlib.Path('api/middleware/error_handler.py').read_text(); print(len(re.findall(r'\(\s*[A-Z]\w+Error,\s*\n\s*_make_', data)))"
# 期望:21

# 9. 404 / 422 兜底已注册
grep -nE "add_exception_handler\(\s*(StarletteHTTPException|RequestValidationError)" api/middleware/error_handler.py
# 期望:命中 2 行

# 10. docstring 同步(反例 24 守门)
grep -nE "minimal ERROR_MAP[^\d]*\b8\b|注册\s*\b8\s*个" api/middleware/error_handler.py
# 期望:空(本 Task 完工后旧字面已修订)

grep -nE "21 个业务 handler|2 个 FastAPI 默认 handler 兜底" api/middleware/error_handler.py
# 期望:命中(新 docstring 字面)

# 11. exceptions.py 0 新增(范围边界硬约束)
git diff origin/main..HEAD -- core/domain/exceptions.py
# 期望:无输出

# 12. features/* 0 修改(范围边界硬约束)
git diff --name-only origin/main..HEAD -- features/
# 期望:无输出

# 13. 隐私脱敏断言(422 不暴露 errors / 405 不暴露 detail / 418 generic 不暴露 SECRET)
# (由 pytest TestDefaultHandlers 4 case + TestLogPrivacy 覆盖,无独立 grep 命令)

# 14. 测试 endpoint 隔离守门(R1 P1-3 硬契约)
grep -rn "_test/raise" api/ --include="*.py"
# 期望:空(/_test/* 仅出现在 tests/,不污染生产 api/)

# 15. make check 一键
make check

# 16. 真启动验收(PM 本地体验,可选)
# 启动后用 curl 触发 404 / 422:
curl -i http://127.0.0.1:8000/nonexistent
# 期望:HTTP/1.1 404 + body {"error":"not_found","message":"请求的资源不存在"}

curl -i -X POST http://127.0.0.1:8000/projects/invalid_id/chat -H "Content-Type: application/json" -d '{}'
# 期望:HTTP/1.1 422 + body {"error":"validation_error","message":"请求参数有问题,请检查后重试"}
# 期望:body 不含 "detail" / "errors" 字段
```

### 11.3 PM 验收 Step B(决策 08 第 2 条)

- [ ] `git status` clean + `git log --oneline main..HEAD` commit 拆分合理
- [ ] `make check` 全绿
- [ ] 11.2 第 7 / 8 / 9 / 10 / 11 / 12 条 grep 命令实际跑,输出与期望一致
- [ ] `api/middleware/error_handler.py` wc -l ≤ 300
- [ ] PR 描述明示反例 24 同款 docstring 修订采纳
- [ ] 搭车 chore 03 索引 4 处修订 git diff 仅这 4 行(决策 08 字节级 Python 保留 CRLF/LF)

### 11.4 PR 元信息

- PR 标题:`TASK-206: 错误处理 + 中文化(Week 2 收尾)`
- 分支名:`task/TASK-206-error-handling-and-i18n`
- PR 描述按 04 § 3 模板 + 逐条勾选 11.2 验收 + R1 反馈采纳清单(若有)

---

## 风险与决策日志

### 12.1 风险与注意点(7 条)

**R1 docstring 漂移再次发生(反例 24 同款)**

本 Task 修订 docstring 反映 21 + 2,但下一任(TASK-207 或 Week 3)若追加 handler 而忘记同步 docstring,**反例 24 再次出现**。规避:本 Task 11.2 #10 grep 守门,后续 Task Stage 0 沿用此 grep;Phase 2 考虑引入"docstring linter"(超出本 Task 范围)。

**R2 tuple 顺序不重组的可读性代价**

#8 MxaError final fallback 在 LLM leaf 之前,review 时困惑。规避:register 函数 docstring(§ 6.3)按子树分组列出 21 handler,作为代码层级的"reading order"提示;不动 tuple 物理顺序(D2)。

**R3 EvidenceMissingError handler 的"last resort"语义易被后续误解**

未来 ChatService 实施者可能误以为"raise EvidenceMissingError 后会自动 200 + E 类降级",实际是 500。规避:本 Task `evidence_missing` machine_code + handler docstring 注释明示"last resort";TASK-307 完整 CitationEnforcer 实施时,**必须**在 ChatService 内部 `try / except EvidenceMissingError` 转换为 E 类 ChatAnswer + `is_fallback=true`,不让其穿透到 handler。

**R4 422 隐私脱敏与开发体验的张力**

不回传 errors() 数组保护隐私,但开发期前端 / 后端联调时缺少"哪个字段错"信息,可能拖慢调试。规避:开发期可临时打开 `DEBUG_VALIDATION=true` env var(Phase 2 实现,本 Task 不做);MCS 默认隐私优先,日志侧记录 `type(exc).__name__` 足够定位 endpoint。

**R5 FastAPI 内部异常类导入 stability**

`fastapi.exceptions.RequestValidationError` 与 `starlette.exceptions.HTTPException` 是公开 API,但 FastAPI / Starlette 大版本升级可能漂移路径。规避:requirements.txt 锁版本(沿用 TASK-201);CI 跑 import 校验(make check 已覆盖)。

**R6 测试 endpoint `/_test/raise/{exc_name}` 污染生产风险**

若 autouse fixture 实现错误(未限制仅测试环境注册),可能在生产 app 暴露 endpoint。规避:fixture 实现使用独立 `test_app` 实例(`fastapi.testclient.TestClient(test_app)`),不 patch 真实 `api.main.app`;conftest 加注释明示"仅测试用"。

**R7 ChatSessionNotFoundError 跨树设计的 review 困惑**

ChatSessionNotFoundError 是 ProjectError 子类(TASK-205 D8),review 时可能困惑"为何 chat 异常落 project 子树"。规避:本 Task docstring(§ 6.3 register 函数级)写"Project 子树 leaf 3(NotFound / TooLarge / ChatSessionNotFound)"明示;不动 exceptions.py(范围边界 D4)。

### 12.2 决策日志紧凑表

| # | 决策 | 替代方案被拒理由 |
|:-:|---|---|
| D1 | EvidenceMissingError → 500 last resort | 403/422 语义偏差;502 上游服务暗示偏差;不注册 = 失精确 machine_code |
| D2 | tuple 顺序不重组 | 重组 = 范围扩张 + git diff 噪音;FastAPI MRO 不依赖顺序 |
| D3 | 404 / 422 兜底实现在 `register_error_handlers` 函数内 | 拆文件 = 预先模块化(拆分预案);main.py 装饰器 = 职责打散 |
| D4 | 0 新增异常类(反例 24 教训) | 新加 Http404Error 扭曲业务异常树语义;ChatNotFoundError 范围外 |
| D5 | TASK-205 🔍→✅ 搭车 PM 显式授权例外(R1 P1-4) | 等 PR merge 后单独跑违反派活脚本一刀切;GitHub 网页改违反决策 08 字节级 |

### 12.3 后续 Task 接力点

- **TASK-207**(ProjectOverview Schema + 教学输出契约):不依赖本 Task,可并行
- **TASK-307**(完整 CitationEnforcer):**依赖本 Task** EvidenceMissingError handler 已就位(last resort 防穿透);实施时在 ChatService 内 try/except 转 E 类降级,handler 仅兜未捕获情况
- **TASK-402 / 403**(前端 UI):依赖本 Task 21 + 2 handler 文案 freeze,前端按 `error` machine_code dispatch UI 状态
- **Phase 2**(i18n):若上线后需多语言,本 Task `_make_handler` 工厂签名预留 message 参数,Phase 2 改造为按 `Accept-Language` 选 message 字典即可,无需重写架构

### 12.4 Phase 2 候选

- `DEBUG_VALIDATION=true` env var 开关 422 errors() 回传(开发体验)
- i18n 多语言文案(`messages_zh.yaml` / `messages_en.yaml` + locale negotiation)
- docstring linter / mypy plugin 守门 docstring 与 tuple 同步
- 429 / 503 / 504 加 Retry-After header

---

## Checklist(精简)

**实施前**:已读 5 核心文档 + 决策 06/07/08/09/11 + 反例 1-24;实地核查 19 handler tuple + 23 异常类树 + 决策 11 兜底空 + 404/422 customize 无 + docstring 漂移(反例 24 同款);理解 0 新增异常类原则 + tuple 不重组 + last resort 语义 + 隐私脱敏 422。

**完工前**:§ 11.2 验收 1-15 全过;commit subject 单行无 body(反例 17);完工三件套(决策 08);03 索引字节级修订(4 行)+ docstring 同步;PR(Codex 给 PM 标题 + 正文)。

---

**版本**:v0.2(R1 conditional pass,7 反馈全采纳,直接进 Codex,不升 R2)
**日期**:2026-06-05
**作者**:Claude(架构师,第十四任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / `20260604-11`
**关联反例**:反例 24(docstring 漂移,本 Task 触发修订)+ 反例 21 / 23(交接 summary 数字不可信,本 Task onboard 实地核查 23 异常类纠正"16 + 3 chat = 19"误报)
**审批**:**一审 1 轮 / R1 conditional pass / 直接进 Codex**(若实施期出现"调试期回传 validation errors / DEBUG_VALIDATION env var 提前实施"等任一,自动升 R2)
