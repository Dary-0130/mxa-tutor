from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.domain.source_ref import SourceRef
from features.chat.chat_schemas import ChatLLMResponse, ChatResponse, SourceRefDTO


def test_llm_response_uses_citation_ids_protocol() -> None:
    parsed = ChatLLMResponse.model_validate(
        {
            "answer": "看 SpeedController。",
            "confidence": "high",
            "citation_ids": ["S1"],
            "follow_up_suggestions": ["Ki 呢?"],
        }
    )

    assert parsed.citation_ids == ["S1"]


def test_llm_response_forbids_extra_fields_and_bad_confidence() -> None:
    with pytest.raises(ValidationError):
        ChatLLMResponse.model_validate(
            {
                "answer": "x",
                "confidence": "certain",
                "citation_ids": [],
                "follow_up_suggestions": [],
                "citations": [],
            }
        )


def test_llm_response_limits_citation_ids() -> None:
    with pytest.raises(ValidationError):
        ChatLLMResponse.model_validate(
            {
                "answer": "x",
                "confidence": "low",
                "citation_ids": ["S1", "S2", "S3", "S4", "S5", "S6", "S7"],
                "follow_up_suggestions": [],
            }
        )


def test_source_ref_dto_round_trips_domain() -> None:
    ref = SourceRef(
        file_path="model.slx",
        block_id="b1",
        block_name="Gain",
        parent_subsystem="Loop",
    )

    assert SourceRefDTO.from_domain(ref).to_domain() == ref


def test_chat_response_fallback_reason_literal() -> None:
    response = ChatResponse(
        session_id="s1",
        message_id="m1",
        answer="不确定",
        confidence="low",
        citations=[],
        follow_up_suggestions=[],
        is_fallback=True,
        fallback_reason="no_retrieval_hits",
    )

    assert response.is_fallback is True
