"""Subprocess sandbox for document parser adapters."""

from __future__ import annotations

import math
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any

from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import DocumentParser, ParsedDocument

DEFAULT_PARSER_TIMEOUT_SECONDS = 30.0
DEFAULT_MEM_LIMIT_BYTES = 512 * 1024 * 1024
SANDBOX_TEMP_PREFIX = "mxa_paper_parse_"
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
    ctx = mp.get_context()
    result_queue: Any = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_sandbox_child_main, args=(request, result_queue))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(1)
        raise DocumentParseError("document_parse_timeout") from None

    try:
        status, payload = result_queue.get_nowait()
    except Empty:
        raise DocumentParseError("document_parse_failed") from None

    if status == "ok" and isinstance(payload, ParsedDocument):
        return payload
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
