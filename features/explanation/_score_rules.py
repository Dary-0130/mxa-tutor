"""Rule tables for explanation evidence block scoring."""

from __future__ import annotations

import re

from core.domain.slx_model import SlxBlock

E1_TYPES: dict[str, tuple[str, ...]] = {
    "input_source": (
        "Constant",
        "Step",
        "Ramp",
        "Signal Builder",
        "Signal Generator",
        "Sine Wave",
        "Pulse Generator",
        "Repeating Sequence",
        "From Workspace",
        "Clock",
        "Random Number",
    ),
    "math_control": (
        "Gain",
        "Sum",
        "Add",
        "Product",
        "Divide",
        "Integrator",
        "Discrete-Time Integrator",
        "Unit Delay",
        "Delay",
        "Memory",
        "Transfer Fcn",
        "Discrete Transfer Fcn",
        "State-Space",
        "PID Controller",
        "Saturation",
        "Rate Limiter",
        "Relay",
        "Dead Zone",
        "Switch",
        "Multiport Switch",
        "Lookup Table",
        "1-D Lookup Table",
        "2-D Lookup Table",
        "MATLAB Function",
    ),
    "routing": (
        "Inport",
        "Outport",
        "Goto",
        "From",
        "Bus Selector",
        "Bus Creator",
        "Mux",
        "Demux",
        "Selector",
        "Terminator",
        "Data Store Memory",
        "Data Store Read",
        "Data Store Write",
    ),
    "measurement": (
        "Scope",
        "Display",
        "To Workspace",
        "To File",
        "XY Graph",
        "Voltage Measurement",
        "Current Measurement",
        "Three-Phase VI Measurement",
        "Power Measurement",
        "RMS",
        "Fourier",
        "FFT",
    ),
    "power": (
        "powergui",
        "Universal Bridge",
        "Three-Phase Series RLC Branch",
        "Three-Phase Parallel RLC Branch",
        "Series RLC Branch",
        "Parallel RLC Branch",
        "Three-Phase Source",
        "AC Voltage Source",
        "DC Voltage Source",
        "Controlled Voltage Source",
        "Controlled Current Source",
        "Breaker",
        "Ideal Switch",
        "IGBT",
        "Diode",
        "Thyristor",
        "MOSFET",
        "Transformer",
        "Three-Phase Transformer",
        "Two-Winding Transformer",
        "Asynchronous Machine",
        "Synchronous Machine",
        "Permanent Magnet Synchronous Machine",
        "DC Machine",
    ),
}

TYPE_ALIASES = {
    "BusCreator": "Bus Creator",
    "BusSelector": "Bus Selector",
    "FromWorkspace": "From Workspace",
    "RandomNumber": "Random Number",
    "Saturate": "Saturation",
    "ToWorkspace": "To Workspace",
    "TransferFcn": "Transfer Fcn",
    "UnitDelay": "Unit Delay",
}

DOMAIN_KEYWORDS = (
    "pll",
    "pwm",
    "svpwm",
    "spwm",
    "dq",
    "abc",
    "clarke",
    "park",
    "abc-dq",
    "dq-abc",
    "grid",
    "converter",
    "inverter",
    "rectifier",
    "dc link",
    "dc bus",
    "current control",
    "voltage control",
    "speed control",
    "rotor",
    "stator",
    "mppt",
    "dfig",
    "pmsm",
)

ELECTRICAL_SYMBOLS = {
    "abc",
    "dq",
    "i",
    "ia",
    "ib",
    "ic",
    "id",
    "idc",
    "idq",
    "iq",
    "kd",
    "ki",
    "kp",
    "p",
    "pll",
    "pref",
    "pu",
    "pwm",
    "q",
    "qref",
    "te",
    "tref",
    "ts",
    "v",
    "va",
    "vab",
    "vac",
    "vb",
    "vbc",
    "vc",
    "vca",
    "vdc",
    "vd",
    "vdq",
    "vq",
    "vref",
    "wm",
    "wr",
}

STRUCTURAL_PARAMS = {
    "AttributesFormatString",
    "BackgroundColor",
    "BlockType",
    "ContentPreviewEnabled",
    "FontName",
    "FontSize",
    "ForegroundColor",
    "LibrarySourceBlock",
    "LibraryVersion",
    "Name",
    "NameLocation",
    "Position",
    "ShowName",
    "SourceBlock",
    "SourceType",
    "ZOrder",
}

DEFAULT_VALUES = {"", "0", "0.0", "[]", "[0]", "[ 0 ]", "-1", "auto", "off", "none", "None"}
AMBIGUOUS_TYPE_WORDS = (
    "constant",
    "gain",
    "sum",
    "add",
    "product",
    "switch",
    "scope",
    "from",
    "goto",
    "mux",
    "demux",
    "selector",
    "saturation",
    "integrator",
    "delay",
    "relay",
    "display",
    "inport",
    "outport",
)
AMBIGUOUS_GENERIC_WORDS = (
    "block",
    "subsystem",
    "model",
    "chart",
    "signal",
    "input",
    "output",
    "data",
)


def normalize_block_type(block_type: str) -> str:
    return TYPE_ALIASES.get(block_type.strip(), block_type.strip())


def classify_block_type(block_type: str) -> str | None:
    normalized = normalize_block_type(block_type)
    low = normalized.lower()
    for category, block_types in E1_TYPES.items():
        for item in block_types:
            item_low = item.lower()
            if low == item_low or item_low in low or low in item_low:
                return category
    return None


def has_domain_keyword(block: SlxBlock) -> bool:
    text = f"{block.name} {block.parent_subsystem or ''}".lower().replace("_", " ")
    return any(keyword in text for keyword in DOMAIN_KEYWORDS)


def is_ambiguously_named(block: SlxBlock) -> bool:
    name = (block.name or "").strip()
    if not name:
        return True
    low = re.sub(r"[\s_-]+", "", name).lower()
    if low in ELECTRICAL_SYMBOLS:
        return False
    if re.fullmatch(rf"({'|'.join(AMBIGUOUS_TYPE_WORDS)})\d*", low):
        return True
    if re.fullmatch(rf"({'|'.join(AMBIGUOUS_GENERIC_WORDS)})\d*", low):
        return True
    if (len(low) <= 2 and low not in ELECTRICAL_SYMBOLS) or re.fullmatch(r"\d+", low):
        return True
    return classify_block_type(block.block_type) is not None and not has_domain_keyword(block)


def nondefault_parameters(block: SlxBlock) -> tuple[tuple[str, str], ...]:
    items: list[tuple[str, str]] = []
    for key, value in sorted((block.parameters or {}).items()):
        if key in STRUCTURAL_PARAMS or key.startswith("RTW"):
            continue
        text = str(value).strip()
        if text in DEFAULT_VALUES:
            continue
        items.append((key, text))
    return tuple(items)
