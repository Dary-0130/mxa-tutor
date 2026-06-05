"""TASK-207 ProjectOverview schema freeze tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import BaseModel

from features.overview.overview_schemas import (
    BlockEntry,
    EntryFileEntry,
    KeyFileEntry,
    ProjectOverview,
    SimulinkModelEntry,
    SourceRefEntry,
)

EXPECTED_TOP_LEVEL_FIELDS = {
    "project_title",
    "project_type",
    "one_sentence_summary",
    "main_entry_files",
    "main_simulink_models",
    "main_execution_flow",
    "key_files",
    "key_blocks",
    "knowledge_points",
    "beginner_reading_order",
    "likely_confusing_points",
    "evidence",
}

EXPECTED_TOP_LEVEL_TYPES = {
    "project_title": str,
    "one_sentence_summary": str,
    "main_entry_files": list[EntryFileEntry],
    "main_simulink_models": list[SimulinkModelEntry],
    "main_execution_flow": list[str],
    "key_files": list[KeyFileEntry],
    "key_blocks": list[BlockEntry],
    "knowledge_points": list[str],
    "beginner_reading_order": list[str],
    "likely_confusing_points": list[str],
    "evidence": list[SourceRefEntry],
}

EXPECTED_CONSTRAINTS = {
    "project_title": {"min_length": 1, "max_length": 30},
    "one_sentence_summary": {"min_length": 1, "max_length": 80},
    "main_entry_files": {"min_length": 1, "max_length": 3},
    "main_simulink_models": {"max_length": 5},
    "main_execution_flow": {"min_length": 3, "max_length": 7},
    "key_files": {"min_length": 3, "max_length": 8},
    "key_blocks": {"max_length": 10},
    "knowledge_points": {"min_length": 3, "max_length": 6},
    "beginner_reading_order": {"min_length": 3, "max_length": 6},
    "likely_confusing_points": {"min_length": 2, "max_length": 5},
    "evidence": {"min_length": 3},
}

EXPECTED_PROJECT_TYPES = (
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
)

EXPECTED_SUB_SCHEMAS = {
    EntryFileEntry: {
        "file_path": (str, {"min_length": 1}),
        "role": (str, {"min_length": 1, "max_length": 100}),
    },
    SimulinkModelEntry: {
        "file_path": (str, {"min_length": 1}),
        "summary": (str, {"min_length": 1, "max_length": 200}),
    },
    KeyFileEntry: {
        "file_path": (str, {"min_length": 1}),
        "why_key": (str, {"min_length": 1, "max_length": 200}),
    },
    BlockEntry: {
        "block_name": (str, {"min_length": 1}),
        "block_type": (str, {"min_length": 1}),
        "location": (str, {"min_length": 1}),
        "why_key": (str, {"min_length": 1, "max_length": 200}),
    },
    SourceRefEntry: {
        "file_path": (str, {"min_length": 1}),
        "line_range": (tuple[int, int] | None, {}),
        "block_id": (str | None, {}),
    },
}


def _constraint_value(schema_cls: type[BaseModel], field_name: str, constraint_name: str) -> Any:
    field_info = schema_cls.model_fields[field_name]
    for item in field_info.metadata:
        if hasattr(item, constraint_name):
            return getattr(item, constraint_name)
    return None


def _sync_message() -> str:
    return (
        "If intended, follow D5 two-tier sync: overview_schemas.py, "
        "tests/features/overview/test_schema_freeze.py, docs/06_OUTPUT_CONTRACTS.md, "
        "schemas/project_overview.schema.json; project_type changes also update "
        "core/prompts/project_overview.yaml and docs/05_EXPLANATION_STYLE_GUIDE.md."
    )


def test_top_level_field_names_frozen() -> None:
    """Freeze the 12 ProjectOverview top-level field names."""
    actual = set(ProjectOverview.model_fields.keys())
    assert actual == EXPECTED_TOP_LEVEL_FIELDS, (
        "ProjectOverview top-level fields drifted. "
        f"Missing: {EXPECTED_TOP_LEVEL_FIELDS - actual}. "
        f"Unexpected: {actual - EXPECTED_TOP_LEVEL_FIELDS}. "
        f"{_sync_message()}"
    )


@pytest.mark.parametrize("field_name,expected_type", EXPECTED_TOP_LEVEL_TYPES.items())
def test_top_level_field_types_frozen(field_name: str, expected_type: object) -> None:
    """Freeze non-Literal top-level annotations."""
    actual = ProjectOverview.model_fields[field_name].annotation
    assert actual == expected_type, (
        f"{field_name} annotation drifted. Expected {expected_type!r}, got {actual!r}. "
        f"{_sync_message()}"
    )


@pytest.mark.parametrize("field_name,expected", EXPECTED_CONSTRAINTS.items())
def test_top_level_field_constraints_frozen(field_name: str, expected: dict[str, int]) -> None:
    """Freeze top-level min_length / max_length constraints."""
    for constraint_name, expected_value in expected.items():
        actual = _constraint_value(ProjectOverview, field_name, constraint_name)
        assert actual == expected_value, (
            f"{field_name}.{constraint_name}: expected {expected_value}, got {actual}. "
            f"{_sync_message()}"
        )


def test_project_type_literal_frozen() -> None:
    """Freeze the ordered ProjectTypeValue Literal[7] contract."""
    actual = get_args(ProjectOverview.model_fields["project_type"].annotation)
    assert actual == EXPECTED_PROJECT_TYPES, (
        f"project_type Literal drifted. Expected {EXPECTED_PROJECT_TYPES}, got {actual}. "
        f"{_sync_message()}"
    )


@pytest.mark.parametrize(
    "schema_cls,expected_fields",
    EXPECTED_SUB_SCHEMAS.items(),
    ids=[schema_cls.__name__ for schema_cls in EXPECTED_SUB_SCHEMAS],
)
def test_sub_schema_fields_frozen(
    schema_cls: type[BaseModel],
    expected_fields: dict[str, tuple[object, dict[str, int]]],
) -> None:
    """Freeze sub-schema field names, annotations, and constraints."""
    actual_fields = set(schema_cls.model_fields.keys())
    expected_field_names = set(expected_fields.keys())
    assert actual_fields == expected_field_names, (
        f"{schema_cls.__name__} fields drifted. "
        f"Expected: {expected_field_names}. Actual: {actual_fields}. {_sync_message()}"
    )

    for field_name, (expected_type, expected_constraints) in expected_fields.items():
        field_info = schema_cls.model_fields[field_name]
        assert field_info.annotation == expected_type, (
            f"{schema_cls.__name__}.{field_name} annotation drifted. "
            f"Expected {expected_type!r}, got {field_info.annotation!r}. {_sync_message()}"
        )
        for constraint_name, expected_value in expected_constraints.items():
            actual = _constraint_value(schema_cls, field_name, constraint_name)
            assert actual == expected_value, (
                f"{schema_cls.__name__}.{field_name}.{constraint_name}: "
                f"expected {expected_value}, got {actual}. {_sync_message()}"
            )


@pytest.mark.parametrize(
    "schema_cls",
    [
        ProjectOverview,
        EntryFileEntry,
        SimulinkModelEntry,
        KeyFileEntry,
        BlockEntry,
        SourceRefEntry,
    ],
    ids=lambda item: item.__name__,
)
def test_extra_forbid_at_all_levels(schema_cls: type[BaseModel]) -> None:
    """Freeze extra='forbid' at every schema level."""
    assert (
        schema_cls.model_config.get("extra") == "forbid"
    ), f"{schema_cls.__name__} lost extra='forbid'. {_sync_message()}"


def test_schema_exported_json_parseable(tmp_path: Path) -> None:
    """Export script runs in tmp_path and produces valid JSON without repo side effects."""
    project_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    result = subprocess.run(
        [sys.executable, "-m", "scripts.export_overview_schema"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert result.returncode == 0, f"export script failed: stderr={result.stderr}"
    schema_path = tmp_path / "schemas" / "project_overview.schema.json"
    assert schema_path.exists(), f"expected output not found: {schema_path}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "properties" in schema or "$ref" in schema, "exported JSON missing schema structure"
