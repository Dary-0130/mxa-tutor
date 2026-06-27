import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { ApiException } from "../../lib/api";
import { getPaperPlan, getPaperSpec } from "../../lib/paperApi";
import type {
  MissingParameterPrompt,
  ModelGenerationPlan,
  PaperPlanResponse,
  PaperSpec,
  UploadDocumentResponse,
} from "../../lib/paperTypes";

export interface PaperResultData {
  paperId: string;
  spec: PaperSpec;
  plan: ModelGenerationPlan;
  missingPrompts: MissingParameterPrompt[];
  remainingMissingPrompts: MissingParameterPrompt[];
}

export type PaperPlanUpdate = {
  plan: ModelGenerationPlan;
  missingPrompts?: MissingParameterPrompt[];
  remainingMissingPrompts?: MissingParameterPrompt[];
};

type LoadState = {
  data: PaperResultData | null;
  loading: boolean;
  error: ApiException | null;
};

function toApiException(error: unknown): ApiException {
  if (error instanceof ApiException) {
    return error;
  }
  return new ApiException(500, "document_parse_failed", "论文解析失败,请检查文件格式或稍后重试。");
}

function isUploadDocumentResponse(value: unknown): value is UploadDocumentResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<UploadDocumentResponse>;
  return Boolean(candidate.paper_id && candidate.spec && candidate.plan && candidate.missing_prompts);
}

function applyPlanResponse(data: PaperResultData, response: PaperPlanResponse): PaperResultData {
  return {
    ...data,
    plan: response.plan,
    missingPrompts: response.missing_prompts,
    remainingMissingPrompts: response.remaining_missing_prompts,
  };
}

async function fetchPaperResult(paperId: string): Promise<PaperResultData> {
  const [specResponse, planResponse] = await Promise.all([
    getPaperSpec(paperId),
    getPaperPlan(paperId),
  ]);
  return {
    paperId,
    spec: specResponse.spec,
    plan: planResponse.plan,
    missingPrompts: planResponse.missing_prompts,
    remainingMissingPrompts: planResponse.remaining_missing_prompts,
  };
}

export function usePaperResult(paperId: string | undefined) {
  const location = useLocation();
  const routeData = useMemo<PaperResultData | null>(() => {
    if (!paperId || !isUploadDocumentResponse(location.state)) {
      return null;
    }
    return {
      paperId,
      spec: location.state.spec,
      plan: location.state.plan,
      missingPrompts: location.state.missing_prompts,
      remainingMissingPrompts: location.state.missing_prompts,
    };
  }, [location.state, paperId]);

  const [state, setState] = useState<LoadState>(() =>
    paperId
      ? { data: routeData, loading: !routeData, error: null }
      : {
          data: null,
          loading: false,
          error: new ApiException(404, "paper_not_found", "论文结果不存在或已过期,请重新上传。"),
        },
  );

  const loadFromServer = useCallback(async () => {
    if (!paperId) {
      setState({
        data: null,
        loading: false,
        error: new ApiException(404, "paper_not_found", "论文结果不存在或已过期,请重新上传。"),
      });
      return;
    }
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      setState({ data: await fetchPaperResult(paperId), loading: false, error: null });
    } catch (error) {
      setState({ data: null, loading: false, error: toApiException(error) });
    }
  }, [paperId]);

  useEffect(() => {
    let cancelled = false;
    if (!paperId) {
      return undefined;
    }
    if (!routeData) {
      queueMicrotask(() => {
        if (!cancelled) {
          setState((current) => ({ ...current, loading: true, error: null }));
        }
      });
      fetchPaperResult(paperId)
        .then((data) => {
          if (!cancelled) {
            setState({ data, loading: false, error: null });
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setState({ data: null, loading: false, error: toApiException(error) });
          }
        });
      return () => {
        cancelled = true;
      };
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setState({ data: routeData, loading: false, error: null });
      }
    });
    getPaperPlan(paperId)
      .then((response) => {
        if (!cancelled) {
          setState((current) =>
            current.data
              ? { data: applyPlanResponse(current.data, response), loading: false, error: null }
              : current,
          );
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [loadFromServer, paperId, routeData]);

  const updatePlan = useCallback((update: PaperPlanUpdate) => {
    setState((current) => {
      if (!current.data) {
        return current;
      }
      return {
        data: {
          ...current.data,
          plan: update.plan,
          missingPrompts: update.missingPrompts ?? current.data.missingPrompts,
          remainingMissingPrompts:
            update.remainingMissingPrompts ?? current.data.remainingMissingPrompts,
        },
        loading: false,
        error: null,
      };
    });
  }, []);

  return { ...state, retry: loadFromServer, updatePlan };
}
