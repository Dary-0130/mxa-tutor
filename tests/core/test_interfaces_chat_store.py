from datetime import datetime

import pytest

from core.domain.chat import ChatMessage, ChatSession
from core.interfaces.chat_store import ChatStore


def _session(session_id: str = "session-1") -> ChatSession:
    now = datetime(2026, 6, 4, 12, 0, 0)
    return ChatSession(
        session_id=session_id,
        project_id="project-1",
        created_at=now,
        updated_at=now,
    )


def _message(message_id: str = "msg-1") -> ChatMessage:
    return ChatMessage(
        message_id=message_id,
        session_id="session-1",
        role="user",
        content="hello",
        created_at=datetime(2026, 6, 4, 12, 1, 0),
    )


def test_chat_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        ChatStore()


class _StubChatStore(ChatStore):
    def __init__(self) -> None:
        self.sessions: dict[str, ChatSession] = {}
        self.messages: list[ChatMessage] = []

    async def create_session(self, session: ChatSession) -> None:
        self.sessions[session.session_id] = session

    async def append_message(self, message: ChatMessage) -> None:
        self.messages.append(message)

    async def get_session(self, session_id: str) -> ChatSession:
        return self.sessions[session_id]

    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        return [
            message
            for message in self.messages[offset : offset + limit]
            if message.session_id == session_id
        ]

    async def list_recent_sessions(
        self, project_id: str, limit: int = 20
    ) -> list[ChatSession]:
        return [
            session
            for session in self.sessions.values()
            if session.project_id == project_id
        ][:limit]


async def test_chat_store_stub_implements_five_methods() -> None:
    store = _StubChatStore()
    session = _session()
    message = _message()

    await store.create_session(session)
    await store.append_message(message)

    assert await store.get_session("session-1") == session
    assert await store.list_messages("session-1") == [message]
    assert await store.list_recent_sessions("project-1") == [session]
