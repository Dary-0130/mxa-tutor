"""Vector store abstraction for project-scoped chunk embeddings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

SourceType = Literal[
    "m_file",
    "m_function",
    "slx_block",
    "slx_subsystem",
    "mat_variable",
    "project_overview",
    "teaching_unit",
]
RESERVED_SOURCE_TYPES: Final[frozenset[str]] = frozenset({"teaching_unit"})


@dataclass(frozen=True)
class ChunkRecord:
    """A chunk record ready to be persisted with its precomputed embedding."""

    chunk_id: str
    project_id: str
    source_type: SourceType
    file_path: str
    symbol_name: str | None
    line_range: tuple[int, int] | None
    block_id: str | None
    block_name: str | None
    block_type: str | None
    parent_subsystem: str | None
    source_text: str
    embedding: list[float]
    model_name: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class QueryHit:
    """Single vector query hit."""

    chunk: ChunkRecord
    score: float


class VectorStore(ABC):
    """Project-scoped vector storage and cosine search."""

    @abstractmethod
    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Persist pre-embedded chunks in batch."""
        ...

    @abstractmethod
    async def query(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 8,
        min_score: float = 0.3,
    ) -> list[QueryHit]:
        """Return top-k cosine hits for one project."""
        ...

    @abstractmethod
    async def delete_by_project_id(self, project_id: str) -> int:
        """Delete all chunks for one project and return the deleted row count."""
        ...

    @abstractmethod
    async def get_chunk_count(self, project_id: str) -> int:
        """Return chunk count for one project."""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """Release resources held by the store."""
        ...
