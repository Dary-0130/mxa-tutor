import type { ProjectOverview, ProjectType } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

const PROJECT_TYPE_LABELS: Record<ProjectType, string> = {
  control_system: "控制系统",
  signal_processing: "信号处理",
  power_electronics: "电力电子",
  communication: "通信工程",
  motor_control: "电机控制",
  new_energy: "新能源",
  general: "通用工程",
};

interface PanelIntroProps {
  overview: ProjectOverview;
  onFocusPanel: (index: number) => void;
}

export function PanelIntro({ overview, onFocusPanel }: PanelIntroProps) {
  return (
    <PanelFrame index={0} title="工程入口" onFocusPanel={onFocusPanel}>
      <div className="panel-intro">
        <span>{PROJECT_TYPE_LABELS[overview.project_type]}</span>
        <h1>{overview.project_title}</h1>
        <p>{overview.one_sentence_summary}</p>
      </div>
    </PanelFrame>
  );
}
