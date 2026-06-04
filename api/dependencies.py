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

from adapters.parser.dependency_analyzer import analyze_dependencies
from adapters.parser.file_classifier import classify_files
from adapters.parser.m_parser import MParserImpl
from adapters.parser.slx_parser import SlxParserImpl
from adapters.parser.zip_extractor import safe_extract
from app.config import AppSettings
from core.interfaces.project_store import ProjectStore
from features.ingest.upload_service import ExtractFn, UploadService


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """加载并返回单例 ``AppSettings``。"""
    settings_values: dict[str, Any] = {}
    return AppSettings(**settings_values)


def get_project_store(request: Request) -> ProjectStore:
    """从 app.state.project_store 取 ProjectStore。"""
    return cast(ProjectStore, request.app.state.project_store)


def get_upload_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
    store: Annotated[ProjectStore, Depends(get_project_store)],
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
    )
