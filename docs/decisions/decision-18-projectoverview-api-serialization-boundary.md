# 决策 18: ProjectOverview API serialization boundary

## 背景

TASK-310 PR #1 把 `ProjectOverview` 数据契约从 `features/overview/overview_schemas.py`(Pydantic)下沉到 `core/domain/project_overview.py`(纯 Python dataclass + Literal)。下沉时需要回答:既有 9 处生产引用是否一刀切改 core dataclass?

R0 起稿假设"一刀切",R1 GPT 抓出反例:API route / scripts / freeze test 必须保留 Pydantic 接口(FastAPI 序列化 / JSON schema 导出 / 字段约束守门),否则 schema 漂移 + 500 错误。

## 决策

按消费方分三类:

- **A 类(保留 Pydantic 接口)**:`api/routes/overview.py` / `scripts/export_overview_schema.py` / wrapper tests / freeze test
  - route response_model **必须**用 `ProjectOverviewModel`(Pydantic wrapper)
  - export script **必须**导出 wrapper schema(JSON 结构不变)
- **B 类(业务消费,改 core dataclass)**:`features/chunking/` / `features/explanation/` 等纯字段读取方,import 改 `from core.domain.project_overview import ...`
- **C 类(bridge)**:`features/overview/overview_schemas.py` 提供 `.to_domain()` + `.from_domain()`;`overview_service.py` 内部返回 core dataclass,API 层 `.from_domain()` 转回 Pydantic;同 feature 内部(`__init__.py` / `overview_service.py`)沿用 schemas import

## 不变量

- API 对外 JSON 字段名 / 类型 / 验证约束**字节级不变**(沿用 TASK-207 freeze 真值 `main_execution_flow max=10` / `key_files min=1` / `evidence min=1`)
- `ProjectOverviewSchema` alias 沿用(消费方 import 路径迁移期兼容)
- freeze test 加两层一致性 + round-trip,守门 dataclass 与 Pydantic wrapper 字段名 / 顺序 / 类型一致

## 关联

- 实施:TASK-310 PR #1(squash commit `453f280` / PR #90,2026-06-15)
- 修订:决策 16(overview_schemas 下沉触发条件 #2 已落地;本 chore PR 同步加 decision-16 实施记录)
- 关联:任务卡 D1-B / GPT R1 P0-2
