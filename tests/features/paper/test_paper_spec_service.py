from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import features.paper.paper_spec_service as service_module
from core.domain.exceptions import DocumentParseError, LLMTimeoutError, PaperSpecGenerationError
from core.interfaces.document_parser import (
    DocumentParser,
    DocumentParserRouter,
    FigurePlaceholder,
    ParsedDocument,
    ParsedLocatorIndex,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.paper import InMemoryPaperSpecCache, PaperSpecService
from features.paper.paper_spec_service import MAX_PAPER_RAW_TEXT_CHARS


class FakeParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        _ = file_path
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = file_path, timeout_seconds
        raise AssertionError("service tests patch run_in_sandbox")


class FakeTextProvider(TextProvider):
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._payload = payload or _valid_payload()
        self._error = error
        self.calls = 0
        self.messages: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _ = json_mode, timeout, max_tokens
        self.calls += 1
        self.messages.append(messages)
        if self._error is not None:
            raise self._error
        return _response(self._payload)

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake", supports_json=True)


@pytest.mark.asyncio
async def test_extract_generates_and_caches_spec(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parsed = _parsed_document()
    provider = FakeTextProvider()
    _patch_sandbox(monkeypatch, parsed)
    service = _service(provider)

    first = await service.extract(tmp_path / "paper.pdf", "paper-1")
    second = await service.extract(tmp_path / "paper.pdf", "paper-1")

    assert first.paper_title == "电机短路实验报告"
    assert second is first
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_extract_uncached_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parsed = _parsed_document()
    provider = FakeTextProvider()
    _patch_sandbox(monkeypatch, parsed)
    service = _service(provider)

    first = await service.extract_uncached(tmp_path / "paper.pdf", "paper-1")
    second = await service.extract_uncached(tmp_path / "paper.pdf", "paper-1")

    assert first == second
    assert first is not second
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_extract_uses_to_thread_for_route_sandbox_and_llm(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    parsed = _parsed_document()

    async def fake_to_thread(function: object, *args: object, **kwargs: object) -> object:
        calls.append(getattr(function, "__name__", function.__class__.__name__))
        return function(*args, **kwargs)  # type: ignore[misc]

    def fake_run_in_sandbox(parser: object, file_path: Path) -> ParsedDocument:
        _ = parser, file_path
        return parsed

    monkeypatch.setattr(service_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(service_module, "run_in_sandbox", fake_run_in_sandbox)

    await _service(FakeTextProvider()).extract(tmp_path / "paper.pdf", "paper-1")

    assert "route" in calls
    assert "fake_run_in_sandbox" in calls
    assert "chat" in calls


def test_invalid_json_raises_generation_error() -> None:
    service = _service(FakeTextProvider())

    with pytest.raises(PaperSpecGenerationError):
        service._parse_and_validate(_response_text("{"), _parsed_document())


def test_schema_error_raises_generation_error() -> None:
    payload = _valid_payload()
    payload["domain"] = "general"

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


def test_service_rejects_figure_when_parser_found_none() -> None:
    payload = _valid_payload()
    payload["figure_locations"] = [
        {"figure_id": "FIG-01", "caption": "model", "paper_section_id": "S1"}
    ]

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


def test_service_rejects_figure_id_outside_whitelist() -> None:
    payload = _valid_payload()
    payload["figure_locations"] = [
        {"figure_id": "FIG-99", "caption": "model", "paper_section_id": "S1"}
    ]
    parsed = _parsed_document(figures=[FigurePlaceholder("FIG-01", "model", "S1")])

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), parsed)


def test_service_rejects_evidence_locator_outside_whitelist() -> None:
    payload = _valid_payload()
    payload["evidence"][0]["paper_section_id"] = "S9"

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


def test_service_rejects_equation_id_outside_whitelist() -> None:
    payload = _valid_payload()
    payload["equations"][0]["equation_id"] = "EQ-99"

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


def test_paper_spec_service_rejects_user_supplied_parameter_in_task501() -> None:
    payload = _valid_payload()
    payload["parameter_table"][0]["source"] = "user_supplied"

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


def test_paper_spec_service_rejects_user_supplied_evidence_in_task501() -> None:
    payload = _valid_payload()
    payload["evidence"] = [
        {
            "source": "user_supplied",
            "paper_section_id": None,
            "equation_id": None,
            "figure_id": None,
            "excerpt": None,
            "missing_param_prompt_id": "MISS-1",
        }
    ]

    with pytest.raises(PaperSpecGenerationError):
        _service(FakeTextProvider())._parse_and_validate(_response(payload), _parsed_document())


@pytest.mark.asyncio
async def test_service_rejects_document_text_over_v0_1_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    parsed = _parsed_document(raw_text="x" * (MAX_PAPER_RAW_TEXT_CHARS + 1))
    provider = FakeTextProvider()
    _patch_sandbox(monkeypatch, parsed)

    with pytest.raises(DocumentParseError):
        await _service(provider).extract(tmp_path / "paper.pdf", "paper-1")

    assert provider.calls == 0


@pytest.mark.asyncio
async def test_llm_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_sandbox(monkeypatch, _parsed_document())
    provider = FakeTextProvider(error=LLMTimeoutError("timeout"))

    with pytest.raises(LLMTimeoutError):
        await _service(provider).extract(tmp_path / "paper.pdf", "paper-1")


def _service(provider: FakeTextProvider) -> PaperSpecService:
    return PaperSpecService(
        cache=InMemoryPaperSpecCache(),
        text_provider=provider,
        document_parser_router=DocumentParserRouter([FakeParser()]),
    )


def _patch_sandbox(monkeypatch: pytest.MonkeyPatch, parsed: ParsedDocument) -> None:
    def fake_run_in_sandbox(parser: object, file_path: Path) -> ParsedDocument:
        _ = parser, file_path
        return parsed

    monkeypatch.setattr(service_module, "run_in_sandbox", fake_run_in_sandbox)


def _parsed_document(
    raw_text: str = "short circuit report H = 3.5",
    figures: list[FigurePlaceholder] | None = None,
) -> ParsedDocument:
    figure_ids = [figure.figure_id for figure in figures or []]
    return ParsedDocument(
        raw_text=raw_text,
        page_count=1,
        figure_placeholders=figures or [],
        table_placeholders=[],
        locator_index=ParsedLocatorIndex(
            section_ids=["S1", "S2"],
            equation_ids=["EQ-01"],
            figure_ids=figure_ids,
        ),
        file_hash="abc",
        extracted_at=datetime.now(UTC),
    )


def _valid_payload() -> dict[str, Any]:
    return {
        "paper_title": "电机短路实验报告",
        "paper_type": "report",
        "domain": "motor_control",
        "abstract": "报告描述同步电机短路实验的参数和公式。",
        "equations": [
            {
                "equation_id": "EQ-01",
                "latex_or_text": "H = 3.5",
                "paper_section_id": "S1",
            }
        ],
        "parameter_table": [
            {
                "name": "惯性常数",
                "symbol": "H",
                "value": "3.5",
                "unit": "s",
                "source": "document_extracted",
            }
        ],
        "figure_locations": [],
        "pseudocode_blocks": [],
        "evidence": [
            {
                "source": "document_extracted",
                "paper_section_id": "S1",
                "equation_id": None,
                "figure_id": None,
                "excerpt": "报告给出了惯性常数和短路实验公式。",
                "missing_param_prompt_id": None,
            }
        ],
    }


def _response(payload: dict[str, Any]) -> LLMResponse:
    return _response_text(json.dumps(copy.deepcopy(payload), ensure_ascii=False))


def _response_text(text: str) -> LLMResponse:
    return LLMResponse(text=text, prompt_tokens=1, completion_tokens=1, model="fake", latency_ms=1)
