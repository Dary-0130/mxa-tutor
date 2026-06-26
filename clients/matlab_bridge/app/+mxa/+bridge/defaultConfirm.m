function confirmed = defaultConfirm(parent, sanitizedText, context)
%DEFAULTCONFIRM Ask the user before sending the immutable sanitized snapshot.

if nargin < 3
    context = "diagnostic";
end

contextText = string(context);
[title, confirmOption, details] = mxa.bridge.defaultConfirmCopy(contextText);

message = sprintf("%s\n\n%s", mxa.bridge.MatlabBridgeApp.SafetyPrompt, sanitizedText);
if strlength(details) > 0
    message = sprintf("%s\n\n%s", details, message);
end
choice = uiconfirm( ...
    parent, ...
    message, ...
    title, ...
    "Options", [confirmOption, "Cancel"], ...
    "DefaultOption", "Cancel", ...
    "CancelOption", "Cancel");

confirmed = strcmp(choice, confirmOption);
end
