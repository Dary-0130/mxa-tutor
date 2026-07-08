"""Merge user-supplied paper parameters into a cached model generation plan."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import ModelGenerationPlan, ParameterMapping
from features.paper.build_guidance_lifecycle import mark_guidance_stale_for_parameter_change
from features.paper.paper_plan_cache import PaperPlanCache, PaperPlanRecord
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
    MissingBindingModel,
)
from features.paper.paper_user_input_schemas import UserSuppliedResponseModel


class UserSupplyService:
    """Merge trusted server-side plan state with user-supplied missing parameters."""

    def __init__(
        self,
        cache: PaperPlanCache,
        evidence_tagger: EvidenceTagger | None = None,
    ) -> None:
        self._cache = cache
        self._evidence_tagger = evidence_tagger or EvidenceTagger()

    async def merge(
        self,
        paper_id: str,
        responses: list[UserSuppliedResponseModel],
    ) -> ModelGenerationPlan:
        record = await self._cache.get(paper_id)
        if record is None:
            raise PaperUserSupplyError("paper_not_found") from None

        plan_copy = deepcopy(record.plan)
        merge_items = self._validate_merge_requests(record, plan_copy, responses)

        for response, missing_prompt, mapping_index in merge_items:
            mapping = plan_copy.parameter_mapping[mapping_index]
            plan_copy.parameter_mapping[mapping_index] = replace(
                mapping,
                value=response.user_supplied_value,
                unit=response.user_supplied_unit,
                source=EvidenceSource.USER_SUPPLIED,
            )
            plan_copy.evidence.append(
                self._evidence_tagger.tag_user_supplied(response, missing_prompt)
            )

        try:
            self._evidence_tagger.validate_for_spec(plan_copy.evidence, record.spec)
        except PaperPlanGenerationError:
            raise PaperUserSupplyError("user_supplied_evidence_invalid") from None

        plan_copy = mark_guidance_stale_for_parameter_change(plan_copy)
        await self._cache.set(
            paper_id,
            PaperPlanRecord(
                paper_id=record.paper_id,
                spec=record.spec,
                plan=plan_copy,
                missing_prompts=record.missing_prompts,
                missing_bindings=record.missing_bindings,
            ),
        )
        return plan_copy

    def _validate_merge_requests(
        self,
        record: PaperPlanRecord,
        plan: ModelGenerationPlan,
        responses: list[UserSuppliedResponseModel],
    ) -> list[tuple[UserSuppliedResponseModel, MissingParameterPrompt, int]]:
        prompts_by_id = {prompt.prompt_id: prompt for prompt in record.missing_prompts}
        bindings_by_id = {binding.prompt_id: binding for binding in record.missing_bindings}
        seen_prompt_ids: set[str] = set()
        merge_items: list[tuple[UserSuppliedResponseModel, MissingParameterPrompt, int]] = []

        for response in responses:
            missing_prompt = prompts_by_id.get(response.prompt_id)
            if missing_prompt is None:
                raise PaperUserSupplyError("prompt_id_not_found") from None
            if response.prompt_id in seen_prompt_ids:
                raise PaperUserSupplyError("prompt_id_duplicated") from None
            seen_prompt_ids.add(response.prompt_id)

            if response.parameter_name != missing_prompt.parameter_name:
                raise PaperUserSupplyError("parameter_name_mismatch") from None

            binding = bindings_by_id.get(response.prompt_id)
            if binding is None:
                raise PaperUserSupplyError("prompt_id_not_found") from None

            mapping_index = self._find_mapping_index(plan.parameter_mapping, binding)
            mapping = plan.parameter_mapping[mapping_index]
            if mapping.value != MISSING_VALUE_SENTINEL:
                raise PaperUserSupplyError("prompt_already_filled") from None

            merge_items.append((response, missing_prompt, mapping_index))

        return merge_items

    def _find_mapping_index(
        self,
        mappings: list[ParameterMapping],
        binding: MissingBindingModel,
    ) -> int:
        for index, mapping in enumerate(mappings):
            if (
                mapping.paper_param_name == binding.paper_param_name
                and mapping.model_param_name == binding.model_param_name
            ):
                return index
        raise PaperUserSupplyError("prompt_id_not_found") from None
