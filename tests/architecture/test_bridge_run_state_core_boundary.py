from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_STATE_MACHINE = ROOT / "core" / "domain" / "bridge_run_state_machine.py"
RUN_STATE_COACHING_DOMAIN = ROOT / "core" / "domain" / "bridge_run_state_coaching.py"
RUN_STATE_COACHING_READER = ROOT / "core" / "interfaces" / "coaching_run_state_reader.py"
RUN_STATE_COACHING_CROSS_ROUND_READER = (
    ROOT / "core" / "interfaces" / "coaching_cross_round_reader.py"
)
RUN_STATE_COACHING_SERVICE = (
    ROOT / "features" / "matlab_bridge" / "bridge_run_state_coaching_service.py"
)
FORBIDDEN_PREFIXES = (
    "adapters",
    "api",
    "fastapi",
    "features.explanation",
    "jose",
    "pydantic",
    "starlette",
)
SERVICE_FORBIDDEN_PREFIXES = (
    "adapters",
    "features.explanation",
    "features.matlab_bridge.bridge_explanation_service",
)


def test_bridge_run_state_machine_keeps_core_boundary_pure() -> None:
    assert _import_offenders(RUN_STATE_MACHINE, FORBIDDEN_PREFIXES) == []


def test_bridge_run_state_coaching_domain_and_reader_keep_core_boundary_pure() -> None:
    assert _import_offenders(RUN_STATE_COACHING_DOMAIN, FORBIDDEN_PREFIXES) == []
    assert _import_offenders(RUN_STATE_COACHING_READER, FORBIDDEN_PREFIXES) == []
    assert _import_offenders(RUN_STATE_COACHING_CROSS_ROUND_READER, FORBIDDEN_PREFIXES) == []


def test_bridge_run_state_coaching_service_uses_reader_abc_not_adapter_private_imports() -> None:
    offenders = _import_offenders(RUN_STATE_COACHING_SERVICE, SERVICE_FORBIDDEN_PREFIXES)
    source = RUN_STATE_COACHING_SERVICE.read_text(encoding="utf-8")

    assert offenders == []
    assert "CoachingCrossRoundReader" in source
    assert "sqlite_bridge_run_state_store" not in source
    assert "_run_state_coaching_draft" in source
    assert "features.explanation" not in source


def _import_offenders(path: Path, forbidden_prefixes: tuple[str, ...]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module, forbidden_prefixes):
                offenders.append(f"{module}:{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name, forbidden_prefixes):
                    offenders.append(f"{alias.name}:{node.lineno}")

    return offenders


def _is_forbidden(module: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
