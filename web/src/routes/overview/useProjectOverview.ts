import { useCallback, useEffect, useState } from "react";
import { ApiException, apiGet } from "../../lib/api";
import type { ProjectOverview } from "../../lib/types";

interface OverviewState {
  data: ProjectOverview | null;
  loading: boolean;
  error: ApiException | null;
}

export function useProjectOverview(projectId: string) {
  const [state, setState] = useState<OverviewState>({
    data: null,
    loading: true,
    error: null,
  });
  const [requestKey, setRequestKey] = useState(0);

  const retry = useCallback(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    setRequestKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (!projectId) {
      return undefined;
    }
    let cancelled = false;
    apiGet<ProjectOverview>(`/projects/${projectId}/overview`)
      .then((data) => {
        if (!cancelled) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const apiError =
          error instanceof ApiException
            ? error
            : new ApiException(0, "network_error", "网络连接失败,请检查网络后重试");
        setState({ data: null, loading: false, error: apiError });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, requestKey]);

  return { ...state, retry };
}
