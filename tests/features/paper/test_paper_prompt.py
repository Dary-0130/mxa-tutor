from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from core.interfaces.document_parser import ParsedDocument, ParsedLocatorIndex
from features.paper import _prompt_loader
from features.paper._prompt_builder import build_messages
from features.paper._prompt_loader import load_prompt_template


@pytest.fixture(autouse=True)
def _clear_prompt_cache() -> None:
    load_prompt_template.cache_clear()


def test_load_prompt_template_reads_paper_spec_yaml() -> None:
    template = load_prompt_template()

    assert template.version == "v0.1"
    assert "PaperSpec" in template.description
    assert "{raw_text}" in template.user
    assert "paper_title" in template.system


def test_load_prompt_template_uses_lru_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    first = load_prompt_template()

    def _fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("cache miss")

    monkeypatch.setattr(_prompt_loader.yaml, "safe_load", _fail)

    assert load_prompt_template() is first


@pytest.mark.parametrize("filename", ["../x.yaml", "a/b.yaml", "a\\b.yaml", ""])
def test_load_prompt_template_rejects_path_traversal(filename: str) -> None:
    with pytest.raises(ValueError):
        load_prompt_template(filename)


def test_prompt_template_is_frozen() -> None:
    template = load_prompt_template()

    with pytest.raises(FrozenInstanceError):
        template.version = "v9"


def test_build_messages_includes_locator_whitelist() -> None:
    parsed = ParsedDocument(
        raw_text="paper raw text",
        page_count=1,
        figure_placeholders=[],
        table_placeholders=["TABLE-01"],
        locator_index=ParsedLocatorIndex(
            section_ids=["S1"],
            equation_ids=["EQ-01"],
            figure_ids=["FIG-01"],
        ),
        file_hash="abc",
        extracted_at=datetime.now(UTC),
    )

    messages = build_messages(parsed)

    assert [message.role for message in messages] == ["system", "user"]
    assert "paper raw text" in messages[1].content
    assert "EQ-01" in messages[1].content
    assert "FIG-01" in messages[1].content
