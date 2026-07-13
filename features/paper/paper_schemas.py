"""Pydantic schemas for paper-to-model contracts."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from core.domain.paper_document_identity import (
    DOCUMENT_ID_PATTERN,
    validate_paper_spec_document_identity,
)
from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry, UserEvidenceAction
from core.domain.paper_missing import MissingParameterPrompt
from core.domain.paper_parameter_conflicts import validate_parameter_conflicts_materialized
from core.domain.paper_plan import (
    BlockRecommendation,
    BuildGuidance,
    ConfigurationHint,
    ConnectionHint,
    GuidanceAssessment,
    GuidanceDetail,
    GuidanceGap,
    GuidanceStatus,
    GuidanceTarget,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    ParameterMappingRef,
    StepBlockRef,
)
from core.domain.paper_spec import (
    EquationEntry,
    FigureRef,
    PaperDocument,
    PaperDomain,
    PaperSpec,
    PaperType,
    ParameterConflict,
    ParameterConflictObservation,
    ParameterConflictValueOption,
    ParameterEntry,
)
from core.domain.paper_tuning import (
    ConfidenceValue,
    ParameterDirection,
    ParameterDirectionValue,
    TuningSuggestion,
)
from features.paper.build_guidance_lifecycle import normalize_guidance_lifecycle


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    @classmethod
    def from_domain(cls, entry: object) -> Self:
        return cls.model_validate(entry)


class PaperEvidenceEntryModel(_StrictBaseModel):
    source: EvidenceSource
    document_id: str | None = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)
    paper_section_id: str | None = Field(default=None, min_length=1)
    equation_id: str | None = Field(default=None, min_length=1)
    figure_id: str | None = Field(default=None, min_length=1)
    excerpt: str | None = Field(default=None, min_length=1, max_length=300)
    missing_param_prompt_id: str | None = Field(default=None, min_length=1)
    user_action: UserEvidenceAction | None = None
    parameter_correction_id: str | None = Field(default=None, min_length=1)
    correction_param_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_source_invariants(self) -> Self:
        locators = (self.paper_section_id, self.equation_id, self.figure_id)
        if self.source is EvidenceSource.DOCUMENT_EXTRACTED:
            if self.document_id is None:
                raise ValueError("document_extracted evidence requires document_id")
            if not any(locator is not None for locator in locators):
                raise ValueError("document_extracted evidence requires at least one locator")
            if self.excerpt is None:
                raise ValueError("document_extracted evidence requires excerpt")
            if self.missing_param_prompt_id is not None:
                raise ValueError("document_extracted evidence cannot link missing prompt")
            if self.user_action is not None:
                raise ValueError("document_extracted evidence cannot have user action")
            if self.parameter_correction_id is not None:
                raise ValueError("document_extracted evidence cannot link correction")
            if self.correction_param_key is not None:
                raise ValueError("document_extracted evidence cannot link correction param key")
            return self

        if self.document_id is not None:
            raise ValueError("user_supplied evidence document_id must be null")
        if any(locator is not None for locator in locators):
            raise ValueError("user_supplied evidence cannot have paper locators")
        if self.excerpt is not None:
            raise ValueError("user_supplied evidence cannot have excerpt")
        if self.user_action is None:
            raise ValueError("user_supplied evidence requires user action")
        if self.user_action is UserEvidenceAction.FILL_MISSING:
            if self.missing_param_prompt_id is None:
                raise ValueError("fill_missing evidence requires missing prompt id")
            if self.parameter_correction_id is not None:
                raise ValueError("fill_missing evidence cannot link correction")
            if self.correction_param_key is not None:
                raise ValueError("fill_missing evidence cannot link correction param key")
            return self
        if self.user_action is UserEvidenceAction.CORRECT_EXTRACTED:
            if self.parameter_correction_id is None:
                raise ValueError("correct_extracted evidence requires correction id")
            if self.missing_param_prompt_id is not None:
                raise ValueError("correct_extracted evidence cannot link missing prompt")
            return self
        return self

    def to_domain(self) -> PaperEvidenceEntry:
        return PaperEvidenceEntry(
            source=self.source,
            document_id=self.document_id,
            paper_section_id=self.paper_section_id,
            equation_id=self.equation_id,
            figure_id=self.figure_id,
            excerpt=self.excerpt,
            missing_param_prompt_id=self.missing_param_prompt_id,
            user_action=self.user_action,
            parameter_correction_id=self.parameter_correction_id,
            correction_param_key=self.correction_param_key,
        )


class EquationEntryModel(_StrictBaseModel):
    equation_id: str = Field(min_length=1)
    latex_or_text: str = Field(min_length=1)
    paper_section_id: str = Field(min_length=1)
    document_id: str | None = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)

    def to_domain(self) -> EquationEntry:
        return EquationEntry(
            equation_id=self.equation_id,
            latex_or_text=self.latex_or_text,
            paper_section_id=self.paper_section_id,
            document_id=self.document_id,
        )


class ParameterEntryModel(_StrictBaseModel):
    name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: EvidenceSource
    document_id: str | None = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)

    @model_validator(mode="after")
    def validate_document_source(self) -> Self:
        if self.source is EvidenceSource.DOCUMENT_EXTRACTED and self.document_id is None:
            raise ValueError("document_extracted parameter requires document_id")
        if self.source is EvidenceSource.USER_SUPPLIED and self.document_id is not None:
            raise ValueError("user_supplied parameter document_id must be null")
        return self

    def to_domain(self) -> ParameterEntry:
        return ParameterEntry(
            name=self.name,
            symbol=self.symbol,
            value=self.value,
            unit=self.unit,
            source=self.source,
            document_id=self.document_id,
        )


class ParameterConflictObservationModel(_StrictBaseModel):
    document_id: str = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)
    locator: str | None = Field(min_length=1)
    excerpt: str | None = Field(min_length=1)

    def to_domain(self) -> ParameterConflictObservation:
        return ParameterConflictObservation(
            document_id=self.document_id,
            locator=self.locator,
            excerpt=self.excerpt,
        )


class ParameterConflictValueOptionModel(_StrictBaseModel):
    value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    observations: list[ParameterConflictObservationModel] = Field(min_length=1)

    def to_domain(self) -> ParameterConflictValueOption:
        return ParameterConflictValueOption(
            value=self.value,
            unit=self.unit,
            observations=[entry.to_domain() for entry in self.observations],
        )


class ParameterConflictModel(_StrictBaseModel):
    parameter_name: str = Field(min_length=1)
    parameter_symbol: str = Field(min_length=1)
    value_options: list[ParameterConflictValueOptionModel] = Field(min_length=2)

    def to_domain(self) -> ParameterConflict:
        return ParameterConflict(
            parameter_name=self.parameter_name,
            parameter_symbol=self.parameter_symbol,
            value_options=[entry.to_domain() for entry in self.value_options],
        )


class PaperDocumentModel(_StrictBaseModel):
    document_id: str = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)
    filename: str = Field(min_length=1, max_length=255)

    @field_validator("filename")
    @classmethod
    def validate_clean_filename(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("filename must not contain path separators")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("filename must not contain control characters")
        return value

    def to_domain(self) -> PaperDocument:
        return PaperDocument(
            document_id=self.document_id,
            filename=self.filename,
        )


class FigureRefModel(_StrictBaseModel):
    figure_id: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    paper_section_id: str = Field(min_length=1)
    document_id: str | None = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)

    def to_domain(self) -> FigureRef:
        return FigureRef(
            figure_id=self.figure_id,
            caption=self.caption,
            paper_section_id=self.paper_section_id,
            document_id=self.document_id,
        )


class BlockRecommendationModel(_StrictBaseModel):
    block_type: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel

    def to_domain(self) -> BlockRecommendation:
        return BlockRecommendation(
            block_type=self.block_type,
            purpose=self.purpose,
            paper_reference=self.paper_reference.to_domain(),
        )


class ParameterMappingModel(_StrictBaseModel):
    paper_param_name: str = Field(min_length=1)
    model_param_name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str | None = Field(default=None, min_length=1)
    source: EvidenceSource

    def to_domain(self) -> ParameterMapping:
        return ParameterMapping(
            paper_param_name=self.paper_param_name,
            model_param_name=self.model_param_name,
            value=self.value,
            unit=self.unit,
            source=self.source,
        )


class StepBlockRefModel(_StrictBaseModel):
    block_ref_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    library_path: str | None = Field(min_length=1)
    purpose: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel | None

    def to_domain(self) -> StepBlockRef:
        return StepBlockRef(
            block_ref_id=self.block_ref_id,
            block_type=self.block_type,
            library_path=self.library_path,
            purpose=self.purpose,
            paper_reference=(
                self.paper_reference.to_domain() if self.paper_reference is not None else None
            ),
        )


class ParameterMappingRefModel(_StrictBaseModel):
    paper_param_name: str = Field(min_length=1)
    model_param_name: str = Field(min_length=1)

    def to_domain(self) -> ParameterMappingRef:
        return ParameterMappingRef(
            paper_param_name=self.paper_param_name,
            model_param_name=self.model_param_name,
        )


class ConnectionHintModel(_StrictBaseModel):
    from_block_ref: Annotated[str, StringConstraints(min_length=1, strict=True)]
    from_port: str | None = Field(min_length=1)
    to_block_ref: Annotated[str, StringConstraints(min_length=1, strict=True)]
    to_port: str | None = Field(min_length=1)
    signal_meaning: str | None = Field(min_length=1)

    def to_domain(self) -> ConnectionHint:
        return ConnectionHint(
            from_block_ref=self.from_block_ref,
            from_port=self.from_port,
            to_block_ref=self.to_block_ref,
            to_port=self.to_port,
            signal_meaning=self.signal_meaning,
        )


class ConfigurationHintModel(_StrictBaseModel):
    target: str = Field(min_length=1)
    setting_name: str | None = Field(min_length=1)
    instruction: str = Field(min_length=1)
    evidence: list[PaperEvidenceEntryModel]

    def to_domain(self) -> ConfigurationHint:
        return ConfigurationHint(
            target=self.target,
            setting_name=self.setting_name,
            instruction=self.instruction,
            evidence=[entry.to_domain() for entry in self.evidence],
        )


class ModelBuildStepModel(_StrictBaseModel):
    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    block_refs: list[StepBlockRefModel]
    parameter_refs: list[ParameterMappingRefModel]
    connection_hints: list[ConnectionHintModel]
    configuration_hints: list[ConfigurationHintModel]
    depends_on: list[str]
    evidence: list[PaperEvidenceEntryModel]
    display_text: str = Field(min_length=1)

    def to_domain(self) -> ModelBuildStep:
        return ModelBuildStep(
            step_id=self.step_id,
            title=self.title,
            intent=self.intent,
            block_refs=[entry.to_domain() for entry in self.block_refs],
            parameter_refs=[entry.to_domain() for entry in self.parameter_refs],
            connection_hints=[entry.to_domain() for entry in self.connection_hints],
            configuration_hints=[entry.to_domain() for entry in self.configuration_hints],
            depends_on=self.depends_on,
            evidence=[entry.to_domain() for entry in self.evidence],
            display_text=self.display_text,
        )


class GuidanceAssessmentModel(_StrictBaseModel):
    content_status: Literal[
        "reproducible_candidate",
        "outline_with_gaps",
        "outline_only",
    ]
    environment_status: Literal[
        "not_checked",
        "compatible",
        "missing_toolbox",
        "incompatible",
    ]
    overall_status: Literal[
        "reproducible_ready",
        "reproducible_candidate_env_unchecked",
        "outline_with_gaps",
        "outline_only",
    ]
    blocking_gap_ids: list[str]
    pending_user_choice_count: int = Field(default=0, ge=0)
    pending_environment_probe_count: int = Field(default=0, ge=0)
    open_requirement_count: int = Field(default=0, ge=0)

    def to_domain(self) -> GuidanceAssessment:
        return GuidanceAssessment(
            content_status=self.content_status,
            environment_status=self.environment_status,
            overall_status=self.overall_status,
            blocking_gap_ids=self.blocking_gap_ids,
            pending_user_choice_count=self.pending_user_choice_count,
            pending_environment_probe_count=self.pending_environment_probe_count,
            open_requirement_count=self.open_requirement_count,
        )


class GuidanceTargetModel(_StrictBaseModel):
    target_kind: Literal["parameter", "configuration", "block_choice", "connection"]
    model_param: str | None = Field(default=None, min_length=1)
    paper_param: str | None = Field(default=None, min_length=1)
    owner_ref: str | None = Field(default=None, min_length=1)
    setting_name: str | None = Field(default=None, min_length=1)
    block_role_ref: str | None = Field(default=None, min_length=1)
    from_block: str | None = Field(default=None, min_length=1)
    from_port: str | None = Field(default=None, min_length=1)
    to_block: str | None = Field(default=None, min_length=1)
    to_port: str | None = Field(default=None, min_length=1)
    signal_role: str | None = Field(default=None, min_length=1)

    def to_domain(self) -> GuidanceTarget:
        return GuidanceTarget(
            target_kind=self.target_kind,
            model_param=self.model_param,
            paper_param=self.paper_param,
            owner_ref=self.owner_ref,
            setting_name=self.setting_name,
            block_role_ref=self.block_role_ref,
            from_block=self.from_block,
            from_port=self.from_port,
            to_block=self.to_block,
            to_port=self.to_port,
            signal_role=self.signal_role,
        )


class GuidanceDetailModel(_StrictBaseModel):
    detail_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
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
        "document_derived",
        "domain_default",
        "engineering_choice",
        "user_environment",
        "user_decision",
        "user_confirmation_required",
        "document_claim_unverified",
    ]
    actionability: Literal[
        "actionable",
        "notice_only",
        "blocked_pending_confirmation",
    ]
    display_text: str = Field(min_length=1)
    evidence: list[PaperEvidenceEntryModel]
    convention_code: str | None = Field(min_length=1)
    confirmation_reason_code: str | None = Field(min_length=1)
    target: GuidanceTargetModel | None = None
    obligation_kind: (
        Literal[
            "determine_parameter_value",
            "select_component",
            "configure_setting",
            "connect_signal",
        ]
        | None
    ) = None
    resolution: dict[str, Any] | None = None
    execution_closure: Literal["closed", "guided_choice", "guided_probe", "open"] = "open"
    input_fact_refs: list[str] = Field(default_factory=list)
    punt_reason_code: str | None = Field(default=None, min_length=1)

    def to_domain(self) -> GuidanceDetail:
        return GuidanceDetail(
            detail_id=self.detail_id,
            step_id=self.step_id,
            detail_kind=self.detail_kind,
            basis=self.basis,
            actionability=self.actionability,
            display_text=self.display_text,
            evidence=[entry.to_domain() for entry in self.evidence],
            convention_code=self.convention_code,
            confirmation_reason_code=self.confirmation_reason_code,
            target=self.target.to_domain() if self.target is not None else None,
            obligation_kind=self.obligation_kind,
            resolution=self.resolution,
            execution_closure=self.execution_closure,
            input_fact_refs=list(self.input_fact_refs),
            punt_reason_code=self.punt_reason_code,
        )


class GuidanceGapModel(_StrictBaseModel):
    gap_id: str = Field(min_length=1)
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
    step_id: str | None = Field(min_length=1)
    basis: Literal["user_confirmation_required"]
    severity: Literal["blocking", "warning"]
    display_text: str = Field(min_length=1)
    target: GuidanceTargetModel | None = None
    obligation_kind: (
        Literal[
            "determine_parameter_value",
            "select_component",
            "configure_setting",
            "connect_signal",
        ]
        | None
    ) = None
    execution_closure: Literal["closed", "guided_choice", "guided_probe", "open"] = "open"
    failure_code: str | None = Field(default=None, min_length=1)

    def to_domain(self) -> GuidanceGap:
        return GuidanceGap(
            gap_id=self.gap_id,
            gap_kind=self.gap_kind,
            scope=self.scope,
            step_id=self.step_id,
            basis=self.basis,
            severity=self.severity,
            display_text=self.display_text,
            target=self.target.to_domain() if self.target is not None else None,
            obligation_kind=self.obligation_kind,
            execution_closure=self.execution_closure,
            failure_code=self.failure_code,
        )


class BuildGuidanceModel(_StrictBaseModel):
    version: Literal["v1", "v2"]
    assessment: GuidanceAssessmentModel
    details: list[GuidanceDetailModel]
    gaps: list[GuidanceGapModel]

    def to_domain(self) -> BuildGuidance:
        return BuildGuidance(
            version=self.version,
            assessment=self.assessment.to_domain(),
            details=[entry.to_domain() for entry in self.details],
            gaps=[entry.to_domain() for entry in self.gaps],
        )


class ParameterDirectionModel(_StrictBaseModel):
    param_name: str = Field(min_length=1)
    direction: ParameterDirectionValue
    physical_meaning: str = Field(min_length=1)

    def to_domain(self) -> ParameterDirection:
        return ParameterDirection(
            param_name=self.param_name,
            direction=self.direction,
            physical_meaning=self.physical_meaning,
        )


class PaperSpecModel(_StrictBaseModel):
    paper_title: str = Field(min_length=1, max_length=200)
    paper_type: PaperType
    domain: PaperDomain
    documents: list[PaperDocumentModel] = Field(min_length=1)
    primary_document_id: str | None = Field(min_length=1, pattern=DOCUMENT_ID_PATTERN)
    abstract: str = Field(min_length=1, max_length=1500)
    equations: list[EquationEntryModel] = Field(default_factory=list)
    parameter_table: list[ParameterEntryModel] = Field(default_factory=list)
    figure_locations: list[FigureRefModel] = Field(default_factory=list)
    pseudocode_blocks: list[str] = Field(default_factory=list)
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)
    parameter_conflicts: list[ParameterConflictModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_document_identity(self) -> Self:
        spec = self._to_domain_unchecked()
        validate_paper_spec_document_identity(spec)
        validate_parameter_conflicts_materialized(spec)
        return self

    def _to_domain_unchecked(self) -> PaperSpec:
        return PaperSpec(
            paper_title=self.paper_title,
            paper_type=self.paper_type,
            domain=self.domain,
            documents=[entry.to_domain() for entry in self.documents],
            primary_document_id=self.primary_document_id,
            abstract=self.abstract,
            equations=[entry.to_domain() for entry in self.equations],
            parameter_table=[entry.to_domain() for entry in self.parameter_table],
            figure_locations=[entry.to_domain() for entry in self.figure_locations],
            pseudocode_blocks=self.pseudocode_blocks,
            evidence=[entry.to_domain() for entry in self.evidence],
            parameter_conflicts=[entry.to_domain() for entry in self.parameter_conflicts],
        )

    def to_domain(self) -> PaperSpec:
        spec = self._to_domain_unchecked()
        validate_paper_spec_document_identity(spec)
        return spec


class ModelGenerationPlanModel(_StrictBaseModel):
    plan_id: str = Field(min_length=1)
    paper_spec_id: str = Field(min_length=1)
    library_choice: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    block_recommendations: list[BlockRecommendationModel] = Field(default_factory=list)
    parameter_mapping: list[ParameterMappingModel] = Field(default_factory=list)
    subsystem_breakdown: list[str] = Field(min_length=3, max_length=10)
    m_script_skeleton: str | None = None
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)
    build_steps: list[ModelBuildStepModel] | None = Field(default=None, min_length=1)
    build_guidance: BuildGuidanceModel | None = None
    guidance_status: GuidanceStatus = "not_generated"

    @classmethod
    def from_domain(cls, entry: object) -> Self:
        if isinstance(entry, ModelGenerationPlan):
            entry = normalize_guidance_lifecycle(entry)
        return cls.model_validate(entry)

    @model_validator(mode="after")
    def validate_guidance_lifecycle_state(self) -> Self:
        if self.guidance_status == "generated":
            if self.build_guidance is None:
                raise ValueError("generated guidance requires build_guidance")
            if self.build_guidance.version != "v2":
                raise ValueError("generated guidance requires v2 build_guidance")
            if not self.build_guidance.details:
                raise ValueError("generated guidance requires details")
            if not any(
                detail.basis in {"document_extracted", "document_derived"} and detail.evidence
                for detail in self.build_guidance.details
            ):
                raise ValueError("generated guidance requires document detail evidence")
            return self
        if (
            self.guidance_status
            in {
                "not_generated",
                "generation_failed",
                "no_document_basis",
            }
            and self.build_guidance is not None
        ):
            raise ValueError("guidance_status requires build_guidance null")
        return self

    def to_domain(self) -> ModelGenerationPlan:
        return normalize_guidance_lifecycle(
            ModelGenerationPlan(
                plan_id=self.plan_id,
                paper_spec_id=self.paper_spec_id,
                library_choice=self.library_choice,
                block_recommendations=[entry.to_domain() for entry in self.block_recommendations],
                parameter_mapping=[entry.to_domain() for entry in self.parameter_mapping],
                subsystem_breakdown=self.subsystem_breakdown,
                m_script_skeleton=self.m_script_skeleton,
                evidence=[entry.to_domain() for entry in self.evidence],
                build_steps=(
                    [entry.to_domain() for entry in self.build_steps]
                    if self.build_steps is not None
                    else None
                ),
                build_guidance=(
                    self.build_guidance.to_domain() if self.build_guidance is not None else None
                ),
                guidance_status=self.guidance_status,
            )
        )


class TuningSuggestionModel(_StrictBaseModel):
    suggestion_id: str = Field(min_length=1)
    user_scenario: str = Field(min_length=1, max_length=500)
    parameter_directions: list[ParameterDirectionModel] = Field(min_length=1)
    expected_effect: str = Field(min_length=1, max_length=500)
    confidence: ConfidenceValue
    evidence: list[PaperEvidenceEntryModel] = Field(min_length=1)
    disclaimer: str = Field(min_length=1)

    def to_domain(self) -> TuningSuggestion:
        return TuningSuggestion(
            suggestion_id=self.suggestion_id,
            user_scenario=self.user_scenario,
            parameter_directions=[entry.to_domain() for entry in self.parameter_directions],
            expected_effect=self.expected_effect,
            confidence=self.confidence,
            evidence=[entry.to_domain() for entry in self.evidence],
            disclaimer=self.disclaimer,
        )


class MissingParameterPromptModel(_StrictBaseModel):
    prompt_id: str = Field(min_length=1)
    parameter_name: str = Field(min_length=1)
    paper_reference: PaperEvidenceEntryModel
    suggested_unit: str | None = Field(default=None, min_length=1)
    user_supplied_value: str | None = Field(default=None, min_length=1)
    user_supplied_unit: str | None = Field(default=None, min_length=1)
    source: Literal["user_supplied"] = "user_supplied"

    @model_validator(mode="after")
    def validate_paper_reference_source(self) -> Self:
        if self.paper_reference.source is not EvidenceSource.DOCUMENT_EXTRACTED:
            raise ValueError("paper_reference must be document_extracted")
        return self

    def to_domain(self) -> MissingParameterPrompt:
        return MissingParameterPrompt(
            prompt_id=self.prompt_id,
            parameter_name=self.parameter_name,
            paper_reference=self.paper_reference.to_domain(),
            suggested_unit=self.suggested_unit,
            user_supplied_value=self.user_supplied_value,
            user_supplied_unit=self.user_supplied_unit,
            source=EvidenceSource(self.source),
        )


PaperEvidenceEntrySchema = PaperEvidenceEntryModel
PaperSpecSchema = PaperSpecModel
ModelGenerationPlanSchema = ModelGenerationPlanModel
TuningSuggestionSchema = TuningSuggestionModel
MissingParameterPromptSchema = MissingParameterPromptModel
