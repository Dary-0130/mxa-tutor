"""Pure Python ModelGenerationPlan domain contract."""

from dataclasses import dataclass

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_spec import PaperSpec


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
class StepBlockRef:
    """Block reference scoped to one model build step."""

    block_ref_id: str
    block_type: str
    library_path: str | None
    purpose: str
    paper_reference: PaperEvidenceEntry | None


@dataclass(frozen=True)
class ParameterMappingRef:
    """Reference to an existing paper-to-model parameter mapping."""

    paper_param_name: str
    model_param_name: str


@dataclass(frozen=True)
class ConnectionHint:
    """Human-readable block connection hint."""

    from_block_ref: str
    from_port: str | None
    to_block_ref: str
    to_port: str | None
    signal_meaning: str | None


@dataclass(frozen=True)
class ConfigurationHint:
    """Non-block model configuration hint."""

    target: str
    setting_name: str | None
    instruction: str
    evidence: list[PaperEvidenceEntry]


@dataclass(frozen=True)
class ModelBuildStep:
    """Structured human build step for later generation phases."""

    step_id: str
    title: str
    intent: str
    block_refs: list[StepBlockRef]
    parameter_refs: list[ParameterMappingRef]
    connection_hints: list[ConnectionHint]
    configuration_hints: list[ConfigurationHint]
    depends_on: list[str]
    evidence: list[PaperEvidenceEntry]
    display_text: str


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
    build_steps: list[ModelBuildStep] | None = None


@dataclass(frozen=True)
class PaperPlanRecord:
    """Internal persisted paper plan bundle assembled from spec and plan rows."""

    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingParameterBinding]
