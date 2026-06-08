from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import AppSettings
from core.domain.exceptions import ChatGenerationError, LLMError, LLMTimeoutError
from eval._bootstrap import EvalAuditContext, build_chat_service_for_eval
from features.chunking import ChunkingService
from features.overview.overview_schemas import ProjectOverview
from features.overview.project_graph_builder import ProjectGraphBuilder


AD_HOC_ROOT = ROOT / "eval" / "ad_hoc"
QUESTIONS_PATH = AD_HOC_ROOT / "questions.jsonl"
PROJECT_MAP_PATH = AD_HOC_ROOT / "project_map_resolved.json"
EVAL_DB_PATH = AD_HOC_ROOT / "eval.sqlite"
PROMPT_PATH = ROOT / "core" / "prompts" / "qa_with_context.yaml"
OVERVIEWS_DIR = AD_HOC_ROOT / "overviews"
ANSWER_RECORDS_PATH = AD_HOC_ROOT / "answer_records.jsonl"
RESULTS_MD_PATH = AD_HOC_ROOT / "results.md"
RUN_METADATA_PATH = AD_HOC_ROOT / "run_metadata.json"

ALIASES = ["01_ee_a", "02_ee_b", "03_ee_c", "04_ee_d"]
QUESTION_TYPES = {"总体", "模块", "参数", "修改"}
EXPECTED_TYPE_COUNTS = {"总体": 20, "模块": 20, "参数": 12, "修改": 8}


def load_questions() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(QUESTIONS_PATH.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_jsonl_line:{line_number}") from exc
        rows.append(row)
    validate_questions(rows)
    return rows


def validate_questions(rows: list[dict[str, str]]) -> None:
    if len(rows) != 60:
        raise ValueError(f"questions_count_mismatch:{len(rows)}")
    required = {"case_id", "project_alias", "question_type", "question"}
    for index, row in enumerate(rows, 1):
        missing = required - set(row)
        extra = set(row) - required
        if missing:
            raise ValueError(f"question_missing_fields:{index}:{sorted(missing)}")
        if extra:
            raise ValueError(f"question_extra_fields:{index}:{sorted(extra)}")
        alias = row["project_alias"]
        if alias not in ALIASES:
            raise ValueError(f"question_bad_alias:{index}:{alias}")
        if row["question_type"] not in QUESTION_TYPES:
            raise ValueError(f"question_bad_type:{index}:{row['question_type']}")
        expected_case = f"{alias}_{index_for_alias(rows[:index], alias):03d}"
        if row["case_id"] != expected_case:
            raise ValueError(f"question_case_id_mismatch:{index}:{row['case_id']}:{expected_case}")
        if not row["question"].strip():
            raise ValueError(f"question_empty:{index}")

    type_counts = Counter(row["question_type"] for row in rows)
    if dict(type_counts) != EXPECTED_TYPE_COUNTS:
        raise ValueError(f"question_type_distribution_mismatch:{dict(type_counts)}")
    alias_counts = Counter(row["project_alias"] for row in rows)
    if any(alias_counts[alias] != 15 for alias in ALIASES):
        raise ValueError(f"question_alias_distribution_mismatch:{dict(alias_counts)}")


def index_for_alias(rows: list[dict[str, str]], alias: str) -> int:
    return sum(1 for row in rows if row.get("project_alias") == alias)


def load_runtime_ids() -> dict[str, str]:
    data = json.loads(PROJECT_MAP_PATH.read_text(encoding="utf-8"))
    projects = data.get("projects", {})
    mapping: dict[str, str] = {}
    for alias in ALIASES:
        item = projects.get(alias, {})
        runtime_id = item.get("runtime_project_id") if isinstance(item, dict) else None
        if not isinstance(runtime_id, str) or not runtime_id:
            raise ValueError(f"missing_runtime_project_id:{alias}")
        mapping[alias] = runtime_id
    return mapping


async def add_overview_chunks(audit: EvalAuditContext, runtime_ids: dict[str, str]) -> int:
    settings = AppSettings(db_path=str(EVAL_DB_PATH))
    hybrid = audit.recording_retriever.inner
    vector = getattr(hybrid, "_vector")
    embedder = getattr(vector, "_embedder")
    chunking = ChunkingService(
        embedder=embedder,
        vector_store=audit.vector_store,
        graph_provider=ProjectGraphBuilder(),
        settings=settings,
    )
    added = 0
    for alias, project_id in runtime_ids.items():
        overview_path = OVERVIEWS_DIR / f"{alias}.json"
        overview = ProjectOverview.model_validate(
            json.loads(overview_path.read_text(encoding="utf-8"))
        )
        added += await chunking.build_embed_store_overview_chunk(overview, project_id)
    await chunking.aclose()
    return added


async def answer_case(
    chat_service: Any,
    audit: EvalAuditContext,
    case: dict[str, str],
    runtime_project_id: str,
) -> dict[str, Any]:
    attempts: list[dict[str, str]] = []
    response = None
    error_type = ""
    error_message = ""
    started = time.perf_counter()
    for attempt in range(1, 3):
        audit.reset_case()
        try:
            response = await chat_service.handle_chat(
                project_id=runtime_project_id,
                question=case["question"],
                session_id=None,
            )
            error_type = ""
            error_message = ""
            break
        except LLMTimeoutError:
            error_type = "llm_timeout"
            error_message = "llm_timeout"
        except LLMError:
            error_type = "llm_api_error"
            error_message = "llm_api_error"
        except ChatGenerationError:
            error_type = "parse_validation_error"
            error_message = "parse_validation_error"
        except Exception as exc:
            error_type = "unexpected_error"
            error_message = type(exc).__name__
        attempts.append({"attempt": str(attempt), "error_type": error_type})
        if attempt == 1:
            await asyncio.sleep(0.5)

    total_duration_ms = int((time.perf_counter() - started) * 1000)
    audit_fields = audit.collect_per_case_audit(response)
    citations = citation_summaries(response, audit)
    record = {
        "case_id": case["case_id"],
        "project_alias": case["project_alias"],
        "runtime_project_id": runtime_project_id,
        "question_type": case["question_type"],
        "question": case["question"],
        "answer": response.answer if response is not None else f"[ERROR: {error_message}]",
        "confidence": response.confidence if response is not None else "",
        "citations": citations,
        "session_id": response.session_id if response is not None else "",
        "is_fallback": bool(response.is_fallback) if response is not None else False,
        "fallback_reason": response.fallback_reason if response is not None else "",
        "error_type": error_type,
        "error_message_sanitized": error_message,
        "attempts": attempts,
        "total_duration_ms": total_duration_ms,
        "audit": audit_fields,
    }
    with ANSWER_RECORDS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def citation_summaries(response: Any, audit: EvalAuditContext) -> list[dict[str, Any]]:
    if response is None:
        return []
    entries = list(audit.recording_prompt_builder.last_source_entries)
    used = [citation.to_domain() for citation in response.citations]
    summaries: list[dict[str, Any]] = []
    for citation in used:
        entry = match_source_entry(citation, entries)
        ref = asdict(citation)
        if entry is None:
            summaries.append(
                {
                    "source_id": "",
                    "source_type": "",
                    "source_ref": strip_empty(ref),
                    "snippet": "",
                }
            )
            continue
        summaries.append(
            {
                "source_id": str(entry.source_id),
                "source_type": str(entry.hit.source_type),
                "source_ref": strip_empty(ref),
                "snippet": str(entry.snippet),
            }
        )
    return summaries


def match_source_entry(citation: Any, entries: list[Any]) -> Any | None:
    for entry in entries:
        ref = entry.source_ref
        if ref.file_path != citation.file_path:
            continue
        if citation.block_name and ref.block_name != citation.block_name:
            continue
        if citation.block_id and ref.block_id != citation.block_id:
            continue
        if citation.parameter_name and ref.parameter_name != citation.parameter_name:
            continue
        return entry
    return None


def strip_empty(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def render_results_md(records: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    lines = [
        f"# mxa 评测结果(2026-06-08;v0.2-rc;run_id {metadata['run_id']})",
        "",
        (
            f"> 4 个 EE slx 工程;60 题;模型 {metadata['model_name']};"
            f"prompt qa_with_context.yaml {metadata['prompt_version']}"
        ),
        "> 题源来自产品导览,出题端有元循环风险;本轮为 slx-only ad-hoc 评测。",
        "> 评分员:PM + 研究生(双盲;先不要互看);分歧以工程作者真值为准。",
        "",
        "## 目录",
    ]
    for alias in ALIASES:
        lines.append(f"- [{alias}](#{alias})(15 题)")
    lines.extend(["", "---", ""])

    by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_alias[record["project_alias"]].append(record)

    for alias in ALIASES:
        lines.extend([f"## {alias}", ""])
        for record in sorted(by_alias[alias], key=lambda item: item["case_id"]):
            lines.extend(render_record(record))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_record(record: dict[str, Any]) -> list[str]:
    question_type = record["question_type"]
    confidence = record["confidence"] or "error"
    lines = [
        f"### Q{record['case_id']} — {question_type}题",
        "",
        f"**题目**:{record['question']}",
        "",
        f"**mxa 答案**(confidence: {confidence}):",
        "",
        record["answer"].strip(),
        "",
        f"**证据引用**({len(record['citations'])} 条):",
        "",
    ]
    if not record["citations"]:
        lines.append("无")
    else:
        for index, citation in enumerate(record["citations"], 1):
            ref = citation["source_ref"]
            path = ref.get("file_path", "")
            block = ref.get("block_name") or ref.get("parameter_name") or "__project_overview__"
            snippet = citation["snippet"].replace("\n", " ")[:100]
            lines.append(
                f"{index}. [{citation['source_id'] or 'S?'}] "
                f"`{citation['source_type'] or 'unknown'}` / `{path}` / "
                f"`{block}` / snippet 前 100 字:`{snippet}`"
            )
    if record["error_type"]:
        lines.extend(["", f"**运行错误**:{record['error_message_sanitized']}"])
    elif record["is_fallback"]:
        lines.extend(["", f"**Fallback**:{record['fallback_reason']}"])
    lines.extend(
        [
            "",
            "---",
            "",
            "#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)",
            "",
            "**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**",
            "- 备注:",
            "",
            "**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**",
            "- 备注:",
            "",
            "---",
            "",
        ]
    )
    return lines


async def main() -> int:
    questions = load_questions()
    runtime_ids = load_runtime_ids()
    if ANSWER_RECORDS_PATH.exists():
        ANSWER_RECORDS_PATH.unlink()

    run_id = "ad_hoc_20260608_" + datetime.now().strftime("%H%M%S")
    started_at = datetime.now().isoformat()
    chat_service, audit = build_chat_service_for_eval(PROMPT_PATH, EVAL_DB_PATH)
    overview_chunks_added = 0
    records: list[dict[str, Any]] = []
    try:
        overview_chunks_added = await add_overview_chunks(audit, runtime_ids)
        for index, case in enumerate(questions, 1):
            record = await answer_case(
                chat_service,
                audit,
                case,
                runtime_ids[case["project_alias"]],
            )
            records.append(record)
            print(
                json.dumps(
                    {
                        "done": index,
                        "case_id": record["case_id"],
                        "confidence": record["confidence"],
                        "citations": len(record["citations"]),
                        "error_type": record["error_type"],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                flush=True,
            )
            if index != len(questions):
                await asyncio.sleep(0.5)
    finally:
        await audit.aclose()

    ended_at = datetime.now().isoformat()
    success_count = sum(1 for record in records if not record["error_type"])
    failures = [
        {
            "case_id": record["case_id"],
            "error_type": record["error_type"],
            "error_message_sanitized": record["error_message_sanitized"],
        }
        for record in records
        if record["error_type"]
    ]
    metadata = {
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "prompt_path": "core/prompts/qa_with_context.yaml",
        "prompt_version": audit.loaded_prompt_version,
        "loaded_prompt_path": audit.loaded_prompt_path,
        "model_name": audit.model_name,
        "temperature": "",
        "top_p": "",
        "question_count": len(questions),
        "success_count": success_count,
        "failure_count": len(failures),
        "fallback_count": sum(1 for record in records if record["is_fallback"]),
        "overview_chunks_added": overview_chunks_added,
        "handle_chat_attempt_count": sum(max(1, len(record["attempts"])) for record in records),
        "failures": failures,
    }
    RUN_METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    RESULTS_MD_PATH.write_text(render_results_md(records, metadata), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
