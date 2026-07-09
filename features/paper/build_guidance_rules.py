"""Shared semantic rules for paper build guidance generation and validation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol

from core.domain.paper_evidence import EvidenceSource, PaperEvidenceEntry
from core.domain.paper_plan import (
    ConfigurationHint,
    ConnectionHint,
    ModelBuildStep,
    ModelGenerationPlan,
    ParameterMapping,
    ParameterMappingRef,
)
from core.domain.paper_spec import PaperSpec, ParameterEntry

DetailKind = Literal[
    "block_selection",
    "subsystem_internal_structure",
    "connection",
    "parameter_value",
    "configuration",
    "verification",
    "gap_notice",
]
DetailBasis = Literal[
    "document_extracted",
    "engineering_convention",
    "user_confirmation_required",
]
GuidanceContentStatus = Literal["reproducible_candidate", "outline_with_gaps", "outline_only"]
GeneratedGuidanceOverallStatus = Literal[
    "reproducible_candidate_env_unchecked",
    "outline_with_gaps",
    "outline_only",
]

CONVENTION_TEMPLATES: dict[str, tuple[DetailKind, Literal["actionable", "notice_only"]]] = {
    "pi_controller_standard_structure": ("subsystem_internal_structure", "actionable"),
    "pid_controller_standard_structure": ("subsystem_internal_structure", "actionable"),
    "clarke_transform_structure": ("subsystem_internal_structure", "notice_only"),
    "park_transform_structure": ("subsystem_internal_structure", "notice_only"),
}

CONFIRMATION_REASON_TEMPLATES: dict[str, str] = {
    "missing_parameter_value": "Confirm the parameter value for {target}; check the source model or paper table.",
    "library_variant_unresolved": "Confirm the Simulink block variant for {target}; check the local library version.",
    "toolbox_unverified": "Confirm toolbox availability for {target}; check the installed MATLAB products.",
    "solver_unverified": "Confirm the solver choice for {target}; check the reproduction environment.",
    "sample_time_unverified": "Confirm sample-time handling for {target}; check the source model setup.",
    "connection_detail_missing": "Confirm the connection detail for {target}; inspect the source diagram or model.",
    "initial_condition_unverified": "Confirm initial-condition handling for {target}; check the source model setup.",
    "switching_frequency_unverified": "Confirm switching-frequency handling for {target}; check the source model setup.",
    "simulation_time_unverified": "Confirm simulation-time handling for {target}; check the source model setup.",
    "configuration_unverified": "Confirm the configuration detail for {target}; check the source model setup.",
    "document_evidence_unverified": "Confirm {target}; the cited paper evidence could not be verified for this detail.",
    "engineering_decision_unverified": "Confirm the engineering decision for {target}; check the source model setup.",
}

GAP_SYNTHESIS_RULES: dict[
    str, tuple[str, Literal["engineering_convention", "user_confirmation_required"], str]
] = {
    "block": ("missing_support_component", "user_confirmation_required", "blocking"),
    "parameter": ("missing_parameter_value", "user_confirmation_required", "blocking"),
    "connection": ("missing_connection_detail", "user_confirmation_required", "blocking"),
    "configuration": ("missing_configuration_detail", "user_confirmation_required", "blocking"),
    "blocked_detail": ("insufficient_document_evidence", "user_confirmation_required", "blocking"),
}

NON_NUMERIC_ENGINEERING_TERMS = frozenset(
    {
        "anti-windup",
        "antiwindup",
        "限幅",
        "saturation",
        "limiter",
        "discrete",
        "continuous",
        "离散",
        "连续",
        "derivative filter",
        "d filter",
        "微分滤波",
        "scaling",
        "缩放",
        "phase sequence",
        "相序",
        "angle source",
        "角度来源",
        "pwm",
        "spwm",
        "svpwm",
        "igbt",
        "mosfet",
        "器件类型",
        "controller variant",
        "控制器变体",
    }
)
TOOL_ENV_TERMS = frozenset(
    {
        "ode15s",
        "ode45",
        "fixed-step",
        "variable-step",
        "powergui",
        "simscape",
        "simpowersystems",
        "specialized power systems",
        "sample time",
        "solver",
        "toolbox",
    }
)
DISPLAY_BLOCK_TERMS = frozenset(
    {
        "scope",
        "display",
        "dashboard",
        "viewer",
        "plot",
        "to workspace",
        "measurement",
        "meter",
        "voltage measurement",
        "current measurement",
        "voltmeter",
        "ammeter",
    }
)
REAL_BLOCK_ALLOW_TERMS = frozenset(
    {
        "machine",
        "motor",
        "generator",
        "converter",
        "inverter",
        "rectifier",
        "controller",
        "transform",
        "filter",
        "plant",
        "power",
        "source",
        "load",
        "pwm",
        "breaker",
        "fault",
    }
)

NUMBER_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9_.+-])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?\s*"
    r"(?:[A-Za-zµμΩ°/%]+|pu|标幺|秒|毫秒|千瓦|兆瓦|伏|安|欧姆|赫兹)"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
PATH_RE = re.compile(r"\b(?:simulink|simscape|powerlib|sps|ee_lib)[A-Za-z0-9_ ./\\-]+", re.I)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class GuidanceEvidenceCard:
    """Private evidence card exposed to the guidance LLM."""

    handle: str
    summary: str
    evidence: PaperEvidenceEntry
    linked_to_build_steps: bool


@dataclass(frozen=True)
class GuidanceEvidencePool:
    """Resolved guidance evidence pool and construction metadata."""

    cards: list[GuidanceEvidenceCard]
    by_handle: dict[str, GuidanceEvidenceCard]
    has_build_step_linked_evidence: bool
    construction_error_count: int
    parameter_mapping_evidence: dict[tuple[str, str], PaperEvidenceEntry]


class _TruthPool(Protocol):
    @property
    def cards(self) -> list[GuidanceEvidenceCard]: ...

    @property
    def parameter_mapping_evidence(self) -> dict[tuple[str, str], PaperEvidenceEntry]: ...


class GroundingTruthIndex:
    """Canonicalized truth surface for high-risk guidance claims."""

    def __init__(self, truth_texts: list[str]) -> None:
        self._truth = [canonicalize(text) for text in truth_texts if canonicalize(text)]

    @classmethod
    def from_spec_plan(
        cls,
        spec: PaperSpec,
        plan: ModelGenerationPlan,
        pool: _TruthPool,
    ) -> GroundingTruthIndex:
        truth_texts: list[str] = []
        for entry in spec.evidence:
            if entry.source is EvidenceSource.DOCUMENT_EXTRACTED and entry.excerpt:
                truth_texts.append(entry.excerpt)
        for equation in spec.equations:
            truth_texts.append(equation.latex_or_text)
        for figure in spec.figure_locations:
            truth_texts.append(figure.caption)
        for parameter in spec.parameter_table:
            if parameter.source is EvidenceSource.DOCUMENT_EXTRACTED:
                truth_texts.extend(parameter_truth_texts(parameter))
        for card in pool.cards:
            if card.evidence.excerpt:
                truth_texts.append(card.evidence.excerpt)
        for mapping in plan.parameter_mapping:
            if (
                mapping.paper_param_name,
                mapping.model_param_name,
            ) in pool.parameter_mapping_evidence:
                truth_texts.extend(mapping_truth_texts(mapping))
        pool_evidence_keys = {evidence_key(card.evidence) for card in pool.cards}
        for block in plan.block_recommendations:
            if evidence_key(block.paper_reference) in pool_evidence_keys:
                truth_texts.extend([block.block_type, block.purpose])
        return cls(truth_texts)

    @classmethod
    def from_inline_evidence(
        cls,
        evidence: list[PaperEvidenceEntry],
        *,
        spec: PaperSpec | None = None,
    ) -> GroundingTruthIndex:
        truth_texts = [entry.excerpt or "" for entry in evidence]
        if spec is not None:
            evidence_keys = evidence_locator_keys(evidence)
            for entry in spec.evidence:
                if _entry_matches_any_locator(entry, evidence_keys) and entry.excerpt:
                    truth_texts.append(entry.excerpt)
            for equation in spec.equations:
                if (equation.document_id, "equation_id", equation.equation_id) in evidence_keys:
                    truth_texts.append(equation.latex_or_text)
            for figure in spec.figure_locations:
                if (figure.document_id, "figure_id", figure.figure_id) in evidence_keys:
                    truth_texts.append(figure.caption)
            for parameter in spec.parameter_table:
                if parameter.document_id in {entry.document_id for entry in evidence}:
                    truth_texts.extend(parameter_truth_texts(parameter))
        return cls(truth_texts)

    def contains(self, token: str) -> bool:
        canonical = canonicalize(token)
        if not canonical:
            return True
        return any(canonical in truth for truth in self._truth)

    def contains_all(self, tokens: list[str]) -> bool:
        return all(self.contains(token) for token in tokens)


class ControlledGuidanceTargets:
    """Controlled target labels for details and confirmations."""

    def __init__(self, build_steps: list[ModelBuildStep]) -> None:
        self._step_ids = {step.step_id for step in build_steps}
        self._targets: dict[str, str] = {"plan": "the overall model plan"}
        for step in build_steps:
            self._targets[step.step_id] = f"step {step.step_id}"
            for block_ref in step.block_refs:
                self._targets[block_ref.block_ref_id] = f"block {block_ref.block_ref_id}"
            for parameter_ref in step.parameter_refs:
                key = parameter_ref_key(parameter_ref)
                self._targets[key] = f"parameter mapping {parameter_ref.paper_param_name}"
            for index, hint in enumerate(step.configuration_hints, start=1):
                self._targets[configuration_key(step.step_id, hint, index)] = (
                    f"configuration for {step.step_id}"
                )

    def step_exists(self, step_id: str) -> bool:
        return step_id in self._step_ids

    def label(self, step_id: str, target: str | None) -> str:
        if target is not None and target in self._targets:
            return self._targets[target]
        if step_id in self._targets:
            return self._targets[step_id]
        return "the referenced step"


def high_risk_claim_tokens(claim_text: str, step: ModelBuildStep) -> list[str]:
    """Extract high-risk tokens that require grounding truth hits."""

    tokens = high_risk_text_tokens(claim_text)
    for block_ref in step.block_refs:
        _append_if_present(tokens, claim_text, block_ref.block_type)
        if block_ref.library_path:
            _append_if_present(tokens, claim_text, block_ref.library_path)
    for parameter_ref in step.parameter_refs:
        _append_if_present(tokens, claim_text, parameter_ref.paper_param_name)
        _append_if_present(tokens, claim_text, parameter_ref.model_param_name)
    for connection in step.connection_hints:
        _append_if_present(tokens, claim_text, connection.from_block_ref)
        _append_if_present(tokens, claim_text, connection.to_block_ref)
        if connection.from_port:
            _append_if_present(tokens, claim_text, connection.from_port)
        if connection.to_port:
            _append_if_present(tokens, claim_text, connection.to_port)
        if connection.signal_meaning:
            _append_if_present(tokens, claim_text, connection.signal_meaning)
    return unique_nonempty(tokens)


def high_risk_text_tokens(text: str) -> list[str]:
    """Extract high-risk free-text tokens without step-local reference expansion."""

    tokens: list[str] = []
    tokens.extend(match.group(0) for match in NUMBER_UNIT_RE.finditer(text))
    tokens.extend(match.group(0) for match in PATH_RE.finditer(text))
    lowered = text.casefold()
    for term in NON_NUMERIC_ENGINEERING_TERMS | TOOL_ENV_TERMS:
        if term.casefold() in lowered:
            tokens.append(term)
    return unique_nonempty(tokens)


def convention_display_text(code: str, target: str) -> str:
    if code == "pi_controller_standard_structure":
        return (
            f"Use a standard PI structure for {target}: error summing plus proportional and "
            "integral paths."
        )
    if code == "pid_controller_standard_structure":
        return (
            f"Use a standard PID structure for {target}: error summing plus proportional, "
            "integral, and derivative paths."
        )
    if code == "clarke_transform_structure":
        return (
            f"Treat Clarke transform details for {target} as a basic structure notice; confirm "
            "scaling and phase convention separately."
        )
    return (
        f"Treat Park transform details for {target} as a basic structure notice; confirm angle "
        "source and convention separately."
    )


def confirmation_display_text(reason_code: str, target: str, direction_hint: str | None) -> str:
    text = CONFIRMATION_REASON_TEMPLATES[reason_code].format(target=target)
    if direction_hint:
        text = f"{text} Check: {clean_display_text(direction_hint)}."
    return text


def gap_rule_signatures() -> set[tuple[str, str, str]]:
    return {
        (gap_kind, basis, severity) for gap_kind, basis, severity in GAP_SYNTHESIS_RULES.values()
    }


def gap_text(gap_kind: str, step_id: str, object_key: str) -> str:
    if gap_kind == "missing_parameter_value":
        return f"Step {step_id} needs confirmed document support for parameter object {object_key}."
    if gap_kind == "missing_connection_detail":
        return (
            f"Step {step_id} needs confirmed document support for connection object {object_key}."
        )
    if gap_kind == "missing_configuration_detail":
        return f"Step {step_id} needs confirmed document support for configuration object {object_key}."
    if gap_kind == "missing_support_component":
        return f"Step {step_id} needs confirmed document support for block object {object_key}."
    return f"Step {step_id} has a detail that requires confirmation before reproduction."


def unsafe_freeform_text(value: str | None) -> bool:
    if not value:
        return False
    return bool(NUMBER_UNIT_RE.search(value) or PATH_RE.search(value))


def unsafe_direction_hint(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    if NUMBER_UNIT_RE.search(value) or PATH_RE.search(value):
        return True
    return any(term in lowered for term in TOOL_ENV_TERMS)


def unsafe_confirmation_display_text(value: str | None, reason_code: str | None) -> bool:
    if not value:
        return False
    if NUMBER_UNIT_RE.search(value) or PATH_RE.search(value):
        return True
    allowed_terms = _confirmation_reason_allowed_terms(reason_code)
    lowered = value.casefold()
    return any(term in lowered for term in TOOL_ENV_TERMS if term not in allowed_terms)


def clean_display_text(value: str) -> str:
    cleaned = CONTROL_CHAR_RE.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    if not cleaned:
        return "Confirm this step against the source material."
    return cleaned


def clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        key = canonicalize(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def canonicalize(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = normalized.replace("μ", "u").replace("µ", "u").replace("ω", "ohm")
    normalized = normalized.replace("\\omega", "ohm").replace("\\times", "x")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("千瓦", "kw").replace("兆瓦", "mw")
    normalized = normalized.replace("秒", "s").replace("毫秒", "ms")
    normalized = normalized.replace("欧姆", "ohm").replace("赫兹", "hz")
    normalized = normalized.replace("伏", "v").replace("安", "a")
    return normalized


def evidence_key(entry: PaperEvidenceEntry) -> tuple[object, ...]:
    return (
        entry.source,
        entry.document_id,
        entry.paper_section_id,
        entry.equation_id,
        entry.figure_id,
        entry.excerpt,
        entry.missing_param_prompt_id,
        entry.user_action,
        entry.parameter_correction_id,
        entry.correction_param_key,
    )


def evidence_locator_keys(
    evidence: list[PaperEvidenceEntry],
) -> set[tuple[str | None, str, str | None]]:
    keys: set[tuple[str | None, str, str | None]] = set()
    for entry in evidence:
        if entry.paper_section_id is not None:
            keys.add((entry.document_id, "paper_section_id", entry.paper_section_id))
        if entry.equation_id is not None:
            keys.add((entry.document_id, "equation_id", entry.equation_id))
        if entry.figure_id is not None:
            keys.add((entry.document_id, "figure_id", entry.figure_id))
    return keys


def parameter_ref_key(ref: ParameterMappingRef) -> str:
    return f"{ref.paper_param_name}::{ref.model_param_name}"


def configuration_key(step_id: str, hint: ConfigurationHint, index: int) -> str:
    return "::".join(
        [
            "config",
            step_id,
            clean_text(hint.target),
            clean_text(hint.setting_name) or f"#{index}",
        ]
    )


def connection_key(connection: ConnectionHint, index: int) -> str:
    parts = [
        connection.from_block_ref,
        connection.from_port or f"from#{index}",
        connection.to_block_ref,
        connection.to_port or f"to#{index}",
        connection.signal_meaning or f"signal#{index}",
    ]
    return "::".join(clean_text(part) for part in parts)


def parameter_truth_texts(parameter: ParameterEntry) -> list[str]:
    return [
        parameter.name,
        parameter.symbol,
        parameter.value,
        parameter.unit,
        f"{parameter.symbol} {parameter.value} {parameter.unit}",
        f"{parameter.name} {parameter.value} {parameter.unit}",
    ]


def mapping_truth_texts(mapping: ParameterMapping) -> list[str]:
    unit = mapping.unit or ""
    return [
        mapping.paper_param_name,
        mapping.model_param_name,
        mapping.value,
        unit,
        f"{mapping.paper_param_name} {mapping.value} {unit}",
        f"{mapping.model_param_name} {mapping.value} {unit}",
    ]


def _append_if_present(tokens: list[str], text: str, value: str | None) -> None:
    cleaned = clean_text(value)
    if cleaned and canonicalize(cleaned) in canonicalize(text):
        tokens.append(cleaned)


def _entry_matches_any_locator(
    entry: PaperEvidenceEntry,
    keys: set[tuple[str | None, str, str | None]],
) -> bool:
    return (
        (entry.document_id, "paper_section_id", entry.paper_section_id) in keys
        or (entry.document_id, "equation_id", entry.equation_id) in keys
        or (entry.document_id, "figure_id", entry.figure_id) in keys
    )


def _confirmation_reason_allowed_terms(reason_code: str | None) -> set[str]:
    if reason_code == "toolbox_unverified":
        return {"toolbox"}
    if reason_code == "solver_unverified":
        return {"solver"}
    if reason_code == "sample_time_unverified":
        return {"sample time"}
    return set()
