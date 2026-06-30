"""Document identity validation helpers for PaperSpec contracts."""

from __future__ import annotations

import re

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_spec import PaperSpec

DEFAULT_DOCUMENT_ID = "DOC-001"
LEGACY_DOCUMENT_FILENAME = "legacy_document"
DOCUMENT_ID_PATTERN = r"^DOC-\d{3}$"
_DOCUMENT_ID_RE = re.compile(DOCUMENT_ID_PATTERN)


def validate_paper_spec_document_identity(spec: PaperSpec) -> None:
    """Validate document identity invariants spanning a PaperSpec."""

    if not spec.documents:
        raise ValueError("documents must not be empty")

    document_ids: list[str] = []
    for document in spec.documents:
        if _DOCUMENT_ID_RE.fullmatch(document.document_id) is None:
            raise ValueError("document_id must match DOC-###")
        document_ids.append(document.document_id)

    document_id_set = set(document_ids)
    if len(document_id_set) != len(document_ids):
        raise ValueError("document_id values must be unique")

    if spec.primary_document_id is not None and spec.primary_document_id not in document_id_set:
        raise ValueError("primary_document_id must reference documents")

    for entry in spec.evidence:
        _validate_document_ref(
            source=entry.source,
            document_id=entry.document_id,
            document_id_set=document_id_set,
            item_name="evidence",
        )
    for parameter in spec.parameter_table:
        _validate_document_ref(
            source=parameter.source,
            document_id=parameter.document_id,
            document_id_set=document_id_set,
            item_name="parameter",
        )


def _validate_document_ref(
    *,
    source: EvidenceSource,
    document_id: str | None,
    document_id_set: set[str],
    item_name: str,
) -> None:
    if source is EvidenceSource.DOCUMENT_EXTRACTED:
        if document_id is None:
            raise ValueError(f"document_extracted {item_name} requires document_id")
        if document_id not in document_id_set:
            raise ValueError(f"document_extracted {item_name} document_id must reference documents")
        return

    if source is EvidenceSource.USER_SUPPLIED:
        if document_id is not None:
            raise ValueError(f"user_supplied {item_name} document_id must be null")
        return

    raise ValueError(f"unknown {item_name} source")
