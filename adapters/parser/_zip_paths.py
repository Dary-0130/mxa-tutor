import os
import re
import unicodedata
from pathlib import Path

from core.domain.exceptions import ZipSlipError

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_UNC_RE = re.compile(r"^(?:\\\\|//)[^\\/]+[\\/][^\\/]+")
_WINDOWS_RESERVED_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    re.IGNORECASE,
)


def _is_windows_unsafe_name(name: str) -> tuple[bool, str]:
    """检查 zip entry name 是否包含 Windows 特有的不安全路径形态。"""
    if not name:
        return True, "路径名为空"

    if _WINDOWS_DRIVE_RE.match(name):
        return True, "包含 Windows drive letter"

    if _WINDOWS_UNC_RE.match(name) or name.startswith(("\\\\", "//")):
        return True, "包含 Windows UNC 路径"

    if ":" in name:
        return True, "包含 Windows ADS 冒号或非法冒号"

    parts = re.split(r"[\\/]+", name)
    for part in parts:
        if part in {"", ".", ".."}:
            continue

        if part.endswith((" ", ".")):
            return True, "路径段尾随空格或点号"

        trimmed = part.rstrip(" .")
        if _WINDOWS_RESERVED_RE.match(trimmed):
            return True, "包含 Windows 保留设备名"

        stem = trimmed.split(".", 1)[0]
        if _WINDOWS_RESERVED_RE.match(stem):
            return True, "包含 Windows 保留设备名"

    return False, ""


def _normalize_zip_path(name: str) -> str:
    """规范化 zip entry 路径并拒绝跨平台不安全片段。"""
    normalized = unicodedata.normalize("NFC", name)
    if "\x00" in normalized or any(ord(char) < 32 for char in normalized):
        raise ZipSlipError(f"zip 内含非法路径片段: {name}")
    if "\\" in normalized:
        raise ZipSlipError(f"zip 内含非法路径片段: {name}")
    if normalized.startswith("/") or Path(normalized).is_absolute():
        raise ZipSlipError(f"zip 内含非法路径片段: {name}")

    unsafe, reason = _is_windows_unsafe_name(normalized)
    if unsafe:
        raise ZipSlipError(f"zip 内含 Windows 不安全路径名: {reason}")

    stripped = normalized.rstrip("/")
    if not stripped:
        raise ZipSlipError(f"zip 内含非法路径片段: {name}")

    parts = stripped.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ZipSlipError(f"zip 内含非法路径片段: {name}")

    return stripped


def _compute_target_within_dest(name: str, dest_root: Path) -> Path:
    """计算 entry 目标路径,并确认它仍在 dest_root 子树内。"""
    normalized = _normalize_zip_path(name)
    target = dest_root / normalized
    target_parent = target.parent.resolve()
    try:
        if os.path.commonpath([str(dest_root), str(target_parent)]) != str(dest_root):
            raise ZipSlipError("zip 路径穿越,文件将写出解压目录")
    except ValueError as exc:
        raise ZipSlipError("zip 路径跨 drive") from exc
    return target
