from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from features.overview import _prompt_loader
from features.overview._prompt_loader import load_prompt_template


@pytest.fixture(autouse=True)
def _clear_prompt_cache() -> None:
    load_prompt_template.cache_clear()


def test_load_prompt_template_reads_project_overview_yaml() -> None:
    template = load_prompt_template()

    assert template.version == "v0.2-rc"
    assert template.description
    assert "{file_list}" in template.user
    assert "project_type" in template.system


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
