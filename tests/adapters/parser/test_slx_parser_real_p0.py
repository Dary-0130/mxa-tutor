from pathlib import Path

from adapters.parser.slx_parser import SlxParserImpl
from core.domain.slx_model import SlxModel


def test_pmsm_project_all_models_parse_with_dynamic_count(
    extracted_slx_projects: dict[str, list[Path]],
) -> None:
    slx_files = extracted_slx_projects["01_pmsm_foc_c2000"]
    models = _parse_all(slx_files)

    assert len(models) == len(slx_files)
    assert all(model.name for model in models)
    assert all(model.blocks for model in models)
    assert sum(1 for model in models if model.subsystems) >= min(5, len(models))
    assert any(
        any(
            keyword in block.name.lower()
            for keyword in ("inverter", "motor", "foc")
            for block in model.blocks
        )
        for model in models
    )


def test_buck_voltage_control_p0(
    extracted_slx_projects: dict[str, list[Path]],
) -> None:
    models = _parse_all(extracted_slx_projects["02_buck_voltage_control"])
    blocks = models[0].blocks

    assert models[0].name
    assert len(blocks) >= 5
    assert any(
        "PI" in block.block_type.upper() or "PID" in block.block_type.upper() for block in blocks
    )
    assert any(block.block_type.startswith("Simscape") for block in blocks) or any(
        "Simscape" in warning for warning in models[0].parse_warnings
    )


def test_pid_antiwindup_variants_p0(
    extracted_slx_projects: dict[str, list[Path]],
) -> None:
    models = _parse_all(extracted_slx_projects["03_pid_antiwindup"])

    assert len(models) == len(extracted_slx_projects["03_pid_antiwindup"])
    assert all(
        any(
            "PID" in block.block_type.upper() or "PID" in block.name.upper()
            for block in model.blocks
        )
        for model in models
    )
    assert (
        sum(
            1
            for model in models
            if any("SATUR" in block.block_type.upper() for block in model.blocks)
        )
        >= 2
    )


def test_lms_noise_cancel_variants_p0(
    extracted_slx_projects: dict[str, list[Path]],
) -> None:
    models = _parse_all(extracted_slx_projects["04_lms_noise_cancel"])

    assert len(models) == len(extracted_slx_projects["04_lms_noise_cancel"])
    assert all(model.blocks for model in models)
    assert any(
        any(
            "LMS" in block.block_type.upper() or "LMS" in block.name.upper()
            for block in model.blocks
        )
        for model in models
    )
    assert any(
        any(
            keyword in block.name.upper()
            for keyword in ("SPECTRUM", "SCOPE", "ARRAY PLOT")
            for block in model.blocks
        )
        for model in models
    )


def _parse_all(slx_files: list[Path]) -> list[SlxModel]:
    parser = SlxParserImpl()
    return [parser.parse(str(path)) for path in slx_files]
