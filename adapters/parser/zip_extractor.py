import io
import os
import stat
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from contextlib import suppress
from pathlib import Path

from loguru import logger

from adapters.parser._zip_paths import _compute_target_within_dest, _normalize_zip_path
from adapters.parser._zip_policy import classify_extension
from app.config import AppSettings
from core.domain.exceptions import (
    FileTypeNotAllowedError,
    ProjectTooLargeError,
    ZipBombError,
    ZipSlipError,
)

CHUNK_SIZE = 1024 * 1024


def safe_extract(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> Path:
    """安全解压 zip 到 dest_dir,失败时抛 UploadError / ProjectError 子类。"""
    timeout_seconds = config.max_extraction_seconds
    deadline = time.monotonic() + timeout_seconds

    _check_outer_envelope(zip_bytes, dest_dir, config)

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zip-extract")
    future = executor.submit(_do_extract, zip_bytes, dest_dir, config, deadline)

    try:
        result = future.result(timeout=timeout_seconds)
    except FuturesTimeout as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise ProjectTooLargeError("解压超时,工程过大或异常") from exc
    except BaseException:
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True, cancel_futures=True)
        return result


def _check_outer_envelope(zip_bytes: bytes, dest_dir: Path, config: AppSettings) -> None:
    max_upload = config.max_upload_size_mb * 1024 * 1024
    if len(zip_bytes) > max_upload:
        raise ProjectTooLargeError(f"上传压缩包过大,超过 {config.max_upload_size_mb}MB 上限")

    if not dest_dir.exists() or not dest_dir.is_dir():
        raise ZipSlipError("解压目标目录不存在或不是目录")
    if dest_dir.is_symlink():
        raise ZipSlipError("解压目标目录不能是符号链接")

    dest_root = dest_dir.resolve()
    upload_root = Path(config.upload_dir).resolve()
    try:
        if os.path.commonpath([str(upload_root), str(dest_root)]) != str(upload_root):
            raise ZipSlipError("解压目标目录不在 upload_dir 子树内")
    except ValueError as exc:
        raise ZipSlipError("解压目标目录与 upload_dir 跨 drive") from exc


def _do_extract(
    zip_bytes: bytes,
    dest_dir: Path,
    config: AppSettings,
    deadline: float,
) -> Path:
    _raise_if_timeout(deadline)
    dest_root = dest_dir.resolve()

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()
            scan = _scan_metadata(infos, dest_root, config)
            _extract_infos(zf, infos, scan, dest_root, config, deadline)
    except zipfile.LargeZipFile as exc:
        raise ZipBombError("zip64 结构超出当前处理范围") from exc
    except zipfile.BadZipFile as exc:
        raise ZipBombError("zip 格式非法,无法读取压缩包") from exc

    _reject_symlink_after_extract(dest_root)
    return dest_root


def _scan_metadata(
    infos: list[zipfile.ZipInfo],
    dest_root: Path,
    config: AppSettings,
) -> tuple[dict[str, Path], set[str]]:
    _check_entry_counts(infos, config)

    target_by_name: dict[str, Path] = {}
    directory_names: set[str] = set()
    raw_seen: set[str] = set()
    nfc_seen: set[str] = set()
    case_seen: set[str] = set()
    total_uncompressed = 0
    total_compressed = 0

    for info in infos:
        _check_entry_flags(info)
        normalized = _normalize_zip_path(info.filename)
        _check_path_collision(info.filename, normalized, raw_seen, nfc_seen, case_seen)

        target_by_name[info.filename] = _compute_target_within_dest(normalized, dest_root)
        if info.is_dir() or info.filename.endswith("/"):
            directory_names.add(info.filename)
            continue

        _check_file_size_and_ext(info, normalized, config)
        total_uncompressed += info.file_size
        total_compressed += info.compress_size

    _check_total_size_and_ratio(total_uncompressed, total_compressed, config)
    return target_by_name, directory_names


def _check_entry_counts(infos: list[zipfile.ZipInfo], config: AppSettings) -> None:
    if not infos:
        raise ZipBombError("zip 格式非法,无法读取压缩包")
    if len(infos) > config.max_entries_per_project:
        raise ProjectTooLargeError(f"工程文件数过多,超过 {config.max_entries_per_project} 个")
    file_count = sum(not info.is_dir() for info in infos)
    if file_count > config.max_files_per_project:
        raise ProjectTooLargeError(f"工程文件数过多,超过 {config.max_files_per_project} 个")


def _check_entry_flags(info: zipfile.ZipInfo) -> None:
    if info.flag_bits & 0x1:
        raise ZipBombError("压缩包含加密文件,暂不支持")
    if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise ZipBombError("压缩方法不支持,仅允许 stored / deflated")

    mode = info.external_attr >> 16
    file_type = mode & 0o170000
    if file_type == stat.S_IFLNK:
        raise ZipSlipError("zip 内含符号链接或非普通文件")
    if file_type and file_type not in {stat.S_IFREG, stat.S_IFDIR}:
        raise ZipSlipError("zip 内含符号链接或非普通文件")


def _check_path_collision(
    raw_name: str,
    normalized: str,
    raw_seen: set[str],
    nfc_seen: set[str],
    case_seen: set[str],
) -> None:
    casefolded = normalized.casefold()
    if raw_name in raw_seen or normalized in nfc_seen or casefolded in case_seen:
        raise ZipSlipError("zip 内存在重复路径或路径碰撞")
    raw_seen.add(raw_name)
    nfc_seen.add(normalized)
    case_seen.add(casefolded)


def _check_file_size_and_ext(
    info: zipfile.ZipInfo,
    normalized: str,
    config: AppSettings,
) -> None:
    max_single = config.max_single_file_mb * 1024 * 1024
    if info.file_size > max_single:
        raise ProjectTooLargeError(f"单个文件解压后过大: {info.filename}")

    ext = Path(normalized).suffix.lower()
    policy = classify_extension(ext)
    if policy == "deny":
        raise FileTypeNotAllowedError(f"包含不支持的文件类型: {ext}")


def _check_total_size_and_ratio(
    total_uncompressed: int, total_compressed: int, config: AppSettings
) -> None:
    max_total = config.max_total_uncompressed_mb * 1024 * 1024
    if total_uncompressed > max_total:
        raise ZipBombError("工程解压后总大小超限,疑似 zip bomb")
    if (
        total_compressed > 0
        and total_uncompressed / total_compressed > config.max_compression_ratio
    ):
        raise ZipBombError("压缩比异常,疑似 zip bomb")


def _extract_infos(
    zf: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
    scan: tuple[dict[str, Path], set[str]],
    dest_root: Path,
    config: AppSettings,
    deadline: float,
) -> None:
    max_single = config.max_single_file_mb * 1024 * 1024
    max_total = config.max_total_uncompressed_mb * 1024 * 1024
    actual_total = 0
    target_by_name, directory_names = scan

    for info in infos:
        _raise_if_timeout(deadline)
        target = target_by_name[info.filename]

        if info.filename in directory_names or info.is_dir():
            _make_directory(target)
            continue

        ext = target.suffix.lower()
        if classify_extension(ext) == "skip":
            logger.info(
                "file_skipped_by_policy: ext={} reason=non_consumable_binary_or_doc",
                ext,
            )
            continue

        _ensure_target_parent(dest_root, target)
        actual_file, actual_total = _copy_entry(
            zf, info, target, max_single, max_total, actual_total, deadline
        )
        if actual_file != info.file_size:
            raise ZipBombError("zip 文件大小元数据与实际读取结果不一致")

        with suppress(OSError):
            os.chmod(target, 0o600)


def _make_directory(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        os.chmod(target, 0o700)


def _ensure_target_parent(dest_root: Path, target: Path) -> None:
    target_parent = target.parent.resolve()
    try:
        if os.path.commonpath([str(dest_root), str(target_parent)]) != str(dest_root):
            raise ZipSlipError("zip 路径穿越,文件将写出解压目录")
    except ValueError as exc:
        raise ZipSlipError("zip 路径跨 drive") from exc
    target.parent.mkdir(parents=True, exist_ok=True)


def _copy_entry(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    target: Path,
    max_single: int,
    max_total: int,
    actual_total: int,
    deadline: float,
) -> tuple[int, int]:
    actual_file = 0
    try:
        with zf.open(info, "r") as src, target.open("xb") as dst:
            while True:
                _raise_if_timeout(deadline)
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break
                actual_file += len(chunk)
                actual_total += len(chunk)
                if actual_file > max_single:
                    raise ProjectTooLargeError(f"单个文件解压后过大: {info.filename}")
                if actual_total > max_total:
                    raise ZipBombError("工程解压后总大小超限,疑似 zip bomb")
                dst.write(chunk)
    except FileExistsError as exc:
        raise ZipSlipError("zip 内存在重复路径或路径碰撞") from exc
    except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise ZipBombError("zip 内容读取失败或格式非法") from exc
    return actual_file, actual_total


def _raise_if_timeout(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ProjectTooLargeError("解压超时,工程过大或异常")


def _reject_symlink_after_extract(dest_root: Path) -> None:
    for root, dirs, files in os.walk(dest_root, followlinks=False):
        root_path = Path(root)
        for name in [*dirs, *files]:
            if (root_path / name).is_symlink():
                raise ZipSlipError("解压结果包含符号链接")
