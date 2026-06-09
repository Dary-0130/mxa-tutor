# 决策 16: overview_schemas 跨 feature 引用暂不重构

## 背景

Week 3 完成后架构审计发现 `features/overview/overview_schemas.py` 被三个 feature 引用:

- `features/overview/` (自身)
- `features/chunking/` (读 ProjectOverview schema 构造 chunk source_text)
- `features/explanation/` (读 ProjectOverview schema 构建 EvidencePack)

初步判断为"跨 feature 公共契约应下沉到 core/"。

## 决策

**暂不搬迁。**

## 理由

1. chunking 和 explanation 引用的是纯数据定义(Pydantic model),不是行为,不构成真正的循环依赖
2. overview_service → chunking_service 是单向行为调用,数据流和控制流方向一致
3. 搬迁代价高:所有 import 路径 + freeze 测试 + 06_OUTPUT_CONTRACTS.md + export 脚本 + schema JSON 全部要同步改(决策 13 同步清单)
4. 对产品上线和前端开发零影响

## 重新评估触发条件

- overview_schemas 新增非 overview 专属的 schema class(说明它已不是 overview 的东西)
- 第四个 feature 开始引用 overview_schemas
- 需要对 features/ 做包级别拆分或独立部署

任一触发时重新评估是否下沉到 core/domain/ 或 core/schemas/。
