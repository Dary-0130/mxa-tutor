import re
import xml.etree.ElementTree as ET

SOLVER_KEYS = {
    "StartTime": "StartTime",
    "StopTime": "StopTime",
    "Solver": "Solver",
    "SolverName": "Solver",
    "SolverType": "SolverType",
    "FixedStep": "FixedStep",
}

IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
IGNORED_IDENTIFIERS = {
    "Inf",
    "NaN",
    "Inherit",
    "auto",
    "off",
    "on",
    "pi",
    "sin",
    "cos",
    "tan",
    "exp",
    "sqrt",
    "fir1",
    "fixdt",
}
IGNORED_PARAMETER_KEYS = {
    "BlockType",
    "ForegroundColor",
    "BackgroundColor",
    "FontName",
    "FontWeight",
    "HorizontalAlignment",
    "NameLocation",
    "SourceType",
    "ShowName",
}
WORKSPACE_PARAMETER_KEYS = {
    "Value",
    "Gain",
    "Kp",
    "Ki",
    "P",
    "I",
    "D",
    "SampleTime",
    "SampTime",
    "FixedStep",
    "Coefficients",
    "Numerator",
    "Denominator",
    "InitialCondition",
}


def parse_solver_config(config_root: ET.Element | None, warnings: list[str]) -> dict[str, str]:
    """提取 solver 关键配置。"""
    if config_root is None:
        return {}

    solver_object = None
    for obj in config_root.iter():
        class_name = obj.get("ClassName") or obj.get("Class") or ""
        if "SolverCC" in class_name:
            solver_object = obj
            break
    if solver_object is None:
        warnings.append("solver 配置解析失败,已跳过:未找到 Simulink.SolverCC")
        return {}

    config: dict[str, str] = {}
    for param in solver_object.iter("P"):
        name = param.get("Name")
        if name in SOLVER_KEYS and param.text is not None:
            config[SOLVER_KEYS[name]] = param.text.strip()
    return config


def is_masked(block_elem: ET.Element) -> bool:
    """判断 block 是否含 mask 信息。"""
    for elem in block_elem.iter():
        if elem.tag == "Mask":
            return True
        if elem.tag == "P" and elem.get("Name") in {"Mask", "MaskType"}:
            return True
    return False


def is_library_link(block_elem: ET.Element) -> bool:
    """判断 block 是否引用 library。"""
    source = _first_param(block_elem, "SourceBlock")
    return bool(source and "/" in source)


def is_model_reference(block_elem: ET.Element, block_type: str) -> bool:
    """判断 block 是否为 model reference。"""
    return block_type == "ModelReference" or _first_param(block_elem, "ModelName") is not None


def collect_workspace_warnings(parameters: dict[str, str]) -> list[str]:
    """从参数中粗略识别 workspace 变量引用。"""
    found: set[str] = set()
    for key, value in parameters.items():
        if key in IGNORED_PARAMETER_KEYS or key in {"SourceBlock", "GraphicalSettings"}:
            continue
        if key not in WORKSPACE_PARAMETER_KEYS and "Gain" not in key:
            continue
        if len(value) > 120 or "/" in value:
            continue
        if " " in value and not any(marker in value for marker in "()[]+-*/"):
            continue
        for ident in IDENTIFIER_RE.findall(value):
            if ident not in IGNORED_IDENTIFIERS and not ident.startswith("uint"):
                found.add(ident)
    if not found:
        return []
    names = ", ".join(sorted(found)[:20])
    return [f"发现可能的 workspace 变量引用:{names}"]


def _first_param(block_elem: ET.Element, name: str) -> str | None:
    for param in block_elem.iter("P"):
        if param.get("Name") == name and param.text:
            return param.text.strip()
    return None
