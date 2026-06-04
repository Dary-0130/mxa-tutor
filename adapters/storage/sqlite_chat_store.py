"""SQLite 持久化 ChatStore 实现(TASK-204)。"""

from datetime import datetime

import aiosqlite
from loguru import logger

from adapters.storage._connection import open_connection
from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatSessionNotFoundError, ProjectNotFoundError, StoreError
from core.interfaces.chat_store import ChatStore


class SqliteChatStore(ChatStore):
    """SQLite 持久化 ChatStore(5 方法接口,TASK-204)。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def aclose(self) -> None:
        """MCS 阶段连接按需打开 + 即关,本方法 no-op。"""

    async def create_session(self, session: ChatSession) -> None:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT 1 FROM project_status_record WHERE project_id=?",
                    (session.project_id,),
                )
                if await cur.fetchone() is None:
                    raise ProjectNotFoundError(f"project not found: {session.project_id}")

                await conn.execute(
                    "INSERT INTO chat_session("
                    "session_id, project_id, created_at, updated_at, title"
                    ") VALUES (?,?,?,?,?)",
                    (
                        session.session_id,
                        session.project_id,
                        session.created_at.isoformat(),
                        session.updated_at.isoformat(),
                        session.title,
                    ),
                )
                await conn.commit()
            except ProjectNotFoundError:
                raise
            except aiosqlite.IntegrityError:
                await conn.rollback()
                raise ValueError("session_id already exists") from None
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteChatStore.create_session failed: session_id={} exception={}",
                    session.session_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def append_message(self, message: ChatMessage) -> None:
        async with open_connection(self._db_path) as conn:
            try:
                await conn.execute("BEGIN")
                cur = await conn.execute(
                    "SELECT 1 FROM chat_session WHERE session_id=?",
                    (message.session_id,),
                )
                if await cur.fetchone() is None:
                    await conn.rollback()
                    raise ChatSessionNotFoundError(message.session_id)

                try:
                    await conn.execute(
                        "INSERT INTO chat_message("
                        "message_id, session_id, role, content, created_at, citations_json"
                        ") VALUES (?,?,?,?,?,?)",
                        (
                            message.message_id,
                            message.session_id,
                            message.role,
                            message.content,
                            message.created_at.isoformat(),
                            message.citations_json,
                        ),
                    )
                except aiosqlite.IntegrityError:
                    await conn.rollback()
                    raise ValueError("message_id already exists") from None

                await conn.execute(
                    "UPDATE chat_session SET updated_at=? WHERE session_id=?",
                    (message.created_at.isoformat(), message.session_id),
                )
                await conn.commit()
            except (ChatSessionNotFoundError, ValueError):
                raise
            except aiosqlite.OperationalError as exc:
                await conn.rollback()
                logger.error(
                    "SqliteChatStore.append_message failed: session_id={} exception={}",
                    message.session_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

    async def get_session(self, session_id: str) -> ChatSession:
        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT session_id, project_id, created_at, updated_at, title "
                    "FROM chat_session WHERE session_id=?",
                    (session_id,),
                )
                row = await cur.fetchone()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteChatStore.get_session failed: session_id={} exception={}",
                    session_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None

        if row is None:
            raise ChatSessionNotFoundError(session_id)
        return _session_from_row(row)

    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        if limit > 200 or limit < 0 or offset < 0:
            raise ValueError("invalid pagination")

        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT 1 FROM chat_session WHERE session_id=?",
                    (session_id,),
                )
                if await cur.fetchone() is None:
                    raise ChatSessionNotFoundError(session_id)

                cur = await conn.execute(
                    "SELECT message_id, session_id, role, content, created_at, citations_json "
                    "FROM chat_message WHERE session_id=? "
                    "ORDER BY created_at ASC LIMIT ? OFFSET ?",
                    (session_id, limit, offset),
                )
                rows = await cur.fetchall()
            except ChatSessionNotFoundError:
                raise
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteChatStore.list_messages failed: session_id={} exception={}",
                    session_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return [_message_from_row(row) for row in rows]

    async def list_recent_sessions(
        self, project_id: str, limit: int = 20
    ) -> list[ChatSession]:
        if limit > 100 or limit < 0:
            raise ValueError("invalid limit")

        async with open_connection(self._db_path) as conn:
            try:
                cur = await conn.execute(
                    "SELECT session_id, project_id, created_at, updated_at, title "
                    "FROM chat_session WHERE project_id=? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (project_id, limit),
                )
                rows = await cur.fetchall()
            except aiosqlite.OperationalError as exc:
                logger.error(
                    "SqliteChatStore.list_recent_sessions failed: project_id={} exception={}",
                    project_id,
                    type(exc).__name__,
                )
                raise StoreError("sqlite_operation_failed") from None
        return [_session_from_row(row) for row in rows]


def _session_from_row(row: aiosqlite.Row) -> ChatSession:
    return ChatSession(
        session_id=row["session_id"],
        project_id=row["project_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        title=row["title"],
    )


def _message_from_row(row: aiosqlite.Row) -> ChatMessage:
    return ChatMessage(
        message_id=row["message_id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        citations_json=row["citations_json"],
    )
