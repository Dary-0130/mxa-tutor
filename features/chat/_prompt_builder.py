"""Build LLM messages for chat QA."""

from __future__ import annotations

import re

from core.domain.chat import ChatMessage
from core.domain.project import Project
from core.interfaces.llm_provider import LLMMessage

from ._prompt_loader import load_prompt_template
from ._retriever import SourceEntry

MAX_SNIPPET_CHARS = 300
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_MESSAGES = 10


class ChatPromptBuilder:
    """Prompt builder for the chat service."""

    def build_messages(
        self,
        project: Project,
        source_entries: list[SourceEntry],
        history: list[ChatMessage],
        question: str,
    ) -> list[LLMMessage]:
        """Build system, history, and user messages."""
        template = load_prompt_template()
        history_msgs = [
            LLMMessage(role=message.role, content=message.content)
            for message in history[-MAX_HISTORY_MESSAGES:]
        ]
        source_block = "\n".join(
            f"[{entry.source_id}] {entry.hit.source_type}: {_truncate(entry.snippet, MAX_SNIPPET_CHARS)}"
            for entry in source_entries
        )
        user_content = template.user.format(
            project_name=project.name,
            project_type=project.project_type.value,
            source_block=_truncate(source_block, MAX_CONTEXT_CHARS),
            question=question,
        )
        return [
            LLMMessage(role="system", content=template.system),
            *history_msgs,
            LLMMessage(role="user", content=user_content),
        ]


def _truncate(text: str, max_chars: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_chars]
