"""Local PDF smoke lane for paper-to-model true-run evaluation.

This script is intentionally local-only: it reads real PDFs from a configured
folder, writes artifacts under ``eval/out/``, and uses a temporary SQLite DB and
upload directory so it never touches ``data/mxa.db``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import aiosqlite
from fastapi import UploadFile
from pydantic import ValidationError
from starlette.responses import JSONResponse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.llm import DeepSeekTextProvider
from adapters.parser.docx_parser import DocxParser
from adapters.parser.pdf_parser import PdfParser
from adapters.storage.schema import init_schema
from adapters.storage.sqlite_paper_cache import SqlitePaperBundleStore, SqlitePaperSpecCacheView
from api.routes.paper_upload import UploadDocumentResponse, upload_document
from app.config import AppSettings
from core.domain.exceptions import PaperSpecGenerationError
from core.domain.paper_plan import PaperPlanRecord
from core.domain.paper_upload_job import PaperUploadJobRecord
from core.interfaces.document_parser import DocumentParserRouter
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper.paper_plan_helpers import (
    BuildStepsDtoValidationError,
    BuildStepsEvidenceError,
    BuildStepsRedLineError,
    BuildStepsStructuredError,
    ModelBuildStepDraft,
    apply_plan_evidence_reference_bridge,
    build_plan_evidence_source_refs,
)
from features.paper.paper_plan_service import (
    BUILD_STEP_ROLE_NAME,
    PaperPlanService,
    _BuildStepsOutputModel,
    _log_omitted_build_step_block_reference_count,
    _preserve_present_invalid_block_ref_paper_references,
)
from features.paper.paper_reparse_service import PaperReparseLockRegistry
from features.paper.paper_spec_service import PaperSpecService

DEFAULT_PAPER_EVAL_DIR_ENV = "PAPER_EVAL_DIR"
DEFAULT_PAPER_EVAL_DIR = r"E:\桌面\样例"
DEFAULT_OUTPUT_ROOT = Path("eval/out/paper_pdf_smoke")
DEFAULT_ROUNDS = 1
HYBRID_ARXIV_IDS = frozenset({"2003.10496", "2107.02719", "2410.04316"})
ARXIV_ID_RE = re.compile(r"arxiv-(?P<id>\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)

BuildStepsResultCode = Literal[
    "结构化成功",
    "dto_invalid",
    "json_parse_failed",
    "br_no_match",
    "redline",
    "evidence_invalid",
    "coverage_missing",
    "其它",
]

SUMMARY_COLUMNS = [
    "run_id",
    "paper_file",
    "arxiv_id",
    "round_index",
    "main_terminal_state",
    "paper_id",
    "job_id",
    "error_code",
    "failure_stage",
    "spec_validation_errors",
    "build_steps_result_code",
    "build_steps_raw_reason_code",
    "build_steps_finish_reason",
    "build_steps_prompt_tokens",
    "build_steps_completion_tokens",
    "build_steps_total_tokens",
    "build_steps_max_tokens",
    "guidance_reached",
    "guidance_status",
    "dto_invalid_errors",
    "hybrid_candidate",
    "hybrid_guardrail_conclusion",
    "hybrid_no_document_basis_misfire",
]

_CURRENT_LLM_ROLE: ContextVar[str | None] = ContextVar("paper_pdf_smoke_llm_role", default=None)


@dataclass(frozen=True)
class SmokePaper:
    path: Path
    arxiv_id: str | None
    hybrid_candidate: bool

    @property
    def slug(self) -> str:
        return self.path.stem.replace(" ", "_")


@dataclass(frozen=True)
class SmokeRuntime:
    run_id: str
    output_dir: Path
    db_path: Path
    upload_dir: Path
    actual_dir: Path


@dataclass(frozen=True)
class LLMCallRecord:
    role: str | None
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    max_tokens: int | None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class BuildStepsTelemetry:
    spec_validation_errors: list[dict[str, object]] = field(default_factory=list)
    fallback_reason_code: str | None = None
    fallback_exception_type: str | None = None
    dto_invalid_errors: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SmokeSummaryRow:
    run_id: str
    paper_file: str
    arxiv_id: str | None
    round_index: int
    main_terminal_state: str
    paper_id: str | None
    job_id: str | None
    error_code: str | None
    failure_stage: str | None
    spec_validation_errors: list[dict[str, object]]
    build_steps_result_code: BuildStepsResultCode
    build_steps_raw_reason_code: str | None
    build_steps_finish_reason: str | None
    build_steps_prompt_tokens: int | None
    build_steps_completion_tokens: int | None
    build_steps_total_tokens: int | None
    build_steps_max_tokens: int | None
    guidance_reached: bool
    guidance_status: str
    dto_invalid_errors: list[dict[str, str]]
    hybrid_candidate: bool
    hybrid_guardrail_conclusion: str
    hybrid_no_document_basis_misfire: bool | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {column: payload[column] for column in SUMMARY_COLUMNS}


class ProviderFactory(Protocol):
    def __call__(self, settings: AppSettings) -> TextProvider: ...


class SettingsFactory(Protocol):
    def __call__(self, runtime: SmokeRuntime) -> AppSettings: ...


class RoundRunner(Protocol):
    async def __call__(
        self,
        paper: SmokePaper,
        round_index: int,
        runtime: SmokeRuntime,
        settings: AppSettings,
        store: SqlitePaperBundleStore,
        provider_factory: ProviderFactory,
    ) -> SmokeSummaryRow: ...


class RecordingTextProvider(TextProvider):
    """TextProvider wrapper that records sanitized per-leaf usage metadata."""

    def __init__(self, delegate: TextProvider) -> None:
        self._delegate = delegate
        self.calls: list[LLMCallRecord] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        response = self._delegate.chat(
            messages,
            json_mode=json_mode,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self.calls.append(
            LLMCallRecord(
                role=_CURRENT_LLM_ROLE.get(),
                finish_reason=response.finish_reason,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                max_tokens=max_tokens,
            )
        )
        return response

    def capability(self) -> ModelCapability:
        return self._delegate.capability()

    def last_call_for_role(self, role: str) -> LLMCallRecord | None:
        for call in reversed(self.calls):
            if call.role == role:
                return call
        return None


class RecordingPaperSpecService(PaperSpecService):
    """Eval-only subclass that records sanitized spec validation failure details."""

    def __init__(
        self,
        *args: Any,
        telemetry: BuildStepsTelemetry,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._smoke_telemetry = telemetry

    def _record_spec_exhausted(self, exc: PaperSpecGenerationError) -> None:
        _record_spec_validation_errors(self._smoke_telemetry, exc.validation_errors)
        super()._record_spec_exhausted(exc)

    def _record_spec_retry(
        self,
        exc: PaperSpecGenerationError,
        remaining_structured_retries: int,
    ) -> None:
        _record_spec_validation_errors(self._smoke_telemetry, exc.validation_errors)
        super()._record_spec_retry(exc, remaining_structured_retries)


class RecordingPaperPlanService(PaperPlanService):
    """Eval-only subclass that records build-step fallback details."""

    def __init__(
        self,
        text_provider: TextProvider,
        *,
        telemetry: BuildStepsTelemetry,
    ) -> None:
        super().__init__(text_provider=text_provider)
        self._smoke_telemetry = telemetry

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        role_name: str,
    ) -> dict[str, Any]:
        token = _CURRENT_LLM_ROLE.set(role_name)
        try:
            return await super()._call_llm_json(messages, role_name)
        finally:
            _CURRENT_LLM_ROLE.reset(token)

    async def _llm_build_steps(
        self,
        block_recommendations,
        parameter_mapping,
        spec,
    ) -> list[ModelBuildStepDraft]:
        data = await self._call_llm_json(
            self._build_step_messages(block_recommendations, parameter_mapping, spec),
            BUILD_STEP_ROLE_NAME,
        )
        source_refs = build_plan_evidence_source_refs(spec)
        raw_data = data
        data = apply_plan_evidence_reference_bridge(data, source_refs)
        _preserve_present_invalid_block_ref_paper_references(raw_data, data)
        _log_omitted_build_step_block_reference_count(raw_data, role_name=BUILD_STEP_ROLE_NAME)
        if data.get("build_steps") == []:
            raise BuildStepsDtoValidationError("empty_steps")
        try:
            model = _BuildStepsOutputModel.model_validate(data)
        except ValidationError as exc:
            self._smoke_telemetry.dto_invalid_errors = _pydantic_loc_type_errors(exc)
            raise BuildStepsDtoValidationError("dto_invalid") from None
        return model.to_drafts()

    def _build_step_messages(self, block_recommendations, parameter_mapping, spec):
        from features.paper._prompt_builder import build_messages_for_build_steps

        return build_messages_for_build_steps(
            block_recommendations,
            parameter_mapping,
            spec.evidence,
            build_plan_evidence_source_refs(spec),
        )

    def _log_build_steps_fallback(self, exc: BuildStepsStructuredError) -> None:
        self._smoke_telemetry.fallback_reason_code = exc.reason_code
        self._smoke_telemetry.fallback_exception_type = type(exc).__name__
        super()._log_build_steps_fallback(exc)


def default_paper_dir() -> Path:
    return Path(os.environ.get(DEFAULT_PAPER_EVAL_DIR_ENV, DEFAULT_PAPER_EVAL_DIR))


def discover_papers(paper_dir: Path, pattern: str = "*.pdf") -> list[SmokePaper]:
    if not paper_dir.is_dir():
        raise SystemExit(f"paper eval dir not found: {paper_dir}")
    papers: list[SmokePaper] = []
    for path in sorted(paper_dir.glob(pattern)):
        if not path.is_file():
            continue
        arxiv_id = _arxiv_id_from_filename(path.name)
        papers.append(
            SmokePaper(
                path=path.resolve(),
                arxiv_id=arxiv_id,
                hybrid_candidate=arxiv_id in HYBRID_ARXIV_IDS,
            )
        )
    if not papers:
        raise SystemExit(f"no PDF papers matched {pattern!r} under {paper_dir}")
    return papers


async def run_smoke(
    *,
    paper_dir: Path,
    output_dir: Path | None,
    rounds: int,
    pattern: str = "*.pdf",
    limit: int | None = None,
    settings_factory: SettingsFactory | None = None,
    provider_factory: ProviderFactory | None = None,
    round_runner: RoundRunner | None = None,
) -> tuple[SmokeRuntime, list[SmokeSummaryRow]]:
    if rounds < 1:
        raise SystemExit("--rounds must be >= 1")
    papers = discover_papers(paper_dir, pattern=pattern)
    if limit is not None:
        papers = papers[:limit]
    runtime = _prepare_runtime(output_dir)
    await _init_temp_db(runtime.db_path)
    settings = (settings_factory or _default_settings_factory)(runtime)
    store = SqlitePaperBundleStore(str(runtime.db_path))
    runner = round_runner or _run_one_pdf_round
    provider_builder = provider_factory or _default_provider_factory
    rows: list[SmokeSummaryRow] = []
    for paper in papers:
        for round_index in range(1, rounds + 1):
            row = await runner(paper, round_index, runtime, settings, store, provider_builder)
            rows.append(row)
            write_summary_artifacts(runtime.output_dir, rows)
            print(_format_progress_line(row), flush=True)
    return runtime, rows


async def _run_one_pdf_round(
    paper: SmokePaper,
    round_index: int,
    runtime: SmokeRuntime,
    settings: AppSettings,
    store: SqlitePaperBundleStore,
    provider_factory: ProviderFactory,
) -> SmokeSummaryRow:
    telemetry = BuildStepsTelemetry()
    provider = RecordingTextProvider(provider_factory(settings))
    spec_service = RecordingPaperSpecService(
        cache=SqlitePaperSpecCacheView(store),
        text_provider=provider,
        document_parser_router=DocumentParserRouter([PdfParser(), DocxParser()]),
        telemetry=telemetry,
    )
    plan_service = RecordingPaperPlanService(provider, telemetry=telemetry)
    response_payload: dict[str, Any] | None = None
    response_model: UploadDocumentResponse | None = None
    unexpected_error: Exception | None = None

    handle = paper.path.open("rb")
    try:
        upload = UploadFile(file=handle, size=paper.path.stat().st_size, filename=paper.path.name)
        result = await upload_document(
            file=[upload],
            service=spec_service,
            plan_service=plan_service,
            bundle_store=store,
            reparse_store=store,
            job_store=store,
            lock_registry=PaperReparseLockRegistry(),
            settings=settings,
            primary_index=None,
        )
        if isinstance(result, JSONResponse):
            response_payload = _json_response_payload(result)
        else:
            response_model = result
            response_payload = result.model_dump(mode="json")
    except Exception as exc:  # summary must still be written for failed true runs
        unexpected_error = exc
        response_payload = {"error": type(exc).__name__, "message": str(exc)}
    finally:
        handle.close()

    paper_id = _paper_id_from_response(response_payload, response_model)
    job_record = await store.get_upload_job(paper_id) if paper_id is not None else None
    plan_record = await store.get_plan_record(paper_id) if paper_id is not None else None
    _write_actual_artifact(
        runtime.actual_dir,
        paper,
        round_index,
        response_payload or {},
        job_record=job_record,
        unexpected_error=unexpected_error,
        spec_validation_errors=telemetry.spec_validation_errors,
    )
    return build_summary_row(
        paper=paper,
        round_index=round_index,
        runtime=runtime,
        telemetry=telemetry,
        build_steps_call=provider.last_call_for_role(BUILD_STEP_ROLE_NAME),
        job_record=job_record,
        plan_record=plan_record,
        response_payload=response_payload,
        unexpected_error=unexpected_error,
    )


def build_summary_row(
    *,
    paper: SmokePaper,
    round_index: int,
    runtime: SmokeRuntime,
    telemetry: BuildStepsTelemetry,
    build_steps_call: LLMCallRecord | None,
    job_record: PaperUploadJobRecord | None,
    plan_record: PaperPlanRecord | None,
    response_payload: dict[str, Any] | None,
    unexpected_error: Exception | None,
) -> SmokeSummaryRow:
    terminal_state = _terminal_state(job_record, unexpected_error)
    plan = plan_record.plan if plan_record is not None else None
    guidance_reached = bool(plan is not None and plan.build_steps)
    guidance_status = plan.guidance_status if guidance_reached else "未触达"
    result_code = classify_build_steps_result(plan_record, telemetry)
    hybrid_conclusion, hybrid_misfire = hybrid_guardrail_conclusion(
        hybrid_candidate=paper.hybrid_candidate,
        guidance_reached=guidance_reached,
        guidance_status=guidance_status,
    )
    return SmokeSummaryRow(
        run_id=runtime.run_id,
        paper_file=paper.path.name,
        arxiv_id=paper.arxiv_id,
        round_index=round_index,
        main_terminal_state=terminal_state,
        paper_id=job_record.paper_id
        if job_record is not None
        else _payload_str(response_payload, "paper_id"),
        job_id=job_record.job_id
        if job_record is not None
        else _payload_str(response_payload, "job_id"),
        error_code=_error_code(job_record, response_payload, unexpected_error),
        failure_stage=job_record.failed_stage if job_record is not None else None,
        spec_validation_errors=list(telemetry.spec_validation_errors),
        build_steps_result_code=result_code,
        build_steps_raw_reason_code=telemetry.fallback_reason_code,
        build_steps_finish_reason=build_steps_call.finish_reason if build_steps_call else None,
        build_steps_prompt_tokens=build_steps_call.prompt_tokens if build_steps_call else None,
        build_steps_completion_tokens=(
            build_steps_call.completion_tokens if build_steps_call else None
        ),
        build_steps_total_tokens=build_steps_call.total_tokens if build_steps_call else None,
        build_steps_max_tokens=build_steps_call.max_tokens if build_steps_call else None,
        guidance_reached=guidance_reached,
        guidance_status=guidance_status,
        dto_invalid_errors=list(telemetry.dto_invalid_errors),
        hybrid_candidate=paper.hybrid_candidate,
        hybrid_guardrail_conclusion=hybrid_conclusion,
        hybrid_no_document_basis_misfire=hybrid_misfire,
    )


def classify_build_steps_result(
    plan_record: PaperPlanRecord | None,
    telemetry: BuildStepsTelemetry,
) -> BuildStepsResultCode:
    if plan_record is not None and plan_record.plan.build_steps:
        return "结构化成功"
    reason = telemetry.fallback_reason_code
    exc_type = telemetry.fallback_exception_type
    if reason == "dto_invalid":
        return "dto_invalid"
    if reason == "json_parse_failed":
        return "json_parse_failed"
    if reason == "br_no_match":
        return "br_no_match"
    if reason == "coverage_missing":
        return "coverage_missing"
    if exc_type == BuildStepsRedLineError.__name__ or reason in {
        "parameter_value_leak",
        "tuning_value_leak",
    }:
        return "redline"
    if exc_type == BuildStepsEvidenceError.__name__ or (
        reason is not None and "evidence" in reason
    ):
        return "evidence_invalid"
    return "其它"


def hybrid_guardrail_conclusion(
    *,
    hybrid_candidate: bool,
    guidance_reached: bool,
    guidance_status: str,
) -> tuple[str, bool | None]:
    if not hybrid_candidate:
        return "not_hybrid_candidate", None
    if not guidance_reached:
        return "根本没跑到护栏", None
    if guidance_status == "no_document_basis":
        return "no_document_basis误触发", True
    if guidance_status == "generated":
        return "护栏没误触发", False
    return f"够到护栏但{guidance_status}", None


def write_summary_artifacts(output_dir: Path, rows: list[SmokeSummaryRow]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "paper_pdf_smoke.summary.json"
    csv_path = output_dir / "paper_pdf_smoke.summary.csv"
    json_path.write_text(
        json.dumps([row.to_dict() for row in rows], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for row in rows:
            payload = row.to_dict()
            payload["dto_invalid_errors"] = json.dumps(
                payload["dto_invalid_errors"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            payload["spec_validation_errors"] = json.dumps(
                payload["spec_validation_errors"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            writer.writerow(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run local PDF paper-to-model smoke evaluation. "
            "This is expensive: one paper round can take about 8-9 minutes."
        )
    )
    parser.add_argument(
        "--paper-dir",
        type=Path,
        default=default_paper_dir(),
        help=f"PDF folder. Defaults to ${DEFAULT_PAPER_EVAL_DIR_ENV} or {DEFAULT_PAPER_EVAL_DIR}.",
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--pattern", default="*.pdf")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--allow-ci",
        action="store_true",
        help="Allow running the real smoke lane when CI is set.",
    )
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _guard_not_ci(args.allow_ci)
    runtime, rows = await run_smoke(
        paper_dir=args.paper_dir,
        output_dir=args.output_dir,
        rounds=args.rounds,
        pattern=args.pattern,
        limit=args.limit,
    )
    print(f"summary_json={runtime.output_dir / 'paper_pdf_smoke.summary.json'}")
    print(f"summary_csv={runtime.output_dir / 'paper_pdf_smoke.summary.csv'}")
    print(f"rows={len(rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


def _default_settings_factory(runtime: SmokeRuntime) -> AppSettings:
    return AppSettings(upload_dir=str(runtime.upload_dir), db_path=str(runtime.db_path))


def _default_provider_factory(settings: AppSettings) -> TextProvider:
    return DeepSeekTextProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def _prepare_runtime(output_dir: Path | None) -> SmokeRuntime:
    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
    root = output_dir or DEFAULT_OUTPUT_ROOT / run_id
    root = root.resolve()
    runtime_dir = root / "_runtime"
    actual_dir = root / "actual"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    actual_dir.mkdir(parents=True, exist_ok=True)
    return SmokeRuntime(
        run_id=run_id,
        output_dir=root,
        db_path=runtime_dir / "paper_pdf_smoke.sqlite",
        upload_dir=runtime_dir / "uploads",
        actual_dir=actual_dir,
    )


async def _init_temp_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as conn:
        await init_schema(conn)


def _guard_not_ci(allow_ci: bool) -> None:
    if os.environ.get("CI") and not allow_ci:
        raise SystemExit("Refusing to run real PDF smoke lane in CI; pass --allow-ci to override.")


def _pydantic_loc_type_errors(exc: ValidationError) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for item in exc.errors(include_url=False, include_context=False, include_input=False):
        loc = item.get("loc")
        error_type = item.get("type")
        errors.append(
            {
                "loc": ".".join(str(part) for part in loc) if isinstance(loc, tuple) else "root",
                "type": str(error_type or "unknown"),
            }
        )
    return errors


def _record_spec_validation_errors(
    telemetry: BuildStepsTelemetry,
    validation_errors: tuple[dict[str, object], ...],
) -> None:
    if not validation_errors:
        return
    telemetry.spec_validation_errors = _merge_spec_validation_errors(
        telemetry.spec_validation_errors,
        validation_errors,
    )


def _merge_spec_validation_errors(
    existing: list[dict[str, object]],
    incoming: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int | None, int | None], int] = {}
    for detail in [*existing, *incoming]:
        key = (
            _detail_str(detail, "loc", default="root"),
            _detail_str(detail, "type", default="unknown"),
            _detail_int(detail, "actual_length"),
            _detail_int(detail, "max_length"),
        )
        grouped[key] = grouped.get(key, 0) + _detail_count(detail)

    merged: list[dict[str, object]] = []
    for loc, error_type, actual_length, max_length in sorted(
        grouped,
        key=lambda key: (
            key[0],
            key[1],
            -1 if key[2] is None else key[2],
            -1 if key[3] is None else key[3],
        ),
    ):
        detail: dict[str, object] = {
            "loc": loc,
            "type": error_type,
            "count": grouped[(loc, error_type, actual_length, max_length)],
        }
        if actual_length is not None:
            detail["actual_length"] = actual_length
        if max_length is not None:
            detail["max_length"] = max_length
        merged.append(detail)
    return merged


def _detail_str(detail: dict[str, object], key: str, *, default: str) -> str:
    value = detail.get(key)
    return value if isinstance(value, str) else default


def _detail_int(detail: dict[str, object], key: str) -> int | None:
    value = detail.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _detail_count(detail: dict[str, object]) -> int:
    value = _detail_int(detail, "count")
    return value if value is not None and value > 0 else 1


def _terminal_state(
    job_record: PaperUploadJobRecord | None,
    unexpected_error: Exception | None,
) -> str:
    if job_record is not None:
        return job_record.job_state
    if unexpected_error is not None:
        return "failed_no_usable_spec"
    return "failed_no_usable_spec"


def _error_code(
    job_record: PaperUploadJobRecord | None,
    response_payload: dict[str, Any] | None,
    unexpected_error: Exception | None,
) -> str | None:
    if job_record is not None and job_record.last_error_code:
        return job_record.last_error_code
    payload_error = _payload_str(response_payload, "error")
    if payload_error:
        return payload_error
    if unexpected_error is not None:
        return type(unexpected_error).__name__
    return None


def _json_response_payload(response: JSONResponse) -> dict[str, Any]:
    payload = json.loads(response.body.decode("utf-8"))
    return payload if isinstance(payload, dict) else {"response": payload}


def _paper_id_from_response(
    response_payload: dict[str, Any] | None,
    response_model: UploadDocumentResponse | None,
) -> str | None:
    if response_model is not None:
        return response_model.paper_id
    return _payload_str(response_payload, "paper_id")


def _payload_str(payload: dict[str, Any] | None, key: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _write_actual_artifact(
    actual_dir: Path,
    paper: SmokePaper,
    round_index: int,
    response_payload: dict[str, Any],
    *,
    job_record: PaperUploadJobRecord | None,
    unexpected_error: Exception | None,
    spec_validation_errors: list[dict[str, object]],
) -> None:
    artifact = {
        "paper_file": paper.path.name,
        "arxiv_id": paper.arxiv_id,
        "round_index": round_index,
        "response": response_payload,
        "job_state": job_record.job_state if job_record is not None else None,
        "failed_stage": job_record.failed_stage if job_record is not None else None,
        "error_code": job_record.last_error_code if job_record is not None else None,
        "spec_validation_errors": spec_validation_errors,
        "unexpected_error_type": type(unexpected_error).__name__ if unexpected_error else None,
    }
    path = actual_dir / f"{paper.slug}__round_{round_index:02d}.actual.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_progress_line(row: SmokeSummaryRow) -> str:
    return (
        f"{row.paper_file} round={row.round_index} terminal={row.main_terminal_state} "
        f"build_steps={row.build_steps_result_code} finish={row.build_steps_finish_reason} "
        f"completion={row.build_steps_completion_tokens}/{row.build_steps_max_tokens} "
        f"total_tokens={row.build_steps_total_tokens} "
        f"guidance={row.guidance_status} hybrid={row.hybrid_guardrail_conclusion}"
    )


def _arxiv_id_from_filename(filename: str) -> str | None:
    match = ARXIV_ID_RE.search(filename)
    return match.group("id") if match else None


if __name__ == "__main__":
    raise SystemExit(main())
