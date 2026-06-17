from __future__ import annotations

import pytest

from core.domain.exceptions import PaperPlanGenerationError, PaperUserSupplyError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import (
    BlockRecommendation,
    ModelGenerationPlan,
    ParameterMapping,
)
from core.domain.paper_spec import EquationEntry, FigureRef, PaperSpec, ParameterEntry
from features.paper.paper_plan_cache import InMemoryPaperPlanCache, PaperPlanRecord
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    EvidenceTagger,
    MissingBindingModel,
)
from features.paper.paper_user_input_schemas import UserSuppliedResponseModel
from features.paper.paper_user_supply_service import UserSupplyService


class FailingValidationEvidenceTagger(EvidenceTagger):
    def validate_for_spec(
        self,
        evidence: list[PaperEvidenceEntry],
        spec: PaperSpec,
    ) -> None:
        _ = evidence, spec
        raise PaperPlanGenerationError("forced_user_side_invariant_failure")


@pytest.mark.asyncio
async def test_merge_fills_sentinel_mappings_and_appends_user_evidence() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    updated = await UserSupplyService(cache).merge("paper-1", [_response()])

    assert updated.parameter_mapping[0] == ParameterMapping(
        paper_param_name="H",
        model_param_name="Synchronous Machine.H",
        value="3.5",
        unit="s",
        source=EvidenceSource.USER_SUPPLIED,
    )
    assert updated.evidence[-1] == PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id="MISS-1",
    )


@pytest.mark.asyncio
async def test_merge_returns_deep_copy_not_mutating_record_in_cache() -> None:
    cache = InMemoryPaperPlanCache()
    original_record = _record()
    await cache.set("paper-1", original_record)

    updated = await UserSupplyService(cache).merge("paper-1", [_response()])
    cached = await cache.get("paper-1")

    assert original_record.plan.parameter_mapping[0].value == MISSING_VALUE_SENTINEL
    assert original_record.plan.evidence == [_document_evidence()]
    assert cached is not None
    assert cached.plan is updated
    assert cached.plan is not original_record.plan


@pytest.mark.asyncio
async def test_merge_raises_when_paper_id_not_in_cache() -> None:
    with pytest.raises(PaperUserSupplyError, match="paper_not_found"):
        await UserSupplyService(InMemoryPaperPlanCache()).merge("missing", [_response()])


@pytest.mark.asyncio
async def test_merge_raises_when_prompt_id_not_in_missing_prompts() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    with pytest.raises(PaperUserSupplyError, match="prompt_id_not_found"):
        await UserSupplyService(cache).merge("paper-1", [_response(prompt_id="MISS-404")])


@pytest.mark.asyncio
async def test_merge_raises_when_prompt_id_duplicated_in_batch() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    with pytest.raises(PaperUserSupplyError, match="prompt_id_duplicated"):
        await UserSupplyService(cache).merge("paper-1", [_response(), _response()])


@pytest.mark.asyncio
async def test_merge_raises_when_parameter_name_mismatch() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    with pytest.raises(PaperUserSupplyError, match="parameter_name_mismatch"):
        await UserSupplyService(cache).merge("paper-1", [_response(parameter_name="Xd")])


@pytest.mark.asyncio
async def test_merge_raises_when_mapping_already_filled() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record(mapping_value="4.0"))

    with pytest.raises(PaperUserSupplyError, match="prompt_already_filled"):
        await UserSupplyService(cache).merge("paper-1", [_response()])


@pytest.mark.asyncio
async def test_merge_allows_sentinel_mapping_to_be_filled_once() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record(mapping_value=MISSING_VALUE_SENTINEL))

    updated = await UserSupplyService(cache).merge("paper-1", [_response()])

    assert updated.parameter_mapping[0].value == "3.5"


@pytest.mark.asyncio
async def test_failed_batch_does_not_mutate_cached_plan() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record(include_second_missing=True))

    with pytest.raises(PaperUserSupplyError, match="parameter_name_mismatch"):
        await UserSupplyService(cache).merge(
            "paper-1",
            [
                _response(),
                _response(
                    prompt_id="MISS-2",
                    parameter_name="wrong",
                    user_supplied_value="0.2",
                    user_supplied_unit="pu",
                ),
            ],
        )

    cached = await cache.get("paper-1")
    assert cached is not None
    assert [mapping.value for mapping in cached.plan.parameter_mapping] == [
        MISSING_VALUE_SENTINEL,
        MISSING_VALUE_SENTINEL,
    ]
    assert cached.plan.evidence == [_document_evidence()]


@pytest.mark.asyncio
async def test_validate_for_spec_fail_does_not_mutate_cached_plan() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    with pytest.raises(PaperUserSupplyError, match="user_supplied_evidence_invalid"):
        await UserSupplyService(cache, FailingValidationEvidenceTagger()).merge(
            "paper-1", [_response()]
        )

    cached = await cache.get("paper-1")
    assert cached is not None
    assert cached.plan.parameter_mapping[0].value == MISSING_VALUE_SENTINEL
    assert cached.plan.evidence == [_document_evidence()]


@pytest.mark.asyncio
async def test_successful_merge_writes_updated_record_to_cache() -> None:
    cache = InMemoryPaperPlanCache()
    await cache.set("paper-1", _record())

    updated = await UserSupplyService(cache).merge("paper-1", [_response()])

    cached = await cache.get("paper-1")
    assert cached is not None
    assert cached.paper_id == "paper-1"
    assert cached.plan == updated
    assert cached.plan.parameter_mapping[0].source is EvidenceSource.USER_SUPPLIED


def _record(
    *,
    mapping_value: str = MISSING_VALUE_SENTINEL,
    include_second_missing: bool = False,
) -> PaperPlanRecord:
    evidence = _document_evidence()
    mappings = [_mapping("H", "Synchronous Machine.H", mapping_value, "s")]
    missing_prompts = [_missing_prompt("MISS-1", "H", "s")]
    bindings = [_binding("MISS-1", "H", "Synchronous Machine.H")]
    if include_second_missing:
        mappings.append(_mapping("Xd", "Synchronous Machine.Xd", MISSING_VALUE_SENTINEL, "pu"))
        missing_prompts.append(_missing_prompt("MISS-2", "Xd", "pu"))
        bindings.append(_binding("MISS-2", "Xd", "Synchronous Machine.Xd"))

    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[
                BlockRecommendation(
                    block_type="Synchronous Machine",
                    purpose="Model the generator.",
                    paper_reference=evidence,
                )
            ],
            parameter_mapping=mappings,
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=None,
            evidence=[evidence],
        ),
        missing_prompts=missing_prompts,
        missing_bindings=bindings,
    )


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        abstract="A synchronous machine short-circuit report.",
        equations=[
            EquationEntry(
                equation_id="EQ-01",
                latex_or_text="H = 3.5",
                paper_section_id="S1",
            )
        ],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
            )
        ],
        figure_locations=[
            FigureRef(figure_id="FIG-01", caption="Machine parameters", paper_section_id="S1")
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _mapping(
    paper_param_name: str,
    model_param_name: str,
    value: str,
    unit: str | None,
) -> ParameterMapping:
    return ParameterMapping(
        paper_param_name=paper_param_name,
        model_param_name=model_param_name,
        value=value,
        unit=unit,
        source=EvidenceSource.DOCUMENT_EXTRACTED,
    )


def _missing_prompt(
    prompt_id: str,
    parameter_name: str,
    suggested_unit: str | None,
) -> MissingParameterPrompt:
    return MissingParameterPrompt(
        prompt_id=prompt_id,
        parameter_name=parameter_name,
        paper_reference=_document_evidence(figure_id="FIG-01"),
        suggested_unit=suggested_unit,
        user_supplied_value=None,
        user_supplied_unit=None,
    )


def _binding(
    prompt_id: str,
    paper_param_name: str,
    model_param_name: str,
) -> MissingBindingModel:
    return MissingBindingModel(
        prompt_id=prompt_id,
        paper_param_name=paper_param_name,
        model_param_name=model_param_name,
    )


def _response(
    *,
    prompt_id: str = "MISS-1",
    parameter_name: str = "H",
    user_supplied_value: str = "3.5",
    user_supplied_unit: str | None = "s",
) -> UserSuppliedResponseModel:
    return UserSuppliedResponseModel(
        prompt_id=prompt_id,
        parameter_name=parameter_name,
        user_supplied_value=user_supplied_value,
        user_supplied_unit=user_supplied_unit,
        user_supplied_note=None,
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )
