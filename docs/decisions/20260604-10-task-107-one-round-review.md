# 20260604-10:TASK-107 一审 1 轮临时降级决议

## 状态

✅ 决议(临时,本 Task 个例,不变更宪法 § 5 清单)

## 触发原因

宪法 § 5 第 4 节"何时找 AI 二审复审"列了 6 个核心二审 Task:
**101 / 102 / 104 / 107 / 205 / 304**。其中 TASK-107 在 onboard 时被描述为
"ProjectGraph + TeachingUnit 基础构建器",复杂度对标 task-104(项目第一个攻击面 P0)。

第八任架构师 onboard 后实地核查 03 索引 line 99-103,发现 TASK-107 验收点
**只列 ProjectGraph**,不列 TeachingUnit。结合 02 § 2 数据流"TeachingUnit 才用 LLM"
+ 03 索引"本 Task 不调用 LLM",唯一一致解读是 **本 Task 仅做 ProjectGraph 构建器**,
TeachingUnit 推到 Week 2 由 LLM Task(TASK-203 或新拆 110)处理。

PM 拍板按此调整。范围缩小后,TASK-107 复杂度降至接近 task-103 / task-105 一审级别
(文档 1472 行,代码 7 个文件总 870 行,测试 8 个文件总 1058 行)。

## 决策

**TASK-107 本次实施仅走 GPT 一审 1 轮,不走二审 2 轮**。

理由:

1. 实际范围(仅 ProjectGraph 构建器,纯结构化转换无 LLM)比"核心二审"标准描述的
   复杂度低
2. 与 task-103(也是核心结构化任务)对标更准,task-103 走一审已通过 main
3. 若 GPT 一审给出"重大异议"(改 dataclass / 引入新依赖 / 推翻范围拍板),则
   自动升 round 2

## 实际结果

GPT 一审 1 轮反馈:**条件通过,不建议重写大纲,也不建议升 round 2**。给出 12 条
工程精细化建议,架构师全部采纳,落地为 task-107.md v1.0 的接口契约硬约束:

- 节点 ID 语法硬契约 + 私有 helper + round-trip 测试
- 大小写保留(node_id 不 lowercase)
- 下游 TeachingUnitBuilder target_id 必须代码注入校验
- execution_flow 只用 CALLS + LOADS_DATA(排除 SIGNAL_FLOWS + BELONGS_TO)
- DFS reverse postorder + gray/black 环检测
- 边方向 4 条硬契约
- 内部 `_BuildDiagnostics` 诊断机制
- entry_points 启发式优先级 H2 > H1 > H3 > H4
- CALLS v0.1 文件级,不做 function symbol 消歧
- unresolved_symbols 4 类精确定义
- Subsystem 不与 Block 重复建模
- block metadata key namespacing

实施结果:Codex 实施完成,221 测试 passed,4 个真实工程跑通无 circular,
review 全过,PR #27 已合并 main(commit `e7d2e22`)。

## 终止条件

本决策**仅适用于 TASK-107 本次实施**。后续核心二审 Task(205 / 304)默认仍按
宪法 § 5 二审 2 轮处理。

若未来出现类似"核心 Task 范围实施时缩小"的情形,可参考本决策的判定逻辑:

1. 实地核查 03 索引验收点 vs Task 名 / 开场白描述,确认实际范围
2. PM 拍板范围调整后,评估调整后复杂度是否仍达"核心"级
3. 复杂度降级,且 GPT 一审无重大异议,可一审通过;否则升 round 2

## 与其他决策的关系

- **决策 04**(理解层不抽顶层 feature):TASK-107 缩到仅 ProjectGraph 构建器后,
  TeachingUnit 自然落入 Week 2 features/overview/ 内部模块,与决策 04 兼容
- **决策 09**(架构师必须实地核查):本决策的触发就是第八任实地核查 03 索引
  发现的范围矛盾,**纪律 1 在 TASK-107 的实战应用**
- **宪法 § 5**(核心二审清单):本决策**不修改宪法**,仅作为 TASK-107 个例的临时
  降级。宪法 § 5 清单保持 101 / 102 / 104 / 107 / 205 / 304

## 一句话总结

**核心 Task 实施时范围实际缩小,经实地核查 + PM 拍板,可临时降级为一审 1 轮;
本次 TASK-107 已按此路径完工,质量未受影响**。

---

**版本**:v1.0
**日期**:2026-06-04
**作者**:Claude(架构师,第八任)
**关联宪法版本**:v2.1(冻结,不修改)
**关联决策**:`docs/decisions/20260601-04-*.md`(理解层位置)/ `20260603-09-*.md`(实地核查纪律,触发本决策)
**关联 Task**:TASK-107(实施完成,commit `e7d2e22`)
**触发事件**:第八任 onboarding 实地核查 03 索引发现范围矛盾(2026-06-03)
