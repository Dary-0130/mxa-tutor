# 决策 19: TeachingUnit cache record state contract

## 背景

TASK-310 PR #2 起 TeachingUnit lazy 生成 + 缓存。Store ABC v0.1 起稿返回 `TeachingUnit | None`,GPT R1 P0-4 抓出反例:无法表达"正在生成中"/"失败可重试"/"失败永久"状态,Service 拿不到精确分支信息。

## 决策

Store ABC 返回 `TeachingUnitCacheRecord`(stateful)dataclass:

```python
@dataclass(frozen=True)
class TeachingUnitCacheRecord:
    cache_key: CacheKey  # 8 元组
    state: Literal["generating", "ready", "failed_retryable", "failed_permanent"]
    unit: TeachingUnit | None
    error_code: str | None
    retry_count: int
    expires_at: int
```

Service 按 `state` 分支处理:
- `generating`:他方占位中,wait timeout 后 503
- `ready`:返回 `unit`
- `failed_retryable`:`retry_count < MAX_RETRIES` 才重试;否则升级 `failed_permanent`
- `failed_permanent`:直接 502
- expired:删除 record,重新生成

`MAX_RETRIES = 3`(MCS)。

## 不变量

- state 转移单调:`generating → ready` / `generating → failed_retryable` / `failed_retryable → failed_permanent`
- `mark_ready` / `mark_failed` 必须基于已存在的 `generating` record(否则违反状态机)
- `begin_generating` 原子占位(SQLite UNIQUE + asyncio.Lock 双层)
- record `unit` 仅在 `state == "ready"` 时非 None

## 关联

- 实施:TASK-310 PR #2(2026-06-15)
- 关联:任务卡 D10(并发去重三层)/ D12(failed_retryable 缓存)/ D15(Store ABC 归属)/ GPT R1 P0-4
