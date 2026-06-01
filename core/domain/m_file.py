from dataclasses import dataclass


@dataclass
class MFunction:
    """MATLAB 文件中的单个函数定义。"""

    name: str
    inputs: list[str]
    outputs: list[str]
    line_range: tuple[int, int]
    docstring: str | None


@dataclass
class MFile:
    """单个 .m 文件解析后的结构化表示。"""

    file_path: str
    file_role: str
    functions: list[MFunction]
    imports: list[str]
    uses_toolbox: list[str]
    raw_code: str
