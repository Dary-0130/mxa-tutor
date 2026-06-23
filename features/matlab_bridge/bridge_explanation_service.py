"""LLM-backed MATLAB bridge error explanation service."""

from __future__ import annotations

import asyncio
import json
import re

from loguru import logger
from pydantic import ValidationError

from core.domain.bridge_explanation import BridgeExplanationRequest, BridgeExplanationResult
from core.domain.exceptions import (
    BridgeExplanationError,
    BridgeExplanationTimeoutError,
    BridgeExplanationUnavailableError,
    LLMAuthError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from core.interfaces.llm_provider import LLMMessage, LLMResponse, TextProvider
from features.matlab_bridge.bridge_explanation_schemas import BridgeExplanationResultModel
from features.paper._prompt_loader import PromptTemplate, load_prompt_template

DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS = 12.0
DEFAULT_BRIDGE_SERVER_DEADLINE_SECONDS = 55.0
DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS = 2048
_BRIDGE_EXPLANATION_FAILED_MESSAGE = "报错解释生成失败,请稍后重试"
_BRIDGE_EXPLANATION_UNAVAILABLE_MESSAGE = "报错解释服务暂时不可用,请稍后重试"
_BRIDGE_EXPLANATION_TIMEOUT_MESSAGE = "报错解释超时,请稍后重试"
_DIAGNOSTIC_SOURCE_DESCRIPTIONS = {
    "manual_error": "用户手动粘贴并确认的 MATLAB 报错文本",
    "auto_captured_error": "客户端自动采集、脱敏、截断并经用户确认的 MATLAB 报错文本",
}
_REQUIRED_SOURCE_CAVEAT_FRAGMENTS = {
    "manual_error": "粘贴的报错文本",
    "auto_captured_error": "自动采集的报错文本",
}

_REDACTION_PLACEHOLDERS = {"[REDACTED_PATH]", "[REDACTED_SECRET]", "[REDACTED_SOURCE]"}
_BUILTIN_IDENTIFIER_ALLOWLIST = {
    "addpath",
    "clear",
    "dbstack",
    "dbstop",
    "doc",
    "exist",
    "help",
    "isfile",
    "isfolder",
    "license",
    "matlab",
    "matlabpath",
    "path",
    "rehash",
    "restoredefaultpath",
    "rmpath",
    "simulink",
    "ver",
    "which",
}
_PATH_PATTERNS = (
    re.compile(r"file://[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9._$-]+\\[^\s'\"<>]+"),
    re.compile(r"[A-Za-z]:[\\/][^\s'\"<>]+"),
    re.compile(r"/(?:Users|home|tmp|var|opt|mnt|Volumes)/[^\s'\"<>]+"),
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[^\s'\"<>]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
)
_SOURCE_PATTERNS = (
    re.compile(r"```[\s\S]*?```"),
    re.compile(r"(?im)^\s*(?:function|classdef|#include)\b.*$"),
)
_PROHIBITED_ASSERTIONS = (
    re.compile(r"(?:已经|已)(?:运行|执行|检查|验证|确认)"),
    re.compile(r"已跑"),
    re.compile(r"仿真.*(?:证明|确认|验证)"),
    re.compile(r"(?:可以确认|根因就是|就是根因|确定是|一定是|必然是|保证)"),
    re.compile(r"执行.*即可解决"),
    re.compile(r"文件(?:确实)?存在"),
    re.compile(r"(?:工具箱|toolbox).*(?:已安装|可用|存在|正常)", re.IGNORECASE),
    re.compile(r"(?:许可证|license).*(?:可用|正常|有效|available|valid)", re.IGNORECASE),
    re.compile(r"(?:版本|release).*(?:兼容|已验证|保证)"),
)
_IDENTIFIER_CHARS = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


class BridgeExplanationService:
    """Generate one deterministic-guarded bridge error explanation."""

    def __init__(
        self,
        text_provider: TextProvider,
        prompt_template: PromptTemplate | None = None,
        *,
        provider_timeout_s: float = DEFAULT_BRIDGE_PROVIDER_TIMEOUT_SECONDS,
        server_deadline_s: float = DEFAULT_BRIDGE_SERVER_DEADLINE_SECONDS,
        max_tokens: int = DEFAULT_BRIDGE_EXPLANATION_MAX_TOKENS,
    ) -> None:
        self._text_provider = text_provider
        self._prompt_template = prompt_template or load_prompt_template(
            "bridge_error_explanation.yaml"
        )
        self._provider_timeout_s = provider_timeout_s
        self._server_deadline_s = server_deadline_s
        self._max_tokens = max_tokens

    async def explain(self, request: BridgeExplanationRequest) -> BridgeExplanationResult:
        redacted_error_text = redact_bridge_error_text(request.error_text)
        messages = self._build_messages(request, redacted_error_text)
        logger.info(
            (
                "Bridge explanation LLM call: request_id={} matlab_release={} "
                "client_version={} diagnostic_kind={} prompt_version={} payload_chars={}"
            ),
            str(request.request_id),
            request.matlab_release,
            request.client_version,
            request.diagnostic_kind,
            self._prompt_template.version,
            len(redacted_error_text),
        )
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._text_provider.chat,
                    messages,
                    json_mode=True,
                    timeout=self._provider_timeout_s,
                    max_tokens=self._max_tokens,
                ),
                timeout=self._server_deadline_s,
            )
        except (TimeoutError, LLMTimeoutError) as exc:
            logger.error(
                "Bridge explanation timeout: request_id={} error_type={}",
                str(request.request_id),
                type(exc).__name__,
            )
            raise BridgeExplanationTimeoutError(_BRIDGE_EXPLANATION_TIMEOUT_MESSAGE) from None
        except (LLMAuthError, LLMQuotaError, LLMRateLimitError, LLMServerError) as exc:
            logger.error(
                "Bridge explanation provider unavailable: request_id={} error_type={}",
                str(request.request_id),
                type(exc).__name__,
            )
            raise BridgeExplanationUnavailableError(
                _BRIDGE_EXPLANATION_UNAVAILABLE_MESSAGE
            ) from None
        except Exception as exc:
            logger.error(
                "Bridge explanation provider failed: request_id={} error_type={}",
                str(request.request_id),
                type(exc).__name__,
            )
            raise BridgeExplanationError(_BRIDGE_EXPLANATION_FAILED_MESSAGE) from None

        return self._parse_and_validate(response, request, redacted_error_text)

    def _build_messages(
        self,
        request: BridgeExplanationRequest,
        redacted_error_text: str,
    ) -> list[LLMMessage]:
        user = _render_user(
            self._prompt_template.user,
            {
                "REQUEST_ID": str(request.request_id),
                "MATLAB_RELEASE": request.matlab_release,
                "CLIENT_VERSION": request.client_version,
                "DIAGNOSTIC_KIND": request.diagnostic_kind,
                "DIAGNOSTIC_SOURCE_DESCRIPTION": _DIAGNOSTIC_SOURCE_DESCRIPTIONS[
                    request.diagnostic_kind
                ],
                "SOURCE_CAVEAT_FRAGMENT": _REQUIRED_SOURCE_CAVEAT_FRAGMENTS[
                    request.diagnostic_kind
                ],
                "REDACTED_ERROR_TEXT": redacted_error_text,
            },
        )
        return [
            LLMMessage(role="system", content=self._prompt_template.system),
            LLMMessage(role="user", content=user),
        ]

    def _parse_and_validate(
        self,
        response: LLMResponse,
        request: BridgeExplanationRequest,
        redacted_error_text: str,
    ) -> BridgeExplanationResult:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            _log_validation_error(request, "json_parse", exc)
            raise BridgeExplanationError(_BRIDGE_EXPLANATION_FAILED_MESSAGE) from None

        if not isinstance(payload, dict):
            _log_validation_error(request, "payload_not_mapping")
            raise BridgeExplanationError(_BRIDGE_EXPLANATION_FAILED_MESSAGE) from None

        try:
            model = BridgeExplanationResultModel.model_validate(payload)
            if model.request_id != request.request_id:
                raise ValueError("request_id_mismatch")
            _validate_grounding(model, redacted_error_text)
            _validate_source_caveat(model, request.diagnostic_kind)
            _validate_output_privacy(model)
        except (ValidationError, ValueError) as exc:
            _log_validation_error(request, type(exc).__name__)
            raise BridgeExplanationError(_BRIDGE_EXPLANATION_FAILED_MESSAGE) from None

        logger.info(
            "Bridge explanation completed: request_id={} model={} latency_ms={}",
            str(request.request_id),
            response.model,
            response.latency_ms,
        )
        return model.to_domain()


def redact_bridge_error_text(text: str) -> str:
    """Apply server-side redaction before the provider sees the user error text."""

    redacted = text
    for pattern in _PATH_PATTERNS:
        redacted = pattern.sub("[REDACTED_PATH]", redacted)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    for pattern in _SOURCE_PATTERNS:
        redacted = pattern.sub("[REDACTED_SOURCE]", redacted)
    return redacted


def bridge_explanation_error_payloads() -> dict[int, dict[str, str]]:
    """Return the frozen status-code to error-code mapping."""

    return {
        502: {
            "error": "bridge_explanation_failed",
            "message": _BRIDGE_EXPLANATION_FAILED_MESSAGE,
        },
        503: {
            "error": "bridge_explanation_unavailable",
            "message": _BRIDGE_EXPLANATION_UNAVAILABLE_MESSAGE,
        },
        504: {
            "error": "bridge_explanation_timeout",
            "message": _BRIDGE_EXPLANATION_TIMEOUT_MESSAGE,
        },
    }


def _render_user(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"__{key}__", value)
    return rendered


def _validate_grounding(model: BridgeExplanationResultModel, redacted_error_text: str) -> None:
    output_text = "\n".join(_iter_output_strings(model))
    for pattern in _PROHIBITED_ASSERTIONS:
        if pattern.search(output_text):
            raise ValueError("prohibited_assertion")
    _validate_event_identifiers(output_text, redacted_error_text)

    for cause in model.likely_causes:
        for signal in cause.supporting_signals:
            if signal not in redacted_error_text:
                raise ValueError("supporting_signal_not_in_redacted_input")
            if _is_placeholder_only(signal):
                raise ValueError("supporting_signal_placeholder_only")


def _validate_output_privacy(model: BridgeExplanationResultModel) -> None:
    output_text = "\n".join(_iter_output_strings(model))
    if contains_private_text(output_text):
        raise ValueError("privacy_scan_failed")


def _validate_source_caveat(model: BridgeExplanationResultModel, diagnostic_kind: str) -> None:
    required_fragment = _REQUIRED_SOURCE_CAVEAT_FRAGMENTS[diagnostic_kind]
    if not any(required_fragment in caveat for caveat in model.caveats):
        raise ValueError("source_caveat_missing")


def contains_private_text(text: str) -> bool:
    """Return True when text contains material that must not leave the server."""

    return any(
        pattern.search(text) for pattern in (*_PATH_PATTERNS, *_SECRET_PATTERNS, *_SOURCE_PATTERNS)
    )


def _validate_event_identifiers(output_text: str, redacted_error_text: str) -> None:
    input_tokens = {token.casefold() for token in _IDENTIFIER_CHARS.findall(redacted_error_text)}
    for token in re.findall(r"`([^`\n]{1,80})`", output_text):
        parts = _IDENTIFIER_CHARS.findall(token)
        if not parts:
            continue
        for part in parts:
            normalized = part.casefold()
            if normalized in _BUILTIN_IDENTIFIER_ALLOWLIST:
                continue
            if normalized not in input_tokens:
                raise ValueError("invented_event_identifier")


def _is_placeholder_only(value: str) -> bool:
    stripped = value.strip()
    if stripped in _REDACTION_PLACEHOLDERS:
        return True
    without_placeholders = stripped
    for placeholder in _REDACTION_PLACEHOLDERS:
        without_placeholders = without_placeholders.replace(placeholder, "")
    return not any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in without_placeholders)


def _iter_output_strings(model: BridgeExplanationResultModel) -> list[str]:
    values = [model.meaning, *model.caveats]
    for cause in model.likely_causes:
        values.append(cause.cause)
        values.extend(cause.supporting_signals)
    values.extend(step.action for step in model.next_steps)
    return values


def _log_validation_error(
    request: BridgeExplanationRequest,
    error_type: str,
    exc: Exception | None = None,
) -> None:
    _ = exc
    logger.error(
        "Bridge explanation validation failed: request_id={} error_type={}",
        str(request.request_id),
        error_type,
    )
