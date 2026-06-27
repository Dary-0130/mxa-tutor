import { useState } from "react";
import { GlassCard } from "../../components/ui/GlassCard";
import { postTuningSuggest } from "../../lib/paperApi";
import type { Confidence, TuningDirection, TuningSuggestion } from "../../lib/paperTypes";

const DIRECTION_LABELS: Record<TuningDirection, string> = {
  increase: "增大",
  decrease: "减小",
  tune_within_range: "区间内调整",
};

const CONFIDENCE_LABELS: Record<Confidence, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function TuningPanel({ paperId }: { paperId: string }) {
  const [scenario, setScenario] = useState("");
  const [suggestion, setSuggestion] = useState<TuningSuggestion | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("输入调参场景后生成建议。");

  const requestSuggestion = async () => {
    const trimmed = scenario.trim();
    if (!trimmed) {
      setMessage("请先描述调参场景。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const response = await postTuningSuggest(paperId, { user_scenario: trimmed });
      setSuggestion(response.suggestion);
    } catch {
      setMessage("调参建议生成失败,请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="paper-tuning-panel">
      <div className="paper-tuning-form">
        <textarea
          value={scenario}
          maxLength={500}
          placeholder="描述当前调参场景"
          onChange={(event) => setScenario(event.target.value)}
        />
        <button className="paper-primary-button" type="button" disabled={loading} onClick={requestSuggestion}>
          生成调参建议
        </button>
      </div>
      <p className="paper-secondary">仅给出调整方向,不提供具体数值。</p>
      {message ? <p className="empty-state-text">{message}</p> : null}
      {suggestion ? (
        <GlassCard className="paper-readable-card paper-tuning-result">
          <div className="paper-direction-list">
            {suggestion.parameter_directions.map((item) => (
              <article key={`${item.param_name}-${item.direction}`} className="paper-direction-item">
                <strong className="paper-token">{item.param_name}</strong>
                <span>{DIRECTION_LABELS[item.direction]}</span>
                <p className="paper-copy">{item.physical_meaning}</p>
              </article>
            ))}
          </div>
          <dl className="paper-tuning-meta">
            <div>
              <dt>预期影响</dt>
              <dd className="paper-copy">{suggestion.expected_effect}</dd>
            </div>
            <div>
              <dt>置信度:</dt>
              <dd>{CONFIDENCE_LABELS[suggestion.confidence]}</dd>
            </div>
          </dl>
          <p className="paper-secondary">{suggestion.disclaimer}</p>
        </GlassCard>
      ) : null}
    </div>
  );
}
