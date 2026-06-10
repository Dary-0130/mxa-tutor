import { useEffect } from "react";
import type { ProjectOverview } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

interface PanelLearningProps {
  overview: ProjectOverview;
  onFocusPanel: (index: number) => void;
}

function LearningSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <section className="learning-section">
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function PanelLearning({ overview, onFocusPanel }: PanelLearningProps) {
  useEffect(() => {
    if (overview.knowledge_points.length === 0) {
      console.warn("ProjectOverview.knowledge_points is empty");
    }
    if (overview.beginner_reading_order.length === 0) {
      console.warn("ProjectOverview.beginner_reading_order is empty");
    }
    if (overview.likely_confusing_points.length === 0) {
      console.warn("ProjectOverview.likely_confusing_points is empty");
    }
  }, [overview.beginner_reading_order, overview.knowledge_points, overview.likely_confusing_points]);

  return (
    <PanelFrame index={4} title="学习路径" onFocusPanel={onFocusPanel}>
      <div className="learning-stack">
        <LearningSection title="知识点" items={overview.knowledge_points} />
        <LearningSection title="阅读顺序" items={overview.beginner_reading_order} />
        <LearningSection title="容易卡住的地方" items={overview.likely_confusing_points} />
      </div>
    </PanelFrame>
  );
}
