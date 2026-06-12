export type ProjectStatusValue = "parsing" | "ready" | "failed";

export type ProjectType =
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

export interface EntryFileEntry {
  file_path: string;
  role: string;
}

export interface SimulinkModelEntry {
  file_path: string;
  summary: string;
}

export interface KeyFileEntry {
  file_path: string;
  why_key: string;
}

export interface BlockEntry {
  block_name: string;
  block_type: string;
  location: string;
  why_key: string;
}

export interface SourceRefEntry {
  file_path: string;
  line_range?: [number, number] | null;
  block_id?: string | null;
}

export interface ProjectOverview {
  project_title: string;
  project_type: ProjectType;
  one_sentence_summary: string;
  main_entry_files: EntryFileEntry[];
  main_simulink_models: SimulinkModelEntry[];
  main_execution_flow: string[];
  key_files: KeyFileEntry[];
  key_blocks: BlockEntry[];
  knowledge_points: string[];
  beginner_reading_order: string[];
  likely_confusing_points: string[];
  evidence: SourceRefEntry[];
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

export interface ChatRequest {
  question: string;
  session_id?: string;
}

export interface ChatSessionDTO {
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageDTO {
  message_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  citations: SourceRef[];
}

export interface ChatSessionsResponse {
  project_id: string;
  sessions: ChatSessionDTO[];
}

export interface ChatMessagesResponse {
  session_id: string;
  messages: ChatMessageDTO[];
}

export interface UIMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: SourceRef[];
  status: "sent" | "pending" | "failed" | "orphan";
  is_fallback?: boolean;
  fallbackInferredFromHistory?: boolean;
  fallback_reason?: FallbackReason | null;
  error_code?: string;
  confidence?: Confidence;
  follow_up_suggestions?: string[];
}
