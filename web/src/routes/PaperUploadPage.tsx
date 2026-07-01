import { useCallback, useMemo, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";
import { resolveErrorMessage } from "../lib/errorMessages";
import { uploadDocument } from "../lib/paperApi";
import { PaperDropzone } from "./paper/PaperDropzone";
import { PaperUploadQueue, type PaperUploadQueueItem } from "./paper/PaperUploadQueue";
import { buildPaperUploadSubmission } from "./paper/paperUploadLogic";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const MAX_PAPER_UPLOAD_FILES = 5;

type PaperUploadStatus = "idle" | "dragging" | "selected" | "uploading" | "failed";

interface PaperUploadState {
  status: PaperUploadStatus;
  items: PaperUploadQueueItem[];
  primaryLocalId: string | null;
  progress: number;
  errorCode?: string;
  noticeMessage?: string;
}

type PaperUploadAction =
  | { type: "DRAG"; dragging: boolean }
  | { type: "ADD_FILES"; files: File[] }
  | { type: "REMOVE_ITEM"; localId: string }
  | { type: "TOGGLE_PRIMARY"; localId: string }
  | { type: "UPLOAD_START" }
  | { type: "PROGRESS"; progress: number }
  | { type: "FAIL"; errorCode: string }
  | { type: "UPLOAD_ABORTED" };

const initialState: PaperUploadState = {
  status: "idle",
  items: [],
  primaryLocalId: null,
  progress: 0,
};

function createLocalId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `paper-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function fileFingerprint(file: File): string {
  return `${file.name}::${file.size}::${file.lastModified}`;
}

function validatePaper(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
    return "unsupported_document_format";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "document_too_large";
  }
  return null;
}

function validationMessage(code: string): string {
  if (code === "unsupported_document_format") {
    return "仅支持 PDF 或 DOCX 文件。";
  }
  if (code === "document_too_large") {
    return "文件超过 50MB,请压缩后再上传。";
  }
  return "该文件暂不可用。";
}

function createQueueItem(file: File): PaperUploadQueueItem {
  const validationCode = validatePaper(file);
  return {
    localId: createLocalId(),
    file,
    fingerprint: fileFingerprint(file),
    validation: validationCode ? "invalid" : "valid",
    validationMessage: validationCode ? validationMessage(validationCode) : undefined,
  };
}

function normalizePrimary(
  items: PaperUploadQueueItem[],
  primaryLocalId: string | null,
): string | null {
  if (primaryLocalId === null) {
    return null;
  }
  const primaryItem = items.find((item) => item.localId === primaryLocalId);
  return primaryItem?.validation === "valid" ? primaryLocalId : null;
}

function addFilesToState(state: PaperUploadState, files: File[]): PaperUploadState {
  const existingFingerprints = new Set(state.items.map((item) => item.fingerprint));
  const incomingFingerprints = new Set<string>();
  const addedItems: PaperUploadQueueItem[] = [];
  let duplicateCount = 0;
  let tooManyCount = 0;
  let validCount = state.items.filter((item) => item.validation === "valid").length;

  for (const file of files) {
    const fingerprint = fileFingerprint(file);
    if (existingFingerprints.has(fingerprint) || incomingFingerprints.has(fingerprint)) {
      duplicateCount += 1;
      continue;
    }
    incomingFingerprints.add(fingerprint);
    const item = createQueueItem(file);
    if (item.validation === "valid" && validCount >= MAX_PAPER_UPLOAD_FILES) {
      tooManyCount += 1;
      continue;
    }
    if (item.validation === "valid") {
      validCount += 1;
    }
    addedItems.push(item);
  }

  const items = [...state.items, ...addedItems];
  const messages = [
    duplicateCount > 0 ? "已跳过完全相同的重复文件。" : null,
    tooManyCount > 0 ? `最多一次上传 ${MAX_PAPER_UPLOAD_FILES} 篇资料。` : null,
  ].filter(Boolean);

  return {
    status: items.length > 0 ? "selected" : "idle",
    items,
    primaryLocalId: normalizePrimary(items, state.primaryLocalId),
    progress: 0,
    noticeMessage: messages.length > 0 ? messages.join(" ") : undefined,
  };
}

function reducer(state: PaperUploadState, action: PaperUploadAction): PaperUploadState {
  switch (action.type) {
    case "DRAG":
      if (state.status === "uploading" || state.items.length > 0) {
        return state;
      }
      return action.dragging ? { ...state, status: "dragging" } : initialState;
    case "ADD_FILES":
      if (state.status === "uploading") {
        return state;
      }
      return addFilesToState(state, action.files);
    case "REMOVE_ITEM": {
      if (state.status === "uploading") {
        return state;
      }
      const items = state.items.filter((item) => item.localId !== action.localId);
      return {
        status: items.length > 0 ? "selected" : "idle",
        items,
        primaryLocalId:
          action.localId === state.primaryLocalId
            ? null
            : normalizePrimary(items, state.primaryLocalId),
        progress: 0,
      };
    }
    case "TOGGLE_PRIMARY": {
      if (state.status === "uploading") {
        return state;
      }
      const item = state.items.find((candidate) => candidate.localId === action.localId);
      if (!item || item.validation !== "valid") {
        return state;
      }
      return {
        ...state,
        status: "selected",
        primaryLocalId: state.primaryLocalId === action.localId ? null : action.localId,
        errorCode: undefined,
        noticeMessage: undefined,
      };
    }
    case "UPLOAD_START":
      return { ...state, status: "uploading", progress: 0, errorCode: undefined, noticeMessage: undefined };
    case "PROGRESS":
      return state.status === "uploading" ? { ...state, progress: action.progress } : state;
    case "FAIL":
      return {
        ...state,
        status: "failed",
        progress: 0,
        errorCode: action.errorCode,
        noticeMessage: undefined,
      };
    case "UPLOAD_ABORTED":
      return {
        ...state,
        status: state.items.length > 0 ? "selected" : "idle",
        progress: 0,
        errorCode: undefined,
        noticeMessage: undefined,
      };
  }
}

export function PaperUploadPage() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<(() => void) | null>(null);
  const navigate = useNavigate();
  const validCount = useMemo(
    () => state.items.filter((item) => item.validation === "valid").length,
    [state.items],
  );
  const busy = state.status === "uploading";
  const hasSelection = state.items.length > 0;
  const canSubmit = validCount > 0 && validCount <= MAX_PAPER_UPLOAD_FILES && !busy;

  const startUpload = useCallback(() => {
    const submission = buildPaperUploadSubmission(state.items, state.primaryLocalId);
    if (submission.files.length === 0) {
      dispatch({ type: "FAIL", errorCode: "document_required" });
      return;
    }
    dispatch({ type: "UPLOAD_START" });
    const task = uploadDocument(submission.files, submission.primaryIndex, (progress) => {
      dispatch({ type: "PROGRESS", progress });
    });
    abortRef.current = task.abort;
    task.promise
      .then((response) => {
        abortRef.current = null;
        navigate(`/paper/${response.paper_id}`, { state: response });
      })
      .catch((error: unknown) => {
        abortRef.current = null;
        if (error instanceof DOMException && error.name === "AbortError") {
          dispatch({ type: "UPLOAD_ABORTED" });
          return;
        }
        const code =
          error && typeof error === "object" && "code" in error
            ? String(error.code)
            : "document_parse_failed";
        dispatch({ type: "FAIL", errorCode: code });
      });
  }, [navigate, state.items, state.primaryLocalId]);

  const queueErrorMessage =
    state.status === "failed"
      ? resolveErrorMessage(state.errorCode)
      : hasSelection && validCount === 0
        ? "请选择至少一篇可读取的 PDF/DOCX 文件。"
        : undefined;

  return (
    <main className="paper-upload-page">
      <PanoramaScene panoramaX={0} />
      <section className="paper-upload-content" aria-label="上传论文文件">
        <div className="paper-upload-copy">
          <p className="section-kicker">PAPER TO MODEL</p>
          <h1>资料入口</h1>
        </div>
        <div className="paper-upload-panel-stack">
          {busy ? (
            <div className="upload-status-card paper-upload-status" aria-live="polite">
              <h2>正在生成建模路线</h2>
              <p>{validCount} 篇资料上传中,进度为总上传进度。</p>
              <div className="upload-status-card__row">
                <span>UPLOAD</span>
                <span>{state.progress}%</span>
              </div>
              <div className="upload-progress" aria-hidden="true">
                <span style={{ width: `${state.progress}%` }} />
              </div>
              <button className="paper-secondary-button" type="button" onClick={() => abortRef.current?.()}>
                取消
              </button>
            </div>
          ) : (
            <PaperDropzone
              disabled={busy}
              dragging={state.status === "dragging"}
              onDragState={(dragging) => dispatch({ type: "DRAG", dragging })}
              onFiles={(files) => dispatch({ type: "ADD_FILES", files })}
            />
          )}
          {hasSelection ? (
            <PaperUploadQueue
              items={state.items}
              primaryLocalId={state.primaryLocalId}
              locked={busy}
              canSubmit={canSubmit}
              errorMessage={queueErrorMessage}
              noticeMessage={state.noticeMessage}
              onRemove={(localId) => dispatch({ type: "REMOVE_ITEM", localId })}
              onTogglePrimary={(localId) => dispatch({ type: "TOGGLE_PRIMARY", localId })}
              onSubmit={startUpload}
            />
          ) : null}
        </div>
      </section>
    </main>
  );
}
