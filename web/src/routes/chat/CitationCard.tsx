import { useState, type KeyboardEvent } from "react";
import type { SourceRef } from "../../lib/types";
import { displayFilePath, formatLineRange } from "./chatHelpers";

interface CitationCardProps {
  citation: SourceRef;
  index: number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const lineRange = formatLineRange(citation.line_range);

  function toggle() {
    setExpanded((value) => !value);
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    toggle();
  }

  return (
    <article
      aria-expanded={expanded}
      className="border border-[var(--color-rebar)] p-3 outline-offset-4 transition-colors hover:border-[var(--color-signal)] focus:border-[var(--color-signal)] focus:outline-2 focus:outline-[var(--color-signal)]"
      role="button"
      tabIndex={0}
      title={displayFilePath(citation)}
      onClick={toggle}
      onKeyDown={onKeyDown}
    >
      <div className="flex items-start gap-3">
        <span className="font-mono text-xs text-[var(--color-signal)]">{String(index + 1).padStart(2, "0")}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-xs text-[var(--color-cold)]">
            {displayFilePath(citation)}
          </p>
          <p className="mt-1 text-xs text-[var(--color-rebar)]">
            {[lineRange, citation.block_name, citation.parameter_name].filter(Boolean).join(" / ") || "结构证据"}
          </p>
        </div>
      </div>
      {expanded ? (
        <dl className="mt-3 grid gap-2 border-t border-[var(--color-rebar)] pt-3 text-xs text-[var(--color-rebar)]">
          <CitationDetail label="block_id" value={citation.block_id} />
          <CitationDetail label="block_name" value={citation.block_name} />
          <CitationDetail label="parent" value={citation.parent_subsystem} />
          <CitationDetail label="parameter" value={citation.parameter_name} />
        </dl>
      ) : null}
    </article>
  );
}

function CitationDetail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2">
      <dt className="font-mono text-[var(--color-signal-dim)]">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere] text-[var(--color-ite)]">{value || "-"}</dd>
    </div>
  );
}
