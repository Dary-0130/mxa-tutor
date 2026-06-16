import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.parser._sandbox import SANDBOX_TEMP_PREFIX, run_in_sandbox
from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import (
    DocumentParser,
    ParsedDocument,
    ParsedLocatorIndex,
    compute_file_hash,
)


class ContextProbeParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = timeout_seconds
        payload = {
            "path": str(file_path),
            "cwd": os.getcwd(),
            "has_project_env": "MXA_PROJECT_ROOT" in os.environ,
        }
        return _parsed(file_path, json.dumps(payload))


class RaisingParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = timeout_seconds
        raise RuntimeError(f"boom {file_path} C:\\private\\secret.pdf /home/private")


class SleepingParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        time.sleep(timeout_seconds + 5)
        return _parsed(file_path, "unreachable")


class ExitParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = file_path, timeout_seconds
        os._exit(7)


class OutsidePathParser(DocumentParser):
    def supports(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = file_path, timeout_seconds
        raise PermissionError("blocked outside path C:\\workspace\\project")


def test_sandbox_child_receives_only_temp_path_and_config(tmp_path: Path) -> None:
    source = tmp_path / "secret_original_name.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    parsed = run_in_sandbox(ContextProbeParser(), source)
    payload = json.loads(parsed.raw_text)

    assert "secret_original_name" not in payload["path"]
    assert payload["path"].endswith("document.pdf")
    assert str(Path.cwd()) not in payload["path"]


def test_sandbox_child_cwd_is_isolated_temp_dir(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    parsed = run_in_sandbox(ContextProbeParser(), source)
    payload = json.loads(parsed.raw_text)

    assert SANDBOX_TEMP_PREFIX in payload["cwd"]
    assert payload["cwd"] != str(Path.cwd())


def test_sandbox_child_env_does_not_include_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setenv("MXA_PROJECT_ROOT", str(Path.cwd()))

    parsed = run_in_sandbox(ContextProbeParser(), source)
    payload = json.loads(parsed.raw_text)

    assert payload["has_project_env"] is False


def test_parse_error_sanitizes_absolute_path_and_original_filename(tmp_path: Path) -> None:
    source = tmp_path / "private_report_name.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    with pytest.raises(DocumentParseError) as exc_info:
        run_in_sandbox(RaisingParser(), source)

    message = str(exc_info.value)
    assert "private_report_name" not in message
    assert "C:\\" not in message
    assert "/home" not in message
    assert "/Users" not in message


def test_sandbox_timeout_is_reported_without_child_traceback(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    with pytest.raises(DocumentParseError) as exc_info:
        run_in_sandbox(SleepingParser(), source, timeout_seconds=0.2)

    assert str(exc_info.value) == "document_parse_timeout"


def test_sandbox_child_crash_is_isolated(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    with pytest.raises(DocumentParseError) as exc_info:
        run_in_sandbox(ExitParser(), source)

    assert str(exc_info.value) == "document_parse_failed"


def test_sandbox_error_if_parser_attempts_path_outside_temp_dir(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    with pytest.raises(DocumentParseError) as exc_info:
        run_in_sandbox(OutsidePathParser(), source)

    assert str(exc_info.value) == "document_parse_failed"


def test_sandbox_non_linux_can_fail_closed_when_hard_limits_required(tmp_path: Path) -> None:
    if sys.platform.startswith("linux"):
        pytest.skip("Linux supports hard parser limits")
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    with pytest.raises(DocumentParseError) as exc_info:
        run_in_sandbox(ContextProbeParser(), source, require_hard_limits=True)

    assert str(exc_info.value) == "unsupported_parser_sandbox_platform"


def _parsed(file_path: Path, raw_text: str) -> ParsedDocument:
    return ParsedDocument(
        raw_text=raw_text,
        page_count=None,
        figure_placeholders=[],
        table_placeholders=[],
        locator_index=ParsedLocatorIndex(section_ids=["S1"], equation_ids=[], figure_ids=[]),
        file_hash=compute_file_hash(file_path),
        extracted_at=datetime.now(UTC),
    )
