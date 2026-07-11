from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelCapability:
    """模型能力声明,用于路由和成本控制。"""

    model_name: str
    supports_streaming: bool = False
    supports_json: bool = False
    supports_tool_call: bool = False
    supports_long_context: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 4096
    cost_input_per_million: float | None = None
    cost_output_per_million: float | None = None


@dataclass
class LLMMessage:
    """LLM 对话中的单条消息。"""

    role: str
    content: str


@dataclass
class LLMResponse:
    """LLM 单次响应的结构化结果。"""

    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int
    finish_reason: str | None = None
    system_fingerprint: str | None = None


class TextProvider(ABC):
    """文本类 LLM 提供方的抽象接口(DeepSeek 等具体实现见 adapters/llm/)。"""

    @abstractmethod
    def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        timeout: float = 30.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """生成一轮文本响应。"""
        ...

    @abstractmethod
    def capability(self) -> ModelCapability:
        """返回模型能力声明。"""
        ...
