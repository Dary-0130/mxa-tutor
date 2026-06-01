from core.domain.m_file import MFile, MFunction


def test_m_function_required_fields() -> None:
    func = MFunction(
        name="compute_gain",
        inputs=["x"],
        outputs=["y"],
        line_range=(1, 10),
        docstring="Compute gain.",
    )

    assert func.name == "compute_gain"
    assert func.inputs == ["x"]
    assert func.outputs == ["y"]
    assert func.line_range == (1, 10)
    assert func.docstring == "Compute gain."


def test_m_file_required_fields() -> None:
    func = MFunction(
        name="compute_gain",
        inputs=["x"],
        outputs=["y"],
        line_range=(1, 10),
        docstring=None,
    )
    m_file = MFile(
        file_path="compute_gain.m",
        file_role="function",
        functions=[func],
        imports=["simulink"],
        uses_toolbox=["Control System Toolbox"],
        raw_code="function y = compute_gain(x)\ny = x;\nend",
    )

    assert m_file.file_path == "compute_gain.m"
    assert m_file.file_role == "function"
    assert m_file.functions == [func]
    assert m_file.imports == ["simulink"]
    assert m_file.uses_toolbox == ["Control System Toolbox"]
    assert "compute_gain" in m_file.raw_code
