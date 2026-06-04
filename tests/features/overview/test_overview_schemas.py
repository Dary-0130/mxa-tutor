from __future__ import annotations

import pytest
from pydantic import ValidationError

from features.overview.overview_schemas import BlockEntry, ProjectOverview


def _payload() -> dict[str, object]:
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


def test_project_overview_accepts_valid_12_field_payload() -> None:
    overview = ProjectOverview.model_validate(_payload())

    assert overview.project_title == "Buck 控制"
    assert overview.evidence[0].line_range == (1, 5)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_type", "unknown"),
        ("project_title", ""),
        ("main_entry_files", []),
        ("main_execution_flow", ["one", "two"]),
        ("key_files", [{"file_path": "main.m", "why_key": "only one"}]),
        ("knowledge_points", ["one", "two"]),
        ("likely_confusing_points", ["one"]),
    ],
)
def test_project_overview_enforces_literal_and_length_bounds(
    field: str,
    value: object,
) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ProjectOverview.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "entry"),
    [
        ("main_entry_files", {"file_path": "main.m"}),
        ("main_simulink_models", {"file_path": "model.slx"}),
        ("key_files", {"file_path": "main.m"}),
    ],
)
def test_file_entry_variants_require_their_specific_field(
    field: str,
    entry: dict[str, str],
) -> None:
    payload = _payload()
    payload[field] = [entry]

    with pytest.raises(ValidationError):
        ProjectOverview.model_validate(payload)


def test_project_overview_forbids_extra_fields() -> None:
    payload = _payload()
    payload["extra"] = "nope"

    with pytest.raises(ValidationError):
        ProjectOverview.model_validate(payload)


def test_nested_entries_forbid_extra_fields() -> None:
    payload = _payload()
    payload["main_entry_files"] = [
        {"file_path": "main.m", "role": "运行入口", "summary": "extra"}
    ]

    with pytest.raises(ValidationError):
        ProjectOverview.model_validate(payload)


def test_block_entry_location_accepts_any_nonempty_string() -> None:
    entry = BlockEntry.model_validate(
        {
            "block_name": "Gain",
            "block_type": "Gain",
            "location": "not service-validated here",
            "why_key": "important",
        }
    )

    assert entry.location == "not service-validated here"
