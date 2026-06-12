import type { ChatResponse, ChatSessionDTO, UIMessage } from "../../lib/types";

export type NewSessionAttempt =
  | null
  | { status: "resolving"; failedUserTempId: string }
  | { status: "resolved"; sessionId: string; failedUserTempId: string }
  | { status: "needs_refresh"; failedUserTempId: string };

export interface ChatState {
  sessions: ChatSessionDTO[];
  activeSessionId: string | null;
  messages: UIMessage[];
  inputDraft: string;
  sessionsLoading: boolean;
  messagesLoading: boolean;
  sending: boolean;
  sessionsErrorCode: string | null;
  messagesErrorCode: string | null;
  pendingRequestId: string | null;
  pendingSessionId: string | null;
  pendingAssistantTempId: string | null;
  pendingUserTempId: string | null;
  preSendSessionsSnapshot: string[];
  newSessionAttempt: NewSessionAttempt;
}

export type ChatAction =
  | { type: "INIT_ACTIVE_SESSION"; sessionId: string | null }
  | { type: "INPUT_CHANGED"; value: string }
  | { type: "FOLLOW_UP_SELECTED"; value: string }
  | { type: "SESSIONS_LOAD_START" }
  | { type: "SESSIONS_LOADED"; sessions: ChatSessionDTO[] }
  | { type: "SESSIONS_LOAD_FAILED"; errorCode: string }
  | { type: "MESSAGES_LOAD_START"; sessionId: string }
  | { type: "MESSAGES_LOADED"; sessionId: string; messages: UIMessage[] }
  | { type: "MESSAGES_LOAD_FAILED"; sessionId: string; errorCode: string }
  | { type: "SEND_START"; requestId: string; userTempId: string; assistantTempId: string; now: string }
  | { type: "SEND_SUCCESS"; requestId: string; response: ChatResponse; now: string }
  | { type: "SEND_FAILED"; requestId: string; errorCode: string }
  | { type: "MESSAGE_RETRY"; requestId: string; userMessageId: string; assistantTempId: string; now: string }
  | { type: "SESSION_SWITCH"; sessionId: string }
  | { type: "SESSION_NEW" }
  | { type: "RESET" };

export function createInitialChatState(): ChatState {
  return {
    sessions: [],
    activeSessionId: null,
    messages: [],
    inputDraft: "",
    sessionsLoading: false,
    messagesLoading: false,
    sending: false,
    sessionsErrorCode: null,
    messagesErrorCode: null,
    pendingRequestId: null,
    pendingSessionId: null,
    pendingAssistantTempId: null,
    pendingUserTempId: null,
    preSendSessionsSnapshot: [],
    newSessionAttempt: null,
  };
}

export function isNewSessionUnconfirmed(state: ChatState): boolean {
  return (
    state.activeSessionId === null &&
    (state.newSessionAttempt?.status === "resolving" ||
      state.newSessionAttempt?.status === "needs_refresh")
  );
}

export function canSubmit(state: ChatState): boolean {
  const question = state.inputDraft.trim();
  return question.length > 0 && question.length <= 1000 && !state.sending && !isNewSessionUnconfirmed(state);
}

export function canRetry(state: ChatState): boolean {
  return state.activeSessionId !== null && !state.sending && !isNewSessionUnconfirmed(state);
}

function clearPending(): Pick<
  ChatState,
  "sending" | "pendingRequestId" | "pendingSessionId" | "pendingAssistantTempId" | "pendingUserTempId"
> {
  return {
    sending: false,
    pendingRequestId: null,
    pendingSessionId: null,
    pendingAssistantTempId: null,
    pendingUserTempId: null,
  };
}

function replacePendingAssistant(state: ChatState, response: ChatResponse, now: string): UIMessage[] {
  return state.messages.map((message) => {
    if (message.message_id !== state.pendingAssistantTempId) {
      return message;
    }
    return {
      message_id: response.message_id,
      role: "assistant",
      content: response.answer,
      created_at: now,
      citations: response.citations,
      status: "sent",
      is_fallback: response.is_fallback,
      fallback_reason: response.fallback_reason,
      confidence: response.confidence,
      follow_up_suggestions: response.follow_up_suggestions,
    };
  });
}

function markPendingFailed(state: ChatState, errorCode: string): UIMessage[] {
  return state.messages.map((message) => {
    if (message.message_id !== state.pendingAssistantTempId) {
      return message;
    }
    return {
      ...message,
      status: "failed",
      error_code: errorCode,
    };
  });
}

function resolveNewSession(state: ChatState, sessions: ChatSessionDTO[]): Partial<ChatState> {
  if (state.newSessionAttempt?.status !== "resolving") {
    return {};
  }
  const before = new Set(state.preSendSessionsSnapshot);
  const newSessions = sessions.filter((session) => !before.has(session.session_id));
  if (newSessions.length !== 1) {
    return {
      newSessionAttempt: {
        status: "needs_refresh",
        failedUserTempId: state.newSessionAttempt.failedUserTempId,
      },
    };
  }
  const sessionId = newSessions[0].session_id;
  return {
    activeSessionId: sessionId,
    newSessionAttempt: {
      status: "resolved",
      sessionId,
      failedUserTempId: state.newSessionAttempt.failedUserTempId,
    },
  };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "INIT_ACTIVE_SESSION":
      return { ...state, activeSessionId: action.sessionId };
    case "INPUT_CHANGED":
    case "FOLLOW_UP_SELECTED":
      return { ...state, inputDraft: action.value.slice(0, 1000) };
    case "SESSIONS_LOAD_START":
      return { ...state, sessionsLoading: true, sessionsErrorCode: null };
    case "SESSIONS_LOADED":
      return {
        ...state,
        sessions: action.sessions,
        sessionsLoading: false,
        sessionsErrorCode: null,
        ...resolveNewSession(state, action.sessions),
      };
    case "SESSIONS_LOAD_FAILED":
      return {
        ...state,
        sessionsLoading: false,
        sessionsErrorCode: action.errorCode,
        newSessionAttempt:
          state.newSessionAttempt?.status === "resolving"
            ? { status: "needs_refresh", failedUserTempId: state.newSessionAttempt.failedUserTempId }
            : state.newSessionAttempt,
      };
    case "MESSAGES_LOAD_START":
      if (state.sending || isNewSessionUnconfirmed(state)) {
        return state;
      }
      return { ...state, activeSessionId: action.sessionId, messagesLoading: true, messagesErrorCode: null };
    case "MESSAGES_LOADED":
      if (action.sessionId !== state.activeSessionId) {
        return state;
      }
      return { ...state, messages: action.messages, messagesLoading: false, messagesErrorCode: null };
    case "MESSAGES_LOAD_FAILED":
      if (action.sessionId !== state.activeSessionId) {
        return state;
      }
      return { ...state, messagesLoading: false, messagesErrorCode: action.errorCode };
    case "SEND_START": {
      if (!canSubmit(state)) {
        return state;
      }
      const question = state.inputDraft.trim();
      const userMessage: UIMessage = {
        message_id: action.userTempId,
        role: "user",
        content: question,
        created_at: action.now,
        citations: [],
        status: "sent",
      };
      const assistantMessage: UIMessage = {
        message_id: action.assistantTempId,
        role: "assistant",
        content: "",
        created_at: action.now,
        citations: [],
        status: "pending",
      };
      return {
        ...state,
        messages: [...state.messages, userMessage, assistantMessage],
        inputDraft: "",
        sending: true,
        pendingRequestId: action.requestId,
        pendingSessionId: state.activeSessionId,
        pendingAssistantTempId: action.assistantTempId,
        pendingUserTempId: action.userTempId,
        preSendSessionsSnapshot: state.sessions.map((session) => session.session_id),
      };
    }
    case "SEND_SUCCESS":
      if (action.requestId !== state.pendingRequestId) {
        return state;
      }
      return {
        ...state,
        ...clearPending(),
        activeSessionId: state.pendingSessionId ?? action.response.session_id,
        messages: replacePendingAssistant(state, action.response, action.now),
        newSessionAttempt: state.pendingSessionId === null ? null : state.newSessionAttempt,
      };
    case "SEND_FAILED":
      if (action.requestId !== state.pendingRequestId) {
        return state;
      }
      return {
        ...state,
        ...clearPending(),
        messages: markPendingFailed(state, action.errorCode),
        newSessionAttempt:
          state.pendingSessionId === null && state.pendingUserTempId
            ? { status: "resolving", failedUserTempId: state.pendingUserTempId }
            : state.newSessionAttempt,
      };
    case "MESSAGE_RETRY": {
      if (!canRetry(state)) {
        return state;
      }
      const target = state.messages.find((message) => message.message_id === action.userMessageId);
      if (!target || target.role !== "user") {
        return state;
      }
      const assistantMessage: UIMessage = {
        message_id: action.assistantTempId,
        role: "assistant",
        content: "",
        created_at: action.now,
        citations: [],
        status: "pending",
      };
      return {
        ...state,
        messages: [
          ...state.messages.map((message) =>
            message.message_id === action.userMessageId ? { ...message, status: "sent" as const } : message,
          ),
          assistantMessage,
        ],
        sending: true,
        pendingRequestId: action.requestId,
        pendingSessionId: state.activeSessionId,
        pendingAssistantTempId: action.assistantTempId,
        pendingUserTempId: action.userMessageId,
      };
    }
    case "SESSION_SWITCH":
      if (state.sending || isNewSessionUnconfirmed(state)) {
        return state;
      }
      return { ...state, activeSessionId: action.sessionId, messages: [], messagesLoading: true };
    case "SESSION_NEW":
      if (state.sending || isNewSessionUnconfirmed(state)) {
        return state;
      }
      return { ...state, activeSessionId: null, messages: [], messagesErrorCode: null };
    case "RESET":
      return createInitialChatState();
    default:
      return state;
  }
}
