function sanitized = redactRunStateString(inputText, maxChars, maxBytes)
%REDACTRUNSTATESTRING Redact and bound one run-state string field.

if nargin < 2
    maxChars = 32;
end
if nargin < 3
    maxBytes = 96;
end

sanitized = string(inputText);
sanitized = strjoin(splitlines(sanitized), " ");
sanitized = mxa.bridge.redactDiagnosticText(sanitized);
sanitized = regexprep(sanitized, ...
    '(?i)\b(UserID|MachineName|ModelFilePath)\s*[:=]\s*[^\s,''"<>]+', ...
    '[REDACTED_METADATA]');
sanitized = strip(sanitized);

if strlength(sanitized) == 0
    sanitized = "unknown";
end
if containsUnsafeControl(sanitized)
    error("mxa:bridge:RunStateUnsafeString", "run-state string contains unsafe control characters.");
end

if strlength(sanitized) > maxChars
    sanitized = extractBefore(sanitized, maxChars + 1);
end
while utf8Length(sanitized) > maxBytes && strlength(sanitized) > 0
    sanitized = extractBefore(sanitized, strlength(sanitized));
end
if strlength(sanitized) == 0
    error("mxa:bridge:RunStateUnsafeString", "run-state string exceeds byte limits.");
end
end

function unsafe = containsUnsafeControl(value)
text = char(value);
unsafe = any(text < 32) || any(text == 127);
bidiControls = [8234 8235 8236 8237 8238 8294 8295 8296 8297];
unsafe = unsafe || any(ismember(double(text), bidiControls));
end

function count = utf8Length(value)
count = numel(unicode2native(char(value), "UTF-8"));
end
