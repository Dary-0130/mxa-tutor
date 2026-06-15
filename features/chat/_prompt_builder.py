"""Build LLM messages for chat QA."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Protocol

from core.domain.chat import ChatMessage
from core.domain.project import Project
from core.domain.teaching_unit import TeachingUnit
from core.interfaces.llm_provider import LLMMessage

from ._prompt_loader import load_prompt_template
from ._retriever import SourceEntry

MAX_SNIPPET_CHARS = 300
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_MESSAGES = 10
TEACHING_UNIT_CONTEXT_TIMEOUT_SECONDS = 0.5


class ReadyTeachingUnitProvider(Protocol):
    """Minimal async provider shape; avoids depending on a concrete store type."""

    async def list_ready_by_project(self, project_id: str) -> list[TeachingUnit]:
        """Return ready TeachingUnit values for one project."""
        ...


class ChatPromptBuilder:
    """Prompt builder for the chat service."""

    def __init__(
        self,
        teaching_unit_store: ReadyTeachingUnitProvider | None = None,
        context_timeout_seconds: float = TEACHING_UNIT_CONTEXT_TIMEOUT_SECONDS,
    ) -> None:
        self._teaching_unit_store = teaching_unit_store
        self._context_timeout_seconds = context_timeout_seconds

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
        teaching_units = self._load_ready_teaching_units(project.id)
        source_block = _build_source_block(source_entries, teaching_units)
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

    def _load_ready_teaching_units(self, project_id: str) -> list[TeachingUnit]:
        if self._teaching_unit_store is None:
            return []
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _list_ready_teaching_units, self._teaching_unit_store, project_id
            )
            try:
                return future.result(timeout=self._context_timeout_seconds)
            except TimeoutError:
                return []


def _truncate(text: str, max_chars: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def _list_ready_teaching_units(
    store: ReadyTeachingUnitProvider,
    project_id: str,
) -> list[TeachingUnit]:
    import asyncio

    return asyncio.run(store.list_ready_by_project(project_id))


def _build_source_block(
    source_entries: list[SourceEntry],
    teaching_units: list[TeachingUnit],
) -> str:
    lines: list[str] = []
    for entry in source_entries:
        line = (
            f"[{entry.source_id}] {entry.hit.source_type}: "
            f"{_truncate(entry.snippet, MAX_SNIPPET_CHARS)}"
        )
        summaries = [
            _truncate(unit.summary, MAX_SNIPPET_CHARS)
            for unit in teaching_units
            if _entry_matches_unit(entry, unit)
        ]
        if summaries:
            line = "\n".join(
                [
                    line,
                    *[f"  教学单元补充: {summary}" for summary in dict.fromkeys(summaries)],
                ]
            )
        lines.append(line)
    return "\n".join(lines)


def _entry_matches_unit(entry: SourceEntry, unit: TeachingUnit) -> bool:
    for ref in unit.source_refs:
        if ref.file_path != entry.source_ref.file_path:
            continue
        if unit.target == "block":
            if ref.block_id and entry.source_ref.block_id:
                return ref.block_id == entry.source_ref.block_id
            if ref.block_name and entry.source_ref.block_name:
                return ref.block_name == entry.source_ref.block_name
            continue
        if unit.target == "subsystem":
            if ref.block_name and entry.source_ref.block_name:
                return ref.block_name == entry.source_ref.block_name
            if ref.parent_subsystem and entry.source_ref.parent_subsystem:
                return ref.parent_subsystem == entry.source_ref.parent_subsystem
            continue
        if unit.target in {"file", "function", "model", "project"}:
            return True
    return False
