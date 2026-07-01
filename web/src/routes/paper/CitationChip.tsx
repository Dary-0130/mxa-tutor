import type { EvidenceSource, PaperAskCitation } from "../../lib/paperTypes";
import { resolveCitationTargetElement, scrollToCitationTarget } from "./anchorRegistry";

type CitationBadgeKind = "document_extracted" | "user_supplied_resolved";

const SOURCE_KIND_TO_BADGE_KIND: Record<EvidenceSource, CitationBadgeKind> = {
  document_extracted: "document_extracted",
  user_supplied: "user_supplied_resolved",
};

interface CitationChipProps {
  citation: PaperAskCitation;
  showDocumentLabel: boolean;
  duplicateDocumentLabels: ReadonlySet<string>;
}

interface CitationChipContentProps {
  citation: PaperAskCitation;
  documentDisplayLabel: string | null;
}

function documentDisplayLabelFor({
  citation,
  duplicateDocumentLabels,
  showDocumentLabel,
}: CitationChipProps): string | null {
  if (!showDocumentLabel || citation.source_kind !== "document_extracted") {
    return null;
  }
  const label = citation.document_label?.trim();
  const documentId = citation.document_id?.trim();
  if (!label || !documentId) {
    return null;
  }
  if (duplicateDocumentLabels.has(label)) {
    return `${label} · ${documentId}`;
  }
  return label;
}

function CitationChipContent({ citation, documentDisplayLabel }: CitationChipContentProps) {
  return (
    <>
      <span className="paper-citation-chip__label">{citation.label}</span>
      {documentDisplayLabel ? (
        <span className="paper-citation-chip__document">{documentDisplayLabel}</span>
      ) : null}
      {citation.excerpt ? <span className="paper-citation-chip__excerpt">{citation.excerpt}</span> : null}
    </>
  );
}

export function CitationChip(props: CitationChipProps) {
  const { citation } = props;
  const badgeKind = SOURCE_KIND_TO_BADGE_KIND[citation.source_kind];
  const isResolved = resolveCitationTargetElement(citation.target) !== null;
  const documentDisplayLabel = documentDisplayLabelFor(props);

  if (!isResolved) {
    return (
      <span
        aria-disabled="true"
        className="paper-source-badge paper-citation-chip"
        data-clickable="false"
        data-kind={badgeKind}
      >
        <CitationChipContent citation={citation} documentDisplayLabel={documentDisplayLabel} />
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
      <CitationChipContent citation={citation} documentDisplayLabel={documentDisplayLabel} />
    </button>
  );
}
