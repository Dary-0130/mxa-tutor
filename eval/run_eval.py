"""Run TASK-306 prompt evaluation cases and write raw CSV output."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import asyncio
import csv
import fnmatch
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.domain.exceptions import ChatGenerationError, LLMError, LLMTimeoutError
from eval._bootstrap import EvalAuditContext, build_chat_service_for_eval

RAW_FIELDNAMES = [
    "run_id",
    "prompt_version",
    "prompt_path",
    "loaded_prompt_path",
    "loaded_prompt_version",
    "prompt_loader_mode",
    "model_name",
    "temperature",
    "top_p",
    "run_at",
    "case_id",
    "project_alias",
    "runtime_project_id",
    "eval_set",
    "question_type",
    "question",
    "expected_behavior",
    "expected_citation_types_any_of",
    "required_citation_types_all_of",
    "answer",
    "confidence",
    "raw_citation_ids_json",
    "source_table_json",
    "source_table_capture_mode",
    "raw_citation_id_type_map_json",
    "returned_citation_refs_json",
    "returned_citation_types_json_or_blank",
    "returned_citation_count",
    "retrieval_hit_types_json",
    "citation_type_source",
    "fallback_reason_or_blank",
    "session_id",
    "isolation_mode",
    "total_duration_ms",
    "llm_duration_ms",
    "error_type",
    "error_code_or_blank",
    "error_message_sanitized",
    "sentinel_leaked",
]

ERROR_MESSAGES = {
    "llm_timeout": "llm_timeout",
    "llm_api_error": "llm_api_error",
    "parse_validation_error": "parse_validation_error",
    "unexpected_error": "unexpected_error",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TASK-306 raw QA eval")
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--project-map-template", required=True, type=Path)
    parser.add_argument("--project-map-resolved", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--eval-db-path", required=True, type=Path)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--project-filter")
    parser.add_argument("--isolation-mode", default="new_session")
    parser.add_argument("--run-id")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    if args.isolation_mode != "new_session":
        raise SystemExit("only isolation-mode=new_session is supported on this HEAD")

    output_dir = _resolve_output_dir(args.output_dir)
    run_id = args.run_id or output_dir.name
    template = _load_json(args.project_map_template)
    resolved = _load_json(args.project_map_resolved)
    runtime_ids = _runtime_project_ids(template, resolved)
    cases = _load_cases(args.cases, template, args.project_filter, args.max_cases)

    chat_service, audit = build_chat_service_for_eval(args.prompt, args.eval_db_path)
    raw_path = output_dir / _raw_filename(audit.loaded_prompt_version)
    rows: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases):
            audit.reset_case()
            started = time.perf_counter()
            run_at = datetime.now(UTC).isoformat()
            response = None
            error_type = ""
            error_message = ""
            try:
                response = await chat_service.handle_chat(
                    project_id=runtime_ids[case["project_alias"]],
                    question=case["question"],
                    session_id=None,
                )
            except LLMTimeoutError:
                error_type = "llm_timeout"
                error_message = ERROR_MESSAGES[error_type]
            except LLMError:
                error_type = "llm_api_error"
                error_message = ERROR_MESSAGES[error_type]
            except ChatGenerationError:
                error_type = "parse_validation_error"
                error_message = ERROR_MESSAGES[error_type]
            except Exception:
                error_type = "unexpected_error"
                error_message = ERROR_MESSAGES[error_type]

            total_duration_ms = int((time.perf_counter() - started) * 1000)
            audit_fields = audit.collect_per_case_audit(response)
            rows.append(
                _raw_row(
                    run_id=run_id,
                    prompt_path=args.prompt,
                    audit=audit,
                    case=case,
                    runtime_project_id=runtime_ids[case["project_alias"]],
                    run_at=run_at,
                    response=response,
                    total_duration_ms=total_duration_ms,
                    error_type=error_type,
                    error_message=error_message,
                    audit_fields=audit_fields,
                )
            )
            if index != len(cases) - 1:
                await asyncio.sleep(0.5)
    finally:
        await audit.aclose()

    _write_csv(raw_path, RAW_FIELDNAMES, rows)
    print(f"wrote {len(rows)} rows to {raw_path}")
    return 0


def _resolve_output_dir(path: Path) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else ROOT / path
    with resolved.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("json_root_must_be_object")
    return data


def _runtime_project_ids(template: dict[str, Any], resolved: dict[str, Any]) -> dict[str, str]:
    selected = template.get("selected_project_aliases", [])
    projects = resolved.get("projects", {})
    if not isinstance(selected, list) or not isinstance(projects, dict):
        raise ValueError("invalid_project_map")
    mapping: dict[str, str] = {}
    for alias in selected:
        project = projects.get(alias, {})
        runtime_id = project.get("runtime_project_id") if isinstance(project, dict) else None
        if not isinstance(runtime_id, str) or not runtime_id:
            raise ValueError(f"missing_runtime_project_id:{alias}")
        mapping[str(alias)] = runtime_id
    return mapping


def _load_cases(
    cases_dir: Path,
    template: dict[str, Any],
    project_filter: str | None,
    max_cases: int | None,
) -> list[dict[str, Any]]:
    root = cases_dir if cases_dir.is_absolute() else ROOT / cases_dir
    selected = [str(alias) for alias in template.get("selected_project_aliases", [])]
    cases: list[dict[str, Any]] = []
    for alias in selected:
        path = root / alias / "questions.jsonl"
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                case = json.loads(line)
                if _case_matches(case, project_filter):
                    cases.append(case)
    cases.sort(key=lambda row: (selected.index(row["project_alias"]), row["case_id"]))
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError("max_cases_must_be_positive")
        cases = cases[:max_cases]
    return cases


def _case_matches(case: dict[str, Any], project_filter: str | None) -> bool:
    if not project_filter:
        return True
    return fnmatch.fnmatch(case["project_alias"], project_filter) or fnmatch.fnmatch(
        case["case_id"], project_filter
    )


def _raw_filename(prompt_version: str) -> str:
    if prompt_version == "v0.1":
        return "qa_v0.1_baseline_raw.csv"
    if prompt_version == "v0.2-rc":
        return "qa_v0.2_rc_raw.csv"
    safe = prompt_version.replace("/", "_").replace("-", "_")
    return f"qa_{safe}_raw.csv"


def _raw_row(
    *,
    run_id: str,
    prompt_path: Path,
    audit: EvalAuditContext,
    case: dict[str, Any],
    runtime_project_id: str,
    run_at: str,
    response: Any,
    total_duration_ms: int,
    error_type: str,
    error_message: str,
    audit_fields: dict[str, Any],
) -> dict[str, Any]:
    answer = response.answer if response is not None else ""
    confidence = response.confidence if response is not None else ""
    row = {
        "run_id": run_id,
        "prompt_version": audit.loaded_prompt_version,
        "prompt_path": str(prompt_path),
        "loaded_prompt_path": audit.loaded_prompt_path,
        "loaded_prompt_version": audit.loaded_prompt_version,
        "prompt_loader_mode": audit.prompt_loader_mode,
        "model_name": audit.model_name,
        "temperature": "",
        "top_p": "",
        "run_at": run_at,
        "case_id": case["case_id"],
        "project_alias": case["project_alias"],
        "runtime_project_id": runtime_project_id,
        "eval_set": case["eval_set"],
        "question_type": case["question_type"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "expected_citation_types_any_of": _json(case["expected_citation_types_any_of"]),
        "required_citation_types_all_of": _json(case["required_citation_types_all_of"]),
        "answer": answer,
        "confidence": confidence,
        "session_id": audit_fields.get("session_id", ""),
        "isolation_mode": "new_session",
        "total_duration_ms": total_duration_ms,
        "error_type": error_type,
        "error_code_or_blank": "",
        "error_message_sanitized": error_message,
        "sentinel_leaked": "__project_overview__" in answer,
    }
    row.update(audit_fields)
    return {field: row.get(field, "") for field in RAW_FIELDNAMES}


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
