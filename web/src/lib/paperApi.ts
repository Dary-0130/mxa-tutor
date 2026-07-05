import { apiGet, apiPost, apiUploadFormTask, type UploadTask } from "./api";
import type {
  PaperAskRequest,
  PaperAskResponse,
  ParameterCorrectionRequest,
  ParameterCorrectionResponse,
  ParameterCorrectionsResponse,
  PaperPlanResponse,
  PaperReparseResponse,
  PaperStatusResponse,
  RerunPlanRequest,
  RerunPlanResponse,
  PaperSpecResponse,
  TuningSuggestRequest,
  TuningSuggestResponse,
  UpdatedPlanResponse,
  UploadDocumentResponse,
  UserSuppliedResponseBatch,
} from "./paperTypes";

function paperPath(paperId: string, suffix: string): string {
  return `/api/v1/papers/${encodeURIComponent(paperId)}${suffix}`;
}

export function uploadDocument(
  files: File[],
  primaryIndex: number | null,
  onProgress?: (percent: number) => void,
): UploadTask<UploadDocumentResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("file", file);
  }
  if (primaryIndex !== null) {
    formData.append("primary_index", String(primaryIndex));
  }
  return apiUploadFormTask<UploadDocumentResponse>("/api/v1/upload-document", formData, onProgress);
}

export function getPaperSpec(paperId: string): Promise<PaperSpecResponse> {
  return apiGet<PaperSpecResponse>(paperPath(paperId, "/spec"));
}

export function getPaperPlan(paperId: string): Promise<PaperPlanResponse> {
  return apiGet<PaperPlanResponse>(paperPath(paperId, "/plan"));
}

export function getPaperStatus(paperId: string): Promise<PaperStatusResponse> {
  return apiGet<PaperStatusResponse>(paperPath(paperId, "/status"));
}

export function postRerunPlan(
  paperId: string,
  request: RerunPlanRequest = {},
): Promise<RerunPlanResponse> {
  return apiPost<RerunPlanResponse>(paperPath(paperId, "/rerun-plan"), request);
}

export function postPaperReparse(paperId: string): Promise<PaperReparseResponse> {
  return apiPost<PaperReparseResponse>(paperPath(paperId, "/reparse"));
}

export function postRegenerateSteps(paperId: string): Promise<UpdatedPlanResponse> {
  return apiPost<UpdatedPlanResponse>(paperPath(paperId, "/regenerate-steps"), {});
}

export function postTuningSuggest(
  paperId: string,
  request: TuningSuggestRequest,
): Promise<TuningSuggestResponse> {
  return apiPost<TuningSuggestResponse>(paperPath(paperId, "/tuning-suggest"), request);
}

export function postPaperAsk(paperId: string, request: PaperAskRequest): Promise<PaperAskResponse> {
  return apiPost<PaperAskResponse>(paperPath(paperId, "/ask"), request);
}

export function postUserSupply(
  paperId: string,
  request: UserSuppliedResponseBatch,
): Promise<UpdatedPlanResponse> {
  return apiPost<UpdatedPlanResponse>(paperPath(paperId, "/user-supply"), request);
}

export function getParameterCorrections(paperId: string): Promise<ParameterCorrectionsResponse> {
  return apiGet<ParameterCorrectionsResponse>(paperPath(paperId, "/parameter-corrections"));
}

export function postParameterCorrection(
  paperId: string,
  request: ParameterCorrectionRequest,
): Promise<ParameterCorrectionResponse> {
  return apiPost<ParameterCorrectionResponse>(paperPath(paperId, "/parameter-correction"), request);
}

export function postUndoParameterCorrection(
  paperId: string,
  correctionId: string,
): Promise<UpdatedPlanResponse> {
  return apiPost<UpdatedPlanResponse>(
    paperPath(paperId, `/parameter-correction/${encodeURIComponent(correctionId)}/undo`),
  );
}
