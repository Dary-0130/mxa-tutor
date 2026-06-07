"""Finalize TASK-306 human scoring with two-stage adjudication."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from loguru import logger

SCORE_COLUMNS = [
    "factual",
    "citation",
    "teaching",
    "actionable",
    "no_fabrication",
    "total",
    "scorer_notes",
]

RAW_SCORE_COLUMNS = [
    "factual",
    "citation",
    "teaching",
    "actionable",
    "no_fabrication",
    "total",
    "scorer_notes",
]

FINAL_EXTRA_COLUMNS = [
    "pm_factual",
    "pm_citation",
    "pm_teaching",
    "pm_actionable",
    "pm_no_fabrication",
    "pm_total",
    "pm_scorer_notes",
    "reviewer_factual",
    "reviewer_citation",
    "reviewer_teaching",
    "reviewer_actionable",
    "reviewer_no_fabrication",
    "reviewer_total",
    "reviewer_scorer_notes",
    "adjudication_required",
    "adjudicated_total",
    "adjudicator_notes",
    "case_final_total",
]

ADJUDICATION_FIELDNAMES = [
    "blind_id",
    "project_alias",
    "question_type",
    "question",
    "answer",
    "pm_factual",
    "pm_citation",
    "pm_teaching",
    "pm_actionable",
    "pm_no_fabrication",
    "pm_total",
    "pm_scorer_notes",
    "reviewer_factual",
    "reviewer_citation",
    "reviewer_teaching",
    "reviewer_actionable",
    "reviewer_no_fabrication",
    "reviewer_total",
    "reviewer_scorer_notes",
    "delta_factual",
    "delta_citation",
    "delta_teaching",
    "delta_actionable",
    "delta_no_fabrication",
    "delta_total",
    "adjudication_reason",
]

RESOLVED_FIELDNAMES = ["blind_id", "adjudicated_total", "adjudicator_notes"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize TASK-306 scored queues")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--scored-pm", required=True, type=Path)
    parser.add_argument("--scored-reviewer", required=True, type=Path)
    parser.add_argument("--raw", action="append", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--adjudication-resolved", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    queue = _load_csv(args.queue)
    key = _load_csv(args.key)
    raw_rows = _load_raw_rows(args.raw)
    pm_scores = _load_scores(args.scored_pm, queue, scorer="PM")
    reviewer_scores = _load_scores(args.scored_reviewer, queue, scorer="reviewer")
    merged = _merge_queue_scores(queue, key, raw_rows, pm_scores, reviewer_scores)
    required = [row for row in merged if row["adjudication_required"] == "true"]

    if args.adjudication_resolved is None and required:
        _write_csv(out_dir / "adjudication_queue.csv", ADJUDICATION_FIELDNAMES, required)
        logger.info(
            "ADJUDICATION REQUIRED: {} cases pending. Fill adjudication_resolved.csv "
            "and rerun with --adjudication-resolved",
            len(required),
        )
        return 2

    resolved = (
        _load_adjudication_resolved(args.adjudication_resolved)
        if args.adjudication_resolved is not None
        else {}
    )
    unresolved = [
        row["blind_id"]
        for row in required
        if row["blind_id"] not in resolved or resolved[row["blind_id"]]["adjudicated_total"] == ""
    ]
    if unresolved:
        logger.error("UNRESOLVED ADJUDICATION: {}", ",".join(unresolved))
        return 2

    final_rows = _apply_final_totals(merged, resolved)
    raw_fieldnames = list(raw_rows[0].keys()) if raw_rows else []
    _write_unblind_outputs(out_dir, final_rows, raw_rows, raw_fieldnames)
    _write_csv(
        out_dir / "qa_final_scored_merged.csv", raw_fieldnames + FINAL_EXTRA_COLUMNS, final_rows
    )
    adjudicated_count = sum(1 for row in final_rows if row["adjudicated_total"] != "")
    _print_stats(final_rows, raw_rows, adjudicated_count=adjudicated_count)
    return 0


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"csv_empty:{path}")
    return rows


def _load_raw_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        for row in _load_csv(path):
            rows.append(row)
    return rows


def _load_scores(
    path: Path,
    queue: list[dict[str, str]],
    *,
    scorer: str,
) -> dict[str, dict[str, str]]:
    expected = {row["blind_id"] for row in queue}
    rows = _load_csv(path)
    seen = {row["blind_id"] for row in rows}
    if expected != seen:
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        raise ValueError(f"{scorer}_blind_id_coverage_failed:missing={missing}:extra={extra}")
    return {row["blind_id"]: _normalized_score(row) for row in rows}


def _normalized_score(row: dict[str, str]) -> dict[str, str]:
    factual = _score_int(row, "factual", 0, 30)
    citation = _score_int(row, "citation", 0, 20)
    teaching = _score_int(row, "teaching", 0, 20)
    actionable = _score_int(row, "actionable", 0, 20)
    no_fabrication = _score_int(row, "no_fabrication", 0, 10)
    total = factual + citation + teaching + actionable + no_fabrication
    return {
        "factual": str(factual),
        "citation": str(citation),
        "teaching": str(teaching),
        "actionable": str(actionable),
        "no_fabrication": str(no_fabrication),
        "total": str(total),
        "scorer_notes": row.get("scorer_notes", ""),
    }


def _score_int(row: dict[str, str], key: str, low: int, high: int) -> int:
    try:
        value = int(row.get(key, ""))
    except ValueError:
        raise ValueError(f"score_not_int:{row.get('blind_id', '')}:{key}") from None
    if value < low or value > high:
        raise ValueError(f"score_out_of_range:{row.get('blind_id', '')}:{key}")
    return value


def _merge_queue_scores(
    queue: list[dict[str, str]],
    key: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    pm_scores: dict[str, dict[str, str]],
    reviewer_scores: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    key_by_blind = {row["blind_id"]: row for row in key}
    raw_by_case_version = {(row["case_id"], row["prompt_version"]): row for row in raw_rows}
    merged: list[dict[str, str]] = []
    for queue_row in queue:
        blind_id = queue_row["blind_id"]
        key_row = key_by_blind[blind_id]
        raw = raw_by_case_version[(key_row["case_id"], key_row["prompt_version"])]
        pm = pm_scores[blind_id]
        reviewer = reviewer_scores[blind_id]
        deltas = _deltas(pm, reviewer)
        required, reason = _adjudication_requirement(deltas)
        merged_row = {
            **raw,
            "blind_id": blind_id,
            "project_alias": queue_row["project_alias"],
            "question_type": queue_row["question_type"],
            "question": queue_row["question"],
            "answer": queue_row["answer"],
            "pm_factual": pm["factual"],
            "pm_citation": pm["citation"],
            "pm_teaching": pm["teaching"],
            "pm_actionable": pm["actionable"],
            "pm_no_fabrication": pm["no_fabrication"],
            "pm_total": pm["total"],
            "pm_scorer_notes": pm["scorer_notes"],
            "reviewer_factual": reviewer["factual"],
            "reviewer_citation": reviewer["citation"],
            "reviewer_teaching": reviewer["teaching"],
            "reviewer_actionable": reviewer["actionable"],
            "reviewer_no_fabrication": reviewer["no_fabrication"],
            "reviewer_total": reviewer["total"],
            "reviewer_scorer_notes": reviewer["scorer_notes"],
            "delta_factual": str(deltas["factual"]),
            "delta_citation": str(deltas["citation"]),
            "delta_teaching": str(deltas["teaching"]),
            "delta_actionable": str(deltas["actionable"]),
            "delta_no_fabrication": str(deltas["no_fabrication"]),
            "delta_total": str(deltas["total"]),
            "adjudication_reason": reason,
            "adjudication_required": "true" if required else "false",
            "adjudicated_total": "",
            "adjudicator_notes": "",
            "case_final_total": "",
        }
        merged.append(merged_row)
    return merged


def _deltas(pm: dict[str, str], reviewer: dict[str, str]) -> dict[str, int]:
    keys = ["factual", "citation", "teaching", "actionable", "no_fabrication", "total"]
    return {key: abs(int(pm[key]) - int(reviewer[key])) for key in keys}


def _adjudication_requirement(deltas: dict[str, int]) -> tuple[bool, str]:
    reasons: list[str] = []
    if deltas["total"] > 15:
        reasons.append("total_delta>15")
    if deltas["factual"] > 15:
        reasons.append("dim_factual_delta>15")
    for key in ("citation", "teaching", "actionable"):
        if deltas[key] > 10:
            reasons.append(f"dim_{key}_delta>10")
    return bool(reasons), ";".join(reasons)


def _load_adjudication_resolved(path: Path) -> dict[str, dict[str, str]]:
    rows = _load_csv(path)
    resolved: dict[str, dict[str, str]] = {}
    for row in rows:
        blind_id = row["blind_id"]
        total = row.get("adjudicated_total", "")
        if total != "":
            value = int(total)
            if value < 0 or value > 100:
                raise ValueError(f"adjudicated_total_out_of_range:{blind_id}")
        resolved[blind_id] = {
            "adjudicated_total": total,
            "adjudicator_notes": row.get("adjudicator_notes", ""),
        }
    return resolved


def _apply_final_totals(
    merged: list[dict[str, str]],
    resolved: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    final_rows: list[dict[str, str]] = []
    for row in merged:
        blind_id = row["blind_id"]
        adjudication = resolved.get(blind_id, {})
        adjudicated_total = adjudication.get("adjudicated_total", "")
        row = dict(row)
        row["adjudicated_total"] = adjudicated_total
        row["adjudicator_notes"] = adjudication.get("adjudicator_notes", "")
        if adjudicated_total != "":
            row["case_final_total"] = adjudicated_total
        else:
            average = (int(row["pm_total"]) + int(row["reviewer_total"])) / 2
            row["case_final_total"] = _format_number(average)
        final_rows.append(row)
    return final_rows


def _write_unblind_outputs(
    out_dir: Path,
    final_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    raw_fieldnames: list[str],
) -> None:
    versions = sorted({row["prompt_version"] for row in raw_rows})
    for scorer, prefix in (("PM", "pm"), ("reviewer", "reviewer")):
        for version in versions:
            rows = [
                {
                    **{field: row.get(field, "") for field in raw_fieldnames},
                    **{
                        "factual": row[f"{prefix}_factual"],
                        "citation": row[f"{prefix}_citation"],
                        "teaching": row[f"{prefix}_teaching"],
                        "actionable": row[f"{prefix}_actionable"],
                        "no_fabrication": row[f"{prefix}_no_fabrication"],
                        "total": row[f"{prefix}_total"],
                        "scorer_notes": row[f"{prefix}_scorer_notes"],
                    },
                }
                for row in final_rows
                if row["prompt_version"] == version
            ]
            _write_csv(
                out_dir / f"{_version_file_prefix(version)}_scored_{scorer}.csv",
                raw_fieldnames + RAW_SCORE_COLUMNS,
                rows,
            )


def _version_file_prefix(version: str) -> str:
    if version == "v0.1":
        return "qa_v0.1_baseline"
    if version == "v0.2-rc":
        return "qa_v0.2_rc"
    return f"qa_{version.replace('-', '_')}"


def _print_stats(
    final_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    *,
    adjudicated_count: int,
) -> None:
    mean_raw = statistics.fmean(
        (int(row["pm_total"]) + int(row["reviewer_total"])) / 2 for row in final_rows
    )
    mean_final = statistics.fmean(float(row["case_final_total"]) for row in final_rows)
    stats = {
        "mean_raw_two_scorer_total": _format_number(mean_raw),
        "mean_case_final_total": _format_number(mean_final),
        "adjudicated_case_count": adjudicated_count,
        "unresolved_adjudication_count": 0,
        "core_success_rate": _success_rate(raw_rows, eval_set="core"),
        "diagnostic_success_rate": _success_rate(raw_rows, eval_set="diagnostic"),
        "overall_success_rate": _success_rate(raw_rows),
        "citation_type_available_rate": _citation_type_available_rate(raw_rows),
    }
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True), flush=True)


def _success_rate(rows: list[dict[str, str]], eval_set: str | None = None) -> str:
    selected = [row for row in rows if eval_set is None or row["eval_set"] == eval_set]
    if not selected:
        return ""
    successes = sum(1 for row in selected if row.get("error_type", "") == "")
    return _format_number(successes / len(selected))


def _citation_type_available_rate(rows: list[dict[str, str]]) -> str:
    selected = [
        row
        for row in rows
        if row.get("eval_set") == "core" and row.get("expected_behavior") == "answer"
    ]
    if not selected:
        return ""
    available = sum(1 for row in selected if row.get("citation_type_source") != "unavailable")
    return _format_number(available / len(selected))


def _format_number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
