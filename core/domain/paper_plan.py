"""Pure Python ModelGenerationPlan domain contract."""

from dataclasses import dataclass

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry


@dataclass(frozen=True)
class BlockRecommendation:
    """Recommended Simulink block and its paper evidence."""

    block_type: str
    purpose: str
    paper_reference: PaperEvidenceEntry


@dataclass(frozen=True)
class ParameterMapping:
    """Mapping from paper parameter to model parameter."""

    paper_param_name: str
    model_param_name: str
    value: str
    unit: str | None
    source: EvidenceSource


@dataclass(frozen=True)
class ModelGenerationPlan:
    """Route-map style model generation plan."""

    plan_id: str
    paper_spec_id: str
    library_choice: str
    block_recommendations: list[BlockRecommendation]
    parameter_mapping: list[ParameterMapping]
    subsystem_breakdown: list[str]
    m_script_skeleton: str | None
    evidence: list[PaperEvidenceEntry]
