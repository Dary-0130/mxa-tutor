from pathlib import Path

import pytest

from adapters.parser.dependency_analyzer import analyze_dependencies
from adapters.parser.file_classifier import classify_files
from adapters.parser.m_parser import MParserImpl
from adapters.parser.zip_extractor import safe_extract
from app.config import AppSettings

SLX_SAMPLES_DIR = Path(__file__).parents[2] / "fixtures" / "slx_samples"

EXPECTED_DEPENDENCIES: dict[str, dict[str, list[str]]] = {
    "01_pmsm_foc_c2000.zip": {
        "FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample/"
        "FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample.m": [
            "FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample/"
            "mcb_pmsm_foc_host_model.slx",
            "FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample/"
            "mcb_pmsm_foc_qep_f28035.slx",
        ]
    },
    "02_buck_voltage_control.zip": {
        "BuckVoltageControlExample/BuckVoltageControlExample.m": [
            "BuckVoltageControlExample/BuckVoltageControl.slx"
        ],
        "BuckVoltageControlExample/BuckVoltageControlPlotVoltage.m": [
            "BuckVoltageControlExample/BuckVoltageControl.slx",
            "BuckVoltageControlExample/simlogNeedsUpdate.m",
        ],
    },
    "03_pid_antiwindup.zip": {
        "AntiWindupControlUsingAPIDControllerExample/"
        "AntiWindupControlUsingAPIDControllerExample.m": [
            "AntiWindupControlUsingAPIDControllerExample/sldemo_antiwindup.slx",
            "AntiWindupControlUsingAPIDControllerExample/sldemo_antiwindupactuator.slx",
            "AntiWindupControlUsingAPIDControllerExample/sldemo_antiwindupfeedforward.slx",
        ]
    },
    "04_lms_noise_cancel.zip": {
        "AcousticNoiseCancellationLMSExample/AcousticNoiseCancellationLMSExample.m": [
            "AcousticNoiseCancellationLMSExample/dspanc.slx"
        ]
    },
}


def _settings(upload_dir: Path) -> AppSettings:
    return AppSettings(deepseek_api_key="test", upload_dir=str(upload_dir))


@pytest.mark.parametrize("zip_path", sorted(SLX_SAMPLES_DIR.glob("*.zip")))
def test_real_project_dependencies(tmp_path: Path, zip_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    dest = upload_root / zip_path.stem
    dest.mkdir(parents=True)

    extracted = safe_extract(zip_path.read_bytes(), dest, _settings(upload_root))
    file_infos = classify_files(extracted, extracted)
    parser = MParserImpl()
    m_files = [
        parser.parse(str(extracted / file_info.relative_path))
        for file_info in file_infos
        if file_info.file_type == ".m"
    ]

    assert (
        analyze_dependencies(file_infos, m_files, project_root=str(extracted))
        == (EXPECTED_DEPENDENCIES[zip_path.name])
    )
