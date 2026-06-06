# TASK-302: SQLite 向量存储 + 检索基础设施(Week 3 第 2/7)

## 状态

🔲 v0.4(R3 反馈 1 P0 + 1 P2 全采纳 / 反例 30 立即入仓 / 待窄 R4)

---

## R3 反馈台账(2026-06-06,GPT 窄 R3 1 P0 + 1 P2 全采纳,触发窄 R4)

> R3 主判定:**D1-D12 主方案保留**(chunks 独立表 / BLOB float32 / Python 真 cosine / lifespan to_thread / FK CASCADE / D12 最小迁移 / 4 补丁 ABC + D11 齐备 — R3 18a-18d 全过);**唯一 P0** 落在 R3 18e —— v0.3 改 ABC + D11 加四补丁,**漏了同步到 § 11.2 验收清单**。**反例 30 立即入仓**决策 09,叠加第二十任 KPI。

### 1 P0 必改(触发窄 R4)

| # | 问题 | v0.4 修订位置 |
|:-:|---|---|
| P0-1 | § 11.2 验收 N 条当前只到 23 项,**未同步 v0.3 ABC + D11 加的四补丁**(`created_at` 出入库 / `query` 空数据语义 / 混维混模型规则 / `add_chunks` 异常语义);R3 18e 自审项数承诺"17-30"但实际只到 23 — Codex / PM 按 § 11.2 验收会漏掉 R2 要求补的四个边界补丁守门 | § 11.2 追加验收 24-30(四补丁 4 项 + R3 18abc 三项一致性 grep 守门 3 项 = 共 7 项);§ Stage 0 R3 18e 改写为 GPT R3 精确版本"§ 11.2 验收 N 条 24-27 覆盖 v0.3 四补丁;28-30 覆盖 R3 三个全文一致性 grep 守门" |

### 1 P2 建议(采纳)

| # | 建议 | v0.4 修订位置 |
|:-:|---|---|
| P2-1 | R3 grep 命中 R1/R2 反馈台账 / 反例 30 候选记录的"旧问题引用"应不算 active spec 失败 | § Stage 0 R3 18 项前加注:"R3 grep 仅审 § 范围 / § 接口契约 / § 决策 / § 风险 / § 验收 / § 给 Codex 提示等当前规范段;命中历史反馈台账 / 反例候选记录的旧问题引用,不按 active spec 失败处理" |

### v0.4 反例 30 立即入仓决策 09(根据 v0.3 末尾承诺规则触发)

**v0.3 末尾承诺规则**:"R3 通过且 R3 不再抓到同源残留 → 反例 30 入仓;**R3 又抓到 → 反例 30 立即入仓 + 第二十任 KPI**"。

**R3 P0-1 = 反例 30 同源**(跨段一致性失败的另一面):不是"grep 关键词枚举不全"(v0.2 → R2 那次),而是"**同一变更应该出现在所有该出现的段,架构师漏了一段**"。本质同反例 5(改 ALLOW_EXTS 没全文 grep 同步)同源,第八任就总结过纪律 5。

**反例 30 触发现场**(v0.3 → R3 之间):架构师写 v0.3 时,在 § 接口契约 1 ABC 设计要点加了四个边界补丁(P1-3 created_at / P1-4 query 空数据 / P1-5 混维 / P1-6 add_chunks 异常语义),同时在 § D11 测试维度也加了对应 ★ 维度,**但 § 11.2 验收 N 条没同步**。架构师跑 R3 18a-18d 自审通过,**故意跳过 18e**,错误理由是"避免 self-confirmation bias"。

**v0.3 → v0.4 之间架构师认知纠错**:grep 跨段一致性自审 ≠ confirmation bias。`§ 11.2 项数 = D11 项数?` 是机械数数,不存在判断偏见;真正的 confirmation bias 是"我已认定 X 是对的,倾向证明 X"。架构师把"避免 self-confirmation"误用到了**应该自检**的机械流程上。

**第二十任 KPI 升级**(决策 09 末尾追加,叠在第十九任反例 29 KPI 之上):
- 任何变更(P0/P1 反馈采纳 / 新增决策 / 新增字段 / 新增规则)在文档多段同时出现时,**写完 v0.x 终稿前**必须 grep 一遍**所有应该出现的段**是否都同步更新;**禁止以"avoid self-confirmation bias"为理由跳过机械数数 / 跨段一致性自审**;machine check ≠ judgment check
- 反例 29 KPI(grep 接口名 / 字段名)+ 反例 30 KPI(grep 语义动词短语 + 跨段同步项数)= 第十九任 + 第二十任 KPI 双重叠加
- 操作清单:每轮 v0.x → R 反馈采纳后,**强制 grep 验证**:(a) 变更是否在 § 范围、§ 接口契约、§ 决策日志、§ 风险、§ 验收、§ Stage 0、§ 给 Codex 提示**全部应在段**出现;(b) 同一变更在不同段的描述是否语义一致(用反例 29 KPI grep 接口名 + 反例 30 KPI grep 语义短语);(c) **架构师自审 5 项核查清单时严禁因 "self-confirmation" 跳过任何机械检查项**

**D8 搭车 chore 更新**:由 v0.2/v0.3 的 4 项扩成 v0.4 的 **5 项**(反例 29 + **反例 30**(立即入仓)+ 03 索引 + TASK-204 § 9.6 erratum + (可选)反例 31 候选)。

---

## R2 反馈台账(2026-06-06,GPT R2 1 P0 + 7 P1 + 3 P2 全采纳,触发窄 R3)

> R2 主判定:**v0.2 方向基本成立**(D1-D12 主方案保留 — chunks 独立表 / BLOB float32 / Python 真 cosine / lifespan to_thread / FK CASCADE / D12 最小迁移全部不推翻);**新发现 1 个 P0 — 反例 29 KPI 自审漏过的语义短语残留**,触发**窄 R3**(只审 5 项,不重审 D1-D12)。

### 1 P0 必改(触发窄 R3)

| # | 问题 | v0.3 修订位置 |
|:-:|---|---|
| P0-1 | § 不做 段 line 278 仍残留 `delete_by_project_id`"**供 TTL cleanup worker 调用**"的旧叙事 — 与 v0.2 主体 ABC/D6 + R2 收敛的 "**不由 cleanup worker 显式调用,走 FK CASCADE 路径**" 冲突;Codex 若按残留语义实施会扩大修改范围 + 双删 + 责任边界不清 | § 不做 该项全段重写为 R2 给出的精确版本:"`delete_by_project_id` 供测试断言 + Phase 2 显式清理/监控使用;TTL 删除主路径走 `cleanup worker → ProjectStore.delete(project_id) → CASCADE`" |

### 7 P1 必改(不升 R3)

| # | 问题 | v0.3 修订位置 |
|:-:|---|---|
| P1-1 | § 风险 R1 仍写"启动失败 EmbeddingModelLoadError 503 返回"误导表述 — 与 v0.2 D8/handler P1-4 修订"lifespan 失败不走 HTTP 路径"冲突 | § 风险 R1 改"启动失败 → uvicorn/TestClient 启动失败 → 用户视角服务暂不可用,**本 Task 不承诺 HTTP 503 body**;503 handler 仅为未来 runtime/lazy reload 路径保留" |
| P1-2 | BLOB codec 提示写"`"<f4"` 或 `np.float32` + tobytes" — `np.float32` 是 **native endian**,不等价于固定 little-endian;Codex 写成平台相关格式风险 | § 给 Codex 提示 + § 接口契约 3 删 "或 `np.float32`";统一为 `_FLOAT32_LE = np.dtype("<f4")`,encode 用 `np.asarray(vec, dtype=_FLOAT32_LE)`,decode 用 `np.frombuffer(blob, dtype=_FLOAT32_LE)` |
| P1-3 | `created_at: datetime \| None = None` 字段存在但**出入库格式规则未写死** — Codex 可能返回 str 破坏 dataclass 类型契约 | § 接口契约 1 ABC 设计要点 加 created_at 规则:入库 None → `datetime.utcnow()`,非 None 原值;存储 `isoformat()` naive UTC(对齐 TASK-204);出库 `datetime.fromisoformat(row[...])`;解析失败 → `VectorStoreError("invalid_created_at")` |
| P1-4 | `query` 在 project 存在但 chunks=0 / project_id 不存在的返回语义未写死 | § 接口契约 1 ABC 设计要点 加 query 空语义:**chunks=0 → 返回 `[]`**(不做 query_dim 校验,无 embedding_dim 可比);**project_id 不存在 → 仍返回 `[]`**(检索层"无知识"由 TASK-304 ChatService 做 E 类降级;`add_chunks` 才严格校验 project_id 存在) |
| P1-5 | 混维 / 混模型数据运行时规则未明确 — `query` 若同 project 内有不同 embedding_dim 的 rows,numpy stack 失败 → 底层 ValueError 泄漏 | § 接口契约 1 ABC 设计要点 加混维规则:**`add_chunks` 单批次内所有 embedding 维度必须一致 → 否则 `ValueError("mixed_embedding_dim")`;新 chunk 与该 project 现有 chunks 的 `embedding_dim` 必须一致 → 否则 `VectorStoreError("embedding_dim_mismatch")`**;`model_name` 本 Task 只存不强校验,同维不同 model_name 不阻断 |
| P1-6 | `add_chunks` 缺失 project_id 异常语义在 § D11 测试维度写"ProjectNotFoundError(**或** IntegrityError → ValueError)" — "或"让测试和实现都漂 | § 接口契约 1 ABC 设计要点 + § D11 测试维度 加固定语义:**`add_chunks` 任一 chunk.project_id 不存在 → `ProjectNotFoundError`(显式预查 SELECT 1);chunk_id 重复 → `ValueError("chunk_id already exists")`;sqlite OperationalError 兜底 → `VectorStoreError("sqlite_operation_failed")`**(类比 SqliteChatStore.append_message 显式预查模式) |
| P1-7 | § 接口契约 2 SqliteVectorStore 实现要点仍写 "numpy 点积(D4)" — Codex 若只看 implementation bullet 不读 D4 详情,会回潮 R1 P1-1 normalize=True 假设 | § 接口契约 2 改 "numpy **真 cosine**(D4:dot / norms,零向量保护)" |

### 3 P2 建议(全采纳)

| # | 建议 | v0.3 修订位置 |
|:-:|---|---|
| P2-1 | `QueryHit.chunk: ChunkRecord` 长期可拆 `ChunkPayload`(不带 embedding)— Phase 2 观察点 | § 风险 R5 后 + § 接力点 加 Phase 2 hint;本 Task 不改接口 |
| P2-2 | `source_text` 长度上限留 TASK-303 接力点点名,不留 Phase 2 | § 接力点 加"**TASK-303 必须定义 source_text 最大长度 / 截断策略**,避免超长工程片段进入 SQLite 与 prompt" |
| P2-3 | R3 走窄审 5 项核查清单(GPT 自己给的方法论) | § Stage 0 + 验收 注入 R3 窄审清单 5 项 |

### v0.3 反例 30 候选(暂不入仓,待 R3 通过观察是否升级)

**反例 30 触发现场**(v0.2 → R2 之间):v0.2 跑了反例 29 KPI 自审(`grep -nE 'VectorStore\.query|delete_by_project|ChunkRecord|EmbeddingModelLoadError|from exc|from None'`)+ 修了 4 处残漏,**但 GPT R2 仍抓到 2 处**:
- P0-1:`delete_by_project_id`(字面对)+ "供 cleanup worker 调用"(语义残留,grep 字面 OK 但语义错)
- P1-1:"EmbeddingModelLoadError 503 返回"短句变体(没在 v0.2 自审 grep 关键词里)

**根因**:反例 29 KPI 自审 grep 靠架构师枚举关键词,**枚举不全 = 残留漏过**。

**反例 30 候选 KPI**(待 R3 通过后决定是否入决策 09):
- 反例 29 自审不仅 grep 接口名 / 字段名,还要 grep **语义动词短语**:"供 X 调用" / "X 返回 N" / "由 X 触发" / "为 X 保留" / "类比 X 节奏" 等
- 或:抽样人工对照 review(类比 GPT 二审)— 任何一审 / 二审 P 抓出 N 个残留 → 升级窄三审

**为何 v0.3 不直接入仓**:R3 是窄审,不该扩范围加新治理;反例 30 是否升级 KPI 应观察 R3 / R4 结果。**R3 通过且 R3 不再抓到同源残留 → 反例 30 入仓**;**R3 又抓到 → 反例 30 立即入仓 + 第二十任 KPI**。

D8 搭车 chore 维持 v0.2 的 4 项(反例 29 + 03 索引 + TASK-204 § 9.6 erratum + 反例 30 候选记录);反例 30 是否成为正式入仓项待 R3 后决定。

---

## R1 反馈台账(2026-06-06,GPT R1 4 P0 + 8 P1 + 4 P2 全采纳)

### 4 P0 必改(全采纳,触发 R2)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P0-1 | `VectorStore.query` 是否调用 embedder 自相矛盾 — § 上游契约 2 写"`vector_store.query` 内调 `embedder.embed([query])`",D6 + § 接口契约 1 写"`query(query_embedding: list[float])` + VectorStore 不持有 embedder";一份文档两套接口边界 | § 上游契约 2 删"内调 embedder.embed"句;§ 接口契约 1 + D6 重申"VectorStore 不持有 embedder,本 Task 不调 embedder;调用方 TASK-304 VectorRetriever 负责先 `embedder.embed([query_text])[0]`";全文 grep 一致性自审 |
| P0-2 | `ChunkRecord` 字段集与 chunks DDL 不一致 — DDL `model_name TEXT NOT NULL` / `created_at TEXT NOT NULL` / `embedding_dim INTEGER NOT NULL` 必填,但 `ChunkRecord` 三字段缺失,无法实现 `add_chunks` | § 接口契约 1 `ChunkRecord` 加 `model_name: str` 必填 + `created_at: datetime \| None = None`(store 在 None 时填);`embedding_dim` **不**进 `ChunkRecord`,由 `len(embedding)` 派生入库(DDL 字段保留作运行时校验) |
| P0-3 | lifespan `raise EmbeddingModelLoadError("...") from exc` 与"不漏 traceback / path / 原异常内容"硬约束冲突 — `from exc` 保留 cause 链,ASGI/uvicorn/TestClient 打印 chained traceback,原异常 repr/path 仍出现在控制台或日志聚合 | § 接口契约 8 + D7 改 `raise EmbeddingModelLoadError("model_load_failed") from None`;新加测试断言"失败路径输出**不含**原始 `OSError("...sensitive path...")` message,不用 `logger.exception`,不输出 `str(exc)`" |
| P0-4 | R2 隐私删除链路表述不自洽 — 同时承诺 FK CASCADE + cleanup worker 显式调 `delete_by_project_id`,但修改文件清单没含 cleanup worker;文档承诺了未装配路径 | § R2 收敛为**方案 A — 以 FK CASCADE 为主**:TASK-302 不改 cleanup worker;`ProjectStore.delete(project_id)` 删除 `project_status_record` 时 chunks 自动 CASCADE 删;新加验收测试"create project → add chunks → project_store.delete → `get_chunk_count(project_id) == 0`" |

### 8 P1 必改(全采纳,不升 R2)

| # | 问题 | v0.2 修订位置 |
|:-:|---|---|
| P1-1 | D4 真余弦 vs 依赖 `normalize=True` 点积 — 若 `embedding_normalize=False`,点积≠余弦,query 结果错 | § D4 改"真 cosine 实现:`scores = np.divide(dots, norm(matrix) * norm(query), out=zeros, where=denom != 0)`",不依赖 normalize 假设;加零向量测试 case |
| P1-2 | BLOB codec 需显式校验长度 / 维度 / dtype / endian | § 接口契约 3 + § 给 Codex 提示 加 `_vector_codec.py` 校验合约:`len(blob) % 4 == 0` + `len(blob) // 4 == embedding_dim` + `len(query_embedding) == embedding_dim` + 固定 `<f4`(little-endian float32)+ decode 异常翻译 `VectorStoreError` |
| P1-3 | v1→v2 schema 不应要求用户删库 — 当前"`schema_migration_required` 抛错 + 用户删 `data/mxa.db`"会丢已有 project / chat 历史 | § R4 改最小迁移;新增 **D12** 决策:`schema.py` 加 `_migrate_v1_to_v2(conn)` 函数(只 `CREATE TABLE IF NOT EXISTS chunks` + `UPDATE schema_version SET version=2`);`init_schema` 在 `version < CURRENT_SCHEMA_VERSION` 时调对应迁移函数而非抛错 |
| P1-4 | `EmbeddingModelLoadError` 503 handler 语义需降级 — lifespan 失败时 app 未启动,**不**走 HTTP 路径;handler 是为未来 lazy reload / runtime dependency 保留 | § 接口契约 5 + D8 改"handler 仍加,为未来 lazy reload / runtime path 保留;**本 Task lifespan 测试断言异常类型,不断言 HTTP 503 body**";用户可见性段从"HTTP 503"改"启动失败 / 服务不可用" |
| P1-5 | 命名 `delete_by_project` vs `delete_by_project_id` 全文不一致;"4 方法"vs"5 方法含 aclose"表述不一 | 全文统一 **`delete_by_project_id`**;ABC 表述统一"**4 业务方法 + 1 lifecycle 方法**:`add_chunks` / `query` / `delete_by_project_id` / `get_chunk_count` / `aclose`" |
| P1-6 | `line_range: tuple[int, int] \| None` 与 DDL `line_start` / `line_end` 两 nullable int 的入出库规则未写死 | § 接口契约 1 加 nullable 规则:入库 `None → (NULL, NULL)`;出库两 NULL → `None`,两非 NULL → `tuple[int, int]`,只有一个 NULL → `VectorStoreError("invalid_line_range")` |
| P1-7 | AppSettings `vector_top_k` / `vector_min_score` 缺边界校验 | § D9 加:`vector_top_k ∈ [1, 50]`(pydantic Field `ge=1, le=50`);`vector_min_score ∈ [-1.0, 1.0]`(`ge=-1.0, le=1.0`);运行时 `query(..., top_k, min_score)` 非法值抛 `ValueError` |
| P1-8 | R2 隐私论证"派生文本不算原始内容"表述偏弱;source_text 可能含函数名 / block 名 / 参数值即原始工程敏感内容 | § R2 改"`source_text` 是 RAG 可用性的**最小必要工程派生文本**,是 01 § 9 / 02 § 12 的**显式例外**;受 project_id 隔离 + TTL/CASCADE 删除 + 日志禁出 + 未来加密预留约束";新加验收"`source_text` 不进日志 / 不进错误 message / 不进 exception repr" |

### 4 P2 建议(全采纳)

| # | 建议 | v0.2 修订位置 |
|:-:|---|---|
| P2-1 | `query` 两阶段读取减少 `source_text` 内存暴露面(SELECT chunk_id + embedding → 算 top_k → SELECT 完整 metadata/source_text) | § 给 Codex 提示 加 hint;不锁接口层(MCS 单工程规模可接受单阶段) |
| P2-2 | `source_type` 不锁 Literal,TASK-302 只透传 string | § 接口契约 1 加注"TASK-302 透传,枚举由 TASK-303 统一定型" |
| P2-3 | 复合索引 `(project_id, source_type)` / `(project_id, model_name)` 先不加 | § 接口契约 3 加注"等 TASK-306 评测后再加" |
| P2-4 | 测试 helper(MockEmbeddingProvider)不跨 conftest import,放 `tests/helpers/embedding.py` | § 给 Codex 提示 加 hint(Codex 实施时落地) |

### v0.2 新增 D12 决策:v1→v2 最小迁移(P1-3)

详 § 决策日志 D12。不引 alembic;`schema.py` 加 `_migrate_v1_to_v2(conn)` 函数;`init_schema` 在 `version < CURRENT_SCHEMA_VERSION` 时调对应迁移而非抛错。`adapters/storage/schema.py` 的 `init_schema` 逻辑因此**改动**(超出 v0.1 "不动 init_schema 逻辑"声明),修订 § 输出 / § 不动文件清单。

### v0.2 新增治理 chore:**反例 29** 入仓决策 09(自审一致性缺失)

**反例 29 触发现场**(v0.1 → R1 之间):架构师写 v0.1 § 上游契约 2 时写"vector_store.query 内调 embedder.embed",同份文档 § 接口契约 1 + D6 又写"VectorStore 不持有 embedder,query 接收 embedding 而非 text;调用方负责 embed";写完 v0.1 终稿前**未跨段 grep 自审接口一致性**。

接续反例 24 / 25 / 26 / 27 / 28 同源:都是"写完没自审"但维度不同 — 反例 28 是单点(命令期望输出),反例 29 是跨段(同一接口在多段描述)。GPT R1 P0-1 抓住。

**第十九任 KPI 升级**(决策 09 末尾追加,叠在反例 26 + 27 + 28 KPI 之上):
- 任何接口签名 / 字段集 / 数据流向 / 命名,在文档多处描述时,写完 v0.x 终稿前必须 `grep -nE '<接口名|字段名>' <task文档>` 跨段交叉验证,**所有出现点描述必须一致**;不一致即 P0
- 接续反例 28 KPI:**所有"X 在多处描述"陈述前必须跨段 grep 一致性自审**,这是架构师工作流硬约束

D8 搭车 chore 由 v0.1 的 3 项扩成 v0.2 erratum 后的 **4 项**(反例 29 + 03 索引 + TASK-204 § 9.6 erratum + (若有)反例 30)。

---

## 审批级别(反例 18 自检 5 维度)

| 维度 | 评分 | 理由 |
|---|---|---|
| 决策密度 | **高**:D1-D11(11 个) | 异常树新增 / chunks schema 形态 / 向量存储格式 / 检索算法 / lifespan 装配工艺 / AppSettings 字段 / 测试策略 / 搭车 chore — 远超 TASK-301 D1-D8(一审 1 轮) |
| 下游扩散面 | **2 强下游**:TASK-303(chunk 化消费 `add_chunks`)/ TASK-304(VectorRetriever 消费 `query`)+ **架构面影响 Phase 2**(向量基础设施一旦定型,sqlite-vec / FAISS 迁移成本高) |
| 用户可见性 | **中**:lifespan 启动时间 +5-10s(首次模型下载触发);**启动失败 = 服务不可用**(uvicorn 退出,非 HTTP 503;P1-4 修订:`EmbeddingModelLoadError` handler 是为未来 lazy reload / runtime path 保留,本 Task lifespan 失败不走 HTTP 路径) |
| 异步 / LLM 首次定型 | **是**:**决策 11 决策 1 首次实战** — lifespan 内 `await asyncio.to_thread(SentenceTransformerEmbedder, ...)` 桥接重活 ~2s + 100MB,模式定型后 TASK-304 同款抄;**整个项目第一个 lifespan 内 to_thread 桥接** |
| 隐私 / 安全 | **首次**:chunks 表存工程内容文本片段(`source_text` 列)— 02 § 12 + 01 § 9 "不记录用户上传的工程内容"硬约束首次入持久层;需要本 Task 拍定边界(chunk 文本是否落 SQLite / TTL 清理路径) |

→ **走 GPT 二审 R1 + R2**(沿用 TASK-104 / 107 / 205 / 304 核心二审模式)。

---

## 上下文

### mxa-tutor 项目快速建立 context

mxa-tutor 是面向中国工科学生(电气 / 自动化 / 通信 / 控制)的 MATLAB / Simulink AI 助教 Web 应用。学生上传 .zip 工程包(.m / .slx / .mat),后端做 Python 静态解析(无 LLM)+ DeepSeek LLM 教学问答。

**当前进度(实地 git log 核查 main HEAD `85b86d3`)**:19/32 Task 完成(TASK-301 嵌入适配器已 merge,但 03 索引仍停留在 TASK-301 🔍 中间态)。Week 3 进度 1/7,**本 Task = Week 3 第二棒(2/7)**。

### 数据流位置(02 § 2)

```
[Parser]  SlxModel / MFile / MatMetadata / FileInfo / file_dependencies
   ↓  无 LLM,纯结构化(TASK-107)
[ProjectGraph]  nodes / edges / entry_points / execution_flow / unresolved_symbols
   ↓  调 LLM 基于 ProjectGraph 生成
[ProjectOverview / TeachingUnit / Chat]  教学化输出,带 SourceRef 证据
   ↓  Week 3 向量化(TASK-301 ✅ + 302 ★ + 303 + 304)
[Vector RAG]  Embedding(TASK-301 ✅)→ SQLite BLOB(本 Task ★)→ 余弦检索(本 Task)→ chunk(TASK-303)→ ChatService 整合(TASK-304)→ 强证据问答
```

本 Task 在数据流的位置:**向量存储 + 检索基础设施层**。
- **接通 TASK-301 EmbeddingProvider**(`adapters/embedding/sentence_transformer.py`)— lifespan 装配 + dependency
- **建 SQLite chunks 表 + 向量列**(BLOB float32 binary,余弦检索)
- **建 VectorStore ABC**(`add_chunks` / `query` / `delete_by_project_id` / `get_chunk_count` / `aclose` — 4 业务方法 + 1 lifecycle,等 TASK-303/304 消费)

**不做**:chunk 化策略(TASK-303)/ VectorRetriever 实现(TASK-304)/ chunk 化的真实数据写入(等 TASK-303)/ 跨工程检索(单工程隔离)。

### 类比 anchor

- **存储层**:`adapters/storage/sqlite_chat_store.py`(commit `5fba99b`,TASK-204 产物)— 几乎 1:1 抄构造函数 / aclose / `async with open_connection` / `aiosqlite.OperationalError → StoreError` / `logger.error metadata-only` 模式
- **schema 升级**:TASK-204 § 9.6 schema.py `CURRENT_SCHEMA_VERSION = 1`(实地 cat 已确认)→ 本 Task bump 到 `2` + 加 chunks 表 DDL
- **lifespan 装配**:`api/main.py` 现有 `AsyncExitStack` + `app.state.project_store / chat_store / chat_service` 模式(commit `dd7a1da` TASK-205 产物);本 Task 加 `app.state.embedder` + `app.state.vector_store`,**且首次用 `await asyncio.to_thread(...)`** 桥接 SentenceTransformer 重活
- **DI**:`api/dependencies.py` `get_chat_store` 是最干净 anchor(`getattr(...) → if None: raise → cast`),本 Task `get_embedder` / `get_vector_store` 全照抄
- **异常 + handler**:`core/domain/exceptions.py` `LLMError(MxaError) → LLMAuthError(LLMError)` 两层模式;`api/middleware/error_handler.py` `_make_handler(503, "llm_auth", "...")` factory + `error_handlers: tuple[...]` 元组

### 关键宪法 / 决策引用

- **02 § 6 决策 1 line 620-624**:SQLite + sentence-transformers,MCS 阶段单工程规模小够用(< 5000 chunk)
- **02 § 6 决策 2**:KISS — 不引入 sqlite-vec / FAISS / pgvector
- **02 § 12 + 01 § 9**:不记录用户上传的工程内容 —— 本 Task chunks 表 `source_text` 列是**唯一例外**,需明确边界(chunk 文本是教学问答必需,删 = RAG 不可用;但 TTL 清理 + project_id 级 delete 必须保证)
- **决策 11 决策 1**:`async def` 内同步重活必须 `await asyncio.to_thread(sync_func, ...)` — 本 Task lifespan 装配 embedder 是该决策**首次实战**
- **决策 11 决策 2**:logger.error metadata-only,禁 `logger.exception` / `str(exc)`
- **决策 06**:Codex 可读仓库文件,文档引用路径不内联全文
- **决策 08**:PM 验 git 三件套 + 字节级 Python 改 docs
- **决策 09 反例 26 + 27 + 28**:hygiene 脚本 + cat pyproject.toml + Stage 0 命令本地实测

---

## 输入(前置依赖)

### 已合并 Task

✅ TASK-001 / 002 / 101 / 104 / 106 / 107 / 108 / 201 / 202 / 203 / 204(`5fba99b`,SQLite 存储 anchor)/ 205(`dd7a1da`,Retriever ABC)/ 206(`746a76d`,ERROR_MAP)/ 207 / **301**(`85b86d3`,EmbeddingProvider 实现 — main HEAD)。

### 上游关键契约(实地核查 main HEAD `85b86d3`,本 Task 不动)

**1. `core/interfaces/embedder.py`**(TASK-101 落地 + TASK-301 实现):
```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    def dimension(self) -> int: ...
```
本 Task **消费**(lifespan 装配 `app.state.embedder`,供 TASK-304 VectorRetriever 调 `embedder.embed([query_text])[0]` 后传给 `vector_store.query`),**不改签名**。**`SqliteVectorStore` 不持有 embedder,本 Task 不调 `embedder.embed`**(P0-1 修订:统一接口边界,详 D6 + § 接口契约 1)。

**2. `adapters/embedding/sentence_transformer.py`**(TASK-301 落地,commit `85b86d3`):
- `SentenceTransformerEmbedder.__init__(model_name, device, normalize)` — 同步 + 重活 ~2s + 100MB 首次下载
- `embed(list[str]) -> list[list[float]]` — 同步,纯本地推理
- `dimension() -> int` — 同步,常数

本 Task **lifespan 装配时用 `await asyncio.to_thread(SentenceTransformerEmbedder, settings.embedding_model_name, settings.embedding_device, settings.embedding_normalize)`** 包装。

**3. `adapters/storage/_connection.py`**(TASK-204 落地):
- `open_connection(db_path) -> AsyncIterator[aiosqlite.Connection]` async context manager
- PRAGMA WAL / busy_timeout=5000 / foreign_keys=ON / synchronous=NORMAL / secure_delete=ON 已配
- `row_factory = aiosqlite.Row` 已配

本 Task SqliteVectorStore 沿用,**不改 PRAGMA**。

**4. `adapters/storage/schema.py`**(TASK-204 落地):
- `CURRENT_SCHEMA_VERSION = 1`(常量 — 实地 cat 确认)
- `_DDL` 含 4 表:`schema_version` + `project_status_record` + `chat_session` + `chat_message`
- `init_schema(conn)` 校验 version > 抛 `unsupported_schema_version` / < 抛 `schema_migration_required`(**v0.2 P1-3 修订:本 Task 改 `init_schema` 逻辑,version < CURRENT 时调 `_migrate_v1_to_v2(conn)` 而非抛错;详 D12**;v0.1 声明"不动 init_schema 逻辑"作废)

**5. `core/domain/exceptions.py`**(TASK-101 + 后续累积,23 类):
- `MxaError` 顶层 / `LLMError → LLMAuthError 等 5 子类` 二层模式 / `StoreError(MxaError)`(TASK-204 加,本 Task 复用为 `VectorStoreError` 父类候选)

本 Task **加 3 个新异常类**(详 D8)。

**6. `api/middleware/error_handler.py`**(TASK-206 落地):
- `error_handlers: tuple[ErrorHandlerSpec, ...]` 元组形态(**与 04 § 10 dict 字面文档漂移,TASK-301 P0-3 已修文档 fence,本 Task 不再触碰 04 § 10**)
- `_make_handler(status_code, machine_code, message)` factory
- `register_error_handlers(app, settings)` 入口

本 Task **在 tuple 末尾追加 1 项**(EmbeddingModelLoadError handler;**handler 为未来 lazy reload / runtime path 保留,本 Task lifespan 失败不走 HTTP 路径,详 P1-4 修订**)。

**7. `app/config.py`**(TASK-108 + 后续累积):
- 现有 7 段:`# LLM` / `# Embedding`(TASK-301 加 3 字段)/ `# Storage` / `# Quota` / `# File limits(基础 + TASK-104 扩展)` / `# Logging`

本 Task **加 1 新段 `# Vector`**(详 D9)。

**8. `features/chat/_retriever.py`**(TASK-205 落地):
- `class Retriever(ABC)` + `async def search(self, project, query, top_k=8) -> list[RetrievalHit]`

本 Task **不动**(TASK-304 才加 VectorRetriever 实现)。

### 必读文档

- `01_PROJECT_CONSTITUTION.md` § 7 异步 + § 9 数据隐私
- `02_ARCHITECTURE_OVERVIEW.md` § 2 数据流 + § 6 决策 1 SQLite + § 12 日志隐私
- `04_ENGINEERING_STANDARDS.md` § 4 文件大小 + § 6 工程规范 + § 9 日志 + § 10 异常处理
- `docs/decisions/20260601-04` ~ `20260603-09` + **`20260604-11`(async + to_thread,本 Task 首次实战)**
- `docs/tasks/task-204-sqlite-storage.md`(SQLite anchor)
- `docs/tasks/task-301-embedding-adapter.md`(EmbeddingProvider anchor + § 12.3 接力点)

---

## 输出(交付物)

### 新增文件(3 个)

| 路径 | 行数估 | 内容 |
|---|---|---|
| `core/interfaces/vector_store.py` | ~30 | `VectorStore` ABC + `ChunkRecord` dataclass(详 § 接口契约) |
| `adapters/storage/sqlite_vector_store.py` | ~200 | `SqliteVectorStore` 实现(类比 `SqliteChatStore` 模式) |
| `adapters/storage/_vector_codec.py` | ~30 | float32 binary BLOB encode/decode helper(`numpy.tobytes` / `numpy.frombuffer`) |

**测试新增(由 Codex 实施)**:
- `tests/adapters/storage/test_sqlite_vector_store_unit.py`(~200 行,mock embedder)
- `tests/adapters/storage/test_sqlite_vector_store_integration.py`(~80 行,真 sentence-transformers,`RUN_EMBEDDING_INTEGRATION=1` skipif)
- `tests/adapters/storage/conftest.py` 补 `MockEmbeddingProvider` 复用(TASK-301 已建,本 Task `from tests.adapters.embedding.conftest import ...`)

### 修改文件(8 个)

| 路径 | 改动范围 | 决策 |
|---|---|---|
| `adapters/storage/schema.py` | bump `CURRENT_SCHEMA_VERSION = 1 → 2` + `_DDL` 末追加 chunks 表 DDL + **加 `_migrate_v1_to_v2(conn)` 函数 + 改 `init_schema` 在 v<CURRENT 时调迁移而非抛错**(P1-3 + D12) | D2 + D3 + D12 |
| `core/domain/exceptions.py` | 加 `EmbeddingError(MxaError)` + `EmbeddingModelLoadError(EmbeddingError)` + `VectorStoreError(StoreError)` | D8 |
| `api/main.py` | lifespan `AsyncExitStack` 内加 `app.state.embedder = await asyncio.to_thread(...)` + `app.state.vector_store = SqliteVectorStore(db_path)` + try/except 翻译为 `EmbeddingModelLoadError` | D7 |
| `api/dependencies.py` | 加 `get_embedder` + `get_vector_store`(类比 `get_chat_store`) | D6 |
| `api/middleware/error_handler.py` | `error_handlers` tuple 末追加 `(EmbeddingModelLoadError, _make_handler(503, "embedding_model_load", "..."))` — **handler 为未来 lazy reload / runtime path 保留,本 Task lifespan 失败不走 HTTP 路径**(P1-4) | D8 |
| `app/config.py` | 加 `# Vector` 段 2 字段(`vector_top_k=8` + `vector_min_score=0.3`) | D9 |
| `.env.example` | 对应 2 字段 + 注释 | D9 |
| `requirements.txt` | 追加 `numpy>=1.26.0,<2.0`(显式声明,反例 12 同源教训) | D10 |
| `pyproject.toml` | **可能**加 `[[tool.mypy.overrides]] module = "numpy.*"`(待 Stage 0 实测,numpy 自带 stubs,**预判不需要**) | — |

### 搭车 chore(本任沿用反例 26-28 同款字节级 Python patch 模式)

| chore | 范围 | 沿用 patch 模式 |
|---|---|---|
| 1. 03 索引补账 | TASK-301 🔍→✅ + Week 3 0/7→1/7 + 18/32→19/32 + line 349 下一步指向 TASK-302 + 日期 | 第十六任 TASK-301 P0-2 同款 7 处字节级 |
| 2. TASK-204 § 9.6 erratum | 文档注释 line 745 `2 = TASK-302 加 chat_message.embedding BLOB(预留)` → 改为 `2 = TASK-302 加 chunks 表(向量存储 + 检索基础设施)` | 字节级 Python `data.index(b"...")` 锚点替换 |
| 3. 反例 29(若本会话踩坑)入决策 09 | 待本会话踩坑账本最终确定 | 第十六任反例 27/28 同款 |

**erratum 理由**:TASK-204 § 9.6 line 745 写"TASK-302 加 chat_message.embedding BLOB(预留)",但本 Task 实地拍定**新建独立 chunks 表**(D2 — 工程内容 RAG 语义 ≠ 聊天消息向量化)。TASK-204 schema.py **代码无任何 v=2 预留**(实地 cat 已确认),只需修文档注释。

### 不动文件(明示)

| 路径 | 不动理由 |
|---|---|
| `core/interfaces/embedder.py` | TASK-301 已落地,本 Task 消费,不改签名 |
| `adapters/embedding/sentence_transformer.py` | TASK-301 已落地,本 Task 消费,不改 |
| `adapters/storage/_connection.py` | TASK-204 已落地,本 Task 沿用 |
| `adapters/storage/sqlite_project_store.py` / `sqlite_chat_store.py` | TASK-204 已落地,作类比 anchor 不改 |
| `features/chat/_retriever.py` / `chat_service.py` | TASK-205 已落地,VectorRetriever 由 **TASK-304** 引入,本 Task 不动 |
| `docs/04_ENGINEERING_STANDARDS.md` § 10 | TASK-301 P0-3 已修 fence;本 Task 不再触碰核心宪法 |

---

## 范围

### 必须做

- [ ] **基础设施层**:
  - [ ] 新建 `VectorStore` ABC + `ChunkRecord` dataclass(`core/interfaces/vector_store.py`)
  - [ ] 实现 `SqliteVectorStore`(类比 `SqliteChatStore`)
  - [ ] BLOB float32 binary encode/decode helper(`_vector_codec.py`)
  - [ ] schema.py 扩 chunks 表 DDL + bump `CURRENT_SCHEMA_VERSION = 2`
- [ ] **异常树扩展**:
  - [ ] 加 `EmbeddingError(MxaError)` + `EmbeddingModelLoadError(EmbeddingError)` + `VectorStoreError(StoreError)`
  - [ ] `error_handler.py` 加 `EmbeddingModelLoadError` handler(machine_code `"embedding_model_load"`,中文文案与 LLMAuthError 同;**handler 为未来 lazy reload / runtime path 保留,本 Task lifespan 失败不走 HTTP 路径**,P1-4)
- [ ] **装配链路**(决策 11 决策 1 首次实战):
  - [ ] `api/main.py` lifespan 加 `await asyncio.to_thread(SentenceTransformerEmbedder, ...)` + `SqliteVectorStore(db_path)`
  - [ ] try/except 翻译 sentence-transformers 库异常为 `EmbeddingModelLoadError`(logger.error metadata-only,决策 11 决策 2)
  - [ ] `api/dependencies.py` 加 `get_embedder` + `get_vector_store`
- [ ] **配置层**:
  - [ ] `AppSettings # Vector` 段加 `vector_top_k=8` + `vector_min_score=0.3`
  - [ ] `.env.example` 对应字段 + 注释
  - [ ] `requirements.txt` 显式加 `numpy>=1.26.0,<2.0`
- [ ] **测试**:
  - [ ] Unit:VectorStore ABC contract / SqliteVectorStore add+query / delete_by_project_id / get_chunk_count / schema_version 升级 / encode-decode round-trip / BLOB 长度校验 / 真 cosine 排序 / 零向量保护 / top_k 截断 / min_score 过滤
  - [ ] Integration(`RUN_EMBEDDING_INTEGRATION=1` skipif):真 SentenceTransformer + 真 SQLite 端到端 add+query
  - [ ] lifespan 集成测试:`app.state.embedder` / `app.state.vector_store` 装配成功 + `EmbeddingModelLoadError` 路径(mock SentenceTransformer 抛异常)
- [ ] **搭车 chore**:03 索引 + TASK-204 § 9.6 erratum + (若有)反例 29 入决策 09

### 不做(明确排除)

- ❌ **chunk 化策略**:本 Task **不**实现 chunk 切分逻辑(`source_text` 怎么从 SlxModel / MFile / Project / Overview 切出来)— **TASK-303 接管**
- ❌ **VectorRetriever 实现 / 替换 KeywordRetriever**:本 Task **不**触 `features/chat/_retriever.py` / `chat_service.py` — **TASK-304 接管**
- ❌ **真实 chunk 数据写入**:本 Task 测试用 mock chunk(`ChunkRecord(...)` 字面构造)走 add+query 路径,**不**触发真实 chunk 化 — 等 TASK-303 / 304
- ❌ **跨工程检索**:`query(embedding, top_k, project_id)` 强制 `WHERE project_id = ?` 过滤,**不支持** project_id=None / 跨工程相似度
- ❌ **批量 embed 优化 / 并行查询 / chunk size 上限**:Phase 2 候选
- ❌ **sqlite-vec / FAISS / pgvector 扩展**:02 § 6 决策 2 KISS,Phase 2 候选
- ❌ **chunk 删除路径完整化**(P0-1 v0.3 修订):本 Task 实现 `delete_by_project_id`,**供测试断言 + Phase 2 显式清理 / 监控使用**;**TASK-302 不改 cleanup worker**,TTL 删除主路径为:`cleanup worker → ProjectStore.delete(project_id) → project_status_record 删除 → chunks FK CASCADE 自动删除`。**不实现 chunk 级 delete**(单 chunk delete 等 TASK-403 用户清理 UI)
- ❌ **embedder 多模型并存 / 模型升级 schema 兼容**:Phase 2 候选(若改模型,chunks 表 embedding 列必须 rebuild;本 Task 加 `model_name` 列预留,具体迁移留 Phase 2)
- ❌ **GPU 部署**:Phase 2 候选

---

## 接口契约

### 1. `VectorStore` ABC(`core/interfaces/vector_store.py`)

```python
@dataclass(frozen=True)
class ChunkRecord:
    """单个 chunk 的入库记录(由 TASK-303 chunk 化逻辑构造,本 Task 不构造,只存)。

    v0.2 修订(P0-2 + P1-6 + P2-2):
    - 加 model_name 必填 + created_at 可选(store 在 None 时填 datetime.utcnow())
    - embedding_dim 不进 ChunkRecord(由 len(embedding) 派生入库,DDL 字段保留作运行时校验)
    - line_range nullable 规则写死(详 § ABC 设计要点)
    - source_type 不锁 Literal,本 Task 透传 string;枚举由 TASK-303 统一定型
    """
    chunk_id: str            # UUID
    project_id: str          # FK → project_status_record.project_id
    source_type: str         # 'm_function' | 'slx_block' | 'slx_subsystem' | 'project_overview' | 'teaching_unit' | etc.(TASK-303 定型,本 Task 透传)
    file_path: str           # 源文件相对路径
    symbol_name: str | None  # 函数名 / block 名 / 变量名
    line_range: tuple[int, int] | None  # 源码行范围(P1-6 规则见下)
    block_id: str | None     # SlxModel block_id
    block_name: str | None
    block_type: str | None
    parent_subsystem: str | None
    source_text: str         # 自然语言描述(供 embedding 用 — 02 § 12 显式例外,见 § 风险 R2)
    embedding: list[float]   # 与 EmbeddingProvider.dimension() 等长
    model_name: str          # 生成此 embedding 的模型名(P0-2 新加,Phase 2 模型升级 rebuild 判断依据)
    created_at: datetime | None = None  # P0-2 新加;调用方传 None 时 store 填 datetime.utcnow()

@dataclass(frozen=True)
class QueryHit:
    """单次 query 命中结果。"""
    chunk: ChunkRecord       # 完整 chunk(含 source_text / metadata 供 TASK-304 ChatService 消费)
    score: float             # 余弦相似度 ∈ [-1, 1](v0.2 真 cosine 实现,不依赖 normalize 假设,详 D4)

class VectorStore(ABC):
    @abstractmethod
    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        """批量入库(已含 embedding,本 Task 不调 embedder)。"""
        ...

    @abstractmethod
    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        """单工程内余弦检索 top-k(强制 project_id 过滤,跨工程隔离)。"""
        ...

    @abstractmethod
    async def delete_by_project_id(self, project_id: str) -> int:
        """删除指定工程所有 chunks,返回删除条数(供测试断言 + Phase 2 监控)。

        v0.2 修订(P0-4):本 Task **不**在 cleanup worker 显式调此方法;
        chunks 的 TTL 清理由 FK CASCADE 路径自动完成
        (`ProjectStore.delete(project_id)` → chunks CASCADE 删)。
        本方法保留作为显式 API,供测试 + Phase 2 用户清理 UI 用。
        """
        ...

    @abstractmethod
    async def get_chunk_count(self, project_id: str) -> int:
        """统计指定工程的 chunk 总数(供测试 + Phase 2 监控)。"""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """资源释放(MCS 阶段 no-op,沿用 SqliteChatStore 模式)。"""
        ...
```

**ABC 设计要点**(详 D6):
- **4 业务方法 + 1 lifecycle 方法**:`add_chunks` / `query` / `delete_by_project_id` / `get_chunk_count` / `aclose`(P1-5)
- `add_chunks` 批量,不支持单条 — 减少 SQL roundtrip,且 chunk 化天然批量
- `query` 强制 `project_id` 参数(无 None),跨工程隔离硬约束 — 与宪法 § 9 "单工程独立"对齐
- `query_embedding: list[float]` 而非 query text — 本 Task **不调 embedder**,**`VectorStore` 不持有 embedder**;调用方(TASK-304 VectorRetriever)负责 `embedder.embed([query_text])[0]` 先行(P0-1)
- `QueryHit.chunk` 含**完整** ChunkRecord(含 `source_text` + metadata)— TASK-304 ChatService 构造 RetrievalHit / SourceRef 需要这些字段
- `delete_by_project_id` 返回 int(删除条数)— 供测试断言 + Phase 2 监控;**不**由 cleanup worker 显式调用(P0-4 + P0-1 v0.3 — 走 FK CASCADE 路径)
- **`line_range` nullable 规则**(P1-6 v0.2):
  - 入库:`None → (line_start=NULL, line_end=NULL)`
  - 出库:两个 NULL → `None`;两个非 NULL → `tuple[int, int]`;**只有一个 NULL → `VectorStoreError("invalid_line_range")`**
- **运行时参数边界**(P1-7 v0.2):`query(...)` 中 `top_k < 1 or top_k > 50` → `ValueError`;`min_score < -1.0 or min_score > 1.0` → `ValueError`
- **`created_at` 出入库规则**(P1-3 v0.3 新增):
  - 入库:`chunk.created_at is None → datetime.utcnow()`;非 None 用原值
  - 存储:`created_at.isoformat()` naive UTC(对齐 TASK-204 时间格式)
  - 出库:`datetime.fromisoformat(row["created_at"])`
  - 解析失败 → `VectorStoreError("invalid_created_at")`
- **`query` 空数据语义**(P1-4 v0.3 新增):
  - **chunks=0(project 存在但无 chunks)→ 返回 `[]`**(此路径**不**做 query_dim 校验,因为无 embedding_dim 可比对)
  - **project_id 不存在 → 仍返回 `[]`**(检索层"无知识"由 TASK-304 VectorRetriever / ChatService 做 E 类降级响应,不在存储层抛 `ProjectNotFoundError`)
  - 与 `add_chunks` 不同:**`add_chunks` 才严格校验 project_id 存在**(写路径必须有 FK 校验防孤儿数据;读路径宽松返回空)
- **混维 / 混模型运行时规则**(P1-5 v0.3 新增):
  - **`add_chunks` 单批次内所有 embedding 维度必须一致** → 否则 `ValueError("mixed_embedding_dim")`(批次内自校验)
  - **新 chunk 的 embedding_dim 必须与该 project 现有 chunks 一致** → 否则 `VectorStoreError("embedding_dim_mismatch")`(显式预查 `SELECT DISTINCT embedding_dim FROM chunks WHERE project_id=?`,>1 行直接拒)
  - `model_name` **只存不强校验** — 同维不同 model_name 不阻断 `add_chunks`;Phase 2 模型升级 rebuild 时基于 `model_name` 列判断
  - 这避免"模型不校验"被误读为"维度也不校验";维度不一致会直接破坏 numpy stack,不该留到 Phase 2
- **`add_chunks` 异常语义固定**(P1-6 v0.3 新增,**禁"或"漂移**):
  - 任一 `chunk.project_id` 不存在 → `ProjectNotFoundError`(显式预查 `SELECT 1 FROM project_status_record WHERE project_id=?`,类比 `SqliteChatStore.append_message` 模式)
  - `chunk_id` 重复 → `ValueError("chunk_id already exists")`(IntegrityError 捕获翻译)
  - sqlite `OperationalError` 兜底 → `VectorStoreError("sqlite_operation_failed")`
  - 混维(批次内 + project 内)→ `ValueError("mixed_embedding_dim")` / `VectorStoreError("embedding_dim_mismatch")`(见上)

### 2. `SqliteVectorStore` 实现(`adapters/storage/sqlite_vector_store.py`)

构造函数:`__init__(self, db_path: str) -> None`(类比 SqliteChatStore,不立即建连接,每方法 `async with open_connection(self._db_path)`)。

**实现要点**(详细代码骨架由 Codex 实施时按类比 anchor 写,本 v0.1 不内联):

- `add_chunks`:`BEGIN` + **显式预查 project_id 存在**(`SELECT 1 FROM project_status_record WHERE project_id=?`,不存在 → `ProjectNotFoundError`,类比 `SqliteChatStore.append_message` 模式;P1-6 v0.3 严格化,禁 IntegrityError 兜底)+ **批次内自校验维度一致**(`ValueError("mixed_embedding_dim")`,P1-5)+ **预查 project 内现有维度**(`SELECT DISTINCT embedding_dim FROM chunks WHERE project_id=?`,>1 行或 ≠ 新维度 → `VectorStoreError("embedding_dim_mismatch")`,P1-5)+ 批量 `INSERT INTO chunks(...) VALUES (?, ?, ...)` + `COMMIT`;`IntegrityError → ValueError("chunk_id already exists")`;`OperationalError → VectorStoreError("sqlite_operation_failed")`;`logger.error metadata-only`
- `query`:`SELECT chunk_id, project_id, source_type, file_path, ..., embedding FROM chunks WHERE project_id=?` → Python 端解码 BLOB + numpy **真 cosine**(D4:`dot / (norm_matrix * norm_query)`,零向量保护 `where=denom > 1e-12`)+ top_k 排序 + min_score 过滤 → 构造 `QueryHit` list 返回。
- `delete_by_project_id`:`DELETE FROM chunks WHERE project_id=?` + `cur.rowcount` 返回 + `COMMIT`
- `get_chunk_count`:`SELECT COUNT(*) FROM chunks WHERE project_id=?`
- `aclose`:no-op

### 3. chunks 表 DDL(`adapters/storage/schema.py` 追加)

```sql
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL,
    source_type       TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    symbol_name       TEXT,
    line_start        INTEGER,
    line_end          INTEGER,
    block_id          TEXT,
    block_name        TEXT,
    block_type        TEXT,
    parent_subsystem  TEXT,
    source_text       TEXT NOT NULL,
    embedding         BLOB NOT NULL,
    embedding_dim     INTEGER NOT NULL,
    model_name        TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (project_id)
        REFERENCES project_status_record(project_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
```

**字段决策**(详 D2):
- `embedding BLOB` + `embedding_dim INTEGER`:BLOB 自描述 + dim 列冗余存(供运行时校验 + Phase 2 多模型并存);**`embedding_dim` 在 `add_chunks` 时由 store 从 `len(chunk.embedding)` 派生填入,不在 `ChunkRecord`**(P0-2)
- `model_name TEXT`:存生成此 embedding 的模型名(Phase 2 升级模型时 rebuild 判断依据)
- `ON DELETE CASCADE`:project 删除时 chunks 联动删(与 chat_session 模式一致);**这是 chunks 删除的主路径**(P0-4)
- `idx_chunks_project`:project_id 单列索引(query 强制按 project_id 过滤);**复合索引 `(project_id, source_type)` / `(project_id, model_name)` 先不加,等 TASK-306 评测确认过滤模式后再加**(P2-3)

**BLOB codec 合约**(P1-2,详 § 给 Codex 提示):
- 固定 dtype:**little-endian float32**(P1-2 v0.3 修订:**必须** `np.dtype("<f4")`,**不**用 `np.float32`(后者是 native endian,跨平台不一致);统一模块级常量 `_FLOAT32_LE = np.dtype("<f4")`)
- encode 校验:`len(chunk.embedding) > 0` 否则 `VectorStoreError("empty_embedding")`
- decode 校验:`len(blob) % 4 == 0` + `len(blob) // 4 == embedding_dim`(读 DDL 列)否则 `VectorStoreError("blob_length_mismatch")`
- query 校验:`len(query_embedding) == embedding_dim`(读 chunks 表任意行)否则 `VectorStoreError("query_dim_mismatch")`
- decode 异常(numpy ValueError / struct error)统一翻译 `VectorStoreError`

### 4. 异常类(`core/domain/exceptions.py` 追加)

```python
class EmbeddingError(MxaError):
    """嵌入模型相关异常基类。"""

class EmbeddingModelLoadError(EmbeddingError):
    """嵌入模型加载失败(下载失败 / 文件损坏 / 设备不支持)。"""

class VectorStoreError(StoreError):
    """向量存储层异常(SQLite BLOB 解码失败 / dim 不匹配 / FK 校验失败等)。"""
```

**设计要点**(详 D8):
- `EmbeddingError` 与 `LLMError` / `ParseError` 平级,二层结构(MxaError → EmbeddingError → EmbeddingModelLoadError)
- `VectorStoreError` 是 `StoreError` 子类 — chunks 表是 storage 一部分,语义上属 StoreError 子树(不引入第三个并列层)

### 5. ERROR_MAP handler(`api/middleware/error_handler.py` `error_handlers` tuple 末追加)

```python
(
    EmbeddingModelLoadError,
    _make_handler(
        503,
        "embedding_model_load",
        "服务暂时不可用,请稍后重试",
    ),
),
```

**设计要点**:
- **handler 语义边界**(P1-4 修订):本 Task lifespan 启动失败时 app **未启动**,**不走** HTTP 路径 → handler **不会**被触发;handler **仍**注册,是为未来 lazy reload / runtime dependency 路径(例如:运行时 embedder 重载 / 健康检查时 embedder 状态校验失败)保留 — 沿用决策 08 "占位 + 渐进装配"模式
- **v0.1 P1-4 修订前的表述误导**:v0.1 § 接口契约 5 写"503 类比 LLMAuthError 节奏(服务暂不可用,用户视角 = 一致体验)" — 这隐含"lifespan 失败 → HTTP 503"语义,与 D7 "失败不掩盖,让 uvicorn 退出"矛盾;v0.2 改为"handler 为未来 runtime path 保留"
- machine_code `"embedding_model_load"` 与异常名对齐
- 中文文案与 `LLMAuthError` 同(避免暴露内部模型加载语义给用户)
- `VectorStoreError` **不**单列 handler — 走父类 `StoreError` handler(500,"系统暂时不可用,请稍后重试"),原因:VectorStoreError 是内部数据问题,与 StoreError 语义重合

### 6. AppSettings 新段(`app/config.py` 追加)

```python
# Vector(TASK-302 新增)
vector_top_k: int = Field(default=8, ge=1, le=50)        # P1-7:配置层边界
vector_min_score: float = Field(default=0.3, ge=-1.0, le=1.0)  # P1-7:配置层边界
```

**设计要点**(详 D9):
- 不加 `vector_batch_size` / `vector_max_seq_length`(Phase 2 候选)
- 与 `# Embedding` 段(TASK-301 加 3 字段)区分语义:Embedding 段管模型,Vector 段管检索行为
- **边界校验**(P1-7):配置层用 pydantic `Field(ge=..., le=...)` 校验启动期非法;运行时 `query(top_k, min_score)` 收到非法值(例:TASK-304 调用时传入用户输入未校验)抛 `ValueError`(由 dependency / route 层接管,非 VectorStoreError)

### 7. dependencies 函数(`api/dependencies.py` 追加)

```python
def get_embedder(request: Request) -> EmbeddingProvider:
    """从 app.state.embedder 取 EmbeddingProvider(由 lifespan 装配)。"""
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise RuntimeError("EmbeddingProvider not initialized; lifespan misconfigured")
    return cast(EmbeddingProvider, embedder)

def get_vector_store(request: Request) -> VectorStore:
    """从 app.state.vector_store 取 VectorStore(由 lifespan 装配)。"""
    store = getattr(request.app.state, "vector_store", None)
    if store is None:
        raise RuntimeError("VectorStore not initialized; lifespan misconfigured")
    return cast(VectorStore, store)
```

类比 `get_chat_store` 完整模式。

### 8. lifespan 装配(`api/main.py` 内 lifespan 函数追加,**决策 11 决策 1 首次实战**)

伪代码 / 架构层:

```python
# 在现有 AsyncExitStack 块内,store / chat_store 装配之后,chat_service 之前
try:
    embedder = await asyncio.to_thread(
        SentenceTransformerEmbedder,
        settings.embedding_model_name,
        settings.embedding_device,
        settings.embedding_normalize,
    )
except Exception as exc:
    logger.error(
        "Embedding model load failed: model_name={} device={} exception={}",
        settings.embedding_model_name,
        settings.embedding_device,
        type(exc).__name__,
    )
    raise EmbeddingModelLoadError("model_load_failed") from None  # P0-3:from None 断异常链

app.state.embedder = embedder
app.state.vector_store = SqliteVectorStore(settings.db_path)
stack.push_async_callback(app.state.vector_store.aclose)
```

**设计要点**(详 D7):
- 失败语义:**不掩盖**(类比 TASK-204 `_bootstrap_db` 失败让 uvicorn 退出 — 基础设施 / schema 错应让用户看到)
- 但**前置 try/except 翻译** sentence-transformers 库自身异常为 `EmbeddingModelLoadError` + logger.error metadata-only(决策 11 决策 2 — 不漏 traceback)
- **`raise ... from None` 断异常链**(P0-3 修订):`from exc` 会保留 cause 链,ASGI/uvicorn/TestClient 打印 chained traceback 时原异常 `repr` / `path` / `str(exc)` 仍出现在控制台或日志聚合,**违反隐私硬约束**;`from None` 完全断链,只保留架构师在 logger 显式落的 metadata 元数据
- 调试访问性的取舍:`from None` 牺牲一定调试便利换隐私强度(必须接受);开发期 Codex 调试可临时 print traceback,生产环境绝不
- `to_thread` 桥接是**决策 11 决策 1 首次实战**(整个项目第一个 lifespan 内重活桥接)
- `vector_store.aclose` 注册到 stack(MCS 阶段 no-op,但保留模式与 `chat_store.aclose` / `project_store.aclose` 一致)

---

## 实施步骤(给 Codex,5 Stage 顺序固定)

| Stage | 范围 | commit 粒度 |
|---|---|---|
| 0 | 实地核查(§ Stage 0 清单 12 条) | 不 commit |
| 1 | 异常类 + ABC + 测试 stub | `feat(domain): add EmbeddingError / VectorStoreError exception classes`<br>`feat(interfaces): add VectorStore ABC + ChunkRecord / QueryHit dataclasses` |
| 2 | schema.py 扩 + bump version + 测试 | `feat(storage): add chunks table DDL + bump schema_version to 2`<br>`test(storage): cover schema_version=2 path` |
| 3 | `_vector_codec.py` + `SqliteVectorStore` 实现 + 测试 | `feat(storage): add float32 BLOB codec helper`<br>`feat(storage): add SqliteVectorStore impl`<br>`test(storage): add SqliteVectorStore unit + integration tests` |
| 4 | lifespan + dependencies + handler + AppSettings + .env.example + requirements.txt + 集成测试 | `feat(api): wire embedder + vector_store in lifespan with asyncio.to_thread`<br>`feat(api): add get_embedder / get_vector_store dependencies`<br>`feat(api): add EmbeddingModelLoadError handler`<br>`feat(config): add # Vector section`<br>`chore(deps): add numpy>=1.26 explicit`<br>`test(api): cover embedder lifespan startup + failure path` |
| 5 | 搭车 chore(03 索引 + TASK-204 § 9.6 erratum) | `chore(docs): bump TASK-301 to ✅ and update Week 3 progress`<br>`chore(docs): erratum TASK-204 § 9.6 schema_version=2 semantics` |

---

## 决策日志

### D1 — 审批级别:GPT 二审 R1 + R2

反例 18 自检 5 维度:决策密度高(11 个 D)/ 下游扩散 2 强 / 用户可见(启动失败 = 服务不可用,P1-4 修订后非 HTTP 503)/ 异步首次定型(决策 11 决策 1 首次实战)/ 隐私首次入持久层(chunks.source_text)。无可类比的"一审 1 轮"先例(TASK-204 当年是一审通过,但当时还没决策 11 + 当时 chunks 表是预想未实现)。

走二审(沿用 TASK-104 / 107 / 205 / 304 核心二审清单同款)。R1 + R2 两轮,文档预估 2000-2500 行。

### D2 — chunks 独立表 vs ALTER chat_message

**选 A:新建独立 `chunks` 表**(详 § 接口契约 3)。

**理由**:
- 语义:工程内容向量化(知识库)≠ 聊天消息向量化(对话历史);两者生命周期不同(chunks 与 project 同生命周期,messages 与 session 同生命周期)
- TASK-204 § 9.6 line 745 文档注释写"加 chat_message.embedding BLOB"是预想偏差(实地 cat schema.py 确认**代码未预留**)— erratum 修文档
- 跨工程隔离:chunks 表 `WHERE project_id=?` 强制过滤;若 ALTER chat_message,join 路径绕 + project_id 过滤要走 session 间接层(复杂度↑)
- Phase 2 扩展:多模型并存 / 模型升级 rebuild 时,独立表清晰,ALTER chat_message 会污染消息表

**为何不选 B(ALTER chat_message.embedding BLOB)**:语义错位 + 跨工程隔离复杂 + Phase 2 污染。

**为何不选 C(全独立 vector DB 文件,主 DB 不动)**:增加文件管理复杂度;TTL cleanup 需协调 2 DB;不符合 KISS。

### D3 — 向量存储格式:SQLite BLOB float32 binary

**选 A:SQLite BLOB 列存 little-endian float32 binary**(P1-2 v0.3 修订:统一 `np.dtype("<f4")`;`arr = np.asarray(vec, dtype=_FLOAT32_LE); arr.tobytes(order="C")` encode;`np.frombuffer(blob, dtype=_FLOAT32_LE)` decode)。

**理由**:
- 02 § 6 决策 2 KISS — 不引入 sqlite-vec / FAISS
- 5000 chunk × 512 维 × 4 byte ≈ 10MB 单工程,SQLite BLOB 完全够用
- float32 vs float64:精度足够(BAAI/bge-small-zh-v1.5 默认 float32 输出)+ 存储减半 + numpy 真 cosine 计算更快
- 解码用 `numpy.frombuffer` 零拷贝,性能 OK

**为何不选 B(JSON 数组存 list[float])**:存储膨胀 5-10x(`"0.123456789,"` 12 字节 vs 4 字节 binary)+ 解码慢(`json.loads`)+ 失类型信息(float64 默认,白浪费)。

**为何不选 C(sqlite-vec 扩展)**:Phase 2 候选;MCS 阶段单工程 < 5000 chunk,Python 内存遍历足够;sqlite-vec 引入额外 SO 依赖 + 跨平台编译复杂。

### D4 — 检索算法:Python 内存遍历**真余弦**(P1-1 修订)

**选 A:`SELECT ... FROM chunks WHERE project_id=?` 全部捞回 + numpy 真 cosine 计算 + Python 排序 + top_k 截断 + min_score 过滤**。

**v0.2 P1-1 修订**:v0.1 写"BAAI/bge-small-zh-v1.5 默认 normalize=True(L2),点积 = 余弦",**依赖 embedding_normalize 配置假设**;若用户配 `embedding_normalize=False`,点积≠余弦,query 结果错。v0.2 改为**始终计算真 cosine**,不依赖 normalize 假设:

```python
# 实施层骨架(由 Codex 落地):
dots = matrix @ query                            # (N,) 点积
denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)  # (N,)
scores = np.divide(dots, denom, out=np.zeros_like(dots), where=denom > 1e-12)  # 零向量保护
```

**理由**:
- 单工程 < 5000 chunk,512 维 → 矩阵 5000×512 × query 1×512 → numpy `np.dot(matrix, query)` + norm < 10ms(真 cosine 比纯点积慢 < 5%,可忽略)
- 不依赖 normalize 配置;即使下游误配也得对结果
- 零向量保护:`where=denom > 1e-12` 防 div-by-zero(MockEmbeddingProvider P1-4 修正后 base[0]=1.0 已防,但 query 端仍可能零向量;真实 BAAI 模型不会产零向量,但代码不假设)
- 实施简单:无需 SQL 算法 / 无需扩展;调试可观察
- 与 D3 BLOB 自然衔接:解码后直接 numpy 矩阵

**性能边界**(详 § 风险 R3):
- 5000 chunk 上限:numpy 矩阵约 10MB,内存 OK
- 超过 10000 chunk:需评估批量解码(分页 + 流式)或升级 sqlite-vec
- 实际 MCS 阶段单工程 chunk 估 500-2000(基于 TASK-303 预期),离上限远

**为何不选 B(SQL 端排序)**:SQLite 无原生向量算子;UDF 注册 Python 函数 + SQLite 跨进程调用反而慢。

**为何不选 C(sqlite-vec / FAISS / Annoy)**:Phase 2 候选;增加依赖 + 跨平台编译。

### D5 — TASK-302 范围严格度:只建 schema + 接口框架,不做 chunk 化

**选 A:本 Task 只建 storage / interface / lifespan 装配 / handler / 测试基础设施**;chunk 化逻辑(`source_text` 怎么从 SlxModel / MFile 切出来)由 **TASK-303** 接管;`VectorRetriever` 实现 + ChatService 集成由 **TASK-304** 接管。

**理由**:
- 范围划清晰:与 TASK-303 / 304 各自负责一层,审查面集中
- 减少本 Task 文档膨胀:chunk 化是设计密度极高的独立题(metadata 设计 + 切分粒度 + Simulink 层级映射),应独立 Task
- 沿用 TASK-301 D2 范围窄模式("加载器有了再装配,不先建好等用")— 但本 Task 是反向:本 Task 是基础设施,TASK-303/304 是消费者
- 测试时 `ChunkRecord(...)` 字面构造 mock chunk 走 add+query 路径,**不**触发真实 chunk 化

**为何不选 B(本 Task 顺带做 chunk 化)**:范围爆炸 / 二审压力 / TASK-303 退化为优化 Task。

### D6 — VectorStore ABC 接口(P0-1 + P0-2 + P1-5 + P1-6 修订)

详 § 接口契约 1。设计要点:

- **5 方法**:**4 业务方法 + 1 lifecycle 方法**(P1-5 统一表述):
  - `add_chunks(chunks: list[ChunkRecord]) -> None`:批量,非单条 — 减少 SQL roundtrip + 与 chunk 化天然批量对齐
  - `query(query_embedding: list[float], project_id: str, top_k=8, min_score=0.3) -> list[QueryHit]`:
    - **接收 embedding 而非 text — VectorStore 不持有 embedder,本 Task 不调 embedder**(P0-1 严格化);调用方(TASK-304 VectorRetriever)负责 `embedder.embed([query_text])[0]` 后传入
    - `project_id` 强制非 None,跨工程隔离硬约束
    - 默认 `top_k=8` 与 KeywordRetriever 一致(TASK-205 `DEFAULT_TOP_K=8`)
    - 默认 `min_score=0.3` 与 AppSettings `vector_min_score` 默认值一致(可被 TASK-304 覆盖)
    - 运行时非法参数 → `ValueError`(P1-7)
  - `delete_by_project_id(project_id: str) -> int`(P1-5 全文统一命名):返回删除条数,供**测试断言 + Phase 2 监控**(P0-4 修订:**不**由 cleanup worker 显式调用,走 FK CASCADE 路径)
  - `get_chunk_count(project_id: str) -> int`:供测试 + Phase 2 监控
- **lifecycle 方法**:
  - `aclose()`:no-op 沿用 SqliteChatStore 模式

- **`ChunkRecord` 字段**(P0-2 修订):覆盖 03 索引 § Week 3 验收中的 chunk metadata 字段;加 `model_name` 必填 + `created_at: datetime | None`(store 在 None 时填);`embedding_dim` 不进 dataclass(派生);**实际 chunk 化语义由 TASK-303 拍**,本 Task ABC 只锁结构 + 类型 + nullable
- **`line_range` 入出库规则**(P1-6):入库 `None → (NULL, NULL)`;出库两 NULL → `None`,两非 NULL → `tuple[int, int]`,只有一个 NULL → `VectorStoreError("invalid_line_range")`
- **`source_type` 不锁 Literal**(P2-2):本 Task 透传 string,枚举由 TASK-303 定型

### D7 — lifespan 装配失败语义:不掩盖,前置翻译异常,**from None 断异常链**(P0-3 修订)

详 § 接口契约 8。设计要点:

- **失败不掩盖**:类比 TASK-204 `_bootstrap_db` 失败让 uvicorn 退出 — 基础设施 / schema 错应让用户看到
- **前置 try/except 翻译**:sentence-transformers 库自身可能抛 `OSError`(网络下载失败)/ `RuntimeError`(GPU 设备不支持)/ `FileNotFoundError`(本地缓存损坏)等异质异常 — 统一翻译为 `EmbeddingModelLoadError`
- **logger.error metadata-only**(决策 11 决策 2):只落 `model_name` / `device` / `type(exc).__name__`,不落 traceback / str(exc) / file path 内容
- **`raise EmbeddingModelLoadError("model_load_failed") from None`**(P0-3 修订):**`from exc` 保留 cause 链会导致 ASGI/uvicorn/TestClient 打印 chained traceback,原异常 `repr` / `path` / `str(exc)` 仍出现在控制台或日志聚合**,违反 01 § 9 / 02 § 12 隐私硬约束;`from None` 完全断链,只保留架构师在 logger 显式落的 metadata 元数据。调试性的代价由开发期 print 临时补救,生产环境绝不

### D8 — 异常树 3 类新增(P1-4 handler 语义修订)

详 § 接口契约 4。设计要点:

- `EmbeddingError(MxaError)` + `EmbeddingModelLoadError(EmbeddingError)` 二层 — 与 `LLMError → LLMAuthError` / `ParseError → SlxParseError / MParseError` 同形态
- `VectorStoreError(StoreError)` 平级 — 不引入第三个并列层,chunks 表是 storage 一部分,语义上属 StoreError 子树
- **`EmbeddingModelLoadError` handler 语义降级**(P1-4 修订):handler 仍注册(503,machine_code `"embedding_model_load"`),但**本 Task lifespan 失败时 app 未启动,不走 HTTP 路径,handler 不被触发**;handler 为未来 lazy reload / runtime path 保留(例如:运行时 embedder 重载 / 健康检查时 embedder 状态校验失败)。v0.1 写"503 类比 LLMAuthError 节奏(服务暂不可用)"隐含的"lifespan 失败 → HTTP 503"语义被纠正
- `VectorStoreError` 走父类 `StoreError` handler(500)— 减少 ERROR_MAP 表项膨胀

### D9 — AppSettings 2 字段新增,1 段新增(P1-7 边界约束修订)

详 § 接口契约 6。

新加段:
```python
# Vector(TASK-302 新增)
vector_top_k: int = Field(default=8, ge=1, le=50)              # P1-7
vector_min_score: float = Field(default=0.3, ge=-1.0, le=1.0)  # P1-7
```

**理由**:
- 与 `# Embedding` 段(TASK-301 加的模型层字段)语义区分:Embedding 管模型,Vector 管检索行为
- `top_k=8` 默认值与 TASK-205 KeywordRetriever 一致(便于 TASK-304 切换无 surprise)
- `min_score=0.3`:经验值;真 cosine ∈ [-1.0, 1.0],0.3 是粗糙阈值;具体调优由 TASK-306 评测脚本基于真实数据迭代

**边界校验**(P1-7):
- 配置层:pydantic `Field(ge=..., le=...)` 校验启动期 .env 非法值,uvicorn 启动失败 fail-fast
- 运行时:`query(top_k, min_score)` 收到非法值(TASK-304 调用时传入用户输入未校验)抛 `ValueError`,由 dependency / route 层接管,非 `VectorStoreError`(VectorStoreError 是存储层异常,参数校验是接口层异常)

**不加**:
- `vector_batch_size`(Phase 2,批量优化)
- `vector_max_seq_length`(Phase 2,长 chunk 截断)
- `vector_db_path`(沿用 `db_path` 单库)

### D10 — numpy 显式入 requirements.txt

**选 A:`requirements.txt` 显式加 `numpy>=1.26.0,<2.0`**。

**理由**:
- sentence-transformers 3.3.0 传递依赖 numpy,但**反例 12 同源教训**:不要凭传递依赖假设可用 — 升级 sentence-transformers 时 numpy 可能不兼容
- 本 Task SqliteVectorStore.query 直接 `import numpy as np` 做点积 — **代码层显式依赖**,不应只靠传递引用
- `>=1.26.0,<2.0`:Python 3.11 + 当前生态稳定区间(numpy 2.0 ABI 变更,锁<2.0)
- numpy 自带 type stubs,**不需要** mypy override(待 Stage 0 实测确认)

**为何不选 B(只靠传递依赖)**:反例 12 已踩过(TASK-106 凭 04 § 6 模板假设 loguru 已加,实际仓库无)。

### D11 — 测试策略:unit mock + integration RUN_EMBEDDING_INTEGRATION=1 skipif

**选 A:unit 全部用 `MockEmbeddingProvider`(TASK-301 conftest 已建,本 Task 复用)**;integration 测试用 `@pytest.mark.skipif(os.environ.get("RUN_EMBEDDING_INTEGRATION") != "1", reason="...")` env opt-in。

**理由**:
- 沿用 TASK-301 R1 P0-1 修正后模式:不动 pyproject.toml `addopts`,用 env skipif 显式 opt-in(避免污染其他 Task 测试)
- CI 默认 `pytest -v --tb=short`(实地 cat .github/workflows/ci.yml 确认)不带 `RUN_EMBEDDING_INTEGRATION=1`,所以 CI **不**触发真实 100MB 模型下载
- 本地全跑用 `RUN_EMBEDDING_INTEGRATION=1 pytest -v`,真实端到端验证
- `MockEmbeddingProvider.embed` 返回固定非零向量(TASK-301 P1-4 修正后,base[0]=1.0 防 div-by-zero)

**测试维度**(粗略,Codex 实施时按维度展开 case;**v0.2 / v0.3 P0/P1 新增维度标 ★**):

Unit(mock embedder):
- SqliteVectorStore add + query round-trip
- add 校验 project_id 存在 → **`ProjectNotFoundError`**(显式预查,P1-6 v0.3 严格化,**禁 IntegrityError 兜底**);chunk_id 重复 → `ValueError("chunk_id already exists")`;sqlite OperationalError 兜底 → `VectorStoreError("sqlite_operation_failed")`
- query 强制 project_id 过滤(跨工程隔离)
- query top_k 截断 / min_score 过滤
- query 非法参数(top_k=0 / top_k=51 / min_score=-1.1 / min_score=1.1)→ `ValueError` ★ P1-7
- delete_by_project_id 返回正确条数 + 显式调用路径
- **FK CASCADE 路径** ★ P0-4:create project → add chunks → `project_store.delete(project_id)` → `vector_store.get_chunk_count(project_id) == 0`
- get_chunk_count 准确
- BLOB encode/decode round-trip(float32 精度)
- BLOB codec 校验 ★ P1-2:`len(blob) % 4 != 0` → VectorStoreError;`len(blob) // 4 != embedding_dim` → VectorStoreError;`len(query_embedding) != embedding_dim` → VectorStoreError;**`_FLOAT32_LE = np.dtype("<f4")` 是模块级唯一来源,禁 native `np.float32`** ★ P1-2 v0.3
- ★ P1-1 **真 cosine**:embedding 不 normalize 时 query 仍返回正确 cosine 排序;**零向量 query** → score=0(不 div-by-zero)
- ★ P0-2 ChunkRecord 字段:`created_at=None` 时 store 填 `datetime.utcnow()`;`embedding_dim` 由 `len(embedding)` 派生入 DDL
- ★ P1-6 `line_range` 入出库规则:None ↔ (NULL, NULL);两非 NULL ↔ tuple;只有一个 NULL → `VectorStoreError("invalid_line_range")`
- ★ **P1-3 v0.3 `created_at` 出入库规则**:`isoformat()` naive UTC 入库;`fromisoformat(row[...])` 出库;**出库类型必须是 `datetime` 不是 str**;解析失败 → `VectorStoreError("invalid_created_at")`
- ★ **P1-4 v0.3 query 空数据语义**:project 存在但 chunks=0 → `[]`;**project_id 不存在 → 也 `[]`**(检索层不抛 ProjectNotFoundError,由 TASK-304 做 E 类降级);**`add_chunks` 才严格校验 project_id 存在**
- ★ **P1-5 v0.3 混维 / 混模型规则**:
  - 单批次混维(`[dim=512, dim=384]`)→ `ValueError("mixed_embedding_dim")`
  - 新批次维度与 project 已有 chunks 不一致 → `VectorStoreError("embedding_dim_mismatch")`
  - **同维不同 model_name 不阻断 `add_chunks`**(model_name 只存不校验)
- ★ P1-3 **schema_version v1→v2 迁移**:已有 v=1 库 + project_status_record/chat_session/chat_message 数据 → 启动后 v=2 + chunks 表存在 + **已有数据保留**

Integration(`RUN_EMBEDDING_INTEGRATION=1`):
- 真 SentenceTransformer + 真 SQLite 端到端 add + query
- embedding 维度 == 512(契约,模型升级时此测试提醒)

API 层(lifespan 集成):
- TestClient 启动 + `app.state.embedder` 是 `SentenceTransformerEmbedder` 实例(mock SentenceTransformer 构造函数)
- lifespan 启动失败路径:mock SentenceTransformer 抛 OSError → 翻译为 EmbeddingModelLoadError → uvicorn 启动失败
- ★ P0-3 **失败路径不漏敏感 message**:启动失败的 logger 输出 / 异常 message / repr 中**不含**原始 OSError("...sensitive path...") message;不用 `logger.exception`,不输出 `str(exc)`
- ★ P1-8 **source_text 日志隔离**:任何路径(add_chunks / query / 异常分支)的 logger 输出**不含** chunk.source_text 字面

### D12 — schema v1→v2 最小迁移(P1-3 新增)

**选 A:`schema.py` 加 `_migrate_v1_to_v2(conn)` 函数;`init_schema` 在 `version < CURRENT_SCHEMA_VERSION` 时调对应迁移函数而非抛 `schema_migration_required`**。

**v0.1 → v0.2 修订背景**:v0.1 § R4 选"不做自动迁移,用户删 `data/mxa.db` 重建,MCS 阶段用户量小可接受";GPT R1 P1-3 抓住"会丢已有 chat/project 历史"。本 Task 是 schema_version 第一次真实使用,TASK-204 已把它作为后续扩展点,自动迁移代价不大(只新增表 + UPDATE version 行)。

**实施伪代码**(架构层,详细骨架由 Codex 落地):

```python
# adapters/storage/schema.py
async def _migrate_v1_to_v2(conn: aiosqlite.Connection) -> None:
    """v1 → v2:只新增 chunks 表 + bump version,不动已有数据。"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            ... -- 详 § 接口契约 3
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
    """)
    await conn.execute(
        "UPDATE schema_version SET version=2, applied_at=? WHERE id=1",
        (datetime.utcnow().isoformat(),),
    )

async def init_schema(conn: aiosqlite.Connection) -> None:
    # ... 沿用 TASK-204 现有逻辑直到 SELECT version
    version = int(row["version"])
    if version > CURRENT_SCHEMA_VERSION:
        raise StoreError("unsupported_schema_version")
    if version < CURRENT_SCHEMA_VERSION:
        # P1-3 修订:不再抛 schema_migration_required,自动迁移
        if version == 1:
            await _migrate_v1_to_v2(conn)
        else:
            raise StoreError(f"no_migration_path_from_v{version}")
    await conn.commit()
```

**理由**:
- 不引 alembic,不扩范围:只是把"新增表"做成可升级
- 沿用 TASK-204 schema_version 表 + `applied_at` 字段记录迁移时间
- 用户视角:升级版本 → 启动一次完成迁移 → 已有 chat/project 数据保留 + chunks 表可用
- 未来 v2→v3 / v3→v4 沿同模式追加 `_migrate_vN_to_vM`

**修改影响清单**(更新 § 输出):
- `schema.py` 改动:bump CURRENT_SCHEMA_VERSION + 追加 chunks DDL + **加 `_migrate_v1_to_v2` 函数 + 改 `init_schema` 逻辑**
- v0.1 § 不动文件清单"`init_schema` 自身不动"作废
- 验收新加 P1-3 测试维度:v1 库 → 启动后 v2 + 数据保留

**为何不选 B(沿用 v0.1 删库方案)**:丢已有用户数据,即使 MCS 阶段也不该。

**为何不选 C(引 alembic)**:扩范围(新依赖 + 迁移文件管理 + Codex 派活复杂度),MCS 阶段过重;v=2 单次升级用 30 行自定义函数足够。

---

## 风险与注意点

### R1 — lifespan 启动时间增加

首次启动需下载 ~100MB 模型(BAAI/bge-small-zh-v1.5)→ uvicorn 启动可能 +30-60s(网络慢时更长);后续启动用本地缓存 → +2-5s。

**缓解**:
- README 明示首次启动等待 + 离线开发 `HF_HUB_OFFLINE=1`
- 生产部署应预下载模型(Docker layer 缓存 / volume mount)
- 启动失败 → `EmbeddingModelLoadError` 抛出 → uvicorn / TestClient 启动失败 → 用户视角 = 服务暂不可用(P1-1 v0.3 修订:**本 Task 不承诺 HTTP 503 body**,因为 lifespan 失败时 app 未启动,不走 HTTP 路径;503 handler 仅为未来 runtime / lazy reload 路径保留,详 § 接口契约 5 + D8)

### R2 — chunk 文本入持久层的隐私边界(02 § 12)(P0-4 + P1-8 修订)

**`source_text` 定位**(P1-8 修订):`chunks.source_text` 是 RAG 可用性的**最小必要工程派生文本**,是 01 § 9 / 02 § 12 "不记录用户上传的工程内容"硬约束的**显式例外**;**不应被描述为"非工程内容"或"严格说不算原始内容"** — 它确实可能包含函数名 / block 名 / 参数值,即原始工程敏感内容。

**约束**(本 Task 拍 + v0.2 P1-8 强化):

1. **project_id 隔离**:chunks 表 FK + WHERE project_id=? 强制按工程隔离查询,跨工程检索不可达
2. **TTL/CASCADE 删除**(P0-4 修订收敛):**以 FK CASCADE 为主路径** — `ProjectStore.delete(project_id)` 删除 `project_status_record` 时,chunks 通过 `ON DELETE CASCADE` 自动删除;TASK-302 **不**改 cleanup worker,**不**让 cleanup worker 显式调 `vector_store.delete_by_project_id`(避免双删 + 减少修改文件;cleanup worker 现已调 `store.delete(project_id)`,通过 store 删除自动触发 chunks CASCADE)
3. **日志层禁出**(P1-8):任何路径(add_chunks / query / 异常分支)的 logger 调用**不含** `chunk.source_text` 字面;仅落 metadata(chunk_id / project_id / source_type / type(exc).__name__)
4. **错误 message 禁出**:`VectorStoreError` / `EmbeddingModelLoadError` 的 message 仅含机器码("blob_length_mismatch" / "model_load_failed" 等),**不含** source_text / model_name / path
5. **exception repr 禁出**:`raise ... from None`(P0-3),不保留原异常 cause 链;开发期 print 临时补救

**未来 Phase 2 强化**:
- 加 `chunks.source_text_encrypted` 列(at-rest 加密)
- 加 `source_text` 输出 token 量限制(防 logger 误打)

**本 Task 验收(v0.2 新增,P1-8)**:
- `grep -rn 'source_text' adapters/storage/ --include='*.py'` 仅出现在 schema 字段 + add_chunks INSERT 参数 + query SELECT 解码,**不**在 logger.* 调用中
- `grep -rn 'source_text' api/ features/` 空(本 Task 不动 api/features,只确认未来 TASK-303/304 不引入)
- FK CASCADE 路径测试(P0-4):`create project → add chunks → project_store.delete(project_id) → vector_store.get_chunk_count(project_id) == 0`

### R3 — 余弦遍历内存上限

5000 chunk × 512 维 × 4 byte ≈ 10MB(per query);超过 10000 chunk 应考虑流式 / sqlite-vec 升级。

**缓解**:
- 本 Task 不加硬上限(否则需配置项),但日志层:`logger.info("VectorStore.query: project_id={} chunk_count={} top_k={}")` 提供 Phase 2 监控数据(注意:**不**记录 source_text)
- TASK-306 评测脚本基于真实工程 chunk 数确认是否触达边界
- **P2-1 hint**(详 § 给 Codex 提示):若 source_text 内存暴露面后续成为问题,可改两阶段读取(先取 chunk_id + embedding 算 top_k,再 SELECT 完整 metadata/source_text)

### R4 — schema_version 升级路径(P1-3 修订)

现有用户 DB 是 v=1;本 Task 升 v=2。

**v0.2 选择**(P1-3 修订):**实现 v1→v2 最小迁移**(详 D12)。
- `schema.py` 加 `_migrate_v1_to_v2(conn)` 函数(只 CREATE TABLE chunks + UPDATE schema_version)
- `init_schema` 在 `version < CURRENT_SCHEMA_VERSION` 时调对应迁移函数,不再抛 `schema_migration_required`
- 用户视角:升级版本 → 启动一次完成迁移 → 已有 chat/project 数据保留 + chunks 表可用
- 不引 alembic;v=2 单次升级 30 行自定义函数足够

**v0.1 → v0.2 变更**:v0.1 写"不做自动迁移,用户删 `data/mxa.db` 重建,MCS 阶段用户量小可接受";GPT R1 P1-3 抓住"会丢已有 chat/project 历史"。v0.2 改实现最小迁移。

**未来 Phase 2**:v2→v3 / v3→v4 沿同模式追加 `_migrate_vN_to_vM`。

### R5 — model_name 字段语义

`chunks.model_name` 列存生成 embedding 的模型名(`BAAI/bge-small-zh-v1.5`)。Phase 2 若升级模型 → query 时 `embedder.dimension()` 与 chunks 表存的不一致 → 需 rebuild。

**本 Task 不做自动校验**:add_chunks 时 model_name 由调用方(TASK-303)传入,query 时不强制校验同 model_name(同维不同 model_name 不阻断 add_chunks,见 P1-5);**严格的维度校验**由 P1-5 v0.3 规则覆盖(`embedding_dim_mismatch`)。Phase 2 加 `if chunks.model_name != embedder.model_name: rebuild` 路径。

### R8 — `QueryHit.chunk: ChunkRecord` 长期可能拆 ChunkPayload(P2-1 v0.3 Phase 2 观察点)

当前 `QueryHit.chunk: ChunkRecord` 会把 `embedding` 也带回(MCS 单工程规模可接受)。TASK-304 ChatService 主要消费 `source_text` + SourceRef metadata,**不需要** embedding。

**Phase 2 候选**:拆 `ChunkPayload`(不带 embedding 字段)作为 query 返回类型;`add_chunks` 仍用 `ChunkRecord`,`query` 返回 `QueryHit(chunk: ChunkPayload, score: float)`。

**本 Task 不改接口**(避免扩大变更范围,留作 Phase 2 观察点)。

### R9 — TASK-303 接力点:`source_text` 最大长度策略(P2-2 v0.3 新增)

本 Task 不负责 chunk 化,但 chunks.source_text 是 RAG 可用性 + 隐私边界双重命题。

**TASK-303 必须定义 `source_text` 最大长度 / 截断策略**,避免:
- 超长工程片段进入 SQLite(单 chunk 几十 KB → 检索内存 + 数据库膨胀)
- 超长片段进入 LLM prompt(超 token budget + 隐私暴露面增大)

具体策略由 TASK-303 拍(建议字符或 token 上限 + 智能截断点 + truncation marker);本 Task 不预设上限以免约束 TASK-303 设计空间;**但 TASK-303 v0.x 接力点强制点名**。

### R6 — Windows Git Bash 路径兼容

`db_path` 含中文路径(用户家目录)→ aiosqlite 已沿用 TASK-204 兼容路径;本 Task 不引入新路径处理。

### R7 — numpy ABI 兼容

`numpy>=1.26.0,<2.0` 锁定:numpy 2.0 ABI 变更可能影响 sentence-transformers ABI 兼容;Phase 2 升级时需重测。

---

## 验收清单

### 11.1 测试要求

- [ ] Unit 测试覆盖 § D11 列出的全部维度(SqliteVectorStore + ABC contract + schema_version + codec)
- [ ] Integration 测试(`RUN_EMBEDDING_INTEGRATION=1`)端到端 add+query 通过
- [ ] lifespan 集成测试:成功路径 + 失败路径(mock SentenceTransformer 抛异常 → EmbeddingModelLoadError)
- [ ] `make check` 全管道绿(lint + type-check + test + hygiene,反例 26 KPI)

### 11.2 验收 N 条(按顺序勾选,Codex 实施时跑)

> 反例 28 KPI:架构师本地实测每条命令的输出再写预期;不凭印象。本 v0.1 给出**验收维度**,**具体命令字面 + 期望输出由 v0.2 在 R1 通过后实地核查写**(粗略稿不内联 grep 字面)。

验收维度(**v0.2 P0/P1 新增维度标 ★**):

1. 文件存在 + 行数符合 § 输出
2. `make check` 全管道绿(反例 26 KPI)
3. `pytest -v` 全绿(不带 `RUN_EMBEDDING_INTEGRATION`,unit 路径)
4. `RUN_EMBEDDING_INTEGRATION=1 pytest -v -m integration` 全绿(本地实地)
5. `grep -rn 'logger\.exception' core/ adapters/ features/ api/ app/` 空(决策 11 决策 2)
6. `grep -rn 'asyncio.to_thread' api/main.py` 命中 lifespan 装配点(决策 11 决策 1 首次实战)
7. `grep -rn 'source_text' adapters/storage/` 不出现在 logger.* 调用(R2 隐私边界,P1-8 强化)
8. `EmbeddingError` / `EmbeddingModelLoadError` / `VectorStoreError` 出现在 `core/domain/exceptions.py`
9. `error_handler.py` 中 `EmbeddingModelLoadError` 在 `error_handlers` tuple(handler 为未来 lazy reload 保留,本 Task lifespan 失败不走 HTTP)★ P1-4
10. schema.py `CURRENT_SCHEMA_VERSION == 2` + chunks 表 DDL 存在 + **`_migrate_v1_to_v2` 函数存在** ★ P1-3 + D12
11. `app/config.py` `# Vector` 段 + 2 字段(`vector_top_k` / `vector_min_score`)+ **`Field(ge=..., le=...)` 边界校验** ★ P1-7
12. `.env.example` 对应 2 字段
13. `requirements.txt` 含 `numpy>=1.26.0,<2.0`
14. 03 索引 `TASK-301` 行 ✅ + Week 3 1/7→2/7 + 19/32→20/32(若 chore 入 PR)
15. TASK-204 § 9.6 line 745 已 erratum
16. **`grep -rn 'from exc' api/main.py` 不在 EmbeddingModelLoadError 抛出点**(P0-3,验证 `from None`)★ P0-3
17. **FK CASCADE 删除路径测试通过**:create project → add chunks → project_store.delete → get_chunk_count == 0 ★ P0-4
18. **v1→v2 迁移测试通过**:已有 v=1 库 + project/chat 数据 → 启动后 v=2 + chunks 表 + 数据保留 ★ P1-3
19. **真 cosine 测试通过**(P1-1):normalize=False 配置下 query 仍按真 cosine 排序 + 零向量 query 不 div-by-zero ★ P1-1
20. **BLOB codec 校验测试通过**:len%4≠0 / dim mismatch / query dim mismatch → VectorStoreError ★ P1-2
21. **line_range nullable 规则测试通过**:None ↔ (NULL, NULL);只有一个 NULL → VectorStoreError ★ P1-6
22. **运行时参数边界测试通过**:query(top_k=0/51, min_score=-1.1/1.1) → ValueError ★ P1-7
23. **失败路径敏感 message 隔离测试通过**:OSError("/sensitive/path") 翻译后,日志/异常 message/repr 中**不含**原始 path ★ P0-3 + P1-8
24. **`created_at` 出入库测试通过**(★ P1-3 v0.3):`created_at=None` 时 store 填 `datetime.utcnow()`;非 None 保留原值;SQLite TEXT 用 `isoformat()` naive UTC;query 出库为 `datetime` 类型(不是 str);非法 created_at 文本 → `VectorStoreError("invalid_created_at")`
25. **`query` 空数据语义测试通过**(★ P1-4 v0.3):project 存在但 chunks=0 → `[]`;**project_id 不存在 → 也 `[]`**(检索层不抛 ProjectNotFoundError,由 TASK-304 做 E 类降级);此路径**不**做 query_dim 校验;`add_chunks` 仍严格校验 project_id 存在(对比)
26. **混维 / 混模型规则测试通过**(★ P1-5 v0.3):单批次 dim 混杂(`[dim=512, dim=384]`)→ `ValueError("mixed_embedding_dim")`;新批次 dim 与 project 已有 chunks 不一致 → `VectorStoreError("embedding_dim_mismatch")`;**同维不同 model_name 不阻断 `add_chunks`**(model_name 只存不校验)
27. **`add_chunks` 异常语义测试通过**(★ P1-6 v0.3,**禁"或"漂移**):任一 `chunk.project_id` 不存在 → `ProjectNotFoundError`(显式预查,**禁 IntegrityError 兜底**);`chunk_id` 重复 → `ValueError("chunk_id already exists")`;sqlite `OperationalError` → `VectorStoreError("sqlite_operation_failed")`
28. **R3 删除链路一致性核查通过**(★ R3 18a):active spec 中只允许 FK CASCADE 主路径;`delete_by_project_id` 仅供测试断言 + Phase 2 显式清理 / 监控;cleanup worker **不**显式调用 `vector_store.delete_by_project_id`(命令:`grep -nE 'cleanup worker|delete_by_project_id|FK CASCADE' docs/tasks/task-302-*.md`,active spec 段无双语义残留)
29. **R3 lifespan 503 表述核查通过**(★ R3 18b):active spec 不暗示 lifespan 失败返回 HTTP body;503 handler 仅为未来 runtime / lazy reload 路径保留(命令:`grep -nE '503 返回|HTTP 503|lifespan' docs/tasks/task-302-*.md`,active spec 段无"启动失败 → HTTP 503"语义)
30. **R3 BLOB endian 核查通过**(★ R3 18c):active codec spec 只允许 `_FLOAT32_LE = np.dtype("<f4")`;`np.float32` 只可出现在反面教材 / 禁止项表述中(命令:`grep -nE 'np\.float32|np\.dtype' docs/tasks/task-302-*.md`,active spec 段无 native endian 用法)

### 11.3 PR 元信息

- 分支:`task/TASK-302-sqlite-vector-store`
- 标题:`TASK-302: SQLite 向量存储 + 检索基础设施(Week 3 第 2/7)`
- 关联 issue / 文档 PR:同步出 docs PR(`task/TASK-302-design`)

---

## 给 Codex 的提示

### 类比 anchor(实地 cat 已确认 `85b86d3`)

- 存储层:`adapters/storage/sqlite_chat_store.py`(几乎 1:1 抄构造 / aclose / async with open_connection / 异常翻译模式)
- schema 升级:`adapters/storage/schema.py` 加表逻辑 + **改 `init_schema` 加 v1→v2 迁移**(P1-3 + D12);**v0.1 写"init_schema 不动"作废**
- lifespan 装配:`api/main.py` 现有 `AsyncExitStack` 块,在 `chat_store` 之后 / `chat_service` 之前装 embedder + vector_store
- DI:`api/dependencies.py` `get_chat_store` 是最干净 anchor
- handler:`api/middleware/error_handler.py` `error_handlers` tuple 末追加 1 项

### 关键约束

- 决策 11 决策 1:lifespan 内 `await asyncio.to_thread(SentenceTransformerEmbedder, ...)` —— 本 Task 首次实战,任何 async def 内同步重活同款
- 决策 11 决策 2:`logger.error("... exception={}", type(exc).__name__)`,禁 `logger.exception` / `str(exc)`
- **`raise EmbeddingModelLoadError("model_load_failed") from None`** ★ P0-3:不用 `from exc` 保留异常链(避免隐私泄漏)
- 反例 26 KPI:验收必须 `make check` 全管道,禁拆条
- 反例 27 KPI:任何 pytest / mypy / ruff 行为陈述前 cat pyproject.toml(已实地 cat,markers 已注册)
- 反例 28 KPI:Stage 0 命令"预期输出"已由架构师本地实测,Codex 跑出不符停手抛冲突
- **反例 29 KPI** ★ v0.2 新增:任何接口签名 / 字段集 / 数据流向 / 命名,在文档多处描述时,实施前 `grep -nE '<接口名|字段名>' docs/tasks/task-302-*.md` 跨段交叉验证

### 实施建议(P1-2 / P2-1 / P2-2 / P2-4)

- **P1-2 BLOB codec 合约**(v0.3 修订:**严格 little-endian,禁 native endian**):`_vector_codec.py` 必须包含:
  - 模块级常量 `_FLOAT32_LE = np.dtype("<f4")` — 单一来源,所有 encode/decode 引用此常量
  - `encode_vector(vec: list[float]) -> bytes`:`np.asarray(vec, dtype=_FLOAT32_LE).tobytes(order="C")`
  - `decode_vector(blob: bytes, expected_dim: int) -> list[float]`:`np.frombuffer(blob, dtype=_FLOAT32_LE)`;校验 `len(blob) % 4 == 0` + `len(blob) // 4 == expected_dim` 双重,否则 `raise VectorStoreError("blob_length_mismatch")`
  - **严禁** `np.float32`(native endian,跨平台不一致);**严禁** `np.asarray(..., dtype=np.float32)`
- **P2-1 两阶段读取 hint**:本 Task `query` 实现单阶段(SELECT 全字段)对 MCS 单工程规模够;但若 Codex 实施时发现内存压力,可改两阶段:阶段 1 `SELECT chunk_id, embedding, embedding_dim` 算 top_k → 阶段 2 按 top_k chunk_id `SELECT * FROM chunks WHERE chunk_id IN (...)` 取完整 metadata。减少 source_text 在内存暴露面;v0.3 不锁接口层
- **P2-2 source_type 透传**:`ChunkRecord.source_type: str`,本 Task 不锁 Literal;枚举由 TASK-303 定型,届时如需收紧再改
- **P2-4 MockEmbeddingProvider 复用**:建议放 `tests/helpers/embedding.py`(或 `tests/fakes/embedding.py`),而非跨 conftest import;TASK-301 已在 `tests/adapters/embedding/conftest.py` 建,Codex 可在本 Task 实施时重构为 helpers 模块(独立小 chore,不阻塞主路径)

### Stage 0 实地核查清单(架构师本地实测后写,反例 28 KPI)

> 本 v0.2 给出**核查维度**,**具体命令 + 期望输出由 R2 通过后实地核查写**(反例 28 KPI:不凭印象先写命令,等架构师本地实测)。

核查维度:
1. `core/interfaces/embedder.py` 签名(TASK-301 已落,本 Task 消费,不动)
2. `adapters/embedding/sentence_transformer.py` 模块级常量 + `__init__` 签名(类比 anchor)
3. `adapters/storage/schema.py` `CURRENT_SCHEMA_VERSION == 1` + `_DDL` 当前 4 表 + `init_schema` 当前抛 `schema_migration_required` 逻辑(本 Task **改** init_schema,P1-3)
4. `adapters/storage/_connection.py` open_connection 签名 + PRAGMA(本 Task 沿用不动)
5. `adapters/storage/sqlite_chat_store.py` 构造 / aclose / 方法模式(类比 anchor)
6. `core/domain/exceptions.py` 当前 23 类 + 不含 `EmbeddingError` / `VectorStoreError`(本 Task 加)
7. `api/main.py` lifespan AsyncExitStack 装配点
8. `api/dependencies.py` `get_chat_store` 模式
9. `api/middleware/error_handler.py` `error_handlers` tuple 末尾 + `_make_handler` factory
10. `app/config.py` 段顺序 + `# Embedding` 段位置(本 Task `# Vector` 段紧随其后或单独段)+ pydantic Field 用法
11. `pyproject.toml` `[tool.pytest.ini_options]` markers 含 `integration` + `slow`(TASK-301 已加)
12. `scripts/check_repo_hygiene.{sh,py}` 6 条规则(反例 26 KPI)
13. `.github/workflows/ci.yml` 5 step + Makefile `check` target 对齐(反例 26 KPI)
14. `requirements.txt` 当前不含 `numpy`(本 Task 显式加)+ `sentence-transformers==3.3.0`(TASK-301 加)
15. 03 索引 7 行 anchor(P0-2 同款 7 处 — TASK-301 ✅ + Week 3 进度 + 总计 + 下一步 + 日期)
16. TASK-204 § 9.6 line 745 anchor(erratum)
17. **本任 v0.2 自身跨段一致性自审** ★ 反例 29 KPI:`grep -nE 'VectorStore\.query|delete_by_project|ChunkRecord|EmbeddingModelLoadError|from exc|from None' docs/tasks/task-302-*.md` 验证多处描述一致
18. **★ v0.3-v0.4 R3 窄审 5 项核查清单**(GPT R2 P2-3 + R3 给出的方法论,反例 30 KPI 实操版):

   **R3 grep 范围说明(P2-1 v0.4)**:R3 grep 仅审 § 范围 / § 接口契约 / § 决策 / § 风险 / § 验收 / § 给 Codex 提示 等 **active spec 段**;命中 § R1 反馈台账 / § R2 反馈台账 / § R3 反馈台账 / 反例候选记录 等 **历史段** 的"旧问题引用",**不按 active spec 失败处理**;旧短语作为反面教材记录是必要文档资产。

   - **18a 删除链路全文一致性**:`grep -nE 'cleanup worker|delete_by_project_id|FK CASCADE' docs/tasks/task-302-*.md` 验证 active spec 只剩一种语义(主路径走 FK CASCADE,delete_by_project_id 仅供测试 + Phase 2 显式清理 / 监控)
   - **18b lifespan 503 表述残留**:`grep -nE '503 返回|HTTP 503|lifespan.*HTTP' docs/tasks/task-302-*.md` 验证 active spec 不再暗示 lifespan 失败返回 HTTP body(只允许"handler 为未来 runtime / lazy reload 保留"语境)
   - **18c BLOB codec endian**:`grep -nE 'np\.float32|np\.dtype' docs/tasks/task-302-*.md` 验证 active spec 只允许 `np.dtype("<f4")` / `_FLOAT32_LE`,**不允许** native `np.float32`(除反面教材引用)
   - **18d 边界规则四补丁齐备**:`created_at` 出入库 / `query` 空数据语义 / 混维 / `add_chunks` 异常语义 — 在 § 接口契约 1 ABC 设计要点 + § D11 测试维度 + **§ 11.2 验收 24-27 三处** 均有(v0.4 强化:不仅 ABC + D11,验收清单必须同步)
   - **18e 验收 vs D11 一致**(v0.4 GPT R3 精确版):**§ 11.2 验收 24-27 覆盖 v0.3 四补丁;28-30 覆盖 R3 18abc 三个全文一致性 grep 守门;与 § D11 测试维度无项数 / 语义漂移**
   - **18f(v0.4 新增,反例 30 入仓 KPI 实操)**:第二十任 KPI — **架构师自审 5 项核查清单时严禁因 "self-confirmation bias" 跳过任何机械检查项**;`§ 11.2 项数 = D11 项数?`这种机械数数不存在判断偏见,**必须自审**

---

## 关联文档

- 关联宪法版本:v2.1(冻结,不修改)
- 关联决策:`docs/decisions/20260601-04` / `20260601-05` / `20260601-06` / `20260601-07` / `20260602-08` / `20260603-09` / **`20260604-11`(本 Task 决策 1 首次实战)**
- 类比 Task:TASK-204(SQLite anchor)/ TASK-301(EmbeddingProvider anchor)/ TASK-205(Retriever ABC,本 Task 不动,TASK-304 接力)
- 前置 commit:main HEAD `85b86d3`(TASK-301 merge)
- **关联反例**:
  - 反例 29(自审一致性缺失 — grep 接口名/字段名跨段一致性,本 Task v0.1 → R1 触发,v0.2 D8 治理 chore 入仓决策 09 + 第十九任 KPI)
  - **反例 30(立即入仓,v0.4)** — 自审 grep 关键词枚举不全 + 同一变更跨段同步漏 + 误把"机械数数"等同于"self-confirmation bias",本 Task v0.2 → R2 + v0.3 → R3 双重触发,v0.4 D8 治理 chore 入仓决策 09 + **第二十任 KPI**(详 § R3 反馈台账末段)

---

**版本**:v0.4(R3 反馈 1 P0 + 1 P2 全采纳 / **反例 30 立即入仓 + 第二十任 KPI** / § 11.2 验收 24-30 补全 / R3 grep active spec 范围说明 / 待窄 R4)
**日期**:2026-06-06
**作者**:Claude(架构师,第十七任)
**审批历史**:v0.1 R1 conditional pass(4 P0 + 8 P1 + 4 P2)→ v0.2 R2 conditional pass(1 P0 + 7 P1 + 3 P2)→ v0.3 R3 conditional pass(1 P0 + 1 P2)→ v0.4 → **待窄 R4**(只审 § 11.2 是否补到 30 条 + R3 grep active spec 范围说明,不重审 D1-D12,不重审 R3 18a-18d)
**审批级别**:**GPT 二审 R1 + R2 + 窄 R3 + 窄 R4**(详 D1 + R2 P2-3 + R3 最终判定)
