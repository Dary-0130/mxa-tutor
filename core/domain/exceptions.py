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


class ParseError(MxaError):
    """文件解析异常的基类。"""


class SlxParseError(ParseError):
    """.slx 文件解析失败。"""


class MParseError(ParseError):
    """.m 文件解析失败。"""


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


class ChatSessionNotFoundError(ProjectError):
    """指定对话会话不存在。"""


class StoreError(MxaError):
    """持久化存储层异常。"""
