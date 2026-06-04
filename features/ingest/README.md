# features/ingest

UploadService 工程上传解析编排。

详见 `docs/02_ARCHITECTURE_OVERVIEW.md` 第 3 节。

`upload_service.py` 只依赖 core 接口和构造函数注入的 callable,不直接 import
`adapters/`。HTTP 同步路径先做 declared size 校验,读取 body 后再做 actual
size 兜底;通过后创建 `project_id` 并把长任务交给 BackgroundTasks。

后台 `process()` 捕获业务异常并写入 `ProjectStore.mark_failed(...)`,避免项目卡在
`parsing`。解压、分类、`.slx` / `.m` 解析和依赖分析都是同步重活,必须通过
`asyncio.to_thread()` 桥接,避免阻塞 event loop。

本 Task 不解析 `.mat`;`Project.mat_files` 固定填 `[]`。任何 `ParseError`
都会让整个 project 进入 `failed + parse_error`。
