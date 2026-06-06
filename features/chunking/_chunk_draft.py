from dataclasses import dataclass

from core.interfaces.vector_store import SourceType


@dataclass(frozen=True)
class ChunkDraft:
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
