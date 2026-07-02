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

export interface UploadDocumentStatus {
  document_id: string;
  filename: string;
  status: "succeeded" | "failed";
  error_code: string | null;
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
