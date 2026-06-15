"""Pure Python ProjectOverview domain contract."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

ProjectTypeValue = Literal[
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
]


class _DataclassDumpMixin:
    def model_dump(self: "DataclassInstance") -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntryFileEntry(_DataclassDumpMixin):
    file_path: str
    role: str


@dataclass(frozen=True)
class SimulinkModelEntry(_DataclassDumpMixin):
    file_path: str
    summary: str


@dataclass(frozen=True)
class KeyFileEntry(_DataclassDumpMixin):
    file_path: str
    why_key: str


@dataclass(frozen=True)
class BlockEntry(_DataclassDumpMixin):
    block_name: str
    block_type: str
    location: str
    why_key: str


@dataclass(frozen=True)
class SourceRefEntry(_DataclassDumpMixin):
    file_path: str
    line_range: tuple[int, int] | None = None
    block_id: str | None = None


@dataclass(frozen=True)
class ProjectOverview(_DataclassDumpMixin):
    project_title: str
    project_type: ProjectTypeValue
    one_sentence_summary: str
    main_entry_files: list[EntryFileEntry]
    main_simulink_models: list[SimulinkModelEntry]
    main_execution_flow: list[str]
    key_files: list[KeyFileEntry]
    key_blocks: list[BlockEntry]
    knowledge_points: list[str]
    beginner_reading_order: list[str]
    likely_confusing_points: list[str]
    evidence: list[SourceRefEntry]
