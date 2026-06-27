import { GlassCard } from "../../components/ui/GlassCard";

export function SubsystemMap({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="empty-state-text">暂无可展示的子系统划分。</p>;
  }

  return (
    <ol className="paper-subsystem-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>
          <GlassCard className="paper-readable-card paper-subsystem-card">
            <span className="paper-token">{String(index + 1).padStart(2, "0")}</span>
            <p className="paper-copy">{item}</p>
          </GlassCard>
        </li>
      ))}
    </ol>
  );
}
