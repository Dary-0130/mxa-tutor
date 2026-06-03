"""FastAPI app 工厂与模块级入口。

uvicorn 通过 ``uvicorn api.main:app`` 加载模块底部的 ``app`` 实例。

lifespan 设计原则(TASK-201 + 后续 Task 共同约束):
1. startup 只做轻量 fail-fast(本 Task:加载 ``AppSettings`` 验证 ``.env``)
2. 重任务用 ``BackgroundTasks`` 或 service 层异步初始化,不在 lifespan 内做
3. 未来 lifespan 一旦初始化真实资源(DB pool / 临时目录 / 后台清理 worker),
   必须用 ``AsyncExitStack`` 或显式 try/cleanup 保证"已初始化资源在 startup
   中途失败时也被清理",不能假设 ``yield`` 后 shutdown block 必然执行
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifecycle。"""
    _ = app
    settings = get_settings()
    logger.info(
        "Application startup: db_path={}, upload_dir={}",
        settings.db_path,
        settings.upload_dir,
    )
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """构造 FastAPI app 实例。

    description 字符串(含 em-dash ``—``)从 ``pyproject.toml`` 的
    ``[project].description`` 复制,保持字面一致。
    """
    settings = get_settings()
    app = FastAPI(
        title="mxa-tutor",
        version="0.0.1",
        description="工科仿真 AI 助教 — MATLAB/Simulink 工程导览与智能问答",
        lifespan=lifespan,
    )
    register_error_handlers(app, settings)
    app.include_router(health_router)
    return app


app = create_app()
