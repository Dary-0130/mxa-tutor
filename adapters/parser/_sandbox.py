"""Subprocess sandbox for document parser adapters."""

from __future__ import annotations

import math
import multiprocessing as mp
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any

from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import DocumentParser, ParsedDocument

DEFAULT_PARSER_TIMEOUT_SECONDS = 30.0
DEFAULT_MEM_LIMIT_BYTES = 512 * 1024 * 1024
SANDBOX_TEMP_PREFIX = "mxa_paper_parse_"
POLL_SECONDS = 0.1
DEAD_PROCESS_DRAIN_GRACE_SECONDS = 0.2
PROCESS_JOIN_SECONDS = 1.0
# Keep sandbox children from inheriting parent memory under Linux's default fork.
_SANDBOX_MP_CONTEXT = mp.get_context("spawn")
_MISSING_RESULT = object()
_ENV_ALLOWLIST = {
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
}


@dataclass(frozen=True)
class _SandboxChildRequest:
    parser: DocumentParser
    file_path: Path
    sandbox_dir: Path
    timeout_seconds: float
    mem_limit_bytes: int


def run_in_sandbox(
    parser: DocumentParser,
    file_path: Path,
    timeout_seconds: float = DEFAULT_PARSER_TIMEOUT_SECONDS,
    mem_limit_bytes: int = DEFAULT_MEM_LIMIT_BYTES,
    require_hard_limits: bool = False,
) -> ParsedDocument:
    """Run a document parser in a child process with sanitized paths and errors."""
    if require_hard_limits and not sys.platform.startswith("linux"):
        raise DocumentParseError("unsupported_parser_sandbox_platform") from None

    source_path = file_path.resolve()
    with tempfile.TemporaryDirectory(prefix=SANDBOX_TEMP_PREFIX) as temp_dir:
        sandbox_dir = Path(temp_dir).resolve()
        sandbox_file = sandbox_dir / f"document{source_path.suffix.lower()}"
        shutil.copyfile(source_path, sandbox_file)
        request = _SandboxChildRequest(
            parser=parser,
            file_path=sandbox_file,
            sandbox_dir=sandbox_dir,
            timeout_seconds=timeout_seconds,
            mem_limit_bytes=mem_limit_bytes,
        )
        return _run_child(request, timeout_seconds)


def _run_child(request: _SandboxChildRequest, timeout_seconds: float) -> ParsedDocument:
    result_queue: Any = _SANDBOX_MP_CONTEXT.Queue(maxsize=1)
    process = _SANDBOX_MP_CONTEXT.Process(
        target=_sandbox_child_main,
        args=(request, result_queue),
    )
    process.start()
    deadline = time.monotonic() + timeout_seconds
    result: Any = _MISSING_RESULT

    while result is _MISSING_RESULT:
        remaining = deadline - time.monotonic()
        if remaining <= 0 and process.is_alive():
            _terminate_then_kill(process)
            raise DocumentParseError("document_parse_timeout") from None

        try:
            result = result_queue.get(timeout=max(0.0, min(POLL_SECONDS, remaining)))
            break
        except Empty:
            if process.is_alive():
                continue
            result = _drain_dead_process_result(result_queue)
            if result is _MISSING_RESULT:
                _raise_for_missing_result(process, deadline)

    process.join(PROCESS_JOIN_SECONDS)
    if process.is_alive():
        _terminate_then_kill(process)

    return _unwrap_child_result(result)


def _drain_dead_process_result(result_queue: Any) -> Any:
    grace_until = time.monotonic() + DEAD_PROCESS_DRAIN_GRACE_SECONDS
    while time.monotonic() < grace_until:
        try:
            return result_queue.get(timeout=min(0.05, max(0.0, grace_until - time.monotonic())))
        except Empty:
            pass
    return _MISSING_RESULT


def _raise_for_missing_result(process: Any, deadline: float) -> None:
    if time.monotonic() >= deadline or _is_cpu_limit_exit(process.exitcode):
        raise DocumentParseError("document_parse_timeout") from None
    raise DocumentParseError("document_parse_failed") from None


def _terminate_then_kill(process: Any) -> None:
    if process.is_alive():
        process.terminate()
    process.join(PROCESS_JOIN_SECONDS)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(PROCESS_JOIN_SECONDS)


def _is_cpu_limit_exit(exitcode: int | None) -> bool:
    sigxcpu = getattr(signal, "SIGXCPU", None)
    return sigxcpu is not None and exitcode == -int(sigxcpu)


def _unwrap_child_result(result: Any) -> ParsedDocument:
    if not isinstance(result, tuple) or len(result) != 2:
        raise DocumentParseError("document_parse_failed") from None

    status, payload = result
    if status == "ok" and isinstance(payload, ParsedDocument):
        return payload
    if status == "error" and payload == "document_parse_failed":
        raise DocumentParseError("document_parse_failed") from None
    raise DocumentParseError("document_parse_failed") from None


def _sandbox_child_main(
    request: _SandboxChildRequest,
    result_queue: Any,
) -> None:
    try:
        _prepare_child(request)
        parsed = request.parser.parse(request.file_path, timeout_seconds=request.timeout_seconds)
        result_queue.put(("ok", parsed))
    except BaseException:
        result_queue.put(("error", "document_parse_failed"))


def _prepare_child(request: _SandboxChildRequest) -> None:
    os.chdir(request.sandbox_dir)
    _sanitize_child_env()
    _assert_path_inside(request.file_path, request.sandbox_dir)
    _apply_resource_limits(request.timeout_seconds, request.mem_limit_bytes)


def _sanitize_child_env() -> None:
    for key in list(os.environ):
        if key.upper() not in _ENV_ALLOWLIST:
            os.environ.pop(key, None)


def _assert_path_inside(file_path: Path, sandbox_dir: Path) -> None:
    resolved_file = file_path.resolve()
    resolved_dir = sandbox_dir.resolve()
    try:
        resolved_file.relative_to(resolved_dir)
    except ValueError:
        raise DocumentParseError("sandbox_path_violation") from None


def _apply_resource_limits(timeout_seconds: float, mem_limit_bytes: int) -> None:
    if not sys.platform.startswith("linux"):
        return
    import resource

    cpu_seconds = max(1, math.ceil(timeout_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit_bytes, mem_limit_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
