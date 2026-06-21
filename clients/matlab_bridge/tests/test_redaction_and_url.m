function tests = test_redaction_and_url
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
rootDir = fileparts(fileparts(mfilename("fullpath")));
appDir = fullfile(rootDir, "app");
addpath(appDir);
testCase.TestData.PathCleanup = onCleanup(@() rmpath(appDir));
end

function testRedactsSupportedAbsolutePaths(testCase)
inputText = [
    "Error in C:\Users\alice\secret\model.m"
    "UNC \\server\share\private\file.m"
    "POSIX /home/alice/project/file.m"
    "URI file:///C:/Users/alice/private/file.m"
];

sanitized = mxa.bridge.redactDiagnosticText(strjoin(inputText, newline));

verifyFalse(testCase, contains(sanitized, "C:\Users\alice"));
verifyFalse(testCase, contains(sanitized, "\\server\share"));
verifyFalse(testCase, contains(sanitized, "/home/alice"));
verifyFalse(testCase, contains(sanitized, "file:///C:/Users"));
verifyGreaterThanOrEqual(testCase, count(sanitized, "[REDACTED_PATH]"), 4);
end

function testValidateBaseUrlAllowsLocalhostHttp(testCase)
verifyWarningFree(testCase, @() mxa.bridge.validateBaseUrl("http://localhost:8000"));
end

function testValidateBaseUrlAllowsHttps(testCase)
verifyWarningFree(testCase, @() mxa.bridge.validateBaseUrl("https://example.com"));
end

function testValidateBaseUrlRejectsRemoteHttp(testCase)
verifyError( ...
    testCase, ...
    @() mxa.bridge.validateBaseUrl("http://127.0.0.1:8000"), ...
    "mxa:bridge:InvalidBaseUrl");
end

function testValidateBaseUrlRejectsUserInfo(testCase)
verifyError( ...
    testCase, ...
    @() mxa.bridge.validateBaseUrl("https://user:secret@example.com"), ...
    "mxa:bridge:InvalidBaseUrl");
end

function testCancelDoesNotSend(testCase)
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) false);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error in C:\Users\alice\secret\model.m");
submitted = app.submitManualError();

verifyFalse(testCase, submitted);
verifyEmpty(testCase, app.LastReceipt);
verifyFalse(testCase, contains(app.LastSanitizedText, "C:\Users\alice"));
end
