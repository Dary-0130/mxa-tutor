"""对话历史存储抽象接口(TASK-204 SQLite 实现)。"""

from abc import ABC, abstractmethod

from core.domain.chat import ChatMessage, ChatSession


class ChatStore(ABC):
    """对话存储(5 方法)。"""

    @abstractmethod
    async def create_session(self, session: ChatSession) -> None:
        """创建会话。

        - session.project_id 不存在 → ProjectNotFoundError
        - session.session_id 已存在 → ValueError
        """
        ...

    @abstractmethod
    async def append_message(self, message: ChatMessage) -> None:
        """追加消息到会话,同步更新 session.updated_at。

        - message.session_id 不存在 → ChatSessionNotFoundError
        - message.message_id 已存在 → ValueError
        """
        ...

    @abstractmethod
    async def get_session(self, session_id: str) -> ChatSession:
        """取会话元信息。不存在 → ChatSessionNotFoundError。"""
        ...

    @abstractmethod
    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        """按 created_at ASC 列消息。

        - 会话不存在 → ChatSessionNotFoundError
        - limit <= 200 / offset >= 0,超界抛 ValueError
        """
        ...

    @abstractmethod
    async def list_recent_sessions(
        self, project_id: str, limit: int = 20
    ) -> list[ChatSession]:
        """按 updated_at DESC 列会话。

        - limit <= 100
        - project 不存在返回空列表
        """
        ...
