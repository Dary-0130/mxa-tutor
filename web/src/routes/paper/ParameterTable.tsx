import { useMemo, useState } from "react";
import { GlassCard } from "../../components/ui/GlassCard";
import { resolveErrorMessage } from "../../lib/errorMessages";
import { formatEvidence } from "../../lib/paperEvidence";
import type {
  MissingParameterPrompt,
  ModelGenerationPlan,
  ParameterCorrection,
  ParameterCorrectionRequest,
  ParameterMapping,
  UserSuppliedResponse,
} from "../../lib/paperTypes";
import { makeMissingPromptAnchorId, makePlanMappingAnchorId } from "./paperAnchors";
import { SourceBadge, type SourceBadgeKind } from "./SourceBadge";
import { useParameterCorrection } from "./useParameterCorrection";
import type { PaperPlanUpdate } from "./usePaperResult";
import { useUserSupply } from "./useUserSupply";

interface ParameterTableProps {
  paperId: string;
  plan: ModelGenerationPlan;
  remainingMissingPrompts: MissingParameterPrompt[];
  parameterCorrections: ParameterCorrection[];
  onPlanUpdate: (update: PaperPlanUpdate) => void;
}

type DraftMap = Record<string, { value: string; unit: string }>;
type CorrectionDraftMap = Record<string, { value: string; unit: string }>;

type ParameterRow = {
  key: string;
  mappingIndex?: number;
  mapping?: ParameterMapping;
  prompt?: MissingParameterPrompt;
};

type SourceRow = {
  kind: "mapping" | "missing";
  source?: "document_extracted" | "user_supplied";
  value?: string | null;
  user_supplied_value?: string | null;
};

const EMPTY_ARRAY: never[] = [];

function arrayOrEmpty<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : EMPTY_ARRAY;
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
    return {
      key: `mapping-${mapping.paper_param_name}-${index}`,
      mappingIndex: index,
      mapping,
      prompt,
    };
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

function correctionForMapping(
  corrections: ParameterCorrection[],
  mapping: ParameterMapping,
  mappingIndex: number,
): ParameterCorrection | undefined {
  return corrections.find(
    (correction) =>
      correction.target.plan_mapping_index === mappingIndex &&
      correction.target.paper_param_name === mapping.paper_param_name &&
      correction.target.model_param_name === mapping.model_param_name,
  );
}

function formatValueUnit(value: string, unit: string | null | undefined): string {
  return unit ? `${value} ${unit}` : value;
}

function correctionErrorMessage(error: ReturnType<typeof useParameterCorrection>["error"]): string {
  if (!error) {
    return "";
  }
  return resolveErrorMessage(error.code);
}

export function ParameterTable({
  paperId,
  plan,
  remainingMissingPrompts,
  parameterCorrections,
  onPlanUpdate,
}: ParameterTableProps) {
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [correctionDrafts, setCorrectionDrafts] = useState<CorrectionDraftMap>({});
  const [editingCorrectionKey, setEditingCorrectionKey] = useState<string | null>(null);
  const parameterMappings = arrayOrEmpty(plan.parameter_mapping);
  const missingPrompts = arrayOrEmpty(remainingMissingPrompts);
  const corrections = arrayOrEmpty(parameterCorrections);
  const planEvidence = arrayOrEmpty(plan.evidence);
  const rows = useMemo(
    () => mergeRows(parameterMappings, missingPrompts),
    [parameterMappings, missingPrompts],
  );
  const { status, submit } = useUserSupply({ paperId, onPlanUpdate });
  const {
    status: correctionStatus,
    error: correctionError,
    apply: applyCorrection,
    undo: undoCorrection,
    dismissError: dismissCorrectionError,
  } = useParameterCorrection({ paperId, onPlanUpdate });
  const message = statusMessage(status);
  const correctionMessage = correctionErrorMessage(correctionError);
  const hasPendingPrompts = missingPrompts.length > 0;

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
    const responses: UserSuppliedResponse[] = missingPrompts.flatMap((prompt) => {
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

  const startCorrectionEdit = (rowKey: string, mapping: ParameterMapping) => {
    setEditingCorrectionKey(rowKey);
    setCorrectionDrafts((current) => ({
      ...current,
      [rowKey]: {
        value: mapping.value === "null" ? "" : mapping.value,
        unit: mapping.unit ?? "",
      },
    }));
  };

  const updateCorrectionDraft = (rowKey: string, field: "value" | "unit", value: string) => {
    setCorrectionDrafts((current) => ({
      ...current,
      [rowKey]: {
        value: field === "value" ? value : (current[rowKey]?.value ?? ""),
        unit: field === "unit" ? value : (current[rowKey]?.unit ?? ""),
      },
    }));
  };

  const submitCorrection = async (
    rowKey: string,
    mapping: ParameterMapping,
    mappingIndex: number,
  ) => {
    const draft = correctionDrafts[rowKey];
    const value = draft?.value.trim();
    if (!value) {
      return;
    }
    const unit = draft.unit.trim();
    const request: ParameterCorrectionRequest = {
      target: {
        paper_param_name: mapping.paper_param_name,
        model_param_name: mapping.model_param_name,
        plan_mapping_index: mappingIndex,
        expected_value: mapping.value,
        expected_unit: mapping.unit ?? null,
      },
      corrected_value: value,
      corrected_unit: unit ? unit : null,
    };
    const ok = await applyCorrection(request);
    if (ok) {
      setEditingCorrectionKey(null);
    }
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
          const activeCorrection =
            row.mapping && row.mappingIndex !== undefined
              ? correctionForMapping(corrections, row.mapping, row.mappingIndex)
              : undefined;
          const promptAnchorId = prompt ? makeMissingPromptAnchorId(prompt.prompt_id) : undefined;
          const mappingAnchorId =
            row.mapping && row.mappingIndex !== undefined
              ? makePlanMappingAnchorId(
                  row.mappingIndex,
                  row.mapping.paper_param_name,
                  row.mapping.model_param_name,
                )
              : undefined;
          const rowAnchorId = mappingAnchorId ?? (!row.mapping ? promptAnchorId : undefined);
          const draft = prompt ? drafts[prompt.prompt_id] : undefined;
          const correctionDraft = correctionDrafts[row.key];
          const correctionEditing = editingCorrectionKey === row.key;
          const canCorrect =
            Boolean(row.mapping && row.mappingIndex !== undefined) &&
            (row.mapping?.source === "document_extracted" || Boolean(activeCorrection));
          const sourceKind = getParamSourceKind({
            kind: prompt && !prompt.user_supplied_value ? "missing" : "mapping",
            source: row.mapping?.source ?? prompt?.source,
            value: row.mapping?.value ?? prompt?.user_supplied_value,
            user_supplied_value: prompt?.user_supplied_value,
          });
          return (
            <div className="paper-param-row" role="row" key={row.key} id={rowAnchorId}>
              <span className="paper-token" role="cell">
                {row.mapping?.paper_param_name ?? prompt?.parameter_name}
              </span>
              <span className="paper-token" role="cell">
                {row.mapping?.model_param_name ?? "待补充"}
              </span>
              <span className="paper-token" role="cell">
                {activeCorrection ? (
                  <span className="paper-correction-value">
                    <strong>你改的</strong>
                    <span>{formatValueUnit(valueLabel(row), row.mapping?.unit)}</span>
                    <small>
                      AI 原本抽:
                      {formatValueUnit(
                        activeCorrection.original.value,
                        activeCorrection.original.unit,
                      )}
                      {activeCorrection.original.document_label
                        ? ` · ${activeCorrection.original.document_label}`
                        : ""}
                    </small>
                  </span>
                ) : (
                  <>
                    {valueLabel(row)}
                    {row.mapping?.unit ? <small>{row.mapping.unit}</small> : null}
                  </>
                )}
              </span>
              <span role="cell">
                <SourceBadge kind={activeCorrection ? "user_corrected" : sourceKind} />
              </span>
              <span role="cell">
                {row.mapping && promptAnchorId ? (
                  <span id={promptAnchorId} className="paper-anchor-stub" aria-hidden="true" />
                ) : null}
                {correctionEditing && row.mapping && row.mappingIndex !== undefined ? (
                  <label className="paper-correction-input">
                    <input
                      value={correctionDraft?.value ?? ""}
                      placeholder="改为"
                      onChange={(event) =>
                        updateCorrectionDraft(row.key, "value", event.target.value)
                      }
                    />
                    <input
                      value={correctionDraft?.unit ?? ""}
                      placeholder={row.mapping.unit ?? "单位"}
                      onChange={(event) =>
                        updateCorrectionDraft(row.key, "unit", event.target.value)
                      }
                    />
                    <span>
                      <button
                        type="button"
                        disabled={correctionStatus === "submitting"}
                        onClick={() =>
                          void submitCorrection(row.key, row.mapping!, row.mappingIndex!)
                        }
                      >
                        保存
                      </button>
                      <button type="button" onClick={() => setEditingCorrectionKey(null)}>
                        取消
                      </button>
                    </span>
                  </label>
                ) : activeCorrection ? (
                  <span className="paper-correction-actions">
                    <button
                      type="button"
                      disabled={correctionStatus === "submitting" || correctionStatus === "undoing"}
                      onClick={() => row.mapping && startCorrectionEdit(row.key, row.mapping)}
                    >
                      调整
                    </button>
                    <button
                      type="button"
                      disabled={
                        correctionStatus === "submitting" ||
                        correctionStatus === "undoing" ||
                        !activeCorrection.can_undo
                      }
                      onClick={() => void undoCorrection(activeCorrection.correction_id)}
                    >
                      撤销
                    </button>
                  </span>
                ) : canCorrect && row.mapping ? (
                  <button
                    className="paper-inline-action"
                    type="button"
                    disabled={correctionStatus === "submitting" || correctionStatus === "undoing"}
                    onClick={() => startCorrectionEdit(row.key, row.mapping!)}
                  >
                    改
                  </button>
                ) : prompt && !prompt.user_supplied_value ? (
                  <label className="paper-missing-input">
                    <input
                      value={draft?.value ?? ""}
                      placeholder="数值(可选)"
                      onChange={(event) =>
                        updateDraft(prompt.prompt_id, "value", event.target.value)
                      }
                    />
                    <input
                      value={draft?.unit ?? ""}
                      placeholder={prompt.suggested_unit ?? "单位"}
                      onChange={(event) =>
                        updateDraft(prompt.prompt_id, "unit", event.target.value)
                      }
                    />
                    <small>
                      {formatEvidence(prompt.paper_reference, { emptyText: "依据:未标注" })}
                    </small>
                  </label>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
      {correctionMessage ? (
        <aside className="paper-correction-notice" aria-live="polite">
          <span>{correctionMessage}</span>
          <button type="button" onClick={dismissCorrectionError}>
            关闭
          </button>
        </aside>
      ) : null}
      <div className="paper-param-actions">
        <button
          className="paper-primary-button"
          type="button"
          disabled={status === "submitting" || missingPrompts.length === 0}
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
        {planEvidence.length === 0 ? (
          <p className="empty-state-text">暂无可展示的参数对照。</p>
        ) : (
          <ul>
            {planEvidence.map((entry, index) => (
              <li key={`${entry.paper_section_id ?? "evidence"}-${index}`}>
                {formatEvidence(entry, { emptyText: "依据:未标注" })}
              </li>
            ))}
          </ul>
        )}
      </GlassCard>
    </div>
  );
}
