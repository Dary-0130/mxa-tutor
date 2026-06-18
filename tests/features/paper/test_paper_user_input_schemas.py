from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from features.paper.paper_user_input_schemas import (
    UserSuppliedResponseBatch,
    UserSuppliedResponseModel,
)


def _constraint_value(schema_cls: type[BaseModel], field_name: str, constraint_name: str) -> Any:
    field_info = schema_cls.model_fields[field_name]
    for item in field_info.metadata:
        if hasattr(item, constraint_name):
            return getattr(item, constraint_name)
    return None


def test_user_supplied_response_model_fields_are_frozen() -> None:
    assert tuple(UserSuppliedResponseModel.model_fields) == (
        "prompt_id",
        "parameter_name",
        "user_supplied_value",
        "user_supplied_unit",
        "user_supplied_note",
    )


def test_user_supplied_response_model_forbids_extra_fields() -> None:
    payload = _response_payload()
    payload["unexpected"] = "x"

    with pytest.raises(ValidationError):
        UserSuppliedResponseModel.model_validate(payload)


def test_user_supplied_response_model_accepts_five_field_payload() -> None:
    model = UserSuppliedResponseModel.model_validate(_response_payload())

    assert model.prompt_id == "MISS-1"
    assert model.parameter_name == "H"
    assert model.user_supplied_value == "3.5"
    assert model.user_supplied_unit == "s"
    assert model.user_supplied_note == "Read from figure."


def test_user_supplied_response_batch_rejects_empty_array() -> None:
    assert UserSuppliedResponseBatch.model_config.get("extra") == "forbid"
    assert (
        _constraint_value(
            UserSuppliedResponseBatch,
            "user_supplied_responses",
            "min_length",
        )
        == 1
    )

    with pytest.raises(ValidationError):
        UserSuppliedResponseBatch.model_validate({"user_supplied_responses": []})


def test_user_supplied_response_batch_accepts_nonempty_array() -> None:
    batch = UserSuppliedResponseBatch.model_validate(
        {"user_supplied_responses": [_response_payload()]}
    )

    assert len(batch.user_supplied_responses) == 1


def _response_payload() -> dict[str, object]:
    return {
        "prompt_id": "MISS-1",
        "parameter_name": "H",
        "user_supplied_value": "3.5",
        "user_supplied_unit": "s",
        "user_supplied_note": "Read from figure.",
    }
