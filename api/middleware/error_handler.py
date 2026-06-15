"""API 层异常 handler 挂载点(不是 ASGI middleware,命名沿用历史目录结构)。

本模块实现 22 个业务 handler,覆盖上传 / 工程 / LLM / 解析 / 导览 /
问答异常树 + ``MxaError`` final fallback,并补 2 个 FastAPI 默认 handler 兜底。

响应体 shape ``{"error": "<machine_code>", "message": "<中文文案>"}`` 由本
Task 锁定。TASK-206 追加 ``QuotaExhaustedError`` /
``EvidenceMissingError`` 两个 leaf handler;TASK-302 追加
``EmbeddingModelLoadError`` handler,不改 shape。

设计要点:
1. handler precedence:FastAPI 按 exception class MRO 查找最具体 handler。
   leaf handler 优先匹配,base fallback 兜底子类漏注册,``MxaError`` final
   fallback 兜未知业务异常。
2. 日志隐私(02 § 12):
   只记录异常类名 / HTTP code / request path / method,不记录异常 message
   (可能含用户文件名 / 路径 / 工程片段),也不记录 422 errors() / detail。
3. ``ProjectTooLargeError`` 文案动态化:从 ``AppSettings`` 读
   ``max_upload_size_mb`` / ``max_files_per_project``,避免文案与配置漂移。
4. ``FileTypeNotAllowedError`` 文案不列扩展名:02 § 9 旧文案列了 6 个扩展名,
   但 TASK-104 实际 ``ALLOW_EXTS`` 比那广得多(``.mdl`` / ``.mlx`` / ``.fig`` /
   ``.png`` / ``.svg`` / ``.pdf`` / ``.json`` / ``.yaml`` 等)。本 Task 文案使用
   概括性描述。完整白名单展示由 TASK-202 或 TASK-206 按 ``_zip_policy.py``
   统一生成。
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import AppSettings
from core.domain.exceptions import (
    ChatGenerationError,
    ChatSessionNotFoundError,
    EmbeddingModelLoadError,
    EvidenceMissingError,
    FileTypeNotAllowedError,
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    MParseError,
    MxaError,
    OverviewGenerationError,
    ProjectError,
    ProjectNotFoundError,
    ProjectTooLargeError,
    QuotaExhaustedError,
    SlxParseError,
    StoreError,
    TeachingUnitGenerationError,
    TeachingUnitInProgressError,
    TeachingUnitTargetNotFoundError,
    UnsupportedTeachingLevelError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)

ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]
ErrorHandlerSpec = tuple[type[Exception], ExceptionHandler]


def _log_error(request: Request, exc: Exception, status_code: int) -> None:
    """统一日志格式:只记录元数据,不记录异常 message。"""
    logger.error(
        "API error: exception={} status={} path={} method={}",
        type(exc).__name__,
        status_code,
        request.url.path,
        request.method,
    )


def _make_handler(
    status_code: int,
    machine_code: str,
    message: str,
) -> ExceptionHandler:
    """工厂函数:为静态文案的异常构造 handler。"""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        _log_error(request, exc, status_code)
        return JSONResponse(
            status_code=status_code,
            content={"error": machine_code, "message": message},
        )

    return handler


def _make_project_too_large_handler(settings: AppSettings) -> ExceptionHandler:
    """``ProjectTooLargeError`` handler:文案动态读 settings。"""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        _log_error(request, exc, 413)
        message = (
            f"工程过大或文件太多,请压缩到 {settings.max_upload_size_mb}MB 以内"
            f"并减少到 {settings.max_files_per_project} 个文件以下后重新上传"
        )
        return JSONResponse(
            status_code=413,
            content={"error": "project_too_large", "message": message},
        )

    return handler


def register_error_handlers(app: FastAPI, settings: AppSettings) -> None:
    """注册 22 个业务 handler + 2 个 FastAPI 默认 handler 兜底。

    注册顺序不影响 FastAPI 行为(FastAPI 按 MRO 查找最具体 handler),
    现有 tuple 顺序保持不重组,仅在末尾追加 3 个 leaf handler。

    业务 handler 覆盖 Upload / Project / LLM / Parse / Overview / Chat /
    Quota / Evidence 子树;HTTP 404 / 405 / 其他 HTTPException 与 422
    RequestValidationError 在本函数内统一中文化并脱敏。
    """

    async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        status_code = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
        if status_code == 404:
            machine_code = "not_found"
            message = "请求的资源不存在"
        elif status_code == 405:
            machine_code = "method_not_allowed"
            message = "请求方式不正确"
        else:
            machine_code = "http_error"
            message = "请求处理失败,请稍后重试"
        _log_error(request, exc, status_code)
        return JSONResponse(
            status_code=status_code,
            content={"error": machine_code, "message": message},
        )

    async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _log_error(request, exc, 422)
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "message": "请求参数有问题,请检查后重试"},
        )

    error_handlers: tuple[ErrorHandlerSpec, ...] = (
        (
            ZipBombError,
            _make_handler(400, "zip_bomb", "压缩文件异常,请检查后重新上传"),
        ),
        (
            ZipSlipError,
            _make_handler(400, "zip_slip", "压缩包内含非法路径,请重新打包后上传"),
        ),
        (
            FileTypeNotAllowedError,
            _make_handler(
                400,
                "file_type_not_allowed",
                "包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试",
            ),
        ),
        (
            ProjectNotFoundError,
            _make_handler(
                404,
                "project_not_found",
                "没有找到这个工程,可能已过期或已被删除,请重新上传",
            ),
        ),
        (
            ProjectTooLargeError,
            _make_project_too_large_handler(settings),
        ),
        (
            UploadError,
            _make_handler(400, "upload_error", "上传文件有问题,请检查压缩包后重新上传"),
        ),
        (
            ProjectError,
            _make_handler(400, "project_error", "工程处理失败,请重新上传后再试"),
        ),
        (
            MxaError,
            _make_handler(500, "internal_error", "出了点问题,我们已经记录,稍后再试"),
        ),
        (
            LLMAuthError,
            _make_handler(503, "llm_auth", "服务暂时不可用,请稍后重试"),
        ),
        (
            LLMQuotaError,
            _make_handler(503, "llm_quota", "服务繁忙,请稍后"),
        ),
        (
            LLMRateLimitError,
            _make_handler(429, "llm_rate_limit", "请求太频繁,稍等一下"),
        ),
        (
            LLMTimeoutError,
            _make_handler(504, "llm_timeout", "网络较慢,正在重试..."),
        ),
        (
            LLMServerError,
            _make_handler(502, "llm_server", "AI 服务暂不稳定,请刷新重试"),
        ),
        (
            SlxParseError,
            _make_handler(400, "slx_parse", "Simulink 模型解析失败,可能版本过老或损坏"),
        ),
        (
            MParseError,
            _make_handler(400, "m_parse", ".m 文件解析失败,请检查文件编码"),
        ),
        (
            OverviewGenerationError,
            _make_handler(502, "overview_generation", "导览生成失败,请刷新重试"),
        ),
        (
            ChatSessionNotFoundError,
            _make_handler(404, "chat_session_not_found", "对话不存在"),
        ),
        (
            StoreError,
            _make_handler(500, "store_error", "系统暂时不可用,请稍后重试"),
        ),
        (
            ChatGenerationError,
            _make_handler(502, "chat_generation", "回答生成失败,请刷新重试"),
        ),
        (
            UnsupportedTeachingLevelError,
            _make_handler(422, "unsupported_teaching_level", "advanced level 暂不开放,请使用 normal"),
        ),
        (
            TeachingUnitTargetNotFoundError,
            _make_handler(404, "teaching_unit_target_not_found", "没有找到要讲解的对象"),
        ),
        (
            TeachingUnitInProgressError,
            _make_handler(503, "generating_in_progress", "教学单元正在生成,请稍后重试"),
        ),
        (
            TeachingUnitGenerationError,
            _make_handler(502, "teaching_unit_generation", "教学单元生成失败,请刷新重试"),
        ),
        (
            QuotaExhaustedError,
            _make_handler(402, "quota_exhausted", "已达到合理使用上限,可联系加量"),
        ),
        (
            EvidenceMissingError,
            _make_handler(500, "evidence_missing", "出了点问题,我们已经记录,稍后再试"),
        ),
        (
            EmbeddingModelLoadError,
            _make_handler(503, "embedding_model_load", "服务暂时不可用,请稍后重试"),
        ),
    )
    for exc_type, handler in error_handlers:
        app.add_exception_handler(exc_type, handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
