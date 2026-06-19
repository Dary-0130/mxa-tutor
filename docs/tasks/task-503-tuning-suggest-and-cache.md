# TASK-503：TuningSuggestion + 持久化 PaperBundleStore + GET 路由 + D 根因方向 A + R6 整体门槛 5 解封

> **版本**：v0.2.3（2026-06-19，Codex Stage 0 实测反馈修订，可派 Codex 进 Stage 1）  
> **作者**：Claude（第 47 任架构师）；v0.2.1 由 GPT 代集成，v0.2.2 架构师 R1 三审，v0.2.3 据 Codex Stage 0 实测补两处 P0  
> **审批级别**：架构升级类 + 评测层门槛 task（R1 + R6 + PM）  
> **前置基线**：main 必须包含 `3941605`（TASK-502 PR #103 squash merge）；Codex Stage 0 已实测 `git merge-base` BASE OK、`CURRENT_SCHEMA_VERSION = 3`  
> **入仓路径**：`docs/tasks/task-503-tuning-suggest-and-cache.md`  
> **入仓模式**：create file

---

## 状态

🔲 **v0.2.3，Codex Stage 0 摸底已通过 + 两处 P0 修订完毕，可派 Codex 进 Stage 1-6 实施**。

- v0.1：架构师起稿。
- v0.2：集成 GPT R1 一审 5 P0 + 9 P1 + 5 P2；PM 拍板真事务方案 A、DAG 方向 A。
- v0.2.1：集成 GPT R1 二审 6 P0 + 9 P1 + 4 P2（core binding 上移 / 组合视图 / 单一 spec 真值 / composer 缺参覆盖 / resolved evidence / LLMError 直通 等）。
- v0.2.2：架构师 R1 三审，抓出 1 项 v0.2.1 新引入 P0（`validate_for_spec` 误删），改双 validator 并存。
- v0.2.3：**Codex Stage 0 只读摸底**（理解自检 6/6 + 实测 14 项）抓出 2 个 P0，架构师据实测修订：
  1. **P0 / K_28a schema 假设陈旧**：main `CURRENT_SCHEMA_VERSION = 3`（v3 = TASK-310 teaching_units），非 v0.2.2 假设的 2。§4 改为 **目标 v4、paper 两表走 `_migrate_v3_to_v4`、dispatcher 重写为 ordered `_MIGRATIONS`**（修 main 既有“旧库先跑 latest DDL”半迁移 bug，D15）；迁移测试矩阵加 **v3→4 保留 teaching_units**。
  2. **P0 / K_30 composer 版本冲突**：main `paper_plan_composer.yaml` 已是 `v0.2`（TASK-502 R6 paper_reference 嵌套约束），非 v0.2.2 假设的 v0.1.3。改为 **v0.2 → v0.3，保留既有约束 + 追加缺参覆盖**（D16）。
  - 同步修 P1/P2：§14.1 CI 用实测命令；`ERROR_MAP` 符号名改“既有 LLMError handler 映射”+ 实测 HTTP 码；§12 任务卡入仓说明。

**Codex Stage 0 已确认可实施（理解 6/6、新增文件/leaf 均不存在、validate_for_spec + UserSupplyService 调用点已核）。本卡修订闭环，可派 Codex 进 Stage 1。**

---

## R2 公开 challenge 清单

| 轮次 | 项 | 裁决 | v0.2.1 落点 |
|---|---|---|---|
| 一审 | 真事务方案 A | PM 接受 | `PaperBundleStore.save_ready_bundle()` 单连接双表事务 |
| 一审 | DAG 方向 A：PlanComposer → MissingDetector | PM 接受 | 保留方向 A，但补 PlanComposer 缺参覆盖 contract |
| 二审 C1 | 单一 `SqlitePaperCache` 多继承三 ABC | GPT challenge 成立 | 改 `SqlitePaperBundleStore` + `_SpecCacheView` + `_PlanCacheView` 组合 |
| 二审 C2 | `MissingBindingModel` 保持 feature 私有但进入 core record/interface | GPT challenge 成立 | 新建 core 内部 domain `MissingParameterBinding`；feature 保留兼容 alias/re-export |
| 二审 C3 | plan 表复制 `spec_json` | GPT challenge 成立 | 删除重复列；bundle read 通过 JOIN 读取唯一 spec 真值 |
| 二审 C4 | PlanComposer prompt 沿用不动 | GPT challenge 成立 | composer prompt 升 v0.3（v0.2.3 Stage 0 修正：main 已是 v0.2，升 v0.3），增加缺参覆盖、唯一性和 evidence 约束 |
| 二审 C5 | tuning 只校验 prompt ID 属于历史列表 | GPT challenge 成立 | 必须同时属于 resolved prompt 集合，且 current plan 已为 user_supplied |
| 二审 C6 | provider 异常统一包装 + `raise ... from exc` | GPT challenge 成立 | LLMError 直接上抛；业务翻译 `from None` |

---

## 1. 上下文与目标

TASK-503 是 paper-to-model v0.1 后端收口 task，承接 TASK-501 的资料解析/PaperSpec 和 TASK-502 的 PaperPlanService/UserSupply/evaluator。

本卡完成五项产品能力：

1. 修复 TASK-502 的 `missing_binding_not_found` 根因；
2. 持久化 PaperSpec + PaperPlan，支持进程重启后读取；
3. 新增 `GET /spec`、`GET /plan`；
4. 新增 `POST /tuning-suggest`；
5. R6 真跑两个 paper-to-model case，解封 TASK-502 整体门槛 5。

前端 UX 仍留 TASK-504；本卡不承诺 `.slx` 成品、运行、收敛或最优调参。

### 1.1 最终数据流

```text
POST /api/v1/upload-document
  ↓ sandbox + parser（TASK-501，沿用）
PaperSpecService.extract_uncached()
  ↓
PaperPlanService.generate()
  ├─ Step 1：PlanComposer(v0.2) ∥ MScriptDrafter
  ├─ Step 2：MissingDetector(v0.2) ∥ SubsystemPlanner
  ├─ Step 3：Python 注入 prompt_id + PlanAssembler 一对一 binding
  └─ Step 4：EvidenceTagger / resolved helper 校验
  ↓
PaperPlanRecord（core internal record）
  ↓
PaperBundleStore.save_ready_bundle()（同一 SQLite connection、双表事务）
  ↓
GET /spec
GET /plan（原始 missing_prompts + remaining_missing_prompts）
POST /user-supply（TASK-502，改用 PlanCacheView）
POST /tuning-suggest（只引用 document evidence 或已 resolved 的 user evidence）
```

---

## 2. 强制范围边界

### 2.1 必须做

- core 内部 cache/store contract 与 binding/record 类型收口；
- SQLite schema bump + ordered migration；
- SQLite bundle store + spec/plan 组合视图；
- PaperSpecService `extract_uncached()`；
- PaperPlanService DAG 方向 A；
- PlanComposer prompt v0.2、MissingDetector prompt v0.2；
- Python 生成 MissingParameterPrompt `prompt_id`；
- GET spec/plan；
- TuningSuggestion service/route；
- PaperNotFoundError / PaperTuningError；
- 真实 SQLite fault injection；
- 两个 evaluator case 真跑；
- 03 TASK_INDEX 当前 task 状态同步。

### 2.2 不做

- TASK-504 前端；
- OCR、多文档、控制/信号处理扩样本；
- MATLAB Engine；
- 逆向调参；
- TuningSuggestion 历史持久化；
- 修改 06 § 12 字段或约束；
- 修改 eval fixtures；
- 修改 parser/sandbox；
- 修改 overview/explanation 私有结构；
- 统一 `put/set`、`invalidate/delete` 命名（留后续 chore）。

### 2.3 红线

- `core/` 不 import `features/`；
- `adapters/storage/` 不 import `features/paper/`；
- `features/paper/` 不 import `features/overview/` 或 `features/explanation/` 私有结构；
- 禁 `logger.exception`；
- 禁业务异常日志落 `str(exc)`、`repr(exc)`、traceback、LLM raw text、用户场景原文、PaperSpec/Plan 内容；
- async service 不得直接调用同步 `TextProvider.chat()`；
- sample fixtures 零改动；
- 对外不出现“一键生成模型/自动生成 .slx/最优调参”等承诺。

---

## 3. core contract 与内部 domain

### 3.1 `MissingParameterBinding` 上移 core

修订 `core/domain/paper_missing.py`，新增纯 Python frozen dataclass：

```python
@dataclass(frozen=True)
class MissingParameterBinding:
    """paper-to-model 内部绑定；不进入 06、API 或 ModelGenerationPlan。"""

    prompt_id: str
    paper_param_name: str
    model_param_name: str
```

约束：

- 名称不用 `Model` 后缀，避免误解为 Pydantic/API model；
- TASK-502 现有 `MissingBindingModel` 改为兼容 alias 或从 `features/paper/paper_plan_helpers.py` re-export：

```python
MissingBindingModel = MissingParameterBinding
```

- `core/` 和 adapter 只引用 `MissingParameterBinding`；
- 不新增 06 § 12 公共字段。

### 3.2 `PaperPlanRecord`

修订 `core/domain/paper_plan.py`：

```python
@dataclass(frozen=True)
class PaperPlanRecord:
    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingParameterBinding]
```

`spec` 在运行时 record 中存在，供 UserSupply/Tuning 使用；**SQLite plan 表不保存第二份 spec JSON**，adapter 通过 JOIN 组装 record。

### 3.3 `core/interfaces/paper_cache.py`

```python
class PaperBundleStore(ABC):
    @abstractmethod
    async def save_ready_bundle(self, record: PaperPlanRecord) -> None: ...

    @abstractmethod
    async def get_spec(self, paper_id: str) -> PaperSpec | None: ...

    @abstractmethod
    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None: ...

    @abstractmethod
    async def delete_bundle(self, paper_id: str) -> None: ...


class PaperSpecCache(ABC):
    @abstractmethod
    async def get(self, paper_id: str) -> PaperSpec | None: ...

    @abstractmethod
    async def put(self, paper_id: str, spec: PaperSpec) -> None: ...

    @abstractmethod
    async def invalidate(self, paper_id: str) -> None: ...


class PaperPlanCache(ABC):
    @abstractmethod
    async def get(self, paper_id: str) -> PaperPlanRecord | None: ...

    @abstractmethod
    async def set(self, paper_id: str, record: PaperPlanRecord) -> None: ...

    @abstractmethod
    async def delete(self, paper_id: str) -> None: ...
```

`features/paper/_paper_spec_cache.py` 与 `paper_plan_cache.py` 保留 InMemory 实现并兼容 re-export；生产装配不再用 InMemory。

---

## 4. SQLite schema 与 migration

> **R1 三审后 Codex Stage 0 实测修订(v0.2.3,K_28a)**:main 当前 `CURRENT_SCHEMA_VERSION = 3`(**不是 v0.2.2 假设的 2**),v3 由 TASK-310(commit `98ef3d9`)引入 `teaching_units` 表 + 2 索引。main 已有 `_migrate_v1_to_v2` + `_migrate_v2_to_v3`,**无** `_migrate_v3_to_v4`,**无** `_MIGRATIONS` 注册表。本任 bump 到 **v4**,paper cache 两表走 `_migrate_v3_to_v4`。

### 4.1 Stage 0 已确认版本(v0.2.3)

- Codex Stage 0 实测 `CURRENT_SCHEMA_VERSION = 3`;本任目标 = **4**;
- main 现状(Codex dump):`init_schema` 先 `executescript(_DDL)` 建 latest,再 `INSERT OR IGNORE schema_version(CURRENT)`,然后 `if version == 1` / `if version == 2` 串行迁移,**每个迁移函数内部各自 `UPDATE schema_version`**,最后 `commit()`;**无 `range(version, CURRENT)` 循环**;
- **重要 bug(Codex 抓出)**:旧库也先跑 latest `_DDL`,所以旧库在进 migration function 前已因 `CREATE TABLE IF NOT EXISTS` 拥有新表 → 半迁移风险(结构已变、version 可能未变);
- 测试文件统一命名 `test_schema_paper_cache_migration.py`,不把目标版本硬编码在文件名;
- 实施后任务卡/PR 写出实际 `3 → 4`。

### 4.2 最新 schema(latest DDL 追加 paper 两表)

`paper_spec_cache`:

```sql
CREATE TABLE paper_spec_cache (
    paper_id        TEXT PRIMARY KEY,
    paper_spec_json TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
```

`paper_plan_cache`:

```sql
CREATE TABLE paper_plan_cache (
    paper_id              TEXT PRIMARY KEY,
    plan_json             TEXT NOT NULL,
    missing_prompts_json  TEXT NOT NULL,
    missing_bindings_json TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
```

**禁止在 `paper_plan_cache` 增加 `spec_json`。** `paper_spec_cache.paper_spec_json` 是唯一持久化真值。

### 4.3 dispatcher 重写(v0.2.3:替换 main 既有 ad-hoc 串行 dispatcher,不只追加 v3→v4)

**决策点(PM 已知,见 D11 / D15)**:本任不能只追加 `if version == 3` 函数,因为 main 现有 dispatcher 有半迁移 bug(旧库先跑 latest DDL)。**本任 §4 重写 `init_schema` dispatcher 为 ordered `_MIGRATIONS` 模式**,这会触及 TASK-310 落地的 `_migrate_v1_to_v2` / `_migrate_v2_to_v3`(折叠进注册表 + 剥离其内部 version 写入),属于**共享基础设施重构**(blast radius 扩到 schema.py 迁移路径,但被迁移测试矩阵 § 4.4 兜底)。

dispatcher 新结构:

- **新库**(无 `schema_version` 表):一次 `executescript(latest _DDL)` 建全部表(含 paper 两表)+ 写入 `CURRENT_SCHEMA_VERSION = 4`;
- **旧库**(有 `schema_version` 表):**先读 version,不跑 latest `_DDL`**(修 Codex 抓出的半迁移 bug);在单一显式事务中按 `_MIGRATIONS` 顺序跑 `range(version, CURRENT)`:
  ```python
  _MIGRATIONS: dict[int, Callable[[aiosqlite.Connection], Awaitable[None]]] = {
      1: _migrate_v1_to_v2,   # TASK-302/既有,折叠进注册表
      2: _migrate_v2_to_v3,   # TASK-310 teaching_units,折叠进注册表
      3: _migrate_v3_to_v4,   # 本任新增:paper_spec_cache + paper_plan_cache 两表
  }
  ```
- `version > CURRENT_SCHEMA_VERSION` → fail closed(`StoreError`,future version 拒绝);
- `version == CURRENT_SCHEMA_VERSION` → no-op(幂等);
- **迁移函数只做本步增量 DDL,不单独 `UPDATE schema_version`**(折叠既有 `_migrate_v1_to_v2` / `_migrate_v2_to_v3` 时剥离它们内部的 version 写入);dispatcher 全部成功后**统一一次** `UPDATE schema_version = 4`;
- **迁移函数在外层事务内只用 `conn.execute()` / `executemany()`,禁止 `executescript()`**(P1-4;若既有 `_migrate_v2_to_v3` 用 executescript 建 teaching_units,需拆成逐条 execute);
- 任一步失败 `rollback`,schema version 和所有新表不得处于半迁移状态;rollback 失败只记 metadata,不覆盖主异常。

> 备选(B2 最小改,若 PM 否决重构):保留 main 既有 ad-hoc 串行 dispatcher,只加 `if version == 3: _migrate_v3_to_v4` + latest DDL 加 paper 两表。更小、不碰 TASK-310 迁移码;但保留半迁移 bug 作为 out-of-scope debt(对 paper 两表良性,因纯 CREATE 无数据迁移,IF NOT EXISTS 幂等)。**架构师推荐 B1(本节主方案)**:既有 dispatcher 的半迁移 bug 是所有未来迁移的隐患,且本任必须动 schema.py,顺手修对比单开 chore 便宜。

### 4.4 migration 测试硬门槛(v0.2.3:加 v3→4 保留 teaching_units)

- v1 → 4,既有 project/chat 数据保留;
- v2 → 4,既有 chunks 数据保留;
- **v3 → 4,既有 `teaching_units` 数据保留**(本任新增,因 v3 = TASK-310 teaching_units);
- target(4)重入幂等;
- future version(5)fail closed;
- migration 中途 fault 后 rollback(schema version + 新表均不半迁移);
- 新库直接 latest(含 paper 两表);
- plan 表不存在 `spec_json` 列。

---

## 5. SQLite bundle store + 组合视图

### 5.1 禁止单类多继承两个同名 `get()`

不实现：

```python
class SqlitePaperCache(PaperBundleStore, PaperSpecCache, PaperPlanCache): ...
```

原因：`PaperSpecCache.get()` 和 `PaperPlanCache.get()` 参数相同、返回类型不同，运行时无法因 DI 的 ABC annotation 自动选择实现。

### 5.2 生产实现

新增 `adapters/storage/sqlite_paper_cache.py`：

```python
class SqlitePaperBundleStore(PaperBundleStore):
    _SPEC_ADAPTER = TypeAdapter(PaperSpec)
    _PLAN_ADAPTER = TypeAdapter(ModelGenerationPlan)
    _PROMPTS_ADAPTER = TypeAdapter(list[MissingParameterPrompt])
    _BINDINGS_ADAPTER = TypeAdapter(list[MissingParameterBinding])

    async def save_ready_bundle(self, record: PaperPlanRecord) -> None: ...
    async def get_spec(self, paper_id: str) -> PaperSpec | None: ...
    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None: ...
    async def delete_bundle(self, paper_id: str) -> None: ...

    # 供组合视图委托的 adapter-private 方法
    async def put_spec(self, paper_id: str, spec: PaperSpec) -> None: ...
    async def invalidate_spec(self, paper_id: str) -> None: ...
    async def set_plan(self, paper_id: str, record: PaperPlanRecord) -> None: ...
    async def delete_plan(self, paper_id: str) -> None: ...


class SqlitePaperSpecCacheView(PaperSpecCache):
    def __init__(self, store: SqlitePaperBundleStore) -> None: ...
    async def get(self, paper_id: str) -> PaperSpec | None:
        return await self._store.get_spec(paper_id)
    async def put(self, paper_id: str, spec: PaperSpec) -> None:
        await self._store.put_spec(paper_id, spec)
    async def invalidate(self, paper_id: str) -> None:
        await self._store.invalidate_spec(paper_id)


class SqlitePaperPlanCacheView(PaperPlanCache):
    def __init__(self, store: SqlitePaperBundleStore) -> None: ...
    async def get(self, paper_id: str) -> PaperPlanRecord | None:
        return await self._store.get_plan_record(paper_id)
    async def set(self, paper_id: str, record: PaperPlanRecord) -> None:
        await self._store.set_plan(paper_id, record)
    async def delete(self, paper_id: str) -> None:
        await self._store.delete_plan(paper_id)
```

### 5.3 真事务写入

`save_ready_bundle()`：

1. 在开事务前完成四份 JSON 序列化；序列化失败 → metadata-only log + `StoreError(... ) from None`；
2. 单 connection：`BEGIN`；
3. UPSERT spec 表；
4. UPSERT plan 表；
5. commit；
6. 任一步失败 rollback 后原样 re-raise。

rollback 失败不得覆盖主异常：

```python
except Exception:
    try:
        await conn.rollback()
    except Exception as rollback_exc:
        logger.error(
            "paper bundle rollback failed: paper_id={} exception={}",
            paper_id,
            type(rollback_exc).__name__,
        )
    raise
```

### 5.4 唯一 spec 真值与完整性

`get_plan_record()` 必须 JOIN 两表：

```sql
SELECT s.paper_spec_json,
       p.plan_json,
       p.missing_prompts_json,
       p.missing_bindings_json
FROM paper_plan_cache AS p
JOIN paper_spec_cache AS s ON s.paper_id = p.paper_id
WHERE p.paper_id = ?;
```

- 两表都不存在 → `None`；
- 仅 spec row 存在 → 合法 spec-only 状态；`get_plan_record()` 返回 `None`，GET spec 仍可命中；
- 仅 plan row 存在 → `StoreError("paper_bundle_incomplete")`，不得伪装 404；
- `set_plan()` 要求 spec row 已存在，否则 `StoreError("paper_spec_missing_for_plan")`；
- `put_spec()` 在 plan row 已存在时拒绝覆盖，要求走完整 bundle rewrite；
- `invalidate_spec()` 若 plan row 已存在，必须在单事务中删除两表，禁止制造 plan-only 状态；
- `delete_plan()` 只删 plan row，留下合法 spec-only 状态以便重新生成；
- `delete_bundle()` 单事务删两表；
- `PaperPlanCacheView.set()` 支持 UserSupply 更新 plan-side JSON；
- 持久化 round-trip 使用 core dataclass TypeAdapter，不 import Pydantic feature wrapper。

### 5.5 DI

lifespan：

```python
store = SqlitePaperBundleStore(db_path)
app.state.paper_bundle_store = store
app.state.paper_spec_cache = SqlitePaperSpecCacheView(store)
app.state.paper_plan_cache = SqlitePaperPlanCacheView(store)
```

依赖函数分别返回三个不同对象/接口；不得把同一对象强转为三个 ABC。

---

## 6. D 根因方向 A

### 6.1 保留方向 A，但修正职责缺口

方向 A 不变：PlanComposer 主导参数 identity，MissingDetector 不再独立命名参数。

v0.2.1 不接受“PlanComposer prompt 沿用不动”。修订 `core/prompts/paper_plan_composer.yaml` **v0.2 → v0.3**（v0.2.3 Stage 0 修正：main 当前已是 `v0.2`，来自 TASK-502 R6 微补丁，语义是 `paper_reference` 嵌套 dict 6 字段约束；本任升 **v0.3**，**保留 v0.2 的 paper_reference 嵌套 dict 约束不动**，在其上**追加**缺参覆盖 contract）：

- 从 `PaperSpec.parameter_table`、equations、figure captions/locations、pseudocode 和 block-relevant evidence 中识别**论文已出现线索、模型搭建必需、但未给明确值**的参数；
- 每个此类参数输出恰好一个 `ParameterMapping`，`value="null"`；
- 只对论文中已有线索的参数起 sentinel，不把 solver、仿真时长等通用工程选择误报为“论文缺参”；
- `paper_param_name` 在整个 mapping 列表唯一；
- 每个 sentinel mapping 必须有可追溯 document evidence；
- 不生成 prompt_id；
- 非缺参 mapping 不得用 sentinel；
- 继续由 Python 覆盖 `plan_id` / `paper_spec_id`。

### 6.2 DAG

```text
Step 0：Python 生成 plan_id / paper_spec_id
Step 1：PlanComposer(v0.2) ∥ MScriptDrafter
Step 2：
  sentinel_mappings = plan.parameter_mapping where value == MISSING_VALUE_SENTINEL
  MissingDetector(spec, sentinel_mappings) ∥ SubsystemPlanner
Step 3：Python 按 sentinel 顺序生成 prompt_id，构造 MissingParameterPrompt
Step 4：PlanAssembler 校验一对一 cardinality，生成 MissingParameterBinding
Step 5：EvidenceTagger.validate_for_spec(evidence, spec) 校验 plan / block / missing prompt evidence
        （generate-time 尚无 PaperPlanRecord，且证据全为 document_extracted，用 validate_for_spec；
          validate_for_record 仅 tuning 用，见 § 9.4）
Step 6：返回 plan + prompts + bindings
```

### 6.3 MissingDetector v0.2

LLM 只输出与每个 sentinel 对应的 draft：

```text
parameter_name（必须逐字复制 paper_param_name）
paper_reference
suggested_unit
source（恒 user_supplied）
```

**不让 LLM 生成 `prompt_id`。** Python 按稳定顺序注入，例如：

```python
prompt_id = f"MISS-{paper_id}-{index:03d}"
```

并构造公共 `MissingParameterPrompt` 的 `user_supplied_value/unit=None`。

### 6.4 cardinality

- sentinel 数量 == prompt 数量 == binding 数量；
- `paper_param_name` 唯一；
- prompt_id 唯一；
- 每个 prompt 恰好一个 binding；
- 每个 binding 恰好一个 sentinel mapping；
- 禁用 set equality 掩盖重复；使用长度 + Counter/显式索引校验。

### 6.5 R6 关键测试

- missing_param case 能产生预期缺参，不因方向 A 丢掉 figure-only 线索；
- material_to_plan 不产生通用工程选择假阳性；
- composer 漏 sentinel → 明确 fail reason；
- duplicate mapping/prompt → fail-fast；
- prompt_id 全由 Python 生成；
- MScriptDrafter 与 PlanComposer 保持并发；
- SubsystemPlanner 与 MissingDetector 保持并发。

---

## 7. resolved prompt 单一算法

在 `features/paper/paper_plan_helpers.py` 新增纯函数：

```python
def resolved_prompt_ids(record: PaperPlanRecord) -> frozenset[str]:
    ...
```

判定某 prompt resolved 必须同时满足：

1. binding 存在且唯一；
2. 对应 mapping 存在且唯一；
3. mapping.value != MISSING_VALUE_SENTINEL；
4. mapping.source == "user_supplied"；
5. plan.evidence 中存在 `source="user_supplied"` 且 `missing_param_prompt_id == prompt_id` 的条目。

该函数是以下两处唯一真值源：

- GET `/plan` 计算 `remaining_missing_prompts`；
- Tuning evidence 校验 user-supplied provenance。

不得在 route 和 validator 中各写一套相似算法。

---

## 8. GET 路由

新增 `api/routes/paper_query.py`。

### 8.1 GET spec

`GET /api/v1/papers/{paper_id}/spec`

- 依赖 `PaperBundleStore.get_spec()`；
- hit → `SpecResponse`；
- miss → `PaperNotFoundError` 404；
- StoreError 保持 500。

### 8.2 GET plan

`PlanResponse`：

```python
class PlanResponse(BaseModel):
    paper_id: str
    plan: ModelGenerationPlanModel
    missing_prompts: list[MissingParameterPromptModel]
    remaining_missing_prompts: list[MissingParameterPromptModel]
```

- `missing_prompts` 保留原始 evaluator/audit 列表；
- `remaining_missing_prompts` 使用 `resolved_prompt_ids(record)`；
- private bindings 不出 API；
- 不完整 bundle → 500 StoreError，不伪装 404。

---

## 9. TuningSuggestionService

### 9.1 request

```python
class TuningSuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_scenario: str = Field(min_length=1, max_length=500)

    @field_validator("user_scenario")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_scenario must contain non-whitespace characters")
        return value  # 保留用户原文，不 trim/rewrite
```

长度/空白非法由 FastAPI 返回 422。

### 9.2 固定字段

```python
TUNING_DISCLAIMER = "建议需用户在 MATLAB 中验证"
```

该字面逐字对齐 06 § 12.6；本卡不修改 06。

Python 注入：

- `suggestion_id`；
- `user_scenario` 原文；
- `disclaimer`。

LLM 仅输出：

- `parameter_directions`；
- `expected_effect`；
- `confidence`；
- `evidence`。

不要把 suggestion_id 传给 LLM，也不要要求 LLM 照抄固定字段。

### 9.3 evidence 上下文

prompt 可用：

- document-extracted evidence；
- 当前 plan 中已经 resolved 的 user-supplied evidence。

不得只传全部历史 `missing_prompt_ids`。传入：

- `allowed_plan_parameter_names`；
- `allowed_document_evidence`；
- `allowed_resolved_user_evidence`；
- `resolved_prompt_ids`。

### 9.4 EvidenceTagger 双方法（R1 三审 P0：保留 `validate_for_spec`，新增 `validate_for_record`）

**不得删除/合并既有 `validate_for_spec`。** 两个方法并存，按调用阶段分工：

```python
# 既有方法（TASK-502 已落，本任不改签名；generate-time + 冻结 UserSupplyService 调用）
def validate_for_spec(
    evidence: list[PaperEvidenceEntry],
    spec: PaperSpec,
) -> None: ...

# 本任新增方法（仅 TuningService 调用；需要 resolved 证据 provenance 时）
def validate_for_record(
    evidence: list[PaperEvidenceEntry],
    record: PaperPlanRecord,
) -> None: ...
```

分工与理由（R1 三审 P0，K_36 + K_30）：

- **`validate_for_spec(evidence, spec)`** —— **保留 TASK-502 既有签名与行为，本任不动**。在两个上下文使用：
  1. `PaperPlanService.generate()` Step 5：此时 plan 刚生成、尚无 `PaperPlanRecord`，且所有 evidence 必为 `document_extracted`（无用户补充），只需 spec 白名单校验；
  2. **冻结的** `UserSupplyService.merge`（§ 12.4 必须 clean）：TASK-502 内部显式调 `evidence_tagger.validate_for_spec(plan_copy.evidence, record.spec)`，**删除此方法会让冻结文件 `AttributeError` 崩**。
  规则（沿用 TASK-502 R1 P1-1，不变）：
  - document_extracted：三 locator ≥ 1 + excerpt 1-300 字 + `missing_param_prompt_id = None`，locator ∈ spec 白名单；
  - user_supplied：三 locator 全 None + excerpt None + `missing_param_prompt_id` 必填（**仅校验基本形状，不校验 resolved**，因为 UserSupply 正处在“把该 prompt 变成 resolved”的过程中，此刻校验 resolved 会循环依赖）；
  - 覆盖 `plan.evidence` + `BlockRecommendation.paper_reference` + `MissingParameterPrompt.paper_reference` 三处证据位置。

- **`validate_for_record(evidence, record)`** —— **本任新增，仅 TuningService 调用**。tuning 读取的是“可能已被用户补充过”的 plan，需确认被引为 `user_supplied` 的证据确实对应一个**已 resolved** 的 prompt（而非历史白名单里尚未补充的 prompt）：
  - document_extracted：locator/excerpt 与 `record.spec` 白名单一致；
  - user_supplied：
    - locator/excerpt 必为空；
    - `missing_param_prompt_id` 必须在 `resolved_prompt_ids(record)`（§ 7 单一算法，比历史 `missing_prompts` 白名单更严）；
    - 必须在 `record.plan.evidence` 中找到对应 user-supplied 条目；
  - unresolved prompt 不得被标成 user-supplied 依据。

> R1 三审注：v0.2.1 曾把本方法写成“签名收口为 `validate_for_record`”，会删除 `validate_for_spec`，导致 generate-time 无 record 可校验、且冻结的 UserSupplyService 崩。v0.2.2 改为**双方法并存**。

### 9.5 param_name

每个 `ParameterDirection.param_name` 必须逐字属于当前 `plan.parameter_mapping[*].paper_param_name`，并且对应 mapping 不是 unresolved sentinel。

### 9.6 异常边界

- `LLMAuthError / LLMQuotaError / LLMRateLimitError / LLMServerError / LLMTimeoutError` 直接上抛，沿用既有 LLMError handler 映射（v0.2.3 Stage 0 实测：无 `ERROR_MAP` 符号，是 handler 内映射；实际 HTTP 码 auth/quota→503、rate-limit→429、timeout→504、server→502，passthrough 测试按此断言）；
- JSON decode / LLM output Pydantic / anti-hallucination / evidence invariant → `PaperTuningError` 502；
- cache miss → `PaperNotFoundError` 404；
- SQLite/serialization → `StoreError` 500；
- 所有业务翻译使用 `from None`；禁止 `from exc`。

示例：

```python
try:
    validate_for_record(suggestion.evidence, record)
except PaperPlanGenerationError as exc:
    logger.error(
        "tuning evidence invalid: paper_id={} exception={}",
        paper_id,
        type(exc).__name__,
    )
    raise PaperTuningError(reason="evidence_invalid") from None
```

### 9.7 最终公共 contract 验证

构造 domain 后，必须再经公开 wrapper 验证一次：

```python
validated = TuningSuggestionModel.from_domain(suggestion).to_domain()
return validated
```

确保 Python 注入字段和 LLM 四字段合并后仍满足 06/Pydantic 约束。

---

## 10. paper upload 真事务

修订 `PaperSpecService`：

- `extract_uncached(file_path, paper_id)` 保留既有解析、LLM、Pydantic、evidence 校验，只移除 cache read/write；
- `extract()` 兼容既有行为，内部调用 `extract_uncached()` 后写原 cache；
- 对既有外部签名无破坏。

修订 `paper_upload.py`：

1. 保留 TASK-501 的 sandbox、magic、hash、metadata-only logging、cleanup；
2. 调 `extract_uncached()`；
3. 调 `PaperPlanService.generate()`；
4. 构造 `PaperPlanRecord`；
5. `await bundle_store.save_ready_bundle(record)`；
6. 成功后返回；
7. 失败不留任一 ready row。

不得保留应用层补偿删除 helper。

---

## 11. 异常与 HTTP

| Exception | HTTP | machine code | 场景 |
|---|---:|---|---|
| `PaperNotFoundError` | 404 | `paper_not_found` | GET/tuning 找不到 bundle |
| `PaperTuningError` | 502 | `paper_tuning_failed` | JSON/schema/anti-hallucination/evidence 输出失败 |
| `PaperPlanGenerationError` | 502 | `paper_plan_generation_failed` | plan DAG/assembler/evidence 生成侧 |
| `PaperUserSupplyError` | 400 | `paper_user_supply_invalid` | TASK-502 用户补充校验；其 cache miss 404 统一留后续 chore |
| `StoreError` | 500 | `store_error` | SQLite、序列化、bundle incomplete |
| 既有 `LLMError` 子类 | 沿用既有 handler 映射（auth/quota→503, rate-limit→429, timeout→504, server→502） | 沿用 | provider/auth/quota/rate-limit/server/timeout |
| FastAPI request validation | 422 | framework default | tuning request 长度、空白、extra 字段 |

---

## 12. 文件真值表

### 12.1 新增生产文件（6）

| 路径 | 用途 |
|---|---|
| `core/interfaces/paper_cache.py` | BundleStore + 两个 cache ABC |
| `core/prompts/paper_tuning_suggest.yaml` | tuning 四字段 prompt |
| `features/paper/paper_tuning_service.py` | tuning use case |
| `adapters/storage/sqlite_paper_cache.py` | BundleStore + 两个组合 view |
| `api/routes/paper_query.py` | GET spec/plan |
| `api/routes/paper_tuning.py` | POST tuning-suggest |

### 12.2 修订生产/文档文件（18）

| 路径 | 修订 |
|---|---|
| `core/domain/paper_missing.py` | `MissingParameterBinding` |
| `core/domain/paper_plan.py` | `PaperPlanRecord` |
| `core/domain/exceptions.py` | PaperTuningError / PaperNotFoundError |
| `core/prompts/paper_plan_composer.yaml` | v0.2 → v0.3 缺参覆盖 contract（保留 v0.2 paper_reference 嵌套约束） |
| `core/prompts/paper_plan_missing_detector.yaml` | v0.2 draft-only output |
| `features/paper/__init__.py` | re-export 必要 service/contract |
| `features/paper/_prompt_builder.py` | composer/missing/tuning builders |
| `features/paper/_paper_spec_cache.py` | core ABC 兼容 re-export |
| `features/paper/paper_plan_cache.py` | core ABC/record 兼容 re-export |
| `features/paper/paper_plan_helpers.py` | alias + cardinality + resolved helper + 双 validator（保留 validate_for_spec + 新增 validate_for_record，§ 9.4） |
| `features/paper/paper_plan_service.py` | DAG 方向 A + Python prompt ID |
| `features/paper/paper_spec_service.py` | extract_uncached |
| `api/dependencies.py` | store + views + tuning service |
| `api/main.py` | lifespan/router |
| `api/middleware/error_handler.py` | 两个新 leaf |
| `api/routes/paper_upload.py` | bundle transaction |
| `docs/03_TASK_INDEX.md` | 当前 task 状态/进度 |
| `adapters/storage/schema.py` | schema + migration |

> Codex Stage 0 必须按逐行表重新计数，并在 PR 中用 `git diff --name-only` 报告实际文件；不得照抄估算总数。

### 12.3 测试文件

必须新增/修订：

- `tests/core/test_paper_cache_contracts.py`
- `tests/features/paper/test_paper_plan_service.py`
- `tests/features/paper/test_paper_plan_helpers.py`
- `tests/features/paper/test_paper_spec_service.py`
- `tests/features/paper/test_paper_tuning_service.py`
- `tests/adapters/storage/test_sqlite_paper_cache.py`
- `tests/adapters/storage/test_schema_paper_cache_migration.py`
- `tests/api/test_paper_upload.py`
- `tests/api/test_paper_query.py`
- `tests/api/test_paper_tuning.py`
- `tests/api/test_paper_tuning_error_handler.py`
- `tests/api/test_lifespan_with_sqlite_paper_cache.py`

### 12.4 必须 clean

- `docs/06_OUTPUT_CONTRACTS.md`
- `features/paper/paper_schemas.py`
- `core/prompts/paper_spec_extract.yaml`
- `core/prompts/paper_plan_subsystem.yaml`
- `core/prompts/paper_plan_mscript.yaml`
- `features/paper/paper_user_supply_service.py`（只通过兼容 re-export/DI 继续工作）
- parser/sandbox 全部；
- overview/explanation 全部；
- `eval/cases/paper_to_model/` 全部。

> **本任务卡入仓说明**(v0.2.3 / Codex Stage 0 P2):`docs/tasks/task-503-tuning-suggest-and-cache.md` 本身随本 PR 一起入仓(入仓模式 = create file),可作为 PR 第一个 commit（如 `docs: add TASK-503 task card`）；§ 14.8 范围报告把它列为**预期 docs 文件**,不触发"范围外文件停手"。

---

## 13. 实施阶段

### 阶段 0：实地核查

- base ancestor；
- git status clean；
- CI workflow 全命令；
- current schema version 与 migration chain；
- TASK-502 四个 LLM role；
- MissingBindingModel 实际字段/类型；
- PaperSpecCache/PaperPlanCache 实际 abstract methods；
- LLMError 子类及既有 handler 映射（无 `ERROR_MAP` 符号，Stage 0 已实测：auth/quota→503, rate-limit→429, timeout→504, server→502）；
- 当前 prompt version；
- 当前 evaluator 两 case 文件完整。

任一与任务卡不符，停手报 PM；不要以“可在实现时猜测”继续。

### 阶段 1：core contract + migration + SQLite store

完成 § 3-5 和对应测试。

### 阶段 2：DAG 方向 A

完成 § 6-7 和两 prompt 版本升级。

### 阶段 3：GET 路由

完成 § 8。

### 阶段 4：TuningSuggestion

完成 § 9、11。

### 阶段 5：upload 真事务 + DI

完成 § 10 和 lifespan 装配。

### 阶段 6：R6 + 索引

真跑全 CI、fault injection、两 case、进程重启持久化；更新 03 索引。

---

## 14. R6 完工硬门槛

### 14.1 CI

Codex Stage 0 已从 `.github/workflows/ci.yml` 抄录实际命令(**v0.2.3 用实测值替换 v0.2.2 示例**):

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
mypy core/ adapters/ features/ api/
pytest -v --tb=short
bash scripts/check_repo_hygiene.sh
```

注意实测与 v0.2.2 示例的差异:`ruff check/format` 是全仓 `.`(非分目录);`mypy` 是 `core/ adapters/ features/ api/`(`features/` 全目录,非 `features/paper/`);`pytest` 是 `-v --tb=short`;额外有 `bash scripts/check_repo_hygiene.sh`。以 workflow 为准。`make check` 只能附加,不能替代 workflow 命令。

### 14.2 分层/隐私静态检查

```bash
git grep -nE 'from features|import features' -- core/ adapters/storage/sqlite_paper_cache.py
# 期望 0

git grep -n 'logger.exception' -- core/ adapters/ features/paper/ api/
# 期望 paper 本次改动 0

git grep -nE 'from exc|raise .* from exc' -- features/paper/paper_tuning_service.py
# 期望 0

git grep -nE 'str\(exc\)|repr\(exc\)|response\.text|raw_text' -- features/paper/ api/routes/paper_*.py adapters/storage/sqlite_paper_cache.py
# 期望不在日志分支出现
```

`asyncio.to_thread` grep 只归档，不作数量硬契约。硬门槛由 semantic spy 验证所有同步 `.chat()` 均经 gateway。

### 14.3 contract/store 测试

必须覆盖：

- core 无 feature-private type；
- store/views 三接口签名；
- 不存在同名方法多继承；
- plan table 无 `spec_json`；
- bundle JOIN round-trip；
- plan-only incomplete bundle → StoreError；spec-only 状态合法；
- UserSupply 通过 plan view 更新后 GET/tuning 读取新记录；
- 两表事务中途 SQLite fault → 两表均无残留；
- rollback 自身失败不覆盖主异常；
- process restart 后 GET 仍命中。

### 14.4 DAG/tuning 测试

- composer missing coverage；
- Python prompt ID；
- duplicate/cardinality；
- resolved helper；
- unresolved user evidence 拒绝；
- resolved user evidence 接受；
- disclaimer 精确字面；
- whitespace scenario 422；
- LLMError 五子类直接上抛；
- PaperTuningError 仅包装输出/校验错误；
- 最终 TuningSuggestionModel 验证。

### 14.5 端点实测

先通过上传获得真实 ID：

```bash
PAPER_ID='<upload response paper_id>'

curl -f "http://localhost:8000/api/v1/papers/${PAPER_ID}/spec"
curl -f "http://localhost:8000/api/v1/papers/${PAPER_ID}/plan"
curl -f -X POST "http://localhost:8000/api/v1/papers/${PAPER_ID}/tuning-suggest" \
  -H 'Content-Type: application/json' \
  -d '{"user_scenario":"我想让短路保护更灵敏"}'
```

404、422、502、既有 LLMError HTTP 映射均有测试。

### 14.6 跨进程重启持久化

表述统一为**跨进程重启**，不是“跨 worker”：

1. 单 worker 启动；
2. 上传并记下 PAPER_ID；
3. 终止进程；
4. 重新启动；
5. GET spec/plan 均 200。

### 14.7 evaluator

```bash
python eval/run_paper_eval.py \
  --case material_to_plan/case_01_motor_short_circuit \
  --output-dir /d/tmp/task-503-r6

python eval/run_paper_eval.py \
  --case missing_param/case_01_missing_image_param \
  --output-dir /d/tmp/task-503-r6
```

硬门槛：

- 两 case 均 `succeeded`；
- 各自 ✅ 或 🟡；
- 0 E1/E2；
- `blocked_known_defect` 不通过；
- actual JSON、CSV、人工项和 fail reason 全部附 PR。

### 14.8 范围报告

PR 必须附：

```bash
git diff --stat origin/main
git diff --name-only origin/main
git status --short
```

并逐项对照 § 12 文件真值表；任何范围外文件停手报 PM。

---

## 15. 验收清单

### 架构

- [ ] core/adapter 不 import feature-private binding
- [ ] 使用 `MissingParameterBinding` core internal domain
- [ ] bundle store + 两个组合 view，无同名 `get()` 多继承
- [ ] spec JSON 只有一份持久化真值
- [ ] plan record 通过 JOIN 组装
- [ ] incomplete bundle fail closed

### DAG

- [ ] PlanComposer prompt v0.2 明确缺参覆盖
- [ ] MissingDetector 不独立命名 parameter
- [ ] prompt_id Python 注入
- [ ] cardinality 不使用 set 掩盖重复
- [ ] 两 case 缺参行为符合 ground truth

### Tuning

- [ ] LLM 只输出 4 字段
- [ ] Python 注入 ID/scenario/disclaimer
- [ ] disclaimer 精确为“建议需用户在 MATLAB 中验证”
- [ ] blank scenario 422
- [ ] user-supplied evidence 只允许 resolved prompt
- [ ] unresolved prompt evidence 拒绝
- [ ] final public wrapper 校验
- [ ] LLMError 子类直接上抛
- [ ] 业务异常 `from None`

### Storage/migration

- [ ] ordered migration
- [ ] 事务内不用 executescript
- [ ] future fail closed
- [ ] fault rollback
- [ ] rollback failure 不覆盖主异常
- [ ] process restart 读取成功

### R6

- [ ] 实际 CI 全绿
- [ ] full pytest 全绿
- [ ] static/privacy/boundary grep 全绿
- [ ] 两 case succeeded + ✅/🟡 + 0 E1/E2
- [ ] sample fixtures 零 diff
- [ ] 完工 report 附 stat/name-only/status
- [ ] 03 TASK_INDEX 同步

---

## 16. 风险与停手机制

1. **PlanComposer 仍漏 figure-only 缺参**：先用 actual prompt/input/output 诊断；不得直接扩大 schema。若 v0.2 prompt 仍无法稳定覆盖，停手报 PM，附两 case actual。
2. **迁移基线不是 v2**：停手报 PM，不自行重编号。
3. **现有 UserSupplyService 与 core alias 不兼容**：只允许兼容 re-export/类型替换；不得改公开 API。
4. **LLM typed error 当前实现与任务卡不同**：以 main 的既有 LLMError handler 映射为真值，保留全部既有 leaf，不统一包装。
5. **SQLite fault injection 难以稳定触发**：在 adapter 内注入 execute hook/fake connection，但必须至少有一条真实 SQLite transaction rollback 集成测试，不可只 mock cache。
6. **真实 case 不达门槛**：走决策 15 diagnose-before-fix，停手报告；不得把 `blocked_known_defect` 改名为 pass。

---

## 17. 决策日志

- **D1**：审批维持 R1 + R6 + PM。
- **D2**：DAG 方向 A 保留；composer prompt 必须升级，不把产品门槛押给 R6 后置微补丁。
- **D3**：binding/record/ABC 全部只依赖 core；06 公共 contract 不变。
- **D4**：SQLite 采用 BundleStore + composition views；拒绝同名方法多继承。
- **D5**：PaperSpec 只持久化一份；plan row 不复制 spec。
- **D6**：upload 使用单 connection 双表事务。
- **D7**：GET plan 的 remaining 与 tuning provenance 共用 `resolved_prompt_ids()`。
- **D8**：tuning 允许双源，但 user source 必须已 resolved。
- **D9**：固定 ID/scenario/disclaimer 均由 Python 注入；prompt 不接 suggestion_id。
- **D10**：LLMError 沿既有树直接上抛；PaperTuningError 只覆盖输出/业务 invariant。
- **D11**：migration ordered、fail closed、fault rollback；**v0.2.3 Stage 0 修正：目标版本 3 → 4（main 已是 v3），paper 两表走 `_migrate_v3_to_v4`**。
- **D12**：R6 两 case 是不可降级硬门槛。
- **D13**：TuningSuggestion 不持久化，理由为需求/key/audit/隐私尚未定义。
- **D14**（R1 三审 P0）：EvidenceTagger 保留既有 `validate_for_spec(evidence, spec)`（generate-time + 冻结 UserSupplyService 用），**新增** `validate_for_record(evidence, record)`（仅 tuning 用，含 resolved provenance 校验）；两方法并存，不合并不删除。
- **D15**（v0.2.3 Stage 0 P0）：§4 dispatcher **重写为 ordered `_MIGRATIONS` 模式（方案 B1）**，替换 main 既有 ad-hoc 串行 dispatcher，折叠 `_migrate_v1_to_v2` / `_migrate_v2_to_v3` 进注册表、剥离其内部 version 写入、修“旧库先跑 latest DDL”半迁移 bug。blast radius 扩到 TASK-310 迁移路径，由 § 4.4 迁移测试矩阵（含 v3→4 保留 teaching_units）兜底。备选 B2（最小追加、保留 bug）若 PM 否决重构再切换。
- **D16**（v0.2.3 Stage 0 P0）：`paper_plan_composer.yaml` 版本 **v0.2 → v0.3**（main 已是 v0.2 = TASK-502 R6 paper_reference 嵌套约束），v0.3 **保留** v0.2 约束 + **追加**缺参覆盖 contract，不覆盖。

---

## 18. 起稿元信息与修订历史

- v0.1（2026-06-19）：架构师起稿。
- v0.2（2026-06-19）：集成 GPT R1 一审 19 项；PM 选择真事务 A、DAG A。
- v0.2.1（2026-06-19）：GPT R1 二审 conditional pass 后代集成 6 P0 + 9 P1 + 4 P2；待 R1 三审。
- v0.2.2（2026-06-19）：架构师 R1 三审。二审 19 项确认关闭 18 项；抓出 1 项 v0.2.1 集成新引入的 P0（`validate_for_spec` 被“签名收口”删除 → generate-time 无校验器 + 冻结 UserSupplyService 崩），改为 `validate_for_spec` + `validate_for_record` 双方法并存（§ 9.4 / D14）。其余 v0.2.1 内容未改动。**R1 三审 P0 = 0，三轮收敛（决策 12 v0.4 § 7.1 R 轮稳态上限 3 轮）。**
- v0.2.3（2026-06-19）：Codex Stage 0 只读摸底反馈（理解 6/6，实测 14 项，抓 2 P0 + 2 P1 + 3 P2）。架构师据 main 实测修订：§4 schema 目标 2→3 改为 **3→4**（main 已 v3 = TASK-310 teaching_units），dispatcher 重写为 ordered `_MIGRATIONS` 修半迁移 bug（D15），迁移测试加 v3→4 保留 teaching_units；composer prompt v0.1.3→v0.2 改为 **v0.2→v0.3**（main 已 v0.2，保留既有约束 + 追加缺参覆盖，D16）；§14.1 CI 用实测命令；`ERROR_MAP` 名改“既有 handler 映射”+ 实测 HTTP 码；§12 加任务卡入仓说明。**两 P0 均为架构师无 checkout 凭知识库起稿的陈旧假设，Stage 0 摸底正常拦下，未流入实现。**

**下一步**：PM 复核 v0.2.3 两处 P0 修订（尤其 D15 dispatcher 重构 blast radius 是否接受 B1）→ 把 v0.2.3 覆盖入仓 → 派 Codex 进 Stage 1-6（Codex 已完成 Stage 0，A/B/D 全清,可直接实施）。Codex 实施期对**任何新的** main 实际与任务卡不符仍按决策 15 停手。
