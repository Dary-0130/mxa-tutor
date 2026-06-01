from pathlib import Path

from adapters.parser.slx_parser import SlxParserImpl
from core.domain.slx_model import SlxModel


def test_real_projects_p1_at_least_three_of_four(
    extracted_slx_projects: dict[str, list[Path]],
) -> None:
    parser = SlxParserImpl()
    parsed = {
        project: [parser.parse(str(path)) for path in slx_files]
        for project, slx_files in extracted_slx_projects.items()
    }

    results = {
        "01_pmsm_foc_c2000": _pmsm_p1(parsed["01_pmsm_foc_c2000"]),
        "02_buck_voltage_control": _buck_p1(parsed["02_buck_voltage_control"]),
        "03_pid_antiwindup": _pid_p1(parsed["03_pid_antiwindup"]),
        "04_lms_noise_cancel": _lms_p1(parsed["04_lms_noise_cancel"]),
    }

    assert sum(results.values()) >= 3, results


def _common_solver_p1(models: list[SlxModel]) -> bool:
    return all(
        model.solver_config
        and ("Solver" in model.solver_config or "SolverType" in model.solver_config)
        for model in models
    ) and any(model.solver_config.get("StopTime") for model in models)


def _pmsm_p1(models: list[SlxModel]) -> bool:
    has_mask_or_library = any(
        block.is_masked or block.is_library_link for model in models for block in model.blocks
    )
    return _common_solver_p1(models) and has_mask_or_library


def _buck_p1(models: list[SlxModel]) -> bool:
    return _common_solver_p1(models) and bool(models[0].solver_config.get("StopTime"))


def _pid_p1(models: list[SlxModel]) -> bool:
    pid_blocks_have_gain = all(
        any(
            ("PID" in block.block_type.upper() or "PID" in block.name.upper())
            and {"P", "I", "D"}.intersection(block.parameters)
            for block in model.blocks
        )
        for model in models
    )
    return _common_solver_p1(models) and pid_blocks_have_gain


def _lms_p1(models: list[SlxModel]) -> bool:
    warnings = "\n".join(warning for model in models for warning in model.parse_warnings)
    fatal_words_absent = "崩溃" not in warnings and "无法解析" not in warnings
    return _common_solver_p1(models) and fatal_words_absent
