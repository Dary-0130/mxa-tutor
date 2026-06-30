"""Paper feature helpers for single-document identity payloads."""

from __future__ import annotations

import copy
import re
from typing import Any

from core.domain.paper_document_identity import DEFAULT_DOCUMENT_ID, LEGACY_DOCUMENT_FILENAME
from core.domain.paper_evidence import EvidenceSource

PAPER_DISPLAY_FILENAME_MAX_LENGTH = 255

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_EVIDENCE_KEYS = frozenset(
    {
        "paper_section_id",
        "equation_id",
        "figure_id",
        "excerpt",
        "missing_param_prompt_id",
    }
)
_MISSING = object()


def sanitize_paper_display_filename(filename: str | None) -> str:
    """Return a safe display-only paper filename."""

    raw = str(filename or "")
    basename = raw.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    cleaned = _CONTROL_CHARS_RE.sub("", basename).strip()
    if not cleaned:
        return LEGACY_DOCUMENT_FILENAME
    return cleaned[:PAPER_DISPLAY_FILENAME_MAX_LENGTH]


def enrich_single_document_spec_payload(
    payload: dict[str, Any],
    *,
    display_filename: str | None,
    document_id: str = DEFAULT_DOCUMENT_ID,
) -> dict[str, Any]:
    """Inject server-owned single-document identity into a raw PaperSpec payload."""

    enriched = copy.deepcopy(payload)
    enriched["documents"] = [
        {
            "document_id": document_id,
            "filename": sanitize_paper_display_filename(display_filename),
        }
    ]
    enriched["primary_document_id"] = None
    for parameter in enriched.get("parameter_table", []):
        if not isinstance(parameter, dict):
            continue
        parameter_document_id = _document_id_for_source(parameter.get("source"), document_id)
        if parameter_document_id is not _MISSING:
            parameter["document_id"] = parameter_document_id
    for equation in enriched.get("equations", []):
        if isinstance(equation, dict):
            equation["document_id"] = document_id
    for figure in enriched.get("figure_locations", []):
        if isinstance(figure, dict):
            figure["document_id"] = document_id
    return enrich_single_document_evidence_payloads(enriched, document_id=document_id)


def enrich_single_document_evidence_payloads(
    value: Any,
    *,
    document_id: str = DEFAULT_DOCUMENT_ID,
) -> Any:
    """Inject DOC-001/None document IDs into raw LLM PaperEvidenceEntry payloads."""

    return _visit_evidence_payloads(value, override=True, document_id=document_id)


def _visit_evidence_payloads(value: Any, *, override: bool, document_id: str) -> Any:
    if isinstance(value, list):
        return [
            _visit_evidence_payloads(item, override=override, document_id=document_id)
            for item in value
        ]
    if not isinstance(value, dict):
        return value

    result = {
        key: _visit_evidence_payloads(item, override=override, document_id=document_id)
        for key, item in value.items()
    }
    if _looks_like_evidence_payload(result):
        resolved_document_id = _document_id_for_source(result.get("source"), document_id)
        if resolved_document_id is not _MISSING and (override or "document_id" not in result):
            result["document_id"] = resolved_document_id
    return result


def _looks_like_evidence_payload(value: dict[str, Any]) -> bool:
    return "source" in value and any(key in value for key in _EVIDENCE_KEYS)


def _document_id_for_source(source: object, document_id: str) -> str | None | object:
    if source in (EvidenceSource.DOCUMENT_EXTRACTED, EvidenceSource.DOCUMENT_EXTRACTED.value):
        return document_id
    if source in (EvidenceSource.USER_SUPPLIED, EvidenceSource.USER_SUPPLIED.value):
        return None
    return _MISSING
