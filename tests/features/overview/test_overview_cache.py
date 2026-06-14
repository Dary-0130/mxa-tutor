from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest

from features.overview import InMemoryOverviewCache, OverviewCache

if TYPE_CHECKING:
    from core.domain.project_overview import ProjectOverview


def _overview(title: str = "demo") -> Any:
    return cast("ProjectOverview", {"project_title": title})


@pytest.mark.asyncio
async def test_cache_get_returns_none_for_miss() -> None:
    cache = InMemoryOverviewCache()

    assert await cache.get("missing") is None


@pytest.mark.asyncio
async def test_cache_put_then_get_returns_same_object() -> None:
    cache = InMemoryOverviewCache()
    overview = _overview()

    await cache.put("p1", overview)

    assert await cache.get("p1") is overview


@pytest.mark.asyncio
async def test_cache_invalidate_removes_only_target_project() -> None:
    cache = InMemoryOverviewCache()
    first = _overview("first")
    second = _overview("second")

    await cache.put("p1", first)
    await cache.put("p2", second)
    await cache.invalidate("p1")

    assert await cache.get("p1") is None
    assert await cache.get("p2") is second


@pytest.mark.asyncio
async def test_cache_concurrent_puts_do_not_mix_project_ids() -> None:
    cache = InMemoryOverviewCache()

    await asyncio.gather(
        *(cache.put(f"p{i}", _overview(f"title-{i}")) for i in range(20)),
    )

    results = await asyncio.gather(*(cache.get(f"p{i}") for i in range(20)))

    assert [item["project_title"] for item in results if item is not None] == [
        f"title-{i}" for i in range(20)
    ]


@pytest.mark.asyncio
async def test_cache_get_does_not_wait_for_write_lock() -> None:
    cache = InMemoryOverviewCache()
    overview = _overview()
    await cache.put("p1", overview)

    await cache._lock.acquire()
    try:
        assert await asyncio.wait_for(cache.get("p1"), timeout=0.1) is overview
    finally:
        cache._lock.release()


def test_cache_implements_overview_cache_interface() -> None:
    assert isinstance(InMemoryOverviewCache(), OverviewCache)
