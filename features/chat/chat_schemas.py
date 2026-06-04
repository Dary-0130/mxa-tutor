"""Schemas for chat API and LLM response validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.domain.source_ref import SourceRef

Confidence = Literal["high", "medium", "low"]
FallbackReason = Literal[
    "no_retrieval_hits",
    "invalid_or_missing_citations",
    "low_relevance",
    "out_of_scope",
]


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRefDTO(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    line_range: tuple[int, int] | None = None
    block_id: str | None = None
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None

    @classmethod
    def from_domain(cls, ref: SourceRef) -> SourceRefDTO:
        return cls(
            file_path=ref.file_path,
            line_range=ref.line_range,
            block_id=ref.block_id,
            block_name=ref.block_name,
            parent_subsystem=ref.parent_subsystem,
            parameter_name=ref.parameter_name,
        )

    def to_domain(self) -> SourceRef:
        return SourceRef(
            file_path=self.file_path,
            line_range=self.line_range,
            block_id=self.block_id,
            block_name=self.block_name,
            parent_subsystem=self.parent_subsystem,
            parameter_name=self.parameter_name,
        )


class ChatLLMResponse(_StrictBaseModel):
    """Raw JSON schema returned by the LLM."""

    answer: str = Field(min_length=1, max_length=1500)
    confidence: Confidence
    citation_ids: list[str] = Field(default_factory=list, max_length=6)
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)


@dataclass
class ChatAnswer:
    """Validated internal answer with expanded citations."""

    answer: str
    confidence: Confidence
    citations: list[SourceRef]
    follow_up_suggestions: list[str]


class ChatRequest(_StrictBaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None


class ChatResponse(_StrictBaseModel):
    session_id: str
    message_id: str
    answer: str
    confidence: Confidence
    citations: list[SourceRefDTO]
    follow_up_suggestions: list[str]
    is_fallback: bool = False
    fallback_reason: FallbackReason | None = None


class SessionDTO(_StrictBaseModel):
    session_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionsResponse(_StrictBaseModel):
    project_id: str
    sessions: list[SessionDTO]


class MessageDTO(_StrictBaseModel):
    message_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    citations: list[SourceRefDTO]


class ChatMessagesResponse(_StrictBaseModel):
    session_id: str
    messages: list[MessageDTO]
