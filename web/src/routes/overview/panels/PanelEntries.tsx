import { EmptyStateText } from "../../../components/ui/EmptyStateText";
import { FileRow } from "../../../components/ui/FileRow";
import type { ProjectOverview } from "../../../lib/types";
import { PanelFrame } from "./PanelFrame";

interface PanelEntriesProps {
  overview: ProjectOverview;
  onFocusPanel: (index: number) => void;
}

export function PanelEntries({ overview, onFocusPanel }: PanelEntriesProps) {
  const hasModels = overview.main_simulink_models.length > 0;
  return (
    <PanelFrame index={1} title="入口与模型" onFocusPanel={onFocusPanel}>
      <div className="panel-columns" data-single={!hasModels ? "true" : undefined}>
        <section>
          <h2>入口文件</h2>
          <div className="list-stack">
            {overview.main_entry_files.map((entry) => (
              <FileRow key={entry.file_path} path={entry.file_path} note={entry.role} />
            ))}
          </div>
        </section>
        <section>
          <h2>Simulink 模型</h2>
          {hasModels ? (
            <div className="list-stack">
              {overview.main_simulink_models.map((model) => (
                <FileRow key={model.file_path} path={model.file_path} note={model.summary} />
              ))}
            </div>
          ) : (
            <EmptyStateText>本工程无 Simulink 模型</EmptyStateText>
          )}
        </section>
      </div>
    </PanelFrame>
  );
}
