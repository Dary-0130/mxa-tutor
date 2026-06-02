"""Coarse file-level dependency analysis for MATLAB projects."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from pathlib import PurePosixPath

from core.domain.m_file import MFile
from core.domain.project import FileInfo

from ._dep_patterns import (
    BUILTIN_FUNCTIONS,
    RE_BLOCK_COMMENT,
    RE_IDENTIFIER_CALL,
    RE_LINE_COMMENT,
    RE_LOAD_CALL,
    RE_SIM_CALL,
)

__all__ = ["analyze_dependencies"]


def analyze_dependencies(
    file_infos: Iterable[FileInfo],
    m_files: Iterable[MFile],
    project_root: str | None = None,
) -> dict[str, list[str]]:
    """Extract coarse cross-file dependencies as ``{source_relpath: targets}``.

    Args:
        file_infos: All project files from ``classify_files``.
        m_files: Parsed ``.m`` files from ``MParserImpl``.
        project_root: Optional project root used to convert absolute ``MFile.file_path``
            values into project-relative POSIX paths.

    Returns:
        A mapping from source file relative path to sorted unique target relative paths.
        Files without outgoing dependencies are omitted.
    """
    file_info_list = list(file_infos)
    m_file_list = list(m_files)
    if not file_info_list or not m_file_list:
        return {}

    fn_to_file = _build_function_name_map(m_file_list, project_root)
    mat_index = _build_file_index_by_ext(file_info_list, ".mat")
    slx_index = _build_file_index_by_ext(file_info_list, ".slx")
    source_index = {
        _normalize_relpath(info.relative_path): info.relative_path for info in file_info_list
    }

    dependencies: dict[str, list[str]] = {}
    for m_file in m_file_list:
        source = _resolve_source_relpath(m_file.file_path, project_root, source_index)
        stripped_code = _strip_comments(m_file.raw_code)
        targets = (
            _extract_m_to_m_targets(stripped_code, fn_to_file, source)
            | _extract_data_load_targets(stripped_code, mat_index)
            | _extract_slx_targets(stripped_code, slx_index)
        )
        targets.discard(source)
        if targets:
            dependencies[source] = sorted(targets)

    return dependencies


def _build_function_name_map(
    m_files: Iterable[MFile],
    project_root: str | None,
) -> dict[str, list[str]]:
    """Build ``{function_name: [defining_relpath, ...]}`` from parsed files."""
    result: dict[str, set[str]] = {}
    for m_file in m_files:
        relpath = _mfile_to_relpath(m_file.file_path, project_root)
        for function in m_file.functions:
            result.setdefault(function.name, set()).add(relpath)
    return {name: sorted(paths) for name, paths in result.items()}


def _build_file_index_by_ext(
    file_infos: Iterable[FileInfo],
    target_ext: str,
) -> dict[str, str]:
    """Build a case-insensitive target lookup for files with ``target_ext``."""
    index: dict[str, str] = {}
    for file_info in sorted(file_infos, key=lambda item: item.relative_path):
        relpath = _normalize_relpath(file_info.relative_path)
        path = PurePosixPath(relpath)
        if path.suffix.lower() != target_ext:
            continue

        stem_relpath = str(path.with_suffix(""))
        for key in (relpath, stem_relpath, path.name, path.stem):
            index.setdefault(key.lower(), relpath)
    return index


def _strip_comments(raw_code: str) -> str:
    """Strip MATLAB line comments and line-delimited block comments."""

    def _blank_block(match: object) -> str:
        text = match.group(0)  # type: ignore[attr-defined]
        return "\n" * text.count("\n")

    without_blocks = RE_BLOCK_COMMENT.sub(_blank_block, raw_code)
    return RE_LINE_COMMENT.sub("", without_blocks)


def _extract_m_to_m_targets(
    stripped_code: str,
    fn_to_file: dict[str, list[str]],
    self_file_relpath: str,
) -> set[str]:
    """Extract ``.m -> .m`` dependency targets from stripped code."""
    targets: set[str] = set()
    for match in RE_IDENTIFIER_CALL.finditer(stripped_code):
        name = match.group(1)
        if name in BUILTIN_FUNCTIONS or _is_function_definition_line(stripped_code, match.start()):
            continue
        for relpath in fn_to_file.get(name, []):
            if relpath != self_file_relpath:
                targets.add(relpath)
    return targets


def _extract_data_load_targets(
    stripped_code: str,
    mat_index: dict[str, str],
) -> set[str]:
    """Extract ``.m -> .mat`` dependency targets from load-like calls."""
    targets: set[str] = set()
    for match in RE_LOAD_CALL.finditer(stripped_code):
        target_name = match.group(1) or match.group(2)
        target = _normalize_target(target_name, mat_index)
        if target:
            targets.add(target)
    return targets


def _extract_slx_targets(
    stripped_code: str,
    slx_index: dict[str, str],
) -> set[str]:
    """Extract ``.m -> .slx`` dependency targets from Simulink API calls."""
    targets: set[str] = set()
    for match in RE_SIM_CALL.finditer(stripped_code):
        raw_name = match.group(1)
        target = _normalize_target(raw_name, slx_index)
        if target is None and "/" in raw_name.replace("\\", "/"):
            target = _normalize_target(
                raw_name.replace("\\", "/").split("/", maxsplit=1)[0], slx_index
            )
        if target:
            targets.add(target)
    return targets


def _normalize_target(name: str, candidates_index: dict[str, str]) -> str | None:
    """Normalize a quoted target name and look it up in a file index."""
    normalized = _normalize_relpath(name)
    return candidates_index.get(normalized.lower())


def _mfile_to_relpath(mfile_path: str, project_root: str | None) -> str:
    """Convert an ``MFile.file_path`` value to a POSIX relative path."""
    path = PurePosixPath(mfile_path.replace("\\", "/"))
    if project_root:
        root = PurePosixPath(project_root.replace("\\", "/"))
        with suppress(ValueError):
            path = path.relative_to(root)
    return _normalize_relpath(str(path))


def _normalize_relpath(path: str) -> str:
    """Normalize a path to the POSIX style used by ``FileInfo.relative_path``."""
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    return normalized.lstrip("./").rstrip("/")


def _resolve_source_relpath(
    mfile_path: str,
    project_root: str | None,
    source_index: dict[str, str],
) -> str:
    relpath = _mfile_to_relpath(mfile_path, project_root)
    if relpath in source_index:
        return source_index[relpath]
    for known_relpath in sorted(source_index):
        if relpath.endswith(f"/{known_relpath}") or relpath == known_relpath:
            return source_index[known_relpath]
    return relpath


def _is_function_definition_line(code: str, match_start: int) -> bool:
    line_start = code.rfind("\n", 0, match_start) + 1
    prefix = code[line_start:match_start]
    return "function" in prefix.split()
