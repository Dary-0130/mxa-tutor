import { useMemo, useRef, useState } from "react";
import { GlassCard } from "../../components/ui/GlassCard";
import { ApiException } from "../../lib/api";
import { postPaperAsk } from "../../lib/paperApi";
import type {
  Confidence,
  PaperAskFallbackReason,
  PaperAskResponse,
  PaperDocument,
} from "../../lib/paperTypes";
import { CitationChip } from "./CitationChip";

const MAX_QUESTION_LENGTH = 1000;

const CONFIDENCE_LABELS: Record<Confidence, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

const FALLBACK_REASON_COPY: Record<PaperAskFallbackReason, string> = {
  insufficient_evidence: "当前资料里没有足够可核验的依据支撑这个回答,所以没有生成带出处的结论。",
  invalid_or_missing_citations: "这次回答生成的出处没有通过校验,因此没有作为正式回答展示。",
  citation_target_unresolved:
    "这次回答引用的依据没有稳定对应到当前结果页中的公式、参数或区块,因此没有作为正式回答展示。",
  out_of_scope: "这个问题超出了当前论文复现结果能可靠回答的范围。",
};

const FALLBACK_HINT = "可以试着围绕论文的公式、参数、建模步骤或调参建议来提问。";

interface PaperAskPanelProps {
  paperId: string;
  documents: PaperDocument[];
}

function validationMessageFor(question: string): string {
  const trimmed = question.trim();
  if (trimmed.length === 0) {
    return "请先输入问题。";
  }
  if (trimmed.length > MAX_QUESTION_LENGTH) {
    return "问题最多 1000 字。";
  }
  return "";
}

function toApiException(error: unknown): ApiException {
  if (error instanceof ApiException) {
    return error;
  }
  return new ApiException(0, "network_error", "请求失败,请稍后重试。");
}

function responseKey(response: PaperAskResponse): string {
  return `${response.session_id}-${response.message_id}`;
}

function duplicateDocumentLabelsFor(documents: PaperDocument[]): ReadonlySet<string> {
  const counts = new Map<string, number>();
  documents.forEach((document) => {
    counts.set(document.filename, (counts.get(document.filename) ?? 0) + 1);
  });
  return new Set(
    [...counts.entries()]
      .filter(([, count]) => count > 1)
      .map(([filename]) => filename),
  );
}

export function PaperAskPanel({ paperId, documents }: PaperAskPanelProps) {
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [answer, setAnswer] = useState<PaperAskResponse | null>(null);
  const [error, setError] = useState<ApiException | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastSubmittedQuestion, setLastSubmittedQuestion] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const validationMessage = useMemo(() => validationMessageFor(question), [question]);
  const duplicateDocumentLabels = useMemo(() => duplicateDocumentLabelsFor(documents), [documents]);
  const showDocumentLabel = documents.length > 1;
  const canSubmit = !loading && validationMessage === "";

  function updateQuestion(value: string) {
    setQuestion(value);
    setError(null);
  }

  async function submitQuestion(questionToSubmit: string) {
    const trimmed = questionToSubmit.trim();
    const validation = validationMessageFor(trimmed);
    if (validation) {
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setAnswer(null);
    setError(null);
    setLastSubmittedQuestion(trimmed);

    try {
      const response = await postPaperAsk(paperId, { question: trimmed, session_id: sessionId });
      if (requestIdRef.current !== requestId) {
        return;
      }
      setAnswer(response);
      setSessionId(response.session_id);
    } catch (caught) {
      if (requestIdRef.current !== requestId) {
        return;
      }
      setError(toApiException(caught));
    } finally {
      if (requestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }

  return (
    <aside className="paper-ask-panel-wrap" aria-label="论文追问">
      <GlassCard className="paper-readable-card paper-ask-panel">
        <div className="paper-ask-heading">
          <h2>论文追问</h2>
          <span>即时</span>
        </div>
        <div className="paper-ask-form">
          <textarea
            aria-describedby="paper-ask-validation"
            aria-label="追问内容"
            value={question}
            placeholder="输入关于公式、参数或建模步骤的问题"
            onChange={(event) => updateQuestion(event.target.value)}
          />
          <button
            className="paper-primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => submitQuestion(question)}
          >
            提问
          </button>
        </div>
        <div className="paper-ask-meta">
          <span>{question.trim().length}/{MAX_QUESTION_LENGTH}</span>
          <span id="paper-ask-validation">{validationMessage}</span>
        </div>

        {loading ? <p className="paper-ask-loading">正在生成回答…</p> : null}

        {error ? (
          <div className="paper-ask-error" role="alert">
            <strong>调用层错误</strong>
            <p>
              {error.status ? `${error.status} ` : ""}
              {error.userMessage}
            </p>
            {lastSubmittedQuestion ? (
              <button
                className="paper-secondary-button"
                type="button"
                disabled={loading}
                onClick={() => submitQuestion(lastSubmittedQuestion)}
              >
                重试
              </button>
            ) : null}
          </div>
        ) : null}

        {answer ? (
          <AskAnswer
            key={responseKey(answer)}
            response={answer}
            showDocumentLabel={showDocumentLabel}
            duplicateDocumentLabels={duplicateDocumentLabels}
            onSuggestionSelect={(suggestion) => updateQuestion(suggestion)}
          />
        ) : null}
      </GlassCard>
    </aside>
  );
}

interface AskAnswerProps {
  response: PaperAskResponse;
  showDocumentLabel: boolean;
  duplicateDocumentLabels: ReadonlySet<string>;
  onSuggestionSelect: (suggestion: string) => void;
}

function AskAnswer({
  response,
  showDocumentLabel,
  duplicateDocumentLabels,
  onSuggestionSelect,
}: AskAnswerProps) {
  if (response.is_fallback && response.fallback_reason) {
    return (
      <article className="paper-ask-answer paper-ask-answer--fallback">
        <div className="paper-ask-answer__header">
          <strong>证据不足</strong>
          <span>置信度:{CONFIDENCE_LABELS[response.confidence]}</span>
        </div>
        <p className="paper-copy">{FALLBACK_REASON_COPY[response.fallback_reason]}</p>
        <p className="paper-secondary">{FALLBACK_HINT}</p>
        <FollowUpSuggestions suggestions={response.follow_up_suggestions} onSelect={onSuggestionSelect} />
      </article>
    );
  }

  return (
    <article className="paper-ask-answer">
      <div className="paper-ask-answer__header">
        <strong>回答</strong>
        <span>置信度:{CONFIDENCE_LABELS[response.confidence]}</span>
      </div>
      <p className="paper-copy">{response.answer}</p>
      {response.citations.length > 0 ? (
        <div className="paper-ask-citations" aria-label="回答出处">
          {response.citations.map((citation) => (
            <CitationChip
              citation={citation}
              duplicateDocumentLabels={duplicateDocumentLabels}
              key={`${response.message_id}-${citation.source_id}`}
              showDocumentLabel={showDocumentLabel}
            />
          ))}
        </div>
      ) : null}
      <FollowUpSuggestions suggestions={response.follow_up_suggestions} onSelect={onSuggestionSelect} />
    </article>
  );
}

interface FollowUpSuggestionsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
}

function FollowUpSuggestions({ suggestions, onSelect }: FollowUpSuggestionsProps) {
  const visibleSuggestions = suggestions.slice(0, 3);
  if (visibleSuggestions.length === 0) {
    return null;
  }

  return (
    <div className="paper-ask-followups" aria-label="建议追问">
      {visibleSuggestions.map((suggestion) => (
        <button key={suggestion} type="button" onClick={() => onSelect(suggestion)}>
          {suggestion}
        </button>
      ))}
    </div>
  );
}
