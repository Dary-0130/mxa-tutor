"""PaperAsk use case for persisted paper plan records."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.domain.paper_ask import (
    EquationTarget,
    MissingPromptParameterTarget,
    PaperAskCitation,
    PaperAskFallbackReason,
    PaperAskRequest,
    PaperAskResponse,
    PaperCitationTarget,
    PaperResultSection,
    PlanMappingParameterTarget,
    SectionTarget,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import ModelBuildStep, PaperPlanRecord
from core.domain.paper_tuning import ConfidenceValue
from core.interfaces.llm_provider import LLMMessage, TextProvider
from features.paper._prompt_loader import load_prompt_template
from features.paper.paper_ask_schemas import PaperAskResponseModel
from features.paper.paper_plan_helpers import (
    UserEvidenceRef,
    resolved_prompt_ids,
    resolved_user_evidence_refs,
)

DEFAULT_ASK_TIMEOUT_SECONDS = 60.0
DEFAULT_ASK_MAX_TOKENS = 1800
DEFAULT_SOURCE_TABLE_LIMIT = 24

_SOURCE_ID_RE = re.compile(r"^S[1-9][0-9]*$")
_FORBIDDEN_OUTPUT_KEY_PARTS = ("anchor", "dom_id", "locator")
_FORBIDDEN_MARKER_PARTS = (
    ("paper", "eq"),
    ("paper", "param", "map"),
    ("paper", "param", "missing"),
)
_RESULT_SECTIONS: frozenset[PaperResultSection] = frozenset(
    {
        "paper-summary",
        "paper-subsystems",
        "paper-build-steps",
        "paper-parameters",
        "paper-tuning",
    }
)


@dataclass(frozen=True)
class SourceTableEntry:
    """One backend-owned source entry that the LLM may cite by source_id."""

    source_id: str
    label: str
    excerpt: str | None
    source_kind: EvidenceSource
    document_id: str | None
    document_label: str | None
    target: PaperCitationTarget

    def to_citation(self) -> PaperAskCitation:
        """Return the public citation shape expanded from backend-owned source metadata."""

        return PaperAskCitation(
            source_id=self.source_id,
            label=self.label,
            excerpt=self.excerpt,
            source_kind=self.source_kind,
            target=self.target,
            document_id=self.document_id,
            document_label=self.document_label,
        )


@dataclass(frozen=True)
class _SourceCandidate:
    label: str
    excerpt: str | None
    source_kind: EvidenceSource
    document_id: str | None
    document_label: str | None
    target: PaperCitationTarget


class PaperAskService:
    """Generate one stateless answer from a ready paper plan."""

    def __init__(
        self,
        text_provider: TextProvider,
        *,
        timeout: float = DEFAULT_ASK_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_ASK_MAX_TOKENS,
        source_table_limit: int = DEFAULT_SOURCE_TABLE_LIMIT,
    ) -> None:
        self._text_provider = text_provider
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._source_table_limit = max(0, source_table_limit)

    async def ask(
        self,
        record: PaperPlanRecord,
        request: PaperAskRequest,
        *,
        corrections: list[PaperParameterCorrection] | None = None,
    ) -> PaperAskResponse:
        """Return a validated answer or a 200-level fallback response."""
        full_source_table = (
            build_paper_ask_source_table(record)
            if corrections is None
            else build_paper_ask_source_table(record, corrections=corrections)
        )
        prompt_source_table = full_source_table[: self._source_table_limit]
        session_id = request.session_id or str(uuid.uuid4())

        if not prompt_source_table:
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="insufficient_evidence",
                answer_kind=None,
            )

        payload = await self._call_llm_payload(
            _build_messages_for_paper_ask(prompt_source_table, request.question)
        )
        if payload is None or _payload_contains_forbidden_output(payload):
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="invalid_or_missing_citations",
                answer_kind=None,
            )

        try:
            output = _PaperAskLLMOutputModel.model_validate(payload)
        except ValidationError:
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="invalid_or_missing_citations",
                answer_kind=None,
            )

        if output.answer_kind == "out_of_scope":
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="out_of_scope",
                answer_kind=output.answer_kind,
            )

        citation_ids = _dedupe_preserving_order(output.citation_ids)
        if not citation_ids or any(_SOURCE_ID_RE.fullmatch(item) is None for item in citation_ids):
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="invalid_or_missing_citations",
                answer_kind=output.answer_kind,
            )

        prompt_index = {entry.source_id: entry for entry in prompt_source_table}
        if any(source_id not in prompt_index for source_id in citation_ids):
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="invalid_or_missing_citations",
                answer_kind=output.answer_kind,
            )

        selected_sources = [prompt_index[source_id] for source_id in citation_ids]
        if any(not _source_entry_target_resolves(entry, record) for entry in selected_sources):
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="citation_target_unresolved",
                answer_kind=output.answer_kind,
            )
        citations = [entry.to_citation() for entry in selected_sources]

        response = PaperAskResponse(
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            answer=output.answer,
            confidence=output.confidence,
            citations=citations,
            follow_up_suggestions=list(output.follow_up_suggestions),
        )
        try:
            return PaperAskResponseModel.from_domain(response).to_domain()
        except ValidationError:
            return self._fallback_response(
                record,
                session_id=session_id,
                reason="invalid_or_missing_citations",
                answer_kind=output.answer_kind,
            )

    async def _call_llm_payload(self, messages: list[LLMMessage]) -> dict[str, Any] | None:
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _fallback_response(
        self,
        record: PaperPlanRecord,
        *,
        session_id: str,
        reason: PaperAskFallbackReason,
        answer_kind: str | None,
    ) -> PaperAskResponse:
        logger.info(
            "paper_ask_fallback paper_id={} reason={} citation_count={} answer_kind={}",
            record.paper_id,
            reason,
            0,
            answer_kind,
        )
        response = PaperAskResponse(
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            answer=_fallback_answer(reason),
            confidence="low",
            citations=[],
            follow_up_suggestions=[],
            is_fallback=True,
            fallback_reason=reason,
        )
        return PaperAskResponseModel.from_domain(response).to_domain()


def build_paper_ask_source_table(
    record: PaperPlanRecord,
    *,
    corrections: list[PaperParameterCorrection] | None = None,
) -> list[SourceTableEntry]:
    """Build the full backend-owned PaperAsk source table for a plan record."""
    candidates: list[_SourceCandidate] = []
    candidates.extend(_spec_candidates(record))
    candidates.extend(_plan_document_section_candidates(record))
    candidates.extend(
        _user_supplied_parameter_candidates(
            record,
            None if corrections is None else resolved_user_evidence_refs(record, corrections),
            corrections,
        )
    )
    candidates.extend(_remaining_missing_prompt_candidates(record))

    return [
        SourceTableEntry(
            source_id=f"S{index}",
            label=candidate.label,
            excerpt=candidate.excerpt,
            source_kind=candidate.source_kind,
            document_id=candidate.document_id,
            document_label=candidate.document_label,
            target=candidate.target,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]


def _spec_candidates(record: PaperPlanRecord) -> list[_SourceCandidate]:
    candidates: list[_SourceCandidate] = []
    representative_document_id = _representative_document_id(record)
    abstract = _document_candidate(
        label="Paper summary",
        excerpt=record.spec.abstract,
        document_id=representative_document_id,
        document_label=_document_label(record, representative_document_id),
        target=SectionTarget(kind="section", result_section="paper-summary"),
    )
    if abstract is not None:
        candidates.append(abstract)

    for equation in record.spec.equations:
        candidate = _document_candidate(
            label=f"Equation {equation.equation_id}",
            excerpt=equation.latex_or_text,
            document_id=equation.document_id,
            document_label=_document_label(record, equation.document_id),
            target=EquationTarget(kind="equation", equation_id=equation.equation_id),
        )
        if candidate is not None:
            candidates.append(candidate)

    equation_ids = {
        (entry.document_id, entry.equation_id)
        for entry in record.spec.equations
        if entry.document_id is not None
    }
    for evidence in record.spec.evidence:
        candidate = _candidate_from_document_evidence(
            evidence,
            label="Document evidence",
            document_label=_document_label(record, evidence.document_id),
            equation_ids=equation_ids,
            section_target="paper-summary",
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _plan_document_section_candidates(record: PaperPlanRecord) -> list[_SourceCandidate]:
    candidates: list[_SourceCandidate] = []
    equation_ids = {
        (entry.document_id, entry.equation_id)
        for entry in record.spec.equations
        if entry.document_id is not None
    }

    for recommendation in record.plan.block_recommendations:
        candidate = _candidate_from_document_evidence(
            recommendation.paper_reference,
            label=f"Block recommendation: {recommendation.block_type}",
            document_label=_document_label(record, recommendation.paper_reference.document_id),
            equation_ids=equation_ids,
            section_target="paper-subsystems",
        )
        if candidate is not None:
            candidates.append(candidate)

    build_step_evidence = _rendered_build_step_evidence(record.plan.build_steps)
    if build_step_evidence is None:
        build_step_evidence = [
            recommendation.paper_reference for recommendation in record.plan.block_recommendations
        ]
    for evidence in build_step_evidence:
        candidate = _candidate_from_document_evidence(
            evidence,
            label="Build-step supporting evidence",
            document_label=_document_label(record, evidence.document_id),
            equation_ids=equation_ids,
            section_target="paper-build-steps",
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _user_supplied_parameter_candidates(
    record: PaperPlanRecord,
    resolved_user_refs: set[UserEvidenceRef] | None,
    corrections: list[PaperParameterCorrection] | None,
) -> list[_SourceCandidate]:
    candidates: list[_SourceCandidate] = []
    for row_index, mapping in enumerate(record.plan.parameter_mapping):
        if mapping.source is not EvidenceSource.USER_SUPPLIED:
            continue
        if resolved_user_refs is not None and not _mapping_has_resolved_user_evidence(
            record,
            row_index,
            resolved_user_refs,
            corrections or [],
        ):
            continue
        candidates.append(
            _SourceCandidate(
                label=_clean_label(f"User-supplied parameter: {mapping.paper_param_name}"),
                excerpt=None,
                source_kind=EvidenceSource.USER_SUPPLIED,
                document_id=None,
                document_label=None,
                target=PlanMappingParameterTarget(
                    kind="parameter",
                    origin="plan_mapping",
                    row_index=row_index,
                    paper_param_name=mapping.paper_param_name,
                    model_param_name=mapping.model_param_name,
                ),
            )
        )
    return candidates


def _mapping_has_resolved_user_evidence(
    record: PaperPlanRecord,
    row_index: int,
    resolved_user_refs: set[UserEvidenceRef],
    corrections: list[PaperParameterCorrection],
) -> bool:
    mapping = record.plan.parameter_mapping[row_index]
    for binding in record.missing_bindings:
        if (
            binding.paper_param_name == mapping.paper_param_name
            and binding.model_param_name == mapping.model_param_name
            and UserEvidenceRef(kind=UserEvidenceAction.FILL_MISSING, key=binding.prompt_id)
            in resolved_user_refs
        ):
            return True
    corrections_by_id = {correction.correction_id: correction for correction in corrections}
    for entry in record.plan.evidence:
        correction = (
            corrections_by_id.get(entry.parameter_correction_id)
            if entry.parameter_correction_id is not None
            else None
        )
        if (
            entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED
            and entry.parameter_correction_id is not None
            and correction is not None
            and correction.plan_target.plan_mapping_index == row_index
            and correction.plan_target.paper_param_name == mapping.paper_param_name
            and correction.plan_target.model_param_name == mapping.model_param_name
            and UserEvidenceRef(
                kind=UserEvidenceAction.CORRECT_EXTRACTED,
                key=entry.parameter_correction_id,
            )
            in resolved_user_refs
        ):
            return True
    return False


def _remaining_missing_prompt_candidates(record: PaperPlanRecord) -> list[_SourceCandidate]:
    resolved_ids = resolved_prompt_ids(record)
    candidates: list[_SourceCandidate] = []
    for prompt in record.missing_prompts:
        if prompt.prompt_id in resolved_ids:
            continue
        candidates.append(
            _SourceCandidate(
                label=_clean_label(f"Missing parameter: {prompt.parameter_name}"),
                excerpt=None,
                source_kind=EvidenceSource.USER_SUPPLIED,
                document_id=None,
                document_label=None,
                target=MissingPromptParameterTarget(
                    kind="parameter",
                    origin="missing_prompt",
                    prompt_id=prompt.prompt_id,
                    parameter_name=prompt.parameter_name,
                ),
            )
        )
    return candidates


def _rendered_build_step_evidence(
    build_steps: list[ModelBuildStep] | None,
) -> list[PaperEvidenceEntry] | None:
    if build_steps is None:
        return None
    evidence: list[PaperEvidenceEntry] = []
    for step in build_steps:
        evidence.extend(step.evidence)
    return evidence


def _candidate_from_document_evidence(
    evidence: PaperEvidenceEntry,
    *,
    label: str,
    document_label: str | None,
    equation_ids: set[tuple[str, str]],
    section_target: PaperResultSection,
) -> _SourceCandidate | None:
    if evidence.source is not EvidenceSource.DOCUMENT_EXTRACTED:
        return None
    if evidence.equation_id is not None:
        if (
            evidence.document_id is None
            or (evidence.document_id, evidence.equation_id) not in equation_ids
        ):
            return None
        return _document_candidate(
            label=label,
            excerpt=evidence.excerpt,
            document_id=evidence.document_id,
            document_label=document_label,
            target=EquationTarget(kind="equation", equation_id=evidence.equation_id),
        )
    if evidence.paper_section_id is None:
        return None
    return _document_candidate(
        label=label,
        excerpt=evidence.excerpt,
        document_id=evidence.document_id,
        document_label=document_label,
        target=SectionTarget(kind="section", result_section=section_target),
    )


def _document_candidate(
    *,
    label: str,
    excerpt: str | None,
    document_id: str | None,
    document_label: str | None,
    target: PaperCitationTarget,
) -> _SourceCandidate | None:
    cleaned_excerpt = _clean_excerpt(excerpt)
    if cleaned_excerpt is None:
        return None
    return _SourceCandidate(
        label=_clean_label(label),
        excerpt=cleaned_excerpt,
        source_kind=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id=document_id,
        document_label=document_label,
        target=target,
    )


def _document_label(record: PaperPlanRecord, document_id: str | None) -> str | None:
    if document_id is None:
        return None
    for document in record.spec.documents:
        if document.document_id == document_id:
            return _clean_label(document.filename)
    return None


def _representative_document_id(record: PaperPlanRecord) -> str | None:
    if record.spec.primary_document_id is not None:
        return record.spec.primary_document_id
    if not record.spec.documents:
        return None
    return record.spec.documents[0].document_id


def _clean_excerpt(value: str | None) -> str | None:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        return None
    return cleaned[:300]


def _clean_label(value: str) -> str:
    cleaned = " ".join(value.split())
    return (cleaned or "Paper source")[:200]


def _build_messages_for_paper_ask(
    source_table: list[SourceTableEntry],
    question: str,
) -> list[LLMMessage]:
    template = load_prompt_template("paper_ask.yaml")
    source_table_json = json.dumps(
        [_source_table_entry_payload(entry) for entry in source_table],
        ensure_ascii=False,
        indent=2,
    )
    return [
        LLMMessage(role="system", content=template.system),
        LLMMessage(
            role="user",
            content=template.user.format(
                source_table_json=source_table_json,
                question=question,
            ),
        ),
    ]


def _source_table_entry_payload(entry: SourceTableEntry) -> dict[str, Any]:
    return {
        "source_id": entry.source_id,
        "label": entry.label,
        "excerpt": entry.excerpt,
        "source_kind": entry.source_kind.value,
        "target": _citation_target_payload(entry.target),
    }


def _citation_target_payload(target: PaperCitationTarget) -> dict[str, Any]:
    if isinstance(target, SectionTarget):
        return {"kind": target.kind, "result_section": target.result_section}
    if isinstance(target, EquationTarget):
        return {"kind": target.kind, "equation_id": target.equation_id}
    if isinstance(target, PlanMappingParameterTarget):
        return {
            "kind": target.kind,
            "origin": target.origin,
            "row_index": target.row_index,
            "paper_param_name": target.paper_param_name,
            "model_param_name": target.model_param_name,
        }
    if isinstance(target, MissingPromptParameterTarget):
        return {
            "kind": target.kind,
            "origin": target.origin,
            "prompt_id": target.prompt_id,
            "parameter_name": target.parameter_name,
        }
    raise TypeError(f"unsupported paper citation target: {type(target).__name__}")


def _payload_contains_forbidden_output(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key).casefold()
            if any(part in key_text for part in _FORBIDDEN_OUTPUT_KEY_PARTS):
                return True
            if _payload_contains_forbidden_output(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_payload_contains_forbidden_output(item) for item in payload)
    if isinstance(payload, str):
        lowered = payload.casefold()
        return any(marker in lowered for marker in _forbidden_dom_markers())
    return False


def _forbidden_dom_markers() -> tuple[str, ...]:
    return tuple("-".join(parts) + "-" for parts in _FORBIDDEN_MARKER_PARTS)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _source_entry_target_resolves(entry: SourceTableEntry, record: PaperPlanRecord) -> bool:
    target = entry.target
    if isinstance(target, SectionTarget):
        return target.result_section in _RESULT_SECTIONS
    if isinstance(target, EquationTarget):
        return (entry.document_id, target.equation_id) in {
            (equation.document_id, equation.equation_id)
            for equation in record.spec.equations
            if equation.document_id is not None
        }
    if isinstance(target, PlanMappingParameterTarget):
        if target.row_index < 0 or target.row_index >= len(record.plan.parameter_mapping):
            return False
        mapping = record.plan.parameter_mapping[target.row_index]
        return (
            mapping.paper_param_name == target.paper_param_name
            and mapping.model_param_name == target.model_param_name
        )
    if isinstance(target, MissingPromptParameterTarget):
        remaining_ids = {
            prompt.prompt_id
            for prompt in record.missing_prompts
            if prompt.prompt_id not in resolved_prompt_ids(record)
        }
        return target.prompt_id in remaining_ids
    return False


def _fallback_answer(reason: PaperAskFallbackReason) -> str:
    if reason == "out_of_scope":
        return "这个问题超出了当前资料复现范围,我暂时不能基于这份资料回答。"
    if reason == "insufficient_evidence":
        return "当前解析结果里没有足够的可引用出处来回答这个问题。"
    if reason == "citation_target_unresolved":
        return "当前解析结果里的出处已发生变化,我暂时不能给出带依据的结论。"
    return "当前回答没有通过出处校验,我暂时不能给出带依据的结论。"


class _PaperAskLLMOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_kind: Literal["answer", "out_of_scope"]
    answer: str = Field(min_length=1, max_length=3000)
    citation_ids: list[str]
    confidence: ConfidenceValue
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)
