from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatGenerationError, StoreError
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.source_ref import SourceRef
from features.chat.chat_schemas import ChatResponse, SourceRefDTO


class ChatServiceFake:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[tuple[str, str, str | None]] = []

    async def handle_chat(
        self, project_id: str, question: str, session_id: str | None
    ) -> ChatResponse:
        self.calls.append((project_id, question, session_id))
        if self.exc is not None:
            raise self.exc
        return ChatResponse(
            session_id=session_id or "s-new",
            message_id="m-answer",
            answer="看 main.m。",
            confidence="high",
            citations=[SourceRefDTO.from_domain(SourceRef("main.m", (1, 3)))],
            follow_up_suggestions=[],
        )


class ProjectStoreFake:
    async def get_project(self, project_id: str) -> Project:
        return Project(
            id=project_id,
            name="demo.zip",
            project_type=ProjectType.GENERAL,
            files=[FileInfo("main.m", ".m", 1)],
            slx_models=[],
            m_files=[],
            mat_files=[],
            created_at=datetime.utcnow(),
            file_dependencies={},
        )


class ChatStoreFake:
    def __init__(self, session_project_id: str = "p1", exc: Exception | None = None) -> None:
        now = datetime.utcnow()
        self.session = ChatSession("s1", session_project_id, now, now, "title")
        self.exc = exc

    async def get_session(self, session_id: str) -> ChatSession:
        return self.session

    async def list_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]:
        if self.exc is not None:
            raise self.exc
        return [
            ChatMessage(
                "u1",
                session_id,
                "user",
                "Kp?",
                datetime.utcnow(),
                "[]",
            ),
            ChatMessage(
                "a1",
                session_id,
                "assistant",
                "看 main.m",
                datetime.utcnow(),
                '[{"file_path":"main.m","line_range":[1,3]}]',
            ),
        ]

    async def list_recent_sessions(self, project_id: str, limit: int = 20) -> list[ChatSession]:
        if self.exc is not None:
            raise self.exc
        return [self.session]


@pytest.fixture(autouse=True)
def _chat_state() -> None:
    app.state.project_store = ProjectStoreFake()
    app.state.chat_store = ChatStoreFake()
    app.state.chat_service = ChatServiceFake()


def _install_state(
    service: ChatServiceFake | None = None,
    chat_store: ChatStoreFake | None = None,
) -> ChatServiceFake:
    installed_service = service or ChatServiceFake()
    app.state.project_store = ProjectStoreFake()
    app.state.chat_store = chat_store or ChatStoreFake()
    app.state.chat_service = installed_service
    return installed_service


def test_post_chat_returns_service_response() -> None:
    service = ChatServiceFake()

    with TestClient(app) as client:
        _install_state(service=service)
        response = client.post("/projects/p1/chat", json={"question": "从哪开始看?"})

    assert response.status_code == 200
    assert response.json()["session_id"] == "s-new"
    assert service.calls == [("p1", "从哪开始看?", None)]


def test_post_chat_generation_error_uses_error_handler() -> None:
    with TestClient(app) as client:
        _install_state(service=ChatServiceFake(exc=ChatGenerationError("invalid_json")))
        response = client.post("/projects/p1/chat", json={"question": "Kp?"})

    assert response.status_code == 502
    assert response.json() == {"error": "chat_generation", "message": "回答生成失败,请刷新重试"}


def test_list_sessions_returns_project_scoped_sessions() -> None:
    with TestClient(app) as client:
        _install_state()
        response = client.get("/projects/p1/sessions")

    assert response.status_code == 200
    assert response.json()["project_id"] == "p1"
    assert response.json()["sessions"][0]["session_id"] == "s1"


def test_list_messages_returns_citations_from_json() -> None:
    with TestClient(app) as client:
        _install_state()
        response = client.get("/projects/p1/sessions/s1/messages?limit=50&offset=0")

    assert response.status_code == 200
    assert response.json()["messages"][1]["citations"][0]["file_path"] == "main.m"


def test_list_messages_rejects_cross_project_session_as_404() -> None:
    with TestClient(app) as client:
        _install_state(chat_store=ChatStoreFake(session_project_id="other"))
        response = client.get("/projects/p1/sessions/s1/messages")

    assert response.status_code == 404
    assert response.json()["error"] == "chat_session_not_found"


def test_chat_store_error_uses_error_handler() -> None:
    with TestClient(app) as client:
        _install_state(chat_store=ChatStoreFake(exc=StoreError("sqlite_operation_failed")))
        response = client.get("/projects/p1/sessions")

    assert response.status_code == 500
    assert response.json()["error"] == "store_error"


def test_message_query_validation_is_422_before_store() -> None:
    with TestClient(app) as client:
        _install_state()
        response = client.get("/projects/p1/sessions/s1/messages?limit=201")

    assert response.status_code == 422
