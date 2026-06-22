"""Tests for repository hygiene scan scope."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_SCRIPT = REPO_ROOT / "scripts" / "check_repo_hygiene.py"

GITIGNORE = """\
.env
data/
__pycache__/
.venv/
/ignored_*.py
"""

ENV_EXAMPLE = """\
DEEPSEEK_API_KEY=
DB_PATH=
UPLOAD_DIR=
MAX_UPLOAD_SIZE_MB=
FREE_QUESTION_PER_PROJECT=
MONTHLY_QUOTA=
LOG_LEVEL=
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _prepare_repo(repo: Path) -> None:
    _git(repo, "init")
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")


def _run_hygiene(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HYGIENE_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_ignores_gitignored_python_files(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)
    (tmp_path / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "ignored_debug.py").write_text(
        'print("debug")\ntry:\n    pass\nexcept:\n    pass\n',
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".gitignore", ".env.example", "clean.py")

    result = _run_hygiene(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All hygiene checks passed!" in result.stdout
    assert "ignored_debug.py" not in result.stdout


def test_reports_tracked_python_violations(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)
    (tmp_path / "tracked_debug.py").write_text('print("debug")\n', encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", ".env.example", "tracked_debug.py")

    result = _run_hygiene(tmp_path)

    assert result.returncode == 1
    assert "FAIL: no print calls in non-test .py files" in result.stdout
    assert 'tracked_debug.py:1:print("debug")' in result.stdout
