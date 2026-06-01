from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """嵌入模型的抽象接口(具体实现见 adapters/embedding/)。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入,返回每个文本的向量。"""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度。"""
        ...
