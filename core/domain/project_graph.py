from dataclasses import dataclass
from enum import Enum

from core.domain.source_ref import SourceRef


class NodeType(Enum):
    """ProjectGraph 中节点的类型。"""

    FILE_M = "file_m"
    FILE_SLX = "file_slx"
    FILE_MAT = "file_mat"
    BLOCK = "block"
    SUBSYSTEM = "subsystem"
    FUNCTION = "function"
    PARAMETER = "parameter"


class EdgeType(Enum):
    """ProjectGraph 中边的类型。"""

    CALLS = "calls"
    SIGNAL_FLOWS = "signal_flows"
    BELONGS_TO = "belongs_to"
    READS_PARAM = "reads_param"
    LOADS_DATA = "loads_data"


@dataclass
class ProjectNode:
    """ProjectGraph 的一个节点。"""

    id: str
    type: NodeType
    label: str
    source_ref: SourceRef
    metadata: dict[str, str]


@dataclass
class ProjectEdge:
    """ProjectGraph 的一条边。"""

    from_node: str
    to_node: str
    type: EdgeType


@dataclass
class ProjectGraph:
    """工程的结构化理解图,由 Parser 输出经纯逻辑转换构建,不含 LLM 调用。"""

    project_id: str
    nodes: list[ProjectNode]
    edges: list[ProjectEdge]
    entry_points: list[str]
    execution_flow: list[str]
    data_flow: list[str]
    control_flow: list[str]
    unresolved_symbols: list[str]
