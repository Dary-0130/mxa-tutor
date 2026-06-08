"""LLM service for generating simulation explanation packs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from core.interfaces.llm_provider import LLMMessage, LLMResponse, TextProvider

from ._evidence_pack import EvidencePack

ClaimType = Literal[
    "project_purpose",
    "reading_order",
    "connection_logic",
    "parameter_reason",
    "modification_advice",
    "observation_point",
    "simulink_caveat",
    "uncertainty_boundary",
]
Confidence = Literal["low", "medium", "high"]

CLAIM_TYPES = set(
    "project_purpose reading_order connection_logic parameter_reason "
    "modification_advice observation_point simulink_caveat uncertainty_boundary".split()
)
CONFIDENCES = {"low", "medium", "high"}

SECTION_HEADINGS: tuple[tuple[str, str], ...] = (
    ("project_purpose", "工程在做什么"),
    ("reading_order", "建议阅读顺序"),
    ("key_subsystems", "关键子系统和模块"),
    ("connection_logic", "信号连接逻辑"),
    ("parameter_reason", "关键参数怎么看"),
    ("modification_advice", "如果要修改先动哪里"),
    ("observation_point", "应该观察哪些位置"),
    ("uncertainty_boundary", "不确定边界"),
)


class ExplanationServiceError(Exception):
    """Raised when the LLM response cannot be parsed into an ExplanationPack."""


@dataclass(frozen=True)
class ExplanationSection:
    """One section from the LLM explanation JSON."""

    section_id: str
    heading: str
    body: str
    claim_ids: list[str]


@dataclass(frozen=True)
class ExplanationClaim:
    """A single evidence-bound explanation claim."""

    claim_id: str
    section: str
    claim_type: ClaimType
    text: str
    evidence_ids: list[str]
    is_inference: bool
    confidence: Confidence


@dataclass(frozen=True)
class ExplanationPack:
    """Structured explanation output before markdown rendering."""

    project_id: str
    title: str
    sections: list[ExplanationSection]
    claims: list[ExplanationClaim]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExplanationGenerationResult:
    """Explanation pack plus LLM accounting."""

    pack: ExplanationPack
    calls: list[LLMResponse]
    failure_count: int


class ExplanationService:
    """Generate an ExplanationPack from EvidencePack and optional overview hint."""

    def __init__(
        self,
        provider: TextProvider,
        *,
        prompt_filename: str = "simulation_explanation_pack.yaml",
        timeout: float = 120.0,
        max_tokens: int | None = 8192,
    ) -> None:
        self._provider = provider
        self._prompt_filename = prompt_filename
        self._timeout = timeout
        self._max_tokens = max_tokens

    def generate(
        self,
        evidence_pack: EvidencePack | dict[str, Any],
        *,
        overview_hint: str | dict[str, Any] | list[Any] | None = None,
        retry_instruction: str | None = None,
    ) -> ExplanationGenerationResult:
        """Call the LLM once and parse the returned structured JSON."""
        messages = self.build_messages(evidence_pack, overview_hint, retry_instruction)
        try:
            response = self._provider.chat(
                messages,
                json_mode=True,
                timeout=self._timeout,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:  # provider translates SDK errors into domain exceptions
            raise ExplanationServiceError("explanation LLM call failed") from exc

        return ExplanationGenerationResult(
            pack=parse_explanation_pack(response.text),
            calls=[response],
            failure_count=0,
        )

    def build_messages(
        self,
        evidence_pack: EvidencePack | dict[str, Any],
        overview_hint: str | dict[str, Any] | list[Any] | None,
        retry_instruction: str | None = None,
    ) -> list[LLMMessage]:
        """Build provider messages without performing the LLM call."""
        system, user_template = load_prompt_template(self._prompt_filename)
        pack_dict = (
            evidence_pack.to_dict() if isinstance(evidence_pack, EvidencePack) else evidence_pack
        )
        user = user_template.format(
            project_id=str(pack_dict.get("project_id", "")),
            project_name=str(pack_dict.get("project_name", "")),
            overview_hint=_format_hint(overview_hint),
            evidence_pack_json=json.dumps(pack_dict, ensure_ascii=False, separators=(",", ":")),
        )
        section_instruction = _section_instruction()
        if retry_instruction:
            user = f"{user}\n\nRetry instruction:\n{retry_instruction.strip()}"
        return [
            LLMMessage("system", system),
            LLMMessage("user", f"{user}\n\n{section_instruction}"),
        ]


def parse_explanation_pack(text: str) -> ExplanationPack:
    """Parse provider text into an ExplanationPack."""
    try:
        data = json.loads(_extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise ExplanationServiceError("LLM response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ExplanationServiceError("LLM response must be a JSON object")

    sections = [_parse_section(item) for item in _required_list(data, "sections")]
    claims = [_parse_claim(item) for item in _required_list(data, "claims")]
    return ExplanationPack(
        project_id=_required_str(data, "project_id"),
        title=_required_str(data, "title"),
        sections=_complete_sections(sections),
        claims=claims,
    )


@lru_cache(maxsize=16)
def load_prompt_template(filename: str) -> tuple[str, str]:
    """Load an explanation prompt template from ``core/prompts``."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("invalid prompt template filename")
    path = Path(__file__).resolve().parents[2] / "core" / "prompts" / filename
    data = _load_prompt_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("prompt template must be a mapping")
    return _required_str(data, "system"), _required_str(data, "user")


def _complete_sections(sections: list[ExplanationSection]) -> list[ExplanationSection]:
    by_id = {section.section_id: section for section in sections}
    return [
        by_id.get(section_id)
        or ExplanationSection(section_id, heading, "当前证据不足,本节不做强断言。", [])
        for section_id, heading in SECTION_HEADINGS
    ]


def _load_prompt_yaml(raw: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        return _parse_simple_prompt_yaml(raw)


def _parse_simple_prompt_yaml(raw: str) -> dict[str, str]:
    data: dict[str, str] = {}
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if ": |" in line:
            key = line.split(":", 1)[0].strip()
            index += 1
            block: list[str] = []
            while index < len(lines) and (lines[index].startswith("  ") or not lines[index]):
                block.append(lines[index][2:] if lines[index].startswith("  ") else "")
                index += 1
            data[key] = "\n".join(block).rstrip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
        index += 1
    return data


def _parse_section(value: Any) -> ExplanationSection:
    if not isinstance(value, dict):
        raise ExplanationServiceError("section must be an object")
    return ExplanationSection(
        section_id=_required_str(value, "section_id"),
        heading=_required_str(value, "heading"),
        body=_required_str(value, "body"),
        claim_ids=[str(item) for item in _required_list(value, "claim_ids")],
    )


def _parse_claim(value: Any) -> ExplanationClaim:
    if not isinstance(value, dict):
        raise ExplanationServiceError("claim must be an object")
    claim_type = _required_str(value, "claim_type")
    confidence = _required_str(value, "confidence")
    if claim_type not in CLAIM_TYPES:
        raise ExplanationServiceError(f"unknown claim_type: {claim_type}")
    if confidence not in CONFIDENCES:
        raise ExplanationServiceError(f"unknown confidence: {confidence}")
    return ExplanationClaim(
        claim_id=_required_str(value, "claim_id"),
        section=_required_str(value, "section"),
        claim_type=claim_type,  # type: ignore[arg-type]
        text=_required_str(value, "text"),
        evidence_ids=[str(item) for item in _required_list(value, "evidence_ids")],
        is_inference=bool(value.get("is_inference")),
        confidence=confidence,  # type: ignore[arg-type]
    )


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExplanationServiceError(f"missing string field: {key}")
    return value.strip()


def _required_list(values: dict[str, Any], key: str) -> list[Any]:
    value = values.get(key)
    if not isinstance(value, list):
        raise ExplanationServiceError(f"missing list field: {key}")
    return value


def _format_hint(value: str | dict[str, Any] | list[Any] | None) -> str:
    if value is None:
        return "无"
    if isinstance(value, str):
        return value.strip() or "无"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _section_instruction() -> str:
    rows = "\n".join(f"- {section_id}: {heading}" for section_id, heading in SECTION_HEADINGS)
    return f"Use exactly these 8 section_id values and headings:\n{rows}\nValidator gate: modification_advice must cite parameter plus measurement/scope; otherwise write uncertainty_boundary."
