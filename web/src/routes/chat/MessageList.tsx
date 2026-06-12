import type { UIMessage } from "../../lib/types";
import { MessageBubble } from "./MessageBubble";
import { useAutoScroll } from "./useAutoScroll";

interface MessageListProps {
  canRetryMessage: boolean;
  messages: UIMessage[];
  messagesLoading: boolean;
  onFollowUp: (value: string) => void;
  onRetry: (userMessageId: string) => void;
}

export function MessageList({
  canRetryMessage,
  messages,
  messagesLoading,
  onFollowUp,
  onRetry,
}: MessageListProps) {
  const { containerRef, handleScroll } = useAutoScroll(messages.map((message) => message.message_id).join("|"));

  return (
    <section
      className="min-h-0 flex-1 overflow-y-auto px-4 py-6"
      ref={containerRef}
      onScroll={handleScroll}
    >
      <div className="mx-auto grid max-w-6xl gap-4">
        {messagesLoading ? (
          <p className="font-mono text-sm text-[var(--color-rebar)]">正在加载会话...</p>
        ) : null}
        {!messagesLoading && messages.length === 0 ? (
          <div className="border border-[var(--color-rebar)] p-6">
            <p className="section-kicker">READY</p>
            <h2 className="mt-3 text-2xl font-black">从工程本身开始问</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--color-rebar)]">
              可以问入口文件、Simulink 模块、参数含义,回答会尽量带上依据。
            </p>
          </div>
        ) : null}
        {messages.map((message, index) => (
          <MessageBubble
            canRetryMessage={canRetryMessage}
            key={message.message_id}
            message={message}
            retryUserMessageId={findRetryUser(messages, index)}
            onFollowUp={onFollowUp}
            onRetry={onRetry}
          />
        ))}
      </div>
    </section>
  );
}

function findRetryUser(messages: UIMessage[], index: number): string | undefined {
  const message = messages[index];
  if (message.role === "user") {
    return message.message_id;
  }
  if (message.status !== "failed") {
    return undefined;
  }
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (messages[cursor].role === "user") {
      return messages[cursor].message_id;
    }
  }
  return undefined;
}
