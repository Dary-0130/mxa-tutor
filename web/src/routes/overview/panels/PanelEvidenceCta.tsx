import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyStateText } from "../../../components/ui/EmptyStateText";
import type { ProjectOverview, SourceRefEntry } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

interface PanelEvidenceCtaProps {
  overview: ProjectOverview;
  projectId: string;
  onCta: () => void;
  onFocusPanel: (index: number) => void;
}

function renderEvidence(ref: SourceRefEntry): string {
  const line = ref.line_range ? `:${ref.line_range[0]}-${ref.line_range[1]}` : "";
  const block = ref.block_id ? ` · ${ref.block_id}` : "";
  return `${ref.file_path}${line}${block}`;
}

export function PanelEvidenceCta({
  overview,
  projectId,
  onCta,
  onFocusPanel,
}: PanelEvidenceCtaProps) {
  const [expanded, setExpanded] = useState(overview.evidence.length <= 3);
  const evidence = expanded ? overview.evidence : overview.evidence.slice(0, 3);

  return (
    <PanelFrame index={5} title="证据与出口" onFocusPanel={onFocusPanel}>
      <div className="panel-evidence-cta">
        <div className="evidence-header">
          <h2>证据引用</h2>
          {overview.evidence.length > 3 ? (
            <button type="button" onClick={() => setExpanded((value) => !value)}>
              {expanded ? "收起" : "展开"}
            </button>
          ) : null}
        </div>
        {overview.evidence.length > 0 ? (
          <ol className="evidence-list" data-native-scroll>
            {evidence.map((ref, index) => (
              <li key={`${ref.file_path}-${ref.block_id ?? ""}-${index}`}>{renderEvidence(ref)}</li>
            ))}
          </ol>
        ) : (
          <EmptyStateText>暂无证据引用</EmptyStateText>
        )}
        <Link className="cta-link" to={`/view/${projectId}/chat`} onClick={onCta}>
          开始提问
        </Link>
      </div>
    </PanelFrame>
  );
}
