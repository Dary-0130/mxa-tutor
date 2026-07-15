from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest

import features.paper.paper_step_regeneration_service as regeneration_module
from core.domain.exceptions import (
    LLMRateLimitError,
    PaperPlanGenerationError,
    PaperReparseInProgressError,
    StoreError,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_correction import (
    PaperParameterCorrection,
    PlanCorrectionTarget,
)
from core.domain.paper_plan import (
    BlockRecommendation,
    BuildGuidance,
    ConfigurationHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceTarget,
    ModelGenerationPlan,
    PaperPlanRecord,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperSpec,
    ParameterEntry,
)
from features.paper.build_steps_dependency_audit import DependencyAudit
from features.paper.paper_plan_helpers import (
    MISSING_VALUE_SENTINEL,
    BuildStepsDtoValidationError,
    MissingBindingModel,
    ModelBuildStepDraft,
)
from features.paper.paper_step_regeneration_service import (
    PaperStepRegenerationError,
    PaperStepRegenerationService,
)


@pytest.mark.asyncio
async def test_acquires_lock_before_reading_and_holds_it_through_llm() -> None:
    registry = _RecordingLockRegistry()
    store = _FakeBundleStore(_record(), lock_registry=registry)
    plan_cache = _FakePlanCache()
    build_started = asyncio.Event()
    build_release = asyncio.Event()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
        build_started=build_started,
        build_release=build_release,
    )
    service = _service(store, plan_cache, plan_service, registry)

    task = asyncio.create_task(service.regenerate_steps("paper-1"))
    await build_started.wait()

    assert registry.locked is True
    assert store.read_lock_states == [True]
    assert plan_cache.set_calls == []

    build_release.set()
    await task

    assert registry.locked is False
    assert registry.events == ["acquire", "enter", "exit"]


@pytest.mark.asyncio
async def test_nothing_to_regenerate_raises_400_without_llm() -> None:
    record = _record(build_steps=_derived_build_steps(), mscript="clear; clc;")
    store = _FakeBundleStore(record)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService()

    with pytest.raises(PaperStepRegenerationError) as exc_info:
        await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert exc_info.value.error_code == "regenerate_nothing_to_do"
    assert exc_info.value.status_code == 400
    assert plan_service.build_calls == 0
    assert plan_service.mscript_calls == 0
    assert plan_cache.set_calls == []


@pytest.mark.parametrize(
    ("has_correction", "has_build_steps", "has_mscript", "allowed"),
    [
        (False, True, True, False),
        (False, True, False, False),
        (False, False, True, True),
        (False, False, False, True),
        (True, True, True, True),
        (True, True, False, True),
        (True, False, True, True),
        (True, False, False, True),
    ],
)
@pytest.mark.asyncio
async def test_regeneration_predicate_ignores_mscript_null(
    has_correction: bool,
    has_build_steps: bool,
    has_mscript: bool,
    allowed: bool,
) -> None:
    correction = _correction()
    corrections = [correction] if has_correction else []
    plan_evidence = [_document_evidence()]
    if has_correction:
        plan_evidence.append(_correction_evidence(correction))
    record = _record(
        build_steps=_derived_build_steps() if has_build_steps else None,
        mscript="clear; clc;" if has_mscript else None,
        mapping_value="3.7" if has_correction else MISSING_VALUE_SENTINEL,
        mapping_source=EvidenceSource.USER_SUPPLIED
        if has_correction
        else EvidenceSource.DOCUMENT_EXTRACTED,
        plan_evidence=plan_evidence,
    )
    store = _FakeBundleStore(record, corrections=corrections)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
    )

    if not allowed:
        with pytest.raises(PaperStepRegenerationError) as exc_info:
            await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")
        assert exc_info.value.error_code == "regenerate_nothing_to_do"
        assert plan_service.build_calls == 0
        assert plan_service.mscript_calls == 0
        return

    await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.build_calls == 1
    assert plan_service.mscript_calls == 1
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_d1_mscript_null_with_complete_steps_does_not_regenerate_again() -> None:
    record = _record(build_steps=_derived_build_steps(), mscript=None)
    store = _FakeBundleStore(record)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService()

    with pytest.raises(PaperStepRegenerationError) as exc_info:
        await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert exc_info.value.error_code == "regenerate_nothing_to_do"
    assert exc_info.value.status_code == 400
    assert plan_service.build_calls == 0
    assert plan_service.mscript_calls == 0
    assert plan_cache.set_calls == []


@pytest.mark.asyncio
async def test_d2_suppressed_steps_regenerate_once_then_become_complete() -> None:
    store = _FakeBundleStore(_record(build_steps=None, mscript=None))
    plan_cache = _FakePlanCache()
    completed_plan = replace(
        _record().plan,
        build_steps=_derived_build_steps(),
        m_script_skeleton="clear; clc;",
        guidance_status="not_generated",
    )
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
        guidance_results=[completed_plan],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated.build_steps is not None
    assert updated.m_script_skeleton == "clear; clc;"
    assert plan_service.build_calls == 1
    assert plan_service.mscript_calls == 1
    assert len(plan_cache.set_calls) == 1

    store.records["paper-1"] = plan_cache.set_calls[-1]
    second_plan_service = _FakePlanService()

    with pytest.raises(PaperStepRegenerationError) as exc_info:
        await _service(store, plan_cache, second_plan_service).regenerate_steps("paper-1")

    assert exc_info.value.error_code == "regenerate_nothing_to_do"
    assert second_plan_service.build_calls == 0
    assert second_plan_service.mscript_calls == 0


@pytest.mark.asyncio
async def test_stale_guidance_status_triggers_regeneration_and_refreshes_guidance() -> None:
    old_guidance = _build_guidance("Old frozen guidance.")
    record = _record(build_steps=_derived_build_steps(), mscript="clear; clc;")
    record = replace(
        record,
        plan=replace(
            record.plan,
            build_guidance=old_guidance,
            guidance_status="stale_pending_regeneration",
        ),
    )
    refreshed_guidance = _build_guidance("Fresh guidance.")
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
        guidance_results=[
            replace(
                record.plan,
                build_guidance=refreshed_guidance,
                guidance_status="generated",
            )
        ],
    )
    store = _FakeBundleStore(record)
    plan_cache = _FakePlanCache()

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.build_calls == 1
    assert plan_service.mscript_calls == 1
    assert plan_service.guidance_calls == 1
    assert plan_service.guidance_inputs[0].guidance_status == "stale_pending_regeneration"
    assert plan_service.guidance_inputs[0].build_guidance is None
    assert updated.guidance_status == "generated"
    assert updated.build_guidance == refreshed_guidance
    assert plan_cache.set_calls[0].plan.guidance_status == "generated"


@pytest.mark.asyncio
async def test_build_step_transient_retries_fourth_attempt_and_writes_once() -> None:
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[
            BuildStepsDtoValidationError("dto"),
            BuildStepsDtoValidationError("dto"),
            BuildStepsDtoValidationError("dto"),
            _build_step_drafts(),
        ],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.build_calls == 4
    assert updated.build_steps is not None
    assert updated.m_script_skeleton == "clear; clc;"
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_build_step_four_transient_failures_fail_closed_but_do_not_500() -> None:
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[LLMRateLimitError("rate") for _ in range(4)],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.build_calls == 4
    assert updated.build_steps is None
    assert updated.m_script_skeleton == "clear; clc;"
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_fail_closed_preserves_existing_build_steps_when_regeneration_fails() -> None:
    original_steps = _derived_build_steps()
    record = _record(build_steps=original_steps)
    record = replace(
        record,
        plan=replace(record.plan, guidance_status="stale_pending_regeneration"),
    )
    store = _FakeBundleStore(record)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[LLMRateLimitError("rate") for _ in range(4)],
        mscript_results=[LLMRateLimitError("rate") for _ in range(4)],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated.build_steps == original_steps
    assert updated.m_script_skeleton is None
    assert plan_cache.set_calls[0].plan.build_steps == original_steps


@pytest.mark.asyncio
async def test_mscript_failure_does_not_block_build_step_write() -> None:
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=[LLMRateLimitError("rate") for _ in range(4)],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.mscript_calls == 4
    assert updated.build_steps is not None
    assert updated.m_script_skeleton is None
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_mscript_conflict_redline_does_not_retry() -> None:
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=[
            PaperPlanGenerationError(
                "role=mscript_drafter_from_mapping: parameter_conflict_mscript"
            )
        ],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.mscript_calls == 1
    assert updated.build_steps is not None
    assert updated.m_script_skeleton is None


@pytest.mark.asyncio
async def test_build_step_redline_does_not_retry() -> None:
    store = _FakeBundleStore(_record(mapping_value="3.5"))
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts(title="Bind H with 3.5 s")],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert plan_service.build_calls == 1
    assert updated.build_steps is None
    assert updated.m_script_skeleton == "clear; clc;"


@pytest.mark.asyncio
async def test_validator_runs_before_single_set_plan_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache(events=events)
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
    )
    service = _service(store, plan_cache, plan_service)
    original_validator = service._validate_regenerated_plan_before_write

    def wrapped_validator(*args: Any, **kwargs: Any) -> None:
        events.append("validator")
        original_validator(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_regenerated_plan_before_write", wrapped_validator)

    await service.regenerate_steps("paper-1")

    assert events == ["validator", "set_plan"]
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_validator_explicitly_calls_conflict_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[ModelGenerationPlan, object]] = []

    def fake_guard(plan: ModelGenerationPlan, conflicts: object) -> None:
        calls.append((plan, conflicts))

    monkeypatch.setattr(
        regeneration_module,
        "validate_plan_does_not_resolve_conflicts",
        fake_guard,
    )
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
    )

    await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert len(calls) == 1
    assert calls[0][0] == plan_cache.set_calls[0].plan


@pytest.mark.asyncio
async def test_validator_rejects_parameter_mapping_drift_without_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
    )
    service = _service(store, plan_cache, plan_service)
    original_replace = regeneration_module._replace_regenerated_artifacts

    def drifting_replace(
        record: PaperPlanRecord,
        *,
        build_steps: object,
        mscript: str | None,
    ) -> ModelGenerationPlan:
        plan = original_replace(record, build_steps=build_steps, mscript=mscript)
        return replace(
            plan,
            parameter_mapping=[
                replace(plan.parameter_mapping[0], value="9.9"),
                *plan.parameter_mapping[1:],
            ],
        )

    monkeypatch.setattr(regeneration_module, "_replace_regenerated_artifacts", drifting_replace)

    updated = await service.regenerate_steps("paper-1")

    assert updated == store.records["paper-1"].plan
    assert plan_cache.set_calls == []


@pytest.mark.asyncio
async def test_resolved_fill_missing_user_evidence_is_allowed() -> None:
    fill_evidence = _fill_missing_evidence()
    record = _record(
        mapping_value="3.5",
        mapping_source=EvidenceSource.USER_SUPPLIED,
        plan_evidence=[_document_evidence(), fill_evidence],
        missing_prompt_filled=True,
    )
    store = _FakeBundleStore(record)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts(evidence=fill_evidence)],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated.build_steps is not None
    assert updated.build_steps[0].evidence == [fill_evidence]
    assert len(plan_cache.set_calls) == 1


@pytest.mark.asyncio
async def test_resolved_correct_extracted_user_evidence_is_allowed_and_corrections_unchanged() -> (
    None
):
    correction = _correction()
    correction_evidence = _correction_evidence(correction)
    record = _record(
        mapping_value=correction.corrected_value,
        mapping_source=EvidenceSource.USER_SUPPLIED,
        plan_evidence=[_document_evidence(), correction_evidence],
    )
    store = _FakeBundleStore(record, corrections=[correction])
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts(evidence=correction_evidence)],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated.build_steps is not None
    assert store.corrections == [correction]
    assert store.apply_parameter_correction_calls == 0
    assert plan_cache.set_calls[0].plan.evidence == record.plan.evidence


@pytest.mark.asyncio
async def test_regeneration_writes_only_plan_cache_not_correction_store() -> None:
    correction = _correction()
    correction_evidence = _correction_evidence(correction)
    record = _record(
        mapping_value=correction.corrected_value,
        mapping_source=EvidenceSource.USER_SUPPLIED,
        plan_evidence=[_document_evidence(), correction_evidence],
    )
    store = _FakeBundleStore(record, corrections=[correction])
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts(evidence=correction_evidence)],
        mscript_results=["clear; clc;"],
    )

    await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert len(plan_cache.set_calls) == 1
    assert store.correction_write_calls == []
    assert store.corrections == [correction]


@pytest.mark.asyncio
async def test_unresolved_user_evidence_fail_closes_without_write() -> None:
    unresolved = _correction_evidence(_correction(correction_id="CORR-404"))
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts(evidence=unresolved)],
        mscript_results=["clear; clc;"],
    )

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated == store.records["paper-1"].plan
    assert plan_cache.set_calls == []


@pytest.mark.asyncio
async def test_store_failure_maps_to_route_local_store_failed_and_preserves_record() -> None:
    original = _record()
    store = _FakeBundleStore(original)
    plan_cache = _FakePlanCache(error=StoreError("sqlite_operation_failed"))
    plan_service = _FakePlanService(
        build_results=[_build_step_drafts()],
        mscript_results=["clear; clc;"],
    )

    with pytest.raises(PaperStepRegenerationError) as exc_info:
        await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert exc_info.value.error_code == "regenerate_store_failed"
    assert exc_info.value.status_code == 500
    assert store.records["paper-1"] == original


@pytest.mark.asyncio
async def test_lock_conflict_maps_to_reparse_in_progress_without_reading() -> None:
    registry = _RecordingLockRegistry(pre_locked=True)
    store = _FakeBundleStore(_record(), lock_registry=registry)
    plan_cache = _FakePlanCache()
    plan_service = _FakePlanService()

    with pytest.raises(PaperReparseInProgressError):
        await _service(store, plan_cache, plan_service, registry).regenerate_steps("paper-1")

    assert store.read_lock_states == []
    assert plan_service.build_calls == 0


@pytest.mark.asyncio
async def test_regeneration_dependency_audit_is_logged_without_changing_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MXA_BUILD_STEPS_DEPENDENCY_AUDIT", "1")
    info_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_info(*args: object, **kwargs: object) -> None:
        info_calls.append((args, kwargs))

    monkeypatch.setattr(regeneration_module.logger, "info", fake_info)
    plan_service = _FakePlanService(
        build_results=[BuildStepsDtoValidationError("depends_on_self") for _ in range(4)],
        mscript_results=["clear; clc;"],
        dependency_audit=DependencyAudit(
            dependency_audit_status="violations",
            total_steps=3,
            total_dep_edges=1,
            dep_edge_density=0.5,
            all_empty_dependency_graph=False,
            nonfirst_steps_with_empty_depends_on=0,
            duplicate_step_id_count=0,
            violations_by_code={"self": 1, "unknown": 0, "cycle": 0, "not_prior": 0},
            violation_edges_total_count=1,
        ),
    )
    store = _FakeBundleStore(_record())
    plan_cache = _FakePlanCache()

    updated = await _service(store, plan_cache, plan_service).regenerate_steps("paper-1")

    assert updated.build_steps is None
    logged = repr(info_calls)
    assert "paper_step_regeneration_build_steps_dependency_audit" in logged
    assert "depends_on_self" in logged
    assert '"dependency_audit_status":"violations"' in logged


def _service(
    store: _FakeBundleStore,
    plan_cache: _FakePlanCache,
    plan_service: _FakePlanService,
    registry: _RecordingLockRegistry | None = None,
) -> PaperStepRegenerationService:
    return PaperStepRegenerationService(
        bundle_store=store,  # type: ignore[arg-type]
        plan_cache=plan_cache,  # type: ignore[arg-type]
        plan_service=plan_service,  # type: ignore[arg-type]
        lock_registry=registry or _RecordingLockRegistry(),
        retry_backoff_base_seconds=0,
    )


class _RecordingLockRegistry:
    def __init__(self, *, pre_locked: bool = False) -> None:
        self.locked = pre_locked
        self.events: list[str] = []

    async def acquire(self, paper_id: str) -> _RecordingLockToken:
        _ = paper_id
        self.events.append("acquire")
        if self.locked:
            raise PaperReparseInProgressError("reparse_in_progress") from None
        return _RecordingLockToken(self)


class _RecordingLockToken:
    def __init__(self, registry: _RecordingLockRegistry) -> None:
        self._registry = registry

    async def __aenter__(self) -> _RecordingLockToken:
        self._registry.locked = True
        self._registry.events.append("enter")
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type, exc, tb
        self._registry.locked = False
        self._registry.events.append("exit")


class _FakeBundleStore:
    def __init__(
        self,
        record: PaperPlanRecord,
        *,
        corrections: list[PaperParameterCorrection] | None = None,
        lock_registry: _RecordingLockRegistry | None = None,
    ) -> None:
        self.records = {record.paper_id: record}
        self.corrections = list(corrections or [])
        self.lock_registry = lock_registry
        self.read_lock_states: list[bool] = []
        self.apply_parameter_correction_calls = 0
        self.correction_write_calls: list[str] = []

    async def get_plan_record(self, paper_id: str) -> PaperPlanRecord | None:
        if self.lock_registry is not None:
            self.read_lock_states.append(self.lock_registry.locked)
        return self.records.get(paper_id)

    async def list_parameter_corrections(
        self,
        paper_id: str,
    ) -> list[PaperParameterCorrection]:
        _ = paper_id
        return list(self.corrections)

    async def apply_parameter_correction_atomically(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        self.apply_parameter_correction_calls += 1
        self.correction_write_calls.append("apply_parameter_correction_atomically")

    async def undo_parameter_correction_atomically(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        self.correction_write_calls.append("undo_parameter_correction_atomically")

    async def insert_parameter_correction(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        self.correction_write_calls.append("insert_parameter_correction")

    async def update_parameter_correction_value(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        self.correction_write_calls.append("update_parameter_correction_value")

    async def delete_parameter_correction(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        self.correction_write_calls.append("delete_parameter_correction")


class _FakePlanCache:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.error = error
        self.events = events
        self.set_calls: list[PaperPlanRecord] = []

    async def set(self, paper_id: str, record: PaperPlanRecord) -> None:
        _ = paper_id
        if self.events is not None:
            self.events.append("set_plan")
        if self.error is not None:
            raise self.error
        self.set_calls.append(record)


class _FakePlanService:
    def __init__(
        self,
        *,
        build_results: list[list[ModelBuildStepDraft] | Exception] | None = None,
        mscript_results: list[str | None | Exception] | None = None,
        guidance_results: list[ModelGenerationPlan | Exception] | None = None,
        build_started: asyncio.Event | None = None,
        build_release: asyncio.Event | None = None,
        dependency_audit: DependencyAudit | None = None,
    ) -> None:
        self.build_results = list(build_results or [])
        self.mscript_results = list(mscript_results or [])
        self.guidance_results = list(guidance_results or [])
        self.build_started = build_started
        self.build_release = build_release
        self.build_calls = 0
        self.mscript_calls = 0
        self.guidance_calls = 0
        self.guidance_inputs: list[ModelGenerationPlan] = []
        self.dependency_audit = dependency_audit or DependencyAudit.unavailable("draft_parse")

    async def _llm_build_steps_for_regeneration(self, *args: object) -> list[ModelBuildStepDraft]:
        _ = args
        self.build_calls += 1
        if self.build_started is not None:
            self.build_started.set()
        if self.build_release is not None:
            await self.build_release.wait()
        if not self.build_results:
            raise AssertionError("unexpected build-step regeneration call")
        result = self.build_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def _llm_mscript_draft_from_mapping(self, *args: object) -> str | None:
        _ = args
        self.mscript_calls += 1
        if not self.mscript_results:
            raise AssertionError("unexpected mscript regeneration call")
        result = self.mscript_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def generate_build_guidance_for_plan(
        self,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
    ) -> ModelGenerationPlan:
        _ = spec
        self.guidance_calls += 1
        self.guidance_inputs.append(plan)
        if not self.guidance_results:
            return plan
        result = self.guidance_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def _llm_plan_compose(self, *args: object) -> object:
        _ = args
        raise AssertionError("plan compose must not run during step regeneration")

    async def _llm_missing_detect(self, *args: object) -> object:
        _ = args
        raise AssertionError("missing detect must not run during step regeneration")

    def build_steps_dependency_audit(self) -> DependencyAudit:
        return self.dependency_audit


def _record(
    *,
    build_steps: list[Any] | None = None,
    mscript: str | None = None,
    mapping_value: str = MISSING_VALUE_SENTINEL,
    mapping_source: EvidenceSource = EvidenceSource.DOCUMENT_EXTRACTED,
    plan_evidence: list[PaperEvidenceEntry] | None = None,
    missing_prompt_filled: bool = False,
) -> PaperPlanRecord:
    evidence = _document_evidence()
    return PaperPlanRecord(
        paper_id="paper-1",
        spec=_spec(),
        plan=ModelGenerationPlan(
            plan_id="PLAN-paper-1",
            paper_spec_id="paper-1",
            library_choice="SimPowerSystems",
            block_recommendations=[_block_recommendation()],
            parameter_mapping=[
                ParameterMapping(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                    value=mapping_value,
                    unit="s",
                    source=mapping_source,
                )
            ],
            subsystem_breakdown=["Place machine", "Apply fault", "Observe current"],
            m_script_skeleton=mscript,
            evidence=plan_evidence if plan_evidence is not None else [evidence],
            build_steps=build_steps,
        ),
        missing_prompts=[
            MissingParameterPrompt(
                prompt_id="MISS-1",
                parameter_name="H",
                paper_reference=_document_evidence(figure_id="FIG-01"),
                suggested_unit="s",
                user_supplied_value="3.5" if missing_prompt_filled else None,
                user_supplied_unit="s" if missing_prompt_filled else None,
            )
        ],
        missing_bindings=[
            MissingBindingModel(
                prompt_id="MISS-1",
                paper_param_name="H",
                model_param_name="Synchronous Machine.H",
            )
        ],
    )


def _spec() -> PaperSpec:
    evidence = _document_evidence()
    return PaperSpec(
        paper_title="Short-circuit report",
        paper_type="report",
        domain="motor_control",
        documents=[PaperDocument(document_id="DOC-001", filename="paper.pdf")],
        primary_document_id=None,
        abstract="A synchronous machine short-circuit report.",
        equations=[EquationEntry("EQ-01", "H = 3.5", "S1", "DOC-001")],
        parameter_table=[
            ParameterEntry(
                name="Inertia constant",
                symbol="H",
                value="3.5",
                unit="s",
                source=EvidenceSource.DOCUMENT_EXTRACTED,
                document_id="DOC-001",
            )
        ],
        figure_locations=[
            FigureRef(
                figure_id="FIG-01",
                caption="Machine parameters",
                paper_section_id="S1",
                document_id="DOC-001",
            )
        ],
        pseudocode_blocks=[],
        evidence=[evidence],
    )


def _block_recommendation() -> BlockRecommendation:
    return BlockRecommendation(
        block_type="Synchronous Machine",
        purpose="Model the generator.",
        paper_reference=_document_evidence(),
    )


def _build_step_drafts(
    *,
    title: str = "Place machine block",
    evidence: PaperEvidenceEntry | None = None,
) -> list[ModelBuildStepDraft]:
    step_evidence = [evidence or _document_evidence()]
    block_evidence = _document_evidence()
    return [
        ModelBuildStepDraft(
            step_id="STEP-001",
            title=title,
            intent="Create the machine subsystem entry point.",
            block_refs=[
                StepBlockRef(
                    block_ref_id="B1",
                    block_type="Synchronous Machine",
                    library_path=None,
                    purpose="Model the generator.",
                    paper_reference=block_evidence,
                )
            ],
            parameter_refs=[],
            connection_hints=[],
            configuration_hints=[],
            depends_on=[],
            evidence=step_evidence,
        ),
        ModelBuildStepDraft(
            step_id="STEP-002",
            title="Bind machine parameter",
            intent="Link the paper parameter name to the model slot.",
            block_refs=[],
            parameter_refs=[
                ParameterMappingRef(
                    paper_param_name="H",
                    model_param_name="Synchronous Machine.H",
                )
            ],
            connection_hints=[],
            configuration_hints=[],
            depends_on=["STEP-001"],
            evidence=step_evidence,
        ),
        ModelBuildStepDraft(
            step_id="STEP-003",
            title="Prepare simulation observation",
            intent="Keep the simulation output ready for comparison.",
            block_refs=[],
            parameter_refs=[],
            connection_hints=[],
            configuration_hints=[
                ConfigurationHint(
                    target="simulation",
                    setting_name="Signal logging",
                    instruction="Record the generated current signal.",
                    evidence=step_evidence,
                )
            ],
            depends_on=["STEP-001"],
            evidence=step_evidence,
        ),
    ]


def _derived_build_steps():
    return regeneration_module.PlanAssembler().validate_and_derive_build_steps(
        _build_step_drafts(),
        _record().plan.parameter_mapping,
        _record().plan.block_recommendations,
    )


def _build_guidance(display_text: str = "Use the documented machine inertia.") -> BuildGuidance:
    return BuildGuidance(
        version="v2",
        assessment=GuidanceAssessment(
            content_status="outline_only",
            environment_status="not_checked",
            overall_status="outline_only",
            blocking_gap_ids=[],
        ),
        details=[
            GuidanceDetail(
                detail_id="GD-001",
                step_id="STEP-001",
                detail_kind="parameter_value",
                basis="document_extracted",
                actionability="actionable",
                display_text=display_text,
                evidence=[_document_evidence()],
                convention_code=None,
                confirmation_reason_code=None,
                target=GuidanceTarget(
                    target_kind="parameter",
                    model_param="Synchronous Machine.H",
                    paper_param="H",
                ),
                obligation_kind="determine_parameter_value",
                resolution={
                    "kind": "fixed",
                    "fixed_kind": "numeric",
                    "value": 3.5,
                    "unit": "s",
                },
                execution_closure="closed",
                input_fact_refs=[],
                punt_reason_code=None,
            )
        ],
        gaps=[],
    )


def _document_evidence(
    *,
    paper_section_id: str | None = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        document_id="DOC-001",
        paper_section_id=paper_section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="The report states the machine parameter.",
        missing_param_prompt_id=None,
    )


def _fill_missing_evidence() -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id="MISS-1",
        user_action=UserEvidenceAction.FILL_MISSING,
    )


def _correction_evidence(correction: PaperParameterCorrection) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.USER_SUPPLIED,
        document_id=None,
        paper_section_id=None,
        equation_id=None,
        figure_id=None,
        excerpt=None,
        missing_param_prompt_id=None,
        user_action=UserEvidenceAction.CORRECT_EXTRACTED,
        parameter_correction_id=correction.correction_id,
        correction_param_key=correction.param_key,
    )


def _correction(*, correction_id: str = "CORR-1") -> PaperParameterCorrection:
    return PaperParameterCorrection(
        correction_id=correction_id,
        paper_id="paper-1",
        param_key="H::Synchronous Machine.H",
        plan_target=PlanCorrectionTarget(
            paper_param_name="H",
            model_param_name="Synchronous Machine.H",
            plan_mapping_index=0,
        ),
        original_value="3.5",
        original_unit="s",
        original_source=EvidenceSource.DOCUMENT_EXTRACTED,
        original_document_id="DOC-001",
        corrected_value="3.7",
        corrected_unit="s",
        created_at="2026-07-02T00:00:00Z",
        updated_at="2026-07-02T00:00:00Z",
    )
