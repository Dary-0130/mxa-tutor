"""健康检查端点的响应 schema。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """``GET /health`` 响应体。

    version 字段需与 ``pyproject.toml`` 的 ``[project].version`` 保持同步。
    本字段升级时需在同一 chore PR 中同时更新两处,不走运行时动态读取。

    ``extra="forbid"`` 锁定 schema 契约:任何额外字段都会触发 ``ValidationError``,
    防止未来不小心放进未声明的字段(例如调试信息泄漏)。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    version: str
    app_name: str
