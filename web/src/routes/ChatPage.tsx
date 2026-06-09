import { useParams } from "react-router-dom";

export function ChatPage() {
  const { projectId } = useParams();
  return (
    <section className="brutal-panel max-w-3xl p-8">
      <p className="font-mono text-sm font-bold uppercase text-[var(--color-signal)]">TASK-403</p>
      <h1 className="mt-4 text-4xl font-black leading-tight md:text-5xl">工程问答占位</h1>
      <p className="mt-6 max-w-2xl text-sm leading-7 text-[var(--color-rebar)]">
        项目 {projectId ?? "unknown"} 的带证据问答界面将在这里实现。
      </p>
      <div className="mt-8 h-2 w-28 bg-[var(--color-signal)]" />
    </section>
  );
}
