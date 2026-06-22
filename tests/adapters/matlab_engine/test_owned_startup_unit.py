from __future__ import annotations

from collections.abc import Callable

import pytest

from adapters.matlab_engine import owned_startup
from adapters.matlab_engine.runtime import MatlabEngineOwnership
from core.domain.exceptions import (
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
    MatlabEngineUnavailableError,
)


class _FakeProcess:
    def __init__(self, pid: int = 1234) -> None:
        self.pid = pid


class _FakeUuid:
    hex = "abc123"


class _FakeFuture:
    def __init__(self, value: object | None = None, exc: Exception | None = None) -> None:
        self.value = value
        self.exc = exc
        self.timeouts: list[float] = []
        self.cancel_calls = 0

    def result(self, *, timeout: float) -> object:
        self.timeouts.append(timeout)
        if self.exc is not None:
            raise self.exc
        return self.value

    def cancel(self) -> bool:
        self.cancel_calls += 1
        return True


class _FakeEngine:
    def __init__(self, pid_future: _FakeFuture | None = None) -> None:
        self.pid_future = pid_future or _FakeFuture(4321)
        self.matlabProcessID = None
        self.feval_calls: list[tuple[str, int, bool]] = []
        self.sqrt_calls = 0
        self.quit_calls = 0

    def feval(self, function_name: str, *, nargout: int, background: bool) -> _FakeFuture:
        self.feval_calls.append((function_name, nargout, background))
        return self.pid_future

    def sqrt(self, value: float, *, nargout: int) -> float:
        assert (value, nargout) == (4.0, 1)
        self.sqrt_calls += 1
        return 2.0

    def quit(self, *, nargout: int = 0) -> None:
        assert nargout == 0
        self.quit_calls += 1


class _FakeMatlabModule:
    def __init__(
        self,
        *,
        names: list[str],
        connect_future: _FakeFuture,
    ) -> None:
        self.names = names
        self.connect_future = connect_future
        self.connect_calls: list[tuple[str, bool]] = []

    def find_matlab(self) -> list[str]:
        return self.names

    def connect_matlab(self, name: str, *, background: bool) -> _FakeFuture:
        self.connect_calls.append((name, background))
        return self.connect_future


@pytest.fixture
def win32_startup(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    order: list[str] = []
    monkeypatch.setattr(owned_startup.sys, "platform", "win32")
    monkeypatch.setattr(owned_startup.uuid, "uuid4", lambda: _FakeUuid())

    def launch(*, share_name: str, log_path: object) -> _FakeProcess:
        _ = share_name, log_path
        order.append("launch")
        return _FakeProcess()

    monkeypatch.setattr(owned_startup, "_launch_owned_matlab_process", launch)
    return order


def test_non_windows_guard_raises_before_sdk_or_popen(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(owned_startup.sys, "platform", "linux")
    monkeypatch.setattr(
        owned_startup,
        "_load_matlab_engine_module",
        lambda: calls.append("load"),
    )
    monkeypatch.setattr(
        owned_startup,
        "_launch_owned_matlab_process",
        lambda **_kwargs: calls.append("launch"),
    )

    with pytest.raises(MatlabEngineUnavailableError) as exc_info:
        owned_startup.start_owned_bounded()

    assert exc_info.value.reason_code == "owned_startup_unsupported_platform"
    assert calls == []


def test_start_owned_bounded_success_uses_sdk_before_launch(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    fake_engine = _FakeEngine()
    connect_future = _FakeFuture(fake_engine)
    fake_module = _FakeMatlabModule(
        names=["task513_abc123"],
        connect_future=connect_future,
    )

    def load_module() -> _FakeMatlabModule:
        win32_startup.append("load")
        return fake_module

    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", load_module)
    monkeypatch.setattr(owned_startup, "_is_pid_in_process_tree", lambda root, pid: True)

    runtime = owned_startup.start_owned_bounded(startup_timeout_s=1.0, poll_interval_s=0.001)
    try:
        assert win32_startup == ["load", "launch"]
        assert runtime.share_name == "task513_abc123"
        assert runtime.session.ownership == MatlabEngineOwnership.OWNED
        assert runtime.session.matlab_process_id == 4321
        assert fake_module.connect_calls == [("task513_abc123", True)]
        assert fake_engine.feval_calls == [("matlabProcessID", 1, True)]
        assert connect_future.timeouts
        assert runtime.provider.health_probe() is None
    finally:
        runtime.cleanup_log_file()


def test_startup_timeout_reaps_owned_tree(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    fake_module = _FakeMatlabModule(names=[], connect_future=_FakeFuture(_FakeEngine()))
    reaped: list[int] = []
    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", lambda: fake_module)
    monkeypatch.setattr(
        owned_startup,
        "_terminate_process_tree",
        _recording_reaper(reaped, result=True),
    )

    with pytest.raises(MatlabEngineTimeoutError) as exc_info:
        owned_startup.start_owned_bounded(startup_timeout_s=0.001, poll_interval_s=0.001)

    assert exc_info.value.reason_code == "startup_timeout_reaped"
    assert reaped == [1234]


def test_connect_timeout_cancels_future_and_reaps(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    connect_future = _FakeFuture(exc=TimeoutError("connect still running"))
    fake_module = _FakeMatlabModule(names=["task513_abc123"], connect_future=connect_future)
    reaped: list[int] = []
    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", lambda: fake_module)
    monkeypatch.setattr(
        owned_startup,
        "_terminate_process_tree",
        _recording_reaper(reaped, result=True),
    )

    with pytest.raises(MatlabEngineTimeoutError) as exc_info:
        owned_startup.start_owned_bounded(startup_timeout_s=1.0, poll_interval_s=0.001)

    assert exc_info.value.reason_code == "startup_timeout_reaped"
    assert connect_future.cancel_calls == 1
    assert reaped == [1234]


def test_connect_failure_reaps_and_raises_startup(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    fake_module = _FakeMatlabModule(
        names=["task513_abc123"],
        connect_future=_FakeFuture(exc=RuntimeError("raw path F:/secret")),
    )
    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", lambda: fake_module)
    monkeypatch.setattr(
        owned_startup,
        "_terminate_process_tree",
        _recording_reaper([], result=True),
    )

    with pytest.raises(MatlabEngineStartupError) as exc_info:
        owned_startup.start_owned_bounded(startup_timeout_s=1.0, poll_interval_s=0.001)

    assert exc_info.value.reason_code == "startup_connect_failed"
    assert "secret" not in str(exc_info.value)


def test_pid_attestation_failure_reaps_and_raises_startup(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    fake_engine = _FakeEngine(pid_future=_FakeFuture(9999))
    fake_module = _FakeMatlabModule(
        names=["task513_abc123"],
        connect_future=_FakeFuture(fake_engine),
    )
    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", lambda: fake_module)
    monkeypatch.setattr(owned_startup, "_is_pid_in_process_tree", lambda root, pid: False)
    monkeypatch.setattr(
        owned_startup,
        "_terminate_process_tree",
        _recording_reaper([], result=True),
    )

    with pytest.raises(MatlabEngineStartupError) as exc_info:
        owned_startup.start_owned_bounded(startup_timeout_s=1.0, poll_interval_s=0.001)

    assert exc_info.value.reason_code == "startup_pid_attestation_failed"


def test_reaper_failure_uses_frozen_reason_code(
    monkeypatch: pytest.MonkeyPatch,
    win32_startup: list[str],
) -> None:
    fake_module = _FakeMatlabModule(names=[], connect_future=_FakeFuture(_FakeEngine()))
    monkeypatch.setattr(owned_startup, "_load_matlab_engine_module", lambda: fake_module)
    monkeypatch.setattr(
        owned_startup,
        "_terminate_process_tree",
        _recording_reaper([], result=False),
    )

    with pytest.raises(MatlabEngineStartupError) as exc_info:
        owned_startup.start_owned_bounded(startup_timeout_s=0.001, poll_interval_s=0.001)

    assert exc_info.value.reason_code == "startup_reaper_failed"


def _recording_reaper(
    seen: list[int],
    *,
    result: bool,
) -> Callable[..., bool]:
    def reaper(pid: int, *, timeout_s: float, poll_interval_s: float) -> bool:
        assert timeout_s > 0
        assert poll_interval_s > 0
        seen.append(pid)
        return result

    return reaper
