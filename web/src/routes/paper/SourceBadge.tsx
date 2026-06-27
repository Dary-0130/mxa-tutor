export type SourceBadgeKind =
  | "document_extracted"
  | "user_supplied_resolved"
  | "missing_unresolved";

const SOURCE_LABELS: Record<SourceBadgeKind, string> = {
  document_extracted: "论文提取",
  user_supplied_resolved: "用户补充",
  missing_unresolved: "待补充",
};

export function SourceBadge({ kind }: { kind: SourceBadgeKind }) {
  return (
    <span className="paper-source-badge" data-kind={kind}>
      {kind === "missing_unresolved" ? <span aria-hidden="true">!</span> : null}
      {SOURCE_LABELS[kind]}
    </span>
  );
}
