function text = formatExplanation(explanation)
%FORMATEXPLANATION Convert a bridge explanation result struct to UI text.

lines = "报错解释已生成。";
meaning = readValue(explanation, "meaning", "");
if strlength(meaning) > 0
    lines(end + 1) = "";
    lines(end + 1) = "含义: " + meaning;
end

causes = readValue(explanation, "likely_causes", []);
if isstruct(causes) && ~isempty(causes)
    lines(end + 1) = "";
    lines(end + 1) = "可能原因:";
    for index = 1:numel(causes)
        cause = readValue(causes(index), "cause", "");
        confidence = readValue(causes(index), "confidence", "");
        if strlength(confidence) > 0
            lines(end + 1) = string(index) + ". " + cause + " (" + confidence + ")";
        else
            lines(end + 1) = string(index) + ". " + cause;
        end
    end
end

steps = readValue(explanation, "next_steps", []);
if isstruct(steps) && ~isempty(steps)
    lines(end + 1) = "";
    lines(end + 1) = "下一步:";
    for index = 1:numel(steps)
        action = readValue(steps(index), "action", "");
        lines(end + 1) = string(index) + ". " + action;
    end
end

caveats = readStringList(readValue(explanation, "caveats", []));
if ~isempty(caveats)
    lines(end + 1) = "";
    lines(end + 1) = "提示:";
    for index = 1:numel(caveats)
        lines(end + 1) = "- " + caveats(index);
    end
end

status = readValue(explanation, "status", "");
mode = readValue(explanation, "mode", "");
requestId = readValue(explanation, "request_id", "");
if strlength(status) > 0 || strlength(mode) > 0 || strlength(requestId) > 0
    lines(end + 1) = "";
end
if strlength(status) > 0
    lines(end + 1) = "status: " + status;
end
if strlength(mode) > 0
    lines(end + 1) = "mode: " + mode;
end
if strlength(requestId) > 0
    lines(end + 1) = "request_id: " + requestId;
end

text = strjoin(lines, newline);
end

function value = readValue(item, fieldName, defaultValue)
value = defaultValue;
if isstruct(item) && isfield(item, fieldName)
    value = item.(fieldName);
end
if ischar(value) || isstring(value)
    value = string(value);
end
end

function values = readStringList(value)
if isempty(value)
    values = strings(0, 1);
elseif iscell(value)
    values = string(value);
elseif isstring(value) || ischar(value)
    values = string(value);
else
    values = string(value);
end
values = values(:);
end
