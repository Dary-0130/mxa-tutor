"""Deterministic helpers for PaperSpec parameter value conflicts."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import replace

from core.domain.paper_evidence import EvidenceSource
from core.domain.paper_spec import (
    PaperSpec,
    ParameterConflict,
    ParameterConflictObservation,
    ParameterConflictValueOption,
    ParameterEntry,
)

CONFIRMATION_REQUIRED_PLACEHOLDER = "需用户确认"


def parameter_entry_key(entry: ParameterEntry) -> tuple[str, str]:
    """Return the stable conflict key for a parameter table entry."""

    return (entry.name.strip(), entry.symbol.strip())


def detect_parameter_conflicts(parameter_table: list[ParameterEntry]) -> list[ParameterConflict]:
    """Detect cross-document conflicting parameter values.

    This is an exact string comparison. It intentionally does not normalize units,
    parse numbers, prefer primary documents, or infer aliases.
    """

    grouped: OrderedDict[
        tuple[str, str],
        OrderedDict[tuple[str, str], list[ParameterConflictObservation]],
    ] = OrderedDict()
    for entry in parameter_table:
        if entry.source is not EvidenceSource.DOCUMENT_EXTRACTED or entry.document_id is None:
            continue
        key = parameter_entry_key(entry)
        signature = (entry.value.strip(), entry.unit.strip())
        options = grouped.setdefault(key, OrderedDict())
        observations = options.setdefault(signature, [])
        observations.append(
            ParameterConflictObservation(
                document_id=entry.document_id,
                locator=None,
                excerpt=None,
            )
        )

    conflicts: list[ParameterConflict] = []
    for (name, symbol), options in grouped.items():
        document_ids = {
            observation.document_id
            for observations in options.values()
            for observation in observations
        }
        if len(document_ids) < 2 or len(options) < 2:
            continue
        conflicts.append(
            ParameterConflict(
                parameter_name=name,
                parameter_symbol=symbol,
                value_options=[
                    ParameterConflictValueOption(
                        value=value,
                        unit=unit,
                        observations=list(observations),
                    )
                    for (value, unit), observations in options.items()
                ],
            )
        )
    return conflicts


def with_parameter_conflicts(spec: PaperSpec) -> PaperSpec:
    """Return ``spec`` with its deterministic conflict materialized view refreshed."""

    return replace(spec, parameter_conflicts=detect_parameter_conflicts(spec.parameter_table))


def validate_parameter_conflicts_materialized(spec: PaperSpec) -> None:
    """Assert stored conflicts equal the deterministic view of ``parameter_table``."""

    expected = detect_parameter_conflicts(spec.parameter_table)
    if spec.parameter_conflicts != expected:
        raise ValueError("parameter_conflicts_mismatch")


def conflict_parameter_aliases(conflict: ParameterConflict) -> frozenset[str]:
    """Return normalized labels that may refer to this conflicted parameter."""

    raw_aliases = {
        conflict.parameter_name,
        conflict.parameter_symbol,
        f"{conflict.parameter_name} {conflict.parameter_symbol}",
        f"{conflict.parameter_name} ({conflict.parameter_symbol})",
    }
    return frozenset(_normalize_label(alias) for alias in raw_aliases if alias.strip())


def label_hits_parameter_conflict(label: str, conflicts: list[ParameterConflict]) -> bool:
    """Return whether a parameter-ish label names one of the conflicts."""

    normalized = _normalize_label(label)
    tokens = frozenset(_label_tokens(normalized))
    for conflict in conflicts:
        for alias in conflict_parameter_aliases(conflict):
            if normalized == alias or alias in tokens:
                return True
    return False


def parameter_entry_hits_conflict(
    entry: ParameterEntry,
    conflicts: list[ParameterConflict],
) -> bool:
    """Return whether a parameter table entry belongs to a conflict."""

    key = parameter_entry_key(entry)
    return any(
        key == (conflict.parameter_name, conflict.parameter_symbol) for conflict in conflicts
    )


def without_conflicted_parameter_entries(spec: PaperSpec) -> PaperSpec:
    """Remove conflicted parameter rows from prompt-facing parameter input."""

    if not spec.parameter_conflicts:
        return spec
    return replace(
        spec,
        parameter_table=[
            entry
            for entry in spec.parameter_table
            if not parameter_entry_hits_conflict(entry, spec.parameter_conflicts)
        ],
        parameter_conflicts=[],
    )


def conflict_prompt_summary(conflicts: list[ParameterConflict]) -> list[dict[str, object]]:
    """Return a no-value summary for prompt inputs.

    Candidate values are intentionally omitted so LLM roles can abstain without
    seeing a menu of possible single values.
    """

    summaries: list[dict[str, object]] = []
    for conflict in conflicts:
        document_ids: list[str] = []
        seen: set[str] = set()
        for option in conflict.value_options:
            for observation in option.observations:
                if observation.document_id in seen:
                    continue
                seen.add(observation.document_id)
                document_ids.append(observation.document_id)
        summaries.append(
            {
                "parameter_name": conflict.parameter_name,
                "parameter_symbol": conflict.parameter_symbol,
                "document_ids": document_ids,
                "status": CONFIRMATION_REQUIRED_PLACEHOLDER,
            }
        )
    return summaries


def text_contains_conflict_value(
    text: str,
    conflicts: list[ParameterConflict],
    *,
    allow_confirmation_placeholder: bool,
) -> bool:
    """Return whether text leaks a concrete candidate value from a conflict."""

    if allow_confirmation_placeholder and CONFIRMATION_REQUIRED_PLACEHOLDER in text:
        return False
    return any(
        _contains_value_token(text, option.value)
        for conflict in conflicts
        for option in conflict.value_options
    )


def mscript_assigns_conflict_value(text: str, conflicts: list[ParameterConflict]) -> bool:
    """Return whether an M script appears to assign a conflicted parameter value."""

    for conflict in conflicts:
        aliases = conflict_parameter_aliases(conflict)
        for option in conflict.value_options:
            if _assignment_contains_value(text, aliases, option.value):
                return True
    return False


def _normalize_label(value: str) -> str:
    return " ".join(value.casefold().split())


def _label_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", value) if token]


def _contains_value_token(text: str, value: str) -> bool:
    token = value.strip()
    if not token:
        return False
    if re.search(r"[A-Za-z0-9]", token):
        pattern = rf"(?<![A-Za-z0-9_.+-]){re.escape(token)}(?![A-Za-z0-9_.+-])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return token in text


def _assignment_contains_value(text: str, aliases: frozenset[str], value: str) -> bool:
    token = value.strip()
    if not token:
        return False
    for alias in aliases:
        if not alias:
            continue
        alias_pattern = re.escape(alias).replace(r"\ ", r"\s+")
        value_pattern = re.escape(token)
        pattern = rf"(?<![A-Za-z0-9_]){alias_pattern}(?![A-Za-z0-9_])\s*=\s*{value_pattern}"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False
