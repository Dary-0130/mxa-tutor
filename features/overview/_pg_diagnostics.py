"""Internal diagnostics collected while building ProjectGraph."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["_BuildDiagnostics"]


@dataclass
class _BuildDiagnostics:
    """Diagnostic aggregation for internal ProjectGraph builder steps."""

    _entries: dict[str, set[str]] = field(default_factory=dict)

    def add(self, category: str, name: str) -> None:
        """Record one diagnostic entry."""
        self._entries.setdefault(category, set()).add(name)

    def collect(self) -> list[str]:
        """Return sorted entries formatted as ``category:name``."""
        result: list[str] = []
        for category in sorted(self._entries):
            for name in sorted(self._entries[category]):
                result.append(f"{category}:{name}")
        return result
