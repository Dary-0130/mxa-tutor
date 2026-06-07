"""Create half-blinded scoring queues for TASK-306."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

QUEUE_FIELDNAMES = [
    "blind_id",
    "project_alias",
    "case_id",
    "question_type",
    "question",
    "answer",
    "confidence",
    "expected_behavior",
    "expected_citation_types_any_of",
    "required_citation_types_all_of",
    "case_notes",
    "raw_citation_ids_json",
    "returned_citation_refs_json",
    "returned_citation_types_json_or_blank",
    "source_table_json",
    "raw_citation_id_type_map_json",
    "retrieval_hit_types_json",
    "citation_type_source",
    "source_table_capture_mode",
    "fallback_reason_or_blank",
    "sentinel_leaked",
]

KEY_FIELDNAMES = [
    "blind_id",
    "case_id",
    "project_alias",
    "prompt_version",
    "prompt_path",
    "raw_csv_path",
]

PROJECT_KEY_FIELDNAMES = [
    "project_alias",
    "source_case_dir",
    "domain",
    "fixture_class",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TASK-306 half-blind scoring queue")
    parser.add_argument("--raw", action="append", required=True, type=Path)
    parser.add_argument("--project-map-template", required=True, type=Path)
    parser.add_argument("--project-map-resolved", required=True, type=Path)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--project-key", required=True, type=Path)
    parser.add_argument("--seed", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template = _load_json(args.project_map_template)
    resolved = _load_json(args.project_map_resolved)
    _validate_resolved_projects(template, resolved)
    case_notes = _load_case_notes(template)
    raw_rows = _load_raw_rows(args.raw)
    rng = random.Random(args.seed)
    rng.shuffle(raw_rows)

    queue_rows: list[dict[str, str]] = []
    key_rows: list[dict[str, str]] = []
    for index, row in enumerate(raw_rows, start=1):
        blind_id = f"B{index:06d}"
        case_id = row["case_id"]
        queue_rows.append(
            {
                "blind_id": blind_id,
                "project_alias": row["project_alias"],
                "case_id": case_id,
                "question_type": row["question_type"],
                "question": row["question"],
                "answer": row["answer"],
                "confidence": row["confidence"],
                "expected_behavior": row["expected_behavior"],
                "expected_citation_types_any_of": row["expected_citation_types_any_of"],
                "required_citation_types_all_of": row["required_citation_types_all_of"],
                "case_notes": case_notes.get(case_id, ""),
                "raw_citation_ids_json": row["raw_citation_ids_json"],
                "returned_citation_refs_json": row["returned_citation_refs_json"],
                "returned_citation_types_json_or_blank": row[
                    "returned_citation_types_json_or_blank"
                ],
                "source_table_json": row["source_table_json"],
                "raw_citation_id_type_map_json": row["raw_citation_id_type_map_json"],
                "retrieval_hit_types_json": row["retrieval_hit_types_json"],
                "citation_type_source": row["citation_type_source"],
                "source_table_capture_mode": row["source_table_capture_mode"],
                "fallback_reason_or_blank": row["fallback_reason_or_blank"],
                "sentinel_leaked": row["sentinel_leaked"],
            }
        )
        key_rows.append(
            {
                "blind_id": blind_id,
                "case_id": case_id,
                "project_alias": row["project_alias"],
                "prompt_version": row["prompt_version"],
                "prompt_path": row["prompt_path"],
                "raw_csv_path": row["_raw_csv_path"],
            }
        )

    _write_csv(args.queue, QUEUE_FIELDNAMES, queue_rows)
    _write_csv(args.key, KEY_FIELDNAMES, key_rows)
    _write_csv(args.project_key, PROJECT_KEY_FIELDNAMES, _project_key_rows(template))
    print(
        f"wrote queue={len(queue_rows)} key={len(key_rows)} "
        f"project_key={len(_project_key_rows(template))}"
    )
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("json_root_must_be_object")
    return data


def _validate_resolved_projects(template: dict[str, Any], resolved: dict[str, Any]) -> None:
    selected = [str(alias) for alias in template.get("selected_project_aliases", [])]
    resolved_projects = resolved.get("projects", {})
    if not isinstance(resolved_projects, dict):
        raise ValueError("invalid_project_map_resolved")
    missing = [alias for alias in selected if alias not in resolved_projects]
    if missing:
        raise ValueError(f"resolved_project_missing:{','.join(missing)}")


def _load_case_notes(template: dict[str, Any]) -> dict[str, str]:
    notes: dict[str, str] = {}
    projects = template.get("projects", {})
    if not isinstance(projects, dict):
        raise ValueError("invalid_project_map_template")
    for value in projects.values():
        if not isinstance(value, dict):
            continue
        source_case_dir = value.get("source_case_dir")
        if not isinstance(source_case_dir, str):
            continue
        path = Path(source_case_dir) / "questions.jsonl"
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                case = json.loads(line)
                notes[str(case["case_id"])] = str(case.get("case_notes", ""))
    return notes


def _load_raw_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                copied = dict(row)
                copied["_raw_csv_path"] = str(path)
                rows.append(copied)
    if not rows:
        raise ValueError("raw_rows_empty")
    return rows


def _project_key_rows(template: dict[str, Any]) -> list[dict[str, str]]:
    selected = [str(alias) for alias in template.get("selected_project_aliases", [])]
    projects = template.get("projects", {})
    if not isinstance(projects, dict):
        raise ValueError("invalid_project_map_template")
    rows: list[dict[str, str]] = []
    for alias in selected:
        project = projects.get(alias)
        if not isinstance(project, dict):
            raise ValueError(f"project_missing:{alias}")
        rows.append(
            {
                "project_alias": alias,
                "source_case_dir": str(project.get("source_case_dir", "")),
                "domain": str(project.get("domain", "")),
                "fixture_class": str(project.get("fixture_class", "")),
            }
        )
    return rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
