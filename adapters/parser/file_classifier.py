import os
from pathlib import Path

from loguru import logger

from adapters.parser._zip_policy import classify_extension
from core.domain.exceptions import FileTypeNotAllowedError, ZipSlipError
from core.domain.project import FileInfo


def classify_files(extracted_root: Path, project_root: Path) -> list[FileInfo]:
    """按扩展名对已解压工程文件做粗分类,不读取文件内容。"""
    root = extracted_root.resolve()
    base = project_root.resolve()
    _ensure_within_root(root, base)

    files: list[FileInfo] = []
    for current_root, _dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current_root)
        for name in sorted(names):
            path = current_path / name
            if path.is_symlink():
                raise ZipSlipError("解压结果包含符号链接")
            _ensure_within_root(path.resolve(), base)

            relative = path.relative_to(base).as_posix()
            ext = path.suffix.lower()
            policy = classify_extension(ext)
            if policy == "deny":
                raise FileTypeNotAllowedError(f"包含不支持的文件类型: {ext}")
            if policy == "skip":
                logger.info(
                    "file_skipped_by_policy: ext={} reason=non_consumable_binary_or_doc",
                    ext,
                )
                continue

            file_type = ext if policy == "allow" else "other"
            files.append(
                FileInfo(
                    relative_path=relative,
                    file_type=file_type,
                    size_bytes=path.stat().st_size,
                )
            )

    return sorted(files, key=lambda item: item.relative_path)


def _ensure_within_root(path: Path, root: Path) -> None:
    try:
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise ZipSlipError("zip 路径穿越,文件将写出解压目录")
    except ValueError as exc:
        raise ZipSlipError("zip 路径跨 drive") from exc
