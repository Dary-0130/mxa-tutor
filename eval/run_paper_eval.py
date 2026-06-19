"""Run paper-to-model evaluator with service-level true run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.llm import DeepSeekTextProvider
from app.config import AppSettings
from core.domain.exceptions import PaperPlanGenerationError
from core.interfaces.document_parser import DocumentParserRouter
from eval._eval_markdown_parser import EvalMarkdownParser
from eval._paper_eval_csv import ExecutionStatus, write_paper_eval_csv
from eval._paper_eval_metrics import (
    compute_a1_field_coverage,
    compute_b1_b2,
    compute_c2_block_coverage,
    compute_c3_param_mapping_coverage,
    compute_d1_mscript_shape,
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
from features.paper.paper_user_input_schemas import UserSuppliedResponseBatch
from features.paper.paper_user_supply_service import UserSupplyService

CASES_ROOT = Path("eval/cases/paper_to_model")
KNOWN_BLOCKED_FAILURES = frozenset({"missing_binding_not_found"})
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
    layer2_metrics: dict[str, Any]
    failure: str | None
    execution_status: ExecutionStatus


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
        verdict=None,
        failure=result.failure,
        output_path=csv_path,
    )
    print(f"wrote {csv_path}")
    print(f"execution_status={result.execution_status}")
    if result.failure:
        print(f"failure={result.failure}")
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

    actual_spec_domain = await services.spec_service.extract(
        source,
        paper_id=paper_id,
    )
    actual_plan_domain = None
    actual_prompts_domain = None
    actual_updated_plan_domain = None
    response_prompt_ids: list[str] = []
    failure: str | None = None
    execution_status: ExecutionStatus = "succeeded"

    try:
        plan, prompts, bindings = await services.plan_service.generate(
            actual_spec_domain,
            paper_id=paper_id,
        )
        actual_plan_domain = plan
        actual_prompts_domain = prompts
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
    except PaperPlanGenerationError as exc:
        reason = str(exc)
        if reason not in KNOWN_BLOCKED_FAILURES:
            raise
        failure = reason
        execution_status = "blocked_known_defect"

    if case_kind == "missing_param" and failure is None:
        payload = _load_required_json(case_dir / "user_input" / "user_supplied_params.json")
        batch = UserSuppliedResponseBatch.model_validate(payload)
        response_prompt_ids = [response.prompt_id for response in batch.user_supplied_responses]
        actual_updated_plan_domain = await services.user_supply_service.merge(
            paper_id,
            batch.user_supplied_responses,
        )

    if case_kind == "material_to_plan":
        golden_spec = _load_required_json(case_dir / "golden" / "expected_paper_spec.json")
        golden_plan = _load_required_json(
            case_dir / "golden" / "expected_model_generation_plan.json"
        )
        golden_prompts = None
        golden_updated_plan = None
    else:
        golden_spec = None
        golden_plan = None
        golden_prompts = _load_required_prompt_list(
            case_dir / "input" / "expected_missing_prompts.json"
        )
        golden_updated_plan = _load_required_json(
            case_dir / "golden" / "expected_updated_plan.json"
        )

    actual_spec = _serialize_spec(actual_spec_domain)
    actual_plan = _serialize_plan(actual_plan_domain)
    actual_prompts = _serialize_prompts(actual_prompts_domain)
    actual_updated_plan = _serialize_plan(actual_updated_plan_domain)

    metrics = _compute_case_layer_metrics(
        case_kind=case_kind,
        actual_spec=actual_spec,
        actual_plan=actual_plan,
        actual_prompts=actual_prompts,
        actual_updated_plan=actual_updated_plan,
        golden_spec=golden_spec,
        golden_plan=golden_plan,
        golden_prompts=golden_prompts,
        golden_updated_plan=golden_updated_plan,
        response_prompt_ids=response_prompt_ids,
        failure=failure,
    )
    return CaseResult(
        case_id=case_id,
        case_kind=case_kind,
        actual_spec=actual_spec,
        actual_plan=actual_plan,
        actual_prompts=actual_prompts,
        actual_updated_plan=actual_updated_plan,
        layer2_metrics=metrics,
        failure=failure,
        execution_status=execution_status,
    )


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
    golden_prompts: list[dict[str, Any]] | None,
    golden_updated_plan: dict[str, Any] | None,
    response_prompt_ids: list[str],
    failure: str | None,
) -> dict[str, Any]:
    a1: float | str = (
        compute_a1_field_coverage(actual_spec or {}, golden_spec)
        if golden_spec is not None
        else "N/A"
    )

    if failure is None and actual_prompts is not None and golden_prompts is not None:
        b1, b2 = compute_b1_b2(actual_prompts, golden_prompts)
    else:
        b1 = b2 = "N/A"

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
        failure=failure,
    )
    e2 = _compute_e2(
        case_kind=case_kind,
        plan=compare_actual,
        golden_prompts=golden_prompts,
        response_prompt_ids=response_prompt_ids,
        failure=failure,
    )
    return {
        "A1": a1,
        "B1": b1,
        "B2": b2,
        "C2": c2,
        "C3": c3,
        "D1": d1,
        "E1": e1,
        "E2": e2,
    }


def _compute_e1(
    *,
    case_kind: CaseKind,
    actual_spec: dict[str, Any] | None,
    actual_plan: dict[str, Any] | None,
    actual_prompts: list[dict[str, Any]] | None,
    actual_updated_plan: dict[str, Any] | None,
    failure: str | None,
) -> str:
    """Automatic invariant result.

    The production services already fail fast through EvidenceTagger, and the
    strict schema-wrapper serialization immediately before this helper validates
    the two PaperEvidenceEntry source invariants. No fallback is permitted.
    """
    if failure is not None:
        return "N/A"
    if actual_spec is None or actual_plan is None or actual_prompts is None:
        return "Fail"
    if case_kind == "missing_param" and actual_updated_plan is None:
        return "Fail"
    return "Pass"


def _compute_e2(
    *,
    case_kind: CaseKind,
    plan: dict[str, Any] | None,
    golden_prompts: list[dict[str, Any]] | None,
    response_prompt_ids: list[str],
    failure: str | None,
) -> str:
    mappings = plan.get("parameter_mapping", []) if isinstance(plan, dict) else []
    user_mappings = [
        mapping
        for mapping in mappings
        if isinstance(mapping, dict) and mapping.get("source") == "user_supplied"
    ]

    if case_kind == "material_to_plan":
        return "Fail" if user_mappings else "N/A"
    if failure is not None:
        return "N/A"
    if plan is None or golden_prompts is None:
        return "Fail"

    expected_ids = {
        prompt.get("prompt_id")
        for prompt in golden_prompts
        if isinstance(prompt, dict) and isinstance(prompt.get("prompt_id"), str)
    }
    response_ids = set(response_prompt_ids)
    if not expected_ids or response_ids != expected_ids:
        return "Fail"
    if len(response_prompt_ids) != len(response_ids):
        return "Fail"
    if len(user_mappings) != len(expected_ids):
        return "Fail"
    if not all(
        isinstance(mapping.get("value"), str) and mapping["value"].strip()
        for mapping in user_mappings
    ):
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


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"missing required JSON: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be object: {path}")
    return value


def _load_required_prompt_list(path: Path) -> list[dict[str, Any]]:
    value = _load_required_json(path)
    if "missing_prompts" not in value:
        raise SystemExit(f"missing key 'missing_prompts': {path}")
    prompts = value["missing_prompts"]
    if not isinstance(prompts, list) or not prompts:
        raise SystemExit(f"missing_prompts must be a non-empty list: {path}")
    if not all(isinstance(prompt, dict) for prompt in prompts):
        raise SystemExit(f"missing_prompts items must be objects: {path}")
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
    }
    for name, value in artifacts.items():
        path = output_dir / f"{slug}.{name}.json"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
