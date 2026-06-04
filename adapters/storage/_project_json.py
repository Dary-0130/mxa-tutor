"""Project JSON 序列化辅助(TASK-204)。"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


def _project_to_json(project: Project) -> str:
    """Project -> JSON 文本,持久化前清空 MFile.raw_code。"""

    data = asdict(project)
    data["project_type"] = project.project_type.value
    data["created_at"] = project.created_at.isoformat()
    for m_file in data["m_files"]:
        m_file["raw_code"] = ""
    return json.dumps(data, ensure_ascii=False)


def _project_from_json(payload: str) -> Project:
    """JSON 文本 -> Project。"""

    return _project_from_dict(json.loads(payload))


def _project_from_dict(data: dict[str, Any]) -> Project:
    return Project(
        id=data["id"],
        name=data["name"],
        project_type=ProjectType(data["project_type"]),
        files=[_file_info_from_dict(item) for item in data["files"]],
        slx_models=[_slx_model_from_dict(item) for item in data["slx_models"]],
        m_files=[_m_file_from_dict(item) for item in data["m_files"]],
        mat_files=[_mat_metadata_from_dict(item) for item in data["mat_files"]],
        created_at=datetime.fromisoformat(data["created_at"]),
        file_dependencies=data["file_dependencies"],
    )


def _file_info_from_dict(data: dict[str, Any]) -> FileInfo:
    return FileInfo(
        relative_path=data["relative_path"],
        file_type=data["file_type"],
        size_bytes=data["size_bytes"],
        description=data["description"],
    )


def _slx_model_from_dict(data: dict[str, Any]) -> SlxModel:
    return SlxModel(
        file_path=data["file_path"],
        name=data["name"],
        blocks=[_slx_block_from_dict(item) for item in data["blocks"]],
        lines=[_slx_line_from_dict(item) for item in data["lines"]],
        subsystems=data["subsystems"],
        solver_config=data["solver_config"],
        parse_warnings=data["parse_warnings"],
    )


def _slx_block_from_dict(data: dict[str, Any]) -> SlxBlock:
    return SlxBlock(
        block_id=data["block_id"],
        name=data["name"],
        block_type=data["block_type"],
        parameters=data["parameters"],
        position=tuple(data["position"]),
        parent_subsystem=data["parent_subsystem"],
        is_masked=data.get("is_masked", False),
        is_library_link=data.get("is_library_link", False),
        is_model_reference=data.get("is_model_reference", False),
    )


def _slx_line_from_dict(data: dict[str, Any]) -> SlxLine:
    return SlxLine(
        from_block=data["from_block"],
        from_port=data["from_port"],
        to_block=data["to_block"],
        to_port=data["to_port"],
    )


def _m_file_from_dict(data: dict[str, Any]) -> MFile:
    return MFile(
        file_path=data["file_path"],
        file_role=data["file_role"],
        functions=[_m_function_from_dict(item) for item in data["functions"]],
        imports=data["imports"],
        uses_toolbox=data["uses_toolbox"],
        raw_code=data["raw_code"],
    )


def _m_function_from_dict(data: dict[str, Any]) -> MFunction:
    return MFunction(
        name=data["name"],
        inputs=data["inputs"],
        outputs=data["outputs"],
        line_range=tuple(data["line_range"]),
        docstring=data["docstring"],
    )


def _mat_metadata_from_dict(data: dict[str, Any]) -> MatMetadata:
    return MatMetadata(
        file_path=data["file_path"],
        file_size_bytes=data["file_size_bytes"],
        variables=[_mat_variable_from_dict(item) for item in data["variables"]],
    )


def _mat_variable_from_dict(data: dict[str, Any]) -> MatVariable:
    return MatVariable(
        name=data["name"],
        var_type=data["var_type"],
        shape=tuple(data["shape"]),
        likely_role=data["likely_role"],
        first_field_names=data["first_field_names"],
    )
