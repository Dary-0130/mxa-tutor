# 决策 17: overview 列表字段超长时降级截断

## 背景

LLM 生成 ProjectOverview 时偶发输出 list 字段超过 Pydantic schema `max_length`
(典型:`knowledge_points` max=6,LLM 给 8 条)。此前 Step 2 直接抛
`ValidationError` → `OverviewGenerationError` → 502,用户导览页打不开。

## 决策

`overview_service._parse_and_validate` Step 2 引入降级截断:

- 首次 `model_validate` 失败时,**仅当**所有错误都是顶层 list 字段的
  `too_long` 类型,截到 `max_length` 后重试一次
- 其他任何错误类型(嵌套校验、字符串超长、`too_short`、字段缺失)原样抛
  `OverviewGenerationError`,不尝试救
- 截断顺序:取 `list[:max_length]`(LLM 通常按重要性排序输出,前 N 条即重要 N 条)
- 截断触发时打 INFO 日志(字段名 + 原长度 + 目标长度),不打字段内容(隐私)

## 拒绝的替代方案

- **改 prompt 强约束最多 N 条**:LLM 不一定严格守,仍有概率超;留给下任作为减频措施,
  本决策仅做兜底
- **抬高 schema max_length**:触发决策 13 全清单同步(freeze test + 边界测试 +
  06_OUTPUT_CONTRACTS + JSON schema + prompt yaml),代价远大于本兜底;且产品未要求

## 不变量

- schema `max_length` 是产品定义的硬上限,本决策不改变这个语义
- 仅在 LLM 输出"略超"时降级,不放宽对外契约
- 字符串字段超长仍 fail(末尾截断风险高,语义可能残缺)
- 嵌套 list 元素校验失败仍 fail(不是长度问题)

## 重新评估触发条件

- 截断 INFO 日志在生产环境频繁触发(> 10%) → 改 prompt 减频
- 用户反馈"内容明显被截"(罕见) → 产品评估是否抬 max_length
