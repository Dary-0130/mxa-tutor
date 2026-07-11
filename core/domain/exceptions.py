class MxaError(Exception):
    """所有业务异常的基类。"""


class LLMError(MxaError):
    """LLM 调用相关异常的基类。"""


class LLMAuthError(LLMError):
    """LLM API 鉴权失败(API Key 无效 / 过期)。"""


class LLMQuotaError(LLMError):
    """LLM 服务商额度耗尽。"""


class LLMRateLimitError(LLMError):
    """LLM 请求被限流。"""


class LLMServerError(LLMError):
    """LLM 服务端错误(5xx)。"""


class LLMTimeoutError(LLMError):
    """LLM 调用超时。"""


class EmbeddingError(MxaError):
    """嵌入模型相关异常的基类。"""


class EmbeddingModelLoadError(EmbeddingError):
    """嵌入模型加载失败。"""


class ParseError(MxaError):
    """文件解析异常的基类。"""


class SlxParseError(ParseError):
    """.slx 文件解析失败。"""


class MParseError(ParseError):
    """.m 文件解析失败。"""


class DocumentParseError(ParseError):
    """PDF / docx 文档解析失败。"""


class ProjectError(MxaError):
    """工程相关异常的基类。"""


class ProjectNotFoundError(ProjectError):
    """指定工程不存在。"""


class ProjectTooLargeError(ProjectError):
    """工程超过大小 / 文件数限制。"""


class UploadError(MxaError):
    """上传相关异常的基类。"""


class ZipBombError(UploadError):
    """压缩比异常,疑似 zip bomb。"""


class ZipSlipError(UploadError):
    """压缩包内含非法路径(zip slip 攻击)。"""


class FileTypeNotAllowedError(UploadError):
    """文件扩展名不在白名单。"""


class QuotaExhaustedError(MxaError):
    """用户使用额度耗尽。"""


class EvidenceMissingError(MxaError):
    """LLM 回答缺少证据引用(被 CitationEnforcer 拦截)。"""


class OverviewGenerationError(MxaError):
    """项目导览生成失败。"""


class PaperSpecGenerationError(MxaError):
    """PaperSpec 生成失败。"""

    def __init__(
        self,
        message: str = "",
        *,
        reason_code: str | None = None,
        finish_reason: str | None = None,
        leaf: str | None = None,
        locator_namespace: str | None = None,
        loc: tuple[str, ...] | None = None,
        validation_errors: tuple[dict[str, object], ...] | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.finish_reason = finish_reason
        self.leaf = leaf
        self.locator_namespace = locator_namespace
        self.loc = loc
        self.validation_errors = validation_errors or ()
        super().__init__(message)


class PaperPlanGenerationError(MxaError):
    """Paper plan 生成失败。"""

    def __init__(
        self,
        message: str = "",
        *,
        reason_code: str | None = None,
        finish_reason: str | None = None,
        leaf: str | None = None,
        locator_namespace: str | None = None,
        loc: tuple[str, ...] | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.finish_reason = finish_reason
        self.leaf = leaf
        self.locator_namespace = locator_namespace
        self.loc = loc
        super().__init__(message)


class PaperNotFoundError(MxaError):
    """指定 paper bundle 不存在。"""


class PaperTuningError(MxaError):
    """Paper tuning suggestion 生成失败。"""


class PaperUserSupplyError(MxaError):
    """用户补充 paper plan 参数失败。"""


class PaperUserSupplyInProgressError(PaperUserSupplyError):
    """A paper plan mutation is already running for the same paper."""


class PaperParameterCorrectionError(MxaError):
    """用户纠错 paper plan 参数失败。"""

    def __init__(self, error_code: str, status_code: int) -> None:
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(error_code)


class PaperReparseSourceUnavailableError(MxaError):
    """Paper reparse source package is missing or expired."""


class PaperReparseInProgressError(MxaError):
    """A paper reparse is already running for the same paper."""


class PaperReparseFailedError(MxaError):
    """Paper reparse failed before the replacement transaction."""


class PaperReparseStoreError(MxaError):
    """Paper reparse replacement failed in persistent storage."""


class MatlabEngineError(MxaError):
    """MATLAB Engine substrate 相关异常的基类。"""

    def __init__(
        self,
        reason_code: str,
        *,
        diagnostic_metadata: dict[str, object] | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.diagnostic_metadata = dict(diagnostic_metadata or {})
        super().__init__(reason_code)


class MatlabEngineUnavailableError(MatlabEngineError):
    """MATLAB Engine Python package 不可用。"""


class MatlabEngineDisabledError(MatlabEngineError):
    """MATLAB Engine service integration is disabled or not wired."""


class MatlabEngineStartupError(MatlabEngineError):
    """MATLAB Engine owned session 启动失败。"""


class MatlabEngineConnectionError(MatlabEngineError):
    """MATLAB Engine shared session 连接失败。"""


class MatlabEngineCapabilityError(MatlabEngineError):
    """MATLAB / Simulink 能力或许可不满足运行要求。"""


class MatlabEngineExecutionError(MatlabEngineError):
    """MATLAB 函数或模型执行失败。"""


class MatlabEngineTimeoutError(MatlabEngineError):
    """MATLAB Engine FutureResult 等待超时。"""


class MatlabEngineCancelledError(MatlabEngineError):
    """MATLAB Engine 调用被主动取消。"""


class MatlabEngineSessionError(MatlabEngineError):
    """MATLAB Engine session 状态不允许当前操作。"""


class MatlabEngineBusyError(MatlabEngineSessionError):
    """同一 MATLAB Engine session 已有调用在执行。"""


class BridgeExplanationError(MxaError):
    """MATLAB bridge 报错解释生成失败。"""


class BridgeExplanationUnavailableError(BridgeExplanationError):
    """MATLAB bridge 报错解释 provider 暂不可用。"""


class BridgeExplanationTimeoutError(BridgeExplanationError):
    """MATLAB bridge 报错解释调用超时。"""


class BridgeRunStateValidationError(MxaError):
    """MATLAB bridge run-state payload failed privacy validation."""


class ChatSessionNotFoundError(ProjectError):
    """指定对话会话不存在。"""


class StoreError(MxaError):
    """持久化存储层异常。"""


class VectorStoreError(StoreError):
    """向量存储层异常。"""


class ChatGenerationError(MxaError):
    """问答生成失败。"""


class UnsupportedTeachingLevelError(MxaError):
    """MCS 阶段不开放的 teaching level。"""


class TeachingUnitGenerationError(MxaError):
    """教学单元生成失败。"""


class TeachingUnitInProgressError(MxaError):
    """教学单元已有生成任务进行中。"""


class TeachingUnitTargetNotFoundError(ProjectError):
    """指定 TeachingUnit target 不存在。"""
