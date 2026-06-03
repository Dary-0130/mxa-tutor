# api

FastAPI 后端。所有 HTTP 端点在此层装配,通过 feature service 调用 core / adapter,
不直接调 LLM(详见 `docs/02_ARCHITECTURE_OVERVIEW.md` § 3 目录结构 / § 7 API 分层约束)。

## 模块结构

- `main.py` — FastAPI app 工厂(`create_app()`)+ 模块级 `app` 实例 + lifespan 钩子
- `dependencies.py` — DI 容器,`get_settings()` 返回 `AppSettings` 单例
- `routes/health.py` — `GET /health` 健康检查端点(readiness check,不查外部依赖)
- `schemas/health.py` — `HealthResponse` Pydantic 响应模型(`extra="forbid"` 锁契约)
- `middleware/error_handler.py` — minimal ERROR_MAP(8 handler,响应体 shape `{"error", "message"}`);命名沿用历史目录,实为 exception handler 挂载点,不是 ASGI middleware

## 启动

开发模式(自动重载,端口 8000):

```bash
make dev
```

或直接:

```bash
uvicorn api.main:app --reload --port 8000
```

Windows / OneDrive / 中文路径 / WSL 用户:`uvicorn[standard]` 的 watchfiles 自动重载在某些环境下不稳定。如发现保存代码后 reload 不触发,临时设环境变量:

```bash
export WATCHFILES_FORCE_POLLING=true
uvicorn api.main:app --reload --port 8000
```

或直接关闭 reload 验证业务功能:

```bash
uvicorn api.main:app --port 8000
```

## 测试

```bash
pytest tests/api/ -v
```

## 后续 Task 扩展点

- TASK-202:在 `routes/upload.py` 实现上传 + 解析 API;禁止在 route 内 `try/except` 翻译业务异常(直接抛 `MxaError` 子类,让 ERROR_MAP 处理)
- TASK-203:在 `routes/overview.py` 实现导览端点
- TASK-205:在 `routes/chat.py` 实现问答端点
- TASK-206:在 `middleware/error_handler.py` 追加剩余 9 项 handler(`LLMError` 5 子类 + `ParseError` 2 + `Quota` + `Evidence`)+ 404/422 中文化,不改本 Task 锁定的响应体 shape
