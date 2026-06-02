from pathlib import Path

from adapters.parser._m_dependencies import detect_toolboxes, extract_imports
from adapters.parser._m_lex import placeholder_strings, preprocess
from adapters.parser._m_structure import classify_file_role, extract_functions
from adapters.parser.m_parser import MParserImpl


def test_preprocess_strips_comments_and_preserves_line_map_tuple() -> None:
    raw = "\n".join(
        [
            "%{",
            "function hidden()",
            "%}",
            "x = 1; %{ inline block marker is just a line comment",
            "y = 'hello %world'; % trailing comment",
        ]
    )

    folded, line_map = preprocess(raw)

    assert "hidden" not in folded
    assert "inline block marker" not in folded
    assert "trailing comment" not in folded
    assert isinstance(line_map[1], tuple)
    assert line_map[4] == (4, 4)


def test_placeholder_strings_handles_quotes_and_transpose() -> None:
    code = "A = B'; C = 'hello'; D = [A B]'; E = 'it''s'; F = \"said \"\"hi\"\"\";"

    placeheld, string_map = placeholder_strings(code)

    assert "B'" in placeheld
    assert "[A B]'" in placeheld
    assert len(string_map) == 3


def test_continuation_line_map_covers_original_line_range() -> None:
    folded, line_map = preprocess("function y = f(x, ...\n    z)\ny = x + z;\nend")

    assert folded.splitlines()[0].strip().startswith("function y = f(x,")
    assert folded.splitlines()[0].strip().endswith("z)")
    assert line_map[1] == (1, 2)
    assert line_map[2] == (3, 3)


def test_classify_file_role_script_function_class() -> None:
    assert classify_file_role("x = 1;") == "script"
    assert classify_file_role("function y = f(x)\nend") == "function"
    assert classify_file_role("classdef MyClass\nend") == "class"
    assert classify_file_role("") == "script"


def test_function_signature_five_forms() -> None:
    code = "\n".join(
        [
            "function out = one(in1, in2)",
            "end",
            "function [out1, out2] = two(in)",
            "end",
            "function three(in1, in2)",
            "end",
            "function four",
            "end",
            "function out = five",
            "end",
        ]
    )

    funcs = _extract(code)

    assert [(func.name, func.inputs, func.outputs) for func in funcs] == [
        ("one", ["in1", "in2"], ["out"]),
        ("two", ["in"], ["out1", "out2"]),
        ("three", ["in1", "in2"], []),
        ("four", [], []),
        ("five", [], ["out"]),
    ]


def test_arguments_block_is_skipped_before_docstring() -> None:
    funcs = _extract(
        "\n".join(
            [
                "function y = f(x)",
                "arguments",
                "    x (1,1) double",
                "end",
                "% This is the doc",
                "y = x + 1;",
                "end",
            ]
        )
    )

    assert funcs[0].docstring == "This is the doc"


def test_multiline_signature_line_range_uses_original_lines() -> None:
    funcs = _extract("function y = f(x, ...\n            z)\ny = x + z;\nend")

    assert funcs[0].line_range == (1, 4)


def test_docstring_is_extracted_from_original_lines() -> None:
    funcs = _extract("function y = f(x)\n  % This is the doc\n  y = x + 1;\nend")

    assert funcs[0].docstring == "This is the doc"


def test_nested_function_is_not_extracted_but_local_function_is() -> None:
    funcs = _extract(
        "\n".join(
            [
                "function outer()",
                "    function inner()",
                "        x = 1;",
                "    end",
                "end",
                "",
                "function localFunc()",
                "z = 3;",
                "end",
            ]
        )
    )

    assert [func.name for func in funcs] == ["outer", "localFunc"]


def test_multiple_local_functions_without_explicit_end_are_extracted() -> None:
    funcs = _extract(
        "\n".join(
            [
                "function y = first(x)",
                "y = x + 1;",
                "function z = second(x)",
                "z = x + 2;",
            ]
        )
    )

    assert [func.name for func in funcs] == ["first", "second"]
    assert funcs[0].line_range == (1, 2)
    assert funcs[1].line_range == (3, 4)


def test_anonymous_function_is_not_extracted() -> None:
    funcs = _extract("f = @(x) x.^2;\nfunction y = realFunc(x)\ny = f(x);\nend")

    assert [func.name for func in funcs] == ["realFunc"]


def test_end_in_index_does_not_close_function_early() -> None:
    funcs = _extract("function y = f(A)\ny = A(end);\nif y > 0; y = y + 1; end\nend")

    assert funcs[0].line_range == (1, 4)


def test_bad_function_signature_is_skipped() -> None:
    funcs = _extract("function = bad\nfunction good()\nend")

    assert [func.name for func in funcs] == ["good"]


def test_classdef_short_circuit_skips_methods(tmp_path: Path) -> None:
    path = tmp_path / "MyClass.m"
    path.write_text(
        "\n".join(
            [
                "classdef MyClass",
                "    methods",
                "        function y = run(obj, x)",
                "            y = x + 1;",
                "        end",
                "    end",
                "    methods (Static)",
                "        function y = helper(x)",
                "            y = x;",
                "        end",
                "    end",
                "end",
            ]
        ),
        encoding="utf-8",
    )

    mfile = MParserImpl().parse(str(path))

    assert mfile.file_role == "class"
    assert mfile.functions == []


def test_imports_are_extracted_in_order_without_duplicates() -> None:
    imports = extract_imports("import matlab.io.*\nimport containers.Map;\nimport matlab.io.*")

    assert imports == ["matlab.io.*", "containers.Map"]


def test_toolbox_high_confidence_matches() -> None:
    code = "\n".join(
        [
            "sys = tf([1], [1 2 1]);",
            "[pxx, f] = pwelch(x);",
            'sim("modelName");',
            "lms = dsp.LMSFilter();",
            "y = qammod(data, 16);",
            'opts = optimoptions("fmincon");',
            "data = iddata(y, u, Ts);",
            "x = fi(0.5, 1, 16, 12);",
        ]
    )

    assert detect_toolboxes(code) == [
        "Control System Toolbox",
        "Signal Processing Toolbox",
        "Communications Toolbox",
        "Optimization Toolbox",
        "System Identification Toolbox",
        "Simulink",
        "DSP System Toolbox",
        "Fixed-Point Designer",
    ]


def test_toolbox_false_positive_cases_do_not_match() -> None:
    code = "tf = 0.01;\nfilter = 3;\nmy_tf_value = 1;\nfi = 5;"

    toolboxes = detect_toolboxes(code)

    assert "Control System Toolbox" not in toolboxes
    assert "Signal Processing Toolbox" not in toolboxes
    assert "Fixed-Point Designer" not in toolboxes


def _extract(raw_code: str):
    folded, line_map = preprocess(raw_code)
    return extract_functions(folded, line_map, raw_code.splitlines())
