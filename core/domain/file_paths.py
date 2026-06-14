"""Public file path invariants for user-visible citations."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

OVERVIEW_SENTINEL = "__project_overview__"

_SERVER_PATH_MARKERS = (
    "mxa-workspace/uploads",
    "pytest-of-",
    "appdata/local/temp",
)


def is_public_file_path(path: str) -> bool:
    """Return whether ``path`` is safe to expose as a project-relative path.

    This is a pure path-shape invariant. It intentionally does not reject words
    like ``uploads`` or ``temp`` because those may be legitimate project folders.
    """
    if path == OVERVIEW_SENTINEL:
        return True
    if not isinstance(path, str) or not path.strip():
        return False

    windows_path = PureWindowsPath(path)
    posix_path = PurePosixPath(path)
    if windows_path.is_absolute() or posix_path.is_absolute():
        return False
    if windows_path.drive or windows_path.root:
        return False

    normalized = path.replace("\\", "/")
    return all(part != ".." for part in normalized.split("/"))


def contains_server_path_hint(path: str) -> bool:
    """Return whether ``path`` contains known server-local path markers."""
    if not isinstance(path, str):
        return False
    normalized = path.lower().replace("\\", "/")
    return any(marker in normalized for marker in _SERVER_PATH_MARKERS)


__all__ = ["OVERVIEW_SENTINEL", "contains_server_path_hint", "is_public_file_path"]
