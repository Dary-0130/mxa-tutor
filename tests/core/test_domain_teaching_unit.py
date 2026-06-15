from dataclasses import fields

from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit, TeachingUnitRef


def test_teaching_unit_has_final_eleven_fields() -> None:
    assert tuple(field.name for field in fields(TeachingUnit)) == (
        "id",
        "title",
        "target",
        "target_id",
        "level",
        "summary",
        "prerequisites",
        "explanation_steps",
        "knowledge_points",
        "source_refs",
        "confusion_points",
    )


def test_teaching_unit_required_fields_round_trip() -> None:
    source_ref = SourceRef(file_path="model.slx", block_id="b1", block_name="Gain")
    prerequisite = TeachingUnitRef(project_id="p1", teaching_unit_id="unit-0")
    unit = TeachingUnit(
        id="unit-1",
        title="Gain block",
        target="block",
        target_id="node-1",
        level="beginner",
        summary="Explains the gain block.",
        prerequisites=[prerequisite],
        explanation_steps=["Read input", "Apply gain", "Output signal"],
        knowledge_points=["PID 控制器"],
        source_refs=[source_ref],
        confusion_points=["Gain is not an integrator."],
    )

    assert unit.id == "unit-1"
    assert unit.title == "Gain block"
    assert unit.target == "block"
    assert unit.target_id == "node-1"
    assert unit.level == "beginner"
    assert unit.summary == "Explains the gain block."
    assert unit.prerequisites == [prerequisite]
    assert unit.explanation_steps == ["Read input", "Apply gain", "Output signal"]
    assert unit.knowledge_points == ["PID 控制器"]
    assert unit.source_refs == [source_ref]
    assert unit.confusion_points == ["Gain is not an integrator."]
