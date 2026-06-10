from __future__ import annotations

import pytest

from features.chat._prompt_loader import load_prompt_template


def test_load_prompt_template_reads_qa_yaml() -> None:
    load_prompt_template.cache_clear()

    template = load_prompt_template()

    assert template.version == "v0.3"
    assert "source_id" in template.description
    assert "{source_block}" in template.user


def test_load_prompt_template_is_cached() -> None:
    load_prompt_template.cache_clear()

    first = load_prompt_template()
    second = load_prompt_template()

    assert first is second


def test_load_prompt_template_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        load_prompt_template("../project_overview.yaml")
