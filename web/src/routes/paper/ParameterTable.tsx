import { useMemo, useState } from "react";
import { GlassCard } from "../../components/ui/GlassCard";
import type {
  MissingParameterPrompt,
  ModelGenerationPlan,
  PaperEvidenceEntry,
  ParameterMapping,
  UserSuppliedResponse,
} from "../../lib/paperTypes";
import { SourceBadge, type SourceBadgeKind } from "./SourceBadge";
import type { PaperPlanUpdate } from "./usePaperResult";
import { useUserSupply } from "./useUserSupply";

interface ParameterTableProps {
  paperId: string;
  plan: ModelGenerationPlan;
  remainingMissingPrompts: MissingParameterPrompt[];
  onPlanUpdate: (update: PaperPlanUpdate) => void;
}

type DraftMap = Record<string, { value: string; unit: string }>;

type ParameterRow = {
  key: string;
  mapping?: ParameterMapping;
  prompt?: MissingParameterPrompt;
};

type SourceRow = {
  kind: "mapping" | "missing";
  source?: "document_extracted" | "user_supplied";
  value?: string | null;
  user_supplied_value?: string | null;
};

function formatEvidence(entry: PaperEvidenceEntry): string {
  const parts: string[] = [];
  if (entry.paper_section_id) {
    parts.push(`章节 ${entry.paper_section_id}`);
  }
  if (entry.equation_id) {
    parts.push(`式(${entry.equation_id})`);
  }
  if (entry.figure_id) {
    parts.push(`图(${entry.figure_id})`);
  }
  return parts.length > 0 ? `依据:${parts.join(" · ")}` : "依据:未标注";
}

function mergeRows(
  mappings: ParameterMapping[],
  prompts: MissingParameterPrompt[],
): ParameterRow[] {
  const usedPromptIds = new Set<string>();
  const rows: ParameterRow[] = mappings.map((mapping, index) => {
    const prompt = prompts.find((candidate) => {
      if (usedPromptIds.has(candidate.prompt_id)) {
        return false;
      }
      return (
        candidate.parameter_name === mapping.paper_param_name ||
        candidate.parameter_name === mapping.model_param_name
      );
    });
    if (prompt) {
      usedPromptIds.add(prompt.prompt_id);
    }
    return { key: `mapping-${mapping.paper_param_name}-${index}`, mapping, prompt };
  });
  for (const prompt of prompts) {
    if (!usedPromptIds.has(prompt.prompt_id)) {
      rows.push({ key: `missing-${prompt.prompt_id}`, prompt });
    }
  }
  return rows;
}

function valueLabel(row: ParameterRow): string {
  if (row.prompt && !row.prompt.user_supplied_value) {
    return "待补充";
  }
  if (row.mapping?.value === "null") {
    return "待补充";
  }
  return row.mapping?.value ?? row.prompt?.user_supplied_value ?? "待补充";
}

function getParamSourceKind(row: SourceRow): SourceBadgeKind {
  if (row.kind === "missing" && !row.user_supplied_value) {
    return "missing_unresolved";
  }
  if (row.source === "user_supplied" && row.value) {
    return "user_supplied_resolved";
  }
  return "document_extracted";
}

function statusMessage(status: ReturnType<typeof useUserSupply>["status"]): string | null {
  if (status === "success") {
    return "已更新参数补充。";
  }
  if (status === "failed") {
    return "参数补充失败,请稍后重试。";
  }
  if (status === "refresh_failed") {
    return "参数已提交,缺参状态刷新失败,可稍后重试。";
  }
  return null;
}

export function ParameterTable({
  paperId,
  plan,
  remainingMissingPrompts,
  onPlanUpdate,
}: ParameterTableProps) {
  const [drafts, setDrafts] = useState<DraftMap>({});
  const rows = useMemo(
    () => mergeRows(plan.parameter_mapping, remainingMissingPrompts),
    [plan.parameter_mapping, remainingMissingPrompts],
  );
  const { status, submit } = useUserSupply({ paperId, onPlanUpdate });
  const message = statusMessage(status);
  const hasPendingPrompts = remainingMissingPrompts.length > 0;

  const updateDraft = (promptId: string, field: "value" | "unit", value: string) => {
    setDrafts((current) => ({
      ...current,
      [promptId]: {
        value: field === "value" ? value : (current[promptId]?.value ?? ""),
        unit: field === "unit" ? value : (current[promptId]?.unit ?? ""),
      },
    }));
  };

  const submitDrafts = () => {
    const responses: UserSuppliedResponse[] = remainingMissingPrompts.flatMap((prompt) => {
      const draft = drafts[prompt.prompt_id];
      const value = draft?.value.trim();
      if (!value) {
        return [];
      }
      const unit = draft.unit.trim();
      return [
        {
          prompt_id: prompt.prompt_id,
          parameter_name: prompt.parameter_name,
          user_supplied_value: value,
          user_supplied_unit: unit || null,
        },
      ];
    });
    void submit(responses);
  };

  if (rows.length === 0) {
    return <p className="empty-state-text">暂无可展示的参数对照。</p>;
  }

  return (
    <div className="paper-parameter-area">
      <p className="paper-secondary">各参数已标注来源。缺失参数可选填,留空不影响其余建模步骤。</p>
      <div className="paper-param-table" role="table" aria-label="参数对照">
        <div className="paper-param-row paper-param-row--head" role="row">
          <span role="columnheader">论文参数</span>
          <span role="columnheader">模型参数</span>
          <span role="columnheader">数值</span>
          <span role="columnheader">来源</span>
          <span role="columnheader">补充</span>
        </div>
        {rows.map((row) => {
          const prompt = row.prompt;
          const draft = prompt ? drafts[prompt.prompt_id] : undefined;
          const sourceKind = getParamSourceKind({
            kind: prompt && !prompt.user_supplied_value ? "missing" : "mapping",
            source: row.mapping?.source ?? prompt?.source,
            value: row.mapping?.value ?? prompt?.user_supplied_value,
            user_supplied_value: prompt?.user_supplied_value,
          });
          return (
            <div className="paper-param-row" role="row" key={row.key}>
              <span className="paper-token" role="cell">
                {row.mapping?.paper_param_name ?? prompt?.parameter_name}
              </span>
              <span className="paper-token" role="cell">
                {row.mapping?.model_param_name ?? "待补充"}
              </span>
              <span className="paper-token" role="cell">
                {valueLabel(row)}
                {row.mapping?.unit ? <small>{row.mapping.unit}</small> : null}
              </span>
              <span role="cell">
                <SourceBadge kind={sourceKind} />
              </span>
              <span role="cell">
                {prompt && !prompt.user_supplied_value ? (
                  <label className="paper-missing-input">
                    <input
                      value={draft?.value ?? ""}
                      placeholder="数值(可选)"
                      onChange={(event) => updateDraft(prompt.prompt_id, "value", event.target.value)}
                    />
                    <input
                      value={draft?.unit ?? ""}
                      placeholder={prompt.suggested_unit ?? "单位"}
                      onChange={(event) => updateDraft(prompt.prompt_id, "unit", event.target.value)}
                    />
                    <small>{formatEvidence(prompt.paper_reference)}</small>
                  </label>
                ) : (
                  null
                )}
              </span>
            </div>
          );
        })}
      </div>
      <div className="paper-param-actions">
        <button
          className="paper-primary-button"
          type="button"
          disabled={status === "submitting" || remainingMissingPrompts.length === 0}
          onClick={submitDrafts}
        >
          提交补充
        </button>
        {message || !hasPendingPrompts ? (
          <span className="paper-secondary">{message ?? "暂无待补充参数。"}</span>
        ) : null}
      </div>
      <GlassCard className="paper-readable-card paper-plan-evidence">
        <h3>路线图整体依据</h3>
        {plan.evidence.length === 0 ? (
          <p className="empty-state-text">暂无可展示的参数对照。</p>
        ) : (
          <ul>
            {plan.evidence.map((entry, index) => (
              <li key={`${entry.paper_section_id ?? "evidence"}-${index}`}>{formatEvidence(entry)}</li>
            ))}
          </ul>
        )}
      </GlassCard>
    </div>
  );
}
