"""Automatic paper-to-model evaluator metrics."""

from __future__ import annotations

from typing import Any

from features.paper.paper_plan_helpers import MISSING_VALUE_SENTINEL

PAPER_SPEC_FIELDS = (
    "paper_title",
    "paper_type",
    "domain",
    "abstract",
    "equations",
    "parameter_table",
    "figure_locations",
    "pseudocode_blocks",
    "evidence",
)


def compute_a1_field_coverage(actual_spec: Any, golden_spec: Any) -> float:
    """A1 PaperSpec field coverage against the nine golden fields."""
    required_fields = [field for field in PAPER_SPEC_FIELDS if _has_value(golden_spec, field)]
    if not required_fields:
        return 1.0
    covered = sum(1 for field in required_fields if _has_value(actual_spec, field))
    return covered / len(required_fields)


def compute_c2_block_coverage(actual_plan: Any, golden_plan: Any) -> float:
    """C2 block coverage by block_type set overlap."""
    actual_blocks = {
        _norm(_field(block, "block_type"))
        for block in _list_field(actual_plan, "block_recommendations")
    }
    golden_blocks = {
        _norm(_field(block, "block_type"))
        for block in _list_field(golden_plan, "block_recommendations")
    }
    actual_blocks.discard("")
    golden_blocks.discard("")
    if not golden_blocks:
        return 1.0
    return len(actual_blocks & golden_blocks) / len(golden_blocks)


def compute_c3_param_mapping_coverage(actual_plan: Any, golden_plan: Any) -> float:
    """C3 parameter mapping coverage, excluding sentinel placeholder values."""
    actual_params = _non_sentinel_param_names(actual_plan)
    golden_params = _non_sentinel_param_names(golden_plan)
    if not golden_params:
        return 1.0
    return len(actual_params & golden_params) / len(golden_params)


def compute_d1_mscript_shape(m_script: str | None) -> dict[str, bool | None]:
    """D1 .m skeleton shape; None marks N/A for the best-effort code artifact."""
    if m_script is None:
        return {"has_params": None, "has_equations": None, "has_plot": None}
    lowered = m_script.lower()
    return {
        "has_params": "参数" in m_script or "parameter" in lowered,
        "has_equations": "方程" in m_script or "equation" in lowered or "=" in m_script,
        "has_plot": "plot" in lowered or "subplot" in lowered or "figure" in lowered,
    }


def is_unitless(unit: str | None) -> bool:
    """D5 unitless equivalence class."""
    return unit is None or unit == "—"


def _non_sentinel_param_names(plan: Any) -> set[str]:
    names: set[str] = set()
    for mapping in _list_field(plan, "parameter_mapping"):
        if _field(mapping, "value") == MISSING_VALUE_SENTINEL:
            continue
        name = _norm(_field(mapping, "paper_param_name"))
        if name:
            names.add(name)
    return names


def _list_field(value: Any, field_name: str) -> list[Any]:
    field = _field(value, field_name)
    return field if isinstance(field, list) else []


def _has_value(value: Any, field_name: str) -> bool:
    field = _field(value, field_name)
    if field is None:
        return False
    if isinstance(field, str):
        return bool(field.strip())
    if isinstance(field, list | tuple | dict | set):
        return bool(field)
    return True


def _field(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _norm(value: Any) -> str:
    return str(value).strip().casefold() if value is not None else ""
