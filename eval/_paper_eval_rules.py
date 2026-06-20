"""Deterministic paper evaluator rules for TASK-503 v0.2.4."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from eval._paper_eval_dynamic_id_adapter import AdapterBinding, R1aPreFailure

RuleStatus = Literal["pass", "fail", "n/a"]
Verdict = Literal["pass", "partial", "fail", "not_evaluated"]
CaseKind = Literal["material_to_plan", "missing_param"]

MISSING_VALUE_SENTINEL = "null"


@dataclass(frozen=True)
class RuleCheck:
    """One auditable deterministic rule assertion."""

    name: str
    status: RuleStatus
    message: str
    expected: Any = None
    actual: Any = None


def compute_verdict(
    *,
    case_kind: CaseKind,
    execution_status: str,
    rule_results: dict[str, Any],
) -> Verdict:
    """Summarize per-case rule results into the public verdict axis."""

    if execution_status == "case_failed":
        return "not_evaluated"
    if execution_status != "succeeded":
        raise ValueError(f"unknown execution_status: {execution_status}")
    if case_kind == "missing_param":
        required = ("r1a_pre", "r1a_post", "r2", "r3", "r4", "r5", "e1")
        return "pass" if all(_rule_passed(rule_results.get(name)) for name in required) else "fail"
    if case_kind == "material_to_plan":
        if not _rule_passed(rule_results.get("e1")) or not _rule_passed(rule_results.get("r3")):
            return "fail"
        soft = [rule_results.get(name) for name in ("a1", "c2", "c3", "d1")]
        return "pass" if all(_soft_rule_perfect(rule) for rule in soft) else "partial"
    raise ValueError(f"unknown case kind: {case_kind}")


def execution_status_and_verdict_from_legacy(
    execution_status: str,
    verdict: str | None,
) -> tuple[str, Verdict]:
    """Map historical blocked_known_defect rows into the dual-axis model."""

    if execution_status == "blocked_known_defect":
        return "case_failed", "not_evaluated"
    if execution_status == "case_failed":
        return "case_failed", "not_evaluated"
    if execution_status == "succeeded":
        if verdict in {"pass", "partial", "fail"}:
            return "succeeded", verdict
        raise ValueError("succeeded rows require pass/partial/fail verdict")
    raise ValueError(f"unknown execution_status: {execution_status}")


def compute_material_rules(
    *,
    metrics: dict[str, Any],
    actual_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute material_to_plan rules around existing soft metrics."""

    r3 = _material_r3(actual_plan)
    return {
        "a1": _numeric_rule("a1", metrics.get("A1"), perfect=1.0),
        "c2": _numeric_rule("c2", metrics.get("C2"), perfect=1.0),
        "c3": _numeric_rule("c3", metrics.get("C3"), perfect=1.0),
        "d1": _d1_rule(metrics.get("D1")),
        "e1": _named_status_rule("e1", metrics.get("E1")),
        "r3": r3,
    }


def compute_missing_rules(
    *,
    actual_prompts: list[dict[str, Any]] | None,
    actual_plan: dict[str, Any] | None,
    actual_updated_plan: dict[str, Any] | None,
    actual_bindings: list[dict[str, Any]] | None,
    adapted_responses: list[dict[str, Any]] | None,
    adapter_bindings: list[AdapterBinding],
    adapter_failures: list[R1aPreFailure],
    document_facts: dict[str, Any] | None,
    e1_status: str,
) -> dict[str, Any]:
    """Compute missing_param deterministic dead-rule results."""

    prompts = actual_prompts or []
    bindings = actual_bindings or []
    responses = adapted_responses or []
    r1a_pre = _r1a_pre(prompts, adapter_bindings, adapter_failures, document_facts)
    r1a_post = _r1a_post(
        original_plan=actual_plan,
        updated_plan=actual_updated_plan,
        responses=responses,
    )
    r2 = _r2(prompts, document_facts)
    r3 = _missing_r3(updated_plan=actual_updated_plan, responses=responses)
    r4 = _r4(
        prompts=prompts,
        bindings=bindings,
        responses=responses,
        updated_plan=actual_updated_plan,
    )
    r5 = _r5(
        prompts=prompts,
        bindings=bindings,
        responses=responses,
        updated_plan=actual_updated_plan,
    )
    return {
        "r1a_pre": r1a_pre,
        "r1a_post": r1a_post,
        "r2": r2,
        "r3": r3,
        "r4": r4,
        "r5": r5,
        "e1": _named_status_rule("e1", e1_status),
    }


def public_rule_details(rule_results: dict[str, Any]) -> dict[str, Any]:
    """Return JSON-safe rule details."""

    return {name: _public_rule(rule) for name, rule in rule_results.items()}


def _r1a_pre(
    prompts: list[dict[str, Any]],
    adapter_bindings: list[AdapterBinding],
    adapter_failures: list[R1aPreFailure],
    document_facts: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = [
        _check(
            "actual_prompts_non_empty",
            bool(prompts),
            "runtime produced at least one missing prompt",
            expected=True,
            actual=bool(prompts),
        ),
        _check(
            "prompt_ids_unique",
            _unique(_field(prompt, "prompt_id") for prompt in prompts),
            "runtime prompt IDs are unique",
        ),
        _check(
            "prompt_names_unique",
            _unique(_field(prompt, "parameter_name") for prompt in prompts),
            "runtime prompt canonical names are unique",
        ),
        _check(
            "adapter_bound_all_fixture_entries",
            not adapter_failures and len(adapter_bindings) > 0,
            "fixture responses bind to runtime prompts by canonical name",
            expected="all fixture rows bound",
            actual=[asdict(failure) for failure in adapter_failures],
        ),
        _check(
            "r2_truth_source_available",
            isinstance(document_facts, dict)
            and isinstance(document_facts.get("document_given_values"), list)
            and isinstance(document_facts.get("document_not_mentioned"), list),
            "R2 truth source is present and machine-readable",
        ),
    ]
    return _rule("r1a_pre", checks)


def _r1a_post(
    *,
    original_plan: dict[str, Any] | None,
    updated_plan: dict[str, Any] | None,
    responses: list[dict[str, Any]],
) -> dict[str, Any]:
    if updated_plan is None:
        return _rule(
            "r1a_post",
            [
                RuleCheck(
                    name="updated_plan_present",
                    status="fail",
                    message="updated plan was not produced",
                    expected=True,
                    actual=False,
                )
            ],
        )

    user_mappings = _user_supplied_mappings(updated_plan)
    user_evidence = _user_supplied_evidence(updated_plan)
    response_by_name = {_canon(response.get("parameter_name")): response for response in responses}
    mapping_by_name = {
        _canon(mapping.get("paper_param_name")): mapping for mapping in user_mappings
    }
    evidence_ids = {
        evidence.get("missing_param_prompt_id")
        for evidence in user_evidence
        if isinstance(evidence.get("missing_param_prompt_id"), str)
    }
    checks: list[RuleCheck] = [
        _check(
            "updated_values_match_responses",
            all(
                _value_matches_response(mapping_by_name.get(name), response)
                for name, response in response_by_name.items()
            ),
            "each user value/unit is written to the matching mapping",
        ),
        _check(
            "updated_sources_user_supplied",
            all(mapping.get("source") == "user_supplied" for mapping in user_mappings),
            "all filled user mappings are marked user_supplied",
        ),
        _check(
            "one_user_evidence_per_response",
            len(user_evidence) == len(responses) and len(evidence_ids) == len(responses),
            "updated plan has exactly one user evidence entry per response",
            expected=len(responses),
            actual=len(user_evidence),
        ),
        _check(
            "document_mappings_unchanged",
            _document_mappings_unchanged(original_plan, updated_plan),
            "document_extracted mappings are not changed by merge",
        ),
    ]
    return _rule("r1a_post", checks)


def _r2(prompts: list[dict[str, Any]], document_facts: dict[str, Any] | None) -> dict[str, Any]:
    given_names = {
        _canon(item.get("canonical_param_name"))
        for item in _list_field(document_facts or {}, "document_given_values")
        if isinstance(item, dict)
    }
    not_mentioned_names = {
        _canon(item.get("canonical_param_name"))
        for item in _list_field(document_facts or {}, "document_not_mentioned")
        if isinstance(item, dict)
    }
    prompt_names = {_canon(prompt.get("parameter_name")) for prompt in prompts}
    conflicts = sorted(name for name in prompt_names if name and name in given_names)
    hallucinations = sorted(name for name in prompt_names if name and name in not_mentioned_names)
    checks = [
        _check(
            "no_document_given_value_reported_missing",
            not conflicts,
            "actual prompts do not conflict with document_given_values",
            expected=[],
            actual=conflicts,
        ),
        _check(
            "no_document_not_mentioned_hallucination",
            not hallucinations,
            "actual prompts do not report declared not-mentioned parameters",
            expected=[],
            actual=hallucinations,
        ),
    ]
    return _rule("r2", checks)


def _missing_r3(
    *,
    updated_plan: dict[str, Any] | None,
    responses: list[dict[str, Any]],
) -> dict[str, Any]:
    if updated_plan is None:
        return _rule(
            "r3",
            [RuleCheck("updated_plan_present", "fail", "updated plan was not produced")],
        )
    user_mappings = _user_supplied_mappings(updated_plan)
    doc_values = {
        str(mapping.get("value"))
        for mapping in _list_field(updated_plan, "parameter_mapping")
        if isinstance(mapping, dict) and mapping.get("source") == "document_extracted"
    }
    user_values = {str(response.get("user_supplied_value")) for response in responses}
    user_evidence = _user_supplied_evidence(updated_plan)
    checks = [
        _check(
            "user_mappings_all_user_supplied",
            len(user_mappings) == len(responses),
            "target mappings are marked user_supplied",
            expected=len(responses),
            actual=len(user_mappings),
        ),
        _check(
            "user_evidence_has_no_document_locator",
            all(
                not any(
                    (
                        entry.get("paper_section_id"),
                        entry.get("equation_id"),
                        entry.get("figure_id"),
                    )
                )
                and entry.get("excerpt") is None
                for entry in user_evidence
            ),
            "user evidence does not carry document locator or excerpt",
        ),
        _check(
            "user_values_not_document_extracted_values",
            not (user_values & doc_values),
            "user values are not copied from document_extracted mapping values",
            expected=[],
            actual=sorted(user_values & doc_values),
        ),
    ]
    return _rule("r3", checks)


def _material_r3(actual_plan: dict[str, Any] | None) -> dict[str, Any]:
    mappings = _list_field(actual_plan or {}, "parameter_mapping")
    user_mappings = [
        mapping
        for mapping in mappings
        if isinstance(mapping, dict) and mapping.get("source") == "user_supplied"
    ]
    return _rule(
        "r3",
        [
            _check(
                "no_user_supplied_mapping",
                not user_mappings,
                "material case must not contain user_supplied mappings",
                expected=0,
                actual=len(user_mappings),
            )
        ],
    )


def _r4(
    *,
    prompts: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    updated_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    user_mappings = _user_supplied_mappings(updated_plan or {})
    response_prompt_ids = {
        response.get("prompt_id")
        for response in responses
        if isinstance(response.get("prompt_id"), str)
    }
    bound_prompts = [
        prompt for prompt in prompts if _field(prompt, "prompt_id") in response_prompt_ids
    ]
    bound_bindings = [
        binding for binding in bindings if _field(binding, "prompt_id") in response_prompt_ids
    ]
    counts = {
        "bound_prompts": len(bound_prompts),
        "bound_bindings": len(bound_bindings),
        "responses": len(responses),
        "user_mappings": len(user_mappings),
        "user_evidence": len(_user_supplied_evidence(updated_plan or {})),
    }
    expected = len(responses)
    checks = [
        _check(
            "one_to_one_counts",
            all(value == expected for value in counts.values()),
            "bound prompts, bindings, responses, mappings, and evidence are one-to-one",
            expected=expected,
            actual=counts,
        ),
        _check(
            "canonical_names_unique",
            _unique(mapping.get("paper_param_name") for mapping in user_mappings),
            "user-supplied mapping canonical names are unique",
        ),
    ]
    return _rule("r4", checks)


def _r5(
    *,
    prompts: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    updated_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    prompt_by_id = {prompt.get("prompt_id"): prompt for prompt in prompts}
    binding_by_id = {binding.get("prompt_id"): binding for binding in bindings}
    mappings_by_name = {
        _canon(mapping.get("paper_param_name")): mapping
        for mapping in _user_supplied_mappings(updated_plan or {})
    }
    failures: list[dict[str, Any]] = []
    for response in responses:
        prompt_id = response.get("prompt_id")
        prompt = prompt_by_id.get(prompt_id)
        binding = binding_by_id.get(prompt_id)
        names = {
            "prompt": _canon(_field(prompt, "parameter_name")),
            "response": _canon(response.get("parameter_name")),
            "binding": _canon(_field(binding, "paper_param_name")),
        }
        mapping = mappings_by_name.get(names["response"])
        names["mapping"] = _canon(_field(mapping, "paper_param_name"))
        if len(set(names.values())) != 1 or "" in names.values():
            failures.append({"prompt_id": prompt_id, "names": names})
    return _rule(
        "r5",
        [
            _check(
                "canonical_name_chain_consistent",
                not failures,
                "prompt, response, binding, and mapping names are identical",
                expected=[],
                actual=failures,
            )
        ],
    )


def _named_status_rule(name: str, status_value: Any) -> dict[str, Any]:
    return _rule(
        name,
        [
            _check(
                f"{name}_pass",
                str(status_value).casefold() == "pass",
                f"{name} is Pass",
                expected="Pass",
                actual=status_value,
            )
        ],
    )


def _numeric_rule(name: str, value: Any, *, perfect: float) -> dict[str, Any]:
    passed = isinstance(value, int | float) and float(value) >= perfect
    return _rule(
        name,
        [
            _check(
                f"{name}_perfect",
                passed,
                f"{name} reaches perfect score",
                expected=perfect,
                actual=value,
            )
        ],
    )


def _d1_rule(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _rule("d1", [RuleCheck("d1_shape", "fail", "D1 shape is missing")])
    concrete = [item for item in value.values() if item is not None]
    return _rule(
        "d1",
        [
            _check(
                "d1_no_false_flags",
                bool(concrete) and all(item is True for item in concrete),
                "D1 has no false shape flags",
                actual=value,
            )
        ],
    )


def _soft_rule_perfect(rule: Any) -> bool:
    return _rule_passed(rule)


def _rule_passed(rule: Any) -> bool:
    return isinstance(rule, dict) and rule.get("status") == "pass"


def _public_rule(rule: Any) -> Any:
    if isinstance(rule, dict):
        return rule
    return rule


def _rule(name: str, checks: list[RuleCheck]) -> dict[str, Any]:
    status: RuleStatus = "pass" if all(check.status == "pass" for check in checks) else "fail"
    return {
        "status": status,
        "checks": [asdict(check) for check in checks],
    }


def _check(
    name: str,
    condition: bool,
    message: str,
    *,
    expected: Any = None,
    actual: Any = None,
) -> RuleCheck:
    return RuleCheck(
        name=name,
        status="pass" if condition else "fail",
        message=message,
        expected=expected,
        actual=actual,
    )


def _value_matches_response(mapping: dict[str, Any] | None, response: dict[str, Any]) -> bool:
    if mapping is None:
        return False
    return (
        mapping.get("value") == response.get("user_supplied_value")
        and mapping.get("unit") == response.get("user_supplied_unit")
        and mapping.get("source") == "user_supplied"
    )


def _document_mappings_unchanged(
    original_plan: dict[str, Any] | None,
    updated_plan: dict[str, Any] | None,
) -> bool:
    if original_plan is None or updated_plan is None:
        return False
    before = {
        (mapping.get("paper_param_name"), mapping.get("model_param_name")): mapping
        for mapping in _list_field(original_plan, "parameter_mapping")
        if isinstance(mapping, dict) and mapping.get("value") != MISSING_VALUE_SENTINEL
    }
    after = {
        (mapping.get("paper_param_name"), mapping.get("model_param_name")): mapping
        for mapping in _list_field(updated_plan, "parameter_mapping")
        if isinstance(mapping, dict)
        and mapping.get("source") == "document_extracted"
        and mapping.get("value") != MISSING_VALUE_SENTINEL
    }
    return before == after


def _user_supplied_mappings(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        mapping
        for mapping in _list_field(plan, "parameter_mapping")
        if isinstance(mapping, dict) and mapping.get("source") == "user_supplied"
    ]


def _user_supplied_evidence(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in _list_field(plan, "evidence")
        if isinstance(entry, dict) and entry.get("source") == "user_supplied"
    ]


def _unique(values: Any) -> bool:
    normalized = [_canon(value) for value in values]
    normalized = [value for value in normalized if value]
    return bool(normalized) and len(normalized) == len(set(normalized))


def _list_field(value: Any, field_name: str) -> list[Any]:
    field = _field(value, field_name)
    return field if isinstance(field, list) else []


def _field(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _canon(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""
