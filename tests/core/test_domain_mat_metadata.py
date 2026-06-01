from core.domain.mat_metadata import MatMetadata, MatVariable


def test_mat_variable_required_fields() -> None:
    variable = MatVariable(
        name="Kp",
        var_type="double",
        shape=(1, 1),
        likely_role=None,
        first_field_names=[],
    )

    assert variable.name == "Kp"
    assert variable.var_type == "double"
    assert variable.shape == (1, 1)
    assert variable.likely_role is None
    assert variable.first_field_names == []


def test_mat_metadata_required_fields() -> None:
    variable = MatVariable(
        name="params",
        var_type="struct",
        shape=(1, 1),
        likely_role="param_table",
        first_field_names=["Kp", "Ki"],
    )
    metadata = MatMetadata(
        file_path="params.mat",
        file_size_bytes=1024,
        variables=[variable],
    )

    assert metadata.file_path == "params.mat"
    assert metadata.file_size_bytes == 1024
    assert metadata.variables == [variable]
