import { apiGet, apiPost, apiUploadFormTask, type UploadTask } from "./api";
import type {
  PaperAskRequest,
  PaperAskResponse,
  PaperPlanResponse,
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

export function postTuningSuggest(
  paperId: string,
  request: TuningSuggestRequest,
): Promise<TuningSuggestResponse> {
  return apiPost<TuningSuggestResponse>(paperPath(paperId, "/tuning-suggest"), request);
}

export function postPaperAsk(
  paperId: string,
  request: PaperAskRequest,
): Promise<PaperAskResponse> {
  return apiPost<PaperAskResponse>(paperPath(paperId, "/ask"), request);
}

export function postUserSupply(
  paperId: string,
  request: UserSuppliedResponseBatch,
): Promise<UpdatedPlanResponse> {
  return apiPost<UpdatedPlanResponse>(paperPath(paperId, "/user-supply"), request);
}
