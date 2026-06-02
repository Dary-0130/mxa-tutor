"""Regex patterns and builtin whitelist for file dependency analysis."""

import re

RE_BLOCK_COMMENT = re.compile(
    r"^\s*%\{[^\n]*\n.*?^\s*%\}[^\n]*$",
    re.MULTILINE | re.DOTALL,
)
RE_LINE_COMMENT = re.compile(r"%[^\n]*")

RE_LOAD_CALL = re.compile(
    r"\b(?:load|loadmat|importdata)\s*"
    r"(?:"
    r"\(\s*['\"]([^'\"]+)['\"]"
    r"|"
    r"\s+([A-Za-z_]\w*(?:\.\w+)?)"
    r")",
)
RE_SIM_CALL = re.compile(
    r"\b(?:sim|load_system|open_system|set_param)\s*"
    r"\(\s*['\"]([^'\"]+)['\"]",
)
RE_IDENTIFIER_CALL = re.compile(r"(?<![.\w@])([A-Za-z_]\w*)\s*\(")

_BUILTIN_NAMES = (
    "disp fprintf sprintf print warning error input keyboard "
    "size length numel ndims isempty isnan isinf isreal isnumeric ischar isstring "
    "iscell isstruct islogical class isa double single int8 int16 int32 int64 uint8 "
    "uint16 uint32 uint64 char string logical cell "
    "abs sqrt exp log log2 log10 sin cos tan asin acos atan atan2 sinh cosh tanh "
    "floor ceil round fix mod rem sign max min sum prod mean median std var cumsum "
    "cumprod diff zeros ones eye rand randn linspace logspace repmat reshape "
    "transpose permute squeeze kron horzcat vertcat cat true false isequal isequaln "
    "any all find strcmp strcmpi strcat strsplit strrep strtrim regexp regexprep "
    "lower upper num2str str2num str2double exist fopen fclose fread fwrite "
    "fileparts fullfile pwd cd ls dir mkdir rmdir plot subplot figure hold grid axis "
    "xlabel ylabel title legend colorbar colormap scatter bar stem semilogx semilogy "
    "loglog polar surf mesh contour imagesc image imshow tf zpk ss step impulse bode "
    "nyquist rlocus margin feedback series parallel minreal balreal fft ifft filter "
    "conv xcorr freqz feval nargin nargout varargin varargout isfield fieldnames "
    "struct cellfun arrayfun structfun lasterr lasterror MException throw rethrow tic "
    "toc clock now datestr datenum pause deal assert"
)

BUILTIN_FUNCTIONS: frozenset[str] = frozenset(_BUILTIN_NAMES.split())
