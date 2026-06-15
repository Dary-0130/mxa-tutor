# 决策 21: EvidencePack consumption boundary

## 背景

TASK-310 PR #2 起 TeachingUnitBuilder 时,候选方案是 EvidencePack slice(从 TASK-308 ExplanationPack 抽取 target 范围的 evidence 给 TeachingUnitBuilder 用)。GPT R1 P1-3 抓出反例:这需要 `features/overview/_teaching_unit_builder.py` import `features/explanation/_evidence_*`,违反"跨 feature 私有 import 禁止"(K_36 同源)。

## 决策

TeachingUnitBuilder **不** import `features/explanation/*` 或 EvidencePack 私有结构。

Builder 仅依赖:
- `core.domain.*`(SourceRef / ProjectGraph / TeachingUnit / TeachingUnitRef)
- `core.interfaces.llm_provider.TextProvider`
- prompt yaml + 自身 prompt 构造逻辑

EvidencePack slice 留 **X8 候选** — 若未来确认需要,另起 task 把 EvidenceBuilder 公开 contract 提到 `core/interfaces/`(类似 ProjectOverview 下沉 core),让 Builder 通过 ABC 消费,而非 import 私有实现。

## 不变量

- features/overview/ ↛ features/explanation/(单向禁止)
- features/explanation/ ↛ features/overview/_teaching_unit_*(双向禁止)
- 三层并存(EvidencePack / TeachingUnit / ExplanationPack)不互相消费私有结构,只在 core/ 公开 contract 层共享
- 自动升 R2 #5 守门:任一双向跨 feature 私有 import 触发立停

## 关联

- 实施:TASK-310 PR #2(2026-06-15)
- 关联:任务卡 D3(三层并存)/ GPT R1 P1-3 / 自动升 R2 #5 / X8 候选
