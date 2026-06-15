# 决策 20: source_version 算法

## 背景

TeachingUnit cache_key 8 元组含 `source_version`,用于在 SourceRef / ProjectGraph schema 升级时自动失效旧缓存(决策 14 同源)。算法候选:

- A. `graph_hash`(全图哈希):每次 graph 微变都失效,性能差 + 命中率低
- B. `project.updated_at`:用户每次重新上传都失效,但与 SourceRef schema 变化无关
- C. **常量 `SOURCE_VERSION = "v1"`**:跟随 SourceRef / ProjectGraph schema 升级人工 bump

## 决策

选 C:`SOURCE_VERSION = "v1"` 模块常量,挂 `features/overview/_teaching_unit_service.py`。

未来 SourceRef 或 ProjectGraph 加字段时,**人工** bump 到 `"v2"`(在对应 task 起稿时拍),所有旧缓存自动失效,重新生成。

## 不变量

- `source_version` 不算 graph hash(性能 + 命中率)
- 不挂 `project.updated_at`(用户操作不该触发 LLM 重新生成)
- bump 跟随 SourceRef / ProjectGraph schema 变化,不跟随业务逻辑变化
- 配套决策 14:schema 变更同步清单加 `SOURCE_VERSION bump`

## 关联

- 实施:TASK-310 PR #2(2026-06-15)
- 关联:任务卡 D7(cache_key 8 元组)/ D14(source_ref 变更失效)/ GPT R1 H5(隐藏决策)
