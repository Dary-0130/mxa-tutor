import { useReducer } from "react";
import { useParams } from "react-router-dom";
import { PanoramaScene } from "../components/scene/PanoramaScene";
import { resolveErrorMessage } from "../lib/errorMessages";
import { ChatHeader } from "./chat/ChatHeader";
import { ChatInputBar } from "./chat/ChatInputBar";
import { MessageList } from "./chat/MessageList";
import { useChatSession } from "./chat/useChatSession";
import {
  canRetry,
  canSubmit,
  chatReducer,
  createInitialChatState,
  isNewSessionUnconfirmed,
  type ChatState,
  type NewSessionAttempt,
} from "./chat/useChatReducer";

export function ChatPage() {
  const { projectId } = useParams();
  if (!projectId) {
    return (
      <section className="brutal-panel max-w-3xl p-8">
        <h1 className="text-3xl font-black">工程不存在</h1>
      </section>
    );
  }
  return <ChatPageContent projectId={projectId} />;
}

function ChatPageContent({ projectId }: { projectId: string }) {
  const [state, dispatch] = useReducer(chatReducer, undefined, createInitialChatState);

  const chat = useChatSession(projectId, state, dispatch);
  const submitEnabled = canSubmit(state);
  const retryEnabled = canRetry(state);
  const locked = state.sending || isNewSessionUnconfirmed(state);

  return (
    <>
      <PanoramaScene panoramaX={0} />
    <section className="relative z-10 flex h-[calc(100vh-72px)] min-h-[620px] flex-col">
      <ChatHeader
        activeSessionId={state.activeSessionId}
        disabled={locked}
        projectId={projectId}
        sessions={state.sessions}
        onNewSession={chat.startNewSession}
        onSwitchSession={chat.switchSession}
      />
      <StatusStrip
        messagesErrorCode={state.messagesErrorCode}
        newSessionAttempt={state.newSessionAttempt}
        sessionsErrorCode={state.sessionsErrorCode}
        onRefresh={chat.loadSessions}
      />
      <MessageList
        canRetryMessage={retryEnabled}
        messages={state.messages}
        messagesLoading={state.messagesLoading}
        onFollowUp={(value) => dispatch({ type: "FOLLOW_UP_SELECTED", value })}
        onRetry={(messageId) => void chat.retryMessage(messageId)}
      />
      <ChatInputBar
        canSubmitMessage={submitEnabled}
        disabledReason={inputDisabledReason(state)}
        value={state.inputDraft}
        onChange={(value) => dispatch({ type: "INPUT_CHANGED", value })}
        onSubmit={() => void chat.sendCurrentDraft()}
      />
    </section>
    </>
  );
}

type StatusStripProps = {
  messagesErrorCode: string | null;
  newSessionAttempt: NewSessionAttempt;
  sessionsErrorCode: string | null;
  onRefresh: () => void;
};

function StatusStrip({
  messagesErrorCode,
  newSessionAttempt,
  onRefresh,
  sessionsErrorCode,
}: StatusStripProps) {
  const errorCode = messagesErrorCode ?? sessionsErrorCode;
  if (newSessionAttempt?.status === "resolving") {
    return (
      <div className="border-b border-[var(--color-rebar)] px-4 py-3 text-sm text-[var(--color-signal-dim)]">
        正在确认会话状态,暂时不能发送或重试。
      </div>
    );
  }
  if (newSessionAttempt?.status === "needs_refresh") {
    return (
      <div className="flex items-center justify-between gap-3 border-b border-[var(--color-rebar)] px-4 py-3 text-sm text-[var(--color-signal-dim)]">
        <span>会话状态未确认,请刷新会话列表后重试。</span>
        <button className="text-command" type="button" onClick={onRefresh}>
          刷新会话
        </button>
      </div>
    );
  }
  if (!errorCode) {
    return null;
  }
  return (
    <div className="border-b border-[var(--color-rebar)] px-4 py-3 text-sm text-[var(--color-signal-dim)]">
      {resolveErrorMessage(errorCode)}
    </div>
  );
}

function inputDisabledReason(state: ChatState): string | null {
  if (state.sending) {
    return "正在生成回答...";
  }
  if (state.newSessionAttempt?.status === "resolving") {
    return "正在确认会话状态,草稿已保留";
  }
  if (state.newSessionAttempt?.status === "needs_refresh") {
    return "会话状态未确认,请刷新会话列表后重试";
  }
  return null;
}
