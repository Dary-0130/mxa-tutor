function snapshot = captureExceptionSnapshot(caughtException)
%CAPTUREEXCEPTIONSNAPSHOT Build a redacted immutable auto-captured error snapshot.

try
    rawSnapshot = strjoin(renderException(caughtException, 0), newline);
    redactedSnapshot = mxa.bridge.redactDiagnosticText(rawSnapshot);
    snapshot = truncateSnapshot(redactedSnapshot);
catch ME
    if strcmp(string(ME.identifier), "mxa:bridge:AutoCaptureFailed")
        rethrow(ME);
    end
    error("mxa:bridge:AutoCaptureFailed", "自动采集失败。");
end

if strlength(strtrim(snapshot)) == 0
    error("mxa:bridge:AutoCaptureFailed", "自动采集为空。");
end
end

function lines = renderException(item, depth)
lines = strings(0, 1);
if depth > 3
    return
end

identifier = limitText(readTextProperty(item, "identifier"), 128);
if depth == 0
    message = limitText(readTextProperty(item, "message"), 2048);
else
    message = limitText(readTextProperty(item, "message"), 768);
end
if depth == 0
    lines(end + 1, 1) = "identifier: " + identifier;
    lines(end + 1, 1) = "message:";
    lines(end + 1, 1) = message;
else
    indent = indentText(depth - 1);
    lines(end + 1, 1) = indent + "- identifier: " + identifier;
    lines(end + 1, 1) = indent + "  message:";
    lines(end + 1, 1) = indent + "  " + message;
end

stackLines = renderStack(readProperty(item, "stack"), depth);
if ~isempty(stackLines)
    if depth == 0
        lines(end + 1, 1) = "stack:";
    else
        indent = indentText(depth - 1);
        lines(end + 1, 1) = indent + "  stack:";
    end
    lines = [lines; stackLines]; %#ok<AGROW>
end

if depth >= 3
    return
end
causes = readProperty(item, "cause");
if isempty(causes)
    return
end
if depth == 0
    lines(end + 1, 1) = "causes:";
end

causeCount = min(numel(causes), 3);
for index = 1:causeCount
    if iscell(causes)
        causeItem = causes{index};
    else
        causeItem = causes(index);
    end
    lines = [lines; renderException(causeItem, depth + 1)]; %#ok<AGROW>
end
end

function lines = renderStack(stackItems, depth)
lines = strings(0, 1);
if ~isstruct(stackItems) || isempty(stackItems)
    return
end

indent = indentText(depth);
frameCount = min(numel(stackItems), 8);
for index = 1:frameCount
    name = limitText(readTextProperty(stackItems(index), "name"), 160);
    lineText = readLineNumber(stackItems(index));
    if strlength(name) == 0 && strlength(lineText) == 0
        continue
    end
    if strlength(lineText) > 0
        lines(end + 1, 1) = indent + "- name: " + name + ", line: " + lineText; %#ok<AGROW>
    else
        lines(end + 1, 1) = indent + "- name: " + name; %#ok<AGROW>
    end
end
end

function text = indentText(depth)
text = "";
for index = 1:max(depth, 0)
    text = text + "  ";
end
end

function value = readProperty(item, propertyName)
value = [];
try
    if isstruct(item) || isobject(item)
        value = item.(char(propertyName));
    end
catch
    value = [];
end
end

function value = readTextProperty(item, propertyName)
rawValue = readProperty(item, propertyName);
if isempty(rawValue)
    value = "";
else
    value = string(rawValue);
    value = strjoin(splitlines(value), newline);
end
end

function text = readLineNumber(stackFrame)
text = "";
lineValue = readProperty(stackFrame, "line");
if isnumeric(lineValue) && isscalar(lineValue) && isfinite(lineValue)
    text = string(floor(lineValue));
end
end

function value = limitText(value, maxChars)
value = string(value);
if strlength(value) > maxChars
    value = extractBefore(value, maxChars + 1);
end
end

function snapshot = truncateSnapshot(value)
marker = "[TRUNCATED_AUTO_CAPTURE]";
maxChars = 4096;
snapshot = string(value);
if strlength(snapshot) <= maxChars
    return
end

keepChars = maxChars - strlength(marker) - 1;
if keepChars < 1
    snapshot = marker;
else
    snapshot = extractBefore(snapshot, keepChars + 1) + newline + marker;
end
end
