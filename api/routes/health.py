"""健康检查端点。

实为 readiness check:验证 app 配置可加载、路由可用。不检查 DeepSeek 网络
连通性或数据库可达性(避免 ``/health`` 因外部依赖抖动而误报)。深度健康检查
由 TASK-405 部署阶段的独立监控系统覆盖。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_settings
from api.schemas.health import HealthResponse
from app.config import AppSettings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthResponse:
    """返回服务健康状态。"""
    _ = settings
    return HealthResponse(
        status="ok",
        version="0.0.1",
        app_name="mxa-tutor",
    )
