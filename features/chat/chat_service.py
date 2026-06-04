"""Chat service orchestrating coarse RAG and LLM QA."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Final

from loguru import logger
from pydantic import ValidationError

from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatGenerationError, ChatSessionNotFoundError, LLMError
from core.domain.project import Project
from core.interfaces.chat_store import ChatStore
from core.interfaces.llm_provider import LLMResponse, TextProvider
from core.interfaces.project_store import ProjectStore

from ._chat_persist import (
    build_e_class_response,
    enhance_query,
    normalize_title,
    to_chat_response,
)
from ._prompt_builder import ChatPromptBuilder
from ._retriever import RetrievalHit, Retriever, SourceEntry
from .chat_schemas import ChatAnswer, ChatLLMResponse, ChatResponse, FallbackReason

DEFAULT_TOP_K: Final[int] = 8
DEFAULT_TIMEOUT_S: Final[float] = 30.0
DEFAULT_MAX_TOKENS: Final[int] = 1500


class ChatService:
    """Handle chat requests end to end."""

    def __init__(
        self,
        project_store: ProjectStore,
        chat_store: ChatStore,
        text_provider: TextProvider,
        retriever: Retriever,
        prompt_builder: ChatPromptBuilder | None = None,
    ) -> None:
        self._project_store = project_store
        self._chat_store = chat_store
        self._text_provider = text_provider
        self._retriever = retriever
        self._prompt_builder = prompt_builder or ChatPromptBuilder()

    async def handle_chat(
        self,
        project_id: str,
        question: str,
        session_id: str | None,
    ) -> ChatResponse:
        project = await self._project_store.get_project(project_id)
        session = await self._get_or_create_session(project_id, question, session_id)
        history_candidates = await self._chat_store.list_messages(
            session.session_id, limit=50, offset=0
        )
        history = history_candidates[-10:]
        await self._chat_store.append_message(
            ChatMessage(
                message_id=str(uuid.uuid4()),
                session_id=session.session_id,
                role="user",
                content=question,
                created_at=datetime.utcnow(),
                citations_json="[]",
            )
        )
        retrieval_hits = await self._retriever.search(
            project, enhance_query(question, history), top_k=DEFAULT_TOP_K
        )
        if not retrieval_hits:
            return await self._build_and_persist_fallback(
                session, project, question, "no_retrieval_hits", []
            )

        source_entries = self._build_source_entries(retrieval_hits)
        messages = self._prompt_builder.build_messages(project, source_entries, history, question)
        try:
            llm_resp = await asyncio.to_thread(
                self._text_provider.chat,
                messages,
                json_mode=True,
                timeout=DEFAULT_TIMEOUT_S,
                max_tokens=DEFAULT_MAX_TOKENS,
            )
            validated = self._parse_and_validate(llm_resp.text, project, source_entries)
        except LLMError as exc:
            logger.error(
                "ChatService LLM call failed: project_id={} session_id={} exception={}",
                project_id,
                session.session_id,
                type(exc).__name__,
            )
            raise
        except ChatGenerationError as exc:
            logger.error(
                "ChatService output validation failed: project_id={} session_id={} exception={}",
                project_id,
                session.session_id,
                type(exc).__name__,
            )
            raise

        if not validated.citations:
            return await self._build_and_persist_fallback(
                session, project, question, "invalid_or_missing_citations", retrieval_hits
            )

        assistant_msg = await self._append_assistant(session.session_id, validated)
        self._log_metadata_only(session.session_id, llm_resp)
        return to_chat_response(session.session_id, assistant_msg.message_id, validated)

    async def _get_or_create_session(
        self, project_id: str, question: str, session_id: str | None
    ) -> ChatSession:
        if session_id is None:
            now = datetime.utcnow()
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                project_id=project_id,
                created_at=now,
                updated_at=now,
                title=normalize_title(question),
            )
            await self._chat_store.create_session(session)
            return session

        session = await self._chat_store.get_session(session_id)
        if session.project_id != project_id:
            raise ChatSessionNotFoundError(session_id)
        return session

    def _build_source_entries(self, hits: list[RetrievalHit]) -> list[SourceEntry]:
        entries: list[SourceEntry] = []
        for index, hit in enumerate(hits, start=1):
            validation_key = None
            if hit.source_type == "block" and hit.source_ref.block_name:
                validation_key = (
                    hit.source_ref.file_path,
                    hit.source_ref.block_name,
                    hit.block_type or "",
                    hit.source_ref.parent_subsystem or "<root>",
                )
            entries.append(
                SourceEntry(
                    source_id=f"S{index}",
                    hit=hit,
                    source_ref=hit.source_ref,
                    snippet=hit.snippet,
                    validation_key=validation_key,
                )
            )
        return entries

    def _parse_and_validate(
        self, llm_text: str, project: Project, source_entries: list[SourceEntry]
    ) -> ChatAnswer:
        try:
            payload = json.loads(llm_text)
        except json.JSONDecodeError:
            logger.error("ChatService LLM output invalid JSON: project_id={}", project.id)
            raise ChatGenerationError("invalid_json") from None

        try:
            llm_response = ChatLLMResponse.model_validate(payload)
        except ValidationError as exc:
            logger.error(
                "ChatService LLM schema validation failed: project_id={} exception={}",
                project.id,
                type(exc).__name__,
            )
            raise ChatGenerationError("schema_validation_failed") from None

        source_table = {entry.source_id: entry for entry in source_entries}
        if any(source_id not in source_table for source_id in llm_response.citation_ids):
            raise ChatGenerationError("unknown_citation_id") from None

        valid_block_keys = {
            (model.file_path, block.name, block.block_type, block.parent_subsystem or "<root>")
            for model in project.slx_models
            for block in model.blocks
        }
        citations = [
            entry.source_ref
            for entry in (source_table[source_id] for source_id in llm_response.citation_ids)
            if _entry_passes_static_validation(entry, valid_block_keys)
        ]
        return ChatAnswer(
            answer=llm_response.answer,
            confidence=llm_response.confidence,
            citations=citations,
            follow_up_suggestions=llm_response.follow_up_suggestions,
        )

    async def _build_and_persist_fallback(
        self,
        session: ChatSession,
        project: Project,
        question: str,
        fallback_reason: FallbackReason,
        retrieval_hits: list[RetrievalHit],
    ) -> ChatResponse:
        answer = build_e_class_response(question, retrieval_hits, fallback_reason)
        assistant_msg = await self._append_assistant(session.session_id, answer)
        logger.error(
            "ChatService fallback: project_id={} session_id={} reason={} hits_count={}",
            project.id,
            session.session_id,
            fallback_reason,
            len(retrieval_hits),
        )
        return to_chat_response(
            session.session_id,
            assistant_msg.message_id,
            answer,
            is_fallback=True,
            fallback_reason=fallback_reason,
        )

    async def _append_assistant(self, session_id: str, answer: ChatAnswer) -> ChatMessage:
        assistant_msg = ChatMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=answer.answer,
            created_at=datetime.utcnow(),
            citations_json=json.dumps([asdict(citation) for citation in answer.citations]),
        )
        await self._chat_store.append_message(assistant_msg)
        return assistant_msg

    def _log_metadata_only(self, session_id: str, response: LLMResponse) -> None:
        logger.info(
            "ChatService LLM response: session_id={} model={} prompt_tokens={} "
            "completion_tokens={} latency_ms={}",
            session_id,
            response.model,
            response.prompt_tokens,
            response.completion_tokens,
            response.latency_ms,
        )


def _entry_passes_static_validation(
    entry: SourceEntry, valid_block_keys: set[tuple[str, str, str, str]]
) -> bool:
    if entry.validation_key is not None and entry.validation_key not in valid_block_keys:
        return False
    line_range = entry.source_ref.line_range
    return line_range is None or (line_range[0] >= 1 and line_range[1] >= line_range[0])
