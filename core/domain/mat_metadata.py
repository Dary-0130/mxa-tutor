from dataclasses import dataclass


@dataclass
class MatVariable:
    """单个 .mat 变量的元信息(不含原始数据)。"""

    name: str
    var_type: str
    shape: tuple[int, ...]
    likely_role: str | None
    first_field_names: list[str]


@dataclass
class MatMetadata:
    """单个 .mat 文件的元信息汇总,不存原始数据。"""

    file_path: str
    file_size_bytes: int
    variables: list[MatVariable]
