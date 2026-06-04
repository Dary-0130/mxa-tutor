from datetime import datetime, timedelta
import json
import sqlite3

import pytest

from adapters.storage._connection import open_connection
from adapters.storage.sqlite_project_store import SqliteProjectStore
from core.domain.exceptions import ProjectNotFoundError
from core.domain.m_file import MFile, MFunction
from core.domain.mat_metadata import MatMetadata, MatVariable
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.slx_model import SlxBlock, SlxLine, SlxModel


def _project(project_id: str = "p1", raw_code: str = "disp('secret')") -> Project:
    return Project(
        id=project_id,
        name="demo.zip",
        project_type=ProjectType.CONTROL_SYSTEM,
        files=[FileInfo(relative_path="model.slx", file_type=".slx", size_bytes=2048)],
        slx_models=[
            SlxModel(
                file_path="model.slx",
                name="model",
                blocks=[
                    SlxBlock(
                        block_id="b1",
                        name="Gain",
                        block_type="Gain",
                        parameters={"Gain": "Kp"},
                        position=(0, 0, 20, 20),
                        parent_subsystem=None,
                    )
                ],
                lines=[SlxLine(from_block="b1", from_port=1, to_block="b2", to_port=1)],
                subsystems={},
                solver_config={},
                parse_warnings=[],
            )
        ],
        m_files=[
            MFile(
                file_path="init.m",
                file_role="script",
                functions=[
                    MFunction(
                        name="init",
                        inputs=[],
                        outputs=[],
                        line_range=(1, 5),
                        docstring=None,
                    )
                ],
                imports=[],
                uses_toolbox=[],
                raw_code=raw_code,
            )
        ],
        mat_files=[
            MatMetadata(
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
        ],
        created_at=datetime(2026, 6, 4, 12, 0, 0),
        file_dependencies={"model.slx": ["init.m"]},
    )


async def test_create_pending_creates_status_record(project_store: SqliteProjectStore) -> None:
    before = datetime.utcnow()

    await project_store.create_pending("p1", "demo.zip")

    view = await project_store.get_status_view("p1")
    assert view.project_id == "p1"
    assert view.name == "demo.zip"
    assert view.status == "parsing"
    assert before <= view.created_at <= datetime.utcnow()
    assert view.error_code is None


async def test_create_pending_duplicate_raises_value_error(
    project_store: SqliteProjectStore,
) -> None:
    await project_store.create_pending("p1", "demo.zip")

    with pytest.raises(ValueError):
        await project_store.create_pending("p1", "other.zip")


async def test_mark_ready_round_trips_project(project_store: SqliteProjectStore) -> None:
    await project_store.create_pending("p1", "demo.zip")

    await project_store.mark_ready("p1", _project())

    view = await project_store.get_status_view("p1")
    project = await project_store.get_project("p1")
    assert view.status == "ready"
    assert project.id == "p1"
    assert project.project_type is ProjectType.CONTROL_SYSTEM
    assert project.slx_models[0].blocks[0].position == (0, 0, 20, 20)
    assert project.m_files[0].functions[0].line_range == (1, 5)
    assert project.mat_files[0].variables[0].shape == (1, 1)
    assert project.m_files[0].raw_code == ""


async def test_mark_ready_redacts_raw_code(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await project_store.create_pending("p1", "demo.zip")

    await project_store.mark_ready("p1", _project(raw_code="function y = secret(x)\ny=x;"))

    with sqlite3.connect(initialized_db_path) as conn:
        row = conn.execute(
            "SELECT project FROM project_status_record WHERE project_id=?",
            ("p1",),
        ).fetchone()
    data = json.loads(row[0])
    assert [m_file["raw_code"] for m_file in data["m_files"]] == [""]


async def test_mark_ready_on_missing_or_non_parsing_raises_value_error(
    project_store: SqliteProjectStore,
) -> None:
    with pytest.raises(ValueError):
        await project_store.mark_ready("missing", _project("missing"))

    await project_store.create_pending("p1", "demo.zip")
    await project_store.mark_failed("p1", "parse_error")
    with pytest.raises(ValueError):
        await project_store.mark_ready("p1", _project())


async def test_mark_failed_records_error_code(project_store: SqliteProjectStore) -> None:
    await project_store.create_pending("p1", "demo.zip")

    await project_store.mark_failed("p1", "zip_bomb")

    view = await project_store.get_status_view("p1")
    assert view.status == "failed"
    assert view.error_code == "zip_bomb"
    with pytest.raises(ProjectNotFoundError):
        await project_store.get_project("p1")


async def test_mark_failed_on_missing_or_ready_raises_value_error(
    project_store: SqliteProjectStore,
) -> None:
    with pytest.raises(ValueError):
        await project_store.mark_failed("missing", "parse_error")

    await project_store.create_pending("p1", "demo.zip")
    await project_store.mark_ready("p1", _project())
    with pytest.raises(ValueError):
        await project_store.mark_failed("p1", "parse_error")


async def test_get_status_view_missing_raises_project_not_found(
    project_store: SqliteProjectStore,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_store.get_status_view("missing")


async def test_get_project_when_parsing_raises_project_not_found(
    project_store: SqliteProjectStore,
) -> None:
    await project_store.create_pending("p1", "demo.zip")

    with pytest.raises(ProjectNotFoundError):
        await project_store.get_project("p1")


async def test_list_expired_filters_by_created_at(
    project_store: SqliteProjectStore,
    initialized_db_path: str,
) -> None:
    await project_store.create_pending("old", "old.zip")
    await project_store.create_pending("fresh", "fresh.zip")
    old_created_at = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    async with open_connection(initialized_db_path) as conn:
        await conn.execute(
            "UPDATE project_status_record SET created_at=? WHERE project_id='old'",
            (old_created_at,),
        )
        await conn.commit()

    assert await project_store.list_expired(ttl_hours=1) == ["old"]


async def test_delete_is_idempotent_and_removes_record(
    project_store: SqliteProjectStore,
) -> None:
    await project_store.delete("missing")
    await project_store.create_pending("p1", "demo.zip")

    await project_store.delete("p1")

    with pytest.raises(ProjectNotFoundError):
        await project_store.get_status_view("p1")
