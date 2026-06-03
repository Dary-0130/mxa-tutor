# TASK-106: DeepSeek TextProvider 实现

## 状态

🔲 未开始

---

## 上下文

这是 Week 1 的第六个 Task,**项目第一个 `adapters/llm/` 模块**,实现 `core/interfaces/llm_provider.py::TextProvider` 抽象接口的具体类,把 DeepSeek API 接入项目。

为什么必须做:

- 宪法 § 7 第 290 行明文路由:**文本 / 代码解读 / 简单问答 → DeepSeek V4-Flash(默认)** / **长上下文 → DeepSeek V4-Pro**
- Week 2 起所有需要 LLM 的 Task(TASK-203 导览生成 / TASK-205 粗 RAG / TASK-305 教学 prompt 优化)都阻塞在本 Task
- TASK-101 已建好 `TextProvider` / `LLMMessage` / `LLMResponse` / `ModelCapability` / 5 个 `LLMError` 子类的"骨架"(纯接口与异常类,无实现)。本 Task 负责"补肉"

本 Task 同时承担**示范责任**:走通 `adapters/llm/` 子目录的代码组织、构造函数注入、API 异常翻译、重试策略,为后续 `adapters/embedding/`(TASK-301 sentence-transformers)/ 未来可能的视觉适配器 `adapters/vision/` 立样。

下游消费者:

- **TASK-203**(导览生成):用 `TextProvider.chat()` 调 LLM 生成项目导览(JSON mode)
- **TASK-205**(粗 RAG 问答):同上,强制 citations
- **TASK-305**(教学 Prompt 优化):跑评测集,可能需要切换 V4-Flash ↔ V4-Pro 比较
- **TASK-307**(证据引用强制器):间接消费

**本 Task 不在 `docs/01_PROJECT_CONSTITUTION.md` 第 5 节"何时找 AI 二审复审"的核心 Task 清单里**(清单:101/102/104/107/205/304),Task 文档完稿后**直接交给 Codex 实施**,不走 GPT 二审。

**本 Task 同时是项目第二个加 runtime 依赖的 Task**(项目第一个是 TASK-108 加的 `pydantic-settings==2.6.1`),本次加 `openai==1.54.0`(04 § 6 工程规范第 265 行模板已列,本 Task 是首次实际入仓)。

上下游依赖:

- **上游**:TASK-101(契约源,`TextProvider` / `LLMMessage` / `LLMResponse` / `ModelCapability` / 5 个 `LLMError` 子类)/ TASK-108(`AppSettings.deepseek_api_key` / `deepseek_base_url`,**仅供构造时获取**,本 Task **不**在 adapter 内 import AppSettings)
- **下游**:TASK-203 / TASK-205 / TASK-305 / TASK-307(Week 2-3 跨周消费)

---

## 输入(前置依赖)

### 必须已完成的 Task

- ✅ TASK-001(项目骨架,已合并):`adapters/llm/` 目录已存在(空目录,可能含 `__init__.py` 与 `README.md` 占位)
- ✅ TASK-002(开发环境 + CI,已合并)
- ✅ TASK-101(core 接口 + domain 数据结构,已合并):**直接契约依赖**,本 Task 实现 `core/interfaces/llm_provider.py::TextProvider` 并返回 `LLMResponse`,翻译为 5 个 `LLMError` 子类
- ✅ TASK-108(`app/config.py + pydantic-settings`,已合并):**间接依赖**,本 Task 自身**不 import AppSettings**,但下游(TASK-201 / 203)构造 `DeepSeekTextProvider` 时会从 `AppSettings.deepseek_api_key` / `deepseek_base_url` 取值传入

### 必须存在的文件 / 状态

- `main` 分支处于 TASK-105 已 ✅ 之后的 HEAD(假设软并行流水线;若 105 还在 🔍 也不阻塞 106 实施,因为两者代码层无重叠)
- 以下 `core/` 文件由 TASK-101 建好,本 Task **直接 import 使用**(契约不变):
  - `core/interfaces/llm_provider.py` — `LLMMessage` / `LLMResponse` / `ModelCapability` dataclass + `TextProvider` ABC
  - `core/domain/exceptions.py` — `LLMError` / `LLMAuthError` / `LLMQuotaError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError`
- 以下目录现状:
  - `adapters/llm/`:已存在(TASK-001 建),含 `__init__.py` + `README.md` 占位(空 / 极简内容)
  - `tests/adapters/llm/`:**可能不存在**(TASK-001 / 102 / 103 / 104 只建了 `tests/adapters/parser/`),本 Task 新建此目录 + `__init__.py`
- `main` 分支保护已开,所有改动走 PR + CI 全绿 + Squash

### 必须读过的文档

- `docs/01_PROJECT_CONSTITUTION.md`(整篇,**特别第 7 节技术架构原则与禁止依赖 / 第 8 节工程规则 / 第 9 节数据隐私 "日志不记录原文"**)
- `docs/02_ARCHITECTURE_OVERVIEW.md`(整篇,**特别第 4.3 节 LLM 接口契约 / 第 4.6 节业务异常 / 第 7 节配置管理 / 第 9 节错误翻译表**)
- `docs/04_ENGINEERING_STANDARDS.md`(整篇,**特别第 4 节代码风格(每文件 ≤ 300 行)/ 第 5 节测试规范(LLM 必须 mock + integration 标记) / 第 6 节依赖管理 / 第 9 节日志规范 / 第 10 节异常处理**)
- `docs/05_EXPLANATION_STYLE_GUIDE.md`(本 Task **不直接产出**讲解输出,但 `TextProvider` 是讲解输出的最终通道,需理解下游使用场景)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`
- `docs/decisions/20260601-05-static-scan-must-exclude-venv-and-git.md`
- `docs/decisions/20260601-06-codex-can-read-repo-files.md`
- `docs/decisions/20260601-07-task-index-update-not-docs-change.md`
- `docs/decisions/20260602-08-pm-verify-git-and-preserve-line-endings.md`(**Codex 完工报告必须含 git 三件套**;**改已有文件必须用编辑器或 Python 字节级操作**)
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(架构师纪律,**特别**注意反例 5:Codex 实施时遇文档与现状不一致,停手抛冲突)
- `docs/tasks/task-101-core-domain-and-interfaces.md`(契约源)
- `docs/tasks/task-108-bootstrap-app-config-layer.md`(**特别**注意 `AppSettings` 实际字段清单,**不含** `deepseek_model` / `deepseek_timeout` / `deepseek_max_tokens` / `deepseek_retry_count` —— 本 Task 通过构造函数参数注入这些,**不**新增 AppSettings 字段)
- 当前 Task 文档:本文

---

## 输出(交付物)

### 新增文件

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `adapters/llm/deepseek.py` | **主入口**,定义 `DeepSeekTextProvider(TextProvider)` + 模块级常量 `DEFAULT_MODEL_NAME` / `DEFAULT_MAX_OUTPUT_TOKENS` / `DEFAULT_CONTEXT_TOKENS` / 重试策略实现 | 180-280 |
| `adapters/llm/_deepseek_errors.py` | 私有,HTTP status code → `LLMError` 子类的翻译表 + 翻译函数 | 60-100 |
| `tests/adapters/llm/__init__.py` | 空文件,模块标记 | — |
| `tests/adapters/llm/conftest.py` | `pytest-mock` fixture:`fake_openai_client`(用于 mock `openai.OpenAI` 构造与 `chat.completions.create` 返回值) | 60-100 |
| `tests/adapters/llm/test_deepseek_unit.py` | 单元测试:正常路径 / JSON mode / 异常翻译(5 类)/ 重试逻辑 / Timeout / ModelCapability | 200-300 |
| `tests/adapters/llm/test_deepseek_integration.py` | 集成测试,**标记 `@pytest.mark.integration` 默认跳过**,真实调 DeepSeek API(本地手动跑) | 40-80 |

`_deepseek_errors.py` 是 `deepseek.py` 的内部协作模块,**不暴露**到 `adapters/llm/__init__.py`(只导出 `DeepSeekTextProvider`)。

### 修改文件

- **`requirements.txt`** — TASK-108 已含 `pydantic-settings==2.6.1`,本 Task **新增 1 行** `openai==1.54.0`(**项目第二个 runtime 依赖**,04 § 6 工程规范第 265 行模板已列)
- **`requirements-dev.txt`** — 本 Task **新增 1 行** `pytest-mock==3.14.0`(若 TASK-108 已经加过则跳过;**先 `cat` 核查**)
- **`adapters/llm/__init__.py`** — TASK-001 建,本 Task **追加** `from .deepseek import DeepSeekTextProvider`,**不动**现有内容(若为空)
- **`adapters/llm/README.md`** — TASK-001 占位,本 Task **重写**:列出 `DeepSeekTextProvider` 的职责 + 用法示例(5-10 行)
- **`pyproject.toml`** — 若现 mypy 配置不含 `adapters/llm/`,本 Task **不动**;若现 mypy target 写 `adapters/`(整 adapters 目录),自动覆盖 `adapters/llm/`。**先 `cat pyproject.toml` 核查**,**若需要修改 pyproject.toml,停手问 PM**
- **`docs/03_TASK_INDEX.md`** — 本 Task 推 🔲 → 🔍,Week 1 进度条第 6 位 ⬜ → 🔍。**必须用字节级 Python 操作(决策 08)**,详见"风险与注意点"风险 1

### 不动文件

- `core/` 下所有文件(本 Task **不**修改 task-101 已建的 `TextProvider` / `LLMMessage` / `LLMResponse` / `ModelCapability` / `LLMError` 子类字段定义)
- `app/config.py`(本 Task **不**新增 AppSettings 字段;default model / timeout / max_tokens 全部以模块级常量或构造函数参数实现)
- `adapters/parser/` / `adapters/embedding/` / `adapters/storage/` / `adapters/payment/`
- `features/` / `api/` / `web/`
- `Makefile` / `.github/workflows/ci.yml` / `scripts/check_repo_hygiene.sh`
- `docs/` 下除 `03_TASK_INDEX.md` 之外的任何文件(决策 07 边界)
- `tests/fixtures/` / `tests/core/` / `tests/adapters/parser/` / `tests/app/`
- 其他 Task 的代码与测试

### 新增依赖

**1 个 runtime 依赖**(项目第二个):

```
openai==1.54.0
```

**可能 0-1 个 dev 依赖**(取决于 TASK-108 是否已加):

```
pytest-mock==3.14.0
```

Codex 实施前**必须 `cat requirements-dev.txt` 核查 `pytest-mock` 是否已在**。若已在则**不动**;若不在则**追加**。

注意:`openai` SDK 内部依赖 `httpx` / `pydantic` / `anyio` 等,所有都是 transitively 引入,**不要**显式加到 `requirements.txt`。

### 新增配置项

**0 个**。本 Task **不修改 `app/config.py`**。

本 Task 通过**构造函数参数**让消费方传入:`api_key` / `base_url` / `model` / `timeout` / `max_output_tokens` / `retry_count`。下游(TASK-201 依赖注入容器)调用时从 `AppSettings.deepseek_api_key` / `deepseek_base_url` 取出传入即可。

**若 Codex 强烈认为需要新增 AppSettings 字段**(例如 `deepseek_model` / `deepseek_timeout`),**停手问 PM**。这是问题 3 已经裁决过的边界:LLM model 名 / 超时 / max_tokens / retry 都不是"运维需要在不同环境调整"的配置,不进 AppSettings。

---

## 范围(必须做)

- [ ] 从 `main` 切分支 `task/TASK-106-deepseek-text-provider`
- [ ] **依赖结构理解**:实施前**第一件事**,跑下面命令看现状,确认本 Task 文档"输入"小节描述与实际一致:
  ```bash
  cat adapters/llm/__init__.py adapters/llm/README.md
  ls -la adapters/llm/
  cat requirements.txt requirements-dev.txt
  cat pyproject.toml
  ```
  若发现与本文档"输出"小节描述显著不符,**停手抛冲突给 PM**,不要默默偏离
- [ ] **追加 `openai==1.54.0` 到 `requirements.txt`**(单行追加,不动现有 `pydantic-settings==2.6.1`)
- [ ] **核查并必要时追加 `pytest-mock==3.14.0` 到 `requirements-dev.txt`**(若不在)
- [ ] `pip install -r requirements-dev.txt` 把新依赖装上(本地验证)
- [ ] **建 `adapters/llm/_deepseek_errors.py`**(详见接口契约 § 7.3):
  - [ ] 定义 `translate_openai_error(exc: Exception) -> LLMError` 函数
  - [ ] HTTP 401 / 403 → `LLMAuthError`
  - [ ] HTTP 402 / 余额不足 → `LLMQuotaError`
  - [ ] HTTP 429 → `LLMRateLimitError`
  - [ ] HTTP 5xx → `LLMServerError`
  - [ ] `openai.APITimeoutError` / `httpx.TimeoutException` → `LLMTimeoutError`
  - [ ] `openai.APIConnectionError` → `LLMServerError`(连接级问题视为服务端不可用)
  - [ ] 未知异常 → `LLMServerError`(兜底,保留 `__cause__` 链)
- [ ] **建 `adapters/llm/deepseek.py`**(详见接口契约 § 7.1 / 7.2 完整骨架):
  - [ ] 模块级常量:`DEFAULT_MODEL_NAME = "deepseek-v4-flash"` / `DEFAULT_BASE_URL = "https://api.deepseek.com"` / `DEFAULT_MAX_OUTPUT_TOKENS = 8192` / `DEFAULT_CONTEXT_TOKENS = 1_000_000` / `DEFAULT_RETRY_COUNT = 3` / `DEFAULT_RETRY_BACKOFFS = (0.5, 1.0, 2.0)`
  - [ ] 模块级 `CAPABILITY: dict[str, ModelCapability]` 表(model_name → ModelCapability),含 `deepseek-v4-flash` + `deepseek-v4-pro` 两条
  - [ ] 类 `DeepSeekTextProvider(TextProvider)`,构造函数签名见 § 7.1
  - [ ] `chat()` 同步方法实现(对齐 task-101 ABC 签名,**不**改成 async)
  - [ ] `capability()` 返回模块级表中对应的 ModelCapability
  - [ ] 内部 `_call_with_retry()` 私有方法,3 次指数退避(0.5s / 1s / 2s)只在 `LLMRateLimitError` / `LLMTimeoutError` / `LLMServerError` 时重试,其他异常立即上抛
  - [ ] **日志**(loguru):每次调用记录 INFO `model=xxx tokens_in=N tokens_out=M latency_ms=L`,**不**记录 messages 原文(04 § 9 数据隐私硬约束)
  - [ ] 类 docstring + 公开方法 docstring(Google 风格)
- [ ] **追加 export 到 `adapters/llm/__init__.py`**:`from .deepseek import DeepSeekTextProvider`
- [ ] **更新 `adapters/llm/README.md`**:列出 `DeepSeekTextProvider` 职责 + 5-10 行用法示例
- [ ] **建测试目录与文件**:`tests/adapters/llm/__init__.py` + `tests/adapters/llm/conftest.py`(详见 § 7.4 fixture)
- [ ] **建单元测试**(`tests/adapters/llm/test_deepseek_unit.py`):
  - [ ] `test_chat_normal_path_returns_llm_response`:mock 正常 200,断言 LLMResponse 字段填充正确
  - [ ] `test_chat_passes_messages_role_content`:断言 messages 的 role / content 透传给 openai SDK
  - [ ] `test_chat_passes_timeout_and_max_tokens`:断言 timeout / max_tokens 参数透传
  - [ ] `test_json_mode_sends_response_format`:`json_mode=True` 时,断言 `response_format={"type": "json_object"}` 传入
  - [ ] `test_json_mode_false_omits_response_format`:`json_mode=False`(默认)时,不传 `response_format`
  - [ ] `test_auth_error_translated`:mock 401 → 抛 `LLMAuthError`
  - [ ] `test_quota_error_translated`:mock 402(余额不足)→ 抛 `LLMQuotaError`
  - [ ] `test_rate_limit_translated_and_retried`:mock 前 3 次 429,第 4 次 200 → **重试 3 次后成功**(总共 4 次调用)
  - [ ] `test_rate_limit_exhausted_raises`:mock 4 次 429 → 抛 `LLMRateLimitError`(重试耗尽)
  - [ ] `test_server_error_translated_and_retried`:mock 前 2 次 503,第 3 次 200 → 重试 2 次后成功
  - [ ] `test_timeout_translated_and_retried`:mock 前 1 次 `APITimeoutError`,第 2 次 200 → 重试 1 次后成功
  - [ ] `test_unknown_error_translated_to_server_error`:mock 未知异常 → 抛 `LLMServerError`(且 `__cause__` 保留原异常)
  - [ ] `test_capability_returns_v4_flash_by_default`:`DeepSeekTextProvider(api_key="fake")` 默认 → `capability().model_name == "deepseek-v4-flash"`
  - [ ] `test_capability_returns_v4_pro_when_constructed`:`DeepSeekTextProvider(api_key="fake", model="deepseek-v4-pro")` → `capability().model_name == "deepseek-v4-pro"`
  - [ ] `test_capability_unknown_model_raises_value_error`:`DeepSeekTextProvider(api_key="fake", model="invalid")` 在构造时立即抛 `ValueError`(不等到 chat 调用)
  - [ ] `test_no_message_content_logged`:跑一次 chat,**断言 loguru 输出里不包含 messages 原文**(用 `caplog` 或 loguru fixture)
- [ ] **建集成测试**(`tests/adapters/llm/test_deepseek_integration.py`):
  - [ ] **整个测试文件标记 `@pytest.mark.integration`**,默认跳过(CI 不跑,本地手动 `pytest -m integration` 才跑)
  - [ ] 文件顶部要求环境变量 `DEEPSEEK_API_KEY`,缺则 `pytest.skip("DEEPSEEK_API_KEY not set")`
  - [ ] `test_real_chat_returns_nonempty_text`:真实 API 调一次,断言 LLMResponse.text 非空 + token 数 > 0
  - [ ] `test_real_json_mode_returns_valid_json`:真实 API 调用 `json_mode=True`,断言返回值 `json.loads()` 成功
- [ ] **本地全检通过**:`make check` 全绿 + `python -m ruff format --check .`(决策 09 反例 8 + 11)
- [ ] **改 `docs/03_TASK_INDEX.md`**:
  - 把 TASK-106 状态从 🔲 改为 🔍
  - Week 1 进度条第 6 位 ⬜ 改为 🔍
  - **必须用字节级 Python 操作**(`read_bytes` + `bytes.replace` + `write_bytes`),详见风险 1
- [ ] **本 Task 最后一个 commit**:`docs: mark TASK-106 as in-review in task index`
- [ ] **完工报告必须含 git 三件套**(决策 08):`git status` / `git log --oneline main..HEAD` / `git push` 完整输出
- [ ] **提 PR**(Codex 给 PM 标题 + 正文,PM 在 GitHub 网页创建)

---

## 不做(明确排除)

- ❌ **流式响应**(streaming):`capability().supports_streaming = False`;Phase 2 内测后视用户体验反馈再决定
- ❌ **Function calling / tool use**:`capability().supports_tool_call = False`;MCS 不用,Phase 2 视需求加
- ❌ **DeepSeek 特有的 `reasoning_content` 字段提取**(deepseek-reasoner / deepseek-v4-pro thinking 模式):返回 `text` 仍是 `content` 字段,`reasoning_content` MCS 暂不展示
- ❌ **多 model 并行 / load balancing**:单 model 单 provider 实例
- ❌ **缓存层**(LLM call cache):归 features 层 / Phase 2 决定
- ❌ **修改 `app/config.py::AppSettings`**:不新增 `deepseek_model` / `deepseek_timeout` / `deepseek_max_tokens` / `deepseek_retry_count` 字段,通过构造函数参数注入
- ❌ **修改 TASK-101 已建的 `TextProvider` / `LLMMessage` / `LLMResponse` / `ModelCapability` / `LLMError` 子类字段定义**(尤其不要试图把 `TextProvider.chat` 改成 `async def`,那是跨 Task 修改契约,需走宪法修订流程)
- ❌ **新增 `LLMError` 子类**(本 Task 严格用 5 个已有子类:LLMAuthError / LLMQuotaError / LLMRateLimitError / LLMServerError / LLMTimeoutError)
- ❌ **`adapters/embedding/` 任何代码**(归 TASK-301)
- ❌ **执行用户上传代码**(宪法 § 8.1 硬约束,即便本 Task 与上传无关也要遵守)
- ❌ **日志记录 messages 原文 / API key / response 完整内容**(04 § 9 + 宪法 § 9 数据隐私硬约束)
- ❌ **不引入除 openai 外的依赖**(`pytest-mock` 算 dev,若 TASK-108 已加则不重复);**不**引入 tenacity / backoff / requests / httpx 等
- ❌ **真实 API 调用进 CI**:集成测试默认跳过,需 `pytest -m integration` 手动触发
- ❌ **不动 `docs/` 核心文档与决策日志**(决策 07 边界,本 Task 仅允许动 `docs/03_TASK_INDEX.md` 的 TASK-106 状态行 + Week 1 进度条第 6 位)

---

## 接口契约

### 7.1 `adapters/llm/deepseek.py` 关键代码骨架

```python
"""DeepSeek TextProvider 实现(OpenAI-compatible API)。

DeepSeek API 兼容 OpenAI Chat Completions 接口,本 Provider 使用 ``openai`` SDK
配合 DeepSeek base_url 调用。Model 名走 V4 系列(``deepseek-v4-flash`` 默认,
对齐宪法 § 7 路由):

- ``deepseek-v4-flash``: 文本 / 代码解读 / 简单问答(默认)
- ``deepseek-v4-pro``  : 长上下文(整工程塞入)

注意:DeepSeek 旧 model 名 ``deepseek-chat`` / ``deepseek-reasoner`` 计划于
2026-07-24 退役(实地核查 DeepSeek 官方公告),**本 Provider 默认不用旧名**。
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger
from openai import OpenAI

from core.domain.exceptions import (
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.interfaces.llm_provider import (
    LLMMessage,
    LLMResponse,
    ModelCapability,
    TextProvider,
)

from ._deepseek_errors import translate_openai_error


__all__ = ["DeepSeekTextProvider"]


# ---------- 模块级常量 ----------

DEFAULT_MODEL_NAME = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFFS = (0.5, 1.0, 2.0)  # 长度必须 >= DEFAULT_RETRY_COUNT


# ---------- ModelCapability 表 ----------
# 实地核查 DeepSeek 官方 2026-05-03 公告与定价
CAPABILITY: dict[str, ModelCapability] = {
    "deepseek-v4-flash": ModelCapability(
        model_name="deepseek-v4-flash",
        supports_streaming=False,         # MCS 不做 streaming
        supports_json=True,                # JSON mode 走 response_format
        supports_tool_call=False,          # MCS 不用
        supports_long_context=False,       # 默认路由不当作长上下文
        max_context_tokens=1_000_000,      # V4-Flash 1M context
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        cost_input_per_million=0.14,       # USD,cache-miss
        cost_output_per_million=0.28,      # USD
    ),
    "deepseek-v4-pro": ModelCapability(
        model_name="deepseek-v4-pro",
        supports_streaming=False,
        supports_json=True,
        supports_tool_call=False,
        supports_long_context=True,        # 长上下文专用
        max_context_tokens=1_000_000,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        cost_input_per_million=0.435,
        cost_output_per_million=0.87,
    ),
}


class DeepSeekTextProvider(TextProvider):
    """DeepSeek API 适配器(同步,OpenAI-compatible)。

    构造时注入 api_key / base_url / model,不读 ``app.config.AppSettings``
    (分层依赖原则:adapter 不知道配置层存在,由 features 层做依赖注入)。

    Example:
        >>> provider = DeepSeekTextProvider(api_key="sk-xxx")
        >>> response = provider.chat(
        ...     messages=[LLMMessage(role="user", content="hello")],
        ...     json_mode=False,
        ...     timeout=30.0,
        ... )
        >>> print(response.text, response.completion_tokens)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL_NAME,
        retry_count: int = DEFAULT_RETRY_COUNT,
    ) -> None:
        if model not in CAPABILITY:
            raise ValueError(
                f"unsupported model: {model!r}. "
                f"Supported: {sorted(CAPABILITY.keys())}"
            )
        if retry_count < 0:
            raise ValueError(f"retry_count must be >= 0, got {retry_count}")

        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._retry_count = retry_count
        # openai.OpenAI 客户端在构造时不发任何请求,延迟到 chat() 调用
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """同步调用 DeepSeek API,带重试和异常翻译。

        Args:
            messages: ``LLMMessage`` 列表(role 取值 ``"system" / "user" / "assistant"``)。
            json_mode: True 时强制 JSON 输出(传 ``response_format={"type": "json_object"}``)。
                调用方需在 prompt 内明示"输出 JSON",否则 DeepSeek 可能返回非合法 JSON 字符串。
            timeout: 单次 HTTP 调用超时秒数。
            max_tokens: 输出 token 上限,None 则用模型默认(``DEFAULT_MAX_OUTPUT_TOKENS``)。

        Returns:
            ``LLMResponse``,5 个字段全部填充。

        Raises:
            LLMAuthError: 401 / 403。
            LLMQuotaError: 402 / 账户余额不足。
            LLMRateLimitError: 429,重试耗尽后仍未恢复。
            LLMServerError: 5xx / 未知异常,重试耗尽后仍未恢复。
            LLMTimeoutError: 网络 / SDK 超时,重试耗尽后仍未恢复。
        """
        # 1. 构造 OpenAI SDK 参数
        openai_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "timeout": timeout,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = DEFAULT_MAX_OUTPUT_TOKENS
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # 2. 带重试的调用
        return self._call_with_retry(kwargs)

    def capability(self) -> ModelCapability:
        """返回本 Provider 当前 model 的能力声明(从 ``CAPABILITY`` 表查)。"""
        return CAPABILITY[self._model]

    # ---------- 内部方法 ----------

    def _call_with_retry(self, kwargs: dict[str, Any]) -> LLMResponse:
        """执行带指数退避的调用,只在可重试异常上重试。"""
        last_exc: LLMError | None = None
        attempts = self._retry_count + 1  # 总尝试次数 = 重试次数 + 1
        for attempt in range(attempts):
            try:
                t0 = time.monotonic()
                completion = self._client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - t0) * 1000)

                # 提取字段。OpenAI SDK 返回的对象层级:
                # completion.choices[0].message.content (str)
                # completion.usage.prompt_tokens (int) / completion_tokens (int)
                # completion.model (str)
                text = completion.choices[0].message.content or ""
                usage = completion.usage
                resp = LLMResponse(
                    text=text,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    model=completion.model,
                    latency_ms=latency_ms,
                )

                # 日志:只记元数据,不记 messages / text 原文
                logger.info(
                    "LLM call: model={} tokens_in={} tokens_out={} latency_ms={}",
                    resp.model,
                    resp.prompt_tokens,
                    resp.completion_tokens,
                    resp.latency_ms,
                )
                return resp

            except Exception as exc:  # 兜底:任何异常先翻译再判断是否重试
                translated = translate_openai_error(exc)
                last_exc = translated

                # 判断是否可重试
                retriable = isinstance(
                    translated,
                    (LLMRateLimitError, LLMServerError, LLMTimeoutError),
                )
                if not retriable or attempt == attempts - 1:
                    # 不可重试 或 已经是最后一次 → 立即上抛
                    raise translated from exc

                # 等待后重试
                backoff = DEFAULT_RETRY_BACKOFFS[
                    min(attempt, len(DEFAULT_RETRY_BACKOFFS) - 1)
                ]
                logger.warning(
                    "LLM call failed (attempt {}/{}), retrying in {}s: {}",
                    attempt + 1,
                    attempts,
                    backoff,
                    type(translated).__name__,
                )
                time.sleep(backoff)

        # 理论不可达(loop 内必 return 或 raise),兜底
        assert last_exc is not None
        raise last_exc
```

### 7.2 关键设计说明

**构造函数注入 vs AppSettings 直读**:本 Provider **不**在内部 `from app.config import AppSettings`。原因:

1. **分层依赖**:`adapters/llm/` 处于 02 § 1 全景图的"适配器层",**不应**知道 `app/config.py` 存在(分层依赖单向,上层依赖下层,下层不知道上层;`app/` 在 02 § 3 目录结构里是"应用装配层",位于 adapters 之上)
2. **测试 mock 简单**:测试时直接 `DeepSeekTextProvider(api_key="fake")` 即可,不需要 patch AppSettings
3. **未来 dependency injection 容器**(TASK-201)统一处理:在 `app/container.py` 中读 `AppSettings.deepseek_api_key` 传入 `DeepSeekTextProvider()`

下游消费样例(给 Codex 看,**本 Task 不实施**):

```python
# 未来 app/container.py 或 features/chat/service.py 的代码(本 Task 不写)
from app.config import AppSettings
from adapters.llm import DeepSeekTextProvider

def make_text_provider(cfg: AppSettings) -> DeepSeekTextProvider:
    return DeepSeekTextProvider(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        # model / retry_count 用模块默认,或后续 AppSettings 真有这些字段时再传
    )
```

**重试逻辑细节**:

- 总尝试次数 = `retry_count + 1`(默认 = 4 次:原始 1 次 + 重试 3 次)
- backoff sequence:`(0.5, 1.0, 2.0)` 秒,attempt index 超出则用最后一个值
- **只有** `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError` 触发重试,其他异常(LLMAuthError / LLMQuotaError / 未知)立即上抛
- `time.sleep()` 是同步阻塞,符合本 Provider 同步签名

**为什么不引入 tenacity / backoff 库**:

- 04 § 6 工程规范模板没列(冻结的依赖白名单)
- 本 Task 重试逻辑 ~20 行,自己写完全够用
- 引入新依赖会触发宪法 § 15 修订流程

### 7.3 `adapters/llm/_deepseek_errors.py` 异常翻译

```python
"""OpenAI SDK 异常 → ``LLMError`` 子类翻译表。"""
from __future__ import annotations

from core.domain.exceptions import (
    LLMAuthError,
    LLMError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)


def translate_openai_error(exc: Exception) -> LLMError:
    """把 openai SDK 或底层 httpx 异常翻译为业务异常。

    翻译规则按 HTTP status code 优先,SDK 异常类型其次,未知兜底为 ``LLMServerError``.

    Returns:
        永远返回 ``LLMError`` 子类实例(不抛异常,由调用方决定是否 raise)。
    """
    # openai SDK 在 1.x 提供 APIStatusError 等基类,但版本兼容性脆弱
    # 安全做法:用 duck typing 看 status_code / response 属性

    # 1. 看是否有 status_code 属性(openai.APIStatusError 系列)
    status_code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )

    if status_code is not None:
        if status_code in (401, 403):
            return LLMAuthError(f"DeepSeek auth failed: {exc}")
        if status_code == 402:
            return LLMQuotaError(f"DeepSeek quota / balance: {exc}")
        if status_code == 429:
            return LLMRateLimitError(f"DeepSeek rate limit: {exc}")
        if 500 <= status_code < 600:
            return LLMServerError(f"DeepSeek server error {status_code}: {exc}")
        # 其他 4xx:视为客户端使用错误(非配置 / 非鉴权),兜底为 server error
        return LLMServerError(f"DeepSeek unexpected status {status_code}: {exc}")

    # 2. 异常类名匹配(避免 import openai SDK 私有异常类导致版本耦合)
    exc_class_name = type(exc).__name__
    if exc_class_name in ("APITimeoutError", "TimeoutException", "ReadTimeout"):
        return LLMTimeoutError(f"DeepSeek timeout: {exc}")
    if exc_class_name in ("APIConnectionError", "ConnectError"):
        return LLMServerError(f"DeepSeek connection failed: {exc}")

    # 3. 字符串关键词兜底
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return LLMTimeoutError(f"DeepSeek timeout: {exc}")
    if "rate limit" in msg or "too many requests" in msg:
        return LLMRateLimitError(f"DeepSeek rate limit: {exc}")

    # 4. 未知 → 兜底 LLMServerError,保留原异常链
    return LLMServerError(f"DeepSeek unknown error: {type(exc).__name__}: {exc}")
```

**关键设计**:

- **不 import openai SDK 私有异常类**(用 `type(exc).__name__` 字符串匹配)。原因:`openai==1.54.0` 与未来版本的私有异常类名 / 路径可能漂移;duck typing 更稳
- 翻译时**不抛异常**,返回 `LLMError` 实例,由调用方 `raise translated from exc` 保留原异常链
- 优先级:status_code → 类名 → 字符串关键词 → 兜底

### 7.4 `tests/adapters/llm/conftest.py` Mock Fixture

```python
"""tests/adapters/llm/conftest.py — pytest-mock fixture for OpenAI client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class FakeUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class FakeMessage:
    content: str


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]
    usage: FakeUsage
    model: str


@pytest.fixture
def fake_completion_factory():
    """工厂:构造伪 OpenAI ChatCompletion 返回值。"""
    def _make(
        text: str = "fake response",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        model: str = "deepseek-v4-flash",
    ) -> FakeCompletion:
        return FakeCompletion(
            choices=[FakeChoice(message=FakeMessage(content=text))],
            usage=FakeUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            model=model,
        )
    return _make


@pytest.fixture
def mock_openai_client(mocker):
    """mock adapters.llm.deepseek.OpenAI 类构造,返回受控的 client 对象。

    返回 (mock_client, mock_create_method) tuple,测试可以配置 mock_create_method.return_value
    或 .side_effect 来控制 chat.completions.create 的行为。
    """
    mock_client = mocker.MagicMock()
    mock_create = mock_client.chat.completions.create
    # patch the OpenAI symbol where it's imported, not where it's defined
    mocker.patch("adapters.llm.deepseek.OpenAI", return_value=mock_client)
    return mock_client, mock_create
```

**关键**:`mocker.patch("adapters.llm.deepseek.OpenAI", ...)` 必须 patch **import 处**(`adapters.llm.deepseek` 模块的 `OpenAI` 引用),**不是** patch `openai.OpenAI`(那不影响已 import 的引用)。

### 7.5 集成测试模板

```python
# tests/adapters/llm/test_deepseek_integration.py
"""真实 DeepSeek API 调用测试,默认 skip,本地手动跑。

运行:
    DEEPSEEK_API_KEY=sk-xxx pytest -m integration tests/adapters/llm/
"""
import os
import json

import pytest

from adapters.llm import DeepSeekTextProvider
from core.interfaces.llm_provider import LLMMessage


pytestmark = pytest.mark.integration


@pytest.fixture
def real_provider():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")
    return DeepSeekTextProvider(api_key=api_key)


def test_real_chat_returns_nonempty_text(real_provider):
    """真实 API 调用,断言返回非空 text + token 计数 > 0。"""
    response = real_provider.chat(
        messages=[LLMMessage(role="user", content="请用一句话介绍 PID 控制器")],
        timeout=30.0,
    )
    assert response.text.strip() != ""
    assert response.completion_tokens > 0
    assert response.prompt_tokens > 0
    assert response.latency_ms > 0


def test_real_json_mode_returns_valid_json(real_provider):
    """真实 API 调用 + JSON mode,断言返回值能被 json.loads。"""
    response = real_provider.chat(
        messages=[
            LLMMessage(role="user", content='输出 JSON: {"answer": "PID is a controller"}, only JSON'),
        ],
        json_mode=True,
        timeout=30.0,
    )
    parsed = json.loads(response.text)
    assert isinstance(parsed, dict)
```

`@pytest.mark.integration` 标记需要在 `pyproject.toml` 注册(若已注册则不动;若未注册,**Codex 停手问 PM**,不要默默改 pyproject.toml — 注册 marker 是 Makefile/CI 配置范围,非本 Task 范围)。

### 7.6 性能预算

- 单次 `chat()` 调用,无重试场景,P50 latency 取决于 DeepSeek API(~1-5 秒,与本 Provider 实现无关)
- 单元测试套件**总耗时 ≤ 2 秒**(全部 mock,无真实 IO,但有 `time.sleep` 重试 → 测试 mock 时**必须**让 backoff 时间归零或 patch `time.sleep`,详见风险 5)
- 集成测试默认跳过,跑一次约 3-15 秒(取决于网络)

---

## 验收标准

> **以下每条都给出 PM 可在 Git Bash 跑出来的命令**。
> 命令在仓库根目录(`F:\mxa-tutor`)下执行,且已 `source .venv/Scripts/activate`。

### 1. 文件全部创建

```bash
ls adapters/llm/deepseek.py adapters/llm/_deepseek_errors.py tests/adapters/llm/__init__.py tests/adapters/llm/conftest.py tests/adapters/llm/test_deepseek_unit.py tests/adapters/llm/test_deepseek_integration.py
```

### 2. `requirements.txt` 已扩展

```bash
grep -nE "^(pydantic-settings|openai)==" requirements.txt
```

期望:看到两行,版本号 `pydantic-settings==2.6.1` + `openai==1.54.0`。

### 3. `adapters/llm/__init__.py` 已追加 export

```bash
grep -n "DeepSeekTextProvider" adapters/llm/__init__.py
```

### 4. 不引入除 openai 外的 runtime 依赖

```bash
git fetch origin main
git diff origin/main..HEAD -- requirements.txt
```

期望:只看到 `+openai==1.54.0` 一行,无其他新增 / 删除。

### 5. 不修改 TASK-001-105 / 108 已建文件

```bash
git diff origin/main..HEAD --stat -- \
    core/ \
    adapters/parser/ adapters/embedding/ adapters/storage/ adapters/payment/ \
    app/config.py app/__init__.py \
    features/ api/ web/ \
    pyproject.toml Makefile .github/ scripts/ \
    tests/core/ tests/fixtures/ tests/app/ tests/adapters/parser/
```

期望:无输出(本 Task 严格只动 `adapters/llm/` + `tests/adapters/llm/` + `requirements.txt` + 可能 `requirements-dev.txt` + `docs/03_TASK_INDEX.md`)。

### 6. 单元测试全绿

```bash
pytest tests/adapters/llm/test_deepseek_unit.py -v
```

期望:16 个测试通过,运行 ≤ 2 秒。

### 7. 集成测试默认跳过

```bash
pytest tests/adapters/llm/test_deepseek_integration.py -v
```

期望:输出含 `skipped`(因为 `@pytest.mark.integration` 默认不跑 / 或因 `DEEPSEEK_API_KEY` 未设而 skip)。

集成测试本地手动验证:

```bash
DEEPSEEK_API_KEY=sk-xxx pytest -m integration tests/adapters/llm/ -v
```

(PM 用真实 key 跑一次,见到 `passed` 后视为本 Task 通过 review)

### 8. lint 和 type-check 全绿

```bash
make lint        # ruff check
make type-check  # mypy core/ adapters/ features/
python -m ruff format --check .   # 决策 09 反例 8 + 11:用 venv 锁定的 ruff,不用系统全局
```

期望:全过。

### 9. 每文件 ≤ 300 行

```bash
wc -l adapters/llm/deepseek.py adapters/llm/_deepseek_errors.py tests/adapters/llm/test_deepseek_unit.py
```

期望:`deepseek.py` ≤ 280 行;`_deepseek_errors.py` ≤ 100 行;`test_deepseek_unit.py` ≤ 300 行。

### 10. README 已更新

```bash
cat adapters/llm/README.md
```

期望:看到 `DeepSeekTextProvider` 的职责说明 + 5-10 行用法示例。

### 11. TASK_INDEX 状态已更新

```bash
grep -n "TASK-106" docs/03_TASK_INDEX.md
```

期望:看到 TASK-106 那一行状态变成 🔍,Week 1 进度条第 6 位变成 🔍。改动用字节级 Python 操作(详见风险 1),`git diff docs/03_TASK_INDEX.md` 应只显示 2 行 +/-。

按 `docs/decisions/20260601-07-task-index-update-not-docs-change.md` 第 1 条,本 Task **只允许动 `docs/03_TASK_INDEX.md` 这一个 docs 文件**。

### 12. 一键全检

```bash
make check
```

应输出 "All checks passed!"。

### 13. PR 元信息

- PR 标题:`TASK-106: DeepSeek TextProvider 实现`
- 分支名:`task/TASK-106-deepseek-text-provider`
- PR 描述按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板,**逐条勾选上面 1-12 项**并简述每项做了什么;**变更摘要必须明示**:本 Task 引入**项目第二个 runtime 依赖** `openai==1.54.0`,transitively 引入 `httpx` / `anyio` 等

### 14. 完工报告含 git 三件套(决策 08)

完工时必须给 PM:

- 修改的文件清单
- 本地 `make check` + `python -m ruff format --check .` 完整输出
- **`git status` / `git log --oneline main..HEAD` / `git push` 完整输出**
- 验收清单 1-13 项逐条勾选 + 说明
- PR 标题 + PR 正文

**不附三件套 = 没完工**,PM 退回让 Codex 补。

---

## 风险与注意点

### 风险 1:改 `docs/03_TASK_INDEX.md` 必须按决策 08 字节级操作

`docs/03_TASK_INDEX.md` 实际行尾是 **LF**(架构师实地 `cat -A` 核查过)。**禁用**:

- ❌ `pathlib.Path.read_text() + write_text()`
- ❌ `open(path, 'w').write(...)`
- ❌ `sed -i`

**只允许**方式 A(编辑器手改)或方式 B(Python 字节级):

```python
import pathlib

p = pathlib.Path('docs/03_TASK_INDEX.md')
data = p.read_bytes()

# TASK-106 状态行 🔲 -> 🔍
old_status = '| TASK-106 | DeepSeek TextProvider 实现 | 🔲 | Codex | 101 |'.encode('utf-8')
new_status = '| TASK-106 | DeepSeek TextProvider 实现 | 🔍 | Codex | 101 |'.encode('utf-8')
assert old_status in data, 'TASK-106 row not found, check spacing'
data = data.replace(old_status, new_status)

# Week 1 进度条第 6 位 ⬜ -> 🔍
# 注意:本 Task 实施时 main 上 TASK-104 / 108 已 ✅,TASK-105 可能 🔍 或 ✅ 视软并行进度
# Codex 实施前先 grep -n "Week 1" docs/03_TASK_INDEX.md | cat -A 看实际进度条字面,
# 然后精确匹配。下面是常见基线(105 已 🔍 + 104 / 108 已 ✅)的字面:
old_bar = 'Week 1:  [✅✅✅✅🔍⬜⬜✅]           5/8  (含 TASK-107 / TASK-108)'.encode('utf-8')
new_bar = 'Week 1:  [✅✅✅✅🔍🔍⬜✅]           5/8  (含 TASK-107 / TASK-108)'.encode('utf-8')
# 如果 105 已经 ✅,old_bar 第 5 位是 ✅ 不是 🔍,Codex 必须**实地 grep 看字面**再匹配
assert old_bar in data, (
    'Week 1 progress bar literal not found. '
    'Run: grep -n "Week 1" docs/03_TASK_INDEX.md | cat -A '
    'and paste output to PM. Architect will provide corrected literal.'
)
data = data.replace(old_bar, new_bar)

p.write_bytes(data)
```

**改完立即 `git diff docs/03_TASK_INDEX.md` 验证**。若 diff 显示几百行红绿,**立即 `git checkout -- docs/03_TASK_INDEX.md` 撤销,换方式 A 用编辑器手改**。

### 风险 2:openai SDK 版本兼容

`openai==1.54.0`(2024 年底版本)对 DeepSeek V4 API 的 `response_format` JSON mode + 基础 chat completions 是支持的。但 V4 特有的 thinking 字段(`reasoning_content`)在 1.54.0 可能未原生支持。

**本 Task 不消费 reasoning_content**,所以无影响。如果 Codex 实施时发现 chat.completions.create 因为 V4 新参数报错,**停手问 PM**,不要单方面升级 openai 版本。

### 风险 3:DeepSeek model 名实地核查

本文档默认 model 写 `"deepseek-v4-flash"`(架构师 2026-06-03 web_search 实地核查 DeepSeek 官方文档,V4 于 2026-04-24 发布)。

如果 Codex 实施时**今天**(实际实施日期)再核查 DeepSeek API 时发现:

- 官方 model 名变了(例如改成 `"deepseek-v5-flash"` / `"deepseek-v4.1-flash"`)→ **停手问 PM**
- `deepseek-chat` / `deepseek-reasoner` 旧名已经 404(2026-07-24 后) → 不影响本 Task(默认就不用旧名)

### 风险 4:`mocker.patch` 路径

mock OpenAI 客户端时,**必须** patch `adapters.llm.deepseek.OpenAI`(import 处),**不是** `openai.OpenAI`(定义处)。错 patch 路径是 Python mock 经典坑,导致 mock 不生效,测试在跑真实 API(还可能因无 key 失败)。

```python
# ✓ 正确:patch import 处
mocker.patch("adapters.llm.deepseek.OpenAI", return_value=mock_client)

# ✗ 错误:patch 定义处不会影响已 import 的引用
mocker.patch("openai.OpenAI", return_value=mock_client)
```

### 风险 5:`time.sleep` 拖慢单元测试

`_call_with_retry` 在重试时调 `time.sleep(0.5/1.0/2.0)`,如果不 mock,单元测试 `test_rate_limit_exhausted_raises` 会真实 sleep `0.5 + 1.0 + 2.0 = 3.5` 秒,违反"单元测试 ≤ 2 秒"性能预算。

**测试中必须 mock `time.sleep`**:

```python
def test_rate_limit_exhausted_raises(mocker, mock_openai_client, ...):
    _, mock_create = mock_openai_client
    # mock all sleep calls inside the retry loop
    mocker.patch("adapters.llm.deepseek.time.sleep")
    # ... rest of test
```

`time.sleep` 在 `adapters.llm.deepseek` 模块 import,所以 patch 路径是 `adapters.llm.deepseek.time.sleep`。

### 风险 6:不要日志记录 messages 原文 / API key

宪法 § 9 / 04 § 9 硬约束:**日志只记录元数据**(model / token 数 / 延迟 / 错误类型),**不**记录:

- messages 原文(可能含学生工程内容 / 个人信息)
- response text 原文(同上)
- API key(部分 / 完整都不行)
- 报错堆栈中的 request body(loguru 默认不会记 request,但 traceback 中可能含 — 谨慎)

**单元测试 `test_no_message_content_logged` 必须断言这点**(用 `caplog` 或 loguru sink fixture)。

### 风险 7:不要在 Provider 内 import AppSettings

`adapters/llm/deepseek.py` **不能**:

```python
from app.config import AppSettings  # ❌ 违反分层依赖
```

分层依赖原则(02 § 1 全景图 + 宪法 § 7):adapter 不知道 app 装配层存在。如果你强烈认为需要,**停手问 PM**。

### 风险 8:`pyproject.toml` mypy target 不动

`pyproject.toml` 的 mypy target 当前可能是 `core/ adapters/ features/`(覆盖整 adapters 目录)。本 Task 不需要修改 mypy 配置。

如果 Codex 跑 `make type-check` 报错说 `adapters/llm/` 类型问题,**先修代码**,**不要**修 mypy target 排除本 Task 的代码。

### 风险 9:Codex 看见冲突就停手

本 Task 文档与 `docs/01/02/04/05` / 决策日志 / 03 索引 / TASK-001-105 / 108 已合并产物 的任何冲突,**停手问 PM**,不要默默偏离。

常见冲突场景:

- `adapters/llm/__init__.py` 已有 `DeepSeekTextProvider` 同名导出 → **不要**覆盖
- `adapters/llm/` 目录不存在(假设 TASK-001 未建) → **不要**自己 mkdir,告诉 PM
- `requirements.txt` 现状与本文档"输入"小节描述不符(例如已有 `openai` 旧版本) → 告诉 PM
- `pyproject.toml` 不含 `[tool.pytest.ini_options] markers = ["integration: ..."]` 注册 → 告诉 PM,不要自己加 marker 注册
- DeepSeek API 在你实施当天已变更 model 名 / 退役 v4-flash → 告诉 PM

### 风险 10:`@pytest.mark.integration` marker 注册

pytest 在 6.0+ 对未注册的 marker 会发警告(若 `--strict-markers` 还会报错)。本 Task 用 `@pytest.mark.integration`,需要在 `pyproject.toml` 注册:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: real API calls, skipped by default in CI",
    "slow: takes longer than 1s, skipped by default in CI",
]
```

**如果 `pyproject.toml` 已注册 `integration` marker**:不动。

**如果未注册**:

- 选项 A:Codex 单方面注册 → **违反 TASK 范围**(动 pyproject.toml),**禁止**
- 选项 B:暂用 `@pytest.mark.skip(reason="real API, run manually")` 代替 → 简单但不规范
- 选项 C:**停手问 PM**,PM 走单独 chore PR 注册 marker

**推荐选项 C**(对齐 task-108 模式)。但若 PM 决定加进本 Task 范围,Codex 可顺手加(类比 TASK-108 加 requirements-dev.txt 模式)。**默认走 C**。

### 风险 11:静态扫描误报

任何 `grep` / `find` 检查必须按决策 05 加 `--exclude-dir=".venv" --exclude-dir=".git"`。

### 风险 12:本地 ruff 版本与 CI 锁定可能漂移(决策 09 反例 11 同类)

CI 跑的 ruff 来自 `requirements-dev.txt` 锁定的 `ruff==0.7.0`(04 § 6 模板)。**Codex 本地若使用系统全局 ruff**(可能是更老版本如 0.5.x / 0.6.x,或更新版本 0.8.x+),`ruff format` 的行为可能与 CI 不一致 —— 尤其 implicit string concatenation 合并这一条规则在不同 ruff 版本启用程度不同。

**TASK-105 实施时已实战触发**:Codex 本地完工报告 `82 files already formatted`(本地全过),CI 却抓到 1 file would be reformatted(`adapters/parser/_dep_patterns.py` 的 `RE_SIM_CALL` 两行 implicit concat 想合并)。原因是 Codex 本地跑的 ruff 不是 venv 锁定的 0.7.0,或 `.ruff_cache` 命中跳过实际检查。

**规避**(本 Task 实施时严格遵守):

1. **完工前自检命令必须用 `python -m ruff` 而不是裸 `ruff`** —— 走 venv 里 site-packages 里固定版本,而不是系统全局 PATH 上随便哪个 ruff
2. **若怀疑 cache 命中**,先 `rm -rf .ruff_cache` 再跑 `python -m ruff format --check .`
3. **完工三件套里 `ruff format --check .` 输出必须用 `python -m ruff format --check .` 的输出贴回**(详见 § 11.5)
4. 如果你的本地环境是 venv 已激活 + `pip install -r requirements-dev.txt` 跑过的,`python -m ruff` 和 `ruff` 应当输出一致。但**保守起见统一用前者**

漏踩这条 → CI 红 → PM 需要再来一轮 round-trip,延误 15-30 分钟。

---

## 估时

预估 **3-5 小时**:

- 阅读本 Task 文档 + 02 § 4.3 / 04 § 5 / task-101 § 7 关键段:0.5 小时
- 建 `_deepseek_errors.py`(直接抄 § 7.3):0.3 小时
- 建 `deepseek.py` 主体(直接抄 § 7.1):0.7 小时
- 建测试 conftest.py + fake fixtures(直接抄 § 7.4):0.3 小时
- 写 16 个单元测试:1-1.5 小时
- 写 2 个集成测试(标记 skip):0.2 小时
- 更新 README / __init__.py:0.2 小时
- 改 03 索引(字节级)+ commit 拆分 + push:0.3 小时
- `make check` + 三件套 + PR 描述:0.3 小时

---

## 给 Codex 的提示

### 1. 推荐实现顺序

1. 切分支 `task/TASK-106-deepseek-text-provider`
2. `cat adapters/llm/__init__.py adapters/llm/README.md requirements.txt requirements-dev.txt pyproject.toml` 看现状
3. 追加 `openai==1.54.0` 到 `requirements.txt`
4. 核查并追加 `pytest-mock==3.14.0` 到 `requirements-dev.txt`(若不在)
5. `pip install -r requirements-dev.txt` 装新依赖
6. 建 `_deepseek_errors.py`(直接抄 § 7.3)
7. 建 `deepseek.py` 主体(直接抄 § 7.1)
8. 建 `tests/adapters/llm/__init__.py` 空文件 + `conftest.py`(直接抄 § 7.4)
9. 建 `test_deepseek_unit.py` 16 个 case(逐条对照 § 5 范围清单)
10. `pytest tests/adapters/llm/test_deepseek_unit.py -v` 跑过
11. 建 `test_deepseek_integration.py`(直接抄 § 7.5)
12. `pytest tests/adapters/llm/test_deepseek_integration.py -v` 看到 skipped
13. 追加 `DeepSeekTextProvider` 导出到 `__init__.py` + 重写 README
14. `make check` + `python -m ruff format --check .` 全检
15. 改 03 索引(决策 08 字节级)
16. commit 拆分 + push + 三件套 + 提 PR

### 2. Commit 拆分建议(Conventional Commits)

```
chore(deps): add openai 1.54.0 (project second runtime dep)
chore(deps): add pytest-mock 3.14.0 to dev deps (if not present)
feat(llm): add deepseek error translation table
feat(llm): add DeepSeek TextProvider with retry and JSON mode
test(llm): add deepseek unit tests (16 cases) + integration template
docs(llm): rewrite adapters/llm/README with usage example
docs: mark TASK-106 as in-review in task index
```

不要单个超大 commit。

### 3. 改 `docs/03_TASK_INDEX.md` 必须按决策 08

**禁用** `read_text` / `write_text` / `sed -i`,详见风险 1 的脚本骨架。**进度条字面量必须实地 grep 后再匹配**(105 / 104 状态可能在你实施时已经 ✅,字面不同),否则 assert 失败。

### 4. CI 实际跑的命令(决策 09 反例 8)

CI workflow 跑:`ruff check .` / `ruff format --check .` / `mypy core/ adapters/ features/` / `pytest -v --tb=short`。

完工前**手动**:

```bash
python -m ruff format --check .
```

挂了就 `python -m ruff format .` 修复并 commit。

### 5. 完工报告必须含 git 三件套(决策 08)+ 工具版本对齐(决策 09 反例 11)

完工时给 PM:

- 修改的文件清单
- 本地 `make check` 输出
- **本地 `python -m ruff format --check .` 完整输出**(必须用 `python -m ruff`,**不**用裸 `ruff`,避免本地系统全局 ruff 与 venv 锁定的 0.7.0 漂移 — 详见风险 12)
- **`git status` / `git log --oneline main..HEAD` / `git push` 完整输出**
- 验收清单 1-13 项逐条勾选 + 说明
- PR 标题:`TASK-106: DeepSeek TextProvider 实现`
- PR 正文(按 `docs/04_ENGINEERING_STANDARDS.md` 第 3 节模板;**变更摘要必须明示**"项目第二个 runtime 依赖")

**不附三件套 = 没完工**,PM 退回让 Codex 补。

### 6. PR 创建流程

Codex 没有 `gh` 登录态,**不要** `gh pr create`。push 完分支后给 PM:PR 标题 + PR 正文,PM 在 GitHub 网页手动创建 PR。

### 7. 遇冲突就停手

本 Task 文档与已合并产物的任何冲突,**停手问 PM**,不要默默偏离。详见风险 9 / 风险 10 的常见冲突场景。

### 8. 决策 09 提醒

虽然决策 09 是**架构师**的纪律(写文档前实地核查,不凭印象),但 Codex 实施时遇到"task 文档与现状不一致"的场景也可以参考其反例集。架构师可能凭印象的维度:**字面量空格 / 字段总数 / CI 行为 / 仓库现状**。抓住就停手抛冲突给 PM。

---

**版本**:Task 文档 v1.1
**作者**:Claude(架构师,第七任)
**日期**:2026-06-03
**修订纪录**:
- v1.0 → v1.1(2026-06-03):TASK-105 实施时 CI 抓到 ruff format 本地与 CI 漂移(Codex 本地 ruff 不是 venv 锁定的 0.7.0),增量修订:6 处 `ruff format ...` 改为 `python -m ruff format ...`(命令字面);新增 § 9 风险 12(toolchain 版本漂移);§ 11.5 完工三件套加一条要求贴 `python -m ruff format --check .` 输出。Line 1045 描述 CI yml 字面**不改**(决策 09 反例 8 精神)。这条事故来源待入决策 09 反例集第 11 行,延后到下次 docs 维护 PR 批量入仓。
**关联宪法版本**:v2.1(冻结)
**关联决策**:`docs/decisions/20260601-04-*.md` / `20260601-05-*.md` / `20260601-06-*.md` / `20260601-07-*.md` / `20260602-08-*.md` / `20260603-09-*.md`
**关联 Task**:依赖 TASK-101(契约源)/ TASK-108(配置层);下游 TASK-203 / TASK-205 / TASK-305 / TASK-307
**是否走 GPT 二审**:**否**(本 Task 不在宪法 § 5 核心 Task 二审清单)
**实地核查日期**:2026-06-03(架构师 web_search 核查 DeepSeek V4 model 命名 + 定价 + 退役计划)
