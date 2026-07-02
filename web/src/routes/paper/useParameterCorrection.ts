import { useCallback, useState } from "react";
import { ApiException } from "../../lib/api";
import {
  getParameterCorrections,
  postParameterCorrection,
  postUndoParameterCorrection,
} from "../../lib/paperApi";
import type { ParameterCorrectionRequest } from "../../lib/paperTypes";
import type { PaperPlanUpdate } from "./usePaperResult";

type CorrectionStatus = "idle" | "submitting" | "undoing" | "success" | "failed";

interface UseParameterCorrectionArgs {
  paperId: string;
  onPlanUpdate: (update: PaperPlanUpdate) => void;
}

function toApiException(error: unknown): ApiException {
  if (error instanceof ApiException) {
    return error;
  }
  return new ApiException(500, "correction_store_failed", "纠错保存失败,旧结果已保留");
}

export function useParameterCorrection({ paperId, onPlanUpdate }: UseParameterCorrectionArgs) {
  const [status, setStatus] = useState<CorrectionStatus>("idle");
  const [error, setError] = useState<ApiException | null>(null);

  const refreshCorrections = useCallback(async () => {
    const response = await getParameterCorrections(paperId);
    return response.corrections;
  }, [paperId]);

  const apply = useCallback(
    async (request: ParameterCorrectionRequest): Promise<boolean> => {
      setStatus("submitting");
      setError(null);
      try {
        const response = await postParameterCorrection(paperId, request);
        const corrections = await refreshCorrections();
        onPlanUpdate({
          plan: response.updated_plan,
          parameterCorrections: corrections,
        });
        setStatus("success");
        return true;
      } catch (caught) {
        setError(toApiException(caught));
        setStatus("failed");
        return false;
      }
    },
    [onPlanUpdate, paperId, refreshCorrections],
  );

  const undo = useCallback(
    async (correctionId: string): Promise<boolean> => {
      setStatus("undoing");
      setError(null);
      try {
        const response = await postUndoParameterCorrection(paperId, correctionId);
        const corrections = await refreshCorrections();
        onPlanUpdate({
          plan: response.updated_plan,
          parameterCorrections: corrections,
        });
        setStatus("success");
        return true;
      } catch (caught) {
        setError(toApiException(caught));
        setStatus("failed");
        return false;
      }
    },
    [onPlanUpdate, paperId, refreshCorrections],
  );

  const dismissError = useCallback(() => {
    setError(null);
    setStatus("idle");
  }, []);

  return { status, error, apply, undo, dismissError };
}
