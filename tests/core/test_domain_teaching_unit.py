from core.domain.source_ref import SourceRef
from core.domain.teaching_unit import TeachingUnit


def test_teaching_unit_required_fields() -> None:
    source_ref = SourceRef(file_path="model.slx", block_id="b1", block_name="Gain")
    unit = TeachingUnit(
        id="unit-1",
        title="Gain block",
        target="block",
        target_id="node-1",
        level="beginner",
        summary="Explains the gain block.",
        prerequisites=["unit-0"],
        explanation_steps=["Read input", "Apply gain", "Output signal"],
        related_concepts=["PID 控制器"],
        source_refs=[source_ref],
        confusion_points=["Gain is not an integrator."],
    )

    assert unit.id == "unit-1"
    assert unit.title == "Gain block"
    assert unit.target == "block"
    assert unit.target_id == "node-1"
    assert unit.level == "beginner"
    assert unit.summary == "Explains the gain block."
    assert unit.prerequisites == ["unit-0"]
    assert unit.explanation_steps == ["Read input", "Apply gain", "Output signal"]
    assert unit.related_concepts == ["PID 控制器"]
    assert unit.source_refs == [source_ref]
    assert unit.confusion_points == ["Gain is not an integrator."]
