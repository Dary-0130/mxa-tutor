# TASK-301: sentence-transformers 嵌入适配器(Week 3 起步)

## 状态

🔲 v0.2(R1 conditional pass / 3 P0 + 5 P1 + 4 P2 全采纳 / 不升 R2 / 可进 Codex)

---

## 审批记录

| 轮次 | 时间 | 结论 | 关键修订点 |
|:---:|:---|:---|:---|
| R1 | 2026-06-05 | **条件通过,不升 R2 / 直接进 Codex** | 3 P0 + 5 P1 + 4 P2 全采纳,转 v0.2 |

### R1 3 P0 必改(全采纳)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P0-1 | `@pytest.mark.integration` 不等于默认跳过;pyproject.toml addopts 不存在(实地核查),CI 跑 `pytest -v --tb=short` 会触发真实 100MB 模型下载 | § 9.8 integration test 用 `RUN_EMBEDDING_INTEGRATION=1` skipif env + § 11.2 #5/#6 验收命令改 + Stage 0 加 pyproject.toml 核查 + pyproject.toml 进修改清单加 markers 注册(P2-3) |
| P0-2 | 03 索引 chore 漏 TASK-301 自身 🔲→🔍 + Week 3 进度条 + line 349 stale("下一步: TASK-203") | § 9.5.2 字节级 Python 扩成 7 处修订(TASK-207 ✅ + TASK-301 🔲→🔍 + Week 2 7/7 + Week 3 [🔍⬜⬜⬜⬜⬜⬜] 0/7 + 18/32 + 日期 + line 349 改) |
| P0-3 | 04 § 10 patch 30 行整块 anchor 字符级不稳 + 四反引号 typo(实际围栏是 3 反引号) | § 9.5.3 改 fence 边界替换:`data.index(b"```python\n# api/middleware...")` 找开头 + `data.index(b"```\n", start)` 找结尾 |
| P0-4 | D8 改 `docs/04_ENGINEERING_STANDARDS.md` 需决策 07 例外授权显式声明 | D8 决策段加"PM 一次性显式例外授权"段落 + 边界明示 |

### R1 5 P1 必改(全采纳)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P1-1 | `requirements.txt` 追加 patch 无尾换行检测,若现有文件末尾无 `\n` 会拼成 `pyyaml==x.y.zsentence-transformers==...` | § 9.4 加 `if not data.endswith(b"\n"): data += b"\n"` 兜底 |
| P1-2 | `.env.example` patch 用 `b"\n"` 字面只匹配 LF,违反决策 08 跨平台兜底 | § 9.3 改 newline-aware:`newline = b"\r\n" if b"\r\n" in data else b"\n"`;03 索引 / 04 § 10 / 决策 09 patch 同源(但 03/04/决策 文档 main HEAD 已是 LF,本 Task 仍走 newline-aware 兜底) |
| P1-3 | `pyproject.toml` 漏在修改文件清单(mypy 大概率 fail `sentence_transformers` missing stubs);Stage 0 实地核查后**确认不存在** override,**必须加**不是条件 | § 6 修改清单加 `pyproject.toml` + § 9.11 新增段:加 `[[tool.mypy.overrides]] module = "sentence_transformers.*"` + `ignore_missing_imports = true` |
| P1-4 | `MockEmbeddingProvider` 默认全零向量会让 TASK-302/304 余弦相似度遇零范数 / div-by-zero | § 9.6 改 `base = [0.0] * dimension; base[0] = 1.0;` 非零 |
| P1-5 | "必须做" 写 integration `dimension > 0`,§ 11.1 写 `dimension == 512`,二者不一致 | § 11.1 + § 9.8 锁定 `== 512` 并加契约测试理由:"runtime 不写死维度;integration 钉死默认模型 `BAAI/bge-small-zh-v1.5` 契约维度 512,模型升级时此测试提醒同步" |

### R1 4 P2 建议(全采纳)

| # | 建议 | v0.2 修订位置 |
|:-:|---|---|
| P2-1 | `model_name` 空校验改 `.strip()` 防全空格 | § 9.1 adapter `if not model_name.strip():` + § 9.7 加 `test_init_whitespace_model_name_raises` 单测 |
| P2-2 | `get_sentence_embedding_dimension()` 返回 `None` 防御(类型签名允许 None) | § 9.1 加 `if dimension is None: raise ValueError(...)` |
| P2-3 | pytest markers 未注册;Stage 0 实地核查 pyproject.toml 后**确认不存在 markers 注册**,顺手加防 `--strict-markers` 切换 | § 9.11 pyproject.toml 修改加 `[tool.pytest.ini_options] markers = ["integration: ...", "slow: ..."]` |
| P2-4 | grep 0 命中预期命令在 `set -e` 环境会中断 | § 11.2 #8 / #11 后半 / #12 加 `\|\| true`(本 Task 是手跑,low priority,顺手) |

### v0.2 新增治理 chore:反例 27 入仓决策 09(D8 升级)

**反例 27 触发现场**(v0.1 → R1 之间):架构师在 TASK-301 v0.1 § 11.2 / D7 中假设 `@pytest.mark.integration` 在 CI 默认 `pytest -v` 命令下自动跳过,**未实地核查 `pyproject.toml`** 是否有 `addopts = "-m 'not integration'"` 或 `addopts = "-m 'not integration and not slow'"`。R1 P0-1 抓住,后续 PM 实地 `cat pyproject.toml` 确认 addopts 不存在 + markers 未注册。

教训接续反例 19(框架默认行为假设同源):pytest mark 行为 ≠ "贴标签即跳过",必须在 pyproject.toml `addopts` 或 conftest 钩子或 `skipif` env 显式声明;架构师写"默认跳过"前必须 `cat pyproject.toml` 看 `addopts` 实际值。

**第十七任 KPI 升级**(决策 09 末尾追加,叠在反例 26 KPI 之上):
- 任何文档引用"pytest mark X 默认跳过/skipif/parametrize/asyncio_mode/strict-markers"等行为前,必须 `cat pyproject.toml` + 必要时 `cat tests/conftest.py` 实地核查 `[tool.pytest.ini_options]` 段
- 任何文档引用"mypy 会/不会检查 X 模块"前,必须 `cat pyproject.toml` 实地核查 `[tool.mypy]` + `[[tool.mypy.overrides]]` 全部条目
- 接续反例 19(Starlette async 默认行为)/ 反例 26(scripts/* hygiene 默认行为):**所有"工具默认行为"陈述前必须 cat 工具配置文件实地核查**

D8 搭车 chore 由 v0.1 的 3 项扩成 v0.2 的 **4 项**(反例 26 + **反例 27** + 03 索引 + 04 § 10)。

### 升级触发条件提醒(R1 重申)

宪法 § 5 二审清单本 Task 不涉及。**若实施期出现"改 schema / 推翻 D2 范围 / lifespan 装配 / 引入新依赖外 deps / EmbeddingError 异常类 / GPU 默认配置 / 推翻 P0-1 skipif env 方案 / 推翻 P0-3 fence 边界替换"等任一,必须自动升 R2**。

---

## 审批级别说明(反例 18 自检)

| 维度 | 评分 | 理由 |
|---|---|---|
| 决策密度 | **低**:D1-D8 | 一审 1 轮 + 范围窄 + adapter 实现 + 加载时机 + AppSettings + deps + 测试 mock + 搭车 chore — 每个决策都有 DeepSeek 类比作 anchor |
| 下游扩散面 | **3 下游消费者** | TASK-302 / 303 / 304(全部 Week 3 未启动);**本 Task 不阻塞任何已合并 Task** |
| 用户可见性 | **无**:零 API 变更,零行为变化 | 不动 lifespan / dependencies / routes;adapter 是工具层 |
| 异步 / LLM 首次定型 | **无**:adapter 同步签名(类比 DeepSeek),不引入新 async 模式 | embed() / dimension() 接口已落地,本 Task 实现层 |
| 隐私 / 安全 | **无**:零新增数据流,零新增日志风险 | embedding 是本地推理无网络;logger.info 只含 model_name / device / dimension 元数据 |

→ **一审 1 轮**(沿用 TASK-106 / 107 / 207 模式)。R1 已 conditional pass。

---

## 上下文

### mxa-tutor 项目快速建立 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。学生上传 .zip 工程包(.m / .slx / .mat),后端做 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。

当前 Week 3 起步(**18/32 Task 完成**,Week 2 已 7/7 收官,TASK-207 已 merge 进 main commit `b5b2271`)。Week 3 进度 0/7,**本 Task 是 Week 3 第一棒(1/7)**,Week 3 后续 TASK-302/303/304 全部依赖本 Task 落地的 EmbeddingProvider 实现层。

**注**:此处"18/32 / Week 3 0/7"是事实状态(基于 main 实际 merge 历史 commit `b5b2271`)。`docs/03_TASK_INDEX.md` 当前仍停留在"TASK-207 🔍 / 17/32 / Week 2 6/7"补账中间态(详见 § Stage 0 #13),本 Task 搭车 chore 做索引补账 7 处(P0-2 升级,见 § 9.5.2)。

### 数据流位置(02 § 2)

```
[Parser]  SlxModel / MFile / MatMetadata / FileInfo / file_dependencies
   ↓  无 LLM,纯结构化(TASK-107)
[ProjectGraph]  nodes / edges / entry_points / execution_flow / unresolved_symbols
   ↓  调 LLM 基于 ProjectGraph 生成
[ProjectOverview / TeachingUnit / Chat]  教学化输出,带 SourceRef 证据
   ↓  Week 3 向量化(TASK-301 ★ + 302 + 303 + 304)
[Vector RAG]  Embedding(SentenceTransformer)→ SQLite BLOB → 余弦检索 → 强证据问答
```

本 Task 在数据流的位置:**Embedding 层实现**。`core/interfaces/embedder.py` 抽象签名已在项目骨架阶段落地(`embed(list[str]) -> list[list[float]]` + `dimension() -> int`,纯同步)。本 Task **不消费** embed(等 TASK-302/304),**只**把 `sentence-transformers` 库接进来作为 `EmbeddingProvider` 实现。

### 类比 anchor:TASK-106 DeepSeek TextProvider

本 Task 实现模式**完全类比** `adapters/llm/deepseek.py`(commit `b1eb647`,TASK-106 产物,已在 main HEAD 稳定):
- `__init__` 接收所有运行时值,**不读 AppSettings**(决策 06 模块封装)
- 模块级 `DEFAULT_MODEL_NAME / DEFAULT_*` 常量
- 实例化时立即建立资源(DeepSeek: `self._client = OpenAI(...)` lightweight;SentenceTransformer: `self._model = SentenceTransformer(...)` heavyweight ~100MB + ~2s)
- `__all__ = ["..."]` 显式导出
- ValueError 校验签名(unsupported model / invalid arg)
- adapter 同步签名,async 调用方负责 `asyncio.to_thread` 桥接(决策 11)

唯一差异:DeepSeek 每次 `chat()` 调网络;SentenceTransformer **只**在 `__init__` 时**可能**调网络(首次下载),`embed()` 纯本地推理。这意味着 sentence-transformers adapter **加载昂贵但调用便宜**,与 DeepSeek 镜像反转。

---

## 输入(前置依赖)

### 已合并 Task

✅ TASK-001 / 002 / 101 / 104 / 106(`b1eb647`,DeepSeek adapter 类比 anchor)/ 107 / 108 / 201(`fa7a4b0`,lifespan + dependencies 形态)/ 202 / 203(`871c8e2`)/ 204 / 205 / 206(`746a76d`)/ 207(`b5b2271`,main HEAD)。

### 上游关键契约(实地核查 main HEAD,本 Task 不动)

**`core/interfaces/embedder.py`**(已在仓库,本 Task 不动签名):

```python
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """嵌入模型的抽象接口(具体实现见 adapters/embedding/)。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入,返回每个文本的向量。"""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度。"""
        ...
```

**`02_ARCHITECTURE_OVERVIEW.md` § 6 决策 2**(钉死):
- 模型 = `BAAI/bge-small-zh-v1.5`(中文,~100MB,效果好,免费)
- 实现 = Python 进程内加载,启动时一次性
- 何时升级 = 单工程 chunk 数 > 5000 或用户量 > 1000(超出 MCS 阶段范围)

**`adapters/llm/deepseek.py`**(类比 anchor,本 Task 不动):见 § 上下文 § 类比 anchor 段。

**`app/config.py` AppSettings 当前字段分组**(实地核查 main HEAD):

```python
# LLM
deepseek_api_key: str
deepseek_base_url: str = "https://api.deepseek.com"

# Storage / Quota / File limits / Logging  ...
```

本 Task 在 `# LLM` 段后**新增** `# Embedding(TASK-301 新增)` 段。

**`requirements.txt`**(实地核查 main HEAD)8 条 deps:`pydantic-settings / loguru / aiosqlite / openai / fastapi / uvicorn / python-multipart / pyyaml`。**sentence-transformers 不在**;04 § 6 模板写的 `sentence-transformers==3.3.0` 是 reference,本 Task 走 04 § 6 流程加入。

**`pyproject.toml`**(实地核查 main HEAD,**R1 P0-1 + P1-3 + P2-3 触发**):
- `[tool.pytest.ini_options]` 仅含 `testpaths = ["tests"]` + `asyncio_mode = "auto"`;**无 `addopts`**(P0-1 用 skipif env 方案);**无 markers 注册**(P2-3 顺手加)
- `[tool.mypy]` 仅含 `python_version / strict=false / warn_unused_ignores / disallow_untyped_defs=false`;**无 sentence_transformers override**(P1-3 必须加)
- `[tool.ruff]` line-length=100,target-version=py311
- `requires-python = ">=3.11"`

**`.github/workflows/ci.yml` 5 step**(实地核查 main HEAD):`ruff check / ruff format --check / mypy / pytest / hygiene`。`Makefile check` target 4 项 = `lint(含 format)+ type-check + test + hygiene` ≡ CI 全 step(反例 26 KPI 升级 § 11.2 #4 用 `make check` 等价 CI 全管道)。

### 必读文档

- `docs/01_PROJECT_CONSTITUTION.md` § 7(异步与并发,决策 11 关联)
- `docs/02_ARCHITECTURE_OVERVIEW.md` § 4.4(EmbeddingProvider 接口)+ § 6 决策 2(模型 + 实现策略)
- `docs/04_ENGINEERING_STANDARDS.md` § 4(代码规范)+ § 5(测试规范)+ § 6(依赖管理)+ § 9(日志)+ § 10(异常,本 Task D8 搭车修订 dict 字面 → tuple 字面)
- `docs/decisions/20260601-04`(理解不抽顶层 feature,本 Task 无关)
- `docs/decisions/20260601-05`(静态扫描排除 .venv/.git)
- `docs/decisions/20260601-06`(Codex 可读仓库,设计文档引用而非内联)
- `docs/decisions/20260601-07`(03 索引更新边界,本 Task 搭车 chore + **04 修订需 PM 例外授权**,见 D8)
- `docs/decisions/20260602-08`(PM 验 git + 字节级 Python 改 docs)
- `docs/decisions/20260603-09`(架构师必须实地核查,反例 26 + 反例 27 本 Task D8 入仓)
- `docs/decisions/20260604-11`(async + to_thread / logger.error metadata-only)
- 反例 21-25(已入仓)+ **反例 26 + 反例 27 候选(本 Task D8 入仓)**

---

## 输出(交付物)

### 新增文件(7 个)

| 文件 | 内容 | 预计行数 |
|---|---|---|
| `adapters/embedding/__init__.py` | `__all__` + 导出 `SentenceTransformerEmbedder` | 4 |
| `adapters/embedding/sentence_transformer.py` | `SentenceTransformerEmbedder(EmbeddingProvider)` 主实现 | 80-120 |
| `adapters/embedding/README.md` | 模块说明 | 30-50 |
| `tests/adapters/embedding/__init__.py` | 空文件(pytest namespace) | 0 |
| `tests/adapters/embedding/conftest.py` | `MockEmbeddingProvider`(P1-4 非零向量)+ fixture(给 TASK-302/304 复用)| 40-60 |
| `tests/adapters/embedding/test_sentence_transformer_unit.py` | mock `SentenceTransformer` 类的 unit test(含 P2-1 strip 单测)| 90-130 |
| `tests/adapters/embedding/test_sentence_transformer_integration.py` | **P0-1**:用 `RUN_EMBEDDING_INTEGRATION=1` skipif env + `@pytest.mark.integration / slow`,默认跳过 | 40-60 |

### 修改文件(5 个 + 4 个搭车 chore)

| 文件 | 修改 | 工艺 |
|---|---|---|
| `app/config.py` | 新增 `# Embedding(TASK-301 新增)` 段 3 字段 | str_replace |
| `.env.example` | 新增 `# Embedding(TASK-301 新增)` 段 3 字段(**P1-2**:newline-aware)| 字节级 Python |
| `requirements.txt` | 末尾追加 `sentence-transformers==3.3.0`(**P1-1**:尾换行检测)| 字节级 Python |
| `pyproject.toml` | **P1-3 + P2-3 + P0-1 新增**:加 `[[tool.mypy.overrides]] module = "sentence_transformers.*"` + `[tool.pytest.ini_options] markers = [...]` 注册 | 字节级 Python |
| `docs/04_ENGINEERING_STANDARDS.md` | **搭车 chore + D8 PM 例外授权**:§ 10 line 552-566 修订 `ERROR_MAP` dict 字面 → `error_handlers: tuple[...]`(**P0-3** fence 边界替换 + **P0-4** 例外授权明示)| 字节级 Python |
| `docs/decisions/20260603-09-architect-must-verify-not-assume.md` | **搭车 chore**:末尾追加 **反例 26 + 反例 27**(D8 升级)+ 第十六任 + 第十七任 KPI 升级 | 字节级 Python |
| `docs/03_TASK_INDEX.md` | **搭车 chore**:**7 行字面修订**(P0-2 升级,见 § 9.5.2) | 字节级 Python |

### 不动文件(明示)

| 文件 | 不动理由 |
|---|---|
| `core/interfaces/embedder.py` | 抽象签名已就位,本 Task 实现层 |
| `api/main.py`(lifespan)| D2 范围决定 — 留 TASK-302/304 装配 |
| `api/dependencies.py` | 同上 |
| `core/domain/exceptions.py` | D5 决定 — 本 Task 不引入 EmbeddingError(超范围)|
| `api/middleware/error_handler.py` | 不消费 embed,无新 handler |
| `tests/conftest.py` | 当前 placeholder,本 Task 不动;`MockEmbeddingProvider` 放在 `tests/adapters/embedding/conftest.py` 局部(类比 `tests/adapters/llm/conftest.py` 已有局部模式)|

---

## 范围

### 必须做

- [ ] 实现 `SentenceTransformerEmbedder(EmbeddingProvider)`,签名:`__init__(model_name, device, normalize)` + `embed(texts) -> list[list[float]]` + `dimension() -> int`
- [ ] 模型在 `__init__` 时同步加载(类比 DeepSeek `__init__` 内 `self._client = OpenAI(...)`,但 heavyweight)
- [ ] 加载日志走 `logger.info("Loading sentence-transformer model: {} on device={}", model_name, device)` + 加载完毕日志 `logger.info("Model loaded: dimension={}", self._dimension)`(元数据,无用户内容)
- [ ] 维度通过 `self._model.get_sentence_embedding_dimension()` 动态获取,**不写死常量**(决策 09 纪律 4);**P2-2**:None 防御
- [ ] **P2-1**:`model_name.strip()` 校验,空字符串 / 全空格抛 ValueError
- [ ] AppSettings 加 3 字段:`embedding_model_name / embedding_device / embedding_normalize`(默认值 `BAAI/bge-small-zh-v1.5` / `cpu` / `True`)
- [ ] `.env.example` 同步 3 个 ENV 变量(`EMBEDDING_MODEL_NAME` / `EMBEDDING_DEVICE` / `EMBEDDING_NORMALIZE`,**P1-2 newline-aware**)
- [ ] `requirements.txt` 加 `sentence-transformers==3.3.0`(**P1-1 尾换行兜底**)
- [ ] **P1-3**:`pyproject.toml` 加 `[[tool.mypy.overrides]] module = "sentence_transformers.*"` + `ignore_missing_imports = true`
- [ ] **P2-3**:`pyproject.toml` 加 `[tool.pytest.ini_options].markers = ["integration: ...", "slow: ..."]` 注册
- [ ] `tests/adapters/embedding/conftest.py` 实现 `MockEmbeddingProvider`(**P1-4 非零向量**:`base[0]=1.0`)+ `@pytest.fixture mock_embedder`,供 TASK-302/304 复用
- [ ] unit test 通过 `mocker.patch("adapters.embedding.sentence_transformer.SentenceTransformer")` mock 模型加载,**不真实下载**;覆盖:正常初始化 / 默认值 / embed 返回正确 shape / dimension 调用 / normalize 行为 / **P2-1 strip 单测**
- [ ] **P0-1**:integration test 用 `RUN_EMBEDDING_INTEGRATION=1` env var skipif,**默认跳过**;**P1-5**:`dimension == 512` 钉死契约(理由见 § 9.8 docstring)
- [ ] **make check 全管道 0 errors**(反例 26 KPI 第一次硬执行)
- [ ] 搭车 chore 4 项(详见 § 9.5)

### 不做(明确排除)

- ❌ **不**改 `core/interfaces/embedder.py` 抽象签名(已稳定)
- ❌ **不**在 `api/main.py` lifespan 装配 `app.state.embedder`(留 TASK-302/304;D2 范围决定)
- ❌ **不**在 `api/dependencies.py` 加 `get_embedder()`(同上)
- ❌ **不**引入 `EmbeddingModelLoadError(MxaError)` 新异常类(D5;lifespan 装配时引入)
- ❌ **不**加 ERROR_MAP handler(D5;无 HTTP 消费场景)
- ❌ **不**支持 GPU `device="cuda"` 在 CI 测试(默认 cpu;dev 本地用户可改 .env 覆盖)
- ❌ **不**暴露 cache_dir 配置(走 HuggingFace 默认 `~/.cache/huggingface/`;离线开发通过 `HF_HUB_OFFLINE=1` ENV 变量)
- ❌ **不**在本 Task 跑评测脚本(TASK-306 范围)
- ❌ **不**实现 retry 逻辑(本地推理无网络瞬态故障)
- ❌ **不**改 pyproject.toml `addopts`(P0-1 用 skipif env 方案,本 Task 范围;不改全局 addopts 避免扩散)

---

## 接口契约

### 抽象签名(已就位,本 Task 不动)

见 § 输入 § 上游关键契约 `core/interfaces/embedder.py` 摘录。

### 本 Task 实现签名

```python
# adapters/embedding/sentence_transformer.py

DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
DEFAULT_DEVICE = "cpu"
DEFAULT_NORMALIZE = True


class SentenceTransformerEmbedder(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str = DEFAULT_DEVICE,
        normalize: bool = DEFAULT_NORMALIZE,
    ) -> None:
        """Initialize and load the sentence-transformer model.

        Args:
            model_name: HuggingFace model identifier (must be non-empty after strip).
            device: PyTorch device ('cpu' / 'cuda' / 'cuda:0' etc.).
            normalize: Whether to L2-normalize embeddings (bge models recommend True).

        Raises:
            ValueError: If model_name strips to empty, or model dimension is unavailable.
        """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch encode texts to vectors. Returns list of dimension-D float lists."""

    def dimension(self) -> int:
        """Return embedding dimension. bge-small-zh-v1.5 = 512."""
```

### AppSettings 新增字段签名

```python
# app/config.py — 在 # LLM 段后,# Storage 段前

# Embedding(TASK-301 新增)
embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
embedding_device: str = "cpu"
embedding_normalize: bool = True
```

### MockEmbeddingProvider 签名(给下游测试用,**P1-4 非零向量**)

```python
# tests/adapters/embedding/conftest.py

class MockEmbeddingProvider(EmbeddingProvider):
    """测试用 mock,返回固定非零向量(避免下游余弦相似度除零)。不加载真实模型。"""

    def __init__(self, dimension: int = 512) -> None:
        self._dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        # P1-4: 非零向量,base[0]=1.0 其余 0.0;避免下游余弦距离 div-by-zero
        base = [0.0] * self._dimension
        base[0] = 1.0
        return [base.copy() for _ in texts]

    def dimension(self) -> int:
        return self._dimension


@pytest.fixture
def mock_embedder() -> MockEmbeddingProvider:
    """fixture 实例(dimension=512,匹配 bge-small-zh-v1.5 模型卡)。"""
    return MockEmbeddingProvider(dimension=512)
```

---

## 实施细节

### 9.1 `adapters/embedding/sentence_transformer.py` 完整骨架(P2-1 + P2-2)

```python
"""sentence-transformers EmbeddingProvider implementation."""

from __future__ import annotations

from loguru import logger
from sentence_transformers import SentenceTransformer

from core.interfaces.embedder import EmbeddingProvider

__all__ = ["SentenceTransformerEmbedder"]


DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
DEFAULT_DEVICE = "cpu"
DEFAULT_NORMALIZE = True


class SentenceTransformerEmbedder(EmbeddingProvider):
    """Synchronous sentence-transformers adapter.

    The adapter loads the model in ``__init__`` (heavyweight, ~100MB download +
    ~2s load time on first run). The application layer is responsible for
    bridging this synchronous load into an async context using
    ``asyncio.to_thread`` per 决策 11.

    The adapter receives all runtime values through its constructor. It does
    not import or read ``app.config.AppSettings`` (per 决策 06).
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str = DEFAULT_DEVICE,
        normalize: bool = DEFAULT_NORMALIZE,
    ) -> None:
        """Initialize the embedder and load the model.

        Args:
            model_name: HuggingFace model identifier.
            device: PyTorch device string (e.g. "cpu", "cuda").
            normalize: If True, L2-normalize the output embeddings. bge models
                recommend True so that cosine similarity == dot product.

        Raises:
            ValueError: If model_name strips to empty, or the loaded model
                returns None for ``get_sentence_embedding_dimension()``.
        """
        # P2-1: 全空格也算空
        if not model_name.strip():
            raise ValueError("model_name must be non-empty (after strip)")

        logger.info(
            "Loading sentence-transformer model: model_name={} device={}",
            model_name,
            device,
        )
        self._model = SentenceTransformer(model_name, device=device)
        self._normalize = normalize

        # P2-2: get_sentence_embedding_dimension() 类型签名允许 None,显式防御
        dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError(
                f"model dimension is unavailable for model_name={model_name!r}"
            )
        self._dimension: int = dimension

        logger.info(
            "Model loaded: model_name={} dimension={} normalize={}",
            model_name,
            self._dimension,
            normalize,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch encode texts to embedding vectors.

        Args:
            texts: List of input strings.

        Returns:
            List of embedding vectors. Each vector has length ``self.dimension()``.
            For an empty input list, returns an empty list.
        """
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension
```

**关键不变量**:
- `__init__` 内立即加载模型(同步),类比 DeepSeek `__init__` 内 `OpenAI(...)`,但 heavyweight
- 不写死 dimension 常量(决策 09 纪律 4)— 通过 `get_sentence_embedding_dimension()` 动态获取
- **P2-1**:`model_name.strip()` 空校验 + 错误消息明示 "after strip"
- **P2-2**:`get_sentence_embedding_dimension()` None 防御 + 显式 ValueError(类型签名允许 None,运行时若 None 会让 `self._dimension: int = None` 类型不一致)
- `embed([])` 返回 `[]`(空输入护栏,避免传 numpy 空数组给下游)
- `convert_to_numpy=True` 配合 `.tolist()` 返回纯 Python list(契约接口要求)
- `normalize_embeddings=True` 默认开(bge 推荐,cosine ≡ dot product 简化下游 SQLite 向量检索)
- adapter 不读 AppSettings(决策 06 模块封装)— 应用层装配时从 AppSettings 取值传入

### 9.2 `app/config.py` 修订(str_replace)

```python
# str_replace 修订:在 `# LLM` 段(line 13-15)后,`# Storage`(line 17)前插入

# LLM
deepseek_api_key: str
deepseek_base_url: str = "https://api.deepseek.com"

# Embedding(TASK-301 新增)
embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
embedding_device: str = "cpu"
embedding_normalize: bool = True

# Storage
db_path: str = "./data/mxa.db"
...
```

### 9.3 `.env.example` 字节级 Python 修订(**P1-2 newline-aware**)

```python
import pathlib
p = pathlib.Path(".env.example")
data = p.read_bytes()

# P1-2: 自动检测 newline 风格(LF or CRLF)
newline = b"\r\n" if b"\r\n" in data else b"\n"

# 在 # Logging 段前插入 # Embedding 段
old_segment = b"# Logging" + newline + b"LOG_LEVEL=INFO" + newline
new_segment = (
    b"# Embedding(TASK-301 \xe6\x96\xb0\xe5\xa2\x9e)" + newline  # UTF-8 "新增"
    + b"EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5" + newline
    + b"EMBEDDING_DEVICE=cpu" + newline
    + b"EMBEDDING_NORMALIZE=true" + newline
    + newline
    + old_segment
)

assert old_segment in data, "anchor not found, .env.example schema may have drifted"
assert b"EMBEDDING_MODEL_NAME" not in data, "embedding section already present"
data = data.replace(old_segment, new_segment, 1)
p.write_bytes(data)
```

**注**:`\xe6\x96\xb0\xe5\xa2\x9e` 是 UTF-8 "新增" 字节序列。Codex 实施前 Stage 0 必须实地核查 main HEAD `.env.example` 行尾(`git ls-files --eol .env.example` 期望 `i/lf w/lf`,但 patch 不假设,自动适配)。

### 9.4 `requirements.txt` 字节级 Python 追加(**P1-1 尾换行兜底**)

```python
import pathlib
p = pathlib.Path("requirements.txt")
data = p.read_bytes()
assert b"sentence-transformers" not in data, "sentence-transformers already present"

# P1-1: 无尾换行兜底,避免 'pyyaml==x.y.zsentence-transformers' 拼接
if not data.endswith(b"\n"):
    data += b"\n"
data += b"sentence-transformers==3.3.0\n"
p.write_bytes(data)
```

### 9.5 搭车 chore 4 项

#### 9.5.1 反例 26 + 反例 27 + KPI 入仓决策 09(**D8 升级,沿用反例 21-25 同款 patch**)

```python
import pathlib
p = pathlib.Path("docs/decisions/20260603-09-architect-must-verify-not-assume.md")
data = p.read_bytes()

append = """

反例 26(2026-06-05 / 第十五任 / TASK-207 实施 CI hygiene fail):
架构师在 task-207 v0.2 § 6.2 / § 7.2 写 `scripts/export_overview_schema.py` 含 `print(f"Exported schema to {out_path}")`,未实地核查 `scripts/check_repo_hygiene.sh` + `scripts/check_repo_hygiene.py` 对 "no print in non-test .py" 的禁令;且 § 11.2 #4 验收清单只列 `make lint && make type-check && python -m ruff format --check`,漏 `make hygiene` / `make check`。
GPT R1 没抓(GPT 看不到 hygiene 脚本)。Codex 严格 follow 文档跑了三条,没跑 hygiene 也没跑 `make check`,所以本地全绿。CI 跑 `bash scripts/check_repo_hygiene.sh`,FAIL。
接续反例 8(make check vs CI 实际命令漂移)/ 反例 24 / 25 同源:凭印象写代码 + 凭印象写验收清单。

第十六任 KPI 升级(本决策末尾追加):
- 架构师写任何 `scripts/*.py` 前必须 `cat scripts/check_repo_hygiene.sh` + `cat scripts/check_repo_hygiene.py` 实地核查所有 6 条规则(.gitignore / .env.example 字段 / 无 sk-real 字面 / 无 TODO/FIXME/XXX / 无 print 非测试 / 无裸 except)
- 验收清单 #4 必须用 `make check` 全管道,禁拆条核查 lint / type-check / format / test / hygiene;若必须拆条,**先 view `.github/workflows/ci.yml` 全 step 逐条对齐**(决策 09 纪律 7 hard enforce 升级)


反例 27(2026-06-05 / 第十六任 / TASK-301 v0.1 R1 P0-1):
架构师在 TASK-301 v0.1 § 11.2 #5/#6 + D7 中假设 `@pytest.mark.integration` 标记的测试在 CI 默认 `pytest -v --tb=short` 命令下"默认跳过",**未实地核查 `pyproject.toml` 是否含 `[tool.pytest.ini_options].addopts = "-m 'not integration'"`**;PM 实地 `cat pyproject.toml` 确认 addopts 不存在 + markers 也未注册,意味着 integration test 会在 CI 真实跑,触发 sentence-transformers 100MB 模型下载,直接违背 D7 的 "CI 快速 + 无网络" 假设。
GPT R1 P0-1 抓住;v0.2 改用 `RUN_EMBEDDING_INTEGRATION=1` env var skipif 显式 opt-in,不动全局 addopts(避免扩散到其他 Task)。
接续反例 19(框架默认行为假设 / Starlette async 自动线程池)/ 反例 26(scripts/* hygiene 默认行为)同源:"工具默认行为"陈述前必须 cat 工具配置文件实地核查。

第十七任 KPI 升级(本决策末尾追加,叠在第十六任 KPI 之上):
- 任何文档引用"pytest mark X 默认跳过 / skipif / parametrize / asyncio_mode / strict-markers"等行为前,必须 `cat pyproject.toml` + 必要时 `cat tests/conftest.py` 实地核查 `[tool.pytest.ini_options]` 段
- 任何文档引用"mypy 会 / 不会检查 X 模块"前,必须 `cat pyproject.toml` 实地核查 `[tool.mypy]` + 所有 `[[tool.mypy.overrides]]` 条目
- 任何文档引用"ruff 会 / 不会检查 X 规则 / 路径"前,必须 `cat pyproject.toml` 实地核查 `[tool.ruff]` + `[tool.ruff.lint]` 段
- 接续反例 19 / 反例 26:**所有"工具默认行为"陈述前必须 cat 工具配置文件实地核查**,不能凭"标准用法应该是这样"印象写
"""

# 注:assert message 用 ASCII (反例 21-25 同款风格);反例 21-25 用 'reflex N',
# 本 patch 改 'counterexample 26 / 27 already in file' 更准确(P2 文风修订)
assert "反例 26" not in data.decode("utf-8"), "counterexample 26 already in file"
assert "反例 27" not in data.decode("utf-8"), "counterexample 27 already in file"
data = data + append.encode("utf-8")
p.write_bytes(data)
```

**模式可扩展性**:反例 21-25 + 26 + 27 + 未来 28/29/... 全部沿用同款 `read_bytes / 字面追加 / assert "反例 N" not in / write_bytes` 模板。每次新反例只需改 N + 内容字面,patch 形态完全一致(项目级定式,决策 08 字节级 Python 改 docs 已固化)。

#### 9.5.2 03 索引字节级 Python 修订(**P0-2 扩成 7 处**)

```python
import pathlib
p = pathlib.Path("docs/03_TASK_INDEX.md")
data = p.read_bytes()

# P1-2: newline-aware
newline = b"\r\n" if b"\r\n" in data else b"\n"

# 修订 1 (line 121): TASK-207 🔍 → ✅(历史补账)
old1 = b"| TASK-207 | **ProjectOverview Schema + \xe6\x95\x99\xe5\xad\xa6\xe8\xbe\x93\xe5\x87\xba\xe5\xa5\x91\xe7\xba\xa6** \xe2\xad\x90 | \xf0\x9f\x94\x8d | Codex | 203 |"
new1 = b"| TASK-207 | **ProjectOverview Schema + \xe6\x95\x99\xe5\xad\xa6\xe8\xbe\x93\xe5\x87\xba\xe5\xa5\x91\xe7\xba\xa6** \xe2\xad\x90 | \xe2\x9c\x85 | Codex | 203 |"
assert old1 in data, "line 121 (TASK-207) anchor not found"
data = data.replace(old1, new1, 1)

# 修订 2 (line 177 Week 3 第一行 TASK-301): 🔲 → 🔍(本 Task 等待验收)
old2 = b"| TASK-301 | sentence-transformers \xe5\xb5\x8c\xe5\x85\xa5\xe9\x80\x82\xe9\x85\x8d\xe5\x99\xa8 | \xf0\x9f\x94\xb2 | Codex | 101 |"
new2 = b"| TASK-301 | sentence-transformers \xe5\xb5\x8c\xe5\x85\xa5\xe9\x80\x82\xe9\x85\x8d\xe5\x99\xa8 | \xf0\x9f\x94\x8d | Codex | 101 |"
assert old2 in data, "line 177 (TASK-301) anchor not found"
data = data.replace(old2, new2, 1)

# 修订 3 (line 338): Week 2 进度条 6/7 → 7/7
old3 = b"Week 2:  [\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xf0\x9f\x94\x8d]         6/7  (\xe5\x90\xab TASK-207)"
new3 = b"Week 2:  [\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85\xe2\x9c\x85]         7/7  (\xe5\x90\xab TASK-207)"
assert old3 in data, "line 338 (Week 2 bar) anchor not found"
data = data.replace(old3, new3, 1)

# 修订 4 (line 339): Week 3 进度条 [⬜⬜⬜⬜⬜⬜⬜] 0/7 → [🔍⬜⬜⬜⬜⬜⬜] 0/7
old4 = b"Week 3:  [\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c]         0/7  (\xe5\x90\xab TASK-307)"
new4 = b"Week 3:  [\xf0\x9f\x94\x8d\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c\xe2\xac\x9c]         0/7  (\xe5\x90\xab TASK-307)"
assert old4 in data, "line 339 (Week 3 bar) anchor not found"
data = data.replace(old4, new4, 1)

# 修订 5 (line 342): 总计 17/32 → 18/32(注意 TASK-301 是 🔍 不计入完成数)
old5 = b"\xe6\x80\xbb\xe8\xae\xa1: 17/32"
new5 = b"\xe6\x80\xbb\xe8\xae\xa1: 18/32"
assert old5 in data, "line 342 (total) anchor not found"
data = data.replace(old5, new5, 1)

# 修订 6 (line 349): "下一步" 字面更新(P0-2 不再可选)
# 当前: "**下一个待启动**:TASK-203 ProjectOverviewService(架构师写文档中)。完成后由 PM 派 Codex 实施。"
# 改为: "**当前状态**:TASK-301 等待验收;通过后启动 TASK-302 SQLite 向量存储 + 检索。"
old6 = (
    b"**\xe4\xb8\x8b\xe4\xb8\x80\xe4\xb8\xaa\xe5\xbe\x85\xe5\x90\xaf\xe5\x8a\xa8**\xef\xbc\x9a"
    b"TASK-203 ProjectOverviewService\xef\xbc\x88\xe6\x9e\xb6\xe6\x9e\x84\xe5\xb8\x88\xe5\x86\x99\xe6\x96\x87\xe6\xa1\xa3\xe4\xb8\xad\xef\xbc\x89\xe3\x80\x82"
    b"\xe5\xae\x8c\xe6\x88\x90\xe5\x90\x8e\xe7\x94\xb1 PM \xe6\xb4\xbe Codex \xe5\xae\x9e\xe6\x96\xbd\xe3\x80\x82"
)
new6 = (
    b"**\xe5\xbd\x93\xe5\x89\x8d\xe7\x8a\xb6\xe6\x80\x81**\xef\xbc\x9a"
    b"TASK-301 \xe7\xad\x89\xe5\xbe\x85\xe9\xaa\x8c\xe6\x94\xb6\xef\xbc\x9b"
    b"\xe9\x80\x9a\xe8\xbf\x87\xe5\x90\x8e\xe5\x90\xaf\xe5\x8a\xa8 TASK-302 SQLite \xe5\x90\x91\xe9\x87\x8f\xe5\xad\x98\xe5\x82\xa8 + \xe6\xa3\x80\xe7\xb4\xa2\xe3\x80\x82"
)
assert old6 in data, "line 349 (next step) anchor not found"
data = data.replace(old6, new6, 1)

# 修订 7 (line 354): 最后更新日期
old7 = b"**\xe6\x9c\x80\xe5\x90\x8e\xe6\x9b\xb4\xe6\x96\xb0**\xef\xbc\x9a2026-06-01"
new7 = b"**\xe6\x9c\x80\xe5\x90\x8e\xe6\x9b\xb4\xe6\x96\xb0**\xef\xbc\x9a2026-06-05"
assert old7 in data, "line 354 (last updated) anchor not found"
data = data.replace(old7, new7, 1)

p.write_bytes(data)
```

**注**(P0-2):
- 7 处修订全 UTF-8 字节级,assert anchor 兜底防漂移
- TASK-301 状态 🔲→🔍 是关键(决策 07:Codex 完工必改本 Task 状态;v0.1 漏列)
- 总计仍是 18/32(TASK-301 🔍 不计入,完成数维持 18,只 TASK-207 ✅ 贡献 +1)
- Week 3 进度条加 🔍 第一格(本 Task)
- line 349 "下一步" stale 改成"当前状态"语义(指向 TASK-302 为下个 Task)
- newline 兜底:实地核查 main HEAD 03 索引是 LF,但 patch 仍走 `newline = b"\r\n" if b"\r\n" in data else b"\n"` 兜底(本 patch 的修订 anchor 不含 newline,所以 newline 检测仅用于未来字段插入场景;P1-2 全局规则一致性)

#### 9.5.3 04 § 10 ERROR_MAP dict 字面 → tuple 字面修订(**P0-3 fence 边界替换 + P0-4 PM 例外授权**)

**P0-4 例外授权声明**:

> 本次 `docs/04_ENGINEERING_STANDARDS.md` § 10 修订是 PM 对决策 07 的一次性显式例外授权,性质是"纠正已与 main HEAD `api/middleware/error_handler.py` 实施漂移的工程规范示例片段",**不修改架构、异常树或 API 行为**;不得作为后续普通 Task 可搭车修改 01/02/04/05 核心文档的先例。本次例外的具体范围:
> - ✅ 允许:§ 10 line 552-566 代码示例 dict 字面 → tuple 字面(对齐 main HEAD 实际形态)
> - ❌ 禁止:任何超出此范围的 § 10 / 其他章节修订
> - ❌ 禁止:后续普通 Task 引用本次为先例;若发生同类漂移,走单独 chore PR

**P0-3 fence 边界替换 patch**:

```python
import pathlib
p = pathlib.Path("docs/04_ENGINEERING_STANDARDS.md")
data = p.read_bytes()

# P0-3: 不用 30 行整块 bytes anchor(字符级 typo 风险高);改用 fence 边界替换
# 实际围栏是 3 反引号(v0.1 P0-3 报告的四反引号是 v0.1 typo)
START_MARK = b"```python\n# api/middleware/error_handler.py\nERROR_MAP = {\n"
END_MARK = b"```\n"

start = data.find(START_MARK)
assert start >= 0, "04 §10 ERROR_MAP fence start mark not found"

end = data.find(END_MARK, start + len(START_MARK))
assert end >= 0, "04 §10 ERROR_MAP fence end mark not found"
end_inclusive = end + len(END_MARK)

# 防重复(若 patch 误跑两次)
assert b"error_handlers: tuple" not in data[start:end_inclusive], (
    "04 §10 already migrated to tuple form"
)

# 新代码块(UTF-8 字面,内容对齐 task-206 § 上游契约段 21 handler 完整表的高频示例)
new_block = (
    b"```python\n"
    b"# api/middleware/error_handler.py\n"
    b"# \xe5\xae\x9e\xe9\x99\x85\xe5\xbd\xa2\xe6\x80\x81\xef\xbc\x88TASK-206 \xe5\xae\x9e\xe6\x96\xbd\xef\xbc\x89\xe6\x98\xaf tuple of (Exception, status, machine_code, message)\xef\xbc\x8c\n"
    b"# \xe7\x94\xb1 register_error_handlers() \xe5\xbe\xaa\xe7\x8e\xaf app.add_exception_handler \xe6\xb3\xa8\xe5\x86\x8c\xe3\x80\x82\n"
    b"# \xe6\xad\xa4\xe5\xa4\x84\xe4\xbb\x85\xe5\x88\x97\xe9\xab\x98\xe9\xa2\x91\xe7\xa4\xba\xe4\xbe\x8b\xef\xbc\x9b\xe5\xae\x8c\xe6\x95\xb4 21 handler \xe8\xa1\xa8\xe8\xa7\x81 docs/tasks/task-206-error-handling-and-i18n.md\xe3\x80\x82\n"
    b"error_handlers: tuple[tuple[type[Exception], int, str, str], ...] = (\n"
    b"    (ZipBombError, 400, \"zip_bomb\", \"\xe5\x8e\x8b\xe7\xbc\xa9\xe6\x96\x87\xe4\xbb\xb6\xe5\xbc\x82\xe5\xb8\xb8\xef\xbc\x8c\xe8\xaf\xb7\xe6\xa3\x80\xe6\x9f\xa5\xe5\x90\x8e\xe9\x87\x8d\xe6\x96\xb0\xe4\xb8\x8a\xe4\xbc\xa0\"),\n"
    b"    (ZipSlipError, 400, \"zip_slip\", \"\xe5\x8e\x8b\xe7\xbc\xa9\xe5\x8c\x85\xe5\x86\x85\xe5\x90\xab\xe9\x9d\x9e\xe6\xb3\x95\xe8\xb7\xaf\xe5\xbe\x84\xef\xbc\x8c\xe8\xaf\xb7\xe9\x87\x8d\xe6\x96\xb0\xe6\x89\x93\xe5\x8c\x85\xe5\x90\x8e\xe4\xb8\x8a\xe4\xbc\xa0\"),\n"
    b"    (FileTypeNotAllowedError, 400, \"file_type_not_allowed\", \"\xe5\x8c\x85\xe5\x90\xab\xe4\xb8\x8d\xe6\x94\xaf\xe6\x8c\x81\xe7\x9a\x84\xe6\x96\x87\xe4\xbb\xb6\xe7\xb1\xbb\xe5\x9e\x8b\"),\n"
    b"    (ProjectTooLargeError, 413, \"project_too_large\", \"\xe5\xb7\xa5\xe7\xa8\x8b\xe8\xbf\x87\xe5\xa4\xa7\xef\xbc\x8c\xe8\xaf\xb7\xe5\x8e\x8b\xe7\xbc\xa9\xe5\x88\xb0 50MB \xe4\xbb\xa5\xe5\x86\x85\"),\n"
    b"    (LLMAuthError, 503, \"llm_auth\", \"\xe6\x9c\x8d\xe5\x8a\xa1\xe6\x9a\x82\xe6\x97\xb6\xe4\xb8\x8d\xe5\x8f\xaf\xe7\x94\xa8\xef\xbc\x8c\xe8\xaf\xb7\xe7\xa8\x8d\xe5\x90\x8e\xe9\x87\x8d\xe8\xaf\x95\"),\n"
    b"    (LLMRateLimitError, 429, \"llm_rate_limit\", \"\xe8\xaf\xb7\xe6\xb1\x82\xe5\xa4\xaa\xe9\xa2\x91\xe7\xb9\x81\xef\xbc\x8c\xe7\xa8\x8d\xe7\xad\x89\xe4\xb8\x80\xe4\xb8\x8b\"),\n"
    b"    (LLMTimeoutError, 504, \"llm_timeout\", \"\xe7\xbd\x91\xe7\xbb\x9c\xe8\xbe\x83\xe6\x85\xa2\xef\xbc\x8c\xe6\xad\xa3\xe5\x9c\xa8\xe9\x87\x8d\xe8\xaf\x95...\"),\n"
    b"    (SlxParseError, 400, \"slx_parse\", \"Simulink \xe6\xa8\xa1\xe5\x9e\x8b\xe8\xa7\xa3\xe6\x9e\x90\xe5\xa4\xb1\xe8\xb4\xa5\xef\xbc\x8c\xe5\x8f\xaf\xe8\x83\xbd\xe7\x89\x88\xe6\x9c\xac\xe8\xbf\x87\xe8\x80\x81\xe6\x88\x96\xe6\x8d\x9f\xe5\x9d\x8f\"),\n"
    b"    (QuotaExhaustedError, 402, \"quota_exhausted\", \"\xe5\xb7\xb2\xe8\xbe\xbe\xe5\x88\xb0\xe5\x90\x88\xe7\x90\x86\xe4\xbd\xbf\xe7\x94\xa8\xe4\xb8\x8a\xe9\x99\x90\xef\xbc\x8c\xe5\x8f\xaf\xe8\x81\x94\xe7\xb3\xbb\xe5\x8a\xa0\xe9\x87\x8f\"),\n"
    b"    # ... \xe5\x85\xb1 21 \xe6\x9d\xa1\xef\xbc\x8c\xe8\xaf\xa6\xe8\xa7\x81 TASK-206 \xe5\xae\x9e\xe6\x96\xbd\xe6\x96\x87\xe6\xa1\xa3\n"
    b")\n"
    b"```\n"
)

data = data[:start] + new_block + data[end_inclusive:]
p.write_bytes(data)
```

**P0-3 关键改动**:
- 不再用 30 行整块 `old_block` anchor(字符级漂移风险)
- 改用 `START_MARK = "```python\n# api/middleware/error_handler.py\nERROR_MAP = {\n"` + `END_MARK = "```\n"` fence 边界查找
- `data.find` + assert ≥ 0 双兜底,任一找不到立即停手(决策 09 纪律 1)
- assert "error_handlers: tuple" not in 防重复入仓
- 实际围栏是 **3 反引号**(v0.1 P0-3 报告的四反引号是 v0.1 typo,v0.2 已修)

### 9.6 `tests/adapters/embedding/conftest.py` 完整骨架(**P1-4 非零向量**)

```python
"""Embedding adapter 测试 fixture。"""

from __future__ import annotations

import pytest

from core.interfaces.embedder import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """测试用 mock,返回固定非零向量(避免下游余弦相似度除零)。不加载真实模型。

    供 TASK-302(向量存储)/ TASK-304(向量 RAG)的测试场景使用。

    P1-4 教训:全零向量在下游余弦相似度场景中触发 div-by-zero 分支 + 所有
    分数相同导致排序测试无意义;改 base[0]=1.0 即可消除两个风险。
    """

    def __init__(self, dimension: int = 512) -> None:
        self._dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        # P1-4: 非零向量(单位向量),L2 范数 = 1.0
        base = [0.0] * self._dimension
        base[0] = 1.0
        return [base.copy() for _ in texts]

    def dimension(self) -> int:
        return self._dimension


@pytest.fixture
def mock_embedder() -> MockEmbeddingProvider:
    """返回 dimension=512 的 MockEmbeddingProvider(匹配 bge-small-zh-v1.5)。"""
    return MockEmbeddingProvider(dimension=512)
```

### 9.7 `tests/adapters/embedding/test_sentence_transformer_unit.py` 骨架(**P2-1 strip 单测**)

```python
"""SentenceTransformerEmbedder unit tests(mock 模型加载,不真实下载)。"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from adapters.embedding.sentence_transformer import (
    DEFAULT_DEVICE,
    DEFAULT_MODEL_NAME,
    DEFAULT_NORMALIZE,
    SentenceTransformerEmbedder,
)


@pytest.fixture
def mock_st_class(mocker):
    """mock SentenceTransformer 类,避免真实下载模型。"""
    mock_class = mocker.patch(
        "adapters.embedding.sentence_transformer.SentenceTransformer"
    )
    mock_instance = MagicMock()
    mock_instance.get_sentence_embedding_dimension.return_value = 512
    mock_instance.encode.return_value = np.array([[0.1, 0.2, 0.3]] * 1)
    mock_class.return_value = mock_instance
    return mock_class, mock_instance


def test_init_with_defaults_loads_model(mock_st_class):
    mock_class, _ = mock_st_class
    embedder = SentenceTransformerEmbedder()
    mock_class.assert_called_once_with(DEFAULT_MODEL_NAME, device=DEFAULT_DEVICE)
    assert embedder.dimension() == 512


def test_init_with_custom_model_name(mock_st_class):
    mock_class, _ = mock_st_class
    SentenceTransformerEmbedder(model_name="custom/model", device="cuda")
    mock_class.assert_called_once_with("custom/model", device="cuda")


def test_init_empty_model_name_raises(mock_st_class):
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        SentenceTransformerEmbedder(model_name="")


def test_init_whitespace_model_name_raises(mock_st_class):
    """P2-1: 全空格也算空。"""
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        SentenceTransformerEmbedder(model_name="   ")


def test_init_dimension_none_raises(mock_st_class):
    """P2-2: get_sentence_embedding_dimension() 返回 None 防御。"""
    _, mock_instance = mock_st_class
    mock_instance.get_sentence_embedding_dimension.return_value = None
    with pytest.raises(ValueError, match="model dimension is unavailable"):
        SentenceTransformerEmbedder()


def test_embed_returns_list_of_lists(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.encode.return_value = np.array([[1.0, 2.0], [3.0, 4.0]])
    embedder = SentenceTransformerEmbedder()
    result = embedder.embed(["text1", "text2"])
    assert isinstance(result, list)
    assert all(isinstance(v, list) for v in result)
    assert result == [[1.0, 2.0], [3.0, 4.0]]


def test_embed_empty_input_returns_empty(mock_st_class):
    _, mock_instance = mock_st_class
    embedder = SentenceTransformerEmbedder()
    assert embedder.embed([]) == []
    # 关键:空输入不调 encode
    mock_instance.encode.assert_not_called()


def test_embed_passes_normalize_flag(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.encode.return_value = np.array([[1.0]])
    embedder = SentenceTransformerEmbedder(normalize=False)
    embedder.embed(["text"])
    call_kwargs = mock_instance.encode.call_args.kwargs
    assert call_kwargs["normalize_embeddings"] is False


def test_dimension_returns_loaded_dimension(mock_st_class):
    _, mock_instance = mock_st_class
    mock_instance.get_sentence_embedding_dimension.return_value = 768
    embedder = SentenceTransformerEmbedder()
    assert embedder.dimension() == 768


def test_default_normalize_is_true():
    assert DEFAULT_NORMALIZE is True


def test_default_model_is_bge_small_zh():
    assert DEFAULT_MODEL_NAME == "BAAI/bge-small-zh-v1.5"


def test_default_device_is_cpu():
    assert DEFAULT_DEVICE == "cpu"
```

### 9.8 `tests/adapters/embedding/test_sentence_transformer_integration.py` 骨架(**P0-1 skipif env + P1-5 维度契约**)

```python
"""SentenceTransformerEmbedder integration tests(真实加载模型,默认跳过)。

**P0-1 启动方式**:通过环境变量 ``RUN_EMBEDDING_INTEGRATION=1`` 显式 opt-in:

    RUN_EMBEDDING_INTEGRATION=1 pytest tests/adapters/embedding/test_sentence_transformer_integration.py -v

CI 默认 ``pytest -v --tb=short`` 不设此 env,本文件全部 skip。

**P1-5 维度契约**:Runtime 代码(adapter / AppSettings / mock fixture)不写死 dimension;
integration test 钉死当前默认模型 ``BAAI/bge-small-zh-v1.5`` 的契约维度 512。若 HuggingFace
模型卡升级或默认模型变更,此测试触发 fail,提醒架构师同步:
  - ``MockEmbeddingProvider`` 默认 dimension(若依赖此契约)
  - TASK-302 SQLite 向量存储 schema(若 BLOB 列宽固定)
  - 02 § 6 决策 2 文档描述
"""

from __future__ import annotations

import os

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder

# P0-1: 显式 opt-in,默认 skip
RUN_INTEGRATION = os.getenv("RUN_EMBEDDING_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        not RUN_INTEGRATION,
        reason="Set RUN_EMBEDDING_INTEGRATION=1 to run real embedding model tests.",
    ),
]


def test_real_model_load_and_embed() -> None:
    """实地加载 bge-small-zh-v1.5,验证 dimension 契约 + embed shape。"""
    embedder = SentenceTransformerEmbedder()

    # P1-5: dimension == 512 是 bge-small-zh-v1.5 的契约维度,钉死防模型升级悄悄漂移
    assert embedder.dimension() == 512, (
        f"bge-small-zh-v1.5 contract dimension is 512, got {embedder.dimension()}. "
        "If model card or default model changed, sync MockEmbeddingProvider "
        "default + 02 § 6 决策 2 + downstream TASK-302 schema."
    )

    vectors = embedder.embed(["你好,这是测试文本", "Hello world"])
    assert len(vectors) == 2
    assert all(len(v) == embedder.dimension() for v in vectors)
    assert all(isinstance(x, float) for v in vectors for x in v)


def test_real_model_embed_empty_input() -> None:
    """空输入返回空列表(不触发真实 encode)。"""
    embedder = SentenceTransformerEmbedder()
    assert embedder.embed([]) == []
```

### 9.9 `adapters/embedding/__init__.py`

```python
"""Embedding adapter 模块。"""

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder

__all__ = ["SentenceTransformerEmbedder"]
```

### 9.10 `adapters/embedding/README.md`

```markdown
# adapters/embedding

EmbeddingProvider 实现层,把 sentence-transformers 接入 mxa-tutor。

## 当前实现

- `SentenceTransformerEmbedder` — 基于 `BAAI/bge-small-zh-v1.5`(中文,~100MB,CPU 推理),实现 `core/interfaces/embedder.py::EmbeddingProvider`。

## 装配

本 Task(TASK-301)只实现 adapter 类,**不**在 lifespan 装配 `app.state.embedder`。
TASK-302(SQLite 向量存储)/ TASK-304(向量 RAG 整合)接通时再装配 lifespan +
`api/dependencies.py::get_embedder()`。

## 模型缓存

走 HuggingFace 默认路径 `~/.cache/huggingface/`。首次加载需联网下载(~100MB)。
离线开发设 `HF_HUB_OFFLINE=1` 环境变量(需先在线下载过一次到默认缓存)。

## 测试

- unit test:`pytest tests/adapters/embedding/ -v` — 全部 mock,不下载模型
- integration test:`RUN_EMBEDDING_INTEGRATION=1 pytest tests/adapters/embedding/test_sentence_transformer_integration.py -v` — 实地加载,需联网
```

### 9.11 `pyproject.toml` 修订(**P1-3 mypy override + P2-3 markers 注册**)

```python
import pathlib
p = pathlib.Path("pyproject.toml")
data = p.read_bytes()

newline = b"\r\n" if b"\r\n" in data else b"\n"

# P1-3: 加 mypy override(sentence_transformers + transitive deps 无 stubs)
# 实地核查 main HEAD:无 [[tool.mypy.overrides]] 段,append 在文件末尾
assert b"sentence_transformers" not in data, "sentence_transformers override already present"
mypy_override = (
    newline
    + b"[[tool.mypy.overrides]]" + newline
    + b'module = "sentence_transformers.*"' + newline
    + b"ignore_missing_imports = true" + newline
)
data = data + mypy_override

# P2-3: 加 pytest markers 注册(防 --strict-markers 切换 + 文档化)
# 实地核查 main HEAD:[tool.pytest.ini_options] 段含 testpaths + asyncio_mode,无 markers
old_pytest_section = (
    b"[tool.pytest.ini_options]" + newline
    + b'testpaths = ["tests"]' + newline
    + b'asyncio_mode = "auto"' + newline
)
new_pytest_section = (
    b"[tool.pytest.ini_options]" + newline
    + b'testpaths = ["tests"]' + newline
    + b'asyncio_mode = "auto"' + newline
    + b"markers = [" + newline
    + b'    "integration: tests that call external services or load real models",' + newline
    + b'    "slow: tests that are intentionally slow",' + newline
    + b"]" + newline
)
assert old_pytest_section in data, "pytest section anchor not found, pyproject.toml schema may have drifted"
assert b'markers = [' not in data, "pytest markers already registered"
data = data.replace(old_pytest_section, new_pytest_section, 1)

p.write_bytes(data)
```

**注**:
- **P1-3** mypy override append 在文件末尾(实地核查 main HEAD pyproject.toml 末段是 `[tool.pytest.ini_options]`;append 不会冲突)
- **P2-3** markers 注册插入 `[tool.pytest.ini_options]` 段尾,保留 testpaths + asyncio_mode 原序
- newline-aware 兜底(同 P1-2)
- 双 assert 防重复入仓

---

## 决策日志

### D1 — 审批级别:一审 1 轮

反例 18 自检 5 维度全低(见上文)。范围窄(不动 lifespan / dependencies / 异常树 / handler),决策密度集中在"adapter 实现细节"层,无新业务决策,无新 async 模式,无新隐私数据流。类比 TASK-106(DeepSeek adapter)+ TASK-207(契约文档)一审 1 轮先例。R1 已 conditional pass(2026-06-05)。

### D2 — 范围窄:不动 lifespan / dependencies(本 Task 核心边界)

**理由**:
- TASK-301 = adapter 实现层。lifespan 装配应在**有消费者**时引入(TASK-302/304),而非"先建好等用"
- lifespan 内若直接 `app.state.embedder = SentenceTransformerEmbedder(...)`,测试 `with TestClient(app)` 会**真实触发 100MB 下载**
- 类比 TASK-106 完工(commit `b1eb647`)时 DeepSeek adapter 也不在 lifespan;TASK-201(commit `fa7a4b0`)才在 lifespan 装配 `app.state.text_provider`,本 Task 沿用此节奏

**替代方案**:
- A(本 Task 选):窄,adapter + 配置 + 测试。**为何选**:✅ 最小 cohesion,TASK-302/304 接通有完整测试场景再装配
- B. 中,A + lifespan 装配 + dependency。**为何不选**:lifespan 测试触发真实下载,CI 时间 +5-10min + flaky
- C. 宽,B + EmbeddingModelLoadError + ERROR_MAP handler。**为何不选**:lifespan 失败无 HTTP 响应,handler 用不上

**实施层支持**:
- adapter 不读 AppSettings(决策 06 模块封装)— TASK-302/304 装配时从 AppSettings 取值传入
- `MockEmbeddingProvider` 已就位,TASK-302/304 测试直接复用

### D3 — adapter 实现模式:类比 DeepSeek `__init__` 接收所有运行时值

**理由**:
- DeepSeek adapter(commit `b1eb647`)已验证此模式 — `__init__(api_key, base_url, model, retry_count)` 全部参数注入,**不读 `app.config`**
- 决策 06 模块封装:adapter 层不依赖 app 层
- 测试可任意覆盖参数

**实施模式**:见 § 9.1。

**替代方案**:
- A(本 Task 选):__init__ 接收所有运行时值。**为何选**:✅ 类比 DeepSeek 模式 + 决策 06 模块封装
- B. __init__ 接收 AppSettings 对象。**为何不选**:adapter 与 AppSettings 耦合
- C. 模块级单例。**为何不选**:违反 04 § 4 禁全局可变状态

### D4 — 模型加载时机:`__init__` 同步加载

**理由**:
- `core/interfaces/embedder.py` 是同步接口,adapter 实现也同步
- 类比 DeepSeek `__init__` 内 `self._client = OpenAI(...)` 立即建立资源
- 应用层(异步 lifespan / async endpoint)调用方负责 `await asyncio.to_thread(SentenceTransformerEmbedder, ...)` 桥接(决策 11 决策 1)— adapter 不引入 async 模式
- `__init__` 同步让测试简单:`embedder = SentenceTransformerEmbedder()` 直接构造

**TASK-302/304 future 装配伪代码示例**(本 Task 不实施):

```python
# 未来 TASK-302/304 lifespan 装配
app.state.embedder = await asyncio.to_thread(
    SentenceTransformerEmbedder,
    model_name=settings.embedding_model_name,
    device=settings.embedding_device,
    normalize=settings.embedding_normalize,
)
```

**替代方案**:
- A(本 Task 选):__init__ 同步加载。**为何选**:✅ 接口一致 + 决策 11 一致
- B. async `__init__` / lazy 加载。**为何不选**:违反 Python 类构造同步惯例 + 首次 embed() 阻塞用户请求
- C. adapter 内自起线程。**为何不选**:不应引入 threading,这是调用方责任

### D5 — 不引入 EmbeddingError 异常类(范围决定)

**理由**:
- 本 Task 不在 lifespan 装配,无 startup failure 异常链需求
- 本 Task 不消费 embed(),无 runtime failure 异常需求
- sentence-transformers 库自身抛的异常在 adapter `__init__` 时直接透传,调用方(TASK-302/304 lifespan)可在装配时翻译为 `EmbeddingModelLoadError(MxaError)`(那个 Task 引入)

**TASK-302/304 future 引入路径**(本 Task 文档化但不实施):

```python
# 未来 TASK-302/304 lifespan 装配时
try:
    embedder = await asyncio.to_thread(SentenceTransformerEmbedder, ...)
except Exception as exc:
    logger.error(
        "Failed to load embedding model: model_name={} exception={}",
        settings.embedding_model_name,
        type(exc).__name__,  # 决策 11 metadata-only
    )
    raise EmbeddingModelLoadError(
        f"Failed to load embedding model: {settings.embedding_model_name}"
    ) from exc
```

`EmbeddingModelLoadError(MxaError)` 是 TASK-302 或 TASK-304 范围。

**替代方案**:
- A(本 Task 选):不引入。**为何选**:✅ 无消费场景
- B. 占位异常类。**为何不选**:无用例无测试,违反 04 § 5
- C. adapter 内 catch 翻译。**为何不选**:无 HTTP handler 消费

### D6 — AppSettings 3 字段:不暴露 cache_dir

**理由**:
- HuggingFace 默认 cache 路径 `~/.cache/huggingface/` 跨平台工作良好
- KISS:3 字段够用;未来 Phase 2 / 离线分发场景再加 cache_dir
- 用户离线开发用 `HF_HUB_OFFLINE=1` ENV 实现,不需 cache_dir 字段

**字段名理由**:
- `embedding_model_name` — 与 02 § 6 决策 2 表述一致
- `embedding_device` — 简短,torch 是实现细节
- `embedding_normalize` — 与 sentence-transformers `encode(normalize_embeddings=)` 语义一致

**替代方案**:
- A(本 Task 选):3 字段。**为何选**:✅ KISS + 覆盖核心配置面
- B. 6+ 字段(cache_dir / max_seq_length / batch_size)。**为何不选**:无用例,过度设计
- C. 0 字段全硬编码。**为何不选**:无法在生产环境调整 device="cuda"

### D7 — 测试策略:unit mock + integration **RUN_EMBEDDING_INTEGRATION=1 env skipif**(P0-1 修订)

**理由**:
- unit test 用 `mocker.patch("adapters.embedding.sentence_transformer.SentenceTransformer")` 替换类本身,**不真实加载**
- integration test(P0-1 修订)用 `pytest.mark.skipif(os.getenv("RUN_EMBEDDING_INTEGRATION") != "1", ...)` 显式 opt-in,**默认 skip**(包括 CI)
- 本地开发者跑 `RUN_EMBEDDING_INTEGRATION=1 pytest tests/adapters/embedding/test_sentence_transformer_integration.py -v` 显式触发
- pytest markers `integration` + `slow` 仍打,P2-3 在 pyproject.toml 注册

**P0-1 关键决策**:用 skipif env 而非全局 addopts
- ❌ 不改全局 addopts(扩散到其他 Task 风险:其他 Task 的 integration / slow 标记测试也会被影响,违反"小范围改动"惯例)
- ✅ 用 skipif env(本 Task 范围,显式 opt-in,语义清晰)
- ✅ 加 markers 注册(P2-3,**与 skipif 互补**:markers 防 strict-markers 切换,skipif 控跳过)

**CI 时间影响**:requirements.txt 加 sentence-transformers + transitive deps(torch ~1GB)— CI 首次 install 慢 5-10min,后续 pip cache 复用(已配置 `cache: 'pip'` + `cache-dependency-path: requirements-dev.txt`)。

**实施层支持**:见 § 9.7 + § 9.8 + § 9.11。

**替代方案**:
- A(本 Task 选):skipif env + markers 注册。**为何选**:✅ 本 Task 范围 + 显式 opt-in
- B. 全局 addopts = "-m 'not integration'"。**为何不选**:扩散到所有 Task,违反小范围改动
- C. CI 跑 integration 强制真实加载。**为何不选**:CI +5-10min + HuggingFace flaky 风险
- D. 不写 integration test。**为何不选**:无 integration 测试无法证明实地可用

### D8 — 搭车 chore 4 项(**P0-4 PM 决策 07 一次性显式例外授权**)

**搭车范围**(v0.1 → v0.2 由 3 项升 4 项):
1. **反例 26** + 第十六任 KPI 入仓决策 09(第十五任 TASK-207 治理候选)
2. **反例 27** + 第十七任 KPI 入仓决策 09(**v0.2 新增**:第十六任 TASK-301 v0.1 R1 P0-1 治理候选)
3. **03 索引 7 行修订**(P0-2 升级:TASK-207 ✅ + TASK-301 🔍 + Week 2 7/7 + Week 3 [🔍...] + 18/32 + line 349 + 日期)
4. **04 § 10 ERROR_MAP dict → tuple 字面修订**(P0-3 fence 边界替换 + P0-4 PM 例外授权)

**P0-4 决策 07 一次性显式例外授权声明**:

> 本次 `docs/04_ENGINEERING_STANDARDS.md` § 10 修订是 PM 对决策 07(03 索引更新边界 + 核心文档修订需 PM 单独流程)的一次性显式例外授权,性质是"纠正已与 main HEAD `api/middleware/error_handler.py` 实施漂移的工程规范示例片段"(TASK-206 实施时改了 error_handler.py 但未同步 04 § 10 教学示例),**不修改架构、异常树或 API 行为**;仅是教学示例的字面同步。
>
> 本次例外的具体边界:
> - ✅ 允许:§ 10 line 552-566 代码示例 dict 字面 → tuple 字面(对齐 main HEAD)
> - ❌ 禁止:任何超出此范围的 § 10 / 其他章节修订
> - ❌ 禁止:后续普通 Task 引用本次为先例;若发生同类漂移,走单独 chore PR
> - ❌ 禁止:把本 Task D8 作为"先例"引用,要求后续 Task 自动放宽 docs/04 修订规则
>
> **PM 授权确认**(本会话 R1 后拍板):"04 § 10 ERROR_MAP dict 漂移修怎么走? → 搭车 TASK-301 PR 一起修"。

**模式可扩展性**:4 项 chore 全部沿用 `read_bytes / 字面匹配(或 fence 边界查找)/ assert "锚点" in data / write_bytes` 字节级 Python 模板。反例 21-25 + 26 + 27 + 未来 28/29 是同款 patch 模板(决策 08 字节级 Python 改 docs 固化为项目纪律)。

**字节级 Python 完整 patch**:见 § 9.5。

**替代方案**:
- A(本 Task 选):搭车 4 项。**为何选**:✅ Week 3 起步搭车成本接近 0;治理 + 项目级遗留一次性收口;反例 26 + 27 同源教训("工具默认行为假设")一并入仓对第十七任更友好
- B. 仅搭车反例 26 + 03 索引(04 § 10 + 反例 27 单开 chore PR)。**为何不选**:① 反例 27 是本 Task v0.1 → R1 之间产出,搭车时机最佳;② 04 § 10 单 chore PR 多一次 review + merge 循环
- C. 全部推到 chore PR 单走。**为何不选**:03 索引补账是本 Task 必然产出,不搭不行

---

## 验收清单

### 11.1 测试要求

`tests/adapters/embedding/test_sentence_transformer_unit.py` 必须覆盖:

- ✅ `__init__` 默认参数加载模型(mock 调用 + dimension 返回 512)
- ✅ `__init__` 自定义 model_name / device
- ✅ `__init__` 空 model_name 抛 ValueError
- ✅ **P2-1**:`__init__` 全空格 model_name 抛 ValueError("after strip")
- ✅ **P2-2**:`__init__` 模型 dimension 返回 None 抛 ValueError
- ✅ `embed` 返回 `list[list[float]]`(类型 + shape)
- ✅ `embed([])` 返回 `[]`(空输入护栏,encode 不被调)
- ✅ `embed` 传递 `normalize` flag 给 `encode(normalize_embeddings=...)`
- ✅ `dimension` 返回正确值
- ✅ 模块级 `DEFAULT_*` 常量正确(bge-small-zh-v1.5 / cpu / True)

`tests/adapters/embedding/test_sentence_transformer_integration.py` 必须覆盖(**P0-1 RUN_EMBEDDING_INTEGRATION=1 env opt-in,默认 skip**):

- ✅ 实地加载 bge-small-zh-v1.5,**dimension == 512 钉死契约**(P1-5)
- ✅ embed 2 个中英文混合文本,返回正确 shape + float 类型
- ✅ embed 空列表返回空列表

### 11.2 验收 N 条(按顺序勾选)

**所有 grep 用 POSIX 字符类**(反例 25 KPI)。**所有 scripts/* 写入前 cat hygiene 脚本**(反例 26 KPI;本 Task 不写新 scripts/* 文件)。**所有 pytest / mypy / ruff 行为陈述前 cat pyproject.toml**(反例 27 KPI)。

```bash
# 1. 文件清单 ls 检查(7 新增)
ls adapters/embedding/__init__.py \
   adapters/embedding/sentence_transformer.py \
   adapters/embedding/README.md \
   tests/adapters/embedding/__init__.py \
   tests/adapters/embedding/conftest.py \
   tests/adapters/embedding/test_sentence_transformer_unit.py \
   tests/adapters/embedding/test_sentence_transformer_integration.py

# 2. AppSettings 新增字段 grep
grep -nE "embedding_model_name|embedding_device|embedding_normalize" app/config.py
# 期望:3 行命中

# 3. .env.example 同步 grep
grep -nE "EMBEDDING_MODEL_NAME|EMBEDDING_DEVICE|EMBEDDING_NORMALIZE" .env.example
# 期望:3 行命中

# 4. **make check 全管道**(反例 26 KPI 第一次硬执行)
make check
# 期望:exit 0,All checks passed!
# 注:这一条**等价于 CI 全 step**(ruff check + ruff format --check + mypy + pytest + hygiene),
# 禁拆条核查;若拆条必须 cat .github/workflows/ci.yml 全 step 逐条对齐(决策 09 纪律 7)

# 5. unit test 全过(不下载模型,integration 默认 skip)
pytest tests/adapters/embedding/ -v
# 期望:约 12 个 unit test passed,2 个 integration test skipped(skipif 起效)
# 反例 27 验证:无 RUN_EMBEDDING_INTEGRATION env,integration 必须 skip

# 6. integration test 手动触发(可选,需联网)
RUN_EMBEDDING_INTEGRATION=1 pytest \
  tests/adapters/embedding/test_sentence_transformer_integration.py -v
# 期望:2 个 integration test passed(首次 ~100MB 下载)
# 验收时可选,本地手动跑过留截图给 PM

# 7. requirements.txt 新增 deps
grep -nE "^sentence-transformers==" requirements.txt
# 期望:1 行命中,版本 3.3.0

# 8. adapter 不读 AppSettings 验证(决策 06)
grep -rnE "from app|import app\.config|AppSettings" adapters/embedding/ || true
# 期望:无输出(P2-4:|| true 防 set -e 中断)

# 9. **P1-3 + P2-3** pyproject.toml 修订验证
grep -nE 'sentence_transformers|markers = \[' pyproject.toml
# 期望:含 `module = "sentence_transformers.*"` + `markers = [`

# 10. 反例 26 + 27 + KPI 已入仓决策 09(D8 搭车 chore)
grep -nE "反例 ?26|反例 ?27|第十六任 KPI|第十七任 KPI|cat scripts/check_repo_hygiene|cat pyproject\.toml" docs/decisions/20260603-09-architect-must-verify-not-assume.md
# 期望:多行命中(反例 26 / 27 / 第十六 + 十七任 KPI / cat hygiene / cat pyproject 锚点)

# 11. 03 索引 7 行修订(P0-2 升级)
grep -nE "TASK-207 \| \*\*ProjectOverview.+✅" docs/03_TASK_INDEX.md  # 修订 1
grep -nE "TASK-301 \| sentence-transformers.+🔍" docs/03_TASK_INDEX.md  # 修订 2
grep -nE "Week 2:  \[(✅){7}\]         7/7" docs/03_TASK_INDEX.md  # 修订 3
grep -nE "Week 3:  \[🔍" docs/03_TASK_INDEX.md  # 修订 4
grep -n "总计: 18/32" docs/03_TASK_INDEX.md  # 修订 5
grep -nE "当前状态.+TASK-301.+TASK-302" docs/03_TASK_INDEX.md  # 修订 6
grep -n "最后更新.*2026-06-05" docs/03_TASK_INDEX.md  # 修订 7
# 期望:7 行各自命中

# 12. 04 § 10 ERROR_MAP 修订(P0-3 fence 边界 + P0-4 PM 例外授权)
grep -nE "error_handlers: tuple\[tuple\[type\[Exception\]" docs/04_ENGINEERING_STANDARDS.md
# 期望:line 552-566 区间命中
grep -cE "^ERROR_MAP = \{" docs/04_ENGINEERING_STANDARDS.md || true
# 期望:0 命中(旧 dict 字面已清)

# 13. lifespan / dependencies 未动验证(D2 范围边界)
git diff main -- api/main.py api/dependencies.py
# 期望:空输出

# 14. core/interfaces/embedder.py 未动验证(D2 范围边界)
git diff main -- core/interfaces/embedder.py
# 期望:空输出
```

### 11.3 PR 元信息

- PR 标题:`TASK-301: sentence-transformers 嵌入适配器(Week 3 起步)`
- 分支名:`task/TASK-301-embedding-adapter`
- PR 描述按 04 § 3 模板 + 逐条勾选 11.2 验收 14 条 + R1 反馈采纳清单(3 P0 + 5 P1 + 4 P2 + 反例 27 入仓)

---

## 风险与决策日志摘要

### 12.1 风险与注意点

**R1 sentence-transformers + transitive deps 包体积**

torch + transformers + tokenizers + sentence-transformers 合计 ~1GB(含 CUDA 库即使 device=cpu)。CI 首次 install 5-10min,后续 pip cache 复用快速。规避:已配置 `cache: 'pip'` + `cache-dependency-path: requirements-dev.txt`(实地核查 ci.yml line 13-16);本 Task 不改 CI 配置。

**R2 HuggingFace Hub 首次下载失败(网络瞬态)**

首次跑 integration test 或生产部署首次启动需下载 ~100MB 模型。sentence-transformers 库自身有 retry + cache 机制。失败时 `__init__` 直接抛 sentence-transformers 异常,调用方负责 catch(本 Task 不在 lifespan,无 catch 需求;TASK-302/304 装配时引入 `EmbeddingModelLoadError`)。规避:README 明示离线开发用 `HF_HUB_OFFLINE=1` ENV;integration test 用 `RUN_EMBEDDING_INTEGRATION=1` opt-in 隔离 CI 风险。

**R3 mypy 严格检查 sentence-transformers stubs 缺失(P1-3 已规避)**

`sentence-transformers` 库官方无 mypy stubs。本 Task § 9.11 直接加 `[[tool.mypy.overrides]] module = "sentence_transformers.*"` + `ignore_missing_imports = true`,**不**留给 Codex 决策。Stage 0 #15 实地核查 main HEAD pyproject.toml 无此 override 后,patch 安全 append。

**R4 numpy / torch 数值类型与 Python list 精度转换**

`encode(convert_to_numpy=True)` 返回 `np.ndarray[float32]`,`.tolist()` 转 Python `list[float]`(float64)— 精度提升,无损。TASK-302 实施时若需 float32 精度可改 `convert_to_numpy=False` + `.cpu().numpy().tolist()`(超本 Task 范围)。

**R5 默认 device="cpu" 在 GPU 服务器浪费**

生产若有 GPU,默认 cpu 推理慢 10-50x。规避:`.env.example` 明示 `EMBEDDING_DEVICE=cpu` 默认 + 注释;README 同步。生产部署文档(TASK-405)再扩展。

**R6 反例 26 + 反例 27 字节级追加遇 emoji / 中文字面编码漂移**

反例 26 / 27 段含中文段落(无 emoji,无 `\s` 字面)。Python 字符串内仅普通中文 + 反引号 + 半角符号。规避:字节级 Python `read_bytes / write_bytes`(决策 08);PM 验收 `git diff` 看反例 26 / 27 段字符正确。沿用反例 21-25 同款模板,已在项目 5 次验证稳定。

**R7 04 § 10 fence 边界替换不稳(P0-3 已规避)**

§ 9.5.3 patch 用 `data.find(START_MARK)` + `data.find(END_MARK, start + len(START_MARK))` fence 边界查找,任一 -1 立即停手(双 assert)。**Codex 实施前 Stage 0 #14 必须实地 `sed -n '552,566p' docs/04_ENGINEERING_STANDARDS.md`** 确认 START_MARK 字节级一致(尤其 `\n` 字面 + `# api/middleware/error_handler.py\nERROR_MAP = {\n` 全字符)。

**R8 测试 mock SentenceTransformer 类的全模块 path 漂移**

`mocker.patch("adapters.embedding.sentence_transformer.SentenceTransformer")` 必须精确匹配 import path。若 adapter 改 `from sentence_transformers import SentenceTransformer` 为 `import sentence_transformers` + `sentence_transformers.SentenceTransformer`,mock path 失效。规避:adapter 用 `from sentence_transformers import SentenceTransformer` 直接 import(§ 9.1 锁定),unit test 同步 patch 路径。

**R9 RUN_EMBEDDING_INTEGRATION env 变量在 CI 上不当被设(理论风险,P0-1 规避)**

若未来 CI 配置漂移把 `RUN_EMBEDDING_INTEGRATION=1` 加进 ci.yml env 段,integration test 会在 CI 真实跑触发 100MB 下载。规避:env 变量名足够独特(`RUN_EMBEDDING_INTEGRATION` 而非 `INTEGRATION_TEST` 通用名);决策 09 反例 27 + 第十七任 KPI 提示后续架构师"工具默认行为陈述前 cat 配置文件"防类似踩坑;Stage 0 #15 + #16 实地核查 main HEAD pyproject.toml + ci.yml 不含此 env 后 patch 安全。

### 12.2 决策日志摘要(D1-D8,详见 § 决策日志)

| D | 决策 | 一句话 |
|:--:|---|---|
| D1 | 一审 1 轮 | 反例 18 自检 5 维度全低;R1 conditional pass |
| D2 | 范围窄:不动 lifespan | TASK-302/304 装配,避免 CI 触发真实模型下载 |
| D3 | adapter __init__ 接收所有运行时值 | 类比 DeepSeek,决策 06 模块封装 |
| D4 | __init__ 同步加载 | 接口同步;调用方负责 to_thread 桥接(决策 11) |
| D5 | 不引入 EmbeddingError | 无 lifespan / 无消费场景,TASK-302/304 引入 |
| D6 | AppSettings 3 字段 | KISS;不暴露 cache_dir |
| D7 | **P0-1 修订**:unit mock + integration **RUN_EMBEDDING_INTEGRATION=1 env skipif** | 本 Task 范围 opt-in,不动全局 addopts |
| D8 | **P0-4 PM 例外授权**:搭车 4 项(反例 26 + **27** + 03 索引 + 04 § 10) | 沿用字节级 Python 模板;PM 一次性显式授权 docs/04 修订 |

### 12.3 后续 Task 接力点

- **TASK-302**(SQLite 向量存储 + 检索):消费 `SentenceTransformerEmbedder.embed()` + `dimension()`;lifespan 装配 `app.state.embedder = await asyncio.to_thread(SentenceTransformerEmbedder, ...)`;`api/dependencies.py` 加 `get_embedder()`;引入 `EmbeddingModelLoadError(MxaError)` + ERROR_MAP handler
- **TASK-303**(chunk 策略):构建带 metadata 的 chunk,供 TASK-302 embed + index
- **TASK-304**(向量 RAG 整合):消费 TASK-302 向量检索,集成进 ChatService
- **Phase 2**:GPU 部署支持 / 模型升级 / 离线分发(`embedding_cache_dir` 字段)

### 12.4 Phase 2 候选

- 加 `embedding_batch_size` AppSettings 字段(大工程批量优化)
- 加 `embedding_max_seq_length` AppSettings 字段(长 chunk 截断)
- 多 embedder 模型并存
- 评测脚本集成 embedding 召回率指标
- embedder 单例池(多 worker 模式)

---

## Stage 0 实地核查清单(给 Codex 跑)

> 决策 09 纪律 1 + 反例 24 / 25 / 26 / **27** 教训。**架构师本地实测每条 grep 命令的输出再写**。
>
> **所有 grep 用 POSIX 字符类**(反例 25 KPI)。**所有 pytest / mypy / ruff 行为陈述前 cat pyproject.toml**(反例 27 KPI)。

实施前 Codex 跑以下 **16** 条核查,任一不符停手抛冲突给 PM:

```bash
# 1. EmbeddingProvider 抽象签名实地核查(本 Task 不动)
cat core/interfaces/embedder.py
# 期望:含 `embed(self, texts: list[str]) -> list[list[float]]` + `dimension(self) -> int` 两个 abstractmethod

# 2. DeepSeek adapter 类比 anchor(本 Task 实现模式照抄)
head -30 adapters/llm/deepseek.py
# 期望:`__init__(api_key, base_url, model, retry_count)` 模式 + 模块级 DEFAULT_* 常量

# 3. app/config.py AppSettings 字段分组
cat app/config.py
# 期望:含 `# LLM` 段 + `deepseek_api_key` + `# Storage`;**不**含 `embedding_*`

# 4. .env.example 现有字段命名风格
cat .env.example
# 期望:含 `DEEPSEEK_API_KEY` + `LOG_LEVEL=INFO`;**不**含 `EMBEDDING_*`

# 5. requirements.txt 现状
cat requirements.txt
# 期望:8 条 deps,**不**含 `sentence-transformers`

# 6. **反例 26 KPI 硬执行:hygiene 脚本 6 条规则**
cat scripts/check_repo_hygiene.sh
cat scripts/check_repo_hygiene.py
# 期望:6 条规则全列;Codex 实施前确认 adapter/.py 不含 print/TODO/裸except

# 7. lifespan 不动验证
head -100 api/main.py
# 期望:lifespan 内 `app.state.text_provider = DeepSeekTextProvider(...)`

# 8. dependencies 不动验证
cat api/dependencies.py
# 期望:含 `get_text_provider` + `get_settings`;**不**加 `get_embedder`

# 9. **反例 26 KPI 硬执行:make check 全管道对齐 CI**
cat .github/workflows/ci.yml
cat Makefile
# 期望:ci.yml 5 step ≡ Makefile `check: lint type-check test hygiene` 4 target

# 10. tests/adapters/embedding/ 当前不存在
ls tests/adapters/
# 期望:含 `llm/ parser/ storage/`;**不**含 `embedding/`

# 11. tests/adapters/llm/conftest.py 类比 mock fixture 模式
cat tests/adapters/llm/conftest.py
# 期望:含 pytest fixture 模式

# 12. 决策 09 末尾形态(反例 26 / 27 入仓前确认未在)
tail -80 docs/decisions/20260603-09-architect-must-verify-not-assume.md
# 期望:含反例 25 + KPI 三条;**不**含 `反例 26` / `反例 27` / `第十六任 KPI` / `第十七任 KPI` 字面

# 13. 03 索引 7 行字面 anchor 实地核查
sed -n '119,121p' docs/03_TASK_INDEX.md  # 修订 1
sed -n '177p' docs/03_TASK_INDEX.md       # 修订 2:TASK-301 当前 🔲
sed -n '338,339p' docs/03_TASK_INDEX.md   # 修订 3+4
sed -n '342p' docs/03_TASK_INDEX.md       # 修订 5
sed -n '349p' docs/03_TASK_INDEX.md       # 修订 6
sed -n '354p' docs/03_TASK_INDEX.md       # 修订 7
# 期望:121 TASK-207 🔍;177 TASK-301 🔲;338 Week 2 6/7;339 Week 3 [⬜x7];342 17/32;349 "下一步: TASK-203";354 2026-06-01

# 14. 04 § 10 ERROR_MAP fence 边界 anchor(P0-3)
sed -n '550,570p' docs/04_ENGINEERING_STANDARDS.md
# 期望:line 552 含 ``` 围栏开头 + `# api/middleware/error_handler.py` + `ERROR_MAP = {`
#       line 566 附近含 ``` 围栏结尾;**实际围栏是 3 反引号,不是 4**(P0-3 修订确认)

# 15. **反例 27 KPI 硬执行**:pyproject.toml 当前状态
cat pyproject.toml
# 期望:[tool.pytest.ini_options] 仅含 testpaths + asyncio_mode,**不**含 addopts / markers;
#       [tool.mypy] 仅含 python_version + strict + warn_unused_ignores + disallow_untyped_defs,
#       **不**含 [[tool.mypy.overrides]];
#       [tool.ruff] line-length=100 + target-version=py311

# 16. requirements-dev.txt 仍引用 requirements.txt
head -2 requirements-dev.txt
# 期望:第 1 行 `-r requirements.txt`(P1-3 衍生核查:TASK-301 加 runtime dep 后,dev 测试需通过传递引用获得)
```

任一不符停手抛冲突给 PM,**不要硬上**。

---

## Checklist(精简)

**实施前**:已读 5 核心文档 + 决策 04/05/06/07/08/09/11 + 反例 1-25(反例 26 + 27 本 Task D8 入仓);实地核查 `core/interfaces/embedder.py` + `adapters/llm/deepseek.py` + `app/config.py` + `.env.example` + `requirements.txt` + `pyproject.toml`(**反例 27 KPI**)+ `api/main.py` + `api/dependencies.py` + `scripts/check_repo_hygiene.{sh,py}`(**反例 26 KPI**)+ `.github/workflows/ci.yml` + `Makefile`(**反例 26 KPI**)+ 03 索引 line 119-121/177/338-339/342/349/354 + 04 § 10 line 552-566;理解 D2 范围窄 + D3 不读 AppSettings + D4 同步加载 + D5 不引入异常 + D7 skipif env + D8 PM 例外授权 + 搭车 chore 4 项。

**完工前**:§ 11.2 验收 1-14 全过(**特别注意 #4 make check 全管道,反例 26 KPI**;**#5 unit + integration skip 验证,反例 27 KPI**);commit subject 单行无 body(反例 17);完工三件套(决策 08);反例 26 + 27 入仓决策 09 + 03 索引 7 行 + 04 § 10 + pyproject.toml 修订五项字节级 Python;PR(Codex 给 PM 标题 + 正文)。

---

**版本**:v0.2(R1 conditional pass / 3 P0 + 5 P1 + 4 P2 全采纳 + 反例 27 入仓 / 不升 R2 / 直接进 Codex)
**日期**:2026-06-05
**作者**:Claude(架构师,第十六任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / `20260604-11`
**关联反例**:**反例 26 + 反例 27**(本 Task D8 治理 chore 入仓决策 09)+ 反例 24 同源(04 § 10 ERROR_MAP dict 字面 → tuple 历史漂移,本 Task D8 搭车修)
**审批历史**:R1 conditional pass(20260605,3 P0 + 5 P1 + 4 P2 全采纳)→ 直接进 Codex
**审批**:**一审 1 轮**(若实施期出现"改 schema / 推翻 D2 范围 / lifespan 装配 / 引入新依赖外 deps / EmbeddingError 异常类 / GPU 默认配置 / 推翻 P0-1 skipif env / 推翻 P0-3 fence 边界替换 / 推翻 P0-4 PM 例外授权"等任一,**必须自动升 R2**)
**前置 commit**:main HEAD `b5b2271`(TASK-207 merge)
