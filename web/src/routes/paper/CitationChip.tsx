import type { EvidenceSource, PaperAskCitation } from "../../lib/paperTypes";
import { resolveCitationTargetElement, scrollToCitationTarget } from "./anchorRegistry";

type CitationBadgeKind = "document_extracted" | "user_supplied_resolved";

const SOURCE_KIND_TO_BADGE_KIND: Record<EvidenceSource, CitationBadgeKind> = {
  document_extracted: "document_extracted",
  user_supplied: "user_supplied_resolved",
};

interface CitationChipProps {
  citation: PaperAskCitation;
}

function CitationChipContent({ citation }: CitationChipProps) {
  return (
    <>
      <span className="paper-citation-chip__label">{citation.label}</span>
      {citation.excerpt ? <span className="paper-citation-chip__excerpt">{citation.excerpt}</span> : null}
    </>
  );
}

export function CitationChip({ citation }: CitationChipProps) {
  const badgeKind = SOURCE_KIND_TO_BADGE_KIND[citation.source_kind];
  const isResolved = resolveCitationTargetElement(citation.target) !== null;

  if (!isResolved) {
    return (
      <span
        aria-disabled="true"
        className="paper-source-badge paper-citation-chip"
        data-clickable="false"
        data-kind={badgeKind}
      >
        <CitationChipContent citation={citation} />
      </span>
    );
  }

  return (
    <button
      className="paper-source-badge paper-citation-chip"
      data-clickable="true"
      data-kind={badgeKind}
      type="button"
      onClick={() => scrollToCitationTarget(citation.target)}
    >
      <CitationChipContent citation={citation} />
    </button>
  );
}
