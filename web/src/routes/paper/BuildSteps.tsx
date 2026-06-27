import { GlassCard } from "../../components/ui/GlassCard";
import type { ModelGenerationPlan, PaperEvidenceEntry } from "../../lib/paperTypes";

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

export function BuildSteps({ plan }: { plan: ModelGenerationPlan }) {
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
          {plan.block_recommendations.map((block, index) => (
            <li key={`${block.block_type}-${index}`}>
              <GlassCard className="paper-readable-card paper-step-card">
                <span className="paper-step-index paper-token">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="paper-token">{block.block_type}</h3>
                  <p className="paper-copy">{block.purpose}</p>
                  <small>{formatEvidence(block.paper_reference)}</small>
                </div>
              </GlassCard>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
