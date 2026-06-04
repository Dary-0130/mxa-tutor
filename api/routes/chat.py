"""Chat HTTP endpoints."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_chat_service, get_chat_store, get_project_store
from core.domain.chat import ChatMessage, ChatSession
from core.domain.exceptions import ChatSessionNotFoundError
from core.interfaces.chat_store import ChatStore
from core.interfaces.project_store import ProjectStore
from features.chat.chat_schemas import (
    ChatMessagesResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionsResponse,
    MessageDTO,
    SessionDTO,
    SourceRefDTO,
)
from features.chat.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/projects/{project_id}/chat", response_model=ChatResponse)
async def post_chat(
    project_id: str,
    body: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """Answer a project-scoped chat question."""
    return await chat_service.handle_chat(project_id, body.question, body.session_id)


@router.get("/projects/{project_id}/sessions", response_model=ChatSessionsResponse)
async def list_sessions(
    project_id: str,
    project_store: Annotated[ProjectStore, Depends(get_project_store)],
    chat_store: Annotated[ChatStore, Depends(get_chat_store)],
) -> ChatSessionsResponse:
    """List recent sessions for a project."""
    await project_store.get_project(project_id)
    sessions = await chat_store.list_recent_sessions(project_id, limit=20)
    return ChatSessionsResponse(
        project_id=project_id,
        sessions=[_session_to_dto(session) for session in sessions],
    )


@router.get(
    "/projects/{project_id}/sessions/{session_id}/messages",
    response_model=ChatMessagesResponse,
)
async def list_messages(
    project_id: str,
    session_id: str,
    project_store: Annotated[ProjectStore, Depends(get_project_store)],
    chat_store: Annotated[ChatStore, Depends(get_chat_store)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatMessagesResponse:
    """List messages in a project-scoped session."""
    await project_store.get_project(project_id)
    session = await chat_store.get_session(session_id)
    if session.project_id != project_id:
        raise ChatSessionNotFoundError(session_id)
    messages = await chat_store.list_messages(session_id, limit=limit, offset=offset)
    return ChatMessagesResponse(
        session_id=session_id,
        messages=[_message_to_dto(message) for message in messages],
    )


def _session_to_dto(session: ChatSession) -> SessionDTO:
    return SessionDTO(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_to_dto(message: ChatMessage) -> MessageDTO:
    return MessageDTO(
        message_id=message.message_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=_citations_from_json(message.citations_json),
    )


def _citations_from_json(citations_json: str) -> list[SourceRefDTO]:
    try:
        values = json.loads(citations_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []
    return [SourceRefDTO.model_validate(value) for value in values if isinstance(value, dict)]
