import type { UploadResponse } from "./types";

export interface ApiError {
  error: string;
  message: string;
}

export interface UploadTask<T> {
  promise: Promise<T>;
  abort: () => void;
}

export class ApiException extends Error {
  readonly status: number;
  readonly code: string;
  readonly userMessage: string;

  constructor(status: number, code: string, userMessage: string) {
    super(userMessage);
    this.name = "ApiException";
    this.status = status;
    this.code = code;
    this.userMessage = userMessage;
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

function buildUrl(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error("API path must start with a single '/'");
  }
  return `${API_BASE}${path}`;
}

async function parseError(response: Response): Promise<ApiException> {
  try {
    const body = (await response.json()) as Partial<ApiError>;
    return new ApiException(
      response.status,
      body.error ?? "request_failed",
      body.message ?? "请求失败，请稍后重试",
    );
  } catch {
    return new ApiException(response.status, "request_failed", "请求失败，请稍后重试");
  }
}

function networkError(): ApiException {
  return new ApiException(0, "network_error", "网络连接失败,请检查网络后重试");
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path), { headers: { Accept: "application/json" } });
  } catch (error) {
    if (error instanceof TypeError) {
      throw networkError();
    }
    throw error;
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw networkError();
    }
    throw error;
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function apiUploadTask(
  path: string,
  file: File,
  onProgress?: (percent: number) => void,
): UploadTask<UploadResponse> {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<UploadResponse>((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", buildUrl(path));
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as UploadResponse);
        return;
      }
      const body = xhr.response as Partial<ApiError> | null;
      reject(
        new ApiException(
          xhr.status,
          body?.error ?? "upload_failed",
          body?.message ?? "上传失败，请稍后重试",
        ),
      );
    };
    xhr.onerror = () => reject(networkError());
    xhr.onabort = () => reject(new DOMException("Upload aborted", "AbortError"));
    xhr.send(formData);
  });
  return {
    promise,
    abort: () => xhr.abort(),
  };
}

export async function apiUpload(
  path: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return apiUploadTask(path, file, onProgress).promise;
}
