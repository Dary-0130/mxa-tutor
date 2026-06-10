import { EmptyStateText } from "../../../components/ui/EmptyStateText";
import { FileRow } from "../../../components/ui/FileRow";
import { GlassCard } from "../../../components/ui/GlassCard";
import type { ProjectOverview } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

interface PanelKeyItemsProps {
  overview: ProjectOverview;
  onFocusPanel: (index: number) => void;
}

export function PanelKeyItems({ overview, onFocusPanel }: PanelKeyItemsProps) {
  const hasBlocks = overview.key_blocks.length > 0;
  return (
    <PanelFrame index={3} title="关键文件与模块" onFocusPanel={onFocusPanel}>
      <div className="panel-columns" data-single={!hasBlocks ? "true" : undefined}>
        <section className="native-list" data-native-scroll>
          <h2>关键文件</h2>
          <div className="list-stack">
            {overview.key_files.map((file) => (
              <FileRow key={file.file_path} path={file.file_path} note={file.why_key} />
            ))}
          </div>
        </section>
        <section className="native-list" data-native-scroll>
          <h2>关键模块</h2>
          {hasBlocks ? (
            <div className="list-stack">
              {overview.key_blocks.map((block) => (
                <GlassCard key={`${block.location}-${block.block_name}`}>
                  <div className="block-entry">
                    <strong>{block.block_name}</strong>
                    <span>{block.block_type}</span>
                    <small>{block.location}</small>
                    <p>{block.why_key}</p>
                  </div>
                </GlassCard>
              ))}
            </div>
          ) : (
            <EmptyStateText>本工程暂无可单独展开的关键模块</EmptyStateText>
          )}
        </section>
      </div>
    </PanelFrame>
  );
}
