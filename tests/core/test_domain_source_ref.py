from core.domain.source_ref import SourceRef


def test_source_ref_minimal() -> None:
    ref = SourceRef(file_path="init_params.m")

    assert ref.file_path == "init_params.m"
    assert ref.line_range is None
    assert ref.block_id is None
    assert ref.block_name is None
    assert ref.parent_subsystem is None
    assert ref.parameter_name is None


def test_source_ref_full() -> None:
    ref = SourceRef(
        file_path="model.slx",
        line_range=(10, 20),
        block_id="SpeedLoop/PID",
        block_name="PID",
        parent_subsystem="SpeedLoop",
        parameter_name="Kp",
    )

    assert ref.line_range == (10, 20)
    assert ref.block_id == "SpeedLoop/PID"
    assert ref.block_name == "PID"
    assert ref.parent_subsystem == "SpeedLoop"
    assert ref.parameter_name == "Kp"
