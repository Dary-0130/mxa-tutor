"""Synchronous MATLAB Engine substrate adapter.

The adapter is intentionally synchronous. Async callers should bridge calls with
``asyncio.to_thread`` and pass a ``threading.Event`` for cancellation.
"""

from __future__ import annotations

import importlib
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from core.domain.exceptions import (
    MatlabEngineBusyError,
    MatlabEngineCancelledError,
    MatlabEngineCapabilityError,
    MatlabEngineConnectionError,
    MatlabEngineError,
    MatlabEngineExecutionError,
    MatlabEngineSessionError,
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
    MatlabEngineUnavailableError,
)

DEFAULT_POLL_INTERVAL_S = 0.1
DEFAULT_CLEANUP_GRACE_S = 5.0

ProcessTerminator = Callable[[int, float], bool]


class MatlabEngineOwnership(StrEnum):
    """Ownership model for a MATLAB Engine connection."""

    OWNED = "owned"
    ATTACHED = "attached"


class MatlabEngineState(StrEnum):
    """Lifecycle state for one MATLAB Engine session wrapper."""

    NEW = "new"
    READY = "ready"
    BUSY = "busy"
    BROKEN = "broken"
    CLOSED = "closed"


@dataclass(frozen=True)
class MatlabSimulationResult:
    """Deterministic result returned by the trivial Simulink fixture."""

    stop_time: float
    sample_count: int
    final_value: float


@dataclass(frozen=True)
class MatlabSimulinkCapability:
    """Simulink installation and license probe result."""

    simulink_version: str
    license_available: bool


@dataclass(frozen=True)
class MatlabFutureRecovery:
    """Sanitized metadata from cancelling or timing out a FutureResult."""

    cancel_returned: bool | None
    health_probe_ok: bool
    future_done_before_cancel: bool


class MatlabEngineSession:
    """One synchronous MATLAB Engine session wrapper.

    A wrapper permits at most one in-flight MATLAB call. It fails immediately
    with ``MatlabEngineBusyError`` instead of queueing.
    """

    def __init__(
        self,
        engine: Any,
        *,
        ownership: MatlabEngineOwnership,
        startup_latency_s: float | None = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
        process_terminator: ProcessTerminator | None = None,
    ) -> None:
        if poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")
        if cleanup_grace_s <= 0:
            raise ValueError("cleanup_grace_s must be positive")

        self._engine = engine
        self._ownership = ownership
        self._startup_latency_s = startup_latency_s
        self._poll_interval_s = poll_interval_s
        self._cleanup_grace_s = cleanup_grace_s
        self._process_terminator = process_terminator or _terminate_process
        self._state = MatlabEngineState.READY
        self._call_lock = threading.Lock()
        self._matlab_process_id = _coerce_pid(_read_engine_pid(engine))

    @classmethod
    def start_owned(
        cls,
        *,
        startup_options: str | None = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
        process_terminator: ProcessTerminator | None = None,
    ) -> MatlabEngineSession:
        """Start a MATLAB process owned by this wrapper."""
        matlab_engine = _load_matlab_engine_module()
        started = time.perf_counter()
        try:
            if startup_options is None:
                engine = matlab_engine.start_matlab()
            else:
                engine = matlab_engine.start_matlab(startup_options)
        except Exception as exc:
            raise MatlabEngineStartupError(
                "matlab_engine_startup_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None

        return cls(
            engine,
            ownership=MatlabEngineOwnership.OWNED,
            startup_latency_s=time.perf_counter() - started,
            poll_interval_s=poll_interval_s,
            cleanup_grace_s=cleanup_grace_s,
            process_terminator=process_terminator,
        )

    @classmethod
    def connect_shared(
        cls,
        name: str,
        *,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
        process_terminator: ProcessTerminator | None = None,
    ) -> MatlabEngineSession:
        """Connect to an explicitly named shared MATLAB session."""
        if not name.strip():
            raise ValueError("name must be non-empty")

        matlab_engine = _load_matlab_engine_module()
        try:
            engine = matlab_engine.connect_matlab(name)
        except Exception as exc:
            raise MatlabEngineConnectionError(
                "matlab_engine_connection_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None

        return cls(
            engine,
            ownership=MatlabEngineOwnership.ATTACHED,
            poll_interval_s=poll_interval_s,
            cleanup_grace_s=cleanup_grace_s,
            process_terminator=process_terminator,
        )

    @classmethod
    def from_connected_owned(
        cls,
        engine: Any,
        *,
        matlab_process_id: int,
    ) -> MatlabEngineSession:
        """Wrap an already-connected Engine handle with owned-session semantics."""
        session = cls(engine, ownership=MatlabEngineOwnership.OWNED)
        coerced_pid = _coerce_pid(matlab_process_id)
        if coerced_pid is None:
            raise ValueError("matlab_process_id must be a positive integer")
        session._matlab_process_id = coerced_pid
        return session

    @property
    def ownership(self) -> MatlabEngineOwnership:
        return self._ownership

    @property
    def state(self) -> MatlabEngineState:
        return self._state

    @property
    def startup_latency_s(self) -> float | None:
        return self._startup_latency_s

    @property
    def matlab_process_id(self) -> int | None:
        return self._matlab_process_id

    def probe_simulink_capability(self) -> MatlabSimulinkCapability:
        """Verify that Simulink is installed and the license can be checked out."""
        self._enter_call()
        try:
            return self._probe_simulink_capability_unlocked()
        finally:
            self._leave_call()

    def run_simulation(
        self,
        fixture_path: Path,
        *,
        timeout_s: float,
        cancel_event: threading.Event | None = None,
    ) -> MatlabSimulationResult:
        """Run a deterministic Simulink fixture through Engine FutureResult."""
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")

        fixture = Path(fixture_path)
        if fixture.suffix.lower() != ".m" or not fixture.is_file():
            raise ValueError("fixture_path must point to a MATLAB .m file")

        self._enter_call()
        try:
            self._probe_simulink_capability_unlocked()
            self._engine.addpath(str(fixture.parent), nargout=0)
            future = self._engine.feval(fixture.stem, nargout=1, background=True)
            raw_result = self._wait_for_future(
                future,
                deadline=time.monotonic() + timeout_s,
                cancel_event=cancel_event,
            )
            return _parse_simulation_result(raw_result)
        except MatlabEngineError:
            raise
        except Exception as exc:
            raise MatlabEngineExecutionError(
                "matlab_engine_execution_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None
        finally:
            self._leave_call()

    def share_as(self, name: str) -> None:
        """Share this session under a deterministic test-owned name."""
        if not name.strip():
            raise ValueError("name must be non-empty")

        self._enter_call()
        try:
            escaped = name.replace("'", "''")
            self._engine.eval(f"matlab.engine.shareEngine('{escaped}')", nargout=0)
        except MatlabEngineError:
            raise
        except Exception as exc:
            raise MatlabEngineExecutionError(
                "matlab_engine_share_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None
        finally:
            self._leave_call()

    def health_probe(self) -> bool:
        """Run a light Engine call to verify the session still responds."""
        self._enter_call()
        try:
            return self._health_probe_unlocked()
        finally:
            self._leave_call()

    def close(self) -> None:
        """Close the wrapper according to ownership; idempotent."""
        if self._state == MatlabEngineState.CLOSED:
            return

        if not self._call_lock.acquire(blocking=False):
            raise MatlabEngineBusyError("matlab_engine_session_busy") from None

        try:
            if self._state == MatlabEngineState.CLOSED:
                return
            if self._ownership == MatlabEngineOwnership.OWNED:
                self._close_owned_unlocked()
            else:
                self._close_attached_unlocked()
        finally:
            self._release_call_lock()

    def __enter__(self) -> MatlabEngineSession:
        self._require_open()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> Literal[False]:
        try:
            self.close()
        except MatlabEngineError as close_error:
            if exc_type is None:
                raise
            logger.error(
                "MATLAB Engine close failed after block error: ownership={} state={} "
                "reason_code={} close_error_type={}",
                self._ownership.value,
                self._state.value,
                close_error.reason_code,
                type(close_error).__name__,
            )
        return False

    def _enter_call(self) -> None:
        if not self._call_lock.acquire(blocking=False):
            raise MatlabEngineBusyError("matlab_engine_session_busy") from None
        try:
            self._require_ready()
            self._state = MatlabEngineState.BUSY
        except Exception:
            self._release_call_lock()
            raise

    def _leave_call(self) -> None:
        if self._state == MatlabEngineState.BUSY:
            self._state = MatlabEngineState.READY
        self._release_call_lock()

    def _release_call_lock(self) -> None:
        try:
            self._call_lock.release()
        except RuntimeError:
            logger.error(
                "MATLAB Engine lock release failed: ownership={} state={}",
                self._ownership.value,
                self._state.value,
            )

    def _require_open(self) -> None:
        if self._state == MatlabEngineState.CLOSED:
            raise MatlabEngineSessionError("matlab_engine_session_closed") from None

    def _require_ready(self) -> None:
        self._require_open()
        if self._state == MatlabEngineState.BROKEN:
            raise MatlabEngineSessionError("matlab_engine_session_broken") from None
        if self._state != MatlabEngineState.READY:
            raise MatlabEngineSessionError("matlab_engine_session_not_ready") from None

    def _probe_simulink_capability_unlocked(self) -> MatlabSimulinkCapability:
        try:
            version_output = self._engine.ver("simulink", nargout=1)
        except Exception as exc:
            raise MatlabEngineCapabilityError(
                "simulink_probe_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None

        version = _extract_simulink_version(version_output)
        if version is None:
            raise MatlabEngineCapabilityError("simulink_unavailable") from None

        try:
            license_available = bool(self._engine.license("test", "Simulink", nargout=1))
        except Exception as exc:
            raise MatlabEngineCapabilityError(
                "simulink_license_probe_failed",
                diagnostic_metadata={"exception_type": type(exc).__name__},
            ) from None

        if not license_available:
            raise MatlabEngineCapabilityError("simulink_license_unavailable") from None

        return MatlabSimulinkCapability(
            simulink_version=version,
            license_available=license_available,
        )

    def _wait_for_future(
        self,
        future: Any,
        *,
        deadline: float,
        cancel_event: threading.Event | None,
    ) -> Any:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                recovery = self._recover_interrupted_future(future)
                raise MatlabEngineCancelledError(
                    "matlab_engine_cancelled",
                    diagnostic_metadata=_recovery_metadata(recovery),
                ) from None

            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                recovery = self._recover_interrupted_future(future)
                raise MatlabEngineTimeoutError(
                    "matlab_engine_timeout",
                    diagnostic_metadata=_recovery_metadata(recovery),
                ) from None

            poll_s = min(self._poll_interval_s, remaining_s)
            try:
                return future.result(poll_s)
            except Exception as exc:
                if _is_timeout_error(exc):
                    continue
                if _is_cancelled_error(exc):
                    recovery = MatlabFutureRecovery(
                        cancel_returned=None,
                        health_probe_ok=self._health_probe_unlocked(),
                        future_done_before_cancel=True,
                    )
                    raise MatlabEngineCancelledError(
                        "matlab_engine_cancelled",
                        diagnostic_metadata=_recovery_metadata(recovery),
                    ) from None
                raise MatlabEngineExecutionError(
                    "matlab_engine_execution_failed",
                    diagnostic_metadata={"exception_type": type(exc).__name__},
                ) from None

    def _recover_interrupted_future(self, future: Any) -> MatlabFutureRecovery:
        done_before_cancel = _future_done(future)
        if done_before_cancel:
            _consume_completed_future(future)
            health_ok = self._health_probe_unlocked()
            self._state = MatlabEngineState.READY if health_ok else MatlabEngineState.BROKEN
            if not health_ok:
                self._recover_broken_session_unlocked()
            return MatlabFutureRecovery(
                cancel_returned=None,
                health_probe_ok=health_ok,
                future_done_before_cancel=True,
            )

        cancel_returned = _future_cancel(future)
        if cancel_returned:
            self._wait_for_cancelled_or_done(future)
            health_ok = self._health_probe_unlocked()
            self._state = MatlabEngineState.READY if health_ok else MatlabEngineState.BROKEN
            if not health_ok:
                self._recover_broken_session_unlocked()
            return MatlabFutureRecovery(
                cancel_returned=True,
                health_probe_ok=health_ok,
                future_done_before_cancel=False,
            )

        self._state = MatlabEngineState.BROKEN
        self._recover_broken_session_unlocked()
        return MatlabFutureRecovery(
            cancel_returned=False,
            health_probe_ok=False,
            future_done_before_cancel=False,
        )

    def _wait_for_cancelled_or_done(self, future: Any) -> None:
        deadline = time.monotonic() + self._cleanup_grace_s
        while time.monotonic() < deadline:
            if _future_done(future) or _future_cancelled(future):
                return
            wait_s = min(self._poll_interval_s, deadline - time.monotonic())
            if wait_s <= 0:
                return
            try:
                future.result(wait_s)
                return
            except Exception as exc:
                if _is_timeout_error(exc):
                    continue
                return

    def _health_probe_unlocked(self) -> bool:
        try:
            return float(self._engine.sqrt(4.0, nargout=1)) == 2.0
        except Exception as exc:
            logger.error(
                "MATLAB Engine health probe failed: ownership={} state={} exception_type={}",
                self._ownership.value,
                self._state.value,
                type(exc).__name__,
            )
            return False

    def _recover_broken_session_unlocked(self) -> None:
        if self._ownership == MatlabEngineOwnership.OWNED:
            try:
                self._close_owned_unlocked()
            except MatlabEngineError as exc:
                logger.error(
                    "MATLAB owned session recovery failed: state={} reason_code={}",
                    self._state.value,
                    exc.reason_code,
                )
        else:
            try:
                self._close_attached_unlocked()
            except MatlabEngineError as exc:
                logger.error(
                    "MATLAB attached session disconnect failed: state={} reason_code={}",
                    self._state.value,
                    exc.reason_code,
                )

    def _close_owned_unlocked(self) -> None:
        quit_ok = self._call_quit_with_grace()
        if quit_ok:
            self._state = MatlabEngineState.CLOSED
            self._engine = None
            return

        terminate_ok = False
        if self._matlab_process_id is not None:
            terminate_ok = self._process_terminator(
                self._matlab_process_id,
                self._cleanup_grace_s,
            )

        if terminate_ok:
            logger.error(
                "MATLAB owned session required process termination: pid={}",
                self._matlab_process_id,
            )
            self._state = MatlabEngineState.CLOSED
            self._engine = None
            return

        self._state = MatlabEngineState.BROKEN
        raise MatlabEngineSessionError("matlab_engine_owned_close_failed") from None

    def _close_attached_unlocked(self) -> None:
        quit_ok = self._call_quit_with_grace()
        if quit_ok:
            self._state = MatlabEngineState.CLOSED
            self._engine = None
            return

        self._state = MatlabEngineState.BROKEN
        raise MatlabEngineSessionError("matlab_engine_attached_disconnect_failed") from None

    def _call_quit_with_grace(self) -> bool:
        if self._engine is None:
            return True

        outcome: dict[str, bool] = {"done": False, "error": False}

        def quit_engine() -> None:
            try:
                try:
                    self._engine.quit(nargout=0)
                except TypeError:
                    self._engine.quit()
            except Exception as exc:
                outcome["error"] = True
                logger.error(
                    "MATLAB Engine quit failed: ownership={} state={} exception_type={}",
                    self._ownership.value,
                    self._state.value,
                    type(exc).__name__,
                )
            finally:
                outcome["done"] = True

        thread = threading.Thread(target=quit_engine, name="matlab-engine-quit", daemon=True)
        thread.start()
        thread.join(self._cleanup_grace_s)
        return outcome["done"] and not outcome["error"]


def _load_matlab_engine_module() -> Any:
    try:
        return importlib.import_module("matlab.engine")
    except Exception as exc:
        raise MatlabEngineUnavailableError(
            "matlab_engine_unavailable",
            diagnostic_metadata={"exception_type": type(exc).__name__},
        ) from None


def _recovery_metadata(recovery: MatlabFutureRecovery) -> dict[str, object]:
    return {
        "cancel_returned": recovery.cancel_returned,
        "health_probe_ok": recovery.health_probe_ok,
        "future_done_before_cancel": recovery.future_done_before_cancel,
    }


def _parse_simulation_result(raw: Any) -> MatlabSimulationResult:
    try:
        return MatlabSimulationResult(
            stop_time=_as_float(_get_field(raw, "stop_time")),
            sample_count=_as_int(_get_field(raw, "sample_count")),
            final_value=_as_float(_get_field(raw, "final_value")),
        )
    except Exception as exc:
        raise MatlabEngineExecutionError(
            "matlab_engine_result_invalid",
            diagnostic_metadata={"exception_type": type(exc).__name__},
        ) from None


def _get_field(raw: Any, field: str) -> Any:
    if isinstance(raw, dict):
        return raw[field]
    if hasattr(raw, field):
        return getattr(raw, field)
    raise KeyError(field)


def _as_float(value: Any) -> float:
    scalar = _first_scalar(value)
    return float(scalar)


def _as_int(value: Any) -> int:
    scalar = _first_scalar(value)
    return int(scalar)


def _first_scalar(value: Any) -> Any:
    if isinstance(value, str | bytes):
        return value
    if isinstance(value, int | float | bool):
        return value
    try:
        iterator = iter(value)
    except TypeError:
        return value

    first = next(iterator)
    return _first_scalar(first)


def _extract_simulink_version(version_output: Any) -> str | None:
    if version_output is None:
        return None
    if isinstance(version_output, dict):
        version = version_output.get("Version") or version_output.get("version")
        return str(version) if version else "unknown"
    if isinstance(version_output, list | tuple):
        if not version_output:
            return None
        return _extract_simulink_version(version_output[0])
    if hasattr(version_output, "Version"):
        return str(version_output.Version)
    if isinstance(version_output, str):
        return version_output or None
    return "unknown"


def _is_timeout_error(exc: Exception) -> bool:
    return type(exc).__name__ == "TimeoutError"


def _is_cancelled_error(exc: Exception) -> bool:
    return type(exc).__name__ in {"CancelledError", "CancelledFutureError"}


def _future_done(future: Any) -> bool:
    done = getattr(future, "done", None)
    if done is None:
        return False
    try:
        return bool(done())
    except Exception:
        return False


def _future_cancelled(future: Any) -> bool:
    cancelled = getattr(future, "cancelled", None)
    if cancelled is None:
        return False
    try:
        return bool(cancelled())
    except Exception:
        return False


def _future_cancel(future: Any) -> bool:
    cancel = getattr(future, "cancel", None)
    if cancel is None:
        return False
    try:
        return bool(cancel())
    except Exception:
        return False


def _consume_completed_future(future: Any) -> None:
    try:
        future.result(0)
    except TypeError:
        try:
            future.result()
        except Exception:
            return
    except Exception:
        return


def _read_engine_pid(engine: Any) -> Any:
    try:
        pid = getattr(engine, "matlabProcessID", None)
        if callable(pid):
            return pid()
        return pid
    except Exception:
        return None


def _coerce_pid(value: Any) -> int | None:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _terminate_process(pid: int, timeout_s: float) -> bool:
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=timeout_s,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return True
