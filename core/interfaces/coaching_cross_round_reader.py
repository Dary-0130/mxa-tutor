"""Window reader boundary for MATLAB bridge run-state coaching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from core.interfaces.coaching_run_state_reader import (
    CoachingRunStateScope,
    CoachingRunStateSnapshot,
)


class CoachingCrossRoundReader(ABC):
    """Read a scoped target run plus a bounded previous-run window."""

    @abstractmethod
    async def read_run_state_window_for_coaching(
        self,
        scope: CoachingRunStateScope,
        run_id: UUID,
        previous_run_count: int,
    ) -> tuple[CoachingRunStateSnapshot, ...]:
        """Read target plus up to previous_run_count predecessors, sorted ascending."""
        ...

    @abstractmethod
    async def assert_coaching_session_active(self, scope: CoachingRunStateScope) -> None:
        """Recheck that the scoped run-state session remains active."""
        ...
