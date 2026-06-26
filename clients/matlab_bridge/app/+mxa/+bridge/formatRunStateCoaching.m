function text = formatRunStateCoaching(result)
%FORMATRUNSTATECOACHING Convert a run-state coaching result to UI text.

lines = "运行状态陪调已生成。";
lines(end + 1) = "mode: " + readValue(result, "mode", "");
lines(end + 1) = "outcome: " + readValue(result, "outcome", "");
summary = readValue(result, "run_summary", "");
if strlength(summary) > 0
    lines(end + 1) = "摘要: " + summary;
end

if isstruct(result) && isfield(result, "signal_readings")
    readings = asStructArray(result.signal_readings);
    if ~isempty(readings)
        lines(end + 1) = "观察:";
        for index = 1:numel(readings)
            lines(end + 1) = "- " + readValue(readings(index), "reading", "");
        end
    end
end

if isstruct(result) && isfield(result, "primary_directions")
    directions = asStructArray(result.primary_directions);
    if ~isempty(directions)
        lines(end + 1) = "建议方向:";
        for index = 1:numel(directions)
            action = readValue(directions(index), "action", "");
            band = readValue(directions(index), "magnitude_band", "");
            lines(end + 1) = "- " + action + " / " + band;
        end
    end
end

if isstruct(result) && isfield(result, "uncertainties")
    uncertainties = string(result.uncertainties);
    if ~isempty(uncertainties)
        lines(end + 1) = "不确定:";
        for index = 1:numel(uncertainties)
            lines(end + 1) = "- " + uncertainties(index);
        end
    end
end

if isstruct(result) && isfield(result, "caveats")
    caveats = string(result.caveats);
    if ~isempty(caveats)
        lines(end + 1) = "提示:";
        for index = 1:numel(caveats)
            lines(end + 1) = "- " + caveats(index);
        end
    end
end

text = strjoin(lines, newline);
end

function value = readValue(source, fieldName, defaultValue)
value = string(defaultValue);
if isstruct(source) && isfield(source, fieldName)
    value = string(source.(fieldName));
end
end

function array = asStructArray(value)
if iscell(value)
    array = [value{:}];
else
    array = value;
end
end
