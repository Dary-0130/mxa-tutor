"""D2 scoring and D3 layered selection for explanation evidence blocks."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict, deque
from dataclasses import replace
from typing import Literal

from core.domain.project import Project
from core.domain.project_graph import EdgeType, NodeType, ProjectGraph
from core.domain.slx_model import SlxBlock

from ._score_rules import (
    classify_block_type,
    has_domain_keyword,
    is_ambiguously_named,
    nondefault_parameters,
    normalize_block_type,
)
from ._score_types import BlockScore, ScoredBlock, SelectionDiagnostics, SelectionResult

ScoreComponent = Literal["topology", "rarity", "clarity", "parameter", "keyword", "total"]


def select_high_value_blocks(
    project: Project,
    graph: ProjectGraph,
    *,
    min_blocks: int = 40,
    max_blocks: int = 80,
) -> SelectionResult:
    records, upstream = _build_records(project, graph)
    if not records:
        return SelectionResult([], _diagnostics([], {}, {}, {}, total_blocks=0))

    layer_raw = _layer_raw_candidates(records, upstream)
    layer_candidates = {
        "L1": _rank(layer_raw["L1"], 10),
        "L2": _rank(layer_raw["L2"], 10),
        "L3": _rank(layer_raw["L3"], 5),
        "L4": _rank(layer_raw["L4"], 8),
        "L5": _rank(layer_raw["L5"], 5),
        "L6": _rank(layer_raw["L6"], 5),
    }
    selected, selected_counts = _merge_layers(layer_candidates, min_blocks, max_blocks, layer_raw)
    diagnostics = _diagnostics(
        selected,
        {layer: len(items) for layer, items in layer_raw.items()},
        {layer: len(items) for layer, items in layer_candidates.items()},
        dict(selected_counts),
        total_blocks=len(records),
    )
    return SelectionResult(selected, diagnostics)


def _build_records(
    project: Project,
    graph: ProjectGraph,
) -> tuple[list[ScoredBlock], dict[str, set[str]]]:
    signal_edges = [edge for edge in graph.edges if edge.type == EdgeType.SIGNAL_FLOWS]
    indegree: Counter[str] = Counter()
    outdegree: Counter[str] = Counter()
    upstream: dict[str, set[str]] = defaultdict(set)
    for edge in signal_edges:
        outdegree[edge.from_node] += 1
        indegree[edge.to_node] += 1
        upstream[edge.to_node].add(edge.from_node)

    node_by_block = {
        (node.source_ref.file_path, node.source_ref.block_id): node.id
        for node in graph.nodes
        if node.type in (NodeType.BLOCK, NodeType.SUBSYSTEM) and node.source_ref.block_id
    }
    type_counts = Counter(
        normalize_block_type(block.block_type)
        for model in project.slx_models
        for block in model.blocks
    )
    max_degree = max(
        (indegree[node] + outdegree[node] for node in set(indegree) | set(outdegree)),
        default=1,
    )
    return _records_from_blocks(
        project, node_by_block, indegree, outdegree, type_counts, max_degree
    ), upstream


def _records_from_blocks(
    project: Project,
    node_by_block: dict[tuple[str, str | None], str],
    indegree: Counter[str],
    outdegree: Counter[str],
    type_counts: Counter[str],
    max_degree: int,
) -> list[ScoredBlock]:
    records: list[ScoredBlock] = []
    total_blocks = max(1, sum(type_counts.values()))
    for model in project.slx_models:
        for block in model.blocks:
            node_id = node_by_block.get(
                (model.file_path, block.block_id),
                f"slx:{model.file_path}::block:{block.block_id}",
            )
            score = _score_block(
                block, node_id, indegree, outdegree, type_counts, max_degree, total_blocks
            )
            records.append(
                ScoredBlock(
                    file_path=model.file_path,
                    model=model,
                    block=block,
                    node_id=node_id,
                    indegree=indegree[node_id],
                    outdegree=outdegree[node_id],
                    e1_category=classify_block_type(block.block_type),
                    is_ambiguously_named=is_ambiguously_named(block),
                    has_domain_keyword=has_domain_keyword(block),
                    nondefault_parameters=nondefault_parameters(block),
                    score=score,
                )
            )
    return records


def _score_block(
    block: SlxBlock,
    node_id: str,
    indegree: Counter[str],
    outdegree: Counter[str],
    type_counts: Counter[str],
    max_degree: int,
    total_blocks: int,
) -> BlockScore:
    category = classify_block_type(block.block_type)
    keyword = has_domain_keyword(block)
    ambiguous = is_ambiguously_named(block)
    block_type_count = type_counts[normalize_block_type(block.block_type)]
    return BlockScore(
        topology_score=(indegree[node_id] + outdegree[node_id]) / max_degree,
        rarity_score=1 - (block_type_count / total_blocks),
        clarity_score=0.0 if ambiguous else (1.0 if keyword else 0.5),
        parameter_score=min(1.0, len(nondefault_parameters(block)) / 5),
        keyword_score=1.0 if category and keyword else (0.5 if category or keyword else 0.0),
    )


def _layer_raw_candidates(
    records: list[ScoredBlock],
    upstream: dict[str, set[str]],
) -> dict[str, list[ScoredBlock]]:
    l1 = _l1_scope_measurement_upstream(records, upstream)
    return {
        "L1": l1,
        "L2": [item for item in records if item.nondefault_parameters],
        "L3": [item for item in records if _is_routing_connector(item.block)],
        "L4": [item for item in records if item.degree >= 4],
        "L5": [item for item in records if item.is_ambiguously_named and item.e1_category],
        "L6": [item for item in records if item.has_domain_keyword],
    }


def _merge_layers(
    layer_candidates: dict[str, list[ScoredBlock]],
    min_blocks: int,
    max_blocks: int,
    layer_raw: dict[str, list[ScoredBlock]],
) -> tuple[list[ScoredBlock], Counter[str]]:
    by_node: dict[str, ScoredBlock] = {}
    selected_order: list[str] = []
    selected_counts: Counter[str] = Counter()
    for layer, layer_records in layer_candidates.items():
        for item in layer_records:
            _add_selected(item, layer, by_node, selected_order, selected_counts)
    if len(by_node) < min_blocks:
        fallback_pool = _rank(
            [item for item in (layer_raw["L1"] + layer_raw["L2"]) if item.node_id not in by_node],
            max_blocks,
        )
        for item in fallback_pool:
            if len(by_node) >= min_blocks:
                break
            _add_selected(item, "quota_to_L1_L2", by_node, selected_order, selected_counts)
    return _rank([by_node[node_id] for node_id in selected_order], max_blocks), selected_counts


def _add_selected(
    item: ScoredBlock,
    layer: str,
    by_node: dict[str, ScoredBlock],
    selected_order: list[str],
    selected_counts: Counter[str],
) -> None:
    existing = by_node.get(item.node_id)
    if existing is None:
        by_node[item.node_id] = replace(item, selection_layers=(layer,))
        selected_order.append(item.node_id)
        selected_counts[layer] += 1
    else:
        by_node[item.node_id] = replace(
            existing, selection_layers=existing.selection_layers + (layer,)
        )


def _l1_scope_measurement_upstream(
    records: list[ScoredBlock],
    upstream: dict[str, set[str]],
) -> list[ScoredBlock]:
    by_node = {item.node_id: item for item in records}
    targets = [item.node_id for item in records if _is_measurement_or_scope(item.block)]
    seen: set[str] = set(targets)
    queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in targets)
    while queue:
        node_id, depth = queue.popleft()
        if depth >= 2:
            continue
        for parent in upstream.get(node_id, set()):
            if parent not in seen:
                seen.add(parent)
                queue.append((parent, depth + 1))
    return [by_node[node_id] for node_id in seen if node_id in by_node]


def _rank(records: list[ScoredBlock], limit: int) -> list[ScoredBlock]:
    return sorted(
        records,
        key=lambda item: (
            -item.score.total_score,
            -item.degree,
            item.block.name,
            item.block.block_id,
        ),
    )[:limit]


def _is_measurement_or_scope(block: SlxBlock) -> bool:
    block_type = normalize_block_type(block.block_type)
    return (
        block_type
        in {"Scope", "Display", "To Workspace", "To File", "XY Graph", "RMS", "Fourier", "FFT"}
        or "Measurement" in block_type
    )


def _is_routing_connector(block: SlxBlock) -> bool:
    return normalize_block_type(block.block_type) in {
        "Bus Creator",
        "Bus Selector",
        "Demux",
        "From",
        "Goto",
        "Mux",
        "Selector",
    }


def _diagnostics(
    selected: list[ScoredBlock],
    raw_layer_counts: dict[str, int],
    top_layer_counts: dict[str, int],
    selected_layer_counts: dict[str, int],
    total_blocks: int,
) -> SelectionDiagnostics:
    l1_raw_count = raw_layer_counts.get("L1", 0)
    return SelectionDiagnostics(
        raw_layer_counts={**raw_layer_counts, "total_blocks": total_blocks},
        top_layer_counts=top_layer_counts,
        selected_layer_counts=selected_layer_counts,
        selected_count=len(selected),
        l1_raw_ratio=round(l1_raw_count / total_blocks, 4) if total_blocks else 0.0,
        score_distribution=_score_distribution(selected),
    )


def _score_distribution(selected: list[ScoredBlock]) -> dict[str, dict[str, float]]:
    values = {
        "topology": [item.score.topology_score for item in selected],
        "rarity": [item.score.rarity_score for item in selected],
        "clarity": [item.score.clarity_score for item in selected],
        "parameter": [item.score.parameter_score for item in selected],
        "keyword": [item.score.keyword_score for item in selected],
        "total": [item.score.total_score for item in selected],
    }
    return {name: _summarize_score(items) for name, items in values.items()}


def _summarize_score(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "median": 0.0, "max": 0.0}
    return {
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
    }
