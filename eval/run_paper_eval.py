"""Run paper-to-model evaluator with service-level true run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.llm import DeepSeekTextProvider
from app.config import AppSettings
from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.interfaces.document_parser import DocumentParserRouter
from eval._eval_markdown_parser import EvalMarkdownParser
from eval._paper_eval_csv import ExecutionStatus, write_paper_eval_csv
from eval._paper_eval_dynamic_id_adapter import (
    AdapterBinding,
    DynamicIdAdapterError,
    R1aPreFailure,
    bind_user_responses_by_canonical_name,
    fixture_entries_from_payload,
)
from eval._paper_eval_metrics import (
    compute_a1_field_coverage,
    compute_c2_block_coverage,
    compute_c3_param_mapping_coverage,
    compute_d1_mscript_shape,
)
from eval._paper_eval_rules import (
    Verdict,
    compute_material_rules,
    compute_missing_rules,
    compute_verdict,
    public_rule_details,
)
from features.paper._paper_spec_cache import InMemoryPaperSpecCache
from features.paper.paper_plan_cache import InMemoryPaperPlanCache, PaperPlanRecord
from features.paper.paper_plan_service import PaperPlanService
from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)
from features.paper.paper_spec_service import PaperSpecService
from features.paper.paper_user_input_schemas import UserSuppliedResponseModel
from features.paper.paper_user_supply_service import UserSupplyService

CASES_ROOT = Path("eval/cases/paper_to_model")
CaseKind = Literal["material_to_plan", "missing_param"]


@dataclass(frozen=True)
class EvaluatorServices:
    spec_service: PaperSpecService
    plan_service: PaperPlanService
    plan_cache: InMemoryPaperPlanCache
    user_supply_service: UserSupplyService


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    case_kind: CaseKind
    actual_spec: dict[str, Any] | None
    actual_plan: dict[str, Any] | None
    actual_prompts: list[dict[str, Any]] | None
    actual_updated_plan: dict[str, Any] | None
    actual_bindings: list[dict[str, Any]] | None
    layer2_metrics: dict[str, Any]
    rule_details: dict[str, Any]
    failure: str | None
    execution_status: ExecutionStatus
    verdict: Verdict
    failure_stage: str | None
    exception_type: str | None
    error_code: str | None


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="paper-to-model evaluator (service-level true run)"
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    root = CASES_ROOT.resolve()
    case_dir = (CASES_ROOT / args.case).resolve()
    if not case_dir.is_relative_to(root):
        raise SystemExit("case path escapes CASES_ROOT")
    if not case_dir.is_dir():
        raise SystemExit(f"case not found: {case_dir}")

    try:
        settings = AppSettings()
    except Exception as exc:
        raise SystemExit(f"AppSettings load failed: {type(exc).__name__}") from None

    text_provider = DeepSeekTextProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    router = DocumentParserRouter([EvalMarkdownParser()])
    plan_cache = InMemoryPaperPlanCache()
    services = EvaluatorServices(
        spec_service=PaperSpecService(
            cache=InMemoryPaperSpecCache(),
            text_provider=text_provider,
            document_parser_router=router,
        ),
        plan_service=PaperPlanService(text_provider=text_provider),
        plan_cache=plan_cache,
        user_supply_service=UserSupplyService(cache=plan_cache),
    )

    result = await _run_case(case_dir, services, root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    slug = result.case_id.replace("/", "__")
    _write_actual_artifacts(result, args.output_dir, slug)

    csv_path = args.output_dir / f"{slug}.paper_eval.csv"
    write_paper_eval_csv(
        case_id=result.case_id,
        layer1_outcome={
            "O1": "",
            "O2": "N/A" if result.case_kind == "material_to_plan" else "",
        },
        layer2_metrics=result.layer2_metrics,
        layer2_manual={"A2": "", "C1": "", "origin_inherited_notes": ""},
        execution_status=result.execution_status,
        verdict=result.verdict,
        failure=result.failure,
        output_path=csv_path,
    )
    print(f"wrote {csv_path}")
    print(f"execution_status={result.execution_status}")
    print(f"verdict={result.verdict}")
    if result.failure:
        print(f"failure={result.failure}")
    if result.failure_stage:
        print(f"failure_stage={result.failure_stage}")
    return 0


async def _run_case(
    case_dir: Path,
    services: EvaluatorServices,
    cases_root_resolved: Path,
) -> CaseResult:
    case_id = case_dir.relative_to(cases_root_resolved).as_posix()
    case_kind = _infer_case_kind(case_id)
    paper_id = f"PAPER-{case_id.replace('/', '__')}"
    source = case_dir / "input" / "source_doc_stripped.md"
    if not source.is_file():
        raise SystemExit(f"missing required markdown: {source}")

    actual_spec_domain = None
    actual_plan_domain = None
    actual_prompts_domain = None
    actual_updated_plan_domain = None
    actual_bindings_domain = None
    adapted_responses: list[UserSuppliedResponseModel] = []
    adapter_bindings: list[AdapterBinding] = []
    adapter_failures: list[R1aPreFailure] = []
    failure_stage: str | None = None

    try:
        failure_stage = "spec_extract"
        actual_spec_domain = await services.spec_service.extract(
            source,
            paper_id=paper_id,
        )
        failure_stage = "plan_generate"
        plan, prompts, bindings = await services.plan_service.generate(
            actual_spec_domain,
            paper_id=paper_id,
        )
        actual_plan_domain = plan
        actual_prompts_domain = prompts
        actual_bindings_domain = bindings
        failure_stage = "plan_cache_set"
        await services.plan_cache.set(
            paper_id,
            PaperPlanRecord(
                paper_id=paper_id,
                spec=actual_spec_domain,
                plan=plan,
                missing_prompts=prompts,
                missing_bindings=bindings,
            ),
        )
    except Exception as exc:
        return _case_failed_result(
            case_id=case_id,
            case_kind=case_kind,
            failure_stage=failure_stage,
            exc=exc,
            actual_spec=_safe_serialize_spec(actual_spec_domain),
            actual_plan=_safe_serialize_plan(actual_plan_domain),
            actual_prompts=_safe_serialize_prompts(actual_prompts_domain),
            actual_updated_plan=_safe_serialize_plan(actual_updated_plan_domain),
            actual_bindings=_serialize_bindings(actual_bindings_domain),
        )

    actual_spec = _serialize_spec(actual_spec_domain)
    actual_plan = _serialize_plan(actual_plan_domain)
    actual_prompts = _serialize_prompts(actual_prompts_domain)
    actual_bindings = _serialize_bindings(actual_bindings_domain)

    if case_kind == "missing_param":
        try:
            failure_stage = "r1a_pre"
            payload = _load_required_json(case_dir / "user_input" / "user_supplied_params.json")
            fixture_entries = fixture_entries_from_payload(payload)
            adapter_success = bind_user_responses_by_canonical_name(
                actual_prompts=actual_prompts or [],
                fixture_entries=fixture_entries,
            )
            adapted_responses = adapter_success.user_supplied_responses
            adapter_bindings = adapter_success.bindings
        except DynamicIdAdapterError as exc:
            adapter_failures = exc.failures

    if case_kind == "missing_param" and not adapter_failures:
        try:
            failure_stage = "user_supply_merge"
            actual_updated_plan_domain = await services.user_supply_service.merge(
                paper_id,
                adapted_responses,
            )
        except Exception as exc:
            return _case_failed_result(
                case_id=case_id,
                case_kind=case_kind,
                failure_stage=failure_stage,
                exc=exc,
                actual_spec=actual_spec,
                actual_plan=actual_plan,
                actual_prompts=actual_prompts,
                actual_updated_plan=_safe_serialize_plan(actual_updated_plan_domain),
                actual_bindings=actual_bindings,
            )

    try:
        failure_stage = "serialize_actuals"
        actual_updated_plan = _serialize_plan(actual_updated_plan_domain)
        failure_stage = "load_golden"
        if case_kind == "material_to_plan":
            golden_spec = _load_required_json(case_dir / "golden" / "expected_paper_spec.json")
            golden_plan = _load_required_json(
                case_dir / "golden" / "expected_model_generation_plan.json"
            )
            golden_updated_plan = None
            document_facts = None
        else:
            golden_spec = None
            golden_plan = None
            golden_updated_plan = _load_required_json(
                case_dir / "golden" / "expected_updated_plan.json"
            )
            document_facts = _load_required_json(
                case_dir / "r2_truth_source" / "document_facts.json"
            )

        failure_stage = "compute_metrics"
        metrics = _compute_case_layer_metrics(
            case_kind=case_kind,
            actual_spec=actual_spec,
            actual_plan=actual_plan,
            actual_prompts=actual_prompts,
            actual_updated_plan=actual_updated_plan,
            golden_spec=golden_spec,
            golden_plan=golden_plan,
            golden_updated_plan=golden_updated_plan,
        )
        adapted_response_dicts = [
            response.model_dump(mode="json") for response in adapted_responses
        ]
        if case_kind == "missing_param":
            rule_results = compute_missing_rules(
                actual_prompts=actual_prompts,
                actual_plan=actual_plan,
                actual_updated_plan=actual_updated_plan,
                actual_bindings=actual_bindings,
                adapted_responses=adapted_response_dicts,
                adapter_bindings=adapter_bindings,
                adapter_failures=adapter_failures,
                document_facts=document_facts,
                e1_status=str(metrics.get("E1", "Fail")),
            )
        else:
            rule_results = compute_material_rules(
                metrics=metrics,
                actual_plan=actual_plan,
            )
        metrics["R3"] = _csv_status(rule_results.get("r3"))
        verdict = compute_verdict(
            case_kind=case_kind,
            execution_status="succeeded",
            rule_results=rule_results,
        )
    except Exception as exc:
        return _case_failed_result(
            case_id=case_id,
            case_kind=case_kind,
            failure_stage=failure_stage,
            exc=exc,
            actual_spec=actual_spec,
            actual_plan=actual_plan,
            actual_prompts=actual_prompts,
            actual_updated_plan=_safe_serialize_plan(actual_updated_plan_domain),
            actual_bindings=actual_bindings,
        )

    return CaseResult(
        case_id=case_id,
        case_kind=case_kind,
        actual_spec=actual_spec,
        actual_plan=actual_plan,
        actual_prompts=actual_prompts,
        actual_updated_plan=actual_updated_plan,
        actual_bindings=actual_bindings,
        layer2_metrics=metrics,
        rule_details=public_rule_details(rule_results),
        failure=None,
        execution_status="succeeded",
        verdict=verdict,
        failure_stage="r1a_pre" if adapter_failures else None,
        exception_type=None,
        error_code=None,
    )


def _case_failed_result(
    *,
    case_id: str,
    case_kind: CaseKind,
    failure_stage: str | None,
    exc: Exception,
    actual_spec: dict[str, Any] | None,
    actual_plan: dict[str, Any] | None,
    actual_prompts: list[dict[str, Any]] | None,
    actual_updated_plan: dict[str, Any] | None,
    actual_bindings: list[dict[str, Any]] | None,
) -> CaseResult:
    error_code = _error_code(exc)
    return CaseResult(
        case_id=case_id,
        case_kind=case_kind,
        actual_spec=actual_spec,
        actual_plan=actual_plan,
        actual_prompts=actual_prompts,
        actual_updated_plan=actual_updated_plan,
        actual_bindings=actual_bindings,
        layer2_metrics=_not_evaluated_metrics(),
        rule_details={
            "case_failure": {
                "status": "n/a",
                "failure_stage": failure_stage,
                "exception_type": type(exc).__name__,
                "error_code": error_code,
            }
        },
        failure=error_code,
        execution_status="case_failed",
        verdict="not_evaluated",
        failure_stage=failure_stage,
        exception_type=type(exc).__name__,
        error_code=error_code,
    )


def _error_code(exc: Exception) -> str:
    if isinstance(exc, PaperPlanGenerationError | PaperUserSupplyError):
        value = str(exc)
        return value if value else type(exc).__name__
    if isinstance(exc, FileNotFoundError):
        return "fixture_missing"
    if isinstance(exc, json.JSONDecodeError):
        return "fixture_json_invalid"
    if isinstance(exc, ValueError):
        return "fixture_invalid"
    return type(exc).__name__


def _not_evaluated_metrics() -> dict[str, Any]:
    return {
        "A1": "N/A",
        "C2": "N/A",
        "C3": "N/A",
        "D1": {"has_params": None, "has_equations": None, "has_plot": None},
        "E1": "N/A",
        "R3": "N/A",
    }


def _csv_status(rule: Any) -> str:
    if not isinstance(rule, dict):
        return "N/A"
    status = rule.get("status")
    if status == "pass":
        return "Pass"
    if status == "fail":
        return "Fail"
    return "N/A"


def _infer_case_kind(case_id: str) -> CaseKind:
    value = case_id.split("/", 1)[0]
    if value == "material_to_plan":
        return "material_to_plan"
    if value == "missing_param":
        return "missing_param"
    raise SystemExit(f"unknown case kind: {value}")


def _compute_case_layer_metrics(
    *,
    case_kind: CaseKind,
    actual_spec: dict[str, Any] | None,
    actual_plan: dict[str, Any] | None,
    actual_prompts: list[dict[str, Any]] | None,
    actual_updated_plan: dict[str, Any] | None,
    golden_spec: dict[str, Any] | None,
    golden_plan: dict[str, Any] | None,
    golden_updated_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    a1: float | str = (
        compute_a1_field_coverage(actual_spec or {}, golden_spec)
        if golden_spec is not None
        else "N/A"
    )

    compare_actual = actual_plan if case_kind == "material_to_plan" else actual_updated_plan
    compare_golden = golden_plan if case_kind == "material_to_plan" else golden_updated_plan
    if compare_actual is not None and compare_golden is not None:
        c2: float | str = compute_c2_block_coverage(compare_actual, compare_golden)
        c3: float | str = compute_c3_param_mapping_coverage(compare_actual, compare_golden)
        d1 = compute_d1_mscript_shape(compare_actual.get("m_script_skeleton"))
    else:
        c2 = c3 = "N/A"
        d1 = {
            "has_params": None,
            "has_equations": None,
            "has_plot": None,
        }

    e1 = _compute_e1(
        case_kind=case_kind,
        actual_spec=actual_spec,
        actual_plan=actual_plan,
        actual_prompts=actual_prompts,
        actual_updated_plan=actual_updated_plan,
    )
    return {
        "A1": a1,
        "C2": c2,
        "C3": c3,
        "D1": d1,
        "E1": e1,
    }


def _compute_e1(
    *,
    case_kind: CaseKind,
    actual_spec: dict[str, Any] | None,
    actual_plan: dict[str, Any] | None,
    actual_prompts: list[dict[str, Any]] | None,
    actual_updated_plan: dict[str, Any] | None,
) -> str:
    """Automatic invariant result.

    The production services already fail fast through EvidenceTagger, and the
    strict schema-wrapper serialization immediately before this helper validates
    the two PaperEvidenceEntry source invariants. No fallback is permitted.
    """
    if actual_spec is None or actual_plan is None or actual_prompts is None:
        return "Fail"
    if case_kind == "missing_param" and actual_updated_plan is None:
        return "Fail"
    return "Pass"


def _serialize_spec(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return PaperSpecModel.from_domain(value).model_dump(mode="json")


def _serialize_plan(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return ModelGenerationPlanModel.from_domain(value).model_dump(mode="json")


def _serialize_prompts(values: Any) -> list[dict[str, Any]] | None:
    if values is None:
        return None
    if not isinstance(values, list):
        raise TypeError("actual prompts must be a list")
    return [
        MissingParameterPromptModel.from_domain(value).model_dump(mode="json") for value in values
    ]


def _safe_serialize_spec(value: Any) -> dict[str, Any] | None:
    try:
        return _serialize_spec(value)
    except Exception:
        return None


def _safe_serialize_plan(value: Any) -> dict[str, Any] | None:
    try:
        return _serialize_plan(value)
    except Exception:
        return None


def _safe_serialize_prompts(values: Any) -> list[dict[str, Any]] | None:
    try:
        return _serialize_prompts(values)
    except Exception:
        return None


def _serialize_bindings(values: Any) -> list[dict[str, Any]] | None:
    if values is None:
        return None
    if not isinstance(values, list):
        raise TypeError("actual bindings must be a list")
    return [asdict(value) for value in values]


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _load_required_prompt_list(path: Path) -> list[dict[str, Any]]:
    value = _load_required_json(path)
    if "missing_prompts" not in value:
        raise ValueError(f"missing key 'missing_prompts': {path}")
    prompts = value["missing_prompts"]
    if not isinstance(prompts, list) or not prompts:
        raise ValueError(f"missing_prompts must be a non-empty list: {path}")
    if not all(isinstance(prompt, dict) for prompt in prompts):
        raise ValueError(f"missing_prompts items must be objects: {path}")
    return prompts


def _write_actual_artifacts(
    result: CaseResult,
    output_dir: Path,
    slug: str,
) -> None:
    artifacts = {
        "actual_spec": result.actual_spec,
        "actual_plan": result.actual_plan,
        "actual_prompts": result.actual_prompts,
        "actual_updated_plan": result.actual_updated_plan,
        "rule_details": result.rule_details,
        "case_result": {
            "case_id": result.case_id,
            "case_kind": result.case_kind,
            "execution_status": result.execution_status,
            "verdict": result.verdict,
            "failure": result.failure,
            "failure_stage": result.failure_stage,
            "exception_type": result.exception_type,
            "error_code": result.error_code,
        },
    }
    for name, value in artifacts.items():
        path = output_dir / f"{slug}.{name}.json"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
