import { GlassCard } from "../../components/ui/GlassCard";
import type { PaperDocument, ParameterConflict } from "../../lib/paperTypes";

interface ParameterConflictsProps {
  conflicts: ParameterConflict[];
  documents: PaperDocument[];
}

function documentLabel(documentId: string, documents: PaperDocument[]): string {
  const document = documents.find((candidate) => candidate.document_id === documentId);
  return document ? `${document.document_id} · ${document.filename}` : documentId;
}

function parameterLabel(conflict: ParameterConflict): string {
  if (conflict.parameter_symbol) {
    return `${conflict.parameter_name} (${conflict.parameter_symbol})`;
  }
  return conflict.parameter_name;
}

export function ParameterConflicts({ conflicts, documents }: ParameterConflictsProps) {
  if (conflicts.length === 0) {
    return null;
  }

  return (
    <GlassCard className="paper-readable-card paper-conflict-panel">
      <div className="paper-conflict-heading">
        <span>参数冲突</span>
        <p>这些文档给出的参数值不一致，需要你确认后再用于建模。</p>
      </div>
      <div className="paper-conflict-list">
        {conflicts.map((conflict) => (
          <section
            className="paper-conflict-item"
            key={`${conflict.parameter_name}-${conflict.parameter_symbol}`}
            aria-label={parameterLabel(conflict)}
          >
            <h3>{parameterLabel(conflict)}</h3>
            <div className="paper-conflict-options">
              {conflict.value_options.map((option, index) => (
                <div className="paper-conflict-option" key={`${option.value}-${option.unit}-${index}`}>
                  <strong className="paper-token">
                    {option.value}
                    <small>{option.unit}</small>
                  </strong>
                  <ul>
                    {option.observations.map((observation) => (
                      <li key={`${option.value}-${observation.document_id}`}>
                        {documentLabel(observation.document_id, documents)}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </GlassCard>
  );
}
