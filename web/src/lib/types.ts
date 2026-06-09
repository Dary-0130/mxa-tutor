export type ProjectStatusValue = "parsing" | "ready" | "failed";
export type ProjectTypeValue =
  | "control_system"
  | "signal_processing"
  | "power_electronics"
  | "communication"
  | "motor_control"
  | "new_energy"
  | "general";
export type Confidence = "high" | "medium" | "low";
export type FallbackReason =
  | "no_retrieval_hits"
  | "invalid_or_missing_citations"
  | "low_relevance"
  | "out_of_scope";

export interface UploadResponse {
  project_id: string;
  status: "parsing";
}

export interface ProjectStatus {
  project_id: string;
  name: string;
  status: ProjectStatusValue;
  created_at: string;
  error_code: string | null;
}

export interface SourceRef {
  file_path: string;
  line_range?: [number, number] | null;
  block_id?: string | null;
  block_name?: string | null;
  parent_subsystem?: string | null;
  parameter_name?: string | null;
}

export interface ProjectOverview {
  project_title: string;
  project_type: ProjectTypeValue;
  one_sentence_summary: string;
  main_entry_files: { file_path: string; role: string }[];
  main_simulink_models: { file_path: string; summary: string }[];
  main_execution_flow: string[];
  key_files: { file_path: string; why_key: string }[];
  key_blocks: { block_name: string; block_type: string; location: string; why_key: string }[];
  knowledge_points: string[];
  beginner_reading_order: string[];
  likely_confusing_points: string[];
  evidence: Pick<SourceRef, "file_path" | "line_range" | "block_id">[];
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  answer: string;
  confidence: Confidence;
  citations: SourceRef[];
  follow_up_suggestions: string[];
  is_fallback: boolean;
  fallback_reason: FallbackReason | null;
}

export interface ChatSessionsResponse {
  project_id: string;
  sessions: { session_id: string; title: string | null; created_at: string; updated_at: string }[];
}

export interface ChatMessagesResponse {
  session_id: string;
  messages: {
    message_id: string;
    role: "user" | "assistant" | "system";
    content: string;
    created_at: string;
    citations: SourceRef[];
  }[];
}
