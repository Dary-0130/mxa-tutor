"""TeachingUnit level resolution policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.domain.exceptions import UnsupportedTeachingLevelError
from core.domain.teaching_unit import TeachingLevel, TeachingTarget

TeachingTrigger = Literal["explicit_click", "chat_lazy", "api"]


@dataclass(frozen=True)
class TeachingUnitRequest:
    """External request shape before service builds graph-specific inputs."""

    project_id: str
    target_type: TeachingTarget
    target_id: str
    level: TeachingLevel | None = None
    trigger: TeachingTrigger = "explicit_click"


class TeachingLevelPolicy:
    """MCS default policy; advanced is reserved for a later async path."""

    def resolve(self, request: TeachingUnitRequest) -> TeachingLevel:
        level = request.level or "normal"
        if level == "advanced":
            raise UnsupportedTeachingLevelError(
                "MCS 阶段 advanced level 暂不开放,请使用 normal 或 beginner"
            )
        return level
