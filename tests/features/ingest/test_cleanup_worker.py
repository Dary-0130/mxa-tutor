import asyncio
from pathlib import Path

import pytest

from features.ingest.cleanup_worker import CleanupWorker


class FakeStore:
    def __init__(
        self,
        expired: list[str] | None = None,
        *,
        list_exc: Exception | None = None,
        delete_fail: set[str] | None = None,
    ) -> None:
        self.expired = expired or []
        self.list_exc = list_exc
        self.delete_fail = delete_fail or set()
        self.deleted: list[str] = []

    async def list_expired(self, _ttl_hours: int) -> list[str]:
        if self.list_exc is not None:
            raise self.list_exc
        return self.expired

    async def delete(self, project_id: str) -> None:
        if project_id in self.delete_fail:
            raise RuntimeError("secret")
        self.deleted.append(project_id)


class FakePaperStore:
    def __init__(self, deleted: int = 0, error: Exception | None = None) -> None:
        self.deleted = deleted
        self.error = error
        self.calls: list[int] = []

    async def delete_expired_paper_bundles(self, *, now=None, ttl_hours: int = 24) -> int:
        _ = now
        self.calls.append(ttl_hours)
        if self.error is not None:
            raise self.error
        return self.deleted


async def test_run_once_deletes_expired_projects(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    store = FakeStore(["old"])
    worker = CleanupWorker(store, tmp_path, ttl_hours=24)

    deleted = await worker.run_once()

    assert deleted == 1
    assert store.deleted == ["old"]
    assert not (tmp_path / "old").exists()


async def test_run_once_sweeps_expired_paper_bundles(tmp_path: Path) -> None:
    paper_store = FakePaperStore(deleted=2)
    worker = CleanupWorker(FakeStore([]), tmp_path, ttl_hours=24, paper_store=paper_store)

    deleted = await worker.run_once()

    assert deleted == 2
    assert paper_store.calls == [24]


async def test_run_once_returns_zero_when_none_expired(tmp_path: Path) -> None:
    worker = CleanupWorker(FakeStore([]), tmp_path, ttl_hours=24)

    assert await worker.run_once() == 0


async def test_run_once_handles_store_list_expired_failure_with_metadata_log(
    tmp_path: Path,
) -> None:
    worker = CleanupWorker(FakeStore(list_exc=RuntimeError("secret")), tmp_path, 24)

    assert await worker.run_once() == 0


async def test_run_once_handles_store_delete_failure_on_one_pid_continues_others(
    tmp_path: Path,
) -> None:
    store = FakeStore(["bad", "ok"], delete_fail={"bad"})
    worker = CleanupWorker(store, tmp_path, 24)

    assert await worker.run_once() == 1
    assert store.deleted == ["ok"]


async def test_run_once_removes_disk_dir_first_then_store(tmp_path: Path, mocker) -> None:
    events = []
    (tmp_path / "old").mkdir()
    store = FakeStore(["old"])

    async def delete(project_id: str) -> None:
        events.append(f"store:{project_id}")
        store.deleted.append(project_id)

    def rmtree(_path: Path, ignore_errors: bool) -> None:
        events.append(f"disk:{ignore_errors}")

    store.delete = delete
    mocker.patch("features.ingest.cleanup_worker.shutil.rmtree", side_effect=rmtree)

    await CleanupWorker(store, tmp_path, 24).run_once()

    assert events == ["disk:True", "store:old"]


async def test_run_once_skips_disk_when_dir_not_exist(tmp_path: Path, mocker) -> None:
    rmtree = mocker.patch("features.ingest.cleanup_worker.shutil.rmtree")

    assert await CleanupWorker(FakeStore(["missing"]), tmp_path, 24).run_once() == 1
    assert rmtree.call_count == 0


def test_run_once_logger_never_uses_exception_method() -> None:
    src = Path("features/ingest/cleanup_worker.py").read_text(encoding="utf-8")
    assert "logger.exception" not in src


async def test_run_forever_cancellation_propagates_cleanly(tmp_path: Path) -> None:
    task = asyncio.create_task(CleanupWorker(FakeStore([]), tmp_path, 24).run_forever())
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_run_forever_interval_respected(tmp_path: Path, mocker) -> None:
    sleeps = []

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)
        raise asyncio.CancelledError

    mocker.patch("features.ingest.cleanup_worker.asyncio.sleep", side_effect=fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await CleanupWorker(FakeStore([]), tmp_path, 24, interval_minutes=2).run_forever()

    assert sleeps == [120]
