"""Build TeachingUnit values from a graph target and LLM output."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from core.domain.project_graph import NodeType, ProjectGraph, ProjectNode
from core.domain.teaching_unit import (
    TeachingLevel,
    TeachingTarget,
    TeachingUnit,
    TeachingUnitRef,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, TextProvider

from ._prompt_loader import PromptTemplate, load_prompt_template

BUILDER_VERSION = "v0.1.0"
DEFAULT_TEACHING_UNIT_TIMEOUT_SECONDS = 8.0
DEFAULT_TEACHING_UNIT_MAX_TOKENS = 1600
MAX_PREREQUISITES = 8


@dataclass(frozen=True)
class TeachingUnitBuildRequest:
    """Inputs required to build one TeachingUnit."""

    project_id: str
    target_node: ProjectNode
    level: TeachingLevel
    prerequisite_candidates: list[TeachingUnitRef]


class TeachingUnitBuilder:
    """Generate a TeachingUnit for one graph target."""

    def __init__(
        self,
        text_provider: TextProvider,
        prompt_loader: Callable[[str], PromptTemplate] = load_prompt_template,
        timeout: float = DEFAULT_TEACHING_UNIT_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_TEACHING_UNIT_MAX_TOKENS,
    ) -> None:
        self._text_provider = text_provider
        self._prompt_loader = prompt_loader
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def build(
        self,
        request: TeachingUnitBuildRequest,
        graph: ProjectGraph,
    ) -> TeachingUnit:
        """Generate and return a TeachingUnit with code-injected identity fields."""
        target_type = _target_type_from_node(request.target_node)
        unit_id = _teaching_unit_id(request.project_id, target_type, request.target_node.id)
        template = self._prompt_loader("teaching_unit.yaml")
        messages = _build_messages(template, request, graph, target_type)
        response = await asyncio.to_thread(
            self._text_provider.chat,
            messages,
            json_mode=True,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
        payload = _parse_payload(response)
        prerequisites = _resolve_prerequisites(
            request.prerequisite_candidates,
            payload.get("prerequisites_hint"),
            unit_id,
        )
        return TeachingUnit(
            id=unit_id,
            title=_required_str(payload, "title"),
            target=target_type,
            target_id=request.target_node.id,
            level=request.level,
            summary=_required_str(payload, "summary"),
            prerequisites=prerequisites,
            explanation_steps=_required_str_list(payload, "explanation_steps"),
            knowledge_points=_required_str_list(payload, "knowledge_points"),
            source_refs=[request.target_node.source_ref],
            confusion_points=_required_str_list(payload, "confusion_points"),
        )


def _build_messages(
    template: PromptTemplate,
    request: TeachingUnitBuildRequest,
    graph: ProjectGraph,
    target_type: TeachingTarget,
) -> list[LLMMessage]:
    user = template.user.format(
        project_id=request.project_id,
        target_type=target_type,
        target_id=request.target_node.id,
        target_label=request.target_node.label,
        target_metadata=json.dumps(
            request.target_node.metadata,
            ensure_ascii=False,
            sort_keys=True,
        ),
        source_ref=json.dumps(
            asdict(request.target_node.source_ref),
            ensure_ascii=False,
            sort_keys=True,
        ),
        level=request.level,
        graph_entry_points=_format_strings(graph.entry_points),
        graph_execution_flow=_format_strings(graph.execution_flow),
        graph_data_flow=_format_strings(graph.data_flow),
        graph_control_flow=_format_strings(graph.control_flow),
        prerequisite_candidates=json.dumps(
            [asdict(item) for item in request.prerequisite_candidates],
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    return [
        LLMMessage(role="system", content=template.system),
        LLMMessage(role="user", content=user),
    ]


def _parse_payload(response: LLMResponse) -> dict[str, Any]:
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError:
        raise ValueError("teaching_unit_json_invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("teaching_unit_payload_invalid")
    for field_name in (
        "title",
        "summary",
        "explanation_steps",
        "knowledge_points",
        "confusion_points",
    ):
        if field_name not in payload:
            raise ValueError("teaching_unit_field_missing")
    return payload


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("teaching_unit_field_invalid")
    return value.strip()


def _required_str_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        raise ValueError("teaching_unit_field_invalid")
    result = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(result) != len(value):
        raise ValueError("teaching_unit_field_invalid")
    return result


def _resolve_prerequisites(
    candidates: list[TeachingUnitRef],
    prerequisites_hint: object,
    current_unit_id: str,
) -> list[TeachingUnitRef]:
    deduped = _dedupe_without_cycles(candidates, current_unit_id)
    if not isinstance(prerequisites_hint, list):
        return deduped[:MAX_PREREQUISITES]

    allowed = {item.teaching_unit_id: item for item in deduped}
    selected: list[TeachingUnitRef] = []
    seen: set[str] = set()
    for value in prerequisites_hint:
        if not isinstance(value, str):
            continue
        candidate = allowed.get(value)
        if candidate is None or candidate.teaching_unit_id in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.teaching_unit_id)
        if len(selected) >= MAX_PREREQUISITES:
            break
    return selected


def _dedupe_without_cycles(
    candidates: list[TeachingUnitRef],
    current_unit_id: str,
) -> list[TeachingUnitRef]:
    result: list[TeachingUnitRef] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate.project_id, candidate.teaching_unit_id)
        if candidate.teaching_unit_id == current_unit_id or key in seen:
            continue
        result.append(candidate)
        seen.add(key)
        if len(result) >= MAX_PREREQUISITES:
            break
    return result


def _target_type_from_node(node: ProjectNode) -> TeachingTarget:
    mapping: dict[NodeType, TeachingTarget] = {
        NodeType.FILE_M: "file",
        NodeType.FILE_MAT: "file",
        NodeType.FILE_SLX: "model",
        NodeType.FUNCTION: "function",
        NodeType.BLOCK: "block",
        NodeType.SUBSYSTEM: "subsystem",
    }
    try:
        return mapping[node.type]
    except KeyError:
        raise ValueError("unsupported_teaching_unit_target") from None


def _teaching_unit_id(project_id: str, target_type: str, target_id: str) -> str:
    digest = hashlib.sha256(f"{project_id}\x1f{target_type}\x1f{target_id}".encode()).hexdigest()
    return f"tu-{digest[:32]}"


def _format_strings(values: list[str]) -> str:
    if not values:
        return "(none)"
    return "\n".join(f"- {value}" for value in values)
