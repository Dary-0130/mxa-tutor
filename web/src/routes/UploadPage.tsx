import { useCallback, useMemo, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { UploadScene } from "../components/scene/UploadScene";
import { apiUploadTask } from "../lib/api";
import { resolveErrorMessage } from "../lib/errorMessages";
import { UploadDropzone } from "./upload/UploadDropzone";
import { UploadStatusCard } from "./upload/UploadStatusCard";
import { useParseStatusPolling } from "./upload/useParseStatusPolling";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

type UploadState =
  | { status: "idle"; file: null; progress: number; projectId: null; errorCode?: string }
  | { status: "dragging"; file: null; progress: number; projectId: null; errorCode?: string }
  | { status: "uploading"; file: File; progress: number; projectId: null; errorCode?: string }
  | { status: "parsing"; file: File; progress: number; projectId: string; errorCode?: string }
  | { status: "failed"; file: File | null; progress: number; projectId: string | null; errorCode: string };

type UploadAction =
  | { type: "DRAG"; dragging: boolean }
  | { type: "UPLOAD_START"; file: File }
  | { type: "PROGRESS"; progress: number }
  | { type: "UPLOAD_DONE"; projectId: string }
  | { type: "FAIL"; errorCode: string }
  | { type: "RESET_TO_IDLE" };

const initialState: UploadState = { status: "idle", file: null, progress: 0, projectId: null };

function reducer(state: UploadState, action: UploadAction): UploadState {
  switch (action.type) {
    case "DRAG":
      if (state.status !== "idle" && state.status !== "dragging") {
        return state;
      }
      return action.dragging
        ? { status: "dragging", file: null, progress: 0, projectId: null }
        : initialState;
    case "UPLOAD_START":
      return { status: "uploading", file: action.file, progress: 0, projectId: null };
    case "PROGRESS":
      return state.status === "uploading" ? { ...state, progress: action.progress } : state;
    case "UPLOAD_DONE":
      return state.file
        ? { status: "parsing", file: state.file, progress: 100, projectId: action.projectId }
        : state;
    case "FAIL":
      return {
        status: "failed",
        file: state.file,
        progress: state.progress,
        projectId: state.projectId,
        errorCode: action.errorCode,
      };
    case "RESET_TO_IDLE":
      return initialState;
  }
}

function validateZip(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".zip")) {
    return "file_type_not_allowed";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "project_too_large";
  }
  return null;
}

export function UploadPage() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<(() => void) | null>(null);
  const navigate = useNavigate();

  const uploadCallbacks = useMemo(
    () => ({
      onReady: () => {
        if (state.projectId) {
          navigate(`/view/${state.projectId}`);
        }
      },
      onFailed: (errorCode: string) => dispatch({ type: "FAIL", errorCode }),
      onTimeout: () => dispatch({ type: "FAIL", errorCode: "parse_timeout" }),
    }),
    [navigate, state.projectId],
  );

  useParseStatusPolling(state.projectId, state.status === "parsing", uploadCallbacks);

  const startUpload = useCallback((file: File) => {
    const validationError = validateZip(file);
    if (validationError) {
      dispatch({ type: "UPLOAD_START", file });
      dispatch({ type: "FAIL", errorCode: validationError });
      return;
    }

    dispatch({ type: "UPLOAD_START", file });
    const task = apiUploadTask("/upload", file, (progress) => {
      dispatch({ type: "PROGRESS", progress });
    });
    abortRef.current = task.abort;
    task.promise
      .then((response) => {
        abortRef.current = null;
        dispatch({ type: "UPLOAD_DONE", projectId: response.project_id });
      })
      .catch((error: unknown) => {
        abortRef.current = null;
        if (error instanceof DOMException && error.name === "AbortError") {
          dispatch({ type: "RESET_TO_IDLE" });
          return;
        }
        const code = error && typeof error === "object" && "code" in error ? String(error.code) : "upload_error";
        dispatch({ type: "FAIL", errorCode: code });
      });
  }, []);

  const sceneState = state.status === "dragging" ? "dragging" : state.status;
  const errorMessage = state.status === "failed" ? resolveErrorMessage(state.errorCode) : undefined;
  const busy = state.status === "uploading" || state.status === "parsing";

  return (
    <main className="upload-page">
      <UploadScene state={sceneState} progress={state.progress} />
      <div className="upload-corner-tag" aria-hidden="true">
        MATLAB · SIMULINK
      </div>
      <section className="upload-content" aria-label="上传 MATLAB 工程">
        <div className="upload-copy">
          <h1 className="upload-hero-brand">MXA TUTOR</h1>
          <p className="upload-hero-tagline">工程导览 + 资料复现路线图</p>
          <div className="upload-hero-note" aria-label="资料入口口径">
            <p>资料入口提供模型搭建副驾与参数对应说明。</p>
            <p>
              稳交付:摘要、公式 / 参数、物理含义、模型搭建路线图;尽力交付:.m 脚本骨架;不承诺:打开即跑的完整 .slx 成品、运行结果正确或最优调参。
            </p>
            <p>
              领域限 control_system / signal_processing / power_electronics / communication / motor_control / new_energy;general 资料入口拒绝,图片参数需用户补充。
            </p>
          </div>
        </div>
        {busy && state.file ? (
          <UploadStatusCard
            file={state.file}
            phase={state.status}
            progress={state.progress}
            onCancel={state.status === "uploading" ? () => abortRef.current?.() : undefined}
          />
        ) : (
          <UploadDropzone
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
