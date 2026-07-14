"""Typed Pydantic payloads for build guidance resolution."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, RootModel, StrictFloat, StrictInt, StrictStr

from core.domain.paper_plan import GuidanceResolution

GUIDANCE_VALUE_TOKEN_PATTERN = r"^[A-Za-z0-9]{1,40}$"


class _ResolutionBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FixedNumericResolutionModel(_ResolutionBaseModel):
    kind: Literal["fixed"]
    fixed_kind: Literal["numeric"]
    value: StrictInt | StrictFloat
    unit: Annotated[str, Field(min_length=1)]


class FixedBlockRefResolutionModel(_ResolutionBaseModel):
    kind: Literal["fixed"]
    fixed_kind: Literal["block_ref"]
    selected_id: Annotated[str, Field(min_length=1)]


class FixedConfigurationOptionResolutionModel(_ResolutionBaseModel):
    kind: Literal["fixed"]
    fixed_kind: Literal["configuration_option"]
    value_token: Annotated[str, Field(pattern=GUIDANCE_VALUE_TOKEN_PATTERN)]
    display_label: Annotated[str, Field(min_length=1, max_length=120)]


class FixedConnectionModeResolutionModel(_ResolutionBaseModel):
    kind: Literal["fixed"]
    fixed_kind: Literal["connection_mode"]
    value_token: Annotated[str, Field(pattern=GUIDANCE_VALUE_TOKEN_PATTERN)]
    display_label: Annotated[str, Field(min_length=1, max_length=120)]


FixedResolutionVariantModel: TypeAlias = Annotated[
    FixedNumericResolutionModel
    | FixedBlockRefResolutionModel
    | FixedConfigurationOptionResolutionModel
    | FixedConnectionModeResolutionModel,
    Field(discriminator="fixed_kind"),
]


class FixedResolutionModel(RootModel[FixedResolutionVariantModel]):
    """OpenAPI-safe fixed wrapper that preserves the flat public JSON shape."""

    @property
    def kind(self) -> Literal["fixed"]:
        return "fixed"


class RangeResolutionModel(_ResolutionBaseModel):
    kind: Literal["range"]
    lower: StrictInt | StrictFloat | StrictStr | None = None
    upper: StrictInt | StrictFloat | StrictStr | None = None
    values: list[StrictInt | StrictFloat | StrictStr] | None = None
    recommended_start: StrictInt | StrictFloat | StrictStr | None = None
    selection_rule: StrictStr | None = None


class EnumSelectionResolutionModel(_ResolutionBaseModel):
    kind: Literal["enum_selection"]
    selected: Annotated[str, Field(min_length=1)]


class DerivationResolutionModel(_ResolutionBaseModel):
    kind: Literal["derivation"]
    formula: StrictStr | None = None
    rule: StrictStr | None = None
    inputs: list[StrictStr]


class ConditionalResolutionModel(_ResolutionBaseModel):
    kind: Literal["conditional"]
    branches: list[dict[str, Any]]
    fallback: StrictStr | None = None
    exhaustive: bool = False


class UserDecisionOptionModel(_ResolutionBaseModel):
    option: Annotated[str, Field(min_length=1)]
    consequence: Annotated[str, Field(min_length=1)]


class GuidedUserDecisionResolutionModel(_ResolutionBaseModel):
    kind: Literal["guided_user_decision"]
    decision_item: Annotated[str, Field(min_length=1)]
    criteria: Annotated[str, Field(min_length=1)]
    options: list[UserDecisionOptionModel]


class EnvironmentProbeActionModel(_ResolutionBaseModel):
    result: Annotated[str, Field(min_length=1)]
    action: Annotated[str, Field(min_length=1)]


class EnvironmentProbeResolutionModel(_ResolutionBaseModel):
    kind: Literal["environment_probe"]
    probe_item: Annotated[str, Field(min_length=1)]
    procedure: Annotated[str, Field(min_length=1)]
    result_actions: list[EnvironmentProbeActionModel]


GuidanceResolutionModel: TypeAlias = Annotated[
    FixedResolutionModel
    | RangeResolutionModel
    | EnumSelectionResolutionModel
    | DerivationResolutionModel
    | ConditionalResolutionModel
    | GuidedUserDecisionResolutionModel
    | EnvironmentProbeResolutionModel,
    Field(discriminator="kind"),
]


def resolution_to_domain(resolution: GuidanceResolutionModel | None) -> GuidanceResolution | None:
    """Return the public JSON dict form used by the domain dataclass."""

    if resolution is None:
        return None
    return cast(GuidanceResolution, resolution.model_dump(mode="json"))
