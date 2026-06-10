# 决策 13: schema 约束改动必须列出全部同步文件

## 背景

PR #58 改了 overview_schemas.py 的 3 个约束值(min_length/max_length),
CI 连挂三轮才发现 test_schema_freeze.py、test_overview_schemas.py、
06_OUTPUT_CONTRACTS.md、project_overview.schema.json 没同步。

## 规则

凡改动 `*_schemas.py` 或 `core/interfaces/*.py` 中的 Pydantic Field 约束
(min_length/max_length/ge/le/Literal 枚举值),PR 任务文档**必须**列出以下同步清单
并逐项确认:

```text
□ 对应的 test_schema_freeze.py 期望值
□ 对应的 test_*_schemas.py 边界测试数据
□ docs/06_OUTPUT_CONTRACTS.md 相关描述
□ schemas/*.schema.json 相关字段
□ 如涉及 project_type Literal: core/prompts/*.yaml + docs/05_EXPLANATION_STYLE_GUIDE.md
```

Codex 完工报告里必须贴这些文件的 diff。缺任何一项 = 未完工。

## 理由

freeze 测试和 schema JSON 是项目的"契约守门",改了源不同步守门等于绕过了守门。
这轮多花了 3 轮 CI 修复,耗时 ~40 分钟。
