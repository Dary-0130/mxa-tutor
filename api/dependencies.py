"""FastAPI 依赖注入容器。

所有需要 ``AppSettings`` 的 route handler 通过
``Annotated[AppSettings, Depends(get_settings)]`` 注入(FastAPI 0.115+ 偏好写法),
不在模块顶部全局实例化 ``settings = AppSettings()``。

``lru_cache(maxsize=1)`` 保证进程内单例语义。测试通过
``app.dependency_overrides[get_settings] = lambda: AppSettings(...)`` 替换;
``tests/api/conftest.py`` 已建 autouse fixture,每个测试前后自动调用
``get_settings.cache_clear()`` 与 ``app.dependency_overrides.clear()``,
测试作者不需要手动管理缓存。

约束:``get_settings()`` 只能加载配置,不能在内部创建 DeepSeek client、
数据库连接、临时目录清理器等有副作用资源。需要这些资源时,新建独立 dependency
(如 ``get_text_provider()`` / ``get_project_store()``)。
"""

from functools import lru_cache, partial
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Depends, Request

from adapters.classifier.general_project_type_resolver import GeneralProjectTypeResolver
from adapters.parser.dependency_analyzer import analyze_dependencies
from adapters.parser.docx_parser import DocxParser
from adapters.parser.file_classifier import classify_files
from adapters.parser.m_parser import MParserImpl
from adapters.parser.pdf_parser import PdfParser
from adapters.parser.slx_parser import SlxParserImpl
from adapters.parser.zip_extractor import safe_extract
from adapters.storage.sqlite_bridge_run_state_store import SqliteBridgeRunStateStore
from app.config import AppSettings
from core.domain.exceptions import BridgeExplanationUnavailableError, MatlabEngineDisabledError
from core.interfaces.chat_store import ChatStore
from core.interfaces.document_parser import DocumentParserRouter
from core.interfaces.embedder import EmbeddingProvider
from core.interfaces.llm_provider import TextProvider
from core.interfaces.matlab_engine_provider import MatlabEngineProvider
from core.interfaces.paper_cache import PaperBundleStore
from core.interfaces.paper_reparse_store import PaperReparseStore
from core.interfaces.project_store import ProjectStore
from core.interfaces.project_type_resolver import ProjectTypeResolver
from core.interfaces.teaching_unit_store import TeachingUnitStore
from core.interfaces.vector_store import VectorStore
from features.chat.chat_service import ChatService
from features.chunking import ChunkingService
from features.ingest.upload_service import ExtractFn, UploadService
from features.matlab_bridge import (
    BridgeAuthService,
    BridgeExplanationService,
    BridgeRunStateCoachingService,
    BridgeRunStateService,
    DiagnosticService,
)
from features.matlab_bridge.bridge_auth_service import (
    InMemoryBridgeRevocationStore,
    build_bridge_auth_config,
)
from features.matlab_bridge.bridge_run_state_coaching_service import (
    BridgeRunStateCoachingUnavailableError,
)
from features.overview import OverviewCache
from features.overview._teaching_level_policy import TeachingLevelPolicy
from features.overview._teaching_unit_builder import TeachingUnitBuilder
from features.overview._teaching_unit_service import TeachingUnitService
from features.overview.overview_service import ProjectOverviewService
from features.paper import (
    PaperPlanCache,
    PaperSpecCache,
    PaperSpecService,
    UserSupplyService,
)
from features.paper.paper_ask_service import PaperAskService
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_reparse_service import PaperReparseLockRegistry, PaperReparseService
from features.paper.paper_tuning_service import TuningSuggestionService


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """加载并返回单例 ``AppSettings``。"""
    settings_values: dict[str, Any] = {}
    return AppSettings(**settings_values)


def get_matlab_bridge_diagnostic_service() -> DiagnosticService:
    """Return the stateless MATLAB bridge diagnostic service."""
    return DiagnosticService()


def get_matlab_bridge_explanation_service(request: Request) -> BridgeExplanationService:
    """Return a bridge explanation service using the shared app text provider."""
    text_provider = getattr(request.app.state, "text_provider", None)
    if text_provider is None:
        raise BridgeExplanationUnavailableError("text_provider_unavailable") from None
    return BridgeExplanationService(text_provider=cast(TextProvider, text_provider))


def get_matlab_bridge_run_state_service() -> BridgeRunStateService:
    """Return the stateless MATLAB bridge run-state validation service."""
    return BridgeRunStateService()


def get_matlab_bridge_run_state_coaching_service(
    request: Request,
) -> BridgeRunStateCoachingService:
    """Return a run-state coaching service using the shared app text provider."""
    text_provider = getattr(request.app.state, "text_provider", None)
    if text_provider is None:
        raise BridgeRunStateCoachingUnavailableError("text_provider_unavailable") from None
    return BridgeRunStateCoachingService(text_provider=cast(TextProvider, text_provider))


def get_matlab_bridge_run_state_store(request: Request) -> SqliteBridgeRunStateStore:
    """Return the app-managed run-state persistence substrate."""
    store = getattr(request.app.state, "bridge_run_state_store", None)
    if store is not None:
        return cast(SqliteBridgeRunStateStore, store)
    settings = get_settings()
    return SqliteBridgeRunStateStore(
        settings.db_path,
        upload_ttl_hours=settings.upload_ttl_hours,
    )


@lru_cache(maxsize=1)
def get_matlab_bridge_auth_service() -> BridgeAuthService:
    """Return the process-local MATLAB bridge auth service for dev/test mode."""
    settings = get_settings()
    config = build_bridge_auth_config(
        signing_key=settings.matlab_bridge_auth_signing_key or "",
        key_id=settings.matlab_bridge_auth_key_id,
        issuer=settings.matlab_bridge_auth_issuer,
        audience=settings.matlab_bridge_auth_audience,
        token_ttl_seconds=settings.matlab_bridge_auth_token_ttl_seconds,
        max_token_lifetime_seconds=settings.matlab_bridge_auth_max_lifetime_seconds,
        clock_skew_seconds=settings.matlab_bridge_auth_clock_skew_seconds,
    )
    return BridgeAuthService(config, revocation_store=InMemoryBridgeRevocationStore())


def get_matlab_engine_provider(request: Request) -> MatlabEngineProvider:
    """Return the app-managed MATLAB Engine provider when the feature is enabled."""
    provider = getattr(request.app.state, "matlab_engine_provider", None)
    if provider is None:
        raise MatlabEngineDisabledError(reason_code="matlab_engine_disabled") from None
    return cast(MatlabEngineProvider, provider)


def get_project_store(request: Request) -> ProjectStore:
    """从 app.state.project_store 取 ProjectStore。"""
    return cast(ProjectStore, request.app.state.project_store)


def get_chat_store(request: Request) -> ChatStore:
    """从 app.state.chat_store 取 ChatStore。"""
    store = getattr(request.app.state, "chat_store", None)
    if store is None:
        raise RuntimeError("ChatStore not initialized; lifespan misconfigured")
    return cast(ChatStore, store)


def get_embedder(request: Request) -> EmbeddingProvider:
    """从 app.state.embedder 取 EmbeddingProvider。"""
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise RuntimeError("EmbeddingProvider not initialized; lifespan misconfigured")
    return cast(EmbeddingProvider, embedder)


def get_vector_store(request: Request) -> VectorStore:
    """从 app.state.vector_store 取 VectorStore。"""
    store = getattr(request.app.state, "vector_store", None)
    if store is None:
        raise RuntimeError("VectorStore not initialized; lifespan misconfigured")
    return cast(VectorStore, store)


def get_teaching_unit_store(request: Request) -> TeachingUnitStore:
    """从 app.state.teaching_unit_store 取 TeachingUnitStore。"""
    store = getattr(request.app.state, "teaching_unit_store", None)
    if store is None:
        raise RuntimeError("TeachingUnitStore not initialized; lifespan misconfigured")
    return cast(TeachingUnitStore, store)


def get_chunking_service(request: Request) -> ChunkingService:
    """从 app.state.chunking_service 取 ChunkingService。"""
    service = getattr(request.app.state, "chunking_service", None)
    if service is None:
        raise RuntimeError("chunking_service not configured")
    return cast(ChunkingService, service)


def get_upload_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
    store: Annotated[ProjectStore, Depends(get_project_store)],
    chunking_service: ChunkingService = Depends(get_chunking_service),  # noqa: B008
) -> UploadService:
    """每次请求构造新 UploadService;store 由 lifespan 装配。"""
    upload_dir = Path(settings.upload_dir)
    max_upload_bytes = settings.max_upload_size_mb * 1024 * 1024
    extractor = cast(ExtractFn, partial(safe_extract, config=settings))
    return UploadService(
        store=store,
        upload_dir=upload_dir,
        max_upload_bytes=max_upload_bytes,
        extractor=extractor,
        classifier=classify_files,
        slx_parser=SlxParserImpl(),
        m_parser=MParserImpl(),
        dependency_analyzer=analyze_dependencies,
        chunking_service=chunking_service,
    )


def get_text_provider(request: Request) -> TextProvider:
    """从 app.state.text_provider 取 TextProvider。"""
    return cast(TextProvider, request.app.state.text_provider)


def get_overview_cache(request: Request) -> OverviewCache:
    """从 app.state.overview_cache 取 OverviewCache。"""
    return cast(OverviewCache, request.app.state.overview_cache)


def get_paper_spec_cache(request: Request) -> PaperSpecCache:
    """从 app.state.paper_spec_cache 取 PaperSpecCache。"""
    cache = getattr(request.app.state, "paper_spec_cache", None)
    if cache is None:
        raise RuntimeError("PaperSpecCache not initialized; lifespan misconfigured")
    return cast(PaperSpecCache, cache)


def get_paper_plan_cache(request: Request) -> PaperPlanCache:
    """从 app.state.paper_plan_cache 取 PaperPlanCache。"""
    cache = getattr(request.app.state, "paper_plan_cache", None)
    if cache is None:
        raise RuntimeError("PaperPlanCache not initialized; lifespan misconfigured")
    return cast(PaperPlanCache, cache)


def get_paper_bundle_store(request: Request) -> PaperBundleStore:
    """从 app.state.paper_bundle_store 取 PaperBundleStore。"""
    store = getattr(request.app.state, "paper_bundle_store", None)
    if store is None:
        raise RuntimeError("PaperBundleStore not initialized; lifespan misconfigured")
    return cast(PaperBundleStore, store)


def get_paper_reparse_store(request: Request) -> PaperReparseStore:
    """从 app.state.paper_bundle_store 取 PaperReparseStore。"""
    store = getattr(request.app.state, "paper_bundle_store", None)
    if store is None:
        raise RuntimeError("PaperReparseStore not initialized; lifespan misconfigured")
    return cast(PaperReparseStore, store)


def get_paper_reparse_lock_registry(request: Request) -> PaperReparseLockRegistry:
    """Return the process-local paper reparse lock registry."""
    registry = getattr(request.app.state, "paper_reparse_lock_registry", None)
    if registry is None:
        registry = PaperReparseLockRegistry()
        request.app.state.paper_reparse_lock_registry = registry
    return cast(PaperReparseLockRegistry, registry)


def get_document_parser_router() -> DocumentParserRouter:
    """装配 PDF / docx 文档 parser router。"""
    return DocumentParserRouter([PdfParser(), DocxParser()])


def get_project_type_resolver() -> ProjectTypeResolver:
    """返回 v0.1 project type resolver。"""
    return GeneralProjectTypeResolver()


def get_teaching_level_policy() -> TeachingLevelPolicy:
    """返回 TeachingUnit level policy。"""
    return TeachingLevelPolicy()


def get_teaching_unit_builder(
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
) -> TeachingUnitBuilder:
    """装配 TeachingUnitBuilder。"""
    return TeachingUnitBuilder(text_provider)


def get_teaching_unit_service(
    project_store: Annotated[ProjectStore, Depends(get_project_store)],
    teaching_unit_store: Annotated[TeachingUnitStore, Depends(get_teaching_unit_store)],
    builder: Annotated[TeachingUnitBuilder, Depends(get_teaching_unit_builder)],
    level_policy: Annotated[TeachingLevelPolicy, Depends(get_teaching_level_policy)],
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
) -> TeachingUnitService:
    """装配 TeachingUnitService。"""
    return TeachingUnitService(
        project_store=project_store,
        teaching_unit_store=teaching_unit_store,
        builder=builder,
        level_policy=level_policy,
        model_name=text_provider.capability().model_name,
    )


def get_overview_service(
    store: Annotated[ProjectStore, Depends(get_project_store)],
    cache: Annotated[OverviewCache, Depends(get_overview_cache)],
    resolver: Annotated[ProjectTypeResolver, Depends(get_project_type_resolver)],
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
    chunking_service: ChunkingService = Depends(get_chunking_service),  # noqa: B008
) -> ProjectOverviewService:
    """装配 ProjectOverviewService。"""
    return ProjectOverviewService(
        store, cache, resolver, text_provider, chunking_service=chunking_service
    )


def get_paper_spec_service(
    cache: Annotated[PaperSpecCache, Depends(get_paper_spec_cache)],
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
    document_parser_router: Annotated[
        DocumentParserRouter,
        Depends(get_document_parser_router),
    ],
) -> PaperSpecService:
    """装配 PaperSpecService。"""
    return PaperSpecService(
        cache=cache,
        text_provider=text_provider,
        document_parser_router=document_parser_router,
    )


def get_paper_plan_service(
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
) -> PaperPlanService:
    """装配 PaperPlanService。"""
    return PaperPlanService(text_provider=text_provider)


def get_paper_reparse_service(
    bundle_store: Annotated[PaperBundleStore, Depends(get_paper_bundle_store)],
    reparse_store: Annotated[PaperReparseStore, Depends(get_paper_reparse_store)],
    spec_service: Annotated[PaperSpecService, Depends(get_paper_spec_service)],
    plan_service: Annotated[PaperPlanService, Depends(get_paper_plan_service)],
    lock_registry: Annotated[
        PaperReparseLockRegistry,
        Depends(get_paper_reparse_lock_registry),
    ],
) -> PaperReparseService:
    """装配 PaperReparseService。"""
    return PaperReparseService(
        bundle_store=bundle_store,
        reparse_store=reparse_store,
        spec_service=spec_service,
        plan_service=plan_service,
        lock_registry=lock_registry,
    )


def get_paper_user_supply_service(
    cache: Annotated[PaperPlanCache, Depends(get_paper_plan_cache)],
) -> UserSupplyService:
    """装配 UserSupplyService。"""
    return UserSupplyService(cache=cache)


def get_paper_ask_service(
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
) -> PaperAskService:
    """装配 PaperAskService。"""
    return PaperAskService(text_provider=text_provider)


def get_paper_tuning_service(
    text_provider: Annotated[TextProvider, Depends(get_text_provider)],
) -> TuningSuggestionService:
    """装配 TuningSuggestionService。"""
    return TuningSuggestionService(text_provider=text_provider)


def get_chat_service(request: Request) -> ChatService:
    """从 app.state 取 chat_service(由 lifespan 装配)。"""
    service = getattr(request.app.state, "chat_service", None)
    if service is None:
        raise RuntimeError("ChatService not initialized; lifespan misconfigured")
    return cast(ChatService, service)
