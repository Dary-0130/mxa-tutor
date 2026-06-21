function text = formatReceipt(receipt)
%FORMATRECEIPT Convert the bridge receipt struct to UI text.

message = readValue(receipt, "message", "连接成功。");
status = readValue(receipt, "status", "");
mode = readValue(receipt, "mode", "");
requestId = readValue(receipt, "request_id", "");

lines = string(message);
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

function value = readValue(receipt, fieldName, defaultValue)
value = string(defaultValue);
if isstruct(receipt) && isfield(receipt, fieldName)
    value = string(receipt.(fieldName));
end
end
