from datetime import datetime

from core.domain.chat import ChatMessage, ChatSession


def test_chat_message_required_fields_and_default_citations() -> None:
    created_at = datetime(2026, 6, 4, 12, 0, 0)

    message = ChatMessage(
        message_id="msg-1",
        session_id="session-1",
        role="user",
        content="怎么分析这个控制环?",
        created_at=created_at,
    )

    assert message.message_id == "msg-1"
    assert message.session_id == "session-1"
    assert message.role == "user"
    assert message.content == "怎么分析这个控制环?"
    assert message.created_at == created_at
    assert message.citations_json == "[]"


def test_chat_session_required_fields_and_default_title() -> None:
    created_at = datetime(2026, 6, 4, 12, 0, 0)
    updated_at = datetime(2026, 6, 4, 12, 1, 0)

    session = ChatSession(
        session_id="session-1",
        project_id="project-1",
        created_at=created_at,
        updated_at=updated_at,
    )

    assert session.session_id == "session-1"
    assert session.project_id == "project-1"
    assert session.created_at == created_at
    assert session.updated_at == updated_at
    assert session.title is None


def test_chat_dataclass_fields_match_contract() -> None:
    assert set(ChatMessage.__dataclass_fields__) == {
        "message_id",
        "session_id",
        "role",
        "content",
        "created_at",
        "citations_json",
    }
    assert set(ChatSession.__dataclass_fields__) == {
        "session_id",
        "project_id",
        "created_at",
        "updated_at",
        "title",
    }
