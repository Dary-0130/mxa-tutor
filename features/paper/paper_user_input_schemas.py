"""Feature-private schemas for paper plan user-supplied inputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserSuppliedResponseModel(BaseModel):
    """User response for one MissingParameterPrompt."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(min_length=1)
    parameter_name: str = Field(min_length=1)
    user_supplied_value: str = Field(min_length=1)
    user_supplied_unit: str | None = Field(default=None, min_length=1)
    user_supplied_note: str | None = Field(default=None, min_length=1)


class UserSuppliedResponseBatch(BaseModel):
    """POST body for paper plan user-supplied responses."""

    model_config = ConfigDict(extra="forbid")

    user_supplied_responses: list[UserSuppliedResponseModel] = Field(min_length=1)
