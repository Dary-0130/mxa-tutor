from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = [
    ROOT / "core",
    ROOT / "features",
    ROOT / "api",
]
ALLOWLIST = {
    ROOT / "api" / "main.py",
}


def test_concrete_matlab_engine_adapter_imports_stay_in_composition_root() -> None:
    offenders: list[str] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*.py"):
            if path in ALLOWLIST:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "adapters.matlab_engine" or module.startswith(
                        "adapters.matlab_engine."
                    ):
                        offenders.append(_display(path, node.lineno))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "adapters.matlab_engine" or alias.name.startswith(
                            "adapters.matlab_engine."
                        ):
                            offenders.append(_display(path, node.lineno))

    assert offenders == []


def _display(path: Path, lineno: int) -> str:
    return f"{path.relative_to(ROOT)}:{lineno}"
