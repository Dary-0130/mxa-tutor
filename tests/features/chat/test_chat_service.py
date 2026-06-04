from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest

from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatGenerationError, ChatSessionNotFoundError, LLMServerError
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.source_ref import SourceRef
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability
from features.chat._chat_persist import enhance_query, normalize_title
from features.chat._retriever import RetrievalHit
from features.chat.chat_service import ChatService


class ProjectStoreFake:
    def __init__(self, project: Project) -> None:
        self.project = project

    async def get_project(self, project_id: str) -> Project:
        assert project_id == self.project.id
        return self.project


class ChatStoreFake:
    def __init__(
        self, session: ChatSession | None = None, history: list[ChatMessage] | None = None
    ):
        self.session = session
        self.history = history or []
        self.created: list[ChatSession] = []
        self.appended: list[ChatMessage] = []
        self.list_calls: list[tuple[int, int]] = []

    async def create_session(self, session: ChatSession) -> None:
        self.session = session
        self.created.append(session)

    async def append_message(self, message: ChatMessage) -> None:
        self.appended.append(message)

    async def get_session(self, session_id: str) -> ChatSession:
        assert self.session is not None
        if self.session.session_id != session_id:
            raise ChatSessionNotFoundError(session_id)
        return self.session

    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        self.list_calls.append((limit, offset))
        return self.history

    async def list_recent_sessions(self, project_id: str, limit: int = 20) -> list[ChatSession]:
        return [self.session] if self.session is not None else []


class RetrieverFake:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    async def search(self, project: Project, query: str, top_k: int = 8) -> list[RetrievalHit]:
        self.queries.append(query)
        return self.hits[:top_k]


class ProviderFake:
    def __init__(self, text: str | None = None, exc: Exception | None = None) -> None:
        self.text = text or json.dumps(
            {
                "answer": "SpeedController 里 Kp 是速度环比例增益。",
                "confidence": "high",
                "citation_ids": ["S1"],
                "follow_up_suggestions": [],
            },
            ensure_ascii=False,
        )
        self.exc = exc
        self.calls = 0
        self.kwargs: dict[str, Any] = {}

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls += 1
        self.kwargs = {"messages": messages, "json_mode": json_mode, "timeout": timeout}
        self.kwargs["max_tokens"] = max_tokens
        if self.exc is not None:
            raise self.exc
        return LLMResponse(self.text, 1, 2, "fake", 3)

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake")


def _project() -> Project:
    return Project(
        id="p1",
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[FileInfo("model.slx", ".slx", 100)],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


def _hit(line_range: tuple[int, int] | None = None) -> RetrievalHit:
    return RetrievalHit(
        source_ref=SourceRef(file_path="model.slx", line_range=line_range),
        score=5,
        snippet="model.slx 里的 SpeedController",
        source_type="file",
    )


def _session(project_id: str = "p1") -> ChatSession:
    now = datetime.utcnow()
    return ChatSession("s1", project_id, now, now, "旧会话")


@pytest.mark.asyncio
async def test_handle_chat_success_uses_last_10_history_and_persists_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [
        ChatMessage(f"m{i}", "s1", "assistant", f"old-{i}", datetime.utcnow(), "[]")
        for i in range(12)
    ]
    chat_store = ChatStoreFake(_session(), history)
    provider = ProviderFake()
    calls: list[object] = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr("features.chat.chat_service.asyncio.to_thread", fake_to_thread)
    service = ChatService(
        ProjectStoreFake(_project()), chat_store, provider, RetrieverFake([_hit()])
    )

    response = await service.handle_chat("p1", "这个 Kp 是什么?", "s1")

    assert response.is_fallback is False
    assert response.citations[0].file_path == "model.slx"
    assert [message.role for message in chat_store.appended] == ["user", "assistant"]
    assert chat_store.list_calls == [(50, 0)]
    assert provider.kwargs["messages"][1].content == "old-2"
    assert calls == [provider.chat]


@pytest.mark.asyncio
async def test_handle_chat_no_retrieval_hits_persists_fallback() -> None:
    chat_store = ChatStoreFake()
    service = ChatService(
        ProjectStoreFake(_project()), chat_store, ProviderFake(), RetrieverFake([])
    )

    response = await service.handle_chat("p1", "老师讲的概念是什么?", None)

    assert response.is_fallback is True
    assert response.fallback_reason == "no_retrieval_hits"
    assert chat_store.created
    assert [message.role for message in chat_store.appended] == ["user", "assistant"]
    assert chat_store.appended[-1].citations_json == "[]"


@pytest.mark.asyncio
async def test_handle_chat_invalid_json_keeps_only_user_message() -> None:
    chat_store = ChatStoreFake(_session())
    service = ChatService(
        ProjectStoreFake(_project()), chat_store, ProviderFake("not json"), RetrieverFake([_hit()])
    )

    with pytest.raises(ChatGenerationError):
        await service.handle_chat("p1", "Kp 是什么?", "s1")

    assert [message.role for message in chat_store.appended] == ["user"]


@pytest.mark.asyncio
async def test_handle_chat_llm_error_keeps_only_user_message() -> None:
    chat_store = ChatStoreFake(_session())
    provider = ProviderFake(exc=LLMServerError("x"))
    service = ChatService(
        ProjectStoreFake(_project()), chat_store, provider, RetrieverFake([_hit()])
    )

    with pytest.raises(LLMServerError):
        await service.handle_chat("p1", "Kp 是什么?", "s1")

    assert [message.role for message in chat_store.appended] == ["user"]


@pytest.mark.asyncio
async def test_handle_chat_rejects_cross_project_session() -> None:
    service = ChatService(
        ProjectStoreFake(_project()),
        ChatStoreFake(_session(project_id="other")),
        ProviderFake(),
        RetrieverFake([_hit()]),
    )

    with pytest.raises(ChatSessionNotFoundError):
        await service.handle_chat("p1", "Kp 是什么?", "s1")


def test_title_and_query_helpers() -> None:
    citation = [{"file_path": "model.slx", "block_name": "SpeedController"}]
    history = [
        ChatMessage(
            "m1", "s1", "assistant", "看这个 block", datetime.utcnow(), json.dumps(citation)
        )
    ]

    assert normalize_title("  第一行\n第二行\t" * 10).startswith("第一行 第二行")
    assert "SpeedController" in enhance_query("那它的 Kp 呢?", history)
