from __future__ import annotations

import json
import os
import uuid
from typing import Any

import pytest

from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatSessionNotFoundError
from core.domain.project import Project
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability
from features.chat import HybridRetriever, KeywordRetriever, VectorRetriever
from features.chat._prompt_builder import ChatPromptBuilder
from features.chat._retriever import RetrievalHit
from features.chat.chat_service import ChatService
from features.overview.project_graph_builder import ProjectGraphBuilder

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_EMBEDDING_INTEGRATION") != "1",
        reason="set RUN_EMBEDDING_INTEGRATION=1 to load the real embedding model",
    ),
]

_VALID_SOURCE_TYPES = {
    "file",
    "function",
    "block",
    "subsystem",
    "param",
    "overview",
    "graph_entry",
    "unresolved",
}


class ProjectStoreDouble:
    def __init__(self, project: Project) -> None:
        self._project = project

    async def get_project(self, project_id: str) -> Project:
        assert project_id == self._project.id
        return self._project


class ChatStoreDouble:
    def __init__(self) -> None:
        self.session: ChatSession | None = None
        self.messages: list[ChatMessage] = []

    async def create_session(self, session: ChatSession) -> None:
        self.session = session

    async def append_message(self, message: ChatMessage) -> None:
        self.messages.append(message)

    async def get_session(self, session_id: str) -> ChatSession:
        if self.session is None or self.session.session_id != session_id:
            raise ChatSessionNotFoundError(session_id)
        return self.session

    async def list_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatMessage]:
        return self.messages[-limit:]

    async def list_recent_sessions(self, project_id: str, limit: int = 20) -> list[ChatSession]:
        return [self.session] if self.session is not None else []


class ProviderDouble:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "json_mode": json_mode,
                "timeout": timeout,
                "max_tokens": max_tokens,
            }
        )
        return LLMResponse(
            text=json.dumps(
                {
                    "answer": "SpeedController 是速度闭环里的 PID 控制器。",
                    "confidence": "high",
                    "citation_ids": ["S1"],
                    "follow_up_suggestions": [],
                },
                ensure_ascii=False,
            ),
            prompt_tokens=10,
            completion_tokens=20,
            model="provider-double",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="provider-double")


def _signature(hit: RetrievalHit) -> tuple[str, str, str | None, str | None]:
    return (
        hit.source_ref.file_path,
        hit.source_type,
        hit.source_ref.block_name,
        hit.source_ref.parameter_name,
    )


@pytest.mark.asyncio
async def test_real_vector_retriever_returns_stable_hits(real_project_with_chunks) -> None:
    retriever = VectorRetriever(
        embedder=real_project_with_chunks.embedder,
        vector_store=real_project_with_chunks.vector_store,
        min_score=-1.0,
    )

    runs = [
        await retriever.search(real_project_with_chunks.project, "速度控制器", top_k=8)
        for _ in range(3)
    ]

    assert all(runs)
    assert [[_signature(hit) for hit in run] for run in runs] == [
        [_signature(hit) for hit in runs[0]]
    ] * 3
    assert all(hit.source_type in _VALID_SOURCE_TYPES for hit in runs[0])
    assert all(hit.source_ref.file_path for hit in runs[0])


@pytest.mark.asyncio
async def test_real_hybrid_retriever_falls_back_when_chunks_are_absent(
    real_project_without_chunks,
) -> None:
    retriever = HybridRetriever(
        vector=VectorRetriever(
            embedder=real_project_without_chunks.embedder,
            vector_store=real_project_without_chunks.vector_store,
            min_score=-1.0,
        ),
        keyword=KeywordRetriever(graph_provider=ProjectGraphBuilder()),
        vector_store=real_project_without_chunks.vector_store,
        min_chunk_count=1,
    )

    hits = await retriever.search(real_project_without_chunks.project, "速度控制器", top_k=8)

    assert hits
    assert all(hit.source_type in _VALID_SOURCE_TYPES for hit in hits)


@pytest.mark.asyncio
async def test_chat_service_uses_hybrid_retriever_and_returns_citations(
    real_project_with_chunks,
) -> None:
    chat_store = ChatStoreDouble()
    provider = ProviderDouble()
    retriever = HybridRetriever(
        vector=VectorRetriever(
            embedder=real_project_with_chunks.embedder,
            vector_store=real_project_with_chunks.vector_store,
            min_score=-1.0,
        ),
        keyword=KeywordRetriever(graph_provider=ProjectGraphBuilder()),
        vector_store=real_project_with_chunks.vector_store,
        min_chunk_count=1,
    )
    service = ChatService(
        project_store=ProjectStoreDouble(real_project_with_chunks.project),
        chat_store=chat_store,
        text_provider=provider,
        retriever=retriever,
        prompt_builder=ChatPromptBuilder(),
    )

    response = await service.handle_chat(
        real_project_with_chunks.project.id,
        "速度控制器做什么?",
        session_id=None,
    )

    assert response.is_fallback is False
    assert response.citations
    assert provider.calls and provider.calls[0]["json_mode"] is True
    assert chat_store.session is not None
    assert uuid.UUID(response.message_id)
