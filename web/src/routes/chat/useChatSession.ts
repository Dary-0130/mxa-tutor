import { useCallback, useEffect, useRef } from "react";
import { ApiException, apiGet, apiPost } from "../../lib/api";
import {
  clearChatActiveSession,
  readChatActiveSession,
  writeChatActiveSession,
} from "../../lib/localStore";
import type {
  ChatMessagesResponse,
  ChatRequest,
  ChatResponse,
  ChatSessionsResponse,
} from "../../lib/types";
import { generateRequestId, markOrphanUsers } from "./chatHelpers";
import {
  canRetry,
  canSubmit,
  isNewSessionUnconfirmed,
  type ChatAction,
  type ChatState,
} from "./useChatReducer";

type DispatchChat = (action: ChatAction) => void;

function errorCode(error: unknown): string {
  return error instanceof ApiException ? error.code : "network_error";
}

export function useChatSession(projectId: string, state: ChatState, dispatch: DispatchChat) {
  const latestRequestIdRef = useRef<string | null>(null);
  const recoveryKeyRef = useRef<string | null>(null);
  const resolvedSessionRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadSessions = useCallback(async () => {
    dispatch({ type: "SESSIONS_LOAD_START" });
    try {
      const data = await apiGet<ChatSessionsResponse>(`/projects/${projectId}/sessions`);
      if (!mountedRef.current) {
        return;
      }
      dispatch({ type: "SESSIONS_LOADED", sessions: data.sessions });
    } catch (error) {
      const code = errorCode(error);
      if (code === "project_not_found") {
        clearChatActiveSession(projectId);
      }
      if (mountedRef.current) {
        dispatch({ type: "SESSIONS_LOAD_FAILED", errorCode: code });
      }
    }
  }, [dispatch, projectId]);

  const loadMessages = useCallback(
    async (sessionId: string) => {
      dispatch({ type: "MESSAGES_LOAD_START", sessionId });
      try {
        const data = await apiGet<ChatMessagesResponse>(
          `/projects/${projectId}/sessions/${sessionId}/messages`,
        );
        if (!mountedRef.current) {
          return;
        }
        dispatch({ type: "MESSAGES_LOADED", sessionId, messages: markOrphanUsers(data.messages) });
      } catch (error) {
        const code = errorCode(error);
        if (code === "chat_session_not_found") {
          clearChatActiveSession(projectId, sessionId);
        }
        if (code === "project_not_found") {
          clearChatActiveSession(projectId);
        }
        if (mountedRef.current) {
          dispatch({ type: "MESSAGES_LOAD_FAILED", sessionId, errorCode: code });
        }
      }
    },
    [dispatch, projectId],
  );

  useEffect(() => {
    const storedSessionId = readChatActiveSession(projectId);
    dispatch({ type: "INIT_ACTIVE_SESSION", sessionId: storedSessionId });
    void loadSessions();
    if (storedSessionId) {
      void loadMessages(storedSessionId);
    }
  }, [dispatch, loadMessages, loadSessions, projectId]);

  useEffect(() => {
    if (state.newSessionAttempt?.status !== "resolving") {
      recoveryKeyRef.current = null;
      return;
    }
    const recoveryKey = state.newSessionAttempt.failedUserTempId;
    if (recoveryKeyRef.current === recoveryKey) {
      return;
    }
    recoveryKeyRef.current = recoveryKey;
    void loadSessions();
  }, [loadSessions, state.newSessionAttempt]);

  useEffect(() => {
    if (state.newSessionAttempt?.status !== "resolved") {
      return;
    }
    if (resolvedSessionRef.current === state.newSessionAttempt.sessionId) {
      return;
    }
    resolvedSessionRef.current = state.newSessionAttempt.sessionId;
    writeChatActiveSession(projectId, state.newSessionAttempt.sessionId);
  }, [projectId, state.newSessionAttempt]);

  const sendCurrentDraft = useCallback(async () => {
    if (!canSubmit(state)) {
      return;
    }
    const requestId = generateRequestId();
    const userTempId = `temp-user-${requestId}`;
    const assistantTempId = `temp-assistant-${requestId}`;
    const now = new Date().toISOString();
    const question = state.inputDraft.trim();
    const sessionId = state.activeSessionId;
    latestRequestIdRef.current = requestId;
    dispatch({ type: "SEND_START", requestId, userTempId, assistantTempId, now });
    try {
      const body: ChatRequest = { question, session_id: sessionId ?? undefined };
      const response = await apiPost<ChatResponse>(`/projects/${projectId}/chat`, body);
      if (!mountedRef.current || latestRequestIdRef.current !== requestId) {
        return;
      }
      dispatch({ type: "SEND_SUCCESS", requestId, response, now: new Date().toISOString() });
      writeChatActiveSession(projectId, response.session_id);
      void loadSessions();
    } catch (error) {
      if (!mountedRef.current || latestRequestIdRef.current !== requestId) {
        return;
      }
      const code = errorCode(error);
      if (code === "chat_session_not_found" && sessionId) {
        clearChatActiveSession(projectId, sessionId);
      }
      if (code === "project_not_found") {
        clearChatActiveSession(projectId);
      }
      dispatch({ type: "SEND_FAILED", requestId, errorCode: code });
    }
  }, [dispatch, loadSessions, projectId, state]);

  const retryMessage = useCallback(
    async (userMessageId: string) => {
      if (!canRetry(state) || !state.activeSessionId) {
        return;
      }
      const target = state.messages.find((message) => message.message_id === userMessageId);
      if (!target || target.role !== "user") {
        return;
      }
      const requestId = generateRequestId();
      const assistantTempId = `temp-assistant-${requestId}`;
      latestRequestIdRef.current = requestId;
      dispatch({
        type: "MESSAGE_RETRY",
        requestId,
        userMessageId,
        assistantTempId,
        now: new Date().toISOString(),
      });
      try {
        const response = await apiPost<ChatResponse>(`/projects/${projectId}/chat`, {
          question: target.content,
          session_id: state.activeSessionId,
        } satisfies ChatRequest);
        if (!mountedRef.current || latestRequestIdRef.current !== requestId) {
          return;
        }
        dispatch({ type: "SEND_SUCCESS", requestId, response, now: new Date().toISOString() });
        writeChatActiveSession(projectId, response.session_id);
        void loadSessions();
      } catch (error) {
        if (!mountedRef.current || latestRequestIdRef.current !== requestId) {
          return;
        }
        const code = errorCode(error);
        if (code === "chat_session_not_found") {
          clearChatActiveSession(projectId, state.activeSessionId);
        }
        dispatch({ type: "SEND_FAILED", requestId, errorCode: code });
      }
    },
    [dispatch, loadSessions, projectId, state],
  );

  const switchSession = useCallback(
    (sessionId: string) => {
      if (state.sending || isNewSessionUnconfirmed(state)) {
        return;
      }
      dispatch({ type: "SESSION_SWITCH", sessionId });
      void loadMessages(sessionId);
    },
    [dispatch, loadMessages, state],
  );

  const startNewSession = useCallback(() => {
    if (state.sending || isNewSessionUnconfirmed(state)) {
      return;
    }
    dispatch({ type: "SESSION_NEW" });
  }, [dispatch, state]);

  return { loadSessions, loadMessages, retryMessage, sendCurrentDraft, startNewSession, switchSession };
}
