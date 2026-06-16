"""Prompt template loader for paper-to-model extraction."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptTemplate:
    """Loaded prompt template."""

    version: str
    description: str
    system: str
    user: str


PROMPT_DIR = Path(__file__).resolve().parents[2] / "core" / "prompts"


@lru_cache(maxsize=16)
def load_prompt_template(filename: str = "paper_spec_extract.yaml") -> PromptTemplate:
    """Load a prompt template from ``core/prompts``."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("invalid prompt template filename")

    path = PROMPT_DIR / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("prompt template must be a mapping")

    values: dict[str, Any] = data
    return PromptTemplate(
        version=_required_str(values, "version"),
        description=_required_str(values, "description"),
        system=_required_str(values, "system"),
        user=_required_str(values, "user"),
    )


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("prompt template field missing")
    return value
