"""Bounded, Windows-owned MATLAB Engine startup for service lifespan wiring."""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

from adapters.matlab_engine.runtime import MatlabEngineSession, _load_matlab_engine_module
from core.domain.exceptions import (
    MatlabEngineError,
    MatlabEngineSessionError,
    MatlabEngineStartupError,
    MatlabEngineTimeoutError,
    MatlabEngineUnavailableError,
)
from core.interfaces.matlab_engine_provider import MatlabEngineProvider

DEFAULT_STARTUP_TIMEOUT_S = 90.0
DEFAULT_CLEANUP_GRACE_S = 10.0
DEFAULT_POLL_INTERVAL_S = 0.5
HEALTH_PROBE_TIMEOUT_S = 15.0


class SessionBackedMatlabEngineProvider(MatlabEngineProvider):
    """Thin bool-to-typed adapter around a concrete MATLAB Engine session."""

    def __init__(self, session: MatlabEngineSession) -> None:
        self._session = session

    def health_probe(self) -> None:
        if not self._session.health_probe():
            raise MatlabEngineSessionError(reason_code="health_probe_failed") from None


@dataclass(slots=True)
class OwnedMatlabEngineRuntime:
    """Composition-root handle for one owned MATLAB Engine process tree."""

    session: MatlabEngineSession
    provider: MatlabEngineProvider
    startup_proc: subprocess.Popen[bytes]
    share_name: str
    cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S
    log_path: Path | None = None
    log_dir: Path | None = None
    _tree_terminated: bool = field(default=False, init=False, repr=False)

    @property
    def is_tree_terminated(self) -> bool:
        return self._tree_terminated

    def terminate_tree(self) -> bool:
        reaped = _terminate_process_tree(
            self.startup_proc.pid,
            timeout_s=self.cleanup_grace_s,
            poll_interval_s=self.poll_interval_s,
        )
        if reaped:
            self._tree_terminated = True
        return reaped

    def wait_tree_gone(self, timeout_s: float | None = None) -> bool:
        return _wait_process_tree_gone(
            self.startup_proc.pid,
            timeout_s=self.cleanup_grace_s if timeout_s is None else timeout_s,
            poll_interval_s=self.poll_interval_s,
        )

    def cleanup_log_file(self) -> None:
        _cleanup_log_artifacts(self.log_path, self.log_dir)


def start_owned_bounded(
    *,
    startup_timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S,
    cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> OwnedMatlabEngineRuntime:
    """Start, connect, attest, and return one bounded owned MATLAB runtime."""
    _validate_positive_timeout("startup_timeout_s", startup_timeout_s)
    _validate_positive_timeout("cleanup_grace_s", cleanup_grace_s)
    _validate_positive_timeout("poll_interval_s", poll_interval_s)

    if sys.platform != "win32":
        raise MatlabEngineUnavailableError(
            reason_code="owned_startup_unsupported_platform"
        ) from None

    matlab_engine = _load_matlab_engine_module()
    share_name = f"task513_{uuid.uuid4().hex}"
    deadline = time.monotonic() + startup_timeout_s
    connect_future: Any | None = None
    log_dir = Path(tempfile.mkdtemp(prefix="mxa-matlab-engine-"))
    log_path = log_dir / "owned.log"

    try:
        proc = _launch_owned_matlab_process(share_name=share_name, log_path=log_path)
    except Exception as exc:
        _cleanup_log_artifacts(log_path, log_dir)
        raise MatlabEngineStartupError(
            reason_code="startup_connect_failed",
            diagnostic_metadata={"exception_type": type(exc).__name__, "stage": "launch"},
        ) from None

    try:
        while True:
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                _raise_timeout_after_cleanup(
                    proc=proc,
                    connect_future=connect_future,
                    cleanup_grace_s=cleanup_grace_s,
                    poll_interval_s=poll_interval_s,
                    log_path=log_path,
                    log_dir=log_dir,
                    stage="find_shared_engine",
                )

            names = _find_shared_engine_names(matlab_engine)
            if share_name not in names:
                time.sleep(min(poll_interval_s, remaining_s))
                continue

            try:
                connect_future = matlab_engine.connect_matlab(share_name, background=True)
                engine = _future_result_before_deadline(connect_future, deadline)
                pid_future = engine.feval("matlabProcessID", nargout=1, background=True)
                matlab_pid = int(_future_result_before_deadline(pid_future, deadline))
            except Exception as exc:
                if _is_timeout_error(exc):
                    _raise_timeout_after_cleanup(
                        proc=proc,
                        connect_future=connect_future,
                        cleanup_grace_s=cleanup_grace_s,
                        poll_interval_s=poll_interval_s,
                        log_path=log_path,
                        log_dir=log_dir,
                        stage="connect_or_pid_probe",
                    )
                _raise_startup_after_cleanup(
                    proc=proc,
                    reason_code="startup_connect_failed",
                    cleanup_grace_s=cleanup_grace_s,
                    poll_interval_s=poll_interval_s,
                    log_path=log_path,
                    log_dir=log_dir,
                    diagnostic_metadata={
                        "exception_type": type(exc).__name__,
                        "stage": "connect_or_pid_probe",
                    },
                )

            if not _is_pid_in_process_tree(proc.pid, matlab_pid):
                _raise_startup_after_cleanup(
                    proc=proc,
                    reason_code="startup_pid_attestation_failed",
                    cleanup_grace_s=cleanup_grace_s,
                    poll_interval_s=poll_interval_s,
                    log_path=log_path,
                    log_dir=log_dir,
                    diagnostic_metadata={"stage": "pid_attestation"},
                )

            session = MatlabEngineSession.from_connected_owned(
                engine,
                matlab_process_id=matlab_pid,
            )
            return OwnedMatlabEngineRuntime(
                session=session,
                provider=SessionBackedMatlabEngineProvider(session),
                startup_proc=proc,
                share_name=share_name,
                cleanup_grace_s=cleanup_grace_s,
                poll_interval_s=poll_interval_s,
                log_path=log_path,
                log_dir=log_dir,
            )
    except MatlabEngineError:
        raise
    except Exception as exc:
        _raise_startup_after_cleanup(
            proc=proc,
            reason_code="startup_connect_failed",
            cleanup_grace_s=cleanup_grace_s,
            poll_interval_s=poll_interval_s,
            log_path=log_path,
            log_dir=log_dir,
            diagnostic_metadata={"exception_type": type(exc).__name__, "stage": "startup"},
        )


def _validate_positive_timeout(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _launch_owned_matlab_process(
    *,
    share_name: str,
    log_path: Path,
) -> subprocess.Popen[bytes]:
    matlab_exe = _resolve_matlab_executable()
    command = f"matlab.engine.shareEngine('{share_name}')"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            matlab_exe,
            "-wait",
            "-nodesktop",
            "-nosplash",
            "-logfile",
            str(log_path),
            "-r",
            command,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _resolve_matlab_executable() -> str:
    configured = os.getenv("MXA_MATLAB_EXE")
    if configured:
        return configured
    discovered = shutil.which("matlab")
    if discovered is not None:
        return discovered
    return "matlab.exe"


def _find_shared_engine_names(matlab_engine: Any) -> set[str]:
    names = matlab_engine.find_matlab()
    return {str(name) for name in names}


def _future_result_before_deadline(future: Any, deadline: float) -> Any:
    remaining_s = deadline - time.monotonic()
    if remaining_s <= 0:
        raise TimeoutError("deadline expired")
    return future.result(timeout=remaining_s)


def _cancel_future(future: Any | None) -> None:
    if future is None:
        return
    cancel = getattr(future, "cancel", None)
    if cancel is None:
        return
    try:
        cancel()
    except Exception:
        return


def _raise_timeout_after_cleanup(
    *,
    proc: subprocess.Popen[bytes],
    connect_future: Any | None,
    cleanup_grace_s: float,
    poll_interval_s: float,
    log_path: Path,
    log_dir: Path,
    stage: str,
) -> NoReturn:
    _cancel_future(connect_future)
    if _terminate_process_tree(
        proc.pid, timeout_s=cleanup_grace_s, poll_interval_s=poll_interval_s
    ):
        _cleanup_log_artifacts(log_path, log_dir)
        raise MatlabEngineTimeoutError(
            reason_code="startup_timeout_reaped",
            diagnostic_metadata={"stage": stage},
        ) from None
    _cleanup_log_artifacts(log_path, log_dir)
    raise MatlabEngineStartupError(
        reason_code="startup_reaper_failed",
        diagnostic_metadata={"stage": stage},
    ) from None


def _raise_startup_after_cleanup(
    *,
    proc: subprocess.Popen[bytes],
    reason_code: str,
    cleanup_grace_s: float,
    poll_interval_s: float,
    log_path: Path,
    log_dir: Path,
    diagnostic_metadata: dict[str, object] | None = None,
) -> NoReturn:
    if not _terminate_process_tree(
        proc.pid,
        timeout_s=cleanup_grace_s,
        poll_interval_s=poll_interval_s,
    ):
        _cleanup_log_artifacts(log_path, log_dir)
        raise MatlabEngineStartupError(
            reason_code="startup_reaper_failed",
            diagnostic_metadata=diagnostic_metadata,
        ) from None
    _cleanup_log_artifacts(log_path, log_dir)
    raise MatlabEngineStartupError(
        reason_code=reason_code,
        diagnostic_metadata=diagnostic_metadata,
    ) from None


def _terminate_process_tree(pid: int, *, timeout_s: float, poll_interval_s: float) -> bool:
    tree_pids = _process_tree_pids(pid) | {pid}
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0 and any(_pid_exists(tree_pid) for tree_pid in tree_pids):
        return False
    return _wait_pids_gone(tree_pids, timeout_s=timeout_s, poll_interval_s=poll_interval_s)


def _wait_process_tree_gone(pid: int, *, timeout_s: float, poll_interval_s: float) -> bool:
    return _wait_pids_gone(
        _process_tree_pids(pid) | {pid},
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )


def _wait_pids_gone(pids: set[int], *, timeout_s: float, poll_interval_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while True:
        if not any(_pid_exists(pid) for pid in pids):
            return True
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            return not any(_pid_exists(pid) for pid in pids)
        time.sleep(min(poll_interval_s, remaining_s))


def _is_pid_in_process_tree(root_pid: int, candidate_pid: int) -> bool:
    if candidate_pid <= 0:
        return False
    if candidate_pid == root_pid:
        return _pid_exists(root_pid)
    return candidate_pid in _process_tree_pids(root_pid)


def _process_tree_pids(root_pid: int) -> set[int]:
    parent_map = _windows_parent_process_map()
    children_by_parent: dict[int, set[int]] = {}
    for pid, parent_pid in parent_map.items():
        children_by_parent.setdefault(parent_pid, set()).add(pid)

    descendants: set[int] = set()
    pending = list(children_by_parent.get(root_pid, set()))
    while pending:
        pid = pending.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        pending.extend(children_by_parent.get(pid, set()))
    return descendants


def _windows_parent_process_map() -> dict[int, int]:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Select-Object ProcessId,ParentProcessId | "
                    "ConvertTo-Csv -NoTypeInformation"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0:
        return {}

    mapping: dict[int, int] = {}
    for row in csv.DictReader(io.StringIO(result.stdout)):
        try:
            pid = int(row["ProcessId"])
            parent_pid = int(row["ParentProcessId"])
        except (KeyError, TypeError, ValueError):
            continue
        mapping[pid] = parent_pid
    return mapping


def _pid_exists(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and str(pid) in result.stdout


def _is_timeout_error(exc: Exception) -> bool:
    return type(exc).__name__ == "TimeoutError"


def _cleanup_log_artifacts(log_path: Path | None, log_dir: Path | None) -> None:
    if log_path is not None:
        with suppress(OSError):
            log_path.unlink(missing_ok=True)
    if log_dir is not None:
        with suppress(OSError):
            log_dir.rmdir()
