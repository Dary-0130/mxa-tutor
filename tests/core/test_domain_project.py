from datetime import datetime

from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


def test_project_type_values_match_contract() -> None:
    assert {item.name: item.value for item in ProjectType} == {
        "CONTROL_SYSTEM": "control_system",
        "SIGNAL_PROCESSING": "signal_processing",
        "POWER_ELECTRONICS": "power_electronics",
        "COMMUNICATION": "communication",
        "MOTOR_CONTROL": "motor_control",
        "NEW_ENERGY": "new_energy",
        "GENERAL": "general",
    }


def test_file_info_required_fields_and_defaults() -> None:
    file_info = FileInfo(relative_path="model.slx", file_type=".slx", size_bytes=2048)

    assert file_info.relative_path == "model.slx"
    assert file_info.file_type == ".slx"
    assert file_info.size_bytes == 2048
    assert file_info.description is None


def test_project_required_fields() -> None:
    block = SlxBlock(
        block_id="b1",
        name="Gain",
        block_type="Gain",
        parameters={},
        position=(0, 0, 20, 20),
        parent_subsystem=None,
    )
    slx_model = SlxModel(
        file_path="model.slx",
        name="model",
        blocks=[block],
        lines=[SlxLine(from_block="b1", from_port=1, to_block="b2", to_port=1)],
        subsystems={},
        solver_config={},
        parse_warnings=[],
    )
    m_function = MFunction(
        name="init",
        inputs=[],
        outputs=[],
        line_range=(1, 5),
        docstring=None,
    )
    m_file = MFile(
        file_path="init.m",
        file_role="script",
        functions=[m_function],
        imports=[],
        uses_toolbox=[],
        raw_code="disp('init')",
    )
    mat_metadata = MatMetadata(
        file_path="params.mat",
        file_size_bytes=512,
        variables=[
            MatVariable(
                name="Kp",
                var_type="double",
                shape=(1, 1),
                likely_role="param_table",
                first_field_names=[],
            )
        ],
    )
    created_at = datetime(2026, 6, 1, 12, 0, 0)
    project = Project(
        id="hash-1",
        name="demo",
        project_type=ProjectType.CONTROL_SYSTEM,
        files=[FileInfo(relative_path="model.slx", file_type=".slx", size_bytes=2048)],
        slx_models=[slx_model],
        m_files=[m_file],
        mat_files=[mat_metadata],
        created_at=created_at,
        file_dependencies={"model.slx": ["init.m"]},
    )

    assert project.id == "hash-1"
    assert project.project_type is ProjectType.CONTROL_SYSTEM
    assert project.slx_models == [slx_model]
    assert project.m_files == [m_file]
    assert project.mat_files == [mat_metadata]
    assert project.created_at == created_at
    assert project.file_dependencies == {"model.slx": ["init.m"]}
