from adapters.parser.dependency_analyzer import analyze_dependencies
from core.domain.m_file import MFunction
from core.domain.project import FileInfo


def _fn(name: str) -> MFunction:
    return MFunction(
        name=name,
        inputs=[],
        outputs=[],
        line_range=(1, 1),
        docstring=None,
    )


def test_m_to_m_basic_call(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("B.m")]
    m_files = [
        make_m_file("A.m", raw_code="function y = foo(x)\ny=x;", functions=[_fn("foo")]),
        make_m_file("B.m", raw_code="y = foo(x);"),
    ]

    assert analyze_dependencies(files, m_files) == {"B.m": ["A.m"]}


def test_m_to_m_self_call_excluded(make_file_info, make_m_file):
    files = [make_file_info("A.m")]
    raw_code = "function y = foo(x)\ny = bar(x);\nfunction z = bar(x)\nz = foo(x);"
    m_files = [make_m_file("A.m", raw_code=raw_code, functions=[_fn("foo"), _fn("bar")])]

    assert analyze_dependencies(files, m_files) == {}


def test_m_to_m_builtin_excluded(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("disp.m")]
    m_files = [
        make_m_file("A.m", raw_code="disp(x); y = length(x);"),
        make_m_file("disp.m", functions=[_fn("disp")]),
    ]

    assert analyze_dependencies(files, m_files) == {}


def test_m_to_m_duplicate_name(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("B.m"), make_file_info("C.m")]
    m_files = [
        make_m_file("A.m", functions=[_fn("helper")]),
        make_m_file("B.m", functions=[_fn("helper")]),
        make_m_file("C.m", raw_code="y = helper(x);"),
    ]

    assert analyze_dependencies(files, m_files) == {"C.m": ["A.m", "B.m"]}


def test_m_to_m_unresolved_silent(make_file_info, make_m_file):
    files = [make_file_info("A.m")]
    m_files = [make_m_file("A.m", raw_code="y = mystery(x);")]

    assert analyze_dependencies(files, m_files) == {}


def test_m_to_mat_load_basic(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("data.mat")]
    m_files = [make_m_file("A.m", raw_code="load('data.mat');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["data.mat"]}


def test_m_to_mat_load_no_extension(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("data.mat")]
    m_files = [make_m_file("A.m", raw_code="load('data');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["data.mat"]}


def test_m_to_mat_loadmat_alias(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("data.mat")]
    m_files = [make_m_file("A.m", raw_code="loadmat('data.mat');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["data.mat"]}


def test_m_to_mat_importdata(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("data.mat")]
    m_files = [make_m_file("A.m", raw_code="importdata('data.mat');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["data.mat"]}


def test_m_to_mat_unresolved_silent(make_file_info, make_m_file):
    files = [make_file_info("A.m")]
    m_files = [make_m_file("A.m", raw_code="load('ghost.mat');")]

    assert analyze_dependencies(files, m_files) == {}


def test_m_to_slx_sim(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("model.slx")]
    m_files = [make_m_file("A.m", raw_code="sim('model.slx');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["model.slx"]}


def test_m_to_slx_sim_no_extension(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("model.slx")]
    m_files = [make_m_file("A.m", raw_code="sim('model');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["model.slx"]}


def test_m_to_slx_load_system(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("model.slx")]
    m_files = [make_m_file("A.m", raw_code="load_system('model');\nopen_system('model');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["model.slx"]}


def test_m_to_slx_set_param_with_subpath(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("model.slx")]
    m_files = [make_m_file("A.m", raw_code="set_param('model/SpeedLoop/PID', 'Gain', '1');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["model.slx"]}


def test_comment_stripped_avoids_false_positive(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("xxx.mat")]
    m_files = [make_m_file("A.m", raw_code="% load('xxx.mat')\nx = 1;")]

    assert analyze_dependencies(files, m_files) == {}


def test_block_comment_stripped(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("xxx.mat")]
    m_files = [make_m_file("A.m", raw_code="%{\nload('xxx.mat')\n%}\nx = 1;")]

    assert analyze_dependencies(files, m_files) == {}


def test_string_literal_may_false_positive(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("xxx.mat")]
    m_files = [make_m_file("A.m", raw_code="message = \"load('xxx.mat')\";")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["xxx.mat"]}


def test_target_list_sorted_dedup(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("data.mat")]
    raw_code = "load('data.mat');\nload('data');\nload data.mat"
    m_files = [make_m_file("A.m", raw_code=raw_code)]

    assert analyze_dependencies(files, m_files) == {"A.m": ["data.mat"]}


def test_no_outgoing_omitted(make_file_info, make_m_file):
    files = [make_file_info("A.m"), make_file_info("helper.m")]
    m_files = [
        make_m_file("A.m", raw_code="x = 1;"),
        make_m_file("helper.m", functions=[_fn("helper")]),
    ]

    assert analyze_dependencies(files, m_files) == {}


def test_path_separator_normalized(make_file_info, make_m_file):
    files: list[FileInfo] = [make_file_info("A.m"), make_file_info("subdir/data.mat")]
    m_files = [make_m_file("A.m", raw_code="load('subdir\\\\data.mat');")]

    assert analyze_dependencies(files, m_files) == {"A.m": ["subdir/data.mat"]}


def test_empty_inputs():
    assert analyze_dependencies([], []) == {}
