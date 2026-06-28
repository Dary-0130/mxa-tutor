import { GlassCard } from "../../components/ui/GlassCard";
import type {
  ModelBuildStep,
  ModelGenerationPlan,
  PaperEvidenceEntry,
  StepBlockRef,
} from "../../lib/paperTypes";
import { SourceBadge, type SourceBadgeKind } from "./SourceBadge";

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
  return parts.length > 0 ? `依据:${parts.join(" · ")}` : "";
}

function sourceToBadgeKind(source: PaperEvidenceEntry["source"]): SourceBadgeKind | null {
  if (source === "document_extracted") return "document_extracted";
  if (source === "user_supplied") return "user_supplied_resolved";
  return null;
}

type EvidenceMeta = {
  kind: SourceBadgeKind;
  text: string | null;
};

function getEvidenceMeta(entry: PaperEvidenceEntry | null | undefined): EvidenceMeta | null {
  if (!entry) {
    return null;
  }
  const kind = sourceToBadgeKind(entry.source);
  if (!kind) {
    return null;
  }
  return {
    kind,
    text: entry.source === "document_extracted" ? formatEvidence(entry) || null : null,
  };
}

function renderEvidenceMeta(entry: PaperEvidenceEntry | null | undefined, key?: string) {
  const meta = getEvidenceMeta(entry);
  if (!meta) {
    return null;
  }
  return (
    <span className="paper-build-step-meta" key={key}>
      <SourceBadge kind={meta.kind} />
      {meta.text ? <small>{meta.text}</small> : null}
    </span>
  );
}

function getBlockLookup(steps: ModelBuildStep[]): Map<string, StepBlockRef | null> {
  const lookup = new Map<string, StepBlockRef | null>();
  for (const step of steps) {
    for (const block of step.block_refs) {
      lookup.set(block.block_ref_id, lookup.has(block.block_ref_id) ? null : block);
    }
  }
  return lookup;
}

function getStepLookup(steps: ModelBuildStep[]): Map<string, number | null> {
  const lookup = new Map<string, number | null>();
  steps.forEach((step, index) => {
    lookup.set(step.step_id, lookup.has(step.step_id) ? null : index + 1);
  });
  return lookup;
}

function describeBlockRef(ref: string, blockLookup: Map<string, StepBlockRef | null>): string {
  const block = blockLookup.get(ref);
  return block ? `${ref}（${block.block_type}）` : ref;
}

function describeDependency(stepId: string, stepLookup: Map<string, number | null>): string {
  const stepNo = stepLookup.get(stepId);
  return stepNo ? `依赖步骤 ${stepNo}` : stepId;
}

function renderEvidenceItems(entries: PaperEvidenceEntry[]) {
  return entries
    .map((entry, index) => renderEvidenceMeta(entry, `${entry.paper_section_id ?? "evidence"}-${index}`))
    .filter(Boolean);
}

export function BuildSteps({ plan }: { plan: ModelGenerationPlan }) {
  const structuredSteps = Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;
  const blockLookup = structuredSteps ? getBlockLookup(structuredSteps) : null;
  const stepLookup = structuredSteps ? getStepLookup(structuredSteps) : null;

  if (structuredSteps) {
    return (
      <div className="paper-build-steps">
        <ol className="paper-step-list paper-build-step-list">
          {structuredSteps.map((step, index) => {
            const titleId = `paper-build-step-${index + 1}-title`;
            const stepEvidenceItems = renderEvidenceItems(step.evidence);
            return (
              <li key={step.step_id || index} aria-labelledby={titleId}>
                <GlassCard className="paper-readable-card paper-step-card paper-build-step-card">
                  <span className="paper-step-index paper-token">{String(index + 1).padStart(2, "0")}</span>
                  <div className="paper-build-step-body">
                    <header className="paper-build-step-header">
                      <h3 id={titleId} className="paper-copy">
                        {step.title}
                      </h3>
                      <p className="paper-secondary">{step.intent}</p>
                    </header>

                    {step.block_refs.length > 0 ? (
                      <section className="paper-build-step-group">
                        <h4>涉及块</h4>
                        <ul className="paper-build-step-block-list">
                          {step.block_refs.map((block, blockIndex) => (
                            <li key={`${block.block_ref_id}-${blockIndex}`} className="paper-build-step-block">
                              <div className="paper-build-step-token-row">
                                <span className="paper-token">{block.block_ref_id}</span>
                                <span className="paper-token">{block.block_type}</span>
                              </div>
                              <p className="paper-copy">{block.purpose}</p>
                              <p className="paper-secondary paper-build-step-library">
                                <span>库路径</span>
                                <span className="paper-token">{block.library_path ?? "库路径待确认"}</span>
                              </p>
                              {renderEvidenceMeta(block.paper_reference, `${block.block_ref_id}-evidence`)}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {step.parameter_refs.length > 0 ? (
                      <section className="paper-build-step-group">
                        <h4>关联参数</h4>
                        <ul className="paper-build-step-param-list">
                          {step.parameter_refs.map((param, paramIndex) => (
                            <li key={`${param.paper_param_name}-${param.model_param_name}-${paramIndex}`}>
                              <span className="paper-token">{param.paper_param_name}</span>
                              <span aria-hidden="true">→</span>
                              <span className="paper-token">{param.model_param_name}</span>
                              <span className="paper-secondary">见参数对照表</span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {step.connection_hints.length > 0 && blockLookup ? (
                      <section className="paper-build-step-group">
                        <h4>接线提示</h4>
                        <ul className="paper-build-step-hint-list">
                          {step.connection_hints.map((hint, hintIndex) => (
                            <li
                              key={`${hint.from_block_ref}-${hint.to_block_ref}-${hintIndex}`}
                              className="paper-build-step-hint"
                            >
                              <p className="paper-build-step-wire">
                                <span className="paper-token">{describeBlockRef(hint.from_block_ref, blockLookup)}</span>
                                <span aria-hidden="true">→</span>
                                <span className="paper-token">{describeBlockRef(hint.to_block_ref, blockLookup)}</span>
                              </p>
                              {hint.from_port || hint.to_port ? (
                                <p className="paper-secondary paper-build-step-ports">
                                  {hint.from_port ? (
                                    <span>
                                      输出端口 <span className="paper-token">{hint.from_port}</span>
                                    </span>
                                  ) : null}
                                  {hint.to_port ? (
                                    <span>
                                      输入端口 <span className="paper-token">{hint.to_port}</span>
                                    </span>
                                  ) : null}
                                </p>
                              ) : null}
                              {hint.signal_meaning ? <p className="paper-copy">{hint.signal_meaning}</p> : null}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {step.configuration_hints.length > 0 ? (
                      <section className="paper-build-step-group">
                        <h4>配置提示</h4>
                        <ul className="paper-build-step-hint-list">
                          {step.configuration_hints.map((hint, hintIndex) => {
                            const evidenceItems = renderEvidenceItems(hint.evidence);
                            return (
                              <li key={`${hint.target}-${hint.setting_name ?? "setting"}-${hintIndex}`}>
                                <div className="paper-build-step-token-row">
                                  <span className="paper-token">{hint.target}</span>
                                  {hint.setting_name ? <span className="paper-token">{hint.setting_name}</span> : null}
                                </div>
                                <p className="paper-copy">{hint.instruction}</p>
                                {evidenceItems.length > 0 ? (
                                  <div className="paper-build-step-meta-list">{evidenceItems}</div>
                                ) : null}
                              </li>
                            );
                          })}
                        </ul>
                      </section>
                    ) : null}

                    {step.depends_on.length > 0 && stepLookup ? (
                      <section className="paper-build-step-group">
                        <h4>依赖</h4>
                        <ul className="paper-build-step-dependency-list">
                          {step.depends_on.map((stepId, dependencyIndex) => (
                            <li key={`${stepId}-${dependencyIndex}`} className="paper-token">
                              {describeDependency(stepId, stepLookup)}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {stepEvidenceItems.length > 0 ? (
                      <section className="paper-build-step-group">
                        <h4>步骤证据</h4>
                        <div className="paper-build-step-meta-list">{stepEvidenceItems}</div>
                      </section>
                    ) : null}
                  </div>
                </GlassCard>
              </li>
            );
          })}
        </ol>
      </div>
    );
  }

  return (
    <div className="paper-build-steps">
      <p className="paper-library-choice">
        <span>推荐库:</span>
        <strong className="paper-token">{plan.library_choice}</strong>
      </p>
      {plan.block_recommendations.length === 0 ? (
        <p className="empty-state-text">暂无可展示的建模步骤。</p>
      ) : (
        <ol className="paper-step-list">
          {plan.block_recommendations.map((block, index) => {
            const evidenceText =
              block.paper_reference.source === "document_extracted" ? formatEvidence(block.paper_reference) : "";
            return (
              <li key={`${block.block_type}-${index}`}>
                <GlassCard className="paper-readable-card paper-step-card">
                  <span className="paper-step-index paper-token">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3 className="paper-token">{block.block_type}</h3>
                    <p className="paper-copy">{block.purpose}</p>
                    {evidenceText ? <small>{evidenceText}</small> : null}
                  </div>
                </GlassCard>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
