from __future__ import annotations

import json

import pytest

from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.explanation._explanation_service import (
    ExplanationService,
    ExplanationServiceError,
    parse_explanation_pack,
)


def test_explanation_service_builds_prompt_and_parses_json_response() -> None:
    provider = FakeProvider(_response_json())
    service = ExplanationService(provider)

    result = service.generate(_evidence_pack(), overview_hint={"tier": "weak_hint_only"})

    assert result.pack.project_id == "p1"
    assert len(result.pack.sections) == 8
    assert result.pack.claims[0].evidence_ids == ["E001"]
    assert sum(call.prompt_tokens + call.completion_tokens for call in result.calls) == 321
    assert provider.messages is not None
    user_message = provider.messages[1].content
    assert '"tier":"weak_hint_only"' in user_message
    assert '"evidence_id":"E001"' in user_message
    assert "Use exactly these 8 section_id values" in user_message


def test_parse_explanation_pack_accepts_fenced_json() -> None:
    pack = parse_explanation_pack(f"```json\n{_response_json()}\n```")

    assert pack.title == "测试讲解"
    assert [section.section_id for section in pack.sections][:2] == [
        "project_purpose",
        "reading_order",
    ]


def test_parse_explanation_pack_rejects_unknown_claim_type() -> None:
    data = json.loads(_response_json())
    data["claims"][0]["claim_type"] = "made_up"

    with pytest.raises(ExplanationServiceError):
        parse_explanation_pack(json.dumps(data, ensure_ascii=False))


class FakeProvider(TextProvider):
    def __init__(self, text: str) -> None:
        self._text = text
        self.messages: list[LLMMessage] | None = None

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.messages = messages
        assert json_mode is True
        assert timeout == 120.0
        assert max_tokens == 8192
        return LLMResponse(
            text=self._text,
            prompt_tokens=123,
            completion_tokens=198,
            model="fake",
            latency_ms=45,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake", supports_json=True)


def _evidence_pack() -> dict[str, object]:
    return {
        "project_id": "p1",
        "project_name": "demo",
        "evidence": [
            {"evidence_id": "E001", "kind": "slx_block", "summary": "block"},
            {"evidence_id": "E002", "kind": "parameter", "summary": "parameter"},
        ],
    }


def _response_json() -> str:
    sections = [
        {
            "section_id": "project_purpose",
            "heading": "工程在做什么",
            "body": "这个工程用于说明静态结构。",
            "claim_ids": ["C001"],
        }
    ]
    return json.dumps(
        {
            "project_id": "p1",
            "title": "测试讲解",
            "sections": sections,
            "claims": [
                {
                    "claim_id": "C001",
                    "section": "project_purpose",
                    "claim_type": "project_purpose",
                    "text": "该工程包含一个可解释的核心 block。",
                    "evidence_ids": ["E001"],
                    "is_inference": False,
                    "confidence": "high",
                }
            ],
        },
        ensure_ascii=False,
    )
