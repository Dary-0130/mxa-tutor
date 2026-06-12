import type { ChatMessageDTO, SourceRef, UIMessage } from "../../lib/types";

export const PROJECT_OVERVIEW_SENTINEL = "__project_overview__";

export function generateRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function displayFilePath(source: Pick<SourceRef, "file_path">): string {
  if (source.file_path === PROJECT_OVERVIEW_SENTINEL) {
    return "项目总览";
  }
  return source.file_path || "未知来源";
}

export function formatLineRange(lineRange?: [number, number] | null): string | null {
  if (!lineRange) {
    return null;
  }
  const [start, end] = lineRange;
  return start === end ? `第 ${start} 行` : `第 ${start}-${end} 行`;
}

export function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function fallbackInferredFromHistory(message: ChatMessageDTO | UIMessage): boolean {
  return message.role === "assistant" && message.citations.length === 0;
}

export function orphanScan(messages: ChatMessageDTO[]): string[] {
  const orphanIds: string[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.role !== "user") {
      continue;
    }
    const next = messages[index + 1];
    if (!next || next.role !== "assistant") {
      orphanIds.push(message.message_id);
    }
  }
  return orphanIds;
}

export function markOrphanUsers(messages: ChatMessageDTO[]): UIMessage[] {
  const orphanIds = new Set(orphanScan(messages));
  return messages
    .filter((message): message is ChatMessageDTO & { role: "user" | "assistant" } => {
      return message.role === "user" || message.role === "assistant";
    })
    .map((message) => {
      const isOrphan = message.role === "user" && orphanIds.has(message.message_id);
      const inferredFallback = fallbackInferredFromHistory(message);
      return {
        message_id: message.message_id,
        role: message.role,
        content: message.content,
        created_at: message.created_at,
        citations: message.citations,
        status: isOrphan ? "orphan" : "sent",
        fallbackInferredFromHistory: inferredFallback || undefined,
      };
    });
}
