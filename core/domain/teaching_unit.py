from dataclasses import dataclass

from core.domain.source_ref import SourceRef


@dataclass
class TeachingUnit:
    """教学讲解单元 —— LLM 基于此生成最终输出(导览 / block 讲解 / .m 讲解 / 问答)。"""

    id: str
    title: str
    target: str
    target_id: str
    level: str
    summary: str
    prerequisites: list[str]
    explanation_steps: list[str]
    related_concepts: list[str]
    source_refs: list[SourceRef]
    confusion_points: list[str]
