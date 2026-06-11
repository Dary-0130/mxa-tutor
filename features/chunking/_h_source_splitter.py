"""Lightweight header source splitting."""

from __future__ import annotations

from ._c_source_splitter import CSourceSection, _count_tokens, split_c_source

HSourceSection = CSourceSection


def split_h_source(raw_code: str, max_tokens: int = 1500) -> list[HSourceSection]:
    """Return one section for short headers, otherwise split by top-level C sections."""
    token_count = _count_tokens(raw_code)
    if token_count <= max_tokens:
        line_count = max(len(raw_code.splitlines()), 1)
        return [
            HSourceSection(
                index=1,
                title="header_file",
                kind="preprocessor_block",
                line_start=1,
                line_end=line_count,
                code=raw_code,
            )
        ]

    sections = split_c_source(raw_code, max_tokens=max_tokens)
    return sections or [
        HSourceSection(
            index=1,
            title="header_file",
            kind="preprocessor_block",
            line_start=1,
            line_end=max(len(raw_code.splitlines()), 1),
            code=raw_code,
        )
    ]
