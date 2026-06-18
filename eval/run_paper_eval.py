"""Run semi-automatic paper-to-model evaluator."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval._paper_eval_csv import write_paper_eval_csv
from eval._paper_eval_metrics import (
    compute_a1_field_coverage,
    compute_b1_b2,
    compute_c2_block_coverage,
    compute_c3_param_mapping_coverage,
    compute_d1_mscript_shape,
)

CASES_ROOT = Path("eval/cases/paper_to_model")


async def main() -> int:
    parser = argparse.ArgumentParser(description="paper-to-model evaluator")
    parser.add_argument(
        "--case",
        required=True,
        help=(
            "case path under eval/cases/paper_to_model/, "
            "e.g. material_to_plan/case_01_motor_short_circuit"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("eval/out/paper_to_model"))
    args = parser.parse_args()

    case_dir = CASES_ROOT / args.case
    if not case_dir.exists():
        raise SystemExit(f"case not found: {case_dir}")

    case_id = case_dir.name
    metrics = _compute_case_metrics(case_dir)
    output_path = args.output_dir / f"{case_id}_paper_eval.csv"
    write_paper_eval_csv(
        case_id=case_id,
        layer1_outcome={"O1": "", "O2": "N/A" if "material_to_plan" in args.case else ""},
        layer2_metrics=metrics,
        layer2_manual={"A2": "", "C1": "", "origin_inherited_notes": ""},
        verdict="manual_review_required",
        output_path=output_path,
    )
    print(f"wrote {output_path}")
    print("verdict=manual_review_required")
    return 0


def _compute_case_metrics(case_dir: Path) -> dict[str, Any]:
    golden_spec = _load_optional_json(case_dir / "golden" / "expected_paper_spec.json")
    golden_plan = _load_optional_json(case_dir / "golden" / "expected_model_generation_plan.json")
    expected_updated_plan = _load_optional_json(case_dir / "golden" / "expected_updated_plan.json")
    expected_prompts = _load_optional_json(case_dir / "input" / "expected_missing_prompts.json")

    actual_spec = golden_spec or {}
    actual_plan = golden_plan or expected_updated_plan or {}
    golden_for_plan = golden_plan or expected_updated_plan or {}
    actual_prompts = expected_prompts.get("missing_prompts", []) if expected_prompts else []
    golden_prompts = actual_prompts
    b1, b2 = compute_b1_b2(actual_prompts, golden_prompts)

    return {
        "A1": compute_a1_field_coverage(actual_spec, golden_spec or actual_spec),
        "B1": b1,
        "B2": b2,
        "C2": compute_c2_block_coverage(actual_plan, golden_for_plan),
        "C3": compute_c3_param_mapping_coverage(actual_plan, golden_for_plan),
        "D1": compute_d1_mscript_shape(_field(actual_plan, "m_script_skeleton")),
        "E1": "manual_or_schema_check_required",
        "E2": _compute_e2_user_supplied_source(actual_plan),
    }


def _compute_e2_user_supplied_source(plan: dict[str, Any]) -> str:
    mappings = plan.get("parameter_mapping", [])
    if not isinstance(mappings, list):
        return "N/A"
    user_mappings = [
        mapping
        for mapping in mappings
        if isinstance(mapping, dict)
        and str(mapping.get("paper_param_name", "")).startswith("(用户补充)")
    ]
    if not user_mappings:
        return "N/A"
    return (
        "Pass"
        if all(mapping.get("source") == "user_supplied" for mapping in user_mappings)
        else "Fail"
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def _field(value: dict[str, Any], field_name: str) -> Any:
    return value.get(field_name)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
