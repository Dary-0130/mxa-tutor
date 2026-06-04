from datetime import datetime
from typing import Literal

import pytest

from adapters.storage.sqlite_chat_store import SqliteChatStore
from adapters.storage.sqlite_project_store import SqliteProjectStore
from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatSessionNotFoundError, ProjectNotFoundError


def _session(
    session_id: str = "session-1",
    project_id: str = "p1",
    updated_at: datetime | None = None,
) -> ChatSession:
    created_at = datetime(2026, 6, 4, 12, 0, 0)
    return ChatSession(
        session_id=session_id,
        project_id=project_id,
        created_at=created_at,
        updated_at=updated_at or created_at,
        title=None,
    )


def _message(
    message_id: str = "msg-1",
    session_id: str = "session-1",
    created_at: datetime | None = None,
    role: Literal["user", "assistant", "system"] = "user",
) -> ChatMessage:
    return ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=f"{role}:{message_id}",
        created_at=created_at or datetime(2026, 6, 4, 12, 1, 0),
    )


async def _create_project(project_store: SqliteProjectStore, project_id: str = "p1") -> None:
    await project_store.create_pending(project_id, "demo.zip")


async def test_create_session_round_trips(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    session = _session()

    await chat_store.create_session(session)

    stored = await chat_store.get_session("session-1")
    assert stored == session


async def test_create_session_missing_project_raises_project_not_found(
    chat_store: SqliteChatStore,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        await chat_store.create_session(_session(project_id="missing"))


async def test_create_session_duplicate_raises_value_error(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    await chat_store.create_session(_session())

    with pytest.raises(ValueError):
        await chat_store.create_session(_session())


async def test_append_message_lists_by_created_at_and_updates_session(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    await chat_store.create_session(_session())
    first = _message("msg-1", created_at=datetime(2026, 6, 4, 12, 1, 0))
    second = _message(
        "msg-2",
        created_at=datetime(2026, 6, 4, 12, 2, 0),
        role="assistant",
    )

    await chat_store.append_message(first)
    await chat_store.append_message(second)

    assert await chat_store.list_messages("session-1") == [first, second]
    assert await chat_store.list_messages("session-1", limit=1, offset=1) == [second]
    assert (await chat_store.get_session("session-1")).updated_at == second.created_at


async def test_append_message_missing_session_raises_chat_session_not_found(
    chat_store: SqliteChatStore,
) -> None:
    with pytest.raises(ChatSessionNotFoundError):
        await chat_store.append_message(_message(session_id="missing"))


async def test_append_message_duplicate_rolls_back_without_updating_session(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    await chat_store.create_session(_session())
    first = _message("msg-1", created_at=datetime(2026, 6, 4, 12, 1, 0))
    duplicate = _message("msg-1", created_at=datetime(2026, 6, 4, 12, 5, 0))
    await chat_store.append_message(first)

    with pytest.raises(ValueError):
        await chat_store.append_message(duplicate)

    assert await chat_store.list_messages("session-1") == [first]
    assert (await chat_store.get_session("session-1")).updated_at == first.created_at


async def test_list_messages_validates_session_and_pagination(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    await chat_store.create_session(_session())

    with pytest.raises(ChatSessionNotFoundError):
        await chat_store.list_messages("missing")
    with pytest.raises(ValueError):
        await chat_store.list_messages("session-1", limit=201)
    with pytest.raises(ValueError):
        await chat_store.list_messages("session-1", offset=-1)


async def test_list_recent_sessions_orders_by_updated_at_and_validates_limit(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    old_session = _session("old", updated_at=datetime(2026, 6, 4, 12, 0, 0))
    new_session = _session("new", updated_at=datetime(2026, 6, 4, 12, 5, 0))
    await chat_store.create_session(old_session)
    await chat_store.create_session(new_session)

    assert await chat_store.list_recent_sessions("p1") == [new_session, old_session]
    assert await chat_store.list_recent_sessions("missing") == []
    with pytest.raises(ValueError):
        await chat_store.list_recent_sessions("p1", limit=101)


async def test_delete_project_cascades_chat_sessions_and_messages(
    project_store: SqliteProjectStore,
    chat_store: SqliteChatStore,
) -> None:
    await _create_project(project_store)
    await chat_store.create_session(_session())
    await chat_store.append_message(_message())

    await project_store.delete("p1")

    with pytest.raises(ChatSessionNotFoundError):
        await chat_store.get_session("session-1")
    assert await chat_store.list_recent_sessions("p1") == []
