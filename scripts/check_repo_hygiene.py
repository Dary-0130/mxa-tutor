"""Cross-platform repository hygiene checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

FAILED = False


def _pass(name: str) -> None:
    print(f"PASS: {name}")


def _fail(name: str, detail: str) -> None:
    global FAILED
    print(f"FAIL: {name}: {detail}")
    FAILED = True


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _git_tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(path) for path in result.stdout.split("\0") if path]


def _py_files(include_tests: bool = True) -> list[Path]:
    ignored: set[str] = set()
    if not include_tests:
        ignored.update({"eval", "scripts", "tests", "tools"})
    return [
        path
        for path in _git_tracked_files()
        if path.suffix == ".py" and not _has_part(path, ignored)
    ]


def _text_files_by_suffix(*suffixes: str) -> list[Path]:
    return [path for path in _git_tracked_files() if path.suffix in suffixes]


def _has_part(path: Path, parts: set[str]) -> bool:
    return any(part in parts for part in path.parts)


def check_gitignore_entries() -> None:
    lines = set(_read(".gitignore").splitlines())
    missing = [entry for entry in [".env", "data/", "__pycache__/", ".venv/"] if entry not in lines]
    if missing:
        _fail(".gitignore includes core entries", f"missing {' '.join(missing)}")
    else:
        _pass(".gitignore includes core entries")


def check_env_example_fields() -> None:
    text = _read(".env.example")
    fields = [
        "DEEPSEEK_API_KEY",
        "DB_PATH",
        "UPLOAD_DIR",
        "MAX_UPLOAD_SIZE_MB",
        "FREE_QUESTION_PER_PROJECT",
        "MONTHLY_QUOTA",
        "LOG_LEVEL",
    ]
    missing = [field for field in fields if f"{field}=" not in text]
    if missing:
        _fail(".env.example includes required fields", f"missing {' '.join(missing)}")
    else:
        _pass(".env.example includes required fields")


def check_no_key_leaks() -> None:
    patterns = ("your-api-key", "sk-real", "sk-prod", "sk-live")
    hits = _find_text(_text_files_by_suffix(".example", ".toml"), patterns)
    if hits:
        _fail("no leaked real-looking API keys", "\n".join(hits))
    else:
        _pass("no leaked real-looking API keys")


def check_no_todos() -> None:
    label = "/".join(("TO" + "DO", "FIX" + "ME", "X" + "XX"))
    hits = _find_text(_py_files(), ("TO" + "DO", "FIX" + "ME", "X" + "XX"))
    if hits:
        _fail(f"no {label} in .py files", "\n".join(hits))
    else:
        _pass(f"no {label} in .py files")


def check_no_print_calls() -> None:
    hits = _find_text(_py_files(include_tests=False), ("print" + "(",))
    if hits:
        _fail("no print calls in non-test .py files", "\n".join(hits))
    else:
        _pass("no print calls in non-test .py files")


def check_no_bare_except() -> None:
    hits = []
    for path in _py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip() == "except:":
                hits.append(f"{path}:{lineno}:{line}")
    if hits:
        _fail("no bare except in .py files", "\n".join(hits))
    else:
        _pass("no bare except in .py files")


def _find_text(paths: list[Path], patterns: tuple[str, ...]) -> list[str]:
    hits = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern in line for pattern in patterns):
                hits.append(f"{path}:{lineno}:{line}")
    return hits


def main() -> int:
    check_gitignore_entries()
    check_env_example_fields()
    check_no_key_leaks()
    check_no_todos()
    check_no_print_calls()
    check_no_bare_except()
    if FAILED:
        print("Hygiene check FAILED.")
        return 1
    print("All hygiene checks passed!")
    return 0


raise SystemExit(main())
