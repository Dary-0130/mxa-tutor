"""TASK-206 API error handler contract tests."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.dependencies import get_settings
from api.middleware.error_handler import register_error_handlers
from app.config import AppSettings
from core.domain.exceptions import (
    ChatGenerationError,
    ChatSessionNotFoundError,
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
    UploadError,
    ZipBombError,
    ZipSlipError,
)

SECRET_USER_MESSAGE = "SECRET_USER_MESSAGE"
SECRET_DETAIL = "SECRET_DETAIL"
SECRET_STUDENT_INPUT = "SECRET_STUDENT_INPUT"
LOG_TEMPLATE = "API error: exception={} status={} path={} method={}"

HandlerCase = tuple[type[Exception], int, str, str]

HANDLER_CASES: list[HandlerCase] = [
    (ZipBombError, 400, "zip_bomb", "压缩文件异常,请检查后重新上传"),
    (ZipSlipError, 400, "zip_slip", "压缩包内含非法路径,请重新打包后上传"),
    (
        FileTypeNotAllowedError,
        400,
        "file_type_not_allowed",
        "包含不支持的文件类型,请只上传 MATLAB/Simulink 工程相关文件后重试",
    ),
    (
        ProjectNotFoundError,
        404,
        "project_not_found",
        "没有找到这个工程,可能已过期或已被删除,请重新上传",
    ),
    (UploadError, 400, "upload_error", "上传文件有问题,请检查压缩包后重新上传"),
    (ProjectError, 400, "project_error", "工程处理失败,请重新上传后再试"),
    (MxaError, 500, "internal_error", "出了点问题,我们已经记录,稍后再试"),
    (LLMAuthError, 503, "llm_auth", "服务暂时不可用,请稍后重试"),
    (LLMQuotaError, 503, "llm_quota", "服务繁忙,请稍后"),
    (LLMRateLimitError, 429, "llm_rate_limit", "请求太频繁,稍等一下"),
    (LLMTimeoutError, 504, "llm_timeout", "网络较慢,正在重试..."),
    (LLMServerError, 502, "llm_server", "AI 服务暂不稳定,请刷新重试"),
    (SlxParseError, 400, "slx_parse", "Simulink 模型解析失败,可能版本过老或损坏"),
    (MParseError, 400, "m_parse", ".m 文件解析失败,请检查文件编码"),
    (OverviewGenerationError, 502, "overview_generation", "导览生成失败,请刷新重试"),
    (ChatSessionNotFoundError, 404, "chat_session_not_found", "对话不存在"),
    (StoreError, 500, "store_error", "系统暂时不可用,请稍后重试"),
    (ChatGenerationError, 502, "chat_generation", "回答生成失败,请刷新重试"),
    (QuotaExhaustedError, 402, "quota_exhausted", "已达到合理使用上限,可联系加量"),
    (EvidenceMissingError, 500, "evidence_missing", "出了点问题,我们已经记录,稍后再试"),
]

EXCEPTION_BY_NAME: dict[str, type[Exception]] = {
    exc_class.__name__: exc_class for exc_class, _, _, _ in HANDLER_CASES
}
EXCEPTION_BY_NAME["ProjectTooLargeError"] = ProjectTooLargeError


class CountPayload(BaseModel):
    count: int


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[AppSettings]:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-for-test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "12")
    monkeypatch.setenv("MAX_FILES_PER_PROJECT", "34")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def test_client(settings: AppSettings) -> Iterator[TestClient]:
    test_app = FastAPI()
    register_error_handlers(test_app, settings)
    _install_test_routes(test_app)
    with TestClient(test_app) as client:
        yield client


class TestBusinessHandlers:
    @pytest.mark.parametrize(
        ("exc_class", "status_code", "machine_code", "message"),
        HANDLER_CASES,
    )
    def test_static_handler_messages(
        self,
        test_client: TestClient,
        exc_class: type[Exception],
        status_code: int,
        machine_code: str,
        message: str,
    ) -> None:
        response = test_client.get(f"/_test/raise/{exc_class.__name__}")

        assert response.status_code == status_code
        assert response.json() == {"error": machine_code, "message": message}
        assert SECRET_USER_MESSAGE not in response.text

    def test_project_too_large_dynamic_message(
        self, test_client: TestClient, settings: AppSettings
    ) -> None:
        response = test_client.get("/_test/raise/ProjectTooLargeError")

        body = response.json()
        assert response.status_code == 413
        assert body["error"] == "project_too_large"
        assert str(settings.max_upload_size_mb) in body["message"]
        assert str(settings.max_files_per_project) in body["message"]
        assert "MB 以内" in body["message"]
        assert "个文件以下" in body["message"]
        assert SECRET_USER_MESSAGE not in body["message"]


class TestNewLeafHandlers:
    def test_quota_exhausted_returns_402(self, test_client: TestClient) -> None:
        response = test_client.get("/_test/raise/QuotaExhaustedError")

        assert response.status_code == 402
        assert response.json() == {
            "error": "quota_exhausted",
            "message": "已达到合理使用上限,可联系加量",
        }

    def test_evidence_missing_is_last_resort_500(self, test_client: TestClient) -> None:
        response = test_client.get("/_test/raise/EvidenceMissingError")

        assert response.status_code == 500
        assert response.json() == {
            "error": "evidence_missing",
            "message": "出了点问题,我们已经记录,稍后再试",
        }


class TestDefaultHandlers:
    def test_404_not_found_is_chinese_and_redacted(self, test_client: TestClient) -> None:
        response = test_client.get("/nonexistent-secret-path")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found", "message": "请求的资源不存在"}
        _assert_text_omits(response.text, ("nonexistent-secret-path", "detail", "errors"))

    def test_405_method_not_allowed_is_chinese_and_redacted(self, test_client: TestClient) -> None:
        response = test_client.post("/_test/get-only")

        assert response.status_code == 405
        assert response.json() == {
            "error": "method_not_allowed",
            "message": "请求方式不正确",
        }
        _assert_text_omits(response.text, ("detail", "errors"))

    def test_generic_http_exception_is_chinese_and_redacted(
        self, test_client: TestClient, mocker
    ) -> None:
        error_log = mocker.patch("api.middleware.error_handler.logger.error")

        response = test_client.get("/_test/http-error")

        assert response.status_code == 418
        assert response.json() == {"error": "http_error", "message": "请求处理失败,请稍后重试"}
        _assert_text_omits(response.text, (SECRET_DETAIL, "detail", "errors"))
        error_log.assert_called_once_with(
            LOG_TEMPLATE, "HTTPException", 418, "/_test/http-error", "GET"
        )
        _assert_text_omits(_mock_call_text(error_log), (SECRET_DETAIL, "detail", "errors"))

    def test_422_validation_error_is_chinese_and_redacted(
        self, test_client: TestClient, mocker
    ) -> None:
        error_log = mocker.patch("api.middleware.error_handler.logger.error")

        response = test_client.post("/_test/validate", json={"count": SECRET_STUDENT_INPUT})

        assert response.status_code == 422
        assert response.json() == {
            "error": "validation_error",
            "message": "请求参数有问题,请检查后重试",
        }
        _assert_text_omits(response.text, (SECRET_STUDENT_INPUT, "detail", "errors"))
        error_log.assert_called_once_with(
            LOG_TEMPLATE, "RequestValidationError", 422, "/_test/validate", "POST"
        )
        _assert_text_omits(_mock_call_text(error_log), (SECRET_STUDENT_INPUT, "detail", "errors"))


class TestLogPrivacy:
    def test_business_handler_log_contains_only_metadata(
        self, test_client: TestClient, mocker
    ) -> None:
        error_log = mocker.patch("api.middleware.error_handler.logger.error")

        response = test_client.get("/_test/raise/MxaError")

        assert response.status_code == 500
        error_log.assert_called_once_with(
            LOG_TEMPLATE, "MxaError", 500, "/_test/raise/MxaError", "GET"
        )
        _assert_text_omits(_mock_call_text(error_log), (SECRET_USER_MESSAGE, "detail", "errors"))


class TestDocstring:
    def test_error_handler_docstring_reflects_task_206_counts(self) -> None:
        source = Path("api/middleware/error_handler.py").read_text(encoding="utf-8")

        assert re.search(r"minimal ERROR_MAP[^\d]*\b8\b|注册\s*\b8\s*个", source) is None
        assert "21 个业务 handler" in source
        assert "2 个 FastAPI 默认 handler 兜底" in source


def _install_test_routes(test_app: FastAPI) -> None:
    async def raise_error(exc_name: str) -> None:
        exc_class = EXCEPTION_BY_NAME[exc_name]
        raise exc_class(SECRET_USER_MESSAGE)

    async def get_only() -> dict[str, bool]:
        return {"ok": True}

    async def http_error() -> None:
        raise StarletteHTTPException(status_code=418, detail=SECRET_DETAIL)

    async def validate(payload: CountPayload) -> dict[str, int]:
        return {"count": payload.count}

    test_app.add_api_route("/_test/raise/{exc_name}", raise_error, methods=["GET"])
    test_app.add_api_route("/_test/get-only", get_only, methods=["GET"])
    test_app.add_api_route("/_test/http-error", http_error, methods=["GET"])
    test_app.add_api_route("/_test/validate", validate, methods=["POST"])


def _assert_text_omits(text: str, forbidden_fragments: tuple[str, ...]) -> None:
    for fragment in forbidden_fragments:
        assert fragment not in text


def _mock_call_text(mock) -> str:
    args_text = " ".join(repr(arg) for arg in mock.call_args.args)
    kwargs_text = " ".join(f"{key}={value!r}" for key, value in mock.call_args.kwargs.items())
    return f"{args_text} {kwargs_text}"
