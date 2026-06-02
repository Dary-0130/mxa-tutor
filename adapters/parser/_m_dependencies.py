import re

TOOLBOX_FUNCTIONS: dict[str, set[str]] = {
    "Control System Toolbox": {
        "tf",
        "zpk",
        "ss",
        "feedback",
        "series",
        "parallel",
        "bode",
        "nyquist",
        "rlocus",
        "lsim",
        "pid",
        "pidtune",
        "margin",
        "stepinfo",
        "pole",
        "zero",
    },
    "Signal Processing Toolbox": {
        "designfilt",
        "butter",
        "cheby1",
        "cheby2",
        "ellip",
        "freqz",
        "spectrogram",
        "pwelch",
        "xcorr",
        "resample",
        "decimate",
        "upfirdn",
    },
    "Communications Toolbox": {
        "qammod",
        "qamdemod",
        "pskmod",
        "pskdemod",
        "awgn",
        "berawgn",
        "rcosdesign",
        "scatterplot",
        "comm.AWGNChannel",
        "comm.PSKModulator",
        "comm.QAMDemodulator",
    },
    "Optimization Toolbox": {
        "optimoptions",
        "fmincon",
        "fminunc",
        "lsqnonlin",
        "lsqlin",
        "quadprog",
        "linprog",
        "fsolve",
    },
    "System Identification Toolbox": {"iddata", "tfest", "ssest", "arx", "n4sid"},
    "Simulink": {
        "sim",
        "set_param",
        "get_param",
        "find_system",
        "add_block",
        "open_system",
        "close_system",
        "save_system",
        "new_system",
    },
    "DSP System Toolbox": {
        "dsp.LMSFilter",
        "dsp.FIRFilter",
        "dsp.SpectrumAnalyzer",
        "dsp.AudioFileReader",
        "dsp.AudioFileWriter",
        "dsp.SineWave",
    },
    "Simscape Electrical": {"ee.getModelVariants", "ee.getNetlistVariants"},
    "Motor Control Blockset": {"mcb_getTrajectory", "mcb_calculateRsLq", "mcb.internal"},
    "Fixed-Point Designer": {"fi", "fimath", "numerictype"},
    "Embedded Coder": {"rtwbuild", "slbuild", "codegen", "rtw.connectivity"},
}


def extract_imports(preprocessed_code: str) -> list[str]:
    """提取 MATLAB import 目标,去重并保持出现顺序。"""
    imports: list[str] = []
    seen: set[str] = set()
    for match in _IMPORT_RE.finditer(preprocessed_code):
        target = match.group(1)
        if target not in seen:
            seen.add(target)
            imports.append(target)
    return imports


def detect_toolboxes(preprocessed_code: str) -> list[str]:
    """启发式检测 .m 代码使用的 toolbox。"""
    result: list[str] = []
    for toolbox_name, function_names in TOOLBOX_FUNCTIONS.items():
        if any(_matches_toolbox_function(preprocessed_code, name) for name in function_names):
            result.append(toolbox_name)
    return result


def _matches_toolbox_function(preprocessed_code: str, name: str) -> bool:
    pattern = r"\b" + re.escape(name) + r"\b" if "." in name else r"\b" + re.escape(name) + r"\s*\("
    return re.search(pattern, preprocessed_code) is not None


_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+(?:\.\*)?)\s*;?\s*$", re.MULTILINE)
