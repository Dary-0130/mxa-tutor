from __future__ import annotations

import pytest

from core.domain.source_ref import SourceRef
from features.chat._chat_persist import _short_hit_label
from features.chat._retriever import RetrievalHit, SourceType


def _make_hit(
    source_type: SourceType, file_path: str, block_name: str | None = None
) -> RetrievalHit:
    return RetrievalHit(
        source_ref=SourceRef(file_path=file_path, block_name=block_name),
        score=1.0,
        snippet="controlled snippet",
        source_type=source_type,
    )


@pytest.mark.parametrize(
    ("source_type", "file_path", "block_name", "expected_label", "forbidden_label"),
    [
        ("overview", "__project_overview__", None, "项目总览", "__project_overview__"),
        ("overview", "some_file.m", None, "some_file.m", "项目总览"),
        ("file", "__project_overview__", None, "__project_overview__", "项目总览"),
        ("block", "model.slx", "Gain", "model.slx / <root> / Gain", "项目总览"),
    ],
)
def test_short_hit_label_sentinel_replacement_four_cases(
    source_type: SourceType,
    file_path: str,
    block_name: str | None,
    expected_label: str,
    forbidden_label: str,
) -> None:
    label = _short_hit_label(_make_hit(source_type, file_path, block_name))

    assert label == expected_label
    assert forbidden_label not in label
