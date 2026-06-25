from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_STATE_MACHINE = ROOT / "core" / "domain" / "bridge_run_state_machine.py"
FORBIDDEN_PREFIXES = (
    "adapters",
    "api",
    "fastapi",
    "features.explanation",
    "jose",
    "pydantic",
    "starlette",
)


def test_bridge_run_state_machine_keeps_core_boundary_pure() -> None:
    tree = ast.parse(RUN_STATE_MACHINE.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"{module}:{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"{alias.name}:{node.lineno}")

    assert offenders == []


def _is_forbidden(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES)
