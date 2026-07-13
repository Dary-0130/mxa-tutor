"""Pure Python ModelGenerationPlan domain contract."""

from dataclasses import dataclass
from typing import Literal, NotRequired, TypeAlias, TypedDict

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_missing import MissingParameterBinding, MissingParameterPrompt
from core.domain.paper_spec import PaperSpec

GuidanceStatus = Literal[
    "not_generated",
    "generated",
    "stale_pending_regeneration",
    "generation_failed",
    "no_document_basis",
]

GuidanceBasis = Literal[
    "document_extracted",
    "document_derived",
    "domain_default",
    "engineering_choice",
    "user_environment",
    "user_decision",
    "user_confirmation_required",
    "document_claim_unverified",
]
GuidanceDetailKind = Literal[
    "block_selection",
    "subsystem_internal_structure",
    "connection",
    "parameter_value",
    "configuration",
    "verification",
    "gap_notice",
]
GuidanceExecutionClosure = Literal["closed", "guided_choice", "guided_probe", "open"]
GuidanceObligationKind = Literal[
    "determine_parameter_value",
    "select_component",
    "configure_setting",
    "connect_signal",
]
GuidanceTargetKind = Literal["parameter", "configuration", "block_choice", "connection"]
GuidanceResolutionKind = Literal[
    "fixed",
    "range",
    "enum_selection",
    "derivation",
    "conditional",
    "guided_user_decision",
    "environment_probe",
]
FixedGuidanceResolutionKind = Literal[
    "numeric",
    "block_ref",
    "configuration_option",
    "connection_mode",
]


class FixedNumericResolution(TypedDict):
    kind: Literal["fixed"]
    fixed_kind: Literal["numeric"]
    value: int | float
    unit: str


class FixedBlockRefResolution(TypedDict):
    kind: Literal["fixed"]
    fixed_kind: Literal["block_ref"]
    selected_id: str


class FixedConfigurationOptionResolution(TypedDict):
    kind: Literal["fixed"]
    fixed_kind: Literal["configuration_option"]
    value_token: str
    display_label: str


class FixedConnectionModeResolution(TypedDict):
    kind: Literal["fixed"]
    fixed_kind: Literal["connection_mode"]
    value_token: str
    display_label: str


FixedGuidanceResolution: TypeAlias = (
    FixedNumericResolution
    | FixedBlockRefResolution
    | FixedConfigurationOptionResolution
    | FixedConnectionModeResolution
)


class RangeResolution(TypedDict):
    kind: Literal["range"]
    lower: NotRequired[int | float | str | None]
    upper: NotRequired[int | float | str | None]
    values: NotRequired[list[int | float | str] | None]
    recommended_start: NotRequired[int | float | str | None]
    selection_rule: NotRequired[str | None]


class EnumSelectionResolution(TypedDict):
    kind: Literal["enum_selection"]
    selected: str


class DerivationResolution(TypedDict):
    kind: Literal["derivation"]
    formula: NotRequired[str | None]
    rule: NotRequired[str | None]
    inputs: list[str]


class ConditionalResolution(TypedDict):
    kind: Literal["conditional"]
    branches: list[dict[str, object]]
    fallback: NotRequired[str | None]
    exhaustive: NotRequired[bool]


class UserDecisionOptionResolution(TypedDict):
    option: str
    consequence: str


class GuidedUserDecisionResolution(TypedDict):
    kind: Literal["guided_user_decision"]
    decision_item: str
    criteria: str
    options: list[UserDecisionOptionResolution]


class EnvironmentProbeActionResolution(TypedDict):
    result: str
    action: str


class EnvironmentProbeResolution(TypedDict):
    kind: Literal["environment_probe"]
    probe_item: str
    procedure: str
    result_actions: list[EnvironmentProbeActionResolution]


GuidanceResolution: TypeAlias = (
    FixedGuidanceResolution
    | RangeResolution
    | EnumSelectionResolution
    | DerivationResolution
    | ConditionalResolution
    | GuidedUserDecisionResolution
    | EnvironmentProbeResolution
)


@dataclass(frozen=True)
class GuidanceTarget:
    """Public target identity for one guidance requirement."""

    target_kind: GuidanceTargetKind
    model_param: str | None = None
    paper_param: str | None = None
    owner_ref: str | None = None
    setting_name: str | None = None
    block_role_ref: str | None = None
    from_block: str | None = None
    from_port: str | None = None
    to_block: str | None = None
    to_port: str | None = None
    signal_role: str | None = None


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
    pending_user_choice_count: int = 0
    pending_environment_probe_count: int = 0
    open_requirement_count: int = 0


@dataclass(frozen=True)
class GuidanceDetail:
    """One structured build guidance detail."""

    detail_id: str
    step_id: str
    detail_kind: GuidanceDetailKind
    basis: GuidanceBasis
    actionability: Literal[
        "actionable",
        "notice_only",
        "blocked_pending_confirmation",
    ]
    display_text: str
    evidence: list[PaperEvidenceEntry]
    convention_code: str | None
    confirmation_reason_code: str | None
    target: GuidanceTarget | None = None
    obligation_kind: GuidanceObligationKind | None = None
    resolution: GuidanceResolution | None = None
    execution_closure: GuidanceExecutionClosure = "open"
    input_fact_refs: list[str] | None = None
    punt_reason_code: str | None = None


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
    basis: Literal["user_confirmation_required"]
    severity: Literal["blocking", "warning"]
    display_text: str
    target: GuidanceTarget | None = None
    obligation_kind: GuidanceObligationKind | None = None
    execution_closure: GuidanceExecutionClosure = "open"
    failure_code: str | None = None


@dataclass(frozen=True)
class BuildGuidance:
    """Structured build guidance contract for later generation phases."""

    version: Literal["v1", "v2"]
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
    guidance_status: GuidanceStatus = "not_generated"


@dataclass(frozen=True)
class PaperPlanRecord:
    """Internal persisted paper plan bundle assembled from spec and plan rows."""

    paper_id: str
    spec: PaperSpec
    plan: ModelGenerationPlan
    missing_prompts: list[MissingParameterPrompt]
    missing_bindings: list[MissingParameterBinding]
