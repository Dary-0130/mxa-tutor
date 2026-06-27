import { type KeyboardEvent, useCallback, useMemo, useReducer, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadScene } from "../components/scene/UploadScene";
import { apiUploadTask } from "../lib/api";
import { resolveErrorMessage } from "../lib/errorMessages";
import { UploadDropzone } from "./upload/UploadDropzone";
import { UploadStatusCard } from "./upload/UploadStatusCard";
import { useParseStatusPolling } from "./upload/useParseStatusPolling";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

type EntryTabKey = "engineering" | "paper";

const ENTRY_TAB_IDS: Record<EntryTabKey, string> = {
  engineering: "home-entry-tab-engineering",
  paper: "home-entry-tab-paper",
};

const ENTRY_PANEL_IDS: Record<EntryTabKey, string> = {
  engineering: "home-entry-panel-engineering",
  paper: "home-entry-panel-paper",
};

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
  const [selectedTab, setSelectedTab] = useState<EntryTabKey>("engineering");
  const abortRef = useRef<(() => void) | null>(null);
  const engineeringTabRef = useRef<HTMLButtonElement | null>(null);
  const paperTabRef = useRef<HTMLButtonElement | null>(null);
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
  const activeTab: EntryTabKey = busy ? "engineering" : selectedTab;

  const activateTab = useCallback(
    (tab: EntryTabKey) => {
      if (busy && tab === "paper") {
        return;
      }
      setSelectedTab(tab);
    },
    [busy],
  );

  const focusTab = useCallback((tab: EntryTabKey) => {
    if (tab === "engineering") {
      engineeringTabRef.current?.focus();
      return;
    }
    paperTabRef.current?.focus();
  }, []);

  const handleTabKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, currentTab: EntryTabKey) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(currentTab);
        return;
      }

      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
        return;
      }

      event.preventDefault();
      const nextTab: EntryTabKey = currentTab === "engineering" ? "paper" : "engineering";
      if (busy && nextTab === "paper") {
        setSelectedTab("engineering");
        focusTab("engineering");
        return;
      }
      setSelectedTab(nextTab);
      focusTab(nextTab);
    },
    [activateTab, busy, focusTab],
  );

  return (
    <main className="upload-page">
      <UploadScene state={sceneState} progress={state.progress} />
      <div className="upload-corner-tag" aria-hidden="true">
        MATLAB · SIMULINK
      </div>
      <section className="upload-content" aria-label="首页入口">
        <div className="upload-copy">
          <h1 className="upload-hero-brand">MXA TUTOR</h1>
          <p className="upload-hero-tagline">工程导览 / 资料复现</p>
        </div>
        <div className="upload-entry-shell">
          <div className="upload-entry-tabs" role="tablist" aria-label="首页入口">
            <button
              ref={engineeringTabRef}
              id={ENTRY_TAB_IDS.engineering}
              type="button"
              role="tab"
              aria-selected={activeTab === "engineering"}
              aria-controls={ENTRY_PANEL_IDS.engineering}
              className={`upload-entry-tab${activeTab === "engineering" ? " upload-entry-tab--active" : ""}`}
              tabIndex={activeTab === "engineering" ? 0 : -1}
              onClick={() => activateTab("engineering")}
              onKeyDown={(event) => handleTabKeyDown(event, "engineering")}
            >
              工程导览
            </button>
            <button
              ref={paperTabRef}
              id={ENTRY_TAB_IDS.paper}
              type="button"
              role="tab"
              aria-selected={activeTab === "paper"}
              aria-controls={ENTRY_PANEL_IDS.paper}
              aria-disabled={busy ? "true" : undefined}
              className={`upload-entry-tab${activeTab === "paper" ? " upload-entry-tab--active" : ""}`}
              tabIndex={activeTab === "paper" ? 0 : -1}
              onClick={() => activateTab("paper")}
              onKeyDown={(event) => handleTabKeyDown(event, "paper")}
            >
              资料复现
            </button>
          </div>

          {activeTab === "engineering" ? (
            <div
              id={ENTRY_PANEL_IDS.engineering}
              className="upload-entry-panel"
              role="tabpanel"
              aria-labelledby={ENTRY_TAB_IDS.engineering}
            >
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
            </div>
          ) : (
            <div
              id={ENTRY_PANEL_IDS.paper}
              className="upload-entry-panel"
              role="tabpanel"
              aria-labelledby={ENTRY_TAB_IDS.paper}
            >
              <div className="upload-paper-entry">
                <p>上传论文 / 报告后，系统将生成复现路线图、参数对应说明与调参方向。该入口独立于工程 .zip 解析流程。</p>
                <button type="button" className="text-command" onClick={() => navigate("/paper")}>
                  进入资料复现 →
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
