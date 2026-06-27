import { useCallback, useState } from "react";
import { getPaperPlan, postUserSupply } from "../../lib/paperApi";
import type { UserSuppliedResponse } from "../../lib/paperTypes";
import type { PaperPlanUpdate } from "./usePaperResult";

type SupplyStatus = "idle" | "submitting" | "success" | "failed" | "refresh_failed";

interface UseUserSupplyArgs {
  paperId: string;
  onPlanUpdate: (update: PaperPlanUpdate) => void;
}

export function useUserSupply({ paperId, onPlanUpdate }: UseUserSupplyArgs) {
  const [status, setStatus] = useState<SupplyStatus>("idle");

  const submit = useCallback(
    async (responses: UserSuppliedResponse[]) => {
      if (responses.length === 0) {
        return;
      }
      setStatus("submitting");
      try {
        const updated = await postUserSupply(paperId, { user_supplied_responses: responses });
        onPlanUpdate({ plan: updated.updated_plan });
        try {
          const refreshed = await getPaperPlan(paperId);
          onPlanUpdate({
            plan: refreshed.plan,
            missingPrompts: refreshed.missing_prompts,
            remainingMissingPrompts: refreshed.remaining_missing_prompts,
          });
          setStatus("success");
        } catch {
          setStatus("refresh_failed");
        }
      } catch {
        setStatus("failed");
      }
    },
    [onPlanUpdate, paperId],
  );

  return { status, submit };
}
