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
from typing import Any

from fastapi import FastAPI
from loguru import logger

from adapters.llm import DeepSeekTextProvider
from adapters.storage._connection import open_connection
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_bridge_run_state_store import SqliteBridgeRunStateStore
from adapters.storage.sqlite_chat_store import SqliteChatStore
from adapters.storage.sqlite_paper_cache import (
    SqlitePaperBundleStore,
    SqlitePaperPlanCacheView,
    SqlitePaperSpecCacheView,
)
from adapters.storage.sqlite_project_store import SqliteProjectStore
from adapters.storage.sqlite_teaching_unit_store import SqliteTeachingUnitStore
from adapters.storage.sqlite_vector_store import SqliteVectorStore
from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.matlab_bridge import (
    install_matlab_bridge_openapi,
)
from api.routes.matlab_bridge import (
    router as matlab_bridge_router,
)
from api.routes.matlab_bridge_auth import router as matlab_bridge_auth_router
from api.routes.overview import router as overview_router
from api.routes.paper_ask import router as paper_ask_router
from api.routes.paper_parameter_correction import router as paper_parameter_correction_router
from api.routes.paper_query import router as paper_query_router
from api.routes.paper_reparse import router as paper_reparse_router
from api.routes.paper_step_regeneration import router as paper_step_regeneration_router
from api.routes.paper_tuning import router as paper_tuning_router
from api.routes.paper_upload import (
    router as paper_upload_router,
)
from api.routes.paper_upload import (
    sweep_stale_paper_upload_jobs,
)
from api.routes.paper_user_supply import router as paper_user_supply_router
from api.routes.teaching_unit import router as teaching_unit_router
from api.routes.upload import router as upload_router
from app.config import AppSettings
from core.domain.exceptions import (
    EmbeddingModelLoadError,
    MatlabEngineBusyError,
    MatlabEngineError,
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
)
from core.interfaces.embedder import EmbeddingProvider
from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever
from features.chat._prompt_builder import ChatPromptBuilder
from features.chat.chat_service import ChatService
from features.chunking import ChunkingService
from features.ingest.cleanup_worker import CleanupWorker
from features.matlab_bridge.run_state_cleanup_worker import RunStateCleanupWorker
from features.overview import InMemoryOverviewCache
from features.overview.project_graph_builder import ProjectGraphBuilder
from features.paper.paper_reparse_service import PaperReparseLockRegistry


def _validate_matlab_bridge_settings(settings: AppSettings) -> None:
    if settings.matlab_bridge_enabled and settings.app_environment not in {"development", "test"}:
        raise RuntimeError("matlab_bridge_enabled requires APP_ENV=development or APP_ENV=test")


def _start_owned_matlab_engine_runtime() -> Any:
    from adapters.matlab_engine.owned_startup import start_owned_bounded

    return start_owned_bounded()


def _matlab_engine_health_probe_timeout_s() -> float:
    from adapters.matlab_engine.owned_startup import HEALTH_PROBE_TIMEOUT_S

    return HEALTH_PROBE_TIMEOUT_S


def _consume_task_result(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.error(
            "MATLAB Engine late task finished with error: exception_type={}",
            type(exc).__name__,
        )


async def _attach_matlab_engine_runtime(app: FastAPI, stack: AsyncExitStack) -> None:
    runtime = await asyncio.to_thread(_start_owned_matlab_engine_runtime)
    stack.push_async_callback(_close_owned_runtime, app, runtime)

    probe_task = asyncio.create_task(asyncio.to_thread(runtime.provider.health_probe))
    done, _pending = await asyncio.wait(
        {probe_task},
        timeout=_matlab_engine_health_probe_timeout_s(),
    )
    if not done:
        reaped = await asyncio.to_thread(runtime.terminate_tree)
        probe_task.add_done_callback(_consume_task_result)
        if reaped:
            raise MatlabEngineTimeoutError(reason_code="health_probe_timeout_reaped") from None
        raise MatlabEngineStartupError(reason_code="health_probe_reaper_failed") from None

    probe_task.result()
    app.state.matlab_engine_provider = runtime.provider


async def _close_owned_runtime(app: FastAPI, runtime: Any) -> None:
    close_task: asyncio.Task[Any] | None = None
    try:
        if getattr(runtime, "is_tree_terminated", False):
            return

        close_task = asyncio.create_task(asyncio.to_thread(runtime.session.close))
        done, _pending = await asyncio.wait(
            {close_task},
            timeout=runtime.cleanup_grace_s,
        )
        if not done:
            close_task.add_done_callback(_consume_task_result)
            reaped = await asyncio.to_thread(runtime.terminate_tree)
            if not reaped:
                logger.error("MATLAB Engine close timeout reaper failed")
            return

        try:
            close_task.result()
        except MatlabEngineBusyError as exc:
            reaped = await asyncio.to_thread(runtime.terminate_tree)
            if not reaped:
                logger.error(
                    "MATLAB Engine busy close reaper failed: reason_code={} exception_type={}",
                    exc.reason_code,
                    type(exc).__name__,
                )
            return
        except MatlabEngineError as exc:
            reaped = await asyncio.to_thread(runtime.terminate_tree)
            if not reaped:
                logger.error(
                    "MATLAB Engine close failed and reaper failed: reason_code={} "
                    "exception_type={}",
                    exc.reason_code,
                    type(exc).__name__,
                )
            return
        except Exception as exc:
            reaped = await asyncio.to_thread(runtime.terminate_tree)
            if not reaped:
                logger.error(
                    "MATLAB Engine close raised unexpected error and reaper failed: "
                    "exception_type={}",
                    type(exc).__name__,
                )
            return

        tree_gone = await asyncio.to_thread(runtime.wait_tree_gone, runtime.cleanup_grace_s)
        if not tree_gone:
            reaped = await asyncio.to_thread(runtime.terminate_tree)
            if not reaped:
                logger.error("MATLAB Engine close returned but process tree remained")
    finally:
        if close_task is not None and not close_task.done():
            close_task.add_done_callback(_consume_task_result)
        if hasattr(app.state, "matlab_engine_provider"):
            delattr(app.state, "matlab_engine_provider")
        cleanup_log_file = getattr(runtime, "cleanup_log_file", None)
        if cleanup_log_file is not None:
            await asyncio.to_thread(cleanup_log_file)


def SentenceTransformerEmbedder(
    model_name: str,
    device: str,
    normalize: bool,
) -> EmbeddingProvider:
    """Typed lazy factory kept patchable for lifespan tests."""
    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(
        model_name=model_name,
        device=device,
        normalize=normalize,
    )


def _build_embedder(settings: AppSettings) -> EmbeddingProvider:
    """Build the configured embedder lazily so importing the API app stays lightweight."""
    return SentenceTransformerEmbedder(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
        normalize=settings.embedding_normalize,
    )


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
        bridge_run_state_store = SqliteBridgeRunStateStore(
            settings.db_path,
            upload_ttl_hours=settings.upload_ttl_hours,
        )
        teaching_unit_store = SqliteTeachingUnitStore(settings.db_path)
        paper_bundle_store = SqlitePaperBundleStore(settings.db_path)
        app.state.project_store = store
        app.state.chat_store = chat_store
        app.state.bridge_run_state_store = bridge_run_state_store
        app.state.teaching_unit_store = teaching_unit_store
        app.state.paper_bundle_store = paper_bundle_store
        app.state.paper_spec_cache = SqlitePaperSpecCacheView(paper_bundle_store)
        app.state.paper_plan_cache = SqlitePaperPlanCacheView(paper_bundle_store)
        app.state.paper_reparse_lock_registry = PaperReparseLockRegistry()
        await sweep_stale_paper_upload_jobs(
            upload_dir=upload_dir,
            bundle_store=paper_bundle_store,
            job_store=paper_bundle_store,
        )
        try:
            embedder: EmbeddingProvider = await asyncio.to_thread(_build_embedder, settings)
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
        app.state.graph_provider = ProjectGraphBuilder()
        app.state.chunking_service = ChunkingService(
            embedder=embedder,
            vector_store=vector_store,
            graph_provider=app.state.graph_provider,
            settings=settings,
        )
        app.state.overview_cache = InMemoryOverviewCache()
        app.state.text_provider = DeepSeekTextProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        app.state.keyword_retriever = KeywordRetriever(graph_provider=app.state.graph_provider)
        app.state.vector_retriever = VectorRetriever(
            embedder=embedder,
            vector_store=app.state.vector_store,
            min_score=settings.vector_min_score,
        )
        app.state.hybrid_retriever = HybridRetriever(
            vector=app.state.vector_retriever,
            keyword=app.state.keyword_retriever,
            vector_store=app.state.vector_store,
            min_chunk_count=settings.rag_min_chunk_count,
        )
        app.state.chat_service = ChatService(
            project_store=store,
            chat_store=chat_store,
            text_provider=app.state.text_provider,
            retriever=app.state.hybrid_retriever,
            prompt_builder=ChatPromptBuilder(teaching_unit_store=teaching_unit_store),
        )
        stack.push_async_callback(app.state.chunking_service.aclose)
        stack.push_async_callback(vector_store.aclose)
        stack.push_async_callback(teaching_unit_store.aclose)
        stack.push_async_callback(chat_store.aclose)
        stack.push_async_callback(store.aclose)
        if settings.matlab_engine_enabled:
            await _attach_matlab_engine_runtime(app, stack)
        worker = CleanupWorker(
            store=store,
            upload_dir=upload_dir,
            ttl_hours=settings.upload_ttl_hours,
            paper_store=paper_bundle_store,
            paper_job_store=paper_bundle_store,
        )
        cleanup_task = asyncio.create_task(worker.run_forever())
        run_state_worker = RunStateCleanupWorker(bridge_run_state_store)
        run_state_cleanup_task = asyncio.create_task(run_state_worker.run_forever())

        async def _shutdown_cleanup() -> None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
            logger.info("CleanupWorker shutdown complete")

        async def _shutdown_run_state_cleanup() -> None:
            run_state_cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await run_state_cleanup_task
            logger.info(
                "Bridge run-state sweep shutdown: event_code={} status={}",
                "bridge_run_state_sweep",
                "shutdown",
            )

        stack.push_async_callback(_shutdown_run_state_cleanup)
        stack.push_async_callback(_shutdown_cleanup)
        yield

    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """构造 FastAPI app 实例。

    description 字符串(含 em-dash ``—``)从 ``pyproject.toml`` 的
    ``[project].description`` 复制,保持字面一致。
    """
    settings = get_settings()
    _validate_matlab_bridge_settings(settings)
    app = FastAPI(
        title="mxa-tutor",
        version="0.0.1",
        description="工科仿真 AI 助教 — MATLAB/Simulink 工程导览与智能问答",
        lifespan=lifespan,
    )
    register_error_handlers(app, settings)
    app.include_router(health_router)
    app.include_router(upload_router)
    app.include_router(paper_upload_router)
    app.include_router(paper_query_router)
    app.include_router(paper_reparse_router)
    app.include_router(paper_parameter_correction_router)
    app.include_router(paper_step_regeneration_router)
    app.include_router(paper_ask_router)
    app.include_router(paper_tuning_router)
    app.include_router(paper_user_supply_router)
    if settings.matlab_bridge_enabled:
        app.include_router(matlab_bridge_router)
        install_matlab_bridge_openapi(app)
        if settings.matlab_bridge_dev_auth_enabled:
            app.include_router(matlab_bridge_auth_router)
    app.include_router(overview_router)
    app.include_router(teaching_unit_router)
    app.include_router(chat_router)
    return app


app = create_app()
