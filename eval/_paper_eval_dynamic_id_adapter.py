"""Bind fixture user responses to runtime MissingParameterPrompt IDs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from features.paper.paper_user_input_schemas import UserSuppliedResponseModel


@dataclass(frozen=True)
class FixtureUserSuppliedEntry:
    """Fixture row keyed by canonical parameter name, not by prompt_id."""

    fixture_prompt_id: str
    parameter_name: str
    user_supplied_value: str
    user_supplied_unit: str | None
    user_supplied_note: str | None


@dataclass(frozen=True)
class R1aPreFailure:
    """Pre-merge binding failure captured as deterministic rule evidence."""

    code: str
    parameter_name: str | None
    message: str


@dataclass(frozen=True)
class AdapterBinding:
    """One fixture-to-runtime prompt binding."""

    fixture_prompt_id: str
    runtime_prompt_id: str
    parameter_name: str


@dataclass(frozen=True)
class AdapterSuccess:
    """Adapted request payload plus auditable binding details."""

    user_supplied_responses: list[UserSuppliedResponseModel]
    bindings: list[AdapterBinding]


class DynamicIdAdapterError(Exception):
    """Raised when fixture responses cannot be bound to runtime prompts."""

    def __init__(self, failures: list[R1aPreFailure]) -> None:
        super().__init__("dynamic_id_adapter_failed")
        self.failures = failures


def bind_user_responses_by_canonical_name(
    *,
    actual_prompts: list[Any],
    fixture_entries: list[FixtureUserSuppliedEntry],
) -> AdapterSuccess:
    """Inject runtime prompt IDs into fixture user responses.

    The fixture prompt_id is intentionally not used for lookup. It is kept only
    in AdapterBinding so reviewers can audit the historical fixture mapping.
    """

    failures: list[R1aPreFailure] = []
    prompts_by_name: dict[str, Any] = {}
    prompt_duplicates: set[str] = set()

    for prompt in actual_prompts:
        name = _canonical_name(_field(prompt, "parameter_name"))
        if not name:
            failures.append(
                R1aPreFailure(
                    code="actual_prompt_missing_parameter_name",
                    parameter_name=None,
                    message="actual prompt has no parameter_name",
                )
            )
            continue
        if name in prompts_by_name:
            prompt_duplicates.add(name)
        prompts_by_name[name] = prompt

    for name in sorted(prompt_duplicates):
        failures.append(
            R1aPreFailure(
                code="actual_prompt_duplicate_parameter_name",
                parameter_name=name,
                message="multiple runtime prompts share the same canonical name",
            )
        )

    fixture_names: set[str] = set()
    fixture_duplicates: set[str] = set()
    for entry in fixture_entries:
        name = _canonical_name(entry.parameter_name)
        if not name:
            failures.append(
                R1aPreFailure(
                    code="fixture_missing_parameter_name",
                    parameter_name=None,
                    message="fixture response has no parameter_name",
                )
            )
            continue
        if name in fixture_names:
            fixture_duplicates.add(name)
        fixture_names.add(name)

    for name in sorted(fixture_duplicates):
        failures.append(
            R1aPreFailure(
                code="fixture_duplicate_parameter_name",
                parameter_name=name,
                message="multiple fixture responses share the same canonical name",
            )
        )

    responses: list[UserSuppliedResponseModel] = []
    bindings: list[AdapterBinding] = []
    for entry in fixture_entries:
        name = _canonical_name(entry.parameter_name)
        prompt = prompts_by_name.get(name)
        if prompt is None:
            failures.append(
                R1aPreFailure(
                    code="fixture_parameter_not_in_actual_prompts",
                    parameter_name=entry.parameter_name,
                    message="fixture response cannot be bound to a runtime prompt",
                )
            )
            continue
        runtime_prompt_id = _field(prompt, "prompt_id")
        if not isinstance(runtime_prompt_id, str) or not runtime_prompt_id.strip():
            failures.append(
                R1aPreFailure(
                    code="actual_prompt_missing_prompt_id",
                    parameter_name=entry.parameter_name,
                    message="matched runtime prompt has no prompt_id",
                )
            )
            continue
        responses.append(
            UserSuppliedResponseModel(
                prompt_id=runtime_prompt_id,
                parameter_name=_field(prompt, "parameter_name"),
                user_supplied_value=entry.user_supplied_value,
                user_supplied_unit=entry.user_supplied_unit,
                user_supplied_note=entry.user_supplied_note,
            )
        )
        bindings.append(
            AdapterBinding(
                fixture_prompt_id=entry.fixture_prompt_id,
                runtime_prompt_id=runtime_prompt_id,
                parameter_name=_field(prompt, "parameter_name"),
            )
        )

    if failures:
        raise DynamicIdAdapterError(failures)
    return AdapterSuccess(user_supplied_responses=responses, bindings=bindings)


def fixture_entries_from_payload(payload: dict[str, Any]) -> list[FixtureUserSuppliedEntry]:
    """Load fixture user responses without relying on their prompt_id for matching."""

    responses = payload.get("user_supplied_responses")
    if not isinstance(responses, list) or not responses:
        raise DynamicIdAdapterError(
            [
                R1aPreFailure(
                    code="fixture_user_responses_missing",
                    parameter_name=None,
                    message="user_supplied_responses must be a non-empty list",
                )
            ]
        )
    entries: list[FixtureUserSuppliedEntry] = []
    for response in responses:
        if not isinstance(response, dict):
            raise DynamicIdAdapterError(
                [
                    R1aPreFailure(
                        code="fixture_response_not_object",
                        parameter_name=None,
                        message="each fixture response must be an object",
                    )
                ]
            )
        entries.append(
            FixtureUserSuppliedEntry(
                fixture_prompt_id=str(response.get("prompt_id", "")),
                parameter_name=str(response.get("parameter_name", "")),
                user_supplied_value=str(response.get("user_supplied_value", "")),
                user_supplied_unit=response.get("user_supplied_unit"),
                user_supplied_note=response.get("user_supplied_note"),
            )
        )
    return entries


def _canonical_name(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"\s*([()])\s*", r"\1", normalized)
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def _field(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)
