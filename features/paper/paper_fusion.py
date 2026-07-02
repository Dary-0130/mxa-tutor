"""Shared successful-paper fusion logic for upload and reparse."""

from __future__ import annotations

from dataclasses import dataclass

from core.domain.exceptions import DocumentParseError
from core.domain.paper_document_identity import validate_paper_spec_document_identity
from core.domain.paper_parameter_conflicts import with_parameter_conflicts
from core.domain.paper_spec import PaperSpec


@dataclass(frozen=True)
class SuccessfulPaperSpec:
    """One successfully extracted document spec with backend-owned identity."""

    upload_index: int
    document_id: str
    filename: str
    spec: PaperSpec


def document_id_for_upload_index(index: int) -> str:
    """Return the backend-owned document id for a zero-based upload index."""

    return f"DOC-{index + 1:03d}"


def fuse_successful_specs(
    successes: list[SuccessfulPaperSpec],
    primary_index: int | None,
) -> PaperSpec:
    """Fuse successful document specs while preserving upload index gaps."""

    representative = _representative_success(successes, primary_index)
    primary_document_id = representative.document_id if primary_index is not None else None
    spec = PaperSpec(
        paper_title=representative.spec.paper_title,
        paper_type=representative.spec.paper_type,
        domain=representative.spec.domain,
        documents=[
            document
            for success in successes
            for document in success.spec.documents
            if document.document_id == success.document_id
        ],
        primary_document_id=primary_document_id,
        abstract=representative.spec.abstract,
        equations=[equation for success in successes for equation in success.spec.equations],
        parameter_table=[
            parameter for success in successes for parameter in success.spec.parameter_table
        ],
        figure_locations=[
            figure for success in successes for figure in success.spec.figure_locations
        ],
        pseudocode_blocks=[
            block for success in successes for block in success.spec.pseudocode_blocks
        ],
        evidence=[entry for success in successes for entry in success.spec.evidence],
    )
    spec = with_parameter_conflicts(spec)
    validate_paper_spec_document_identity(spec)
    return spec


def _representative_success(
    successes: list[SuccessfulPaperSpec],
    primary_index: int | None,
) -> SuccessfulPaperSpec:
    if primary_index is None:
        return successes[0]
    for success in successes:
        if success.upload_index == primary_index:
            return success
    raise DocumentParseError("primary_document_failed") from None
