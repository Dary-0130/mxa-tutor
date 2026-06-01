import pytest

from core.domain.m_file import MFile
from core.domain.slx_model import SlxModel
from core.interfaces.parser import MParser, SlxParser


def test_slx_parser_is_abstract() -> None:
    with pytest.raises(TypeError):
        SlxParser()


def test_m_parser_is_abstract() -> None:
    with pytest.raises(TypeError):
        MParser()


class _StubSlxParser(SlxParser):
    def parse(self, slx_file_path: str) -> SlxModel:
        return SlxModel(
            file_path=slx_file_path,
            name="stub",
            blocks=[],
            lines=[],
            subsystems={},
            solver_config={},
            parse_warnings=[],
        )


class _StubMParser(MParser):
    def parse(self, m_file_path: str) -> MFile:
        return MFile(
            file_path=m_file_path,
            file_role="script",
            functions=[],
            imports=[],
            uses_toolbox=[],
            raw_code="",
        )


def test_parser_stubs_work() -> None:
    slx_parser = _StubSlxParser()
    m_parser = _StubMParser()

    assert slx_parser.parse("model.slx").file_path == "model.slx"
    assert m_parser.parse("init.m").file_path == "init.m"
