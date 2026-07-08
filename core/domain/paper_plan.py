"""Pure Python ModelGenerationPlan domain contract."""

from dataclasses import dataclass
from typing import Literal

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
class GuidanceAssessment:
    """Machine-coded assessment summary for build guidance."""

    content_status: Literal["reproducible_candidate", "outline_with_gaps", "outline_only"]
    environment_status: Literal["not_checked", "compatible", "missing_toolbox", "incompatible"]
    overall_status: Literal[
        "reproducible_ready",
        "reproducible_candidate_env_unchecked",
        "outline_with_gaps",
        "outline_only",
    ]
    blocking_gap_ids: list[str]


@dataclass(frozen=True)
class GuidanceDetail:
    """One structured build guidance detail."""

    detail_id: str
    step_id: str
    detail_kind: Literal[
        "block_selection",
        "subsystem_internal_structure",
        "connection",
        "parameter_value",
        "configuration",
        "verification",
        "gap_notice",
    ]
    basis: Literal[
        "document_extracted",
        "engineering_convention",
        "user_confirmation_required",
    ]
    actionability: Literal[
        "actionable",
        "notice_only",
        "blocked_pending_confirmation",
    ]
    display_text: str
    evidence: list[PaperEvidenceEntry]
    convention_code: str | None
    confirmation_reason_code: str | None


@dataclass(frozen=True)
class GuidanceGap:
    """Machine-coded gap surfaced by build guidance."""

    gap_id: str
    gap_kind: Literal[
        "missing_support_component",
        "missing_parameter_value",
        "toolbox_unverified",
        "library_variant_unresolved",
        "missing_connection_detail",
        "missing_configuration_detail",
        "insufficient_document_evidence",
    ]
    scope: Literal["plan", "step", "subsystem"]
    step_id: str | None
    basis: Literal["engineering_convention", "user_confirmation_required"]
    severity: Literal["blocking", "warning"]
    display_text: str


@dataclass(frozen=True)
class BuildGuidance:
    """Structured build guidance contract for later generation phases."""

    version: Literal["v1"]
    assessment: GuidanceAssessment
    details: list[GuidanceDetail]
    gaps: list[GuidanceGap]


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
    build_guidance: BuildGuidance | None = None


@dataclass(frozen=True)
class PaperPlanRecord:
    """Internal persisted paper plan bundle assembled from spec and plan rows."""

    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingParameterBinding]
