import { useCallback, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";
import { uploadDocument } from "../lib/paperApi";
import { resolveErrorMessage } from "../lib/errorMessages";
import { PaperDropzone } from "./paper/PaperDropzone";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

type PaperUploadState =
  | { status: "idle"; file: null; progress: number; errorCode?: string }
  | { status: "dragging"; file: null; progress: number; errorCode?: string }
  | { status: "uploading"; file: File; progress: number; errorCode?: string }
  | { status: "failed"; file: File | null; progress: number; errorCode: string };

type PaperUploadAction =
  | { type: "DRAG"; dragging: boolean }
  | { type: "UPLOAD_START"; file: File }
  | { type: "PROGRESS"; progress: number }
  | { type: "FAIL"; errorCode: string }
  | { type: "RESET_TO_IDLE" };

const initialState: PaperUploadState = { status: "idle", file: null, progress: 0 };

function reducer(state: PaperUploadState, action: PaperUploadAction): PaperUploadState {
  switch (action.type) {
    case "DRAG":
      if (state.status !== "idle" && state.status !== "dragging") {
        return state;
      }
      return action.dragging ? { status: "dragging", file: null, progress: 0 } : initialState;
    case "UPLOAD_START":
      return { status: "uploading", file: action.file, progress: 0 };
    case "PROGRESS":
      return state.status === "uploading" ? { ...state, progress: action.progress } : state;
    case "FAIL":
      return {
        status: "failed",
        file: state.file,
        progress: state.progress,
        errorCode: action.errorCode,
      };
    case "RESET_TO_IDLE":
      return initialState;
  }
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

export function PaperUploadPage() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<(() => void) | null>(null);
  const navigate = useNavigate();

  const startUpload = useCallback(
    (file: File) => {
      const validationError = validatePaper(file);
      if (validationError) {
        dispatch({ type: "UPLOAD_START", file });
        dispatch({ type: "FAIL", errorCode: validationError });
        return;
      }

      dispatch({ type: "UPLOAD_START", file });
      const task = uploadDocument(file, (progress) => {
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
            dispatch({ type: "RESET_TO_IDLE" });
            return;
          }
          const code =
            error && typeof error === "object" && "code" in error
              ? String(error.code)
              : "document_parse_failed";
          dispatch({ type: "FAIL", errorCode: code });
        });
    },
    [navigate],
  );

  const busy = state.status === "uploading";
  const errorMessage =
    state.status === "failed"
      ? resolveErrorMessage(state.errorCode) || "论文解析失败,请检查文件格式或稍后重试。"
      : undefined;

  return (
    <main className="paper-upload-page">
      <PanoramaScene panoramaX={0} />
      <section className="paper-upload-content" aria-label="上传论文文件">
        <div className="paper-upload-copy">
          <p className="section-kicker">PAPER TO MODEL</p>
          <h1>资料入口</h1>
          <p className="paper-copy">上传论文或报告后,生成可对照 MATLAB / Simulink 搭建的阅读工作台。</p>
        </div>
        {busy && state.file ? (
          <div className="upload-status-card paper-upload-status" aria-live="polite">
            <h2>{state.file.name}</h2>
            <p>正在解析论文并生成建模路线…</p>
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
            errorMessage={errorMessage}
            onDragState={(dragging) => dispatch({ type: "DRAG", dragging })}
            onFile={startUpload}
          />
        )}
      </section>
    </main>
  );
}
