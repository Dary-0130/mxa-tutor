"""CI-safe MATLAB Engine substrate unit tests with fake engine objects."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.matlab_engine import runtime
from adapters.matlab_engine.runtime import (
    MatlabEngineOwnership,
    MatlabEngineSession,
    MatlabEngineState,
)
from core.domain.exceptions import (
    MatlabEngineBusyError,
    MatlabEngineCancelledError,
    MatlabEngineCapabilityError,
    MatlabEngineConnectionError,
    MatlabEngineExecutionError,
    MatlabEngineSessionError,
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
    MatlabEngineUnavailableError,
)


class FakeFuture:
    def __init__(
        self,
        result_value: object | None = None,
        *,
        result_exception: Exception | None = None,
        always_timeout: bool = False,
        cancel_return: bool = True,
        done_initially: bool = False,
    ) -> None:
        self.result_value = result_value if result_value is not None else _valid_result()
        self.result_exception = result_exception
        self.always_timeout = always_timeout
        self.cancel_return = cancel_return
        self._done = done_initially
        self._cancelled = False
        self.result_timeouts: list[float | None] = []
        self.cancel_calls = 0

    def result(self, timeout: float | None = None) -> object:
        self.result_timeouts.append(timeout)
        if self.always_timeout and not self._done:
            raise TimeoutError("fake future still running")
        self._done = True
        if self.result_exception is not None:
            raise self.result_exception
        return self.result_value

    def cancel(self) -> bool:
        self.cancel_calls += 1
        if self.cancel_return:
            self._cancelled = True
            self._done = True
        return self.cancel_return

    def done(self) -> bool:
        return self._done

    def cancelled(self) -> bool:
        return self._cancelled


class FakeEngine:
    def __init__(
        self,
        future: FakeFuture | None = None,
        *,
        simulink_version: object = None,
        license_available: bool = True,
        health_ok: bool = True,
        feval_exception: Exception | None = None,
        quit_exception: Exception | None = None,
        disconnect_exception: Exception | None = None,
        quit_delay_s: float = 0.0,
        disconnect_delay_s: float = 0.0,
        pid: int | None = None,
    ) -> None:
        self.future = future or FakeFuture()
        self.simulink_version = (
            {"Name": "Simulink", "Version": "26.1"}
            if simulink_version is None
            else simulink_version
        )
        self.license_available = license_available
        self.health_ok = health_ok
        self.feval_exception = feval_exception
        self.quit_exception = quit_exception
        self.disconnect_exception = disconnect_exception
        self.quit_delay_s = quit_delay_s
        self.disconnect_delay_s = disconnect_delay_s
        self.matlabProcessID = pid
        self.addpath_calls: list[str] = []
        self.feval_calls: list[tuple[str, int, bool]] = []
        self.sqrt_calls = 0
        self.quit_calls = 0
        self.disconnect_calls = 0
        self.eval_calls: list[str] = []

    def addpath(self, path: str, *, nargout: int) -> None:
        assert nargout == 0
        self.addpath_calls.append(path)

    def feval(self, function_name: str, *, nargout: int, background: bool) -> FakeFuture:
        self.feval_calls.append((function_name, nargout, background))
        if self.feval_exception is not None:
            raise self.feval_exception
        return self.future

    def ver(self, product: str, *, nargout: int) -> object:
        assert product == "simulink"
        assert nargout == 1
        return self.simulink_version

    def license(self, action: str, product: str, *, nargout: int) -> bool:
        assert (action, product, nargout) == ("test", "Simulink", 1)
        return self.license_available

    def sqrt(self, value: float, *, nargout: int) -> float:
        assert (value, nargout) == (4.0, 1)
        self.sqrt_calls += 1
        if not self.health_ok:
            raise RuntimeError("health path F:\\secret\\model.slx")
        return 2.0

    def eval(self, command: str, *, nargout: int) -> None:
        assert nargout == 0
        self.eval_calls.append(command)

    def quit(self, *, nargout: int = 0) -> None:
        assert nargout == 0
        self.quit_calls += 1
        if self.quit_delay_s > 0:
            import time

            time.sleep(self.quit_delay_s)
        if self.quit_exception is not None:
            raise self.quit_exception

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.disconnect_delay_s > 0:
            import time

            time.sleep(self.disconnect_delay_s)
        if self.disconnect_exception is not None:
            raise self.disconnect_exception


def _valid_result() -> dict[str, float]:
    return {"stop_time": 1.0, "sample_count": 11.0, "final_value": 2.0}


@pytest.fixture
def fixture_file(tmp_path: Path) -> Path:
    fixture = tmp_path / "mxa_fake_fixture.m"
    fixture.write_text("function result = mxa_fake_fixture()\nend\n", encoding="utf-8")
    return fixture


def test_runtime_import_does_not_load_matlab_engine() -> None:
    sys.modules.pop("matlab.engine", None)

    importlib.reload(runtime)

    assert "matlab.engine" not in sys.modules


def test_start_owned_missing_package_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_import(name: str) -> object:
        assert name == "matlab.engine"
        raise ModuleNotFoundError("F:\\secret\\matlabengine")

    monkeypatch.setattr(runtime.importlib, "import_module", fail_import)

    with pytest.raises(MatlabEngineUnavailableError) as exc_info:
        MatlabEngineSession.start_owned()

    assert exc_info.value.reason_code == "matlab_engine_unavailable"
    assert "secret" not in str(exc_info.value)


def test_startup_failure_translates_without_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(
        start_matlab=lambda: (_ for _ in ()).throw(RuntimeError("C:\\secret\\startup.m"))
    )
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: fake_module)

    with pytest.raises(MatlabEngineStartupError) as exc_info:
        MatlabEngineSession.start_owned()

    assert exc_info.value.reason_code == "matlab_engine_startup_failed"
    assert "secret" not in repr(exc_info.value)


def test_connect_shared_uses_explicit_name(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def connect_matlab(name: str) -> FakeEngine:
        calls.append(name)
        return FakeEngine()

    fake_module = SimpleNamespace(connect_matlab=connect_matlab)
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: fake_module)

    session = MatlabEngineSession.connect_shared("mxa_shared_unit")

    assert calls == ["mxa_shared_unit"]
    assert session.ownership == MatlabEngineOwnership.ATTACHED


def test_connect_shared_failure_translates(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(
        connect_matlab=lambda name: (_ for _ in ()).throw(RuntimeError("shared secret"))
    )
    monkeypatch.setattr(runtime.importlib, "import_module", lambda name: fake_module)

    with pytest.raises(MatlabEngineConnectionError) as exc_info:
        MatlabEngineSession.connect_shared("mxa_missing")

    assert exc_info.value.reason_code == "matlab_engine_connection_failed"
    assert "secret" not in str(exc_info.value)


def test_probe_simulink_missing_raises_capability() -> None:
    session = MatlabEngineSession(
        FakeEngine(simulink_version=[]),
        ownership=MatlabEngineOwnership.OWNED,
    )

    with pytest.raises(MatlabEngineCapabilityError) as exc_info:
        session.probe_simulink_capability()

    assert exc_info.value.reason_code == "simulink_unavailable"


def test_probe_simulink_license_missing_raises_capability() -> None:
    session = MatlabEngineSession(
        FakeEngine(license_available=False),
        ownership=MatlabEngineOwnership.OWNED,
    )

    with pytest.raises(MatlabEngineCapabilityError) as exc_info:
        session.probe_simulink_capability()

    assert exc_info.value.reason_code == "simulink_license_unavailable"


def test_run_simulation_success(fixture_file: Path) -> None:
    fake_engine = FakeEngine(FakeFuture(_valid_result()))
    session = MatlabEngineSession(fake_engine, ownership=MatlabEngineOwnership.OWNED)

    result = session.run_simulation(fixture_file, timeout_s=1.0)

    assert result.stop_time == 1.0
    assert result.sample_count == 11
    assert result.final_value == 2.0
    assert fake_engine.feval_calls == [("mxa_fake_fixture", 1, True)]
    assert fake_engine.addpath_calls == [str(fixture_file.parent)]
    assert session.state == MatlabEngineState.READY


def test_execution_error_translates_without_raw_matlab_text(fixture_file: Path) -> None:
    future = FakeFuture(result_exception=RuntimeError("F:\\secret\\model.slx failed"))
    session = MatlabEngineSession(FakeEngine(future), ownership=MatlabEngineOwnership.OWNED)

    with pytest.raises(MatlabEngineExecutionError) as exc_info:
        session.run_simulation(fixture_file, timeout_s=1.0)

    assert exc_info.value.reason_code == "matlab_engine_execution_failed"
    assert "secret" not in str(exc_info.value)
    assert "model.slx" not in repr(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_timeout_calls_cancel_and_restores_ready_when_health_probe_passes(
    fixture_file: Path,
) -> None:
    future = FakeFuture(always_timeout=True, cancel_return=True)
    fake_engine = FakeEngine(future)
    session = MatlabEngineSession(
        fake_engine,
        ownership=MatlabEngineOwnership.OWNED,
        poll_interval_s=0.001,
        cleanup_grace_s=0.001,
    )

    with pytest.raises(MatlabEngineTimeoutError) as exc_info:
        session.run_simulation(fixture_file, timeout_s=0.002)

    assert future.cancel_calls == 1
    assert exc_info.value.diagnostic_metadata["cancel_returned"] is True
    assert exc_info.value.diagnostic_metadata["health_probe_ok"] is True
    assert fake_engine.sqrt_calls == 1
    assert session.state == MatlabEngineState.READY


def test_timeout_cancel_false_breaks_and_recovers_by_ownership(fixture_file: Path) -> None:
    future = FakeFuture(always_timeout=True, cancel_return=False)
    fake_engine = FakeEngine(future)
    session = MatlabEngineSession(
        fake_engine,
        ownership=MatlabEngineOwnership.OWNED,
        poll_interval_s=0.001,
        cleanup_grace_s=0.001,
    )

    with pytest.raises(MatlabEngineTimeoutError) as exc_info:
        session.run_simulation(fixture_file, timeout_s=0.002)

    assert future.cancel_calls == 1
    assert exc_info.value.diagnostic_metadata["cancel_returned"] is False
    assert fake_engine.quit_calls == 1
    assert session.state == MatlabEngineState.CLOSED


def test_cancel_event_cancels_future_via_public_api(fixture_file: Path) -> None:
    future = FakeFuture(always_timeout=True, cancel_return=True)
    fake_engine = FakeEngine(future)
    session = MatlabEngineSession(
        fake_engine,
        ownership=MatlabEngineOwnership.OWNED,
        poll_interval_s=0.001,
        cleanup_grace_s=0.001,
    )
    import threading

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(MatlabEngineCancelledError) as exc_info:
        session.run_simulation(fixture_file, timeout_s=1.0, cancel_event=cancel_event)

    assert future.cancel_calls == 1
    assert exc_info.value.diagnostic_metadata["cancel_returned"] is True
    assert session.state == MatlabEngineState.READY


def test_busy_session_fails_immediately(fixture_file: Path) -> None:
    session = MatlabEngineSession(FakeEngine(), ownership=MatlabEngineOwnership.OWNED)
    assert session._call_lock.acquire(blocking=False)
    try:
        with pytest.raises(MatlabEngineBusyError):
            session.run_simulation(fixture_file, timeout_s=1.0)
    finally:
        session._call_lock.release()


def test_close_owned_and_attached_are_idempotent() -> None:
    owned_engine = FakeEngine()
    attached_engine = FakeEngine()
    owned = MatlabEngineSession(owned_engine, ownership=MatlabEngineOwnership.OWNED)
    attached = MatlabEngineSession(attached_engine, ownership=MatlabEngineOwnership.ATTACHED)

    owned.close()
    owned.close()
    attached.close()
    attached.close()

    assert owned_engine.quit_calls == 1
    assert attached_engine.disconnect_calls == 0
    assert attached_engine.quit_calls == 1
    assert owned.state == MatlabEngineState.CLOSED
    assert attached.state == MatlabEngineState.CLOSED


def test_owned_can_terminate_after_grace_attached_never_terminates() -> None:
    terminated: list[int] = []

    def terminator(pid: int, timeout_s: float) -> bool:
        terminated.append(pid)
        assert timeout_s == 0.001
        return True

    owned = MatlabEngineSession(
        FakeEngine(quit_delay_s=0.02, pid=4242),
        ownership=MatlabEngineOwnership.OWNED,
        cleanup_grace_s=0.001,
        process_terminator=terminator,
    )
    attached = MatlabEngineSession(
        FakeEngine(quit_delay_s=0.02, pid=5555),
        ownership=MatlabEngineOwnership.ATTACHED,
        cleanup_grace_s=0.001,
        process_terminator=terminator,
    )

    owned.close()
    with pytest.raises(MatlabEngineSessionError):
        attached.close()

    assert terminated == [4242]
    assert attached.state == MatlabEngineState.BROKEN


def test_closed_session_rejects_calls(fixture_file: Path) -> None:
    session = MatlabEngineSession(FakeEngine(), ownership=MatlabEngineOwnership.OWNED)
    session.close()

    with pytest.raises(MatlabEngineSessionError):
        session.run_simulation(fixture_file, timeout_s=1.0)


def test_context_manager_does_not_mask_block_exception() -> None:
    session = MatlabEngineSession(
        FakeEngine(quit_exception=RuntimeError("F:\\secret\\quit.m")),
        ownership=MatlabEngineOwnership.OWNED,
    )

    with pytest.raises(ValueError, match="body failed"), session:
        raise ValueError("body failed")


def test_share_as_uses_eval_without_loading_matlab_module() -> None:
    fake_engine = FakeEngine()
    session = MatlabEngineSession(fake_engine, ownership=MatlabEngineOwnership.OWNED)

    session.share_as("mxa_shared_unit")

    assert fake_engine.eval_calls == ["matlab.engine.shareEngine('mxa_shared_unit')"]


def test_from_connected_owned_wraps_existing_engine_with_owned_pid() -> None:
    fake_engine = FakeEngine(pid=None)

    session = MatlabEngineSession.from_connected_owned(fake_engine, matlab_process_id=9876)

    assert session.ownership == MatlabEngineOwnership.OWNED
    assert session.matlab_process_id == 9876
    assert session.state == MatlabEngineState.READY
