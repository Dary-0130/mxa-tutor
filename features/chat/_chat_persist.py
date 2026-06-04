"""Persistence-adjacent helpers for chat service."""

from __future__ import annotations

import json
import re
from typing import Final

from core.domain.chat import ChatMessage

from ._retriever import RetrievalHit
from .chat_schemas import ChatAnswer, ChatResponse, FallbackReason, SourceRefDTO

_PRONOUN_PATTERNS: Final[tuple[str, ...]] = (
    "这个",
    "它",
    "上面",
    "那个",
    "刚才",
    "前面",
    "上一个",
    "那段",
    "它的",
)
_CARRYOVER_HISTORY_DEPTH: Final[int] = 2


def normalize_title(question: str) -> str:
    text = re.sub(r"[\n\r\t\v\f]", " ", question)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:40] or "新会话"


def enhance_query(question: str, history: list[ChatMessage]) -> str:
    if not any(pattern in question for pattern in _PRONOUN_PATTERNS):
        return question
    labels: list[str] = []
    assistant_messages = [message for message in reversed(history) if message.role == "assistant"]
    for message in assistant_messages[:_CARRYOVER_HISTORY_DEPTH]:
        labels.extend(_citation_labels(message.citations_json))
    if not labels:
        return question
    suffix = " / ".join(list(dict.fromkeys(labels)))[:200]
    return f"{question} (上下文涉及:{suffix})"[:1200]


def build_e_class_response(
    question: str, retrieval_hits: list[RetrievalHit], fallback_reason: FallbackReason
) -> ChatAnswer:
    _ = question, fallback_reason
    if retrieval_hits:
        labels = "、".join(_short_hit_label(hit) for hit in retrieval_hits[:3])[:80]
        answer = (
            f"根据当前工程文件,我能定位到 {labels} 这些位置,但结构化信息还不足以可靠回答。"
            "建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。"
        )
    else:
        answer = (
            "我在当前工程文件里没有找到与这个问题相关的内容。可能需要运行仿真、查看 .mat 数据,"
            "或换个角度问:这个工程有哪些参数文件?顶层模型是哪个?"
        )
    return ChatAnswer(answer=answer, confidence="low", citations=[], follow_up_suggestions=[])


def to_chat_response(
    session_id: str,
    message_id: str,
    answer: ChatAnswer,
    is_fallback: bool = False,
    fallback_reason: FallbackReason | None = None,
) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        message_id=message_id,
        answer=answer.answer,
        confidence=answer.confidence,
        citations=[SourceRefDTO.from_domain(ref) for ref in answer.citations],
        follow_up_suggestions=answer.follow_up_suggestions,
        is_fallback=is_fallback,
        fallback_reason=fallback_reason,
    )


def _citation_labels(citations_json: str) -> list[str]:
    try:
        values = json.loads(citations_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []
    labels: list[str] = []
    for value in values:
        if isinstance(value, dict):
            labels.extend(
                str(item)
                for item in (
                    value.get("file_path"),
                    value.get("block_name"),
                    value.get("parameter_name"),
                )
                if item
            )
    return labels


def _short_hit_label(hit: RetrievalHit) -> str:
    ref = hit.source_ref
    if ref.block_name:
        parent = ref.parent_subsystem or "<root>"
        return f"{ref.file_path} / {parent} / {ref.block_name}"[:50]
    if ref.parameter_name:
        return f"{ref.file_path} 中的参数 {ref.parameter_name}"[:50]
    return ref.file_path[:50]
