"""Sanitized dependency graph audit for build step drafts."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

DependencyAuditStatus = Literal["clean", "violations", "unavailable"]
DependencyUnavailableStage = Literal["draft_parse", "audit_error"]
DependencyViolationCode = Literal["self", "unknown", "cycle", "not_prior", "ambiguous"]

BUILD_STEPS_DEPENDENCY_AUDIT_ENV = "MXA_BUILD_STEPS_DEPENDENCY_AUDIT"
DEFAULT_DEPENDENCY_VIOLATION_RECORD_LIMIT = 50
_STEP_ID_ASCII_RE = re.compile(r"^STEP-(\d{3})$", re.ASCII)
_SOURCE_REF_ASCII_RE = re.compile(r"^REF-(\d{3})$", re.ASCII)


def _empty_violation_counts() -> dict[str, int]:
    return {"self": 0, "unknown": 0, "cycle": 0, "not_prior": 0}


@dataclass(frozen=True)
class DependencyViolationEdge:
    step_index: int
    step_id_conforming: bool
    dep_conforming: bool
    dep_match_count: int
    dep_index: int | None
    violation: DependencyViolationCode
    dep_length_bucket: str | None = None
    cycle_length_bucket: str | None = None


@dataclass(frozen=True)
class DependencySameNumberProbe:
    step_ordinal: int
    dep_ordinal: int
    chosen_source_ref_ordinal: int
    dep_ordinal_equals_source_ref_ordinal: bool


@dataclass(frozen=True)
class _StepShape:
    step_id: object
    depends_on: list[object]
    block_ref_ids: list[object]
    connection_ref_pairs: list[tuple[object, object]]
    connection_ref_ids: list[object]
    chosen_source_ref_ordinal: int | None


@dataclass(frozen=True)
class _EdgeRecord:
    step_index: int
    step_id_conforming: bool
    step_ordinal: int | None
    dep_text: object
    dep_conforming: bool
    dep_ordinal: int | None
    dep_match_count: int
    dep_index: int | None


@dataclass(frozen=True)
class DependencyAudit:
    dependency_audit_status: DependencyAuditStatus
    unavailable_stage: DependencyUnavailableStage | None = None
    total_steps: int | None = None
    total_dep_edges: int | None = None
    dep_edge_density: float | None = None
    all_empty_dependency_graph: bool | None = None
    nonfirst_steps_with_empty_depends_on: int | None = None
    duplicate_step_id_count: int | None = None
    violations_by_code: dict[str, int] = field(default_factory=_empty_violation_counts)
    violation_edges: list[DependencyViolationEdge] = field(default_factory=list)
    violation_edges_total_count: int = 0
    violation_edges_truncated: bool = False
    same_number_probes: list[DependencySameNumberProbe] = field(default_factory=list)
    same_number_probe_count: int = 0
    dep_ordinal_equals_source_ref_ordinal_count: int = 0
    connection_ref_not_visible_count: int | None = None
    per_step_connection_counts: list[int] = field(default_factory=list)
    per_step_cross_step_connection_counts: list[int] = field(default_factory=list)
    per_step_inbound_dep_counts: list[int] = field(default_factory=list)
    evidence_ref_count: int | None = None
    block_candidate_count: int | None = None
    parameter_mapping_count: int | None = None
    prompt_tokens_bucket: str | None = None
    rendered_prompt_version: str | None = None

    @classmethod
    def unavailable(cls, stage: DependencyUnavailableStage) -> DependencyAudit:
        return cls(dependency_audit_status="unavailable", unavailable_stage=stage)

    def with_context(
        self,
        *,
        evidence_ref_count: int | None = None,
        block_candidate_count: int | None = None,
        parameter_mapping_count: int | None = None,
        prompt_tokens_bucket: str | None = None,
        rendered_prompt_version: str | None = None,
    ) -> DependencyAudit:
        return replace(
            self,
            evidence_ref_count=evidence_ref_count,
            block_candidate_count=block_candidate_count,
            parameter_mapping_count=parameter_mapping_count,
            prompt_tokens_bucket=prompt_tokens_bucket,
            rendered_prompt_version=rendered_prompt_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_steps_dependency_audit_enabled() -> bool:
    value = os.environ.get(BUILD_STEPS_DEPENDENCY_AUDIT_ENV, "")
    return value.lower() in {"1", "true", "yes", "on"}


def audit_step_dependencies(
    draft_steps: object,
    *,
    max_violation_edges: int = DEFAULT_DEPENDENCY_VIOLATION_RECORD_LIMIT,
) -> DependencyAudit:
    try:
        return _audit_step_dependencies_unchecked(
            draft_steps,
            max_violation_edges=max_violation_edges,
        )
    except Exception:
        return DependencyAudit.unavailable("audit_error")


def audit_step_dependencies_from_payload(
    payload: object,
    *,
    max_violation_edges: int = DEFAULT_DEPENDENCY_VIOLATION_RECORD_LIMIT,
) -> DependencyAudit:
    try:
        if not isinstance(payload, dict):
            return DependencyAudit.unavailable("draft_parse")
        draft_steps = payload.get("build_steps")
        if not isinstance(draft_steps, list):
            return DependencyAudit.unavailable("draft_parse")
        return _audit_step_dependencies_unchecked(
            draft_steps,
            max_violation_edges=max_violation_edges,
        )
    except Exception:
        return DependencyAudit.unavailable("audit_error")


def prompt_token_bucket(prompt_tokens: int | None) -> str | None:
    if prompt_tokens is None:
        return None
    if prompt_tokens <= 0:
        return "0"
    if prompt_tokens <= 2_000:
        return "1-2000"
    if prompt_tokens <= 4_000:
        return "2001-4000"
    if prompt_tokens <= 8_000:
        return "4001-8000"
    if prompt_tokens <= 16_000:
        return "8001-16000"
    return "16001+"


def _audit_step_dependencies_unchecked(
    draft_steps: object,
    *,
    max_violation_edges: int,
) -> DependencyAudit:
    if not isinstance(draft_steps, list):
        return DependencyAudit.unavailable("draft_parse")

    steps = [_extract_step_shape(step) for step in draft_steps]
    step_ids = [step.step_id for step in steps if isinstance(step.step_id, str)]
    step_id_counts = Counter(step_ids)
    duplicate_step_id_count = sum(count - 1 for count in step_id_counts.values() if count > 1)
    total_steps = len(steps)
    total_dep_edges = sum(len(step.depends_on) for step in steps)
    edge_records = _build_edge_records(steps, step_id_counts)

    violation_edges: list[DependencyViolationEdge] = []
    append_violation = violation_edges.append
    for record in edge_records:
        if record.dep_match_count == 0:
            append_violation(
                _edge_violation(
                    record,
                    "unknown",
                    dep_length_bucket=_length_bucket(record.dep_text),
                )
            )
        elif record.dep_match_count > 1:
            append_violation(_edge_violation(record, "ambiguous"))
        elif record.dep_index == record.step_index:
            append_violation(_edge_violation(record, "self"))

    clean_edge_records = [
        record
        for record in edge_records
        if record.dep_match_count == 1 and record.dep_index != record.step_index
    ]
    cycle_edges = _cycle_edge_keys(clean_edge_records)
    cycle_length_bucket = _cycle_length_bucket(len({key[0] for key in cycle_edges}))
    for record in clean_edge_records:
        if record.dep_index is None:
            continue
        key = (record.step_index, record.dep_index)
        if key in cycle_edges:
            append_violation(
                _edge_violation(record, "cycle", cycle_length_bucket=cycle_length_bucket)
            )

    not_prior_edges = _not_prior_edge_keys(clean_edge_records, cycle_edges, total_steps)
    for record in clean_edge_records:
        if record.dep_index is None:
            continue
        key = (record.step_index, record.dep_index)
        if key in not_prior_edges:
            append_violation(_edge_violation(record, "not_prior"))

    violations_by_code = _empty_violation_counts()
    for edge in violation_edges:
        if edge.violation in violations_by_code:
            violations_by_code[edge.violation] += 1

    same_number_probes = _same_number_probes(steps, edge_records)
    connection_ref_not_visible_count = _connection_ref_not_visible_count(steps, edge_records)
    per_step_connection_counts = [len(step.connection_ref_pairs) for step in steps]
    per_step_cross_step_connection_counts = _per_step_cross_step_connection_counts(
        steps,
        edge_records,
    )
    per_step_inbound_dep_counts = _per_step_inbound_dep_counts(steps, edge_records)
    status: DependencyAuditStatus = (
        "violations" if violation_edges or duplicate_step_id_count > 0 else "clean"
    )
    violation_edges_total_count = len(violation_edges)
    truncated_edges = violation_edges[:max_violation_edges]
    return DependencyAudit(
        dependency_audit_status=status,
        total_steps=total_steps,
        total_dep_edges=total_dep_edges,
        dep_edge_density=total_dep_edges / max(total_steps - 1, 1),
        all_empty_dependency_graph=total_dep_edges == 0,
        nonfirst_steps_with_empty_depends_on=sum(
            1 for index, step in enumerate(steps) if index > 0 and not step.depends_on
        ),
        duplicate_step_id_count=duplicate_step_id_count,
        violations_by_code=violations_by_code,
        violation_edges=truncated_edges,
        violation_edges_total_count=violation_edges_total_count,
        violation_edges_truncated=violation_edges_total_count > len(truncated_edges),
        same_number_probes=same_number_probes,
        same_number_probe_count=len(same_number_probes),
        dep_ordinal_equals_source_ref_ordinal_count=sum(
            1 for probe in same_number_probes if probe.dep_ordinal_equals_source_ref_ordinal
        ),
        connection_ref_not_visible_count=connection_ref_not_visible_count,
        per_step_connection_counts=per_step_connection_counts,
        per_step_cross_step_connection_counts=per_step_cross_step_connection_counts,
        per_step_inbound_dep_counts=per_step_inbound_dep_counts,
    )


def _extract_step_shape(step: object) -> _StepShape:
    if isinstance(step, dict):
        step_id = step.get("step_id")
        depends_on = step.get("depends_on")
        evidence = step.get("evidence")
        block_refs = step.get("block_refs")
        connection_hints = step.get("connection_hints")
    else:
        step_id = getattr(step, "step_id", None)
        depends_on = getattr(step, "depends_on", None)
        evidence = getattr(step, "evidence", None)
        block_refs = getattr(step, "block_refs", None)
        connection_hints = getattr(step, "connection_hints", None)
    if not isinstance(depends_on, list):
        depends_on_items: list[object] = []
    else:
        depends_on_items = list(depends_on)
    return _StepShape(
        step_id=step_id,
        depends_on=depends_on_items,
        block_ref_ids=_block_ref_ids(block_refs),
        connection_ref_pairs=_connection_ref_pairs(connection_hints),
        connection_ref_ids=_connection_ref_ids(connection_hints),
        chosen_source_ref_ordinal=_chosen_source_ref_ordinal(evidence),
    )


def _build_edge_records(
    steps: list[_StepShape],
    step_id_counts: Counter[str],
) -> list[_EdgeRecord]:
    index_by_id: dict[str, int] = {}
    for index, step in enumerate(steps):
        step_id = step.step_id
        if isinstance(step_id, str) and step_id_counts[step_id] == 1:
            index_by_id[step_id] = index

    records: list[_EdgeRecord] = []
    for step_index, step in enumerate(steps):
        step_id = step.step_id
        step_match = _STEP_ID_ASCII_RE.fullmatch(step_id) if isinstance(step_id, str) else None
        for dep_text in step.depends_on:
            dep_match = _STEP_ID_ASCII_RE.fullmatch(dep_text) if isinstance(dep_text, str) else None
            dep_match_count = step_id_counts[dep_text] if isinstance(dep_text, str) else 0
            dep_index = (
                index_by_id[dep_text]
                if isinstance(dep_text, str) and dep_match_count == 1
                else None
            )
            records.append(
                _EdgeRecord(
                    step_index=step_index,
                    step_id_conforming=step_match is not None,
                    step_ordinal=int(step_match.group(1)) if step_match else None,
                    dep_text=dep_text,
                    dep_conforming=dep_match is not None,
                    dep_ordinal=int(dep_match.group(1)) if dep_match else None,
                    dep_match_count=dep_match_count,
                    dep_index=dep_index,
                )
            )
    return records


def _edge_violation(
    record: _EdgeRecord,
    violation: DependencyViolationCode,
    *,
    dep_length_bucket: str | None = None,
    cycle_length_bucket: str | None = None,
) -> DependencyViolationEdge:
    return DependencyViolationEdge(
        step_index=record.step_index,
        step_id_conforming=record.step_id_conforming,
        dep_conforming=record.dep_conforming,
        dep_match_count=record.dep_match_count,
        dep_index=record.dep_index,
        violation=violation,
        dep_length_bucket=dep_length_bucket,
        cycle_length_bucket=cycle_length_bucket,
    )


def _cycle_edge_keys(edge_records: list[_EdgeRecord]) -> set[tuple[int, int]]:
    graph: dict[int, list[int]] = {}
    for record in edge_records:
        if record.dep_index is not None:
            graph.setdefault(record.step_index, []).append(record.dep_index)

    visiting: set[int] = set()
    visited: set[int] = set()
    stack: list[int] = []
    cycle_edges: set[tuple[int, int]] = set()

    def visit(node: int) -> None:
        if node in visited:
            return
        if node in visiting:
            return
        visiting.add(node)
        stack.append(node)
        for dep_index in graph.get(node, []):
            if dep_index in visiting:
                cycle_start = stack.index(dep_index)
                cycle_nodes = stack[cycle_start:] + [dep_index]
                for from_index, to_index in zip(cycle_nodes, cycle_nodes[1:], strict=False):
                    cycle_edges.add((from_index, to_index))
            else:
                visit(dep_index)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cycle_edges


def _not_prior_edge_keys(
    edge_records: list[_EdgeRecord],
    cycle_edges: set[tuple[int, int]],
    total_steps: int,
) -> set[tuple[int, int]]:
    graph: dict[int, list[int]] = {index: [] for index in range(total_steps)}
    for record in edge_records:
        dep_index = record.dep_index
        if dep_index is None:
            continue
        key = (record.step_index, dep_index)
        if key in cycle_edges:
            continue
        graph[record.step_index].append(dep_index)

    remaining = set(range(total_steps))
    ordered: list[int] = []
    while remaining:
        ready = [
            index
            for index in remaining
            if all(dep_index not in remaining for dep_index in graph.get(index, []))
        ]
        if not ready:
            return set()
        ready.sort()
        next_index = ready[0]
        remaining.remove(next_index)
        ordered.append(next_index)

    seen: set[int] = set()
    not_prior: set[tuple[int, int]] = set()
    for step_index in ordered:
        for dep_index in graph.get(step_index, []):
            if dep_index not in seen:
                not_prior.add((step_index, dep_index))
        seen.add(step_index)
    return not_prior


def _same_number_probes(
    steps: list[_StepShape],
    edge_records: list[_EdgeRecord],
) -> list[DependencySameNumberProbe]:
    probes: list[DependencySameNumberProbe] = []
    for record in edge_records:
        step_ordinal = record.step_ordinal
        dep_ordinal = record.dep_ordinal
        source_ordinal = steps[record.step_index].chosen_source_ref_ordinal
        if step_ordinal is None or dep_ordinal is None or source_ordinal is None:
            continue
        probes.append(
            DependencySameNumberProbe(
                step_ordinal=step_ordinal,
                dep_ordinal=dep_ordinal,
                chosen_source_ref_ordinal=source_ordinal,
                dep_ordinal_equals_source_ref_ordinal=dep_ordinal == source_ordinal,
            )
        )
    return probes


def _connection_ref_not_visible_count(
    steps: list[_StepShape],
    edge_records: list[_EdgeRecord],
) -> int:
    deps_by_step: dict[int, list[int]] = {index: [] for index in range(len(steps))}
    for record in edge_records:
        if record.dep_match_count == 1 and record.dep_index is not None:
            deps_by_step[record.step_index].append(record.dep_index)

    total = 0
    for step_index, step in enumerate(steps):
        visible_step_indexes = {step_index, *_dependency_closure_indexes(step_index, deps_by_step)}
        visible_refs = [
            block_ref_id
            for visible_step_index in visible_step_indexes
            for block_ref_id in steps[visible_step_index].block_ref_ids
            if isinstance(block_ref_id, str)
        ]
        visible_counts = Counter(visible_refs)
        for connection_ref_id in step.connection_ref_ids:
            if (
                not isinstance(connection_ref_id, str)
                or visible_counts.get(connection_ref_id, 0) != 1
            ):
                total += 1
    return total


def _per_step_cross_step_connection_counts(
    steps: list[_StepShape],
    edge_records: list[_EdgeRecord],
) -> list[int]:
    deps_by_step = _deps_by_step(steps, edge_records)
    counts: list[int] = []
    for step_index, step in enumerate(steps):
        visible_step_indexes = {step_index, *_dependency_closure_indexes(step_index, deps_by_step)}
        visible_refs = [
            block_ref_id
            for visible_step_index in visible_step_indexes
            for block_ref_id in steps[visible_step_index].block_ref_ids
            if isinstance(block_ref_id, str)
        ]
        visible_counts = Counter(visible_refs)
        unique_visible_ref_owner: dict[str, int] = {}
        for visible_step_index in visible_step_indexes:
            for block_ref_id in steps[visible_step_index].block_ref_ids:
                if isinstance(block_ref_id, str) and visible_counts.get(block_ref_id, 0) == 1:
                    unique_visible_ref_owner[block_ref_id] = visible_step_index

        cross_step_count = 0
        for from_ref, to_ref in step.connection_ref_pairs:
            if _pair_has_cross_step_ref(
                from_ref,
                to_ref,
                step_index=step_index,
                unique_visible_ref_owner=unique_visible_ref_owner,
            ):
                cross_step_count += 1
        counts.append(cross_step_count)
    return counts


def _pair_has_cross_step_ref(
    from_ref: object,
    to_ref: object,
    *,
    step_index: int,
    unique_visible_ref_owner: dict[str, int],
) -> bool:
    for ref in (from_ref, to_ref):
        if isinstance(ref, str) and unique_visible_ref_owner.get(ref) not in {None, step_index}:
            return True
    return False


def _per_step_inbound_dep_counts(
    steps: list[_StepShape],
    edge_records: list[_EdgeRecord],
) -> list[int]:
    counts = [0 for _ in steps]
    for record in edge_records:
        dep_index = record.dep_index
        if record.dep_match_count == 1 and dep_index is not None and dep_index != record.step_index:
            counts[dep_index] += 1
    return counts


def _deps_by_step(
    steps: list[_StepShape],
    edge_records: list[_EdgeRecord],
) -> dict[int, list[int]]:
    deps_by_step: dict[int, list[int]] = {index: [] for index in range(len(steps))}
    for record in edge_records:
        if record.dep_match_count == 1 and record.dep_index is not None:
            deps_by_step[record.step_index].append(record.dep_index)
    return deps_by_step


def _dependency_closure_indexes(
    step_index: int,
    deps_by_step: dict[int, list[int]],
) -> set[int]:
    closure: set[int] = set()

    def visit(index: int) -> None:
        for dep_index in deps_by_step.get(index, []):
            if dep_index in closure:
                continue
            closure.add(dep_index)
            visit(dep_index)

    visit(step_index)
    return closure


def _block_ref_ids(block_refs: object) -> list[object]:
    if not isinstance(block_refs, list):
        return []
    result: list[object] = []
    for block_ref in block_refs:
        if isinstance(block_ref, dict):
            result.append(block_ref.get("block_ref_id"))
        else:
            result.append(getattr(block_ref, "block_ref_id", None))
    return result


def _connection_ref_ids(connection_hints: object) -> list[object]:
    if not isinstance(connection_hints, list):
        return []
    result: list[object] = []
    for from_ref, to_ref in _connection_ref_pairs(connection_hints):
        result.append(from_ref)
        result.append(to_ref)
    return result


def _connection_ref_pairs(connection_hints: object) -> list[tuple[object, object]]:
    if not isinstance(connection_hints, list):
        return []
    result: list[tuple[object, object]] = []
    for connection_hint in connection_hints:
        if isinstance(connection_hint, dict):
            result.append(
                (
                    connection_hint.get("from_block_ref"),
                    connection_hint.get("to_block_ref"),
                )
            )
        else:
            result.append(
                (
                    getattr(connection_hint, "from_block_ref", None),
                    getattr(connection_hint, "to_block_ref", None),
                )
            )
    return result


def _chosen_source_ref_ordinal(evidence: object) -> int | None:
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str):
            continue
        match = _SOURCE_REF_ASCII_RE.fullmatch(source_ref)
        if match is not None:
            return int(match.group(1))
    return None


def _length_bucket(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    length = len(value)
    if length == 0:
        return "0"
    if length <= 8:
        return "1-8"
    if length <= 32:
        return "9-32"
    if length <= 128:
        return "33-128"
    return "129+"


def _cycle_length_bucket(length: int) -> str | None:
    if length <= 0:
        return None
    if length == 1:
        return "1"
    if length == 2:
        return "2"
    if length == 3:
        return "3"
    if length <= 8:
        return "4-8"
    return "9+"
