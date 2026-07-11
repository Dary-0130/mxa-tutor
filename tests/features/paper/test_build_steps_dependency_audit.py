import json

import pytest

import features.paper.build_steps_dependency_audit as subject
from features.paper.build_steps_dependency_audit import (
    audit_step_dependencies,
    audit_step_dependencies_from_payload,
)


def test_audit_records_self_dependency_by_index_only() -> None:
    audit = audit_step_dependencies(
        [
            _step(1, []),
            _step(2, ["STEP-001"]),
            _step(3, ["STEP-003"], source_ref="REF-003"),
        ]
    )

    assert audit.dependency_audit_status == "violations"
    assert audit.violations_by_code["self"] == 1
    assert audit.violation_edges[0].step_index == 2
    assert audit.violation_edges[0].dep_index == 2
    assert audit.violation_edges[0].step_id_conforming is True
    assert audit.violation_edges[0].dep_conforming is True
    assert audit.dep_ordinal_equals_source_ref_ordinal_count == 1


def test_audit_records_multiple_violating_edges() -> None:
    audit = audit_step_dependencies(
        [
            _step(1, []),
            _step(2, ["STEP-999"]),
            _step(3, ["STEP-003"]),
        ]
    )

    assert audit.violation_edges_total_count == 2
    assert [edge.violation for edge in audit.violation_edges] == ["unknown", "self"]
    assert audit.violations_by_code == {"self": 1, "unknown": 1, "cycle": 0, "not_prior": 0}


def test_audit_classifies_unknown_cycle_and_topo_accepted_order() -> None:
    unknown = audit_step_dependencies([_step(1, ["STEP-999"]), _step(2, []), _step(3, [])])
    cycle = audit_step_dependencies([_step(1, ["STEP-002"]), _step(2, ["STEP-001"]), _step(3, [])])
    topo_accepted = audit_step_dependencies(
        [_step(2, ["STEP-001"]), _step(1, []), _step(3, ["STEP-002"])]
    )

    assert unknown.violations_by_code["unknown"] == 1
    assert cycle.violations_by_code["cycle"] == 2
    assert {edge.cycle_length_bucket for edge in cycle.violation_edges} == {"2"}
    assert topo_accepted.dependency_audit_status == "clean"
    assert topo_accepted.violations_by_code["not_prior"] == 0


def test_audit_counts_duplicate_step_ids_and_does_not_choose_ambiguous_dep() -> None:
    audit = audit_step_dependencies(
        [
            _step(1, [], step_id="STEP-001"),
            _step(2, [], step_id="STEP-001"),
            _step(3, ["STEP-001"]),
        ]
    )

    assert audit.dependency_audit_status == "violations"
    assert audit.duplicate_step_id_count == 1
    assert audit.violation_edges[0].violation == "ambiguous"
    assert audit.violation_edges[0].dep_match_count == 2
    assert audit.violation_edges[0].dep_index is None


def test_audit_records_empty_graph_shape() -> None:
    audit = audit_step_dependencies([_step(1, []), _step(2, []), _step(3, [])])

    assert audit.dependency_audit_status == "clean"
    assert audit.total_steps == 3
    assert audit.total_dep_edges == 0
    assert audit.dep_edge_density == 0
    assert audit.all_empty_dependency_graph is True
    assert audit.nonfirst_steps_with_empty_depends_on == 2
    assert audit.connection_ref_not_visible_count == 0


def test_audit_counts_connection_refs_not_visible_without_recording_ids() -> None:
    audit = audit_step_dependencies(
        [
            _step(1, [], block_ref_ids=["B1"]),
            _step(2, [], block_ref_ids=["B2"]),
            _step(3, ["STEP-001"], block_ref_ids=["B3"], connection_refs=["B3", "B2"]),
        ]
    )
    payload = json.dumps(audit.to_dict(), ensure_ascii=False)

    assert audit.connection_ref_not_visible_count == 1
    assert "B2" not in payload


def test_audit_truncates_violation_edges_but_preserves_total_count() -> None:
    audit = audit_step_dependencies(
        [_step(1, [f"STEP-{index:03d}" for index in range(100, 160)]), _step(2, []), _step(3, [])],
        max_violation_edges=3,
    )

    assert audit.violation_edges_total_count == 60
    assert len(audit.violation_edges) == 3
    assert audit.violation_edges_truncated is True


def test_audit_unavailable_for_payload_without_steps_array() -> None:
    audit = audit_step_dependencies_from_payload({"not_build_steps": []})

    assert audit.dependency_audit_status == "unavailable"
    assert audit.unavailable_stage == "draft_parse"


def test_audit_error_is_swallowed_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> subject.DependencyAudit:
        raise RuntimeError("forced")

    monkeypatch.setattr(subject, "_audit_step_dependencies_unchecked", boom)

    audit = audit_step_dependencies([])

    assert audit.dependency_audit_status == "unavailable"
    assert audit.unavailable_stage == "audit_error"


@pytest.mark.parametrize(
    "dependency",
    [
        "STEP-002 求解第3.2节",
        "STEP-002\n正文",
        "ＳＴＥＰ-002",
        "STEP-002\u200b",
        "STEP-002\x00secret-tail",
        "STEP-002" + "x" * 200,
    ],
)
def test_nonconforming_dependency_strings_are_bucketed_not_recorded(dependency: str) -> None:
    audit = audit_step_dependencies([_step(1, []), _step(2, [dependency]), _step(3, [])])
    payload = json.dumps(audit.to_dict(), ensure_ascii=False)

    assert audit.violation_edges[0].dep_conforming is False
    assert audit.violation_edges[0].dep_length_bucket is not None
    assert dependency not in payload
    assert dependency[:8] not in payload


def _step(
    ordinal: int,
    depends_on: list[str],
    *,
    step_id: str | None = None,
    source_ref: str | None = None,
    block_ref_ids: list[str] | None = None,
    connection_refs: list[str] | None = None,
) -> dict[str, object]:
    evidence = [{"source_ref": source_ref}] if source_ref is not None else []
    block_refs = [
        {"block_ref_id": block_ref_id, "block_type": "Gain", "purpose": "Scale"}
        for block_ref_id in block_ref_ids or []
    ]
    connection_hints = []
    if connection_refs:
        connection_hints.append(
            {
                "from_block_ref": connection_refs[0],
                "to_block_ref": connection_refs[1] if len(connection_refs) > 1 else None,
            }
        )
    return {
        "step_id": step_id or f"STEP-{ordinal:03d}",
        "depends_on": depends_on,
        "evidence": evidence,
        "block_refs": block_refs,
        "connection_hints": connection_hints,
    }
