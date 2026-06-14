"""Pydantic schemas for generated project overview JSON."""

from __future__ import annotations

from dataclasses import asdict

from pydantic import BaseModel, ConfigDict, Field

from core.domain import project_overview as domain_overview

ProjectTypeValue = domain_overview.ProjectTypeValue


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntryFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=100)

    @classmethod
    def from_domain(cls, entry: domain_overview.EntryFileEntry) -> EntryFileEntry:
        return cls(**asdict(entry))

    def to_domain(self) -> domain_overview.EntryFileEntry:
        return domain_overview.EntryFileEntry(file_path=self.file_path, role=self.role)


class SimulinkModelEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=200)

    @classmethod
    def from_domain(cls, entry: domain_overview.SimulinkModelEntry) -> SimulinkModelEntry:
        return cls(**asdict(entry))

    def to_domain(self) -> domain_overview.SimulinkModelEntry:
        return domain_overview.SimulinkModelEntry(
            file_path=self.file_path,
            summary=self.summary,
        )


class KeyFileEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)

    @classmethod
    def from_domain(cls, entry: domain_overview.KeyFileEntry) -> KeyFileEntry:
        return cls(**asdict(entry))

    def to_domain(self) -> domain_overview.KeyFileEntry:
        return domain_overview.KeyFileEntry(file_path=self.file_path, why_key=self.why_key)


class BlockEntry(_StrictBaseModel):
    block_name: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    why_key: str = Field(min_length=1, max_length=200)

    @classmethod
    def from_domain(cls, entry: domain_overview.BlockEntry) -> BlockEntry:
        return cls(**asdict(entry))

    def to_domain(self) -> domain_overview.BlockEntry:
        return domain_overview.BlockEntry(
            block_name=self.block_name,
            block_type=self.block_type,
            location=self.location,
            why_key=self.why_key,
        )


class SourceRefEntry(_StrictBaseModel):
    file_path: str = Field(min_length=1)
    line_range: tuple[int, int] | None = None
    block_id: str | None = None

    @classmethod
    def from_domain(cls, entry: domain_overview.SourceRefEntry) -> SourceRefEntry:
        return cls(**asdict(entry))

    def to_domain(self) -> domain_overview.SourceRefEntry:
        return domain_overview.SourceRefEntry(
            file_path=self.file_path,
            line_range=self.line_range,
            block_id=self.block_id,
        )


class ProjectOverview(_StrictBaseModel):
    project_title: str = Field(min_length=1, max_length=30)
    project_type: ProjectTypeValue
    one_sentence_summary: str = Field(min_length=1, max_length=80)
    main_entry_files: list[EntryFileEntry] = Field(min_length=1, max_length=3)
    main_simulink_models: list[SimulinkModelEntry] = Field(max_length=5)
    main_execution_flow: list[str] = Field(min_length=3, max_length=10)
    key_files: list[KeyFileEntry] = Field(min_length=1, max_length=8)
    key_blocks: list[BlockEntry] = Field(max_length=10)
    knowledge_points: list[str] = Field(min_length=3, max_length=6)
    beginner_reading_order: list[str] = Field(min_length=3, max_length=6)
    likely_confusing_points: list[str] = Field(min_length=2, max_length=5)
    evidence: list[SourceRefEntry] = Field(min_length=1)

    @classmethod
    def from_domain(cls, overview: domain_overview.ProjectOverview) -> ProjectOverview:
        return cls(
            project_title=overview.project_title,
            project_type=overview.project_type,
            one_sentence_summary=overview.one_sentence_summary,
            main_entry_files=[
                EntryFileEntry.from_domain(entry) for entry in overview.main_entry_files
            ],
            main_simulink_models=[
                SimulinkModelEntry.from_domain(entry) for entry in overview.main_simulink_models
            ],
            main_execution_flow=overview.main_execution_flow,
            key_files=[KeyFileEntry.from_domain(entry) for entry in overview.key_files],
            key_blocks=[BlockEntry.from_domain(entry) for entry in overview.key_blocks],
            knowledge_points=overview.knowledge_points,
            beginner_reading_order=overview.beginner_reading_order,
            likely_confusing_points=overview.likely_confusing_points,
            evidence=[SourceRefEntry.from_domain(entry) for entry in overview.evidence],
        )

    def to_domain(self) -> domain_overview.ProjectOverview:
        return domain_overview.ProjectOverview(
            project_title=self.project_title,
            project_type=self.project_type,
            one_sentence_summary=self.one_sentence_summary,
            main_entry_files=[entry.to_domain() for entry in self.main_entry_files],
            main_simulink_models=[entry.to_domain() for entry in self.main_simulink_models],
            main_execution_flow=self.main_execution_flow,
            key_files=[entry.to_domain() for entry in self.key_files],
            key_blocks=[entry.to_domain() for entry in self.key_blocks],
            knowledge_points=self.knowledge_points,
            beginner_reading_order=self.beginner_reading_order,
            likely_confusing_points=self.likely_confusing_points,
            evidence=[entry.to_domain() for entry in self.evidence],
        )


ProjectOverviewModel = ProjectOverview
ProjectOverviewSchema = ProjectOverview
