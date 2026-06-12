import type { UIMessage } from "../../lib/types";
import { resolveErrorMessage } from "../../lib/errorMessages";
import { CitationCard } from "./CitationCard";
import { FallbackBanner } from "./FallbackBanner";
import { FollowUpChips } from "./FollowUpChips";
import { formatTimestamp } from "./chatHelpers";

interface MessageBubbleProps {
  message: UIMessage;
  canRetryMessage: boolean;
  retryUserMessageId?: string;
  onRetry: (userMessageId: string) => void;
  onFollowUp: (value: string) => void;
}

export function MessageBubble({
  canRetryMessage,
  message,
  onFollowUp,
  onRetry,
  retryUserMessageId,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showFallback = Boolean(message.is_fallback || message.fallbackInferredFromHistory);
  const failedText = message.error_code ? resolveErrorMessage(message.error_code) : "回答生成失败,请重试";

  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[min(760px,100%)] border p-4 ${
          isUser
            ? "border-[var(--color-signal)] bg-black/10 text-right"
            : "border-[var(--color-rebar)] bg-[var(--color-formwork)]/70"
        }`}
      >
        <div className="mb-3 flex items-center justify-between gap-4 text-xs text-[var(--color-rebar)]">
          <span className="font-mono uppercase">{isUser ? "user" : "assistant"}</span>
          <time className="font-mono">{formatTimestamp(message.created_at)}</time>
        </div>
        {message.status === "pending" ? (
          <p className="font-mono text-sm text-[var(--color-rebar)]">正在生成回答...</p>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
        )}
        {message.status === "failed" ? (
          <RetryBlock
            buttonText="重试"
            canRetryMessage={canRetryMessage}
            text={failedText}
            userMessageId={retryUserMessageId}
            onRetry={onRetry}
          />
        ) : null}
        {message.status === "orphan" ? (
          <RetryBlock
            buttonText="重新生成"
            canRetryMessage={canRetryMessage}
            text="上次回答未生成,点击重试"
            userMessageId={message.message_id}
            onRetry={onRetry}
          />
        ) : null}
        {!isUser && message.status === "sent" ? (
          <>
            <FallbackBanner show={showFallback} />
            {message.citations.length > 0 ? (
              <section className="mt-5 border-t border-[var(--color-rebar)] pt-4 text-left">
                <h3 className="mb-3 font-mono text-xs font-bold text-[var(--color-signal)]">依据</h3>
                <div className="grid gap-2">
                  {message.citations.map((citation, index) => (
                    <CitationCard citation={citation} index={index} key={`${citation.file_path}-${index}`} />
                  ))}
                </div>
              </section>
            ) : null}
            <FollowUpChips suggestions={message.follow_up_suggestions} onSelect={onFollowUp} />
          </>
        ) : null}
      </div>
    </article>
  );
}
interface RetryBlockProps {
  buttonText: string;
  canRetryMessage: boolean;
  text: string;
  userMessageId?: string;
  onRetry: (userMessageId: string) => void;
}

function RetryBlock({ buttonText, canRetryMessage, onRetry, text, userMessageId }: RetryBlockProps) {
  return (
    <div className="mt-4 border-t border-[var(--color-rebar)] pt-3 text-left">
      <p className="text-sm text-[var(--color-signal-dim)]">{text}</p>
      <button
        className="mt-3 border border-[var(--color-signal)] px-3 py-2 font-mono text-xs font-bold uppercase text-[var(--color-ite)] disabled:cursor-not-allowed disabled:border-[var(--color-rebar)] disabled:text-[var(--color-rebar)]"
        disabled={!canRetryMessage || !userMessageId}
        type="button"
        onClick={() => {
          if (userMessageId) {
            onRetry(userMessageId);
          }
        }}
      >
        {buttonText}
      </button>
    </div>
  );
}
