import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { ApiException } from "../../lib/api";
import {
  getParameterCorrections,
  getPaperPlan,
  getPaperSpec,
  postPaperReparse,
} from "../../lib/paperApi";
import type {
  MissingParameterPrompt,
  ModelGenerationPlan,
  ParameterCorrection,
  PaperPlanResponse,
  PaperSpec,
  UploadDocumentResponse,
  UploadDocumentStatus,
} from "../../lib/paperTypes";

export interface PaperResultData {
  paperId: string;
  spec: PaperSpec;
  plan: ModelGenerationPlan;
  missingPrompts: MissingParameterPrompt[];
  remainingMissingPrompts: MissingParameterPrompt[];
  parameterCorrections: ParameterCorrection[];
  documentStatuses?: UploadDocumentStatus[];
  version: number;
}

export type PaperPlanUpdate = {
  plan: ModelGenerationPlan;
  missingPrompts?: MissingParameterPrompt[];
  remainingMissingPrompts?: MissingParameterPrompt[];
  parameterCorrections?: ParameterCorrection[];
};

type LoadState = {
  data: PaperResultData | null;
  loading: boolean;
  error: ApiException | null;
  reparsing: boolean;
  reparseError: ApiException | null;
  reparseSourceUnavailable: boolean;
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
  return Boolean(
    candidate.paper_id && candidate.spec && candidate.plan && candidate.missing_prompts,
  );
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
  const [specResponse, planResponse, correctionsResponse] = await Promise.all([
    getPaperSpec(paperId),
    getPaperPlan(paperId),
    getParameterCorrections(paperId),
  ]);
  return {
    paperId,
    spec: specResponse.spec,
    plan: planResponse.plan,
    missingPrompts: planResponse.missing_prompts,
    remainingMissingPrompts: planResponse.remaining_missing_prompts,
    parameterCorrections: correctionsResponse.corrections,
    version: 0,
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
      parameterCorrections: [],
      documentStatuses: location.state.document_statuses,
      version: 0,
    };
  }, [location.state, paperId]);

  const [state, setState] = useState<LoadState>(() =>
    paperId
      ? {
          data: routeData,
          loading: !routeData,
          error: null,
          reparsing: false,
          reparseError: null,
          reparseSourceUnavailable: false,
        }
      : {
          data: null,
          loading: false,
          error: new ApiException(404, "paper_not_found", "论文结果不存在或已过期,请重新上传。"),
          reparsing: false,
          reparseError: null,
          reparseSourceUnavailable: false,
        },
  );

  const loadFromServer = useCallback(async () => {
    if (!paperId) {
      setState({
        data: null,
        loading: false,
        error: new ApiException(404, "paper_not_found", "论文结果不存在或已过期,请重新上传。"),
        reparsing: false,
        reparseError: null,
        reparseSourceUnavailable: false,
      });
      return;
    }
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      setState({
        data: await fetchPaperResult(paperId),
        loading: false,
        error: null,
        reparsing: false,
        reparseError: null,
        reparseSourceUnavailable: false,
      });
    } catch (error) {
      setState({
        data: null,
        loading: false,
        error: toApiException(error),
        reparsing: false,
        reparseError: null,
        reparseSourceUnavailable: false,
      });
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
            setState({
              data,
              loading: false,
              error: null,
              reparsing: false,
              reparseError: null,
              reparseSourceUnavailable: false,
            });
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setState({
              data: null,
              loading: false,
              error: toApiException(error),
              reparsing: false,
              reparseError: null,
              reparseSourceUnavailable: false,
            });
          }
        });
      return () => {
        cancelled = true;
      };
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setState({
          data: routeData,
          loading: false,
          error: null,
          reparsing: false,
          reparseError: null,
          reparseSourceUnavailable: false,
        });
      }
    });
    Promise.all([getPaperPlan(paperId), getParameterCorrections(paperId)])
      .then(([response, corrections]) => {
        if (!cancelled) {
          setState((current) =>
            current.data
              ? {
                  ...current,
                  data: {
                    ...applyPlanResponse(current.data, response),
                    parameterCorrections: corrections.corrections,
                  },
                  loading: false,
                  error: null,
                }
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
          parameterCorrections: update.parameterCorrections ?? current.data.parameterCorrections,
        },
        loading: false,
        error: null,
        reparsing: current.reparsing,
        reparseError: current.reparseError,
        reparseSourceUnavailable: current.reparseSourceUnavailable,
      };
    });
  }, []);

  const reparse = useCallback(async () => {
    if (!paperId || state.reparsing || !state.data) {
      return;
    }
    setState((current) => {
      if (current.reparsing || !current.data) {
        return current;
      }
      return { ...current, reparsing: true, reparseError: null };
    });
    try {
      const response = await postPaperReparse(paperId);
      setState((current) => {
        const previousVersion = current.data?.version ?? 0;
        return {
          data: {
            paperId: response.paper_id,
            spec: response.spec,
            plan: response.plan,
            missingPrompts: response.missing_prompts,
            remainingMissingPrompts: response.remaining_missing_prompts,
            parameterCorrections: [],
            documentStatuses: undefined,
            version: previousVersion + 1,
          },
          loading: false,
          error: null,
          reparsing: false,
          reparseError: null,
          reparseSourceUnavailable: false,
        };
      });
    } catch (error) {
      const apiError = toApiException(error);
      setState((current) => ({
        ...current,
        reparsing: false,
        reparseError: apiError,
        reparseSourceUnavailable:
          current.reparseSourceUnavailable || apiError.code === "reparse_source_unavailable",
      }));
    }
  }, [paperId, state.data, state.reparsing]);

  const dismissReparseError = useCallback(() => {
    setState((current) => ({ ...current, reparseError: null }));
  }, []);

  return { ...state, retry: loadFromServer, updatePlan, reparse, dismissReparseError };
}
