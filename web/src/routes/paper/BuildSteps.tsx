import { useEffect, useId, useRef, useState } from "react";
import { GlassCard } from "../../components/ui/GlassCard";
import { formatEvidence } from "../../lib/paperEvidence";
import type {
  ModelBuildStep,
  ModelGenerationPlan,
  PaperEvidenceEntry,
  ConfigurationHint,
  StepBlockRef,
} from "../../lib/paperTypes";
import {
  buildGuidanceDisplayModel,
  type DisplayGuidanceBucket,
  type DisplayGuidanceGroup,
  type DisplayGuidanceItem,
  type DisplayGuidanceModel,
  type GuidanceEvidenceDisplay,
  type GuidanceSourceDisplay,
} from "./buildGuidanceDisplay";
import { SourceBadge, type SourceBadgeKind } from "./SourceBadge";

const EMPTY_ARRAY: never[] = [];

function arrayOrEmpty<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : EMPTY_ARRAY;
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
      <small className="paper-build-step-origin-label">步骤原始依据</small>
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
    .map((entry, index) =>
      renderEvidenceMeta(entry, `${entry.paper_section_id ?? "evidence"}-${index}`),
    )
    .filter(Boolean);
}

function GuidanceSourcePill({ source }: { source: GuidanceSourceDisplay }) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const tooltipId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    function closeOnOutsidePointer(event: PointerEvent) {
      const target = event.target;
      if (target instanceof Node && buttonRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    }
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
    };
  }, [open]);

  return (
    <span className="paper-guidance-source-wrap">
      <button
        ref={buttonRef}
        type="button"
        className="paper-guidance-source-pill"
        data-tone={source.tone}
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        aria-label={`${source.label}: ${source.description}`}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((value) => !value)}
        onFocus={() => setOpen(true)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {source.label}
      </button>
      {open ? (
        <span id={tooltipId} role="tooltip" className="paper-guidance-source-tip">
          {source.description}
        </span>
      ) : null}
    </span>
  );
}

function GuidanceEvidence({ evidence }: { evidence: GuidanceEvidenceDisplay }) {
  return (
    <details className="paper-guidance-evidence" open>
      <summary>
        <span>{evidence.title}</span>
        <span>{evidence.chips.length > 1 ? `${evidence.summary} · 展开全部` : evidence.summary}</span>
      </summary>
      <ul>
        {evidence.chips.map((chip) => (
          <li key={chip.key}>
            <strong>{chip.title}</strong>
            {chip.excerpt ? <p>{chip.excerpt}</p> : <p>已关联到论文摘录</p>}
            <small>{chip.locatorText}</small>
          </li>
        ))}
      </ul>
    </details>
  );
}

function GuidanceItem({ item }: { item: DisplayGuidanceItem }) {
  return (
    <li className="paper-guidance-item" data-tone={item.source?.tone ?? "gap"}>
      <div className="paper-guidance-item-head">
        <span className="paper-guidance-kind">
          <span aria-hidden="true">{item.kind.mark}</span>
          {item.kind.label}
        </span>
        {item.source ? <GuidanceSourcePill source={item.source} /> : null}
        {item.severityLabel ? (
          <span
            className="paper-guidance-severity"
            title={item.severityHint ?? undefined}
            data-level={item.severityLabel === "关键待确认" ? "critical" : "review"}
          >
            {item.severityLabel}
          </span>
        ) : null}
      </div>
      <p className="paper-copy">{item.text}</p>
      {item.reasonText ? <p className="paper-guidance-reason">{item.reasonText}</p> : null}
      {item.targetLine ? <p className="paper-secondary">{item.targetLine}</p> : null}
      {item.evidence ? <GuidanceEvidence evidence={item.evidence} /> : null}
    </li>
  );
}

function GuidanceGroup({ group }: { group: DisplayGuidanceGroup }) {
  return (
    <section className="paper-guidance-group" aria-label={group.label}>
      <header>
        <h5>{group.label}</h5>
        <span>
          说明 {group.detailCount} · 缺口 {group.gapCount}
        </span>
      </header>
      <ul>
        {group.items.map((item) => (
          <GuidanceItem key={item.key} item={item} />
        ))}
      </ul>
    </section>
  );
}

function GuidanceBucket({
  bucket,
  showWhenEmpty = false,
}: {
  bucket: DisplayGuidanceBucket;
  showWhenEmpty?: boolean;
}) {
  if (bucket.totalCount === 0 && !showWhenEmpty) {
    return null;
  }
  return (
    <section id={bucket.anchorId} className="paper-build-guidance" aria-label={bucket.title}>
      <header className="paper-build-guidance-head">
        <h4>{bucket.title}</h4>
        <span>
          建模建议 {bucket.detailCount} 条 · 待核对缺口 {bucket.gapCount} 条
        </span>
      </header>
      {bucket.gapCount > 0 ? (
        <p className="paper-guidance-gap-title">待核对的缺口 · 需你逐条确认</p>
      ) : null}
      {bucket.totalCount > 0 ? (
        <div className="paper-guidance-groups">
          {bucket.groups.map((group) => (
            <GuidanceGroup key={group.key} group={group} />
          ))}
        </div>
      ) : (
        <p className="paper-secondary">暂无未归入具体步骤的建议。</p>
      )}
    </section>
  );
}

function GuidanceHead({ model }: { model: DisplayGuidanceModel }) {
  const hasRows = model.counts.visibleTotal > 0;
  if (!hasRows && !model.statusText && !model.dataNotice) {
    return null;
  }
  const stepGuidanceBuckets = Array.from(model.stepBuckets, (entry) => entry[1]);
  const links = [
    ...stepGuidanceBuckets
      .filter((bucket) => bucket.totalCount > 0)
      .map((bucket) => ({
        href: `#${bucket.anchorId}`,
        label: bucket.title,
        total: bucket.totalCount,
      })),
    ...(model.looseBucket.totalCount > 0
      ? [
          {
            href: `#${model.looseBucket.anchorId}`,
            label: "全局待确认",
            total: model.looseBucket.totalCount,
          },
        ]
      : []),
  ];

  return (
    <section className="paper-guidance-summary" aria-label="逐条建模建议汇总">
      <div className="paper-guidance-summary-line">
        <strong>逐条建模建议</strong>
        <span>
          建模建议 {model.counts.details} 条 · 待核对缺口 {model.counts.gaps} 条
        </span>
      </div>
      {links.length > 0 ? (
        <nav aria-label="逐条建模建议跳转">
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label} · {link.total}
            </a>
          ))}
        </nav>
      ) : null}
      {model.dataNotice && hasRows ? (
        <p className="paper-guidance-format-note">{model.dataNotice}</p>
      ) : null}
      {model.statusText ? <p className="paper-secondary">{model.statusText}</p> : null}
      {hasRows ? (
        <p className="paper-secondary paper-guidance-scope-note">
          以下建议分别以各自来源章为准
        </p>
      ) : null}
    </section>
  );
}

function normalizeConfigurationHint(hint: ConfigurationHint): ConfigurationHint {
  return {
    ...hint,
    evidence: arrayOrEmpty(hint.evidence),
  };
}

function normalizeBuildStep(step: ModelBuildStep): ModelBuildStep {
  return {
    ...step,
    block_refs: arrayOrEmpty(step.block_refs),
    parameter_refs: arrayOrEmpty(step.parameter_refs),
    connection_hints: arrayOrEmpty(step.connection_hints),
    configuration_hints: arrayOrEmpty(step.configuration_hints).map(normalizeConfigurationHint),
    depends_on: arrayOrEmpty(step.depends_on),
    evidence: arrayOrEmpty(step.evidence),
  };
}

interface BuildStepsProps {
  plan: ModelGenerationPlan;
  regenerating?: boolean;
  regenerateMessage?: string | null;
  regenerateErrorMessage?: string | null;
  onRegenerate?: () => void;
  onDismissRegenerateMessage?: () => void;
}

export function BuildSteps({
  plan,
  regenerating = false,
  regenerateMessage = null,
  regenerateErrorMessage = null,
  onRegenerate,
  onDismissRegenerateMessage,
}: BuildStepsProps) {
  const structuredSteps = Array.isArray(plan.build_steps) && plan.build_steps.length > 0 ? plan.build_steps : null;
  const normalizedSteps = structuredSteps ? structuredSteps.map(normalizeBuildStep) : null;
  const guidanceModel = buildGuidanceDisplayModel(plan, normalizedSteps ?? []);
  const blockLookup = normalizedSteps ? getBlockLookup(normalizedSteps) : null;
  const stepLookup = normalizedSteps ? getStepLookup(normalizedSteps) : null;
  const regenerateButton = onRegenerate ? (
    <button
      className="paper-primary-button paper-regenerate-steps-button"
      type="button"
      disabled={regenerating}
      onClick={onRegenerate}
    >
      {regenerating ? <span className="paper-button-spinner" aria-hidden="true" /> : null}
      <span>{regenerating ? "生成中…" : "重新生成步骤"}</span>
    </button>
  ) : null;
  const regenerateNotice =
    regenerateMessage || regenerateErrorMessage ? (
      <aside className="paper-regenerate-steps-notice" aria-live="polite">
        <span>{regenerateErrorMessage ?? regenerateMessage}</span>
        {onDismissRegenerateMessage ? (
          <button type="button" onClick={onDismissRegenerateMessage}>
            关闭
          </button>
        ) : null}
      </aside>
    ) : null;

  if (normalizedSteps) {
    return (
      <div className="paper-build-steps">
        {regenerateButton ? (
          <div className="paper-build-step-return-head">
            <p className="paper-secondary">当前步骤可按最新参数重新生成。</p>
            {regenerateButton}
          </div>
        ) : null}
        {regenerateNotice}
        <GuidanceHead model={guidanceModel} />
        <ol className="paper-step-list paper-build-step-list">
          {normalizedSteps.map((step, index) => {
            const titleId = `paper-build-step-${index + 1}-title`;
            const stepEvidenceItems = renderEvidenceItems(step.evidence);
            const guidanceBucket = guidanceModel.stepBuckets.get(step.step_id);
            return (
              <li key={step.step_id || index} aria-labelledby={titleId}>
                <GlassCard className="paper-readable-card paper-step-card paper-build-step-card">
                  <span className="paper-step-index paper-token">
                    {String(index + 1).padStart(2, "0")}
                  </span>
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
                            <li
                              key={`${block.block_ref_id}-${blockIndex}`}
                              className="paper-build-step-block"
                            >
                              <div className="paper-build-step-token-row">
                                <span className="paper-token">{block.block_ref_id}</span>
                                <span className="paper-token">{block.block_type}</span>
                              </div>
                              <p className="paper-copy">{block.purpose}</p>
                              <p className="paper-secondary paper-build-step-library">
                                <span>库路径</span>
                                <span className="paper-token">
                                  {block.library_path ?? "库路径待确认"}
                                </span>
                              </p>
                              {renderEvidenceMeta(
                                block.paper_reference,
                                `${block.block_ref_id}-evidence`,
                              )}
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
                            <li
                              key={`${param.paper_param_name}-${param.model_param_name}-${paramIndex}`}
                            >
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
                                <span className="paper-token">
                                  {describeBlockRef(hint.from_block_ref, blockLookup)}
                                </span>
                                <span aria-hidden="true">→</span>
                                <span className="paper-token">
                                  {describeBlockRef(hint.to_block_ref, blockLookup)}
                                </span>
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
                              {hint.signal_meaning ? (
                                <p className="paper-copy">{hint.signal_meaning}</p>
                              ) : null}
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
                              <li
                                key={`${hint.target}-${hint.setting_name ?? "setting"}-${hintIndex}`}
                              >
                                <div className="paper-build-step-token-row">
                                  <span className="paper-token">{hint.target}</span>
                                  {hint.setting_name ? (
                                    <span className="paper-token">{hint.setting_name}</span>
                                  ) : null}
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
                    {guidanceBucket ? <GuidanceBucket bucket={guidanceBucket} /> : null}
                  </div>
                </GlassCard>
              </li>
            );
          })}
        </ol>
        {guidanceModel.counts.visibleTotal > 0 ? (
          <GuidanceBucket bucket={guidanceModel.looseBucket} showWhenEmpty />
        ) : null}
      </div>
    );
  }

  return (
    <div className="paper-build-steps">
      <div className="paper-build-step-return-head">
        <p className="paper-secondary">当前显示推荐块视图;完整步骤可重新生成。</p>
        {regenerateButton}
      </div>
      {regenerateNotice}
      <GuidanceHead model={guidanceModel} />
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
              block.paper_reference.source === "document_extracted"
                ? formatEvidence(block.paper_reference)
                : "";
            return (
              <li key={`${block.block_type}-${index}`}>
                <GlassCard className="paper-readable-card paper-step-card">
                  <span className="paper-step-index paper-token">
                    {String(index + 1).padStart(2, "0")}
                  </span>
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
      {guidanceModel.counts.visibleTotal > 0 ? (
        <GuidanceBucket bucket={guidanceModel.looseBucket} showWhenEmpty />
      ) : null}
    </div>
  );
}
