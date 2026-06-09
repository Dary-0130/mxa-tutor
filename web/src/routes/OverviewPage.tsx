import { useParams } from "react-router-dom";

export function OverviewPage() {
  const { projectId } = useParams();
  return (
    <section className="brutal-panel max-w-3xl p-8">
      <p className="font-mono text-sm font-bold uppercase text-[var(--color-signal)]">TASK-402</p>
      <h1 className="mt-4 text-4xl font-black leading-tight md:text-5xl">工程导览占位</h1>
      <p className="mt-6 max-w-2xl text-sm leading-7 text-[var(--color-rebar)]">
        项目 {projectId ?? "unknown"} 的结构化导览将在这里渲染。
      </p>
      <div className="mt-8 h-2 w-28 bg-[var(--color-signal)]" />
    </section>
  );
}
