"""Shared scoring dataclasses for explanation evidence selection."""

from __future__ import annotations

from dataclasses import dataclass

from core.domain.slx_model import SlxBlock, SlxModel


@dataclass(frozen=True)
class BlockScore:
    topology_score: float
    rarity_score: float
    clarity_score: float
    parameter_score: float
    keyword_score: float

    @property
    def total_score(self) -> float:
        """v0.2.3 equal-weight sum; TASK-310 owns later tuning."""
        return (
            self.topology_score
            + self.rarity_score
            + self.clarity_score
            + self.parameter_score
            + self.keyword_score
        )


@dataclass(frozen=True)
class ScoredBlock:
    file_path: str
    model: SlxModel
    block: SlxBlock
    node_id: str
    indegree: int
    outdegree: int
    e1_category: str | None
    is_ambiguously_named: bool
    has_domain_keyword: bool
    nondefault_parameters: tuple[tuple[str, str], ...]
    score: BlockScore
    selection_layers: tuple[str, ...] = ()

    @property
    def degree(self) -> int:
        return self.indegree + self.outdegree


@dataclass(frozen=True)
class SelectionDiagnostics:
    raw_layer_counts: dict[str, int]
    top_layer_counts: dict[str, int]
    selected_layer_counts: dict[str, int]
    selected_count: int
    l1_raw_ratio: float
    score_distribution: dict[str, dict[str, float]]


@dataclass(frozen=True)
class SelectionResult:
    selected: list[ScoredBlock]
    diagnostics: SelectionDiagnostics
