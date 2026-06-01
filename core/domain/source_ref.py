from dataclasses import dataclass


@dataclass
class SourceRef:
    """证据引用 —— 所有教学输出和问答都必须基于 SourceRef。"""

    file_path: str
    line_range: tuple[int, int] | None = None
    block_id: str | None = None
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None
