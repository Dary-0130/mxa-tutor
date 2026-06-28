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

export interface PaperEvidenceEntry {
  source: EvidenceSource;
  paper_section_id?: string | null;
  equation_id?: string | null;
  figure_id?: string | null;
  excerpt?: string | null;
  missing_param_prompt_id?: string | null;
}

export interface EquationEntry {
  equation_id: string;
  latex_or_text: string;
  paper_section_id: string;
}

export interface ParameterEntry {
  name: string;
  symbol: string;
  value: string;
  unit: string;
  source: EvidenceSource;
}

export interface FigureRef {
  figure_id: string;
  caption: string;
  paper_section_id: string;
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
  abstract: string;
  equations: EquationEntry[];
  parameter_table: ParameterEntry[];
  figure_locations: FigureRef[];
  pseudocode_blocks: string[];
  evidence: PaperEvidenceEntry[];
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

export interface UploadDocumentResponse {
  paper_id: string;
  spec: PaperSpec;
  plan: ModelGenerationPlan;
  missing_prompts: MissingParameterPrompt[];
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
