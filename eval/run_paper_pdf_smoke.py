"""Local PDF smoke lane for paper-to-model true-run evaluation.

This script is intentionally local-only: it reads real PDFs from a configured
folder, writes artifacts under ``eval/out/``, and uses a temporary SQLite DB and
upload directory so it never touches ``data/mxa.db``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from collections import Counter
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol, cast

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
from core.domain.exceptions import PaperPlanGenerationError, PaperSpecGenerationError
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_conflicts import validate_parameter_conflicts_materialized
from core.domain.paper_plan import ModelBuildStep, ModelGenerationPlan, PaperPlanRecord
from core.domain.paper_spec import PaperSpec
from core.domain.paper_upload_job import PaperUploadJobRecord
from core.interfaces.document_parser import DocumentParserRouter
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper._prompt_loader import load_prompt_template
from features.paper.build_guidance_generator import (
    GUIDANCE_FULL_ATTEMPTS,
    GUIDANCE_HARD_CALL_CAP,
    GUIDANCE_ROLE_NAME,
    GUIDANCE_WALL_CLOCK_SECONDS,
    BuildGuidanceGenerator,
    _critical_steps,
)
from features.paper.build_guidance_observability import (
    SUMMARY_SCHEMA_VERSION,
    first_blocking_stage_from_owner,
    guidance_exception_code,
    guidance_failure_owner_bucket,
    validate_guidance_status_reason,
)
from features.paper.build_guidance_requirements import enumerate_guidance_requirements
from features.paper.build_steps_dependency_audit import (
    DependencyAudit,
    audit_step_dependencies_from_payload,
    prompt_token_bucket,
)
from features.paper.paper_plan_helpers import (
    BuildStepsDtoValidationError,
    BuildStepsEvidenceError,
    BuildStepsJsonParseError,
    BuildStepsRedLineError,
    BuildStepsStructuredError,
    MissingBindingModel,
    ModelBuildStepDraft,
    build_plan_evidence_source_refs,
)
from features.paper.paper_plan_service import (
    _UNSET,
    BUILD_STEP_ROLE_NAME,
    DEFAULT_PAPER_PLAN_MAX_TOKENS,
    DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
    MISSING_DETECTOR_ROLE_NAME,
    PLAN_COMPOSER_ROLE_NAME,
    PLAN_STRUCTURED_RETRY_EXTRA_ATTEMPTS,
    PaperPlanService,
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
    "draft_schema_invalid",
    "source_ref_missing",
    "source_ref_type_invalid",
    "source_ref_no_match",
    "source_ref_ambiguous",
    "final_evidence_invalid",
    "source_ref_leaked",
    "其它",
]
BUILD_STEPS_BRIDGE_REASON_CODES = frozenset(
    {
        "draft_schema_invalid",
        "source_ref_missing",
        "source_ref_type_invalid",
        "source_ref_no_match",
        "source_ref_ambiguous",
        "final_evidence_invalid",
        "source_ref_leaked",
    }
)

SUMMARY_COLUMNS = [
    "run_id",
    "summary_schema_version",
    "git_revision",
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
    "build_steps_response_model",
    "build_steps_system_fingerprint",
    "llm_model_identifiers",
    "llm_model_identifier_counts",
    "llm_system_fingerprints",
    "llm_system_fingerprint_counts",
    "llm_version_fingerprint_note",
    "run_llm_model_identifiers",
    "run_llm_model_identifier_counts",
    "run_llm_system_fingerprints",
    "run_llm_system_fingerprint_counts",
    "run_llm_version_fingerprint_note",
    "paired_build_steps_enabled",
    "paired_arm_count",
    "paired_downstream_arm",
    "paired_arm_order",
    "paired_build_steps_arms",
    "guidance_reached",
    "guidance_invoked",
    "guidance_provider_call_count",
    "guidance_status",
    "guidance_failure_reason",
    "guidance_retry_count",
    "guidance_generator_exception",
    "guidance_validator_machine_codes",
    "guidance_requirement_ref_missing_count",
    "guidance_requirement_ref_unknown_count",
    "guidance_requirement_enumerated_count",
    "guidance_attempt_record_count",
    "guidance_attempts",
    "guidance_terminal_termination_guard",
    "guidance_status_reason_valid",
    "first_blocking_stage",
    "terminal_observed_stage",
    "failure_owner_bucket",
    "plan_ready",
    "build_steps_structured",
    "guidance_delivered",
    "guidance_evidence_clean",
    "guidance_fully_actionable",
    "all_document_details_lost",
    "critical_step_count",
    "blocking_gap_count",
    "final_detail_total_count",
    "final_document_detail_count",
    "final_unverified_detail_count",
    "final_detail_basis_counts",
    "final_execution_closure_counts",
    "pending_user_choice_count",
    "pending_environment_probe_count",
    "open_requirement_count",
    "generator_downgraded_unverified_count",
    "validator_dropped_unverified_count",
    "final_surviving_unverified_count",
    "guidance_effective_config",
    "guidance_prompt_template_version",
    "guidance_prompt_template_sha256",
    "dto_invalid_errors",
    "dependency_audit_status",
    "dependency_audit_unavailable_stage",
    "total_steps",
    "total_dep_edges",
    "dep_edge_density",
    "all_empty_dependency_graph",
    "nonfirst_steps_with_empty_depends_on",
    "duplicate_step_id_count",
    "violations_by_code",
    "violation_edges",
    "violation_edges_total_count",
    "violation_edges_truncated",
    "same_number_probe_count",
    "dep_ordinal_equals_source_ref_ordinal_count",
    "same_number_probes",
    "connection_ref_not_visible_count",
    "per_step_connection_counts",
    "per_step_cross_step_connection_counts",
    "per_step_inbound_dep_counts",
    "evidence_ref_count",
    "block_candidate_count",
    "parameter_mapping_count",
    "prompt_tokens_bucket",
    "rendered_prompt_version",
    "hybrid_candidate",
    "hybrid_guardrail_conclusion",
    "hybrid_no_document_basis_misfire",
]
VERSION_FINGERPRINT_UNAVAILABLE_NOTE = "供应商未提供版本标识"
NO_LLM_CALLS_NOTE = "本轮未发生 LLM 调用"
GUIDANCE_BASIS_KEYS = (
    "document_extracted",
    "document_derived",
    "domain_default",
    "engineering_choice",
    "user_environment",
    "user_decision",
    "user_confirmation_required",
    "document_claim_unverified",
)
GUIDANCE_CLOSURE_KEYS = ("closed", "guided_choice", "guided_probe", "open")

_CURRENT_LLM_ROLE: ContextVar[str | None] = ContextVar("paper_pdf_smoke_llm_role", default=None)
_CURRENT_LLM_ARM: ContextVar[str | None] = ContextVar("paper_pdf_smoke_llm_arm", default=None)
_CURRENT_PAIRED_BUILD_STEPS: ContextVar[bool] = ContextVar(
    "paper_pdf_smoke_paired_build_steps",
    default=False,
)
_CURRENT_PAIRED_BUILD_STEPS_FULL: ContextVar[bool] = ContextVar(
    "paper_pdf_smoke_paired_build_steps_full",
    default=False,
)


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
    arm_label: str | None
    request_model: str | None
    json_mode: bool
    timeout: float
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    max_tokens: int | None
    response_format: str | None
    temperature: float | None
    top_p: float | None
    seed: int | None
    response_model: str | None
    system_fingerprint: str | None
    exception_code: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class BuildStepsTelemetry:
    spec_validation_errors: list[dict[str, object]] = field(default_factory=list)
    fallback_reason_code: str | None = None
    fallback_exception_code: str | None = None
    dto_invalid_errors: list[dict[str, str]] = field(default_factory=list)
    dependency_audit: DependencyAudit = field(
        default_factory=lambda: DependencyAudit.unavailable("draft_parse")
    )
    paired_build_steps_enabled: bool = False
    paired_downstream_arm: str | None = None
    paired_arm_order: list[str] = field(default_factory=list)
    paired_build_steps_arms: list[dict[str, Any]] = field(default_factory=list)
    guidance_failure_reason: str | None = None
    guidance_validator_machine_codes: list[str] = field(default_factory=list)
    guidance_retry_count: int | None = None
    guidance_generator_exception: str | None = None
    guidance_attempts: list[dict[str, object]] = field(default_factory=list)
    guidance_terminal_termination_guard: str | None = None
    generator_downgraded_unverified_count: int | None = None
    validator_dropped_unverified_count: int | None = None
    all_document_details_lost: bool | None = None
    guidance_artifact_snapshots: list[GuidanceArtifactSnapshot] = field(default_factory=list)
    guidance_drafts: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GuidanceArtifactSnapshot:
    """Eval-only snapshot for writing readable build guidance artifacts."""

    arm_label: str
    plan: ModelGenerationPlan | None
    guidance_status: str
    guidance_delivered: bool
    guidance_evidence_clean: bool
    guidance_fully_actionable: bool
    generator_downgraded_unverified_count: int | None
    validator_dropped_unverified_count: int | None
    final_surviving_unverified_count: int | None
    blocking_gap_count: int | None


@dataclass(frozen=True)
class SmokeSummaryRow:
    run_id: str
    summary_schema_version: str
    git_revision: str
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
    build_steps_response_model: str | None
    build_steps_system_fingerprint: str | None
    llm_model_identifiers: list[str]
    llm_model_identifier_counts: dict[str, int]
    llm_system_fingerprints: list[str]
    llm_system_fingerprint_counts: dict[str, int]
    llm_version_fingerprint_note: str | None
    run_llm_model_identifiers: list[str]
    run_llm_model_identifier_counts: dict[str, int]
    run_llm_system_fingerprints: list[str]
    run_llm_system_fingerprint_counts: dict[str, int]
    run_llm_version_fingerprint_note: str | None
    paired_build_steps_enabled: bool
    paired_arm_count: int
    paired_downstream_arm: str | None
    paired_arm_order: list[str]
    paired_build_steps_arms: list[dict[str, Any]]
    guidance_reached: bool
    guidance_invoked: bool
    guidance_provider_call_count: int
    guidance_status: str
    guidance_failure_reason: str | None
    guidance_retry_count: int | None
    guidance_generator_exception: str | None
    guidance_validator_machine_codes: list[str]
    guidance_requirement_ref_missing_count: int | None
    guidance_requirement_ref_unknown_count: int | None
    guidance_requirement_enumerated_count: int | None
    guidance_attempt_record_count: int
    guidance_attempts: list[dict[str, object]]
    guidance_terminal_termination_guard: str | None
    guidance_status_reason_valid: bool
    first_blocking_stage: str | None
    terminal_observed_stage: str | None
    failure_owner_bucket: str | None
    plan_ready: bool
    build_steps_structured: bool
    guidance_delivered: bool
    guidance_evidence_clean: bool
    guidance_fully_actionable: bool
    all_document_details_lost: bool | None
    critical_step_count: int | None
    blocking_gap_count: int | None
    final_detail_total_count: int | None
    final_document_detail_count: int | None
    final_unverified_detail_count: int | None
    final_detail_basis_counts: dict[str, int] | None
    final_execution_closure_counts: dict[str, int] | None
    pending_user_choice_count: int | None
    pending_environment_probe_count: int | None
    open_requirement_count: int | None
    generator_downgraded_unverified_count: int | None
    validator_dropped_unverified_count: int | None
    final_surviving_unverified_count: int | None
    guidance_effective_config: dict[str, object]
    guidance_prompt_template_version: str
    guidance_prompt_template_sha256: str
    dto_invalid_errors: list[dict[str, str]]
    dependency_audit_status: str
    dependency_audit_unavailable_stage: str | None
    total_steps: int | None
    total_dep_edges: int | None
    dep_edge_density: float | None
    all_empty_dependency_graph: bool | None
    nonfirst_steps_with_empty_depends_on: int | None
    duplicate_step_id_count: int | None
    violations_by_code: dict[str, int]
    violation_edges: list[dict[str, Any]]
    violation_edges_total_count: int
    violation_edges_truncated: bool
    same_number_probe_count: int
    dep_ordinal_equals_source_ref_ordinal_count: int
    same_number_probes: list[dict[str, Any]]
    connection_ref_not_visible_count: int | None
    per_step_connection_counts: list[int]
    per_step_cross_step_connection_counts: list[int]
    per_step_inbound_dep_counts: list[int]
    evidence_ref_count: int | None
    block_candidate_count: int | None
    parameter_mapping_count: int | None
    prompt_tokens_bucket: str | None
    rendered_prompt_version: str | None
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


class GuidanceBatchInvalidError(ValueError):
    """Raised when guidance observability gates invalidate an eval batch."""


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
        request_model = self._delegate.capability().model_name
        try:
            response = self._delegate.chat(
                messages,
                json_mode=json_mode,
                timeout=timeout,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self.calls.append(
                LLMCallRecord(
                    role=_CURRENT_LLM_ROLE.get(),
                    arm_label=_CURRENT_LLM_ARM.get(),
                    request_model=request_model,
                    json_mode=json_mode,
                    timeout=timeout,
                    finish_reason=None,
                    prompt_tokens=0,
                    completion_tokens=0,
                    max_tokens=max_tokens,
                    response_format="json_object" if json_mode else None,
                    temperature=None,
                    top_p=None,
                    seed=None,
                    response_model=None,
                    system_fingerprint=None,
                    exception_code=guidance_exception_code(exc),
                )
            )
            raise
        self.calls.append(
            LLMCallRecord(
                role=_CURRENT_LLM_ROLE.get(),
                arm_label=_CURRENT_LLM_ARM.get(),
                request_model=request_model,
                json_mode=json_mode,
                timeout=timeout,
                finish_reason=response.finish_reason,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                max_tokens=max_tokens,
                response_format="json_object" if json_mode else None,
                temperature=None,
                top_p=None,
                seed=None,
                response_model=response.model,
                system_fingerprint=response.system_fingerprint,
            )
        )
        return response

    def capability(self) -> ModelCapability:
        return self._delegate.capability()

    def last_call_for_role(
        self,
        role: str,
        *,
        arm_label: str | None = None,
    ) -> LLMCallRecord | None:
        for call in reversed(self.calls):
            if call.role == role and (arm_label is None or call.arm_label == arm_label):
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


class RecordingBuildGuidanceGenerator(BuildGuidanceGenerator):
    """Eval-only guidance generator that records terminal reason codes."""

    def __init__(
        self,
        text_provider: TextProvider,
        *,
        telemetry: BuildStepsTelemetry,
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,
    ) -> None:
        super().__init__(text_provider, timeout=timeout, max_tokens=max_tokens)
        self._smoke_telemetry = telemetry

    async def generate(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        self._smoke_telemetry.guidance_failure_reason = None
        self._smoke_telemetry.guidance_validator_machine_codes = []
        self._smoke_telemetry.guidance_retry_count = None
        self._smoke_telemetry.guidance_generator_exception = None
        self._smoke_telemetry.guidance_attempts = []
        self._smoke_telemetry.guidance_terminal_termination_guard = None
        self._smoke_telemetry.generator_downgraded_unverified_count = None
        self._smoke_telemetry.validator_dropped_unverified_count = None
        self._smoke_telemetry.all_document_details_lost = None
        self._smoke_telemetry.guidance_drafts = []
        result = await super().generate(spec, plan)
        self._sync_guidance_telemetry()
        if (
            result.guidance_status == "generation_failed"
            and self._smoke_telemetry.guidance_failure_reason is None
        ):
            self._smoke_telemetry.guidance_failure_reason = (
                "guidance_validator_generated_output_changed"
            )
            self._smoke_telemetry.guidance_validator_machine_codes = [
                "guidance_validator_generated_output_changed"
            ]
        return result

    def _sync_guidance_telemetry(self) -> None:
        telemetry = self.last_telemetry
        self._smoke_telemetry.guidance_attempts = telemetry.attempt_dicts()
        self._smoke_telemetry.guidance_terminal_termination_guard = (
            telemetry.terminal_termination_guard
        )
        self._smoke_telemetry.guidance_generator_exception = telemetry.generator_exception
        if telemetry.terminal_reason is not None:
            self._smoke_telemetry.guidance_failure_reason = telemetry.terminal_reason
        if not telemetry.attempts:
            return
        self._smoke_telemetry.guidance_retry_count = max(0, len(telemetry.attempts) - 1)
        last_attempt = telemetry.attempts[-1]
        self._smoke_telemetry.guidance_validator_machine_codes = list(
            last_attempt.validator_machine_codes
        )
        if last_attempt.detail_downgraded_count is not None:
            self._smoke_telemetry.generator_downgraded_unverified_count = (
                last_attempt.detail_downgraded_count
            )
        if last_attempt.validator_dropped_unverified_count is not None:
            self._smoke_telemetry.validator_dropped_unverified_count = (
                last_attempt.validator_dropped_unverified_count
            )
        self._smoke_telemetry.all_document_details_lost = (
            "guidance_validator_all_document_details_lost" in last_attempt.validator_machine_codes
        )

    async def _call_llm_json(
        self,
        messages: list[LLMMessage],
        retry_context: Any,
    ) -> Any:
        token = _CURRENT_LLM_ROLE.set(GUIDANCE_ROLE_NAME)
        try:
            result = await super()._call_llm_json(messages, retry_context)
            self._smoke_telemetry.guidance_drafts.append(
                _guidance_draft_capture_payload(
                    result.payload,
                    attempt_index=len(self._smoke_telemetry.guidance_drafts) + 1,
                    arm_label=_CURRENT_LLM_ARM.get(),
                )
            )
            return result
        finally:
            _CURRENT_LLM_ROLE.reset(token)

    def _log_terminal(
        self,
        status: Literal["generation_failed", "no_document_basis"],
        reason: str,
        *,
        retry_count: int,
    ) -> None:
        self._smoke_telemetry.guidance_failure_reason = reason
        self._smoke_telemetry.guidance_validator_machine_codes = []
        self._smoke_telemetry.guidance_retry_count = retry_count
        super()._log_terminal(status, reason, retry_count=retry_count)


class RecordingPaperPlanService(PaperPlanService):
    """Eval-only subclass that records build-step fallback details."""

    def __init__(
        self,
        text_provider: TextProvider,
        *,
        telemetry: BuildStepsTelemetry,
        paired_build_steps: bool = False,
        paired_build_steps_full: bool = False,
        pair_order_start: str = "off",
        timeout: float = DEFAULT_PAPER_PLAN_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_PAPER_PLAN_MAX_TOKENS,
    ) -> None:
        super().__init__(
            text_provider=text_provider,
            build_guidance_generator=RecordingBuildGuidanceGenerator(
                text_provider,
                telemetry=telemetry,
                timeout=timeout,
                max_tokens=max_tokens,
            ),
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self._smoke_telemetry = telemetry
        self._paired_build_steps = paired_build_steps
        self._paired_build_steps_full = paired_build_steps_full
        self._pair_order_start = pair_order_start

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

    async def _generate_build_guidance(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        result = await super()._generate_build_guidance(spec, plan)
        if (
            result.guidance_status == "generation_failed"
            and self._smoke_telemetry.guidance_failure_reason is None
        ):
            self._smoke_telemetry.guidance_failure_reason = "guidance_generator_exception"
            self._smoke_telemetry.guidance_generator_exception = "unexpected_internal_error"
            self._smoke_telemetry.guidance_validator_machine_codes = [
                "guidance_generator_exception"
            ]
        return result

    async def _generate_with_retries(
        self,
        spec: PaperSpec,
        paper_id: str,
    ) -> tuple[ModelGenerationPlan, list[MissingParameterPrompt], list[MissingBindingModel]]:
        if not self._paired_build_steps_full:
            return await super()._generate_with_retries(spec, paper_id)

        plan_id = f"PLAN-{paper_id}"
        paper_spec_id = paper_id
        try:
            validate_parameter_conflicts_materialized(spec)
        except ValueError:
            raise PaperPlanGenerationError(
                "parameter_conflicts_mismatch",
                reason_code="parameter_conflicts_mismatch",
            ) from None
        self._preflight_spec_equation_namespace(spec)

        # Full paired mode intentionally keeps the same upstream plan/missing/mscript
        # material for both build-step arms, then runs validation and guidance per arm.
        remaining_structured_retries = PLAN_STRUCTURED_RETRY_EXTRA_ATTEMPTS
        retried_leaves: set[str] = set()
        plan_composer_output: ModelGenerationPlan | None = None
        mscript: str | None = None
        mscript_ready = False

        while plan_composer_output is None:
            if mscript_ready:
                plan_result = await self._capture_plan_leaf(
                    self._llm_plan_compose(spec, plan_id, paper_spec_id),
                    PLAN_COMPOSER_ROLE_NAME,
                )
                mscript_result: str | BaseException | None = mscript
            else:
                plan_result, mscript_result = await asyncio.gather(
                    self._capture_plan_leaf(
                        self._llm_plan_compose(spec, plan_id, paper_spec_id),
                        PLAN_COMPOSER_ROLE_NAME,
                    ),
                    self._llm_mscript_draft(spec),
                    return_exceptions=True,
                )
                if not isinstance(mscript_result, BaseException):
                    mscript = mscript_result
                    mscript_ready = True

            if isinstance(mscript_result, BaseException):
                raise mscript_result
            if isinstance(plan_result, BaseException):
                if self._should_retry_plan_leaf(
                    plan_result,
                    PLAN_COMPOSER_ROLE_NAME,
                    remaining_structured_retries,
                ):
                    remaining_structured_retries -= 1
                    retried_leaves.add(PLAN_COMPOSER_ROLE_NAME)
                    self._record_plan_retry(
                        plan_result,
                        PLAN_COMPOSER_ROLE_NAME,
                        remaining_structured_retries,
                    )
                    continue
                self._record_plan_exhausted(plan_result, PLAN_COMPOSER_ROLE_NAME)
                raise plan_result
            plan_composer_output = cast(ModelGenerationPlan, plan_result)
            self._record_plan_rescue_if_needed(PLAN_COMPOSER_ROLE_NAME, retried_leaves)

        sentinel_mappings = self._sentinel_mappings(plan_composer_output.parameter_mapping)
        build_steps_result: object = _UNSET
        missing_prompts: list[MissingParameterPrompt] | None = None
        while missing_prompts is None:
            if build_steps_result is _UNSET:
                missing_result, build_steps_result = await asyncio.gather(
                    self._capture_plan_leaf(
                        self._llm_missing_detect(spec, paper_id, sentinel_mappings),
                        MISSING_DETECTOR_ROLE_NAME,
                    ),
                    self._paired_build_step_drafts(
                        plan_composer_output.block_recommendations,
                        plan_composer_output.parameter_mapping,
                        spec,
                    ),
                    return_exceptions=True,
                )
            else:
                missing_result = await self._capture_plan_leaf(
                    self._llm_missing_detect(spec, paper_id, sentinel_mappings),
                    MISSING_DETECTOR_ROLE_NAME,
                )
            if isinstance(missing_result, BaseException):
                if self._should_retry_plan_leaf(
                    missing_result,
                    MISSING_DETECTOR_ROLE_NAME,
                    remaining_structured_retries,
                ):
                    remaining_structured_retries -= 1
                    retried_leaves.add(MISSING_DETECTOR_ROLE_NAME)
                    self._record_plan_retry(
                        missing_result,
                        MISSING_DETECTOR_ROLE_NAME,
                        remaining_structured_retries,
                    )
                    continue
                self._record_plan_exhausted(missing_result, MISSING_DETECTOR_ROLE_NAME)
                raise missing_result
            missing_prompts = cast(list[MissingParameterPrompt], missing_result)
            self._record_plan_rescue_if_needed(MISSING_DETECTOR_ROLE_NAME, retried_leaves)

        if isinstance(build_steps_result, BaseException):
            raise build_steps_result
        arm_results = cast(
            dict[str, list[ModelBuildStepDraft] | BaseException],
            build_steps_result,
        )
        arm_plans: dict[str, tuple[ModelGenerationPlan, list[MissingBindingModel]]] = {}
        for arm_label in self._smoke_telemetry.paired_arm_order:
            arm_plans[arm_label] = await self._assemble_and_guide_arm(
                arm_label=arm_label,
                arm_result=arm_results.get(arm_label),
                spec=spec,
                paper_id=paper_id,
                plan_composer_output=plan_composer_output,
                mscript=mscript,
                missing_prompts=missing_prompts,
            )

        on_plan = arm_plans.get("on")
        if on_plan is None:
            raise AssertionError("paired full build-step on arm did not run")
        return on_plan[0], missing_prompts, on_plan[1]

    async def _assemble_and_guide_arm(
        self,
        *,
        arm_label: str,
        arm_result: list[ModelBuildStepDraft] | BaseException | None,
        spec: PaperSpec,
        paper_id: str,
        plan_composer_output: ModelGenerationPlan,
        mscript: str | None,
        missing_prompts: list[MissingParameterPrompt],
    ) -> tuple[ModelGenerationPlan, list[MissingBindingModel]]:
        token = _CURRENT_LLM_ARM.set(arm_label)
        is_downstream_arm = arm_label == "on"
        payload = self._paired_arm_payload(arm_label)
        build_steps: list[ModelBuildStep] | None
        raw_reason_code: str | None = None
        exception_code: str | None = None
        try:
            if isinstance(arm_result, BuildStepsStructuredError):
                raise arm_result
            if isinstance(arm_result, BaseException):
                raise arm_result
            if arm_result is None:
                raise AssertionError(f"paired build-step {arm_label} arm did not run")
            build_steps = self._plan_assembler.validate_and_derive_build_steps(
                arm_result,
                plan_composer_output.parameter_mapping,
                plan_composer_output.block_recommendations,
            )
            self._validate_build_step_evidence(build_steps, spec)
            subsystem_steps = [step.display_text for step in build_steps]
            full_result_code: BuildStepsResultCode = "结构化成功"
        except BuildStepsStructuredError as exc:
            raw_reason_code = exc.reason_code
            exception_code = _build_steps_exception_code(exc)
            full_result_code = _classify_build_steps_failure(
                raw_reason_code,
                exception_code,
            )
            if is_downstream_arm:
                self._log_build_steps_fallback(exc)
            build_steps = None
            subsystem_steps = await self._llm_subsystem_plan(
                plan_composer_output.block_recommendations,
                spec.evidence,
            )
        finally:
            _CURRENT_LLM_ARM.reset(token)

        token = _CURRENT_LLM_ARM.set(arm_label)
        try:
            assembled_plan, missing_bindings = self._plan_assembler.merge(
                plan_composer_output=plan_composer_output,
                subsystem_steps=subsystem_steps,
                mscript=mscript,
                missing_prompts=missing_prompts,
                paper_id=paper_id,
                build_steps=build_steps,
            )
            guided_plan = await self._generate_build_guidance(spec, assembled_plan)
        finally:
            _CURRENT_LLM_ARM.reset(token)

        self._smoke_telemetry.guidance_artifact_snapshots.append(
            _guidance_snapshot_for_plan(
                arm_label,
                guided_plan,
                telemetry=self._smoke_telemetry,
            )
        )
        payload.update(
            {
                "full_pipeline_used": True,
                "full_build_steps_success": build_steps is not None,
                "full_build_steps_result_code": full_result_code,
                "full_build_steps_raw_reason_code": raw_reason_code,
                "full_build_steps_exception_code": exception_code,
                "full_guidance_reached": bool(guided_plan.build_steps),
                "full_guidance_status": guided_plan.guidance_status,
                "full_guidance_failure_reason": self._smoke_telemetry.guidance_failure_reason,
                "full_guidance_validator_machine_codes": list(
                    self._smoke_telemetry.guidance_validator_machine_codes
                ),
            }
        )
        return guided_plan, missing_bindings

    async def _llm_build_steps(
        self,
        block_recommendations,
        parameter_mapping,
        spec,
    ) -> list[ModelBuildStepDraft]:
        if self._paired_build_steps:
            return await self._paired_llm_build_steps(
                block_recommendations, parameter_mapping, spec
            )
        data = await self._call_llm_json(
            self._build_step_messages(
                block_recommendations,
                parameter_mapping,
                spec,
                dependency_salience_enabled=True,
            ),
            BUILD_STEP_ROLE_NAME,
        )
        source_refs = build_plan_evidence_source_refs(spec)
        drafts = self._parse_build_steps_output(
            data,
            document_source_refs=source_refs,
            user_source_refs=[],
            role_name=BUILD_STEP_ROLE_NAME,
            evidence_ref_count=len(source_refs),
            block_candidate_count=len(block_recommendations),
            parameter_mapping_count=len(parameter_mapping),
            rendered_prompt_version=load_prompt_template("paper_plan_build_steps.yaml").version,
        )
        self._smoke_telemetry.dependency_audit = self.build_steps_dependency_audit()
        return drafts

    async def _paired_llm_build_steps(
        self,
        block_recommendations,
        parameter_mapping,
        spec,
    ) -> list[ModelBuildStepDraft]:
        arm_results = await self._paired_build_step_drafts(
            block_recommendations,
            parameter_mapping,
            spec,
        )
        on_result = arm_results.get("on")
        if isinstance(on_result, BaseException):
            raise on_result
        if on_result is None:
            raise AssertionError("paired build-step on arm did not run")
        return on_result

    async def _paired_build_step_drafts(
        self,
        block_recommendations,
        parameter_mapping,
        spec,
    ) -> dict[str, list[ModelBuildStepDraft] | BaseException]:
        order = ["on", "off"] if self._pair_order_start == "on" else ["off", "on"]
        self._smoke_telemetry.paired_build_steps_enabled = True
        self._smoke_telemetry.paired_downstream_arm = "on"
        self._smoke_telemetry.paired_arm_order = list(order)
        arm_results: dict[str, list[ModelBuildStepDraft] | BaseException] = {}
        arm_dto_errors: dict[str, list[dict[str, str]]] = {}
        arm_audits: dict[str, DependencyAudit] = {}

        for call_order, arm_label in enumerate(order, start=1):
            self._clear_build_steps_dependency_audit()
            self._smoke_telemetry.dto_invalid_errors = []
            result_code = "json_parse_failed"
            arm_audit = DependencyAudit.unavailable("draft_parse")
            token = _CURRENT_LLM_ARM.set(arm_label)
            try:
                data = await self._call_llm_json(
                    self._build_step_messages(
                        block_recommendations,
                        parameter_mapping,
                        spec,
                        dependency_salience_enabled=arm_label == "on",
                    ),
                    BUILD_STEP_ROLE_NAME,
                )
                source_refs = build_plan_evidence_source_refs(spec)
                arm_audit = audit_step_dependencies_from_payload(data).with_context(
                    evidence_ref_count=len(source_refs),
                    block_candidate_count=len(block_recommendations),
                    parameter_mapping_count=len(parameter_mapping),
                    rendered_prompt_version="v0.3" if arm_label == "on" else "v0.2",
                )
                arm_results[arm_label] = self._parse_build_steps_output(
                    data,
                    document_source_refs=source_refs,
                    user_source_refs=[],
                    role_name=BUILD_STEP_ROLE_NAME,
                    evidence_ref_count=len(source_refs),
                    block_candidate_count=len(block_recommendations),
                    parameter_mapping_count=len(parameter_mapping),
                    rendered_prompt_version=("v0.3" if arm_label == "on" else "v0.2"),
                )
                result_code = "parsed"
            except BaseException as exc:
                arm_results[arm_label] = exc
                result_code = _paired_arm_result_code(exc)
            finally:
                _CURRENT_LLM_ARM.reset(token)

            arm_dto_errors[arm_label] = list(self._smoke_telemetry.dto_invalid_errors)
            recorded_audit = self.build_steps_dependency_audit()
            arm_audits[arm_label] = (
                recorded_audit
                if recorded_audit.dependency_audit_status != "unavailable"
                else arm_audit
            )
            self._smoke_telemetry.paired_build_steps_arms.append(
                {
                    "arm_label": arm_label,
                    "call_order": call_order,
                    "downstream_used": arm_label == "on",
                    "dependency_salience_enabled": arm_label == "on",
                    "result_code": result_code,
                    "dto_invalid_errors": arm_dto_errors[arm_label],
                    "dependency_audit": arm_audits[arm_label].to_dict(),
                }
            )

        self._smoke_telemetry.dto_invalid_errors = arm_dto_errors.get("on", [])
        self._smoke_telemetry.dependency_audit = arm_audits.get(
            "on",
            DependencyAudit.unavailable("draft_parse"),
        )
        self._last_build_steps_dependency_audit = self._smoke_telemetry.dependency_audit
        return arm_results

    def _paired_arm_payload(self, arm_label: str) -> dict[str, Any]:
        for arm in self._smoke_telemetry.paired_build_steps_arms:
            if arm.get("arm_label") == arm_label:
                return arm
        raise AssertionError(f"paired build-step {arm_label} arm telemetry missing")

    def _record_build_steps_dto_validation_errors(
        self,
        exc: ValidationError,
        *,
        role_name: str,
    ) -> None:
        _ = role_name
        self._smoke_telemetry.dto_invalid_errors = _pydantic_loc_type_errors(exc)

    def _build_step_messages(
        self,
        block_recommendations,
        parameter_mapping,
        spec,
        *,
        dependency_salience_enabled: bool,
    ):
        from features.paper._prompt_builder import (
            build_messages_for_build_steps,
            build_messages_for_build_steps_legacy_dependency_eval,
        )

        builder = (
            build_messages_for_build_steps
            if dependency_salience_enabled
            else build_messages_for_build_steps_legacy_dependency_eval
        )

        return builder(
            block_recommendations,
            parameter_mapping,
            spec.evidence,
            build_plan_evidence_source_refs(spec),
        )

    def _log_build_steps_fallback(self, exc: BuildStepsStructuredError) -> None:
        self._smoke_telemetry.fallback_reason_code = exc.reason_code
        self._smoke_telemetry.fallback_exception_code = _build_steps_exception_code(exc)
        self._smoke_telemetry.dependency_audit = self.build_steps_dependency_audit()
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
    paired_build_steps: bool = False,
    paired_build_steps_full: bool = False,
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
    paired_enabled = paired_build_steps or paired_build_steps_full
    pair_token = _CURRENT_PAIRED_BUILD_STEPS.set(paired_enabled)
    full_pair_token = _CURRENT_PAIRED_BUILD_STEPS_FULL.set(paired_build_steps_full)
    try:
        for paper in papers:
            for round_index in range(1, rounds + 1):
                row = await runner(paper, round_index, runtime, settings, store, provider_builder)
                rows.append(row)
                write_summary_artifacts(runtime.output_dir, rows)
                print(_format_progress_line(row), flush=True)
    finally:
        _CURRENT_PAIRED_BUILD_STEPS_FULL.reset(full_pair_token)
        _CURRENT_PAIRED_BUILD_STEPS.reset(pair_token)
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
    paired_build_steps = _CURRENT_PAIRED_BUILD_STEPS.get()
    paired_build_steps_full = _CURRENT_PAIRED_BUILD_STEPS_FULL.get()
    pair_order_start = _paired_build_steps_first_arm(round_index)
    plan_service = RecordingPaperPlanService(
        provider,
        telemetry=telemetry,
        paired_build_steps=paired_build_steps,
        paired_build_steps_full=paired_build_steps_full,
        pair_order_start=pair_order_start,
    )
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
        response_payload = {"error_code": guidance_exception_code(exc)}
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
    row = build_summary_row(
        paper=paper,
        round_index=round_index,
        runtime=runtime,
        telemetry=telemetry,
        build_steps_call=provider.last_call_for_role(
            BUILD_STEP_ROLE_NAME,
            arm_label="on" if paired_build_steps else None,
        ),
        llm_calls=provider.calls,
        job_record=job_record,
        plan_record=plan_record,
        response_payload=response_payload,
        unexpected_error=unexpected_error,
    )
    snapshots = telemetry.guidance_artifact_snapshots or [
        _guidance_snapshot_for_plan(
            "on" if paired_build_steps else "main",
            plan_record.plan if plan_record is not None else None,
            row=row,
        )
    ]
    write_guidance_artifacts(
        runtime.output_dir,
        paper=paper,
        round_index=round_index,
        row=row,
        snapshots=snapshots,
    )
    write_guidance_draft_artifacts(
        runtime.output_dir,
        paper=paper,
        round_index=round_index,
        drafts=telemetry.guidance_drafts,
    )
    return row


def build_summary_row(
    *,
    paper: SmokePaper,
    round_index: int,
    runtime: SmokeRuntime,
    telemetry: BuildStepsTelemetry,
    build_steps_call: LLMCallRecord | None,
    llm_calls: list[LLMCallRecord],
    job_record: PaperUploadJobRecord | None,
    plan_record: PaperPlanRecord | None,
    response_payload: dict[str, Any] | None,
    unexpected_error: Exception | None,
) -> SmokeSummaryRow:
    terminal_state = _terminal_state(job_record, unexpected_error)
    plan = plan_record.plan if plan_record is not None else None
    plan_ready = plan is not None
    build_steps_structured = bool(plan is not None and plan.build_steps)
    guidance_reached = build_steps_structured
    guidance_status = plan.guidance_status if plan is not None else "not_generated"
    guidance_calls = [call for call in llm_calls if call.role == GUIDANCE_ROLE_NAME]
    guidance_invoked = bool(guidance_calls)
    guidance_call = guidance_calls[0] if guidance_calls else None
    guidance_failure_reason = (
        None if guidance_status == "generated" else telemetry.guidance_failure_reason
    )
    status_reason_valid = _guidance_status_reason_valid(
        guidance_status,
        guidance_failure_reason,
    )
    output_counts = _guidance_output_counts(plan)
    final_unverified_detail_count = output_counts["final_unverified_detail_count"]
    guidance_delivered = guidance_status == "generated" and output_counts["has_guidance"] is True
    guidance_evidence_clean = guidance_delivered and final_unverified_detail_count == 0
    guidance_fully_actionable = guidance_evidence_clean and output_counts["blocking_gap_count"] == 0
    failed_for_owner = not guidance_delivered
    owner_bucket = guidance_failure_owner_bucket(
        failed=failed_for_owner,
        plan_ready=plan_ready,
        build_steps_structured=build_steps_structured,
        guidance_invoked=guidance_invoked,
        guidance_failure_reason=guidance_failure_reason,
    )
    first_blocking_stage = first_blocking_stage_from_owner(owner_bucket)
    terminal_observed_stage = _terminal_observed_stage(
        plan_ready=plan_ready,
        build_steps_structured=build_steps_structured,
        guidance_failure_reason=guidance_failure_reason,
    )
    result_code = classify_build_steps_result(plan_record, telemetry)
    hybrid_conclusion, hybrid_misfire = hybrid_guardrail_conclusion(
        hybrid_candidate=paper.hybrid_candidate,
        guidance_reached=guidance_reached,
        guidance_status=guidance_status,
    )
    dependency_audit = _dependency_audit_for_summary(telemetry, build_steps_call)
    llm_model_summary = _llm_model_summary(llm_calls, no_calls_note=NO_LLM_CALLS_NOTE)
    paired_build_steps_arms = _paired_build_steps_arms_for_summary(telemetry, llm_calls)
    return SmokeSummaryRow(
        run_id=runtime.run_id,
        summary_schema_version=SUMMARY_SCHEMA_VERSION,
        git_revision=_git_revision(),
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
        build_steps_response_model=(
            _model_fingerprint(build_steps_call.response_model) if build_steps_call else None
        ),
        build_steps_system_fingerprint=(
            build_steps_call.system_fingerprint if build_steps_call else None
        ),
        llm_model_identifiers=llm_model_summary["model_identifiers"],
        llm_model_identifier_counts=llm_model_summary["model_identifier_counts"],
        llm_system_fingerprints=llm_model_summary["system_fingerprints"],
        llm_system_fingerprint_counts=llm_model_summary["system_fingerprint_counts"],
        llm_version_fingerprint_note=llm_model_summary["version_fingerprint_note"],
        run_llm_model_identifiers=llm_model_summary["model_identifiers"],
        run_llm_model_identifier_counts=llm_model_summary["model_identifier_counts"],
        run_llm_system_fingerprints=llm_model_summary["system_fingerprints"],
        run_llm_system_fingerprint_counts=llm_model_summary["system_fingerprint_counts"],
        run_llm_version_fingerprint_note=llm_model_summary["version_fingerprint_note"],
        paired_build_steps_enabled=telemetry.paired_build_steps_enabled,
        paired_arm_count=len(paired_build_steps_arms),
        paired_downstream_arm=telemetry.paired_downstream_arm,
        paired_arm_order=list(telemetry.paired_arm_order),
        paired_build_steps_arms=paired_build_steps_arms,
        guidance_reached=guidance_reached,
        guidance_invoked=guidance_invoked,
        guidance_provider_call_count=len(guidance_calls),
        guidance_status=guidance_status,
        guidance_failure_reason=guidance_failure_reason,
        guidance_retry_count=telemetry.guidance_retry_count,
        guidance_generator_exception=telemetry.guidance_generator_exception,
        guidance_validator_machine_codes=list(telemetry.guidance_validator_machine_codes),
        guidance_requirement_ref_missing_count=_guidance_resolver_code_count(
            telemetry.guidance_attempts,
            "requirement_ref_missing",
            guidance_invoked=guidance_invoked,
        ),
        guidance_requirement_ref_unknown_count=_guidance_resolver_code_count(
            telemetry.guidance_attempts,
            "requirement_ref_unknown",
            guidance_invoked=guidance_invoked,
        ),
        guidance_requirement_enumerated_count=output_counts[
            "guidance_requirement_enumerated_count"
        ],
        guidance_attempt_record_count=len(telemetry.guidance_attempts),
        guidance_attempts=list(telemetry.guidance_attempts),
        guidance_terminal_termination_guard=telemetry.guidance_terminal_termination_guard,
        guidance_status_reason_valid=status_reason_valid,
        first_blocking_stage=first_blocking_stage,
        terminal_observed_stage=terminal_observed_stage,
        failure_owner_bucket=owner_bucket,
        plan_ready=plan_ready,
        build_steps_structured=build_steps_structured,
        guidance_delivered=guidance_delivered,
        guidance_evidence_clean=guidance_evidence_clean,
        guidance_fully_actionable=guidance_fully_actionable,
        all_document_details_lost=(
            telemetry.all_document_details_lost
            if telemetry.all_document_details_lost is not None
            else False
            if guidance_delivered
            else None
        ),
        critical_step_count=output_counts["critical_step_count"],
        blocking_gap_count=output_counts["blocking_gap_count"],
        final_detail_total_count=output_counts["final_detail_total_count"],
        final_document_detail_count=output_counts["final_document_detail_count"],
        final_unverified_detail_count=final_unverified_detail_count,
        final_detail_basis_counts=output_counts["final_detail_basis_counts"],
        final_execution_closure_counts=output_counts["final_execution_closure_counts"],
        pending_user_choice_count=output_counts["pending_user_choice_count"],
        pending_environment_probe_count=output_counts["pending_environment_probe_count"],
        open_requirement_count=output_counts["open_requirement_count"],
        generator_downgraded_unverified_count=(
            telemetry.generator_downgraded_unverified_count if guidance_delivered else None
        ),
        validator_dropped_unverified_count=(
            telemetry.validator_dropped_unverified_count if guidance_delivered else None
        ),
        final_surviving_unverified_count=final_unverified_detail_count,
        guidance_effective_config=_guidance_effective_config(guidance_call),
        guidance_prompt_template_version=_guidance_prompt_template_version(),
        guidance_prompt_template_sha256=_guidance_prompt_template_sha256(),
        dto_invalid_errors=list(telemetry.dto_invalid_errors),
        dependency_audit_status=dependency_audit.dependency_audit_status,
        dependency_audit_unavailable_stage=dependency_audit.unavailable_stage,
        total_steps=dependency_audit.total_steps,
        total_dep_edges=dependency_audit.total_dep_edges,
        dep_edge_density=dependency_audit.dep_edge_density,
        all_empty_dependency_graph=dependency_audit.all_empty_dependency_graph,
        nonfirst_steps_with_empty_depends_on=(
            dependency_audit.nonfirst_steps_with_empty_depends_on
        ),
        duplicate_step_id_count=dependency_audit.duplicate_step_id_count,
        violations_by_code=dict(dependency_audit.violations_by_code),
        violation_edges=[asdict(edge) for edge in dependency_audit.violation_edges],
        violation_edges_total_count=dependency_audit.violation_edges_total_count,
        violation_edges_truncated=dependency_audit.violation_edges_truncated,
        same_number_probe_count=dependency_audit.same_number_probe_count,
        dep_ordinal_equals_source_ref_ordinal_count=(
            dependency_audit.dep_ordinal_equals_source_ref_ordinal_count
        ),
        same_number_probes=[asdict(probe) for probe in dependency_audit.same_number_probes],
        connection_ref_not_visible_count=dependency_audit.connection_ref_not_visible_count,
        per_step_connection_counts=list(dependency_audit.per_step_connection_counts),
        per_step_cross_step_connection_counts=list(
            dependency_audit.per_step_cross_step_connection_counts
        ),
        per_step_inbound_dep_counts=list(dependency_audit.per_step_inbound_dep_counts),
        evidence_ref_count=dependency_audit.evidence_ref_count,
        block_candidate_count=dependency_audit.block_candidate_count,
        parameter_mapping_count=dependency_audit.parameter_mapping_count,
        prompt_tokens_bucket=dependency_audit.prompt_tokens_bucket,
        rendered_prompt_version=dependency_audit.rendered_prompt_version,
        hybrid_candidate=paper.hybrid_candidate,
        hybrid_guardrail_conclusion=hybrid_conclusion,
        hybrid_no_document_basis_misfire=hybrid_misfire,
    )


def write_guidance_artifacts(
    output_dir: Path,
    *,
    paper: SmokePaper,
    round_index: int,
    row: SmokeSummaryRow,
    snapshots: list[GuidanceArtifactSnapshot],
) -> list[Path]:
    """Write eval-only raw and readable build guidance artifacts."""

    artifact_dir = output_dir / "guidance_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for snapshot in snapshots:
        stem = (
            f"{paper.slug}__round_{round_index:02d}"
            f"__arm_{_safe_artifact_part(snapshot.arm_label)}"
        )
        payload = _guidance_artifact_payload(row, snapshot)
        json_path = artifact_dir / f"{stem}.guidance.json"
        text_path = artifact_dir / f"{stem}.guidance.txt"
        json_path.write_text(
            json.dumps(_jsonable(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        text_path.write_text(
            render_guidance_artifact_text(row, snapshot),
            encoding="utf-8",
        )
        written.extend([json_path, text_path])
    return written


def write_guidance_draft_artifacts(
    output_dir: Path,
    *,
    paper: SmokePaper,
    round_index: int,
    drafts: list[dict[str, Any]],
) -> list[Path]:
    """Write eval-only sanitized guidance draft payloads for direct inspection."""

    if not drafts:
        return []
    draft_dir = output_dir / "guidance_drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, draft in enumerate(drafts, start=1):
        stem = f"{paper.slug}__round_{round_index:02d}__attempt_{index:02d}"
        path = draft_dir / f"{stem}.guidance_draft.json"
        path.write_text(
            json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def _guidance_draft_capture_payload(
    payload: dict[str, Any],
    *,
    attempt_index: int,
    arm_label: str | None,
) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    raw_details = payload.get("details")
    if isinstance(raw_details, list):
        for item in raw_details:
            if not isinstance(item, dict):
                continue
            details.append(
                {
                    "step_id": item.get("step_id"),
                    "requirement_ref": item.get("requirement_ref"),
                    "basis": item.get("basis"),
                    "claim_text": item.get("claim_text"),
                    "supporting_evidence_refs": item.get("supporting_evidence_refs"),
                    "target": item.get("target"),
                    "confirmation_reason_code": item.get("confirmation_reason_code"),
                    "direction_hint": item.get("direction_hint"),
                    "resolution": item.get("resolution"),
                    "punt_reason_code": item.get("punt_reason_code"),
                }
            )
    return {
        "attempt_index": attempt_index,
        "arm_label": arm_label,
        "details": details,
    }


def _guidance_artifact_payload(
    row: SmokeSummaryRow,
    snapshot: GuidanceArtifactSnapshot,
) -> dict[str, object]:
    plan = snapshot.plan
    return {
        "paper_id": row.paper_id,
        "round_index": row.round_index,
        "arm": snapshot.arm_label,
        "build_steps": plan.build_steps if plan is not None else None,
        "build_guidance": plan.build_guidance if plan is not None else None,
        "guidance_status": snapshot.guidance_status,
        "guidance_delivered": snapshot.guidance_delivered,
        "guidance_evidence_clean": snapshot.guidance_evidence_clean,
        "guidance_fully_actionable": snapshot.guidance_fully_actionable,
        "generator_downgraded_unverified_count": (snapshot.generator_downgraded_unverified_count),
        "validator_dropped_unverified_count": snapshot.validator_dropped_unverified_count,
        "final_surviving_unverified_count": snapshot.final_surviving_unverified_count,
        "blocking_gap_count": snapshot.blocking_gap_count,
    }


def render_guidance_artifact_text(
    row: SmokeSummaryRow,
    snapshot: GuidanceArtifactSnapshot,
) -> str:
    """Render one build guidance artifact for direct human reading."""

    plan = snapshot.plan
    lines = [
        f"paper_id: {row.paper_id or 'unknown'}",
        f"round_index: {row.round_index}",
        f"arm: {snapshot.arm_label}",
        f"guidance_status: {snapshot.guidance_status}",
        (
            "judgement: "
            f"delivered={snapshot.guidance_delivered}, "
            f"evidence_clean={snapshot.guidance_evidence_clean}, "
            f"fully_actionable={snapshot.guidance_fully_actionable}"
        ),
        (
            "counts: "
            "generator_downgraded_unverified_count="
            f"{_display_count(snapshot.generator_downgraded_unverified_count)}, "
            "validator_dropped_unverified_count="
            f"{_display_count(snapshot.validator_dropped_unverified_count)}, "
            "final_surviving_unverified_count="
            f"{_display_count(snapshot.final_surviving_unverified_count)}, "
            f"blocking_gap_count={_display_count(snapshot.blocking_gap_count)}"
        ),
        "",
    ]
    if plan is None or not plan.build_steps:
        lines.append("（无 build_steps）")
        return "\n".join(lines) + "\n"
    if plan.build_guidance is None:
        lines.append("（无 build_guidance）")

    details_by_step: dict[str, list[Any]] = {}
    gaps_by_step: dict[str, list[Any]] = {}
    if plan.build_guidance is not None:
        for detail in plan.build_guidance.details:
            details_by_step.setdefault(detail.step_id, []).append(detail)
        for gap in plan.build_guidance.gaps:
            if gap.step_id is not None:
                gaps_by_step.setdefault(gap.step_id, []).append(gap)

    for index, step in enumerate(plan.build_steps, start=1):
        lines.append(f"[步骤 {index}] {step.title}")
        lines.append(f"  说明:{step.display_text or step.intent}")
        lines.append(f"  参数:{_render_step_parameters(step)}")
        for detail in details_by_step.get(step.step_id, []):
            lines.append(f"  说明:{detail.display_text}")
            lines.append(f"  出处:{_render_detail_source(detail)}")
        for gap in gaps_by_step.get(step.step_id, []):
            prefix = "[阻塞] " if gap.severity == "blocking" else ""
            lines.append(f"  缺口:{prefix}{gap.display_text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _guidance_snapshot_for_plan(
    arm_label: str,
    plan: ModelGenerationPlan | None,
    *,
    telemetry: BuildStepsTelemetry | None = None,
    row: SmokeSummaryRow | None = None,
) -> GuidanceArtifactSnapshot:
    output_counts = _guidance_output_counts(plan)
    guidance_status = plan.guidance_status if plan is not None else "not_generated"
    guidance_delivered = guidance_status == "generated" and output_counts["has_guidance"] is True
    final_unverified = output_counts["final_unverified_detail_count"]
    guidance_evidence_clean = guidance_delivered and final_unverified == 0
    guidance_fully_actionable = guidance_evidence_clean and output_counts["blocking_gap_count"] == 0
    return GuidanceArtifactSnapshot(
        arm_label=arm_label,
        plan=plan,
        guidance_status=guidance_status,
        guidance_delivered=guidance_delivered,
        guidance_evidence_clean=guidance_evidence_clean,
        guidance_fully_actionable=guidance_fully_actionable,
        generator_downgraded_unverified_count=_artifact_count(
            "generator_downgraded_unverified_count",
            guidance_delivered=guidance_delivered,
            telemetry=telemetry,
            row=row,
        ),
        validator_dropped_unverified_count=_artifact_count(
            "validator_dropped_unverified_count",
            guidance_delivered=guidance_delivered,
            telemetry=telemetry,
            row=row,
        ),
        final_surviving_unverified_count=final_unverified,
        blocking_gap_count=output_counts["blocking_gap_count"],
    )


def _artifact_count(
    field_name: str,
    *,
    guidance_delivered: bool,
    telemetry: BuildStepsTelemetry | None,
    row: SmokeSummaryRow | None,
) -> int | None:
    if not guidance_delivered:
        return None
    if row is not None:
        value = getattr(row, field_name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if telemetry is not None:
        value = getattr(telemetry, field_name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    return None


def _guidance_resolver_code_count(
    attempts: list[dict[str, object]],
    code: str,
    *,
    guidance_invoked: bool,
) -> int | None:
    if not guidance_invoked:
        return None
    count = 0
    for attempt in attempts:
        codes = attempt.get("resolver_event_codes")
        if isinstance(codes, list):
            count += sum(1 for item in codes if item == code)
    return count


def _render_step_parameters(step: ModelBuildStep) -> str:
    if not step.parameter_refs:
        return "无"
    return ", ".join(
        f"{ref.paper_param_name} -> {ref.model_param_name}" for ref in step.parameter_refs
    )


def _render_detail_source(detail: Any) -> str:
    if detail.basis == "document_claim_unverified" or (
        detail.basis == "user_confirmation_required"
        and detail.confirmation_reason_code == "document_evidence_unverified"
    ):
        return "★ 未核实,请用户自行确认"
    if detail.basis == "engineering_convention":
        return f"工程惯例:{detail.convention_code or 'unspecified'}"
    if not detail.evidence:
        return "论文依据缺失"
    return "; ".join(_render_evidence_locator(entry) for entry in detail.evidence)


def _render_evidence_locator(entry: Any) -> str:
    if entry.paper_section_id:
        return f"论文 {entry.document_id or 'unknown'} 第 {entry.paper_section_id} 处"
    if entry.equation_id:
        return f"论文 {entry.document_id or 'unknown'} 公式 {entry.equation_id}"
    if entry.figure_id:
        return f"论文 {entry.document_id or 'unknown'} 图 {entry.figure_id}"
    return f"论文 {entry.document_id or 'unknown'}"


def _display_count(value: int | None) -> str:
    return "null" if value is None else str(value)


def _safe_artifact_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe or "main"


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def classify_build_steps_result(
    plan_record: PaperPlanRecord | None,
    telemetry: BuildStepsTelemetry,
) -> BuildStepsResultCode:
    if plan_record is not None and plan_record.plan.build_steps:
        return "结构化成功"
    return _classify_build_steps_failure(
        telemetry.fallback_reason_code,
        telemetry.fallback_exception_code,
    )


def _guidance_output_counts(plan: ModelGenerationPlan | None) -> dict[str, Any]:
    build_steps = plan.build_steps if plan is not None else None
    critical_step_count = len(_critical_steps(build_steps)) if build_steps is not None else None
    requirement_count = (
        len(enumerate_guidance_requirements(plan.paper_spec_id, build_steps))
        if plan is not None and build_steps
        else None
    )
    guidance = plan.build_guidance if plan is not None else None
    if guidance is None:
        return {
            "has_guidance": False,
            "critical_step_count": critical_step_count,
            "guidance_requirement_enumerated_count": requirement_count,
            "blocking_gap_count": None,
            "final_detail_total_count": None,
            "final_document_detail_count": None,
            "final_unverified_detail_count": None,
            "final_detail_basis_counts": None,
            "final_execution_closure_counts": None,
            "pending_user_choice_count": None,
            "pending_environment_probe_count": None,
            "open_requirement_count": None,
        }
    final_unverified = _final_unverified_detail_count(plan)
    return {
        "has_guidance": True,
        "critical_step_count": critical_step_count,
        "guidance_requirement_enumerated_count": requirement_count,
        "blocking_gap_count": len(guidance.assessment.blocking_gap_ids),
        "final_detail_total_count": len(guidance.details),
        "final_document_detail_count": sum(
            1 for detail in guidance.details if detail.basis == "document_extracted"
        ),
        "final_unverified_detail_count": final_unverified,
        "final_detail_basis_counts": _count_values(
            (detail.basis for detail in guidance.details),
            GUIDANCE_BASIS_KEYS,
        ),
        "final_execution_closure_counts": _count_values(
            (detail.execution_closure for detail in guidance.details),
            GUIDANCE_CLOSURE_KEYS,
        ),
        "pending_user_choice_count": guidance.assessment.pending_user_choice_count,
        "pending_environment_probe_count": guidance.assessment.pending_environment_probe_count,
        "open_requirement_count": guidance.assessment.open_requirement_count,
    }


def _count_values(values: Iterable[object], keys: tuple[str, ...]) -> dict[str, int]:
    counts = Counter(value for value in values if isinstance(value, str))
    return {key: counts.get(key, 0) for key in keys}


def _final_unverified_detail_count(plan: ModelGenerationPlan) -> int:
    if plan.build_guidance is None:
        return 0
    return sum(
        1
        for detail in plan.build_guidance.details
        if detail.basis == "document_claim_unverified"
        or (
            detail.basis == "user_confirmation_required"
            and detail.confirmation_reason_code == "document_evidence_unverified"
        )
    )


def _guidance_status_reason_valid(status: str, reason: str | None) -> bool:
    try:
        validate_guidance_status_reason(status, reason)
    except ValueError:
        return False
    return True


def _terminal_observed_stage(
    *,
    plan_ready: bool,
    build_steps_structured: bool,
    guidance_failure_reason: str | None,
) -> str | None:
    if guidance_failure_reason is not None:
        return "guidance"
    if not plan_ready:
        return "plan"
    if not build_steps_structured:
        return "build_steps"
    return None


def _guidance_effective_config(call: LLMCallRecord | None) -> dict[str, object]:
    return {
        "model_fingerprint": _model_fingerprint(call.request_model) if call else None,
        "max_tokens": call.max_tokens if call else None,
        "timeout": call.timeout if call else None,
        "json_mode": call.json_mode if call else None,
        "response_format": call.response_format if call else None,
        "temperature": call.temperature if call else None,
        "top_p": call.top_p if call else None,
        "seed": call.seed if call else None,
        "guidance_full_attempts": GUIDANCE_FULL_ATTEMPTS,
        "guidance_hard_call_cap": GUIDANCE_HARD_CALL_CAP,
        "guidance_wall_clock_seconds": GUIDANCE_WALL_CLOCK_SECONDS,
        "guidance_prompt_template_version": _guidance_prompt_template_version(),
        "guidance_prompt_template_sha256": _guidance_prompt_template_sha256(),
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "git_revision": _git_revision(),
    }


def _model_fingerprint(model: str | None) -> str | None:
    if not model:
        return None
    digest = hashlib.sha256(f"llm-model:{model}".encode()).hexdigest()[:12]
    return f"model_fp_{digest}"


def _guidance_prompt_template_version() -> str:
    return load_prompt_template("paper_build_guidance.yaml").version


def _guidance_prompt_template_sha256() -> str:
    path = Path(__file__).resolve().parents[1] / "core" / "prompts" / "paper_build_guidance.yaml"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def validate_guidance_batch_observability(
    rows: list[SmokeSummaryRow],
    *,
    planned_round_count: int | None = None,
) -> None:
    """Validate pre-registered TASK-535 guidance batch gates."""

    if planned_round_count is not None and len(rows) != planned_round_count:
        raise GuidanceBatchInvalidError("terminal_round_record_count_mismatch")
    for row in rows:
        if not row.guidance_status_reason_valid:
            raise GuidanceBatchInvalidError("invalid_guidance_status_reason")
        if row.guidance_delivered and row.all_document_details_lost:
            raise GuidanceBatchInvalidError("delivered_with_all_document_details_lost")
        if (
            row.guidance_failure_reason == "retry_cap_exhausted"
            and row.guidance_provider_call_count >= GUIDANCE_HARD_CALL_CAP
        ):
            raise GuidanceBatchInvalidError("retry_cap_exhausted_reached_hard_cap")
        if not row.guidance_delivered and row.first_blocking_stage is None:
            raise GuidanceBatchInvalidError("missing_first_blocking_stage")
        if row.failure_owner_bucket == "unattributed":
            raise GuidanceBatchInvalidError("unattributed_failures")
        if row.guidance_attempt_record_count != row.guidance_provider_call_count:
            raise GuidanceBatchInvalidError("guidance_attempt_provider_count_mismatch")


def _classify_build_steps_failure(
    reason: str | None,
    exception_code: str | None,
) -> BuildStepsResultCode:
    if reason in BUILD_STEPS_BRIDGE_REASON_CODES:
        return cast(BuildStepsResultCode, reason)
    if reason == "dto_invalid":
        return "dto_invalid"
    if reason == "json_parse_failed":
        return "json_parse_failed"
    if reason == "br_no_match":
        return "br_no_match"
    if reason == "coverage_missing":
        return "coverage_missing"
    if exception_code == "build_steps_redline" or reason in {
        "parameter_value_leak",
        "tuning_value_leak",
    }:
        return "redline"
    if exception_code == "build_steps_evidence" or (reason is not None and "evidence" in reason):
        return "evidence_invalid"
    return "其它"


def _build_steps_exception_code(exc: BaseException) -> str:
    if isinstance(exc, BuildStepsRedLineError):
        return "build_steps_redline"
    if isinstance(exc, BuildStepsEvidenceError):
        return "build_steps_evidence"
    if isinstance(exc, BuildStepsDtoValidationError):
        return "build_steps_dto"
    if isinstance(exc, BuildStepsJsonParseError):
        return "build_steps_json_parse"
    if isinstance(exc, BuildStepsStructuredError):
        return "build_steps_structured"
    return "unexpected_internal_error"


def _paired_arm_result_code(exc: BaseException) -> str:
    reason_code = getattr(exc, "reason_code", None)
    if isinstance(reason_code, str) and reason_code:
        return reason_code
    if isinstance(exc, BuildStepsStructuredError):
        return _build_steps_exception_code(exc)
    return guidance_exception_code(exc)


def _dependency_audit_for_summary(
    telemetry: BuildStepsTelemetry,
    build_steps_call: LLMCallRecord | None,
) -> DependencyAudit:
    audit = telemetry.dependency_audit
    if audit.prompt_tokens_bucket is not None or build_steps_call is None:
        return audit
    return replace(audit, prompt_tokens_bucket=prompt_token_bucket(build_steps_call.prompt_tokens))


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
    payloads = _summary_payloads_with_run_model_summary(rows)
    json_path.write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for payload in payloads:
            payload["dto_invalid_errors"] = json.dumps(
                payload["dto_invalid_errors"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for json_column in (
                "llm_model_identifiers",
                "llm_model_identifier_counts",
                "llm_system_fingerprints",
                "llm_system_fingerprint_counts",
                "run_llm_model_identifiers",
                "run_llm_model_identifier_counts",
                "run_llm_system_fingerprints",
                "run_llm_system_fingerprint_counts",
                "paired_arm_order",
                "paired_build_steps_arms",
                "guidance_validator_machine_codes",
                "guidance_attempts",
                "guidance_effective_config",
                "final_detail_basis_counts",
                "final_execution_closure_counts",
                "violations_by_code",
                "violation_edges",
                "same_number_probes",
                "per_step_connection_counts",
                "per_step_cross_step_connection_counts",
                "per_step_inbound_dep_counts",
            ):
                payload[json_column] = json.dumps(
                    payload[json_column],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            payload["spec_validation_errors"] = json.dumps(
                payload["spec_validation_errors"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            writer.writerow(payload)


def _summary_payloads_with_run_model_summary(
    rows: list[SmokeSummaryRow],
) -> list[dict[str, Any]]:
    run_model_summary = _run_model_summary_from_rows(rows)
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload = row.to_dict()
        payload["run_llm_model_identifiers"] = run_model_summary["model_identifiers"]
        payload["run_llm_model_identifier_counts"] = run_model_summary["model_identifier_counts"]
        payload["run_llm_system_fingerprints"] = run_model_summary["system_fingerprints"]
        payload["run_llm_system_fingerprint_counts"] = run_model_summary[
            "system_fingerprint_counts"
        ]
        payload["run_llm_version_fingerprint_note"] = run_model_summary["version_fingerprint_note"]
        payloads.append(payload)
    return payloads


def _paired_build_steps_arms_for_summary(
    telemetry: BuildStepsTelemetry,
    llm_calls: list[LLMCallRecord],
) -> list[dict[str, Any]]:
    if not telemetry.paired_build_steps_enabled:
        return []
    call_by_arm: dict[str, LLMCallRecord] = {}
    for call in llm_calls:
        if call.role == BUILD_STEP_ROLE_NAME and call.arm_label is not None:
            call_by_arm[call.arm_label] = call

    arms: list[dict[str, Any]] = []
    for arm in telemetry.paired_build_steps_arms:
        payload = dict(arm)
        call = call_by_arm.get(str(payload.get("arm_label")))
        payload.update(
            {
                "finish_reason": call.finish_reason if call else None,
                "prompt_tokens": call.prompt_tokens if call else None,
                "completion_tokens": call.completion_tokens if call else None,
                "total_tokens": call.total_tokens if call else None,
                "max_tokens": call.max_tokens if call else None,
                "response_model": _model_fingerprint(call.response_model) if call else None,
                "system_fingerprint": call.system_fingerprint if call else None,
            }
        )
        arms.append(payload)
    return arms


def _run_model_summary_from_rows(rows: list[SmokeSummaryRow]) -> dict[str, Any]:
    model_counts: Counter[str] = Counter()
    fingerprint_counts: Counter[str] = Counter()
    saw_llm_call = False
    for row in rows:
        for model, count in row.llm_model_identifier_counts.items():
            model_counts[model] += count
            saw_llm_call = True
        for fingerprint, count in row.llm_system_fingerprint_counts.items():
            fingerprint_counts[fingerprint] += count
    return _model_summary_from_counts(
        model_counts,
        fingerprint_counts,
        saw_llm_call=saw_llm_call,
        no_calls_note="本次运行未发生 LLM 调用",
    )


def _llm_model_summary(
    calls: list[LLMCallRecord],
    *,
    no_calls_note: str,
) -> dict[str, Any]:
    model_counts: Counter[str] = Counter(
        fingerprint
        for call in calls
        if (fingerprint := _model_fingerprint(call.response_model)) is not None
    )
    fingerprint_counts: Counter[str] = Counter(
        call.system_fingerprint for call in calls if call.system_fingerprint
    )
    return _model_summary_from_counts(
        model_counts,
        fingerprint_counts,
        saw_llm_call=bool(calls),
        no_calls_note=no_calls_note,
    )


def _model_summary_from_counts(
    model_counts: Counter[str],
    fingerprint_counts: Counter[str],
    *,
    saw_llm_call: bool,
    no_calls_note: str,
) -> dict[str, Any]:
    if not saw_llm_call:
        note = no_calls_note
    elif not fingerprint_counts:
        note = VERSION_FINGERPRINT_UNAVAILABLE_NOTE
    else:
        note = None
    return {
        "model_identifiers": sorted(model_counts),
        "model_identifier_counts": dict(sorted(model_counts.items())),
        "system_fingerprints": sorted(fingerprint_counts),
        "system_fingerprint_counts": dict(sorted(fingerprint_counts.items())),
        "version_fingerprint_note": note,
    }


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
    parser.add_argument(
        "--paired-build-steps",
        action="store_true",
        help="Call BuildStepPlanner twice on the same upstream input: legacy off arm and salience on arm.",
    )
    parser.add_argument(
        "--paired-build-steps-full",
        action="store_true",
        help=(
            "Call BuildStepPlanner twice on the same upstream input, then run full "
            "build-step validation and build guidance for both arms. The on arm "
            "remains the persisted main path."
        ),
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
        paired_build_steps=args.paired_build_steps,
        paired_build_steps_full=args.paired_build_steps_full,
    )
    print(f"summary_json={_display_path(runtime.output_dir / 'paper_pdf_smoke.summary.json')}")
    print(f"summary_csv={_display_path(runtime.output_dir / 'paper_pdf_smoke.summary.csv')}")
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


def _paired_build_steps_first_arm(round_index: int) -> str:
    return "on" if round_index % 2 == 0 else "off"


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


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return str(resolved.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return resolved.name


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
                "loc": _sanitize_pydantic_loc(loc),
                "type": str(error_type or "unknown"),
            }
        )
    return errors


_SAFE_PYDANTIC_LOC_PARTS = frozenset(
    {
        "build_steps",
        "step_id",
        "title",
        "intent",
        "block_refs",
        "block_ref_id",
        "block_type",
        "library_path",
        "purpose",
        "paper_reference",
        "parameter_refs",
        "paper_param_name",
        "model_param_name",
        "connection_hints",
        "from_block_ref",
        "from_port",
        "to_block_ref",
        "to_port",
        "signal_meaning",
        "configuration_hints",
        "target",
        "setting_name",
        "instruction",
        "depends_on",
        "evidence",
        "source",
        "document_id",
        "paper_section_id",
        "equation_id",
        "figure_id",
        "excerpt",
        "missing_param_prompt_id",
        "user_action",
        "parameter_correction_id",
        "correction_param_key",
        "source_ref",
    }
)


def _sanitize_pydantic_loc(loc: object) -> str:
    if not isinstance(loc, tuple):
        return "root"
    parts: list[str] = []
    for part in loc:
        text = str(part)
        if isinstance(part, int) or text.isdigit() or text in _SAFE_PYDANTIC_LOC_PARTS:
            parts.append(text)
        else:
            parts.append("<dynamic_key>")
    return ".".join(parts)


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
    payload_error_code = _payload_str(response_payload, "error_code")
    if payload_error_code:
        return payload_error_code
    payload_error = _payload_str(response_payload, "error")
    if payload_error:
        return payload_error
    if unexpected_error is not None:
        return guidance_exception_code(unexpected_error)
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
        "unexpected_error_code": guidance_exception_code(unexpected_error)
        if unexpected_error
        else None,
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
