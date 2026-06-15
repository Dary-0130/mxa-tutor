"""Pure Python ProjectOverview domain contract."""

from dataclasses import dataclass
from typing import Literal

ProjectTypeValue = Literal[
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
]

@dataclass(frozen=True)
class EntryFileEntry:
    file_path: str
    role: str


@dataclass(frozen=True)
class SimulinkModelEntry:
    file_path: str
    summary: str


@dataclass(frozen=True)
class KeyFileEntry:
    file_path: str
    why_key: str


@dataclass(frozen=True)
class BlockEntry:
    block_name: str
    block_type: str
    location: str
    why_key: str


@dataclass(frozen=True)
class SourceRefEntry:
    file_path: str
    line_range: tuple[int, int] | None = None
    block_id: str | None = None


@dataclass(frozen=True)
class ProjectOverview:
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
