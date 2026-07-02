# TASK-522-C1:用户纠错 · 契约 substrate(v0.2 — GPT R1 + Codex R6 双审收敛版)

## 状态

🔲 v0.2(2026-07-02,派 Codex 终版)
- 起稿基础:origin/main HEAD 本会话末实测 = `f29e4a4`(Stage 0 用 live 值校验,允许 main 合法前进)
- GPT(R1)设计审:9 P0 + 6 P1 + 4 P2 + 裁决 A/B/C + 反方向 challenge(overlay 模型)——全盘采纳,核心结构按 overlay 收敛
- Codex(R6)并行 live 核:7 项现状假设全部核准(冲突参数不进 plan mapping / parameter_table 允许同 (name,symbol) 多行 / validate_for_spec 不反查 ParameterEntry / GET 暴露 evidence + ParameterEntry.source / build_steps 生成期 user prompt allowlist 为空 / 清理级联现覆盖三表 / 锁 registry 形状可复用)
- **本卡只落契约 substrate,全程惰性:不接端点、不改纠错行为、不动前端;纠错服务 + 端点 + 撤销 + 锁 + 建模步骤简化 + 前端 = TASK-522-C2**

---

## 上下文

### 在解析纠错子线(TASK-522)的位置

解析纠错四条:① 诚实提示(对内暂缓)/ ② 重新解析(**522-B ✅ 合并 #160**)/ ③ 用户纠错 / ④ 局部重跑(最难,排最后)。

③「用户纠错」= 让用户手动改 AI **抽错的参数值**。本卡(C1)只铺契约地基;行为 + 前端在 C2。

### 核心架构决策:overlay 模型(纠错不篡改论文抽取表)

双审共同收敛出的核心结构 —— **纠错改「工作值」、不改「论文抽取表」**:

- `PaperSpec.parameter_table` = **不可变**的文档抽取结果(论文说什么就是什么),纠错**永不改它**。它是 521-B2 `parameter_conflicts` 冲突检测的真值源 —— 保持不动,冲突检测不受任何搅动。
- `ModelGenerationPlan.parameter_mapping` = 实际拿去建模的**工作值**(前端参数表就是渲染这个,Codex R6 #2 已证 `<ParameterTable plan={data.plan}>`)。纠错改的是这里对应那条 mapping 的 value/unit,并把 source 翻成 `user_supplied`。
- 新增内部表 `paper_parameter_correction` = 纠错的**审计/撤销 overlay**(存 AI 原抽值 + 纠错值),供 C2 的「AI 原本抽:X」+ 撤销。

这样:纠错不伪造论文出处(改过的值 source=user_supplied、无 document_id,和现有「补缺失值」同待遇);论文抽取表与冲突视图零搅动;原抽值有完整审计留痕。GPT 反方向 challenge 明确推荐此 overlay 结构、避免将来工作台本地包审计历史时返工。

### 现状地基(Codex R6 @ `f29e4a4` 实测,C2 会用)

- 出处枚举 `EvidenceSource {document_extracted, user_supplied}`。`source=user_supplied` 时 `document_id` 恒 null(`ParameterEntryModel` validator 已强制);evidence 里 user_supplied 条目**现强制要 `missing_param_prompt_id`**(其余 locator/excerpt/document 全 null)——**这正是本卡要扩的点**:现契约只覆盖「填缺失」,覆盖不了「纠正已抽出」(纠错没有 prompt)。
- spec 参数 = `ParameterEntry(name, symbol, value, unit, source, document_id)`;plan 映射 = `ParameterMapping(paper_param_name, model_param_name, value, unit, source)`(无 document/locator)。
- 冲突参数**不进 plan.parameter_mapping**(`without_conflicted_parameter_entries` 过滤 + `validate_plan_does_not_resolve_conflicts` 守门)。⇒ 冲突参数没有可纠错的 plan mapping;③ 天然管不到冲突消解(那是 522-D 的活)。
- `validate_for_spec` 只校验传入的 evidence list,**不反查 ParameterEntry**;`ParameterEntry.source/document_id` 自校验,与 evidence list 相互独立。⇒「纠错值靠 mapping.source 自描述」在这层可行。
- GET `/spec` 暴露 `spec.evidence`(list[PaperEvidenceEntryModel])+ ParameterEntry.source/document_id;GET `/plan` 暴露 `plan.evidence` + ParameterMapping.source。⇒ **PaperEvidenceEntry 是对外 DTO 的一部分,给它加字段 = 对外契约变更**(可空、向后兼容,见 § 接口契约)。
- build_steps 生成期 provenance 校验 `allowed_user_prompt_ids=frozenset()`(空);`parameter_refs` 只按 `(paper_param_name, model_param_name)` 名字匹配 mapping、不要求 evidence。
- 清理/替换现状:`delete_bundle` / `delete_expired_paper_bundles` / `replace_ready_bundle_with_source`(522-B)现级联/事务覆盖 `paper_plan_cache` / `paper_spec_cache` / `paper_reparse_source_cache` 三表。
- `PaperReparseLockRegistry` = 单进程 per-paper asyncio.Lock registry(形状可复用,名字/错误 reparse 专用)。

### Base + 范围边界

- **Base**:main 必须含 `f29e4a4`(Stage 0 用 `git merge-base --is-ancestor <live f29e4a4> origin/main` 校验,允许 main 合法前进)。
- **范围(C1)**:出处契约扩展 + 纠错表 schema + 惰性 store CRUD + 清理级联 + 统一「用户证据」判定器 + 06 文档 + schema JSON + 边界/向后兼容测试。**全程惰性,端到端无纠错发生。**
- **不在本卡(留 C2)**:纠错服务(target 校验 / stale / ambiguous / apply / undo)、端点、per-paper 纠错锁使用、build_steps/m_script 简化、把消费方接到统一判定器、前端、截图。

---

## 输入(前置依赖)

- 必须已完成:TASK-502(UserSupplyService/EvidenceTagger)、TASK-503(PaperBundleStore SQLite)、TASK-507-A/B(build_steps provenance)、TASK-521-A/B1/B2/C(多文档身份 + 冲突 + citation)、**TASK-522-B(reparse + 清理级联 + 锁 registry + 原子替换)**均已合并 main
- 必读:`06_OUTPUT_CONTRACTS.md`(paper-to-model 输出契约,含 evidence / ParameterEntry / ParameterMapping)、`04_ENGINEERING_STANDARDS.md`(§ 8.6 文档安全、日志禁令)、决策 12 v0.4 / 13 / 26

---

## 输出(交付物)

- 修改:`PaperEvidenceEntry`(core dataclass)+ `PaperEvidenceEntryModel`(pydantic)——加 3 可空字段 + invariant validator + 向后兼容读回
- 新增:`PaperParameterCorrection` / `PlanCorrectionTarget` domain 类型 + `paper_parameter_correction` 表 DDL + `CURRENT_SCHEMA_VERSION` 6→7 + 索引
- 新增:PaperBundleStore 惰性 CRUD(insert/update_value/get/list/delete correction)
- 修改:`delete_bundle` / `delete_expired_paper_bundles` / `replace_ready_bundle_with_source` 级联/事务加 `paper_parameter_correction`(纯加一张表,原行为不动)
- 新增:`resolved_user_evidence_refs` 统一判定器(惰性,单测)+ `UserEvidenceRef` / `UserEvidenceAction` 类型
- 修改:`06_OUTPUT_CONTRACTS.md` evidence 契约段;schema JSON(export/verify 零非预期 drift)
- 新增:边界测试 + 向后兼容读回测试 + 级联/CRUD 单测

---

## 范围(必须做)

- [ ] **A. 出处契约扩展(裁决 A ①)**:`PaperEvidenceEntry` + `PaperEvidenceEntryModel` 加 `user_action` / `parameter_correction_id` / `correction_param_key` 三个可空字段(默认 None),按 § 接口契约 invariant 表加 validator。
- [ ] **A2. 向后兼容读回**:老 `user_supplied` blob(有 `missing_param_prompt_id`、无 `user_action`)读回时归一化为 `user_action="fill_missing"`;新写入一律显式写 `user_action`。归一化在读回 seam 做,validator 对新写入严格。
- [ ] **B. 纠错表 + domain 类型**:`PaperParameterCorrection` / `PlanCorrectionTarget` frozen dataclass;`paper_parameter_correction` 表 DDL + 索引 `idx_paper_parameter_correction_paper(paper_id)`;`CURRENT_SCHEMA_VERSION` 6→7。
- [ ] **C. 惰性 store CRUD**:insert / update_corrected_value / get / list_by_paper / delete —— 序列化走已实证 wrapper 模式,失败向上抛 StoreError,**不 log 任何 value/unit**(decision 11)。本卡无 service 调用它们,仅单测覆盖。
- [ ] **D. 清理/替换级联**:`delete_bundle` + `delete_expired_paper_bundles`(TTL)+ `replace_ready_bundle_with_source`(reparse 成功清空该 paper 纠错)三处,各加 `DELETE FROM paper_parameter_correction WHERE paper_id=?`,与现有删除**同事务**;TTL sweep 补该表 orphan 清理。**纯加一张表进现有级联,现有三表行为逐字不动**(diff 边界逐处核)。
- [ ] **E. 统一判定器(裁决 C)**:新增 `resolved_user_evidence_refs(record, corrections) -> set[UserEvidenceRef]`,并存 `resolved_prompt_ids`(**不删不合并**):fill_missing → prompt_id ∈ `resolved_prompt_ids(record)`;correct_extracted → correction_id ∈ 活跃 corrections 且 target 仍匹配当前 plan mapping。本卡只实现 + 单测(合成数据),**不改任何现有消费方**(build_steps/tuning/ask 接线留 C2)。
- [ ] **F. schema-sync(decision 13 全清单)**:`make export-schema && make verify-schema` 捕获 evidence 契约变更、无其他非预期 drift;06 文档同步;新字段边界测试(4 类组合:document_extracted / 老式 user_supplied / fill_missing / correct_extracted)。

---

## 不做(明确排除,留 C2 或更后)

- ❌ 纠错服务业务逻辑:target 定位 / stale echo 校验 / ambiguous 拒绝 / apply / undo(C2)
- ❌ 端点:`POST /parameter-correction`、`/undo`、`GET /parameter-corrections`(C2)
- ❌ per-paper 纠错锁的**使用**(与 reparse 互斥)(C2;本卡不碰 lock registry 代码)
- ❌ build_steps / m_script_skeleton 简化(纠错触发的 null-out)(C2)
- ❌ 把 build_steps provenance / tuning / ask source table 接到统一判定器(C2)
- ❌ 前端任何改动 / 截图(C2)
- ❌ **改 `PaperSpec.parameter_table`**(overlay 模型:抽取表永不可变,不在本卡也不在 C2)
- ❌ 改已合并的 522-B `PaperReparseLockRegistry` 类本体 / reparse 路由 / seam(本卡只在 §D 三个清理/替换函数加一张表进级联)

---

## 接口契约(贴具体签名,Codex 不许改签名语义)

### A. 出处契约(core dataclass)

```python
class UserEvidenceAction(str, Enum):
    FILL_MISSING = "fill_missing"
    CORRECT_EXTRACTED = "correct_extracted"

@dataclass(frozen=True)
class PaperEvidenceEntry:
    source: EvidenceSource
    document_id: str | None
    paper_section_id: str | None
    equation_id: str | None
    figure_id: str | None
    excerpt: str | None
    missing_param_prompt_id: str | None
    # 新增(均可空,默认 None,加在末尾保持位置构造兼容)
    user_action: UserEvidenceAction | None = None
    parameter_correction_id: str | None = None
    correction_param_key: str | None = None
```

### A. 对外 pydantic 模型新增字段 + invariant

`PaperEvidenceEntryModel` 加同名三字段(`parameter_correction_id` / `correction_param_key` 若非 None 则 `min_length=1`),`model_validator(mode="after")` 强制下表(**这是本卡红线校验,逐条实现**):

| source | user_action | 要求 | 禁止 |
|---|---|---|---|
| document_extracted | 必 None | —(现有 document 校验不变) | user_action / correction_id / param_key 任一非 None → reject |
| user_supplied | None(**仅向后兼容**) | missing_param_prompt_id 必填(归一化视为 fill_missing) | correction_id / param_key 非 None → reject |
| user_supplied | fill_missing | missing_param_prompt_id 必填 | correction_id / param_key 非 None → reject |
| user_supplied | correct_extracted | parameter_correction_id 必填;document_id/section/equation/figure/excerpt 全 None | missing_param_prompt_id 非 None → reject |

向后兼容:老 blob(user_supplied + missing_param_prompt_id + 无 user_action)读回归一化为 fill_missing;归一化优先在读回 seam 完成,validator 对新写入严格(`user_supplied` 必带 `user_action`)。**优先方案 = 读回归一化 + validator 严格;若 Codex 判定读回 seam 不易插入,可退为「validator 接受 user_action=None 的隐式 fill_missing 兼容态」,二选一在 Stage 0 定并报架构师。**

### B. 纠错 domain 类型 + 表

```python
@dataclass(frozen=True)
class PlanCorrectionTarget:
    paper_param_name: str
    model_param_name: str
    plan_mapping_index: int

@dataclass(frozen=True)
class PaperParameterCorrection:
    correction_id: str
    paper_id: str
    param_key: str                      # = f"{paper_param_name}::{model_param_name}"(plan mapping 身份)
    plan_target: PlanCorrectionTarget
    original_value: str
    original_unit: str | None
    original_source: EvidenceSource     # 首次纠错时的原 source(document_extracted)
    original_document_id: str | None    # 原抽出参数的 document_id(供 C2「AI 原本抽」+ doc label)
    corrected_value: str
    corrected_unit: str | None
    created_at: str
    updated_at: str
```

```sql
CREATE TABLE paper_parameter_correction (
    correction_id      TEXT PRIMARY KEY,
    paper_id           TEXT NOT NULL,
    param_key          TEXT NOT NULL,
    plan_target_json   TEXT NOT NULL,
    original_value     TEXT NOT NULL,
    original_unit      TEXT,
    original_source    TEXT NOT NULL,
    original_document_id TEXT,
    corrected_value    TEXT NOT NULL,
    corrected_unit     TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX idx_paper_parameter_correction_paper ON paper_parameter_correction(paper_id);
```

> P1-1 语义(供 C2,本卡表结构已支持):重复纠错同一 param_key 时 `UPDATE corrected_value/unit/updated_at`、**`original_*` 保持首次值不变**(撤销回到 AI 原抽,而非上一次纠错值)。

### C. 惰性 store CRUD(签名)

```python
async def insert_parameter_correction(self, correction: PaperParameterCorrection) -> None: ...
async def update_parameter_correction_value(
    self, paper_id: str, correction_id: str, corrected_value: str,
    corrected_unit: str | None, updated_at: str,
) -> None: ...
async def get_parameter_correction(
    self, paper_id: str, correction_id: str,
) -> PaperParameterCorrection | None: ...
async def list_parameter_corrections(self, paper_id: str) -> list[PaperParameterCorrection]: ...
async def delete_parameter_correction(self, paper_id: str, correction_id: str) -> None: ...
```

### E. 统一判定器(签名)

```python
@dataclass(frozen=True)
class UserEvidenceRef:
    kind: UserEvidenceAction
    key: str   # fill_missing → prompt_id;correct_extracted → correction_id

def resolved_user_evidence_refs(
    record: PaperPlanRecord,
    corrections: list[PaperParameterCorrection],
) -> set[UserEvidenceRef]: ...
```

---

## 验收标准(给出可跑命令)

- [ ] `make check` 全绿(含新边界测试 + 向后兼容读回测试 + CRUD/级联单测);后端真测试,断言覆盖:invariant 四类组合、老 blob 读回归一化、CRUD 往返、三处级联删空纠错表、TTL orphan 清理、判定器 fill_missing/correct_extracted 双路(合成数据)
- [ ] `make export-schema && make verify-schema` —— evidence 契约变更被捕获,**无其他非预期 drift**
- [ ] `pnpm typecheck && pnpm lint && pnpm build` 绿(前端类型若从 schema 生成,3 个可空字段不得破坏 build;**本卡无 UI 改动、无截图**)
- [ ] `git diff --check` 通过(行尾/字节,decision 08)
- [ ] **隐私 grep 新代码干净**:无 `logger.exception` / `str(exc)` / `repr(exc)` / `exc_info`;纠错 value/unit/param_key 不出现在任何 log/error body;新增 SQL 错误只 log `type(exc).__name__`(对齐 522-B store)
- [ ] **diff 边界逐处核**:§D 三个清理/替换函数,挨着已合并 522-B 逻辑的改动逐处贴前后对比,证明**纯加一张表进级联、现有三表删除逐字不变、事务边界不变**
- [ ] 端到端惰性证明:全库无任何代码路径会写入 `paper_parameter_correction`(service/endpoint 均未落地);现有 upload / user-supply / reparse / ask / build_steps 行为零变化(跑对应现有测试全绿)

---

## 风险与注意点

- **对外契约变更**:PaperEvidenceEntryModel 进 GET /spec、/plan 响应。新增字段必须可空 + 默认 None + 向后兼容(老前端忽略新字段、老数据读回带 None→归一化)。这是 521-C 加 document_id/label 的同款可空扩展套路,不是破坏性变更。
- **向后兼容读回**:existing 库里已有 `user_supplied`(fill_missing)evidence blob;读回必须不炸、归一化正确。这是本卡最易翻处 —— 单测必须覆盖「老 blob 无 user_action 字段」读回。
- **级联触已合并 522-B 代码**:§D 是 schema-sync 必需的合并产物触碰(decision 13),同 522-B 自己扩 CleanupWorker 的先例。必须 diff 边界逐处核、原行为逐字不变。
- **惰性红线**:本卡端到端不得产生任何纠错;判定器的 correct_extracted 路径、CRUD、correction 表在本卡全靠单测合成数据驱动,无生产路径触发。若发现某现有校验/序列化因新字段而破坏,**停手报架构师**(禁兜底硬上)。
- **overlay 不可变红线**:`PaperSpec.parameter_table` 本卡与 C2 均不可变;冲突检测真值源保持不动。

---

## Stage 0 可落性 gate(Codex 实现前核,不符停手报架构师,禁兜底硬上)

1. `git fetch origin && git rev-parse origin/main` —— 报 HEAD;`git merge-base --is-ancestor <live f29e4a4> origin/main` 通过(允许 main 已合法前进,用 live 值)。
2. 确认本卡已随代码入 `docs/tasks/`(PM 预放,untracked=预期)。
3. 核现状与本卡 § 上下文一致(贴 RAW 定性):
   - `PaperEvidenceEntry` / `PaperEvidenceEntryModel` 现字段 = source/document_id/paper_section_id/equation_id/figure_id/excerpt/missing_param_prompt_id。
   - `CURRENT_SCHEMA_VERSION` 现 = 6(522-B 已 5→6)。
   - `delete_bundle` / `delete_expired_paper_bundles` / `replace_ready_bundle_with_source` 现级联/事务 = plan/spec/reparse_source 三表(本卡在此三处加一张表)。
   - GET /spec、/plan 现暴露 evidence list(对外变更面)。
4. **高风险假设 gate(核准才动)**:向 PaperEvidenceEntryModel 加 3 个可空默认 None 字段,**不破坏任何现有 validator / serializer / 消费方 / 现有测试**(逐一核 evidence 的现有消费点:validate_for_spec、build_steps evidence 校验、tuning 若消费 user_supplied evidence、对外序列化)。若任一破坏 → 停手报架构师。
5. **向后兼容读回 seam gate**:确认读回归一化能否干净插入(§ 接口契约 A 二选一在此定),报架构师采用哪个。
6. 任一不符 → 停手诊断(decision 15:卡/包写错 vs main 真不对 vs 同步动作漏做)。

---

## 给 Codex 的提示

- 走 feature branch(**git fetch 后从 origin/main 切**,不许 main 直推)。
- **卡随代码同 PR**(本卡 `git add` 进代码 PR);**索引收尾单独 PR**;**本代码 PR 不碰 `03_TASK_INDEX.md`**。
- PR:Codex 给标题 + 正文草稿 + `pull/new` 链接,PM 网页侧建 PR + squash merge。
- `make check` 全管道跑,禁拆 CI step 列;显式加 `make export-schema && make verify-schema`。
- 新字段加末尾;frozen dataclass 位置构造兼容;pydantic 新字段可空默认 None。
- 序列化复用现有已实证 wrapper;禁宽 catch / `str(value)` / fallback。
- RAW 取证/diff 贴对话、去行号、不收本机路径。

---

**版本**:v0.2(2026-07-02,GPT R1 + Codex R6 双审收敛,派 Codex 终版)
**作者**:Claude(架构师)
**前置 commit**:main 必须含 `f29e4a4`(Stage 0 用 `git merge-base --is-ancestor` 校验,允许 main 合法前进)
**入库改名**:入 `docs/tasks/task-522-c1-user-correction-contract-substrate-v0_2.md`
**审批级别**:GPT R1 设计审 + Codex R6 live 核双通过 → PM 拍 overlay 方向 + 可空扩展 + 级联知会(已拍)→ 派 Codex Stage 0 → 实现
**后继**:TASK-522-C2(纠错行为 + 端点 + 撤销 + 锁 + build_steps 简化 + 前端),C1 合并进 main 后起草
