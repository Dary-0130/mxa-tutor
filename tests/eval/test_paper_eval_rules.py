from __future__ import annotations

from eval._paper_eval_dynamic_id_adapter import AdapterBinding
from eval._paper_eval_rules import compute_material_rules, compute_missing_rules, compute_verdict


def test_missing_rules_pass_for_one_to_one_user_supplied_chain() -> None:
    rules = compute_missing_rules(
        actual_prompts=_prompts(),
        actual_plan=_plan(user_filled=False),
        actual_updated_plan=_plan(user_filled=True),
        actual_bindings=_bindings(),
        adapted_responses=_responses(),
        adapter_bindings=[
            AdapterBinding("MISS-001", "MISS-101", "同步发电机惯性时间常数 H"),
            AdapterBinding("MISS-002", "MISS-102", "同步发电机摩擦因数 F"),
        ],
        adapter_failures=[],
        document_facts=_document_facts(),
        e1_status="Pass",
    )

    assert {name: rule["status"] for name, rule in rules.items()} == {
        "r1a_pre": "pass",
        "r1a_post": "pass",
        "r2": "pass",
        "r3": "pass",
        "r4": "pass",
        "r5": "pass",
        "e1": "pass",
    }
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="succeeded",
            rule_results=rules,
        )
        == "pass"
    )


def test_r2_fails_when_actual_prompt_conflicts_with_document_given_value() -> None:
    rules = compute_missing_rules(
        actual_prompts=[{"prompt_id": "MISS-001", "parameter_name": "额定有功功率 PN"}],
        actual_plan=_plan(user_filled=False),
        actual_updated_plan=_plan(user_filled=True),
        actual_bindings=_bindings()[:1],
        adapted_responses=_responses()[:1],
        adapter_bindings=[AdapterBinding("MISS-001", "MISS-001", "额定有功功率 PN")],
        adapter_failures=[],
        document_facts=_document_facts(),
        e1_status="Pass",
    )

    assert rules["r2"]["status"] == "fail"
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="succeeded",
            rule_results=rules,
        )
        == "fail"
    )


def test_missing_rules_allow_extra_unresolved_prompts_outside_fixture_bound_chain() -> None:
    prompts = [
        *_prompts(),
        {"prompt_id": "MISS-999", "parameter_name": "励磁电压 Vf0"},
    ]
    bindings = [
        *_bindings(),
        {
            "prompt_id": "MISS-999",
            "paper_param_name": "励磁电压 Vf0",
            "model_param_name": "Synchronous Machine.Vf0",
        },
    ]

    rules = compute_missing_rules(
        actual_prompts=prompts,
        actual_plan=_plan_with_extra_unresolved(user_filled=False),
        actual_updated_plan=_plan_with_extra_unresolved(user_filled=True),
        actual_bindings=bindings,
        adapted_responses=_responses(),
        adapter_bindings=[
            AdapterBinding("MISS-001", "MISS-101", "同步发电机惯性时间常数 H"),
            AdapterBinding("MISS-002", "MISS-102", "同步发电机摩擦因数 F"),
        ],
        adapter_failures=[],
        document_facts=_document_facts(),
        e1_status="Pass",
    )

    assert rules["r1a_post"]["status"] == "pass"
    assert rules["r4"]["status"] == "pass"
    assert (
        compute_verdict(
            case_kind="missing_param",
            execution_status="succeeded",
            rule_results=rules,
        )
        == "pass"
    )


def test_r5_fails_on_canonical_name_drift() -> None:
    responses = _responses()
    responses[0] = {**responses[0], "parameter_name": "漂移参数名"}

    rules = compute_missing_rules(
        actual_prompts=_prompts(),
        actual_plan=_plan(user_filled=False),
        actual_updated_plan=_plan(user_filled=True),
        actual_bindings=_bindings(),
        adapted_responses=responses,
        adapter_bindings=[
            AdapterBinding("MISS-001", "MISS-101", "同步发电机惯性时间常数 H"),
            AdapterBinding("MISS-002", "MISS-102", "同步发电机摩擦因数 F"),
        ],
        adapter_failures=[],
        document_facts=_document_facts(),
        e1_status="Pass",
    )

    assert rules["r5"]["status"] == "fail"


def test_material_r3_replaces_old_e2_user_supplied_pollution_check() -> None:
    clean = compute_material_rules(
        metrics=_perfect_material_metrics(),
        actual_plan={
            "parameter_mapping": [{"paper_param_name": "PN", "source": "document_extracted"}]
        },
    )
    polluted = compute_material_rules(
        metrics=_perfect_material_metrics(),
        actual_plan={"parameter_mapping": [{"paper_param_name": "H", "source": "user_supplied"}]},
    )

    assert clean["r3"]["status"] == "pass"
    assert polluted["r3"]["status"] == "fail"
    assert (
        compute_verdict(
            case_kind="material_to_plan",
            execution_status="succeeded",
            rule_results=polluted,
        )
        == "fail"
    )


def _prompts() -> list[dict[str, str]]:
    return [
        {"prompt_id": "MISS-101", "parameter_name": "同步发电机惯性时间常数 H"},
        {"prompt_id": "MISS-102", "parameter_name": "同步发电机摩擦因数 F"},
    ]


def _bindings() -> list[dict[str, str]]:
    return [
        {
            "prompt_id": "MISS-101",
            "paper_param_name": "同步发电机惯性时间常数 H",
            "model_param_name": "Synchronous Machine.H",
        },
        {
            "prompt_id": "MISS-102",
            "paper_param_name": "同步发电机摩擦因数 F",
            "model_param_name": "Synchronous Machine.F",
        },
    ]


def _responses() -> list[dict[str, str]]:
    return [
        {
            "prompt_id": "MISS-101",
            "parameter_name": "同步发电机惯性时间常数 H",
            "user_supplied_value": "3.5",
            "user_supplied_unit": "s",
        },
        {
            "prompt_id": "MISS-102",
            "parameter_name": "同步发电机摩擦因数 F",
            "user_supplied_value": "0",
            "user_supplied_unit": "pu",
        },
    ]


def _plan(*, user_filled: bool) -> dict[str, object]:
    user_source = "user_supplied" if user_filled else "document_extracted"
    return {
        "parameter_mapping": [
            {
                "paper_param_name": "PN",
                "model_param_name": "Synchronous Machine.Pn",
                "value": "200e6",
                "unit": "VA",
                "source": "document_extracted",
            },
            {
                "paper_param_name": "同步发电机惯性时间常数 H",
                "model_param_name": "Synchronous Machine.H",
                "value": "3.5" if user_filled else "null",
                "unit": "s",
                "source": user_source,
            },
            {
                "paper_param_name": "同步发电机摩擦因数 F",
                "model_param_name": "Synchronous Machine.F",
                "value": "0" if user_filled else "null",
                "unit": "pu",
                "source": user_source,
            },
        ],
        "evidence": [
            {"source": "document_extracted", "paper_section_id": "S2", "excerpt": "PN = 200 MW"},
            {
                "source": "user_supplied",
                "paper_section_id": None,
                "equation_id": None,
                "figure_id": None,
                "excerpt": None,
                "missing_param_prompt_id": "MISS-101",
            },
            {
                "source": "user_supplied",
                "paper_section_id": None,
                "equation_id": None,
                "figure_id": None,
                "excerpt": None,
                "missing_param_prompt_id": "MISS-102",
            },
        ]
        if user_filled
        else [{"source": "document_extracted", "paper_section_id": "S2", "excerpt": "PN = 200 MW"}],
    }


def _plan_with_extra_unresolved(*, user_filled: bool) -> dict[str, object]:
    plan = _plan(user_filled=user_filled)
    mappings = plan["parameter_mapping"]
    assert isinstance(mappings, list)
    mappings.append(
        {
            "paper_param_name": "励磁电压 Vf0",
            "model_param_name": "Synchronous Machine.Vf0",
            "value": "null",
            "unit": "pu",
            "source": "document_extracted",
        }
    )
    return plan


def _document_facts() -> dict[str, object]:
    return {
        "document_given_values": [{"canonical_param_name": "额定有功功率 PN"}],
        "document_not_mentioned": [{"canonical_param_name": "励磁调节器增益"}],
    }


def _perfect_material_metrics() -> dict[str, object]:
    return {
        "A1": 1.0,
        "C2": 1.0,
        "C3": 1.0,
        "D1": {"has_params": True, "has_equations": True, "has_plot": True},
        "E1": "Pass",
    }
