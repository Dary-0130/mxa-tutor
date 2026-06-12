import type { KeyboardEvent } from "react";

interface ChatInputBarProps {
  canSubmitMessage: boolean;
  disabledReason?: string | null;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatInputBar({
  canSubmitMessage,
  disabledReason,
  onChange,
  onSubmit,
  value,
}: ChatInputBarProps) {
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    if (canSubmitMessage) {
      onSubmit();
    }
  }

  return (
    <footer className="border-t-2 border-[var(--color-rebar)] bg-[var(--color-concrete)] px-4 py-4">
      <div className="mx-auto grid max-w-6xl gap-3">
        <label className="sr-only" htmlFor="chat-input">
          输入问题
        </label>
        <textarea
          className="min-h-28 resize-y border border-[var(--color-rebar)] bg-[var(--color-formwork)] p-3 text-sm leading-7 text-[var(--color-ite)] outline-none focus:border-[var(--color-signal)] focus:outline-2 focus:outline-[var(--color-signal)]"
          id="chat-input"
          maxLength={1000}
          placeholder="问这个工程里的文件、模块、参数..."
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-h-5 text-xs text-[var(--color-rebar)]">
            {disabledReason || `${value.length}/1000`}
          </p>
          <button
            className="bg-[var(--color-signal)] px-6 py-3 font-mono text-xs font-black uppercase text-black disabled:cursor-not-allowed disabled:bg-[var(--color-rebar)]"
            disabled={!canSubmitMessage}
            type="button"
            onClick={onSubmit}
          >
            SEND
          </button>
        </div>
      </div>
    </footer>
  );
}
