from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.domain.m_file import MFile
from core.domain.mat_metadata import MatMetadata
from core.domain.slx_model import SlxModel


class ProjectType(Enum):
    """项目类型分类,用于路由 prompt 模板和导览生成。"""

    CONTROL_SYSTEM = "control_system"
    SIGNAL_PROCESSING = "signal_processing"
    POWER_ELECTRONICS = "power_electronics"
    COMMUNICATION = "communication"
    MOTOR_CONTROL = "motor_control"
    NEW_ENERGY = "new_energy"
    GENERAL = "general"


@dataclass
class FileInfo:
    """工程中单个文件的元信息。"""

    relative_path: str
    file_type: str
    size_bytes: int
    description: str | None = None


@dataclass
class Project:
    """单个上传工程的完整结构化表示。"""

    id: str
    name: str
    project_type: ProjectType
    files: list[FileInfo]
    slx_models: list[SlxModel]
    m_files: list[MFile]
    mat_files: list[MatMetadata]
    created_at: datetime
    file_dependencies: dict[str, list[str]]
