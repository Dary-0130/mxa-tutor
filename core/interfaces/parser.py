from abc import ABC, abstractmethod

from core.domain.m_file import MFile
from core.domain.slx_model import SlxModel


class SlxParser(ABC):
    """.slx 文件解析器的抽象接口(具体实现见 adapters/parser/)。"""

    @abstractmethod
    def parse(self, slx_file_path: str) -> SlxModel:
        """解析 .slx 文件。"""
        ...


class MParser(ABC):
    """.m 文件解析器的抽象接口(具体实现见 adapters/parser/)。"""

    @abstractmethod
    def parse(self, m_file_path: str) -> MFile:
        """解析 .m 文件。"""
        ...
