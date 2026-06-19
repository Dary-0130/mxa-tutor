"""CSV writer for semi-automatic paper-to-model evaluation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Literal

ExecutionStatus = Literal["succeeded", "blocked_known_defect"]
Verdict = Literal["pass", "partial", "fail"]

FIELDNAMES = [
    "case_id",
    "execution_status",
    "verdict",
    "failure",
    "O1_plan_executability",
    "O2_user_supply_update",
    "A1_field_coverage",
    "B1_missing_recall",
    "B2_missing_precision",
    "C2_block_coverage",
    "C3_param_mapping_coverage",
    "D1_has_params",
    "D1_has_equations",
    "D1_has_plot",
    "E1_evidence_invariant",
    "E2_user_supplied_source",
    "A2_no_hallucination_manual",
    "C1_library_choice_manual",
    "origin_inherited_notes",
]


def write_paper_eval_csv(
    case_id: str,
    layer1_outcome: dict[str, Any],
    layer2_metrics: dict[str, Any],
    layer2_manual: dict[str, Any],
    execution_status: ExecutionStatus,
    verdict: Verdict | None,
    failure: str | None,
    output_path: Path,
) -> None:
    """Write one paper-to-model evaluation row."""
    _validate_state(execution_status=execution_status, failure=failure)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "execution_status": execution_status,
        "verdict": verdict or "",
        "failure": failure or "",
        "O1_plan_executability": _csv_value(layer1_outcome.get("O1", "")),
        "O2_user_supply_update": _csv_value(layer1_outcome.get("O2", "")),
        "A1_field_coverage": _csv_value(layer2_metrics.get("A1", "")),
        "B1_missing_recall": _csv_value(layer2_metrics.get("B1", "")),
        "B2_missing_precision": _csv_value(layer2_metrics.get("B2", "")),
        "C2_block_coverage": _csv_value(layer2_metrics.get("C2", "")),
        "C3_param_mapping_coverage": _csv_value(layer2_metrics.get("C3", "")),
        "D1_has_params": _csv_value(layer2_metrics.get("D1", {}).get("has_params", "")),
        "D1_has_equations": _csv_value(layer2_metrics.get("D1", {}).get("has_equations", "")),
        "D1_has_plot": _csv_value(layer2_metrics.get("D1", {}).get("has_plot", "")),
        "E1_evidence_invariant": _csv_value(layer2_metrics.get("E1", "")),
        "E2_user_supplied_source": _csv_value(layer2_metrics.get("E2", "")),
        "A2_no_hallucination_manual": _csv_value(layer2_manual.get("A2", "")),
        "C1_library_choice_manual": _csv_value(layer2_manual.get("C1", "")),
        "origin_inherited_notes": _csv_value(layer2_manual.get("origin_inherited_notes", "")),
    }
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)


def _validate_state(*, execution_status: ExecutionStatus, failure: str | None) -> None:
    if execution_status == "succeeded" and failure is not None:
        raise ValueError("succeeded rows must not include failure")
    if execution_status == "blocked_known_defect" and not failure:
        raise ValueError("blocked_known_defect rows require failure")


def _csv_value(value: Any) -> Any:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return value
