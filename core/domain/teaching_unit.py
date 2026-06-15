from dataclasses import dataclass
from typing import Literal

from core.domain.source_ref import SourceRef

TeachingTarget = Literal["file", "function", "block", "subsystem", "model", "project"]
TeachingLevel = Literal["beginner", "normal", "advanced"]


@dataclass(frozen=True)
class TeachingUnitRef:
    """Reference to another teaching unit; cross-project shape is reserved."""

    project_id: str
    teaching_unit_id: str


@dataclass
class TeachingUnit:
    """教学讲解单元 —— LLM 基于此生成最终输出(导览 / block 讲解 / .m 讲解 / 问答)。"""

    id: str
    title: str
    target: TeachingTarget
    target_id: str
    level: TeachingLevel
    summary: str
    prerequisites: list[TeachingUnitRef]
    explanation_steps: list[str]
    knowledge_points: list[str]
    source_refs: list[SourceRef]
    confusion_points: list[str]
