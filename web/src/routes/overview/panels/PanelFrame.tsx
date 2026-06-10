import type { ReactNode } from "react";

interface PanelFrameProps {
  index: number;
  title: string;
  children: ReactNode;
  onFocusPanel: (index: number) => void;
}

export function PanelFrame({ index, title, children, onFocusPanel }: PanelFrameProps) {
  return (
    <article
      className="overview-panel"
      data-panel-index={index}
      tabIndex={0}
      aria-label={`导览第 ${index + 1} 屏 / 共 6 屏`}
      onFocus={() => onFocusPanel(index)}
    >
      <div className="panel-content">
        <p className="section-kicker">{title}</p>
        {children}
      </div>
      <span className="panel-count">{String(index + 1).padStart(2, "0")} / 06</span>
    </article>
  );
}
