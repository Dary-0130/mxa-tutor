import { Link } from "react-router-dom";
import type { ChatSessionDTO } from "../../lib/types";

interface ChatHeaderProps {
  activeSessionId: string | null;
  disabled: boolean;
  projectId: string;
  sessions: ChatSessionDTO[];
  onNewSession: () => void;
  onSwitchSession: (sessionId: string) => void;
}

export function ChatHeader({
  activeSessionId,
  disabled,
  onNewSession,
  onSwitchSession,
  projectId,
  sessions,
}: ChatHeaderProps) {
  return (
    <header className="border-b-2 border-[var(--color-rebar)] bg-[var(--color-concrete)] px-4 py-3">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <Link className="text-command" to={`/view/${projectId}`}>
            返回导览
          </Link>
          <h1 className="mt-2 truncate text-xl font-black">工程问答</h1>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="sr-only" htmlFor="chat-session-select">
            会话
          </label>
          <select
            className="border border-[var(--color-rebar)] bg-[var(--color-formwork)] px-3 py-2 font-mono text-xs text-[var(--color-ite)] disabled:text-[var(--color-rebar)]"
            disabled={disabled || sessions.length === 0}
            id="chat-session-select"
            value={activeSessionId ?? ""}
            onChange={(event) => onSwitchSession(event.target.value)}
          >
            <option disabled value="">
              新会话
            </option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.title || "未命名会话"}
              </option>
            ))}
          </select>
          <button
            className="border border-[var(--color-signal)] px-3 py-2 font-mono text-xs font-bold uppercase text-[var(--color-ite)] disabled:cursor-not-allowed disabled:border-[var(--color-rebar)] disabled:text-[var(--color-rebar)]"
            disabled={disabled}
            type="button"
            onClick={onNewSession}
          >
            新会话
          </button>
        </div>
      </div>
    </header>
  );
}
