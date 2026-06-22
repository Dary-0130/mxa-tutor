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

function testFormatReceiptIgnoresServerMessage(testCase)
receipt = struct( ...
    "request_id", "2690af3d-9cfe-4442-900e-c86af37a6244", ...
    "status", "received", ...
    "mode", "connectivity_stub", ...
    "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");

text = mxa.bridge.formatReceipt(receipt);

verifyTrue(testCase, contains(text, "连接回执已收到"));
verifyTrue(testCase, contains(text, "status: received"));
verifyTrue(testCase, contains(text, "mode: connectivity_stub"));
verifyFalse(testCase, contains(text, "不提供报错解释"));
end

function testFormatExplanationRendersContractFields(testCase)
explanation = makeExplanation("2690af3d-9cfe-4442-900e-c86af37a6244");

text = mxa.bridge.formatExplanation(explanation);

verifyTrue(testCase, contains(text, "报错解释已生成"));
verifyTrue(testCase, contains(text, "含义:"));
verifyTrue(testCase, contains(text, "可能原因:"));
verifyTrue(testCase, contains(text, "下一步:"));
verifyTrue(testCase, contains(text, "提示:"));
verifyTrue(testCase, contains(text, "mode: llm_error_explanation"));
end

function testSubmitSendsExplanationAfterValidatedAck(testCase)
diagnosticPayload = [];
explanationPayload = [];

app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();
responseText = strjoin(string(app.ResponseTextArea.Value), newline);

verifyTrue(testCase, submitted);
verifyNotEmpty(testCase, app.LastReceipt);
verifyNotEmpty(testCase, app.LastExplanation);
verifyEqual(testCase, string(diagnosticPayload.protocol_version), "0.3-a");
verifyEqual(testCase, string(explanationPayload.protocol_version), "0.3-b1");
verifyEqual(testCase, string(explanationPayload.request_id), string(diagnosticPayload.request_id));
verifyTrue(testCase, isfield(explanationPayload, "llm_processing_consent_confirmed"));
verifyTrue(testCase, contains(responseText, "连接回执已收到"));
verifyTrue(testCase, contains(responseText, "报错解释已生成"));
verifyFalse(testCase, contains(responseText, "不提供报错解释"));

    function receipt = fakeDiagnosticPost(~, payload, timeoutSeconds)
        diagnosticPayload = payload;
        verifyEqual(testCase, timeoutSeconds, 10);
        receipt = struct( ...
            "request_id", payload.request_id, ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, payload, timeoutSeconds)
        explanationPayload = payload;
        verifyEqual(testCase, timeoutSeconds, 60);
        explanation = makeExplanation(payload.request_id);
    end
end

function testExplanationFailureKeepsNeutralAck(testCase)
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();
responseText = strjoin(string(app.ResponseTextArea.Value), newline);

verifyTrue(testCase, submitted);
verifyNotEmpty(testCase, app.LastReceipt);
verifyEmpty(testCase, app.LastExplanation);
verifyTrue(testCase, contains(responseText, "连接回执已收到"));
verifyTrue(testCase, contains(responseText, "解释失败"));
verifyFalse(testCase, contains(responseText, "不提供报错解释"));
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:HTTP5xx");

    function receipt = fakeDiagnosticPost(~, payload, ~)
        receipt = struct( ...
            "request_id", payload.request_id, ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanation = [];
        error("mxa:bridge:HTTP5xx", "service unavailable");
    end
end

function testInvalidAckDoesNotSendExplanation(testCase)
explanationCalls = 0;
app = mxa.bridge.MatlabBridgeApp( ...
    BaseUrl="http://localhost:8000", ...
    Visible="off", ...
    ConfirmFunction=@(~, ~) true, ...
    DiagnosticPostFunction=@fakeDiagnosticPost, ...
    ExplanationPostFunction=@fakeExplanationPost);
cleanup = onCleanup(@() delete(app));

app.setErrorText("Error using sim. Undefined function or variable Kp_ctrl.");
submitted = app.submitManualError();

verifyFalse(testCase, submitted);
verifyEmpty(testCase, app.LastReceipt);
verifyEqual(testCase, explanationCalls, 0);
verifyEqual(testCase, app.LastErrorIdentifier, "mxa:bridge:InvalidReceipt");

    function receipt = fakeDiagnosticPost(~, ~, ~)
        receipt = struct( ...
            "request_id", "11111111-1111-4111-8111-111111111111", ...
            "status", "received", ...
            "mode", "connectivity_stub", ...
            "message", "连接成功。本版本仅验证诊断信息传输,不提供报错解释。");
    end

    function explanation = fakeExplanationPost(~, ~, ~)
        explanationCalls = explanationCalls + 1;
        explanation = makeExplanation("11111111-1111-4111-8111-111111111111");
    end
end

function explanation = makeExplanation(requestId)
cause = struct( ...
    "cause", "Kp_ctrl 可能尚未定义或未进入当前 workspace。", ...
    "is_inference", true, ...
    "confidence", "medium", ...
    "supporting_signals", {{"Undefined function or variable Kp_ctrl"}});
step = struct("action", "先运行 which 查看名称解析,再检查初始化脚本。");
explanation = struct( ...
    "protocol_version", "0.3-b1", ...
    "request_id", requestId, ...
    "status", "completed", ...
    "mode", "llm_error_explanation", ...
    "meaning", "这段报错表示 MATLAB 没找到 Kp_ctrl 这个名称。", ...
    "likely_causes", cause, ...
    "next_steps", step, ...
    "caveats", {{"这里只基于粘贴的报错文本,没有运行仿真。"}});
end
