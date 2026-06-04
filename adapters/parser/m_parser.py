from pathlib import Path

from adapters.parser._m_dependencies import detect_toolboxes, extract_imports
from adapters.parser._m_lex import preprocess
from adapters.parser._m_structure import classify_file_role, extract_functions
from core.domain.exceptions import MParseError
from core.domain.m_file import MFile, MFunction
from core.interfaces.parser import MParser


class MParserImpl(MParser):
    """.m 文件解析器具体实现(正则 + 简单 AST)。"""

    def parse(self, m_file_path: str) -> MFile:
        """解析单个 .m 文件。"""
        raw_code = read_m_file(m_file_path)
        folded_code, line_map = preprocess(raw_code)
        role = classify_file_role(folded_code)
        if role == "class":
            functions: list[MFunction] = []
        else:
            functions = extract_functions(
                preprocessed_code=folded_code,
                line_map=line_map,
                original_lines=raw_code.splitlines(),
            )

        return MFile(
            file_path=str(Path(m_file_path)),
            file_role=role,
            functions=functions,
            imports=extract_imports(folded_code),
            uses_toolbox=detect_toolboxes(folded_code),
            raw_code=raw_code,
        )


def read_m_file(m_file_path: str) -> str:
    """bytes-first 读取 .m 文件,优先保住中文注释。"""
    path = Path(m_file_path)
    if not path.exists():
        raise MParseError(f"找不到 .m 文件:{m_file_path}")
    if path.is_dir():
        raise MParseError(f"路径不是文件:{m_file_path}")

    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise MParseError(f".m 文件读取失败:{m_file_path}") from exc

    if b"\x00" in raw_bytes[:8192]:
        raise MParseError(f".m 文件解析失败:不是有效的文本文件({m_file_path})")

    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")
