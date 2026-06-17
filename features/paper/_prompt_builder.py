"""Build PaperSpec extraction prompt messages from parsed documents."""

from __future__ import annotations

from core.interfaces.document_parser import FigurePlaceholder, ParsedDocument
from core.interfaces.llm_provider import LLMMessage

from ._prompt_loader import load_prompt_template


def build_messages(parsed: ParsedDocument) -> list[LLMMessage]:
    """Build system/user messages for PaperSpec extraction."""
    template = load_prompt_template()
    user = template.user.format(
        raw_text=parsed.raw_text,
        figure_placeholders=_format_figures(parsed.figure_placeholders),
        table_placeholders=_format_strings(parsed.table_placeholders),
        section_ids=_format_strings(parsed.locator_index.section_ids),
        equation_ids=_format_strings(parsed.locator_index.equation_ids),
        figure_ids=_format_strings(parsed.locator_index.figure_ids),
    )
    return [
        LLMMessage(role="system", content=template.system),
        LLMMessage(role="user", content=user),
    ]


def _format_figures(figures: list[FigurePlaceholder]) -> str:
    if not figures:
        return "(none)"
    return "\n".join(
        "- id={}; caption={}; section={}".format(
            figure.figure_id,
            figure.caption or "(empty)",
            figure.paper_section_id or "(unknown)",
        )
        for figure in figures
    )


def _format_strings(values: list[str]) -> str:
    if not values:
        return "(none)"
    return "\n".join(f"- {value}" for value in values)
