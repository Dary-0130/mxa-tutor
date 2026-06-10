import { GlassCard } from "../../../components/ui/GlassCard";
import type { ProjectOverview } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

interface PanelFlowProps {
  overview: ProjectOverview;
  onFocusPanel: (index: number) => void;
}

export function PanelFlow({ overview, onFocusPanel }: PanelFlowProps) {
  return (
    <PanelFrame index={2} title="执行流程" onFocusPanel={onFocusPanel}>
      <div className="flow-scroll" data-native-scroll>
        <ol className="flow-timeline">
          {overview.main_execution_flow.map((step, index) => (
            <li key={`${index}-${step}`}>
              <GlassCard>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <p>{step}</p>
              </GlassCard>
            </li>
          ))}
        </ol>
      </div>
    </PanelFrame>
  );
}
