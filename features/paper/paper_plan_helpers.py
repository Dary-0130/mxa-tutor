"""Feature-private helpers for paper plan generation."""

from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Literal, NoReturn, Protocol

from core.domain.exceptions import MxaError, PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_parameter_correction import PaperParameterCorrection
from core.domain.paper_plan import (
    BlockRecommendation,
    ConfigurationHint,
    ConnectionHint,
    ModelBuildStep,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import PaperSpec

MISSING_VALUE_SENTINEL: str = "null"
PLAN_EVIDENCE_SOURCE_REF_FIELD: str = "source_ref"
MissingBindingModel = MissingParameterBinding
_STEP_ID_RE = re.compile(r"^STEP-\d{3}$")
_CONFIG_REDLINE_TARGETS = frozenset({"solver", "powergui", "simulation"})
_MULTIPLIER_OR_TUNING_RE = re.compile(
    r"("
    r"(增大|增加|减小|降低|提高|调高|调低|increase|decrease|raise|lower)"
    r"\s*[-+]?\d+(?:\.\d+)?\s*(%|倍|x|×)"
    r"|[-+]?\d+(?:\.\d+)?\s*(%|倍|x|×)"
    r"|(?:最优|最佳|optimal|推荐设为|recommend(?:ed)?)\s*[:：]?\s*[-+]?\d"
    r")",
    re.IGNORECASE,
)
_NUMBER_TOKEN_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.IGNORECASE)


class BuildStepsStructuredError(MxaError):
    """Structured build-step generation failed and may fall back to legacy steps."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class BuildStepsJsonParseError(BuildStepsStructuredError):
    """BuildStepPlanner returned invalid JSON."""


class BuildStepsDtoValidationError(BuildStepsStructuredError):
    """BuildStepPlanner JSON did not match the private draft DTO."""


class BuildStepsSemanticValidationError(BuildStepsStructuredError):
    """Build steps failed deterministic semantic validation."""


class BuildStepsRedLineError(BuildStepsStructuredError):
    """Build steps leaked forbidden values or tuning instructions."""


class BuildStepsEvidenceError(BuildStepsStructuredError):
    """Build-step evidence failed generate-time double-source validation."""


class _UserSuppliedResponseLike(Protocol):
    prompt_id: str


@dataclass(frozen=True)
class ModelBuildStepDraft:
    """Private draft shape parsed from BuildStepPlanner output before display_text exists."""

    step_id: str
    title: str
    intent: str
    block_refs: list[StepBlockRef]
    parameter_refs: list[ParameterMappingRef]
    connection_hints: list[ConnectionHint]
    configuration_hints: list[ConfigurationHint]
    depends_on: list[str]
    evidence: list[PaperEvidenceEntry]


@dataclass(frozen=True)
class PlanEvidenceSourceRef:
    """Backend-owned source tag that plan LLM roles may cite transiently."""

    source_ref: str
    document_id: str
    locator_kind: Literal["paper_section_id", "equation_id", "figure_id"]
    locator_id: str
    filename: str
    excerpt: str


@dataclass(frozen=True)
class UserEvidenceRef:
    """Resolved user evidence key used by downstream provenance consumers."""

    kind: UserEvidenceAction
    key: str


class EvidenceTagger:
    """Validate and create evidence entries without inventing locators."""

    def validate_for_spec(
        self,
        evidence: list[PaperEvidenceEntry],
        spec: PaperSpec,
    ) -> None:
        """Validate double-source invariants and PaperSpec locator whitelists."""

        allowed_sections = {
            (entry.document_id, entry.paper_section_id)
            for entry in spec.evidence
            if entry.document_id is not None and entry.paper_section_id is not None
        }
        allowed_equations = {
            (entry.document_id, entry.equation_id)
            for entry in spec.equations
            if entry.document_id is not None
        }
        allowed_figures = {
            (entry.document_id, entry.figure_id)
            for entry in spec.figure_locations
            if entry.document_id is not None
        }
        allowed_document_ids = {document.document_id for document in spec.documents}

        for entry in evidence:
            self._validate_source_invariants(entry, allowed_document_ids)
            self._validate_locator_whitelist(
                entry=entry,
                allowed_sections=allowed_sections,
                allowed_equations=allowed_equations,
                allowed_figures=allowed_figures,
            )

    def validate_for_record(
        self,
        evidence: list[PaperEvidenceEntry],
        record: PaperPlanRecord,
        *,
        allowed_user_evidence_refs: set[UserEvidenceRef] | None = None,
    ) -> None:
        """Validate evidence against PaperSpec and resolved user-supplied provenance."""

        self.validate_for_spec(evidence, record.spec)
        resolved_refs = (
            resolved_user_evidence_refs(record, [])
            if allowed_user_evidence_refs is None
            else allowed_user_evidence_refs
        )
        plan_user_evidence_refs = _plan_user_evidence_refs(record.plan.evidence)
        for entry in evidence:
            if entry.source is not EvidenceSource.USER_SUPPLIED:
                continue
            ref = _user_evidence_ref(entry)
            if ref is None:
                _raise_plan_generation_error("user_evidence_unresolved")
            if ref not in resolved_refs:
                if ref.kind is UserEvidenceAction.CORRECT_EXTRACTED:
                    _raise_plan_generation_error("user_evidence_unresolved_correction")
                _raise_plan_generation_error("user_evidence_unresolved_prompt")
            if ref not in plan_user_evidence_refs:
                _raise_plan_generation_error("user_evidence_missing_from_plan")

    def tag_user_supplied(
        self,
        response: _UserSuppliedResponseLike,
        missing_prompt: MissingParameterPrompt,
    ) -> PaperEvidenceEntry:
        """Create a user-supplied evidence entry for a matched missing prompt."""

        if response.prompt_id != missing_prompt.prompt_id:
            raise PaperUserSupplyError("prompt_id_mismatch")
        return PaperEvidenceEntry(
            source=EvidenceSource.USER_SUPPLIED,
            document_id=None,
            paper_section_id=None,
            equation_id=None,
            figure_id=None,
            excerpt=None,
            missing_param_prompt_id=missing_prompt.prompt_id,
            user_action=UserEvidenceAction.FILL_MISSING,
        )

    def _validate_source_invariants(
        self,
        entry: PaperEvidenceEntry,
        allowed_document_ids: set[str],
    ) -> None:
        if entry.source is EvidenceSource.DOCUMENT_EXTRACTED:
            if entry.document_id not in allowed_document_ids:
                _raise_plan_generation_error("document_evidence_document_id_invalid")
            if not any((entry.paper_section_id, entry.equation_id, entry.figure_id)):
                _raise_plan_generation_error("document_evidence_missing_locator")
            if not entry.excerpt or len(entry.excerpt) > 300:
                _raise_plan_generation_error("document_evidence_invalid_excerpt")
            if entry.missing_param_prompt_id is not None:
                _raise_plan_generation_error("document_evidence_has_missing_prompt")
            if entry.user_action is not None:
                _raise_plan_generation_error("document_evidence_has_user_action")
            if entry.parameter_correction_id is not None:
                _raise_plan_generation_error("document_evidence_has_correction_id")
            if entry.correction_param_key is not None:
                _raise_plan_generation_error("document_evidence_has_correction_field")
            return

        if entry.source is EvidenceSource.USER_SUPPLIED:
            if entry.document_id is not None:
                _raise_plan_generation_error("user_evidence_document_id_not_null")
            if any((entry.paper_section_id, entry.equation_id, entry.figure_id)):
                _raise_plan_generation_error("user_evidence_has_locator")
            if entry.excerpt is not None:
                _raise_plan_generation_error("user_evidence_has_excerpt")
            if entry.user_action is None:
                _raise_plan_generation_error("user_evidence_missing_action")
            if entry.user_action is UserEvidenceAction.FILL_MISSING:
                if entry.missing_param_prompt_id is None:
                    _raise_plan_generation_error("user_evidence_missing_prompt_id")
                if entry.parameter_correction_id is not None:
                    _raise_plan_generation_error("user_evidence_has_correction_id")
                if entry.correction_param_key is not None:
                    _raise_plan_generation_error("user_evidence_has_correction_field")
                return
            if entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED:
                if entry.missing_param_prompt_id is not None:
                    _raise_plan_generation_error("user_evidence_has_missing_prompt_id")
                if entry.parameter_correction_id is None:
                    _raise_plan_generation_error("user_evidence_missing_correction_id")
                return
            return

        _raise_plan_generation_error("unknown_evidence_source")

    def _validate_locator_whitelist(
        self,
        *,
        entry: PaperEvidenceEntry,
        allowed_sections: set[tuple[str, str]],
        allowed_equations: set[tuple[str, str]],
        allowed_figures: set[tuple[str, str]],
    ) -> None:
        if entry.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            return
        assert entry.document_id is not None
        if (
            entry.paper_section_id is not None
            and (entry.document_id, entry.paper_section_id) not in allowed_sections
        ):
            _raise_plan_generation_error("paper_section_id_outside_whitelist")
        if (
            entry.equation_id is not None
            and (entry.document_id, entry.equation_id) not in allowed_equations
        ):
            _raise_plan_generation_error("equation_id_outside_whitelist")
        if (
            entry.figure_id is not None
            and (entry.document_id, entry.figure_id) not in allowed_figures
        ):
            _raise_plan_generation_error("figure_id_outside_whitelist")


def build_plan_evidence_source_refs(spec: PaperSpec) -> list[PlanEvidenceSourceRef]:
    """Build backend-owned transient source tags for plan LLM evidence citation."""

    filename_by_document_id = {
        document.document_id: document.filename for document in spec.documents
    }
    sources: list[PlanEvidenceSourceRef] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(
        *,
        document_id: str | None,
        locator_kind: Literal["paper_section_id", "equation_id", "figure_id"],
        locator_id: str | None,
        excerpt: str | None,
    ) -> None:
        if document_id is None or locator_id is None:
            return
        cleaned_excerpt = _source_ref_excerpt(excerpt)
        if cleaned_excerpt is None:
            return
        key = (document_id, locator_kind, locator_id, cleaned_excerpt)
        if key in seen:
            return
        seen.add(key)
        sources.append(
            PlanEvidenceSourceRef(
                source_ref=f"REF-{len(sources) + 1:03d}",
                document_id=document_id,
                locator_kind=locator_kind,
                locator_id=locator_id,
                filename=filename_by_document_id.get(document_id, document_id),
                excerpt=cleaned_excerpt,
            )
        )

    for entry in spec.evidence:
        if entry.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            continue
        add(
            document_id=entry.document_id,
            locator_kind="paper_section_id",
            locator_id=entry.paper_section_id,
            excerpt=entry.excerpt,
        )
        add(
            document_id=entry.document_id,
            locator_kind="equation_id",
            locator_id=entry.equation_id,
            excerpt=entry.excerpt,
        )
        add(
            document_id=entry.document_id,
            locator_kind="figure_id",
            locator_id=entry.figure_id,
            excerpt=entry.excerpt,
        )
    for equation in spec.equations:
        add(
            document_id=equation.document_id,
            locator_kind="equation_id",
            locator_id=equation.equation_id,
            excerpt=equation.latex_or_text,
        )
    for figure in spec.figure_locations:
        add(
            document_id=figure.document_id,
            locator_kind="figure_id",
            locator_id=figure.figure_id,
            excerpt=figure.caption,
        )
    return sources


def apply_plan_evidence_reference_bridge(
    payload: dict[str, Any],
    source_refs: list[PlanEvidenceSourceRef],
) -> dict[str, Any]:
    """Resolve transient source_ref tags to persisted canonical evidence fields."""

    index = {entry.source_ref: entry for entry in source_refs}
    bridged = _visit_plan_evidence_payloads(copy.deepcopy(payload), index)
    if not isinstance(bridged, dict):
        return {}
    return bridged


def _visit_plan_evidence_payloads(
    value: Any,
    index: dict[str, PlanEvidenceSourceRef],
) -> Any:
    if isinstance(value, list):
        items_result: list[Any] = []
        for item in value:
            visited = _visit_plan_evidence_payloads(item, index)
            if visited is not _DROP_EVIDENCE:
                items_result.append(visited)
        return items_result
    if not isinstance(value, dict):
        return value

    object_result: dict[str, Any] = {}
    for key, item in value.items():
        visited = _visit_plan_evidence_payloads(item, index)
        if visited is not _DROP_EVIDENCE:
            object_result[key] = visited
    if _looks_like_plan_evidence_payload(object_result):
        return _bridge_plan_evidence_payload(object_result, index)
    return object_result


def _bridge_plan_evidence_payload(
    payload: dict[str, Any],
    index: dict[str, PlanEvidenceSourceRef],
) -> dict[str, Any] | object:
    source = payload.get("source")
    if source in (EvidenceSource.USER_SUPPLIED, EvidenceSource.USER_SUPPLIED.value):
        result = dict(payload)
        result.pop(PLAN_EVIDENCE_SOURCE_REF_FIELD, None)
        result["document_id"] = None
        result.setdefault("user_action", UserEvidenceAction.FILL_MISSING.value)
        return result
    if source not in (EvidenceSource.DOCUMENT_EXTRACTED, EvidenceSource.DOCUMENT_EXTRACTED.value):
        return payload

    source_ref = payload.get(PLAN_EVIDENCE_SOURCE_REF_FIELD)
    if not isinstance(source_ref, str):
        return _DROP_EVIDENCE
    source_entry = index.get(source_ref)
    if source_entry is None:
        return _DROP_EVIDENCE

    result = dict(payload)
    result.pop(PLAN_EVIDENCE_SOURCE_REF_FIELD, None)
    result["document_id"] = source_entry.document_id
    result["paper_section_id"] = None
    result["equation_id"] = None
    result["figure_id"] = None
    result[source_entry.locator_kind] = source_entry.locator_id
    result["excerpt"] = source_entry.excerpt
    result["missing_param_prompt_id"] = None
    return result


_PLAN_EVIDENCE_KEYS = frozenset(
    {
        "paper_section_id",
        "equation_id",
        "figure_id",
        "excerpt",
        "missing_param_prompt_id",
        "user_action",
        "parameter_correction_id",
        "correction_param_key",
        PLAN_EVIDENCE_SOURCE_REF_FIELD,
    }
)
_DROP_EVIDENCE = object()


def _looks_like_plan_evidence_payload(value: dict[str, Any]) -> bool:
    return "source" in value and any(key in value for key in _PLAN_EVIDENCE_KEYS)


def _source_ref_excerpt(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    return cleaned[:300]


class PlanAssembler:
    """Merge LLM role outputs and produce private missing bindings."""

    def merge(
        self,
        plan_composer_output: ModelGenerationPlan,
        subsystem_steps: list[str],
        mscript: str | None,
        missing_prompts: list[MissingParameterPrompt],
        paper_id: str,
        build_steps: list[ModelBuildStep] | None = None,
    ) -> tuple[ModelGenerationPlan, list[MissingBindingModel]]:
        bindings = [
            self._binding_for_prompt(plan_composer_output.parameter_mapping, missing_prompt)
            for missing_prompt in missing_prompts
        ]
        plan = replace(
            plan_composer_output,
            plan_id=f"PLAN-{paper_id}",
            paper_spec_id=paper_id,
            subsystem_breakdown=list(subsystem_steps),
            m_script_skeleton=mscript,
            build_steps=build_steps,
        )
        return plan, bindings

    def validate_and_derive_build_steps(
        self,
        draft_steps: list[ModelBuildStepDraft],
        parameter_mapping: list[ParameterMapping],
        block_recommendations: list[BlockRecommendation],
    ) -> list[ModelBuildStep]:
        """Validate draft build steps and derive display_text from safe fields."""

        if not draft_steps:
            _raise_semantic("empty_steps")
        if len(draft_steps) < 3 or len(draft_steps) > 10:
            _raise_semantic("build_steps_length_invalid")

        ordered_steps = self._topologically_order_steps(draft_steps)
        self._validate_parameter_mapping_unique(parameter_mapping)
        mapping_key_counts = Counter(
            (mapping.paper_param_name, mapping.model_param_name) for mapping in parameter_mapping
        )
        recommendation_index = self._build_recommendation_index(block_recommendations)

        self._validate_operable_steps(ordered_steps)
        self._validate_parameter_refs(ordered_steps, mapping_key_counts)
        self._validate_block_refs(ordered_steps, recommendation_index)
        self._validate_block_ref_ids(ordered_steps)
        self._validate_connection_visibility(ordered_steps)
        self._validate_recommendation_coverage(ordered_steps, recommendation_index)
        self._validate_redlines(ordered_steps, parameter_mapping)

        build_steps: list[ModelBuildStep] = []
        for step in ordered_steps:
            display_text = self._derive_display_text(step)
            derived = ModelBuildStep(
                step_id=step.step_id,
                title=step.title,
                intent=step.intent,
                block_refs=list(step.block_refs),
                parameter_refs=list(step.parameter_refs),
                connection_hints=list(step.connection_hints),
                configuration_hints=list(step.configuration_hints),
                depends_on=list(step.depends_on),
                evidence=list(step.evidence),
                display_text=display_text,
            )
            build_steps.append(derived)
        return build_steps

    def _topologically_order_steps(
        self,
        draft_steps: list[ModelBuildStepDraft],
    ) -> list[ModelBuildStepDraft]:
        step_ids = [step.step_id for step in draft_steps]
        if any(_STEP_ID_RE.fullmatch(step_id) is None for step_id in step_ids):
            _raise_semantic("step_id_invalid")
        if any(count != 1 for count in Counter(step_ids).values()):
            _raise_semantic("step_id_duplicate")

        by_id = {step.step_id: step for step in draft_steps}
        original_index = {step.step_id: index for index, step in enumerate(draft_steps)}
        for step in draft_steps:
            for dependency in step.depends_on:
                if dependency not in by_id:
                    _raise_semantic("depends_on_unknown")
                if dependency == step.step_id:
                    _raise_semantic("depends_on_self")

        remaining = set(step_ids)
        ordered: list[ModelBuildStepDraft] = []
        while remaining:
            ready = [
                step_id
                for step_id in remaining
                if all(dependency not in remaining for dependency in by_id[step_id].depends_on)
            ]
            if not ready:
                _raise_semantic("depends_on_cycle")
            ready.sort(key=original_index.__getitem__)
            next_id = ready[0]
            remaining.remove(next_id)
            ordered.append(by_id[next_id])

        seen: set[str] = set()
        for step in ordered:
            if any(dependency not in seen for dependency in step.depends_on):
                _raise_semantic("depends_on_not_prior")
            seen.add(step.step_id)
        return ordered

    def _validate_parameter_mapping_unique(
        self,
        parameter_mapping: list[ParameterMapping],
    ) -> None:
        key_counts = Counter(
            (mapping.paper_param_name, mapping.model_param_name) for mapping in parameter_mapping
        )
        if any(count != 1 for count in key_counts.values()):
            _raise_semantic("parameter_mapping_duplicate")

    def _build_recommendation_index(
        self,
        block_recommendations: list[BlockRecommendation],
    ) -> dict[tuple[str, str], str]:
        key_counts = Counter(_block_recommendation_key(block) for block in block_recommendations)
        if any(count != 1 for count in key_counts.values()):
            _raise_semantic("br_ambiguous")
        return {
            _block_recommendation_key(block): f"BR-{index:03d}"
            for index, block in enumerate(block_recommendations, start=1)
        }

    def _validate_operable_steps(self, steps: list[ModelBuildStepDraft]) -> None:
        for step in steps:
            if not any(
                (
                    step.block_refs,
                    step.parameter_refs,
                    step.connection_hints,
                    step.configuration_hints,
                )
            ):
                _raise_semantic("step_not_operable")

    def _validate_parameter_refs(
        self,
        steps: list[ModelBuildStepDraft],
        mapping_key_counts: Counter[tuple[str, str]],
    ) -> None:
        for step in steps:
            for parameter_ref in step.parameter_refs:
                key = (parameter_ref.paper_param_name, parameter_ref.model_param_name)
                if mapping_key_counts.get(key, 0) != 1:
                    _raise_semantic("parameter_ref_no_match")

    def _validate_block_refs(
        self,
        steps: list[ModelBuildStepDraft],
        recommendation_index: dict[tuple[str, str], str],
    ) -> None:
        for step in steps:
            for block_ref in step.block_refs:
                key = _block_ref_key(block_ref)
                if key not in recommendation_index:
                    _raise_semantic("br_no_match")

    def _validate_block_ref_ids(self, steps: list[ModelBuildStepDraft]) -> None:
        block_ref_ids = [block_ref.block_ref_id for step in steps for block_ref in step.block_refs]
        if any(count != 1 for count in Counter(block_ref_ids).values()):
            _raise_semantic("block_ref_id_duplicate")

    def _validate_connection_visibility(self, steps: list[ModelBuildStepDraft]) -> None:
        by_id = {step.step_id: step for step in steps}
        block_refs_by_step = {
            step.step_id: [block_ref.block_ref_id for block_ref in step.block_refs]
            for step in steps
        }

        for step in steps:
            visible_steps = {step.step_id, *self._dependency_closure(step.step_id, by_id)}
            visible_refs = [
                block_ref_id
                for visible_step_id in visible_steps
                for block_ref_id in block_refs_by_step[visible_step_id]
            ]
            visible_counts = Counter(visible_refs)
            for connection_hint in step.connection_hints:
                for block_ref_id in (
                    connection_hint.from_block_ref,
                    connection_hint.to_block_ref,
                ):
                    if visible_counts.get(block_ref_id, 0) != 1:
                        _raise_semantic("connection_ref_not_visible")

    def _dependency_closure(
        self,
        step_id: str,
        by_id: dict[str, ModelBuildStepDraft],
    ) -> frozenset[str]:
        result: set[str] = set()
        stack = list(by_id[step_id].depends_on)
        while stack:
            dependency = stack.pop()
            if dependency in result:
                continue
            result.add(dependency)
            stack.extend(by_id[dependency].depends_on)
        return frozenset(result)

    def _validate_recommendation_coverage(
        self,
        steps: list[ModelBuildStepDraft],
        recommendation_index: dict[tuple[str, str], str],
    ) -> None:
        coverage_set = set(recommendation_index)
        if not coverage_set:
            return
        covered = {_block_ref_key(block_ref) for step in steps for block_ref in step.block_refs}
        if coverage_set - covered:
            _raise_semantic("coverage_missing")

    def _validate_redlines(
        self,
        steps: list[ModelBuildStepDraft],
        parameter_mapping: list[ParameterMapping],
    ) -> None:
        for step in steps:
            self._validate_text_for_redline(
                step.title,
                parameter_mapping,
                allow_config_values=False,
            )
            self._validate_text_for_redline(
                step.intent,
                parameter_mapping,
                allow_config_values=False,
            )
            for block_ref in step.block_refs:
                self._validate_text_for_redline(
                    block_ref.purpose,
                    parameter_mapping,
                    allow_config_values=False,
                )
            for connection_hint in step.connection_hints:
                if connection_hint.signal_meaning is not None:
                    self._validate_text_for_redline(
                        connection_hint.signal_meaning,
                        parameter_mapping,
                        allow_config_values=False,
                    )
            for configuration_hint in step.configuration_hints:
                self._validate_config_text_for_redline(
                    configuration_hint.target,
                    parameter_mapping,
                )
                if configuration_hint.setting_name is not None:
                    self._validate_config_text_for_redline(
                        configuration_hint.setting_name,
                        parameter_mapping,
                    )
                self._validate_text_for_redline(
                    configuration_hint.instruction,
                    parameter_mapping,
                    allow_config_values=_is_allowed_config_hint(
                        configuration_hint,
                        parameter_mapping,
                    ),
                )

    def _validate_text_for_redline(
        self,
        text: str,
        parameter_mapping: list[ParameterMapping],
        *,
        allow_config_values: bool,
    ) -> None:
        if _MULTIPLIER_OR_TUNING_RE.search(text) and not allow_config_values:
            _raise_redline("tuning_value_leak")

        for mapping in parameter_mapping:
            if mapping.value == MISSING_VALUE_SENTINEL:
                continue
            if allow_config_values:
                continue
            if _text_leaks_mapping_value(text, mapping):
                _raise_redline("parameter_value_leak")

    def _validate_config_text_for_redline(
        self,
        text: str,
        parameter_mapping: list[ParameterMapping],
    ) -> None:
        for mapping in parameter_mapping:
            if mapping.value == MISSING_VALUE_SENTINEL:
                continue
            if _text_leaks_mapping_value(text, mapping):
                _raise_redline("parameter_value_leak")

    def _derive_display_text(self, step: ModelBuildStepDraft) -> str:
        parts = [
            f"{_clean_text(step.step_id)} {_clean_text(step.title)}",
            _clean_text(step.intent),
        ]
        if step.block_refs:
            blocks = "; ".join(
                f"{_clean_text(block.block_type)} for {_clean_text(block.purpose)}"
                for block in step.block_refs
            )
            parts.append(f"Blocks: {blocks}")
        if step.parameter_refs:
            parameters = "; ".join(
                f"{_clean_text(ref.paper_param_name)} -> {_clean_text(ref.model_param_name)}"
                for ref in step.parameter_refs
            )
            parts.append(f"Parameters: {parameters}")
        signal_meanings = [
            _clean_text(connection.signal_meaning)
            for connection in step.connection_hints
            if connection.signal_meaning is not None
        ]
        if signal_meanings:
            parts.append(f"Signals: {'; '.join(signal_meanings)}")
        if step.configuration_hints:
            configs = "; ".join(
                ".".join(
                    part
                    for part in (
                        _clean_text(hint.target),
                        _clean_text(hint.setting_name),
                    )
                    if part
                )
                for hint in step.configuration_hints
            )
            parts.append(f"Configure: {configs}")
        return " | ".join(part for part in parts if part)

    def _binding_for_prompt(
        self,
        mappings: list[ParameterMapping],
        missing_prompt: MissingParameterPrompt,
    ) -> MissingBindingModel:
        matches = [
            mapping
            for mapping in mappings
            if mapping.value == MISSING_VALUE_SENTINEL
            and mapping.paper_param_name == missing_prompt.parameter_name
        ]
        if not matches:
            _raise_plan_generation_error("missing_binding_not_found")
        if len(matches) > 1:
            _raise_plan_generation_error("missing_binding_ambiguous")

        mapping = matches[0]
        return MissingBindingModel(
            prompt_id=missing_prompt.prompt_id,
            paper_param_name=mapping.paper_param_name,
            model_param_name=mapping.model_param_name,
        )


def resolved_prompt_ids(record: PaperPlanRecord) -> frozenset[str]:
    """Return prompt IDs that are uniquely bound, filled, and evidenced."""

    binding_counts = Counter(binding.prompt_id for binding in record.missing_bindings)
    resolved: list[str] = []
    for binding in record.missing_bindings:
        if binding_counts[binding.prompt_id] != 1:
            continue
        matches = [
            mapping
            for mapping in record.plan.parameter_mapping
            if mapping.paper_param_name == binding.paper_param_name
            and mapping.model_param_name == binding.model_param_name
        ]
        if len(matches) != 1:
            continue
        mapping = matches[0]
        if mapping.value == MISSING_VALUE_SENTINEL:
            continue
        if mapping.source is not EvidenceSource.USER_SUPPLIED:
            continue
        if not any(
            entry.source is EvidenceSource.USER_SUPPLIED
            and entry.user_action is UserEvidenceAction.FILL_MISSING
            and entry.missing_param_prompt_id == binding.prompt_id
            for entry in record.plan.evidence
        ):
            continue
        resolved.append(binding.prompt_id)
    return frozenset(resolved)


def resolved_user_evidence_refs(
    record: PaperPlanRecord,
    corrections: list[PaperParameterCorrection],
) -> set[UserEvidenceRef]:
    """Return user-supplied evidence refs that still resolve in the current record."""

    refs = {
        UserEvidenceRef(kind=UserEvidenceAction.FILL_MISSING, key=prompt_id)
        for prompt_id in resolved_prompt_ids(record)
    }
    corrections_by_id = {
        correction.correction_id: correction
        for correction in corrections
        if correction.paper_id == record.paper_id
    }
    for entry in record.plan.evidence:
        if entry.source is not EvidenceSource.USER_SUPPLIED:
            continue
        if entry.user_action is not UserEvidenceAction.CORRECT_EXTRACTED:
            continue
        if entry.parameter_correction_id is None:
            continue
        correction = corrections_by_id.get(entry.parameter_correction_id)
        if correction is None:
            continue
        if not _correction_target_matches_plan(record, correction):
            continue
        refs.add(
            UserEvidenceRef(
                kind=UserEvidenceAction.CORRECT_EXTRACTED,
                key=correction.correction_id,
            )
        )
    return refs


def _correction_target_matches_plan(
    record: PaperPlanRecord,
    correction: PaperParameterCorrection,
) -> bool:
    target = correction.plan_target
    if target.plan_mapping_index < 0:
        return False
    if target.plan_mapping_index >= len(record.plan.parameter_mapping):
        return False
    mapping = record.plan.parameter_mapping[target.plan_mapping_index]
    expected_key = f"{target.paper_param_name}::{target.model_param_name}"
    return (
        correction.param_key == expected_key
        and mapping.paper_param_name == target.paper_param_name
        and mapping.model_param_name == target.model_param_name
        and mapping.source is EvidenceSource.USER_SUPPLIED
    )


def _plan_user_evidence_refs(evidence: list[PaperEvidenceEntry]) -> set[UserEvidenceRef]:
    refs: set[UserEvidenceRef] = set()
    for entry in evidence:
        ref = _user_evidence_ref(entry)
        if ref is not None:
            refs.add(ref)
    return refs


def _user_evidence_ref(entry: PaperEvidenceEntry) -> UserEvidenceRef | None:
    if entry.source is not EvidenceSource.USER_SUPPLIED:
        return None
    if (
        entry.user_action is UserEvidenceAction.FILL_MISSING
        and entry.missing_param_prompt_id is not None
    ):
        return UserEvidenceRef(
            kind=UserEvidenceAction.FILL_MISSING,
            key=entry.missing_param_prompt_id,
        )
    if (
        entry.user_action is UserEvidenceAction.CORRECT_EXTRACTED
        and entry.parameter_correction_id is not None
    ):
        return UserEvidenceRef(
            kind=UserEvidenceAction.CORRECT_EXTRACTED,
            key=entry.parameter_correction_id,
        )
    return None


def validate_build_step_evidence_for_spec(
    evidence: list[PaperEvidenceEntry],
    spec: PaperSpec,
    *,
    allowed_user_prompt_ids: frozenset[str],
    allowed_user_evidence_refs: set[UserEvidenceRef] | None = None,
) -> None:
    """Validate build-step evidence with explicit generate-time user evidence allowlist."""

    try:
        EvidenceTagger().validate_for_spec(evidence, spec)
    except PaperPlanGenerationError as exc:
        reason = exc.reason_code or "evidence_invalid"
        raise BuildStepsEvidenceError(reason) from None

    allowed_refs = allowed_user_evidence_refs or set()
    for entry in evidence:
        if entry.source is not EvidenceSource.USER_SUPPLIED:
            continue
        if entry.user_action is UserEvidenceAction.FILL_MISSING:
            if entry.missing_param_prompt_id not in allowed_user_prompt_ids:
                raise BuildStepsEvidenceError("user_supplied_evidence_not_allowed")
            continue
        ref = _user_evidence_ref(entry)
        if ref is None or ref not in allowed_refs:
            raise BuildStepsEvidenceError("user_supplied_evidence_not_allowed")


def _block_recommendation_key(block: BlockRecommendation) -> tuple[str, str]:
    return (_normalized(block.block_type), _normalized(block.purpose))


def _block_ref_key(block_ref: StepBlockRef) -> tuple[str, str]:
    return (_normalized(block_ref.block_type), _normalized(block_ref.purpose))


def _normalized(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _is_allowed_config_hint(
    hint: ConfigurationHint,
    parameter_mapping: list[ParameterMapping],
) -> bool:
    if _normalized(hint.target) not in _CONFIG_REDLINE_TARGETS:
        return False
    setting_name = _normalized(hint.setting_name)
    if not setting_name:
        return True
    return not any(
        _parameter_setting_name_matches(setting_name, mapping) for mapping in parameter_mapping
    )


def _parameter_setting_name_matches(setting_name: str, mapping: ParameterMapping) -> bool:
    names = (
        _normalized(mapping.paper_param_name),
        _normalized(mapping.model_param_name),
    )
    return any(
        name and (setting_name == name or setting_name in name or name in setting_name)
        for name in names
    )


def _parameter_name_and_value_nearby(text: str, mapping: ParameterMapping) -> bool:
    lowered = text.casefold()
    value = str(mapping.value).casefold().strip()
    if not value:
        return False
    names = [
        name.casefold().strip()
        for name in (mapping.paper_param_name, mapping.model_param_name)
        if name.strip()
    ]
    for name in names:
        for start in _label_starts(lowered, name):
            window = lowered[max(0, start - 40) : start + len(name) + 40]
            if _contains_value_literal(window, value, allow_short_integer=True):
                return True
    return False


def _text_leaks_mapping_value(
    text: str,
    mapping: ParameterMapping,
) -> bool:
    if _parameter_name_and_value_nearby(text, mapping):
        return True
    if _contains_value_literal(text, mapping.value, allow_short_integer=False):
        return True
    return _contains_numeric_unit_composite(text, mapping)


def _contains_value_literal(
    text: str,
    value: str,
    *,
    allow_short_integer: bool,
) -> bool:
    literal = value.strip()
    if not literal:
        return False
    if not allow_short_integer and not _is_specific_value_literal(literal):
        return False
    return _contains_standalone_literal(text, literal)


def _contains_numeric_unit_composite(text: str, mapping: ParameterMapping) -> bool:
    unit = (mapping.unit or "").strip()
    if not unit or unit in {"—", "-"}:
        return False
    for number in _NUMBER_TOKEN_RE.findall(mapping.value):
        pattern = (
            rf"(?<![A-Za-z0-9_.+-]){re.escape(number)}\s*" rf"{re.escape(unit)}(?![A-Za-z0-9_])"
        )
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def _is_specific_value_literal(value: str) -> bool:
    if re.fullmatch(r"[-+]?\d+", value):
        digits = value.removeprefix("+").removeprefix("-")
        return len(digits) >= 3
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:e[-+]?\d+)?", value, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"[-+]?\d+e[-+]?\d+", value, flags=re.IGNORECASE):
        return True
    return (
        len(_NUMBER_TOKEN_RE.findall(value)) >= 2
        and re.search(
            r"[*/()]|pi|π",
            value,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _contains_standalone_literal(text: str, literal: str) -> bool:
    if re.search(r"[A-Za-z0-9]", literal):
        if re.fullmatch(
            r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?",
            literal,
            flags=re.IGNORECASE,
        ):
            pattern = rf"(?<![A-Za-z0-9_.+-]){re.escape(literal)}(?![A-Za-z0-9_+-]|\.\d)"
        else:
            pattern = rf"(?<![A-Za-z0-9_.+-]){re.escape(literal)}(?![A-Za-z0-9_.+-])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return literal in text


def _label_starts(text: str, label: str) -> list[int]:
    if re.search(r"[A-Za-z0-9]", label):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(label)}(?![A-Za-z0-9_])"
        return [match.start() for match in re.finditer(pattern, text, flags=re.IGNORECASE)]

    starts: list[int] = []
    start = text.find(label)
    while start != -1:
        starts.append(start)
        start = text.find(label, start + 1)
    return starts


def _raise_plan_generation_error(reason_code: str) -> NoReturn:
    raise PaperPlanGenerationError(
        reason_code,
        reason_code=reason_code,
        locator_namespace=_locator_namespace_for_reason(reason_code),
    )


def _raise_semantic(reason_code: str) -> NoReturn:
    raise BuildStepsSemanticValidationError(reason_code)


def _raise_redline(reason_code: str) -> NoReturn:
    raise BuildStepsRedLineError(reason_code)


def _locator_namespace_for_reason(reason_code: str) -> str | None:
    if reason_code in {"equation_locator_invalid", "equation_id_outside_whitelist"}:
        return "equation_id"
    if reason_code in {"paper_section_locator_invalid", "paper_section_id_outside_whitelist"}:
        return "paper_section_id"
    if reason_code in {"figure_locator_invalid", "figure_id_outside_whitelist"}:
        return "figure_id"
    return None
