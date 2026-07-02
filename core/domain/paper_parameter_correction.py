"""Domain contract for user parameter correction overlays."""

from dataclasses import dataclass

from core.domain.paper_evidence import EvidenceSource


@dataclass(frozen=True)
class PlanCorrectionTarget:
    """Stable pointer to the plan mapping corrected by a user."""

    paper_param_name: str
    model_param_name: str
    plan_mapping_index: int


@dataclass(frozen=True)
class PaperParameterCorrection:
    """Audit row for an overlay correction to a plan mapping value."""

    correction_id: str
    paper_id: str
    param_key: str
    plan_target: PlanCorrectionTarget
    original_value: str
    original_unit: str | None
    original_source: EvidenceSource
    original_document_id: str | None
    corrected_value: str
    corrected_unit: str | None
    created_at: str
    updated_at: str
