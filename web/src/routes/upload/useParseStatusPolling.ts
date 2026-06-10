import { useEffect } from "react";
import { ApiException, apiGet } from "../../lib/api";
import type { ProjectStatus } from "../../lib/types";

export const POLL_INTERVAL_MS = 2000;
export const POLL_MAX_ATTEMPTS = 60;

interface PollingCallbacks {
  onReady: () => void;
  onFailed: (code: string) => void;
  onTimeout: () => void;
}

export function useParseStatusPolling(
  projectId: string | null,
  active: boolean,
  callbacks: PollingCallbacks,
) {
  useEffect(() => {
    if (!active || !projectId) {
      return undefined;
    }

    let cancelled = false;
    let timeoutId: number | undefined;

    const poll = async (attempt: number) => {
      try {
        const status = await apiGet<ProjectStatus>(`/projects/${projectId}/status`);
        if (cancelled) {
          return;
        }
        if (status.status === "ready") {
          callbacks.onReady();
          return;
        }
        if (status.status === "failed") {
          callbacks.onFailed(status.error_code ?? "project_error");
          return;
        }
        if (attempt >= POLL_MAX_ATTEMPTS - 1) {
          callbacks.onTimeout();
          return;
        }
        timeoutId = window.setTimeout(() => void poll(attempt + 1), POLL_INTERVAL_MS);
      } catch (error) {
        if (cancelled) {
          return;
        }
        callbacks.onFailed(error instanceof ApiException ? error.code : "network_error");
      }
    };

    void poll(0);
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [active, callbacks, projectId]);
}
