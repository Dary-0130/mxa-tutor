from __future__ import annotations

import pytest

from eval._paper_eval_dynamic_id_adapter import (
    DynamicIdAdapterError,
    FixtureUserSuppliedEntry,
    bind_user_responses_by_canonical_name,
)


def test_binds_fixture_responses_by_canonical_name_and_injects_runtime_ids() -> None:
    result = bind_user_responses_by_canonical_name(
        actual_prompts=[
            {"prompt_id": "MISS-017", "parameter_name": "同步发电机惯性时间常数 H"},
            {"prompt_id": "MISS-042", "parameter_name": "电机初相角 α0"},
        ],
        fixture_entries=[
            FixtureUserSuppliedEntry(
                fixture_prompt_id="MISS-001",
                parameter_name="同步发电机惯性时间常数 H",
                user_supplied_value="3.5",
                user_supplied_unit="s",
                user_supplied_note="from fixture",
            ),
            FixtureUserSuppliedEntry(
                fixture_prompt_id="MISS-006",
                parameter_name="电机初相角 α0",
                user_supplied_value="1.5708",
                user_supplied_unit="rad",
                user_supplied_note=None,
            ),
        ],
    )

    assert [response.prompt_id for response in result.user_supplied_responses] == [
        "MISS-017",
        "MISS-042",
    ]
    assert [binding.fixture_prompt_id for binding in result.bindings] == [
        "MISS-001",
        "MISS-006",
    ]


def test_rejects_unmatched_fixture_name() -> None:
    with pytest.raises(DynamicIdAdapterError) as exc_info:
        bind_user_responses_by_canonical_name(
            actual_prompts=[{"prompt_id": "MISS-001", "parameter_name": "H"}],
            fixture_entries=[
                FixtureUserSuppliedEntry(
                    fixture_prompt_id="MISS-001",
                    parameter_name="F",
                    user_supplied_value="0",
                    user_supplied_unit="pu",
                    user_supplied_note=None,
                )
            ],
        )

    assert exc_info.value.failures[0].code == "fixture_parameter_not_in_actual_prompts"


def test_canonical_name_normalizes_width_and_separator_spacing() -> None:
    result = bind_user_responses_by_canonical_name(
        actual_prompts=[
            {"prompt_id": "MISS-003", "parameter_name": "变压器变比"},
            {"prompt_id": "MISS-005", "parameter_name": "变压器接线方式"},
        ],
        fixture_entries=[
            FixtureUserSuppliedEntry(
                fixture_prompt_id="MISS-003",
                parameter_name="变压器变比(原边/副边电压比)",
                user_supplied_value="13.8 / 230",
                user_supplied_unit="kV / kV",
                user_supplied_note=None,
            ),
            FixtureUserSuppliedEntry(
                fixture_prompt_id="MISS-005",
                parameter_name="变压器接线方式(原边 / 副边连接组别)",
                user_supplied_value="Yn / d11",
                user_supplied_unit=None,
                user_supplied_note=None,
            ),
        ],
    )

    assert [response.prompt_id for response in result.user_supplied_responses] == [
        "MISS-003",
        "MISS-005",
    ]
    assert result.user_supplied_responses[1].parameter_name == "变压器接线方式"


def test_rejects_duplicate_actual_names() -> None:
    with pytest.raises(DynamicIdAdapterError) as exc_info:
        bind_user_responses_by_canonical_name(
            actual_prompts=[
                {"prompt_id": "MISS-001", "parameter_name": "H"},
                {"prompt_id": "MISS-002", "parameter_name": "H"},
            ],
            fixture_entries=[
                FixtureUserSuppliedEntry(
                    fixture_prompt_id="MISS-001",
                    parameter_name="H",
                    user_supplied_value="3.5",
                    user_supplied_unit="s",
                    user_supplied_note=None,
                )
            ],
        )

    assert any(
        failure.code == "actual_prompt_duplicate_parameter_name"
        for failure in exc_info.value.failures
    )
