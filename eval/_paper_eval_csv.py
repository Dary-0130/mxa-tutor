"""CSV writer for semi-automatic paper-to-model evaluation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

FIELDNAMES = [
    "case_id",
    "verdict",
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
    verdict: str,
    output_path: Path,
) -> None:
    """Write one paper-to-model evaluation row."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "verdict": verdict,
        "O1_plan_executability": layer1_outcome.get("O1", ""),
        "O2_user_supply_update": layer1_outcome.get("O2", ""),
        "A1_field_coverage": layer2_metrics.get("A1", ""),
        "B1_missing_recall": layer2_metrics.get("B1", ""),
        "B2_missing_precision": layer2_metrics.get("B2", ""),
        "C2_block_coverage": layer2_metrics.get("C2", ""),
        "C3_param_mapping_coverage": layer2_metrics.get("C3", ""),
        "D1_has_params": layer2_metrics.get("D1", {}).get("has_params", ""),
        "D1_has_equations": layer2_metrics.get("D1", {}).get("has_equations", ""),
        "D1_has_plot": layer2_metrics.get("D1", {}).get("has_plot", ""),
        "E1_evidence_invariant": layer2_metrics.get("E1", ""),
        "E2_user_supplied_source": layer2_metrics.get("E2", ""),
        "A2_no_hallucination_manual": layer2_manual.get("A2", ""),
        "C1_library_choice_manual": layer2_manual.get("C1", ""),
        "origin_inherited_notes": layer2_manual.get("origin_inherited_notes", ""),
    }
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)
