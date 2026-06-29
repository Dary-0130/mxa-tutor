import type { PaperEvidenceEntry } from "./paperTypes";

type FormatEvidenceOptions = {
  emptyText?: string;
};

export function formatEvidence(
  entry: PaperEvidenceEntry,
  { emptyText = "" }: FormatEvidenceOptions = {},
): string {
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
  return parts.length > 0 ? `依据:${parts.join(" · ")}` : emptyText;
}
