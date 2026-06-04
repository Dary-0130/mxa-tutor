"""对话消息与会话 domain 数据结构(TASK-204)。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChatRole = Literal["user", "assistant", "system"]


@dataclass
class ChatMessage:
    """单条对话消息。所有字段持久化进 chat_message 表。"""

    message_id: str
    session_id: str
    role: ChatRole
    content: str
    created_at: datetime
    citations_json: str = "[]"


@dataclass
class ChatSession:
    """单次对话会话,绑定 project_id。"""

    session_id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
