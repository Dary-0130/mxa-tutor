import json
from pathlib import Path

from features.paper.paper_schemas import (
    MissingParameterPromptModel,
    ModelGenerationPlanModel,
    PaperSpecModel,
)

ROOT = Path("eval/cases/paper_to_model")
PAPER_SPEC_PATH = (
    ROOT / "material_to_plan/case_01_motor_short_circuit/golden/expected_paper_spec.json"
)
PLAN_PATH = (
    ROOT / "material_to_plan/case_01_motor_short_circuit/golden/expected_model_generation_plan.json"
)
MISSING_PATH = (
    ROOT / "missing_param/case_01_missing_image_param/input/expected_missing_prompts.json"
)
UPDATED_PLAN_PATH = (
    ROOT / "missing_param/case_01_missing_image_param/golden/expected_updated_plan.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(model: object) -> object:
    return model.model_dump(mode="json")  # type: ignore[attr-defined]


def test_expected_paper_spec_roundtrip_matches_sample_json() -> None:
    data = _load(PAPER_SPEC_PATH)
    model = PaperSpecModel.model_validate(data)
    assert _json_dump(PaperSpecModel.from_domain(model.to_domain())) == data


def test_expected_model_generation_plan_roundtrip_matches_sample_json() -> None:
    data = _load(PLAN_PATH)
    model = ModelGenerationPlanModel.model_validate(data)
    assert data["build_steps"] is None
    assert model.build_steps is None
    assert _json_dump(ModelGenerationPlanModel.from_domain(model.to_domain())) == data


def test_expected_missing_prompts_dict_roundtrip_matches_sample_json() -> None:
    data = _load(MISSING_PATH)
    prompts = data["missing_prompts"]
    assert isinstance(prompts, list)

    models = [MissingParameterPromptModel.model_validate(item) for item in prompts]
    actual = {
        "missing_prompts": [
            _json_dump(MissingParameterPromptModel.from_domain(model.to_domain()))
            for model in models
        ]
    }

    assert actual == data


def test_expected_updated_plan_roundtrip_matches_sample_json() -> None:
    data = _load(UPDATED_PLAN_PATH)
    model = ModelGenerationPlanModel.model_validate(data)
    assert data["build_steps"] is None
    assert model.build_steps is None
    assert _json_dump(ModelGenerationPlanModel.from_domain(model.to_domain())) == data
