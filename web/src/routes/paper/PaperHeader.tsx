import { Link } from "react-router-dom";
import type { PaperDomain, PaperSpec, PaperType } from "../../lib/paperTypes";

const DOMAIN_LABELS: Record<PaperDomain, string> = {
  control_system: "控制系统",
  signal_processing: "信号处理",
  power_electronics: "电力电子",
  communication: "通信",
  motor_control: "电机控制",
  new_energy: "新能源",
};

const PAPER_TYPE_LABELS: Record<PaperType, string> = {
  paper: "论文",
  report: "报告",
  thesis: "学位论文",
};

export function PaperHeader({ spec }: { spec: PaperSpec }) {
  return (
    <header className="paper-header">
      <div>
        <p className="section-kicker">PAPER WORKBENCH</p>
        <h1>{spec.paper_title}</h1>
        <p className="paper-copy">{spec.abstract}</p>
        <div className="paper-header__tags" aria-label="论文元信息">
          <span>{DOMAIN_LABELS[spec.domain]}</span>
          <span>{PAPER_TYPE_LABELS[spec.paper_type]}</span>
        </div>
      </div>
      <Link className="paper-primary-link" to="/paper">
        重新上传
      </Link>
    </header>
  );
}
