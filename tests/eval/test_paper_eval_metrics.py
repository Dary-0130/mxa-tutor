from __future__ import annotations

from eval._paper_eval_metrics import (
    MISSING_VALUE_SENTINEL,
    compute_a1_field_coverage,
    compute_b1_b2,
    compute_c3_param_mapping_coverage,
    compute_d1_mscript_shape,
    is_unitless,
)


def test_compute_c3_excludes_sentinel_mappings() -> None:
    actual = {
        "parameter_mapping": [
            {"paper_param_name": "PN", "value": "200e6"},
            {"paper_param_name": "H", "value": MISSING_VALUE_SENTINEL},
        ]
    }
    golden = {
        "parameter_mapping": [
            {"paper_param_name": "PN", "value": "200e6"},
            {"paper_param_name": "H", "value": "3.5"},
        ]
    }

    assert compute_c3_param_mapping_coverage(actual, golden) == 0.5


def test_is_unitless_returns_true_for_null_and_em_dash() -> None:
    assert is_unitless(None)
    assert is_unitless("—")
    assert not is_unitless("s")


def test_compute_d1_mscript_shape_handles_null() -> None:
    assert compute_d1_mscript_shape(None) == {
        "has_params": None,
        "has_equations": None,
        "has_plot": None,
    }


def test_compute_a1_field_coverage_basic() -> None:
    golden = {
        "paper_title": "t",
        "paper_type": "report",
        "domain": "motor_control",
        "abstract": "a",
        "equations": [{"equation_id": "EQ-1"}],
        "parameter_table": [{"symbol": "PN"}],
        "figure_locations": [],
        "pseudocode_blocks": ["x"],
        "evidence": [{"source": "document_extracted"}],
    }
    actual = {
        "paper_title": "t",
        "paper_type": "report",
        "domain": "motor_control",
        "abstract": "a",
        "equations": [],
        "parameter_table": [{"symbol": "PN"}],
        "pseudocode_blocks": ["x"],
        "evidence": [{"source": "document_extracted"}],
    }

    assert compute_a1_field_coverage(actual, golden) == 7 / 8


def test_compute_b1_b2_recall_precision() -> None:
    actual = [
        {"parameter_name": "H"},
        {"parameter_name": "F"},
        {"parameter_name": "extra"},
    ]
    golden = [
        {"parameter_name": "H"},
        {"parameter_name": "F"},
        {"parameter_name": "alpha0"},
    ]

    assert compute_b1_b2(actual, golden) == (2 / 3, 2 / 3)
