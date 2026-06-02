from pathlib import Path

from adapters.parser.m_parser import MParserImpl

EXPECTED: dict[str, tuple[str, int, str | None]] = {
    "FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample.m": ("script", 0, None),
    "mcb_c2000_pmsm_offset_data.m": ("script", 0, None),
    "mcb_pmsm_foc_f280049C_data.m": ("script", 0, None),
    "mcb_pmsm_foc_f28335_data.m": ("script", 0, None),
    "mcb_pmsm_foc_qep_f28035_data.m": ("script", 0, None),
    "BuckVoltageControlData.m": ("script", 0, None),
    "BuckVoltageControlExample.m": ("script", 0, None),
    "BuckVoltageControlPlotVoltage.m": ("script", 0, None),
    "simlogNeedsUpdate.m": ("function", 1, "simlogNeedsUpdate"),
    "AntiWindupControlUsingAPIDControllerExample.m": ("script", 0, None),
    "AcousticNoiseCancellationLMSExample.m": ("script", 0, None),
}


def test_all_real_m_files_match_v13_matrix(
    extracted_m_files: dict[str, list[Path]],
) -> None:
    parser = MParserImpl()
    all_paths = [path for paths in extracted_m_files.values() for path in paths]

    assert len(all_paths) == 11
    assert {path.name for path in all_paths} == set(EXPECTED)

    parsed = {path.name: parser.parse(str(path)) for path in all_paths}

    assert sum(1 for mfile in parsed.values() if mfile.file_role == "script") == 10
    assert sum(1 for mfile in parsed.values() if mfile.file_role == "function") == 1
    assert sum(1 for mfile in parsed.values() if mfile.file_role == "class") == 0

    for filename, (role, function_count, first_function) in EXPECTED.items():
        mfile = parsed[filename]
        assert mfile.file_role == role
        assert len(mfile.functions) >= function_count
        if function_count == 0:
            assert mfile.functions == []
        if first_function is not None:
            assert mfile.functions[0].name == first_function
        assert mfile.file_path
        assert mfile.raw_code
        assert isinstance(mfile.imports, list)
        assert all(isinstance(item, str) for item in mfile.imports)
        assert isinstance(mfile.uses_toolbox, list)
        assert all(isinstance(item, str) for item in mfile.uses_toolbox)
