"""Dedicated run-state retention sweep worker."""

from __future__ import annotations

import asyncio
from typing import Protocol

from loguru import logger

from core.domain.exceptions import StoreError


class RunStateSweepStore(Protocol):
    async def sweep_expired_run_state(self) -> int:
        """Clear due run-state snapshots and return affected session count."""


class RunStateCleanupWorker:
    """Clear run-state snapshots on a dedicated cadence without touching ingest cleanup."""

    def __init__(
        self,
        store: RunStateSweepStore,
        *,
        interval_seconds: int = 3600,
    ) -> None:
        self._store = store
        self._interval_seconds = interval_seconds

    async def run_once(self) -> int:
        try:
            return await self._store.sweep_expired_run_state()
        except StoreError as exc:
            logger.error(
                "Bridge run-state sweep unavailable: event_code={} status={} exception={}",
                "bridge_run_state_sweep",
                "store_unavailable",
                type(exc).__name__,
            )
            return 0

    async def run_forever(self) -> None:
        logger.info(
            "Bridge run-state sweep started: event_code={} status={} interval_seconds={}",
            "bridge_run_state_sweep",
            "started",
            self._interval_seconds,
        )
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.info(
                "Bridge run-state sweep cancelled: event_code={} status={}",
                "bridge_run_state_sweep",
                "cancelled",
            )
            raise
