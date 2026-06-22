"""Real MATLAB Engine substrate checks.

Set ``MXA_RUN_MATLAB_ENGINE=1`` to opt in. When the env var is set, missing
``matlabengine`` must fail collection instead of skipping.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

RUN_ENGINE = os.getenv("MXA_RUN_MATLAB_ENGINE") == "1"
if not RUN_ENGINE:
    pytest.skip("Set MXA_RUN_MATLAB_ENGINE=1 to run.", allow_module_level=True)

import matlab.engine as matlab_engine  # noqa: E402

from adapters.matlab_engine.runtime import (  # noqa: E402
    MatlabEngineOwnership,
    MatlabEngineSession,
    MatlabEngineState,
)
from core.domain.exceptions import (  # noqa: E402
    MatlabEngineCancelledError,
    MatlabEngineExecutionError,
    MatlabEngineTimeoutError,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

TRIVIAL_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "matlab_engine" / "mxa_trivial_sim_fixture.m"
)


def test_matlab_engine_module_imported_after_opt_in() -> None:
    assert matlab_engine is not None


def test_start_owned_probe_and_trivial_sim() -> None:
    session = MatlabEngineSession.start_owned()
    try:
        assert session.ownership == MatlabEngineOwnership.OWNED
        assert session.startup_latency_s is not None
        capability = session.probe_simulink_capability()
        assert capability.license_available is True
        assert capability.simulink_version

        result = session.run_simulation(TRIVIAL_FIXTURE, timeout_s=120.0)

        assert result.stop_time == 1.0
        assert result.sample_count == 11
        assert result.final_value == 2.0
        assert session.state == MatlabEngineState.READY
    finally:
        session.close()


def test_execution_error_is_typed_and_sanitized(tmp_path: Path) -> None:
    fixture = tmp_path / "mxa_failing_fixture.m"
    fixture.write_text(
        "\n".join(
            [
                "function result = mxa_failing_fixture()",
                "error('mxa:failure', 'F:\\secret\\model_name leaked');",
                "result = struct('stop_time', 0, 'sample_count', 0, 'final_value', 0);",
                "end",
                "",
            ]
        ),
        encoding="utf-8",
    )
    session = MatlabEngineSession.start_owned()
    try:
        with pytest.raises(MatlabEngineExecutionError) as exc_info:
            session.run_simulation(fixture, timeout_s=10.0)
        assert exc_info.value.reason_code == "matlab_engine_execution_failed"
        assert "secret" not in str(exc_info.value)
        assert "model_name" not in repr(exc_info.value)
        assert exc_info.value.__cause__ is None
    finally:
        session.close()


def test_timeout_and_cancel_use_future_layer(tmp_path: Path) -> None:
    fixture = tmp_path / "mxa_long_fixture.m"
    fixture.write_text(
        "\n".join(
            [
                "function result = mxa_long_fixture()",
                "pause(5);",
                "result = struct('stop_time', 1.0, 'sample_count', 11, 'final_value', 2.0);",
                "end",
                "",
            ]
        ),
        encoding="utf-8",
    )

    timeout_session = MatlabEngineSession.start_owned(poll_interval_s=0.1, cleanup_grace_s=5.0)
    try:
        with pytest.raises(MatlabEngineTimeoutError) as exc_info:
            timeout_session.run_simulation(fixture, timeout_s=0.5)
        assert "cancel_returned" in exc_info.value.diagnostic_metadata
        assert "health_probe_ok" in exc_info.value.diagnostic_metadata
    finally:
        if timeout_session.state != MatlabEngineState.CLOSED:
            timeout_session.close()

    cancel_session = MatlabEngineSession.start_owned(poll_interval_s=0.1, cleanup_grace_s=5.0)
    try:
        import threading

        cancel_event = threading.Event()
        cancel_event.set()
        with pytest.raises(MatlabEngineCancelledError) as exc_info:
            cancel_session.run_simulation(fixture, timeout_s=10.0, cancel_event=cancel_event)
        assert exc_info.value.diagnostic_metadata["cancel_returned"] is True
        assert "health_probe_ok" in exc_info.value.diagnostic_metadata
    finally:
        if cancel_session.state != MatlabEngineState.CLOSED:
            cancel_session.close()


def test_connect_shared_attached_close_does_not_stop_test_owned_session() -> None:
    name = f"mxa_t512_{uuid.uuid4().hex}"
    process = _start_external_shared_matlab(name)
    owner_pid: int | None = None

    try:
        attached = _connect_shared_with_retry(name)
        owner_pid = attached.matlab_process_id
        assert owner_pid is not None
        try:
            assert attached.ownership == MatlabEngineOwnership.ATTACHED
            assert attached.matlab_process_id == owner_pid
            attached.close()
            assert _pid_exists(owner_pid)
        finally:
            if attached.state != MatlabEngineState.CLOSED:
                attached.close()

        reattached = MatlabEngineSession.connect_shared(name)
        try:
            assert reattached.matlab_process_id == owner_pid
            reattached.close()
            assert _pid_exists(owner_pid)
        finally:
            if reattached.state != MatlabEngineState.CLOSED:
                reattached.close()
    finally:
        _terminate_process(process)
        if owner_pid is not None:
            assert _wait_pid_gone(owner_pid, timeout_s=20.0)


def test_two_owned_rounds_leave_no_residual_processes() -> None:
    for _ in range(2):
        session = MatlabEngineSession.start_owned()
        pid = session.matlab_process_id
        try:
            assert pid is not None
            result = session.run_simulation(TRIVIAL_FIXTURE, timeout_s=120.0)
            assert result.sample_count == 11
        finally:
            if session.state != MatlabEngineState.CLOSED:
                session.close()
        assert _wait_pid_gone(pid)


def _connect_shared_with_retry(name: str, timeout_s: float = 60.0) -> MatlabEngineSession:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return MatlabEngineSession.connect_shared(name)
        except Exception as exc:
            last_error = exc
            time.sleep(1.0)
    if last_error is not None:
        raise last_error
    raise RuntimeError("connect_shared retry deadline expired")


def _start_external_shared_matlab(name: str) -> subprocess.Popen[bytes]:
    matlab_exe = os.getenv("MXA_MATLAB_EXE") or shutil.which("matlab")
    if matlab_exe is None:
        fallback = Path("F:/Matlab/bin/matlab.exe")
        matlab_exe = str(fallback) if fallback.is_file() else None
    if matlab_exe is None:
        raise RuntimeError("MATLAB executable not found")

    command = f"matlab.engine.shareEngine('{name}');"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [matlab_exe, "-nosplash", "-nodesktop", "-r", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()


def _wait_pid_gone(pid: int, timeout_s: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return True
        time.sleep(0.25)
    return not _pid_exists(pid)


def _pid_exists(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            check=False,
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return False
    return True
