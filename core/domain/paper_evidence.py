"""Pure Python paper-to-model evidence contract."""

from dataclasses import dataclass
from enum import Enum


class EvidenceSource(str, Enum):
    """Source marker for paper-to-model evidence."""

    DOCUMENT_EXTRACTED = "document_extracted"
    USER_SUPPLIED = "user_supplied"


class UserEvidenceAction(str, Enum):
    """Action represented by a user-supplied evidence entry."""

    FILL_MISSING = "fill_missing"
    CORRECT_EXTRACTED = "correct_extracted"


@dataclass(frozen=True)
class PaperEvidenceEntry:
    """Evidence entry for paper sections, equations, figures, or user-supplied params."""

    source: EvidenceSource
    document_id: str | None
    paper_section_id: str | None
    equation_id: str | None
    figure_id: str | None
    excerpt: str | None
    missing_param_prompt_id: str | None
    user_action: UserEvidenceAction | None = None
    parameter_correction_id: str | None = None
    correction_param_key: str | None = None
