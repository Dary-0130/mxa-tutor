"""API exception handler 测试。"""

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

from api.dependencies import get_settings
from core.domain.exceptions import (
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
    SlxParseError,
    UploadError,
    ZipBombError,
    ZipSlipError,
)


def test_zip_bomb_returns_400_with_locked_shape() -> None:
    response = _trigger(ZipBombError, "secret path")

    assert response.status_code == 400
    assert response.json() == {
        "error": "zip_bomb",
        "message": "压缩文件异常,请检查后重新上传",
    }


def test_zip_slip_returns_400_with_locked_shape() -> None:
    response = _trigger(ZipSlipError, "secret path")

    assert response.status_code == 400
    assert response.json() == {
        "error": "zip_slip",
        "message": "压缩包内含非法路径,请重新打包后上传",
    }


def test_file_type_not_allowed_returns_400_with_locked_shape() -> None:
    response = _trigger(FileTypeNotAllowedError, "secret.m")

    body = response.json()
    assert response.status_code == 400
    assert body == {
        "error": "file_type_not_allowed",
        "message": "包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试",
    }
    assert ".m" not in body["message"]
    assert ".slx" not in body["message"]


def test_project_not_found_returns_404_with_locked_shape() -> None:
    response = _trigger(ProjectNotFoundError, "secret project")

    assert response.status_code == 404
    assert response.json() == {
        "error": "project_not_found",
        "message": "没有找到这个工程,可能已过期或已被删除,请重新上传",
    }


def test_project_too_large_returns_413_with_dynamic_message(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "12")
    monkeypatch.setenv("MAX_FILES_PER_PROJECT", "34")
    get_settings.cache_clear()

    response = _trigger(ProjectTooLargeError, "secret project")

    body = response.json()
    assert response.status_code == 413
    assert body["error"] == "project_too_large"
    assert "12MB" in body["message"]
    assert "34 个文件" in body["message"]


def test_upload_error_base_fallback_returns_400() -> None:
    response = _trigger(UploadError, "secret path")

    assert response.status_code == 400
    assert response.json() == {
        "error": "upload_error",
        "message": "上传文件有问题,请检查压缩包后重新上传",
    }


def test_project_error_base_fallback_returns_400() -> None:
    response = _trigger(ProjectError, "secret project")

    assert response.status_code == 400
    assert response.json() == {
        "error": "project_error",
        "message": "工程处理失败,请重新上传后再试",
    }


def test_mxa_error_final_fallback_returns_500() -> None:
    response = _trigger(MxaError, "secret content")

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "message": "出了点问题,我们已经记录,稍后再试",
    }


def test_llm_timeout_returns_504_with_locked_shape() -> None:
    response = _trigger(LLMTimeoutError, "secret")

    assert response.status_code == 504
    assert response.json() == {"error": "llm_timeout", "message": "网络较慢,正在重试..."}


def test_overview_generation_returns_502_with_locked_shape() -> None:
    response = _trigger(OverviewGenerationError, "secret")

    assert response.status_code == 502
    assert response.json() == {"error": "overview_generation", "message": "导览生成失败,请刷新重试"}


def test_zip_bomb_leaf_takes_precedence_over_upload_base() -> None:
    response = _trigger(ZipBombError, "secret path")

    body = response.json()
    assert response.status_code == 400
    assert body["error"] == "zip_bomb"
    assert "压缩文件异常" in body["message"]
    assert body["error"] != "upload_error"
    assert "上传文件有问题" not in body["message"]


def test_log_does_not_contain_exception_message() -> None:
    buf = io.StringIO()
    sink_id = logger.add(buf, level="ERROR")
    try:
        response = _trigger(MxaError, "sensitive-content-from-user")

        assert response.status_code == 500
        log_output = buf.getvalue()
        assert "MxaError" in log_output
        assert "/_trigger" in log_output
        assert "sensitive-content-from-user" not in log_output
    finally:
        logger.remove(sink_id)


def test_all_handlers_registered_after_create_app() -> None:
    from api.main import create_app

    app = create_app()
    expected_handlers = {
        ZipBombError,
        ZipSlipError,
        FileTypeNotAllowedError,
        ProjectNotFoundError,
        ProjectTooLargeError,
        UploadError,
        ProjectError,
        MxaError,
        LLMAuthError,
        LLMQuotaError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMServerError,
        SlxParseError,
        MParseError,
        OverviewGenerationError,
    }

    registered = expected_handlers.intersection(app.exception_handlers)

    assert registered == expected_handlers
    assert len(registered) == 16


def test_handler_response_does_not_leak_str_exc() -> None:
    response = _trigger(ZipBombError, "path/to/secret.zip")

    body = response.json()
    assert "path/to/secret.zip" not in body["message"]


def _trigger(exc_type: type[Exception], message: str) -> object:
    from api.main import create_app

    app = create_app()
    _register_trigger(app, exc_type, message)

    with TestClient(app) as client:
        return client.get("/_trigger")


def _register_trigger(app: FastAPI, exc_type: type[Exception], message: str) -> None:
    async def trigger() -> None:
        raise exc_type(message)

    app.add_api_route("/_trigger", trigger, methods=["GET"])
