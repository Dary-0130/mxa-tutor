# adapters/storage

SQLite 存储 / 文件系统存储 / 沙箱。

详见 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节。

TASK-202 临时前移 `InMemoryProjectStore`,用于 upload/status 在 TASK-204 SQLite
落地前共享状态。它实现 `ProjectStore` 的 7 个生命周期方法:

- `create_pending`
- `mark_ready`
- `mark_failed`
- `get_status_view`
- `get_project`
- `list_expired`
- `delete`

该实现基于进程内 dict 和 `asyncio.Lock`,只适用于单 worker。多进程下不同
worker 看不到彼此的内存状态,会导致刚上传的 `project_id` 查询 404。
