"""FastAPI app 工厂与模块级入口。

uvicorn 通过 ``uvicorn api.main:app`` 加载模块底部的 ``app`` 实例。

lifespan 设计原则(TASK-201 + 后续 Task 共同约束):
1. startup 只做轻量 fail-fast(本 Task:加载 ``AppSettings`` 验证 ``.env``)
2. 重任务用 ``BackgroundTasks`` 或 service 层异步初始化,不在 lifespan 内做
3. 未来 lifespan 一旦初始化真实资源(DB pool / 临时目录 / 后台清理 worker),
   必须用 ``AsyncExitStack`` 或显式 try/cleanup 保证"已初始化资源在 startup
   中途失败时也被清理",不能假设 ``yield`` 后 shutdown block 必然执行
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder
from adapters.llm import DeepSeekTextProvider
from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_chat_store import SqliteChatStore
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.overview import router as overview_router
from api.routes.upload import router as upload_router
from core.domain.exceptions import EmbeddingModelLoadError
from features.chat import KeywordRetriever
from features.chat._prompt_builder import ChatPromptBuilder
from features.chat.chat_service import ChatService
from features.chunking import ChunkingService
from features.ingest.cleanup_worker import CleanupWorker
from features.overview import InMemoryOverviewCache
from features.overview.project_graph_builder import ProjectGraphBuilder


@asynccontextmanager
async def _bootstrap_db(db_path: str) -> AsyncIterator[None]:
    """启动时初始化 SQLite schema,不在 lifespan 期间持有连接。"""

    async with open_connection(db_path) as conn:
        await init_schema(conn)
    yield


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifecycle。"""
    settings = get_settings()
    logger.info(
        "Application startup: db_path={}, upload_dir={}, ttl_hours={}",
        settings.db_path,
        settings.upload_dir,
        settings.upload_ttl_hours,
    )
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_bootstrap_db(settings.db_path))
        store = SqliteProjectStore(settings.db_path)
        chat_store = SqliteChatStore(settings.db_path)
        app.state.project_store = store
        app.state.chat_store = chat_store
        try:
            embedder = await asyncio.to_thread(
                SentenceTransformerEmbedder,
                settings.embedding_model_name,
                settings.embedding_device,
                settings.embedding_normalize,
            )
        except Exception as exc:
            logger.error(
                "Embedding model load failed: model_name={} device={} exception={}",
                settings.embedding_model_name,
                settings.embedding_device,
                type(exc).__name__,
            )
            raise EmbeddingModelLoadError("model_load_failed") from None

        app.state.embedder = embedder
        vector_store = SqliteVectorStore(settings.db_path)
        app.state.vector_store = vector_store
        app.state.chunking_service = ChunkingService(
            embedder=embedder,
            vector_store=vector_store,
            graph_provider=ProjectGraphBuilder(),
            settings=settings,
        )
        app.state.overview_cache = InMemoryOverviewCache()
        app.state.text_provider = DeepSeekTextProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        app.state.chat_service = ChatService(
            project_store=store,
            chat_store=chat_store,
            text_provider=app.state.text_provider,
            retriever=KeywordRetriever(graph_provider=ProjectGraphBuilder()),
            prompt_builder=ChatPromptBuilder(),
        )
        stack.push_async_callback(app.state.chunking_service.aclose)
        stack.push_async_callback(vector_store.aclose)
        stack.push_async_callback(chat_store.aclose)
        stack.push_async_callback(store.aclose)

        worker = CleanupWorker(
            store=store,
            upload_dir=upload_dir,
            ttl_hours=settings.upload_ttl_hours,
        )
        cleanup_task = asyncio.create_task(worker.run_forever())

        async def _shutdown_cleanup() -> None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
            logger.info("CleanupWorker shutdown complete")

        stack.push_async_callback(_shutdown_cleanup)
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
    app.include_router(upload_router)
    app.include_router(overview_router)
    app.include_router(chat_router)
    return app


app = create_app()
