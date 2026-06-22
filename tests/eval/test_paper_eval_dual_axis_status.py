from __future__ import annotations

from pathlib import Path

import pytest

from eval._paper_eval_csv import write_paper_eval_csv
from eval._paper_eval_rules import compute_verdict, execution_status_and_verdict_from_legacy


def test_case_failed_requires_not_evaluated_verdict(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not_evaluated"):
        write_paper_eval_csv(
            case_id="case",
            layer1_outcome={},
            layer2_metrics={},
            layer2_manual={},
            execution_status="case_failed",
            verdict="fail",
            failure="merge_failed",
            output_path=tmp_path / "bad.csv",
        )


def test_succeeded_rejects_not_evaluated_verdict(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pass/partial/fail"):
        write_paper_eval_csv(
            case_id="case",
            layer1_outcome={},
            layer2_metrics={},
            layer2_manual={},
            execution_status="succeeded",
            verdict="not_evaluated",
            failure=None,
            output_path=tmp_path / "bad.csv",
        )


def test_legacy_blocked_known_defect_maps_to_case_failed_not_evaluated() -> None:
    assert execution_status_and_verdict_from_legacy("blocked_known_defect", None) == (
        "case_failed",
        "not_evaluated",
    )


def test_compute_verdict_uses_dual_axis_invariants() -> None:
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="case_failed",
            rule_results={},
        )
        == "not_evaluated"
    )
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="succeeded",
            rule_results={
                "r1a_pre": {"status": "pass"},
                "r1a_post": {"status": "pass"},
                "r2": {"status": "pass"},
                "r3": {"status": "pass"},
                "r4": {"status": "pass"},
                "r5": {"status": "pass"},
                "e1": {"status": "pass"},
            },
        )
        == "pass"
    )
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="succeeded",
            rule_results={
                "r1a_pre": {"status": "fail"},
                "r1a_post": {"status": "pass"},
                "r2": {"status": "pass"},
                "r3": {"status": "pass"},
                "r4": {"status": "pass"},
                "r5": {"status": "pass"},
                "e1": {"status": "pass"},
            },
        )
        == "fail"
    )


def test_error_explanation_verdict_has_no_partial() -> None:
    passing_rules = {
        "error_mapping": {"status": "pass"},
        "schema_contract": {"status": "pass"},
        "privacy": {"status": "pass"},
        "timeout": {"status": "pass"},
        "grounding_hygiene": {"status": "pass"},
    }
    failing_rules = {**passing_rules, "privacy": {"status": "fail"}}

    assert (
        compute_verdict(
            case_kind="error_explanation",
            execution_status="succeeded",
            rule_results=passing_rules,
        )
        == "pass"
    )
    assert (
        compute_verdict(
            case_kind="error_explanation",
            execution_status="succeeded",
            rule_results=failing_rules,
        )
        == "fail"
    )
    assert (
        compute_verdict(
            case_kind="error_explanation",
            execution_status="case_failed",
            rule_results=passing_rules,
        )
        == "not_evaluated"
    )
