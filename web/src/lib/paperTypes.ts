export type EvidenceSource = "document_extracted" | "user_supplied";
export type PaperDomain =
  | "control_system"
  | "signal_processing"
  | "power_electronics"
  | "communication"
  | "motor_control"
  | "new_energy";
export type PaperType = "paper" | "report" | "thesis";
export type TuningDirection = "increase" | "decrease" | "tune_within_range";
export type Confidence = "high" | "medium" | "low";
export type PaperAskFallbackReason =
  | "insufficient_evidence"
  | "invalid_or_missing_citations"
  | "citation_target_unresolved"
  | "out_of_scope";
export type PaperUploadExecutionMode = "sync" | "async" | "rerun_plan";
export type PaperUploadJobState =
  | "queued"
  | "running"
  | "spec_ready"
  | "plan_generating"
  | "ready"
  | "plan_failed_retryable"
  | "plan_failed_permanent"
  | "failed_no_usable_spec"
  | "abandoned_plan_retryable"
  | "abandoned_reupload_required";
export type PaperUploadStage =
  | "uploading"
  | "parsing"
  | "extracting_spec"
  | "fusing"
  | "persisting_spec"
  | "generating_plan"
  | "persisting_plan"
  | "done";
export type PaperUploadDocumentState =
  | "pending"
  | "parsing"
  | "parsed"
  | "extracting"
  | "succeeded"
  | "failed";
export type PaperUploadNextAction =
  | "wait"
  | "rerun_plan"
  | "reupload"
  | "open_result"
  | "none"
  | "contact_support";
export type GuidanceContentStatus =
  | "reproducible_candidate"
  | "outline_with_gaps"
  | "outline_only";
export type GuidanceEnvironmentStatus =
  | "not_checked"
  | "compatible"
  | "missing_toolbox"
  | "incompatible";
export type GuidanceOverallStatus =
  | "reproducible_ready"
  | "reproducible_candidate_env_unchecked"
  | "outline_with_gaps"
  | "outline_only";
export type GuidanceDetailKind =
  | "block_selection"
  | "subsystem_internal_structure"
  | "connection"
  | "parameter_value"
  | "configuration"
  | "verification"
  | "gap_notice";
export type GuidanceBasis =
  | "document_extracted"
  | "document_derived"
  | "domain_default"
  | "engineering_choice"
  | "user_environment"
  | "user_decision"
  | "user_confirmation_required"
  | "document_claim_unverified";
export type GuidanceActionability =
  | "actionable"
  | "notice_only"
  | "blocked_pending_confirmation";
export type GuidanceClosure =
  | "closed"
  | "guided_choice"
  | "guided_probe"
  | "open";
export type GuidanceTargetKind =
  | "parameter"
  | "configuration"
  | "block_choice"
  | "connection";
export type GuidanceObligationKind =
  | "determine_parameter_value"
  | "select_component"
  | "configure_setting"
  | "connect_signal";
export type GuidanceGapKind =
  | "missing_support_component"
  | "missing_parameter_value"
  | "toolbox_unverified"
  | "library_variant_unresolved"
  | "missing_connection_detail"
  | "missing_configuration_detail"
  | "insufficient_document_evidence";
export type GuidanceScope = "plan" | "step" | "subsystem";
export type GuidanceSeverity = "blocking" | "warning";
export type GuidanceStatus =
  | "not_generated"
  | "generated"
  | "stale_pending_regeneration"
  | "generation_failed"
  | "no_document_basis";
export type GuidanceViewState =
  | "current"
  | "stale_with_snapshot"
  | "stale_empty"
  | "failed_retryable"
  | "no_basis"
  | "not_generated";

export type PaperCitationTarget =
  | SectionTarget
  | EquationTarget
  | PlanMappingParameterTarget
  | MissingPromptParameterTarget;

export interface SectionTarget {
  kind: "section";
  result_section:
    | "paper-summary"
    | "paper-subsystems"
    | "paper-build-steps"
    | "paper-parameters"
    | "paper-tuning";
}

export interface EquationTarget {
  kind: "equation";
  equation_id: string;
}

export interface PlanMappingParameterTarget {
  kind: "parameter";
  origin: "plan_mapping";
  row_index: number;
  paper_param_name: string;
  model_param_name: string;
}

export interface MissingPromptParameterTarget {
  kind: "parameter";
  origin: "missing_prompt";
  prompt_id: string;
  parameter_name: string;
}

export interface PaperEvidenceEntry {
  source: EvidenceSource;
  document_id: string | null;
  paper_section_id?: string | null;
  equation_id?: string | null;
  figure_id?: string | null;
  excerpt?: string | null;
  missing_param_prompt_id?: string | null;
  user_action?: "fill_missing" | "correct_extracted" | null;
  parameter_correction_id?: string | null;
  correction_param_key?: string | null;
}

export interface EquationEntry {
  equation_id: string;
  latex_or_text: string;
  paper_section_id: string;
  document_id: string | null;
}

export interface ParameterEntry {
  name: string;
  symbol: string;
  value: string;
  unit: string;
  source: EvidenceSource;
  document_id: string | null;
}

export interface ParameterConflictObservation {
  document_id: string;
  locator: string | null;
  excerpt: string | null;
}

export interface ParameterConflictValueOption {
  value: string;
  unit: string;
  observations: ParameterConflictObservation[];
}

export interface ParameterConflict {
  parameter_name: string;
  parameter_symbol: string;
  value_options: ParameterConflictValueOption[];
}

export interface FigureRef {
  figure_id: string;
  caption: string;
  paper_section_id: string;
  document_id: string | null;
}

export interface PaperDocument {
  document_id: string;
  filename: string;
}

export interface BlockRecommendation {
  block_type: string;
  purpose: string;
  paper_reference: PaperEvidenceEntry;
}

export interface ParameterMapping {
  paper_param_name: string;
  model_param_name: string;
  value: string;
  unit?: string | null;
  source: EvidenceSource;
}

export interface StepBlockRef {
  block_ref_id: string;
  block_type: string;
  library_path: string | null;
  purpose: string;
  paper_reference: PaperEvidenceEntry | null;
}

export interface ParameterMappingRef {
  paper_param_name: string;
  model_param_name: string;
}

export interface ConnectionHint {
  from_block_ref: string;
  from_port: string | null;
  to_block_ref: string;
  to_port: string | null;
  signal_meaning: string | null;
}

export interface ConfigurationHint {
  target: string;
  setting_name: string | null;
  instruction: string;
  evidence: PaperEvidenceEntry[];
}

export interface ModelBuildStep {
  step_id: string;
  title: string;
  intent: string;
  block_refs: StepBlockRef[];
  parameter_refs: ParameterMappingRef[];
  connection_hints: ConnectionHint[];
  configuration_hints: ConfigurationHint[];
  depends_on: string[];
  evidence: PaperEvidenceEntry[];
  display_text: string;
}

export interface GuidanceAssessment {
  content_status: GuidanceContentStatus;
  environment_status: GuidanceEnvironmentStatus;
  overall_status: GuidanceOverallStatus;
  blocking_gap_ids: string[];
  pending_user_choice_count: number;
  pending_environment_probe_count: number;
  open_requirement_count: number;
}

export interface GuidanceTarget {
  target_kind: GuidanceTargetKind;
  model_param: string | null;
  paper_param: string | null;
  owner_ref: string | null;
  setting_name: string | null;
  block_role_ref: string | null;
  from_block: string | null;
  from_port: string | null;
  to_block: string | null;
  to_port: string | null;
  signal_role: string | null;
}

export interface GuidanceDetail {
  detail_id: string;
  step_id: string;
  detail_kind: GuidanceDetailKind;
  basis: GuidanceBasis;
  actionability: GuidanceActionability;
  display_text: string;
  evidence: PaperEvidenceEntry[];
  convention_code: string | null;
  confirmation_reason_code: string | null;
  target: GuidanceTarget | null;
  obligation_kind: GuidanceObligationKind | null;
  resolution: Record<string, unknown> | null;
  execution_closure: GuidanceClosure;
  input_fact_refs: string[];
  punt_reason_code: string | null;
}

export interface GuidanceGap {
  gap_id: string;
  gap_kind: GuidanceGapKind;
  scope: GuidanceScope;
  step_id: string | null;
  basis: "user_confirmation_required";
  severity: GuidanceSeverity;
  display_text: string;
  target: GuidanceTarget | null;
  obligation_kind: GuidanceObligationKind | null;
  execution_closure: GuidanceClosure;
  failure_code: string | null;
}

export interface BuildGuidance {
  version: "v1" | "v2";
  assessment: GuidanceAssessment;
  details: GuidanceDetail[];
  gaps: GuidanceGap[];
}

export interface ModelGenerationPlan {
  plan_id: string;
  paper_spec_id: string;
  library_choice: string;
  block_recommendations: BlockRecommendation[];
  parameter_mapping: ParameterMapping[];
  subsystem_breakdown: string[];
  m_script_skeleton?: string | null;
  evidence: PaperEvidenceEntry[];
  build_steps: ModelBuildStep[] | null;
  build_guidance: BuildGuidance | null;
  guidance_status: GuidanceStatus;
}

export function guidanceViewState(plan: ModelGenerationPlan): GuidanceViewState {
  if (plan.guidance_status === "generated") {
    return "current";
  }
  if (plan.guidance_status === "stale_pending_regeneration") {
    return plan.build_guidance ? "stale_with_snapshot" : "stale_empty";
  }
  if (plan.guidance_status === "generation_failed") {
    return "failed_retryable";
  }
  if (plan.guidance_status === "no_document_basis") {
    return "no_basis";
  }
  return "not_generated";
}

export interface MissingParameterPrompt {
  prompt_id: string;
  parameter_name: string;
  paper_reference: PaperEvidenceEntry;
  suggested_unit?: string | null;
  user_supplied_value?: string | null;
  user_supplied_unit?: string | null;
  source: "user_supplied";
}

export interface PaperSpec {
  paper_title: string;
  paper_type: PaperType;
  domain: PaperDomain;
  documents: PaperDocument[];
  primary_document_id: string | null;
  abstract: string;
  equations: EquationEntry[];
  parameter_table: ParameterEntry[];
  figure_locations: FigureRef[];
  pseudocode_blocks: string[];
  evidence: PaperEvidenceEntry[];
  parameter_conflicts: ParameterConflict[];
}

export interface ParameterDirection {
  param_name: string;
  direction: TuningDirection;
  physical_meaning: string;
}

export interface TuningSuggestion {
  suggestion_id: string;
  user_scenario: string;
  parameter_directions: ParameterDirection[];
  expected_effect: string;
  confidence: Confidence;
  evidence: PaperEvidenceEntry[];
  disclaimer: string;
}

export interface PaperAskRequest {
  question: string;
  session_id?: string | null;
}

export interface PaperAskCitation {
  source_id: string;
  label: string;
  excerpt: string | null;
  source_kind: EvidenceSource;
  target: PaperCitationTarget;
  document_id?: string | null;
  document_label?: string | null;
}

export interface PaperAskResponse {
  session_id: string;
  message_id: string;
  answer: string;
  confidence: Confidence;
  citations: PaperAskCitation[];
  follow_up_suggestions: string[];
  is_fallback: boolean;
  fallback_reason: PaperAskFallbackReason | null;
}

export interface UploadDocumentResponse {
  paper_id: string;
  spec: PaperSpec;
  plan: ModelGenerationPlan;
  missing_prompts: MissingParameterPrompt[];
  document_statuses: UploadDocumentStatus[];
}

export interface UploadAsyncResponse {
  paper_id: string;
  job_id: string;
}

export interface UploadDocumentStatus {
  document_id: string;
  filename: string;
  status: "succeeded" | "failed";
  error_code: string | null;
}

export interface PaperJobDocumentStatus {
  document_id: string;
  status: PaperUploadDocumentState;
  error_code: string | null;
}

export interface PaperStatusResponse {
  paper_id: string;
  job_id: string;
  execution_mode: PaperUploadExecutionMode;
  job_state: PaperUploadJobState;
  stage: PaperUploadStage;
  failed_stage: PaperUploadStage | null;
  error_code: string | null;
  retryable: boolean;
  next_action: PaperUploadNextAction;
  expires_at: string;
  documents: PaperJobDocumentStatus[];
}

export type RerunPlanRequest = Record<string, never>;

export interface RerunPlanResponse {
  paper_id: string;
  job_id: string;
  job_state: PaperUploadJobState;
  plan: ModelGenerationPlan;
  missing_prompts: MissingParameterPrompt[];
  remaining_missing_prompts: MissingParameterPrompt[];
}

export interface PaperSpecResponse {
  paper_id: string;
  spec: PaperSpec;
}

export interface PaperPlanResponse {
  paper_id: string;
  plan: ModelGenerationPlan;
  missing_prompts: MissingParameterPrompt[];
  remaining_missing_prompts: MissingParameterPrompt[];
}

export interface PaperReparseResponse {
  paper_id: string;
  spec: PaperSpec;
  plan: ModelGenerationPlan;
  missing_prompts: MissingParameterPrompt[];
  remaining_missing_prompts: MissingParameterPrompt[];
}

export interface TuningSuggestRequest {
  user_scenario: string;
}

export interface TuningSuggestResponse {
  paper_id: string;
  suggestion: TuningSuggestion;
}

export interface UserSuppliedResponse {
  prompt_id: string;
  parameter_name: string;
  user_supplied_value: string;
  user_supplied_unit?: string | null;
  user_supplied_note?: string | null;
}

export interface UserSuppliedResponseBatch {
  user_supplied_responses: UserSuppliedResponse[];
}

export interface UpdatedPlanResponse {
  paper_id: string;
  updated_plan: ModelGenerationPlan;
}

export interface ParameterCorrectionTarget {
  paper_param_name: string;
  model_param_name: string;
  plan_mapping_index: number;
}

export interface ParameterCorrectionRequestTarget extends ParameterCorrectionTarget {
  expected_value: string;
  expected_unit: string | null;
}

export interface ParameterCorrectionRequest {
  target: ParameterCorrectionRequestTarget;
  corrected_value: string;
  corrected_unit?: string | null;
}

export interface ParameterCorrection {
  correction_id: string;
  param_key: string;
  target: ParameterCorrectionTarget;
  original: {
    value: string;
    unit: string | null;
    source: "document_extracted";
    document_id: string | null;
    document_label: string | null;
  };
  corrected: {
    value: string;
    unit: string | null;
  };
  created_at: string;
  updated_at: string;
  can_undo: boolean;
  can_undo_reason: "active" | "target_stale" | "missing_mapping";
}

export interface ParameterCorrectionsResponse {
  paper_id: string;
  corrections: ParameterCorrection[];
}

export interface ParameterCorrectionResponse {
  paper_id: string;
  updated_plan: ModelGenerationPlan;
  correction: ParameterCorrection;
}
