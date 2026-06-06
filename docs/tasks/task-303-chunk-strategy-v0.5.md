# TASK-303: 工程分块策略 + chunk metadata + source_text 模板(Week 3 第 3/7)

## 状态

🟢 v0.5(R4 GPT 1 P0 全采纳;**PM 同意修完直接进 Codex,不过 R5**)

---

## R4 反馈台账(2026-06-06,GPT R4 1 P0 全采纳,**v0.5 = 最终版,直接进 Codex**)

> R4 主判定:**v0.4 业务方案已通过**(#35 真实契约验证 / SourceType 输入契约 / #36 DI 守门 / 反例 31 升仪方向 全部已闭合);**仅剩 1 P0 = Stage 0 `awk` range 命令级错误**(起始行即结束 bug),会误阻断 Codex 实施。**PM 决定**:v0.5 修完此处 awk 命令后**直接进 Codex,不过 R5**。

### 1 P0 必改(全采纳 GPT 方案 B Python 脚本)

| # | 问题 | v0.5 修订位置 |
|:-:|---|---|
| P0-1 | **Stage 0 `awk '/async def add_chunks\(/,/^    async def /'` 在起始行立即结束** — `add_chunks` 定义行 `    async def add_chunks(...)` 同时匹配 start pattern(`async def add_chunks(` 子串)**和** end pattern(`^    async def ` 4 空格开头);awk range `p1, p2` 在同行匹配两 pattern 时只输出该行 → **函数体被忽略** → grep BEGIN/COMMIT/ROLLBACK/OperationalError 0 命中 → Codex 按"Stage 0 任一不符停手"**误判 TASK-302 不满足前置契约,误阻断实施**;**反例 28 同源**(Stage 0 命令"预期输出"本地实测或 PM 兜底 KPI 未兑现 — 架构师本地无 repo,凭印象写 awk 没实测)| **采纳 GPT 方案 B — Python 抽函数体脚本**(避开 awk range + 缩进 + 同行匹配三重坑;合并 5 项必需组群检查到单 Python 调用):合并原 R6 + 验收 #35 两条 awk 命令为**单个 `python - <<'PY' ... PY`** heredoc,检查 `BEGIN / COMMIT / ROLLBACK / OperationalError / sqlite_operation_failed` 五组关键字至少各命中一处;详 R6 + 验收 #35 修订段;**反例 28 KPI 转 PM 兜底**(架构师无 repo,Codex 实施前 PM 在真实 `adapters/storage/sqlite_vector_store.py` 上跑此 Python 脚本验证输出 + 必需组群命中)|

### R4 已闭合项(GPT 明示无需 R5 重审)

| 项 | R4 判定 |
|---|---|
| #35 真实契约验证方向 | ✅ 通过(`tests/features/chunking/test_vector_store_atomicity_contract.py` 真实 SqliteVectorStore + 真实 schema + monkeypatch fault-injection + `VectorStoreError("sqlite_operation_failed")` 公共契约 + duplicate rollback case 全部齐备)|
| SourceType 输入契约 | ✅ 通过(明确"唯一接口级类型注解收紧"+ 不动其他字段/方法签名)|
| #36 DI 守门 | ✅ 通过(运行时 fixture + `inspect.signature` + 多行 awk range)|
| 反例 31 升仪方向 | ✅ 通过(KPI 5 条 + 循环论证守门 (e) + R3 P0-1 同源证据)|

### 架构师反思 — 反例 28 同源,**不是反例 31**

R4 P0-1 根因:**反例 28**(Stage 0 命令"预期输出"本地实测或 PM 兜底)— 架构师本地无 repo + 凭印象写 awk 命令 + 没用脚本工具实测 = 反例 28 KPI 未兑现。

**不是反例 31 同源**(反例 31 是决策回避 / 软妥协 / 循环论证;这次是机械层凭印象错误)。反例 31 KPI 5 条**不是万能**,机械层(反例 21 / 24 / 25 / 28)仍需独立守门。

**v0.5 兜底兑现**:
- 采用 GPT 方案 B(Python 抽函数体)避开 awk range + 缩进 + 同行匹配三重边界
- **PM 兜底验证**:Codex 实施前 PM 在 `adapters/storage/sqlite_vector_store.py` 上跑一次 Python 脚本,验证输出非空 + 5 项必需组群全部命中(详 § 给 Codex 提示 § "PM 兜底验证步骤")
- 此 v0.5 兜底是**反例 28 KPI 完整闭环**(架构师无 repo → PM 兜底实测)

---

## R3 反馈台账(2026-06-06,GPT R3 1 P0 + 3 P1 全采纳,触发极窄 R4)

> R3 主判定:**v0.3 R2 修订 7 项总体闭合**(SourceType 定义顺序 / D16 性能澄清 / DI 注入链路 / 8→9 文件 / make_chunk_id 收紧 / 日志守门扩范围 / R6 方向闭合);**仅剩 1 P0 + 3 P1 验收 / Stage 0 命令精修**,**0 业务设计漏洞**;主体方案稳定。触发**极窄 R4**(GPT 明示:只审 5 项修订,深看 #35;D2-D16 不重审)。

### 1 P0 必改(全采纳,触发极窄 R4)

| # | 问题 | v0.4 修订位置 |
|:-:|---|---|
| P0-1 | **验收 #35 用 mock VectorStore 验证 TASK-302 原子性 = 循环论证** — mock 只能证明 mock 按测试作者设定方式 rollback,**不能证明真实 SqliteVectorStore 原子性**;TASK-302 公共契约已锁 `OperationalError → VectorStoreError("sqlite_operation_failed")`,#35 写 raw OperationalError 也违反契约。**又一次反例 31 同源**(决策回避的**循环论证隐蔽形态**:用 mock 自验证 mock 假装满足硬前提;反例 31 KPI 第一条 grep "若/可能/待" 抓不到这种形态)| **#35 大重写** — 改为真实 `SqliteVectorStore.add_chunks` fault-injection integration test:新增 `tests/features/chunking/test_vector_store_atomicity_contract.py`(放本任 tests 目录,验证 TASK-302 的下游契约,不算修改 TASK-302 实现);用**真实** SqliteVectorStore + 真实 schema init + monkeypatch aiosqlite Connection.execute 在第 k 次 INSERT 抛 OperationalError;断言对外异常 `VectorStoreError("sqlite_operation_failed")`(TASK-302 公共契约,**不是 raw OperationalError**);`chunk_count == 0`(整批 rollback);重试 add_chunks(全 N)→ `chunk_count == N`;**+ duplicate rollback case**(`add_chunks([new1, existing2])` → `ValueError("chunk_id already exists")` → 新 chunk `new1` 不被持久化);**反例 31 KPI 候选 (e) 同步**:决策 09 patch 草稿加"验收测试 / Stage 0 命令必须验证真实下游契约,不能 mock 自验证自身" |

### 3 P1 必改(全采纳,不升 R4)

| # | 问题 | v0.4 修订位置 |
|:-:|---|---|
| P1-1 | **§ 输入 / 上游关键契约残留 v0.1 矛盾陈述** — "本任不动接口,只追加 SourceType Literal 定义" + ChunkRecord 字段注释 `source_type: str # 本任收紧为 SourceType Literal(D1),不动字段类型(str 兼容)`;与 R1/R2 SourceType 真收紧方向冲突;Codex 可能误读"只追加 Literal,不改 ChunkRecord 字段注解" | § 输入 § 1 重写:`core/interfaces/vector_store.py(TASK-302 已 main freeze,本任仅做唯一接口级修改 — D1 类型注解收紧)`;ChunkRecord 字段注释改"`source_type: SourceType # 本任 D1 收紧,v0.2 R1 P0-1 + v0.3 R2 P0-1 锁定义顺序`";加明示段:"TASK-303 允许且必须做唯一接口级类型注解收紧;**除此不改** ChunkRecord 字段名 / 字段顺序 / 字段集 / VectorStore ABC 5 方法签名";**反例 30 同源**(v0.1 老陈述未跨段同步) |
| P1-2 | **#36 grep 守门假设函数签名单行,多行会误报** — `get_upload_service` 3+ Depends 必多行(100 字符行宽);`UploadService.__init__` 4-5 参数也必多行;现有 grep `def get_upload_service\(.*chunking_service.*Depends\(get_chunking_service\)` 会找不到匹配 → 验收**误报失败** | #36 改 **awk range 守门**(扫函数体多行)+ **Python `inspect.signature` 测试守门**:`assert "chunking_service" in inspect.signature(UploadService).parameters`;**反例 25 同源**(grep regex 假设单行)|
| P1-3 | **Stage 0 事务 grep 没限定 add_chunks 函数范围 + "async with execute 自动 transaction" 措辞错** — grep 扫整文件可命中别的方法 BEGIN/COMMIT(假阳性);aiosqlite `async with conn.execute(...)` 主要是 **cursor lifecycle 管理**,**不保证 transaction**(我凭印象写) | R6 + Stage 0 必查 改 **awk range 限定** `add_chunks` 函数体扫 BEGIN/COMMIT/ROLLBACK;**删除** "typical aiosqlite 模式是 async with self._conn.execute(...) 自动 transaction" 措辞;明示:"仅看到 `async with execute` **不足以证明事务**,必须在 add_chunks 函数体内看到显式 `BEGIN + COMMIT + 异常 ROLLBACK`,或看到经测试证明会 rollback 的 transaction context manager;**P0-1 fault-injection 测试是最终守门**";**反例 21 + 反例 25 同源**(grep 范围不限 + aiosqlite 行为凭印象)|

### R3 已闭合项(不需 R4 重审)

| R2 项 | R3 判定 |
|---|---|
| R2 P0-1 SourceType 定义顺序 | 已闭合(接口契约 + awk + runtime import 守门)|
| R2 P0-2 R6 partial 论证 | 方向闭合(只需修 #35 验证对象)|
| R2 P1-1 D16 性能矛盾 | 已闭合(承认 embed 1 次 + 验收 #30 守门)|
| R2 P1-2 8 → 9 文件残留 | 已闭合(active spec 全改)|
| R2 P1-3 DI 注入链路 | 设计闭合(只需修 #36 grep)|
| R2 P1-4 日志 grep 范围 | 已闭合(#27 三文件扫 + chunk_id 守门)|
| R2 P1-5 make_chunk_id 类型链路 | 已闭合(#3 守门)|

### 架构师反思 — 反例 31 升仪后第一次实战兑现 + 新维度发现

**反例 31 KPI 第一条 grep "若/可能/待/上游应/前端应/等等/TODO" 抓显式软妥协有效**;但 R3 P0-1 是**循环论证形态**(用 mock 验证 mock 假装满足硬前提)— **更隐蔽,关键词 grep 无法直接抓**。

**反例 31 KPI 候选 (e) 追加**(在决策 09 patch 草稿同步):
> **(e) 验收测试 / Stage 0 命令必须验证真实下游契约,不能用 mock / fake / stub 自验证自身;当 D 决策或 R 风险段标明"前置假设 X"时,验收必须 fault-inject / integration test 验证 X,不能用 mock 实现 X 自验证(循环论证)**

R3 反馈整体评估:**1 P0 + 3 P1 = 4/4 验收 / Stage 0 命令精修,0 业务设计漏洞**;主体方案稳定。

---

## R2 反馈台账(2026-06-06,GPT R2 2 P0 + 5 P1 全采纳,触发窄 R3)

> R2 主判定:**v0.2 R1 修订大部分有效**(SourceType 真收紧、ChunkingError feature-private、D14 反转、D16 cache hit 补偿均闭合);**新发现 2 P0** 都是潜在硬错:P0-1 定义顺序导致 NameError 风险;P0-2 D14+R6 partial write 论证自相矛盾。需出 v0.3 + **窄 R3**(只审 7 项修订清单,不重审 D2-D10 / R1 已通过项)。

### 2 P0 必改(全采纳,触发窄 R3)

| # | 问题 | v0.3 修订位置 |
|:-:|---|---|
| P0-1 | **D1 写"文件末追加 SourceType"但 ChunkRecord 字段类型注解收紧两段未同步** — 若 Codex 字面理解放在 ChunkRecord 后,**Python dataclass 字段类型注解在 class body 时立即 evaluate,会 NameError**;v0.2 只锁 grep 命中,未锁定义位置 | § 接口契约 § 1 重写:**SourceType / RESERVED_SOURCE_TYPES 必须定义在 ChunkRecord 之前**(显式锁死,删"文件末追加"措辞);修改文件清单 `core/interfaces/vector_store.py` 改动范围同步精修;验收 #3 加 **runtime python import 守门**(`python - <<'PY' from ... import ChunkRecord, RESERVED_SOURCE_TYPES; assert ... PY`);**反例 30 同源**(v0.1 "文件末追加" 措辞未与 v0.2 ChunkRecord 类型收紧 同步)|
| P0-2 | **D14 + R6 partial write 论证自相矛盾** — R6 说"前 50 dup no-op + 后 50 补写最终一致",但 D14 catch dup 时 `return 0`,**后 50 永远不写**;TASK-302 `add_chunks` 是批量接口,遇到第一个 dup 就抛 `ValueError`;**反例 31 候选同源**(我在 v0.2 用 R6 软论证"幂等天然处理"绕开 add_chunks 实际语义,**未拍硬决策**)| **采纳 GPT 方案 A** — 硬锁 TASK-302 `add_chunks` 单事务原子性为**本任前置硬假设**;R6 重写:不再"幂等天然处理 partial";Stage 0 必查 `SqliteVectorStore.add_chunks` 是否 BEGIN/COMMIT 单事务(实地 cat + 测试);若非原子 Codex **停手补 TASK-302**(不可硬上 — 决策 09 纪律 1);验收新增 #35 模拟 `add_chunks` 中途抛 OperationalError 后 `chunk_count == 0`,重试 add_chunks(全 N chunks)后 `chunk_count == N` |

### 5 P1 必改(全采纳,不升 R3)

| # | 问题 | v0.3 修订位置 |
|:-:|---|---|
| P1-1 | **D16 性能段自相矛盾** — 先写 "cache hit + chunk 已存在 → 无 embed 调用,因为 embed 在 add_chunks 之前",随后又承认 "cache hit 路径会先 embed source_text 再尝试 add_chunks";**反例 31 候选同源**(我用"等等"明确标记矛盾但 v0.2 finalize 时**没改完**)| D16 性能段重写:**删除** "无 embed 调用 / 几乎零成本" 残留;统一承认 cache hit + dup 路径会先调 `_embed_drafts([draft])` (~50ms 同步重活,via `asyncio.to_thread`),随后 add_chunks dup no-op return 0;**MCS 阶段可接受,本任不加 `_overview_chunk_exists` 预检**(KISS,避免引入额外 SQL query)|
| P1-2 | active spec 仍写 "8 文件"(D10 段);新增文件清单已改 9,但 D10 段 / 给 Codex / 验收 #4 残留 | grep "8 文件" 全文修;D10 段 + 验收 #4 + 给 Codex 提示 全部 "8 文件" → "**9 文件**" |
| P1-3 | **DI 注入链路未锁** — v0.2 加了 `get_chunking_service`,但 UploadService / ProjectOverviewService **构造函数 + 装配 dependency 都未同步**;Codex 实施可能用 `app.state` 直接取(违反 DI 模式)| § 接口契约 § 9 加:**UploadService.__init__ / ProjectOverviewService.__init__ 加 `chunking_service: ChunkingService` 参数**;`get_upload_service` / `get_overview_service` 同步加 `Depends(get_chunking_service)`;修改文件清单 `upload_service.py` / `overview_service.py` 改动范围加"**构造函数加 chunking_service 参数**" + `dependencies.py` 改动范围加"**get_upload_service / get_overview_service 同步注入 chunking_service**";验收新增 #36 fixture 测试 `overview_service._chunking_service is app.state.chunking_service` + UploadService 同款 |
| P1-4 | 日志 grep 守门 #27 只扫 `features/chunking/`,但 best-effort try/except + logger 在 `features/ingest/upload_service.py` 和 `features/overview/overview_service.py` 中(本任已修改)| 验收 #27 grep 扩到本任**所有修改文件**:`features/chunking/ + features/ingest/upload_service.py + features/overview/overview_service.py`;扩字段守门:`source_text / docstring / parameter / chunk_id` 全部禁出任何 logger level |
| P1-5 | `make_chunk_id(project_id: str, source_type: str, ...)` 仍是 str,**类型链路弱口**(ChunkRecord / ChunkDraft.source_type 已收紧 SourceType,helper 应同步)| § 接口契约 § 4 `_chunk_id.py` 签名改 `make_chunk_id(project_id: str, source_type: SourceType, ...)`;import `SourceType` from `core.interfaces.vector_store`;验收 #3 加 grep 守门 `def make_chunk_id` 行含 `source_type: SourceType` |

### R2 已通过项(不需 R3 重审)

| 项 | R2 判定 |
|---|---|
| SourceType 7 枚举集合 | 集合合理(只需修定义顺序 P0-1)|
| `ChunkDraft` 独立文件 | 通过 |
| `ChunkingError(RuntimeError)` feature-private | 通过(不进 core / ERROR_MAP 守门已清楚)|
| D14 去掉 `delete_by_project_id` | 方向通过(只需修 R6 partial 论证 P0-2)|
| `exc.args == ("chunk_id already exists",)` | 通过 |
| D15 chunk 数公式 | 通过(已排除 FILE_SLX / FILE_MAT / PARAMETER / project_overview)|
| `m_file.symbol_name = None` | 通过(验收 #33 已覆盖)|
| `.env.example` + AppSettings 6 字段 | 通过 |
| 日志禁止 source_text / docstring / parameter | 方向通过(只需扩 grep 范围 P1-4)|
| D16 cache hit 补偿 | 方向通过(只需修性能段矛盾 P1-1)|

### 架构师反例 31 升仪决定(v0.3 主动升仪)

本会话累计 **4 处同源** "决策回避" 漏洞:
- **R1 P0-1 软妥协**("向后兼容"避 TASK-302 漂移,实际 TASK-302 P2-2 预留 + Literal runtime 兼容 str = 零成本)
- **R1 P0-4 转嫁**("前端 / 上游应清 overview cache",实际本任内 D14 反转 + D16 cache hit 补偿可闭环)
- **R2 P0-2 软论证未拍板**(R6 "幂等天然处理 partial" 绕开 add_chunks 实际语义,**v0.2 finalize 时已能识别**)
- **R2 P1-1 用"等等"明确标记矛盾却没改完**(D16 性能段)

**4 同源 + 跨 2 次审查 + 自我"等等"标记仍未改**,已满足决策 09 升仪标准(类比第十五任 KPI / 第十六任反例 27/28 / 第十七任反例 29/30 同款"跨多次审查同源")。

**v0.3 主动升仪反例 31 入决策 09**(搭车 chore patch);**升仪名称**:"**架构师识别到问题但回避拍硬决策(决策回避 / 软妥协 / 转嫁 / 用'等等'标记不改)**";详 § 输出 搭车 chore 段。

---

## R1 反馈台账(2026-06-06,GPT R1 4 P0 + 9 P1 + 3 P2 全采纳,触发窄 R2)

> R1 主判定:**v0.1 方向基本成立**(D1-D13 / D15 主方案保留);**新发现 4 P0** 全部精修边界(SourceType 真收紧 / D14 dup 检测 / ChunkingError 定义 / chunk_project 重建闭环),触发**窄 R2**(只审 7 项修订清单,不重审 D2-D10)。

### 4 P0 必改(全采纳,触发窄 R2)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P0-1 | **D1 SourceType 没真收紧到 `ChunkRecord.source_type` 类型链路** — v0.1 写"`ChunkRecord.source_type: str` 保持(向后兼容);只测试断言"是软妥协;Literal 在 runtime 是 str 子类型完全兼容,TASK-302 P2-2 预留给本任收紧 | § 接口契约 1 ChunkRecord 字段类型 `str → SourceType`;ChunkDraft.source_type 同步;§ 输出修改文件清单 + 不动文件 同步明示是"类型注解收紧"(TASK-302 P2-2 预留合法变更);验收 #3 加 `grep 'source_type: SourceType'` 静态类型守门 |
| P0-2 | **D14 dup 检测用 `str(exc)` 自相矛盾** — 验收 #26 明禁 `grep 'str\(exc'` 0 命中,但 D14 伪代码用 `if "chunk_id already exists" in str(exc)`;Codex 按 D14 实现会打挂验收 #26;**反例 30 同源**(规则一段写,实现段漏同步) | § 接口契约 3 ChunkingService.build_embed_store_overview_chunk + D14 伪代码 改 `exc.args == ("chunk_id already exists",)` 精确匹配;**任何 logger level 严禁出 source_text / docstring / parameter value**(P1-6 扩展);验收 #22 + #26 同步修订 |
| P0-3 | **`ChunkingError` 被使用但未定义、未列入交付物** — D11 伪代码 `raise ChunkingError("embedding_count_mismatch")`;新增文件 8 个清单无 `_errors.py`,异常树也没扩;Codex 会未定义符号 / 或擅自改 `core/domain/exceptions.py` 扩大 ERROR_MAP;**反例 23 同源** | 新增 `features/chunking/_errors.py` 定义 feature-private `ChunkingError(RuntimeError)`;**不进 core,不进 HTTP ERROR_MAP**;§ 输出新增文件 8→9;§ 接口契约 加新段 8;验收新增 #29 `grep 'class ChunkingError' features/chunking/_errors.py` + 守门 `core/ + api/middleware/error_handler.py` 0 命中 |
| P0-4 | **D14 chunk_project 重建会删除 `project_overview` chunk,文档承认 cache hit 后不补回 — v0.1 R5 自己承认却没闭环** — "前端 / 上游应清 overview cache" 是转嫁,不是本 Task 可验证工程闭环;**新踩坑维度候选(反例 31)**:架构师识别到问题但回避拍硬决策 | **D14 主决策反转**:`build_embed_store_project_chunks` **去掉** `delete_by_project_id(project.id)`;改 duplicate no-op(同 project_id 视为不可变 MCS 快照,重复触发 = no-op,与 chunk_overview 同款 exc.args 检测);R5 风险段消除(原风险因方案改不复存在);**新增 D16 overview cache hit 补偿**(cache hit / miss 都触发 chunk_overview,dup no-op 静默 debug);验收 #21 + #22 同步修订 + 新增 #30 cache hit 补偿测试 |

### 9 P1 必改(全采纳,不升 R2)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P1-1 | 新增文件清单 8 个但树里只列 7 个;`ChunkDraft` 位置含糊 | § 输出新增文件 改 9 个:加 `_chunk_draft.py`(从 chunking_service 拆出避免超 200 行)+ `_errors.py`(P0-3)|
| P1-2 | 修改文件 6 个漏 `.env.example`(验收 #24 要求改但未列入)| § 输出修改文件 6→7,加 `.env.example` |
| P1-3 | D15 "chunk 数 == 节点数 + mat_variables" 提示错(节点数含 skip 的 FILE_SLX / FILE_MAT / PARAMETER)| D15 chunk 数公式改 `emit 节点数(FILE_M + FUNCTION + BLOCK + SUBSYSTEM)+ sum(mat.variables)`;`project_overview` 不混入 chunk_project 路径 |
| P1-4 | D5 metadata `m_file.symbol_name = m_file.file_role` 语义不准(file_role 是角色非 symbol)| D5 metadata 矩阵改 `m_file.symbol_name = None`(file 名已由 file_path 表达)|
| P1-5 | overview cache hit 路径没"补 overview chunk"机制(TASK-303 上线前已 cache 项目 / chunk 写失败 cache 成功后,后续 cache hit 不再补)| **新增 D16**:cache hit / miss 都 best-effort 调 `build_embed_store_overview_chunk`(idempotent + dup no-op 静默);ProjectOverviewService.get_or_generate 伪代码同步;验收新增 #30 |
| P1-6 | D7 / D9 允许 DEBUG 记录 `source_text` 的口子应删 — source_text 是 SQLite 显式例外,不是日志例外 | D7 / D9 改"**任何 logger level 都不得出** source_text / docstring / parameter value;本地调试用 pytest assertion / snapshot 文件,不走 logger";验收 #26 grep 扩 `'logger\.(debug\|info\|warning\|error).*source_text\|.*docstring\|.*parameter' features/chunking/` 0 命中 |
| P1-7 | overview embedding 路径缺 `len(embeddings) != len(drafts)` 校验 | § 接口契约 3 ChunkingService 抽公共 helper `_embed_drafts(drafts) -> list[list[float]]`,project + overview 两路径都走;D11 伪代码同步 |
| P1-8 | `FileInfo.description` 没字段级上限(只靠总长 1024,description 可挤掉文件角色 / 函数数)| § 接口契约 5 加 `_DESCRIPTION_MAX_CHARS_DEFAULT = 300` 模块级常量 + AppSettings `chunking_description_max_chars: int = Field(default=300, ge=0, le=1000)`;§ 输出 修改文件 app/config.py 改 6→7 字段 |
| P1-9 | `SourceType` grep 守门只 grep `Literal[`,Codex 保留 `source_type: str` 验收会误过 | 验收 #3 加:`grep 'source_type: SourceType' core/interfaces/vector_store.py`(命中 1)+ `grep 'source_type: SourceType' features/chunking/_chunk_draft.py`(命中 1)+ mypy 守门 |

### 3 P2 建议(全采纳)

| # | 建议 | v0.2 修订位置 |
|:-:|---|---|
| P2-1 | `make_chunk_id` 空 identifier 处理未说明 | § 接口契约 4 加 `if not raw_id: raise ValueError("empty_chunk_identifier")`;验收新增 #31 |
| P2-2 | subsystem child block names 排序规则未明示(可能 fixture 顺序漂移导致 snapshot 不稳)| § 接口契约 5 `build_slx_subsystem_source_text` 明示"child_block_ids 按 SlxModel.subsystems[name] dict 内**原始顺序**(parser 输出顺序)取前 top_n;不重排" |
| P2-3 | TASK-304 / 前端不应把 `project_overview.file_path = "__project_overview__"` 渲染为可点击文件路径 | § 关联文档 TASK-304 接力点加:"`source_type == "project_overview"` 时,citation label 渲染为'项目总览',不按 file_path 跳转" |

---

## pre-R1 反馈台账(2026-06-06,GPT 5 P0 + 11 P1 + 5 P2 全采纳)

> **pre-R1 工艺说明**:架构师在写正式 v0.1 之前,先把 D 决策候选(含 trade-off)丢 GPT 做预审(pre-R1),目标降低 R1 大改风险。本次 pre-R1 抓 5 P0 全部"决策上下游硬约束兼容性"漏洞,正式 v0.1 已全采纳。

### 5 P0 必改(全采纳,v0.1 已反映)

| # | 问题 | v0.1 修订位置 |
|:-:|---|---|
| P0-1 | `ChunkRecord.embedding` 必填(非 Optional),"chunks_unembedded" 在类型上不合法 | 新增 **D13** ChunkDraft 中间类型;接口契约 § 1 加 ChunkDraft dataclass;ChunkingService 返回 `list[ChunkDraft]`,embed 后 materialize 成 ChunkRecord |
| P0-2 | ProjectGraph NodeType 7 类无 MAT_VARIABLE;`mat_variable` chunk 必须从 Project.mat_files.variables 直取 | **D4** 来源改 Project.mat_files.variables;**D11** 加"来源矩阵"(D15 详);删除 v0.1 早期"完全基于 ProjectGraph 遍历"表述 |
| P0-3 | `chunk_id` 重复 → TASK-302 P1-6 锁的 `ValueError("chunk_id already exists")`,我口头 "INSERT OR IGNORE / 先 delete" 未拍板 | 新增 **D14** chunk rebuild/duplicate 策略:`chunk_project` 先 `delete_by_project_id` 重建;`chunk_overview` 固定 ID + dup no-op<br>**⚠️ v0.2 R1 P0-4 又反转**:`chunk_project` 不再 delete_by_project_id,改 add + dup no-op(详 v0.2 R1 反馈台账 P0-4) |
| P0-4 | 扩 `ProjectStatus.rag_status` 是 P0 范围漂移(schema migration + API + 前端) | **D12** 改"不扩 ProjectStatus";TASK-304 通过 `vector_store.get_chunk_count(project_id) == 0` 判断 RAG 不可用 fallback KeywordRetriever |
| P0-5 | chunk 失败 vs `mark_ready` 顺序未锁,直接违反 D12 失败不阻塞 | **D11** 加"事务边界 / 状态边界":parse + `mark_ready` 主链路;chunk + embed + add_chunks **包裹 try/except 异常不反向修改 ProjectStatus** |

### 11 P1 必改(全采纳,v0.1 已反映)

| # | 问题 | v0.1 修订位置 |
|:-:|---|---|
| P1-1 | `SourceType` 必须定义在 `core/interfaces/vector_store.py`(与 ChunkRecord 同文件),不能在 features/chunking 让 core 反向 import | **D1** 定义位置 core/interfaces;features/chunking 只 import |
| P1-2 | teaching_unit 标 reserved + 改"避免后续再改 core 类型契约"(Literal 是 Python 类型 非 DB migration) | **D1 / D6** 措辞修正;验收加"chunk_project 不产 source_type=teaching_unit chunk" |
| P1-3 | NodeType → SourceType 映射表 + skip 规则缺失 | 新增 **D15** 映射表 |
| P1-4 | docstring / parameters 字段级 sanitizer | **D7** 加字段级截断常量(`_DOCSTRING_MAX_CHARS = 300` / `_PARAM_VALUE_MAX_CHARS = 80` / `_MAX_PARAMS_PER_BLOCK = 12`)+ **禁 raw_code 引用 grep 守门** |
| P1-5 | D8 理由别宣称精确 token 边界 | **D8** 改"产品侧最小必要预算 非 tokenizer 精确边界" |
| P1-6 | chunk_id 加 hash suffix 防碰撞 + 完整 chunk_id 不进生产日志 | **D9** chunk_id 格式 `{project_id}::{source_type}::{safe_id}::{sha1[:12]}`;日志只记 project_id / source_type / chunk_count / error_class |
| P1-7 | D10 锁依赖方向 | **D10** 加"可依赖 core/domain + core/interfaces + features/overview/overview_schemas.py;禁 import overview/_*.py 私有 + adapters" |
| P1-8 | UploadService 不直接持 ProjectGraphBuilder | **D11** ChunkingService 内部注入 `ProjectGraphProvider` Protocol 调 builder;**ChunkingService 单一入口** `build_embed_store_project_chunks(project)` |
| P1-9 | 空 batch 边界 | **D11** 加 `if not drafts: log info + return`;验收加空工程 / 空 .mat / 无 block .slx 测试 |
| P1-10 | project_overview chunk 的 metadata 填充规则缺失 | **D5** 加 metadata population matrix(7 类全覆盖)|
| P1-11 | D1 不收 entry/unresolved 但要明确不比 KeywordRetriever 倒退 | **D1** trade-off 加:entry_points / execution_flow 折入 `project_overview.source_text`;unresolved_symbols 暂不入向量库,由 TASK-304 KeywordRetriever fallback / TASK-307 接管 |

### 5 P2 建议(全采纳)

| # | 建议 | v0.1 修订位置 |
|:-:|---|---|
| P2-1 | 每类 chunk 计数验收输出 | § 验收 #N 加 chunk 覆盖率日志(`m_file=N / m_function=N / slx_block=N / slx_subsystem=N / mat_variable=N / project_overview=1`)|
| P2-2 | 7 类 source_text 模板 snapshot test | § 验收 + 测试矩阵加 snapshot |
| P2-3 | `_MAX_SUBSYSTEM_CHILD_BLOCK_NAMES = 20` 锁常量 | **D7** 加该常量 |
| P2-4 | head-only 截断保留;Phase 2 评估 head+tail | **D8** 保留 head-only;§ 接力点 加 Phase 2 hint |
| P2-5 | 审批级别维持核心二审 R1+R2 | § 审批级别 保持 |

---

## 审批级别(反例 18 自检 5 维度)

| 维度 | 评分 | 理由 |
|---|---|---|
| 决策密度 | **高**(D1-D15)| 7 SourceType + 4 chunk 粒度 + source_text 模板 + 7 字段 sanitizer + 长度策略 + chunk_id 格式 + 代码位置 + 双挂载点 + best-effort + ChunkDraft + 幂等 + NodeType 映射 + 失败语义 |
| 下游扩散 | **强** | TASK-304(VectorRetriever 整合)直接消费 chunk 数据 + Literal;chunk 化粒度选错 = Week 3 RAG 链路重做 |
| 用户可见 | **中** | chunk 化质量直接决定 0.2 版本 citation 覆盖率 ≥ 90% / 评测平均分 ≥ 70 是否达标 |
| 异步 / LLM 首次定型 | 否 | 沿用 TASK-302 决策 11 决策 1 to_thread 模式;无新 lifespan 装配 |
| 隐私 / 安全 | **是**(再定型)| `source_text` 内容形态 = 02 § 12 / 01 § 9 显式例外的实际边界;TASK-302 R2 已开例外,本任 7 类 chunk 各自模板都是新增"显式例外"载荷 + 字段级 sanitizer 是首次定型 |

→ **走 GPT 二审 R1 + R2**(沿用 TASK-104 / 107 / 205 / 302 核心二审模式)

---

## 上下文

### mxa-tutor 项目快速 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。学生上传 .zip 工程包(.m / .slx / .mat),后端做 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。

**当前进度(实地核查 main HEAD `83a7948`)**:20/32 Task 完成(TASK-302 SQLite 向量存储 已 merge);Week 3 进度 [✅✅⬜⬜⬜⬜⬜] 2/7,**本 Task = Week 3 第三棒(3/7)**。

### 数据流位置(02 § 2)

```
[Parser] SlxModel / MFile / MatMetadata / FileInfo / file_dependencies
   ↓  无 LLM,纯结构化(TASK-101 / 102 / 103 / 104 / 105)
[ProjectGraph] nodes / edges / entry_points / execution_flow / unresolved_symbols(TASK-107)
   ↓  调 LLM 基于 ProjectGraph 生成
[ProjectOverview]  教学化输出 12 字段 + 5 子 schema,带 SourceRef 证据(TASK-203 / 207)
   ↓  Week 3 向量化(TASK-301 ✅ + 302 ✅ + 303 ★ + 304 ⬜)
[Vector RAG] Embedding(TASK-301)→ chunk 化(本 Task)→ SQLite BLOB(TASK-302)→ 余弦检索(TASK-302)→ ChatService 整合(TASK-304)→ 强证据问答
```

**本 Task 在数据流的位置:chunk 化层** — 把 Project + ProjectOverview 转成 ChunkRecord 入 SQLite 供向量检索。

- **消费 TASK-301 EmbeddingProvider**(`adapters/embedding/sentence_transformer.py`)— 把 source_text 批量 embed
- **消费 TASK-302 VectorStore.add_chunks**(`adapters/storage/sqlite_vector_store.py`)— 落库 ChunkRecord
- **遵循 TASK-302 ChunkRecord 14 字段契约**(已 main freeze;本任**仅做一处接口级修改**:`source_type` 类型注解 `str → SourceType`,详 D1)

**不做**:VectorRetriever / Retriever 替换 ChatService(TASK-304)/ 跨工程检索 / chunk 化以外的事 / TeachingUnit chunk 实际生成(Phase 2 接力)。

### 类比 anchor

- **node_id 命名空间 helper**:`features/overview/_node_id.py` `make_*_id` 系列(commit `dd7a1da` 等 TASK-107 产物)— 本任 `chunk_id` 命名空间 helper 完全照抄模式 + 加 hash suffix
- **节点 builder**:`features/overview/_pg_nodes.py` `build_*_nodes` 系列 — 本任 chunk 化遵循 NodeType → SourceType 映射(D15)
- **source_text 模板**:`features/chat/_retriever.py` KeywordRetriever 5 类隐式模板(commit `dd7a1da` TASK-205 产物)— 本任 source_text 模板 沿用 m_function / slx_block 模式 + 扩 4 新类型
- **service 装配模式**:`features/overview/overview_service.py` ProjectOverviewService(TASK-203 产物)— 本任 ChunkingService 类比构造
- **lifespan + DI**:`api/main.py` + `api/dependencies.py`(TASK-302 已 装 embedder + vector_store)— 本任加 chunking_service 装配

### 关键宪法 / 决策引用

- **01 § 7 分层**:core/ 不允许 import adapters/ features/;features 只依赖 core 接口;**SourceType 必须在 core 层**(D1 + P1-1)
- **01 § 8**:文件 ≤ 300 行(本任 features/chunking/ 拆 5-6 个 .py,每个 ≤ 200 行预估)
- **01 § 9 + 02 § 12**:数据库不存原文;日志不记原文;**`source_text` 是 TASK-302 R2 显式例外**(继承,本任 7 类 chunk 各自 source_text 模板逐一论证 在 § 隐私)
- **02 § 2 数据流**:Parser → ProjectGraph → 教学输出 → Vector RAG;**chunk 化 = "教学输出 → embeddable text" 桥接层**
- **02 § 6 决策 1**:SQLite + sentence-transformers,MCS 单工程小够用,**升级阈值 chunk > 5000 或用户 > 1000**(本任 chunk 总量预估 100-500/工程 远低于阈值)
- **02 § 6 决策 5**:.mat 只做元信息(变量名 / 类型 / shape),**本任 mat_variable chunk 沿用元信息原则**
- **02 § 6 决策 7**:教学理解中间层(ProjectGraph / TeachingUnit)不抽顶层 feature — **chunking 不是教学理解中间层(是 RAG 基础设施层),不在决策 7 约束范围**(D10 详)
- **决策 11 决策 1**:async def 内同步重活必须 `await asyncio.to_thread(sync_func, ...)`(TASK-302 已实战通过,本任 embedder + project_graph_builder 同款)
- **决策 11 决策 2**:logger.error metadata-only,**禁 `logger.exception` / `str(exc)`**(本任 chunk 化失败日志严格遵守)
- **决策 06**:Codex 可读仓库文件,文档引用路径不内联全文
- **决策 08**:PM 验 git 三件套 + 字节级 Python 改 docs(本任搭车 chore 沿用)
- **决策 09 反例 26 + 27 + 28 + 29 + 30 + 第二十一任 KPI**:scripts/* + make check + cat pyproject.toml + Stage 0 命令本地实测 + 接口跨段 grep + 变更跨段同步 + 严禁因 self-confirmation 跳过机械检查

---

## 输入(前置依赖)

### 已合并 Task

✅ TASK-001 / 002 / 101 / 102 / 103 / 104 / 105 / 106 / 107 / 108 / 201 / 202 / 203(`?`,ProjectOverviewService 入口)/ 204(`5fba99b`,SQLite anchor)/ 205(`dd7a1da`,KeywordRetriever anchor)/ 206 / 207 / **301**(`85b86d3`,EmbeddingProvider 实现)/ **302**(`83a7948`,SQLite VectorStore + ChunkRecord — main HEAD)。

### 上游关键契约(实地核查 main HEAD `83a7948`,本 Task 不动)

#### 1. `core/interfaces/vector_store.py`(TASK-302 已 main freeze;**本任仅做唯一接口级修改 — D1 类型注解收紧**)

**v0.4 R3 P1-1 修订**:TASK-302 main HEAD 当前为 `source_type: str`;**TASK-303 允许且必须做唯一接口级类型注解收紧**:`ChunkRecord.source_type: str → SourceType`(TASK-302 P2-2 注释明示预留);**除此不改** ChunkRecord 字段名 / 字段顺序 / 字段集 / 其他字段类型 / VectorStore ABC 5 方法签名。

```python
@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    project_id: str
    source_type: SourceType         # ★ v0.2 R1 P0-1 + v0.3 R2 P0-1:类型注解 str → SourceType
    file_path: str                  #    (TASK-302 main HEAD 是 str;本任唯一接口级修改;
    symbol_name: str | None         #     SourceType 定义必须在此 ChunkRecord 之前 — 防 NameError)
    line_range: tuple[int, int] | None
    block_id: str | None
    block_name: str | None
    block_type: str | None
    parent_subsystem: str | None
    source_text: str                # 02 § 12 / 01 § 9 显式例外,见 § 风险 R2
    embedding: list[float]          # ★ 必填(非 Optional);ChunkDraft 中间类型不含此字段(D13)
    model_name: str                 # ★ 必填
    created_at: datetime | None = None
```

VectorStore ABC 5 方法(**本任不动签名**):`add_chunks(list[ChunkRecord]) -> None` / `query(...)` / `delete_by_project_id(project_id) -> int` / `get_chunk_count(project_id) -> int` / `aclose()`。

**TASK-302 公共契约**(本任硬假设,v0.3 R2 P0-2 + v0.4 R3 P0-1):
- **重复 chunk_id**:`add_chunks` 任一 chunk_id 已存在 → `ValueError("chunk_id already exists")`(`exc.args == ("chunk_id already exists",)` 单元素 tuple);本任 D14 利用此契约做 dup no-op 幂等
- **SQLite OperationalError 翻译**:`add_chunks` 内部 SQLite `OperationalError` → 对外抛 `VectorStoreError("sqlite_operation_failed")`(不暴露 raw `OperationalError`)
- **单事务原子性**:`add_chunks(chunks)` 是单事务批量写入,任一 row 失败 → 整批 rollback;**不允许 partial chunks 状态**;本任 D14 dup no-op 设计依赖此前置(详 R6 + 验收 #35 fault-injection 守门)
- **架构师 Stage 0 必查**:若发现 TASK-302 当前实现未满足"单事务原子性 + OperationalError 翻译",**Codex 停手抛冲突给 PM,不可硬上**(决策 09 纪律 1)

#### 2. domain 数据结构全字段(实地 cat)

```python
# core/domain/m_file.py
@dataclass
class MFunction:
    name: str
    inputs: list[str]
    outputs: list[str]
    line_range: tuple[int, int]        # 非可选
    docstring: str | None

@dataclass
class MFile:
    file_path: str
    file_role: str
    functions: list[MFunction]
    imports: list[str]
    uses_toolbox: list[str]
    raw_code: str                      # ★ 隐私敏感;本任 chunker 禁引用(D7 + grep 守门)

# core/domain/slx_model.py
@dataclass
class SlxBlock:
    block_id: str
    name: str
    block_type: str
    parameters: dict[str, str]
    position: tuple[int, int, int, int]
    parent_subsystem: str | None
    is_masked: bool = False
    is_library_link: bool = False
    is_model_reference: bool = False

@dataclass
class SlxModel:
    file_path: str
    name: str
    blocks: list[SlxBlock]
    lines: list[SlxLine]
    subsystems: dict[str, list[str]]   # ★ 不是独立 dataclass;subsystem_name → block_id 列表
    solver_config: dict[str, str]
    parse_warnings: list[str]

# core/domain/mat_metadata.py
@dataclass
class MatVariable:
    name: str
    var_type: str
    shape: tuple[int, ...]
    likely_role: str | None
    first_field_names: list[str]

@dataclass
class MatMetadata:
    file_path: str
    file_size_bytes: int
    variables: list[MatVariable]       # ★ mat_variable chunk 来源(D4)

# core/domain/project.py
@dataclass
class FileInfo:
    relative_path: str
    file_type: str
    size_bytes: int
    description: str | None = None

@dataclass
class Project:
    id: str
    name: str
    project_type: ProjectType
    files: list[FileInfo]
    slx_models: list[SlxModel]
    m_files: list[MFile]
    mat_files: list[MatMetadata]
    created_at: datetime
    file_dependencies: dict[str, list[str]]

# core/domain/project_graph.py
class NodeType(Enum):
    FILE_M = "file_m"
    FILE_SLX = "file_slx"
    FILE_MAT = "file_mat"
    BLOCK = "block"
    SUBSYSTEM = "subsystem"
    FUNCTION = "function"
    PARAMETER = "parameter"            # ★ Phase 2 候选;本任不 emit chunk(D15)

@dataclass
class ProjectNode:
    id: str
    type: NodeType
    label: str
    source_ref: SourceRef              # ★ 每节点必带
    metadata: dict[str, str]

@dataclass
class ProjectGraph:
    project_id: str
    nodes: list[ProjectNode]
    edges: list[ProjectEdge]
    entry_points: list[str]            # ★ 折入 project_overview chunk(D1 P1-11)
    execution_flow: list[str]          # ★ 同上
    data_flow: list[str]
    control_flow: list[str]
    unresolved_symbols: list[str]      # ★ 本任不入向量库;留 KeywordRetriever fallback(D1 P1-11)
```

#### 3. `features/overview/overview_schemas.py`(TASK-207 已 freeze,本任不动)

```python
ProjectTypeValue = Literal["control_system", "signal_processing", ...]  # 7 类
class ProjectOverview(_StrictBaseModel):
    project_title: str
    project_type: ProjectTypeValue
    one_sentence_summary: str
    main_entry_files: list[EntryFileEntry]      # 1-3
    main_simulink_models: list[SimulinkModelEntry]
    main_execution_flow: list[str]              # 3-7,本任 project_overview source_text 含
    key_files: list[KeyFileEntry]               # 3-8
    key_blocks: list[BlockEntry]                # ≤10
    knowledge_points: list[str]                 # 3-6
    beginner_reading_order: list[str]           # 3-6
    likely_confusing_points: list[str]          # 2-5
    evidence: list[SourceRefEntry]              # ≥3
```

#### 4. service 入口签名(D11 挂载点)

```
# 挂载点 1:features/ingest/upload_service.py
class UploadService:
    async def process(self, project_id: str, zip_bytes: bytes, name: str) -> None  # line 116
    def _run_parse_sync(...)                                                        # line 155(同步重活,to_thread 桥接)
    
# 挂载点 2:features/overview/overview_service.py
class ProjectOverviewService:
    async def get_or_generate(self, project_id: str) -> ProjectOverview             # line 57
    def _build_graph_sync(self, project: Project) -> ProjectGraph                   # line 85

# 下游消费(TASK-304 接力)
class ChatService:
    async def handle_chat(...)                                                       # line 54
    # DEFAULT_TOP_K = 8(与 TASK-302 D9 vector_top_k 对齐)
```

#### 5. KeywordRetriever 现有 source_text 模板(D7 类比 anchor)

```python
# features/chat/_retriever.py
# file_info  (line 125): f"文件 {file_info.relative_path},类型 {file_info.file_type}。{description}"
# m_function (line 142): f"函数 {func.name} 位于 {m_file.file_path},输入 {func.inputs},输出 {func.outputs}。{func.docstring or ''}"
# slx_block  (line 170): f"Block {block.name}({block.block_type}) 位于 {model.file_path}/{parent},参数 {params}"
# entry      (line 197): _truncate(f"工程执行入口或流程节点:{entry}")
# unresolved (line 206): _truncate(f"未解析符号:{symbol}")
# _PARAM_VALUE_MAX_CHARS 已在 KeywordRetriever 类常量中(用于截断单 parameter value)
```

---

## 输出(交付物)

### 新增文件(9 个 — v0.2 R1 P1-1 + P0-3)

```
features/chunking/
├── __init__.py
├── README.md                           ~30 行,模块用途
├── chunking_service.py                 ~180 行,ChunkingService 单一入口 + _embed_drafts helper
├── _chunk_draft.py                     ~30 行,ChunkDraft dataclass(v0.2 R1 P1-1 拆出)
├── _errors.py                          ~20 行,ChunkingError feature-private(v0.2 R1 P0-3 新增)
├── _chunk_id.py                        ~60 行,make_chunk_id 命名空间 + hash + 空 ID 校验(D9 + P2-1)
├── _source_text_templates.py           ~200 行,7 类模板 + sanitizer(D7 + R1 P1-8 description)
├── _project_chunker.py                 ~150 行,chunk Project → 6 类 ChunkDraft
└── _overview_chunker.py                ~50 行,chunk ProjectOverview → 1 ChunkDraft
```

预估总 ~720 行,平均每文件 ~80 行,均 < 01 § 8 的 300 行约束。

**测试新增**(由 Codex 实施):

- `tests/features/chunking/test_chunking_service_unit.py`(~280 行)— 单元 + dup no-op + cache hit 补偿
- `tests/features/chunking/test_source_text_templates_unit.py`(~200 行)— 7 类模板 snapshot(P2-2)
- `tests/features/chunking/test_chunk_id_unit.py`(~90 行)— 命名空间 + hash 碰撞 + 空 ID 抛 ValueError(P2-1)
- `tests/features/chunking/test_errors_unit.py`(~30 行)— ChunkingError 定义 + 不在 core 守门(P0-3)
- `tests/features/chunking/test_integration.py`(~150 行)— UploadService + ChunkingService + 真 embedder 端到端(`RUN_EMBEDDING_INTEGRATION=1` skipif)
- `tests/features/chunking/conftest.py`(~50 行)— fixture / mock helper

### 修改文件(7 个 — v0.2 R1 P1-2 加 .env.example)

| 路径 | 改动范围 | 决策 |
|---|---|---|
| `core/interfaces/vector_store.py` | (a) **`SourceType = Literal[...]` 7 枚举 + `RESERVED_SOURCE_TYPES = frozenset({"teaching_unit"})` 必须定义在 ChunkRecord 之前**(v0.3 R2 P0-1 锁死定义顺序,防 NameError;不写"文件末追加");(b) **改 `ChunkRecord.source_type` 类型注解 `str → SourceType`**(v0.2 R1 P0-1 强收紧;TASK-302 P2-2 预留合法变更;runtime 完全兼容 main 已落数据);(c) 若文件未启用 `from __future__ import annotations` 且字段类型解析依赖,可选加(Stage 0 实地核查 main HEAD 文件顶部 import 决定)| D1 |
| `features/ingest/upload_service.py` | (a) `__init__` **加 `chunking_service: ChunkingService` 参数 + 存为 `self._chunking_service`**(v0.3 R2 P1-3);(b) `process(...)` 末段 `mark_ready` 后包裹 try/except 调 `self._chunking_service.build_embed_store_project_chunks(project)` | D11 + D12 |
| `features/overview/overview_service.py` | (a) `__init__` **加 `chunking_service: ChunkingService` 参数 + 存为 `self._chunking_service`**(v0.3 R2 P1-3);(b) `get_or_generate(...)` **cache hit + cache miss 两路径**都包裹 try/except 调 `self._chunking_service.build_embed_store_overview_chunk(overview, project_id)`(v0.2 R1 P1-5 D16 cache hit 补偿)| D11 + D12 + D16 |
| `api/main.py` | lifespan AsyncExitStack 加 chunking_service 装配(继 vector_store / embedder 之后)| D10 + D11 |
| `api/dependencies.py` | (a) 加 `get_chunking_service` DI(类比 `get_chat_service`);(b) **`get_upload_service` 加 `chunking_service: ChunkingService = Depends(get_chunking_service)` + 传给 UploadService(...)** ;(c) **`get_overview_service` 加 `chunking_service` 同款 Depends + 传给 ProjectOverviewService(...)**(v0.3 R2 P1-3 锁死注入链路)| D10 |
| `app/config.py` | 加 `# Chunking` 段 **6 字段**(v0.2 R1 P1-8 加 `chunking_description_max_chars`):`chunking_max_source_text_chars: int = Field(default=1024, ge=64, le=4096)` + `chunking_docstring_max_chars: int = Field(default=300, ge=0, le=1000)` + `chunking_param_value_max_chars: int = Field(default=80, ge=0, le=500)` + `chunking_max_params_per_block: int = Field(default=12, ge=0, le=50)` + `chunking_max_subsystem_child_block_names: int = Field(default=20, ge=0, le=100)` + **`chunking_description_max_chars: int = Field(default=300, ge=0, le=1000)`** | D7 + D8 |
| **`.env.example`**(v0.2 R1 P1-2 新增)| 加 `CHUNKING_*` 6 字段注释,对齐 AppSettings 默认值 | D7 + D8 |

### 搭车 chore(本任沿用反例 26-30 同款字节级 Python patch 模式)

| chore | 范围 | patch 模式 |
|---|---|---|
| 1. 03 索引补账 | TASK-303 行 ⬜→✅ + Week 3 进度 [✅✅⬜⬜⬜⬜⬜] 2/7 → [✅✅✅⬜⬜⬜⬜] 3/7 + 总计 20/32 → 21/32 + 当前状态 "TASK-303 完成,启动 TASK-304" + 日期 2026-06-XX + **决策 09 反例库 30 → 31** | 第十六任 / 第十七任同款 6-7 处字节级 |
| 2. **反例 31 主动升仪入决策 09**(v0.3 R2 升仪 + v0.4 R3 加 KPI (e))| 已满足升仪标准:R1 P0-1(软妥协)+ R1 P0-4(转嫁)+ R2 P0-2(软论证未拍板)+ R2 P1-1(用"等等"标记不改)+ **R3 P0-1(循环论证)**(v0.4 新增)**共 5 同源 + 跨 3 次审查**;升仪名称:"**架构师识别到问题但回避拍硬决策(决策回避 / 软妥协 / 转嫁 / 用'等等'标记不改 / 循环论证假装满足硬前提)**";**KPI 5 条**(v0.4 R3 加 (e) 循环论证守门);详 § 给 Codex 提示 § "决策 09 反例 31 patch 草稿" | 第十六任反例 27/28 / 第十七任反例 29/30 同款字节级 Python patch:`docs/decisions/20260603-09-architect-must-verify-not-assume.md` 末追加反例 31 段;03 索引 § "决策 09 反例库" 计数同步 30 → 31 |

### 不动文件(明示,反例 24 KPI 兑现:不凭印象写"不动",已实地核查 main HEAD)

| 路径 | 不动理由 |
|---|---|
| `core/interfaces/vector_store.py` 内 VectorStore ABC + ChunkRecord 字段集 | TASK-302 已 main freeze,本任仅:(a) 追加 `SourceType` Literal + `RESERVED_SOURCE_TYPES`;(b) 改 `ChunkRecord.source_type` 类型注解 `str → SourceType`(TASK-302 P2-2 预留)。**不改 ChunkRecord 字段名 / 字段顺序 / 字段集 / 其他字段类型**;**不改 VectorStore ABC 5 方法签名** |
| `core/domain/exceptions.py` | **v0.2 R1 P0-3 已锁**:`ChunkingError` feature-private 在 `features/chunking/_errors.py`,**不进 core/domain/exceptions.py**(避免 ERROR_MAP / HTTP handler 膨胀)|
| `core/domain/*` 其他 | TASK-101 ~ TASK-107 已落地,本任消费,不改 |
| `adapters/storage/sqlite_vector_store.py` | TASK-302 已 main freeze,本任消费 add_chunks(不消费 delete_by_project_id — **v0.2 R1 P0-4 D14 已锁:chunk_project 不再 delete**)|
| `adapters/storage/schema.py` | TASK-302 已 bump v=2,本任不引入 schema 变更(D12 已锁:不扩 ProjectStatus / 不扩 chunks 表)|
| `adapters/embedding/sentence_transformer.py` | TASK-301 已落地,本任消费 embed 接口,不改 |
| `features/chat/_retriever.py` | TASK-205 已落地,KeywordRetriever 作类比 anchor 不改;**TASK-304 替换 Retriever** |
| `features/overview/_node_id.py` / `_pg_nodes.py` / `_pg_edges.py` | TASK-107 / TASK-203 已落地,本任作 chunker 类比 anchor 不改 |
| `core/domain/project_status.py` | **D12 已锁**:不扩 ProjectStatus.rag_status |
| `adapters/storage/sqlite_project_store.py` | 同 D12,不动 |
| `api/middleware/error_handler.py` | **v0.2 R1 P0-3 已锁**:ChunkingError feature-private 不进 ERROR_MAP / handler 元组 |

---

## 范围

### 必须做(对齐 Week 3 验收 03 索引 line 187-203)

- [ ] **D1 SourceType Literal 7 枚举定义在 `core/interfaces/vector_store.py`**:`m_file / m_function / slx_block / slx_subsystem / mat_variable / project_overview / teaching_unit`;`teaching_unit` 标 reserved 文档注释,本任不产
- [ ] **D2-D6 chunk 化粒度落地 6 类**(teaching_unit 不产):
  - [ ] 每 .m 文件 1 `m_file` chunk + 每 MFunction 1 `m_function` chunk
  - [ ] 每 SlxBlock 1 `slx_block` chunk + 每 subsystem 1 `slx_subsystem` chunk
  - [ ] 每 MatVariable 1 `mat_variable` chunk(空 .mat 不产)
  - [ ] 1 个 `project_overview` chunk(每项目)
- [ ] **D7 source_text 模板 + 字段级 sanitizer**(7 类模板齐备,docstring / parameters 字段级截断,禁 raw_code 引用)
- [ ] **D8 source_text 总长 ≤ 1024 chars**(head-only 截断 + `[…]` 标记)
- [ ] **D9 chunk_id 命名空间 + sha1 hash suffix 12 chars**
- [ ] **D10 features/chunking/ 新顶层模块** 9 文件按依赖方向锁(v0.3 R2 P1-2 修正)
- [ ] **D11 ChunkingService 单一入口 build_embed_store_project_chunks + build_embed_store_overview_chunk + `_embed_drafts` 公共 helper**(v0.2 R1 P1-7);双挂载点(UploadService.process 末 + ProjectOverviewService.get_or_generate **cache hit / miss 两路径末** D16);**best-effort 包裹 try/except 不反向修改 ProjectStatus**;空 batch 边界
- [ ] **D12 失败不扩 ProjectStatus**;TASK-304 用 `vector_store.get_chunk_count` 判断 RAG 不可用 fallback KeywordRetriever
- [ ] **D13 ChunkDraft 中间类型**(features/chunking/_chunk_draft.py **拆出独立文件** v0.2 R1 P1-1);ChunkingService 返回 list[ChunkDraft],embed 后 materialize ChunkRecord;**source_type: SourceType**(v0.2 R1 P0-1)
- [ ] **D14 chunk duplicate no-op 策略**(v0.2 R1 P0-2 + P0-4 大重写):
  - [ ] `build_embed_store_project_chunks`:**直接 add_chunks(chunks),不 delete_by_project_id**;`exc.args == ("chunk_id already exists",)` → log info "project_chunks_already_exist" + return 0;其他 ValueError 不吞
  - [ ] `build_embed_store_overview_chunk`:固定 chunk_id = `{project_id}::project_overview`;`exc.args == ("chunk_id already exists",)` → **debug log + return 0**(v0.2 R1 P1-5 改 debug);其他 ValueError 不吞
  - [ ] 两路径都用 **exc.args 精确 tuple 匹配**(v0.2 R1 P0-2:**不调用 `str(exc)`**)
- [ ] **D15 NodeType → SourceType 映射表** 落地 _project_chunker.py
- [ ] **D16 overview cache hit 补偿**(v0.2 R1 P1-5 新增):ProjectOverviewService.get_or_generate cache hit / miss 两路径都 best-effort 调 build_embed_store_overview_chunk,依赖 D14 dup no-op 幂等
- [ ] **`ChunkingError` feature-private**(v0.2 R1 P0-3 新增):在 `features/chunking/_errors.py`,继承 RuntimeError;**不进 core,不进 HTTP ERROR_MAP**
- [ ] **lifespan + DI 装配 ChunkingService**(api/main.py + api/dependencies.py)
- [ ] **AppSettings # Chunking 段 6 字段**(v0.2 R1 P1-8 加 description;D7 + D8 全字段 pydantic Field 校验)
- [ ] **测试**:Unit + Integration(`RUN_EMBEDDING_INTEGRATION=1` skipif)+ snapshot(P2-2)+ 空 batch 边界(P1-9)+ dup no-op + cache hit 补偿
- [ ] **搭车 chore**:03 索引补账 + (若有)反例 31 入决策 09

### 不做(明确排除)

- ❌ **VectorRetriever / Retriever 替换 ChatService**:TASK-304 接管;本任只产 chunk 入库,不消费查询
- ❌ **跨工程检索**:`query(project_id=...)` 已 TASK-302 强 WHERE 过滤;本任沿用
- ❌ **chunk delete 任何形式**(v0.2 R1 P0-4):本任**不消费** `vector_store.delete_by_project_id`(D14 反转后改 dup no-op);单 chunk delete / 全项目重建均留 Phase 2 接力(若 Phase 2 需,新增专用 service method 协调 OverviewCache + chunks)
- ❌ **chunk schema 变更**:不动 chunks 表 DDL(TASK-302 已落 v2)
- ❌ **ProjectStatus 字段扩**(D12 P0-4):不引入 `rag_status` / `rag_available`;TASK-304 用 `get_chunk_count` 判断
- ❌ **TeachingUnit chunk 实际生成**(D6):Literal 含 reserved,本任不 implement
- ❌ **PARAMETER 节点 emit chunk**(D15):ProjectGraph 已有 PARAMETER NodeType,但本任 skip(Phase 2 / 0.4 版本接力)
- ❌ **FILE_SLX / FILE_MAT 节点 emit chunk**(D15):信息已被 slx_block / slx_subsystem / mat_variable 覆盖,skip
- ❌ **embedder 模型升级 / 多模型并存**:Phase 2 候选;若改模型,chunks 表必须 rebuild(沿用 TASK-302 model_name 字段)
- ❌ **chunk_overview 写入失败时降级用旧 overview chunk**:本任 dup 直接 no-op;若数据漂移留 Phase 2 cache invalidation 解决
- ❌ **chunk 内容审查 / 敏感词过滤**:01 § 9 / 02 § 12 + TASK-302 R2 已覆盖隐私边界;本任不引入额外审查

---

## 接口契约

### 1. `SourceType` Literal + `ChunkRecord.source_type` 类型注解收紧(`core/interfaces/vector_store.py` **修改:`SourceType` 必须定义在 `ChunkRecord` 之前**)

**v0.3 R2 P0-1 修订**:**SourceType 定义位置锁死在 ChunkRecord 之前**(删除 v0.2 "文件末追加" 措辞)。
- 理由:Python `@dataclass(frozen=True)` 字段类型注解 `source_type: SourceType` 在 class body 执行时 evaluate;若 SourceType 定义在 ChunkRecord 之后 + 文件未启用 `from __future__ import annotations`,**import 时 NameError**
- 防御:即使有 `from __future__ import annotations`,dataclasses 模块在 `__init__` 生成时可能尝试 resolve;**最稳的做法是定义顺序锁死**(无论 future annotations 是否启用都安全)

**v0.2 R1 P0-1 继承**:`ChunkRecord.source_type` 字段类型注解从 `str` 收紧为 `SourceType` Literal(TASK-302 P2-2 注释预留的合法变更;Literal 在 runtime 是 str 子类型,**与 TASK-302 已落库数据 + 已 main merge add_chunks 调用完全兼容**)。

**修订后 core/interfaces/vector_store.py 结构**(SourceType 在 ChunkRecord 之前):

```python
# core/interfaces/vector_store.py
from __future__ import annotations  # 若文件未有此行,Codex 实施时 Stage 0 必查 + 决策保留或加;详 Stage 0 #1
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

# ★ v0.3 R2 P0-1:SourceType / RESERVED_SOURCE_TYPES 必须定义在 ChunkRecord 之前
SourceType = Literal[
    "m_file",
    "m_function",
    "slx_block",
    "slx_subsystem",
    "mat_variable",
    "project_overview",
    "teaching_unit",   # reserved — 本任不产;Phase 2 / 0.3+ 代码细节理解版接力
]

RESERVED_SOURCE_TYPES: Final[frozenset[str]] = frozenset({"teaching_unit"})
"""本任 ChunkingService 不产出 reserved SourceType 的 chunk;验收守门。"""


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    project_id: str
    source_type: SourceType            # ★ v0.2 改:str → SourceType(R1 P0-1 强收紧;TASK-302 P2-2 预留)
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


class VectorStore(ABC):
    """TASK-302 已 main freeze,本任不动 ABC 5 方法签名"""
    @abstractmethod
    async def add_chunks(self, chunks: list[ChunkRecord]) -> None: ...
    @abstractmethod
    async def query(self, ...) -> list[QueryResult]: ...
    @abstractmethod
    async def delete_by_project_id(self, project_id: str) -> int: ...
    @abstractmethod
    async def get_chunk_count(self, project_id: str) -> int: ...
    @abstractmethod
    async def aclose(self) -> None: ...
```

**ChunkDraft 同步**(§ 接口契约 2):`ChunkDraft.source_type: SourceType`(非 `str`,R1 P1-9 静态守门)。

**测试守门**(v0.3 R2 P0-1 加 runtime import 守门):
- `ChunkingService` 产出 chunk 的 `source_type` 必属于 `get_args(SourceType)`
- `chunk_project` 产出 chunk 中 `source_type != "teaching_unit"`(D6 RESERVED 守门)
- **runtime import 守门**(验收 #3):
  ```bash
  python - <<'PY'
  from core.interfaces.vector_store import ChunkRecord, RESERVED_SOURCE_TYPES, SourceType
  from typing import get_args
  assert "source_type" in ChunkRecord.__annotations__
  assert ChunkRecord.__annotations__["source_type"] is SourceType or str(ChunkRecord.__annotations__["source_type"]) == "SourceType"
  assert "teaching_unit" in RESERVED_SOURCE_TYPES
  assert set(get_args(SourceType)) == {"m_file", "m_function", "slx_block", "slx_subsystem", "mat_variable", "project_overview", "teaching_unit"}
  print("OK")
  PY
  # 期望:stdout "OK" + exit 0
  ```

### 2. `ChunkDraft`(`features/chunking/_chunk_draft.py` 新建,**v0.2 拆出独立文件** P1-1)

```python
from dataclasses import dataclass
from core.interfaces.vector_store import SourceType

@dataclass(frozen=True)
class ChunkDraft:
    """chunk 化产物中间类型,无 embedding/model_name/created_at;
    ChunkingService 内部使用,embed 后 materialize 成 ChunkRecord(D13)。
    
    v0.2 修订(R1 P1-9):source_type 类型从 str 收紧为 SourceType Literal,
    与 ChunkRecord.source_type 类型注解对齐。
    """
    chunk_id: str
    project_id: str
    source_type: SourceType    # ★ v0.2 改:str → SourceType(P0-1 + P1-9 收紧)
    file_path: str
    symbol_name: str | None
    line_range: tuple[int, int] | None
    block_id: str | None
    block_name: str | None
    block_type: str | None
    parent_subsystem: str | None
    source_text: str       # 已 sanitize + truncate(D7 + D8)
```

**为何拆独立文件**(v0.2 P1-1):避免 `chunking_service.py` 超 200 行(01 § 8 文件 ≤ 300 行约束);ChunkDraft 是 features/chunking 内部实现细节,**只在 ChunkingService 内部流转**,落库前 materialize 成 ChunkRecord(对外接口)。

### 3. `ChunkingService`(`features/chunking/chunking_service.py`)

```python
from features.chunking._chunk_draft import ChunkDraft
from features.chunking._errors import ChunkingError   # ★ v0.2 加,R1 P0-3 feature-private

class ProjectGraphProvider(Protocol):
    """ProjectGraph 构建提供者(P1-8 解耦,避免 UploadService 直接持 ProjectGraphBuilder)。"""
    def build(self, project: Project) -> ProjectGraph: ...

class ChunkingService:
    """ChunkingService 单一入口(P1-8 / D11)。
    
    职责:把 Project / ProjectOverview 转成 ChunkDraft,embed 成 ChunkRecord,落 VectorStore。
    
    设计要点(v0.2 R1 修订):
    - 双挂载点入口(build_embed_store_project_chunks + build_embed_store_overview_chunk)
    - best-effort 失败不反向修改 ProjectStatus(D12);**调用方在 try/except 内调本类**
    - **chunk_project 路径 NOT delete + add;改 add + dup no-op**(R1 P0-4,D14 v0.2 修订):
      同 project_id 视为不可变 MCS 快照,重复触发 = no-op,与 chunk_overview 同款 exc.args 检测
    - chunk_overview 路径固定 chunk_id + dup no-op(D14):**用 `exc.args == ("...",)` 精确匹配**
      (R1 P0-2:不调用 `str(exc)`,避免与本任隐私守门 + 验收 #26 冲突)
    - 抽 `_embed_drafts(drafts)` 公共 helper:project + overview 两路径都走长度校验(R1 P1-7)
    """
    
    _DUP_CHUNK_ID_ARGS: Final[tuple[str, ...]] = ("chunk_id already exists",)
    """TASK-302 P1-6 锁定的 ValueError args 字面,本任用精确 tuple 匹配检测 dup(R1 P0-2)。"""
    
    def __init__(
        self,
        embedder: EmbeddingProvider,        # TASK-301
        vector_store: VectorStore,           # TASK-302
        graph_provider: ProjectGraphProvider, # 注入 ProjectGraphBuilder(P1-8)
        settings: AppSettings,
        clock: Clock | None = None,          # 默认 datetime.utcnow,测试可注入
    ) -> None: ...
    
    async def _embed_drafts(self, drafts: list[ChunkDraft]) -> list[list[float]]:
        """公共 embed helper(R1 P1-7):project + overview 两路径都走,统一长度校验。
        
        步骤:
        1. source_texts = [d.source_text for d in drafts]
        2. embeddings = await asyncio.to_thread(self._embedder.embed, source_texts)
        3. if len(embeddings) != len(drafts): raise ChunkingError("embedding_count_mismatch")
        4. return embeddings
        """
        ...
    
    async def build_embed_store_project_chunks(self, project: Project) -> int:
        """
        Project 维度 chunk 化:6 类 source_type(m_file / m_function / slx_block /
        slx_subsystem / mat_variable;`project_overview` 走独立入口)。
        
        返回:
        - 正常写入路径:写入的 chunk 数(>0)
        - 空 batch 路径:0(空工程,正常路径,P1-9)
        - **dup no-op 路径(v0.2 R1 P0-4 大改)**:0(同 project_id 重复触发,non-fatal)
        
        异常上抛由调用方决定 best-effort,本方法不吞;调用方包 try/except。
        
        步骤(v0.2 修订:**去掉 delete_by_project_id**,改 dup no-op):
        1. graph = await asyncio.to_thread(self._graph_provider.build, project)
        2. drafts = _project_chunker.build_drafts(project, graph, settings) → list[ChunkDraft]
        3. if not drafts:
             logger.info("project_chunking_skipped: project_id={} reason=no_chunks", project.id)
             return 0  # P1-9 空 batch 边界
        4. embeddings = await self._embed_drafts(drafts)  # R1 P1-7 公共 helper
        5. chunks = [self._materialize(d, e) for d, e in zip(drafts, embeddings, strict=True)]
        6. try:
             await self._vector_store.add_chunks(chunks)
        7. except ValueError as exc:
             if exc.args == self._DUP_CHUNK_ID_ARGS:  # ★ v0.2 R1 P0-2:exc.args 精确匹配,不调 str(exc)
                 logger.info(
                     "project_chunks_already_exist: project_id={} drafts_count={}",
                     project.id, len(drafts),
                 )
                 return 0  # 同 project_id 视为不可变 MCS 快照,dup no-op(R1 P0-4)
             raise  # 其他 ValueError 不吞
        8. logger.info(
             "project_chunks_added: project_id={} m_file={} m_function={} "
             "slx_block={} slx_subsystem={} mat_variable={}",
             project.id, ... (按 source_type 分类计数,P2-1)
           )
        9. return len(chunks)
        
        注意:**不调用 delete_by_project_id**(v0.2 R1 P0-4):
        - 原 v0.1 方案"先 delete 再 add"会损坏已生成的 `project_overview` chunk
        - MCS 阶段同 project_id 是不可变工程快照(24h TTL 删除前内容不变)
        - 重复触发场景(任务重试 / 客户端重连)= dup no-op,正确幂等行为
        - 真正"重建"能力 Phase 2 接力(若 Phase 2 需,新增专用 service method 协调 OverviewCache + chunks)
        """
        ...
    
    async def build_embed_store_overview_chunk(
        self, overview: ProjectOverview, project_id: str
    ) -> int:
        """
        ProjectOverview 维度 chunk 化:1 个 project_overview chunk。
        
        返回:
        - 1:写入成功
        - 0:dup no-op(同 project_id 已写入 — 允许 cache hit 补偿 D16 / cache miss 重复触发)
        
        异常上抛由调用方决定 best-effort,本方法不吞;调用方包 try/except。
        
        步骤(v0.2 R1 修订:exc.args 检测 + cache hit 补偿支持):
        1. draft = _overview_chunker.build_draft(overview, project_id)
        2. embeddings = await self._embed_drafts([draft])  # R1 P1-7 公共 helper
        3. chunk = self._materialize(draft, embeddings[0])
        4. try:
             await self._vector_store.add_chunks([chunk])
        5. except ValueError as exc:
             if exc.args == self._DUP_CHUNK_ID_ARGS:  # ★ v0.2 R1 P0-2:exc.args 精确匹配
                 logger.debug(
                     "overview_chunk_already_exists: project_id={}",
                     project_id,
                 )  # ★ v0.2 R1 P1-5:dup 改 debug(避免 cache hit 每次 GET 都打 info)
                 return 0
             raise  # 其他 ValueError 不吞
        6. logger.info("overview_chunk_added: project_id={}", project_id)
        7. return 1
        
        D16 cache hit 补偿(R1 P1-5 + v0.3 R2 P1-1):
        - ProjectOverviewService.get_or_generate 在 cache hit / miss 路径都调本方法
        - **cache hit + chunk 已存在 路径会先 embed**(~50ms via to_thread),随后 add_chunks dup no-op return 0
        - MCS 阶段可接受;不加 _overview_chunk_exists 预检(KISS)
        - dup 日志降 debug 避免每次 GET overview 打 info 噪声
        """
        ...
    
    def _materialize(self, draft: ChunkDraft, embedding: list[float]) -> ChunkRecord:
        """ChunkDraft → ChunkRecord(D13 materialize 边界)。
        
        v0.2 R1 P0-1:draft.source_type 已是 SourceType Literal,
        ChunkRecord.source_type 类型注解也已收紧为 SourceType,赋值零摩擦。
        """
        return ChunkRecord(
            chunk_id=draft.chunk_id,
            project_id=draft.project_id,
            source_type=draft.source_type,                 # SourceType → SourceType
            file_path=draft.file_path,
            symbol_name=draft.symbol_name,
            line_range=draft.line_range,
            block_id=draft.block_id,
            block_name=draft.block_name,
            block_type=draft.block_type,
            parent_subsystem=draft.parent_subsystem,
            source_text=draft.source_text,
            embedding=embedding,
            model_name=self._settings.embedding_model_name,  # ★ TASK-301 settings
            created_at=self._clock.utcnow(),
        )
    
    async def aclose(self) -> None:
        """无资源持有,no-op。占位以便 lifespan AsyncExitStack 统一管理。"""
        ...
```

### 4. `_chunk_id.py`(`features/chunking/_chunk_id.py` 新建)

```python
"""chunk_id 命名空间 + hash suffix(D9 + P1-6)。
类比 features/overview/_node_id.py make_*_id 模式。

v0.3 R2 P1-5:make_chunk_id 的 source_type 参数从 str 收紧为 SourceType
(类型链路完整性,与 ChunkRecord / ChunkDraft 一致)。
"""

import hashlib
import re
from typing import Final
from core.interfaces.vector_store import SourceType  # ★ v0.3 R2 P1-5

_HASH_LEN: Final[int] = 12
_SAFE_ID_MAX_LEN: Final[int] = 80
_SAFE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-zA-Z0-9_./-]")

def _sanitize_identifier(raw: str) -> str:
    """把 identifier 规整成 ASCII 安全字符,截断到 _SAFE_ID_MAX_LEN。"""
    safe = _SAFE_ID_PATTERN.sub("_", raw)
    return safe[:_SAFE_ID_MAX_LEN]

def make_chunk_id(project_id: str, source_type: SourceType, *identifier_parts: str) -> str:
    """生成命名空间 chunk_id:`{project_id}::{source_type}::{safe_id}::{sha1[:12]}`。
    
    幂等:同 (project_id, source_type, identifier_parts) 输入 → 相同 chunk_id。
    防碰撞:hash suffix 防止 `a b.m` 和 `a_b.m` 撞同 safe_id。
    
    v0.2 R1 P2-1:空 identifier_parts 抛 ValueError("empty_chunk_identifier")。
    v0.3 R2 P1-5:source_type 参数收紧为 SourceType Literal(类型链路完整性)。
    
    Args:
        project_id: 项目 ID
        source_type: SourceType Literal 集成员(类型守门)
        identifier_parts: 唯一定位 identifier(如 file_path + symbol_name);**禁止全空**
    
    Returns:
        chunk_id 字符串(无长度上限,SQLite TEXT 接受)
    
    Raises:
        ValueError("empty_chunk_identifier"): identifier_parts 全空或空字符串
    """
    raw_id = "::".join(identifier_parts)
    if not raw_id:
        raise ValueError("empty_chunk_identifier")
    safe_id = _sanitize_identifier(raw_id)
    digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:_HASH_LEN]
    return f"{project_id}::{source_type}::{safe_id}::{digest}"

def make_overview_chunk_id(project_id: str) -> str:
    """固定 ID:`{project_id}::project_overview`(D14 dup no-op 锚点)。
    
    不加 safe_id 和 hash suffix — 每项目唯一 1 个 overview chunk,
    重复触发依赖 add_chunks 的 ValueError("chunk_id already exists")catch。
    """
    return f"{project_id}::project_overview"
```

### 5. `_source_text_templates.py`(`features/chunking/_source_text_templates.py` 新建)

```python
"""7 类 chunk source_text 模板 + 字段级 sanitizer(D7 + P1-4)。

设计原则:
- 中文教学化口吻(对齐 05_EXPLANATION_STYLE_GUIDE.md)
- 沿用 KeywordRetriever 模式(file_info / m_function / slx_block 直接抄)
- 扩 4 类(slx_subsystem / mat_variable / project_overview / teaching_unit reserved)
- 字段级 sanitizer:docstring / parameters / description / subsystem child_block_names 各自上限
- 总长 1024 chars head-only 截断 + `[…]` 标记
- **禁引用 MFile.raw_code**(grep 守门)
"""

from typing import Final
# 字段级 sanitizer 上限(从 AppSettings 注入,以下为默认 / fallback 值)
_DOCSTRING_MAX_CHARS_DEFAULT: Final[int] = 300
_PARAM_VALUE_MAX_CHARS_DEFAULT: Final[int] = 80
_MAX_PARAMS_PER_BLOCK_DEFAULT: Final[int] = 12
_MAX_SUBSYSTEM_CHILD_BLOCK_NAMES_DEFAULT: Final[int] = 20  # P2-3
_DESCRIPTION_MAX_CHARS_DEFAULT: Final[int] = 300           # ★ v0.2 R1 P1-8 新增
_SOURCE_TEXT_MAX_CHARS_DEFAULT: Final[int] = 1024  # D8
_TRUNCATE_MARKER: Final[str] = "[…]"

def _collapse_whitespace(text: str) -> str:
    """折叠 whitespace + 去控制字符。"""
    ...

def _truncate_field(text: str, max_chars: int) -> str:
    """字段级截断 head-only + `[…]` 标记。"""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(_TRUNCATE_MARKER)] + _TRUNCATE_MARKER

def truncate_source_text(text: str, max_chars: int) -> str:
    """source_text 总长 head-only 截断(D8)。"""
    return _truncate_field(text, max_chars)

# ---- 7 类模板 ----

def build_m_file_source_text(file_info: FileInfo, m_file: MFile, description_max: int) -> str:
    """
    模板:`f"文件 {file_info.relative_path},类型 {file_info.file_type},
            角色 {m_file.file_role},含 {len(m_file.functions)} 个函数。{description_truncated}"`
    
    v0.2 R1 P1-8:description 字段级截断 description_max(默认 300),
    防 description 挤掉文件角色 / 函数数等关键字段。
    """
    desc = _collapse_whitespace(file_info.description or "")
    desc_truncated = _truncate_field(desc, description_max)
    return (
        f"文件 {file_info.relative_path},类型 {file_info.file_type},"
        f"角色 {m_file.file_role},含 {len(m_file.functions)} 个函数。{desc_truncated}"
    )

def build_m_function_source_text(m_file: MFile, func: MFunction, docstring_max: int) -> str:
    """
    模板沿用 KeywordRetriever line 142-143:
    `f"函数 {func.name} 位于 {m_file.file_path},
       输入 {func.inputs},输出 {func.outputs}。{docstring_truncated}"`
    
    docstring 字段级截断 docstring_max(默认 300)。
    """
    doc = _collapse_whitespace(func.docstring or "")
    doc_truncated = _truncate_field(doc, docstring_max)
    return (
        f"函数 {func.name} 位于 {m_file.file_path},"
        f"输入 {func.inputs},输出 {func.outputs}。{doc_truncated}"
    )

def build_slx_block_source_text(
    model: SlxModel,
    block: SlxBlock,
    param_value_max: int,
    max_params: int,
) -> str:
    """
    模板沿用 KeywordRetriever line 170-171:
    `f"Block {block.name}({block.block_type}) 位于 {model.file_path}/{parent},参数 {params}"`
    
    parameters 字段级截断 + 最多 max_params 个(P1-4):
    - 单 value 截断 param_value_max(默认 80)
    - key 按字典序排序,取前 max_params 个(默认 12)
    """
    parent = block.parent_subsystem or "顶层"
    # 排序后取前 max_params,单 value 截断
    sorted_items = sorted(block.parameters.items())[:max_params]
    params_str = ",".join(
        f"{k}={_truncate_field(v, param_value_max)}"
        for k, v in sorted_items
    )
    return (
        f"Block {block.name}({block.block_type}) 位于 {model.file_path}/{parent},"
        f"参数 {params_str}"
    )

def build_slx_subsystem_source_text(
    model: SlxModel,
    subsystem_name: str,
    child_block_ids: list[str],
    block_id_to_name: dict[str, str],
    top_n: int,
) -> str:
    """
    模板:`f"子系统 {subsystem_name} 在 {model.file_path} 内,
            包含 {len(child_block_ids)} 个 block。子 block:{top_n_names}"`
    
    v0.2 R1 P2-2:child_block_ids 按 SlxModel.subsystems[name] dict 内**原始顺序**
    (Parser 输出顺序)取前 top_n(默认 20);**不重排**(保证 snapshot 稳定)。
    
    超过 top_n 时,末尾加 `等 N 个` 后缀。
    """
    names = [block_id_to_name[bid] for bid in child_block_ids[:top_n] if bid in block_id_to_name]
    suffix = f"等 {len(child_block_ids)} 个" if len(child_block_ids) > top_n else ""
    return (
        f"子系统 {subsystem_name} 在 {model.file_path} 内,"
        f"包含 {len(child_block_ids)} 个 block。子 block:{','.join(names)}{suffix}"
    )

def build_mat_variable_source_text(mat: MatMetadata, var: MatVariable) -> str:
    """
    模板:`f"变量 {var.name} 在 {mat.file_path} 中,类型 {var.var_type},
            shape {var.shape}{role_suffix}"`
    
    role_suffix = `,角色 {var.likely_role}` if var.likely_role else ""
    """
    role_suffix = f",角色 {var.likely_role}" if var.likely_role else ""
    return (
        f"变量 {var.name} 在 {mat.file_path} 中,类型 {var.var_type},"
        f"shape {var.shape}{role_suffix}"
    )

def build_project_overview_source_text(overview: ProjectOverview) -> str:
    """
    模板:汇总 12 字段中 7 个最教学相关的字段(其他字段如 main_entry_files / key_files
    是 list 引用,detail 已在 file_m / m_function chunk 中覆盖,不重复)。
    
    `f"项目 {project_title} 类型 {project_type}。{one_sentence_summary} 
       主流程 {','.join(main_execution_flow)}。
       知识点 {','.join(knowledge_points)}。
       建议阅读顺序 {','.join(beginner_reading_order)}。
       常见困惑 {','.join(likely_confusing_points)}"`
    
    entry_points / execution_flow 折入 main_execution_flow(P1-11)。
    """
    return (
        f"项目 {overview.project_title} 类型 {overview.project_type}。"
        f"{overview.one_sentence_summary} "
        f"主流程 {','.join(overview.main_execution_flow)}。"
        f"知识点 {','.join(overview.knowledge_points)}。"
        f"建议阅读顺序 {','.join(overview.beginner_reading_order)}。"
        f"常见困惑 {','.join(overview.likely_confusing_points)}"
    )

# teaching_unit 模板预留(本任不调用):
def build_teaching_unit_source_text(unit: TeachingUnit) -> str:  # noqa: F401 — Phase 2 接力
    """
    Phase 2 接力,本任不产 teaching_unit chunk(D6)。
    保留模板备 Phase 2 / 0.3+ 版本启用。
    """
    return (
        f"教学单元 {unit.title}({unit.level}):{unit.summary} "
        f"讲解步骤 {','.join(unit.explanation_steps)}"
    )
```

### 6. `_project_chunker.py`(`features/chunking/_project_chunker.py` 新建)

```python
"""把 Project + ProjectGraph 转成 list[ChunkDraft](6 类 chunk,D11 主链路)。

NodeType → SourceType 映射(D15):
- FILE_M    → emit m_file       (来源:ProjectGraph.nodes[type=FILE_M] + Project.m_files 补 file_role)
- FUNCTION  → emit m_function   (来源:ProjectGraph.nodes[type=FUNCTION] 或 Project.m_files.functions 直取)
- BLOCK     → emit slx_block    (来源:ProjectGraph.nodes[type=BLOCK])
- SUBSYSTEM → emit slx_subsystem(来源:ProjectGraph.nodes[type=SUBSYSTEM])
- FILE_SLX  → skip(信息已被 slx_block + slx_subsystem 全量覆盖)
- FILE_MAT  → skip(信息已被 mat_variable 的 file_path metadata 覆盖)
- PARAMETER → skip(Phase 2 / 0.4 版本接力,参数折叠进 slx_block.source_text)

mat_variable 不在 ProjectGraph NodeType 中(P0-2 + D4 + D15):
- 来源:Project.mat_files.variables 直取
- 每 MatVariable → 1 ChunkDraft
- 空 .mat (variables=[]) → 不产 chunk
"""

def build_drafts(project: Project, graph: ProjectGraph, settings: AppSettings) -> list[ChunkDraft]:
    """主入口:Project + ProjectGraph → list[ChunkDraft]。
    
    步骤(顺序固定,便于测试 + 日志元数据):
    1. _build_m_file_drafts(project)          → list[ChunkDraft](source_type=m_file)
    2. _build_m_function_drafts(project)      → list[ChunkDraft](source_type=m_function)
    3. _build_slx_block_drafts(project, settings) → ...
    4. _build_slx_subsystem_drafts(project, settings) → ...
    5. _build_mat_variable_drafts(project)    → ...
    6. concat 所有,返回(空 list 是有效返回值,调用方判断)
    """
    drafts: list[ChunkDraft] = []
    drafts.extend(_build_m_file_drafts(project))
    drafts.extend(_build_m_function_drafts(project))
    drafts.extend(_build_slx_block_drafts(project, settings))
    drafts.extend(_build_slx_subsystem_drafts(project, settings))
    drafts.extend(_build_mat_variable_drafts(project))
    return drafts

# _build_*_drafts 每个 ~20-30 行,沿用 features/overview/_pg_nodes.py 同款风格

def _build_m_file_drafts(project: Project) -> list[ChunkDraft]:
    """
    遍历 project.m_files;file_info 来自 project.files 按 relative_path 匹配;
    若匹配失败 → log warn metadata-only + skip(防御:不抛异常,best-effort 同款)。
    
    metadata 填充:
    - file_path = m_file.file_path
    - symbol_name = m_file.file_role(检索辅助;file_role 是 schema 字段,非用户原文)
    - line_range / block_id / block_name / block_type / parent_subsystem = None
    """
    ...

def _build_m_function_drafts(project: Project) -> list[ChunkDraft]:
    """
    遍历 project.m_files.*.functions;chunk_id identifier_parts = (file_path, func.name)。
    
    metadata 填充:
    - file_path = m_file.file_path
    - symbol_name = func.name
    - line_range = func.line_range  (MFunction.line_range 非可选 tuple)
    - block_id / block_name / block_type / parent_subsystem = None
    """
    ...

def _build_slx_block_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    """
    遍历 project.slx_models.*.blocks;过滤 is_library_link / is_model_reference(本任不展开,
    沿用 01 § 3 MCS v0.1 不承诺策略)— 这些 block 仍产 chunk,但 source_text 注明 "外部引用"。
    
    metadata 填充:
    - file_path = model.file_path
    - symbol_name = block.name
    - block_id = block.block_id
    - block_name = block.name
    - block_type = block.block_type
    - parent_subsystem = block.parent_subsystem
    - line_range = None  (.slx 是 XML,无源码行号)
    """
    ...

def _build_slx_subsystem_drafts(project: Project, settings: AppSettings) -> list[ChunkDraft]:
    """
    遍历 project.slx_models;对每 model,遍历 model.subsystems.items():
    - key = subsystem_name
    - value = child_block_ids 列表
    - 反查 model.blocks 取 block_id_to_name dict
    - 调 build_slx_subsystem_source_text(top_n=settings.chunking_max_subsystem_child_block_names)
    
    metadata 填充:
    - file_path = model.file_path
    - symbol_name = subsystem_name
    - block_id = None  (subsystem 是 dict key,无独立 block_id)
    - block_name = subsystem_name
    - block_type = "Subsystem"
    - parent_subsystem = None  (本任不做嵌套 subsystem 父子关系,Phase 2 接力)
    - line_range = None
    """
    ...

def _build_mat_variable_drafts(project: Project) -> list[ChunkDraft]:
    """
    遍历 project.mat_files;对每 mat,遍历 mat.variables:
    - 空 variables → skip(P0-2 + P1-9)
    
    metadata 填充:
    - file_path = mat.file_path
    - symbol_name = var.name
    - block_id / block_name / block_type / parent_subsystem / line_range = None
    """
    ...
```

### 7. `_overview_chunker.py`(`features/chunking/_overview_chunker.py` 新建)

```python
"""把 ProjectOverview 转成单个 ChunkDraft(source_type=project_overview,D5 + P1-10)。

metadata 填充矩阵(P1-10):
- chunk_id = make_overview_chunk_id(project_id)  (固定 ID,D14)
- file_path = "__project_overview__"  (sentinel;非真实路径,避免与文件类 chunk 撞)
- symbol_name = overview.project_title
- line_range = None
- block_id / block_name / block_type / parent_subsystem = None
- source_text = build_project_overview_source_text(overview)  (D7)
"""

def build_draft(overview: ProjectOverview, project_id: str) -> ChunkDraft:
    ...
```

### 8. `_errors.py`(`features/chunking/_errors.py` 新建,**v0.2 R1 P0-3 新增**)

```python
"""feature-private 异常类(R1 P0-3)。

设计原则:
- **feature-private**:不进 core/domain/exceptions.py(避免 ERROR_MAP / HTTP handler 膨胀)
- **不进 HTTP ERROR_MAP**:chunking 失败是 best-effort 增强链路,不应直接 HTTP 500;
  调用方(UploadService / OverviewService)try/except 捕获 + metadata-only 日志
- 子类基类:RuntimeError(非 MxaError),避免被 core/domain 异常树吸收
"""

class ChunkingError(RuntimeError):
    """chunking 失败的 feature-private 异常。
    
    用例:
    - `embedding_count_mismatch`: embedder 返回长度 ≠ drafts 长度(P1-7)
    - 其他不应 HTTP 路径暴露的内部 invariant 违反
    
    **不在 HTTP ERROR_MAP**:调用方在 best-effort 包裹内 catch 此异常 + 元数据日志。
    """
```

**测试守门**:
- `grep -n 'class ChunkingError' features/chunking/_errors.py` 命中 1
- `grep -rn 'ChunkingError' core/ api/middleware/error_handler.py` **0 命中**(feature-private 不污染 core)

### 9. service / DI / lifespan 装配(沿用 TASK-302 anchor;v0.3 R2 P1-3 锁死注入链路)

**v0.3 R2 P1-3 修订**:`UploadService.__init__` / `ProjectOverviewService.__init__` **加 `chunking_service: ChunkingService` 参数**;`get_upload_service` / `get_overview_service` **同步加 `Depends(get_chunking_service)`**(不能只加 `get_chunking_service` 一个独立 dependency 然后让 service 内部 `app.state` 取 — 违反 DI 模式 + 测试难 mock)。

```python
# api/main.py lifespan(类比 TASK-302 实战通过的模式)
async with AsyncExitStack() as stack:
    # ... 现有装配(text_provider / project_store / chat_store / overview_cache / 
    #              chat_service / embedder / vector_store)
    chunking_service = ChunkingService(
        embedder=embedder,
        vector_store=vector_store,
        graph_provider=ProjectGraphBuilder(),
        settings=settings,
    )
    stack.push_async_callback(chunking_service.aclose)
    app.state.chunking_service = chunking_service

# api/dependencies.py — v0.3 R2 P1-3:加 chunking_service + 修 get_upload_service / get_overview_service
def get_chunking_service(request: Request) -> ChunkingService:
    """类比 get_chat_service。"""
    svc = getattr(request.app.state, "chunking_service", None)
    if svc is None:
        raise RuntimeError("chunking_service not configured")
    return cast(ChunkingService, svc)

# v0.3 R2 P1-3:get_upload_service 同步加 chunking_service Depends
def get_upload_service(
    project_store: ProjectStore = Depends(get_project_store),
    project_status_store: ProjectStatusStore = Depends(get_project_status_store),
    chunking_service: ChunkingService = Depends(get_chunking_service),  # ★ v0.3 R2 P1-3 新增
    # ... 其他既有依赖 ...
) -> UploadService:
    return UploadService(
        project_store=project_store,
        project_status_store=project_status_store,
        chunking_service=chunking_service,  # ★ v0.3 R2 P1-3 新增
        # ... 其他既有参数 ...
    )

# v0.3 R2 P1-3:get_overview_service 同步加 chunking_service Depends
def get_overview_service(
    project_store: ProjectStore = Depends(get_project_store),
    cache: OverviewCache = Depends(get_overview_cache),
    resolver: ProjectGraphResolver = Depends(get_project_graph_resolver),
    text_provider: TextProvider = Depends(get_text_provider),
    chunking_service: ChunkingService = Depends(get_chunking_service),  # ★ v0.3 R2 P1-3 新增
) -> ProjectOverviewService:
    return ProjectOverviewService(
        project_store=project_store,
        cache=cache,
        resolver=resolver,
        text_provider=text_provider,
        chunking_service=chunking_service,  # ★ v0.3 R2 P1-3 新增
    )

# features/ingest/upload_service.py — v0.3 R2 P1-3:__init__ 加 chunking_service 参数
class UploadService:
    def __init__(
        self,
        project_store: ProjectStore,
        project_status_store: ProjectStatusStore,
        chunking_service: ChunkingService,  # ★ v0.3 R2 P1-3 新增
        # ... 其他既有参数 ...
    ) -> None:
        self._project_store = project_store
        self._project_status_store = project_status_store
        self._chunking_service = chunking_service  # ★ v0.3 R2 P1-3 新增
        # ...

    async def process(self, project_id: str, zip_bytes: bytes, name: str) -> None:
        # ... 现有逻辑 ...
        project = await asyncio.to_thread(self._run_parse_sync, ...)
        await self._project_store.save_project(project)
        await self._project_status_store.mark_ready(project_id)  # ★ 主链路先 ready
        # ↓ best-effort 增强链路,D11 + D12
        try:
            await self._chunking_service.build_embed_store_project_chunks(project)
        except Exception as exc:
            # 决策 11 决策 2:metadata-only
            logger.error(
                "project_chunking_failed: project_id={} exception={}",
                project_id, type(exc).__name__,
            )
            # 不反向修改 ProjectStatus(D12 + P0-5)

# features/overview/overview_service.py — v0.3 R2 P1-3:__init__ 加 chunking_service 参数
class ProjectOverviewService:
    def __init__(
        self,
        project_store: ProjectStore,
        cache: OverviewCache,
        resolver: ProjectGraphResolver,
        text_provider: TextProvider,
        chunking_service: ChunkingService,  # ★ v0.3 R2 P1-3 新增
    ) -> None:
        self._project_store = project_store
        self._cache = cache
        self._resolver = resolver
        self._text_provider = text_provider
        self._chunking_service = chunking_service  # ★ v0.3 R2 P1-3 新增

    async def get_or_generate(self, project_id: str) -> ProjectOverview:
        cached = await self._cache.get(project_id)
        if cached is not None:
            # ★ v0.2 R1 P1-5 D16:cache hit 路径也 best-effort 补 overview chunk
            # v0.3 R2 P1-1:cache hit + dup 路径**会先调 _embed_drafts**(~50ms via to_thread),
            # 随后 add_chunks dup no-op return 0;MCS 阶段可接受
            try:
                await self._chunking_service.build_embed_store_overview_chunk(cached, project_id)
            except Exception as exc:
                logger.error(
                    "overview_chunking_failed_on_cache_hit: project_id={} exception={}",
                    project_id, type(exc).__name__,
                )
            return cached
        overview = await self._generate(project_id)
        await self._cache.put(project_id, overview)  # ★ 先 cache(主链路)
        # ↓ best-effort 增强链路 — cache miss 路径
        try:
            await self._chunking_service.build_embed_store_overview_chunk(overview, project_id)
        except Exception as exc:
            logger.error(
                "overview_chunking_failed: project_id={} exception={}",
                project_id, type(exc).__name__,
            )
        return overview
```
```

---

## 决策日志

### D1 — SourceType Literal 7 枚举 + 定义位置 + reserved + entry/unresolved 折叠说明

**问题**:TASK-302 ChunkRecord.source_type 当前 `str` 透传(P2-2 待 TASK-303 定型);三处文档不一致(03 索引 6 / 路线图 7 / TASK-302 注释 5+etc)。

**决策**:**7 枚举,定义在 `core/interfaces/vector_store.py`(P1-1)**:

```python
SourceType = Literal[
    "m_file", "m_function",
    "slx_block", "slx_subsystem",
    "mat_variable",
    "project_overview",
    "teaching_unit",   # reserved,本任不产
]
```

**理由**:
- 路线图 § 6.3 是 0.2 版本 chunk 必须覆盖的明示
- m_function 是 RAG 召回最重要的粒度(03 索引漏是缺陷,P1-2 已修)
- KeywordRetriever 已做 m_function 在 prompt 阶段;TASK-303 入 SQLite 沿用同语义,不引新概念
- 定义在 core/interfaces/vector_store.py 而非 features/chunking — **避免 core 反向 import features(违反 01 § 7)**
- 改 Literal 是 Python 类型契约变更,**非 SQLite migration**(P1-2 修正措辞:source_type 是 TEXT,Literal 是 Python 静态类型 hint)

**entry / unresolved 折叠说明(P1-11)**:
- KeywordRetriever 现有 entry / unresolved 隐式 source_type 不进 SourceType Literal
- entry_points / execution_flow → 折入 `project_overview.source_text`(已在 D5 模板中)
- unresolved_symbols → 暂不入向量库;由 TASK-304 保留 KeywordRetriever fallback 或 TASK-307 证据强制器接管
- **目的**:0.2 版本向量 RAG 对"入口在哪 / 未解析符号"问题不比 TASK-205 倒退

**reserved teaching_unit**:本任 Literal 含此值,但 ChunkingService **不产** teaching_unit chunk;验收守门(`chunk_project` 在测试 fixture 中不产 source_type=teaching_unit 的 chunk)。Phase 2 / 0.3+ 版本接力。

### D2 — .m 文件 chunk 粒度(两层并存)

**决策**:每 .m 文件 1 `m_file` chunk + 每 MFunction 1 `m_function` chunk。

**理由**:
- 对齐 KeywordRetriever 当前 file_info + m_function 两层模式(向后兼容)
- 粗粒度 m_file 承担"这个文件干啥"类问题(file_role + functions_count summary)
- 细粒度 m_function 承担"这个函数干啥 / 在哪用"类问题
- 学生典型句式两类都有(01 § 2),缺一不可

**chunk 总量影响**:.m 文件平均 2-5 函数,两层比单层多 50-80% chunk;实际 100-500/工程 远低于 02 § 6 决策 1 阈值 5000。

### D3 — .slx chunk 粒度(两层并存)

**决策**:每 SlxBlock 1 `slx_block` chunk + 每 subsystem 1 `slx_subsystem` chunk(subsystem 从 `SlxModel.subsystems` dict 派生,基于 ProjectGraph SUBSYSTEM 节点)。

**理由**:
- KeywordRetriever 只做 slx_block 是 TASK-205 缺口
- slx_subsystem 对教学问答关键:学生典型问"这个子系统在干啥"(02 § 2)
- 不做 file_slx chunk(SlxModel 信息已在 slx_block / slx_subsystem 全量覆盖,加 file_slx 冗余;D15 已 skip)
- subsystem 实现基于 ProjectGraph SUBSYSTEM 节点遍历,与 SlxModel.subsystems dict 等价(更干净,沿用 features/overview/_pg_nodes.py 已做归一化)

### D4 — .mat 只 mat_variable,来源 Project.mat_files.variables 直取(P0-2)

**决策**:每 MatVariable 1 `mat_variable` chunk;**不从 ProjectGraph 派生**(ProjectGraph NodeType 无 MAT_VARIABLE,只有 FILE_MAT)。

**理由**:
- 02 § 6 决策 5:.mat 只做元信息(变量名 / 类型 / shape),本任沿用
- 单 .mat 通常变量数 5-20,粒度可控
- file_mat chunk 不做(信息已在 mat_variable 的 file_path metadata 隐含;D15 已 skip)
- **来源 Project.mat_files.variables 而非 ProjectGraph**:ProjectGraph 7 NodeType 无 MAT_VARIABLE(P0-2 修正)

**空 .mat 边界**(variables=[])→ 不产 chunk(P1-9 空 batch 边界)

### D5 — ProjectOverview 整 1 chunk + metadata 填充矩阵(P1-10)

**决策**:整 ProjectOverview → 1 个 `project_overview` chunk;不细拆 12 字段。

**理由**:
- 12 字段中 main_entry_files / main_simulink_models / key_files / key_blocks / evidence 都是 list 引用,对应的 detail 已在其他 chunk 类型(file_m / file_slx / m_function / slx_block)覆盖
- 整 overview 承担"项目是干嘛的 / 怎么入门"宏观问
- chunk 总量预算友好

**metadata 填充矩阵**(P1-10,7 类全覆盖;v0.2 R1 P1-4 修订 m_file.symbol_name):

| source_type | file_path | symbol_name | line_range | block_id | block_name | block_type | parent_subsystem |
|---|---|---|---|---|---|---|---|
| m_file | m_file.file_path | **None**(v0.2 R1 P1-4:file_role 是角色非 symbol,文件名已由 file_path 表达)| None | None | None | None | None |
| m_function | m_file.file_path | func.name | func.line_range | None | None | None | None |
| slx_block | model.file_path | block.name | None | block.block_id | block.name | block.block_type | block.parent_subsystem |
| slx_subsystem | model.file_path | subsystem_name | None | None | subsystem_name | "Subsystem" | None |
| mat_variable | mat.file_path | var.name | None | None | None | None | None |
| **project_overview** | `"__project_overview__"`(sentinel)| overview.project_title | None | None | None | None | None |
| teaching_unit(reserved)| (Phase 2 决定)| (Phase 2)| (Phase 2)| (Phase 2)| (Phase 2)| (Phase 2)| (Phase 2)|

### D6 — teaching_unit reserved,本任不产

**决策**:`SourceType` Literal 含 `teaching_unit`(D1),但 ChunkingService **不产** teaching_unit chunk;验收守门。

**理由**:
- TeachingUnit dataclass 已在 core/domain/teaching_unit.py 落地,但当前 MCS 阶段无任何 service 主动产 TeachingUnit 实例(ProjectOverview 12 字段已替代)
- Phase 2 / 0.3+ 版本可能 reintroduce(代码细节理解)
- Literal 含 reserved 值避免后续改 core SourceType 类型契约触发跨 module 修改(P1-2 修正措辞)

**测试守门**:`chunk_project(fixture) 不产生 source_type == "teaching_unit"` 的 ChunkDraft。

### D7 — source_text 模板 + 字段级 sanitizer(P1-4)

**模板设计**(7 类完整列在 § 接口契约 5);**字段级 sanitizer**:

```python
# 模块级常量(从 AppSettings 注入,以下为 fallback 默认)
_DOCSTRING_MAX_CHARS = 300          # 单 docstring 上限
_PARAM_VALUE_MAX_CHARS = 80         # 单 parameter value 上限
_MAX_PARAMS_PER_BLOCK = 12          # SlxBlock 取前 N 个 parameter(字典序排序)
_MAX_SUBSYSTEM_CHILD_BLOCK_NAMES = 20  # subsystem chunk 取前 N 个 child block 名(P2-3)
```

**禁引用 MFile.raw_code**:
- 验收 `grep -rnE 'raw_code' features/chunking/` 必须 0 命中
- 测试 case:fixture m_file.raw_code 含敏感内容,生成的 chunk.source_text 不含 raw_code

**为何不让 source_text 直接含 raw_code**:
- 01 § 9 + 02 § 12 隐私硬约束
- raw_code 是完整用户上传内容,**远超** TASK-302 R2 "最小必要派生文本"边界
- 0.3+ Phase 2 "代码细节理解版"可能开 raw_code 局部读取,但本任 0.2 不开

**collapse_whitespace + 去控制字符**:docstring / description 等用户上传字段先 collapse(防御 \n \r \t 异常)。

### D8 — source_text 总长 1024 chars head-only 截断(P1-5)

**决策**:落 SQLite 时即截断,`_MAX_SOURCE_TEXT_CHARS = 1024`(从 AppSettings.chunking_max_source_text_chars 注入,默认 1024);超长 head-only 保留 + 尾 `[…]` 标记。

**理由(措辞已 P1-5 修正)**:
- 1024 chars 是 MCS 的**产品侧最小必要预算**(隐私 + 存储 + prompt 上下文综合),**不是 tokenizer 精确边界**
- bge-small-zh-v1.5 长度行为不作为正确性前提(超长截断由模型 / pipeline 决定,不在本任保证)
- 落 SQLite 时即截断 = 隐私 + 存储双优(TASK-302 R2 "最小必要派生文本"原则)
- head-only:教学关键信息(name / type / file_path)通常在头部,截断不破坏召回相关度(P2-4 保留 head-only,Phase 2 评估 head+tail)

**测试覆盖**:
- `len(source_text) <= 1024`
- 截断后以 `[…]` 结尾(若有截断)
- 空 docstring / 空 parameters 不产生空 source_text
- 超长中文 / 英文 / 符号混排截断后字节安全(无非法 UTF-8)

### D9 — chunk_id 命名空间 + sha1 hash suffix(P1-6)

**决策**:

```
chunk_id = f"{project_id}::{source_type}::{safe_id}::{sha1(raw_id)[:12]}"

# 其中:
# raw_id = "::".join(identifier_parts)
# safe_id = re.sub(r"[^a-zA-Z0-9_./-]", "_", raw_id)[:80]
# digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:12]

# project_overview 特例:固定 ID 无 hash
chunk_id_overview = f"{project_id}::project_overview"
```

**理由**:
- 幂等(同 raw_id 输入 → 相同 chunk_id);**v0.2 R1 P0-4 D14 dup no-op 幂等**(直接 add,重复触发 catch ValueError + return 0,**不再** delete + add)
- 防碰撞:hash suffix 防 `a b.m` vs `a_b.m` sanitize 后撞(P1-6 抓)
- 跨 source_type 唯一(命名空间隔离)
- 反查友好(`WHERE chunk_id LIKE '{project_id}::%'` 即可拉项目全 chunk)

**生产日志不出完整 chunk_id**(P1-6,v0.2 R1 P1-6 加严):
- chunk_id 含 file_path / function name / block_id 等用户工程元数据
- 日志只记 `project_id` / `source_type` / `chunk_count` / `error_class`
- **v0.2 修订**:**任何 logger level(DEBUG / INFO / WARNING / ERROR)均不得输出完整 chunk_id、source_text、docstring、parameter value**(R1 P1-6:source_text 是 SQLite 显式例外,不是日志例外)
- 本地调试 / 测试如需查看 chunk 内容,使用 **pytest assertion / snapshot 文件**,不走 logger
- 验收 #26 grep 扩:`grep -rnE 'logger\.(debug|info|warning|error).*(source_text|docstring|parameter)' features/chunking/` → 0 命中

**v0.2 R1 P2-1 加空 identifier 校验**:`make_chunk_id` 在 `raw_id` 为空字符串时抛 `ValueError("empty_chunk_identifier")`(防御 Codex 误传空 identifier_parts 导致 chunk_id 退化为 `{project_id}::{source_type}::::{hash}` 撞名)。

### D10 — features/chunking/ 新顶层 + 依赖方向锁(P1-7)

**决策**:`features/chunking/` 新顶层模块。

**理由**:
- chunk 化跨 ingest(Project)+ overview(ProjectOverview)两域,放任一边都横向耦合
- chunking 不是教学理解中间层(02 § 6 决策 7 针对的是 ProjectGraph / TeachingUnit),而是 **RAG 基础设施层** — 把 domain / overview 转成 embeddable text
- 类比 `features/overview/` / `features/chat/` / `features/ingest/` 都是独立 feature,加 chunking 一个不违反 KISS
- ChunkingService 单一入口 + ProjectGraphProvider Protocol 解耦 UploadService / OverviewService(P1-8)

**依赖方向锁**(P1-7):

| 允许依赖 | 不允许 |
|---|---|
| `core/domain/*`(domain dataclass)| `features/overview/_*.py` 私有 helper(只能 import overview_schemas)|
| `core/interfaces/*`(SourceType / EmbeddingProvider / VectorStore ABC)| `adapters/*`(违反 01 § 7 分层)|
| `features/overview/overview_schemas.py`(ProjectOverview pydantic schema)| `core/*` 反向 import `features/chunking`(违反 01 § 7)|
| `app/config.py`(AppSettings)| `web/*` |
| 内部 `features/chunking/_*.py` 私有 | |

**测试守门**(grep):
- `grep -rnE 'from features\.overview\._' features/chunking/` → 0 命中(禁 private helper)
- `grep -rnE 'from adapters' features/chunking/` → 0 命中

### D11 — ChunkingService 单一入口 + best-effort + 双挂载 + 空 batch 边界 + mark_ready 顺序锁(P0-5 + P1-8 + P1-9)

**决策**:

**单一入口(P1-8)**:`ChunkingService` 提供 2 个 async 方法供调用方触发:
- `build_embed_store_project_chunks(project: Project) -> int`(6 类 chunk 入库)
- `build_embed_store_overview_chunk(overview, project_id) -> int`(1 个 overview chunk 入库)

UploadService / OverviewService **不直接持** ProjectGraphBuilder / Embedder / VectorStore;只持 ChunkingService。

**双挂载点 + best-effort 包裹 + mark_ready 顺序锁(P0-5)**:

```python
# UploadService.process
project = await asyncio.to_thread(self._run_parse_sync, ...)
await self._project_store.save_project(project)
await self._project_status_store.mark_ready(project_id)  # ★ 主链路先 ready
try:
    await self._chunking_service.build_embed_store_project_chunks(project)
except Exception as exc:
    logger.error("project_chunking_failed: project_id={} exception={}",
                 project_id, type(exc).__name__)
    # 不反向修改 ProjectStatus(D12)

# ProjectOverviewService.get_or_generate (cache miss 路径)
overview = await self._generate(project_id)
await self._cache.put(project_id, overview)  # ★ 先 cache
try:
    await self._chunking_service.build_embed_store_overview_chunk(overview, project_id)
except Exception as exc:
    logger.error("overview_chunking_failed: ...")
```

**顺序锁**:`mark_ready` 必须在 `build_embed_store_project_chunks` 之前;`cache.put` 必须在 `build_embed_store_overview_chunk` 之前。**主链路 ready 后才触发 best-effort 增强**。

**空 batch 边界(P1-9)**:
- `build_embed_store_project_chunks(empty_project)`:`if not drafts: log info "no_chunks" + return 0`
- `_build_mat_variable_drafts` 对空 .mat 变量列表 → 不产 chunk
- 验收测试覆盖空工程 / 空 .mat / 无 block .slx

**embedding 批量长度校验**:`len(embeddings) != len(drafts)` → `raise ChunkingError("embedding_count_mismatch")`;不写部分 chunks。

**NodeType → SourceType 映射(详 D15)**:_project_chunker.py 实施。

### D12 — 失败不扩 ProjectStatus,TASK-304 用 get_chunk_count 判断(P0-4)

**决策**:**TASK-303 不扩 ProjectStatus 任何字段**(不引入 `rag_status` / `rag_available`)。

**理由**(P0-4 抓):
- 扩 ProjectStatus 是 schema migration + ProjectStatusRecord 字段 + ProjectStore API + status API response + 前端轮询契约多面工程
- 本任范围漂移代价大于收益
- TASK-302 VectorStore.get_chunk_count(project_id) 已存在,TASK-304 直接 query 判断 RAG 可用性

**TASK-304 fallback 路径**(本任范围外,但给 TASK-304 提示):

```python
# TASK-304 ChatService 装配时:
chunk_count = await self._vector_store.get_chunk_count(project_id)
if chunk_count == 0:
    # vector RAG 不可用,fallback KeywordRetriever
    retriever = self._keyword_retriever
else:
    retriever = self._vector_retriever
```

**chunk 化失败的日志**(决策 11 决策 2 metadata-only):

```python
logger.error(
    "project_chunking_failed: project_id={} exception={} duration_ms={}",
    project_id, type(exc).__name__, elapsed_ms,
)
# 严禁 logger.exception / str(exc)(避免泄漏 source_text / raw_code / traceback path)
```

### D13 — ChunkDraft vs ChunkRecord materialize 边界(P0-1)

**决策**:`ChunkDraft` 中间类型(`features/chunking/_chunk_draft.py` 或 chunking_service.py 内),无 embedding / model_name / created_at;ChunkingService 内部生成 → embed → `_materialize(draft, embedding)` 转成 ChunkRecord 落库。

**理由**(P0-1 抓):
- `ChunkRecord.embedding: list[float]` 是必填(非 Optional),"unembedded ChunkRecord" 在类型上不合法
- 用 ChunkDraft 中间类型避免 dataclasses.replace 用空 list 占位的语义错乱
- ChunkDraft 是 features/chunking 内部实现细节,**不进 core/interfaces**(避免污染对外接口)

**测试覆盖**:
- `ChunkingService.build_embed_store_project_chunks` 内部产出 ChunkDraft 而非 ChunkRecord
- materialize 后 ChunkRecord.model_name 等于 AppSettings.embedding_model_name(TASK-301 settings 已落)
- materialize 后 ChunkRecord.created_at 是 datetime(非 None)

### D14 — chunk duplicate no-op 策略(v0.2 R1 P0-2 + P0-4 大重写)

**v0.2 R1 修订**:原 v0.1 D14 用 `delete_by_project_id` + `str(exc)` 检测,两处均违反本任硬约束;v0.2 改为**两路径都用 add + dup no-op 幂等**,且 dup 检测用 `exc.args == ("chunk_id already exists",)` 精确匹配。

**决策**:

**`build_embed_store_project_chunks(project)` 路径**(v0.2 R1 P0-4 反转):
- 直接 `await self._vector_store.add_chunks(chunks)`(**去掉** v0.1 的 `delete_by_project_id`)
- 若 `ValueError` 且 `exc.args == ("chunk_id already exists",)` → **log info "project_chunks_already_exist" + return 0**
- 其他 `ValueError` 不吞,异常上抛(调用方 best-effort try/except 捕获)

```python
try:
    await self._vector_store.add_chunks(chunks)
except ValueError as exc:
    if exc.args == self._DUP_CHUNK_ID_ARGS:  # ★ v0.2 R1 P0-2:exc.args 精确匹配
        logger.info(
            "project_chunks_already_exist: project_id={} drafts_count={}",
            project.id, len(drafts),
        )
        return 0  # 同 project_id 视为不可变 MCS 快照,dup no-op
    raise
```

**为何反转**(R1 P0-4):
- 原 v0.1 `delete_by_project_id` + add 方案会**损坏已生成的 `project_overview` chunk**(因为 delete_by_project_id 不分 source_type,会一并删除该 project 的所有 chunk)
- v0.1 R5 自己承认风险但只给"前端 / 上游应清 overview cache"转嫁,**不是本 Task 可验证工程闭环**
- MCS 阶段同 `project_id` = **不可变工程快照**(24h TTL 删除前内容不变);重复触发场景 = 任务重试 / 客户端重连,正确行为 = 幂等 no-op
- 真正"重建"能力(用户改 zip 再传)走**新 project_id**,不复用旧 project_id
- 若 Phase 2 需要"同 project_id 重建"语义(改 file 后端不重发 project_id),新增专用 service method 协调 OverviewCache + chunks,本任不做

**`build_embed_store_overview_chunk(overview, project_id)` 路径**(v0.2 R1 P0-2 改 exc.args):
- 固定 chunk_id = `make_overview_chunk_id(project_id) = f"{project_id}::project_overview"`(D9 特例)
- `add_chunks([chunk])`
- 若 `ValueError` 且 `exc.args == ("chunk_id already exists",)` → **debug log + return 0**(v0.2 R1 P1-5:dup 改 debug 避免 cache hit 每次 GET 都打 info)

```python
try:
    await self._vector_store.add_chunks([chunk])
except ValueError as exc:
    if exc.args == self._DUP_CHUNK_ID_ARGS:  # ★ v0.2 R1 P0-2:不调 str(exc)
        logger.debug(
            "overview_chunk_already_exists: project_id={}",
            project_id,
        )  # ★ v0.2 R1 P1-5:dup 改 debug
        return 0
    raise
```

**为何 exc.args 而非 str(exc)**(R1 P0-2):
- 本任验收 #26 + "关键约束"明禁 `str(exc)`(决策 11 决策 2 隐私守门:`str(exc)` 可能含 SQLite traceback / 工程片段)
- TASK-302 P1-6 已锁定 ValueError 的 args 字面为单元素 tuple `("chunk_id already exists",)`,**精确 tuple 匹配比 substring 检测更稳**
- 若未来 TASK-302 改 ValueError message,改 args 也是接口契约级变更,本任的 `_DUP_CHUNK_ID_ARGS` 常量明示依赖该契约

**测试覆盖**(v0.2 R1 修订):
- 同 project 连续调 `chunk_overview` 两次 → 不 500,chunk_count 不增加,**第二次走 debug 日志非 info**
- 同 project 连续调 `chunk_project` 两次 → 不 500,**chunk_count 不变**(dup no-op,不再 delete + add)
- chunk_project 后调 chunk_overview → overview chunk 写成功(无干扰)
- chunk_overview 后调 chunk_project → project chunks 写成功(无干扰)+ overview chunk 仍存在(v0.2 R1 P0-4 关键:overview chunk **不再被** chunk_project 删除)
- 非 dup ValueError(如 `("mixed_embedding_dim",)`)→ 上抛,not catch

### D15 — NodeType → SourceType 映射表(v0.2 R1 P1-3 chunk 数公式修正)

**决策**:

| NodeType | 处理 | 来源 |
|---|---|---|
| `FILE_M` | emit `m_file` | ProjectGraph.nodes[type=FILE_M] + Project.m_files 反查补 file_role / functions_count |
| `FUNCTION` | emit `m_function` | ProjectGraph.nodes[type=FUNCTION] + Project.m_files.functions 反查取 line_range / docstring / inputs / outputs |
| `BLOCK` | emit `slx_block` | ProjectGraph.nodes[type=BLOCK] + Project.slx_models.blocks 反查取 parameters / position |
| `SUBSYSTEM` | emit `slx_subsystem` | ProjectGraph.nodes[type=SUBSYSTEM] + Project.slx_models.subsystems 反查取 child_block_ids |
| `FILE_SLX` | **skip** | 信息已被 slx_block / slx_subsystem 全量覆盖 |
| `FILE_MAT` | **skip 或仅作 file_path 来源** | 信息已被 mat_variable 的 file_path metadata 覆盖 |
| `PARAMETER` | **skip** | Phase 2 / 0.4 接力;参数信息已折叠进 slx_block.source_text |
| (无对应 NodeType) | emit `mat_variable` | **Project.mat_files.variables 直取**(ProjectGraph 无 MAT_VARIABLE 节点,P0-2)|
| (无对应 NodeType) | emit `project_overview` | ProjectOverviewService 生成结果(本任 _overview_chunker 转换)|

**实施提示**(v0.2 R1 P1-3 修正):_project_chunker.py 不一定**严格遍历 ProjectGraph.nodes**;为了避免 ProjectGraph 节点元数据丢失(如 m_file.file_role 不在 metadata 中),可以直接遍历 Project.m_files / Project.slx_models / Project.mat_files,**ProjectGraph 用作辅助校验**:

```python
# v0.2 R1 P1-3 修正 — 正确的 chunk 数验收公式:
expected_project_chunks = (
    count_nodes(NodeType.FILE_M)        # emit m_file
    + count_nodes(NodeType.FUNCTION)    # emit m_function
    + count_nodes(NodeType.BLOCK)       # emit slx_block
    + count_nodes(NodeType.SUBSYSTEM)   # emit slx_subsystem
    + sum(len(mat.variables) for mat in project.mat_files)  # emit mat_variable(不走 ProjectGraph)
)
# project_overview 走独立入口 build_embed_store_overview_chunk,不混入此公式
```

**注意**:FILE_SLX / FILE_MAT / PARAMETER 节点 **skip**(D15 映射),**不计入** expected_project_chunks;teaching_unit 本任不产,也不计入。

### D16 — overview cache hit 补偿(v0.2 R1 P1-5 新增)

**问题**:v0.1 在 `ProjectOverviewService.get_or_generate` 只在 **cache miss 生成路径**末调 `build_embed_store_overview_chunk`;cache hit 直接 return。这留两个边界:
1. TASK-303 上线前已有 overview cache 的项目,后续 cache hit 永不补 chunk
2. cache.put 成功但 chunk 写失败(例如 embed 间歇错),后续 cache hit 永不补 chunk

**决策**(v0.2 R1 P1-5):**cache hit / miss 两路径都 best-effort 调** `build_embed_store_overview_chunk`,依赖 D14 dup no-op 幂等。

```python
# features/overview/overview_service.py
async def get_or_generate(self, project_id: str) -> ProjectOverview:
    cached = await self._cache.get(project_id)
    if cached is not None:
        # ★ cache hit 路径补偿
        try:
            await self._chunking_service.build_embed_store_overview_chunk(cached, project_id)
        except Exception as exc:
            logger.error(
                "overview_chunking_failed_on_cache_hit: project_id={} exception={}",
                project_id, type(exc).__name__,
            )
        return cached
    overview = await self._generate(project_id)
    await self._cache.put(project_id, overview)
    # cache miss 路径
    try:
        await self._chunking_service.build_embed_store_overview_chunk(overview, project_id)
    except Exception as exc:
        logger.error(
            "overview_chunking_failed: project_id={} exception={}",
            project_id, type(exc).__name__,
        )
    return overview
```

**性能影响**(D16 + D14 联动,v0.3 R2 P1-1 重写,删除 v0.2 自相矛盾措辞):
- **cache hit + chunk 已存在 路径**:`_overview_chunker.build_draft(...)` → `_embed_drafts([draft])`(**1 次 embed,~50ms 同步重活 via `asyncio.to_thread`**)→ `_materialize(draft, embedding)` → `add_chunks([chunk])` → SQLite UNIQUE 约束失败抛 `ValueError("chunk_id already exists")` → catch + debug log + return 0
- **MCS 阶段可接受**:`GET /projects/{id}/overview` 整体目标 < 5s(02 § 11);单次 embed ~50ms 在预算内
- **本任不加 `_overview_chunk_exists(project_id)` 预检**(KISS;避免引入额外 SQL query;ChunkingService 单一职责);Phase 2 评测发现性能瓶颈再加

**dup 日志降 debug**(R1 P1-5 + R2 P1-1):避免每次 GET overview 都打 info(production INFO 噪声);开发期调 DEBUG 仍可见。

**测试覆盖**(v0.3 R2 P1-1 + R1 P1-5):
- cache hit + chunk 已存在 → 调 embed 1 次 + dup no-op,return,chunk_count 不增加
- cache hit + chunk 不存在(TASK-303 上线前老项目)→ 补写成功,chunk_count == 1
- cache miss + chunk 不存在 → 正常生成 + 写入
- cache miss + chunk 已存在(理论上不应出现,但容错)→ dup no-op

---

## 风险

### R1 — embedding 批量调失败(隔离)

**风险**:`embedder.embed(source_texts)` 抛 EmbeddingError / OSError / 网络异常 / 内存不足。

**应对**:
- **决策 11 决策 1**:`await asyncio.to_thread(embedder.embed, ...)` 桥接同步重活,不阻塞 event loop
- **决策 11 决策 2**:logger.error metadata-only,**禁 logger.exception / str(exc)**(避免泄漏 source_text / raw_code)
- **best-effort 包裹**(D12):异常上抛 ChunkingService,UploadService / OverviewService 内层 try/except 捕获 + 记日志 + 不影响主链路
- **空批量保护**(P1-9):`if not source_texts: return 0`(不调 embedder)

### R2 — source_text 隐私边界(继承 TASK-302 R2)

**风险**:source_text 进 SQLite chunks 表,是 01 § 9 / 02 § 12 显式例外。本任 7 类 chunk 各自 source_text 内容形态需逐一论证。

**应对**(详 § 4 隐私表 + 字段级 sanitizer):

| source_type | source_text 主要载荷 | 隐私边界 |
|---|---|---|
| m_file | file_path + file_role + functions_count + description | 元数据派生(file_role 是 schema 字段,description 可能用户上传 → collapse_whitespace + 总长截断防御)|
| m_function | name + inputs + outputs + docstring 截断 | **含 docstring**(用户上传)— 已沿用 TASK-205 KeywordRetriever 同例外 + 字段级截断 300 chars |
| slx_block | name + type + path + parent + parameters 截断 | **含 parameters values 截断** — 已沿用 TASK-205 KeywordRetriever + _PARAM_VALUE_MAX_CHARS = 80 + max_params = 12 |
| slx_subsystem | subsystem_name + model.file_path + child_block_count + top_20_names | 结构化派生(全部来自 schema 字段,非原文)|
| mat_variable | name + type + shape + likely_role | 元信息(符合 02 § 6 决策 5 .mat 仅元信息原则)|
| project_overview | LLM 生成的 12 字段汇总 | LLM 输出,非用户原文 |
| teaching_unit(reserved)| LLM 输出 | Phase 2 论证 |

**禁引用 raw_code**:
- 验收 `grep -rnE 'raw_code' features/chunking/` 必须 0 命中
- 测试 fixture m_file.raw_code 含敏感内容,生成 chunk 不含

**日志禁出**(v0.2 R1 P1-6 加严):source_text / docstring / parameter values **任何 logger level(DEBUG / INFO / WARNING / ERROR)均不得输出**;**source_text 是 SQLite 显式例外,不是日志例外**。本地调试 / 测试如需查看,使用 pytest assertion / snapshot 文件,**不走 logger**。

### R3 — chunk 总量预算(02 § 6 决策 1 阈值)

**风险**:7 类 chunk 总量可能远超预期(超大工程)。

**估算**:典型 MCS 工程:
- .m 文件 10-50 个 × 2-5 函数 / 文件 → 30-300 m_file + m_function chunk
- .slx 模型 1-10 个 × 10-50 block / 模型 → 10-500 slx_block chunk
- subsystem 5-20 / 模型 × 1-10 模型 → 5-200 slx_subsystem chunk
- .mat 0-5 个 × 5-20 变量 / 文件 → 0-100 mat_variable chunk
- project_overview = 1
- **典型总量 100-1000/工程**,02 § 6 决策 1 阈值 5000 留 5x 安全垫

**应对**:
- 不引入特殊优化(KISS)
- AppSettings 不暴露上限(超 5000 chunk 工程是 Phase 2 升级阈值)
- 监控:验收输出 chunk 计数(P2-1)便于运营观察

### R4 — TeachingUnit 接口预留烂尾

**风险**:`SourceType` Literal 含 `teaching_unit`,但本任不产;Phase 2 是否真会启用?

**应对**:
- TeachingUnit dataclass 已在 core/domain/teaching_unit.py 落地(TASK-101)
- 路线图 § 0.3+ 明示 Phase 2 / 0.3+ 版本可能 reintroduce(代码细节理解版)
- 测试守门:`chunk_project(fixture) 不产 teaching_unit`;Phase 2 启用时加 `chunk_teaching_unit` 实施 + 移除测试守门
- 反 R4:即使 Phase 2 不启用 teaching_unit chunk,Literal 含此值的代价是零(SQLite TEXT 兼容)

### R5 — 已消除(v0.2 R1 P0-4 D14 反转后此风险不复存在)

**v0.1 原 R5**:`chunk_project` 重建会 delete + add 导致 `project_overview` chunk 被一并删除,文档承认 cache hit 不补回。

**v0.2 R1 P0-4 已消除**:D14 主决策反转,`build_embed_store_project_chunks` 不再 `delete_by_project_id`,改为 add + dup no-op 幂等。**overview chunk 不再被 chunk_project 干扰**;D16 cache hit 补偿是兜底但实际几乎不会用到(MCS 阶段同 project_id 不可变工程快照)。

### R6 — partial chunk 写入失败的重试幂等性(v0.3 R2 P0-2 大重写)

**v0.3 R2 P0-2 修订**:v0.2 原 R6 "本任幂等设计天然处理 partial / 重试时前 50 走 dup no-op + 后 50 补写最终一致" **论证错误**。GPT 指出:重试时 `add_chunks(chunks)` 遇到第一个已存在 chunk → TASK-302 抛 `ValueError("chunk_id already exists")` → D14 catch + return 0 → **后 50 个永远不写**。**反例 31 候选同源**(我在 v0.2 用软论证"幂等天然处理"绕开 add_chunks 实际批量语义,未拍硬决策)。

**v0.3 决策 — 采纳 GPT 方案 A:硬锁 TASK-302 add_chunks 单事务原子性为本任前置硬假设**

**风险论证**:
- TASK-302 `add_chunks(chunks)` 是批量接口;若实现非单事务(逐条 INSERT 无 BEGIN/COMMIT)→ 中途异常会留 partial state(前 N 已写 + 后 M 未写)
- 重试 `add_chunks(全 chunks)` 时,SQLite UNIQUE 约束在第一个已存在 chunk_id 上失败 → 抛 `ValueError("chunk_id already exists")` → D14 catch + return 0 → **后 M chunk 永远不被补写**
- 这违反 D14 dup no-op 的设计意图(意图:**整批写入或整批 dup no-op**,不是逐条 dup check)

**前置硬假设**(v0.3 R2 P0-2 锁死):
- **TASK-302 `SqliteVectorStore.add_chunks` 必须是单事务原子操作**:任一 row 写入失败,整批 rollback(BEGIN / COMMIT / ROLLBACK 包裹)
- **不允许 partial chunks 状态**:要么全部成功,要么全部回滚(后续重试 add_chunks(全 chunks) 等价于首次写入,无 dup)
- 此前置假设符合 SQLite 数据库批量写入的标准语义,也是 TASK-302 作为存储层应提供的职责边界

**Stage 0 必查**(v0.4 R3 P1-3 修订:awk range 限定 add_chunks 函数体 + 删除 async with execute 误导措辞):
- **Stage 0 必查 — Python 抽函数体脚本**(v0.5 R4 P0-1 采纳 GPT 方案 B,避开 awk range + 缩进 + 同行匹配三重边界;**单 Python 调用合并 5 项必需组群检查**):
  ```bash
  python - <<'PY'
  from pathlib import Path

  path = Path("adapters/storage/sqlite_vector_store.py")
  lines = path.read_text(encoding="utf-8").splitlines()

  start = next(i for i, line in enumerate(lines) if line.startswith("    async def add_chunks("))
  end = next(
      (i for i in range(start + 1, len(lines)) if lines[i].startswith("    async def ")),
      len(lines),
  )

  body = "\n".join(lines[start:end])

  required_groups = [
      ("BEGIN", ["BEGIN"]),
      ("COMMIT", ["COMMIT", ".commit("]),
      ("ROLLBACK", ["ROLLBACK", ".rollback("]),
      ("OperationalError", ["OperationalError"]),
      ("sqlite_operation_failed", ['VectorStoreError("sqlite_operation_failed")', "sqlite_operation_failed"]),
  ]

  missing = [
      name
      for name, needles in required_groups
      if not any(needle in body for needle in needles)
  ]

  if missing:
      raise SystemExit(f"add_chunks contract check failed; missing: {', '.join(missing)}")
  print("add_chunks contract OK")
  PY
  # 期望:stdout "add_chunks contract OK" + exit 0
  # 任一组群缺失 → SystemExit 退出码非 0 + 列出缺失项;Codex 停手抛冲突给 PM
  ```
  **5 项必需组群语义**:
  - `BEGIN`:显式 transaction 开始(BEGIN / BEGIN TRANSACTION / BEGIN IMMEDIATE 任一)
  - `COMMIT`:显式 transaction 提交(COMMIT 字面 或 `.commit(` 调用)
  - `ROLLBACK`:异常分支显式回滚(ROLLBACK 字面 或 `.rollback(` 调用)
  - `OperationalError`:catch aiosqlite/sqlite3 的 OperationalError
  - `sqlite_operation_failed`:翻译为 `VectorStoreError("sqlite_operation_failed")` 公共契约
- **关键澄清**(v0.4 R3 P1-3 删除 v0.3 错误措辞):**仅看到 `async with self._conn.execute(...)` 不足以证明事务**;`async with execute` 主要是 **cursor lifecycle 管理**,**不保证 transaction**;Python 脚本以 5 项必需组群在 `add_chunks` 函数体内同时命中作为初筛守门
- **若 Stage 0 Python 脚本退出码非 0**:Codex **停手抛冲突给 PM**,**不可硬上**(决策 09 纪律 1);需先回补 TASK-302,再实施本任
- **架构师 fallback**:若 PM 同意 TASK-302 也修,本任范围扩;若不同意,本任改 D14 catch dup 时**验证完整 project chunk set 已存在**(预检 + ChunkingError("partial_project_chunks"))— 此为 R2 GPT 方案 B(本任 v0.4 默认走方案 A)
- **最终守门**:Stage 0 Python 脚本仅作初筛;**验收 #35 fault-injection integration 测试是最终守门**(v0.4 R3 P0-1 大重写)
- **v0.5 反例 28 KPI 转 PM 兜底**:架构师本地无 repo,无法实测 Python 脚本在真实 `sqlite_vector_store.py` 上的输出;**Codex 实施前 PM 兜底跑一次此 Python 脚本**,验证退出码 0 + stdout "add_chunks contract OK"(详 § 给 Codex 提示 § "PM 兜底验证步骤")

**验收覆盖**(v0.4 R3 P0-1 大重写 — 真实 SqliteVectorStore fault-injection,见 § 验收 #35):
- 用**真实 SqliteVectorStore + 真实 schema init**(tmp_path 文件 DB),**不是 mock**
- monkeypatch aiosqlite Connection.execute 在第 k 次 INSERT 抛 `OperationalError`
- 断言对外异常是 `VectorStoreError("sqlite_operation_failed")`(TASK-302 公共契约,**不是 raw OperationalError**)
- `vector_store.get_chunk_count(project_id) == 0`(整批 rollback)
- 去掉 fault 后重试 `add_chunks(全 N chunks)` → `chunk_count == N`(全部写入)
- **+ duplicate rollback case**:`add_chunks([new1, existing2])` → `ValueError("chunk_id already exists")` → 新 chunk `new1` 不被持久化(查询 chunk_count 验证)

---

## 验收

### 11.1 文档审批

- [x] v0.1 走 GPT R1 二审,反馈台账分级 P0/P1/P2 全采纳(本 v0.2 已反映)
- [ ] v0.2 走 GPT **窄 R2**(只审 R1 7 项修订清单,不重审 D2-D10 主方案)
- [ ] (可能) v0.3 走窄 R3(若 R2 仍有 P0)
- [ ] Codex 实施前最终版进 docs PR(沿用 TASK-302 模式)

### 11.2 实施验收(37 条,v0.3 R2 修订 #3 / #27 + 新增 #35 / #36 / #37)

1. **make check 全管道 5 step 绿**(反例 26 KPI,**禁拆条**;CI 实际命令 = `make lint && make type-check && python -m ruff format --check && make test && bash scripts/check_repo_hygiene.sh`)
2. **pytest -q 全绿 含 RUN_EMBEDDING_INTEGRATION=1 5 passed**(反例 27 KPI,markers / addopts 已 cat pyproject.toml 实地核查)
3. **SourceType Literal + ChunkRecord.source_type 类型注解收紧 + 定义顺序锁 + runtime import 守门**(v0.2 R1 P0-1 + P1-9 + v0.3 R2 P0-1 + P1-5 多重 grep / runtime):
   - `grep -nE 'SourceType = Literal\[' core/interfaces/vector_store.py` 命中 1 行
   - `grep -nE 'source_type: SourceType' core/interfaces/vector_store.py` 命中 1 行(ChunkRecord 字段)
   - `grep -nE 'source_type: SourceType' features/chunking/_chunk_draft.py` 命中 1 行(ChunkDraft 字段)
   - `grep -nE 'source_type: SourceType' features/chunking/_chunk_id.py` 命中 1 行(`make_chunk_id` 签名,v0.3 R2 P1-5)
   - `grep -nE 'RESERVED_SOURCE_TYPES' core/interfaces/vector_store.py` 命中 1 行
   - **定义顺序守门**(v0.3 R2 P0-1):`awk '/^SourceType = Literal\[/{s=NR} /^class ChunkRecord/{c=NR} END{exit !(s>0 && c>0 && s<c)}' core/interfaces/vector_store.py` 退出码 0(SourceType 必须在 ChunkRecord 之前)
   - **runtime import 守门**(v0.3 R2 P0-1):
     ```bash
     python - <<'PY'
     from core.interfaces.vector_store import ChunkRecord, RESERVED_SOURCE_TYPES, SourceType
     from typing import get_args
     assert "source_type" in ChunkRecord.__annotations__
     assert "teaching_unit" in RESERVED_SOURCE_TYPES
     assert set(get_args(SourceType)) == {"m_file", "m_function", "slx_block", "slx_subsystem", "mat_variable", "project_overview", "teaching_unit"}
     print("OK")
     PY
     # 期望:stdout "OK" + exit 0
     ```
4. **features/chunking/ 模块 9 文件全建 + 单文件 ≤ 200 行**(v0.2 R1 P1-1:`wc -l features/chunking/*.py features/chunking/README.md` 全部 ≤ 200,平均 ~80;`ls features/chunking/ | wc -l` ≥ 9)
5. **ChunkingService 类 + 2 个 async 入口方法 + `_embed_drafts` helper**(v0.2 R1 P1-7:`grep -nE 'class ChunkingService|async def build_embed_store_|async def _embed_drafts' features/chunking/chunking_service.py` 命中 4 行)
6. **ProjectGraphProvider Protocol 注入**(`grep -nE 'class ProjectGraphProvider\(Protocol\)' features/chunking/chunking_service.py` 命中 1)
7. **ChunkDraft dataclass frozen 无 embedding/model_name/created_at**(`grep -nE 'embedding|model_name|created_at' features/chunking/_chunk_draft.py` 0 命中;test_chunking_service_unit 断言)
8. **chunk_id 命名空间 + sha1 hash suffix 12 chars + 空 identifier 抛 ValueError**(v0.2 R1 P2-1):
   - `a b.m` vs `a_b.m` 生成不同 chunk_id(hash suffix 防碰撞)
   - sha1 suffix 长度 == 12
   - `make_chunk_id(project_id, source_type)` 无 identifier_parts → `ValueError("empty_chunk_identifier")`
9. **`make_overview_chunk_id(project_id)` 固定格式 `{project_id}::project_overview`**(无 hash suffix,D14 dup no-op 锚点)
10. **6 类 chunk 在测试 fixture 上产出**(`m_file / m_function / slx_block / slx_subsystem / mat_variable / project_overview`;**不产 teaching_unit**,D6 守门)
11. **chunk 计数日志输出**(P2-1,format `project_chunks_added: project_id={} m_file={} m_function={} slx_block={} slx_subsystem={} mat_variable={}`;**不含完整 chunk_id**,P1-6)
12. **source_text 模板 snapshot 通过**(P2-2,7 类模板含 fixture 中文路径 / 空 docstring / 超长 parameters / subsystem 超过 top-N / overview 字段长 / **长 description 截断 P1-8**)
13. **source_text 总长 ≤ 1024 chars**(test_source_text_templates_unit 全样本断言;**1024 是产品侧预算 非 tokenizer 边界**,P1-5 措辞)
14. **截断后以 `[…]` 结尾**(若长度 == 1024 且原长 > 1024)
15. **docstring 截断 ≤ _DOCSTRING_MAX_CHARS=300 chars**(单字段)
16. **parameter value 截断 ≤ _PARAM_VALUE_MAX_CHARS=80 chars**(单字段);最多 12 个参数
17. **subsystem child_block_names 截断 ≤ _MAX_SUBSYSTEM_CHILD_BLOCK_NAMES=20 个**;超过加 `等 N 个` 后缀;**按 SlxModel.subsystems[name] 原始顺序取**(v0.2 R1 P2-2,不重排)
18. **description 字段级截断 ≤ _DESCRIPTION_MAX_CHARS=300 chars**(v0.2 R1 P1-8 新增):长 description 不挤掉 file_role / functions_count
19. **空工程 / 空 .mat / 无 block .slx / 0 drafts 不调 embedder**(v0.2 R1 P1-7 / P1-9):
    - test_chunking_service_unit 三个 fixture 全 0 chunk + log "project_chunking_skipped: ... reason=no_chunks"
    - mock embedder.embed 在空 drafts 时 **未被调用**(call_count == 0)
20. **mark_ready 顺序锁**(v0.2 R1 P0-5):UploadService.process 测试 — mock embedder 抛异常,GET /projects/{id}/status 仍为 ready 且 `vector_store.get_chunk_count(project_id) == 0`
21. **overview 顺序锁**(v0.2 R1 P0-5):ProjectOverviewService.get_or_generate 测试 — chunk_overview 抛异常时,cache.put 已完成 + return overview 正常
22. **chunk_project 路径 NOT delete + dup no-op**(v0.2 R1 P0-4 D14 大改):
    - 测试用 mock vector_store 验证 `delete_by_project_id` **未被调用**
    - 同 project 连续调两次 `build_embed_store_project_chunks` → 第二次 add_chunks 抛 ValueError(`exc.args == ("chunk_id already exists",)`)→ catch + log info "project_chunks_already_exist" + return 0
    - chunk_overview 后再调 chunk_project → overview chunk 仍存在(关键防御 P0-4)
23. **chunk_overview 路径 dup 时 debug no-op + 用 exc.args 精确匹配**(v0.2 R1 P0-2 + P1-5 D14):
    - 连续调两次同 project_id → 第二次走 dup no-op,return 0
    - 第二次日志级别 == **DEBUG**(非 INFO,P1-5 避免 cache hit 每次 GET 打 info)
    - 实现用 `exc.args == ("chunk_id already exists",)` 精确匹配(P0-2;不调用 `str(exc)`)
24. **AppSettings # Chunking 段 6 字段含 pydantic Field 边界校验**(v0.2 R1 P1-8 加 description):`grep -nE 'chunking_max_source_text_chars|chunking_docstring_max_chars|chunking_param_value_max_chars|chunking_max_params_per_block|chunking_max_subsystem_child_block_names|chunking_description_max_chars' app/config.py` **6 行命中**,每行含 `Field(default=...` + `ge=...` + `le=...`
25. **.env.example 6 字段含注释**(对齐 AppSettings 默认值,v0.2 R1 P1-2 修改文件清单已含)
26. **禁引用 raw_code**(`grep -rnE 'raw_code' features/chunking/` → 0 命中)
27. **禁 logger.exception / str(exc) + 禁任何 level 出 source_text / docstring / parameter / chunk_id**(v0.2 R1 P1-6 加严 + v0.3 R2 P1-4 扩范围):
    - `grep -rnE 'logger\.exception|str\(exc' features/chunking/ features/ingest/upload_service.py features/overview/overview_service.py` → 0 命中
    - `grep -rnE 'logger\.(debug|info|warning|error).*(source_text|docstring|parameter|chunk_id)' features/chunking/ features/ingest/upload_service.py features/overview/overview_service.py` → 0 命中
    - **v0.3 R2 P1-4 关键扩范围**:grep 必须覆盖本任所有修改文件,not just features/chunking/
28. **依赖方向锁 grep**(R1 P1-7):
    - `grep -rnE 'from features\.overview\._' features/chunking/` → 0 命中(禁 overview 私有 helper)
    - `grep -rnE 'from adapters' features/chunking/` → 0 命中(禁 adapters)
29. **`ChunkingError` feature-private 定义 + 不污染 core**(v0.2 R1 P0-3 新增):
    - `grep -n 'class ChunkingError' features/chunking/_errors.py` 命中 1
    - `grep -rn 'ChunkingError' core/ api/middleware/error_handler.py core/domain/exceptions.py` → **0 命中**(feature-private 守门)
30. **overview cache hit 补偿测试通过**(v0.2 R1 P1-5 D16 新增 + v0.3 R2 P1-1 性能澄清):
    - cache hit + chunk 已存在 fixture → 调用 `get_or_generate` 后,**embed 被调用 1 次**(v0.3 R2 P1-1 承认成本)+ add_chunks dup no-op,return cached overview;chunk_count 不增加
    - cache hit + chunk 不存在(模拟 TASK-303 上线前老项目)→ 补写成功,新 chunk_count == 1
    - cache miss + chunk 不存在 → 正常生成 + 写入
31. **search-only 守门**(P1-2):`get_args(SourceType)` 含 `"teaching_unit"` 但测试 fixture chunk 集中无 `source_type == "teaching_unit"`(D6 守门)
32. **chunk 数公式正确**(v0.2 R1 P1-3):测试用 fixture 验证 `len(drafts) == count_file_m + count_function + count_block + count_subsystem + sum(len(mat.variables))`;**不混入** project_overview / FILE_SLX / FILE_MAT / PARAMETER
33. **`m_file.symbol_name == None`**(v0.2 R1 P1-4):test fixture 断言 file 类 ChunkDraft.symbol_name 全 None(非 file_role)
34. **TASK-302 ABC 不动验证**(v0.2 R1 P0-1 + 不动文件守门):
    - `grep -nE 'class VectorStore\(ABC\)|class ChunkRecord' core/interfaces/vector_store.py` 命中各 1
    - 5 方法签名不变(用 `git diff main -- core/interfaces/vector_store.py` 仅看到 (a) SourceType / RESERVED_SOURCE_TYPES 追加 + (b) ChunkRecord.source_type 类型注解 `str → SourceType` + (c) 可能的 `from __future__ import annotations` import 调整,**无其他字段变更**)
35. **`add_chunks` 单事务原子性硬前提验证 — fault-injection integration test**(v0.4 R3 P0-1 大重写;v0.3 mock 自验证 = 循环论证):
    - **新增测试文件**:`tests/features/chunking/test_vector_store_atomicity_contract.py`(放本任 tests 目录,验证 TASK-302 下游契约,**不修改 TASK-302 实现**)
    - **测试设计**(用**真实** SqliteVectorStore + 真实 schema,**不是 mock**):
      1. `tmp_path` 文件 DB + 真实 `SqliteVectorStore` 实例 + 真实 schema init
      2. 先创建 project_status_record(满足 FK 约束,若存在)
      3. 构造 N 个真实 `ChunkRecord`
      4. monkeypatch aiosqlite Connection.execute(或类似低层方法),使第 k 次 INSERT 后抛 `sqlite3.OperationalError`
      5. 调用 `await vector_store.add_chunks(chunks)`:断言对外抛 `VectorStoreError("sqlite_operation_failed")`(TASK-302 公共契约,**不是 raw `OperationalError`**)
      6. 断言 `await vector_store.get_chunk_count(project_id) == 0`(整批 rollback)
      7. 去除 monkeypatch fault 后重试 `await vector_store.add_chunks(chunks)`,断言 `chunk_count == N`(全部写入)
    - **duplicate rollback case**:
      1. 先写入 `existing_chunk_2`(单条成功)
      2. 调用 `add_chunks([new_chunk_1, existing_chunk_2])`
      3. 断言抛 `ValueError("chunk_id already exists")`(`exc.args == ("chunk_id already exists",)`)
      4. 断言 `new_chunk_1` **未被持久化**(`chunk_count` 仅含 `existing_chunk_2`)
    - **守门 grep**:
      ```bash
      ls tests/features/chunking/test_vector_store_atomicity_contract.py  # 文件存在
      grep -n 'SqliteVectorStore' tests/features/chunking/test_vector_store_atomicity_contract.py  # 用真实 store
      grep -n 'VectorStoreError("sqlite_operation_failed")\|sqlite_operation_failed' tests/features/chunking/test_vector_store_atomicity_contract.py  # 验证 TASK-302 公共契约翻译
      ```
    - **Stage 0 初筛 — Python 抽函数体脚本**(v0.5 R4 P0-1 采纳 GPT 方案 B,与 R6 § Stage 0 必查同款):
      ```bash
      python - <<'PY'
      from pathlib import Path

      path = Path("adapters/storage/sqlite_vector_store.py")
      lines = path.read_text(encoding="utf-8").splitlines()

      start = next(i for i, line in enumerate(lines) if line.startswith("    async def add_chunks("))
      end = next(
          (i for i in range(start + 1, len(lines)) if lines[i].startswith("    async def ")),
          len(lines),
      )

      body = "\n".join(lines[start:end])

      required_groups = [
          ("BEGIN", ["BEGIN"]),
          ("COMMIT", ["COMMIT", ".commit("]),
          ("ROLLBACK", ["ROLLBACK", ".rollback("]),
          ("OperationalError", ["OperationalError"]),
          ("sqlite_operation_failed", ['VectorStoreError("sqlite_operation_failed")', "sqlite_operation_failed"]),
      ]

      missing = [
          name
          for name, needles in required_groups
          if not any(needle in body for needle in needles)
      ]

      if missing:
          raise SystemExit(f"add_chunks contract check failed; missing: {', '.join(missing)}")
      print("add_chunks contract OK")
      PY
      ```
      期望:stdout `"add_chunks contract OK"` + exit 0;5 项必需组群任一缺失 → SystemExit + 列缺失项;Codex 停手抛冲突给 PM
      **关键**:v0.4 原 awk range 命令 `awk '/async def add_chunks\(/,/^    async def /'` 因 `add_chunks` 定义行同时匹配 start + end pattern,**只输出函数签名行,函数体被忽略** → 会误报 Stage 0 不满足前置契约 → 误阻断 Codex(v0.5 R4 P0-1 采纳 GPT 方案 B Python 抽函数体避开此坑)
      **v0.5 反例 28 PM 兜底**:架构师本地无 repo,**Codex 实施前 PM 在真实 `adapters/storage/sqlite_vector_store.py` 上跑此 Python 脚本兜底验证**;退出码 0 = TASK-302 满足前置契约,Codex 可进入实施;退出码非 0 = 停手回补 TASK-302
    - **若 Stage 0 Python 脚本 + fault-injection 测试发现 TASK-302 未满足前置假设**:Codex **停手抛冲突给 PM,不可硬上**(决策 09 纪律 1);需先回补 TASK-302
    - **注**:本任不修 `adapters/storage/sqlite_vector_store.py`(不动文件守门);**新增测试文件验证 TASK-302 已落地契约,不算修改 TASK-302 实现**(类比 contract test 模式)
    - **关联反例 31 升仪 KPI (e)**(v0.4 R3 P0-1 主动追加):"验收测试 / Stage 0 命令必须验证真实下游契约,不能 mock 自验证自身;当 D / R 段标明'前置假设 X'时,验收必须 fault-inject / integration test 验证 X,不能用 mock 实现 X 自验证(循环论证)"
36. **DI 注入链路完整性 fixture 测试 — awk range + Python inspect 守门**(v0.4 R3 P1-2 修订;v0.3 单行 grep 多行函数签名会误报):
    - **运行时 fixture 守门**:
      - `overview_service._chunking_service is app.state.chunking_service`(FastAPI TestClient 注入验证)
      - `upload_service._chunking_service is app.state.chunking_service`(同款)
    - **Python `inspect.signature` 静态守门**(测试文件 `test_di_injection_unit.py`):
      ```python
      import inspect
      from features.ingest.upload_service import UploadService
      from features.overview.overview_service import ProjectOverviewService
      from api.dependencies import get_upload_service, get_overview_service
      
      assert "chunking_service" in inspect.signature(UploadService).parameters
      assert "chunking_service" in inspect.signature(ProjectOverviewService).parameters
      assert "chunking_service" in inspect.signature(get_upload_service).parameters
      assert "chunking_service" in inspect.signature(get_overview_service).parameters
      ```
    - **awk range 守门**(扫多行函数签名,v0.4 R3 P1-2 修订):
      ```bash
      # get_upload_service 函数体扫 chunking_service Depends 注入
      awk '/def get_upload_service\(/,/^\) -> UploadService:/' api/dependencies.py \
        | grep -q 'chunking_service: ChunkingService = Depends(get_chunking_service)'
      # get_overview_service 同款
      awk '/def get_overview_service\(/,/^\) -> ProjectOverviewService:/' api/dependencies.py \
        | grep -q 'chunking_service: ChunkingService = Depends(get_chunking_service)'
      # UploadService.__init__ 函数体扫 chunking_service 参数
      awk '/class UploadService:/,/def process\(/' features/ingest/upload_service.py \
        | grep -q 'chunking_service: ChunkingService'
      # ProjectOverviewService.__init__ 同款
      awk '/class ProjectOverviewService:/,/async def get_or_generate\(/' features/overview/overview_service.py \
        | grep -q 'chunking_service: ChunkingService'
      ```
37. **反例 31 升仪到决策 09 patch 落地**(v0.3 R2 主动升仪 + v0.4 R3 P0-1 加 KPI (e)):
    - `grep -nE '反例 31' docs/decisions/20260603-09-architect-must-verify-not-assume.md` 命中
    - 反例 31 **KPI 5 条**(v0.4 R3 加 (e))全部落 docs:(a) grep "若/可能/待/上游应/前端应/等等/TODO";(b) 本任可闭环不转嫁;(c) R 段 vs D 段最终一致;(d) "等等"标记 finalize 前必须解决;**(e) 验收测试不能 mock 自验证依赖契约硬前提**
    - 03 索引同步:决策 09 反例库 30 → 31

### 11.3 PR 元信息

- 分支:`task/TASK-303-chunking`
- 标题:`TASK-303: 工程分块策略 + chunk metadata + source_text 模板(Week 3 第 3/7)`
- 关联 issue / 文档 PR:同步出 docs PR(`task/TASK-303-design`)

---

## 给 Codex 的提示

### 类比 anchor(实地 cat 已确认 main HEAD `83a7948`)

- **node_id 命名空间 helper**:`features/overview/_node_id.py`(P1-6 chunk_id 类比;**加 sha1 hash suffix 是 D9 新增,_node_id.py 没有此特性**)
- **节点 builder**:`features/overview/_pg_nodes.py`(D15 NodeType → SourceType 映射的类比;但 mat_variable 不走 ProjectGraph,直取 Project.mat_files.variables)
- **service 入口**:`features/overview/overview_service.py` ProjectOverviewService(本任 ChunkingService 类比构造 + DI)
- **KeywordRetriever 模板**:`features/chat/_retriever.py` line 125-206(D7 模板沿用 m_function / slx_block;扩 4 新类型)
- **lifespan + DI**:`api/main.py` AsyncExitStack 现有 embedder + vector_store 装配点(TASK-302 commit `83a7948`);本任在后追加 chunking_service
- **SQLite anchor**:无新增(D12 不动 schema)

### 关键约束

- **决策 11 决策 1**:`embedder.embed(...)` + `graph_provider.build(...)` 均为同步重活,必须 `await asyncio.to_thread(...)` 桥接(TASK-302 已实战通过)
- **决策 11 决策 2**:logger.error metadata-only,**严禁 `logger.exception` / `str(exc)`**;失败日志只含 project_id / source_type / chunk_count / exception class name
- **反例 21 KPI**:domain 字段引用前必须 view m_file.py / slx_model.py / project.py 等实地核查(本任已 surface 全字段于 § 输入)
- **反例 24 KPI**:既有代码改动前必须 view 当前代码骨架(本任 § 输入 § 接口契约已 surface);UploadService.process line 116 + ProjectOverviewService.get_or_generate line 57 是修改锚点
- **反例 25 KPI**:所有 grep 用 POSIX 字符类(本任验收清单已用 `[[:upper:]]` / 字面匹配)
- **反例 26 KPI**:验收 #1 必须 `make check` 全管道,禁拆条
- **反例 27 KPI**:pyproject.toml markers 已注册(TASK-301 加 integration + slow);本任沿用 `@pytest.mark.integration` + `RUN_EMBEDDING_INTEGRATION=1` skipif
- **反例 28 KPI**:Stage 0 命令"预期输出"由架构师本地实测(或 PM 兜底声明,本任沿用第十七任工艺);Codex 跑出不符停手抛冲突
- **反例 29 KPI**:接口签名 / 字段集 / 命名跨段一致性 grep(本任已自审)
- **反例 30 KPI**:任何变更跨段同步;严禁因"avoid confirmation bias"跳过机械数数

### 实施建议

#### 关键决策点高频踩坑列表

- **D1 SourceType 定义位置 + 类型注解收紧**(v0.2 R1 P0-1):必须在 `core/interfaces/vector_store.py`(P1-1);**`ChunkRecord.source_type` 字段类型注解从 `str` 改为 `SourceType`**(TASK-302 P2-2 预留合法变更);`ChunkDraft.source_type: SourceType`(P1-9)
- **D4 mat_variable 数据来源**:直取 Project.mat_files.variables,**不要遍历 ProjectGraph.nodes**(pre-R1 P0-2)
- **D11 mark_ready 顺序**:`mark_ready` / `cache.put` 必须在 chunk 化前完成,chunk 化包裹 try/except(pre-R1 P0-5)
- **D11 `_embed_drafts` 公共 helper**(v0.2 R1 P1-7):project + overview 两路径**都走** helper,统一长度校验;**不要**只在 project 路径校验长度
- **D13 ChunkDraft vs ChunkRecord**:ChunkingService 内部生成 ChunkDraft,embed 后 materialize ChunkRecord(pre-R1 P0-1);不要试图用 `ChunkRecord(embedding=[])` 占位
- **D14 chunk_project — v0.2 关键反转!**(R1 P0-4):**直接 `add_chunks(chunks)`,NOT `delete_by_project_id`!** 若 `ValueError` 且 `exc.args == ("chunk_id already exists",)` → log info "project_chunks_already_exist" + return 0(同 project_id 视为不可变 MCS 快照,dup no-op 幂等);其他 ValueError 不吞
- **D14 chunk_overview dup — v0.2 关键改 exc.args!**(R1 P0-2):catch `ValueError` 后**用 `exc.args == ("chunk_id already exists",)` 精确 tuple 匹配**;**严禁用 `str(exc)`**(本任验收 #27 grep 守门);dup 走 **debug log**(v0.2 R1 P1-5:避免 cache hit 每次 GET 打 info)+ return 0;其他 ValueError 不吞
- **D16 overview cache hit 补偿**(v0.2 R1 P1-5 新增):`ProjectOverviewService.get_or_generate` **cache hit / miss 两路径都** best-effort 调 `build_embed_store_overview_chunk`;依赖 D14 dup no-op 幂等(老项目补偿 + 间歇错恢复)
- **`ChunkingError` feature-private**(v0.2 R1 P0-3):**只**在 `features/chunking/_errors.py` 定义,继承 `RuntimeError`(非 MxaError);**严禁** import 到 `core/domain/exceptions.py` / **严禁** 进 `api/middleware/error_handler.py` ERROR_MAP;调用方 best-effort try/except 捕获,不上 HTTP 500
- **D7 sanitizer 字段级截断**:docstring 单字段 ≤ 300 chars;param value 单字段 ≤ 80 chars;最多 12 参数;subsystem child 最多 20 名(**按 SlxModel.subsystems[name] 原始顺序取** v0.2 R1 P2-2,不重排);**description 单字段 ≤ 300 chars**(v0.2 R1 P1-8 新增)
- **D8 source_text 总长**:落 SQLite 前总长截断 ≤ 1024 chars(D8);**不是 tokenizer 边界**(P1-5)
- **D9 chunk_id hash suffix**:`sha1(raw_id.encode("utf-8")).hexdigest()[:12]`,防 sanitize 碰撞(P1-6);**空 identifier 抛 `ValueError("empty_chunk_identifier")`**(v0.2 R1 P2-1)
- **D9 日志安全 — v0.2 R1 P1-6 加严!**:**任何 logger level(DEBUG / INFO / WARNING / ERROR)均不得输出** 完整 chunk_id / source_text / docstring / parameter value;**本地调试用 pytest assertion / snapshot 文件,不走 logger**
- **D10 依赖方向**:禁 `from features.overview._*`(私有);禁 `from adapters`(分层)(P1-7)
- **禁引用 raw_code**:验收 grep 守门(D7)

#### 测试 helper 复用

- TASK-301 已在 `tests/adapters/embedding/conftest.py` 建 MockEmbeddingProvider;**本任直接 import 复用**(TASK-302 P2-4 同款):
  ```python
  from tests.adapters.embedding.conftest import MockEmbeddingProvider
  ```
- 或本任在 `tests/features/chunking/conftest.py` 内复制 mock(若跨 conftest import 不便)
- VectorStore mock 可类比 TASK-302 `test_sqlite_vector_store_unit.py` 模式

#### 文件大小约束

- 04 § 4:单 .py 文件 ≤ 300 行;本任 features/chunking/ **9 个文件**预估 ≤ 200,如某文件实测超 200 → 拆分:
  - `_source_text_templates.py` 可拆 `_templates_m.py` + `_templates_slx.py` + `_templates_mat.py` + `_templates_overview.py`
  - `_project_chunker.py` 可拆 `_chunker_m.py` + `_chunker_slx.py` + `_chunker_mat.py`

### Stage 0 实地核查清单(架构师本地无 repo,Codex 跑后 PM 兜底,沿用第十七任工艺)

> 本 v0.1 给出**核查维度**,**具体命令 + 期望输出由 R2 通过后再细化**(反例 28 KPI:不凭印象先写命令,等架构师本地实测;本任沿用第十七任 Stage 0 工艺声明)。
>
> Codex 跑这些 cat / grep,任一不符**停手抛冲突给 PM,不要硬上**。

核查维度(R2 后细化为 18-20 条具体命令):

1. `core/interfaces/vector_store.py` ChunkRecord 14 字段 + 5 方法 ABC(TASK-302 main HEAD `83a7948`)
2. `core/domain/m_file.py` MFile / MFunction 字段集
3. `core/domain/slx_model.py` SlxModel.subsystems: dict[str, list[str]](无独立 SlxSubsystem)
4. `core/domain/mat_metadata.py` MatVariable / MatMetadata 字段
5. `core/domain/project.py` Project / FileInfo / ProjectType 字段
6. `core/domain/project_graph.py` NodeType 7 类(含 PARAMETER 但本任不 emit)
7. `core/domain/source_ref.py` 6 字段(SourceRef 无 chunk_id)
8. `core/domain/teaching_unit.py` 字段(D6 reserved 预留)
9. `features/overview/overview_schemas.py` ProjectOverview 12 字段 + 5 子 schema(TASK-207 freeze)
10. `features/overview/_node_id.py` make_*_id 系列(D9 类比 anchor)
11. `features/overview/overview_service.py` ProjectOverviewService.get_or_generate line 57(D11 挂载点 2)
12. `features/ingest/upload_service.py` UploadService.process line 116(D11 挂载点 1)
13. `features/chat/_retriever.py` KeywordRetriever line 66-206(D7 模板类比)
14. `api/main.py` lifespan AsyncExitStack 现有装配点(TASK-302 commit 后状态)
15. `api/dependencies.py` get_chat_service 等模式(D10 DI 类比)
16. `app/config.py` # Vector 段(TASK-302 加)+ 本任要加 # Chunking 段
17. `pyproject.toml` `[tool.pytest.ini_options]` markers integration + slow(TASK-301 已加)
18. `.github/workflows/ci.yml` 5 step 对齐 Makefile check target
19. `scripts/check_repo_hygiene.sh / .py` 6 条规则(反例 26 KPI)
20. 本任 v0.1 自身跨段一致性 grep(反例 29 + 30 KPI):
    - `grep -nE 'SourceType|ChunkDraft|ChunkingService|build_embed_store_' docs/tasks/task-303-*.md` 验证多处描述一致

### 完工动作(决策 08 三件套)

```
git status
git log --oneline main..HEAD
git push origin task/TASK-303-chunking
```

### PR

- 分支:`task/TASK-303-chunking`
- 标题:`TASK-303: 工程分块策略 + chunk metadata + source_text 模板(Week 3 第 3/7)`
- 正文:Codex 给 PM,PM 在 GitHub 网页创建 PR(反例 22 教训:docs / 代码都走 PR)

### 决策 09 反例 31 patch 草稿(v0.3 R2 主动升仪 — 搭车 chore #2 落地)

> Codex 实施时,把以下文本以**字节级 append** 到 `docs/decisions/20260603-09-architect-must-verify-not-assume.md` 文件末尾(沿用第十六任反例 27/28 / 第十七任反例 29/30 同款字节级 Python patch 模式)。03 索引 § "决策 09 反例库" 计数 30 → 31 同步。

```text
---

## 反例 31:架构师识别到问题但回避拍硬决策(决策回避 / 软妥协 / 转嫁 / 用"等等"标记不改)

**来源**:第十八任架构师 TASK-303 v0.1 → v0.2 → v0.3 → v0.4 跨 R1 + R2 + R3 **三次审查 5 同源**:
- R1 P0-1:SourceType 软妥协("向后兼容"避 TASK-302 漂移,实际 TASK-302 P2-2 预留 + Literal runtime 兼容 str = 零成本)
- R1 P0-4:chunk_project 重建闭环转嫁("前端 / 上游应清 overview cache",实际本任内 D14 反转 + D16 cache hit 补偿可闭环)
- R2 P0-2:R6 partial 论证用"幂等天然处理"软论证绕开 add_chunks 实际批量语义,**v0.2 finalize 时已能识别**
- R2 P1-1:v0.2 D16 性能段用"等等"明确标记矛盾**却 finalize 时没改完**
- **R3 P0-1**(v0.4 新增):**验收 #35 用 mock VectorStore 验证 TASK-302 原子性 = 循环论证**(用 mock 自验证自身 = 假装满足硬前提的隐蔽形态)

**根因**:架构师在 R 风险段 / trade-off 段 / 验收设计识别到问题,但选择"留余地 / 软妥协 / 转嫁给上下游 / 用'等等' / 'TODO' 标记不改 / **用 mock 自验证假装满足**"等回避动作;表面像边界论证 / 测试覆盖,实际是不敢拍硬决策 / 不真正验证依赖。

**KPI 5 条**(v0.4 R3 P0-1 加 (e);后续架构师 + Codex 必查):

1. 每个 D 决策候选 / R 风险段写完后,**grep 本文档** "若 / 可能 / 待 / 上游应 / 前端应 / 等等 / TODO" 自查软妥协痕迹;有命中 → 必须解决或正式声明 Phase 2 接力
2. 凡是本任内可拍闭环的,**不留给上下游**;转嫁前必须问"本任真的不能解决吗?" — 一般答案是"能"
3. R 风险段与 D 决策段必须**最终一致**:若 R 段标记问题但 D 段未解决,v0.x finalize 前必须解决 — 否则下游 审查 / Codex 实施 P0 必爆
4. 用"等等" / "但是" / "TODO" / "标记问题但 v0.x 未改" 等自我警示标记,finalize 前**必须 grep 自查 + 问题必须解决**(不允许带"等等"标记进入正式 v0.x)
5. **(v0.4 R3 P0-1 新增,循环论证守门)验收测试 / Stage 0 命令必须验证真实下游契约,不能用 mock / fake / stub 自验证自身**;当 D 决策或 R 风险段标明"前置假设 X"时,**验收必须 fault-inject / integration test 验证 X**,不能用 mock 实现 X 自验证(典型反例:R6 假设 TASK-302 add_chunks 原子,验收 #35 写"用 mock 实现单事务语义" = 循环论证);finalize 前 grep 验收测试 "mock" / "fake" / "stub" 关键词,确认未在硬前提验证位置滥用

**与既有反例的边界**:
- 反例 19 / 24(凭印象写):是"没核查";反例 31 是"已识别但没拍"
- 反例 23(用了不存在符号):是"凭印象用错";反例 31 是"明知问题不解决"
- 反例 29 / 30(跨段同步漏):是"机械漏检";反例 31 是"主动回避"
- 反例 31 是**决策心态 + 验证设计**层面踩坑,前面反例多是**执行机械**层面

**第十八任 KPI 兑现声明**:TASK-303 v0.4 finalize 时,grep "若 / 可能 / 待 / 上游应 / 前端应 / 等等 / mock / fake / stub" 全文,所有命中确认在合法语境(历史台账 / 反衬 / Phase 2 接力声明 / 单元测试合理使用 mock 替代不验证硬契约的部分)。
```

**Stage 0 必查**(Codex 落实施前):
- `cat docs/decisions/20260603-09-architect-must-verify-not-assume.md | tail -50`:确认目前末段无反例 31(避免重复 append)
- `grep -c "## 反例" docs/decisions/20260603-09-architect-must-verify-not-assume.md`:append 前应为 30,append 后应为 31

### PM 兜底验证步骤(v0.5 R4 P0-1 新增 — 反例 28 KPI 闭环)

> **背景**:架构师本地无 repo,v0.5 R4 P0-1 Python 脚本未经本地实测;**Codex 实施前 PM 兜底跑一次此 Python 脚本**,验证 TASK-302 `SqliteVectorStore.add_chunks` 是否满足本任前置硬契约(D14 dup no-op 设计依赖此前置)。
> 
> 沿用第十七任 TASK-302 Stage 0 工艺(架构师无 repo / PM 兜底实测),反例 28 KPI 闭环。

**PM 兜底验证清单**(Codex 实施前 PM 在仓库根目录执行):

1. **核查 main HEAD**:
   ```bash
   git log -1 --oneline main -- adapters/storage/sqlite_vector_store.py
   ```
   预期:命中 `83a7948`(TASK-302 merge commit)或后续 hotfix commit;若有非 TASK-302 commit 修改此文件,先告知架构师

2. **跑 Stage 0 Python 脚本验证 add_chunks 满足前置契约**:
   ```bash
   python - <<'PY'
   from pathlib import Path

   path = Path("adapters/storage/sqlite_vector_store.py")
   lines = path.read_text(encoding="utf-8").splitlines()

   start = next(i for i, line in enumerate(lines) if line.startswith("    async def add_chunks("))
   end = next(
       (i for i in range(start + 1, len(lines)) if lines[i].startswith("    async def ")),
       len(lines),
   )

   body = "\n".join(lines[start:end])

   required_groups = [
       ("BEGIN", ["BEGIN"]),
       ("COMMIT", ["COMMIT", ".commit("]),
       ("ROLLBACK", ["ROLLBACK", ".rollback("]),
       ("OperationalError", ["OperationalError"]),
       ("sqlite_operation_failed", ['VectorStoreError("sqlite_operation_failed")', "sqlite_operation_failed"]),
   ]

   missing = [
       name
       for name, needles in required_groups
       if not any(needle in body for needle in needles)
   ]

   if missing:
       raise SystemExit(f"add_chunks contract check failed; missing: {', '.join(missing)}")
   print("add_chunks contract OK")
   PY
   ```
   **三种结果分支**:
   - **stdout `"add_chunks contract OK"` + exit 0** → TASK-302 满足前置契约,**Codex 可以进入实施**
   - **SystemExit + 列出缺失组群**(如 `missing: BEGIN, ROLLBACK`)→ TASK-302 当前未满足前置假设,**Codex 停手抛冲突给 PM**(决策 09 纪律 1);PM 与架构师商议是否回补 TASK-302 或走 R2 GPT 方案 B(预检 + ChunkingError fallback)
   - **start = StopIteration**(`async def add_chunks(` 子串未找到 — 比如缩进非 4 空格 / 函数名改名)→ Codex 停手,**架构师必须先核查 main HEAD 实际函数签名**

3. **若 Python 脚本通过,PM 把验证输出反馈给架构师**(回 transcript):
   ```
   PM 已跑 Stage 0 Python 脚本;
   stdout: add_chunks contract OK
   exit code: 0
   → TASK-302 前置契约满足,Codex 可进入实施
   ```

4. **架构师收到 PM 验证结果后**,sign off Codex 实施;若 PM 验证失败,启动决策 09 纪律 1 回补流程

**反例 28 KPI 闭环**:架构师本地无 repo → 凭印象写 awk 命令踩坑(R4 P0-1)→ v0.5 用 GPT 方案 B Python 抽函数体避开 awk 边界陷阱 → PM 兜底实测 Python 脚本 → 闭环。

---

### 关键约束 reminder

- **反例 14**:bash 命令不带中文括号
- **反例 17**:commit subject 单行无 body
- **反例 19-30**:全部 KPI 实地核查
- **决策 11**:async + to_thread / logger.error metadata-only(TASK-302 已首次实战通过)
- **决策 09 纪律 1**:Stage 0 任一不符停手抛冲突

任一不符**停手抛冲突给 PM,不要硬上**。

---

## 关联文档

- 关联宪法版本:**v2.1(冻结,不修改)**
- 关联决策:`docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / `20260604-11`
- 类比 Task:
  - TASK-204(SQLite anchor)
  - TASK-205(KeywordRetriever source_text 模板 anchor)
  - TASK-207(ProjectOverview schema anchor)
  - TASK-301(EmbeddingProvider anchor)
  - **TASK-302(ChunkRecord freeze + R9 / P2-2 接力点 + R2 隐私显式例外论证)**— 本任直接消费
- 前置 commit:main HEAD `83a7948`(TASK-302 merge)
- **关联反例**:
  - 反例 21(domain 字段凭印象 — 本任已 surface 全字段于 § 输入,反例 21 KPI 兑现)
  - 反例 24(代码骨架凭印象 — 本任已 surface UploadService / OverviewService 入口行号,反例 24 KPI 兑现)
  - 反例 23(凭印象用不存在符号 — pre-R1 + R1 P0-3 ChunkingError 同源,v0.2 已落 `features/chunking/_errors.py`)
  - 反例 29(接口跨段一致性 grep — 本任已三轮自审 SourceType / ChunkDraft / ChunkingService / str(exc) / delete_by_project_id / ChunkingError / D16 / "8 文件" 跨段一致)
  - 反例 30(变更跨段同步 — 本任 D 决策表 + 接口契约 + 范围 + 决策日志 + 风险 + 验收 + 给 Codex 提示 **七段同步**;v0.2 finalize 前抓到 5 处 delete_by_project_id 残留 → 已补;**v0.3 finalize 前抓到 "8 文件" + 验收 #27 grep 范围 + DI 注入链路 跨段同步** → 已补;反例 30 KPI 严格兑现)
  - **反例 31 主动升仪入决策 09**(v0.3 R2 升仪 + v0.4 R3 加 KPI (e);不再是 session-local 候选):"**架构师识别到问题但回避拍硬决策(决策回避 / 软妥协 / 转嫁 / 用'等等'标记不改 / 循环论证假装满足硬前提)**"
    - 触发证据 **5 同源 + 跨 3 次审查**:R1 P0-1(软妥协)+ R1 P0-4(转嫁)+ R2 P0-2(软论证未拍板)+ R2 P1-1(用"等等"标记不改)+ **R3 P0-1(循环论证)**
    - **KPI 5 条**(v0.4 R3 加 (e)):(a) D / R 段写完 grep "若/可能/待/上游应/前端应/等等/TODO" 自查;(b) 本任可闭环的不转嫁;(c) R 段问题 D 段必须解决;(d) "等等" 标记 finalize 前必须 grep + 解决;**(e) 验收测试必须验证真实下游契约,不能 mock 自验证(循环论证守门)**
    - patch 草稿见 § 给 Codex 提示 § "决策 09 反例 31 patch 草稿"

---

**版本**:v0.5(R4 GPT 1 P0 全采纳;**PM 同意修完直接进 Codex,不过 R5**)
**日期**:2026-06-06
**作者**:Claude(架构师,第十八任)
**main HEAD**:`83a7948`(TASK-302 merge)
**审批级别**:**GPT 二审 R1 + R2 + R3 + R4**(R4 通过 1 项 surgical 修订;**v0.5 = 最终版**;**不过 R5**,直接进 Codex)
**接续**:本 v0.5 → **PM 兜底验证 Stage 0 Python 脚本** → Codex 派活 → PR → main merge → TASK-304(21/32)
**R4 反馈整体评估**:**1 P0 = 验收 / Stage 0 命令级精修(awk range 起始行立即结束 bug),0 业务设计漏洞**;v0.4 业务方案 GPT 明示通过
**v0.5 ↔ v0.4 差异概览**(全部 surgical):
- **R6 Stage 0 必查 + 验收 #35 Stage 0 初筛**(R4 P0-1):2 处 `awk '/async def add_chunks\(/,/^    async def /'` 命令(因 add_chunks 定义行同时匹配 start + end pattern 在起始行立即结束 bug)→ **合并为单个 `python - <<'PY' ... PY` heredoc**(采纳 GPT 方案 B):用 Python 抽函数体 + 5 项必需组群检查(BEGIN / COMMIT / ROLLBACK / OperationalError / sqlite_operation_failed)
- **§ 给 Codex 提示新增 § "PM 兜底验证步骤"**(v0.5 R4 P0-1 反例 28 KPI 闭环):架构师无 repo,Codex 实施前 PM 兜底跑 Python 脚本验证 TASK-302 满足前置契约;退出码 0 → Codex 可进入;非 0 → 停手回补 TASK-302
- **反例 28 KPI PM 兜底声明**:架构师本地无 repo → 反例 28 KPI 转 PM 兜底实测(沿用第十七任 TASK-302 工艺)
- 业务方案 / 决策日志 / 风险段 / 接口契约 全部不动(R4 已闭合)

**v0.5 = 最终版,直接进 Codex**(PM sign off);**任何 R5 后续修订需架构师 + PM 双方同意**

---

**v0.4 ↔ v0.3 差异概览**(历史 audit):
- **验收 #35 大重写**(R3 P0-1):mock VectorStore 自验证 = 循环论证 → 改真实 SqliteVectorStore fault-injection integration test(`tests/features/chunking/test_vector_store_atomicity_contract.py`);用真实 schema + monkeypatch aiosqlite + 验证 `VectorStoreError("sqlite_operation_failed")` 公共契约翻译 + duplicate rollback case
- **§ 输入 § 1 ChunkRecord 段重写**(R3 P1-1):删除 "本任不动接口 / 只追加 / str 兼容" 残留;明示"唯一接口级修改 = D1 类型注解收紧"
- **验收 #36 grep 改 awk range + Python inspect**(R3 P1-2):多行函数签名守门;`inspect.signature(UploadService).parameters` 检查 chunking_service 注入
- **R6 Stage 0 必查改 awk range 限定 add_chunks 函数体 + OperationalError 翻译扫**(R3 P1-3):**删除** "async with execute 自动 transaction" 误导措辞;明示"仅看到 async with execute 不足以证明事务"
- **反例 31 KPI 5 条**(R3 P0-1 主动加 (e)):验收测试 / Stage 0 命令必须验证真实下游契约,不能 mock 自验证(循环论证守门);决策 09 patch 草稿 + 搭车 chore + 关联文档 三段同步
- 验收 37 条总数不变;#35 / #36 / #37 内容精修

---

**v0.3 ↔ v0.2 差异概览**(历史 audit):
- D1 SourceType 定义顺序锁死在 ChunkRecord 之前(R2 P0-1;删除"文件末追加"措辞;加 awk + runtime python import 守门)
- R6 partial write 论证大重写(R2 P0-2):**采纳方案 A** 硬锁 TASK-302 `add_chunks` 单事务原子性为本任前置硬假设;Stage 0 必查 BEGIN/COMMIT;若非原子 Codex 停手;验收新增 #35
- D16 性能段重写(R2 P1-1):删除"无 embed 调用 / 几乎零成本"自相矛盾措辞;承认 cache hit + dup 路径会先 embed ~50ms,MCS 可接受
- DI 注入链路锁死(R2 P1-3):UploadService / ProjectOverviewService `__init__` 加 `chunking_service` 参数;`get_upload_service` / `get_overview_service` 同步 `Depends(get_chunking_service)`;验收新增 #36 fixture 测试
- 验收 #27 grep 守门扩范围(R2 P1-4):覆盖本任所有修改文件(features/chunking + features/ingest/upload_service.py + features/overview/overview_service.py)+ 加 chunk_id 守门
- `make_chunk_id(source_type: SourceType, ...)` 收紧(R2 P1-5)
- "8 文件" 全文修为 "9 文件"(R2 P1-2)
- **反例 31 主动升仪到决策 09**(v0.3 主动)+ 03 索引反例库计数 30 → 31 + 决策 09 文末 append patch(搭车 chore #2 落地)+ 验收新增 #37
- 验收 34 → **37 条**(新增 #35 add_chunks 原子性测试 / #36 DI 注入链路 fixture / #37 反例 31 升仪 patch 落地)

---

**v0.2 ↔ v0.1 差异概览**(历史 audit):
- D14 主决策反转(R1 P0-4):chunk_project 不再 delete_by_project_id 改 dup no-op
- 新增 D16 overview cache hit 补偿(R1 P1-5)
- ChunkRecord.source_type 类型注解 str → SourceType 真收紧(R1 P0-1)
- 新增 `features/chunking/_errors.py` feature-private ChunkingError(R1 P0-3)
- 验收 28→34 条(新增 ChunkingError 守门 / D16 测试 / chunk 数公式 / source_type 静态守门 / TASK-302 ABC 不动 / description 截断)
- 修改文件 6→7(加 `.env.example`)+ 新增文件 8→9(加 `_chunk_draft.py` + `_errors.py`)
- 字段级 sanitizer 加 description 上限(R1 P1-8)
- 日志守门加严:任何 logger level 不出 source_text / docstring / parameter value(R1 P1-6)
