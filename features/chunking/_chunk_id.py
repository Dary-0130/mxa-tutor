"""Deterministic chunk identifiers."""

from __future__ import annotations

import hashlib
import re
from typing import Final

from core.interfaces.vector_store import SourceType

_HASH_LEN: Final[int] = 12
_SAFE_ID_MAX_LEN: Final[int] = 80
_SAFE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-zA-Z0-9_./-]")


def _sanitize_identifier(raw: str) -> str:
    return _SAFE_ID_PATTERN.sub("_", raw)[:_SAFE_ID_MAX_LEN]


def make_chunk_id(project_id: str, source_type: SourceType, *identifier_parts: str) -> str:
    raw_id = "::".join(identifier_parts)
    if not raw_id:
        raise ValueError("empty_chunk_identifier")
    safe_id = _sanitize_identifier(raw_id)
    digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:_HASH_LEN]
    return f"{project_id}::{source_type}::{safe_id}::{digest}"


def make_overview_chunk_id(project_id: str) -> str:
    return f"{project_id}::project_overview"
