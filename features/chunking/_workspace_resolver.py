"""Extract base workspace literals from .m files.

Temporary shim for variable resolution until 0.4 阶段's parameter graph
(ParameterNode + READS_PARAM edges). When that's in place, delete this
module and read from ProjectGraph instead.
"""

from __future__ import annotations

import re

from core.domain.m_file import MFile

__all__ = ["extract_workspace_literals", "is_unresolved_var_ref"]

_SCALAR_LITERAL_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(-?\d+\.?\d*(?:[eE][+-]?\d+)?|'[^']*'|\"[^\"]*\")"
    r"\s*;?\s*(?:%.*)?$"
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def extract_workspace_literals(m_files: list[MFile]) -> dict[str, str]:
    """Extract scalar literal assignments from .m files' base workspace."""
    literals: dict[str, str] = {}
    for m_file in m_files:
        for line in m_file.raw_code.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("%"):
                continue

            match = _SCALAR_LITERAL_RE.match(line)
            if match:
                name, value = match.group(1), match.group(2)
                literals[name] = value
    return literals


def is_unresolved_var_ref(value: str, literals: dict[str, str]) -> bool:
    """Return True when value is a bare identifier absent from literals."""
    stripped = value.strip()
    if not _IDENTIFIER_RE.match(stripped):
        return False
    return stripped not in literals
