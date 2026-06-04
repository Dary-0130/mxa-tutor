"""上传 + 解析编排服务。"""

from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

from loguru import logger

from core.domain.exceptions import (
    FileTypeNotAllowedError,
    MxaError,
    ParseError,
    ProjectError,
    ProjectTooLargeError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)
from core.domain.m_file import MFile
from core.domain.project import FileInfo, Project, ProjectType
from core.domain.project_status import ProjectStatusErrorCode
from core.interfaces.parser import MParser, SlxParser
from core.interfaces.project_store import ProjectStore

ExtractFn: TypeAlias = Callable[[bytes, Path], Path]
ClassifyFn: TypeAlias = Callable[[Path, Path], list[FileInfo]]
DependencyAnalyzeFn: TypeAlias = Callable[
    [list[FileInfo], list[MFile], str | None], dict[str, list[str]]
]

_LEAF_CODE_MAP: dict[type[Exception], ProjectStatusErrorCode] = {
    ZipBombError: "zip_bomb",
    ZipSlipError: "zip_slip",
    FileTypeNotAllowedError: "file_type_not_allowed",
    ProjectTooLargeError: "project_too_large",
}
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _classify_error(exc: Exception) -> ProjectStatusErrorCode:
    """把业务异常翻译为 ProjectStatusErrorCode。"""
    for exc_type, code in _LEAF_CODE_MAP.items():
        if isinstance(exc, exc_type):
            return code
    if isinstance(exc, UploadError):
        return "upload_error"
    if isinstance(exc, ProjectError):
        return "project_error"
    if isinstance(exc, ParseError):
        return "parse_error"
    return "internal_error"


def _sanitize_filename(raw: str | None) -> str:
    """清洗 multipart filename,避免路径片段 / 控制字符污染状态视图。"""
    if not raw:
        return "uploaded.zip"
    name = Path(raw.replace("\\", "/")).name
    name = _CONTROL_CHARS_RE.sub("", name)
    name = name[:100].strip()
    return name or "uploaded.zip"


class UploadService:
    """编排上传同步预校验 + 异步解析。"""

    def __init__(
        self,
        store: ProjectStore,
        upload_dir: Path,
        max_upload_bytes: int,
        extractor: ExtractFn,
        classifier: ClassifyFn,
        slx_parser: SlxParser,
        m_parser: MParser,
        dependency_analyzer: DependencyAnalyzeFn,
    ) -> None:
        self._store = store
        self._upload_dir = upload_dir
        self._max_upload_bytes = max_upload_bytes
        self._extractor = extractor
        self._classifier = classifier
        self._slx_parser = slx_parser
        self._m_parser = m_parser
        self._dependency_analyzer = dependency_analyzer

    def check_declared_size(self, declared_size: int | None) -> None:
        """第一道防线:HTTP 表头 size 校验,不读 body 即拒。"""
        if declared_size is not None and declared_size > self._max_upload_bytes:
            raise ProjectTooLargeError("上传压缩包过大,请检查后重新上传")

    def check_actual_size(self, actual_size: int) -> None:
        """第二道兜底:read body 后实际字节数校验。"""
        if actual_size > self._max_upload_bytes:
            raise ProjectTooLargeError("上传压缩包过大,请检查后重新上传")

    async def create_upload_record(self, name: str) -> str:
        """生成 UUID + store 落 parsing 记录,UUID 冲突最多重试 3 次。"""
        last_error: ValueError | None = None
        for _ in range(3):
            project_id = str(uuid.uuid4())
            try:
                await self._store.create_pending(project_id, name)
                return project_id
            except ValueError as exc:
                last_error = exc
        raise ProjectError("无法创建上传记录,请重试") from last_error

    async def process(self, project_id: str, zip_bytes: bytes, name: str) -> None:
        """异步:解压 + 解析 + 落库,异常翻译为 failed 状态。"""
        project_dir = self._upload_dir / project_id
        try:
            project_dir.mkdir(parents=True, exist_ok=False)
            project = await asyncio.to_thread(
                self._run_parse_sync,
                project_id,
                zip_bytes,
                name,
                project_dir,
            )
            await self._store.mark_ready(project_id, project)
            logger.info(
                "Upload processed: project_id={} files={} slx={} m={}",
                project_id,
                len(project.files),
                len(project.slx_models),
                len(project.m_files),
            )
        except MxaError as exc:
            error_code = _classify_error(exc)
            logger.error(
                "Upload processing failed: project_id={} exception={} error_code={}",
                project_id,
                type(exc).__name__,
                error_code,
            )
            await self._store.mark_failed(project_id, error_code)
            self._cleanup_project_dir(project_dir)
        except Exception as exc:
            logger.error(
                "Upload processing crashed: project_id={} exception={}",
                project_id,
                type(exc).__name__,
            )
            await self._store.mark_failed(project_id, "internal_error")
            self._cleanup_project_dir(project_dir)

    def _run_parse_sync(
        self,
        project_id: str,
        zip_bytes: bytes,
        name: str,
        project_dir: Path,
    ) -> Project:
        """同步重活集合;通过 asyncio.to_thread 在线程池执行。"""
        extracted_root = self._extractor(zip_bytes, project_dir)
        file_infos = self._classifier(extracted_root, extracted_root)

        slx_models = []
        for file_info in file_infos:
            if file_info.file_type == ".slx":
                slx_models.append(
                    self._slx_parser.parse(str(extracted_root / file_info.relative_path))
                )

        m_files = []
        for file_info in file_infos:
            if file_info.file_type == ".m":
                m_files.append(self._m_parser.parse(str(extracted_root / file_info.relative_path)))

        file_dependencies = self._dependency_analyzer(file_infos, m_files, str(extracted_root))
        return Project(
            id=project_id,
            name=name,
            project_type=ProjectType.GENERAL,
            files=file_infos,
            slx_models=slx_models,
            m_files=m_files,
            mat_files=[],
            created_at=datetime.utcnow(),
            file_dependencies=file_dependencies,
        )

    @staticmethod
    def _cleanup_project_dir(project_dir: Path) -> None:
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
