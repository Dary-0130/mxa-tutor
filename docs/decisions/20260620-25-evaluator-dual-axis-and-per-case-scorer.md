# 决策 25:evaluator 双轴状态 + per-case scorer + case-boundary 异常封装与归因分离 + judge 留 v0.2 多 case

> **编号**:25
> **日期**:2026-06-20
> **作者**:Claude(架构师,第 49 任)
> **拍板**:PM Dary(D-501~D-512 全拍闭环)
> **关联**:决策 12 v0.4(双 AI 互审工艺)/ 决策 15(diagnose-before-fix)/ 决策 19(TeachingUnit cache record state 双轴范例)/ 决策 21(EvidencePack consumption boundary 不同域)/ 决策 22(paper 红线)
> **触发**:TASK-503 v0.2.4 evaluator 判分改造期发现 v0.2.3 旧 evaluator 单轴 `ExecutionStatus = Literal["succeeded", "blocked_known_defect"]` 把"判分错"与"真异常"混淆,且 E2 集合相等死锁动态 prompt_id;架构师 GPT 四轮 + PM 全拍后归并为长期 decision
> **状态**:🔲 起草中(本版 v0.1,随 TASK-503 v0.2.4 + TASK-500 v0.2.2 同期入仓)

---

## 1. 上下文

paper-to-model evaluator 在 TASK-502 v0.2 落地时只支持单轴 `ExecutionStatus = Literal["succeeded", "blocked_known_defect"]`,设计假设是"production case 阻塞 = 已知缺陷登记;否则 succeeded";verdict 字段在 CSV 留空(`verdict=None` 传入)。

TASK-503 v0.2.4 evaluator 判分改造前夜暴露三个问题:

1. **判分错与真异常混淆**:旧 `blocked_known_defect` 实际仅 catch `PaperPlanGenerationError + reason ∈ KNOWN_BLOCKED_FAILURES`,merge / serialization / provider / IO 异常都直接 crash evaluator 主循环(取证 16 § B2 实测 `run_paper_eval.py` line 84 / 170 / 181 三处 catch 位置)。判分错(规则失败)与真异常(代码 / IO / 资源)归类无法区分。
2. **动态 prompt_id 死锁集合相等**:旧 `_compute_e2`(取证 16 § B2 lines 333-372)绑 `response_ids == expected_ids + len(user_mappings) == len(expected_ids)` 集合相等;production `prompt_id = f"MISS-{index:03d}"` 顺序由 LLM 决定(取证 15 + 16 § B2 line 178 直接读 fixture prompt_id)→ fixture 固定 ID 与运行期 ID 不齐 → merge 抛 `parameter_name_mismatch` → E2 自动 N/A。
3. **judge / 漏报盲评 v0.1 单 case 不适用**:v0.1 单 case 固定 fixture,judge 评分波动大、不可重现;但 v0.2 多 case + 开放世界识别完整性场景需要 judge。两个口径需要长期分清,否则 v0.1 死规则口径会被 v0.2 误用,或 v0.2 多 case 退化为 v0.1 死规则。

本决策固化"evaluator 状态语义 + per-case scorer 分派原则 + case-boundary 异常封装规则 + judge 适用边界"四组长期口径。

---

## 2. evaluator 双轴状态

### 2.1 双轴定义

```python
ExecutionStatus = Literal["succeeded", "case_failed"]
Verdict = Literal["pass", "partial", "fail", "not_evaluated"]
```

笛卡尔积理论 2 × 4 = 8 种组合;**不变量约束有效 5 种**:

| execution_status | verdict | 语义 | 出现条件 |
|---|---|---|---|
| succeeded | pass | case 跑完,全部规则通过 | 死规则全 pass / 软指标达阈 |
| succeeded | partial | case 跑完,部分规则通过(只 material 类 case) | 既有 metrics 部分达阈 |
| succeeded | fail | case 跑完,确定性规则失败 | R1a/R2/R3/R4/R5 任一 fail / R4/R5 前置失败主动跳 merge |
| case_failed | not_evaluated | case 中途真异常,无确定性 verdict | merge 抛错 / IO / serialization / provider / fixture 损坏 / 产物缺失 |
| (合法保留) | — | — | — |

**不变量**:
- `execution_status == "case_failed" → verdict == "not_evaluated"`(case 中途异常不写 pass / partial / fail,因没跑完所有规则)
- `execution_status == "succeeded" → verdict ∈ {"pass", "partial", "fail"}`(case 跑完必有确定性 verdict)
- `verdict == "not_evaluated" → execution_status == "case_failed"`(反向不变量)

### 2.2 不允许的组合

| execution_status | verdict | 拒绝原因 |
|---|---|---|
| succeeded | not_evaluated | case 跑完应有确定性 verdict;无法 succeed 而无判定 |
| case_failed | pass / partial / fail | case 中途异常,无证据写确定性 verdict;强写会让"真异常"伪装为判分结果 |

### 2.3 `blocked_known_defect` 历史读取映射

`blocked_known_defect` 不再作新 execution 状态;历史 CSV 读取(如旧 evaluator 跑过 case)遇到 `blocked_known_defect` → 自动映射 `case_failed + not_evaluated`,门槛不通过。

理由:历史 `blocked_known_defect` 实际意为"已知 production 缺陷阻塞 case",但该归因在新口径下属于真异常类(catch domain exception → case_failed),不能伪装为 pass / partial。

### 2.4 verdict 自动汇总

新建 `compute_verdict(rule_results) -> Verdict` 汇总函数:

```python
def compute_verdict(
    *,
    case_kind: CaseKind,
    execution_status: ExecutionStatus,
    rule_results: dict[str, Any],
) -> Verdict:
    if execution_status == "case_failed":
        return "not_evaluated"
    # case_kind 分派
    if case_kind == "missing_param":
        # 五条死规则全自动:全 pass → pass;任一 fail → fail;无 partial
        rules = ["r1a_pre", "r1a_post", "r2", "r3", "r4", "r5", "e1"]
        if all(rule_results[r] == "pass" for r in rules):
            return "pass"
        return "fail"
    if case_kind == "material_to_plan":
        # 既有 metrics + R3 改名(行为不变):pass / partial / fail
        return _compute_material_verdict(rule_results)
    raise ValueError(f"unknown case kind: {case_kind}")
```

---

## 3. per-case scorer 分派原则

### 3.1 case_kind 分派的必要性

material_to_plan 与 missing_param 两类 case 的真值源、判分维度、人工介入度本质不同:

| 维度 | material_to_plan | missing_param |
|---|---|---|
| 真值源 | golden JSON(expected_paper_spec / expected_model_generation_plan) | source_doc + R2 真值源 fact table |
| 判分指标 | A1 / C2 / C3 / D1 / E1 + R3(原 E2 改名)+ 人工 A2 / C1 | R1a-pre / R1a-post / R2 / R3 / R4 / R5 + E1 |
| partial 允许 | 是(指标可部分达阈) | 否(五条死规则全 pass 才 pass) |
| 人工介入 | A2 / C1 维度仍人工 | 全自动,无人工 |
| 漏报盲评 | 不适用(material 是"plan 应包含什么"明确 oracle) | 不适用 v0.1(漏报盲评归 v0.2 多 case + judge) |
| 漏报判断 | golden 数量 == actual 数量隐含 | R2 不判漏报;只判冲突 + 幻觉 |

强制单一 scorer 跑两种 case 会引入分支 if/else 漂移,长期维护困难。per-case scorer 分派是结构性必要。

### 3.2 evaluator 入口分派

`run_paper_eval.py::_run_case` 在 case_kind 推断后,按 case_kind 分派给:

- `_compute_material_metrics(...)`:material 既有逻辑保留,R3 改名(无 user_supplied mapping)
- `_compute_missing_rules(...)`:missing 五条死规则 + E1

两个分派器输出格式统一为 `rule_results: dict[str, "pass" | "partial" | "fail" | "n/a"]`,然后传给 `compute_verdict` 汇总。

### 3.3 production helper 独立性原则

evaluator 的 R1a-post resolved 判据**刻意独立写代码**,不调 `features/paper/paper_plan_helpers.py::resolved_prompt_ids()`(GPT 明确:同 helper 会让生产评测同错同过)。判据复用 `paper_plan_helpers` 五条逻辑,但代码独立 + 测试独立。

---

## 4. case-boundary 异常封装与归因分离

### 4.1 异常封装原则

对**主动执行、可归属单 case 的公开领域异常**,在 case 边界封装并写结构化结果,**不在 artifact 写出前中断**:

```python
async def _run_case(case_dir: Path, services, root) -> CaseResult:
    failure_stage: str | None = None
    exception_type: str | None = None
    error_code: str | None = None
    try:
        # ... actor 调用 ...
        # ... adapter 注入 ...
        # ... merge ...
        # ... 判分 ...
    except (
        PaperPlanGenerationError,
        PaperUserSupplyError,
        StoreError,
        # 其他可归属单 case 的 domain exceptions
    ) as exc:
        failure_stage = "<判分前最近完成阶段>"
        exception_type = type(exc).__name__
        error_code = getattr(exc, "reason", None)
        execution_status = "case_failed"
    finally:
        # 始终写 case_result + actual artifacts + 规则明细 + failure_stage
        _write_case_result(case_id, actual_artifacts, rule_results, failure_stage, exception_type, error_code)
```

**不 catch**:
- `BaseException`(KeyboardInterrupt / SystemExit 直接上抛)
- 配置 / 依赖 / 资源 / 编程类致命异常(`AppSettings load failed` / `ImportError` / `MemoryError` 等)— 这些是 run-level 问题,case 边界不应吞掉,需 run-level 诊断

### 4.2 归因分离

异常类型 / 错误码**只描述症状,不自动证明根因**:

| 症状 | 可能根因 |
|---|---|
| `PaperUserSupplyError("parameter_name_mismatch")` | (1) fixture 命名漂移(归 TASK-500 v0.2.x 修);(2) production prompt builder 行为变化(归 TASK-501/502/503);(3) evaluator adapter 注入缺陷(归 TASK-503 v0.2.4) |
| `PaperPlanGenerationError("missing_binding_not_found")` | (1) PlanComposer prompt 漏 sentinel(归 TASK-503 R6);(2) fixture 期望与 production v0.2 prompt 不齐(归 TASK-500 微补丁);(3) MissingDetector LLM 输出漂移 |
| `StoreError("paper_bundle_incomplete")` | (1) SQLite 事务 rollback 失败;(2) fault injection 触发;(3) bundle store contract 缺陷 |

evaluator **不主观判定根因**,只记录症状 + failure_stage;根因留架构师 / PM diagnose-before-fix(决策 15)。

### 4.3 fixture 阻塞使用边界

旧 `blocked_known_defect` 工艺允许 fixture 名义 = "已知 production 缺陷阻塞 case",新口径下**仅在以下三类证据成立时使用**:

1. **独立 fixture 一致性检查**通过(fixture 自身 schema / 命名 / 引用闭合,与 production 无关)
2. **经批准 case 级缺陷登记**(PM 拍板某 production 缺陷阻塞某 case,登记缺陷 ID + 修复 task + 影响范围)
3. **等价可复核证据**(多次独立运行复现同症状,且独立工具 / 独立审查者验证)

**证据不足**:记 `case_failed + not_evaluated` + failure_stage,**不通过门槛**;不允许 evaluator 兜底掩盖 production 行为。

### 4.4 新增领域异常审查 evaluator coverage

新增 paper 域 domain exception(如 `PaperTuningError` 等)→ 同期审查 evaluator case-boundary catch list + 对应测试是否覆盖;**只有新增不同结果语义时**才扩 `Verdict` / `ExecutionStatus` 枚举(避免每个异常新增枚举值导致状态爆炸)。

---

## 5. judge 留 v0.2 多 case;v0.1 硬契约用确定性死规则

### 5.1 判分手段适用边界

| 手段 | 适用 case 性质 | 评分稳定性 | 复现性 |
|---|---|---|---|
| 死规则(R1a/R2/...) | 固定 oracle 可枚举(给定文档 + 给定参数集合)+ 硬契约 | 100% 稳定 | 完全复现 |
| 软指标阈值(A1/C2/C3/D1) | 集合相似度 + 部分通过 + 部分 oracle 已知 | 高(浮点阈值)| 高(seed 锁定)|
| 人工评分(A2/C1) | 主观判断 + 部分 oracle | 低(评审者间一致性需校准)| 中 |
| judge LLM 评分 | 开放世界识别完整性 + 无可靠客观 oracle + 多 case 统计稳定 | 低(LLM 输出方差)| 低(需多次平均)|

### 5.2 v0.1 任务硬契约用死规则

paper-to-model v0.1 固定单 case + 固定 fixture + 固定文档,**漏报判断不在 v0.1 范围**(决策 22 § 10.4)。

本任 missing case 用 R1a-pre / R1a-post / R2(冲突 + 幻觉)/ R3(来源真实性)/ R4(一对一基数)/ R5(全链 canonical 一致)五条死规则 + E1。

material case 用既有 metrics + R3 改名(行为不变)。

**不引入 judge**;不引入 R1b(产品级 resolved 二次校验,本任 R1a-pre/post 已覆盖);不引入漏报盲评。

### 5.3 v0.2 多 case 何时引入 judge

未来 v0.2 多 case 引入 judge 的**前置条件**(必须**全部**满足):

1. case 明确承担**开放世界识别完整性**职责(例如"对未见过的论文,SUT 应识别哪些缺参"— 无固定 oracle)
2. **无可靠客观 oracle**(无 R2 真值源可声明 conflict / hallucination 完整集合)
3. judge LLM 输出经过统计稳定性验证(多次独立运行评分方差可控)
4. judge 评分**只用于探查 / 排序 / 软指标**,**硬契约始终由确定性规则验证**

引入路径:走架构升级类决策(R1 + R6 + PM 三道),独立 task 落地 judge prompt + judge 评测脚本 + judge 评分稳定性验证集。

### 5.4 反向约束:硬契约始终由确定性规则验证

任何场景下,以下硬契约**始终用确定性规则验证**(即使引入 judge 后):

- 来源真实性(R3:user_supplied evidence 不带 locator-excerpt;user 值不在 document_extracted 中)
- 写回正确性(R1a-post:value 逐字 / source 标 USER_SUPPLIED / 新增 1 条 evidence / 旁损无)
- 一对一基数(R4:prompts == bindings == mappings 数 + canonical 唯一)
- 全链 canonical 一致(R5:运行期 prompt / response / binding / mapping 全链 parameter_name 逐字一致)

judge 评分**不替代**上述死规则;judge 只补充开放世界识别完整性维度。

---

## 6. 范围边界

### 6.1 本决策不涵盖

- production code 行为修订(`paper_user_supply_service.py merge` / `paper_plan_helpers.resolved_prompt_ids` 等);production 内部行为遵循各自 task 工艺(TASK-501/502/503)
- evaluator 内部具体函数签名 / 文件命名 / 测试组织(归 TASK-503 v0.2.4 § 12 文件真值表 + § 13 阶段 6)
- 决策 19 TeachingUnit cache record state contract(那是 cache record 域,本决策是 evaluator state 域;两个域不同)
- 决策 21 EvidencePack consumption boundary(那是 explanation feature 域;本决策是 evaluator 域)

### 6.2 本决策覆盖

- evaluator 状态枚举的语义规范(双轴 + 不变量)
- per-case scorer 分派的结构性原则
- case-boundary 异常封装规则(catch 边界 + finally 写入 + 归因分离)
- judge / 死规则 / 软指标 / 人工评分四种手段的适用边界

### 6.3 与既有决策的关系

- **决策 12 v0.4**(双 AI 互审):本决策走 R1 GPT 审 + R6 Codex 实施 + PM 拍板三道工艺
- **决策 15**(diagnose-before-fix):evaluator case_failed 时停手 + 报根因,不自动 fix
- **决策 19**(TeachingUnit cache record state):cache record 域的双轴范例;本决策 evaluator 双轴在结构上参考(`state` × `verdict`),语义独立
- **决策 21**(EvidencePack boundary):验证"不同域用不同 schema"的原则同样适用于 evaluator state vs cache record state
- **决策 22**(paper 红线):v0.1 任务硬契约 + v0.2 多 case + judge 留 v0.2 的边界与决策 22 § 10.4 一致

---

## 7. 验收(本决策入仓时)

- [ ] decision 文件入仓 `docs/decisions/20260620-25-evaluator-dual-axis-and-per-case-scorer.md`
- [ ] TASK-503 v0.2.4 § 17 决策日志加 D17-D22 共 6 项,引用本决策
- [ ] TASK-503 v0.2.4 § 14.7 / § 15 / § 16 / § 17 文字与本决策 § 2-§ 5 字面闭环对齐
- [ ] TASK-503 v0.2.4 实施后 evaluator code 行为闭环(`tests/eval/test_paper_eval_dual_axis_status.py` 覆盖 § 2.1 五种合法组合 + § 2.2 拒绝组合 + § 2.3 历史读取映射)

---

## 8. 修订历史

- v0.1(2026-06-20):架构师起稿(第 49 任接手);PM Dary D-501~D-512 全拍后归并;随 TASK-503 v0.2.4 + TASK-500 v0.2.2 同期入仓;关联 GPT 四轮审 + 取证 14/15/16 全链字面证据
