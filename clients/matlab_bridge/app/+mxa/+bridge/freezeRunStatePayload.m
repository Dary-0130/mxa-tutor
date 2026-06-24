function [frozenJson, frozenBytes] = freezeRunStatePayload(payload)
%FREEZERUNSTATEPAYLOAD Encode once and enforce the 28KB UTF-8 preflight.

rejectUnsafeJsonValue(payload);
frozenJson = string(jsonencode(payload));
frozenBytes = unicode2native(char(frozenJson), "UTF-8");
if numel(frozenBytes) > 28 * 1024
    error("mxa:bridge:RunStatePayloadTooLarge", "run-state payload exceeds 28KB.");
end
end

function rejectUnsafeJsonValue(value)
if isnumeric(value)
    if any(~isfinite(value), "all")
        error("mxa:bridge:RunStateNonFiniteValue", ...
            "run-state payload contains a non-finite numeric value.");
    end
    return
end
if islogical(value) || ischar(value) || isstring(value)
    return
end
if iscell(value)
    for index = 1:numel(value)
        rejectUnsafeJsonValue(value{index});
    end
    return
end
if isstruct(value)
    fields = fieldnames(value);
    for itemIndex = 1:numel(value)
        for fieldIndex = 1:numel(fields)
            rejectUnsafeJsonValue(value(itemIndex).(fields{fieldIndex}));
        end
    end
    return
end
error("mxa:bridge:RunStateUnsupportedJsonValue", ...
    "run-state payload contains an unsupported JSON value.");
end
