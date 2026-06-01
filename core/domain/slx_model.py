from dataclasses import dataclass


@dataclass
class SlxBlock:
    """Simulink 模型中的单个 block。"""

    block_id: str
    name: str
    block_type: str
    parameters: dict[str, str]
    position: tuple[int, int, int, int]
    parent_subsystem: str | None
    is_masked: bool = False
    is_library_link: bool = False
    is_model_reference: bool = False


@dataclass
class SlxLine:
    """Simulink 模型中两个 block 之间的连接线。"""

    from_block: str
    from_port: int
    to_block: str
    to_port: int


@dataclass
class SlxModel:
    """单个 .slx 文件解析后的结构化表示。"""

    file_path: str
    name: str
    blocks: list[SlxBlock]
    lines: list[SlxLine]
    subsystems: dict[str, list[str]]
    solver_config: dict[str, str]
    parse_warnings: list[str]
