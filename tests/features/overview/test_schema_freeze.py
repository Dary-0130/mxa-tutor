"""TASK-207 ProjectOverview schema freeze tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import BaseModel

from core.domain import project_overview as domain_overview
from features.overview.overview_schemas import (
    BlockEntry,
    EntryFileEntry,
    KeyFileEntry,
    ProjectOverview,
    SimulinkModelEntry,
    SourceRefEntry,
)

EXPECTED_TOP_LEVEL_FIELD_ORDER = (
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

EXPECTED_DOMAIN_TOP_LEVEL_TYPES = {
    "project_title": str,
    "project_type": domain_overview.ProjectTypeValue,
    "one_sentence_summary": str,
    "main_entry_files": list[domain_overview.EntryFileEntry],
    "main_simulink_models": list[domain_overview.SimulinkModelEntry],
    "main_execution_flow": list[str],
    "key_files": list[domain_overview.KeyFileEntry],
    "key_blocks": list[domain_overview.BlockEntry],
    "knowledge_points": list[str],
    "beginner_reading_order": list[str],
    "likely_confusing_points": list[str],
    "evidence": list[domain_overview.SourceRefEntry],
}

EXPECTED_CONSTRAINTS = {
    "project_title": {"min_length": 1, "max_length": 30},
    "one_sentence_summary": {"min_length": 1, "max_length": 80},
    "main_entry_files": {"min_length": 1, "max_length": 3},
    "main_simulink_models": {"max_length": 5},
    "main_execution_flow": {"min_length": 3, "max_length": 10},
    "key_files": {"min_length": 1, "max_length": 8},
    "key_blocks": {"max_length": 10},
    "knowledge_points": {"min_length": 3, "max_length": 6},
    "beginner_reading_order": {"min_length": 3, "max_length": 6},
    "likely_confusing_points": {"min_length": 2, "max_length": 5},
    "evidence": {"min_length": 1},
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

EXPECTED_DOMAIN_SUB_SCHEMAS = {
    domain_overview.EntryFileEntry: {
        "file_path": str,
        "role": str,
    },
    domain_overview.SimulinkModelEntry: {
        "file_path": str,
        "summary": str,
    },
    domain_overview.KeyFileEntry: {
        "file_path": str,
        "why_key": str,
    },
    domain_overview.BlockEntry: {
        "block_name": str,
        "block_type": str,
        "location": str,
        "why_key": str,
    },
    domain_overview.SourceRefEntry: {
        "file_path": str,
        "line_range": tuple[int, int] | None,
        "block_id": str | None,
    },
}

EXPECTED_SCHEMA_DOMAIN_PAIRS = (
    (EntryFileEntry, domain_overview.EntryFileEntry),
    (SimulinkModelEntry, domain_overview.SimulinkModelEntry),
    (KeyFileEntry, domain_overview.KeyFileEntry),
    (BlockEntry, domain_overview.BlockEntry),
    (SourceRefEntry, domain_overview.SourceRefEntry),
)


def _constraint_value(schema_cls: type[BaseModel], field_name: str, constraint_name: str) -> Any:
    field_info = schema_cls.model_fields[field_name]
    for item in field_info.metadata:
        if hasattr(item, constraint_name):
            return getattr(item, constraint_name)
    return None


def _sync_message() -> str:
    return (
        "If intended, follow D1-B three-tier sync: core/domain/project_overview.py, "
        "overview_schemas.py, "
        "tests/features/overview/test_schema_freeze.py, docs/06_OUTPUT_CONTRACTS.md, "
        "schemas/project_overview.schema.json; project_type changes also update "
        "core/prompts/project_overview.yaml and docs/05_EXPLANATION_STYLE_GUIDE.md."
    )


def _domain_field_types(dataclass_type: type[object]) -> dict[str, object]:
    return {field.name: field.type for field in fields(dataclass_type)}


def _valid_payload() -> dict[str, object]:
    return {
        "project_title": "Buck 控制",
        "project_type": "control_system",
        "one_sentence_summary": "这是一个 Buck 电压闭环控制工程。",
        "main_entry_files": [{"file_path": "main.m", "role": "运行入口"}],
        "main_simulink_models": [{"file_path": "model.slx", "summary": "主仿真模型"}],
        "main_execution_flow": ["打开 main.m", "加载参数", "运行 model.slx"],
        "key_files": [
            {"file_path": "main.m", "why_key": "启动仿真"},
            {"file_path": "params.m", "why_key": "定义参数"},
            {"file_path": "model.slx", "why_key": "包含控制回路"},
        ],
        "key_blocks": [
            {
                "block_name": "Gain",
                "block_type": "Gain",
                "location": "model.slx / <root>",
                "why_key": "代表控制增益",
            }
        ],
        "knowledge_points": ["闭环控制", "PWM", "采样"],
        "beginner_reading_order": ["main.m", "params.m", "model.slx"],
        "likely_confusing_points": ["未能确定 load_x", "Gain 的单位要结合参数看"],
        "evidence": [
            {"file_path": "main.m", "line_range": [1, 5]},
            {"file_path": "params.m", "line_range": [1, 3]},
            {"file_path": "model.slx", "block_id": "b1"},
        ],
    }


def test_top_level_field_names_frozen() -> None:
    """Freeze the 12 ProjectOverview top-level field names."""
    actual = set(ProjectOverview.model_fields.keys())
    assert actual == EXPECTED_TOP_LEVEL_FIELDS, (
        "ProjectOverview top-level fields drifted. "
        f"Missing: {EXPECTED_TOP_LEVEL_FIELDS - actual}. "
        f"Unexpected: {actual - EXPECTED_TOP_LEVEL_FIELDS}. "
        f"{_sync_message()}"
    )


def test_top_level_field_order_matches_domain_dataclass() -> None:
    """Freeze field order across domain dataclass and Pydantic wrapper."""
    schema_order = tuple(ProjectOverview.model_fields)
    domain_order = tuple(field.name for field in fields(domain_overview.ProjectOverview))

    assert schema_order == EXPECTED_TOP_LEVEL_FIELD_ORDER
    assert domain_order == schema_order, (
        f"ProjectOverview domain field order drifted. Expected {schema_order}, "
        f"got {domain_order}. {_sync_message()}"
    )


@pytest.mark.parametrize("field_name,expected_type", EXPECTED_TOP_LEVEL_TYPES.items())
def test_top_level_field_types_frozen(field_name: str, expected_type: object) -> None:
    """Freeze non-Literal top-level annotations."""
    actual = ProjectOverview.model_fields[field_name].annotation
    assert actual == expected_type, (
        f"{field_name} annotation drifted. Expected {expected_type!r}, got {actual!r}. "
        f"{_sync_message()}"
    )


@pytest.mark.parametrize("field_name,expected_type", EXPECTED_DOMAIN_TOP_LEVEL_TYPES.items())
def test_domain_top_level_field_types_frozen(
    field_name: str,
    expected_type: object,
) -> None:
    """Freeze domain dataclass top-level annotations."""
    actual = _domain_field_types(domain_overview.ProjectOverview)[field_name]
    assert actual == expected_type, (
        f"domain ProjectOverview.{field_name} annotation drifted. "
        f"Expected {expected_type!r}, got {actual!r}. {_sync_message()}"
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


@pytest.mark.parametrize("domain_cls,expected_fields", EXPECTED_DOMAIN_SUB_SCHEMAS.items())
def test_domain_sub_schema_fields_frozen(
    domain_cls: type[object],
    expected_fields: dict[str, object],
) -> None:
    """Freeze domain sub-dataclass field names, order, and annotations."""
    actual_types = _domain_field_types(domain_cls)
    assert tuple(actual_types) == tuple(expected_fields), (
        f"{domain_cls.__name__} domain field order drifted. "
        f"Expected: {tuple(expected_fields)}. Actual: {tuple(actual_types)}. "
        f"{_sync_message()}"
    )
    assert actual_types == expected_fields


@pytest.mark.parametrize(
    "schema_cls,domain_cls",
    EXPECTED_SCHEMA_DOMAIN_PAIRS,
    ids=[schema_cls.__name__ for schema_cls, _domain_cls in EXPECTED_SCHEMA_DOMAIN_PAIRS],
)
def test_sub_schema_field_order_matches_domain_dataclass(
    schema_cls: type[BaseModel],
    domain_cls: type[object],
) -> None:
    """Freeze sub-schema field order across domain dataclass and wrapper."""
    schema_order = tuple(schema_cls.model_fields)
    domain_order = tuple(field.name for field in fields(domain_cls))

    assert domain_order == schema_order, (
        f"{domain_cls.__name__} field order drifted from {schema_cls.__name__}. "
        f"Expected {schema_order}, got {domain_order}. {_sync_message()}"
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


def test_project_overview_bridge_round_trip() -> None:
    """Freeze ProjectOverview wrapper <-> domain bridge equivalence."""
    model = ProjectOverview.model_validate(_valid_payload())
    domain = model.to_domain()

    assert isinstance(domain, domain_overview.ProjectOverview)
    assert ProjectOverview.from_domain(domain) == model
