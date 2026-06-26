from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from core.domain.bridge_auth import BridgeAuthClaims, BridgeAuthContext
from core.domain.bridge_run_state_coaching import BridgeRunStateCoachingRequest
from core.domain.exceptions import LLMTimeoutError
from core.interfaces.coaching_cross_round_reader import CoachingCrossRoundReader
from core.interfaces.coaching_run_state_reader import (
    CoachingRunStateMetric,
    CoachingRunStateReadRejectedError,
    CoachingRunStateScope,
    CoachingRunStateSeries,
    CoachingRunStateSnapshot,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, ModelCapability, TextProvider
from features.matlab_bridge.bridge_run_state_coaching_service import (
    BridgeRunStateCoachingBusyError,
    BridgeRunStateCoachingFailedError,
    BridgeRunStateCoachingService,
    BridgeRunStateCoachingTimeoutError,
    CoachingAttemptSlotManager,
)

REQUEST_ID = UUID("2690af3d-9cfe-4442-900e-c86af37a6244")
SESSION_ID = UUID("11111111-1111-4111-8111-111111111111")
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")
PREVIOUS_RUN_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeProvider(TextProvider):
    def __init__(
        self,
        response_text: str | None = None,
        *,
        exc: Exception | None = None,
        block_event: threading.Event | None = None,
    ) -> None:
        self.response_text = response_text or json.dumps(_draft_payload(), ensure_ascii=False)
        self.exc = exc
        self.block_event = block_event
        self.calls = 0
        self.messages: list[LLMMessage] = []
        self.timeouts: list[float] = []
        self.max_tokens: list[int | None] = []

    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        assert json_mode is True
        self.calls += 1
        self.messages = messages
        self.timeouts.append(timeout)
        self.max_tokens.append(max_tokens)
        if self.block_event is not None:
            self.block_event.wait(timeout=5)
        if self.exc is not None:
            raise self.exc
        return LLMResponse(
            text=self.response_text,
            prompt_tokens=1,
            completion_tokens=1,
            model="fake",
            latency_ms=1,
        )

    def capability(self) -> ModelCapability:
        return ModelCapability(model_name="fake", supports_json=True)


class FakeReader(CoachingCrossRoundReader):
    def __init__(
        self,
        snapshot: CoachingRunStateSnapshot | None = None,
        snapshots: tuple[CoachingRunStateSnapshot, ...] | None = None,
        *,
        reject_on_fence: bool = False,
    ) -> None:
        if snapshots is not None:
            self.snapshots = snapshots
        else:
            self.snapshots = (snapshot or _snapshot(),)
        self.reject_on_fence = reject_on_fence
        self.read_calls = 0
        self.fence_calls = 0
        self.previous_run_counts: list[int] = []

    async def read_run_state_window_for_coaching(
        self,
        scope: CoachingRunStateScope,
        run_id: UUID,
        previous_run_count: int,
    ) -> tuple[CoachingRunStateSnapshot, ...]:
        assert scope.session_id == str(SESSION_ID)
        assert run_id == RUN_ID
        self.previous_run_counts.append(previous_run_count)
        self.read_calls += 1
        return self.snapshots

    async def assert_coaching_session_active(self, scope: CoachingRunStateScope) -> None:
        assert scope.session_id == str(SESSION_ID)
        self.fence_calls += 1
        if self.reject_on_fence:
            raise CoachingRunStateReadRejectedError("session_terminal")


async def test_coach_builds_single_run_result_with_evidence_chain() -> None:
    provider = FakeProvider()
    reader = FakeReader()
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    result = await service.coach(_request(), _auth_context(), reader=reader)

    assert result.protocol_version == "0.3-c1"
    assert result.outcome == "coached"
    assert result.context_run_ids == (RUN_ID,)
    assert result.cross_round_trend is None
    assert result.run_summary.startswith("本轮状态为 completed")
    assert result.caveats
    assert result.signal_readings[0].evidence_ids[0] == result.evidence[0].evidence_id
    assert result.primary_directions[0].rationale_reading_id == result.signal_readings[0].reading_id
    assert provider.timeouts == [12.0]
    assert provider.max_tokens == [1024]
    assert "typed-data:run_state_observations" in provider.messages[1].content
    assert reader.read_calls == 1
    assert reader.fence_calls == 2


async def test_unknown_run_without_signals_returns_insufficient_without_provider() -> None:
    provider = FakeProvider()
    reader = FakeReader(
        _snapshot(
            run_status="unknown",
            convergence_status="unknown",
            metrics=(),
            series=(),
        )
    )
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    result = await service.coach(_request(), _auth_context(), reader=reader)

    assert result.outcome == "insufficient_evidence"
    assert result.primary_directions == ()
    assert result.fallback_reason == "run_status_unknown"
    assert result.overall_confidence == "low"
    assert provider.calls == 0
    assert reader.fence_calls == 1


async def test_previous_run_count_uses_window_and_trend_with_history() -> None:
    provider = FakeProvider(
        json.dumps(
            _draft_payload(cross_round_trend="前序和目标轮的可观测信号更稳定。"), ensure_ascii=False
        )
    )
    reader = FakeReader(
        snapshots=(
            _snapshot(run_id=PREVIOUS_RUN_ID, run_sequence=6),
            _snapshot(run_id=RUN_ID, run_sequence=7),
        )
    )
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    result = await service.coach(_request(previous_run_count=1), _auth_context(), reader=reader)

    assert result.context_run_ids == (PREVIOUS_RUN_ID, RUN_ID)
    assert result.cross_round_trend == "前序和目标轮的可观测信号更稳定。"
    assert reader.previous_run_counts == [1]
    payload = _provider_context_payload(provider)
    assert [item["run_id"] for item in payload["runs"]] == [str(PREVIOUS_RUN_ID), str(RUN_ID)]
    assert "delta" not in _json_keys(payload)
    assert "parameter_changes" not in _json_keys(payload)
    assert "user_adjustments" not in _json_keys(payload)


async def test_single_run_context_forces_cross_round_trend_null() -> None:
    provider = FakeProvider(
        json.dumps(_draft_payload(cross_round_trend="上一轮看起来更稳定。"), ensure_ascii=False)
    )
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    result = await service.coach(
        _request(previous_run_count=1), _auth_context(), reader=FakeReader()
    )

    assert result.context_run_ids == (RUN_ID,)
    assert result.cross_round_trend is None


async def test_provider_output_fail_closed_for_dead_values_privacy_and_trend_commitments() -> None:
    cases = [
        (_draft_payload(reading="请把 Kp 调到 5。"), FakeReader()),
        (_draft_payload(reading="我已经运行仿真并确认问题。"), FakeReader()),
        (_draft_payload(reading="路径 C:/Users/alice/private/model.slx 暴露。"), FakeReader()),
        (
            _draft_payload(cross_round_trend="我已经确认前序轮更稳定。"),
            FakeReader(
                snapshots=(
                    _snapshot(run_id=PREVIOUS_RUN_ID, run_sequence=6),
                    _snapshot(run_id=RUN_ID, run_sequence=7),
                )
            ),
        ),
    ]

    for draft, reader in cases:
        provider = FakeProvider(json.dumps(draft, ensure_ascii=False))
        service = BridgeRunStateCoachingService(
            provider,
            slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
        )

        with pytest.raises(BridgeRunStateCoachingFailedError):
            await service.coach(_request(previous_run_count=1), _auth_context(), reader=reader)


async def test_provider_timeout_maps_to_timeout_after_final_fence() -> None:
    provider = FakeProvider(exc=LLMTimeoutError("timeout"))
    reader = FakeReader()
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    with pytest.raises(BridgeRunStateCoachingTimeoutError):
        await service.coach(_request(), _auth_context(), reader=reader)
    assert reader.fence_calls == 2


async def test_server_deadline_times_out_retained_provider_attempt() -> None:
    release_provider = threading.Event()
    provider = FakeProvider(block_event=release_provider)
    reader = FakeReader()
    service = BridgeRunStateCoachingService(
        provider,
        server_deadline_s=0.01,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    try:
        with pytest.raises(BridgeRunStateCoachingTimeoutError):
            await service.coach(_request(), _auth_context(), reader=reader)
        assert reader.fence_calls == 2
        with pytest.raises(BridgeRunStateCoachingBusyError):
            await service.coach(_request(), _auth_context(), reader=FakeReader())
    finally:
        release_provider.set()
        await asyncio_sleep(0.05)


async def test_pre_send_fence_rejects_before_provider_call() -> None:
    provider = FakeProvider()
    reader = FakeReader(reject_on_fence=True)
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )

    with pytest.raises(CoachingRunStateReadRejectedError, match="session_terminal"):
        await service.coach(_request(), _auth_context(), reader=reader)
    assert provider.calls == 0
    assert reader.read_calls == 1
    assert reader.fence_calls == 1


async def test_in_flight_session_is_busy_until_provider_attempt_settles() -> None:
    release_provider = threading.Event()
    provider = FakeProvider(block_event=release_provider)
    service = BridgeRunStateCoachingService(
        provider,
        slot_manager=CoachingAttemptSlotManager(ttl_seconds=10),
    )
    first = asyncio_create(service.coach(_request(), _auth_context(), reader=FakeReader()))
    await _wait_until(lambda: provider.calls == 1)

    with pytest.raises(BridgeRunStateCoachingBusyError):
        await service.coach(_request(), _auth_context(), reader=FakeReader())

    release_provider.set()
    await first


async def test_attempt_slot_compare_and_release_blocks_lease_aba_and_orphan_overflow() -> None:
    manager = CoachingAttemptSlotManager(ttl_seconds=0.01, orphan_limit=1)
    first = await manager.acquire("session")
    assert first is not None
    await asyncio_sleep(0.02)
    second = await manager.acquire("session")
    assert second is not None
    await manager.release("session", first)

    assert await manager.acquire("session") is None
    await manager.release("session", second)

    overflow = CoachingAttemptSlotManager(ttl_seconds=0.01, orphan_limit=1)
    first = await overflow.acquire("session")
    assert first is not None
    await asyncio_sleep(0.02)
    second = await overflow.acquire("session")
    assert second is not None
    await asyncio_sleep(0.02)
    assert await overflow.acquire("session") is None


def test_service_source_uses_provider_task_shield_and_avoids_logger_exception() -> None:
    source = Path("features/matlab_bridge/bridge_run_state_coaching_service.py").read_text(
        encoding="utf-8"
    )

    assert "asyncio.shield(provider_task)" in source
    assert "asyncio.wait_for(\n                asyncio.to_thread" not in source
    assert "logger.exception" not in source


def _request(**overrides: object) -> BridgeRunStateCoachingRequest:
    payload: dict[str, object] = {
        "protocol_version": "0.3-c1",
        "request_id": REQUEST_ID,
        "session_id": SESSION_ID,
        "run_id": RUN_ID,
        "run_state_coaching_consent_confirmed": True,
        "coaching_consent_notice_version": "run_state_coaching_v1",
        "previous_run_count": 0,
    }
    payload.update(overrides)
    return BridgeRunStateCoachingRequest(**payload)  # type: ignore[arg-type]


def _auth_context() -> BridgeAuthContext:
    now = datetime.now(UTC)
    return BridgeAuthContext(
        claims=BridgeAuthClaims(
            issuer="issuer",
            audience="audience",
            subject="user-alpha",
            user_id="user-alpha",
            project_id="project-alpha",
            session_id=str(SESSION_ID),
            capabilities=frozenset({"run_state:explain"}),
            token_id="token-id",
            issued_at=now,
            not_before=now,
            expires_at=now + timedelta(minutes=5),
            process_generation="generation-1",
        )
    )


def _snapshot(
    *,
    run_id: UUID = RUN_ID,
    run_sequence: int = 7,
    run_status: str = "completed",
    convergence_status: str = "not_applicable",
    metrics: tuple[CoachingRunStateMetric, ...] | None = None,
    series: tuple[CoachingRunStateSeries, ...] | None = None,
) -> CoachingRunStateSnapshot:
    return CoachingRunStateSnapshot(
        run_id=run_id,
        request_id=REQUEST_ID,
        run_sequence=run_sequence,
        matlab_release="R2026a",
        client_version="0.1.0",
        run_status=run_status,
        convergence_status=convergence_status,
        stop_reason="ReachedStopTime",
        solver="ode45",
        metrics_status="available" if metrics is not None or run_status != "unknown" else "unknown",
        metrics=metrics
        if metrics is not None
        else (
            CoachingRunStateMetric(
                name="wall_clock_elapsed",
                value=1.25,
                unit_status="known",
                unit="s",
            ),
        ),
        series_status="available" if series is not None or run_status != "unknown" else "unknown",
        series=series
        if series is not None
        else (
            CoachingRunStateSeries(
                series_id="simout",
                label="simout",
                representation="identity_uniform_v1",
                time_unit="s",
                value_unit_status="unknown",
                source_point_count=4,
                t_start=0.0,
                sample_min=-1.0,
                sample_max=1.0,
                value_unit=None,
            ),
        ),
        received_at=datetime.now(UTC),
    )


def _draft_payload(
    *,
    reading: str = "wall_clock_elapsed 和 simout 摘要说明本轮有可观察信号。",
    cross_round_trend: str | None = None,
) -> dict[str, object]:
    return {
        "outcome": "coached",
        "signal_readings": [
            {
                "reading_id": "r1",
                "reading": reading,
                "is_inference": True,
                "confidence": "medium",
                "evidence_ids": ["e1"],
            }
        ],
        "primary_directions": [
            {
                "action": "compare",
                "magnitude_band": "slight",
                "rationale_reading_id": "r1",
                "alternatives": [
                    {
                        "action": "hold",
                        "magnitude_band": "slight",
                        "rationale_reading_id": "r1",
                    }
                ],
            }
        ],
        "cross_round_trend": cross_round_trend,
        "uncertainties": [],
        "fallback_reason": None,
    }


def _provider_context_payload(provider: FakeProvider) -> dict[str, object]:
    content = provider.messages[1].content
    start_marker = "```json typed-data:run_state_observations"
    start = content.index(start_marker) + len(start_marker)
    end = content.index("```", start)
    return json.loads(content[start:end].strip())


def _json_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for nested in value.values():
            keys.update(_json_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(_json_keys(nested))
        return keys
    return set()


def asyncio_create(coro):
    import asyncio

    return asyncio.create_task(coro)


async def asyncio_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def _wait_until(predicate) -> None:
    deadline = time.monotonic() + 2
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition did not become true")
        await asyncio_sleep(0.01)
