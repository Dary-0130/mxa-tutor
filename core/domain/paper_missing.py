"""Pure Python MissingParameterPrompt domain contract."""

from dataclasses import dataclass

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry


@dataclass(frozen=True)
class MissingParameterPrompt:
    """Prompt asking the user to supply a parameter that text extraction could not recover."""

    prompt_id: str
    parameter_name: str
    paper_reference: PaperEvidenceEntry
    suggested_unit: str | None
    user_supplied_value: str | None
    user_supplied_unit: str | None
    source: EvidenceSource = EvidenceSource.USER_SUPPLIED
