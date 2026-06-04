"""Pydantic schemas for generated project overview JSON."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectTypeValue = Literal[
    "control_system",
    "signal_processing",
    "power_electronics",
    "communication",
    "motor_control",
    "new_energy",
    "general",
]


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntryFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=100)


class SimulinkModelEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=200)


class KeyFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)


class BlockEntry(_StrictBaseModel):
    block_name: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)


class SourceRefEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    line_range: tuple[int, int] | None = None
    block_id: str | None = None


class ProjectOverview(_StrictBaseModel):
    project_title: str = Field(min_length=1, max_length=30)
    project_type: ProjectTypeValue
    one_sentence_summary: str = Field(min_length=1, max_length=80)
    main_entry_files: list[EntryFileEntry] = Field(min_length=1, max_length=3)
    main_simulink_models: list[SimulinkModelEntry] = Field(max_length=5)
    main_execution_flow: list[str] = Field(min_length=3, max_length=7)
    key_files: list[KeyFileEntry] = Field(min_length=3, max_length=8)
    key_blocks: list[BlockEntry] = Field(max_length=10)
    knowledge_points: list[str] = Field(min_length=3, max_length=6)
    beginner_reading_order: list[str] = Field(min_length=3, max_length=6)
    likely_confusing_points: list[str] = Field(min_length=2, max_length=5)
    evidence: list[SourceRefEntry] = Field(min_length=3)
