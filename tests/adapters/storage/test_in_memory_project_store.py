import asyncio
from datetime import datetime, timedelta

import pytest

from adapters.storage.in_memory_project_store import InMemoryProjectStore
from core.domain.exceptions import ProjectNotFoundError
from core.domain.project import Project, ProjectType


def _project(project_id: str = "p1") -> Project:
    return Project(
        id=project_id,
        name="demo.zip",
        project_type=ProjectType.GENERAL,
        files=[],
        slx_models=[],
        m_files=[],
        mat_files=[],
        created_at=datetime.utcnow(),
        file_dependencies={},
    )


async def test_create_pending_creates_record_with_now_timestamps() -> None:
    store = InMemoryProjectStore()
    before = datetime.utcnow()

    await store.create_pending("p1", "demo.zip")

    view = await store.get_status_view("p1")
    assert view.project_id == "p1"
    assert view.name == "demo.zip"
    assert view.status == "parsing"
    assert before <= view.created_at <= datetime.utcnow()
    assert view.error_code is None


async def test_create_pending_duplicate_raises_value_error() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")

    with pytest.raises(ValueError):
        await store.create_pending("p1", "other.zip")


async def test_mark_ready_transitions_status_and_attaches_project() -> None:
    store = InMemoryProjectStore()
    project = _project()
    await store.create_pending("p1", "demo.zip")

    await store.mark_ready("p1", project)

    assert (await store.get_status_view("p1")).status == "ready"
    assert await store.get_project("p1") is project


async def test_mark_ready_on_missing_raises_value_error() -> None:
    with pytest.raises(ValueError):
        await InMemoryProjectStore().mark_ready("missing", _project())


async def test_mark_ready_on_already_failed_raises_value_error() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")
    await store.mark_failed("p1", "parse_error")

    with pytest.raises(ValueError):
        await store.mark_ready("p1", _project())


async def test_mark_failed_records_error_code_using_literal_type() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")

    await store.mark_failed("p1", "zip_bomb")

    view = await store.get_status_view("p1")
    assert view.status == "failed"
    assert view.error_code == "zip_bomb"


async def test_mark_failed_on_already_ready_raises_value_error() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")
    await store.mark_ready("p1", _project())

    with pytest.raises(ValueError):
        await store.mark_failed("p1", "parse_error")


async def test_get_status_view_returns_five_fields_excluding_project() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")

    view = await store.get_status_view("p1")

    assert set(view.__dataclass_fields__) == {
        "project_id",
        "name",
        "status",
        "created_at",
        "error_code",
    }
    assert not hasattr(view, "project")


async def test_get_status_view_missing_raises_project_not_found_error() -> None:
    with pytest.raises(ProjectNotFoundError):
        await InMemoryProjectStore().get_status_view("missing")


async def test_get_project_returns_only_when_ready() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")
    with pytest.raises(ProjectNotFoundError):
        await store.get_project("p1")

    project = _project()
    await store.mark_ready("p1", project)

    assert await store.get_project("p1") is project


async def test_get_project_when_failed_raises_project_not_found_error() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("p1", "demo.zip")
    await store.mark_failed("p1", "parse_error")

    with pytest.raises(ProjectNotFoundError):
        await store.get_project("p1")


async def test_list_expired_filters_by_created_at_boundary() -> None:
    store = InMemoryProjectStore()
    await store.create_pending("old", "old.zip")
    await store.create_pending("fresh", "fresh.zip")
    store._records["old"].created_at = datetime.utcnow() - timedelta(hours=2)

    assert await store.list_expired(ttl_hours=1) == ["old"]


async def test_delete_is_idempotent_on_missing() -> None:
    store = InMemoryProjectStore()
    await store.delete("missing")
    await store.create_pending("p1", "demo.zip")
    await store.delete("p1")

    with pytest.raises(ProjectNotFoundError):
        await store.get_status_view("p1")


async def test_concurrent_create_does_not_deadlock() -> None:
    store = InMemoryProjectStore()

    await asyncio.gather(
        *(store.create_pending(f"p{index}", f"{index}.zip") for index in range(20))
    )

    assert len(await store.list_expired(ttl_hours=-1)) == 20
