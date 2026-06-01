# 20260601-04:`features/understanding/` 暂不作为顶层 feature

## 状态
✅ 决议

## 背景

v2.1 架构修订引入"教学理解中间层"(`ProjectGraph` + `TeachingUnit`)。

关于这一层的代码组织,有两个候选方案:

- **方案 A**:新增顶层 `features/understanding/`,与 `ingest` / `overview` / `chat` / `billing` 并列
- **方案 B**:不新增顶层 feature,把构建逻辑放在 `features/overview/` 内部模块

AI 二审建议方案 B,Claude 也倾向方案 B。本决策正式归档。

## 决策

**MCS 阶段不新增顶层 `features/understanding/`。**

- 数据结构(`ProjectGraph` / `TeachingUnit` / `SourceRef`)放在 `core/domain/`
- 构建逻辑放在 `features/overview/` 内部:
  - `project_graph_builder.py`
  - `teaching_unit_builder.py`
  - `schemas.py`
  - `citation_collector.py`

`features/overview/service.py` 的内部职责拆成:

```
ProjectOverviewService
  ├─ ProjectGraphBuilder
  ├─ TeachingUnitBuilder
  ├─ OverviewSchemaGenerator
  └─ CitationCollector
```

## 理由

1. **MCS 阶段不是独立用户用例**
   - 用户看到的入口:上传 / 查看导览 / 点击 block / 提问 / 导出
   - 没有"工程理解"按钮
   - `ProjectGraph` / `TeachingUnit` 是内部中间产物,不是产品功能

2. **减少 Codex 心智负担**
   - 新增顶层 feature 会让 Codex 在写代码时不确定"导览生成"与"工程理解"边界
   - 现有四大 feature(ingest / overview / chat / billing)已经够用

3. **避免过早抽象**
   - 等真实复用压力出现再抽出来,而不是想象中的复用

4. **通过清晰内部模块保留重构边界**
   - 即使在 `features/overview/` 内部,也用独立文件(`project_graph_builder.py` 等)承载
   - 未来真要抽出独立 feature,只是 `git mv` 几个文件,不是大重构

## 影响范围

- 02 架构总览 v2.1:目录结构按本决策
- 03 Task 索引 v2.1:TASK-107(ProjectGraph + TeachingUnit 基础构建器)产出物放 `features/overview/`
- 不影响 core/domain 数据结构
- 不影响其他 feature

## 何时升级为顶层 feature

满足**任一**条件,即可重新讨论是否抽出独立 feature:

1. `ChatService` 需要频繁主动重建 `ProjectGraph`(而非复用 overview 已构建的)
2. 导出报告 / 答辩准备 / 课程知识点映射 多处复用 `TeachingUnit`
3. understanding 相关代码超过 500-800 行
4. 出现跨工程对比 / 工程质量分析 / 参数风险分析等新能力

## 是否可逆

✅ 可逆。

未来如需抽出独立 feature,只需:
- `git mv features/overview/project_graph_builder.py features/understanding/`
- `git mv features/overview/teaching_unit_builder.py features/understanding/`
- 更新 `features/overview/service.py` 的 import 路径
- 更新文档

预计 1-2 小时即可完成迁移。

---

**决策日期**:2026-06-01
**决策人**:Claude(架构) + PM,基于 AI 二审建议
**关联文档**:01_PROJECT_CONSTITUTION.md v2.1 / 02_ARCHITECTURE_OVERVIEW.md v2.1
