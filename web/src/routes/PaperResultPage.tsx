import { Link, useParams } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";
import { ApiException } from "../lib/api";
import { resolveErrorMessage } from "../lib/errorMessages";
import { BuildSteps } from "./paper/BuildSteps";
import { EquationList } from "./paper/EquationList";
import { PaperAskPanel } from "./paper/PaperAskPanel";
import { PaperHeader } from "./paper/PaperHeader";
import { ParameterConflicts } from "./paper/ParameterConflicts";
import { ParameterTable } from "./paper/ParameterTable";
import { SectionNav } from "./paper/SectionNav";
import { SubsystemMap } from "./paper/SubsystemMap";
import { TuningPanel } from "./paper/TuningPanel";
import { usePaperResult } from "./paper/usePaperResult";

function PaperLoading() {
  return (
    <main className="paper-state-page">
      <PanoramaScene panoramaX={0} />
      <p>正在解析论文并生成建模路线…</p>
    </main>
  );
}

function PaperError({ error, retry }: { error: ApiException; retry: () => void }) {
  const notFound = error.code === "paper_not_found" || error.status === 404;
  const message = notFound ? "论文结果不存在或已过期,请重新上传。" : resolveErrorMessage(error.code);

  return (
    <main className="paper-state-page">
      <PanoramaScene panoramaX={0} />
      <section className="paper-error-panel">
        <h1>{message}</h1>
        <div>
          {!notFound ? (
            <button type="button" onClick={retry}>
              重试
            </button>
          ) : null}
          <Link to="/paper">重新上传</Link>
        </div>
      </section>
    </main>
  );
}

export function PaperResultPage() {
  const { paperId } = useParams();
  const { data, loading, error, retry, updatePlan } = usePaperResult(paperId);

  if (loading && !data) {
    return <PaperLoading />;
  }
  if (error || !data) {
    return (
      <PaperError
        error={error ?? new ApiException(404, "paper_not_found", "论文结果不存在或已过期,请重新上传。")}
        retry={retry}
      />
    );
  }
  const renderableEquations = data.spec.equations.filter((equation) => equation.latex_or_text.trim() !== "");
  const includeEquations = renderableEquations.length > 0;

  return (
    <main className="paper-page">
      <PanoramaScene panoramaX={0} />
      <p className="sr-only">
        论文复现阅读工作台包含论文摘要、子系统划分、建模步骤、参数对照和调参建议。
      </p>
      <SectionNav includeEquations={includeEquations} />
      <div className="paper-shell">
        <PaperHeader spec={data.spec} />
        <div className="paper-body-grid">
          <div className="paper-content-column">
            <section id="paper-summary" className="paper-section" aria-labelledby="paper-summary-title">
              <h2 id="paper-summary-title">论文摘要</h2>
              <div className="paper-readable-card paper-summary-card">
                <p className="paper-copy">{data.spec.abstract}</p>
              </div>
            </section>
            {includeEquations ? (
              <section id="paper-equations" className="paper-section" aria-labelledby="paper-equations-title">
                <h2 id="paper-equations-title">公式</h2>
                <EquationList items={renderableEquations} />
              </section>
            ) : null}
            <section id="paper-subsystems" className="paper-section" aria-labelledby="paper-subsystems-title">
              <h2 id="paper-subsystems-title">子系统划分</h2>
              <SubsystemMap items={data.plan.subsystem_breakdown} />
            </section>
            <section id="paper-build-steps" className="paper-section" aria-labelledby="paper-build-steps-title">
              <h2 id="paper-build-steps-title">建模步骤</h2>
              <BuildSteps plan={data.plan} />
            </section>
            <section id="paper-parameters" className="paper-section" aria-labelledby="paper-parameters-title">
              <h2 id="paper-parameters-title">参数对照</h2>
              <ParameterConflicts
                conflicts={data.spec.parameter_conflicts}
                documents={data.spec.documents}
              />
              <ParameterTable
                paperId={data.paperId}
                plan={data.plan}
                remainingMissingPrompts={data.remainingMissingPrompts}
                onPlanUpdate={updatePlan}
              />
            </section>
            <section id="paper-tuning" className="paper-section" aria-labelledby="paper-tuning-title">
              <h2 id="paper-tuning-title">调参建议</h2>
              <TuningPanel paperId={data.paperId} />
            </section>
          </div>
          <PaperAskPanel key={data.paperId} paperId={data.paperId} documents={data.spec.documents} />
        </div>
      </div>
    </main>
  );
}
