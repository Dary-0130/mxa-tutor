"""Small helpers for EvidenceBuilder."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Literal

from core.domain.slx_model import SlxBlock, SlxLine, SlxModel
from core.domain.source_ref import SourceRef
from features.overview.overview_schemas import ProjectOverview

from ._evidence_pack import EndpointRef, JsonValue, ParameterRoleGuess, _jsonify
from ._score import classify_block_type, normalize_block_type
from ._score_types import ScoredBlock


def overview_source_ref(overview: ProjectOverview) -> SourceRef:
    if overview.evidence:
        evidence = overview.evidence[0]
        return SourceRef(
            file_path=evidence.file_path,
            line_range=evidence.line_range,
            block_id=evidence.block_id,
        )
    return SourceRef(file_path="<project_overview>")


def block_source_ref(file_path: str, block: SlxBlock) -> SourceRef:
    return SourceRef(
        file_path=file_path,
        block_id=block.block_id,
        block_name=block.name,
        parent_subsystem=block.parent_subsystem,
    )


def endpoint(block: SlxBlock | None, port: str | None = None) -> EndpointRef:
    if block is None:
        return EndpointRef(None, "<unresolved>", None, port=port)
    return EndpointRef(
        block_id=block.block_id,
        block_name=block.name,
        block_type=normalize_block_type(block.block_type),
        port=port,
    )


def score_payload(scored: ScoredBlock) -> dict[str, JsonValue]:
    return {
        "topology_score": round(scored.score.topology_score, 3),
        "rarity_score": round(scored.score.rarity_score, 3),
        "clarity_score": round(scored.score.clarity_score, 3),
        "parameter_score": round(scored.score.parameter_score, 3),
        "keyword_score": round(scored.score.keyword_score, 3),
        "total_score": round(scored.score.total_score, 3),
    }


def block_summary(scored: ScoredBlock) -> str:
    block = scored.block
    location = block.parent_subsystem or "顶层"
    category = scored.e1_category or "未命中 E1 分类"
    return (
        f"Block {block.name}({normalize_block_type(block.block_type)}) 位于 "
        f"{scored.file_path}/{location},D3={','.join(scored.selection_layers)},分类={category}。"
    )


def line_summary(line: SlxLine, source: SlxBlock | None, target: SlxBlock | None) -> str:
    source_name = source.name if source else line.from_block
    target_name = target.name if target else line.to_block
    return f"静态连接线:{source_name}:{line.from_port} -> {target_name}:{line.to_port}。"


def downstream_endpoints(scored: ScoredBlock, *, limit: int) -> list[EndpointRef]:
    downstream: list[EndpointRef] = []
    for line in scored.model.lines:
        if line.from_block != scored.block.block_id:
            continue
        target = next(
            (block for block in scored.model.blocks if block.block_id == line.to_block), None
        )
        if target is not None:
            downstream.append(endpoint(target, str(line.to_port)))
        if len(downstream) >= limit:
            break
    return downstream


def connector_tags(block: SlxBlock) -> list[str]:
    tags: list[str] = []
    for key in ("GotoTag", "Tag", "InputSignals", "OutputSignals"):
        value = block.parameters.get(key)
        if value:
            tags.extend([part.strip() for part in re.split(r"[,;&|]", value) if part.strip()])
    return tags[:12]


def guess_parameter_role(name: str, value: str) -> ParameterRoleGuess:
    text = f"{name} {value}".lower()
    if "init" in text or "initial" in text:
        return "initial_value"
    if any(token in text for token in ("kp", "ki", "kd", "gain", "ratio")):
        return "gain"
    if any(token in text for token in ("sample", "ts", "fixedstep")):
        return "sample_time"
    if any(token in text for token in ("limit", "max", "min", "protection", "saturation")):
        return "protection"
    if any(token in text for token in ("label", "measurement", "output")):
        return "observation"
    if any(token in text for token in ("grid", "base", "nominal", "pref", "qref")):
        return "grid_equivalent"
    if value.strip() in {"", "0", "off", "None"}:
        return "placeholder"
    if any(token in text for token in ("voltage", "current", "power", "frequency", "speed")):
        return "operating_point"
    return "unknown"


def parameter_inference_basis(scored: ScoredBlock, name: str) -> list[str]:
    basis = [f"block_type={normalize_block_type(scored.block.block_type)}"]
    if scored.block.parent_subsystem:
        basis.append(f"parent_subsystem={scored.block.parent_subsystem}")
    if classify_block_type(scored.block.block_type):
        basis.append(f"e1_category={scored.e1_category}")
    if scored.has_domain_keyword:
        basis.append("domain_keyword_hit")
    basis.append(f"parameter_name={name}")
    return basis


def parameter_confidence(name: str) -> Literal["low", "medium", "high"]:
    low = name.lower()
    if any(token in low for token in ("kp", "ki", "kd", "gain", "sample", "ts", "label")):
        return "medium"
    return "low"


def is_measurement(block: SlxBlock) -> bool:
    block_type = normalize_block_type(block.block_type)
    return (
        block_type in {"Display", "To Workspace", "To File", "XY Graph", "RMS", "Fourier", "FFT"}
        or "Measurement" in block_type
    )


def block_index(models: list[SlxModel]) -> dict[tuple[str, str], SlxBlock]:
    return {(model.file_path, block.block_id): block for model in models for block in model.blocks}


def clean_text(text: str, max_chars: int) -> str:
    sanitized = re.sub(r"[A-Za-z]:\\[^\s,;]+", "<local_path>", text)
    sanitized = re.sub(r"/(?:Users|home)/[^\s,;]+", "<local_path>", sanitized)
    sanitized = " ".join(sanitized.split())
    if len(sanitized) <= max_chars:
        return sanitized
    return sanitized[: max(0, max_chars - 3)].rstrip() + "..."


def payload_dict(value: object) -> dict[str, JsonValue]:
    payload = _jsonify(asdict(value))
    return payload if isinstance(payload, dict) else {"value": payload}
