from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import eval.run_paper_eval as subject
from core.domain.exceptions import PaperPlanGenerationError
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_plan import BlockRecommendation, ModelGenerationPlan, ParameterMapping
from core.domain.paper_spec import FigureRef, PaperSpec
from eval._paper_eval_csv import write_paper_eval_csv
from features.paper.paper_plan_cache import InMemoryPaperPlanCache
from features.paper.paper_plan_helpers import MissingBindingModel
from features.paper.paper_schemas import MissingParameterPromptModel
from features.paper.paper_user_input_schemas import (
    UserSuppliedResponseBatch,
    UserSuppliedResponseModel,
)

CASES_ROOT = Path("eval/cases/paper_to_model").resolve()
MATERIAL_CASE = CASES_ROOT / "material_to_plan" / "case_01_motor_short_circuit"
MISSING_CASE = CASES_ROOT / "missing_param" / "case_01_missing_image_param"


class FakeSpecService:
    def __init__(self, spec: PaperSpec) -> None:
        self.spec = spec
        self.calls: list[tuple[Path, str]] = []

    async def extract(self, file_path: Path, paper_id: str) -> PaperSpec:
        self.calls.append((file_path, paper_id))
        return self.spec


class FakePlanService:
    def __init__(
        self,
        *,
        plan: ModelGenerationPlan | None = None,
        prompts: list[MissingParameterPrompt] | None = None,
        bindings: list[MissingBindingModel] | None = None,
        error: PaperPlanGenerationError | None = None,
    ) -> None:
        self.plan = plan
        self.prompts = prompts or []
        self.bindings = bindings or []
        self.error = error
        self.calls: list[tuple[PaperSpec, str]] = []

    async def generate(
        self,
        spec: PaperSpec,
        paper_id: str,
    ) -> tuple[
        ModelGenerationPlan,
        list[MissingParameterPrompt],
        list[MissingBindingModel],
    ]:
        self.calls.append((spec, paper_id))
        if self.error is not None:
            raise self.error
        assert self.plan is not None
        return self.plan, self.prompts, self.bindings


class RecordingUserSupplyService:
    def __init__(self, updated_plan: ModelGenerationPlan) -> None:
        self.updated_plan = updated_plan
        self.calls: list[tuple[str, list[UserSuppliedResponseModel]]] = []

    async def merge(
        self,
        paper_id: str,
        responses: list[UserSuppliedResponseModel],
    ) -> ModelGenerationPlan:
        self.calls.append((paper_id, responses))
        return self.updated_plan


def test_compute_case_metrics_keeps_golden_independent_by_metric() -> None:
    actual_spec = {
        "paper_title": "actual",
        "paper_type": "report",
        "domain": "motor_control",
        "abstract": "a",
        "evidence": [{"source": "document_extracted", "paper_section_id": "S1"}],
    }
    base_golden_spec = dict(actual_spec)
    changed_golden_spec = {**base_golden_spec, "parameter_table": [{"name": "PN"}]}
    plan = {
        "block_recommendations": [{"block_type": "Gain"}],
        "parameter_mapping": [{"paper_param_name": "PN", "value": "200"}],
        "m_script_skeleton": "params = 1\nplot(params)",
    }

    base = subject._compute_case_layer_metrics(
        case_kind="material_to_plan",
        actual_spec=actual_spec,
        actual_plan=plan,
        actual_prompts=[],
        actual_updated_plan=None,
        golden_spec=base_golden_spec,
        golden_plan=plan,
        golden_updated_plan=None,
    )
    changed = subject._compute_case_layer_metrics(
        case_kind="material_to_plan",
        actual_spec=actual_spec,
        actual_plan=plan,
        actual_prompts=[],
        actual_updated_plan=None,
        golden_spec=changed_golden_spec,
        golden_plan=plan,
        golden_updated_plan=None,
    )

    assert changed["A1"] != base["A1"]
    assert {k: v for k, v in changed.items() if k != "A1"} == {
        k: v for k, v in base.items() if k != "A1"
    }


@pytest.mark.asyncio
async def test_run_case_calls_spec_and_plan_services_without_golden_self_fallback() -> None:
    spec = _spec(title="Actual service spec")
    plan = _plan()
    spec_service = FakeSpecService(spec)
    plan_service = FakePlanService(plan=plan)

    result = await subject._run_case(
        MATERIAL_CASE,
        subject.EvaluatorServices(
            spec_service=spec_service,
            plan_service=plan_service,
            plan_cache=InMemoryPaperPlanCache(),
            user_supply_service=object(),
        ),
        CASES_ROOT,
    )

    assert spec_service.calls == [
        (
            MATERIAL_CASE / "input" / "source_doc_stripped.md",
            "PAPER-material_to_plan__case_01_motor_short_circuit",
        )
    ]
    assert plan_service.calls == [(spec, "PAPER-material_to_plan__case_01_motor_short_circuit")]
    assert result.actual_spec is not None
    assert result.actual_spec["paper_title"] == "Actual service spec"
    assert result.execution_status == "succeeded"
    assert result.failure is None


@pytest.mark.asyncio
async def test_generation_error_records_case_failed_and_no_fake_prompts() -> None:
    result = await subject._run_case(
        MISSING_CASE,
        subject.EvaluatorServices(
            spec_service=FakeSpecService(_spec()),
            plan_service=FakePlanService(
                error=PaperPlanGenerationError("missing_binding_not_found")
            ),
            plan_cache=InMemoryPaperPlanCache(),
            user_supply_service=object(),
        ),
        CASES_ROOT,
    )

    assert result.execution_status == "case_failed"
    assert result.verdict == "not_evaluated"
    assert result.failure == "missing_binding_not_found"
    assert result.actual_plan is None
    assert result.actual_prompts is None
    assert result.actual_updated_plan is None
    assert result.layer2_metrics == {
        "A1": "N/A",
        "C2": "N/A",
        "C3": "N/A",
        "D1": {"has_params": None, "has_equations": None, "has_plot": None},
        "E1": "N/A",
        "R3": "N/A",
    }


@pytest.mark.asyncio
async def test_unknown_generation_error_is_case_boundary_failure() -> None:
    result = await subject._run_case(
        MISSING_CASE,
        subject.EvaluatorServices(
            spec_service=FakeSpecService(_spec()),
            plan_service=FakePlanService(
                error=PaperPlanGenerationError("missing_binding_ambiguous")
            ),
            plan_cache=InMemoryPaperPlanCache(),
            user_supply_service=object(),
        ),
        CASES_ROOT,
    )

    assert result.execution_status == "case_failed"
    assert result.verdict == "not_evaluated"
    assert result.failure == "missing_binding_ambiguous"
    assert result.failure_stage == "plan_generate"


def test_user_response_batch_fails_fast_on_wrong_key_or_empty_list() -> None:
    with pytest.raises(ValidationError):
        UserSuppliedResponseBatch.model_validate({"responses": []})
    with pytest.raises(ValidationError):
        UserSuppliedResponseBatch.model_validate({"user_supplied_responses": []})


@pytest.mark.asyncio
async def test_missing_success_passes_pydantic_models_to_merge() -> None:
    prompts = _missing_prompts_from_golden()
    updated_plan = _updated_plan_for_prompts(prompts)
    supply_service = RecordingUserSupplyService(updated_plan)

    result = await subject._run_case(
        MISSING_CASE,
        subject.EvaluatorServices(
            spec_service=FakeSpecService(_spec()),
            plan_service=FakePlanService(
                plan=_plan(),
                prompts=prompts,
                bindings=_bindings_for_prompts(prompts),
            ),
            plan_cache=InMemoryPaperPlanCache(),
            user_supply_service=supply_service,
        ),
        CASES_ROOT,
    )

    assert len(supply_service.calls) == 1
    _, responses = supply_service.calls[0]
    assert all(isinstance(response, UserSuppliedResponseModel) for response in responses)
    assert not any(isinstance(response, dict) for response in responses)
    assert result.execution_status == "succeeded"
    assert result.layer2_metrics["E1"] == "Pass"
    assert result.layer2_metrics["R3"] == "Pass"


def test_schema_wrapper_serialization_succeeds_and_validation_errors_escape() -> None:
    plan = _updated_plan_for_prompts(_missing_prompts_from_golden()[:1])
    serialized = subject._serialize_plan(plan)

    assert serialized is not None
    assert serialized["parameter_mapping"][0]["source"] == "user_supplied"
    with pytest.raises(ValidationError):
        subject._serialize_plan(replace(plan, subsystem_breakdown=["only two", "steps"]))


def test_missing_case_without_golden_spec_marks_a1_na() -> None:
    metrics = subject._compute_case_layer_metrics(
        case_kind="missing_param",
        actual_spec={"paper_title": "actual"},
        actual_plan=_plan_dict(user_mapping_count=0),
        actual_prompts=[],
        actual_updated_plan=_plan_dict(user_mapping_count=0),
        golden_spec=None,
        golden_plan=None,
        golden_updated_plan=_plan_dict(user_mapping_count=0),
    )

    assert metrics["A1"] == "N/A"


def test_write_actual_artifacts_serializes_blocked_nulls(tmp_path: Path) -> None:
    result = subject.CaseResult(
        case_id="missing_param/case_01_missing_image_param",
        case_kind="missing_param",
        actual_spec={"paper_title": "actual"},
        actual_plan=None,
        actual_prompts=None,
        actual_updated_plan=None,
        actual_bindings=None,
        layer2_metrics={},
        rule_details={"case_failure": {"status": "n/a"}},
        failure="missing_binding_not_found",
        execution_status="case_failed",
        verdict="not_evaluated",
        failure_stage="plan_generate",
        exception_type="PaperPlanGenerationError",
        error_code="missing_binding_not_found",
    )

    subject._write_actual_artifacts(result, tmp_path, "case")

    assert json.loads((tmp_path / "case.actual_spec.json").read_text(encoding="utf-8")) == {
        "paper_title": "actual"
    }
    assert json.loads((tmp_path / "case.actual_plan.json").read_text(encoding="utf-8")) is None
    assert json.loads((tmp_path / "case.actual_prompts.json").read_text(encoding="utf-8")) is None
    assert (
        json.loads((tmp_path / "case.actual_updated_plan.json").read_text(encoding="utf-8")) is None
    )
    assert (tmp_path / "case.rule_details.json").is_file()
    assert (tmp_path / "case.case_result.json").is_file()


def test_csv_writes_status_failure_and_rejects_invalid_state(tmp_path: Path) -> None:
    csv_path = tmp_path / "row.csv"

    write_paper_eval_csv(
        case_id="missing_param/case_01_missing_image_param",
        layer1_outcome={"O1": "", "O2": ""},
        layer2_metrics={
            "A1": "N/A",
            "C2": "N/A",
            "C3": "N/A",
            "D1": {"has_params": None, "has_equations": None, "has_plot": None},
            "E1": "N/A",
            "R3": "N/A",
        },
        layer2_manual={"A2": "", "C1": "", "origin_inherited_notes": ""},
        execution_status="case_failed",
        verdict="not_evaluated",
        failure="missing_binding_not_found",
        output_path=csv_path,
    )

    row = next(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert row["execution_status"] == "case_failed"
    assert row["verdict"] == "not_evaluated"
    assert row["failure"] == "missing_binding_not_found"
    assert "B1_missing_recall" not in row
    assert "B2_missing_precision" not in row
    assert "E2_user_supplied_source" not in row
    assert row["R3_source_authenticity"] == "N/A"
    assert row["D1_has_params"] == "N/A"
    with pytest.raises(ValueError):
        write_paper_eval_csv(
            case_id="case",
            layer1_outcome={},
            layer2_metrics={},
            layer2_manual={},
            execution_status="succeeded",
            verdict="pass",
            failure="missing_binding_not_found",
            output_path=tmp_path / "bad-succeeded.csv",
        )
    with pytest.raises(ValueError):
        write_paper_eval_csv(
            case_id="case",
            layer1_outcome={},
            layer2_metrics={},
            layer2_manual={},
            execution_status="case_failed",
            verdict="fail",
            failure=None,
            output_path=tmp_path / "bad-blocked.csv",
        )


@pytest.mark.asyncio
async def test_main_configures_provider_and_writes_csv_plus_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, str] = {}

    class FakeSettings:
        deepseek_api_key = "test-key"
        deepseek_base_url = "https://example.test"

    class FakeProvider:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    async def fake_run_case(
        case_dir: Path,
        services: subject.EvaluatorServices,
        cases_root_resolved: Path,
    ) -> subject.CaseResult:
        assert case_dir == MATERIAL_CASE
        assert cases_root_resolved == CASES_ROOT
        assert services.spec_service is not None
        assert services.plan_service is not None
        return subject.CaseResult(
            case_id="material_to_plan/case_01_motor_short_circuit",
            case_kind="material_to_plan",
            actual_spec={"paper_title": "actual"},
            actual_plan={"parameter_mapping": []},
            actual_prompts=[],
            actual_updated_plan=None,
            actual_bindings=[],
            layer2_metrics={
                "A1": 1.0,
                "C2": 1.0,
                "C3": 1.0,
                "D1": {"has_params": None, "has_equations": None, "has_plot": None},
                "E1": "Pass",
                "R3": "Pass",
            },
            rule_details={"r3": {"status": "pass", "checks": []}},
            failure=None,
            execution_status="succeeded",
            verdict="pass",
            failure_stage=None,
            exception_type=None,
            error_code=None,
        )

    monkeypatch.setattr(subject, "AppSettings", FakeSettings)
    monkeypatch.setattr(subject, "DeepSeekTextProvider", FakeProvider)
    monkeypatch.setattr(subject, "_run_case", fake_run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_paper_eval.py",
            "--case",
            "material_to_plan/case_01_motor_short_circuit",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert await subject.main() == 0

    slug = "material_to_plan__case_01_motor_short_circuit"
    assert captured == {
        "api_key": "test-key",
        "base_url": "https://example.test",
    }
    assert (tmp_path / f"{slug}.paper_eval.csv").is_file()
    assert (tmp_path / f"{slug}.actual_spec.json").is_file()
    assert (tmp_path / f"{slug}.actual_plan.json").is_file()
    assert (tmp_path / f"{slug}.actual_prompts.json").is_file()
    assert (tmp_path / f"{slug}.actual_updated_plan.json").is_file()
    assert (tmp_path / f"{slug}.rule_details.json").is_file()
    assert (tmp_path / f"{slug}.case_result.json").is_file()


def test_reverse_grep_old_helper_name_is_not_reintroduced() -> None:
    old_helper_name = "_compute_" + "layer2_metrics"
    assert not hasattr(subject, old_helper_name)


def _spec(title: str = "Spec") -> PaperSpec:
    ref = _doc_ref()
    return PaperSpec(
        paper_title=title,
        paper_type="report",
        domain="motor_control",
        abstract="abstract",
        equations=[],
        parameter_table=[],
        figure_locations=[
            FigureRef(
                figure_id="FIG-01",
                caption="figure one",
                paper_section_id="S5",
            ),
            FigureRef(
                figure_id="FIG-02",
                caption="figure two",
                paper_section_id="S5",
            ),
            FigureRef(
                figure_id="FIG-03",
                caption="figure three",
                paper_section_id="S5",
            ),
        ],
        pseudocode_blocks=[],
        evidence=[ref, _doc_ref(section_id="S5", figure_id="FIG-01")],
    )


def _plan(
    *,
    mappings: list[ParameterMapping] | None = None,
    m_script_skeleton: str | None = "params = 1\nx = params + 1\nplot(x)",
) -> ModelGenerationPlan:
    ref = _doc_ref()
    return ModelGenerationPlan(
        plan_id="PLAN-test",
        paper_spec_id="PAPER-test",
        library_choice="Simscape Electrical Specialized Power Systems",
        block_recommendations=[BlockRecommendation("Gain", "test block", ref)],
        parameter_mapping=mappings if mappings is not None else [],
        subsystem_breakdown=["load source", "wire blocks", "configure solver"],
        m_script_skeleton=m_script_skeleton,
        evidence=[ref],
    )


def _updated_plan_for_prompts(
    prompts: list[MissingParameterPrompt],
) -> ModelGenerationPlan:
    mappings = [
        ParameterMapping(
            paper_param_name=prompt.parameter_name,
            model_param_name=f"model.param.{index}",
            value=str(index),
            unit=prompt.suggested_unit,
            source=EvidenceSource.USER_SUPPLIED,
        )
        for index, prompt in enumerate(prompts, start=1)
    ]
    return replace(
        _plan(mappings=mappings),
        evidence=[
            _doc_ref(),
            *[
                PaperEvidenceEntry(
                    source=EvidenceSource.USER_SUPPLIED,
                    paper_section_id=None,
                    equation_id=None,
                    figure_id=None,
                    excerpt=None,
                    missing_param_prompt_id=prompt.prompt_id,
                )
                for prompt in prompts
            ],
        ],
    )


def _missing_prompts_from_golden() -> list[MissingParameterPrompt]:
    prompts = subject._load_required_prompt_list(
        MISSING_CASE / "input" / "expected_missing_prompts.json"
    )
    return [MissingParameterPromptModel.model_validate(prompt).to_domain() for prompt in prompts]


def _bindings_for_prompts(prompts: list[MissingParameterPrompt]) -> list[MissingBindingModel]:
    return [
        MissingBindingModel(
            prompt_id=prompt.prompt_id,
            paper_param_name=prompt.parameter_name,
            model_param_name=f"model.param.{index}",
        )
        for index, prompt in enumerate(prompts, start=1)
    ]


def _doc_ref(
    *,
    section_id: str = "S1",
    equation_id: str | None = None,
    figure_id: str | None = None,
) -> PaperEvidenceEntry:
    return PaperEvidenceEntry(
        source=EvidenceSource.DOCUMENT_EXTRACTED,
        paper_section_id=section_id,
        equation_id=equation_id,
        figure_id=figure_id,
        excerpt="evidence excerpt",
        missing_param_prompt_id=None,
    )


def _plan_dict(
    *,
    user_mapping_count: int,
    empty_value_at: int | None = None,
) -> dict[str, Any]:
    return {
        "parameter_mapping": [
            {
                "paper_param_name": f"P{index}",
                "model_param_name": f"M{index}",
                "value": "" if empty_value_at == index else str(index),
                "source": "user_supplied",
            }
            for index in range(1, user_mapping_count + 1)
        ],
        "block_recommendations": [{"block_type": "Gain"}],
        "m_script_skeleton": "params = 1\nplot(params)",
    }
