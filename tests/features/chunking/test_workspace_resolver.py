from __future__ import annotations

from core.domain.m_file import MFile
from features.chunking._workspace_resolver import (
    extract_workspace_literals,
    is_unresolved_var_ref,
)


def _make_mfile(raw_code: str) -> MFile:
    return MFile(
        file_path="t.m",
        file_role="script",
        functions=[],
        imports=[],
        uses_toolbox=[],
        raw_code=raw_code,
    )


class TestExtractWorkspaceLiterals:
    def test_simple_int(self) -> None:
        m_file = _make_mfile("x = 1;")
        assert extract_workspace_literals([m_file]) == {"x": "1"}

    def test_scientific_notation(self) -> None:
        m_file = _make_mfile("Ts_sys = 1e-6;")
        assert extract_workspace_literals([m_file]) == {"Ts_sys": "1e-6"}

    def test_negative_float(self) -> None:
        m_file = _make_mfile("offset = -3.14;")
        assert extract_workspace_literals([m_file]) == {"offset": "-3.14"}

    def test_single_quoted_string(self) -> None:
        m_file = _make_mfile("name = 'DAB';")
        assert extract_workspace_literals([m_file]) == {"name": "'DAB'"}

    def test_skip_full_line_comment(self) -> None:
        m_file = _make_mfile("% x = 1;")
        assert extract_workspace_literals([m_file]) == {}

    def test_skip_expression(self) -> None:
        m_file = _make_mfile("x = 2 * pi;")
        assert extract_workspace_literals([m_file]) == {}

    def test_skip_array(self) -> None:
        m_file = _make_mfile("Lr = [1e-3 2e-3];")
        assert extract_workspace_literals([m_file]) == {}

    def test_skip_function_call(self) -> None:
        m_file = _make_mfile("x = sqrt(2);")
        assert extract_workspace_literals([m_file]) == {}

    def test_last_assignment_wins(self) -> None:
        m_file = _make_mfile("x = 1;\nx = 2;")
        assert extract_workspace_literals([m_file]) == {"x": "2"}

    def test_multiple_files_merged(self) -> None:
        m_file_1 = _make_mfile("Ts_sys = 1e-6;")
        m_file_2 = _make_mfile("U1 = 400;")
        assert extract_workspace_literals([m_file_1, m_file_2]) == {
            "Ts_sys": "1e-6",
            "U1": "400",
        }

    def test_inline_comment_after_assignment(self) -> None:
        m_file = _make_mfile("Ts_sys = 1e-6; % sampling time")
        assert extract_workspace_literals([m_file]) == {"Ts_sys": "1e-6"}


class TestIsUnresolvedVarRef:
    def test_identifier_not_in_workspace(self) -> None:
        assert is_unresolved_var_ref("U1", {}) is True

    def test_identifier_in_workspace(self) -> None:
        assert is_unresolved_var_ref("Ts_sys", {"Ts_sys": "1e-6"}) is False

    def test_number_is_not_unresolved(self) -> None:
        assert is_unresolved_var_ref("400", {}) is False

    def test_expression_is_not_unresolved(self) -> None:
        assert is_unresolved_var_ref("2*pi", {}) is False

    def test_string_literal_is_not_unresolved(self) -> None:
        assert is_unresolved_var_ref("'DAB'", {}) is False

    def test_array_is_not_unresolved(self) -> None:
        assert is_unresolved_var_ref("[1 2 3]", {}) is False

    def test_whitespace_handled(self) -> None:
        assert is_unresolved_var_ref("  U1  ", {}) is True
