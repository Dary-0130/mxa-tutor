"""Feature-private helpers for paper plan generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import ModelGenerationPlan, ParameterMapping
from core.domain.paper_spec import PaperSpec

MISSING_VALUE_SENTINEL: str = "null"


@dataclass(frozen=True)
class MissingBindingModel:
    """Private binding from a missing prompt to one parameter mapping."""

    prompt_id: str
    paper_param_name: str
    model_param_name: str


class _UserSuppliedResponseLike(Protocol):
    prompt_id: str


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
        )
        return plan, bindings

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
