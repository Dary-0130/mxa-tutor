"""Feature-private helpers for paper plan generation."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import NoReturn, Protocol

from core.domain.exceptions import MxaError, PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
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


class EvidenceTagger:
    """Validate and create evidence entries without inventing locators."""

    def validate_for_spec(
        self,
        evidence: list[PaperEvidenceEntry],
        spec: PaperSpec,
    ) -> None:
        """Validate double-source invariants and PaperSpec locator whitelists."""

        allowed_sections = {
            entry.paper_section_id for entry in spec.evidence if entry.paper_section_id is not None
        }
        allowed_equations = {entry.equation_id for entry in spec.equations}
        allowed_figures = {entry.figure_id for entry in spec.figure_locations}

        for entry in evidence:
            self._validate_source_invariants(entry)
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
    ) -> None:
        """Validate evidence against PaperSpec and resolved user-supplied provenance."""

        self.validate_for_spec(evidence, record.spec)
        resolved_ids = resolved_prompt_ids(record)
        plan_user_evidence_ids = {
            entry.missing_param_prompt_id
            for entry in record.plan.evidence
            if entry.source is EvidenceSource.USER_SUPPLIED
            and entry.missing_param_prompt_id is not None
        }
        for entry in evidence:
            if entry.source is not EvidenceSource.USER_SUPPLIED:
                continue
            if entry.missing_param_prompt_id not in resolved_ids:
                raise PaperPlanGenerationError("user_evidence_unresolved_prompt")
            if entry.missing_param_prompt_id not in plan_user_evidence_ids:
                raise PaperPlanGenerationError("user_evidence_missing_from_plan")

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
            paper_section_id=None,
            equation_id=None,
            figure_id=None,
            excerpt=None,
            missing_param_prompt_id=missing_prompt.prompt_id,
        )

    def _validate_source_invariants(self, entry: PaperEvidenceEntry) -> None:
        if entry.source is EvidenceSource.DOCUMENT_EXTRACTED:
            if not any((entry.paper_section_id, entry.equation_id, entry.figure_id)):
                raise PaperPlanGenerationError("document_evidence_missing_locator")
            if not entry.excerpt or len(entry.excerpt) > 300:
                raise PaperPlanGenerationError("document_evidence_invalid_excerpt")
            if entry.missing_param_prompt_id is not None:
                raise PaperPlanGenerationError("document_evidence_has_missing_prompt")
            return

        if entry.source is EvidenceSource.USER_SUPPLIED:
            if any((entry.paper_section_id, entry.equation_id, entry.figure_id)):
                raise PaperPlanGenerationError("user_evidence_has_locator")
            if entry.excerpt is not None:
                raise PaperPlanGenerationError("user_evidence_has_excerpt")
            if entry.missing_param_prompt_id is None:
                raise PaperPlanGenerationError("user_evidence_missing_prompt_id")
            return

        raise PaperPlanGenerationError("unknown_evidence_source")

    def _validate_locator_whitelist(
        self,
        *,
        entry: PaperEvidenceEntry,
        allowed_sections: set[str],
        allowed_equations: set[str],
        allowed_figures: set[str],
    ) -> None:
        if entry.paper_section_id is not None and entry.paper_section_id not in allowed_sections:
            raise PaperPlanGenerationError("paper_section_id_outside_whitelist")
        if entry.equation_id is not None and entry.equation_id not in allowed_equations:
            raise PaperPlanGenerationError("equation_id_outside_whitelist")
        if entry.figure_id is not None and entry.figure_id not in allowed_figures:
            raise PaperPlanGenerationError("figure_id_outside_whitelist")


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
            self._validate_text_for_redline(
                display_text,
                parameter_mapping,
                allow_config_values=False,
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
            if _parameter_name_and_value_nearby(text, mapping) and not allow_config_values:
                _raise_redline("parameter_value_leak")
            if allow_config_values:
                continue
            for token in _bare_value_tokens(mapping):
                if _contains_bare_token(text, token):
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
            raise PaperPlanGenerationError("missing_binding_not_found")
        if len(matches) > 1:
            raise PaperPlanGenerationError("missing_binding_ambiguous")

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
            and entry.missing_param_prompt_id == binding.prompt_id
            for entry in record.plan.evidence
        ):
            continue
        resolved.append(binding.prompt_id)
    return frozenset(resolved)


def validate_build_step_evidence_for_spec(
    evidence: list[PaperEvidenceEntry],
    spec: PaperSpec,
    *,
    allowed_user_prompt_ids: frozenset[str],
) -> None:
    """Validate build-step evidence with explicit generate-time user evidence allowlist."""

    try:
        EvidenceTagger().validate_for_spec(evidence, spec)
    except PaperPlanGenerationError as exc:
        reason = str(exc) or "evidence_invalid"
        raise BuildStepsEvidenceError(reason) from None

    for entry in evidence:
        if entry.source is not EvidenceSource.USER_SUPPLIED:
            continue
        if entry.missing_param_prompt_id not in allowed_user_prompt_ids:
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
        start = lowered.find(name)
        while start != -1:
            window = lowered[max(0, start - 40) : start + len(name) + 40]
            if value in window:
                return True
            start = lowered.find(name, start + 1)
    return False


def _bare_value_tokens(mapping: ParameterMapping) -> list[str]:
    tokens = list(_NUMBER_TOKEN_RE.findall(mapping.value))
    if mapping.unit is not None:
        unit = mapping.unit.strip()
        if unit and unit not in {"—", "-"}:
            tokens.append(unit)
    return [token for token in tokens if token]


def _contains_bare_token(text: str, token: str) -> bool:
    if not token:
        return False
    if re.fullmatch(r"[A-Za-z]", token):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    if re.search(r"[A-Za-z0-9]", token):
        pattern = rf"(?<![A-Za-z0-9_.+-]){re.escape(token)}(?![A-Za-z0-9_.+-])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return token in text


def _raise_semantic(reason_code: str) -> NoReturn:
    raise BuildStepsSemanticValidationError(reason_code)


def _raise_redline(reason_code: str) -> NoReturn:
    raise BuildStepsRedLineError(reason_code)
