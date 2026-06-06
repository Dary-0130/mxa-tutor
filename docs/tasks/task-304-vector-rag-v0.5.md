# TASK-304: 向量 RAG 整合到 ChatService(Week 3 第 4/7)

## 状态

🟢 v0.5.1(**最终版**,R3 0 P0 + 2 P1 + 4 P2 全采纳;进 Codex 第二棒)

---

## R1 反馈台账(2026-06-07,GPT Pro 8 P0 + 3 P2 全采纳)

> **R1 主判定**:v0.2 方向稳定(VectorRetriever / HybridRetriever / lifespan 单例 / 8 类 Literal 扩 / 4 fallback_reason 枚举 全部保留);**8 P0 全部精修边界 + 跨段一致性 + 工具默认行为类反馈**;0 业务设计漏洞。**5 处架构师自查漏抓**已声明,触发第二十一任 KPI 候选升级。

### 8 P0 必改(全采纳)

| # | 问题 | v0.3 修订位置 | 反例溯源 |
|:-:|---|---|---|
| **P0-1** | 真实 embed 失败不进 fallback:VectorRetriever 假设 EmbeddingProvider 抛 EmbeddingError,但 `adapters/embedding/sentence_transformer.py::SentenceTransformerEmbedder.embed` (line 69) **不 wrap raw exc**;`model.encode()` 原始异常会穿透 HybridRetriever 的 catch `(VectorStoreError, EmbeddingError)`,跑到 ChatService 抛 500 而非 fallback | § 接口契约 2 VectorRetriever.search 加 try/except wrap:`try: embeddings = await asyncio.to_thread(...) except EmbeddingError: raise except Exception as exc: raise EmbeddingError(f"embed_failed:{type(exc).__name__}") from exc`;**KPI b 兑现** — 本任本地闭环,不转嫁 TASK-301 改 wrap(那是 TASK-301 内部实现细节);验收 #X 新增"真实 embed raw exc → 被 wrap 成 EmbeddingError" | **反例 24 + 反例 31 KPI b 同源**(我假设 TASK-301 wrap,未实地核查 line 69;转嫁给 TASK-301 是错的,本任能闭环)|
| **P0-2** | Stage 0 #10 grep 误报:`grep -nE 'file\|block\|function\|param\|graph_entry\|unresolved'` 会命中普通 prompt 文案的 `{source_block}` / `block` 词(qa_with_context.yaml line 21 / 41),不是 source_type 枚举字面;期望"0 行 PASS"必失败 | § Stage 0 #10 大重写:**改 Codex `cat core/prompts/qa_with_context.yaml` 全文 + 人工判断**是否含 source_type **枚举字面集合**(典型形态如 "可选值:file / block / function / param / graph_entry / unresolved" 或 yaml list);命中枚举集合 → 触发 hot-patch;命中普通词 → PASS | **反例 25 同源**(grep 写松必误报;严格 grep "枚举集合" 形态难写,改人工判断)|
| **P0-3** | 文件数仍不准:`tests/features/chat/conftest.py` 当前**不存在**(Codex 第一棒未核查),文档把它放"修改文件"说"追加"错;`api/dependencies.py` 零变更也算进修改 9 个 | § 输出重整:**新增 6 个**(_vector_retriever / _hybrid_retriever / 3 个测试 + **tests/features/chat/conftest.py 新建**);**修改 7 个**(_retriever.py / __init__.py / api/main.py / app/config.py / .env.example / features/chat/README.md / docs/03_TASK_INDEX.md;**去掉 api/dependencies.py**)| **反例 24 + 反例 30 同源**(第一棒漏让 Codex 核查 conftest.py 存在性 + 机械数数把零变更算入修改)|
| **P0-4** | fallback 字段名跨段不一致:P2-12 + D2 + D11 + 验收 #12-#15 文字描述用 `fallback_reason=...`;**但示例代码内 `logger.info(... reason=...` 用 `reason=`**(line 624 + 验收 grep 也查 `reason=...`);TASK-306 评测 grep 口径分裂 | § 接口契约 3 示例代码 `reason=` → `fallback_reason=`(关键字参数名 + log message 全统一);验收 #12-#15 + #24 grep 关键字 `reason=` → `fallback_reason=` | **反例 29 严重命中**(跨段一致性失败;我 v0.2 自查 grep fallback_reason 只看 4 段命中,没看示例代码内 reason 字面)|
| **P0-5** | 日志敏感字段 grep 守门漏 chunk_id / chunk_text:反馈台账 + D12 + R 段都禁这俩字段,但验收 #24 grep 只查 query/question/source_text/answer/{exc}/repr/str,**漏 chunk_id\|chunk_text** | § 验收 #24 grep 扩:`'logger\.(exception\|debug\|info\|warning\|error\|critical).*(query\|question\|source_text\|chunk_text\|chunk_id\|answer\|\{exc\}\|repr\(exc\)\|str\(exc\))'`;D12 显式列出全部禁列字段 | **反例 30 严重命中**(D12 vs 验收 grep 跨段同步漏;第十八任反例 29 KPI 没有兑现)|
| **P0-6** | 示例代码 ruff F401 风险:`from core.domain.exceptions import EmbeddingError, VectorStoreError` 但 `VectorStoreError` 只在 docstring 提到,代码实际未引用;`pyproject.toml [tool.ruff.lint] select = ["E", "F", "I", "B", "UP", "SIM"]` 会抓 F401 | § 接口契约 2 示例 `import` 删 `VectorStoreError`(本任 VectorRetriever 不 catch / 不 raise VectorStoreError;只 HybridRetriever 引用) | **反例 25 + 反例 27 同源**(ruff 默认行为类 — 在 v0.2 时已经知道 pyproject.toml 配 F 规则,但写示例代码时凭印象写了 unused import)|
| **P0-7** | HybridRetriever 类型设计前后不一致:示例 `__init__(vector: VectorRetriever, keyword: KeywordRetriever, ...)`(具体类),但 R9 写"只绑定 Retriever ABC"(ABC 类型);影响 mock 单测 + Phase 2 替换 | § 接口契约 3 `__init__` 类型 hint 改 `vector: Retriever, keyword: Retriever`(ABC);R9 描述对齐 | **反例 29 严重命中**(跨段一致性失败;__init__ 签名 vs R9 描述不一致)|
| **P0-8** | overview sentinel `__project_overview__` 透传本任未闭环:TASK-303 P2-3 提醒"TASK-304/前端不要渲染为可点击文件路径",但 v0.2 VectorRetriever `_to_retrieval_hit` 直接 `chunk.file_path` → SourceRef;前端拿到 SourceRef 后看不到 source_type(API citation 不带 source_type)→ 无强类型识别哨兵 | **PM 拍板 A:本任不改 ChatResponse / 不改 SourceRef**;明示 sentinel 透传是 **TASK-307 证据强制器** + **TASK-403 前端**的两方责任;本任只确保:(a) `chunk.file_path == "__project_overview__"` 时正常透传到 SourceRef.file_path(单测守门);(b) 验收 #X 新增"哨兵透传 + RetrievalHit.source_type == 'overview' 可识别"双重锚点;(c) 给下游 TASK-307 / TASK-403 留下识别路径(source_type 强类型 + file_path 字面双校验);R12 新增"前端识别脆弱"风险声明 | **新维度** — 跨 Task 责任边界默认推给下游,与反例 31 KPI b 同源;PM 拍板 A 后本任内闭环识别路径,不扩 ChatResponse |

### 3 P2 必改(全采纳)

| # | 问题 | v0.3 修订位置 |
|:-:|---|---|
| **P2-1** | api/main.py 的 import 变更没有明确列出;当前只 import KeywordRetriever,task 直接实例化 VectorRetriever / HybridRetriever 会 NameError | § 修改文件 api/main.py 行 + D10 显式列出新增 import:`from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever`(沿用 __init__.py re-export);删除任何旧的 `from features.chat._retriever import KeywordRetriever` 单点 import(若有)|
| **P2-2** | 真实 SQLite 集成测试缺 project row 前置:`SqliteVectorStore.add_chunks` 校验 project 存在(SqliteProjectStore.save_project),验收 #19 没说前置创建 project_status_record → ProjectNotFoundError | § 验收 #19 + #20 加 fixture 链路明示:**SqliteProjectStore.save_project + mark_ready 先建 project_status_record**,再 ChunkingService 灌 chunks;`tests/features/chat/conftest.py` 提供 `real_project_with_chunks` fixture(整合 SqliteProjectStore + SqliteVectorStore + ChunkingService 真实链路) |
| **P2-3** | "mypy strict" 验收不可复现:`pyproject.toml [tool.mypy] strict = false`,Makefile 只跑 `mypy core/ adapters/ features/`;验收口径无可执行命令 | § 验收 #30 改 `mypy features/chat/`(沿当前 strict=false 配置,不引入新配置;反例 27 KPI 兑现 — 工具默认行为类陈述前必须 cat 工具配置);**不改 pyproject.toml**;若 Codex 实施时发现 mypy 报 error 来自上游 main 已有问题 → 上报 PM 决定是否搭车 fix |

### 架构师自查 KPI 兑现声明(v0.2 → R1 期间漏抓 5 处反例同源)

GPT R1 抓住的 8 P0 中,**5 处是我 v0.2 自审应该抓到的反例同源**:

| # | 反例 | 现象 | 我自审为什么漏抓 |
|:-:|:-:|---|---|
| 漏-1 | 反例 24 + 31 KPI b | 转嫁 TASK-301 wrap raw exc | 依赖假设,**没 cat sentence_transformer.py line 69 实地核查 wrap 逻辑** |
| 漏-2 | 反例 29 严重 | fallback_reason vs reason= 字段名跨段不一致 | grep fallback_reason 只看 4 段文字命中,**没看示例代码内 reason 字面**(grep 范围漏)|
| 漏-3 | 反例 30 严重 | 日志 grep 漏 chunk_id / chunk_text | D12 禁列含这俩,验收 grep 没含 → **D 段 vs 验收段跨段同步漏**(第十八任反例 29 KPI 没兑现)|
| 漏-4 | 反例 29 严重 | HybridRetriever __init__ 类型 vs R9 描述不一致 | 自审签名只看 lifespan 装配 line 263,**没核查 __init__ 类型 hint 与 R9 文字描述跨段一致** |
| 漏-5 | 反例 27 严重 | "mypy strict" 凭印象写,**没 cat pyproject.toml line 15 实地核查 `strict = false`** | 反例 27 同源 — 工具默认行为类陈述前必须 cat 工具配置 |

**第二十一任 KPI 候选升级**(等 v0.3 通过 R2 / Codex 第二棒后,若反例形态稳定 → 升仪决策 09):

- **新维度 KPI**:架构师自审 grep,**必须跨 5 段交叉**(反馈台账 / D 段 / R 段 / 示例代码 / 验收 grep 命令字面)+ **grep 关键字必须精确字符串列表**(`fallback_reason | reason= | chunk_id | chunk_text` 单独 grep,不缩为概念词)+ **任何"工具默认行为"陈述前必须 cat 工具配置实地核查**(反例 27 接续)
- **操作清单**(写完每个 v0.x 终稿前):
  - 1. cat pyproject.toml `[tool.ruff.lint] / [tool.mypy] / [tool.pytest.ini_options]` 验证所有"工具默认行为"陈述
  - 2. 验收段 grep 命令清单逐条与 D 段禁列字段交叉,**关键字必须 1:1 对齐**(D 禁 N 个字段,验收 grep N 个字段)
  - 3. 示例代码内 logger.* / 异常 / 关键字段名 grep,与 D 段 + R 段文字描述对齐
  - 4. **跨段 __init__ 签名 / 字段集 / 类型 hint** 三处描述一致:示例代码 / lifespan 装配 / D 段决策 / R 段风险 / 验收守门 5 处交叉
  - 5. **跨 Task 责任边界** — 任何"上游应 / 下游应 / TASK-XXX 接力" 字面,问"本任真能不闭环吗?",一般答案是"能闭环"

---

## R2 / R2.5 反馈台账(2026-06-07,GPT Pro R2 1 P0 + 8 P1 + 4 P2 + R2.5 预审 6 P1;全采纳)

> **R2 主判定**:v0.3 对 R1 的修订大部分闭环(embed wrap 示例代码 / HybridRetriever ABC 签名 / import 顺序 / 日志 grep 扩 / overview 哨兵透传);**P0-1 D11 段旧措辞反向否定 P0-1 wrap** 是唯一 P0(R 段改了但 D 段没同步 = 反例 31 KPI 3 再次命中);8 P1 全跨段一致性 / 工具默认行为 / API 名称残留。触发 **R2.5 预审**(PM 选 Z 后,Z 专属 5 段落地需要 GPT 复核)。

| R2 # | 严重度 | 问题 | v0.4 修订 | 闭环验收 |
|:-:|:-:|---|---|---|
| P0-1 | P0 | D11 "禁 catch Exception" 反向否定 embed wrap | D11 改"禁静默吞 Exception;catch + re-raise = 翻译,允许" | D11 段 + 示例代码 + §范围 D11 行三处统一 ✓ |
| P1-1 | P1 | `save_project` → `create_pending + mark_ready(project_id, project)` | 验收 #19/#20 / conftest / Codex 提示 #21 全改 | grep `save_project` 仅在 v0.2 反馈台账历史记录残留(合法) ✓ |
| P1-2 | P1 | 双锚点对 TASK-403 不成立(ChatResponse 无 source_type)| §接口契约 5 + R12 + #18c + 示例代码注释全改:"前端只能 file_path 字面识别" | grep "双锚点/前端无需" 仅在 R1 反馈台账历史残留(合法) ✓ |
| P1-3 | P1 | E 类 fallback 泄露 `__project_overview__` | PM 拍 Z:接受;R12 改"已知技术债" | R12 段 + §接口契约 5 + #18c + Codex #17 统一 ✓ |
| P1-4 | P1 | D2 "持有 VectorRetriever + KeywordRetriever" 旧描述 | D2 改 "持有 vector: Retriever + keyword: Retriever(ABC 类型)" | grep "VectorRetriever + KeywordRetriever" = 0 ✓ |
| P1-5 | P1 | 日志级别 D11 "warning" vs 示例 "info" | §范围 D11 行 + D11 段统一 `logger.info` | grep "log warning" 仅在反馈台账残留 ✓ |
| P1-6 | P1 | import 顺序触发 ruff I001 | 示例代码 stdlib → 第三方(loguru)→ 本地 | 两个示例段均对齐 ✓ |
| P1-7 | P1 | #18a "invalid query" 不可操作 | 改 monkeypatch `_model.encode` 抛 RuntimeError | #18a 文本已更新 ✓ |
| P1-8 | P1 | #34 grep `v0\.3` 自伤 | v0.4 移除验收 #34 | #34 标注已删除 ✓(v0.5 整段移除) |
| P2-1 | P2 | 不动文件列 `_keyword_scorer.py` 不存在 | 删除该行 | grep = 0 ✓ |
| P2-2 | P2 | 关联文档路径下划线 vs 点号 | 改 glob `task-205-*.md` / `task-303-*.md` + Codex 实地确认 | ✓ |
| P2-3 | P2 | hot-patch 版本号混用 | 统一 "hot-patch" | grep `v0.2.1\|v0.3.1` = 0 ✓ |
| P2-4 | P2 | commit 5 conftest "追加" | 改 "新建" | ✓ |

**R2.5 预审追加**(PM 选 Z 后 GPT 复核;**原 6 P1 中 P1-2/P1-3 已并入 R2 表 P1-2/P1-3 不单列;下表实列 4 行**):

| R2.5 # | 严重度 | 问题 | v0.4 修订 | 闭环验收 |
|:-:|:-:|---|---|---|
| P1-1 | P1 | Z 选择没有 5 段落地动作 | R12 / §接口契约 5 / #18c / 示例代码注释 / Codex #17 全按 Z 修订 | 见 R2 P1-2 / P1-3 ✓ |
| P1-4 | P1 | #18b `inspect.signature` 被 future annotations 绊倒 | 改 `typing.get_type_hints` | #18b 文本已更新 ✓ |
| P1-5 | P1 | D12 `hit_count` vs 示例 `chunk_hit` | 示例改 `hit_count=` | grep `chunk_hit` = 0 ✓ |
| P1-6 | P1 | D10 text_provider 顺序 | 加注释"不参与 #26 守门" | D10 step 4 已标注 ✓ |

---

## R3 反馈台账(2026-06-07,GPT Pro R3 0 P0 + 2 P1 + 4 P2;全采纳 → v0.5 最终版)

> **R3 主判定**:v0.4 对 R2 大部分实质问题已扎实闭环;无 P0;2 P1 = R2/R2.5 台账缺失 + R12 技术债归属写错;4 P2 = grep 口径 / #34 残留 / 版本号残留 / R1 台账历史。**修完 2 P1 后可进 Codex 第二棒**。

| R3 # | 严重度 | 问题 | v0.5 修订 |
|:-:|:-:|---|---|
| P1-1 | P1 | R2/R2.5 闭环台账缺失 | **本段即是**(上方 R2/R2.5 台账 + 逐条闭环验收映射)|
| P1-2 | P1 | R12 技术债归属写错:TASK-403 前端无法修 backend answer | R12 技术债清单改:"消解落到 **backend ChatService / `_chat_persist.py`** 或后续 backend task;TASK-307 只解决强类型识别" |
| P2-1 | P2 | #23 grep 口径不够准 | 改两个守门:禁直接调用 + 要求存在 `asyncio.to_thread(self._embedder.embed` |
| P2-2 | P2 | #34 旧 grep 块仍留 | 整段移除(不只标注删除)|
| P2-3 | P2 | Stage 0 残留 "v0.3 finalize" | 去掉版本号 |
| P2-4 | P2 | R1 台账 `save_project` | 保留(历史记录原文,不修);Codex 第二棒不应 grep 反馈台账执行 |

---

## v0.2 反馈台账(2026-06-06,Codex Stage 0 + GPT instant 预审)

> **工艺说明**:本任 v0.1 → v0.2 之间**两份反馈合并处理**:① Codex 第一棒 Stage 0 实地核查(2 FAIL = 反例 24 / 29 同源)+ ② GPT-5.5 instant 预审(4 P0 + 7 P1 + 3 P2,因 GPT Pro 限额未恢复)。GPT instant **不算正式二审**,但反馈质量等同 P0 / P1 处理;**正式 R1 等 GPT Pro 解锁后过**。

### Codex Stage 0 实测反馈(2 FAIL + 1 重要发现)

| # | 反馈 | v0.2 修订位置 | 反例溯源 |
|:-:|---|---|---|
| **#4 FAIL** | `SqliteVectorStore.query` 路径**也会**抛 `ValueError("invalid top_k")` / `ValueError("invalid min_score")`(_validate_query_args 内,line 219/221);v0.1 § 输入 § 2 写"ValueError 仅 add_chunks 路径"不准确 | § 输入 § 2 修订"`query` + `add_chunks` 两路径都可能抛 `ValueError`,本任 HybridRetriever **不 catch ValueError**(那是编程错误);VectorRetriever 自身在 search 前预校验 top_k / min_score" + D11 加显式声明 | 反例 24(凭印象写,未实地核查 sqlite_vector_store.py 行为)|
| **#5 FAIL** | 草稿多处写 `features/chat/service.py`,实际文件名 `features/chat/chat_service.py`(v0.1 line 204 / 922 / 1072 / line 132 + 145 含 Claude 幻觉预写的"v0.1.1 修订"注释,跨段不一致)| 全文 grep `service\.py` 改 `chat_service.py`;**v0.1 line 132 / 145 / 1122 / 1177 的"v0.1.1 修订"注释删除**(那是 Claude create_file 时**幻觉预写未来注释**,不是真实修订记录)| 反例 24 + **反例 29**(同一路径多段写不一致;且 Claude **幻觉预写未来状态** = 反例 24 新维度)|
| #6 关键发现 | 当前装配模式 = **lifespan 单例**(`get_chat_service` 仅 `getattr(request.app.state, "chat_service", None)`,无 Depends 组装);KeywordRetriever 在 api/main.py lifespan **内联构造**(line 106 `KeywordRetriever(graph_provider=ProjectGraphBuilder())`);ProjectGraphBuilder() 两处内联(line 94 给 ChunkingService,line 106 给 KeywordRetriever);12 个 DI 函数 | **D9 + D10 大改**:本任装配方案锁定 **lifespan 单例模式**(P0-1 决策);`api/dependencies.py` **零变更**;从修改文件清单去掉 | 实测发现,影响 P0-1 |

### GPT-5.5 instant 预审反馈(4 P0 + 7 P1 + 3 P2 全采纳)

> **GPT instant 与 GPT Pro 二审差异声明**:本次 GPT Pro 限额未恢复,PM 用 GPT-5.5 instant 做 v0.1 预审;反馈质量与正式 R1 二审有差异(instant 看不到代码深层、可能漏框架默认行为类反馈)。**v0.2 finalize 后仍需 GPT Pro 正式 R1**(预计 2026-06-07 14:00 后);本台账区分"已通过 instant 预审"vs"仍需 Pro 二审"。

| # | 严重度 | 问题 | v0.2 修订位置 | 反例溯源 |
|:-:|:-:|---|---|---|
| **P0-1** | 必改 | DI 装配自相矛盾:v0.1 同时写 lifespan 装配 `app.state.vector_retriever / hybrid_retriever / chat_service` + 在 `api/dependencies.py` 加 `get_vector_retriever / get_hybrid_retriever` DI;两套互斥,Codex Stage 0 #6 实测确认当前是 **lifespan 单例**模式 | § 修改文件 line 180 **删除 api/dependencies.py**(改"零变更");D9 重写"lifespan 单例装配 + ChatService DI 函数零变更";D10 装配顺序明示 KeywordRetriever 从 lifespan 内联抽出存到 `app.state.keyword_retriever`;给 Codex 提示段加"禁创新 DI 函数,沿 task-205 单例模式" | 反例 24(凭印象写两套装配)|
| **P0-2** | 必改 | `vector_top_k` "复用"矛盾:ChatService.handle_chat 调 `top_k=DEFAULT_TOP_K`(line 76-78),不读 `settings.vector_top_k`;D14 又说 top_k 由 ChatService 统一,与 D6 "复用" 冲突 | D6 **删除"复用 vector_top_k"叙事**,改"本任仅复用 `vector_min_score`(走 VectorRetriever.__init__);**不复用** `vector_top_k`(ChatService DEFAULT_TOP_K 控制,本任不引入 top_k 配置链路)";D14 同步修订;§ 输入 § 7 更新陈述 | 反例 29(跨段一致性失败,D6 vs D14)|
| **P0-3** | 必改 | 03 索引补账写 `🔲→✅` 违反治理:Codex 完工 PR 是 🔍 等待验收;✅ 在 review + merge 后由 PM 单独 chore 改;v0.1 让 Codex 自审自批 | § 范围"搭车 chore" + § 风险 R10 + § 验收 #30 全部改 `🔲 → 🔍`;**不写**"TASK-304 完成,启动 TASK-305"(那是 merge 后状态);进度条 [3/7]→[4/7] **不动**(Codex 不改进度条 — 进度条按 ✅ 计;merge 后 PM chore 改);只改 TASK-304 行状态 + 最后更新日期 | 新维度("Codex 自审自批" — 工艺纪律未明示边界)|
| **P0-4** | 必改 | 文件数量统计不准:v0.1 写"新增 6 个"实为 5 个(README.md 追加不算新增);"修改 5 个"实为 6 个 + 漏 features/chat/README.md 和 tests/features/chat/conftest.py | § 输出重整:**新增 5 个**(_vector_retriever / _hybrid_retriever / 3 个测试)+ **修改 9 个**(_retriever.py / __init__.py / api/main.py / app/config.py / .env.example / features/chat/README.md / tests/features/chat/conftest.py / docs/03_TASK_INDEX.md);api/dependencies.py 从修改清单去掉(P0-1)| 反例 30(机械数数错;第十八任 task-108 同源)|
| **P1-5** | 改 | Stage 0 标题写"以下 8 项"实际 #1-#9 | § Stage 0 标题改"以下 9 项" + 加 #10(prompt yaml 核查,P1-11)= 共 10 项 | 反例 30(机械计数错)|
| **P1-6** | 改 | VectorRetriever 示例代码 ruff/mypy 风险:`from dataclasses import dataclass` + `ChunkRecord` import 未消费;"优雅降级"注释与 `raise ValueError` 实现矛盾 | § 接口契约 2 示例代码:删 `dataclass` import 和 `ChunkRecord` import(未消费);**删除"优雅降级"注释**,保留 `raise ValueError`;与 D4 决策"抛 ValueError 不静默"对齐 | 反例 29 同源(代码注释与代码实现跨段不一致)|
| **P1-7** | 改 | `min_score` 没 `__init__` 预校验,只校验 top_k;`VectorRetriever(min_score=2.0)` 错误构造仅在 search 时才暴露 | § 接口契约 2 `__init__` 加 `if min_score < -1.0 or min_score > 1.0: raise ValueError("min_score out of range")`;验收 #6 扩 min_score 边界 | 反例 24(凭印象认为 top_k 校验够,没全面检查所有参数边界)|
| **P1-8** | 改 | `mat_variable → "param"` 但 `SourceRef.parameter_name=None` 丢变量名:`chunk.symbol_name`(.mat var name)未透传到 SourceRef.parameter_name → citation 层面只剩 file_path,变量名要靠 snippet | § 接口契约 4 映射表 + 示例代码:`parameter_name = chunk.symbol_name if mapped_type == "param" else None`;验收 #X 加守门 | 反例 29(D4 映射表 + SourceRef 字段映射表两段未对齐)|
| **P1-9** | 改 | 日志守门 grep 漏 `warning/info`:D12 禁所有 logger level 泄露 query/source_text/answer/chunk_id,但验收 #21 grep 只查 `exception/error`;本任主要用 `warning/info` | 验收 #21 grep 改:`logger\.(exception\|debug\|info\|warning\|error\|critical).*(query\|question\|source_text\|answer\|chunk_id\|\{exc\}\|repr\(exc\)\|str\(exc\))`;白名单字段在 D12 显式列出 | 反例 30(grep 范围漏)|
| **P1-10** | 改 | Integration #18 "至少 1 个非 block citation" flaky:真实向量检索受模型 / chunk 内容 / query 文案 / min_score 影响,top_k 里可能全是 slx_block 或全是 overview | 拆 2 个测试:**单元** #X 用 MockEmbeddingProvider 可控 chunks(注入 slx_subsystem + project_overview)→ 强制召回非 block → 断言 ChatService 透传不丢;**集成** #18 改"返非空 + source_type 在 8 类内 + citation 不为空",**不强制具体类型** | 反例 31 KPI e 同源(测试断言过强会造成 flaky → 间接成为循环论证)|
| **P1-11** | 改 | "不改 prompt yaml" 应先核查:v0.1 直接断言 prompt 是字符串透传,未实地核查 `core/prompts/qa_with_context.yaml` 是否写死了 source_type 枚举说明 | § Stage 0 加 **#10**:`grep -nE 'file\|block\|function\|param\|graph_entry\|unresolved\|source_type\|来源类型' core/prompts/qa_with_context.yaml`;通过(无枚举字面)→ 保留"不改 prompt yaml";命中(有枚举字面)→ 触发 hot-patch,prompt yaml 同步加 "subsystem" / "overview" 类型描述 | 反例 24(凭印象认为 prompt 不感知 source_type)+ 反例 27(默认行为类陈述前必须实地核查)|
| **P2-12** | 改 | HybridRetriever fallback 日志无结构化 `fallback_reason`,TASK-306 评测难定位 | § 接口契约 3 + D11 固定 4 枚举:`chunk_count_below_threshold` / `get_chunk_count_failed` / `vector_search_failed` / `vector_empty_hits`;`logger.info(... fallback_reason={reason} ...)` 显式输出 | — |
| **P2-13** | 改 | `VectorRetriever.search` 末尾 `logger.info` 每次问答都打,生产可能偏吵 | § 接口契约 2 示例代码 `logger.info` → `logger.debug`;HybridRetriever 的 fallback 路径保留 `logger.info`(关键事件) | — |
| **P2-14** | 改 | `HybridRetriever.search` 每次先查 `get_chunk_count` 多 1 SQL,生产规模大可能性能压力 | § 风险 R11 新增声明这是 trade-off;Phase 2 候选:缓存空 chunk project 标记到 `project_status_record.chunk_ready` 或 app-level cache | — |

### v0.2 我自己跨段一致性自审命中(反例 29 + 30 + 31 KPI 兑现)

**v0.1 自查发现 5 处反例同源**(GPT 没抓到但我自己抓到的也要计入,工艺纪律兑现):

| # | 反例 | 现象 | 自查时机 |
|:-:|:-:|---|---|
| 自-1 | 反例 24 | `service.py` 路径多段写错 + Claude `create_file` 时**幻觉预写"v0.1.1 修订"注释**(凭"未来印象"写而非实地状态)| Codex Stage 0 #5 实测才暴露 |
| 自-2 | 反例 29 | DI 装配 lifespan vs Depends 两段互斥写法 | GPT instant P0-1 抓 |
| 自-3 | 反例 29 | `vector_top_k` 复用叙事 vs ChatService DEFAULT_TOP_K 跨段不一致 | GPT instant P0-2 抓 |
| 自-4 | 反例 30 | 文件数 6+5 / 5+6 / 5+9 三处机械数数错 | GPT instant P0-4 抓 |
| 自-5 | 反例 30 | Stage 0 "8 项" vs 实际 9 项 | GPT instant P1-5 抓 |
| 自-6(新) | **反例 24 新维度** | Claude **`create_file` 时幻觉预写未来注释**(v0.1 line 132 / 145 / 1122 / 1177 含"v0.1.1 修订"字面,但 v0.1 写作时根本没有 v0.1.1 概念)| Codex Stage 0 + 架构师自查 grep 抓 |

**第二十一任 KPI 候选**(等 v0.2 通过 R1 后,若新反例形态稳定 → 升仪决策 09):
- **任何 Claude `create_file` / `str_replace` 生成的文档,finalize 前 grep 是否含"未来版本号"(v0.1.1 / v0.2 / R1 / 第 N 棒 / "已修订")字面;若现版本号 < 该字面提到的版本号 → 触发"幻觉预写未来状态"反例 24 新维度**

---

## 概要

新增 `VectorRetriever`(实现 `Retriever` ABC,消费 `EmbeddingProvider` + `VectorStore`)+ `HybridRetriever`(协调 vector 主路 + keyword fallback,4 种 `fallback_reason` 枚举)。**`ChatService.handle_chat` 流程零变更** — 只在 `api/main.py` lifespan 装配把 `app.state.chat_service` 的 retriever 实例从 `KeywordRetriever(...)` 换成 `HybridRetriever(...)`(沿 task-205 / task-203 已确立的 **lifespan 单例模式**;`api/dependencies.py` **零变更**)。

本任在 Week 3 的位置:**3/7 → 4/7**。前置 TASK-301 / 302 / 303 已 main freeze;下游 TASK-305(教学 Prompt)/ TASK-306(评测)/ TASK-307(证据强制器)依赖本任落地的 RAG 基础设施。

---

## 上下文(在项目里的位置)

- **架构面**:把 Week 1-3 累积的向量基础设施(Embedder + VectorStore + Chunker)接入 Week 2 落地的 ChatService。这是 RAG 流水线最后一步对齐。
- **业务面**:学生提问质量从"关键词命中"升级到"语义相似度";为 TASK-306 评测打底("向量 RAG vs 粗 RAG 准确率明显更高"是 Week 3 验收硬指标)。
- **风险面**:本任是 RAG 链路总成阶段,**任何上游契约误读都会在本任暴露**。Stage 0 实地核查是反例 28 KPI 兑现的关键。

---

## 输入(前置依赖)

### 上游关键契约(已 main HEAD freeze,本任不动)

> **决策 09 反例 28 + 反例 31 KPI 兑现声明**:以下契约本任**不重复验证 TASK-301 / 302 / 303 公共契约**(由各自任的 unit + fault-injection contract test 守门);Stage 0 仅做"接口存在 + 签名一致"实地核查,不做"行为重新验证"(避免循环论证)。

**1. `core/interfaces/embedder.py::EmbeddingProvider`**(TASK-301 落,本任消费)

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...   # 同步,无 async
    @abstractmethod
    def dimension(self) -> int: ...
```

**关键性质**:`embed` 是**同步重活**(sentence-transformers CPU 推理,几十-几百 ms);本任在 async 函数内调用必须 `asyncio.to_thread` 桥接(决策 11 决策 1)。

**2. `core/interfaces/vector_store.py::VectorStore`**(TASK-302 落,本任消费 `query` + `get_chunk_count`)

```python
class VectorStore(ABC):
    @abstractmethod
    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]: ...

    @abstractmethod
    async def get_chunk_count(self, project_id: str) -> int: ...
    # add_chunks / delete_by_project_id / aclose 本任不消费
```

```python
@dataclass(frozen=True)
class QueryHit:
    chunk: ChunkRecord
    score: float
```

**关键性质**(本任硬假设,**TASK-302 已 main freeze + TASK-303 contract test 守门**):
- `chunks=0` / `project_id` 不存在 → `query` 返回 `[]`(不抛 ProjectNotFoundError)
- `top_k ∈ [1, 50]` / `min_score ∈ [-1.0, 1.0]` 外抛 `ValueError`(**v0.2 P0-4 修订**:Codex Stage 0 #4 实测确认 `SqliteVectorStore.query` 内 `_validate_query_args` 抛 `ValueError("invalid top_k")` / `ValueError("invalid min_score")`;**`add_chunks` 也抛 `ValueError("chunk_id already exists")`**;两路径都抛但不同 message)
- `OperationalError → VectorStoreError("sqlite_operation_failed")`(TASK-303 contract test 守门,本任不重测)

**3. `core/interfaces/vector_store.py::ChunkRecord` + `SourceType`**(TASK-303 main freeze 后形态;Codex Stage 0 #3 实测确认)

```python
SourceType = Literal[
    "m_file", "m_function",
    "slx_block", "slx_subsystem",
    "mat_variable",
    "project_overview",
    "teaching_unit",   # reserved,本任永不出现(RESERVED_SOURCE_TYPES 守门)
]

RESERVED_SOURCE_TYPES: Final[frozenset[str]] = frozenset({"teaching_unit"})

@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    project_id: str
    source_type: SourceType
    file_path: str
    symbol_name: str | None
    line_range: tuple[int, int] | None
    block_id: str | None
    block_name: str | None
    block_type: str | None
    parent_subsystem: str | None
    source_text: str
    embedding: list[float]
    model_name: str
    created_at: datetime | None = None
```

**4. `features/chat/_retriever.py`**(TASK-205 落,本任**修改** `SourceType` Literal 扩 6 → 8 类;**不动** Retriever ABC / RetrievalHit 字段集 / KeywordRetriever 类;Codex Stage 0 #1 实测确认)

```python
# main HEAD 当前形态(line 1-30,本任修改 line 15)
from typing import Literal, Protocol

SourceType = Literal["file", "block", "function", "param", "graph_entry", "unresolved"]   # 6 类

@dataclass(frozen=True)
class RetrievalHit:
    source_ref: SourceRef
    score: float
    snippet: str
    source_type: SourceType
    block_type: str | None = None   # 仅 source_type=="block" 时填(TASK-205 R2 P0-2)

class Retriever(ABC):
    @abstractmethod
    async def search(
        self, project: Project, query: str, top_k: int = 8,
    ) -> list[RetrievalHit]: ...

class KeywordRetriever(Retriever):
    def __init__(self, graph_provider: ProjectGraphProvider) -> None: ...
    async def search(self, project, query, top_k=8) -> list[RetrievalHit]: ...
```

**关键性质**:`Retriever.search` 是 `async`;`ChatService` 直接 `await self._retriever.search(...)`,**不**在 ChatService 内 `asyncio.to_thread(retriever.search, ...)`(coroutine 丢线程池硬 bug,TASK-205 R1 P0-2 已锁)。

**5. `features/chat/chat_service.py::ChatService.handle_chat`**(TASK-205 落,本任**零变更**;Codex Stage 0 #5 实测路径修订:**文件名是 `chat_service.py`,不是 `service.py`**)

7 步流程(TASK-205 v0.2 § 6.1 已锁;Codex Stage 0 #5 实测确认 line 51 `self._retriever = retriever` + line 76-78 `retrieval_hits = await self._retriever.search(project, enhance_query(...), top_k=DEFAULT_TOP_K)`):
1. project / session 兜底
2. 取历史
3. append user message
4. **`await self._retriever.search(project, effective_query, top_k=DEFAULT_TOP_K)`** ← 本任只换 `self._retriever` 实例,**不改 `DEFAULT_TOP_K`**
5. 空召回短路(E 类降级)
6. LLM 调用 + `_parse_and_validate`
7. 校验后 citations==[] → E 类降级

**关键性质**:`_parse_and_validate` Step 4 仅对 `hit.source_type == "block"` 计算四元组 `validation_key`,**其他类型 `validation_key=None`,透传无校验**。新增的 `"subsystem"` / `"overview"` 类型不触发 block 校验,语义安全(详 D3 决策)。

**6. `api/dependencies.py::get_chat_service` + `api/main.py` lifespan**(Codex Stage 0 #6 实测,本任**改 lifespan,不改 dependencies**)

**当前形态**(Codex Stage 0 #6 实测):
- `api/dependencies.py` line 138-140:`def get_chat_service(request: Request) -> ChatService:` + `return getattr(request.app.state, "chat_service", None)` — **lifespan 单例模式**,DI 仅取 app.state
- `api/main.py` lifespan line 94:`graph_provider=ProjectGraphBuilder()`(传给 ChunkingService 内联构造)
- `api/main.py` lifespan line 106:`retriever=KeywordRetriever(graph_provider=ProjectGraphBuilder())`(再次内联构造,与 line 94 是独立实例)
- 共 12 个 `def get_*` DI 函数

**本任装配方案**(P0-1 锁定 lifespan 单例):
- `api/main.py` lifespan **改**:把 line 106 内联的 `ProjectGraphBuilder()` 抽出到 `app.state.graph_provider`(避免重复构造);新增 `app.state.keyword_retriever / vector_retriever / hybrid_retriever`;`app.state.chat_service` 的 retriever 改为 `app.state.hybrid_retriever`
- `api/dependencies.py` **零变更**(`get_chat_service` 仍仅取 app.state.chat_service,本任**不新增**任何 DI 函数)

**7. `app/config.py::AppSettings`**(Codex Stage 0 #7 实测,本任**新增 1 字段,不复用 vector_top_k**)

Codex Stage 0 #7 实测确认 line 24-25:
```python
vector_top_k: int = Field(default=8, ge=1, le=50)        # TASK-302 D9 已落
vector_min_score: float = Field(default=0.3, ge=-1.0, le=1.0)   # TASK-302 D9 已落
# chunking_* 6 字段(TASK-303 D7+D8 已落,line 28-33)
# 无 rag_* 字段
```

**v0.2 P0-2 修订**:
- **本任仅复用 `vector_min_score`**(VectorRetriever.__init__ 传入)
- **本任不复用 `vector_top_k`**:ChatService 调 `retriever.search(top_k=DEFAULT_TOP_K=8)`,`vector_top_k` settings 字段对本任**无影响**;不在 lifespan 装配 `top_k=settings.vector_top_k`,避免给后续开发者错觉"配置生效"
- 新增 `rag_min_chunk_count`(详 D6)

**8. `core/domain/exceptions.py`**(TASK-302 D8 已加 `VectorStoreError(StoreError)` / `EmbeddingError(MxaError)` / `EmbeddingModelLoadError`;本任消费 `VectorStoreError` + `EmbeddingError`,不新增异常类)

**9. `features/chat/__init__.py`**(Codex Stage 0 #9 实测,本任**修改** re-export)

当前 line 3-5:
```python
from features.chat._retriever import KeywordRetriever, ProjectGraphProvider, RetrievalHit, Retriever
__all__ = ["KeywordRetriever", "ProjectGraphProvider", "RetrievalHit", "Retriever"]
```

本任改:加 `VectorRetriever` / `HybridRetriever` re-export,`__all__` 同步 6 项(详 D9)。

---

## 输出(交付物)

### 新增文件(6 个;**v0.3 P0-3 修订:tests/features/chat/conftest.py 当前不存在,转新建**)

```
features/chat/
├── _vector_retriever.py            ~150 行,VectorRetriever 实现 + ChunkRecord→RetrievalHit 映射
├── _hybrid_retriever.py            ~120 行,HybridRetriever 协调 fallback + 4 fallback_reason 枚举

tests/features/chat/
├── conftest.py                     ~80 行,新建(v0.3 P0-3 修订;含 mock_keyword_retriever / mock_chunk_record_builder / real_project_with_chunks fixture,P2-2)
├── test_vector_retriever_unit.py   ~250 行,VectorRetriever 单元(映射 / 空召回 / dedupe / to_thread 桥接 / min_score 校验 / wrap raw exc P0-1)
├── test_hybrid_retriever_unit.py   ~180 行,HybridRetriever 单元(4 fallback 路径 + 正常路径 + fallback_reason 守门 + ABC 类型)
├── test_vector_retriever_integration.py   ~150 行,真 SentenceTransformer + 真 SqliteVectorStore 端到端(RUN_EMBEDDING_INTEGRATION=1 skipif;P2-2 含 project row 前置 fixture)
```

预估总 ~930 行,平均每文件 ~155 行,均 < 01 § 8 的 300 行约束。

### 修改文件(7 个;**v0.3 P0-3 修订:去掉 api/dependencies.py 零变更**)

| 路径 | 改动范围 | 决策 |
|---|---|---|
| `features/chat/_retriever.py` | **`SourceType` Literal 6 → 8 类**(line 15 追加 `"subsystem"` + `"overview"`);ABC + RetrievalHit + KeywordRetriever 类**零变更** | D3 |
| `features/chat/__init__.py` | line 3 import 加 `VectorRetriever` / `HybridRetriever`;line 5 `__all__` 同步 6 项 | D9 |
| `features/chat/README.md` | 追加 2 段:VectorRetriever 用途说明 + HybridRetriever fallback 行为说明(~30 行) | — |
| `api/main.py` | **(v0.3 P2-1 修订:显式 import 行)** `from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever`(沿 __init__.py re-export);**删除任何旧的 `from features.chat._retriever import KeywordRetriever` 直接引用 _retriever**;lifespan `AsyncExitStack` 装配链路:抽出 `app.state.graph_provider = ProjectGraphBuilder()` 单实例;加 `app.state.keyword_retriever = KeywordRetriever(graph_provider=app.state.graph_provider)` + `app.state.vector_retriever = VectorRetriever(embedder=app.state.embedder, vector_store=app.state.vector_store, min_score=settings.vector_min_score)` + `app.state.hybrid_retriever = HybridRetriever(vector=app.state.vector_retriever, keyword=app.state.keyword_retriever, vector_store=app.state.vector_store, min_chunk_count=settings.rag_min_chunk_count)`;`app.state.chat_service` 装配时 `retriever=app.state.hybrid_retriever`(替换 line 106 当前的内联 KeywordRetriever)| D10 + P2-1 |
| `app/config.py` | **新增** `rag_min_chunk_count: int = Field(default=1, ge=0, le=100)`;在 `# Vector store` 段后追加 `# RAG retrieval` 段 1 字段;**不动** `vector_top_k` / `vector_min_score` | D6 |
| `.env.example` | 同步加 `RAG_MIN_CHUNK_COUNT=1` 注释 + 默认值 | D6 |
| `docs/03_TASK_INDEX.md` | **搭车 chore**:TASK-304 行 `🔲 → 🔍`(P0-3 修订)+ 最后更新日期同步;**不动**进度条 / 总计 / 当前状态字面 | 搭车 chore |

> **v0.3 P0-3 删除**:v0.2 修改文件清单中 `api/dependencies.py` 零变更项已撤回(零变更不应列入修改清单);现仅作为不动文件参考列在下方。
> **v0.3 P0-3 删除**:v0.2 把 `tests/features/chat/conftest.py` 列在修改文件"追加 fixture",但 Codex 第一棒未核查存在性 → 现转入新增文件(新建)。

### 不动文件(明示)

| 路径 | 不动理由 |
|---|---|
| `core/interfaces/vector_store.py` | TASK-302 + TASK-303 已 main freeze,本任仅**消费** `VectorStore.query` + `get_chunk_count` + `ChunkRecord` + `SourceType` + `QueryHit`,**不改任何签名 / 字段 / Literal 枚举** |
| `core/interfaces/embedder.py` | TASK-301 落地,本任仅消费 `embed` + `dimension`,**不改签名** |
| `core/domain/exceptions.py` | 异常族已齐全(VectorStoreError / EmbeddingError / LLMError),本任消费 |
| `core/domain/source_ref.py` | TASK-101 锁的跨 Task 契约,本任仅**构造** `SourceRef`,不改字段 |
| `adapters/storage/sqlite_vector_store.py` | TASK-302 已 main freeze,**不动**(交接文案硬约束) |
| `adapters/embedding/sentence_transformer.py` | TASK-301 已 main freeze,本任消费 |
| `features/chunking/` | TASK-303 已 main freeze,本任**不消费 chunking_service**,只消费它产出的入库 chunks(通过 vector_store.query) |
| `features/chat/chat_service.py::ChatService` | `handle_chat` 7 步流程 + `_parse_and_validate` 校验五步 + `_build_source_entries` 全部**零变更**;本任只换 retriever 实例(D9) |
| `features/chat/_prompt_builder.py` | LLM prompt 构造,本任不改 |
| `features/chat/_validators.py` / `_chat_schemas.py`(若存在;Stage 0 #1 PASS 未列,Codex 第二棒实施时若发现存在以实际为准)| ChatGenerationError / ChatAnswer / 校验 schema 不动 |
| `features/ingest/upload_service.py` | TASK-303 已挂载 chunking_service,本任不动 |
| `features/overview/overview_service.py` | 同上 |
| `api/routes/chat.py` | API 路由层不变(ChatService 接口不变) |
| `api/middleware/error_handler.py` | 异常翻译表已含 `VectorStoreError`(走父类 `StoreError` handler,500),本任不扩 |
| `api/dependencies.py` | **v0.2 P0-1 修订:零变更**(lifespan 单例模式,不新增 DI 函数) |
| `core/prompts/qa_with_context.yaml` | **条件不动**(v0.2 P1-11 修订):Stage 0 #10 核查通过(无 source_type 枚举字面)→ 不动;若核查命中(prompt 列了 6 类枚举字面)→ 触发 hot-patch,prompt yaml 同步加 "subsystem" / "overview" 类型描述 |

---

## 范围

### 必做(检查清单 D1-D15)

- [ ] **D1 VectorRetriever 实现 Retriever ABC**:`async def search(project, query, top_k=8) -> list[RetrievalHit]`;**embed 调用 wrap raw exc → EmbeddingError**(**v0.3 P0-1**,本任本地闭环)
- [ ] **D2 HybridRetriever 协调 fallback**:也实现 Retriever ABC;4 种 `fallback_reason` 枚举(P2-12);`__init__` 类型 hint 用 `Retriever` ABC,不绑定具体类(**v0.3 P0-7**)
- [ ] **D3 `features/chat/_retriever.py::SourceType` Literal 6 → 8 类**(加 `"subsystem"` + `"overview"`)
- [ ] **D4 ChunkRecord.source_type → RetrievalHit.source_type 映射表**(详 § 接口契约 4;含 P1-8 mat_variable.symbol_name → SourceRef.parameter_name + **P0-8 overview 哨兵透传**)
- [ ] **D5 embed 调用 `asyncio.to_thread` 桥接**(决策 11 决策 1)
- [ ] **D6 AppSettings 加 `rag_min_chunk_count` 1 字段**;**仅复用 `vector_min_score`**(**v0.2 P0-2 修订:不复用 `vector_top_k`**)
- [ ] **D7 snippet 来源 `chunk.source_text` + 防御 `_truncate(300)` cap**(TASK-205 RetrievalHit.snippet ≤ 300 字硬约束)
- [ ] **D8 dedupe 策略**:仅 by-chunk_id 防御性,**不做** by source_ref / by (file_path, block_name)
- [ ] **D9 lifespan 单例装配**(**v0.2 P0-1 修订:不新增 DI 函数**);`features/chat/__init__.py` re-export 6 项
- [ ] **D10 lifespan 装配链路顺序 + 抽出 `app.state.graph_provider` 单实例**;**显式 import 行**(**v0.3 P2-1**)
- [ ] **D11 VectorRetriever embed 路径允许 `except Exception → raise EmbeddingError from exc`(异常翻译,非静默吞)**;**HybridRetriever 内 catch `VectorStoreError` + `EmbeddingError` → 降级 keyword + log info + fallback_reason 枚举**;**禁 catch `ValueError`**;LLMError 不在本任处理范围
- [ ] **D12 日志 metadata-only**(决策 11 决策 2;**v0.2 P1-9 + v0.3 P0-5 修订**:grep 守门覆盖所有 logger level + chunk_id / chunk_text 加入禁列)
- [ ] **D13 min_score 默认 0.3**(对齐 TASK-302 `vector_min_score`);`__init__` 加预校验(**v0.2 P1-7 修订**)
- [ ] **D14 top_k 默认 8**(对齐 ABC 默认值 + ChatService `DEFAULT_TOP_K`;**v0.2 P0-2 修订:本任不引入 top_k 配置**)
- [ ] **D15 集成测试 `RUN_EMBEDDING_INTEGRATION=1` skipif**(对齐 TASK-301 / 303);**集成断言改弱**(**v0.2 P1-10 修订**)+ **加 project row 前置 fixture**(**v0.3 P2-2**)
- [ ] **测试**:Unit(VectorRetriever 映射 / HybridRetriever 4 fallback 路径 / **embed wrap raw exc** / **ABC 类型守门** / **overview 哨兵透传**)+ Integration(真实 RAG 端到端含 project row 前置)+ to_thread 守门 + min_score 边界守门
- [ ] **搭车 chore**:03 索引 TASK-304 行 `🔲 → 🔍`(**v0.2 P0-3 修订:不写 ✅;不动进度条**)

### 不做(明确排除)

- ❌ **不改 ChatService.handle_chat 流程 / _parse_and_validate 校验逻辑**(TASK-205 main freeze)
- ❌ **不改 Retriever ABC 签名 / RetrievalHit 字段集**(只扩 `SourceType` Literal,字段类型 hint 不变)
- ❌ **不改 TASK-303 chunking 链路**(本任只读 chunks 表,不写)
- ❌ **不改 TASK-302 VectorStore ABC / SqliteVectorStore 实现**
- ❌ **不新增 DI 函数**(**v0.2 P0-1 修订**:lifespan 单例模式,沿 task-203 / task-205 既定模式)
- ❌ **不复用 `vector_top_k` settings 字段**(**v0.2 P0-2 修订**:ChatService DEFAULT_TOP_K 控制,settings 字段对本任无效)
- ❌ **不在 03 索引写 `✅`**(**v0.2 P0-3 修订**:Codex 完工只能写 🔍;✅ 由 PM 在 merge 后单独 chore 改;进度条 / 总计 / 当前状态本任不动)
- ❌ **不引入 Reranker**(Phase 2 候选)
- ❌ **不引入 Query Rewriter / HyDE / Multi-Query**(Phase 2 / TASK-305 候选)
- ❌ **不改 LLM prompt yaml**(条件不做;Stage 0 #10 核查通过才生效;命中则 hot-patch)
- ❌ **不删除 KeywordRetriever**(作为 fallback 实例继续装配)
- ❌ **不引入 chunks 表 schema 变更**
- ❌ **不引入向量索引(ANN / IVF / HNSW)**(MCS 单工程规模 < 5000 chunk,02 § 6 决策 1 已锁线性扫描)
- ❌ **不引入 metadata 过滤检索**(SQL WHERE source_type / file_path):Phase 2 / TASK-306 评测后再决定
- ❌ **不引入 streaming retrieval**(VectorStore.query list 返回)
- ❌ **不引入 caching layer**(MCS embed < 100ms,缓存收益不抵复杂度;P2-14 trade-off 见 R11)

---

## 接口契约

### 1. `SourceType` Literal 扩 6 → 8 类(`features/chat/_retriever.py` line 15 修改)

```python
# features/chat/_retriever.py(本任 line 15 修改,其他行不动)
SourceType = Literal[
    "file",
    "block",
    "function",
    "param",
    "graph_entry",
    "unresolved",
    "subsystem",   # ★ D3 新增,slx_subsystem chunk 映射目标
    "overview",    # ★ D3 新增,project_overview chunk 映射目标
]
```

**理由**(D3 完整决策):
- TASK-303 持久化 6 类 source_type(7 类 Literal 含 reserved):`m_file / m_function / slx_block / slx_subsystem / mat_variable / project_overview`
- TASK-205 RetrievalHit.source_type 锁的 6 类是为 KeywordRetriever 设计,无 chunk 维度
- 若降维硬映射(slx_subsystem → "block"):chunk metadata `block_type="Subsystem"` 与 `SlxBlock.block_type` 真实值(Simulink XML 标准是 `"SubSystem"`)大小写错位 → ChatService Step 4 四元组校验**丢弃该 citation**
- 扩 Literal 后,`"subsystem"` / `"overview"` 类型走非 "block" 分支,`validation_key=None`,**LLM 引用透传,无丢弃**

**ChatService 影响零**:`_build_source_entries`(TASK-205 § 6.5.3)仅 `if hit.source_type == "block"` 触发四元组;其他类型 validation_key=None。新增类型自然透传。

**LLM prompt 影响**:`f"[{entry.source_id}] {entry.hit.source_type}: {entry.snippet}"` 字符串透传到 LLM 上下文;若 `core/prompts/qa_with_context.yaml` 写死了 source_type 枚举说明,需同步加 "subsystem" / "overview" 描述 — **Stage 0 #10 核查决定**。

### 2. `VectorRetriever`(`features/chat/_vector_retriever.py` 新建)

```python
"""Dense vector retriever using EmbeddingProvider + VectorStore."""
from __future__ import annotations

import asyncio

from loguru import logger                     # ★ v0.4 R2 P1-6:第三方在本地前(ruff I001)

from core.domain.exceptions import EmbeddingError
from core.domain.project import Project
from core.domain.source_ref import SourceRef
from core.interfaces.embedder import EmbeddingProvider
from core.interfaces.vector_store import QueryHit, VectorStore
from features.chat._retriever import RetrievalHit, Retriever, SourceType


# ChunkRecord.source_type → RetrievalHit.source_type 映射(D4)
# vector_store 持久化 6 类 → retriever 8 类(扩 Literal 后)
_SOURCE_TYPE_MAP: dict[str, SourceType] = {
    "m_file":           "file",
    "m_function":       "function",
    "slx_block":        "block",
    "slx_subsystem":    "subsystem",     # ★ D3 + D4
    "mat_variable":     "param",
    "project_overview": "overview",      # ★ D3 + D4
    # "teaching_unit" 永不出现(TASK-303 RESERVED_SOURCE_TYPES 守门)
}

_SNIPPET_MAX_CHARS = 300  # D7,对齐 TASK-205 RetrievalHit.snippet ≤ 300 字硬约束
_MIN_SCORE_LO = -1.0
_MIN_SCORE_HI = 1.0
_TOP_K_LO = 1
_TOP_K_HI = 50


class VectorRetriever(Retriever):
    """Dense vector retriever:embed query → vector_store.query → RetrievalHit list.

    本类不持有 KeywordRetriever;fallback 协调由 HybridRetriever 负责(D2 + D11)。
    embed 是同步重活,async search 内 asyncio.to_thread 桥接(D5,决策 11)。

    v0.3 P0-1 修订:embed 调用 wrap raw exc → EmbeddingError(本任本地闭环,不依赖 TASK-301
    SentenceTransformerEmbedder.embed 的 wrap 行为;实测 line 69 未 wrap,raw exc 会穿透)。
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        min_score: float = 0.3,    # D13,对齐 TASK-302 vector_min_score
    ) -> None:
        # P1-7:min_score 也在 __init__ 预校验,避免错误构造
        if min_score < _MIN_SCORE_LO or min_score > _MIN_SCORE_HI:
            raise ValueError("min_score out of range")
        self._embedder = embedder
        self._vector_store = vector_store
        self._min_score = min_score

    async def search(
        self,
        project: Project,
        query: str,
        top_k: int = 8,    # D14,对齐 ABC 默认值 + ChatService DEFAULT_TOP_K
    ) -> list[RetrievalHit]:
        """检索 top-k 相似 chunk 并转 RetrievalHit。

        异常向上抛(由 HybridRetriever 内 catch + 降级,D11):
        - EmbeddingError:embed 失败(模型挂 / OOM / raw exc 被本层 wrap;P0-1)
        - VectorStoreError:SQLite 操作失败(磁盘满 / 损坏;vector_store.query 抛)
        - ValueError:top_k 非法(预校验;不被 HybridRetriever catch)
        """
        # Step 1:防御性 top_k 预校验(后续 vector_store.query 也会校验,本层提早拒绝)
        if top_k < _TOP_K_LO or top_k > _TOP_K_HI:
            raise ValueError("top_k out of range")

        # Step 2:embed query(同步重活,D5 asyncio.to_thread 桥接 + P0-1 wrap raw exc)
        try:
            embeddings = await asyncio.to_thread(self._embedder.embed, [query])
        except EmbeddingError:
            raise  # 已是 EmbeddingError 直接向上抛
        except Exception as exc:
            # ★ P0-1:任何非 EmbeddingError(model.encode 原始异常 / OOM / runtime)
            # 都 wrap 成 EmbeddingError,让 HybridRetriever 能 catch 并 fallback;
            # 不依赖 TASK-301 SentenceTransformerEmbedder.embed 的 wrap 行为(实测 line 69 未 wrap)
            raise EmbeddingError(f"embed_failed:{type(exc).__name__}") from exc

        if not embeddings or len(embeddings[0]) != self._embedder.dimension():
            raise EmbeddingError("embed_returned_invalid_shape")
        query_embedding = embeddings[0]

        # Step 3:vector_store 查询(VectorStoreError / ValueError 由 vector_store 抛,本层透传)
        query_hits: list[QueryHit] = await self._vector_store.query(
            query_embedding=query_embedding,
            project_id=project.id,
            top_k=top_k,
            min_score=self._min_score,
        )

        # Step 4:防御性 by-chunk_id dedupe(D8;vector_store 已保证唯一,本层兜底)
        seen_chunk_ids: set[str] = set()
        deduped: list[QueryHit] = []
        for qh in query_hits:
            if qh.chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(qh.chunk.chunk_id)
            deduped.append(qh)

        # Step 5:转 RetrievalHit;未知 source_type 抛 ValueError(P1-6:不静默降级,与 D4 一致)
        hits = [self._to_retrieval_hit(qh) for qh in deduped]

        # P2-13 修订:每次问答打 info 偏吵 → 改 debug;HybridRetriever 的 fallback 保留 info
        logger.debug(
            "VectorRetriever.search: project_id={} hit_count={} top_k={}",
            project.id, len(hits), top_k,
        )
        return hits

    @staticmethod
    def _to_retrieval_hit(qh: QueryHit) -> RetrievalHit:
        """QueryHit → RetrievalHit 转换。

        D4 source_type 映射 + D7 snippet 防御截断 + SourceRef 构造。
        P1-8:mat_variable 时把 chunk.symbol_name(var.name)透传到 SourceRef.parameter_name。
        P0-8 (PM 拍 Z):project_overview chunk 的哨兵 file_path="__project_overview__" 原样
        透传到 SourceRef.file_path(**不替换**;PM 接受 E 类 fallback sentinel 泄露 UX 问题;
        TASK-403 前端只能用 file_path 字面识别;详 R12 技术债声明)。
        """
        chunk = qh.chunk
        mapped_type = _SOURCE_TYPE_MAP.get(chunk.source_type)
        if mapped_type is None:
            # teaching_unit 永不到这(TASK-303 RESERVED 守门);其他未知 → 抛(P1-6 与 D4 一致)
            raise ValueError(f"unknown_source_type:{chunk.source_type}")

        # P1-8 修订:mat_variable → "param" 时,把变量名透传到 parameter_name
        parameter_name = chunk.symbol_name if mapped_type == "param" else None

        source_ref = SourceRef(
            file_path=chunk.file_path,    # P0-8:overview 哨兵 "__project_overview__" 正常透传
            line_range=chunk.line_range,
            block_id=chunk.block_id,
            block_name=chunk.block_name,
            parent_subsystem=chunk.parent_subsystem,
            parameter_name=parameter_name,
        )

        # D7 snippet 防御 cap(TASK-303 chunker 已 sanitize + truncate 到 1024 字,
        # 本任进一步 cap 到 300 字对齐 TASK-205 RetrievalHit.snippet 约束)
        snippet = chunk.source_text
        if len(snippet) > _SNIPPET_MAX_CHARS:
            snippet = snippet[: _SNIPPET_MAX_CHARS - 1] + "…"

        # block_type 仅 source_type=="block" 时透传(TASK-205 R2 P0-2 约束)
        block_type = chunk.block_type if mapped_type == "block" else None

        return RetrievalHit(
            source_ref=source_ref,
            score=qh.score,
            snippet=snippet,
            source_type=mapped_type,
            block_type=block_type,
        )
```

### 3. `HybridRetriever`(`features/chat/_hybrid_retriever.py` 新建)

```python
"""Hybrid retriever:vector main path + keyword fallback."""
from __future__ import annotations

from typing import Literal

from loguru import logger                     # ★ v0.4 R2 P1-6:第三方在本地前(ruff I001)

from core.domain.exceptions import EmbeddingError, VectorStoreError
from core.domain.project import Project
from core.interfaces.vector_store import VectorStore
from features.chat._retriever import RetrievalHit, Retriever


# P2-12:fallback_reason 4 枚举(结构化日志 + TASK-306 评测可定位)
FallbackReason = Literal[
    "chunk_count_below_threshold",
    "get_chunk_count_failed",
    "vector_search_failed",
    "vector_empty_hits",
]


class HybridRetriever(Retriever):
    """协调 vector 主路 + keyword fallback(D2 + D11)。

    v0.3 P0-7 修订:__init__ 类型 hint 用 Retriever ABC,不绑定具体 VectorRetriever /
    KeywordRetriever 实现;支持 mock 单测 + Phase 2 替换检索器(对齐 R9)。

    Fallback 触发条件(4 种 fallback_reason):
    1. vector_store.get_chunk_count(project_id) < min_chunk_count → chunk_count_below_threshold
    2. get_chunk_count 抛 VectorStoreError → get_chunk_count_failed
    3. vector 抛 VectorStoreError / EmbeddingError → vector_search_failed
    4. vector 返回 [] → vector_empty_hits

    禁 catch ValueError(那是编程错误,P0-4);LLMError 不在本任处理范围。
    """

    def __init__(
        self,
        vector: Retriever,           # ★ v0.3 P0-7:Retriever ABC,不绑定 VectorRetriever
        keyword: Retriever,          # ★ v0.3 P0-7:Retriever ABC,不绑定 KeywordRetriever
        vector_store: VectorStore,
        min_chunk_count: int = 1,    # D6 + D2,默认 1 = chunks==0 即 fallback
    ) -> None:
        self._vector = vector
        self._keyword = keyword
        self._vector_store = vector_store
        self._min_chunk_count = min_chunk_count

    async def search(
        self,
        project: Project,
        query: str,
        top_k: int = 8,
    ) -> list[RetrievalHit]:
        # Path 1:get_chunk_count 查询
        try:
            chunk_count = await self._vector_store.get_chunk_count(project.id)
        except VectorStoreError as exc:
            return await self._fallback(
                project, query, top_k,
                fallback_reason="get_chunk_count_failed",     # ★ v0.3 P0-4:统一 fallback_reason
                exc_class=type(exc).__name__,
            )

        # Path 2:chunks 不足阈值
        if chunk_count < self._min_chunk_count:
            return await self._fallback(
                project, query, top_k,
                fallback_reason="chunk_count_below_threshold",   # ★ v0.3 P0-4
                chunk_count=chunk_count,
            )

        # Path 3:走向量;异常或空召回降级
        try:
            hits = await self._vector.search(project, query, top_k)
        except (VectorStoreError, EmbeddingError) as exc:
            return await self._fallback(
                project, query, top_k,
                fallback_reason="vector_search_failed",          # ★ v0.3 P0-4
                exc_class=type(exc).__name__,
                chunk_count=chunk_count,
            )

        if not hits:
            return await self._fallback(
                project, query, top_k,
                fallback_reason="vector_empty_hits",             # ★ v0.3 P0-4
                chunk_count=chunk_count,
            )

        return hits

    async def _fallback(
        self,
        project: Project,
        query: str,
        top_k: int,
        *,
        fallback_reason: FallbackReason,    # ★ v0.3 P0-4:关键字参数名统一
        chunk_count: int | None = None,
        exc_class: str | None = None,
    ) -> list[RetrievalHit]:
        """统一 fallback 入口 + 结构化 logger.info(D12 metadata-only)。

        v0.3 P0-4 修订:log message 关键字一律用 `fallback_reason=`,不用 `reason=`,
        对齐 D11 文字描述 + P2-12 反馈 + TASK-306 评测 grep 口径。
        """
        logger.info(
            "HybridRetriever.fallback: project_id={} fallback_reason={} chunk_count={} exc_class={}",
            project.id, fallback_reason, chunk_count, exc_class,
        )
        return await self._keyword.search(project, query, top_k)
```

### 4. ChunkRecord.source_type → RetrievalHit.source_type 映射表(D4 + P1-8 修订)

| ChunkRecord.source_type | RetrievalHit.source_type | block_type 透传 | parameter_name 透传(P1-8) | ChatService 校验路径 |
|---|---|---|---|---|
| `"m_file"` | `"file"` | None | None | non-block,validation_key=None,透传 |
| `"m_function"` | `"function"` | None | None | non-block,透传 |
| `"slx_block"` | `"block"` | `chunk.block_type`(真实 SlxBlock.block_type,如 "Gain" / "Sum" / "SubSystem")| None | **block,触发四元组校验**;依赖 TASK-303 chunker 透传真实 block_type |
| `"slx_subsystem"` | `"subsystem"`(★ D3 新增) | None | None | non-block,**透传不丢弃** |
| `"mat_variable"` | `"param"` | None | **`chunk.symbol_name`(.mat 变量名)**(★ P1-8 修订) | non-block,透传 |
| `"project_overview"` | `"overview"`(★ D3 新增) | None | None | non-block,透传 |
| `"teaching_unit"`(reserved) | — | — | — | 永不出现(TASK-303 守门) |

### 5. snippet / SourceRef 构造(D7)

**snippet**:
- 来源:`ChunkRecord.source_text`(TASK-303 chunker 已 sanitize + cap 到 1024 字)
- 本任二次截断:cap 到 300 字(`_SNIPPET_MAX_CHARS`),用 `…` 标记
- 不重做 sanitize(信任 TASK-303 守门)

**SourceRef** 字段映射(TASK-101 锁的 6 字段契约;**v0.3 P0-8 修订:overview 哨兵透传明示**):

| SourceRef 字段 | 来源 |
|---|---|
| `file_path: str` | `chunk.file_path`(**含 overview 哨兵 `"__project_overview__"` 原样透传,P0-8 PM 拍 Z**)|
| `line_range: tuple[int, int] \| None` | `chunk.line_range` |
| `block_id: str \| None` | `chunk.block_id` |
| `block_name: str \| None` | `chunk.block_name` |
| `parent_subsystem: str \| None` | `chunk.parent_subsystem` |
| `parameter_name: str \| None` | **`chunk.symbol_name if mapped_type == "param" else None`**(P1-8 修订)|

**overview 哨兵透传说明(v0.4 PM 拍 Z:接受 sentinel 泄露)**:
- `file_path = "__project_overview__"` **原样透传**到 SourceRef.file_path(不替换为人类可读标题;PM 拍 Z)
- ChatResponse.citations 输出 SourceRefDTO,**不含 source_type**;TASK-403 前端**只能用 `file_path == "__project_overview__"` 字面识别**
- TASK-307 可在 features/chat 内用 `RetrievalHit.source_type == "overview"` 强类型识别(不依赖前端)
- E 类 fallback `_short_hit_label` 会把 `__project_overview__` 拼进用户可见 answer — **PM 拍 Z 接受此 UX 问题**,消解需后续 backend task(详 R12 技术债)

### 6. dedupe 策略(D8)

- 仅 by-chunk_id 防御性 dedupe(VectorStore 已保证唯一,本层兜底)
- **不做** by source_ref / by (file_path, block_name):slx_block 和 slx_subsystem 在同一 file_path 可能共存,误删丢语义

### 7. AppSettings 新增字段(D6,**v0.2 P0-2 修订**)

```python
# app/config.py(本任仅追加 1 字段;不复用 vector_top_k)

class AppSettings(BaseSettings):
    # ... existing fields ...

    # Vector store(TASK-302 已落,本任仅 VectorRetriever 内部用 vector_min_score)
    vector_top_k: int = Field(default=8, ge=1, le=50)          # ★ 本任不复用(ChatService DEFAULT_TOP_K 控制)
    vector_min_score: float = Field(default=0.3, ge=-1.0, le=1.0)   # ★ 本任复用

    # RAG retrieval(★ TASK-304 新增 D6)
    rag_min_chunk_count: int = Field(
        default=1, ge=0, le=100,
        description="HybridRetriever 触发 keyword fallback 的 chunk 数阈值;"
                    "vector_store.get_chunk_count(project_id) < rag_min_chunk_count 时降级",
    )
```

`.env.example` 追加:
```bash
# RAG retrieval (TASK-304)
RAG_MIN_CHUNK_COUNT=1
```

---

## 决策日志

### D1 — VectorRetriever 实现 Retriever ABC(不引入新接口)

**决策**:VectorRetriever 实现 `features/chat/_retriever.py::Retriever` ABC,签名 `async def search(project, query, top_k=8) -> list[RetrievalHit]`。

**理由**:
- ChatService 已经依赖 Retriever ABC(TASK-205 R1 P0-2 锁),引入新接口 = 改 ChatService = 跨 Task 改 main freeze
- HybridRetriever 也实现 Retriever ABC → ChatService DI 注入透明
- VectorRetriever / KeywordRetriever / HybridRetriever 三者可互换 → 评测期(TASK-306)可分别测试

**trade-off**:`Retriever.search` 是粗 RAG 设计(只接受 query text + top_k),无法暴露 min_score / source_type filter 等向量检索专属参数;`min_score` 通过 `VectorRetriever.__init__` 传入,运行时不暴露(MCS 阶段够用;Phase 2 评测后再决定是否扩 ABC)。

### D2 — HybridRetriever 协调 fallback(4 fallback_reason 枚举,P2-12)

**决策**:新增 `HybridRetriever` 实现 Retriever ABC,持有 vector: Retriever + keyword: Retriever + VectorStore 引用(ABC 类型,v0.4 R2 P1-4);**4 种 fallback_reason 枚举**(结构化日志 + TASK-306 评测可定位):
1. `chunk_count_below_threshold` — `get_chunk_count < min_chunk_count`
2. `get_chunk_count_failed` — `get_chunk_count` 抛 VectorStoreError
3. `vector_search_failed` — VectorRetriever 抛 VectorStoreError / EmbeddingError
4. `vector_empty_hits` — VectorRetriever 返 []

**理由**:
- KPI b "本任可闭环不转嫁":TASK-303 D12 已锁 "TASK-304 用 `get_chunk_count == 0` fallback KeywordRetriever";本任兑现并扩展(4 路径,工程稳定性)
- P2-12 fallback_reason 枚举:TASK-306 评测时可统计各 fallback 频率 + Phase 2 调优依据

**trade-off**:fallback 后 LLM 看到的 hits 质量与正常 vector 不同(snippet 来源不同 — vector 是 chunk source_text,keyword 是即时构造的 file/block 标签);**LLM prompt 不感知这个差异**(prompt 模板透传 source_type + snippet),由 confidence 字段 + 评测反映质量差。**本任不在 service / response 层暴露 fallback_reason**(对前端透明,符合 TASK-205 fallback_reason "内部分类"语义)。

### D3 — RetrievalHit.source_type Literal 扩 6 → 8 类

**决策**:`features/chat/_retriever.py::SourceType` Literal 加 `"subsystem"` + `"overview"`,共 8 类。

**理由**(详 § 接口契约 1):
- 不扩 = slx_subsystem → "block" 降维硬映射,因 chunk metadata block_type="Subsystem" 与 SlxBlock.block_type="SubSystem" 大小写错位 → ChatService Step 4 校验丢弃 citation
- 扩 = chunk-based 检索新语义类型的正常工程演化;ChatService 现有逻辑零变更

**trade-off**:引入 main freeze 接口扩展,但是 Literal 加值不删不改,向后兼容。

### D4 — ChunkRecord.source_type → RetrievalHit.source_type 映射(P1-8 修订)

**决策**:VectorRetriever 内 `_SOURCE_TYPE_MAP: dict[str, SourceType]` 6 项映射;未知 source_type 抛 `ValueError("unknown_source_type:...")`(**P1-6 修订:不静默降级**)。

**P1-8 修订**:`mat_variable → "param"` 时,`chunk.symbol_name` 透传到 `SourceRef.parameter_name`,避免变量名丢失(原 v0.1 全填 None)。

### D5 — embed 调用 asyncio.to_thread 桥接(决策 11 决策 1)

**决策**:`VectorRetriever.search` 内 embed 调用必须 `await asyncio.to_thread(self._embedder.embed, [query])`;**禁** 直接 `self._embedder.embed([query])`。

**理由**:决策 11 决策 1 硬约束。EmbeddingProvider.embed 是同步重活(50-200ms);async 函数内直接调阻塞 event loop。

**测试守门**:`test_embed_runs_in_thread`:用 monkeypatch + threading.current_thread() 断言 embed 调用在非 main thread 执行。

### D6 — AppSettings `rag_min_chunk_count` 1 字段;**仅复用 `vector_min_score`**(v0.2 P0-2 修订)

**决策**:
- `vector_min_score`:TASK-302 已落字段,**本任复用**(VectorRetriever.__init__ 传入 `min_score=settings.vector_min_score`)
- `vector_top_k`:**本任不复用**(ChatService 调 `retriever.search(top_k=DEFAULT_TOP_K=8)`,settings 字段对本任无影响)
- `rag_min_chunk_count`:本任新增 1 字段,`ge=0, le=100`,默认 1

**理由**(P0-2 修订):
- v0.1 写"复用 vector_top_k"是反例 29(跨段一致性失败 — ChatService DEFAULT_TOP_K 路径绕开了 settings)
- 不引入 top_k 配置链路,避免误导(后续开发者以为改 `VECTOR_TOP_K=20` 会生效,实际不会)

### D7 — snippet 来源 chunk.source_text + 防御 cap 300 字

**决策**:`RetrievalHit.snippet = chunk.source_text[:300]`(超长用 `…` 标记)。

**理由**:
- chunk.source_text 已 TASK-303 sanitize + cap 到 1024 字;本任 cap 到 300 字对齐 TASK-205 RetrievalHit.snippet 硬约束
- 不重做 sanitize(信任 TASK-303 守门;反例 31 KPI e)

### D8 — dedupe 仅 by-chunk_id(防御性)

**决策**:VectorRetriever 内 `seen_chunk_ids: set[str]` 防御性去重;**不做** by source_ref 去重。

**理由**:
- VectorStore 已保证 chunk_id 唯一(TASK-302 PRIMARY KEY);理论命中 0
- slx_block 和 slx_subsystem 在同一 file_path 可能共存(母系统 + 内部 block 同名),source_ref 维度去重会误删;chunk_id 维度天然区分

### D9 — lifespan 单例装配(v0.2 P0-1 锁定 + Codex Stage 0 #6 实测确认)

**决策**:
- 沿 task-203 / task-205 既定的 lifespan 单例模式:
  - `api/main.py` lifespan 装配 `app.state.vector_retriever / hybrid_retriever`,`app.state.chat_service` 的 retriever 改为 `app.state.hybrid_retriever`
  - `api/dependencies.py` **零变更**(`get_chat_service` 仍仅取 app.state.chat_service,**不新增 `get_vector_retriever` / `get_hybrid_retriever` DI 函数**)
- `features/chat/__init__.py` 同步 re-export `VectorRetriever` / `HybridRetriever`(类比当前 4 项 re-export 模式)

**理由**(P0-1 修订 + Codex Stage 0 #6 实测):
- v0.1 同时写两套装配是反例 24(凭印象写,未实地核查 api/dependencies.py)
- 当前 ChatService 在 lifespan 内联装配 KeywordRetriever(line 106),本任只换 retriever 实例,**保持架构一致性**(P0-1)

### D10 — lifespan 装配链路顺序 + 抽出 `app.state.graph_provider`

**决策**:`api/main.py` `AsyncExitStack` 装配顺序:
```
1. settings = AppSettings()
2. app.state.project_store = SqliteProjectStore(settings.db_path)
3. app.state.chat_store = SqliteChatStore(settings.db_path)
4. app.state.text_provider = DeepSeekTextProvider(...)                                 # 已有,与 RAG 链路无关,不参与 #26 守门;真实顺序以 main.py 为准
5. app.state.embedder = await asyncio.to_thread(SentenceTransformerEmbedder, ...)   # TASK-301
6. app.state.vector_store = SqliteVectorStore(settings.db_path)                      # TASK-302
7. app.state.graph_provider = ProjectGraphBuilder()                                   # ★ 本任新增(抽出共用单实例)
8. app.state.chunking_service = ChunkingService(..., graph_provider=app.state.graph_provider)   # 改:从内联 ProjectGraphBuilder() 改为引用 app.state.graph_provider
9. app.state.keyword_retriever = KeywordRetriever(graph_provider=app.state.graph_provider)       # ★ 本任新增(从 chat_service 内联抽出)
10. app.state.vector_retriever = VectorRetriever(
        embedder=app.state.embedder,
        vector_store=app.state.vector_store,
        min_score=settings.vector_min_score,
    )
11. app.state.hybrid_retriever = HybridRetriever(
        vector=app.state.vector_retriever,
        keyword=app.state.keyword_retriever,
        vector_store=app.state.vector_store,
        min_chunk_count=settings.rag_min_chunk_count,
    )
12. app.state.chat_service = ChatService(..., retriever=app.state.hybrid_retriever, ...)
```

**理由**:
- 依赖方向:hybrid_retriever 依赖 vector_retriever + keyword_retriever + vector_store;装配顺序保证
- 抽出 `app.state.graph_provider`:Codex Stage 0 #6 实测 main HEAD line 94 + 106 重复构造 ProjectGraphBuilder(),本任顺手减少重复(单实例 + 给 ChunkingService 和 KeywordRetriever 共用)
- AsyncExitStack 不需要给 retriever 注册 cleanup(无资源持有;embedder / vector_store 已注册 cleanup,本任不重注册)

### D11 — 异常分层 + HybridRetriever 兜底(**v0.4 R2 P0-1 大重写:允许 embed wrap**)

**决策**:
- VectorRetriever **embed 路径**:允许 `except Exception as exc: raise EmbeddingError(...) from exc`(**P0-1 wrap raw exc**;这不是"静默吞",是 **re-raise 为业务异常 = 异常翻译**,对齐 04 § 10 adapter 层异常翻译原则);**VectorStoreError / ValueError 仍透传不 catch**
- HybridRetriever 内 catch `VectorStoreError` + `EmbeddingError` → fallback keyword + `logger.info(... fallback_reason ...)`(D12 metadata-only)
- **禁 catch `ValueError`**(那是编程错误)
- **禁静默吞 Exception**(catch Exception 后**不 raise 新异常 = 吞**;catch + **re-raise as EmbeddingError = 翻译,允许**;区分标准:re-raise 后调用方能感知异常 = OK)
- LLMError 不在本任处理范围(ChatService 现有 ERROR_MAP 处理)

**理由**:
- 单一职责:VectorRetriever 纯检索,异常透明;HybridRetriever 是协调层,负责降级
- 决策 11 决策 2:`logger.info` metadata-only,不落 `str(exc)` / traceback;只落 `type(exc).__name__`

### D12 — 日志 metadata-only(决策 11 决策 2,**v0.2 P1-9 + v0.3 P0-5 修订**)

**禁出**(features/chat/_vector_retriever.py + _hybrid_retriever.py,**所有 logger level + 全字段列表**):
- ❌ `logger.exception(...)`
- ❌ 任何含以下完整值的 logger 调用(所有 level):
  - `query` / `question`(用户问题原文)
  - `source_text` / `chunk_text`(chunk 原文 + **v0.3 P0-5 新增**)
  - `answer`(LLM 输出原文)
  - `chunk_id` 完整字面(**v0.3 P0-5 新增**;仅允许 hash 前缀 12 位,对齐 TASK-302 / 303 chunk_id 格式)
- ❌ 任何含 `{exc}` / `repr(exc)` / `str(exc)` 的 f-string

**允许出**(白名单字段,8 项):
- ✅ `project_id` / `source_type` / `chunk_count` / `hit_count` / `top_k` / `fallback_reason` / `type(exc).__name__` / `exc_class`

**验收守门**(P1-9 + P0-5 修订:扩 grep 范围所有 logger level + 全禁列字段):
```bash
grep -nE 'logger\.(exception|debug|info|warning|error|critical).*(query|question|source_text|chunk_text|chunk_id|answer|\{exc\}|repr\(exc\)|str\(exc\))' \
  features/chat/_vector_retriever.py features/chat/_hybrid_retriever.py
# 期望 0 行
```

### D13 — min_score 默认 0.3 + __init__ 预校验(P1-7)

**决策**:`VectorRetriever.__init__(min_score=0.3)` 默认值;lifespan 从 `settings.vector_min_score` 注入;`__init__` 加预校验 `if min_score < -1.0 or min_score > 1.0: raise ValueError("min_score out of range")`(P1-7)。

**理由**:TASK-302 D9 已锁 `vector_min_score: float = 0.3` 是基线;P1-7 修订:错误构造应在 `__init__` 立刻抛,而不是延迟到 search 时(防御性编程)。

### D14 — top_k 默认 8(**v0.2 P0-2 修订:本任不引入 top_k 配置**)

**决策**:
- `VectorRetriever.search` / `HybridRetriever.search` 默认 `top_k=8`(对齐 Retriever ABC 默认值 + ChatService `DEFAULT_TOP_K=8`)
- **本任不暴露 top_k 配置项**(不读 settings.vector_top_k)
- ChatService 调 `retriever.search(top_k=DEFAULT_TOP_K)`,本任沿用

**理由**(P0-2 修订):
- v0.1 写"复用 vector_top_k"是反例 29 — ChatService DEFAULT_TOP_K 路径绕开了 settings,settings 字段对本任无影响
- 不引入 top_k 配置链路 → 不误导后续开发者

### D15 — 集成测试 RUN_EMBEDDING_INTEGRATION=1 skipif + 弱断言(P1-10 修订)

**决策**:`tests/features/chat/test_vector_retriever_integration.py`:
- 加 `@pytest.mark.skipif(not os.getenv("RUN_EMBEDDING_INTEGRATION"), reason="...")`(对齐 TASK-301 / 303 工艺)
- **集成断言弱化**(P1-10 修订):
  - 真实 SentenceTransformerEmbedder + 真实 SqliteVectorStore + 真实 ChunkingService 灌 chunks → VectorRetriever.search("query") 返**非空** + 各 hit `source_type ∈ {file, function, block, subsystem, param, overview}`(8 类内,排除 graph_entry / unresolved 这两个 keyword 专属)+ citation 非空
  - **不强制具体 source_type**(避免 flaky)
- **受控单元测试** 接管"非 block 类型透传"断言:用 MockEmbeddingProvider + 受控 ChunkRecord 注入(slx_subsystem + project_overview)→ 强制召回非 block → 断言 RetrievalHit 中包含 source_type="subsystem" 或 "overview" 至少 1 个

**理由**(P1-10 修订):
- 真实模型召回结果受 chunk 内容 / query 文案 / min_score 影响,强制"必有 X 类型"会 flaky → 间接成为循环论证(反例 31 KPI e 同源)
- 拆 2 个测试:单元测可控验证语义透传 + 集成测验证链路连通

---

## 风险

### R1 — embed 阻塞 event loop(决策 11 反例 19 同源)

**触发条件**:Codex 实施时忘了 `asyncio.to_thread`,直接 `self._embedder.embed(...)` 在 async search 内。

**后果**:单 worker 模式下问答期间(50-200ms)全站无响应。

**守门**:
- 静态:`grep -nE 'self\._embedder\.embed' features/chat/_vector_retriever.py` 命中行必须前置 `await asyncio.to_thread`
- 动态:`test_embed_runs_in_thread` 用 monkeypatch + threading 验证

### R2 — min_score 设太高 → 频繁 fallback keyword

**触发条件**:`vector_min_score = 0.3` 在 bge-small-zh-v1.5 上对教学问答可能偏高。

**应对**:
- TASK-306 评测期实测调整;本任不预判数值
- D11 fallback 时 `logger.info(fallback_reason=vector_empty_hits)` 提供可观测数据(P2-12)
- AppSettings `vector_min_score` 已是 Field(ge=-1.0, le=1.0),运维可热改

### R3 — slx_block chunk metadata block_type 与 SlxBlock.block_type 大小写错位

**触发条件**:TASK-303 chunker 透传 `slx_block.block.block_type` 到 chunk metadata 时,与 SlxBlock 真实值一致(规范是直接赋值,无字符串变换)。

**后果**:slx_block → "block" 走 ChatService Step 4 四元组校验时,(file_path, block_name, block_type, parent_subsystem) 必须能在 SlxModel.blocks 集合中找到,否则该 citation 被丢弃。

**应对**:
- 本任**不重测 TASK-303** 透传行为(反例 31 KPI e:不循环验证下游契约)
- VectorRetriever `_to_retrieval_hit` 中 `block_type=chunk.block_type if mapped_type == "block" else None` 严格透传,不做 case 变换
- 集成测试覆盖:真实 SLX 工程 → chunk → vector retrieve → ChatService 完整链路 → 至少 1 个 slx_block citation 不被丢弃(集成断言弱化但仍验链路)
- 若集成测试发现 TASK-303 chunker block_type 与 SlxBlock.block_type 不一致 → 反例 31 升仪触发(TASK-303 P0 漏);本任**不修 TASK-303**,向 PM 上报

### R4 — dedupe 边界:slx_block + slx_subsystem 同 file 共存

**触发条件**:同一 .slx 文件下,slx_block 和 slx_subsystem 同时召回。

**应对**:D8 决策仅做 by-chunk_id dedupe,跨 source_type 不去重 → 风险消解。

### R5 — lifespan 装配顺序错(embedder 未就绪,vector_retriever 已用)

**应对**:D10 已明示 12 步顺序;Codex 严格 follow;验收守门 grep app.state.* 行号严格递增。

### R6 — KeywordRetriever 装配链调整(P0-1 + Codex Stage 0 #6 实测)

**触发条件**:Codex Stage 0 #6 实测确认 KeywordRetriever 在 api/main.py lifespan **内联构造**(line 106),不是 DI;本任要把它抽出存到 `app.state.keyword_retriever`。

**后果**:若 Codex 实施时只新增 hybrid_retriever 装配但忘记把 KeywordRetriever 抽出,会出现 KeywordRetriever 被双重构造(line 106 旧 + 新加的 app.state.keyword_retriever),浪费 ProjectGraphBuilder()。

**应对**:
- D10 明示 12 步装配顺序 + 抽出 `app.state.graph_provider` 单实例(给 ChunkingService + KeywordRetriever 共用)
- 验收 #25 守门:`grep -c "KeywordRetriever(" api/main.py` 期望 = 1(只在 line `app.state.keyword_retriever =` 出现 1 次)
- 验收 #26 守门:`grep -c "ProjectGraphBuilder()" api/main.py` 期望 = 1(抽出后只在 line `app.state.graph_provider =` 出现 1 次)

### R7 — fallback 后 confidence 标签不一致(LLM 视角)

**应对**:本任不在 prompt 中暴露 fallback 信号;TASK-306 评测时分别测试 hybrid 全向量 vs 全 fallback 路径,统计 confidence 分布。

### R8 — 集成测试首次跑慢(模型下载)

**应对**:`RUN_EMBEDDING_INTEGRATION=1` skipif → CI 默认不跑;TASK-301 已落 SentenceTransformerEmbedder,本地评测期模型已 cached。

### R9 — VectorRetriever / HybridRetriever 写死 Retriever ABC 后,Phase 2 升级困难

**应对**:VectorRetriever 通过 VectorStore ABC 解耦(TASK-302 已做);存储替换不动 VectorRetriever。HybridRetriever 不绑定具体 VectorRetriever 实现,只绑定 Retriever ABC。

### R10 — 03 索引补账状态语义(P0-3 修订)

**触发条件**:Codex 完工时 PR 还在 review 阶段,不能写 ✅。

**应对**(P0-3 修订):
- 搭车 chore 字节级 patch 只改 TASK-304 行 `🔲 → 🔍`
- **不动**进度条 [3/7]、总计 21/32、当前状态字面
- merge 后由 PM 单独 chore patch 改 🔍 → ✅ + [4/7] + 22/32 + "TASK-304 完成,启动 TASK-305"

### R11 — HybridRetriever 每次问答多 1 SQL `get_chunk_count`(P2-14 修订)

**触发条件**:HybridRetriever.search 每次先查 `vector_store.get_chunk_count(project_id)`,生产规模下每问答多 1 次 SQL 往返。

**后果**:MCS 单工程规模(SQLite 内存压力小)不明显;Phase 2 用户量上去(> 100 并发)可能成为性能瓶颈。

**应对**:
- 本任 trade-off 接受(简单 + 正确性 > 性能优化)
- Phase 2 候选:把"空 chunk project"标记缓存到 `project_status_record.chunk_ready` bool 列(类似 ProjectStatus 设计)或 app-level cache(`functools.lru_cache(maxsize=1000)` on get_chunk_count)
- 本任不实施;TASK-306 评测时观察 get_chunk_count 平均耗时,> 5ms 触发 Phase 2 缓存升级

### R12 — overview sentinel 用户可见泄露(**v0.4 PM 拍 Z:已知技术债,本任不修**)

**触发条件**:VectorRetriever 将 `project_overview` chunk 的 `file_path="__project_overview__"` 哨兵原样透传到 SourceRef.file_path;ChatService E 类 fallback 的 `_short_hit_label(hit)` 会把 `source_ref.file_path` 拼进用户可见 answer → overview 命中时用户看到 `__project_overview__` 字面(UX 问题)。

**PM 决策 Z**:接受 sentinel 用户可见风险;**本任不修改 E 类 fallback 路径 / 不修改 VectorRetriever 替换 file_path / 不修改 ChatService**。

**识别路径(给下游 TASK-307 / TASK-403)**:
- `RetrievalHit.source_type == "overview"`:features/chat 内部 + TASK-307 可用(ChatResponse.citations **不含** source_type,前端不可用)
- `SourceRef.file_path == "__project_overview__"`:是 TASK-403 前端**唯一可用**锚点(ChatResponse.citations 输出 SourceRefDTO,含 file_path)
- **前端必须字面识别 `file_path == "__project_overview__"`**;没有其他强类型路径(PM 拍 Z 不扩 ChatResponse)

**技术债清单**(v0.5 R3 P1-2 归属修正):
1. E 类 fallback `_short_hit_label` 对 `file_path == "__project_overview__"` 应替换为人类可读标题(如"项目总览")— **消解必须落到 backend `ChatService` / `_chat_persist.py` 或后续 backend task**(前端拿到时 answer 已包含 `__project_overview__`,无法修复);TASK-307 证据强制器只能解决 citation source_type 强类型识别,**不直接解决 E 类文案泄露**
2. 若 Phase 2 需强类型:扩 SourceRef 加 `source_type: str | None = None`(TASK-101 跨任契约扩,需 PM + 二审)或 ChatResponse.citations 从 `list[SourceRef]` → `list[CitationOut]`

---

## Stage 0 实地核查(给 Codex 第二棒实施前的最后核查 — 第一棒已跑 9 项,本任第二棒只补 #10)

> **背景**:Codex 第一棒已跑 #1-#9(PASS 7 / FAIL 2);FAIL 项 v0.2 已修订(#4 ValueError 边界 / #5 路径)。**v0.2 P1-11 新增 #10**(prompt yaml 核查),需 Codex 第二棒实施前补跑 1 条命令。

### #10(v0.2 新增 P1-11;**v0.3 P0-2 大重写**)— `core/prompts/qa_with_context.yaml` 是否含 source_type 枚举字面集合

**v0.3 P0-2 修订背景**:v0.2 #10 原 grep `'file|block|function|param|graph_entry|unresolved'` 会**误报**普通 prompt 文案的 `block` 词、`{source_block}` 模板变量(qa_with_context.yaml line 21 / 41 实测命中);期望"0 行 PASS" 必失败,A/B 任一分支都不触发。

**v0.3 修订:改 Codex `cat` 全文 + 人工判断是否含 source_type **枚举集合**字面**:

```bash
cat core/prompts/qa_with_context.yaml
```

**Codex 输出格式**:
```
#10 prompt yaml 核查:[ PASS / 触发 hot-patch ]

完整内容:[贴 cat 输出全文]

人工判断:
- 是否含 source_type **枚举集合** 字面(典型形态:"可选值:file / block / function / param / graph_entry / unresolved" 或 yaml list `source_types:` 下列 6 个值)?
  [ ] 是 → 触发 hot-patch
  [ ] 否(普通文案含 "block" 单词不算)→ PASS

判断依据:[Codex 解释 — 看到的 yaml 是否在某个段列出 6 类枚举值]
```

**PASS 分支**:不改 prompt yaml(本任决策保持)。

**触发 hot-patch 分支**(prompt 列了 6 类枚举):
- 修改文件清单加 `core/prompts/qa_with_context.yaml`
- yaml 同步加 `subsystem` / `overview` 类型说明
- 验收新增 #36:`grep -c "subsystem\|overview" core/prompts/qa_with_context.yaml` ≥ 2

**Codex 第二棒实施前必跑**;若 PM 在审查阶段已通过 Codex 实测确认 PASS,本任可在 finalize 时直接锁定"PASS 分支",免再次跑。

---

## 验收标准(Codex 实施完成后)

> **反例 31 KPI e 兑现**:验收必须用真实下游契约(VectorStore + EmbeddingProvider 真实实现),不能用 mock 自验证;mock 仅用于不被验证的 collaborator(如 ChatStore / ProjectStore)。

### 单元测试(`pytest tests/features/chat/ -v`)

- [ ] **#1 SourceType Literal 扩 8 类静态**:
  ```python
  from typing import get_args
  from features.chat._retriever import SourceType
  assert set(get_args(SourceType)) == {
      "file", "block", "function", "param",
      "graph_entry", "unresolved",
      "subsystem", "overview",
  }
  ```
- [ ] **#2 VectorRetriever 6 → 8 类映射**:每种 ChunkRecord.source_type → 对应 RetrievalHit.source_type 正确;teaching_unit 抛 ValueError
- [ ] **#3 VectorRetriever embed asyncio.to_thread 桥接守门**(D5):monkeypatch self._embedder.embed → 记录 threading.current_thread().name;断言不在 main thread
- [ ] **#4 VectorRetriever 空召回**:vector_store.query 返 [] → search 返 []
- [ ] **#5 VectorRetriever by-chunk_id dedupe**(D8 防御):构造 2 个相同 chunk_id 的 QueryHit → search 返 1 个
- [ ] **#6 VectorRetriever 参数预校验**(P1-7):
  - top_k=0 / top_k=51 → `VectorRetriever.search()` 抛 ValueError
  - `VectorRetriever(min_score=2.0)` → `__init__` 抛 ValueError("min_score out of range")
  - `VectorRetriever(min_score=-1.5)` → 同上
- [ ] **#7 VectorRetriever EmbeddingError / VectorStoreError 向上抛**:mock 抛 → search 抛同款异常(不 catch)
- [ ] **#8 VectorRetriever snippet 防御截断**:chunk.source_text 长度 500 → RetrievalHit.snippet 长度 ≤ 300 + 以 `…` 结尾
- [ ] **#9 VectorRetriever slx_block block_type 透传**:chunk.block_type="Gain" + mapped_type="block" → RetrievalHit.block_type="Gain"
- [ ] **#10 VectorRetriever slx_subsystem block_type 不透传**:chunk.block_type="Subsystem" + mapped_type="subsystem" → RetrievalHit.block_type=None
- [ ] **#11 VectorRetriever mat_variable parameter_name 透传**(P1-8):chunk.source_type="mat_variable" + chunk.symbol_name="omega_ref" → RetrievalHit.source_ref.parameter_name="omega_ref" + RetrievalHit.source_type="param"
- [ ] **#12 HybridRetriever fallback path 1 (chunk_count_below_threshold)**:mock get_chunk_count 返 0 → keyword.search 被调用,vector.search 不被调用,logger.info 含 `fallback_reason=chunk_count_below_threshold`(**v0.3 P0-4:统一 fallback_reason 关键字**)
- [ ] **#13 HybridRetriever fallback path 2 (get_chunk_count_failed)**:mock get_chunk_count 抛 VectorStoreError → keyword.search 被调用,logger.info 含 `fallback_reason=get_chunk_count_failed`
- [ ] **#14 HybridRetriever fallback path 3 (vector_search_failed)**:mock vector.search 抛 VectorStoreError 或 EmbeddingError → keyword.search 被调用,logger.info 含 `fallback_reason=vector_search_failed`
- [ ] **#15 HybridRetriever fallback path 4 (vector_empty_hits)**:mock vector.search 返 [] → keyword.search 被调用,logger.info 含 `fallback_reason=vector_empty_hits`
- [ ] **#16 HybridRetriever 正常路径**:mock vector.search 返非空 → keyword.search 不被调用,无 fallback log
- [ ] **#17 HybridRetriever 禁 catch ValueError**(D11):mock vector.search 抛 ValueError → 异常向上抛(不被 catch,不 fallback)
- [ ] **#18 HybridRetriever 受控类型透传单测**(P1-10):MockEmbeddingProvider + 受控 ChunkRecord(注入 slx_subsystem + project_overview 各 1)→ VectorRetriever.search 返 RetrievalHit 含 source_type ∈ {"subsystem", "overview"} 至少 1 个
- [ ] **#18a VectorRetriever embed wrap raw exc**(**v0.3 P0-1**):mock embedder.embed 抛 `RuntimeError("model loaded fail")`(非 EmbeddingError 的任意 exc)→ `VectorRetriever.search` 抛 `EmbeddingError("embed_failed:RuntimeError")` + `__cause__` 是原 RuntimeError(`from exc` 链);**v0.4 R2 P1-7 修订**:删除集成层 "invalid query" 守门(SentenceTransformerEmbedder.embed 对任意字符串正常 encode,无 "invalid query" 契约;用 monkeypatch `_model.encode` 抛 RuntimeError 替代)
- [ ] **#18b HybridRetriever __init__ 类型 ABC 守门**(**v0.3 P0-7;v0.4 R2 P1-4 修订**):构造 `HybridRetriever(vector=mock_retriever_abc, keyword=mock_retriever_abc, vector_store=mock_store)` — `mock_retriever_abc` 是仅实现 Retriever ABC 的 Mock(不是 VectorRetriever / KeywordRetriever 具体类)→ `HybridRetriever.search` 正常工作;**v0.4 修订**:用 `typing.get_type_hints(HybridRetriever.__init__)["vector"] is Retriever` 断言(不用 `inspect.signature`,因为 `from __future__ import annotations` 会让 signature 返回字符串而非类型对象)
- [ ] **#18c VectorRetriever overview 哨兵透传**(**v0.4 PM 拍 Z**):构造 ChunkRecord(source_type="project_overview", file_path="__project_overview__", symbol_name="MyProject") → VectorRetriever 转 RetrievalHit 后:(a) `source_ref.file_path == "__project_overview__"`(哨兵原样透传);(b) `retrieval_hit.source_type == "overview"`(内部强类型识别)→ **TASK-403 前端只能用 file_path 字面识别(ChatResponse 不含 source_type);PM 拍 Z 接受 E 类 fallback sentinel 泄露风险**

### 集成测试(`RUN_EMBEDDING_INTEGRATION=1 pytest tests/features/chat/test_vector_retriever_integration.py -v`)

- [ ] **#19 端到端 vector retrieve(弱断言,P1-10 修订;**v0.3 P2-2 加 project row 前置**)**:
  - **前置 fixture**:`tests/features/chat/conftest.py::real_project_with_chunks`:`ProjectStore.create_pending(...)` 建 project_status_record → `SqliteProjectStore.mark_ready(project_id, project)` → 真实 SentenceTransformerEmbedder + 真实 SqliteVectorStore(tmp_path)+ 真实 ChunkingService 灌 1 个 SLX fixture 工程的 chunks(不前置 create_pending / mark_ready 会 ProjectNotFoundError)
  - **断言**:VectorRetriever.search("速度控制器") 返**非空** + 每个 hit.source_type ∈ 8 类内 + 不 flaky(连跑 3 次结果一致)
- [ ] **#20 端到端 hybrid fallback**(**v0.3 P2-2 加 project row 前置**):同 #19 前置但 vector_store 不灌 chunks(ProjectStore.create_pending + mark_ready 仍跑,只跳过 ChunkingService 灌 chunks)→ HybridRetriever.search 走 keyword,返非空(KeywordRetriever 命中 file_name / block_name 兜底)
- [ ] **#21 端到端 ChatService 链路**:真实 ChatService(retriever=HybridRetriever,LLM mock 返合法 citations)→ handle_chat 走 retrieval 步骤,validated.citations 非空(**P1-10 修订:不强制具体 source_type 类型**)

### 静态守门(对齐 task-303 反例 26 KPI)

- [ ] **#22 `make check`** 全管道绿(lint + type-check + format check + test + hygiene)
- [ ] **#23 决策 11 决策 1 守门**(asyncio.to_thread 桥接;**v0.5 R3 P2-1 改两个守门**):
  ```bash
  # 守门 A:禁直接调用(若命中说明漏了 to_thread)
  grep -nE '(await\s+)?self\._embedder\.embed\(' features/chat/_vector_retriever.py
  # 期望 0 行(直接调用模式应不存在)

  # 守门 B:要求存在 to_thread 调用
  grep -c 'asyncio\.to_thread(self\._embedder\.embed' features/chat/_vector_retriever.py
  # 期望 = 1
  ```
- [ ] **#24 决策 11 决策 2 守门 + P1-9 + P0-5 扩 grep**(所有 logger level + 全禁列字段含 chunk_id / chunk_text):
  ```bash
  grep -nE 'logger\.(exception|debug|info|warning|error|critical).*(query|question|source_text|chunk_text|chunk_id|answer|\{exc\}|repr\(exc\)|str\(exc\))' \
    features/chat/_vector_retriever.py features/chat/_hybrid_retriever.py
  # 期望 0 行
  ```
- [ ] **#25 lifespan 单实例守门**(R6,P0-1 + Codex Stage 0 #6 修订):
  ```bash
  grep -c "KeywordRetriever(" api/main.py        # 期望 = 1(只在 app.state.keyword_retriever = ... 出现)
  grep -c "ProjectGraphBuilder()" api/main.py    # 期望 = 1(抽出后只在 app.state.graph_provider = ... 出现)
  ```
- [ ] **#26 lifespan 装配顺序守门**:
  ```bash
  grep -n 'app\.state\.\(embedder\|vector_store\|graph_provider\|keyword_retriever\|vector_retriever\|hybrid_retriever\|chat_service\)' api/main.py
  # 期望:行号严格递增 embedder < vector_store < graph_provider < keyword_retriever < vector_retriever < hybrid_retriever < chat_service
  ```
- [ ] **#27 RetrievalHit 字段集守门**(防 Codex 误改):
  ```python
  from features.chat._retriever import RetrievalHit
  from dataclasses import fields
  names = {f.name for f in fields(RetrievalHit)}
  assert names == {"source_ref", "score", "snippet", "source_type", "block_type"}, names
  ```
- [ ] **#28 SourceType 8 类 runtime 守门**:见 #1
- [ ] **#29 ChatService.handle_chat 7 步流程零变更守门**:
  ```bash
  git diff main -- features/chat/chat_service.py
  # 期望:空 diff(本任不动 ChatService;v0.2 P5 修订:文件名 chat_service.py)
  ```
- [ ] **#30 mypy `features/chat/` 通过**(**v0.3 P2-3 修订**:沿当前 `pyproject.toml [tool.mypy] strict = false` 配置,不引入新配置;反例 27 KPI 兑现 — 工具默认行为类陈述前必须 cat 工具配置):
  ```bash
  mypy features/chat/
  # 期望:无 error;若报 error 来自上游 main 已有问题 → Codex 上报 PM 决定是否搭车 fix
  ```

### 反例 KPI 兑现守门

- [ ] **#31 跨段一致性 grep 自审**(反例 29 + 30):本任 task 文档中 `VectorRetriever` / `HybridRetriever` / `rag_min_chunk_count` / `subsystem` / `overview` / `chat_service.py` 路径在多段描述一致
- [ ] **#32 反例 31 KPI 软妥协 grep 自审**:
  ```bash
  grep -nE '若|可能|待|上游应|前端应|等等|TODO' docs/tasks/task-304-*.md
  # 期望:命中均在合法语境(决策反衬 / Phase 2 接力 / 风险陈述 / 命令字面)
  ```
- [ ] **#33 验收测试不 mock 自验证下游契约**(反例 31 KPI e):
  ```bash
  grep -nE 'mock|Mock|fake|Fake|stub|Stub' tests/features/chat/test_vector_retriever_integration.py
  # 期望:仅出现在不被验证的 collaborator(LLM TextProvider 等);
  # 不在 EmbeddingProvider / VectorStore 上 mock(那是被验证对象)
  ```
### 搭车 chore(P0-3 修订)

- [ ] **#35 `docs/03_TASK_INDEX.md` 字节级 patch**:
  - Week 3 行:`TASK-304` 状态 `🔲` → `🔍`(**P0-3:Codex 不写 ✅;不动进度条 [3/7]、总计 21/32、当前状态**)
  - 最后更新日期同步 PR 创建日期
  - **反例库计数不动**(本任工艺顺利的话,无新反例 — 自查 5 处反例同源是 v0.1 → v0.2 自我修正,不入反例库正式编号)

---

## 给 Codex 的提示(第二棒实施)

### 实施顺序建议

每 commit 跑 `make check` 确认绿,再继续下一步(决策 08 实施 chunk 工艺):

1. **前置:** 跑 Stage 0 #10(prompt yaml 核查),输出 PASS / 触发 hot-patch
2. **commit 1:** 扩 `features/chat/_retriever.py::SourceType` Literal 6 → 8 类(单点改动);加单元测试 #1 + #28
3. **commit 2:** 写 `_vector_retriever.py`(150 行)+ unit tests(#2-#11 + #18)
4. **commit 3:** 写 `_hybrid_retriever.py`(120 行)+ unit tests(#12-#17)
5. **commit 4:** 改 `api/main.py` lifespan + `app/config.py` + `.env.example` + `features/chat/__init__.py` + `features/chat/README.md`(P0-1 + D10 装配)
6. **commit 5:** 写 integration test + tests/features/chat/conftest.py 新建 + 搭车 chore `docs/03_TASK_INDEX.md` `🔲 → 🔍`(P0-3)

### 常见坑(避免反例同源)

1. **asyncio.to_thread 桥接**(决策 11 决策 1):看到 async def 内 `self._embedder.embed` → 必须 `await asyncio.to_thread(self._embedder.embed, ...)`
2. **logger.exception 禁用 + 所有 level 禁敏感字段**(决策 11 决策 2 + P1-9 + **v0.3 P0-5**):看到 `logger.{level}` 含 `query/source_text/chunk_text/chunk_id/answer/{exc}` → 停手
3. **ChatService 不动**(D9):若发现"为了 hybrid fallback 需要改 ChatService 流程",停手抛冲突
4. **不新增 DI 函数**(P0-1):若想在 api/dependencies.py 加 `get_vector_retriever` / `get_hybrid_retriever`,停手 — 本任沿 lifespan 单例模式
5. **不复用 vector_top_k**(P0-2):若想 lifespan 装配传 `top_k=settings.vector_top_k`,停手 — settings 字段对本任无效
6. **03 索引不写 ✅**(P0-3):搭车 chore 只改 `🔲 → 🔍`;不动进度条 / 总计 / 当前状态字面
7. **mat_variable parameter_name 透传**(P1-8):VectorRetriever `_to_retrieval_hit` 中 `parameter_name = chunk.symbol_name if mapped_type == "param" else None`
8. **block_type 仅 "block" 类型透传**(R3 + D4):其他类型置 None
9. **KeywordRetriever 不双重构造**(R6):从 lifespan line 106 抽出到 app.state.keyword_retriever;旧 line 106 内联代码必须删除
10. **ProjectGraphBuilder() 单实例**(R6):抽出到 app.state.graph_provider 共用,删除 line 94 + line 106 重复构造
11. **未知 source_type 抛 ValueError 不静默降级**(P1-6 + D4)
12. **min_score __init__ 预校验**(P1-7):VectorRetriever(min_score=2.0) 必须立刻抛
13. **跨 source_type 不去重**(D8)
14. **embed wrap raw exc**(**v0.3 P0-1**):任何非 EmbeddingError 异常都 wrap 成 `EmbeddingError(f"embed_failed:{type(exc).__name__}") from exc`;不依赖 TASK-301 SentenceTransformerEmbedder.embed 的 wrap 行为(实测 line 69 未 wrap)
15. **fallback_reason 关键字统一**(**v0.3 P0-4**):log message 用 `fallback_reason=`,不用 `reason=`;关键字参数名也用 `fallback_reason`
16. **HybridRetriever __init__ 类型 ABC**(**v0.3 P0-7**):`vector: Retriever, keyword: Retriever`,不绑定具体 VectorRetriever / KeywordRetriever
17. **overview 哨兵透传**(**v0.3 P0-8;v0.4 PM 拍 Z**):`chunk.file_path == "__project_overview__"` 时**原样透传**到 SourceRef.file_path,不替换为人类可读标题;PM 拍 Z 接受 E 类 fallback sentinel 泄露(详 R12 技术债)
18. **VectorStoreError import**(**v0.3 P0-6**):_vector_retriever.py **不要** import VectorStoreError(它不 raise / 不 catch 这个类型;ruff F401 会抓)
19. **api/main.py 显式 import**(**v0.3 P2-1**):`from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever`;若发现旧 `from features.chat._retriever import KeywordRetriever` 直接引用 _retriever,删除
20. **mypy 沿 strict=false**(**v0.3 P2-3**):跑 `mypy features/chat/`;若报上游 main 已有 error,上报 PM 决定是否搭车 fix(不改 pyproject.toml)
21. **集成测试 project row 前置**(**v0.3 P2-2**):`ProjectStore.create_pending + mark_ready` 先建 project_status_record,再 ChunkingService 灌 chunks;否则 ProjectNotFoundError

### 测试 fixture 复用

- `tests/adapters/embedding/conftest.py::MockEmbeddingProvider`(TASK-301 落):单元测试 mock embedder
- `tests/adapters/storage/conftest.py`(TASK-204 / 302 落):tmp_path SQLite fixture
- 新增 `tests/features/chat/conftest.py::mock_keyword_retriever` + `mock_chunk_record_builder`(本任):见修改文件清单

### 性能预期

- VectorRetriever.search:embed(50-200ms,to_thread)+ vector_store.query(<10ms,单工程 < 5000 chunk)+ 转换(<1ms)= 总 60-250ms
- HybridRetriever.search:get_chunk_count(<1ms,R11)+ vector.search(60-250ms)= 总 60-250ms
- ChatService.handle_chat 整体响应预算:< 8s(01 § 11);RAG 部分预算 < 300ms

---

## 关联文档

- `docs/01_PROJECT_CONSTITUTION.md` v2.1 § 7 异步与并发 / § 8 工程规则 / § 11 用户体验底线
- `docs/02_ARCHITECTURE_OVERVIEW.md` v2.1 § 5 数据流 流 3(向量 RAG)/ § 6 决策 1-2
- `docs/03_TASK_INDEX.md` Week 3 / 验收标准
- `docs/04_ENGINEERING_STANDARDS.md` § 4 代码风格 / § 5 测试规范 / § 9 日志规范 / § 10 异常处理
- `docs/05_EXPLANATION_STYLE_GUIDE.md` D 类(QA)/ E 类(不确定)
- `docs/decisions/20260601-04-understanding-not-top-level-feature.md`
- `docs/decisions/20260603-09-architect-must-verify-not-assume.md`(反例 24 / 28 / 29 / 30 / 31 KPI 兑现)
- `docs/decisions/20260604-11-async-blocking-and-logger-exception-bans.md`(决策 11 决策 1 + 2)
- `docs/tasks/task-205-*.md`(ChatService 7 步流程 + Retriever ABC;**文件名 chat_service.py**;**v0.4 R2 P2-2:真实文件名由 Codex 第二棒 `ls docs/tasks/` 实地确认**)
- `docs/tasks/task-301-embedding-adapter.md`(EmbeddingProvider 实现)
- `docs/tasks/task-302-sqlite-vector-store.md`(VectorStore + ChunkRecord + QueryHit)
- `docs/tasks/task-303-*.md`(SourceType 7 类 + ChunkingService 单一入口 + D5 metadata 矩阵;**v0.4 R2 P2-2:真实文件名由 Codex 实地确认**)

---

**版本**:v0.5.1(最终版,R3.5 2 P1 + 2 P2 采纳)
**日期**:2026-06-07
**作者**:Claude(架构师,第十九任)
**关联宪法版本**:v2.1(冻结)
**触发 Task**:Week 3 第 4/7;TASK-303 完成后接力
**审查历程**:v0.1 → Codex Stage 0(2 FAIL)+ GPT instant 预审(14 条)→ v0.2 → GPT Pro R1(11 条)→ v0.3 → GPT Pro R2(13 条)+ R2.5 预审(6 条)→ v0.4 → GPT Pro R3(6 条)→ v0.5 → **v0.5.1 最终版**
**下一步**:PM 把 v0.5.1 + Codex 第二棒派活包传给 Codex → 实施代码 + 测试 + PR
